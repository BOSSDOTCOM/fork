#!/usr/bin/env bash
# Fixture for tools/jobs/check_paths.py (never run): every line marked "want: RULE[, RULE]" must be flagged
# with exactly those rules, and no other line may be flagged.
PY=C:/tools/venv/Scripts/python.exe
B=/c/work/8b
M=/mnt/c/work/8b
G=$B/gates
# The 2026-11-10 incident: a Git Bash path inside -c code, which MSYS never converts.
"$PY" -I -c "import json; json.dump({}, open(r'$B/ready.part.json', 'w'))"  # want: msys-path
"$PY" -I tool.py /c/work/x.json  # want: msys-path
"$PY" -I tool.py "$G/x.json"  # want: msys-path
# The incident's second shape: NAME=PATH, rewritten by MSYS as a path list.
"$PY" -I tool.py "$G/cand.fnet=C:/work/layout.json"  # want: msys-path
"$PY" -I tool.py "$M/x"  # want: mount-path
"$PY" -I tool.py "$HOME/fork-jobs/x"  # want: posix-path
"$PY" -I tool.py ~/fork-jobs/x  # want: posix-path
here=$(cd "$(dirname "$0")" && pwd)
"$PY" -I "$here/x.py"  # want: posix-path
tmp=$(mktemp -d)
python.exe -c pass "$tmp/x"  # want: posix-path
out=$("$PY" -I - "$B/r.json" <<'EOF'  # want: msys-path
import json, sys
print(json.load(open(sys.argv[1])))  # a quoted heredoc's body is the program's own text
EOF
)
"$PY" -I - <<EOF
print(open('$B/x').read())  # want: msys-path
EOF
"$PY" -I - <<'EOF'
print(open('/c/work/x').read())  # want: msys-path
EOF
powershell.exe -NoProfile -Command "Get-Item $HOME/x"  # want: posix-path
wsl.exe -d Ubuntu -- bash /mnt/c/work/x.sh  # want: wsl-pathconv
wsl -d Ubuntu -- bash "$M/x.sh"  # want: wsl-pathconv
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash /c/work/x.sh  # want: wsl-form
# A job started from Git Bash: the WSL command's path reaches python.exe, which MSYS rewrites (exit 127).
"$PY" tools/jobs/jobctl.py start x -- wsl.exe -d Ubuntu -- bash /mnt/c/work/x.sh  # want: wsl-pathconv
"$PY" tools/jobs/jobctl.py start x -- bash "$B/x.sh"  # want: msys-path
for c in .venv/Scripts/python.exe .venv/bin/python python3; do
  if "$c" -c pass; then py=$c; break; fi
done
"$py" -I x.py "$G/y"  # want: msys-path
"${PYTHON:-python3}" x.py "$B/y"  # want: msys-path
note() { "$PY" -I "$B/morning.py" "$1"; }  # want: msys-path
x=$(C:/tools/gh.exe api "$B/z")  # want: msys-path
"$PY" x.py --opt="$B/z" || echo failed  # want: msys-path
files=("$B/a" "$B/b")
"$PY" x.py "${files[@]}"  # want: msys-path
data=${SPRT_DATA:-$HOME/fork-sprt}/run
"$PY" x.py "$data/design.json"  # want: posix-path
"$PY" x.py \
  --in "$B/a"  # want: msys-path
"$PY" x.py "$B/a"  # fork-paths: ok # want: bad-marker, msys-path
# The environment of a Windows program is rewritten like its arguments (/mnt/c/q arrives as C:/Program Files/...).
FORK_JOBS=$M/jobs "$PY" -I tools/jobs/jobctl.py status  # want: mount-path
# Functions that hand "$@" to a Windows program are checked at each call.
ledger() { "$PY" -I tools/jobs/ledger.py "$@"; }
ledger record --file "$B/ledger.jsonl"  # want: msys-path
wslrun() { wsl.exe -d Ubuntu --exec "$@" 2>/dev/null | tr -d '\r'; }
wslrun test -f /home/u/done  # want: wsl-pathconv
