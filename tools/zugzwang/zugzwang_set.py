# SPDX-License-Identifier: GPL-3.0-or-later
"""The tablebase-checked zugzwang set (owner's order, 2026-11-12, for B6, null-move verification at depth, a
TCEC-safety item): positions where having the move costs the side to move its tablebase result, found by probing
tablebases with each side to move, and a runner that searches them with Fork builds and reports which it solves.

**Zugzwang, exactly** (declared before any position was drawn, 2026-11-12). A position P (side to move S, not in
check, no castling right, no en-passant square, halfmove clock 0, at least one legal move) and P', the same
placement with the other side O to move (legal, since S is not in check), are both probed. a = WDL(P) for S and
b = WDL(P') for O, each on the tablebase's 5-valued scale (+2 won, +1 cursed win, 0 drawn, -1 blessed loss, -2
lost). P is kept only when a and b are both exact (-2, 0 or +2: no fifty-move ambiguity) and a + b < 0, which
says S would do better if it could pass (S's result with O to move is -b > a). The condition is symmetric: a + b
< 0 is also O's zugzwang in P', so with WDL alone every zugzwang found is mutual (a one-sided zugzwang, where
only one side loses by moving, needs distance-to-mate or distance-to-zero data and is not in this set). The
types, by (a, b): **D/L** (0, -2): S to move draws, O to move loses, so S would win by passing; **L/D** (-2, 0):
S to move loses, O to move draws; **L/L** (-2, -2): whoever moves loses. a is never +2.
**Null-move eligible**: Fork tries a null move only for a side with a knight, bishop, rook or queen
(src/search/searcher.cpp, has_non_pawn_material), so P is kept only when S has one; a pawn-only zugzwang can
never meet a null move at its own node.
**Kept moves**: for a D/L position, the legal moves whose child keeps the draw for S (child WDL for O, mapped
+-1 to drawn: the fifty-move rule decides those, and Fork plays by it); a lost position keeps every move ('*').

**Source 1, random placements** (`scan`, then `generate`): for every material of the Syzygy 3-4-5 directory
(every .rtbw file), random placements (the material's first side White or Black at random, the side to move at
random, pawns on ranks 2-7, kept when legal, the side to move not in check and having a legal move), each probed
both ways; the frequency is the share of draws that are null-move-eligible zugzwangs. **Measured** (2026-11-12,
`scan --n 20000`, 2,900,000 draws over 145 materials): 4 eligible zugzwangs in all, one each in KNPvK, KBNvKN,
KNPvKN and KQPvKQ (5e-5 each), none in any other material (KRPvKR, KQvKR, KBPvKB and KRvKP included; a quiet-only
trial, no capture or promotion for either side, found 1 in 170,477 quiet KRPvKR draws). **Selection rule**
(declared after the scan, before `generate` drew a position): per piece count, the TOP[n] materials of highest
frequency (ties by name) with frequency at least MIN_FREQ (any material with a zugzwang among its draws), then up
to PER_MATERIAL positions of each in at most MAX_TRIES draws, with one RNG per material seeded 'SEED:MATERIAL',
the first eligible zugzwangs drawn, no placement twice (board alone, so P and P' never both appear).
At that rate (about 1.4 in a million draws over all materials) random placements cannot fill a 6-7-piece
stratum at ChessTB's speed (about 1,000 probes a second here), so `scan67` and `generate67` (the same rules on
the `full/` materials) were not run on 2026-11-12, and the 6-7-piece rows come from:
**Source 2, Fork's own self-play** (`harvest`, then `find` and `find67`, then `select`): every position of the
named viriformat game files with at most 7 pieces (the rules of game_positions; 6-7 pieces only in a material
with a ChessTB `full/` table), distinct by board and side to move, at most HARVEST_PER_GROUP of each piece count
drawn with a seeded RNG, each probed both ways like source 1; then at most SELECT_PER_MATERIAL of each material
(canonical: either colour) drawn with a seeded RNG. These are positions Fork's games reach, Fork's own data
(no other engine involved). **Run** (2026-11-12): the shards td80-g3j-w00.vf and td80-g3j-w01.vf (Fork's 8b
self-play arms, ~/fork-data/8b/arms; 155 MB each), `--per-group 400000`: none of 62,543 distinct 5-piece
positions (the first table position of each game) is an eligible zugzwang; of 893,497 distinct 6-piece and 491,945
7-piece candidates, 400,000 of each were drawn and probed, 216 eligible zugzwangs (145 D/L, 71 L/D), of 14
materials; `select` kept 112. Both sources' rows were re-verified on ChessTB (`verify67 --min-pieces 3`: the
3-5-piece rows on ChessTB's shipping files, a generator independent of Syzygy, kept moves included): 149 of 149
equal.

**Probers.** 3-5 pieces: upstream python-chess's chess.syzygy (Fork's .venv) on the local Syzygy 3-4-5 tables.
6-7 pieces: chess.chesstb of the python-chess fork pinned in heldout_67.PROBER, in WSL's own venv
(~/fork-tools/chesstb-venv), never in Fork's .venv; each table file's size and SHA-256 are checked against the
download records first (heldout_67.checked), and the probe directory holds links to exactly the materials a
position and its children can reach (the `full/` file of the material, plus every `full/` file and every
shipping 3-5-piece file on disk, so a capture's child is probed too; a child whose table is missing leaves the
row's kept moves unknown, '?').

**Solved** (declared before any engine run, 2026-11-12), from the engine's last reported score s for the side to
move: a lost position is solved when s <= -100 cp (or a mate against S); a drawn (D/L) one when |s| <= 200 cp
and the move played is a kept move. The cp thresholds are tools/nnue/endgame_check.py's misjudged thresholds
(won below +100, lost above -100, drawn beyond +-200), reused, not new.

    zugzwang_set.py scan --syzygy DIR --out SCAN.tsv [--n 600] [--seed 2026111260]
    zugzwang_set.py scan67 --source DIR --plan PLAN.tsv --manifest MANIFEST.jsonl --work DIR --out SCAN.tsv
    zugzwang_set.py generate --syzygy DIR --scan SCAN.tsv --out PART.tsv
    zugzwang_set.py generate67 --source DIR --plan PLAN.tsv --manifest MANIFEST.jsonl --work DIR --scan SCAN.tsv
                               --out PART.tsv
    zugzwang_set.py harvest --vf GAMES.vf... --out CANDS.txt [--per-group 200000]
    zugzwang_set.py find --cands CANDS.txt --syzygy DIR --out FOUND345.tsv
    zugzwang_set.py find67 --cands CANDS.txt --source ... --work DIR --out FOUND67.tsv   (WSL's ChessTB venv)
    zugzwang_set.py select FOUND.tsv... --out PART.tsv [--per-material 24]
    zugzwang_set.py merge PART.tsv... --out tools/zugzwang/zugzwang_set.tsv
    zugzwang_set.py published --html PAGE.html --out tools/zugzwang/published_cpw.tsv
    zugzwang_set.py verify SET.tsv --syzygy DIR                    (rows of 3-5 pieces)
    zugzwang_set.py verify67 SET.tsv --source ... --work DIR [--min-pieces 3]   (6-7, or all, on ChessTB)
    zugzwang_set.py run SET.tsv --engine NAME=EXE... --nodes N[,N...] --out RESULTS.jsonl
                        [--syzygy DIR --max-pieces 5] [--hash 64] [--parallel]
    zugzwang_set.py report SET.tsv RESULTS.jsonl [--base NAME] [--json OUT]

`run` drives each engine over plain UCI pipes (as tools/solve_suite.py does), Threads 1, a `ucinewgame` before
every position, `go nodes N`, at below-normal priority on Windows; a restart skips the results already written.

**First run** (2026-11-12, B6 null-move verification; clang-v3 Windows builds of 7b6aa17 (off), f4af4ee (on,
NullVerifyMinDepth 6) and e9b246f (on, 10), bench 9,639,207 / 9,646,339 / 9,946,893 as their commits state;
Hash 64, Threads 1, no tables): solved of 149 at 1M nodes off 138, on6 141, on10 141; at 5M 142, 140, 142; at
25M 142, 143, 142. Every D/L row is solved by every build at every budget; the differences are lost (L/D) rows.
Only B6 solves at 1M: z026 (off -64, on -305) and z131 (off -35, on -158), plus threshold cases near -100 (z037
for on10 and z112 for on6 at 1M, z111 for on6 at 25M); off solves and on6 does not at 5M: z105 (-137 against
-65) and z111 (-100 against -92). Six rows no build solves at any budget: five KBNvKN losses scored -41 to -77
(also with Syzygy on: Fork probes only at a zero halfmove clock) and z141 (about -95). Mean depth at 25M: off
39.06, on6 38.47, on10 38.75.
The five published positions: zugzwang.005's Nxd5 found only with B6 (5M and 25M, both depths); zugzwang.001's
Rf1 by all, scored 0 off and +140 to +211 on; zugzwang.002's Kh6 by all; zugzwang.003 and .004 by none.
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

import chess

HERE = Path(__file__).resolve().parent
SEED = 2026111260
SCAN_N = 600
MIN_FREQ = 1e-9  # any material with a zugzwang among its scan draws
TOP = {3: 2, 4: 8, 5: 10, 6: 6, 7: 3}
PER_MATERIAL = 12
HARVEST_PER_GROUP = 200_000
SELECT_PER_MATERIAL = 24
MAX_TRIES = 2_000_000
EXACT = (-2, 0, 2)
LOST_CP = -100
DRAWN_CP = 200
KIND = {'P': chess.PAWN, 'N': chess.KNIGHT, 'B': chess.BISHOP, 'R': chess.ROOK, 'Q': chess.QUEEN, 'K': chess.KING}
CPW_URL = 'https://www.chessprogramming.org/Null_Move_Test-Positions'
COLUMNS = ['id', 'source', 'pieces', 'material', 'type', 'wdl_stm', 'wdl_other_to_move', 'kept_moves', 'fen']
HEADER = ('# zugzwang set: tools/zugzwang/zugzwang_set.py (generate, generate67, merge). wdl_stm: WDL of the '
          'position for the side to move; wdl_other_to_move: WDL of the same placement with the other side to move, '
          'for that side; kept_moves: the moves keeping the draw (D/L) or * (lost); ? unknown')


# ------------------------------------------------------------------------------------------------- definitions
def zugzwang_type(a, b):
    """'D/L', 'L/D' or 'L/L' when P (a = WDL for its side to move) and P' (b = WDL for the other side, to move)
    make a zugzwang with both values exact; None otherwise."""
    if a not in EXACT or b not in EXACT or a + b >= 0:
        return None
    return {(0, -2): 'D/L', (-2, 0): 'L/D', (-2, -2): 'L/L'}[(a, b)]


def has_piece(board, colour):
    return any(board.pieces(k, colour) for k in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN))


def other_to_move(board):
    p = board.copy(stack=False)
    p.turn = not p.turn
    return p


def placement(rng, material):
    """A random placement of `material` by the scan's rule, or None when this draw is rejected."""
    first, second = material.split('v')
    strong = rng.choice([chess.WHITE, chess.BLACK])
    ps = [(KIND[p], strong) for p in first] + [(KIND[p], not strong) for p in second]
    squares = rng.sample(range(64), len(ps))
    if any(kind == chess.PAWN and sq // 8 in (0, 7) for (kind, _), sq in zip(ps, squares)):
        return None
    b = chess.Board(None)
    for (kind, colour), sq in zip(ps, squares):
        b.set_piece_at(sq, chess.Piece(kind, colour))
    b.turn = rng.choice([chess.WHITE, chess.BLACK])
    if not b.is_valid() or b.is_check() or b.is_checkmate() or b.is_stalemate():
        return None
    if not other_to_move(b).is_valid():
        return None
    return b


def child_wdl(probe, child):
    """WDL of a child for its side to move; a finished game is scored here, not probed."""
    if child.is_checkmate():
        return -2
    if child.is_stalemate() or child.is_insufficient_material():
        return 0
    return probe(child)


def kept_moves(probe, board, a):
    """The moves keeping the draw of a drawn position ('*' for a lost one: no move changes a loss)."""
    if a == -2:
        return '*'
    keep = []
    for m in board.legal_moves:
        c = board.copy(stack=False)
        c.push(m)
        try:
            w = child_wdl(probe, c)
        except Exception:  # a child table is missing (ChessTB 6-7): the row's kept moves are unknown
            return '?'
        if -w in (-1, 0, 1):
            keep.append(m.uci())
    return ' '.join(sorted(keep))


def classify(probe, b):
    """(type, a, bv) for a placement, type None when it is not an eligible zugzwang (then a and bv may be None:
    a side to move without a piece is not probed, and P' only when a can be part of a zugzwang)."""
    if not has_piece(b, b.turn):
        return None, None, None
    a = probe(b)
    if a not in (0, -2):
        return None, a, None
    bv = probe(other_to_move(b))
    return zugzwang_type(a, bv), a, bv


# ------------------------------------------------------------------------------------------------------ probers
def syzygy_prober(directory):
    import chess.syzygy
    tb = chess.syzygy.open_tablebase(directory)
    return tb, tb.probe_wdl


def syzygy_materials(directory):
    return sorted({p.stem for p in Path(directory).glob('*.rtbw')}, key=lambda m: (len(m), m))


def chesstb_setup(source, plan, manifest, work):
    """(prober, materials) over ChessTB: every `full/` WDL file and every shipping 3-5-piece WDL file on disk,
    each checked against the download records (heldout_67.checked), linked into one probe directory."""
    sys.path.insert(0, str(HERE.parent / 'nnue'))
    import chess.chesstb
    import heldout_67 as h
    records = h.load_records(plan, manifest)
    full = sorted(p for p in records if p.startswith('full/wdl/') and (Path(source) / p).exists())
    ship = sorted(p for p in records if p.startswith('wdl/') and p.endswith('.lzw') and len(Path(p).stem) <= 5
                  and (Path(source) / p).exists())
    names = {Path(p).name for p in full}
    materials = []
    for m in h.MATERIALS:
        try:
            h.table_name(m, names)
            materials.append(m)
        except FileNotFoundError:
            pass
    paths = [h.checked(source, rel, records, work) for rel in full + ship]
    tb = chess.chesstb.open_tablebase(str(h.link_dir(work, 'zugzwang-all', paths)))
    return tb, tb.probe_wdl, materials


# --------------------------------------------------------------------------------------------------------- scan
def scan_materials(probe, materials, n, seed):
    rows = []
    for material in materials:
        rng = random.Random(f'{seed}:scan:{material}')
        drawn = tries = 0
        c = Counter()
        while drawn < n and tries < 50 * n:  # a cap on rejected draws
            tries += 1
            b = placement(rng, material)
            if b is None:
                continue
            drawn += 1
            t, a, bv = classify(probe, b)
            if t:
                c[t] += 1
        z = sum(c.values())
        rows.append((material, len(material) - 1, drawn, z, z / max(drawn, 1), c['D/L'], c['L/D'], c['L/L']))
        print(f'{material}: {z}/{drawn} eligible zugzwangs ({100 * z / max(drawn, 1):.2f}%) '
              f'D/L {c["D/L"]} L/D {c["L/D"]} '
              f'L/L {c["L/L"]}', flush=True)
    return rows


def write_scan(rows, out):
    lines = ['material\tpieces\tdrawn\tzugzwangs\tfrequency\tD/L\tL/D\tL/L']
    lines += [f'{m}\t{p}\t{n}\t{z}\t{f:.5f}\t{dl}\t{ld}\t{ll}' for m, p, n, z, f, dl, ld, ll in rows]
    Path(out).write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


def selected(scan_file):
    """The selection rule over a scan file: per piece count, TOP[n] materials of highest frequency >= MIN_FREQ."""
    by_n = defaultdict(list)
    for line in Path(scan_file).read_text(encoding='utf-8').splitlines()[1:]:
        f = line.split('\t')
        if float(f[4]) >= MIN_FREQ:
            by_n[int(f[1])].append((-float(f[4]), f[0]))
    out = []
    for n in sorted(by_n):
        out += [m for _, m in sorted(by_n[n])[:TOP.get(n, 0)]]
    return out


# ----------------------------------------------------------------------------------------------------- generate
def generate_rows(probe, materials, source, per_material=PER_MATERIAL, seed=SEED):
    rows = []
    for material in materials:
        rng = random.Random(f'{seed}:{material}')
        seen, got, tries = set(), 0, 0
        t0 = time.time()
        while got < per_material and tries < MAX_TRIES:
            tries += 1
            b = placement(rng, material)
            if b is None or b.board_fen() in seen:
                continue
            t, a, bv = classify(probe, b)
            if not t:
                continue
            seen.add(b.board_fen())
            got += 1
            rows.append({'source': source, 'pieces': len(material) - 1, 'material': material, 'type': t,
                         'wdl_stm': a, 'wdl_other_to_move': bv, 'kept_moves': kept_moves(probe, b, a),
                         'fen': b.fen()})
        print(f'{material}: {got} positions in {tries} draws ({time.time() - t0:.1f} s)', flush=True)
    return rows


# ------------------------------------------------------------------------------------------------------ harvest
PIECE_OF = {0: chess.PAWN, 1: chess.KNIGHT, 2: chess.BISHOP, 3: chess.ROOK, 4: chess.QUEEN, 5: chess.KING}
CORNERS = (0, 7, 56, 63)


def game_positions(path, max_pieces):
    """(game number, board) for every position of a viriformat game file (Fork's self-play shards; the format as
    tools/datagen/verify_games.py reads it) with at most max_pieces pieces, no castling right left (a corner
    rook's code-6 right, dropped when its king or rook moves or the rook is taken) and no en-passant capture
    possible (the position right after a pawn's two-square move is skipped), the side to move not in check, with a
    legal move and a piece. Games are replayed from their headers with an array; a board is built only when the
    piece count qualifies. A truncated last game is ignored."""
    data = Path(path).read_bytes()
    i, end, game = 0, len(data), 0
    while i + 32 <= end:
        h = data[i:i + 32]
        occ = int.from_bytes(h[0:8], 'little')
        arr, rights, k, o = [-1] * 64, set(), 0, occ
        while o:
            sq = (o & -o).bit_length() - 1
            o &= o - 1
            code = h[8 + k // 2] >> (4 * (k % 2)) & 15
            k += 1
            if code & 7 == 6:
                rights.add(sq)
                code = (code & 8) | 3
            arr[sq] = code
        black = bool(h[24] & 128)
        ep_now = (h[24] & 127) != 64
        j, moves = i + 32, []
        while j + 4 <= end:
            code = data[j] | data[j + 1] << 8
            j += 4
            if code == 0:
                break
            moves.append(code)
        else:
            return
        count = bin(occ).count('1')
        for step in range(len(moves) + 1):
            if count <= max_pieces and not rights and not ep_now:
                b = chess.Board(None)
                for sq in range(64):
                    if arr[sq] >= 0:
                        b.set_piece_at(sq, chess.Piece(PIECE_OF[arr[sq] & 7], not arr[sq] & 8))
                b.turn = chess.BLACK if black else chess.WHITE
                if (has_piece(b, b.turn) and b.is_valid() and not b.is_check() and not b.is_checkmate()
                        and not b.is_stalemate() and other_to_move(b).is_valid()):
                    yield game, b
            if step == len(moves):
                break
            code = moves[step]
            frm, to, promo, kind = code & 63, code >> 6 & 63, code >> 12 & 3, code >> 14
            piece = arr[frm]
            if piece & 7 == 5:
                rights -= {c for c in CORNERS if (c < 8) == (not piece & 8)}
            rights -= {frm, to}
            ep_now = piece & 7 == 0 and abs(to - frm) == 16
            arr[frm] = -1
            if kind == 2:  # castling: the king's move to its own rook's square
                rook = arr[to]
                arr[to] = -1
                base = frm & 56
                kd, rd = (base + 6, base + 5) if (to & 7) > (frm & 7) else (base + 2, base + 3)
                arr[kd], arr[rd] = piece, rook
            else:
                if arr[to] >= 0:
                    count -= 1
                if kind == 1:
                    arr[(frm & 56) | (to & 7)] = -1
                    count -= 1
                elif kind == 3:
                    piece = (piece & 8) | (promo + 1)
                arr[to] = piece
            black = not black
        i = j
        game += 1


VALUE = {'K': 0, 'Q': 9, 'R': 5, 'B': 3, 'N': 3, 'P': 1}


def table_materials_67():
    """The 6-7-piece materials with a ChessTB `full/` table (tools/nnue/heldout_67.py's list)."""
    sys.path.insert(0, str(HERE.parent / 'nnue'))
    import heldout_67
    return list(heldout_67.MATERIALS)


def canonical(material, known=()):
    """One name per material whatever the colours: the orientation in `known` if either is there, else the side of
    higher value first (Q 9, R 5, B and N 3, P 1; ties by the longer, then the larger string)."""
    a, b = material.split('v')
    for m in (f'{a}v{b}', f'{b}v{a}'):
        if m in known:
            return m
    key = lambda s: (sum(VALUE[c] for c in s), len(s), s)  # noqa: E731
    return f'{a}v{b}' if key(a) >= key(b) else f'{b}v{a}'


def harvest(paths, max_pieces, per_group, seed, table_67=None):
    """Distinct (board, side to move) candidates from the game files (with table_67, a 6-7-piece one only when
    its material is in it), then at most per_group of each piece count, drawn with
    random.Random('SEED:harvest:N') in first-seen order."""
    groups, seen = defaultdict(list), set()
    for p in paths:
        t0 = time.time()
        n0 = sum(len(g) for g in groups.values())
        for game, b in game_positions(p, max_pieces):
            n = len(b.piece_map())
            if table_67 is not None and n >= 6 and canonical(material_of(b), table_67) not in table_67:
                continue
            key = (b.board_fen(), b.turn)
            if key in seen:
                continue
            seen.add(key)
            groups[len(b.piece_map())].append(b.fen())
        print(f'{p}: {sum(len(g) for g in groups.values()) - n0} new candidates ({time.time() - t0:.0f} s)', flush=True)
    out = []
    for n in sorted(groups):
        fens = groups[n]
        if len(fens) > per_group:
            fens = random.Random(f'{seed}:harvest:{n}').sample(fens, per_group)
        out += fens
        print(f'{n} pieces: {len(groups[n])} distinct candidates, {min(len(groups[n]), per_group)} kept', flush=True)
    return out


def find_rows(probe, fens, source, materials=None):
    """The eligible zugzwangs among candidate FENs (materials: the ones a prober covers, either side first;
    None for every material)."""
    rows, c = [], Counter()
    t0 = time.time()
    for fen in fens:
        b = chess.Board(fen)
        m = canonical(material_of(b), materials or ())
        if materials is not None and m not in materials:
            c['no table'] += 1
            continue
        c['probed'] += 1
        t, a, bv = classify(probe, b)
        if not t:
            continue
        c[t] += 1
        rows.append({'source': source, 'pieces': len(b.piece_map()), 'material': m, 'type': t, 'wdl_stm': a,
                     'wdl_other_to_move': bv, 'kept_moves': kept_moves(probe, b, a), 'fen': b.fen()})
    print(f'{len(fens)} candidates: {dict(c)} ({time.time() - t0:.0f} s)', flush=True)
    return rows


def select(found_files, per_material, seed):
    """At most per_material rows of each material from the found files (drawn with random.Random('SEED:select:
    MATERIAL') when there are more), no placement twice (the first file's row wins)."""
    by_m, seen = defaultdict(list), set()
    for f in found_files:
        for r in read_rows(f):
            key = chess.Board(r['fen']).board_fen()
            if key not in seen:
                seen.add(key)
                by_m[r['material']].append(r)
    out = []
    for m in sorted(by_m):
        rs = by_m[m]
        if len(rs) > per_material:
            rs = random.Random(f'{seed}:select:{m}').sample(rs, per_material)
        out += rs
    return out


def write_rows(rows, out, header=HEADER):
    lines = [header, '\t'.join(COLUMNS)]
    for r in rows:
        lines.append('\t'.join(str(r.get(c, '')) for c in COLUMNS))
    Path(out).write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


def read_rows(path):
    lines = [l for l in Path(path).read_text(encoding='utf-8').splitlines() if l and not l.startswith('#')]
    cols = lines[0].split('\t')
    rows = []
    for l in lines[1:]:
        r = dict(zip(cols, l.split('\t')))
        for k in ('pieces', 'wdl_stm', 'wdl_other_to_move'):
            if r.get(k, '') != '':
                r[k] = int(r[k])
        rows.append(r)
    return rows


def merge(parts, out):
    rows, seen = [], set()
    for p in parts:
        for r in read_rows(p):
            key = chess.Board(r['fen']).board_fen()
            if key in seen:
                raise SystemExit(f'{r["fen"]}: placement twice')
            seen.add(key)
            rows.append(r)
    rows.sort(key=lambda r: (r['pieces'], r['material']))
    for i, r in enumerate(rows, 1):
        r['id'] = f'z{i:03d}'
    write_rows(rows, out)
    counts = sorted(Counter(r['material'] for r in rows).items())
    print(f'{len(rows)} positions: ' + ', '.join(f'{k} {v}' for k, v in counts))


def material_of(board):
    """White's pieces, then Black's, each in K Q R B N P order: 'KRPvKR'."""
    order = 'KQRBNP'
    side = [''.join(sorted((p.symbol().upper() for p in board.piece_map().values() if p.color == c),
                           key=order.index)) for c in (chess.WHITE, chess.BLACK)]
    return 'v'.join(side)


EPD_LINE = re.compile(r'^\s*(\S+ [wb] \S+ \S+) (\d+) (\d+) bm ([^;]+);\s*id "([^"]+)";')


def published_rows(html_file):
    """The rows of the Chess Programming Wiki's 'Null Move Test-Positions' page (CPW_URL), read from the saved
    page: each EPD line's position, its best moves (bm, converted from SAN to UCI) and its id. Their zugzwang
    claims are the page's, not tablebase-checked (more than 7 pieces, or a material without a table here)."""
    import html as html_lib
    text = html_lib.unescape(re.sub(r'<[^>]+>', '\n', Path(html_file).read_text(encoding='utf-8')))
    rows = []
    for line in text.splitlines():
        m = EPD_LINE.match(line)
        if not m:
            continue
        b = chess.Board(f'{m.group(1)} {m.group(2)} {m.group(3)}')
        best = sorted(b.parse_san(s).uci() for s in m.group(4).split())
        rows.append({'id': f'c{len(rows) + 1:03d}', 'source': f'cpw:{m.group(5)}', 'pieces': len(b.piece_map()),
                     'material': canonical(material_of(b)), 'type': 'published', 'wdl_stm': '', 'wdl_other_to_move': '',
                     'kept_moves': ' '.join(best), 'fen': b.fen()})
    return rows


# ------------------------------------------------------------------------------------------------------- verify
def verify_row(probe, r):
    """Every claim of a row, checked again; a list of the claims that fail."""
    bad = []
    b = chess.Board(r['fen'])
    if b.castling_rights or b.ep_square is not None or b.halfmove_clock != 0 or not b.is_valid():
        bad.append('not a castling-free, en-passant-free legal position with halfmove 0')
        return bad
    if b.is_check() or b.is_game_over():
        bad.append('side to move in check or game over')
    if not has_piece(b, b.turn):
        bad.append('side to move has no piece (never null-move eligible)')
    a, bv = probe(b), probe(other_to_move(b))  # both sides to move, probed afresh
    t = zugzwang_type(a, bv)
    if (a, bv) != (r['wdl_stm'], r['wdl_other_to_move']):
        bad.append(f'WDL {a}/{bv}, the row says {r["wdl_stm"]}/{r["wdl_other_to_move"]}')
    if t != r['type']:
        bad.append(f'type {t}, the row says {r["type"]}')
    if len(b.piece_map()) != r['pieces']:
        bad.append('piece count')
    k = kept_moves(probe, b, a)
    if k != r['kept_moves']:
        bad.append(f'kept moves {k!r}, the row says {r["kept_moves"]!r}')
    return bad


def verify(probe, rows):
    fails = 0
    for r in rows:
        bad = verify_row(probe, r)
        if bad:
            fails += 1
            print(f'{r["id"]} {r["fen"]}: ' + '; '.join(bad))
    print(f'verified {len(rows)} rows: {len(rows) - fails} ok, {fails} failed')
    return fails


# ---------------------------------------------------------------------------------------------------------- run
INFO = re.compile(r'\bdepth (\d+)\b.*?\bscore (cp|mate) (-?\d+)')


def parse_info(line):
    """(depth, kind, value, nodes, time ms) of an info line with a score, or None."""
    m = INFO.search(line)
    if not m or ' lowerbound' in line or ' upperbound' in line:
        return None
    nodes = re.search(r'\bnodes (\d+)', line)
    ms = re.search(r'\btime (\d+)', line)
    return (int(m.group(1)), m.group(2), int(m.group(3)), int(nodes.group(1)) if nodes else 0,
            int(ms.group(1)) if ms else 0)


class Engine:
    def __init__(self, exe, options):
        flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
        self.p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
                                  creationflags=flags)
        self.send('uci')
        self.wait('uciok')
        for k, v in options.items():
            self.send(f'setoption name {k} value {v}')
        self.ready()

    def send(self, s):
        self.p.stdin.write(s + '\n')
        self.p.stdin.flush()

    def wait(self, token):
        lines = []
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError('engine exited')
            lines.append(line.rstrip('\n'))
            if line.startswith(token):
                return lines

    def ready(self):
        self.send('isready')
        self.wait('readyok')

    def search(self, fen, nodes):
        self.send('ucinewgame')
        self.send(f'position fen {fen}')
        self.ready()
        t0 = time.time()
        self.send(f'go nodes {nodes}')
        lines = self.wait('bestmove')
        wall = time.time() - t0
        last = None
        for l in lines:
            x = parse_info(l)
            if x:
                last = x
        best = lines[-1].split()[1]
        return {'depth': last[0] if last else 0, 'kind': last[1] if last else 'cp', 'score': last[2] if last else 0,
                'nodes': last[3] if last else 0, 'ms': last[4] if last else 0, 'wall': round(wall, 3),
                'bestmove': best}

    def quit(self):
        try:
            self.send('quit')
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


def solved(row, res):
    """(score class agrees, move kept), each None when not meaningful, for one result. A published row (no WDL:
    its zugzwang claim is not tablebase-checked) is judged by its best moves alone."""
    if row['wdl_stm'] == '':
        return None, res['bestmove'] in row['kept_moves'].split()
    if res['kind'] == 'mate':
        cls = 'won' if res['score'] > 0 else 'lost'
        ok_score = cls == 'lost' if row['wdl_stm'] == -2 else False
    else:
        s = res['score']
        ok_score = s <= LOST_CP if row['wdl_stm'] == -2 else abs(s) <= DRAWN_CP
    if row['wdl_stm'] == -2 or row['kept_moves'] == '?':
        return ok_score, None
    return ok_score, res['bestmove'] in row['kept_moves'].split()


def run(set_file, engines, budgets, out, syzygy=None, max_pieces=5, hash_mb=64, parallel=False):
    rows = read_rows(set_file)
    if syzygy:
        rows = [r for r in rows if r['pieces'] <= max_pieces]
    tag = 'syzygy' if syzygy else 'notb'
    done = set()
    if Path(out).exists():
        for l in Path(out).read_text(encoding='utf-8').splitlines():
            if l.strip():
                d = json.loads(l)
                done.add((d['engine'], d['tb'], d['nodes_limit'], d['id']))
    lock = threading.Lock()
    f = open(out, 'a', encoding='utf-8', newline='\n')

    def one(name, exe):
        opts = {'Threads': 1, 'Hash': hash_mb}
        if syzygy:
            opts['SyzygyPath'] = syzygy
        e = Engine(exe, opts)
        try:
            for n in budgets:
                for r in rows:
                    if (name, tag, n, r['id']) in done:
                        continue
                    res = e.search(r['fen'], n)
                    ok_score, ok_move = solved(r, res)
                    d = {'engine': name, 'tb': tag, 'nodes_limit': n, 'id': r['id'], **res,
                         'ok_score': ok_score, 'ok_move': ok_move,
                         'solved': ok_score is not False and ok_move is not False}
                    with lock:
                        f.write(json.dumps(d) + '\n')
                        f.flush()
        finally:
            e.quit()

    if parallel:
        ts = [threading.Thread(target=one, args=(n, x)) for n, x in engines]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
    else:
        for n, x in engines:
            one(n, x)
    f.close()


# ------------------------------------------------------------------------------------------------------- report
def report(set_file, results, base=None, json_out=None):
    rows = {r['id']: r for r in read_rows(set_file)}
    res = [json.loads(l) for l in Path(results).read_text(encoding='utf-8').splitlines() if l.strip()]
    groups = defaultdict(dict)
    for d in res:
        groups[(d['tb'], d['nodes_limit'], d['engine'])][d['id']] = d
    engines = sorted({d['engine'] for d in res})
    base = base or engines[0]
    summary = []
    for (tb, n, eng), g in sorted(groups.items()):
        ids = list(g)
        s = {'tb': tb, 'nodes': n, 'engine': eng, 'positions': len(ids),
             'solved': sum(g[i]['solved'] for i in ids), 'score_ok': sum(g[i]['ok_score'] for i in ids),
             'move_checked': sum(g[i]['ok_move'] is not None for i in ids),
             'move_ok': sum(bool(g[i]['ok_move']) for i in ids),
             'nodes_total': sum(g[i]['nodes'] for i in ids), 'ms_total': sum(g[i]['ms'] for i in ids),
             'mean_depth': round(sum(g[i]['depth'] for i in ids) / max(len(ids), 1), 2),
             'by_type': {}, 'by_pieces': {}}
        for key, field in (('by_type', 'type'), ('by_pieces', 'pieces')):
            c = defaultdict(lambda: [0, 0])
            for i in ids:
                c[str(rows[i][field])][0] += g[i]['solved']
                c[str(rows[i][field])][1] += 1
            s[key] = {k: f'{v[0]}/{v[1]}' for k, v in sorted(c.items())}
        b = groups.get((tb, n, base), {})
        if eng != base and b:
            common = [i for i in ids if i in b]
            s['only_this'] = sorted(i for i in common if g[i]['solved'] and not b[i]['solved'])
            s['only_base'] = sorted(i for i in common if b[i]['solved'] and not g[i]['solved'])
        summary.append(s)
        line = (f'{tb:6} {n:>9} {eng:10} solved {s["solved"]:3}/{len(ids)} (score {s["score_ok"]}, move '
                f'{s["move_ok"]}/{s["move_checked"]}) depth {s["mean_depth"]:5} nodes {s["nodes_total"]} '
                f'time {s["ms_total"] / 1000:.1f} s  by type {s["by_type"]} by pieces {s["by_pieces"]}')
        if 'only_this' in s:
            line += f'\n{"":17} vs {base}: only this solves {s["only_this"]}; only {base} solves {s["only_base"]}'
        print(line)
    if json_out:
        Path(json_out).write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8', newline='\n')
    return summary


# --------------------------------------------------------------------------------------------------------- main
def lower_priority():
    """Below-normal priority (the machine is shared): SetPriorityClass on Windows, nice elsewhere."""
    if os.name == 'nt':
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
    else:
        os.nice(10)


def main(argv=None):
    lower_priority()
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('scan')
    p.add_argument('--syzygy', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--n', type=int, default=SCAN_N)
    p.add_argument('--seed', type=int, default=SEED)
    for name in ('scan67', 'generate67', 'verify67'):
        p = sub.add_parser(name)
        if name == 'verify67':
            p.add_argument('set')
            p.add_argument('--min-pieces', type=int, default=6,
                           help='3: also the 3-5-piece rows, on the shipping ChessTB files')
        p.add_argument('--source', required=True)
        p.add_argument('--plan', required=True)
        p.add_argument('--manifest', required=True)
        p.add_argument('--work', required=True)
        if name != 'verify67':
            p.add_argument('--out', required=True)
        if name == 'scan67':
            p.add_argument('--n', type=int, default=SCAN_N)
            p.add_argument('--seed', type=int, default=SEED)
        if name == 'generate67':
            p.add_argument('--scan', required=True)
    p = sub.add_parser('generate')
    p.add_argument('--syzygy', required=True)
    p.add_argument('--scan', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('harvest')
    p.add_argument('--vf', nargs='+', required=True, help="Fork's self-play game files")
    p.add_argument('--out', required=True)
    p.add_argument('--max-pieces', type=int, default=7)
    p.add_argument('--per-group', type=int, default=HARVEST_PER_GROUP)
    p.add_argument('--seed', type=int, default=SEED)
    p = sub.add_parser('find')
    p.add_argument('--cands', required=True)
    p.add_argument('--syzygy', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('find67')
    p.add_argument('--cands', required=True)
    p.add_argument('--source', required=True)
    p.add_argument('--plan', required=True)
    p.add_argument('--manifest', required=True)
    p.add_argument('--work', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('select')
    p.add_argument('found', nargs='+')
    p.add_argument('--out', required=True)
    p.add_argument('--per-material', type=int, default=SELECT_PER_MATERIAL)
    p.add_argument('--seed', type=int, default=SEED)
    p = sub.add_parser('merge')
    p.add_argument('parts', nargs='+')
    p.add_argument('--out', required=True)
    p = sub.add_parser('published')
    p.add_argument('--html', required=True, help='the saved CPW_URL page')
    p.add_argument('--out', required=True)
    p = sub.add_parser('verify')
    p.add_argument('set')
    p.add_argument('--syzygy', required=True)
    p = sub.add_parser('run')
    p.add_argument('set')
    p.add_argument('--engine', action='append', required=True, help='NAME=EXE')
    p.add_argument('--nodes', required=True, help='comma-separated node budgets')
    p.add_argument('--out', required=True)
    p.add_argument('--syzygy')
    p.add_argument('--max-pieces', type=int, default=5)
    p.add_argument('--hash', type=int, default=64)
    p.add_argument('--parallel', action='store_true')
    p = sub.add_parser('report')
    p.add_argument('set')
    p.add_argument('results')
    p.add_argument('--base')
    p.add_argument('--json')
    a = ap.parse_args(argv)

    if a.cmd == 'scan':
        tb, probe = syzygy_prober(a.syzygy)
        write_scan(scan_materials(probe, syzygy_materials(a.syzygy), a.n, a.seed), a.out)
    elif a.cmd == 'scan67':
        tb, probe, materials = chesstb_setup(a.source, a.plan, a.manifest, a.work)
        write_scan(scan_materials(probe, materials, a.n, a.seed), a.out)
    elif a.cmd == 'generate':
        tb, probe = syzygy_prober(a.syzygy)
        write_rows(generate_rows(probe, selected(a.scan), 'random-placement'), a.out)
    elif a.cmd == 'generate67':
        tb, probe, _ = chesstb_setup(a.source, a.plan, a.manifest, a.work)
        write_rows(generate_rows(probe, selected(a.scan), 'random-placement'), a.out)
    elif a.cmd == 'harvest':
        fens = harvest(a.vf, a.max_pieces, a.per_group, a.seed, set(table_materials_67()))
        Path(a.out).write_text('\n'.join(fens) + '\n', encoding='utf-8', newline='\n')
    elif a.cmd == 'find':
        tb, probe = syzygy_prober(a.syzygy)
        fens = [l for l in Path(a.cands).read_text(encoding='utf-8').splitlines() if l]
        fens = [f for f in fens if len(chess.Board(f).piece_map()) <= 5]
        write_rows(find_rows(probe, fens, 'fork-selfplay', set(syzygy_materials(a.syzygy))), a.out)
    elif a.cmd == 'find67':
        tb, probe, materials = chesstb_setup(a.source, a.plan, a.manifest, a.work)
        fens = [l for l in Path(a.cands).read_text(encoding='utf-8').splitlines() if l]
        fens = [f for f in fens if len(chess.Board(f).piece_map()) >= 6]
        write_rows(find_rows(probe, fens, 'fork-selfplay', set(materials)), a.out)
    elif a.cmd == 'select':
        write_rows(select(a.found, a.per_material, a.seed), a.out)
    elif a.cmd == 'merge':
        merge(a.parts, a.out)
    elif a.cmd == 'published':
        rows = published_rows(a.html)
        write_rows(rows, a.out, f'# published zugzwang positions: the EPD lines of {CPW_URL} (CC BY-SA 3.0), '
                                'read by zugzwang_set.py published; bm converted to UCI in kept_moves; '
                                'zugzwang claims not tablebase-checked')
        print(f'{len(rows)} published positions')
    elif a.cmd == 'verify':
        tb, probe = syzygy_prober(a.syzygy)
        return 1 if verify(probe, [r for r in read_rows(a.set) if r['wdl_stm'] != '' and r['pieces'] <= 5]) else 0
    elif a.cmd == 'verify67':
        tb, probe, _ = chesstb_setup(a.source, a.plan, a.manifest, a.work)
        rows = [r for r in read_rows(a.set) if r['wdl_stm'] != '' and r['pieces'] >= a.min_pieces]
        return 1 if verify(probe, rows) else 0
    elif a.cmd == 'run':
        engines = [tuple(e.split('=', 1)) for e in a.engine]
        run(a.set, engines, [int(x) for x in a.nodes.split(',')], a.out, a.syzygy, a.max_pieces, a.hash,
            a.parallel)
    elif a.cmd == 'report':
        report(a.set, a.results, a.base, a.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
