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
        sites = [{'id': 1, 'eval_a': 10}, {'id': 2, 'eval_a': 300}, {'id': 3, 'eval_a': 10}]
        controls = [{'id': 4, 'eval_a': 10}, {'id': 5, 'eval_a': 300}, {'id': 6, 'eval_a': 300}]
        labels = {1: (30, 0, 10), 2: (200, 0, 10), 3: (20000, 1, 9), 4: (20, 0, 10), 5: (280, 0, 10),
                  6: (340, 0, 10)}
        r = cs.error_ratio(sites, controls, labels)
        # Site errors 20 and 100 (the mate left out); control errors 10, 20 and 40.
        self.assertEqual((r['sites'], r['controls']), (2, 3))
        self.assertAlmostEqual(r['ratio'], round(60 / (70 / 3), 3))
        # Matched: the controls' bin means, 10 (|eval| 10) and 30 (|eval| 300), at the sites' bins.
        self.assertAlmostEqual(r['ratio_matched'], round(60 / 20, 3))

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


if __name__ == '__main__':
    unittest.main()
