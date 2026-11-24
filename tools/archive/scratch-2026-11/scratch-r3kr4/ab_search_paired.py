"""Scratch wrapper (not committed) around bench/ab_search.py: the same
interleaved rounds and identity checks (its Side class), then ab_search's own
report plus the per-round nps lists and the paired ratio B/A per round:
geometric mean with a normal 95% interval on the log ratios (the design
report's method).

    python3 -I ab_paired.py REPO A/fork B/fork A_COMMIT B_COMMIT ROUNDS CORE [--allow-identical]
"""
import math
import statistics
import sys

repo, a, b, ac, bc, rounds, core = sys.argv[1:8]
allow = '--allow-identical' in sys.argv
sys.path.insert(0, f'{repo}/bench')
import ab_search  # noqa: E402

rounds, core = int(rounds), int(core)
sides = {'A': ab_search.Side('A', a, 'baseline', ac), 'B': ab_search.Side('B', b, 'baseline', bc)}
if sides['A'].sha == sides['B'].sha and not allow:
    sys.exit('identical binaries')
for s in sides.values():
    s.check_identity()
nps = {'A': [], 'B': []}
bench = {}
for r in range(rounds):
    for side in (['A', 'B'] if r % 2 == 0 else ['B', 'A']):
        nodes, sig, v = sides[side].run(core)
        if bench.setdefault(side, (nodes, sig)) != (nodes, sig):
            sys.exit(f'{side}: bench changed')
        nps[side].append(v)
    print(f'round {r + 1}: A {nps["A"][-1]:.0f} B {nps["B"][-1]:.0f} ratio {nps["B"][-1] / nps["A"][-1]:.4f}',
          flush=True)
print('bench', bench, 'same' if bench['A'] == bench['B'] else 'DIFFER')
logs = [math.log(y / x) for x, y in zip(nps['A'], nps['B'])]
m, sd = statistics.mean(logs), statistics.stdev(logs)
half = 1.96 * sd / math.sqrt(len(logs))
print(f'paired ratio B/A {math.exp(m):.4f} (95% {math.exp(m - half):.4f}-{math.exp(m + half):.4f}), {len(logs)} rounds')
a_med, b_med = statistics.median(nps['A']), statistics.median(nps['B'])
print(f'median A {a_med:.0f} B {b_med:.0f} change {100 * (b_med - a_med) / a_med:+.1f}%; best A {max(nps["A"]):.0f} '
      f'B {max(nps["B"]):.0f} change {100 * (max(nps["B"]) - max(nps["A"])) / max(nps["A"]):+.1f}%')
