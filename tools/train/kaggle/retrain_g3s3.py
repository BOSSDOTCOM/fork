# SPDX-License-Identifier: GPL-3.0-or-later

"""Item 8a: the default network's retrain on g3s3 (owner, 2026-11-07; DESIGN.md §6 decision 10; the think tank's
synthesis §5), on Kaggle (GPU T4 x2). Adapted from item 7's retrain_g3s2.py. Architecture s512pp (S512ppr2's),
every arm warm from S512ppr2's float weights (item 7's run s512pp-warm-s1, superbatch 352), S = 92, result weight
0.5, AdamW, batch 16,384 x 305 per superbatch, read interleaved (fork-train --interleave), validation g3s3-val.vf
(its first 20,000 positions per superbatch, for monitoring).

Arms (declared before the run):
- R1, R2, the control: the owner's standard recipe unchanged (LR 0.0001, tenfold drop after superbatch 180, 360
  superbatches, the best checkpoint by validation loss), seeds 1 and 2. Kept besides the best: the superbatch-180
  and superbatch-360 checkpoints with optimiser state, and the float weights of superbatches 331-360 (R1-avg is
  their mean).
- CD, the cooldown branch: resumes R1's superbatch-180 checkpoint (weights and AdamW moments); 20 superbatches at
  1e-5, 15 at 3e-6, 15 at 1e-6, each stage a constant-LR resume (a huge --lr-step) of the previous stage's last
  checkpoint; CD-avg is the mean of the last 15 (superbatches 216-230). No trainer change. Known property: each
  resume restarts the data stream at its beginning (the trainer has no skip option), so CD reads the first
  superbatches' games of the interleaved stream again in each stage; each stage gets its own --seed (11, 12, 13)
  so the shuffle differs (owner, 2026-11-07).
- D1, anneal only (information; owner, 2026-11-07: it runs): S512ppr2 at 1e-5 for 60 superbatches, no 1e-4
  phase; seed 1. Its last 15 superbatches' float weights are kept too (D1-avg, information only).
No recency arm (no deep-label gold set exists) and no high-WDL branch (later, on the finished candidate).
GPU 0 runs R1 then CD; GPU 1 runs R2 then D1.

Offline scoring (after training, device 0): S512ppr2 and each candidate on all of g3s3-val.vf's kept positions
(fork-train train --superbatches 0 --val-positions 10^9) and on its 20,000-position prefix. Averaged weights are
quantised by the trainer itself: a one-batch run at LR 0 from the averaged weights, whose checkpoint must hold the
same float weights byte for byte (checked), so its quantised.bin is the average's.

Decision rule (synthesis §5.5 with decision 10's wording; summary['decision'] applies it, the owner decides):
1. Validity: R1's, R2's and D1's superbatch 0 (S512ppr2 on g3s3-val's prefix) equal the warm-start check's value
   within 1e-6; R1's superbatch-180 weights re-scored equal R1's val.txt line 180 within 1e-6 (CD's start).
2. Candidate: R-best (the owner's rule: each seed's best checkpoint by the prefix, the lower seed) unless R1-avg
   or CD-avg is more than 1e-5 lower on the full set; then the lower of those. Never best-of-N.
3. Kill: the candidate's full-set loss not at least 2e-5 below S512ppr2's: no SPRT (wait for the next part).
4. Information only: D1 vs R1's window mean (superbatches 331-360) on the prefix (within 3e-5: propose the short
   recipe, with an equal endgame check; worse by more than 5e-5: the stable phase carries learning); CD-avg vs
   R1's window mean on the prefix (the noise-floor estimate).
The gates after the session (conversion, parity, netcheck, scale match, the endgame check at most 15 of 900, qloss,
the STC SPRT [0, 5] against S512ppr2) run locally, as item 7's did.

Layout: /kaggle/working/result/<run>/ (best/, ck-180/, ck-<last>/, window/<sb>.bin, val.txt, train.log, run.json),
result/avg-*/ (weights.bin, quantised.bin) for the offline step, the summary result/retrain.json.

    python3 retrain_g3s3.py           # on Kaggle (the kernel runs it without arguments)
    python retrain_g3s3.py --plan     # anywhere: prints the arms' commands and the settings, touches nothing
"""
import glob
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
import traceback

COMMIT = 'phase-4'          # replaced by the pushed commit's hash (holding g3g.json and g3s3.json) before the push
ARCH = 's512pp'
SCALE = 92                  # fit_scale.py on 2 M positions of the g3s3 mix: 88, inside 88-96 (synthesis §5.2)
RESULT_WEIGHT = 0.5
BATCH = 16384
BATCHES = 305
VAL_POSITIONS = 20000       # the per-superbatch monitoring prefix
ALL_POSITIONS = 10 ** 9     # offline scoring: every kept position of the validation file
NO_DROP = 10 ** 6           # an --lr-step no run reaches: a constant LR
MANIFESTS = ['data/manifests/g2s1.json', 'data/manifests/g3s1.json', 'data/manifests/g3b.json',
             'data/manifests/g3c.json', 'data/manifests/g3d.json', 'data/manifests/g3e.json',
             'data/manifests/g3s2.json', 'data/manifests/g3f.json', 'data/manifests/g3g.json',
             'data/manifests/g3s3.json']
VAL = 'g3s3-val.vf'
# S512ppr2's float weights (item 7's s512pp-warm-s1, superbatch 352), checked by reproducing its own validation
# loss on the file and prefix it was selected on.
INIT = {'weights': 's512ppr2-weights.bin',
        'sha256': '9bdf6f4910e40dfeb004c996683fb5fe43f1bcfe5ef0d2e8b701f73cc189b40c',
        'val': 'g3s2-val.vf', 'loss': 0.01908862}
TOLERANCE = 1e-6
TIE = 1e-5                  # decision 10: an averaged candidate must be more than this below R-best
KILL_MARGIN = 2e-5          # the candidate must be at least this below S512ppr2 on the full set
D1_SHORT, D1_LONG = 3e-5, 5e-5
ARMS = {
    'r1': {'seed': 1, 'init': True, 'stages': [(1, 360, 0.0001, 180)], 'keep': {180, 360}, 'window': (331, 360)},
    'r2': {'seed': 2, 'init': True, 'stages': [(1, 360, 0.0001, 180)], 'keep': {180, 360}, 'window': (331, 360)},
    'cd': {'seed': 1, 'resume': ('r1', 180), 'stage_seeds': (11, 12, 13),
           'stages': [(181, 200, 1e-5, NO_DROP), (201, 215, 3e-6, NO_DROP), (216, 230, 1e-6, NO_DROP)],
           'keep': {200, 215, 230}, 'window': (216, 230)},
    'd1': {'seed': 1, 'init': True, 'stages': [(1, 60, 1e-5, NO_DROP)], 'keep': {60}, 'window': (46, 60)},
}
QUEUES = [['r1', 'cd'], ['r2', 'd1']]   # per GPU: CD needs R1's superbatch-180 checkpoint
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


def stage_args(arm, i):
    """The trainer flags of one stage of an arm, without paths."""
    a = ARMS[arm]
    start, end, lr, step = a['stages'][i]
    seed = a.get('stage_seeds', [a['seed']] * len(a['stages']))[i]
    return (f'--start {start} --superbatches {end} --lr {lr} --lr-step {step} --seed {seed} '
            f'--patience {end + 1} --scale {SCALE} --result-weight {RESULT_WEIGHT} --batch {BATCH} '
            f'--batches {BATCHES} --interleave --val-positions {VAL_POSITIONS} --threads 2')


def plan():
    """--plan: the settings and every stage's command with placeholder paths; nothing is touched."""
    print(json.dumps({'commit': COMMIT, 'arch': ARCH, 'scale': SCALE, 'result_weight': RESULT_WEIGHT,
                      'manifests': MANIFESTS, 'val': VAL, 'init': INIT, 'queues': QUEUES}, indent=1))
    for q, arms in enumerate(QUEUES):
        for arm in arms:
            a = ARMS[arm]
            for i in range(len(a['stages'])):
                if i == 0 and 'resume' in a:
                    src_arm, src_sb = a['resume']
                    src = f'--resume <result>/{src_arm}/ck-{src_sb} (from <run-{src_arm}>/s512pp-{src_arm}-{src_sb})'
                elif i > 0:
                    src = f'--resume <run-{arm}>/s512pp-{arm}-{a["stages"][i - 1][1]}'
                else:
                    src = f'--init-weights <{INIT["weights"]}>'
                print(f'GPU {q} {arm} stage {i + 1}: fork-train train --arch {ARCH} --buckets <s512pp.json table> '
                      f'--data <101 training files> --val <{VAL}> {stage_args(arm, i)} {src} --device {q} '
                      f'--id s512pp-{arm} --out <run-{arm}>')
            print(f'   keep full: {sorted(a["keep"])} + best; window weights: {a["window"]}')
    print('offline: fork-train train ... --init-weights W --superbatches 0 --val-positions '
          f'{ALL_POSITIONS} (and {VAL_POSITIONS}) for S512ppr2, R1-best, R2-best, R1-avg, CD-avg, D1-final, D1-avg')


if __name__ == '__main__' and '--plan' in sys.argv:
    plan()
    sys.exit(0)
if __name__ == '__main__' and ('--help' in sys.argv or '-h' in sys.argv):
    print(__doc__)
    sys.exit(0)
if not os.path.isdir(DATA):
    sys.exit(f'{DATA} not found: this script runs inside the Kaggle session (use --plan to print the arms)')

os.makedirs(WORK, exist_ok=True)
os.makedirs(RESULT, exist_ok=True)
home = os.path.expanduser('~')
env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
       'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
settings = {'commit': COMMIT, 'arch': ARCH, 'arms': {k: {**v, 'keep': sorted(v['keep'])} for k, v in ARMS.items()},
            'queues': QUEUES, 'scale': SCALE, 'result_weight': RESULT_WEIGHT, 'batch': BATCH, 'batches': BATCHES,
            'val_positions': VAL_POSITIONS, 'manifests': MANIFESTS, 'val': VAL, 'interleave': True, 'init': INIT,
            'tie': TIE, 'kill_margin': KILL_MARGIN}
summary = {'settings': settings, 'checks': {}, 'runs': {}, 'offline': {}}
lock = threading.Lock()


def save():
    with lock:
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
rc_pip, out_pip, _ = sh('python3 -m pip install -q chess==1.11.2')
summary['pip'] = {'rc': rc_pip, 'tail': out_pip[-200:]}
train = f'{repo}/tools/train/target/release/fork-train'
desc = json.load(open(f'{repo}/tools/nnue/{ARCH}.json')) if built else {'table': []}
SPEC = f'--arch {ARCH} --buckets ' + ','.join(map(str, desc['table']))
found = sorted(glob.glob(f'{DATA}/**/*.vf', recursive=True))
by_name = {}
twice = []
for p in found:
    twice += [os.path.basename(p)] if os.path.basename(p) in by_name else []
    by_name.setdefault(os.path.basename(p), p)
# The storage rule (DESIGN.md §5.3, deliverable 3): every mounted shard matches its sealed manifest's SHA-256.
sealed = {}
for m in MANIFESTS:
    for b in json.load(open(f'{repo}/{m}'))['batches']:
        for s in b:
            sealed[s['file']] = s['sha256']
mismatch = [n for n, p in by_name.items() if sealed.get(n) != sha256(p)]
missing = sorted(set(sealed) - set(by_name))
summary['hash_check'] = {'shards': len(found), 'sealed': len(sealed), 'mismatches': mismatch, 'missing': missing,
                         'names_twice': twice}
shards = [p for n, p in sorted(by_name.items()) if not n.endswith('-val.vf')]
init = glob.glob(f'{DATA}/**/{INIT["weights"]}', recursive=True)
init_ok = len(init) == 1 and sha256(init[0]) == INIT['sha256']
summary['init_weights'] = {'found': len(init), 'sha256_ok': init_ok}
ok = built and rc_pip == 0 and not mismatch and not missing and not twice and len(found) == len(sealed) \
    and shards and VAL in by_name and INIT['val'] in by_name and init_ok
summary['training_shards'] = len(shards)
save()


def score(weights, val, positions, out_dir, device=0):
    """A float weights file's validation loss (superbatch 0 of a --superbatches 0 run)."""
    shutil.rmtree(out_dir, ignore_errors=True)
    rc, out, secs = sh(f'{train} train {SPEC} --data {shards[0]} --val {val} --val-positions {positions} '
                       f'--scale {SCALE} --result-weight {RESULT_WEIGHT} --init-weights {weights} --superbatches 0 '
                       f'--device {device} --threads 2 --out {out_dir}', env=env)
    loss = None
    if rc == 0 and os.path.exists(f'{out_dir}/val.txt'):
        first = open(f'{out_dir}/val.txt').readline().split()
        loss = float(first[1]) if first and first[0] == '0' else None
    return {'rc': rc, 'loss': loss, 'seconds': secs, 'tail': '' if loss is not None else out[-300:]}


def feature_checks():
    """fork-train check, and the feature leg against tools/nnue/reference.py."""
    res = {}
    rc, out, _ = sh(f'{train} check {SPEC} --out {WORK}/check-{ARCH}', env=env)
    res['check'] = {'rc': rc, 'out': out[-300:]}
    legs = []
    for src in (f'--epd {repo}/tests/nnue/parity.epd', f'--data {by_name[VAL]} --count 5000'):
        feats = f'{WORK}/features-{ARCH}-{len(legs)}.txt'
        rc1, out1, _ = sh(f'{train} features {SPEC} {src} > {feats}', env=env)
        rc2, out2, _ = sh(f'python3 {repo}/tools/nnue/reference.py features --rust {feats} '
                          f'--layout {repo}/tools/nnue/{ARCH}.json')
        legs.append({'source': src.split()[0], 'features_rc': rc1, 'leg_rc': rc2, 'leg': out2.strip()[-300:]})
    res['feature_legs'] = legs
    res['ok'] = rc == 0 and all(l['features_rc'] == 0 and l['leg_rc'] == 0 for l in legs)
    return res


if ok:
    c = feature_checks()
    if c['ok']:
        # The weights file is S512ppr2's: its own loss on the file and prefix it was selected on.
        c['warm_start'] = score(init[0], by_name[INIT['val']], VAL_POSITIONS, f'{WORK}/init-check')
        c['ok'] = c['warm_start']['loss'] is not None and abs(c['warm_start']['loss'] - INIT['loss']) <= TOLERANCE
        # The value every warm arm's superbatch 0 must reproduce (validity rule 1).
        c['warm_start_g3s3'] = score(init[0], by_name[VAL], VAL_POSITIONS, f'{WORK}/init-g3s3')
        c['ok'] = c['ok'] and c['warm_start_g3s3']['loss'] is not None
    summary['checks'][ARCH] = c
    ok = c['ok']
    save()


def checkpoints(arm, out_dir):
    """{superbatch: folder} of the run's complete checkpoints (superbatch.txt is written last)."""
    done = {}
    for d in glob.glob(f'{out_dir}/s512pp-{arm}-*'):
        tail = d.rsplit('-', 1)[1]
        if tail.isdigit() and os.path.exists(f'{d}/superbatch.txt'):
            done[int(tail)] = d
    return done


def curve_of(out_dir):
    curve = []
    if os.path.exists(f'{out_dir}/val.txt'):
        for line in open(f'{out_dir}/val.txt'):
            # Complete lines only (a line still being written can parse short).
            if line.endswith('\n') and len(line.split()) == 2:
                curve.append((int(line.split()[0]), float(line.split()[1])))
    return curve


def prune(arm, out_dir, final=False):
    """Keeps the declared checkpoints (ARMS keep), the best so far by validation loss (superbatch 0, the initial
    weights, is never the result) and, while training, the two newest; copies each window superbatch's float
    weights to window/<sb>.bin before its folder can go."""
    a = ARMS[arm]
    done = checkpoints(arm, out_dir)
    os.makedirs(f'{out_dir}/window', exist_ok=True)
    keep = set(a['keep'])
    if not final:
        keep |= set(sorted(done)[-2:])
    trained = [c for c in curve_of(out_dir) if c[0] > 0]
    if trained:
        keep.add(min(trained, key=lambda c: c[1])[0])
    lo, hi = a['window']
    for sb, d in done.items():
        if lo <= sb <= hi and not os.path.exists(f'{out_dir}/window/{sb}.bin'):
            shutil.copy(f'{d}/optimiser_state/weights.bin', f'{out_dir}/window/{sb}.bin.part')
            os.replace(f'{out_dir}/window/{sb}.bin.part', f'{out_dir}/window/{sb}.bin')
        if sb not in keep and (not (lo <= sb <= hi) or os.path.exists(f'{out_dir}/window/{sb}.bin')):
            shutil.rmtree(d, ignore_errors=True)


def run_arm(arm, device):
    """Runs an arm's stages one after another on one GPU, pruning every minute; returns its record."""
    a = ARMS[arm]
    out_dir = f'{WORK}/run-{arm}'
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    began = time.time()
    record = {'arm': arm, 'device': device, 'stages': []}
    for i, (start, end, lr, step) in enumerate(a['stages']):
        if i == 0 and 'resume' in a:
            src_arm, src_sb = a['resume']
            src = f'--resume {RESULT}/{src_arm}/ck-{src_sb}'
        elif i > 0:
            src = f'--resume {out_dir}/s512pp-{arm}-{a["stages"][i - 1][1]}'
        else:
            src = f'--init-weights {init[0]}'
        cmd = (f'{train} train {SPEC} --data {" ".join(shards)} --val {by_name[VAL]} {stage_args(arm, i)} {src} '
               f'--device {device} --id s512pp-{arm} --out {out_dir} >> {out_dir}/train.log 2>&1')
        t = time.time()
        proc = subprocess.Popen(cmd, shell=True, env={**os.environ, **env})
        while proc.poll() is None:
            prune(arm, out_dir)
            time.sleep(60)
        record['stages'].append({'start': start, 'end': end, 'lr': lr, 'rc': proc.returncode,
                                 'seconds': round(time.time() - t, 1)})
        if proc.returncode != 0:
            break
    prune(arm, out_dir, final=True)
    record['seconds'] = round(time.time() - began, 1)
    curve = curve_of(out_dir)
    record['val_curve'] = curve
    record['initial_loss'] = curve[0][1] if curve and curve[0][0] == 0 else None
    trained = [c for c in curve if c[0] > 0]
    record['positions_per_second'] = round(BATCH * BATCHES * len(trained) / record['seconds']) if trained else None
    dest = f'{RESULT}/{arm}'
    os.makedirs(dest, exist_ok=True)
    done = checkpoints(arm, out_dir)
    if trained:
        sb, best = min(trained, key=lambda c: c[1])
        record['kept_superbatch'], record['best_loss'] = sb, best
        lo, hi = a['window']
        win = [l for s, l in trained if lo <= s <= hi]
        record['window_mean'] = sum(win) / len(win) if len(win) == hi - lo + 1 else None
        # The best checkpoint whole (optimiser state included), its float weights also beside quantised.bin.
        shutil.copytree(done[sb], f'{dest}/best', dirs_exist_ok=True)
        shutil.copy(f'{done[sb]}/optimiser_state/weights.bin', f'{dest}/best/weights.bin')
        for k in sorted(a['keep']):
            if k in done:  # the whole checkpoint, optimiser state included (CD resumes R1's ck-180)
                shutil.copytree(done[k], f'{dest}/ck-{k}', dirs_exist_ok=True)
        shutil.copytree(f'{out_dir}/window', f'{dest}/window', dirs_exist_ok=True)
        record['window_kept'] = len(os.listdir(f'{dest}/window'))
        shutil.copy(f'{out_dir}/val.txt', f'{dest}/val.txt')
    shutil.copy(f'{out_dir}/train.log', f'{dest}/train.log')
    json.dump(record, open(f'{dest}/run.json', 'w'), indent=1)
    shutil.rmtree(out_dir, ignore_errors=True)
    return record


def queue(arms, device):
    for arm in arms:
        if 'resume' in ARMS[arm]:
            src_arm, src_sb = ARMS[arm]['resume']
            if not os.path.isdir(f'{RESULT}/{src_arm}/ck-{src_sb}/optimiser_state'):
                with lock:
                    summary['runs'][arm] = {'arm': arm, 'error': f'{src_arm} superbatch {src_sb} checkpoint missing'}
                save()
                continue
        try:
            rec = run_arm(arm, device)
        except Exception:  # recorded, and the other arms go on
            rec = {'arm': arm, 'error': traceback.format_exc()[-2000:]}
        with lock:
            summary['runs'][arm] = rec
        save()


def read_records(path):
    """bullet's weights.bin as [(name, count, offset)] and its bytes (records: ASCII name, 0x0A, u64 count, f32s)."""
    data = open(path, 'rb').read()
    out, at = [], 0
    while at < len(data):
        nl = data.index(b'\n', at)
        (n,) = struct.unpack_from('<Q', data, nl + 1)
        out.append((data[at:nl], n, nl + 9))
        at = nl + 9 + 4 * n
    return out, data


def average_weights(paths, out_path):
    """The elementwise mean of float weights files of one architecture, in the first file's record layout
    (sums in double precision, the mean rounded once to f32; plain Python, so it also runs on a CPU machine)."""
    from array import array
    assert sys.byteorder == 'little'
    layout, _ = read_records(paths[0])
    sums = [array('d', bytes(8 * n)) for _, n, _ in layout]
    for p in paths:
        lay, data = read_records(p)
        assert [(a, b) for a, b, _ in lay] == [(a, b) for a, b, _ in layout], p
        for k, (_, n, off) in enumerate(lay):
            x = array('f', data[off:off + 4 * n])
            acc = sums[k]
            for i in range(n):
                acc[i] += x[i]
    out = bytearray()
    for (name, n, _), acc in zip(layout, sums):
        out += name + b'\n' + struct.pack('<Q', n) + array('f', [v / len(paths) for v in acc]).tobytes()
    open(out_path, 'wb').write(bytes(out))


def quantise(weights, out_dir, device=0):
    """The trainer's own quantised.bin of a float weights file: one batch at LR 0, whose checkpoint must hold the
    same float weights byte for byte."""
    shutil.rmtree(out_dir, ignore_errors=True)
    rc, out, _ = sh(f'{train} train {SPEC} --data {shards[0]} --scale {SCALE} --result-weight {RESULT_WEIGHT} '
                    f'--init-weights {weights} --lr 0 --batch {BATCH} --batches 1 --superbatches 1 --seed 1 '
                    f'--device {device} --threads 2 --id q --out {out_dir}', env=env)
    ck = f'{out_dir}/q-1'
    same = rc == 0 and os.path.exists(f'{ck}/optimiser_state/weights.bin') and \
        open(f'{ck}/optimiser_state/weights.bin', 'rb').read() == open(weights, 'rb').read()
    return {'rc': rc, 'unchanged': same, 'quantised': f'{ck}/quantised.bin' if same else None,
            'tail': '' if same else out[-300:]}


def offline():
    """Averages, quantises and scores every candidate on the full validation set and its prefix."""
    res = summary['offline']
    nets = {'s512ppr2': init[0]}
    for arm in ('r1', 'r2'):
        if os.path.exists(f'{RESULT}/{arm}/best/weights.bin'):
            nets[f'{arm}-best'] = f'{RESULT}/{arm}/best/weights.bin'
    if os.path.exists(f'{RESULT}/d1/ck-60/optimiser_state/weights.bin'):
        nets['d1-final'] = f'{RESULT}/d1/ck-60/optimiser_state/weights.bin'
    for arm in ('r1', 'cd', 'd1'):
        lo, hi = ARMS[arm]['window']
        win = [f'{RESULT}/{arm}/window/{sb}.bin' for sb in range(lo, hi + 1)]
        if all(os.path.exists(p) for p in win):
            dest = f'{RESULT}/avg-{arm}'
            os.makedirs(dest, exist_ok=True)
            average_weights(win, f'{dest}/weights.bin')
            q = quantise(f'{dest}/weights.bin', f'{WORK}/q-{arm}')
            res[f'quantise-{arm}'] = q
            if q['quantised']:
                shutil.copy(q['quantised'], f'{dest}/quantised.bin')
            # Scored either way (the score reads the float weights); without quantised.bin it cannot be converted.
            nets[f'{arm}-avg'] = f'{dest}/weights.bin'
    for name, w in nets.items():
        res[name] = {'full': score(w, by_name[VAL], ALL_POSITIONS, f'{WORK}/score-{name}'),
                     'prefix': score(w, by_name[VAL], VAL_POSITIONS, f'{WORK}/score-{name}-p')}
        if name != 's512ppr2':  # the trainer's float outputs on the parity positions, for the parity legs
            dest = f'{RESULT}/d1' if name == 'd1-final' else os.path.dirname(w)
            sh(f'{train} eval {SPEC} --weights {w} --epd {repo}/tests/nnue/parity.epd '
               f'--out {dest}/parity-trainer-{name}.txt', env=env)
        save()
    # CD's start: R1's superbatch-180 weights re-scored on the prefix against R1's own line 180.
    r1 = dict(summary['runs'].get('r1', {}).get('val_curve', []))
    if 180 in r1 and os.path.isdir(f'{RESULT}/r1/ck-180'):
        s = score(f'{RESULT}/r1/ck-180/optimiser_state/weights.bin', by_name[VAL], VAL_POSITIONS, f'{WORK}/score-180')
        res['r1-180-recheck'] = {'loss': s['loss'], 'val_txt': r1[180],
                                 'ok': s['loss'] is not None and abs(s['loss'] - r1[180]) <= TOLERANCE}
    save()


def full(name):
    return ((summary['offline'].get(name) or {}).get('full') or {}).get('loss')


def prefix(name):
    return ((summary['offline'].get(name) or {}).get('prefix') or {}).get('loss')


def decide():
    """The declared rule applied to the numbers; the owner decides."""
    d = {}
    ref = (summary['checks'].get(ARCH) or {}).get('warm_start_g3s3', {}).get('loss')
    starts = {arm: summary['runs'].get(arm, {}).get('initial_loss') for arm in ('r1', 'r2', 'd1')}
    d['validity'] = {'reference': ref, 'superbatch_0': starts,
                     'ok': ref is not None and all(v is not None and abs(v - ref) <= TOLERANCE for v in starts.values())
                     and (summary['offline'].get('r1-180-recheck') or {}).get('ok', False)}
    seeds = [(summary['runs'][a]['best_loss'], a) for a in ('r1', 'r2') if 'best_loss' in summary['runs'].get(a, {})]
    if len(seeds) == 2 and full('s512ppr2') is not None:
        rbest = f'{min(seeds)[1]}-best'
        chosen = rbest
        if full(rbest) is not None:
            better = [(full(n), n) for n in ('r1-avg', 'cd-avg') if full(n) is not None and full(n) < full(rbest) - TIE]
            if better:
                chosen = min(better)[1]
        d.update(r_best=rbest, candidate=chosen, candidate_full=full(chosen), s512ppr2_full=full('s512ppr2'),
                 candidates_full={n: full(n) for n in ('r1-best', 'r2-best', 'r1-avg', 'cd-avg')},
                 not_r_best=chosen != rbest)
        d['sprt'] = full(chosen) is not None and full(chosen) <= full('s512ppr2') - KILL_MARGIN
    r1w = summary['runs'].get('r1', {}).get('window_mean')
    d1w = summary['runs'].get('d1', {}).get('window_mean')
    info = {'r1_window_mean_prefix': r1w, 'd1_last15_mean_prefix': d1w, 'd1_final_prefix': prefix('d1-final'),
            'cd_avg_prefix': prefix('cd-avg'), 'r1_avg_prefix': prefix('r1-avg'),
            'd1_final_full': full('d1-final'), 'd1_avg_full': full('d1-avg')}
    if r1w is not None and d1w is not None:
        gap = d1w - r1w
        info['d1_minus_r1_window'] = gap
        info['d1_reading'] = ('within 3e-5: propose the short recipe (if the endgame check is equal)' if gap <= D1_SHORT
                              else 'worse by more than 5e-5: the stable phase carries learning' if gap > D1_LONG
                              else 'between: undecided')
    if r1w is not None and prefix('cd-avg') is not None:
        info['cd_avg_minus_r1_window'] = prefix('cd-avg') - r1w
    d['information'] = info
    summary['decision'] = d


try:
    if ok:
        threads = [threading.Thread(target=queue, args=(arms, dev)) for dev, arms in enumerate(QUEUES)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        offline()
        decide()
finally:
    # Even after a failure: the clone and its build would otherwise fill the session's output with thousands of files.
    shutil.rmtree(repo, ignore_errors=True)
    shutil.rmtree(WORK, ignore_errors=True)
save()
print(json.dumps(summary, indent=1))
