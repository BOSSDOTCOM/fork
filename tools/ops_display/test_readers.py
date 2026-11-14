# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the display's readers and statistics on fixtures copied from the live files (user names,
addresses and ids replaced), and on empty, truncated and corrupt input.
Run: python -I -B -m unittest discover -s tools/ops_display -p "test_*.py"
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import readers as R  # noqa: E402
import stats  # noqa: E402


def fixture(name):
    with open(os.path.join(HERE, 'fixtures', name), encoding='utf-8') as f:
        return f.read()


def fjson(name):
    return json.loads(fixture(name))


class Times(unittest.TestCase):
    def test_every_time_format_gives_the_same_instant(self):
        want = 1794676740  # 2026-11-14 12:19:00 PM EST = 17:19 UTC
        self.assertEqual(R.utc_minute('2026-11-14 17:19'), want)
        self.assertEqual(R.est_stamp('2026-11-14 12:19 PM EST r8c: stage 0'), want)
        self.assertEqual(R.est_stamp('2026-11-14 12:19:00 PM EST heartbeat'), want)
        self.assertEqual(R.iso('2026-11-14T12:19:00-0500'), want)
        self.assertEqual(R.iso('2026-11-14T17:19:00+0000'), want)
        self.assertEqual(R.iso('2026-11-14T09:19:00.329-08:00'), want)
        self.assertEqual(R.iso('2026-11-14T17:19:00Z'), want)

    def test_midnight_and_noon(self):
        self.assertEqual(R.est_stamp('2026-11-14 12:05 AM EST') + 12 * 3600, R.est_stamp('2026-11-14 12:05 PM EST'))
        self.assertEqual(R.est_stamp('2026-11-14 1:05 PM EST'), R.est_stamp('2026-11-14 01:05 PM EST'))

    def test_bad_times_are_none(self):
        for bad in ('', 'yesterday', '2026-13-40 99:99', None, '2026-11-14T12:19:00'):
            self.assertIsNone(R.iso(bad))
            self.assertIsNone(R.utc_minute(bad) if isinstance(bad, str) else None)
        self.assertIsNone(R.est_stamp('2026-11-14 25:99 PM EST'))
        self.assertIsNone(R.est_stamp(None))


class Statistics(unittest.TestCase):
    """The display's own pentanomial figures must equal the driver's printed lines."""

    def test_matches_every_block_of_a_real_driver_log(self):
        d = R.driver_log(fixture('driver-capped.log'))
        self.assertEqual(len(d['stages']), 8)
        for s in d['stages']:
            got = stats.summary(s['ptnml'])
            self.assertEqual(got['games'], s['games'])
            self.assertAlmostEqual(got['elo'], s['elo'], delta=0.011)
            self.assertAlmostEqual(got['elo_err'], s['elo_err'], delta=0.011)
            self.assertAlmostEqual(got['nelo'], s['nelo'], delta=0.011)
            self.assertAlmostEqual(got['nelo_err'], s['nelo_err'], delta=0.011)
            self.assertAlmostEqual(stats.llr(s['ptnml'], 0, 6), s['llr'], delta=0.011)

    def test_empty_and_one_sided_counts(self):
        self.assertIsNone(stats.summary([0, 0, 0, 0, 0]))
        s = stats.summary([0, 0, 0, 0, 10])
        self.assertIsNone(s['elo'])
        self.assertEqual(s['games'], 20)
        self.assertEqual(stats.llr([0, 0, 0, 0, 0], 0, 6), 0.0)

    def test_add_ignores_malformed_counts(self):
        self.assertEqual(stats.add([[1, 2, 3, 4, 5], [1, 1, 1, 1, 1], 'x', [1, 2], [1, -1, 0, 0, 0], None]), [2, 3, 4, 5, 6])


class DriverLog(unittest.TestCase):
    def test_capped_sprt(self):
        d = R.driver_log(fixture('driver-capped.log'))
        self.assertEqual(d['name'], 'f12-pin-see-stc')
        h = d['header']
        self.assertEqual((h['kind'], h['tc_class'], h['cap'], h['idea'], h['try'], h['futility_after']),
                         ('search', 'stc', 8, 'f12-pin-see', 1, 2))
        self.assertEqual((h['elo0'], h['elo1'], h['alpha'], h['beta']), (0.0, 6.0, 0.05, 0.20))
        last = d['stages'][-1]
        self.assertEqual((last['stage'], last['games'], last['elo'], last['elo_err'], last['llr'], last['lo'], last['hi']),
                         (7, 12800, 1.44, 3.48, -0.32, -1.56, 2.77))
        self.assertEqual(last['ptnml'], [138, 1548, 2986, 1579, 149])
        self.assertEqual(last['run'], 43576284240)
        self.assertEqual(last['merged'] - last['dispatched'], 18 * 60)
        self.assertEqual((d['end']['kind'], d['end']['stage']), ('undecided', 7))
        self.assertTrue(d['end']['text'].startswith('capped (8 of 8 stages'))
        self.assertIsNone(d['flight'])
        self.assertIsNone(d['stopped'])

    def test_rejected_and_futility(self):
        d = R.driver_log(fixture('driver-h0.log'))
        self.assertEqual((d['end']['kind'], d['end']['text'], len(d['stages'])), ('decided', 'H0 accepted', 2))
        self.assertEqual(d['stages'][-1]['elo'], -6.62)
        d = R.driver_log(fixture('driver-futility.log'))
        self.assertTrue(d['end']['text'].startswith('futility stop'))

    def test_fixed_node_screen_has_no_kind(self):
        d = R.driver_log(fixture('driver-screen.log'))
        self.assertIsNone(d['header']['kind'])
        self.assertEqual((d['header']['first_stage'], d['header']['last_stage']), (0, 0))
        self.assertEqual((d['stages'][0]['elo'], d['stages'][0]['elo_err'], d['stages'][0]['games']), (-2.39, 9.02, 1600))
        self.assertEqual(d['end']['kind'], 'undecided')

    def test_in_flight_after_a_resume(self):
        d = R.driver_log(fixture('driver-resume.log'))
        self.assertEqual(d['stages'], [])
        self.assertEqual(d['flight']['stage'], 0)
        self.assertEqual(d['flight']['run'], 43624890824)   # the resumed run, not the first one
        self.assertIsNone(d['end'])

    def test_a_failed_run_stops_and_a_resume_clears_it(self):
        text = fixture('driver-stopping.log')
        first = '\n'.join(text.splitlines()[:3]) + '\n'
        d = R.driver_log(first)
        self.assertIn("ended 'failure'; stopping", d['stopped']['text'])
        self.assertIsNone(d['flight'])
        d = R.driver_log(text)
        self.assertIsNone(d['stopped'])
        self.assertEqual(d['stages'][0]['elo'], -19.78)

    def test_head_to_head_log_is_tolerated(self):
        d = R.driver_log(fixture('driver-h2h.log'))
        self.assertEqual(d['name'], 'tm-variant')
        self.assertEqual(d['stages'], [])
        self.assertTrue(any('picked b' in n for n in d['notes']))

    def test_a_block_cut_mid_write_is_not_used(self):
        text = fixture('driver-capped.log')
        lines = text.splitlines()
        cut = max(i for i, l in enumerate(lines) if 'Ptnml' in l)       # the last block loses its LLR line
        d = R.driver_log('\n'.join(lines[:cut + 1]))
        self.assertEqual(len(d['stages']), 7)
        self.assertEqual(d['stages'][-1]['stage'], 6)

    def test_every_truncation_parses_without_error(self):
        text = fixture('driver-capped.log')
        for n in range(0, len(text), 37):
            d = R.driver_log(text[:n])
            self.assertLessEqual(len(d['stages']), 8)

    def test_empty_and_garbage(self):
        for bad in ('', None, '\x00\x01\x02 not a log', 'Elo: nan +/- nan, nElo: nan +/- nan\n' * 3):
            d = R.driver_log(bad)
            self.assertEqual(d['stages'], [])
            self.assertIsNone(d['name'])

    def test_design_and_outcome(self):
        g = R.design(fjson('design.json'))
        self.assertEqual((g['kind'], g['tc_class'], g['tc'], g['games'], g['cap'], g['elo1'], g['beta']),
                         ('search', 'stc', '8+0.08', 1600, 8, 6.0, 0.2))
        self.assertIsNone(R.design({'x': 1}))
        self.assertIsNone(R.design([1, 2]))
        d = R.driver_log(fixture('driver-capped.log'))
        self.assertEqual(R.outcome('capped\n', d, True)['kind'], 'capped')
        self.assertEqual(R.outcome('H1 accepted', d, True)['kind'], 'passed')
        self.assertEqual(R.outcome('H0 accepted', d, True)['kind'], 'rejected')
        self.assertEqual(R.outcome('futility stop', d, True)['kind'], 'rejected')
        self.assertEqual(R.outcome('complete', d, True)['kind'], 'complete')
        self.assertEqual(R.outcome('stopped (owner, 2026-11-13): not promoted', d, True)['kind'], 'stopped')
        screen = R.driver_log(fixture('driver-screen.log'))
        self.assertEqual(R.outcome('capped', screen, False)['kind'], 'screen')   # a screen's verdict file means nothing
        odd = R.outcome('something new the driver never wrote before', d, True)
        self.assertEqual((odd['kind'], odd['label']), ('other', 'something new the driver never wrote before'))
        stopped = R.driver_log('\n'.join(fixture('driver-stopping.log').splitlines()[:3]) + '\n')
        self.assertEqual(R.outcome('', stopped, False)['kind'], 'interrupted')


class Queue(unittest.TestCase):
    def test_queue_logs(self):
        a = R.queue_log(fixture('queue-a.log'))
        self.assertTrue(all(e['at'] for e in a))
        done = [e['key'] for e in a if e['kind'] == 'done']
        self.assertIn('z26-e2-clamp-ltc', done)
        b = R.queue_log(fixture('queue-b.log'))          # ends with a hand-edited fragment without a newline
        self.assertEqual(b[-1]['key'], '15-r8c-zf2-eplo2-vs-c2')
        failed = R.queue_log('2026-11-12 05:56 PM EST 16-ld-e-decide: failed (exit 1), attempt 2 of 3: retry in 30 minutes; see x\n')
        self.assertEqual(failed[0]['kind'], 'failed')
        self.assertEqual(R.queue_log(''), [])
        self.assertEqual(R.queue_log(None), [])

    def test_item_log_names_the_test_not_the_item(self):
        i = R.item_log(fixture('item-screen.log'))
        self.assertEqual(i['sprt'], 'r8c-fn-r8cc1-vs-r8brft1')
        self.assertFalse(i['waiting'])
        g = R.item_log(fixture('item-gated.log'))
        self.assertTrue(g['waiting'])
        self.assertEqual(R.item_log(''), {'sprt': None, 'waiting': False, 'last_line': ''})

    def test_lane_marker(self):
        m = R.lane_marker(fixture('lane-marker-running.txt'))
        self.assertEqual((m['lane'], m['state'], m['item'], m['drivers'], m['source']),
                         ('B', 'running', '15-r8c-c-cbest-promo-stc', ['r8cc2-promo-stc'], 'watcher'))
        self.assertEqual((m['started'], m['updated']), (1794680240, 1794681753))
        i = R.lane_marker(fixture('lane-marker-idle.txt'))
        self.assertEqual((i['state'], i['item'], i['drivers'], i['since']), ('idle', None, ['f11-root-lean-ltc'], R.est_stamp('2026-11-14 01:26:56 PM EST')))
        chain = R.lane_marker('lane=A\nstate=running\nitem=z70a-f11-root-lean-ltc\nstarted=2026-11-14 01:17:20 PM EST\n')
        self.assertEqual((chain['source'], chain['started'], chain['drivers']), ('chain', R.est_stamp('2026-11-14 01:17:20 PM EST'), []))
        for bad in ('', None, 'lane=A\n', 'state=running\n', 'lane=A\nstate=dancing\n', '\x00\xff', 'lane=A\nstate=runn'):
            self.assertIsNone(R.lane_marker(bad), bad)

    def test_item_kind_and_title(self):
        self.assertEqual(R.item_kind('z70a-f11-root-lean-ltc'), 'LTC')
        self.assertEqual(R.item_kind('z70b-f11-root-lean-retry'), 'retry')
        self.assertEqual(R.item_kind('96c-b6-null-verify-nonreg'), 'non-regression')
        self.assertEqual(R.item_kind('82a0-gauntlet-phase4-head'), 'gauntlet')
        self.assertEqual(R.item_kind('01-r8c-cc1-vs-r8brft1'), 'screen')
        self.assertEqual(R.item_kind('something-else'), 'test')
        codes = R.survey_codes(fixture('survey.md'))
        self.assertIn('B6', codes)
        self.assertEqual(codes['D15'], 'Low-ply history; no history updates from shallow cutoffs')
        ideas = R.ideas_md(fixture('ideas.md'))
        self.assertEqual(ideas[124], 'Root reductions')
        self.assertEqual(ideas[157], 'King-relative offset inputs')
        t = R.item_title('96c-b6-null-verify-nonreg', None, codes, ideas)
        self.assertEqual((t['title'], t['about']), ('B6 null verify', 'NMP verification search'))
        t = R.item_title('89a-i42-cont-inputs-stc', None, codes, ideas)
        self.assertEqual((t['title'], t['about']), ('Idea 42 cont inputs', 'Continuation histories as inputs to the LMR history term'))
        self.assertEqual(R.item_title('15-r8c-c-cbest-promo-stc', 'r8cc2-promo-stc')['title'], 'r8cc2 promotion test')
        t = R.item_title('01-r8c-cc1-vs-r8brft1', 'r8c-fn-r8cc1-vs-r8brft1', codes, ideas)
        self.assertEqual(t['title'], 'r8cc1 against r8brft1')
        t = R.item_title('a-brand-new-kind-of-item')
        self.assertEqual(t['title'], 'A brand new kind of item')

    def test_item_comment(self):
        c = R.item_comment(fixture('item-88a.sh'))
        self.assertTrue(c.startswith("Idea 59's follow-up 1"))
        self.assertLessEqual(len(c), 260)
        self.assertTrue(R.item_comment(fixture('item-01.sh')).startswith("Owner's order 2026-11-14"))
        self.assertIsNone(R.item_comment('#!/usr/bin/env bash\nexit 0\n'))
        self.assertIsNone(R.item_comment(''))

    def test_lane_discovery_from_the_job_and_its_script(self):
        rec = fjson('job-queue-b.json')
        j = R.job_record(rec)
        self.assertEqual((j['name'], j['type'], j['state']), ('night-queue-b', 'github2', 'running'))
        self.assertNotIn('command', j)
        self.assertTrue(R.job_script(rec).endswith('chain-b.sh'))
        self.assertEqual(R.chain_items_folder(fixture('chain-b.sh')), 'items-b')
        self.assertIsNone(R.chain_items_folder('echo no items here'))
        self.assertIsNone(R.job_record({'state': 'running'}))
        self.assertIsNone(R.job_record('x'))
        self.assertIsNone(R.job_script({'command': 'bash x.sh'}))

    def test_jsonl_sources_drop_partial_lines(self):
        ev, bad = R.events(fixture('events.jsonl'))
        self.assertEqual(bad, 0)
        self.assertTrue(all(set(e) == {'at', 'event', 'name', 'type', 'exit_code'} for e in ev))   # no command lines
        self.assertEqual(ev[-2]['name'], 'r8c-a2-upload')
        ev2, bad2 = R.events(fixture('events.jsonl')[:-40])                # the last line cut mid-write
        self.assertEqual((len(ev2), bad2), (len(ev) - 1, 1))
        lg, bad = R.ledger(fixture('ledger.jsonl'))
        self.assertEqual(bad, 0)
        self.assertTrue(all(r['run_id'] and r['at'] for r in lg))
        tr, _ = R.tries(fixture('tries.jsonl'))
        self.assertEqual(tr['f11-root-lean-ltc'], {'idea': 'f11-root-lean', 'kind': 'search', 'tc_class': 'ltc', 'try': 1})
        self.assertEqual(R.events('{"at": 1}\n[1, 2]\nnot json\n'), ([], 2))
        self.assertEqual(R.ledger(''), ([], 0))


class Overview(unittest.TestCase):
    def test_default_net(self):
        self.assertEqual(R.default_net('set(FORK_NET "${CMAKE_SOURCE_DIR}/nets/r8brft1.fnet" CACHE FILEPATH "x")'), 'r8brft1')
        self.assertIsNone(R.default_net('nothing'))
        self.assertIsNone(R.default_net(None))
        n = R.nets_md(fixture('nets.md'))
        self.assertEqual((n['default'], n['since']), ('r8brft1', '2026-11-11'))
        self.assertEqual([e['name'] for e in n['entries']], ['S512ppr3', 'r8btd90', 'r8brft1'])
        self.assertEqual(R.nets_md(''), {'default': None, 'since': None, 'entries': []})

    def test_gauntlet(self):
        o = R.ordo(fixture('ordo.txt'))
        self.assertEqual((o['rating'], o['error'], o['played']), (3553.7, 22.0, 1400))
        self.assertEqual(o['anchors']['Clover 6.1'], 3639.0)
        self.assertEqual(len(o['anchors']), 7)
        self.assertIsNone(R.ordo('no table'))
        m = R.gauntlet_meta(fixture('gauntlet-meta.txt'))
        self.assertEqual((m['run'], m['commit'], m['book'], m['kind']), ('43492038248', '117d26a', 'balanced', 'gauntlet'))
        self.assertEqual(m['at'], R.iso('2026-11-13T19:25:19Z'))
        old = R.gauntlet_meta(fixture('gauntlet-meta-old.txt'))
        self.assertEqual(len(old['commit']), 7)          # no commit in the title: the run's head
        self.assertIsNone(R.gauntlet_meta(''))
        s = R.gauntlet_summary(fixture('gauntlet-summary.md'))
        self.assertEqual(s['reference'], {'name': 'Stockfish 19', 'rating': 3792, 'elo': -184.0, 'lo': -209.7, 'hi': -160.0})
        self.assertEqual(s['gain'], {'elo': 38.2, 'sd': 9.0})
        self.assertEqual(R.gauntlet_summary(fixture('gauntlet-summary-old.md'))['reference'], None)
        self.assertEqual(R.gauntlet_summary(''), {'reference': None, 'transfer': None, 'gain': None})
        inf = R.gauntlet_summary('- Stockfish 19 (CCRL Blitz 3792, x): Fork 1/400; Elo -900.0, 95% interval -inf to -700.0 (p)')
        self.assertEqual((inf['reference']['lo'], inf['reference']['hi']), (None, -700.0))

    def test_anchor_check(self):
        md = ('| Pooled | 294/800 (36.8%) | 291/800 (36.4%) | -2.8 | 8.3 | -18.6 to +13.7 |\n\n'
              "**Outcome: flagged for the owner's review.** Confirmed: the lower 95% bound is above 0.\n")
        self.assertEqual(R.anchor_check(md), {'outcome': 'flagged', 'gain': -2.8, 'lo': -18.6, 'hi': 13.7})
        ok = '| Pooled | 248.5/800 (31.1%) | 277.5/800 (34.7%) | +28.7 | 9.0 | +10.4 to +45.9 |\n**Outcome: confirmed.** x\n'
        self.assertEqual(R.anchor_check(ok)['outcome'], 'confirmed')
        self.assertIsNone(R.anchor_check('**Outcome: confirmed.**'))
        self.assertIsNone(R.anchor_check(''))

    def test_adoptions(self):
        t = R.transfer(fjson('transfer.json'))
        root = next(x for x in t if x['change'].startswith('Root reductions'))
        self.assertEqual((root['elo'], root['err'], root['test']), (14.94, 6.24, 'root-lmr-ltc'))
        self.assertEqual(root['tests'], ['root-lmr-ltc', 'root-lmr-stc'])    # its earlier STC pass counts as adopted too
        with self.assertRaises(ValueError):
            R.transfer({'adopted': 'no'})
        log = ('a86ddcc 2026-11-13 Search: root reductions adopted on their STC and LTC passes, pre-approved by the owner\n'
               '929f114 2026-11-13 Search: the linear history bonus (D11) adopted on its STC pass at LinearBonusPerPly 125\n'
               '1111111 2026-11-13 Docs: E2 not adopted on its LTC pass\n'
               '2222222 2026-11-12 Docs: E1 (the pass-best stop rule) adopted on its non-regression pass; its SPRTs recorded\n'
               '3333333 2026-11-12 Search: neither adopted on its pass\n')
        a = R.adoptions(log)
        self.assertEqual([x['commit'] for x in a], ['a86ddcc', '929f114'])
        self.assertEqual(a[0]['what'], 'root reductions')
        self.assertEqual(R.adoptions(''), [])

    def test_stack_perf_decisions(self):
        self.assertEqual(R.stack_sum('2026-11-12 x stack-check-1-stc: ProbCut + E1 + B13, sum +18.70'), 18.7)
        self.assertIsNone(R.stack_sum('no figure'))
        p = R.perf_log(fixture('perf-log.md'))
        self.assertEqual((p[0]['date'], p[0]['change']), ('2026-11-12', '+14.7%'))
        self.assertEqual(R.perf_log(''), [])
        md = '# Morning\n## Results\n- x\n## Decisions for the owner\n- 12:15 AM EST: keep it or retarget?\n- ANSWERED (owner): keep\n## Failures\n- none\n'
        self.assertEqual(R.decisions(md), ['12:15 AM EST: keep it or retarget?', 'ANSWERED (owner): keep'])
        self.assertEqual(R.decisions('# no such section'), [])
        self.assertEqual(R.decisions(md[:40]), [])       # read half written: no section yet


class Training(unittest.TestCase):
    def test_gates(self):
        g = R.gates_json(fjson('gates.json'))
        self.assertFalse(g['failed'])                    # although its "legs" text contains FAIL
        self.assertIn('FAIL', fjson('gates.json')['legs'])
        self.assertEqual(g['recall'], {'misjudged': 9, 'of': 900, 'passed': True})
        self.assertEqual([(h['name'], h['ratio'], h['flagged']) for h in g['heldout']],
                         [('4-5 pieces', 0.84, False), ('6-7 pieces', 0.958, False)])
        flagged = fjson('gates.json')
        flagged['heldout']['flagged'] = True
        self.assertEqual(R.gates_json(flagged)['flags'], 1)
        with self.assertRaises(ValueError):
            R.gates_json({'scale': 89})
        with self.assertRaises(ValueError):
            R.gates_json(None)
        older = {'gates_failed': True}                   # an older generation without held-out fields
        self.assertEqual(R.gates_json(older)['heldout'], [])
        t = R.gates_txt(fixture('gates.txt'))
        self.assertEqual(len(t), 10)
        self.assertEqual(t['eplo2'], {'exit': 0, 'flags': 0, 'note': None})
        self.assertEqual(R.gates_txt('c1 invalid\nc2 exit=1 flags=2\njunk\n'),
                         {'c1': {'exit': None, 'flags': 0, 'note': 'invalid'}, 'c2': {'exit': 1, 'flags': 2, 'note': None}})

    def test_bakes_screens_fetch(self):
        b = R.bakes_txt(fixture('bakes.txt'))
        self.assertEqual(b['r8cc1'], {'commit': 'a71dd2d', 'nodes': 5202763, 'signature': 'e086362fa5386067'})
        self.assertIn('r8brft1', b)
        self.assertEqual(R.bakes_txt('r8cc1 short 12 zz\n'), {})
        s = R.results_txt(fixture('screens.txt'))
        one = next(x for x in s if x['name'] == 'r8c-fn-r8ceplo2-vs-r8cc2')
        self.assertEqual((one['elo'], one['elo_err'], one['at']), (13.47, 9.14, R.est_stamp('2026-11-14 12:32 PM EST')))
        self.assertGreaterEqual(len(s), 8)
        r = R.results_txt(fixture('results.txt'))
        self.assertEqual((r[0]['name'], r[0]['elo']), ('i80-early-fn-i801', -1.74))
        self.assertEqual(R.results_txt('2026-11-13 11:49 PM EST half a li'), [])
        f = R.fetch_log(fixture('fetch-main.log'))
        self.assertEqual(f['ended'], 'COMPLETE')
        self.assertEqual((f['quota']['used'], f['quota']['left'], f['quota']['total']), (7.14, 22.86, 30.0))
        self.assertEqual(f['quota']['reset'], R.iso('2026-11-21T00:00:00+00:00'))
        self.assertTrue(f['fetched'])
        self.assertEqual(R.fetch_log(''), {'ended': None, 'quota': None, 'fetched': False})

    def test_kaggle_status_and_refs(self):
        self.assertEqual(R.kaggle_status('owner/fork-retrain-8c-a1 has status "KernelWorkerStatus.RUNNING"'), 'RUNNING')
        self.assertEqual(R.kaggle_status('owner/x has status "complete"'), 'COMPLETE')
        self.assertIsNone(R.kaggle_status('403 Forbidden'))
        self.assertEqual(R.kernel_refs('push owner/fork-retrain-8c-a1 then owner/fork-retrain-8c-a1 and owner/fork-x'),
                         ['owner/fork-retrain-8c-a1', 'owner/fork-x'])
        for path in ('C:/Users/someone/fork-data/8c/gpu-queue.txt', 'C:\\Users\\someone/fork-data', '/c/Users/someone/fork-jobs/x',
                     '~/fork-data/kaggle', '/home/someone/fork-data', 'someone/fork-data/8c', 'see someone/fork-data.'):
            self.assertEqual(R.kernel_refs(path), [], path)             # a piece of a path is never a kernel
        self.assertEqual(R.kernel_refs('status of "owner/fork-retrain-8c-a1": RUNNING'), ['owner/fork-retrain-8c-a1'])
        self.assertEqual(R.kernel_id({'id': 'owner/fork-retrain-8c-a1', 'enable_gpu': True}), 'owner/fork-retrain-8c-a1')
        for bad in ({}, {'id': 5}, {'id': 'no-slash'}, {'id': 'a/b/c'}, None, []):
            self.assertIsNone(R.kernel_id(bad))

    def test_session_record_and_arms(self):
        r = R.retrain_json(fjson('retrain.json'))
        self.assertIn('c1', r['arms'])
        self.assertEqual((r['arms']['c1']['seed'], r['arms']['c1']['valid']), (1, True))
        with self.assertRaises(ValueError):
            R.retrain_json({'runs': []})
        arms = ['c1', 'c2', 'ep1', 'eplo1', 'eplo2', 'i801']
        self.assertEqual(R.arm_of('r8ceplo2', arms), ('eplo', 2))
        self.assertEqual(R.arm_of('r8cc1', arms), ('c', 1))
        self.assertEqual(R.arm_of('r8ci801', arms), ('i80', 1))
        self.assertIsNone(R.arm_of('r8brft1', arms))
        self.assertEqual(R.uho_run(fjson('uho-run.json')), {'name': 'r8cc1', 'ratio': 0.402})
        self.assertIsNone(R.uho_run({'name': 'x'}))
        d = R.ld_decision(fjson('ld-decision.json'))
        self.assertEqual((d['verdict'], d['winner'], d['pooled']['d50']['elo']), ('20k stays (no deeper arm qualifies)', None, -55.74))
        self.assertIsNone(R.ld_decision({}))


class Data(unittest.TestCase):
    def test_generator_log(self):
        d = R.datagen_log(fixture('datagen.log'))
        self.assertEqual((d['seconds'], d['positions'], d['done']), (12240, 29852407, False))
        self.assertEqual(d['rate'], round((29852407 - 29716486) / 60 * 3600))   # the recent rate, not the average
        done = R.datagen_log('30 s: 445 games, 40945 positions, 1357 positions/s\n'
                             'done: 2383060 games, 229475885 positions in 125926.7 s (1822 positions/s)\n')
        self.assertEqual((done['positions'], done['done'], done['rate']), (229475885, True, 0))
        self.assertIsNone(R.datagen_log('Syzygy: tables up to 5 pieces\n'))
        self.assertIsNone(R.datagen_log(''))
        one = R.datagen_log('30 s: 445 games, 40945 positions, 1357 positions/s\n')
        self.assertIsNone(one['rate'])

    def test_part_state_files(self):
        w = R.watchdog(fjson('watchdog.json'))
        self.assertEqual((w['part'], w['running'], w['how']), ('g4c', False, 'ended'))
        self.assertIsNone(R.watchdog({}))
        p = R.part_json(fjson('part.json'))
        self.assertEqual((p['name'], p['net'], p['dir']), ('g4c', 'r8brft1', '~/fork-data/gen4c'))
        self.assertIsNone(R.part_json([]))
        s = R.seal_result(fjson('seal-result.json'))
        self.assertEqual(s['state'], 'sealed')
        self.assertIsNone(R.seal_result({'steps': []}))

    def test_manifests(self):
        m = R.manifest(fjson('manifest-part.json'))
        self.assertEqual((m['run'], m['labeller'], m['positions'], m['unsaved'], m['is_part']),
                         ('g4c', 'r8brft1', 229475885, 104639325, True))
        cut = R.manifest(fjson('manifest-cut.json'))
        self.assertEqual((cut['labeller'], cut['is_part']), ('s512ppr3', False))    # a cut is never added to totals
        self.assertIsNone(R.manifest(fjson('manifest-snapshot.json')))
        running = fjson('manifest-part.json')
        running['generator']['tool'] = 'fork_datagen (snapshot of complete games of a running run)'
        self.assertFalse(R.manifest(running)['is_part'])     # an old-style snapshot: a subset of its part
        f = R.manifest(fjson('manifest-filler.json'))
        self.assertEqual((f['labeller'], f['positions']), ('r8brft1', 106192556))
        with self.assertRaises(ValueError):
            R.manifest('half a file')
        self.assertEqual(R.labeller('bootstrap (material)'), 'material')
        self.assertEqual(R.labeller('bootstrap'), 'bootstrap')
        self.assertIsNone(R.labeller(None))

    def test_cloud(self):
        raw = fjson('gcp-status.json')
        self.assertIn('ip', raw['vm'])
        g = R.gcp_status(raw)
        self.assertNotIn('203.0.113.7', json.dumps(g))   # the address never leaves the reader
        self.assertNotIn('ip', g['vm'])
        self.assertEqual((g['vm']['status'], g['vm']['machine_type'], g['running']), ('RUNNING', 'c2d-highcpu-8', 'filler-g4'))
        self.assertEqual(g['items']['filler-g4']['state'], 'running')
        self.assertEqual(g['vm']['last_start'], R.iso('2026-11-10T17:38:13.329-08:00'))
        self.assertTrue(g['at'])
        with self.assertRaises(ValueError):
            R.gcp_status({'worker': {}})
        down = R.gcp_status({'at': 'x', 'vm': {'status': 'UNKNOWN'}, 'worker': {'error': 'ssh timed out'}})
        self.assertEqual((down['vm']['status'], down['worker_error'], down['items']), ('UNKNOWN', 'ssh timed out', {}))
        null = R.gcp_status({'vm': None, 'worker': None})
        self.assertIsNone(null['running'])
        secret = {'project': 'project-secret-1', 'billing_account': '000000-AAAAAA-BBBBBB', 'ssh_key': 'C:/Users/someone/.ssh/key',
                  'usd_per_hour_running': 0.119, 'usd_per_hour_stopped': 0.0045, 'egress_usd_per_gib': 0.12}
        self.assertEqual(R.gcp_rates(secret), {'usd_per_hour_running': 0.119, 'usd_per_hour_stopped': 0.0045, 'egress_usd_per_gib': 0.12})
        e, bad = R.egress(fixture('egress.jsonl'))
        self.assertEqual((e['pulls'], bad), (4, 0))
        self.assertAlmostEqual(e['usd'], 0.1009, places=3)
        self.assertEqual(R.filler_ok(fixture('filler.ok')), {'chunks': 424, 'positions': 106192556})
        self.assertIsNone(R.filler_ok(''))

    def test_arms(self):
        a = R.arms_log(fixture('arms.log'))
        self.assertEqual((a['tag'], a['seconds'], a['live']), ('ld2', 125094, 3))
        self.assertEqual(a['arms'], {'d20': 93265599, 'd50': 40936453, 'd100': 20920269})
        self.assertIsNone(R.arms_log('2026-11-10 02:55:03 PM EST ld2: ld2-d50: --nodes 50000 (pid 507)\n'))
        self.assertIsNone(R.arms_log(''))


class Machine(unittest.TestCase):
    def test_watchers(self):
        f = R.freezewatch(fixture('freezewatch.log'))
        self.assertEqual(f['stall_count'], 0)
        self.assertGreaterEqual(len(f['samples']), 5)
        self.assertTrue(all(0 < s['commit'] <= 100 and s['avail_mb'] > 0 for s in f['samples']))
        st = R.freezewatch('2026-11-12 04:30:00 PM EST STALL: 45 s without a tick\n2026-11-12 05:00:00 PM EST heartbeat: 1 stall so far; avail 900 MB, commit 97.5%\n')
        self.assertEqual((st['stalls'][0]['seconds'], st['stall_count'], st['samples'][0]['commit']), (45, 1, 97.5))
        self.assertEqual(R.freezewatch(''), {'samples': [], 'stalls': [], 'stall_count': 0})
        w = R.wslcache(fixture('wslcache.log'))
        self.assertEqual(w['limit_mb'], 1536)
        self.assertGreaterEqual(w['drop_count'], 1)
        self.assertIsNone(R.wslcache(''))
        unknown = R.wslcache('2026-11-14 12:14 PM EST dropped: WSL cache 1690 -> ? MB; Windows free 0.92 -> 1.89 GB\n')
        self.assertIsNone(unknown['cache_mb'])
        m = R.memwatch(fixture('memwatch.log'))
        self.assertTrue(m['started'])
        self.assertEqual(m['actions'], [])
        acted = R.memwatch("2026-11-14 01:00 PM EST memwatch3: low memory (900 MB free for 15 minutes): dropped WSL's page cache (1200 MB); free now 2100 MB\n"
                           '2026-11-14 01:20 PM EST memwatch3: low memory: stopped agent job evo-1 (type evolve); restart it when memory allows\n'
                           '2026-11-14 01:40 PM EST memwatch3: ALERT: low memory (800 MB) and nothing stoppable\n')
        self.assertEqual([a['kind'] for a in acted['actions']], ['dropped', 'stopped', 'alert'])

    def test_compile_lock(self):
        c = R.compile_waits(fixture('compile-waits.log'), '2026-11-13')
        self.assertEqual(c['seconds'], 1928)             # the sum that lifted the lock on that day
        self.assertEqual(c['waits'][-1], {'seconds': 161, 'who': 'speed4'})
        self.assertEqual(R.compile_waits(fixture('compile-waits.log'), '2026-11-14')['seconds'], 0)
        self.assertEqual(R.compile_waits('', '2026-11-13'), {'seconds': 0, 'waits': []})


class Preliminary(unittest.TestCase):
    def test_shard_progress_record(self):
        p = R.shard_progress({'sprt': 'x-stc', 'stage': 2, 'shard': 5, 'ptnml': [1, 10, 20, 12, 2], 'finished_games': 90,
                              'at': '2026-11-14T17:19:00+0000'})
        self.assertEqual((p['stage'], p['shard'], p['games'], p['ptnml']), (2, 5, 90, [1, 10, 20, 12, 2]))
        self.assertEqual(R.shard_progress({'stage': 0, 'shard': 0, 'ptnml': [0, 1, 2, 1, 0]})['games'], 8)
        for bad in (None, [], {'stage': 0, 'shard': 0}, {'stage': 0, 'shard': 0, 'ptnml': [1, 2, 3]},
                    {'stage': 0, 'shard': 0, 'ptnml': [1, 2, 3, 4, -1]}, {'stage': 0, 'shard': 0, 'ptnml': [1, 2, 3, 4, 'x']},
                    {'stage': 0, 'shard': 0, 'ptnml': [True, 2, 3, 4, 5]}, {'stage': '0', 'shard': 0, 'ptnml': [1, 2, 3, 4, 5]}):
            with self.assertRaises(ValueError):
                R.shard_progress(bad)


class Robustness(unittest.TestCase):
    """Every text reader must take empty, binary and truncated input without raising."""

    TEXT = [R.driver_log, R.queue_log, R.item_log, R.item_comment, R.survey_codes, R.ideas_md, R.default_net, R.nets_md,
            R.ordo, R.gauntlet_meta, R.gauntlet_summary, R.adoptions, R.stack_sum, R.perf_log, R.decisions, R.gates_txt,
            R.bakes_txt, R.results_txt, R.fetch_log, R.kaggle_status, R.kernel_refs, R.datagen_log, R.filler_ok,
            R.arms_log, R.freezewatch, R.wslcache, R.memwatch, R.chain_items_folder, R.anchor_check, R.lane_marker,
            lambda t: R.events(t), lambda t: R.ledger(t), lambda t: R.tries(t), lambda t: R.egress(t),
            lambda t: R.compile_waits(t, '2026-11-13')]

    def test_text_readers_never_raise(self):
        names = [n for n in os.listdir(os.path.join(HERE, 'fixtures'))]
        samples = ['', '\n', '\x00\xff\xfe' * 50, '{' * 200, 'x' * 5000]
        for n in names:
            t = fixture(n)
            samples += [t, t[:len(t) // 2], t[:len(t) // 3], t[len(t) // 2:], t.replace('\n', '\r\n')]
        for fn in self.TEXT:
            for s in samples:
                fn(s)
            fn(None)

    def test_json_readers_reject_or_ignore_wrong_shapes(self):
        shapes = [None, 1, 'text', [], [1, 2], {}, {'name': 5}, {'vm': 3}, {'state': None}]
        for fn in (R.design, R.job_record, R.job_script, R.watchdog, R.part_json, R.seal_result, R.ld_decision,
                   R.uho_run, R.gcp_rates):
            for s in shapes:
                fn(s)                                    # these return None for what they cannot use
        for fn in (R.gates_json, R.transfer, R.retrain_json, R.manifest, R.gcp_status, R.shard_progress):
            for s in shapes:
                try:
                    fn(s)
                except ValueError:
                    pass                                 # a changed format is reported, never anything else


if __name__ == '__main__':
    unittest.main()
