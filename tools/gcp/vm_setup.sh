#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Sets up (re-runnable) the Google Cloud CPU worker (docs/gcp-worker.md) and builds one pinned engine there.
# Run on the VM as its worker user (sudo for packages and /opt only), normally through tools/gcp/gcp.sh setup:
#
#   bash vm_setup.sh COMMIT          COMMIT: a full 40-hex commit of the public repository
#
# 1. packages (clang/llvm for the PGO build, cmake, ninja, git, python3-venv, curl, rsync);
# 2. the build target from the CPU's own flags, never native: x86-64-v3 (AVX2, BMI2, FMA required), or
#    x86-64-v4 when AVX-512 F, BW, CD, DQ and VL are all present;
# 3. the repository at COMMIT in $W/src (a clone of the public repo), the default network read from
#    CMakeLists.txt;
# 4. the clang PGO build Fork's data generation uses (cmake/pgo.cmake, as tools/control_center/start_part.sh,
#    with ARCH given), fork and fork_datagen copied to $W/builds/COMMIT12-ARCH/ and checked: `fork version`
#    names the target, the network and the commit; bench equals tests/bench-NET.ref; perftbench equals
#    tests/perft_bench.ref (.github/ci/bench-parity.sh). pins.txt there holds both SHA-256s, which every job
#    checks before it runs;
# 5. a Python venv with python-chess 1.11.2 (verify_games.py) and the Syzygy 3-4-5 tables, every file checked
#    (tools/cloud/fetch_tables.sh).
# Prints "setup ok BUILD_DIR" last; anything else is a failure.
set -euo pipefail
commit=${1:?usage: vm_setup.sh COMMIT}
[[ $commit =~ ^[0-9a-f]{40}$ ]] || { echo "vm_setup.sh: COMMIT must be a full 40-hex commit" >&2; exit 2; }
W=${FORK_WORKER_ROOT:-/opt/fork}
repo_url=${FORK_REPO_URL:-https://github.com/BOSSDOTCOM/fork.git}
say() { echo "$(TZ=EST5 date '+%Y-%m-%d %I:%M:%S %p EST') vm_setup: $*"; }

export DEBIAN_FRONTEND=noninteractive
need=()
for p in clang llvm lld cmake ninja-build git python3 python3-venv curl rsync; do
  dpkg -s "$p" >/dev/null 2>&1 || need+=("$p")
done
if ((${#need[@]})); then
  say "installing ${need[*]}"
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -q >/dev/null
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q "${need[@]}" >/dev/null
fi
sudo mkdir -p "$W"
sudo chown "$(id -u):$(id -g)" "$W"
mkdir -p "$W/builds" "$W/queue" "$W/work" "$W/out" "$W/state"

flags=" $(grep -m1 '^flags' /proc/cpuinfo | cut -d: -f2) "
has() { local f; for f in "$@"; do case $flags in *" $f "*) ;; *) return 1 ;; esac; done; }
has avx2 bmi2 fma || { echo "vm_setup.sh: this CPU lacks AVX2, BMI2 or FMA" >&2; exit 1; }
arch=x86-64-v3
has avx512f avx512bw avx512cd avx512dq avx512vl && arch=x86-64-v4
cpu=$(grep -m1 '^model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ *//')
say "CPU $cpu, $(nproc) vCPU, target $arch"

if [ ! -d "$W/src/.git" ]; then git clone -q "$repo_url" "$W/src"; fi
cd "$W/src"
git fetch -q origin
git checkout -q --detach "$commit"
[ "$(git rev-parse HEAD)" = "$commit" ] || { echo "vm_setup.sh: checkout is not $commit" >&2; exit 1; }
net=$(sed -n 's|^set(FORK_NET "${CMAKE_SOURCE_DIR}/nets/\([A-Za-z0-9_]*\)\.fnet".*|\1|p' CMakeLists.txt)
[ -n "$net" ] || { echo "vm_setup.sh: no default network in CMakeLists.txt" >&2; exit 1; }
out=$W/builds/${commit:0:12}-$arch
if [ -f "$out/pins.txt" ] && (cd "$out" && sha256sum -c --quiet pins.txt); then
  say "build $out exists and matches its pins"
else
  say "PGO build of ${commit:0:12} ($net, $arch)"
  cmake -DSOURCE_DIR="$PWD" -DCXX=clang++ -DCOMPILER_ID=Clang -DARCH="$arch" -P cmake/pgo.cmake >"$W/state/pgo.log" 2>&1 ||
    { tail -20 "$W/state/pgo.log" >&2; exit 1; }
  cmake --build build/clang-pgo --target fork fork_datagen >>"$W/state/pgo.log" 2>&1 ||
    { tail -20 "$W/state/pgo.log" >&2; exit 1; }
  rm -rf "$out"; mkdir -p "$out"
  cp build/clang-pgo/fork build/clang-pgo/fork_datagen "$out/"
  "$out/fork" version >"$out/version.txt"
  grep -qx "arch $arch" "$out/version.txt" || { echo "vm_setup.sh: the build's target is not $arch" >&2; exit 1; }
  grep -qx "net $net" "$out/version.txt" || { echo "vm_setup.sh: the build's network is not $net" >&2; exit 1; }
  grep -E '^Fork ' "$out/version.txt" | grep -q "+${commit:0:7}" || { echo "vm_setup.sh: the build is not from $commit" >&2; exit 1; }
  bash .github/ci/bench-parity.sh "$out/fork" >"$out/bench-parity.txt" || { cat "$out/bench-parity.txt" >&2; exit 1; }
  (cd "$out" && sha256sum fork fork_datagen >pins.txt)
  { echo "commit=$commit"; echo "arch=$arch"; echo "net=$net"; echo "cpu=$cpu"
    echo "compiler=$(clang++ --version | head -1)"
    grep -E '^(nodes|signature) ' <("$out/fork" bench 2>&1) | sed 's/ /=/'; } >"$out/build.env"
fi
cat "$out/bench-parity.txt" "$out/pins.txt"

if [ ! -x "$W/venv/bin/python" ]; then python3 -m venv "$W/venv"; fi
"$W/venv/bin/python" -c 'import chess, sys; sys.exit(chess.__version__ != "1.11.2")' 2>/dev/null ||
  "$W/venv/bin/pip" install -q chess==1.11.2
bash tools/cloud/fetch_tables.sh "$W/syzygy"
say "setup ok $out"
echo "setup ok $out"
