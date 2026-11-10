# SPDX-License-Identifier: GPL-3.0-or-later

"""Retrain 8b's idea 69 arm "cw" and a second control seed "c2" (owner, 2026-11-10: run idea 69's arm now as an extra 8b arm; docs/research/class-sampler/
design.md section 14), on Kaggle (GPU T4 x2, device 0). Made from retrain 8b's own kernel (tools/train/kaggle/retrain_8b.py at
8b's launch commit 320c0be) by one script, so everything but the arm is 8b's: architecture s512pp, S = 92, AdamW, batch
16,384 x 305 per superbatch, 360 superbatches, read interleaved, validation g4s1-val.vf (its first 20,000 positions per
superbatch, for monitoring only); the same 16 datasets, the same input checks (every file's SHA-256 against the manifests),
and the same offline step and validity record.

The arms (declared before any result):
- c2 (the owner's recommendation 7, 2026-11-10: a second control seed): arm c exactly with seed 2 (the data order; the
  warm start fixes the weights), on GPU 1 beside cw, as 8b ran its arms side by side. Not a candidate: gated, and baked
  only for the seed-noise head-to-head r8bc2 against r8bc beside cw's.
- cw: arm c's exact recipe (warm from S512ppr3's float weights, LR 0.0001 dropped tenfold after 180, seed 1, result weight
  0.5) on arm c's exact 129 files in the same order, plus --cell-weights TABLE (the table solved on arm c's own training
  files, the narrowed floor; its SHA-256 checked before anything trains) and --exempt with the 10 Syzygy slice files
  (weight 1, as every position has in c). The trainer is NEW's (8b's trainer plus idea 69's loss weights; the preflight
  cw_preflight.py checked that without a table, and with a table of ones, it trains as 8b's does). The candidate is
  cw-avg, the mean of superbatches 331-360's float weights, quantised by the trainer itself.

Validity (blocking; summary['validity']): 8b's (inputs, the warm start's g3s3-val prefix loss, cw's superbatch 0 equal to
S512ppr3's g4s1-val prefix loss within 1e-6: validation is unweighted), plus summary['cell_weights']: the table's path and
SHA-256, the exempt list (exactly the control list's slice files), the trainer commit.

Layout: /kaggle/working/result/cw/ (best/, ck-180/, ck-360/, window/, val.txt, train.log, run.json, files.json),
result/avg-cw/ (weights.bin, quantised.bin, parity-trainer-cw-avg.txt), the summary result/retrain.json.

    python3 retrain_8b_cw.py                      # on Kaggle
    python retrain_8b_cw.py --plan                # anywhere: the settings and the arm's command; touches nothing
    python retrain_8b_cw.py --check-inputs DIR... # anywhere: the input checks and the arm's file list
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

COMMIT = 'phase-4'          # replaced by the pushed commit's hash (the manifests, the new trainer, the table)
TABLE = 'docs/research/class-sampler/weights-r8b-c.txt'
TABLE_SHA256 = ''           # replaced by the committed table's SHA-256 before the push
EXEMPT = ['g3s2-slice1-00-rest.vf'] + [f'slice1-0{i}.vf' for i in range(1, 10)]   # the Syzygy slice: weight 1
ARCH = 's512pp'
SCALE = 92                  # 8a's recipe (fit_scale.py on g3s3's mix: 88, inside 88-96); the TD labels use it too
BATCH = 16384
BATCHES = 305
SUPERBATCHES = 360
VAL_POSITIONS = 20000       # the per-superbatch monitoring prefix
ALL_POSITIONS = 10 ** 9     # offline scoring: every kept position of a file
MANIFESTS = ['g2s1', 'g3s1', 'g3b', 'g3c', 'g3d', 'g3e', 'g3s2', 'g3f', 'g3g', 'g3s3',   # item 8a's inputs
             'g3h', 'g3i', 'g3j', 'g4',                                                  # the sealed parts since
             'g4s1-pre', 'r8b-blend', 'r8b-arms', 'r8b-g4']                             # 8b's derived files
VAL = 'g4s1-val.vf'
VAL_BLEND = 'bl-g4s1-val.vf'
NEWEST = ('g3j-', 'g4-', 'g4s1-g3j-', 'g4s1-g4-')    # S512ppr3's parts and their rests: the TD arms' TD copies
I52_POOL = ['g3j-w00.vf', 'g3j-w01.vf', 'g3j-w02.vf', 'g3j-w03.vf', 'g3j-w04.vf']
I52_SITES = 'i52-sites.vf'
EVAL_ONLY = ['i52-held.vf', 'i52-controls.vf']       # never trained: idea 52's held-out sites and the controls
# S512ppr3's float weights (item 8a's R1-avg), checked by reproducing their own g3s3-val prefix loss.
INIT = {'weights': 's512ppr3-weights.bin',
        'sha256': '022158587653ba32d5830ce4f6a3b7e1a88283e7cb9e3c507936ad0c8b37ecc3',
        'val': 'g3s3-val.vf', 'loss': 0.01960772}
TOLERANCE = 1e-6
TD_START_TOLERANCE = 1e-5
WINDOW = (331, 360)
KEEP = {180, 360}
ARMS = {
    'cw': {'files': 'control', 'init': True, 'lr': 0.0001, 'lr_step': 180, 'result_weight': 0.5, 'val': VAL,
           'cell_weights': True},
    'c2': {'files': 'control', 'init': True, 'lr': 0.0001, 'lr_step': 180, 'result_weight': 0.5, 'val': VAL,
           'seed': 2},
}
SEED = 1
QUEUES = [['cw'], ['c2']]
CANDIDATES = ['cw']
DATA = '/kaggle/input'
WORK = '/kaggle/working/retrain'
RESULT = '/kaggle/working/result'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def is_slice(name):
    return 'slice' in name


def is_derived(name):
    return name.startswith(('bl-', 'i52-')) or (name.startswith('td') and name[2:4].isdigit() and name[4] == '-')


def arm_files(kind, base):
    """An arm's training file names, from the control's (`base`): each substitution named in the module note."""
    if kind == 'control':
        return list(base)
    if kind == 'i52':
        return [f'i52-{n}' if n in I52_POOL else n for n in base] + [I52_SITES]
    if kind.startswith('td'):
        return [n if is_slice(n) else f'{kind}-{n}' if n.startswith(NEWEST) else f'bl-{n}' for n in base]
    raise ValueError(kind)


def resolve(found, sealed, hashes=True):
    """The input checks on {name: path} of the mounted .vf files: every file sealed (the manifests' SHA-256) and every
    sealed file mounted once; then the control's training files and each arm's list. Returns (record, lists)."""
    by_name, twice = {}, []
    for p in sorted(found):
        n = os.path.basename(p)
        twice += [n] if n in by_name else []
        by_name.setdefault(n, p)
    mismatch = [n for n, p in by_name.items() if n not in sealed or (hashes and sealed[n] != sha256(p))]
    missing = sorted(set(sealed) - set(by_name))
    base = sorted(n for n in by_name if not n.endswith('-val.vf') and not is_derived(n) and n not in EVAL_ONLY)
    lists, unresolved = {}, {}
    for arm, a in ARMS.items():
        names = arm_files(a['files'], base)
        lists[arm] = names
        unresolved[arm] = [n for n in names if n not in by_name] + ([a['val']] if a['val'] not in by_name else [])
    record = {'mounted': len(by_name), 'sealed': len(sealed), 'mismatches': mismatch, 'missing': missing,
              'names_twice': twice, 'unresolved': {k: v for k, v in unresolved.items() if v},
              'files_per_arm': {k: len(v) for k, v in lists.items()},
              'bytes_per_arm': {k: sum(os.path.getsize(by_name[n]) for n in v if n in by_name)
                                for k, v in lists.items()},
              'slice_files': sorted(n for n in base if is_slice(n))}
    record['ok'] = not (mismatch or missing or twice or record['unresolved']) and bool(base)
    return record, lists, by_name


def sealed_files(repo):
    sealed = {}
    for m in MANIFESTS:
        for b in json.load(open(f'{repo}/data/manifests/{m}.json'))['batches']:
            for s in b:
                sealed[s['file']] = s['sha256']
    return sealed


def stage_args(arm, val_path):
    a = ARMS[arm]
    return (f'--start 1 --superbatches {SUPERBATCHES} --lr {a["lr"]} --lr-step {a["lr_step"]} '
            f'--seed {a.get("seed", SEED)} '
            f'--patience {SUPERBATCHES + 1} --scale {SCALE} --result-weight {a["result_weight"]} --batch {BATCH} '
            f'--batches {BATCHES} --interleave --val {val_path} --val-positions {VAL_POSITIONS} --threads 2')


def weight_args(arm, repo):
    """Idea 69's options of an arm: the table and the exempt files (none for an arm without loss weights)."""
    if not ARMS[arm].get('cell_weights'):
        return ''
    return f'--cell-weights {repo}/{TABLE} --exempt {" ".join(EXEMPT)}'


def cell_checks(repo, names):
    """The table's SHA-256 and the exempt list against the arm's files: every exempt name is a training file of the
    arm, and the exempt files are exactly its slice files."""
    path = f'{repo}/{TABLE}'
    digest = sha256(path) if os.path.exists(path) else None
    slices = sorted(n for n in names if is_slice(n))
    rec = {'table': TABLE, 'sha256': digest, 'sha256_expected': TABLE_SHA256, 'exempt': EXEMPT,
           'arm_slice_files': slices, 'trainer_commit': COMMIT}
    rec['ok'] = digest is not None and digest == TABLE_SHA256 and sorted(EXEMPT) == slices
    return rec


def plan():
    """--plan: the settings and each arm's command with placeholder paths; nothing is touched."""
    print(json.dumps({'commit': COMMIT, 'arch': ARCH, 'scale': SCALE, 'manifests': MANIFESTS, 'init': INIT,
                      'queues': QUEUES, 'window': WINDOW, 'keep': sorted(KEEP), 'seed': SEED}, indent=1))
    for q, arms in enumerate(QUEUES):
        for arm in arms:
            a = ARMS[arm]
            src = f'--init-weights <{INIT["weights"]}>' if a['init'] else '(seeded random weights)'
            print(f'GPU {q} {arm}: fork-train train --arch {ARCH} --buckets <s512pp.json table> --data <{a["files"]} '
                  f'files> {stage_args(arm, "<" + a["val"] + ">")} {src} {weight_args(arm, "<repo>")} --device {q} '
                  f'--id s512pp-{arm} --out <run-{arm}>')
    print('offline: each arm\'s window mean, quantised; S512ppr3 and the candidates scored (result weight 0.5) on '
          f'{VAL} (all and the prefix), {EVAL_ONLY[0]} and {EVAL_ONLY[1]}')


def check_inputs(folders, repo):
    """--check-inputs: the session's input checks against local folders (each dataset's files, as Kaggle mounts
    them)."""
    found = [p for f in folders for p in glob.glob(f'{f}/**/*.vf', recursive=True)]
    record, lists, by_name = resolve(found, sealed_files(repo))
    init = [p for f in folders for p in glob.glob(f'{f}/**/{INIT["weights"]}', recursive=True)]
    record['init_weights'] = {'found': len(init), 'sha256_ok': len(init) == 1 and sha256(init[0]) == INIT['sha256']}
    print(json.dumps(record, indent=1))
    for arm, names in lists.items():
        print(arm, len(names), 'files;', ', '.join(names[:3]), '...', ', '.join(names[-3:]))
    return 0 if record['ok'] and record['init_weights']['sha256_ok'] else 1


def sh(cmd, env=None, timeout=12 * 3600):
    t = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr), round(time.time() - t, 1)


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
    """The elementwise mean of float weights files of one architecture (8a's: sums in double precision, the mean
    rounded once to f32)."""
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


def session():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(RESULT, exist_ok=True)
    home = os.path.expanduser('~')
    env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
           'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
    settings = {'commit': COMMIT, 'arch': ARCH, 'arms': ARMS, 'queues': QUEUES, 'scale': SCALE, 'batch': BATCH,
                'batches': BATCHES, 'superbatches': SUPERBATCHES, 'val_positions': VAL_POSITIONS,
                'manifests': MANIFESTS, 'init': INIT, 'window': WINDOW, 'keep': sorted(KEEP), 'seed': SEED}
    summary = {'settings': settings, 'checks': {}, 'runs': {}, 'offline': {}}
    lock = threading.Lock()

    def save():
        with lock:
            json.dump(summary, open(f'{RESULT}/retrain.json', 'w'), indent=1)

    rc, _, _ = sh('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal')
    summary['rustup'] = rc
    repo = f'{WORK}/fork'
    rc, out, _ = sh(f'cd {WORK} && rm -rf fork && git clone -q https://github.com/BOSSDOTCOM/fork && cd fork && '
                    f'git checkout -q {COMMIT} && git log --oneline -1')
    summary['head'] = out.strip()[-120:]
    rc, out, secs = sh(f'cd {repo}/tools/train && cargo build --release --locked --features cuda', env=env)
    summary['build'] = {'rc': rc, 'seconds': secs, 'tail': out[-400:] if rc else ''}
    built = rc == 0
    train = f'{repo}/tools/train/target/release/fork-train'
    desc = json.load(open(f'{repo}/tools/nnue/{ARCH}.json')) if built else {'table': []}
    spec = f'--arch {ARCH} --buckets ' + ','.join(map(str, desc['table']))
    record, lists, by_name = resolve(glob.glob(f'{DATA}/**/*.vf', recursive=True), sealed_files(repo))
    summary['inputs'] = record
    init = glob.glob(f'{DATA}/**/{INIT["weights"]}', recursive=True)
    init_ok = len(init) == 1 and sha256(init[0]) == INIT['sha256']
    summary['init_weights'] = {'found': len(init), 'sha256_ok': init_ok}
    ok = built and record['ok'] and init_ok and INIT['val'] in by_name
    summary['cell_weights'] = cell_checks(repo, lists['cw']) if built else {'ok': False}
    ok = ok and summary['cell_weights']['ok']
    save()

    def score(weights, val, positions, out_dir, result_weight=0.5, device=0, extra=''):
        """A float weights file's loss on a file (superbatch 0 of a --superbatches 0 run)."""
        shutil.rmtree(out_dir, ignore_errors=True)
        rc, out, secs = sh(f'{train} train {spec} --data {by_name[lists["cw"][0]]} --val {val} '
                           f'--val-positions {positions} --scale {SCALE} --result-weight {result_weight} '
                           f'--init-weights {weights} --superbatches 0 --device {device} --threads 2 --out {out_dir} '
                           f'{extra}',
                           env=env)
        loss = None
        if rc == 0 and os.path.exists(f'{out_dir}/val.txt'):
            first = open(f'{out_dir}/val.txt').readline().split()
            loss = float(first[1]) if first and first[0] == '0' else None
        return {'rc': rc, 'loss': loss, 'seconds': secs, 'tail': '' if loss is not None else out[-300:]}

    if ok:
        c = {}
        rc, out, _ = sh(f'{train} check {spec} --out {WORK}/check-{ARCH}', env=env)
        c['check'] = {'rc': rc, 'out': out[-300:]}
        c['warm_start'] = score(init[0], by_name[INIT['val']], VAL_POSITIONS, f'{WORK}/init-check')
        c['reference'] = score(init[0], by_name[VAL], VAL_POSITIONS, f'{WORK}/init-ref')
        c['ok'] = rc == 0 and c['warm_start']['loss'] is not None and \
            abs(c['warm_start']['loss'] - INIT['loss']) <= TOLERANCE and c['reference']['loss'] is not None
        summary['checks'] = c
        ok = c['ok']
        save()

    def checkpoints(arm, out_dir):
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
                if line.endswith('\n') and len(line.split()) == 2:
                    curve.append((int(line.split()[0]), float(line.split()[1])))
        return curve

    def prune(arm, out_dir, final=False):
        """8a's: keeps KEEP, the best so far, the two newest while training; window weights copied first."""
        done = checkpoints(arm, out_dir)
        os.makedirs(f'{out_dir}/window', exist_ok=True)
        keep = set(KEEP)
        if not final:
            keep |= set(sorted(done)[-2:])
        trained = [c for c in curve_of(out_dir) if c[0] > 0]
        if trained:
            keep.add(min(trained, key=lambda c: c[1])[0])
        lo, hi = WINDOW
        for sb, d in done.items():
            if lo <= sb <= hi and not os.path.exists(f'{out_dir}/window/{sb}.bin'):
                shutil.copy(f'{d}/optimiser_state/weights.bin', f'{out_dir}/window/{sb}.bin.part')
                os.replace(f'{out_dir}/window/{sb}.bin.part', f'{out_dir}/window/{sb}.bin')
            if sb not in keep and (not (lo <= sb <= hi) or os.path.exists(f'{out_dir}/window/{sb}.bin')):
                shutil.rmtree(d, ignore_errors=True)

    def run_arm(arm, device):
        a = ARMS[arm]
        out_dir = f'{WORK}/run-{arm}'
        shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir)
        dest = f'{RESULT}/{arm}'
        os.makedirs(dest, exist_ok=True)
        files = [by_name[n] for n in lists[arm]]
        json.dump({'files': lists[arm], 'val': a['val']}, open(f'{dest}/files.json', 'w'), indent=1)
        src = f'--init-weights {init[0]}' if a['init'] else ''
        cmd = (f'{train} train {spec} --data {" ".join(files)} {stage_args(arm, by_name[a["val"]])} {src} '
               f'{weight_args(arm, repo)} '
               f'--device {device} --id s512pp-{arm} --out {out_dir} >> {out_dir}/train.log 2>&1')
        began = time.time()
        proc = subprocess.Popen(cmd, shell=True, env={**os.environ, **env})
        while proc.poll() is None:
            prune(arm, out_dir)
            time.sleep(60)
        prune(arm, out_dir, final=True)
        rec = {'arm': arm, 'device': device, 'rc': proc.returncode, 'seconds': round(time.time() - began, 1),
               'files': len(files)}
        curve = curve_of(out_dir)
        rec['val_curve'] = curve
        rec['initial_loss'] = curve[0][1] if curve and curve[0][0] == 0 else None
        trained = [c for c in curve if c[0] > 0]
        rec['positions_per_second'] = round(BATCH * BATCHES * len(trained) / rec['seconds']) if trained else None
        done = checkpoints(arm, out_dir)
        if trained:
            sb, best = min(trained, key=lambda c: c[1])
            rec['best_superbatch'], rec['best_loss'] = sb, best
            lo, hi = WINDOW
            win = [l for s, l in trained if lo <= s <= hi]
            rec['window_mean'] = sum(win) / len(win) if len(win) == hi - lo + 1 else None
            shutil.copytree(done[sb], f'{dest}/best', dirs_exist_ok=True)
            shutil.copy(f'{done[sb]}/optimiser_state/weights.bin', f'{dest}/best/weights.bin')
            for k in sorted(KEEP):
                if k in done:
                    shutil.copytree(done[k], f'{dest}/ck-{k}', dirs_exist_ok=True)
            shutil.copytree(f'{out_dir}/window', f'{dest}/window', dirs_exist_ok=True)
            rec['window_kept'] = len(os.listdir(f'{dest}/window'))
            shutil.copy(f'{out_dir}/val.txt', f'{dest}/val.txt')
        shutil.copy(f'{out_dir}/train.log', f'{dest}/train.log')
        json.dump(rec, open(f'{dest}/run.json', 'w'), indent=1)
        shutil.rmtree(out_dir, ignore_errors=True)
        return rec

    def queue(arms, device):
        for arm in arms:
            try:
                rec = run_arm(arm, device)
            except Exception:  # recorded, and the other arms go on
                rec = {'arm': arm, 'error': traceback.format_exc()[-2000:]}
            with lock:
                summary['runs'][arm] = rec
            save()

    def quantise(weights, out_dir, device=0):
        shutil.rmtree(out_dir, ignore_errors=True)
        rc, out, _ = sh(f'{train} train {spec} --data {by_name[lists["cw"][0]]} --scale {SCALE} --result-weight 0.5 '
                        f'--init-weights {weights} --lr 0 --batch {BATCH} --batches 1 --superbatches 1 --seed 1 '
                        f'--device {device} --threads 2 --id q --out {out_dir}', env=env)
        ck = f'{out_dir}/q-1'
        same = rc == 0 and os.path.exists(f'{ck}/optimiser_state/weights.bin') and \
            open(f'{ck}/optimiser_state/weights.bin', 'rb').read() == open(weights, 'rb').read()
        return {'rc': rc, 'unchanged': same, 'quantised': f'{ck}/quantised.bin' if same else None,
                'tail': '' if same else out[-300:]}

    def offline():
        res = summary['offline']
        nets = {'s512ppr3': init[0]}
        for arm in ARMS:
            lo, hi = WINDOW
            win = [f'{RESULT}/{arm}/window/{sb}.bin' for sb in range(lo, hi + 1)]
            if all(os.path.exists(p) for p in win):
                dest = f'{RESULT}/avg-{arm}'
                os.makedirs(dest, exist_ok=True)
                average_weights(win, f'{dest}/weights.bin')
                q = quantise(f'{dest}/weights.bin', f'{WORK}/q-{arm}')
                res[f'quantise-{arm}'] = q
                if q['quantised']:
                    shutil.copy(q['quantised'], f'{dest}/quantised.bin')
                nets[f'{arm}-avg'] = f'{dest}/weights.bin'
            if os.path.exists(f'{RESULT}/{arm}/best/weights.bin'):
                nets[f'{arm}-best'] = f'{RESULT}/{arm}/best/weights.bin'
        for name, w in nets.items():
            res[name] = {'full': score(w, by_name[VAL], ALL_POSITIONS, f'{WORK}/s-{name}'),
                         'prefix': score(w, by_name[VAL], VAL_POSITIONS, f'{WORK}/s-{name}-p'),
                         'i52_held': score(w, by_name[EVAL_ONLY[0]], ALL_POSITIONS, f'{WORK}/s-{name}-h'),
                         'i52_controls': score(w, by_name[EVAL_ONLY[1]], ALL_POSITIONS, f'{WORK}/s-{name}-k')}
            if name == 's512ppr3' or name.endswith('-avg'):
                res[name]['cells'] = score(w, by_name[VAL], ALL_POSITIONS, f'{WORK}/s-{name}-cells',
                                           extra=f'--val-cells {RESULT}/cells-{name}.txt --cell-weights {repo}/{TABLE}')
            if name.endswith('-avg'):
                sh(f'{train} eval {spec} --weights {w} --epd {repo}/tests/nnue/parity.epd '
                   f'--out {os.path.dirname(w)}/parity-trainer-{name}.txt', env=env)
            save()

    def validity():
        ref = summary['checks'].get('reference', {}).get('loss')
        starts = {arm: summary['runs'].get(arm, {}).get('initial_loss') for arm in ARMS if ARMS[arm]['init']}
        tol = {arm: TOLERANCE if ARMS[arm]['result_weight'] else TD_START_TOLERANCE for arm in starts}
        v = {'reference': ref, 'superbatch_0': starts, 'tolerance': tol,
             'ok': ref is not None and all(s is not None and abs(s - ref) <= tol[arm] for arm, s in starts.items()),
             'inputs_ok': summary['inputs']['ok'],
             'runs_ok': all(summary['runs'].get(arm, {}).get('rc') == 0 for arm in ARMS)}
        v['candidates'] = {f'{arm}-avg': {'full': (summary['offline'].get(f'{arm}-avg') or {}).get('full', {}).get('loss'),
                                          'quantised': bool((summary['offline'].get(f'quantise-{arm}') or {})
                                                            .get('quantised'))} for arm in CANDIDATES}
        v['cell_weights'] = summary.get('cell_weights')
        summary['validity'] = v

    try:
        if ok:
            threads = [threading.Thread(target=queue, args=(arms, dev)) for dev, arms in enumerate(QUEUES)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            offline()
            validity()
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(WORK, ignore_errors=True)
    save()
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
    elif '--plan' in sys.argv:
        plan()
    elif '--check-inputs' in sys.argv:
        here = os.path.dirname(os.path.abspath(__file__))
        sys.exit(check_inputs(sys.argv[sys.argv.index('--check-inputs') + 1:], os.path.dirname(os.path.dirname(
            os.path.dirname(here)))))
    elif not os.path.isdir(DATA):
        sys.exit(f'{DATA} not found: this script runs inside the Kaggle session (--plan, --check-inputs DIR)')
    else:
        session()
