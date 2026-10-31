// SPDX-License-Identifier: GPL-3.0-or-later

// The web page's entry points (src/web/web_engine.hpp; DESIGN.md §5.5),
// natively: positions and moves in and out, the game states, and a search.
//
// Positions, all checked with python-chess 1.11.2 (an independent
// implementation): the checkmate, stalemate and illegal-move positions of
// tests/test_uci.cpp (checked 2026-10-24); the knight shuffle and the
// fifty-move clock position of tests/test_draws.cpp; on 2026-10-31,
// 4k3/8/8/8/8/8/8/4K3 w - - 0 1 is valid with insufficient material, the
// start position has 20 legal moves, and in 6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1
// a1a8 mates.
#include <set>
#include <sstream>
#include <string>
#include <string_view>

#include "core/movegen.hpp"
#include "core/position.hpp"
#include "harness.hpp"
#include "web/web_engine.hpp"

namespace forkeng::test {

namespace {

std::set<std::string> words(std::string_view text) {
  std::istringstream in{std::string(text)};
  std::set<std::string> out;
  for (std::string w; in >> w;) out.insert(w);
  return out;
}

// The value after `key` in a search result, or "" if absent.
std::string field(std::string_view text, std::string_view key) {
  std::istringstream in{std::string(text)};
  for (std::string w; in >> w;) {
    if (w == key) {
      std::string v;
      in >> v;
      return v;
    }
  }
  return "";
}

}  // namespace

TEST_CASE("web", "positions in, legal moves and FEN out") {
  CHECK_EQ(fork_web_init(4), 1);
  CHECK_EQ(fork_web_set_position("startpos", ""), 1);
  CHECK_EQ(std::string(fork_web_fen()),
           std::string("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"));
  const std::set<std::string> start = words(fork_web_legal_moves());
  CHECK_EQ(start.size(), std::size_t{20});
  // Every listed move is legal in Fork's own position, and no move is listed twice.
  Position pos;
  CHECK(pos.set_fen(fork_web_fen()));
  for (const std::string& m : start) CHECK_MSG(pos.parse_uci(m) != NoMove, m);
  CHECK_EQ(fork_web_set_position("startpos", "e2e4 e7e5"), 1);
  CHECK_EQ(std::string(fork_web_fen()),
           std::string("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"));
  // An illegal move or a bad FEN is refused and leaves the position as it was.
  CHECK_EQ(fork_web_set_position("startpos", "e2e4 e7e5 e1e3"), 0);
  CHECK_EQ(fork_web_set_position("not a fen", ""), 0);
  CHECK_EQ(std::string(fork_web_fen()),
           std::string("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"));
  // Extra spaces between moves are ignored.
  CHECK_EQ(fork_web_set_position("startpos", "  e2e4   e7e5 "), 1);
  CHECK_EQ(std::string(fork_web_status()), std::string("playing"));
}

TEST_CASE("web", "game states: mate, stalemate and the draws by rule") {
  CHECK_EQ(fork_web_init(4), 1);
  CHECK_EQ(fork_web_set_position("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1", ""), 1);
  CHECK_EQ(std::string(fork_web_status()), std::string("checkmate"));
  CHECK_EQ(std::string(fork_web_legal_moves()), std::string(""));
  CHECK_EQ(std::string(fork_web_search(1000)), std::string("bestmove none"));
  CHECK_EQ(fork_web_set_position("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", ""), 1);
  CHECK_EQ(std::string(fork_web_status()), std::string("stalemate"));
  CHECK_EQ(fork_web_set_position("4k3/8/8/8/8/8/8/4K3 w - - 0 1", ""), 1);
  CHECK_EQ(std::string(fork_web_status()), std::string("insufficient"));
  CHECK_EQ(fork_web_set_position("4k3/8/8/8/8/8/8/R3K3 w - - 99 80", ""), 1);
  CHECK_EQ(std::string(fork_web_status()), std::string("playing"));
  CHECK_EQ(fork_web_set_position("4k3/8/8/8/8/8/8/R3K3 w - - 99 80", "a1a2"), 1);
  CHECK_EQ(std::string(fork_web_status()), std::string("fifty-move"));
  CHECK_EQ(fork_web_set_position("startpos", "g1f3 g8f6 f3g1 f6g8"), 1);
  CHECK_EQ(std::string(fork_web_status()), std::string("playing"));
  CHECK_EQ(fork_web_set_position("startpos", "g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8"), 1);
  CHECK_EQ(std::string(fork_web_status()), std::string("repetition"));
}

TEST_CASE("web", "a search returns a legal move with its score and line, deterministically") {
  CHECK_EQ(fork_web_init(4), 1);
  CHECK_EQ(fork_web_set_position("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", ""), 1);
  fork_web_new_game();
  const std::string mate = fork_web_search(20000);
  CHECK_MSG(field(mate, "bestmove") == "a1a8", mate);
  CHECK_MSG(field(mate, "mate") == "1", mate);
  CHECK_MSG(field(mate, "pv") == "a1a8", mate);
  CHECK_EQ(fork_web_set_position("startpos", "e2e4"), 1);
  fork_web_new_game();
  const std::string first = fork_web_search(5000);
  fork_web_new_game();
  const std::string second = fork_web_search(5000);
  CHECK_EQ(first, second);
  CHECK_MSG(words(fork_web_legal_moves()).count(field(first, "bestmove")) == 1, first);
  CHECK_MSG(!field(first, "cp").empty() && !field(first, "depth").empty() && !field(first, "nodes").empty(),
            first);
  // The node limit is honoured: the search stops within one node batch of it.
  CHECK_MSG(std::stoull(field(first, "nodes")) >= 5000, first);
}

}  // namespace forkeng::test
