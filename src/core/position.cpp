#include "core/position.hpp"

#include <algorithm>
#include <array>
#include <charconv>

#include "core/movegen.hpp"
#include "core/zobrist.hpp"

namespace fork {

namespace {

constexpr std::string_view PieceChars = "PNBRQK??pnbrqk";

struct CastleInfo {
  int right;
  Square king;
  Square rook;
  char fen;
};
constexpr CastleInfo Castles[4] = {
    {WhiteOO, 4, 7, 'K'}, {WhiteOOO, 4, 0, 'Q'}, {BlackOO, 60, 63, 'k'}, {BlackOOO, 60, 56, 'q'}};

// Rights that survive a move touching each square (as origin or destination).
constexpr std::array<int, 64> CastlingMask = [] {
  std::array<int, 64> m{};
  for (int& x : m) x = AllCastling;
  for (const CastleInfo& c : Castles) {
    m[c.king] &= ~c.right;
    m[c.rook] &= ~c.right;
  }
  return m;
}();

std::string square_name(Square s) {
  return {char('a' + file_of(s)), char('1' + rank_of(s))};
}

}  // namespace

void init() {
  static const bool once = [] {
    init_bitboards();
    zobrist::init();
    return true;
  }();
  (void)once;
}

Position::Position() {
  init();
  clear();
  bool ok = set_fen(StartFen);
  assert(ok);
  (void)ok;
}

void Position::clear() {
  std::fill(std::begin(board_), std::end(board_), NoPiece);
  std::fill(std::begin(by_type_), std::end(by_type_), 0);
  std::fill(std::begin(by_color_), std::end(by_color_), 0);
  side_ = White;
  castling_ = 0;
  ep_ = NoSquare;
  halfmove_ = 0;
  fullmove_ = 1;
  key_ = 0;
  checkers_ = 0;
  history_.clear();
  history_.reserve(1024);
}

void Position::put(Piece p, Square s) {
  board_[s] = p;
  by_type_[type_of(p)] |= bb(s);
  by_color_[color_of(p)] |= bb(s);
}

void Position::remove(Square s) {
  Piece p = board_[s];
  by_type_[type_of(p)] &= ~bb(s);
  by_color_[color_of(p)] &= ~bb(s);
  board_[s] = NoPiece;
}

Bitboard Position::attackers_to(Square s, Bitboard occ) const {
  return (pawn_attacks(Black, s) & pieces(White, Pawn)) |
         (pawn_attacks(White, s) & pieces(Black, Pawn)) |
         (knight_attacks(s) & pieces(Knight)) |
         (king_attacks(s) & pieces(King)) |
         (bishop_attacks(s, occ) & (pieces(Bishop) | pieces(Queen))) |
         (rook_attacks(s, occ) & (pieces(Rook) | pieces(Queen)));
}

bool Position::attacked_by(Color by, Square s, Bitboard occ) const {
  return (pawn_attacks(~by, s) & pieces(by, Pawn)) ||
         (knight_attacks(s) & pieces(by, Knight)) ||
         (king_attacks(s) & pieces(by, King)) ||
         (bishop_attacks(s, occ) & pieces(by, Bishop, Queen)) ||
         (rook_attacks(s, occ) & pieces(by, Rook, Queen));
}

Bitboard Position::pinned(Color c) const {
  Square ksq = king_square(c);
  Color them = ~c;
  Bitboard snipers = (rook_attacks(ksq, pieces(them)) & pieces(them, Rook, Queen)) |
                     (bishop_attacks(ksq, pieces(them)) & pieces(them, Bishop, Queen));
  Bitboard result = 0;
  while (snipers) {
    Bitboard b = between(ksq, pop_lsb(snipers)) & pieces();
    if (b && !more_than_one(b)) result |= b & pieces(c);
  }
  return result;
}

bool Position::ep_capture_legal(Square ep) const {
  Color us = side_;
  Square capsq = ep - forward(us);
  Square ksq = king_square(us);
  Bitboard candidates = pawn_attacks(~us, ep) & pieces(us, Pawn);
  while (candidates) {
    Square from = pop_lsb(candidates);
    Bitboard occ = (pieces() ^ bb(from) ^ bb(capsq)) | bb(ep);
    if (!(attackers_to(ksq, occ) & pieces(~us) & ~bb(capsq))) return true;
  }
  return false;
}

Key Position::compute_key() const {
  Key k = 0;
  for (Square s = 0; s < 64; ++s)
    if (board_[s] != NoPiece) k ^= zobrist::piece_square[board_[s]][s];
  if (side_ == Black) k ^= zobrist::side;
  k ^= zobrist::castling[castling_];
  if (ep_ != NoSquare) k ^= zobrist::ep_file[file_of(ep_)];
  return k;
}

void Position::finish_setup() {
  key_ = compute_key();
  checkers_ = attackers_to(king_square(side_), pieces()) & pieces(~side_);
}

bool Position::set_fen(std::string_view fen, std::string* error) {
  auto fail = [error](std::string msg) {
    if (error) *error = std::move(msg);
    return false;
  };

  std::vector<std::string_view> fields;
  for (std::size_t i = 0; i < fen.size();) {
    while (i < fen.size() && (fen[i] == ' ' || fen[i] == '\t')) ++i;
    std::size_t j = i;
    while (j < fen.size() && fen[j] != ' ' && fen[j] != '\t') ++j;
    if (j > i) fields.push_back(fen.substr(i, j - i));
    i = j;
  }
  if (fields.size() != 4 && fields.size() != 6)
    return fail("expected 4 or 6 fields, got " + std::to_string(fields.size()));

  Position p = *this;
  p.clear();

  // Placement, from rank 8 down to rank 1.
  int rank = 7, file = 0;
  for (char c : fields[0]) {
    if (c == '/') {
      if (file != 8 || rank == 0) return fail("bad rank layout in placement");
      --rank;
      file = 0;
    } else if (c >= '1' && c <= '8') {
      file += c - '0';
      if (file > 8) return fail("rank too long in placement");
    } else {
      std::size_t idx = PieceChars.find(c);
      if (idx == std::string_view::npos || c == '?') return fail(std::string("bad piece character '") + c + "'");
      if (file >= 8) return fail("rank too long in placement");
      p.put(Piece(idx), make_square(file, rank));
      ++file;
    }
  }
  if (rank != 0 || file != 8) return fail("placement does not describe 8 ranks of 8 squares");

  for (Color c : {White, Black}) {
    if (popcount(p.pieces(c, King)) != 1) return fail("each side needs exactly one king");
    if (popcount(p.pieces(c, Pawn)) > 8) return fail("more than 8 pawns for one side");
    if (popcount(p.pieces(c)) > 16) return fail("more than 16 pieces for one side");
  }
  if (p.pieces(Pawn) & (Rank1 | Rank8)) return fail("pawn on the first or last rank");

  if (fields[1] == "w") p.side_ = White;
  else if (fields[1] == "b") p.side_ = Black;
  else return fail("side to move must be 'w' or 'b'");

  if (fields[2] != "-") {
    for (char c : fields[2]) {
      const CastleInfo* info = nullptr;
      for (const CastleInfo& ci : Castles)
        if (ci.fen == c) info = &ci;
      if (!info) return fail(std::string("bad castling character '") + c + "'");
      if (p.castling_ & info->right) return fail("repeated castling right");
      Color col = c == 'K' || c == 'Q' ? White : Black;
      if (p.board_[info->king] != make_piece(col, King) || p.board_[info->rook] != make_piece(col, Rook))
        return fail(std::string("castling right '") + c + "' without king and rook on their home squares");
      p.castling_ |= info->right;
    }
  }

  // The ep square is accepted when plausible and kept only if a legal ep
  // capture exists (see DESIGN.md 4.4).
  Square ep = NoSquare;
  if (fields[3] != "-") {
    std::string_view f = fields[3];
    if (f.size() != 2 || f[0] < 'a' || f[0] > 'h' || f[1] < '1' || f[1] > '8')
      return fail("bad en passant square");
    ep = make_square(f[0] - 'a', f[1] - '1');
    Color us = p.side_;
    if (relative_rank(us, ep) != 5 || p.board_[ep] != NoPiece ||
        p.board_[ep + forward(us)] != NoPiece ||
        p.board_[ep - forward(us)] != make_piece(~us, Pawn))
      return fail("en passant square is not consistent with a double pawn push");
  }

  if (fields.size() == 6) {
    auto parse = [](std::string_view s, int& out) {
      auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), out);
      return ec == std::errc() && ptr == s.data() + s.size() && out >= 0;
    };
    if (!parse(fields[4], p.halfmove_)) return fail("bad halfmove clock");
    if (!parse(fields[5], p.fullmove_)) return fail("bad fullmove number");
    p.fullmove_ = std::max(p.fullmove_, 1);
  }

  if (p.attackers_to(p.king_square(~p.side_), p.pieces()) & p.pieces(p.side_))
    return fail("the side not to move is in check");

  if (ep != NoSquare && p.ep_capture_legal(ep)) p.ep_ = ep;
  p.finish_setup();
  *this = std::move(p);
  return true;
}

std::string Position::fen() const {
  std::string s;
  for (int r = 7; r >= 0; --r) {
    int empty = 0;
    for (int f = 0; f < 8; ++f) {
      Piece p = board_[make_square(f, r)];
      if (p == NoPiece) {
        ++empty;
        continue;
      }
      if (empty) s += char('0' + empty);
      empty = 0;
      s += PieceChars[p];
    }
    if (empty) s += char('0' + empty);
    if (r) s += '/';
  }
  s += side_ == White ? " w " : " b ";
  if (!castling_) s += '-';
  for (const CastleInfo& c : Castles)
    if (castling_ & c.right) s += c.fen;
  s += ' ';
  s += ep_ == NoSquare ? "-" : square_name(ep_);
  s += ' ' + std::to_string(halfmove_) + ' ' + std::to_string(fullmove_);
  return s;
}

void Position::make(Move m) {
  history_.push_back({key_, checkers_, NoPiece, castling_, ep_, halfmove_});
  Undo& u = history_.back();
  const Color us = side_, them = ~us;
  const Square from = m.from(), to = m.to();
  Key k = key_;

  if (ep_ != NoSquare) {
    k ^= zobrist::ep_file[file_of(ep_)];
    ep_ = NoSquare;
  }
  ++halfmove_;
  Square new_ep = NoSquare;

  if (m.is_castle()) {
    Square kto = castle_king_to(from, to), rto = castle_rook_to(from, to);
    Piece king = board_[from], rook = board_[to];
    remove(from);
    remove(to);
    put(king, kto);
    put(rook, rto);
    k ^= zobrist::piece_square[king][from] ^ zobrist::piece_square[king][kto] ^
         zobrist::piece_square[rook][to] ^ zobrist::piece_square[rook][rto];
  } else {
    Piece p = board_[from];
    if (m.is_capture()) {
      Square capsq = m.is_en_passant() ? to - forward(us) : to;
      Piece cap = board_[capsq];
      u.captured = cap;
      remove(capsq);
      k ^= zobrist::piece_square[cap][capsq];
      halfmove_ = 0;
    }
    remove(from);
    Piece placed = m.is_promotion() ? make_piece(us, m.promotion_type()) : p;
    put(placed, to);
    k ^= zobrist::piece_square[p][from] ^ zobrist::piece_square[placed][to];
    if (type_of(p) == Pawn) {
      halfmove_ = 0;
      if (m.flag() == DoublePush) new_ep = from + forward(us);
    }
  }

  int rights = castling_ & CastlingMask[from] & CastlingMask[to];
  if (rights != castling_) {
    k ^= zobrist::castling[castling_] ^ zobrist::castling[rights];
    castling_ = rights;
  }

  side_ = them;
  k ^= zobrist::side;
  if (us == Black) ++fullmove_;
  checkers_ = attackers_to(king_square(them), pieces()) & pieces(us);

  if (new_ep != NoSquare && ep_capture_legal(new_ep)) {
    ep_ = new_ep;
    k ^= zobrist::ep_file[file_of(new_ep)];
  }
  key_ = k;
}

void Position::unmake(Move m) {
  const Undo u = history_.back();
  history_.pop_back();
  side_ = ~side_;
  const Color us = side_;
  const Square from = m.from(), to = m.to();

  if (m.is_castle()) {
    Square kto = castle_king_to(from, to), rto = castle_rook_to(from, to);
    Piece king = board_[kto], rook = board_[rto];
    remove(kto);
    remove(rto);
    put(king, from);
    put(rook, to);
  } else {
    Piece placed = board_[to];
    remove(to);
    put(m.is_promotion() ? make_piece(us, Pawn) : placed, from);
    if (m.is_capture()) put(u.captured, m.is_en_passant() ? to - forward(us) : to);
  }

  if (us == Black) --fullmove_;
  key_ = u.key;
  checkers_ = u.checkers;
  castling_ = u.castling;
  ep_ = u.ep;
  halfmove_ = u.halfmove;
}

void Position::make_null() {
  assert(!checkers_);
  history_.push_back({key_, checkers_, NoPiece, castling_, ep_, halfmove_});
  if (ep_ != NoSquare) {
    key_ ^= zobrist::ep_file[file_of(ep_)];
    ep_ = NoSquare;
  }
  ++halfmove_;
  if (side_ == Black) ++fullmove_;
  side_ = ~side_;
  key_ ^= zobrist::side;
  checkers_ = 0;  // the side that passed was not in check, so the other side is not either
}

void Position::unmake_null() {
  const Undo u = history_.back();
  history_.pop_back();
  side_ = ~side_;
  if (side_ == Black) --fullmove_;
  key_ = u.key;
  checkers_ = u.checkers;
  ep_ = u.ep;
  halfmove_ = u.halfmove;
}

bool Position::is_pseudo_legal(Move m) const {
  if (m.is_none()) return false;
  const Color us = side_;
  const Square from = m.from(), to = m.to();
  const int flag = m.flag();
  const Piece p = board_[from];
  if (p == NoPiece || color_of(p) != us) return false;
  if (flag == 3 || flag == 6 || flag == 7) return false;
  const PieceType pt = type_of(p);

  if (flag == Castle) {
    if (pt != King || checkers_) return false;
    for (const CastleInfo& c : Castles)
      if (c.king == from && c.rook == to && (castling_ & c.right))
        return board_[to] == make_piece(us, Rook) && !(between(from, to) & pieces());
    return false;
  }

  if (flag == EnPassant)
    return pt == Pawn && to == ep_ && (pawn_attacks(us, from) & bb(to));

  const Piece target = board_[to];
  if (m.is_capture()) {
    if (target == NoPiece || color_of(target) == us || type_of(target) == King) return false;
  } else if (target != NoPiece) {
    return false;
  }

  if (pt == Pawn) {
    if (m.is_promotion() != (relative_rank(us, to) == 7)) return false;
    if (m.is_capture()) return pawn_attacks(us, from) & bb(to);
    if (flag == DoublePush)
      return relative_rank(us, from) == 1 && to == from + 2 * forward(us) &&
             board_[from + forward(us)] == NoPiece;
    return to == from + forward(us);
  }

  if (flag != Quiet && flag != Capture) return false;
  return attacks(pt, from, pieces()) & bb(to);
}

bool Position::is_legal(Move m) const {
  const Color us = side_, them = ~us;
  const Square from = m.from(), to = m.to();
  const Square ksq = king_square(us);

  if (m.is_castle()) {
    Square kto = castle_king_to(from, to);
    for (Bitboard path = between(from, kto) | bb(kto); path;)
      if (attacked_by(them, pop_lsb(path), pieces())) return false;
    return true;
  }
  if (from == ksq) return !attacked_by(them, to, pieces() ^ bb(from));
  if (more_than_one(checkers_)) return false;

  if (m.is_en_passant()) {
    Square capsq = to - forward(us);
    Bitboard occ = (pieces() ^ bb(from) ^ bb(capsq)) | bb(to);
    return !(attackers_to(ksq, occ) & pieces(them) & ~bb(capsq));
  }
  if (checkers_ && !((between(ksq, lsb(checkers_)) | checkers_) & bb(to))) return false;
  if ((pinned(us) & bb(from)) && !(line(ksq, from) & bb(to))) return false;
  return true;
}

std::string Position::move_to_uci(Move m) const {
  if (m.is_none()) return "0000";
  Square to = m.is_castle() ? castle_king_to(m.from(), m.to()) : m.to();
  std::string s = square_name(m.from()) + square_name(to);
  if (m.is_promotion()) s += "nbrq"[m.promotion_type() - Knight];
  return s;
}

Move Position::parse_uci(std::string_view uci) const {
  MoveList list;
  generate<GenType::Legal>(*this, list);
  for (Move m : list)
    if (move_to_uci(m) == uci) return m;
  return NoMove;
}

Position Position::mirrored() const {
  Position r = *this;
  r.clear();
  for (Square s = 0; s < 64; ++s)
    if (board_[s] != NoPiece) r.put(board_[s] ^ 8, s ^ 56);
  r.side_ = ~side_;
  r.castling_ = ((castling_ & 3) << 2) | ((castling_ >> 2) & 3);
  r.ep_ = ep_ == NoSquare ? NoSquare : ep_ ^ 56;
  r.halfmove_ = halfmove_;
  r.fullmove_ = fullmove_;
  r.finish_setup();
  return r;
}

bool Position::same_state(const Position& o) const {
  return std::equal(std::begin(board_), std::end(board_), std::begin(o.board_)) &&
         std::equal(std::begin(by_type_), std::end(by_type_), std::begin(o.by_type_)) &&
         std::equal(std::begin(by_color_), std::end(by_color_), std::begin(o.by_color_)) &&
         side_ == o.side_ && castling_ == o.castling_ && ep_ == o.ep_ &&
         halfmove_ == o.halfmove_ && fullmove_ == o.fullmove_ && key_ == o.key_ &&
         checkers_ == o.checkers_ && history_.size() == o.history_.size();
}

}  // namespace fork
