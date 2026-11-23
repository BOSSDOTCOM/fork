#!/usr/bin/env bash
# Fixture for tools/jobs/check_paths.py (never run): nothing in this file may be flagged.
. tools/jobs/paths.sh
PY=C:/tools/venv/Scripts/python.exe
B=C:/work/8b
W=$(fork_path win /c/work/8b)
U=/c/work/u
"$PY" -I -c "import json; json.dump({}, open(r'$B/ready.part.json', 'w'))"
"$PY" -I tool.py "$W/x" "$(fork_path win "$U/y")" "$(cygpath -m "$U/z")" "$(fork_path_for "$PY" "$HOME/q")"
U2=$(fork_path_for "$PY" "$U")
"$PY" tool.py "$U2/x" "$(pwd -W)/y"
ls "$U" /c/work >/dev/null  # Git Bash's own programs take /c/ paths
cat "$HOME/x" | "$PY" -I filter.py >"$U/out.txt" 2>>"$tmp/err.log"  # redirections are bash's own
"$PY" tool.py relative/dir "$1" "$name" '~/not-expanded'
"$PY" -c "print('x/c/y'); import re; re.sub('a/b/', '', 's')"
cmd.exe //c echo hi
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash /mnt/c/work/x.sh
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -e wslpath -a "$(pwd -W)"
fork_wsl -d Ubuntu -- bash /mnt/c/work/x.sh "$(fork_path wsl "$U/y")"
wsl.exe -d Ubuntu -- bash -lc "cd /mnt/c/work && ./x.sh"
"$PY" -I tool.py "$U/x"  # fork-paths: ok the tool takes Git Bash paths and converts them itself
# fork-paths: ok MSYS converts this bare argument; kept for the comparison test
"$PY" -I tool.py "$U/y"
python3 tool.py "$U/x"  # a bare python3 is not taken for a Windows program
"$PY" -I - "$W/r.json" <<'EOF'
import sys
print(open(sys.argv[1]).read())  # $B here is the program's text, not bash's
EOF
"$PY" -I - <<EOF
print(open('$W/x').read())
EOF
case $x in
  a) "$PY" tool.py "$W" ;;
  *) echo "$U" ;;
esac
ledger() { "$PY" -I tools/jobs/ledger.py "$@"; }
ledger record --file "$W/ledger.jsonl" --name "$1"
FORK_JOBS=$W/jobs "$PY" -I tools/jobs/jobctl.py status
SPRT_DATA=/c/work/sprt bash tools/github/sprt_run.sh x  # bash is Git Bash's own; the driver converts
plain() { echo "$@"; }
plain /c/work/x
export MSYS_NO_PATHCONV=1
wsl.exe -d Ubuntu -- bash /mnt/c/work/y.sh
