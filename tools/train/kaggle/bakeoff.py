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
batches and S = 107. Round 1 (g1s1, 2026-10-30) used S = 105, 80
superbatches with the drop at 40 (400 M positions seen, about 4.3 passes
over its 93.5 M kept), the manifest data/manifests/g1s1.json and round 1's
maps. Round 2 (g2s1, owner, 2026-11-01: the same 4.3 passes) uses the
values below and the maps refitted on g2s1; it runs in two pushes, each
copy's RUNS replaced like COMMIT (b0, s512 and h512, then afs and xgr512),
so neither session nears Kaggle's 12-hour limit.

The trainer writes a checkpoint every superbatch (float weights, AdamW's
moments, quantised.bin). While a run trains, the checkpoints that can no
longer be kept are deleted: only the best so far and the two newest stay.
Keeping all of them filled /kaggle/working (about 20 GB) in round 2's
second push: XGR-512's two runs stopped at superbatches 326 and 328 of 360
with "No space left on device" (an H-512 checkpoint is about 27 MB; 360
per run, two runs at once).
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
SCALE = 92                  # S fitted on g2s1 (fit_scale.py's fit, 2 M positions drawn from every source
                            # in proportion to its saved positions); the same for every entry
RESULT_WEIGHT = 0.5         # bullet's weight on the game result: 1 - lambda, lambda = 0.5 (§5.3)
BATCH = 16384
BATCHES = 305               # per superbatch: 5 M positions
SUPERBATCHES = 360          # 1.8 B positions seen, about 4.3 passes over g2s1's 415.9 M kept
LR = 0.001                  # bullet's example value (KB bullet-internals.md §5.3)
LR_STEP = 180               # tenfold drop every LR_STEP superbatches (halfway, as round 1)
VAL_POSITIONS = 20000
KEEP = 'best'               # 'best': the lowest validation loss; 'last': the final superbatch
MANIFEST = 'data/manifests/g2s1.json'
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


def drop_old_checkpoints(name, out_dir):
    """Deletes the run's checkpoints except the one KEEP would choose so far
    (from val.txt) and the two newest (the newest may still be written)."""
    found = {}
    for d in glob.glob(f'{out_dir}/{name}-*'):
        tail = d.rsplit('-', 1)[1]
        if tail.isdigit():
            found[int(tail)] = d
    keep = set(sorted(found)[-2:])
    curve = []
    if os.path.exists(f'{out_dir}/val.txt'):
        for line in open(f'{out_dir}/val.txt'):
            # Complete lines only: a line still being written can parse as a
            # smaller loss than it will hold ("0.0" of "0.0213...").
            if line.endswith('\n') and len(line.split()) == 2:
                curve.append((int(line.split()[0]), float(line.split()[1])))
    if curve:
        keep.add(min(curve, key=lambda c: c[1])[0] if KEEP == 'best' else curve[-1][0])
    for sb, d in found.items():
        if sb not in keep:
            shutil.rmtree(d, ignore_errors=True)


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
        while any(proc.poll() is None for *_, proc in live):
            for arch, seed, name, out_dir, began, proc in live:
                drop_old_checkpoints(name, out_dir)
            time.sleep(60)
        for arch, seed, name, out_dir, began, proc in live:
            drop_old_checkpoints(name, out_dir)
            summary['runs'][name] = finish(arch, seed, name, out_dir, began, proc)
            json.dump(summary, open(f'{RESULT}/bakeoff.json', 'w'), indent=1)
shutil.rmtree(repo, ignore_errors=True)
json.dump(summary, open(f'{RESULT}/bakeoff.json', 'w'), indent=1)
print(json.dumps(summary, indent=1))
