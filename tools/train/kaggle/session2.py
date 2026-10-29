# SPDX-License-Identifier: GPL-3.0-or-later

"""Kaggle test session 2 (DESIGN.md §5.3, deliverable 0): paste the whole
file into one cell of a private notebook (GPU T4 x2, internet on, a small
dataset of Fork's shards attached) and run it. It installs Rust (K2, K4),
builds tools/train with CUDA at the commit below (K3, K4), runs a short
training on the attached shards with checkpoints (K5, K17), resumes it from
its last checkpoint in the same session (K6's mechanism), evaluates the
parity positions with the trainer's own model (K15), and trains on both
GPUs at once (K18). It prints one JSON object at the end. It reads no
secret; outputs go to /kaggle/working.

Set DATA to the attached dataset's folder and COMMIT to the pushed commit.
"""
import glob
import json
import os
import subprocess
import time

COMMIT = 'phase-4'  # branch or commit pushed to github.com/BOSSDOTCOM/fork
DATA = '/kaggle/input'  # attached datasets (shards *.vf anywhere below; *-val.vf held out)
WORK = '/kaggle/working/s2'
facts = {}


def sh(cmd, env=None, timeout=3600):
    t = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr)[-3000:], round(time.time() - t, 1)


os.makedirs(WORK, exist_ok=True)
home = os.path.expanduser('~')
cargo_env = {'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
             'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}

rc, out, secs = sh('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal')
facts['K2_K4_rustup'] = {'rc': rc, 'seconds': secs, 'tail': out[-300:]}
rc, out, secs = sh(f'cd {WORK} && rm -rf fork && git clone -q https://github.com/BOSSDOTCOM/fork && '
                   f'cd fork && git checkout -q {COMMIT} && git log --oneline -1')
facts['clone'] = {'rc': rc, 'seconds': secs, 'head': out.strip()[-200:]}
rc, out, secs = sh(f'cd {WORK}/fork/tools/train && cargo build --release --locked --features cuda',
                   env=cargo_env, timeout=5400)
facts['K4_build'] = {'rc': rc, 'seconds': secs, 'tail': out[-800:]}
train = f'{WORK}/fork/tools/train/target/release/fork-train'
found = sorted(glob.glob(f'{DATA}/**/*.vf', recursive=True))
shards = [p for p in found if not p.endswith('-val.vf')]
val = [p for p in found if p.endswith('-val.vf')]
facts['shards'] = len(shards)
facts['val_shards'] = len(val)
facts['gpus'] = sh('nvidia-smi --query-gpu=name,memory.total --format=csv,noheader')[1].strip()

if rc == 0 and shards:
    data = ' '.join(shards)
    common = f'--data {data} --scale 400 --batch 16384 --batches 512 --lr-step 18 --threads 3'
    if val:
        common += f' --val {val[0]} --val-positions 100000 --patience 3'
    rc, out, secs = sh(f'{train} loader --data {data} --positions 2000000', env=cargo_env)
    facts['K17_loader_one_thread'] = {'rc': rc, 'out': out.strip()[-200:]}
    rc, out, secs = sh(f'{train} check --out {WORK}/check', env=cargo_env)
    facts['check'] = {'rc': rc, 'out': out.strip()[-200:]}
    rc, out, secs = sh(f'{train} train {common} --superbatches 2 --out {WORK}/run', env=cargo_env, timeout=7200)
    facts['K5_K17_train_2x512x16384'] = {'rc': rc, 'seconds': secs,
                                         'positions_per_s': round(2 * 512 * 16384 / max(secs, 1)), 'tail': out[-600:]}
    rc, out, secs = sh(f'{train} train {common} --start 3 --superbatches 3 --resume {WORK}/run/b0-2 '
                       f'--out {WORK}/run', env=cargo_env, timeout=3600)
    facts['K6_resume_in_session'] = {'rc': rc, 'seconds': secs, 'tail': out[-400:]}
    epd = f'{WORK}/fork/tests/datagen_openings.epd'
    rc, out, secs = sh(f'{train} eval --checkpoint {WORK}/run/b0-3 --epd {epd} --out {WORK}/parity-trainer.txt',
                       env=cargo_env)
    facts['K15_eval'] = {'rc': rc, 'lines': sum(1 for _ in open(f'{WORK}/parity-trainer.txt')) if rc == 0 else 0,
                         'tail': out[-300:]}
    both = (f'{train} train {common} --superbatches 1 --device 0 --out {WORK}/d0 > {WORK}/d0.log 2>&1 & '
            f'{train} train {common} --superbatches 1 --device 1 --out {WORK}/d1 > {WORK}/d1.log 2>&1; wait; '
            f'tail -2 {WORK}/d0.log {WORK}/d1.log')
    rc, out, secs = sh(both, env=cargo_env, timeout=7200)
    facts['K18_two_gpus_1x512x16384_each'] = {'rc': rc, 'seconds': secs, 'tail': out[-500:]}
    facts['files'] = sorted(os.path.relpath(p, WORK) for p in glob.glob(f'{WORK}/run/**/*', recursive=True))[:40]
    for name in ('val.txt', 'stopped-early.txt'):
        p = f'{WORK}/run/{name}'
        if os.path.exists(p):
            facts[name] = open(p).read()[-500:]
with open('/kaggle/working/session2.json', 'w') as f:
    json.dump(facts, f, indent=1)
print(json.dumps(facts, indent=1))
