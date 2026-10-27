"""Unit tests of the heuristic-discovery harness (ideas.md idea 23): regions
and the guard, the gate's rules and order (with a fake runner: no builds),
the proxies' metrics, the population, the agents' parsing and budget, the
match parser, and one orchestrated generation with stub agents and fakes.

    python3 -m unittest discover -s tools/evolve -p 'test_*.py'
"""
import json
import os
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


class FakeRunner:
    """The gate's runner without builds: each step's answer is set by the test."""

    def __init__(self, work, built=True, perft=('a', 'b'), suites=True, benches=None):
        self.work = Path(work)
        self.built, self.perft_out, self.suites_ok = built, list(perft), suites
        self.benches = list(benches or [{'nodes': '1', 'signature': 's'}] * 2)
        self.calls = []

    def read(self, commit, path):
        return FILE

    def tree(self, commit, files, name):
        self.calls.append(('tree', name))
        d = self.work / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def build(self, tree, stats=False):
        self.calls.append(('build', stats))
        return self.built, 'log', tree / ('build-stats' if stats else 'build')

    def perft(self, engine):
        self.calls.append(('perft',))
        return self.perft_out

    def suites(self, build):
        self.calls.append(('suites',))
        return self.suites_ok, 'suite log'

    def bench(self, engine):
        self.calls.append(('bench',))
        return self.benches.pop(0)

    def run(self, cmd, cwd=None, timeout=None):
        return 0, 'stats: 100 reduced searches, 5 re-searched at full depth (5.0%)\nstats: mean reduction 1.500 plies\n'


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def gate(self, body='  return 1;', **kw):
        runner = FakeRunner(self.tmp.name, **kw)
        return gate.run_gate(runner, 'HEAD', 'lmr', body, ['a', 'b'], 't'), runner

    def test_pass(self):
        result, runner = self.gate()
        self.assertTrue(result.passed)
        self.assertEqual(result.step, 'done')
        self.assertEqual([c[0] for c in runner.calls], ['tree', 'build', 'perft', 'suites', 'bench', 'bench'])

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
        out = 'x\nstats: 2000 reduced searches, 10 re-searched at full depth (0.5%)\nstats: mean reduction 1.250 plies\n'
        self.assertEqual(proxies.descriptors(out), (1.25, 0.005))
        with self.assertRaises(ValueError):
            proxies.descriptors('nodes 1\n')

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
                         'history+threatened')
        self.assertEqual(population.inputs_used('  return c.historyx + c.phase;'), 'phase')
        a = self.pop.add(1, 'i', 'r', None, 'residual', '  return c.history < 0;', '')
        b = self.pop.add(1, 'i', 'r', None, 'residual', '  return c.phase < 8;', '')
        self.assertTrue(self.pop.offer_elite('i', a, (1.0, 0.01), 0.5))
        self.assertTrue(self.pop.offer_elite('i', b, (1.0, 0.01), 0.4))  # same behaviour, other inputs
        self.assertEqual(sorted(cell for cell, _, _ in self.pop.elites('i')), ['4:0:history', '4:0:phase'])

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

    def test_one_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            labels = Path(tmp) / 'p.jsonl'
            labels.write_text(json.dumps({'id': 0, 'fen': 'x', 'bm': 'e2e4', 'ce': 0, 'split': 'evolve'}) + '\n')
            cfg = json.loads((Path(__file__).resolve().parent / 'config.json').read_text())
            import re
            self.assertIsNone(re.search(r'/Users/(?!Public/)', json.dumps(cfg)))  # names no user
            self.assertNotIn('/home/', json.dumps(cfg))
            cfg.update({'positions': str(labels), 'per_island': 1, 'critic_audit_share': 1.0, 'dashboard_mirror': None,
                        'islands': ['proposer_aggressive', 'proposer_cautious', 'proposer_stats', 'explorer'],
                        'match': dict(cfg['match'], games=0)})
            fitness = iter([0.30, 0.31, 0.29])
            real = proxies.run_proxies
            proxies.run_proxies = lambda engine, labels, nodes: proxies.ProxyResult(1, next(fitness), 0.0, 9.0)
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
            pop = loop.pop
            statuses = {r[0]: r[1] for r in pop.db.execute('SELECT id, status FROM candidates')}
            self.assertEqual(statuses[1], 'scored')            # the baseline
            self.assertEqual(statuses[2], 'promoted (match skipped)')  # aggressive: 0.31 >= 0.30 + 0.005
            self.assertEqual(statuses[3], 'scored')            # cautious: 0.29
            self.assertEqual(statuses[4], 'gate:build')        # the body that does not compile
            self.assertTrue(statuses[5].startswith('critic_rejected (audited: gate:static'))  # floating point
            self.assertEqual(len(pop.events('critic_rejected')), 1)
            self.assertEqual(len(pop.events('analyst')), 0)    # every 3 generations
            self.assertEqual(pop.best()[0], 2)                 # the fittest so far
            self.assertEqual(len(pop.events('promoted')), 1)   # the match is skipped (games = 0)
            page = (Path(tmp) / 'run' / 'dashboard.html').read_text(encoding='utf-8')
            for section in ('Islands', 'Top candidates', 'Promotions', 'Critic rejections (1)',
                            'Gate failures and malformed replies', 'Analyst summaries', 'Tokens'):
                self.assertIn(section, page)
            self.assertIn('floating point breaks the hot-path rules', page)  # the critic's reason
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
