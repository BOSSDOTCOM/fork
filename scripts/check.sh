#!/usr/bin/env bash
# Fork's single source of truth for "is the tree healthy?", shared by the
# Claude Code hooks (.claude/settings.json) and the git pre-commit hook
# (scripts/hooks/pre-commit).
#
#   scripts/check.sh quick   clang-release build + fast tests (post-edit hook)
#   scripts/check.sh stop    clang-release build + every non-slow test,
#                            including bench parity and no_alloc; this
#                            platform only (Stop hook). Skipped when the code
#                            is unchanged since a passing stop or full run.
#   scripts/check.sh full    clang-release, clang-debug (ASan+UBSan) and
#                            gcc-release: build + every non-slow test,
#                            including bench parity (pre-commit, sign-offs).
#                            On Linux also gcc-debug (GCC ASan+UBSan). On
#                            Windows also a UCI start-up smoke loop (50 runs)
#                            of every MinGW GCC preset's engine, then the
#                            Linux check (below).
#
# Both platforms on every full check: on Windows, `full` copies the working
# tree exactly as it is (tracked and untracked, non-ignored files) into
# ~/fork-check inside WSL (distro FORK_WSL_DISTRO, default Ubuntu; the
# owner's ~/fork copy is never touched) and runs the native Linux check there.
# A Linux failure, or WSL being unavailable, fails the whole check.
# FORK_SKIP_LINUX=1 skips the Linux part with a warning and records no pass.
#
# TCEC toolchain leg (also part of every full check on Windows): the same
# tree is copied into a second WSL distro running Ubuntu 22.04 with TCEC's
# compilers (FORK_TCEC_DISTRO, default Ubuntu-22.04; set up once with
# scripts/tcec-toolchain-setup.sh), built there with update.sh using gcc 11.4,
# g++-12, clang 16 and clang 19 in turn, and each binary's `fork bench` must
# match tests/bench.ref. FORK_SKIP_TCEC=1 skips it with a warning and records
# no pass. Run directly on Linux, `full` cannot reach the TCEC distro and
# records no pass either.
#
# Passing `stop` and `full` runs are remembered by a fingerprint of the
# content of every source, test and build file plus the check scripts
# (tracked and untracked, non-ignored), not of the commit: docs-only commits
# and doc edits never trigger a rerun, and a long background job (MSan,
# perft, fuzzing) is never competed with unless code actually changed.
# Exit status is non-zero on any failure; the failure output goes to stderr.
set -uo pipefail
cd "$(dirname "$0")/.."
. scripts/env.sh

mode=${1:-quick}
code_paths=(src tests bench fuzz tools/magic_seeds.cpp tools/dump_tables.cpp tools/hash_timing.cpp cmake CMakeLists.txt CMakePresets.json
            scripts/check.sh scripts/env.sh scripts/uci-smoke.sh update.sh)
log=$(mktemp)

# One check at a time (owner, 2026-10-26): a check run beside another one
# (the Stop hook during a pre-commit full check, say) competes for CPU and
# memory, and the timing and Hash tests then fail for the wrong reason. The
# lock is a directory holding the owner's PID, cleared when that process is
# gone. `full` waits for it; the hook modes wait within their hooks' time
# limits (stop 10 min, quick 4 min), then skip with a warning and record no
# pass.
lock=build/.check.lock
case "$mode" in
  full) wait_s=-1 ;;
  stop) wait_s=600 ;;
  *) wait_s=240 ;;
esac
mkdir -p build
waited=0
until mkdir "$lock" 2>/dev/null; do
  holder=$(cat "$lock/pid" 2>/dev/null)
  if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
    rm -rf "$lock"  # the holder is gone: a stale lock
    continue
  fi
  if [ "$wait_s" -ge 0 ] && [ "$waited" -ge "$wait_s" ]; then
    echo "fork check $mode: skipped, another check (PID ${holder:-unknown}) still running after ${waited} s; no pass recorded" >&2
    rm -f "$log"
    exit 0
  fi
  sleep 5
  waited=$((waited + 5))
done
echo $$ > "$lock/pid"
trap 'rm -f "$log"; rm -rf "$lock"' EXIT

fail() {
  {
    echo "FORK CHECK FAILED ($mode): $1"
    tail -n 60 "$log"
  } >&2
  exit 1
}

# Content hash of the code: path and blob hash of every existing file under
# code_paths (a deleted file drops out of the list, which changes the hash).
fingerprint() {
  git ls-files -co --exclude-standard -- "${code_paths[@]}" | sort -u |
    while read -r f; do [ -f "$f" ] && echo "$f"; done >"$log.paths"
  git hash-object --stdin-paths <"$log.paths" >"$log.blobs"
  paste "$log.paths" "$log.blobs" | sha1sum | cut -d' ' -f1
  rm -f "$log.paths" "$log.blobs"
}

stamp_matches() {  # fingerprint, stamp files...
  local fp=$1 s
  shift
  for s in "$@"; do
    [ -f "$s" ] && [ "$(cat "$s")" = "$fp" ] && return 0
  done
  return 1
}

# no_alloc (the counting-allocator test, fork_alloc_test) must run and pass in
# every preset checked here; build_and_test fails if its "Passed" line is
# missing, so it can never be skipped silently. Its only sanctioned exclusions
# are TSan, MSan and valgrind runs (Linux sign-off, not part of this script):
# its replacement global operator new/delete collides with those tools' own
# (a link error under TSan/MSan; under valgrind the test's self-check reports
# that the counter is not in effect). ASan/UBSan builds run it. See
# .claude/rules/testing.md.
build_and_test() {  # preset, ctest filter args...
  local preset=$1 out
  shift
  if [ ! -f "build/$preset/build.ninja" ]; then
    cmake --preset "$preset" >>"$log" 2>&1 || fail "configure $preset"
  fi
  cmake --build "build/$preset" >>"$log" 2>&1 || fail "build $preset"
  out=$(ctest --test-dir "build/$preset" --output-on-failure "$@" 2>&1)
  local status=$?
  echo "$out" >>"$log"
  [ $status -eq 0 ] || fail "tests $preset"
  # Skipped cases and notes (retried timing attempts) are not failures, but
  # they stay visible (owner, 2026-10-26): CTest hides a passing test's output.
  local last="build/$preset/Testing/Temporary/LastTest.log"
  if [ -f "$last" ] && grep -qE '^(SKIP|NOTE) ' "$last"; then
    grep -E '^(SKIP|NOTE) ' "$last" | sed "s/^/fork check $mode ($preset): /" >&2
  fi
  echo "$out" | grep -qE 'Test +#[0-9]+: no_alloc \.+ +Passed' || fail "no_alloc did not run in $preset"
}

native_full() {
  local presets=(clang-release clang-debug gcc-release)
  [ "$(uname -s)" = Linux ] && presets+=(gcc-debug)
  for preset in "${presets[@]}"; do
    build_and_test "$preset" -LE slow
  done
  [ "$(uname -s)" = Linux ] || windows_gcc_smoke
  echo "${presets[*]}"
}

# Windows only (owner, 2026-10-24): every MinGW GCC preset's engine must
# start cleanly in UCI mode, 50 times (scripts/uci-smoke.sh). Builds only the
# fork target of each; the full gcc-debug suite runs at each phase end.
windows_gcc_smoke() {
  local preset
  for preset in gcc-debug gcc-release gcc-v3 gcc-avx512 gcc-nopext; do
    if [ ! -f "build/$preset/build.ninja" ]; then
      cmake --preset "$preset" >>"$log" 2>&1 || fail "configure $preset"
    fi
    cmake --build "build/$preset" --target fork >>"$log" 2>&1 || fail "build $preset (fork)"
    scripts/uci-smoke.sh "build/$preset/fork.exe" 50 >>"$log" 2>&1 || fail "UCI start-up smoke loop, $preset"
  done
}

# Windows side: copy the working tree into WSL and run the Linux check there.
linux_leg() {
  local distro=${FORK_WSL_DISTRO:-Ubuntu} list=build/.linux-check-files src
  command -v wsl.exe >/dev/null || fail "wsl.exe not found (set FORK_SKIP_LINUX=1 to skip the Linux check)"
  git ls-files -co --exclude-standard >"$list" || fail "listing the working tree for Linux"
  src=$(MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -e wslpath -a "$(pwd -W)" 2>>"$log" | tr -d '\r') ||
    fail "WSL distro $distro unavailable (set FORK_SKIP_LINUX=1 to skip the Linux check)"
  [ -n "$src" ] || fail "WSL distro $distro unavailable (set FORK_SKIP_LINUX=1 to skip the Linux check)"
  MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -e bash "$src/scripts/check.sh" linux-sync "$src" >>"$log" 2>&1 ||
    fail "Linux check in WSL ($distro, ~/fork-check)"
}

# Windows side: copy the working tree into the Ubuntu 22.04 distro and build
# it there with TCEC's compilers.
tcec_leg() {
  local distro=${FORK_TCEC_DISTRO:-Ubuntu-22.04} list=build/.linux-check-files src
  git ls-files -co --exclude-standard >"$list" || fail "listing the working tree for the TCEC build"
  src=$(MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -u root -e wslpath -a "$(pwd -W)" 2>>"$log" | tr -d '\r') ||
    fail "WSL distro $distro unavailable (see scripts/tcec-toolchain-setup.sh; FORK_SKIP_TCEC=1 to skip)"
  [ -n "$src" ] || fail "WSL distro $distro unavailable (see scripts/tcec-toolchain-setup.sh; FORK_SKIP_TCEC=1 to skip)"
  MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -u root -e bash "$src/scripts/check.sh" tcec-sync "$src" >>"$log" 2>&1 ||
    fail "TCEC toolchain build in WSL ($distro, ~/fork-tcec)"
}

case "$mode" in
  tcec-sync)  # internal, run inside the Ubuntu 22.04 distro by tcec_leg: $2 = Windows tree as a /mnt path
    src=$2 dst=$HOME/fork-tcec
    rm -rf "$dst" && mkdir -p "$dst"
    (cd "$src" && tar -cf - -T build/.linux-check-files) | (cd "$dst" && tar -xf -) ||
      { echo "copying the tree to $dst failed" >&2; exit 1; }
    cd "$dst"
    # compiler, and the version its `fork version` line must report
    for pair in "g++:gcc 11.4." "g++-12:gcc 12." "clang++-16:clang 16." "clang++-19:clang 19."; do
      cxx=${pair%%:*} want=${pair#*:}
      echo "== TCEC build with $cxx"
      out=$(CXX=$cxx bash ./update.sh 2>&1) || { echo "$out"; echo "update.sh failed with $cxx" >&2; exit 1; }
      bin=$(echo "$out" | tail -n 1)
      echo "$out" | grep -q "^compiler $want" ||
        { echo "$out"; echo "$cxx is not the expected $want" >&2; exit 1; }
      echo "$out" | grep -q -i 'LTO not supported' && echo "note: $cxx built without LTO"
      "$bin" bench | head -n 2 >bench.out
      diff bench.out tests/bench.ref || { echo "bench parity failed with $cxx" >&2; exit 1; }
      echo "bench parity ok with $cxx"
    done
    ;;
  linux-sync)  # internal, run inside WSL by linux_leg: $2 = Windows tree as a /mnt path
    src=$2 dst=$HOME/fork-check
    mkdir -p "$dst"
    # Fresh source tree each time, so deleted files disappear; build/ and the
    # downloaded test data in .cache/ persist, and tar keeps the mtimes, so
    # only changed files recompile.
    find "$dst" -mindepth 1 -maxdepth 1 ! -name build ! -name .cache -exec rm -rf {} +
    (cd "$src" && tar -cf - -T build/.linux-check-files) | (cd "$dst" && tar -xf -) ||
      { echo "copying the tree to $dst failed" >&2; exit 1; }
    exec bash "$dst/scripts/check.sh" full-native
    ;;
  full-native)  # internal: this platform's presets only, no stamp
    presets=$(native_full) || exit 1
    echo "fork check full-native ($(uname -s)): ok ($presets)"
    ;;
  quick)
    build_and_test clang-release -R '^(magics|fen|zobrist_ep|perft_edge|pseudo_legal|no_alloc|bench_parity)$'
    echo "fork check quick: ok"
    ;;
  stop)
    mkdir -p build
    fp=$(fingerprint)
    if stamp_matches "$fp" build/.check-stop-pass build/.check-full-pass; then
      echo "fork check stop: skipped (code unchanged since last pass)"
      exit 0
    fi
    build_and_test clang-release -LE slow
    echo "$fp" >build/.check-stop-pass
    echo "fork check stop: ok (clang-release, all non-slow tests, bench parity, no_alloc)"
    ;;
  full)
    mkdir -p build
    stamp=build/.check-full-pass
    fp=$(fingerprint)
    if stamp_matches "$fp" "$stamp"; then
      echo "fork check full: ok (unchanged since last pass)"
      exit 0
    fi
    presets=$(native_full) || exit 1
    platforms="$(uname -s): $presets"
    [ "$(uname -s)" = Linux ] || platforms="$platforms, UCI smoke x50 for gcc-{debug,release,v3,avx512,nopext}"
    if [ "$(uname -s)" != Linux ]; then
      if [ "${FORK_SKIP_LINUX:-0}" = 1 ]; then
        echo "fork check full: WARNING: Linux check SKIPPED (FORK_SKIP_LINUX=1); no pass recorded" >&2
        echo "fork check full: ok on $platforms only; Linux SKIPPED"
        exit 0
      fi
      linux_leg
      platforms="$platforms; Linux (WSL): clang-release clang-debug gcc-release gcc-debug"
      if [ "${FORK_SKIP_TCEC:-0}" = 1 ]; then
        echo "fork check full: WARNING: TCEC toolchain build SKIPPED (FORK_SKIP_TCEC=1); no pass recorded" >&2
        echo "fork check full: ok on $platforms; TCEC toolchain SKIPPED"
        exit 0
      fi
      tcec_leg
      platforms="$platforms; TCEC toolchain (Ubuntu 22.04): gcc 11.4, g++-12, clang 16, clang 19"
    else
      echo "fork check full: WARNING: TCEC toolchain build runs from Windows only; no pass recorded" >&2
      echo "fork check full: ok on $platforms; TCEC toolchain not run"
      exit 0
    fi
    echo "$fp" >"$stamp"
    echo "fork check full: ok ($platforms; bench parity included)"
    ;;
  *)
    echo "usage: scripts/check.sh quick|stop|full" >&2
    exit 2
    ;;
esac
