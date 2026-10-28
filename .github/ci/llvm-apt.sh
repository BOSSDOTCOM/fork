#!/usr/bin/env bash
# CI (Ubuntu runner): one clang major from the LLVM project's apt repository
# (https://apt.llvm.org, suite llvm-toolchain-<codename>-<major>), the way
# scripts/tcec-toolchain-setup.sh installs clang 16 and 19, plus its
# sanitizer runtimes (libclang-rt-<major>-dev, which holds MSan's).
#
#   .github/ci/llvm-apt.sh MAJOR
#
# Prints the installed version and, under GitHub Actions, sets the step
# outputs version (e.g. 21.1.8), tag (llvmorg-<version>, the llvm-project
# tag scripts/msan.sh builds libc++ from, so the two always match) and
# ident (the full `clang --version` line, made safe for cache keys).
#
# Checked 2026-10-28: apt.llvm.org serves llvm-toolchain-resolute-21
# (Ubuntu 26.04, today's ubuntu-latest) with clang-21 1:21.1.8~++20260528104042+2078da43e25a,
# and 2078da43e25a is the commit of llvm-project's tag llvmorg-21.1.8
# (GitHub API, git/tags for that tag), scripts/msan.sh's default.
set -euo pipefail
major=${1:?usage: llvm-apt.sh MAJOR}
. /etc/os-release
code=${VERSION_CODENAME:?no VERSION_CODENAME in /etc/os-release}

keyring=/etc/apt/keyrings/apt.llvm.org.asc
sudo install -d -m 0755 /etc/apt/keyrings
sudo wget -qO "$keyring" https://apt.llvm.org/llvm-snapshot.gpg.key
echo "deb [signed-by=$keyring] https://apt.llvm.org/$code/ llvm-toolchain-$code-$major main" |
  sudo tee /etc/apt/sources.list.d/llvm-$major.list >/dev/null
# The runner image may already have Ubuntu's own clang-<major>, whose Debian
# version sorts above apt.llvm.org's (~ sorts first): pin the LLVM origin so
# its packages win, downgrade included.
printf 'Package: *\nPin: origin apt.llvm.org\nPin-Priority: 1001\n' |
  sudo tee /etc/apt/preferences.d/apt-llvm-org.pref >/dev/null
sudo apt-get update -q
sudo apt-get install -y -q --allow-downgrades "clang-$major" "libclang-rt-$major-dev" ninja-build
installed=$(dpkg-query -W -f '${Version}' "clang-$major")
echo "clang-$major package: $installed"
case "$installed" in *~++*) ;; *) echo "clang-$major $installed is not from apt.llvm.org" >&2; exit 1 ;; esac

version=$("clang++-$major" -dumpversion)
ident=$("clang++-$major" --version | head -n 1)
echo "clang++-$major: $ident (version $version, libc++ tag llvmorg-$version)"
case "$version" in "$major".*) ;; *) echo "clang++-$major reports version $version" >&2; exit 1 ;; esac
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  {
    echo "version=$version"
    echo "tag=llvmorg-$version"
    echo "ident=$(printf '%s' "$ident" | tr -c 'A-Za-z0-9._+-' '_')"
  } >>"$GITHUB_OUTPUT"
fi
