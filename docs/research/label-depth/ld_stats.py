# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-arm statistics of the label-depth runs (docs/research/label-depth/): records, the saved, unsaved and
in-check shares, mate-band and tactical saved records, an estimate of the trainer's kept count, and (when the
arm's fork_datagen run json exists) nodes_spent per record, nodes per second per thread and records per second.

Decodes each shard with tools/datagen/verify_games.py's own decoder and replays it with python-chess.
"kept (estimate)" applies the trainer's filter as tools/train/src/main.rs states it (filter_check,
filter_tactical, max_eval 20000): saved, side to move not in check, |score| <= 20000, the move played neither a
capture nor a promotion. The trainer's own count (fork-train stats) is reported beside it when given.

    python -I ld_stats.py ARM_DIR... [--json OUT]
"""
import json
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools' / 'datagen'))
import verify_games as V  # noqa: E402

UNSAVED = 32767
MAX_EVAL = 20000


def shard_stats(path, acc):
    """Adds a shard's complete games to acc (a game still being written at the end is left out)."""
    data = Path(path).read_bytes()
    i = 0
    while i + 32 <= len(data):
        if not int.from_bytes(data[i:i + 8], 'little'):
            break
        board, _ = V.decode_board(data[i:i + 32])
        j = i + 32
        g = dict.fromkeys(acc, 0)
        g['games'] = 1
        closed = False
        while j + 4 <= len(data):
            code, score = V.u16(data, j), V.i16(data, j + 2)
            j += 4
            if code == 0:
                closed = True
                break
            move = next(m for m in board.legal_moves if V.code_of(board, m) == code)
            g['records'] += 1
            if score == UNSAVED:
                g['unsaved'] += 1
            elif board.is_check():
                g['in_check'] += 1
            else:
                g['saved_nocheck'] += 1
                if abs(score) > MAX_EVAL:
                    g['mate_band'] += 1
                elif board.is_capture(move) or move.promotion:
                    g['tactical'] += 1
                else:
                    g['kept_est'] += 1
            board.push(move)
        if not closed:
            break
        for k in acc:
            acc[k] += g[k]
        i = j


def arm_stats(d):
    d = Path(d)
    acc = dict(games=0, records=0, unsaved=0, in_check=0, saved_nocheck=0, mate_band=0, tactical=0, kept_est=0)
    shards = sorted(d.glob('*.vf'))
    for s in shards:
        shard_stats(s, acc)
    out = {'arm': d.name, 'shards': len(shards), **acc}
    r = acc['records']
    if r:
        out['share_unsaved'] = acc['unsaved'] / r
        out['share_in_check'] = acc['in_check'] / r
        out['share_saved_nocheck'] = acc['saved_nocheck'] / r
        out['kept_est_per_record'] = acc['kept_est'] / r
        out['records_per_game'] = r / acc['games']
    run = d / f'{d.name}.json'
    if run.exists():
        m = json.loads(run.read_text())
        th = m['settings']['threads']
        out['run_json'] = {k: m[k] for k in ('games', 'positions', 'positions_unsaved', 'nodes_spent', 'seconds')}
        out['nodes_per_record'] = m['nodes_spent'] / m['positions']
        out['nodes_per_s_per_thread'] = m['nodes_spent'] / m['seconds'] / th
        out['records_per_s'] = m['positions'] / m['seconds']
        out['ends'] = m['ends']
        if m['positions'] != r:
            out['warning'] = f"shards hold {r} records, the run json {m['positions']}"
    return out


def main(argv):
    js = None
    if '--json' in argv:
        k = argv.index('--json')
        js = argv[k + 1]
        argv = argv[:k] + argv[k + 2:]
    res = [arm_stats(d) for d in argv]
    print(json.dumps(res, indent=1))
    if js:
        Path(js).write_text(json.dumps(res, indent=1) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
