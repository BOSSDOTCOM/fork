// SPDX-License-Identifier: GPL-3.0-or-later

// Elementary mates (docs/ideas.md 203; rare-ideas survey rare.md RI-41): Fork
// plays both sides of basic won endings from fixed starting positions and the
// attacker must deliver mate before the fifty-move rule, a repetition or any
// other draw ends the game, and within a margin over the fastest mate. Another
// engine was once slow to mate in KRvK and KBNvK after a TT change; this
// catches a TT, table-use, pruning or evaluation change that breaks the
// conversion of such endings.
//
// Positions: constructed by tools/make_mate_positions.py (seed 203, 20,000
// random placements per ending, kept only if python-chess's Syzygy prober,
// on the lichess mirror's tables that CMakeLists.txt pins, gives the side to
// move a win, WDL 2), never typed. Per ending: "far", the largest distance to
// zero (DTZ) drawn; "centre", the largest DTZ with the defending king on d4,
// e4, d5 or e5; "typical", the median win by DTZ, colour-flipped so Black
// attacks. The rows below are the script's output as printed. Each start is
// checked again here with Fathom (a win for the side to move), so a wrong row
// fails. Against a lone king the DTZ is the fastest mate in plies (the only
// zeroing moves there are the lone king's captures, which draw; the tables'
// DTZ can be one ply over); with a defending pawn or rook it is the distance
// to the next capture or pawn move.
//
// Games: each side has its own searcher and TT (2 MB, kept for the whole
// game, as in a real game), every move a fixed node budget, so the games are
// deterministic and the same on every preset (bench parity). The defender
// always uses the tables, so every ending a start can reach by captures and
// promotions must have its tables (WDL and DTZ) in the pinned set: the first
// case checks that, by material and by probing every capture or pawn move in
// the first two plies (until 2026-11-17 the set lacked KQvKN, KQvKB and
// KQvKQ, which the KQvKP far start's defender reaches by promoting, d1=N
// among them). Two variants of games:
// - Without the attacker's tables (use_tables off, so the search and the
//   evaluation must convert on their own): the endings Fork converts at the
//   budget, KQvK, KRvK and KQvKP, must end in mate, against a lone king
//   within MarginMoves of the fastest mate.
// - With the attacker's tables: all 18 starts must end in mate before the
//   fifty-move rule (the distance-to-zero root ranking guarantees it), and
//   against a lone king within TableMarginMoves of the fastest mate (since
//   use_fastest_table_win, owner 2026-11-15).
//
// "The fastest mate" is the start's DTZ from the tables, in moves (half its
// plies, rounded up): the length of the mate when the attacker shortens and
// the defender lengthens the distance to zero at every move. Against a lone
// king the only zeroing moves are the lone king's captures, which draw, so
// it is the distance to mate under best play by both sides (DTM), up to the
// tables' DTZ rounding (one ply). Fork's defender searches and does not
// always resist longest, so a game can mate in fewer moves.
//
// Measured on 6ed1f87 (clang-release, 2026-11-15; every start, both
// variants, at 5k, 20k, 100k and 300k nodes a move for both sides):
// - Without the attacker's tables Fork never mated in KBNvK (any start) or in
//   KQvKR's far and centre starts at any of the four budgets: the fifty-move
//   rule ended them (or a stalemate, or a piece given away once the rule's
//   draw was inside the search). KBBvK converted from all three starts only
//   at 100k (in 30, 28 and 47 of the 50 moves), from one or two at 20k and
//   300k, from none at 5k. Those endings are left out of the first variant,
//   which asserts only what Fork did at both budgets tried from 100k up
//   (KQvKP's far start failed at 5k and 20k).
// - With the tables Fork mated in every start at every budget, but in KBNvK
//   always, and in KBBvK in 11 of the 12 games, on the 50th move, the last
//   the rule allows (the ranking keeps every move that still wins under the
//   rule, and the search sees no faster mate), so the second variant asserted
//   the rule only.
// With use_fastest_table_win on (2026-11-15, sprt/tb-root-dtz), at 20k nodes:
// KBNvK mated in 29, 31 and 20 moves (fastest 32, 31, 25), KBBvK in 13, 16
// and 13 (17, 17, 12), KQvKR in 27, 30 and 9 (52, 56 and 13 before), and
// KQvK and KRvK at or under the fastest. At 5k, 20k, 100k and 300k every
// lone-king start mated at most 1 move over the fastest (KBBvK centre at 5k,
// KBBvK typical at 20k, KBNvK centre at 100k). Without the switch the
// tightened second variant fails 10 starts: the six KBBvK and KBNvK starts
// (mate on the 50th move), the three KRvK starts and KQvK typical.
// Run time: 13 s in clang-release, 35 s in gcc-debug (2026-11-15), so a fast
// test; both builds played the same games, move for move.
// Re-measured with KQvKN, KQvKB and KQvKQ added (2026-11-17, phase-4 at
// 7ee56d5, default net r3kr1, clang-release, the suite's own budgets only):
// - without the attacker's tables (100k): KQvK far 13, centre 9, typical 7
//   moves (fastest 10, 9, 6); KRvK 16, 16, 11 (16, 16, 10); KQvKP far 30
//   (22 without the three tables), centre 12, typical 8;
// - with them (20k): KQvK 9, 9, 6; KRvK 15, 13, 9; KBBvK 13, 16, 13; KBNvK
//   29, 31, 20; KQvKP 20, 9, 8; KQvKR 27, 30, 9 moves: all the same as
//   without the three tables (KBBvK, KBNvK and KQvKR as on 2026-11-15).
// Without the three tables the reachability case fails (KQvKN, KQvKB, KQvKQ
// missing; Fathom answers none of the far start's d1=Q, d1=B, d1=N
// positions) and the games still pass. Run time 10 s in clang-release.
//
// Fault injection (2026-11-15, each reverted): the root ranking by the tables
// switched off fails 6 starts of the second variant (KBBvK and KBNvK reach
// the fifty-move rule); the attacker's TT switched off fails the first (KQvK
// far mated in 26 moves, the fastest 10); a 5k budget fails it too. Mate
// scores that ignore the distance, and TT mate scores stored from the root
// instead of the node, both passed: in these games a mate is found only a
// few moves before it is played, so the eval and the tables steer the rest.
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <memory>
#include <set>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "core/movegen.hpp"
#include "harness.hpp"
#include "search/endgame_tables.hpp"
#include "search/searcher.hpp"

namespace forkeng::test {

namespace {

struct MateStart {
  const char* ending;
  const char* label;
  const char* fen;
  int dtz;  // plies, from python-chess's prober (tools/make_mate_positions.py)
};

// tools/make_mate_positions.py .cache/syzygy345 --seed 203 --draws 20000
// (python-chess 1.11.2), its output verbatim.
constexpr MateStart Starts[] = {
    // KQvK: 11656 wins in 20000 draws
    {"KQvK", "far", "8/8/3k4/8/8/8/6Q1/7K w - - 0 1", 19},
    {"KQvK", "centre", "5QK1/8/8/8/3k4/8/8/8 w - - 0 1", 17},
    {"KQvK", "typical", "3K4/8/q7/8/8/8/1k6/8 b - - 0 1", 11},
    // KRvK: 14076 wins in 20000 draws
    {"KRvK", "far", "1K6/2R5/3k4/8/8/8/8/8 w - - 0 1", 31},
    {"KRvK", "centre", "1K6/8/8/3k4/8/2R5/8/8 w - - 0 1", 31},
    {"KRvK", "typical", "4r3/1K6/8/8/5k2/8/8/8 b - - 0 1", 19},
    // KBBvK: 6556 wins in 20000 draws
    {"KBBvK", "far", "3B4/8/3k4/8/6B1/8/8/K7 w - - 0 1", 34},
    {"KBBvK", "centre", "5B2/8/8/8/3k4/3B4/8/K7 w - - 0 1", 34},
    {"KBBvK", "typical", "6b1/8/7K/1k6/8/8/1b6/8 b - - 0 1", 24},
    // KBNvK: 14133 wins in 20000 draws
    {"KBNvK", "far", "8/8/8/6B1/6k1/8/8/N6K w - - 0 1", 64},
    {"KBNvK", "centre", "1N6/8/8/4k3/8/8/4B3/7K w - - 0 1", 62},
    {"KBNvK", "typical", "3b4/8/2K5/8/3k4/8/n7/8 b - - 0 1", 50},
    // KQvKP: 8767 wins in 20000 draws
    {"KQvKP", "far", "K7/8/7Q/8/8/8/2kp4/8 w - - 0 1", 45},
    {"KQvKP", "centre", "2Q5/8/8/4p3/3k4/8/8/K7 w - - 0 1", 11},
    {"KQvKP", "typical", "8/8/5K2/8/8/4k3/6P1/3q4 b - - 0 1", 3},
    // KQvKR: 11628 wins in 20000 draws
    {"KQvKR", "far", "8/8/6Q1/8/8/2k5/3r4/K7 w - - 0 1", 59},
    {"KQvKR", "centre", "8/7Q/8/8/3k4/8/4r3/K7 w - - 0 1", 57},
    {"KQvKR", "typical", "1R6/4q3/8/K7/8/8/7k/8 b - - 0 1", 3},
};

// Against a lone king the DTZ is the fastest mate (the header).
constexpr bool lone_king(const MateStart& s) { return std::string_view(s.ending).ends_with("vK"); }

// The endings Fork converts without its tables at NoTableNodes (the header).
bool converts_without_tables(const MateStart& s) {
  const std::string_view e = s.ending;
  return e == "KQvK" || e == "KRvK" || e == "KQvKP";
}

// Nodes a move without the attacker's tables: the smallest budget measured at
// which KQvK, KRvK and KQvKP converted from every start (20k lost KQvKP's far
// start; 300k converted them too).
constexpr std::uint64_t NoTableNodes = 100000;
// Nodes a move with the tables: they decide; every start converted at 5k,
// 20k, 100k and 300k. 20k keeps the case short.
constexpr std::uint64_t TableNodes = 20000;
// Moves over the fastest mate allowed against a lone king without the
// tables: the largest excess measured at 20k-300k was 11 (KRvK far at 300k;
// 3 at 100k); 5k gave 20 (KQvK typical) and fails. With the tables the bound
// was the fifty-move rule only before use_fastest_table_win: KQvK and KRvK
// took up to 28 moves over the fastest there (KQvK far at 5k; 16 for KRvK
// centre at 300k, 8 at 20k).
constexpr int MarginMoves = 15;
// Moves over the fastest mate allowed against a lone king with the tables:
// the root then keeps only the moves of smallest DTZ, so the attacker's own
// play stays within the DTZ, and 2 moves cover the tables' rounding (one ply)
// with one to spare. Measured with use_fastest_table_win: at most 1 over at
// 5k-300k nodes (the header).
constexpr int TableMarginMoves = 2;

std::string tables_dir() { return FORK_SYZYGY345_DIR; }

// One side of the game: its own TT and searcher, kept for the whole game.
struct Player {
  std::vector<TtBucket> buckets;
  TransTable tt;
  std::unique_ptr<Searcher> searcher;
  explicit Player(bool tables) : buckets(TtBuckets) {
    tt.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
    searcher = std::make_unique<Searcher>(tt);
    searcher->switches.use_tables = tables;
  }
  static constexpr std::size_t TtBuckets = (2u << 20) / sizeof(TtBucket);
};

struct Playout {
  bool mated = false;      // the attacker mated
  int attacker_moves = 0;  // moves the attacker played
  const char* end = "?";
  std::string moves;  // the game in UCI notation
};

Playout play_out(const MateStart& s, std::uint64_t nodes, bool attacker_tables) {
  Playout out;
  Position pos;
  if (!pos.set_fen(s.fen)) {
    out.end = "bad FEN";
    return out;
  }
  pos.reserve_plies(512);
  const Color attacker = pos.side_to_move();
  Player attack(attacker_tables), defend(true);
  const std::atomic<bool> stop{false};
  SearchQuota quota;
  quota.nodes = nodes;
  for (;;) {
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    // Mate is checked before the fifty-move rule (DESIGN.md 4.5).
    if (legal.size() == 0) {
      out.mated = pos.in_check() && pos.side_to_move() != attacker;
      out.end = pos.in_check() ? "mate" : "stalemate";
      return out;
    }
    if (pos.fifty_move_reached()) return out.end = "fifty-move rule", out;
    if (pos.repetition_count() >= 3) return out.end = "repetition", out;
    if (pos.insufficient_material()) return out.end = "insufficient material", out;
    Player& mover = pos.side_to_move() == attacker ? attack : defend;
    const SearchResult r = mover.searcher->deliberate(pos, quota, stop, nullptr, nullptr);
    if (r.best == NoMove || !legal.contains(r.best)) return out.end = "no legal move from the search", out;
    if (pos.side_to_move() == attacker) ++out.attacker_moves;
    out.moves += pos.move_to_uci(r.best) + ' ';
    pos.make(r.best);
  }
}

// Every start is a win for the side to move by the tables (Fathom here,
// python-chess in the generator).
bool starts_verified() {
  CHECK(load_endgame_tables(tables_dir()).find("pieces") != std::string::npos);
  bool all = true;
  for (const MateStart& s : Starts) {
    Position pos;
    const bool ok = pos.set_fen(s.fen) && probe_table_wdl(pos) == TableWdl::Win;
    CHECK_MSG(ok, s.ending << ' ' << s.label << ": " << s.fen << " is not a table win for the side to move");
    all = all && ok;
  }
  return all;
}

// Plays every start `pick` keeps; `margin_moves` < 0: the fifty-move rule is
// the only bound.
void run_suite(std::uint64_t nodes, bool attacker_tables, int margin_moves, bool (*pick)(const MateStart&)) {
  if (!starts_verified()) return load_endgame_tables(""), void();
  for (const MateStart& s : Starts) {
    if (!pick(s)) continue;
    const Playout p = play_out(s, nodes, attacker_tables);
    const int fastest = (s.dtz + 1) / 2;  // the attacker's moves in the fastest mate (against a lone king)
    std::cout << "  " << s.ending << ' ' << s.label << ": " << (p.mated ? "mate" : p.end) << " after "
              << p.attacker_moves << " moves";
    if (lone_king(s)) std::cout << " (fastest " << fastest << ")";
    std::cout << '\n';
    CHECK_MSG(p.mated, s.ending << ' ' << s.label << ' ' << s.fen << ": " << p.end << " after "
                                << p.attacker_moves << " moves: " << p.moves);
    if (p.mated && lone_king(s) && margin_moves >= 0)
      CHECK_MSG(p.attacker_moves <= fastest + margin_moves,
                s.ending << ' ' << s.label << ' ' << s.fen << ": mate after " << p.attacker_moves
                         << " moves, the fastest is " << fastest << ": " << p.moves);
  }
  load_endgame_tables("");
}

bool every_start(const MateStart&) { return true; }

// An ending's key, the same whichever side a table's file name lists first
// and in whatever order it lists a side's pieces.
std::string ending_key(std::string a, std::string b) {
  std::sort(a.begin(), a.end());
  std::sort(b.begin(), b.end());
  if (b < a) std::swap(a, b);
  return a + 'v' + b;
}

// The keys of the files with extension `ext` (".rtbw", ".rtbz") in the
// tables' directory.
std::set<std::string> table_keys(const std::string& ext) {
  std::set<std::string> keys;
  for (const auto& entry : std::filesystem::directory_iterator(tables_dir())) {
    if (entry.path().extension() != ext) continue;
    const std::string stem = entry.path().stem().string();
    const std::size_t v = stem.find('v');
    if (v != std::string::npos) keys.insert(ending_key(stem.substr(0, v), stem.substr(v + 1)));
  }
  return keys;
}

// Every ending reachable from `a` against `b` by captures (any piece but a
// king can be taken, by the other king if by nothing else) and promotions (a
// pawn to a queen, rook, bishop or knight), repeated, into `out`.
void reachable_endings(const std::string& a, const std::string& b, std::set<std::string>& out) {
  if (!out.insert(ending_key(a, b)).second) return;
  for (int side = 0; side < 2; ++side) {
    const std::string& mine = side == 0 ? a : b;
    const std::string& theirs = side == 0 ? b : a;
    for (std::size_t i = 0; i < mine.size(); ++i) {
      if (mine[i] == 'K') continue;
      std::string fewer = mine;
      fewer.erase(i, 1);
      reachable_endings(fewer, theirs, out);
      if (mine[i] != 'P') continue;
      for (const char promo : {'Q', 'R', 'B', 'N'}) {
        std::string promoted = mine;
        promoted[i] = promo;
        reachable_endings(promoted, theirs, out);
      }
    }
  }
}

// Fathom answers `pos`, reached from start `s` by `line`, if a capture or a
// pawn move made it (the only positions the search probes: a zero fifty-move
// count).
void check_probed(const Position& pos, const MateStart& s, const std::string& line) {
  if (pos.halfmove_clock() != 0 || popcount(pos.pieces()) <= 2) return;
  CHECK_MSG(probe_table_wdl(pos).has_value(),
            s.ending << ' ' << s.label << " after " << line << ": no table answers " << pos.fen());
}

}  // namespace

// Both sides use the tables (the header), so every ending a game can reach
// needs them; without one, the search there has no answer. From the KQvKP far
// start the defender under-promoted (d1=N) into KQvKN, which the pinned set
// lacked until 2026-11-17.
TEST_CASE("elementary_mates", "every ending a start can reach has its WDL and DTZ tables") {
  std::set<std::string> reach;
  for (const MateStart& s : Starts) {
    const std::string ending = s.ending;
    const std::size_t v = ending.find('v');
    reachable_endings(ending.substr(0, v), ending.substr(v + 1), reach);
  }
  const std::set<std::string> wdl = table_keys(".rtbw"), dtz = table_keys(".rtbz");
  for (const std::string& key : reach) {
    if (key == "KvK") continue;  // two kings: a draw, no table
    CHECK_MSG(wdl.contains(key), key << ": no .rtbw table in " << tables_dir());
    CHECK_MSG(dtz.contains(key), key << ": no .rtbz table in " << tables_dir());
  }
  // The same through Fathom, on real positions: every capture or pawn move in
  // the first two plies from every start (the far KQvKP start's promotions
  // among them) reaches a position the tables answer.
  CHECK(load_endgame_tables(tables_dir()).find("pieces") != std::string::npos);
  for (const MateStart& s : Starts) {
    Position pos;
    CHECK(pos.set_fen(s.fen));
    MoveList first;
    generate<GenMode::Legal>(pos, first);
    for (const Move m1 : first) {
      const std::string line1 = pos.move_to_uci(m1);
      pos.make(m1);
      check_probed(pos, s, line1);
      MoveList second;
      generate<GenMode::Legal>(pos, second);
      for (const Move m2 : second) {
        const std::string line2 = line1 + ' ' + pos.move_to_uci(m2);
        pos.make(m2);
        check_probed(pos, s, line2);
        pos.unmake(m2);
      }
      pos.unmake(m1);
    }
  }
  load_endgame_tables("");
}

TEST_CASE("elementary_mates", "without its tables the attacker mates in KQvK, KRvK and KQvKP") {
  run_suite(NoTableNodes, false, MarginMoves, converts_without_tables);
}

TEST_CASE("elementary_mates", "with its tables the attacker mates in every start, near the fastest mate") {
  run_suite(TableNodes, true, TableMarginMoves, every_start);
}

}  // namespace forkeng::test
