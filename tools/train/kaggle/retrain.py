# SPDX-License-Identifier: GPL-3.0-or-later

"""Warm-started retrains on Kaggle (owner, 2026-11-02): S512r3 (S-512's
architecture, the default network's next retrain) and S512+X (S-512 plus
XGR's exposure plane, tools/train --arch s512x), both from S512r2's float
weights, on generation 2's snapshot g2s1 and generation 3's first snapshot
g3s1 together, two seeds each, S512r2's settings otherwise. Pushed with
`kaggle kernels push` (GPU T4 x2, internet on, both shard datasets and
S512r2's weights attached), like bakeoff.py, whose run layout it keeps:
/kaggle/working/result/<arch>-s<seed>/ with the kept checkpoint's
quantised.bin and weights.bin, the trainer's evaluation of the parity
positions (parity-trainer.txt), the validation curve and run.json; the
summary is result/retrain.json.

Before any training, every mounted shard is checked against its sealed
manifest and S512r2's weights against INIT_SHA256. Each architecture's
warm start must then reproduce S512r2's own validation loss on g2s1-val.vf
(INIT_LOSS: its kept superbatch 307's 0.01945765, the same 20,000
positions, S and result weight; within 1e-6): S512r3 from S512r2's weights
as they are, S512+X from them with the exposure inputs appended as zero
columns (tools/nnue/extend_weights.py, whose output must match
EXTENDED_SHA256), which compute S-512's output exactly. S512+X also needs
`fork-train check` to pass and its feature lists (`fork-train features` on
the parity positions and on validation positions) to equal those of
Fork's independent reference (tools/nnue/reference.py features). An
architecture that fails a check is not trained; the check's output is in
the summary.

Settings: S512r2's (bakeoff.py, round 2): S = 92 (a warm start keeps its
net's target scale, as B0r1 did), result weight 0.5, AdamW, LR 0.001
dropped tenfold after 180 superbatches, batch 16,384 x 305 per superbatch,
360 superbatches, the checkpoint with the lowest validation loss kept, S512r2's
phase table (tools/nnue/s512.json; s512x.json holds the same). Validation:
g3s1-val.vf, every source of both snapshots (data/manifests/g3s1.json).
The S512r3 pair trains first; S512+X after it.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import time

COMMIT = 'phase-4'          # replaced by the pushed commit's hash before the push
RUNS = [('s512', 1), ('s512', 2), ('s512x', 1), ('s512x', 2)]
SCALE = 92
RESULT_WEIGHT = 0.5
BATCH = 16384
BATCHES = 305
SUPERBATCHES = 360
LR = 0.001
LR_STEP = 180
VAL_POSITIONS = 20000
KEEP = 'best'
MANIFESTS = ['data/manifests/g2s1.json', 'data/manifests/g3s1.json']
VAL = 'g3s1-val.vf'
INIT_CHECK_VAL = 'g2s1-val.vf'
INIT_WEIGHTS = 's512r2-weights.bin'  # round 2's S-512 seed 2, superbatch 307 (the promoted S512r2)
INIT_SHA256 = '8c972f73e1dd2c9dc7a9d1597f4e3ad78c9dd89323e6a307afd712c29addf692'
EXTENDED_SHA256 = '2457dc449d844cb19cef8a1adfb01d6d534aa826094a42a4e7384ae79720c20d'  # extend_weights.py's output (computed locally)
INIT_LOSS = 0.01945765
INIT_TOLERANCE = 1e-6
DATA = '/kaggle/input'
WORK = '/kaggle/working/retrain'
RESULT = '/kaggle/working/result'


def sh(cmd, env=None, timeout=12 * 3600):
    t = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr), round(time.time() - t, 1)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def maps_args(repo, arch):
    desc = json.load(open(f'{repo}/tools/nnue/{arch}.json'))
    return ' --buckets ' + ','.join(map(str, desc['table']))


os.makedirs(WORK, exist_ok=True)
os.makedirs(RESULT, exist_ok=True)
home = os.path.expanduser('~')
env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
       'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
settings = {'commit': COMMIT, 'scale': SCALE, 'result_weight': RESULT_WEIGHT, 'batch': BATCH, 'batches': BATCHES,
            'superbatches': SUPERBATCHES, 'lr': LR, 'lr_step': LR_STEP, 'val_positions': VAL_POSITIONS,
            'keep': KEEP, 'manifests': MANIFESTS, 'val': VAL, 'init_weights': INIT_WEIGHTS,
            'init_sha256': INIT_SHA256}
summary = {'settings': settings, 'checks': {}, 'runs': {}}


def save():
    json.dump(summary, open(f'{RESULT}/retrain.json', 'w'), indent=1)


rc, out, secs = sh('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal')
summary['rustup'] = rc
repo = f'{WORK}/fork'
rc, out, secs = sh(f'cd {WORK} && rm -rf fork && git clone -q https://github.com/BOSSDOTCOM/fork && cd fork && '
                   f'git checkout -q {COMMIT} && git log --oneline -1')
summary['head'] = out.strip()[-120:]
rc, out, secs = sh(f'cd {repo}/tools/train && cargo build --release --locked --features cuda', env=env)
summary['build'] = {'rc': rc, 'seconds': secs, 'tail': out[-400:] if rc else ''}
built = rc == 0
# python-chess for tools/nnue (extend_weights.py and reference.py import models.py), as the local .venv's.
rc_pip, out_pip, _ = sh('python3 -m pip install -q chess==1.11.2')
summary['pip'] = {'rc': rc_pip, 'tail': out_pip[-200:]}
train = f'{repo}/tools/train/target/release/fork-train'
found = sorted(glob.glob(f'{DATA}/**/*.vf', recursive=True))
by_name = {os.path.basename(p): p for p in found}
# The storage rule (DESIGN.md §5.3, deliverable 3): every mounted shard must
# match its sealed manifest's SHA-256 before it is used.
sealed = {}
for m in MANIFESTS:
    for b in json.load(open(f'{repo}/{m}'))['batches']:
        for s in b:
            sealed[s['file']] = s['sha256']
mismatch = [n for n, p in by_name.items() if sealed.get(n) != sha256(p)]
missing = sorted(set(sealed) - set(by_name))
summary['hash_check'] = {'shards': len(found), 'sealed': len(sealed), 'mismatches': mismatch, 'missing': missing}
shards = [p for n, p in sorted(by_name.items()) if not n.endswith('-val.vf')]
init = glob.glob(f'{DATA}/**/{INIT_WEIGHTS}', recursive=True)
init_ok = len(init) == 1 and sha256(init[0]) == INIT_SHA256
summary['init_weights'] = {'found': len(init), 'sha256_ok': init_ok}
ok = built and rc_pip == 0 and not mismatch and not missing and len(found) == len(sealed) and shards and VAL in by_name \
    and INIT_CHECK_VAL in by_name and init_ok
save()

inits = {}
if ok:
    inits['s512'] = init[0]
    ext = f'{WORK}/s512x-init-weights.bin'
    rc, out, _ = sh(f'python3 {repo}/tools/nnue/extend_weights.py {init[0]} {ext}')
    summary['checks']['s512x_extend'] = {'rc': rc, 'out': out[-300:],
                                         'sha256': sha256(ext) if rc == 0 else None}
    if rc == 0 and sha256(ext) == EXTENDED_SHA256:
        inits['s512x'] = ext
    save()


def warm_start_loss(arch):
    """S512r2's validation loss reproduced from the initial weights."""
    out_dir = f'{WORK}/init-{arch}'
    shutil.rmtree(out_dir, ignore_errors=True)
    rc, out, _ = sh(f'{train} train --arch {arch}{maps_args(repo, arch)} --data {shards[0]} '
                    f'--val {by_name[INIT_CHECK_VAL]} --val-positions {VAL_POSITIONS} --scale {SCALE} '
                    f'--result-weight {RESULT_WEIGHT} --init-weights {inits[arch]} --superbatches 0 '
                    f'--device 0 --threads 2 --out {out_dir}', env=env)
    loss = None
    if rc == 0 and os.path.exists(f'{out_dir}/val.txt'):
        first = open(f'{out_dir}/val.txt').readline().split()
        loss = float(first[1]) if first and first[0] == '0' else None
    return {'rc': rc, 'loss': loss, 'tail': out[-300:]}


def s512x_checks():
    """fork-train check, and the feature leg against tools/nnue/reference.py."""
    res = {}
    rc, out, _ = sh(f'{train} check --arch s512x{maps_args(repo, "s512x")} --out {WORK}/check-s512x', env=env)
    res['check'] = {'rc': rc, 'out': out[-300:]}
    legs = []
    for src in (f'--epd {repo}/tests/nnue/parity.epd', f'--data {by_name[VAL]} --count 5000'):
        feats = f'{WORK}/features-s512x-{len(legs)}.txt'
        rc1, out1, _ = sh(f'{train} features --arch s512x{maps_args(repo, "s512x")} {src} > {feats}', env=env)
        rc2, out2, _ = sh(f'python3 {repo}/tools/nnue/reference.py features --rust {feats} '
                          f'--layout {repo}/tools/nnue/s512x.json')
        legs.append({'source': src.split()[0], 'features_rc': rc1, 'leg_rc': rc2, 'leg': out2.strip()[-300:]})
    res['feature_legs'] = legs
    res['ok'] = rc == 0 and all(l['features_rc'] == 0 and l['leg_rc'] == 0 for l in legs)
    return res


trainable = set()
if ok:
    for arch in ('s512', 's512x'):
        if arch not in inits:
            summary['checks'][arch] = {'ok': False, 'reason': 'no initial weights (hash mismatch or tool failure)'}
            continue
        c = {}
        if arch == 's512x':
            c = s512x_checks()
            if not c['ok']:
                summary['checks'][arch] = c
                save()
                continue
        c['warm_start'] = warm_start_loss(arch)
        loss = c['warm_start']['loss']
        c['ok'] = loss is not None and abs(loss - INIT_LOSS) <= INIT_TOLERANCE
        summary['checks'][arch] = c
        if c['ok']:
            trainable.add(arch)
        save()


def start(arch, seed, device):
    name = f'{arch}-s{seed}'
    out_dir = f'{WORK}/run-{name}'
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    cmd = (f'{train} train --arch {arch}{maps_args(repo, arch)} --data {" ".join(shards)} --val {by_name[VAL]} '
           f'--val-positions {VAL_POSITIONS} --patience {SUPERBATCHES + 1} --scale {SCALE} '
           f'--result-weight {RESULT_WEIGHT} --batch {BATCH} --batches {BATCHES} --superbatches {SUPERBATCHES} '
           f'--lr {LR} --lr-step {LR_STEP} --seed {seed} --device {device} --id {name} --threads 2 '
           f'--init-weights {inits[arch]} --out {out_dir} > {out_dir}/train.log 2>&1')
    return name, out_dir, time.time(), subprocess.Popen(cmd, shell=True, env={**os.environ, **env})


def drop_old_checkpoints(name, out_dir):
    """Deletes the run's checkpoints except the one KEEP would choose so far
    (from val.txt) and the two newest (the newest may still be written)."""
    kept = {}
    for d in glob.glob(f'{out_dir}/{name}-*'):
        tail = d.rsplit('-', 1)[1]
        if tail.isdigit():
            kept[int(tail)] = d
    keep = set(sorted(kept)[-2:])
    curve = []
    if os.path.exists(f'{out_dir}/val.txt'):
        for line in open(f'{out_dir}/val.txt'):
            # Complete lines only (a line still being written can parse short).
            if line.endswith('\n') and len(line.split()) == 2:
                curve.append((int(line.split()[0]), float(line.split()[1])))
    # Superbatch 0 is the initial weights, which have no checkpoint and are
    # never the result: the kept checkpoint is the best trained one, even
    # when none beats the initial loss.
    curve = [c for c in curve if c[0] > 0]
    if curve:
        keep.add(min(curve, key=lambda c: c[1])[0] if KEEP == 'best' else curve[-1][0])
    for sb, d in kept.items():
        if sb not in keep:
            shutil.rmtree(d, ignore_errors=True)


def finish(arch, seed, name, out_dir, began, proc):
    rc = proc.wait()
    record = {'arch': arch, 'seed': seed, 'rc': rc, 'seconds': round(time.time() - began, 1), **settings}
    curve = []
    if os.path.exists(f'{out_dir}/val.txt'):
        curve = [(int(a), float(b)) for a, b in (l.split() for l in open(f'{out_dir}/val.txt'))]
    record['val_curve'] = curve
    trained = [c for c in curve if c[0] > 0]
    record['positions_per_second'] = round(BATCH * BATCHES * len(trained) / record['seconds']) if trained else None
    dest = f'{RESULT}/{name}'
    os.makedirs(dest, exist_ok=True)
    if trained:
        # Superbatch 0 is the initial weights (S512r2's): never kept as the result.
        sb = min(trained, key=lambda c: c[1])[0] if KEEP == 'best' else trained[-1][0]
        record['kept_superbatch'] = sb
        record['initial_loss'] = curve[0][1] if curve[0][0] == 0 else None
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


pending = [r for r in RUNS if r[0] in trainable]
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
        save()
shutil.rmtree(repo, ignore_errors=True)
save()
print(json.dumps(summary, indent=1))
