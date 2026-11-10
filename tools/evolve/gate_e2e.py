# SPDX-License-Identifier: GPL-3.0-or-later

"""The evolve gate end to end on Linux (ideas.md idea 23; owner, 2026-11-09:
the ordering pilot's first prerequisite): build the gate's baseline with
every configured compiler, then run planted candidates through the real
gate (real trees, builds, preprocessing, perft, suites and benches) and
check that each stops at the step it should.

The planted set, per region: a clean body (passes every step), the escapes
audit-1 U-2 found (a %:define digraph, a '}' that leaves the function, code
hidden after a "//" inside a string literal, a make_unique allocation, hidden
static state: each refused by the static rules), and for the ordering region
a body only clang++-19 accepts (std::div, not constexpr in GCC 11's library:
refused by g++ at the compile step, audit-1 U-17) and a body whose int
arithmetic overflows at the inputs' extremes (refused at the compile step by
tests/test_ordering.cpp's static_assert). With --layers, the static rules are
switched off for the escapes, to show which later step stops each one.

    python3 tools/evolve/gate_e2e.py --region quiet_order --work ~/fork-evolve/e2e \\
        --compilers g++ clang++-19 --test-cache ~/fork-evolve/cache [--layers] [--skip-clean]

Exit status 0 if every candidate stopped where expected; prints one line per
candidate (step, compiler, time) and writes e2e.json in --work.
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gate  # noqa: E402
import regions  # noqa: E402

# (name, body, expected step with the static rules on, expected step with them off or None to skip)
CANDIDATES = {
    'quiet_order': [
        ('clean: the follow entry at its weight less one quarter',
         '  int score = s.butterfly;\n  if (s.has_reply) score += s.reply * s.reply_weight / 4;\n'
         '  if (s.has_follow) score += s.follow * (s.follow_weight - 1) / 4;\n  return score;', 'done', None),
        ('escape: a %:define digraph', '  return s.butterfly;\n%:define ReplyWeight 640\n', 'static',
         'preprocessed'),
        ("escape: an unbalanced '}' that leaves the function", '  return s.butterfly; }', 'static', 'build'),
        ('escape: code after a "//" inside a string literal',
         '  const char* p = "//"; static int n = 0; return s.butterfly + n + p[0] * 0;', 'static', 'build'),
        ('escape: a make_unique allocation', '  auto p = std::make_unique<int>(s.butterfly);\n  return *p;',
         'static', 'build'),
        ('escape: hidden static state', '  static int calls = 0;\n  return s.butterfly + (++calls & 1);', 'static',
         'build'),
        ('two compilers: std::div (clang++-19 accepts, GCC 11 rejects)', '  return std::div(s.butterfly, 3).quot;',
         'build', None),
        ('overflow at the extremes: a product of three entries', '  return s.butterfly * s.reply * s.follow;',
         'build', None),
    ],
    'lmr': [
        ('clean: one ply more for late moves with a poor history from depth 8',
         '  return c.depth >= 8 && c.move_number >= 12 && c.history < -4000 ? 1 : 0;', 'done', None),
        ('escape: a %:define digraph', '  static_cast<void>(c);\n  return 0;\n%:define LmrCorrectionStrength 640\n',
         'static', 'preprocessed'),
        ("escape: an unbalanced '}' that leaves the function", '  static_cast<void>(c);\n  return 0; }', 'static',
         'build'),
        ('escape: code after a "//" inside a string literal',
         '  const char* p = "//"; static int n = 0; return n + p[0] * 0 + c.depth * 0;', 'static', 'build'),
        ('escape: a make_unique allocation', '  auto p = std::make_unique<int>(c.depth);\n  return *p * 0;', 'static',
         'build'),
        ('escape: hidden static state', '  static int calls = 0;\n  return (++calls & 1) * 0 + c.depth * 0;', 'static',
         'build'),
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--region', default='quiet_order', choices=sorted(CANDIDATES))
    ap.add_argument('--work', required=True)
    ap.add_argument('--repo', default=str(HERE.parents[1]))
    ap.add_argument('--commit', default='HEAD')
    ap.add_argument('--compilers', nargs='+', default=['g++', 'clang++-19'])
    ap.add_argument('--test-cache')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--layers', action='store_true', help='also run the escapes with the static rules off')
    ap.add_argument('--skip-clean', action='store_true', help='leave out the clean body (its full gate takes longest)')
    a = ap.parse_args()
    work = Path(a.work).expanduser()
    runner = gate.Runner(a.repo, work, jobs=a.jobs, test_cache=a.test_cache, compilers=a.compilers)
    commit = runner.resolve(a.commit)
    started = time.time()
    tree = runner.tree(commit, {}, 'baseline')
    perft = None
    for variant in runner.variants():
        built, log, build = variant.build(tree)
        if not built:
            sys.exit(f'the baseline does not build with {variant.compiler}: {log[-1500:]}')
        counts = variant.perft(build / 'fork')
        if perft is not None and counts != perft:
            sys.exit(f'the baseline perft differs between compilers: {counts} != {perft}')
        perft = counts
    reference = gate.make_reference(runner, a.region, tree, perft)
    print(f'baseline {commit[:12]} built with {", ".join(a.compilers)} in {time.time() - started:.0f} s; '
          f'perft {perft}; units including {regions.REGIONS[a.region]}: '
          f'{", ".join(f"{k}: {len(v)}" for k, v in reference.units.items())}', flush=True)
    runs = [(name, body, step, False) for name, body, step, _ in CANDIDATES[a.region]
            if not (a.skip_clean and step == 'done')]
    if a.layers:
        runs += [(name, body, step, True) for name, body, _, step in CANDIDATES[a.region] if step]
    results, ok = [], True
    real_static = gate.static_violations
    for k, (name, body, expected, layers) in enumerate(runs):
        gate.static_violations = (lambda b: []) if layers else real_static
        t0 = time.time()
        try:
            result = gate.run_gate(runner, commit, a.region, body, reference, f'e2e-{k}')
        finally:
            gate.static_violations = real_static
        good = result.step == expected
        ok = ok and good
        results.append({'candidate': name, 'static_rules': not layers, 'expected': expected, 'step': result.step,
                        'passed': result.passed, 'compiler': result.compiler, 'seconds': round(time.time() - t0),
                        'bench': result.bench, 'detail': result.detail[-1200:]})
        print(f'{"ok  " if good else "FAIL"} {"rules off: " if layers else ""}{name}: stopped at {result.step}'
              f'{" (" + result.compiler + ")" if result.compiler else ""}, expected {expected}; '
              f'{time.time() - t0:.0f} s{"; bench " + str(result.bench) if result.passed else ""}', flush=True)
        if not good:
            print('    ' + result.detail[-1200:].replace('\n', '\n    '), flush=True)
    (work / 'e2e.json').write_text(json.dumps({'region': a.region, 'commit': commit, 'compilers': a.compilers,
                                               'compiler_versions': runner.compiler_version(), 'perft': perft,
                                               'results': results, 'all_as_expected': ok}, indent=1),
                                   encoding='utf-8')
    print(f'{"every candidate stopped where expected" if ok else "SOME CANDIDATES DID NOT"}; '
          f'{time.time() - started:.0f} s in all')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
