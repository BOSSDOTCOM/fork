#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# A retrain candidate's integrity gates (retrain 8b's gates.sh, moved into the repository; bug review 2026-11-11,
# T2, owner the same day: the quantization-loss limits now gate the shipped, clamped net, and the clamp count has
# a limit).
#
#   tools/nnue/gates.sh NAME DIR TRAINER_FILE CONTROL_FNET VAL_FILE OUT
#
# DIR holds bullet's weights.bin and quantised.bin, TRAINER_FILE the trainer's float outputs on
# tests/nnue/parity.epd, CONTROL_FNET the net whose mean |eval| the scale is matched to, VAL_FILE the validation
# positions for that match. Steps: convert at the trained scale (TRAINED_S, 92); match the scale to the
# control's mean |eval| on 4,000 VAL positions; convert at the matched S; the unclamped net's legs; the link clamp
# (tools/nnue/pp_bound.py) under the clamp-count limit, and its re-check (nothing left to clamp); the clamped
# net's legs (its parity file); the scale re-match (reported); the endgame check against the control (reported);
# netcheck of the clamped net. Writes OUT/NAME/{cand.fnet,cand.parity,gates.json, the legs, endgame and netcheck
# outputs}; exit 0 only if every gate passes:
# - the unclamped net: every leg passes (R-quant equals bullet's quantised.bin and the net file, R-float equals
#   the trainer, the quantization loss within MAX_LOSS / P99_LOSS cp, max / p99);
# - the clamp: at most MAX_CLAMPED link weights clamped; the clamped net has none left over the bound;
# - the clamped net, the one shipped: the trainer leg and the quantization loss within MAX_LOSS / P99_LOSS; its
#   only allowed failure is "Fork's net file differs from R-quant", and only when a weight was clamped (the
#   clamped weights are exactly where it differs);
# - netcheck exact on the clamped net's own parity file.
#
# MAX_CLAMPED is 8 (owner's decision of 2026-11-11 asked for a small limit with a recorded reason): the link
# weights clamped in every gate run on record were 0 to 5 of 311,296 (the shipped nets S512ppr2 2, S512ppr3,
# r8btd90 and r8brft1 1; the most, 5, the from-scratch arm r8bscr), so 8 passes every net so far with room for
# that spread and fails a net whose links outgrow the reader's bound systematically, which would need a look
# (the clamp then changes evaluations beyond a stray weight).
#
# Environment: FORK_PYTHON (default the repository's .venv, else python3), FORK_BIN (the engine for netcheck,
# default build/clang-release/fork[.exe]), FORK_SYZYGY (default ~/fork-data/syzygy/3-4-5), LAYOUT (default
# tools/nnue/s512pp.json), TRAINED_S (92), MAX_LOSS (21), P99_LOSS (16), MAX_CLAMPED (8).
set -uo pipefail
[ $# -eq 6 ] || { sed -n '7,7p' "$0" >&2; exit 2; }
R=$(cd "$(dirname "$0")/../.." && pwd)
. "$R/tools/jobs/paths.sh" || exit 2
PY=${FORK_PYTHON:-}
if [ -z "$PY" ]; then
  for c in "$R/.venv/Scripts/python.exe" "$R/.venv/bin/python" python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c pass >/dev/null 2>&1; then PY=$c; break; fi
  done
fi
[ -n "$PY" ] || { echo "gates.sh: no Python" >&2; exit 2; }
BIN=${FORK_BIN:-$R/build/clang-release/fork}
[ -x "$BIN" ] || [ ! -x "$BIN.exe" ] || BIN=$BIN.exe
MAX_LOSS=${MAX_LOSS:-21} P99_LOSS=${P99_LOSS:-16} MAX_CLAMPED=${MAX_CLAMPED:-8} TRAINED_S=${TRAINED_S:-92}
# Every path in the form the program it goes to takes (DESIGN.md section 1).
p() { fork_path_for "$PY" "$1"; }
NAME=$1
O=$(p "$2") TR=$(p "$3") CTRL=$(p "$4") VAL=$(p "$5")
W=$6/$NAME
L=$(p "${LAYOUT:-$R/tools/nnue/s512pp.json}")
SYZ=$(p "${FORK_SYZYGY:-$HOME/fork-data/syzygy/3-4-5}")
T=$(p "$R/tools/nnue")
rm -rf "$W"; mkdir -p "$W"
WP=$(p "$W")
fail=0
gate() { echo "GATE FAILED: $*"; fail=1; }
legs() {  # net parity-out output-file
  nice "$PY" -I "$T/reference.py" legs --net "$1" --weights "$O/weights.bin" --quantised "$O/quantised.bin" \
    --epd "$(p "$R/tests/nnue/parity.epd")" --trainer "$TR" --layout "$L" --max-loss "$MAX_LOSS" \
    --p99-loss "$P99_LOSS" --out "$2" >"$3" 2>&1
}
match() { nice "$PY" -I "$T/match_scale.py" --control "$CTRL" --control-layout "$L" --net "$1" --layout "$L" \
  "$VAL" --positions 4000 2>&1 | tail -1; }
echo "== $NAME"
nice "$PY" -I "$T/convert.py" "$O/quantised.bin" "$WP/s$TRAINED_S.fnet" --scale "$TRAINED_S" --layout "$L" | tail -1 ||
  gate "conversion at $TRAINED_S"
m=$(match "$WP/s$TRAINED_S.fnet"); echo "scale match at $TRAINED_S: $m"
S=$("$PY" -I -c "import json,sys; print(json.loads(sys.argv[1])['matched_scale'])" "$m" | tr -d '\r') ||
  { echo "gates.sh: no matched scale"; exit 1; }
nice "$PY" -I "$T/convert.py" "$O/quantised.bin" "$WP/s$S.fnet" --scale "$S" --layout "$L" | tail -1 ||
  gate "conversion at $S"
legs "$WP/s$S.fnet" "$WP/s$S.parity" "$W/legs-unclamped.txt" || gate "the unclamped net's legs (legs-unclamped.txt)"
echo "unclamped S = $S: $(grep -v '^$' "$W/legs-unclamped.txt" | tail -3 | tr '\n' ' ')"
nice "$PY" -I "$T/pp_bound.py" "$WP/s$S.fnet" --clamp "$WP/cand.fnet" --max-clamped "$MAX_CLAMPED" >"$W/clamp.txt" 2>&1 ||
  gate "the clamp count (clamp.txt)"
cat "$W/clamp.txt"
clamped=$("$PY" -I -c "import json,sys; print(json.loads(sys.argv[1])['clamped'])" "$(tail -1 "$W/clamp.txt")" | tr -d '\r') ||
  { echo "gates.sh: no clamp count"; exit 1; }
nice "$PY" -I "$T/pp_bound.py" "$WP/cand.fnet" --max-clamped 0 >"$W/clamp-recheck.txt" 2>&1 ||
  gate "the clamped net still has link weights over the bound (clamp-recheck.txt)"
echo "clamped, bound re-check: $(head -1 "$W/clamp-recheck.txt")"
legs "$WP/cand.fnet" "$WP/cand.parity" "$W/legs-clamped.txt"  # writes cand.parity, the shipped net's
echo "clamped S = $S: $(grep -v '^$' "$W/legs-clamped.txt" | tail -3 | tr '\n' ' ')"
allowed="FAIL quantization leg: Fork's net file differs from R-quant"
other=$(grep '^FAIL' "$W/legs-clamped.txt" | grep -vxF "$allowed")
[ -z "$other" ] || gate "the clamped net's legs: $(echo "$other" | head -3 | tr '\n' ' ')"
[ "$clamped" -gt 0 ] || ! grep -qxF "$allowed" "$W/legs-clamped.txt" ||
  gate "the clamped net differs from R-quant with no weight clamped"
grep -q '"loss_max"' "$W/legs-clamped.txt" || gate "the clamped net's legs printed no losses"
echo "scale re-match: $(match "$WP/cand.fnet")"
nice "$PY" -I "$T/endgame_check.py" "$(p "$R")" "$SYZ" "$WP/cand.fnet=$L" "$CTRL=$L" >"$W/endgame.txt" 2>&1
echo "endgame check: $(tail -2 "$W/endgame.txt" | tr '\n' ' ')"
"$BIN" netcheck "$(fork_path_for "$BIN" "$W/cand.parity")" "$(fork_path_for "$BIN" "$W/cand.fnet")" >"$W/netcheck.txt" 2>&1 ||
  gate "netcheck (netcheck.txt)"
echo "netcheck: $(tail -2 "$W/netcheck.txt" | tr '\n' ' ')"
grep -q ' 0 mismatches' "$W/netcheck.txt" || gate "netcheck is not exact"
echo "cand.fnet sha256 $(sha256sum "$W/cand.fnet" | cut -c1-64)"
"$PY" -I - "$WP" "$S" "$fail" "$clamped" "$MAX_CLAMPED" <<'EOF'
import json, sys
w, s, fail, clamped, limit = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
stats = [json.loads(x) for x in open(f'{w}/legs-clamped.txt') if x.startswith('{')]
json.dump({'scale': s, 'gates_failed': bool(fail), 'clamped': clamped, 'max_clamped': limit,
           'clamped_legs': stats[-1] if stats else None, 'endgame': open(f'{w}/endgame.txt').read()[-600:],
           'netcheck': open(f'{w}/netcheck.txt').read()[-300:], 'legs': open(f'{w}/legs-clamped.txt').read()[-600:]},
          open(f'{w}/gates.json', 'w'), indent=1)
EOF
[ "$fail" = 0 ] && echo "gates passed" || echo "gates FAILED"
exit $fail
