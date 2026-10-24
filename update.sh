#!/usr/bin/env bash
# Builds the Fork binary for TCEC (or any Linux x86-64 machine) from source.
#
#   ./update.sh                     inside a Fork checkout: builds that tree
#   FORK_REPO=<git url> ./update.sh elsewhere: clones into ./fork, then builds
#
# Prints the path of the finished binary on its last line.
#
# Environment (all optional):
#   CXX         compiler; default: the first found of clang++-19, clang++-16,
#               clang++, g++-12, g++
#   FORK_ARCH   -march target; default x86-64-v3 (AVX2 + BMI2). Never "native":
#               TCEC may build on one server and run on another of a
#               different CPU generation. x86-64-v4 adds AVX-512.
#   FORK_REF    branch, tag or commit to build after cloning (default: the
#               repository's default branch)
#   FORK_JOBS   parallel build jobs (default: nproc)
#
# Needs CMake 3.22+ and either Ninja or make. Builds the engine only: no
# tests, no downloads, Release with debug info (-O3 -g), LTO where the
# toolchain supports it. See DESIGN.md §5.1.
set -euo pipefail

die() { echo "update.sh: $*" >&2; exit 1; }

if [ -f CMakeLists.txt ] && [ -f src/main.cpp ] && grep -q '^project(fork ' CMakeLists.txt; then
  src=$(pwd)
elif [ -n "${FORK_REPO:-}" ]; then
  command -v git >/dev/null || die "git not found"
  if [ -d fork/.git ]; then
    git -C fork fetch --tags origin
  else
    git clone "$FORK_REPO" fork
  fi
  if [ -n "${FORK_REF:-}" ]; then
    git -C fork checkout --detach "$FORK_REF"
  else
    git -C fork merge --ff-only "@{u}" 2>/dev/null || true
  fi
  src=$(cd fork && pwd)
else
  die "run inside a Fork checkout, or set FORK_REPO to clone one"
fi

if [ -z "${CXX:-}" ]; then
  for c in clang++-19 clang++-16 clang++ g++-12 g++; do
    if command -v "$c" >/dev/null; then CXX=$c; break; fi
  done
fi
[ -n "${CXX:-}" ] || die "no C++ compiler found (set CXX)"
command -v cmake >/dev/null || die "cmake not found"

arch=${FORK_ARCH:-x86-64-v3}
[ "$arch" != native ] || die "FORK_ARCH=native is not allowed for TCEC builds"
jobs=${FORK_JOBS:-$(nproc 2>/dev/null || echo 4)}
generator=()
command -v ninja >/dev/null && generator=(-G Ninja)

build="$src/build/tcec"
rm -rf "$build"
cmake -S "$src" -B "$build" "${generator[@]}" \
  -DCMAKE_CXX_COMPILER="$CXX" \
  -DCMAKE_BUILD_TYPE=Release \
  -DFORK_ARCH="$arch" \
  -DFORK_BUILD_TESTS=OFF
cmake --build "$build" --target fork -j "$jobs"

"$build/fork" version
echo "$build/fork"
