# SPDX-License-Identifier: GPL-3.0-or-later
"""From a snapshot to what the display says about it: the alerts, and the situation (the pipeline's nodes,
its links and one sentence on what is happening). Pure functions of the snapshot; the thresholds are data
(rules.json beside this file, re-read when it changes), so tuning an alert needs no code edit.

Tiers: critical (something is stopped or broken; stays until its cause clears), attention (worth the
owner's eye), info (resolved or expected). A rejected or capped test is a normal outcome, never an alert."""
import json
import re
import time

DEFAULTS = {
    'expected_watchers': ['gcpwatch', 'watch', 'freezewatch', 'wslcache'],
    'production_types': 'datagen|seal|upload|gcp|kaggle|chain|github|copies|slice',
    'failed_job_hours': 6,
    'vm_status_stale_minutes': 11,
    'commit_percent': 90,
    'memory_gb': 1.0,
    'quota_hours': 5,
    'quota_stale_hours': 12,
    'cpu_idle_percent': 25,
    'cpu_idle_minutes': 15,
    'event_hours': 2,
    'retrain_hours': 24,
}


def load(text):
    """rules.json's text over the defaults. Unknown keys are kept; a bad file raises ValueError."""
    cfg = dict(DEFAULTS)
    if text and text.strip():
        d = json.loads(text)
        if not isinstance(d, dict):
            raise ValueError('rules.json is not an object')
        cfg.update(d)
    return cfg


# ---------------------------------------------------------------- formatting

def est(epoch, now=None):
    """'12:19 PM', or 'Fri 5:40 PM' when not today, or 'Nov 12, 4:26 PM' when over six days ago (EST)."""
    if not epoch:
        return ''
    t = time.gmtime(epoch - 5 * 3600)
    hm = time.strftime('%I:%M %p', t).lstrip('0')
    if now is None:
        return hm
    n = time.gmtime(now - 5 * 3600)
    if (t.tm_year, t.tm_yday) == (n.tm_year, n.tm_yday):
        return hm
    if abs(now - epoch) < 6 * 86400:
        return time.strftime('%a ', t) + hm
    return time.strftime('%b ', t) + str(t.tm_mday) + ', ' + hm


def span(seconds):
    """'45 s', '12 min', '3 h 20 min', '2 d 4 h'."""
    s = max(0, int(seconds))
    if s < 90:
        return f'{s} s'
    if s < 5400:
        return f'{round(s / 60)} min'
    if s < 2 * 86400:
        h, m = divmod(round(s / 60), 60)
        return f'{h} h {m} min' if m else f'{h} h'
    d, h = divmod(round(s / 3600), 24)
    return f'{d} d {h} h' if h else f'{d} d'


def coarse(seconds):
    """One unit only, for the large figures: '45 min', '20 h', '3 d'."""
    s = max(0, int(seconds))
    return f'{round(s / 60)} min' if s < 5400 else f'{round(s / 3600)} h' if s < 2 * 86400 else f'{round(s / 86400)} d'


def positions(n):
    """229475885 -> '229.5 M'; 2371000000 -> '2.37 B'."""
    if n is None:
        return 'unknown'
    if n >= 1e9:
        return f'{n / 1e9:.2f} B'
    if n >= 1e6:
        return f'{n / 1e6:.1f} M'
    if n >= 1e3:
        return f'{n / 1e3:.0f} K'
    return str(n)


def signed(v, digits=1):
    return ('−' if v < 0 else '+') + f'{abs(v):.{digits}f}'


# ---------------------------------------------------------------- alerts

def alerts(snap, cfg=None):
    """[{id, tier, what, why, at, source}], critical first, then attention, then info; newest first in a tier."""
    cfg = cfg or DEFAULTS
    now = snap['now']
    out = []

    def add(tier, aid, what, why, at=None, source=''):
        out.append({'id': aid, 'tier': tier, 'what': what, 'why': why, 'at': at, 'source': source})

    jobs = snap.get('jobs') or {'running': [], 'failed': []}
    for lane in snap.get('lanes') or []:
        if not lane['up']:
            add('critical', f"lane-down:{lane['id']}", f"Lane {lane['id']} is down",
                f"Its queue runner ({lane['job']}) has no live process; {lane['pending']} items are waiting.",
                None, f"locks/{lane['lock']}.json")
        elif lane['state'] == 'stopped':
            add('critical', f"lane-stopped:{lane['id']}:{(lane['sprt'] or {}).get('name')}",
                f"Lane {lane['id']} stopped on a failed run",
                f"{(lane['item'] or {}).get('title', 'Its test')}: {(lane['sprt'] or {}).get('stopped')}",
                None, f"driver log of {(lane['sprt'] or {}).get('name')}")
        elif lane['state'] == 'idle':
            waiting = [q for q in snap.get('queue') or [] if q['lane'] == lane['id']]
            if waiting:
                add('attention', f"lane-idle:{lane['id']}", f"Lane {lane['id']} is idle with {len(waiting)} items waiting",
                    'Every waiting item is behind a gate or a retry timer: ' + ', '.join(q['title'] for q in waiting[:3]) + '.',
                    None, lane['folder'] or '')
    running_types = {r['lock'] or r['type'] for r in jobs['running'] if r['live'] is not False}
    for w in cfg['expected_watchers']:
        if w not in running_types:
            add('critical', f'watcher:{w}', f'A watcher is not running: {w}',
                'Its lock names no live job, so what it guards is unwatched.', None, f'locks/{w}.json')
    for r in jobs['running']:
        if r['live'] is False and not (r['lock'] or '').startswith('github'):
            add('attention', f"stale-job:{r['name']}", f"A job record says running but has no process: {r['name']}",
                'It ended without closing its record (a crash or a reboot).', r['started'], f"jobs/{r['name']}.json")
    for f in jobs['failed']:
        if now - f['at'] > cfg['failed_job_hours'] * 3600:
            continue
        prod = re.search(cfg['production_types'], f"{f['type'] or ''} {f['name']}")
        if f['recovered']:
            add('info', f"job-failed:{f['name']}:{int(f['at'])}", f"A step failed once, then passed: {f['name']}",
                f"It exited {f['exit_code']} at {est(f['at'], now)}; a later run of the same step passed.", f['at'], f"jobs/{f['name']}.json")
        else:
            add('critical' if prod else 'attention', f"job-failed:{f['name']}:{int(f['at'])}", f"A job failed: {f['name']}",
                f"It exited {f['exit_code']} at {est(f['at'], now)} and nothing after it has passed.", f['at'], f"jobs/{f['name']}.json")

    data = snap.get('data') or {}
    vm = data.get('vm')
    if vm:
        age = now - vm['status_at'] if vm.get('status_at') else None
        if age is not None and age > cfg['vm_status_stale_minutes'] * 60:
            add('critical', 'vm-stale', 'The cloud VM watcher has gone quiet', f'Its status file is {span(age)} old; it refreshes about every 5 minutes.',
                vm['status_at'], 'gcp/status.json')
        if vm.get('wanted') == 'running' and vm['status'] != 'RUNNING':
            add('critical', 'vm-state', f"The cloud VM is {str(vm['status']).lower()}, not running", 'It is wanted running.', vm['status_at'], 'gcp/status.json')
        if vm.get('worker_error'):
            add('attention', 'vm-worker', 'The cloud VM worker did not answer', vm['worker_error'], vm['status_at'], 'gcp/status.json')
    for part, state in (data.get('seals') or {}).items():
        if state in ('failed', 'verify-failed'):
            add('critical', f'seal:{part}', f'The seal of part {part} failed', f'State: {state}.', None, f'parts/{part}/seal-result.json')
    pc = data.get('pc')
    if pc and pc['state'] == 'idle':
        add('attention', f"pc-idle:{pc.get('part')}", 'The PC is not generating data',
            (f"Part {pc['part']} ended {est(pc['since'], now)}" + (f" and is {pc['seal']}" if pc.get('seal') else '') + '. No part is running.')
            if pc.get('part') else 'No part is running.', pc.get('since'), 'watchdog.json')

    m = snap.get('machine') or {}
    fz = m.get('freeze') or {}
    if fz.get('last_stall') and now - fz['last_stall']['at'] < cfg['event_hours'] * 3600:
        add('critical', f"stall:{int(fz['last_stall']['at'])}", 'The machine froze', f"A stall of {fz['last_stall']['seconds']} s at {est(fz['last_stall']['at'], now)}.",
            fz['last_stall']['at'], 'freezewatch.log')
    for a in ((m.get('memwatch') or {}).get('actions') or []):
        if a['at'] and now - a['at'] < cfg['event_hours'] * 3600:
            add('critical' if a['kind'] == 'alert' else 'attention', f"memwatch:{int(a['at'])}",
                'The memory watch raised an alert' if a['kind'] == 'alert' else 'The memory watch acted', a['text'].lstrip(': '), a['at'], 'memwatch log')
    if m.get('commit') is not None and m['commit'] >= cfg['commit_percent']:
        add('attention', 'commit', f"Memory is tight: commit charge {m['commit']:.0f}%",
            f"{m['mem_avail'] / 2 ** 30:.2f} GB available." if m.get('mem_avail') else '', None, 'live')
    elif m.get('mem_avail') is not None and m['mem_avail'] < cfg['memory_gb'] * 2 ** 30:
        add('attention', 'memory', f"Memory is low: {m['mem_avail'] / 2 ** 30:.2f} GB available", 'The memory watch acts after 15 minutes below 1 GB.', None, 'live')
    cpu = (m.get('hist') or {}).get('cpu') or []
    need = cfg['cpu_idle_minutes'] * 2
    waiting = [q for q in snap.get('queue') or [] if q['state'] == 'pending']
    if len(cpu) >= need and max(cpu[-need:]) < cfg['cpu_idle_percent'] and (waiting or (pc and pc['state'] == 'idle')):
        add('attention', 'cpu-idle', f"The CPU has been under {cfg['cpu_idle_percent']}% for {cfg['cpu_idle_minutes']} minutes",
            'Work is waiting that could use it.', None, 'live')
    comp = m.get('compile') or {}
    if comp.get('state') == 'lifted':
        add('info', 'compile-lifted', 'The compile lock is lifted', comp.get('text', ''), comp.get('at'), 'compile.lock.lifted')

    for q in snap.get('queue') or []:
        if q['failures']:
            add('attention', f"item-failures:{q['key']}", f"A queue item has failed {q['failures']} time(s): {q['title']}",
                (f"It retries at {est(q['retry_at'], now)}." if q['retry_at'] else 'It is skipped after the third failure.'), None, q['key'])
    for i in snap.get('interrupted') or []:
        add('attention', f"interrupted:{i['name']}", f"A test stopped without a verdict: {i['title']}",
            f"Its run was dispatched {est(i['since'], now)} and never merged; no lane is running it.", i['since'], f"driver log of {i['name']}")
    for v in snap.get('verdicts') or []:
        if v['outcome']['kind'] == 'passed' and not v['adopted'] and now - v['at'] < 86400 and 'stack-check' not in v['name']:
            add('info', f"passed:{v['name']}", f"A test passed; its adoption is not recorded yet: {v['title']}",
                f"{signed(v['elo'])} ± {v['err']:.1f} Elo over {v['games']:,} games ({v['klass']})." if v['elo'] is not None else '', v['at'], v['name'])

    tr = snap.get('training') or {}
    for r in tr.get('retrains') or []:
        if not r.get('gates_at') or now - r['gates_at'] > cfg['retrain_hours'] * 3600:
            continue                                        # a retrain's gate results are news for a day
        failed = [a['arm'] for a in r['arms'] if a['cells'].get('gates') == 'fail']
        flagged = [a['arm'] for a in r['arms'] if a['cells'].get('heldout') == 'flag']
        if failed:
            add('attention', f"gates:{r['id']}", f"Retrain {r['title']}: {len(failed)} arm(s) failed the integrity gates",
                'Arms: ' + ', '.join(failed) + '.', r['gates_at'], 'gates.json')
        if flagged:
            add('attention', f"heldout:{r['id']}", f"Retrain {r['title']}: {len(flagged)} arm(s) flagged on a held-out endgame check",
                'Over 15% more misjudged positions than the default net; reported, not a gate. Arms: ' + ', '.join(flagged) + '.',
                r['gates_at'], 'gates.json')
    for s in tr.get('sessions') or []:
        if s['state'] and s['state'] not in ('RUNNING', 'QUEUED', 'COMPLETE') and s['last_run'] and now - s['last_run'] < 12 * 3600:
            add('attention', f"kaggle:{s['ref']}:{int(s['last_run'])}", f"A Kaggle session did not complete: {s['ref']}",
                f"Its state is {s['state'].lower().replace('_', ' ')}; it started {est(s['last_run'], now)}.", s['at'], 'Kaggle')
    q = tr.get('quota')
    if q:
        if q['left'] < cfg['quota_hours']:
            add('attention', 'quota', f"Kaggle GPU quota is low: {q['left']:.1f} h left", f"As of {est(q['at'], now)}; it resets {est(q['reset'], now)}.", q['at'], 'fetch log')
    ov = snap.get('overview') or {}
    for c in ov.get('checks') or []:
        if c['outcome'] == 'flagged' and now - c['at'] < 4 * 86400:
            add('attention', f"anchor-check:{c['run']}", 'An anchor check is flagged for review',
                f"Measured {signed(c['gain'])} Elo ({signed(c['lo'])} to {signed(c['hi'])}) on {est(c['at'], now)}.", c['at'], f"gauntlet run {c['run']}")
    for key, h in ((snap.get('health') or {}).get('failing') or {}).items():
        add('attention', f'source:{key}', 'A source can no longer be read as expected', f"{key}: {h['error']}. The last good value stays on screen.", None, key)

    order = {'critical': 0, 'attention': 1, 'info': 2}
    out.sort(key=lambda a: (order[a['tier']], -(a['at'] or now)))
    return out


# ---------------------------------------------------------------- situation

def situation(snap):
    """{text, nodes[], edges[]}: the pipeline as the display draws it. A node: {id, col, name, state, word,
    big, small, focus (panel key), until (an epoch the big figure counts down to, or None)}."""
    now = snap['now']
    data, tr, ov = snap.get('data') or {}, snap.get('training') or {}, snap.get('overview') or {}
    nodes, edges, said = [], [], []
    pc, vm = data.get('pc'), data.get('vm')
    if pc:
        on = pc['state'] == 'active'
        nodes.append({'id': 'pc', 'col': 1, 'name': 'PC data generation', 'state': 'active' if on else 'idle',
                      'word': 'generating' if on else 'idle',
                      'big': (f"{positions(pc['rate'])} / h" if pc.get('rate') else 'running') if on else (f"idle {coarse(now - pc['since'])}" if pc.get('since') else 'idle'),
                      'small': (f"part {pc['part']}: {positions(pc['positions'])} positions" + (f" of {positions(pc['target'])}" if pc.get('target') else '')) if on and pc.get('positions')
                      else (pc.get('note') or (f"last part {pc['part']}: {positions(pc.get('last_positions'))} positions" + (f", {pc['seal']}" if pc.get('seal') else '')) if pc.get('part') else 'no part recorded'),
                      'focus': 4, 'until': None})
        edges.append(['pc', 'data', 'active' if on else 'idle'])
        said.append('the PC is generating data' if on else 'the PC generator is idle')
    if vm:
        gen = vm['status'] == 'RUNNING' and bool(vm.get('running'))
        nodes.append({'id': 'vm', 'col': 1, 'name': 'Cloud VM generation',
                      'state': 'active' if gen else 'idle' if vm['status'] in ('RUNNING', 'TERMINATED', 'STOPPED') else 'attention',
                      'word': (f"running {vm['running']}" if gen else str(vm['status']).lower()),
                      'big': f"~{positions(vm['rate_est'])} / h" if gen and vm.get('rate_est') else ('running' if gen else str(vm['status']).lower()),
                      'small': (f"positions, estimated from the last full run; since {est(vm['since'], now)}" if gen and vm.get('rate_est')
                                else f"since {est(vm['since'], now)}; rate not recorded" if gen else f"{positions(vm.get('verified'))} positions verified on the PC"),
                      'focus': 4, 'until': None})
        edges.append(['vm', 'data', 'active' if gen else 'idle'])
        said.append('the cloud VM is generating data' if gen else f"the cloud VM is {str(vm['status']).lower()}")
    labs = data.get('labellers') or []
    cur = next((l for l in labs if l['name'] == ov.get('net')), None)
    nodes.append({'id': 'data', 'col': 2, 'name': 'Training data', 'state': 'nominal', 'word': 'sealed',
                  'big': positions(data.get('total')) if data.get('total') else 'unknown',
                  'small': 'positions' + (f"; {positions(cur['positions'])} of them labelled by the current net" if cur else ''),
                  'focus': 4, 'until': None})
    sessions = tr.get('sessions') or []
    live = [s for s in sessions if s.get('state') in ('RUNNING', 'QUEUED')]
    q = tr.get('quota')
    nodes.append({'id': 'kaggle', 'col': 3, 'name': 'Kaggle training', 'state': 'active' if live else 'idle',
                  'word': f"{len(live)} session{'s' if len(live) != 1 else ''} running" if live else ('no session running' if tr.get('watching') else 'no session'),
                  'big': f"{q['left']:.1f} h left" if q else 'quota unknown',
                  'small': (f"GPU quota of {q['total']:.0f} h, as of {est(q['at'], now)}" + (', before the sessions now running' if live else '')
                            if q else 'no session log found')
                  + (f". In preparation: {', '.join(p['name'] for p in tr['prep'][:2])}" if tr.get('prep') else ''),
                  'focus': 3, 'until': None})
    edges.append(['data', 'kaggle', 'active' if live else 'idle'])
    said.append((f'{len(live)} Kaggle sessions are running' if len(live) > 1 else 'a Kaggle session is running') if live else 'Kaggle is idle')
    queue = snap.get('queue') or []
    kinds = {}
    for it in queue:
        kinds[it['kind']] = kinds.get(it['kind'], 0) + 1
    nodes.append({'id': 'queue', 'col': 3, 'name': 'Tests waiting', 'state': 'nominal' if queue else 'idle', 'word': 'queued' if queue else 'empty',
                  'big': f'{len(queue)} waiting', 'small': ', '.join(f'{n} {k}' for k, n in sorted(kinds.items(), key=lambda x: -x[1])[:4]) or 'the queue is empty',
                  'focus': 2, 'until': None})
    lane_said = []
    for lane in snap.get('lanes') or []:
        v, item = lane.get('sprt') or {}, lane.get('item') or {}
        net_test = v.get('klass') == 'screen' or (v.get('design') or {}).get('kind') == 'network'
        st = {'down': 'failure', 'stopped': 'failure', 'testing': 'active', 'starting': 'active', 'idle': 'idle'}[lane['state']]
        fl = v.get('flight') or {}
        word = {'down': 'down', 'stopped': 'stopped', 'idle': 'idle', 'starting': 'between stages',
                'testing': 'screening' if v.get('klass') == 'screen' else 'testing'}[lane['state']]
        short = 'waiting' if lane['state'] == 'starting' else word
        nodes.append({'id': 'lane-' + lane['id'], 'col': 4, 'name': f"GitHub lane {lane['id']}", 'state': st, 'word': word,
                      'big': 'result due' if lane['state'] == 'testing' and fl.get('eta') else short,
                      'small': (f"{item.get('title', '')}" + (f", stage {v['stage_no']} of {v['stage_count']}" if v.get('stage_no') and v.get('stage_count') and v['stage_count'] > 1 else ''))
                      if item else f"{lane['pending']} items waiting",
                      'focus': 2, 'until': fl.get('eta') if lane['state'] == 'testing' else None})
        if item:
            edges.append(['kaggle' if net_test else 'queue', 'lane-' + lane['id'], 'failure' if st == 'failure' else 'active'])
        edges.append(['lane-' + lane['id'], 'engine', 'idle'])
        lane_said.append(f"lane {lane['id']} is {word}" + (f" ({item['title']})" if item and lane['state'] in ('testing', 'starting') else ''))
    week = (ov.get('adoptions') or {}).get('week')
    nodes.append({'id': 'engine', 'col': 5, 'name': 'Engine', 'state': 'nominal',
                  'word': f"{ov.get('branch') or 'branch unknown'} at {ov.get('commit') or '?'}", 'big': ov.get('net') or 'net unknown',
                  'small': 'default net' + (f"; {week} search changes adopted this week" if week is not None else ''), 'focus': 7, 'until': None})
    g = ov.get('latest')
    ref = (g or {}).get('reference')
    nodes.append({'id': 'gauntlet', 'col': 5, 'name': 'Gauntlet', 'state': 'nominal' if g else 'idle',
                  'word': f"last {est(g['at'], now)}" if g else 'none found', 'big': f"{g['rating']:.1f}" if g else 'no rating',
                  'small': (f"± {g['err']:.1f} Elo" + (f"; {signed(ref['elo'], 0)} to {ref['name']}" if ref else '')) if g else '', 'focus': 7, 'until': None})
    edges.append(['engine', 'gauntlet', 'idle'])
    text = '; '.join(lane_said + said)
    text = (text[:1].upper() + text[1:] + '.') if text else 'No lane, generator or session was found.'
    return {'text': text, 'nodes': nodes, 'edges': edges, 'labeller': ov.get('net'),
            'loop_active': bool((pc and pc['state'] == 'active') or (vm and vm['status'] == 'RUNNING' and vm.get('running')))}
