# SPDX-License-Identifier: GPL-3.0-or-later

"""Idea 59 step 3: the Boundary Refiner's training session, on Kaggle (GPU T4 x2), kernel fork-refiner
(docs/research/boundary-refiner/step3-plan.md 3.6-3.7, "The training session" and the cap's procedure, recorded
before the run; lane E, E-f). Data: the private dataset fork-i59s3 (train.sites, val.sites, test.sites,
s512ppr3.fnet, parity.sites, parity-weights.bin, val-windows.jsonl; tools/nnue/refiner.py export). The trainer is
fork-train --arch refiner at COMMIT, built with CUDA; the frozen base is S512ppr3's net file (its integers / 255).

Steps, in order; either check failing stops the session (fix the pipeline, not a try):
1. The parity chain's trainer leg: fork-train eval on parity.sites with the synthetic refiner parity-weights.bin
   against R-float (tools/nnue/models.py refiner_float on the same base), every head within 0.0002.
2. A1: superbatch 0's weighted validation loss (heads at zero) equal to the base's own within 1e-6.
3. Nine runs, LR 0.001 (AdamW), a tenfold drop at superbatch 40 of 80, one pass of the data per superbatch,
   batch 16,384, early stopping with patience 8 on the weighted validation loss (val.sites):
   - w1, w2: the weighted arm (closeness x call mix), seeds 1 and 2, cap 198 cp;
   - p1, p2: the plain arm (weight 1 at every used site; mates and the table band stay out), seeds 1 and 2, 198;
   - w1-c57, w1-c480: the weighted arm, seed 1, at the cap's other candidates;
   - l125k, l250k, l500k: the learning curve, the weighted arm, seed 1, cap 198, on seeded subsets of train.sites
     (1M is w1).
   GPU 0: w1, p1, w1-c57, l125k, l250k; GPU 1: w2, p2, w1-c480, l500k. A curve run is dropped (for a second
   session) if the session's GPU time with its estimate would pass 4 T4 GPU-hours.
4. The cap: each candidate's validation outputs give deployment-weighted net flips (sites inside gate (a)'s
   margins, equal within a kind, times the call-mix factor: val-windows.jsonl's weight) at the gate's nearest
   bound, at reverse futility (x - 80 >= beta) and at futility (x + 100 + 70 <= alpha, main-search sites);
   start at 57, a larger candidate replaces the current one if its score is higher by more than one standard
   error of the paired difference. Also each run's gate net flips (the arms' offline check, information).
No offline acceptance on test here (it waits for the orchestrator's confirmation).

Layout: /kaggle/working/result/<run>/ (best/weights.bin, val.txt, mu.txt, train.log, run.json, eval-val.txt),
result/parity/ (trainer-parity.txt, a1.log), the summary result/refiner.json.

    python3 refiner.py           # on Kaggle (the kernel runs it without arguments)
    python refiner.py --plan     # anywhere: prints the runs' commands and the settings, touches nothing
"""
import glob
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback

COMMIT = 'idea59/step3'     # replaced by the pushed commit's hash in the kernel's staged copy
SCALE = 89                  # S512ppr3's output scale (docs/nets.md)
CAP = 198                   # the declared cap (the 75th percentile; plan 3.7)
CAPS = (57, 198, 480)       # the cap's candidates (50th, 75th, 90th percentiles; plan 3.7)
SUPERBATCHES, LR_STEP, PATIENCE, BATCH, LR = 80, 40, 8, 16384, 0.001
BUDGET = 4 * 3600           # GPU-seconds (the plan's 4 T4 GPU-hours)
RUNS = {
    'w1': {'sites': 'train', 'seed': 1, 'cap': 198}, 'w2': {'sites': 'train', 'seed': 2, 'cap': 198},
    'p1': {'sites': 'plain', 'seed': 1, 'cap': 198}, 'p2': {'sites': 'plain', 'seed': 2, 'cap': 198},
    'w1-c57': {'sites': 'train', 'seed': 1, 'cap': 57}, 'w1-c480': {'sites': 'train', 'seed': 1, 'cap': 480},
    'l125k': {'sites': 125000, 'seed': 1, 'cap': 198, 'curve': True},
    'l250k': {'sites': 250000, 'seed': 1, 'cap': 198, 'curve': True},
    'l500k': {'sites': 500000, 'seed': 1, 'cap': 198, 'curve': True},
}
QUEUES = [['w1', 'p1', 'w1-c57', 'l125k', 'l250k'], ['w2', 'p2', 'w1-c480', 'l500k']]
WORK = '/kaggle/working/refiner'
RESULT = '/kaggle/working/result'


def sh(cmd, env=None, timeout=12 * 3600):
    t = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr), round(time.time() - t, 1)


def stage_args(run, device):
    """A run's trainer flags, without paths."""
    a = RUNS[run]
    return (f'--scale {SCALE} --cap {a["cap"]} --seed {a["seed"]} --superbatches {SUPERBATCHES} --lr {LR} '
            f'--lr-step {LR_STEP} --patience {PATIENCE} --batch {BATCH} --threads 2 --device {device}')


def plan():
    """--plan: the settings and every run's command with placeholder paths; nothing is touched."""
    print(json.dumps({'commit': COMMIT, 'scale': SCALE, 'caps': CAPS, 'runs': RUNS, 'queues': QUEUES,
                      'budget_gpu_seconds': BUDGET}, indent=1))
    print('check 1: fork-train eval --arch refiner --base-weights <s512ppr3.fnet> --weights <parity-weights.bin> '
          '--sites <parity.sites> --out <parity/trainer-parity.txt>, then R-float on each line')
    print(f'check 2: fork-train train --arch refiner ... --sites <train.sites> --val-sites <val.sites> '
          f'--superbatches 0 --scale {SCALE} --cap {CAP} --out <parity/a1>')
    for q, runs in enumerate(QUEUES):
        for run in runs:
            print(f'GPU {q} {run}: fork-train train --arch refiner --base-weights <s512ppr3.fnet> '
                  f'--sites <{RUNS[run]["sites"]}> --val-sites <val.sites> {stage_args(run, q)} --out <result/{run}>')


if __name__ == '__main__' and '--plan' in sys.argv:
    plan()
    sys.exit(0)
if __name__ == '__main__' and ('--help' in sys.argv or '-h' in sys.argv):
    print(__doc__)
    sys.exit(0)
inputs = {os.path.basename(p): p for p in glob.glob('/kaggle/input/**/*', recursive=True) if os.path.isfile(p)}
if 'train.sites' not in inputs:
    sys.exit('the fork-i59s3 dataset is not attached: this script runs inside the Kaggle session (--plan prints the runs)')

os.makedirs(WORK, exist_ok=True)
os.makedirs(f'{RESULT}/parity', exist_ok=True)
home = os.path.expanduser('~')
env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
       'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
summary = {'settings': {'commit': COMMIT, 'scale': SCALE, 'caps': CAPS, 'runs': RUNS, 'queues': QUEUES,
                        'superbatches': SUPERBATCHES, 'lr': LR, 'lr_step': LR_STEP, 'patience': PATIENCE,
                        'batch': BATCH, 'budget_gpu_seconds': BUDGET},
           'checks': {}, 'runs': {}, 'dropped': [], 'cap': {}, 'gate_nf': {}, 'curve': {}}
lock = threading.Lock()


def save():
    with lock:
        json.dump(summary, open(f'{RESULT}/refiner.json', 'w'), indent=1)


def finish(why):
    """Stops the session after a failed check, the reason in the summary."""
    summary['stopped'] = why
    save()
    print('STOP:', why)
    sys.exit(1)


rc, out, secs = sh('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal')
summary['rustup'] = rc
rc, out, secs = sh('pip install -q chess==1.11.2')
summary['python_chess'] = rc
repo = f'{WORK}/fork'
rc, out, secs = sh(f'cd {WORK} && rm -rf fork && git clone -q https://github.com/BOSSDOTCOM/fork && cd fork && '
                   f'git checkout -q {COMMIT} && git log --oneline -1')
summary['head'] = out.strip()[-120:]
rc, out, secs = sh(f'cd {repo}/tools/train && cargo build --release --locked --features cuda', env=env)
summary['build'] = {'rc': rc, 'seconds': secs, 'tail': out[-400:] if rc else ''}
save()
if rc:
    finish('the trainer did not build')
ft = f'{repo}/tools/train/target/release/fork-train'
net = inputs['s512ppr3.fnet']
sys.path.insert(0, f'{repo}/tools/nnue')
import chess  # noqa: E402
import models  # noqa: E402
import netformat  # noqa: E402

# 1. The parity chain's trainer leg.
rc, out, secs = sh(f'{ft} eval --arch refiner --base-weights {net} --weights {inputs["parity-weights.bin"]} '
                   f'--sites {inputs["parity.sites"]} --out {RESULT}/parity/trainer-parity.txt', env=env)
if rc:
    summary['checks']['parity'] = {'rc': rc, 'tail': out[-400:]}
    finish('the trainer leg did not run')
data = open(net, 'rb').read()
arch = models.arch_from_net('s512pp', data[netformat.HEADER_BYTES:])
unpacked = models.unpack(arch, data[netformat.HEADER_BYTES:])
base = {'l0w': [models.to_f32(x / models.QA) for x in unpacked['ftw']],
        'l0b': [models.to_f32(x / models.QA) for x in unpacked['ftb']]}
floats = netformat.read_weights_bin(open(inputs['parity-weights.bin'], 'rb').read())
r = {k: [models.to_f32(x) for x in v] for k, v in floats.items()}
worst, lines = 0.0, open(inputs['parity.sites'], encoding='utf-8').read().splitlines()
trainer = [list(map(float, t.split())) for t in open(f'{RESULT}/parity/trainer-parity.txt').read().splitlines()]
for line, t in zip(lines, trainer):
    fen, base_eval = line.split(' | ')[:2]
    y = models.refiner_float(arch, base, r, chess.Board(fen), int(base_eval), 8)
    worst = max(worst, abs(y[0] - t[0]), abs(y[1] - t[1]))
summary['checks']['parity'] = {'sites': len(lines), 'lines': len(trainer), 'worst': worst, 'seconds': secs}
save()
if len(trainer) != len(lines) or worst > 0.0002:
    finish(f'the trainer leg: worst difference {worst} over {len(trainer)} of {len(lines)} lines')

# 2. A1.
rc, out, secs = sh(f'{ft} train --arch refiner --base-weights {net} --sites {inputs["train.sites"]} '
                   f'--val-sites {inputs["val.sites"]} --superbatches 0 --scale {SCALE} --cap {CAP} '
                   f'--out {RESULT}/parity/a1', env=env)
open(f'{RESULT}/parity/a1.log', 'w').write(out)
m = re.search(r'superbatch 0 validation loss (\S+), the base\'s own (\S+) \(difference (\S+)\)', out)
summary['checks']['a1'] = {'rc': rc, 'loss': m and float(m.group(1)), 'base': m and float(m.group(2)),
                           'seconds': secs}
mu = re.search(r'mu = (\S+) cp', out)
summary['mu'] = mu and float(mu.group(1))
save()
if rc or not m or abs(float(m.group(1)) - float(m.group(2))) > 1e-6:
    finish('A1: the initial validation loss is not the base\'s own within 1e-6')

# The plain arm's and the curve's files.
with open(f'{WORK}/plain.sites', 'w') as f:
    for line in open(inputs['train.sites'], encoding='utf-8'):
        p = line.rstrip('\n').split(' | ')
        p[3] = '1.000000' if float(p[3]) > 0 else '0.000000'
        f.write(' | '.join(p) + '\n')
train_lines = open(inputs['train.sites'], encoding='utf-8').read().splitlines()
order = list(range(len(train_lines)))
random.Random(20261108).shuffle(order)
files = {'train': inputs['train.sites'], 'plain': f'{WORK}/plain.sites'}
for run, a in RUNS.items():
    if isinstance(a['sites'], int):
        files[run] = f'{WORK}/{run}.sites'
        with open(files[run], 'w') as f:
            for i in sorted(order[:a['sites']]):
                f.write(train_lines[i] + '\n')
del train_lines
used = {'seconds': 0.0, 'rate': None}   # finished runs' GPU-seconds; seconds per superbatch per million sites


def queue(device, runs):
    """One GPU's runs in order; a curve run is dropped if it would pass the GPU-time budget."""
    for run in runs:
        a = RUNS[run]
        path = files[run] if run in files else files[a['sites']]
        n = sum(1 for _ in open(path, encoding='utf-8'))
        if a.get('curve'):
            with lock:
                rate = used['rate']
                estimate = rate * n / 1e6 * SUPERBATCHES if rate else 0.0
                if used['seconds'] + estimate > BUDGET:
                    summary['dropped'].append({'run': run, 'used': used['seconds'], 'estimate': estimate})
                    save()
                    continue
        out_dir = f'{RESULT}/{run}'
        t = time.time()
        rc, out, secs = sh(f'{ft} train --arch refiner --base-weights {net} --sites {path} '
                           f'--val-sites {inputs["val.sites"]} {stage_args(run, device)} --out {out_dir}', env=env)
        open(f'{out_dir}/train.log', 'w').write(out)
        val = [tuple(map(float, x.split())) for x in open(f'{out_dir}/val.txt').read().splitlines()] \
            if os.path.exists(f'{out_dir}/val.txt') else []
        trained = [v for v in val if v[0] > 0]
        best = min(trained, key=lambda v: v[1]) if trained else None
        info = {'rc': rc, 'seconds': secs, 'sites': n, 'superbatches': len(trained), 'val': val,
                'best': best and {'superbatch': int(best[0]), 'loss': best[1]}}
        if best:
            os.makedirs(f'{out_dir}/best', exist_ok=True)
            shutil.copy(f'{out_dir}/refiner-{int(best[0])}/optimiser_state/weights.bin', f'{out_dir}/best/weights.bin')
            for d in glob.glob(f'{out_dir}/refiner-*'):
                shutil.rmtree(d)
            rc2, out2, secs2 = sh(f'{ft} eval --arch refiner --base-weights {net} --weights {out_dir}/best/weights.bin '
                                  f'--sites {inputs["val.sites"]} --out {out_dir}/eval-val.txt --device {device}', env=env)
            info['eval'] = {'rc': rc2, 'seconds': secs2}
        json.dump({'run': run, **a, **info}, open(f'{out_dir}/run.json', 'w'), indent=1)
        with lock:
            summary['runs'][run] = info
            used['seconds'] += time.time() - t
            if not a.get('curve') and trained and used['rate'] is None:
                used['rate'] = secs / len(trained) / (n / 1e6)
        save()


threads = [threading.Thread(target=lambda q=q, runs=runs: queue(q, runs)) for q, runs in enumerate(QUEUES)]
for th in threads:
    th.start()
for th in threads:
    th.join()

# 4. The cap, and each run's gate net flips.
try:
    windows = [json.loads(x) for x in open(inputs['val-windows.jsonl'], encoding='utf-8')]

    def score(run, cap):
        """Per inside-gate site: (weight, gate flip, reverse-futility flip, futility flip), each -1, 0 or 1
        (None at quiescence sites for the last two)."""
        ys = [float(x.split()[0]) for x in open(f'{RESULT}/{run}/eval-val.txt').read().splitlines()]
        out = []
        for w, y in zip(windows, ys):
            if w['weight'] <= 0:
                continue
            b, d, delta = w['base'], w['label'], max(-cap, min(cap, y * SCALE))
            near = min((abs(b - x), side, x) for side, x in (('alpha', w['alpha']), ('beta', w['beta'])) if abs(x) < 29250)
            above = (lambda x: x >= near[2]) if near[1] == 'beta' else (lambda x: x > near[2])

            flip = lambda test, x, z: int(test(x) != test(d) and test(z) == test(d)) - \
                int(test(x) == test(d) and test(z) != test(d))  # noqa: E731
            g = flip(above, b, b + delta)
            if w['kind'] == 0:
                pe = w['prune_eval']
                rf = flip(lambda x: x - 80 >= w['beta'], pe, pe + delta)
                fu = flip(lambda x: x + 100 + 70 <= w['alpha'], pe, pe + delta)
            else:
                rf = fu = None
            out.append((w['weight'], g, rf, fu))
        return out

    by_cap = {57: 'w1-c57', 198: 'w1', 480: 'w1-c480'}
    terms = {}
    for cap in CAPS:
        if os.path.exists(f'{RESULT}/{by_cap[cap]}/eval-val.txt'):
            c = score(by_cap[cap], cap)
            w_all, w_main = sum(x[0] for x in c), sum(x[0] for x in c if x[2] is not None)
            # Each site's share of the score: the gate's net flip over all sites, the thresholds' over main search.
            terms[cap] = [x[0] * (x[1] / w_all + ((x[2] + x[3]) / w_main if x[2] is not None else 0.0)) for x in c]
    summary['cap']['scores'] = {cap: sum(t) for cap, t in terms.items()}
    if len(terms) == 3:
        current = 57
        for larger in (198, 480):
            diff = [a - b for a, b in zip(terms[larger], terms[current])]
            n = len(diff)
            mean = sum(diff) / n
            se = math.sqrt(sum((x - mean) ** 2 for x in diff) * n / (n - 1))
            summary['cap'][f'{larger} vs {current}'] = {'difference': sum(diff), 'se': se}
            if sum(diff) > se:
                current = larger
        summary['cap']['chosen'] = current
    for run in RUNS:
        if os.path.exists(f'{RESULT}/{run}/eval-val.txt'):
            c = score(run, RUNS[run]['cap'])
            summary['gate_nf'][run] = sum(x[0] * x[1] for x in c) / sum(x[0] for x in c)
    for run in ('l125k', 'l250k', 'l500k', 'w1'):
        if summary['runs'].get(run, {}).get('best'):
            summary['curve'][run] = summary['runs'][run]['best']['loss']
except Exception:
    summary['analysis_error'] = traceback.format_exc()[-800:]
save()
print(json.dumps({k: summary[k] for k in ('checks', 'cap', 'gate_nf', 'curve', 'dropped')}, indent=1))
