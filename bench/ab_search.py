# SPDX-License-Identifier: GPL-3.0-or-later

"""Interleaved A/B comparison of search speed (DESIGN.md §5.2, performance gate).

The search-bench sibling of bench/ab.py: runs `fork bench` of two engine
binaries alternately (A B, then B A, ...) for several rounds, pinned to one
core on Linux, and compares nodes per second. Reports the median and the
best (maximum: load only ever slows a run down) nps of each side and the
change of B relative to A, with ab.py's noise rule: a change counts only if
both estimators move the same way by more than 3% or twice the
round-to-round spread, whichever is larger.

Bench node counts are printed for both sides. They must be equal for a pure
speed change (`--same-nodes` enforces it); a deliverable that changes the
search changes them by design, and then only nps is compared.

Identity checks as in ab.py: each side's expected variant and commit must
match what `fork version` reports ("variant ... | commit ... |",
cmake/build_id.cmake), the SHA-256 of each file is re-checked before every
run, and byte-identical binaries are refused unless --allow-identical is
given (A/A noise runs).

usage: python3 -I bench/ab_search.py A/fork B/fork --a-variant baseline --a-commit 1234abc
           --b-variant baseline --b-commit 5678def [--rounds 6] [--core 4] [--same-nodes] [--allow-identical]
"""

import argparse
import hashlib
import os
import re
import statistics
import subprocess
import sys

IDENTITY = re.compile(r"variant (\S+) \| commit (\S+) \|")


def fail(msg):
    sys.exit(f"ab_search.py: error: {msg}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def commit_matches(expected, actual):
    exp_dirty, act_dirty = expected.endswith("-dirty"), actual.endswith("-dirty")
    exp_hash = expected.removesuffix("-dirty").lower()
    act_hash = actual.removesuffix("-dirty").lower()
    return len(exp_hash) >= 7 and act_hash.startswith(exp_hash) and exp_dirty == act_dirty


class Side:
    def __init__(self, label, path, variant, commit):
        self.label, self.path = label, os.path.abspath(path)
        self.variant, self.commit = variant, commit
        if not os.path.isfile(self.path):
            fail(f"{label}: no such file {self.path}")
        if len(commit.removesuffix("-dirty")) < 7:
            fail(f"{label}: commit '{commit}' is too short (need at least 7 hex digits)")
        self.sha = sha256(self.path)

    def check_identity(self):
        if sha256(self.path) != self.sha:
            fail(f"{self.label}: {self.path} changed during the run (SHA-256 differs)")
        out = subprocess.run([self.path, "version"], capture_output=True, text=True, check=True).stdout
        m = IDENTITY.search(out)
        if not m:
            fail(f"{self.label}: `{self.path} version` reports no 'variant ... | commit ...' identity")
        variant, commit = m.groups()
        if variant != self.variant:
            fail(f"{self.label}: binary reports variant '{variant}', expected '{self.variant}'")
        if not commit_matches(self.commit, commit):
            fail(f"{self.label}: binary reports commit '{commit}', expected '{self.commit}'")
        return commit

    def run(self, core):
        self.check_identity()
        pin = (lambda: os.sched_setaffinity(0, {core})) if hasattr(os, "sched_setaffinity") else None
        out = subprocess.run([self.path, "bench"], capture_output=True, text=True, check=True,
                             preexec_fn=pin).stdout
        nodes = int(re.search(r"nodes (\d+)", out).group(1))
        nps = int(re.search(r"nps (\d+)", out).group(1))
        sig = re.search(r"signature ([0-9a-f]+)", out).group(1)
        return nodes, sig, nps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--a-variant", required=True)
    ap.add_argument("--a-commit", required=True)
    ap.add_argument("--b-variant", required=True)
    ap.add_argument("--b-commit", required=True)
    ap.add_argument("--allow-identical", action="store_true")
    ap.add_argument("--same-nodes", action="store_true", help="fail unless both benches give the same nodes and signature")
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--core", type=int, default=4)
    args = ap.parse_args()
    sides = {"A": Side("A", args.a, args.a_variant, args.a_commit),
             "B": Side("B", args.b, args.b_variant, args.b_commit)}
    if sides["A"].sha == sides["B"].sha and not args.allow_identical:
        fail("A and B are byte-identical files (pass --allow-identical for an A/A run)")
    reported = {k: s.check_identity() for k, s in sides.items()}

    nps = {"A": [], "B": []}
    bench = {}
    for r in range(args.rounds):
        for side in (["A", "B"] if r % 2 == 0 else ["B", "A"]):
            nodes, sig, v = sides[side].run(args.core)
            if bench.setdefault(side, (nodes, sig)) != (nodes, sig):
                fail(f"{side}: bench changed between runs ({bench[side]} then {(nodes, sig)})")
            nps[side].append(v)
    if args.same_nodes and bench["A"] != bench["B"]:
        fail(f"bench differs: A {bench['A']}, B {bench['B']}")

    for k, s in sides.items():
        print(f"{k} = {s.path}\n    variant {s.variant} | commit {reported[k]} | sha256 {s.sha}\n"
              f"    bench nodes {bench[k][0]} signature {bench[k][1]}")
    print(f"identity checked before the run and on all {2 * args.rounds} runs; "
          f"{args.rounds} interleaved rounds" + (f", core {args.core}" if hasattr(os, "sched_setaffinity") else ", not pinned"))
    a_med, b_med = statistics.median(nps["A"]), statistics.median(nps["B"])
    a_max, b_max = max(nps["A"]), max(nps["B"])
    ch_med, ch_max = (b_med - a_med) / a_med, (b_max - a_max) / a_max

    def mad(xs, m):
        return 1.4826 * statistics.median(abs(x - m) for x in xs) / m

    threshold = max(0.03, 2 * max(mad(nps["A"], a_med), mad(nps["B"], b_med)))
    if abs(ch_med) > threshold and abs(ch_max) > threshold and (ch_med > 0) == (ch_max > 0):
        verdict = "B faster" if ch_max > 0 else "B slower"
    else:
        verdict = "no significant difference"
    print(f"nps     A median {a_med:>12.0f}  B median {b_med:>12.0f}  {100 * ch_med:+.1f}%")
    print(f"        A best   {a_max:>12.0f}  B best   {b_max:>12.0f}  {100 * ch_max:+.1f}%")
    print(f"noise threshold {100 * threshold:.1f}%: {verdict}")


if __name__ == "__main__":
    main()
