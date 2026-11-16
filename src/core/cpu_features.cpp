// SPDX-License-Identifier: GPL-3.0-or-later

// The extensions this build was compiled for, from the compiler's predefined
// macros (src/core/cpu_gate.hpp). Compiled with the build's flags, unlike
// cpu_gate.cpp, so the macros are the ones every other file sees; a constant,
// set before any code runs (constinit), which the startup check reads.
#include <cstdint>

#include "core/cpu_gate.hpp"

namespace forkeng {

namespace {

// Evaluated by the compiler only (for the constant below).
constexpr std::uint32_t macro_features() {
  std::uint32_t f = 0;
#if defined(__SSE3__)
  f |= CpuSse3;
#endif
#if defined(__SSSE3__)
  f |= CpuSsse3;
#endif
#if defined(__SSE4_1__)
  f |= CpuSse41;
#endif
#if defined(__SSE4_2__)
  f |= CpuSse42;
#endif
#if defined(__POPCNT__)
  f |= CpuPopcnt;
#endif
#if defined(__AVX__)
  f |= CpuAvx;
#endif
#if defined(__AVX2__)
  f |= CpuAvx2;
#endif
#if defined(__BMI__)
  f |= CpuBmi;
#endif
#if defined(__BMI2__)
  f |= CpuBmi2;
#endif
#if defined(__FMA__)
  f |= CpuFma;
#endif
#if defined(__AVX512F__)
  f |= CpuAvx512F;
#endif
#if defined(__AVX512BW__)
  f |= CpuAvx512Bw;
#endif
#if defined(__AVX512CD__)
  f |= CpuAvx512Cd;
#endif
#if defined(__AVX512DQ__)
  f |= CpuAvx512Dq;
#endif
#if defined(__AVX512VL__)
  f |= CpuAvx512Vl;
#endif
#if defined(__AVX512VNNI__)
  f |= CpuAvx512Vnni;
#endif
  return f;
}

}  // namespace

// External linkage from its declaration in cpu_gate.hpp.
constinit const std::uint32_t compiled_cpu_features = macro_features();

}  // namespace forkeng
