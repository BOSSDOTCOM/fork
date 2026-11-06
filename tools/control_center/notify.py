# SPDX-License-Identifier: GPL-3.0-or-later
"""Windows notifications for the Control Center: a toast through Windows PowerShell's WinRT toast API (no
dependencies), and events() which compares two successive snapshots and names what deserves one:
- an SPRT decides (the driver log's "decided after stage N", "undecided after stage N" or a stop);
- a Kaggle session finishes (running or queued, then anything else);
- a supervisor job fails (ends with a nonzero exit) or stops unexpectedly (its record says running with no
  process left; a datagen job stopped without the app's stop request; a datagen part that ends by itself);
- a seal finishes, passes or fails;
- the disk runs low or memory is under pressure (each warning once, when it appears).
The first snapshot only sets the baseline, so nothing that was already true when the app opened is
announced.
"""
import os
import subprocess

TOAST = r'''
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$x = $t.GetElementsByTagName('text')
$x.Item(0).AppendChild($t.CreateTextNode($env:FORK_CC_TITLE)) | Out-Null
$x.Item(1).AppendChild($t.CreateTextNode($env:FORK_CC_TEXT)) | Out-Null
$n = [Windows.UI.Notifications.ToastNotification]::new($t)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe').Show($n)
'''


def toast(title, text, popen=subprocess.Popen):
    """Shows a Windows toast without waiting for it. Returns False off Windows."""
    if os.name != 'nt':
        return False
    env = dict(os.environ, FORK_CC_TITLE=str(title)[:120], FORK_CC_TEXT=str(text)[:400])
    popen(['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', TOAST],
          env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
          creationflags=0x08000000)
    return True


DONE_KAGGLE = {'complete', 'error', 'cancelrequested', 'cancelacknowledged'}


def events(prev, cur):
    """[(title, text)] for what changed between two snapshots (see the module docstring)."""
    if not prev:
        return []
    out = []
    # SPRTs
    before = {s['name']: s for s in prev.get('sprts', [])}
    for s in cur.get('sprts', []):
        p = before.get(s['name'])
        if s.get('finished') and (p is None or not p.get('finished')) and p is not None:
            res = ''
            if s.get('elo') is not None:
                res = (f" Elo {s['elo']:+.2f} +/- {s['elo_err']:.2f}, LLR {s['llr']:.2f} "
                       f"({s['llr_lo']}, {s['llr_hi']}) [{s['elo0']:g}, {s['elo1']:g}]: {s.get('verdict')}")
            out.append((f"SPRT {s['name']}", f"{s['finished']}.{res}"))
    # Kaggle
    kb = prev.get('kaggle', {})
    for ref, st in cur.get('kaggle', {}).items():
        was = kb.get(ref)
        if was in ('running', 'queued') and st in DONE_KAGGLE:
            out.append(('Kaggle session finished', f'{ref}: {st}'))
    # jobs
    pj = {(j['supervisor'], j['name'], j['id']): j for j in prev.get('jobs', [])}
    expected = set(cur.get('expected_stops', []))
    for j in cur.get('jobs', []):
        p = pj.get((j['supervisor'], j['name'], j['id']))
        if p is None or p['raw_state'] not in ('running', 'starting') or not p['processes']:
            continue
        where = f"{j['name']} ({j['type']}, {j['supervisor']})"
        if j['raw_state'] == 'ended' and j.get('exit_code') not in (0, None):
            out.append(('Job failed', f"{where} ended with exit code {j['exit_code']}"))
        elif j['raw_state'] in ('running', 'starting') and not j['processes']:
            out.append(('Job stopped unexpectedly', f'{where}: no process left, the record still says running'))
        elif j['type'] == 'datagen' and j['raw_state'] == 'ended':
            out.append(('Data generation ended', f"{where} ended by itself (exit {j.get('exit_code')})"))
        elif j['type'] == 'datagen' and j['raw_state'] == 'stopped' and j['name'] not in expected:
            out.append(('Data generation stopped', f'{where} was stopped, not from the Control Center'))
    # seals
    ps = prev.get('seals', {})
    for name, st in cur.get('seals', {}).items():
        if st in ('sealed', 'verify-failed', 'failed') and ps.get(name) != st:
            out.append((f'Seal of {name}: {st}', cur.get('seal_messages', {}).get(name, '')))
    # disk and memory
    pw = set(prev.get('warnings', []))
    for w in cur.get('warnings', []):
        if w not in pw:
            out.append(('Fork machine warning', w))
    return out
