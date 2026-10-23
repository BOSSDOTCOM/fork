// movegen: fully legal move generation.
//
// Purpose: generate<Legal|Captures|Quiets> without make-and-test, using the
// check and pin information in the current State.
// Invariants:
// - Every generated move is legal; Captures and Quiets partition Legal
//   (Captures = captures, en passant and all promotions).
// - Generation order is deterministic (bench signature depends on it).
// - No heap allocation (tests/alloc_test.cpp).
#pragma once

#include "core/position.hpp"

namespace forkeng {

enum class GenMode : std::uint8_t {
  Legal,     // every legal move
  Captures,  // legal captures (incl. en passant) and all promotions
  Quiets,    // every other legal move, including castling
};

template <GenMode T>
void generate(const Position& pos, MoveList& list);

}  // namespace forkeng
