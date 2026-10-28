// SPDX-License-Identifier: GPL-3.0-or-later

// Finds, for every square, a seed whose first magic candidate already works,
// and prints the seed tables for src/core/bitboard.cpp. Fork's magics come
// from its own search; these seeds only make that search fast at startup.
//
//   fork_magic_seeds [max_seed]
#include <cstdio>
#include <cstdlib>

#include "core/bitboard.hpp"

int main(int argc, char** argv) {
  const std::uint64_t max_seed = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : 200000;
  for (bool rook : {true, false}) {
    std::printf("constexpr std::uint64_t %sSeeds[64] = {\n", rook ? "Rook" : "Bishop");
    long total = 0;
    for (forkeng::Square s = 0; s < 64; ++s) {
      std::uint64_t best_seed = 1;
      int best = forkeng::magic_search_attempts(rook, s, 1, 1 << 22);
      for (std::uint64_t seed = 2; seed <= max_seed && best > 1; ++seed) {
        int attempts = forkeng::magic_search_attempts(rook, s, seed, best - 1);
        if (attempts > 0) {
          best = attempts;
          best_seed = seed;
        }
      }
      total += best;
      std::printf("%s%llu", s % 8 ? ", " : (s ? ",\n    " : "    "),
                  static_cast<unsigned long long>(best_seed));
    }
    std::printf("\n};  // %ld candidates in total\n", total);
  }
  return 0;
}
