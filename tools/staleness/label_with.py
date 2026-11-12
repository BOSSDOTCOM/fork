# SPDX-License-Identifier: GPL-3.0-or-later
"""Resumable labels for the staleness audit's re-runs (coordinator's order of
2026-11-12: every constant chosen by a declared measurement rule is measured
again on the current default net and search, by the same rule).

The labels are those of tools/lmr_history_measure.py `label` (the 25 M-node
labels of the evolve split of tools/evolve/positions.jsonl, `go nodes N`
from a fresh state, Hash 64, mate scores and |score| > 1500 cp dropped),
with UCI options set first, so the IIR measurement's labels can be made the
way tools/no_move_measure.py makes them (the reduction off) while every
answer is saved as it finishes (a preempted VM resumes where it was).

    label_with.py FORK OUT.jsonl [--nodes 25000000] [--jobs 8] [--option NAME=VALUE ...]
"""
import argparse
import json
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'evolve'))
import lmr_history_measure as lhm  # noqa: E402
import proxies  # noqa: E402


class OptionEngine(lhm.Engine):
    def configure(self, options):
        for name, value in (options or {}).items():
            self.send(f'setoption name {name} value {value}')
        self.send('isready')
        self.until('readyok')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('fork')
    ap.add_argument('out')
    ap.add_argument('--nodes', type=int, default=25000000)
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--option', action='append', default=[])
    a = ap.parse_args()
    options = dict(o.split('=', 1) for o in a.option)
    lhm.Engine = OptionEngine  # lhm.run builds its engines from this name
    repo = os.path.dirname(os.path.dirname(HERE))
    rows = proxies.load_positions(os.path.join(repo, 'tools', 'evolve', 'positions.jsonl'), 'evolve')
    saved_path = a.out + '.answers'
    done = {}
    if os.path.exists(saved_path):
        with open(saved_path, 'rb') as f:
            data = f.read()
        data = data[:data.rfind(b'\n') + 1]
        with open(saved_path, 'wb') as f:
            f.write(data)
        for line in data.decode('utf-8').splitlines():
            d = json.loads(line)
            done[d['id']] = d['answer']
    todo = [r for r in rows if r['id'] not in done]
    print(f'{len(done)} answers saved earlier, {len(todo)} to search; options {options}', flush=True)
    lock = threading.Lock()
    with open(saved_path, 'a', encoding='utf-8') as saved:
        def record(r, s):
            with lock:
                saved.write(json.dumps({'id': r['id'], 'answer': s}) + '\n')
                saved.flush()
        for r, s in zip(todo, lhm.run(a.fork, todo, a.nodes, options, a.jobs, 64, record)):
            done[r['id']] = s
    kept = 0
    with open(a.out + '.part', 'w', encoding='utf-8') as f:
        for r in rows:
            s = done[r['id']]
            if s['mate'] or s['score'] is None or abs(s['score']) > lhm.LabelCap:
                continue
            f.write(json.dumps({'id': r['id'], 'fen': r['fen'], 'bm': s['move'], 'ce': s['score'],
                                'depth': s['depth'], 'nodes': a.nodes}) + '\n')
            kept += 1
    os.replace(a.out + '.part', a.out)
    print(f'{kept} of {len(rows)} positions labeled at {a.nodes} nodes')


if __name__ == '__main__':
    main()
