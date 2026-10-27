#!/usr/bin/env bash
# Fetches the match tools a cloud SPRT shard needs, pinned and checked
# (docs/kb/tools.md "Cloud SPRT"): the fastchess Linux release and the
# opening book, at the versions of the local test setup (branch kb,
# tools/versions.lock).
#
#   tools/cloud/fetch_tools.sh DIR      -> DIR/fastchess, DIR/UHO_Lichess_4852_v1.epd
#
# Needs curl, tar, unzip, sha256sum.
set -euo pipefail
dir=${1:?usage: fetch_tools.sh DIR}
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
echo "fetch_tools.sh: fastchess and the book in $dir"
