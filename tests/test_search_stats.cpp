// SPDX-License-Identifier: GPL-3.0-or-later

// The stats build's measurement counters (DESIGN.md §5.7, Phase 4 step 1).
// Compiled only with FORK_SEARCH_STATS (the clang-stats preset), suite
// "search_stats". The counters must only read the search: a stats build
// with every report on searches the same tree, node for node, as with them
// off, and that run is pinned to tests/bench-<net>.ref by bench_parity.
// Positions: the CPW perft suite (tests/suite.hpp) and a FEN reused from
// tests/test_search.cpp (checked there by tools/check_search_positions.py).
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#ifdef _WIN32
#include <io.h>
#else
#include <unistd.h>
#endif

#include "core/movegen.hpp"
#include "eval/eval.hpp"
#include "harness.hpp"
#include "search/search_bench.hpp"
#include "search/searcher.hpp"
#include "suite.hpp"

#if defined(FORK_EVAL_NNUE)
#include "eval/nnue/accumulator.hpp"
#endif

namespace forkeng::test {

TEST_CASE("search_stats", "bench is unchanged with the counter report on") {
  // The environment variable is read when a Searcher is constructed.
  const auto set_report = [](bool on) {
#ifdef _WIN32
    _putenv_s("FORK_STATS_REPORT", on ? "1" : "");
#else
    if (on)
      setenv("FORK_STATS_REPORT", "1", 1);
    else
      unsetenv("FORK_STATS_REPORT");
#endif
  };
  set_report(false);
  const SearchBenchResult off = run_search_bench();
  set_report(true);
  // The bench with stderr sent to a file, read back afterwards.
  const std::string path = "search_stats_stderr.txt";
  std::fflush(stderr);
#ifdef _WIN32
  const int saved = _dup(_fileno(stderr));
  std::FILE* sink = std::fopen(path.c_str(), "wb");
  _dup2(_fileno(sink), _fileno(stderr));
#else
  const int saved = dup(fileno(stderr));
  std::FILE* sink = std::fopen(path.c_str(), "wb");
  dup2(fileno(sink), fileno(stderr));
#endif
  const SearchBenchResult on = run_search_bench();
  std::fflush(stderr);
#ifdef _WIN32
  _dup2(saved, _fileno(stderr));
  _close(saved);
#else
  dup2(saved, fileno(stderr));
  close(saved);
#endif
  std::fclose(sink);
  set_report(false);
  std::ifstream in(path, std::ios::binary);
  std::ostringstream text;
  text << in.rdbuf();
  in.close();
  std::remove(path.c_str());
  const std::string err = text.str();
  CHECK_EQ(on.nodes, off.nodes);
  CHECK_EQ(on.signature, off.signature);
  // One dump per bench position, each a full counter line.
  std::size_t dumps = 0;
  for (std::size_t at = err.find("search_counters "); at != std::string::npos;
       at = err.find("search_counters ", at + 1))
    ++dumps;
  CHECK_EQ(dumps, search_bench_fens().size());
  CHECK(err.find(" main_nodes=") != std::string::npos);
  CHECK(err.find(" pawn_makes_quiesce=") != std::string::npos);
#if defined(FORK_EVAL_NNUE)
  CHECK(err.find(" walked_plies=") != std::string::npos);
#endif
}

TEST_CASE("search_stats", "node and evaluation counts add up") {
  std::vector<TtBucket> buckets(16384);
  TransTable table;
  table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  auto searcher = std::make_unique<Searcher>(table);
  const std::atomic<bool> stop{false};
  SearchQuota limits;
  limits.depth = 8;
  std::uint64_t nodes = 0;
  for (const PerftPosition& p : perft_suite()) {
    Position pos;
    CHECK(pos.set_fen(p.fen));
    nodes += searcher->deliberate(pos, limits, stop, nullptr, nullptr).nodes;
  }
  const SearchCounters& c = searcher->counters;
  CHECK_EQ(c.root_nodes + c.main_nodes + c.quiesce_nodes_pv + c.quiesce_nodes_non_pv, nodes);
  CHECK(c.evals_main > 0);
  CHECK(c.evals_quiesce > 0);
  CHECK(c.pawn_makes > 0);
  CHECK(c.pawn_makes <= c.makes);
  CHECK(c.pawn_makes_quiesce <= c.pawn_makes);
#if defined(FORK_EVAL_NNUE)
  // Two layers count independently: the search's evaluation calls and the
  // feature stack's evaluations.
  const FeatureStackTally& t = searcher->feature_tally();
  CHECK_EQ(t.evaluations, c.evals_main + c.evals_quiesce + c.evals_horizon);
  CHECK_EQ(t.root_refreshes, static_cast<std::uint64_t>(perft_suite().size()));
  CHECK(t.perspective_updates > 0);
  CHECK(t.update_rows >= 2 * t.perspective_updates);  // every move removes and adds a piece
#endif
}

TEST_CASE("search_stats", "pawn moves and TT evaluations are counted where they occur") {
  std::vector<TtBucket> buckets(16384);
  TransTable table;
  table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  const std::atomic<bool> stop{false};
  SearchQuota limits;
  limits.depth = 8;
  {
    // No pawns on the board: no pawn moves.
    auto searcher = std::make_unique<Searcher>(table);
    Position pos;
    CHECK(pos.set_fen("8/8/3k4/8/8/3K4/8/R7 w - - 0 1"));
    searcher->deliberate(pos, limits, stop, nullptr, nullptr);
    CHECK_EQ(searcher->counters.pawn_makes, std::uint64_t{0});
    CHECK(searcher->counters.makes > 0);
  }
  for (const bool use_tt : {true, false}) {
    auto searcher = std::make_unique<Searcher>(table);
    searcher->switches.use_tt = use_tt;
    Position pos;
    CHECK(pos.set_fen(perft_suite()[1].fen));
    searcher->deliberate(pos, limits, stop, nullptr, nullptr);
    const std::uint64_t first = searcher->counters.tt_eval_hits_main;
    searcher->deliberate(pos, limits, stop, nullptr, nullptr);  // the TT is kept: its evaluations are reused
    const std::uint64_t second = searcher->counters.tt_eval_hits_main - first;
    if (use_tt) {
      CHECK(second > 0);
    } else {
      CHECK_EQ(first + second, std::uint64_t{0});
      CHECK_EQ(searcher->counters.tt_eval_hits_quiesce, std::uint64_t{0});
    }
  }
}

#if defined(FORK_EVAL_NNUE)
TEST_CASE("search_stats", "the feature stack's tally matches hand counts") {
  // The oracle is the feature definition (accumulator.hpp's header): a
  // non-capturing piece move removes one row and adds one per perspective; a
  // pawn move also changes the link rows on S512+PP; a king crossing the
  // d/e line recomputes its own perspective on a mirrored net. Moves are
  // picked from the legal list by their kind, not typed.
  const NetFile& net = embedded_net();
  auto stack = std::make_unique<FeatureStack>();
  const auto pick = [](const Position& pos, PieceType type, bool capture) {
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    for (Move m : legal)
      if (kind_of(pos.piece_at(m.from())) == type && m.is_capture() == capture && !m.is_castle() &&
          !m.is_promotion())
        return m;
    return NoMove;
  };
  Position pos;
  CHECK(pos.set_fen(perft_suite()[0].fen));
  stack->reset(net, pos);
  CHECK_EQ(stack->tally().root_refreshes, std::uint64_t{1});
  // A knight move, evaluated one ply on: two perspectives, two rows each.
  const Move knight = pick(pos, Knight, false);
  CHECK(!knight.is_none());
  stack->push_move(net, 0, pos, knight);
  pos.make(knight);
  stack->evaluate(net, 1, pos);
  CHECK_EQ(stack->tally().perspective_updates, std::uint64_t{2});
  CHECK_EQ(stack->tally().update_rows, std::uint64_t{4});
  CHECK_EQ(stack->tally().link_updates, std::uint64_t{0});
  CHECK_EQ(stack->tally().walked_plies, std::uint64_t{1});
  CHECK_EQ(stack->tally().evaluations, std::uint64_t{1});
  // A pawn move and another knight move, evaluated two plies on.
  const Move pawn = pick(pos, Pawn, false);
  CHECK(!pawn.is_none());
  stack->push_move(net, 1, pos, pawn);
  pos.make(pawn);
  const Move knight2 = pick(pos, Knight, false);
  CHECK(!knight2.is_none());
  stack->push_move(net, 2, pos, knight2);
  pos.make(knight2);
  stack->evaluate(net, 3, pos);
  CHECK_EQ(stack->tally().perspective_updates, std::uint64_t{6});
  CHECK_EQ(stack->tally().walked_plies, std::uint64_t{3});
  CHECK_EQ(stack->tally().move_pushes, std::uint64_t{3});
  if constexpr (NetArchitecture == 8) {
    CHECK_EQ(stack->tally().link_updates, std::uint64_t{2});  // the pawn move, both perspectives
    CHECK(stack->tally().update_rows >= 12);
  } else {
    CHECK_EQ(stack->tally().link_updates, std::uint64_t{0});
    CHECK_EQ(stack->tally().update_rows, std::uint64_t{12});
  }
  // A null move is pushed, never evaluated by itself.
  stack->push_null(3);
  CHECK_EQ(stack->tally().null_pushes, std::uint64_t{1});
  // Kiwipete: a king move onto the d-file crosses the d/e line.
  Position kiwi;
  CHECK(kiwi.set_fen(perft_suite()[1].fen));
  stack->reset(net, kiwi);
  MoveList legal;
  generate<GenMode::Legal>(kiwi, legal);
  Move across = NoMove;
  for (Move m : legal)
    if (kind_of(kiwi.piece_at(m.from())) == King && !m.is_castle() && file_of(m.to()) == 3) across = m;
  CHECK(!across.is_none());
  const std::uint64_t refreshes = stack->tally().frame_refreshes;
  stack->push_move(net, 0, kiwi, across);
  CHECK_EQ(stack->tally().frame_refreshes - refreshes, std::uint64_t{NetMirrored ? 1 : 0});
}
#endif

}  // namespace forkeng::test
