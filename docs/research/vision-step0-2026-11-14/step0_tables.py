# SPDX-License-Identifier: GPL-3.0-or-later
"""Vision step 0 (ideas.md 185): the report's tables from the JSON results of step0_study.py (study-SET.json,
inject-*.json) and step0_routing.py (routing-SET.json), as markdown on stdout.

    step0_tables.py RESULTS_DIR [--line NAME=PCT ...]
"""
import argparse
import json
from pathlib import Path

SETS = ('g4c', 'g4s2val')
DESIGNS = ('square', 'pooled', 'bucket')
LABEL = {
    'xl': "x_lower's state", 'xx': 'full exposure plane', 'links': "the 608 pawn links (both perspectives)",
    'xpn': 'x_lower, cheaper pawn or knight attacker', 'xsl': 'x_lower, cheaper slider attacker',
    'pin': 'pinned (absolute)', 'pinq': 'pinned to the queen', 'disc': 'discovery candidates',
    'forkn': 'knight fork squares', 'forkp': 'pawn-push fork squares', 'under': 'under-defended, not exposed',
    'file': 'file-line contact (R, Q)', 'block': 'blockade occupant of passers', 'loose': 'loose / overprotected',
    'kk': 'king pair (KK)', 'mat': 'captured-material ordinals', 'trap': 'trapped (d_mob rule)',
    'trapa': 'trapped and attacked', 'back': 'back-rank weakness', 'sev': 'absolute 7th (control)',
    'bad': 'bad bishop (control)',
}
PANEL = ('pin', 'pinq', 'disc', 'forkn', 'forkp', 'under', 'file', 'block', 'loose', 'kk', 'mat', 'trap', 'trapa',
         'back', 'sev', 'bad')


def cell(res, net):
    r = res.get(net)
    if not r:
        return 'n/a'
    return f"{r['share_pct']:.3f} ± {r['se_pct']:.3f}"


def load(d):
    out = {}
    for s in SETS:
        p = Path(d) / f'study-{s}.json'
        if p.exists():
            out[s] = json.loads(p.read_text())
    return out


def best(row, net, sets_data, fam, side):
    vals = []
    for s, data in sets_data.items():
        f = data['families'].get(fam, {}).get(side)
        if not f:
            continue
        for d in DESIGNS:
            r = f.get(d, {}).get(net)
            if r:
                vals.append((r['share_pct'], r['se_pct'], s, d))
    return max(vals) if vals else None


def calibration(sets_data):
    print('| Family | Side | Net | Set | by square | pooled | by bucket | positions with any |')
    print('|---|---|---|---|---|---|---|---|')
    for fam, nets in (('xl', ('r3pp1', 'r8brft1', 'r3kr1', 's512r2')), ('xx', ('s512r2', 'r3pp1', 'r8brft1', 'r3kr1')),
                      ('links', ('s512r2', 'r8brft1', 'r3kr1'))):
        for side in ('mover', 'opp', 'both'):
            for net in nets:
                for s, data in sets_data.items():
                    f = data['families'].get(fam, {}).get(side)
                    if not f or net not in f.get('square', {}):
                        continue
                    prev = f['prevalence']['positions_with_any_pct']
                    print(f"| {LABEL[fam]} | {side} | {net} | {s} | {cell(f['square'], net)} | "
                          f"{cell(f['pooled'], net)} | {cell(f['bucket'], net)} | {prev:.1f}% |")


def order(sets_data):
    print('| Family | Side | Net | Set | by square | pooled | by bucket | positions with any |')
    print('|---|---|---|---|---|---|---|---|')
    for side in ('mover', 'opp', 'both'):
        for fam in ('xl', 'xpn', 'xsl'):
            for net in ('r3kr1', 'r8brft1', 'r3pp1'):
                for s, data in sets_data.items():
                    f = data['families'].get(fam, {}).get(side)
                    if not f or net not in f.get('square', {}):
                        continue
                    prev = f['prevalence']['positions_with_any_pct']
                    print(f"| {LABEL[fam]} | {side} | {net} | {s} | {cell(f['square'], net)} | "
                          f"{cell(f['pooled'], net)} | {cell(f['bucket'], net)} | {prev:.1f}% |")


def panel(sets_data, net, lines):
    print('| Family | Side | positions with any (g4c) | cells per position | g4c square | g4c pooled | g4c bucket | '
          'g4s2-val square | g4s2-val pooled | g4s2-val bucket | largest | against 0.5% | against the '
          'calibrated line |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for fam in PANEL:
        sides = list(sets_data['g4c']['families'].get(fam, {}).keys())
        for side in sides:
            f = sets_data['g4c']['families'][fam][side]
            g = sets_data.get('g4s2val', {}).get('families', {}).get(fam, {}).get(side, {})
            prev = f['prevalence']
            b = best(None, net, sets_data, fam, side)
            big = f'{b[0]:.3f} ({b[2]}, {b[3]})' if b else 'n/a'
            old = 'below' if b and b[0] < 0.5 else 'above'
            cal = ', '.join(f"{'below' if b and b[0] < v else 'above'} {k}" for k, v in lines.items())
            print(f"| {LABEL[fam]} | {side} | {prev['positions_with_any_pct']:.2f}% | "
                  f"{prev['cells_per_position']:.3f} | {cell(f['square'], net)} | {cell(f['pooled'], net)} | "
                  f"{cell(f['bucket'], net)} | {cell(g.get('square', {}), net)} | {cell(g.get('pooled', {}), net)} | "
                  f"{cell(g.get('bucket', {}), net)} | {big} | {old} | {cal} |")


def injections(d):
    print('| Injected family | Side | Injected (% of the new variance) | Set | recovered: by square | pooled | by bucket |')
    print('|---|---|---|---|---|---|---|')
    for p in sorted(Path(d).glob('inject-*.json')):
        r = json.loads(p.read_text())
        inj = r['inject']
        f = r['families'][inj['family']][inj['side']]
        net = r['nets'][0]
        print(f"| {LABEL[inj['family']]} | {inj['side']} | {inj['share_of_new_var_pct']:.3f} | "
              f"{r['feat'].replace('feat-', '').replace('.npz', '')} | {cell(f['square'], net)} | "
              f"{cell(f['pooled'], net)} | {cell(f['bucket'], net)} |")


def routing(d):
    print('| Set | Routing | heads | held-out loss | against the phase refit (8-fold mean ± se) | lambda | iterations |')
    print('|---|---|---|---|---|---|---|')
    for s in SETS:
        p = Path(d) / f'routing-{s}.json'
        if not p.exists():
            continue
        r = json.loads(p.read_text())
        print(f"| {s} | r3kr1 as shipped (integer) | 8 | {r['shipped_integer']['loss']:.7f} | "
              f"{r['shipped_integer']['loss'] - r['routings']['phase']['loss']:+.2e} | | |")
        print(f"| {s} | r3kr1 as shipped (float form) | 8 | {r['shipped_float']['loss']:.7f} | | | |")
        for name, x in r['routings'].items():
            label = name + (f" (column {r['column']})" if name == 'column' else '')
            print(f"| {s} | {label} | {x['heads']} | {x['loss']:.7f} | {x['diff_vs_phase']:+.2e} ± "
                  f"{x['diff_vs_phase_se']:.1e} | {x['lambda']:g} | {x['iterations']} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data')
    ap.add_argument('--line', action='append', default=[], help='NAME=PCT')
    a = ap.parse_args()
    sets_data = load(a.data)
    lines = {k: float(v) for k, v in (x.split('=') for x in a.line)}
    print('## calibration\n')
    calibration(sets_data)
    print('\n## order\n')
    order(sets_data)
    for net in ('r3kr1', 'r8brft1'):
        print(f'\n## panel {net}\n')
        panel(sets_data, net, lines)
    print('\n## injections\n')
    injections(a.data)
    print('\n## routing\n')
    routing(a.data)


if __name__ == '__main__':
    main()
