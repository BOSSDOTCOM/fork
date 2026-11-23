# shellcheck shell=bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Path forms across Git Bash, PowerShell, Windows Python and WSL, and the outputs check behind "No silent done"
# (DESIGN.md section 1; owner, 2026-11-10, after retrain 8b's chain handed a Windows Python /c/... paths and
# reported "chain done" with no ready file). Source it:  . tools/jobs/paths.sh
# Its twin, tools/jobs/paths.py, follows the same rules; test_paths.py checks both on one table.
#
#   fork_path TARGET PATH       print PATH in TARGET's form; exit 2 if it has none
#       TARGET  win      C:/x, //wsl.localhost/DISTRO/x  Windows Python, PowerShell, jobctl, any .exe
#               winbs    C:\x, \\wsl.localhost\DISTRO\x  the same with backslashes (cmd.exe)
#               gitbash  /c/x                            Git Bash
#               wsl      /mnt/c/x, /home/x               WSL (a UNC path of another distribution has none)
#               here     the running environment's own form (gitbash in Git Bash, wsl in WSL or Linux)
#       PATH    /c/x (Git Bash), C:\x or C:/x (Windows), /mnt/c/x (WSL mount), \\wsl.localhost\DISTRO\x or
#               \\wsl$\DISTRO\x (UNC), wsl:/home/x or wsl:~/x (a path inside the WSL distribution, named from
#               anywhere), ~ or ~/x (this environment's home), or a relative path (only separators change).
#               Another absolute POSIX path (/tmp, /usr/bin, /home/x without wsl:) is the running
#               environment's: in Git Bash the MSYS root's, converted with cygpath; in WSL the distribution's.
#   fork_path_for PROGRAM PATH  PATH in the form PROGRAM takes: win for a Windows program, else here
#   fork_is_windows_program PROGRAM
#                               true for a Windows program: in Git Bash anything outside the MSYS root's /usr
#                               and /bin, in WSL a .exe; on plain Linux nothing
#   fork_wsl ARGS...            wsl.exe ARGS with Git Bash's argument conversion off, so /mnt/c/... and /home/...
#                               reach WSL as written (without it, /mnt/c/x arrives as C:/Program Files/Git/mnt/c/x)
#   fork_path_env               gitbash, wsl or linux ($FORK_PATH_ENV overrides, for tests)
#   fork_require_outputs SPEC...
#                               the outputs check: 0 if every output is valid, else 1, with one line per
#                               problem on stderr naming the file ("missing: F", "empty: F", "invalid JSON: F")
#       SPEC    FILE (present and not empty), json:FILE (also parses as JSON, through a Python given the
#               file in its own form, as an argument), any:FILE (present, may be empty)
#   fork_chain_done LABEL SPEC...
#                               a chain's last word: "LABEL done (N outputs verified)" and 0, or
#                               "LABEL failed: missing: F; ..." and 1, naming every missing or invalid output
#
# Settings: FORK_WSL_DISTRO (default $WSL_DISTRO_NAME inside WSL, else Ubuntu), FORK_WSL_HOME (the home for
# wsl:~, default asked of the distribution), FORK_PYTHON (the Python for JSON checks, default the repository's
# .venv, else python3, else python).

_fork_paths_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)

fork_path_env() {
  if [ -n "${FORK_PATH_ENV:-}" ]; then printf '%s\n' "$FORK_PATH_ENV"; return 0; fi
  if [ -z "${_fork_paths_env:-}" ]; then
    case $(uname -s 2>/dev/null) in
      MINGW* | MSYS* | CYGWIN*) _fork_paths_env=gitbash ;;
      *) if [ -n "${WSL_DISTRO_NAME:-}" ] || [ -e /proc/sys/fs/binfmt_misc/WSLInterop ]; then
           _fork_paths_env=wsl
         else
           _fork_paths_env=linux
         fi ;;
    esac
  fi
  printf '%s\n' "$_fork_paths_env"
}

_fork_distro() { printf '%s' "${FORK_WSL_DISTRO:-${WSL_DISTRO_NAME:-Ubuntu}}"; }

_fork_wsl_home() {  # env
  if [ -n "${FORK_WSL_HOME:-}" ]; then printf '%s' "$FORK_WSL_HOME"; return 0; fi
  case $1 in wsl | linux) printf '%s' "${HOME:-/root}"; return 0 ;; esac
  command -v wsl.exe >/dev/null 2>&1 || { echo "fork_path: wsl:~ needs FORK_WSL_HOME or wsl.exe" >&2; return 2; }
  local h
  h=$(MSYS_NO_PATHCONV=1 wsl.exe -d "$(_fork_distro)" -e sh -c 'printf %s "$HOME"' 2>/dev/null | tr -d '\r')
  case $h in /*) printf '%s' "$h" ;; *) echo "fork_path: cannot read the WSL home of $(_fork_distro)" >&2; return 2 ;; esac
}

# Sets _fp_kind (drive, distro or rel) and _fp_a, _fp_b: the drive letter and the rest (/... or empty), the
# distribution and its absolute path, or the relative path.
_fork_path_parse() {  # env path
  local env=$1 p=$2 in_wsl=0 h s lc r
  [ -n "$p" ] || { echo "fork_path: empty path" >&2; return 2; }
  case $p in wsl:*) in_wsl=1; p=${p#wsl:} ;; esac
  case $p in
    '~' | '~/'*)
      if [ $in_wsl = 1 ]; then h=$(_fork_wsl_home "$env") || return 2; else h=${HOME:-}; fi
      p=${h%/}${p:1} ;;
  esac
  local re_mount='^/mnt/([A-Za-z])(/.*)?$' re_gb='^/([A-Za-z])(/.*)?$' re_win='^([A-Za-z]):([\/].*)?$'
  if [[ $p =~ $re_mount ]] || { [ $in_wsl = 0 ] && { [[ $p =~ $re_gb ]] || [[ $p =~ $re_win ]]; }; }; then
    _fp_kind=drive _fp_a=${BASH_REMATCH[1],,} _fp_b=${BASH_REMATCH[2]//\\//}
    return 0
  fi
  s=${p//\\//}
  lc=${s,,}
  case $lc in
    //wsl.localhost/*) r=${s:16} ;;
    //wsl\$/*) r=${s:7} ;;
    *) r= ;;
  esac
  if [ -n "$r" ]; then
    _fp_kind=distro _fp_a=${r%%/*} _fp_b=${r#*/}
    [ "$_fp_b" = "$r" ] && _fp_b= || _fp_b=/$_fp_b
    _fp_b=${_fp_b:-/}
    return 0
  fi
  case $p in
    /*)
      if [ $in_wsl = 1 ] || [ "$env" != gitbash ]; then
        _fp_kind=distro _fp_a=$(_fork_distro) _fp_b=$p
        return 0
      fi
      command -v cygpath >/dev/null 2>&1 || { echo "fork_path: $p: a Git Bash (MSYS root) path needs cygpath" >&2; return 2; }
      local w
      w=$(cygpath -m -- "$p") || return 2
      [[ $w =~ $re_win ]] || { echo "fork_path: $p: cygpath gave '$w'" >&2; return 2; }
      _fp_kind=drive _fp_a=${BASH_REMATCH[1],,} _fp_b=${BASH_REMATCH[2]//\\//}
      return 0 ;;
  esac
  [ $in_wsl = 0 ] || { echo "fork_path: wsl:$p: not an absolute path" >&2; return 2; }
  _fp_kind=rel _fp_a=$p _fp_b=
}

fork_path() {  # target path
  [ $# -eq 2 ] || { echo "usage: fork_path win|winbs|gitbash|wsl|here PATH" >&2; return 2; }
  local target=$1 env out
  env=$(fork_path_env)
  case $target in
    win | winbs | gitbash | wsl) ;;
    here) if [ "$env" = gitbash ]; then target=gitbash; else target=wsl; fi ;;
    *) echo "fork_path: unknown target '$target' (win, winbs, gitbash, wsl or here)" >&2; return 2 ;;
  esac
  _fork_path_parse "$env" "$2" || return 2
  case $_fp_kind in
    rel)
      if [ "$target" = winbs ]; then out=${_fp_a//\//\\}; else out=${_fp_a//\\//}; fi ;;
    drive)
      local rest=${_fp_b:-/}
      case $target in
        win) out=${_fp_a^^}:$rest ;;
        winbs) out=${_fp_a^^}:$rest; out=${out//\//\\} ;;
        gitbash) out=/$_fp_a$rest ;;
        wsl) out=/mnt/$_fp_a$rest ;;
      esac ;;
    distro)
      if [ "$target" = wsl ]; then
        if [ "${_fp_a,,}" != "$(_fork_distro | tr '[:upper:]' '[:lower:]')" ]; then
          echo "fork_path: $2: a path of WSL distribution $_fp_a, not $(_fork_distro)" >&2
          return 2
        fi
        out=$_fp_b
      else
        out=//wsl.localhost/$_fp_a$_fp_b
        [ "$target" = winbs ] && out=${out//\//\\}
      fi ;;
  esac
  printf '%s\n' "$out"
}

fork_is_windows_program() {  # program
  local f
  f=$(command -v -- "$1" 2>/dev/null) || f=$1
  f=${f//\\//}
  case $(fork_path_env) in
    gitbash)
      case $f in /usr/* | /bin/* | */Git/usr/* | */Git/bin/*) return 1 ;; */* | *.[Ee][Xx][Ee]) return 0 ;; esac
      return 1 ;;
    wsl)
      case $f in *.[Ee][Xx][Ee] | /mnt/[A-Za-z]/*) return 0 ;; esac
      return 1 ;;
  esac
  return 1
}

fork_path_for() {  # program path
  [ $# -eq 2 ] || { echo "usage: fork_path_for PROGRAM PATH" >&2; return 2; }
  if fork_is_windows_program "$1"; then fork_path win "$2"; else fork_path here "$2"; fi
}

fork_wsl() { MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' wsl.exe "$@"; }

_fork_python() {
  local c
  for c in "${FORK_PYTHON:-}" "$_fork_paths_root/.venv/Scripts/python.exe" "$_fork_paths_root/.venv/bin/python" \
    python3 python; do
    [ -n "$c" ] || continue
    if command -v "$c" >/dev/null 2>&1 && "$c" -c pass >/dev/null 2>&1; then printf '%s\n' "$c"; return 0; fi
  done
  return 1
}

fork_require_outputs() {  # spec...
  [ $# -gt 0 ] || { echo "fork_require_outputs: no outputs named" >&2; return 2; }
  local spec kind f here bad=0 py i out conv
  local -a jsons=() names=()
  for spec in "$@"; do
    case $spec in
      json:*) kind=json f=${spec#json:} ;;
      any:*) kind=any f=${spec#any:} ;;
      *) kind=file f=$spec ;;
    esac
    here=$(fork_path here "$f" 2>/dev/null) || here=$f
    if [ ! -f "$here" ]; then echo "missing: $f" >&2; bad=1; continue; fi
    if [ "$kind" != any ] && [ ! -s "$here" ]; then echo "empty: $f" >&2; bad=1; continue; fi
    if [ "$kind" = json ]; then jsons+=("$here"); names+=("$f"); fi
  done
  [ ${#jsons[@]} -gt 0 ] || return $bad
  if ! py=$(_fork_python); then
    for f in "${names[@]}"; do echo "invalid JSON: $f (no Python to check it)" >&2; done
    return 1
  fi
  for i in "${!jsons[@]}"; do
    # The file in this Python's own form, as an argument: never inside the code (MSYS converts neither).
    conv=$(fork_path_for "$py" "${jsons[$i]}") || conv=${jsons[$i]}
    if ! out=$("$py" -I -c 'import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    json.load(f)' "$conv" 2>&1); then
      echo "invalid JSON: ${names[$i]} ($(printf '%s\n' "$out" | tail -1 | tr -d '\r'))" >&2
      bad=1
    fi
  done
  return $bad
}

fork_chain_done() {  # label spec...
  local label=${1:?fork_chain_done LABEL SPEC...} errs n
  shift
  n=$#
  if [ "$n" -eq 0 ]; then echo "$label failed: no outputs named to verify"; return 1; fi
  if errs=$(fork_require_outputs "$@" 2>&1 >/dev/null); then
    if [ "$n" -eq 1 ]; then echo "$label done (1 output verified)"; else echo "$label done ($n outputs verified)"; fi
    return 0
  fi
  echo "$label failed: $(printf '%s\n' "$errs" | tr -d '\r' | paste -sd ';' - | sed 's/;/; /g')"
  return 1
}
