"""The full session's data sources against its input check, without downloading: each dataset's file list from the
Kaggle API (names only), empty stand-in files in a fresh folder, then bakeoff_r3.resolve(hashes=False) with the
manifests of the branch (session A's and X's lists). Prints the record; exit 1 unless both resolve.

    python -I check_full_sources.py LAUNCH_DIR WORKTREE
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

launch, repo = Path(sys.argv[1]), Path(sys.argv[2])
KAGGLE = str(Path('~/fork/.venv/Scripts/kaggle.exe').expanduser())
meta = json.loads((launch / 'kernel-metadata.json').read_text())
names = {}
for ds in meta['dataset_sources']:
    token, got = None, []
    while True:
        args = [KAGGLE, 'datasets', 'files', ds, '--page-size', '200', '--csv'] + (['--page-token', token] if token else [])
        out = subprocess.run(args, capture_output=True, text=True, timeout=300).stdout
        lines = out.splitlines()
        rows = [l.split(',')[0] for l in lines if l and not l.startswith('name') and not l.startswith('Next Page')]
        got += [r for r in rows if r.endswith('.vf') or r.endswith('.bin')]
        nxt = [l for l in lines if 'Next Page Token' in l or 'nextPageToken' in l]
        if not nxt:
            break
        token = nxt[0].split()[-1]
    names[ds] = got
    print(ds, len(got), flush=True)
sys.path.insert(0, str(launch))
import bakeoff_r3 as k  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    paths = []
    for ds, files in names.items():
        for f in files:
            p = Path(d, ds.split('/')[1], f)
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(b'')
            if f.endswith('.vf'):
                paths.append(str(p))
    sealed = k.sealed_files(str(repo))
    record, lists, _ = k.resolve(paths, sealed, hashes=False)
    src = [f for files in names.values() for f in files if f == k.SOURCE['weights']]
json.dump(lists, open(str(launch) + "-lists.json", "w"))
print(json.dumps({"ok": record['ok'], 'mounted': record['mounted'], 'mismatches_unsealed': record['mismatches'][:10],
                  'names_twice': record['names_twice'][:10], 'unresolved': record['unresolved'],
                  'files_per_arm': record['files_per_arm'], 'slice_files': record['slice_files'],
                  'source_found': len(src)}, indent=1))
sys.exit(0 if record['ok'] and len(src) == 1 else 1)
