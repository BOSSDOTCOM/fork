// bitboard: table construction and the magic search (see bitboard.hpp).
#include "core/bitboard.hpp"

#include <vector>

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
Bitboard slider_table[102400 + 5248];

constexpr int RookDirs[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
constexpr int BishopDirs[4][2] = {{1, 1}, {1, -1}, {-1, 1}, {-1, -1}};

Bitboard ray_walk(Square s, Bitboard occ, const int (&dirs)[4][2]) {
  Bitboard result = 0;
  for (const auto& d : dirs) {
    int f = file_of(s) + d[0], r = rank_of(s) + d[1];
    while (f >= 0 && f < 8 && r >= 0 && r < 8) {
      Square t = make_square(f, r);
      result |= bb(t);
      if (occ & bb(t)) break;
      f += d[0];
      r += d[1];
    }
  }
  return result;
}

// Deterministic xorshift64* stream for the magic search.
struct Rng {
  std::uint64_t state;
  std::uint64_t next() {
    state ^= state >> 12;
    state ^= state << 25;
    state ^= state >> 27;
    return state * 0x2545F4914F6CDD1DULL;
  }
  std::uint64_t sparse() { return next() & next() & next(); }
};

// Per-square seeds for the magic search, found by Fork's own offline search
// (fork_magic_seeds, tools/magic_seeds.cpp): with these, the first or second
// candidate already works, so startup does almost no searching. Any nonzero
// seed gives correct magics; these only make startup fast.
// clang-format off
constexpr std::uint64_t RookSeeds[64] = {
    13359, 1897, 596, 16388, 11763, 18433, 19475, 4299,
    10028, 5402, 12825, 16350, 5083, 8414, 5553, 8431,
    9426, 484, 11340, 4198, 7397, 5684, 4809, 8480,
    6108, 3475, 11024, 2422, 6326, 19559, 1087, 4745,
    4878, 1145, 6228, 10884, 11280, 2083, 10237, 8974,
    3842, 6869, 349, 12819, 7427, 17075, 2555, 188,
    1226, 1226, 5531, 1866, 9533, 11767, 1714, 12115,
    2902, 2902, 3305, 11383, 14421, 6229, 10121, 2196
};  // 97 candidates in total
constexpr std::uint64_t BishopSeeds[64] = {
    68, 53, 337, 55, 61, 47, 92, 336,
    230, 79, 166, 214, 112, 333, 190, 30,
    45, 5, 1474, 116, 2066, 342, 236, 67,
    25, 244, 237, 12750, 18577, 350, 46, 99,
    239, 29, 195, 16, 17088, 240, 122, 83,
    100, 184, 3450, 8193, 1527, 87, 87, 185,
    92, 92, 13, 128, 57, 31, 61, 53,
    336, 30, 191, 89, 32, 53, 230, 68
};  // 66 candidates in total
// clang-format on

// Mask, relevant occupancy subsets and their attack sets for one square.
struct SliderSquare {
  Bitboard mask = 0;
  int bits = 0;
  std::vector<Bitboard> occupancies, references;
};

SliderSquare slider_square(Square s, const int (&dirs)[4][2]) {
  SliderSquare sq;
  Bitboard rank_edges = (Rank1 | Rank8) & ~(Rank1 << (8 * rank_of(s)));
  Bitboard file_edges = (FileA | FileH) & ~(FileA << file_of(s));
  sq.mask = ray_walk(s, 0, dirs) & ~(rank_edges | file_edges);
  sq.bits = popcount(sq.mask);
  Bitboard subset = 0;  // carry-rippler over every subset of the mask
  do {
    sq.occupancies.push_back(subset);
    sq.references.push_back(ray_walk(s, subset, dirs));
    subset = (subset - sq.mask) & sq.mask;
  } while (subset);
  return sq;
}

// Tries candidates from `seed` until one maps every subset without a
// destructive collision, filling `out` (1 << bits entries). Returns the number
// of candidates tried, or -1 if more than `limit` were needed.
int search_magic(const SliderSquare& sq, std::uint64_t seed, Bitboard* out, Bitboard& magic, int limit) {
  thread_local std::vector<unsigned> used_epoch;
  thread_local unsigned epoch = 0;
  used_epoch.assign(std::size_t{1} << sq.bits, 0);
  epoch = 0;
  const auto shift = static_cast<unsigned>(64 - sq.bits);
  Rng rng{seed};
  for (int attempt = 1; attempt <= limit; ++attempt) {
    Bitboard candidate;
    do {
      candidate = rng.sparse();
    } while (popcount((sq.mask * candidate) >> 56) < 6);
    ++epoch;
    bool ok = true;
    for (std::size_t i = 0; i < sq.occupancies.size() && ok; ++i) {
      std::size_t idx = (sq.occupancies[i] * candidate) >> shift;
      if (used_epoch[idx] != epoch) {
        used_epoch[idx] = epoch;
        out[idx] = sq.references[i];
      } else if (out[idx] != sq.references[i]) {
        ok = false;
      }
    }
    if (ok) {
      magic = candidate;
      return attempt;
    }
  }
  return -1;
}

// Fills `entries` for one slider kind, placing each square's attacks in the
// shared table starting at `table_offset`. Returns the next free offset.
std::size_t init_slider(SliderEntry* entries, const int (&dirs)[4][2], std::size_t table_offset,
                        [[maybe_unused]] const std::uint64_t (&seeds)[64]) {
  for (Square s = 0; s < 64; ++s) {
    const SliderSquare sq = slider_square(s, dirs);
    SliderEntry& e = entries[s];
    Bitboard* out = slider_table + table_offset;
    e.mask = sq.mask;
    e.attacks = out;
    e.shift = static_cast<unsigned>(64 - sq.bits);
    e.magic = 0;
#if FORK_USE_PEXT
    for (std::size_t i = 0; i < sq.occupancies.size(); ++i)
      out[e.index(sq.occupancies[i])] = sq.references[i];
#else
    // A stale seed table only costs time: keep searching until a magic is found.
    while (search_magic(sq, seeds[s], out, e.magic, 1 << 20) < 0) {}
#endif
    table_offset += std::size_t{1} << sq.bits;
  }
  return table_offset;
}

}  // namespace

int magic_search_attempts(bool rook, Square s, std::uint64_t seed, int limit) {
  const SliderSquare sq = slider_square(s, rook ? RookDirs : BishopDirs);
  std::vector<Bitboard> out(std::size_t{1} << sq.bits);
  Bitboard magic = 0;
  return search_magic(sq, seed, out.data(), magic, limit);
}

Bitboard rook_attacks_slow(Square s, Bitboard occ) { return ray_walk(s, occ, RookDirs); }
Bitboard bishop_attacks_slow(Square s, Bitboard occ) { return ray_walk(s, occ, BishopDirs); }

void init_bitboards() {
  static const bool once = (build_bitboard_tables(), true);
  (void)once;
}

void build_bitboard_tables() {
  for (Square s = 0; s < 64; ++s) {
    Bitboard b = bb(s);
    tables::pawn_attacks[White][s] = shift_north(shift_east(b) | shift_west(b));
    tables::pawn_attacks[Black][s] = shift_south(shift_east(b) | shift_west(b));

    Bitboard k = shift_east(b) | shift_west(b);
    k |= b;
    k |= shift_north(k) | shift_south(k);
    tables::king_attacks[s] = k & ~b;

    Bitboard n = 0;
    constexpr int jumps[8][2] = {{1, 2}, {2, 1}, {2, -1}, {1, -2}, {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}};
    for (const auto& j : jumps) {
      int f = file_of(s) + j[0], r = rank_of(s) + j[1];
      if (f >= 0 && f < 8 && r >= 0 && r < 8) n |= bb(make_square(f, r));
    }
    tables::knight_attacks[s] = n;
  }

  std::size_t offset = init_slider(tables::rook, RookDirs, 0, RookSeeds);
  init_slider(tables::bishop, BishopDirs, offset, BishopSeeds);

  for (Square a = 0; a < 64; ++a) {
    for (Square b = 0; b < 64; ++b) {
      tables::between[a][b] = tables::line[a][b] = 0;
      if (a == b) continue;
      if (rook_attacks_slow(a, 0) & bb(b)) {
        tables::line[a][b] = (rook_attacks_slow(a, 0) & rook_attacks_slow(b, 0)) | bb(a) | bb(b);
        tables::between[a][b] = rook_attacks_slow(a, bb(b)) & rook_attacks_slow(b, bb(a));
      } else if (bishop_attacks_slow(a, 0) & bb(b)) {
        tables::line[a][b] = (bishop_attacks_slow(a, 0) & bishop_attacks_slow(b, 0)) | bb(a) | bb(b);
        tables::between[a][b] = bishop_attacks_slow(a, bb(b)) & bishop_attacks_slow(b, bb(a));
      }
    }
  }
}

}  // namespace forkeng
