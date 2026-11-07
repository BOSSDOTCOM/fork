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

The two-try limit (owner, DESIGN.md §6 2026-11-07 decision 2: at most two tries per idea; per time control
class, so an LTC confirmation of an STC pass is not a retry; every kind but custom carries an idea id, and
each retrain is its own idea). Tries go in $FORK_JOBS/tries.jsonl, apart from the run records:

    ledger.py try IDEA SPRT --kind search|network --tc-class stc|ltc --base SHA --test SHA
                  [--owner-override TEXT] [--check]
        a new SPRT name for IDEA at that class is try N; a third (N > TRY_LIMIT) is refused (exit 3) unless
        --owner-override gives the owner's decision, recorded verbatim. An SPRT name already recorded is a
        resume (not counted). --check only answers (exit 0 or 3) and writes nothing. Exit 2: bad arguments.
    ledger.py tries IDEA
        prints "TRY SPRT KIND TC_CLASS BASE TEST [override: TEXT]" per recorded try.
"""
import json
import os
import re
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


TRY_LIMIT = 2
IDEA_OK = re.compile(r'^[a-z0-9][a-z0-9.-]{0,47}$')


def tries_path():
    return path().parent / 'tries.jsonl'


def try_records(idea=None):
    try:
        with open(tries_path(), encoding='utf-8') as f:
            recs = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []
    return [r for r in recs if idea is None or r['idea'] == idea]


def record_try(argv):
    """ledger.py try ...: exit 0 (may run; recorded unless --check), 1 (the SPRT name is another idea's),
    2 (bad arguments), 3 (refused: the try limit)."""
    check = '--check' in argv
    argv = [a for a in argv if a != '--check']
    if len(argv) < 2 or len(argv) % 2:
        sys.stderr.write(__doc__)
        sys.exit(2)
    idea, sprt = argv[0], argv[1]
    opts = dict(zip(argv[2::2], argv[3::2]))
    kind, tc_class, base, test = (opts.get(k) for k in ('--kind', '--tc-class', '--base', '--test'))
    override = opts.get('--owner-override')
    bad = (not IDEA_OK.match(idea) and f'idea {idea!r} is not [a-z0-9][a-z0-9.-]*'
           or kind not in ('search', 'network') and f'--kind {kind!r} is not search or network'
           or tc_class not in ('stc', 'ltc') and f'--tc-class {tc_class!r} is not stc or ltc'
           or not (base and test and len(base) == 40 and len(test) == 40) and '--base and --test must be full hashes'
           or override is not None and not override.strip() and "--owner-override needs the owner's decision")
    if bad:
        print(f'ledger: {bad}', file=sys.stderr)
        sys.exit(2)
    for r in try_records():
        if r['sprt'] == sprt:
            if r['idea'] != idea:
                print(f"ledger: {sprt} is a try of idea {r['idea']}, not {idea}", file=sys.stderr)
                sys.exit(1)
            print(f"resume of try {r['try']}")
            return
    same = [r for r in try_records(idea) if r['tc_class'] == tc_class]
    n = len(same) + 1
    if n > TRY_LIMIT and override is None:
        names = ', '.join(r['sprt'] for r in same)
        print(f'ledger: idea {idea} already has {len(same)} {tc_class} tries ({names}); another needs '
              f'--owner-override', file=sys.stderr)
        sys.exit(3)
    print(f'try {n} of {TRY_LIMIT}' if n <= TRY_LIMIT else f'try {n} (owner override: {override})')
    if check:
        return
    rec = {'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'idea': idea, 'sprt': sprt, 'kind': kind,
           'tc_class': tc_class, 'base': base, 'test': test, 'try': n}
    if override is not None:
        rec['override'] = override
    tries_path().parent.mkdir(parents=True, exist_ok=True)
    with open(tries_path(), 'a', encoding='utf-8') as f:
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
    elif cmd == 'try':
        record_try(rest)
    elif cmd == 'tries' and len(rest) == 1:
        for r in try_records(rest[0]):
            print(r['try'], r['sprt'], r['kind'], r['tc_class'], r['base'], r['test'],
                  *(['override:', r['override']] if 'override' in r else []))
    elif cmd == 'known' and len(rest) == 1:
        sys.exit(0 if any(int(r['run_id']) == int(rest[0]) for r in records()) else 1)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
