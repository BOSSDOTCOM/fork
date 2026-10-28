"""Tests of the sharded-SPRT statistics (tools/cloud/sprt_merge.py).

The oracle is fastchess itself: the pentanomial counts, Elo, nElo and LLR it
reported for 18 of Fork's SPRTs (docs/history/phase-3/sprt-log.md, the last
report of each entry). Its figures are rounded to two decimals.

    python3 -m unittest discover -s tools/cloud -p 'test_*.py'
"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sprt_merge as sm  # noqa: E402

# name, bounds [nElo0, nElo1], Ptnml(0-2), Elo, Elo +/-, nElo, nElo +/-, LLR
ORACLE = [
    ('ma-UseQuiesce', [0.0, 5.0], [2, 9, 29, 28, 115], 281.3, 45.45, 334.44, 35.59, 2.96),
    ('ma-UseTT', [0.0, 5.0], [4, 13, 61, 65, 82], 173.76, 29.28, 224.77, 32.1, 2.95),
    ('ma-UseSeeQuiesce', [0.0, 5.0], [315, 508, 1169, 518, 389], 9.47, 7.28, 11.64, 8.94, 2.19),
    ('ma-UsePvs', [0.0, 5.0], [17, 24, 115, 70, 91], 109.83, 23.96, 132.64, 27.04, 2.96),
    ('ma-UseAspiration', [0.0, 5.0], [103, 195, 981, 205, 116], 3.91, 7.6, 6.19, 12.04, 0.49),
    ('adj-check-UsePvs', [0.0, 5.0], [17, 21, 116, 86, 80], 106.94, 22.84, 134.39, 26.92, 2.96),
    ('mb-d5-ordering', [0.0, 5.0], [2, 19, 79, 57, 79], 150.0, 27.07, 196.65, 31.34, 2.95),
    ('mb-UseHistory', [0.0, 5.0], [0, 1, 14, 22, 124], 418.92, 60.19, 624.51, 37.95, 2.96),
    ('mb-tier1', [0.0, 5.0], [0, 1, 9, 26, 123], 439.21, 61.04, 698.69, 38.19, 2.96),
    ('mb-UseSeePrune', [0.0, 5.0], [142, 284, 556, 325, 214], 21.16, 10.08, 25.99, 12.35, 2.95),
    ('mb-tier1-ltc', [0.0, 5.0], [0, 0, 3, 18, 132], 555.67, 80.38, 1093.5, 38.93, 2.96),
    ('ttblend-ltc', [0.0, 3.0], [64, 144, 251, 187, 54], 5.71, 13.79, 7.54, 18.2, 0.21),
    ('rv-failhigh', [-3.0, 0.0], [88, 217, 447, 187, 61], -14.6, 10.75, -20.71, 15.23, -0.95),
    ('rv-futile', [-3.0, 0.0], [92, 186, 402, 204, 116], 11.47, 11.9, 14.69, 15.23, 0.8),
    ('rv-ttrefine', [0.0, 3.0], [50, 102, 171, 110, 67], 14.6, 17.76, 17.74, 21.53, 0.4),
    ('rv-keepexact', [-3.0, 0.0], [224, 502, 956, 494, 224], -0.58, 7.49, -0.76, 9.83, 0.09),
    ('mc-tables', [0.0, 3.0], [179, 464, 1053, 535, 269], 17.46, 7.18, 23.45, 9.63, 2.72),
    ('mc-time', [-3.0, 0.0], [227, 508, 1075, 489, 201], -4.93, 7.09, -6.71, 9.63, -0.65),
]


class StatisticsTests(unittest.TestCase):
    def test_elo_and_nelo_match_fastchess(self):
        for name, _, p, e, e_err, ne, ne_err, _ in ORACLE:
            n, mean, var = sm.moments(p)
            se = math.sqrt(var / n)
            half = (sm.elo(mean + 1.96 * se) - sm.elo(mean - 1.96 * se)) / 2
            self.assertAlmostEqual(sm.elo(mean), e, delta=0.006, msg=name)
            self.assertAlmostEqual(half, e_err, delta=0.006, msg=name)
            self.assertAlmostEqual(sm.nelo(p), ne, delta=0.006, msg=name)
            self.assertAlmostEqual(1.96 * sm.NELO_SCALE / math.sqrt(n), ne_err, delta=0.006, msg=name)

    def test_llr_matches_fastchess_while_undecided(self):
        # Within 0.01: fastchess's own LLR differs slightly from the normal
        # approximation (largest gap 0.008 over these runs). A run that crossed
        # a bound reports the crossing value; those are checked for the
        # decision only.
        for name, b, p, *_, reported in ORACLE:
            value, decision = sm.verdict(p, *b)
            if abs(reported) < 2.94:
                self.assertAlmostEqual(value, reported, delta=0.01, msg=name)
                self.assertEqual(decision, 'continue', name)
            else:
                self.assertEqual(decision, 'H1 accepted', name)

    def test_bounds(self):
        lower, upper = sm.bounds(0.05, 0.05)
        self.assertAlmostEqual(upper, 2.944, places=3)
        self.assertAlmostEqual(lower, -2.944, places=3)


class MergeTests(unittest.TestCase):
    def shard(self, p, **meta):
        base = {'base': 'aaa', 'test': 'bbb', 'tc': '8+0.08', 'hash': '16', 'base_opts': '', 'test_opts': ''}
        base.update(meta)
        return {'ptnml': p, 'finished_games': 2 * sum(p), 'time_losses': 0, 'abnormal': 0, 'status': 'done',
                'meta': base}

    def test_shards_add_up_to_the_whole(self):
        whole = [179, 464, 1053, 535, 269]  # mc-tables
        parts = [[45, 116, 263, 134, 67], [45, 116, 263, 134, 67], [45, 116, 264, 134, 67],
                 [44, 116, 263, 133, 68]]
        self.assertEqual([sum(c) for c in zip(*parts)], whole)
        merged = sm.merge([self.shard(p) for p in parts])
        self.assertEqual(merged['ptnml'], whole)
        self.assertAlmostEqual(sm.llr(merged['ptnml'], 0, 3), 2.72, delta=0.01)

    def test_shards_with_the_same_openings_are_refused(self):
        a = self.shard([1, 2, 3, 2, 1], opening_start='1')
        b = self.shard([1, 2, 3, 2, 1], opening_start='1')
        with self.assertRaises(ValueError):
            sm.merge([a, b])
        b['meta']['opening_start'] = '1251'
        self.assertEqual(sm.merge([a, b])['pairs'], 18)

    def test_shards_on_different_books_are_refused(self):
        a = self.shard([1, 2, 3, 2, 1], opening_start='1', rounds='50', book_sha='aa')
        b = self.shard([1, 2, 3, 2, 1], opening_start='51', rounds='50', book_sha='bb')
        with self.assertRaisesRegex(ValueError, 'book_sha'):
            sm.merge([a, b])
        b['meta']['book_sha'] = 'aa'
        self.assertEqual(sm.merge([a, b])['pairs'], 18)

    def test_adjacent_ranges_merge_intersecting_ones_do_not(self):
        a = self.shard([1, 2, 3, 2, 1], opening_start='1', opening_end='50')
        b = self.shard([1, 2, 3, 2, 1], opening_start='51', opening_end='100')
        self.assertEqual(sm.merge([b, a])['pairs'], 18)
        b['meta']['opening_start'] = '50'
        with self.assertRaisesRegex(ValueError, 'lines 1-50 and 50-100'):
            sm.merge([a, b])

    def test_shards_of_different_tests_are_refused(self):
        with self.assertRaises(ValueError):
            sm.merge([self.shard([1, 2, 3, 2, 1]), self.shard([1, 2, 3, 2, 1], test='ccc')])
        with self.assertRaises(ValueError):
            sm.merge([self.shard([1, 2, 3, 2, 1]), self.shard([1, 2, 3, 2, 1], tc='40+0.4')])

    def test_tables_on_and_off_do_not_mix(self):
        on = self.shard([1, 2, 3, 2, 1], tables='3-4-5', opening_start='1')
        off = self.shard([1, 2, 3, 2, 1], tables='off', opening_start='101')
        with self.assertRaisesRegex(ValueError, 'tables'):
            sm.merge([on, off])
        merged = sm.merge([on, dict(off, meta=dict(off['meta'], tables='3-4-5'))])
        self.assertEqual(merged['meta']['tables'], '3-4-5')
        self.assertIn('Tables: 3-4-5 (both engines)', sm.report(merged, -3, 0))

    # Audit-1 (A6) U-4: the auditor's two cases, which the old merge (equal
    # opening_start only) accepted.
    @staticmethod
    def plan(stage, shards, games):
        """The openings run_shard.sh gives each shard: sprt.yml's (and
        aws_spot_sprt.sh's) per-shard games, run_shard.sh's rounds and start."""
        per = (games + 2 * shards - 1) // (2 * shards) * 2
        rounds = (per + 1) // 2
        return [(1 + (stage * shards + i) * rounds, rounds) for i in range(shards)]

    def staged(self, stage, shards, games, runner='github'):
        return [self.shard([1, 2, 3, 2, 1], opening_start=str(start), rounds=str(rounds), stage=str(stage),
                           shards=str(shards), runner=runner) for start, rounds in self.plan(stage, shards, games)]

    def test_stages_with_a_different_game_count_share_openings(self):
        # Stage 0: 16 x 1,600 games, openings 1-800; stage 1 with games=1088:
        # openings 545-1,088, no start equal to a stage-0 start.
        with self.assertRaises(ValueError):
            sm.merge(self.staged(0, 16, 1600) + self.staged(1, 16, 1088))
        self.assertEqual(sm.merge(self.staged(0, 16, 1600) + self.staged(1, 16, 1600))['shards'], 32)

    def test_aws_and_github_shards_of_one_test_overlap(self):
        # One AWS shard of 5,000 games (openings 1-2,500) and a GitHub stage 1
        # (openings 801-1,600).
        with self.assertRaises(ValueError):
            sm.merge(self.staged(0, 1, 5000, 'aws') + self.staged(1, 16, 1600))

    def test_snapshot_reads_the_last_report(self):
        log = '\n'.join([
            'Started game 1 of 400 (test vs base)',
            'Finished game 1 (test vs base): 1-0 {White mates}',
            'Finished game 2 (base vs test): 0-1 {White loses on time}',
            'Finished game 3 (test vs base): 1/2-1/2 {Draw by 3-fold repetition}',
            'Ptnml(0-2): [1, 2, 3, 2, 1], WL/DD Ratio: 1.00',
            'Finished game 4 (base vs test): 1-0 {White mates}',
            'Ptnml(0-2): [2, 4, 6, 5, 3], WL/DD Ratio: 1.20',
        ])
        s = sm.snapshot(log)
        # Pairs from the games: (1, 2) the test scores 1 + 1 (bin 4); (3, 4)
        # 1/2 + 0 (bin 1). fastchess's last report is kept for comparison.
        self.assertEqual(s['ptnml'], [0, 1, 0, 0, 1])
        self.assertEqual(s['fastchess_ptnml'], [2, 4, 6, 5, 3])
        self.assertEqual((s['pairs'], s['finished_games'], s['time_losses'], s['abnormal']), (2, 4, 1, 0))
        self.assertEqual(sm.snapshot('nothing yet')['ptnml'], [0, 0, 0, 0, 0])

    def test_time_losses_in_fastchess_wording(self):
        # The reason strings of the pinned fastchess (v1.8.2-alpha, the
        # binary in ~/fork-tools/bin, read with `strings` on 2026-10-27):
        # "{} loses on time ({}ms overrun)" and "Engine {} loses on time by
        # {}ms"; disconnects, stalls and illegal moves are counted as abnormal.
        log = '\n'.join([
            'Finished game 1 (test vs base): 0-1 {White loses on time (12ms overrun)}',
            'Finished game 2 (base vs test): 1-0 {Black disconnects}',
            "Finished game 3 (test vs base): 0-1 {White's connection stalls}",
            'Finished game 4 (base vs test): 0-1 {White makes an illegal move}',
        ])
        s = sm.snapshot(log)
        self.assertEqual((s['finished_games'], s['time_losses'], s['abnormal']), (4, 1, 3))

    def test_a_shard_that_ends_early_is_short(self):
        self.assertEqual(sm.final_status('done', 2, {'rounds': '50'}), 'short')
        self.assertEqual(sm.final_status('done', 50, {'rounds': '50'}), 'done')
        self.assertEqual(sm.final_status('interrupted', 2, {'rounds': '50'}), 'interrupted')
        self.assertEqual(sm.final_status('failed', 50, {'rounds': '50'}), 'failed')

    def test_report_lists_planned_and_played_pairs_per_shard(self):
        a = self.shard([1, 2, 3, 2, 1], stage='0', shard='1', rounds='50', opening_start='51', runner='github')
        b = self.shard([0, 1, 0, 1, 0], stage='0', shard='0', rounds='50', opening_start='1', runner='github',
                       fastchess_exit='139')
        b['status'] = 'failed'
        text = sm.report(sm.merge([a, b]), -3, 0)
        self.assertIn('  stage 0 shard 0 (github): failed, pairs 2 of 50 planned, fastchess exit 139\n'
                      '  stage 0 shard 1 (github): done, pairs 9 of 50 planned\n', text)

    def test_pairs_count_only_when_both_games_are_done(self):
        # Concurrency finishes games out of order; game 6 is still running.
        log = '\n'.join([
            'Finished game 2 (base vs test): 1/2-1/2 {Draw by 3-fold repetition}',
            'Finished game 5 (test vs base): 1-0 {White mates}',
            'Finished game 1 (test vs base): 0-1 {Black mates}',
            'Finished game 4 (base vs test): 0-1 {Black mates}',
            'Finished game 3 (test vs base): 1/2-1/2 {Draw by fifty moves rule}',
        ])
        # (1, 2): 0 + 1/2 (bin 1); (3, 4): 1/2 + 1 (bin 3); (5, 6) unfinished.
        self.assertEqual(sm.pairs_from_games(log), [0, 1, 0, 1, 0])


if __name__ == '__main__':
    unittest.main()
