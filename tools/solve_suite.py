"""Tactical and mate regression guards (DESIGN.md §5.2): runs Fork on a test
suite at a fixed node count and counts the positions it solves. Solve counts
guard against pruning that hides tactics or mates; they never replace an
SPRT, and neither suite is ever a tuning target.

Suites (KB tools.md §4; both downloaded into .cache/suites/ and checked
against their SHA-256, never committed; docs/ORIGINALITY.md):
- wac: Win at Chess, 300 positions (Fred Reinfeld, 1958), as the EPD file on
  John Bergbom's site, http://www.bergbomconsulting.se/chess/epdfiles/wac.epd
  (22,995 bytes, SHA-256 e1eab24c...a09e8, no licence stated; copyright
  UNVERIFIED). Solved: the move played is a `bm` move and no `am` move.
- mate: vondele/matetrack's matetrack.epd at commit 8085413b (GPL-3.0;
  449,928 bytes, SHA-256 8ba57122...eefd72), the 297 positions with a mate
  for the side to move in 1 to 5 moves. A test input only, by the owner's
  decision of 2026-10-25 (KB data-policy.md decision 7): solver-made and
  corrected with Stockfish, so a diagnostic, never a tuning target or
  training data. Lines are four FEN fields, then `bm #N;` and fields without
  opcodes, so they are split here rather than by python-chess's EPD parser.
  Solved: the last reported score is a mate in at most N moves.

    .venv/Scripts/python.exe -I tools/solve_suite.py ENGINE [--suite wac|mate] [--nodes 200000]
        [--option UseLmr=false ...]

ENGINE is an absolute path. The engine is driven over plain UCI pipes:
python-chess's engine wrapper left the interpreter hanging at exit on
Windows after a full suite (seen 2026-10-25; cause UNVERIFIED).
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import urllib.request

import chess

SUITES = {
    'wac': ('http://www.bergbomconsulting.se/chess/epdfiles/wac.epd',
            'e1eab24c3c609012b1aa6d8b4f532429ce61c2217402efd051297303e78a09e8', 'wac.epd'),
    'mate': ('https://raw.githubusercontent.com/vondele/matetrack/8085413b46d6d4f1bb9612353a6385dec784dae7/'
             'matetrack.epd',
             '8ba5712234ba0cb2a1f1b1934872d1d30ba5e01c80482844dccccd4bc2eefd72', 'matetrack.epd'),
}
MATE_MAX = 5  # mates in 1 to 5 moves for the side to move (KB tools.md §4: 297 positions)
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.cache', 'suites')


def suite_lines(name):
    url, sha256, filename = SUITES[name]
    path = os.path.join(CACHE_DIR, filename)
    if not os.path.exists(path) or hashlib.sha256(open(path, 'rb').read()).hexdigest() != sha256:
        os.makedirs(CACHE_DIR, exist_ok=True)
        data = urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(data).hexdigest() != sha256:
            sys.exit(f'{filename} does not match its pinned SHA-256')
        open(path, 'wb').write(data)
    return [l for l in open(path, encoding='ascii').read().splitlines() if l.strip()]


def wac_items(lines):
    for line in lines:
        board, ops = chess.Board.from_epd(line)
        yield ops.get('id', board.fen()), board, ops


def mate_items(lines):
    for number, line in enumerate(lines, 1):
        found = re.search(r'\bbm #(-?\d+);', line)
        if not found:
            sys.exit(f'matetrack line {number}: no "bm #N;" field')
        n = int(found.group(1))
        if not 1 <= n <= MATE_MAX:
            continue
        board = chess.Board(' '.join(line.split()[:4]) + ' 0 1')
        if not board.is_valid():
            sys.exit(f'matetrack line {number}: invalid position')
        yield f'line {number} (#{n})', board, n


class Uci:
    def __init__(self, path):
        self.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def send(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()

    def until(self, prefix, seen=None):
        """Reads up to the line starting with `prefix`; earlier lines go to `seen`."""
        while True:
            line = self.p.stdout.readline()
            if not line:
                sys.exit(f'engine closed its output while waiting for {prefix!r}')
            if line.startswith(prefix):
                return line.split()
            if seen is not None:
                seen.append(line)

    def close(self):
        self.send('quit')
        try:
            self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.p.kill()
            sys.exit('engine did not exit within 10 s of quit')


def last_mate(info_lines):
    """The mate distance in the last scored info line, or None."""
    for line in reversed(info_lines):
        fields = line.split()
        if 'score' in fields:
            at = fields.index('score')
            return int(fields[at + 2]) if fields[at + 1] == 'mate' else None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('engine')
    ap.add_argument('--suite', choices=sorted(SUITES), default='wac')
    ap.add_argument('--nodes', type=int, default=200000)
    ap.add_argument('--hash', type=int, default=16)
    ap.add_argument('--option', action='append', default=[], help='NAME=VALUE, sent as setoption')
    a = ap.parse_args()
    lines = suite_lines(a.suite)
    items = list(wac_items(lines) if a.suite == 'wac' else mate_items(lines))
    eng = Uci(a.engine)
    eng.send('uci')
    eng.until('uciok')
    for opt in [f'Hash={a.hash}'] + a.option:
        name, value = opt.split('=', 1)
        eng.send(f'setoption name {name} value {value}')
    eng.send('isready')
    eng.until('readyok')
    solved, failed = 0, []
    for label, board, want in items:
        eng.send('ucinewgame')  # each position from a cleared search state
        eng.send('isready')  # the UCI spec's handshake after ucinewgame
        eng.until('readyok')
        eng.send('position fen ' + board.fen())
        eng.send(f'go nodes {a.nodes}')
        info = []
        move = chess.Move.from_uci(eng.until('bestmove', info)[1])
        if a.suite == 'wac':
            ok = ('bm' not in want or move in want['bm']) and ('am' not in want or move not in want['am'])
        else:
            mate = last_mate(info)
            ok = mate is not None and 1 <= mate <= want
        solved += ok
        if not ok:
            failed.append(label)
    eng.close()
    options = ' '.join(a.option) or 'defaults'
    print(f'{a.suite}: {solved} / {len(items)} solved at {a.nodes} nodes per position ({options})')
    print('not solved:', ' '.join(failed))


if __name__ == '__main__':
    main()
