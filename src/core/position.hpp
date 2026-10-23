// position: board state, FEN, make/unmake, legality and check queries.
//
// Purpose: the board (bitboards and mailbox), the per-ply State stack, FEN
// input/output, and move validation for moves from any source.
// Invariants:
// - by_type_/by_color_/board_ always describe the same placement.
// - states_.back() is the current ply; every State field equals what
//   compute_state() derives from the board (checked at every perft node).
// - The ep square is stored, hashed and printed only when an ep capture is
//   legal (DESIGN.md 4.4).
// - make()/unmake() never allocate while the State stack is within its reserve,
//   and unmake() restores an identical position (same_state).
// - A Position is owned by one thread; search threads each get a copy.
#pragma once

#include <string>
#include <string_view>
#include <vector>

#include "core/bitboard.hpp"
#include "core/types.hpp"

namespace fork {

// Builds attack tables and Zobrist keys once (thread-safe). Call before any
// search thread starts; Position() also calls it.
void init();

// Everything about a position that make() computes once per ply and unmake()
// restores by popping. Kept in a stack so earlier keys stay available for
// repetition detection.
struct State {
  Key key;
  Key pawn_key;
  Key material_key;
  Key non_pawn_key[2];   // per color, kings included
  Bitboard checkers;     // enemy pieces giving check to the side to move
  Bitboard blockers[2];  // pieces (either color) whose removal alone would expose c's king to an enemy slider
  Bitboard pinners[2];   // enemy sliders whose only obstacle to c's king is one of c's pieces
  Bitboard checking_squares[6];  // squares from which the side to move would give check, per piece type
  int castling;
  Square ep;  // NoSquare unless an ep capture is legal
  int halfmove;
  Piece captured;  // piece captured by the move that led here

  bool operator==(const State&) const = default;
};

class Position {
 public:
  static constexpr std::string_view StartFen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

  Position();  // the start position

  // Parses `fen`. On failure returns false, leaves the position unchanged and
  // describes the problem in `error` (if given).
  bool set_fen(std::string_view fen, std::string* error = nullptr);
  std::string fen() const;

  Color side_to_move() const { return side_; }
  Piece piece_on(Square s) const { return static_cast<Piece>(board_[s]); }
  Bitboard pieces() const { return by_color_[White] | by_color_[Black]; }
  Bitboard pieces(Color c) const { return by_color_[c]; }
  Bitboard pieces(PieceType t) const { return by_type_[t]; }
  Bitboard pieces(Color c, PieceType t) const { return by_color_[c] & by_type_[t]; }
  Bitboard pieces(Color c, PieceType t1, PieceType t2) const {
    return by_color_[c] & (by_type_[t1] | by_type_[t2]);
  }
  int count(Color c, PieceType t) const { return popcount(pieces(c, t)); }
  Square king_square(Color c) const { return lsb(pieces(c, King)); }

  const State& state() const { return states_.back(); }
  int castling_rights() const { return state().castling; }
  Square ep_square() const { return state().ep; }
  int halfmove_clock() const { return state().halfmove; }
  int fullmove_number() const { return fullmove_; }
  Key key() const { return state().key; }
  Key pawn_key() const { return state().pawn_key; }
  Key material_key() const { return state().material_key; }
  Key non_pawn_key(Color c) const { return state().non_pawn_key[c]; }
  std::size_t ply_count() const { return states_.size() - 1; }  // moves made since set_fen

  Bitboard checkers() const { return state().checkers; }
  bool in_check() const { return state().checkers != 0; }
  Bitboard blockers(Color c) const { return state().blockers[c]; }
  Bitboard pinners(Color c) const { return state().pinners[c]; }
  Bitboard pinned(Color c) const { return state().blockers[c] & pieces(c); }
  Bitboard checking_squares(PieceType t) const { return state().checking_squares[t]; }

  Bitboard attackers_to(Square s, Bitboard occ) const;  // both colors
  bool attacked_by(Color by, Square s, Bitboard occ) const;

  bool is_pseudo_legal(Move m) const;  // any 16-bit pattern is safe to pass
  bool is_legal(Move m) const;         // requires is_pseudo_legal(m)
  bool gives_check(Move m) const;      // requires is_pseudo_legal(m) && is_legal(m)
  Key predicted_key(Move m) const;     // exact key after make(m), for TT prefetch

  void make(Move m);
  void unmake(Move m);
  void make_null();
  void unmake_null();

  // Draw and repetition queries (the rules are documented in DESIGN.md 4.5).
  int repetition_count()
      const;  // occurrences of this position since the last irreversible move, this one included
  bool insufficient_material() const;
  bool fifty_move_reached() const { return state().halfmove >= 100; }

  std::string move_to_uci(Move m) const;
  Move parse_uci(std::string_view uci) const;  // a legal move, or NoMove

  Position mirrored() const;  // ranks flipped, colors swapped
  bool same_state(const Position& o) const;

  // Recomputes every key and the per-ply state from the board, for tests.
  State compute_state() const;

  // Castling geometry for a castle move encoded as king -> rook square.
  static Square castle_king_to(Square king_from, Square rook_from) {
    return rook_from > king_from ? king_from + 2 : king_from - 2;
  }
  static Square castle_rook_to(Square king_from, Square rook_from) {
    return rook_from > king_from ? king_from + 1 : king_from - 1;
  }

 private:
  State& st() { return states_.back(); }
  void clear();
  void put(Piece p, Square s);
  void remove(Square s);
  void toggle_keys(State& s, Piece p, Square sq) const;
  void update_check_info(State& s) const;  // checkers, blockers, pinners, check squares
  bool ep_capture_legal(Square ep) const;  // for the side to move
  bool has_insufficient_material(Color c) const;
  void finish_setup();  // state from scratch after board setup

  std::uint8_t board_[64];  // Piece per square, stored narrow (64 bytes instead of 256)
  Bitboard by_type_[6];
  Bitboard by_color_[2];
  Color side_ = White;
  int fullmove_ = 1;
  std::vector<State> states_;  // states_.back() is the current ply
};

}  // namespace fork
