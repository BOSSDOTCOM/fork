# SPDX-License-Identifier: GPL-3.0-or-later

"""Tallies match PGNs: games, results, Termination tags and the runner's
reason for each result (the last {comment} of the movetext, e.g. "{Black
mates}" or "{Draw by 3-fold repetition}"). Standard library only.

    python3 tools/pgn_summary.py a.pgn [b.pgn ...]

Exit status 1 if any game ended other than by the rules or by
adjudication. Normal endings are the Terminations "normal" and
"adjudication" (fastchess writes the latter for its resign and draw
adjudication, which sprt.sh and run_shard.sh turn on). Every other
Termination, or a reason mentioning time, a forfeit, an illegal move, a
disconnect, a stall, a crash or an abandoned game, is counted by kind and
reported on its own line. (The pinned fastchess, v1.8.2-alpha, has the
Terminations "time forfeit", "illegal move", "abandoned" and "unterminated",
and reasons such as "loses on time", "disconnects", "'s connection stalls",
"makes an illegal move": the strings in its binary, read 2026-10-27.)
"""
import collections
import re
import sys

NORMAL_TERMINATIONS = {'normal', 'adjudication'}
# Kind of an abnormal ending, from the Termination tag and the reason; the
# first match wins.
KINDS = [
    ('time forfeit', re.compile(r'time|forfeit', re.I)),
    ('illegal move', re.compile(r'illegal', re.I)),
    ('stall', re.compile(r'stall', re.I)),
    ('disconnect', re.compile(r'disconnect|connection', re.I)),
    ('crash', re.compile(r'crash', re.I)),
    ('abandoned', re.compile(r'abandon', re.I)),
    ('unterminated', re.compile(r'unterminated', re.I)),
]


def abnormal_kind(termination, reason):
    """None for a game that ended by the rules or by adjudication, else the
    kind of abnormal ending."""
    for kind, pattern in KINDS:
        if pattern.search(termination) or pattern.search(reason):
            return kind
    if termination.lower() not in NORMAL_TERMINATIONS:
        return f'other termination "{termination}"'
    return None


def games(text):
    # A game is its tag section followed by its movetext.
    for block in re.split(r'\n\s*\n(?=\[Event )', text.strip()):
        if block.strip():
            yield block


def main(paths):
    bad = collections.Counter()
    for path in paths:
        with open(path, encoding='utf-8', errors='replace') as f:
            text = f.read()
        results, terms, reasons = collections.Counter(), collections.Counter(), collections.Counter()
        n = 0
        plies = []
        for g in games(text):
            n += 1
            tags = dict(re.findall(r'^\[(\w+) "(.*)"\]$', g, re.M))
            results[tags.get('Result', '?')] += 1
            term = tags.get('Termination', 'normal')
            terms[term] += 1
            moves = g.split('\n\n', 1)[-1]
            comments = re.findall(r'\{([^}]*)\}', moves)
            # cutechess-cli and fastchess put the reason after the last
            # move's "eval/depth time" comment: "{0.00/1 0s, White mates}".
            reason = comments[-1].split(', ')[-1].strip() if comments else '?'
            bare = re.sub(r'\{[^}]*\}', ' ', moves)
            plies.append(len([t for t in bare.split() if not re.fullmatch(r'\d+\.+|1-0|0-1|1/2-1/2|\*', t)]))
            reasons[reason] += 1
            kind = abnormal_kind(term, reason)
            if kind:
                bad[kind] += 1
        print(f'{path}: {n} games; results {dict(results)}; terminations {dict(terms)}; '
              f'plies min {min(plies, default=0)}, mean {sum(plies) / max(1, len(plies)):.0f}, '
              f'max {max(plies, default=0)}')
        for reason, k in reasons.most_common():
            print(f'    {k:4d}  {reason}')
    print(f'games not ending by the rules or adjudication: {sum(bad.values())}')
    for kind, k in bad.most_common():
        print(f'    {k:4d}  {kind}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
