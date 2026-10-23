#include "core/position.hpp"

#include <algorithm>
#include <array>
#include <charconv>

#include "core/movegen.hpp"
#include "core/zobrist.hpp"

namespace fork {

namespace {

constexpr std::string_view PieceChars = "PNBRQK??pnbrqk";
constexpr Bitboard DarkSquares = 0xAA55AA55AA55AA55ULL;  // a1 is dark
constexpr std::size_t StateReserve = 1024;

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
  return {static_cast<char>('a' + file_of(s)), static_cast<char>('1' + rank_of(s))};
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
  std::ranges::fill(board_, NoPiece);
  std::ranges::fill(by_type_, 0);
  std::ranges::fill(by_color_, 0);
  side_ = White;
  fullmove_ = 1;
  states_.clear();
  states_.reserve(StateReserve);
  State s{};
  s.ep = NoSquare;
  s.captured = NoPiece;
  states_.push_back(s);
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

void Position::toggle_keys(State& s, Piece p, Square sq) const {
  Key z = zobrist::piece_square[p][sq];
  s.key ^= z;
  if (type_of(p) == Pawn) s.pawn_key ^= z;
  else s.non_pawn_key[color_of(p)] ^= z;
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

void Position::update_check_info(State& s) const {
  const Bitboard occ = pieces();
  for (Color c : {White, Black}) {
    Square ksq = king_square(c);
    Bitboard snipers = (rook_attacks(ksq, 0) & pieces(~c, Rook, Queen)) |
                       (bishop_attacks(ksq, 0) & pieces(~c, Bishop, Queen));
    // A blocker is a piece whose removal alone would expose the king.
    s.blockers[c] = s.pinners[c] = 0;
    while (snipers) {
      Square sniper = pop_lsb(snipers);
      Bitboard b = between(ksq, sniper) & occ;
      if (b && !more_than_one(b)) {
        s.blockers[c] |= b;
        if (b & pieces(c)) s.pinners[c] |= bb(sniper);
      }
    }
  }

  s.checkers = attackers_to(king_square(side_), occ) & pieces(~side_);

  const Square eksq = king_square(~side_);
  s.check_squares[Pawn] = pawn_attacks(~side_, eksq);
  s.check_squares[Knight] = knight_attacks(eksq);
  s.check_squares[Bishop] = bishop_attacks(eksq, occ);
  s.check_squares[Rook] = rook_attacks(eksq, occ);
  s.check_squares[Queen] = s.check_squares[Bishop] | s.check_squares[Rook];
  s.check_squares[King] = 0;
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

State Position::compute_state() const {
  State s = state();
  s.key = s.pawn_key = s.material_key = 0;
  s.non_pawn_key[White] = s.non_pawn_key[Black] = 0;
  for (Square sq = 0; sq < 64; ++sq)
    if (board_[sq] != NoPiece) toggle_keys(s, board_[sq], sq);
  for (Piece p = 0; p < 16; ++p) {
    if (p == NoPiece || type_of(p) >= NoPieceType) continue;
    for (int n = 0; n < count(color_of(p), type_of(p)); ++n) s.material_key ^= zobrist::material[p][n];
  }
  if (side_ == Black) s.key ^= zobrist::side;
  s.key ^= zobrist::castling[s.castling];
  if (s.ep != NoSquare) s.key ^= zobrist::ep_file[file_of(s.ep)];
  update_check_info(s);
  return s;
}

void Position::finish_setup() { st() = compute_state(); }

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
  State& s = p.st();

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
      p.put(static_cast<Piece>(idx), make_square(file, rank));
      ++file;
    }
  }
  if (rank != 0 || file != 8) return fail("placement does not describe 8 ranks of 8 squares");

  for (Color c : {White, Black}) {
    if (p.count(c, King) != 1) return fail("each side needs exactly one king");
    if (p.count(c, Pawn) > 8) return fail("more than 8 pawns for one side");
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
      if (s.castling & info->right) return fail("repeated castling right");
      Color col = c == 'K' || c == 'Q' ? White : Black;
      if (p.board_[info->king] != make_piece(col, King) || p.board_[info->rook] != make_piece(col, Rook))
        return fail(std::string("castling right '") + c + "' without king and rook on their home squares");
      s.castling |= info->right;
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
    auto parse = [](std::string_view str, int& out) {
      auto [ptr, ec] = std::from_chars(str.data(), str.data() + str.size(), out);
      return ec == std::errc() && ptr == str.data() + str.size() && out >= 0;
    };
    if (!parse(fields[4], s.halfmove)) return fail("bad halfmove clock");
    if (!parse(fields[5], p.fullmove_)) return fail("bad fullmove number");
    p.fullmove_ = std::max(p.fullmove_, 1);
  }

  if (p.attackers_to(p.king_square(~p.side_), p.pieces()) & p.pieces(p.side_))
    return fail("the side not to move is in check");

  if (ep != NoSquare && p.ep_capture_legal(ep)) s.ep = ep;
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
      if (empty) s += static_cast<char>('0' + empty);
      empty = 0;
      s += PieceChars[p];
    }
    if (empty) s += static_cast<char>('0' + empty);
    if (r) s += '/';
  }
  s += side_ == White ? " w " : " b ";
  if (!castling_rights()) s += '-';
  for (const CastleInfo& c : Castles)
    if (castling_rights() & c.right) s += c.fen;
  s += ' ';
  s += ep_square() == NoSquare ? "-" : square_name(ep_square());
  s += ' ' + std::to_string(halfmove_clock()) + ' ' + std::to_string(fullmove_);
  return s;
}

void Position::make(Move m) {
  // Grow explicitly so push_back never copies from a reallocated element.
  if (states_.size() == states_.capacity()) states_.reserve(states_.capacity() * 2);
  states_.push_back(states_.back());
  State& s = st();
  const Color us = side_, them = ~us;
  const Square from = m.from(), to = m.to();

  s.captured = NoPiece;
  ++s.halfmove;
  if (s.ep != NoSquare) {
    s.key ^= zobrist::ep_file[file_of(s.ep)];
    s.ep = NoSquare;
  }
  Square new_ep = NoSquare;

  if (m.is_castle()) {
    Square kto = castle_king_to(from, to), rto = castle_rook_to(from, to);
    Piece king = board_[from], rook = board_[to];
    remove(from);
    remove(to);
    put(king, kto);
    put(rook, rto);
    toggle_keys(s, king, from);
    toggle_keys(s, king, kto);
    toggle_keys(s, rook, to);
    toggle_keys(s, rook, rto);
  } else {
    Piece p = board_[from];
    if (m.is_capture()) {
      Square capsq = m.is_en_passant() ? to - forward(us) : to;
      Piece cap = board_[capsq];
      s.captured = cap;
      remove(capsq);
      toggle_keys(s, cap, capsq);
      s.material_key ^= zobrist::material[cap][count(them, type_of(cap))];
      s.halfmove = 0;
    }
    remove(from);
    toggle_keys(s, p, from);
    Piece placed = p;
    if (m.is_promotion()) {
      placed = make_piece(us, m.promotion_type());
      s.material_key ^= zobrist::material[p][count(us, Pawn)];
      s.material_key ^= zobrist::material[placed][count(us, m.promotion_type())];
    }
    put(placed, to);
    toggle_keys(s, placed, to);
    if (type_of(p) == Pawn) {
      s.halfmove = 0;
      if (m.flag() == DoublePush) new_ep = from + forward(us);
    }
  }

  int rights = s.castling & CastlingMask[from] & CastlingMask[to];
  if (rights != s.castling) {
    s.key ^= zobrist::castling[s.castling] ^ zobrist::castling[rights];
    s.castling = rights;
  }

  side_ = them;
  s.key ^= zobrist::side;
  if (us == Black) ++fullmove_;
  update_check_info(s);

  if (new_ep != NoSquare && ep_capture_legal(new_ep)) {
    s.ep = new_ep;
    s.key ^= zobrist::ep_file[file_of(new_ep)];
  }
}

void Position::unmake(Move m) {
  const Piece captured = st().captured;
  states_.pop_back();
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
    if (m.is_capture()) put(captured, m.is_en_passant() ? to - forward(us) : to);
  }
  if (us == Black) --fullmove_;
}

void Position::make_null() {
  assert(!in_check());
  if (states_.size() == states_.capacity()) states_.reserve(states_.capacity() * 2);
  states_.push_back(states_.back());
  State& s = st();
  s.captured = NoPiece;
  ++s.halfmove;
  if (s.ep != NoSquare) {
    s.key ^= zobrist::ep_file[file_of(s.ep)];
    s.ep = NoSquare;
  }
  if (side_ == Black) ++fullmove_;
  side_ = ~side_;
  s.key ^= zobrist::side;
  update_check_info(s);
}

void Position::unmake_null() {
  states_.pop_back();
  side_ = ~side_;
  if (side_ == Black) --fullmove_;
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
    if (pt != King || in_check()) return false;
    for (const CastleInfo& c : Castles)
      if (c.king == from && c.rook == to && (castling_rights() & c.right))
        return board_[to] == make_piece(us, Rook) && !(between(from, to) & pieces());
    return false;
  }

  if (flag == EnPassant)
    return pt == Pawn && to == ep_square() && (pawn_attacks(us, from) & bb(to));

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
  if (more_than_one(checkers())) return false;

  if (m.is_en_passant()) {
    Square capsq = to - forward(us);
    Bitboard occ = (pieces() ^ bb(from) ^ bb(capsq)) | bb(to);
    return !(attackers_to(ksq, occ) & pieces(them) & ~bb(capsq));
  }
  if (checkers() && !((between(ksq, lsb(checkers())) | checkers()) & bb(to))) return false;
  if ((pinned(us) & bb(from)) && !(line(ksq, from) & bb(to))) return false;
  return true;
}

bool Position::gives_check(Move m) const {
  const Color us = side_, them = ~us;
  const Square from = m.from(), to = m.to();
  const Square eksq = king_square(them);

  if (m.is_castle()) {
    // The rook (or, in principle, a slider uncovered by the king) may check.
    Square kto = castle_king_to(from, to), rto = castle_rook_to(from, to);
    Bitboard occ = (pieces() ^ bb(from) ^ bb(to)) | bb(kto) | bb(rto);
    Bitboard rooks = (pieces(us, Rook, Queen) ^ bb(to)) | bb(rto);
    return (rook_attacks(eksq, occ) & rooks) || (bishop_attacks(eksq, occ) & pieces(us, Bishop, Queen));
  }

  // Discovered check: the moving piece was the only blocker of one of our sliders.
  if ((blockers(them) & bb(from)) && !(line(eksq, from) & bb(to))) return true;

  if (m.is_promotion())
    return attacks(m.promotion_type(), to, pieces() ^ bb(from)) & bb(eksq);

  if (check_squares(type_of(board_[from])) & bb(to)) return true;

  if (m.is_en_passant()) {
    // Removing the captured pawn can uncover a slider.
    Square capsq = to - forward(us);
    Bitboard occ = (pieces() ^ bb(from) ^ bb(capsq)) | bb(to);
    return (rook_attacks(eksq, occ) & pieces(us, Rook, Queen)) ||
           (bishop_attacks(eksq, occ) & pieces(us, Bishop, Queen));
  }
  return false;
}

Key Position::key_after(Move m) const {
  const Color us = side_, them = ~us;
  const Square from = m.from(), to = m.to();
  const State& s = state();
  Key k = s.key ^ zobrist::side;
  if (s.ep != NoSquare) k ^= zobrist::ep_file[file_of(s.ep)];

  if (m.is_castle()) {
    Square kto = castle_king_to(from, to), rto = castle_rook_to(from, to);
    Piece king = board_[from], rook = board_[to];
    k ^= zobrist::piece_square[king][from] ^ zobrist::piece_square[king][kto] ^
         zobrist::piece_square[rook][to] ^ zobrist::piece_square[rook][rto];
  } else {
    Piece p = board_[from];
    if (m.is_capture()) {
      Square capsq = m.is_en_passant() ? to - forward(us) : to;
      k ^= zobrist::piece_square[board_[capsq]][capsq];
    }
    Piece placed = m.is_promotion() ? make_piece(us, m.promotion_type()) : p;
    k ^= zobrist::piece_square[p][from] ^ zobrist::piece_square[placed][to];

    if (m.flag() == DoublePush) {
      // The ep square counts only if the opponent could legally capture.
      Square ep = from + forward(us);
      Square tksq = king_square(them);
      Bitboard occ_after_push = (pieces() ^ bb(from)) | bb(to);
      Bitboard our_pawns = pieces(us, Pawn) ^ bb(from);  // the pushed pawn is the one captured
      for (Bitboard c = pawn_attacks(us, ep) & pieces(them, Pawn); c;) {
        Square cap_from = pop_lsb(c);
        Bitboard occ = (occ_after_push ^ bb(cap_from) ^ bb(to)) | bb(ep);
        bool exposed = (pawn_attacks(them, tksq) & our_pawns) ||
                       (knight_attacks(tksq) & pieces(us, Knight)) ||
                       (king_attacks(tksq) & pieces(us, King)) ||
                       (bishop_attacks(tksq, occ) & pieces(us, Bishop, Queen)) ||
                       (rook_attacks(tksq, occ) & pieces(us, Rook, Queen));
        if (!exposed) {
          k ^= zobrist::ep_file[file_of(ep)];
          break;
        }
      }
    }
  }

  int rights = s.castling & CastlingMask[from] & CastlingMask[to];
  return k ^ zobrist::castling[s.castling] ^ zobrist::castling[rights];
}

int Position::repetition_count() const {
  // Only positions since the last irreversible move can repeat; a position
  // repeats only with the same side to move, so step back two plies at a time.
  const int n = static_cast<int>(states_.size());
  const int window = std::min(state().halfmove, n - 1);
  const Key k = key();
  int count = 1;
  for (int back = 2; back <= window; back += 2)
    if (states_[n - 1 - back].key == k) ++count;
  return count;
}

bool Position::has_insufficient_material(Color c) const {
  // Material-only test (piece placement ignored): c can never deliver mate.
  if (pieces(c) & (pieces(Pawn) | pieces(Rook) | pieces(Queen))) return false;
  if (pieces(c, Knight)) {
    // A lone knight, and the opponent has nothing but king and queens (any
    // other enemy piece could block its own king into a mate).
    return popcount(pieces(c)) <= 2 && !(pieces(~c) & ~pieces(King) & ~pieces(Queen));
  }
  if (pieces(c, Bishop)) {
    // Bishops only, all bishops on the board on one square color, and no
    // pawns or knights anywhere.
    Bitboard bishops = pieces(Bishop);
    bool one_color = !(bishops & DarkSquares) || !(bishops & ~DarkSquares);
    return one_color && !pieces(Pawn) && !pieces(Knight);
  }
  return true;  // bare king
}

bool Position::insufficient_material() const {
  return has_insufficient_material(White) && has_insufficient_material(Black);
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
  int c = castling_rights();
  r.st().castling = ((c & 3) << 2) | ((c >> 2) & 3);
  r.st().ep = ep_square() == NoSquare ? NoSquare : ep_square() ^ 56;
  r.st().halfmove = halfmove_clock();
  r.fullmove_ = fullmove_;
  r.finish_setup();
  return r;
}

bool Position::same_state(const Position& o) const {
  return std::equal(std::begin(board_), std::end(board_), std::begin(o.board_)) &&
         std::equal(std::begin(by_type_), std::end(by_type_), std::begin(o.by_type_)) &&
         std::equal(std::begin(by_color_), std::end(by_color_), std::begin(o.by_color_)) &&
         side_ == o.side_ && fullmove_ == o.fullmove_ && states_.size() == o.states_.size() &&
         state() == o.state();
}

}  // namespace fork
