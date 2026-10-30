# SPDX-License-Identifier: GPL-3.0-or-later

"""The bake-off's eval-scale normalization (DESIGN.md §5.4, games plan 2;
KB phase4-designs/judgement.md §6.2): the output scale S that gives a net
the same mean |eval| as the control net on the same positions, so the
search's margins (tuned for one scale) do not decide a pairing.

Positions: the first --positions positions of a held-out shard that pass
the training filter (not in check, no capture or promotion played, |score|
<= 20000). Each net's evaluation is the reference's R-int
(tools/nnue/reference.py, models.py) at the net's own S; the matched S is
round(S * mean|control| / mean|net|), and is printed with both means.

    match_scale.py --control B0.fnet [--control-layout b0.json]
                   --net NET.fnet --layout NET.json SHARD [--positions N]
"""
import argparse
import json
import sys
from pathlib import Path

import chess

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'datagen'))
import models  # noqa: E402
import netformat  # noqa: E402
import reference  # noqa: E402
import verify_games as vg  # noqa: E402

MAX_SCORE = 20000


def positions(path, limit):
    data = Path(path).read_bytes()
    out, i = [], 0
    while i + 32 <= len(data) and len(out) < limit:
        board, _ = vg.decode_board(data[i:i + 32])
        i += 32
        while i + 4 <= len(data):
            code, score = vg.u16(data, i), vg.i16(data, i + 2)
            i += 4
            if code == 0:
                break
            move = next(m for m in board.legal_moves if vg.code_of(board, m) == code)
            if len(out) < limit and not board.is_check() and not board.is_capture(move) \
                    and move.promotion is None and abs(score) <= MAX_SCORE:
                out.append(board.copy(stack=False))
            board.push(move)
    return out


def evaluator(net_path, layout_path):
    """(R-int of a board, the net's S)."""
    desc = netformat.layout(layout_path)
    data = Path(net_path).read_bytes()
    scale = netformat.header_fields(data)['scale']
    if desc['architecture'] == 1:
        net = netformat.read_net(data, desc)
        return (lambda board: reference.r_int(net, board)), scale
    arch = models.arch_from_net(desc['name'], data[netformat.HEADER_BYTES:])
    net = models.unpack(arch, data[netformat.HEADER_BYTES:])
    return (lambda board: models.r_int(arch, net, scale, board)), scale


def mean_abs(fn, boards):
    return sum(abs(fn(b)) for b in boards) / len(boards)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('shard')
    ap.add_argument('--control', required=True)
    ap.add_argument('--control-layout', default=str(HERE / 'b0.json'))
    ap.add_argument('--net', required=True)
    ap.add_argument('--layout', required=True)
    ap.add_argument('--positions', type=int, default=10000)
    a = ap.parse_args(argv)
    boards = positions(a.shard, a.positions)
    control, _ = evaluator(a.control, a.control_layout)
    net, scale = evaluator(a.net, a.layout)
    m_control, m_net = mean_abs(control, boards), mean_abs(net, boards)
    matched = round(scale * m_control / m_net)
    print(json.dumps({'positions': len(boards), 'control_mean_abs': round(m_control, 2),
                      'net_mean_abs': round(m_net, 2), 'net_scale': scale, 'matched_scale': matched}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
