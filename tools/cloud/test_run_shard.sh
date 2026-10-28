#!/usr/bin/env bash
# Dry-run test of tools/cloud/run_shard.sh with a fake fastchess (no engine
# runs, no game is played): what it passes to fastchess, what it records in
# result.json, and its exit status. Uses python3, or $PYTHON if set.
#
#   bash tools/cloud/test_run_shard.sh
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

# python3 for run_shard.sh: $PYTHON, else the first python that runs.
mkdir -p "$tmp/bin"
py=${PYTHON:-}
if [ -z "$py" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null && "$c" -c 'pass' 2>/dev/null; then py=$(command -v "$c"); break; fi
  done
fi
[ -n "$py" ] || { echo "test_run_shard.sh: no python found" >&2; exit 1; }
printf '#!/bin/sh\nexec "%s" -B "$@"\n' "$py" >"$tmp/bin/python3"
chmod +x "$tmp/bin/python3"
export PATH="$tmp/bin:$PATH"

# Fake fastchess: FAKE_FC=full (every pair asked for), crash (2 pairs, then
# SIGSEGV) or fail (2 pairs, then exit 1). Arguments go to $tmp/args.
cat >"$tmp/fastchess" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$FAKE_ARGS"
rounds=0
while [ $# -gt 0 ]; do [ "$1" = -rounds ] && rounds=$2; shift; done
n=$rounds
[ "${FAKE_FC:-full}" = full ] || n=2
for k in $(seq 1 "$n"); do
  echo "Finished game $((2 * k - 1)) (test vs base): 1-0 {White mates}"
  echo "Finished game $((2 * k)) (base vs test): 1/2-1/2 {Draw by 3-fold repetition}"
done
case ${FAKE_FC:-full} in
  crash) kill -SEGV $$ ;;
  fail) exit 1 ;;
esac
exit 0
EOF
chmod +x "$tmp/fastchess"
printf '#!/bin/sh\n' >"$tmp/base" && printf '#!/bin/sh\n' >"$tmp/test" && chmod +x "$tmp/base" "$tmp/test"
echo 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -' >"$tmp/book.epd"
mkdir -p "$tmp/tb" "$tmp/tb-short"
for i in $(seq 1 145); do : >"$tmp/tb/T$i.rtbw"; : >"$tmp/tb/T$i.rtbz"; done
: >"$tmp/tb-short/KPvK.rtbw"

shard() {  # out dir, extra run_shard.sh arguments... ; status in $status
  local out=$1
  shift
  FAKE_ARGS="$tmp/args" FORK_SHARD_INTERVAL=1 bash "$here/run_shard.sh" --base "$tmp/base" --test "$tmp/test" \
    --fastchess "$tmp/fastchess" --book "$tmp/book.epd" --shard 1 --shards 4 --games 10 --tc 8+0.08 \
    --out "$tmp/$out" --concurrency 2 "$@" >"$tmp/$out.txt" 2>&1
  status=$?
}
meta() {  # out dir, key -> value
  "$py" -c 'import json, sys; print(json.load(open(sys.argv[1]))["meta"].get(sys.argv[2], ""))' "$tmp/$1/result.json" "$2"
}
arg() { grep -qx -- "$1" "$tmp/args"; }

# D-2: tables for both engines when --syzygy is given, recorded in the meta.
shard tables --syzygy "$tmp/tb"
check "tables: exit 0" test "$status" = 0
check "tables: SyzygyPath for both engines (-each)" arg "option.SyzygyPath=$(cd "$tmp/tb" && pwd)"
check "tables: meta tables=3-4-5" test "$(meta tables tables)" = 3-4-5
shard notables
check "no tables: exit 0" test "$status" = 0
check "no tables: no SyzygyPath" bash -c "! grep -q SyzygyPath '$tmp/args'"
check "no tables: meta tables=off" test "$(meta notables tables)" = off
shard badtables --syzygy "$tmp/tb-short"
check "an incomplete set is refused" test "$status" = 2

# U-3: the book's name, permutation seed and SHA-256 are in the meta.
check "book: name" test "$(meta notables book)" = book.epd
check "book: no seed for a book in file order" test "$(meta notables book_seed)" = none
check "book: SHA-256" test "$(meta notables book_sha)" = "$(sha256sum "$tmp/book.epd" | cut -d' ' -f1)"
cp "$tmp/book.epd" "$tmp/UHO.shuffled-42.epd"
shard seeded --book "$tmp/UHO.shuffled-42.epd"
check "book: seed from a shuffled book's name" test "$(meta seeded book_seed)" = 42

echo "${failures} failure(s)"
exit $((failures > 0))
