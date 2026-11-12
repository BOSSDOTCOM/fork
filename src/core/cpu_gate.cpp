// SPDX-License-Identifier: GPL-3.0-or-later

// cpu_gate: the startup check that this machine has the instruction sets the
// build was compiled for (DESIGN.md §7; the TCEC build row of §5.6).
//
// Purpose: a build for x86-64-v3 or x86-64-v4 (AVX-512, VNNI) started on a
// CPU without those instructions stops at once with a message naming the
// missing features and the build to use, instead of dying on an illegal
// instruction somewhere in the search. Selection stays at compile time
// (.claude/rules/simd.md): this is a refusal, never a dispatch.
// Invariants:
// - This file is compiled for baseline x86-64 (CMakeLists.txt), and the
//   check runs as a constructor of priority 101, before the default-priority
//   static constructors of every other file, so no instruction the CPU lacks
//   runs before it.
// - The features checked are the ones CMake derives from FORK_ARCH and
//   FORK_VNNI (FORK_CPU_NEEDS_V3, _V4, _VNNI); a native build checks none.
// - FORK_CPU_GATE_TEST=fail in the environment makes the check fail as if a
//   feature were missing (the ctest case cpu_gate_refusal; a test-only hook,
//   it can only stop the program, never let it run on a CPU that lacks one).
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace forkeng {
namespace {

#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
[[gnu::constructor(101)]] void refuse_unsupported_cpu() {
  __builtin_cpu_init();
  const char* missing[16];
  int n = 0;
  [[maybe_unused]] const auto need = [&](bool present, const char* name) {
    if (!present && n < 16) missing[n++] = name;
  };
#if defined(FORK_CPU_NEEDS_V3) || defined(FORK_CPU_NEEDS_V4)
  need(__builtin_cpu_supports("popcnt"), "popcnt");
  need(__builtin_cpu_supports("avx2"), "avx2");
  need(__builtin_cpu_supports("bmi"), "bmi");
  need(__builtin_cpu_supports("bmi2"), "bmi2");
  need(__builtin_cpu_supports("fma"), "fma");
#endif
#if defined(FORK_CPU_NEEDS_V4)
  need(__builtin_cpu_supports("avx512f"), "avx512f");
  need(__builtin_cpu_supports("avx512bw"), "avx512bw");
  need(__builtin_cpu_supports("avx512cd"), "avx512cd");
  need(__builtin_cpu_supports("avx512dq"), "avx512dq");
  need(__builtin_cpu_supports("avx512vl"), "avx512vl");
#endif
#if defined(FORK_CPU_NEEDS_VNNI)
  need(__builtin_cpu_supports("avx512vnni"), "avx512vnni");
#endif
  const char* test = std::getenv("FORK_CPU_GATE_TEST");
  const bool forced = test != nullptr && std::strcmp(test, "fail") == 0;
  if (n == 0 && !forced) return;
  std::fprintf(stderr, "fork: this build (%s) needs CPU features this machine lacks:", FORK_ARCH_NAME);
  for (int i = 0; i < n; ++i) std::fprintf(stderr, " %s", missing[i]);
  if (forced) std::fprintf(stderr, " (forced by FORK_CPU_GATE_TEST)");
  std::fprintf(stderr, "; use a build for this CPU (update.sh with FORK_ARCH=x86-64-v3, or x86-64)\n");
  std::_Exit(1);
}
#endif

}  // namespace
}  // namespace forkeng
