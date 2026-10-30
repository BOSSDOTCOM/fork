// SPDX-License-Identifier: GPL-3.0-or-later

// self_play: one self-play game for training data (DESIGN.md §5.3,
// deliverable 2).
//
// Purpose: Fork plays itself from an opening, every move a fixed node-count
// search (a depth-1 search where that limit cannot finish depth 1), recording each position's move and score
// into a GameWriter, and ends the game by the rules or by two exact adjudications: the Syzygy win/draw/loss
// tables once the root is in them, and a mate score reported by the search. An optional score adjudication
// (off by default) ends it as a win once the side ahead has scored at least adjudicate_cp for
// adjudicate_plies positions in a row.
// Invariants:
// - A game is a pure function of the build (evaluator and net), the
//   opening and SelfPlayConfig: the TT and the move-ordering history are
//   cleared before each game and no time limit applies, so the search is
//   deterministic (the bench-parity property).
// - No eval-based draw adjudication, and win adjudication only when
//   adjudicate_plies > 0 (§5.3: thresholds measured per labelling network;
//   generation 0's evaluation was too weak for any).
// - A game whose first search scores beyond decided_cp, or that reaches
//   max_plies, is discarded, never written.
// - Tables are probed only through endgame_tables (thread-safe win/draw/loss
//   probes, loaded once before any game starts).
#pragma once

#include <atomic>
#include <cstdint>
#include <memory>

#include "datagen/game_record.hpp"
#include "search/hash_memory.hpp"
#include "search/searcher.hpp"

namespace forkeng {

struct SelfPlayConfig {
  std::uint64_t nodes = 0;     // exact node limit per move
  std::size_t hash_bytes = 0;  // this game's transposition table
  int decided_cp = 400;        // discard openings scoring beyond this
  int max_plies = 500;         // discard longer games: bullet's game reader stops at 512 records
  int adjudicate_cp = 0;       // score adjudication: |White's score| at least this...
  int adjudicate_plies = 0;    // ...with one sign for this many positions in a row; 0 = off
};

// The score adjudication's count: positions in a row whose White-view score
// is at least `cp` for the same side. A score inside the band or for the
// other side starts the count again.
struct ScoreStreak {
  int cp = 0, plies = 0;
  int count = 0, sign = 0;
  // Adds the next recorded score; returns +1 (White wins) or -1 (Black
  // wins) once `plies` scores in a row are beyond the band, else 0.
  int add(int white_score) {
    const int s = white_score >= cp ? 1 : white_score <= -cp ? -1 : 0;
    count = s == 0 ? 0 : s == sign ? count + 1 : 1;
    sign = s;
    return plies > 0 && count >= plies ? s : 0;
  }
};

enum class GameEnd : std::uint8_t {
  Checkmate,
  Stalemate,
  Repetition,
  FiftyMoves,
  InsufficientMaterial,
  TableResult,  // the root is in the Syzygy tables
  MateFound,    // the search reported a forced mate
  DecidedOpening,
  TooLong,
  ScoreAdjudicated,  // the score adjudication (SelfPlayConfig::adjudicate_plies)
};
constexpr int GameEndCount = 10;
const char* game_end_name(GameEnd end);

struct SelfPlayOutcome {
  GameEnd end;
  GameResult result;  // meaningful only for written games
  bool written;       // false for DecidedOpening and TooLong
};

// One worker's game player: owns a search thread's state and its table.
class SelfPlayGame {
 public:
  // Returns null (and a reason in `report`) if the table cannot be allocated.
  static std::unique_ptr<SelfPlayGame> create(const SelfPlayConfig& config, std::string& report);

  // Plays one game from `opening` into `writer` (begun and, for written
  // games, finished here).
  SelfPlayOutcome play(const Position& opening, GameWriter& writer);

 private:
  explicit SelfPlayGame(const SelfPlayConfig& config) : config_(config), searcher_(table_) {}

  SelfPlayConfig config_;
  HashMemory memory_;
  TransTable table_;
  Searcher searcher_;
  std::atomic<bool> stop_{false};
};

}  // namespace forkeng
