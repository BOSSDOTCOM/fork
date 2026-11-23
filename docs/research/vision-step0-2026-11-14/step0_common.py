# SPDX-License-Identifier: GPL-3.0-or-later
"""Vision step 0 (ideas.md 185): the shared part of the scripts in this folder.

Positions are `fork-train dump` lines (the trainer's own filter and side-to-move-relative view, as idea 175's study
read them: "code:square ... | score | result", codes 0-5 the mover's pawn ... king, 8-13 the opponent's, squares seen
from the mover). The board is built with the mover as White, to move; the opponent (Black) moves down the board.

Each family is a set of 0/1 cells per position. A family's cells are laid out as `block * width + square` for most
families (width 64), so "pooled over squares" is one value per block (side, kind, state) and "by output bucket" is
one value per (block, bucket). Every finder below is written from the concept, with python-chess's attack tables;
the checks against independent oracles are in step0_features.py (python-chess's is_pinned, models.py's exposure
rules, a slow removal-based discoverer finder) and step0_pins_cpp.py (Fork's own Position::pinned/discoverers).

Families (side 0 = the mover's pieces, side 1 = the opponent's; "kind" P N B R Q K = 0..5):
- xl: x_lower's state (a non-king piece attacked by an enemy piece of a lower class: pawn < minor < rook < queen;
  pseudo-attacks on the occupancy, pins ignored), side x kind N..Q.
- xpn / xsl: x_lower split by the attacker: a cheaper pawn or knight attacks it (N, B: a pawn; R, Q: a pawn or a
  knight) / a cheaper slider attacks it (R: a bishop; Q: a bishop or a rook). xl = xpn | xsl on the same cell.
- xx: the full exposure plane (XGR's rule): xl, or attacked by any enemy piece (the king included) and defended by
  none of its own (the king included); pawns too. side x kind P..Q.
- pin: absolutely pinned (the only piece between its own king and an enemy slider on the line), side x kind P..Q.
- pinq: pinned to its own queen (the only piece between an own queen and an enemy bishop on a diagonal or an enemy
  rook on a rank or file; enemy queens excluded), side x kind P..Q.
- disc: discovery candidates (the only piece between the enemy king and an own slider), side x kind P..K; side 1
  (the opponent's, against the mover) is the panel's family, side 0 is a contrast.
- forkn: knight fork squares of a side: a square an own knight can reach (not own-occupied), not attacked by the
  enemy's pawns, from which a knight attacks at least two of the enemy's king, queen, rooks and undefended minors.
  side x square (side 1: the opponent's, against the mover).
- forkp: pawn-push fork squares of a side: a pawn's single or double push to an empty square after which it attacks
  two enemy non-pawn pieces (the king included). side x square.
- under: under-defended and not exposed: attacked by at least two enemy pieces, defended by at most one, and not in
  xx. side x kind P..Q (side 0, the mover's, is the panel's; side 1 a contrast).
- file: file-line contact state of rooks and queens: the first piece met going forward along the file: an own rook
  or queen (doubled, state 0), an enemy rook or queen (contested, 1), none to the edge (clear, 2); other first
  pieces have no cell. (side x {R, Q}) x state.
- block: blockade occupant of a passed pawn (no enemy pawn ahead on its own or a neighbouring file): the stop square
  holds an enemy minor (0), an enemy rook or queen (1), the enemy king (2), an own piece (3); empty has no cell.
  (side x class), the pawn's square.
- loose: loose (no own defender, state 0) or overprotected (own defenders - enemy attackers >= 2, state 1), for N, B,
  R, Q. (side x kind) x state.
- kk: the king pair, the mover's king mirrored to files e-h (32) x the opponent's king (64), mirrored with it.
  Pooled: the kings' wing classes (a-c, d-e, f-h of the mirrored squares).
- mat: captured-material ordinals (thermometer of each side's count): P >= 1..8, N, B, R >= 1..3, Q >= 1..2 per
  side (19 + 19), then the mover's bishop pair, the opponent's, and opposite-coloured bishops (one each, on
  different colours). Not by square: "by square" is the thermometer cells themselves; pooled is per (side, kind).
- trap: trapped by lens 3's d_mob rule (no destination square that is not own-occupied and not attacked by an enemy
  pawn), N..Q, side x kind. trapa: the same and attacked by an enemy piece (a stricter contrast).
- back: back-rank weakness (king on its home rank, every flight square on its second rank own-occupied, no own rook
  or queen on the home rank, an enemy rook or queen on the board), side x the king's file (width 8).
- sev: the absolute 7th (a rook on the side's 7th rank with the enemy king on its 8th; predicted null), side x square.
- bad: the bad bishop (own pawns on the bishop's square colour that are rammed, an enemy pawn directly ahead; class
  min(n, 3) for n >= 1; predicted null), (side x class) x square.
- links: S512+PP's 608 pawn links (tools/nnue/contacts.py link_features, rank limit 1) of the mover's perspective
  (cells 0-607) and the opponent's (608-1215); pooled: per perspective, link type (the two pawns' owners x rank
  offset x file offset).
"""
import sys
from pathlib import Path

import chess
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'tools' / 'nnue'))
import contacts  # noqa: E402

QA, QB = 255, 64
TRAIN_SCALE = 92.0
BLOCK = 2000
FOLDS = 8
CLASS = (1, 2, 2, 3, 4, 5)  # P N B R Q K
W, B = chess.WHITE, chess.BLACK
LINK_RANKS = contacts.S512PP_RANKS
LINKS = contacts.link_count(LINK_RANKS)
RANK_1, RANK_2, RANK_7, RANK_8 = chess.BB_RANK_1, chess.BB_RANK_2, chess.BB_RANK_7, chess.BB_RANK_8
LIGHT = chess.BB_LIGHT_SQUARES
M64 = (1 << 64) - 1


def read_dump(path, limit=0):
    """The positions (bytes of code, square pairs) and their scores."""
    out, scores = [], []
    with open(path, encoding='ascii') as fh:
        for line in fh:
            left, score, _ = line.split('|')
            out.append(bytes(int(x) for t in left.split() for x in t.split(':')))
            scores.append(int(score))
            if limit and len(out) >= limit:
                break
    return out, np.array(scores, dtype=np.float64)


def board_of(packed):
    b = chess.Board(None)
    b.set_piece_map({sq: chess.Piece((code & 7) + 1, W if code < 8 else B)
                     for code, sq in zip(packed[0::2], packed[1::2])})
    b.turn = W
    return b


def bits(mask):
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


def popcount(x):
    return bin(x).count('1')


# ---- family layouts: (cells, side of each cell or -1, group of each cell) ----

def _square_major(blocks, side_of_block, width=64):
    cells = blocks * width
    side = np.array([side_of_block(c // width) for c in range(cells)], dtype=np.int8)
    group = np.arange(cells) // width
    return cells, side, group


def _kk_layout():
    def wing(f):
        return 0 if f <= 2 else (1 if f <= 4 else 2)
    group = np.zeros(2048, dtype=np.int64)
    for m in range(32):
        mf = 4 + m % 4
        for o in range(64):
            group[m * 64 + o] = wing(mf) * 3 + wing(o % 8)
    _, group = np.unique(group, return_inverse=True)
    return 2048, np.full(2048, -1, dtype=np.int8), group


def _mat_layout():
    side = np.array([0] * 19 + [1] * 19 + [0, 1, -1], dtype=np.int8)
    kind_of_t = [0] * 8 + [1] * 3 + [2] * 3 + [3] * 3 + [4] * 2
    group = np.array([kind_of_t[t] for t in range(19)] + [5 + kind_of_t[t] for t in range(19)] + [10, 11, 12])
    return 41, side, group


def _links_layout():
    table = contacts.link_table(LINK_RANKS)
    inverse = {v: k for k, v in table.items()}
    slots = [(s, q) for s in (0, 1) for q in range(8, 56)]
    types = {}
    group = np.zeros(2 * LINKS, dtype=np.int64)
    for n in range(LINKS):
        (i, j) = inverse[n]
        (si, qi), (sj, qj) = slots[i], slots[j]
        key = (si + sj, abs(qi // 8 - qj // 8), abs(qi % 8 - qj % 8))
        t = types.setdefault(key, len(types))
        group[n] = t
    group[LINKS:] = group[:LINKS] + len(types)
    side = np.array([0] * LINKS + [1] * LINKS, dtype=np.int8)
    return 2 * LINKS, side, group


def layouts():
    two = lambda k: (lambda blk: blk // k)  # noqa: E731  side = block // (blocks per side)
    out = {
        'xl': _square_major(8, two(4)), 'xpn': _square_major(8, two(4)), 'xsl': _square_major(4, two(2)),
        'xx': _square_major(10, two(5)), 'pin': _square_major(10, two(5)), 'pinq': _square_major(10, two(5)),
        'disc': _square_major(12, two(6)), 'forkn': _square_major(2, two(1)), 'forkp': _square_major(2, two(1)),
        'under': _square_major(10, two(5)), 'file': _square_major(12, two(6)), 'block': _square_major(8, two(4)),
        'loose': _square_major(16, two(8)), 'kk': _kk_layout(), 'mat': _mat_layout(),
        'trap': _square_major(8, two(4)), 'trapa': _square_major(8, two(4)),
        'back': _square_major(2, two(1), width=8), 'sev': _square_major(2, two(1)),
        'bad': _square_major(6, two(3)), 'links': _links_layout(),
    }
    return out


FAMILY_NAMES = list(layouts())


# ---- the finders ----

def _line_masks():
    """For each pair of squares on a common line: the squares strictly between, and the line's type."""
    between = {}
    for a in range(64):
        for b in range(64):
            if a == b:
                continue
            ra, fa, rb, fb = a >> 3, a & 7, b >> 3, b & 7
            dr, df = rb - ra, fb - fa
            if dr == 0 or df == 0:
                kind = 'r'
            elif abs(dr) == abs(df):
                kind = 'b'
            else:
                continue
            sr = (dr > 0) - (dr < 0)
            sf = (df > 0) - (df < 0)
            m = 0
            r, f = ra + sr, fa + sf
            while (r, f) != (rb, fb):
                m |= 1 << (r * 8 + f)
                r += sr
                f += sf
            between[(a, b)] = (m, kind)
    return between


BETWEEN = _line_masks()
PAWN_ATT = chess.BB_PAWN_ATTACKS
KNIGHT = chess.BB_KNIGHT_ATTACKS
KING_ATT = chess.BB_KING_ATTACKS
FILE_MASK = [chess.BB_FILES[s & 7] for s in range(64)]
AHEAD = [[0] * 64, [0] * 64]       # squares strictly ahead on the file, for side 0 (up) and side 1 (down)
PASS_SPAN = [[0] * 64, [0] * 64]   # own and neighbouring files ahead
for _s in range(64):
    _r, _f = _s >> 3, _s & 7
    for _rr in range(8):
        for _ff in (_f - 1, _f, _f + 1):
            if not 0 <= _ff < 8:
                continue
            bit = 1 << (_rr * 8 + _ff)
            if _rr > _r:
                PASS_SPAN[0][_s] |= bit
                if _ff == _f:
                    AHEAD[0][_s] |= bit
            if _rr < _r:
                PASS_SPAN[1][_s] |= bit
                if _ff == _f:
                    AHEAD[1][_s] |= bit


def lone_shields(king, shields, occ, rook_sliders, bishop_sliders):
    """The pieces of `shields` that are the only piece between `king` and a slider of the right line type."""
    found = 0
    for s in bits(rook_sliders | bishop_sliders):
        entry = BETWEEN.get((king, s))
        if entry is None:
            continue
        m, kind = entry
        if not (rook_sliders if kind == 'r' else bishop_sliders) >> s & 1:
            continue
        mid = m & occ
        if mid and not mid & (mid - 1) and mid & shields:
            found |= mid
    return found


def position_cells(board):
    """{family: sorted list of cells} for one side-relative board (White = mover)."""
    occ = board.occupied
    by = [board.occupied_co[W], board.occupied_co[B]]
    col = (W, B)
    pcs = [[board.pieces_mask(t, c) for t in range(1, 7)] for c in col]   # [side][kind]
    kings = [board.king(W), board.king(B)]
    # attack masks per piece, the per-class unions and the "at least 1 / at least 2" sets
    per_piece = [[], []]   # (square, kind, mask)
    cls_att = [[0] * 6, [0] * 6]
    att1, att2 = [0, 0], [0, 0]
    for s in (0, 1):
        for k in range(6):
            for sq in bits(pcs[s][k]):
                m = PAWN_ATT[col[s]][sq] if k == 0 else board.attacks_mask(sq)
                per_piece[s].append((sq, k, m))
                cls_att[s][k] |= m
                att2[s] |= att1[s] & m
                att1[s] |= m

    def count(s, sq):
        return sum(1 for _, _, m in per_piece[s] if m >> sq & 1)

    out = {name: [] for name in FAMILY_NAMES}
    for s in (0, 1):
        e = 1 - s
        ea = cls_att[e]
        ep, en, eb, er, eq = ea[0], ea[1], ea[2], ea[3], ea[4]
        minors_e = en | eb
        lower = (pcs[s][1] | pcs[s][2]) & ep | pcs[s][3] & (ep | minors_e) | pcs[s][4] & (ep | minors_e | er)
        by_pn = (pcs[s][1] | pcs[s][2]) & ep | (pcs[s][3] | pcs[s][4]) & (ep | en)
        by_sl = pcs[s][3] & eb | pcs[s][4] & (eb | er)
        nonking = by[s] & ~pcs[s][5]
        exact = lower | (nonking & att1[e] & ~att1[s])
        for k in range(1, 5):
            for sq in bits(lower & pcs[s][k]):
                out['xl'].append((s * 4 + k - 1) * 64 + sq)
            for sq in bits(by_pn & pcs[s][k]):
                out['xpn'].append((s * 4 + k - 1) * 64 + sq)
        for k in (3, 4):
            for sq in bits(by_sl & pcs[s][k]):
                out['xsl'].append((s * 2 + k - 3) * 64 + sq)
        for k in range(5):
            for sq in bits(exact & pcs[s][k]):
                out['xx'].append((s * 5 + k) * 64 + sq)
        # pins: own king, enemy sliders (queens count on both lines)
        rs, bs = pcs[e][3] | pcs[e][4], pcs[e][2] | pcs[e][4]
        pinned = lone_shields(kings[s], by[s], occ, rs, bs)
        for k in range(5):
            for sq in bits(pinned & pcs[s][k]):
                out['pin'].append((s * 5 + k) * 64 + sq)
        pq = 0
        for qsq in bits(pcs[s][4]):
            pq |= lone_shields(qsq, by[s] & ~pcs[s][5], occ, pcs[e][3], pcs[e][2])
        for k in range(5):
            for sq in bits(pq & pcs[s][k]):
                out['pinq'].append((s * 5 + k) * 64 + sq)
        disc = lone_shields(kings[e], by[s], occ, pcs[s][3] | pcs[s][4], pcs[s][2] | pcs[s][4])
        for k in range(6):
            for sq in bits(disc & pcs[s][k]):
                out['disc'].append((s * 6 + k) * 64 + sq)
        # side s's knight fork squares against side e
        targets = pcs[e][5] | pcs[e][4] | pcs[e][3] | ((pcs[e][1] | pcs[e][2]) & ~att1[e])
        reach = 0
        for sq in bits(pcs[s][1]):
            reach |= KNIGHT[sq]
        reach &= ~by[s] & ~cls_att[e][0]
        for d in bits(reach):
            t = KNIGHT[d] & targets
            if t & (t - 1):
                out['forkn'].append(s * 64 + d)
        # side s's pawn-push forks
        big = by[e] & ~pcs[e][0]
        fp = 0
        for sq in bits(pcs[s][0]):
            step = 8 if s == 0 else -8
            d = sq + step
            if not 0 <= d < 64 or occ >> d & 1:
                continue
            dests = [d]
            start_rank = 1 if s == 0 else 6
            d2 = d + step
            if sq >> 3 == start_rank and not occ >> d2 & 1:
                dests.append(d2)
            for dd in dests:
                t = PAWN_ATT[col[s]][dd] & big
                if t & (t - 1):
                    fp |= 1 << dd
        for d in bits(fp):
            out['forkp'].append(s * 64 + d)
        # under-defended, not exposed
        und = by[s] & ~pcs[s][5] & att2[e] & ~exact
        for sq in bits(und):
            if count(s, sq) <= 1:
                k = board.piece_type_at(sq) - 1
                out['under'].append((s * 5 + k) * 64 + sq)
        # file-line contact (rooks and queens, looking forward)
        heavy_s, heavy_e = pcs[s][3] | pcs[s][4], pcs[e][3] | pcs[e][4]
        for k in (3, 4):
            for sq in bits(pcs[s][k]):
                ahead = AHEAD[s][sq] & occ
                if not ahead:
                    state = 2
                else:
                    first = (ahead & -ahead).bit_length() - 1 if s == 0 else ahead.bit_length() - 1
                    state = 0 if heavy_s >> first & 1 else (1 if heavy_e >> first & 1 else None)
                if state is not None:
                    out['file'].append(((s * 2 + k - 3) * 3 + state) * 64 + sq)
        # blockade occupant of passed pawns
        for sq in bits(pcs[s][0]):
            if PASS_SPAN[s][sq] & pcs[e][0]:
                continue
            stop = sq + (8 if s == 0 else -8)
            if not 0 <= stop < 64 or not occ >> stop & 1:
                continue
            if by[s] >> stop & 1:
                cls = 3
            else:
                t = board.piece_type_at(stop)
                cls = 0 if t in (chess.KNIGHT, chess.BISHOP) else (1 if t in (chess.ROOK, chess.QUEEN) else
                                                                    (2 if t == chess.KING else None))
            if cls is not None:
                out['block'].append((s * 4 + cls) * 64 + sq)
        # loose and overprotected (N..Q)
        for k in range(1, 5):
            for sq in bits(pcs[s][k]):
                d = count(s, sq)
                if d == 0:
                    out['loose'].append(((s * 4 + k - 1) * 2) * 64 + sq)
                elif d - count(e, sq) >= 2:
                    out['loose'].append(((s * 4 + k - 1) * 2 + 1) * 64 + sq)
        # trapped (d_mob's safe mobility zero), and trapped while attacked
        for sq, k, m in per_piece[s]:
            if 1 <= k <= 4 and not m & ~by[s] & ~cls_att[e][0]:
                out['trap'].append((s * 4 + k - 1) * 64 + sq)
                if att1[e] >> sq & 1:
                    out['trapa'].append((s * 4 + k - 1) * 64 + sq)
        # back rank
        ks = kings[s]
        home, second = (0, 1) if s == 0 else (7, 6)
        if ks >> 3 == home:
            flights = KING_ATT[ks] & chess.BB_RANKS[second]
            if (flights & ~by[s]) == 0 and not (heavy_s & chess.BB_RANKS[home]) and heavy_e:
                out['back'].append(s * 8 + (ks & 7))
        # the absolute 7th (rooks)
        r7, r8 = (6, 7) if s == 0 else (1, 0)
        if kings[e] >> 3 == r8:
            for sq in bits(pcs[s][3] & chess.BB_RANKS[r7]):
                out['sev'].append(s * 64 + sq)
        # the bad bishop
        if pcs[s][2]:
            fwd = 8 if s == 0 else -8
            rammed_light = rammed_dark = 0
            for sq in bits(pcs[s][0]):
                d = sq + fwd
                if 0 <= d < 64 and pcs[e][0] >> d & 1:
                    if LIGHT >> sq & 1:
                        rammed_light += 1
                    else:
                        rammed_dark += 1
            for sq in bits(pcs[s][2]):
                n = rammed_light if LIGHT >> sq & 1 else rammed_dark
                if n:
                    out['bad'].append((s * 3 + min(n, 3) - 1) * 64 + sq)
    # the king pair
    m, o = kings
    if m & 7 < 4:
        m, o = m ^ 7, o ^ 7
    out['kk'].append(((m >> 3) * 4 + (m & 7) - 4) * 64 + o)
    # material ordinals
    for s in (0, 1):
        n = [popcount(pcs[s][k]) for k in range(5)]
        base = s * 19
        caps = (8, 3, 3, 3, 2)
        offs = (0, 8, 11, 14, 17)
        for k in range(5):
            for t in range(min(n[k], caps[k])):
                out['mat'].append(base + offs[k] + t)
    bish = [(popcount(pcs[s][2] & LIGHT), popcount(pcs[s][2] & ~LIGHT & M64)) for s in (0, 1)]
    for s in (0, 1):
        if bish[s][0] and bish[s][1]:
            out['mat'].append(38 + s)
    if sum(bish[0]) == 1 and sum(bish[1]) == 1 and bish[0][0] != bish[1][0]:
        out['mat'].append(40)
    # the pawn links of both perspectives
    out['links'] = (contacts.link_features(board, W, LINK_RANKS) +
                    [LINKS + c for c in contacts.link_features(board, B, LINK_RANKS)])
    for name in out:
        out[name] = sorted(out[name])
    return out


def base_cells(packed):
    """The base table's cells: (colour relative to the mover) * 384 + kind * 64 + square."""
    return [(code >> 3) * 384 + (code & 7) * 64 + sq for code, sq in zip(packed[0::2], packed[1::2])]


def phase_of(packed):
    w = (0, 1, 1, 2, 4, 0)
    return sum(w[code & 7] for code in packed[0::2])


def folds_of(n):
    return (np.arange(n) // BLOCK) % FOLDS


def label_of(scores):
    return 1.0 / (1.0 + np.exp(-scores / TRAIN_SCALE))
