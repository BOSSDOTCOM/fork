#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Spot interruption watcher for a cloud job (the SPRT shards and cloud data
# generation): polls the instance metadata service (IMDSv2: a session token
# first) for spot/instance-action, which appears about two minutes before
# AWS reclaims a spot instance, and sends SIGTERM to the job's PID when it
# does, so the job can stop cleanly and its results can be uploaded. Exits
# when the job ends (0 either way); prints "spot interruption notice" when
# it stopped the job.
#
#   tools/cloud/spot_watch.sh PID [--imds URL] [--interval SECONDS]
#
# --imds defaults to EC2's http://169.254.169.254 (the test points it at a
# fake service).
set -uo pipefail
pid=${1:?usage: spot_watch.sh PID [--imds URL] [--interval SECONDS]}
shift
imds=http://169.254.169.254 interval=5
while [ $# -gt 0 ]; do
  case $1 in
    --imds) imds=$2 ;; --interval) interval=$2 ;;
    *) echo "spot_watch.sh: unknown option $1" >&2; exit 2 ;;
  esac
  shift 2
done
while kill -0 "$pid" 2>/dev/null; do
  token=$(curl -s -m 2 -X PUT -H 'X-aws-ec2-metadata-token-ttl-seconds: 300' "$imds/latest/api/token")
  code=$(curl -s -m 2 -o /dev/null -w '%{http_code}' -H "X-aws-ec2-metadata-token: $token" \
    "$imds/latest/meta-data/spot/instance-action")
  if [ "$code" = 200 ]; then
    echo "spot interruption notice"
    kill -TERM "$pid"
    exit 0
  fi
  sleep "$interval"
done
exit 0
