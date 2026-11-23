#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Tests start_part.sh (Linux/WSL) with stubs: a fake `fork` (version, bench), a fake fork_datagen that
# records its arguments, a fake pgrep, a temporary folder for everything. Checks:
# - a running fork_datagen refuses the start (pgrep finds one), and the folder stays empty;
# - a bench mismatch, a wrong network and a wrong commit each refuse it before fork_datagen runs;
# - reused binaries of another target than ARCH (native) are not used: the script turns to a build of COMMIT
#   (which fails here, the repository being fake) and fork_datagen does not run;
# - a bad openings hash refuses it;
# - the passing case copies the reused binaries and runs fork_datagen with exactly the standing settings.
#     bash tools/control_center/test_start_part.sh
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
t=$(mktemp -d)
trap 'rm -rf "$t"' EXIT
fail=0
check() { if eval "$2"; then echo "ok: $1"; else echo "FAIL: $1"; fail=1; fi; }

mkdir -p "$t/bin" "$t/prev" "$t/part" "$t/data"
cat >"$t/bin/pgrep" <<'EOF'
#!/usr/bin/env bash
[ -e "$STUB_RUNNING" ]
EOF
cat >"$t/prev/fork" <<'EOF'
#!/usr/bin/env bash
case $1 in
  version) printf 'Fork 0.3.0-dev+%s\ncompiler clang 21.1.8\narch %s\nnet %s\n' "${STUB_COMMIT:-684bac6}" "${STUB_ARCH:-x86-64-v3}" "${STUB_NET:-s512r2}";;
  bench) printf 'nodes %s\nsignature 4cf778ff753861f7\nnps 1\n' "${STUB_NODES:-14180299}";;
esac
EOF
cat >"$t/prev/fork_datagen" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$STUB_ARGS"
EOF
chmod +x "$t/bin/pgrep" "$t/prev/fork" "$t/prev/fork_datagen"
echo "some openings" >"$t/data/open.epd"
sha=$(sha256sum "$t/data/open.epd" | cut -d' ' -f1)

setup() {  # $1: the part's folder, $2: the openings hash
  rm -rf "$1"
  mkdir -p "$t/state"
  cp "$here/start_part.sh" "$t/state/start_part.sh"
  cat >"$t/state/params.sh" <<EOF
NAME=g9f
DIR=$1
MODE=reuse
ARCH=x86-64-v3
REUSE_DIR=$t/prev
REPO=/nonexistent
BRANCH=phase-4
COMMIT=cccccccccccccccccccccccccccccccccccccccc
ENGINE_COMMIT=684bac6
NET=s512r2
WANT_NODES=14180299
WANT_SIGNATURE=4cf778ff753861f7
CLONE=$t/clone
BUILDS=$t/builds
OPENINGS=$t/data/open.epd
OPENINGS_SHA256=$2
TABLES=$t/tables
POSITIONS=447173594
NODES=20000
THREADS=10
SEED=20261111
HASH_MB=1
SHARD_MB=1024
ADJ_CP=700
ADJ_PLIES=8
SAVE_PERCENT=50
UNSAVED_NODES=4000
CHECK_NODES=2000
EOF
}
run() { PATH="$t/bin:$PATH" STUB_RUNNING="$t/running" STUB_ARGS="$t/args" bash "$t/state/start_part.sh" >"$t/out" 2>&1; }

touch "$t/running"
setup "$t/p1" "$sha"; rm -f "$t/args"; run; rc=$?
check "refused while fork_datagen runs" "[ $rc -ne 0 ] && grep -q 'already running' '$t/out' && [ ! -e '$t/args' ]"
check "the folder stays empty" "[ -z \"\$(ls -A '$t/p1')\" ]"
rm "$t/running"

setup "$t/p2" "$sha"; rm -f "$t/args"; STUB_NODES=1 run; rc=$?
check "refused on a bench mismatch" "[ $rc -ne 0 ] && grep -q 'BENCH MISMATCH' '$t/out' && [ ! -e '$t/args' ]"
setup "$t/p3" "$sha"; rm -f "$t/args"; STUB_NET=b0r2 run; rc=$?
check "refused on another network" "[ $rc -ne 0 ] && grep -q 'network is not s512r2' '$t/out' && [ ! -e '$t/args' ]"
setup "$t/p4" "$sha"; rm -f "$t/args"; STUB_COMMIT=1111111 run; rc=$?
check "refused on another commit" "[ $rc -ne 0 ] && grep -q 'not from 684bac6' '$t/out' && [ ! -e '$t/args' ]"
setup "$t/p7" "$sha"; rm -f "$t/args"; STUB_ARCH=native run; rc=$?
check "native binaries are rebuilt, not reused" "[ $rc -ne 0 ] && grep -q \"for 'native', not x86-64-v3: building\" '$t/out' && [ ! -e '$t/args' ]"
setup "$t/p5" "0000000000000000000000000000000000000000000000000000000000000000"; rm -f "$t/args"; run; rc=$?
check "refused on a bad openings hash" "[ $rc -ne 0 ] && [ ! -e '$t/args' ]"

setup "$t/p6" "$sha"; rm -f "$t/args"; run; rc=$?
want="--openings $t/data/open.epd --out $t/p6 --run g9f --positions 447173594 --nodes 20000 --threads 10 --seed 20261111 --hash-mb 1 --shard-mb 1024 --tables $t/tables --adjudicate-cp 700 --adjudicate-plies 8 --save-percent 50 --unsaved-nodes 4000 --check-nodes 2000"
check "the passing case runs fork_datagen" "[ $rc -eq 0 ] && [ -e '$t/args' ]"
check "with exactly the standing settings" "[ \"\$(tr '\n' ' ' <'$t/args' | sed 's/ \$//')\" = \"$want\" ]"
check "from the reused binaries" "cmp -s '$t/prev/fork' '$t/p6/fork' && cmp -s '$t/prev/fork_datagen' '$t/p6/fork_datagen'"
check "after the start line the seal reads" "grep -Eq 'g9f starting at .*\([0-9]{9,}\)' '$t/out'"
[ $fail -eq 0 ] && echo "start_part.sh: all checks passed" || { echo "start_part.sh: FAILED"; cat "$t/out"; exit 1; }
