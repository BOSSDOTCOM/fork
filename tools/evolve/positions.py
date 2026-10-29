# SPDX-License-Identifier: GPL-3.0-or-later

"""The heuristic-discovery loop's position set (ideas.md idea 23, DESIGN.md
§5.2 deliverable 8c): positions from Fork's own self-play, labeled by Fork's
own much deeper search (KB data-policy.md rule 1: labels come from Fork).

Openings: random 8-ply games played by python-chess with uniformly random
legal moves (tools/make_openings.py's method, with this set's own seed), so
no book and no other engine chose any move (the UHO books are off-limits for
tuning, data-policy.md). Each game is Fork against itself at a fixed node
budget per move (deterministic), ended by the rules, by a decided score
(|score| >= 1000 cp for 6 plies) or at 200 plies. From each game, positions
from ply 12 on, every 6th ply, out of check and with at least 8 pieces, at
most 10 per game; each is labeled with `go depth D` from a fresh state
(ucinewgame, Hash 64). Labels with a mate score or |score| > 1500 cp are
dropped (the score-error proxy needs centipawn labels). One game in six
goes to the holdout split with all of its positions, never used during
evolution: the split is drawn per game, so no held-out position shares a
game with an evolve position (audit-1 U-13).

Batches made before that change (the committed positions.jsonl: ids p…
and b01p… to b10p…) drew the split per position and record no game; they
keep their split as committed (an audit measured the within-game
correlation of the gains as negligible, -0.022 to +0.015). The per-game
split applies to batches generated from now on.

Output: JSON Lines, one position per line: id, game (the batch's id prefix,
"g" and the game's number), fen (the full FEN the label was searched from,
clocks included), bm (the label's best move, UCI), san (the same in SAN),
ce (its score in cp, side to move), depth, nodes, split ("evolve" or
"holdout"). The loop's own scripts read it without python-chess.

    .venv/Scripts/python.exe -I tools/evolve/positions.py OUT.jsonl --engine FORK \\
        [--games 150] [--play-nodes 20000] [--label-depth 15] [--seed 20261027]
"""
import argparse
import json
import random
import subprocess
import sys
import time

try:
    import chess
except ImportError:  # the split rule (assign_splits) and its tests need no python-chess
    chess = None

HoldoutShare = 6  # one game in six is held out


def assign_splits(games, rng):
    """{game: "evolve" or "holdout"} for each distinct game in `games`, in order of first
    appearance: one draw per game, so every position of a game lands in the same split."""
    splits = {}
    for game in games:
        if game not in splits:
            splits[game] = 'holdout' if rng.randrange(HoldoutShare) == 0 else 'evolve'
    return splits


class Uci:
    """A minimal UCI driver: one engine process, lines read synchronously."""

    def __init__(self, path, options):
        self.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8',
                                  bufsize=1)
        self.send('uci')
        self.until('uciok')
        for name, value in options.items():
            self.send(f'setoption name {name} value {value}')
        self.ready()

    def send(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()

    def until(self, prefix):
        lines = []
        while True:
            line = self.p.stdout.readline()
            if not line:
                sys.exit(f'engine closed its output waiting for {prefix!r}')
            lines.append(line.rstrip('\n'))
            if line.startswith(prefix):
                return lines

    def ready(self):
        self.send('isready')
        self.until('readyok')

    def search(self, board, go):
        """(best move, last score line as (kind, value), depth, nodes) for the game so far."""
        start = board.root().fen()
        moves = ' '.join(m.uci() for m in board.move_stack)
        self.send(f'position fen {start}' + (f' moves {moves}' if moves else ''))
        self.send(f'go {go}')
        lines = self.until('bestmove')
        score, depth, nodes = None, 0, 0
        for line in lines:
            t = line.split()
            if not t or t[0] != 'info' or 'score' not in t:
                continue
            i = t.index('score')
            if t[i + 1] in ('cp', 'mate') and 'lowerbound' not in t and 'upperbound' not in t:
                score = (t[i + 1], int(t[i + 2]))
                if 'depth' in t:
                    depth = int(t[t.index('depth') + 1])
                if 'nodes' in t:
                    nodes = int(t[t.index('nodes') + 1])
        return chess.Move.from_uci(lines[-1].split()[1]), score, depth, nodes

    def close(self):
        self.send('quit')
        self.p.wait(timeout=10)


def random_opening(rng, plies):
    while True:
        board = chess.Board()
        for _ in range(plies):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        if not board.is_game_over() and len(board.move_stack) == plies:
            return chess.Board(board.fen())


def play_game(fork, board, nodes):
    """Fork against itself from `board`; returns the board with the game's moves."""
    decided = 0
    while not board.is_game_over(claim_draw=True) and len(board.move_stack) < 200:
        move, score, _, _ = fork.search(board, f'nodes {nodes}')
        board.push(move)
        decided = decided + 1 if score and (score[0] == 'mate' or abs(score[1]) >= 1000) else 0
        if decided >= 6:
            break
    return board


def samples(game, opening_plies):
    """Sampled positions of a finished game, as FENs."""
    out = []
    board = game.root()
    for ply, move in enumerate(game.move_stack, start=1):
        board.push(move)
        if ply + opening_plies < 12 or (ply + opening_plies) % 6 or len(out) >= 10:
            continue
        if board.is_check() or board.is_game_over() or len(board.piece_map()) < 8:
            continue
        out.append(board.fen())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--engine', required=True)
    ap.add_argument('--games', type=int, default=150)
    ap.add_argument('--play-nodes', type=int, default=20000)
    ap.add_argument('--label-depth', type=int, default=15)
    ap.add_argument('--opening-plies', type=int, default=8)
    ap.add_argument('--seed', type=int, default=20261027)
    ap.add_argument('--id-prefix', default='p', help='id prefix, so later batches can be appended (default p)')
    a = ap.parse_args()
    if chess is None:
        sys.exit('positions.py needs python-chess (the .venv has it)')
    rng = random.Random(a.seed)
    t0 = time.time()

    player = Uci(a.engine, {'Hash': 16})
    fens, seen = [], set()  # (fen, game id)
    for g in range(a.games):
        player.send('ucinewgame')
        player.ready()
        game = play_game(player, random_opening(rng, a.opening_plies), a.play_nodes)
        for fen in samples(game, a.opening_plies):
            key = ' '.join(fen.split()[:4])
            if key not in seen:
                seen.add(key)
                fens.append((fen, f'{a.id_prefix}g{g:04d}'))
        print(f'game {g + 1}/{a.games}: {len(game.move_stack)} plies, {len(fens)} positions '
              f'({time.time() - t0:.0f} s)', flush=True)
    player.close()
    splits = assign_splits([game for _, game in fens], rng)

    labeler = Uci(a.engine, {'Hash': 64})
    kept = 0
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        for i, (fen, game) in enumerate(fens):
            board = chess.Board(fen)
            labeler.send('ucinewgame')
            labeler.ready()
            move, score, depth, nodes = labeler.search(board, f'depth {a.label_depth}')
            if score and score[0] == 'cp' and abs(score[1]) <= 1500 and depth >= a.label_depth:
                f.write(json.dumps({'id': f'{a.id_prefix}{i:05d}', 'game': game, 'fen': fen, 'bm': move.uci(),
                                    'san': board.san(move), 'ce': score[1], 'depth': depth, 'nodes': nodes,
                                    'split': splits[game]}) + '\n')
                kept += 1
            if (i + 1) % 50 == 0:
                print(f'labeled {i + 1}/{len(fens)}, kept {kept} ({time.time() - t0:.0f} s)', flush=True)
    labeler.close()
    print(f'positions: {kept} of {len(fens)} kept, seed {a.seed}, {a.games} games at {a.play_nodes} nodes, '
          f'labels at depth {a.label_depth} ({time.time() - t0:.0f} s)')


if __name__ == '__main__':
    main()
