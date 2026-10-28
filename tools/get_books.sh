#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Downloads the SPRT opening book into ~/fork-tools/books (run in WSL).
#
# UHO_Lichess_4852_v1.epd from official-stockfish/books (CC0-1.0), pinned to
# commit 426eca42 (2023-10-21), where it was added. Test openings only, never
# training data (owner, 2026-10-24; KB data-policy.md decision 6). Its
# positions come from Lichess games, selected by an engine's draw rate, so
# nothing derived from it may enter Fork's training or tuning data.
set -euo pipefail

dest=$HOME/fork-tools/books
url=https://github.com/official-stockfish/books/raw/426eca422c202ef381a1380ada1873a7f185c4b9/UHO_Lichess_4852_v1.epd.zip
zip_sha=4e298f11e8acfa106babe02968f2e61582145e7874c59284690b20b9650e0e07
epd_sha=7a7f6470615a69c6cf23d565417701d38732876f480af90d67b42abade35644a

mkdir -p "$dest"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/book.zip" "$url"
[ "$(sha256sum "$tmp/book.zip" | cut -d' ' -f1)" = "$zip_sha" ] || { echo "get_books.sh: zip SHA-256 mismatch" >&2; exit 1; }
python3 -I -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extract("UHO_Lichess_4852_v1.epd", sys.argv[2])' \
  "$tmp/book.zip" "$tmp"
[ "$(sha256sum "$tmp/UHO_Lichess_4852_v1.epd" | cut -d' ' -f1)" = "$epd_sha" ] || { echo "get_books.sh: epd SHA-256 mismatch" >&2; exit 1; }
mv "$tmp/UHO_Lichess_4852_v1.epd" "$dest/"
echo "get_books.sh: $dest/UHO_Lichess_4852_v1.epd ($(wc -l <"$dest/UHO_Lichess_4852_v1.epd") positions)"
