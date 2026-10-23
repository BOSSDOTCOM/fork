#include "core/bitboard.hpp"

#include <vector>

namespace fork {

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

// Fills `entries` for one slider kind, placing each square's attacks in
// `table` starting at `table_offset`. Returns the next free offset.
std::size_t init_slider(SliderEntry* entries, const int (&dirs)[4][2],
                        std::size_t table_offset, [[maybe_unused]] Rng& rng) {
  std::vector<Bitboard> occupancies, references;
  [[maybe_unused]] std::vector<unsigned> used_epoch;
  [[maybe_unused]] unsigned epoch = 0;

  for (Square s = 0; s < 64; ++s) {
    Bitboard rank_edges = (Rank1 | Rank8) & ~(Rank1 << (8 * rank_of(s)));
    Bitboard file_edges = (FileA | FileH) & ~(FileA << file_of(s));
    SliderEntry& e = entries[s];
    e.mask = ray_walk(s, 0, dirs) & ~(rank_edges | file_edges);
    int bits = popcount(e.mask);
    std::size_t size = std::size_t{1} << bits;
    Bitboard* out = slider_table + table_offset;
    e.attacks = out;
    e.shift = static_cast<unsigned>(64 - bits);
    e.magic = 0;

    // Enumerate every subset of the mask (carry-rippler).
    occupancies.clear();
    references.clear();
    Bitboard subset = 0;
    do {
      occupancies.push_back(subset);
      references.push_back(ray_walk(s, subset, dirs));
      subset = (subset - e.mask) & e.mask;
    } while (subset);

#if FORK_USE_PEXT
    for (std::size_t i = 0; i < occupancies.size(); ++i)
      out[e.index(occupancies[i])] = references[i];
#else
    used_epoch.assign(size, 0);
    for (;;) {
      Bitboard magic = rng.sparse();
      if (popcount((e.mask * magic) >> 56) < 6) continue;
      e.magic = magic;
      ++epoch;
      bool ok = true;
      for (std::size_t i = 0; i < occupancies.size() && ok; ++i) {
        std::size_t idx = e.index(occupancies[i]);
        if (used_epoch[idx] != epoch) {
          used_epoch[idx] = epoch;
          out[idx] = references[i];
        } else if (out[idx] != references[i]) {
          ok = false;
        }
      }
      if (ok) break;
    }
#endif
    table_offset += size;
  }
  return table_offset;
}

}  // namespace

Bitboard rook_attacks_slow(Square s, Bitboard occ) { return ray_walk(s, occ, RookDirs); }
Bitboard bishop_attacks_slow(Square s, Bitboard occ) { return ray_walk(s, occ, BishopDirs); }

void init_bitboards() {
  static bool done = false;
  if (done) return;
  done = true;

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

  Rng rng{0x5EED'F0F0'C0FF'EE11ULL};
  std::size_t offset = init_slider(tables::rook, RookDirs, 0, rng);
  init_slider(tables::bishop, BishopDirs, offset, rng);

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

}  // namespace fork
