#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Terminates Fork's cloud instances that are past their time limit: every
# instance tagged fork-run whose fork-expires tag (UTC, set at launch from
# --max-hours) is in the past and that is still pending, running, stopping
# or stopped. Each instance already arms its own shutdown at that limit;
# this is the second safeguard, for an instance whose shutdown failed.
# Instances without the tags are never touched.
#
#   tools/cloud/aws_cleanup.sh --region REGION [--dry-run] [--grace-minutes 15]
#
# Prints each instance it terminates (or would, with --dry-run). FORK_AWS
# names the AWS CLI command (the tests use a stub); FORK_NOW overrides the
# current time (UTC, for the tests).
set -euo pipefail
aws=${FORK_AWS:-aws}
region="" dry=0 grace=15
while [ $# -gt 0 ]; do
  case $1 in
    --region) region=$2; shift ;; --grace-minutes) grace=$2; shift ;;
    --dry-run) dry=1 ;;
    *) echo "aws_cleanup.sh: unknown option $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$region" ] || { echo "aws_cleanup.sh: --region is required" >&2; exit 2; }
case $grace in '' | *[!0-9]*) echo "aws_cleanup.sh: --grace-minutes must be a number" >&2; exit 2 ;; esac
now=$(date -u -d "${FORK_NOW:-now}" +%s)
expired=()
while read -r id run expires; do
  [ -n "${id:-}" ] || continue
  limit=$(date -u -d "$expires" +%s 2>/dev/null) || { echo "aws_cleanup.sh: $id has an unreadable fork-expires '$expires'; left alone" >&2; continue; }
  if [ "$now" -gt $((limit + grace * 60)) ]; then
    echo "$([ $dry = 1 ] && echo 'would terminate' || echo terminating) $id (run $run, expired $expires)"
    expired+=("$id")
  fi
done < <("$aws" ec2 describe-instances --region "$region" \
  --filters Name=tag-key,Values=fork-run Name=instance-state-name,Values=pending,running,stopping,stopped \
  --query "Reservations[].Instances[].[InstanceId, Tags[?Key=='fork-run']|[0].Value, Tags[?Key=='fork-expires']|[0].Value]" \
  --output text)
if [ ${#expired[@]} -eq 0 ]; then
  echo "nothing past its limit in $region"
elif [ $dry = 0 ]; then
  "$aws" ec2 terminate-instances --region "$region" --instance-ids "${expired[@]}" \
    --query 'TerminatingInstances[].[InstanceId, CurrentState.Name]' --output text
fi
