# SPDX-License-Identifier: GPL-3.0-or-later

"""Idea 69's preflight before the cw arm (owner, 2026-11-10; docs/research/class-sampler/design.md sections 12-14), on
Kaggle (GPU T4 x2, device 0 only). A few GPU minutes; its verdict decides whether the cw arm runs.

The same short training run, five times, on one T4, one after the other: architecture s512pp warm from S512ppr3's float
weights, g3j-w00..w04 of fork-g3hij interleaved, seed 1, LR 0.0001, batch 16,384 x 305, 3 superbatches (about
15 M positions), a 4,194,304-position shuffle buffer, 2 loader threads:
- old1, old2: the trainer of retrain 8b's launch commit (OLD, the control's trainer), twice: CUDA's run-to-run
  determinism;
- none: the new trainer (NEW) without --cell-weights (every loss weight 1);
- ones: the new trainer with a table of 112 ones;
- table: the new trainer with the cw arm's table (TABLE, checked against TABLE_SHA256).

Verdict (declared before the run): EQUAL passes if none and ones reproduce old1's superbatch-3 float weights byte for
byte; if old1 and old2 differ (CUDA not deterministic), none and ones must differ from old1 by no more than old2 does
(the largest absolute difference of any weight). SPEED passes if table's trained positions per second (from the
trainer's own progress lines, the first to the last) are at least 99% of the mean of old1 and old2. table must differ
from old1 (the weights act). The cw arm runs only if EQUAL and SPEED pass.

    python3 cw_preflight.py            # on Kaggle
    python cw_preflight.py --plan      # anywhere: the commands, with placeholder paths
"""
import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time

OLD = '320c0bee66da6958fb9507e17f9bdb4fc99178d7'   # retrain 8b's launch commit (its kernel built this trainer)
NEW = 'phase-4'           # replaced by the pushed commit holding the new trainer and the table before the push
TABLE = 'docs/research/class-sampler/weights-r8b-c.txt'
TABLE_SHA256 = '4ac778ac45f59a06f3d605f3b718203f0564a495e04708476eaebedf06781b0a'   # docs/research/class-sampler/weights-r8b-c.txt
ARCH = 's512pp'
SCALE = 92
BATCH = 16384
BATCHES = 305
SUPERBATCHES = 3
BUFFER = 1 << 22
FILES = ['g3j-w00.vf', 'g3j-w01.vf', 'g3j-w02.vf', 'g3j-w03.vf', 'g3j-w04.vf']
INIT = {'weights': 's512ppr3-weights.bin',
        'sha256': '022158587653ba32d5830ce4f6a3b7e1a88283e7cb9e3c507936ad0c8b37ecc3'}
RUNS = ['old1', 'old2', 'none', 'ones', 'table']
SPEED_RATIO = 0.99
DATA = '/kaggle/input'
WORK = '/kaggle/working/preflight'
RESULT = '/kaggle/working/result'
PROGRESS = re.compile(r'superbatch (\d+) batch (\d+) loss')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def sh(cmd, env=None, timeout=3600):
    t = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr), round(time.time() - t, 1)


def ones_table():
    sigs = ['Q-MG', 'Q-EG', 'noQ-MG', 'R+minor-EG', 'R-EG', 'minor-EG', 'pawn-EG']
    parts = ['Q-imbalance', 'R-vs-minors', 'minor-up', 'other-imbalance', 'B-vs-N', 'level', 'pawn+-1', 'pawn+-2+']
    return ''.join(f'{s}|{p} {w} 1\n' for s in sigs for p in parts for w in ('two-wing', 'one-wing'))


def floats(path):
    """bullet's weights.bin records (ASCII name, 0x0A, u64 count, f32s) as {name: tuple of floats}."""
    data = open(path, 'rb').read()
    out, at = {}, 0
    while at < len(data):
        nl = data.index(b'\n', at)
        (n,) = struct.unpack_from('<Q', data, nl + 1)
        out[data[at:nl].decode()] = struct.unpack_from(f'<{n}f', data, nl + 9)
        at = nl + 9 + 4 * n
    return out


def max_diff(a, b):
    fa, fb = floats(a), floats(b)
    if fa.keys() != fb.keys():
        return float('inf')
    return max(max(abs(x - y) for x, y in zip(fa[k], fb[k])) for k in fa)


def rate(lines):
    """Trained positions per second from (seconds, superbatch, batch) progress stamps, the first to the last."""
    if len(lines) < 2:
        return None
    (t0, s0, b0), (t1, s1, b1) = lines[0], lines[-1]
    batches = (s1 - s0) * BATCHES + (b1 - b0)
    return round(batches * BATCH / (t1 - t0)) if t1 > t0 and batches > 0 else None


def command(train, spec, files, init, out, extra=''):
    return (f'{train} train {spec} --data {" ".join(files)} --start 1 --superbatches {SUPERBATCHES} --lr 0.0001 '
            f'--lr-step 180 --seed 1 --patience {SUPERBATCHES + 1} --scale {SCALE} --result-weight 0.5 '
            f'--batch {BATCH} --batches {BATCHES} --buffer {BUFFER} --interleave --threads 2 --init-weights {init} '
            f'--device 0 --id p --out {out} {extra}').strip()


def verdict(rec):
    """The declared rule (module docstring) on the runs' records."""
    w = {r: rec[r].get('weights') for r in RUNS}
    if not all(w.values()):
        return {'equal': False, 'speed': False, 'pass': False, 'why': 'a run produced no superbatch-3 weights'}
    same = {r: rec[r]['sha256'] == rec['old1']['sha256'] for r in RUNS}
    noise = 0.0 if same['old2'] else max_diff(w['old1'], w['old2'])
    diff = {r: 0.0 if same[r] else max_diff(w['old1'], w[r]) for r in ('none', 'ones', 'table')}
    equal = all(same[r] or diff[r] <= noise for r in ('none', 'ones'))  # noise 0: byte for byte
    base = [rec[r].get('positions_per_second') for r in ('old1', 'old2')]
    speed_ok = all(base) and rec['table'].get('positions_per_second') is not None and \
        rec['table']['positions_per_second'] >= SPEED_RATIO * sum(base) / 2
    acts = not same['table']
    return {'deterministic': same['old2'], 'old_noise': noise, 'max_diff_vs_old1': diff,
            'bitwise_equal_to_old1': same, 'equal': equal, 'speed': bool(speed_ok), 'table_acts': acts,
            'speed_ratio_table': (rec['table'].get('positions_per_second') or 0) / (sum(base) / 2) if all(base) else None,
            'pass': equal and bool(speed_ok) and acts}


def session():
    began = time.time()
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(RESULT, exist_ok=True)
    home = os.path.expanduser('~')
    env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
           'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
    summary = {'old': OLD, 'new': NEW, 'table': TABLE, 'runs': {}}

    def save():
        json.dump(summary, open(f'{RESULT}/preflight.json', 'w'), indent=1)

    summary['gpu'] = sh('nvidia-smi -L')[1].strip()
    summary['rustup'] = sh('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal')[0]
    repo = f'{WORK}/fork'
    rc, out, _ = sh(f'cd {WORK} && rm -rf fork && git clone -q https://github.com/BOSSDOTCOM/fork && cd fork && '
                    f'git checkout -q {NEW} && git worktree add -q ../old {OLD} && git log --oneline -1 && '
                    f'git -C ../old log --oneline -1')
    summary['heads'] = out.strip()[-240:]
    trains = {}
    for name, src in (('old', f'{WORK}/old'), ('new', repo)):
        rc, out, secs = sh(f'cd {src}/tools/train && cargo build --release --locked --features cuda', env=env)
        summary[f'build_{name}'] = {'rc': rc, 'seconds': secs, 'tail': out[-400:] if rc else ''}
        trains[name] = f'{src}/tools/train/target/release/fork-train'
    by_name = {os.path.basename(p): p for p in glob.glob(f'{DATA}/**/*.vf', recursive=True)}
    init = glob.glob(f'{DATA}/**/{INIT["weights"]}', recursive=True)
    table = f'{repo}/{TABLE}'
    checks = {'files': all(f in by_name for f in FILES),
              'init': len(init) == 1 and sha256(init[0]) == INIT['sha256'],
              'table': os.path.exists(table) and sha256(table) == TABLE_SHA256,
              'builds': all(summary[f'build_{n}']['rc'] == 0 for n in ('old', 'new'))}
    summary['checks'] = checks
    save()
    if not all(checks.values()):
        summary['verdict'] = {'pass': False, 'why': 'a check failed before the runs'}
        save()
        return
    open(f'{WORK}/ones.txt', 'w').write(ones_table())
    desc = json.load(open(f'{repo}/tools/nnue/{ARCH}.json'))
    spec = f'--arch {ARCH} --buckets ' + ','.join(map(str, desc['table']))
    files = [by_name[f] for f in FILES]
    extra = {'old1': '', 'old2': '', 'none': '', 'ones': f'--cell-weights {WORK}/ones.txt',
             'table': f'--cell-weights {table}'}
    for run in RUNS:
        out_dir = f'{WORK}/run-{run}'
        shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir)
        cmd = command(trains['old' if run.startswith('old') else 'new'], spec, files, init[0], out_dir, extra[run])
        t0 = time.time()
        stamps, tail = [], []
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                env={**os.environ, **env})
        for line in proc.stdout:
            m = PROGRESS.search(line)
            if m:
                stamps.append((time.time() - t0, int(m.group(1)), int(m.group(2))))
            tail = (tail + [line])[-20:]
        proc.wait()
        ck = f'{out_dir}/p-{SUPERBATCHES}/optimiser_state/weights.bin'
        rec = {'rc': proc.returncode, 'seconds': round(time.time() - t0, 1), 'progress_lines': len(stamps),
               'positions_per_second': rate(stamps), 'command': cmd.replace(WORK, '<work>').replace(DATA, '<data>')}
        if os.path.exists(ck):
            keep = f'{RESULT}/{run}.weights.bin'
            shutil.copy(ck, keep)
            rec['weights'], rec['sha256'] = keep, sha256(keep)
        else:
            rec['tail'] = ''.join(tail)[-1500:]
        summary['runs'][run] = rec
        shutil.rmtree(out_dir, ignore_errors=True)
        save()
    summary['verdict'] = verdict(summary['runs'])
    summary['session_seconds'] = round(time.time() - began, 1)
    shutil.rmtree(WORK, ignore_errors=True)
    save()
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    if '--plan' in sys.argv:
        for run in RUNS:
            extra = {'ones': '--cell-weights <ones.txt>', 'table': f'--cell-weights <{TABLE}>'}.get(run, '')
            train = '<old fork-train>' if run.startswith('old') else '<new fork-train>'
            print(run + ':', command(train, '--arch s512pp --buckets <s512pp.json table>', [f'<{f}>' for f in FILES],
                                      f'<{INIT["weights"]}>', f'<run-{run}>', extra))
    elif not os.path.isdir(DATA):
        sys.exit(f'{DATA} not found: this script runs inside the Kaggle session (--plan)')
    else:
        session()
