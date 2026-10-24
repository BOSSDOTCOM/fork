"""Tallies match PGNs: games, results, Termination tags and the runner's
reason for each result (the last {comment} of the movetext, e.g. "{Black
mates}" or "{Draw by 3-fold repetition}"). Standard library only.

    python3 tools/pgn_summary.py a.pgn [b.pgn ...]

Exit status 1 if any game ended other than by the rules: a Termination
other than "normal" (cutechess-cli and fastchess write e.g. "time
forfeit", "illegal move", "abandoned", "stalled connection"), or a reason
mentioning time, illegal, disconnect, crash or stall.
"""
import collections
import re
import sys

BAD = re.compile(r'time|illegal|disconnect|crash|stall|abandon|connection|forfeit|unterminated', re.I)


def games(text):
    # A game is its tag section followed by its movetext.
    for block in re.split(r'\n\s*\n(?=\[Event )', text.strip()):
        if block.strip():
            yield block


def main(paths):
    bad = 0
    for path in paths:
        text = open(path, encoding='utf-8', errors='replace').read()
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
            if term.lower() != 'normal' or BAD.search(reason):
                bad += 1
        print(f'{path}: {n} games; results {dict(results)}; terminations {dict(terms)}; '
              f'plies min {min(plies, default=0)}, mean {sum(plies) / max(1, len(plies)):.0f}, '
              f'max {max(plies, default=0)}')
        for reason, k in reasons.most_common():
            print(f'    {k:4d}  {reason}')
    print(f'games not ending by the rules: {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
