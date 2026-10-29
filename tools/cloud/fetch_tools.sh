#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Fetches the match tools a cloud SPRT shard needs, pinned and checked
# (docs/kb/tools.md "Cloud SPRT"): the fastchess Linux release and the
# opening book, at the versions of the local test setup (branch kb,
# tools/versions.lock).
#
#   tools/cloud/fetch_tools.sh DIR      -> DIR/fastchess, DIR/UHO_Lichess_4852_v1.epd,
#                                          DIR/UHO_Lichess_4852_v1.shuffled-SEED.epd
#
# The shards play the shuffled copy: a fixed-seed permutation of the book
# (tools/cloud/shuffle_book.py), because they take consecutive lines and the
# book's first lines are unrepresentative (audit-1 U-3: 30% of lines 1-800
# are at move 4 or earlier, against 1.8% of the whole book). Its SHA-256 is
# pinned too. Needs curl, tar, unzip, sha256sum, python3.
set -euo pipefail
dir=${1:?usage: fetch_tools.sh DIR}
# Before the cd below: $0 may be a relative path (the shards run
# "bash tools/cloud/fetch_tools.sh DIR"), which a cd would break.
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$dir"
cd "$dir"

# fastchess v1.8.2-alpha (commit f618e345), the Linux x86-64 release.
fc_url=https://github.com/Disservin/fastchess/releases/download/v1.8.2-alpha/fastchess-linux-x86-64.tar
fc_sha=1003f920bebe841acdab5e6d7871e93171a4586857b3ec91c21ef5777f26ff96
# UHO_Lichess_4852_v1.epd (official-stockfish/books at a804a97e, CC0-1.0;
# test openings only, KB data-policy.md): the zip, then the unpacked book's
# own checksum (2,632,036 positions; the same file as the local setup's).
book_url=https://raw.githubusercontent.com/official-stockfish/books/a804a97e709f40aa75a00f9d19e84915b7a3a45c/UHO_Lichess_4852_v1.epd.zip
book_sha=7a7f6470615a69c6cf23d565417701d38732876f480af90d67b42abade35644a
# The permutation's seed (the date it was chosen, 2026-10-27) and the
# shuffled book's SHA-256 (computed with shuffle_book.py from the book above,
# twice, with the same result; its first 800 lines then average move 7.47,
# share at move 4 or earlier 1.1%, against 7.41 and 1.8% for the whole).
book_seed=20261027
shuffled=UHO_Lichess_4852_v1.shuffled-$book_seed.epd
shuffled_sha=51eb21c01ab03f1caa96a5205268faf6f11f26547dc9e0e7ab6a574181b4dbdc

if [ ! -x fastchess ]; then
  curl -fsSL --retry 3 -o fastchess.tar "$fc_url"
  echo "$fc_sha  fastchess.tar" | sha256sum -c --quiet
  mkdir -p fc && tar -xf fastchess.tar -C fc
  bin=$(find fc -type f -name 'fastchess*' -perm -u+x | head -n 1)
  [ -n "$bin" ] || { echo "fetch_tools.sh: no fastchess binary in the release" >&2; exit 1; }
  mv "$bin" fastchess && rm -rf fc fastchess.tar
fi
if [ ! -f UHO_Lichess_4852_v1.epd ]; then
  curl -fsSL --retry 3 -o book.zip "$book_url"
  unzip -q -o book.zip && rm -f book.zip
fi
echo "$book_sha  UHO_Lichess_4852_v1.epd" | sha256sum -c --quiet
if ! echo "$shuffled_sha  $shuffled" | sha256sum -c --quiet --status 2>/dev/null; then
  python3 -I "$here/shuffle_book.py" --seed "$book_seed" UHO_Lichess_4852_v1.epd "$shuffled"
fi
echo "$shuffled_sha  $shuffled" | sha256sum -c --quiet
echo "fetch_tools.sh: fastchess, the book and its shuffled copy (seed $book_seed) in $dir"
