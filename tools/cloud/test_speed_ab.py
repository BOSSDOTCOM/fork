# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of the runner A/B's tools: bench/ab_search.py's noise rule, its perf counts and --json
output, and tools/cloud/speed_ab_merge.py (.github/workflows/speed-ab.yml).

The perf texts are real `perf stat -x, -e ... -o FILE -- true` output, captured from perf 6.18
under WSL Ubuntu on 2026-11-13 (bus-cycles:u is an event that kernel's PMU does not support).
The end-to-end tests run stand-in engines and a stand-in perf (Python scripts) and need a POSIX
system; the pure tests run everywhere.

    python3 -I -B -m unittest discover -s tools/cloud -p 'test_speed_ab*.py'
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "bench"))
import ab_search  # noqa: E402
import speed_ab_merge  # noqa: E402

PERF_OK = textwrap.dedent("""\
    # started on Fri Nov 13 12:50:17 2026

    410191,,cycles:u,413834,100.00,,
    131349,,instructions:u,413834,100.00,0.32,insn per cycle
    """)
PERF_UNSUPPORTED = textwrap.dedent("""\
    # started on Fri Nov 13 12:50:31 2026

    300549,,cycles:u,426459,100.00,,
    <not supported>,,bus-cycles:u,0,100.00,,
    """)


class CompareTest(unittest.TestCase):
    def test_nps_rule_by_hand(self):
        # medians 100.5 and 110.5 (+9.95%), bests 102 and 112 (+9.80%); spreads 1.4826 * 1.0 / 100.5
        # and / 110.5, so the threshold is the 3% floor (twice the larger spread is 2.95%).
        r = ab_search.compare([100, 102, 98, 101], [110, 111, 109, 112], 0.03)
        self.assertAlmostEqual(r["change_median"], 10 / 100.5)
        self.assertAlmostEqual(r["change_best"], 10 / 102)
        self.assertAlmostEqual(r["threshold"], 0.03)
        self.assertEqual(r["verdict"], "B faster")
        r = ab_search.compare([110, 111, 109, 112], [100, 102, 98, 101], 0.03)
        self.assertEqual(r["verdict"], "B slower")

    def test_spread_sets_the_threshold(self):
        # A's deviations 5, 5, 0 from 205: threshold 2 * 1.4826 * 5 / 205 = 7.23%, above both changes.
        r = ab_search.compare([200, 210, 205], [190, 195, 192], 0.01, lower_is_better=True)
        self.assertAlmostEqual(r["threshold"], 2 * 1.4826 * 5 / 205)
        self.assertAlmostEqual(r["change_median"], 205 / 192 - 1)
        self.assertAlmostEqual(r["change_best"], 200 / 190 - 1)
        self.assertEqual(r["verdict"], "no significant difference")

    def test_lower_is_better_reads_fewer_cycles_as_faster(self):
        r = ab_search.compare([200, 201, 200], [190, 191, 190], 0.01, lower_is_better=True)
        self.assertEqual((r["a_best"], r["b_best"]), (200, 190))
        self.assertAlmostEqual(r["threshold"], 0.01)
        self.assertEqual(r["verdict"], "B faster")

    def test_estimators_must_agree(self):
        # The medians move +10%, the bests -1%: no verdict.
        r = ab_search.compare([100, 100, 120], [110, 110, 118.8], 0.03)
        self.assertEqual(r["verdict"], "no significant difference")


class PerfCsvTest(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(ab_search.parse_perf_csv(PERF_OK), (410191, 131349))

    def test_uncounted_event_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "could not count bus-cycles"):
            ab_search.parse_perf_csv(PERF_UNSUPPORTED.replace("cycles:u,426459", "instructions:u,426459"))

    def test_missing_event_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "no instructions"):
            ab_search.parse_perf_csv(PERF_OK.splitlines()[2])


def make_doc(label, a_nps, b_nps, a_cycles=None, b_cycles=None, nodes=(1000, 1000), sig=("aa", "aa"),
             sha=("1" * 64, "2" * 64)):
    runs = [{"round": i, "side": "A", "nps": v, "cycles": a_cycles[i] if a_cycles else None,
             "instructions": 500 if a_cycles else None} for i, v in enumerate(a_nps)]
    runs += [{"round": i, "side": "B", "nps": v, "cycles": b_cycles[i] if b_cycles else None,
              "instructions": 490 if b_cycles else None} for i, v in enumerate(b_nps)]
    sides = {s: {"path": f"/x/{s}", "variant": "baseline", "commit": c * 40, "sha256": sha[i],
                 "nodes": nodes[i], "signature": sig[i]} for i, (s, c) in enumerate((("A", "a"), ("B", "b")))}
    cycles = None
    if a_cycles:
        cycles = ab_search.compare([c / nodes[0] for c in a_cycles], [c / nodes[1] for c in b_cycles], 0.01, True)
    return {"format": speed_ab_merge.FORMAT, "label": label, "cpu": "test", "rounds": len(a_nps), "core": 3,
            "sides": sides, "bench_identical": (nodes[0], sig[0]) == (nodes[1], sig[1]), "runs": runs,
            "nps": ab_search.compare(a_nps, b_nps, 0.03), "cycles_per_node": cycles,
            "instructions": {"a_median": 500, "b_median": 490, "change": -0.02} if a_cycles else None}


class MergeTest(unittest.TestCase):
    def test_one_runner_is_its_own_result(self):
        d = make_doc("r1", [100, 102, 98, 101], [110, 111, 109, 112], [2000, 2010, 1990, 2005], [1900, 1905, 1890, 1902])
        m = speed_ab_merge.merge([d])
        for key in ("change_median", "change_best", "threshold"):
            self.assertAlmostEqual(m["nps"][key], d["nps"][key])
            self.assertAlmostEqual(m["cycles_per_node"][key], d["cycles_per_node"][key])
        self.assertEqual(m["verdict"], "B faster")
        self.assertEqual(m["rule"], "the nps rule")

    def test_runners_of_different_speed_pool_by_ratio(self):
        # Two machines, one twice as fast, B 5% faster on both. Raw pooling buries it in the
        # machines' difference; pooling each runner's ratios keeps it.
        slow = make_doc("slow", [100, 101, 99, 100], [105, 106, 104, 105])
        fast = make_doc("fast", [200, 202, 198, 200], [210, 212, 208, 210])
        raw = ab_search.compare([100, 101, 99, 100, 200, 202, 198, 200], [105, 106, 104, 105, 210, 212, 208, 210], 0.03)
        self.assertEqual(raw["verdict"], "no significant difference")
        m = speed_ab_merge.merge([slow, fast])
        self.assertEqual(m["nps"]["verdict"], "B faster")
        self.assertEqual(m["runners"], 2)
        self.assertIsNone(m["cycles_per_node"])
        self.assertEqual(m["rule"], "the nps rule")

    def test_cycles_rule_decides_below_the_nps_floor(self):
        d = make_doc("r1", [100, 101, 100, 101], [102, 103, 102, 103], [3000, 3001, 3000, 3001], [2940, 2941, 2940, 2941])
        m = speed_ab_merge.merge([d])
        self.assertEqual(m["nps"]["verdict"], "no significant difference")
        self.assertEqual(m["verdict"], "B faster")
        self.assertIn("cycles-per-node 1% rule", m["rule"])

    def test_opposite_verdicts_are_a_conflict(self):
        d = make_doc("r1", [100, 101, 100, 101], [110, 111, 110, 111], [3000, 3001, 3000, 3001], [3100, 3101, 3100, 3101])
        self.assertEqual(speed_ab_merge.merge([d])["verdict"], "conflict")

    def test_different_benches_use_the_nps_rule_only(self):
        d = make_doc("r1", [100, 101, 100, 101], [101, 102, 101, 102], [3000, 3001, 3000, 3001], [2900, 2901, 2900, 2901],
                     nodes=(1000, 1100), sig=("aa", "bb"))
        m = speed_ab_merge.merge([d])
        self.assertEqual(m["verdict"], "no significant difference")
        self.assertIn("benches differ", m["rule"])
        self.assertIn("**Bench differs**", speed_ab_merge.report([d], m))

    def test_results_of_other_binaries_are_refused(self):
        one = make_doc("r1", [100, 101], [102, 103])
        other = make_doc("r2", [100, 101], [102, 103], sha=("1" * 64, "3" * 64))
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i, d in enumerate((one, other)):
                paths.append(os.path.join(tmp, f"{i}.json"))
                with open(paths[-1], "w") as f:
                    json.dump(d, f)
            with self.assertRaises(SystemExit) as e:
                speed_ab_merge.load(paths)
            self.assertIn("sha256", str(e.exception))

    def test_report_ends_with_the_verdict(self):
        d = make_doc("r1", [100, 101, 100, 101], [100, 101, 100, 101], sha=("1" * 64, "1" * 64))
        m = speed_ab_merge.merge([d])
        text = speed_ab_merge.report([d], m)
        self.assertTrue(text.splitlines()[-1].startswith("verdict: no significant difference"))
        self.assertIn("A/A run", text)
        self.assertIn("not measured (no runner exposed hardware counters)", text)


FAKE_ENGINE = """\
#!/usr/bin/env python3
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "cfg.json")) as f:
    cfg = json.load(f)
if sys.argv[1] == "version":
    print("Fork test\\narch x86-64-v3\\nvariant baseline | commit " + cfg["commit"] + " |")
elif sys.argv[1] == "bench":
    path = os.path.join(here, "count")
    n = int(open(path).read()) if os.path.exists(path) else 0
    with open(path, "w") as f:
        f.write(str(n + 1))
    nps = cfg["nps"][n % len(cfg["nps"])]
    print("nodes %d\\nsignature %s\\nnps %d" % (cfg["nodes"], cfg["signature"], nps))
"""

# perf stat -x, -e EVENTS -o FILE -- ENGINE bench: runs the engine, then writes the CSV with the
# engine's configured cycles for the run just made (or <not supported> for cycles).
FAKE_PERF = """\
#!/usr/bin/env python3
import json, os, subprocess, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
cmd = args[args.index("--") + 1:]
rc = subprocess.run(cmd).returncode
here = os.path.dirname(os.path.abspath(cmd[0]))
with open(os.path.join(here, "cfg.json")) as f:
    cfg = json.load(f)
n = int(open(os.path.join(here, "count")).read()) - 1
cycles = "<not supported>" if cfg.get("unsupported") else str(cfg["cycles"][n % len(cfg["cycles"])])
with open(out, "w") as f:
    f.write("# started on Fri Nov 13 12:50:17 2026\\n\\n")
    f.write(cycles + ",,cycles:u,413834,100.00,,\\n")
    f.write(str(cfg["instructions"]) + ",,instructions:u,413834,100.00,0.32,insn per cycle\\n")
sys.exit(rc)
"""


@unittest.skipUnless(os.name == "posix" and shutil.which("python3"), "stand-in engines need a POSIX system")
class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.perf = self.script("perf", FAKE_PERF)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def script(self, rel, text):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        return path

    def engine(self, side, **cfg):
        """A stand-in engine in its own folder, with its configuration beside it."""
        cfg.setdefault("commit", side * 40)
        cfg.setdefault("nodes", 1000)
        cfg.setdefault("signature", "00aa")
        cfg.setdefault("instructions", 5000)
        os.makedirs(os.path.join(self.tmp, side))
        with open(os.path.join(self.tmp, side, "cfg.json"), "w") as f:
            json.dump(cfg, f)
        return self.script(os.path.join(side, "fork"), FAKE_ENGINE + f"# {side}\n")

    def ab(self, a, b, *extra):
        cmd = [sys.executable, "-I", os.path.join(ROOT, "bench", "ab_search.py"), a, b,
               "--a-variant", "baseline", "--a-commit", "a" * 12, "--b-variant", "baseline",
               "--b-commit", "b" * 12, "--core", "0", *extra]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_json_with_counters(self):
        a = self.engine("a", nps=[1000, 1010, 990], cycles=[3000, 3003, 2997])
        b = self.engine("b", nps=[1100, 1110, 1090], cycles=[2800, 2803, 2797])
        out = os.path.join(self.tmp, "r.json")
        p = self.ab(a, b, "--rounds", "3", "--same-nodes", "--perf", "--perf-command", self.perf,
                    "--json", out, "--label", "runner 1")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("noise threshold", p.stdout)
        self.assertIn("cycles threshold 1.00% (the 1% rule): B faster", p.stdout)
        with open(out) as f:
            doc = json.load(f)
        self.assertEqual(doc["label"], "runner 1")
        self.assertTrue(doc["bench_identical"])
        self.assertEqual([r["side"] for r in doc["runs"]], ["A", "B", "B", "A", "A", "B"])
        self.assertEqual(sorted(r["cycles"] for r in doc["runs"] if r["side"] == "B"), [2797, 2800, 2803])
        self.assertAlmostEqual(doc["cycles_per_node"]["a_median"], 3.0)
        self.assertEqual(doc["nps"]["verdict"], "B faster")
        # The merge of this one result, through its command line, and a missing runner.
        merged = os.path.join(self.tmp, "m.json")
        cmd = [sys.executable, "-I", os.path.join(HERE, "speed_ab_merge.py"), out, "--json", merged]
        p = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.rstrip().splitlines()[-1].startswith("verdict: B faster (by the nps rule)"))
        p = subprocess.run(cmd + ["--expect-runners", "2"], capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("1 of 2 runners reported", p.stderr)

    def test_no_counters_without_perf(self):
        a = self.engine("a", nps=[1000])
        b = self.engine("b", nps=[1000])
        out = os.path.join(self.tmp, "r.json")
        p = self.ab(a, b, "--rounds", "2", "--json", out)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn("cycles", p.stdout)
        with open(out) as f:
            doc = json.load(f)
        self.assertIsNone(doc["cycles_per_node"])
        self.assertEqual(doc["nps"]["verdict"], "no significant difference")

    def test_uncounted_cycles_stop_the_run(self):
        a = self.engine("a", nps=[1000], cycles=[1], unsupported=True)
        b = self.engine("b", nps=[1000], cycles=[1])
        p = self.ab(a, b, "--rounds", "1", "--perf", "--perf-command", self.perf)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("could not count cycles:u", p.stderr)

    def test_different_benches_refused_with_same_nodes(self):
        a = self.engine("a", nps=[1000])
        b = self.engine("b", nps=[1000], nodes=999)
        p = self.ab(a, b, "--rounds", "1", "--same-nodes")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("bench differs", p.stderr)
        p = self.ab(a, b, "--rounds", "1")
        self.assertEqual(p.returncode, 0, p.stderr)


if __name__ == "__main__":
    unittest.main()
