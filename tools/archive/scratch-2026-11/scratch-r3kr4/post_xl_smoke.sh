#!/usr/bin/env bash
# The x_lower smoke session's output, checked locally (Git Bash): the summary, the warm start's trainer files against
# the reference (its quantised file converted with s512ppxl.json = r8brft1's laid out by exposure_net, before any
# clamp), and xl1's window average through conversion, the link clamp, the legs and the architecture 10 engine's
# netcheck.
set -u
S=$(cygpath -m ~/fork-runners/scratch-r3kr4)  # archive: was a literal /c/ path
R=$S/wt
O=$S/xl-smoke-out/result
W=$S/work/post-xl
PY=$R/.venv/Scripts/python.exe
T=$R/tools/nnue
BIN=$R/build/xl-rel/fork.exe
mkdir -p "$W"
"$PY" -I - "$O/bakeoff_r3.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
print('head', d.get('head')); print('build', d.get('build')); print('pip', d.get('pip', {}).get('rc'))
print('inputs ok', d['inputs']['ok'], d['inputs']['files_per_arm'], 'unresolved', d['inputs']['unresolved'])
print('source', d.get('source_weights'), 'warm start', d.get('warm_start'))
for k, v in d.get('checks', {}).items():
    if isinstance(v, dict):
        v = {x: y for x, y in v.items() if x in ('rc', 'leg_rc', 'loss', 'unchanged', 'out')}
    print(' ', k, str(v)[:220])
for arm, r in d.get('runs', {}).items():
    print(arm, {k: r.get(k) for k in ('rc', 'seconds', 'initial_loss', 'laps', 'lap_mean_after_first', 'window_mean',
                                     'error')})
    print('  curve', r.get('val_curve'))
print('validity', json.dumps(d.get('validity'))[:700])
EOF
"$PY" -I "$T/convert.py" "$O/warm/source-quantised.bin" "$W/source-s88.fnet" --scale 88 --layout "$T/s512pp.json" | tail -1
"$PY" -I "$T/convert.py" "$O/warm/exposure-quantised.bin" "$W/warm-s88.fnet" --scale 88 --layout "$T/s512ppxl.json" | tail -1
"$PY" -I -c "
import sys; sys.path.insert(0, sys.argv[1]); import extend_weights
a = open(sys.argv[2], 'rb').read(); b = open(sys.argv[3], 'rb').read()
print('warm start: the trainer quantised file = exposure_net(r8brft1 trainer quantised), byte for byte:', extend_weights.exposure_net(a) == b)
" "$T" "$W/source-s88.fnet" "$W/warm-s88.fnet"
"$PY" -I "$T/pp_bound.py" "$W/warm-s88.fnet" --clamp "$W/warm-s88-clamped.fnet" | tail -1
cmp "$W/warm-s88-clamped.fnet" "$R/nets/r8brft1xl.fnet" && echo "warm start: converted and clamped = nets/r8brft1xl.fnet"
"$PY" -I "$T/extend_weights.py" "$(cygpath -m ~)"/fork-data/kaggle/r8b-rft-out/result/avg-rft1/weights.bin "$W/xl-warm.bin" --arch s512ppxl | tail -1
"$PY" -I "$T/reference.py" legs --net "$R/nets/r8brft1xl.fnet" --weights "$W/xl-warm.bin" \
  --quantised "$O/warm/exposure-quantised.bin" --epd "$R/tests/nnue/parity.epd" --trainer "$O/warm/parity-trainer-exposure.txt" \
  --layout "$T/s512ppxl.json" --max-loss 21 --p99-loss 16 > "$W/legs-warm.txt" 2>&1
echo "warm legs: $(tr '\n' ' ' < "$W/legs-warm.txt")"
q=$O/avg-xl1/quantised.bin; w=$O/avg-xl1/weights.bin; tr=$(ls "$O"/avg-xl1/parity-trainer-*.txt | head -1)
"$PY" -I "$T/convert.py" "$q" "$W/xl1-s92.fnet" --scale 92 --layout "$T/s512ppxl.json" | tail -1
"$PY" -I "$T/pp_bound.py" "$W/xl1-s92.fnet" --clamp "$W/xl1-cand.fnet" --max-clamped 8 | tail -1
"$PY" -I "$T/reference.py" legs --net "$W/xl1-cand.fnet" --weights "$w" --quantised "$q" --epd "$R/tests/nnue/parity.epd" \
  --trainer "$tr" --layout "$T/s512ppxl.json" --max-loss 21 --p99-loss 16 --out "$W/xl1-cand.parity" > "$W/legs-xl1.txt" 2>&1
echo "xl1 legs: $(tr '\n' ' ' < "$W/legs-xl1.txt")"
"$BIN" netcheck "$W/xl1-cand.parity" "$W/xl1-cand.fnet"
"$PY" -I -c "
import struct, sys
d = open(sys.argv[1], 'rb').read(); H = 512; at = 192
w = struct.unpack_from(f'<{2016 * H}h', d, at)
x = w[768 * H:(768 + 640) * H]
print('xl1 exposure rows nonzero:', sum(1 for v in x if v), 'of', len(x))
" "$W/xl1-cand.fnet"
