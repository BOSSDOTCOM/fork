"""Tactical regression guard (DESIGN.md §5.2): runs Fork on a test suite at a
fixed node count and counts the positions whose best move it finds.

Suite: Win at Chess, 300 positions (Fred Reinfeld, 1958), as the EPD file on
John Bergbom's site: http://www.bergbomconsulting.se/chess/epdfiles/wac.epd
(22,995 bytes, SHA-256 e1eab24c...a09e8, no licence stated; the positions
come from Reinfeld's book, their copyright status is UNVERIFIED). Downloaded
into .cache/suites/ and checked against the SHA-256, never committed
(docs/ORIGINALITY.md). Solve counts guard against pruning that hides
tactics; they never replace an SPRT.

    .venv/Scripts/python.exe -I tools/solve_suite.py build/clang-release/fork.exe [--nodes 200000]
"""
import argparse
import hashlib
import os
import sys
import urllib.request

import chess
import chess.engine

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('engine')
    ap.add_argument('--nodes', type=int, default=200000)
    ap.add_argument('--hash', type=int, default=16)
    a = ap.parse_args()
    lines = suite_lines()
    solved, failed = 0, []
    with chess.engine.SimpleEngine.popen_uci(a.engine) as eng:
        eng.configure({'Hash': a.hash})
        for line in lines:
            board, ops = chess.Board.from_epd(line)
            eng.protocol.send_line('ucinewgame')  # each position from a cleared search state
            result = eng.play(board, chess.engine.Limit(nodes=a.nodes))
            ok = True
            if 'bm' in ops:
                ok = result.move in ops['bm']
            if 'am' in ops:
                ok = ok and result.move not in ops['am']
            solved += ok
            if not ok:
                failed.append(ops.get('id', board.fen()))
    print(f'WAC: {solved} / {len(lines)} solved at {a.nodes} nodes per position')
    print('not solved:', ' '.join(failed))


if __name__ == '__main__':
    main()
