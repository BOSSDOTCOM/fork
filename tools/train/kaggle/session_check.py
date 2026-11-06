# SPDX-License-Identifier: GPL-3.0-or-later

"""The automatic part of the Kaggle test session (DESIGN.md §5.3,
deliverable 0). Paste the whole file into one notebook cell (GPU session,
internet on) and run it; it prints the facts behind checklist items K2,
K3, K4, K11 and K17's core count as one JSON object at the end, to paste
into the KB record. It reads no secret, prints no account data and writes
nothing.
"""
import glob
import json
import os
import platform
import shutil
import subprocess
import urllib.request


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return f'unavailable: {e}'


def reachable(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status
    except Exception as e:  # noqa: BLE001 - any failure is the answer
        return f'failed: {e}'


def cuda_libraries():
    """The CUDA libraries bullet links (cuda, cudart, nvrtc, cublas), from
    the loader cache and from the usual directories (Kaggle may keep
    libcuda outside the cache)."""
    names = ('libcuda.so', 'libcudart', 'libnvrtc', 'libcublas')
    cached = [l.strip() for l in run(['ldconfig', '-p']).splitlines() if any(n in l for n in names)]
    found = []
    for d in ('/usr/local/nvidia/lib64', '/usr/local/cuda/lib64', '/usr/local/cuda/targets/x86_64-linux/lib',
              '/usr/lib/x86_64-linux-gnu', '/usr/lib64'):
        for n in names:
            found += glob.glob(os.path.join(d, n + '*'))
    return {'ldconfig': cached, 'files': sorted(set(found))}


def main():
    smi = run(['nvidia-smi'])
    facts = {
        'K2_internet': {u: reachable(u) for u in ('https://static.rust-lang.org/rustup/dist/',
                                                  'https://github.com/', 'https://crates.io/')},
        'K3_gpus': run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total',
                        '--format=csv,noheader']).splitlines(),
        'K3_smi_header': [l for l in smi.splitlines() if 'CUDA Version' in l or 'Driver Version' in l],
        'K3_cuda_libraries': cuda_libraries(),
        'K3_nvcc': run(['nvcc', '--version']).splitlines()[-2:],
        'K3_cuda_env': {k: os.environ.get(k) for k in ('CUDA_PATH', 'CUDA_HOME', 'LD_LIBRARY_PATH')},
        'K4_rust_preinstalled': run(['rustc', '--version']),
        'K11_disk_free_gb': {p: round(shutil.disk_usage(p).free / 2**30, 1)
                             for p in ('/kaggle/working', '/kaggle/input', '/tmp', '/') if os.path.exists(p)},
        'K17_cpu_count': os.cpu_count(),
        'memory_gb': round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2**30, 1),
        'os': platform.platform(),
        'python': platform.python_version(),
        'glibc': '-'.join(platform.libc_ver()),
    }
    print(json.dumps(facts, indent=1, default=str))


main()
