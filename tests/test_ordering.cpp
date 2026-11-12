// SPDX-License-Identifier: GPL-3.0-or-later

// Move ordering (DESIGN.md §5.2, deliverable 5): the staged selector yields
// exactly the right moves, and the history update stays bounded.
#include <algorithm>
#include <cstdint>
#include <memory>
#include <set>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "harness.hpp"
#include "search/move_selector.hpp"
#include "search/quiet_history.hpp"
#include "search/see.hpp"
#include "suite.hpp"
#include "tune/params.hpp"

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
      // With and without the threat buckets (tier 2, T56): only the order
      // may change.
      for (bool aware : {false, true}) {
        MoveSelector s;
        s.start_main(pos, tt, h, nullptr, NoArrival, NoArrival, nullptr, aware);
        const std::vector<Move> got = drain(s);
        CHECK_MSG(sorted_raw(got) == want,
                  pos.fen() << " tt " << tt.raw() << " aware " << aware << ": main selector set differs");
        // A legal TT move comes first.
        if (!tt.is_none() && std::find(legal.begin(), legal.end(), tt) != legal.end())
          CHECK_MSG(!got.empty() && got.front() == tt, pos.fen());
        ++c.checks;
        for (bool see_filter : {true, false}) {
          MoveSelector q;
          q.start_quiesce(pos, tt, see_filter, h, nullptr, aware);
          CHECK_MSG(sorted_raw(drain(q)) == sorted_raw(quiesce_set(pos, see_filter)),
                    pos.fen() << " tt " << tt.raw() << " see " << see_filter << ": quiescence set differs");
          ++c.checks;
        }
      }
    }
  }
  // stop_quiets: no quiet move after the call, and every capture and
  // promotion still comes (every evasion, in check).
  MoveSelector s;
  s.start_main(pos, NoMove, &history);
  s.stop_quiets();
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

// The pair history (tier 2, T10): every piece (colour and type) on every
// square has its own slot in [0, PairSlots); the table stays within the
// butterfly history's bounds for any update sequence; and the selector puts
// a quiet move with a reply entry first after the move it is paired with,
// and ignores the table at a node with no arrival (the root, after a null
// move). Heap-allocated: the table is about 1.2 MB.
TEST_CASE("ordering", "pair history: distinct slots, bounded, and it orders quiets after the arrival only") {
  std::set<int> slots;
  for (Color c : {White, Black})
    for (int t = Pawn; t <= King; ++t)
      for (int sq = 0; sq < 64; ++sq) {
        const int slot = pair_slot(static_cast<Piece>(c * 8 + t), static_cast<Square>(sq));
        CHECK(slot >= 0 && slot < PairSlots);
        slots.insert(slot);
      }
  CHECK_EQ(static_cast<int>(slots.size()), PairSlots);

  auto pairs = std::make_unique<PairHistory[]>(2);  // the reply and follow tables, as in the searcher
  std::uint64_t seed = 11;
  for (int i = 0; i < 200000; ++i) {
    const int amount = static_cast<int>(splitmix_next(seed) % (2 * HistoryMax + 1)) - HistoryMax;
    pairs[ReplyTable].apply(100, 200, amount);
    const int v = pairs[ReplyTable].value(100, 200);
    CHECK_MSG(v >= -HistoryMax && v <= HistoryMax, "value " << v << " after amount " << amount);
  }
  pairs[ReplyTable].clear();
  CHECK_EQ(pairs[ReplyTable].value(100, 200), 0);

  // The position of the case above, without its history. Without the pair
  // table the quiets come in generation order and the deferred losing
  // capture last; the last quiet gets the only reply entry, paired with an
  // arrival of a black pawn on h5, and must then come first.
  Position pos;
  CHECK(pos.set_fen("4k3/8/2p5/3p3p/8/4N1Q1/8/4K3 w - - 0 1"));
  QuietHistory history;
  MoveSelector s;
  s.start_main(pos, NoMove, &history);
  const std::vector<Move> plain = drain(s);
  CHECK(plain.size() >= 3 && plain.back() == pos.parse_uci("e3d5"));
  const Move reply = plain[plain.size() - 2];
  CHECK(!reply.is_capture() && !reply.is_promotion() && plain.front() != reply);
  const int arrival = pair_slot(static_cast<Piece>(Black * 8 + Pawn), static_cast<Square>(39));  // h5
  pairs[ReplyTable].apply(arrival, pair_slot(pos.piece_at(reply.from()), reply.to()), 1600);
  s.start_main(pos, NoMove, &history, pairs.get(), arrival);
  const std::vector<Move> got = drain(s);
  CHECK(!got.empty() && got.front() == reply);
  s.start_main(pos, NoMove, &history, pairs.get(), NoArrival);
  CHECK(drain(s) == plain);
  // The same entry in the follow table, read with the follow arrival only.
  pairs[ReplyTable].clear();
  pairs[FollowTable].apply(arrival, pair_slot(pos.piece_at(reply.from()), reply.to()), 1600);
  s.start_main(pos, NoMove, &history, pairs.get(), NoArrival, arrival);
  const std::vector<Move> followed = drain(s);
  CHECK(!followed.empty() && followed.front() == reply);
  s.start_main(pos, NoMove, &history, pairs.get(), arrival, NoArrival);
  CHECK(drain(s) == plain);
}

// The take history (tier 2, T11): distinct slots, bounded updates, and the
// selector orders two captures of the same victim by it instead of by the
// attacker. Constructed position (checked with python-chess: legal, the
// only captures are Qxd5 and exd5, d5 undefended, so both are good
// captures): MVV-LVA puts exd5 first (the cheaper attacker); a take history
// entry for Qxd5 must put it first, and only when the table is given.
TEST_CASE("ordering", "take history: distinct slots, bounded, and it reorders equal-victim captures") {
  std::set<int> slots;
  for (Color c : {White, Black})
    for (int t = Pawn; t <= King; ++t)
      for (int sq = 0; sq < 64; ++sq)
        for (int v = Pawn; v <= King; ++v) {
          const int slot =
              take_slot(static_cast<Piece>(c * 8 + t), static_cast<Square>(sq), static_cast<PieceType>(v));
          CHECK(slot >= 0 && slot < TakeSlots);
          slots.insert(slot);
        }
  CHECK_EQ(static_cast<int>(slots.size()), TakeSlots);

  auto takes = std::make_unique<TakeHistory>();
  std::uint64_t seed = 13;
  for (int i = 0; i < 200000; ++i) {
    const int amount = static_cast<int>(splitmix_next(seed) % (2 * HistoryMax + 1)) - HistoryMax;
    takes->apply(1234, amount);
    const int v = takes->value(1234);
    CHECK_MSG(v >= -HistoryMax && v <= HistoryMax, "value " << v << " after amount " << amount);
  }
  takes->clear();
  CHECK_EQ(takes->value(1234), 0);

  Position pos;
  CHECK(pos.set_fen("4k3/8/8/3p4/4P3/8/8/3QK3 w - - 0 1"));
  const Move queen = pos.parse_uci("d1d5"), pawn = pos.parse_uci("e4d5");
  QuietHistory history;
  MoveSelector s;
  s.start_main(pos, NoMove, &history);
  const std::vector<Move> plain = drain(s);
  CHECK(plain.size() >= 2 && plain[0] == pawn && plain[1] == queen);
  takes->apply(take_slot(pos.piece_at(queen.from()), queen.to(), Pawn), 1600);
  s.start_main(pos, NoMove, &history, nullptr, NoArrival, NoArrival, takes.get());
  const std::vector<Move> learned = drain(s);
  CHECK(learned.size() >= 2 && learned[0] == queen && learned[1] == pawn);
  s.start_quiesce(pos, NoMove, true, &history, takes.get());
  const std::vector<Move> quiesce = drain(s);
  CHECK(quiesce.size() == 2 && quiesce[0] == queen);
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

namespace forkeng::test {

// The take history's reach (tier 2, T11; found by the tier-2 review of
// 2026-10-31, which showed the first justification counted one side of the
// history's range only): two entries at opposite limits move two captures
// apart by 2 * HistoryMax * TakeWeight / 32 = 2,500 score units, 3.1 pawns
// at 8 units per centipawn. So a pawn capture can come before a knight
// capture (2 pawns apart), and never before a rook capture (4 pawns apart).
// Constructed positions, checked with python-chess: legal, the only
// captures are Qxa5 and exd5, both good captures (a5 undefended; d5
// undefended, or defended by the rook so exd5 is an even trade).
TEST_CASE("ordering", "take history: it can reorder victims 2 pawns apart, never 4") {
  const auto ordered = [](std::string_view fen, PieceType big) {
    Position pos;
    CHECK(pos.set_fen(fen));
    const Move takes_big = pos.parse_uci("a1a5"), takes_pawn = pos.parse_uci("e4d5");
    auto takes = std::make_unique<TakeHistory>();
    // Repeated capped bonuses and maluses (record_cutoff's amounts) drive
    // the two entries to their opposite limits.
    for (int i = 0; i < 200; ++i) {
      takes->apply(take_slot(pos.piece_at(takes_pawn.from()), takes_pawn.to(), Pawn), HistoryBonusCap);
      takes->apply(take_slot(pos.piece_at(takes_big.from()), takes_big.to(), big), -HistoryBonusCap);
    }
    QuietHistory history;
    MoveSelector s;
    s.start_main(pos, NoMove, &history, nullptr, NoArrival, NoArrival, takes.get());
    const std::vector<Move> got = drain(s);
    CHECK(got.size() >= 2);
    return got.size() >= 2 && got[0] == takes_big;
  };
  CHECK(!ordered("4k3/8/8/n2p4/4P3/8/8/Q6K w - - 0 1", Knight));  // within the reach: reordered
  CHECK(ordered("4k3/8/8/r2p4/4P3/8/8/Q6K w - - 0 1", Rook));     // beyond it: never
}

// quiet_order_score (DESIGN.md §5.7, X2) is the selector's quiet score as
// a function: with seeded random butterfly, reply and follow entries for
// every quiet move, the selector yields each position's quiets in
// non-increasing helper score, and hand-set entries give the documented sum,
// clamped to int16 (ReplyWeight 6 / 4 takes three full entries past it).
TEST_CASE("ordering", "quiet_order_score orders quiets as the selector does") {
  auto pairs = std::make_unique<PairHistory[]>(2);
  auto history = std::make_unique<QuietHistory>();
  const int arrival = pair_slot(static_cast<Piece>(Black * 8 + Knight), static_cast<Square>(42));
  const int follow = pair_slot(static_cast<Piece>(White * 8 + Bishop), static_cast<Square>(19));
  std::uint64_t seed = 20261107;
  int checked = 0;
  for (const PerftPosition& p : perft_suite()) {
    Position pos;
    CHECK(pos.set_fen(p.fen));
    if (pos.in_check()) continue;
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    for (Move m : legal) {
      const auto amount = [&] { return static_cast<int>(splitmix_next(seed) % 4001) - 2000; };
      const int slot = pair_slot(pos.piece_at(m.from()), m.to());
      history->apply(pos.side_to_move(), m, amount());
      pairs[ReplyTable].apply(arrival, slot, amount());
      pairs[FollowTable].apply(follow, slot, amount());
    }
    MoveSelector s;
    s.start_main(pos, NoMove, history.get(), pairs.get(), arrival, follow);
    int previous = INT16_MAX;
    for (Move m : drain(s)) {
      if (m.is_capture() || m.is_promotion()) continue;
      const int score = quiet_order_score(pos, m, history.get(), pairs.get(), arrival, follow);
      CHECK_MSG(score <= previous,
                p.name << ": " << pos.move_to_uci(m) << " " << score << " after " << previous);
      previous = score;
      ++checked;
    }
  }
  CHECK(checked > 50);
  // Hand-set entries: 10,000 each (one bonus of HistoryMax from 0).
  Position pos;
  CHECK(pos.set_fen(perft_suite()[0].fen));
  const Move m = pos.parse_uci("g1f3");
  const int slot = pair_slot(pos.piece_at(m.from()), m.to());
  auto fresh = std::make_unique<QuietHistory>();
  auto fresh_pairs = std::make_unique<PairHistory[]>(2);
  fresh->apply(White, m, HistoryMax);
  CHECK_EQ(quiet_order_score(pos, m, fresh.get(), fresh_pairs.get(), NoArrival, NoArrival), HistoryMax);
  fresh_pairs[ReplyTable].apply(arrival, slot, HistoryMax);
  const int with_reply = std::min(HistoryMax + HistoryMax * ReplyWeight / 4, static_cast<int>(INT16_MAX));
  CHECK_EQ(quiet_order_score(pos, m, fresh.get(), fresh_pairs.get(), arrival, NoArrival), with_reply);
  fresh_pairs[FollowTable].apply(follow, slot, HistoryMax);
  const int with_both = std::min(HistoryMax + HistoryMax * ReplyWeight / 4 + HistoryMax * FollowWeight / 4,
                                 static_cast<int>(INT16_MAX));
  CHECK_EQ(quiet_order_score(pos, m, fresh.get(), fresh_pairs.get(), arrival, follow), with_both);
  CHECK_EQ(with_both, static_cast<int>(INT16_MAX));  // the clamp is reached
  CHECK_EQ(quiet_order_score(pos, m, nullptr, fresh_pairs.get(), NoArrival, follow),
           HistoryMax * FollowWeight / 4);
  // Without pair tables the arrivals are ignored, as MoveSelector::start_main
  // drops them: a stats build with UseHistory off and the reply or follow
  // history on passes arrivals with no tables (searcher.cpp's X2 read).
  CHECK_EQ(quiet_order_score(pos, m, fresh.get(), nullptr, arrival, follow), HistoryMax);
  CHECK_EQ(quiet_order_score(pos, m, nullptr, nullptr, arrival, NoArrival), 0);
  // A threat bucket (tier 2, T56) reads that bucket's entry alone.
  CHECK_EQ(quiet_order_score(pos, m, fresh.get(), nullptr, NoArrival, NoArrival, 2), 0);
  fresh->apply(White, m, -HistoryMax, 2);
  CHECK_EQ(quiet_order_score(pos, m, fresh.get(), nullptr, NoArrival, NoArrival, 2), -HistoryMax);
  CHECK_EQ(quiet_order_score(pos, m, fresh.get(), nullptr, NoArrival, NoArrival), HistoryMax);
}

// The threat set (tier 2, T56; KB §3.34's test plan): attacked_squares(by)
// equals the single-square query attacked_by on every square, for both
// colours, over the perft and edge positions of tests/suite.hpp.
TEST_CASE("ordering", "attacked squares: equal to the single-square attack query everywhere") {
  std::vector<std::string_view> fens;
  for (const PerftPosition& p : perft_suite()) fens.push_back(p.fen);
  for (const EdgePosition& p : edge_positions()) fens.push_back(p.fen);
  int compared = 0;
  for (std::string_view fen : fens) {
    Position pos;
    CHECK_MSG(pos.set_fen(fen), fen);
    for (Color by : {White, Black}) {
      Bitboard want = 0;
      for (Square s = 0; s < 64; ++s)
        if (pos.attacked_by(by, s, pos.pieces())) want |= bb(s);
      CHECK_MSG(pos.attacked_squares(by) == want, fen << " by " << static_cast<int>(by));
      ++compared;
    }
  }
  CHECK(compared > 20);
}

// Threat buckets (tier 2, T56): a quiet move's bucket is 2 * (from-square
// attacked) + (to-square attacked) by the opponent, against the
// single-square query; kiwipete (tests/suite.hpp's perft position 2) has
// quiets in all four buckets; and an update to one bucket leaves the other
// three as they were.
TEST_CASE("ordering", "threat buckets: from and to bits, all four reached, independent entries") {
  Position pos;
  CHECK(pos.set_fen(perft_suite()[1].fen));
  CHECK(perft_suite()[1].name == std::string_view("kiwipete"));
  const Bitboard attacked = pos.attacked_squares(Black);
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  bool reached[ThreatBuckets] = {};
  for (Move m : legal) {
    if (m.is_capture() || m.is_promotion()) continue;
    const int want =
        2 * pos.attacked_by(Black, m.from(), pos.pieces()) + pos.attacked_by(Black, m.to(), pos.pieces());
    CHECK_MSG(threat_bucket(attacked, m) == want, pos.move_to_uci(m));
    reached[want] = true;
  }
  for (int b = 0; b < ThreatBuckets; ++b) CHECK_MSG(reached[b], "bucket " << b);
  const Move m = pos.parse_uci("c3b1");
  auto history = std::make_unique<QuietHistory>();
  history->apply(White, m, 1000, 3);
  CHECK(history->value(White, m, 3) > 0);
  for (int b = 0; b < 3; ++b) CHECK_EQ(history->value(White, m, b), 0);
  CHECK_EQ(history->value(White, m), 0);  // the default bucket is 0
}

// History ageing (the engine survey's D17): each table's age keeps
// keep_quarters / 4 of every entry, rounded toward zero, on both signs;
// 4 quarters leaves it as it was and 0 clears it.
TEST_CASE("ordering", "history ageing: every table keeps its quarters of each entry") {
  Position pos;
  CHECK(pos.set_fen(perft_suite()[1].fen));  // kiwipete
  const Move m = pos.parse_uci("c3b1"), n = pos.parse_uci("a2a3");
  auto quiet = std::make_unique<QuietHistory>();
  auto pairs = std::make_unique<PairHistory[]>(2);
  auto takes = std::make_unique<TakeHistory>();
  quiet->apply(White, m, 1001, 3);
  quiet->apply(Black, n, -999);
  pairs[FollowTable].apply(100, 200, 1001);
  takes->apply(300, -999);
  const int q = quiet->value(White, m, 3), r = quiet->value(Black, n), p = pairs[FollowTable].value(100, 200),
            t = takes->value(300);
  CHECK(q > 0 && r < 0 && p > 0 && t < 0);
  quiet->age(4);
  pairs[FollowTable].age(4);
  takes->age(4);
  CHECK(quiet->value(White, m, 3) == q && quiet->value(Black, n) == r);
  CHECK(pairs[FollowTable].value(100, 200) == p && takes->value(300) == t);
  quiet->age(3);
  pairs[FollowTable].age(2);
  takes->age(1);
  CHECK_EQ(quiet->value(White, m, 3), q * 3 / 4);
  CHECK_EQ(quiet->value(Black, n), r * 3 / 4);  // toward zero: -749 for -999
  CHECK_EQ(pairs[FollowTable].value(100, 200), p / 2);
  CHECK_EQ(takes->value(300), t / 4);
  CHECK_EQ(quiet->value(White, m, 0), 0);  // an empty entry stays empty
  quiet->age(0);
  CHECK_EQ(quiet->value(White, m, 3), 0);
}

// The selector reads the threat bucket only when threat-aware: in kiwipete
// the knight on c3, attacked by the b4 pawn, has a bonus for c3b1 in that
// move's bucket, and another quiet has a smaller bonus in bucket 0. With
// the buckets, c3b1 comes before it; without them c3b1 reads bucket 0,
// where it has nothing, so the other quiet comes first.
TEST_CASE("ordering", "threat buckets: the selector orders quiets by the move's own bucket") {
  Position pos;
  CHECK(pos.set_fen(perft_suite()[1].fen));  // kiwipete
  const Bitboard attacked = pos.attacked_squares(Black);
  const Move escape = pos.parse_uci("c3b1");
  CHECK(threat_bucket(attacked, escape) >= 2);  // its from-square is attacked
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  Move other = NoMove;
  for (Move m : legal)
    if (!m.is_capture() && !m.is_promotion() && threat_bucket(attacked, m) == 0) {
      other = m;
      break;
    }
  CHECK(!other.is_none());
  auto history = std::make_unique<QuietHistory>();
  history->apply(White, escape, 1600, threat_bucket(attacked, escape));
  history->apply(White, other, 800, 0);
  for (bool aware : {false, true}) {
    MoveSelector s;
    s.start_main(pos, NoMove, history.get(), nullptr, NoArrival, NoArrival, nullptr, aware);
    const std::vector<Move> got = drain(s);
    const auto at = [&](Move m) { return std::find(got.begin(), got.end(), m) - got.begin(); };
    CHECK_MSG((at(escape) < at(other)) == aware, "aware " << aware);
    // The selector's threat set is the opponent's attacks, and 0 without the buckets.
    CHECK_EQ(s.attacked_by_opponent(), aware ? attacked : Bitboard{0});
  }
}

// The int16 headroom of the quiet score at the reply and follow weights'
// highest values (owner, 2026-11-09: ReplyWeight's range widened to 12 after
// this check; final-retune.md). The selector sums in int and clamps to int16
// before the narrowing store, so the int sum must be exact: at most
// HistoryMax * (4 + 12 + 8) / 4 = 60,000 in magnitude, far inside int.
TEST_CASE("ordering", "the quiet score's sum is exact in int at the weights' highest") {
  const int reply = find_param("ReplyWeight")->highest;
  const int follow = find_param("FollowWeight")->highest;
  CHECK(std::int64_t{HistoryMax} * std::max(reply, follow) <= INT32_MAX);   // each product
  CHECK(std::int64_t{HistoryMax} * (4 + reply + follow) / 4 <= INT32_MAX);  // the sum
  // One reply entry alone at the highest weight still fits int16 unclamped
  // (30,000 at 12): only sums of tables reach the clamp.
  CHECK(HistoryMax * reply / 4 <= INT16_MAX);
}

#ifdef FORK_TUNE
// Tuning builds: with ReplyWeight and FollowWeight at their highest values,
// the score is the exact sum clamped to [-INT16_MAX, INT16_MAX] for entries
// at both limits, and the selector still orders quiets by it.
TEST_CASE("ordering", "tuning build: the quiet score at the reply and follow weights' highest") {
  const int reply = find_param("ReplyWeight")->highest;
  const int follow = find_param("FollowWeight")->highest;
  CHECK(set_param("ReplyWeight", reply));
  CHECK(set_param("FollowWeight", follow));
  CHECK_EQ(ReplyWeight, 12);
  Position pos;
  CHECK(pos.set_fen(perft_suite()[0].fen));
  const Move m = pos.parse_uci("g1f3");
  const int slot = pair_slot(pos.piece_at(m.from()), m.to());
  const int arrival = pair_slot(static_cast<Piece>(Black * 8 + Knight), static_cast<Square>(42));
  const int follow_arrival = pair_slot(static_cast<Piece>(White * 8 + Bishop), static_cast<Square>(19));
  for (const int sign : {1, -1}) {
    auto history = std::make_unique<QuietHistory>();
    auto pairs = std::make_unique<PairHistory[]>(2);
    pairs[ReplyTable].apply(arrival, slot, sign * HistoryMax);
    CHECK_EQ(quiet_order_score(pos, m, history.get(), pairs.get(), arrival, NoArrival),
             sign * HistoryMax * reply / 4);  // 30,000: unclamped
    history->apply(White, m, sign * HistoryMax);
    pairs[FollowTable].apply(follow_arrival, slot, sign * HistoryMax);
    const std::int64_t exact = std::int64_t{sign} * HistoryMax * (4 + reply + follow) / 4;
    CHECK_EQ(quiet_order_score(pos, m, history.get(), pairs.get(), arrival, follow_arrival),
             static_cast<int>(std::clamp<std::int64_t>(exact, -INT16_MAX, INT16_MAX)));
    MoveSelector s;
    s.start_main(pos, NoMove, history.get(), pairs.get(), arrival, follow_arrival);
    // The start position has no captures: the saturated move comes first
    // with the maximum score and last with the minimum.
    const std::vector<Move> got = drain(s);
    CHECK(!got.empty() && (sign > 0 ? got.front() : got.back()) == m);
  }
  for (const TuneParam& p : param_table()) CHECK(set_param(p.name, p.default_value));
}
#endif

}  // namespace forkeng::test
