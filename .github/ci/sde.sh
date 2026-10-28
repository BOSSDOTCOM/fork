#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# CI: Intel Software Development Emulator (SDE), to run binaries built for a
# CPU level the runner lacks (GitHub's hosted runners may have no AVX-512).
#
#   .github/ci/sde.sh needs ARCH         exit 0 when this CPU cannot run a
#                                        FORK_ARCH=ARCH build (prints the
#                                        CPU and the missing flags), else 1;
#                                        FORK_CI_FORCE_SDE=1 forces SDE for
#                                        x86-64-v4 (to test this path)
#   .github/ci/sde.sh install DIR        download (pinned SHA-256) and
#                                        extract SDE into DIR, unless there
#   .github/ci/sde.sh wrap DIR BIN OUT   write OUT, a script running BIN
#                                        under SDE (same arguments, stdin,
#                                        stdout and exit status)
#   .github/ci/sde.sh inplace DIR BIN... move each BIN to BIN.real and wrap
#                                        it under its own name, so ctest and
#                                        the UCI suites (which start the
#                                        engine by path) run it under SDE
#
# Version, URLs and SHA-256s: Intel's SDE download page,
# https://www.intel.com/content/www/us/en/download/684897/intel-software-development-emulator.html
# (10.13.1, 2026-07-28, "Latest" on 2026-10-28; the page lists the SHA-256 of
# each file), cross-checked against the downloaded files on 2026-10-28. The
# downloadmirror.intel.com URL is the one the page's download buttons use
# (also in chaotic-aur's intel-sde package, same SHA-256). Licence: Intel's
# SDE licence agreement (accepted on download); SDE is a test tool only and
# is never part of Fork.
#
# The emulated CPU is Skylake server (-skx): AVX-512 F, CD, BW, DQ and VL,
# exactly the x86-64-v4 level the avx512 presets target.
set -euo pipefail

sde_version=10.13.1-2026-07-28
sde_mirror=https://downloadmirror.intel.com/924984
sde_lin_sha256=94e97d623fec54385686e1e7ba65ebc9941748c05ee451423948334892bf2b50
sde_win_sha256=74e626ede09b0baa5011fc9e51b58627ea92c3fc0bae5fd7db34b490f335f651
sde_chip=-skx

is_windows() { case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) return 0 ;; *) return 1 ;; esac; }

sde_exe() {  # DIR -> path of the SDE launcher
  local d=$1 c
  for c in sde64 sde64.exe sde sde.exe; do
    [ -f "$d/$c" ] && { echo "$d/$c"; return 0; }
  done
  echo "no SDE launcher in $d" >&2
  return 1
}

case "${1:-}" in
  needs)
    arch=${2:?ARCH}
    flags=$(grep -m1 -E '^flags' /proc/cpuinfo 2>/dev/null | cut -d: -f2- || true)
    model=$(grep -m1 -E '^model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2- | sed 's/^ *//' || true)
    echo "CPU: ${model:-unknown}"
    case "$arch" in
      native) want="" ;;
      x86-64-v3) want="avx avx2 bmi1 bmi2 fma f16c movbe" ;;
      x86-64-v4) want="avx avx2 bmi1 bmi2 fma f16c movbe avx512f avx512cd avx512bw avx512dq avx512vl" ;;
      *) echo "unknown ARCH $arch" >&2; exit 2 ;;
    esac
    missing=""
    for f in $want; do
      grep -qw "$f" <<<"$flags" || missing="$missing $f"
    done
    if [ -n "$missing" ]; then
      echo "CPU lacks$missing: $arch binaries need SDE"
      exit 0
    fi
    if [ "${FORK_CI_FORCE_SDE:-0}" = 1 ] && [ "$arch" = x86-64-v4 ]; then
      echo "CPU runs $arch natively, but FORK_CI_FORCE_SDE=1: using SDE anyway"
      exit 0
    fi
    echo "CPU runs $arch natively"
    exit 1
    ;;
  install)
    dir=${2:?DIR}
    if [ -d "$dir" ] && sde_exe "$dir" >/dev/null 2>&1; then
      echo "SDE $sde_version already in $dir (cache hit)"
      exit 0
    fi
    if is_windows; then
      file=sde-external-$sde_version-win.tar.xz sha=$sde_win_sha256
    else
      file=sde-external-$sde_version-lin.tar.xz sha=$sde_lin_sha256
    fi
    tmp=$(mktemp -d)
    curl -fsSL --retry 3 -A "Mozilla/5.0" -o "$tmp/$file" "$sde_mirror/$file"
    echo "$sha  $tmp/$file" | sha256sum -c -
    rm -rf "$dir" && mkdir -p "$dir"
    tar -xJf "$tmp/$file" -C "$dir" --strip-components=1
    rm -rf "$tmp"
    echo "SDE $sde_version installed in $dir: $(sde_exe "$dir")"
    ;;
  wrap)
    dir=${2:?DIR} bin=${3:?BIN} out=${4:?OUT}
    exe=$(sde_exe "$(cd "$dir" && pwd)")
    bin=$(cd "$(dirname "$bin")" && pwd)/$(basename "$bin")
    printf '#!/usr/bin/env bash\n# Runs %s under Intel SDE (%s); written by .github/ci/sde.sh.\nexec "%s" %s -- "%s" "$@"\n' \
      "$(basename "$bin")" "$sde_chip" "$exe" "$sde_chip" "$bin" >"$out"
    chmod +x "$out"
    echo "wrapped $bin under SDE as $out"
    ;;
  inplace)
    dir=${2:?DIR}
    shift 2
    for bin in "$@"; do
      [ -f "$bin" ] || { echo "no $bin" >&2; exit 1; }
      mv "$bin" "$bin.real"
      bash "$0" wrap "$dir" "$bin.real" "$bin"
    done
    ;;
  *)
    echo "usage: sde.sh needs ARCH | install DIR | wrap DIR BIN OUT | inplace DIR BIN..." >&2
    exit 2
    ;;
esac
