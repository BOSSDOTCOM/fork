#!/usr/bin/env bash
# Bake-off round 3 option (a): build and test fork-train with a throwaway
# CARGO_HOME inside this scratch folder (WSL).
#   run-cargo.sh test            cargo test (all tests)
#   run-cargo.sh build           cargo build --release (CPU; no cuda)
set -u
WIN_HOME=${WIN_HOME:?set WIN_HOME to the Windows home folder as WSL sees it, /mnt/c/Users/<user>}  # archive: was a literal path
S=$WIN_HOME/fork-runners/scratch-r3kr4
export RUSTUP_HOME=$HOME/fork-tools/rust/rustup
export CARGO_HOME=$S/cargo-home
export CARGO_TARGET_DIR=$S/target
export CARGO_BUILD_JOBS=3
export PATH=$HOME/fork-tools/rust/cargo/bin:$PATH
cd "$S/wt/tools/train" || exit 1
case "$1" in
  test)
    nice cargo test --locked -j 3 2>&1
    ;;
  build)
    nice cargo build --release --locked -j 3 2>&1 | tail -5
    ;;
esac
