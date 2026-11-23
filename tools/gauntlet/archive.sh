#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Keeps a gauntlet run's results after GitHub deletes them (owner,
# 2026-11-09: artifacts are kept 90 days; the first runs' expire on
# 2027-01-29 to 2027-01-31). Downloads every artifact of a run of
# .github/workflows/gauntlet.yml (a gauntlet or an anchor check) into
# DEST/run-RUN_ID/, writes a SHA-256 manifest and a meta file, and verifies
# the manifest. Part of each gauntlet's report step (DESIGN.md §5.2, Testing
# setup); tools/gauntlet/report.py's level 0 reads the archive when the
# runner could not download an earlier run (--archive).
#
#   tools/gauntlet/archive.sh RUN_ID [DEST]      DEST defaults to ~/fork-data/gauntlet
#
# Layout: the run's result artifact (gauntlet-result or check-result, or a
# run's only artifact) at the top of run-RUN_ID, so run-RUN_ID/gauntlet.pgn
# and run-RUN_ID/ordo.txt are where report.py and the Control Center read
# them; every other artifact (the game shards, the Fork binary) in a folder
# of its own name. meta.txt: the run (id, repository, head commit, created
# time, conclusion, title) and a tab-separated row per artifact: id, name,
# GitHub's size in bytes and digest, its expiry, and what became of it
# (archived, or expired: listed only). SHA256SUMS: sha256sum's format, one
# line per file under run-RUN_ID (meta.txt included), relative paths.
#
# Each artifact is fetched as GitHub's zip, checked against the digest
# GitHub reports for it (when it gives one) and unpacked. A folder that
# already holds files without a manifest (an archive made by hand): a file
# identical to the artifact's is kept as it is; one that differs is kept,
# the artifact's copy goes to the artifact's own folder beside it, and both
# are reported (exit status 3). Nothing is ever overwritten.
#
# Idempotent: when run-RUN_ID has its manifest, the archive is only
# verified (no download, so it works once GitHub's copy is gone): every
# file must match and every file must be listed. A mismatch is an error.
#
# Exit status: 0 archived or verified; 1 a failure (nothing is left half
# written: no manifest unless every artifact is in place); 2 usage; 3
# archived, with an earlier copy that differs from the artifact kept beside
# it. Never writes into a git work tree (the repository included).
# Environment: GH (default gh), REPO (default BOSSDOTCOM/fork).
set -uo pipefail
usage='usage: tools/gauntlet/archive.sh RUN_ID [DEST]'
run=${1:-}
case $run in '' | *[!0-9]*) echo "$usage" >&2; exit 2 ;; esac
[ $# -le 2 ] || { echo "$usage" >&2; exit 2; }
dest=${2:-$HOME/fork-data/gauntlet}
GH=${GH:-gh}
REPO=${REPO:-BOSSDOTCOM/fork}
die() { echo "archive.sh: run $run: $*" >&2; exit 1; }

mkdir -p "$dest" || die "cannot create $dest"
dest=$(cd "$dest" && pwd -P) || die "cannot enter $dest"
if (cd "$dest" && env -u GIT_DIR -u GIT_WORK_TREE git rev-parse --is-inside-work-tree >/dev/null 2>&1); then
  die "$dest is inside a git work tree: the archive is kept outside every repository"
fi
dir=$dest/run-$run

# Every file under run-RUN_ID but the manifest, relative, sorted.
files() { (cd "$dir" && find . -type f ! -path ./SHA256SUMS | sed 's|^\./||' | LC_ALL=C sort); }

verify() {
  local listed
  (cd "$dir" && sha256sum -c --quiet SHA256SUMS) || die "a file does not match $dir/SHA256SUMS"
  listed=$(sed -E 's/^[0-9a-f]{64} [ *]//' "$dir/SHA256SUMS" | LC_ALL=C sort)
  [ "$(files)" = "$listed" ] || die "$dir holds files that are not in its manifest: $(comm -23 <(files) <(echo "$listed") | tr '\n' ' ')"
}

if [ -f "$dir/SHA256SUMS" ]; then
  verify
  echo "run $run: verified $(wc -l <"$dir/SHA256SUMS") files in $dir (already archived)"
  exit 0
fi

# The run, and its artifacts (id, name, size, expired, digest, expiry).
info=$("$GH" api "repos/$REPO/actions/runs/$run" \
  --jq '[.id, .head_sha, .created_at, .status, (.conclusion // ""), .path, .display_title] | @tsv') ||
  die "cannot read the run from GitHub"
IFS=$'\t' read -r id sha created status conclusion path title <<<"$info"
[ "$id" = "$run" ] || die "GitHub answered for run '$id'"
case $path in *gauntlet.yml*) ;; *) die "not a gauntlet run (workflow $path)" ;; esac
[ "$status" = completed ] || die "the run is $status: archive it once it has completed"
list=$("$GH" api "repos/$REPO/actions/runs/$run/artifacts?per_page=100" \
  --jq '.total_count, (.artifacts[] | [.id, .name, .size_in_bytes, .expired, (.digest // ""), (.expires_at // "")] | @tsv)') ||
  die "cannot list the run's artifacts"
total=$(head -n 1 <<<"$list")
rows=$(tail -n +2 <<<"$list")
[ "$total" -le 100 ] 2>/dev/null || die "GitHub lists '$total' artifacts (more than one page)"
[ "$(grep -c . <<<"$rows")" = "$total" ] || die "GitHub listed $(grep -c . <<<"$rows") of $total artifacts"
[ "$total" -gt 0 ] || die "the run has no artifacts"
top=$(cut -f2 <<<"$rows" | grep -xE 'gauntlet-result|check-result' | head -n 1)
[ -n "$top" ] || [ "$total" != 1 ] || top=$(cut -f2 <<<"$rows")

stage=$(mktemp -d "$dest/.run-$run.partial.XXXXXX") || die "cannot create a staging folder in $dest"
trap 'rm -rf "$stage"' EXIT
unpack() {  # zip folder
  if command -v unzip >/dev/null 2>&1; then unzip -q "$1" -d "$2"
  else python3 -I -m zipfile -e "$1" "$2"; fi
}
table=""
while IFS=$'\t' read -r aid name size expired digest expires; do
  case $name in '' | . | .. | */* | *\\*) die "artifact name '$name' cannot be a folder name" ;; esac
  if [ "$expired" = true ]; then
    echo "run $run: artifact $name has expired on GitHub: listed in meta.txt, not archived" >&2
    table+="artifact	$aid	$name	$size	$digest	$expires	expired"$'\n'
    continue
  fi
  "$GH" api "repos/$REPO/actions/artifacts/$aid/zip" >"$stage/$aid.zip" || die "cannot download artifact $name"
  case $digest in
    sha256:*) [ "$(sha256sum <"$stage/$aid.zip" | cut -c1-64)" = "${digest#sha256:}" ] ||
                die "artifact $name does not match GitHub's digest $digest" ;;
    '') echo "run $run: GitHub gives no digest for artifact $name" >&2 ;;
    *) die "artifact $name has a digest of an unknown kind: $digest" ;;
  esac
  mkdir "$stage/$aid" && unpack "$stage/$aid.zip" "$stage/$aid" || die "cannot unpack artifact $name"
  rm -f "$stage/$aid.zip"
  table+="artifact	$aid	$name	$size	$digest	$expires	archived"$'\n'
done <<<"$rows"

# Into place: never over an existing file.
mkdir -p "$dir" || die "cannot create $dir"
differ=()
while IFS=$'\t' read -r aid name _ expired _; do
  [ "$expired" = true ] && continue
  if [ "$name" = "$top" ]; then into=$dir; else into=$dir/$name; fi
  while IFS= read -r f; do
    if [ -e "$into/$f" ]; then
      cmp -s "$stage/$aid/$f" "$into/$f" && continue
      if [ "$into" = "$dir" ] && [ -e "$dir/$name/$f" ] && cmp -s "$stage/$aid/$f" "$dir/$name/$f"; then
        differ+=("$f (the artifact's copy in $name/$f)")  # placed there by an interrupted run
        continue
      fi
      if [ "$into" = "$dir" ] && [ ! -e "$dir/$name/$f" ]; then
        mkdir -p "$(dirname "$dir/$name/$f")" && mv "$stage/$aid/$f" "$dir/$name/$f" || die "cannot move $f into place"
        differ+=("$f (the artifact's copy in $name/$f)")
        continue
      fi
      die "$into/$f exists and differs from artifact $name's copy: left as it is, nothing archived"
    fi
    mkdir -p "$(dirname "$into/$f")" && mv "$stage/$aid/$f" "$into/$f" || die "cannot move $f into place"
  done < <(cd "$stage/$aid" && find . -type f | sed 's|^\./||' | LC_ALL=C sort)
done <<<"$rows"

{
  printf 'run\t%s\nrepository\t%s\nhead_sha\t%s\ncreated_at\t%s\nconclusion\t%s\ntitle\t%s\n' \
    "$run" "$REPO" "$sha" "$created" "$conclusion" "$title"
  printf 'archived_at\t%s\nlayout\t%s at the top; every other artifact in a folder of its name\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${top:-no result artifact}"
  printf '# artifact\tid\tname\tsize_in_bytes\tdigest\texpires_at\tstatus\n'
  printf '%s' "$table"
  for d in "${differ[@]}"; do printf 'differs\t%s\n' "$d"; done
} >"$stage/meta.txt" || die "cannot write meta.txt"
if [ -e "$dir/meta.txt" ]; then  # an interrupted run's (the same but for its time), or not ours
  [ "$(grep -v '^archived_at' "$stage/meta.txt")" = "$(grep -v '^archived_at' "$dir/meta.txt")" ] ||
    die "$dir/meta.txt exists without a manifest and is not this archive's: left as it is"
else
  mv "$stage/meta.txt" "$dir/meta.txt" || die "cannot write meta.txt"
fi
(cd "$dir" && files | tr '\n' '\0' | xargs -0 sha256sum >"$stage/SHA256SUMS") || die "cannot hash the files"
mv "$stage/SHA256SUMS" "$dir/SHA256SUMS" || die "cannot write the manifest"
verify
bytes=$(cd "$dir" && files | tr '\n' '\0' | xargs -0 cat | wc -c)
echo "run $run: archived $(wc -l <"$dir/SHA256SUMS") files, $bytes bytes, in $dir (commit ${sha:0:7}, created $created)"
if [ ${#differ[@]} -gt 0 ]; then
  printf 'run %s: an earlier copy differs from the artifact (both kept): %s\n' "$run" "${differ[@]}" >&2
  exit 3
fi
exit 0
