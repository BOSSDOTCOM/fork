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

# Low priority while test games run (owner, 2026-10-26): when a game queue
# has created build/.games-running in this tree (or FORK_LOW_PRIORITY=1 is
# set), the shell that sources this file drops its priority, which every
# build, test and check it starts inherits (below normal on Windows, nice 19
# on Linux, where all WSL distros share one kernel with the games), and
# builds and tests run with few parallel jobs. Timing tests then report
# SKIPPED, as their measurements would not mean anything.
fork_env_dir=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)
if [ "${FORK_LOW_PRIORITY:-}" = 1 ] || [ -f "$fork_env_dir/../build/.games-running" ]; then
  export FORK_LOW_PRIORITY=1
  export FORK_JOBS=${FORK_LOW_JOBS:-4}                       # update.sh
  export CMAKE_BUILD_PARALLEL_LEVEL=${FORK_LOW_JOBS:-4}      # cmake --build
  export CTEST_PARALLEL_LEVEL=1                              # one test at a time
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      if [ -r "/proc/$$/winpid" ]; then
        powershell.exe -NoProfile -Command \
          "\$p = Get-Process -Id $(cat "/proc/$$/winpid"); if (\$p.PriorityClass -eq 'Normal') { \$p.PriorityClass = 'BelowNormal' }" \
          >/dev/null 2>&1 || true
      fi
      ;;
    *) renice -n 19 -p $$ >/dev/null 2>&1 || true ;;
  esac
fi
unset fork_env_dir
