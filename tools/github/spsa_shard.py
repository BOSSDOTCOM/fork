# SPDX-License-Identifier: GPL-3.0-or-later
"""One shard of an SPSA iteration (.github/workflows/spsa.yml; DESIGN.md §5.2, "SPSA on GitHub"): game pairs
of one FORK_TUNE engine against itself, every draw with its own perturbation. Draw j plays K pairs (K =
--draw-pairs, default 1, so every pair has its own draw) of theta + c*signs ("plus") against theta - c*signs
("minus"), the signs and the randomly rounded values coming from the draw's seed (tools/github/spsa.py:
pair_seed, perturbed_values), so the driver can check every record against the seed.

    spsa_shard.py --engine EXE --fastchess BIN --book EPD --shard I --shards N --games G --label L --commit C
        --stage D --params P --openings LINE --draw-pairs K --tc TC --hash MB --out DIR
        [--syzygy DIR] [--concurrency W] [--meta KEY=VALUE ...]

Conditions as an SPRT shard (tools/cloud/run_shard.sh): one thread, Hash, the same adjudication, each
opening played with both colours, Syzygy 3-4-5 for both sides with --syzygy. Openings: the shard's pairs are
book lines LINE + I*P to LINE + (I+1)*P - 1 (P pairs per shard: G/2 shared out, rounded up to whole draws),
draw j taking K consecutive lines. Each draw is one fastchess call in its own folder (its config.json
autosave), W at a time (default nproc - 1, as run_shard.sh).

OUT/result.json is rewritten atomically after each draw, so a stopped job keeps its finished draws: status
(running, done, short, failed, interrupted, with run_shard.sh's meanings), records (index, line, signs,
plus, minus, ptnml scored for plus, time_losses, abnormal), ptnml, sums (sum of (pair score - 1/2) * sign
per parameter) and meta. A draw whose fastchess exits non-zero or reports a fatal error fails the shard;
one that ends normally with fewer pairs makes it short. SIGTERM or SIGINT stops the running calls and
records "interrupted". Exit status 1 for short and failed, 2 for bad arguments, else 0.
"""
import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'cloud'))

import spsa  # noqa: E402
import sprt_merge  # noqa: E402


def command(path):
    """A script with a shebang runs through bash on Windows (the tests' fake fastchess); anything else as is."""
    if os.name == 'nt':
        with open(path, 'rb') as f:
            if f.read(2) == b'#!':
                return ['bash', path]
    return [path]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    for name in ('engine', 'fastchess', 'book', 'label', 'commit', 'params', 'tc', 'out'):
        ap.add_argument(f'--{name}', required=True)
    for name in ('shard', 'shards', 'games', 'stage', 'openings', 'hash'):
        ap.add_argument(f'--{name}', type=int, required=True)
    ap.add_argument('--draw-pairs', type=int, default=1)
    ap.add_argument('--syzygy', default='')
    ap.add_argument('--concurrency', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--meta', action='append', default=[])
    a = ap.parse_args(argv)
    for name in ('engine', 'fastchess', 'book'):
        if not Path(getattr(a, name)).exists():
            print(f'spsa_shard: --{name} {getattr(a, name)} does not exist', file=sys.stderr)
            return 2
    try:
        tuned, fixed = spsa.parse_params(a.params)
    except spsa.Refused as e:
        print(f'spsa_shard: {e}', file=sys.stderr)
        return 2
    if not (0 <= a.shard < a.shards and a.games > 0 and a.draw_pairs > 0 and a.concurrency > 0):
        print('spsa_shard: bad shard, games, draw pairs or concurrency', file=sys.stderr)
        return 2
    tables, each_tb = 'off', []
    if a.syzygy:
        tb = Path(a.syzygy).resolve()
        w, z = len(list(tb.glob('*.rtbw'))), len(list(tb.glob('*.rtbz')))
        if (w, z) != (145, 145):
            print(f'spsa_shard: --syzygy {a.syzygy} holds {w} .rtbw + {z} .rtbz, not the 3-4-5 set (145 + 145)',
                  file=sys.stderr)
            return 2
        tables, each_tb = '3-4-5', [f'option.SyzygyPath={tb}']
    engine, book = str(Path(a.engine).resolve()), str(Path(a.book).resolve())
    k = a.draw_pairs
    per = spsa.shard_plan(a.games, a.shards, k)
    start = a.openings + a.shard * per
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    seed_match = re.search(r'\.shuffled-(\d+)\.epd$', Path(book).name)
    meta = {'label': a.label, 'commit': a.commit, 'stage': str(a.stage), 'params': a.params, 'shard': str(a.shard),
            'shards': str(a.shards), 'opening_start': str(start), 'opening_end': str(start + per - 1),
            'draw_pairs': str(k), 'tc': a.tc, 'hash': str(a.hash), 'tables': tables, 'book': Path(book).name,
            'book_seed': seed_match.group(1) if seed_match else 'none',
            'book_sha': hashlib.sha256(Path(book).read_bytes()).hexdigest(),
            'engine_build': hashlib.sha256(Path(engine).read_bytes()).hexdigest()[:16],
            'concurrency': str(a.concurrency)}
    meta.update(dict(kv.split('=', 1) for kv in a.meta))
    names = [n for n, _, _ in tuned]
    fixed_opts = [f'option.{n}={v}' for n, v in fixed.items()]

    lock = threading.Lock()
    records, running, exits = {}, {}, []
    state = {'stopped': False, 'bad': None}

    def write(status):
        recs = [records[j] for j in sorted(records)]
        ptnml = [sum(r['ptnml'][i] for r in recs) for i in range(5)]
        sums = {n: sum(spsa.pair_scores(r['ptnml'])[1] * (1 if r['signs'][i] == '+' else -1) for r in recs)
                for i, n in enumerate(names)}
        result = {'status': status, 'records': recs, 'ptnml': ptnml, 'sums': sums,
                  'meta': dict(meta, fastchess_exit=str(max(exits, default=0)))}
        spsa.write_json(out / 'result.json', result)

    def draw(j):
        if state['stopped'] or state['bad']:
            return
        seed = spsa.pair_seed(a.label, a.commit, a.stage, a.shard, j)
        signs, plus, minus = spsa.perturbed_values(seed, tuned)
        line = start + j * k
        work = out / 'work' / str(j)
        work.mkdir(parents=True, exist_ok=True)
        cmd = command(a.fastchess) + [
            '-engine', f'cmd={engine}', 'name=plus', *[f'option.{n}={v}' for n, v in zip(names, plus)], *fixed_opts,
            '-engine', f'cmd={engine}', 'name=minus', *[f'option.{n}={v}' for n, v in zip(names, minus)], *fixed_opts,
            '-each', f'tc={a.tc}', f'option.Hash={a.hash}', 'option.Threads=1', *each_tb,
            '-openings', f'file={book}', 'format=epd', 'order=sequential', f'start={line}',
            '-repeat', '-rounds', str(k), '-concurrency', '1',
            '-resign', 'movecount=5', 'score=1000', 'twosided=true', '-draw', 'movenumber=40', 'movecount=10',
            'score=10', '-recover', '-pgnout', f'file={work / "games.pgn"}']
        with open(work / 'fastchess.log', 'w', encoding='utf-8') as log:
            proc = subprocess.Popen(cmd, cwd=work, stdout=log, stderr=subprocess.STDOUT)
            with lock:
                running[j] = proc
            code = proc.wait()
        with lock:
            running.pop(j, None)
        text = (work / 'fastchess.log').read_text(encoding='utf-8', errors='replace')
        snap = sprt_merge.snapshot(text)
        ptnml = sprt_merge.pairs_from_games(text, test='plus')
        with lock:
            if state['stopped']:
                return
            exits.append(code)
            if code != 0 or re.search(r'^Fatal', text, re.M):
                state['bad'] = state['bad'] or 'failed'
                print(f'spsa_shard: draw {j} (line {line}): fastchess exit {code}', file=sys.stderr)
                print(text[-2000:], file=sys.stderr)
                return
            if sum(ptnml) != k:
                state['bad'] = state['bad'] or 'short'
                print(f'spsa_shard: draw {j} (line {line}): {sum(ptnml)} pairs, not {k}', file=sys.stderr)
                return
            records[j] = {'index': j, 'line': line, 'signs': ''.join('+' if s > 0 else '-' for s in signs),
                          'plus': plus, 'minus': minus, 'ptnml': ptnml, 'time_losses': snap['time_losses'],
                          'abnormal': snap['abnormal']}
            write('running')

    def stop(signum, frame):
        with lock:
            state['stopped'] = True
            for proc in running.values():
                proc.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    write('running')
    with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        list(pool.map(draw, range(per // k)))
    status = 'interrupted' if state['stopped'] else state['bad'] or 'done'
    write(status)
    # One PGN and one log for the artifact, in draw order; the per-draw folders go.
    with open(out / 'games.pgn', 'w', encoding='utf-8') as pgn, open(out / 'fastchess.log', 'w', encoding='utf-8') as log:
        for j in range(per // k):
            work = out / 'work' / str(j)
            for src, dst in ((work / 'games.pgn', pgn), (work / 'fastchess.log', log)):
                if src.exists():
                    dst.write(src.read_text(encoding='utf-8', errors='replace'))
    for j in range(per // k):
        work = out / 'work' / str(j)
        for f in work.glob('*') if work.exists() else []:
            f.unlink()
        if work.exists():
            work.rmdir()
    if (out / 'work').exists():
        (out / 'work').rmdir()
    done = len(records)
    print(f'shard {a.shard} {status}: draws {done} of {per // k}, pairs {done * k}, '
          f'ptnml {[sum(r["ptnml"][i] for r in records.values()) for i in range(5)]}, '
          f'time losses {sum(r["time_losses"] for r in records.values())}, fastchess exit {max(exits, default=0)}')
    return 1 if status in ('short', 'failed') else 0


if __name__ == '__main__':
    sys.exit(main())
