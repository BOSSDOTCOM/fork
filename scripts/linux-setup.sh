#!/usr/bin/env bash
# One-time setup of the Linux working copy in WSL2 Ubuntu (DESIGN.md 2).
# Run inside Ubuntu:  bash /mnt/c/Users/<user>/fork/scripts/linux-setup.sh
# Installs the build toolchain (asks for your sudo password), then clones the
# Windows repo into ~/fork (the Linux copy lives in the WSL filesystem, never
# under /mnt/c) or fast-forwards it if it already exists. Re-runnable.
set -euo pipefail

src="${FORK_WINDOWS_REPO:-/mnt/c/Users/<user>/fork}"
dst="${FORK_LINUX_REPO:-$HOME/fork}"

packages=(build-essential g++ clang llvm lld cmake ninja-build git
          clang-tidy cppcheck valgrind)
# Sanitizer runtimes for clang ship separately on newer Ubuntu releases.
if apt-cache show libclang-rt-dev >/dev/null 2>&1; then packages+=(libclang-rt-dev); fi

missing=()
for p in "${packages[@]}"; do
  dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
done
if ((${#missing[@]})); then
  echo "installing: ${missing[*]}"
  sudo apt-get update
  sudo apt-get install -y "${missing[@]}"
else
  echo "toolchain packages already installed"
fi

if [ -d "$dst/.git" ]; then
  git -C "$dst" fetch "$src" main
  git -C "$dst" merge --ff-only FETCH_HEAD
else
  git clone "$src" "$dst"
fi

echo
clang++ --version | head -1
g++ --version | head -1
cmake --version | head -1
echo "ninja $(ninja --version)"
echo
echo "Linux copy ready at $dst. Build and test every preset with:"
echo "  cd $dst && scripts/build.sh"
