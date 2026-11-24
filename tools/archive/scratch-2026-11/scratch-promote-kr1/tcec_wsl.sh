#!/usr/bin/env bash
# WSL Ubuntu-22.04: the TCEC build path on the clean clone ~/scratch-promote-kr1/fork, TCEC's four compilers.
WIN_HOME=${WIN_HOME:?set WIN_HOME to the Windows home folder as WSL sees it, /mnt/c/Users/<user>}  # archive: was a literal path
s=$WIN_HOME/fork-runners/scratch-promote-kr1
cd ~/scratch-promote-kr1/fork || exit 1
export FORK_JOBS=3
nice bash "$s/tcec_path.sh" "$PWD" "$s/tcec-wsl" \
  gcc11-v3=g++@x86-64-v3 gcc11-v4=g++@x86-64-v4 gcc12-v3=g++-12@x86-64-v3 gcc12-v4=g++-12@x86-64-v4 \
  clang16-v3=clang++-16@x86-64-v3 clang16-v4=clang++-16@x86-64-v4 clang19-v3=clang++-19@x86-64-v3 \
  clang19-v4=clang++-19@x86-64-v4 > "$s/tcec-wsl.log" 2>&1
echo "exit $?"
