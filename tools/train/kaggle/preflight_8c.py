# SPDX-License-Identifier: GPL-3.0-or-later

"""Retrain 8c's preflight, P1 (owner's decision O7, 2026-11-12; plan section 7), on Kaggle (GPU T4 x2), on the
inputs that exist before g4c's seal. It answers four questions before 8c's launch session spends its hours:

1. Do about 25 or more data sources attach to one kernel? (Kaggle's limit is UNVERIFIED; 8c needs about 25-33.)
   The kernel's metadata names every dataset of the account (32 with fork-g4b and fork-pos1); each one's mount
   is found and its files counted ('mounts').
2. Do the inputs check? Every .vf file of the datasets 8c reads (8b's 16, fork-r8b-rft-init's warm start, the
   label-depth arms fork-ld-d20/d50/d100, the new parts fork-g4b and fork-pos1) hashed against its manifest:
   8b's 18 manifests at retrain/8b-rft 43f6ecc, g4b and ld-d20/d50/d100 at COMMIT, pos1's embedded below (its
   manifest data/manifests/pos1.json is on retrain/8c-prep, not yet pushed when this ran).
3. Does the loader read every new part? fork-train stats (the trainer's own filter) per part: the kept positions
   of g4b, ld-d20, ld-d50, ld-d100 and pos1, against each manifest's saved positions.
4. Do a few superbatches run on 8c's file set, and how fast? Two runs side by side (seeds 1 and 2, one T4 each),
   warm from r8btd90's float weights (the owner's O4), result weight 0, LR 1e-4, on 8b's td90 arm's files (TD(0.9)
   copies of g3j/g4, blend copies of the rest, the Syzygy slice unchanged) plus the new raw parts above (their TD
   copies do not exist yet; raw files stand in for them, which changes nothing for the loader or the speed),
   SUPERBATCHES superbatches each; each superbatch timed; superbatch 0 against r8btd90's own loss on
   bl-g4s1-val.vf at result weight 0 (computed here) within 1e-5, and r8btd90's g4s1-val prefix loss of 8b's
   session (0.01938369, result weight 0.5) reproduced within 1e-6.

Nothing is kept but result/preflight.json (no network is trained to a candidate).

    python3 preflight_8c.py          # on Kaggle
    python preflight_8c.py --plan    # anywhere: the settings; touches nothing
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback

COMMIT = 'e6b2ac3671f21bb34b0f6db58396948aaadab1ab'   # phase-4 (pushed): the trainer, g4b and ld-* manifests
COMMIT_8B = '43f6ecc107d8bbd9b3a12c76de8d02d65fb1b41a'  # retrain/8b-rft (pushed): 8b's manifests
ARCH = 's512pp'
SCALE = 92
BATCH = 16384
BATCHES = 305
SUPERBATCHES = 6
VAL_POSITIONS = 20000
MANIFESTS_8B = ['g2s1', 'g3s1', 'g3b', 'g3c', 'g3d', 'g3e', 'g3s2', 'g3f', 'g3g', 'g3s3', 'g3h', 'g3i', 'g3j', 'g4',
                'g4s1-pre', 'r8b-blend', 'r8b-arms', 'r8b-g4']
MANIFESTS_NEW = ['g4b', 'ld-d20', 'ld-d50', 'ld-d100']
POS1 = {  # data/manifests/pos1.json on retrain/8c-prep (the positional slice slice-pos-td90, renamed)
    'pos1-w00.vf': '3b2ffbf3d6b4b5fb82cf4c4d9d09074823d45febf9447687a287d3790b7a4d0a',
    'pos1-w01.vf': '3b6255a46d1359580c0d4fc73ea06a32ff0a54807ad33b0530db65f8d078d17b',
    'pos1-w02.vf': '5851b582a8caa5c9be13ac3831e07f819508e8a348e0abb9f96d23f8a7622361',
    'pos1-w03.vf': '1b8a1a06ab90ff5ae51be65b3dbb26e60a89f9de9c69f599acfcbc531b164e3c',
    'pos1-w04.vf': 'daa60d89f10131653c51e13caea06ae8298f6d6a130b5e30e5c6ac11339a5084',
    'pos1-w05.vf': '523b58b6c125686f89cb0bd2cdc6a3f2c5bfcf175222f241f82fadf3d4f44035',
    'pos1-w06.vf': '9d5139514cdb6bb738204fee1dcbdfd032bb5107ff2af95f4030051164ddadfd',
    'pos1-w07.vf': '912ab5409c44b15b232c4ca84a456240cecee97ab03065ffc8405008f075bfdc',
}
POS1_POSITIONS = 12500535
# The datasets 8c reads (their files are checked); every other attached dataset only tests the source count.
NEEDED = ['fork-g2s1', 'fork-g3s1', 'fork-g3rest', 'fork-g3bcd', 'fork-g3e', 'fork-g3s2', 'fork-g3f', 'fork-g3g',
          'fork-g3s3', 'fork-g3hij', 'fork-r8b-blend-1', 'fork-r8b-blend-2', 'fork-r8b-blend-3', 'fork-r8b-arms',
          'fork-g4', 'fork-r8b-g4', 'fork-r8b-rft-init', 'fork-ld-d20', 'fork-ld-d50', 'fork-ld-d100', 'fork-g4b',
          'fork-pos1']
EXTRA = ['fork-ld-d20c50', 'fork-ld-d20c100', 'fork-i59s3', 'fork-g2', 'fork-g2bc', 'fork-g1s1', 'fork-g1s0',
         'fork-g0s1', 'fork-g0s2', 'fork-s2-test']
NEW_PARTS = {'g4b': 'g4b-', 'ld-d20': 'ld-d20-', 'ld-d50': 'ld-d50-', 'ld-d100': 'ld-d100-', 'pos1': 'pos1-'}
VAL = 'g4s1-val.vf'
VAL_BLEND = 'bl-g4s1-val.vf'
NEWEST = ('g3j-', 'g4-', 'g4s1-g3j-', 'g4s1-g4-')
EVAL_ONLY = ['i52-held.vf', 'i52-controls.vf']
INIT = {'weights': 'r8b-td90-avg.bin', 'sha256': 'b5ae40056f943d4407fef453f3034a52baddb9e441b7ba352772831904bfe7c1',
        'val': 'g4s1-val.vf', 'loss': 0.01938369}
TOLERANCE = 1e-6
TD_START_TOLERANCE = 1e-5
DATA = '/kaggle/input'
WORK = '/kaggle/working/pre'
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


def is_new(name):
    return name.startswith(tuple(NEW_PARTS.values()))


def td90_files(base):
    """8b's td90 arm (retrain_8b.py arm_files('td90')) on 8b's own files; the new parts raw."""
    old = [n for n in base if not is_new(n)]
    return ([n if is_slice(n) else f'td90-{n}' if n.startswith(NEWEST) else f'bl-{n}' for n in old]
            + [n for n in base if is_new(n)])


def mounts():
    """Each attached dataset's mount folder (found by name at any depth under DATA) and its file count."""
    found = {}
    for root, dirs, _files in os.walk(DATA):
        for d in dirs:
            if d in NEEDED + EXTRA and d not in found:
                found[d] = os.path.join(root, d)
        if root.count(os.sep) - DATA.count(os.sep) >= 3:
            dirs[:] = []
    rec = {}
    for d in NEEDED + EXTRA:
        p = found.get(d)
        files = [f for f in glob.glob(f'{p}/**/*', recursive=True) if os.path.isfile(f)] if p else []
        rec[d] = {'mounted': p is not None, 'files': len(files), 'bytes': sum(os.path.getsize(f) for f in files)}
    return rec, found


def sh(cmd, env=None, timeout=4 * 3600):
    t = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr), round(time.time() - t, 1)


def plan():
    print(json.dumps({'commit': COMMIT, 'commit_8b': COMMIT_8B, 'needed': NEEDED, 'extra': EXTRA,
                      'sources': len(NEEDED) + len(EXTRA), 'superbatches': SUPERBATCHES, 'init': INIT,
                      'new_parts': NEW_PARTS}, indent=1))


def session():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(RESULT, exist_ok=True)
    home = os.path.expanduser('~')
    env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
           'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}
    summary = {'settings': {'commit': COMMIT, 'commit_8b': COMMIT_8B, 'superbatches': SUPERBATCHES, 'init': INIT,
                            'sources': len(NEEDED) + len(EXTRA)}, 'began': time.time()}
    lock = threading.Lock()

    def save():
        with lock:
            json.dump(summary, open(f'{RESULT}/preflight.json', 'w'), indent=1)

    # 1. The mounts.
    rec, found = mounts()
    summary['mounts'] = rec
    summary['mounted'] = sum(r['mounted'] for r in rec.values())
    summary['input_root'] = sorted(os.listdir(DATA))[:60]
    save()
    # The trainer.
    rc, _, _ = sh('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal')
    summary['rustup'] = rc
    repo = f'{WORK}/fork'
    rc, out, _ = sh(f'cd {WORK} && rm -rf fork && git clone -q https://github.com/BOSSDOTCOM/fork && cd fork && '
                    f'git checkout -q {COMMIT} && git log --oneline -1')
    summary['head'] = out.strip()[-120:]
    rc, out, secs = sh(f'cd {repo}/tools/train && cargo build --release --locked --features cuda', env=env)
    summary['build'] = {'rc': rc, 'seconds': secs, 'tail': out[-400:] if rc else ''}
    train = f'{repo}/tools/train/target/release/fork-train'
    desc = json.load(open(f'{repo}/tools/nnue/{ARCH}.json')) if rc == 0 else {'table': []}
    spec = f'--arch {ARCH} --buckets ' + ','.join(map(str, desc['table']))
    save()
    # 2. The inputs.
    sealed, began = {}, time.time()
    for m in MANIFESTS_8B:
        _, text, _ = sh(f'cd {repo} && git show {COMMIT_8B}:data/manifests/{m}.json')
        for b in json.loads(text)['batches']:
            for s in b:
                sealed[s['file']] = s['sha256']
    for m in MANIFESTS_NEW:
        for b in json.load(open(f'{repo}/data/manifests/{m}.json'))['batches']:
            for s in b:
                sealed[s['file']] = s['sha256']
    sealed.update(POS1)
    by_name, twice = {}, []
    for d in NEEDED:
        if d in found:
            for p in sorted(glob.glob(f'{found[d]}/**/*.vf', recursive=True)):
                n = os.path.basename(p)
                twice += [n] if n in by_name else []
                by_name.setdefault(n, p)
    mismatch = [n for n, p in by_name.items() if n not in sealed or sealed[n] != sha256(p)]
    missing = sorted(set(sealed) - set(by_name))
    base = sorted(n for n in by_name if not n.endswith('-val.vf') and not is_derived(n) and n not in EVAL_ONLY)
    files = td90_files(base)
    unresolved = [n for n in files + [VAL, VAL_BLEND] if n not in by_name]
    init = glob.glob(f'{found.get("fork-r8b-rft-init", DATA)}/**/{INIT["weights"]}', recursive=True)
    init_ok = len(init) == 1 and sha256(init[0]) == INIT['sha256']
    summary['inputs'] = {'files': len(by_name), 'sealed': len(sealed), 'mismatches': mismatch, 'missing': missing,
                         'names_twice': twice, 'unresolved': unresolved, 'train_files': len(files),
                         'new_files': [n for n in files if is_new(n)],
                         'train_bytes': sum(os.path.getsize(by_name[n]) for n in files if n in by_name),
                         'init_ok': init_ok, 'hash_seconds': round(time.time() - began, 1)}
    summary['inputs']['ok'] = not (mismatch or missing or twice or unresolved) and init_ok
    save()
    ok = summary['build']['rc'] == 0 and summary['inputs']['ok']
    # 3. The loader on the new parts (the trainer's own filter).
    if summary['build']['rc'] == 0:
        stats = {}
        for part, prefix in NEW_PARTS.items():
            names = [n for n in base if n.startswith(prefix)]
            if not names:
                stats[part] = {'files': 0}
                continue
            rc, out, secs = sh(f'{train} stats ' + ' '.join(f'--data {by_name[n]}' for n in names))
            kept = next((int(l.split()[1]) for l in out.splitlines() if l.startswith('positions ')), None)
            stats[part] = {'files': len(names), 'rc': rc, 'kept': kept, 'seconds': secs,
                           'tail': '' if kept is not None else out[-300:]}
            save()
        summary['loader'] = stats
        save()

    def score(weights, val, out_dir, result_weight, device=0):
        shutil.rmtree(out_dir, ignore_errors=True)
        rc, out, secs = sh(f'{train} train {spec} --data {by_name[files[0]]} --val {val} '
                           f'--val-positions {VAL_POSITIONS} --scale {SCALE} --result-weight {result_weight} '
                           f'--init-weights {weights} --superbatches 0 --device {device} --threads 2 --out {out_dir}',
                           env=env)
        loss = None
        if rc == 0 and os.path.exists(f'{out_dir}/val.txt'):
            first = open(f'{out_dir}/val.txt').readline().split()
            loss = float(first[1]) if first and first[0] == '0' else None
        return {'rc': rc, 'loss': loss, 'seconds': secs, 'tail': '' if loss is not None else out[-300:]}

    if ok:
        c = {'warm_start': score(init[0], by_name[INIT['val']], f'{WORK}/init-check', 0.5),
             'reference': score(init[0], by_name[VAL_BLEND], f'{WORK}/init-ref', 0.0)}
        c['ok'] = c['warm_start']['loss'] is not None and abs(c['warm_start']['loss'] - INIT['loss']) <= TOLERANCE \
            and c['reference']['loss'] is not None
        summary['checks'] = c
        save()
    # 4. A few superbatches, two runs side by side.
    summary['runs'] = {}

    def run(seed, device):
        out_dir = f'{WORK}/run-{seed}'
        shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir)
        cmd = (f'{train} train {spec} --data {" ".join(by_name[n] for n in files)} --start 1 '
               f'--superbatches {SUPERBATCHES} --lr 0.0001 --lr-step 180 --seed {seed} --patience {SUPERBATCHES + 1} '
               f'--scale {SCALE} --result-weight 0.0 --batch {BATCH} --batches {BATCHES} --interleave '
               f'--val {by_name[VAL_BLEND]} --val-positions {VAL_POSITIONS} --threads 2 --init-weights {init[0]} '
               f'--device {device} --id s512pp-pre{seed} --out {out_dir} >> {out_dir}/train.log 2>&1')
        began = time.time()
        proc = subprocess.Popen(cmd, shell=True, env={**os.environ, **env})
        seen, times = 0, []
        while proc.poll() is None:
            if os.path.exists(f'{out_dir}/val.txt'):
                n = sum(1 for _ in open(f'{out_dir}/val.txt'))
                if n > seen:
                    times += [round(time.time() - began, 1)] * (n - seen)
                    seen = n
            for d in glob.glob(f'{out_dir}/s512pp-pre{seed}-*'):
                if os.path.exists(f'{d}/superbatch.txt'):  # a finished checkpoint: not kept
                    shutil.rmtree(d, ignore_errors=True)
            time.sleep(2)
        curve = []
        if os.path.exists(f'{out_dir}/val.txt'):
            curve = [(int(l.split()[0]), float(l.split()[1])) for l in open(f'{out_dir}/val.txt') if len(l.split()) == 2]
        laps = [round(b - a, 1) for a, b in zip(times, times[1:])]
        rec = {'seed': seed, 'device': device, 'rc': proc.returncode, 'seconds': round(time.time() - began, 1),
               'val_curve': curve, 'val_seen_at': times, 'superbatch_seconds': laps,
               'tail': open(f'{out_dir}/train.log').read()[-1500:]}
        with lock:
            summary['runs'][seed] = rec
        save()

    if ok and summary['checks']['ok']:
        threads = [threading.Thread(target=run, args=(seed, seed - 1)) for seed in (1, 2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        ref = summary['checks']['reference']['loss']
        starts = {s: (r['val_curve'][0][1] if r['val_curve'] and r['val_curve'][0][0] == 0 else None)
                  for s, r in summary['runs'].items()}
        laps = [x for r in summary['runs'].values() for x in r['superbatch_seconds'][1:]]  # the first lap holds setup
        summary['verdict'] = {
            'sources_attached': summary['mounted'], 'sources_named': len(NEEDED) + len(EXTRA),
            'inputs_ok': summary['inputs']['ok'],
            'loader_ok': all(v.get('kept') for v in summary.get('loader', {}).values()),
            'superbatch_0_ok': all(s is not None and abs(s - ref) <= TD_START_TOLERANCE for s in starts.values()),
            'runs_ok': all(r['rc'] == 0 for r in summary['runs'].values()),
            'superbatch_seconds_median': sorted(laps)[len(laps) // 2] if laps else None}
    summary['seconds'] = round(time.time() - summary['began'], 1)
    shutil.rmtree(repo, ignore_errors=True)
    save()
    print(json.dumps(summary, indent=1)[:20000])


if __name__ == '__main__':
    if '--plan' in sys.argv:
        plan()
    elif not os.path.isdir(DATA):
        sys.exit(f'{DATA} not found: this script runs inside the Kaggle session (--plan)')
    else:
        try:
            session()
        except Exception:
            os.makedirs(RESULT, exist_ok=True)
            open(f'{RESULT}/error.txt', 'w').write(traceback.format_exc())
            raise
