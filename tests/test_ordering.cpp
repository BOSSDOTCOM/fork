// Move ordering (DESIGN.md §5.2, deliverable 5): the staged selector yields
// exactly the right moves, and the history update stays bounded.
#include <algorithm>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "harness.hpp"
#include "search/move_selector.hpp"
#include "search/quiet_history.hpp"
#include "search/see.hpp"
#include "suite.hpp"

namespace forkeng::test {

namespace {

std::vector<std::uint16_t> sorted_raw(const std::vector<Move>& moves) {
  std::vector<std::uint16_t> out;
  for (Move m : moves) out.push_back(m.raw());
  std::sort(out.begin(), out.end());
  return out;
}

std::vector<Move> drain(MoveSelector& s) {
  std::vector<Move> out;
  for (Move m; !(m = s.take_next()).is_none();) out.push_back(m);
  return out;
}

// What the quiescence search must try at a node, computed independently.
std::vector<Move> quiesce_set(const Position& pos, bool see_filter) {
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  std::vector<Move> out;
  for (Move m : legal) {
    if (pos.in_check()) {
      out.push_back(m);
      continue;
    }
    if (!m.is_capture() && !m.is_promotion()) continue;
    if (m.is_promotion() && m.promo_type() != Queen) continue;
    if (see_filter && m.is_capture() && see_value(pos, m) < 0) continue;
    out.push_back(m);
  }
  return out;
}

struct Counts {
  long nodes = 0, checks = 0;
};

void check_node(Position& pos, const QuietHistory& history, std::uint64_t& seed, Counts& c) {
  MoveList legal_list;
  generate<GenMode::Legal>(pos, legal_list);
  const std::vector<Move> legal(legal_list.begin(), legal_list.end());
  const std::vector<std::uint16_t> want = sorted_raw(legal);
  // TT moves: none, each legal move in turn (up to 4), and random 16-bit
  // patterns (mostly illegal, some not even pseudo-legal).
  std::vector<Move> tt_moves = {NoMove};
  for (std::size_t i = 0; i < legal.size() && i < 4; ++i) tt_moves.push_back(legal[i]);
  for (int i = 0; i < 4; ++i)
    tt_moves.push_back(Move::from_raw(static_cast<std::uint16_t>(splitmix_next(seed))));
  for (Move tt : tt_moves) {
    for (const QuietHistory* h : {static_cast<const QuietHistory*>(nullptr), &history}) {
      MoveSelector s;
      s.start_main(pos, tt, h);
      const std::vector<Move> got = drain(s);
      CHECK_MSG(sorted_raw(got) == want, pos.fen() << " tt " << tt.raw() << ": main selector set differs");
      // A legal TT move comes first.
      if (!tt.is_none() && std::find(legal.begin(), legal.end(), tt) != legal.end())
        CHECK_MSG(!got.empty() && got.front() == tt, pos.fen());
      ++c.checks;
      for (bool see_filter : {true, false}) {
        MoveSelector q;
        q.start_quiesce(pos, tt, see_filter, h);
        CHECK_MSG(sorted_raw(drain(q)) == sorted_raw(quiesce_set(pos, see_filter)),
                  pos.fen() << " tt " << tt.raw() << " see " << see_filter << ": quiescence set differs");
        ++c.checks;
      }
    }
  }
  // skip_quiets: no quiet move after the call, and every capture and
  // promotion still comes (every evasion, in check).
  MoveSelector s;
  s.start_main(pos, NoMove, &history);
  s.skip_quiets();
  const std::vector<Move> kept = drain(s);
  for (Move m : kept) CHECK_MSG(m.is_capture() || m.is_promotion() || pos.in_check(), pos.fen());
  std::size_t noisy = 0;
  for (Move m : legal) noisy += pos.in_check() || m.is_capture() || m.is_promotion();
  CHECK_MSG(kept.size() == noisy, pos.fen() << ": " << kept.size() << " of " << noisy);
  ++c.nodes;
}

void walk(Position& pos, int depth, const QuietHistory& history, std::uint64_t& seed, Counts& c) {
  check_node(pos, history, seed, c);
  if (depth == 0) return;
  MoveList list;
  generate<GenMode::Legal>(pos, list);
  for (Move m : list) {
    pos.make(m);
    walk(pos, depth - 1, history, seed, c);
    pos.unmake(m);
  }
}

}  // namespace

TEST_CASE("ordering", "the selector yields exactly the legal moves (main) and the capture set (quiescence)") {
  // A history with arbitrary values, so ordering by it is exercised.
  QuietHistory history;
  std::uint64_t seed = 20261025;
  for (int i = 0; i < 20000; ++i) {
    const Move m = Move::from_raw(static_cast<std::uint16_t>(splitmix_next(seed) & 0xFFF));
    history.apply(Color(i & 1), m, static_cast<int>(splitmix_next(seed) % 3201) - 1600);
  }
  Counts c;
  for (const PerftPosition& p : perft_suite()) {
    Position pos;
    CHECK(pos.set_fen(p.fen));
    walk(pos, Optimized ? 2 : 1, history, seed, c);
  }
  CHECK(c.nodes > (Optimized ? 5000 : 100));
}

TEST_CASE("ordering", "a losing capture comes after the quiets; the best-history quiet comes first") {
  // Constructed (legality checked by tools/check_search_positions.py): the
  // only capture is Nxd5, which the c6 pawn defends (SEE -200), so it is
  // deferred to the end; e1f1 has the only non-zero history, so it leads the
  // quiets and, with no good capture, comes first.
  Position pos;
  CHECK(pos.set_fen("4k3/8/2p5/3p3p/8/4N1Q1/8/4K3 w - - 0 1"));
  QuietHistory history;
  history.apply(White, pos.parse_uci("e1f1"), 1600);
  MoveSelector s;
  s.start_main(pos, NoMove, &history);
  const std::vector<Move> got = drain(s);
  CHECK(!got.empty() && got.back() == pos.parse_uci("e3d5"));
  CHECK(!got.empty() && got.front() == pos.parse_uci("e1f1"));
}

TEST_CASE("ordering",
          "history: bounded for any update sequence, monotone, bonus grows with depth and is capped") {
  QuietHistory h;
  const Move m(12, 28, Quiet);
  std::uint64_t seed = 7;
  for (int i = 0; i < 200000; ++i) {
    const int amount = static_cast<int>(splitmix_next(seed) % (2 * HistoryMax + 1)) - HistoryMax;
    h.apply(White, m, amount);
    const int v = h.value(White, m);
    CHECK_MSG(v >= -HistoryMax && v <= HistoryMax, "value " << v << " after amount " << amount);
  }
  // Monotone: a bonus never lowers the value, a malus never raises it.
  for (int start : {-HistoryMax, -9000, -1, 0, 1, 5000, HistoryMax}) {
    for (int amount : {1, 16, 400, 1600, HistoryMax}) {
      QuietHistory a;
      a.apply(Black, m, start);  // from 0, reaches start exactly when |start| <= HistoryMax
      const int before = a.value(Black, m);
      QuietHistory b = a;
      a.apply(Black, m, amount);
      b.apply(Black, m, -amount);
      CHECK(a.value(Black, m) >= before);
      CHECK(b.value(Black, m) <= before);
    }
  }
  for (int d = 1; d < 40; ++d) CHECK(bonus_for_depth(d + 1) >= bonus_for_depth(d));
  CHECK_EQ(bonus_for_depth(100), HistoryBonusCap);
  h.clear();
  CHECK_EQ(h.value(White, m), 0);
}

}  // namespace forkeng::test
