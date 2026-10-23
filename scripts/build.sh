#!/usr/bin/env bash
# Configure, build and test presets; prints a summary table.
#   scripts/build.sh                 all presets, then PGO for both compilers
#   scripts/build.sh clang-debug ... chosen presets (clang-pgo / gcc-pgo run PGO)
#   FORK_SLOW=1 adds the slow-labelled tests (full-depth perft in debug builds)
set -u
cd "$(dirname "$0")/.."
. scripts/env.sh

all="clang-debug clang-release clang-v3 clang-avx512 clang-nopext
     gcc-debug gcc-release gcc-v3 gcc-avx512 gcc-nopext clang-pgo gcc-pgo"
presets="${*:-$all}"
ctest_args="--output-on-failure"
[ "${FORK_SLOW:-0}" = 1 ] || ctest_args="$ctest_args -LE slow"

summary=""
fail=0
for p in $presets; do
  echo "=== $p"
  case "$p" in
    clang-pgo|gcc-pgo)
      cxx=$FORK_CLANG_CXX; id=Clang
      [ "$p" = gcc-pgo ] && { cxx=$FORK_GCC_CXX; id=GNU; }
      cmake -DSOURCE_DIR="$PWD" -DCXX="$cxx" -DCOMPILER_ID=$id -P cmake/pgo.cmake
      ;;
    *)
      cmake --preset "$p" >/dev/null && cmake --build "build/$p" &&
        ctest --test-dir "build/$p" $ctest_args
      ;;
  esac
  if [ $? -eq 0 ]; then r=PASS; else r=FAIL; fail=1; fi
  summary="$summary$(printf '%-14s %s' "$p" "$r")\n"
done
printf "\n%b" "$summary"
exit $fail
