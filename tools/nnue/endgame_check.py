# SPDX-License-Identifier: GPL-3.0-or-later
"""S512r2 against S512r3 on simple endings (owner, 2026-11-05): random legal KPK, KQK and KRK positions
(either side to move, the extra piece for either colour), kept only when quiet (not in check, no capture
available, so a static evaluation means something), each probed in the Syzygy tables (WDL from the side
to move) and evaluated by each net's integer evaluation (the reference's R-int, tools/nnue/models.py, at
the net's own scale). Declared before the run: a won position is misjudged below +100 cp, a lost one
above -100 cp, a drawn one beyond +-200 cp.

**What it measures (2026-11-11, bug review T1):** these 900 positions come from the population the Syzygy
endgame slice (tools/datagen/endgame_slice.py, half of it KPK, KQK and KRK) trains on, and 898 of them are in
the slice's ten files verbatim (509 in slice1-01 alone; tools/nnue/endgame_heldout.py overlap --old-check). Since
g3s2 the result measures **recall** of slice positions, not generalisation; the held-out check is
tools/nnue/endgame_heldout.py.

**The integrity/recall gate (owner, 2026-11-12, about 5:00 PM and 5:50 PM EST):** at most 15 of the 900
misjudged (think tank decision 10's target), enforced only for a net trained with the endgame slice (it catches
missing or corrupted slice data) and reported only for any other net. `gate` reads this script's output (the
first net's count, the candidate's in tools/nnue/gates.sh) and exits 1 only when the gate applies and fails.

    endgame_check.py REPO SYZYGY_DIR NET_A[=LAYOUT] NET_B[=LAYOUT] [--per-kind 300]
(LAYOUT defaults to tools/nnue/s512.json)
    endgame_check.py gate OUTPUT.txt --slice-trained {0,1} [--limit 15]
"""
import argparse
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chess  # noqa: E402
import chess.syzygy  # noqa: E402

KINDS = (('KPK', chess.PAWN), ('KQK', chess.QUEEN), ('KRK', chess.ROOK))
SEED = 20261105
RECALL_LIMIT = 15  # the integrity/recall gate: owner, 2026-11-07 (think tank decision 10), named 2026-11-12


def random_position(rng, extra):
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


def positions(per_kind=300):
    """The check's positions in order, as (ending, board): the same sequence the check has always drawn
    (one generator seeded SEED, KPK then KQK then KRK)."""
    rng = random.Random(SEED)
    return [(name, random_position(rng, extra)) for name, extra in KINDS for _ in range(per_kind)]


def verdict(wdl):
    return 'won' if wdl > 0 else 'lost' if wdl < 0 else 'drawn'


def misjudged(kind, cp):
    return cp < 100 if kind == 'won' else cp > -100 if kind == 'lost' else abs(cp) > 200


def load(repo, arg):
    import models
    path, _, layout = arg.partition('=')
    return models.evaluator(path, layout or str(repo / 'tools/nnue/s512.json'))[0]


def recall_gate(text, slice_trained, limit=RECALL_LIMIT):
    """(line, failed) for the integrity/recall gate on this script's output `text`: the first net's misjudged count
    against `limit`. Enforced (failed when over the limit, or when no count is found) only for a slice-trained net;
    otherwise reported, never failed."""
    m = re.search(r'^(.+?): (\d+) of (\d+) misjudged', text, re.M)
    if not slice_trained:
        what = f'{m[1]} {m[2]} of {m[3]} misjudged' if m else 'no misjudged count in the output'
        return (f'integrity/recall check: {what} (report only: not trained with the endgame slice, '
                f'SLICE_TRAINED=0; the gate, at most {limit}, applies to slice-trained nets)'), False
    if not m:
        return 'integrity/recall gate: no misjudged count in the output: FAILED (SLICE_TRAINED=1)', True
    failed = int(m[2]) > limit
    return (f'integrity/recall gate: {m[1]} {m[2]} of {m[3]} misjudged, at most {limit}: '
            + ('FAILED' if failed else 'passed') + ' (trained with the endgame slice, SLICE_TRAINED=1)'), failed


def gate_main(argv):
    ap = argparse.ArgumentParser(prog='endgame_check.py gate', description='the integrity/recall gate')
    ap.add_argument('output', help="this script's output for the candidate (first) and a control")
    ap.add_argument('--slice-trained', type=int, choices=(0, 1), required=True,
                    help='1: the net was trained with the endgame slice (the gate applies); 0: report only')
    ap.add_argument('--limit', type=int, default=RECALL_LIMIT)
    a = ap.parse_args(argv)
    line, failed = recall_gate(Path(a.output).read_text(encoding='utf-8', errors='replace'), a.slice_trained,
                               a.limit)
    print(line)
    return 1 if failed else 0


def main(argv):
    if len(argv) > 1 and argv[1] == 'gate':
        return gate_main(argv[2:])
    repo = Path(argv[1])
    syzygy, nets = argv[2], argv[3:5]
    per_kind = int(argv[argv.index('--per-kind') + 1]) if '--per-kind' in argv else 300
    loaded = [load(repo, p) for p in nets]
    tb = chess.syzygy.open_tablebase(syzygy)
    totals = {}
    for name, b in positions(per_kind):
        kind = verdict(tb.probe_wdl(b))
        for k, evaluate in enumerate(loaded):
            cp = evaluate(b)
            t = totals.setdefault((name, kind, k), [0, 0])
            t[0] += 1
            t[1] += misjudged(kind, cp)
    names = [Path(p.partition('=')[0]).stem for p in nets]
    print(f'{"ending":6} {"result":6} {"positions":>9}  ' + '  '.join(f'{n + " misjudged":>20}' for n in names))
    for name, _ in KINDS:
        for kind in ('won', 'drawn', 'lost'):
            if (name, kind, 0) not in totals:
                continue
            n = totals[(name, kind, 0)][0]
            cells = '  '.join(f'{totals[(name, kind, k)][1]:>9} ({100 * totals[(name, kind, k)][1] / n:5.1f}%)'
                              for k in range(2))
            print(f'{name:6} {kind:6} {n:>9}  {cells}')
    for k, n in enumerate(names):
        bad = sum(v[1] for (e, r, kk), v in totals.items() if kk == k)
        allp = sum(v[0] for (e, r, kk), v in totals.items() if kk == k)
        print(f'{n}: {bad} of {allp} misjudged ({100 * bad / allp:.1f}%)')


if __name__ == '__main__':
    sys.exit(main(sys.argv))
