#!/usr/bin/env bash
# Idea 178's smoke check (the GPU queue's `require` line after it pushes fork-i178-m-smoke): waits for the session,
# downloads its output to scratch-i178m/smoke-out-<time>, and passes only if
#   - the summary shows SMOKE, ARM_SET M, the commit, the CUDA build rc 0, inputs ok, the source's SHA-256 ok;
#   - fork-train check of h512ppm and h512pp, and the feature legs of both, pass on the GPU build;
#   - the warm start's float loss equals r3kr1's within 1e-6 and its quantised file, converted, is r3kr1's laid out as
#     architecture 12 byte for byte (the kernel's own checks), and the trainer's float outputs of the warm start equal
#     r3kr1's at every parity position;
#   - each arm ran 4 superbatches (rc 0), its superbatch 0 equals the reference within 1e-5, validity ok, both
#     window averages quantised;
#   - mb1's window average (a non-zero block after 4 superbatches): the reference's legs pass with the trainer's float
#     outputs on the parity positions (R-float within 0.01 cp of the GPU's), and an architecture 12 engine's netcheck
#     of it, converted and clamped, is exact; kc1's likewise on the default engine (architecture 9).
# Prints both arms' laps. Exit 0 only if every check passes ("I178 SMOKE PASSED").
set -uo pipefail
M=$(cygpath -m ~/fork-runners/scratch-i178m)  # archive: was a literal path
R=$M/wt
T=$R/tools/nnue
K=~/fork/.venv/Scripts/kaggle.exe
PY=~/fork/.venv/Scripts/python.exe
KID=bossdotcom/fork-i178-m-smoke
OUT=$M/smoke-out-$(date +%Y%m%d-%H%M)
W=$OUT-check
E12=$M/engines/fork-a12.exe   # an architecture 12 build of train/i178-m (r3kr1, zero block)
E9=$M/engines/fork-a9.exe     # an architecture 9 build (r3kr1)
for i in $(seq 1 30); do
  st=$("$K" kernels status "$KID" 2>&1 | tail -1)
  echo "$st" | grep -qi 'RUNNING\|QUEUED\|COMPLETE\|ERROR' && break
  sleep 60
done
while true; do
  st=$("$K" kernels status "$KID" 2>&1 | tail -1)
  echo "$st" | grep -qi 'COMPLETE\|ERROR\|CANCEL' && break
  sleep 120
done
echo "session ended: $st"
echo "quota after the smoke: $("$K" quota 2>&1 | grep GPU)"
[ -e "$OUT" ] && { echo "$OUT exists"; exit 1; }
mkdir -p "$OUT" "$W"
timeout 1800 "$K" kernels output "$KID" -p "$(cygpath -w "$OUT")" > "$W/output.log" 2>&1
J=$OUT/result/bakeoff_r3.json
[ -f "$J" ] || { echo "no bakeoff_r3.json"; exit 1; }
fail=0
"$PY" -I - "$J" "$OUT/result/warm" <<'EOF' || fail=1
import json, sys
from pathlib import Path
d = json.load(open(sys.argv[1], encoding='utf-8'))
s, c, runs, v, off = d['settings'], d.get('checks', {}), d.get('runs', {}), d.get('validity', {}), d.get('offline', {})
warm = Path(sys.argv[2])
same = None
a, b = warm / 'parity-trainer-source.txt', warm / 'parity-trainer-mover.txt'
diff = None
if a.exists() and b.exists():
    la, lb = a.read_text().splitlines(), b.read_text().splitlines()
    fa = {l.rsplit('|', 1)[0].strip(): float(l.rsplit('|', 1)[1]) for l in la if '|' in l}
    fb = {l.rsplit('|', 1)[0].strip(): float(l.rsplit('|', 1)[1]) for l in lb if '|' in l}
    if len(fa) == len(fb) == 446 and set(fa) == set(fb):
        diff = max(abs(fa[k] - fb[k]) for k in fa)
        same = diff <= 1e-6  # raw outputs (before x S): 1e-6 is far below a hundredth of a centipawn
        print(f'trainer floats, warm start vs r3kr1: {sum(fa[k] == fb[k] for k in fa)} of 446 identical, '
              f'max difference {diff:.3g}')
rep = {'smoke': s.get('smoke'), 'arm_set': s.get('arm_set'), 'commit': s.get('commit'), 'head': d.get('head'),
       'build': (d.get('build') or {}).get('rc'), 'build_s': (d.get('build') or {}).get('seconds'),
       'inputs_ok': d.get('inputs', {}).get('ok'), 'files': d.get('inputs', {}).get('files_per_arm'),
       'source_ok': (d.get('source_weights') or {}).get('sha256_ok'), 'warm_start': d.get('warm_start'),
       'checks': {k: (x.get('rc'), x.get('leg_rc')) for k, x in c.items() if k.startswith(('check-', 'features-'))},
       'reference': (c.get('reference') or {}).get('loss'),
       'warm_float': (c.get('warm_float-mover') or {}).get('loss'), 'warm_float_ok': c.get('warm_float_ok-mover'),
       'quantised_identity': c.get('quantised_identity-mover'), 'checks_ok': c.get('ok'),
       'trainer_floats_warm_equal_source': same,
       'runs': {a: {k: r.get(k) for k in ('rc', 'seconds', 'initial_loss', 'positions_per_second', 'laps',
                                          'lap_mean_after_first', 'error')} for a, r in runs.items()},
       'curves': {a: r.get('val_curve') for a, r in runs.items()},
       'superbatch_0': v.get('per_arm'), 'validity_ok': v.get('ok'),
       'quantised': {a: bool((off.get(f'quantise-{a}') or {}).get('quantised')) for a in ('mb1', 'kc1')}}
print(json.dumps(rep, indent=1))
ck = rep['checks']
good = (rep['smoke'] is True and rep['arm_set'] == 'M' and rep['build'] == 0 and rep['inputs_ok'] and rep['source_ok']
        and all(x[0] == 0 for x in ck.values()) and all(x[1] == 0 for k, x in ck.items() if k.startswith('features-'))
        and {'check-h512ppm', 'check-h512pp', 'features-h512ppm', 'features-h512pp'} <= set(ck)
        and rep['warm_float_ok'] is True and rep['quantised_identity'] is True and rep['checks_ok'] is True
        and same is True and rep['validity_ok'] is True and all(rep['quantised'].values())
        and all(r.get('rc') == 0 and len([p for p in (rep['curves'][a] or []) if p[0] > 0]) == 4
                for a, r in rep['runs'].items()) and set(rep['runs']) == {'mb1', 'kc1'})
print('summary checks', 'PASSED' if good else 'FAILED')
sys.exit(0 if good else 1)
EOF
# The window averages: legs with the trainer's float outputs (GPU) and the engines' netcheck.
for arm in mb1 kc1; do
  lay=$T/h512ppm.json; eng=$E12
  [ $arm = kc1 ] && lay=$T/h512pp.json && eng=$E9
  A=$OUT/result/avg-$arm
  tr=$(ls "$A"/parity-trainer-*.txt 2>/dev/null | head -1)
  [ -f "$A/quantised.bin" ] && [ -n "$tr" ] || { echo "$arm: no quantised.bin or trainer floats"; fail=1; continue; }
  "$PY" -I "$T/convert.py" "$A/quantised.bin" "$W/$arm-s89.fnet" --scale 89 --layout "$lay" | tail -1
  "$PY" -I "$T/pp_bound.py" "$W/$arm-s89.fnet" --clamp "$W/$arm.fnet" | tail -1
  if "$PY" -I "$T/reference.py" legs --net "$W/$arm-s89.fnet" --weights "$A/weights.bin" --quantised "$A/quantised.bin" \
      --epd "$R/tests/nnue/parity.epd" --trainer "$tr" --layout "$lay" --max-loss 21 --p99-loss 16 > "$W/legs-$arm.txt" 2>&1
  then echo "$arm legs PASSED: $(grep '^{' "$W/legs-$arm.txt")"
  else echo "$arm legs FAILED: $(tr '\n' ' ' < "$W/legs-$arm.txt")"; fail=1
  fi
  "$PY" -I "$T/reference.py" legs --net "$W/$arm.fnet" --weights "$A/weights.bin" --quantised "$A/quantised.bin" \
    --epd "$R/tests/nnue/parity.epd" --layout "$lay" --out "$W/$arm.parity" > /dev/null 2>&1
  nc=$("$eng" netcheck "$W/$arm.parity" "$W/$arm.fnet" 2>&1 | tail -1)
  echo "$arm netcheck: $nc"
  echo "$nc" | grep -q ', 0 mismatches' || fail=1
done
"$PY" -I - "$OUT/result/avg-mb1/weights.bin" <<'EOF'
import struct, sys
data = open(sys.argv[1], 'rb').read()
at = 0
while at < len(data):
    nl = data.index(b'\n', at)
    (n,) = struct.unpack_from('<Q', data, nl + 1)
    if data[at:nl] == b'm0w':
        v = struct.unpack_from(f'<{n}f', data, nl + 9)
        print(f'mb1 m0w after 4 superbatches: {sum(1 for x in v if x != 0.0)} of {n} non-zero, max |w| {max(map(abs, v)):.5f}')
    at = nl + 9 + 4 * n
EOF
[ $fail = 0 ] && echo "I178 SMOKE PASSED" || echo "I178 SMOKE FAILED"
exit $fail
