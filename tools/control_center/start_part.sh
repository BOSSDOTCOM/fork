#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Starts one data-generation part in WSL for the Control Center, under the job supervisor
# (jobctl.py start datagen NAME -- bash start_part.sh), with params.sh beside it (written by datagen.py).
# The labeller policy (DESIGN.md section 5.3, deliverable 2): the current default engine, as
# - MODE=build: a clang PGO build of COMMIT (the tip of BRANCH) for the target ARCH (x86-64-v3 by default;
#   owner, 2026-11-12) in the app's own clone CLONE (never ~/fork), kept in BUILDS; or
# - MODE=reuse: the previous part's binaries from REUSE_DIR, when no engine file changed since their commit and
#   they were built for ARCH (binaries of another target, such as the native builds before 2026-11-12, are
#   rebuilt from COMMIT instead);
# either way bench-checked against tests/bench-NET.ref (WANT_NODES, WANT_SIGNATURE), its network, target and
# commit checked in `fork version`, and the openings checked by SHA-256. Then fork_datagen runs (exec, so a stop
# of the job reaches it) with the standing settings, with a CPU-load log beside it as earlier parts had.
set -euo pipefail
. "$(dirname "$0")/params.sh"
ARCH=${ARCH:-x86-64-v3}
say() { echo "$(TZ=EST5 date '+%Y-%m-%d %I:%M:%S %p EST') $NAME: $*"; }
say "commit $COMMIT ($BRANCH), net $NET, mode $MODE, seed $SEED, target $POSITIONS, $THREADS threads"
mkdir -p "$DIR"
[ -z "$(ls -A "$DIR" 2>/dev/null)" ] || { say "$DIR is not empty"; exit 1; }
if pgrep -x fork_datagen >/dev/null; then say "fork_datagen is already running"; exit 1; fi
if [ "$MODE" = reuse ]; then
  had=$("$REUSE_DIR/fork" version 2>/dev/null | sed -n 's/^arch //p')
  if [ "$had" != "$ARCH" ]; then
    say "the previous binaries are for '$had', not $ARCH: building $COMMIT instead"
    MODE=build ENGINE_COMMIT=$COMMIT
  fi
fi
if [ "$MODE" = build ]; then
  [ -d "$CLONE/.git" ] || git clone -q "$REPO" "$CLONE"
  cd "$CLONE"
  git fetch -q origin "$BRANCH"
  git checkout -q --detach "$COMMIT"
  [ "$(git rev-parse HEAD)" = "$COMMIT" ] || { say "checkout is not $COMMIT"; exit 1; }
  . scripts/env.sh >/dev/null
  net=$(sed -n 's|^set(FORK_NET "${CMAKE_SOURCE_DIR}/nets/\([A-Za-z0-9_]*\)\.fnet".*|\1|p' CMakeLists.txt)
  [ "$net" = "$NET" ] || { say "default network is $net, not $NET"; exit 1; }
  say "PGO build"
  nice -n 10 cmake -DSOURCE_DIR="$PWD" -DCXX="$FORK_CLANG_CXX" -DCOMPILER_ID=Clang -DARCH="$ARCH" -P cmake/pgo.cmake 2>&1 |
    tail -2
  nice -n 10 cmake --build build/clang-pgo --target fork fork_datagen 2>&1 | tail -1
  rm -rf "$BUILDS"; mkdir -p "$BUILDS"
  cp build/clang-pgo/fork build/clang-pgo/fork_datagen "$BUILDS/"
  src=$BUILDS
else
  src=$REUSE_DIR
fi
for f in fork fork_datagen; do cp "$src/$f" "$DIR/$f"; done
ver=$("$DIR/fork" version)
echo "$ver" | grep -E '^(Fork|arch|net) ' | tr '\n' ' '; echo
echo "$ver" | grep -qx "net $NET" || { say "the binary's network is not $NET"; exit 1; }
echo "$ver" | grep -qx "arch $ARCH" || { say "the binary is not built for $ARCH"; exit 1; }
echo "$ver" | grep -E '^Fork ' | grep -q "+${ENGINE_COMMIT:0:7}" || { say "the binary is not from $ENGINE_COMMIT"; exit 1; }
got=$("$DIR/fork" bench 2>&1 | grep -E '^(nodes|signature) ' | tr '\n' ' ')
want="nodes $WANT_NODES signature $WANT_SIGNATURE "
[ "$got" = "$want" ] || { say "BENCH MISMATCH ($got, want $want)"; exit 1; }
echo "bench ok: $got"
echo "$OPENINGS_SHA256  $OPENINGS" | sha256sum -c
sha256sum "$DIR/fork_datagen" "$DIR/fork" | sed "s#$HOME#~#g"
cd "$DIR"
bash -c '
  prev=($(head -1 /proc/stat))
  while sleep 60 && pgrep -x fork_datagen >/dev/null; do
    cur=($(head -1 /proc/stat))
    idle=$(( ${cur[4]} + ${cur[5]} - ${prev[4]} - ${prev[5]} ))
    total=0; for i in 1 2 3 4 5 6 7 8; do total=$(( total + ${cur[$i]} - ${prev[$i]} )); done
    echo "$(TZ=EST5 date "+%Y-%m-%d %I:%M %p") load1 $(cut -d" " -f1 /proc/loadavg) busy $(( 100 * (total - idle) / total ))%"
    prev=("${cur[@]}")
  done' >"$DIR/cpu-load.log" 2>&1 < /dev/null &
echo "$NAME starting at $(TZ=EST5 date '+%Y-%m-%d %I:%M:%S %p EST') ($(date +%s))"
exec ./fork_datagen --openings "$OPENINGS" --out "$DIR" \
  --run "$NAME" --positions "$POSITIONS" --nodes "$NODES" --threads "$THREADS" --seed "$SEED" \
  --hash-mb "$HASH_MB" --shard-mb "$SHARD_MB" --tables "$TABLES" \
  --adjudicate-cp "$ADJ_CP" --adjudicate-plies "$ADJ_PLIES" \
  --save-percent "$SAVE_PERCENT" --unsaved-nodes "$UNSAVED_NODES" --check-nodes "$CHECK_NODES" \
  >"$DIR/$NAME.log" 2>&1 < /dev/null
