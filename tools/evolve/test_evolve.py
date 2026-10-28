"""Unit tests of the heuristic-discovery harness (ideas.md idea 23): regions
and the guard, the gate's rules and order (with a fake runner: no builds),
the proxies' metrics, the population, the agents' parsing and budget, the
match parser, and one orchestrated generation with stub agents and fakes.

    python3 -m unittest discover -s tools/evolve -p 'test_*.py'
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agents  # noqa: E402
import gate  # noqa: E402
import match  # noqa: E402
import orchestrator  # noqa: E402
import population  # noqa: E402
import proxies  # noqa: E402
import regions  # noqa: E402

FILE = """#pragma once
int before();
int lmr_correction(int c) {
  // FORK-EVOLVE-BEGIN lmr
  return 0;
  // FORK-EVOLVE-END lmr
}
int after();
"""
PATH = regions.REGIONS['lmr']


class RegionTests(unittest.TestCase):
    def test_body_and_replace(self):
        self.assertEqual(regions.body(FILE, 'lmr'), '  return 0;')
        new = regions.replace_body(FILE, 'lmr', '  return c > 3 ? 1 : 0;')
        self.assertEqual(regions.body(new, 'lmr'), '  return c > 3 ? 1 : 0;')
        self.assertEqual(regions.replace_body(new, 'lmr', '  return 0;'), FILE)

    def test_bad_markers(self):
        for text in (FILE.replace('  // FORK-EVOLVE-END lmr\n', ''),
                     FILE.replace('END lmr', 'END other'),
                     FILE + '// FORK-EVOLVE-BEGIN lmr\n// FORK-EVOLVE-END lmr\n',
                     FILE.replace('BEGIN lmr', 'BEGIN Bad-Name')):
            with self.assertRaises(regions.RegionError):
                regions.find_regions(text)

    def test_committed_region(self):
        """The engine's region as committed: present, clean, and the zero correction."""
        repo = Path(__file__).resolve().parents[2]
        text = (repo / PATH).read_text(encoding='utf-8')
        self.assertEqual(set(regions.find_regions(text)), {'lmr'})
        body = regions.body(text, 'lmr')
        self.assertEqual(gate.static_violations(body), [])
        self.assertIn('return 0;', body)

    def test_guard_accepts_body_changes_only(self):
        good = regions.replace_body(FILE, 'lmr', '  return 1;')
        self.assertEqual(regions.guard({PATH: FILE}, {PATH: good}, 'lmr'), (True, ''))

    def test_guard_rejects(self):
        cases = {
            'outside': FILE.replace('int after();', 'int after(); int sneaky();'),
            'marker removed': FILE.replace('  // FORK-EVOLVE-END lmr\n', ''),
            'signature': FILE.replace('int lmr_correction(int c)', 'int lmr_correction(long c)'),
        }
        for why, text in cases.items():
            ok, reason = regions.guard({PATH: FILE}, {PATH: text}, 'lmr')
            self.assertFalse(ok, why)
            self.assertTrue(reason)
        ok, reason = regions.guard({PATH: FILE}, {PATH: FILE, 'src/search/searcher.cpp': 'x'}, 'lmr')
        self.assertFalse(ok)
        self.assertIn('outside the region', reason)
        self.assertFalse(regions.guard({PATH: FILE}, {PATH: FILE}, 'nosuch')[0])


class StaticRuleTests(unittest.TestCase):
    def test_clean_bodies_pass(self):
        for body in ('  return c.depth >= 8 && c.history < 0 ? 1 : 0;',
                     '  static_cast<void>(c);\n  return 0;',
                     '  // a comment saying new or float is not code\n  return 0;'):
            self.assertEqual(gate.static_violations(body), [], body)

    def test_each_rule_fires(self):
        cases = {
            '  int* p = new int(1); return *p;': 'heap allocation',
            '  if (c.depth) throw 1; return 0;': 'exceptions',
            '  const double r = 0.4; return int(r);': 'floating point',
            '  return rand() % 2;': 'randomness or the clock',
            '  static int n = 0; return ++n;': 'static or shared state',
            '#define X 1\n  return X;': 'preprocessor lines',
            '  printf("x"); return 0;': 'I/O',
            '  // FORK-EVOLVE-END lmr\n  return 0;': 'region markers inside the body',
        }
        for body, reason in cases.items():
            self.assertIn(reason, gate.static_violations(body), body)

    # Audit-1 (A6, U-2): bodies the first rules let through, each of which
    # compiles in searcher.cpp with clang -Werror (the audit's probe).
    def test_float_literals_in_every_form(self):
        for body in ('  return static_cast<int>(.5 * c.depth) - c.base;',
                     '  return static_cast<int>(c.depth / 2. + 1.f) - c.base;',
                     '  return static_cast<int>(1e3) > c.history ? 1 : 0;',
                     "  return static_cast<int>(1'0e1'0) > 0;",
                     '  return static_cast<int>(0x1p3) - c.base;',
                     '  return static_cast<int>(0x1.8p1L) - c.base;',
                     '  return c.depth > 0 ? static_cast<int>(sqrt(c.depth)) - 1 : 0;',
                     '  long double r = 1; return static_cast<int>(r);',
                     '  std::float32_t r = 1; return static_cast<int>(r);'):
            self.assertIn('floating point', gate.static_violations(body), body)
        for body in ("  return c.history > 1'000 ? 0x1E : 0b10;", '  return c.depth > 2u ? 1ll : 0x0eull;'):
            self.assertEqual(gate.static_violations(body), [], body)

    def test_digraph_preprocessor_line(self):
        # %: is the digraph of # ([lex.digraph]); this one rewrites a
        # parameter that searcher.cpp reads outside the region.
        reasons = gate.static_violations('  return 0;\n%:define LmrCorrectionStrength 640\n')
        self.assertIn('preprocessor lines', reasons)
        self.assertIn('digraphs or trigraphs', reasons)
        for body in ('  if (c.on_pv) <% return 1; %>\n  return 0;', '  int t<:2:> = {0, 1};\n  return t[0];',
                     '  return 0; // ??/\n', '  return 0;\n  ??=define X 1\n'):
            self.assertIn('digraphs or trigraphs', gate.static_violations(body), body)

    def test_line_splices(self):
        self.assertIn('line splices (backslash-newline)', gate.static_violations('  // a comment \\\n  return 0;'))
        self.assertIn('line splices (backslash-newline)', gate.static_violations('  return 0; /\\\n/ x\n'))
        self.assertIn('backslashes outside literals', gate.static_violations('  int \\u0061 = 1; return a;'))

    def test_code_after_a_string_holding_two_slashes(self):
        self.assertIn('floating point', gate.static_violations(
            '  const char* s = "//"; double x = 0.5 * c.depth; static_cast<void>(s);\n'
            '  return static_cast<int>(x) - c.base;'))
        self.assertIn('static or shared state', gate.static_violations(
            '  const char* s = R"x(")x"; static int n = 0; static_cast<void>(s);\n  return ++n;'))
        self.assertIn('static or shared state', gate.static_violations(
            "  const char q = '\"'; static int n = 0; static_cast<void>(q);\n  return ++n;"))
        # What a literal or a comment holds is not code.
        self.assertEqual(gate.static_violations('  const char* s = "new double /* static"; static_cast<void>(s);\n'
                                                '  return 0; /* "float" */'), [])

    def test_heap_allocation_without_new(self):
        for body in ('  auto p = std::make_unique<int>(c.depth);\n  return *p > 100 ? 1 : 0;',
                     '  auto p = std::make_shared<int>(1);\n  return *p;',
                     '  std::allocator<int> a;\n  return 0;'):
            self.assertIn('heap allocation', gate.static_violations(body), body)
        self.assertIn('containers', gate.static_violations('  std::vector<int> v{1};\n  return v[0];'))

    def test_body_that_leaves_the_function(self):
        body = ('  return 0;\n}\ninline int evolve_calls = 0;\n'
                'inline int evolve_hidden(const LmrContext& c) {\n  ++evolve_calls;\n  return c.depth;')
        self.assertIn('leaves the function (unbalanced braces, brackets or parentheses)',
                      gate.static_violations(body))
        self.assertTrue(gate.static_violations('  return 0;\n}\nint x() {\n  return 1;'))  # balanced, but below 0
        self.assertTrue(gate.static_violations('  if (c.on_pv) {\n  return 0;'))

    # The residual gap of the gate (owner, 2026-10-27): a body's own lines are
    # left out of the preprocessed comparison, so a body that closes its
    # function and adds code after it is stopped by the bracket rule alone.
    # These bodies break no other rule, so the bracket reason must be the
    # only one: if the bracket rule stops working, this test fails.
    LEAVES = 'leaves the function (unbalanced braces, brackets or parentheses)'

    def test_closing_the_function_early_is_caught_by_the_bracket_rule_alone(self):
        for body in (
                # closes the function, then defines another (balanced overall)
                '  return 0;\n}\nconstexpr int evolve_extra(const LmrContext& c) {\n  return c.depth;',
                # closes the function, then adds an overload that the next code could pick
                '  return c.base > 0 ? 0 : 0;\n}\nconstexpr int lmr_correction(int depth) {\n  return depth;',
                # one closer too many at the end
                '  return 0;\n}',
                # a brace opened in a string does not balance a real closer
                '  const char* s = "{"; static_cast<void>(s);\n  return 0;\n}\nconstexpr int f() {\n  return 1;',
                # nor one in a comment, a character literal or a raw string
                '  return 0; // {\n}\nconstexpr int f() {\n  return 1;',
                "  const char q = '{'; static_cast<void>(q);\n  return 0;\n}\nconstexpr int f() {\n  return 1;",
                '  const char* r = R"x({)x"; static_cast<void>(r);\n  return 0;\n}\nconstexpr int f() {\n'
                '  return 1;',
                # brackets of different kinds that do not nest
                '  return (c.depth];',
                '  return c.depth > 3 ? (c.base) : 0);',
                # an opener left open
                '  if (c.on_pv) {\n  return 0;'):
            self.assertEqual(gate.static_violations(body), [self.LEAVES], body)

    def test_brackets_inside_literals_and_comments_do_not_count(self):
        for body in ('  const char* s = "}"; static_cast<void>(s);\n  return 0;',
                     '  return 0; // }\n',
                     '  return 0; /* } ) ] */',
                     "  const char q = '}'; static_cast<void>(q);\n  return 0;",
                     '  const char* r = R"x(} ")x"; static_cast<void>(r);\n  return 0;',
                     '  if (c.on_pv) {\n    return (c.depth + 1) / 2;\n  }\n  return 0;'):
            self.assertEqual(gate.static_violations(body), [], body)

    def test_clock_environment_and_builtins(self):
        for body, reason in (('  return __builtin_ia32_rdtsc() & 1 ? 1 : 0;', 'reserved names or compiler builtins'),
                             ('  return std::chrono::steady_clock::now().time_since_epoch().count() & 1;',
                              'randomness or the clock'),
                             ('  return clock() & 1;', 'randomness or the clock'),
                             ('  return std::getenv("X") ? 1 : 0;', 'the environment'),
                             ('  thread_local int n = 0;\n  return ++n;', 'static or shared state'),
                             ('  asm("nop");\n  return 0;', 'inline assembly'),
                             ('  _Pragma("once") return 0;', 'reserved names or compiler builtins')):
            self.assertIn(reason, gate.static_violations(body), body)

    def test_validation_run_bodies_pass(self):
        """Bodies from the validation run (2026-10-27) that compiled: none breaks a rule."""
        for body in (
                '  if (c.on_pv)\n    return 0;\n  if (c.history > 2000 || c.threatened || c.attacks)\n    return -1;\n'
                '  if (c.history < -1000 && c.quiet_moves >= 8 && c.move_number >= 6)\n    return 1;\n  return 0;\n',
                '  int corr = 0;\n  const bool good_history = c.history >= 4000;\n'
                '  const bool tactical = c.threatened && c.attacks;\n'
                '  if ((good_history || tactical) && (c.on_pv || c.depth <= 4)) {\n    corr = -1;\n  }\n'
                '  return corr;\n',
                '  int r = c.base;\n\n  // History as weak evidence: coarse steps so only strong scores matter.\n'
                '  r -= c.history / 3500;\n  if (c.on_pv) r -= 1;\n'
                '  if (c.entry_bound == 1 && c.entry_depth >= c.depth - 1 && !c.on_pv) r += 1;\n'
                '  if (r < 1) r = 1;\n  if (r > c.depth - 1) r = c.depth - 1;\n  return r - c.base;\n',
                '  int r = c.base * 4;\n  int n = c.quiet_moves > 0 ? c.quiet_moves : 1;\n'
                '  int pos = c.move_number * 16 / n;\n  if (pos >= 12) r += 2;\n  else if (pos <= 5) r -= 1;\n'
                '  if (r < 4) r = 4;\n  if (r > 4 * c.depth) r = 4 * c.depth;\n  return (r + 2) / 4 - c.base;\n'):
            self.assertEqual(gate.static_violations(body), [], body)


# A preprocessed unit as `-E` writes it (line markers, comments gone), for
# the fake runner: searcher.cpp's own lines around the included header.
def fake_preprocessed(tree, header_text, leak=''):
    root = Path(tree).as_posix()
    text = f'# 1 "{root}/src/search/searcher.cpp"\nint before;\n# 1 "{root}/{PATH}" 1\n'
    text += '\n'.join(line if not line.strip().startswith('//') else '' for line in header_text.split('\n'))
    return text + f'\n# 3 "{root}/src/search/searcher.cpp" 2\nint strength = {leak or "LmrCorrectionStrength"};\n'


class FakeRunner:
    """The gate's runner without builds: each step's answer is set by the test.
    Trees are real folders (the guard reads them back); preprocessing is faked."""

    def __init__(self, work, built=True, perft=('a', 'b'), suites=True, benches=None):
        self.work = Path(work)
        self.built, self.perft_out, self.suites_ok = built, list(perft), suites
        self.benches = list(benches or [{'nodes': '1', 'signature': 's'}] * 2)
        self.calls = []
        self.leak = ''  # what the fake preprocessor puts outside the region for a candidate tree
        self.write_hook = None  # (path, text) -> text, to fake a runner that writes something else

    head = '0123456789abcdef0123456789abcdef01234567'  # what the fake repository's refs resolve to

    def resolve(self, ref):
        return self.head

    def read(self, commit, path):
        return FILE

    def tree(self, commit, files, name):
        self.calls.append(('tree', name))
        d = self.work / name
        files = dict({PATH: FILE, 'src/search/searcher.cpp': '#include "search/lmr_table.hpp"\n'}, **files)
        for path, text in files.items():
            (d / path).parent.mkdir(parents=True, exist_ok=True)
            (d / path).write_text(self.write_hook(path, text) if self.write_hook else text, encoding='utf-8',
                                  newline='\n')
        return d

    def read_file(self, tree, path):
        return (Path(tree) / path).read_text(encoding='utf-8')

    def snapshot(self, tree):
        return gate.Runner.snapshot(self, tree)

    def configure(self, tree, stats=False):
        self.calls.append(('configure',))
        return True, 'log', tree / 'build'

    def preprocess(self, build, units):
        self.calls.append(('preprocess',))
        tree = Path(build).parent
        leak = self.leak if tree.name != 'baseline' else ''
        return {'src/search/searcher.cpp': fake_preprocessed(tree, self.read_file(tree, PATH), leak)}

    def build(self, tree, stats=False):
        self.calls.append(('build', stats))
        return self.built, 'log', tree / ('build-stats' if stats else 'build')

    def perft(self, engine):
        self.calls.append(('perft',))
        return self.perft_out

    def suites(self, build):
        self.calls.append(('suites',))
        return self.suites_ok, 'suite log'

    def compiler_version(self):
        return 'fake c++ 1.0'

    def bench(self, engine):
        self.calls.append(('bench',))
        return self.benches.pop(0)

    def run(self, cmd, cwd=None, timeout=None):
        return 0, ('stats: 100 reduced searches, 5 re-searched at full depth (5.0%)\nstats: mean reduction 1.500 plies\n'
                   'stats: LMR rule ran at 200 sites, fired at 30, changed the reduction at 20\n')


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def gate(self, body='  return 1;', setup=None, **kw):
        runner = FakeRunner(self.tmp.name, **kw)
        base = runner.tree('HEAD', {}, 'baseline')
        reference = gate.make_reference(runner, 'lmr', base, base / 'build', ['a', 'b'])
        runner.calls = []
        if setup:
            setup(runner)
        return gate.run_gate(runner, 'HEAD', 'lmr', body, reference, 't'), runner

    def test_pass(self):
        result, runner = self.gate()
        self.assertTrue(result.passed)
        self.assertEqual(result.step, 'done')
        self.assertEqual([c[0] for c in runner.calls],
                         ['tree', 'configure', 'preprocess', 'build', 'perft', 'suites', 'bench', 'bench'])

    def test_a_body_that_closes_its_function_stops_at_the_static_step(self):
        """The gate refuses it before writing a tree or building anything (owner, 2026-10-27)."""
        result, runner = self.gate(body='  return 0;\n}\nconstexpr int evolve_extra(const LmrContext& c) {\n'
                                        '  return c.depth;')
        self.assertFalse(result.passed)
        self.assertEqual(result.step, 'static')
        self.assertIn('leaves the function', result.detail)
        self.assertEqual(runner.calls, [])

    def test_preprocessed_check_catches_what_the_rules_miss(self):
        """A body whose effect reaches code outside the region (the audit's %:define) fails before
        any build, even with the static rules switched off."""
        real = gate.static_violations
        gate.static_violations = lambda body: []
        try:
            result, runner = self.gate(body='  return 0;\n%:define LmrCorrectionStrength 640\n',
                                       setup=lambda r: setattr(r, 'leak', '640'))
        finally:
            gate.static_violations = real
        self.assertEqual((result.passed, result.step), (False, 'preprocessed'))
        self.assertIn("'int strength = 640;'", result.detail)
        self.assertNotIn(('build', False), runner.calls)

    def test_guard_reads_the_written_tree(self):
        """The guard checks the file as written, not text rebuilt from the baseline: a runner that
        writes something else outside the body, or touches another file, is caught."""
        def outside(r):
            r.write_hook = lambda path, text: text.replace('int after();', 'int after(); int sneaky = 1;')
        result, _ = self.gate(setup=outside)
        self.assertEqual((result.passed, result.step), (False, 'guard'))
        self.assertIn('outside region', result.detail)

        def other_file(r):
            real_tree = r.tree

            def tree(commit, files, name):
                d = real_tree(commit, files, name)
                (d / 'src' / 'search' / 'searcher.cpp').write_text('int changed;\n', encoding='utf-8')
                return d
            r.tree = tree
        result, _ = self.gate(setup=other_file)
        self.assertEqual((result.passed, result.step), (False, 'guard'))
        self.assertIn('src/search/searcher.cpp', result.detail)

    def test_outside_lines(self):
        root = '/w/cand-1'
        pre = ('# 1 "/w/cand-1/src/a.cpp"\nint a;\n# 1 "/w/cand-1/src/search/lmr_table.hpp" 1\n'
               'h1\nh2\nBODY1\nBODY2\nh5\n# 2 "/w/cand-1/src/a.cpp" 2\n\nint b = "/w/cand-1/x";\n')
        lines, included = gate.outside_lines(pre, root, 'src/search/lmr_table.hpp', (3, 4))
        self.assertTrue(included)
        self.assertEqual(lines, [('<tree>/src/a.cpp', 'int a;'), ('<tree>/src/search/lmr_table.hpp', 'h1'),
                                 ('<tree>/src/search/lmr_table.hpp', 'h2'), ('<tree>/src/search/lmr_table.hpp', 'h5'),
                                 ('<tree>/src/a.cpp', 'int b = "<tree>/x";')])
        self.assertFalse(gate.outside_lines('# 1 "/w/cand-1/src/b.cpp"\nint x;\n', root,
                                            'src/search/lmr_table.hpp', (3, 4))[1])
        self.assertEqual(gate.preprocess_command({'command': 'c++ -DX -I/t/src -O2 -o a.o -c /t/src/a.cpp',
                                                  'directory': '/t/b', 'file': '/t/src/a.cpp'}),
                         ['c++', '-DX', '-I/t/src', '-O2', '/t/src/a.cpp', '-E'])

    def test_perft_count_ignores_timing(self):
        # Found by the first dry run: the last line (nps) varies, the count does not.
        out = 'nodes 197281\ntime 0.0011 s\nnps 175641915\n'
        self.assertEqual(gate.perft_count(out), 'nodes 197281')
        self.assertEqual(gate.perft_count(out.replace('0.0011', '0.0042').replace('175641915', '46971666')),
                         'nodes 197281')
        self.assertIsNone(gate.perft_count('error\n'))

    def test_static_stops_before_building(self):
        result, runner = self.gate(body='  return int(0.5);')
        self.assertEqual((result.passed, result.step), (False, 'static'))
        self.assertEqual(runner.calls, [])

    def test_each_later_step_stops_the_gate(self):
        for kw, step in (({'built': False}, 'build'), ({'perft': ('a', 'c')}, 'perft'), ({'suites': False}, 'suites'),
                         ({'benches': [{'nodes': '1', 'signature': 's'}, {'nodes': '1', 'signature': 't'}]},
                          'determinism')):
            result, _ = self.gate(**kw)
            self.assertEqual((result.passed, result.step), (False, step), kw)


class RunnerTests(unittest.TestCase):
    """The real Runner's commands and text handling, with its processes recorded, not run."""

    def recording(self, **kw):
        runner = gate.Runner('.', '.', **kw)
        runner.commands = []

        def run(cmd, cwd=None, timeout=None):
            runner.commands.append(cmd)
            return 0, '100% tests passed, 0 tests failed out of 6\n'
        runner.run = run
        return runner

    def test_suites_must_all_run(self):
        """A renamed or dropped suite fails the gate (audit-1 U-11): ctest exits 0 when nothing matches."""
        self.assertTrue(gate.suites_passed(0, 'x\n100% tests passed, 0 tests failed out of 6\n'))
        self.assertFalse(gate.suites_passed(0, 'No tests were found!!!\n'))
        self.assertFalse(gate.suites_passed(0, '100% tests passed, 0 tests failed out of 5\n'))
        self.assertFalse(gate.suites_passed(8, 'No tests were found!!!\n'))
        self.assertFalse(gate.suites_passed(8, '83% tests passed, 1 tests failed out of 6\n'))
        runner = self.recording()
        self.assertTrue(runner.suites(Path('b'))[0])
        cmd = runner.commands[0]
        self.assertIn('--no-tests=error', cmd)
        self.assertEqual(cmd[-1], '^(search|pruning|params|tt|ordering|no_alloc)$')

    def test_the_compiler_is_named(self):
        """The gate builds with the configured compiler, not CMake's default (audit-1 U-17)."""
        runner = self.recording(compiler='g++-12')
        runner.configure(Path('t'))
        self.assertIn('-DCMAKE_CXX_COMPILER=g++-12', runner.commands[0])
        cfg = json.loads((Path(__file__).resolve().parent / 'config.json').read_text(encoding='utf-8'))
        self.assertTrue(cfg['compiler'])

    def test_prompt_states_the_region_signature(self):
        """The prompt shows the function as the header declares it: constexpr (audit-1 U-17)."""
        repo = Path(__file__).resolve().parents[2]
        header = (repo / PATH).read_text(encoding='utf-8')
        context = (Path(__file__).resolve().parent / 'prompts' / 'context.md').read_text(encoding='utf-8')
        signature = next(line for line in header.split('\n') if 'lmr_correction(const LmrContext& c)' in line)
        self.assertEqual(signature, 'constexpr int lmr_correction(const LmrContext& c) {')
        self.assertIn(signature, context.split('\n'))

    def test_resolve_gives_the_full_hash(self):
        runner = gate.Runner(Path(__file__).resolve().parents[2], '.')
        head = runner.resolve('HEAD')
        self.assertRegex(head, r'^[0-9a-f]{40}$')
        self.assertEqual(runner.resolve(head[:12]), head)
        with self.assertRaises(subprocess.CalledProcessError):
            runner.resolve('no-such-ref-anywhere')

    def test_text_is_utf8_whatever_the_locale(self):
        """The region file holds non-ASCII text (a section sign); the runner reads, writes and decodes
        UTF-8 explicitly, not in the locale's encoding (audit-1 S-6)."""
        runner = gate.Runner(Path(__file__).resolve().parents[2], '.')
        code, out = runner.run([sys.executable, '-c',
                                "import sys; sys.stdout.buffer.write('\\u00a7 \\u2212'.encode())"])
        self.assertEqual((code, out), (0, '§ −'))
        self.assertIn('§5.2', runner.read('HEAD', PATH))
        with tempfile.TemporaryDirectory() as tmp:
            runner.work = Path(tmp)
            text = '// § −\n' + runner.read('HEAD', PATH)
            tree = runner.tree('HEAD', {PATH: text}, 't')
            self.assertEqual((tree / PATH).read_bytes(), text.encode('utf-8'))
            self.assertEqual(runner.read_file(tree, PATH), text)


def find_compiler():
    for name in (os.environ.get('FORK_GCC_CXX'), os.environ.get('FORK_CLANG_CXX'), 'g++', 'clang++', 'c++'):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


@unittest.skipUnless(find_compiler(), 'no C++ compiler on PATH (source scripts/env.sh)')
class RealPreprocessTests(unittest.TestCase):
    """The preprocessed comparison on the engine's real searcher.cpp, with a real compiler's `-E`
    (the audit's %:define candidate, which compiles: A6 U-2)."""

    def unit_lines(self, tmp, name, body):
        repo = Path(__file__).resolve().parents[2]
        tree = Path(tmp) / name
        shutil.copytree(repo / 'src', tree / 'src')
        if body is not None:
            text = (tree / PATH).read_text(encoding='utf-8')
            (tree / PATH).write_text(regions.replace_body(text, 'lmr', body), encoding='utf-8', newline='\n')
        (tree / 'build').mkdir()
        source = (tree / 'src' / 'search' / 'searcher.cpp').as_posix()
        (tree / 'build' / 'compile_commands.json').write_text(json.dumps([{
            'directory': (tree / 'build').as_posix(), 'file': source,
            'arguments': [find_compiler(), '-std=c++20', '-DNDEBUG', '-DFORK_EVAL_BOOTSTRAP',
                          '-I' + (tree / 'src').as_posix(), '-o', 'searcher.o', '-c', source]}]), encoding='utf-8')
        runner = gate.Runner(repo, tmp, jobs=1)
        text = runner.preprocess(tree / 'build', None)['src/search/searcher.cpp']
        lines = gate.body_lines(runner.read_file(tree, PATH), 'lmr')
        return gate.outside_lines(text, tree, PATH, lines)

    def test_digraph_define_changes_searcher_cpp(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, included = self.unit_lines(tmp, 'baseline', None)
            self.assertTrue(included)
            self.assertIn(('<tree>/src/search/searcher.cpp', 'const int correction = rule * LmrCorrectionStrength / 64;'),
                          base)
            same, _ = self.unit_lines(tmp, 'rule', '  if (c.on_pv)\n    return 0;\n  // a longer body\n'
                                                   '  return c.history < -4000 ? 1 : 0;')
            self.assertIsNone(gate.first_difference(base, same))
            leak, _ = self.unit_lines(tmp, 'digraph', '  static_cast<void>(c);\n  return 0;\n'
                                                      '%:define LmrCorrectionStrength 640\n')
            diff = gate.first_difference(base, leak)
            self.assertIsNotNone(diff)
            self.assertIn('rule * 640 / 64', diff)


class ProxyTests(unittest.TestCase):
    LABELS = [{'bm': 'e2e4', 'ce': 20}, {'bm': 'd2d4', 'ce': -50}, {'bm': 'g1f3', 'ce': 0}, {'bm': 'c2c4', 'ce': 900}]

    def test_measure(self):
        answers = [proxies.Answer('e2e4', 30, 9), proxies.Answer('e2e4', -50, 10),
                   proxies.Answer('g1f3', None, 8), proxies.Answer('c2c4', -900, 9)]
        r = proxies.measure(answers, self.LABELS)
        self.assertEqual(r.positions, 4)
        self.assertAlmostEqual(r.agreement, 0.75)
        # errors 10, 0, the cap (no score), the cap (1800 capped): mean (10 + 0 + 400 + 400) / 4
        self.assertAlmostEqual(r.score_error, 202.5)
        self.assertAlmostEqual(r.depth, 9.0)
        self.assertAlmostEqual(r.fitness(), 0.75 - 0.2025)

    def test_perfect_and_empty(self):
        perfect = proxies.measure([proxies.Answer(r['bm'], r['ce'], 5) for r in self.LABELS], self.LABELS)
        self.assertEqual((perfect.agreement, perfect.score_error), (1.0, 0.0))
        self.assertEqual(proxies.measure([], []).positions, 0)

    def test_descriptors(self):
        out = ('x\nstats: 2000 reduced searches, 10 re-searched at full depth (0.5%)\nstats: mean reduction 1.250 plies\n'
               'stats: LMR rule ran at 4000 sites, fired at 900, changed the reduction at 400\n')
        self.assertEqual(proxies.descriptors(out), (1.25, 0.005, 0.1))
        with self.assertRaises(ValueError):  # a build without the trigger counters
            proxies.descriptors(out.split('stats: LMR rule')[0])
        with self.assertRaises(ValueError):
            proxies.descriptors('nodes 1\n')

    def test_paired_interval(self):
        base = [0.0, 1.0] * 50
        same = proxies.paired_interval(base, base, 1)
        self.assertEqual(same, (0.0, 0.0, 0.0))
        better = proxies.paired_interval([1.0] * 100, base, 1)  # +1 on half the positions
        self.assertAlmostEqual(better[0], 0.5)
        self.assertTrue(0.35 < better[1] < 0.5 < better[2] < 0.65)
        noisy = proxies.paired_interval([1.0, 0.0] * 50, [0.0, 1.0] * 50, 1)  # +1, -1 alternately: no gain
        self.assertTrue(noisy[1] < 0 < noisy[2])
        self.assertEqual(proxies.paired_interval([1.0], base, 1), None)  # different position sets
        self.assertEqual(proxies.paired_interval(base, base[::-1], 5), proxies.paired_interval(base, base[::-1], 5))
        r = proxies.measure([proxies.Answer('e2e4', 10, 5), proxies.Answer('d2d4', None, 5)],
                            [{'bm': 'e2e4', 'ce': 30}, {'bm': 'e2e4', 'ce': 0}])
        self.assertEqual(r.per_position, [0.98, -0.4])
        self.assertAlmostEqual(r.fitness(), sum(r.per_position) / 2)

    def test_parallel_proxies_keep_the_order(self):
        class Fake:
            def __init__(self, path):
                pass

            def answer(self, fen, nodes):
                return proxies.Answer(fen, 0, 1)

            def close(self):
                pass
        real = proxies.Engine
        proxies.Engine = Fake
        try:
            labels = [{'fen': f'm{i}', 'bm': f'm{i}' if i % 3 else 'x', 'ce': 0} for i in range(23)]
            one = proxies.run_proxies('e', labels, 1)
            four = proxies.run_proxies('e', labels, 1, jobs=4)
        finally:
            proxies.Engine = real
        self.assertEqual(one, four)
        self.assertEqual(one.per_position[:3], [0.0, 1.0, 1.0])

    def test_load_positions_splits(self):
        with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as f:
            for i, split in enumerate(['evolve', 'holdout', 'evolve']):
                f.write(json.dumps({'id': i, 'fen': 'x', 'bm': 'e2e4', 'ce': 0, 'split': split}) + '\n')
        try:
            self.assertEqual(len(proxies.load_positions(f.name)), 2)
            self.assertEqual(len(proxies.load_positions(f.name, 'holdout')), 1)
            self.assertEqual(len(proxies.load_positions(f.name, None)), 3)
        finally:
            os.unlink(f.name)


class PositionSplitTests(unittest.TestCase):
    """Audit-1 U-13: the held-out split is drawn per game, for batches made from now on."""

    def test_every_position_of_a_game_shares_its_split(self):
        import random
        import positions
        games = [f'b11pg{g:04d}' for g in range(600) for _ in range(10)]  # 10 positions per game
        splits = positions.assign_splits(games, random.Random(20261111))
        self.assertEqual(len(splits), 600)
        self.assertEqual(splits, positions.assign_splits(games, random.Random(20261111)))  # seeded
        held = sum(s == 'holdout' for s in splits.values())
        self.assertTrue(70 <= held <= 130, held)  # one game in six: 100 expected
        rows = [{'game': g, 'split': splits[g]} for g in games]
        by_game = {}
        for r in rows:
            by_game.setdefault(r['game'], set()).add(r['split'])
        self.assertTrue(all(len(s) == 1 for s in by_game.values()))

    def test_the_committed_set_is_unchanged(self):
        """The committed batches keep their per-position split (no game field): 4,794 evolve, 940 held out."""
        path = Path(__file__).resolve().parent / 'positions.jsonl'
        rows = proxies.load_positions(path, None)
        self.assertEqual((len(proxies.load_positions(path)), len(proxies.load_positions(path, 'holdout'))),
                         (4794, 940))
        self.assertFalse(any('game' in r for r in rows))


class PopulationTests(unittest.TestCase):
    def setUp(self):
        self.pop = population.Population(':memory:')

    def tearDown(self):
        self.pop.close()

    def test_elites_keep_the_fitter(self):
        a = self.pop.add(1, 'i', 'r', None, 'residual', 'a', '')
        b = self.pop.add(1, 'i', 'r', None, 'residual', 'b', '')
        c = self.pop.add(1, 'i', 'r', None, 'residual', 'c', '')
        self.assertTrue(self.pop.offer_elite('i', a, (1.0, 0.01), 0.5))
        self.assertFalse(self.pop.offer_elite('i', b, (1.1, 0.011), 0.4))  # same cell, less fit
        self.assertTrue(self.pop.offer_elite('i', c, (1.1, 0.011), 0.6))
        self.assertTrue(self.pop.offer_elite('i', b, (2.0, 0.01), 0.4))  # another cell
        self.assertEqual(len(self.pop.elites('i')), 2)
        self.assertEqual(self.pop.best('i'), (c, 0.6))

    def test_inputs_used_is_a_grid_axis(self):
        self.assertEqual(population.inputs_used('  return c.depth > 8 ? c.base : 0;'), '-')
        self.assertEqual(population.inputs_used('  if (c.threatened && c.history < 0) return 1;\n  return 0;'),
                         'move')
        self.assertEqual(population.inputs_used('  return c.historyx + c.phase + c.on_pv;'), 'node')
        self.assertEqual(population.inputs_used('  return c.attacks + c.piece + c.branch_share;'), 'move+iteration')
        a = self.pop.add(1, 'i', 'r', None, 'residual', '  return c.history < 0;', '')
        b = self.pop.add(1, 'i', 'r', None, 'residual', '  return c.phase < 8;', '')
        self.assertTrue(self.pop.offer_elite('i', a, (1.0, 0.01), 0.5))
        self.assertTrue(self.pop.offer_elite('i', b, (1.0, 0.01), 0.4))  # same behaviour, other inputs
        self.assertEqual(sorted(cell for cell, _, _ in self.pop.elites('i')), ['4:0:move', '4:0:node'])

    def test_parents_are_seeded(self):
        ids = [self.pop.add(1, 'i', 'r', None, 'residual', str(k), '') for k in range(6)]
        for k, cid in enumerate(ids):
            self.pop.offer_elite('i', cid, (k * 1.0, 0.0), 0.1 * k)
        self.assertEqual(self.pop.choose_parents('i', 2, 7), self.pop.choose_parents('i', 2, 7))
        self.assertEqual(self.pop.choose_parents('empty', 2, 7), [])

    def test_reseed_and_events(self):
        a = self.pop.add(1, 'good', 'r', None, 'residual', 'a', '')
        b = self.pop.add(1, 'bad', 'r', None, 'residual', 'b', '')
        self.pop.offer_elite('good', a, (1.0, 0.0), 0.9)
        self.pop.offer_elite('bad', b, (3.0, 0.0), 0.1)
        self.pop.reseed('bad', 'good')
        self.assertEqual(self.pop.best('bad'), (a, 0.9))
        self.pop.log(1, 'critic_rejected', {'id': b, 'reasons': 'float'})
        self.assertEqual(len(self.pop.events('critic_rejected')), 1)


class AgentTests(unittest.TestCase):
    def test_parse_proposal(self):
        p = agents.parse_proposal('MODE: full\nRATIONALE: because.\n```cpp\n  return 0;\n```\n')
        self.assertEqual((p.mode, p.rationale, p.body), ('full', 'because.', '  return 0;\n'))
        self.assertIsNone(agents.parse_proposal('no code here'))
        self.assertIsNone(agents.parse_proposal('MODE: sideways\n```cpp\nx\n```'))

    def test_parse_verdict(self):
        self.assertTrue(agents.parse_verdict('VERDICT: accept\nREASONS: fine').accept)
        v = agents.parse_verdict('VERDICT: reject\nREASONS: float')
        self.assertEqual((v.accept, v.reasons), (False, 'float'))
        self.assertFalse(agents.parse_verdict('hmm').accept)

    def test_stream_parsing_refuses_tools(self):
        def stream(tools, mcp, subtype='success'):
            return '\n'.join([
                json.dumps({'type': 'system', 'subtype': 'init', 'tools': tools, 'mcp_servers': mcp}),
                json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'x'}]}}),
                json.dumps({'type': 'result', 'subtype': subtype, 'is_error': subtype != 'success', 'result': 'MODE: residual',
                            'usage': {'input_tokens': 2, 'output_tokens': 5, 'cache_creation_input_tokens': 100,
                                      'cache_read_input_tokens': 50}})])
        r = agents.parse_stream(stream([], []))
        self.assertEqual((r.text, r.tokens), ('MODE: residual', 157))
        for bad in (stream(['WebFetch'], []), stream([], [{'name': 'x'}]), stream([], [], 'error_max_turns'), 'junk'):
            with self.assertRaises(RuntimeError):
                agents.parse_stream(bad)

    def test_cli_command_has_no_tools(self):
        cmd = agents.CliAgent().command()
        self.assertEqual(cmd[cmd.index('--tools') + 1], '""')
        for flag in ('--disallowedTools', '--strict-mcp-config', '--safe-mode', '--no-session-persistence'):
            self.assertIn(flag, cmd)

    def test_budget(self):
        now = [0.0]
        b = agents.Budget(tokens=100, candidates=3, seconds=60, clock=lambda: now[0])
        self.assertIsNone(b.exhausted())
        b.spend(tokens=100)
        self.assertEqual(b.exhausted(), 'token budget')
        b = agents.Budget(tokens=100, candidates=3, seconds=60, clock=lambda: now[0])
        b.spend(candidates=3)
        self.assertEqual(b.exhausted(), 'candidate budget')
        b = agents.Budget(tokens=100, candidates=3, seconds=60, clock=lambda: now[0])
        now[0] = 61
        self.assertEqual(b.exhausted(), 'time budget')

    def test_prompts_fill(self):
        for role in agents.ROLES:
            text = agents.prompt_for(role, mode='residual', parents='P', statistics='S', history='H',
                                     insights='I', protected=3, rationale='R', body='B', every=3, candidates='C')
            self.assertIn('Clean room', text, role)
            self.assertNotIn('{mode}', text, role)


class MatchTests(unittest.TestCase):
    def test_parse_and_passes(self):
        out = ('Elo: -40.00 +/- 30.00, nElo: -50 +/- 37\nGames: 100, Wins: 20, Losses: 31, Draws: 49\n'
               'Elo: -12.50 +/- 20.00, nElo: -15 +/- 25\nGames: 400, Wins: 110, Losses: 124, Draws: 166\n')
        r = match.parse(out)
        self.assertEqual((r.games, r.wins, r.losses, r.draws), (400, 110, 124, 166))
        self.assertTrue(r.passes(0))          # -12.5 + 20 > 0
        self.assertFalse(r.passes(10))
        self.assertIsNone(match.parse('nothing'))


class OrchestratorTests(unittest.TestCase):
    """One generation through the whole funnel, with fakes for builds, engines and the proxies."""

    def run_generation(self, tmp, held):
        """Generation 1 with stub agents; fake proxies by candidate: scoring-set fitness 0.30 (the
        baseline), 0.31 and 0.29, and held-out fitness from `held` (candidate -> fitness)."""
        labels = Path(tmp) / 'p.jsonl'
        labels.write_text(json.dumps({'id': 0, 'fen': 'x', 'bm': 'e2e4', 'ce': 0, 'split': 'evolve'}) + '\n' +
                          json.dumps({'id': 1, 'fen': 'y', 'bm': 'e2e4', 'ce': 0, 'split': 'holdout'}) + '\n')
        cfg = json.loads((Path(__file__).resolve().parent / 'config.json').read_text(encoding='utf-8'))
        import re
        self.assertIsNone(re.search(r'/Users/(?!Public/)', json.dumps(cfg)))  # names no user
        self.assertNotIn('/home/', json.dumps(cfg))
        cfg.update({'positions': str(labels), 'per_island': 1, 'critic_audit_share': 1.0, 'dashboard_mirror': None,
                    'islands': ['proposer_aggressive', 'proposer_cautious', 'proposer_stats', 'explorer'],
                    'match': dict(cfg['match'], games=0)})
        scoring = {1: 0.30, 2: 0.31, 3: 0.29}

        def fake(engine, labels, nodes, jobs=1):
            cid = int(Path(engine).parent.parent.name.split('-')[1])
            f = held[cid] if labels[0]['split'] == 'holdout' else scoring[cid]
            return proxies.ProxyResult(1, f, 0.0, 9.0, [f])
        real = proxies.run_proxies
        proxies.run_proxies = fake
        try:
            runner = FakeRunner(Path(tmp) / 'work', benches=[{'nodes': '1', 'signature': 's'}] * 20)
            loop = orchestrator.Loop(cfg, Path(tmp) / 'run', orchestrator.dry_run_agent(), runner)
            loop.start()
            runner.built = True
            # The build stub fails for the body that does not compile.
            real_build = runner.build

            def build(tree, stats=False):
                if not stats and tree.name == 'cand-4':
                    return False, 'syntax error', tree / 'build'
                return real_build(tree, stats)
            runner.build = build
            self.assertIsNone(loop.generation(1))
        finally:
            proxies.run_proxies = real
        statuses = {r[0]: r[1] for r in loop.pop.db.execute('SELECT id, status FROM candidates')}
        return loop, statuses

    def test_one_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop, statuses = self.run_generation(tmp, {1: 0.40, 2: 0.42, 3: 0.39})
            pop = loop.pop
            self.assertEqual(statuses[1], 'scored')            # the baseline
            self.assertEqual(statuses[2], 'promoted (match skipped)')  # 0.31 >= 0.30 + 0.005, held out 0.42 > 0.40
            self.assertEqual(statuses[3], 'scored')            # cautious: 0.29
            self.assertEqual(statuses[4], 'gate:build')        # the body that does not compile
            self.assertTrue(statuses[5].startswith('critic_rejected (audited: gate:static'))  # floating point
            self.assertEqual(len(pop.events('critic_rejected')), 1)
            self.assertEqual(len(pop.events('analyst')), 0)    # every 3 generations
            self.assertEqual(pop.best()[0], 2)                 # the fittest so far
            self.assertEqual(len(pop.events('improved')), 1)   # 0.31 beyond the baseline's 0.30; 0.29 is not
            self.assertEqual(loop.best_generation, 1)
            self.assertEqual(len(pop.events('promoted')), 1)   # the match is skipped (games = 0)
            record = json.loads(pop.get(2)['proxies'])
            self.assertAlmostEqual(record['holdout_fitness'], 0.42)
            self.assertAlmostEqual(record['holdout_low'], 0.02)
            page = (Path(tmp) / 'run' / 'dashboard.html').read_text(encoding='utf-8')
            for section in ('Islands', 'Top candidates', 'Promotions', 'Critic rejections (1)',
                            'Gate failures and malformed replies', 'Analyst summaries', 'Tokens',
                            'Held-out fitness', '0.4200'):
                self.assertIn(section, page)
            self.assertIn('floating point breaks the hot-path rules', page)  # the critic's reason
            loop.close()

    def test_promotion_needs_the_held_out_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop, statuses = self.run_generation(tmp, {1: 0.40, 2: 0.40, 3: 0.39})  # no held-out gain
            self.assertEqual(statuses[2], 'not confirmed on the held-out set: not promoted')
            self.assertEqual(len(loop.pop.events('promoted')), 0)
            detail = json.loads(loop.pop.events('not_promoted')[0][2])
            self.assertEqual((detail['reason'], detail['holdout_low']), ('not confirmed on the held-out set', 0.0))
            loop.close()


def loop_cfg(tmp):
    """The committed config with a two-position set, three islands of one proposal each, no match."""
    labels = Path(tmp) / 'p.jsonl'
    labels.write_text(json.dumps({'id': 0, 'fen': 'x', 'bm': 'e2e4', 'ce': 0, 'split': 'evolve'}) + '\n' +
                      json.dumps({'id': 1, 'fen': 'y', 'bm': 'e2e4', 'ce': 0, 'split': 'holdout'}) + '\n',
                      encoding='utf-8')
    cfg = json.loads((Path(__file__).resolve().parent / 'config.json').read_text(encoding='utf-8'))
    cfg.update({'positions': str(labels), 'per_island': 1, 'critic_audit_share': 0.0, 'dashboard_mirror': None,
                'islands': ['proposer_aggressive', 'proposer_cautious', 'explorer'],
                'match': dict(cfg['match'], games=0)})
    return cfg


def fake_proxies(engine, labels, nodes, jobs=1):
    return proxies.ProxyResult(1, 0.3, 0.0, 9.0, [0.3])


class Crash(BaseException):
    """A process killed mid-run: not an Exception, so nothing in the loop catches it."""


class LoopFailureTests(unittest.TestCase):
    """Audit-1 U-7: one failure must not end a run, and a run can be resumed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.real = proxies.run_proxies
        proxies.run_proxies = fake_proxies
        self.slept = []

    def tearDown(self):
        proxies.run_proxies = self.real
        self.tmp.cleanup()

    def loop(self, agent=None, resume=False, runner=None):
        runner = runner or FakeRunner(Path(self.tmp.name) / 'work', benches=[{'nodes': '1', 'signature': 's'}] * 99)
        return orchestrator.Loop(loop_cfg(self.tmp.name), Path(self.tmp.name) / 'run',
                                 agent or orchestrator.dry_run_agent(), runner, resume=resume, sleep=self.slept.append)

    def statuses(self, loop):
        return [r[0] for r in loop.pop.db.execute('SELECT status FROM candidates ORDER BY id')]

    def test_one_failed_agent_call_does_not_end_the_run(self):
        class Flaky(agents.StubAgent):
            def ask(self, role, prompt):
                if role == 'critic':
                    raise RuntimeError('claude -p failed for critic: rate limited')  # CliAgent.ask's error
                return super().ask(role, prompt)
        loop = self.loop(Flaky(orchestrator.dry_run_agent().script))
        loop.start()
        self.assertIsNone(loop.generation(1))  # 3 errors: under the 4 gate runs the stop needs
        self.assertEqual(self.statuses(loop)[1:], ['error:critic'] * 3)
        self.assertEqual(len(loop.pop.events('error')), 3)
        self.assertEqual(self.slept, [60, 120, 240] * 3)  # agent_retries 3, backoff 60 s doubling
        self.assertEqual(len(loop.pop.events('generation_done')), 1)
        loop.close()

    def test_a_transient_failure_is_retried(self):
        class OnceFlaky(agents.StubAgent):
            failed = False

            def ask(self, role, prompt):
                if not self.failed:
                    OnceFlaky.failed = True
                    raise subprocess.TimeoutExpired('claude', 900)
                return super().ask(role, prompt)
        loop = self.loop(OnceFlaky(orchestrator.dry_run_agent().script))
        loop.start()
        loop.generation(1)
        self.assertEqual(self.slept, [60])
        self.assertEqual(len(loop.pop.events('agent_retry')), 1)
        self.assertEqual(len(loop.pop.events('error')), 0)
        loop.close()

    def test_errors_count_toward_the_gate_failure_stop(self):
        loop = self.loop()
        loop.start()
        loop.cfg.update(per_island=2, critic_audit_share=1.0)  # 6 requests, every one gated

        def broken(*a, **k):
            raise subprocess.TimeoutExpired('fork bench', 600)
        loop.runner.bench = broken  # every gate's bench times out
        stop = loop.generation(1)
        self.assertTrue(stop.startswith('gate failure rate'), stop)
        self.assertIn('error:gate', self.statuses(loop))
        loop.close()

    def test_a_used_run_dir_needs_resume(self):
        loop = self.loop()
        loop.start()
        loop.close()
        with self.assertRaises(orchestrator.RunDirError):
            self.loop()
        with self.assertRaises(orchestrator.RunDirError):
            orchestrator.Loop(loop_cfg(self.tmp.name), Path(self.tmp.name) / 'empty', orchestrator.dry_run_agent(),
                              FakeRunner(Path(self.tmp.name) / 'work'), resume=True)

    def test_restarting_in_the_same_run_dir_resumes(self):
        stub = agents.StubAgent(orchestrator.dry_run_agent().script, tokens_per_reply=10)
        loop = self.loop(stub)
        loop.run(1)
        used = dict(loop.budget.used)
        self.assertEqual(used, {'tokens': 60, 'candidates': 3})  # 3 proposals and 3 critic calls
        loop = self.loop(agents.StubAgent(orchestrator.dry_run_agent().script, tokens_per_reply=10), resume=True)
        loop.run(2)
        pop = population.Population(str(Path(self.tmp.name) / 'run' / 'population.sqlite'))
        self.assertEqual(pop.db.execute("SELECT COUNT(*) FROM candidates WHERE agent = 'baseline'").fetchone()[0], 1)
        self.assertEqual(pop.db.execute('SELECT COUNT(*) FROM candidates WHERE generation = 1').fetchone()[0], 3)
        self.assertEqual(pop.db.execute('SELECT COUNT(*) FROM candidates WHERE generation = 2').fetchone()[0], 3)
        self.assertEqual(loop.budget.used, {'tokens': 120, 'candidates': 6})
        self.assertEqual([json.loads(d)['generation'] for _, _, d in pop.events('resumed')], [2])
        self.assertAlmostEqual(loop.baseline_fitness, 0.3)
        self.assertTrue(loop.baseline_scores)
        pop.close()

    def test_resume_mid_generation(self):
        class Dies(agents.StubAgent):
            def ask(self, role, prompt):
                if role == 'proposer_cautious':
                    raise Crash()
                return super().ask(role, prompt)
        loop = self.loop(Dies(orchestrator.dry_run_agent().script))
        loop.start()
        with self.assertRaises(Crash):
            loop.generation(1)
        loop.close()
        loop = self.loop(resume=True)
        self.assertEqual(loop.run(1), 'generation limit')
        pop = population.Population(str(Path(self.tmp.name) / 'run' / 'population.sqlite'))
        islands = [r[0] for r in pop.db.execute('SELECT island FROM candidates WHERE generation = 1 ORDER BY id')]
        self.assertEqual(islands, ['proposer_aggressive', 'proposer_cautious', 'explorer'])  # each request once
        self.assertEqual([json.loads(d)['first_request'] for _, _, d in pop.events('resumed')], [1])
        self.assertEqual(len(pop.events('generation_done')), 1)
        pop.close()


class RecordingRunner(FakeRunner):
    """A fake runner that records the commit of every read and tree."""

    def __init__(self, work):
        super().__init__(work, benches=[{'nodes': '1', 'signature': 's'}] * 99)
        self.commits = []

    def read(self, commit, path):
        self.commits.append(commit)
        return super().read(commit, path)

    def tree(self, commit, files, name):
        self.commits.append(commit)
        return super().tree(commit, files, name)


class PinnedBaselineTests(unittest.TestCase):
    """Audit-1 U-8: the baseline commit is resolved once and only its hash is used."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.real = proxies.run_proxies, match.run_match
        proxies.run_proxies = fake_proxies

    def tearDown(self):
        proxies.run_proxies, match.run_match = self.real
        self.tmp.cleanup()

    def test_baseline_commit_is_pinned_for_the_run(self):
        runner = RecordingRunner(Path(self.tmp.name) / 'work')
        cfg = loop_cfg(self.tmp.name)
        self.assertEqual(cfg['baseline_commit'], 'HEAD')  # the committed config names a moving ref
        loop = orchestrator.Loop(cfg, Path(self.tmp.name) / 'run', orchestrator.dry_run_agent(), runner)
        loop.start()
        runner.head = 'f' * 40  # a commit made during the run moves HEAD
        loop.generation(1)
        self.assertEqual(set(runner.commits), {FakeRunner.head})
        self.assertEqual(loop.pop.get_meta('baseline_commit'), FakeRunner.head)
        state = json.loads((Path(self.tmp.name) / 'run' / 'state.json').read_text(encoding='utf-8'))
        self.assertEqual(state['baseline_commit'], FakeRunner.head)
        loop.close()
        # A resumed run keeps the pinned hash, wherever the ref points now.
        loop = orchestrator.Loop(cfg, Path(self.tmp.name) / 'run', orchestrator.dry_run_agent(), runner, resume=True)
        self.assertEqual(loop.commit, FakeRunner.head)
        loop.close()

    def test_hand_off_names_the_hash(self):
        cfg = loop_cfg(self.tmp.name)
        cfg['match'] = dict(cfg['match'], games=2)
        match.run_match = lambda *a, **k: match.MatchResult(2, 2, 0, 0, 400.0, 10.0)
        loop = orchestrator.Loop(cfg, Path(self.tmp.name) / 'run', orchestrator.dry_run_agent(),
                                 RecordingRunner(Path(self.tmp.name) / 'work'))
        loop.start()
        cid = loop.pop.add(1, 'proposer_aggressive', 'r', None, 'residual', '  return 1;', '')
        loop.pop.update(cid, proxies=json.dumps({'gain_low': 0.1, 'holdout_low': 0.1}),
                        descriptors=json.dumps([1.0, 0.0, 0.2]))
        loop.promote(1, cid, loop.baseline_fitness + 1)
        text = (Path(self.tmp.name) / 'run' / 'handoff' / f'candidate-{cid}-sprt.txt').read_text(encoding='utf-8')
        self.assertIn(f'git switch -c evolve-{cid} {FakeRunner.head}', text)
        self.assertNotIn('HEAD', text)
        loop.close()


class DashboardTests(unittest.TestCase):
    def test_agent_text_is_escaped(self):
        import dashboard
        with tempfile.TemporaryDirectory() as tmp:
            pop = population.Population(str(Path(tmp) / 'population.sqlite'))
            cid = pop.add(1, 'explorer', 'explorer', None, 'full', '  return 0; // </pre><b>x</b>',
                          '<script>alert(1)</script>')
            pop.update(cid, status='scored', fitness=0.5, proxies=json.dumps({'agreement': 0.5}),
                       descriptors=json.dumps([1.5, 0.01]))
            pop.log(1, 'critic_rejected', {'id': cid, 'reasons': '<img src=x onerror=alert(1)>', 'audited': False})
            pop.close()
            page = dashboard.render(tmp).read_text(encoding='utf-8')
        self.assertNotIn('<script>alert', page)
        self.assertNotIn('<img src=x', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertIn('&lt;/pre&gt;&lt;b&gt;x&lt;/b&gt;', page)


if __name__ == '__main__':
    unittest.main()
