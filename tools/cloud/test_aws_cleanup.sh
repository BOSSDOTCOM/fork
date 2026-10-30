#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Tests of tools/cloud/aws_cleanup.sh with a stub AWS CLI (FORK_AWS) and a
# fixed clock (FORK_NOW): only tagged instances past fork-expires plus the
# grace period are terminated; --dry-run terminates nothing.
#
#   bash tools/cloud/test_aws_cleanup.sh
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
cat >"$tmp/aws" <<'EOF'
#!/usr/bin/env bash
case "$1 $2" in
  "ec2 describe-instances")
    printf 'i-old\tsprt-a\t2026-10-30T10:00:00Z\n'
    printf 'i-fresh\tdatagen-b\t2026-10-30T13:00:00Z\n'
    printf 'i-grace\tdatagen-c\t2026-10-30T11:50:00Z\n'
    printf 'i-bad\tdatagen-d\tnot-a-time\n' ;;
  "ec2 terminate-instances") shift 2; echo "$*" >>"$STUB_LOG"; echo "terminated" ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$tmp/aws"
export FORK_AWS=$tmp/aws STUB_LOG=$tmp/terminated FORK_NOW=2026-10-30T12:00:00Z

bash "$here/aws_cleanup.sh" --region r --dry-run >"$tmp/dry.out" 2>&1
check "dry run names the expired instance" grep -q "would terminate i-old" "$tmp/dry.out"
check "dry run terminates nothing" [ ! -e "$tmp/terminated" ]
bash "$here/aws_cleanup.sh" --region r >"$tmp/run.out" 2>&1
check "only the expired instance is terminated" grep -q -- "--instance-ids i-old --query" "$tmp/terminated"
check "an instance inside its limit is kept" bash -c "! grep -q i-fresh '$tmp/terminated'"
check "an instance inside the grace period is kept" bash -c "! grep -q i-grace '$tmp/terminated'"
check "an unreadable limit is reported and left alone" grep -q "i-bad has an unreadable" "$tmp/run.out"
FORK_NOW=2026-10-30T09:00:00Z bash "$here/aws_cleanup.sh" --region r >"$tmp/none.out" 2>&1
check "nothing expired: nothing terminated" grep -q "nothing past its limit" "$tmp/none.out"
echo "$failures failure(s)"
[ $failures -eq 0 ]
