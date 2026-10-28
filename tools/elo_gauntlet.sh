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
# Exits 1 with no ratings when fastchess fails or plays fewer games than
# planned (the partial PGN is kept), or when Ordo fails.
set -euo pipefail
[ $# -ge 3 ] || { sed -n '2,15p' "$0"; exit 2; }
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
# ANCHORS=a (Milestone A, the default), b (Milestone B: Stash 15.3 and
# 19.0 plus three unrelated code bases; owner, 2026-10-25) or c (Milestone
# C: the B set plus Weiss 1.0 above it; owner, 2026-10-26. The KB's
# Milestone C anchors Supernova 2.4 and K2 0.99 are added once built).
case "${ANCHORS:-a}" in
  a) anchors=(
       "Shallow Blue 2.0.0|shallowblue-2.0.0|1578"
       "Stash 12.0|stash-12.0|1883"
       "Stash 15.3|stash-15.3|2173"
       "Stash 19.0|stash-19.0|2473"
       "Weiss 1.0|weiss-1.0|2896"
     ) ;;
  b) anchors=(
       "Belette 2.0.0|belette-2.0.0|2115"
       "Stash 15.3|stash-15.3|2173"
       "Chal 1.3.0|chal-1.3.0|2285"
       "Stash 19.0|stash-19.0|2473"
       "WyldChess 1.51|wyldchess-1.51|2603"
     ) ;;
  c) anchors=(
       "Belette 2.0.0|belette-2.0.0|2115"
       "Stash 15.3|stash-15.3|2173"
       "Chal 1.3.0|chal-1.3.0|2285"
       "Stash 19.0|stash-19.0|2473"
       "WyldChess 1.51|wyldchess-1.51|2603"
       "Weiss 1.0|weiss-1.0|2896"
     ) ;;
  *) echo "elo_gauntlet.sh: ANCHORS must be a, b or c" >&2; exit 2 ;;
esac
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

fc_status=0
"$bin/fastchess" "${args[@]}" -tournament gauntlet -seeds 1 \
  -each tc=10+0.1 \
  -openings file="$book" format=epd order=random -srand 20261025 \
  -rounds $((per / 2)) -repeat -concurrency "${CONCURRENCY:-10}" \
  -pgnout file="$out/gauntlet.pgn" >"$out/gauntlet.log" 2>&1 || fc_status=$?
# Games played against games planned (per anchor, with both colours).
planned=$(( per / 2 * 2 * ${#anchors[@]} ))
played=$(grep -c '^\[Event ' "$out/gauntlet.pgn" 2>/dev/null || true)
echo "fastchess done: ${played:-0} of $planned games, exit status $fc_status"
# A failed or short gauntlet gives no ratings: a partial result would read
# like a finished one. The partial PGN stays in $out for a look by hand.
if [ "$fc_status" != 0 ] || [ "${played:-0}" != "$planned" ]; then
  echo "elo_gauntlet.sh: fastchess failed or stopped early (exit status $fc_status, ${played:-0} of $planned games); no ratings, see $out/gauntlet.log" >&2
  tail -n 5 "$out/gauntlet.log" >&2
  exit 1
fi
"$bin/ordo" -p "$out/gauntlet.pgn" -m "$out/anchors.csv" -W -D -s 1000 -o "$out/ordo.txt" >"$out/ordo.log" 2>&1 ||
  { echo "elo_gauntlet.sh: ordo failed, see $out/ordo.log" >&2; tail -n 5 "$out/ordo.log" >&2; exit 1; }
cat "$out/ordo.txt"
