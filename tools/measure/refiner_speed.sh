#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Idea 59 step 3, the speed gate S1 (M1, M2; docs/research/boundary-refiner/
# step3-plan.md §4.5 and the owner's additions of 2026-11-08): what one
# refiner call costs, part by part, and what the refiner costs the whole
# search at the real gate rate, against the break-even estimate and, in the
# second window, the owner's cost gate (at most about 3.5% of nps in game).
#
# Two windows. The first (2026-11-08) measured the entry layer's shapes on
# native builds. The second measures the 8-wide shape at the dense-weight
# bounds 64 and 32: on x86-64-v3 builds (the AVX2 path, what the GitHub SPRT
# shards run; the cost gate judges these) and on the VNNI preset (TCEC).
# `run` and `profile` only in a quiet window the owner chooses (data
# generation and every other CPU job suspended), from a committed tree (the
# binaries report their commit, and the A/B harnesses check it).
#   bash tools/measure/refiner_speed.sh build [second]    # zero refiners, the window's builds, their benches
#   bash tools/measure/refiner_speed.sh run [second]      # the interleaved A/B rounds and fork_micro's parts (quiet)
#   FORK_REPO=/mnt/c/Users/<user>/fork bash tools/measure/refiner_speed.sh profile COMMIT
#                                                         # WSL Linux: a sampling profile of `fork bench` (quiet)
#   bash tools/measure/refiner_speed.sh report [second]   # anywhere: per-call cost, nps loss in game, the lines
# Results go to $STEP3_AB_DIR (default ~/fork-measure/i59s3), the second
# window's to its subfolder `second`.
set -euo pipefail
cd "$(dirname "$0")/../.."
here=$(pwd)
out=${STEP3_AB_DIR:-$HOME/fork-measure/i59s3}
window=first
if [ "${1:-}" != profile ] && [ "${2:-}" = second ]; then
  window=second
  out=$out/second
fi
mkdir -p "$out"
py=${PYTHON:-python}
exe=
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) exe=.exe ;; esac
# The tree must be committed; the commit the binaries will report.
clean() {
  git diff --quiet HEAD -- || { echo "commit first: the A/B needs a clean tree" >&2; exit 1; }
  commit=$(git rev-parse HEAD)
}
zero() {  # zero ARCH L1 BOUND OUT: a zero refiner of that shape for S512ppr3
  $py -I tools/nnue/refiner.py zero --base nets/s512ppr3.fnet --arch "$1" --l1 "$2" --bound "$3" --cap 20000 --out "$4"
}
build() {  # build PRESET LABEL [REFINER_FILE]: build/ab-LABEL
  cmake --preset "$1" -B "build/ab-$2" -DFORK_BUILD_LABEL="$2" ${3:+-DFORK_REFINER_NET="$3"} >/dev/null &&
    cmake --build "build/ab-$2"
}
if [ $window = first ]; then
  shapes="refiner16 refiner8 danger16"   # try 1's shape, the narrower entry layer, the danger summary
else
  # The 8-wide shape at bounds 64 and 32: x86-64-v3 (the AVX2 path) and the
  # VNNI preset, each with its own refiner-less baseline.
  shapes="refiner8v3 refiner8b32v3 refiner8vnni refiner8b32vnni"
fi

case "${1:-}" in
  build)
    clean
    . scripts/env.sh
    if [ $window = first ]; then
      zero 1 8 64 "$out/refiner-zero8.frnet"
      zero 2 16 64 "$out/refiner-danger16.frnet"
      cmake --preset clang-release >/dev/null && cmake --build build/clang-release
      build clang-release refiner16 "$here/tests/nnue/refiner-zero.frnet"
      build clang-release refiner8 "$out/refiner-zero8.frnet"
      build clang-release danger16 "$out/refiner-danger16.frnet"
      # phase-4's release build (d89814f), for the default build's own price.
      if [ ! -x build/ab-phase4/fork$exe ]; then
        rm -rf build/ab-phase4-src && git worktree add --detach build/ab-phase4-src d89814f >/dev/null
        cmake --preset clang-release -S build/ab-phase4-src -B build/ab-phase4 -DFORK_BUILD_TESTS=OFF >/dev/null &&
          cmake --build build/ab-phase4 --target fork
        git worktree remove --force build/ab-phase4-src
      fi
      list="ab-phase4 clang-release ab-refiner16 ab-refiner8 ab-danger16"
    else
      zero 1 8 64 "$out/refiner-zero8.frnet"
      zero 1 8 32 "$out/refiner-zero8b32.frnet"
      build clang-v3 baselinev3
      build clang-v3 refiner8v3 "$out/refiner-zero8.frnet"
      build clang-v3 refiner8b32v3 "$out/refiner-zero8b32.frnet"
      build clang-vnni baselinevnni
      build clang-vnni refiner8vnni "$out/refiner-zero8.frnet"
      build clang-vnni refiner8b32vnni "$out/refiner-zero8b32.frnet"
      list="ab-baselinev3 ab-refiner8v3 ab-refiner8b32v3 ab-baselinevnni ab-refiner8vnni ab-refiner8b32vnni"
    fi
    for b in $list; do
      echo "== $b (every one: 14149617 / 1cb0717f040c294d)"; build/$b/fork$exe bench 2>&1 | grep -v '^nps'
    done
    ;;

  run)
    clean
    ab() { $py -I bench/ab_search.py "$@" --same-nodes --rounds 10; }
    # The gate's call rates on the bench (the nodes and calls behind the per-call cost).
    for v in $shapes; do
      build/ab-$v/fork$exe bench 25 25 2>"$out/tally-$v-25-25.txt" >/dev/null
      build/ab-$v/fork$exe bench 25 10 2>"$out/tally-$v-25-10.txt" >/dev/null
    done
    # 1. Per-call cost: each shape against itself, gate off (-1 -1) against on,
    #    at setting (b) 25/25 and setting (a) 25/10: the same code and tree,
    #    only the refiner's calls differ.
    for v in $shapes; do
      for s in "25 25" "25 10"; do
        ab build/ab-$v/fork$exe build/ab-$v/fork$exe --a-variant $v --a-commit "$commit" --b-variant $v \
          --b-commit "$commit" --a-args "-1 -1" --b-args "$s" | tee "$out/ab-$v-off-${s// /-}.txt"
      done
    done
    if [ $window = first ]; then
      # 2. G1 on try 1's shape: 25/25 against 25/25 with reused evaluations refined.
      build/ab-refiner16/fork$exe bench 25 25 reused 2>"$out/tally-refiner16-g1.txt" >/dev/null
      ab build/ab-refiner16/fork$exe build/ab-refiner16/fork$exe --a-variant refiner16 --a-commit "$commit" \
        --b-variant refiner16 --b-commit "$commit" --a-args "25 25" --b-args "25 25 reused" | tee "$out/ab-refiner16-g1.txt"
      # 3. The overhead without calls (gate tests at every computed evaluation,
      #    the TT flag, the frames' fields, code layout): the release build
      #    against the refiner build with its gate off.
      ab build/clang-release/fork$exe build/ab-refiner16/fork$exe --a-variant baseline --a-commit "$commit" \
        --b-variant refiner16 --b-commit "$commit" --b-args "-1 -1" | tee "$out/ab-release-refiner16-off.txt"
      # 4. The whole price at the build's defaults (25/25): release against refiner.
      ab build/clang-release/fork$exe build/ab-refiner16/fork$exe --a-variant baseline --a-commit "$commit" \
        --b-variant refiner16 --b-commit "$commit" | tee "$out/ab-release-refiner16.txt"
      # 5. The default build's own price (the TT flag's argument, the merged
      #    measurement code): phase-4's release build against this one.
      ab build/ab-phase4/fork$exe build/clang-release/fork$exe --a-variant baseline --a-commit d89814f \
        --b-variant baseline --b-commit "$commit" | tee "$out/ab-phase4-release.txt"
      micro_filters="refiner exposed danger gate_fires"
    else
      # 2. Each target's overhead without calls and whole price at the
      #    defaults (25/25), against its own refiner-less baseline.
      for t in v3 vnni; do
        ab build/ab-baseline$t/fork$exe build/ab-refiner8$t/fork$exe --a-variant baseline$t --a-commit "$commit" \
          --b-variant refiner8$t --b-commit "$commit" --b-args "-1 -1" | tee "$out/ab-baseline$t-refiner8$t-off.txt"
        for v in refiner8$t refiner8b32$t; do
          ab build/ab-baseline$t/fork$exe build/ab-$v/fork$exe --a-variant baseline$t --a-commit "$commit" \
            --b-variant $v --b-commit "$commit" | tee "$out/ab-baseline$t-$v.txt"
        done
      done
      micro_filters="refiner"
    fi
    # 6. M2, one call part by part (fork_micro; interleaved, repeated): each
    #    shape's parts as an A/A of its own binary (both columns are the
    #    same build: their agreement is the noise), then shape against shape.
    for v in $shapes; do
      for f in $micro_filters; do
        $py -I bench/ab.py build/ab-$v/fork_micro$exe build/ab-$v/fork_micro$exe --allow-identical --rounds 10 \
          --a-variant $v --a-commit "$commit" --b-variant $v --b-commit "$commit" --filter $f | tee "$out/micro-$v-$f.txt"
      done
    done
    if [ $window = first ]; then
      pairs="refiner16:refiner8 refiner16:danger16"
    else
      pairs="refiner8v3:refiner8b32v3 refiner8vnni:refiner8b32vnni refiner8v3:refiner8vnni"
    fi
    for pair in $pairs; do
      a=${pair%%:*} b=${pair#*:}
      $py -I bench/ab.py build/ab-$a/fork_micro$exe build/ab-$b/fork_micro$exe --rounds 10 --a-variant $a \
        --a-commit "$commit" --b-variant $b --b-commit "$commit" --filter refiner | tee "$out/micro-$a-vs-$b.txt"
    done
    if [ $window = first ]; then
      echo "next: bash $0 report (and, in WSL, FORK_REPO=... bash $0 profile $commit)"
    else
      echo "next: bash $0 report second"
    fi
    ;;

  profile)
    # WSL Linux (perf; tools/perf_gate.sh's method), from the Windows
    # repository's object store (a Windows worktree's .git link does not
    # resolve in WSL): FORK_REPO=/mnt/c/Users/<user>/fork bash <this> profile COMMIT.
    # The commit is built with the zero refiner in ~/fork-perf, then `fork
    # bench` is sampled with the gate on (25/25) and off (-1 -1); the top 25
    # symbols by self time each. LTO inlines most of the refiner into the
    # search: read the two profiles side by side, and fork_micro's parts for
    # the split.
    command -v perf >/dev/null || { echo "perf not found (run this step in WSL)" >&2; exit 1; }
    [ -n "${FORK_REPO:-}" ] && [ -n "${2:-}" ] || { echo "usage: FORK_REPO=<repo> bash $0 profile COMMIT" >&2; exit 2; }
    c=$(git -C "$FORK_REPO" rev-parse --short=7 "$2")
    d=$HOME/fork-perf/refiner-$c
    if [ ! -x "$d/fork" ]; then
      rm -rf "$d-src" && git clone -q "$FORK_REPO" "$d-src" && git -C "$d-src" checkout -q "$c"
      cmake -S "$d-src" -B "$d-src/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DFORK_BUILD_TESTS=OFF \
        -DCMAKE_CXX_COMPILER=clang++ -DFORK_REFINER_NET="$d-src/tests/nnue/refiner-zero.frnet" >/dev/null
      cmake --build "$d-src/build" --target fork >/dev/null
      mkdir -p "$d" && cp "$d-src/build/fork" "$d/fork" && cp "$d-src/tools/perf_symbols.py" "$d/" && rm -rf "$d-src"
    fi
    "$d/fork" bench 2>&1 | grep -v '^nps'   # 14149617 / 1cb0717f040c294d
    for s in "25 25" "-1 -1"; do
      tag=${s// /_}
      (cd "$d" && perf record -q -o "perf-$tag.data" -- ./fork bench $s >/dev/null 2>&1)
      perf report -i "$d/perf-$tag.data" --stdio --no-children --sort symbol 2>/dev/null |
        python3 -I "$d/perf_symbols.py" "$d/fork" 25 | tee "$out/profile-$tag.txt"
    done
    ;;

  report)
    # The arithmetic (step3-plan.md §4.1; the owner's additions):
    # - per-call cost in node times c = (nps_off / nps_on - 1) / r_bench,
    #   r_bench the bench's calls per node at that setting;
    # - nps loss at the real gate rate L = 1 - 1 / (1 + r_game c), r_game the
    #   oracle's in-game calls per node at 800k nodes: (b) 6.97%, (a) 3.81%
    #   (oracle-rates-b/-a, S512r2's replays; S512ppr3's own rates in game are
    #   not measured yet: X3 / M4 follow);
    # - price at 1.5 Elo per 1% of nps (1.26-1.80); the expected gain's
    #   upper-bound proxy, the oracle's fixed-node gain against S512r2: (b)
    #   +41.0 +/- 10.0, (a) +29.8 +/- 9.8; break-even loss L* = G / k, with
    #   the interval [(G - e) / 1.80, (G + e) / 1.26];
    # - the lines: 3% (design), 3.5% (the owner's cost gate for the AVX2
    #   path, 2026-11-08), 5% (hard).
    $py -I - "$out" <<'PY'
import re
import sys
from pathlib import Path

out = Path(sys.argv[1])
GAME = {'25-25': 0.0697, '25-10': 0.0381}
GAIN = {'25-25': (41.0, 10.0), '25-10': (29.8, 9.8)}
K = (1.26, 1.5, 1.80)
print('Break-even nps loss L* = G / k (the oracle gain as the upper-bound proxy):')
for s, (g, e) in GAIN.items():
    print(f'  setting {s}: L* = {g / K[1]:.1f}% [{(g - e) / K[2]:.1f}%, {(g + e) / K[0]:.1f}%]')
for f in sorted(out.glob('ab-*-off-25-*.txt')):
    shape, s = re.match(r'ab-(.+)-off-(25-\d+)\.txt', f.name).groups()
    text = f.read_text()
    a = float(re.search(r'A median\s+(\d+)', text).group(1))
    b = float(re.search(r'B median\s+(\d+)', text).group(1))
    tally = (out / f'tally-{shape}-{s}.txt').read_text()
    nodes = int(re.search(r'refiner nodes (\d+)', tally).group(1))
    calls = int(re.search(r'main_calls (\d+)', tally).group(1)) + int(re.search(r'quiesce_calls (\d+)', tally).group(1))
    r_bench = calls / nodes
    c = (a / b - 1) / r_bench
    loss = 1 - 1 / (1 + GAME[s] * c)
    g, e = GAIN[s]
    line = 'within 3%' if loss <= 0.03 else 'within the 3.5% gate' if loss <= 0.035 else \
        'within 5%' if loss <= 0.05 else 'over 5%'
    print(f'{shape} {s}: bench {100 * (1 - b / a):.2f}% nps at {100 * r_bench:.2f}% of nodes called; '
          f'{c * 1e9 / a:.0f} ns per call ({c:.3f} node times); at the in-game rate {100 * GAME[s]:.2f}%: '
          f'{100 * loss:.2f}% nps, price {K[1] * 100 * loss:.1f} Elo [{K[0] * 100 * loss:.1f}, {K[2] * 100 * loss:.1f}]; '
          f'expected net against the proxy {g - K[1] * 100 * loss:+.1f} '
          f'[{g - e - K[2] * 100 * loss:+.1f}, {g + e - K[0] * 100 * loss:+.1f}]; lines: {line}')
PY
    ;;

  *) echo "usage: bash $0 build|run|report [second] | profile COMMIT" >&2; exit 2 ;;
esac
