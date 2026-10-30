# SPDX-License-Identifier: GPL-3.0-or-later

"""Seals a finished fork_datagen run for upload (DESIGN.md §5.3,
deliverable 3).

`seal RUN.json` hashes every shard the run's manifest lists, checks each
shard's size against it, and writes the committed manifest
data/manifests/<run>.json: fork_datagen's settings and statistics, the
openings manifest's hash, and per shard its file name, games, positions,
bytes and SHA-256. Shards are grouped into upload batches of at most 50
files (Kaggle's top-level file limit; the CLI skips subfolders by default,
KB phase4-pipeline.md §4.7). No paths are written, only file names, so
the manifest is safe to publish.

Each sealed run is one part of a generation (the labeller policy, DESIGN.md
§5.3, deliverable 2): its manifest records the labelling network (a network
run's evaluator must name it, "nnue (<net>)"), its openings file and why
the part ended (--part-end, required).

The upload and confirmation steps (kaggle datasets create, the CPU-session
hash check, deleting local shards only on a full match) are added after
the Kaggle test session (deliverable 0, checks K7-K9) has shown the CLI's
real behaviour.

    .venv/Scripts/python.exe -I tools/datagen/upload_batch.py seal RUN.json \\
        --openings-manifest OPENINGS.manifest.json --part-end REASON [--out data/manifests]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

BATCH_FILES = 50


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def seal(run_json, openings_manifest, out_dir, part_end):
    run_json = Path(run_json)
    run = json.loads(run_json.read_text())
    if not part_end.strip():
        raise SystemExit('say why this part ended (--part-end)')
    if run['evaluator'] == 'nnue':
        raise SystemExit('the run does not name its labelling network; set "evaluator": "nnue (<net>)"')
    shards = sorted(run['shards'], key=lambda s: s['file'])
    for s in shards:
        path = run_json.parent / s['file']
        size = path.stat().st_size
        if size != s['bytes']:
            raise SystemExit(f"{s['file']}: {size} bytes on disk, the run says {s['bytes']}")
        s['sha256'] = sha256_of(path)
    om = json.loads(Path(openings_manifest).read_text())
    name = run_json.stem
    sealed = {
        'run': name,
        'generator': {k: run[k] for k in ('tool', 'version', 'evaluator', 'arch')},
        'settings': run['settings'],
        'openings': {'file': om['output'], 'sha256': om['output_sha256'], 'positions': om['positions'],
                     'source': om['source'], 'source_sha256': om['source_sha256']},
        'games': run['games'],
        'positions': run['positions'],
        'seconds': run['seconds'],
        'results': run['results'],
        'ends': run['ends'],
        'part_end': part_end,
        'batches': [shards[i:i + BATCH_FILES] for i in range(0, len(shards), BATCH_FILES)],
    }
    # The split search's counts, from runs whose fork_datagen writes them.
    for k in ('positions_unsaved', 'nodes_spent'):
        if k in run:
            sealed[k] = run[k]
    if sum(s['games'] for s in shards) != run['games'] or sum(s['positions'] for s in shards) != run['positions']:
        raise SystemExit('the shard counts do not add up to the run totals')
    out = Path(out_dir) / f'{name}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sealed, indent=1) + '\n', newline='\n')
    print(f'{out}: {len(shards)} shards in {len(sealed["batches"])} batches, {run["positions"]} positions')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('seal')
    s.add_argument('run_json')
    s.add_argument('--openings-manifest', required=True)
    s.add_argument('--out', default=str(Path(__file__).resolve().parents[2] / 'data' / 'manifests'))
    s.add_argument('--part-end', required=True, help='why this part of the generation ended')
    a = ap.parse_args(argv)
    if a.cmd == 'seal':
        seal(a.run_json, a.openings_manifest, a.out, a.part_end)
    return 0


if __name__ == '__main__':
    sys.exit(main())
