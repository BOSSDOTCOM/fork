#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Dry-run test of tools/github/spsa_shard.py with a fake fastchess (no engine runs, no game is played): the
# options each side gets in every draw (theta + c*signs for plus, theta - c*signs for minus, as the draw's
# seed gives them, and the fixed options on both), the openings, what result.json records (the driver's own
# check, spsa.py verify_shards, accepts it), and the failure states. Uses python (or $PYTHON).
#
#   bash tools/github/test_spsa_shard.sh
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
[ -n "$py" ] || { echo "test_spsa_shard.sh: no python found" >&2; exit 1; }

# Fake fastchess: its arguments go to $FAKE_DIR/args.<start line>; it plays -rounds pairs, plus winning game
# one and drawing game two. FAKE_FC=crash (exit 139 at line $FAKE_LINE), short (one game fewer at that
# line), slow (sleeps 30 s before playing).
cat >"$tmp/fastchess" <<'EOF'
#!/usr/bin/env bash
rounds=0 line=0
for a in "$@"; do case $a in start=*) line=${a#start=} ;; esac; done
args=("$@")
for i in "${!args[@]}"; do [ "${args[$i]}" = -rounds ] && rounds=${args[$((i + 1))]}; done
printf '%s\n' "$@" >"$FAKE_DIR/args.$line"
[ "${FAKE_FC:-}" = slow ] && sleep 30
n=$((2 * rounds))
[ "${FAKE_FC:-}" = short ] && [ "$line" = "${FAKE_LINE:-}" ] && n=$((n - 1))
for g in $(seq 1 "$n"); do
  if [ $((g % 2)) = 1 ]; then echo "Finished game $g (plus vs minus): 1-0 {White mates}"
  else echo "Finished game $g (minus vs plus): 1/2-1/2 {Draw by 3-fold repetition}"; fi
done
if [ "${FAKE_FC:-}" = crash ] && [ "$line" = "${FAKE_LINE:-}" ]; then exit 139; fi
exit 0
EOF
chmod +x "$tmp/fastchess"
printf '#!/bin/sh\n' >"$tmp/fork" && chmod +x "$tmp/fork"
for i in $(seq 1 20); do echo "8/8/8/8/8/8/8/K6k w - - 0 $i"; done >"$tmp/book.shuffled-7.epd"
mkdir -p "$tmp/tb" "$tmp/tb-short"
for i in $(seq 1 145); do : >"$tmp/tb/T$i.rtbw"; : >"$tmp/tb/T$i.rtbz"; done
: >"$tmp/tb-short/KPvK.rtbw"
commit=0123456789abcdef0123456789abcdef01234567
params='RfpMargin=80.300:6.000,LmpQuietAllowance=12.500:1.000,UseRazoring=true'

shard() {  # out dir, draw pairs, extra arguments...; status in $status
  local out=$1 k=$2
  shift 2
  mkdir -p "$tmp/$out.args"
  FAKE_DIR=$tmp/$out.args "$py" -I -B "$here/spsa_shard.py" --engine "$tmp/fork" --fastchess "$tmp/fastchess" \
    --book "$tmp/book.shuffled-7.epd" --shard 1 --shards 2 --games 12 --label spsa-test --commit "$commit" \
    --stage 3 --params "$params" --openings 2000001 --draw-pairs "$k" --tc 8+0.08 --hash 16 \
    --syzygy "$tmp/tb" --concurrency 2 --out "$tmp/$out" --meta runner=test "$@" >"$tmp/$out.txt" 2>&1
  status=$?
}
field() {  # out dir, python expression on the result r
  "$py" -I -c "import json, sys; r = json.load(open(sys.argv[1])); print($2)" "$tmp/$1/result.json" | tr -d "\r"
}

# 1-8: every draw's options are its seed's, symmetric around theta, fixed options on both sides.
shard one 1
check "one pair per draw: exit 0" test "$status" = 0
check "status done, 3 draws (6 games over 2 shards = 3 pairs here)" test "$(field one "r['status'], len(r['records'])")" = "done 3"
check "openings: shard 1 of 2 plays lines 2000004-2000006" test "$(field one "r['meta']['opening_start'], r['meta']['opening_end']")" = "2000004 2000006"
check "one fastchess call per draw, at its own line" test "$(ls "$tmp/one.args" | tr '\n' ' ')" = "args.2000004 args.2000005 args.2000006 "
check "the options are the seed's (plus for plus, minus for minus), fixed on both" "$py" -I -B - "$here" "$tmp/one" <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import json, spsa
out = Path(sys.argv[2])
r = json.load(open(out / 'result.json'))
tuned, fixed = spsa.parse_params(r['meta']['params'])
names = [n for n, _, _ in tuned]
for rec in r['records']:
    signs, plus, minus = spsa.perturbed_values(spsa.pair_seed('spsa-test', r['meta']['commit'], 3, 1, rec['index']), tuned)
    args = (out.parent / 'one.args' / f'args.{rec["line"]}').read_text().split('\n')
    second = args.index('-engine', 1)
    first_side, second_side = args[:second], args[second:args.index('-each')]
    assert 'name=plus' in first_side and 'name=minus' in second_side, args
    for n, p, m in zip(names, plus, minus):
        assert f'option.{n}={p}' in first_side and f'option.{n}={m}' in second_side, (n, p, m)
    assert first_side.count('option.UseRazoring=true') == 1 and second_side.count('option.UseRazoring=true') == 1
    for (n, theta, c), s, p, m in zip(tuned, signs, plus, minus):
        assert abs((p + m) / 2 - theta) <= 0.5 and abs(p - m - 2 * c * s) <= 1, (n, theta, c, p, m)
    assert (rec['plus'], rec['minus']) == (plus, minus)
EOF
check "each call: -rounds 1 -repeat, Syzygy, Hash, one thread, -concurrency 1" bash -c "
  a='$tmp/one.args/args.2000005'
  grep -qx -- -repeat \$a && grep -A1 -x -- -rounds \$a | grep -qx 1 && grep -qx 'option.SyzygyPath=.*' \$a &&
  grep -qx option.Hash=16 \$a && grep -qx option.Threads=1 \$a && grep -A1 -x -- -concurrency \$a | grep -qx 1"
check "pentanomial for plus: a win and a draw per pair" test "$(field one "r['ptnml']")" = "[0, 0, 0, 3, 0]"
check "the driver's own check accepts the shard (a one-shard run)" "$py" -I -B - "$here" "$tmp/one/result.json" "$params" <<'EOF'
import sys, json
sys.path.insert(0, sys.argv[1])
import spsa
r = json.load(open(sys.argv[2]))
r['meta']['shard'], r['meta']['shards'] = '0', '1'
disp = {'label': 'spsa-test', 'commit': r['meta']['commit'], 'stage': 3, 'params': sys.argv[3], 'tc': '8+0.08',
        'hash': 16, 'games': 6, 'shards': 1, 'draw_pairs': 1, 'openings': 2000004}
# shard 1's seeds: verify as the driver would for shard index 1 of 2 (the meta says 1)
r['meta']['shard'], r['meta']['shards'] = '1', '2'
other = json.loads(json.dumps(r)); other['meta']['shard'] = '0'
other['meta']['opening_start'], other['meta']['opening_end'] = '2000001', '2000003'
for rec in other['records']:
    rec['line'] -= 3
    s, p, m = spsa.perturbed_values(spsa.pair_seed('spsa-test', r['meta']['commit'], 3, 0, rec['index']),
                                    spsa.parse_params(sys.argv[3])[0])
    rec['signs'], rec['plus'], rec['minus'] = ''.join('+' if x > 0 else '-' for x in s), p, m
disp.update(shards=2, games=12, openings=2000001)
assert len(spsa.verify_shards(disp, [other, r])) == 6
EOF
check "meta: label, stage, book seed, tables, runner" test "$(field one "r['meta']['label'], r['meta']['stage'], r['meta']['book_seed'], r['meta']['tables'], r['meta']['runner']")" = "spsa-test 3 7 3-4-5 test"

# 9-10: two pairs per draw: -rounds 2, two lines per draw.
shard two 2
check "two pairs per draw: exit 0, 2 draws of 2 pairs (rounded up to whole draws)" test "$status-$(field two "len(r['records']), sum(r['ptnml'])")" = "0-2 4"
check "two pairs per draw: lines 2000005 and 2000007" test "$(ls "$tmp/two.args" | tr '\n' ' ')" = "args.2000005 args.2000007 "

# 11-13: failures.
FAKE_FC=crash FAKE_LINE=2000005 shard crash 1
check "a crashing draw: exit 1, status failed, exit 139 recorded" test "$status-$(field crash "r['status'], r['meta']['fastchess_exit']")" = "1-failed 139"
FAKE_FC=short FAKE_LINE=2000006 shard short 1
check "a draw with a game missing: exit 1, status short" test "$status-$(field short "r['status']")" = "1-short"
shard badtb 1 --syzygy "$tmp/tb-short"
check "an incomplete table set is refused" test "$status" = 2

# 14: SIGTERM keeps finished draws as interrupted (Linux: Git Bash cannot signal a native Windows process).
if [ "$(uname -s)" = Linux ]; then
  mkdir -p "$tmp/term.args"
  FAKE_FC=slow FAKE_DIR=$tmp/term.args "$py" -I -B "$here/spsa_shard.py" --engine "$tmp/fork" --fastchess "$tmp/fastchess" \
    --book "$tmp/book.shuffled-7.epd" --shard 0 --shards 1 --games 6 --label spsa-test --commit "$commit" --stage 0 \
    --params "$params" --openings 2000001 --tc 8+0.08 --hash 16 --concurrency 1 --out "$tmp/term" >"$tmp/term.txt" 2>&1 &
  pid=$!
  sleep 3
  kill -TERM "$pid"
  wait "$pid"
  status=$?
  check "SIGTERM: exit 0, status interrupted" test "$status-$(field term "r['status']")" = "0-interrupted"
else
  echo "SKIP  SIGTERM (Linux only)"
fi

echo "${failures} failure(s)"
exit $((failures > 0))
