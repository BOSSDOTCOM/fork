#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The shard progress uploads change no result (owner, 2026-11-14): the same shard is played twice with
# tools/cloud/run_shard.sh, once alone and once with the progress watcher (tools/cloud/shard_progress.py)
# running beside it as in .github/workflows/sprt.yml, its uploads going to a folder through a stand-in upload
# command, and the results are compared byte for byte: the shard's result.json, the merge's output
# (sprt_merge.py merge: its summary and merged.json) and the shard's folder (the shard-* artifact). The
# watcher must also have uploaded several records, the last one final.
#
#   bash tools/cloud/test_shard_progress.sh
#       a fake fastchess that plays nothing (deterministic output, a game every 50 ms): every file of the
#       shard's folder byte for byte
#   bash tools/cloud/test_shard_progress.sh --real FORK FASTCHESS BOOK [NODES] [GAMES]
#       real games between two copies of FORK at NODES nodes per move (default 4000; GAMES default 12,
#       concurrency 1, so the games are deterministic): result.json and the merge byte for byte, the PGN and
#       the fastchess log byte for byte after their clock and duration fields are masked (they differ between
#       any two runs: shown by a third run without the watcher, which must differ from the first only there)
#
# Each fault makes the test fail (the checker can fail), done by the stand-in upload: FAULT=write-out writes
# a file into the shard's folder, FAULT=append-pgn appends to its PGN, FAULT=edit-result changes one count in
# its result.json once the shard has ended. Uses python3, or $PYTHON if set.
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
py=${PYTHON:-}
if [ -z "$py" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null && "$c" -c 'pass' 2>/dev/null; then py=$(command -v "$c"); break; fi
  done
fi
[ -n "$py" ] || { echo "test_shard_progress.sh: no python found" >&2; exit 1; }
mkdir -p "$tmp/bin"
printf '#!/bin/sh\nexec "%s" -B "$@"\n' "$py" >"$tmp/bin/python3"  # run_shard.sh calls python3
chmod +x "$tmp/bin/python3"
export PATH="$tmp/bin:$PATH"

mode=fake
if [ "${1:-}" = --real ]; then
  mode=real fork=${2:?--real FORK FASTCHESS BOOK [NODES] [GAMES]} fastchess=${3:?} book=${4:?}
  nodes=${5:-4000} games=${6:-12}
  for f in "$fork" "$fastchess" "$book"; do [ -e "$f" ] || { echo "test_shard_progress.sh: no $f" >&2; exit 2; }; done
  cp "$fork" "$tmp/base" && cp "$fork" "$tmp/test" && chmod +x "$tmp/base" "$tmp/test"
  opts=(--base-opts "nodes=$nodes" --test-opts "nodes=$nodes" --tc 600+6 --concurrency 1 --games "$games")
else
  # Fake fastchess: writes the "Finished game" lines fastchess writes for the shard's games, a pair every
  # 100 ms, and a PGN; no engine runs.
  cat >"$tmp/fastchess" <<'EOF'
#!/usr/bin/env bash
rounds=0 pgn=
while [ $# -gt 0 ]; do
  [ "$1" = -rounds ] && rounds=$2
  case $1 in file=*.pgn) pgn=${1#file=} ;; esac
  shift
done
for k in $(seq 1 "$rounds"); do
  case $((k % 3)) in
    0) r1='1-0 {White mates}' r2='1/2-1/2 {Draw by 3-fold repetition}' ;;
    1) r1='1/2-1/2 {Draw by adjudication}' r2='1/2-1/2 {Draw by adjudication}' ;;
    2) r1='0-1 {Black mates}' r2='1-0 {White mates}' ;;
  esac
  echo "Finished game $((2 * k - 1)) (test vs base): $r1"
  echo "Finished game $((2 * k)) (base vs test): $r2"
  printf '[Round "%s"]\n\n1. e4 *\n\n' "$k" >>"$pgn"
  sleep 0.1
done
EOF
  chmod +x "$tmp/fastchess"
  fastchess=$tmp/fastchess
  printf '#!/bin/sh\n' >"$tmp/base" && printf '#!/bin/sh\n' >"$tmp/test" && chmod +x "$tmp/base" "$tmp/test"
  echo 'a book line (the fake fastchess reads no book)' >"$tmp/book.epd"
  book=$tmp/book.epd games=40
  opts=(--tc 8+0.08 --concurrency 2 --games "$games")
fi

# The stand-in upload: copies the record it is given into $tmp/sent (and, with FAULT, does the harm).
cat >"$tmp/upload.sh" <<'EOF'
#!/usr/bin/env bash
n=$(ls "$SENT" | wc -l)
cp "$2" "$SENT/$(printf %03d "$n")-$1.json"
case ${FAULT:-} in
  write-out) echo x >"$SHARD_OUT/progress.json" ;;
  append-pgn) [ "$n" = 2 ] && echo '[Event "fault"]' >>"$SHARD_OUT/games.pgn" ;;
  edit-result)
    [ "$n" = 2 ] && (
      until grep -q '"status": "done"' "$SHARD_OUT/result.json" 2>/dev/null; do sleep 0.05; done
      sed -i 's/"abnormal": 0/"abnormal": 1/' "$SHARD_OUT/result.json"
    ) </dev/null >/dev/null 2>&1 &
    ;;
esac
exit 0
EOF
chmod +x "$tmp/upload.sh"

shard() {  # label: the same shard (stage 1, shard 2 of 4) into $tmp/<label>/out
  FORK_SHARD_INTERVAL=1 bash "$here/run_shard.sh" --base "$tmp/base" --test "$tmp/test" --fastchess "$fastchess" \
    --book "$book" --shard 2 --shards 4 --stage 1 --hash 16 --out "$tmp/$1/out" "${opts[@]}" \
    --meta base=b0 --meta test=t0 --meta runner=test >"$tmp/$1.txt" 2>&1
}
merge() {  # label: the merge of that shard alone, as the workflow's merge job and the driver run it
  (cd "$tmp/$1" && python3 "$here/sprt_merge.py" merge out/result.json --elo0 0 --elo1 5 --json merged.json \
    >summary.txt 2>&1)
}
meta=(--stage 1 --shard 2 --shards 4 --games-planned "$games" --run-id 1 --base b0 --test t0)

# Without the watcher.
mkdir -p "$tmp/alone"
shard alone
check "alone: the shard ran" grep -q '"status": "done"' "$tmp/alone/out/result.json"
merge alone

# With it, as the workflow runs it: started first, in the background, then the games, then finish.
mkdir -p "$tmp/with" "$tmp/sent"
SENT=$tmp/sent SHARD_OUT=$tmp/with/out python3 "$here/shard_progress.py" watch --log "$tmp/with/out/fastchess.log" \
  --dir "$tmp/progress" --name progress-1-2 --upload "bash $tmp/upload.sh" --every-games 4 --every-seconds 3600 \
  --poll 0.1 "${meta[@]}" >"$tmp/watch.txt" 2>&1 &
watcher=$!
shard with
python3 "$here/shard_progress.py" finish --log "$tmp/with/out/fastchess.log" --dir "$tmp/progress" \
  --result "$tmp/with/out/result.json" --wait 20 "${meta[@]}" >>"$tmp/watch.txt" 2>&1
wait "$watcher"
merge with

uploads=$(ls "$tmp/sent" | wc -l)
check "the watcher uploaded the start and at least one record while the games ran ($uploads)" [ "$uploads" -ge 2 ]
check "the final record is final, with the shard's status" python3 -c '
import json, sys; r = json.load(open(sys.argv[1])); sys.exit(not (r["state"] == "final" and r["shard_status"] == "done"))' \
  "$tmp/progress/progress.json"
check "no record is called result.json" bash -c "! find '$tmp/sent' '$tmp/progress' -name result.json | grep -q ."
check "result.json: byte for byte" cmp "$tmp/alone/out/result.json" "$tmp/with/out/result.json"
check "the merge's summary: byte for byte" cmp "$tmp/alone/summary.txt" "$tmp/with/summary.txt"
check "merged.json: byte for byte" cmp "$tmp/alone/merged.json" "$tmp/with/merged.json"
files() { (cd "$1" && find . -type f | sort); }
check "the shard's folder: the same files" [ "$(files "$tmp/alone/out")" = "$(files "$tmp/with/out")" ]

if [ "$mode" = fake ]; then
  check "the shard's folder: every file byte for byte" diff -r "$tmp/alone/out" "$tmp/with/out"
else
  # Clock fields only: fastchess's "Total Time" line; the PGN's Date, GameDuration, GameStartTime and
  # GameEndTime tags and each move's thinking time (the "0.744s" of {+0.28/19 0.744s}), its movetext lines
  # joined first (a longer time can move a line break). Scores, depths, moves, results and reasons stay.
  mask() {
    python3 - "$1" <<'EOF'
import re, sys
text = open(sys.argv[1], encoding='utf-8').read()
text = re.sub(r'(?m)^Total Time: .*$', 'Total Time: X', text)
text = re.sub(r'(?m)^\[(Date|GameDuration|GameStartTime|GameEndTime) "[^"]*"\]$', r'[\1 "X"]', text)
out = []
for block in re.split(r'\n\n+', text):
    if sys.argv[1].endswith('.pgn') and not block.startswith('['):  # a PGN's movetext
        block = re.sub(r'(\d+\.\d+)s(?=[,}])', 'Xs', block.replace('\n', ' '))
    out.append(block)
print('\n\n'.join(out))
EOF
  }
  mkdir -p "$tmp/alone2"
  shard alone2
  for f in games.pgn fastchess.log; do
    mask "$tmp/alone/out/$f" >"$tmp/alone/$f.masked"
    mask "$tmp/alone2/out/$f" >"$tmp/alone2/$f.masked"
    mask "$tmp/with/out/$f" >"$tmp/with/$f.masked"
    check "$f: two runs without the watcher are equal once masked (the mask hides only timing)" \
      cmp "$tmp/alone/$f.masked" "$tmp/alone2/$f.masked"
    check "$f: byte for byte once masked" cmp "$tmp/alone/$f.masked" "$tmp/with/$f.masked"
  done
  check "result.json: a second run without the watcher is byte for byte the first (the games are deterministic)" \
    cmp "$tmp/alone/out/result.json" "$tmp/alone2/out/result.json"
  check "games were played ($(grep -c '^Finished game' "$tmp/alone/out/fastchess.log"))" \
    [ "$(grep -c '^Finished game' "$tmp/alone/out/fastchess.log")" -ge 4 ]
fi
[ "$failures" = 0 ] || { echo "--- watcher"; cat "$tmp/watch.txt"; echo "--- shard"; tail -5 "$tmp/with.txt"; }
echo "${failures} failure(s)"
exit $((failures > 0))
