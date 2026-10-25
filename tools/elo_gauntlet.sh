#!/usr/bin/env bash
# Elo baseline gauntlet (Milestone A, owner 2026-10-25), in WSL: Fork against
# the anchor engines built by tools/get_anchor_engines.sh, then Ordo with the
# anchors fixed at their CCRL Blitz ratings (KB competition.md §5).
#
#   tools/elo_gauntlet.sh <fork binary> <openings.epd> <output dir> [games per anchor]
#
# fastchess gauntlet, Fork as the seed; 10+0.1 s, one thread each (every
# engine's default; the weaker anchors have no Threads option), Fork's
# Hash 16 MB (the anchors keep their own defaults; Weiss's online book off),
# each opening played with both colours, concurrency 10. Openings: random
# 8-ply positions (tools/make_openings.py), the same for every pairing.
# Caveat for the result: CCRL Blitz is 2'+1" on CCRL's hardware, so an Elo
# fitted at 10+0.1 on this machine is a rough placement, not a CCRL rating.
set -euo pipefail
[ $# -ge 3 ] || { sed -n '2,13p' "$0"; exit 2; }
fork=$(realpath "$1")
book=$(realpath "$2")
out=$3
per=${4:-200}
eng=$HOME/fork-tools/engines
bin=$HOME/fork-tools/bin
mkdir -p "$out"
out=$(realpath "$out")
cd "$out"  # fastchess writes config.json into the working directory

# Name, binary, CCRL Blitz 2'+1" rating (list computed 2026-10-24).
anchors=(
  "Shallow Blue 2.0.0|shallowblue-2.0.0|1578"
  "Stash 12.0|stash-12.0|1883"
  "Stash 15.3|stash-15.3|2173"
  "Stash 19.0|stash-19.0|2473"
  "Weiss 1.0|weiss-1.0|2896"
)
args=(-engine cmd="$fork" name=Fork option.Hash=16)
: >"$out/anchors.csv"
for a in "${anchors[@]}"; do
  IFS='|' read -r name file rating <<<"$a"
  [ -x "$eng/$file" ] || { echo "elo_gauntlet.sh: missing $eng/$file (tools/get_anchor_engines.sh)" >&2; exit 1; }
  extra=()
  [ "$file" = weiss-1.0 ] && extra=(option.NoobBook=false)
  args+=(-engine cmd="$eng/$file" name="$name" "${extra[@]}")
  echo "\"$name\",$rating" >>"$out/anchors.csv"
done

"$bin/fastchess" "${args[@]}" -tournament gauntlet -seeds 1 \
  -each tc=10+0.1 \
  -openings file="$book" format=epd order=random -srand 20261025 \
  -rounds $((per / 2)) -repeat -concurrency "${CONCURRENCY:-10}" \
  -pgnout file="$out/gauntlet.pgn" >"$out/gauntlet.log" 2>&1 || echo "fastchess ended with an error"
echo "fastchess done"
"$bin/ordo" -p "$out/gauntlet.pgn" -m "$out/anchors.csv" -W -D -s 1000 -o "$out/ordo.txt" >/dev/null 2>&1
cat "$out/ordo.txt"
