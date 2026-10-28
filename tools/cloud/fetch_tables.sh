#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The Syzygy 3-4-5 tablebases a cloud SPRT shard gives both engines
# (DESIGN.md §5.2, "Testing setup": 3-4-5 Syzygy for both sides), checked
# file by file against the committed manifest tools/cloud/syzygy-345.sha256
# (its header says where the hashes come from).
#
#   tools/cloud/fetch_tables.sh DIR      -> DIR/*.rtbw, DIR/*.rtbz (290 files, 939 MiB)
#
# Files already in DIR (a restored cache) are kept; missing ones are
# downloaded from the lichess mirror, four at a time. Every file is then
# verified, and DIR must hold no other table file: the set is exactly the
# manifest's, or the script fails. Needs curl, sha256sum, xargs.
set -euo pipefail
dir=${1:?usage: fetch_tables.sh DIR}
here=$(cd "$(dirname "$0")" && pwd)
url=${FORK_TABLES_URL:-https://tablebase.lichess.ovh/tables/standard}
[ -d "$dir" ] || mkdir -p "$dir"
cd "$dir"
list=$(mktemp)
trap 'rm -f "$list"' EXIT
grep -v '^#' "$here/syzygy-345.sha256" | grep . >"$list"
[ "$(wc -l <"$list")" = 290 ] || { echo "fetch_tables.sh: the manifest does not list 290 files" >&2; exit 1; }

# Missing files: WDL from 3-4-5-wdl/, DTZ from 3-4-5-dtz/.
awk '{ print $2 }' "$list" | while read -r f; do [ -f "$f" ] || echo "$f"; done |
  awk -v u="$url" '/\.rtbw$/ { print u "/3-4-5-wdl/" $0 } /\.rtbz$/ { print u "/3-4-5-dtz/" $0 }' |
  xargs -r -n 1 -P 4 sh -c 'curl -fsSL --retry 5 --retry-delay 5 -o "$(basename "$1").part" "$1" &&
    mv "$(basename "$1").part" "$(basename "$1")"' fetch

sha256sum -c --quiet --strict "$list" || { echo "fetch_tables.sh: a table file does not match the manifest" >&2; exit 1; }
extra=$(find . -maxdepth 1 -type f \( -name '*.rtbw' -o -name '*.rtbz' \) | sed 's|^\./||' | sort |
  comm -23 - <(awk '{ print $2 }' "$list" | sort))
[ -z "$extra" ] || { echo "fetch_tables.sh: table files not in the manifest: $extra" >&2; exit 1; }
echo "fetch_tables.sh: 290 Syzygy 3-4-5 files verified in $(pwd)"
