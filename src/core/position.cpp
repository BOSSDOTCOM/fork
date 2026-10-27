// position: implementation (see position.hpp for the invariants).
#include "core/position.hpp"

#include <algorithm>
#include <array>
#include <charconv>

#include "core/movegen.hpp"
#include "core/zobrist.hpp"

namespace forkeng {

namespace {

constexpr std::string_view PieceChars = "PNBRQK??pnbrqk";
constexpr Bitboard DarkSquares = 0xAA55AA55AA55AA55ULL;              // a1 is dark
constexpr int MaxHalfmoveClock = 10000, MaxFullmoveNumber = 100000;  // accepted in a FEN

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
  s.game_span = 1;
  s.captured = NoPiece;
  states_.push_back(s);
}

void Position::put(Piece p, Square s) {
  board_[s] = p;
  by_type_[kind_of(p)] |= bb(s);
  by_color_[side_of(p)] |= bb(s);
}

void Position::remove(Square s) {
  Piece p = board_[s];
  by_type_[kind_of(p)] &= ~bb(s);
  by_color_[side_of(p)] &= ~bb(s);
  board_[s] = NoPiece;
}

void Position::toggle_keys(State& s, Piece p, Square sq) const { s.key ^= zobrist::piece_square[p][sq]; }

Bitboard Position::attackers_to(Square s, Bitboard occ) const {
  return (pawn_attacks(Black, s) & pieces(White, Pawn)) | (pawn_attacks(White, s) & pieces(Black, Pawn)) |
         (knight_attacks(s) & pieces(Knight)) | (king_attacks(s) & pieces(King)) |
         (bishop_attacks(s, occ) & (pieces(Bishop) | pieces(Queen))) |
         (rook_attacks(s, occ) & (pieces(Rook) | pieces(Queen)));
}

bool Position::attacked_by(Color by, Square s, Bitboard occ) const {
  return (pawn_attacks(~by, s) & pieces(by, Pawn)) || (knight_attacks(s) & pieces(by, Knight)) ||
         (king_attacks(s) & pieces(by, King)) || (bishop_attacks(s, occ) & pieces(by, Bishop, Queen)) ||
         (rook_attacks(s, occ) & pieces(by, Rook, Queen));
}

// The pieces in `shields` that are the only piece between `king` and a slider
// of `rook_sliders` (on a rank or file) or `bishop_sliders` (on a diagonal),
// so that lifting one opens that slider's line to the king. Found with x-ray
// attacks (CPW "X-ray Attacks (Bitboards)", "Checks and Pinned Pieces
// (Bitboards)"): look out from the king, lift the shields seen first, look
// again, and every slider that comes into view marks a line whose shield is
// the one piece between it and the king.
Bitboard Position::lone_shields(Square king, Bitboard shields, Bitboard rook_sliders,
                                Bitboard bishop_sliders) const {
  const Bitboard occ = pieces();
  const Bitboard straight = rook_attacks(king, occ), diagonal = bishop_attacks(king, occ);
  Bitboard revealed = rook_attacks(king, occ & ~(straight & shields)) & ~straight & rook_sliders;
  revealed |= bishop_attacks(king, occ & ~(diagonal & shields)) & ~diagonal & bishop_sliders;
  Bitboard found = 0;
  while (revealed) found |= between(king, pop_lsb(revealed)) & shields;
  return found;
}

// Check information for the side to move, from the board alone. Pins and
// discovered-check candidates are one computation seen from each king (CPW
// "Discovered Check"): our pieces shielding our king from enemy sliders are
// pinned; our pieces shielding the enemy king from our sliders can discover
// check by moving off the line.
void Position::refresh_check_info(State& s) const {
  const Color us = side_, them = ~us;
  const Square own_king = king_square(us), their_king = king_square(them);
  s.checkers = attackers_to(own_king, pieces()) & pieces(them);
  s.pinned = lone_shields(own_king, pieces(us), pieces(them, Rook, Queen), pieces(them, Bishop, Queen));
  s.discoverers = lone_shields(their_king, pieces(us), pieces(us, Rook, Queen), pieces(us, Bishop, Queen));
}

// Occupancy once the side to move has captured en passant from `from` to
// `to`: the capturing pawn has moved and the pawn it took, which stood beside
// it, is gone.
Bitboard Position::occupancy_after_ep(Square from, Square to) const {
  const Square taken = to - forward(side_);
  return (pieces() & ~bb(from) & ~bb(taken)) | bb(to);
}

bool Position::ep_capture_legal(Square ep) const {
  Color us = side_;
  Square cap_sq = ep - forward(us);
  Square own_king = king_square(us);
  Bitboard candidates = pawn_attacks(~us, ep) & pieces(us, Pawn);
  while (candidates) {
    Square from = pop_lsb(candidates);
    Bitboard occ = occupancy_after_ep(from, ep);
    if (!(attackers_to(own_king, occ) & pieces(~us) & ~bb(cap_sq))) return true;
  }
  return false;
}

State Position::compute_state() const {
  State s = state();
  s.key = 0;
  for (Square sq = 0; sq < 64; ++sq)
    if (board_[sq] != NoPiece) toggle_keys(s, board_[sq], sq);
  if (side_ == Black) s.key ^= zobrist::side;
  s.key ^= zobrist::castling[s.castling];
  if (s.ep != NoSquare) s.key ^= zobrist::ep_file[file_of(s.ep)];
  refresh_check_info(s);
  return s;
}

void Position::finish_setup() { ply_state() = compute_state(); }

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
  State& s = p.ply_state();

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
      if (idx == std::string_view::npos || c == '?')
        return fail(std::string("bad piece character '") + c + "'");
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
    // Pieces beyond the starting set can only come from promotions, one per
    // missing pawn. Every position reachable from here keeps this property,
    // which bounds its move count (MoveList, types.hpp).
    int promoted = std::max(0, p.count(c, Queen) - 1) + std::max(0, p.count(c, Rook) - 2) +
                   std::max(0, p.count(c, Bishop) - 2) + std::max(0, p.count(c, Knight) - 2);
    if (promoted > 8 - p.count(c, Pawn)) return fail("more promoted pieces than missing pawns");
  }
  if (p.pieces(Pawn) & (Rank1 | Rank8)) return fail("pawn on the first or last rank");

  if (fields[1] == "w")
    p.side_ = White;
  else if (fields[1] == "b")
    p.side_ = Black;
  else
    return fail("side to move must be 'w' or 'b'");

  if (fields[2] != "-") {
    for (char c : fields[2]) {
      const CastleInfo* info = nullptr;
      for (const CastleInfo& ci : Castles)
        if (ci.fen == c) info = &ci;
      if (!info) return fail(std::string("bad castling character '") + c + "'");
      if (s.castling & info->right) return fail("repeated castling right");
      Color col = c == 'K' || c == 'Q' ? White : Black;
      if (p.board_[info->king] != piece_of(col, King) || p.board_[info->rook] != piece_of(col, Rook))
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
    if (rank_from(us, ep) != 5 || p.board_[ep] != NoPiece || p.board_[ep + forward(us)] != NoPiece ||
        p.board_[ep - forward(us)] != piece_of(~us, Pawn))
      return fail("en passant square is not consistent with a double pawn push");
  }

  if (fields.size() == 6) {
    // Capped far below INT_MAX so that make() can never overflow them (review
    // L1); real games stay in the hundreds.
    auto parse = [](std::string_view str, int& out, int cap) {
      auto [ptr, ec] = std::from_chars(str.data(), str.data() + str.size(), out);
      return ec == std::errc() && ptr == str.data() + str.size() && out >= 0 && out <= cap;
    };
    if (!parse(fields[4], s.halfmove, MaxHalfmoveClock)) return fail("bad halfmove clock");
    if (!parse(fields[5], p.fullmove_, MaxFullmoveNumber)) return fail("bad fullmove number");
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
  s += ep_target() == NoSquare ? "-" : square_name(ep_target());
  s += ' ' + std::to_string(halfmove_clock()) + ' ' + std::to_string(fullmove_);
  return s;
}

void Position::make(Move m) {
  // Grow explicitly so push_back never copies from a reallocated element.
  if (states_.size() == states_.capacity()) states_.reserve(states_.capacity() * 2);
  states_.push_back(states_.back());
  State& s = ply_state();
  const Color us = side_, them = ~us;
  const Square from = m.from(), to = m.to();

  s.captured = NoPiece;
  ++s.halfmove;
  ++s.game_span;
  if (s.ep != NoSquare) {
    s.key ^= zobrist::ep_file[file_of(s.ep)];
    s.ep = NoSquare;
  }
  Square new_ep = NoSquare;

  if (m.is_castle()) {
    const auto [king_to, rook_to] = castle_landing(from, to);
    Piece king = board_[from], rook = board_[to];
    remove(from);
    remove(to);
    put(king, king_to);
    put(rook, rook_to);
    toggle_keys(s, king, from);
    toggle_keys(s, king, king_to);
    toggle_keys(s, rook, to);
    toggle_keys(s, rook, rook_to);
  } else {
    Piece p = board_[from];
    if (m.is_capture()) {
      Square cap_sq = capture_square(m);
      Piece cap = board_[cap_sq];
      s.captured = cap;
      remove(cap_sq);
      toggle_keys(s, cap, cap_sq);
      s.halfmove = 0;
    }
    remove(from);
    toggle_keys(s, p, from);
    Piece placed = p;
    if (m.is_promotion()) {
      placed = piece_of(us, m.promo_type());
    }
    put(placed, to);
    toggle_keys(s, placed, to);
    if (kind_of(p) == Pawn) {
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
  refresh_check_info(s);

  if (new_ep != NoSquare && ep_capture_legal(new_ep)) {
    s.ep = new_ep;
    s.key ^= zobrist::ep_file[file_of(new_ep)];
  }
}

void Position::unmake(Move m) {
  const Piece captured = ply_state().captured;
  states_.pop_back();
  side_ = ~side_;
  const Color us = side_;
  const Square from = m.from(), to = m.to();

  if (m.is_castle()) {
    const auto [king_to, rook_to] = castle_landing(from, to);
    Piece king = board_[king_to], rook = board_[rook_to];
    remove(king_to);
    remove(rook_to);
    put(king, from);
    put(rook, to);
  } else {
    Piece placed = board_[to];
    remove(to);
    put(m.is_promotion() ? piece_of(us, Pawn) : placed, from);
    if (m.is_capture()) put(captured, capture_square(m));
  }
  if (us == Black) --fullmove_;
}

void Position::make_null() {
  assert(!in_check());
  if (states_.size() == states_.capacity()) states_.reserve(states_.capacity() * 2);
  states_.push_back(states_.back());
  State& s = ply_state();
  s.captured = NoPiece;
  ++s.halfmove;
  s.game_span = 0;
  if (s.ep != NoSquare) {
    s.key ^= zobrist::ep_file[file_of(s.ep)];
    s.ep = NoSquare;
  }
  if (side_ == Black) ++fullmove_;
  side_ = ~side_;
  s.key ^= zobrist::side;
  refresh_check_info(s);
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
  if (p == NoPiece || side_of(p) != us) return false;
  if (flag == 3 || flag == 6 || flag == 7) return false;
  const PieceType pt = kind_of(p);

  if (flag == Castle) {
    if (pt != King || in_check()) return false;
    for (const CastleInfo& c : Castles)
      if (c.king == from && c.rook == to && (castling_rights() & c.right))
        return board_[to] == piece_of(us, Rook) && !(between(from, to) & pieces());
    return false;
  }

  if (flag == EnPassant) return pt == Pawn && to == ep_target() && (pawn_attacks(us, from) & bb(to));

  const Piece target = board_[to];
  if (m.is_capture()) {
    if (target == NoPiece || side_of(target) == us || kind_of(target) == King) return false;
  } else if (target != NoPiece) {
    return false;
  }

  if (pt == Pawn) {
    if (m.is_promotion() != (rank_from(us, to) == 7)) return false;
    if (m.is_capture()) return pawn_attacks(us, from) & bb(to);
    if (flag == DoublePush)
      return rank_from(us, from) == 1 && to == from + 2 * forward(us) &&
             board_[from + forward(us)] == NoPiece;
    return to == from + forward(us);
  }

  if (flag != Quiet && flag != Capture) return false;
  return attacks(pt, from, pieces()) & bb(to);
}

bool Position::is_legal(Move m) const {
  const Color us = side_, them = ~us;
  const Square from = m.from(), to = m.to();
  const Square own_king = king_square(us);

  if (m.is_castle()) {
    Square king_to = castle_landing(from, to).king;
    for (Bitboard path = between(from, king_to) | bb(king_to); path;)
      if (attacked_by(them, pop_lsb(path), pieces())) return false;
    return true;
  }
  if (from == own_king) return !attacked_by(them, to, pieces() ^ bb(from));
  if (has_multiple(checkers())) return false;

  if (m.is_en_passant()) {
    Square cap_sq = to - forward(us);
    Bitboard occ = occupancy_after_ep(from, to);
    return !(attackers_to(own_king, occ) & pieces(them) & ~bb(cap_sq));
  }
  if (checkers() && !((between(own_king, lsb(checkers())) | checkers()) & bb(to))) return false;
  if ((pinned() & bb(from)) && !(line(own_king, from) & bb(to))) return false;
  return true;
}

bool Position::gives_check(Move m) const {
  const Color us = side_, them = ~us;
  const Square from = m.from(), to = m.to();
  const Square their_king = king_square(them);

  if (m.is_castle()) {
    // The rook (or, in principle, a slider uncovered by the king) may check.
    const auto [king_to, rook_to] = castle_landing(from, to);
    Bitboard occ = (pieces() ^ bb(from) ^ bb(to)) | bb(king_to) | bb(rook_to);
    Bitboard rooks = (pieces(us, Rook, Queen) ^ bb(to)) | bb(rook_to);
    return (rook_attacks(their_king, occ) & rooks) ||
           (bishop_attacks(their_king, occ) & pieces(us, Bishop, Queen));
  }

  // Discovered check: the moving piece was the only piece between one of our
  // sliders and the enemy king, and it leaves that line.
  if ((discoverers() & bb(from)) && !(line(their_king, from) & bb(to))) return true;

  if (m.is_promotion()) return attacks(m.promo_type(), to, pieces() ^ bb(from)) & bb(their_king);

  // Direct check by the moving piece from its new square, using the occupancy
  // before the move. That is safe: if the origin were the only piece between
  // the new square and the enemy king, the piece would already be giving
  // check from there.
  const PieceType moved = kind_of(board_[from]);
  if (moved == Pawn ? bool(pawn_attacks(us, to) & bb(their_king))
                    : moved != King && bool(attacks(moved, to, pieces()) & bb(their_king)))
    return true;

  if (m.is_en_passant()) {
    // Removing the captured pawn can uncover a slider.
    Bitboard occ = occupancy_after_ep(from, to);
    return (rook_attacks(their_king, occ) & pieces(us, Rook, Queen)) ||
           (bishop_attacks(their_king, occ) & pieces(us, Bishop, Queen));
  }
  return false;
}

Key Position::predicted_null_key() const {
  const State& s = state();
  return s.key ^ zobrist::side ^ (s.ep != NoSquare ? zobrist::ep_file[file_of(s.ep)] : Key{0});
}

Key Position::predicted_key(Move m) const {
  const Color us = side_, them = ~us;
  const Square from = m.from(), to = m.to();
  const State& s = state();
  Key k = s.key ^ zobrist::side;
  if (s.ep != NoSquare) k ^= zobrist::ep_file[file_of(s.ep)];

  if (m.is_castle()) {
    const auto [king_to, rook_to] = castle_landing(from, to);
    Piece king = board_[from], rook = board_[to];
    k ^= zobrist::piece_square[king][from] ^ zobrist::piece_square[king][king_to] ^
         zobrist::piece_square[rook][to] ^ zobrist::piece_square[rook][rook_to];
  } else {
    Piece p = board_[from];
    if (m.is_capture()) {
      Square cap_sq = capture_square(m);
      k ^= zobrist::piece_square[board_[cap_sq]][cap_sq];
    }
    Piece placed = m.is_promotion() ? piece_of(us, m.promo_type()) : p;
    k ^= zobrist::piece_square[p][from] ^ zobrist::piece_square[placed][to];

    if (m.flag() == DoublePush) {
      // The ep square counts only if the opponent could legally capture.
      Square ep = from + forward(us);
      Square their_king = king_square(them);
      Bitboard occ_after_push = (pieces() ^ bb(from)) | bb(to);
      Bitboard our_pawns = pieces(us, Pawn) ^ bb(from);  // the pushed pawn is the one captured
      for (Bitboard c = pawn_attacks(us, ep) & pieces(them, Pawn); c;) {
        Square cap_from = pop_lsb(c);
        Bitboard occ = (occ_after_push ^ bb(cap_from) ^ bb(to)) | bb(ep);
        bool exposed = (pawn_attacks(them, their_king) & our_pawns) ||
                       (knight_attacks(their_king) & pieces(us, Knight)) ||
                       (king_attacks(their_king) & pieces(us, King)) ||
                       (bishop_attacks(their_king, occ) & pieces(us, Bishop, Queen)) ||
                       (rook_attacks(their_king, occ) & pieces(us, Rook, Queen));
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
  // Only positions since the last irreversible move can repeat, and none from
  // before a null move: a position reached only because one side passed is
  // not part of the game (review M2). A position repeats only with the same
  // side to move, so step back two plies at a time.
  const int n = static_cast<int>(states_.size());
  const int window = std::min({state().halfmove, state().game_span - 1, n - 1});
  const Key k = key();
  int count = 1;
  for (int back = 2; back <= window; back += 2)
    if (states_[n - 1 - back].key == k) ++count;
  return count;
}

bool Position::cannot_mate(Color c) const {
  // Sort this side's army (king aside) into one of four kinds, then decide
  // from that kind and what else stands on the board.
  enum class Army { KingAlone, OneKnight, BishopsOnly, Mating };

  const Bitboard kings = by_type_[King];
  const Bitboard army = by_color_[c] & ~kings;
  const Bitboard knights = army & by_type_[Knight];
  const Bitboard bishops = army & by_type_[Bishop];

  Army kind = Army::Mating;
  if (army == 0)
    kind = Army::KingAlone;
  else if (army == knights && !has_multiple(knights))
    kind = Army::OneKnight;
  else if (army == bishops)
    kind = Army::BishopsOnly;

  switch (kind) {
    case Army::KingAlone:
      return true;
    case Army::OneKnight: {
      // A lone knight counts as unable to mate unless the defender owns a
      // pawn, knight, bishop or rook besides its king; a defender with only
      // queens (or nothing at all) does not change that (DESIGN.md 4.5).
      const Bitboard helpers = by_color_[~c] & ~kings & ~by_type_[Queen];
      return helpers == 0;
    }
    case Army::BishopsOnly: {
      // Bishops that all share one square colour, with no pawn or knight
      // anywhere that could block a flight square of the other colour.
      if (by_type_[Pawn] | by_type_[Knight]) return false;
      const Bitboard all_bishops = by_type_[Bishop];
      const bool on_dark = (all_bishops & DarkSquares) != 0;
      const bool on_light = (all_bishops & ~DarkSquares) != 0;
      return !(on_dark && on_light);
    }
    case Army::Mating:
      break;
  }
  return false;
}

bool Position::insufficient_material() const {
  // A draw by material only when neither side has material that could mate.
  return cannot_mate(White) && cannot_mate(Black);
}

std::string Position::move_to_uci(Move m) const {
  if (m.is_none()) return "0000";
  Square to = m.is_castle() ? castle_landing(m.from(), m.to()).king : m.to();
  std::string s = square_name(m.from()) + square_name(to);
  if (m.is_promotion()) s += "nbrq"[m.promo_type() - Knight];
  return s;
}

Move Position::parse_uci(std::string_view uci) const {
  MoveList list;
  generate<GenMode::Legal>(*this, list);
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
  r.ply_state().castling = ((c & 3) << 2) | ((c >> 2) & 3);
  r.ply_state().ep = ep_target() == NoSquare ? NoSquare : ep_target() ^ 56;
  r.ply_state().halfmove = halfmove_clock();
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

}  // namespace forkeng
