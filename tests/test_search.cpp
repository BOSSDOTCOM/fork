// SPDX-License-Identifier: GPL-3.0-or-later

// The search (DESIGN.md §5.2, deliverables 2-4). Positions other than the
// perft suite are constructed for Fork; the facts each test relies on (mate
// in N, no mate in 1, legal FEN) are checked with python-chess by
// tools/check_search_positions.py.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <iostream>
#include <limits>
#include <memory>
#include <thread>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "eval/eval.hpp"
#include "harness.hpp"
#include "search/search_bench.hpp"
#include "search/searcher.hpp"
#include "search/see.hpp"
#include "search/time_budget.hpp"
#include "suite.hpp"
#include "uci/go_limits.hpp"
#include "uci/session.hpp"
#include "uci/tokens.hpp"

namespace forkeng::test {

namespace {

// The draw rules both references apply before anything else: 0 for a draw,
// mated_score for mate on the 100th half-move, ScoreNone otherwise.
int reference_draw(Position& pos, int ply) {
  if (pos.repetition_count() >= 2 || pos.insufficient_material()) return 0;
  if (pos.fifty_move_reached()) {
    if (!pos.in_check()) return 0;
    MoveList list;
    generate<GenMode::Legal>(pos, list);
    return list.size() ? 0 : mated_score(ply);
  }
  return ScoreNone;
}

// A textbook fail-hard alpha-beta quiescence search with the search's move
// set: every evasion in check (mated if none), else stand pat or any capture
// or queen promotion, skipping (with `see_filter`) captures that lose by SEE.
// Called with the full window it returns the exact minimax value; plain
// minimax over every capture sequence is far too slow to use.
int reference_quiesce(Position& pos, int ply, int alpha, int beta, bool see_filter) {
  if (const int d = reference_draw(pos, ply); d != ScoreNone) return d;
  const bool in_check = pos.in_check();
  if (ply >= MaxPly) return in_check ? 0 : static_eval(pos);
  MoveList list;
  generate<GenMode::Legal>(pos, list);
  if (in_check && list.size() == 0) return mated_score(ply);
  if (!in_check) {
    const int stand = static_eval(pos);
    if (stand >= beta) return beta;
    alpha = std::max(alpha, stand);
  }
  for (Move m : list) {
    if (!in_check) {
      if (!m.is_capture() && !m.is_promotion()) continue;
      if (m.is_promotion() && m.promo_type() != Queen) continue;
      if (see_filter && m.is_capture() && see_value(pos, m) < 0) continue;
    }
    pos.make(m);
    const int score = -reference_quiesce(pos, ply + 1, -beta, -alpha, see_filter);
    pos.unmake(m);
    if (score >= beta) return beta;
    alpha = std::max(alpha, score);
  }
  return alpha;
}

// A textbook fail-hard alpha-beta with the search's own rules (draws,
// 50-move rule with mate first, ply limit, the quiescence search above at the
// horizon) and nothing else: no PVS, no aspiration, no TT, no move ordering.
// The oracle for the root score, called with the full window (tests must not
// compare the search with itself).
int reference_alphabeta(Position& pos, int depth, int ply, int alpha, int beta, bool see_filter) {
  const bool in_check = pos.in_check();
  if (ply > 0) {
    if (depth <= 0) return reference_quiesce(pos, ply, alpha, beta, see_filter);
    if (const int d = reference_draw(pos, ply); d != ScoreNone) return d;
    if (ply >= MaxPly) return in_check ? 0 : static_eval(pos);
  }
  MoveList list;
  generate<GenMode::Legal>(pos, list);
  if (list.size() == 0) return in_check ? mated_score(ply) : 0;
  for (Move m : list) {
    pos.make(m);
    const int score = -reference_alphabeta(pos, depth - 1, ply + 1, -beta, -alpha, see_filter);
    pos.unmake(m);
    if (score >= beta) return beta;
    alpha = std::max(alpha, score);
  }
  return alpha;
}

int reference_minimax(Position& pos, int depth, int ply, bool see_filter = true) {
  return reference_alphabeta(pos, depth, ply, -ScoreInfinite, ScoreInfinite, see_filter);
}

// Whether the full-width tree a search of `depth` plies can visit (every
// legal move, then the quiescence search's moves: captures and queen
// promotions, every evasion in check) holds a position that repeats one on
// its path. The TT ignores the path, so where a repetition draw is in the
// tree an entry can carry it to a path without that repetition, and TT
// cutoffs need not equal minimax (graph-history interaction; DESIGN.md
// §5.3, B0's tests). The exact tests check this first. Small trees only.
bool repetition_in_tree(Position& pos, int depth, int ply = 0) {
  if (ply > 0 && pos.repetition_count() >= 2) return true;
  if (ply >= MaxPly || pos.insufficient_material() || pos.fifty_move_reached()) return false;
  const bool in_check = pos.in_check();
  MoveList list;
  generate<GenMode::Legal>(pos, list);
  for (Move m : list) {
    if (depth <= 0 && !in_check &&
        (!(m.is_capture() || m.is_promotion()) || (m.is_promotion() && m.promo_type() != Queen)))
      continue;
    pos.make(m);
    const bool found = repetition_in_tree(pos, depth - 1, ply + 1);
    pos.unmake(m);
    if (found) return true;
  }
  return false;
}

// A 1 MB table of plain memory for the tests' searches.
struct TestHash {
  std::vector<TtBucket> buckets = std::vector<TtBucket>(16384);
  TransTable table;
  TestHash() {
    table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  }
  void clear() { std::fill(buckets.begin(), buckets.end(), TtBucket{}); }
};

// Switches for a search that must equal minimax: TT cutoffs only at their
// own depth, and no pruning or reductions (they are not exact).
SearchSwitches exact_switches() {
  SearchSwitches s;
  s.tt_exact_depth = true;
  s.use_rfp = s.use_nmp = s.use_lmr = s.use_lmp = s.use_futility = s.use_see_prune = false;
  return s;
}

struct Fixture {
  TestHash store;
  std::unique_ptr<Searcher> searcher = std::make_unique<Searcher>(store.table);
  std::atomic<bool> stop{false};

  SearchResult search(Position& pos, const SearchQuota& limits) {
    return searcher->deliberate(pos, limits, stop, nullptr, nullptr);
  }
  SearchResult search(std::string_view fen, int depth) {
    Position pos;
    const bool ok = pos.set_fen(fen);
    CHECK_MSG(ok, fen);
    SearchQuota limits;
    limits.depth = depth;
    return search(pos, limits);
  }
};

// Positions for the oracle test: the perft suite and the ends of random
// games from the start position (fixed seed).
std::vector<Position> oracle_positions() {
  std::vector<Position> out;
  for (const PerftPosition& p : perft_suite()) {
    Position pos;
    CHECK(pos.set_fen(p.fen));
    out.push_back(pos);
  }
  std::uint64_t seed = 20261024;
  while (out.size() < 18) {
    Position pos;
    const int plies = 6 + static_cast<int>(splitmix_next(seed) % 40);
    for (int i = 0; i < plies; ++i) {
      MoveList list;
      generate<GenMode::Legal>(pos, list);
      if (list.size() == 0) break;
      pos.make(list[splitmix_next(seed) % list.size()]);
    }
    MoveList list;
    generate<GenMode::Legal>(pos, list);
    if (list.size() > 0) out.push_back(Position(pos));
  }
  return out;
}

}  // namespace

// The search bench begins with the CPW perft suite, retyped in
// src/search/search_bench.cpp; tests/suite.hpp holds the copy checked
// against chessprogramming.org with its published counts (audit-1 A9 F-10:
// every retyped FEN is a risk, non-negotiable 1).
TEST_CASE("search", "the search bench's perft-suite FENs equal the cited suite") {
  const auto& suite = perft_suite();
  CHECK(search_bench_fens().size() >= suite.size());
  for (std::size_t i = 0; i < suite.size() && i < search_bench_fens().size(); ++i)
    CHECK_MSG(search_bench_fens()[i] == suite[i].fen, suite[i].name << ": " << search_bench_fens()[i]);
}

TEST_CASE("search",
          "root score equals plain minimax: PVS, aspiration, mate distance pruning, TT on and off") {
  Fixture fx;
  // With the quiescence search the reference grows fast: depth 3 (2 in debug
  // builds), and depth 1 for the variant without the SEE filter, whose
  // reference searches every capture sequence. Aspiration windows start at
  // depth 4, so the endgame test below (depth 6) is the one that checks them.
  const int depth = Optimized ? 3 : 2;
  int compared = 0;
  for (Position& pos : oracle_positions()) {
    const int expected = reference_minimax(pos, depth, 0);
    const int expected_without_see = reference_minimax(pos, 1, 0, false);
    // The TT cuts only at its entry's own depth (tt_exact_depth), so every
    // variant must equal minimax; variant 4 switches the TT off, variant 5
    // the quiescence search's SEE filter.
    for (int variant = 0; variant < 6; ++variant) {
      fx.store.clear();
      fx.searcher->switches = exact_switches();
      fx.searcher->switches.use_pvs = variant != 1;
      fx.searcher->switches.use_aspiration = variant != 2;
      fx.searcher->switches.use_mate_distance = variant != 3;
      fx.searcher->switches.use_tt = variant != 4;
      fx.searcher->switches.use_see_quiesce = variant != 5;
      SearchQuota limits;
      limits.depth = variant == 5 ? 1 : depth;
      const SearchResult r = fx.search(pos, limits);
      const int want = variant == 5 ? expected_without_see : expected;
      CHECK_MSG(r.score == want, pos.fen() << " variant " << variant << ": " << r.score << " vs " << want);
      CHECK_EQ(r.depth, variant == 5 ? 1 : depth);
      ++compared;
    }
  }
  CHECK(compared >= 108);
}

// Endgames transpose a lot, so the TT really cuts here (counted below).
// Exactness is claimed only where no repetition is in reach (a path-blind
// TT may carry a repetition draw across paths: the next test case), and the
// test checks that first (owner, 2026-10-29). Constructed positions:
// - four plain endgames at depth 3: from depth 4 each holds a repetition
//   (both kings can step out and back);
// - four locked ones at depth 6 (5 in debug builds): one side's king is
//   walled in by a pawn cluster with no capture on either side (black: Ka5,
//   b6 and b4 against a4, b3 and b5; or its colour mirror), so that side
//   can only push its free pawns, every one of its moves is irreversible,
//   and no position can repeat; python-chess found none to depth 7 (the
//   check below repeats it).
namespace {

struct DepthCase {
  std::string_view fen;
  int depth;
};
std::vector<DepthCase> repetition_free_cases() {
  std::vector<DepthCase> out;
  for (std::string_view fen : {"8/2k5/8/1p6/1P6/8/5K2/8 w - - 0 1", "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",
                               "8/8/3k4/8/8/3K4/8/R7 w - - 0 1", "8/5pk1/8/8/8/8/5PK1/8 b - - 0 1"})
    out.push_back({fen, 3});
  for (std::string_view fen :
       {"8/6pp/1p6/kP6/Pp6/1P6/8/3K4 w - - 0 1", "8/6pp/1p6/kP6/Pp6/1P6/8/3K4 b - - 0 1",
        "3k4/8/1p6/pP6/Kp6/1P6/6PP/8 w - - 0 1", "8/6pp/1p6/kP6/Pp6/1P6/8/3K3R w - - 0 1"})
    out.push_back({fen, Optimized ? 6 : 5});
  return out;
}

}  // namespace

TEST_CASE("search",
          "TT cutoffs at exact depth equal plain minimax on small endgames, no repetition in reach") {
  Fixture fx;
  std::uint64_t first_nodes = 0, again_nodes = 0;
  for (const DepthCase& c : repetition_free_cases()) {
    const std::string_view fen = c.fen;
    const int depth = c.depth;
    Position pos;
    CHECK(pos.set_fen(fen));
    CHECK_MSG(!repetition_in_tree(pos, depth), fen << ": a repetition fits in depth " << depth);
    const int expected = reference_minimax(pos, depth, 0);
    SearchQuota limits;
    limits.depth = depth;
    for (bool tt : {false, true}) {
      fx.store.clear();
      fx.searcher->switches = exact_switches();
      fx.searcher->switches.use_tt = tt;
      const SearchResult r = fx.search(pos, limits);
      CHECK_MSG(r.score == expected, fen << " tt " << tt << ": " << r.score << " vs " << expected);
    }
    // The TT really cuts: searching again over the filled table still equals
    // minimax, and over all the positions takes fewer nodes (its exact-depth
    // entries cut, at non-PV nodes only, so not in every tiny tree). Fewer
    // nodes than without a TT is not a given at depth 3, where the TT's move
    // ordering can cost more than its few cutoffs save.
    fx.store.clear();
    const SearchResult first = fx.search(pos, limits);
    const SearchResult again = fx.search(pos, limits);
    CHECK_MSG(again.score == expected, fen << " again: " << again.score << " vs " << expected);
    first_nodes += first.nodes;
    again_nodes += again.nodes;
  }
  CHECK_MSG(again_nodes < first_nodes,
            again_nodes << " nodes over the filled TT, " << first_nodes << " before");
}

// The known path-dependent case, tolerated (owner, 2026-10-29): in KRK at
// depth 6 a repetition fits in the tree, and a score the TT stored on a path
// where the defending king repeated (a draw) can cut on another path, so the
// root may differ a little from minimax (with B0, 554 against 558). That is
// graph-history interaction, the usual price of a path-blind TT; Fork accepts
// it. Without the TT the search must still equal minimax exactly; with it,
// the score must stay near minimax and keep the win.
TEST_CASE("search", "known: with a repetition in reach, TT cutoffs may differ slightly from minimax") {
  Fixture fx;
  const std::string_view fen = "8/8/3k4/8/8/3K4/8/R7 w - - 0 1";
  const int depth = Optimized ? 6 : 4;
  Position pos;
  CHECK(pos.set_fen(fen));
  CHECK(repetition_in_tree(pos, depth));
  const int expected = reference_minimax(pos, depth, 0);
  for (bool tt : {false, true}) {
    fx.store.clear();
    fx.searcher->clear_history();
    fx.searcher->switches = exact_switches();
    fx.searcher->switches.use_tt = tt;
    SearchQuota limits;
    limits.depth = depth;
    const SearchResult r = fx.search(pos, limits);
    if (!tt)
      CHECK_MSG(r.score == expected, "no TT: " << r.score << " vs " << expected);
    else
      CHECK_MSG(std::abs(r.score - expected) <= 50 && r.score > 0 && !is_mate_score(r.score),
                "TT: " << r.score << " vs " << expected);
  }
}

// Audit-1 Q-7: zero-window searches against a zero-window reference. The
// root-score oracle above runs full windows, where the TT's bound checks,
// the bound stored by a PV node that fails low and mate distance pruning
// never decide: a TT upper bound cutting on the wrong side (mutant M12) and a
// mate-distance beta one ply too tight (M14) were caught only by bench
// parity (M14 is caught here, M12 by the next case). Here, with one TT shared
// as in a real search (a full-window search first, then probes at every
// depth), every probe at beta must fail high exactly when the reference
// (fail-hard, window [beta - 1, beta]) does, and its fail-soft score must be
// a valid bound of the exact value. Betas lie around the exact value and, in
// the mate positions (test_search.cpp's mates, checked by
// tools/check_search_positions.py), on the mate scores, where mate distance
// pruning binds.
TEST_CASE("search",
          "zero-window probes agree with a zero-window reference, mate bands included (TT shared)") {
  Fixture fx;
  struct Probed {
    std::string_view fen;
    int depth;
    bool small = true;  // small enough to check for repetitions in full width
  };
  std::vector<Probed> positions;
  for (const PerftPosition& p : perft_suite()) positions.push_back({p.fen, Optimized ? 3 : 2, false});
  // The TT endgames above (the locked ones to depth 6, 5 in debug builds, so
  // the full-window search that fills the TT uses aspiration windows, from
  // depth 5) and the mates, at depth 3: from depth 4 each of those holds a
  // repetition, where exactness is not claimed (the TT case above). The perft
  // positions are too large for the full-width check (every capture
  // sequence) and are not checked for repetitions.
  for (const DepthCase& c : repetition_free_cases()) positions.push_back({c.fen, c.depth});
  for (std::string_view fen : {"6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "k7/8/2K5/8/8/8/8/7R w - - 0 1",
                               "6k1/5ppp/8/8/8/8/8/R5K1 b - - 0 1"})
    positions.push_back({fen, 3});
  int probes = 0, mate_band = 0;
  for (const Probed& p : positions) {
    Position pos;
    CHECK(pos.set_fen(p.fen));
    if (p.small)
      CHECK_MSG(!repetition_in_tree(pos, p.depth), p.fen << ": a repetition fits in depth " << p.depth);
    fx.store.clear();
    fx.searcher->clear_history();
    fx.searcher->switches = exact_switches();
    SearchQuota limits;
    limits.depth = p.depth;
    const int full = fx.search(pos, limits).score;  // fills the TT with PV and non-PV entries
    for (int d = 1; d <= p.depth; ++d) {
      const int value = reference_minimax(pos, d, 0);
      if (d == p.depth) CHECK_MSG(full == value, p.fen << ": full window " << full << " vs " << value);
      std::vector<int> betas;
      for (int offset : {-300, -40, -1, 0, 1, 40, 300}) betas.push_back(value + offset);
      for (int n = 1; n <= 5; ++n) {
        betas.push_back(mate_score(n));
        betas.push_back(mated_score(n));
        betas.push_back(mated_score(n) + 1);
      }
      for (int beta : betas) {
        beta = std::clamp(beta, -ScoreInfinite + 1, ScoreInfinite);
        const int s = fx.searcher->probe_zero_window(pos, beta, d, fx.stop);
        const int ref = reference_alphabeta(pos, d, 0, beta - 1, beta, true);
        ++probes;
        mate_band += is_mate_score(beta);
        CHECK_MSG((s >= beta) == (ref >= beta),
                  p.fen << " depth " << d << " beta " << beta << ": probe " << s << ", reference " << ref);
        CHECK_MSG(s >= beta ? value >= s : value <= s,
                  p.fen << " depth " << d << " beta " << beta << ": fail-soft " << s << ", exact " << value);
      }
    }
  }
  CHECK(probes > 0 && mate_band > 0);
}

// Audit-1 Q-10 (DESIGN.md §5.2's tiny-hash stress test): every search
// fixture used 16,384 buckets, so the TT's replacement under heavy pressure
// was never searched through. With 1, 2 and 16 buckets: the exact-depth
// search still equals minimax, and the release search plays a legal move
// with a score inside the score bands, on the oracle positions.
TEST_CASE("search",
          "a tiny TT (1 to 16 buckets): still minimax at exact depth, legal moves, scores in band") {
  const int depth = Optimized ? 3 : 2;
  std::vector<Position> positions = oracle_positions();
  std::vector<int> minimax;
  for (Position& pos : positions) minimax.push_back(reference_minimax(pos, depth, 0));
  for (const std::size_t count : {std::size_t{1}, std::size_t{2}, std::size_t{16}}) {
    std::vector<TtBucket> buckets(count);
    TransTable table;
    table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
    auto searcher = std::make_unique<Searcher>(table);
    const std::atomic<bool> stop{false};
    for (std::size_t i = 0; i < positions.size(); ++i) {
      Position& pos = positions[i];
      const int expected = minimax[i];
      searcher->switches = exact_switches();
      SearchQuota limits;
      limits.depth = depth;
      const SearchResult exact = searcher->deliberate(pos, limits, stop, nullptr, nullptr);
      CHECK_MSG(exact.score == expected,
                pos.fen() << " with " << count << " buckets: " << exact.score << " vs " << expected);
      searcher->switches = SearchSwitches{};
      limits.depth = Optimized ? 8 : 5;
      const SearchResult r = searcher->deliberate(pos, limits, stop, nullptr, nullptr);
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      CHECK_MSG(legal.contains(r.best), pos.fen() << " with " << count << " buckets: best move not legal");
      CHECK_MSG(std::abs(r.score) <= MateScore && (is_tb_or_mate(r.score) || std::abs(r.score) <= EvalLimit),
                pos.fen() << " with " << count << " buckets: score " << r.score);
    }
  }
}

// Audit-1 V-5: the search stack's frame stays small (review 2, claim (e):
// shrunk from 4 KB to 2,664 B; 2,672 B measured with clang on 2026-10-27).
// A guard, so a growing frame is a decision, not an accident.
static_assert(sizeof(PlyFrame) <= 2688,
              "PlyFrame grew past 2,688 bytes (DESIGN.md §5.2, review 2 claim (e))");

// Audit-1 Q-7: the TT's bound checks at their edge (mutant M12: an upper
// bound cut when s <= beta instead of s <= alpha). An upper bound u, stored
// for the probed position at the probe's depth, is a true bound here (the
// exact value plus 50): a probe whose alpha equals u must cut and return u;
// a probe whose beta equals u must not cut (the value is below it) and must
// fail low.
TEST_CASE("search", "a TT upper bound cuts when it is at or below alpha, never at beta") {
  Fixture fx;
  for (std::string_view fen : {"8/8/3k4/8/8/3K4/8/R7 w - - 0 1",
                               "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"}) {
    Position pos;
    CHECK(pos.set_fen(fen));
    const int depth = 2;
    const int value = reference_minimax(pos, depth, 0);
    const int upper = value + 50;
    fx.searcher->switches = exact_switches();
    for (int beta : {upper + 1, upper}) {
      fx.store.clear();
      fx.store.table.deposit(pos.key(), NoMove, upper, ScoreNone, depth, TtBound::Upper, false);
      const int s = fx.searcher->probe_zero_window(pos, beta, depth, fx.stop);
      if (beta == upper + 1)
        CHECK_MSG(s == upper, fen << ": alpha at the bound: " << s << " (bound " << upper << ")");
      else
        CHECK_MSG(s < beta,
                  fen << ": beta at the bound: " << s << " (bound " << upper << ", value " << value << ")");
    }
  }
}

// Audit-1 Q-7: the null move's zugzwang guard (no null move for a side with
// only pawns: pawn endings are where passing is most often best). Dropping
// it was caught only by bench parity (mutant M18b). Two constructed king and
// pawn endings where the depth-9 search with the guard keeps the tables'
// result and the search without it does not (found by comparing the two
// builds over random pawn endings). The moves' results are from the lichess
// tablebase API (https://tablebase.lichess.ovh/standard?fen=..., fetched
// 2026-10-27; Syzygy WDL, the fifty-move rule counted):
// - 8/1p6/8/6k1/8/8/4P3/7K b: a win for Black only by b7b5 (b7b6 and every
//   king move draw);
// - 8/3p4/8/6P1/3k3p/5K2/8/8 b: a draw only by d4d5 or d4e5 (every other
//   move loses).
TEST_CASE("search", "no null move without pieces: two pawn endings keep their tablebase result") {
  Fixture fx;
  Position pos;
  SearchResult r = fx.search("8/1p6/8/6k1/8/8/4P3/7K b - - 0 1", 9);
  CHECK(pos.set_fen("8/1p6/8/6k1/8/8/4P3/7K b - - 0 1"));
  CHECK_MSG(pos.move_to_uci(r.best) == "b7b5",
            "played " << pos.move_to_uci(r.best) << " (score " << r.score << ")");
  fx.store.clear();
  fx.searcher->clear_history();
  r = fx.search("8/3p4/8/6P1/3k3p/5K2/8/8 b - - 0 1", 9);
  CHECK(pos.set_fen("8/3p4/8/6P1/3k3p/5K2/8/8 b - - 0 1"));
  const std::string played = pos.move_to_uci(r.best);
  CHECK_MSG(played == "d4d5" || played == "d4e5", "played " << played << " (score " << r.score << ")");
}

// DESIGN.md §5.2 deliverable 4: quiescence values on constructed exchanges,
// against python-chess. tools/check_search_positions.py computes each
// position's material-only value of a depth-1 search ending in a capture
// search, and the moves reaching it (python-chess generates the moves; no
// Fork code is involved). Fork must play one of those moves (or, where every
// quiet move ties, avoid the losing capture) and, with the bootstrap
// evaluation, score within 100 cp of the material value: its placement terms
// make the rest.
//
// A network may prefer a quiet move to the material gain, so where a
// position is in Syzygy range its move is checked against the tablebase
// result instead: it must play a move that keeps it (owner, 2026-10-29). In
// the two-rook position every one of White's 16 legal moves keeps the win
// (lichess tablebase API, 2026-10-29; B0r1 plays d2b2, DTM 41 against d2d5's
// 31), so only the bootstrap evaluation's d2d5 is checked there. The K+R+P v
// K+R position below separates the moves: d2d5, a6a7, d2a2 and d2h2 keep the
// win; d2b2, d2c2, d2d1, d2e2, d2f2, d2g2, e1d1 and e1e2 draw; d2d3, d2d4,
// e1f1 and e1f2 lose (Syzygy 3-4-5 through python-chess's chess.syzygy, and
// the lichess tablebase API,
// https://tablebase.lichess.ovh/standard?fen=7k/8/P7/3r4/8/8/3R4/4K3_w_-_-_0_1,
// agreeing, 2026-10-29).
TEST_CASE("search", "quiescence values on constructed exchanges match python-chess") {
  Fixture fx;
  struct Exchange {
    std::string_view fen;
    int material;           // python-chess value, centipawns for the side to move
    std::string_view best;  // the only best move, or "" if many quiet moves tie
    std::string_view avoid;
    std::string_view keeps_result = "";  // with a network: the moves that keep the tablebase result
    bool best_bootstrap_only = false;    // with a network: every move keeps the result, nothing to check
  };
  for (const Exchange& x :
       {Exchange{"4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1", 100, "e4d5", ""},
        Exchange{"4k3/8/3p4/4r3/8/5N2/8/4K3 w - - 0 1", -100, "f3e5", ""},
        Exchange{"4k3/8/2p5/3p4/8/8/3Q4/4K3 w - - 0 1", 700, "", "d2d5"},
        Exchange{"4k3/1P6/8/8/8/8/8/4K3 w - - 0 1", 900, "b7b8q", ""},
        Exchange{"3rk3/8/8/3p4/8/8/3R4/3RK3 w - - 0 1", 500, "d2d5", "", "", true},
        Exchange{"7k/8/P7/3r4/8/8/3R4/4K3 w - - 0 1", 600, "d2d5", "", "a6a7 d2a2 d2d5 d2h2"}}) {
    fx.store.clear();
    Position pos;
    CHECK(pos.set_fen(x.fen));
    const SearchResult r = fx.search(x.fen, 1);
    const std::string played = pos.move_to_uci(r.best);
#if defined(FORK_EVAL_BOOTSTRAP)
    const bool network = false;
#else
    const bool network = true;
#endif
    if (network && !x.keeps_result.empty()) {
      const std::string list = " " + std::string(x.keeps_result) + " ";
      CHECK_MSG(list.find(" " + played + " ") != std::string::npos,
                x.fen << ": played " << played << ", which changes the tablebase result");
    } else if (!x.best.empty() && !(network && x.best_bootstrap_only)) {
      CHECK_MSG(played == x.best, x.fen << ": played " << played);
    }
    if (!x.avoid.empty()) CHECK_MSG(played != x.avoid, x.fen << ": played " << played);
#if defined(FORK_EVAL_BOOTSTRAP)
    // The tolerance is the bootstrap evaluation's (its 1/3/3/5/9 material
    // plus placement terms); a network values material its own way (B0
    // scores the fresh queen 763), so only the moves are checked there.
    CHECK_MSG(std::abs(r.score - x.material) <= 100,
              x.fen << ": score " << r.score << ", material " << x.material);
#endif
  }
}

TEST_CASE("search", "finds mate in 1 and mate in 2, and stops early on go mate") {
  Fixture fx;
  // Back-rank mate in 1: Ra8#.
  SearchResult r = fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 3);
  CHECK_EQ(r.score, mate_score(1));
  Position pos;
  CHECK(pos.set_fen("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"));
  CHECK_EQ(pos.move_to_uci(r.best), std::string("a1a8"));
  // K+R v K, mate in 2 (and not in 1).
  r = fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 4);
  CHECK_EQ(r.score, mate_score(3));
  // go mate 2 stops once the mate is found (depth 3: the quiescence search
  // sees that the king has no evasion), well before depth 20.
  CHECK(pos.set_fen("k7/8/2K5/8/8/8/8/7R w - - 0 1"));
  SearchQuota limits;
  limits.depth = 20;
  limits.mate_moves = 2;
  r = fx.search(pos, limits);
  CHECK_EQ(r.score, mate_score(3));
  CHECK_EQ(r.depth, 3);
}

TEST_CASE("search", "draws: 50-move rule (mate first), repetition") {
  Fixture fx;
  // Halfmove clock 99: Ra8# still mates on the 100th half-move...
  CHECK_EQ(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 99 80", 3).score, mate_score(1));
  // ...but with no mate in 1 every move ends in a draw by the 50-move rule.
  CHECK_EQ(fx.search("7k/8/8/8/8/8/8/R5K1 w - - 99 80", 3).score, 0);
  CHECK(fx.search("7k/8/8/8/8/8/8/R5K1 w - - 0 80", 3).score > 300);
  // 1. e4 Nf6 2. Nf3 Ng8 3. Ng1: ...Nf6 repeats the position after 1...Nf6.
  // Black starts without its queen, so the evaluation is far from 0 with any
  // evaluator (B0r2 scores the full-material position at exactly 0;
  // python-chess confirms the line legal and ...Nf6 a repetition).
  Position pos;
  CHECK(pos.set_fen("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"));
  for (const char* uci : {"e2e4", "g8f6", "g1f3", "f6g8", "f3g1"}) pos.make(pos.parse_uci(uci));
  SearchQuota limits;
  limits.depth = 1;
  limits.restrict_to.add(pos.parse_uci("g8f6"));
  const SearchResult r = fx.search(pos, limits);
  CHECK_EQ(pos.move_to_uci(r.best), std::string("g8f6"));
  CHECK_EQ(r.score, 0);
  CHECK(static_eval(pos) < -300);  // so the 0 is the draw, not the evaluation
}

// Audit-1 Q-8: the quiescence search's own "mate on the 100th half-move" rule.
// The case above searches to depth 3, so the mate is seen by the main search;
// scoring it a draw in the quiescence search passed every test (mutant M15).
// At depth 1 the mated child is a quiescence node.
TEST_CASE("search", "draws: mate on the 100th half-move is found at a quiescence node") {
  Fixture fx;
  CHECK_EQ(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 99 80", 1).score, mate_score(1));
}

TEST_CASE("search", "limits: nodes, depth, searchmoves; a preset stop still returns a legal move") {
  Fixture fx;
  Position pos;
  SearchQuota limits;
  limits.nodes = 5000;
  SearchResult r = fx.search(pos, limits);
  CHECK_EQ(r.nodes, 5000u);
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  CHECK(legal.contains(r.best));

  limits = SearchQuota{};
  limits.depth = 2;
  limits.restrict_to.add(pos.parse_uci("a2a3"));
  limits.restrict_to.add(pos.parse_uci("h2h3"));
  r = fx.search(pos, limits);
  CHECK(r.best == pos.parse_uci("a2a3") || r.best == pos.parse_uci("h2h3"));
  CHECK_EQ(r.depth, 2);

  fx.stop = true;
  limits = SearchQuota{};
  r = fx.search(pos, limits);
  CHECK(legal.contains(r.best));
  fx.stop = false;
}

TEST_CASE("search", "no legal move: mate and stalemate") {
  Fixture fx;
  // Fool's mate: White is mated.
  SearchResult r = fx.search("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3", 5);
  CHECK(r.best.is_none());
  CHECK_EQ(r.score, mated_score(0));
  // Black to move, stalemated.
  r = fx.search("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", 5);
  CHECK(r.best.is_none());
  CHECK_EQ(r.score, 0);
}

TEST_CASE("search", "the same search twice gives the same nodes, move and score") {
  Fixture fx;
  const SearchResult a = fx.search("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 4);
  fx.store.clear();  // the same TT contents too
  // and the same history, which persists between searches (searcher.hpp).
  // Without this the second search started from the first one's history;
  // the node counts still agreed with the bootstrap evaluation and B0, not
  // with B0r1 (5631 vs 5610).
  fx.searcher->clear_history();
  const SearchResult b = fx.search("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 4);
  CHECK_EQ(a.nodes, b.nodes);
  CHECK(a.best == b.best);
  CHECK_EQ(a.score, b.score);
}

TEST_CASE("time_budget", "movetime, sudden death, increment, movestogo, extreme values") {
  ClockInput c;
  c.movetime = 1000;
  c.overhead_ms = 100;
  TimeBudget t = plan_time(c);
  CHECK_EQ(t.soft_ms, 900);
  CHECK_EQ(t.hard_ms, 900);
  // Owner, 2026-10-25: the overhead never takes more than half of a movetime
  // (it used to leave 1 ms for any movetime of 100 ms or less).
  for (const auto& [movetime, expected] : {std::pair<std::int64_t, std::int64_t>{50, 25},
                                           {100, 50},
                                           {150, 75},
                                           {200, 100},
                                           {201, 101},
                                           {1, 1},
                                           {0, 1},
                                           {-20, 1}}) {
    c.movetime = movetime;
    t = plan_time(c);
    CHECK_MSG(t.soft_ms == expected && t.hard_ms == expected, "movetime " << movetime << ": " << t.soft_ms);
  }
  c.movetime = 50;
  c.overhead_ms = 0;
  CHECK_EQ(plan_time(c).hard_ms, 50);  // no overhead: the whole movetime
  c.overhead_ms = 100;

  c = ClockInput{};
  CHECK_EQ(plan_time(c).soft_ms, -1);  // no clock: no time limit
  CHECK_EQ(plan_time(c).hard_ms, -1);

  for (std::int64_t remaining :
       {std::int64_t{-5000}, std::int64_t{0}, std::int64_t{1}, std::int64_t{50}, std::int64_t{1000},
        std::int64_t{60000}, std::int64_t{1800000}, std::int64_t{9223372036854775807}}) {
    for (std::int64_t inc : {std::int64_t{0}, std::int64_t{100}, std::int64_t{3000}, std::int64_t{-10},
                             std::int64_t{9223372036854775807}}) {
      for (std::int64_t mtg : {std::int64_t{0}, std::int64_t{1}, std::int64_t{40}, std::int64_t{1000}}) {
        c = ClockInput{};
        c.remaining_ms = remaining;
        c.increment_ms = inc;
        if (mtg) c.movestogo = mtg;
        c.overhead_ms = 100;
        t = plan_time(c);
        CHECK_MSG(t.soft_ms >= 1 && t.soft_ms <= t.hard_ms, remaining << " " << inc << " " << mtg);
        // The hard limit never reaches into the overhead or the last tenth.
        const std::int64_t available =
            std::max<std::int64_t>(1, std::min(remaining, std::int64_t{1} << 40) - 100);
        CHECK_MSG(t.hard_ms <= std::max<std::int64_t>(1, available - available / 10),
                  remaining << " " << inc);
      }
    }
  }
  // 30 minutes + 3 s (TCEC Swiss): a sane share, well under a tenth.
  c = ClockInput{};
  c.remaining_ms = 1800000;
  c.increment_ms = 3000;
  c.overhead_ms = 100;
  t = plan_time(c);
  CHECK(t.soft_ms > 30000 && t.soft_ms < 180000);
}

}  // namespace forkeng::test

namespace forkeng::test {

// Deliverable 8 (first external review, claim (b)): three quarters of the
// increment, multiplied before dividing, so small increments count exactly.
TEST_CASE("time_budget", "the increment adds exactly three quarters of itself, small ones included") {
  ClockInput base;
  base.remaining_ms = 600000;  // ten minutes: the cap never binds
  base.overhead_ms = 100;
  const std::int64_t without = plan_time(base).soft_ms;
  for (std::int64_t inc = 1; inc <= 40; ++inc) {
    ClockInput c = base;
    c.increment_ms = inc;
    CHECK_MSG(plan_time(c).soft_ms - without == inc * 3 / 4, "increment " << inc << " ms");
  }
}

// Deliverable 8, variant B2: one more Move Overhead of reserve inside the
// danger zone (less than two overheads plus an increment left), and only a
// tenth of the clock outside it. Literal budgets (audit-1 Q-11: this case
// recomputed the zone with the implementation's own expressions and checked
// an upper bound only, so `<` turned `<=` at the zone's edge passed). Each
// value comes from a separate restatement of the rule in
// tools/check_search_positions.py, not from this code (overhead 100, AssumedMovesLeft 30,
// ReserveDivisor 10, HardOverSoft 4): available = clock - 100; reserve a
// tenth, or max(a tenth, 100) in the zone; cap = available - reserve; share =
// available / 30 + 3/4 of the increment; hard = min(share, cap / 4) x 4.
// 379 and 380 ms with an 80 ms increment straddle the zone's edge
// (available 279 < 280, and 280): there the cap decides, hard 176 and 252.
TEST_CASE("time_budget", "an extra overhead of reserve only in the danger zone") {
  struct Budget {
    std::int64_t remaining, inc, soft, hard;
  };
  for (const Budget& b : {Budget{150, 0, 1, 1},     Budget{150, 20, 1, 1},     Budget{150, 80, 1, 1},
                          Budget{250, 0, 5, 20},    Budget{250, 20, 20, 48},   Budget{250, 80, 42, 48},
                          Budget{300, 0, 6, 24},    Budget{300, 20, 21, 84},   Budget{300, 80, 66, 100},
                          Budget{319, 0, 7, 28},    Budget{319, 20, 22, 88},   Budget{319, 80, 67, 116},
                          Budget{320, 0, 7, 28},    Budget{320, 20, 22, 88},   Budget{320, 80, 67, 120},
                          Budget{379, 0, 9, 36},    Budget{379, 20, 24, 96},   Budget{379, 80, 69, 176},
                          Budget{380, 0, 9, 36},    Budget{380, 20, 24, 96},   Budget{380, 80, 69, 252},
                          Budget{500, 0, 13, 52},   Budget{500, 20, 28, 112},  Budget{500, 80, 73, 292},
                          Budget{1000, 0, 30, 120}, Budget{1000, 20, 45, 180}, Budget{1000, 80, 90, 360},
                          Budget{2000, 0, 63, 252}, Budget{2000, 20, 78, 312}, Budget{2000, 80, 123, 492}}) {
    ClockInput c;
    c.remaining_ms = b.remaining;
    c.increment_ms = b.inc;
    c.overhead_ms = 100;
    const TimeBudget t = plan_time(c);
    CHECK_MSG(t.soft_ms == b.soft && t.hard_ms == b.hard,
              b.remaining << " ms + " << b.inc << ": soft " << t.soft_ms << " hard " << t.hard_ms << ", want "
                          << b.soft << " and " << b.hard);
  }
}

// Audit-1 Q-4 and Q-5: what a go turns into (quota_for_go, the session's
// assembly of the clock arguments, Move Overhead and the other limits). The
// side to move's own increment (the opponent's passed every test, mutant
// M40), the Move Overhead (ignoring it passed too, M42), movestogo 0 or
// negative (unclamped, a division by zero, M38) and the depth, nodes and mate
// clamps (M43, M44). Each budget below is worked by hand from time_budget.cpp
// with the parameter defaults (AssumedMovesLeft 30, ReserveDivisor 10,
// DangerZoneOverheads 2, HardOverSoft 4):
// - Black, 2000 ms + 60 s, overhead 100: available 1900, inside the danger
//   zone (1900 < 2 x 100 + 60000), reserve max(190, 100) = 190, cap 1710;
//   share 1900 / 30 + 1710 x 3 / 4 = 63 + 1282 = 1345; hard min(1345, 1710 / 4)
//   x 4 = 1708; soft 1345. White, no increment: share 63, hard 252, soft 63.
// - White, 10000 ms, overhead 500: available 9500, reserve 950, cap 8550;
//   share 316, hard 1264, soft 316 (overhead 0 would give 333 and 1332).
// - movestogo 0 or -3, 1000 ms, overhead 100: one move to go; available 900,
//   reserve 90, cap 810; share 900, hard min(900, 202) x 4 = 808, soft 808.
TEST_CASE("time_budget", "a go's limits: the side to move's clock and increment, Move Overhead, clamps") {
  auto quota = [](std::string_view args, Color us, std::int64_t overhead) {
    std::vector<std::string> warnings;
    const GoLimits go = parse_go(split_tokens(args), 0, Position(), warnings);
    CHECK_MSG(warnings.empty(), args);
    return quota_for_go(go, us, overhead);
  };
  SearchQuota q = quota("wtime 2000 btime 2000 winc 0 binc 60000", Black, 100);
  CHECK_EQ(q.soft_ms, 1345);
  CHECK_EQ(q.hard_ms, 1708);
  q = quota("wtime 2000 btime 2000 winc 0 binc 60000", White, 100);
  CHECK_EQ(q.soft_ms, 63);
  CHECK_EQ(q.hard_ms, 252);
  q = quota("wtime 10000 btime 3000", White, 500);
  CHECK_EQ(q.soft_ms, 316);
  CHECK_EQ(q.hard_ms, 1264);
  for (const char* mtg : {"wtime 1000 btime 1000 movestogo 0", "wtime 1000 btime 1000 movestogo -3"}) {
    q = quota(mtg, White, 100);
    CHECK_MSG(q.soft_ms == 808 && q.hard_ms == 808, mtg << ": soft " << q.soft_ms << " hard " << q.hard_ms);
  }
  q = quota("movetime 1000", Black, 100);
  CHECK_MSG(q.soft_ms == 900 && q.hard_ms == 900, "movetime: soft " << q.soft_ms << " hard " << q.hard_ms);
  q = quota("infinite wtime 1000 btime 1000", White, 100);
  CHECK_MSG(q.soft_ms == -1 && q.hard_ms == -1, "infinite: soft " << q.soft_ms << " hard " << q.hard_ms);
  // No limit sent: none applies.
  q = quota("", White, 100);
  CHECK(q.depth == MaxPly - 1 && q.nodes == 0 && q.mate_moves == 0 && q.soft_ms == -1 && q.hard_ms == -1);
  // Zero, negative and huge values a GUI can send.
  for (const auto& [args, depth] : {std::pair<const char*, int>{"depth 0", 1},
                                    {"depth -7", 1},
                                    {"depth 1", 1},
                                    {"depth 249", MaxPly - 1},
                                    {"depth 1000000000000", MaxPly - 1}})
    CHECK_MSG(quota(args, White, 100).depth == depth, args << ": " << quota(args, White, 100).depth);
  for (const auto& [args, nodes] : {std::pair<const char*, std::uint64_t>{"nodes 0", 1},
                                    {"nodes -5", 1},
                                    {"nodes 1", 1},
                                    {"nodes 123456", 123456}})
    CHECK_MSG(quota(args, White, 100).nodes == nodes, args << ": " << quota(args, White, 100).nodes);
  for (const auto& [args, mate] :
       {std::pair<const char*, int>{"mate 0", 0}, {"mate -3", 0}, {"mate 2", 2}, {"mate 1000", MaxPly}})
    CHECK_MSG(quota(args, White, 100).mate_moves == mate, args << ": " << quota(args, White, 100).mate_moves);
  // Audit-1 R-4: go mate N searches at most the 2N - 1 plies a mate in N
  // needs (at least 1), and a smaller depth limit still applies.
  for (const auto& [args, depth] : {std::pair<const char*, int>{"mate 1", 1},
                                    {"mate 2", 3},
                                    {"mate 7", 13},
                                    {"mate 0", 1},
                                    {"mate -3", 1},
                                    {"mate 1000", MaxPly - 1},
                                    {"mate 99999999999999999999", MaxPly - 1},
                                    {"mate 5 depth 4", 4},
                                    {"depth 20 mate 5", 9}})
    CHECK_MSG(quota(args, White, 100).depth == depth, args << ": depth " << quota(args, White, 100).depth);
}

// Deliverable 8, Milestone A's time loss: at 2+0.02 under full load the
// clock drained to about the Move Overhead, each move then cost about the
// increment in latency (16-20 ms measured), and one longer stall flagged. A
// simulated game where Fork always spends its whole hard limit (the worst
// case) with 18 ms of latency per move: once the clock has settled, one
// 150 ms stall must not run it out (fault-injected: with only a tenth of the
// clock in reserve, deliverable 8a, the clock settles near one overhead and
// the stall flags).
TEST_CASE("time_budget", "a low clock keeps enough reserve to survive a stall") {
  std::int64_t clock = 2000;
  std::int64_t lowest = clock;
  for (int move = 0; move < 300; ++move) {
    ClockInput c;
    c.remaining_ms = clock;
    c.increment_ms = 20;
    c.overhead_ms = 100;
    const std::int64_t latency = move == 250 ? 150 : 18;
    clock += 20 - plan_time(c).hard_ms - latency;
    lowest = std::min(lowest, clock);
  }
  CHECK_MSG(lowest > 0, "the clock ran out (lowest " << lowest << " ms)");
}

}  // namespace forkeng::test

// ---- Adversarial review of deliverable 2 (tests written failing, then fixed) ----
namespace forkeng::test {

// The most negative clock a GUI can send: go_limits.hpp clamps values beyond
// the 64-bit range to it ("go movetime -99999999999999999999").
TEST_CASE("time_budget", "review: INT64_MIN movetime or clock gives the minimum budget, not none") {
  constexpr std::int64_t Min = std::numeric_limits<std::int64_t>::min();
  ClockInput c;
  c.movetime = Min;
  c.overhead_ms = 100;
  TimeBudget t = plan_time(c);
  CHECK_MSG(t.hard_ms == 1 && t.soft_ms == 1,
            "movetime INT64_MIN: soft " << t.soft_ms << " hard " << t.hard_ms);
  c = ClockInput{};
  c.remaining_ms = Min;
  c.overhead_ms = 100;
  t = plan_time(c);
  CHECK_MSG(t.hard_ms == 1 && t.soft_ms == 1, "wtime INT64_MIN: soft " << t.soft_ms << " hard " << t.hard_ms);
}

namespace {
struct LastReport final : SearchListener {
  Move first = NoMove;
  int score = 0;
  int count = 0;
  void on_iteration(const Position&, const IterationReport& r) override {
    first = r.pv->length ? r.pv->moves[0] : NoMove;
    score = r.score;
    ++count;
  }
};
}  // namespace

// The last info line the GUI sees before bestmove (session.cpp prints no
// other line when an iteration finished) should name the move played. Run
// twice: as the engine plays (fail lines only after a second), and with every
// aspiration fail reported. The second found a gap (2026-10-27): a stop during
// the re-search after a reported fail left that fail as the last line (a fail
// low has no PV; a fail high names a move that is not played). It first showed
// under heavy load, when a node-limited debug search took over a second.
TEST_CASE("search", "review: after a stop mid-iteration, the last reported PV starts with the best move") {
  for (const std::int64_t fail_report_ms : {std::int64_t{1000}, std::int64_t{0}}) {
    TestHash store;
    auto searcher = std::make_unique<Searcher>(store.table);
    searcher->fail_report_ms = fail_report_ms;
    const std::atomic<bool> stop{false};
    int mismatches = 0, tried = 0;
    for (const PerftPosition& p : perft_suite()) {
      for (std::uint64_t nodes = 2000; nodes <= 200000 && mismatches == 0; nodes += 9973) {
        Position pos;
        CHECK(pos.set_fen(p.fen));
        SearchQuota limits;
        limits.nodes = nodes;
        LastReport rep;
        const SearchResult r = searcher->deliberate(pos, limits, stop, nullptr, &rep);
        ++tried;
        if (r.depth > 0 && !(rep.first == r.best)) {
          ++mismatches;
          CHECK_MSG(false, p.fen << " nodes " << nodes << ": last info pv " << pos.move_to_uci(rep.first)
                                 << " score " << rep.score << ", bestmove " << pos.move_to_uci(r.best)
                                 << " score " << r.score << " (fail reports after " << fail_report_ms
                                 << " ms)");
        }
      }
    }
    CHECK(tried > 0);
  }
}

// The policy for a stop during a root fail high's re-search (owner,
// 2026-10-26): the fail high is not trusted, and the previous iteration's
// move is kept. External review claim (a) proposed playing it; that lost
// -14.6 +/- 10.8 Elo at STC (sprt-log.md rv-failhigh) and was reverted.
// Node-limited searches over the bench positions (search_bench.cpp, sourced
// there) stop at many different points; wherever one stops with a fail high
// unresolved whose move differs from the last finished iteration's best
// (found by re-running the search to that depth, which repeats those
// iterations exactly), that move must not be the one played. At least one
// such stop must occur, or the test proves nothing. How often one occurs
// depends on the network: B0's first ten bench positions had some, B0r1's
// none, its first ones at positions 30 and 34 below 30,000 nodes and at 34
// and 41 below 12,000. So every bench position is scanned, until three
// such stops are seen.
TEST_CASE("search", "a stop during a root fail high's re-search keeps the previous iteration's move") {
  Fixture fx;
  auto fresh_search = [&](std::string_view fen, const SearchQuota& q) {
    fx.store.clear();
    fx.searcher->clear_history();
    Position pos;
    CHECK(pos.set_fen(fen));
    return fx.search(pos, q);
  };
  int distinct_fail_highs = 0;
  // The first bench positions are the perft suite (perft position 6 stopped
  // at 4,991 nodes with g5f6 failed high and c3d5 the previous best).
  for (std::size_t i = 0; i < search_bench_fens().size() && distinct_fail_highs < 3; ++i) {
    const std::string_view fen = search_bench_fens()[i];
    for (std::uint64_t nodes = 2000; nodes <= (Optimized ? 30000u : 12000u); nodes += 997) {
      SearchQuota q;
      q.nodes = nodes;
      const SearchResult r = fresh_search(fen, q);
      const Move pending = fx.searcher->unresolved_fail_high();
      if (pending.is_none() || r.depth == 0) continue;
      SearchQuota to_depth;
      to_depth.depth = r.depth;
      const Move previous_best = fresh_search(fen, to_depth).best;
      if (pending == previous_best) continue;
      ++distinct_fail_highs;
      Position pos;
      CHECK(pos.set_fen(fen));
      CHECK_MSG(r.best != pending, fen << " at " << nodes << " nodes: played the unconfirmed fail high "
                                       << pos.move_to_uci(pending) << " (previous best "
                                       << pos.move_to_uci(previous_best) << ")");
    }
  }
  CHECK_MSG(distinct_fail_highs > 0, "no search stopped with a distinct fail high unresolved");
}

}  // namespace forkeng::test

namespace forkeng::test {
namespace {
// Pauses once, after the iteration of one depth, so the elapsed time jumps.
struct PausingListener final : SearchListener {
  int pause_after = 0;
  std::chrono::milliseconds pause{0};
  void on_iteration(const Position&, const IterationReport& r) override {
    if (r.depth == pause_after) std::this_thread::sleep_for(pause);
  }
};
}  // namespace

// Deliverable 8, variant (c): no iteration starts that would probably not
// finish before the hard limit (elapsed * 5/3 past it). With soft = hard =
// 90 ms and a 60 ms pause after depth 3, the rule stops at depth 3
// (60 * 5/3 > 90); without it, depth 4 from the start position starts, as
// the soft limit is not reached, and finishes long before the hard limit
// (fault-injected).
TEST_CASE("search", "an iteration that would not finish before the hard limit is not started") {
  TestHash store;
  auto searcher = std::make_unique<Searcher>(store.table);
  const std::atomic<bool> stop{false};
  Position pos;
  CHECK(pos.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"));
  SearchQuota limits;
  limits.depth = 5;
  limits.soft_ms = 90;
  limits.hard_ms = 90;
  PausingListener listener;
  listener.pause_after = 3;
  listener.pause = std::chrono::milliseconds{60};
  const SearchResult r = searcher->deliberate(pos, limits, stop, nullptr, &listener);
  CHECK_EQ(r.depth, 3);
}

// Audit-1 Q-1: the soft limit ends the iterations. The time_budget cases test
// plan_time's numbers only, and the case above binds through the hard-limit
// rule (soft = hard); removing the soft check passed every test (mutant M57).
// The search's clock counts from go_received, set a second in the past here,
// so the soft limit has passed when depth 1 finishes and no second iteration
// starts, however far away the hard limit (an hour) is. Load cannot make it
// fail: a slower machine only makes the elapsed time larger.
TEST_CASE("search", "a search stops iterating once its soft limit has passed") {
  TestHash store;
  auto searcher = std::make_unique<Searcher>(store.table);
  const std::atomic<bool> stop{false};
  Position pos;
  SearchQuota limits;
  limits.depth = 12;
  limits.soft_ms = 1;
  limits.hard_ms = 3'600'000;
  limits.go_received = std::chrono::steady_clock::now() - std::chrono::milliseconds{1000};
  CHECK_EQ(searcher->deliberate(pos, limits, stop, nullptr, nullptr).depth, 1);
}

// Audit-1 Q-8: a pondering search ignores its soft and hard limits (they
// apply from ponderhit on). The UCI ponder case checks only when bestmove is
// printed, which the session holds until ponderhit anyway, so applying either
// limit while pondering passed every test (mutants M26, M27). Both limits
// have passed here (go a second ago, 1 ms each), yet the search reaches the
// depth asked for.
TEST_CASE("search", "a pondering search ignores its soft and hard limits") {
  TestHash store;
  auto searcher = std::make_unique<Searcher>(store.table);
  const std::atomic<bool> stop{false};
  const std::atomic<bool> pondering{true};
  Position pos;
  SearchQuota limits;
  limits.depth = 7;
  limits.soft_ms = 1;
  limits.hard_ms = 1;
  limits.go_received = std::chrono::steady_clock::now() - std::chrono::milliseconds{1000};
  CHECK_EQ(searcher->deliberate(pos, limits, stop, &pondering, nullptr).depth, 7);
}

namespace {
// Every report of a search: depth, score, bound and the pv's first move.
struct ReportLog final : SearchListener {
  struct Entry {
    int depth, score, bound;
    Move first;
  };
  std::vector<Entry> entries;
  void on_iteration(const Position&, const IterationReport& r) override {
    entries.push_back({r.depth, r.score, r.bound, r.pv->length ? r.pv->moves[0] : NoMove});
  }
};
}  // namespace

// Audit-1 Q-8: after a stop mid-iteration, a move other than the last
// finished iteration's best is played only if it came back with an exact
// score above that iteration's (searcher.cpp, the stop rule). The fail-high
// case above covers the other half of the rule; playing the unfinished
// iteration's best whatever its score passed every test (mutant M24).
// Node-limited searches over the bench positions stop at many points; the
// last finished iteration is the first exact report at the result's depth.
// At least one stop must play a new move, or the test proves nothing. That
// is required of optimized builds only: node-limited searches are the same
// in every build (bench parity), and the smaller sample debug builds can
// afford may hold no such stop (none in the first 6 positions after
// 304081e, RfpMargin 40, so gcc-debug failed in CI).
TEST_CASE("search", "a stop mid-iteration plays a new move only if it scored above the last iteration") {
  Fixture fx;
  int switched = 0;
  const std::size_t positions = Optimized ? search_bench_fens().size() : 6;
  for (std::size_t i = 0; i < positions; ++i) {
    const std::string_view fen = search_bench_fens()[i];
    for (std::uint64_t nodes = 2000; nodes <= (Optimized ? 30000u : 12000u); nodes += 997) {
      fx.store.clear();
      fx.searcher->clear_history();
      Position pos;
      CHECK(pos.set_fen(fen));
      SearchQuota q;
      q.nodes = nodes;
      ReportLog log;
      const SearchResult r = fx.searcher->deliberate(pos, q, fx.stop, nullptr, &log);
      if (r.depth == 0) continue;
      const auto finished = std::ranges::find_if(
          log.entries, [&](const ReportLog::Entry& e) { return e.depth == r.depth && e.bound == 0; });
      CHECK_MSG(finished != log.entries.end(),
                fen << " at " << nodes << " nodes: no report of depth " << r.depth);
      if (finished == log.entries.end() || r.best == finished->first) continue;
      ++switched;
      CHECK_MSG(r.score > finished->score, fen << " at " << nodes << " nodes: played "
                                               << pos.move_to_uci(r.best) << " at " << r.score << " over "
                                               << pos.move_to_uci(finished->first) << " at "
                                               << finished->score << " (depth " << r.depth << ")");
    }
  }
  if (Optimized)
    CHECK_MSG(switched > 0, "no stop played a move other than the last finished iteration's");
  else if (switched == 0)
    NOTE("no stop in the debug sample played a new move; optimized builds require one");
}

// Audit-1 V-4 (00bed14): no LMR or PVS re-search once the search has
// stopped (a stopped child returns 0, which can beat alpha, and each
// re-search counts one more node past a node limit). Reverting 00bed14
// passed every test; over many limits, it counts two or more nodes over the
// limit. Since audit-1 A1 suspicion 8 the limit is exact: the root's PVS
// re-search checks the stop too (without it, 16 of these limits end one
// node over), and the root node polls the limits (without it, one does: an
// iteration that ends one node short of the limit).
TEST_CASE("search", "a node limit is kept exactly") {
  Fixture fx;
  int searches = 0;
  for (const PerftPosition& p : perft_suite()) {
    for (std::uint64_t nodes = 2000; nodes <= (Optimized ? 60000u : 15000u); nodes += 997) {
      fx.store.clear();
      fx.searcher->clear_history();
      Position pos;
      CHECK(pos.set_fen(p.fen));
      SearchQuota q;
      q.nodes = nodes;
      const SearchResult r = fx.search(pos, q);
      ++searches;
      CHECK_MSG(r.nodes == nodes, p.fen << ": limit " << nodes << ", searched " << r.nodes);
    }
  }
  CHECK(searches > 0);
}

// Audit-1, A1 S-2: the listener's contract (searcher.hpp). A depth-limited
// search that is never stopped reports each finished iteration exactly once,
// in order, as an exact score, and with fail reports on (fail_report_ms 0)
// adds one bound line per aspiration fail; over the perft suite at depth 12
// some fail (the A1 audit counted 12).
TEST_CASE("search", "the listener: one exact report per finished iteration, plus one per reported fail") {
  struct Counter final : SearchListener {
    int exact = 0, bounds = 0, last_exact_depth = 0;
    bool in_order = true;
    void on_iteration(const Position&, const IterationReport& r) override {
      if (r.bound != 0) {
        ++bounds;
        return;
      }
      in_order = in_order && r.depth == last_exact_depth + 1;
      last_exact_depth = r.depth;
      ++exact;
    }
  };
  Fixture fx;
  fx.searcher->fail_report_ms = 0;
  const int depth = Optimized ? 12 : 8;
  int bounds = 0;
  for (const auto& p : perft_suite()) {
    Position pos;
    CHECK(pos.set_fen(p.fen));
    fx.store.clear();
    fx.searcher->clear_history();
    SearchQuota limits;
    limits.depth = depth;
    Counter c;
    const SearchResult r = fx.searcher->deliberate(pos, limits, fx.stop, nullptr, &c);
    CHECK_EQ(r.depth, depth);
    CHECK_MSG(c.exact == depth && c.in_order, p.fen << ": " << c.exact << " exact reports");
    bounds += c.bounds;
  }
  CHECK_MSG(bounds > 0, "no aspiration fail was reported");
}
// Audit-1, B-1: with one root move a timed search stops once 1/8 of its soft
// limit has passed. A 150 ms pause after depth 1 passes 1/8 of 800 ms, so
// the forced position (White's only move is g2g3; tools/check_search_positions.py)
// stops at depth 1; with the switch off, and in a position with more moves,
// the search runs to its depth limit, far below the soft limit.
TEST_CASE("search", "a forced move stops at a fraction of the soft limit") {
  TestHash store;
  auto searcher = std::make_unique<Searcher>(store.table);
  const std::atomic<bool> stop{false};
  auto depth_reached = [&](std::string_view fen, bool rule) {
    Position pos;
    CHECK(pos.set_fen(fen));
    searcher->switches.use_forced_move_stop = rule;
    SearchQuota limits;
    limits.depth = 6;
    limits.soft_ms = 800;
    limits.hard_ms = 3200;
    PausingListener listener;
    listener.pause_after = 1;
    listener.pause = std::chrono::milliseconds{150};
    return searcher->deliberate(pos, limits, stop, nullptr, &listener).depth;
  };
  const std::string_view forced = "rnb1kbnr/pppp1ppp/8/4p3/7q/5P2/PPPPP1PP/RNBQKBNR w KQkq - 1 3";
  CHECK_EQ(depth_reached(forced, true), 1);
  CHECK_EQ(depth_reached(forced, false), 6);
  CHECK_EQ(depth_reached("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", true), 6);
}
}  // namespace forkeng::test
