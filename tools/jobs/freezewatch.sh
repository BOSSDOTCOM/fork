#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Freeze watch (owner, 2026-11-12: report whether the PC's freezes stop). Wakes every FREEZEWATCH_TICK seconds
# (default 5) and logs any wake-up that came more than FREEZEWATCH_STALL seconds after the last one (default 20:
# the PC was unresponsive), with Windows' available memory and commit charge at that moment; a heartbeat line
# every FREEZEWATCH_HEARTBEAT seconds (default 1800). Read-only: it changes nothing.
#
# No process per tick (owner, 2026-11-24, the token leak's option d: every process start leaks kernel token
# objects on this PC). The tick sleeps with bash's read -t on a FIFO held open read-write (it never gets data, so
# read waits out its timeout) and reads the clock with printf's %(...)T, both builtins. Only a stall or a heartbeat
# starts a process (one PowerShell for the memory counters). The earlier version started sleep, date and a
# subshell every 5 seconds, about 2,000 process starts an hour.
#
# Log lines (the Operations Display parses "heartbeat: N stalls so far; avail M MB, commit P%" and "STALL: N s",
# tools/ops_display/readers.py freezewatch()): "YYYY-MM-DD hh:mm:ss AM EST <message>".
#   FREEZEWATCH_LOG   the log (default ~/fork-jobs/night/freezewatch.log)
#   FREEZEWATCH_TICKS stop after this many ticks (default 0: run forever; tests only)
#   FREEZEWATCH_MEM   a fixed memory text instead of asking PowerShell (tests only)
L=${FREEZEWATCH_LOG:-$HOME/fork-jobs/night/freezewatch.log}
TICK=${FREEZEWATCH_TICK:-5}
STALL=${FREEZEWATCH_STALL:-20}
HEARTBEAT=${FREEZEWATCH_HEARTBEAT:-1800}
TICKS=${FREEZEWATCH_TICKS:-0}
say() { local t; TZ=EST5 printf -v t '%(%Y-%m-%d %I:%M:%S %p)T' -1; echo "$t EST $*" >>"$L"; }
mem() {
  if [ -n "${FREEZEWATCH_MEM:-}" ]; then echo "$FREEZEWATCH_MEM"; return; fi
  powershell.exe -NoProfile -Command "'avail ' + (Get-Counter '\Memory\Available MBytes').CounterSamples[0].CookedValue + ' MB, commit ' + [math]::Round((Get-Counter '\Memory\% Committed Bytes In Use').CounterSamples[0].CookedValue,1) + '%'" 2>/dev/null | tr -d '\r'
}
# The sleeper: a FIFO opened read-write never reaches end-of-file and never gets data. Its name is removed at once;
# the open descriptor keeps it alive.
fifo=$(mktemp -u "${TMPDIR:-/tmp}/freezewatch-XXXXXX") && mkfifo "$fifo" && exec {SLEEPER}<>"$fifo" && rm -f "$fifo" ||
  { echo "freezewatch: cannot make its sleeper FIFO" >&2; exit 1; }
say "freezewatch started (pid $$): ${TICK} s tick, a stall is a gap of more than ${STALL} s, no process per tick; $(mem)"
printf -v prev '%(%s)T' -1; beat=$prev; stalls=0; n=0
while :; do
  read -r -t "$TICK" -u "$SLEEPER" _
  printf -v now '%(%s)T' -1; gap=$((now - prev))
  if [ "$gap" -gt "$STALL" ]; then stalls=$((stalls + 1)); say "STALL: ${gap} s between ticks (expected ${TICK}); $(mem)"; fi
  if [ $((now - beat)) -ge "$HEARTBEAT" ]; then say "heartbeat: $stalls stalls so far; $(mem)"; beat=$now; fi
  prev=$now
  n=$((n + 1)); [ "$TICKS" -gt 0 ] && [ "$n" -ge "$TICKS" ] && break
done
exit 0
