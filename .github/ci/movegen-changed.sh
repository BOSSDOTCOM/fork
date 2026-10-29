#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# CI: did this push or pull request change a file that move generation's
# results depend on? Decides whether the 2-hour perft_epd_full job runs
# (owner, 2026-10-28: required only when such files change; nightly on main
# otherwise, .github/workflows/nightly.yml). Prints movegen=true|false to
# $GITHUB_OUTPUT.
#
# The files: the core library (board, move generation, perft), the EPD
# suite's test and the test harness, and the build definition (the suite's
# download and registration, the compiler flags). When the changed files
# cannot be listed (a new branch, a rewritten history, a manual run), the
# answer is true.
#
#   EVENT=... BASE_SHA=... BEFORE=... .github/ci/movegen-changed.sh
set -euo pipefail
pattern='^(src/core/|tests/(test_epd\.cpp|harness\.hpp|main\.cpp)$|CMakeLists\.txt$|CMakePresets\.json$|cmake/)'
from=""
case "${EVENT:-}" in
  pull_request) from=${BASE_SHA:-} ;;
  push) from=${BEFORE:-} ;;
esac
answer=true
if [ -n "$from" ] && [ "$from" != 0000000000000000000000000000000000000000 ] &&
  git cat-file -e "$from^{commit}" 2>/dev/null; then
  changed=$(git diff --name-only "$from" HEAD)
  echo "Changed files since ${from:0:12}:"
  echo "$changed" | sed 's/^/  /'
  if grep -Eq "$pattern" <<<"$changed"; then answer=true; else answer=false; fi
else
  echo "Changed files unknown (event ${EVENT:-none}, from '${from}'): running the suite"
fi
echo "movegen=$answer"
echo "movegen=$answer" >> "${GITHUB_OUTPUT:-/dev/null}"
