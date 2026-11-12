# SPDX-License-Identifier: GPL-3.0-or-later

"""A training snapshot's new parts, as item 7's and item 8a's snapshots
were built (data/manifests/g3s2.json, g3s3.json), for retrain 8b's g4s1
(docs/research/retrain-8b/plan.md). Bare Python: no python-chess (the shards
were verified at their seal; this splits whole games and counts records).

1. `hold SHARD --games N --prefix P --out DIR [--exclude SITES.jsonl...]`:
   a part's designated validation shard (its *-val.vf) split by whole
   games: its first N games go to DIR/P-<shard>-held.vf (validation only),
   the rest to DIR/P-<shard>-rest.vf (training). --exclude names site files
   whose "game" fields ("SHARD#INDEX", the index 0-based in the shard) mark
   games kept out of both, so positions that a label study holds out never
   train (retrain 8b: idea 51's H and the ensemble teacher's H2, both drawn
   from g3j-w05-val.vf).
2. `val --base FILE --streams K --held FILE... --out FILE`: the snapshot's
   validation file: the base validation file's K streams (game i belongs to
   stream i mod K, as each earlier snapshot interleaved its sources) and
   each held file as one more stream, merged one game at a time, so the
   first positions (the trainer's monitoring prefix) come from every source.
3. `record NAME FILE... --out JSON [--note TEXT]`: the files' games,
   records, unsaved records, saved records, bytes and SHA-256, as a
   manifest in data/manifests' layout ({"run": NAME, "batches": [[...]]},
   at most 50 files a batch, Kaggle's top-level limit), which the training
   kernels check every mounted file against.

    snapshot_parts.py hold SHARD --games 60 --prefix g4s1 --out DIR [--exclude SITES...]
    snapshot_parts.py val --base g3s3-val.vf --streams 32 --held H... --out g4s1-val.vf
    snapshot_parts.py record NAME FILE... --out NAME.json [--note TEXT]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

UNSAVED = 32767      # src/datagen/self_play.hpp: an unsaved position's record
BATCH_FILES = 50     # tools/datagen/upload_batch.py: Kaggle's top-level file limit


def game_spans(data):
    """(start, end, records, unsaved records) of each game; raises ValueError on a truncated file."""
    out, i, n = [], 0, len(data)
    while i < n:
        if n - i < 32:
            raise ValueError(f'truncated board at byte {i}')
        j, recs, unsaved = i + 32, 0, 0
        while True:
            if n - j < 4:
                raise ValueError(f'truncated moves at byte {j}')
            code = data[j] | data[j + 1] << 8
            score = data[j + 2] | data[j + 3] << 8
            j += 4
            if code == 0:
                break
            recs += 1
            unsaved += score == UNSAVED
        out.append((i, j, recs, unsaved))
        i = j
    return out


def stats_of(name, data):
    spans = game_spans(data)
    n = sum(s[2] for s in spans)
    u = sum(s[3] for s in spans)
    return {'file': name, 'games': len(spans), 'positions': n, 'positions_unsaved': u, 'positions_saved': n - u,
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def excluded_games(paths, shard_name):
    """The game indices of `shard_name` that the site files name."""
    out = set()
    for p in paths:
        for line in Path(p).read_text(encoding='utf-8').splitlines():
            if line.strip():
                game = json.loads(line).get('game', '')
                if '#' in game and game.rsplit('#', 1)[0] == shard_name:
                    out.add(int(game.rsplit('#', 1)[1]))
    return out


def hold(data, games, exclude):
    """(held bytes, rest bytes, games excluded from the rest)."""
    spans = game_spans(data)
    if len(spans) < games:
        raise ValueError(f'{len(spans)} games, {games} to hold')
    held = b''.join(data[s:e] for s, e, _, _ in spans[:games])
    rest = b''.join(data[s:e] for k, (s, e, _, _) in enumerate(spans) if k >= games and k not in exclude)
    return held, rest, sum(1 for k in exclude if games <= k < len(spans))


def merge_streams(streams):
    """One game from each stream in turn, until every stream is empty."""
    out = bytearray()
    for i in range(max(len(s) for s in streams)):
        for s in streams:
            if i < len(s):
                out += s[i]
    return bytes(out)


def write_atomic(path, data):
    tmp = path.with_name(path.name + '.part')
    tmp.write_bytes(data)
    tmp.replace(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('hold')
    p.add_argument('shard', type=Path)
    p.add_argument('--games', type=int, required=True)
    p.add_argument('--prefix', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--exclude', type=Path, nargs='*', default=[])
    p = sub.add_parser('val')
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--streams', type=int, required=True)
    p.add_argument('--held', type=Path, nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('record')
    p.add_argument('name')
    p.add_argument('files', type=Path, nargs='+')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--note', default='')
    a = ap.parse_args(argv)
    try:
        if a.command == 'hold':
            data = a.shard.read_bytes()
            exclude = excluded_games(a.exclude, a.shard.name)
            held, rest, dropped = hold(data, a.games, exclude)
            stem = a.shard.name[:-3] if a.shard.name.endswith('.vf') else a.shard.name
            a.out.mkdir(parents=True, exist_ok=True)
            names = (f'{a.prefix}-{stem}-held.vf', f'{a.prefix}-{stem}-rest.vf')
            write_atomic(a.out / names[0], held)
            write_atomic(a.out / names[1], rest)
            info = {'source': a.shard.name, 'source_sha256': hashlib.sha256(data).hexdigest(), 'held_games': a.games,
                    'excluded_games': dropped,
                    'exclude_files': {f'{p.parent.name}/{p.name}': hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in a.exclude},
                    'held': stats_of(names[0], held), 'rest': stats_of(names[1], rest)}
            print(json.dumps(info))
            return 0
        if a.command == 'val':
            base = a.base.read_bytes()
            spans = game_spans(base)
            if len(spans) % a.streams:
                raise ValueError(f'{len(spans)} base games do not split into {a.streams} streams')
            streams = [[base[s:e] for s, e, _, _ in spans[i::a.streams]] for i in range(a.streams)]
            for h in a.held:
                d = h.read_bytes()
                streams.append([d[s:e] for s, e, _, _ in game_spans(d)])
            out = merge_streams(streams)
            write_atomic(a.out, out)
            print(json.dumps({'base': a.base.name, 'streams': len(streams), **stats_of(a.out.name, out)}))
            return 0
        rows = [stats_of(f.name, f.read_bytes()) for f in a.files]
        record = {'run': a.name, 'note': a.note,
                  'totals': {k: sum(r[k] for r in rows) for k in ('games', 'positions', 'positions_unsaved',
                                                                   'positions_saved', 'bytes')},
                  'batches': [rows[i:i + BATCH_FILES] for i in range(0, len(rows), BATCH_FILES)]}
        a.out.write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8')
        print(json.dumps({'run': a.name, 'files': len(rows), **record['totals']}))
        return 0
    except (ValueError, OSError) as e:
        print(f'FAIL {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
