#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# CI (Windows, Git Bash): the local development toolchain, pinned.
#
#   .github/ci/win-tools.sh install llvm-mingw|winlibs   download what is
#       missing under $FORK_TOOLS (default C:/fork-tools), verify each
#       archive's SHA-256 before extracting it: the compiler named, plus
#       CMake and Ninja
#   . .github/ci/win-tools.sh env                         (sourced) set
#       FORK_CLANG_CXX / FORK_GCC_CXX and PATH the way scripts/env.sh does
#       for the winget installs: LLVM-MinGW, CMake and Ninja first, WinLibs
#       last (LLVM-MinGW ships its own g++.exe, really clang; CLAUDE.md)
#
# The same releases as the owner's winget installs (2026-10-28):
#   MartinStorsjo.LLVM-MinGW.UCRT 23.1.3-20261006 (clang 23.1.3)
#   BrechtSanders.WinLibs.POSIX.UCRT 16.2.0-14.0.0-r2 (GCC 16.2.0, MinGW-w64 UCRT 14.0.0)
#   Kitware.CMake 4.4.4, Ninja-build.Ninja 1.13.2
# URLs and SHA-256s from the winget-pkgs installer manifests
# (github.com/microsoft/winget-pkgs, manifests/m/MartinStorsjo/LLVM-MinGW/UCRT/
# 23.1.3-20261006, manifests/b/BrechtSanders/WinLibs/POSIX/UCRT/16.2.0-14.0.0-r2,
# manifests/k/Kitware/CMake/4.4.4, manifests/n/Ninja-build/Ninja/1.13.2: the
# x64 zip entries' InstallerSha256), each identical to the digest GitHub
# lists for that release asset (checked 2026-10-28).
#
# Bump a version by editing this file: the CI cache key hashes it.
[ "${BASH_SOURCE[0]}" = "$0" ] && set -euo pipefail  # strict only when run, not when sourced

FORK_TOOLS=${FORK_TOOLS:-C:/fork-tools}

fork_tools_env() {
  local root=$FORK_TOOLS
  case "$root" in [A-Za-z]:*) root=$(cygpath -u "$root") ;; esac
  local llvm=$root/llvm-mingw/llvm-mingw-20261006-ucrt-x86_64
  local gcc=$root/winlibs/mingw64/bin
  local cmk=$root/cmake/cmake-4.4.4-windows-x86_64
  local nin=$root/ninja
  local front="$cmk/bin:$nin" back=""
  if [ -d "$llvm" ]; then
    FORK_CLANG_CXX="$(cygpath -m "$llvm/bin/clang++.exe")"
    export FORK_CLANG_CXX
    front="$llvm/bin:$front"
  fi
  if [ -d "$gcc" ]; then
    FORK_GCC_CXX="$(cygpath -m "$gcc/g++.exe")"
    export FORK_GCC_CXX
    back=":$gcc"
  fi
  export PATH="$front:$PATH$back"
}

fetch() {  # url sha256 dest-dir
  local url=$1 sha=$2 dest=$3 tmp file
  if [ -d "$dest" ] && [ -n "$(ls -A "$dest" 2>/dev/null)" ]; then
    echo "have $dest (cache hit)"
    return 0
  fi
  tmp=$(mktemp -d)
  file=$tmp/$(basename "$url")
  echo "downloading $url"
  curl -fsSL --retry 3 -o "$file" "$url"
  echo "$sha  $file" | sha256sum -c -
  rm -rf "$dest" && mkdir -p "$dest"
  local sz=7z
  command -v 7z >/dev/null || sz="/c/Program Files/7-Zip/7z.exe"
  "$sz" x -y -bd -o"$(cygpath -w "$dest")" "$(cygpath -w "$file")" >/dev/null
  rm -rf "$tmp"
  echo "extracted into $dest"
}

case "${1:-}" in
  env)
    fork_tools_env
    ;;
  install)
    which=${2:?llvm-mingw or winlibs}
    root=$FORK_TOOLS
    case "$which" in
      llvm-mingw)
        fetch https://github.com/mstorsjo/llvm-mingw/releases/download/20261006/llvm-mingw-20261006-ucrt-x86_64.zip \
          317492c456aa27ee607a5919f1d2d38dcdc1112516a24d0bf4b00d078f52d17a "$root/llvm-mingw"
        ;;
      winlibs)
        fetch https://github.com/brechtsanders/winlibs_mingw/releases/download/16.2.0posix-14.0.0-ucrt-r2/winlibs-x86_64-posix-seh-gcc-16.2.0-mingw-w64ucrt-14.0.0-r2.zip \
          d5dbafc4a170e762ca6143151ec918fb9e2c72736fb14cd704abebc6bdd5276a "$root/winlibs"
        ;;
      *) echo "unknown toolchain $which" >&2; exit 2 ;;
    esac
    fetch https://github.com/Kitware/CMake/releases/download/v4.4.4/cmake-4.4.4-windows-x86_64.zip \
      bace36e94b31c68ab6fa295f26dfa11219e0701cf7c94b0284a7d1cb13dac536 "$root/cmake"
    fetch https://github.com/ninja-build/ninja/releases/download/v1.13.2/ninja-win.zip \
      07fc8261b42b20e71d1720b39068c2e14ffcee6396b76fb7a795fb460b78dc65 "$root/ninja"
    fork_tools_env
    echo "cmake: $(cmake --version | head -n 1)"
    echo "ninja: $(ninja --version)"
    if [ -n "${FORK_CLANG_CXX:-}" ]; then echo "clang: $("$FORK_CLANG_CXX" --version | head -n 1)"; fi
    if [ -n "${FORK_GCC_CXX:-}" ]; then echo "gcc: $("$FORK_GCC_CXX" --version | head -n 1)"; fi
    ;;
  *)
    echo "usage: win-tools.sh install llvm-mingw|winlibs, or source it with: env" >&2
    return 2 2>/dev/null || exit 2
    ;;
esac
