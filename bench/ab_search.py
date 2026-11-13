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

`--perf` runs every bench under `perf stat -e cycles:u,instructions:u` (Linux,
hardware counters needed) and adds cycles per node, judged by the 1% rule for
bench-identical speed changes (DESIGN.md §6, 2026-11-07 decision 8): the same
two estimators (median, and best = fewest cycles), each beyond 1% or twice the
spread. `--json PATH` writes every run and both verdicts, for
tools/cloud/speed_ab_merge.py (the runner A/B, .github/workflows/speed-ab.yml).

Identity checks as in ab.py: each side's expected variant and commit must
match what `fork version` reports ("variant ... | commit ... |",
cmake/build_id.cmake), the SHA-256 of each file is re-checked before every
run, and byte-identical binaries are refused unless --allow-identical is
given (A/A noise runs).

usage: python3 -I bench/ab_search.py A/fork B/fork --a-variant baseline --a-commit 1234abc
           --b-variant baseline --b-commit 5678def [--rounds 6] [--core 4] [--same-nodes] [--allow-identical]
           [--perf] [--json out.json] [--label NAME]
"""

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile

IDENTITY = re.compile(r"variant (\S+) \| commit (\S+) \|")
NPS_FLOOR = 0.03      # the nps rule (ab.py's noise rule)
CYCLES_FLOOR = 0.01   # the cycles-per-node rule (DESIGN.md §6, 2026-11-07 decision 8)
PERF_EVENTS = "cycles:u,instructions:u"


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


def relative_spread(xs, m):
    """Median absolute deviation, scaled to a normal sigma, relative to m."""
    return 1.4826 * statistics.median(abs(x - m) for x in xs) / m


def compare(a, b, floor, lower_is_better=False):
    """The noise rule on two samples. Changes are speed changes (positive: B faster): for a
    higher-is-better measure (nps) B/A - 1, for a lower-is-better one (cycles per node) A/B - 1.
    "best" is the maximum, or the minimum when lower is better (load only ever makes a run worse).
    A change counts only if median and best move the same way by more than the threshold,
    max(floor, twice the larger relative spread)."""
    a_med, b_med = statistics.median(a), statistics.median(b)
    if lower_is_better:
        a_best, b_best = min(a), min(b)
        ch_med, ch_best = a_med / b_med - 1, a_best / b_best - 1
    else:
        a_best, b_best = max(a), max(b)
        ch_med, ch_best = (b_med - a_med) / a_med, (b_best - a_best) / a_best
    threshold = max(floor, 2 * max(relative_spread(a, a_med), relative_spread(b, b_med)))
    if abs(ch_med) > threshold and abs(ch_best) > threshold and (ch_med > 0) == (ch_best > 0):
        verdict = "B faster" if ch_best > 0 else "B slower"
    else:
        verdict = "no significant difference"
    return {"a_median": a_med, "b_median": b_med, "a_best": a_best, "b_best": b_best,
            "change_median": ch_med, "change_best": ch_best, "threshold": threshold, "verdict": verdict}


def parse_perf_csv(text):
    """cycles and instructions from `perf stat -x,` output (value, unit, event, ...)."""
    got = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split(",")
        if len(fields) < 3:
            continue
        value, event = fields[0].strip(), fields[2].strip()
        key = "instructions" if "instructions" in event else "cycles" if "cycles" in event else None
        if key is None:
            continue
        if not value.isdigit():
            raise ValueError(f"perf could not count {event} ({value})")
        got[key] = int(value)
    for key in ("cycles", "instructions"):
        if key not in got:
            raise ValueError(f"perf reported no {key} count")
    return got["cycles"], got["instructions"]


def cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


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

    def run(self, core, perf=None):
        """One `fork bench`: nodes, signature, nps, and (with perf, the perf executable) cycles and
        instructions, else None for both."""
        self.check_identity()
        pin = (lambda: os.sched_setaffinity(0, {core})) if hasattr(os, "sched_setaffinity") else None
        cmd, counts = [self.path, "bench"], None
        if perf:
            fd, counts = tempfile.mkstemp(suffix=".perf")
            os.close(fd)
            cmd = [perf, "stat", "-x,", "-e", PERF_EVENTS, "-o", counts, "--"] + cmd
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, check=True, preexec_fn=pin).stdout
            cycles = instructions = None
            if counts:
                with open(counts) as f:
                    try:
                        cycles, instructions = parse_perf_csv(f.read())
                    except ValueError as e:
                        fail(f"{self.label}: {e}")
        finally:
            if counts:
                os.remove(counts)
        nodes = int(re.search(r"nodes (\d+)", out).group(1))
        nps = int(re.search(r"nps (\d+)", out).group(1))
        sig = re.search(r"signature ([0-9a-f]+)", out).group(1)
        return nodes, sig, nps, cycles, instructions


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
    ap.add_argument("--perf", action="store_true",
                    help="run each bench under perf stat and judge cycles per node too (hardware counters needed)")
    ap.add_argument("--perf-command", default="perf", help=argparse.SUPPRESS)  # tests: a stand-in perf
    ap.add_argument("--json", help="write every run, the identities and the verdicts to this file")
    ap.add_argument("--label", default="", help="a name for this machine or run, in the JSON")
    args = ap.parse_args()
    if args.rounds < 1:
        fail("--rounds must be at least 1")
    sides = {"A": Side("A", args.a, args.a_variant, args.a_commit),
             "B": Side("B", args.b, args.b_variant, args.b_commit)}
    if sides["A"].sha == sides["B"].sha and not args.allow_identical:
        fail("A and B are byte-identical files (pass --allow-identical for an A/A run)")
    reported = {k: s.check_identity() for k, s in sides.items()}

    perf = args.perf_command if args.perf else None
    runs = []
    bench = {}
    for r in range(args.rounds):
        for side in (["A", "B"] if r % 2 == 0 else ["B", "A"]):
            nodes, sig, v, cycles, instructions = sides[side].run(args.core, perf)
            if bench.setdefault(side, (nodes, sig)) != (nodes, sig):
                fail(f"{side}: bench changed between runs ({bench[side]} then {(nodes, sig)})")
            runs.append({"round": r, "side": side, "nps": v, "cycles": cycles, "instructions": instructions})
    if args.same_nodes and bench["A"] != bench["B"]:
        fail(f"bench differs: A {bench['A']}, B {bench['B']}")

    def values(side, key):
        return [run[key] for run in runs if run["side"] == side]

    pinned = hasattr(os, "sched_setaffinity")
    for k, s in sides.items():
        print(f"{k} = {s.path}\n    variant {s.variant} | commit {reported[k]} | sha256 {s.sha}\n"
              f"    bench nodes {bench[k][0]} signature {bench[k][1]}")
    print(f"identity checked before the run and on all {2 * args.rounds} runs; "
          f"{args.rounds} interleaved rounds" + (f", core {args.core}" if pinned else ", not pinned"))
    nps = compare(values("A", "nps"), values("B", "nps"), NPS_FLOOR)
    print(f"nps     A median {nps['a_median']:>12.0f}  B median {nps['b_median']:>12.0f}  {100 * nps['change_median']:+.1f}%")
    print(f"        A best   {nps['a_best']:>12.0f}  B best   {nps['b_best']:>12.0f}  {100 * nps['change_best']:+.1f}%")
    print(f"noise threshold {100 * nps['threshold']:.1f}%: {nps['verdict']}")

    cycles = instructions = None
    if perf:
        cpn = {k: [run["cycles"] / bench[k][0] for run in runs if run["side"] == k] for k in sides}
        cycles = compare(cpn["A"], cpn["B"], CYCLES_FLOOR, lower_is_better=True)
        ia, ib = statistics.median(values("A", "instructions")), statistics.median(values("B", "instructions"))
        instructions = {"a_median": ia, "b_median": ib, "change": ib / ia - 1}
        print(f"cycles/node A median {cycles['a_median']:>9.1f}  B median {cycles['b_median']:>9.1f}  "
              f"{100 * cycles['change_median']:+.2f}% (positive: B faster)")
        print(f"            A best   {cycles['a_best']:>9.1f}  B best   {cycles['b_best']:>9.1f}  "
              f"{100 * cycles['change_best']:+.2f}%")
        print(f"cycles threshold {100 * cycles['threshold']:.2f}% (the 1% rule): {cycles['verdict']}")
        print(f"instructions per bench A median {ia:.0f}  B median {ib:.0f}  {100 * instructions['change']:+.3f}%")

    if args.json:
        doc = {"format": "fork-ab-search-1", "label": args.label, "cpu": cpu_model(),
               "rounds": args.rounds, "core": args.core if pinned else None,
               "sides": {k: {"path": s.path, "variant": s.variant, "commit": reported[k], "sha256": s.sha,
                             "nodes": bench[k][0], "signature": bench[k][1]} for k, s in sides.items()},
               "bench_identical": bench["A"] == bench["B"],
               "runs": runs, "nps": nps, "cycles_per_node": cycles, "instructions": instructions}
        with open(args.json, "w") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")


if __name__ == "__main__":
    main()
