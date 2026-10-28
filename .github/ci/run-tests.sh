#!/usr/bin/env bash
# CI: the fast suite (every test not labelled slow) of one CMake build, with
# the same guarantees as scripts/check.sh: bench parity must have run and
# passed (unless REQUIRE_BENCH=0, when the caller checks it with
# bench-parity.sh), and so must no_alloc unless the build cannot have it
# (TSan, MSan: REQUIRE_NO_ALLOC=0; .claude/rules/testing.md). Skipped cases and notes from
# the test log are printed, so they stay visible on a green run.
#
#   .github/ci/run-tests.sh BUILD_DIR [extra ctest args]
set -uo pipefail
dir=${1:?usage: run-tests.sh BUILD_DIR [ctest args]}
shift
log=$(mktemp)
ctest --test-dir "$dir" -LE slow --output-on-failure "$@" 2>&1 | tee "$log"
status=${PIPESTATUS[0]}

last="$dir/Testing/Temporary/LastTest.log"
if [ -f "$last" ] && grep -qE '^(SKIP|NOTE) ' "$last"; then
  echo "::group::Skipped cases and notes"
  grep -E '^(SKIP|NOTE) ' "$last"
  echo "::endgroup::"
fi

[ "$status" -eq 0 ] || { echo "::error::ctest failed in $dir"; exit 1; }
need=()
[ "${REQUIRE_BENCH:-1}" = 1 ] && need+=(bench_parity perft_bench_parity)  # 0: the caller runs bench-parity.sh
[ "${REQUIRE_NO_ALLOC:-1}" = 1 ] && need+=(no_alloc)
for t in "${need[@]}"; do
  grep -qE "Test +#[0-9]+: $t \.+ +Passed" "$log" || { echo "::error::$t did not run and pass in $dir"; exit 1; }
done
echo "fast suite ok in $dir (${need[*]:-all} passed)"
