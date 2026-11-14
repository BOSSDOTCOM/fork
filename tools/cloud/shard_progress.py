# SPDX-License-Identifier: GPL-3.0-or-later
"""A GitHub SPRT shard's running progress, for display only (owner, 2026-11-14).

While a shard of .github/workflows/sprt.yml plays its games (tools/cloud/run_shard.sh, unchanged), `watch`
runs beside it in the background: it reads the shard's fastchess log, counts what has finished the way the
merge counts it (tools/cloud/sprt_merge.py's own functions: a pair counts once both its games are done), and
every --every-games finished games, or every --every-seconds when anything finished since the last upload,
writes DIR/progress.json and runs the upload command (tools/cloud/progress_upload.sh: the artifact
progress-STAGE-SHARD, replacing the previous one). When the shard's games end, `finish` stops the watcher and
writes the final record, which the workflow uploads under the same name.

It only reads the shard's files (the log, and result.json at the end) and writes only under DIR, which must
lie outside the shard's output folder: the shard's results, their artifact (shard-STAGE-SHARD) and the merge
are byte for byte what they are without it (tools/cloud/test_shard_progress.sh). Nothing reads these records
but the display (the Fork Operations Display; docs/research/shard-progress.md has the format and how to read
them): the merge downloads shard-* artifacts and the driver (tools/github/sprt_run.sh) reads only files named
result.json. A failed upload is logged and skipped; it never stops the watcher or fails the shard.

    shard_progress.py watch  --log LOG --dir DIR --name NAME --upload "CMD" [META] [--every-games N]
                             [--every-seconds S] [--poll S] [--upload-timeout S] [--max-seconds S]
    shard_progress.py finish --log LOG --dir DIR --result RESULT.json [META] [--wait S]
    shard_progress.py record --log LOG [--result RESULT.json] [META]       (prints one record)

META: --run-id, --run-attempt, --sprt-name, --stage, --shard, --shards, --games-planned, --base, --test.
The upload command gets the artifact's name and the record's path as its last two arguments.
"""
import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sprt_merge  # noqa: E402  (the merge's own counting)

FORMAT = 'fork-shard-progress/1'
RECORD = 'progress.json'


def counts(log_text, test='test'):
    """The finished games of a fastchess log, counted as the merge counts them: the pentanomial of the
    finished pairs (sprt_merge.pairs_from_games, as in result.json), finished games, time losses and abnormal
    endings (sprt_merge.snapshot), and the test engine's wins, draws and losses over every finished game."""
    snap = sprt_merge.snapshot(log_text)
    points = {}
    for line in log_text.splitlines():
        m = sprt_merge._GAME.match(line)
        if m:
            white_points = {'1-0': 1.0, '0-1': 0.0, '1/2-1/2': 0.5}[m.group(4)]
            points[int(m.group(1))] = white_points if m.group(2) == test else 1.0 - white_points
    values = list(points.values())
    return {'games_finished': snap['finished_games'], 'pairs_finished': snap['pairs'], 'ptnml': snap['ptnml'],
            'wdl': {'wins': values.count(1.0), 'draws': values.count(0.5), 'losses': values.count(0.0)},
            'time_losses': snap['time_losses'], 'abnormal': snap['abnormal']}


def utc_now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def number(text):
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def record(log_text, a, state, seq, started, shard_status=None):
    games_planned = number(a.games_planned)
    return {'format': FORMAT, 'state': state, 'shard_status': shard_status, 'upload_seq': seq,
            'started_utc': started, 'updated_utc': utc_now(),
            'run_id': number(a.run_id), 'run_attempt': number(a.run_attempt), 'sprt_name': a.sprt_name or '',
            'stage': number(a.stage), 'shard': number(a.shard), 'shards': number(a.shards),
            'base': a.base or '', 'test': a.test or '',
            'games_planned': games_planned,
            'pairs_planned': None if games_planned is None else (games_planned + 1) // 2,
            **counts(log_text)}


def read_text(path):
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def write_record(directory, rec):
    """DIR/progress.json, replaced whole (a reader never sees half a record)."""
    tmp = directory / (RECORD + '.tmp')
    tmp.write_text(json.dumps(rec, indent=1) + '\n', encoding='utf-8')
    os.replace(tmp, directory / RECORD)


def say(*words):
    print(utc_now(), *words, flush=True)


def watch(a):
    directory = Path(a.dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'watcher.pid').write_text(str(os.getpid()), encoding='utf-8')
    stop = directory / 'stop'
    upload = shlex.split(a.upload)
    started = utc_now()
    end = time.monotonic() + a.max_seconds
    say(f'watching {a.log}: every {a.every_games} games or {a.every_seconds} s with news; artifact {a.name}')
    try:
        loop(a, directory, stop, upload, started, end)
    finally:
        (directory / 'watcher.pid').unlink(missing_ok=True)  # finish waits for this


def loop(a, directory, stop, upload, started, end):
    seq = 0
    sent_games = None  # games in the last record uploaded (None: nothing uploaded yet)
    sent_at = time.monotonic()
    while not stop.exists() and time.monotonic() < end:
        text = read_text(a.log)
        games = counts(text)['games_finished']
        due = (sent_games is None or games >= sent_games + a.every_games
               or (games != sent_games and time.monotonic() - sent_at >= a.every_seconds))
        if due:
            seq += 1
            write_record(directory, record(text, a, 'running', seq, started))
            (directory / 'seq').write_text(str(seq), encoding='utf-8')
            try:
                rc = subprocess.run(upload + [a.name, str(directory / RECORD)], timeout=a.upload_timeout).returncode
            except (OSError, subprocess.SubprocessError) as e:
                rc = f'not run ({e})'
            say(f'record {seq}: {games} games; upload exit {rc}')
            sent_games, sent_at = games, time.monotonic()
        wake = time.monotonic() + a.poll
        while time.monotonic() < wake and not stop.exists():
            time.sleep(min(0.5, a.poll))
    say('stopped' if stop.exists() else 'time limit reached')


def alive(pid, pid_file):
    """Whether the watcher still runs: it removes its pid file when it ends; on POSIX also whether the
    process exists (one killed outright leaves the file). Windows (the tests) uses the file alone: its
    os.kill(pid, 0) would send CTRL_C_EVENT."""
    if not pid_file.exists():
        return False
    if os.name == 'nt':
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def finish(a):
    directory = Path(a.dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'stop').write_text('', encoding='utf-8')
    pid = number(read_text(directory / 'watcher.pid').strip())
    if pid is not None:
        end = time.monotonic() + a.wait
        pid_file = directory / 'watcher.pid'
        while alive(pid, pid_file) and time.monotonic() < end:
            time.sleep(0.2)
        if alive(pid, pid_file) and hasattr(os, 'killpg'):  # its own session (started detached): it and its upload
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except OSError:
                pass
    shard_status = None
    try:
        shard_status = json.loads(read_text(a.result)).get('status') if a.result else None
    except ValueError:
        pass
    seq = (number(read_text(directory / 'seq').strip()) or 0) + 1
    try:
        started = json.loads(read_text(directory / RECORD)).get('started_utc')
    except ValueError:
        started = None
    rec = record(read_text(a.log), a, 'final', seq, started, shard_status)
    write_record(directory, rec)
    say(f'final record: {rec["games_finished"]} games, shard status {shard_status}')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('watch', 'finish', 'record'):
        s = sub.add_parser(name)
        s.add_argument('--log', required=True)
        for key in ('run-id', 'run-attempt', 'sprt-name', 'stage', 'shard', 'shards', 'games-planned', 'base',
                    'test'):
            s.add_argument('--' + key, default=None)
        if name != 'record':
            s.add_argument('--dir', required=True)
        if name == 'watch':
            s.add_argument('--name', required=True)
            s.add_argument('--upload', required=True)
            s.add_argument('--every-games', type=int, default=100)
            s.add_argument('--every-seconds', type=float, default=300)
            s.add_argument('--poll', type=float, default=30)
            s.add_argument('--upload-timeout', type=float, default=60)
            s.add_argument('--max-seconds', type=float, default=6 * 3600)
        else:
            s.add_argument('--result', default=None)
        if name == 'finish':
            s.add_argument('--wait', type=float, default=90)
    a = p.parse_args(argv)
    if a.cmd == 'watch':
        watch(a)
    elif a.cmd == 'finish':
        finish(a)
    else:
        status = None
        if a.result:
            try:
                status = json.loads(read_text(a.result)).get('status')
            except ValueError:
                pass
        print(json.dumps(record(read_text(a.log), a, 'final' if status else 'running', 0, None, status), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
