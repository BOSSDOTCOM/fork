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
# Stub: Cost Explorer's applied credits per month (STUB_CREDITS, negative amounts).
case "$1 $2" in
  "ce get-cost-and-usage") echo "$STUB_CREDITS" ;;
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
if grep -q 'last 24 h (worst case): \$9.00' "$tmp/report" && ! grep -q ' old ' "$tmp/report"; then
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

echo "$failures failure(s)"
[ $failures -eq 0 ]
