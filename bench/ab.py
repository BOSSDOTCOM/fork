"""Interleaved A/B microbenchmark comparison.

Runs two fork_micro binaries alternately (A B B A ...) for several rounds on
the same pinned core, so background load and thermal drift affect both sides
equally. Reports, per benchmark, the median of the per-round medians and the
minimum over all samples (load only ever adds time, so the minimum is the
most robust estimate of intrinsic cost), and the change of B relative to A.

An A/A run (identical binaries) gave 1 false "significant" verdict in 36
comparisons, so confirm gains under 5% with a second run.

Identity checks (a mislabeled binary once produced a wrong comparison):
each side's expected variant and commit are required and must match what the
binary reports about itself (fork_micro embeds them at build time, see
cmake/build_id.cmake), before the first round and on every run. The SHA-256
of each file is recorded at the start and re-checked before every run, and
identical A and B files are refused unless --allow-identical is given (A/A
runs). Any mismatch stops the run with an error.

A commit is given as a hash or hash prefix (at least 7 characters), with
"-dirty" appended when the build came from a tree with uncommitted changes
(the binary reports the same suffix). `git rev-parse HEAD` gives the hash.

usage: python -I bench/ab.py A/fork_micro.exe B/fork_micro.exe
           --a-variant baseline --a-commit 1234abc --b-variant NAME --b-commit 1234abc
           [--rounds 6] [--core 4] [--filter NAME] [--allow-identical]
"""

import argparse
import hashlib
import os
import re
import statistics
import subprocess
import sys
import tempfile

IDENTITY = re.compile(r"variant (\S+) \| commit (\S+) \|")


def fail(msg):
    sys.exit(f"ab.py: error: {msg}")


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

    def check_file(self):
        if sha256(self.path) != self.sha:
            fail(f"{self.label}: {self.path} changed during the run (SHA-256 differs)")

    def check_identity(self, header, where):
        m = IDENTITY.search(header)
        if not m:
            fail(f"{self.label}: {where} has no 'variant ... | commit ...' identity "
                 f"(built before the harness fix?): {header.strip()!r}")
        variant, commit = m.groups()
        if variant != self.variant:
            fail(f"{self.label}: binary reports variant '{variant}', expected '{self.variant}' ({self.path})")
        if not commit_matches(self.commit, commit):
            fail(f"{self.label}: binary reports commit '{commit}', expected '{self.commit}' ({self.path})")
        return commit

    def probe(self):
        # A filter that matches no benchmark: fork_micro only sets up and prints its header line.
        p = subprocess.run([self.path, "--reps", "1", "--filter", "no-such-benchmark"],
                           capture_output=True, text=True)
        if p.returncode != 0:
            fail(f"{self.label}: {self.path} exited with {p.returncode} (not a fork_micro?): "
                 f"{p.stderr.strip()[:200]!r}")
        out = p.stdout
        return self.check_identity(out.splitlines()[0] if out else "", "output")

    def run(self, core, reps, flt):
        self.check_file()
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.txt")
            cmd = [self.path, "--core", str(core), "--reps", str(reps), "--save", out]
            if flt:
                cmd += ["--filter", flt]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
            with open(out) as f:
                lines = f.read().splitlines()
        self.check_identity(lines[0] if lines else "", "saved file")
        res = {}
        for line in lines:
            if line.startswith("#"):
                continue
            name, median, _p10, _p90, mn = line.split()
            res[name] = (float(median), float(mn))
        return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--a-variant", required=True)
    ap.add_argument("--a-commit", required=True)
    ap.add_argument("--b-variant", required=True)
    ap.add_argument("--b-commit", required=True)
    ap.add_argument("--allow-identical", action="store_true",
                    help="permit byte-identical A and B (A/A noise runs)")
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--core", type=int, default=4)
    ap.add_argument("--filter", default="")
    args = ap.parse_args()
    sides = {"A": Side("A", args.a, args.a_variant, args.a_commit),
             "B": Side("B", args.b, args.b_variant, args.b_commit)}
    if sides["A"].sha == sides["B"].sha and not args.allow_identical:
        fail("A and B are byte-identical files (pass --allow-identical for an A/A run)")
    reported = {k: s.probe() for k, s in sides.items()}

    runs = {"A": [], "B": []}
    for r in range(args.rounds):
        order = ["A", "B"] if r % 2 == 0 else ["B", "A"]
        for side in order:
            runs[side].append(sides[side].run(args.core, args.reps, args.filter))
    for s in sides.values():
        s.check_file()

    for k, s in sides.items():
        print(f"{k} = {args.a if k == 'A' else args.b}\n"
              f"    variant {s.variant} | commit {reported[k]} | sha256 {s.sha}")
    print(f"identity checked before the run and on all {2 * args.rounds} runs\n"
          f"{args.rounds} interleaved rounds x {args.reps} reps\n")
    print(f"{'benchmark':<18} {'A med':>10} {'B med':>10} {'change':>8}   {'A min':>10} {'B min':>10} {'change':>8}  verdict")
    for name in runs["A"][0]:
        a_meds = [r[name][0] for r in runs["A"]]
        b_meds = [r[name][0] for r in runs["B"]]
        a_med, b_med = statistics.median(a_meds), statistics.median(b_meds)
        a_min = min(r[name][1] for r in runs["A"])
        b_min = min(r[name][1] for r in runs["B"])
        ch_med = (b_med - a_med) / a_med
        ch_min = (b_min - a_min) / a_min
        # Threshold: 3% (an A/A run of identical binaries showed up to 3%), or
        # twice the round-to-round variation of this benchmark if larger.
        # Robust spread (scaled median absolute deviation): one disturbed
        # round must not hide a real change.
        def mad(xs, m):
            return 1.4826 * statistics.median(abs(x - m) for x in xs) / m
        noise = max(mad(a_meds, a_med), mad(b_meds, b_med))
        threshold = max(0.03, 2 * noise)
        # A real change shows up in both estimators with the same sign.
        if abs(ch_min) > threshold and abs(ch_med) > threshold and (ch_min > 0) == (ch_med > 0):
            verdict = "B faster" if ch_min < 0 else "B slower"
        else:
            verdict = "no significant difference"
        print(f"{name:<18} {a_med:>10.2f} {b_med:>10.2f} {100 * ch_med:>+7.1f}%   "
              f"{a_min:>10.2f} {b_min:>10.2f} {100 * ch_min:>+7.1f}%  {verdict}")


if __name__ == "__main__":
    main()
