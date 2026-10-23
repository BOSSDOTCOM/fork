// zobrist: key generation (see zobrist.hpp).
#include "core/zobrist.hpp"

namespace fork::zobrist {

Key piece_square[16][64];
Key side;
Key castling[16];
Key ep_file[8];
Key material[16][16];

void init() {
  // splitmix64 with a fixed seed: keys (and bench signatures) are reproducible.
  std::uint64_t state = 0xF0E1'D2C3'B4A5'9687ULL;
  auto next = [&state] {
    std::uint64_t z = (state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
  };
  for (auto& row : piece_square)
    for (Key& k : row) k = next();
  side = next();
  // Each right gets a key; a rights state is the xor of its rights' keys,
  // so a change of rights costs a single table lookup.
  Key right[4] = {next(), next(), next(), next()};
  for (int s = 0; s < 16; ++s) {
    castling[s] = 0;
    for (int r = 0; r < 4; ++r)
      if (s & (1 << r)) castling[s] ^= right[r];
  }
  for (Key& k : ep_file) k = next();
  for (auto& row : material)
    for (Key& k : row) k = next();
}

}  // namespace fork::zobrist
