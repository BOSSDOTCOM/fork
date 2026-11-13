# SPDX-License-Identifier: GPL-3.0-or-later

"""Merges the runners' results of a runner A/B (.github/workflows/speed-ab.yml) into one verdict.

Each runner ran bench/ab_search.py with --json on the same two binaries. The runners' CPUs differ,
so their raw nps cannot be pooled: each runner's runs are divided by that runner's median over all
its runs (both sides), which keeps every ratio and every relative spread as it was and removes the
machine's speed, and the pooled samples are judged by ab_search.py's own rule (compare()):
- nps: median and best both beyond max(3%, twice the spread), the same way;
- cycles per node (only runners whose counters worked): the same with a 1% floor, the rule for
  bench-identical speed changes (DESIGN.md §6, 2026-11-07 decision 8).
With one runner the pooled numbers are that runner's own.

The verdict: if the benches differ (allowed only by the workflow's explicit input) the change
alters the search and only the nps rule applies. If they are identical, the nps rule decides when
it sees a difference, else the cycles rule; opposite verdicts are reported as a conflict.

usage: python3 -I tools/cloud/speed_ab_merge.py results/*/result.json [--json merged.json]
           [--expect-runners N]
Prints a Markdown report whose last line starts "verdict:".
"""

import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bench"))
from ab_search import CYCLES_FLOOR, NPS_FLOOR, compare  # noqa: E402

FORMAT = "fork-ab-search-1"
IDENTITY_KEYS = ("variant", "commit", "sha256", "nodes", "signature")


def fail(msg):
    sys.exit(f"speed_ab_merge.py: error: {msg}")


def load(paths):
    docs = []
    for p in paths:
        with open(p) as f:
            doc = json.load(f)
        if doc.get("format") != FORMAT:
            fail(f"{p}: not an ab_search.py --json result")
        docs.append(doc)
    if not docs:
        fail("no results")
    first = docs[0]["sides"]
    for p, d in zip(paths, docs):
        for side in ("A", "B"):
            for key in IDENTITY_KEYS:
                if d["sides"][side][key] != first[side][key]:
                    fail(f"{p}: side {side} {key} {d['sides'][side][key]!r} differs from "
                         f"{paths[0]}'s {first[side][key]!r}: not the same A/B")
    return docs


def normalised(doc, key):
    """The runner's A and B values of key (per node for cycles), divided by its median over both."""
    nodes = {s: doc["sides"][s]["nodes"] for s in ("A", "B")}
    vals = {s: [r[key] / (nodes[s] if key == "cycles" else 1) for r in doc["runs"] if r["side"] == s]
            for s in ("A", "B")}
    scale = statistics.median(vals["A"] + vals["B"])
    return [v / scale for v in vals["A"]], [v / scale for v in vals["B"]]


def merge(docs):
    a_nps, b_nps, a_cpn, b_cpn = [], [], [], []
    counted = [d for d in docs if d.get("cycles_per_node")]
    for d in docs:
        a, b = normalised(d, "nps")
        a_nps += a
        b_nps += b
    for d in counted:
        a, b = normalised(d, "cycles")
        a_cpn += a
        b_cpn += b
    nps = compare(a_nps, b_nps, NPS_FLOOR)
    cycles = compare(a_cpn, b_cpn, CYCLES_FLOOR, lower_is_better=True) if counted else None
    instructions = (statistics.median(d["instructions"]["change"] for d in counted) if counted else None)
    identical = docs[0]["bench_identical"]
    none = "no significant difference"
    if not identical:
        verdict, rule = nps["verdict"], "the nps rule only: the benches differ, so this A/B changes the search"
    elif nps["verdict"] != none and cycles and cycles["verdict"] not in (none, nps["verdict"]):
        verdict, rule = "conflict", f"nps says {nps['verdict']}, cycles per node says {cycles['verdict']}"
    elif nps["verdict"] != none:
        verdict, rule = nps["verdict"], "the nps rule"
    elif cycles and cycles["verdict"] != none:
        verdict, rule = cycles["verdict"], "the cycles-per-node 1% rule (the nps rule not met)"
    else:
        verdict = none
        rule = "neither the nps rule nor the cycles-per-node rule" if cycles else \
            "the nps rule (no hardware counters: cycles per node not measured)"
    return {"runners": len(docs), "counted_runners": len(counted), "bench_identical": identical,
            "same_binary": docs[0]["sides"]["A"]["sha256"] == docs[0]["sides"]["B"]["sha256"],
            "nps": nps, "cycles_per_node": cycles, "instructions_change": instructions,
            "verdict": verdict, "rule": rule}


def pct(x, digits=1):
    return f"{100 * x:+.{digits}f}%"


def report(docs, m):
    s = docs[0]["sides"]
    out = [f"### Runner A/B: A {s['A']['commit'][:12]} vs B {s['B']['commit'][:12]}", ""]
    if m["same_binary"]:
        out.append("A/A run: both sides are the same binary (the noise floor).")
    bench = f"{s['A']['nodes']} / {s['A']['signature']}"
    if m["bench_identical"]:
        out.append(f"Bench identical: {bench}.")
    else:
        out.append(f"**Bench differs** (allowed by the run's input): A {bench}, "
                   f"B {s['B']['nodes']} / {s['B']['signature']}.")
    out += ["", "| runner | CPU | rounds | nps A / B median | nps median / best | threshold | nps verdict "
            "| cycles/node median / best | threshold | cycles verdict |", "|---|---|---|---|---|---|---|---|---|---|"]
    for d in docs:
        n, c = d["nps"], d.get("cycles_per_node")
        cyc = (f"{pct(c['change_median'], 2)} / {pct(c['change_best'], 2)} | {100 * c['threshold']:.2f}% | "
               f"{c['verdict']}") if c else "no counters | | "
        out.append(f"| {d.get('label') or '?'} | {d.get('cpu', '?')} | {d['rounds']} | "
                   f"{n['a_median']:.0f} / {n['b_median']:.0f} | {pct(n['change_median'])} / {pct(n['change_best'])} | "
                   f"{100 * n['threshold']:.1f}% | {n['verdict']} | {cyc} |")
    n, c = m["nps"], m["cycles_per_node"]
    out += ["", f"Pooled over {m['runners']} runner(s) (each runner scaled to its own median):",
            f"- nps: median {pct(n['change_median'])}, best {pct(n['change_best'])}, "
            f"noise threshold {100 * n['threshold']:.1f}%: {n['verdict']}"]
    if c:
        out.append(f"- cycles per node ({m['counted_runners']} of {m['runners']} runner(s) with counters): "
                   f"median {pct(c['change_median'], 2)}, best {pct(c['change_best'], 2)} (positive: B faster), "
                   f"threshold {100 * c['threshold']:.2f}%: {c['verdict']}")
        out.append(f"- instructions per bench (median over runners): {pct(m['instructions_change'], 3)}")
    else:
        out.append("- cycles per node: not measured (no runner exposed hardware counters)")
    out += ["", f"verdict: {m['verdict']} (by {m['rule']})"]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--json", help="write the merged numbers here")
    ap.add_argument("--expect-runners", type=int, help="fail (after the report) unless this many results came")
    args = ap.parse_args()
    docs = load(args.results)
    m = merge(docs)
    print(report(docs, m))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(m, f, indent=1)
            f.write("\n")
    if args.expect_runners is not None and len(docs) != args.expect_runners:
        fail(f"{len(docs)} of {args.expect_runners} runners reported")


if __name__ == "__main__":
    main()
