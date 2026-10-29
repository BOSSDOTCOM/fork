#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# CI: bench parity for one engine binary, run directly (also when the binary
# is an SDE wrapper script, which CMake's execute_process cannot start on
# Windows). The same comparison as cmake/check_bench.cmake: the node count
# and signature of `fork bench` against tests/bench.ref, and of
# `fork perftbench` against tests/perft_bench.ref.
#
#   .github/ci/bench-parity.sh FORK_BINARY
set -euo pipefail
fork=${1:?usage: bench-parity.sh FORK_BINARY}
root=$(cd "$(dirname "$0")/../.." && pwd)
for pair in bench:bench.ref perftbench:perft_bench.ref; do
  cmd=${pair%%:*} ref=$root/tests/${pair#*:}
  out=$("$fork" "$cmd" | tr -d '\r')
  got=$(grep -E '^(nodes|signature) ' <<<"$out" | head -n 2)
  want=$(tr -d '\r' <"$ref" | grep -E '^(nodes|signature) ' | head -n 2)
  if [ "$got" != "$want" ]; then
    echo "::error::$cmd parity failed for $fork"
    echo "got:"; echo "$got"; echo "expected ($ref):"; echo "$want"
    exit 1
  fi
  echo "$cmd parity ok ($fork): $(tr '\n' ' ' <<<"$got")"
done
