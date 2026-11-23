# SPDX-License-Identifier: GPL-3.0-or-later
"""The positional-advantage slice (ideas.md 66; docs/research/defense-slices/pilot.md section 5) on the Google
Cloud worker, resumable at game boundaries (docs/gcp-worker.md). The settings are slice.sh's (the PC's version):
80,000 nodes, hash 4 MB, decided-cp 31000, max plies 500, no random plies, adjudication 1500 cp x 16 plies, the
Syzygy 3-4-5 tables; the labeller is whatever pinned build it is given (r8btd90 since 2026-11-10).

The run is a sequence of segments OUT/RUN/seg-KK (fork_datagen run RUN-sKK, seed SEED + K):
- a segment that finished has fork_datagen's own manifest RUN-sKK.json;
- a segment the machine stopped under (a spot preemption) is salvaged at the next start: its shards move to
  seg-KK/raw/, each is cut after its last complete game (the game in progress at the stop is dropped, as the
  Control Center's seal does: seal_part.complete_games), and RUN-sKK.json is written in the same form with
  "interrupted": true. At most one game per worker is lost;
- the next segment plays only the starts no complete game has used yet (defense_starts.py played over every
  segment's shards, which also fails if any start was played twice), in the list's order, for the positions
  still missing. Segment 0 is exactly the uninterrupted run (seed SEED, every start).
When the target is reached: bench again, verify_games.py on each segment with its manifest (--table-pieces 5),
defense_starts.py played over all segments (PLAYED.tsv), then OUT/RUN/done.json (positions, games, segments,
every shard's SHA-256, the builds' and tools' SHA-256s, the checks' output). The PC pulls the folder and checks
it again before anything uses it (tools/gcp/gcp.py finish).

    python3 -I slice_vm.py RUN --openings EPD --starts TSV --positions N --threads T --build DIR
        --pin-fork SHA256 --pin-datagen SHA256 --bench NODES:SIGNATURE --slice-tools DIR
        --pin-defense-starts SHA256 --pin-verify SHA256 [--seed 20261110] [--out /opt/fork/out]
        [--tables /opt/fork/syzygy] [--python /opt/fork/venv/bin/python]
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'control_center'))
from seal_part import complete_games  # noqa: E402

SHARD = re.compile(r'^(?P<run>.+)-w(?P<worker>\d{2})-(?P<index>\d{4})\.vf$')


def say(msg):
    t = time.strftime('%Y-%m-%d %I:%M:%S %p EST', time.gmtime(time.time() - 5 * 3600))
    print(f'{t} slice_vm: {msg}', flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def check_pin(path, want):
    got = sha256(path)
    if got != want:
        raise SystemExit(f'STOP: {path} has SHA-256 {got}, the pin is {want}')


def bench(fork, want, when):
    out = subprocess.run([fork, 'bench'], capture_output=True, text=True).stdout + ''
    got = ':'.join(re.findall(r'^(?:nodes|signature) (\S+)', out, re.M))
    if got != want:
        raise SystemExit(f'STOP: bench {got or "(none)"} ({when}), want {want}')
    say(f'bench ok ({when}): {got}')


def write_json(path, data):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(data, indent=1) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def salvage(seg, run):
    """Cuts an interrupted segment's shards after their last complete game; writes its manifest. Re-runnable:
    the originals stay in raw/ and the cut copies are always rewritten from them."""
    raw = seg / 'raw'
    raw.mkdir(exist_ok=True)
    for f in sorted(seg.iterdir()):
        if f.is_file() and SHARD.match(f.name):
            os.replace(f, raw / f.name)
    shards, games, positions, dropped = [], 0, 0, 0
    for f in sorted(raw.iterdir()):
        m = SHARD.match(f.name)
        if not m or m['run'] != run:
            continue
        data = f.read_bytes()
        end, g, p, u, _ = complete_games(data)
        if u:
            raise SystemExit(f'{f}: unsaved records in a slice shard')
        (seg / f.name).write_bytes(data[:end])
        if g:
            shards.append({'file': f.name, 'worker': int(m['worker']), 'games': g, 'positions': p, 'bytes': end})
        else:
            (seg / f.name).unlink()
        games, positions, dropped = games + g, positions + p, dropped + len(data) - end
    settings = json.loads((seg / 'settings.json').read_text(encoding='utf-8'))
    man = {'run': run, 'interrupted': True, 'settings': settings, 'games': games, 'positions': positions,
           'positions_unsaved': 0, 'dropped_bytes': dropped, 'shards': shards}
    write_json(seg / f'{run}.json', man)
    say(f'{run} salvaged: {games} complete games, {positions} positions, {dropped} bytes of unfinished games dropped')
    return man


def played_ids(a, segs):
    """The start ids every complete game of these segments used (defense_starts.py played); fails on a start
    played twice or a game from a start not in the list."""
    shards = [str(s / f['file']) for s, m in segs for f in m['shards']]
    if not shards:
        return set()
    out = Path(a.out) / a.run / 'played.tsv'
    r = subprocess.run([a.python, '-I', str(Path(a.slice_tools) / 'defense_starts.py'), 'played', a.starts, *shards,
                        '--out', str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'STOP: defense_starts.py played failed: {(r.stdout + r.stderr).strip()[-500:]}')
    with open(out, encoding='utf-8') as f:
        f.readline()
        return {line.split('\t', 1)[0] for line in f if line.strip()}


def remaining_openings(a, used, path):
    """The list's starts (the openings file's FENs, in order) that no complete game has used."""
    by_fen = {}
    with open(a.starts, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        i_id, i_fen = head.index('id'), head.index('fen')
        for line in f:
            c = line.rstrip('\n').split('\t')
            by_fen[c[i_fen]] = c[i_id]
    n = 0
    with open(a.openings, encoding='utf-8') as f, open(path, 'w', encoding='utf-8', newline='\n') as o:
        o.write(f'# starts of {Path(a.openings).name} not yet played ({len(used)} played)\n')
        for line in f:
            fen = line.rstrip('\n')
            if not fen or fen.startswith('#'):
                continue
            if fen not in by_fen:
                raise SystemExit(f'STOP: an opening not in the starts list: {fen}')
            if by_fen[fen] not in used:
                o.write(fen + '\n')
                n += 1
    return n


def datagen_argv(a, seg, run, positions, openings, seed):
    return [str(Path(a.build) / 'fork_datagen'), '--openings', str(openings), '--out', str(seg), '--run', run,
            '--positions', str(positions), '--nodes', '80000', '--threads', str(a.threads), '--seed', str(seed),
            '--hash-mb', '4', '--tables', a.tables, '--decided-cp', '31000', '--max-plies', '500',
            '--random-min', '0', '--random-max', '0', '--adjudicate-cp', '1500', '--adjudicate-plies', '16']


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('run')
    for k in ('openings', 'starts', 'build', 'pin_fork', 'pin_datagen', 'bench', 'slice_tools',
              'pin_defense_starts', 'pin_verify'):
        ap.add_argument('--' + k.replace('_', '-'), required=True)
    ap.add_argument('--positions', type=int, required=True)
    ap.add_argument('--threads', type=int, required=True)
    ap.add_argument('--seed', type=int, default=20261110)
    ap.add_argument('--out', default='/opt/fork/out')
    ap.add_argument('--tables', default='/opt/fork/syzygy')
    ap.add_argument('--python', default='/opt/fork/venv/bin/python')
    a = ap.parse_args(argv)
    root = Path(a.out) / a.run
    root.mkdir(parents=True, exist_ok=True)
    done = root / 'done.json'
    if done.exists():
        say(f'{done} exists already')
        return 0
    fork, datagen = Path(a.build) / 'fork', Path(a.build) / 'fork_datagen'
    tools = Path(a.slice_tools)
    check_pin(fork, a.pin_fork)
    check_pin(datagen, a.pin_datagen)
    check_pin(tools / 'defense_starts.py', a.pin_defense_starts)
    check_pin(tools / 'verify_games.py', a.pin_verify)
    want = a.bench.replace(' ', '')
    bench(str(fork), want, 'before')

    while True:
        segs, k = [], 0
        while (root / f'seg-{k:02d}').is_dir():
            seg, run = root / f'seg-{k:02d}', f'{a.run}-s{k:02d}'
            man = json.loads((seg / f'{run}.json').read_text(encoding='utf-8')) \
                if (seg / f'{run}.json').exists() else salvage(seg, run)
            segs.append((seg, man))
            k += 1
        have = sum(m['positions'] for _, m in segs)
        if have >= a.positions:
            break
        seg, run = root / f'seg-{k:02d}', f'{a.run}-s{k:02d}'
        seg.mkdir()
        openings = a.openings
        if segs:
            used = played_ids(a, segs)
            openings = seg / 'openings.epd'
            left = remaining_openings(a, used, openings)
            say(f'{len(used)} starts played so far; {left} left for segment {k}')
        settings = {'nodes': 80000, 'threads': a.threads, 'seed': a.seed + k, 'hash_mb': 4, 'tables': a.tables,
                    'decided_cp': 31000, 'max_plies': 500, 'random_min': 0, 'random_max': 0,
                    'adjudicate_cp': 1500, 'adjudicate_plies': 16, 'positions_target': a.positions - have,
                    'openings': str(openings), 'save_percent': 100}
        write_json(seg / 'settings.json', settings)
        argv_dg = datagen_argv(a, seg, run, a.positions - have, openings, a.seed + k)
        say(f'segment {k}: {a.positions - have} positions, seed {a.seed + k}, {a.threads} threads')
        t0 = time.time()
        with open(seg / f'{run}.log', 'wb') as log:
            rc = subprocess.run(argv_dg, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL).returncode
        if rc != 0 or not (seg / f'{run}.json').exists():
            # fork_datagen failed by itself (a stop by signal ends this script too). Salvage at the next start
            # would hide a real failure, so fail loudly instead.
            raise SystemExit(f'STOP: fork_datagen exited {rc} in segment {k} after {time.time() - t0:.0f} s; '
                             f'see {seg / (run + ".log")}')
        say(f'segment {k} finished in {time.time() - t0:.0f} s')

    bench(str(fork), want, 'after')
    verify = []
    for i, (seg, m) in enumerate(segs):
        shards = [str(seg / f['file']) for f in m['shards']]
        r = subprocess.run([a.python, '-I', str(tools / 'verify_games.py'), *shards, '--manifest',
                            str(seg / f'{a.run}-s{i:02d}.json'), '--table-pieces', '5'],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f'STOP: verify_games.py failed on {seg.name}: {(r.stdout + r.stderr).strip()[-500:]}')
        verify.append(f'{seg.name}: {r.stdout.strip().splitlines()[-1]}')
        say(verify[-1])
    used = played_ids(a, segs)
    say(f'defense_starts.py played: {len(used)} games matched to their starts, none twice')
    data = {
        'run': a.run, 'positions': sum(m['positions'] for _, m in segs), 'games': sum(m['games'] for _, m in segs),
        'segments': [{'dir': s.name, 'run': f'{a.run}-s{i:02d}', 'interrupted': bool(m.get('interrupted')),
                      'games': m['games'], 'positions': m['positions'], 'seed': a.seed + i} for i, (s, m) in
                     enumerate(segs)],
        'finished': time.strftime('%Y-%m-%d %I:%M:%S %p EST', time.gmtime(time.time() - 5 * 3600)),
        'verify': verify, 'played': f'{len(used)} games matched to their starts',
        'builds': {'fork': a.pin_fork, 'fork_datagen': a.pin_datagen, 'bench': want},
        'tools': {'defense_starts.py': a.pin_defense_starts, 'verify_games.py': a.pin_verify},
        'sha256': {f'{s.name}/{f["file"]}': sha256(s / f['file']) for s, m in segs for f in m['shards']},
    }
    write_json(done, data)
    say(f'done file written: {done} ({data["positions"]} positions, {data["games"]} games, {len(segs)} segment(s))')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
