# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure parsers of the formats the Control Center reads: fork_datagen's progress log, the sealed manifests,
the SPRT driver's log (tools/github/sprt_run.sh), the SPRT log (docs/history/phase-4/sprt-log.md),
docs/nets.md, DESIGN.md's Phase 4 checklist (section 5.6) and decisions log, Ordo's table, the training
run records (run.json), the Kaggle CLI's output, gh's JSON, /proc/meminfo and df.

Nothing here touches the disk or runs a command: every function takes text (or parsed JSON) and returns
plain data, so each one is tested on the real formats.
"""
import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone

MINUS = str.maketrans({'−': '-', '–': '-'})  # the docs write minus signs as U+2212
EST = timezone(timedelta(hours=-5), 'EST')


def num(text):
    """A number as the docs write it: U+2212 minus signs and thousands commas allowed."""
    return float(text.translate(MINUS).replace(',', ''))


# ---------------------------------------------------------------- times

def est(epoch):
    """An epoch as the owner reads times: EST (UTC-5), 12-hour AM/PM."""
    if epoch is None:
        return '-'
    return datetime.fromtimestamp(epoch, EST).strftime('%Y-%m-%d %I:%M:%S %p EST')


def iso_epoch(text):
    """jobctl's timestamps (2026-11-06T10:45:12-0500) and gh's (2026-11-06T18:42:36Z) as epochs."""
    if not text:
        return None
    t = text.strip().replace('Z', '+0000')
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f%z'):
        try:
            return datetime.strptime(t, fmt).timestamp()
        except ValueError:
            pass
    return None


def duration(seconds):
    if seconds is None:
        return '-'
    s = int(max(0, seconds))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return (f'{d}d ' if d else '') + f'{h:d}:{m:02d}:{s:02d}'


# ---------------------------------------------------------------- fork_datagen

PROGRESS = re.compile(r'^(\d+) s: (\d+) games, (\d+) positions, (\d+) positions/s$')
DONE = re.compile(r'^done: (\d+) games, (\d+) positions in ([\d.]+) s \((\d+) positions/s\)$')


def datagen_log(text):
    """fork_datagen's stderr: a progress line every 30 s, a "done:" line when the part reaches its target.
    Returns the last progress line, the rate over the last two lines (the log's own rate is the average
    since the start) and the done line if any."""
    progress, done = [], None
    for line in text.splitlines():
        line = line.strip()
        m = PROGRESS.match(line)
        if m:
            progress.append(tuple(int(x) for x in m.groups()))
            continue
        m = DONE.match(line)
        if m:
            done = {'games': int(m[1]), 'positions': int(m[2]), 'seconds': float(m[3]), 'rate': int(m[4])}
    out = {'lines': len(progress), 'done': done, 'last': None, 'recent_rate': None}
    if progress:
        s, g, p, r = progress[-1]
        out['last'] = {'seconds': s, 'games': g, 'positions': p, 'rate': r}
        if len(progress) >= 2:
            s0, _, p0, _ = progress[-2]
            if s > s0:
                out['recent_rate'] = (p - p0) / (s - s0)
    return out


STARTED = re.compile(r'starting at .*\((\d{9,})\)')


def job_log_start(text):
    """The epoch a part's launch script printed just before fork_datagen began ("g3e starting at ... (EPOCH)")."""
    m = None
    for m in STARTED.finditer(text):
        pass
    return int(m[1]) if m else None


DATAGEN_FLAGS = {'--positions': 'positions_target', '--nodes': 'nodes', '--threads': 'threads', '--seed': 'seed',
                 '--hash-mb': 'hash_mb', '--shard-mb': 'shard_mb', '--decided-cp': 'decided_cp',
                 '--max-plies': 'max_plies', '--random-min': 'random_min', '--random-max': 'random_max',
                 '--adjudicate-cp': 'adjudicate_cp', '--adjudicate-plies': 'adjudicate_plies',
                 '--save-percent': 'save_percent', '--unsaved-nodes': 'unsaved_nodes', '--check-nodes': 'check_nodes'}


def datagen_args(argv):
    """fork_datagen's command line (from /proc/PID/cmdline or a launch script) as manifest settings."""
    out, paths = {}, {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in DATAGEN_FLAGS and i + 1 < len(argv):
            try:
                out[DATAGEN_FLAGS[a]] = int(argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif a in ('--openings', '--out', '--run', '--tables') and i + 1 < len(argv):
            paths[a[2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return out, paths


def tables_label(path):
    """The manifests' name for a Syzygy folder named by its piece counts: '~/fork-tools/syzygy/3-4-5' gives
    'syzygy 5-piece' (verify_games.py reads the count back); None for a folder without counts."""
    counts = [int(x) for x in re.findall(r'\d+', str(path).rstrip('/').rsplit('/', 1)[-1])]
    return f'syzygy {max(counts)}-piece' if counts else None


def fork_version(text):
    """`fork version`: {'version': '0.3.0-dev+684bac6', 'commit': '684bac6', 'compiler': 'clang 21.1.8',
    'arch': 'native', 'net': 's512r2', 'evaluator': 'nnue'}."""
    out = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        k, v = parts
        if k == 'Fork':
            out['version'] = v.strip()
            m = re.search(r'\+([0-9a-f]{7,40})', v)
            if m:
                out['commit'] = m[1]
        elif k == 'compiler':
            m = re.match(r'(\S+ [\d.]+)', v)
            out['compiler'] = m[1] if m else v
        elif k in ('arch', 'net', 'evaluator'):
            out[k] = v.strip()
    return out


def bench_expected(text):
    """tests/bench-<net>.ref: the "nodes N" and "signature S" lines."""
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in ('nodes', 'signature'):
            out[parts[0]] = parts[1]
    return out


def default_net(cmakelists):
    m = re.search(r'set\(FORK_NET "\$\{CMAKE_SOURCE_DIR\}/nets/([A-Za-z0-9_]+)\.fnet"', cmakelists)
    return m[1] if m else None


# ---------------------------------------------------------------- parts and manifests

PART = re.compile(r'^g(\d+)([a-z]*)$')


def part_key(name):
    """('g3e') -> (3, 'e'); the first part of a generation has no letter and sorts first. None if the name is
    not a local part (snapshots such as g3s1, cloud runs)."""
    m = PART.match(name)
    if not m:
        return None
    return int(m[1]), (len(m[2]), m[2])


def next_part(name):
    gen, (_, letters) = part_key(name)
    if not letters:
        return f'g{gen}b'
    if letters[-1] == 'z':
        raise ValueError(f'{name}: no letter after z')
    return f'g{gen}{letters[:-1]}{chr(ord(letters[-1]) + 1)}'


def part_dir(name):
    """The part's WSL folder under ~/fork-data: g3e -> gen3e."""
    return 'gen' + name[1:]


def is_part_manifest(m):
    """A sealed local part (not a snapshot, a cut of another part or an openings manifest)."""
    return (isinstance(m, dict) and part_key(str(m.get('run', ''))) is not None and 'settings' in m
            and not str(m.get('part_end', '')).startswith('not a part'))


def net_of(evaluator):
    m = re.match(r'nnue \(([^)]+)\)', evaluator or '')
    return m[1] if m else (evaluator or '?')


def manifest_summary(m):
    """One sealed part, as the Data tab shows it."""
    st = m.get('settings', {})
    shards = [s for batch in m.get('batches', []) for s in batch]
    unsaved = m.get('positions_unsaved')
    gen = m.get('generator', {})
    return {
        'run': m.get('run'), 'generation': (part_key(m['run']) or (None,))[0],
        'games': m.get('games'), 'positions': m.get('positions'),
        'saved': (m['positions'] - unsaved) if unsaved is not None and m.get('positions') is not None else None,
        'net': net_of(gen.get('evaluator')), 'version': gen.get('version'),
        'commit': (re.search(r'\+([0-9a-f]{7,40})', gen.get('version') or '') or [None, None])[1],
        'seed': st.get('seed'), 'threads': st.get('threads'), 'nodes': st.get('nodes'),
        'target': st.get('positions_target'), 'seconds': m.get('seconds'),
        'openings': (m.get('openings') or {}).get('file') or st.get('openings'),
        'split': (f"{st['save_percent']}% / {st.get('unsaved_nodes')} / {st.get('check_nodes')}"
                  if 'save_percent' in st else 'off'),
        'adjudicate': (f"{st.get('adjudicate_cp')} cp x {st.get('adjudicate_plies')}"
                       if st.get('adjudicate_plies') else 'off'),
        'files': [s['file'] for s in shards], 'bytes': sum(s.get('bytes', 0) for s in shards),
        'part_end': m.get('part_end'),
    }


# ---------------------------------------------------------------- jobs

def job_row(record, live_pids, now):
    """A supervisor job record (jobctl.py's jobs/NAME.json) with its live processes."""
    start = iso_epoch(record.get('started'))
    end = iso_epoch(record.get('ended') or record.get('stopped'))
    state = record.get('state', '?')
    if state in ('running', 'starting', 'stopping') and not live_pids:
        state += ' (no process left)'
    elif state not in ('running', 'starting', 'stopping') and live_pids:
        state += ' (processes alive)'
    return {
        'name': record.get('name'), 'type': record.get('type'), 'state': state, 'raw_state': record.get('state'),
        'exit_code': record.get('exit_code'), 'started': start, 'ended': end,
        'elapsed': ((end or now) - start) if start else None, 'processes': list(live_pids),
        'log': record.get('log'), 'id': record.get('id'),
    }


def measure_progress(text):
    """The last informative line of a measurement's log, and an "x of y" count when the line has one."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {'line': '', 'done': None, 'total': None}
    last = lines[-1]
    m = re.search(r'(\d[\d,]*)\s*(?:/|of)\s*(\d[\d,]*)', last)
    done = total = None
    if m:
        done, total = int(num(m[1])), int(num(m[2]))
    else:
        m = re.search(r'(\d[\d,]*) answers saved earlier, (\d[\d,]*) to search', last)
        if m:
            done, total = int(num(m[1])), int(num(m[1])) + int(num(m[2]))
    return {'line': last[:200], 'done': done, 'total': total}


# ---------------------------------------------------------------- SPRT driver log and SPRT log

DRIVER_LINE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC (\S+): (.*)$')
ELO = re.compile(r'Elo: ([-−\d.]+) \+/- ([\d.]+), nElo: ([-−\d.]+) \+/- ([\d.]+)')
LLR = re.compile(r'LLR: ([-−\d.]+) \(([-−\d.]+), ([-−\d.]+)\) \[([-−\d.]+), ([-−\d.]+)\] nElo: (.+)$')
GAMES = re.compile(r'games (\d+)')


def merged_block(lines):
    """fastchess / sprt_merge.py's summary lines -> numbers."""
    out = {}
    for line in lines:
        line = line.strip()
        m = GAMES.search(line) if line.startswith('Shards:') else None
        if m:
            out['games'] = int(m[1])
        m = ELO.search(line)
        if m and line.startswith('Elo:'):
            out.update(elo=num(m[1]), elo_err=num(m[2]), nelo=num(m[3]), nelo_err=num(m[4]))
        m = LLR.search(line)
        if m:
            out.update(llr=num(m[1]), llr_lo=num(m[2]), llr_hi=num(m[3]), elo0=num(m[4]), elo1=num(m[5]),
                       verdict=m[6].strip())
        if line.startswith('Verdict: '):  # sprt_run.sh's kinds (design R): the staged decision
            out['decision'] = line[len('Verdict: '):].strip()
    return out


def driver_log(text):
    """tools/github/sprt_run.sh's driver log: per SPRT its header, each stage's run and merged result, and
    how it finished. Returns {name: {...}} in the order first seen."""
    sprts = {}
    current, block = None, None

    def close():
        nonlocal block
        if block is not None and current is not None:
            st = sprts[current]['stages'].get(block[0])
            if st is not None:
                st.update(merged_block(block[1]))
        block = None

    for raw in text.splitlines():
        if raw.startswith('    ') and block is not None:
            block[1].append(raw)
            continue
        m = DRIVER_LINE.match(raw.strip())
        if not m:
            continue
        close()
        when, name, msg = m[1], m[2].rstrip(':'), m[3]
        current = name
        s = sprts.setdefault(name, {'name': name, 'stages': {}, 'finished': None, 'first_at': when})
        s['last_at'] = when
        h = re.match(r'base (\S+), test (\S+), bounds \[([-−\d.]+), ([-−\d.]+)\], stages (\d+) to (\d+)', msg)
        if h:
            s.update(base=h[1], test=h[2], elo0=num(h[3]), elo1=num(h[4]), first_stage=int(h[5]),
                     last_stage=int(h[6]), finished=None)
            k = re.search(r', kind (\w+), .*?, cap (\d+),', msg)  # the kinds since 2026-11-07 (design R)
            s.update(kind=k[1] if k else None, cap=int(k[2]) if k else None)
            continue
        st = re.match(r'stage (\d+): (?:run (\d+) (dispatched|merged)|waiting for run (\d+))', msg)
        if st:
            n = int(st[1])
            stage = s['stages'].setdefault(n, {'stage': n})
            stage['run'] = int(st[2] or st[4])
            stage['state'] = st[3] or 'waiting'
            if st[3] == 'merged':
                block = (n, [])
            continue
        if msg.startswith(('decided after stage', 'undecided after stage', 'complete after stage')):
            s['finished'] = msg
        elif msg.endswith('stopping'):
            s['finished'] = msg
    close()
    return sprts


def sprt_state(s):
    """The latest merged numbers of one SPRT from driver_log(), with its current stage."""
    merged = [st for st in s['stages'].values() if st.get('state') == 'merged' and 'llr' in st]
    latest = max(merged, key=lambda x: x['stage']) if merged else {}
    current = max(s['stages'].values(), key=lambda x: x['stage']) if s['stages'] else {}
    return {'name': s['name'], 'stage': current.get('stage'), 'stage_state': current.get('state'),
            'run': current.get('run'), 'merged_stage': latest.get('stage'), **{k: latest.get(k) for k in (
                'games', 'elo', 'elo_err', 'nelo', 'nelo_err', 'llr', 'llr_lo', 'llr_hi', 'verdict', 'decision')},
            'kind': s.get('kind'), 'cap': s.get('cap'),
            'elo0': s.get('elo0'), 'elo1': s.get('elo1'), 'finished': s.get('finished'),
            'first_stage': s.get('first_stage'), 'last_stage': s.get('last_stage'), 'base': s.get('base'),
            'test': s.get('test'), 'last_at': s.get('last_at')}


VERDICT = re.compile(r'\*\*(H[01] accepted)|\*\*(undecided[^*]*)\*\*|\b(H[01] accepted)\b')


def sprt_log(md):
    """docs/history/phase-4/sprt-log.md: one entry per "### " section, in the log's order, with its date,
    name, verdict and the last merged result block it shows."""
    entries = []
    sections = re.split(r'^### ', md, flags=re.M)[1:]
    for sec in sections:
        title, _, body = sec.partition('\n')
        m = re.match(r'(\d{4}-\d{2}-\d{2}) (\S+)\s*(?:\((.*)\))?', title.strip())
        if m:
            date, name, desc = m[1], m[2], (m[3] or '')
        else:
            date, name, desc = None, title.split(' (')[0].strip(), title.strip()
        verdict = None
        r = re.search(r'Result: \*\*([^*]+)\*\*', body)
        if r:
            verdict = r[1].strip()
        else:
            v = VERDICT.search(body)
            if v:
                verdict = (v[1] or v[2] or v[3]).strip()
        blocks = re.findall(r'```\n(.*?)```', body, flags=re.S)
        res = merged_block(blocks[-1].splitlines()) if blocks else {}
        if 'elo' not in res:  # a results table instead of a code block: "| -30.04 ± 10.82 | -47.52 ± 17.02 |"
            t = re.findall(r'\| ([-−+]?[\d.]+) ± ([\d.]+) \| ([-−+]?[\d.]+) ± ([\d.]+) \|', body)
            if t:
                res.update(elo=num(t[-1][0]), elo_err=num(t[-1][1]), nelo=num(t[-1][2]), nelo_err=num(t[-1][3]))
        runs = [int(x) for x in re.findall(r'\b(4\d{10})\b', body)]
        res['block_verdict'] = res.pop('verdict', None)
        entries.append({**res, 'date': date, 'name': name.rstrip(':'), 'desc': desc, 'runs': runs,
                        'verdict': verdict or res['block_verdict']})
    return entries


def sprt_gains(entries):
    """Accepted SPRTs (H1) with an Elo, cumulated in log order: [(date, name, elo, cumulative)]. Non-
    regression tests ([-3, 0] bounds) are left out, since their H1 means "no loss", not a gain."""
    out, total = [], 0.0
    for e in entries:
        if e.get('verdict', '') and e['verdict'].startswith('H1') and e.get('elo') is not None and e.get('date'):
            if e.get('elo1') is not None and e['elo1'] <= 0:
                continue
            total += e['elo']
            out.append((e['date'], e['name'], e['elo'], total))
    return out


# ---------------------------------------------------------------- nets.md

def nets_md(md):
    """docs/nets.md: each "## " network section's table (Item -> Value), which one is the default, and the
    bake-off entries table."""
    nets = []
    for sec in re.split(r'^## ', md, flags=re.M)[1:]:
        title, _, body = sec.partition('\n')
        items = {}
        for row in re.findall(r'^\| ([^|]+?) \| (.+) \|\s*$', body, flags=re.M):
            k, v = row[0].strip(), row[1].strip()
            if k in ('Item', '---') or set(k) <= set('-'):
                continue
            items[k] = v
        name = re.split(r'[,(]', title)[0].strip()
        date = (re.search(r'\((\d{4}-\d{2}-\d{2})\)', title) or [None, None])[1]
        status = items.get('Status', '')
        nets.append({'title': title.strip(), 'name': name, 'date': date, 'items': items,
                     'default': bool(re.search(r'default network since', status, re.I)),
                     'status': status, 'bench': items.get('Bench', ''), 'sprt': items.get('SPRT', '')})
    entries = []
    for row in re.findall(r'^\| ([^|]+) \| `([^`]+)` \| (\d+) \| ([^|]+) \|\s*$', md, flags=re.M):
        entries.append({'entry': row[0].strip(), 'net': row[1], 'arch_id': int(row[2]), 'bench': row[3].strip()})
    sections = [n for n in nets if n['items']]
    return {'nets': sections, 'default': next((n for n in sections if n['default']), None), 'entries': entries}


# ---------------------------------------------------------------- DESIGN.md

def section(md, heading_prefix):
    """The text of the DESIGN.md section whose heading starts with heading_prefix, up to the next heading of
    the same or a higher level."""
    m = re.search(r'^(#+) ' + re.escape(heading_prefix) + r'.*$', md, flags=re.M)
    if not m:
        return ''
    level = len(m[1])
    rest = md[m.end():]
    n = re.search(r'^#{1,%d} ' % level, rest, flags=re.M)
    return md[m.start():m.end() + (n.start() if n else len(rest))]


STATUS_WORDS = [  # first match wins; the checklist's own words
    ('done', r'\*\*done\*\*|\bdone\b|\bconfirmed\b|none outstanding'),
    ('running', r'\brunning\b|\btraining on kaggle\b|\bin progress\b|\bin flight\b'),
    ('held', r'\bheld\b|\bdeferred\b|\bgated\b|\bshelved\b|stays off'),
    ('next', r'\bnext in the queue\b|\bin the next snapshot\b|\bready\b'),
    ('planned', r'\bnot started\b|\bplanned\b|\bowed\b|\bdesigned\b|\bat the end\b|\bnot yet run\b|\bafter\b'),
]


def classify(status):
    s = status.lower()
    for tag, pat in STATUS_WORDS:
        if re.search(pat, s):
            return tag
    return 'open'


def plain(md_text):
    return re.sub(r'\*\*|`', '', md_text).strip()


def checklist(design_md):
    """Section 5.6, the Phase 4 checklist: its item tables grouped by their bold headings (Network, Search,
    Speed, Final steps), and the order table."""
    sec = section(design_md, '5.6 ')
    groups, order = [], []
    group = None
    for line in sec.splitlines():
        g = re.match(r'^\*\*([A-Z][A-Za-z ]+)\*\*\s*$', line.strip())
        if g:
            group = {'group': g[1], 'items': []}
            groups.append(group)
            continue
        if not line.startswith('|') or set(line.replace('|', '').strip()) <= set('-'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if cells[0] in ('item', '#'):
            continue
        # The order table: "# | item | why here | estimate" (to 2026-11-06), or since the order of 2026-11-07
        # "# | step | lane | when / depends on | estimate" (a "done" row first, which is not numbered).
        if len(cells) in (4, 5) and cells[0].isdigit():
            lane, why = ('', cells[2]) if len(cells) == 4 else (cells[2], cells[3])
            order.append({'n': int(cells[0]), 'item': plain(cells[1]), 'why': plain(why), 'lane': plain(lane),
                          'estimate': plain(cells[-1]), 'status': classify(cells[1])})
        elif len(cells) == 2 and group is not None:
            group['items'].append({'item': plain(cells[0]), 'status_text': plain(cells[1]),
                                   'status': classify(cells[1])})
    title = sec.splitlines()[0].lstrip('# ').strip() if sec else ''
    return {'title': title, 'groups': [g for g in groups if g['items']], 'order': order}


GAUNTLET = re.compile(r'Fork (\d{4}\.\d) ± (\d+\.\d)')


def decision_gauntlets(design_md):
    """The decisions log's gauntlet results: [(date, rating, error, text)] for each row whose bold title
    names a gauntlet; the first rating in the row is the run's own."""
    out = []
    for line in section(design_md, '6. Decisions log').splitlines():
        m = re.match(r'^\| (\d{4}-\d{2}-\d{2}) \| \*\*([^*]*)\*\*(.*)\|\s*$', line)
        if not m or 'gauntlet' not in (m[2] + m[3]).lower():
            continue
        g = GAUNTLET.search(m[2]) or GAUNTLET.search(m[3])
        if g:
            run = re.search(r'Run (\d{9,})', m[3])
            out.append({'date': m[1], 'rating': float(g[1]), 'error': float(g[2]), 'title': plain(m[2]),
                        'run': int(run[1]) if run else None})
    return out


def ordo(text, player='Fork'):
    """Ordo's rating table: the player's row."""
    for line in text.splitlines():
        m = re.match(r'^\s*\d+ (.+?)\s+:\s+([\d.]+)\s+([\d.-]+)\s+([\d.]+)\s+(\d+)\s+(\d+)', line)
        if m and m[1].strip() == player:
            return {'rating': float(m[2]), 'error': None if set(m[3]) <= set('-') else float(m[3]),
                    'points': float(m[4]), 'games': int(m[5]), 'percent': int(m[6])}
    return None


# ---------------------------------------------------------------- training, Kaggle, GitHub

def training_run(rec):
    """A training seed's run.json: its best validation loss and where it fell."""
    curve = rec.get('val_curve') or []
    best = min(curve, key=lambda x: x[1]) if curve else None
    return {'arch': rec.get('arch'), 'seed': rec.get('seed'), 'rc': rec.get('rc'), 'seconds': rec.get('seconds'),
            'superbatches': rec.get('superbatches'), 'best_loss': best[1] if best else None,
            'best_at': best[0] if best else None, 'last_at': curve[-1][0] if curve else None,
            'commit': (rec.get('commit') or '')[:7], 'manifests': rec.get('manifests', []),
            'warm': bool(rec.get('init_weights'))}


def kaggle_list(text):
    """`kaggle kernels list --mine --csv`."""
    rows = list(csv.DictReader(io.StringIO(text.strip()))) if text.strip().startswith('ref') else []
    return [{'ref': r.get('ref'), 'title': r.get('title'), 'last_run': r.get('lastRunTime')} for r in rows]


def kaggle_status(text):
    """`kaggle kernels status REF`: 'owner/x has status "KernelWorkerStatus.COMPLETE"' -> 'complete'."""
    m = re.search(r'has status "(?:KernelWorkerStatus\.)?([A-Za-z_]+)"', text)
    return m[1].lower() if m else None


def kaggle_datasets(text):
    rows = list(csv.DictReader(io.StringIO(text.strip()))) if text.strip().startswith('ref') else []
    return [r.get('ref') for r in rows]


def gh_runs(text):
    try:
        runs = json.loads(text)
    except ValueError:
        return []
    out = []
    for r in runs:
        out.append({'id': r.get('databaseId'), 'title': r.get('displayTitle'), 'workflow': r.get('workflowName'),
                    'branch': r.get('headBranch'), 'status': r.get('status'), 'conclusion': r.get('conclusion') or '',
                    'created': iso_epoch(r.get('createdAt')), 'url': r.get('url')})
    return out


# ---------------------------------------------------------------- machine

def meminfo(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r'^(\w+):\s+(\d+) kB', line)
        if m:
            out[m[1]] = int(m[2]) * 1024
    return out


def df(text):
    """`df -B1 -P PATH`: (total, free) in bytes."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    f = lines[-1].split()
    try:
        return {'total': int(f[1]), 'free': int(f[3])}
    except (IndexError, ValueError):
        return None
