#!/usr/bin/env bash
# Dry-run test of tools/sprt.sh: nothing is compiled and no game is played.
# A throwaway repository holds a copy of sprt.sh, a fake update.sh that
# "builds" a shell-script engine, and two commits; a fake fastchess prints
# a canned match (or fails) and records its arguments. The only change to
# the copied sprt.sh is the book's pinned SHA-256 (the fake book is one
# line). Runs in Git Bash or Linux in a few seconds.
#
#   bash tools/test_sprt.sh
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0
check() {  # description, command...
  local what=$1
  shift
  if "$@"; then echo "PASS  $what"; else echo "FAIL  $what"; failures=$((failures + 1)); fi
}

# The fake home: fastchess and the book where sprt.sh looks for them.
home=$tmp/home
mkdir -p "$home/fork-tools/bin" "$home/fork-tools/books"
echo 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -' >"$home/fork-tools/books/UHO_Lichess_4852_v1.epd"
book_sha=$(sha256sum "$home/fork-tools/books/UHO_Lichess_4852_v1.epd" | cut -d' ' -f1)
cat >"$home/fork-tools/bin/fastchess" <<'EOF'
#!/usr/bin/env bash
# Fake fastchess: FAKE_FC=ok (a decided SPRT), fatal (refuses at once) or
# stopped (two games, then killed). Its arguments go to $FAKE_ARGS.
printf '%s\n' "$@" >"$FAKE_ARGS"
case ${FAKE_FC:-ok} in
  fatal) echo "Fatal; unknown engine option"; exit 1 ;;
  stopped)
    echo "Finished game 1 (test vs base): 1-0 {White wins by adjudication}"
    echo "Finished game 2 (base vs test): 1/2-1/2 {Draw by 3-fold repetition}"
    exit 130 ;;
esac
echo "Finished game 1 (test vs base): 1-0 {White wins by adjudication}"
echo "Finished game 2 (base vs test): 1/2-1/2 {Draw by 3-fold repetition}"
echo "--------------------------------------------------"
echo "Results of test vs base (8+0.08, 1t, 16MB, UHO_Lichess_4852_v1.epd):"
echo "Elo: 191.31 +/- 0.00, nElo: 0.00 +/- 0.00"
echo "Games: 2, Wins: 1, Losses: 0, Draws: 1, Points: 1.5 (75.00 %)"
echo "Ptnml(0-2): [0, 0, 0, 1, 0], WL/DD Ratio: 0.00"
echo "LLR: 2.95 (100.0%) (-2.94, 2.94) [0.00, 3.00]"
echo "--------------------------------------------------"
echo "SPRT ([0.00, 3.00]) completed - H1 was accepted"
echo "Finished match"
EOF
chmod +x "$home/fork-tools/bin/fastchess"

# The throwaway repository: two commits, each with a fake update.sh.
repo=$tmp/repo
mkdir -p "$repo/tools" "$repo/docs/history/phase-3" "$repo/tests"
sed "s/^book_sha=.*/book_sha=$book_sha/" "$here/sprt.sh" >"$repo/tools/sprt.sh"
: >"$repo/docs/history/phase-3/sprt-log.md"
printf 'nodes 100\nsignature 00000000000000aa\n' >"$repo/tests/bench.ref"
cat >"$repo/update.sh" <<'EOF'
#!/usr/bin/env bash
# Fake TCEC build: the "engine" answers version and bench.
set -e
mkdir -p build/tcec
cat >build/tcec/fork <<'ENG'
#!/bin/sh
case $1 in
  version) echo "Fork 0.0.0-dev"; echo "compiler fake 1.0" ;;
  bench) echo "nodes 100"; echo "signature 00000000000000aa"; echo "nps 1000" ;;
esac
ENG
chmod +x build/tcec/fork
echo "compiler fake 1.0"
echo "$(pwd)/build/tcec/fork"
EOF
chmod +x "$repo/update.sh"
git -C "$repo" init -q .
git -C "$repo" config user.email test@example.invalid
git -C "$repo" config user.name test
git -C "$repo" config core.autocrlf false
git -C "$repo" add -A
git -C "$repo" update-index --chmod=+x update.sh tools/sprt.sh
git -C "$repo" commit -qm base
echo change >"$repo/marker"
git -C "$repo" add marker && git -C "$repo" commit -qm test
log_md=$repo/docs/history/phase-3/sprt-log.md

run() {  # name, env assignments... ; runs sprt.sh, output in $tmp/out, status in $status
  local name=$1
  shift
  : >"$log_md"
  env -u BASE_OPTS -u TEST_OPTS HOME="$home" FORK_SPRT_DIR="$tmp/sprt" FAKE_ARGS="$tmp/args" "$@" \
    bash "$repo/tools/sprt.sh" "$name" HEAD~1 HEAD 0 3 8+0.08 >"$tmp/out" 2>&1
  status=$?
}

# U-1: neither BASE_OPTS nor TEST_OPTS set (a plain commit-against-commit
# test) used to die with "unbound variable" after the heading.
run plain
check "plain run exits 0" test "$status" = 0
check "plain run logs its verdict" grep -q 'Verdict: \*\*H1 was accepted\*\*' "$log_md"
check "plain run logs the report" grep -q '^Ptnml(0-2): \[0, 0, 0, 1, 0\]' "$log_md"
check "no unbound variable" bash -c "! grep -q 'unbound variable' '$tmp/out'"

# Options under the home folder are logged from ~.
run opts TEST_OPTS="option.SyzygyPath=$home/tb"
check "home path in options logged as ~" grep -q 'test opts option.SyzygyPath=~/tb' "$log_md"

echo "${failures} failure(s)"
exit $((failures > 0))
