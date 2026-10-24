// types: basic chess value types shared by every module.
//
// Purpose: squares, colors, piece types and pieces, castling-right bits, the
// 16-bit Move encoding and the fixed-capacity MoveList.
// Invariants:
// - Square a1 = 0 ... h8 = 63; NoSquare = 64 is never used as a table index.
// - Piece = color * 8 + type; NoPiece = 15. side_of/kind_of are only valid
//   for real pieces.
// - Move: from (bits 0-5), to (6-11), flag (12-15); raw 0 is NoMove. Castling
//   is king origin -> castling rook square. Flags 3, 6 and 7 are never
//   produced (is_pseudo_legal rejects them).
// - MoveList holds MaxMoves = 323 moves, the most any position set_fen accepts
//   (or any position reached from one) can have; see MoveList.
#pragma once

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

namespace forkeng {

using Bitboard = std::uint64_t;
using Key = std::uint64_t;

// Squares: a1 = 0, b1 = 1, ..., h8 = 63.
using Square = int;
constexpr Square NoSquare = 64;

constexpr int file_of(Square s) { return s & 7; }
constexpr int rank_of(Square s) { return s >> 3; }
constexpr Square make_square(int file, int rank) { return rank * 8 + file; }
constexpr Bitboard bb(Square s) { return Bitboard{1} << s; }

enum Color : std::uint8_t { White = 0, Black = 1 };
constexpr Color operator~(Color c) { return static_cast<Color>(c ^ 1); }

// Square seen from `c`'s side of the board (a1 <-> a8 for Black).
constexpr Square relative(Color c, Square s) { return c == White ? s : s ^ 56; }
constexpr int rank_from(Color c, Square s) { return c == White ? rank_of(s) : 7 - rank_of(s); }
constexpr int forward(Color c) { return c == White ? 8 : -8; }

enum PieceType : std::uint8_t { Pawn, Knight, Bishop, Rook, Queen, King, NoPieceType };

// Piece = color * 8 + type.
using Piece = int;
constexpr Piece NoPiece = 15;
constexpr Piece piece_of(Color c, PieceType t) { return c * 8 + t; }
constexpr Color side_of(Piece p) { return Color(p >> 3); }
constexpr PieceType kind_of(Piece p) { return PieceType(p & 7); }

// Castling rights bits.
enum : std::uint8_t { WhiteOO = 1, WhiteOOO = 2, BlackOO = 4, BlackOOO = 8, AllCastling = 15 };

// Move: from (bits 0-5) | to (bits 6-11) | flag (bits 12-15).
// Castling is encoded as king origin -> castling rook square.
enum MoveFlag : std::uint8_t {
  Quiet = 0,
  DoublePush = 1,
  Castle = 2,
  Capture = 4,
  EnPassant = 5,
  PromoKnight = 8,
  PromoBishop = 9,
  PromoRook = 10,
  PromoQueen = 11,
  PromoCaptureKnight = 12,
  PromoCaptureBishop = 13,
  PromoCaptureRook = 14,
  PromoCaptureQueen = 15
};

class Move {
 public:
  constexpr Move() = default;
  constexpr Move(Square from, Square to, int flag)
      : data_(static_cast<std::uint16_t>(from | (to << 6) | (flag << 12))) {}
  static constexpr Move from_raw(std::uint16_t raw) {
    Move m;
    m.data_ = raw;
    return m;
  }

  constexpr Square from() const { return data_ & 63; }
  constexpr Square to() const { return (data_ >> 6) & 63; }
  constexpr int flag() const { return data_ >> 12; }
  constexpr std::uint16_t raw() const { return data_; }

  constexpr bool is_none() const { return data_ == 0; }
  constexpr bool is_capture() const { return flag() & 4; }
  constexpr bool is_promotion() const { return flag() & 8; }
  constexpr bool is_castle() const { return flag() == Castle; }
  constexpr bool is_en_passant() const { return flag() == EnPassant; }
  constexpr PieceType promo_type() const { return PieceType(Knight + (flag() & 3)); }

  constexpr bool operator==(const Move&) const = default;

 private:
  std::uint16_t data_ = 0;
};

constexpr Move NoMove{};

// An upper bound on the moves in any position whose material passes set_fen's
// promotion rule (extra pieces need missing pawns): with all eight pawns
// promoted to queens, 9 queens x 27 + 2 rooks x 14 + 2 bishops x 13 +
// 2 knights x 8 + 8 king steps + 2 castlings = 323 pseudo-legal moves, and a
// promoting pawn (at most 12 moves) never beats the queen it becomes
// (review suspicion 1, 2026-10-24).
constexpr std::size_t MaxMoves = 323;

struct MoveList {
  std::array<Move, MaxMoves> moves;
  std::size_t count = 0;

  void add(Move m) {
    assert(count < moves.size());
    moves[count++] = m;
  }
  std::size_t size() const { return count; }
  const Move* begin() const { return moves.data(); }
  const Move* end() const { return moves.data() + count; }
  Move operator[](std::size_t i) const { return moves[i]; }
  bool contains(Move m) const {
    for (Move x : *this)
      if (x == m) return true;
    return false;
  }
};

}  // namespace forkeng
