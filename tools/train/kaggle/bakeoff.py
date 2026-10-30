# SPDX-License-Identifier: GPL-3.0-or-later

"""Bake-off training runs on Kaggle (DESIGN.md §5.4), pushed with `kaggle
kernels push` (GPU T4 x2, internet on, the shard dataset attached). It
builds tools/train at COMMIT, checks every mounted shard against the sealed
manifest, then trains each entry of RUNS (an architecture and a seed), two
at a time, one per GPU, all with the same settings and the maps of
tools/nnue/<arch>.json; validates after each superbatch on the held-out
*-val.vf shard; and for each run writes /kaggle/working/result/<arch>-s<seed>/
with the chosen checkpoint's quantised.bin and float weights.bin, the
trainer's own evaluation of the parity positions (parity-trainer.txt, the
parity test's T), the validation curve and a run record (run.json). The
summary of all runs is result/bakeoff.json.

The settings below are this push's; every run record repeats them. The
dry run (2026-10-30, g1s0) used one seed per entry, 3 superbatches of 100
batches and S = 107; the bake-off (g1s1) uses the values below.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import time

COMMIT = 'phase-4'          # replaced by the pushed commit's hash before the push
RUNS = [(arch, seed) for arch in ('b0', 's512', 'h512', 'afs', 'xgr512') for seed in (1, 2)]
SCALE = 105                 # S fitted on g1s1 (fit_scale.py, 2 M positions); the same for every entry
RESULT_WEIGHT = 0.5         # bullet's weight on the game result: 1 - lambda, lambda = 0.5 (§5.3)
BATCH = 16384
BATCHES = 305               # per superbatch: 5 M positions
SUPERBATCHES = 80           # 400 M positions seen, about 4.3 passes over g1s1's 93.5 M kept
LR = 0.001                  # bullet's example value (KB bullet-internals.md §5.3)
LR_STEP = 40                # tenfold drop every LR_STEP superbatches
VAL_POSITIONS = 20000
KEEP = 'best'               # 'best': the lowest validation loss; 'last': the final superbatch
MANIFEST = 'data/manifests/g1s1.json'
DATA = '/kaggle/input'
WORK = '/kaggle/working/bake'
RESULT = '/kaggle/working/result'


def sh(cmd, env=None, timeout=12 * 3600):
    t = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr), round(time.time() - t, 1)


def maps_args(repo, arch):
    if arch == 'b0':
        return ''
    desc = json.load(open(f'{repo}/tools/nnue/{arch}.json'))
    out = ''
    if arch in ('h512', 'afs'):
        out += ' --regions ' + ','.join(map(str, desc['regions']))
    if desc.get('table'):
        out += ' --buckets ' + ','.join(map(str, desc['table']))
    return out


os.makedirs(WORK, exist_ok=True)
os.makedirs(RESULT, exist_ok=True)
home = os.path.expanduser('~')
env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
       'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
settings = {'commit': COMMIT, 'scale': SCALE, 'result_weight': RESULT_WEIGHT, 'batch': BATCH, 'batches': BATCHES,
            'superbatches': SUPERBATCHES, 'lr': LR, 'lr_step': LR_STEP, 'val_positions': VAL_POSITIONS,
            'keep': KEEP, 'manifest': MANIFEST}
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
found = sorted(glob.glob(f'{DATA}/**/*.vf', recursive=True))
shards = [p for p in found if not p.endswith('-val.vf')]
val = [p for p in found if p.endswith('-val.vf')]
# The storage rule (DESIGN.md §5.3, deliverable 3): every mounted shard must
# match the sealed manifest's SHA-256 before it is used.
sealed = {s['file']: s['sha256'] for b in json.load(open(f'{repo}/{MANIFEST}'))['batches'] for s in b}
mismatch = [os.path.basename(p) for p in found
            if sealed.get(os.path.basename(p)) != hashlib.sha256(open(p, 'rb').read()).hexdigest()]
summary['hash_check'] = {'shards': len(found), 'sealed': len(sealed), 'mismatches': mismatch}
ok = rc == 0 and not mismatch and len(found) == len(sealed) and shards and val


def start(arch, seed, device):
    name = f'{arch}-s{seed}'
    out_dir = f'{WORK}/run-{name}'
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    cmd = (f'{train} train --arch {arch}{maps_args(repo, arch)} --data {" ".join(shards)} --val {val[0]} '
           f'--val-positions {VAL_POSITIONS} --patience {SUPERBATCHES + 1} --scale {SCALE} '
           f'--result-weight {RESULT_WEIGHT} --batch {BATCH} --batches {BATCHES} --superbatches {SUPERBATCHES} '
           f'--lr {LR} --lr-step {LR_STEP} --seed {seed} --device {device} --id {name} --threads 2 '
           f'--out {out_dir} > {out_dir}/train.log 2>&1')
    return name, out_dir, time.time(), subprocess.Popen(cmd, shell=True, env={**os.environ, **env})


def finish(arch, seed, name, out_dir, began, proc):
    rc = proc.wait()
    record = {'arch': arch, 'seed': seed, 'rc': rc, 'seconds': round(time.time() - began, 1), **settings}
    curve = []
    if os.path.exists(f'{out_dir}/val.txt'):
        curve = [(int(a), float(b)) for a, b in (l.split() for l in open(f'{out_dir}/val.txt'))]
    record['val_curve'] = curve
    record['positions_per_second'] = round(BATCH * BATCHES * len(curve) / record['seconds']) if curve else None
    dest = f'{RESULT}/{name}'
    os.makedirs(dest, exist_ok=True)
    if curve:
        sb = min(curve, key=lambda c: c[1])[0] if KEEP == 'best' else curve[-1][0]
        record['kept_superbatch'] = sb
        ck = f'{out_dir}/{name}-{sb}'
        shutil.copy(f'{ck}/quantised.bin', f'{dest}/quantised.bin')
        shutil.copy(f'{ck}/optimiser_state/weights.bin', f'{dest}/weights.bin')
        erc, eout, _ = sh(f'{train} eval --arch {arch}{maps_args(repo, arch)} --weights {dest}/weights.bin '
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
        live = [(arch, seed, *start(arch, seed, device)) for device, (arch, seed) in enumerate(batch)]
        for arch, seed, name, out_dir, began, proc in live:
            summary['runs'][name] = finish(arch, seed, name, out_dir, began, proc)
            json.dump(summary, open(f'{RESULT}/bakeoff.json', 'w'), indent=1)
shutil.rmtree(repo, ignore_errors=True)
json.dump(summary, open(f'{RESULT}/bakeoff.json', 'w'), indent=1)
print(json.dumps(summary, indent=1))
