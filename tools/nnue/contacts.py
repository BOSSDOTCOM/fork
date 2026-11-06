# SPDX-License-Identifier: GPL-3.0-or-later
"""Fork's contact and pawn-link inputs (ideas.md idea 41; DESIGN.md §5.4,
"S512cl"): the Python reference, written from the design (Fork KB
nnue-inputs.md's concepts only) on python-chess's attack sets, apart from
Fork's C++ and the trainer's Rust, so the three can be compared.

Every square is seen in a perspective's frame, the piece inputs' frame:
vertically flipped for Black, then mirrored left-right when that side's own
king is on files a-d. Sides are relative: 0 the perspective's own, 1 the
enemy's. A class is side * 5 + kind (pawn 0, knight 1, bishop 2, rook 3,
queen 4); kings take no part.

Contacts: one input per (attacker class, attacker square, target square,
victim class) for a piece that attacks another on the current board
(python-chess's attacks: sliders stop at the first piece, pawns diagonally
forward), both pieces not kings, not both pawns (the links cover pawn
contact). When two pieces attack each other, one of the two inputs is
implied by the other, so only one is kept: the one whose attacker is the
cheaper piece (pawn < knight = bishop < rook < queen); between pieces of one
kind, the one whose attacker stands on the lower frame square.

Links: one input per unordered pair of pawns, of either side, whose files
are the same or adjacent, and, with a rank limit R, whose ranks are at most
R apart (S512cl: no limit, R = 7; S512+PP: R = 1, owner, 2026-11-06, the
measured speed step; ideas.md 40).

The index space is enumerated once, statically, in a fixed order (the order
the engine and the trainer use too): contacts by attacker class, attacker
square, target square (ascending, over the squares the attacker's kind
reaches from its square on an empty board) and victim class, leaving out
the combinations no position can make active (kings; pawn-pawn; pawns on
the first or last rank; for one kind, the higher attacker square; a queen's
contact with a rook on a line or a bishop on a diagonal; a bishop's or a
queen's with a pawn that attacks it back); links by the pair of pawn slots
(side * 48 + frame square - 8), the lower first.

    contacts.py lists EPD [--count N]   each position's inputs per perspective
        ("FEN | side to move's | the other's": contacts, then links offset by
        the contact count, each list sorted; tests/nnue/s512cl-contacts.txt)
    contacts.py links EPD --ranks R [--count N]   the links alone (numbers
        within the link block of rank limit R, each list sorted;
        tests/nnue/s512pp-links.txt with R = 1)
"""
import sys

import chess

KINDS = 5
VALUE = [1, 2, 2, 3, 4]  # pawn, knight, bishop, rook, queen
PIECE_SQUARES = 768


def frame_of(board, persp):
    """The perspective's square map (python-chess square -> frame square)."""
    def orient(s):
        return s if persp == chess.WHITE else s ^ 56
    flip = 7 if orient(board.king(persp)) % 8 < 4 else 0
    return lambda s: orient(s) ^ flip


def empty_reach(cls, sq):
    """The frame squares the class's kind reaches from `sq` on an empty
    board (own pawns attack up the frame, enemy pawns down)."""
    side, kind = divmod(cls, KINDS)
    colour = chess.WHITE if side == 0 else chess.BLACK
    board = chess.BaseBoard.empty()
    board.set_piece_at(sq, chess.Piece(kind + 1, colour))
    return sorted(board.attacks(sq))


def pawn_attacks_from(side, sq):
    return set(empty_reach(side * KINDS, sq))


def _line(a, b):
    return a % 8 == b % 8 or a // 8 == b // 8


def _diagonal(a, b):
    return abs(a % 8 - b % 8) == abs(a // 8 - b // 8)


def contact_possible(att, a, b, vic):
    """Whether (att, a, b, vic) can be active in some position (b already in
    the attacker's empty-board reach)."""
    (sa, ka), (sv, kv) = divmod(att, KINDS), divmod(vic, KINDS)
    if ka == 0 and not 8 <= a < 56:
        return False
    if kv == 0 and not 8 <= b < 56:
        return False
    if ka == 0 and kv == 0:
        return False
    if ka == kv and a > b:
        return False
    if ka == 4 and kv == 3 and _line(a, b):
        return False
    if ka == 4 and kv == 2 and _diagonal(a, b):
        return False
    if ka in (2, 4) and kv == 0 and a in pawn_attacks_from(sv, b):
        return False
    return True


_TABLES = None
_LINKS = {}
NO_RANK_LIMIT = 7  # S512cl's links: any two ranks
S512PP_RANKS = 1   # S512+PP's links: neighbouring or equal ranks


def linked(qa, qb, ranks):
    """Whether pawns on frame squares qa and qb form a link."""
    return qa != qb and abs(qa % 8 - qb % 8) <= 1 and abs(qa // 8 - qb // 8) <= ranks


def link_table(ranks=NO_RANK_LIMIT):
    """{(slot, slot): link number} of rank limit `ranks`, built once each."""
    if ranks not in _LINKS:
        slots = [(side, sq) for side in (0, 1) for sq in range(8, 56)]
        links = {}
        for i, (si, qi) in enumerate(slots):
            for j in range(i + 1, len(slots)):
                if linked(qi, slots[j][1], ranks):
                    links[(i, j)] = len(links)
        _LINKS[ranks] = links
    return _LINKS[ranks]


def tables():
    """(contact index dict, link index dict), built once: S512cl's."""
    global _TABLES
    if _TABLES is None:
        contacts = {}
        for att in range(2 * KINDS):
            for a in range(64):
                for b in empty_reach(att, a):
                    for vic in range(2 * KINDS):
                        if contact_possible(att, a, b, vic):
                            contacts[(att, a, b, vic)] = len(contacts)
        _TABLES = (contacts, link_table())
    return _TABLES


def contact_count():
    return len(tables()[0])


def link_count(ranks=NO_RANK_LIMIT):
    return len(link_table(ranks))


def contact_features(board, persp):
    """Contact input numbers (0-based within the contact block) of `persp`."""
    contacts, _ = tables()
    f = frame_of(board, persp)
    out = []
    for a_sq, x in board.piece_map().items():
        if x.piece_type == chess.KING:
            continue
        for b_sq in board.attacks(a_sq):
            y = board.piece_at(b_sq)
            if y is None or y.piece_type == chess.KING:
                continue
            if x.piece_type == chess.PAWN and y.piece_type == chess.PAWN:
                continue
            kx, ky = x.piece_type - 1, y.piece_type - 1
            if a_sq in board.attacks(b_sq):  # they attack each other: one is kept
                if VALUE[ky] < VALUE[kx] or (kx == ky and f(b_sq) < f(a_sq)):
                    continue
            att = KINDS * int(x.color != persp) + kx
            vic = KINDS * int(y.color != persp) + ky
            out.append(contacts[(att, f(a_sq), f(b_sq), vic)])
    return sorted(out)


def link_features(board, persp, ranks=NO_RANK_LIMIT):
    """Link input numbers (0-based within the link block of rank limit
    `ranks`) of `persp`."""
    links = link_table(ranks)
    f = frame_of(board, persp)
    slots = sorted((int(board.color_at(s) != persp)) * 48 + f(s) - 8 for s in board.pieces(chess.PAWN, True) |
                   board.pieces(chess.PAWN, False))
    out = []
    for i, a in enumerate(slots):
        for b in slots[i + 1:]:
            if linked(a % 48 + 8, b % 48 + 8, ranks):
                out.append(links[(a, b)])
    return sorted(out)


def lists(board, persp):
    return contact_features(board, persp) + [contact_count() + i for i in link_features(board, persp)]


def main(argv):
    if len(argv) < 2 or argv[0] not in ('lists', 'links') or (argv[0] == 'links' and '--ranks' not in argv):
        print('usage: contacts.py lists EPD [--count N] | contacts.py links EPD --ranks R [--count N]',
              file=sys.stderr)
        return 2
    count = int(argv[argv.index('--count') + 1]) if '--count' in argv else None
    fens = [line.strip() for line in open(argv[1], encoding='utf-8') if line.strip() and not line.startswith('#')]
    if argv[0] == 'links':
        ranks = int(argv[argv.index('--ranks') + 1])
        each = lambda b, p: link_features(b, p, ranks)  # noqa: E731
    else:
        each = lists
    for fen in fens[:count]:
        board = chess.Board(fen)
        print(fen, '|', ' '.join(map(str, each(board, board.turn))), '|',
              ' '.join(map(str, each(board, not board.turn))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
