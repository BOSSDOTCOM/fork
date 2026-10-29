# SPDX-License-Identifier: GPL-3.0-or-later

"""B0's training run on Kaggle (DESIGN.md §5.3, deliverables 4 and 7), pushed
with `kaggle kernels push` (GPU T4 x2, internet on, the shard dataset
attached). It builds tools/train at COMMIT, trains on every attached shard
except the held-out *-val.vf, validates after each superbatch, stops early
once validation stops improving (or at MAX_SUPERBATCHES, inside Kaggle's
12-hour limit), then evaluates the parity positions with the trainer's own
model at the best checkpoint (the parity test's T) and copies that
checkpoint's quantised.bin and float weights to /kaggle/working/result/
with a summary (result/train.json).

The settings below are this run's; the run record (train.json) repeats them.
"""
import glob
import json
import os
import shutil
import subprocess
import time

COMMIT = 'phase-4'
SCALE = 134                 # S, fitted on this data's nine training shards (fit_scale.py, 600,000 positions)
RESULT_WEIGHT = 0.5         # bullet's weight on the game result: 1 - lambda, lambda = 0.5 (§5.3)
BATCH = 16384
BATCHES = 305               # 5 M positions per superbatch: validation about every 0.85 epoch of g0s1
MAX_SUPERBATCHES = 120
PATIENCE = 8
LR = 0.001                  # bullet's example value (KB bullet-internals.md §5.3)
LR_STEP = 40                # tenfold drop every 40 superbatches
VAL_POSITIONS = 20000
MANIFEST = 'data/manifests/g0s1.json'  # the sealed shards' SHA-256s, checked before training
DATA = '/kaggle/input'
WORK = '/kaggle/working/b0'
RESULT = '/kaggle/working/result'


def sh(cmd, env=None, timeout=12 * 3600):
    t = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr), round(time.time() - t, 1)


assert SCALE > 0, 'set SCALE'
os.makedirs(WORK, exist_ok=True)
os.makedirs(RESULT, exist_ok=True)
home = os.path.expanduser('~')
env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
       'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
record = {'commit': COMMIT, 'scale': SCALE, 'result_weight': RESULT_WEIGHT, 'batch': BATCH, 'batches': BATCHES,
          'max_superbatches': MAX_SUPERBATCHES, 'patience': PATIENCE, 'lr': LR, 'lr_step': LR_STEP,
          'val_positions': VAL_POSITIONS}
rc, out, secs = sh('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal')
record['rustup'] = rc
rc, out, secs = sh(f'cd {WORK} && rm -rf fork && git clone -q https://github.com/BOSSDOTCOM/fork && cd fork && '
                   f'git checkout -q {COMMIT} && git log --oneline -1')
record['head'] = out.strip()[-120:]
rc, out, secs = sh(f'cd {WORK}/fork/tools/train && cargo build --release --locked --features cuda', env=env)
record['build'] = {'rc': rc, 'seconds': secs}
train = f'{WORK}/fork/tools/train/target/release/fork-train'
found = sorted(glob.glob(f'{DATA}/**/*.vf', recursive=True))
shards = [p for p in found if not p.endswith('-val.vf')]
val = [p for p in found if p.endswith('-val.vf')]
record['shards'] = [os.path.basename(p) for p in shards]
record['val'] = [os.path.basename(p) for p in val]
# The storage rule (DESIGN.md §5.3, deliverable 3): every mounted shard must
# match the sealed manifest's SHA-256 before it is used.
import hashlib  # noqa: E402
sealed = {s['file']: s['sha256'] for b in json.load(open(f'{WORK}/fork/{MANIFEST}'))['batches'] for s in b}
mismatch = []
for p in found:
    h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    if sealed.get(os.path.basename(p)) != h:
        mismatch.append(os.path.basename(p))
record['hash_check'] = {'shards': len(found), 'sealed': len(sealed), 'mismatches': mismatch}
if mismatch or len(found) != len(sealed):
    rc = 1
if rc == 0 and shards and val:
    cmd = (f'{train} train --data {" ".join(shards)} --val {val[0]} --val-positions {VAL_POSITIONS} '
           f'--patience {PATIENCE} --scale {SCALE} --result-weight {RESULT_WEIGHT} --batch {BATCH} '
           f'--batches {BATCHES} --superbatches {MAX_SUPERBATCHES} --lr {LR} --lr-step {LR_STEP} '
           f'--threads 3 --out {WORK}/run > {RESULT}/train.log 2>&1')
    rc, _, secs = sh(cmd, env=env, timeout=11 * 3600)
    record['train'] = {'rc': rc, 'seconds': secs}
    curve = []
    if os.path.exists(f'{WORK}/run/val.txt'):
        curve = [(int(a), float(b)) for a, b in (l.split() for l in open(f'{WORK}/run/val.txt'))]
    record['val_curve'] = curve
    if os.path.exists(f'{WORK}/run/stopped-early.txt'):
        record['stopped_early'] = open(f'{WORK}/run/stopped-early.txt').read().strip()
    if curve:
        best = min(curve, key=lambda c: c[1])[0]
        record['best_superbatch'] = best
        ck = f'{WORK}/run/b0-{best}'
        shutil.copy(f'{ck}/quantised.bin', f'{RESULT}/quantised.bin')
        shutil.copy(f'{ck}/optimiser_state/weights.bin', f'{RESULT}/weights.bin')
        rc, out, secs = sh(f'{train} eval --checkpoint {ck} --epd {WORK}/fork/tests/nnue/parity.epd '
                           f'--out {RESULT}/parity-trainer.txt', env=env)
        record['eval'] = {'rc': rc, 'tail': out[-300:]}
    # Keep the output small: only the result folder and the last checkpoint.
    keep = sorted(glob.glob(f'{WORK}/run/b0-*'), key=lambda p: int(p.rsplit('-', 1)[1]))[-1:]
    for p in glob.glob(f'{WORK}/run/b0-*'):
        if p not in keep:
            shutil.rmtree(p, ignore_errors=True)
shutil.rmtree(f'{WORK}/fork', ignore_errors=True)
with open(f'{RESULT}/train.json', 'w') as f:
    json.dump(record, f, indent=1)
print(json.dumps(record, indent=1))
