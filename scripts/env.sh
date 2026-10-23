# Names the compilers the CMake presets use. Source it: . scripts/env.sh
# Linux: system clang++/g++ (override by exporting FORK_CLANG_CXX/FORK_GCC_CXX first).
# Git Bash on Windows: the winget-installed toolchain.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    pk="$(cygpath -u "$LOCALAPPDATA")/Microsoft/WinGet/Packages"
    llvm=$(ls -d "$pk"/MartinStorsjo.LLVM-MinGW.UCRT*/llvm-mingw-* | head -1)
    cmk=$(ls -d "$pk"/Kitware.CMake*/cmake-* | head -1)
    nin=$(ls -d "$pk"/Ninja-build.Ninja* | head -1)
    gcc=$(ls -d "$pk"/BrechtSanders.WinLibs.POSIX.UCRT*/mingw64/bin | head -1)
    export FORK_CLANG_CXX="$(cygpath -m "$llvm/bin/clang++.exe")"
    export FORK_GCC_CXX="$(cygpath -m "$gcc/g++.exe")"
    export PATH="$llvm/bin:$cmk/bin:$nin:$PATH:$gcc"
    ;;
  *)
    export FORK_CLANG_CXX="${FORK_CLANG_CXX:-clang++}"
    export FORK_GCC_CXX="${FORK_GCC_CXX:-g++}"
    ;;
esac
