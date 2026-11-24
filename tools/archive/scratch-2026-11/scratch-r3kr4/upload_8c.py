"""Bake-off round 3 option (a): the dataset fork-r3-init-8c (retrain 8c's possible candidates' float window-average weights), uploaded with a download-back check as retrain 8c's uploads were (fork-data/8c/upload.py): stage a
folder of hard links and dataset-metadata.json, create the private dataset bossdotcom/NAME (never re-upload one the
account holds), wait until ready, download each file back into an empty folder this script creates, check its SHA-256,
remove the folder. Exit 1 on any difference.

    python -I upload_init.py stage | push
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

S = Path('~/fork-runners/scratch-r3kr4').expanduser()
KAGGLE = str(Path('~/fork/.venv/Scripts/kaggle.exe').expanduser())
OWNER, NAME = 'bossdotcom', 'fork-r3-init-8c'
R8C = str(Path('~/fork-data/8c/a1-out/result').expanduser())
FILES = {'r8cc1-avg.bin': (f'{R8C}/avg-c1/weights.bin', 'cb3a989d96431ba1fddd8c6f91cf77be73787801919d664a6e95bb279ce579ad'),
         'r8cc2-avg.bin': (f'{R8C}/avg-c2/weights.bin', '350c38567f813af00e193b96ba163dc26289653341826c3fe470cd1fd60e7233'),
         'r8ceplo1-avg.bin': (f'{R8C}/avg-eplo1/weights.bin',
                              '248949506c64b87d30f1b7d92de2b4091a6b8c2c0c53cbe19e3309a6509ed533'),
         'r8ceplo2-avg.bin': (f'{R8C}/avg-eplo2/weights.bin',
                              '4118015e47ca596a966ee29821a43ae613155af9b0c9a95913d6fc81e06f3539')}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 22), b''):
            h.update(block)
    return h.hexdigest()


def log(msg):
    print(time.strftime('%I:%M:%S %p'), msg, flush=True)


def kaggle(*args, timeout=3600):
    r = subprocess.run([KAGGLE, *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def stage():
    up = S / 'up' / NAME
    if up.exists():
        sys.exit(f'{up} exists')
    up.mkdir(parents=True)
    for name, (src, h) in FILES.items():
        if sha256(src) != h:
            sys.exit(f'{src}: SHA-256 differs from {h}')
        os.link(src, up / name)
    (up / 'dataset-metadata.json').write_text(json.dumps(
        {'title': NAME, 'id': f'{OWNER}/{NAME}',
         'subtitle': 'Fork bake-off round 3: retrain 8c candidates float weights (warm-start sources)',
         'licenses': [{'name': 'other'}], 'keywords': ['synthetic']}, indent=1) + '\n', encoding='utf-8')
    log(f'staged {list(FILES)}')


def push():
    up = S / 'up' / NAME
    rc, out = kaggle('datasets', 'status', f'{OWNER}/{NAME}', timeout=120)
    if rc == 0 and 'ready' in out.lower():
        log('already on Kaggle, not re-uploaded; checking it')
    else:
        log('creating')
        rc, out = kaggle('datasets', 'create', '-p', str(up))
        if rc:
            sys.exit(f'create failed: {out[-500:]}')
        for _ in range(120):
            rc, out = kaggle('datasets', 'status', f'{OWNER}/{NAME}', timeout=120)
            if 'ready' in out.lower():
                break
            time.sleep(30)
        else:
            sys.exit(f'not ready after an hour: {out[-200:]}')
        log('ready')
    back = S / f'back-{NAME}'
    if back.exists():
        sys.exit(f'{back} exists')
    back.mkdir()
    bad = []
    for name, (_, h) in FILES.items():
        got = back / name
        for attempt in range(10):
            rc, out = kaggle('datasets', 'download', f'{OWNER}/{NAME}', '-f', name, '-p', str(back))
            if rc == 0 and not got.exists() and (back / f'{name}.zip').exists():
                import zipfile
                with zipfile.ZipFile(back / f'{name}.zip') as z:
                    z.extractall(back)
                (back / f'{name}.zip').unlink()
            if rc == 0 and got.exists():
                break
            log(f'{name}: download attempt {attempt + 1} failed; retrying in 30 s')
            time.sleep(30)
        ok = got.exists() and sha256(got) == h
        log(f'{name}: downloaded back, SHA-256 {"matches" if ok else "DIFFERS or missing"}')
        if not ok:
            bad.append(name)
        if got.exists():
            got.unlink()
    rc, out = kaggle('datasets', 'files', f'{OWNER}/{NAME}', timeout=300)
    log('listed: ' + ' '.join(line.split()[0] for line in out.splitlines()[2:] if line.split()))
    back.rmdir()
    log('checked' if not bad else f'CHECK FAILED {bad}')
    return 0 if not bad else 1


if __name__ == '__main__':
    if sys.argv[1] == 'stage':
        stage()
    else:
        sys.exit(push())
