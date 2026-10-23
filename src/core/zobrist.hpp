// zobrist: hashing keys.
//
// Purpose: random keys for piece-squares, side, castling rights, en passant
// files and material counts.
// Invariants:
// - Keys come from a fixed-seed splitmix64 stream, so keys and the bench
//   signature are identical on every build. New key tables must be appended
//   after the existing ones, or every existing key (and bench) changes.
#pragma once

#include "core/types.hpp"

namespace fork::zobrist {

extern Key piece_square[16][64];  // indexed by Piece (NoPiece row unused)
extern Key side;                  // xored in when Black is to move
extern Key castling[16];
extern Key ep_file[8];
// material[piece][n] is xored in for the n-th piece of that kind (0-based),
// so a material key depends only on the piece counts.
extern Key material[16][16];

void init();

}  // namespace fork::zobrist
