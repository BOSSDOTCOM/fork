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
#   are unknown: launches are allowed and every report says so.
#
#   tools/cloud/cost_guard.sh check COST     exit 0 when a launch costing at most COST fits, 5 over
#                                            the daily cap, 6 below the credit floor
#   tools/cloud/cost_guard.sh record RUN COST    add a launch to the ledger
#   tools/cloud/cost_guard.sh report         the last 24 hours' launches and the credits
#
# The ledger (FORK_LAUNCH_LEDGER, default ~/.config/fork-cloud-launches.tsv)
# and the settings live outside the repository. FORK_AWS names the AWS CLI
# command and FORK_NOW the current time (the tests use both).
set -euo pipefail
aws=${FORK_AWS:-aws}
cap=${FORK_DAILY_CAP:-10} floor=${FORK_CREDIT_FLOOR:-25}
ledger=${FORK_LAUNCH_LEDGER:-$HOME/.config/fork-cloud-launches.tsv}
now=$(date -u -d "${FORK_NOW:-now}" +%s)
dollars() { [[ $1 =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "cost_guard.sh: '$1' is not an amount in dollars" >&2; exit 2; }; }

recent() {  # worst-case dollars launched in the last 24 hours
  [ -f "$ledger" ] || { echo 0; return; }
  awk -F'\t' -v since=$((now - 86400)) '$1 >= since { s += $3 } END { printf "%.2f\n", s + 0 }' "$ledger"
}

credits() {  # remaining credits in dollars, or "unknown"
  [ -n "${FORK_CREDITS_START:-}" ] && [ -n "${FORK_CREDITS_SINCE:-}" ] || { echo unknown; return; }
  dollars "$FORK_CREDITS_START"
  local applied
  # Credits appear in Cost Explorer as negative amounts of record type Credit.
  applied=$("$aws" ce get-cost-and-usage --time-period "Start=$FORK_CREDITS_SINCE,End=$(date -u -d "@$((now + 86400))" +%F)" \
    --granularity MONTHLY --metrics UnblendedCost --filter '{"Dimensions":{"Key":"RECORD_TYPE","Values":["Credit"]}}' \
    --query 'ResultsByTime[].Total.UnblendedCost.Amount' --output text) || { echo unknown; return; }
  awk -v start="$FORK_CREDITS_START" -v a="$applied" 'BEGIN { n = split(a, v, /[ \t\n]+/); s = 0;
    for (i = 1; i <= n; i++) s += v[i]; printf "%.2f\n", start + s }'
}

case ${1:-} in
  check)
    dollars "${2:-}"
    used=$(recent)
    if awk -v u="$used" -v c="$2" -v cap="$cap" 'BEGIN { exit !(u + c > cap) }'; then
      echo "cost guard: refused, \$$used launched in the last 24 h + \$$2 exceeds the daily cap of \$$cap" >&2
      exit 5
    fi
    left=$(credits)
    if [ "$left" != unknown ] && awk -v l="$left" -v f="$floor" 'BEGIN { exit !(l < f) }'; then
      echo "cost guard: refused, credits \$$left are below the floor of \$$floor (running instances finish)" >&2
      exit 6
    fi
    [ "$left" = unknown ] || left=\$$left
    echo "cost guard ok: \$$used + \$$2 within the daily cap of \$$cap; credits $left (floor \$$floor)"
    ;;
  record)
    [ -n "${2:-}" ] || { echo "cost_guard.sh record RUN COST" >&2; exit 2; }
    dollars "${3:-}"
    mkdir -p "$(dirname "$ledger")"
    printf '%s\t%s\t%s\n' "$now" "$2" "$3" >>"$ledger"
    ;;
  report)
    echo "launches in the last 24 h (worst case): \$$(recent) of the daily cap \$$cap"
    if [ -f "$ledger" ]; then
      while IFS=$'\t' read -r t run cost; do
        if [ "$t" -ge $((now - 86400)) ]; then echo "  $(date -u -d "@$t" '+%Y-%m-%d %H:%M UTC')  $run  \$$cost"; fi
      done <"$ledger"
    fi
    left=$(credits)
    if [ "$left" = unknown ]; then
      echo "credits: unknown (set FORK_CREDITS_START and FORK_CREDITS_SINCE from the billing console)"
    else
      echo "credits: \$$left remaining (floor \$$floor; Cost Explorer lags by about a day)"
    fi
    ;;
  *) echo "usage: cost_guard.sh check COST | record RUN COST | report" >&2; exit 2 ;;
esac
