#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Checks a spot launch against the account's applied EC2 spot quota before
# anything is launched (owner, 2026-10-30): the vCPUs of the spot instances
# already pending or running plus COUNT x TYPE's vCPUs must not exceed the
# applied "All Standard (A, C, D, H, I, M, R, T, Z) Spot Instance Requests"
# quota (code L-34B43A08, as `aws service-quotas list-service-quotas
# --service-code ec2` lists it). Every number comes from AWS at the time of
# the check: the quota, each type's vCPUs and the running instances.
#
#   tools/cloud/spot_quota.sh --region REGION --type TYPE [--count N]
#
# Prints one line and exits 0 when the launch fits, 3 when it would exceed
# the quota, 2 on a usage error or a type outside the Standard families.
# FORK_AWS names the AWS CLI command (the tests use a stub).
set -euo pipefail
aws=${FORK_AWS:-aws}
region="" type="" count=1
while [ $# -gt 0 ]; do
  case $1 in
    --region) region=$2 ;; --type) type=$2 ;; --count) count=$2 ;;
    *) echo "spot_quota.sh: unknown option $1" >&2; exit 2 ;;
  esac
  shift 2
done
[ -n "$region" ] && [ -n "$type" ] || { echo "spot_quota.sh: --region and --type are required" >&2; exit 2; }
case $count in '' | *[!0-9]*) echo "spot_quota.sh: --count must be a number" >&2; exit 2 ;; esac
# The quota covers these families only (its name); anything else has its own.
standard() { case ${1%%.*} in [acdhimrtz]*) return 0 ;; *) return 1 ;; esac; }
standard "$type" || { echo "spot_quota.sh: $type is not in the Standard spot quota's families" >&2; exit 2; }
vcpus() {
  "$aws" ec2 describe-instance-types --region "$region" --instance-types "$1" \
    --query 'InstanceTypes[0].VCpuInfo.DefaultVCpus' --output text
}
quota=$("$aws" service-quotas get-service-quota --region "$region" --service-code ec2 --quota-code L-34B43A08 \
  --query 'Quota.Value' --output text)
quota=${quota%.*}
per=$(vcpus "$type")
used=0
for t in $("$aws" ec2 describe-instances --region "$region" \
    --filters Name=instance-lifecycle,Values=spot Name=instance-state-name,Values=pending,running \
    --query 'Reservations[].Instances[].InstanceType' --output text); do
  standard "$t" && used=$((used + $(vcpus "$t")))
done
want=$((count * per))
case "$quota$per$used" in *[!0-9]*) echo "spot_quota.sh: unexpected answer from AWS" >&2; exit 2 ;; esac
if [ $((used + want)) -le "$quota" ]; then
  echo "spot quota ok: $count x $type = $want vCPU, $used in use, applied quota $quota ($region)"
else
  echo "spot quota exceeded: $count x $type = $want vCPU, $used in use, applied quota $quota ($region): refused" >&2
  exit 3
fi
