"""Idea 178's session (M: mb1, H512+PP+M, beside kc1, H512+PP, both warm from r3kr1): the Kaggle kernel folder from
tools/train/kaggle/bakeoff_r3.py at a pushed commit, as round 3's make_kernel.py (scratch-r3kr4) makes its folders.
The only edits are exact replacements: COMMIT set to the commit, ARM_SET to 'M', and with --smoke the smoke switch.
The source is the kernel's own M_SOURCE (r3kr1-avg.bin of the dataset fork-i178-init, to be uploaded first).

    python -I make_kernel_m.py --repo WORKTREE --commit HASH --out DIR [--smoke]
Session M is kernel fork-i178-m; with --smoke fork-i178-m-smoke.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

# Round 3's full and smoke data sources (scratch-r3kr4/make_kernel.py), the source's dataset added below.
FULL_SOURCES = ['fork-g2s1', 'fork-g3s1', 'fork-g3rest', 'fork-g3bcd', 'fork-g3e', 'fork-g3s2', 'fork-g3f', 'fork-g3g',
                'fork-g3s3', 'fork-g3hij', 'fork-r8b-blend-1', 'fork-r8b-blend-2', 'fork-r8b-blend-3', 'fork-r8b-arms',
                'fork-g4', 'fork-r8b-g4', 'fork-ld-d20', 'fork-ld-d50', 'fork-ld-d100', 'fork-g4b', 'fork-r8c-td',
                'fork-r8c-filler', 'fork-slice1b', 'fork-g4c', 'fork-r8c-post', 'fork-r8c-cut']
SMOKE_SOURCES = ['fork-g3bcd', 'fork-r8b-blend-1', 'fork-g4b', 'fork-r8c-td', 'fork-r8c-filler', 'fork-slice1b',
                 'fork-r8b-g4']

ap = argparse.ArgumentParser()
ap.add_argument('--repo', required=True)
ap.add_argument('--commit', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--smoke', action='store_true')
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
assert src.count("\nARM_SET = 'A' ") == 1
src = src.replace("\nARM_SET = 'A' ", "\nARM_SET = 'M' ", 1)
found = re.findall(r"M_SOURCE = dict\(name='([^']*)', weights='([^']*)', dataset='([^']*)',", src)
assert len(found) == 1, 'the kernel holds no single M_SOURCE'
dataset = found[0][2]
kname = 'fork-i178-m' + ('-smoke' if a.smoke else '')
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
(out / 'bakeoff_r3.py').write_text(src, encoding='utf-8', newline='\n')
sources = (SMOKE_SOURCES if a.smoke else FULL_SOURCES) + [dataset]
meta = {'id': f'bossdotcom/{kname}', 'title': kname, 'code_file': 'bakeoff_r3.py', 'language': 'python',
        'kernel_type': 'script', 'is_private': True, 'enable_gpu': True, 'enable_internet': True,
        'dataset_sources': [f'bossdotcom/{d}' for d in sources], 'competition_sources': [], 'kernel_sources': []}
(out / 'kernel-metadata.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'commit': full, 'smoke': a.smoke, 'id': meta['id'], 'out': str(out), 'sources': len(sources),
                  'source': list(found[0])}))
