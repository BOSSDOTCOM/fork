// splitmix: Fork's one pseudo-random stream, for table generation only.
//
// Purpose: a fixed-seed generator for the Zobrist keys (zobrist.cpp) and the
// magic-number candidates (bitboard.cpp); its output function also mixes
// the TT's data digest (search/trans_table.cpp; audit-1 T-6).
// Invariants:
// - splitmix64 exactly as in Sebastiano Vigna's public-domain reference,
//   https://prng.di.unimi.it/splitmix64.c (constants checked against it on
//   2026-10-24). Changing it changes every Zobrist key and so the bench
//   signature.
// - Deterministic: the same seed always gives the same stream.
#pragma once

#include <cstdint>

namespace forkeng {

// The reference's output function: mixes all 64 bits of `z` into each bit
// of the result.
constexpr std::uint64_t splitmix_finalize(std::uint64_t z) {
  z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
  return z ^ (z >> 31);
}

// Advances `state` and returns the next 64-bit output.
inline std::uint64_t splitmix_next(std::uint64_t& state) {
  return splitmix_finalize(state += 0x9E3779B97F4A7C15ULL);
}

}  // namespace forkeng
