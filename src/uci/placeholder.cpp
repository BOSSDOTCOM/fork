#include "uci/placeholder.hpp"

#include <algorithm>

#include "core/movegen.hpp"

namespace forkeng {

PlaceholderPick pick_placeholder_move(Position& pos, const std::vector<Move>& restrict_to) {
  MoveList all;
  generate<GenMode::Legal>(pos, all);
  for (Move m : all)
    if (restrict_to.empty() || std::find(restrict_to.begin(), restrict_to.end(), m) != restrict_to.end())
      return {m, 1};
  return {all.size() ? all[0] : NoMove, 1};
}

}  // namespace forkeng
