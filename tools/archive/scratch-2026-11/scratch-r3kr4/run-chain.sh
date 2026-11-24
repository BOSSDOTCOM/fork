#!/usr/bin/env bash
# Bake-off round 3 option (a): the trainer-side chain on the CPU (WSL), for
# H512+PP's warm start from r8brft1's float weights: check (graph and save
# list), the feature leg, the trainer's float evaluation of the parity
# positions (the warm start, and r8brft1's own float weights for comparison),
# and the trainer's quantised file of the warm start (an LR-0 step).
set -u
WIN_HOME=${WIN_HOME:?set WIN_HOME to the Windows home folder as WSL sees it, /mnt/c/Users/<user>}  # archive: was a literal path
S=$WIN_HOME/fork-runners/scratch-r3kr4
W=$S/work/chain
T=$S/target/release/fork-train
R=$S/wt
SRC=$WIN_HOME/fork-data/kaggle/r8b-rft-out/result/avg-rft1/weights.bin
WARM=$S/work/h512pp-warm-r8brft1.bin
DATA=$WIN_HOME/fork-data/kaggle/back-g4b/g4b-w00.vf
BUCKETS=$(python3 -c "import json; print(','.join(map(str, json.load(open('$R/tools/nnue/h512pp.json'))['table'])))")
mkdir -p "$W"
cd "$W" || exit 1
echo "buckets $BUCKETS"
nice "$T" check --arch h512pp --buckets "$BUCKETS" --out "$W/check-h512pp" 2>&1 | tail -1
nice "$T" features --arch h512pp --buckets "$BUCKETS" --epd "$R/tests/nnue/parity.epd" > "$W/features-h512pp.txt" 2>"$W/features-h512pp.err"
echo "features exit $? lines $(wc -l < "$W/features-h512pp.txt")"
nice "$T" eval --arch h512pp --buckets "$BUCKETS" --weights "$WARM" --epd "$R/tests/nnue/parity.epd" --out "$W/trainer-kr4-warm.txt" 2>&1 | tail -2
echo "eval kr4 exit $? lines $(wc -l < "$W/trainer-kr4-warm.txt")"
nice "$T" eval --arch s512pp --buckets "$BUCKETS" --weights "$SRC" --epd "$R/tests/nnue/parity.epd" --out "$W/trainer-r8brft1.txt" 2>&1 | tail -2
echo "eval r8brft1 exit $? lines $(wc -l < "$W/trainer-r8brft1.txt")"
rm -rf "$W/q-kr4"
nice "$T" train --arch h512pp --buckets "$BUCKETS" --data "$DATA" --scale 92 --result-weight 0.5 --init-weights "$WARM" \
  --lr 0 --batch 16384 --batches 1 --superbatches 1 --seed 1 --threads 2 --id q --out "$W/q-kr4" > "$W/q-kr4.log" 2>&1
echo "quantise exit $?"
cmp "$W/q-kr4/q-1/optimiser_state/weights.bin" "$WARM" && echo "LR-0 step left the weights unchanged"
ls -la "$W/q-kr4/q-1/quantised.bin"
