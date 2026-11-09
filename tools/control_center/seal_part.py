# SPDX-License-Identifier: GPL-3.0-or-later
"""Seals a stopped (or finished) data-generation part for the Control Center, as its own job under the
Windows supervisor (jobctl.py start seal seal-NAME), at below-normal priority:

1. copy: each worker's complete games from the part's WSL folder to <copies>/<part>/ (the bytes up to the
   last complete game; the unfinished game a stop leaves at each shard's end is dropped), the held-out
   worker's shard named *-val.vf, and <part>.json in the run-manifest form upload_batch.py seal reads;
2. verify: tools/datagen/verify_games.py on every copied shard with that manifest (every move legal, every
   result explained, the counts and unsaved records matching);
3. seal: tools/datagen/upload_batch.py seal, which hashes every shard and writes data/manifests/<part>.json
   with the labelling network, the openings and why the part ended.

A failed verification stops before the seal and keeps every file (the WSL originals are never touched).
Progress and the outcome go to seal-result.json beside the request.

    seal_part.py REQUEST.json   (written by generation_control.py's stop_and_seal)
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config  # noqa: E402
import parsers as P  # noqa: E402
from runner import BELOW_NORMAL_PRIORITY_CLASS, CREATE_NO_WINDOW  # noqa: E402

UNSAVED = 32767  # src/datagen/self_play.hpp UnsavedScore (an unsaved record of the split search)
SHARD = re.compile(r'^(?P<run>.+)-w(?P<worker>\d{2})-(?P<index>\d{4})\.vf$')


def complete_games(data):
    """(end, games, positions, unsaved, results[black, draw, white]) over the complete games at the start of a
    viriformat shard: a game is a 32-byte packed board (its result at byte 30) followed by 4-byte records
    (move, score) and a zero move that ends it. A board with no pieces (zero occupancy) ends the complete games:
    no real position has one, and a power loss leaves a shard's tail zero-filled (2026-11-07, g3h)."""
    usable = len(data) // 4 * 4
    w = memoryview(data)[:usable].cast('I')
    n, i, end, games, positions, unsaved = len(w), 0, 0, 0, 0, 0
    res = [0, 0, 0]
    while i + 8 <= n:
        if not (w[i] | w[i + 1]):  # the occupancy bitboard, the board record's first 8 bytes
            break
        j, p, u = i + 8, 0, 0
        closed = False
        while j < n:
            x = w[j]
            j += 1
            if not x & 0xFFFF:
                closed = True
                break
            p += 1
            u += (x >> 16) == UNSAVED
        if not closed:
            break
        r = data[i * 4 + 30]
        if r > 2:
            raise ValueError(f'game {games}: result byte {r}')
        res[r] += 1
        games += 1
        positions += p
        unsaved += u
        i = end = j
    return end * 4, games, positions, unsaved, res


def copy_part(name, src, out, val_worker):
    """Copies each shard's complete games; returns the shards' entries and the totals."""
    files = sorted(f for f in os.listdir(src) if (m := SHARD.match(f)) and m['run'] == name)
    if not files:
        raise SystemExit(f'no shards of {name} in {src}')
    workers = sorted({int(SHARD.match(f)['worker']) for f in files})
    if val_worker == 'last':
        val_worker = workers[-1]
    single = all(SHARD.match(f)['index'] == '0000' for f in files)
    shards, totals = [], {'games': 0, 'positions': 0, 'unsaved': 0, 'results': [0, 0, 0], 'dropped': 0}
    for f in files:
        m = SHARD.match(f)
        worker = int(m['worker'])
        data = Path(src, f).read_bytes()
        end, games, positions, unsaved, res = complete_games(data)
        stem = f'{name}-w{worker:02d}' + ('' if single else f"-{m['index']}")
        fname = stem + ('-val' if worker == val_worker else '') + '.vf'
        Path(out, fname).write_bytes(data[:end])
        shards.append({'file': fname, 'worker': worker, 'games': games, 'positions': positions, 'bytes': end})
        totals['games'] += games
        totals['positions'] += positions
        totals['unsaved'] += unsaved
        totals['results'] = [a + b for a, b in zip(totals['results'], res)]
        totals['dropped'] += len(data) - end
    return shards, totals


def previous_manifest(repo_manifests, name):
    """The latest sealed part of the same generation before this one (its fixed settings carry over)."""
    gen = P.part_key(name)[0]
    best = None
    for f in Path(repo_manifests).glob('g*.json'):
        try:
            m = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        k = P.part_key(str(m.get('run', '')))
        if P.is_part_manifest(m) and k[0] == gen and k < P.part_key(name):
            if best is None or k > P.part_key(best['run']):
                best = m
    return best


class Progress:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {'state': 'starting', 'steps': []}

    def __call__(self, state, message, **extra):
        self.data.update(state=state, message=message, at=time.time(), **extra)
        self.data['steps'].append({'state': state, 'message': message, 'at': time.time()})
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, indent=1), encoding='utf-8')
        os.replace(tmp, self.path)
        print(f'{P.est(time.time())} {state}: {message}', flush=True)


def lower_priority():
    if os.name == 'nt':
        k32 = ctypes.WinDLL('kernel32')
        k32.SetPriorityClass(k32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS)


def run_step(argv, log):
    flags = (CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS) if os.name == 'nt' else 0
    with open(log, 'a', encoding='utf-8') as f:
        f.write(f'\n$ {" ".join(map(str, argv[:4]))} ...\n')
        f.flush()
        return subprocess.call([str(a) for a in argv], stdout=f, stderr=subprocess.STDOUT, creationflags=flags)


def tail(path, n=5):
    try:
        return ' | '.join(Path(path).read_text(encoding='utf-8', errors='replace').strip().splitlines()[-n:])
    except OSError:
        return ''


def seal(req, here, wsl_version=None, verify=None, upload=None):
    """The three steps. wsl_version, verify and upload replace the external commands in tests."""
    name = req['name']
    progress = Progress(Path(here) / 'seal-result.json')
    log = Path(here) / 'seal-steps.log'
    repo = Path(req['repo'])
    out = Path(req['copies']) / name
    src = req.get('src') or str(config.wsl_unc(req['distro'], req['home'], req['dir']))
    try:
        if out.exists() and any(out.iterdir()):
            progress('failed', f'{out} already holds files; nothing was overwritten')
            return 1
        out.mkdir(parents=True, exist_ok=True)
        progress('copying', f'complete games from {req["dir"]} to {out}')
        shards, t = copy_part(name, src, out, req.get('val_worker', 'last'))
        progress('copied', f"{len(shards)} shards, {t['games']:,} games, {t['positions']:,} positions "
                           f"({t['unsaved']:,} unsaved); {t['dropped']:,} bytes of unfinished games dropped")
        if wsl_version is None:
            r = subprocess.run(['wsl.exe', '-d', req['distro'], '--exec', f"{req['dir']}/fork", 'version'],
                               capture_output=True, text=True, timeout=60,
                               creationflags=CREATE_NO_WINDOW if os.name == 'nt' else 0)
            wsl_version = r.stdout
        ver = P.fork_version(wsl_version)
        if not ver.get('version') or not ver.get('net'):
            progress('failed', f"`fork version` in {req['dir']} gave no version or network; files kept in {out}")
            return 1
        prev = previous_manifest(repo / 'data' / 'manifests', name) or {}
        settings = dict(prev.get('settings', {}))
        cmd_settings, paths = P.datagen_args(req.get('cmdline') or [])
        settings.update(req.get('settings') or {})
        settings.update(cmd_settings)
        openings = os.path.basename(paths.get('openings') or settings.get('openings') or '')
        settings['openings'] = openings
        om_path = repo / 'data' / 'manifests' / f'openings-{Path(openings).stem}.json'
        om = json.loads(om_path.read_text(encoding='utf-8'))
        settings['openings_count'] = om['positions']
        gen = P.part_key(name)[0]
        arch = ver.get('arch', '?')
        prev_arch = (prev.get('generator') or {}).get('arch', '')
        if arch == 'native' and prev_arch.startswith('native'):
            arch = prev_arch
        finished = req.get('finished')
        run_json = None
        if finished:
            try:
                run_json = json.loads(Path(src, f'{name}.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                run_json = None
        when = 'finished at its target' if finished else f"stopped on {P.est(req.get('stopped'))}"
        run_manifest = {
            'tool': (f"fork_datagen (complete games of generation {gen}'s run {name}, labelled by Fork "
                     f"{ver['version']} ({ver['net']}), on {settings.get('threads')} threads, {when}; "
                     f"sealed by the Control Center)"),
            'version': f"{ver['version']} (WSL clang PGO, {ver.get('compiler', '?')})",
            'evaluator': f"nnue ({ver['net']})", 'arch': arch, 'settings': settings,
            'games': t['games'], 'positions': t['positions'], 'positions_unsaved': t['unsaved'],
            'seconds': (run_json or {}).get('seconds') or req.get('seconds'),
            'results': {'white': t['results'][2], 'draw': t['results'][1], 'black': t['results'][0]},
            'ends': (run_json or {}).get('ends') or 'not counted (the run was stopped, not finished)',
            'shards': shards,
        }
        with open(out / f'{name}.json', 'w', encoding='utf-8', newline='\n') as f:
            json.dump(run_manifest, f, indent=1)
            f.write('\n')
        progress('verifying', f'verify_games.py on {len(shards)} shards (below-normal priority)')
        pieces = re.search(r'(\d)-piece', str(settings.get('tables', ''))) if settings.get('tables') else None
        vargv = [req['python'], '-I', repo / 'tools' / 'datagen' / 'verify_games.py',
                 *[out / s['file'] for s in shards], '--manifest', out / f'{name}.json',
                 '--table-pieces', pieces[1] if pieces else '0']
        rc = (verify or (lambda a: run_step(a, log)))(vargv)
        if rc != 0:
            progress('verify-failed', f'verification FAILED (exit {rc}): {tail(log)}; nothing sealed, every file '
                                      f'kept ({out} and the WSL originals)')
            return 1
        progress('verified', f'every game of {name} verified: {tail(log, 1)}')
        part_end = (f"{req['reason'].strip()}; generation {gen}'s part {name}, started "
                    f"{P.est(req.get('started'))}, {when}, on {settings.get('threads')} threads (Control Center); "
                    f"every game verified (tools/datagen/verify_games.py with its manifest)")
        uargv = [req['python'], '-I', repo / 'tools' / 'datagen' / 'upload_batch.py', 'seal', out / f'{name}.json',
                 '--openings-manifest', om_path, '--part-end', part_end, '--out', req['manifests_out']]
        rc = (upload or (lambda a: run_step(a, log)))(uargv)
        if rc != 0:
            progress('failed', f'upload_batch.py seal failed (exit {rc}): {tail(log)}; files kept in {out}')
            return 1
        manifest = Path(req['manifests_out']) / f'{name}.json'
        progress('sealed', f'{name} sealed: {manifest} ({t["games"]:,} games, {t["positions"]:,} positions); '
                           f'commit the manifest on {req.get("branch", "phase-4")}', manifest=str(manifest))
        return 0
    except Exception as e:  # noqa: BLE001  (reported, files kept)
        progress('failed', f'{type(e).__name__}: {e}; every file kept')
        return 1


def main(argv):
    if len(argv) != 1:
        sys.exit(__doc__)
    lower_priority()
    req_path = Path(argv[0])
    req = json.loads(req_path.read_text(encoding='utf-8'))
    return seal(req, req_path.parent)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
