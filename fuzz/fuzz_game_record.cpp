// SPDX-License-Identifier: GPL-3.0-or-later

// libFuzzer target: arbitrary bytes into the self-play game reader
// (src/datagen/game_record.hpp; DESIGN.md §5.3, deliverable 2). The reader
// must never crash or read out of bounds, and every game it accepts must
// re-encode to exactly the bytes it read.
#include <cstdint>
#include <cstdlib>
#include <span>
#include <string>

#include "datagen/game_record.hpp"

namespace {

void require(bool ok) {
  if (!ok) std::abort();  // libFuzzer reports the crash with its input
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
  static const bool initialized = (forkeng::init(), true);
  (void)initialized;
  if (size > 4096) return 0;
  const std::span<const std::uint8_t> input(data, size);
  std::size_t offset = 0;
  forkeng::ReadGame game;
  std::string error;
  while (offset < size) {
    const std::size_t start = offset;
    if (!forkeng::decode_game(input, offset, game, error)) {
      require(!error.empty());
      return 0;
    }
    require(offset > start && offset <= size);
    // Re-encode: Fork's writer must reproduce the accepted bytes, except the
    // fields the reader normalizes (castling order, the header score, a
    // zero fullmove number, a halfmove clock above 255).
    forkeng::Position pos;
    require(pos.set_fen(game.start_fen));
    forkeng::GameWriter writer;
    writer.begin(pos);
    for (const auto& m : game.moves) {
      writer.add(m.move, m.white_score);
      pos.make(m.move);
    }
    writer.finish(game.result);
    const auto again = writer.bytes();
    require(again.size() == offset - start);
    // The move records (after the 32-byte board) must match exactly.
    for (std::size_t i = forkeng::CompactBoardBytes; i < again.size(); ++i) require(again[i] == data[start + i]);
  }
  return 0;
}
