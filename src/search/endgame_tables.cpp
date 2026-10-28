#include "search/endgame_tables.hpp"

#include <algorithm>
#include <memory>

#include "core/bitboard.hpp"
#include "core/movegen.hpp"
#include "tbprobe.h"

namespace forkeng {

namespace {

// Fathom's root results (about 100 KB): allocated when tables are loaded, so
// no search ever allocates. Used only by rank_root_by_tables, once per search.
std::unique_ptr<TbRootMoves> root_results;

// The arguments every Fathom probe takes, from Fork's position.
struct ProbeArgs {
  std::uint64_t white, black, kings, queens, rooks, bishops, knights, pawns;
  unsigned rule50, castling, ep;
  bool white_to_move;
};

ProbeArgs probe_args(const Position& pos) {
  const Square ep = pos.ep_target();
  return {pos.pieces(White),
          pos.pieces(Black),
          pos.pieces(King),
          pos.pieces(Queen),
          pos.pieces(Rook),
          pos.pieces(Bishop),
          pos.pieces(Knight),
          pos.pieces(Pawn),
          static_cast<unsigned>(pos.halfmove_clock()),
          static_cast<unsigned>(pos.castling_rights()),
          ep == NoSquare ? 0u : static_cast<unsigned>(ep),  // Fathom: 0 means none (a1 is never one)
          pos.side_to_move() == White};
}

// Fathom's promotion codes (TB_PROMOTES_*) as Fork's piece types.
PieceType promotion_piece(unsigned code) {
  switch (code) {
    case TB_PROMOTES_QUEEN:
      return Queen;
    case TB_PROMOTES_ROOK:
      return Rook;
    case TB_PROMOTES_BISHOP:
      return Bishop;
    case TB_PROMOTES_KNIGHT:
      return Knight;
    default:
      return NoPieceType;
  }
}

// The legal move of `pos` that a Fathom move describes, or NoMove.
Move legal_move_for(const MoveList& legal, TbMove tm) {
  const Square from = static_cast<Square>(TB_MOVE_FROM(tm)), to = static_cast<Square>(TB_MOVE_TO(tm));
  const PieceType promo = promotion_piece(TB_MOVE_PROMOTES(tm));
  for (Move m : legal)
    if (m.from() == from && m.to() == to &&
        (m.is_promotion() ? m.promo_type() == promo : promo == NoPieceType))
      return m;
  return NoMove;
}

}  // namespace

std::string load_endgame_tables(const std::string& path) {
  // Empty directories (a separator at either end, or two in a row) are
  // dropped first: tb_init counts a trailing one as one more directory and
  // reads past its copy of the string looking for it (audit-1, R-1).
#ifdef _WIN32
  constexpr char Separator = ';';
#else
  constexpr char Separator = ':';
#endif
  std::string dirs;
  for (std::size_t from = 0; from <= path.size();) {
    const std::size_t to = std::min(path.find(Separator, from), path.size());
    if (to > from) {
      if (!dirs.empty()) dirs += Separator;
      dirs.append(path, from, to - from);
    }
    from = to + 1;
  }
  tb_init(dirs.c_str());  // re-initializes; an empty path unloads every table
  if (TB_LARGEST == 0) {
    root_results.reset();
    return path.empty() ? "Syzygy: no tables" : "Syzygy: no tables found in " + path;
  }
  if (!root_results) root_results = std::make_unique<TbRootMoves>();
  return "Syzygy: tables up to " + std::to_string(TB_LARGEST) + " pieces";
}

int endgame_table_pieces() { return static_cast<int>(TB_LARGEST); }

std::optional<TableWdl> probe_table_wdl(const Position& pos) {
  if (popcount(pos.pieces()) > endgame_table_pieces() || pos.castling_rights() != 0 ||
      pos.halfmove_clock() != 0)
    return std::nullopt;
  const ProbeArgs a = probe_args(pos);
  const unsigned r = tb_probe_wdl(a.white, a.black, a.kings, a.queens, a.rooks, a.bishops, a.knights, a.pawns,
                                  a.rule50, a.castling, a.ep, a.white_to_move);
  switch (r) {
    case TB_LOSS:
      return TableWdl::Loss;
    case TB_BLESSED_LOSS:
      return TableWdl::BlessedLoss;
    case TB_DRAW:
      return TableWdl::Draw;
    case TB_CURSED_WIN:
      return TableWdl::CursedWin;
    case TB_WIN:
      return TableWdl::Win;
    default:
      return std::nullopt;  // TB_RESULT_FAILED: no table for it
  }
}

bool rank_root_by_tables(const Position& pos, bool repeated, MoveList& keep) {
  keep.count = 0;
  if (!root_results || popcount(pos.pieces()) > endgame_table_pieces() || pos.castling_rights() != 0)
    return false;
  const ProbeArgs a = probe_args(pos);
  TbRootMoves& r = *root_results;
  const bool by_dtz = tb_probe_root_dtz(a.white, a.black, a.kings, a.queens, a.rooks, a.bishops, a.knights,
                                        a.pawns, a.rule50, a.castling, a.ep, a.white_to_move, repeated,
                                        /*useRule50=*/true, &r) != 0;
  if (!by_dtz &&
      tb_probe_root_wdl(a.white, a.black, a.kings, a.queens, a.rooks, a.bishops, a.knights, a.pawns, a.rule50,
                        a.castling, a.ep, a.white_to_move, /*useRule50=*/true, &r) == 0)
    return false;
  if (r.size == 0) return false;
  // Keep the moves of the best rank, best first (ties in Fathom's order).
  std::int32_t best = r.moves[0].tbRank;
  for (unsigned i = 1; i < r.size; ++i) best = std::max(best, r.moves[i].tbRank);
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  for (unsigned i = 0; i < r.size; ++i) {
    if (r.moves[i].tbRank != best) continue;
    const Move m = legal_move_for(legal, r.moves[i].move);
    if (m.is_none()) {  // a move Fork does not recognize: trust neither side
      keep.count = 0;
      return false;
    }
    keep.add(m);
  }
  return keep.size() > 0;
}

}  // namespace forkeng
