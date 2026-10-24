// placeholder: the Phase 2 stand-in for a search (deleted in Phase 3).
//
// Purpose: pick a legal move so the protocol can be tested end to end.
// Invariants:
// - Deterministic: the same position and restriction give the same move.
// - The move is legal, and is one of `restrict_to` when that holds any move.
// - NoMove only when the position has no legal move.
#pragma once

#include <cstdint>
#include <vector>

#include "core/position.hpp"

namespace forkeng {

struct PlaceholderPick {
  Move move;
  std::uint64_t nodes;  // positions visited, the root included
};

PlaceholderPick pick_placeholder_move(Position& pos, const std::vector<Move>& restrict_to);

}  // namespace forkeng
