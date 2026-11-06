# SPDX-License-Identifier: GPL-3.0-or-later
"""The Control Center's settings. Paths are written relative to the home folder (~) and resolved at run
time, so nothing here names a user. A JSON file in the state folder (%LOCALAPPDATA%/ForkControlCenter/
config.json) overrides any key.

Standing data-generation settings (DESIGN.md section 5.3, deliverable 2, "Standing data-generation setting
since 2026-10-31"): 20,000 nodes, the score adjudication at 700 cp for 8 plies, and the split search
--save-percent 50 --unsaved-nodes 4000 --check-nodes 2000; hash 1 MB and 1,024 MB shards as every part so
far; 10 threads ("Datagen takes 10 of the 12 threads", section 5.3, owner's answers of 2026-10-28, 3).

The disk margin is the app's own rule, not a documented number (DESIGN.md only says "Disk is rechecked
before each long datagen run"): a start needs room for the part's remaining target at the measured
bytes per position on WSL's disk and twice that on C: (WSL's virtual disk grows on C:, and the sealed copy
goes there too), plus disk_reserve_gb on each. UNVERIFIED as policy: the owner may set another margin.
"""
import json
import os
from pathlib import Path

DEFAULTS = {
    'repo': '~/fork',                      # the phase-4 checkout whose docs, manifests and tools are read
    'branch': 'phase-4',                   # the default engine comes from this branch
    'python': '~/fork/.venv/Scripts/python.exe',
    'kaggle': '~/fork/.venv/Scripts/kaggle.exe',
    'windows_jobs': '~/fork-jobs',         # the Windows supervisor's folder (SPRT drivers, measurements)
    'wsl_distro': 'Ubuntu',
    'wsl_jobs': '~/fork-jobs',             # in WSL: the datagen supervisor's folder
    'wsl_data': '~/fork-data',             # in WSL: one folder per part, gen<N><letter>
    'wsl_build_clone': '~/fork-cc-build',  # in WSL: the clone the app builds new default engines in
    'copies': '~/fork-data/kaggle',        # Windows: each sealed part's complete games, <copies>/<part>/
    'training_out': '~/fork-data/kaggle',  # Windows: downloaded Kaggle outputs (*/result/*/run.json)
    'gauntlets': '~/fork-data/gauntlet',   # Windows: downloaded gauntlet runs (run-*/ordo.txt)
    'manifests_out': None,                 # where seals write data/manifests/<part>.json (None: the repo's)
    'poll_seconds': 30,
    'github_seconds': 60,
    'kaggle_seconds': 120,
    'kaggle_kernels': 4,                   # the most recently run kernels whose status is polled
    'threads': 10,
    'val_worker': 'last',                  # the held-out worker's shard is renamed *-val.vf, as every part's
    'bytes_per_position': 4.6,             # measured: g3d 13,362,808 bytes / 3,047,986 positions = 4.38
    'disk_reserve_gb': 20,
    'disk_warn_gb': 20,
    'memory_warn_percent': 90,
    'stop_grace_seconds': 20,
    'standing': {'nodes': 20000, 'hash_mb': 1, 'shard_mb': 1024, 'adjudicate_cp': 700, 'adjudicate_plies': 8,
                 'save_percent': 50, 'unsaved_nodes': 4000, 'check_nodes': 2000},
    'tables_wsl': '~/fork-tools/syzygy/3-4-5',
    'openings_wsl': '~/fork-data/openings',
    'engine_paths': ['src', 'cmake', 'CMakeLists.txt', 'CMakePresets.json', 'nets', 'third_party'],
}


def state_dir():
    base = os.environ.get('FORK_CC_STATE') or os.path.join(os.environ.get('LOCALAPPDATA') or str(Path.home()),
                                                          'ForkControlCenter')
    p = Path(base)
    return p


def expand(path):
    """A Windows-side setting: ~ is this user's home folder."""
    return Path(os.path.expanduser(path)) if path else None


def load(overrides=None):
    cfg = json.loads(json.dumps(DEFAULTS))
    f = state_dir() / 'config.json'
    try:
        cfg.update(json.loads(f.read_text(encoding='utf-8')))
    except (OSError, ValueError):
        pass
    if overrides:
        cfg.update(overrides)
    return cfg


def to_wsl(path):
    """C:\\Users\\x\\y -> /mnt/c/Users/x/y (a Windows path as WSL sees it)."""
    p = str(path).replace('\\', '/')
    if len(p) >= 2 and p[1] == ':':
        return f'/mnt/{p[0].lower()}{p[2:]}'
    return p


def wsl_unc(distro, wsl_home, wsl_path):
    """A WSL path (~ expanded with WSL's own home) as Windows reads it: \\\\wsl.localhost\\<distro>\\..."""
    p = wsl_path.replace('~', wsl_home, 1) if wsl_path.startswith('~') else wsl_path
    return Path('\\\\wsl.localhost\\' + distro + p.replace('/', '\\'))
