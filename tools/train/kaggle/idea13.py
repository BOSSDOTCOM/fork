# SPDX-License-Identifier: GPL-3.0-or-later

"""The idea-13 training runs on Kaggle (ideas.md idea 13; DESIGN.md decisions
log, 2026-10-30), pushed with `kaggle kernels push` (GPU T4 x2, internet on,
both arms' shard datasets attached). As bakeoff.py: it builds tools/train at
COMMIT, checks every mounted shard against its arm's sealed manifest, then
trains B0's shape on each arm with seeds 1 and 2, two runs at a time, one per
GPU, all with the bake-off's settings (the same positions seen by every run)
and the best checkpoint on the arm's own held-out *-val.vf shard. Each kept
net is then scored on both arms' held-out sets (the trainer's validation
loss for initial weights, with no training step), so a net is compared on
its own arm's positions and on the other's. For each run it writes
/kaggle/working/result/b0-<arm>-s<seed>/ with the kept checkpoint's
quantised.bin and float weights.bin, the trainer's evaluation of the parity
positions (parity-trainer.txt), the validation curve and a run record
(run.json, with the cross-scores); the summary is result/idea13.json.

Arm A is run g2 (normal settings), arm B is g2bc (the split search, cut to
arm A's 21,738 s).
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import time

COMMIT = 'phase-4'          # replaced by the pushed commit's hash before the push
ARMS = {'a': 'g2', 'b': 'g2bc'}   # arm: sealed run (its shards are <run>-w*.vf)
RUNS = [(arm, seed) for arm in ARMS for seed in (1, 2)]
SCALE = 90                  # S fitted on arm A (fit_scale.py, 2 M positions; arm B fits 94), for both arms
RESULT_WEIGHT = 0.5         # as the bake-off (bakeoff.py)
BATCH = 16384
BATCHES = 305               # per superbatch: 5 M positions
SUPERBATCHES = 80           # 400 M positions seen by every run
LR = 0.001
LR_STEP = 40                # tenfold drop every LR_STEP superbatches
VAL_POSITIONS = 20000
DATA = '/kaggle/input'
WORK = '/kaggle/working/i13'
RESULT = '/kaggle/working/result'


def sh(cmd, env=None, timeout=12 * 3600):
    t = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr), round(time.time() - t, 1)


os.makedirs(WORK, exist_ok=True)
os.makedirs(RESULT, exist_ok=True)
home = os.path.expanduser('~')
env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
       'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
settings = {'commit': COMMIT, 'arms': ARMS, 'scale': SCALE, 'result_weight': RESULT_WEIGHT, 'batch': BATCH,
            'batches': BATCHES, 'superbatches': SUPERBATCHES, 'lr': LR, 'lr_step': LR_STEP,
            'val_positions': VAL_POSITIONS, 'keep': 'best'}
summary = {'settings': settings, 'runs': {}}
rc, out, secs = sh('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal')
summary['rustup'] = rc
repo = f'{WORK}/fork'
rc, out, secs = sh(f'cd {WORK} && rm -rf fork && git clone -q https://github.com/BOSSDOTCOM/fork && cd fork && '
                   f'git checkout -q {COMMIT} && git log --oneline -1')
summary['head'] = out.strip()[-120:]
rc, out, secs = sh(f'cd {repo}/tools/train && cargo build --release --locked --features cuda', env=env)
summary['build'] = {'rc': rc, 'seconds': secs, 'tail': out[-400:] if rc else ''}
train = f'{repo}/tools/train/target/release/fork-train'
ok = rc == 0 and SCALE > 0
shards, val = {}, {}
summary['hash_check'] = {}
for arm, run in ARMS.items():
    found = sorted(glob.glob(f'{DATA}/**/{run}-w*.vf', recursive=True))
    shards[arm] = [p for p in found if not p.endswith('-val.vf')]
    val[arm] = [p for p in found if p.endswith('-val.vf')]
    # The storage rule (DESIGN.md §5.3, deliverable 3): every mounted shard
    # must match the sealed manifest's SHA-256 before it is used.
    sealed = {s['file']: s['sha256'] for b in json.load(open(f'{repo}/data/manifests/{run}.json'))['batches'] for s in b}
    mismatch = [os.path.basename(p) for p in found
                if sealed.get(os.path.basename(p)) != hashlib.sha256(open(p, 'rb').read()).hexdigest()]
    summary['hash_check'][arm] = {'shards': len(found), 'sealed': len(sealed), 'mismatches': mismatch}
    ok = ok and not mismatch and len(found) == len(sealed) and shards[arm] and len(val[arm]) == 1


def start(arm, seed, device):
    name = f'b0-{arm}-s{seed}'
    out_dir = f'{WORK}/run-{name}'
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    cmd = (f'{train} train --arch b0 --data {" ".join(shards[arm])} --val {val[arm][0]} '
           f'--val-positions {VAL_POSITIONS} --patience {SUPERBATCHES + 1} --scale {SCALE} '
           f'--result-weight {RESULT_WEIGHT} --batch {BATCH} --batches {BATCHES} --superbatches {SUPERBATCHES} '
           f'--lr {LR} --lr-step {LR_STEP} --seed {seed} --device {device} --id {name} --threads 2 '
           f'--out {out_dir} > {out_dir}/train.log 2>&1')
    return name, out_dir, time.time(), subprocess.Popen(cmd, shell=True, env={**os.environ, **env})


def held_out_loss(weights, arm):
    """The trainer's validation loss of a float weights file on ARM's held-out
    shard: a warm start with no superbatch writes only superbatch 0's loss."""
    out_dir = f'{WORK}/score'
    shutil.rmtree(out_dir, ignore_errors=True)
    rc, out, _ = sh(f'{train} train --arch b0 --data {val[arm][0]} --val {val[arm][0]} '
                    f'--val-positions {VAL_POSITIONS} --scale {SCALE} --result-weight {RESULT_WEIGHT} '
                    f'--init-weights {weights} --superbatches 0 --out {out_dir}', env=env)
    try:
        return float(open(f'{out_dir}/val.txt').read().split()[1])
    except (OSError, IndexError, ValueError):
        return {'rc': rc, 'tail': out[-300:]}


def finish(arm, seed, name, out_dir, began, proc):
    rc = proc.wait()
    record = {'arm': arm, 'run': ARMS[arm], 'seed': seed, 'rc': rc, 'seconds': round(time.time() - began, 1),
              **settings}
    curve = []
    if os.path.exists(f'{out_dir}/val.txt'):
        curve = [(int(a), float(b)) for a, b in (l.split() for l in open(f'{out_dir}/val.txt'))]
    record['val_curve'] = curve
    record['positions_per_second'] = round(BATCH * BATCHES * len(curve) / record['seconds']) if curve else None
    dest = f'{RESULT}/{name}'
    os.makedirs(dest, exist_ok=True)
    if curve:
        sb = min(curve, key=lambda c: c[1])[0]
        record['kept_superbatch'] = sb
        ck = f'{out_dir}/{name}-{sb}'
        shutil.copy(f'{ck}/quantised.bin', f'{dest}/quantised.bin')
        shutil.copy(f'{ck}/optimiser_state/weights.bin', f'{dest}/weights.bin')
        erc, eout, _ = sh(f'{train} eval --arch b0 --weights {dest}/weights.bin '
                          f'--epd {repo}/tests/nnue/parity.epd --out {dest}/parity-trainer.txt', env=env)
        record['eval'] = {'rc': erc, 'tail': eout[-300:]}
        shutil.copy(f'{out_dir}/val.txt', f'{dest}/val.txt')
    shutil.copy(f'{out_dir}/train.log', f'{dest}/train.log')
    json.dump(record, open(f'{dest}/run.json', 'w'), indent=1)
    shutil.rmtree(out_dir, ignore_errors=True)
    return record


if ok:
    pending = list(RUNS)
    while pending:
        batch = [pending.pop(0) for _ in range(min(2, len(pending)))]
        live = [(arm, seed, *start(arm, seed, device)) for device, (arm, seed) in enumerate(batch)]
        for arm, seed, name, out_dir, began, proc in live:
            summary['runs'][name] = finish(arm, seed, name, out_dir, began, proc)
            json.dump(summary, open(f'{RESULT}/idea13.json', 'w'), indent=1)
    # Cross-scoring, after training (one GPU): every kept net on both held-out sets.
    for name, record in summary['runs'].items():
        weights = f'{RESULT}/{name}/weights.bin'
        if os.path.exists(weights):
            record['held_out_loss'] = {arm: held_out_loss(weights, arm) for arm in ARMS}
            # The scoring path's check: on its own arm a net must reproduce
            # the loss its kept checkpoint had during training.
            own = record['held_out_loss'][record['arm']]
            if isinstance(own, float) and record['val_curve']:
                record['own_score_difference'] = own - min(c[1] for c in record['val_curve'])
            json.dump(record, open(f'{RESULT}/{name}/run.json', 'w'), indent=1)
shutil.rmtree(repo, ignore_errors=True)
json.dump(summary, open(f'{RESULT}/idea13.json', 'w'), indent=1)
print(json.dumps(summary, indent=1))
