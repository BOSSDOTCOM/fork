#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later

# Builds tools/overlap/overlap_audit.cpp into OUT (default build/overlap/fork_overlap_audit[.exe]) from Fork's core
# and the game-record reader only, one compile at a time (a small, low-memory build; not part of CMake, so the
# engine's builds and CI are unchanged). Uses the clang of scripts/env.sh.
#
#   bash tools/overlap/build.sh [OUT]
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
. "$root/scripts/env.sh" >/dev/null
exe=""
case "$(uname -s)" in MINGW* | MSYS* | CYGWIN*) exe=".exe" ;; esac
out="${1:-$root/build/overlap/fork_overlap_audit$exe}"
obj="$(dirname "$out")/obj"
mkdir -p "$obj"
flags=(-std=c++20 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Wshadow -Werror -I "$root/src")
srcs=(src/core/bitboard.cpp src/core/movegen.cpp src/core/position.cpp src/core/zobrist.cpp
  src/datagen/game_record.cpp tools/overlap/overlap_audit.cpp)
objs=()
for s in "${srcs[@]}"; do
  o="$obj/$(basename "${s%.cpp}").o"
  "$FORK_CLANG_CXX" "${flags[@]}" -c "$root/$s" -o "$o"
  objs+=("$o")
done
"$FORK_CLANG_CXX" "${objs[@]}" -o "$out"
echo "built $out"
