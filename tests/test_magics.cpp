#include <algorithm>

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
  check_slider(tables::rook, rook_attacks, rook_attacks_by_walk, "rook");
}

TEST_CASE("magics", "bishop lookups match ray walk for every subset") {
  check_slider(tables::bishop, bishop_attacks, bishop_attacks_by_walk, "bishop");
}

// Independent oracle for between/line: plane geometry on (file, rank)
// coordinates, not ray walking. a and b are aligned when they differ and share
// a file, a rank or a diagonal; c is on their line when the three points are
// collinear, and strictly between them when it is also inside their bounding
// box and is neither end.
TEST_CASE("magics", "between and line match coordinate geometry for every pair") {
  for (Square a = 0; a < 64; ++a)
    for (Square b = 0; b < 64; ++b) {
      int fa = file_of(a), ra = rank_of(a), fb = file_of(b), rb = rank_of(b);
      bool aligned = a != b && (fa == fb || ra == rb || fa - fb == ra - rb || fa - fb == rb - ra);
      Bitboard want_between = 0, want_line = 0;
      for (Square c = 0; aligned && c < 64; ++c) {
        int fc = file_of(c), rc = rank_of(c);
        if ((fc - fa) * (rb - ra) != (rc - ra) * (fb - fa)) continue;
        want_line |= bb(c);
        bool inside = std::min(fa, fb) <= fc && fc <= std::max(fa, fb) && std::min(ra, rb) <= rc &&
                      rc <= std::max(ra, rb);
        if (inside && c != a && c != b) want_between |= bb(c);
      }
      CHECK_MSG(between(a, b) == want_between, "between " << a << ' ' << b);
      CHECK_MSG(line(a, b) == want_line, "line " << a << ' ' << b);
    }
}

// Masks: empty-board attacks without the board edges, except the edges along
// which a rook on that edge itself slides.
TEST_CASE("magics", "relevant-occupancy masks") {
  for (Square s = 0; s < 64; ++s) {
    Bitboard own_rank = Rank1 << (8 * rank_of(s)), own_file = FileA << file_of(s);
    Bitboard rook_edges = ((Rank1 | Rank8) & ~own_rank) | ((FileA | FileH) & ~own_file);
    CHECK_MSG(tables::rook[s].mask == (rook_attacks_by_walk(s, 0) & ~rook_edges), "rook mask " << s);
    CHECK_MSG(tables::bishop[s].mask == (bishop_attacks_by_walk(s, 0) & ~(Rank1 | Rank8 | FileA | FileH)),
              "bishop mask " << s);
  }
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
