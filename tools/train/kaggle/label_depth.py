# SPDX-License-Identifier: GPL-3.0-or-later

"""The label-depth experiment's small nets on Kaggle (docs/research/label-depth/; design: section 1.4 of
docs/research/labels-teacher/report.md, approved by the owner on 2026-11-09), pushed with `kaggle kernels push`
(GPU T4 x2, internet on, the five sealed datasets attached). As idea13.py: builds tools/train at COMMIT, checks every
mounted shard against its sealed manifest (data/manifests/<run>.json at COMMIT), then trains B0's shape on each arm
with seeds 1 and 2, two runs at a time, one per GPU, all with idea 13's settings: from scratch, 80 superbatches of
5 M positions (400 M seen by every run), LR 0.001 dropped tenfold every 40, result weight 0.5, one S for every arm
(fitted on D20), and the checkpoint with the lowest validation loss on the arm's own held-out file (the volume
controls validate on D20's). A kept checkpoint before superbatch 40 is flagged as volume-starved (design section
1.4). Each kept net is also scored on D20's held-out file (for interpretation only).

For each run: /kaggle/working/result/ld-<arm>-s<seed>/ with quantised.bin, weights.bin, parity-trainer.txt,
val.txt, train.log and run.json; the summary is result/label_depth.json.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import time

COMMIT = 'research/label-depth'   # replaced by the pushed commit's hash before the push
ARMS = {'d20': 'ld-d20', 'd50': 'ld-d50', 'd100': 'ld-d100', 'c50': 'ld-d20c50', 'c100': 'ld-d20c100'}
VAL_RUN = {'d20': 'ld-d20', 'd50': 'ld-d50', 'd100': 'ld-d100', 'c50': 'ld-d20', 'c100': 'ld-d20'}
RUNS = [(arm, seed) for arm in ARMS for seed in (1, 2)]
SCALE = 81                  # fit_scale.py on ld-d20's training files, 2 M positions (2026-11-12; 0 refuses to train)
RESULT_WEIGHT = 0.5
BATCH = 16384
BATCHES = 305               # per superbatch: 5 M positions
SUPERBATCHES = 80           # 400 M positions seen by every run
LR = 0.001
LR_STEP = 40
VAL_POSITIONS = 20000
STARVED_BEFORE = 40
DATA = '/kaggle/input'
WORK = '/kaggle/working/ld'
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
settings = {'commit': COMMIT, 'arms': ARMS, 'val_run': VAL_RUN, 'scale': SCALE, 'result_weight': RESULT_WEIGHT,
            'batch': BATCH, 'batches': BATCHES, 'superbatches': SUPERBATCHES, 'lr': LR, 'lr_step': LR_STEP,
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
files = {}
summary['hash_check'] = {}
for run in sorted(set(ARMS.values())):
    # Both segments' files: RUN-wNN.vf (segment 1, its held-out RUN-wNN-val.vf) and RUN-s2-wNN.vf (segment 2).
    found = sorted(glob.glob(f'{DATA}/**/{run}-*.vf', recursive=True))
    # The storage rule (DESIGN.md §5.3, deliverable 3): every mounted shard must match its sealed SHA-256.
    sealed = {s['file']: s['sha256'] for b in json.load(open(f'{repo}/data/manifests/{run}.json'))['batches']
              for s in b}
    mismatch = [os.path.basename(p) for p in found
                if sealed.get(os.path.basename(p)) != hashlib.sha256(open(p, 'rb').read()).hexdigest()]
    summary['hash_check'][run] = {'shards': len(found), 'sealed': len(sealed), 'mismatches': mismatch}
    ok = ok and not mismatch and len(found) == len(sealed)
    files[run] = found
shards, val = {}, {}
for arm, run in ARMS.items():
    shards[arm] = [p for p in files[run] if not p.endswith('-val.vf')]
    v = [p for p in files[VAL_RUN[arm]] if p.endswith('-val.vf')]
    val[arm] = v[0] if len(v) == 1 else None
    ok = ok and bool(shards[arm]) and val[arm] is not None
summary['ok_to_train'] = ok


def start(arm, seed, device):
    name = f'ld-{arm}-s{seed}'
    out_dir = f'{WORK}/run-{name}'
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    cmd = (f'{train} train --arch b0 --data {" ".join(shards[arm])} --val {val[arm]} '
           f'--val-positions {VAL_POSITIONS} --patience {SUPERBATCHES + 1} --scale {SCALE} '
           f'--result-weight {RESULT_WEIGHT} --batch {BATCH} --batches {BATCHES} --superbatches {SUPERBATCHES} '
           f'--lr {LR} --lr-step {LR_STEP} --seed {seed} --device {device} --id {name} --threads 2 '
           f'--out {out_dir} > {out_dir}/train.log 2>&1')
    return name, out_dir, time.time(), subprocess.Popen(cmd, shell=True, env={**os.environ, **env})


def held_out_loss(weights, path):
    """The trainer's validation loss of a float weights file on a held-out file (no training step)."""
    out_dir = f'{WORK}/score'
    shutil.rmtree(out_dir, ignore_errors=True)
    rc, out, _ = sh(f'{train} train --arch b0 --data {path} --val {path} --val-positions {VAL_POSITIONS} '
                    f'--scale {SCALE} --result-weight {RESULT_WEIGHT} --init-weights {weights} --superbatches 0 '
                    f'--out {out_dir}', env=env)
    try:
        return float(open(f'{out_dir}/val.txt').read().split()[1])
    except (OSError, IndexError, ValueError):
        return {'rc': rc, 'tail': out[-300:]}


def finish(arm, seed, name, out_dir, began, proc):
    rc = proc.wait()
    record = {'arm': arm, 'run': ARMS[arm], 'val_run': VAL_RUN[arm], 'seed': seed, 'rc': rc,
              'seconds': round(time.time() - began, 1), **settings}
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
        record['volume_starved'] = sb < STARVED_BEFORE
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
            json.dump(summary, open(f'{RESULT}/label_depth.json', 'w'), indent=1)
    d20_val = val['d20']
    for name, record in summary['runs'].items():
        weights = f'{RESULT}/{name}/weights.bin'
        if os.path.exists(weights):
            record['loss_on_d20_val'] = held_out_loss(weights, d20_val)
            json.dump(record, open(f'{RESULT}/{name}/run.json', 'w'), indent=1)
shutil.rmtree(repo, ignore_errors=True)
json.dump(summary, open(f'{RESULT}/label_depth.json', 'w'), indent=1)
print(json.dumps(summary, indent=1))
