// SPDX-License-Identifier: GPL-3.0-or-later

#include "datagen/self_play.hpp"

#include <cstdio>
#include <cstdlib>
#include <new>

#include "core/movegen.hpp"
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

SelfPlayOutcome SelfPlayGame::play(const Position& opening, GameWriter& writer) {
  memory_.clear(1);
  searcher_.clear_history();
  Position pos = opening;
  pos.reserve_plies(static_cast<std::size_t>(config_.max_plies) + 1);
  writer.begin(pos);
  SearchQuota limits;
  limits.nodes = config_.nodes;
  const int table_pieces = endgame_table_pieces();

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

    table_.advance_age();
    SearchResult s = searcher_.deliberate(pos, limits, stop_, nullptr, nullptr);
    // deliberate() always returns a legal root move, but where the node limit
    // runs out before depth 1 finishes (a position with long capture chains)
    // its score is meaningless (0 at depth 0) and must never be written: that
    // move is searched to depth 1 without a node limit instead, which always
    // finishes and stays deterministic.
    if (s.depth == 0) {
      SearchQuota one_ply;
      one_ply.depth = 1;
      s = searcher_.deliberate(pos, one_ply, stop_, nullptr, nullptr);
    }
    if (s.best == NoMove || !legal.contains(s.best) || s.depth == 0) {
      std::fprintf(stderr, "fork_datagen: no finished search in %s\n", pos.fen().c_str());
      std::abort();
    }
    if (ply == 0 && !is_mate_score(s.score) && std::abs(s.score) > config_.decided_cp)
      return SelfPlayOutcome{GameEnd::DecidedOpening, GameResult::Draw, false};

    writer.add(s.best, us == White ? s.score : -s.score);
    if (is_mate_score(s.score)) return finish(GameEnd::MateFound, s.score > 0 ? win_for(us) : win_for(~us));
    pos.make(s.best);
  }
}

}  // namespace forkeng
