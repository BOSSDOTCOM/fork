#!/usr/bin/env bash
# CI: one slow perft suite on a clang-release build, then bench parity
# (ci.yml's slow jobs and nightly.yml).
#
#   .github/ci/slow-suite.sh SUITE        e.g. perft_epd_full
set -euo pipefail
suite=${1:?usage: slow-suite.sh SUITE}
sudo apt-get update -q
sudo apt-get install -y -q ninja-build
nproc
grep -m1 'model name' /proc/cpuinfo
cmake --preset clang-release
cmake --build build/clang-release --target fork fork_tests
ctest --test-dir build/clang-release -R "^${suite}\$" --timeout 16000 --no-tests=error --output-on-failure
bash .github/ci/bench-parity.sh build/clang-release/fork
