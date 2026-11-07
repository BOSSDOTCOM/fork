// SPDX-License-Identifier: GPL-3.0-or-later

// The stats build's measurement counters (DESIGN.md §5.7, Phase 4 step 1).
// Compiled only with FORK_SEARCH_STATS (the clang-stats preset), suite
// "search_stats". The counters must only read the search: a stats build
// with every report on searches the same tree, node for node, as with them
// off, and that run is pinned to tests/bench-<net>.ref by bench_parity.
// Positions: the CPW perft suite (tests/suite.hpp) and a FEN reused from
// tests/test_search.cpp (checked there by tools/check_search_positions.py).
#include <algorithm>
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

// X2: every LMR site lands in each histogram once (a missing arrival in its
// own counter), the term's changes need a firing, every late capture lands
// in the take histogram; and history persists across the searches of a
// game, so the replay sees larger history values than a cleared search.
TEST_CASE("search_stats", "X2 histograms add up, and history carries over between searches") {
  std::vector<TtBucket> buckets(16384);
  TransTable table;
  table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  const std::atomic<bool> stop{false};
  SearchQuota limits;
  limits.depth = 9;
  auto carried = std::make_unique<Searcher>(table);
  Position pos;
  CHECK(pos.set_fen(perft_suite()[0].fen));
  // A short game: each side plays the search's move, history carried.
  for (int ply = 0; ply < 8; ++ply) {
    const SearchResult r = carried->deliberate(pos, limits, stop, nullptr, nullptr);
    CHECK(!r.best.is_none());
    pos.make(r.best);
  }
  const SearchCounters before = carried->counters;
  carried->deliberate(pos, limits, stop, nullptr, nullptr);
  const SearchCounters& c = carried->counters;
  const auto sum = [](const std::uint64_t* bins, int count) {
    std::uint64_t total = 0;
    for (int i = 0; i < count; ++i) total += bins[i];
    return total;
  };
  CHECK(c.lmr_rule_sites > 0);
  CHECK_EQ(sum(c.lmr_order_bins, OrderBins), c.lmr_rule_sites);
  CHECK_EQ(sum(c.lmr_quiet_bins, TableBins), c.lmr_rule_sites);
  CHECK_EQ(sum(c.lmr_reply_bins, TableBins) + c.lmr_reply_absent, c.lmr_rule_sites);
  CHECK_EQ(sum(c.lmr_follow_bins, TableBins) + c.lmr_follow_absent, c.lmr_rule_sites);
  CHECK(c.lmr_history_changes <= c.lmr_history_fire_less + c.lmr_history_fire_more);
  CHECK(c.late_capture_sites > 0);
  CHECK_EQ(sum(c.late_take_bins, TableBins), c.late_capture_sites);
  // The last search's sites with a zero-band butterfly value (bin of [0, 250)):
  // fewer with history carried than in a cleared searcher on the same position.
  const std::uint64_t carried_sites = c.lmr_rule_sites - before.lmr_rule_sites;
  const std::uint64_t carried_zero = c.lmr_quiet_bins[TableBins / 2] - before.lmr_quiet_bins[TableBins / 2];
  std::fill(buckets.begin(), buckets.end(), TtBucket{});
  auto cleared = std::make_unique<Searcher>(table);
  cleared->deliberate(pos, limits, stop, nullptr, nullptr);
  const SearchCounters& f = cleared->counters;
  CHECK(carried_sites > 0 && f.lmr_rule_sites > 0);
  CHECK_MSG(static_cast<double>(carried_zero) / static_cast<double>(carried_sites) <
                static_cast<double>(f.lmr_quiet_bins[TableBins / 2]) / static_cast<double>(f.lmr_rule_sites),
            "zero-band share carried " << carried_zero << "/" << carried_sites << ", cleared "
                                       << f.lmr_quiet_bins[TableBins / 2] << "/" << f.lmr_rule_sites);
}

// X6: one trace row per finished iteration. The oracle for each row's best
// move is a separate search to that row's depth from the same cleared
// state (a search is deterministic, so its iterations repeat the longer
// search's first ones).
TEST_CASE("search_stats", "the iteration trace has one row per finished iteration, with the best move") {
  std::vector<TtBucket> buckets(16384);
  TransTable table;
  table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  const std::atomic<bool> stop{false};
  const auto set_trace = [](bool on) {
#ifdef _WIN32
    _putenv_s("FORK_ITERATION_TRACE", on ? "1" : "");
#else
    if (on)
      setenv("FORK_ITERATION_TRACE", "1", 1);
    else
      unsetenv("FORK_ITERATION_TRACE");
#endif
  };
  Position pos;
  CHECK(pos.set_fen(perft_suite()[1].fen));
  SearchQuota limits;
  limits.depth = 10;
  set_trace(true);
  auto traced = std::make_unique<Searcher>(table);
  set_trace(false);
  const std::string path = "search_stats_trace.txt";
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
  const SearchResult result = traced->deliberate(pos, limits, stop, nullptr, nullptr);
  std::fflush(stderr);
#ifdef _WIN32
  _dup2(saved, _fileno(stderr));
  _close(saved);
#else
  dup2(saved, fileno(stderr));
  close(saved);
#endif
  std::fclose(sink);
  std::ifstream in(path, std::ios::binary);
  std::vector<std::vector<long long>> rows;
  for (std::string line; std::getline(in, line);) {
    if (line.rfind("iteration_trace ", 0) != 0) continue;
    std::vector<long long> fields;
    std::istringstream text(line.substr(16));
    for (std::string field; std::getline(text, field, '|');) fields.push_back(std::stoll(field));
    CHECK_EQ(fields.size(), std::size_t{11});
    rows.push_back(fields);
  }
  in.close();
  std::remove(path.c_str());
  CHECK_EQ(static_cast<int>(rows.size()), result.depth);
  for (std::size_t k = 0; k < rows.size(); ++k) {
    const std::vector<long long>& r = rows[k];
    CHECK_EQ(r[0], static_cast<long long>(k + 1));  // depth
    CHECK(r[2] >= 0 && r[2] <= 1000);               // share
    CHECK(r[3] >= 0 && r[3] <= 1000);               // share over every pass
    CHECK(r[4] >= 0 && r[4] <= 1000);               // runner-up
    CHECK(r[6] >= r[5]);                            // the iteration's nodes include its last pass
    CHECK(r[8] >= 1);                               // passes
    CHECK_EQ(r[9], 48LL);                           // Kiwipete's 48 root moves (tests/suite.hpp)
    // The oracle: a search to this depth from the same cleared state.
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    auto shorter = std::make_unique<Searcher>(table);
    SearchQuota to_depth;
    to_depth.depth = static_cast<int>(k + 1);
    const SearchResult s = shorter->deliberate(pos, to_depth, stop, nullptr, nullptr);
    CHECK_EQ(r[1], static_cast<long long>(s.best.raw()));
    CHECK_EQ(r[7], static_cast<long long>(s.score));
  }
  CHECK(!rows.empty() && rows.back()[1] == static_cast<long long>(result.best.raw()));
}

// X10, the decision ledger: its side searches must be invisible to the real
// search. The bench with the ledger, the trace and the counter report all on
// equals the bench with them off (pinned to the reference by bench_parity).
TEST_CASE("search_stats", "bench is unchanged with the ledger and the trace on") {
  const auto set_env = [](const char* name, const char* value) {
#ifdef _WIN32
    _putenv_s(name, value ? value : "");
#else
    if (value)
      setenv(name, value, 1);
    else
      unsetenv(name);
#endif
  };
  const SearchBenchResult off = run_search_bench();
  set_env("FORK_PRUNE_LEDGER", "64");
  set_env("FORK_ITERATION_TRACE", "1");
  set_env("FORK_STATS_REPORT", "1");
  const std::string path = "search_stats_ledger_bench.txt";
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
  set_env("FORK_PRUNE_LEDGER", nullptr);
  set_env("FORK_ITERATION_TRACE", nullptr);
  set_env("FORK_STATS_REPORT", nullptr);
  std::ifstream in(path, std::ios::binary);
  std::size_t rfp_rows = 0, futility_rows = 0, traces = 0;
  for (std::string line; std::getline(in, line);) {
    rfp_rows += line.rfind("prune_ledger rfp|", 0) == 0;
    futility_rows += line.rfind("prune_ledger futility|", 0) == 0;
    traces += line.rfind("iteration_trace ", 0) == 0;
  }
  in.close();
  std::remove(path.c_str());
  CHECK_EQ(on.nodes, off.nodes);
  CHECK_EQ(on.signature, off.signature);
  CHECK(rfp_rows > 0);
  CHECK(futility_rows > 0);
  CHECK(traces > 0);
}

// X10: with every candidate sampled, the rows match the real search's own
// counts (counters exclude the side searches): one fired RFP row per RFP
// cut, one fired futility row per futile node; fired rows meet the margin,
// unfired ones do not; and the searches equal the same searches without
// the ledger.
TEST_CASE("search_stats", "ledger rows match the real search's prunes, and the search is unchanged") {
  std::vector<TtBucket> buckets(16384);
  TransTable table;
  table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  const std::atomic<bool> stop{false};
  const auto set_ledger = [](const char* value) {
#ifdef _WIN32
    _putenv_s("FORK_PRUNE_LEDGER", value ? value : "");
#else
    if (value)
      setenv("FORK_PRUNE_LEDGER", value, 1);
    else
      unsetenv("FORK_PRUNE_LEDGER");
#endif
  };
  SearchQuota limits;
  limits.depth = 7;
  std::vector<SearchResult> plain;
  for (int i = 0; i < 3; ++i) {
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    auto searcher = std::make_unique<Searcher>(table);
    Position pos;
    CHECK(pos.set_fen(perft_suite()[i].fen));
    plain.push_back(searcher->deliberate(pos, limits, stop, nullptr, nullptr));
  }
  set_ledger("1");
  auto ledger = std::make_unique<Searcher>(table);
  set_ledger(nullptr);
  const std::string path = "search_stats_ledger_rows.txt";
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
  std::vector<SearchResult> ledgered;
  for (int i = 0; i < 3; ++i) {
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    ledger->clear_history();
    Position pos;
    CHECK(pos.set_fen(perft_suite()[i].fen));
    ledgered.push_back(ledger->deliberate(pos, limits, stop, nullptr, nullptr));
  }
  std::fflush(stderr);
#ifdef _WIN32
  _dup2(saved, _fileno(stderr));
  _close(saved);
#else
  dup2(saved, fileno(stderr));
  close(saved);
#endif
  std::fclose(sink);
  for (int i = 0; i < 3; ++i) {
    CHECK_EQ(ledgered[i].nodes, plain[i].nodes);
    CHECK_EQ(ledgered[i].best.raw(), plain[i].best.raw());
    CHECK_EQ(ledgered[i].score, plain[i].score);
    CHECK_EQ(ledgered[i].depth, plain[i].depth);
  }
  std::ifstream in(path, std::ios::binary);
  std::uint64_t rfp_fired = 0, rfp_rows = 0, futility_fired = 0, futility_rows = 0;
  for (std::string line; std::getline(in, line);) {
    if (line.rfind("prune_ledger ", 0) != 0) continue;
    std::vector<std::string> fields;
    std::istringstream text(line.substr(13));
    for (std::string field; std::getline(text, field, '|');) fields.push_back(field);
    if (fields[0] == "rfp") {
      CHECK_EQ(fields.size(), std::size_t{14});
      const int excess = std::stoi(fields[3]), margin = std::stoi(fields[5]), fired = std::stoi(fields[10]);
      CHECK_EQ(fired, excess >= margin ? 1 : 0);
      CHECK(excess >= 0);
      ++rfp_rows;
      rfp_fired += fired;
    } else {
      CHECK(fields[0] == "futility");
      CHECK_EQ(fields.size(), std::size_t{16});
      const int deficit = std::stoi(fields[3]), margin = std::stoi(fields[5]), fired = std::stoi(fields[10]);
      CHECK_EQ(fired, deficit >= margin ? 1 : 0);
      CHECK(deficit >= 0);
      ++futility_rows;
      futility_fired += fired;
    }
  }
  in.close();
  std::remove(path.c_str());
  const SearchCounters& c = ledger->counters;
  CHECK(rfp_fired > 0 && futility_fired > 0);
  CHECK_EQ(rfp_fired, c.rfp_cuts);
  CHECK_EQ(futility_fired, c.futile_nodes);
  CHECK_EQ(rfp_rows, c.ledger_rfp_candidates);
  CHECK_EQ(futility_rows, c.ledger_futility_candidates);
  CHECK_EQ(rfp_rows + futility_rows, c.ledger_rows);
  CHECK(c.ledger_side_nodes > 0);
}

// Idea 59 step 1: every computed evaluation lands once in its gap histogram
// or its infinite-window count (main search and quiescence apart), every
// reused one in the reuse histograms, and the depth bands split the main
// search's computed ones exactly.
TEST_CASE("search_stats", "idea 59 window gaps account for every evaluation") {
  std::vector<TtBucket> buckets(16384);
  TransTable table;
  table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  const std::atomic<bool> stop{false};
  auto searcher = std::make_unique<Searcher>(table);
  SearchQuota limits;
  limits.depth = 9;
  for (const PerftPosition& p : perft_suite()) {
    Position pos;
    CHECK(pos.set_fen(p.fen));
    searcher->deliberate(pos, limits, stop, nullptr, nullptr);
  }
  const SearchCounters& c = searcher->counters;
  const auto sum = [](const std::uint64_t* bins, int count) {
    std::uint64_t total = 0;
    for (int i = 0; i < count; ++i) total += bins[i];
    return total;
  };
  CHECK_EQ(sum(c.eval_gap_main_bins, GapBins) + c.eval_gap_main_infinite, c.evals_main);
  CHECK_EQ(sum(c.eval_gap_quiesce_bins, GapBins) + c.eval_gap_quiesce_infinite, c.evals_quiesce);
  CHECK_EQ(sum(c.eval_gap_main_reuse_bins, GapBins) + c.eval_gap_main_reuse_infinite, c.tt_eval_hits_main);
  CHECK_EQ(sum(c.eval_gap_quiesce_reuse_bins, GapBins) + c.eval_gap_quiesce_reuse_infinite,
           c.tt_eval_hits_quiesce);
  std::uint64_t banded = 0;
  for (int b = 0; b < GapBands; ++b) banded += sum(c.eval_gap_band_bins[b], GapBins);
  CHECK_EQ(banded, sum(c.eval_gap_main_bins, GapBins));
  CHECK_EQ(sum(c.eval_gap_band_infinite, GapBands), c.eval_gap_main_infinite);
  CHECK(c.eval_gap_main_one_sided <= sum(c.eval_gap_main_bins, GapBins));
  CHECK(c.eval_gap_quiesce_one_sided <= sum(c.eval_gap_quiesce_bins, GapBins));
  CHECK(c.eval_gap_main_bins[0] + c.eval_gap_quiesce_bins[0] > 0);  // some evaluations sit on a bound
}

}  // namespace forkeng::test
