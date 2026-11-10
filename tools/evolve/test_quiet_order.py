# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests of the ordering pilot's additions to the heuristic-discovery
harness (ideas.md idea 23, owner 2026-11-09): two-compiler gating, the
fixed-depth node fitness and its equivalence guard, the baseline self-check,
the candidate and reply logs, and the replay modes. Builds and engines are
faked (test_evolve.FakeRunner), except RealTwoCompilerTests, which compiles
Fork's real move selector with TCEC's g++ 11 and clang++-19 when both are
installed (WSL Ubuntu-22.04).

    python3 -m unittest discover -s tools/evolve -p 'test_*.py'
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agents  # noqa: E402
import depth_nodes  # noqa: E402
import gate  # noqa: E402
import orchestrator  # noqa: E402
import regions  # noqa: E402
from test_evolve import PATH_Q, FakeRunner, OrderFakeRunner  # noqa: E402

TWO = ('g++', 'clang++-19')


class TwoCompilerGateTests(unittest.TestCase):
    """Every candidate must pass the gate with both compilers (owner, 2026-11-09)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def gate(self, body='  return 1;', **kw):
        runner = FakeRunner(self.tmp.name, compilers=TWO, **kw)
        base = runner.tree('HEAD', {}, 'baseline')
        reference = gate.make_reference(runner, 'lmr', base, ['a', 'b'])
        runner.calls.clear()
        return gate.run_gate(runner, 'HEAD', 'lmr', body, reference, 't'), runner, reference

    def test_both_compilers_run_every_check(self):
        result, runner, reference = self.gate()
        self.assertTrue(result.passed)
        self.assertEqual(sorted(reference.units), [0, 1])  # each compiler's own preprocessed reference
        steps = [c[0] for c in runner.calls]
        self.assertEqual(steps, ['tree'] + ['configure', 'generate', 'preprocess', 'syntax'] * 2 +
                         ['build', 'perft', 'suites', 'bench', 'bench'] * 2)

    def test_a_failure_with_either_compiler_refuses(self):
        for compiler in TWO:
            for failing, step in (('syntax', 'build'), ('build', 'build'), ('perft', 'perft'), ('suites', 'suites')):
                result, _, _ = self.gate(fail={compiler: failing})
                self.assertEqual((result.passed, result.step, result.compiler), (False, step, compiler),
                                 (compiler, failing))
                self.assertIn(f'[{compiler}]', result.detail)

    def test_the_compilers_must_agree_on_bench(self):
        benches = [{'nodes': '1', 'signature': 's'}] * 2 + [{'nodes': '2', 'signature': 't'}] * 2
        result, _, _ = self.gate(benches=benches)
        self.assertEqual((result.passed, result.step), (False, 'determinism'))
        self.assertIn('the compilers disagree', result.detail)

    def test_fault_injected_one_compiler_gate_passes_what_two_refuse(self):
        """The check can fail: a gate that ran only the first compiler would pass a candidate
        clang++-19 refuses."""
        runner = FakeRunner(self.tmp.name, compilers=TWO, fail={'clang++-19': 'syntax'})
        base = runner.tree('HEAD', {}, 'baseline')
        reference = gate.make_reference(runner, 'lmr', base, ['a', 'b'])
        runner.variants = lambda: FakeRunner.variants(runner)[:1]
        self.assertTrue(gate.run_gate(runner, 'HEAD', 'lmr', '  return 1;', reference, 't').passed)

    def test_the_snapshot_leaves_out_every_compilers_build_folder(self):
        """Found by the Linux end-to-end run: the second compiler's build-1/ counted as a tree
        difference, so every candidate stopped at the guard."""
        tree = Path(self.tmp.name) / 'tree'
        for rel in ('src/a.cpp', 'build/x', 'build-1/y', 'build-stats/z', '.cache/c', 'builder/kept'):
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            (tree / rel).write_text('x', encoding='utf-8')
        self.assertEqual(sorted(gate.Runner('.', '.').snapshot(tree)), ['builder/kept', 'src/a.cpp'])

    def test_the_build_names_its_targets_and_the_generated_headers(self):
        runner = gate.Runner('.', '.', jobs=2, compilers=list(TWO))
        commands = []
        runner.run = lambda cmd, cwd=None, timeout=None: (commands.append(cmd), (0, ''))[1]
        second = runner.variants()[1]
        self.assertEqual((second.compiler, second.build_name), ('clang++-19', 'build-1'))
        second.build(Path('t'))
        self.assertIn('-DCMAKE_CXX_COMPILER=clang++-19', commands[0])
        self.assertIn(str(Path('t') / 'build-1'), commands[0])
        self.assertEqual(commands[1][-3:], ['fork', 'fork_tests', 'fork_alloc_test'])
        second.generate(Path('t') / 'build-1')
        self.assertEqual(commands[2][-2:], ['--target', 'fork_build_id'])


def tcec_compilers():
    """g++ 11 and clang++-19 (TCEC's, in WSL Ubuntu-22.04), or None."""
    gxx, clang = shutil.which('g++'), shutil.which('clang++-19')
    if not gxx or not clang:
        return None
    version = subprocess.run([gxx, '-dumpversion'], capture_output=True, text=True).stdout.strip()
    return (gxx, clang) if version.split('.')[0] == '11' else None


@unittest.skipUnless(tcec_compilers(), "TCEC's g++ 11 and clang++-19 not installed (WSL Ubuntu-22.04 has them)")
class RealTwoCompilerTests(unittest.TestCase):
    """The gate's compile step (`-fsyntax-only` with the unit's own command) on Fork's real move
    selector: a quiet_score body clang++-19 accepts and GCC 11 rejects (a call to a library
    function that is not constexpr, the kind audit-1 U-17 found) is refused by g++."""

    def syntax(self, compiler, body):
        repo = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / 'tree'
            shutil.copytree(repo / 'src', tree / 'src')
            if body is not None:
                text = (tree / PATH_Q).read_text(encoding='utf-8')
                (tree / PATH_Q).write_text(regions.replace_body(text, 'quiet_order', body), encoding='utf-8',
                                           newline='\n')
            (tree / 'build').mkdir()
            source = (tree / 'src' / 'search' / 'move_selector.cpp').as_posix()
            (tree / 'build' / 'compile_commands.json').write_text(json.dumps([{
                'directory': (tree / 'build').as_posix(), 'file': source,
                'arguments': [compiler, '-std=c++20', '-O2', '-Wall', '-Wextra', '-Wpedantic', '-Wshadow', '-Werror',
                              '-DNDEBUG', '-DFORK_EVAL_BOOTSTRAP', '-I' + (tree / 'src').as_posix(), '-o',
                              'move_selector.o', '-c', source]}]), encoding='utf-8')
            return gate.Runner(repo, tmp, jobs=1).syntax(tree / 'build', ['src/search/move_selector.cpp'])

    def test_gcc_rejects_what_clang_accepts(self):
        gxx, clang = tcec_compilers()
        body = '  return std::div(s.butterfly, 3).quot;'
        self.assertEqual(gate.static_violations(body), [])  # nothing for the static rules to see
        self.assertEqual(self.syntax(clang, body), '')
        failure = self.syntax(gxx, body)
        self.assertIn('compiling src/search/move_selector.cpp failed', failure)
        self.assertIn('constexpr', failure)

    def test_the_committed_body_compiles_with_both(self):
        for compiler in tcec_compilers():
            self.assertEqual(self.syntax(compiler, None), '', compiler)


class DepthNodesTests(unittest.TestCase):
    def test_parse_search(self):
        lines = ['info depth 1 seldepth 1 score cp 5 nodes 20 nps 1 pv e2e4',
                 'info depth 2 seldepth 3 score cp 12 lowerbound nodes 70 pv e2e4',
                 'info depth 2 seldepth 3 score mate 4 nodes 90 nps 2 pv d2d4', 'bestmove d2d4 ponder e7e5']
        a = depth_nodes.parse_search(lines, 2)
        self.assertEqual((a.nodes, a.move, a.score), (90, 'd2d4', 'mate 4'))
        with self.assertRaises(RuntimeError):
            depth_nodes.parse_search(lines, 3)

    def test_reduction_and_interval(self):
        base = [100, 200, 300, 400]
        self.assertAlmostEqual(depth_nodes.node_reduction([90, 180, 270, 360], base), 0.1)
        self.assertEqual(depth_nodes.reduction_interval(base, base, 1), (0.0, 0.0, 0.0))
        r, low, high = depth_nodes.reduction_interval([90, 180, 270, 360], base, 1)
        self.assertAlmostEqual(r, 0.1)
        self.assertAlmostEqual(low, 0.1)
        self.assertAlmostEqual(high, 0.1)
        r, low, high = depth_nodes.reduction_interval([50, 250, 290, 410], base, 7)
        self.assertTrue(low <= r <= high and low < high)
        self.assertEqual(depth_nodes.reduction_interval([50, 250, 290, 410], base, 7),
                         depth_nodes.reduction_interval([50, 250, 290, 410], base, 7))  # seeded
        s = depth_nodes.paired_summary([50, 200, 310, 400], base)
        self.assertEqual((s['fewer'], s['equal'], s['more'], s['total']), (1, 2, 1, 960))

    def test_equivalence(self):
        A = depth_nodes.DepthAnswer
        self.assertTrue(depth_nodes.equivalent(A(1, 'e2e4', 'cp 10'), A(9, 'e2e4', 'cp 35'), 25))
        self.assertFalse(depth_nodes.equivalent(A(1, 'e2e4', 'cp 10'), A(9, 'e2e4', 'cp 36'), 25))
        self.assertFalse(depth_nodes.equivalent(A(1, 'e2e4', 'cp 10'), A(9, 'd2d4', 'cp 10'), 25))
        self.assertTrue(depth_nodes.equivalent(A(1, 'e2e4', 'mate 3'), A(9, 'e2e4', 'mate 5'), 25))
        self.assertFalse(depth_nodes.equivalent(A(1, 'e2e4', 'mate 3'), A(9, 'e2e4', 'mate -3'), 25))
        self.assertFalse(depth_nodes.equivalent(A(1, 'e2e4', 'mate 3'), A(9, 'e2e4', 'cp 900'), 25))
        base = [A(1, 'a', 'cp 0'), A(1, 'b', 'cp 0')]
        self.assertEqual(depth_nodes.equivalence_share([A(5, 'a', 'cp 0'), A(5, 'c', 'cp 0')], base, 25), 0.5)

    def test_digest_sample_and_descriptors(self):
        A = depth_nodes.DepthAnswer
        self.assertEqual(depth_nodes.digest([A(1, 'a', 'cp 0')]), depth_nodes.digest([A(1, 'a', 'cp 0')]))
        self.assertNotEqual(depth_nodes.digest([A(1, 'a', 'cp 0')]), depth_nodes.digest([A(2, 'a', 'cp 0')]))
        rows = [{'id': i} for i in range(50)]
        pick = depth_nodes.sample_rows(rows, 10, 3)
        self.assertEqual(pick, depth_nodes.sample_rows(rows, 10, 3))
        self.assertEqual([r['id'] for r in pick], sorted(r['id'] for r in pick))
        self.assertEqual(len(pick), 10)
        self.assertEqual(depth_nodes.sample_rows(rows, 0, 3), rows)
        self.assertEqual(depth_nodes.ordering_descriptors(
            'stats: 1640362 beta cutoffs, 84.6% on the first move, mean cutoff index 0.3579\n'), (0.846, 0.3579))

    def test_parallel_engines_keep_the_order(self):
        class Fake:
            def __init__(self, path, hash_mb=16):
                pass

            def search(self, fen, depth):
                return depth_nodes.DepthAnswer(len(fen), fen, 'cp 0')

            def close(self):
                pass
        real = depth_nodes.DepthEngine
        depth_nodes.DepthEngine = Fake
        try:
            rows = [{'fen': 'x' * (i + 1)} for i in range(11)]
            one = depth_nodes.run_fixed_depth('e', rows, 3)
            three = depth_nodes.run_fixed_depth('e', rows, 3, jobs=3)
        finally:
            depth_nodes.DepthEngine = real
        self.assertEqual([a.row() for a in one], [a.row() for a in three])
        self.assertEqual([a.nodes for a in one], list(range(1, 12)))


# --- the nodes mode through the orchestrator, with fakes ---------------------------------

AGGRESSIVE = ('  int score = s.butterfly;\n  if (s.has_reply) score += s.reply * s.reply_weight / 4;\n'
              '  if (s.has_follow) score += s.follow * s.reply_weight / 4;\n  return score;')


class FakeDepth:
    """depth_nodes.run_fixed_depth by the region body found in the engine's tree: the baseline
    (`return s.butterfly;`) searches 100 nodes per position; `nodes` and `moves` give other
    bodies' answers (default: the baseline's)."""

    def __init__(self, nodes=None, moves=None):
        self.nodes = {k.strip(): v for k, v in (nodes or {}).items()}
        self.moves = {k.strip(): v for k, v in (moves or {}).items()}
        self.calls = []

    def __call__(self, engine, rows, depth, jobs=1, hash_mb=16):
        tree = Path(engine).parent.parent
        body = regions.body((tree / PATH_Q).read_text(encoding='utf-8'), 'quiet_order').strip()
        self.calls.append((tree.name, rows[0]['split'], jobs))
        nodes = self.nodes.get(body, 100)
        move = self.moves.get(body, 'e2e4')
        return [depth_nodes.DepthAnswer(nodes(i) if callable(nodes) else nodes, move, 'cp 10')
                for i in range(len(rows))]


class BuildFails(OrderFakeRunner):
    """The fake build fails for a body that does not compile (`+;`)."""

    def build(self, tree, stats=False):
        built, log, out = super().build(tree, stats)
        if '+;' in self.read_file(tree, self.path):
            return False, 'syntax error', out
        return built, log, out


def nodes_cfg(tmp):
    rows = [{'id': i, 'fen': f'f{i}', 'bm': 'e2e4', 'ce': 0, 'split': 'evolve'} for i in range(6)]
    rows += [{'id': 10 + i, 'fen': f'h{i}', 'bm': 'e2e4', 'ce': 0, 'split': 'holdout'} for i in range(3)]
    labels = Path(tmp) / 'p.jsonl'
    labels.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    cfg = json.loads((Path(__file__).resolve().parent / 'config_quiet_order.json').read_text(encoding='utf-8'))
    cfg.update({'positions': str(labels), 'per_island': 1, 'critic_audit_share': 1.0, 'dashboard_mirror': None,
                'full_share': 0.3333, 'depth': 3, 'proxy_jobs': 2})
    cfg['guard'] = dict(cfg['guard'], calibration=[{'name': 'plus zero', 'body': '  return s.butterfly + 0;'}])
    return cfg


class NodesLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.real = depth_nodes.run_fixed_depth
        self.loops = []

    def tearDown(self):
        depth_nodes.run_fixed_depth = self.real
        for loop in self.loops:  # a failed test leaves its database open (Windows cannot delete it then)
            try:
                loop.close()
            except Exception:  # noqa: BLE001 (already closed)
                pass
        self.tmp.cleanup()

    def loop(self, fake, run='run', agent=None, cfg=None):
        depth_nodes.run_fixed_depth = fake
        runner = BuildFails(Path(self.tmp.name) / run / 'work', benches=[{'nodes': '1', 'signature': 's'}] * 99)
        loop = orchestrator.Loop(cfg or nodes_cfg(self.tmp.name), Path(self.tmp.name) / run,
                                 agent or orchestrator.dry_run_agent('quiet_order'), runner, sleep=lambda s: None)
        self.loops.append(loop)
        return loop

    def statuses(self, loop):
        return {cid: status for cid, status in loop.pop.db.execute('SELECT id, status FROM candidates')}

    def test_one_generation(self):
        fake = FakeDepth({'return s.butterfly + 0;': lambda i: 100 + (i == 0), AGGRESSIVE: 80})
        loop = self.loop(fake)
        loop.start()
        # The self-check: the baseline twice on each set, the second time on one more process.
        self.assertEqual(fake.calls[:4], [('cand-1', 'evolve', 2), ('cand-1', 'evolve', 3),
                                          ('cand-1', 'holdout', 2), ('cand-1', 'holdout', 3)])
        self.assertEqual(len(loop.pop.events('self_check')), 2)
        self.assertAlmostEqual(loop.guard_threshold, 0.98)  # the calibration body is equivalent everywhere
        self.assertIsNone(loop.generation(1))
        s = self.statuses(loop)
        self.assertEqual(s, {1: 'scored', 2: 'calibration', 3: 'promoted (match skipped)', 4: 'gate:build',
                             5: 'critic_rejected (audited: gate:static)'})
        record = json.loads(loop.pop.get(3)['proxies'])
        self.assertAlmostEqual(record['gain'], 0.2)
        self.assertEqual((record['total'], record['holdout_total']), (480, 240))
        self.assertAlmostEqual(record['holdout_gain'], 0.2)
        self.assertTrue(record['guard_passed'])
        self.assertEqual(len(loop.pop.events('improved')), 1)
        self.assertEqual(loop.pop.best()[0], 3)
        # The logs: every candidate once, every agent call in order.
        logged = [json.loads(line) for line in (Path(self.tmp.name) / 'run' / 'candidates.jsonl').read_text(
            encoding='utf-8').splitlines()]
        self.assertEqual([c['id'] for c in logged], [2, 1, 3, 4, 5])
        third = logged[2]
        self.assertEqual((third['agent'], third['body'], third['measured']['digest']),
                         ('proposer_aggressive', AGGRESSIVE + '\n', record['digest']))
        self.assertNotIn('per_position', third['measured'])
        self.assertEqual(logged[3]['gate']['step'], 'build')
        replies = [json.loads(line) for line in (Path(self.tmp.name) / 'run' / 'replies.jsonl').read_text(
            encoding='utf-8').splitlines()]
        self.assertEqual([r['role'] for r in replies], ['proposer_aggressive', 'critic', 'proposer_cautious', 'critic',
                                                         'explorer', 'critic'])
        loop.close()

    def test_the_guard_refuses_a_different_search(self):
        """Fewer nodes but other best moves: refused, not placed, not a gate failure."""
        fake = FakeDepth({AGGRESSIVE: 50}, {AGGRESSIVE: 'd2d4'})
        loop = self.loop(fake)
        loop.start()
        loop.generation(1)
        self.assertEqual(self.statuses(loop)[3], 'guard: not equivalent')
        self.assertEqual(loop.pop.best()[0], 1)  # still the baseline
        self.assertNotIn(3, [c for _, c, _ in loop.pop.elites('proposer_aggressive')])
        done = json.loads(loop.pop.events('generation_done')[0][2])
        self.assertEqual((done['gate_runs'], done['gate_failures']), (3, 2))  # the build and the audited float
        self.assertEqual(len(loop.pop.events('guard_refused')), 1)
        loop.close()

    def test_the_self_check_stops_a_run_whose_counts_do_not_repeat(self):
        class Drifts(FakeDepth):
            def __call__(self, engine, rows, depth, jobs=1, hash_mb=16):
                answers = super().__call__(engine, rows, depth, jobs, hash_mb)
                if len(self.calls) == 2:
                    answers[4] = depth_nodes.DepthAnswer(101, 'e2e4', 'cp 10')
                return answers
        loop = self.loop(Drifts())
        with self.assertRaisesRegex(RuntimeError, 'self-check failed on the generation set: 1 positions differ'):
            loop.start()
        loop.close()

    def run_logged(self):
        fake = FakeDepth({'return s.butterfly + 0;': 101, AGGRESSIVE: 80})
        loop = self.loop(fake)
        loop.run(1)
        return fake

    def test_replay_reproduces_every_candidate_and_detects_a_difference(self):
        fake = self.run_logged()
        source = Path(self.tmp.name) / 'run'
        replay = self.loop(fake, 'replay', agents.ReplayAgent(source / 'replies.jsonl'))
        replay.run(1)
        self.assertEqual(replay.agent.mismatches, [])
        rows, ok = orchestrator.compare_outcomes(orchestrator.candidate_outcomes(source / 'population.sqlite'),
                                                 orchestrator.candidate_outcomes(Path(self.tmp.name) / 'replay' /
                                                                                 'population.sqlite'))
        self.assertTrue(ok, rows)
        self.assertEqual(len(rows), 5)
        # Fault injection: the same log replayed by an engine that counts one node more for
        # the aggressive body must not compare equal.
        other = self.loop(FakeDepth({'return s.butterfly + 0;': 101, AGGRESSIVE: 81}), 'replay2',
                          agents.ReplayAgent(source / 'replies.jsonl'))
        other.run(1)
        rows, ok = orchestrator.compare_outcomes(orchestrator.candidate_outcomes(source / 'population.sqlite'),
                                                 orchestrator.candidate_outcomes(Path(self.tmp.name) / 'replay2' /
                                                                                 'population.sqlite'))
        self.assertFalse(ok)
        self.assertEqual([r[0] for r in rows if not all(r[1:])], [3])

    def test_replay_notes_a_prompt_that_differs(self):
        self.run_logged()
        source = Path(self.tmp.name) / 'run'
        agent = agents.ReplayAgent(source / 'replies.jsonl')
        agent.ask('proposer_aggressive', 'another prompt')
        self.assertEqual(agent.mismatches, [{'call': 1, 'role': 'proposer_aggressive',
                                             'logged_role': 'proposer_aggressive', 'prompt_matches': False}])

    def test_replay_of_chosen_candidates(self):
        fake = self.run_logged()
        source = Path(self.tmp.name) / 'run'
        loop = self.loop(fake, 'only3', agents.ReplayAgent(source / 'replies.jsonl'))
        rows, ok = orchestrator.replay_candidates(loop, source, [3])
        self.assertTrue(ok, rows)
        self.assertEqual([r[0] for r in rows], [1, 3])
        loop = self.loop(FakeDepth({AGGRESSIVE: 79}), 'only3b', agents.ReplayAgent(source / 'replies.jsonl'))
        rows, ok = orchestrator.replay_candidates(loop, source, [3])
        self.assertFalse(ok)

    def test_resume_restores_the_nodes_state(self):
        fake = self.run_logged()
        loop = orchestrator.Loop(nodes_cfg(self.tmp.name), Path(self.tmp.name) / 'run',
                                 orchestrator.dry_run_agent('quiet_order'),
                                 BuildFails(Path(self.tmp.name) / 'run' / 'work'), resume=True)
        self.loops.append(loop)
        depth_nodes.run_fixed_depth = fake
        g, first = loop.restore()
        self.assertEqual((g, first), (2, 0))
        self.assertAlmostEqual(loop.guard_threshold, 0.98)
        self.assertEqual([a.nodes for a in loop.baseline_answers], [100] * 6)
        self.assertEqual(loop.best_nodes, [80] * 6)
        loop.close()

    def test_prompts_are_the_regions(self):
        text = agents.prompt_for('proposer_cautious', region='quiet_order', mode='residual', parents='P',
                                 statistics='S', history='H', insights='I')
        self.assertIn('constexpr int quiet_score(const QuietScoreInputs& s) {', text)
        self.assertIn('Clean room', text)
        for field in ('{mode}', '{parents}', '{statistics}', '{history}', '{insights}'):
            self.assertNotIn(field, text)
        critic = agents.prompt_for('critic', region='quiet_order', mode='full', requested='full', rationale='R',
                                   body='B')
        self.assertNotIn("Fork's measurements", critic)
        # The pilot's first explorer proposal was rejected as "nothing indicates a full replacement was
        # requested": the critic is told the mode its author was asked for.
        self.assertIn('The author was asked for: full mode.', critic)
        self.assertNotIn('{requested}', critic)
        repo = Path(__file__).resolve().parents[2]
        header = (repo / PATH_Q).read_text(encoding='utf-8')
        self.assertIn('constexpr int quiet_score(const QuietScoreInputs& s) {', header.split('\n'))
        committed = regions.body(header, 'quiet_order')
        context = (Path(__file__).resolve().parent / 'prompts' / 'quiet_order' / 'context.md').read_text(
            encoding='utf-8')
        self.assertIn(committed, context)  # the prompt shows the committed body as it is


if __name__ == '__main__':
    unittest.main()
