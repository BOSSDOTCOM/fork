"""Tactical regression guard (DESIGN.md §5.2): runs Fork on a test suite at a
fixed node count and counts the positions whose best move it finds.

Suite: Win at Chess, 300 positions (Fred Reinfeld, 1958), as the EPD file on
John Bergbom's site: http://www.bergbomconsulting.se/chess/epdfiles/wac.epd
(22,995 bytes, SHA-256 e1eab24c...a09e8, no licence stated; the positions
come from Reinfeld's book, their copyright status is UNVERIFIED; file and
provenance verified in the KB, tools.md §4, 2026-10-25). Downloaded
into .cache/suites/ and checked against the SHA-256, never committed
(docs/ORIGINALITY.md). Solve counts guard against pruning that hides
tactics; they never replace an SPRT.

    .venv/Scripts/python.exe -I tools/solve_suite.py ENGINE [--nodes 200000] [--option UseLmr=false ...]

ENGINE is an absolute path. The engine is driven over plain UCI pipes:
python-chess's engine wrapper left the interpreter hanging at exit on
Windows after a full suite (seen 2026-10-25; cause UNVERIFIED), so it is used
only to parse the EPD.
"""
import argparse
import hashlib
import os
import subprocess
import sys
import urllib.request

import chess

URL = 'http://www.bergbomconsulting.se/chess/epdfiles/wac.epd'
SHA256 = 'e1eab24c3c609012b1aa6d8b4f532429ce61c2217402efd051297303e78a09e8'
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.cache', 'suites', 'wac.epd')


def suite_lines():
    if not os.path.exists(CACHE) or hashlib.sha256(open(CACHE, 'rb').read()).hexdigest() != SHA256:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        data = urllib.request.urlopen(URL, timeout=60).read()
        if hashlib.sha256(data).hexdigest() != SHA256:
            sys.exit('wac.epd does not match its pinned SHA-256')
        open(CACHE, 'wb').write(data)
    return [l for l in open(CACHE, encoding='ascii').read().splitlines() if l.strip()]


class Uci:
    def __init__(self, path):
        self.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def send(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()

    def until(self, prefix):
        while True:
            line = self.p.stdout.readline()
            if not line:
                sys.exit(f'engine closed its output while waiting for {prefix!r}')
            if line.startswith(prefix):
                return line.split()

    def close(self):
        self.send('quit')
        try:
            self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.p.kill()
            sys.exit('engine did not exit within 10 s of quit')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('engine')
    ap.add_argument('--nodes', type=int, default=200000)
    ap.add_argument('--hash', type=int, default=16)
    ap.add_argument('--option', action='append', default=[], help='NAME=VALUE, sent as setoption')
    a = ap.parse_args()
    lines = suite_lines()
    eng = Uci(a.engine)
    eng.send('uci')
    eng.until('uciok')
    for opt in [f'Hash={a.hash}'] + a.option:
        name, value = opt.split('=', 1)
        eng.send(f'setoption name {name} value {value}')
    eng.send('isready')
    eng.until('readyok')
    solved, failed = 0, []
    for line in lines:
        board, ops = chess.Board.from_epd(line)
        eng.send('ucinewgame')  # each position from a cleared search state
        eng.send('isready')  # the UCI spec's handshake after ucinewgame
        eng.until('readyok')
        eng.send('position fen ' + board.fen())
        eng.send(f'go nodes {a.nodes}')
        move = chess.Move.from_uci(eng.until('bestmove')[1])
        ok = True
        if 'bm' in ops:
            ok = move in ops['bm']
        if 'am' in ops:
            ok = ok and move not in ops['am']
        solved += ok
        if not ok:
            failed.append(ops.get('id', board.fen()))
    eng.close()
    options = ' '.join(a.option) or 'defaults'
    print(f'WAC: {solved} / {len(lines)} solved at {a.nodes} nodes per position ({options})')
    print('not solved:', ' '.join(failed))


if __name__ == '__main__':
    main()
