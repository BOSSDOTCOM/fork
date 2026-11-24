#!/usr/bin/env bash
# Idea 178 (H512+PP+M, architecture 12): its training path checked locally, from r3kr1's float weights (round 3
# session A's avg-kr1/weights.bin and the trainer's own quantised.bin of them). Without --features cuda bullet runs
# on a mock device: graphs are built and lowered (forward and backward), but nothing is computed, so the trainer's
# float outputs are checked on Kaggle (the smoke, then the session's parity-trainer files), not here.
#   1. fork-train check of h512ppm: its quantised file reads as tools/nnue/h512ppm.json;
#   2. the feature leg (fork-train features against reference.py features) on the parity positions;
#   3. the graph lowers on the device: eval reaches the mock runtime (no IR error), train reaches its gradient step
#      (no CompilingBackwards error);
#   4. the warm start (extend_weights.py --arch h512ppm), in the reference: r3kr1's session quantised file converted
#      at S = 89 and clamped is nets/r3kr1.fnet; the reference's redo of bullet's save list on r3kr1's weights is the
#      session's quantised file (legs, h512pp); the warm start's R-float equals r3kr1's at every parity position, and
#      its saved tensors (R-quant) converted are r3kr1's converted file laid out as architecture 12
#      (extend_weights.mover_net), byte for byte, before the clamp; clamped, nets/r3kr1.fnet laid out as 12;
#   5. a seeded block (m0w random): R-quant converted and clamped, for the engine's netcheck (check_engine.sh).
# Git Bash; the trainer runs in WSL (Ubuntu).
set -u
M=$(cygpath -m ~/fork-runners/scratch-i178m)  # archive: was a literal /c/ path
R=$M/wt
W=$M/work
PY=~/fork/.venv/Scripts/python.exe
T=$R/tools/nnue
SRC=$(cygpath -m ~/fork-data/r3/out-a/result/avg-kr1)
VAL=$(cygpath -m ~/fork-data/8c/val/bl-g4s2-val.vf)
EPD=$R/tests/nnue/parity.epd
mkdir -p "$W"
wslp() { local p; p=$(cygpath -u "$1"); echo "/mnt/c${p#/c}"; }
ft() { MSYS_NO_PATHCONV=1 wsl -d Ubuntu -- "$(wslp ~/fork-runners/scratch-r3kr4)/target/release/fork-train" "$@"; }
TABLE=$("$PY" -I -c "import json,sys; print(','.join(map(str, json.load(open(sys.argv[1]))['table'])))" "$T/h512pp.json" | tr -d '\r')
fail=0
ok() { echo "PASS $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== 1. check"
rm -rf "$W/check-h512ppm"
ft check --arch h512ppm --buckets "$TABLE" --out "$(wslp "$W/check-h512ppm")" | tail -1
"$PY" -I -c "
import sys; sys.path.insert(0, sys.argv[1]); import netformat
netformat.read_quantised(open(sys.argv[2], 'rb').read(), netformat.layout(sys.argv[3])); print('read')" \
  "$T" "$W/check-h512ppm/quantised.bin" "$T/h512ppm.json" | grep -q read && ok "check: quantised.bin reads as h512ppm.json" ||
  bad "check: quantised.bin does not read as h512ppm.json"

echo "== 2. feature leg"
ft features --arch h512ppm --buckets "$TABLE" --epd "$(wslp "$EPD")" > "$W/features-h512ppm.txt"
"$PY" -I "$T/reference.py" features --rust "$W/features-h512ppm.txt" --layout "$T/h512ppm.json" && ok "feature leg" ||
  bad "feature leg"

echo "== 3. the graph lowers"
"$PY" -I "$T/extend_weights.py" "$SRC/weights.bin" "$W/m-warm.bin" --arch h512ppm | tail -1
ft eval --arch h512ppm --buckets "$TABLE" --weights "$(wslp "$W/m-warm.bin")" --epd "$(wslp "$EPD")" \
  --out "$(wslp "$W/trainer-m-warm.txt")" > "$W/eval-m.log" 2>&1
grep -q "mock runtime" "$W/eval-m.log" && ! grep -q IRError "$W/eval-m.log" &&
  ok "forward: lowered, stopped at the mock runtime" || bad "forward: $(head -c 300 "$W/eval-m.log")"
rm -rf "$W/run-m"
ft train --arch h512ppm --buckets "$TABLE" --data "$(wslp "$VAL")" --scale 92 --result-weight 0 \
  --init-weights "$(wslp "$W/m-warm.bin")" --lr 0.001 --batch 1024 --batches 2 --superbatches 1 --seed 3 --threads 2 \
  --id m --out "$(wslp "$W/run-m")" > "$W/train-m.log" 2>&1
grep -q "GradientCalculationError" "$W/train-m.log" && ! grep -q -E "CompilingBackwards|IRError" "$W/train-m.log" &&
  ok "backward: lowered, stopped at the mock runtime's gradient step (the warm start loaded)" ||
  bad "backward: $(head -c 300 "$W/train-m.log")"

echo "== 4. the warm start (reference)"
"$PY" -I "$T/convert.py" "$SRC/quantised.bin" "$W/r3kr1-s89.fnet" --scale 89 --layout "$T/h512pp.json" | tail -1
"$PY" -I "$T/pp_bound.py" "$W/r3kr1-s89.fnet" --clamp "$W/r3kr1-s89-clamped.fnet" | tail -1
cmp -s "$W/r3kr1-s89-clamped.fnet" "$R/nets/r3kr1.fnet" &&
  ok "r3kr1's session quantised file converted at 89 and clamped = nets/r3kr1.fnet" || bad "r3kr1 conversion"
"$PY" -I "$T/reference.py" legs --net "$R/nets/r3kr1.fnet" --weights "$SRC/weights.bin" --quantised "$SRC/quantised.bin" \
  --epd "$EPD" --trainer "$SRC/parity-trainer-kr1-avg.txt" --layout "$T/h512pp.json" > "$W/legs-r3kr1.txt" 2>&1
grep -v "^FAIL net file\|Fork's net file differs" "$W/legs-r3kr1.txt" | grep -q "^FAIL" &&
  bad "r3kr1 legs: $(tr '\n' ' ' < "$W/legs-r3kr1.txt")" ||
  ok "r3kr1: R-quant = the session's quantised file, R-float = the trainer's floats (GPU) within 0.01 cp: $(grep '^{' "$W/legs-r3kr1.txt")"
"$PY" -I - "$T" "$SRC/weights.bin" "$W/m-warm.bin" "$W/r3kr1-s89.fnet" "$W" "$EPD" <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import chess
import convert, extend_weights, models, netformat, reference
f32 = lambda w: {k: [models.to_f32(x) for x in v] for k, v in w.items()}  # noqa: E731
kr = f32(netformat.read_weights_bin(open(sys.argv[2], 'rb').read()))
wm = f32(netformat.read_weights_bin(open(sys.argv[3], 'rb').read()))
a9, a12 = models.Arch('h512pp', table=netformat.layout(sys.argv[1] + '/h512pp.json')['table']), None
desc = netformat.layout(sys.argv[1] + '/h512ppm.json')
a12 = models.Arch('h512ppm', desc['regions'], desc['table'])
fens = reference.read_fens(sys.argv[6])
same = sum(models.r_float(a12, wm, chess.Board(f)) == models.r_float(a9, kr, chess.Board(f)) for f in fens)
movers = sum(bool(models.mover_squares(chess.Board(f))) for f in fens)
print(f'R-float: the warm start equals r3kr1 at {same} of {len(fens)} parity positions ({movers} with a mover\'s '
      f'exposed piece)')
saved = models.saved_tensors(a12, wm)
q = {t['name']: saved[t['name']][1] for t in desc['quantised']}
qbin = netformat.write_quantised(q, desc)
Path(sys.argv[5], 'm-warm-quantised.bin').write_bytes(qbin)
net = convert.convert(qbin, desc, 89)
Path(sys.argv[5], 'm-warm-s89.fnet').write_bytes(net)
ok = extend_weights.mover_net(open(sys.argv[4], 'rb').read()) == net
print('quantised identity', 'same' if ok else 'differ')
sys.exit(0 if ok and same == len(fens) else 1)
EOF
[ $? = 0 ] && ok "warm start: R-float = r3kr1's everywhere; R-quant converted = r3kr1's converted laid out as 12, byte for byte" ||
  bad "warm start identity"
"$PY" -I "$T/pp_bound.py" "$W/m-warm-s89.fnet" --clamp "$W/m-warm-clamped.fnet" | tail -1
"$PY" -I "$T/extend_weights.py" "$R/nets/r3kr1.fnet" "$W/r3kr1-m0.fnet" --arch h512ppm | tail -1
cmp -s "$W/m-warm-clamped.fnet" "$W/r3kr1-m0.fnet" &&
  ok "warm start converted and clamped = nets/r3kr1.fnet laid out as architecture 12 (zero block)" || bad "warm clamp"
# The legs on the converted file before the clamp (R-quant is the unclamped file); then the parity file (R-int) of
# the clamped net for the engine's netcheck (its quantization leg fails by the clamp, as expected).
"$PY" -I "$T/reference.py" legs --net "$W/m-warm-s89.fnet" --weights "$W/m-warm.bin" \
  --quantised "$W/m-warm-quantised.bin" --epd "$EPD" --layout "$T/h512ppm.json" --max-loss 21 --p99-loss 16 \
  > "$W/legs-m-warm.txt" 2>&1 && ok "warm legs: $(grep '^{' "$W/legs-m-warm.txt")" ||
  bad "warm legs: $(tr '\n' ' ' < "$W/legs-m-warm.txt")"
"$PY" -I "$T/reference.py" legs --net "$W/m-warm-clamped.fnet" --weights "$W/m-warm.bin" \
  --quantised "$W/m-warm-quantised.bin" --epd "$EPD" --layout "$T/h512ppm.json" --out "$W/m-warm.parity" > /dev/null 2>&1

echo "== 5. a seeded block (for the engine)"
"$PY" -I - "$T" "$W/m-warm.bin" "$W/m-block.bin" "$W" <<'EOF'
import random, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import convert, models, netformat
w = netformat.read_weights_bin(open(sys.argv[2], 'rb').read())
rng = random.Random(178)
w['m0w'] = [models.to_f32(rng.uniform(-0.4, 0.4)) for _ in range(64 * 650)]
open(sys.argv[3], 'wb').write(netformat.write_weights_bin(w))
desc = netformat.layout(sys.argv[1] + '/h512ppm.json')
a12 = models.Arch('h512ppm', desc['regions'], desc['table'])
saved = models.saved_tensors(a12, {k: [models.to_f32(x) for x in v] for k, v in w.items()})
qbin = netformat.write_quantised({t['name']: saved[t['name']][1] for t in desc['quantised']}, desc)
Path(sys.argv[4], 'm-block-quantised.bin').write_bytes(qbin)
Path(sys.argv[4], 'm-block-s89.fnet').write_bytes(convert.convert(qbin, desc, 89))
print('seeded block written')
EOF
"$PY" -I "$T/pp_bound.py" "$W/m-block-s89.fnet" --clamp "$W/m-block.fnet" | tail -1
"$PY" -I "$T/reference.py" legs --net "$W/m-block-s89.fnet" --weights "$W/m-block.bin" \
  --quantised "$W/m-block-quantised.bin" --epd "$EPD" --layout "$T/h512ppm.json" > "$W/legs-m-block.txt" 2>&1 &&
  ok "block legs: $(grep '^{' "$W/legs-m-block.txt")" || bad "block legs: $(tr '\n' ' ' < "$W/legs-m-block.txt")"
"$PY" -I "$T/reference.py" legs --net "$W/m-block.fnet" --weights "$W/m-block.bin" --quantised "$W/m-block-quantised.bin" \
  --epd "$EPD" --layout "$T/h512ppm.json" --out "$W/m-block.parity" > /dev/null 2>&1
"$PY" -I - "$W/m-warm.parity" "$W/m-block.parity" <<'EOF'
import sys
a = [l.rsplit('|', 1)[1].strip() for l in open(sys.argv[1]).readlines()[1:]]
b = [l.rsplit('|', 1)[1].strip() for l in open(sys.argv[2]).readlines()[1:]]
print(f'the seeded block moves R-int at {sum(x != y for x, y in zip(a, b))} of {len(a)} parity positions')
EOF
echo "check_i178.sh: $([ $fail = 0 ] && echo ALL PASSED || echo FAILURES)"
exit $fail
