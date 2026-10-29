# SPDX-License-Identifier: GPL-3.0-or-later

"""Writes the opening positions Fork's self-play data generation starts from
(DESIGN.md §5.3, deliverable 1), from one Lichess CC0 monthly game file.

Only headers and moves are read; every comment is skipped, so no
`[%eval]` (Stockfish's evaluations, KB data-policy.md) ever reaches the
output. A game is used when it is rated, standard chess, neither player has
the BOT title, and both are rated at least --min-rating. From each used
game: the position after a random ply in [--ply-min, --ply-max], then
--random-min to --random-max uniformly random legal plies (python-chess's
move generator), skipping positions where the game is over and positions
already written (compared without the move counters). Every random choice
comes from a generator seeded by (--seed, the game's index in the file), so
the same file and settings give the same output byte for byte.

The source's SHA-256 is checked against --sha256 (from Lichess's published
sha256sums.txt) before anything is read. The output EPD is not committed
(size); the manifest written beside it (OUT.manifest.json, or --manifest)
is, under data/manifests/, and regenerates it.

    .venv/Scripts/python.exe -I tools/datagen/datagen_openings.py \\
        lichess_db_standard_rated_2016-09.pgn.zst OUT.epd --sha256 HEX
"""
import argparse
import hashlib
import io
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import chess

COMMENT = re.compile(r'\{[^}]*\}')
MOVE_NUMBER = re.compile(r'^\d+\.+$')
RESULTS = {'1-0', '0-1', '1/2-1/2', '*'}
STAT_KEYS = ('games', 'not_rated', 'not_standard', 'bot', 'below_rating',
             'rating_pass', 'too_short', 'game_over', 'duplicate', 'written')


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def open_text(path):
    """The PGN text of a file, decompressing .zst while streaming."""
    if str(path).endswith('.zst'):
        import zstandard
        raw = open(path, 'rb')
        return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw),
                                encoding='utf-8', errors='replace')
    return open(path, encoding='utf-8', errors='replace')


def read_games(lines):
    """Yields (headers, movetext) per game of a PGN stream."""
    headers, moves, in_moves = {}, [], False
    for line in lines:
        line = line.strip()
        if line.startswith('['):
            if in_moves:
                yield headers, ' '.join(moves)
                headers, moves, in_moves = {}, [], False
            m = re.match(r'\[(\w+)\s+"(.*)"\]$', line)
            if m:
                headers[m.group(1)] = m.group(2)
        elif line:
            in_moves = True
            moves.append(line)
    if headers or moves:
        yield headers, ' '.join(moves)


def san_moves(movetext, limit):
    """The first `limit` SAN moves of a movetext, comments, move numbers,
    NAGs, annotations and the result removed."""
    out = []
    for tok in COMMENT.sub(' ', movetext).split():
        if MOVE_NUMBER.match(tok) or tok in RESULTS or tok.startswith('$'):
            continue
        tok = re.sub(r'^\d+\.+', '', tok).rstrip('?!')
        if tok:
            out.append(tok)
            if len(out) == limit:
                break
    return out


def rating(headers, key):
    try:
        return int(headers.get(key, ''))
    except ValueError:
        return None


def game_filter(headers, min_rating):
    """The stat key a game is dropped under, or None when it is used."""
    if not headers.get('Event', '').startswith('Rated'):
        return 'not_rated'
    if headers.get('Variant', 'Standard') != 'Standard':
        return 'not_standard'
    if 'BOT' in (headers.get('WhiteTitle'), headers.get('BlackTitle')):
        return 'bot'
    w, b = rating(headers, 'WhiteElo'), rating(headers, 'BlackElo')
    if w is None or b is None or min(w, b) < min_rating:
        return 'below_rating'
    return None


def opening_from(movetext, rng, a):
    """The opening position for one used game, or the stat key it fails on."""
    ply = rng.randint(a.ply_min, a.ply_max)
    sans = san_moves(movetext, ply)
    if len(sans) < ply:
        return 'too_short'
    board = chess.Board()
    for san in sans:
        board.push_san(san)
        if board.is_game_over(claim_draw=True):
            return 'game_over'
    for _ in range(rng.randint(a.random_min, a.random_max)):
        moves = sorted(board.legal_moves, key=lambda m: m.uci())
        if not moves:
            return 'game_over'
        board.push(rng.choice(moves))
        if board.is_game_over(claim_draw=True):
            return 'game_over'
    return board


def git_commit():
    root = Path(__file__).resolve().parents[2]
    try:
        head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = subprocess.run(['git', '-C', str(root), 'status', '--porcelain', '--', 'tools/datagen'],
                               capture_output=True, text=True, check=True).stdout.strip()
        return head + ('-dirty' if dirty else '')
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def run(a, lines):
    stats = dict.fromkeys(STAT_KEYS, 0)
    seen = set()
    out = []
    for index, (headers, movetext) in enumerate(read_games(lines)):
        if a.limit_games and index >= a.limit_games:
            break
        stats['games'] += 1
        why = game_filter(headers, a.min_rating)
        if why:
            stats[why] += 1
            continue
        stats['rating_pass'] += 1
        rng = random.Random(f'{a.seed}:{index}')
        board = opening_from(movetext, rng, a)
        if isinstance(board, str):
            stats[board] += 1
            continue
        if board.epd() in seen:
            stats['duplicate'] += 1
            continue
        seen.add(board.epd())
        out.append(board.fen())
        stats['written'] += 1
    return out, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('source', help='Lichess monthly PGN (.pgn.zst or plain .pgn)')
    ap.add_argument('out', help='output EPD (one FEN per line)')
    ap.add_argument('--sha256', required=True, help="the source's published SHA-256")
    ap.add_argument('--manifest', help='manifest path (default: OUT.manifest.json)')
    ap.add_argument('--seed', type=int, default=20261028)
    ap.add_argument('--min-rating', type=int, default=2000)
    ap.add_argument('--ply-min', type=int, default=8)
    ap.add_argument('--ply-max', type=int, default=16)
    ap.add_argument('--random-min', type=int, default=2)
    ap.add_argument('--random-max', type=int, default=4)
    ap.add_argument('--limit-games', type=int, default=0, help='stop after N games (tests; 0 = all)')
    a = ap.parse_args(argv)
    if not (0 < a.ply_min <= a.ply_max and 0 <= a.random_min <= a.random_max):
        ap.error('need 0 < ply-min <= ply-max and 0 <= random-min <= random-max')

    digest = sha256_of(a.source)
    if digest != a.sha256.lower():
        print(f'SHA-256 mismatch for {a.source}: {digest}, expected {a.sha256}', file=sys.stderr)
        return 1
    with open_text(a.source) as lines:
        fens, stats = run(a, lines)
    data = ''.join(f + '\n' for f in fens).encode()
    Path(a.out).write_bytes(data)
    manifest = {
        'tool': 'tools/datagen/datagen_openings.py',
        'tool_commit': git_commit(),
        'source': Path(a.source).name,
        'source_sha256': digest,
        'settings': {k: getattr(a, k) for k in
                     ('seed', 'min_rating', 'ply_min', 'ply_max', 'random_min', 'random_max', 'limit_games')},
        'filters': 'rated standard games, no BOT title, both ratings >= min_rating; comments never read',
        'stats': stats,
        'output': Path(a.out).name,
        'output_sha256': hashlib.sha256(data).hexdigest(),
        'positions': len(fens),
    }
    Path(a.manifest or a.out + '.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', newline='\n')
    print(json.dumps(stats))
    return 0


if __name__ == '__main__':
    sys.exit(main())
