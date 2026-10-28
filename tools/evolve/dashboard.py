"""The heuristic-discovery run's live dashboard (ideas.md idea 23,
deliverable 8c): one self-contained HTML page in the run folder, rewritten
after every candidate and refreshing itself in the browser every 60
seconds, so it can stay open during a run. With `mirror`, a copy is also
written there (e.g. a Windows folder, which browsers open more reliably
than a page on the WSL share). It shows the run's state and budget, the
islands and their grid cells, the top candidates, critic rejections with
reasons, gate failures, analyst summaries and promotions. Everything an
agent wrote is escaped: it is model output, shown as text.

    python3 tools/evolve/dashboard.py RUN_DIR      (also called by the orchestrator)
"""
import html
import json
import sqlite3
import sys
import time
from pathlib import Path

REFRESH_SECONDS = 60

STYLE = """
:root { --bg: #fbfbfa; --fg: #1d1d1b; --muted: #6b6b66; --line: #deded9; --card: #ffffff;
        --good: #1f7a4d; --bad: #b3261e; --warn: #9a6700; --accent: #2457a6; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #161615; --fg: #ececea; --muted: #a3a39d; --line: #33332f; --card: #1f1f1d;
          --good: #5cc290; --bad: #f2867c; --warn: #e3b341; --accent: #7aa7f0; } }
* { box-sizing: border-box; }
body { margin: 0; padding: 16px; background: var(--bg); color: var(--fg);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
h1 { font-size: 20px; margin: 0 0 4px; } h2 { font-size: 16px; margin: 24px 0 8px; }
.muted { color: var(--muted); } .good { color: var(--good); } .bad { color: var(--bad); } .warn { color: var(--warn); }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 10px; }
.card b { display: block; font-size: 18px; font-variant-numeric: tabular-nums; }
.bar { height: 6px; background: var(--line); border-radius: 3px; margin-top: 6px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent); }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; background: var(--card); }
th, td { border-bottom: 1px solid var(--line); padding: 6px 8px; text-align: left; vertical-align: top; }
th { color: var(--muted); font-weight: 600; white-space: nowrap; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
pre { margin: 4px 0 0; white-space: pre-wrap; font: 12px/1.4 ui-monospace, Consolas, monospace; }
details summary { cursor: pointer; color: var(--accent); }
"""


def esc(x):
    return html.escape('' if x is None else str(x))


def _rows(db, sql, args=()):
    cur = db.execute(sql, args)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _json(text):
    try:
        return json.loads(text) if text else {}
    except (TypeError, ValueError):
        return {}


def render(run_dir, mirror=None):
    """Writes RUN_DIR/dashboard.html (and MIRROR/dashboard.html) from the run's
    database and state file."""
    run = Path(run_dir)
    db = sqlite3.connect(str(run / 'population.sqlite'))
    try:
        state = run / 'state.json'
        page = _page(db, _json(state.read_text(encoding='utf-8')) if state.exists() else {})
    finally:
        db.close()
    tmp = run / 'dashboard.html.tmp'
    tmp.write_text(page, encoding='utf-8')
    tmp.replace(run / 'dashboard.html')
    if mirror:
        out = Path(mirror).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        (out / 'dashboard.html.tmp').write_text(page, encoding='utf-8')
        (out / 'dashboard.html.tmp').replace(out / 'dashboard.html')
    return run / 'dashboard.html'


def _page(db, state):
    cands = _rows(db, 'SELECT * FROM candidates ORDER BY id')
    events = _rows(db, 'SELECT generation, kind, detail, created FROM events ORDER BY id')
    elites = _rows(db, 'SELECT island, cell, candidate, fitness FROM elites ORDER BY island, fitness DESC')
    by_id = {c['id']: c for c in cands}
    base = next((c for c in cands if c['island'] == 'baseline'), None)
    base_fit = base['fitness'] if base and base['fitness'] is not None else None
    parts = [f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
             f'<meta name="viewport" content="width=device-width, initial-scale=1">'
             f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}"><title>Fork heuristic discovery</title>'
             f'<style>{STYLE}</style></head><body>']
    parts.append(f'<h1>Fork heuristic discovery: {esc(state.get("region", "lmr"))}</h1>'
                 f'<div class="muted">Run {esc(state.get("run", ""))} · {esc(state.get("status", "running"))} · '
                 f'updated {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())} · refreshes every '
                 f'{REFRESH_SECONDS} s</div>')
    parts.append(_cards(state, cands, base_fit))
    parts.append(_islands(elites, by_id, state, base_fit))
    parts.append(_top(cands, base_fit))
    parts.append(_promotions(events))
    parts.append(_rejections(events, by_id))
    parts.append(_gate_failures(events, by_id))
    parts.append(_analyst(events))
    parts.append('</body></html>')
    return '\n'.join(parts)


def _cards(state, cands, base_fit):
    used, limits = state.get('budget_used', {}), state.get('budget_limits', {})

    def card(label, value, frac=None, cls=''):
        bar = f'<div class="bar"><i style="width:{min(100, max(0, frac * 100)):.0f}%"></i></div>' if frac is not None else ''
        return f'<div class="card"><span class="muted">{esc(label)}</span><b class="{cls}">{value}</b>{bar}</div>'

    tokens, tlim = used.get('tokens', 0), limits.get('tokens') or 1
    ncand, clim = used.get('candidates', 0), limits.get('candidates') or 1
    secs, slim = state.get('elapsed_seconds', 0), limits.get('seconds') or 1
    scored = [c for c in cands if c['fitness'] is not None and c['island'] != 'baseline']
    best = max((c['fitness'] for c in scored), default=None)
    gain = '' if best is None or base_fit is None else f'{best - base_fit:+.4f}'
    return '<div class="cards">' + ''.join([
        card('Generation', f'{esc(state.get("generation", 0))} / {esc(state.get("generations", "?"))}'),
        card('Tokens', f'{tokens:,} / {tlim:,}', tokens / tlim),
        card('Candidates', f'{ncand} / {clim}', ncand / clim),
        card('Wall time', f'{secs / 3600:.1f} h / {slim / 3600:.0f} h', secs / slim),
        card('Baseline fitness', '—' if base_fit is None else f'{base_fit:.4f}'),
        card('Best vs baseline', gain or '—', None, 'good' if gain.startswith('+') and gain != '+0.0000' else ''),
    ]) + '</div>'


def _islands(elites, by_id, state, base_fit):
    out = ['<h2>Islands</h2><div class="scroll"><table><tr><th>Island</th><th>Cells</th><th>Best</th>'
           '<th>Fitness</th><th>vs baseline</th><th>Cells (mean reduction : re-search)</th></tr>']
    islands = {}
    for e in elites:
        islands.setdefault(e['island'], []).append(e)
    for name in state.get('islands', sorted(islands)):
        cells = islands.get(name, [])
        best = cells[0] if cells else None
        protected = ' <span class="warn">(protected)</span>' if name == 'explorer' and \
            state.get('generation', 0) < state.get('explorer_protected', 0) else ''
        delta = '' if not best or base_fit is None else f'{best["fitness"] - base_fit:+.4f}'
        best_id = '#' + esc(best['candidate']) if best else '—'
        best_fit = f'{best["fitness"]:.4f}' if best else ''
        cell_list = ', '.join(f'{esc(c["cell"])}={c["fitness"]:.4f} (#{c["candidate"]})' for c in cells[:8])
        out.append(f'<tr><td>{esc(name)}{protected}</td><td class="num">{len(cells)}</td>'
                   f'<td class="num">{best_id}</td><td class="num">{best_fit}</td>'
                   f'<td class="num">{delta}</td><td class="muted">{cell_list}</td></tr>')
    out.append('</table></div>')
    return ''.join(out)


def _top(cands, base_fit, limit=15):
    scored = sorted((c for c in cands if c['fitness'] is not None), key=lambda c: -c['fitness'])[:limit]
    out = [f'<h2>Top candidates</h2><div class="scroll"><table><tr><th>#</th><th>Gen</th><th>Island</th>'
           f'<th>Mode</th><th>Fitness</th><th>Gain (95% interval)</th><th>Held-out fitness</th>'
           f'<th>Held-out gain (95% interval)</th><th>Trigger</th><th>Agreement</th>'
           f'<th>Score error</th><th>Depth</th><th>Descriptors</th><th>Status</th><th>Rationale and code</th></tr>']
    for c in scored:
        p = _json(c['proxies'])
        desc = _json(c['descriptors'])
        desc_txt = ', '.join(f'{d:.3f}' for d in desc[:2]) if isinstance(desc, list) else ''
        gain = (f'{p["gain"]:+.4f} [{p["gain_low"]:+.4f}, {p["gain_high"]:+.4f}]' if 'gain_low' in p else '')
        held = f'{p["holdout_fitness"]:.4f}' if 'holdout_fitness' in p else ''
        held_gain = (f'{p["holdout_gain"]:+.4f} [{p["holdout_low"]:+.4f}, {p["holdout_high"]:+.4f}]'
                     if 'holdout_low' in p else '')
        trigger = f'{100 * desc[2]:.2f}%' if isinstance(desc, list) and len(desc) > 2 else ''
        cls = '' if base_fit is None else ('good' if c['fitness'] > base_fit else 'bad' if c['fitness'] < base_fit else '')
        out.append(f'<tr><td class="num">{c["id"]}</td><td class="num">{c["generation"]}</td><td>{esc(c["island"])}</td>'
                   f'<td>{esc(c["mode"])}</td><td class="num {cls}">{c["fitness"]:.4f}</td>'
                   f'<td class="num">{gain}</td><td class="num">{held}</td><td class="num">{held_gain}</td>'
                   f'<td class="num">{trigger}</td>'
                   f'<td class="num">{p.get("agreement", 0):.3f}</td><td class="num">{p.get("score_error", 0):.1f}</td>'
                   f'<td class="num">{p.get("depth", 0):.2f}</td><td class="num">{desc_txt}</td><td>{esc(c["status"])}</td>'
                   f'<td>{esc((c["rationale"] or "")[:300])}<details><summary>code</summary><pre>{esc(c["body"])}</pre>'
                   f'</details></td></tr>')
    out.append('</table></div>')
    return ''.join(out)


def _event_rows(events, kinds):
    return [(e, _json(e['detail']) if e['detail'] and e['detail'][:1] in '{[' else {'text': e['detail']})
            for e in events if e['kind'] in kinds]


def _promotions(events):
    rows = _event_rows(events, ('promoted', 'handoff', 'match_failed'))
    out = ['<h2>Promotions</h2>']
    if not rows:
        return out[0] + '<p class="muted">None yet: a candidate is promoted when its proxy fitness beats the baseline by the configured margin.</p>'
    out.append('<div class="scroll"><table><tr><th>Gen</th><th>#</th><th>Stage</th><th>Detail</th></tr>')
    for e, d in rows:
        stage = {'promoted': 'promoted (match skipped)' if d.get('match') else 'promoted',
                 'handoff': 'SPRT hand-off', 'match_failed': 'short match: not kept'}[e['kind']]
        detail = d.get('commands') or d.get('result') or d.get('match') or ''
        out.append(f'<tr><td class="num">{e["generation"]}</td><td class="num">{esc(d.get("id"))}</td>'
                   f'<td>{esc(stage)}</td><td><pre>{esc(json.dumps(detail) if not isinstance(detail, str) else detail)}</pre></td></tr>')
    out.append('</table></div>')
    return ''.join(out)


def _rejections(events, by_id):
    rows = _event_rows(events, ('critic_rejected',))
    out = [f'<h2>Critic rejections ({len(rows)})</h2>']
    if not rows:
        return out[0] + '<p class="muted">None yet.</p>'
    out.append('<div class="scroll"><table><tr><th>Gen</th><th>#</th><th>Island</th><th>Reasons</th>'
               '<th>Audited by the gate</th></tr>')
    for e, d in rows:
        c = by_id.get(d.get('id'), {})
        audit = esc(c.get('status', '')) if d.get('audited') else 'no'
        out.append(f'<tr><td class="num">{e["generation"]}</td><td class="num">{esc(d.get("id"))}</td>'
                   f'<td>{esc(c.get("island", ""))}</td><td>{esc(d.get("reasons"))}</td><td>{audit}</td></tr>')
    out.append('</table></div>')
    return ''.join(out)


def _gate_failures(events, by_id):
    rows = _event_rows(events, ('gate_failed', 'malformed'))
    out = [f'<h2>Gate failures and malformed replies ({len(rows)})</h2>']
    if not rows:
        return out[0] + '<p class="muted">None yet.</p>'
    out.append('<div class="scroll"><table><tr><th>Gen</th><th>#</th><th>Step</th><th>Detail</th></tr>')
    for e, d in rows:
        step = d.get('step', 'malformed reply' if e['kind'] == 'malformed' else '')
        detail = d.get('detail') or d.get('reply') or ''
        out.append(f'<tr><td class="num">{e["generation"]}</td><td class="num">{esc(d.get("id", ""))}</td>'
                   f'<td>{esc(step)}</td><td><details><summary>{esc(detail[:120])}</summary><pre>{esc(detail)}</pre>'
                   f'</details></td></tr>')
    out.append('</table></div>')
    return ''.join(out)


def _analyst(events):
    rows = _event_rows(events, ('analyst',))
    out = ['<h2>Analyst summaries</h2>']
    if not rows:
        return out[0] + '<p class="muted">None yet: the analyst writes every few generations.</p>'
    for e, d in reversed(rows):
        out.append(f'<div class="card"><span class="muted">After generation {e["generation"]}</span>'
                   f'<pre>{esc(d.get("insights", ""))}</pre></div>')
    return ''.join(out)


if __name__ == '__main__':
    print(render(sys.argv[1]))
