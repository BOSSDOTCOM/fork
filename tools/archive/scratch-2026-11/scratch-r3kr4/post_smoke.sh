#!/usr/bin/env bash
# The smoke session's output, checked locally (Git Bash): the summary, the warm start's trainer files against the
# reference, and kr1's (and pp1's) window average through conversion, the link clamp, the legs and the engine's
# netcheck (an architecture 9 build for kr1, the default build for pp1).
set -u
S=$(cygpath -m ~/fork-runners/scratch-r3kr4)  # archive: was a literal /c/ path
R=$S/wt
O=$S/smoke-out/result
W=$S/work/post
PY=$R/.venv/Scripts/python.exe
T=$R/tools/nnue
mkdir -p "$W"
"$PY" -I - "$O/bakeoff_r3.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
print('head', d.get('head')); print('build', d.get('build')); print('pip', d.get('pip', {}).get('rc'))
print('inputs ok', d['inputs']['ok'], 'files', d['inputs']['files_per_arm'], 'unresolved', d['inputs']['unresolved'],
      'mismatches', d['inputs']['mismatches'][:5])
print('source', d.get('source_weights'), 'warm start', d.get('warm_start'))
c = d.get('checks', {})
for k in ('check-h512pp', 'check-s512pp'):
    print(k, (c.get(k) or {}).get('rc'), (c.get(k) or {}).get('out', '')[-120:].strip())
print('reference', c.get('reference'), 'warm_float', c.get('warm_float'), 'warm_float_ok', c.get('warm_float_ok'))
print('quantise', {k: (c.get(k) or {}).get('unchanged') for k in ('quantise_source', 'quantise_warm')},
      'quantised_identity', c.get('quantised_identity'), c.get('quantised_identity_tail', '')[-200:])
for arm, r in d.get('runs', {}).items():
    print(arm, {k: r.get(k) for k in ('rc', 'seconds', 'initial_loss', 'positions_per_second', 'laps',
                                     'lap_mean_after_first', 'best_superbatch', 'window_mean', 'error')})
    print('  curve', r.get('val_curve'))
print('validity', json.dumps(d.get('validity'), indent=None)[:900])
off = d.get('offline', {})
for k, v in off.items():
    print('offline', k, {x: (y or {}).get('loss') if isinstance(y, dict) else y for x, y in v.items()}
          if not k.startswith('quantise') else v.get('unchanged'))
EOF
ls -la "$O/warm" "$O/avg-kr1" "$O/avg-pp1" 2>&1 | grep -v '^total'
# The warm start: the trainer's quantised file converted at 88 against the reference's (the pre-clamp file made
# earlier, work/kr4-from-float-s88.fnet), and the trainer's float leg on the warm start's weights.
"$PY" -I "$T/convert.py" "$O/warm/warm-quantised.bin" "$W/warm-s88.fnet" --scale 88 --layout "$T/h512pp.json" | tail -1
cmp "$W/warm-s88.fnet" "$S/work/kr4-from-float-s88.fnet" && echo "warm start: the trainer's quantised file = the reference's (pre-clamp), byte for byte"
"$PY" -I "$T/pp_bound.py" "$W/warm-s88.fnet" --clamp "$W/warm-s88-clamped.fnet" | tail -1
cmp "$W/warm-s88-clamped.fnet" "$R/nets/r8brft1kr4.fnet" && echo "warm start: converted and clamped = nets/r8brft1kr4.fnet"
"$PY" -I "$T/reference.py" legs --net "$R/nets/r8brft1kr4.fnet" --weights "$S/work/h512pp-warm-r8brft1.bin" \
  --quantised "$O/warm/warm-quantised.bin" --epd "$R/tests/nnue/parity.epd" --trainer "$O/warm/parity-trainer-warm.txt" \
  --layout "$T/h512pp.json" --max-loss 21 --p99-loss 16 > "$W/legs-warm.txt" 2>&1
echo "warm legs: $(tr '\n' ' ' < "$W/legs-warm.txt")"
# kr1's and pp1's window averages.
for arm in kr1 pp1; do
  lay=$T/h512pp.json; bin=$R/build/kr4-ff/fork.exe
  [ $arm = pp1 ] && lay=$T/s512pp.json && bin=$R/build/precommit-tree/build/clang-release/fork.exe
  q=$O/avg-$arm/quantised.bin; w=$O/avg-$arm/weights.bin; tr=$(ls "$O"/avg-$arm/parity-trainer-*.txt 2>/dev/null | head -1)
  [ -f "$q" ] || { echo "$arm: no quantised.bin"; continue; }
  "$PY" -I "$T/convert.py" "$q" "$W/$arm-s92.fnet" --scale 92 --layout "$lay" | tail -1
  "$PY" -I "$T/pp_bound.py" "$W/$arm-s92.fnet" --clamp "$W/$arm-cand.fnet" --max-clamped 8 | tail -1
  "$PY" -I "$T/reference.py" legs --net "$W/$arm-cand.fnet" --weights "$w" --quantised "$q" --epd "$R/tests/nnue/parity.epd" \
    --trainer "$tr" --layout "$lay" --max-loss 21 --p99-loss 16 --out "$W/$arm-cand.parity" > "$W/legs-$arm.txt" 2>&1
  echo "$arm legs: $(tr '\n' ' ' < "$W/legs-$arm.txt")"
  "$bin" netcheck "$W/$arm-cand.parity" "$W/$arm-cand.fnet"
done
