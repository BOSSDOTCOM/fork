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
// - A Position is owned by one thread; search threads each get a copy, which
//   keeps a full State reserve (no allocation in make() on the copy).
#pragma once

#include <string>
#include <string_view>
#include <vector>

#include "core/bitboard.hpp"
#include "core/types.hpp"

namespace forkeng {

// Builds attack tables and Zobrist keys once (thread-safe). Call before any
// search thread starts; Position() also calls it.
void init();

// The per-ply record: what make() pushes and unmake() pops. Kept in a stack so
// earlier keys stay available for repetition detection. Only what Fork's code
// reads is stored.
struct State {
  // Hash and rule state.
  Key key;
  int castling;
  Square ep;  // NoSquare unless an ep capture is legal
  int halfmove;
  // Positions on the stack, ending with this one, that belong to the game since
  // set_fen or the last null move: 1 at the FEN, +1 per move, 0 right after a
  // null move (that position exists only because a side passed). Bounds the
  // repetition window (review M2).
  int game_span;
  // Check information for the side to move.
  Bitboard checkers;     // enemy pieces attacking our king
  Bitboard pinned;       // our pieces that are the only piece between our king and an enemy slider
  Bitboard discoverers;  // our pieces that are the only piece between the enemy king and one of our sliders
  // For unmake().
  Piece captured;  // the piece the move that led here captured, or NoPiece

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
  Piece piece_at(Square s) const { return static_cast<Piece>(board_[s]); }
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
  Square ep_target() const { return state().ep; }
  int halfmove_clock() const { return state().halfmove; }
  int fullmove_number() const { return fullmove_; }
  Key key() const { return state().key; }
  std::size_t ply_count() const { return states_.size() - 1; }  // moves made since set_fen

  Bitboard checkers() const { return state().checkers; }
  bool in_check() const { return state().checkers != 0; }
  // Pieces of the side to move that may only move along the line to their king.
  Bitboard pinned() const { return state().pinned; }
  // Pieces of the side to move that give discovered check by leaving their line.
  Bitboard discoverers() const { return state().discoverers; }

  Bitboard attackers_to(Square s, Bitboard occ) const;  // both colors
  bool attacked_by(Color by, Square s, Bitboard occ) const;

  bool is_pseudo_legal(Move m) const;  // any 16-bit pattern is safe to pass
  bool is_legal(Move m) const;         // requires is_pseudo_legal(m)
  bool gives_check(Move m) const;      // requires is_pseudo_legal(m) && is_legal(m)
  Key predicted_key(Move m) const;     // exact key after make(m), for TT prefetch
  Key predicted_null_key() const;      // exact key after make_null(), for TT prefetch
  // Occupancy after the side to move captures en passant from `from` to `to`.
  Bitboard occupancy_after_ep(Square from, Square to) const;
  // The square of the piece a capture by the side to move removes.
  Square capture_square(Move m) const { return m.is_en_passant() ? m.to() - forward(side_) : m.to(); }

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

  // Where king and rook land for a castle move encoded as king -> rook square:
  // the king goes two files towards the rook, and the rook to the square the
  // king passed over.
  struct CastleLanding {
    Square king, rook;
  };
  static CastleLanding castle_landing(Square king_from, Square rook_from) {
    const int towards_rook = rook_from > king_from ? 1 : -1;
    return {king_from + 2 * towards_rook, king_from + towards_rook};
  }

 private:
  State& ply_state() { return states_.back(); }
  void clear();
  void put(Piece p, Square s);
  void remove(Square s);
  void toggle_keys(State& s, Piece p, Square sq) const;
  void refresh_check_info(State& s) const;  // checkers, pinned, discoverers
  Bitboard lone_shields(Square king, Bitboard shields, Bitboard rook_sliders, Bitboard bishop_sliders) const;
  bool ep_capture_legal(Square ep) const;  // for the side to move
  // True when material alone rules out a mate by side c (DESIGN.md 4.5).
  bool cannot_mate(Color c) const;
  void finish_setup();  // state from scratch after board setup

  // States reserved up front; make() grows the stack only beyond this.
  static constexpr std::size_t StateReserve = 1024;

  // The State stack. A copy reserves room for StateReserve more plies, so
  // make() on a copied Position (a search thread's board) does not allocate
  // and does not move the States under a caller's reference (review M1).
  struct StateStack : std::vector<State> {
    StateStack() = default;
    // Not the base copy constructor on purpose: copy_from reserves first.
    // GCC -Wextra wants the base named, which clang-tidy calls redundant.
    // NOLINTNEXTLINE(bugprone-copy-constructor-init,readability-redundant-member-init)
    StateStack(const StateStack& o) : std::vector<State>() { copy_from(o); }
    StateStack& operator=(const StateStack& o) {
      if (this != &o) copy_from(o);
      return *this;
    }
    StateStack(StateStack&&) noexcept = default;
    StateStack& operator=(StateStack&&) noexcept = default;
    void copy_from(const StateStack& o) {
      reserve(o.size() + StateReserve);
      assign(o.begin(), o.end());
    }
  };

  std::uint8_t board_[64];  // Piece per square, stored narrow (64 bytes instead of 256)
  Bitboard by_type_[6];
  Bitboard by_color_[2];
  Color side_ = White;
  int fullmove_ = 1;
  StateStack states_;  // states_.back() is the current ply
};

}  // namespace forkeng
