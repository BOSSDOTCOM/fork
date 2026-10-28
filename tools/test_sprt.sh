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
mkdir -p "$repo/tools" "$repo/docs/history/phase-3" "$repo/tests" "$repo/config"
sed "s/^book_sha=.*/book_sha=$book_sha/" "$here/sprt.sh" >"$repo/tools/sprt.sh"
# The tables: the real config's layout, and 145 + 145 empty files.
cp "$here/../config/local-test.json" "$repo/config/"
mkdir -p "$home/fork-tools/syzygy/3-4-5" "$tmp/tb-short"
for i in $(seq 1 145); do : >"$home/fork-tools/syzygy/3-4-5/T$i.rtbw"; : >"$home/fork-tools/syzygy/3-4-5/T$i.rtbz"; done
: >"$tmp/tb-short/KPvK.rtbw"
: >"$repo/docs/history/phase-3/sprt-log.md"
printf 'nodes 100\nsignature 00000000000000aa\n' >"$repo/tests/bench.ref"
# The fake engine names the compiler it was "built" with ($1) and reports a
# bench of 100 nodes (FAKE_NODES at run time changes it).
cat >"$repo/fake-engine.sh" <<'EOF'
#!/usr/bin/env bash
# fake-engine.sh OUT COMPILER: writes the fake engine.
mkdir -p "$(dirname "$1")"
cat >"$1" <<ENG
#!/bin/sh
case \$1 in
  version) echo "Fork 0.0.0-dev"; echo "compiler $2" ;;
  bench) echo "nodes \${FAKE_NODES:-100}"; echo "signature 00000000000000aa"; echo "nps 1000" ;;
esac
ENG
chmod +x "$1"
EOF
cat >"$repo/update.sh" <<'EOF'
#!/usr/bin/env bash
# Fake TCEC build (update.sh's interface: CXX, last line the binary).
set -e
bash fake-engine.sh build/tcec/fork "$("$CXX" --version | head -n 1)"
echo "$(pwd)/build/tcec/fork"
EOF
chmod +x "$repo/update.sh"
# Fake compilers and a fake cmake (for TUNE=1 builds), on PATH.
bin=$tmp/bin
mkdir -p "$bin"
printf '#!/bin/sh\necho "fakecxx version 1.0"\n' >"$bin/fakecxx"
printf '#!/bin/sh\necho "othercxx version 2.0"\n' >"$bin/othercxx"
cat >"$bin/cmake" <<'EOF'
#!/usr/bin/env bash
# Fake cmake: configure records the compiler; --build writes the engine.
if [ "$1" = --build ]; then
  bash "$2/../../fake-engine.sh" "$2/fork" "$("$(cat "$2/cxx")" --version | head -n 1) (tune)"
  exit 0
fi
while [ $# -gt 0 ]; do
  case $1 in
    -B) b=$2; shift ;;
    -DCMAKE_CXX_COMPILER=*) cxx=${1#*=} ;;
  esac
  shift
done
mkdir -p "$b" && echo "${cxx:?no compiler passed}" >"$b/cxx"
EOF
chmod +x "$bin/fakecxx" "$bin/othercxx" "$bin/cmake"
export PATH="$bin:$PATH"
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
  env -u BASE_OPTS -u TEST_OPTS -u TUNE -u SRAND -u TABLES -u SYZYGY_PATH HOME="$home" FORK_SPRT_DIR="$tmp/sprt" FAKE_ARGS="$tmp/args" \
    CXX=fakecxx "$@" bash "$repo/tools/sprt.sh" "$name" HEAD~1 HEAD 0 3 8+0.08 >"$tmp/out" 2>&1
  status=$?
}
logged() { grep -q -- "$1" "$log_md"; }

# U-1: neither BASE_OPTS nor TEST_OPTS set (a plain commit-against-commit
# test) used to die with "unbound variable" after the heading.
run plain
check "plain run exits 0" test "$status" = 0
check "plain run logs its verdict" logged 'Verdict: \*\*H1 was accepted\*\*'
check "plain run logs the report" logged '^Ptnml(0-2): \[0, 0, 0, 1, 0\]'
check "no unbound variable" bash -c "! grep -q 'unbound variable' '$tmp/out'"

# Options under the home folder are logged from ~.
run opts TABLES=0 TEST_OPTS="option.SyzygyPath=$home/tb"
check "home path in options logged as ~" logged 'test opts option.SyzygyPath=~/tb'

# D-2: by default both engines get the 3-4-5 tables from
# config/local-test.json (-each), and the log says so.
run tables
check "tables: exit 0" test "$status" = 0
check "tables: SyzygyPath for both engines" bash -c "grep -A6 -x -- -each '$tmp/args' | grep -qx 'option.SyzygyPath=$home/fork-tools/syzygy/3-4-5'"
check "tables: logged" logged 'Syzygy 3-4-5 for both sides (~/fork-tools/syzygy/3-4-5)'
run notables TABLES=0
check "TABLES=0: no SyzygyPath" bash -c "! grep -q SyzygyPath '$tmp/args'"
check "TABLES=0: logged as no tables" logged ', no tables'
run missing SYZYGY_PATH="$tmp/tb-short"
check "an incomplete set stops the run" test "$status" = 1
check "an incomplete set logs nothing" test ! -s "$log_md"
run twice TEST_OPTS="option.SyzygyPath=$home/tb"
check "SyzygyPath in options with TABLES=1 is refused" test "$status" = 2

# U-10: the builds' identities (version, compiler, bench) are logged; the
# compiler is passed to update.sh and keys the build cache.
run ident
check "both builds' identity logged" logged '^- Builds: base Fork 0.0.0-dev, fakecxx version 1.0, bench 100 00000000000000aa (= bench.ref); test Fork 0.0.0-dev, fakecxx version 1.0, bench 100 00000000000000aa (= bench.ref)'
run other CXX=othercxx
check "another compiler gets its own builds" logged 'base Fork 0.0.0-dev, othercxx version 2.0,'
check "build cache keyed by compiler" test "$(ls -d "$tmp"/sprt/build-* | wc -l)" = 4
run tune TUNE=1
check "TUNE=1 builds get the same compiler" logged 'base Fork 0.0.0-dev, fakecxx version 1.0 (tune), bench'

# U-10: a bench that differs from the commit's tests/bench.ref stops the run
# before any game, and nothing is logged.
run stale FAKE_NODES=101
check "bench mismatch exits 1" test "$status" = 1
check "bench mismatch says so" grep -q "bench '101 00000000000000aa' is not its tests/bench.ref '100 00000000000000aa'" "$tmp/out"
check "bench mismatch logs nothing" test ! -s "$log_md"

# U-10: a fastchess that fails before any game logs nothing and exits 1.
run fatal FAKE_FC=fatal
check "no game: exit 1" test "$status" = 1
check "no game: nothing logged" test ! -s "$log_md"
# A run stopped after some games logs them, says so, and exits 3.
run stopped FAKE_FC=stopped
check "stopped run exits 3" test "$status" = 3
check "stopped run logged as stopped" logged 'INCONCLUSIVE: stopped early after 2 games (fastchess exit status 130)'

# U-16: the opening order's seed is the stamp (or SRAND), passed and logged.
run seeded SRAND=12345
check "SRAND reaches fastchess" bash -c "grep -qx -- -srand '$tmp/args' && grep -A1 -x -- -srand '$tmp/args' | grep -qx 12345"
check "seed logged" logged 'Openings in random order, -srand 12345\.'
run stamped
check "default seed is the stamp" bash -c "grep -A1 -x -- -srand '$tmp/args' | tail -n 1 | grep -qE '^20[0-9]{12}\$'"

echo "${failures} failure(s)"
exit $((failures > 0))
