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

// Endgames transpose a lot, so the TT really cuts here (counted below), and
// minimax to depth 6 is still cheap. Constructed positions.
TEST_CASE("search", "TT cutoffs at exact depth equal plain minimax on small endgames at depth 6") {
  Fixture fx;
  const int depth = Optimized ? 6 : 4;
  for (std::string_view fen : {"8/2k5/8/1p6/1P6/8/5K2/8 w - - 0 1", "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",
                               "8/8/3k4/8/8/3K4/8/R7 w - - 0 1", "8/5pk1/8/8/8/8/5PK1/8 b - - 0 1"}) {
    Position pos;
    CHECK(pos.set_fen(fen));
    const int expected = reference_minimax(pos, depth, 0);
    std::uint64_t nodes[2] = {0, 0};
    for (bool tt : {true, false}) {
      fx.store.clear();
      fx.searcher->switches = exact_switches();
      fx.searcher->switches.use_tt = tt;
      SearchQuota limits;
      limits.depth = depth;
      const SearchResult r = fx.search(pos, limits);
      CHECK_MSG(r.score == expected, fen << " tt " << tt << ": " << r.score << " vs " << expected);
      nodes[tt] = r.nodes;
    }
    // The TT really cut: fewer nodes with it.
    CHECK_MSG(nodes[1] < nodes[0],
              fen << ": " << nodes[1] << " nodes with the TT, " << nodes[0] << " without");
  }
}

// DESIGN.md §5.2 deliverable 4: quiescence values on constructed exchanges,
// against python-chess. tools/check_search_positions.py computes each
// position's material-only value of a depth-1 search ending in a capture
// search, and the moves reaching it (python-chess generates the moves; no
// Fork code is involved). Fork must play one of those moves (or, where every
// quiet move ties, avoid the losing capture) and score within 100 cp of the
// material value: the bootstrap evaluation's placement terms make the rest.
TEST_CASE("search", "quiescence values on constructed exchanges match python-chess") {
  Fixture fx;
  struct Exchange {
    std::string_view fen;
    int material;           // python-chess value, centipawns for the side to move
    std::string_view best;  // the only best move, or "" if many quiet moves tie
    std::string_view avoid;
  };
  for (const Exchange& x : {Exchange{"4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1", 100, "e4d5", ""},
                            Exchange{"4k3/8/3p4/4r3/8/5N2/8/4K3 w - - 0 1", -100, "f3e5", ""},
                            Exchange{"4k3/8/2p5/3p4/8/8/3Q4/4K3 w - - 0 1", 700, "", "d2d5"},
                            Exchange{"4k3/1P6/8/8/8/8/8/4K3 w - - 0 1", 900, "b7b8q", ""},
                            Exchange{"3rk3/8/8/3p4/8/8/3R4/3RK3 w - - 0 1", 500, "d2d5", ""}}) {
    fx.store.clear();
    Position pos;
    CHECK(pos.set_fen(x.fen));
    const SearchResult r = fx.search(x.fen, 1);
    const std::string played = pos.move_to_uci(r.best);
    if (!x.best.empty()) CHECK_MSG(played == x.best, x.fen << ": played " << played);
    if (!x.avoid.empty()) CHECK_MSG(played != x.avoid, x.fen << ": played " << played);
    CHECK_MSG(std::abs(r.score - x.material) <= 100,
              x.fen << ": score " << r.score << ", material " << x.material);
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
  Position pos;
  for (const char* uci : {"e2e4", "g8f6", "g1f3", "f6g8", "f3g1"}) pos.make(pos.parse_uci(uci));
  SearchQuota limits;
  limits.depth = 1;
  limits.restrict_to.add(pos.parse_uci("g8f6"));
  const SearchResult r = fx.search(pos, limits);
  CHECK_EQ(pos.move_to_uci(r.best), std::string("g8f6"));
  CHECK_EQ(r.score, 0);
  CHECK(static_eval(pos) != 0);  // so the 0 is the draw, not the evaluation
}

TEST_CASE("search", "limits: nodes, depth, searchmoves; a preset stop still returns a legal move") {
  Fixture fx;
  Position pos;
  SearchQuota limits;
  limits.nodes = 5000;
  SearchResult r = fx.search(pos, limits);
  CHECK(r.nodes >= 5000 && r.nodes <= 5001);
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
// tenth of the clock outside it.
TEST_CASE("time_budget", "an extra overhead of reserve only in the danger zone") {
  for (std::int64_t remaining : {150, 250, 300, 319, 320, 500, 1000, 2000}) {
    for (std::int64_t inc : {0, 20, 80}) {
      ClockInput c;
      c.remaining_ms = remaining;
      c.increment_ms = inc;
      c.overhead_ms = 100;
      const TimeBudget t = plan_time(c);
      const std::int64_t available = remaining - 100;
      const bool zone = available < 200 + inc;
      const std::int64_t reserve = zone ? std::max<std::int64_t>(available / 10, 100) : available / 10;
      CHECK_MSG(t.hard_ms <= std::max<std::int64_t>(1, available - reserve), remaining << " ms + " << inc);
      if (zone && available <= 100) CHECK_MSG(t.hard_ms == 1, remaining << " ms + " << inc);
    }
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

// ---- Adversarial review of deliverable 2 (uncommitted; failing tests) ----
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
// such stop must occur, or the test proves nothing.
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
  const std::size_t positions = Optimized ? 10 : 6;
  for (std::size_t i = 0; i < positions; ++i) {
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
}  // namespace forkeng::test
