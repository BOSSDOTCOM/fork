// Legal move generation.
#pragma once

#include "core/position.hpp"

namespace fork {

enum class GenType : std::uint8_t {
  Legal,     // every legal move
  Captures,  // legal captures (incl. en passant) and all promotions
  Quiets,    // every other legal move, including castling
};

template <GenType T>
void generate(const Position& pos, MoveList& list);

}  // namespace fork
