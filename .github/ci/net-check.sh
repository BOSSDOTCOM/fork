#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# CI: one bake-off network built into Fork and checked (owner, 2026-10-31:
# every round-2 architecture in CI). A clang release build of `fork` only
# (no tests, so no test data to fetch) with nets/NET.fnet embedded, then:
# `fork version` names the network; netcheck against tests/nnue/NET.parity
# (Fork's inference equals the reference's R-int on all 446 positions);
# and bench parity against tests/bench-NET.ref (.github/ci/bench-parity.sh).
# A missing parity file or bench reference fails the check rather than
# skipping it.
#
#   .github/ci/net-check.sh NET [BUILD_DIR]
set -euo pipefail
net=${1:?usage: net-check.sh NET [BUILD_DIR]}
root=$(cd "$(dirname "$0")/../.." && pwd)
build=${2:-$root/build/net-$net}
for f in "nets/$net.fnet" "tests/nnue/$net.parity" "tests/bench-$net.ref"; do
  [ -f "$root/$f" ] || { echo "::error::$f is missing"; exit 1; }
done
cd "$root"
cmake --preset clang-release -B "$build" -DFORK_BUILD_TESTS=OFF -DFORK_NET="$root/nets/$net.fnet" >/dev/null
cmake --build "$build" --target fork
fork=$build/fork
named=$("$fork" version | tr -d '\r' | sed -n 's/^net //p')
[ "$named" = "$net" ] || { echo "::error::fork version names the network '$named', not '$net'"; exit 1; }
"$fork" netcheck "$root/tests/nnue/$net.parity"
bash "$root/.github/ci/bench-parity.sh" "$fork"
