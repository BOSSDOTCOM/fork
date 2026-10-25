#!/usr/bin/env bash
# Performance gate for one deliverable (DESIGN.md §5.2, Quality control 2), in
# WSL. Usage:
#   tools/perf_gate.sh NEW_COMMIT [OLD_COMMIT]
# Without OLD: an A/A noise run of NEW against a copy of itself (the noise
# floor). With OLD: bench/ab_search.py with A = OLD, B = NEW (search nps).
# Then one perf profile of `fork bench` for NEW: the top 15 functions by self
# time, summed per containing function by tools/perf_symbols.py (WSL's perf is
# built without libelf and prints raw addresses). Results go into
# docs/history/phase-3/perf-log.md by hand.
set -euo pipefail
here=$(dirname "$0")
repo=$(cd "$here/.." && pwd)
new=$(bash "$here/perf_build.sh" "$1")
newc=$(git -C "$repo" rev-parse --short=7 "$1")
"$new" version | tail -n 1
if [ $# -ge 2 ]; then
  old=$(bash "$here/perf_build.sh" "$2")
  oldc=$(git -C "$repo" rev-parse --short=7 "$2")
  python3 -I "$repo/bench/ab_search.py" "$old" "$new" --a-variant baseline --a-commit "$oldc" \
    --b-variant baseline --b-commit "$newc" --rounds 6
else
  cp "$new" "$new-copy"
  python3 -I "$repo/bench/ab_search.py" "$new" "$new-copy" --a-variant baseline --a-commit "$newc" \
    --b-variant baseline --b-commit "$newc" --allow-identical --rounds 6
fi
echo "--- perf profile of fork bench ($newc), top 15 by self time"
cd "$(dirname "$new")"
perf record -q -o perf.data -- "$new" bench >/dev/null 2>&1
perf report -i perf.data --stdio --no-children --sort symbol 2>/dev/null | python3 -I "$here/perf_symbols.py" "$new" 15
