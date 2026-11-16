// SPDX-License-Identifier: GPL-3.0-or-later

// cpu_gate: the instruction-set extensions a build was compiled for, and the
// startup check that the CPU has them (src/core/cpu_gate.cpp; DESIGN.md §7).
//
// Purpose: name, as one bit each, the x86-64 extensions the compiler may use
// in Fork's code, so that the startup check can compare what the build needs
// with what the CPU offers and refuse, with a message, instead of dying on an
// illegal instruction.
// Invariants:
// - compiled_cpu_features is set from the compiler's own predefined macros
//   (__AVX2__, __BMI2__, __AVX512F__, ...) in a file compiled with the
//   build's flags (cpu_features.cpp), as a constant: no code runs to set it.
// - The functions declared here are defined in cpu_gate.cpp, which is
//   compiled for baseline x86-64 without LTO, so they run on any x86-64 CPU;
//   that file uses no inline or template function from a header, whose kept
//   copy the linker may take from a file compiled with the build's flags.
// - The bits are Fork's own numbering, never CPUID's.
// - Only extensions every supported compiler's __builtin_cpu_supports names
//   are listed (checked on TCEC's gcc 11 and 12 and clang 16 and 19,
//   2026-11-16): x86-64-v3's F16C, LZCNT and MOVBE are not, as clang 16
//   rejects their names; a CPU is refused for the others only.
#pragma once

#include <cstdint>

namespace forkeng {

// One bit per extension, in the order the refusal names them.
enum CpuFeature : std::uint32_t {
  CpuSse3 = 1u << 0,
  CpuSsse3 = 1u << 1,
  CpuSse41 = 1u << 2,
  CpuSse42 = 1u << 3,
  CpuPopcnt = 1u << 4,
  CpuAvx = 1u << 5,
  CpuAvx2 = 1u << 6,
  CpuBmi = 1u << 7,
  CpuBmi2 = 1u << 8,
  CpuFma = 1u << 9,
  CpuAvx512F = 1u << 10,
  CpuAvx512Bw = 1u << 11,
  CpuAvx512Cd = 1u << 12,
  CpuAvx512Dq = 1u << 13,
  CpuAvx512Vl = 1u << 14,
  CpuAvx512Vnni = 1u << 15,
};

// The number of CpuFeature bits.
inline constexpr int CpuFeatureCount = 16;

// The extensions this build's code was compiled for (cpu_features.cpp).
extern const std::uint32_t compiled_cpu_features;

// The extensions in `needed` that `present` lacks.
std::uint32_t missing_cpu_features(std::uint32_t needed, std::uint32_t present);

// The name of one CpuFeature bit (as the compilers' __builtin_cpu_supports
// spells it), or "?" for anything else.
const char* cpu_feature_name(std::uint32_t feature);

// Writes the names of the bits of `features`, in bit order, each preceded by
// a space, into `out` (always terminated, cut short if `size` is too small).
// Returns the number of names.
int write_cpu_feature_names(std::uint32_t features, char* out, int size);

// The extensions this CPU (and its operating system) supports, of those
// above; all of them where the check cannot ask (not x86-64, or a compiler
// without __builtin_cpu_supports), so the check never refuses there.
std::uint32_t present_cpu_features();

}  // namespace forkeng
