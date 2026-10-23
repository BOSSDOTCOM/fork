"""Interleaved A/B microbenchmark comparison.

Runs two fork_micro binaries alternately (A B B A ...) for several rounds on
the same pinned core, so background load and thermal drift affect both sides
equally. Reports, per benchmark, the median of the per-round medians and the
minimum over all samples (load only ever adds time, so the minimum is the
most robust estimate of intrinsic cost), and the change of B relative to A.

An A/A run (identical binaries) gave 1 false "significant" verdict in 36
comparisons, so confirm gains under 5% with a second run.

usage: python -I bench/ab.py A/fork_micro.exe B/fork_micro.exe [--rounds 6] [--core 4] [--filter NAME]
"""

import argparse
import os
import statistics
import subprocess
import tempfile


def run(exe, core, reps, flt):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "r.txt")
        cmd = [exe, "--core", str(core), "--reps", str(reps), "--save", out]
        if flt:
            cmd += ["--filter", flt]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        res = {}
        for line in open(out):
            if line.startswith("#"):
                continue
            name, median, p10, p90, mn = line.split()
            res[name] = (float(median), float(mn))
        return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--core", type=int, default=4)
    ap.add_argument("--filter", default="")
    args = ap.parse_args()
    a_exe, b_exe = os.path.abspath(args.a), os.path.abspath(args.b)

    runs = {"A": [], "B": []}
    for r in range(args.rounds):
        order = ["A", "B"] if r % 2 == 0 else ["B", "A"]
        for side in order:
            runs[side].append(run(a_exe if side == "A" else b_exe, args.core, args.reps, args.filter))

    print(f"A = {args.a}\nB = {args.b}\n{args.rounds} interleaved rounds x {args.reps} reps\n")
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
