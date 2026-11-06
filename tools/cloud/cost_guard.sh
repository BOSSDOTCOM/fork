#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Spending guards for Fork's cloud launches (owner, 2026-10-30), run on the
# owner's machine before every launch:
# - a standing daily cap: the worst-case cost of every launch in the last 24
#   hours (its --max-hours times its price cap, recorded in a local ledger)
#   plus the new launch's must not exceed FORK_DAILY_CAP dollars (default 10);
# - a credit floor: the remaining AWS credits (FORK_CREDITS_START, the balance
#   the owner read on FORK_CREDITS_SINCE, minus the credits Cost Explorer
#   shows applied since then) must stay at or above FORK_CREDIT_FLOOR dollars
#   (default 25); below it no new instance is launched (running ones finish)
#   until the owner decides. Without FORK_CREDITS_START the remaining credits
#   are unknown: launches are allowed and every report says so. When Cost
#   Explorer cannot be read (an expired login, say) they are unread: treated
#   as unknown, and the report says the query failed.
# A launch is booked at its worst case while its instance runs; once the
# instance has ended (finished, interrupted or terminated), the booking is
# replaced by what it cost, its hours run times the spot price paid (owner,
# 2026-10-31; tools/cloud/spot_cost.py). The instance's spot request gives
# its start, end, type and zone, the zone's spot price history the price over
# the run; check and report settle every ended instance first. A booking
# whose instance AWS no longer lists (spot requests are kept only some hours
# after they close), or a row from before instances were recorded, keeps its
# worst case until `settle RUN COST` sets its cost by hand.
#
#   tools/cloud/cost_guard.sh check COST     exit 0 when a launch costing at most COST fits, 5 over
#                                            the daily cap, 6 below the credit floor
#   tools/cloud/cost_guard.sh record RUN COST [REGION INSTANCE]
#                                            add a launch to the ledger, booked at COST
#   tools/cloud/cost_guard.sh settle [RUN COST]  replace the bookings of ended instances by their
#                                            cost (or set RUN's cost by hand)
#   tools/cloud/cost_guard.sh report         the last 24 hours' launches and the credits
#
# The ledger (FORK_LAUNCH_LEDGER, default ~/.config/fork-cloud-launches.tsv)
# and the settings live outside the repository. Its rows: launch time, run,
# dollars, then region, instance and "booked" or "paid" (older rows have the
# first three only and count as booked). FORK_AWS names the AWS CLI command,
# FORK_NOW the current time (the tests use both), PYTHON the interpreter.
set -euo pipefail
aws=${FORK_AWS:-aws} py=${PYTHON:-python3}
here=$(cd "$(dirname "$0")" && pwd)
cap=${FORK_DAILY_CAP:-10} floor=${FORK_CREDIT_FLOOR:-25}
ledger=${FORK_LAUNCH_LEDGER:-$HOME/.config/fork-cloud-launches.tsv}
now=$(date -u -d "${FORK_NOW:-now}" +%s)
dollars() { [[ $1 =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "cost_guard.sh: '$1' is not an amount in dollars" >&2; exit 2; }; }

recent() {  # worst-case dollars launched in the last 24 hours
  [ -f "$ledger" ] || { echo 0; return; }
  awk -F'\t' -v since=$((now - 86400)) '$1 >= since { s += $3 } END { printf "%.2f\n", s + 0 }' "$ledger"
}

cost_paid() {  # region instance: an ended instance's cost in dollars; fails while it runs or if unknown
  local code start end itype zone rows rc
  read -r code start end itype zone < <("$aws" ec2 describe-spot-instance-requests --region "$1" \
    --filters "Name=instance-id,Values=$2" --output text \
    --query 'SpotInstanceRequests[0].[Status.Code,CreateTime,Status.UpdateTime,LaunchSpecification.InstanceType,LaunchedAvailabilityZone]' \
    2>/dev/null | tr -d '\r')
  case ${code:-} in instance-terminated-*) ;; *) return 1 ;; esac
  [ -n "${zone:-}" ] && [ "$zone" != None ] || return 1
  rows=$(mktemp)
  # From a day before the start, so the price in effect at the start is among the rows.
  "$aws" ec2 describe-spot-price-history --region "$1" --instance-types "$itype" --availability-zone "$zone" \
    --product-descriptions Linux/UNIX --start-time "$(date -u -d "@$(($(date -u -d "$start" +%s) - 86400))" +%FT%TZ)" \
    --end-time "$end" --query 'SpotPriceHistory[].[SpotPrice,Timestamp]' --output json >"$rows" 2>/dev/null &&
    "$py" "$here/spot_cost.py" "$rows" "$start" "$end" | tr -d '\r'
  rc=${PIPESTATUS[0]}
  rm -f "$rows"
  return "$rc"
}

settle() {  # the ledger again, with the cost of every ended instance in place of its booking
  [ -f "$ledger" ] || return 0
  local t run cost region id state paid new
  new=$(mktemp)
  while IFS=$'\t' read -r t run cost region id state; do
    if [ "${state:-}" = booked ] && paid=$(cost_paid "$region" "$id") && [[ $paid =~ ^[0-9]+\.[0-9]+$ ]]; then
      echo "cost guard: $run ($id) has ended; its \$$cost booking is now its cost, \$$paid" >&2
      cost=$paid state=paid
    fi
    if [ -n "${state:-}" ]; then printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$t" "$run" "$cost" "$region" "$id" "$state"
    else printf '%s\t%s\t%s\n' "$t" "$run" "$cost"; fi
  done <"$ledger" >"$new"
  cat "$new" >"$ledger"
  rm -f "$new"
}

credits() {  # remaining credits in dollars, "unknown" without a starting balance, "unread" if the query fails
  [ -n "${FORK_CREDITS_START:-}" ] && [ -n "${FORK_CREDITS_SINCE:-}" ] || { echo unknown; return; }
  dollars "$FORK_CREDITS_START"
  local applied
  # Credits appear in Cost Explorer as negative amounts of record type Credit.
  applied=$("$aws" ce get-cost-and-usage --time-period "Start=$FORK_CREDITS_SINCE,End=$(date -u -d "@$((now + 86400))" +%F)" \
    --granularity MONTHLY --metrics UnblendedCost --filter '{"Dimensions":{"Key":"RECORD_TYPE","Values":["Credit"]}}' \
    --query 'ResultsByTime[].Total.UnblendedCost.Amount' --output text) || { echo unread; return; }
  awk -v start="$FORK_CREDITS_START" -v a="$applied" 'BEGIN { n = split(a, v, /[ \t\n]+/); s = 0;
    for (i = 1; i <= n; i++) s += v[i]; printf "%.2f\n", start + s }'
}

case ${1:-} in
  check)
    dollars "${2:-}"
    settle
    used=$(recent)
    if awk -v u="$used" -v c="$2" -v cap="$cap" 'BEGIN { exit !(u + c > cap) }'; then
      echo "cost guard: refused, \$$used launched in the last 24 h + \$$2 exceeds the daily cap of \$$cap" >&2
      exit 5
    fi
    left=$(credits)
    if [[ $left != unknown && $left != unread ]] && awk -v l="$left" -v f="$floor" 'BEGIN { exit !(l < f) }'; then
      echo "cost guard: refused, credits \$$left are below the floor of \$$floor (running instances finish)" >&2
      exit 6
    fi
    case $left in unknown) ;; unread) left="unread (the AWS query failed)" ;; *) left=\$$left ;; esac
    echo "cost guard ok: \$$used + \$$2 within the daily cap of \$$cap; credits $left (floor \$$floor)"
    ;;
  record)
    [ -n "${2:-}" ] || { echo "cost_guard.sh record RUN COST [REGION INSTANCE]" >&2; exit 2; }
    dollars "${3:-}"
    mkdir -p "$(dirname "$ledger")"
    if [ -n "${5:-}" ]; then printf '%s\t%s\t%s\t%s\t%s\tbooked\n' "$now" "$2" "$3" "$4" "$5" >>"$ledger"
    else printf '%s\t%s\t%s\n' "$now" "$2" "$3" >>"$ledger"; fi
    ;;
  settle)
    if [ -z "${2:-}" ]; then settle; exit 0; fi
    dollars "${3:-}"
    [ -f "$ledger" ] && awk -F'\t' -v run="$2" '$2 == run { found = 1 } END { exit !found }' "$ledger" ||
      { echo "cost_guard.sh: no launch $2 in the ledger" >&2; exit 2; }
    # "-" for an unknown region or instance: bash's read merges empty tab-separated fields.
    awk -F'\t' -v OFS='\t' -v run="$2" -v c="$3" '$2 == run { $3 = c; if ($4 == "") $4 = "-"
      if ($5 == "") $5 = "-"; $6 = "paid" } 1' "$ledger" >"$ledger.new" &&
      cat "$ledger.new" >"$ledger" && rm -f "$ledger.new"
    ;;
  report)
    settle
    echo "launches in the last 24 h (worst case while running, the cost once ended): \$$(recent) of the daily cap \$$cap"
    if [ -f "$ledger" ]; then
      while IFS=$'\t' read -r t run cost region id state; do
        if [ "$t" -ge $((now - 86400)) ]; then
          echo "  $(date -u -d "@$t" '+%Y-%m-%d %H:%M UTC')  $run  \$$cost  ${state:-booked}"
        fi
      done <"$ledger"
    fi
    left=$(credits)
    if [ "$left" = unknown ]; then
      echo "credits: unknown (set FORK_CREDITS_START and FORK_CREDITS_SINCE from the billing console)"
    elif [ "$left" = unread ]; then
      echo "credits: unknown (the Cost Explorer query failed: is the AWS login current?)"
    else
      echo "credits: \$$left remaining (floor \$$floor; Cost Explorer lags by about a day)"
    fi
    ;;
  *) echo "usage: cost_guard.sh check COST | record RUN COST [REGION INSTANCE] | settle [RUN COST] | report" >&2
     exit 2 ;;
esac
