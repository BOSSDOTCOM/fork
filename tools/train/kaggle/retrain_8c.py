# SPDX-License-Identifier: GPL-3.0-or-later

"""Retrain 8c, session A1 (the plan of 2026-11-12, docs/research/retrain-8c/plan.md; the owner's decisions of about
4:05 PM EST that day), on Kaggle (GPU T4 x2). Adapted from retrain 8b's kernel (tools/train/kaggle/retrain_8b.py,
8b's launch commit 320c0be) and the result fine-tune's (retrain_8b_rft.py): architecture s512pp, S = 92, AdamW, batch
16,384 x 305 per superbatch, read interleaved, the same input checks (every file's SHA-256 against the committed
manifests), the same window averages, quantisation and offline files.

Data: the snapshot g4s2 (plan section 1): g4s1 (8b's 129 training files) plus the parts sealed since, g4b, ld-d20,
ld-d50 and ld-d100 (the label-depth arms, in every arm: owner's O3; ld-d20c50/c100 not mounted), g4c and the VM
filler parts (FILLER, named at their seals); validation g4s2-val.vf and its blend copy (built at g4c's seal). The
positional slice pos1 is session A2's arm, not A1's (not mounted here).

Arms (declared in the plan before any result; two seeds each, seed K on GPU K - 1):
- cK, the control: 8b's winning recipe (td90's): TD(0.9) copies (td90-) of every part labelled by S512ppr3 or later
  (TD_PARTS), blend copies (bl-) of the older parts, the endgame slice unchanged, --result-weight 0; warm from
  r8btd90's float weights (its window average; owner's O4), LR 1e-4 dropped tenfold after superbatch 180, 360
  superbatches; the candidate is cK-avg, the mean of superbatches 331-360's float weights.
- i80K, idea 80: cK's files with every TD part read as its i80- copy (td_labels.py --label-unsaved: the unsaved
  records not in check carry their TD(0.9) label too; the saved records' labels equal the td90- copy's); the same
  steps.
- the fine-tune trio on cK-avg (owner's O1 and O4: "the rft-ep fine-tune applied after"), 60 superbatches at a
  constant LR, the candidate the mean of superbatches 46-60:
  - rftK: r8brft1's recipe: --result-weight 1.0 on the originals (cK's files' sources), LR 1e-5;
  - epK (rft-ep): the split copies (ep-, td_labels.py split --max-pieces 7) of cK's files at --result-weight 0: the
    game result on records with 8 or more pieces, cK's own target on 7 or fewer, the slice unchanged, LR 1e-5;
  - eploK (rft-ep-lo): epK at LR 5e-6.
Queues: GPU K - 1 runs cK, then (cK-avg made in the queue) rftK, epK, eploK, then i80K.

The ep- copies are made in this session, not uploaded (as the 8c preview's kernel fork-retrain-8b-rftep made them
on 2026-11-12: 119 files, 2.38 B records, 44 minutes on 4 CPUs): before training, td_labels.py split --max-pieces 7
at COMMIT of every control file but the slice, each checked against its source by td_labels.py check --mode split
(every 100th game recounted by python-chess). A failed split stops only the ep and eplo arms; c, rft and i80 run.

The endgame slice is the fresh slice slice1b (plan O2, owner 2026-11-12: v1 regenerated with new seeds, the held-out
sets excluded, the 900 endgame-check positions kept); v1's files (slice1-*, g3s2-slice1-00-rest) are mounted with
fork-g3s2 but trained by no arm (NOT_A1).

Validity (blocking; summary['validity']): every input matches its manifest and every arm's list resolves;
r8btd90's weights reproduce their own g4s1-val prefix loss of 8b's session (0.01938369, result weight 0.5) within
1e-6; cK's and i80K's superbatch 0 equal r8btd90's loss on bl-g4s2-val.vf at result weight 0 (computed here)
within 1e-5; each fine-tune's superbatch 0 equals its base cK-avg's loss on its own validation file at its own
result weight (computed in the queue) within 1e-6 (1e-5 on copies). Validation loss decides nothing (plan section 5).

Layout: result/<arm>/ (best/, ck-*/, window/, val.txt, train.log, run.json, files.json), result/avg-<arm>/
(weights.bin, quantised.bin, parity-trainer-<arm>-avg.txt), the summary result/retrain.json.

Arm sets (owner, 2026-11-13, about 8:30 PM EST: idea 80's arm in its own session, launched with A1's other arms, to
shorten A1's wall time): ARM_SET = 'all' (the default: every arm, as before), 'main' (c, rft, ep and eplo on both
GPUs) or 'i80' (i801 and i802 only), set only in a kernel copy by one exact replacement (make_kernel.py --arms). The
other arms are dropped from ARMS and QUEUES before anything runs; every remaining arm's settings, file list, checks and
outputs are the 'all' kernel's. The in-session split runs only when an ep arm is in the set.

Smoke mode (owner, 2026-11-13, about 2:55 PM EST: a smoke run of the kernel as it will be pushed, before g4c's
seal): SMOKE = True, set only in the smoke run's kernel copy, shrinks the sizes and nothing else: the originals are
SMOKE_ORIGINALS (one file of each kind: an older part read as its blend copy, a TD part, a filler part and a filler
rest, the fresh slice) with their derived files, plus SMOKE_ALSO (files that must stay untrained: v1's slice, a filler
-val source); the manifests not sealed yet are skipped; validation is g4s1-val.vf and its blend copy (g4s2-val is
made at the seal); 8 batches a superbatch; 4 superbatches (LR drop after 2, window 3-4) for c and i80, 3 (window
2-3) for the fine-tunes. Every check, the in-session split, every arm, the averages, quantisation and the offline
scores run as in the real session. With SMOKE = False (the default) nothing differs from the kernel without it.

    python3 retrain_8c.py                      # on Kaggle
    python retrain_8c.py --plan                # anywhere: the settings and every arm's command; touches nothing
    python retrain_8c.py --check-inputs DIR... # anywhere: the input checks and each arm's file list
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

COMMIT = 'retrain/8c-prep'  # replaced by the pushed commit's hash (every manifest below) before the push
ARCH = 's512pp'
SCALE = 92                  # 8a's recipe (fit_scale.py on g3s3's mix: 88, inside 88-96); the TD labels use it too
BATCH = 16384
BATCHES = 305
VAL_POSITIONS = 20000       # the per-superbatch monitoring prefix
ALL_POSITIONS = 10 ** 9     # offline scoring: every kept position of a file
# The VM filler parts' manifest names (plan section 1; each run its own part): the five runs finished before
# g4c's seal, and the run cut at g4c's seal (O9), 2026-11-13 5:49 PM EST (424 chunks).
FILLER = ['g4-gcp-20261111T191107Z', 'g4-gcp-20261112T041330Z', 'g4-gcp-20261112T185227Z',
          'g4-gcp-20261112T213623Z', 'g4-gcp-20261112T214053Z', 'g4-gcp-20261112T214524Z']
MANIFESTS = (['g2s1', 'g3s1', 'g3b', 'g3c', 'g3d', 'g3e', 'g3s2', 'g3f', 'g3g', 'g3s3',     # item 8a's inputs
              'g3h', 'g3i', 'g3j', 'g4', 'g4s1-pre', 'r8b-blend', 'r8b-arms', 'r8b-g4',   # 8b's
              'g4b', 'ld-d20', 'ld-d50', 'ld-d100', 'g4c', 'slice1b'] + FILLER            # the parts since
             + ['g4s2-pre', 'g4s2-post', 'r8c-td', 'r8c-i80', 'r8c-post'])                             # 8c's derived files
VAL = 'g4s2-val.vf'
VAL_BLEND = 'bl-g4s2-val.vf'
SMOKE = False               # the smoke run's kernel copy only (module note); False: the real session
SMOKE_ORIGINALS = ['g3b-w00.vf', 'g4b-w00.vf', 'g4-gcp-20261112T213623Z-w00.vf',
                   'g4s2-g4-gcp-20261112T185227Z-w02-val-rest.vf', 'slice1b-00.vf']
SMOKE_ALSO = ['slice1-01.vf', 'g4-gcp-20261112T185227Z-w02-val.vf']   # mounted, never trained
VAL_8B = 'g4s1-val.vf'
# The parts labelled by S512ppr3 or later (their files and their validation rests): TD(0.9) copies, i80 copies.
TD_PARTS = ('g3j-', 'g4-', 'g4s1-g3j-', 'g4s1-g4-', 'g4b-', 'ld-d20-', 'ld-d50-', 'ld-d100-', 'g4c-',
            'g4s2-g4b-', 'g4s2-g4c-', 'g4s2-ld-') + tuple(f'{f}-' for f in FILLER) + tuple(f'g4s2-{f}-' for f in FILLER)
NOT_A1 = ('pos1-', 'ld-d20c50-', 'ld-d20c100-',   # not this session's data (the positional slice is A2's arm)
          'slice1-', 'g3s2-slice1-')               # v1's slice: replaced by slice1b (O2)
SPLIT_MAX_PIECES = 7        # rft-ep (plan section 3; constant screen passed 2026-11-12)
SPLIT_SAMPLE = 100          # td_labels.py check: python-chess recount on every 100th game (its default)
CHESS = 'chess==1.11.2'     # python-chess for td_labels.py (the repository's .venv version; the preview's)
EVAL_ONLY = ['i52-held.vf', 'i52-controls.vf']       # never trained (idea 52's, retired; no longer scored)
# r8btd90's float weights (8b's td90 window average, dataset fork-r8b-rft-init), checked by reproducing their own
# g4s1-val prefix loss of 8b's session.
INIT = {'weights': 'r8b-td90-avg.bin', 'sha256': 'b5ae40056f943d4407fef453f3034a52baddb9e441b7ba352772831904bfe7c1',
        'val': VAL_8B, 'loss': 0.01938369}
TOLERANCE = 1e-6
TD_START_TOLERANCE = 1e-5
NO_DROP = 10 ** 6           # an --lr-step no run reaches: a constant LR (8a's kernel)
BASE_SETTINGS = {'superbatches': 360, 'lr_step': 180, 'window': (331, 360), 'keep': (180, 360)}
FINE_TUNE_SETTINGS = {'superbatches': 60, 'lr_step': NO_DROP, 'window': (46, 60), 'keep': (60,)}
if SMOKE:
    BATCHES = 8
    BASE_SETTINGS = {'superbatches': 4, 'lr_step': 2, 'window': (3, 4), 'keep': (2, 4)}
    FINE_TUNE_SETTINGS = {'superbatches': 3, 'lr_step': NO_DROP, 'window': (2, 3), 'keep': (3,)}
    VAL, VAL_BLEND = VAL_8B, 'bl-g4s1-val.vf'
ARMS = {}
for k in (1, 2):
    ARMS[f'c{k}'] = {**BASE_SETTINGS, 'files': 'control', 'init': 'td90', 'lr': 1e-4, 'result_weight': 0.0,
                     'val': VAL_BLEND, 'seed': k}
    ARMS[f'i80{k}'] = {**BASE_SETTINGS, 'files': 'i80', 'init': 'td90', 'lr': 1e-4, 'result_weight': 0.0,
                       'val': VAL_BLEND, 'seed': k}
    ARMS[f'rft{k}'] = {**FINE_TUNE_SETTINGS, 'files': 'originals', 'init': f'c{k}', 'lr': 1e-5, 'result_weight': 1.0,
                       'val': VAL, 'seed': k}
    ARMS[f'ep{k}'] = {**FINE_TUNE_SETTINGS, 'files': 'ep', 'init': f'c{k}', 'lr': 1e-5, 'result_weight': 0.0,
                      'val': VAL_BLEND, 'seed': k}
    ARMS[f'eplo{k}'] = {**FINE_TUNE_SETTINGS, 'files': 'ep', 'init': f'c{k}', 'lr': 5e-6, 'result_weight': 0.0,
                        'val': VAL_BLEND, 'seed': k}
QUEUES = [['c1', 'rft1', 'ep1', 'eplo1', 'i801'], ['c2', 'rft2', 'ep2', 'eplo2', 'i802']]
ARM_SET = 'all'             # a kernel copy only (module note): 'all', 'main' or 'i80'
ARM_SETS = {'all': None, 'main': ('c', 'rft', 'ep', 'eplo'), 'i80': ('i80',)}
if ARM_SETS[ARM_SET]:
    QUEUES = [[a for a in q if a.rstrip('12') in ARM_SETS[ARM_SET]] for q in QUEUES]
    ARMS = {a: v for a, v in ARMS.items() if a.rstrip('12') in ARM_SETS[ARM_SET]}
CANDIDATES = list(ARMS)
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


def split_source(name):
    """The mounted file an ep- copy is made from in the session (the name itself for any other)."""
    return name[3:] if name.startswith('ep-') else name


def is_derived(name):
    return name.startswith(('bl-', 'i52-', 'i80-', 'ep-')) or \
        (name.startswith('td') and name[2:4].isdigit() and name[4] == '-')


def control_name(n):
    """The control's file for an original: the slice unchanged, a TD part's TD(0.9) copy, else the blend copy."""
    return n if is_slice(n) else f'td90-{n}' if n.startswith(TD_PARTS) else f'bl-{n}'


def arm_files(kind, base):
    """An arm's training file names, from the originals (`base`): each substitution named in the module note."""
    if kind == 'originals':
        return list(base)
    if kind == 'control':
        return [control_name(n) for n in base]
    if kind == 'i80':
        return [f'i80-{n}' if n.startswith(TD_PARTS) and not is_slice(n) else control_name(n) for n in base]
    if kind == 'ep':
        return [n if is_slice(n) else f'ep-{control_name(n)}' for n in base]
    raise ValueError(kind)


def resolve(found, sealed, hashes=True):
    """The input checks on the mounted .vf files: every file sealed (the manifests' SHA-256) and every sealed file
    mounted once; then the originals and each arm's list. Returns (record, lists, by_name)."""
    by_name, twice = {}, []
    for p in sorted(found):
        n = os.path.basename(p)
        twice += [n] if n in by_name else []
        by_name.setdefault(n, p)
    mismatch = [n for n, p in by_name.items() if n not in sealed or (hashes and sealed[n] != sha256(p))]
    missing = sorted(set(sealed) - set(by_name))
    base = sorted(n for n in by_name if not n.endswith('-val.vf') and not is_derived(n) and n not in EVAL_ONLY
                  and not n.startswith(NOT_A1))
    lists, unresolved = {}, {}
    for arm, a in ARMS.items():
        names = arm_files(a['files'], base)
        lists[arm] = names
        unresolved[arm] = [n for n in names if split_source(n) not in by_name] + \
            ([a['val']] if a['val'] not in by_name else [])
    record = {'mounted': len(by_name), 'sealed': len(sealed), 'mismatches': mismatch, 'missing': missing,
              'names_twice': twice, 'unresolved': {k: v for k, v in unresolved.items() if v},
              'files_per_arm': {k: len(v) for k, v in lists.items()},
              'bytes_per_arm': {k: sum(os.path.getsize(by_name[split_source(n)]) for n in v
                                       if split_source(n) in by_name) for k, v in lists.items()},
              'slice_files': sorted(n for n in base if is_slice(n)),
              'td_parts': sorted(n for n in base if n.startswith(TD_PARTS))}
    record['ok'] = not (mismatch or missing or twice or record['unresolved']) and bool(base)
    return record, lists, by_name


def smoke_subset(found, sealed):
    """The smoke run's inputs: the mounted paths and sealed entries of SMOKE_ORIGINALS, their control and i80
    copies, SMOKE_ALSO and the validation files (the ep- copies are made in the session)."""
    need = set(SMOKE_ORIGINALS) | set(SMOKE_ALSO) | {VAL, VAL_BLEND, INIT['val']}
    for kind in ('control', 'i80'):
        need |= set(arm_files(kind, SMOKE_ORIGINALS))
    return ([p for p in found if os.path.basename(p) in need], {n: h for n, h in sealed.items() if n in need})


def sealed_files(repo):
    sealed = {}
    for m in MANIFESTS:
        if SMOKE and not os.path.exists(f'{repo}/data/manifests/{m}.json'):
            continue
        for b in json.load(open(f'{repo}/data/manifests/{m}.json'))['batches']:
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
    print(json.dumps({'commit': COMMIT, 'arch': ARCH, 'scale': SCALE, 'manifests': MANIFESTS, 'init': INIT,
                      'filler': FILLER, 'queues': QUEUES}, indent=1))
    for q, arms in enumerate(QUEUES):
        for arm in arms:
            a = ARMS[arm]
            src = f'<{INIT["weights"]}>' if a['init'] == 'td90' else f'<{a["init"]}-avg weights>'
            print(f'GPU {q} {arm}: fork-train train --arch {ARCH} --buckets <s512pp.json table> --data <{a["files"]} '
                  f'files> {stage_args(arm, "<" + a["val"] + ">")} --init-weights {src} --device {q} '
                  f'--id s512pp-{arm} --out <run-{arm}>  (window {a["window"]}, keep {a["keep"]})')
    print(f'offline: each arm\'s window mean, quantised; r8btd90 and the candidates scored on {VAL}: at result '
          f'weight 0.5 (all and the prefix) and 1.0 (all)')


def check_inputs(folders, repo):
    """--check-inputs: the session's input checks against local folders (each dataset's files)."""
    found = [p for f in folders for p in glob.glob(f'{f}/**/*.vf', recursive=True)]
    sealed = sealed_files(repo)
    if SMOKE:
        found, sealed = smoke_subset(found, sealed)
    record, lists, by_name = resolve(found, sealed)
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
    settings = {'commit': COMMIT, 'smoke': SMOKE, 'arm_set': ARM_SET, 'arch': ARCH, 'arms': ARMS, 'queues': QUEUES, 'scale': SCALE, 'batch': BATCH,
                'batches': BATCHES, 'val_positions': VAL_POSITIONS, 'manifests': MANIFESTS, 'init': INIT,
                'filler': FILLER}
    summary = {'settings': settings, 'checks': {}, 'runs': {}, 'offline': {}, 'tune_refs': {}}
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
    found, sealed = glob.glob(f'{DATA}/**/*.vf', recursive=True), sealed_files(repo)
    if SMOKE:
        found, sealed = smoke_subset(found, sealed)
    record, lists, by_name = resolve(found, sealed)
    summary['inputs'] = record
    init = glob.glob(f'{DATA}/**/{INIT["weights"]}', recursive=True)
    init_ok = len(init) == 1 and sha256(init[0]) == INIT['sha256']
    summary['init_weights'] = {'found': len(init), 'sha256_ok': init_ok}
    ok = built and record['ok'] and init_ok and INIT['val'] in by_name
    save()
    any_file = by_name[lists[QUEUES[0][0]][0]] if ok else None  # the first queued arm's first file (any file serves)

    def score(weights, val, positions, out_dir, result_weight=0.5, device=0):
        """A float weights file's loss on a file (superbatch 0 of a --superbatches 0 run)."""
        shutil.rmtree(out_dir, ignore_errors=True)
        rc, out, secs = sh(f'{train} train {spec} --data {any_file} --val {val} '
                           f'--val-positions {positions} --scale {SCALE} --result-weight {result_weight} '
                           f'--init-weights {weights} --superbatches 0 --device {device} --threads 2 --out {out_dir}',
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
        # The base arms' superbatch 0: r8btd90 on their own validation file at their own result weight (0).
        c['reference'] = score(init[0], by_name[VAL_BLEND], VAL_POSITIONS, f'{WORK}/init-ref', result_weight=0.0)
        c['ok'] = rc == 0 and c['warm_start']['loss'] is not None and \
            abs(c['warm_start']['loss'] - INIT['loss']) <= TOLERANCE and c['reference']['loss'] is not None
        summary['checks'] = c
        ok = c['ok']
        save()

    def make_split():
        """rft-ep's copies, made here (no upload; the 8c preview kernel's step): td_labels.py split --max-pieces
        SPLIT_MAX_PIECES of every control file but the slice, each checked against its source by td_labels.py check
        --mode split; the copies join by_name as ep-<source>. Returns (folder or None, record)."""
        srcs = sorted({split_source(n) for arm in ARMS for n in lists[arm] if n.startswith('ep-')},
                      key=lambda n: (-os.path.getsize(by_name[n]), n))
        need = sum(os.path.getsize(by_name[n]) for n in srcs)
        free = {}
        for d in ('/tmp', '/kaggle/working'):
            try:
                free[d] = shutil.disk_usage(d).free
            except OSError:
                pass
        root = max(free, key=free.get)
        mem = 0
        for line in open('/proc/meminfo'):
            if line.startswith('MemAvailable:'):
                mem = int(line.split()[1]) * 1024
        largest = os.path.getsize(by_name[srcs[0]]) if srcs else 1
        workers = max(1, min(os.cpu_count() or 1, mem // (4 * largest)))
        rec = {'files': len(srcs), 'bytes': need, 'free': free, 'root': root, 'mem_available': mem,
               'cpus': os.cpu_count(), 'workers': workers, 'max_pieces': SPLIT_MAX_PIECES, 'sample': SPLIT_SAMPLE}
        rc, out, _ = sh(f'python3 -m pip install -q {CHESS} && python3 --version')
        rec['pip'] = {'rc': rc, 'tail': out[-300:]}
        if rc or not srcs or free[root] < need * 1.2:
            rec['ok'] = False
            return None, rec
        dest = f'{root}/ep-split'
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest)
        tool = f'{repo}/tools/datagen/td_labels.py'
        began = time.time()

        def last_json(text):
            for line in reversed(text.strip().splitlines()):
                try:
                    return json.loads(line)
                except ValueError:
                    continue
            return None

        def one(n):
            path = f'{dest}/ep-{n}'
            rc1, o1, s1 = sh(f'python3 {tool} split {by_name[n]} --out {path} --max-pieces {SPLIT_MAX_PIECES}')
            made = last_json(o1) if rc1 == 0 else None
            rc2, o2, s2 = (1, '', 0)
            if made:
                rc2, o2, s2 = sh(f'python3 {tool} check {by_name[n]} {path} --mode split --scale {SCALE} '
                                 f'--max-pieces {SPLIT_MAX_PIECES} --sample {SPLIT_SAMPLE}')
            checked = last_json(o2) if rc2 == 0 else None
            r = {'split_rc': rc1, 'check_rc': rc2, 'seconds': [s1, s2],
                 'split': {k: made.get(k) for k in ('sha256', 'bytes', 'games', 'records', 'to_result', 'kept_target',
                                                    'unsaved', 'beyond_limit', 'one_move')} if made else None,
                 'check': {k: checked.get(k) for k in ('games', 'records', 'changed', 'games_recomputed',
                                                       'records_recomputed', 'bad')} if checked else None}
            r['ok'] = bool(made and checked and not checked['bad'] and
                           os.path.getsize(path) == os.path.getsize(by_name[n]))
            if not r['ok']:
                r['tail'] = (o1[-300:] + ' | ' + o2[-300:])
            return n, r

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(workers) as ex:
            per_file = dict(ex.map(one, srcs))
        rec['seconds'] = round(time.time() - began, 1)
        rec['per_file'] = per_file
        rec['totals'] = {k: sum((r['split'] or {}).get(k) or 0 for r in per_file.values())
                         for k in ('records', 'to_result', 'kept_target', 'unsaved', 'beyond_limit', 'one_move')}
        rec['failed'] = sorted(n for n, r in per_file.items() if not r['ok'])
        rec['ok'] = not rec['failed'] and len(per_file) == len(srcs)
        if rec['ok']:
            for n in srcs:
                by_name[f'ep-{n}'] = f'{dest}/ep-{n}'
        return dest, rec

    split_root, split_ok = None, False
    if ok and any(a['files'] == 'ep' for a in ARMS.values()):
        split_root, summary['split'] = make_split()
        split_ok = summary['split']['ok']
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
        """8a's: keeps the arm's KEEP, the best so far, the two newest while training; window weights copied first."""
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
        if a['files'] == 'ep' and not split_ok:
            return {'arm': arm, 'error': 'the in-session split failed (summary["split"]): not run'}
        if a['init'] == 'td90':
            start = init[0]
        else:
            start = average(a['init'])
            if start is None:
                return {'arm': arm, 'error': f'no window average of {a["init"]}: not run'}
            # The fine-tune's superbatch 0 reference: its base on its own validation file at its own result weight.
            ref = score(start, by_name[a['val']], VAL_POSITIONS, f'{WORK}/ref-{arm}', a['result_weight'], device)
            with lock:
                summary['tune_refs'][arm] = ref
        out_dir = f'{WORK}/run-{arm}'
        shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir)
        dest = f'{RESULT}/{arm}'
        os.makedirs(dest, exist_ok=True)
        files = [by_name[n] for n in lists[arm]]
        json.dump({'files': lists[arm], 'val': a['val'], 'init': a['init']}, open(f'{dest}/files.json', 'w'),
                  indent=1)
        cmd = (f'{train} train {spec} --data {" ".join(files)} {stage_args(arm, by_name[a["val"]])} '
               f'--init-weights {start} --device {device} --id s512pp-{arm} --out {out_dir} >> {out_dir}/train.log 2>&1')
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
            except Exception:  # recorded, and the other arms go on
                rec = {'arm': arm, 'error': traceback.format_exc()[-2000:]}
            with lock:
                summary['runs'][arm] = rec
            save()

    def quantise(weights, out_dir, device=0):
        shutil.rmtree(out_dir, ignore_errors=True)
        rc, out, _ = sh(f'{train} train {spec} --data {any_file} --scale {SCALE} --result-weight 0.5 '
                        f'--init-weights {weights} --lr 0 --batch {BATCH} --batches 1 --superbatches 1 --seed 1 '
                        f'--device {device} --threads 2 --id q --out {out_dir}', env=env)
        ck = f'{out_dir}/q-1'
        same = rc == 0 and os.path.exists(f'{ck}/optimiser_state/weights.bin') and \
            open(f'{ck}/optimiser_state/weights.bin', 'rb').read() == open(weights, 'rb').read()
        return {'rc': rc, 'unchanged': same, 'quantised': f'{ck}/quantised.bin' if same else None,
                'tail': '' if same else out[-300:]}

    def offline():
        res = summary['offline']
        nets = {'td90-avg (base)': init[0]}
        for arm in ARMS:
            w = average(arm)
            if w:
                q = quantise(w, f'{WORK}/q-{arm}')
                res[f'quantise-{arm}'] = q
                if q['quantised']:
                    shutil.copy(q['quantised'], f'{RESULT}/avg-{arm}/quantised.bin')
                nets[f'{arm}-avg'] = w
        for name, w in nets.items():
            tag = name.split()[0]
            res[name] = {'full': score(w, by_name[VAL], ALL_POSITIONS, f'{WORK}/s-{tag}'),
                         'prefix': score(w, by_name[VAL], VAL_POSITIONS, f'{WORK}/s-{tag}-p'),
                         'full_result': score(w, by_name[VAL], ALL_POSITIONS, f'{WORK}/s-{tag}-r', result_weight=1.0)}
            if name.endswith('-avg'):
                sh(f'{train} eval {spec} --weights {w} --epd {repo}/tests/nnue/parity.epd '
                   f'--out {os.path.dirname(w)}/parity-trainer-{name}.txt', env=env)
            save()

    def validity():
        ref = summary['checks'].get('reference', {}).get('loss')
        starts, refs, tol = {}, {}, {}
        for arm, a in ARMS.items():
            starts[arm] = summary['runs'].get(arm, {}).get('initial_loss')
            refs[arm] = ref if a['init'] == 'td90' else summary['tune_refs'].get(arm, {}).get('loss')
            tol[arm] = TOLERANCE if a['result_weight'] and a['files'] == 'originals' else TD_START_TOLERANCE
        v = {'superbatch_0': starts, 'references': refs, 'tolerance': tol,
             'per_arm': {arm: starts[arm] is not None and refs[arm] is not None and
                         abs(starts[arm] - refs[arm]) <= tol[arm] for arm in ARMS},
             'inputs_ok': summary['inputs']['ok'], 'split_ok': split_ok,
             'runs_ok': {arm: summary['runs'].get(arm, {}).get('rc') == 0 for arm in ARMS}}
        v['ok'] = all(v['per_arm'].values())
        v['candidates'] = {f'{arm}-avg': {'full': (summary['offline'].get(f'{arm}-avg') or {}).get('full', {}).get('loss'),
                                          'quantised': bool((summary['offline'].get(f'quantise-{arm}') or {})
                                                            .get('quantised'))} for arm in CANDIDATES}
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
        if split_root:
            shutil.rmtree(split_root, ignore_errors=True)
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
