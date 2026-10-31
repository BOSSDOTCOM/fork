#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Tests of tools/cloud/cost_guard.sh with a stub AWS CLI (FORK_AWS) and a
# fixed clock (FORK_NOW): the daily cap over the last 24 hours' launches,
# the credit floor from Cost Explorer's applied credits, and the unknown
# balance. No AWS account is needed.
#
#   bash tools/cloud/test_cost_guard.sh
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0
expect() {  # description, wanted exit status, cost_guard.sh arguments...
  local what=$1 want=$2
  shift 2
  bash "$here/cost_guard.sh" "$@" >"$tmp/out" 2>&1
  local got=$?
  if [ "$got" = "$want" ]; then echo "PASS  $what"; else
    echo "FAIL  $what (exit $got, wanted $want)"; cat "$tmp/out"; failures=$((failures + 1)); fi
}
cat >"$tmp/aws" <<'EOF'
#!/usr/bin/env bash
# Stub: Cost Explorer's applied credits per month (STUB_CREDITS, negative
# amounts); spot requests of instance i-ended (ended after 3 hours in
# us-x-1a), i-run (running) and none for any other; the pool's prices,
# $0.10 from 18:00 and $0.20 from 21:00.
case "$1 $2" in
  "ce get-cost-and-usage") echo "$STUB_CREDITS" ;;
  "ec2 describe-spot-instance-requests")
    case "$*" in
      *Values=i-ended*) printf 'instance-terminated-by-price\t2026-10-30T19:00:00+00:00\t2026-10-30T22:00:00+00:00\tc8a.2xlarge\tus-x-1a\n' ;;
      *Values=i-run*) printf 'fulfilled\t2026-10-30T20:00:00+00:00\t2026-10-30T20:01:00+00:00\tc8a.2xlarge\tus-x-1a\n' ;;
      *) printf 'None\n' ;;
    esac ;;
  "ec2 describe-spot-price-history")
    echo '[["0.200000", "2026-10-30T21:00:00+00:00"], ["0.100000", "2026-10-30T18:00:00+00:00"]]' ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$tmp/aws"
export FORK_AWS=$tmp/aws FORK_LAUNCH_LEDGER=$tmp/ledger.tsv FORK_NOW=2026-10-30T22:00:00Z
unset FORK_CREDITS_START FORK_CREDITS_SINCE FORK_DAILY_CAP FORK_CREDIT_FLOOR

# 1. The daily cap: worst cases of the last 24 hours plus the new launch.
expect "an empty ledger leaves the whole cap" 0 check 3
FORK_NOW=2026-10-29T21:00:00Z bash "$here/cost_guard.sh" record old 3   # 25 hours ago: outside the window
bash "$here/cost_guard.sh" record r1 3
bash "$here/cost_guard.sh" record r2 3
expect "a third \$3 launch fits \$10" 0 check 3
bash "$here/cost_guard.sh" record r3 3
expect "a fourth does not" 5 check 3
expect "a launch costing \$1 still fits (\$9 + \$1)" 0 check 1
FORK_DAILY_CAP=20 expect "the cap can be raised" 0 check 3
expect "a malformed cost is refused" 2 check 3x
bash "$here/cost_guard.sh" report >"$tmp/report"
if grep -q 'last 24 h .*: \$9.00' "$tmp/report" && ! grep -q ' old ' "$tmp/report"; then
  echo "PASS  the report lists the window's launches only"; else echo "FAIL  report"; cat "$tmp/report"; failures=$((failures + 1)); fi

# 2. The credit floor: start minus the credits applied since.
rm -f "$FORK_LAUNCH_LEDGER"
export FORK_CREDITS_SINCE=2026-10-30 FORK_CREDITS_START=100 STUB_CREDITS="-60.5	-10"
expect "\$29.50 left is above the \$25 floor" 0 check 3
export STUB_CREDITS="-60.5	-20"
expect "\$19.50 left is below it: no launch" 6 check 3
bash "$here/cost_guard.sh" report >"$tmp/report"
if grep -q 'credits: \$19.50 remaining' "$tmp/report"; then echo "PASS  the report shows the credits left"; else
  echo "FAIL  credit report"; cat "$tmp/report"; failures=$((failures + 1)); fi

# 3. Unknown balance: launches allowed, the report says so.
unset FORK_CREDITS_START
expect "without a starting balance the floor cannot refuse" 0 check 3
bash "$here/cost_guard.sh" report >"$tmp/report"
if grep -q 'credits: unknown' "$tmp/report"; then echo "PASS  the report says the credits are unknown"; else
  echo "FAIL  unknown report"; cat "$tmp/report"; failures=$((failures + 1)); fi

# 4. An ended instance's booking becomes its cost: 2 hours at $0.10 and 1 at
# $0.20 is $0.40. A running instance, one AWS no longer lists and a row
# without an instance keep their bookings until settled by hand.
rm -f "$FORK_LAUNCH_LEDGER"
export PYTHON=${PYTHON:-python3}
bash "$here/cost_guard.sh" record r-ended 3 us-x-1 i-ended
bash "$here/cost_guard.sh" record r-run 3 us-x-1 i-run
bash "$here/cost_guard.sh" record r-gone 3 us-x-1 i-gone
expect "\$9 booked + \$3 fits once the ended instance costs \$0.40" 0 check 3
row() { awk -F'\t' -v r="$1" '$2 == r { print $3, $6 }' "$FORK_LAUNCH_LEDGER"; }
if [ "$(row r-ended)" = "0.40 paid" ] && [ "$(row r-run)" = "3 booked" ] && [ "$(row r-gone)" = "3 booked" ]; then
  echo "PASS  only the ended instance's booking is replaced"; else
  echo "FAIL  settle"; cat "$FORK_LAUNCH_LEDGER"; failures=$((failures + 1)); fi
expect "\$6.40 + \$4 is over the cap" 5 check 4
bash "$here/cost_guard.sh" record r-old 3
expect "settling by hand needs a launch in the ledger" 2 settle r-none 1
bash "$here/cost_guard.sh" settle r-gone 1.25
bash "$here/cost_guard.sh" settle r-old 0.50
if [ "$(row r-gone)" = "1.25 paid" ] && [ "$(row r-old)" = "0.50 paid" ]; then
  echo "PASS  settling by hand, an older three-column row too"; else
  echo "FAIL  settle by hand"; cat "$FORK_LAUNCH_LEDGER"; failures=$((failures + 1)); fi
bash "$here/cost_guard.sh" report >"$tmp/report"
if grep -q 'last 24 h .*: \$5.15 of' "$tmp/report" && grep -q 'r-ended  \$0.40  paid' "$tmp/report" &&
  grep -q 'r-run  \$3  booked' "$tmp/report" && grep -q 'r-old  \$0.50  paid' "$tmp/report"; then
  echo "PASS  the report shows costs and bookings"; else
  echo "FAIL  settled report"; cat "$tmp/report"; failures=$((failures + 1)); fi
if [ "$(row r-old)" = "0.50 paid" ] && [ "$(row r-gone)" = "1.25 paid" ] && [ "$(row r-ended)" = "0.40 paid" ]; then
  echo "PASS  settled rows stay settled when the ledger is rewritten"; else
  echo "FAIL  rewrite"; cat "$FORK_LAUNCH_LEDGER"; failures=$((failures + 1)); fi

echo "$failures failure(s)"
[ $failures -eq 0 ]
