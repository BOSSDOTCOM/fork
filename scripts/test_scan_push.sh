#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Tests the push gate (scripts/scan-push.sh and scripts/hooks/pre-push) in a
# throwaway repository with a local bare remote: a clean commit pushes; a
# planted hit of each kind (a home path with this machine's user name, a
# credential's shape, a private pattern) blocks both the scan and the push,
# and a private pattern's match is never printed. Every planted value is
# built at run time, so this file holds none of them.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }

git init -q --bare "$tmp/remote.git"
git init -q "$tmp/work"
cd "$tmp/work" || exit 1
git config user.name test
git config user.email test@example.invalid
git config core.autocrlf false
git config core.hooksPath "$tmp/work/scripts/hooks"
mkdir -p scripts/hooks
cp "$here/scan-push.sh" scripts/
cp "$here/hooks/pre-push" scripts/hooks/
git remote add origin "$tmp/remote.git"
printf 'nothing personal here\n' >clean.txt
git add -A && git commit -q -m clean
base=$(git rev-parse HEAD)
export FORK_SCAN_PATTERNS="$tmp/patterns"
private_value="planted-$(date +%s)-value"
printf '# test patterns\n%s\n' "$private_value" >"$FORK_SCAN_PATTERNS"
check "a clean commit scans clean" "bash scripts/scan-push.sh HEAD >/dev/null 2>&1"
check "a clean commit pushes" "git push -q origin HEAD:refs/heads/main >/dev/null 2>&1"

user=${USERNAME:-${USER:-$(id -un)}}
plant() {  # name, file content
  git checkout -q -B "plant-$1" "$base"
  printf '%s\n' "$2" >"planted-$1.txt"
  git add -A && git commit -q -m "plant $1"
  bash scripts/scan-push.sh HEAD >"$tmp/scan-$1.log" 2>&1
  echo $? >"$tmp/scan-$1.rc"
  git push -q origin "HEAD:refs/heads/plant-$1" >"$tmp/push-$1.log" 2>&1
  echo $? >"$tmp/push-$1.rc"
}
plant home "a log line: C:\\Users\\$user\\fork\\build"
plant secret "key = AK""IA$(printf 'Q%.0s' {1..16})"
plant private "note: $private_value"
for kind in home secret private; do
  check "a planted $kind hit fails the scan" "[ \$(cat $tmp/scan-$kind.rc) = 1 ]"
  check "a planted $kind hit blocks the push" "[ \$(cat $tmp/push-$kind.rc) != 0 ]"
  check "the remote has no plant-$kind branch" "! git ls-remote --exit-code origin plant-$kind >/dev/null 2>&1"
done
check "the private pattern's match is not printed" "! grep -q -- '$private_value' $tmp/scan-private.log $tmp/push-private.log"
check "the scan names the file" "grep -q 'planted-home.txt' $tmp/scan-home.log"

echo "scan-push tests: $fails failure(s)"
[ "$fails" = 0 ]
