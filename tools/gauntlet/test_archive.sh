#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Tests of tools/gauntlet/archive.sh against a fake gh on PATH (a shell
# script that answers the three API calls from files in a state folder and
# counts the downloads). Checks: the layout (the result artifact at the
# top, the others in their own folders, an expired one listed in meta.txt
# only), the manifest in sha256sum's format and its verification; a second
# call only verifies, with no download and GitHub's copy gone; a changed,
# a removed and an unlisted file are each an error and nothing is
# rewritten; an earlier hand-made copy: an identical file kept, a
# different one kept beside the artifact's copy (exit 3), then verified; a
# zip that does not match GitHub's digest, a failed download, a run still
# going and a run of another workflow each stop it with no manifest and no
# staging folder left; a destination inside a git work tree is refused.
# Uses $PYTHON (default python3) to write the zips.
#
#   bash tools/gauntlet/test_archive.sh
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
PYTHON=${PYTHON:-python3}
# A relative path (check.sh passes .venv/Scripts/python.exe) would break inside the subshells that cd away.
case $PYTHON in */*) PYTHON=$(cd "$(dirname "$PYTHON")" && pwd)/$(basename "$PYTHON") ;; esac

mkdir -p "$tmp/bin"
cat >"$tmp/bin/gh" <<'EOF'
#!/usr/bin/env bash
# The fake gh: state in $FAKE_GH (run.tsv, artifacts.tsv, zips/ID.zip; a file "gone" makes every call fail).
[ "$1" = api ] || { echo "fake gh: unexpected $*" >&2; exit 1; }
[ ! -e "$FAKE_GH/gone" ] || { echo "fake gh: HTTP 404: Not Found" >&2; exit 1; }
case $2 in
  repos/owner/fork/actions/runs/*/artifacts\?per_page=100) cat "$FAKE_GH/artifacts.tsv" ;;
  repos/owner/fork/actions/runs/*) cat "$FAKE_GH/run.tsv" ;;
  repos/owner/fork/actions/artifacts/*/zip)
    id=${2#repos/owner/fork/actions/artifacts/}
    id=${id%/zip}
    echo "$id" >>"$FAKE_GH/downloads"
    [ ! -e "$FAKE_GH/fail-$id" ] || { echo "fake gh: connection reset" >&2; exit 1; }
    cat "$FAKE_GH/zips/$id.zip" ;;
  *) echo "fake gh: unexpected $*" >&2; exit 1 ;;
esac
EOF
chmod +x "$tmp/bin/gh"
export PATH="$tmp/bin:$PATH" REPO=owner/fork
unset GH

# A state folder with run 123's two live artifacts and an expired one.
state() {  # label
  local s=$tmp/$1
  mkdir -p "$s/zips" "$s/src/result" "$s/src/shard"
  printf '[Event "x"]\n[Result "1-0"]\n\n1. e4 1-0\n' >"$s/src/result/gauntlet.pgn"
  printf 'fake ordo table\n' >"$s/src/result/ordo.txt"
  printf '[Event "x"]\n' >"$s/src/shard/games.pgn"
  printf 'cpu=test\n' >"$s/src/shard/shard.txt"
  (cd "$s/src/result" && "$PYTHON" -I -m zipfile -c ../../zips/11.zip gauntlet.pgn ordo.txt) &&
    (cd "$s/src/shard" && "$PYTHON" -I -m zipfile -c ../../zips/12.zip games.pgn shard.txt) ||
    { echo "cannot write the zips with $PYTHON"; exit 1; }
  printf '123\tabc1234def\t2026-11-09T00:06:19Z\tcompleted\tsuccess\t.github/workflows/gauntlet.yml\tA title\n' >"$s/run.tsv"
  {
    echo 3
    printf '11\tgauntlet-result\t300\tfalse\tsha256:%s\t2027-02-07T00:06:20Z\n' "$(sha256sum <"$s/zips/11.zip" | cut -c1-64)"
    printf '12\tgames-x-1\t200\tfalse\tsha256:%s\t2027-02-07T00:06:20Z\n' "$(sha256sum <"$s/zips/12.zip" | cut -c1-64)"
    printf '13\tfork\t3000\ttrue\tsha256:%s\t2026-11-16T00:11:30Z\n' "$(printf '0%.0s' {1..64})"
  } >"$s/artifacts.tsv"
  : >"$s/downloads"
}
archive() {  # label dest
  FAKE_GH=$tmp/$1 bash "$here/archive.sh" 123 "$2" >"$tmp/$1/out" 2>&1
  echo $? >"$tmp/$1/rc"
}
rc() { [ "$(cat "$tmp/$1/rc")" = "$2" ] || { cat "$tmp/$1/out"; false; }; }
no_partial() { ! ls -a "$1" | grep -q partial; }

# 1. A fresh archive.
state fresh
archive fresh "$tmp/fresh/dest"
d=$tmp/fresh/dest/run-123
check "fresh: exit 0" rc fresh 0
check "fresh: the result artifact at the top" cmp -s "$d/gauntlet.pgn" "$tmp/fresh/src/result/gauntlet.pgn"
check "fresh: a shard in its own folder" cmp -s "$d/games-x-1/shard.txt" "$tmp/fresh/src/shard/shard.txt"
check "fresh: the expired artifact is not downloaded" test ! -e "$d/fork"
check "fresh: two downloads" test "$(sort "$tmp/fresh/downloads" | tr '\n' ' ')" = "11 12 "
check "fresh: the manifest lists every file, meta.txt included" \
  test "$(sed -E 's/^[0-9a-f]{64} [ *]//' "$d/SHA256SUMS" | tr '\n' ' ')" = \
  "games-x-1/games.pgn games-x-1/shard.txt gauntlet.pgn meta.txt ordo.txt "
check "fresh: sha256sum -c accepts the manifest" bash -c "cd '$d' && sha256sum -c --quiet SHA256SUMS"
check "fresh: meta.txt has the commit and every artifact" \
  bash -c "grep -qx 'head_sha	abc1234def' '$d/meta.txt' && grep -q '	gauntlet-result	300	sha256:.*	archived$' '$d/meta.txt' &&
           grep -q '	fork	3000	.*	expired$' '$d/meta.txt'"
check "fresh: no staging folder left" no_partial "$tmp/fresh/dest"

# 2. Idempotent: verified, not downloaded again, even with GitHub's copy gone.
touch "$tmp/fresh/gone"
sum=$(cat "$d/SHA256SUMS")
archive fresh "$tmp/fresh/dest"
check "again: exit 0 with GitHub gone" rc fresh 0
check "again: says verified" grep -q 'verified 5 files' "$tmp/fresh/out"
check "again: no download" test "$(wc -l <"$tmp/fresh/downloads")" = 2
check "again: the manifest unchanged" test "$(cat "$d/SHA256SUMS")" = "$sum"

# 3. A changed, a removed or an unlisted file: an error, nothing rewritten.
printf 'tampered\n' >"$d/ordo.txt"
archive fresh "$tmp/fresh/dest"
check "changed file: exit 1" rc fresh 1
check "changed file: left as it is" test "$(cat "$d/ordo.txt")" = tampered
cp "$tmp/fresh/src/result/ordo.txt" "$d/ordo.txt"
mv "$d/games-x-1/games.pgn" "$tmp/fresh/aside.pgn"
archive fresh "$tmp/fresh/dest"
check "removed file: exit 1" rc fresh 1
mv "$tmp/fresh/aside.pgn" "$d/games-x-1/games.pgn"
printf 'note\n' >"$d/notes.txt"
archive fresh "$tmp/fresh/dest"
check "unlisted file: exit 1" rc fresh 1
check "unlisted file: named" grep -q 'notes.txt' "$tmp/fresh/out"
rm "$d/notes.txt"
archive fresh "$tmp/fresh/dest"
check "restored: exit 0" rc fresh 0
check "restored: the manifest unchanged" test "$(cat "$d/SHA256SUMS")" = "$sum"

# 4. An earlier copy made by hand: identical files kept, a different one kept beside the artifact's.
state hand
d=$tmp/hand/dest/run-123
mkdir -p "$d"
cp "$tmp/hand/src/result/gauntlet.pgn" "$d/gauntlet.pgn"
printf 'an older ordo table\n' >"$d/ordo.txt"
archive hand "$tmp/hand/dest"
check "hand copy: exit 3" rc hand 3
check "hand copy: the differing file kept" test "$(cat "$d/ordo.txt")" = 'an older ordo table'
check "hand copy: the artifact's copy beside it" cmp -s "$d/gauntlet-result/ordo.txt" "$tmp/hand/src/result/ordo.txt"
check "hand copy: the identical file not duplicated" test ! -e "$d/gauntlet-result/gauntlet.pgn"
check "hand copy: reported" grep -q 'ordo.txt' "$tmp/hand/out"
check "hand copy: in meta.txt" grep -q '^differs	ordo.txt' "$d/meta.txt"
check "hand copy: both in the manifest" bash -c "grep -q ' .ordo.txt\$' '$d/SHA256SUMS' && grep -q 'gauntlet-result/ordo.txt' '$d/SHA256SUMS'"
archive hand "$tmp/hand/dest"
check "hand copy: then verified, exit 0" rc hand 0

# 5. Failures: no manifest, no staging folder.
state digest
printf 'x' >>"$tmp/digest/zips/12.zip"
archive digest "$tmp/digest/dest"
check "digest mismatch: exit 1" rc digest 1
check "digest mismatch: named" grep -q 'does not match GitHub' "$tmp/digest/out"
check "digest mismatch: nothing archived" test ! -e "$tmp/digest/dest/run-123"
check "digest mismatch: no staging folder" no_partial "$tmp/digest/dest"
state flaky
touch "$tmp/flaky/fail-12"
archive flaky "$tmp/flaky/dest"
check "failed download: exit 1" rc flaky 1
check "failed download: nothing archived" test ! -e "$tmp/flaky/dest/run-123"
check "failed download: no staging folder" no_partial "$tmp/flaky/dest"
state running
sed -i 's/completed/in_progress/' "$tmp/running/run.tsv"
archive running "$tmp/running/dest"
check "run in progress: exit 1" rc running 1
check "run in progress: nothing downloaded" test ! -s "$tmp/running/downloads"
state other
sed -i 's/gauntlet.yml/sprt.yml/' "$tmp/other/run.tsv"
archive other "$tmp/other/dest"
check "another workflow's run: exit 1" rc other 1
state repo
git init -q "$tmp/repo/work"
archive repo "$tmp/repo/work/archive"
check "inside a git work tree: exit 1" rc repo 1
check "inside a git work tree: nothing downloaded" test ! -s "$tmp/repo/downloads"
FAKE_GH=$tmp/fresh bash "$here/archive.sh" >/dev/null 2>&1
check "no run id: usage, exit 2" test $? = 2

echo "$failures failed"
[ "$failures" = 0 ]
