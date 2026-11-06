#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The push gate's personal-data scan (owner, 2026-11-05: the scan completes
# and passes in its own step before any push; a hit blocks the push). The
# repository is public, so everything a push publishes, history included,
# is scanned first: every added line of every commit the remote does not
# have yet.
#
#   scripts/scan-push.sh REF...        scan what pushing REF... would publish
#   scripts/scan-push.sh --pre-push    the same for the refs git hands the
#                                      pre-push hook on standard input
#
# A hit is any of:
# - this machine's user name, or a home path with it (C:\Users\<name>,
#   /c/Users/<name>, /mnt/c/Users/<name>, /home/<name>), the names read from
#   the environment at run time, so the script itself holds none;
# - a pattern from the private patterns file (FORK_SCAN_PATTERNS, default
#   ~/.config/fork-private-patterns: one extended regular expression per
#   line, # for comments; kept outside the repository, it holds the
#   personal email and the cloud account's identifiers);
# - a credential's shape: an AWS access key id, a GitHub token, a private
#   key block, a Slack token.
# Hits are reported by commit, file and kind; a private pattern's match is
# never printed. Exit status: 0 clean, 1 a hit, 2 a scan that could not run
# (which blocks too).
set -uo pipefail

commits=()
if [ "${1:-}" = --pre-push ]; then
  while read -r local_ref local_sha remote_ref remote_sha; do
    [ -n "${local_sha:-}" ] || continue
    case $local_sha in *[!0]*) ;; *) continue ;; esac  # a deleted ref publishes nothing
    mapfile -t -O "${#commits[@]}" commits < <(git rev-list "$local_sha" --not --remotes) || exit 2
  done
else
  [ $# -gt 0 ] || { sed -n '9,13p' "$0" >&2; exit 2; }
  for ref in "$@"; do
    git rev-parse --verify -q "$ref^{commit}" >/dev/null || { echo "scan-push: no commit $ref" >&2; exit 2; }
    mapfile -t -O "${#commits[@]}" commits < <(git rev-list "$ref" --not --remotes) || exit 2
  done
fi

# Names from the environment (Windows and Unix), deduplicated, at least 3 characters.
names=()
for n in "${USERNAME:-}" "${USER:-}" "$(basename "${USERPROFILE:-}")" "$(basename "${HOME:-}")" "$(id -un 2>/dev/null)"; do
  [ ${#n} -ge 3 ] || continue
  case " ${names[*]-} " in *" $n "*) ;; *) names+=("$n") ;; esac
done
home_res=()
for n in "${names[@]}"; do
  q=$(printf '%s' "$n" | sed 's/[][\.*^$+?(){}|/]/\\&/g')
  home_res+=("[Uu]sers[\\\\/]+$q([^A-Za-z0-9_-]|\$)" "/home/$q([^A-Za-z0-9_-]|\$)" "(^|[^A-Za-z0-9_])$q([^A-Za-z0-9_]|\$)")
done
private=${FORK_SCAN_PATTERNS:-$HOME/.config/fork-private-patterns}
private_res=()
if [ -f "$private" ]; then
  while IFS= read -r line; do
    line=${line%$'\r'}
    case $line in '' | '#'*) continue ;; esac
    private_res+=("$line")
  done <"$private"
fi
secret_res=('AKIA[0-9A-Z]{16}' 'gh[pousr]_[A-Za-z0-9]{30,}' 'github_pat_[A-Za-z0-9_]{20,}'
  '-----BEGIN [A-Z ]*PRIVATE KEY-----' 'xox[abprs]-[A-Za-z0-9-]{10,}')

hits=0
for c in "${commits[@]}"; do
  # Added lines only, each prefixed by its file, from the commit's own patch
  # (a merge's against its first parent).
  added=$(git show --format= --unified=0 --no-color --first-parent -m "$c" |
    awk '/^\+\+\+ /{f=substr($0,7); next} /^\+/{print f "\t" substr($0,2)}') || exit 2
  [ -n "$added" ] || continue
  report() {  # kind, regexes...
    local kind=$1 re file
    shift
    for re in "$@"; do
      while IFS= read -r file; do
        [ -n "$file" ] || continue
        echo "scan-push: HIT in ${c:0:12} $file ($kind)" >&2
        hits=$((hits + 1))
      done < <(printf '%s\n' "$added" | grep -E -i -- "$re" | cut -f1 | sort -u)
    done
  }
  [ ${#home_res[@]} -gt 0 ] && report "user name or home path" "${home_res[@]}"
  [ ${#private_res[@]} -gt 0 ] && report "a private pattern" "${private_res[@]}"
  report "a credential's shape" "${secret_res[@]}"
done
if [ "$hits" -gt 0 ]; then
  echo "scan-push: $hits hit(s) in ${#commits[@]} commit(s): the push is blocked" >&2
  exit 1
fi
echo "scan-push: ${#commits[@]} commit(s) scanned, clean"
