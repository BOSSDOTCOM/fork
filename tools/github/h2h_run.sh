#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Head-to-head selection of a search constant's value on the GitHub shards (owner, DESIGN.md §6 2026-11-07
# decision 3): two or three candidate values, each a commit that differs only in the constant, played
# against each other on the same openings, and the value picked with its delta +/- e
# (tools/cloud/h2h_pick.py), as a row for the Search constants table.
#
#   tools/github/h2h_run.sh NAME --const CONSTANT --stages L --prefer LABEL --prefer-reason TEXT --idea ID \
#       [--tie-margin F] [--origin O] LABEL=COMMIT LABEL=COMMIT [LABEL=COMMIT]
#
#   NAME             label: $SPRT_DATA/NAME holds declaration.json, driver.log, pick.json and
#                    constants-line.md; pairing A-B's stages are the SPRT $SPRT_DATA/NAME.A-B
#   --const          the constant's name, as in the constants table
#   --stages L       stages per pairing, 1 to 4 (1,600 games each at STC)
#   --prefer LABEL   the value kept on a tie (the current or the simpler one), declared before any game,
#   --prefer-reason  with its reason ("the current value", "the simpler value")
#   --tie-margin F   the tie rule's margin in half-widths (default 0.5, owner 2026-11-07)
#   --origin O       the first stage index (default 0): the openings
#   --idea ID        the idea the constant belongs to (recorded; a selection is not an SPRT try)
#   LABEL=COMMIT     a candidate: the value as written in the table ([A-Za-z0-9._-], at most 16) and the
#                    commit that sets it (on GitHub)
#
# Two values play one pairing (the first listed as base), three a round robin (A-B, A-C, B-C), each
# through tools/github/sprt_run.sh --kind fixed --cap L --origin O, so with its rules (the supervisor, run
# titles, the ledger, the meta and shard checks) and on the same stage indices, hence the same opening
# lines. No pairing stops early. The declaration (the values, stages, preferred value, tie margin and
# conditions) is written before the first dispatch; a rerun with any other declaration is refused, and a
# rerun skips the pairings already complete. The winner then gets its design R SPRT against "off" on fresh
# openings (--origin O+L, printed at the end).
#
# Environment: as sprt_run.sh (TC, GAMES, HASH, SHARDS, TABLES, BASE_OPTS, TEST_OPTS, REF, REPO, GH,
# PYTHON, SPRT_DATA, POLL, FORK_JOBS, SPRT_UNSUPERVISED), passed through to every pairing. Runs only under
# the job supervisor: tools/jobs/jobctl.py start github NAME -- bash tools/github/h2h_run.sh NAME ...
#
# Exit status: 0 picked, 1 stopped (bad arguments, a changed declaration, a pairing that did not complete,
# or the picker's refusal).
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.."
const= stages= prefer= prefer_reason= tie_margin=0.5 origin=0 idea=
pos=()
while [ $# -gt 0 ]; do
  case $1 in
    --const | --stages | --prefer | --prefer-reason | --tie-margin | --origin | --idea)
      [ $# -ge 2 ] || { echo "h2h_run.sh: $1 needs a value" >&2; exit 1; }
      case $1 in
        --const) const=$2 ;;
        --stages) stages=$2 ;;
        --prefer) prefer=$2 ;;
        --prefer-reason) prefer_reason=$2 ;;
        --tie-margin) tie_margin=$2 ;;
        --origin) origin=$2 ;;
        --idea) idea=$2 ;;
      esac
      shift 2 ;;
    --*) echo "h2h_run.sh: unknown option $1" >&2; exit 1 ;;
    *) pos+=("$1"); shift ;;
  esac
done
set -- "${pos[@]}"
[ $# -ge 1 ] || { sed -n '8,21p' "$here/h2h_run.sh" >&2; exit 1; }
name=$1
shift
root=${SPRT_DATA:-$HOME/fork-sprt/github}
data=$root/$name
mkdir -p "$data"
say() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') $name: $*" | tee -a "$data/driver.log"; }
stop() { say "$*; stopping"; exit 1; }

py=${PYTHON:-}
if [ -z "$py" ]; then
  for c in .venv/Scripts/python.exe .venv/bin/python python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c pass >/dev/null 2>&1; then py=$c; break; fi
  done
fi
[ -n "$py" ] || stop "no Python for the pick"
[ -n "${FORK_JOB:-}" ] || [ "${SPRT_UNSUPERVISED:-}" = 1 ] ||
  stop "not started by the job supervisor (tools/jobs/jobctl.py start github $name -- $0 ...)"

[ $# -ge 2 ] && [ $# -le 3 ] || stop "a head-to-head takes 2 or 3 values (LABEL=COMMIT), not $#"
[[ $name =~ ^[A-Za-z0-9_-]+$ ]] || stop "NAME '$name' must be [A-Za-z0-9_-] (pairings are NAME.A-B)"
[ -n "$const" ] || stop "--const names the constant"
case $stages in 1 | 2 | 3 | 4) ;; *) stop "--stages takes 1 to 4 stages per pairing" ;; esac
case $origin in '' | *[!0-9]*) stop "--origin takes a whole number" ;; esac
[[ $tie_margin =~ ^[0-9]+(\.[0-9]+)?$ ]] && [ "$tie_margin" != 0 ] || stop "--tie-margin takes a positive number"
[ -n "${prefer_reason//[[:space:]]/}" ] || stop "--prefer-reason says why the preferred value (the current or the simpler one)"
[ -n "$idea" ] || stop "--idea names the idea the constant belongs to"
labels=() shas=()
for v in "$@"; do
  label=${v%%=*} commit=${v#*=}
  [ "$label" != "$v" ] && [[ $label =~ ^[A-Za-z0-9._-]{1,16}$ ]] || stop "'$v' is not LABEL=COMMIT (LABEL [A-Za-z0-9._-], at most 16)"
  sha=$(git rev-parse --verify --quiet "$commit^{commit}") || stop "$label: $commit is not a commit in this clone"
  for i in "${!labels[@]}"; do
    [ "${labels[$i]}" != "$label" ] || stop "the value $label is listed twice"
    [ "${shas[$i]}" != "$sha" ] || stop "the values ${labels[$i]} and $label are the same commit"
  done
  labels+=("$label") shas+=("$sha")
done
case " ${labels[*]} " in *" $prefer "*) ;; *) stop "--prefer '$prefer' is not one of the values (${labels[*]})" ;; esac

# The declaration: written before the first dispatch, compared on a rerun.
values=()
for i in "${!labels[@]}"; do values+=("${labels[$i]}=${shas[$i]}"); done
why=$("$py" -I - "$data/declaration.json" "$const" "$stages" "$origin" "$prefer" "$prefer_reason" "$tie_margin" \
  "$idea" "${TC:-8+0.08}" "${HASH:-}" "${GAMES:-}" "${SHARDS:-16}" "${values[@]}" <<'EOF'
import json, sys, time
path = sys.argv[1]
keys = ('const', 'stages', 'origin', 'prefer', 'prefer_reason', 'tie_margin', 'idea', 'tc', 'hash', 'games', 'shards')
want = dict(zip(keys, sys.argv[2:13]))
want['values'] = dict(v.split('=', 1) for v in sys.argv[13:])
try:
    have = json.load(open(path, encoding='utf-8'))
except FileNotFoundError:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(dict(want, declared_at=time.strftime('%Y-%m-%dT%H:%M:%S%z')), f, indent=1)
    sys.exit(0)
have.pop('declared_at', None)
for k in sorted(set(want) | set(have)):
    if want.get(k) != have.get(k) or (k == 'values' and list(want[k]) != list(have.get(k, {}))):
        print(f'{k} {want.get(k)!r} differs from the declaration\'s {have.get(k)!r} ({path})')
        sys.exit(1)
EOF
) || stop "the requested head-to-head: $why"

say "head-to-head of $const: values ${labels[*]}, $stages stage(s) per pairing from stage $origin, prefer $prefer ($prefer_reason), tie margin $tie_margin e, idea $idea"
for i in "${!labels[@]}"; do
  for j in "${!labels[@]}"; do
    [ "$j" -gt "$i" ] || continue
    pairing=$name.${labels[$i]}-${labels[$j]}
    if [ "$(cat "$root/$pairing/verdict" 2>/dev/null)" = complete ]; then
      say "pairing $pairing: complete, skipped"
      continue
    fi
    say "pairing $pairing: ${labels[$i]} (base) against ${labels[$j]} (test)"
    bash tools/github/sprt_run.sh --kind fixed --idea "$idea" --cap "$stages" --origin "$origin" \
      "$pairing" "${shas[$i]}" "${shas[$j]}"
    status=$?
    [ "$status" = 0 ] && [ "$(cat "$root/$pairing/verdict" 2>/dev/null)" = complete ] ||
      stop "pairing $pairing stopped (sprt_run.sh exit $status; see $root/$pairing/driver.log)"
  done
done
picked=$("$py" -I tools/cloud/h2h_pick.py "$data" "$root" 2>&1) || stop "the pick: $picked"
echo "$picked" | sed 's/^/    /' | tee -a "$data/driver.log"
winner=$(sed -n 's/^winner: \([^ ]*\).*/\1/p' <<<"$picked")
for i in "${!labels[@]}"; do [ "${labels[$i]}" != "$winner" ] || commit=${shas[$i]}; done
say "picked $winner (pick.json, constants-line.md); next, its design R SPRT against off on fresh openings:" \
  "tools/github/sprt_run.sh --kind search --idea $idea --origin $((origin + stages)) NAME OFF-COMMIT $commit"
exit 0
