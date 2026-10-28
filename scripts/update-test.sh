#!/usr/bin/env bash
# Tests update.sh's clone mode (FORK_REPO) against a toy upstream, without
# building: FORK_CHECKOUT_ONLY stops it after the checkout. Each run must
# check out the upstream's current commit: after a fast-forward, after a
# rewritten history (a force push), for a branch, a tag and a commit given in
# FORK_REF; an unknown FORK_REF must fail. (audit-1, T-1: a rewritten history
# left the old commit checked out, built with exit status 0.)
#
#   scripts/update-test.sh [path/to/update.sh]
set -uo pipefail

script=${1:-$(dirname "$0")/../update.sh}
script=$(cd "$(dirname "$script")" && pwd)/$(basename "$script")
[ -f "$script" ] || { echo "update-test: no update.sh at $script" >&2; exit 2; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0
g() { git -c core.autocrlf=false -c user.name=test -c user.email=test@example.invalid -c init.defaultBranch=main "$@"; }

g init -q --bare "$tmp/up.git"
g clone -q "$tmp/up.git" "$tmp/dev" 2>/dev/null
commit() { echo "$1" > "$tmp/dev/file" && g -C "$tmp/dev" add file && g -C "$tmp/dev" commit -q -m "$1"; }
commit one
g -C "$tmp/dev" push -q origin main
g -C "$tmp/dev" branch other && g -C "$tmp/dev" push -q origin other
mkdir "$tmp/run"

# check <label> <expected commit> [FORK_REF]: one update.sh run in $tmp/run.
check() {
  local label=$1 want=$2 got
  (cd "$tmp/run" && FORK_REPO="$tmp/up.git" FORK_REF="${3:-}" FORK_CHECKOUT_ONLY=1 bash "$script" >/dev/null 2>&1)
  local rc=$?
  got=$(git -C "$tmp/run/fork" rev-parse HEAD 2>/dev/null)
  if [ $rc -eq 0 ] && [ "$got" = "$want" ]; then
    echo "ok   $label"
  else
    echo "FAIL $label: exit $rc, checked out ${got:-nothing}, expected $want"
    failures=$((failures + 1))
  fi
}
tip() { git -C "$tmp/up.git" rev-parse "$1"; }

check "first clone: the default branch" "$(tip main)"
commit two && g -C "$tmp/dev" push -q origin main
check "after a fast-forward" "$(tip main)"
g -C "$tmp/dev" commit -q --amend -m "two, rewritten" && g -C "$tmp/dev" push -q --force origin main
check "after a rewritten history" "$(tip main)"
g -C "$tmp/dev" checkout -q other && commit three && g -C "$tmp/dev" push -q origin other
check "FORK_REF names a branch: origin's, not a stale local one" "$(tip other)" other
commit four && g -C "$tmp/dev" push -q origin other
check "the branch again, after it moved" "$(tip other)" other
g -C "$tmp/dev" tag t1 && g -C "$tmp/dev" push -q origin t1
check "FORK_REF names a tag" "$(tip t1)" t1
check "FORK_REF names a commit" "$(tip main)" "$(tip main)"
(cd "$tmp/run" && FORK_REPO="$tmp/up.git" FORK_REF=no-such-ref FORK_CHECKOUT_ONLY=1 bash "$script" >/dev/null 2>&1)
if [ $? -ne 0 ]; then echo "ok   an unknown FORK_REF fails"; else echo "FAIL an unknown FORK_REF exits 0"; failures=$((failures + 1)); fi

[ $failures -eq 0 ] && echo "update-test: all passed" || echo "update-test: $failures failed"
exit $((failures > 0))
