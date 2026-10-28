// SPDX-License-Identifier: GPL-3.0-or-later

// bitboard: table construction and the magic search (see bitboard.hpp).
//
// Everything here is built by walking the board one step at a time from
// (file, rank) coordinates: leaper attacks, the reference slider attacks,
// the relevant-occupancy masks, and the between/line tables. The magic
// search is the trial-and-error method of CPW "Looking for Magics" with
// sparse candidates (the AND of three random words), drawn from Fork's
// splitmix64 stream (splitmix.hpp). Sources: docs/ORIGINALITY.md.
#include "core/bitboard.hpp"

#include <algorithm>
#include <climits>
#include <vector>

#include "core/splitmix.hpp"

namespace forkeng {

namespace tables {
Bitboard pawn_attacks[2][64];
Bitboard knight_attacks[64];
Bitboard king_attacks[64];
Bitboard between[64][64];
Bitboard line[64][64];
SliderEntry rook[64];
SliderEntry bishop[64];
}  // namespace tables

namespace {

// Rook needs 102400 entries over all squares, bishop 5248.
constexpr std::size_t RookTableSize = 102400, BishopTableSize = 5248;
Bitboard slider_table[RookTableSize + BishopTableSize];

// A move of one square as (file change, rank change).
struct FileRankStep {
  int df, dr;
};

// The eight directions: the first four along ranks and files (rook), the
// last four along diagonals (bishop).
constexpr FileRankStep Compass[8] = {{0, 1}, {1, 0}, {0, -1}, {-1, 0}, {1, 1}, {1, -1}, {-1, -1}, {-1, 1}};
constexpr int RookDirsBegin = 0, BishopDirsBegin = 4;

// The square one step from `s`, or NoSquare if that leaves the board.
Square step_from(Square s, FileRankStep d) {
  int file = file_of(s) + d.df, rank = rank_of(s) + d.dr;
  if (file < 0 || file > 7 || rank < 0 || rank > 7) return NoSquare;
  return make_square(file, rank);
}

// Every square reached from `s` in direction `d` on an empty board.
Bitboard ray_from(Square s, FileRankStep d) {
  Bitboard ray = 0;
  for (Square t = step_from(s, d); t != NoSquare; t = step_from(t, d)) ray |= bb(t);
  return ray;
}

// Reference slider attacks: in each of the four directions starting at
// Compass[dirs_begin], every square up to the board edge or up to and
// including the first occupied square.
Bitboard walk_ray_attacks(Square s, Bitboard occ, int dirs_begin) {
  Bitboard reached = 0;
  for (int d = dirs_begin; d < dirs_begin + 4; ++d) {
    for (Square t = step_from(s, Compass[d]); t != NoSquare; t = step_from(t, Compass[d])) {
      reached |= bb(t);
      if (occ & bb(t)) break;
    }
  }
  return reached;
}

// Relevant-occupancy mask: the empty-board rays from `s`, each stopping one
// square before the edge. An edge square never hides anything behind it, so
// whether it is occupied cannot change the attack set.
Bitboard slider_mask(Square s, int dirs_begin) {
  Bitboard mask = 0;
  for (int d = dirs_begin; d < dirs_begin + 4; ++d) {
    for (Square t = step_from(s, Compass[d]); t != NoSquare; t = step_from(t, Compass[d]))
      if (step_from(t, Compass[d]) != NoSquare) mask |= bb(t);
  }
  return mask;
}

// The subset of `mask` chosen by `index`: bit i of `index` decides whether
// the i-th lowest square of `mask` is in it (a portable bit deposit, the
// inverse of PEXT by `mask`).
Bitboard deposit_bits(std::uint64_t index, Bitboard mask) {
  Bitboard subset = 0;
  for (int i = 0; mask; ++i) {
    Square s = pop_lsb(mask);
    if ((index >> i) & 1) subset |= bb(s);
  }
  return subset;
}

void build_leaper_tables() {
  constexpr FileRankStep KnightJumps[8] = {{1, 2},   {2, 1},   {2, -1}, {1, -2},
                                           {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}};
  for (Square s = 0; s < 64; ++s) {
    Bitboard knight = 0, king = 0;
    for (FileRankStep j : KnightJumps)
      if (Square t = step_from(s, j); t != NoSquare) knight |= bb(t);
    for (FileRankStep d : Compass)
      if (Square t = step_from(s, d); t != NoSquare) king |= bb(t);
    tables::knight_attacks[s] = knight;
    tables::king_attacks[s] = king;
    for (Color c : {White, Black}) {
      int ahead = c == White ? 1 : -1;
      Bitboard pawn = 0;
      for (int side : {-1, 1})
        if (Square t = step_from(s, {side, ahead}); t != NoSquare) pawn |= bb(t);
      tables::pawn_attacks[c][s] = pawn;
    }
  }
}

// Walking from `a` in one direction, the squares passed before reaching `b`
// are between(a, b), and the line through both is a's ray that way, the ray
// the opposite way, and `a` itself. Pairs that share no direction stay 0.
void build_line_tables() {
  for (Square a = 0; a < 64; ++a) {
    std::fill(std::begin(tables::between[a]), std::end(tables::between[a]), Bitboard{0});
    std::fill(std::begin(tables::line[a]), std::end(tables::line[a]), Bitboard{0});
    for (FileRankStep d : Compass) {
      Bitboard whole_line = bb(a) | ray_from(a, d) | ray_from(a, {-d.df, -d.dr});
      Bitboard passed = 0;
      for (Square b = step_from(a, d); b != NoSquare; b = step_from(b, d)) {
        tables::between[a][b] = passed;
        tables::line[a][b] = whole_line;
        passed |= bb(b);
      }
    }
  }
}

// Per-square seeds for the magic search, found offline by
// tools/magic_seeds.cpp (target fork_magic_seeds): with these the first or
// second candidate already works, so startup does almost no searching. Any
// nonzero seed gives correct magics; these only make startup fast.
// clang-format off
constexpr std::uint64_t RookSeeds[64] = {
    50641, 26359, 158776, 20875, 31803, 24319, 5698, 26827,
    2004, 11346, 1036, 43425, 7705, 7768, 7705, 32058,
    24950, 4228, 24261, 52117, 71026, 10224, 3533, 23365,
    22283, 20073, 11331, 22278, 7768, 7768, 9683, 24786,
    9016, 11346, 34206, 32527, 25225, 60602, 20727, 31924,
    7232, 81484, 53544, 22278, 109384, 37683, 7705, 16426,
    467, 467, 1036, 11703, 4120, 19575, 1102, 4582,
    44515, 4466, 20546, 40717, 37102, 4276, 1626, 6028
};  // 66 candidates in total
constexpr std::uint64_t BishopSeeds[64] = {
    5749, 42, 15, 392, 101, 412, 856, 12128,
    2718, 622, 889, 1950, 661, 1896, 117, 1416,
    2183, 1676, 5619, 11906, 1751, 1695, 1416, 254,
    1483, 1483, 3377, 1758, 20373, 14051, 1601, 145,
    3162, 2293, 15738, 30098, 29380, 1399, 1399, 2652,
    968, 178, 1997, 3619, 418, 195, 1089, 622,
    856, 479, 284, 429, 207, 42, 42, 42,
    12128, 1416, 675, 834, 53, 1896, 2718, 5749
};  // 64 candidates in total
// clang-format on

// One relevant occupancy of a square and the attack set it produces.
struct Occupancy {
  Bitboard occ;
  Bitboard reach;
};

std::vector<Occupancy> all_occupancies(Square s, Bitboard mask, int dirs_begin) {
  std::vector<Occupancy> list(std::size_t{1} << popcount(mask));
  for (std::size_t i = 0; i < list.size(); ++i) {
    Bitboard occ = deposit_bits(i, mask);
    list[i] = {occ, walk_ray_attacks(s, occ, dirs_begin)};
  }
  return list;
}

// Draws candidates from the stream seeded with `seed` until one maps every
// occupancy to a slot that is free or already holds the same attack set
// (sharing a slot is fine when the attacks agree). The candidate is checked
// in a scratch table, and only a winner's table is copied to `out`
// (1 << bits entries; slots no occupancy reaches are 0). Returns the number
// of candidates tried, or -1 if `limit` were tried without success.
int pick_magic(const std::vector<Occupancy>& occupancies, int bits, std::uint64_t seed, int limit,
               Bitboard& magic, Bitboard* out) {
  const std::size_t size = std::size_t{1} << bits;
  const unsigned shift = 64 - bits;
  std::vector<Bitboard> scratch(size);
  std::vector<char> taken(size);
  std::uint64_t state = seed;
  for (int tried = 1; tried <= limit; ++tried) {
    Bitboard candidate = splitmix_next(state);
    candidate &= splitmix_next(state);
    candidate &= splitmix_next(state);
    std::fill(taken.begin(), taken.end(), 0);
    bool works = true;
    for (const Occupancy& o : occupancies) {
      std::size_t slot = (o.occ * candidate) >> shift;
      if (!taken[slot]) {
        taken[slot] = 1;
        scratch[slot] = o.reach;
      } else if (scratch[slot] != o.reach) {
        works = false;
        break;
      }
    }
    if (!works) continue;
    magic = candidate;
    for (std::size_t i = 0; i < size; ++i) out[i] = taken[i] ? scratch[i] : 0;
    return tried;
  }
  return -1;
}

// Fills one slider kind's entries. Square s's slice of slider_table starts at
// `offset` and has 1 << popcount(mask) entries; returns the offset after the
// last square.
std::size_t build_slider(SliderEntry* entries, int dirs_begin, const std::uint64_t* seeds,
                         std::size_t offset) {
  for (Square s = 0; s < 64; ++s) {
    SliderEntry& e = entries[s];
    e.mask = slider_mask(s, dirs_begin);
    const int bits = popcount(e.mask);
    e.shift = 64 - bits;
    e.magic = 0;
    e.table = slider_table + offset;
#if FORK_USE_PEXT
    (void)seeds;
    // PEXT by the mask is the inverse of deposit_bits, so entry i belongs to
    // the i-th subset.
    for (std::uint64_t i = 0; i < (std::uint64_t{1} << bits); ++i)
      slider_table[offset + i] = walk_ray_attacks(s, deposit_bits(i, e.mask), dirs_begin);
#else
    pick_magic(all_occupancies(s, e.mask, dirs_begin), bits, seeds[s], INT_MAX, e.magic,
               slider_table + offset);
#endif
    offset += std::size_t{1} << bits;
  }
  return offset;
}

}  // namespace

int magic_search_attempts(bool rook, Square s, std::uint64_t seed, int limit) {
  const int dirs_begin = rook ? RookDirsBegin : BishopDirsBegin;
  const Bitboard mask = slider_mask(s, dirs_begin);
  const int bits = popcount(mask);
  std::vector<Bitboard> out(std::size_t{1} << bits);
  Bitboard magic = 0;
  return pick_magic(all_occupancies(s, mask, dirs_begin), bits, seed, limit, magic, out.data());
}

Bitboard rook_attacks_by_walk(Square s, Bitboard occ) { return walk_ray_attacks(s, occ, RookDirsBegin); }
Bitboard bishop_attacks_by_walk(Square s, Bitboard occ) { return walk_ray_attacks(s, occ, BishopDirsBegin); }

void init_bitboards() {
  // A function-local static is initialized exactly once, even with threads.
  static const bool built = (build_bitboard_tables(), true);
  (void)built;
}

void build_bitboard_tables() {
  build_leaper_tables();
  build_line_tables();
  std::size_t used = build_slider(tables::rook, RookDirsBegin, RookSeeds, 0);
  used = build_slider(tables::bishop, BishopDirsBegin, BishopSeeds, used);
  assert(used == RookTableSize + BishopTableSize);
  (void)used;
}

}  // namespace forkeng
