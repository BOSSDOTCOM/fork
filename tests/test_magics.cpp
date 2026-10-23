#include "core/bitboard.hpp"
#include "harness.hpp"

using namespace forkeng;

namespace {

std::uint64_t noise_state = 0x1234'5678'9ABC'DEF1ULL;
std::uint64_t noise() {
  noise_state ^= noise_state << 13;
  noise_state ^= noise_state >> 7;
  noise_state ^= noise_state << 17;
  return noise_state;
}

void check_slider(const SliderEntry* entries, Bitboard (*fast)(Square, Bitboard),
                  Bitboard (*slow)(Square, Bitboard), const char* name) {
  for (Square s = 0; s < 64; ++s) {
    Bitboard mask = entries[s].mask;
    Bitboard subset = 0;
    do {
      // Squares outside the mask must not change the result.
      Bitboard occ = subset | (noise() & ~mask & ~bb(s));
      CHECK_MSG(fast(s, occ) == slow(s, occ), name << " square " << s);
      subset = (subset - mask) & mask;
    } while (subset);
  }
}

}  // namespace

TEST_CASE("magics", "rook lookups match ray walk for every subset") {
  check_slider(tables::rook, rook_attacks, rook_attacks_slow, "rook");
}

TEST_CASE("magics", "bishop lookups match ray walk for every subset") {
  check_slider(tables::bishop, bishop_attacks, bishop_attacks_slow, "bishop");
}

TEST_CASE("magics", "leaper tables and lines") {
  constexpr Square a1 = 0, b3 = 17, c2 = 10, h8 = 63, e4 = 28, b1 = 1, a2 = 8, b2 = 9;
  CHECK_EQ(knight_attacks(a1), bb(b3) | bb(c2));
  CHECK_EQ(king_attacks(a1), bb(b1) | bb(a2) | bb(b2));
  CHECK_EQ(popcount(knight_attacks(e4)), 8);
  CHECK_EQ(pawn_attacks(White, e4), bb(e4 + 7) | bb(e4 + 9));
  CHECK_EQ(pawn_attacks(Black, e4), bb(e4 - 7) | bb(e4 - 9));
  CHECK_EQ(pawn_attacks(White, 15), bb(22));  // h2 attacks g3 only
  CHECK_EQ(popcount(between(a1, h8)), 6);
  CHECK_EQ(popcount(line(a1, h8)), 8);
  CHECK_EQ(between(a1, b3), Bitboard{0});
  CHECK_EQ(line(a1, b3), Bitboard{0});
  CHECK_EQ(line(a1, 7), Rank1);
}
