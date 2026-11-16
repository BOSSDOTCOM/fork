// SPDX-License-Identifier: GPL-3.0-or-later

// The startup CPU check's decision (src/core/cpu_gate.hpp): what a build
// needs against what a CPU offers, with made-up feature sets, and the real
// check on this machine. The refusal itself (message, exit status, nothing
// run after it) is the ctest case cpu_gate_refusal (CMakeLists.txt).
#include <cstdint>
#include <string>

#include "core/cpu_gate.hpp"
#include "harness.hpp"

namespace forkeng::test {

namespace {

// The names write_cpu_feature_names gives, as a string.
std::string names_of(std::uint32_t features) {
  char out[512];
  write_cpu_feature_names(features, out, static_cast<int>(sizeof out));
  return out;
}

// x86-64-v3's extensions among those checked, and x86-64-v4's: the macros
// `-march=x86-64-v3` and `-march=x86-64-v4` define, read from both local
// compilers (LLVM-MinGW clang++ and WinLibs g++, `-dM -E`, 2026-11-16). v3
// also defines __F16C__, __LZCNT__ and __MOVBE__, which are not checked
// (clang 16, a TCEC compiler, has no __builtin_cpu_supports name for them).
constexpr std::uint32_t V3 =
    CpuSse3 | CpuSsse3 | CpuSse41 | CpuSse42 | CpuPopcnt | CpuAvx | CpuAvx2 | CpuBmi | CpuBmi2 | CpuFma;
constexpr std::uint32_t V4 = V3 | CpuAvx512F | CpuAvx512Bw | CpuAvx512Cd | CpuAvx512Dq | CpuAvx512Vl;

}  // namespace

TEST_CASE("cpu_gate", "a CPU with everything the build needs passes; one without is refused by name") {
  CHECK_EQ(missing_cpu_features(V3, V3), std::uint32_t{0});
  CHECK_EQ(missing_cpu_features(V3, V4), std::uint32_t{0});  // more than needed
  CHECK_EQ(missing_cpu_features(0, 0), std::uint32_t{0});    // a baseline build runs anywhere
  // The pext build on a CPU without BMI2.
  CHECK_EQ(missing_cpu_features(V3, V3 & ~CpuBmi2), std::uint32_t{CpuBmi2});
  CHECK_EQ(names_of(missing_cpu_features(V3, V3 & ~CpuBmi2)), std::string(" bmi2"));
  // x86-64-v4 on an AVX2 machine: every AVX-512 subset, in bit order.
  CHECK_EQ(missing_cpu_features(V4, V3), V4 & ~V3);
  CHECK_EQ(names_of(missing_cpu_features(V4, V3)),
           std::string(" avx512f avx512bw avx512cd avx512dq avx512vl"));
  // VNNI on an AVX-512 machine without it.
  CHECK_EQ(names_of(missing_cpu_features(V4 | CpuAvx512Vnni, V4)), std::string(" avx512vnni"));
  // A v3 build on a v2 machine (no AVX at all).
  CHECK_EQ(names_of(missing_cpu_features(V3, CpuSse3 | CpuSsse3 | CpuSse41 | CpuSse42 | CpuPopcnt)),
           std::string(" avx avx2 bmi bmi2 fma"));
}

TEST_CASE("cpu_gate", "feature names: every bit has its own, the output is cut safely") {
  for (int i = 0; i < CpuFeatureCount; ++i) {
    const std::string name = cpu_feature_name(1u << i);
    CHECK_MSG(name != "?" && !name.empty(), "bit " << i);
    for (int j = 0; j < i; ++j) CHECK_MSG(name != cpu_feature_name(1u << j), "bits " << j << " and " << i);
  }
  CHECK_EQ(std::string(cpu_feature_name(CpuBmi2 | CpuAvx2)), std::string("?"));  // not one bit
  CHECK_EQ(std::string(cpu_feature_name(0)), std::string("?"));
  char small[8];
  CHECK_EQ(write_cpu_feature_names(CpuAvx512Vnni | CpuBmi2, small, static_cast<int>(sizeof small)), 2);
  CHECK_EQ(std::string(small), std::string(" bmi2 a"));  // 7 characters and the terminator
  CHECK_EQ(write_cpu_feature_names(0, small, static_cast<int>(sizeof small)), 0);
  CHECK_EQ(std::string(small), std::string());
}

// The real check: this build's own needs are present on the machine that
// runs its tests (it would not have started otherwise), and they follow the
// compiler's macros as every other file sees them.
TEST_CASE("cpu_gate", "the real check passes here, on the build's own macros") {
  CHECK_EQ(missing_cpu_features(compiled_cpu_features, present_cpu_features()), std::uint32_t{0});
#if defined(__AVX2__)
  CHECK((compiled_cpu_features & CpuAvx2) != 0);
#else
  CHECK((compiled_cpu_features & CpuAvx2) == 0);
#endif
#if defined(__BMI2__)
  CHECK((compiled_cpu_features & CpuBmi2) != 0);
#else
  CHECK((compiled_cpu_features & CpuBmi2) == 0);
#endif
#if defined(__AVX512F__)
  CHECK((compiled_cpu_features & CpuAvx512F) != 0);
#else
  CHECK((compiled_cpu_features & CpuAvx512F) == 0);
#endif
#if defined(__AVX512VNNI__)
  CHECK((compiled_cpu_features & CpuAvx512Vnni) != 0);
#else
  CHECK((compiled_cpu_features & CpuAvx512Vnni) == 0);
#endif
}

}  // namespace forkeng::test
