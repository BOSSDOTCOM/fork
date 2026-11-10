#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Dry-run test of tools/elo_gauntlet.sh (audit-1 U-18: it printed ratings
# after a failed fastchess run; docs/history/phase-3/audit-1-findings.md §1).
# A fake home holds the anchor binaries, a fake fastchess that writes a PGN
# of FAKE_GAMES games and exits FAKE_FC_STATUS, and a fake ordo that writes
# a ratings table (or fails with FAKE_ORDO=fail). Nothing is played; no
# Python. Runs in Git Bash or Linux in a second or two.
#
#   bash tools/test_elo_gauntlet.sh [path to elo_gauntlet.sh]
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
script=${1:-$here/elo_gauntlet.sh}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0
check() {  # description, command...
  local what=$1
  shift
  if "$@"; then echo "PASS  $what"; else echo "FAIL  $what"; failures=$((failures + 1)); fi
}

home=$tmp/home
mkdir -p "$home/fork-tools/bin" "$home/fork-tools/engines"
# The default anchor set (ANCHORS=a): five engines, any executable will do.
for f in shallowblue-2.0.0 stash-12.0 stash-15.3 stash-19.0 weiss-1.0; do
  printf '#!/bin/sh\nexit 0\n' >"$home/fork-tools/engines/$f"
  chmod +x "$home/fork-tools/engines/$f"
done
cat >"$home/fork-tools/bin/fastchess" <<'EOF'
#!/usr/bin/env bash
# Fake fastchess: FAKE_GAMES games into the -pgnout file, then FAKE_FC_STATUS.
pgn=
while [ $# -gt 0 ]; do
  [ "$1" = -pgnout ] && { pgn=${2#file=}; shift; }
  shift
done
for i in $(seq 1 "${FAKE_GAMES:-0}"); do
  printf '[Event "Fake %s"]\n[Result "1/2-1/2"]\n\n1/2-1/2\n\n' "$i" >>"$pgn"
done
echo "Finished match"
exit "${FAKE_FC_STATUS:-0}"
EOF
cat >"$home/fork-tools/bin/ordo" <<'EOF'
#!/usr/bin/env bash
# Fake ordo: a ratings table into the -o file, or a failure (FAKE_ORDO=fail).
[ "${FAKE_ORDO:-ok}" = fail ] && { echo "ordo: bad input"; exit 1; }
while [ $# -gt 0 ]; do
  [ "$1" = -o ] && { printf '   # PLAYER : RATING\n   1 Fork   : FAKE-RATING-1234\n' >"$2"; shift; }
  shift
done
EOF
chmod +x "$home/fork-tools/bin/fastchess" "$home/fork-tools/bin/ordo"
printf '#!/bin/sh\nexit 0\n' >"$tmp/fork"
chmod +x "$tmp/fork"
echo 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -' >"$tmp/book.epd"

# 4 games per anchor, five anchors: 20 planned.
run() {  # name, VAR=value...: runs the gauntlet in its own output directory
  local name=$1
  shift
  rm -rf "$tmp/out-$name"
  env HOME="$home" "$@" bash "$script" "$tmp/fork" "$tmp/book.epd" "$tmp/out-$name" 4 \
    >"$tmp/stdout-$name" 2>"$tmp/stderr-$name"
  status=$?
}
rated() { grep -q FAKE-RATING "$tmp/stdout-$1"; }

run failed FAKE_GAMES=3 FAKE_FC_STATUS=1
check "failed fastchess run exits non-zero" test "$status" != 0
check "failed fastchess run prints no ratings" bash -c "! grep -q FAKE-RATING '$tmp/stdout-failed'"
check "failed fastchess run keeps the partial PGN" test -s "$tmp/out-failed/gauntlet.pgn"
run short FAKE_GAMES=19 FAKE_FC_STATUS=0
check "short run (19 of 20 games) exits non-zero" test "$status" != 0
check "short run prints no ratings" bash -c "! grep -q FAKE-RATING '$tmp/stdout-short'"
run nopgn FAKE_GAMES=0 FAKE_FC_STATUS=1
check "fastchess failing before any game exits non-zero" test "$status" != 0
check "fastchess failing before any game prints no ratings" bash -c "! grep -q FAKE-RATING '$tmp/stdout-nopgn'"
run ordofail FAKE_GAMES=20 FAKE_ORDO=fail
check "ordo failure exits non-zero" test "$status" != 0
check "ordo failure prints no ratings" bash -c "! grep -q FAKE-RATING '$tmp/stdout-ordofail'"
run complete FAKE_GAMES=20 FAKE_FC_STATUS=0
check "complete run exits 0" test "$status" = 0
check "complete run prints the ratings" rated complete

echo "${failures} failure(s)"
exit $((failures > 0))
