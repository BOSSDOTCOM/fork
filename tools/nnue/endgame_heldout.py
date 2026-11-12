# SPDX-License-Identifier: GPL-3.0-or-later
"""The held-out endgame check (bug review 2026-11-11, T1; owner, 2026-11-11): Syzygy-labelled endings that the
endgame slice (tools/datagen/endgame_slice.py) cannot generate, so a net's score on them measures what it learned
about endings, not what it remembers of the slice.

Why a new check: tools/nnue/endgame_check.py draws random quiet KPK, KQK and KRK positions, and the slice's
generator draws half of its positions from exactly those three endings (BASIC) with the same placement rule;
898 of the old check's 900 positions are in the slice's ten files verbatim, 509 in slice1-01 alone (the bug
review's count; `overlap --old-check` reproduces both).

**What the slice can generate** (endgame_slice.py `generate`): random legal placements of a material signature,
either colour on either side, from BASIC (3 pieces: KPvK, KQvK, KRvK) or from the signatures Fork's games reach
at table entry (the first position of at most 5 pieces in each game). A capture removes one piece at a time and
the self-play games start with 32, so that first position always has exactly 5 pieces: every slice signature
has 3 or 5 pieces, never 4. **The held-out classes** are therefore
- every 4-piece class (CLASSES_4: the instructive ones), and
- the 5-piece classes absent from the slice's signature list (CLASSES_5: queen against two minor pieces),
and `overlap` confirms both from the slice files themselves (their material-class histogram), besides the exact
position match (board and side to move).

**Positions and labels: endgame_check.py's rules, unchanged.** Random placements with the strong side's colour
and the side to move drawn at random (pawns on ranks 2-7), kept only when legal (python-chess is_valid), quiet
(not in check, no capture available) and not over; the label is the Syzygy WDL from the side to move (3-4-5
tables), a cursed win counted as won and a blessed loss as lost, as endgame_check.py does (the WDL value is kept
in the file, so they can be split out). Misjudged, declared before any run as in endgame_check.py: a won
position below +100 cp, a lost one above -100 cp, a drawn one beyond +-200 cp, from the side to move, by each
net's integer evaluation (R-int, tools/nnue/models.py) at the net's own scale. No position repeats (board and
side to move). Seeded: the committed file tools/nnue/endgame_heldout.tsv is the output of `generate` at the
default seed and size.

    endgame_heldout.py generate --tables DIR [--per-class 200] [--seed 20261111] --out FILE.tsv
    endgame_heldout.py overlap FILE.tsv SLICE.vf... [--old-check]
    endgame_heldout.py check FILE.tsv NET[=LAYOUT]... [--json OUT]   (LAYOUT defaults to tools/nnue/s512pp.json)
    endgame_heldout.py report FILE.tsv CANDIDATE[=LAYOUT] --reference DEFAULT[=LAYOUT] [--flag-ratio 1.15]
                       [--warm-start NET[=LAYOUT]] [--json OUT]

`report` is the network-decision step (owner, 2026-11-11; tools/nnue/gates.sh runs it): both nets' counts, the
ratio, and "FLAG for the owner's review" when the candidate is more than 15% worse than the current default (it
misjudges more than 1.15 times the default's count; the default is the net a promotion would replace). With
--warm-start, a second line gives the candidate's change against the net its run warm-started from, for diagnosis
only (owner, 2026-11-12, about 5:00 PM EST); without it, that line says the change was not reported. It is
reported, never a gate on screening or promotion: the exit status is 0 either way.
"""
import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chess  # noqa: E402

import endgame_check  # noqa: E402

SEED = 20261111
PER_CLASS = 200
FLAG_RATIO = 1.15  # owner, 2026-11-11 and 2026-11-12: flag a candidate more than 15% worse than the current default
CLASSES_4 = ['KQvKR', 'KQvKP', 'KRvKP', 'KRvKB', 'KRvKN', 'KPvKP', 'KQvKQ', 'KRvKR', 'KBvKP', 'KNvKP',
             'KBNvK', 'KBBvK', 'KNNvK', 'KBPvK', 'KNPvK', 'KPPvK']
CLASSES_5 = ['KQvKBN', 'KQvKBB', 'KQvKNN']
CLASSES = CLASSES_4 + CLASSES_5
KIND = {'P': chess.PAWN, 'N': chess.KNIGHT, 'B': chess.BISHOP, 'R': chess.ROOK, 'Q': chess.QUEEN, 'K': chess.KING}
ORDER = 'KQRBNP'
CODE_LETTER = {0: 'P', 1: 'N', 2: 'B', 3: 'R', 4: 'Q', 5: 'K'}  # viriformat piece codes (verify_games.py)
NIBBLE = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}
RECORD = 40  # a slice record: the 32-byte board, one move with its score, the 4-byte terminator


def material_class(sides):
    """'KQvKR' for either colour assignment: the two sides' pieces (strongest first), the larger side first."""
    a, b = (''.join(sorted(s, key=ORDER.index)) for s in sides)
    return f'{a}v{b}' if (len(a), [-ORDER.index(c) for c in a]) >= (len(b), [-ORDER.index(c) for c in b]) \
        else f'{b}v{a}'


def board_class(board):
    return material_class([''.join(chess.piece_symbol(p.piece_type).upper() for p in board.piece_map().values()
                                   if p.color == c) for c in (chess.WHITE, chess.BLACK)])


def random_position(rng, cls, max_tries=1_000_000):
    """A random quiet position of class `cls` by endgame_check.py's rules (either colour for the first side)."""
    first, second = cls.split('v')
    for _ in range(max_tries):
        strong = rng.choice([chess.WHITE, chess.BLACK])
        pieces = [(KIND[p], strong) for p in first] + [(KIND[p], not strong) for p in second]
        squares = rng.sample(range(64), len(pieces))
        if any(kind == chess.PAWN and sq // 8 in (0, 7) for (kind, _), sq in zip(pieces, squares)):
            continue
        b = chess.Board(None)
        for (kind, colour), sq in zip(pieces, squares):
            b.set_piece_at(sq, chess.Piece(kind, colour))
        b.turn = rng.choice([chess.WHITE, chess.BLACK])
        if not b.is_valid() or b.is_check() or any(b.is_capture(m) for m in b.legal_moves) or b.is_game_over():
            continue
        return b
    raise RuntimeError(f'no quiet {cls} position in {max_tries} tries')


def key(board):
    """The slice's own board bytes (endgame_slice.encode's layout: occupancy, then a 4-bit code per piece in square
    order) and the side to move: equal exactly when the boards and the sides to move are equal."""
    occ, nibbles = 0, []
    for sq in range(64):
        p = board.piece_at(sq)
        if p is not None:
            occ |= 1 << sq
            nibbles.append(NIBBLE[p.piece_type] | (8 if p.color == chess.BLACK else 0))
    packed = bytearray(16)
    for k, n in enumerate(nibbles):
        packed[k // 2] |= n << (4 * (k % 2))
    return occ.to_bytes(8, 'little') + bytes(packed), board.turn == chess.BLACK


def generate(tables, per_class=PER_CLASS, seed=SEED):
    """[(class, wdl, board)], per_class positions of each class in CLASSES order, no (board, side) twice."""
    import chess.syzygy
    rng = random.Random(seed)
    out, seen = [], set()
    with chess.syzygy.open_tablebase(tables) as tb:
        for cls in CLASSES:
            made = 0
            while made < per_class:
                b = random_position(rng, cls)
                k = key(b)
                if k in seen:
                    continue
                seen.add(k)
                out.append((cls, tb.probe_wdl(b), b))
                made += 1
    return out


def write(rows, path):
    lines = ['# class\twdl (Syzygy, side to move)\tfen  -- tools/nnue/endgame_heldout.py generate']
    lines += [f'{cls}\t{wdl}\t{b.fen()}' for cls, wdl, b in rows]
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


def read(path):
    rows = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            cls, wdl, fen = line.split('\t')
            rows.append((cls, int(wdl), chess.Board(fen)))
    return rows


def scan(path, wanted):
    """One slice file: {key: count} of the wanted keys found, the material-class histogram, records, sha256."""
    data = Path(path).read_bytes()
    if len(data) % RECORD:
        raise ValueError(f'{path}: {len(data)} bytes, not a whole number of {RECORD}-byte one-move records')
    prefixes = {k[0][:24] for k in wanted}
    found, classes, cache = Counter(), Counter(), {}
    for i in range(0, len(data), RECORD):
        if data[i + 36:i + 40] != b'\0\0\0\0':
            raise ValueError(f'{path}: record {i // RECORD} is not a one-move game')
        head = data[i:i + 24]
        n = int.from_bytes(head[:8], 'little').bit_count()
        packed = head[8:8 + (n + 1) // 2]
        cls = cache.get(packed + bytes([n]))
        if cls is None:
            sides = ['', '']
            for k in range(n):
                code = packed[k // 2] >> (4 * (k % 2)) & 15
                sides[code >> 3] += CODE_LETTER[code & 7]
            cls = cache[packed + bytes([n])] = material_class(sides)
        classes[cls] += 1
        if head in prefixes:
            k = (bytes(head), bool(data[i + 24] & 128))
            if k in wanted:
                found[k] += 1
    return found, classes, len(data) // RECORD, hashlib.sha256(data).hexdigest()


def overlap(check_rows, slice_paths, old_check=False):
    sets = {'held-out': {key(b): board_class(b) for _, _, b in check_rows}}
    if old_check:
        sets['endgame_check.py'] = {key(b): board_class(b) for _, b in endgame_check.positions()}
    wanted = set().union(*sets.values())
    report = {'files': [], 'classes': Counter()}
    hits = {name: Counter() for name in sets}
    for path in slice_paths:
        found, classes, records, sha = scan(path, wanted)
        report['classes'].update(classes)
        per = {}
        for name, s in sets.items():
            f = [k for k in found if k in s]
            hits[name].update(f)
            per[name] = len(f)
        report['files'].append({'file': Path(path).name, 'records': records, 'sha256': sha, 'matches': per})
        print(f'{Path(path).name}: {records} records, sha256 {sha}, matches '
              + ', '.join(f'{n} {c}' for n, c in per.items()), flush=True)
    report['matches'] = {}
    for name, s in sets.items():
        by = Counter(s[k] for k in hits[name])
        report['matches'][name] = {'positions': len(s), 'found_in_any_file': len(hits[name]),
                                   'by_class': dict(sorted(by.items()))}
    held = set(sets['held-out'].values())
    report['held_out_classes_in_slice'] = {c: report['classes'][c] for c in sorted(held) if report['classes'][c]}
    report['piece_counts'] = dict(sorted(Counter(sum(1 for ch in c if ch != 'v') for c in report['classes'])
                                         .items()))
    report['classes'] = dict(report['classes'].most_common())
    return report


def check(rows, nets):
    """{net: {(class, result): [positions, misjudged]}} by endgame_check.py's rule."""
    import models
    out = {}
    for arg in nets:
        path, _, lay = arg.partition('=')
        evaluate, _ = models.evaluator(path, lay or str(HERE / 's512pp.json'))
        t = {}
        for cls, wdl, b in rows:
            kind = endgame_check.verdict(wdl)
            cell = t.setdefault((cls, kind), [0, 0])
            cell[0] += 1
            cell[1] += endgame_check.misjudged(kind, evaluate(b))
        out[Path(path).stem] = t
    return out


def totals(table):
    """(misjudged, positions) of one net's check table."""
    return sum(v[1] for v in table.values()), sum(v[0] for v in table.values())


def flag_line(cand, ct, ref, rt, limit=None):
    """The gate report's line (owner, 2026-11-11: reported in every network decision, not a gate): both counts,
    their ratio, and a flag for the owner's review when the candidate misjudges more than `limit` times the
    current default's count (a rise of more than 15%)."""
    limit = FLAG_RATIO if limit is None else limit
    ratio = ct[0] / rt[0] if rt[0] else float('inf') if ct[0] else 1.0
    flagged = ratio > limit
    line = (f'held-out endgame check: {cand} {ct[0]} of {ct[1]} misjudged, the default {ref} {rt[0]} of {rt[1]}, '
            f'ratio {ratio:.3f}: ' + (f"FLAG for the owner's review (a rise of more than "
                                      f'{100 * (limit - 1):.0f}%)' if flagged else
                                      f'within the flag limit ({limit:.2f}: flagged when more than '
                                      f'{100 * (limit - 1):.0f}% worse)'))
    return line, flagged


def warm_start_line(label, cand, ct, warm=None, wt=None):
    """The diagnosis line beside the flag (owner, 2026-11-12, about 5:00 PM EST): the candidate's misjudged count
    against the net its run warm-started from. Reported only: never flagged, never a gate."""
    if warm is None:
        return f'{label}, change against the warm start: not reported (no warm-start net given)'
    change = ct - wt
    share = f'{100 * change / wt:+.1f}%' if wt else 'no ratio: the warm start misjudges none'
    return (f'{label}, change against the warm start {warm}: {cand} {ct} against {wt}, {change:+d} ({share}); '
            'for diagnosis, not flagged')


def print_check(res):
    names = list(res)
    first = res[names[0]]
    print(f'{"class":7} {"result":6} {"positions":>9}  ' + '  '.join(f'{n:>16}' for n in names))
    for cls in CLASSES:
        for kind in ('won', 'drawn', 'lost'):
            if (cls, kind) in first:
                n = first[(cls, kind)][0]
                print(f'{cls:7} {kind:6} {n:>9}  ' + '  '.join(f'{res[m][(cls, kind)][1]:>16}' for m in names))
    for label, group in (('4-piece', CLASSES_4), ('5-piece', CLASSES_5), ('all', CLASSES)):
        cells = []
        for m in names:
            bad = sum(v[1] for (c, _), v in res[m].items() if c in group)
            alln = sum(v[0] for (c, _), v in res[m].items() if c in group)
            cells.append(f'{bad} of {alln} ({100 * bad / alln:.1f}%)')
        print(f'{label}: ' + '; '.join(f'{m} {c}' for m, c in zip(names, cells)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('generate')
    g.add_argument('--tables', required=True)
    g.add_argument('--per-class', type=int, default=PER_CLASS)
    g.add_argument('--seed', type=int, default=SEED)
    g.add_argument('--out', required=True)
    o = sub.add_parser('overlap')
    o.add_argument('positions')
    o.add_argument('slices', nargs='+')
    o.add_argument('--old-check', action='store_true', help="also match endgame_check.py's 900 positions")
    o.add_argument('--json')
    c = sub.add_parser('check')
    c.add_argument('positions')
    c.add_argument('nets', nargs='+')
    c.add_argument('--json')
    r = sub.add_parser('report', help="a candidate against the current default, flagged above FLAG_RATIO")
    r.add_argument('positions')
    r.add_argument('candidate')
    r.add_argument('--reference', required=True, help='the current default net, NET[=LAYOUT]')
    r.add_argument('--flag-ratio', type=float, default=FLAG_RATIO)
    r.add_argument('--warm-start', help="the net the candidate's run warm-started from, NET[=LAYOUT] (diagnosis only)")
    r.add_argument('--json')
    a = ap.parse_args(argv)
    if a.cmd == 'report':
        rows = read(a.positions)
        (cand, tc), = check(rows, [a.candidate]).items()
        (ref, tr), = check(rows, [a.reference]).items()
        ref = ref if ref != cand else ref + ' (reference)'
        ct, rt = totals(tc), totals(tr)
        line, flagged = flag_line(cand, ct, ref, rt, a.flag_ratio)
        shown = {cand: tc, ref: tr}
        warm, wt = None, None
        if a.warm_start:
            (warm, tw), = check(rows, [a.warm_start]).items()
            warm = warm if warm not in shown else warm + ' (warm start)'
            shown[warm] = tw
            wt = totals(tw)[0]
        print_check(shown)
        print(line)
        print(warm_start_line('held-out endgame check', cand, ct[0], warm, wt))
        if a.json:
            Path(a.json).write_text(json.dumps({'candidate': cand, 'candidate_misjudged': ct[0], 'reference': ref,
                                                'reference_misjudged': rt[0], 'positions': ct[1],
                                                'ratio': ct[0] / rt[0] if rt[0] else None,
                                                'flag_ratio': a.flag_ratio, 'flagged': flagged,
                                                'warm_start': warm, 'warm_start_misjudged': wt,
                                                'warm_start_change': None if warm is None else ct[0] - wt},
                                               indent=1) + '\n', encoding='utf-8')
        return 0
    if a.cmd == 'generate':
        rows = generate(a.tables, a.per_class, a.seed)
        write(rows, a.out)
        wdl = Counter((cls, endgame_check.verdict(w)) for cls, w, _ in rows)
        print(f'{len(rows)} positions, {len(CLASSES)} classes; ' + ', '.join(
            f'{cls} {wdl[(cls, "won")]}/{wdl[(cls, "drawn")]}/{wdl[(cls, "lost")]}' for cls in CLASSES))
        return 0
    rows = read(a.positions)
    if a.cmd == 'overlap':
        rep = overlap(rows, a.slices, a.old_check)
        print(json.dumps({k: rep[k] for k in ('matches', 'held_out_classes_in_slice', 'piece_counts')}, indent=1))
        if a.json:
            Path(a.json).write_text(json.dumps(rep, indent=1) + '\n', encoding='utf-8')
        return 1 if rep['matches']['held-out']['found_in_any_file'] or rep['held_out_classes_in_slice'] else 0
    res = check(rows, a.nets)
    print_check(res)
    if a.json:
        Path(a.json).write_text(json.dumps({m: {f'{c} {k}': v for (c, k), v in t.items()} for m, t in res.items()},
                                           indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
