// Board state, FEN, make/unmake.
#pragma once

#include <string>
#include <string_view>
#include <vector>

#include "core/bitboard.hpp"
#include "core/types.hpp"

namespace fork {

// Builds attack tables and Zobrist keys. Call once before using Position.
void init();

class Position {
 public:
  static constexpr std::string_view StartFen =
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

  Position();  // the start position

  // Parses `fen`. On failure returns false, leaves the position unchanged and
  // describes the problem in `error` (if given).
  bool set_fen(std::string_view fen, std::string* error = nullptr);
  std::string fen() const;

  Color side_to_move() const { return side_; }
  Piece piece_on(Square s) const { return board_[s]; }
  Bitboard pieces() const { return by_color_[White] | by_color_[Black]; }
  Bitboard pieces(Color c) const { return by_color_[c]; }
  Bitboard pieces(PieceType t) const { return by_type_[t]; }
  Bitboard pieces(Color c, PieceType t) const { return by_color_[c] & by_type_[t]; }
  Bitboard pieces(Color c, PieceType t1, PieceType t2) const {
    return by_color_[c] & (by_type_[t1] | by_type_[t2]);
  }
  Square king_square(Color c) const { return lsb(pieces(c, King)); }

  int castling_rights() const { return castling_; }
  Square ep_square() const { return ep_; }  // NoSquare unless an ep capture is legal
  int halfmove_clock() const { return halfmove_; }
  int fullmove_number() const { return fullmove_; }
  Key key() const { return key_; }
  Key compute_key() const;  // from scratch, for verification
  std::size_t ply_count() const { return history_.size(); }

  Bitboard checkers() const { return checkers_; }
  bool in_check() const { return checkers_ != 0; }
  Bitboard attackers_to(Square s, Bitboard occ) const;  // both colors
  bool attacked_by(Color by, Square s, Bitboard occ) const;
  Bitboard pinned(Color c) const;  // c's pieces pinned to c's king

  bool is_pseudo_legal(Move m) const;  // any 16-bit pattern is safe to pass
  bool is_legal(Move m) const;         // requires is_pseudo_legal(m)

  void make(Move m);
  void unmake(Move m);
  void make_null();
  void unmake_null();

  std::string move_to_uci(Move m) const;
  Move parse_uci(std::string_view uci) const;  // a legal move, or NoMove

  Position mirrored() const;  // ranks flipped, colors swapped
  bool same_state(const Position& o) const;

  // Castling geometry for a castle move encoded as king -> rook square.
  static Square castle_king_to(Square king_from, Square rook_from) {
    return rook_from > king_from ? king_from + 2 : king_from - 2;
  }
  static Square castle_rook_to(Square king_from, Square rook_from) {
    return rook_from > king_from ? king_from + 1 : king_from - 1;
  }

 private:
  struct Undo {
    Key key;
    Bitboard checkers;
    Piece captured;
    int castling;
    Square ep;
    int halfmove;
  };

  void clear();
  void put(Piece p, Square s);
  void remove(Square s);
  bool ep_capture_legal(Square ep) const;  // for the side to move
  void finish_setup();                     // key, checkers after board setup

  Piece board_[64];
  Bitboard by_type_[6];
  Bitboard by_color_[2];
  Color side_ = White;
  int castling_ = 0;
  Square ep_ = NoSquare;
  int halfmove_ = 0;
  int fullmove_ = 1;
  Key key_ = 0;
  Bitboard checkers_ = 0;
  std::vector<Undo> history_;
};

}  // namespace fork
