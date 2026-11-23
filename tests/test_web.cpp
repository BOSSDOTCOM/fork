// SPDX-License-Identifier: GPL-3.0-or-later

// The web page's entry points (src/web/web_engine.hpp; DESIGN.md §5.5),
// natively: positions and moves in and out, the game states, a search and
// its iteration reports, notation and the static evaluation.
//
// Positions, all checked with python-chess 1.11.2 (an independent
// implementation): the checkmate, stalemate and illegal-move positions of
// tests/test_uci.cpp (checked 2026-10-24); the knight shuffle and the
// fifty-move clock position of tests/test_draws.cpp; on 2026-10-31,
// 4k3/8/8/8/8/8/8/4K3 w - - 0 1 is valid with insufficient material, the
// start position has 20 legal moves, and in 6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1
// a1a8 mates. On 2026-11-02, every expected SAN below was python-chess
// 1.11.2's for the same moves (Board.san), in the CPW perft positions
// (tests/suite.hpp: Kiwipete, position 5, position 6) and in
// 8/5k2/8/8/Q6Q/8/8/Q3K3 w - - 0 1, built for the three disambiguation
// forms (python-chess: valid).
#include <set>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

#include "core/movegen.hpp"
#include "core/position.hpp"
#include "eval/eval.hpp"
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

TEST_CASE("web", "lines in standard algebraic notation") {
  CHECK_EQ(fork_web_init(4), 1);
  const auto san = [](const char* fen, const char* moves, const char* line) {
    return std::string(fork_web_san(fen, moves, line));
  };
  CHECK_EQ(san("startpos", "", "e2e4 e7e5 g1f3 b8c6 f1b5"), std::string("e4 e5 Nf3 Nc6 Bb5"));
  // Captures, en passant, check and mate.
  CHECK_EQ(san("startpos", "e2e4 a7a6", "e4e5 d7d5 e5d6"), std::string("e5 d5 exd6"));
  CHECK_EQ(san("startpos", "", "f2f3 e7e5 g2g4 d8h4"), std::string("f3 e5 g4 Qh4#"));
  CHECK_EQ(san("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "", "a1a8"), std::string("Ra8#"));
  // Castling both ways (Kiwipete).
  const char* kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  CHECK_EQ(san(kiwipete, "", "e1g1 e8c8"), std::string("O-O O-O-O"));
  CHECK_EQ(san(kiwipete, "", "e1c1"), std::string("O-O-O"));
  // Promotions with capture, and knights told apart by file (position 5).
  const char* position5 = "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8";
  CHECK_EQ(san(position5, "", "d7c8q"), std::string("dxc8=Q"));
  CHECK_EQ(san(position5, "", "d7c8n"), std::string("dxc8=N"));
  CHECK_EQ(san(position5, "", "e2c3"), std::string("Nec3"));
  CHECK_EQ(san(position5, "", "b1c3"), std::string("Nbc3"));
  // Rooks told apart by file (position 6); queens by file, rank or both.
  CHECK_EQ(san("r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10", "", "f1e1"),
           std::string("Rfe1"));
  const char* queens = "8/5k2/8/8/Q6Q/8/8/Q3K3 w - - 0 1";
  CHECK_EQ(san(queens, "", "a4d4"), std::string("Qa4d4"));
  CHECK_EQ(san(queens, "", "a1d4"), std::string("Q1d4"));
  CHECK_EQ(san(queens, "", "h4d4"), std::string("Qhd4"));
  CHECK_EQ(san(queens, "", "h4f6"), std::string("Qhf6+"));
  CHECK_EQ(san(queens, "", "a4a8"), std::string("Qa8"));
  // The line ends at its first illegal or malformed move; a bad start gives "".
  CHECK_EQ(san("startpos", "", "e2e4 e2e4 e7e5"), std::string("e4"));
  CHECK_EQ(san("startpos", "", "e2e4 zz e7e5"), std::string("e4"));
  CHECK_EQ(san("not a fen", "", "e2e4"), std::string(""));
  CHECK_EQ(san("startpos", "e2e5", "e2e4"), std::string(""));
  // It leaves the engine's own position alone.
  CHECK_EQ(fork_web_set_position("startpos", "d2d4"), 1);
  san("startpos", "", "e2e4");
  CHECK_EQ(std::string(fork_web_fen()),
           std::string("rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1"));
}

TEST_CASE("web", "the static evaluation of the current position") {
  CHECK_EQ(fork_web_init(4), 1);
  // The build's own static evaluation, from the side to move's view: in the
  // stalemate position above, Black, a queen down, stands far worse.
  Position pos;
  CHECK_EQ(fork_web_set_position("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", ""), 1);
  CHECK(pos.set_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"));
  CHECK_EQ(fork_web_evaluate(), static_eval(pos));
  CHECK_MSG(fork_web_evaluate() < -300, fork_web_evaluate());
  CHECK_EQ(fork_web_set_position("startpos", "e2e4"), 1);
  CHECK(pos.set_fen(fork_web_fen()));
  CHECK_EQ(fork_web_evaluate(), static_eval(pos));
}

namespace {
std::vector<std::string> reported_lines;
void keep_line(const char* line) { reported_lines.emplace_back(line); }
}  // namespace

TEST_CASE("web", "each finished iteration is reported while the search runs") {
  CHECK_EQ(fork_web_init(4), 1);
  CHECK_EQ(fork_web_set_position("startpos", "e2e4"), 1);
  fork_web_new_game();
  reported_lines.clear();
  fork_web_set_iteration_hook(keep_line);
  const std::string result = fork_web_search(20000);
  fork_web_set_iteration_hook(nullptr);
  CHECK_MSG(reported_lines.size() >= 2, result);
  if (reported_lines.empty()) return;
  // Depths rise; each line names its score, nodes and a line of legal moves
  // starting from the root; the last one is the result's.
  int last_depth = 0;
  for (const std::string& line : reported_lines) {
    CHECK_MSG(line.rfind("depth ", 0) == 0, line);
    const int depth = std::stoi(field(line, "depth"));
    CHECK_MSG(depth > last_depth, line);
    last_depth = depth;
    CHECK_MSG(!field(line, "cp").empty() || !field(line, "mate").empty(), line);
    CHECK_MSG(!field(line, "nodes").empty(), line);
    CHECK_MSG(words(fork_web_legal_moves()).count(field(line, "pv")) == 1, line);
  }
  CHECK_EQ(field(reported_lines.back(), "pv"), field(result, "pv"));
  CHECK_EQ(std::to_string(last_depth), field(result, "depth"));
  // Without a hook nothing is reported.
  reported_lines.clear();
  fork_web_new_game();
  fork_web_search(5000);
  CHECK_EQ(reported_lines.size(), std::size_t{0});
}

// A search stopped mid-iteration that plays the unfinished iteration's move
// reports that move's line at the unfinished depth; the result then gives the
// same depth and score (fix/partial-iteration-report, 2026-11-10). Before the
// fix, after 1. e4 at 21,000 nodes the last line was "depth 8 score cp -10 ...
// pv c7c5 ..." and the result "bestmove c7c5 score cp -10 depth 7": depth 8's
// score and line under depth 7 (also at 1,000, 5,000 and 21,500-24,000
// nodes; the case above, at 20,000, stopped after a finished iteration). The
// limits are swept so the case keeps a stop mid-iteration as the tree changes.
TEST_CASE("web", "after a stop mid-iteration the result's depth and score are its last line's") {
  CHECK_EQ(fork_web_init(4), 1);
  for (int nodes = 1000; nodes <= 25000; nodes += 500) {
    CHECK_EQ(fork_web_set_position("startpos", "e2e4"), 1);
    fork_web_new_game();
    reported_lines.clear();
    fork_web_set_iteration_hook(keep_line);
    const std::string result = fork_web_search(nodes);
    fork_web_set_iteration_hook(nullptr);
    CHECK_MSG(!reported_lines.empty(), result);
    if (reported_lines.empty()) continue;
    const std::string& last = reported_lines.back();
    CHECK_MSG(field(last, "depth") == field(result, "depth") && field(last, "cp") == field(result, "cp") &&
                  field(last, "mate") == field(result, "mate") &&
                  field(last, "pv") == field(result, "bestmove"),
              nodes << " nodes: last line '" << last << "', result '" << result << "'");
  }
}

}  // namespace forkeng::test
