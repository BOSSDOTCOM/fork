#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Builds an A/B experiment variant next to a reference preset, checks bench
# parity and the test suite on the variant, then runs the interleaved
# comparison (bench/ab.py).
#   bench/experiment.sh <clang|gcc> <NAME|NOLTO> [rounds]
# NAME is passed as FORK_EXPERIMENT (FORK_EXP_NAME in the code); NOLTO turns
# off link-time optimization instead.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/env.sh
compiler=$1 name=$2 rounds=${3:-6}
ref=build/$compiler-release
dir=build/ab-$compiler-$name
cxx=$FORK_CLANG_CXX
[ "$compiler" = gcc ] && cxx=$FORK_GCC_CXX
extra=(-DFORK_EXPERIMENT="$name" -DFORK_BUILD_LABEL=)
[ "$name" = NOLTO ] && extra=(-DFORK_LTO=OFF -DFORK_EXPERIMENT= -DFORK_BUILD_LABEL=NOLTO)
# Both binaries come from this tree; ab.py checks they report this commit.
commit=$(git rev-parse HEAD)
git diff --quiet HEAD -- || commit+=-dirty

cmake -S . -B "$dir" -G Ninja -DCMAKE_CXX_COMPILER="$cxx" -DCMAKE_BUILD_TYPE=Release "${extra[@]}" >/dev/null
cmake --build "$dir" >/dev/null
cmake --build "$ref" >/dev/null
ctest --test-dir "$dir" -LE slow -E perft_epd --output-on-failure >/dev/null
echo "variant $name ($compiler): tests and bench parity pass"
python=.venv/Scripts/python.exe
[ -x "$python" ] || python=.venv/bin/python
"$python" -I bench/ab.py "$ref/fork_micro" "$dir/fork_micro" --rounds "$rounds" \
  --a-variant baseline --a-commit "$commit" --b-variant "$name" --b-commit "$commit"
