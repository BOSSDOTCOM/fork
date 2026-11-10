# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent oracle for idea 69's material cells.

Written only from the taxonomy text of the conversion-and-defense report
(docs/research/conversion-defense/report.md on branch
research/conversion-defense, section "Taxonomy"), without reading the
trainer's implementation, so the two can be checked against each other.

A position's cell is "SIGNATURE|SECOND" and its wing class is "two-wing" or
"one-wing".

Signature (P = phase count: knights and bishops 1, rooks 2, queens 4,
both sides):
  Q-MG        a queen on the board, P >= 13
  Q-EG        a queen on the board, P <= 12
  noQ-MG      no queens, rooks and minors, P >= 10
  R+minor-EG  no queens, rooks and minors, P <= 9
  R-EG        rooks only
  minor-EG    minors only (its sub-types are not used here)
  pawn-EG     kings and pawns only

Second field: the imbalance, or for equal pieces the pawn balance:
  Q-imbalance, R-vs-minors, minor-up, other-imbalance, B-vs-N, or
  level / pawn+-1 / pawn+-2+.

Interpretation choices (where the text is ambiguous):
  1. Piece presence for the signature is counted over the whole board, both
     sides together. "A queen on" means at least one queen of either colour.
     "Rooks and minors" means at least one rook and at least one minor on the
     board, whichever sides they belong to; so R vs N (one side has only the
     rook, the other only the knight) is a rooks-and-minors signature, not
     R-EG or minor-EG. "Rooks only" means at least one rook and no minor (no
     queen); "minors only" at least one minor and no rook (no queen);
     "kings and pawns" no queen, rook or minor at all.
  2. P is not capped at 24. Promotions can push it above 24, but every
     threshold (13/12, 10/9) is far below 24, so capping would never change
     a class.
  3. "Minor" means knight or bishop; the minor count is knights + bishops.
  4. The imbalance rules are applied in the listed order, the first that
     holds wins, comparing per-side counts (queens Q, rooks R, minors M,
     bishops B, knights N):
       a. Q-imbalance: the queen counts differ.
       b. R-vs-minors: the rook counts and the minor counts both differ, in
          opposite directions (one side has more rooks, the other more
          minors).
       c. minor-up: queen and rook counts equal, the minor counts differ.
       d. other-imbalance: anything else that is not equal (rook counts
          differ with minor counts equal, or rooks and minors both up for the
          same side).
       e. B-vs-N: queen, rook and minor counts all equal, but the bishop
          counts differ (and so the knight counts, the other way).
       f. equal-pieces: otherwise. Only this case takes the pawn balance as
          the second field; B-vs-N is its own second field, since the text
          lists it beside equal-pieces rather than as part of it.
     Kings are ignored.
  5. Pawn balance: |white pawns - black pawns| = 0 -> "level", 1 ->
     "pawn+-1", >= 2 -> "pawn+-2+". pawn-EG positions (no pieces) are
     equal-pieces, so they always take the pawn balance.
  6. Wings: pawns of either colour count. "two-wing" when at least one pawn
     stands on files a-c and at least one on files f-h; otherwise
     "one-wing". That includes positions with no pawns at all and positions
     whose pawns stand only on files d-e (no pawn on either wing): the text
     offers only "both wings or one", and such a position does not have
     pawns on both wings.
  7. Every rule above uses whole-board presence, absolute differences or
     symmetric comparisons, so the class does not depend on the side to
     move or on which side is up.

Interface: classify_fen(fen), classify_pieces(text), and a command line
(cases / check / count; see main()).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = range(6)
_FEN_KIND = {"p": PAWN, "n": KNIGHT, "b": BISHOP, "r": ROOK, "q": QUEEN, "k": KING}


def _classify(counts: list[list[int]], pawn_files: list[int]) -> tuple[str, str]:
    """counts[side][kind] for two sides; pawn_files: file of every pawn."""
    a, b = counts
    queens = a[QUEEN] + b[QUEEN]
    rooks = a[ROOK] + b[ROOK]
    minors = a[KNIGHT] + a[BISHOP] + b[KNIGHT] + b[BISHOP]
    phase = minors + 2 * rooks + 4 * queens

    if queens:
        sig = "Q-MG" if phase >= 13 else "Q-EG"
    elif rooks and minors:
        sig = "noQ-MG" if phase >= 10 else "R+minor-EG"
    elif rooks:
        sig = "R-EG"
    elif minors:
        sig = "minor-EG"
    else:
        sig = "pawn-EG"

    dq = a[QUEEN] - b[QUEEN]
    dr = a[ROOK] - b[ROOK]
    dm = (a[KNIGHT] + a[BISHOP]) - (b[KNIGHT] + b[BISHOP])
    db = a[BISHOP] - b[BISHOP]
    if dq != 0:
        second = "Q-imbalance"
    elif dr != 0 and dm != 0 and (dr > 0) != (dm > 0):
        second = "R-vs-minors"
    elif dr == 0 and dm != 0:
        second = "minor-up"
    elif dr != 0 or dm != 0:
        second = "other-imbalance"
    elif db != 0:
        second = "B-vs-N"
    else:
        dp = abs(a[PAWN] - b[PAWN])
        second = "level" if dp == 0 else ("pawn+-1" if dp == 1 else "pawn+-2+")

    queenside = any(f <= 2 for f in pawn_files)
    kingside = any(f >= 5 for f in pawn_files)
    wing = "two-wing" if queenside and kingside else "one-wing"
    return f"{sig}|{second}", wing


def classify_fen(fen: str) -> tuple[str, str]:
    """(cell, wing) from a FEN; only the board field is read."""
    fields = fen.split()
    if not fields:
        raise ValueError("empty FEN")
    ranks = fields[0].split("/")
    if len(ranks) != 8:
        raise ValueError(f"board field needs 8 ranks: {fields[0]!r}")
    counts = [[0] * 6, [0] * 6]
    pawn_files: list[int] = []
    for rank in ranks:
        file = 0
        for ch in rank:
            if ch.isdigit():
                file += int(ch)
                continue
            kind = _FEN_KIND.get(ch.lower())
            if kind is None:
                raise ValueError(f"bad piece {ch!r} in {fields[0]!r}")
            counts[0 if ch.isupper() else 1][kind] += 1
            if kind == PAWN:
                pawn_files.append(file)
            file += 1
        if file != 8:
            raise ValueError(f"rank {rank!r} does not have 8 files")
    return _classify(counts, pawn_files)


def classify_pieces(text: str) -> tuple[str, str]:
    """(cell, wing) from the trainer's dump format: tokens "P:S"."""
    counts = [[0] * 6, [0] * 6]
    pawn_files: list[int] = []
    for token in text.split():
        p_text, sep, s_text = token.partition(":")
        if not sep:
            raise ValueError(f"bad token {token!r}")
        piece = int(p_text)
        square = int(s_text)
        kind = piece & 7
        if kind > KING or piece < 0 or piece > 15:
            raise ValueError(f"bad piece code in {token!r}")
        if not 0 <= square < 64:
            raise ValueError(f"bad square in {token!r}")
        counts[1 if piece & 8 else 0][kind] += 1
        if kind == PAWN:
            pawn_files.append(square % 8)
    return _classify(counts, pawn_files)


def _data_lines(path: str):
    with open(path, encoding="utf-8") as fh:
        for number, raw in enumerate(fh, 1):
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            yield number, line


def cmd_cases(path: str) -> int:
    n = mismatches = 0
    for number, line in _data_lines(path):
        parts = [p.strip() for p in line.split(";")]
        if len(parts) != 3:
            print(f"line {number}: malformed: {line}")
            mismatches += 1
            n += 1
            continue
        fen, cell, wing = parts
        n += 1
        try:
            got = classify_fen(fen)
        except ValueError as exc:
            print(f"line {number}: error {exc}: {line}")
            mismatches += 1
            continue
        if got != (cell, wing):
            mismatches += 1
            print(f"line {number}: {fen} ; expected {cell} ; {wing} ; oracle {got[0]} ; {got[1]}")
    print(f"cases {n} mismatches {mismatches}")
    return 1 if mismatches else 0


def cmd_check(path: str) -> int:
    n = mismatches = 0
    for number, line in _data_lines(path):
        # The separator is " | " with its spaces: cell names contain a bare "|".
        parts = [p.strip() for p in line.split(" | ")]
        n += 1
        if len(parts) != 3:
            mismatches += 1
            if mismatches <= 20:
                print(f"line {number}: malformed: {line}")
            continue
        pieces, cell, wing = parts
        try:
            got = classify_pieces(pieces)
        except ValueError as exc:
            mismatches += 1
            if mismatches <= 20:
                print(f"line {number}: error {exc}: {line}")
            continue
        if got != (cell, wing):
            mismatches += 1
            if mismatches <= 20:
                print(f"line {number}: {pieces} | other {cell} | {wing} | oracle {got[0]} | {got[1]}")
    print(f"positions {n} mismatches {mismatches}")
    return 1 if mismatches else 0


def cmd_count(path: str) -> int:
    cells: Counter[str] = Counter()
    wings: Counter[str] = Counter()
    joint: Counter[str] = Counter()
    n = 0
    for _, line in _data_lines(path):
        pieces = line.split(" | ", 1)[0]
        cell, wing = classify_pieces(pieces)
        n += 1
        cells[cell] += 1
        wings[wing] += 1
        joint[f"{cell};{wing}"] += 1
    out = {
        "positions": n,
        "cells": dict(sorted(cells.items())),
        "wings": dict(sorted(wings.items())),
        "joint": dict(sorted(joint.items())),
    }
    print(json.dumps(out, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (
        ("cases", "lines 'FEN ; cell ; wing': report disagreements"),
        ("check", "lines 'PIECES | cell | wing': compare with another implementation"),
        ("count", "lines whose first ' | ' field is PIECES: JSON counts"),
    ):
        p = sub.add_parser(name, help=text)
        p.add_argument("file")
    args = parser.parse_args(argv)
    handler = {"cases": cmd_cases, "check": cmd_check, "count": cmd_count}[args.command]
    return handler(args.file)


if __name__ == "__main__":
    sys.exit(main())
