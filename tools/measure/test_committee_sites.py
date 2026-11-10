# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/committee_sites.py: its own shard decoder against
python-chess's replay, the trainer's filter, the top-set threshold and draw,
the labeller's protocol and resumption, the bench check and the error ratio.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import io
import json
import random
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import chess

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'datagen'))

import committee_sites as cs  # noqa: E402
import verify_games as vg  # noqa: E402

NIBBLE = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}
ROOK_RIGHT = {chess.H1: chess.BB_H1, chess.A1: chess.BB_A1, chess.H8: chess.BB_H8, chess.A8: chess.BB_A8}


def encode_game(start, moves, scores, result):
    """A viriformat game (verify_games.decode_board's layout): the start board,
    a castling rook written as code 6, then each move's code and score, the terminator."""
    occ, nibbles = 0, []
    for sq in range(64):
        p = start.piece_at(sq)
        if p is None:
            continue
        occ |= 1 << sq
        code = NIBBLE[p.piece_type]
        if p.piece_type == chess.ROOK and sq in ROOK_RIGHT and start.castling_rights & ROOK_RIGHT[sq]:
            code = 6
        nibbles.append(code | (8 if p.color == chess.BLACK else 0))
    packed = bytearray(16)
    for k, n in enumerate(nibbles):
        packed[k // 2] |= n << (4 * (k % 2))
    ep = 64 if start.ep_square is None else start.ep_square
    out = struct.pack('<Q', occ) + bytes(packed)
    out += bytes([(0 if start.turn == chess.WHITE else 128) | ep, start.halfmove_clock])
    out += struct.pack('<H', start.fullmove_number) + struct.pack('<h', 0) + bytes([result, 0])
    board = start.copy()
    for move, score in zip(moves, scores):
        out += struct.pack('<Hh', vg.code_of(board, move), score)
        board.push(move)
    return out + struct.pack('<Hh', 0, 0)


def reference_kept(start, moves, scores, result, game):
    """The kept positions by python-chess: saved, |score| <= 20,000, not in check, no capture or promotion."""
    out, board = [], start.copy()
    for ply, (move, score) in enumerate(zip(moves, scores)):
        if (score != cs.UNSAVED_SCORE and abs(score) <= cs.KEPT_MAX_SCORE and not board.is_check()
                and not board.is_capture(move) and not move.promotion):
            out.append((game, ply, board.uci(move), score, result, board.fen(en_passant='xfen')))
        board.push(move)
    return out


def random_games(seed, count, plies):
    """Seeded random legal games from the start position; some start from a
    position reached after a double pawn push (an en passant square in the header)."""
    rng = random.Random(seed)
    games = []
    for g in range(count):
        board = chess.Board()
        if g % 3 == 2:  # a start board with an en passant square (and lost castling rights, sometimes)
            for _ in range(rng.randrange(2, 30)):
                legal = list(board.legal_moves)
                if not legal:
                    break
                board.push(rng.choice(legal))
            doubles = [m for m in board.legal_moves
                       if board.piece_type_at(m.from_square) == chess.PAWN
                       and abs(m.to_square - m.from_square) == 16]
            if doubles:
                board.push(rng.choice(doubles))
            board = chess.Board(board.fen(en_passant='fen'))
        start = board.copy()
        moves, scores = [], []
        for _ in range(plies):
            legal = list(board.legal_moves)
            if not legal or board.is_insufficient_material():
                break
            # Prefer castling, en passant and promotions when on offer, so the games cover them.
            special = [m for m in legal if board.is_castling(m) or board.is_en_passant(m) or m.promotion]
            move = rng.choice(special if special and rng.random() < 0.7 else legal)
            moves.append(move)
            scores.append(rng.choice([0, 35, -120, 900, -20000, 20000, 20001, -29990, cs.UNSAVED_SCORE]))
            board.push(move)
        games.append((start, moves, scores, rng.randrange(3)))
    return games


class CommitteeSitesTests(unittest.TestCase):
    def test_replay_matches_python_chess(self):
        games = random_games(20261109, 60, 160)
        data = b''.join(encode_game(*g) for g in games)
        want = [row for k, g in enumerate(games) for row in reference_kept(*g, k)]
        got = list(cs.replay_records(data))
        self.assertEqual(got, want)
        # The games cover what the decoder must get right.
        kinds = {'castling': 0, 'ep': 0, 'promotion': 0, 'check': 0, 'ep_in_header': 0, 'ep_written': 0}
        for start, moves, _, _ in games:
            board = start.copy()
            kinds['ep_in_header'] += start.ep_square is not None
            for m in moves:
                kinds['castling'] += board.is_castling(m)
                kinds['ep'] += board.is_en_passant(m)
                kinds['promotion'] += m.promotion is not None
                kinds['check'] += board.is_check()
                board.push(m)
        kinds['ep_written'] = sum(1 for row in got if row[5].split(' ')[3] != '-')
        for k, n in kinds.items():
            self.assertGreater(n, 0, k)
        # Both castling sides of both colours, through their UCI moves in the kept rows.
        castles = {row[2] for row in got if row[2] in ('e1g1', 'e1c1', 'e8g8', 'e8c8')}
        self.assertEqual(castles, {'e1g1', 'e1c1', 'e8g8', 'e8c8'})

    def test_filter(self):
        board = chess.Board()
        moves = [chess.Move.from_uci(u) for u in ('e2e4', 'd7d5', 'e4d5', 'd8d5', 'b1c3', 'd5e5', 'g1e2', 'e5e4')]
        scores = [10, cs.UNSAVED_SCORE, 30, 20001, 15, -20000, 20000, 5]
        rows = list(cs.replay_records(encode_game(board, moves, scores, 1)))
        # e4d5 is a capture, d8d5 a capture (and 20001), d7d5 unsaved; Bc3... d5e5 is kept at -20000;
        # g1e2 is played in check (Qe5+) and dropped.
        self.assertEqual([r[2] for r in rows], ['e2e4', 'b1c3', 'd5e5', 'e5e4'])
        self.assertEqual(rows[0][5], chess.Board().fen())

    def test_top_threshold(self):
        hist = {0: 50, 10: 30, 20: 15, 30: 5}
        self.assertEqual(cs.top_threshold(hist, 0.05), 30)  # rank 5: exactly the five at 30
        self.assertEqual(cs.top_threshold(hist, 0.06), 20)  # rank 6: the ties at 20 come in too
        self.assertEqual(cs.top_threshold(hist, 0.2), 20)
        self.assertEqual(cs.top_threshold(hist, 1.0), 0)

    def _work(self, tmp, rows_by_shard):
        for name, rows in rows_by_shard.items():
            with open(tmp / f'{name}.tsv', 'w', encoding='utf-8') as f, \
                    open(tmp / f'{name}.a', 'w', encoding='utf-8') as fa, \
                    open(tmp / f'{name}.b', 'w', encoding='utf-8') as fb:
                for k, (fen, a, b) in enumerate(rows):
                    f.write(f'{k}\t0\te2e4\t0\t1\t{fen}\n')
                    fa.write(f'{a}\n')
                    fb.write(f'{b}\n')

    def test_select(self):
        # 40 positions; D = |a - b| is 100 for 4 of them (two of which are the same position), 0 otherwise.
        board = chess.Board()
        fens = []
        for move in list(board.legal_moves)[:20]:
            b = board.copy()
            b.push(move)
            fens.append(b.fen())
        rows = [(fens[k % 20].replace(' 0 1', f' {k} 1') if k % 20 else fens[0], 0, 0) for k in range(40)]
        for k in (3, 7, 11):
            rows[k] = (rows[k][0], 50, -50)
        rows[23] = (rows[3][0].replace(' 3 1', ' 9 1'), 60, -40)  # the same position as row 3, another clock
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._work(tmp, {'s1': rows[:25], 's2': rows[25:]})
            controls, sites, stats = cs.select_sites(tmp, ['s1', 's2'], 0.1, 3, 5, seed=7)
            self.assertEqual(stats['threshold_cp'], 100)
            self.assertEqual(stats['top_set'], 4)
            self.assertEqual(stats['positions'], 40)
            self.assertEqual(len(sites), 3)
            self.assertTrue(all(s['d'] == 100 and s['set'] == 'top' for s in sites))
            self.assertEqual(len({cs.position_key(s['fen']) for s in sites}), 3)  # the duplicate dropped
            self.assertEqual(len(controls), 5)
            self.assertTrue(all(s['d'] == 0 and s['set'] == 'control' for s in controls))
            self.assertEqual(len({cs.position_key(s['fen']) for s in controls}), 5)
            again = cs.select_sites(tmp, ['s1', 's2'], 0.1, 3, 5, seed=7)
            self.assertEqual((controls, sites, stats), again)
            with self.assertRaises(SystemExit):  # four top positions hold only three distinct ones
                cs.select_sites(tmp, ['s1', 's2'], 0.1, 4, 5, seed=7)
            # The command line writes the controls first, ids in order.
            out = tmp / 'out'
            with mock.patch('sys.stdout', io.StringIO()):
                self.assertEqual(cs.main(['select', str(tmp), str(out), '--shards', 's1', 's2', '--top-share',
                                          '0.1', '--count', '3', '--control', '5', '--seed', '7']), 0)
            written = [json.loads(line) for line in (out / 'sites.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual([w['id'] for w in written], list(range(8)))
            self.assertEqual([w['set'] for w in written], ['control'] * 5 + ['top'] * 3)

    def test_parse_label(self):
        self.assertEqual(cs.parse_label('info depth 14 seldepth 20 score cp -37 nodes 200000 pv e2e4\n'),
                         (-37, 0, 14))
        self.assertEqual(cs.parse_label('info depth 9 score mate 3 nodes 1000 pv h5f7'), (20000, 1, 9))
        self.assertEqual(cs.parse_label('info depth 9 score mate -2 nodes 1000'), (-20000, 1, 9))
        with self.assertRaises(RuntimeError):
            cs.parse_label(None)

    def test_search_labels_protocol_and_resume(self):
        sent = []

        class Engine:
            """A stand-in engine: answers uci, isready and go."""
            def __init__(self, *args, **kwargs):
                self.stdin = self
                self.stdout = self
                self.out = []

            def write(self, text):
                line = text.strip()
                sent.append(line)
                if line == 'uci':
                    self.out.append('uciok\n')
                elif line == 'isready':
                    self.out.append('readyok\n')
                elif line.startswith('go'):
                    self.out += ['info depth 1 score cp 5 nodes 10\n', 'info depth 2 score cp -8 nodes 99\n',
                                 'bestmove e2e4\n']

            def flush(self):
                pass

            def readline(self):
                return self.out.pop(0) if self.out else ''

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'labels.tsv'
            path.write_text('4\t12\t0\t15\n5\t3', encoding='utf-8')  # the second line was cut short
            done = cs.read_labels(path)
            self.assertEqual(done, {4: (12, 0, 15)})
            self.assertEqual(path.read_text(encoding='utf-8'), '4\t12\t0\t15\n')
            cs.search_labels('fork', [(5, chess.Board().fen())], path, 200000, 1, syzygy='/tables', popen=Engine)
            self.assertEqual(cs.read_labels(path), {4: (12, 0, 15), 5: (-8, 0, 2)})
            self.assertIn('setoption name SyzygyPath value /tables', sent)
            self.assertLess(sent.index('setoption name SyzygyPath value /tables'), sent.index('go nodes 200000'))
            self.assertLess(sent.index('ucinewgame'), sent.index(f'position fen {chess.Board().fen()}'))
            sent.clear()
            cs.search_labels('fork', [(6, chess.Board().fen())], path, 1000, 1, popen=Engine)
            self.assertFalse(any('SyzygyPath' in s for s in sent))

    def test_check_bench(self):
        ref = (HERE.parents[1] / 'tests' / 'bench-s512ppr3.ref').read_text(encoding='utf-8')
        nodes = ref.split('nodes ')[1].split()[0]
        signature = ref.split('signature ')[1].split()[0]

        def run(bench_nodes):
            def fake(cmd, **kwargs):
                text = 'Fork x\nnet s512ppr3\n' if cmd[1] == 'version' else \
                    f'nodes {bench_nodes}\nsignature {signature}\nnps 1\n'
                return mock.Mock(stdout=text)
            with mock.patch.object(cs.subprocess, 'run', fake):
                return cs.check_bench('fork')

        self.assertEqual(run(nodes), (nodes, signature))
        with self.assertRaises(SystemExit):
            run(int(nodes) + 1)
        with self.assertRaises(SystemExit):  # a prefix of the reference's count is not a match
            run(nodes[:-1])

    def test_error_ratio(self):
        sites = [{'id': 1, 'eval_a': 10}, {'id': 2, 'eval_a': 300}, {'id': 3, 'eval_a': 10}, {'id': 7, 'eval_a': 10}]
        controls = [{'id': 4, 'eval_a': 10}, {'id': 5, 'eval_a': 300}, {'id': 6, 'eval_a': 300},
                    {'id': 8, 'eval_a': 300}]
        labels = {1: (30, 0, 10), 2: (200, 0, 10), 3: (20000, 1, 9), 4: (20, 0, 10), 5: (280, 0, 10),
                  6: (340, 0, 10), 7: (29497, 0, 30), 8: (-29250, 0, 30)}
        r = cs.error_ratio(sites, controls, labels)
        # Site errors 20 and 100 (the mate and the table win left out); control errors 10, 20 and 40.
        self.assertEqual((r['sites'], r['controls']), (2, 3))
        self.assertAlmostEqual(r['ratio'], round(60 / (70 / 3), 3))
        # Matched: the controls' bin means, 10 (|eval| 10) and 30 (|eval| 300), at the sites' bins.
        self.assertAlmostEqual(r['ratio_matched'], round(60 / 20, 3))

    def test_matched_interval(self):
        # Two bins; every site errs 2x the controls of its bin, so every resample's matched ratio is 2.
        sites = [{'id': k, 'eval_a': 10 if k % 2 else 300} for k in range(20)]
        controls = [{'id': 100 + k, 'eval_a': 10 if k % 2 else 300} for k in range(20)]
        labels = {s['id']: (s['eval_a'] + (20 if s['eval_a'] == 10 else 60), 0, 10) for s in sites}
        labels.update({s['id']: (s['eval_a'] - (10 if s['eval_a'] == 10 else 30), 0, 10) for s in controls})
        r = cs.matched_interval(sites, controls, labels, 200, 7)
        self.assertEqual((r['low'], r['high'], r['resamples'], r['seed']), (2.0, 2.0, 200, 7))
        # Noisy controls: the interval holds the point estimate, and the same seed gives the same interval.
        rng = random.Random(3)
        labels.update({s['id']: (s['eval_a'] + rng.randint(-40, 40), 0, 10) for s in controls})
        point = cs.error_ratio(sites, controls, labels)['ratio_matched']
        r = cs.matched_interval(sites, controls, labels, 400, 11)
        self.assertLess(r['low'], point)
        self.assertGreater(r['high'], point)
        self.assertEqual(r, cs.matched_interval(sites, controls, labels, 400, 11))

    def test_positions_command(self):
        games = random_games(5, 4, 40)
        with tempfile.TemporaryDirectory() as t:
            shard = Path(t) / 'x.vf'
            shard.write_bytes(b''.join(encode_game(*g) for g in games))
            out = Path(t) / 'x.tsv'
            with mock.patch('sys.stdout', io.StringIO()):
                self.assertEqual(cs.main(['positions', str(shard), str(out)]), 0)
            lines = out.read_text(encoding='utf-8').splitlines()
            want = [row for k, g in enumerate(games) for row in reference_kept(*g, k)]
            self.assertEqual(lines, ['\t'.join(str(x) for x in row) for row in want])
            self.assertFalse((Path(t) / 'x.tsv.part').exists())


def sigmoid(x):
    return 1.0 / (1.0 + 2.718281828459045 ** -x)


class ArmTests(unittest.TestCase):
    """Idea 52's arm for retrain 8b (`arm`): the one-move games against python-chess, the label targets, and
    equal data on a pool of random games."""

    def test_encode_site_against_python_chess(self):
        # Every kept position of random games (castling, an en passant square in the FEN, clocks): the
        # one-move game decodes (verify_games.decode_board, python-chess) to the same position, and its
        # code is python-chess's code for the move.
        games = random_games(52, 40, 120)
        rows = [r for k, g in enumerate(games) for r in reference_kept(*g, k)]
        castles = 0
        for game, ply, uci, score, result, fen in rows:
            data = cs.encode_site(fen, uci, score, result)
            self.assertEqual(len(data), 40)
            board, res = vg.decode_board(data[:32])
            self.assertEqual(board.fen(en_passant='xfen'), fen)
            self.assertEqual(res, result)
            move = chess.Move.from_uci(uci)
            self.assertIn(move, board.legal_moves)
            self.assertEqual(struct.unpack_from('<Hh', data, 32), (vg.code_of(board, move), score))
            self.assertEqual(data[36:], bytes(4))
            castles += board.is_castling(move)
        self.assertGreater(castles, 0)

    def test_site_target(self):
        # blend: the deep score (White's view) with the game's result; a table win clamped to the trainer's limit.
        self.assertEqual(cs.site_target(150, True, 1, 'blend', 92.0), (150, 1))
        self.assertEqual(cs.site_target(150, False, 0, 'blend', 92.0), (-150, 0))
        self.assertEqual(cs.site_target(29200, False, 0, 'blend', 92.0), (-20000, 0))
        # label: 0.5 sigmoid(s / S) + 0.5 z equals sigmoid(deep / S) (White's view) within the rounding.
        for cp in (-20000, -3000, -400, -101, -100, -99, -10, 0, 10, 99, 100, 101, 400, 3000, 20000, 29200):
            for white in (True, False):
                s, z = cs.site_target(cp, white, 1, 'label', 92.0)
                self.assertLessEqual(abs(s), 20000)
                p = sigmoid((cp if white else -cp) / 92.0) if abs(cp) <= 20000 else (1.0 if (cp > 0) == white else 0.0)
                got = 0.5 * sigmoid(s / 92.0) + 0.5 * (0.0, 0.5, 1.0)[z]
                self.assertLessEqual(abs(got - p), 0.5 / 92.0 / 8 + 1e-9, (cp, white, s, z))

    def _pool(self, tmp):
        games = random_games(20261109, 120, 90)
        names = ['p0', 'p1']  # as select names them; the files are p0.vf and p1.vf
        pool = tmp / 'pool'
        pool.mkdir()
        rows = {}
        for i, name in enumerate(names):
            part = games[i::2]
            (pool / f'{name}.vf').write_bytes(b''.join(encode_game(*g) for g in part))
            rows[name] = list(cs.replay_records((pool / f'{name}.vf').read_bytes()))
        return pool, names, rows

    def _sites(self, tmp, rows, n_top, n_control, seed=3):
        rng = random.Random(seed)
        everything = [(name, line, r) for name in sorted(rows) for line, r in enumerate(rows[name])]
        picked = rng.sample(everything, n_top + n_control)
        out = tmp / 'out'
        out.mkdir()
        sites = []
        for k, (name, line, r) in enumerate(picked):
            sites.append({'id': k, 'set': 'control' if k < n_control else 'top', 'shard': name, 'line': line,
                          'game': r[0], 'ply': r[1], 'move': r[2], 'score_white': r[3], 'result': r[4],
                          'fen': r[5]})
        (out / 'sites.jsonl').write_text(''.join(json.dumps(s) + '\n' for s in sites), encoding='utf-8')
        labels = ''.join(f'{s["id"]}\t{rng.choice([-300, -20, 0, 45, 800, 20000, -29200])}\t0\t12\n' for s in sites)
        (out / 'labels.tsv').write_text(labels, encoding='utf-8')
        (out / 'stats.json').write_text(json.dumps({'positions_by_shard': {k: len(v) for k, v in rows.items()}}),
                                        encoding='utf-8')
        return out, sites

    def test_arm_equal_data(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            pool, names, rows = self._pool(tmp)
            out, sites = self._sites(tmp, rows, 30, 6)
            dest = tmp / 'arm'
            with mock.patch('sys.stdout', io.StringIO()):
                self.assertEqual(cs.main(['arm', str(out), str(dest), '--pool', str(pool), '--shards', *names,
                                          '--factor', '4', '--hold', '5', '--seed', '9']), 0)
            record = json.loads((dest / 'arm.json').read_text(encoding='utf-8'))
            self.assertEqual((record['trained_sites'], record['held_sites'], record['controls']), (25, 5, 6))
            self.assertTrue(record['check']['equal_data'])
            # Independently (python-chess): kept positions of the copies + the sites file = the pool's.
            kept = lambda data: len(list(cs.replay_records(data)))  # noqa: E731
            pool_kept = sum(len(v) for v in rows.values())
            copies_kept = sum(kept((dest / f'i52-{n}.vf').read_bytes()) for n in names)
            site_games = (dest / 'i52-sites.vf').read_bytes()
            self.assertEqual(len(site_games), 25 * 4 * 40)
            self.assertEqual(copies_kept + 25 * 4, pool_kept)
            # Every trained site's own record is gone from the copies; the held sites and controls are not.
            left = {(n, r[0], r[1]) for n in names for r in cs.replay_records((dest / f'i52-{n}.vf').read_bytes())}
            for s in sites:
                there = (s['shard'], s['game'], s['ply']) in left
                self.assertEqual(there, s['set'] == 'control' or s['id'] >= 6 + 25, s['id'])
            # The sites file: the trained sites in order, four rounds, each the position and move played, its
            # score the deep label (White's view, clamped) and its result the game's (target blend).
            labels = {int(line.split('\t')[0]): int(line.split('\t')[1])
                      for line in (out / 'labels.tsv').read_text(encoding='utf-8').splitlines()}
            trained = [s for s in sites if s['set'] == 'top'][:25]
            for k in range(100):
                s = trained[k % 25]
                board, result = vg.decode_board(site_games[40 * k:40 * k + 32])
                self.assertEqual(board.fen(en_passant='xfen'), s['fen'])
                self.assertEqual(result, s['result'])
                code, score = struct.unpack_from('<Hh', site_games, 40 * k + 32)
                self.assertEqual(code, vg.code_of(board, chess.Move.from_uci(s['move'])))
                want = labels[s['id']] if board.turn == chess.WHITE else -labels[s['id']]
                self.assertEqual(score, max(-20000, min(20000, want)))
            # The evaluation files: the held sites and the controls, label targets.
            self.assertEqual(len((dest / 'i52-held.vf').read_bytes()), 5 * 40)
            self.assertEqual(len((dest / 'i52-controls.vf').read_bytes()), 6 * 40)
            for name, info in record['files'].items():
                self.assertEqual(cs.sha256_file(dest / name), info['sha256'])
            # The same seed gives the same arm.
            again = tmp / 'again'
            with mock.patch('sys.stdout', io.StringIO()):
                cs.main(['arm', str(out), str(again), '--pool', str(pool), '--shards', *names, '--factor', '4',
                         '--hold', '5', '--seed', '9'])
            self.assertEqual(json.loads((again / 'arm.json').read_text(encoding='utf-8'))['files'], record['files'])

    def test_verify_arm_catches_a_wrong_copy(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            pool, names, rows = self._pool(tmp)
            out, sites = self._sites(tmp, rows, 12, 2)
            dest = tmp / 'arm'
            record = cs.build_arm(out, dest, pool, names, 3, 2, 9, 'blend', 92.0)
            trained = [s for s in sites if s['set'] == 'top'][:10]
            held = [s for s in sites if s['set'] == 'top'][10:]
            controls = [s for s in sites if s['set'] == 'control']
            # One more record dropped in a copy: the kept count no longer adds up.
            copy = dest / f'i52-{names[0]}.vf'
            data = bytearray(copy.read_bytes())
            original = (pool / f'{names[0]}.vf').read_bytes()
            for game, ply, at in cs.game_records(original):
                if data[at:at + 2] == original[at:at + 2] and abs(struct.unpack_from('<h', data, at)[0]) < 100:
                    data[at:at + 2] = struct.pack('<h', cs.UNSAVED_SCORE)
                    break
            copy.write_bytes(bytes(data))
            with self.assertRaises(SystemExit):
                cs.verify_arm(dest, pool, record, trained, held, controls)
            # A sites file with ten games (one round) missing, after a fresh build.
            record = cs.build_arm(out, dest, pool, names, 3, 2, 9, 'blend', 92.0)
            cs.verify_arm(dest, pool, record, trained, held, controls)  # the fresh build passes
            sites_file = dest / 'i52-sites.vf'
            sites_file.write_bytes(sites_file.read_bytes()[:-400])
            with self.assertRaises(SystemExit):
                cs.verify_arm(dest, pool, record, trained, held, controls)


if __name__ == '__main__':
    unittest.main()
