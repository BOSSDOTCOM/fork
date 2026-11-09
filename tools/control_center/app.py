# SPDX-License-Identifier: GPL-3.0-or-later
"""Fork Control Center: one window over Fork's long-running work (tkinter, no other dependencies).

Everything is read-only except the Data generation tab's controls (generation_control.py). The read-only tabs are
built without the controller or the runner: they only receive snapshots to show, and a function that
opens a link in the browser. A background thread polls every poll_seconds (GitHub and Kaggle less often)
and hands each snapshot to the window; notifications compare successive snapshots (notify.py).

    pythonw -I tools/control_center/app.py      (the desktop shortcut runs this)
"""
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collectors  # noqa: E402
import config  # noqa: E402
import generation_control  # noqa: E402
import notify  # noqa: E402
import parsers as P  # noqa: E402
import winutil  # noqa: E402
from runner import ReadOnly, Runner  # noqa: E402

TITLE = 'Fork Control Center'
COLORS = {'done': '#2e7d32', 'running': '#1565c0', 'next': '#6a1b9a', 'held': '#b26a00', 'planned': '#555555',
          'open': '#333333', 'bad': '#c62828', 'good': '#2e7d32', 'warn': '#b26a00'}


def n(x, fmt='{:,}'):
    return '-' if x is None else fmt.format(x)


def gbytes(x):
    return '-' if x is None else f'{x / 1e9:,.1f} GB'


class Table(ttk.Frame):
    """A Treeview with columns, a scrollbar and set_rows()."""

    def __init__(self, parent, columns, widths=None, height=8, tree=False):
        super().__init__(parent)
        show = 'tree headings' if tree else 'headings'
        self.tv = ttk.Treeview(self, columns=columns, show=show, height=height)
        for i, c in enumerate(columns):
            self.tv.heading(c, text=c)
            self.tv.column(c, width=(widths or {}).get(c, 110), anchor='w', stretch=True)
        if tree:
            self.tv.column('#0', width=(widths or {}).get('#0', 160))
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        for tag, color in COLORS.items():
            self.tv.tag_configure(tag, foreground=color)
        self.payload = {}

    def set_rows(self, rows):
        """rows: [(values, tag, payload)]"""
        self.tv.delete(*self.tv.get_children())
        self.payload = {}
        for values, tag, payload in rows:
            iid = self.tv.insert('', 'end', values=[str(v) for v in values], tags=(tag,) if tag else ())
            self.payload[iid] = payload

    def set_tree(self, groups):
        """groups: [(label, values, tag, [(label, values, tag, payload)])]"""
        self.tv.delete(*self.tv.get_children())
        self.payload = {}
        for label, values, tag, children in groups:
            g = self.tv.insert('', 'end', text=label, values=[str(v) for v in values], open=True,
                               tags=(tag,) if tag else ())
            for clabel, cvalues, ctag, payload in children:
                iid = self.tv.insert(g, 'end', text=clabel, values=[str(v) for v in cvalues],
                                     tags=(ctag,) if ctag else ())
                self.payload[iid] = payload


class Fields(ttk.Frame):
    """Label: value pairs in a grid."""

    def __init__(self, parent, names, cols=2):
        super().__init__(parent)
        self.vars = {}
        for i, name in enumerate(names):
            r, c = divmod(i, cols)
            ttk.Label(self, text=name + ':', font=('Segoe UI', 9, 'bold')).grid(row=r, column=2 * c, sticky='w',
                                                                              padx=(8, 4), pady=2)
            v = tk.StringVar(value='-')
            ttk.Label(self, textvariable=v).grid(row=r, column=2 * c + 1, sticky='w', padx=(0, 18), pady=2)
            self.vars[name] = v

    def set(self, **values):
        for k, v in values.items():
            self.vars[k.replace('_', ' ')].set('-' if v is None else str(v))


# ================================================================ the one tab with controls

class DatagenTab(ttk.Frame):
    FIELDS = ['Part', 'Phase', 'Started', 'Elapsed', 'Games', 'Positions', 'Positions/s', 'Target', 'Seed',
              'Threads', 'Engine', 'Auto-stop', 'Keep awake', 'Seal']

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        top = ttk.LabelFrame(self, text='Current part')
        top.pack(fill='x', padx=8, pady=6)
        self.fields = Fields(top, self.FIELDS)
        self.fields.pack(fill='x', pady=4)
        bar = ttk.Frame(self)
        bar.pack(fill='x', padx=8, pady=4)
        self.start_btn = ttk.Button(bar, text='Start generating', command=self.on_start)
        self.start_btn.pack(side='left')
        ttk.Label(bar, text='threads').pack(side='left', padx=(10, 2))
        self.threads = tk.StringVar(value=str(app.cfg['threads']))
        ttk.Spinbox(bar, from_=1, to=12, width=4, textvariable=self.threads).pack(side='left')
        self.stop_btn = ttk.Button(bar, text='Stop & seal', command=self.on_stop)
        self.stop_btn.pack(side='left', padx=(18, 0))
        ttk.Label(bar, text='auto-stop after').pack(side='left', padx=(24, 2))
        self.hours = tk.StringVar(value='')
        ttk.Entry(bar, width=6, textvariable=self.hours).pack(side='left')
        ttk.Label(bar, text='hours').pack(side='left', padx=(2, 4))
        ttk.Button(bar, text='Set', command=self.on_set_auto).pack(side='left')
        ttk.Button(bar, text='Clear', command=self.on_clear_auto).pack(side='left', padx=4)
        info = ttk.LabelFrame(self, text='Activity')
        info.pack(fill='both', expand=True, padx=8, pady=6)
        self.log = tk.Text(info, height=14, wrap='word', state='disabled', font=('Consolas', 9))
        self.log.pack(fill='both', expand=True)
        self.current = None
        self.busy = False

    def say(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', f"{time.strftime('%I:%M:%S %p')}  {text}\n")
        self.log.see('end')
        self.log.configure(state='disabled')

    def render(self, snap):
        run = snap.get('datagen')
        wd = snap.get('watchdog')
        self.current = run
        live = bool(run and run['live'])
        if run:
            pct = f" ({100 * run['progress']:.2f}% of the target)" if run.get('progress') is not None else ''
            rate = f"{n(run['rate'])} average, {n(run['recent_rate'], '{:,.0f}')} over the last 30 s"
            auto = run.get('autostop')
            seal = run.get('seal') or {}
            res = (seal.get('result') or {})
            self.fields.set(Part=run['name'], Phase=run['phase'] + ('' if live else ' (not running)'),
                            Started=P.est(run['started']), Elapsed=P.duration(run['elapsed']),
                            Games=n(run['games']), Positions=n(run['positions']) + pct, **{'Positions/s': rate},
                            Target=n(run['target']), Seed=run['seed'], Threads=run['threads'],
                            Engine=(run.get('engine') or '-').strip(),
                            **{'Auto-stop': (f"after {auto['hours']:g} h, at {P.est(auto['deadline'])}"
                                             if auto else 'off'),
                               'Keep awake': (f"{'yes' if wd.get('sleep_blocked') else 'REQUEST FAILED'} "
                                              f"(watchdog pid {wd['pid']}, part {wd['part']})"
                                              if wd and wd.get('alive') else 'no'),
                               'Seal': (f"{res.get('state')}: {res.get('message', '')[:140]}" if res else
                                        (seal.get('job_state') or '-'))})
        else:
            self.fields.set(Part='none', Phase='-')
        if not self.busy:
            self.start_btn.state(['disabled'] if live or snap.get('probe_error') else ['!disabled'])
            self.stop_btn.state(['!disabled'] if live else ['disabled'])

    def background(self, work, done):
        self.busy = True
        self.start_btn.state(['disabled'])
        self.stop_btn.state(['disabled'])

        def go():
            try:
                result = work()
                self.app.ui(lambda: done(result, None))
            except Exception as e:  # noqa: BLE001
                self.app.ui(lambda: done(None, e))
        threading.Thread(target=go, daemon=True).start()

    def finish(self):
        self.busy = False
        self.app.poke()

    def on_start(self):
        threads = self.threads.get().strip()
        self.say('planning the next part ...')

        def planned(result, err):
            if err:
                self.say(f'start refused: {err}')
                self.finish()
                return
            plan, probe, why = result
            if why:
                self.say('start refused: ' + '; '.join(why))
                messagebox.showwarning(TITLE, 'Start refused:\n\n' + '\n'.join(why))
                self.finish()
                return
            st = plan['settings']
            how = ('a PGO build of that commit' if plan['mode'] == 'build' else
                   f"the binary of {plan['previous']} (no engine file changed since {plan['engine_commit'][:10]})")
            text = (f"Start part {plan['name']} of generation {plan['generation']}?\n\n"
                    f"Engine: {plan['branch']} at {plan['commit'][:10]}, network {plan['net']}\n"
                    f"  {how}, bench must be {plan['bench_nodes']} / {plan['bench_signature']}\n"
                    f"Seed {st['seed']}, target {st['positions_target']:,} positions "
                    f"(the rest after {plan['previous']}), {st['threads']} threads\n"
                    f"{st['nodes']:,} nodes, adjudication {st['adjudicate_cp']} cp x {st['adjudicate_plies']}, "
                    f"split search {st['save_percent']}% / {st['unsaved_nodes']} / {st['check_nodes']}\n"
                    f"Openings {plan['openings']}; folder {plan['dir']}\n"
                    + (f"\nDiffers from {plan['previous']}: {plan['differs_from_previous']}\n"
                       if plan['differs_from_previous'] else ''))
            if not messagebox.askyesno(TITLE, text):
                self.say('start cancelled')
                self.finish()
                return
            hours = self.hours.get().strip() or None
            self.background(lambda: self.app.ctl.start(plan, probe, auto_stop_hours=hours), started)

        def started(result, err):
            self.say(f'start failed: {err}' if err else f'started: {result}')
            if err:
                messagebox.showerror(TITLE, str(err))
            self.finish()

        def work():
            plan, probe = self.app.ctl.plan(threads=int(threads) if threads.isdigit() else None)
            return plan, probe, self.app.ctl.preflight(plan, probe)
        self.background(work, planned)

    def on_stop(self):
        run = self.current
        if not run or not run['live']:
            return
        reason = simpledialog.askstring(
            TITLE, f"Stop {run['name']} and seal it?\n\nWhy does the part end? (recorded as part_end in the "
                   f"manifest)", initialvalue='stopped from the Control Center', parent=self)
        if not reason:
            self.say('stop cancelled')
            return
        self.say(f"stopping {run['name']} ...")

        def done(result, err):
            self.say(f'stop & seal: {err}' if err else result)
            if err:
                messagebox.showerror(TITLE, str(err))
            self.finish()
        self.background(lambda: self.app.ctl.stop_and_seal(run['name'], reason), done)

    def on_set_auto(self):
        run = self.current
        if not run or not run['live']:
            self.say('auto-stop: no part is running (the hours given here also apply to the next start)')
            return
        try:
            d = self.app.ctl.set_auto_stop(run['name'], self.hours.get().strip())
            self.app.ctl.ensure_watchdog(run['name'])
            self.say(f"auto-stop: {run['name']} stops and seals at {P.est(d['deadline'])}")
        except (generation_control.Refused, ValueError) as e:
            self.say(f'auto-stop: {e}')
        self.app.poke()

    def on_clear_auto(self):
        if self.current:
            self.app.ctl.set_auto_stop(self.current['name'], None)
            self.say(f"auto-stop cleared for {self.current['name']}")
        self.app.poke()


# ================================================================ read-only tabs (no controller, no runner)

class JobsTab(ttk.Frame):
    def __init__(self, parent, open_url):
        super().__init__(parent)
        cols = ('supervisor', 'name', 'type', 'state', 'started', 'elapsed', 'processes', 'progress')
        self.table = Table(self, cols, {'state': 170, 'started': 200, 'processes': 160, 'progress': 330}, height=14)
        self.table.pack(fill='both', expand=True, padx=8, pady=6)
        ttk.Label(self, text='Locks', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=8)
        self.locks = Table(self, ('supervisor', 'type', 'held by', 'since'), {'since': 220}, height=5)
        self.locks.pack(fill='x', padx=8, pady=(0, 8))

    def render(self, snap):
        rows = []
        for j in snap.get('jobs', []):
            prog = j.get('progress') or {}
            p = prog.get('line', '')
            if prog.get('total'):
                p = f"{prog['done']:,} of {prog['total']:,}  {p}"
            tag = 'running' if j['processes'] else ('bad' if 'no process' in j['state'] or (
                j.get('exit_code') not in (0, None)) else '')
            rows.append(((j['supervisor'], j['name'], j['type'], j['state'] + (
                f" (exit {j['exit_code']})" if j.get('exit_code') is not None else ''), P.est(j['started']),
                P.duration(j['elapsed']), ' '.join(map(str, j['processes'][:6])) or '-', p), tag, j))
        self.table.set_rows(rows)
        self.locks.set_rows([((lk['supervisor'], lk['type'], lk.get('name'),
                               P.est(P.iso_epoch(lk.get('started')))), '', lk) for lk in snap.get('locks', [])])


class TestingTab(ttk.Frame):
    def __init__(self, parent, open_url):
        super().__init__(parent)
        self.open_url = open_url
        cur = ttk.LabelFrame(self, text='Current SPRT')
        cur.pack(fill='x', padx=8, pady=6)
        self.fields = Fields(cur, ['Name', 'Job', 'Stage', 'Games', 'Elo', 'nElo', 'LLR', 'Bounds', 'Verdict',
                                   'Run'], cols=3)
        self.fields.pack(fill='x')
        self.llr = tk.Canvas(cur, height=34, bg='white', highlightthickness=0)
        self.llr.pack(fill='x', padx=8, pady=4)
        mid = ttk.Frame(self)
        mid.pack(fill='both', expand=True, padx=8)
        left = ttk.Frame(mid)
        left.pack(side='left', fill='both', expand=True)
        ttk.Label(left, text='Queue: waiting jobs, then the section 5.6 order', font=('Segoe UI', 9, 'bold')).pack(
            anchor='w')
        self.queue = Table(left, ('#', 'item'), {'#': 40, 'item': 520}, height=6)
        self.queue.pack(fill='both', expand=True)
        ttk.Label(left, text='Recent results (SPRT log)', font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        self.results = Table(left, ('date', 'name', 'verdict', 'Elo', 'LLR'), {'name': 230, 'verdict': 200},
                             height=8)
        self.results.pack(fill='both', expand=True)
        ttk.Label(left, text='SPRTs in the driver logs (latest first)', font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        self.drivers = Table(left, ('last line (UTC)', 'name', 'job', 'stage', 'games', 'Elo', 'LLR', 'state'),
                             {'name': 200, 'last line (UTC)': 120, 'stage': 50, 'state': 170}, height=5)
        self.drivers.pack(fill='both', expand=True)
        right = ttk.Frame(mid)
        right.pack(side='left', fill='both', expand=True, padx=(8, 0))
        ttk.Label(right, text='GitHub runs (double-click opens the run)', font=('Segoe UI', 9, 'bold')).pack(
            anchor='w')
        self.runs = Table(right, ('workflow', 'branch', 'status', 'created', 'title'),
                          {'workflow': 70, 'created': 170, 'title': 300}, height=9)
        self.runs.pack(fill='both', expand=True)
        ttk.Label(right, text='CI', font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        self.ci = Table(right, ('branch', 'status', 'created', 'title'), {'created': 170, 'title': 250}, height=5)
        self.ci.pack(fill='both', expand=True)
        self.gh_error = tk.StringVar()
        ttk.Label(right, textvariable=self.gh_error, foreground=COLORS['bad']).pack(anchor='w')
        for t in (self.runs, self.ci):
            t.tv.bind('<Double-1>', lambda e, t=t: self.open_selected(t))

    def open_selected(self, table):
        for iid in table.tv.selection():
            url = (table.payload.get(iid) or {}).get('url')
            if url and url.startswith('https://github.com/'):
                self.open_url(url)

    def draw_llr(self, s):
        c = self.llr
        c.delete('all')
        w = max(c.winfo_width(), 300)
        if not s or s.get('llr') is None:
            c.create_text(10, 17, anchor='w', text='no merged stage yet')
            return
        lo, hi, v = s['llr_lo'], s['llr_hi'], s['llr']
        x = lambda t: 20 + (w - 40) * (min(max(t, lo), hi) - lo) / (hi - lo)  # noqa: E731
        c.create_rectangle(20, 12, w - 20, 22, fill='#eeeeee', outline='#999999')
        c.create_line(x(0), 8, x(0), 26, fill='#999999')
        c.create_text(20, 30, text=f'{lo:g} (H0)', anchor='w', font=('Segoe UI', 7))
        c.create_text(w - 20, 30, text=f'{hi:g} (H1)', anchor='e', font=('Segoe UI', 7))
        c.create_oval(x(v) - 6, 11, x(v) + 6, 23, fill=COLORS['running'])
        c.create_text(x(v), 4, text=f'LLR {v:.2f}', font=('Segoe UI', 7))

    def render(self, snap):
        s = snap.get('current_sprt')
        if s:
            if s.get('stage') is None:
                stage = f"none dispatched yet (stages {s.get('first_stage')} to {s.get('last_stage')})"
            else:
                stage = f"{s['stage']} of {s.get('last_stage')} ({s.get('stage_state')})"
            self.fields.set(Name=s['name'], Job=f"{s.get('job')} ({'running' if s.get('job_live') else 'not running'})",
                            Stage=stage, Games=n(s.get('games')),
                            Elo=(f"{s['elo']:+.2f} +/- {s['elo_err']:.2f}" if s.get('elo') is not None else '-'),
                            nElo=(f"{s['nelo']:+.2f} +/- {s['nelo_err']:.2f}" if s.get('nelo') is not None else '-'),
                            LLR=(f"{s['llr']:.2f} ({s['llr_lo']:g}, {s['llr_hi']:g})" if s.get('llr') is not None
                                 else '-'),
                            Bounds=(f"[{s['elo0']:g}, {s['elo1']:g}] nElo" if s.get('elo0') is not None else '-'),
                            Verdict=s.get('finished') or s.get('verdict') or '-', Run=s.get('run'))
        self.draw_llr(s)
        q = [((f'job', f"{j['name']} ({j['type']}, waiting since {P.est(j['started'])})"), 'running', j)
             for j in snap.get('queue', [])]
        for o in (snap.get('roadmap') or {}).get('order', [])[:6]:
            q.append(((o['n'], o['item'][:160]), o['status'], o))
        self.queue.set_rows(q)
        log = (snap.get('networks') or {}).get('sprt_log', [])
        rows = []
        for e in list(reversed(log))[:20]:
            v = e.get('verdict') or ''
            tag = 'good' if v.startswith('H1') else ('bad' if v.startswith('H0') else '')
            rows.append(((e.get('date') or '', e['name'], v[:60],
                          f"{e['elo']:+.2f} +/- {e['elo_err']:.2f}" if e.get('elo') is not None else '-',
                          f"{e['llr']:.2f}" if e.get('llr') is not None else '-'), tag, e))
        self.results.set_rows(rows)
        drows = []
        for d in sorted(snap.get('sprts', []), key=lambda d: d.get('last_at') or '', reverse=True)[:12]:
            stage = '-' if d.get('stage') is None else d['stage']
            drows.append(((d.get('last_at') or '', d['name'], d.get('job'), stage,
                           n(d.get('games')), f"{d['elo']:+.2f} +/- {d['elo_err']:.2f}" if d.get('elo') is not None
                           else '-', f"{d['llr']:.2f}" if d.get('llr') is not None else '-',
                           d.get('finished') or d.get('verdict') or d.get('stage_state') or 'waiting'),
                          'running' if d.get('job_live') and not d.get('finished') else '', d))
        self.drivers.set_rows(drows)
        gh = snap.get('github') or {}
        fmt = lambda r: (r['status'] if r['status'] != 'completed' else r['conclusion'])  # noqa: E731
        tag = lambda r: {'success': 'good', 'failure': 'bad', 'cancelled': 'warn'}.get(  # noqa: E731
            r['conclusion'], 'running' if r['status'] != 'completed' else '')
        self.runs.set_rows([((r['workflow'], r['branch'], fmt(r), P.est(r['created']), r['title']), tag(r), r)
                            for r in gh.get('runs', [])])
        self.ci.set_rows([((r['branch'], fmt(r), P.est(r['created']), r['title']), tag(r), r)
                          for r in gh.get('ci', [])])
        self.gh_error.set(f"gh: {gh['error']}" if gh.get('error') else '')


class TrainingTab(ttk.Frame):
    def __init__(self, parent, open_url):
        super().__init__(parent)
        self.open_url = open_url
        ttk.Label(self, text='Kaggle sessions (most recently run; the token is never shown)',
                  font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=8, pady=(6, 0))
        self.kernels = Table(self, ('kernel', 'status', 'last run (UTC)'), {'kernel': 300}, height=6)
        self.kernels.pack(fill='x', padx=8)
        self.kernels.tv.bind('<Double-1>', lambda e: self.open_kernel())
        self.err = tk.StringVar()
        ttk.Label(self, textvariable=self.err, foreground=COLORS['bad']).pack(anchor='w', padx=8)
        ttk.Label(self, text='Recent training results (downloaded run.json records)',
                  font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=8, pady=(6, 0))
        self.runs = Table(self, ('run', 'arch', 'seed', 'best val loss', 'at superbatch', 'of', 'warm start',
                                 'time', 'commit', 'data'), {'run': 190, 'data': 260}, height=14)
        self.runs.pack(fill='both', expand=True, padx=8, pady=(0, 8))

    def open_kernel(self):
        for iid in self.kernels.tv.selection():
            ref = (self.kernels.payload.get(iid) or {}).get('ref')
            if ref and '/' in ref:
                self.open_url(f'https://www.kaggle.com/code/{ref}')

    def render(self, snap):
        info = snap.get('kaggle_info') or {}
        self.kernels.set_rows([((k['ref'], k.get('status') or '?', k.get('last_run') or ''),
                                {'running': 'running', 'queued': 'running', 'complete': 'good',
                                 'error': 'bad'}.get(k.get('status'), ''), k) for k in info.get('kernels', [])])
        self.err.set(f"kaggle: {info['error']}" if info.get('error') else '')
        self.runs.set_rows([((t['folder'], t['arch'], t['seed'], n(t['best_loss'], '{:.6f}'), t['best_at'],
                              t['last_at'], 'yes' if t['warm'] else 'no', P.duration(t['seconds']), t['commit'],
                              ', '.join(Path(m).stem for m in t['manifests'])),
                             'bad' if t['rc'] not in (0, None) else '', t) for t in snap.get('training_runs', [])])


class NetworksTab(ttk.Frame):
    def __init__(self, parent, open_url):
        super().__init__(parent)
        self.default = tk.StringVar()
        ttk.Label(self, textvariable=self.default, font=('Segoe UI', 10, 'bold'), wraplength=1100).pack(
            anchor='w', padx=8, pady=6)
        self.nets = Table(self, ('network', 'date', 'bench', 'SPRT', 'status'),
                          {'network': 220, 'bench': 220, 'SPRT': 330, 'status': 330}, height=7)
        self.nets.pack(fill='x', padx=8)
        charts = ttk.Frame(self)
        charts.pack(fill='both', expand=True, padx=8, pady=6)
        self.gauntlet = tk.Canvas(charts, bg='white', height=260)
        self.gauntlet.pack(side='left', fill='both', expand=True)
        self.gains = tk.Canvas(charts, bg='white', height=260)
        self.gains.pack(side='left', fill='both', expand=True, padx=(8, 0))
        self.last = None
        for c in (self.gauntlet, self.gains):
            c.bind('<Configure>', lambda e: self.draw())

    def render(self, snap):
        self.last = snap.get('networks') or {}
        nets = self.last.get('nets') or {}
        d = nets.get('default')
        self.default.set(f"Default network: {d['name']} ({d['date']}). {P.plain(d['status'])[:240]}" if d
                         else 'Default network: not found in docs/nets.md')
        rows = []
        for x in nets.get('nets', []):
            if x['name'].startswith('Quantization') or x['name'].startswith('The bake-off'):
                continue
            rows.append(((x['name'] + (' (default)' if x['default'] else ''), x['date'] or '',
                          P.plain(x['bench'])[:60], P.plain(x['sprt'])[:90], P.plain(x['status'])[:90]),
                         'good' if x['default'] else '', x))
        for e in nets.get('entries', []):
            rows.append(((f"{e['entry']} (CI entry)", '', e['bench'], '', e['net']), 'planned', e))
        self.nets.set_rows(rows)
        self.draw()

    def chart(self, c, title, points, ylabel, errors=None, line=False):
        c.delete('all')
        w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 160)
        c.create_text(10, 10, anchor='nw', text=title, font=('Segoe UI', 9, 'bold'))
        if not points:
            c.create_text(w / 2, h / 2, text='no data')
            return
        ys = [p[1] for p in points] + [p[1] + (errors[i] if errors else 0) for i, p in enumerate(points)] + \
             [p[1] - (errors[i] if errors else 0) for i, p in enumerate(points)]
        lo, hi = min(ys), max(ys)
        if hi - lo < 1:
            hi, lo = hi + 1, lo - 1
        pad = (hi - lo) * 0.08
        lo, hi = lo - pad, hi + pad
        L, R, T, B = 60, w - 20, 34, h - 40
        X = lambda i: L + (R - L) * (i + 0.5) / len(points)  # noqa: E731
        Y = lambda v: B - (B - T) * (v - lo) / (hi - lo)  # noqa: E731
        c.create_line(L, B, R, B, fill='#999999')
        c.create_line(L, T, L, B, fill='#999999')
        for k in range(5):
            v = lo + (hi - lo) * k / 4
            c.create_text(L - 4, Y(v), text=f'{v:,.0f}', anchor='e', font=('Segoe UI', 7))
        c.create_text(12, (T + B) / 2, text=ylabel, angle=90, font=('Segoe UI', 7))
        prev = None
        for i, (label, v) in enumerate(points):
            x, y = X(i), Y(v)
            if errors:
                c.create_line(x, Y(v - errors[i]), x, Y(v + errors[i]), fill='#90a4ae', width=2)
            if line and prev:
                c.create_line(prev[0], prev[1], x, y, fill=COLORS['running'], width=2)
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=COLORS['running'], outline='')
            c.create_text(x, y - 10, text=f'{v:,.1f}', font=('Segoe UI', 7))
            c.create_text(x, B + 8, text=label[:14], font=('Segoe UI', 7), anchor='n')
            prev = (x, y)

    def draw(self):
        if self.last is None:
            return
        g = self.last.get('gauntlets', [])
        self.chart(self.gauntlet, 'Gauntlet ratings (Ordo; anchor sets differ between runs)',
                   [(x['date'], x['rating']) for x in g], 'rating', errors=[x['error'] for x in g])
        gains = self.last.get('gains', [])
        self.chart(self.gains, 'SPRT gains over time (accepted SPRTs, cumulative Elo)',
                   [(f"{d[5:]} {name[:8]}", tot) for d, name, elo, tot in gains], 'cumulative Elo', line=True)


class DataTab(ttk.Frame):
    def __init__(self, parent, open_url):
        super().__init__(parent)
        cols = ('games', 'positions', 'saved', 'labelling net', 'seed', 'threads', 'settings', 'sealed', 'where')
        self.table = Table(self, cols, {'#0': 150, 'settings': 260, 'where': 330, 'labelling net': 90,
                                        'threads': 60, 'sealed': 60}, height=24, tree=True)
        self.table.pack(fill='both', expand=True, padx=8, pady=8)

    def render(self, snap):
        gens = {}
        for s in snap.get('data', []):
            gens.setdefault(s.get('generation'), []).append(s)
        groups = []
        for g in sorted(gens, key=lambda x: (x is None, x)):
            parts = gens[g]
            tot_g = sum(p.get('games') or 0 for p in parts)
            tot_p = sum(p.get('positions') or 0 for p in parts)
            kids = []
            for p in parts:
                settings = (f"{n(p.get('nodes'))} nodes, adj {p.get('adjudicate', '-')}, split {p.get('split', '-')}"
                            if p.get('sealed') else 'copied, not sealed')
                kids.append((p['run'], (n(p.get('games')), n(p.get('positions')), n(p.get('saved')),
                                        p.get('net'), p.get('seed'), p.get('threads') or '-', settings,
                                        'yes' if p.get('sealed') else 'no', '; '.join(p.get('where', [])) or '-'),
                             '' if p.get('sealed') else 'warn', p))
            groups.append((f'generation {g}', (n(tot_g), n(tot_p), '', '', '', '', f'{len(parts)} parts', '', ''),
                           'running', kids))
        self.table.set_tree(groups)


class MachineTab(ttk.Frame):
    def __init__(self, parent, open_url):
        super().__init__(parent)
        self.fields = Fields(self, ['CPU (Windows)', 'Memory (Windows)', 'WSL memory', 'WSL load', 'C: free',
                                    'WSL disk free'], cols=1)
        self.fields.pack(anchor='w', padx=8, pady=8)
        self.warn = tk.StringVar()
        ttk.Label(self, textvariable=self.warn, foreground=COLORS['bad'], font=('Segoe UI', 10, 'bold')).pack(
            anchor='w', padx=8)

    def render(self, snap):
        m = snap.get('machine') or {}
        mem, wm, cd, wd = m.get('memory'), m.get('wsl_memory'), m.get('c_disk'), m.get('wsl_disk')
        self.fields.set(**{
            'CPU (Windows)': n(m.get('cpu'), '{:.0f}%') if m.get('cpu') is not None else 'measuring ...',
            'Memory (Windows)': (f"{mem['load']}% used, {gbytes(mem['free'])} free of {gbytes(mem['total'])}"
                                 if mem else '-'),
            'WSL memory': (f"{gbytes(wm['available'])} available of {gbytes(wm['total'])}" if wm else '-'),
            'WSL load': ' '.join(m.get('wsl_load') or []) or '-',
            'C: free': (f"{gbytes(cd['free'])} of {gbytes(cd['total'])}" if cd else '-'),
            'WSL disk free': (f"{gbytes(wd['free'])} of {gbytes(wd['total'])} (virtual; its file grows on C:)"
                              if wd else '-')})
        w = m.get('warnings') or []
        self.warn.set('\n'.join(w) if w else 'No warnings.')


class RoadmapTab(ttk.Frame):
    def __init__(self, parent, open_url):
        super().__init__(parent)
        self.title = tk.StringVar()
        ttk.Label(self, textvariable=self.title, font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=8, pady=6)
        pw = ttk.PanedWindow(self, orient='vertical')
        pw.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self.items = Table(pw, ('status', 'detail'), {'#0': 330, 'status': 80, 'detail': 760}, height=14, tree=True)
        self.order = Table(pw, ('#', 'item', 'estimate'), {'#': 40, 'item': 900, 'estimate': 160}, height=8)
        pw.add(self.items, weight=3)
        pw.add(self.order, weight=2)

    def render(self, snap):
        r = snap.get('roadmap') or {}
        self.title.set(r.get('title') or 'Section 5.6 not found in DESIGN.md')
        self.items.set_tree([(g['group'], ('', ''), 'running', [
            (i['item'][:60], (i['status'], i['status_text'][:300]), i['status'], i) for i in g['items']])
            for g in r.get('groups', [])])
        self.order.set_rows([((o['n'], o['item'][:300], o['estimate']), o['status'], o) for o in r.get('order', [])])


READ_ONLY_TABS = [('Jobs', JobsTab), ('Testing', TestingTab), ('Training', TrainingTab),
                  ('Networks and strength', NetworksTab), ('Data', DataTab), ('Machine', MachineTab),
                  ('Roadmap', RoadmapTab)]


def open_url(url):
    if url.startswith('https://'):
        webbrowser.open(url)


# ================================================================ the window and the poller

class App:
    def __init__(self, root, cfg, runner, ctl, collector, toast=notify.toast, autostart=True):
        self.root, self.cfg, self.ctl, self.collector, self.toast = root, cfg, ctl, collector, toast
        root.title(TITLE)
        root.geometry('1280x800')
        self.queue = queue.Queue()
        self.wake = threading.Event()
        self.prev = None
        nb = ttk.Notebook(root)
        nb.pack(fill='both', expand=True)
        self.datagen_tab = DatagenTab(nb, self)
        nb.add(self.datagen_tab, text='Data generation')
        self.tabs = [self.datagen_tab]
        for title, cls in READ_ONLY_TABS:
            t = cls(nb, open_url)
            nb.add(t, text=title)
            self.tabs.append(t)
        bar = ttk.Frame(root)
        bar.pack(fill='x')
        self.status = tk.StringVar(value='starting ...')
        ttk.Label(bar, textvariable=self.status).pack(side='left', padx=8, pady=2)
        ttk.Button(bar, text='Refresh', command=self.poke).pack(side='right', padx=8, pady=2)
        self.root.after(300, self.drain)
        if autostart:
            threading.Thread(target=self.poll_loop, daemon=True).start()

    def ui(self, fn):
        self.queue.put(('call', fn))

    def poke(self):
        self.wake.set()

    def snapshot(self):
        probe, err = None, None
        try:
            probe = self.ctl.probe([self.cfg['wsl_data']])
        except Exception as e:  # noqa: BLE001
            err = str(e)
        snap = self.collector.collect(probe, probe_error=err)
        snap['datagen'] = self.ctl.running(probe) if probe else None
        if snap['datagen'] and snap['datagen']['live']:
            self.ctl.ensure_watchdog(snap['datagen']['name'])
        snap['watchdog'] = self.ctl.watchdog_state()
        return snap

    def poll_loop(self):
        while True:
            try:
                self.queue.put(('snap', self.snapshot()))
            except Exception:  # noqa: BLE001
                self.queue.put(('error', traceback.format_exc(limit=3)))
            self.wake.wait(self.cfg['poll_seconds'])
            self.wake.clear()

    def drain(self):
        try:
            while True:
                kind, item = self.queue.get_nowait()
                if kind == 'call':
                    item()
                elif kind == 'error':
                    self.status.set('poll failed: ' + item.strip().splitlines()[-1][:200])
                else:
                    self.show(item)
        except queue.Empty:
            pass
        self.root.after(500, self.drain)

    def show(self, snap):
        for t in self.tabs:
            try:
                t.render(snap)
            except Exception:  # noqa: BLE001
                self.status.set(f'{type(t).__name__}: ' + traceback.format_exc(limit=2).strip().splitlines()[-1])
        for title, text in notify.events(self.prev, snap):
            self.toast(f'Fork: {title}', text)
            self.datagen_tab.say(f'notification: {title}: {text}')
        self.prev = snap
        err = f"  WSL: {snap['probe_error'][:120]}" if snap.get('probe_error') else ''
        self.status.set(f"updated {time.strftime('%I:%M:%S %p')}; every {self.cfg['poll_seconds']} s{err}")


def single_instance(state):
    """True if no other Control Center window runs (a pid file in the state folder)."""
    state.mkdir(parents=True, exist_ok=True)
    f = state / 'app.json'
    try:
        other = json.loads(f.read_text(encoding='utf-8'))
        if other.get('pid') != os.getpid() and winutil.pid_alive(other.get('pid')):
            return False
    except (OSError, ValueError):
        pass
    f.write_text(json.dumps({'pid': os.getpid(), 'started': time.time()}), encoding='utf-8')
    return True


def main():
    cfg = config.load()
    state = config.state_dir()
    root = tk.Tk()
    if not single_instance(state):
        root.withdraw()
        messagebox.showinfo(TITLE, 'The Control Center is already open.')
        return
    runner = Runner()
    collector = collectors.Collector(cfg, ReadOnly(runner), state=state)
    ctl = generation_control.GenerationControl(cfg, runner, state=state, windows_jobs=collector.windows_jobs)
    App(root, cfg, runner, ctl, collector)
    root.mainloop()


if __name__ == '__main__':
    main()
