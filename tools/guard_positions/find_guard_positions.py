# SPDX-License-Identifier: GPL-3.0-or-later

"""Finds king-and-pawn positions for the null move's zugzwang-guard test (no
null move for a side with only pawns; audit-1's mutant M18b removes it):
positions whose tablebase move the guarded search finds and keeps, and the
search without the guard does not.

Pipeline, in a fixed order from a recorded seed (see README.md beside this
file):
  1. random positions with two kings and 2 or 3 pawns (4 or 5 pieces), the
     side to move with at least one pawn, legal and not in check;
  2. the tablebase filter (python-chess's chess.syzygy, the local 3-4-5 WDL
     tables): the moves keeping the best WDL ("saving moves") number at most
     --max-saving and fewer than the legal moves; positions where the root or
     any move's result is a cursed win or blessed loss (WDL +-1) are skipped,
     so "keeps the result" is the same with and without the fifty-move rule;
  3. the mutant filter: the M18b engine (tests/mutants/
     m18b-null-zugzwang-guard.patch) with the base configuration and the
     engine's defaults (UseImprovingLmp on) must not find and keep a saving
     move by --max-depth;
  4. the check: the mutant with the other two configurations, and the
     guarded engine with all three, which must each find and keep a saving
     move by --max-depth. A position the mutant fails with every
     configuration is a "hard failure"; one it fails only with some is
     "partial" (logged, not kept);
  5. the reference runs of each kept position with UseImprovingLmp off.

"Found and kept": the first completed iteration from which every later
iteration up to --max-depth has a saving move as its first PV move (lines
marked upperbound or lowerbound are ignored); its depth, nodes and time.

Both engines must be FORK_TUNE builds. Every parameter of a configuration
is set over UCI from that commit's own src/tune/params.hpp, so the engines'
compiled defaults do not matter. Threads 1, Hash 16, a fresh engine process
per run, at most --jobs engine processes at once.

Every evaluated position is appended to --out (JSON lines) with its random
index, so a run can be audited; the summary goes to standard output.

usage: python -I tools/guard_positions/find_guard_positions.py --tables DIR \
         --intact EXE --mutant EXE --out FILE [--seed 20261125] [--want 6] \
         [--max-minutes 120] [--jobs 3] [--nodes-bar]
"""
import argparse
import concurrent.futures
import json
import os
import random
import re
import subprocess
import sys
import threading
import time

import chess
import chess.syzygy

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The three configurations (owner, 2026-11-25): commits differing only in
# src/tune/params.hpp's defaults.
CONFIGS = [("base", "3875ca9f2a105fbecc2b65e56f2cdc80ad682d68"),
           ("candidate", "c51114974fa190af2ad53614b0ad97ec336c5f6e"),
           ("arm", "5d4682ee38e3bb9f477bd262314870098c74ffee")]


def params_of(commit):
    text = subprocess.run(["git", "-C", REPO, "show", f"{commit}:src/tune/params.hpp"], capture_output=True,
                          text=True, check=True).stdout
    params = {m.group(1): int(m.group(2)) for m in re.finditer(r"X\((\w+),\s*(-?\d+),", text)}
    if not params:
        raise SystemExit(f"no parameters parsed from {commit}:src/tune/params.hpp")
    return params


# ---------------------------------------------------------------- positions

def random_position(rng):
    """Two kings and 2 or 3 pawns on random squares; the side to move has a
    pawn. Returns a Board or None when the placement is not legal."""
    n_pawns = rng.choice((2, 3))
    stm = rng.choice((chess.WHITE, chess.BLACK))
    colours = [rng.choice((chess.WHITE, chess.BLACK)) for _ in range(n_pawns)]
    if stm not in colours:
        return None
    board = chess.Board(None)
    board.turn = stm
    squares = rng.sample(range(64), 2 + n_pawns)
    board.set_piece_at(squares[0], chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(squares[1], chess.Piece(chess.KING, chess.BLACK))
    for sq, colour in zip(squares[2:], colours):
        if chess.square_rank(sq) in (0, 7):
            return None
        board.set_piece_at(sq, chess.Piece(chess.PAWN, colour))
    if not board.is_valid() or board.is_check() or not any(board.legal_moves):
        return None
    return board


def wdl_after(tb, board, move):
    """The mover's WDL after the move (-2..2)."""
    board.push(move)
    try:
        if chess.popcount(board.occupied) == 2:
            return 0
        if board.is_checkmate():
            return 2
        if board.is_stalemate():
            return 0
        return -tb.probe_wdl(board)
    finally:
        board.pop()


def tablebase_facts(tb, board, max_saving):
    """None, or (root WDL, saving moves, every move's WDL)."""
    root = tb.probe_wdl(board)
    results = {m.uci(): wdl_after(tb, board, m) for m in board.legal_moves}
    if root in (1, -1) or any(v in (1, -1) for v in results.values()):
        return None
    best = max(results.values())
    if best != root:
        raise SystemExit(f"tablebase inconsistency at {board.fen()}: root {root}, best move {best}")
    saving = sorted(m for m, v in results.items() if v == best)
    if len(saving) > max_saving or len(saving) == len(results):
        return None
    return root, saving, results


# ---------------------------------------------------------------- engine runs

def run_engine(engine, fen, params, improving, max_depth, timeout, go=None):
    """Completed iterations {depth: (first PV move, nodes, ms)} and the
    bestmove of `go depth max_depth` (or of the given go command); raises on
    unknown options or a timeout."""
    lines = ["uci", "setoption name Threads value 1", "setoption name Hash value 16",
             f"setoption name UseImprovingLmp value {'true' if improving else 'false'}"]
    lines += [f"setoption name {k} value {v}" for k, v in params.items()]
    lines += ["isready", "ucinewgame", "isready", f"position fen {fen}", go or f"go depth {max_depth}"]
    p = subprocess.Popen([engine], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True)
    timer = threading.Timer(timeout, p.kill)
    timer.start()
    its, unknown, best = {}, 0, None
    try:
        p.stdin.write("\n".join(lines) + "\n")
        p.stdin.flush()
        for line in p.stdout:
            if line.startswith("info string") and "No such option" in line:
                unknown += 1
            t = line.split()
            if (t[:1] == ["info"] and "depth" in t and "pv" in t and "nodes" in t and "upperbound" not in t
                    and "lowerbound" not in t):
                its[int(t[t.index("depth") + 1])] = (t[t.index("pv") + 1], int(t[t.index("nodes") + 1]),
                                                     int(t[t.index("time") + 1]))
            if line.startswith("bestmove"):
                best = t[1]
                break
        if best is None:
            raise TimeoutError(f"no bestmove within {timeout} s")
        p.stdin.write("quit\n")
        p.stdin.flush()
        p.wait(timeout=60)
    finally:
        timer.cancel()
        if p.poll() is None:
            p.kill()
            p.wait()
    if unknown:
        raise SystemExit(f"{engine}: {unknown} options unknown (not a FORK_TUNE build?)")
    return its, best


def found_and_kept(its, good):
    ds = sorted(its)
    for i, d in enumerate(ds):
        if all(its[e][0] in good for e in ds[i:]):
            return {"depth": d, "nodes": its[d][1], "ms": its[d][2]}
    return None


def probe(engine, fen, params, improving, good, args):
    its, best = run_engine(engine, fen, params, improving, args.max_depth, args.timeout)
    last = max(its) if its else 0
    return {"fk": found_and_kept(its, good), "last_depth": last, "nodes": its[last][1] if its else 0,
            "ms": its[last][2] if its else 0, "last_pv": its[last][0] if its else None, "bestmove": best}


def check_positions(args, params, tb):
    """--check: the tablebase facts and all twelve runs of each FEN, one
    after the other; exits non-zero unless the guarded engine finds and
    keeps a saving move everywhere."""
    ok = True
    with open(args.out, "a", encoding="utf-8") as out:
        for fen in args.check:
            board = chess.Board(fen)
            facts = tablebase_facts(tb, board, 99)
            if facts is None:
                raise SystemExit(f"{fen}: a cursed win or blessed loss among its moves")
            root, saving, results = facts
            rec = {"check": fen, "wdl": root, "saving": saving, "moves": results}
            print(f"{fen}: WDL {root}, saving {' '.join(saving)}")
            for improving in (True, False):
                for kind, engine in (("intact", args.intact), ("mutant", args.mutant)):
                    key = f"{kind}_{'on' if improving else 'off'}"
                    rec[key] = {}
                    for name, _ in CONFIGS:
                        r = probe(engine, fen, params[name], improving, set(saving), args)
                        rec[key][name] = r
                        if kind == "intact" and improving and not r["fk"]:
                            ok = False
                        fk = (f"found and kept from depth {r['fk']['depth']}: {r['fk']['nodes']:,} nodes, "
                              f"{r['fk']['ms']:,} ms" if r["fk"] else
                              f"NOT found and kept by depth {r['last_depth']}: {r['nodes']:,} nodes "
                              f"(last pv {r['last_pv']})")
                        print(f"  {key:10s} {name:10s} {fk}", flush=True)
            out.write(json.dumps(rec) + "\n")
    return 0 if ok else 1


def nodes_bar(fen, params, good, rec, args):
    """--nodes-bar: B is twice the worst found-and-kept nodes of the guarded
    engine (UseImprovingLmp on, the three configurations), rounded up to a
    multiple of 1,000. The guarded engine's bestmove at `go nodes B` must be
    a saving move in every configuration, and the mutant's at `go nodes 4B`
    must not be in any (its moves at B and 2B are recorded too)."""
    need = max(rec["intact_on"][n]["fk"]["nodes"] for n, _ in CONFIGS)
    budget = -(-2 * need // 1000) * 1000
    bar = {"B": budget, "need": need, "intact": {}, "mutant": {}}
    rec["nodes_bar"] = bar
    for name, _ in CONFIGS:  # the mutant at 4B first: the cheapest way to fail
        bar["mutant"][name] = {"4B": run_engine(args.mutant, fen, params[name], True, 0, args.timeout,
                                                f"go nodes {4 * budget}")[1]}
        if bar["mutant"][name]["4B"] in good:
            return False
    for name, _ in CONFIGS:
        bar["intact"][name] = run_engine(args.intact, fen, params[name], True, 0, args.timeout,
                                         f"go nodes {budget}")[1]
        if bar["intact"][name] not in good:
            return False
        for mult in (1, 2):
            bar["mutant"][name][f"{mult}B"] = run_engine(args.mutant, fen, params[name], True, 0, args.timeout,
                                                         f"go nodes {mult * budget}")[1]
    return True


# ---------------------------------------------------------------- driver

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", required=True, help="Syzygy 3-4-5 WDL tables")
    ap.add_argument("--intact", required=True, help="FORK_TUNE engine with the guard")
    ap.add_argument("--mutant", required=True, help="FORK_TUNE engine built with the M18b patch")
    ap.add_argument("--out", required=True, help="JSON-lines log of every position evaluated")
    ap.add_argument("--seed", type=int, default=20261125)
    ap.add_argument("--max-depth", type=int, default=22)
    ap.add_argument("--max-saving", type=int, default=2)
    ap.add_argument("--want", type=int, default=6, help="stop after this many kept positions")
    ap.add_argument("--max-minutes", type=float, default=120.0, help="stop starting new positions after this")
    ap.add_argument("--max-positions", type=int, default=0, help="stop after this many random draws (0: none)")
    ap.add_argument("--jobs", type=int, default=3, help="engine processes at once")
    ap.add_argument("--timeout", type=float, default=600.0, help="seconds per engine run")
    ap.add_argument("--nodes-bar", action="store_true",
                    help="a hard failure is kept only if it also passes the go-nodes bar (see nodes_bar)")
    ap.add_argument("--check", action="append", metavar="FEN",
                    help="no search: rerun both engines, every configuration, UseImprovingLmp on and off, on FEN")
    args = ap.parse_args()

    params = {name: params_of(commit) for name, commit in CONFIGS}
    rng = random.Random(args.seed)
    tb = chess.syzygy.open_tablebase(args.tables, load_dtz=False)
    if args.check:
        return check_positions(args, params, tb)
    start = time.monotonic()
    out = open(args.out, "a", encoding="utf-8")
    out_lock = threading.Lock()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs)
    stats = {"drawn": 0, "legal": 0, "tablebase": 0, "evaluated": 0, "hard": 0, "partial": 0, "timeouts": 0}
    kept = []

    def log(rec):
        with out_lock:
            out.write(json.dumps(rec) + "\n")
            out.flush()

    def record(rec):
        rec["elapsed_s"] = round(time.monotonic() - start, 1)
        stats["evaluated"] += 1
        v = rec["verdict"]
        if v.startswith("kept"):
            kept.append(rec)
            stats["hard"] += 1
        elif v.startswith("partial"):
            stats["partial"] += 1
        elif v.startswith("timeout"):
            stats["timeouts"] += 1
        log(rec)
        print(f"[{rec['elapsed_s']:>7.0f} s] #{rec['index']:<7} {rec['fen']:<40} {v}", flush=True)

    def evaluate(index, fen, facts):
        root, saving, results = facts
        good = set(saving)
        rec = {"index": index, "fen": fen, "pieces": chess.popcount(chess.Board(fen).occupied), "wdl": root,
               "saving": saving, "moves": results, "seed": args.seed}
        try:
            rec["mutant_on"] = {"base": probe(args.mutant, fen, params["base"], True, good, args)}
            if rec["mutant_on"]["base"]["fk"]:
                rec["verdict"] = "mutant finds (base)"
                return rec
            for name in ("candidate", "arm"):
                rec["mutant_on"][name] = probe(args.mutant, fen, params[name], True, good, args)
            rec["intact_on"] = {}
            for name, _ in CONFIGS:
                rec["intact_on"][name] = probe(args.intact, fen, params[name], True, good, args)
                if not rec["intact_on"][name]["fk"]:
                    rec["verdict"] = f"intact fails ({name})"
                    return rec
            fails = [n for n, _ in CONFIGS if not rec["mutant_on"][n]["fk"]]
            rec["verdict"] = "kept (hard failure)" if len(fails) == 3 else f"partial (mutant fails {fails})"
            if len(fails) != 3:
                return rec
            if args.nodes_bar and not nodes_bar(fen, params, good, rec, args):
                rec["verdict"] = "hard failure, fails the nodes bar"
                return rec
            if args.nodes_bar:
                rec["verdict"] = "kept (hard failure, nodes bar)"
            rec["intact_off"] = {n: probe(args.intact, fen, params[n], False, good, args) for n, _ in CONFIGS}
            rec["mutant_off"] = {n: probe(args.mutant, fen, params[n], False, good, args) for n, _ in CONFIGS}
            return rec
        except TimeoutError as e:
            rec["verdict"] = f"timeout: {e}"
            return rec

    pending = set()
    index = 0
    stop_reason = None
    while True:
        elapsed = time.monotonic() - start
        if len(kept) >= args.want:
            stop_reason = f"{args.want} kept"
        elif elapsed > args.max_minutes * 60:
            stop_reason = f"{args.max_minutes} minutes"
        elif args.max_positions and stats["drawn"] >= args.max_positions:
            stop_reason = f"{args.max_positions} positions drawn"
        if stop_reason:
            break
        while len(pending) < args.jobs:
            board = None
            while board is None:
                index += 1
                stats["drawn"] += 1
                b = random_position(rng)
                if b is None:
                    continue
                stats["legal"] += 1
                facts = tablebase_facts(tb, b, args.max_saving)
                if facts is None:
                    continue
                board = b
            stats["tablebase"] += 1
            pending.add(pool.submit(evaluate, index, board.fen(), facts))
        done, pending = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
        for fut in done:
            record(fut.result())
    # Finish the positions already started, so their results are logged.
    for fut in concurrent.futures.as_completed(pending):
        record(fut.result())
    pool.shutdown()
    summary = {"summary": True, "seed": args.seed, "stop": stop_reason, "minutes": round((time.monotonic() - start) / 60, 1),
               **stats, "kept": [r["fen"] for r in kept]}
    log(summary)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
