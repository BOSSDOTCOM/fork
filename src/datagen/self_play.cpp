// SPDX-License-Identifier: GPL-3.0-or-later

#include "datagen/self_play.hpp"

#include <cstdio>
#include <cstdlib>
#include <new>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "search/endgame_tables.hpp"

namespace forkeng {

namespace {

GameResult win_for(Color c) { return c == White ? GameResult::WhiteWin : GameResult::BlackWin; }

}  // namespace

const char* game_end_name(GameEnd end) {
  switch (end) {
    case GameEnd::Checkmate:
      return "checkmate";
    case GameEnd::Stalemate:
      return "stalemate";
    case GameEnd::Repetition:
      return "repetition";
    case GameEnd::FiftyMoves:
      return "fifty_moves";
    case GameEnd::InsufficientMaterial:
      return "insufficient_material";
    case GameEnd::TableResult:
      return "table_result";
    case GameEnd::MateFound:
      return "mate_found";
    case GameEnd::DecidedOpening:
      return "decided_opening";
    case GameEnd::TooLong:
      return "too_long";
    case GameEnd::ScoreAdjudicated:
      return "score_adjudicated";
  }
  return "?";
}

std::unique_ptr<SelfPlayGame> SelfPlayGame::create(const SelfPlayConfig& config, std::string& report) {
  std::unique_ptr<SelfPlayGame> game(new (std::nothrow) SelfPlayGame(config));
  if (!game) {
    report = "out of memory for the search state";
    return nullptr;
  }
  if (!game->memory_.resize(config.hash_bytes, report) || game->memory_.bytes() != config.hash_bytes) {
    report = "cannot allocate the " + std::to_string(config.hash_bytes >> 20) + " MB table: " + report;
    return nullptr;
  }
  game->table_.bind_memory(game->memory_.data(), game->memory_.bytes());
  return game;
}

SelfPlayOutcome SelfPlayGame::play(const Position& opening, GameWriter& writer, std::uint64_t save_seed) {
  memory_.clear(1);
  unsaved_ = 0;
  nodes_spent_ = 0;
  std::uint64_t save_stream = save_seed;
  searcher_.clear_history();
  Position pos = opening;
  pos.reserve_plies(static_cast<std::size_t>(config_.max_plies) + 1);
  writer.begin(pos);
  SearchQuota limits;
  const int table_pieces = endgame_table_pieces();
  ScoreStreak streak;
  streak.cp = config_.adjudicate_cp;
  streak.plies = config_.adjudicate_plies;

  auto finish = [&](GameEnd end, GameResult result) {
    writer.finish(result);
    return SelfPlayOutcome{end, result, true};
  };

  for (int ply = 0;; ++ply) {
    const Color us = pos.side_to_move();
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    // Mate is checked before the fifty-move rule (DESIGN.md 4.5).
    if (legal.size() == 0)
      return pos.in_check() ? finish(GameEnd::Checkmate, win_for(~us))
                            : finish(GameEnd::Stalemate, GameResult::Draw);
    if (pos.fifty_move_reached()) return finish(GameEnd::FiftyMoves, GameResult::Draw);
    if (pos.repetition_count() >= 3) return finish(GameEnd::Repetition, GameResult::Draw);
    if (pos.insufficient_material()) return finish(GameEnd::InsufficientMaterial, GameResult::Draw);
    if (table_pieces && popcount(pos.pieces()) <= table_pieces) {
      if (const auto wdl = probe_table_wdl(pos)) {
        // Cursed wins and blessed losses are draws under the fifty-move rule.
        const GameResult r = *wdl == TableWdl::Win    ? win_for(us)
                             : *wdl == TableWdl::Loss ? win_for(~us)
                                                      : GameResult::Draw;
        return finish(GameEnd::TableResult, r);
      }
    }
    if (ply >= config_.max_plies) return SelfPlayOutcome{GameEnd::TooLong, GameResult::Draw, false};

    // The split search (off unless save_percent < 100 or check_nodes is set).
    bool saved = true;
    limits.nodes = config_.nodes;
    if (pos.in_check()) {
      if (config_.check_nodes) limits.nodes = config_.check_nodes;
    } else if (config_.save_percent < 100) {
      saved = splitmix_next(save_stream) % 100 < static_cast<std::uint64_t>(config_.save_percent);
      if (!saved) limits.nodes = config_.unsaved_nodes;
    }

    table_.advance_age();
    SearchResult s = searcher_.deliberate(pos, limits, stop_, nullptr, nullptr);
    nodes_spent_ += s.nodes;
    // deliberate() always returns a legal root move, but where the node limit
    // runs out before depth 1 finishes (a position with long capture chains)
    // its score is meaningless (0 at depth 0) and must never be written: that
    // move is searched to depth 1 without a node limit instead, which always
    // finishes and stays deterministic.
    if (s.depth == 0) {
      SearchQuota one_ply;
      one_ply.depth = 1;
      s = searcher_.deliberate(pos, one_ply, stop_, nullptr, nullptr);
      nodes_spent_ += s.nodes;
    }
    if (s.best == NoMove || !legal.contains(s.best) || s.depth == 0) {
      std::fprintf(stderr, "fork_datagen: no finished search in %s\n", pos.fen().c_str());
      std::abort();
    }
    if (ply == 0 && !is_mate_score(s.score) && std::abs(s.score) > config_.decided_cp)
      return SelfPlayOutcome{GameEnd::DecidedOpening, GameResult::Draw, false};

    // An unsaved position keeps its move but not its score, except a mate
    // score, which ends the game and is written as the reason.
    const int white_score = us == White ? s.score : -s.score;
    if (!saved && !is_mate_score(s.score)) {
      writer.add(s.best, UnsavedScore);
      ++unsaved_;
      pos.make(s.best);
      continue;
    }
    writer.add(s.best, white_score);
    if (is_mate_score(s.score)) return finish(GameEnd::MateFound, s.score > 0 ? win_for(us) : win_for(~us));
    if (config_.adjudicate_plies > 0) {
      if (const int winner = streak.add(white_score))
        return finish(GameEnd::ScoreAdjudicated, winner > 0 ? GameResult::WhiteWin : GameResult::BlackWin);
    }
    pos.make(s.best);
  }
}

}  // namespace forkeng
