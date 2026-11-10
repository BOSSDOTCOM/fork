# SPDX-License-Identifier: GPL-3.0-or-later

"""Retrain 8b's training inputs (docs/research/retrain-8b/plan.md; owner,
2026-11-09): everything the Kaggle kernel tools/train/kaggle/retrain_8b.py
mounts beyond the datasets already on Kaggle, built, checked, hashed into
manifests and uploaded in two stages.

`pre` (before g4's seal; nothing in it depends on g4):
1. Every source file checked against its sealed manifest's SHA-256: item
   8a's training files (its kernel's MANIFESTS) and the sealed parts g3h,
   g3i and g3j, read from the local copies under --kaggle.
2. g4s1's new-part splits (snapshot_parts.py hold): the first 60 games of
   g3h's, g3i's and g3j's validation shards held for g4s1-val.vf, the rest
   trains; from g3j-w05-val.vf the games of idea 51's held-out set H and the
   ensemble teacher's H2 (--exclude) are kept out of training too.
3. Blend copies (td_labels.py blend, W = 0.5, S = 92) of every training file
   older than g3j (8a's, g3h's, g3i's and their rests), the endgame slice
   excepted (every arm reads the slice unchanged): the TD arms train at
   --result-weight 0, and these copies give the older data the control's
   target there. Each copy checked (td_labels.py check, every 100th game
   recomputed).
4. TD copies (td_labels.py labels, S = 92, the default definition: lambda 0
   is the record's own score) of g3j's training shards and its rest, at each
   --lam (0.8 and 0.9); each checked the same way.
5. Idea 52's arm (committee_sites.py arm, the declared settings).
6. Manifests in --manifests (data/manifests): g4s1-pre.json (the rests),
   r8b-blend.json (three batches, one dataset each), r8b-arms.json (the TD
   copies and idea 52's files, with the arm's record), and the upload folders
   under OUT/up/ (hard links): fork-g3hij (g3h, g3i, g3j whole, the rests,
   S512ppr3's float weights), fork-r8b-blend-1..3, fork-r8b-arms.

`post` (after g4's seal, one command): g4's shards checked against
data/manifests/g4.json; g4's validation shard split (60 games held); g4s1-val.vf
(g3s3-val.vf's 32 streams and the held games of g3h, g3i, g3j and g4, one
game at a time) and its blend copy (the TD arms' validation file); the TD
copies of g4's training shards and its rest; manifests g4s1.json and
r8b-g4.json; upload folders fork-g4 (the sealed part whole) and fork-r8b-g4.

`upload STAGE --owner NAME`: creates each of the stage's datasets that the
account does not hold yet (never re-uploads one), waits until Kaggle has it
ready, downloads it back into an empty folder and checks every file's
SHA-256 against the manifests; exit 1 on any difference.

Each step is skipped when its outputs and their check records exist, so a
stopped run resumes. Run as a jobctl job (types slice, upload) at low
priority.

    retrain_8b_inputs.py pre  --kaggle DIR --out DIR --i52 DIR --exclude H.jsonl H2.jsonl [--manifests DIR]
    retrain_8b_inputs.py post --kaggle DIR --out DIR [--g4 g4] [--g4-dir DIR] [--g4-manifest FILE] [--manifests DIR]
    retrain_8b_inputs.py upload pre|post --out DIR --owner NAME [--kaggle-cli PATH] [--manifests DIR] [--also FILE...]
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OLD_MANIFESTS = ('g2s1', 'g3s1', 'g3b', 'g3c', 'g3d', 'g3e', 'g3s2', 'g3f', 'g3g', 'g3s3')  # item 8a's MANIFESTS
OLD_FOLDERS = ('g2s1', 'g3s1', 'g3rest', 'g3bcd', 'g3e', 'g3s2', 'g3f', 'g3g', 'g3s3')
NEW_PARTS = ('g3h', 'g3i', 'g3j')
TD_PARTS = ('g3j',)          # S512ppr3's parts (g4 at the seal)
SNAPSHOT = 'g4s1'
HOLD = 60
SCALE = 92                   # the trainer's --scale in 8a's recipe (and the TD pre-tests')
BLEND_WEIGHT = 0.5           # the recipe's --result-weight
LAMBDAS = (0.8, 0.9)         # the owner's 8b label arms
BASE_VAL = ('g3s3-val.vf', 32)   # g3s3-val.vf: g3s2-val's 30 streams and g3f's and g3g's, 60 games each
I52_POOL = ('g3j-w00', 'g3j-w01', 'g3j-w02', 'g3j-w03', 'g3j-w04')
I52_FACTOR, I52_HOLD, I52_SEED, I52_TARGET = 16, 10000, 20261109, 'blend'   # the plan's declared arm
INIT = ('g3s3-out/result/avg-r1/weights.bin', 's512ppr3-weights.bin',
        '022158587653ba32d5830ce4f6a3b7e1a88283e7cb9e3c507936ad0c8b37ecc3')
PY = sys.executable
sys.path.insert(0, str(HERE))
import snapshot_parts  # noqa: E402


def lower_priority():
    """Below-normal priority for this process and the tools it starts (they inherit it): data generation and
    the measurement jobs come first on the shared machine."""
    if os.name == 'nt':
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    else:
        os.nice(10)


def log(text):
    print(f'{time.strftime("%I:%M:%S %p")} {text}', flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def shards_of(manifests, name):
    return [s for b in json.loads((manifests / f'{name}.json').read_text(encoding='utf-8'))['batches'] for s in b]


def is_slice(name):
    """The Syzygy endgame slice's files (g3s2.json: slice1-01..09.vf and g3s2-slice1-00-rest.vf)."""
    return 'slice' in name


def td_name(lam, name):
    return f'td{round(lam * 100):02d}-{name}'


def run(tool, *args):
    """A tool of this folder or tools/measure as a child process (its output to this log); raises on failure."""
    r = subprocess.run([PY, '-I', str(tool), *map(str, args)], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if out:
        print(out[-2000:], flush=True)
    if r.returncode:
        raise SystemExit(f'{Path(tool).name} {args[0]} failed (exit {r.returncode})')
    return out


def index(folders):
    found = {}
    for d in folders:
        for p in sorted(Path(d).glob('*.vf')):
            found.setdefault(p.name, p)
    return found


def verify_sources(files, found, done_mark):
    """Each (name, sha256) against its local copy; a record of the pass is kept so a resumed run skips it."""
    if done_mark.exists() and json.loads(done_mark.read_text())['files'] == sorted(n for n, _ in files):
        log(f'sources already verified ({len(files)} files)')
        return
    bad = [n for n, h in files if n not in found or sha256(found[n]) != h]
    if bad:
        raise SystemExit(f'sources missing or not matching their manifests: {bad[:10]}')
    done_mark.write_text(json.dumps({'files': sorted(n for n, _ in files)}) + '\n')
    log(f'{len(files)} source files match their sealed SHA-256')


def checked_copy(kind, source, dest, param):
    """td_labels.py blend or labels, then td_labels.py check; skipped when both records exist."""
    td = HERE / 'td_labels.py'
    mark = dest.with_name(dest.name + '.check.json')
    if dest.exists() and mark.exists() and dest.with_name(dest.name + '.json').exists():
        return
    if kind == 'blend':
        run(td, 'blend', source, '--out', dest, '--weight', param, '--scale', SCALE)
        out = run(td, 'check', source, dest, '--mode', 'blend', '--weight', param, '--scale', SCALE, '--sample', 100)
    else:
        run(td, 'labels', source, '--out', dest, '--lam', param, '--scale', SCALE)
        out = run(td, 'check', source, dest, '--mode', 'td', '--lam', param, '--scale', SCALE, '--sample', 100)
    mark.write_text(out.splitlines()[-1] + '\n')


def link(src, folder):
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / Path(src).name
    if not dest.exists():
        try:
            os.link(src, dest)
        except OSError:
            shutil.copy2(src, dest)


def record(name, files, manifests, note, extra=None):
    out = run(HERE / 'snapshot_parts.py', 'record', name, *files, '--out', manifests / f'{name}.json', '--note', note)
    if extra:
        path = manifests / f'{name}.json'
        rec = json.loads(path.read_text(encoding='utf-8'))
        rec.update(extra)
        path.write_text(json.dumps(rec, indent=1) + '\n', encoding='utf-8')
    return out


def pre(a):
    out, manifests = a.out, a.manifests
    out.mkdir(parents=True, exist_ok=True)
    found = index([a.kaggle / f for f in OLD_FOLDERS + NEW_PARTS])
    old = [s for m in OLD_MANIFESTS for s in shards_of(manifests, m)]
    new = [s for m in NEW_PARTS for s in shards_of(manifests, m)]
    verify_sources([(s['file'], s['sha256']) for s in old + new], found, out / 'sources-pre.ok')
    init = a.kaggle / INIT[0]
    if sha256(init) != INIT[2]:
        raise SystemExit(f'{init}: not S512ppr3\'s float weights')

    # 2. The new parts' splits.
    splits = out / 'g3hij'
    rests = []
    for part in NEW_PARTS:
        val = [s['file'] for s in shards_of(manifests, part) if s['file'].endswith('-val.vf')]
        assert len(val) == 1, part
        stem = val[0][:-3]
        rest = splits / f'{SNAPSHOT}-{stem}-rest.vf'
        if not rest.exists():
            run(HERE / 'snapshot_parts.py', 'hold', found[val[0]], '--games', HOLD, '--prefix', SNAPSHOT, '--out',
                splits, '--exclude', *a.exclude)
            log(f'{part}: {HOLD} games held, the rest is {rest.name}')
        rests.append(rest)

    # 3. Blend copies of every training file older than S512ppr3's parts, the slice excepted.
    older = [s['file'] for s in old + new if not s['file'].endswith('-val.vf') and not is_slice(s['file'])
             and not s['file'].startswith(TD_PARTS)]
    older_paths = [found[n] for n in older] + [r for r in rests if not r.name.startswith(
        tuple(f'{SNAPSHOT}-{p}-' for p in TD_PARTS))]
    blend = out / 'blend'
    blend.mkdir(exist_ok=True)
    for k, src in enumerate(older_paths):
        checked_copy('blend', src, blend / f'bl-{src.name}', BLEND_WEIGHT)
        log(f'blend {k + 1}/{len(older_paths)}: {src.name}')

    # 4. TD copies of S512ppr3's part g3j (training shards and its rest).
    arms = out / 'arms'
    arms.mkdir(exist_ok=True)
    newest = [found[s['file']] for s in new if s['file'].startswith(TD_PARTS) and not s['file'].endswith('-val.vf')]
    newest += [r for r in rests if r.name.startswith(tuple(f'{SNAPSHOT}-{p}-' for p in TD_PARTS))]
    for lam in a.lam:
        for src in newest:
            checked_copy('td', src, arms / td_name(lam, src.name), lam)
            log(f'TD({lam}) {src.name}')

    # 5. Idea 52's arm.
    i52 = arms / 'i52'
    if not (i52 / 'arm.json').exists():
        run(REPO / 'tools' / 'measure' / 'committee_sites.py', 'arm', a.i52, i52, '--pool', a.kaggle / 'g3j',
            '--shards', *I52_POOL, '--factor', I52_FACTOR, '--hold', I52_HOLD, '--seed', I52_SEED, '--target',
            I52_TARGET, '--scale', SCALE)
        log("idea 52's arm written and read back")
    arm = json.loads((i52 / 'arm.json').read_text(encoding='utf-8'))

    # 6. Manifests and upload folders.
    record(f'{SNAPSHOT}-pre', rests, manifests,
           f"{SNAPSHOT}'s new-part rests before g4's seal (retrain_8b_inputs.py pre): the first {HOLD} games of each "
           "validation shard held for the snapshot's validation file, idea 51's H and the teacher's H2 games kept "
           "out of g3j-w05-val's rest",
           {'held': [snapshot_parts.stats_of(p.name, p.read_bytes()) for p in sorted(splits.glob('*-held.vf'))],
            'exclude': {f'{Path(p).parent.name}/{Path(p).name}': sha256(p) for p in a.exclude}})
    bl = sorted(blend.glob('bl-*.vf'))
    record('r8b-blend', bl, manifests,
           f'blend copies (W = {BLEND_WEIGHT}, S = {SCALE}) of every training file older than g3j, the slice '
           'excepted, for the TD arms at --result-weight 0 (td_labels.py blend, each checked)')
    td_files = sorted(arms.glob('td*.vf'))
    i52_files = [i52 / n for n in sorted(arm['files'])]
    record('r8b-arms', td_files + i52_files, manifests,
           f'TD({", ".join(map(str, a.lam))}) copies of g3j (td_labels.py labels, S = {SCALE}, each checked) and '
           "idea 52's arm (committee_sites.py arm)",
           {'arm': {k: v for k, v in arm.items() if k != 'files'}})
    up = out / 'up-pre'
    for part in NEW_PARTS:
        for s in shards_of(manifests, part):
            link(found[s['file']], up / 'fork-g3hij')
    for r in rests:
        link(r, up / 'fork-g3hij')
    if not (up / 'fork-g3hij' / INIT[1]).exists():
        shutil.copy2(init, up / 'fork-g3hij' / INIT[1])
    for k in range(0, len(bl), 50):
        for p in bl[k:k + 50]:
            link(p, up / f'fork-r8b-blend-{k // 50 + 1}')
    for p in td_files + i52_files:
        link(p, up / 'fork-r8b-arms')
    log(f'pre done: upload folders under {up}')
    return 0


def post(a):
    out, manifests = a.out, a.manifests
    part = a.g4
    g4dir = a.g4_dir or a.kaggle / part
    found = index([g4dir, out / 'g3hij'] + [a.kaggle / f for f in OLD_FOLDERS])
    g4 = [s for b in json.loads((a.g4_manifest or manifests / f'{part}.json').read_text(encoding='utf-8'))['batches']
          for s in b]
    verify_sources([(s['file'], s['sha256']) for s in g4], found, out / f'sources-{part}.ok')
    split = out / part
    val = [s['file'] for s in g4 if s['file'].endswith('-val.vf')]
    assert len(val) == 1, val
    rest = split / f'{SNAPSHOT}-{val[0][:-3]}-rest.vf'
    if not rest.exists():
        run(HERE / 'snapshot_parts.py', 'hold', found[val[0]], '--games', HOLD, '--prefix', SNAPSHOT, '--out', split)
    held = sorted((out / 'g3hij').glob('*-held.vf')) + sorted(split.glob('*-held.vf'))
    valfile = split / f'{SNAPSHOT}-val.vf'
    if not valfile.exists():
        run(HERE / 'snapshot_parts.py', 'val', '--base', found[BASE_VAL[0]], '--streams', BASE_VAL[1], '--held',
            *held, '--out', valfile)
    checked_copy('blend', valfile, split / f'bl-{valfile.name}', BLEND_WEIGHT)
    newest = [found[s['file']] for s in g4 if not s['file'].endswith('-val.vf')] + [rest]
    for lam in LAMBDAS:
        for src in newest:
            checked_copy('td', src, split / td_name(lam, src.name), lam)
            log(f'TD({lam}) {src.name}')
    files = [rest, valfile, split / f'bl-{valfile.name}'] + sorted(split.glob('td*.vf'))
    record('r8b-g4', files, manifests,
           f"g4's rest, {SNAPSHOT}-val.vf (g3s3-val's 32 streams and {len(held)} held sources), its blend copy "
           f'(the TD arms\' validation), the TD copies of g4 (retrain_8b_inputs.py post)')
    up = out / 'up-post'
    for s in g4:
        link(found[s['file']], up / f'fork-{part}')
    for p in files:
        link(p, up / 'fork-r8b-g4')
    log(f'post done: upload folders under {up}')
    return 0


def kaggle(cli, *args, timeout=3600):
    r = subprocess.run([cli, *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)


def upload(a):
    up = a.out / f'up-{a.stage}'
    want = {}
    for m in sorted(a.manifests.glob('*.json')) + list(a.also):
        try:
            for b in json.loads(m.read_text(encoding='utf-8')).get('batches', []):
                for s in b:
                    want[s['file']] = s['sha256']
        except (ValueError, AttributeError, TypeError):
            continue
    want[INIT[1]] = INIT[2]
    rc, mine = kaggle(a.kaggle_cli, 'datasets', 'list', '--mine', '--page-size', '100')
    if rc:
        raise SystemExit('kaggle datasets list failed')
    held = {line.split()[0].split('/')[-1] for line in mine.splitlines()[2:] if line.strip()}
    bad = []
    for folder in sorted(p for p in up.iterdir() if p.is_dir()):
        name = folder.name
        dataset = f'{a.owner}/{name}'
        names = sorted(p.name for p in folder.iterdir() if p.name != 'dataset-metadata.json')
        unknown = [n for n in names if n.endswith('.vf') and n not in want] + \
                  [n for n in names if n in want and sha256(folder / n) != want[n]]
        if unknown:
            raise SystemExit(f'{name}: files without a matching manifest entry: {unknown[:5]}')
        if name in held:
            log(f'{name}: already on Kaggle, not uploaded again')
        else:
            (folder / 'dataset-metadata.json').write_text(json.dumps(
                {'title': name, 'id': dataset, 'licenses': [{'name': 'other'}], 'keywords': ['synthetic']},
                indent=1) + '\n')
            rc, text = kaggle(a.kaggle_cli, 'datasets', 'create', '-p', str(folder), timeout=6 * 3600)
            log(f'{name}: create exit {rc}: {text.strip().splitlines()[-1] if text.strip() else ""}')
            if rc:
                raise SystemExit(f'{name}: upload failed')
        for _ in range(180):
            rc, st = kaggle(a.kaggle_cli, 'datasets', 'status', dataset, timeout=300)
            if st.strip().endswith('ready'):
                break
            time.sleep(60)
        else:
            raise SystemExit(f'{name}: not ready after 3 hours')
        back = a.out / f'back-{a.stage}' / name
        shutil.rmtree(back, ignore_errors=True)
        back.mkdir(parents=True)
        for attempt in range(6):
            rc, text = kaggle(a.kaggle_cli, 'datasets', 'download', dataset, '-p', str(back), '--unzip', timeout=7200)
            if rc == 0:
                break
            time.sleep(300)
        got = {p.name: p for p in back.rglob('*') if p.is_file()}
        miss = [n for n in names if n not in got or sha256(got[n]) != sha256(folder / n)]
        log(f'{name}: downloaded back, {len(names) - len(miss)} of {len(names)} files match')
        bad += miss
        shutil.rmtree(back, ignore_errors=True)
    if bad:
        raise SystemExit(f'files that did not come back intact: {bad[:10]}')
    log(f'upload {a.stage}: every dataset on Kaggle and checked')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    for name in ('pre', 'post'):
        p = sub.add_parser(name)
        p.add_argument('--kaggle', type=Path, required=True, help='the local copies (~/fork-data/kaggle)')
        p.add_argument('--out', type=Path, required=True)
        p.add_argument('--manifests', type=Path, default=REPO / 'data' / 'manifests')
    p = sub.choices['pre']
    p.add_argument('--i52', type=Path, required=True, help="idea 52's labelled sites (sites.jsonl, labels.tsv, stats.json)")
    p.add_argument('--exclude', type=Path, nargs='+', required=True, help="site files of H and H2")
    p.add_argument('--lam', type=float, nargs='+', default=list(LAMBDAS))
    p = sub.choices['post']
    p.add_argument('--g4', default='g4', help="g4's run name (its manifest data/manifests/<name>.json)")
    p.add_argument('--g4-dir', type=Path, help="g4's sealed copy (default KAGGLE/<name>)")
    p.add_argument('--g4-manifest', type=Path, help="g4's sealed manifest (default MANIFESTS/<name>.json)")
    p = sub.add_parser('upload')
    p.add_argument('stage', choices=('pre', 'post'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--owner', required=True, help='the Kaggle account name')
    p.add_argument('--kaggle-cli', default=str(REPO / '.venv' / 'Scripts' / 'kaggle.exe'))
    p.add_argument('--manifests', type=Path, default=REPO / 'data' / 'manifests')
    p.add_argument('--also', type=Path, nargs='*', default=[], help="more manifests (g4's, before it is committed)")
    a = ap.parse_args(argv)
    if a.command != 'upload':
        lower_priority()
    return {'pre': pre, 'post': post, 'upload': upload}[a.command](a)


if __name__ == '__main__':
    sys.exit(main())
