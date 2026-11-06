# SPDX-License-Identifier: GPL-3.0-or-later

"""The default network's retrain on g3s2 (owner, 2026-11-06; DESIGN.md §5.6
item 7), on Kaggle. Its architecture is chosen by S512+PP's evidence: S512+PP
(s512pp) only if S512+PP passed its STC SPRT against S512r2, plain S-512
(s512) otherwise; ARCH is set to the decided one before the push and the
kernel refuses to run without it.

Two recipes, two seeds each, declared before the run:
- warm: a warm start at an initial LR of 0.0001, dropped tenfold after 180
  superbatches; from S512r2's float weights (s512), or from S512+PP's
  candidate's float weights (s512pp: round 2's run s512pp-s2, kept
  superbatch 350, the net of bake/s512pp). The warm start must reproduce its
  net's own validation loss first (INIT_CHECKS: the same validation file,
  20,000 positions, S and result weight; within 1e-6).
- scratch: from random weights with the current schedule (LR 0.001, dropped
  tenfold after 180 superbatches).
Otherwise S512r2's settings (retrain.py's): S = 92, result weight 0.5,
AdamW, batch 16,384 x 305 per superbatch, 360 superbatches, the checkpoint
with the lowest validation loss kept. Batch 1 trains warm and scratch seed
1 side by side (one GPU each), batch 2 their seed 2.

Data: g2s1, g3s1 and g3s2 (data/manifests/g3s2.json: the rest of g3, the
parts g3b-g3e and the Syzygy endgame slice), read interleaved
(fork-train --interleave), so the slice and every part are spread through
each pass. Every mounted shard must match its sealed manifest's SHA-256;
the *-val.vf files never train (each part's designated shard: its first 60
games are in g3s2-val.vf and its rest trains as g3s2-<shard>-rest.vf).
Validation: g3s2-val.vf, shared by every run.

Scoring (summary['recipes']): each recipe by the mean of its seeds'
best-checkpoint losses on g3s2-val.vf; the better recipe's best seed is the
candidate (then the parity chain, the endgame acceptance test and its STC
SPRT against S512r2, locally). A difference within 4e-5 (S-512's measured
seed spread from scratch) is recorded as unresolved. The run layout is
retrain.py's: /kaggle/working/result/<arch>-<recipe>-s<seed>/, the summary
result/retrain.json.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import time
import traceback

COMMIT = 'nets/s512pp'      # replaced by the pushed commit's hash before the push
ARCH = None                 # 's512pp' or 's512': set from S512+PP's STC SPRT before the push
SEEDS = (1, 2)
RECIPES = {'warm': {'lr': 0.0001, 'lr_step': 180, 'init': True},
           'scratch': {'lr': 0.001, 'lr_step': 180, 'init': False}}
SEED_SPREAD = 4e-5  # S-512's measured seed spread from scratch: a smaller difference is unresolved
SCALE = 92
RESULT_WEIGHT = 0.5
BATCH = 16384
BATCHES = 305
SUPERBATCHES = 360
VAL_POSITIONS = 20000
MANIFESTS = ['data/manifests/g2s1.json', 'data/manifests/g3s1.json', 'data/manifests/g3b.json',
             'data/manifests/g3c.json', 'data/manifests/g3d.json', 'data/manifests/g3e.json',
             'data/manifests/g3s2.json']
VAL = 'g3s2-val.vf'
# The warm start's initial weights per architecture: file, SHA-256, the validation file and loss it must reproduce.
INIT_CHECKS = {
    's512': {'weights': 's512r2-weights.bin',
             'sha256': '8c972f73e1dd2c9dc7a9d1597f4e3ad78c9dd89323e6a307afd712c29addf692',
             'val': 'g2s1-val.vf', 'loss': 0.01945765},   # S512r2: round 2's S-512 seed 2, superbatch 307
    's512pp': {'weights': 's512pp-s2-weights.bin',
               'sha256': 'ca22060b2d0f29950d1066251b5736b7f14d0416e50075ec848d358352f13ff5',
               'val': 'g3s1-val.vf', 'loss': 0.01929241},  # S512+PP's run s512pp-s2, superbatch 350
}
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


assert ARCH in INIT_CHECKS, 'ARCH is not set: S512+PP\'s STC SPRT decides it'
os.makedirs(WORK, exist_ok=True)
os.makedirs(RESULT, exist_ok=True)
home = os.path.expanduser('~')
env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
       'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
init_check = INIT_CHECKS[ARCH]
settings = {'commit': COMMIT, 'arch': ARCH, 'recipes': RECIPES, 'seeds': SEEDS, 'scale': SCALE,
            'result_weight': RESULT_WEIGHT, 'batch': BATCH, 'batches': BATCHES, 'superbatches': SUPERBATCHES,
            'val_positions': VAL_POSITIONS, 'keep': 'best', 'manifests': MANIFESTS, 'val': VAL,
            'interleave': True, 'init': init_check}
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
# python-chess for tools/nnue (reference.py imports models.py), as the local .venv's.
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
init = glob.glob(f'{DATA}/**/{init_check["weights"]}', recursive=True)
init_ok = len(init) == 1 and init_check['sha256'] is not None and sha256(init[0]) == init_check['sha256']
summary['init_weights'] = {'found': len(init), 'sha256_ok': init_ok}
ok = built and rc_pip == 0 and not mismatch and not missing and len(found) == len(sealed) and shards \
    and VAL in by_name and init_check['val'] in by_name and init_ok
summary['training_shards'] = len(shards)
save()


def warm_start_loss():
    """The initial net's own validation loss, reproduced from its float weights."""
    out_dir = f'{WORK}/init-{ARCH}'
    shutil.rmtree(out_dir, ignore_errors=True)
    rc, out, _ = sh(f'{train} train --arch {ARCH}{maps_args(repo, ARCH)} --data {shards[0]} '
                    f'--val {by_name[init_check["val"]]} --val-positions {VAL_POSITIONS} --scale {SCALE} '
                    f'--result-weight {RESULT_WEIGHT} --init-weights {init[0]} --superbatches 0 '
                    f'--device 0 --threads 2 --out {out_dir}', env=env)
    loss = None
    if rc == 0 and os.path.exists(f'{out_dir}/val.txt'):
        first = open(f'{out_dir}/val.txt').readline().split()
        loss = float(first[1]) if first and first[0] == '0' else None
    return {'rc': rc, 'loss': loss, 'tail': out[-300:]}


def feature_checks():
    """fork-train check, and the feature leg against tools/nnue/reference.py."""
    res = {}
    rc, out, _ = sh(f'{train} check --arch {ARCH}{maps_args(repo, ARCH)} --out {WORK}/check-{ARCH}', env=env)
    res['check'] = {'rc': rc, 'out': out[-300:]}
    legs = []
    for src in (f'--epd {repo}/tests/nnue/parity.epd', f'--data {by_name[VAL]} --count 5000'):
        feats = f'{WORK}/features-{ARCH}-{len(legs)}.txt'
        rc1, out1, _ = sh(f'{train} features --arch {ARCH}{maps_args(repo, ARCH)} {src} > {feats}', env=env)
        rc2, out2, _ = sh(f'python3 {repo}/tools/nnue/reference.py features --rust {feats} '
                          f'--layout {repo}/tools/nnue/{ARCH}.json')
        legs.append({'source': src.split()[0], 'features_rc': rc1, 'leg_rc': rc2, 'leg': out2.strip()[-300:]})
    res['feature_legs'] = legs
    res['ok'] = rc == 0 and all(l['features_rc'] == 0 and l['leg_rc'] == 0 for l in legs)
    return res


if ok:
    c = feature_checks() if ARCH == 's512pp' else {'ok': True}
    if c['ok']:
        c['warm_start'] = warm_start_loss()
        loss = c['warm_start']['loss']
        c['ok'] = loss is not None and abs(loss - init_check['loss']) <= INIT_TOLERANCE
    summary['checks'][ARCH] = c
    ok = c['ok']
    save()


def start(recipe, seed, device):
    r = RECIPES[recipe]
    name = f'{ARCH}-{recipe}-s{seed}'
    out_dir = f'{WORK}/run-{name}'
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    cmd = (f'{train} train --arch {ARCH}{maps_args(repo, ARCH)} --data {" ".join(shards)} --interleave '
           f'--val {by_name[VAL]} --val-positions {VAL_POSITIONS} --patience {SUPERBATCHES + 1} --scale {SCALE} '
           f'--result-weight {RESULT_WEIGHT} --batch {BATCH} --batches {BATCHES} --superbatches {SUPERBATCHES} '
           f'--lr {r["lr"]} --lr-step {r["lr_step"]} --seed {seed} --device {device} --id {name} --threads 2 '
           + (f'--init-weights {init[0]} ' if r['init'] else '') + f'--out {out_dir} > {out_dir}/train.log 2>&1')
    return name, out_dir, time.time(), subprocess.Popen(cmd, shell=True, env={**os.environ, **env})


def drop_old_checkpoints(name, out_dir):
    """Deletes the run's checkpoints except the best so far (from val.txt)
    and the two newest (the newest may still be written)."""
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
    # Superbatch 0 is the initial weights: never the result.
    curve = [c for c in curve if c[0] > 0]
    if curve:
        keep.add(min(curve, key=lambda c: c[1])[0])
    for sb, d in kept.items():
        if sb not in keep:
            shutil.rmtree(d, ignore_errors=True)


def finish(recipe, seed, name, out_dir, began, proc):
    rc = proc.wait()
    record = {'arch': ARCH, 'recipe': recipe, 'seed': seed, 'rc': rc, 'seconds': round(time.time() - began, 1),
              **RECIPES[recipe]}
    curve = []
    if os.path.exists(f'{out_dir}/val.txt'):
        curve = [(int(a), float(b)) for a, b in (l.split() for l in open(f'{out_dir}/val.txt'))]
    record['val_curve'] = curve
    trained = [c for c in curve if c[0] > 0]
    record['positions_per_second'] = round(BATCH * BATCHES * len(trained) / record['seconds']) if trained else None
    dest = f'{RESULT}/{name}'
    os.makedirs(dest, exist_ok=True)
    if trained:
        sb, best = min(trained, key=lambda c: c[1])
        record['kept_superbatch'] = sb
        record['best_loss'] = best
        record['initial_loss'] = curve[0][1] if curve[0][0] == 0 else None
        ck = f'{out_dir}/{name}-{sb}'
        shutil.copy(f'{ck}/quantised.bin', f'{dest}/quantised.bin')
        shutil.copy(f'{ck}/optimiser_state/weights.bin', f'{dest}/weights.bin')
        erc, eout, _ = sh(f'{train} eval --arch {ARCH}{maps_args(repo, ARCH)} --weights {dest}/weights.bin '
                          f'--epd {repo}/tests/nnue/parity.epd --out {dest}/parity-trainer.txt', env=env)
        record['eval'] = {'rc': erc, 'tail': eout[-300:]}
        shutil.copy(f'{out_dir}/val.txt', f'{dest}/val.txt')
    shutil.copy(f'{out_dir}/train.log', f'{dest}/train.log')
    json.dump(record, open(f'{dest}/run.json', 'w'), indent=1)
    shutil.rmtree(out_dir, ignore_errors=True)
    return record


def score_recipes():
    """Each recipe's mean best loss, the better recipe and its best seed."""
    means = {}
    for recipe in RECIPES:
        losses = [r['best_loss'] for r in summary['runs'].values() if r.get('recipe') == recipe and 'best_loss' in r]
        if len(losses) == len(SEEDS):
            means[recipe] = sum(losses) / len(losses)
    out = {'means': means}
    if len(means) == len(RECIPES):
        better = min(means, key=means.get)
        runs = [(r['best_loss'], n) for n, r in summary['runs'].items() if r.get('recipe') == better and 'best_loss' in r]
        diff = max(means.values()) - min(means.values())
        out.update(better=better, difference=diff, resolved=diff > SEED_SPREAD, candidate=min(runs)[1])
    summary['recipes'] = out


pending = [(recipe, seed) for seed in SEEDS for recipe in RECIPES] if ok else []
try:
    while pending:
        batch = [pending.pop(0) for _ in range(min(2, len(pending)))]
        live = [(recipe, seed, *start(recipe, seed, device)) for device, (recipe, seed) in enumerate(batch)]
        while any(proc.poll() is None for *_, proc in live):
            for recipe, seed, name, out_dir, began, proc in live:
                drop_old_checkpoints(name, out_dir)
            time.sleep(60)
        for recipe, seed, name, out_dir, began, proc in live:
            drop_old_checkpoints(name, out_dir)
            try:
                summary['runs'][name] = finish(recipe, seed, name, out_dir, began, proc)
            except Exception:  # recorded, and the other runs go on
                summary['runs'][name] = {'arch': ARCH, 'recipe': recipe, 'seed': seed,
                                         'error': traceback.format_exc()[-2000:]}
                if os.path.exists(f'{out_dir}/train.log'):
                    os.makedirs(f'{RESULT}/{name}', exist_ok=True)
                    shutil.copy(f'{out_dir}/train.log', f'{RESULT}/{name}/train.log')
            score_recipes()
            save()
finally:
    # Even after a failure: the clone and its build would otherwise fill the
    # session's output with thousands of files.
    shutil.rmtree(repo, ignore_errors=True)
save()
print(json.dumps(summary, indent=1))
