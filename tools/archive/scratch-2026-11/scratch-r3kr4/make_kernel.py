"""Bake-off round 3 option (a): the Kaggle kernel folder from tools/train/kaggle/bakeoff_r3.py at a pushed commit
(as retrain 8c's make_kernel.py). The only edits are exact replacements: COMMIT set to the commit, with --smoke the
smoke switch, and with --source NAME FILE SHA256 DATASET another warm-start source in place of the kernel's own
SOURCE (r8ceplo2, file r8ceplo2-avg.bin of dataset fork-r3-init-8c, from retrain/r3-kr4 3650403 on: the owner's order
of 2026-11-14 ~5:55 PM EST; r8brft1 at earlier commits). Without --source the kernel's SOURCE and its dataset are used.

    python -I make_kernel.py --repo WORKTREE --commit HASH --out DIR [--arms A|X|X2] [--smoke]
        [--source NAME FILE SHA256 DATASET]
Session A (kr1 + pp1) is kernel fork-bakeoff-r3, session X (xl1) fork-bakeoff-r3-xl, X2 (xl2) fork-bakeoff-r3-xl2; -smoke after any for a smoke copy.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

# The full session: retrain 8c's A1 data sources but the i80 copies (no arm here reads them) and r8b-rft-init
# (8c's warm start), plus the source's dataset.
FULL_SOURCES = ['fork-g2s1', 'fork-g3s1', 'fork-g3rest', 'fork-g3bcd', 'fork-g3e', 'fork-g3s2', 'fork-g3f', 'fork-g3g',
                'fork-g3s3', 'fork-g3hij', 'fork-r8b-blend-1', 'fork-r8b-blend-2', 'fork-r8b-blend-3', 'fork-r8b-arms',
                'fork-g4', 'fork-r8b-g4', 'fork-ld-d20', 'fork-ld-d50', 'fork-ld-d100', 'fork-g4b', 'fork-r8c-td',
                'fork-r8c-filler', 'fork-slice1b', 'fork-g4c', 'fork-r8c-post', 'fork-r8c-cut']
# The smoke run's inputs: g3b-w00 (fork-g3bcd), bl-g3b-w00 (fork-r8b-blend-1), g4b-w00 (fork-g4b), the td90- copies
# (fork-r8c-td), the filler file and filler rest (fork-r8c-filler), slice1b-00 (fork-slice1b), g4s1-val and
# bl-g4s1-val (fork-r8b-g4).
SMOKE_SOURCES = ['fork-g3bcd', 'fork-r8b-blend-1', 'fork-g4b', 'fork-r8c-td', 'fork-r8c-filler', 'fork-slice1b',
                 'fork-r8b-g4']

ap = argparse.ArgumentParser()
ap.add_argument('--repo', required=True)
ap.add_argument('--commit', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--smoke', action='store_true')
ap.add_argument('--arms', choices=('A', 'X', 'X2'), default='A')
ap.add_argument('--source', nargs=4, metavar=('NAME', 'FILE', 'SHA256', 'DATASET'))
a = ap.parse_args()
full = subprocess.run(['git', '-C', a.repo, 'rev-parse', a.commit], capture_output=True, text=True,
                      check=True).stdout.strip()
src = subprocess.run(['git', '-C', a.repo, 'show', f'{full}:tools/train/kaggle/bakeoff_r3.py'], capture_output=True,
                     text=True, encoding='utf-8', check=True).stdout
old = "COMMIT = 'nets/r3-kr4'      # replaced by the pushed commit's hash before the push"
assert src.count(old) == 1
src = src.replace(old, f"COMMIT = '{full}'  # pushed")
if a.smoke:
    assert src.count('\nSMOKE = False ') == 1
    src = src.replace('\nSMOKE = False ', '\nSMOKE = True  ', 1)
if a.arms != 'A':
    old_set = "\nARM_SET = 'A' "
    assert src.count(old_set) == 1
    src = src.replace(old_set, f"\nARM_SET = '{a.arms}' ", 1)
SOURCE_RE = re.compile(r"SOURCE = \{'name': '([^']*)', 'weights': '([^']*)',\n +'sha256': '([0-9a-f]{64})',\n +"
                       r"'dataset': '([^']*)'\}")
found = SOURCE_RE.findall(src)
assert len(found) == 1, 'the kernel holds no single SOURCE block'
default_source = found[0]  # r8ceplo2 since 3650403 (owner, 2026-11-14 ~5:55 PM EST); r8brft1 before
dataset = default_source[3]
if a.source:
    name, file, sha, dataset = a.source
    block = (f"SOURCE = {{'name': '{name}', 'weights': '{file}',\n          'sha256': '{sha}',\n"
             f"          'dataset': '{dataset}'}}")
    src = SOURCE_RE.sub(lambda m: block, src)
kname = 'fork-bakeoff-r3' + {'A': '', 'X': '-xl', 'X2': '-xl2'}[a.arms] + ('-smoke' if a.smoke else '')
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
(out / 'bakeoff_r3.py').write_text(src, encoding='utf-8', newline='\n')
sources = (SMOKE_SOURCES if a.smoke else FULL_SOURCES) + [dataset]
meta = {'id': f'bossdotcom/{kname}', 'title': kname, 'code_file': 'bakeoff_r3.py', 'language': 'python',
        'kernel_type': 'script', 'is_private': True, 'enable_gpu': True, 'enable_internet': True,
        'dataset_sources': [f'bossdotcom/{d}' for d in sources], 'competition_sources': [], 'kernel_sources': []}
(out / 'kernel-metadata.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'commit': full, 'arms': a.arms, 'smoke': a.smoke, 'id': meta['id'], 'out': str(out), 'sources': len(sources),
                  'source': a.source or list(default_source)}))
