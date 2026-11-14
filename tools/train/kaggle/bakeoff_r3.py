# SPDX-License-Identifier: GPL-3.0-or-later

"""Bake-off round 3, option (a): H512+PP (architecture 9: S512+PP's piece inputs per own-king region of the map M4,
with a factoriser, the pawn links shared after the region rows) trained beside its same-recipe control (S512+PP,
architecture 8), on Kaggle (GPU T4 x2). The owner's decisions of 2026-11-14 (DESIGN.md decisions log, "Bake-off round
3: the king-input designs measured and decided"): train (a) only; M4; screen it against a same-recipe control trained
alongside it; warm-start from 8c's winner once promoted, r8brft1 otherwise. Written from retrain 8c's kernel
(tools/train/kaggle/retrain_8c.py on retrain/8c-prep, its session A1's control arm c): the same data, recipe, input
checks, window averages, quantisation and offline files; the arms differ only in the architecture and its warm start.

Arms (seed 1 each, side by side, one T4 each; the same seed, so both read the data in the same order):
- kr1, H512+PP: warm from SOURCE's float weights laid out by tools/nnue/extend_weights.py --arch h512pp in the session
  (every region's rows zero, the factoriser SOURCE's piece rows, the links copied: its output is SOURCE's exactly);
- pp1, the control, S512+PP: warm from SOURCE's float weights as they are;
- xl1, x_lower, S512+PPXL (architecture 10: S512+PP plus the exposure plane's lower-class half): warm from SOURCE laid
  out by extend_weights.py --arch s512ppxl (the exposure inputs and their factoriser zero); its own session (X), one
  seed, compared against session A's pp1 (owner, 2026-11-14: the same recipe, data and warm start).
Sessions (ARM_SET): A = kr1 (GPU 0) beside pp1 (GPU 1); X = xl1 alone (GPU 0).
Recipe (8c's control arm c): retrain 8c's control files (TD(0.9) copies of the parts labelled by S512ppr3 or later, blend
copies of the older parts, the fresh endgame slice slice1b unchanged), --result-weight 0, AdamW, LR 1e-4 dropped
tenfold after superbatch 180, 360 superbatches of 305 x 16,384 positions, S = 92, read interleaved; the candidate is
the window average, the mean of superbatches 331-360's float weights, quantised by the trainer. No fine-tune here: the
two arms are compared like for like (a fine-tune of either, as 8c chooses one, is a later session).

SOURCE (the owner's decision 6): r8brft1's float weights (retrain 8b's result fine-tune, its rft1 window average:
Kaggle kernel fork-retrain-8b-rft version 1's avg-rft1/weights.bin), to be uploaded as the dataset named in SOURCE; if
retrain 8c's winner is promoted first, SOURCE becomes that arm's window average (its avg-<arm>/weights.bin) by one edit
of SOURCE (name, file, SHA-256). Either is an S512+PP net's float weights.

Validity (blocking; summary['validity']):
- every input matches its manifest and both arms' lists resolve (and are the same list);
- SOURCE's file matches its SHA-256; each warm start is laid out from it;
- `fork-train check` of each architecture; the feature leg of each new one (fork-train features against
  tools/nnue/reference.py features on the parity positions);
- each warm start's identity, in floats: it scores SOURCE's own loss on the validation file at result weight 0 (both
  computed here) within 1e-6;
- each warm start's identity, quantised: the trainer's quantised file of the warm start (an LR-0 step), converted,
  equals SOURCE's own quantised file converted and laid out (extend_weights.regioned_net: every region SOURCE's rows;
  exposure_net: the exposure rows zero), byte for byte, before any clamp; so the converted warm start evaluates as
  SOURCE (a build with it gives SOURCE's bench);
- each arm's superbatch 0 equals that reference loss within 1e-5 (8c's tolerance on label copies).
Validation loss decides nothing (the screens do; docs/research/bakeoff-r3/option-a-plan.md).

Layout: result/<arm>/ (best/, ck-*/, window/, val.txt, train.log, run.json, files.json), result/avg-<arm>/
(weights.bin, quantised.bin, parity-trainer-<arm>-avg.txt), result/warm/ (SOURCE's and each warm start's quantised
file, <init>-quantised.bin, and their parity-trainer files: the trainer leg of the warm start), the summary
result/bakeoff_r3.json.

Arm sets: ARM_SET = 'A' (kr1 and pp1), 'X' (xl1), 'kr' or 'pp' (one arm of A), set in a kernel copy by one exact
replacement, as 8c's.
Smoke mode: SMOKE = True, in a kernel copy only, shrinks the sizes and nothing else (8c's smoke set of originals, 4
full-size superbatches with the drop after 2 and the window 3-4, the offline scores on the 20,000-position prefix):
every check, both arms, the averages, quantisation and the offline scores run as in the real session; its laps (each
checkpoint's time, run.json's laps) measure each architecture's speed on the T4.

COMMIT must hold this file, the trainer's h512pp and s512ppxl architectures (tools/train), tools/nnue
(extend_weights.py, h512pp.json, s512ppxl.json) and retrain 8c's manifests (branch retrain/r3-kr4 holds them all).

    python3 bakeoff_r3.py                      # on Kaggle
    python bakeoff_r3.py --plan                # anywhere: the settings and each arm's command; touches nothing
    python bakeoff_r3.py --check-inputs DIR... # anywhere: the input checks and each arm's file list
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

COMMIT = 'nets/r3-kr4'      # replaced by the pushed commit's hash before the push
SCALE = 92                  # 8c's (the TD labels use it too)
BATCH = 16384
BATCHES = 305
VAL_POSITIONS = 20000       # the per-superbatch monitoring prefix
ALL_POSITIONS = 10 ** 9     # offline scoring: every kept position of a file
# Retrain 8c's inputs (retrain_8c.py at retrain/8c-prep 178f16b): its manifests but the i80 copies' (no arm here reads
# them), its filler parts and the names of its TD parts.
FILLER = ['g4-gcp-20261111T191107Z', 'g4-gcp-20261112T041330Z', 'g4-gcp-20261112T185227Z',
          'g4-gcp-20261112T213623Z', 'g4-gcp-20261112T214053Z', 'g4-gcp-20261112T214524Z']
MANIFESTS = (['g2s1', 'g3s1', 'g3b', 'g3c', 'g3d', 'g3e', 'g3s2', 'g3f', 'g3g', 'g3s3',
              'g3h', 'g3i', 'g3j', 'g4', 'g4s1-pre', 'r8b-blend', 'r8b-arms', 'r8b-g4',
              'g4b', 'ld-d20', 'ld-d50', 'ld-d100', 'g4c', 'slice1b'] + FILLER
             + ['g4s2-pre', 'g4s2-post', 'r8c-td', 'r8c-post'])
VAL = 'g4s2-val.vf'
VAL_BLEND = 'bl-g4s2-val.vf'
TD_PARTS = ('g3j-', 'g4-', 'g4s1-g3j-', 'g4s1-g4-', 'g4b-', 'ld-d20-', 'ld-d50-', 'ld-d100-', 'g4c-',
            'g4s2-g4b-', 'g4s2-g4c-', 'g4s2-ld-') + tuple(f'{f}-' for f in FILLER) + tuple(f'g4s2-{f}-' for f in FILLER)
NOT_TRAINED = ('pos1-', 'ld-d20c50-', 'ld-d20c100-',   # not 8c's control data (the positional slice is A2's arm)
               'slice1-', 'g3s2-slice1-')               # v1's slice: replaced by slice1b (8c's O2)
EVAL_ONLY = ['i52-held.vf', 'i52-controls.vf']
SMOKE = False               # the smoke run's kernel copy only (module note); False: the real session
SMOKE_ORIGINALS = ['g3b-w00.vf', 'g4b-w00.vf', 'g4-gcp-20261112T213623Z-w00.vf',
                   'g4s2-g4-gcp-20261112T185227Z-w02-val-rest.vf', 'slice1b-00.vf']
CHESS = 'chess==1.11.2'     # python-chess for tools/nnue (models.py imports it); the repository's .venv version
# The source net's float weights (module note): r8brft1's until 8c's winner is promoted.
SOURCE = {'name': 'r8brft1', 'weights': 'r8brft1-avg.bin',
          'sha256': '2d70ebccb6e6eb7d192faea0e16bee5c1aa2169c0346f3791e5d6bb27ae1dba1',
          'dataset': 'fork-r3-kr4-init'}
WARM_TOLERANCE = 1e-6       # the warm start's float identity (the same sums, zeros added)
START_TOLERANCE = 1e-5      # an arm's superbatch 0 against the reference (8c's on label copies)
BASE_SETTINGS = {'superbatches': 360, 'lr': 1e-4, 'lr_step': 180, 'window': (331, 360), 'keep': (180, 360),
                 'result_weight': 0.0, 'files': 'control', 'val': VAL_BLEND}
if SMOKE:
    # Full-size superbatches (305 batches), so each arm's laps are the real session's; 4 of them, and the offline
    # scores on the monitoring prefix only.
    BASE_SETTINGS = {**BASE_SETTINGS, 'superbatches': 4, 'lr_step': 2, 'window': (3, 4), 'keep': (2, 4)}
    VAL, VAL_BLEND = 'g4s1-val.vf', 'bl-g4s1-val.vf'
    BASE_SETTINGS['val'] = VAL_BLEND
    ALL_POSITIONS = VAL_POSITIONS
ARMS = {'kr1': {**BASE_SETTINGS, 'arch': 'h512pp', 'init': 'regioned', 'seed': 1},
        'pp1': {**BASE_SETTINGS, 'arch': 's512pp', 'init': 'source', 'seed': 1},
        'xl1': {**BASE_SETTINGS, 'arch': 's512ppxl', 'init': 'exposure', 'seed': 1}}
# The warm starts laid out from SOURCE in the session: (architecture, extend_weights.py's net-file function that
# lays SOURCE's quantised net out the same way, for the quantised identity).
WARM_STARTS = {'regioned': ('h512pp', 'regioned_net'), 'exposure': ('s512ppxl', 'exposure_net')}
# The sessions (module note): A = kr1 and its same-recipe control pp1, one GPU each; X = xl1 alone (x_lower, owner
# 2026-11-14: compared against session A's control); kr and pp one arm of A each.
ARM_SET = 'A'               # a kernel copy only (module note): 'A', 'X', 'kr' or 'pp'
ARM_SETS = {'A': [['kr1'], ['pp1']], 'X': [['xl1']], 'kr': [['kr1']], 'pp': [['pp1']]}
QUEUES = ARM_SETS[ARM_SET]
ARMS = {a: v for a, v in ARMS.items() if any(a in q for q in QUEUES)}
DATA = '/kaggle/input'
WORK = '/kaggle/working/bakeoff'
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
    return name.startswith(('bl-', 'i52-', 'i80-', 'ep-', 'lam-')) or \
        (name.startswith('td') and name[2:4].isdigit() and name[4] == '-')


def control_name(n):
    """8c's control file for an original: the slice unchanged, a TD part's TD(0.9) copy, else the blend copy."""
    return n if is_slice(n) else f'td90-{n}' if n.startswith(TD_PARTS) else f'bl-{n}'


def originals(names):
    """The training originals among mounted file names (8c's rule for its control arm)."""
    return sorted(n for n in names if not n.endswith('-val.vf') and not is_derived(n) and n not in EVAL_ONLY
                  and not n.startswith(NOT_TRAINED))


def resolve(found, sealed, hashes=True):
    """The input checks on the mounted .vf files: every mounted file sealed (the manifests' SHA-256), every file an
    arm reads mounted, and both arms' lists the same. Returns (record, lists, by_name)."""
    by_name, twice = {}, []
    for p in sorted(found):
        n = os.path.basename(p)
        twice += [n] if n in by_name else []
        by_name.setdefault(n, p)
    mismatch = [n for n, p in by_name.items() if n not in sealed or (hashes and sealed[n] != sha256(p))]
    base = originals(by_name)
    lists, unresolved = {}, {}
    for arm, a in ARMS.items():
        names = [control_name(n) for n in base]
        lists[arm] = names
        unresolved[arm] = [n for n in names if n not in by_name] + ([a['val']] if a['val'] not in by_name else [])
    same = len({tuple(v) for v in lists.values()}) <= 1
    record = {'mounted': len(by_name), 'sealed': len(sealed), 'mismatches': mismatch, 'names_twice': twice,
              'unresolved': {k: v for k, v in unresolved.items() if v}, 'same_lists': same,
              'files_per_arm': {k: len(v) for k, v in lists.items()},
              'bytes_per_arm': {k: sum(os.path.getsize(by_name[n]) for n in v if n in by_name)
                                for k, v in lists.items()},
              'slice_files': sorted(n for n in base if is_slice(n)),
              'td_parts': sorted(n for n in base if n.startswith(TD_PARTS))}
    record['ok'] = not (mismatch or twice or record['unresolved']) and same and bool(base)
    return record, lists, by_name


def smoke_subset(found, sealed):
    """The smoke run's inputs: SMOKE_ORIGINALS, their control copies and the validation files."""
    need = set(SMOKE_ORIGINALS) | {control_name(n) for n in SMOKE_ORIGINALS} | {VAL, VAL_BLEND}
    return ([p for p in found if os.path.basename(p) in need], {n: h for n, h in sealed.items() if n in need})


def sealed_files(repo):
    sealed = {}
    for m in MANIFESTS:
        path = f'{repo}/data/manifests/{m}.json'
        if SMOKE and not os.path.exists(path):
            continue
        for b in json.load(open(path))['batches']:
            for s in b:
                sealed[s['file']] = s['sha256']
    return sealed


def stage_args(arm, val_path):
    a = ARMS[arm]
    return (f'--start 1 --superbatches {a["superbatches"]} --lr {a["lr"]} --lr-step {a["lr_step"]} '
            f'--seed {a["seed"]} --patience {a["superbatches"] + 1} --scale {SCALE} '
            f'--result-weight {a["result_weight"]} --batch {BATCH} --batches {BATCHES} --interleave '
            f'--val {val_path} --val-positions {VAL_POSITIONS} --threads 2')


def plan():
    """--plan: the settings and each arm's command with placeholder paths; nothing is touched."""
    print(json.dumps({'commit': COMMIT, 'scale': SCALE, 'source': SOURCE, 'manifests': MANIFESTS, 'filler': FILLER,
                      'queues': QUEUES, 'arms': ARMS, 'smoke': SMOKE, 'arm_set': ARM_SET}, indent=1))
    for q, arms in enumerate(QUEUES):
        for arm in arms:
            a = ARMS[arm]
            src = f'<{SOURCE["weights"]}>' if a['init'] == 'source' else \
                f'<extend_weights.py {SOURCE["weights"]} --arch {a["arch"]}>'
            print(f'GPU {q} {arm}: fork-train train --arch {a["arch"]} --buckets <s512pp.json table> --data '
                  f'<{a["files"]} files> {stage_args(arm, "<" + a["val"] + ">")} --init-weights {src} --device {q} '
                  f'--id {a["arch"]}-{arm} --out <run-{arm}>  (window {a["window"]}, keep {a["keep"]})')
    print(f'offline: each arm\'s window mean, quantised; {SOURCE["name"]} and the candidates scored on {VAL}: at '
          f'result weight 0.5 (all and the prefix) and 1.0 (all)')


def check_inputs(folders, repo):
    """--check-inputs: the session's input checks against local folders (each dataset's files)."""
    found = [p for f in folders for p in glob.glob(f'{f}/**/*.vf', recursive=True)]
    sealed = sealed_files(repo)
    if SMOKE:
        found, sealed = smoke_subset(found, sealed)
    record, lists, _ = resolve(found, sealed)
    init = [p for f in folders for p in glob.glob(f'{f}/**/{SOURCE["weights"]}', recursive=True)]
    record['source_weights'] = {'found': len(init), 'sha256_ok': len(init) == 1 and sha256(init[0]) == SOURCE['sha256']}
    print(json.dumps(record, indent=1))
    for arm, names in lists.items():
        print(arm, len(names), 'files;', ', '.join(names[:3]), '...', ', '.join(names[-3:]))
    return 0 if record['ok'] and record['source_weights']['sha256_ok'] else 1


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


def identity_probe(nnue, source_quantised, warm_quantised, arch='h512pp', lay_out='regioned_net'):
    """A script printing True when the warm start's quantised file, converted with `arch`'s layout, is SOURCE's
    converted and laid out by extend_weights.`lay_out` (regioned_net: every region SOURCE's rows; exposure_net: the
    exposure rows zero), both before any clamp."""
    return '\n'.join([
        'import sys',
        f'sys.path.insert(0, {nnue!r})',
        'import convert, extend_weights, netformat',
        f'a = convert.convert(open({source_quantised!r}, "rb").read(), netformat.layout({nnue + "/s512pp.json"!r}), '
        f'{SCALE})',
        f'b = convert.convert(open({warm_quantised!r}, "rb").read(), netformat.layout({nnue + "/" + arch + ".json"!r}), '
        f'{SCALE})',
        f'print(extend_weights.{lay_out}(a) == b)', ''])


def session():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(RESULT, exist_ok=True)
    home = os.path.expanduser('~')
    env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
           'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
    settings = {'commit': COMMIT, 'smoke': SMOKE, 'arm_set': ARM_SET, 'arms': ARMS, 'queues': QUEUES, 'scale': SCALE,
                'batch': BATCH, 'batches': BATCHES, 'val_positions': VAL_POSITIONS, 'manifests': MANIFESTS,
                'source': SOURCE, 'filler': FILLER}
    summary = {'settings': settings, 'checks': {}, 'runs': {}, 'offline': {}}
    lock = threading.Lock()

    def save():
        with lock:
            json.dump(summary, open(f'{RESULT}/bakeoff_r3.json', 'w'), indent=1)

    rc, _, _ = sh('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal')
    summary['rustup'] = rc
    repo = f'{WORK}/fork'
    rc, out, _ = sh(f'cd {WORK} && rm -rf fork && git clone -q https://github.com/BOSSDOTCOM/fork && cd fork && '
                    f'git checkout -q {COMMIT} && git log --oneline -1')
    summary['head'] = out.strip()[-120:]
    rc, out, secs = sh(f'cd {repo}/tools/train && cargo build --release --locked --features cuda', env=env)
    summary['build'] = {'rc': rc, 'seconds': secs, 'tail': out[-400:] if rc else ''}
    built = rc == 0
    rc, out, _ = sh(f'python3 -m pip install -q {CHESS} && python3 --version')
    summary['pip'] = {'rc': rc, 'tail': out[-300:]}
    train = f'{repo}/tools/train/target/release/fork-train'
    nnue = f'{repo}/tools/nnue'
    table = ','.join(map(str, json.load(open(f'{nnue}/s512pp.json'))['table'])) if built else ''

    def spec(arch):
        return f'--arch {arch} --buckets {table}'

    found, sealed = glob.glob(f'{DATA}/**/*.vf', recursive=True), sealed_files(repo)
    if SMOKE:
        found, sealed = smoke_subset(found, sealed)
    record, lists, by_name = resolve(found, sealed)
    summary['inputs'] = record
    src = glob.glob(f'{DATA}/**/{SOURCE["weights"]}', recursive=True)
    src_ok = len(src) == 1 and sha256(src[0]) == SOURCE['sha256']
    summary['source_weights'] = {'found': len(src), 'sha256_ok': src_ok}
    ok = built and summary['pip']['rc'] == 0 and record['ok'] and src_ok
    init_of = {'source': src[0] if src else None}
    warms = sorted({a['init'] for a in ARMS.values()} - {'source'})
    summary['warm_start'] = {}
    for init in warms:
        arch = WARM_STARTS[init][0]
        init_of[init] = f'{WORK}/{arch}-warm.bin'
        if ok:
            rc, out, _ = sh(f'python3 {nnue}/extend_weights.py {src[0]} {init_of[init]} --arch {arch}')
            summary['warm_start'][init] = {'rc': rc, 'out': out[-300:]}
            ok = rc == 0 and os.path.exists(init_of[init])
    save()
    any_file = by_name[lists[QUEUES[0][0]][0]] if ok else None  # any training file serves the scoring runs

    def score(arch, weights, val, positions, out_dir, result_weight=0.5, device=0):
        """A float weights file's loss on a file (superbatch 0 of a --superbatches 0 run)."""
        shutil.rmtree(out_dir, ignore_errors=True)
        rc, out, secs = sh(f'{train} train {spec(arch)} --data {any_file} --val {val} '
                           f'--val-positions {positions} --scale {SCALE} --result-weight {result_weight} '
                           f'--init-weights {weights} --superbatches 0 --device {device} --threads 2 --out {out_dir}',
                           env=env)
        loss = None
        if rc == 0 and os.path.exists(f'{out_dir}/val.txt'):
            first = open(f'{out_dir}/val.txt').readline().split()
            loss = float(first[1]) if first and first[0] == '0' else None
        return {'rc': rc, 'loss': loss, 'seconds': secs, 'tail': '' if loss is not None else out[-300:]}

    def quantise(arch, weights, out_dir, device=0):
        shutil.rmtree(out_dir, ignore_errors=True)
        rc, out, _ = sh(f'{train} train {spec(arch)} --data {any_file} --scale {SCALE} --result-weight 0.5 '
                        f'--init-weights {weights} --lr 0 --batch {BATCH} --batches 1 --superbatches 1 --seed 1 '
                        f'--device {device} --threads 2 --id q --out {out_dir}', env=env)
        ck = f'{out_dir}/q-1'
        same = rc == 0 and os.path.exists(f'{ck}/optimiser_state/weights.bin') and \
            open(f'{ck}/optimiser_state/weights.bin', 'rb').read() == open(weights, 'rb').read()
        return {'rc': rc, 'unchanged': same, 'quantised': f'{ck}/quantised.bin' if same else None,
                'tail': '' if same else out[-300:]}

    if ok:
        c = {}
        archs = sorted({a['arch'] for a in ARMS.values()} | {'s512pp'})
        for arch in archs:
            rc, out, _ = sh(f'{train} check {spec(arch)} --out {WORK}/check-{arch}', env=env)
            c[f'check-{arch}'] = {'rc': rc, 'out': out[-300:]}
        # The feature leg of each new architecture: the trainer's active inputs on the parity positions against the
        # reference's (tools/nnue/reference.py features).
        for arch in archs:
            if arch == 's512pp':
                continue
            rc, out, _ = sh(f'{train} features {spec(arch)} --epd {repo}/tests/nnue/parity.epd '
                            f'> {WORK}/features-{arch}.txt', env=env)
            rc2, out2, _ = sh(f'python3 {nnue}/reference.py features --rust {WORK}/features-{arch}.txt '
                              f'--layout {nnue}/{arch}.json')
            c[f'features-{arch}'] = {'rc': rc, 'leg_rc': rc2, 'out': out2[-300:]}
        # The reference: SOURCE on the arms' validation file at their result weight (0); each warm start must score
        # the same (its float identity).
        c['reference'] = score('s512pp', src[0], by_name[VAL_BLEND], VAL_POSITIONS, f'{WORK}/ref', result_weight=0.0)
        os.makedirs(f'{RESULT}/warm', exist_ok=True)
        qs = quantise('s512pp', src[0], f'{WORK}/q-source')
        c['quantise_source'] = qs
        if qs['quantised']:
            shutil.copy(qs['quantised'], f'{RESULT}/warm/source-quantised.bin')
        sh(f'{train} eval {spec("s512pp")} --weights {src[0]} --epd {repo}/tests/nnue/parity.epd '
           f'--out {RESULT}/warm/parity-trainer-source.txt', env=env)
        ref = c['reference']['loss']
        good = all(c[f'check-{a}']['rc'] == 0 for a in archs) and \
            all(v['rc'] == 0 and v['leg_rc'] == 0 for k, v in c.items() if k.startswith('features-'))
        for init in warms:
            arch, lay_out = WARM_STARTS[init]
            w = init_of[init]
            got = score(arch, w, by_name[VAL_BLEND], VAL_POSITIONS, f'{WORK}/ref-{init}', result_weight=0.0)
            c[f'warm_float-{init}'] = got
            c[f'warm_float_ok-{init}'] = ref is not None and got['loss'] is not None and \
                abs(ref - got['loss']) <= WARM_TOLERANCE
            # The quantised identity: the trainer's own files of both, converted, compared after laying SOURCE out.
            qw = quantise(arch, w, f'{WORK}/q-{init}')
            c[f'quantise-{init}'] = qw
            same = False
            if qs['quantised'] and qw['quantised']:
                shutil.copy(qw['quantised'], f'{RESULT}/warm/{init}-quantised.bin')
                with open(f'{WORK}/identity-{init}.py', 'w') as f:
                    f.write(identity_probe(nnue, qs['quantised'], qw['quantised'], arch, lay_out))
                rc, out, _ = sh(f'python3 {WORK}/identity-{init}.py')
                same = rc == 0 and out.strip().endswith('True')
                c[f'quantised_identity_tail-{init}'] = out[-300:]
            c[f'quantised_identity-{init}'] = same
            # The trainer leg of the warm start: its float outputs on the parity positions.
            sh(f'{train} eval {spec(arch)} --weights {w} --epd {repo}/tests/nnue/parity.epd '
               f'--out {RESULT}/warm/parity-trainer-{init}.txt', env=env)
            good = good and c[f'warm_float_ok-{init}'] and same
        c['ok'] = good and ref is not None
        summary['checks'] = c
        ok = c['ok']
        save()

    def checkpoints(arm, out_dir):
        done = {}
        for d in glob.glob(f'{out_dir}/{ARMS[arm]["arch"]}-{arm}-*'):
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

    def prune(arm, out_dir, final=False, seen=None):
        """8a's: keeps the arm's KEEP, the best so far, the two newest while training; window weights copied first.
        `seen` gets each checkpoint's time (its superbatch.txt), recorded before any checkpoint is removed."""
        a = ARMS[arm]
        done = checkpoints(arm, out_dir)
        if seen is not None:
            for sb, d in done.items():
                seen.setdefault(sb, os.path.getmtime(f'{d}/superbatch.txt'))
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

    def average(arm):
        """The arm's window mean (result/avg-<arm>/weights.bin), or None when its window is incomplete."""
        lo, hi = ARMS[arm]['window']
        win = [f'{RESULT}/{arm}/window/{sb}.bin' for sb in range(lo, hi + 1)]
        if not all(os.path.exists(p) for p in win):
            return None
        dest = f'{RESULT}/avg-{arm}'
        os.makedirs(dest, exist_ok=True)
        if not os.path.exists(f'{dest}/weights.bin'):
            average_weights(win, f'{dest}/weights.bin.part')
            os.replace(f'{dest}/weights.bin.part', f'{dest}/weights.bin')
        return f'{dest}/weights.bin'

    def run_arm(arm, device):
        a = ARMS[arm]
        out_dir = f'{WORK}/run-{arm}'
        shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir)
        dest = f'{RESULT}/{arm}'
        os.makedirs(dest, exist_ok=True)
        files = [by_name[n] for n in lists[arm]]
        json.dump({'files': lists[arm], 'val': a['val'], 'init': a['init'], 'arch': a['arch'], 'source': SOURCE},
                  open(f'{dest}/files.json', 'w'), indent=1)
        cmd = (f'{train} train {spec(a["arch"])} --data {" ".join(files)} {stage_args(arm, by_name[a["val"]])} '
               f'--init-weights {init_of[a["init"]]} --device {device} --id {a["arch"]}-{arm} --out {out_dir} '
               f'>> {out_dir}/train.log 2>&1')
        began = time.time()
        proc = subprocess.Popen(cmd, shell=True, env={**os.environ, **env})
        seen = {}
        while proc.poll() is None:
            prune(arm, out_dir, seen=seen)
            time.sleep(20)
        prune(arm, out_dir, final=True, seen=seen)
        rec = {'arm': arm, 'arch': a['arch'], 'device': device, 'rc': proc.returncode,
               'seconds': round(time.time() - began, 1), 'files': len(files)}
        curve = curve_of(out_dir)
        rec['val_curve'] = curve
        rec['initial_loss'] = curve[0][1] if curve and curve[0][0] == 0 else None
        trained = [c for c in curve if c[0] > 0]
        rec['positions_per_second'] = round(BATCH * BATCHES * len(trained) / rec['seconds']) if trained else None
        # Laps: seconds from the start (superbatch 1, startup and the initial validation included) or from the last
        # checkpoint (each later superbatch, its training and the previous superbatch's validation).
        times = [began] + [seen[sb] for sb in sorted(seen)]
        rec['laps'] = {sb: round(t - p, 1) for sb, t, p in zip(sorted(seen), times[1:], times[:-1])}
        later = [v for sb, v in rec['laps'].items() if sb > 1]
        rec['lap_mean_after_first'] = round(sum(later) / len(later), 2) if later else None
        done = checkpoints(arm, out_dir)
        if trained:
            sb, best = min(trained, key=lambda c: c[1])
            rec['best_superbatch'], rec['best_loss'] = sb, best
            lo, hi = a['window']
            win = [l for s, l in trained if lo <= s <= hi]
            rec['window_mean'] = sum(win) / len(win) if len(win) == hi - lo + 1 else None
            shutil.copytree(done[sb], f'{dest}/best', dirs_exist_ok=True)
            shutil.copy(f'{done[sb]}/optimiser_state/weights.bin', f'{dest}/best/weights.bin')
            for k in a['keep']:
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
            except Exception:  # recorded, and the other arm goes on
                rec = {'arm': arm, 'error': traceback.format_exc()[-2000:]}
            with lock:
                summary['runs'][arm] = rec
            save()

    def offline():
        res = summary['offline']
        nets = {f'{SOURCE["name"]} (source)': ('s512pp', src[0])}
        for arm in ARMS:
            w = average(arm)
            if w:
                arch = ARMS[arm]['arch']
                q = quantise(arch, w, f'{WORK}/q-{arm}')
                res[f'quantise-{arm}'] = q
                if q['quantised']:
                    shutil.copy(q['quantised'], f'{RESULT}/avg-{arm}/quantised.bin')
                nets[f'{arm}-avg'] = (arch, w)
        for name, (arch, w) in nets.items():
            tag = name.split()[0]
            res[name] = {'full': score(arch, w, by_name[VAL], ALL_POSITIONS, f'{WORK}/s-{tag}'),
                         'prefix': score(arch, w, by_name[VAL], VAL_POSITIONS, f'{WORK}/s-{tag}-p'),
                         'full_result': score(arch, w, by_name[VAL], ALL_POSITIONS, f'{WORK}/s-{tag}-r',
                                              result_weight=1.0)}
            if name.endswith('-avg'):
                sh(f'{train} eval {spec(arch)} --weights {w} --epd {repo}/tests/nnue/parity.epd '
                   f'--out {os.path.dirname(w)}/parity-trainer-{name}.txt', env=env)
            save()

    def validity():
        ref = summary['checks'].get('reference', {}).get('loss')
        starts = {arm: summary['runs'].get(arm, {}).get('initial_loss') for arm in ARMS}
        v = {'superbatch_0': starts, 'reference': ref, 'tolerance': START_TOLERANCE,
             'per_arm': {arm: starts[arm] is not None and ref is not None and abs(starts[arm] - ref) <= START_TOLERANCE
                         for arm in ARMS},
             'inputs_ok': summary['inputs']['ok'],
             'warm_float_ok': {k: v for k, v in summary['checks'].items() if k.startswith('warm_float_ok-')},
             'quantised_identity': {k: v for k, v in summary['checks'].items() if k.startswith('quantised_identity-')},
             'runs_ok': {arm: summary['runs'].get(arm, {}).get('rc') == 0 for arm in ARMS}}
        v['ok'] = all(v['per_arm'].values()) and all(v['runs_ok'].values())
        v['candidates'] = {f'{arm}-avg': {'full': (summary['offline'].get(f'{arm}-avg') or {}).get('full', {})
                                          .get('loss'),
                                          'quantised': bool((summary['offline'].get(f'quantise-{arm}') or {})
                                                            .get('quantised'))} for arm in ARMS}
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
