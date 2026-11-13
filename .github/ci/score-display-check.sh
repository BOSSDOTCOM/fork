#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The workflows' CalibratedScore belt (owner, 2026-11-13: "make every harness force the option off by default,
# including branch workflows, with a test"). Run from the checkout's root in a workflow's build job, after the
# engines are built and before any game:
#
#   bash .github/ci/score-display-check.sh ENGINE...
#
# If any ENGINE advertises the CalibratedScore option (Fork since c7a61ea, default on: it changes the centipawn
# numbers fastchess adjudicates on), the harness this run uses, this checkout's tools/, scripts/, bench/ and
# .github/, must pass tools/check_score_display_off.py (every launcher sets the option off); otherwise the run
# stops here. An engine without the option needs nothing. tools/check_score_display_off.py fails on a workflow
# that plays games without this step. PYTHON: default python3.
set -uo pipefail
py=${PYTHON:-python3}
[ $# -ge 1 ] || { echo "usage: score-display-check.sh ENGINE..." >&2; exit 2; }
with=()
for e in "$@"; do
  [ -x "$e" ] || { echo "score-display-check.sh: no engine $e" >&2; exit 1; }
  # The whole option list first, then the search: a grep that stops early must not kill the engine mid-answer.
  list=$(printf 'uci\nquit\n' | timeout 30 "$e" 2>/dev/null | tr -d '\r')
  grep -q '^uciok$' <<<"$list" || { echo "score-display-check.sh: $e did not answer uciok" >&2; exit 1; }
  if grep -qE '^option name CalibratedScore( |$)' <<<"$list"; then with+=("$e"); fi
done
if [ ${#with[@]} -eq 0 ]; then
  echo "score-display-check.sh: no engine advertises CalibratedScore: nothing to force off"
  exit 0
fi
if [ ! -f tools/check_score_display_off.py ]; then
  echo "::error::${with[*]} advertise CalibratedScore (default on), but this harness has no tools/check_score_display_off.py: dispatch from a ref that contains c7a61ea" >&2
  exit 1
fi
if ! out=$("$py" -I -B tools/check_score_display_off.py . 2>&1); then
  echo "$out" >&2
  echo "::error::${with[*]} advertise CalibratedScore (default on), but this harness does not force it off (tools/check_score_display_off.py above)" >&2
  exit 1
fi
echo "score-display-check.sh: ${with[*]} advertise CalibratedScore; this harness forces it off ($out)"
