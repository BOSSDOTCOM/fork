# SPDX-License-Identifier: GPL-3.0-or-later
"""The run-ID ledger (owner, 2026-11-05): every GitHub run a Fork driver dispatches, recorded with the
inputs it was dispatched with, so a run is attributed by its recorded inputs and never by "the newest run".
Append-only JSON lines in $FORK_JOBS/ledger.jsonl (default ~/fork-jobs).

    ledger.py add SPRT STAGE RUN_ID --base SHA --test SHA [--source dispatch|import] [--note TEXT]
        records a dispatched run (import: a run attributed after the fact, with the evidence in --note);
        refuses a run id already recorded for another SPRT or stage.
    ledger.py runs SPRT
        prints "STAGE RUN_ID BASE TEST" for each recorded stage of SPRT (the last record per stage).
    ledger.py check SPRT STAGE RUN_ID BASE TEST
        exit 0 only if the ledger's record for that stage is exactly that run with those inputs.
    ledger.py known RUN_ID
        exit 0 if the run id is recorded (for any SPRT).
"""
import json
import os
import sys
import time
from pathlib import Path


def path():
    return Path(os.environ.get('FORK_JOBS') or Path.home() / 'fork-jobs') / 'ledger.jsonl'


def records():
    try:
        with open(path(), encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def stages(sprt):
    out = {}
    for r in records():
        if r['sprt'] == sprt:
            out[int(r['stage'])] = r
    return out


def add(argv):
    sprt, stage, run = argv[0], int(argv[1]), int(argv[2])
    opts = dict(zip(argv[3::2], argv[4::2]))
    base, test = opts.get('--base'), opts.get('--test')
    if not (base and test and len(base) == 40 and len(test) == 40):
        sys.exit('ledger: --base and --test must be full commit hashes')
    for r in records():
        if int(r['run_id']) == run and (r['sprt'], int(r['stage'])) != (sprt, stage):
            sys.exit(f"ledger: run {run} is already recorded as {r['sprt']} stage {r['stage']}")
    rec = {'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'sprt': sprt, 'stage': stage, 'run_id': run,
           'base': base, 'test': test, 'source': opts.get('--source', 'dispatch')}
    if '--note' in opts:
        rec['note'] = opts['--note']
    path().parent.mkdir(parents=True, exist_ok=True)
    with open(path(), 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, sort_keys=True) + '\n')


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == 'add' and len(rest) >= 3:
        add(rest)
    elif cmd == 'runs' and len(rest) == 1:
        for stage, r in sorted(stages(rest[0]).items()):
            print(stage, r['run_id'], r['base'], r['test'])
    elif cmd == 'check' and len(rest) == 5:
        r = stages(rest[0]).get(int(rest[1]))
        ok = r is not None and (int(r['run_id']), r['base'], r['test']) == (int(rest[2]), rest[3], rest[4])
        sys.exit(0 if ok else 1)
    elif cmd == 'known' and len(rest) == 1:
        sys.exit(0 if any(int(r['run_id']) == int(rest[0]) for r in records()) else 1)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
