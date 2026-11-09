# SPDX-License-Identifier: GPL-3.0-or-later
"""The data-generation watchdog: a small detached process (one at a time) that the Control Center starts
while a part runs, so it works with the app closed:
- keeps Windows from sleeping (system sleep only; the display may still turn off) while the part's job
  lives, and hands sleep back to Windows when the job ends, is stopped, or the watchdog exits;
- at the part's auto-stop deadline (autostop.json in the part's state folder, set from the app), stops and
  seals the part as the Stop & seal button does.
It polls the WSL supervisor every poll_seconds and writes a heartbeat to watchdog.json in the state folder.

    watchdog.py --part NAME
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config  # noqa: E402
import winutil  # noqa: E402


def watch(part, is_running, deadline_of, stop_and_seal, sleep_block, heartbeat, now=time.time, sleep=time.sleep,
          poll=30, unknown_limit=20):
    """The loop, with every effect injected. Returns how it ended: 'ended', 'auto-stopped', 'unknown' (the
    job's state could not be read unknown_limit times in a row), or 'auto-stop failed: ...'."""
    sleep_block(True)
    unknown = 0
    try:
        while True:
            running = is_running(part)
            heartbeat(running)
            if running is False:
                return 'ended'
            unknown = unknown + 1 if running is None else 0
            if unknown >= unknown_limit:
                return 'unknown'
            d = deadline_of(part)
            if running and d and now() >= d['deadline']:
                try:
                    stop_and_seal(part, f"auto-stop after {d['hours']:g} hours (set from the Control Center)")
                except Exception as e:  # noqa: BLE001
                    return f'auto-stop failed: {e}'
                return 'auto-stopped'
            sleep(poll)
    finally:
        sleep_block(False)


def main(argv):
    if len(argv) != 2 or argv[0] != '--part':
        sys.exit(__doc__)
    part = argv[1]
    import generation_control  # noqa: E402
    import notify  # noqa: E402
    from runner import Runner  # noqa: E402
    cfg = config.load()
    state = config.state_dir()
    ctl = generation_control.GenerationControl(cfg, Runner(), state=state)
    wfile = state / 'watchdog.json'
    started = time.time()
    blocked = {'ok': None}

    def block(on):
        """SetThreadExecutionState's own answer is what the heartbeat reports."""
        ok = winutil.sleep_block(on)
        blocked['ok'] = bool(ok) if on else False
        return ok

    def heartbeat(running):
        data = {'pid': os.getpid(), 'part': part, 'started': started, 'heartbeat': time.time(), 'running': running,
                'sleep_blocked': blocked['ok']}
        state.mkdir(parents=True, exist_ok=True)
        tmp = wfile.with_suffix('.tmp')
        tmp.write_text(json.dumps(data), encoding='utf-8')
        os.replace(tmp, wfile)

    def deadline_of(name):
        return ctl.read_state(name, 'autostop.json')

    def stop_and_seal(name, reason):
        msg = ctl.stop_and_seal(name, reason)
        notify.toast('Fork: auto-stop', msg)

    how = watch(part, lambda n: generation_control.is_running(ctl, n), deadline_of, stop_and_seal, block, heartbeat,
                poll=cfg['poll_seconds'])
    try:
        data = json.loads(wfile.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {'pid': os.getpid(), 'part': part}
    data.update(exited=time.time(), how=how, sleep_blocked=False)
    wfile.write_text(json.dumps(data), encoding='utf-8')
    if how.startswith('auto-stop failed'):
        notify.toast('Fork: auto-stop FAILED', how)


if __name__ == '__main__':
    main(sys.argv[1:])
