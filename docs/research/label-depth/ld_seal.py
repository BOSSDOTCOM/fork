# SPDX-License-Identifier: GPL-3.0-or-later
"""Seals one label-depth arm (or a volume control cut from D20) as its own part, as the Control Center's
seal_part.py seals a generation part: copy each worker's complete games, write the run manifest, verify every game
with tools/datagen/verify_games.py (--manifest, --table-pieces 5), then tools/datagen/upload_batch.py seal writes
data/manifests/<run>.json. Also writes the Kaggle dataset-metadata.json (fork-<run>).

Held-out file: with 3 workers a whole held-out worker would take a third of the arm's data, so the last worker's
first games, up to VAL_KEPT positions kept by the trainer's filter, become <run>-w02-val.vf and the rest of that
worker <run>-w02.vf (the trainer validates on the first 20,000 kept positions of the -val file, as idea13.py).

    python -I ld_seal.py arm RUN OUT_DIR REPO --nodes N --hash-mb H --segment SRC_DIR SRC_RUN SEED STARTED STOPPED
                         [--segment ...]   (one per segment of the run, in order: a resume after a stop is a
                         segment with its own seed, so no game repeats and game i opens alike in every arm)
    python -I ld_seal.py cut RUN D20_OUT_DIR TARGET_OUT_DIR OUT_DIR REPO
        (D20's training files cut, file by file, to the first games reaching the target arm's kept count in the
        same file: the volume controls D20/50 and D20/100, design section 1.2)
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The repository whose tools are used (LD_TOOLS_REPO, for a copy of this script kept outside the repository).
TOOLS = Path(os.environ.get('LD_TOOLS_REPO') or HERE.parents[2])
sys.path.insert(0, str(TOOLS / 'tools' / 'datagen'))
sys.path.insert(0, str(TOOLS / 'tools' / 'control_center'))
import verify_games as V  # noqa: E402
from seal_part import complete_games  # noqa: E402

UNSAVED = 32767
MAX_EVAL = 20000
VAL_KEPT = 25000
OPENINGS_MANIFEST = 'openings-lichess-2026-09.json'  # every game's opening is the full book's for its segment's seed
VERSION = '0.3.0-dev+a4ee674'
NET = 's512ppr3'
SHARD = re.compile(r'^(?P<run>.+)-w(?P<worker>\d{2})-(?P<index>\d{4})\.vf$')


def games(data):
    """(start, end, kept, records, unsaved, result) per complete game of a shard."""
    i = 0
    while i + 32 <= len(data) and int.from_bytes(data[i:i + 8], 'little'):
        board, result = V.decode_board(data[i:i + 32])
        j, kept, records, unsaved, closed = i + 32, 0, 0, 0, False
        while j + 4 <= len(data):
            code, score = V.u16(data, j), V.i16(data, j + 2)
            j += 4
            if code == 0:
                closed = True
                break
            move = next(m for m in board.legal_moves if V.code_of(board, m) == code)
            records += 1
            if score == UNSAVED:
                unsaved += 1
            elif not board.is_check() and abs(score) <= MAX_EVAL and not (board.is_capture(move) or move.promotion):
                kept += 1
            board.push(move)
        if not closed:
            return
        yield i, j, kept, records, unsaved, result
        i = j


def game_digests(data):
    """A 16-byte digest per complete game: the start board's position bytes (0-27) and every move code."""
    i, n = 0, len(data)
    while i + 32 <= n and int.from_bytes(data[i:i + 8], 'little'):
        h = hashlib.blake2b(data[i:i + 28], digest_size=16)
        j = i + 32
        while j + 4 <= n:
            code = data[j:j + 2]
            j += 4
            if code == b'\0\0':
                break
            h.update(code)
        yield h.digest()
        i = j


def piece(data, name, worker, upto_kept=None, start=0):
    """The games of data from byte `start` while the kept count stays below upto_kept (all if None): returns
    (entry, end byte, totals)."""
    t = {'games': 0, 'positions': 0, 'unsaved': 0, 'kept': 0, 'results': [0, 0, 0]}
    end = start
    for s, e, kept, records, unsaved, result in games(data[start:]):
        if upto_kept is not None and t['kept'] >= upto_kept:
            break
        t['games'] += 1
        t['positions'] += records
        t['unsaved'] += unsaved
        t['kept'] += kept
        t['results'][result] += 1
        end = start + e
    return {'file': name, 'worker': worker, 'games': t['games'], 'positions': t['positions'],
            'bytes': end - start}, end, t


def add(totals, t):
    for k in ('games', 'positions', 'unsaved', 'kept'):
        totals[k] += t[k]
    totals['results'] = [a + b for a, b in zip(totals['results'], t['results'])]


def finish(run, out, repo, shards, totals, tool, settings, seconds, part_end, subtitle):
    manifest = {
        'tool': tool, 'version': f'{VERSION} (WSL clang PGO, clang 21.1.8)', 'evaluator': f'nnue ({NET})',
        'arch': 'native', 'settings': settings, 'games': totals['games'], 'positions': totals['positions'],
        'positions_unsaved': totals['unsaved'], 'seconds': seconds,
        'results': {'white': totals['results'][2], 'draw': totals['results'][1], 'black': totals['results'][0]},
        'ends': 'not counted (the run was stopped, not finished)', 'shards': shards,
    }
    (out / f'{run}.json').write_text(json.dumps(manifest, indent=1) + '\n', newline='\n')
    py = sys.executable
    rc = subprocess.call([py, '-I', str(TOOLS / 'tools' / 'datagen' / 'verify_games.py'),
                          *[str(out / s['file']) for s in shards], '--manifest', str(out / f'{run}.json'),
                          '--table-pieces', '5'])
    if rc != 0:
        sys.exit(f'{run}: verification FAILED (exit {rc}); nothing sealed, files kept in {out}')
    om = repo / 'data' / 'manifests' / OPENINGS_MANIFEST
    if not om.exists():
        om = HERE / OPENINGS_MANIFEST  # a copy beside this script (the main checkout's phase-4 lacks it)
    rc = subprocess.call([py, '-I', str(TOOLS / 'tools' / 'datagen' / 'upload_batch.py'), 'seal',
                          str(out / f'{run}.json'), '--openings-manifest', str(om), '--part-end', part_end,
                          '--out', str(repo / 'data' / 'manifests')])
    if rc != 0:
        sys.exit(f'{run}: upload_batch.py seal failed (exit {rc})')
    meta = {'title': f'fork-{run}', 'id': f'bossdotcom/fork-{run}', 'subtitle': subtitle,
            'licenses': [{'name': 'other'}], 'keywords': ['synthetic']}
    (out / 'dataset-metadata.json').write_text(json.dumps(meta, indent=2) + '\n', newline='\n')
    print(json.dumps({'run': run, 'kept': totals['kept'], **{k: totals[k] for k in ('games', 'positions', 'unsaved')},
                      'shards': shards}, indent=1))


def est(epoch):
    return time.strftime('%Y-%m-%d %I:%M:%S %p EST', time.localtime(epoch))


def seal_arm(run, out, repo, nodes, hash_mb, segments):
    """segments: [(src_dir, src_run, seed, started, stopped)], in order. Segment 1's files keep the names
    <run>-wWW.vf (the last worker split into its held-out file and the rest); segment k > 1's are <run>-sK-wWW.vf."""
    out.mkdir(parents=True, exist_ok=False)
    shards, totals = [], {'games': 0, 'positions': 0, 'unsaved': 0, 'kept': 0, 'results': [0, 0, 0]}
    dropped, seg_info, threads = 0, [], None
    seen, repeated = set(), 0  # digests of earlier segments' games (start position + every move)
    for k, (src, src_run, seed, started, stopped) in enumerate(segments, 1):
        this, rep_k = set(), 0
        files = sorted(f.name for f in Path(src).iterdir() if (m := SHARD.match(f.name)) and m['run'] == src_run)
        if not files:
            sys.exit(f'no shards of {src_run} in {src}')
        workers = sorted({int(SHARD.match(f)['worker']) for f in files})
        threads = threads or len(workers)
        if len(workers) != threads:
            sys.exit(f'segment {k} has {len(workers)} workers, segment 1 {threads}')
        if any(SHARD.match(f)['index'] != '0000' for f in files):
            sys.exit('more than one shard per worker: not handled')  # 1024 MB shards; an arm writes far less
        stem = run if k == 1 else f'{run}-s{k}'
        seg = {'games': 0, 'positions': 0, 'unsaved': 0, 'kept': 0, 'results': [0, 0, 0]}
        for f in files:
            w = int(SHARD.match(f)['worker'])
            data = Path(src, f).read_bytes()
            end = complete_games(data)[0]
            dropped += len(data) - end
            data = data[:end]
            for g in game_digests(data):
                if g in seen:
                    rep_k += 1
                this.add(g)
            cut = 0
            if k == 1 and w == workers[-1]:
                val, cut, t = piece(data, f'{stem}-w{w:02d}-val.vf', w, upto_kept=VAL_KEPT)
                (out / val['file']).write_bytes(data[:cut])
                shards.append(val)
                add(totals, t)
                add(seg, t)
            rest, end2, t = piece(data, f'{stem}-w{w:02d}.vf', w, start=cut)
            assert end2 == len(data)
            (out / rest['file']).write_bytes(data[cut:])
            shards.append(rest)
            add(totals, t)
            add(seg, t)
        book = f'lichess-2026-09-s{seed}-k2500000.epd'
        seg_info.append({'segment': k, 'run': src_run, 'seed': seed, 'openings_file': book,
                         'started': est(started), 'stopped': est(stopped), 'seconds': round(stopped - started, 1),
                         **{x: seg[x] for x in ('games', 'positions', 'unsaved', 'kept')},
                         'games_repeating_an_earlier_segment': rep_k})
        print(f'{run}: segment {k}: {seg["games"]} games, {rep_k} identical to an earlier segment\'s')
        repeated += rep_k
        seen |= this
    if repeated:
        sys.exit(f'{run}: {repeated} games of a later segment repeat an earlier segment\'s game (same start and '
                 f'moves); nothing sealed, files kept in {out}')
    print(f'{run}: {dropped} bytes of unfinished games dropped')
    seconds = round(sum(s['seconds'] for s in seg_info), 1)
    settings = {'openings': 'lichess-2026-09.epd', 'openings_count': 13943421, 'positions_target': 999000000,
                'nodes': nodes, 'threads': threads, 'seed': segments[0][2], 'hash_mb': hash_mb, 'shard_mb': 1024,
                'tables': 'syzygy 5-piece', 'decided_cp': 400, 'max_plies': 500, 'random_min': 2, 'random_max': 4,
                'adjudicate_cp': 700, 'adjudicate_plies': 8, 'save_percent': 50, 'unsaved_nodes': 4000,
                'check_nodes': 2000, 'wall_limit_seconds': 144000,
                'openings_note': ('each segment read a 2.5 M-line file (ld_book.py) giving every game the opening the '
                                  "full lichess-2026-09.epd gives it for that segment's seed"),
                'segments': seg_info}
    when = '; '.join(f"segment {s['segment']} (seed {s['seed']}) {s['started']} to {s['stopped']}" for s in seg_info)
    tool = (f'fork_datagen (complete games of the label-depth arm {run}, labelled by Fork {VERSION} ({NET}), '
            f'on {threads} threads beside the other two arms (layout A), {len(seg_info)} segment(s): {when}; the '
            f'last worker of segment 1 split into a held-out file and the rest)')
    part_end = (f"stopped at the label-depth experiment's 40-hour limit ({seconds:.0f} s of wall time in all; "
                f'layout A, owner-approved 2026-11-09; docs/research/label-depth/); the arm {run}: {when}, saved '
                f'searches at {nodes} nodes with Hash {hash_mb} MB, on {threads} threads; every game verified '
                f'(tools/datagen/verify_games.py with its manifest)')
    finish(run, out, repo, shards, totals, tool, settings, seconds, part_end,
           f'Fork label-depth arm {run} ({nodes}-node saved searches, S512ppr3 labels)')


def seal_cut(run, d20, target, out, repo):
    d20m = json.loads((d20 / f'{d20.name}.json').read_text())
    out.mkdir(parents=True, exist_ok=False)
    shards, totals = [], {'games': 0, 'positions': 0, 'unsaved': 0, 'kept': 0, 'results': [0, 0, 0]}
    for s in d20m['shards']:
        if s['file'].endswith('-val.vf'):
            continue  # the controls validate on D20's own held-out file
        tfile = target / s['file'].replace(d20.name, target.name)
        want = sum(g[2] for g in games(tfile.read_bytes()))
        data = (d20 / s['file']).read_bytes()
        name = s['file'].replace(d20.name, run)
        entry, end, t = piece(data, name, s['worker'], upto_kept=want)
        (out / name).write_bytes(data[:end])
        shards.append(entry)
        add(totals, t)
        print(f'{name}: {t["kept"]} kept (target {want} from {tfile.name})')
    settings = dict(d20m['settings'], cut_of=d20.name, cut_to=target.name)
    tool = (f'cut of {d20.name}: each training file\'s first games until its kept positions reach '
            f'{target.name}\'s same file (the label-depth volume control); labelled by Fork {VERSION} ({NET})')
    part_end = (f'not a part: the label-depth volume control {run}, {d20.name}\'s first games per training file '
                f'cut to {target.name}\'s kept counts (design section 1.2; for interpretation only); every game '
                f'verified (tools/datagen/verify_games.py with its manifest)')
    finish(run, out, repo, shards, totals, tool, settings, None, part_end,
           f'Fork label-depth volume control {run} (D20 cut to {target.name}\'s kept count)')


def main(a):
    if a[0] == 'arm':
        run, out, repo = a[1], Path(a[2]), Path(a[3])
        nodes = hash_mb = None
        segments, i = [], 4
        while i < len(a):
            if a[i] == '--nodes':
                nodes, i = int(a[i + 1]), i + 2
            elif a[i] == '--hash-mb':
                hash_mb, i = int(a[i + 1]), i + 2
            elif a[i] == '--segment':
                segments.append((Path(a[i + 1]), a[i + 2], int(a[i + 3]), float(a[i + 4]), float(a[i + 5])))
                i += 6
            else:
                sys.exit(f'unknown argument {a[i]}')
        if nodes is None or hash_mb is None or not segments:
            sys.exit(__doc__)
        seal_arm(run, out, repo, nodes, hash_mb, segments)
    elif a[0] == 'cut':
        seal_cut(a[1], Path(a[2]), Path(a[3]), Path(a[4]), Path(a[5]))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
