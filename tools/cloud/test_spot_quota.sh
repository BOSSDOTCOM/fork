#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Tests of tools/cloud/spot_quota.sh with a stub AWS CLI (FORK_AWS): the
# applied quota, each type's vCPUs and the running spot instances come from
# the stub's environment, so no AWS account is needed.
#
#   bash tools/cloud/test_spot_quota.sh
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0
expect() {  # description, wanted exit status, spot_quota.sh arguments...
  local what=$1 want=$2
  shift 2
  bash "$here/spot_quota.sh" "$@" >"$tmp/out" 2>&1
  local got=$?
  if [ "$got" = "$want" ]; then echo "PASS  $what"; else
    echo "FAIL  $what (exit $got, wanted $want)"; cat "$tmp/out"; failures=$((failures + 1)); fi
}
cat >"$tmp/aws" <<'EOF'
#!/usr/bin/env bash
# Stub: STUB_QUOTA, STUB_RUNNING (space-separated types); vCPUs per type below.
case "$1 $2" in
  "service-quotas get-service-quota")
    case "$*" in *"--quota-code L-34B43A08"*) echo "$STUB_QUOTA" ;; *) exit 1 ;; esac ;;
  "ec2 describe-instance-types")
    case "$*" in
      *c7a.2xlarge*) echo 8 ;; *c7a.xlarge*) echo 4 ;; *c7a.16xlarge*) echo 64 ;; *m7a.large*) echo 2 ;;
      *) exit 1 ;;
    esac ;;
  "ec2 describe-instances") echo "$STUB_RUNNING" ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$tmp/aws"
export FORK_AWS=$tmp/aws STUB_QUOTA=8.0 STUB_RUNNING=""
expect "one c7a.2xlarge fits an 8 vCPU quota" 0 --region r --type c7a.2xlarge
expect "two c7a.2xlarge exceed it" 3 --region r --type c7a.2xlarge --count 2
expect "a c7a.16xlarge exceeds it" 3 --region r --type c7a.16xlarge
STUB_RUNNING="c7a.xlarge" expect "running instances count: 4 + 8 > 8" 3 --region r --type c7a.2xlarge
STUB_RUNNING="c7a.xlarge" expect "4 + 4 fits" 0 --region r --type c7a.xlarge
STUB_RUNNING="m7a.large m7a.large" expect "2 + 2 + 4 fits" 0 --region r --type c7a.xlarge
expect "a type outside the Standard families is refused" 2 --region r --type g6.xlarge
STUB_QUOTA=oops expect "an unexpected answer is refused" 2 --region r --type c7a.2xlarge
expect "--type is required" 2 --region r
echo "$failures failure(s)"
[ $failures -eq 0 ]
