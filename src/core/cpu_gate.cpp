// SPDX-License-Identifier: GPL-3.0-or-later

// cpu_gate: the startup check that this machine has the instruction sets the
// build was compiled for (DESIGN.md §7; the TCEC build row of §5.6).
//
// Purpose: a build whose code uses extensions this CPU lacks (x86-64-v3's
// AVX2 and BMI2, x86-64-v4's AVX-512, VNNI, or whatever a native build was
// given) stops at once with one line naming the missing extensions and the
// build to use, and exit status 1, instead of dying on an illegal instruction
// somewhere in the search. Selection stays at compile time
// (.claude/rules/simd.md): this is a refusal, never a dispatch.
// Invariants:
// - This file is compiled for baseline x86-64 without AVX and without LTO
//   (CMakeLists.txt), and the check runs as a constructor of priority 101,
//   before the default-priority static constructors of every other file, so
//   no instruction the CPU lacks runs before it. It calls no inline or
//   template function from a header (the linker may keep another file's copy
//   of one, compiled with the build's flags): only the C library and the
//   functions below.
// - What is checked is compiled_cpu_features, which the compiler's own
//   macros set where the rest of the build is compiled (cpu_features.cpp),
//   so the list follows FORK_ARCH, FORK_VNNI and native builds alike.
// - FORK_CPU_GATE_TEST=fail in the environment makes the check fail as if a
//   feature were missing (the ctest case cpu_gate_refusal; a test-only hook,
//   it can only stop the program, never let it run on a CPU that lacks one).
#include "core/cpu_gate.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace forkeng {

namespace {

// By bit, as cpu_gate.hpp orders them.
const char* const FeatureNames[CpuFeatureCount] = {
    "sse3", "ssse3", "sse4.1",  "sse4.2",   "popcnt",   "avx",      "avx2",     "bmi",
    "bmi2", "fma",   "avx512f", "avx512bw", "avx512cd", "avx512dq", "avx512vl", "avx512vnni",
};

}  // namespace

std::uint32_t missing_cpu_features(std::uint32_t needed, std::uint32_t present) { return needed & ~present; }

const char* cpu_feature_name(std::uint32_t feature) {
  for (int i = 0; i < CpuFeatureCount; ++i)
    if (feature == (1u << i)) return FeatureNames[i];
  return "?";
}

int write_cpu_feature_names(std::uint32_t features, char* out, int size) {
  int used = 0, count = 0;
  if (size > 0) out[0] = '\0';
  for (int i = 0; i < CpuFeatureCount; ++i) {
    if ((features & (1u << i)) == 0) continue;
    ++count;
    for (const char* c = " "; *c != '\0' && used + 1 < size; ++c) out[used++] = *c;
    for (const char* c = FeatureNames[i]; *c != '\0' && used + 1 < size; ++c) out[used++] = *c;
    if (size > 0) out[used] = '\0';
  }
  return count;
}

std::uint32_t present_cpu_features() {
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
  // Needed before __builtin_cpu_supports in a constructor that may run
  // before the runtime's own initialization of the CPU model.
  __builtin_cpu_init();
  std::uint32_t f = 0;
  if (__builtin_cpu_supports("sse3")) f |= CpuSse3;
  if (__builtin_cpu_supports("ssse3")) f |= CpuSsse3;
  if (__builtin_cpu_supports("sse4.1")) f |= CpuSse41;
  if (__builtin_cpu_supports("sse4.2")) f |= CpuSse42;
  if (__builtin_cpu_supports("popcnt")) f |= CpuPopcnt;
  if (__builtin_cpu_supports("avx")) f |= CpuAvx;
  if (__builtin_cpu_supports("avx2")) f |= CpuAvx2;
  if (__builtin_cpu_supports("bmi")) f |= CpuBmi;
  if (__builtin_cpu_supports("bmi2")) f |= CpuBmi2;
  if (__builtin_cpu_supports("fma")) f |= CpuFma;
  if (__builtin_cpu_supports("avx512f")) f |= CpuAvx512F;
  if (__builtin_cpu_supports("avx512bw")) f |= CpuAvx512Bw;
  if (__builtin_cpu_supports("avx512cd")) f |= CpuAvx512Cd;
  if (__builtin_cpu_supports("avx512dq")) f |= CpuAvx512Dq;
  if (__builtin_cpu_supports("avx512vl")) f |= CpuAvx512Vl;
  if (__builtin_cpu_supports("avx512vnni")) f |= CpuAvx512Vnni;
  return f;
#else
  return (1u << CpuFeatureCount) - 1;  // every one: no refusal where the CPU cannot be asked
#endif
}

namespace {

#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
[[gnu::constructor(101)]] void refuse_unsupported_cpu() {
  const std::uint32_t missing = missing_cpu_features(compiled_cpu_features, present_cpu_features());
  const char* test = std::getenv("FORK_CPU_GATE_TEST");
  const bool forced = test != nullptr && std::strcmp(test, "fail") == 0;
  if (missing == 0 && !forced) return;
  char names[16 * CpuFeatureCount];
  write_cpu_feature_names(missing, names, static_cast<int>(sizeof names));
  std::fprintf(stderr,
               "fork: this build (%s) needs CPU features this machine lacks:%s%s; use a build for this CPU "
               "(update.sh with FORK_ARCH=x86-64-v3, or x86-64)\n",
               FORK_ARCH_NAME, names, forced ? " (forced by FORK_CPU_GATE_TEST)" : "");
  std::_Exit(1);
}
#endif

}  // namespace

}  // namespace forkeng
