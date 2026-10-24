"""Time-boxed libFuzzer run with plateau detection.

Runs one fuzz target in libFuzzer fork mode on all cores, at most
--max-seconds, and stops early when coverage ("cov:") has not grown for
--plateau-seconds. Prints final coverage, whether it plateaued, and any
crashes (libFuzzer writes crash-*/leak-*/timeout-* artifacts).

usage: python -I tools/fuzz/run_fuzz.py --target build/clang-fuzz/fuzz_fen.exe
           --corpus fuzz/corpus/fen [--max-seconds 180] [--plateau-seconds 60] [--jobs N]
"""

import argparse
import glob
import os
import re
import subprocess
import sys
import threading
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--max-seconds", type=int, default=180)
    ap.add_argument("--plateau-seconds", type=int, default=60)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--artifacts", default="fuzz/artifacts")
    a = ap.parse_args()

    target = os.path.abspath(a.target)
    os.makedirs(a.corpus, exist_ok=True)
    artifacts = os.path.abspath(a.artifacts) + os.sep
    os.makedirs(artifacts, exist_ok=True)
    before = set(glob.glob(artifacts + "*"))

    cmd = [target, f"-fork={a.jobs}", f"-max_total_time={a.max_seconds}", "-ignore_crashes=1",
           f"-artifact_prefix={artifacts}", "-print_final_stats=1", a.corpus]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            errors="replace")
    start = time.time()
    state = {"cov": 0, "ft": 0, "execs": 0, "last_growth": start, "lines": []}
    lock = threading.Lock()

    def reader():
        for line in proc.stdout:
            with lock:
                state["lines"].append(line.rstrip())
                m = re.search(r"#(\d+).*?cov: (\d+) ft: (\d+)", line)
                if m:
                    execs, cov, ft = int(m[1]), int(m[2]), int(m[3])
                    state["execs"] = max(state["execs"], execs)
                    if cov > state["cov"]:
                        state["cov"] = cov
                        state["last_growth"] = time.time()
                    state["ft"] = max(state["ft"], ft)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    plateaued = False
    while proc.poll() is None:
        time.sleep(1)
        with lock:
            if time.time() - state["last_growth"] >= a.plateau_seconds and state["cov"] > 0:
                plateaued = True
                break
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
    t.join(timeout=5)
    elapsed = time.time() - start

    crashes = sorted(set(glob.glob(artifacts + "*")) - before)
    crash_lines = [l for l in state["lines"] if "ERROR:" in l or "deadly signal" in l or "==ERROR" in l]
    name = os.path.basename(target)
    print(f"{name}: {elapsed:.0f} s, {a.jobs} jobs, cov {state['cov']}, ft {state['ft']}, "
          f"execs {state['execs']:,}, corpus {len(os.listdir(a.corpus))} files, "
          f"{'plateaued (no coverage growth for ' + str(a.plateau_seconds) + ' s)' if plateaued else 'still growing at the time limit'}, "
          f"coverage last grew at {state['last_growth'] - start:.0f} s, "
          f"{len(crashes)} crash artifacts")
    for c in crashes:
        print("  CRASH ARTIFACT", c)
    for l in crash_lines[:10]:
        print("  ", l)
    sys.exit(1 if crashes or crash_lines else 0)


if __name__ == "__main__":
    main()
