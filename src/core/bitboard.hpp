// Bitboard helpers, precomputed attack tables and slider lookups.
#pragma once

#include <bit>

#include "core/types.hpp"

#if defined(__BMI2__) && !defined(FORK_NO_PEXT)
#define FORK_USE_PEXT 1
#include <immintrin.h>
#else
#define FORK_USE_PEXT 0
#endif

namespace fork {

constexpr Bitboard FileA = 0x0101010101010101ULL;
constexpr Bitboard FileH = FileA << 7;
constexpr Bitboard Rank1 = 0xFFULL;
constexpr Bitboard Rank8 = Rank1 << 56;

inline int popcount(Bitboard b) { return std::popcount(b); }
inline Square lsb(Bitboard b) { assert(b); return std::countr_zero(b); }
inline Square pop_lsb(Bitboard& b) { Square s = lsb(b); b &= b - 1; return s; }
inline bool more_than_one(Bitboard b) { return b & (b - 1); }

// One-step shifts that drop squares falling off the a/h files.
constexpr Bitboard shift_north(Bitboard b) { return b << 8; }
constexpr Bitboard shift_south(Bitboard b) { return b >> 8; }
constexpr Bitboard shift_east(Bitboard b) { return (b & ~FileH) << 1; }
constexpr Bitboard shift_west(Bitboard b) { return (b & ~FileA) >> 1; }

// Slider lookup entry for one square. With PEXT the magic and shift are unused.
struct SliderEntry {
  Bitboard mask;
  Bitboard magic;
  const Bitboard* attacks;
  unsigned shift;

  std::size_t index(Bitboard occ) const {
#if FORK_USE_PEXT
    return _pext_u64(occ, mask);
#else
    return ((occ & mask) * magic) >> shift;
#endif
  }
};

namespace tables {
extern Bitboard pawn_attacks[2][64];
extern Bitboard knight_attacks[64];
extern Bitboard king_attacks[64];
extern Bitboard between[64][64];  // squares strictly between two aligned squares
extern Bitboard line[64][64];     // full line through two aligned squares, else 0
extern SliderEntry rook[64];
extern SliderEntry bishop[64];
}  // namespace tables

// Builds every table once (thread-safe); call at startup (main, tests).
void init_bitboards();
// Rebuilds the tables unconditionally. Only for timing startup cost: never
// call while another thread may be reading the tables.
void build_bitboard_tables();

// Reference slider attacks by ray-walking (used for table building and tests).
Bitboard rook_attacks_slow(Square s, Bitboard occ);
Bitboard bishop_attacks_slow(Square s, Bitboard occ);

inline Bitboard pawn_attacks(Color c, Square s) { return tables::pawn_attacks[c][s]; }
inline Bitboard knight_attacks(Square s) { return tables::knight_attacks[s]; }
inline Bitboard king_attacks(Square s) { return tables::king_attacks[s]; }
inline Bitboard between(Square a, Square b) { return tables::between[a][b]; }
inline Bitboard line(Square a, Square b) { return tables::line[a][b]; }

inline Bitboard rook_attacks(Square s, Bitboard occ) {
  const SliderEntry& e = tables::rook[s];
  return e.attacks[e.index(occ)];
}
inline Bitboard bishop_attacks(Square s, Bitboard occ) {
  const SliderEntry& e = tables::bishop[s];
  return e.attacks[e.index(occ)];
}
inline Bitboard queen_attacks(Square s, Bitboard occ) {
  return rook_attacks(s, occ) | bishop_attacks(s, occ);
}

// Attacks of a non-pawn piece type from `s`.
inline Bitboard attacks(PieceType t, Square s, Bitboard occ) {
  switch (t) {
    case Knight: return knight_attacks(s);
    case Bishop: return bishop_attacks(s, occ);
    case Rook: return rook_attacks(s, occ);
    case Queen: return queen_attacks(s, occ);
    case King: return king_attacks(s);
    default: assert(false); return 0;
  }
}

}  // namespace fork
