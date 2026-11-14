# SPDX-License-Identifier: GPL-3.0-or-later
"""Readers: text or parsed JSON in, plain data out. No file access, no clock, no process: every function
here is pure, so each is tested on fixtures copied from the live files (tests: test_readers.py), including
empty, truncated and corrupt input. A reader returns None, or an empty result, for input it cannot use; it
raises ValueError only where the caller must know the format changed (the collector turns that into an alert).

Times come back as epoch seconds. The sources write them five ways: UTC to the minute (driver logs), EST with
a 12-hour clock (queue, item and watcher logs), ISO with an offset (job records, ledger, events, cloud),
float epochs (the old Control Center's state) and bare EST times without a date (chain logs)."""
import calendar
import json
import re
from datetime import datetime, timedelta, timezone

EST = timezone(timedelta(hours=-5), 'EST')
MINUS = str.maketrans({'\u2212': '-', '\u2013': '-'})


# ---------------------------------------------------------------- times

def utc_minute(text):
    """'2026-11-14 17:19' (UTC) -> epoch, or None."""
    try:
        return calendar.timegm(datetime.strptime(text.strip(), '%Y-%m-%d %H:%M').timetuple())
    except (ValueError, AttributeError):
        return None


_EST_STAMP = re.compile(r'(\d{4}-\d\d-\d\d) (\d{1,2}):(\d\d)(?::(\d\d))? ?([AP]M)(?: EST)?')


def est_stamp(text):
    """The first '2026-11-14 12:16 PM EST' (seconds optional) in the text -> epoch, or None."""
    m = _EST_STAMP.search(text or '')
    if not m:
        return None
    try:
        d = datetime.strptime(m.group(1), '%Y-%m-%d')
    except ValueError:
        return None
    hour = int(m.group(2)) % 12 + (12 if m.group(5) == 'PM' else 0)
    if hour > 23 or int(m.group(3)) > 59:
        return None
    return d.replace(hour=hour, minute=int(m.group(3)), second=int(m.group(4) or 0), tzinfo=EST).timestamp()


def iso(text):
    """ISO 8601 with an offset ('-0500', '+0000', '-08:00', 'Z'; fractional seconds allowed) -> epoch, or None."""
    if not isinstance(text, str):
        return None
    t = text.strip().replace('Z', '+00:00')
    m = re.match(r'^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?([+-]\d\d):?(\d\d)$', t)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(3) + m.group(4), '%Y-%m-%dT%H:%M:%S%z').timestamp()
    except ValueError:
        return None


def num(text):
    try:
        return float(str(text).translate(MINUS).replace(',', ''))
    except ValueError:
        return None


def jsonl(text, keep=None):
    """(records, bad lines) of a JSON-lines text. A partial or corrupt line is counted, not fatal."""
    out, bad = [], 0
    for line in (text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(rec, dict):
            out.append({k: rec.get(k) for k in keep} if keep else rec)
        else:
            bad += 1
    return out, bad


# ---------------------------------------------------------------- SPRT driver log

_DRIVER = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d) UTC (\S+): (.*)$')
_ELO = re.compile(r'Elo: (-?[\d.]+|-?inf|nan) \+/- ([\d.]+|inf|nan), nElo: (-?[\d.]+|-?inf|nan) \+/- ([\d.]+|inf|nan)')
_LLR = re.compile(r'LLR: (-?[\d.]+) \((-?[\d.]+), (-?[\d.]+)\) \[(-?[\d.]+), (-?[\d.]+)\] nElo: (.+)$')
_PTNML = re.compile(r'Ptnml\(0-2\): \[(\d+), (\d+), (\d+), (\d+), (\d+)\]')
_SHARDS = re.compile(r'Shards: (\d+).*?pairs (\d+), games (\d+) \((\d+) finished, time losses (\d+), abnormal (\d+)\)')
_STAGE = re.compile(r'^stage (\d+): (.*)$')
_RUN = re.compile(r'run (\d+)')
_HEADER = re.compile(r'^base ([0-9a-f]{7,40}), test ([0-9a-f]{7,40}), bounds \[(-?[\d.]+), (-?[\d.]+)\], stages (\d+) to (\d+)(.*)$')
_END = re.compile(r'^(decided|undecided|complete) after stage (\d+)(?:: (.*))?$')


def _fnum(s):
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v == v and abs(v) != float('inf') else None


def _header(rest):
    m = _HEADER.match(rest)
    if not m:
        return None
    h = {'base': m.group(1), 'test': m.group(2), 'elo0': float(m.group(3)), 'elo1': float(m.group(4)),
         'first_stage': int(m.group(5)), 'last_stage': int(m.group(6)), 'kind': None, 'tc_class': None,
         'cap': None, 'idea': None, 'try': None, 'futility_after': None, 'alpha': None, 'beta': None}
    tail = m.group(7)
    for key, pat in (('kind', r'kind (\w+)'), ('alpha', r'alpha ([\d.]+)'), ('beta', r'beta ([\d.]+)'),
                     ('cap', r'cap (\d+)'), ('futility_after', r'futility after (\d+)'), ('idea', r'idea (\S+)'),
                     ('try', r'\((?:try|resume of try) (\d+)')):
        mm = re.search(pat, tail)
        if mm:
            v = mm.group(1)
            h[key] = float(v) if key in ('alpha', 'beta') else int(v) if key in ('cap', 'futility_after', 'try') else v
    mm = re.search(r', (stc|ltc)\b', tail)
    if mm:
        h['tc_class'] = mm.group(1)
    return h


def driver_log(text):
    """The state of one SPRT, head-to-head or fixed-node run from its driver.log.

    {name, header, stages[], flight, end, stopped, last_at, notes}. stages are the merged ones in order, each
    cumulative: {stage, run, dispatched, merged, pairs, games, time_losses, abnormal, elo, elo_err, nelo,
    nelo_err, ptnml, llr, lo, hi, state}. flight is the stage dispatched and not yet merged. end is the
    driver's closing line {at, kind: decided|undecided|complete, stage, text}; stopped is a '; stopping' line.
    A block is used only when it is complete (it has its LLR line); a log cut mid-block keeps the block before."""
    out = {'name': None, 'header': None, 'stages': [], 'flight': None, 'end': None, 'stopped': None,
           'last_at': None, 'notes': []}
    stages, dispatched, cur = {}, {}, None
    for raw in (text or '').splitlines():
        line = raw.rstrip('\r').translate(MINUS)
        m = _DRIVER.match(line)
        if m:
            at, name, rest = utc_minute(m.group(1)), m.group(2), m.group(3)
            out['name'] = out['name'] or name
            out['last_at'] = at
            cur = None
            h = _header(rest)
            if h:
                out['header'] = h
                out['end'] = out['stopped'] = None     # a resume re-opens the test
                continue
            e = _END.match(rest)
            if e:
                out['end'] = {'at': at, 'kind': e.group(1), 'stage': int(e.group(2)), 'text': e.group(3) or ''}
                out['flight'] = None
                continue
            s = _STAGE.match(rest)
            if s:
                k, what = int(s.group(1)), s.group(2)
                run = _RUN.search(what)
                if what.rstrip().endswith('; stopping'):
                    out['stopped'] = {'at': at, 'stage': k, 'text': what}
                    out['flight'] = None
                elif 'dispatched' in what and run:
                    dispatched[k] = (int(run.group(1)), at)
                    out['flight'] = {'stage': k, 'run': int(run.group(1)), 'dispatched': at}
                    out['stopped'] = None
                elif 'waiting for run' in what and run:
                    out['flight'] = {'stage': k, 'run': int(run.group(1)), 'dispatched': dispatched.get(k, (None, at))[1]}
                elif what.endswith('merged') and run:
                    cur = {'stage': k, 'run': int(run.group(1)), 'dispatched': dispatched.get(k, (None, None))[1],
                           'merged': at}
                    if out['flight'] and out['flight']['stage'] == k:
                        out['flight'] = None
                else:
                    out['notes'].append(what[:200])
                continue
            if rest.rstrip().endswith('; stopping'):
                out['stopped'] = {'at': at, 'stage': None, 'text': rest}
            else:
                out['notes'].append(rest[:200])
            continue
        if cur is None or not line.startswith(' '):
            continue
        s = line.strip()
        mm = _SHARDS.search(s)
        if mm:
            cur.update(pairs=int(mm.group(2)), games=int(mm.group(3)), time_losses=int(mm.group(5)),
                       abnormal=int(mm.group(6)))
            continue
        mm = _ELO.search(s)
        if mm:
            cur.update(elo=_fnum(mm.group(1)), elo_err=_fnum(mm.group(2)), nelo=_fnum(mm.group(3)),
                       nelo_err=_fnum(mm.group(4)))
            continue
        mm = _PTNML.search(s)
        if mm:
            cur['ptnml'] = [int(x) for x in mm.groups()]
            continue
        mm = _LLR.search(s)
        if mm:
            cur.update(llr=float(mm.group(1)), lo=float(mm.group(2)), hi=float(mm.group(3)), state=mm.group(6).strip())
            if 'games' in cur and 'elo' in cur:
                stages[cur['stage']] = cur
            cur = None
    out['stages'] = [stages[k] for k in sorted(stages)]
    out['notes'] = out['notes'][-5:]
    return out


def design(d):
    """design.json (every value a string) -> typed fields, or None when it is not a design."""
    if not isinstance(d, dict) or 'elo0' not in d:
        return None
    f = lambda k: num(d.get(k))  # noqa: E731
    i = lambda k: int(f(k)) if f(k) is not None else None  # noqa: E731
    return {'kind': d.get('kind'), 'tc_class': d.get('tc_class'), 'tc': d.get('tc'), 'games': i('games'),
            'cap': i('cap'), 'elo0': f('elo0'), 'elo1': f('elo1'), 'alpha': f('alpha'), 'beta': f('beta'),
            'futility_after': i('futility_after'), 'shards': i('shards'), 'hash': i('hash'), 'idea': d.get('idea'),
            'base': d.get('base'), 'test': d.get('test'), 'declared': iso(d.get('declared_at'))}


def outcome(verdict_text, drv, has_design):
    """How a finished or stopped test reads: {kind, label, meaning}. kind is one of passed, rejected, capped,
    complete, screen, stopped, interrupted, running, other. An unknown verdict is shown as written."""
    v = (verdict_text or '').strip()
    low = v.lower()
    if not has_design and drv and drv.get('stages') and (drv.get('end') or v):
        return {'kind': 'screen', 'label': 'Screen finished', 'meaning': 'a fixed-length measurement; its Elo is the result'}
    if low.startswith('h1 accepted'):
        return {'kind': 'passed', 'label': 'Passed', 'meaning': 'the gain is confirmed at this time control'}
    if low.startswith('h0 accepted'):
        return {'kind': 'rejected', 'label': 'Rejected', 'meaning': 'no gain shown'}
    if low.startswith('futility'):
        return {'kind': 'rejected', 'label': 'Rejected early', 'meaning': 'below zero after the early look'}
    if low.startswith('capped'):
        return {'kind': 'capped', 'label': 'Capped', 'meaning': 'undecided at the game limit, not passed'}
    if low.startswith('complete'):
        return {'kind': 'complete', 'label': 'Complete', 'meaning': 'fixed-length run finished'}
    if low.startswith(('stopped', 'tabled')):
        return {'kind': 'stopped', 'label': v.split(' ', 1)[0].capitalize(), 'meaning': v[:160]}
    if v:
        return {'kind': 'other', 'label': v[:60], 'meaning': v[:160]}
    if drv and drv.get('stopped'):
        return {'kind': 'interrupted', 'label': 'Stopped by a failure', 'meaning': drv['stopped']['text'][:160]}
    return {'kind': 'running', 'label': 'No verdict', 'meaning': ''}


# ---------------------------------------------------------------- queue

_QUEUE_LINE = re.compile(r'^(?:lane (\w+): )?(\d{4}-\d\d-\d\d \d{1,2}:\d\d [AP]M EST) (\S+?): (.*)$')
_ITEM_UTC = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d UTC (\S+): ')
_PREFIX = re.compile(r'^z?\d+[a-z]?\d*-')
_SUFFIX = re.compile(r'-(stc|ltc|retry|nonreg|h2h|fn|screen)$')
_KINDS = {'stc': 'STC', 'ltc': 'LTC', 'retry': 'retry', 'nonreg': 'non-regression', 'h2h': 'head-to-head',
          'fn': 'screen', 'screen': 'screen'}


def queue_log(text):
    """Events of a lane's queue log: [{at, key, text, kind: done|failed|skipped|other}]."""
    out = []
    for line in (text or '').splitlines():
        m = _QUEUE_LINE.match(line.strip())
        if not m:
            continue
        what = m.group(4)
        kind = 'done' if what == 'done' else 'skipped' if 'skipped' in what else 'failed' if what.startswith('failed') else 'other'
        out.append({'at': est_stamp(m.group(2)), 'key': m.group(3), 'text': what[:200], 'kind': kind})
    return out


def item_log(text):
    """What an item's own log says: {sprt, waiting, last_line}. sprt is the test name of its last driver
    line (the item key is not the test name); waiting is true when its last line is a gate or not-ready note."""
    sprt, last = None, ''
    for line in (text or '').splitlines():
        if not line.strip():
            continue
        if not line.startswith(' '):
            last = line.strip()
        m = _ITEM_UTC.match(line)
        if m:
            sprt = m.group(1).split('.')[0] if re.search(r'\.[^.]+-[^.]+$', m.group(1)) else m.group(1)
    low = last.lower()
    return {'sprt': sprt, 'waiting': 'gated: waits for' in low or 'not ready' in low, 'last_line': last[:240]}


def lane_marker(text):
    """A lane's current-item marker (state/current-<LANE>.txt, KEY=VALUE lines, written by the queue runner or
    by its bridging watcher since 2026-11-14): {lane, state: running|idle|stopped, item, started, drivers[],
    source, updated}. None when the text is not a marker (no lane or no state line)."""
    kv = {}
    for line in (text or '').splitlines():
        k, sep, v = line.partition('=')
        if sep and re.match(r'^[a-z_]+$', k.strip()):
            kv[k.strip()] = v.strip()
    if not kv.get('lane') or kv.get('state') not in ('running', 'idle', 'stopped'):
        return None
    epoch = lambda k: num(kv[k]) if kv.get(k) else None  # noqa: E731
    return {'lane': kv['lane'], 'state': kv['state'], 'item': kv.get('item') or None,
            'started': epoch('started_epoch') or est_stamp(kv.get('started', '')),
            'since': est_stamp(kv.get('since', '')), 'drivers': [d for d in re.split(r'[,\s]+', kv.get('drivers', '')) if d],
            'source': kv.get('source') or 'chain', 'updated': epoch('updated_epoch') or est_stamp(kv.get('updated', '')),
            'last_item': kv.get('last_item') or None, 'last_exit': kv.get('last_exit') or None}


def item_kind(key):
    """The plain kind of a queue item or test from its name: STC, LTC, retry, screen, ..."""
    kinds = []
    k = key
    while True:
        m = _SUFFIX.search(k)
        if not m:
            break
        kinds.insert(0, _KINDS[m.group(1)])
        k = k[:m.start()]
    if not kinds:
        return 'gauntlet' if 'gauntlet' in key else 'screen' if '-vs-' in key else 'test'
    return ' '.join(dict.fromkeys(kinds))


def item_title(key, sprt=None, codes=None, ideas=None):
    """A readable name for a queue item or test, made from the name alone plus the survey's code table and
    the ideas list: {title, about}. 'z70a-f11-root-lean-ltc' -> title 'F11 root lean', about 'Optimism ...'."""
    name = sprt or key
    base = _PREFIX.sub('', name)
    while _SUFFIX.search(base):
        base = _SUFFIX.sub('', base)
    if '-vs-' in base:
        left, right = base.split('-vs-', 1)
        left = re.sub(r'^.*?(?:-fn-|^fn-)', '', left)
        return {'title': f'{left} against {right}'.replace('-', ' '), 'about': 'net against net'}
    if '-promo' in base:
        return {'title': base.split('-promo')[0] + ' promotion test', 'about': 'net against the default net'}
    parts = base.split('-')
    code = parts[0]
    if codes and len(parts) > 1 and code.upper() in codes:
        return {'title': f'{code.upper()} ' + ' '.join(parts[1:]), 'about': codes[code.upper()]}
    m = re.match(r'^(?:i|idea)(\d+)$', code)
    if m and ideas and int(m.group(1)) in ideas:
        rest = ' '.join(parts[1:])
        return {'title': f'Idea {m.group(1)}' + (f' {rest}' if rest else ''), 'about': ideas[int(m.group(1))]}
    title = ' '.join(parts)
    return {'title': title[:1].upper() + title[1:], 'about': None}


def item_comment(script):
    """The first sentence of an item script's own description (its leading comment), or None."""
    words = []
    for line in (script or '').splitlines()[:30]:
        s = line.strip()
        if s.startswith('#!') or not s.startswith('#'):
            if words:
                break
            continue
        words.append(s.lstrip('#').strip())
    text = re.sub(r'\s+', ' ', ' '.join(words)).strip()
    if not text:
        return None
    m = re.search(r'(?<=[a-z0-9)\'"])\. (?=[A-Z])', text)
    if m and m.start() > 30:
        text = text[:m.start() + 1]
    return text if len(text) <= 260 else text[:257].rsplit(' ', 1)[0] + '...'


def survey_codes(md):
    """{code: meaning} from the engine survey's comparison table rows '| F11 | Optimism (...) | ...'."""
    out = {}
    for line in (md or '').splitlines():
        m = re.match(r'^\|\s*([A-Z]\d{1,3})\s*\|\s*([^|]+?)\s*\|', line)
        if m:
            out[m.group(1)] = re.sub(r'[*`]', '', m.group(2))[:120]
    return out


def ideas_md(md):
    """{number: title} from docs/ideas.md headings '## 124. Root reductions (...)' and '### 157. ...'."""
    out = {}
    for line in (md or '').splitlines():
        m = re.match(r'^#{2,3} (\d+)\. (.+?)\s*(?:\(.*)?$', line)
        if m:
            out[int(m.group(1))] = m.group(2).strip()[:120]
    return out


# ---------------------------------------------------------------- jobs, ledger, events

def job_record(rec):
    """A jobctl record reduced to what the display may show (no command line, no paths)."""
    if not isinstance(rec, dict) or not rec.get('name'):
        return None
    return {'name': str(rec['name']), 'type': rec.get('type'), 'state': rec.get('state'), 'id': rec.get('id'),
            'started': iso(rec.get('started')), 'ended': iso(rec.get('ended') or rec.get('stopped')),
            'exit_code': rec.get('exit_code'), 'pid': rec.get('pid'), 'keeper': rec.get('keeper'),
            'pid_started': rec.get('pid_started'), 'keeper_started': rec.get('keeper_started')}


def job_script(rec):
    """The script a job runs (the last command argument ending .sh or .py), for discovery; never displayed."""
    cmd = rec.get('command') if isinstance(rec, dict) else None
    if not isinstance(cmd, list):
        return None
    for a in reversed(cmd):
        if isinstance(a, str) and re.search(r'\.(sh|py)$', a):
            return a
    return None


def chain_items_folder(script):
    """The items folder a queue runner script reads ('I=$N/items-b' -> 'items-b'), or None."""
    m = re.search(r'^\s*I=\$N/([\w.-]+)\s*$', script or '', re.M)
    return m.group(1) if m else None


def events(text):
    """Supervisor events, reduced: [{at, event, name, type, exit_code}] (command lines are dropped)."""
    recs, bad = jsonl(text)
    out = [{'at': iso(r.get('at')), 'event': r.get('event'), 'name': r.get('name'), 'type': r.get('type'),
            'exit_code': r.get('exit_code')} for r in recs if r.get('event') and r.get('name')]
    return out, bad


def ledger(text):
    recs, bad = jsonl(text)
    out = [{'at': iso(r.get('at')), 'sprt': r.get('sprt'), 'stage': r.get('stage'), 'run_id': r.get('run_id')}
           for r in recs if r.get('sprt') is not None and r.get('run_id') is not None]
    return out, bad


def tries(text):
    recs, bad = jsonl(text)
    return {r['sprt']: {'idea': r.get('idea'), 'kind': r.get('kind'), 'tc_class': r.get('tc_class'), 'try': r.get('try')}
            for r in recs if r.get('sprt')}, bad


# ---------------------------------------------------------------- overview

def default_net(cmakelists):
    m = re.search(r'set\(FORK_NET "\$\{CMAKE_SOURCE_DIR\}/nets/([A-Za-z0-9_+-]+)\.fnet"', cmakelists or '')
    return m.group(1) if m else None


def nets_md(md):
    """{default, since, entries[{name, title, status}]} from docs/nets.md: one '## name, ...' section per net
    with an Item/Value table; the default is the entry whose Status says 'default network since DATE'."""
    entries, default, since = [], None, None
    for sec in re.split(r'^## ', md or '', flags=re.M)[1:]:
        head, _, body = sec.partition('\n')
        m = re.match(r'^([A-Za-z0-9_+-]+), (.*)$', head.strip())
        st = re.search(r'^\|\s*Status\s*\|\s*(.*?)\s*\|\s*$', body, re.M)
        if not m or not st:
            continue
        status = re.sub(r'\*\*', '', st.group(1))
        entries.append({'name': m.group(1), 'title': m.group(2)[:160], 'status': status[:300]})
        d = re.search(r'default network since (\d{4}-\d\d-\d\d)', status)
        if d:
            default, since = m.group(1), d.group(1)
    return {'default': default, 'since': since, 'entries': entries}


def ordo(text, player='Fork'):
    """{rating, error, points, played} of the player in an Ordo table, plus anchors {name: rating}; or None."""
    row, anchors = None, {}
    for line in (text or '').splitlines():
        m = re.match(r'^\s*\d+\s+(.+?)\s*:\s+([\d.]+)\s+([\d.]+|-+)\s+([\d.]+)\s+(\d+)\s+', line)
        if not m:
            continue
        if m.group(1).strip() == player:
            row = {'rating': float(m.group(2)), 'error': _fnum(m.group(3)), 'points': float(m.group(4)),
                   'played': int(m.group(5))}
        else:
            anchors[m.group(1).strip()] = float(m.group(2))
    if row:
        row['anchors'] = anchors
    return row


def gauntlet_meta(text):
    """meta.txt (tab-separated key/value head) -> {run, at, commit, book, kind, conclusion}."""
    kv = {}
    for line in (text or '').splitlines():
        if line.startswith('#'):
            break
        k, _, v = line.partition('\t')
        if v:
            kv[k.strip()] = v.strip()
    if 'run' not in kv:
        return None
    title = kv.get('title', '')
    m = re.search(r'\b([0-9a-f]{40})\b', title)
    return {'run': kv['run'], 'at': iso(kv.get('created_at')), 'commit': (m.group(1) if m else kv.get('head_sha', ''))[:7],
            'book': 'uho-reserved' if 'uho' in title.lower() else 'balanced',
            'kind': 'check' if kv.get('layout', '').startswith('check-result') else 'gauntlet',
            'conclusion': kv.get('conclusion')}


def gauntlet_summary(md):
    """From a gauntlet's summary.md: {reference{name, rating, elo, lo, hi}, transfer{ratio, lo, hi}, gain{elo, sd}}.
    Each part is None when its line is absent (older gauntlets have no reference opponent)."""
    text = (md or '').translate(MINUS)
    out = {'reference': None, 'transfer': None, 'gain': None}
    m = re.search(r'^- (.+?) \(CCRL Blitz (\d+)[^)]*\): Fork .*?Elo (-?[\d.]+), 95% interval (-?[\d.]+|-?inf) to (-?[\d.]+|-?inf)',
                  text, re.M)
    if m:
        out['reference'] = {'name': m.group(1), 'rating': int(m.group(2)), 'elo': float(m.group(3)),
                            'lo': _fnum(m.group(4)), 'hi': _fnum(m.group(5))}
    m = re.search(r'^- Transfer ratio (-?[\d.]+), 95% interval (-?[\d.]+) to (-?[\d.]+)', text, re.M)
    if m:
        out['transfer'] = {'ratio': float(m.group(1)), 'lo': float(m.group(2)), 'hi': float(m.group(3))}
    m = re.search(r'^- On .*?: ([+-][\d.]+) Elo, bootstrap SD ([\d.]+)', text, re.M)
    if m:
        out['gain'] = {'elo': float(m.group(1)), 'sd': float(m.group(2))}
    return out


def anchor_check(md):
    """An anchor check's summary.md -> {outcome: confirmed|consistent|flagged, gain, lo, hi}, or None."""
    text = (md or '').translate(MINUS)
    o = re.search(r'\*\*Outcome: (confirmed|consistent|flagged)', text)
    p = re.search(r'^\| Pooled \|[^|]*\|[^|]*\| ([+-]?[\d.]+) \| [\d.]+ \| ([+-]?[\d.]+) to ([+-]?[\d.]+) \|', text, re.M)
    if not o or not p:
        return None
    return {'outcome': o.group(1), 'gain': float(p.group(1)), 'lo': float(p.group(2)), 'hi': float(p.group(3))}


def transfer(d):
    """tools/gauntlet/transfer.json -> adopted changes [{change, elo, err, test, tests}]. tests holds every
    test the entry names (its adopting test, and an earlier STC or first try recorded beside it)."""
    if not isinstance(d, dict) or not isinstance(d.get('adopted'), list):
        raise ValueError('transfer.json has no adopted list')
    name = lambda v: str(v).split(':')[0].strip()[:60]  # noqa: E731
    return [{'change': str(a.get('change', ''))[:120], 'elo': num(a.get('elo')), 'err': num(a.get('ci95')),
             'test': name(a.get('test', '')), 'tests': [name(a[k]) for k in ('test', 'stc', 'ltc', 'first') if a.get(k)]}
            for a in d['adopted'] if isinstance(a, dict)]


_ADOPT = re.compile(r'^(\S+) (\d{4}-\d\d-\d\d) (?:Search|UCI|NNUE|Eval|Engine|Time): (.*? adopted on (?:its|their) .*)$')


def adoptions(git_log):
    """Adoption commits from `git log --format='%h %ad %s' --date=short`: [{commit, date, what}].
    'not adopted' and 'neither adopted' do not count."""
    out = []
    for line in (git_log or '').splitlines():
        m = _ADOPT.match(line.strip())
        if m and not re.search(r'\b(not|neither|never) adopted\b', m.group(3)):
            out.append({'commit': m.group(1), 'date': m.group(2), 'what': m.group(3).split(' adopted on ')[0][:120]})
    return out


def stack_sum(item_log_text):
    """The claimed sum of separate tests in a stacking check's item log ('sum +18.70'), or None."""
    m = re.search(r'sum \+?(-?[\d.]+)', (item_log_text or '').translate(MINUS))
    return float(m.group(1)) if m else None


def perf_log(md):
    """Speed milestones from the performance log: [{date, change, what}] for each '| nps, ...' table row,
    dated by the nearest heading above it. Not a time series: machines and targets differ between rows."""
    out, date, head = [], None, ''
    for line in (md or '').splitlines():
        if line.startswith('#'):
            d = re.search(r'(\d{4}-\d\d-\d\d)', line)
            date, head = (d.group(1) if d else date), re.sub(r'^#+\s*', '', line)[:120]
            continue
        m = re.match(r'^\|\s*nps, ([^|]+)\|[^|]*\|[^|]*\|\s*\**([+-][\d.]+%)', line.translate(MINUS))
        if m and date:
            out.append({'date': date, 'change': m.group(2), 'what': f'{head}: {m.group(1).strip()}'[:200]})
    return out


def decisions(md, limit=6):
    """The last lines of MORNING.md's 'Decisions for the owner' section, as text (the file does not mark an
    item open or answered, so the display shows them as written)."""
    m = re.search(r'^## Decisions for the owner\s*\n(.*?)(?=^## |\Z)', md or '', re.M | re.S)
    if not m:
        return []
    lines = [re.sub(r'^[-*]\s*', '', x.strip()) for x in m.group(1).splitlines() if x.strip()]
    return [x[:300] for x in lines[-limit:]]


# ---------------------------------------------------------------- training

def gates_json(d):
    """One net's gate result: {failed, clamped, recall_ok, recall, heldout[{name, ratio, flagged, positions}]}."""
    if not isinstance(d, dict) or 'gates_failed' not in d:
        raise ValueError('gates.json has no gates_failed field')
    held = []
    for key, label in (('heldout', '4-5 pieces'), ('heldout67', '6-7 pieces')):
        h = d.get(key)
        if isinstance(h, dict) and isinstance(h.get('ratio'), (int, float)):
            held.append({'name': label, 'ratio': round(h['ratio'], 3), 'flagged': bool(h.get('flagged')),
                         'positions': h.get('positions'), 'reference': h.get('reference')})
    recall = str(d.get('recall', ''))
    m = re.search(r'cand (\d+) of (\d+) misjudged', recall)
    return {'failed': bool(d['gates_failed']), 'clamped': d.get('clamped'), 'scale': d.get('scale'),
            'recall': {'misjudged': int(m.group(1)), 'of': int(m.group(2)), 'passed': 'passed' in recall} if m else None,
            'heldout': held, 'flags': sum(1 for h in held if h['flagged'])}


def gates_txt(text):
    """A session's 'ARM exit=N flags=N' lines -> {arm: {exit, flags, note}}."""
    out = {}
    for line in (text or '').splitlines():
        m = re.match(r'^(\S+) exit=(-?\d+) flags=(\d+)\s*$', line.strip())
        if m:
            out[m.group(1)] = {'exit': int(m.group(2)), 'flags': int(m.group(3)), 'note': None}
            continue
        m = re.match(r'^(\S+) (invalid|nowarm)\s*$', line.strip())
        if m:
            out[m.group(1)] = {'exit': None, 'flags': 0, 'note': m.group(2)}
    return out


def bakes_txt(text):
    """'net commit nodes signature' lines; the last line per net wins -> {net: {commit, nodes, signature}}."""
    out = {}
    for line in (text or '').splitlines():
        m = re.match(r'^(\S+) ([0-9a-f]{40}) (\d+) ([0-9a-f]{16})\s*$', line.strip())
        if m:
            out[m.group(1)] = {'commit': m.group(2)[:7], 'nodes': int(m.group(3)), 'signature': m.group(4)}
    return out


_RESULT = re.compile(r'^(?:- )?(\d{4}-\d\d-\d\d \d{1,2}:\d\d [AP]M EST) (.*?)Elo: (-?[\d.]+) \+/- ([\d.]+), nElo: (-?[\d.]+) \+/- ([\d.]+)')


def results_txt(text):
    """Screen result lines ('<EST stamp> <who>: Elo: e +/- h, nElo: ...') -> [{at, name, text, elo, elo_err}].
    name is the test name when the line starts with one."""
    out = []
    for line in (text or '').splitlines():
        m = _RESULT.match(line.strip().translate(MINUS))
        if not m:
            continue
        who = m.group(2).strip().rstrip(':').strip()
        name = re.match(r'^([\w.+-]+)$', who)
        ref = re.search(r'\(([\w.+-]+-fn-[\w.+-]+)[;)]', line)
        out.append({'at': est_stamp(m.group(1)), 'name': name.group(1) if name else ref.group(1) if ref else None,
                    'text': who[:200], 'elo': float(m.group(3)), 'elo_err': float(m.group(4))})
    return out


def fetch_log(text):
    """A session's fetch log: {ended: status text, quota{used, left, total, reset}, fetched}. Times in these
    logs carry no date, so the caller dates them by the file's modified time."""
    out = {'ended': None, 'quota': None, 'fetched': False}
    for line in (text or '').splitlines():
        m = re.search(r'session ended: "?(?:KernelWorkerStatus\.)?(\w+)"?', line)
        if m:
            out['ended'] = m.group(1)
        m = re.search(r'quota after the session: GPU ([\d.]+)h ([\d.]+)h ([\d.]+)h (\S+)', line)
        if m:
            out['quota'] = {'used': float(m.group(1)), 'left': float(m.group(2)), 'total': float(m.group(3)),
                            'reset': iso(m.group(4))}
        if re.search(r'\bfetched\s*$', line):
            out['fetched'] = True
    return out


def kaggle_status(text):
    """`kaggle kernels status REF` output -> the state word (COMPLETE, RUNNING, QUEUED, ERROR, CANCEL...), or None."""
    m = re.search(r'has status "?(?:KernelWorkerStatus\.)?(\w+)"?', text or '')
    return m.group(1).upper() if m else None


def kernel_refs(text):
    """Kaggle kernel references ('owner/fork-...') named in a text, in order of first appearance. A piece of
    a file path ('C:/Users/name/fork-data/x') is not a reference: the match must stand alone, with no path
    character before or after it. The collector further polls only references it also finds as the id of a
    kernel-metadata.json (the first version of this reader took a path for a kernel, 2026-11-14)."""
    return list(dict.fromkeys(re.findall(r'(?<![\w/\\:.~-])([A-Za-z0-9_-]+/fork-[A-Za-z0-9_-]+)(?![\w/\\.-])', text or '')))


def kernel_id(d):
    """The kernel a kernel-metadata.json was pushed as ('owner/name'), or None."""
    v = d.get('id') if isinstance(d, dict) else None
    return v if isinstance(v, str) and re.match(r'^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+$', v) else None


def uho_run(d):
    """A UHO diagnostic run: {name, ratio} (the candidate's median advantage over Stockfish's), or None."""
    try:
        return {'name': d['name'], 'ratio': round(float(d['static']['adv']['median_ratio']), 3)}
    except (KeyError, TypeError, ValueError):
        return None


def retrain_json(d):
    """A session's own record, reduced: {arms{name: {seed, init, superbatches, valid}}, inputs_ok, ok}."""
    try:
        arms = d['settings']['arms']
        val = d.get('validity', {})
    except (KeyError, TypeError) as e:
        raise ValueError('retrain.json has no settings.arms') from e
    per = val.get('per_arm', {}) if isinstance(val, dict) else {}
    return {'arms': {k: {'seed': v.get('seed'), 'init': v.get('init'), 'superbatches': v.get('superbatches'),
                         'valid': per.get(k)} for k, v in arms.items() if isinstance(v, dict)},
            'inputs_ok': val.get('inputs_ok') if isinstance(val, dict) else None,
            'ok': val.get('ok') if isinstance(val, dict) else None}


def arm_of(net, arms):
    """('eplo', 2) for net 'r8ceplo2' given the session's arm names; the retrain prefix is whatever precedes
    the arm name. None when no arm matches."""
    best = None
    for a in arms:
        if net.endswith(a) and (best is None or len(a) > len(best)):
            best = a
    if not best:
        return None
    m = re.match(r'^(.*?)(\d)$', best)        # the last digit is the seed: 'i801' is arm i80, seed 1
    return (m.group(1), int(m.group(2))) if m else (best, None)


def ld_decision(d):
    if not isinstance(d, dict) or 'verdict' not in d:
        return None
    pooled = {k: {'elo': v.get('elo'), 'err': v.get('half_95'), 'qualifies': v.get('qualifies')}
              for k, v in (d.get('pooled') or {}).items() if isinstance(v, dict)}
    return {'verdict': str(d['verdict'])[:160], 'winner': d.get('winner'), 'pooled': pooled}


# ---------------------------------------------------------------- data

_PROGRESS = re.compile(r'^(\d+) s: (\d+) games, (\d+) positions, (\d+) positions/s$')
_DONE = re.compile(r'^done: (\d+) games, (\d+) positions in ([\d.]+) s \((\d+) positions/s\)$')


def datagen_log(text, window=3600):
    """A part's generator log: {seconds, games, positions, rate (positions/h over the last `window` seconds
    of lines), done}. The log's own positions/s is the average since the start, so the recent rate is taken
    from two lines. None when the text has no progress line."""
    pts, done = [], None
    for line in (text or '').splitlines():
        m = _PROGRESS.match(line.strip())
        if m:
            pts.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
            continue
        m = _DONE.match(line.strip())
        if m:
            done = {'games': int(m.group(1)), 'positions': int(m.group(2)), 'seconds': float(m.group(3))}
    if not pts and not done:
        return None
    if done:
        return {'seconds': done['seconds'], 'games': done['games'], 'positions': done['positions'], 'rate': 0, 'done': True}
    s, g, p = pts[-1]
    first = next((x for x in pts if s - x[0] <= window), pts[0])
    rate = (p - first[2]) / (s - first[0]) * 3600 if s > first[0] else None
    return {'seconds': s, 'games': g, 'positions': p, 'rate': round(rate) if rate is not None else None, 'done': False}


def watchdog(d):
    """The old Control Center's watchdog heartbeat: {part, running, heartbeat, exited, how}."""
    if not isinstance(d, dict) or 'part' not in d:
        return None
    return {'part': d.get('part'), 'running': bool(d.get('running')), 'heartbeat': d.get('heartbeat'),
            'exited': d.get('exited'), 'how': d.get('how')}


def part_json(d):
    if not isinstance(d, dict) or not d.get('name'):
        return None
    s = d.get('settings') if isinstance(d.get('settings'), dict) else {}
    return {'name': d['name'], 'net': d.get('net'), 'generation': d.get('generation'), 'dir': d.get('dir'),
            'target': s.get('positions_target'), 'threads': s.get('threads')}


def seal_result(d):
    if not isinstance(d, dict) or 'state' not in d:
        return None
    return {'state': d['state'], 'at': d.get('at'), 'message': str(d.get('message', ''))[:200]}


def labeller(evaluator):
    """'nnue (r8brft1)' -> 'r8brft1'; 'bootstrap ...' -> 'bootstrap'."""
    m = re.search(r'\(([^)]+)\)', evaluator or '')
    return m.group(1) if m else (str(evaluator).split()[0] if evaluator else None)


def manifest(d):
    """A data manifest reduced: {run, labeller, games, positions, unsaved, part_end, is_part}; None for a
    dataset manifest (no generator). is_part is false for cuts (a part_end that says 'not a part') and for
    snapshots of a running run (the tool text says so): both are subsets of a part and must not be added to
    totals."""
    if not isinstance(d, dict):
        raise ValueError('manifest is not an object')
    if 'generator' not in d:
        return None     # a snapshot or dataset manifest: it lists sources, it generated nothing
    gen = d.get('generator') if isinstance(d.get('generator'), dict) else {}
    totals = d.get('totals') if isinstance(d.get('totals'), dict) else {}
    pos = d.get('positions', totals.get('positions'))
    end = str(d.get('part_end', ''))
    return {'run': d.get('run'), 'labeller': labeller(gen.get('evaluator')), 'games': d.get('games', totals.get('games')),
            'positions': pos, 'unsaved': d.get('positions_unsaved', totals.get('positions_unsaved')),
            'part_end': end[:160],
            'is_part': (isinstance(d.get('settings'), dict) and not end.startswith('not a part')
                        and not re.search(r'\bsnapshot\b|^cut of\b', str(gen.get('tool', '')).lower()))}


def gcp_status(d):
    """The cloud watcher's status file reduced by allow-list (the VM's address is never read out):
    {at, vm{status, machine_type, provisioning, last_start, last_stop}, running, items{name: {class, state}},
    worker_at, worker_error, events[{at, event, name, why}]}."""
    if not isinstance(d, dict) or 'vm' not in d:
        raise ValueError('status.json has no vm field')
    vm = d.get('vm') if isinstance(d.get('vm'), dict) else {}
    w = d.get('worker') if isinstance(d.get('worker'), dict) else {}
    items = {str(k): {'class': v.get('class'), 'state': v.get('state'), 'resumes': v.get('resumes')}
             for k, v in (w.get('items') or {}).items() if isinstance(v, dict)}
    evs = [{'at': iso(e.get('at')), 'event': e.get('event'), 'name': e.get('name'), 'why': str(e.get('why', ''))[:120]}
           for e in d.get('events') or [] if isinstance(e, dict)]
    return {'at': est_stamp(str(d.get('at', ''))),
            'vm': {'status': vm.get('status'), 'machine_type': vm.get('machine_type'), 'provisioning': vm.get('provisioning'),
                   'last_start': iso(vm.get('last_start')), 'last_stop': iso(vm.get('last_stop'))},
            'running': w.get('running'), 'items': items, 'worker_at': iso(w.get('at')),
            'worker_error': str(w['error'])[:120] if w.get('error') else None, 'events': evs}


def gcp_rates(d):
    """Only the three cost rates of gcp.json; every other field (project, billing, keys) is left unread."""
    if not isinstance(d, dict):
        return None
    return {k: d.get(k) for k in ('usd_per_hour_running', 'usd_per_hour_stopped', 'egress_usd_per_gib')
            if isinstance(d.get(k), (int, float))}


def egress(text):
    recs, bad = jsonl(text)
    return {'usd': round(sum(r.get('usd', 0) for r in recs if isinstance(r.get('usd'), (int, float))), 4),
            'bytes': sum(r.get('bytes', 0) for r in recs if isinstance(r.get('bytes'), int)), 'pulls': len(recs)}, bad


def filler_ok(text):
    """'424 chunk(s), 106192556 positions verified into ...' -> {chunks, positions}, or None."""
    m = re.match(r'^(\d+) chunk\(s\), (\d+) positions verified', (text or '').strip())
    return {'chunks': int(m.group(1)), 'positions': int(m.group(2))} if m else None


_ARMS = re.compile(r'^(\d{4}-\d\d-\d\d \d{1,2}:\d\d:\d\d [AP]M EST) (\S+): (\d+) s, (\d+) live: (.*)$')


def arms_log(text):
    """The label-depth arms' heartbeat: {at, tag, seconds, live, arms{name: positions}} of the last line."""
    last = None
    for line in (text or '').splitlines():
        m = _ARMS.match(line.strip())
        if m:
            arms = {a: int(p) for a, p in re.findall(r'(\w+)\s+(\d+) positions', m.group(5))}
            if arms:
                last = {'at': est_stamp(m.group(1)), 'tag': m.group(2), 'seconds': int(m.group(3)),
                        'live': int(m.group(4)), 'arms': arms}
    return last


# ---------------------------------------------------------------- machine

def freezewatch(text):
    """The freeze monitor's log: {samples[{at, avail_mb, commit}], stalls[{at, seconds}], stall_count}."""
    samples, stalls, count = [], [], None
    for line in (text or '').splitlines():
        at = est_stamp(line)
        m = re.search(r'heartbeat: (\d+) stalls? so far; avail (\d+) MB, commit ([\d.]+)%', line)
        if m and at:
            count = int(m.group(1))
            samples.append({'at': at, 'avail_mb': int(m.group(2)), 'commit': float(m.group(3))})
            continue
        m = re.search(r'STALL: (\d+) s', line)
        if m and at:
            stalls.append({'at': at, 'seconds': int(m.group(1))})
    return {'samples': samples, 'stalls': stalls, 'stall_count': count if count is not None else len(stalls)}


def wslcache(text):
    """The WSL cache job's log: {at, cache_mb, limit_mb, drops[{at, before, after}]} (the last line's state)."""
    last, limit, drops = None, None, []
    for line in (text or '').splitlines():
        at = est_stamp(line)
        m = re.search(r'dropped: WSL cache (\d+) -> (\d+|\?) MB', line)
        if m and at:
            after = int(m.group(2)) if m.group(2).isdigit() else None
            drops.append({'at': at, 'before': int(m.group(1)), 'after': after})
            last = {'at': at, 'cache_mb': after}
            continue
        m = re.search(r'WSL cache (\d+) MB \(under (\d+)\)', line)
        if m and at:
            last, limit = {'at': at, 'cache_mb': int(m.group(1))}, int(m.group(2))
    if not last:
        return None
    return {**last, 'limit_mb': limit, 'drops': drops[-20:], 'drop_count': len(drops)}


def memwatch(text):
    """The memory watch's log: {started, actions[{at, kind: dropped|stopped|alert, text}]}."""
    started, actions = None, []
    for line in (text or '').splitlines():
        at = est_stamp(line)
        if 'started (pid' in line:
            started = at
        elif 'ALERT' in line:
            actions.append({'at': at, 'kind': 'alert', 'text': line.split('memwatch', 1)[-1][:200]})
        elif 'stopped agent job' in line:
            actions.append({'at': at, 'kind': 'stopped', 'text': line.split('memwatch', 1)[-1][:200]})
        elif "dropped WSL's page cache" in line:
            actions.append({'at': at, 'kind': 'dropped', 'text': line.split('memwatch', 1)[-1][:200]})
    return {'started': started, 'actions': actions[-20:]}


def compile_waits(text, day):
    """Seconds waited for the compile lock on `day` ('2026-11-13') and the last waits: {seconds, waits}."""
    total, waits = 0, []
    for line in (text or '').splitlines():
        m = re.match(r'^(\d{4}-\d\d-\d\d) (\d+) (\S+) ', line.strip())
        if m and m.group(1) == day:
            total += int(m.group(2))
            waits.append({'seconds': int(m.group(2)), 'who': m.group(3)})
    return {'seconds': total, 'waits': waits[-8:]}


# ---------------------------------------------------------------- preliminary results (per-shard progress)

def shard_progress(d):
    """One shard's progress record (the proposed artifact content, DESIGN.md section 8):
    {"sprt": name, "stage": K, "shard": i, "ptnml": [5 counts], "finished_games": n, "at": ISO time}.
    Returns {sprt, stage, shard, ptnml, games, at}; raises ValueError for anything else, so a changed
    format is reported and never shown as a result."""
    if not isinstance(d, dict):
        raise ValueError('progress record is not an object')
    p = d.get('ptnml')
    if not (isinstance(p, list) and len(p) == 5 and all(isinstance(c, int) and not isinstance(c, bool) and c >= 0 for c in p)):
        raise ValueError('progress record has no pentanomial count of five non-negative integers')
    if not isinstance(d.get('stage'), int) or not isinstance(d.get('shard'), int):
        raise ValueError('progress record has no stage or shard number')
    games = d.get('finished_games')
    return {'sprt': d.get('sprt'), 'stage': d['stage'], 'shard': d['shard'], 'ptnml': p,
            'games': games if isinstance(games, int) else 2 * sum(p), 'at': iso(d.get('at'))}
