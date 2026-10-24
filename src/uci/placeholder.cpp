#include "uci/placeholder.hpp"

#include <algorithm>

#include "core/movegen.hpp"

namespace forkeng {

// The owner's rule (DESIGN.md §5.1): a move that mates in one, else the best
// capture by MVV-LVA (most valuable victim first, then least valuable
// attacker; piece values in PieceType order, pawn < knight < bishop < rook
// < queen, king last as attacker), else the first legal move. Ties go to the
// first move in generation order.
PlaceholderPick pick_placeholder_move(Position& pos, const std::vector<Move>& restrict_to) {
  MoveList all;
  generate<GenMode::Legal>(pos, all);
  MoveList candidates;
  for (Move m : all)
    if (restrict_to.empty() || std::find(restrict_to.begin(), restrict_to.end(), m) != restrict_to.end())
      candidates.add(m);
  if (candidates.size() == 0) candidates = all;  // restrict_to held no legal move
  std::uint64_t nodes = 1;
  if (candidates.size() == 0) return {NoMove, nodes};

  for (Move m : candidates) {
    pos.make(m);
    ++nodes;
    MoveList replies;
    generate<GenMode::Legal>(pos, replies);
    const bool mate = replies.size() == 0 && pos.in_check();
    pos.unmake(m);
    if (mate) return {m, nodes};
  }

  Move best = NoMove;
  int best_victim = -1, best_attacker = 0;
  for (Move m : candidates) {
    if (!m.is_capture()) continue;
    const int victim = m.is_en_passant() ? Pawn : kind_of(pos.piece_at(m.to()));
    const int attacker = kind_of(pos.piece_at(m.from()));
    if (victim > best_victim || (victim == best_victim && attacker < best_attacker)) {
      best = m;
      best_victim = victim;
      best_attacker = attacker;
    }
  }
  return {best.is_none() ? candidates[0] : best, nodes};
}

}  // namespace forkeng
