// SPDX-License-Identifier: GPL-3.0-or-later

// game_record: self-play games in the viriformat layout (DESIGN.md §5.3,
// deliverable 2), written and read by Fork's own code from the format's
// README (cosmobobak/viriformat, MIT, pinned in KB phase4-pipeline.md §3).
//
// Purpose: one game = a 32-byte packed start board, then one (move, score)
// pair of 2 + 2 bytes per position played, then 4 zero bytes. The bullet
// trainer reads these files directly.
// Invariants:
// - Little-endian throughout; squares a1 = 0 ... h8 = 63.
// - Board: occupancy (u64); one 4-bit code per occupied square in ascending
//   square order, entry k in byte 8 + k/2, low nibble for even k; code =
//   colour << 3 | type (pawn 0 ... king 5), type 6 for a rook that still
//   carries a castling right (castling rights exist only there); byte 24 =
//   en passant square (Fork's: set only when an en passant capture is legal)
//   or 64, plus 128 when Black is to move; halfmove (capped at 255),
//   fullmove (u16), a header score of 0, the result (0 Black won, 1 draw,
//   2 White won), a zero byte.
// - Move: from | to << 6 | promotion (0 knight ... 3 queen) << 12 | type << 14
//   with type 0 normal, 1 en passant, 2 castling (king to its own rook's
//   square, as Fork encodes it), 3 promotion.
// - Score: the search score of the position the move was played in, from
//   White's view (i16).
// - Never writes the format's later extension record (bullet's pinned
//   reader predates it).
// - The reader accepts only games whose every move is legal; it never reads
//   past the end of its input.
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

#include "core/position.hpp"

namespace forkeng {

// The game's result, from White's view, as the format stores it.
enum class GameResult : std::uint8_t { BlackWin = 0, Draw = 1, WhiteWin = 2 };

constexpr std::size_t CompactBoardBytes = 32;
constexpr std::size_t MoveRecordBytes = 4;

// The packed start board of `pos` with `result` filled in.
void encode_board(const Position& pos, GameResult result, std::uint8_t out[CompactBoardBytes]);

// The format's 16-bit move code for a move of `pos` (Fork's own encoding
// differs in the flag bits).
std::uint16_t encode_move(Move m);

// Builds one game in memory; the whole game is appended to a file only
// when finished, so a file never holds part of a game it wrote.
class GameWriter {
 public:
  GameWriter() { bytes_.reserve(8192); }

  void begin(const Position& start);
  void add(Move m, int white_score);
  void finish(GameResult result);  // writes the result and the terminator

  std::span<const std::uint8_t> bytes() const { return bytes_; }
  int positions() const { return positions_; }

 private:
  std::vector<std::uint8_t> bytes_;
  int positions_ = 0;
};

struct ReadMove {
  Move move;  // Fork's move, legal in the position it was played in
  int white_score;
};

struct ReadGame {
  std::string start_fen;
  GameResult result = GameResult::Draw;
  std::vector<ReadMove> moves;
};

// Reads the game starting at `offset` and advances it past the terminator.
// Returns false, with a reason in `error`, on any malformed or illegal
// content (offset is then unspecified).
bool decode_game(std::span<const std::uint8_t> data, std::size_t& offset, ReadGame& out, std::string& error);

}  // namespace forkeng
