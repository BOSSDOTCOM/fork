# SPDX-License-Identifier: GPL-3.0-or-later
"""S512r2 against S512r3 on simple endings (owner, 2026-11-05): random legal KPK, KQK and KRK positions
(either side to move, the extra piece for either colour), kept only when quiet (not in check, no capture
available, so a static evaluation means something), each probed in the Syzygy tables (WDL from the side
to move) and evaluated by each net's integer evaluation (the reference's R-int, tools/nnue/models.py, at
the net's own scale). Declared before the run: a won position is misjudged below +100 cp, a lost one
above -100 cp, a drawn one beyond +-200 cp.

    endgame_check.py REPO SYZYGY_DIR NET_A[=LAYOUT] NET_B[=LAYOUT] [--per-kind 300]
(LAYOUT defaults to tools/nnue/s512.json)
"""
import random
import sys
from pathlib import Path

repo = Path(sys.argv[1])
sys.path.insert(0, str(repo / 'tools/nnue'))
import chess  # noqa: E402
import chess.syzygy  # noqa: E402
import models  # noqa: E402
import netformat  # noqa: E402

syzygy, nets = sys.argv[2], sys.argv[3:5]
per_kind = int(sys.argv[sys.argv.index('--per-kind') + 1]) if '--per-kind' in sys.argv else 300


def load(arg):
    path, _, layout = arg.partition('=')
    desc = netformat.layout(layout or str(repo / 'tools/nnue/s512.json'))
    data = Path(path).read_bytes()
    arch = models.arch_from_net(desc['name'], data[netformat.HEADER_BYTES:])
    return arch, models.unpack(arch, data[netformat.HEADER_BYTES:]), netformat.header_fields(data)['scale']


loaded = [load(p) for p in nets]
rng = random.Random(20261105)
tb = chess.syzygy.open_tablebase(syzygy)


def random_position(extra):
    while True:
        b = chess.Board(None)
        strong = rng.choice([chess.WHITE, chess.BLACK])
        squares = rng.sample(range(64), 3)
        b.set_piece_at(squares[0], chess.Piece(chess.KING, chess.WHITE))
        b.set_piece_at(squares[1], chess.Piece(chess.KING, chess.BLACK))
        if extra == chess.PAWN and squares[2] // 8 in (0, 7):
            continue
        b.set_piece_at(squares[2], chess.Piece(extra, strong))
        b.turn = rng.choice([chess.WHITE, chess.BLACK])
        if not b.is_valid() or b.is_check() or any(b.is_capture(m) for m in b.legal_moves) or b.is_game_over():
            continue
        return b


def verdict(wdl):
    return 'won' if wdl > 0 else 'lost' if wdl < 0 else 'drawn'


def misjudged(kind, cp):
    return cp < 100 if kind == 'won' else cp > -100 if kind == 'lost' else abs(cp) > 200


totals = {}
for name, extra in (('KPK', chess.PAWN), ('KQK', chess.QUEEN), ('KRK', chess.ROOK)):
    for _ in range(per_kind):
        b = random_position(extra)
        kind = verdict(tb.probe_wdl(b))
        for k, (arch, net, scale) in enumerate(loaded):
            cp = models.r_int(arch, net, scale, b)
            t = totals.setdefault((name, kind, k), [0, 0])
            t[0] += 1
            t[1] += misjudged(kind, cp)
names = [Path(p.partition('=')[0]).stem for p in nets]
print(f'{"ending":6} {"result":6} {"positions":>9}  ' + '  '.join(f'{n + " misjudged":>20}' for n in names))
for name in ('KPK', 'KQK', 'KRK'):
    for kind in ('won', 'drawn', 'lost'):
        if (name, kind, 0) not in totals:
            continue
        n = totals[(name, kind, 0)][0]
        cells = '  '.join(f'{totals[(name, kind, k)][1]:>9} ({100 * totals[(name, kind, k)][1] / n:5.1f}%)' for k in range(2))
        print(f'{name:6} {kind:6} {n:>9}  {cells}')
for k, n in enumerate(names):
    bad = sum(v[1] for (e, r, kk), v in totals.items() if kk == k)
    allp = sum(v[0] for (e, r, kk), v in totals.items() if kk == k)
    print(f'{n}: {bad} of {allp} misjudged ({100 * bad / allp:.1f}%)')
