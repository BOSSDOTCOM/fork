#!/usr/bin/env bash
# MemorySanitizer build of Fork against an MSan-instrumented libc++ (Linux
# only). MSan needs every part of the program instrumented, the C++ standard
# library included; against the distro's uninstrumented libstdc++ it reports
# false positives inside the library (2026-10-23: std::getline on an
# ifstream, number formatting in operator<<). Only this build uses libc++;
# every other build keeps libstdc++.
#
#   scripts/msan.sh libcxx          build and install the instrumented libc++
#   scripts/msan.sh selftest        prove MSan reports through this libc++
#   scripts/msan.sh build           configure and build build/clang-msan-libcxx
#   scripts/msan.sh test [ARGS...]  ctest in that build (ARGS go to ctest)
#
# libc++ and libc++abi come from llvm-project at the tag matching the system
# clang (FORK_LLVM_TAG, default llvmorg-21.1.8; check `clang++ --version`),
# with LLVM_USE_SANITIZER=MemoryWithOrigins so reports can be diagnosed with
# origins; Fork itself is built without origin tracking unless
# FORK_MSAN_ORIGINS=1. Install prefix: ~/fork-tools/libcxx-msan-<tag>.
# libunwind is NOT built: with an MSan-instrumented libunwind linked in,
# every MSan report crashed with a stack overflow in the reporter (found by
# the selftest, 2026-10-23), so libc++abi uses the system unwinder.
# no_alloc, uci_oom and uci_hash_oom are excluded: their replacement operator new/delete collides with the
# MSan runtime (.claude/rules/testing.md).
set -euo pipefail
cd "$(dirname "$0")/.."
[ "$(uname -s)" = Linux ] || { echo "scripts/msan.sh: Linux only" >&2; exit 2; }

tag=${FORK_LLVM_TAG:-llvmorg-21.1.8}
tools=$HOME/fork-tools
src=$tools/src/llvm-project-${tag#llvmorg-}
prefix=$tools/libcxx-msan-${tag#llvmorg-}
dir=build/clang-msan-libcxx
cc=${FORK_MSAN_CC:-clang}
cxx=${FORK_MSAN_CXX:-clang++}

case "${1:-}" in
  libcxx)
    if [ ! -d "$src/.git" ]; then
      git clone -q --depth 1 --branch "$tag" --filter=blob:none --sparse \
        https://github.com/llvm/llvm-project.git "$src"
    fi
    # libc: libc++'s charconv includes LLVM libc's shared/fp_bits.h.
    git -C "$src" sparse-checkout set runtimes libcxx libcxxabi libunwind libc cmake llvm/cmake \
      llvm/utils/llvm-lit third-party/benchmark
    echo "llvm-project $(git -C "$src" describe --tags) $(git -C "$src" rev-parse HEAD)"
    rm -rf "$src/build-msan" "$prefix"
    cmake -S "$src/runtimes" -B "$src/build-msan" -G Ninja \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER="$cc" -DCMAKE_CXX_COMPILER="$cxx" \
      -DLLVM_ENABLE_RUNTIMES="libcxx;libcxxabi" -DLIBCXXABI_USE_LLVM_UNWINDER=OFF \
      -DLLVM_USE_SANITIZER=MemoryWithOrigins \
      -DLIBCXX_INCLUDE_TESTS=OFF -DLIBCXXABI_INCLUDE_TESTS=OFF -DLIBCXX_INCLUDE_BENCHMARKS=OFF \
      -DCMAKE_INSTALL_PREFIX="$prefix"
    cmake --build "$src/build-msan"
    cmake --install "$src/build-msan"
    echo "installed $prefix"
    ;;
  selftest)
    # An uninitialized read through libc++ must give a clean MSan report
    # naming the line; a pass here means a clean test run means something.
    d=$(mktemp -d)
    printf '%s\n' '#include <iostream>' '#include <vector>' 'int main() {' \
      '  std::vector<int> v;' '  v.reserve(4);' \
      '  if (v.data()[0] == 42) std::cout << "yes\n";  // never written: uninitialized' \
      '  std::cout << "done\n";' '}' >"$d/probe.cpp"
    "$cxx" -fsanitize=memory -g -fno-omit-frame-pointer -nostdinc++ -isystem "$prefix/include/c++/v1" \
      -stdlib=libc++ -L"$prefix/lib" -Wl,-rpath,"$prefix/lib" "$d/probe.cpp" -o "$d/probe"
    out=$("$d/probe" 2>&1 || true)
    rm -rf "$d"
    if grep -q "WARNING: MemorySanitizer: use-of-uninitialized-value" <<<"$out" &&
       grep -q "probe.cpp:6" <<<"$out"; then
      echo "msan selftest: ok (uninitialized read reported at probe.cpp:6)"
    else
      echo "msan selftest: FAILED, MSan did not report the uninitialized read cleanly:" >&2
      head -8 <<<"$out" >&2
      exit 1
    fi
    ;;
  build)
    [ -d "$prefix/include/c++/v1" ] || { echo "no instrumented libc++ at $prefix: run scripts/msan.sh libcxx" >&2; exit 1; }
    origins=""
    [ "${FORK_MSAN_ORIGINS:-0}" = 1 ] && origins="-fsanitize-memory-track-origins=2"
    cmake -S . -B "$dir" -G Ninja -DCMAKE_CXX_COMPILER="$cxx" -DCMAKE_BUILD_TYPE=Release -DFORK_LTO=OFF \
      -DCMAKE_CXX_FLAGS="-fsanitize=memory $origins -g -fno-omit-frame-pointer -nostdinc++ -isystem $prefix/include/c++/v1" \
      -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=memory -stdlib=libc++ -L$prefix/lib -Wl,-rpath,$prefix/lib"
    cmake --build "$dir" --target fork fork_tests
    ;;
  test)
    shift
    ctest --test-dir "$dir" -E "^(no_alloc|uci_oom|uci_hash_oom)$" --output-on-failure "$@"
    ;;
  *)
    echo "usage: scripts/msan.sh libcxx|selftest|build|test [ctest args]" >&2
    exit 2
    ;;
esac
