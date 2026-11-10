#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Checks ld_book.py's file: fork_datagen with the full book and with the K-line file, same seed and settings
# (D20's and D100's), must write byte-identical shards.   bash ld_book_check.sh FULL SUB SEED
set -euo pipefail
FULL=$1 SUB=$2 SEED=$3
BIN=$HOME/fork-data/ld-builds/pgo
T=$HOME/fork-data/ld-bookcheck
rm -rf "$T"; mkdir -p "$T"
for cfg in "20000 1 9000" "100000 5 3000"; do
  set -- $cfg
  for book in full sub; do
    f=$FULL; [ $book = sub ] && f=$SUB
    d=$T/n$1-$book; mkdir -p "$d"
    "$BIN/fork_datagen" --openings "$f" --out "$d" --run chk --positions "$3" --nodes "$1" --threads 3 \
      --seed "$SEED" --hash-mb "$2" --shard-mb 1024 --tables "$HOME/fork-tools/syzygy/3-4-5" \
      --adjudicate-cp 700 --adjudicate-plies 8 --save-percent 50 --unsaved-nodes 4000 --check-nodes 2000 \
      2>&1 | tail -1
  done
  for s in "$T"/n$1-full/*.vf; do
    cmp "$s" "$T/n$1-sub/$(basename "$s")" && echo "identical: n$1 $(basename "$s") $(stat -c %s "$s") bytes"
  done
  ls "$T"/n$1-sub/*.vf | wc -l
done
rm -rf "$T"
