#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Dry runs of tools/github/h2h_run.sh (head-to-head selection of a constant's value; owner, DESIGN.md §6
# 2026-11-07 decision 3) against the fake gh (tools/github/fake_gh.sh), its pairings played by
# sprt_run.sh --kind fixed: two values play one pairing, three and four a round robin, every pairing on the same
# stages (so the same openings); the stronger value is picked with its delta +/- e and a constants-table
# row; an edge within the declared tie margin (0.5 e) keeps the preferred value; a rerun skips finished
# pairings; a changed declaration, a failed run and bad arguments stop it before a pick. Uses python3 (or
# $PYTHON).
#
#   bash tools/github/test_h2h_run.sh
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
export PYTHON=${PYTHON:-python3}
c20=$(git -C "$here" rev-parse HEAD~3)
c40=$(git -C "$here" rev-parse HEAD~2)
c60=$(git -C "$here" rev-parse HEAD~1)
c80=$(git -C "$here" rev-parse HEAD)
cp "$here/fake_gh.sh" "$tmp/gh"
chmod +x "$tmp/gh"

better='[2, 6, 20, 14, 8]'   # per shard: the test side clearly stronger (+96.36 +/- 34.05 over 2 stages)
worse='[8, 14, 20, 6, 2]'    # the same, from the other side
edge='[4, 10, 20, 11, 5]'    # +13.83 +/- 34.05: below 0.5 e
even='[5, 10, 20, 10, 5]'

setup() {  # label
  st=$tmp/$1
  mkdir -p "$st"
  echo 0 >"$st/busy"
  echo 500 >"$st/latest"
  printf '%s\n' "$c20" "$c40" "$c60" "$c80" >"$st/commits"
  git -C "$here" rev-parse HEAD >"$st/ref.test"  # REF (test): this repository's HEAD (sprt_run.sh checks it)
  echo "$even" >"$st/ptnml"
  : >"$st/dispatches"
}
drive() {  # label args...
  local label=$1
  shift
  FAKE_GH=$tmp/$label GH=$tmp/gh POLL=0 SHARDS=2 REPO=owner/fork REF=test SPRT_DATA=$tmp/$label/data \
    FORK_JOBS=$tmp/$label/jobs SPRT_UNSUPERVISED=${UNSUPERVISED-1} \
    bash "$here/h2h_run.sh" "$label" "$@" >"$tmp/$label/out" 2>&1
  echo $? >"$tmp/$label/rc"
}
rc() { cat "$tmp/$1/rc"; }
dispatches() { wc -l <"$tmp/$1/dispatches" | tr -d ' '; }
stages() { grep -o 'stage=[0-9]*' "$tmp/$1/dispatches" | tr '\n' ' '; }
decl=(--const RfpTest --stages 2 --prefer 40 --prefer-reason "the current value" --idea rfp)

setup h-two
echo "$better" >"$tmp/h-two/ptnml.$c40.$c60"
drive h-two "${decl[@]}" "40=$c40" "60=$c60"
check "two values: exit 0 after one pairing of 2 stages" [ "$(rc h-two):$(stages h-two)" = "0:stage=0 stage=1 " ]
check "two values: the stronger is picked" grep -q '"winner": "60"' "$tmp/h-two/data/h-two/pick.json"
check "two values: the row has the delta, its error and the games" bash -c \
  "grep -q '60 - 40 +96.36 +/- 34.05 nElo' '$tmp/h-two/data/h-two/constants-line.md' && grep -q '(400 games)' '$tmp/h-two/data/h-two/constants-line.md'"
check "two values: the pairing ran as kind fixed" grep -q "kind fixed, stc, alpha 0.05, beta 0.20, cap 2, fixed length, idea rfp" "$tmp/h-two/out"

setup h-tie
echo "$edge" >"$tmp/h-tie/ptnml.$c40.$c60"
drive h-tie "${decl[@]}" "40=$c40" "60=$c60"
check "an edge within 0.5 e keeps the preferred value" bash -c \
  "[ \$(cat '$tmp/h-tie/rc') = 0 ] && grep -q '\"winner\": \"40\"' '$tmp/h-tie/data/h-tie/pick.json' && grep -q 'the tie rule keeps 40' '$tmp/h-tie/data/h-tie/constants-line.md'"

setup h-three
echo "$better" >"$tmp/h-three/ptnml.$c40.$c60"
echo "$worse" >"$tmp/h-three/ptnml.$c60.$c80"
drive h-three "${decl[@]}" "40=$c40" "60=$c60" "80=$c80"
check "three values: a round robin of 3 pairings, each stages 0 and 1" [ "$(rc h-three):$(stages h-three)" = "0:stage=0 stage=1 stage=0 stage=1 stage=0 stage=1 " ]
check "three values: every pairing dispatched with its commits" bash -c \
  "grep -q 'base=$c40 -f test=$c60' '$tmp/h-three/dispatches' && grep -q 'base=$c40 -f test=$c80' '$tmp/h-three/dispatches' && grep -q 'base=$c60 -f test=$c80' '$tmp/h-three/dispatches'"
check "three values: each pairing's runs carry its own name (bug review 2026-11-11, T6)" bash -c \
  "grep -q 'name=h-three.40-60\$' '$tmp/h-three/dispatches' && grep -q 'name=h-three.40-80\$' '$tmp/h-three/dispatches' && grep -q 'name=h-three.60-80\$' '$tmp/h-three/dispatches' && grep -q \"stage 1 (h-three.60-80)\$\" '$tmp/h-three/titles'"
check "three values: the strongest is picked" grep -q '"winner": "60"' "$tmp/h-three/data/h-three/pick.json"
check "three values: the row says round robin and least squares" grep -q "values 40, 60, 80 in a round robin, 2 stages of 200 games per pairing on the same openings (1,200 games); 60 - 40 +96.36 +/- 27.80 nElo, 80 - 40 +0.00 +/- 27.80 nElo (least squares over the 3 pairings)" "$tmp/h-three/data/h-three/constants-line.md"

setup h-four
echo "$better" >"$tmp/h-four/ptnml.$c40.$c60"
echo "$better" >"$tmp/h-four/ptnml.$c20.$c60"
echo "$worse" >"$tmp/h-four/ptnml.$c60.$c80"
decl4=(--const RfpTest --stages 2 --prefer 20 --prefer-reason "the most cautious" --idea rfp)
drive h-four "${decl4[@]}" "20=$c20" "40=$c40" "60=$c60" "80=$c80"
check "four values: a round robin of 6 pairings, each stages 0 and 1" [ "$(rc h-four):$(stages h-four)" = "0:stage=0 stage=1 stage=0 stage=1 stage=0 stage=1 stage=0 stage=1 stage=0 stage=1 stage=0 stage=1 " ]
names_ok() {  # every pairing of the four values was dispatched under its own name
  local p
  for p in 20-40 20-60 20-80 40-60 40-80 60-80; do grep -q "name=h-four.$p\$" "$tmp/h-four/dispatches" || return 1; done
}
check "four values: every pairing dispatched under its own name" names_ok
check "four values: the strongest is picked" grep -q '"winner": "60"' "$tmp/h-four/data/h-four/pick.json"
check "four values: the row says round robin over 6 pairings (2,400 games)" grep -q "values 20, 40, 60, 80 in a round robin, 2 stages of 200 games per pairing on the same openings (2,400 games); .* (least squares over the 6 pairings)" "$tmp/h-four/data/h-four/constants-line.md"

setup h-four-tie
echo "$edge" >"$tmp/h-four-tie/ptnml.$c20.$c40"
drive h-four-tie "${decl4[@]}" "20=$c20" "40=$c40" "60=$c60" "80=$c80"
check "four values: an edge within 0.5 e keeps the preferred value" bash -c \
  "[ \$(cat '$tmp/h-four-tie/rc') = 0 ] && grep -q '\"winner\": \"20\"' '$tmp/h-four-tie/data/h-four-tie/pick.json'"

drive h-three "${decl[@]}" "40=$c40" "60=$c60" "80=$c80"
check "a rerun skips the finished pairings and picks the same" bash -c \
  "[ \$(cat '$tmp/h-three/rc') = 0 ] && [ \$(wc -l <'$tmp/h-three/dispatches') = 6 ] && grep -q '\"winner\": \"60\"' '$tmp/h-three/data/h-three/pick.json'"

drive h-three --const RfpTest --stages 2 --prefer 60 --prefer-reason "the simpler value" --idea rfp "40=$c40" "60=$c60" "80=$c80"
check "a changed declaration is refused, nothing dispatched" bash -c \
  "[ \$(cat '$tmp/h-three/rc') = 1 ] && [ \$(wc -l <'$tmp/h-three/dispatches') = 6 ] && grep -q 'differs from the declaration' '$tmp/h-three/out'"

setup h-fail
touch "$tmp/h-fail/fail.502"
drive h-fail "${decl[@]}" "40=$c40" "60=$c60"
check "a failed run stops it before any pick" bash -c \
  "[ \$(cat '$tmp/h-fail/rc') = 1 ] && [ ! -e '$tmp/h-fail/data/h-fail/pick.json' ] && grep -q 'pairing h-fail.40-60 stopped' '$tmp/h-fail/out'"

setup h-refusals
drive h-refusals "${decl[@]}" "40=$c40"
check "one value is refused" bash -c "[ \$(cat '$tmp/h-refusals/rc') = 1 ] && grep -q 'takes 2 to 4 values' '$tmp/h-refusals/out'"
drive h-refusals "${decl[@]}" "20=$c20" "40=$c40" "60=$c60" "80=$c80" "99=$c80"
check "five values are refused" bash -c "[ \$(cat '$tmp/h-refusals/rc') = 1 ] && grep -q 'takes 2 to 4 values (LABEL=COMMIT), not 5' '$tmp/h-refusals/out'"
drive h-refusals "${decl[@]}" "40=$c40" "60=$c40"
check "two values on one commit are refused" bash -c "[ \$(cat '$tmp/h-refusals/rc') = 1 ] && grep -q 'the same commit' '$tmp/h-refusals/out'"
drive h-refusals --const RfpTest --stages 2 --prefer 50 --prefer-reason "the current value" --idea rfp "40=$c40" "60=$c60"
check "a preferred value that is not a candidate is refused" bash -c "[ \$(cat '$tmp/h-refusals/rc') = 1 ] && grep -q 'is not one of the values' '$tmp/h-refusals/out'"
UNSUPERVISED= drive h-refusals "${decl[@]}" "40=$c40" "60=$c60"
check "outside the supervisor it refuses" bash -c "[ \$(cat '$tmp/h-refusals/rc') = 1 ] && grep -q 'not started by the job supervisor' '$tmp/h-refusals/out'"
check "and none of the refusals dispatched anything" [ "$(dispatches h-refusals)" = 0 ]

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed"
  for d in "$tmp"/*/; do [ -f "$d/out" ] && { echo "--- $d"; tail -8 "$d/out"; }; done
  exit 1
fi
echo "all checks passed"
