# SPDX-License-Identifier: GPL-3.0-or-later

"""The parity test's trainer leg T on Kaggle (DESIGN.md §5.3, deliverable 6):
bullet's own float evaluation of tests/nnue/parity.epd with a training
run's best weights. Pushed with `kaggle kernels push` with the training
kernel's output attached as a kernel source (its result/weights.bin); writes
/kaggle/working/parity-trainer.txt ("FEN | raw output" per position).
"""
import glob
import os
import subprocess

COMMIT = 'phase-4'
WORK = '/kaggle/working/t'
home = os.path.expanduser('~')
env = {**os.environ, 'PATH': f"{home}/.cargo/bin:{os.environ['PATH']}", 'CUDA_PATH': '/usr/local/cuda',
       'RUSTFLAGS': '-L /usr/local/nvidia/lib64'}


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
    print(cmd[:120], '->', r.returncode, (r.stdout + r.stderr)[-800:])
    return r.returncode


os.makedirs(WORK, exist_ok=True)
weights = sorted(glob.glob('/kaggle/input/**/result/weights.bin', recursive=True))
print('weights:', weights)
sh('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal')
sh(f'cd {WORK} && rm -rf fork && git clone -q https://github.com/BOSSDOTCOM/fork && cd fork && git checkout -q {COMMIT}'
   ' && git log --oneline -1')
rc = sh(f'cd {WORK}/fork/tools/train && cargo build --release --locked --features cuda')
if rc == 0 and weights:
    sh(f'{WORK}/fork/tools/train/target/release/fork-train eval --weights {weights[0]} '
       f'--epd {WORK}/fork/tests/nnue/parity.epd --out /kaggle/working/parity-trainer.txt')
subprocess.run(f'rm -rf {WORK}', shell=True)
