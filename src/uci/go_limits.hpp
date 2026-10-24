// go_limits: the arguments of a UCI `go` command.
//
// Purpose: parse `go` into one value that the search (Phase 3) and time
// management (Phase 5) read.
// Invariants:
// - Every argument is optional; an argument that was not sent does not limit
//   the search (UCI spec), so each is an std::optional.
// - Numbers are 64-bit and may be zero or negative (a GUI can send a negative
//   remaining time); values beyond the 64-bit range are clamped to it.
// - restrict_to (`searchmoves`) holds only moves legal in the position given
//   to parse_go, without duplicates, in the order sent.
// - Parsing never throws except std::bad_alloc; a bad or unknown token is
//   skipped and described in `warnings`.
#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "core/position.hpp"
#include "uci/tokens.hpp"

namespace forkeng {

struct GoLimits {
  std::optional<std::int64_t> time[2];  // wtime, btime: ms left on each clock
  std::optional<std::int64_t> inc[2];   // winc, binc: ms added per move
  std::optional<std::int64_t> movestogo, depth, nodes, mate, movetime;
  bool infinite = false;
  bool ponder = false;
  std::vector<Move> restrict_to;  // searchmoves; empty means every legal move
  bool restrict_sent = false;     // `searchmoves` was present (even if no move in it was legal)
};

// Parses tokens[first..] (the tokens after `go`) for `pos`.
GoLimits parse_go(const std::vector<LineToken>& tokens, std::size_t first, const Position& pos,
                  std::vector<std::string>& warnings);

// Parses a UCI move for `pos`, accepting an upper-case promotion letter.
// Returns NoMove unless the move is legal.
Move parse_uci_move(const Position& pos, std::string_view text);

}  // namespace forkeng
