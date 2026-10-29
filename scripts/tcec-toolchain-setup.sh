#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Provisions the TCEC-toolchain check environment: a WSL distro running
# Ubuntu 22.04 with the compilers TCEC's servers have (gcc 11.4, g++-12,
# clang 16 and 19; docs/kb/competition.md on branch kb) and Ubuntu 22.04's
# own CMake (3.22). scripts/check.sh full builds Fork there with update.sh.
#
# One-time setup, from Windows (Git Bash or PowerShell):
#   wsl.exe --install -d Ubuntu-22.04 --no-launch
#   wsl.exe -d Ubuntu-22.04 -u root -e bash scripts/tcec-toolchain-setup.sh
# (run from the repo root; WSL maps the current directory). Re-runnable.
#
# clang 16 and 19 are not in Ubuntu 22.04's archive; they come from the LLVM
# project's apt repository (https://apt.llvm.org, suites
# llvm-toolchain-jammy-16 and -19, checked 2026-10-24: 16.0.6 and 19.1.7).
# Only the compiler packages are installed, no lld, as on a server where an
# admin ran `apt install clang-16`; the build must cope with that.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root: wsl.exe -d Ubuntu-22.04 -u root -e bash $0" >&2
  exit 1
fi
. /etc/os-release
if [ "$VERSION_ID" != 22.04 ]; then
  echo "expected Ubuntu 22.04, found $PRETTY_NAME" >&2
  exit 1
fi

# Under WSL, never stop at the first-launch user prompt: the check runs as
# root. (The same script provisions the ubuntu:22.04 container in CI.)
if grep -qi microsoft /proc/version && ! grep -q '^default=root' /etc/wsl.conf 2>/dev/null; then
  printf '[user]\ndefault=root\n' >>/etc/wsl.conf
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ca-certificates wget gnupg git cmake ninja-build g++ g++-12

keyring=/etc/apt/keyrings/apt.llvm.org.asc
install -d -m 0755 /etc/apt/keyrings
wget -qO "$keyring" https://apt.llvm.org/llvm-snapshot.gpg.key
for v in 16 19; do
  echo "deb [signed-by=$keyring] https://apt.llvm.org/jammy/ llvm-toolchain-jammy-$v main"
done >/etc/apt/sources.list.d/llvm.list
apt-get update -q
apt-get install -y -q clang-16 clang-19

echo
g++ --version | head -1
g++-12 --version | head -1
clang++-16 --version | head -1
clang++-19 --version | head -1
cmake --version | head -1
echo "ninja $(ninja --version)"
