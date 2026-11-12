// SPDX-License-Identifier: GPL-3.0-or-later

// Draw rules: repetition counting, insufficient material and the fifty-move
// clock.
#include <algorithm>
#include <array>
#include <initializer_list>
#include <string>
#include <string_view>
#include <vector>

#include "core/bitboard.hpp"
#include "core/movegen.hpp"
#include "core/position.hpp"
#include "core/revisit.hpp"
#include "core/splitmix.hpp"
#include "core/zobrist.hpp"
#include "harness.hpp"

using namespace forkeng;
using namespace forkeng::test;

namespace {

// Material signatures for the insufficient-material sweep. Each side's
// non-king pieces are written as letters in the order P N D L R Q, where D is
// a bishop on a dark square and L a bishop on a light square.
constexpr std::string_view SignatureLetters = "PNDLRQ";

// Every multiset of up to two letters, in canonical (sorted) order.
std::vector<std::string> small_armies() {
  std::vector<std::string> out{""};
  for (std::size_t i = 0; i < SignatureLetters.size(); ++i) {
    out.emplace_back(1, SignatureLetters[i]);
    for (std::size_t j = i; j < SignatureLetters.size(); ++j)
      out.push_back(std::string{SignatureLetters[i], SignatureLetters[j]});
  }
  return out;
}

// Builds a legal position (White to move, kings on h1 and h8, no checks) with
// the given armies. Squares were chosen so no piece attacks the enemy king:
// dark bishops on a3/a5 (White) and b6/d8 (Black), light bishops on b3/a4 and
// a6/c8, everything else on d3/e3 and d6/e6.
std::string signature_fen(const std::string& white, const std::string& black) {
  char board[8][8];  // [rank][file], rank 0 = rank 1
  for (auto& rank : board) std::fill(std::begin(rank), std::end(rank), '.');
  board[0][7] = 'K';
  board[7][7] = 'k';
  struct Spot {
    int file, rank;
  };
  auto place = [&](const std::string& army, bool is_white) {
    const std::array<Spot, 2> dark =
        is_white ? std::array<Spot, 2>{{{0, 2}, {0, 4}}} : std::array<Spot, 2>{{{1, 5}, {3, 7}}};
    const std::array<Spot, 2> light =
        is_white ? std::array<Spot, 2>{{{1, 2}, {0, 3}}} : std::array<Spot, 2>{{{0, 5}, {2, 7}}};
    const std::array<Spot, 2> other =
        is_white ? std::array<Spot, 2>{{{3, 2}, {4, 2}}} : std::array<Spot, 2>{{{3, 5}, {4, 5}}};
    int used_dark = 0, used_light = 0, used_other = 0;
    for (char letter : army) {
      Spot s{};
      char piece = letter;
      if (letter == 'D') {
        s = dark[used_dark++];
        piece = 'B';
      } else if (letter == 'L') {
        s = light[used_light++];
        piece = 'B';
      } else {
        s = other[used_other++];
      }
      board[s.rank][s.file] = is_white ? piece : static_cast<char>(piece - 'A' + 'a');
    }
  };
  place(white, true);
  place(black, false);
  std::string fen;
  for (int rank = 7; rank >= 0; --rank) {
    int empty = 0;
    for (int file = 0; file < 8; ++file) {
      if (board[rank][file] == '.') {
        ++empty;
        continue;
      }
      if (empty) fen += static_cast<char>('0' + empty);
      empty = 0;
      fen += board[rank][file];
    }
    if (empty) fen += static_cast<char>('0' + empty);
    if (rank) fen += '/';
  }
  return fen + " w - - 0 1";
}

void play(Position& pos, std::initializer_list<const char*> moves) {
  for (const char* uci : moves) {
    Move m = pos.parse_uci(uci);
    CHECK_MSG(!m.is_none(), uci);
    if (!m.is_none()) pos.make(m);
  }
}

}  // namespace

TEST_CASE("draws", "a position repeats after a knight shuffle") {
  Position pos;
  play(pos, {"g1f3", "g8f6", "f3g1", "f6g8"});
  CHECK_EQ(pos.repetition_count(), 2);
  play(pos, {"g1f3", "g8f6", "f3g1", "f6g8"});
  CHECK_EQ(pos.repetition_count(), 3);
}

TEST_CASE("draws", "an irreversible move ends the repetition window") {
  Position pos;
  play(pos, {"g1f3", "g8f6", "f3g1", "f6g8", "e2e4", "e7e5"});
  CHECK_EQ(pos.repetition_count(), 1);
}

// Review M2 (2026-10-23): the window reached back across a null move. The
// start position with Black to move exists only because White passed, so a
// search must not count a later occurrence as a repetition of it.
TEST_CASE("draws", "the repetition window stops at a null move") {
  Position pos;
  pos.make_null();
  play(pos, {"g8f6", "b1c3", "f6g8", "c3b1"});
  CHECK_EQ(pos.repetition_count(), 1);
  // After the null move, ordinary repetitions still count.
  play(pos, {"g8f6", "b1c3", "f6g8", "c3b1"});
  CHECK_EQ(pos.repetition_count(), 2);
}

// Audit-1 Q-3: the fifty-move clock (reset by every capture and pawn move)
// after captures, pawn moves, en passant, a promotion and castling, and the
// rule reached at exactly 100 half-moves. A capture that
// kept the count (mutant M01) passed every test, bench included, and silently
// stopped every endgame-table probe after a capture (probes need a zero
// clock); the rule one ply late (M05) passed too. Every clock value below is
// python-chess 1.11.2's for the same moves (tools/check_search_positions.py).
TEST_CASE("draws", "the halfmove clock resets on captures and pawn moves; the rule binds at exactly 100") {
  struct ClockCase {
    std::string_view fen;
    std::initializer_list<const char*> moves;
    std::initializer_list<int> clocks;  // after each move
  };
  for (const ClockCase& c :
       {ClockCase{Position::StartFen,
                  {"g1f3", "b8c6", "f3e5", "c6e5", "g2g3", "e5f3", "e2f3"},
                  {1, 2, 3, 0, 0, 1, 0}},
        ClockCase{"4k3/8/8/8/8/8/8/R3K2R w K - 37 50", {"e1g1", "e8d7", "f1f7", "d7e6"}, {38, 39, 40, 41}},
        ClockCase{"4k3/8/8/8/8/8/r7/R3K3 w - - 37 50", {"a1a2"}, {0}},
        ClockCase{"4k3/1p6/8/2P5/8/8/8/4K3 b - - 37 50", {"b7b5"}, {0}},
        ClockCase{"4k3/8/8/1pP5/8/8/8/4K3 w - b6 12 50", {"c5b6"}, {0}},
        ClockCase{"4k3/1P6/8/8/8/8/8/4K3 w - - 37 50", {"b7b8q"}, {0}}}) {
    Position pos;
    CHECK_MSG(pos.set_fen(c.fen), c.fen);
    auto clock = c.clocks.begin();
    for (const char* uci : c.moves) {
      play(pos, {uci});
      CHECK_MSG(pos.halfmove_clock() == *clock, c.fen << " after " << uci << ": " << pos.halfmove_clock());
      ++clock;
    }
  }
  Position pos;
  CHECK(pos.set_fen("4k3/8/8/8/8/8/8/R3K3 w - - 99 80"));
  CHECK(!pos.fifty_move_reached());
  play(pos, {"a1a2"});
  CHECK_EQ(pos.halfmove_clock(), 100);
  CHECK(pos.fifty_move_reached());
}

// Insufficient material (DESIGN.md 4.5): every signature with at most two
// non-king pieces per side, bishops on either square colour. The expected
// draws are listed by hand from the rule's prose; every other signature must
// not be a draw. The draws: bare kings; one lone knight against a bare king;
// and boards whose only pieces besides the kings are one to four bishops all
// on squares of one colour (on either side or both).
TEST_CASE("draws", "insufficient material across small material signatures") {
  const std::vector<std::pair<std::string, std::string>> draws = {
      {"", ""},   {"N", ""},   {"", "N"},   {"D", ""},    {"DD", ""},   {"", "D"},  {"", "DD"},
      {"D", "D"}, {"DD", "D"}, {"D", "DD"}, {"DD", "DD"}, {"L", ""},    {"LL", ""}, {"", "L"},
      {"", "LL"}, {"L", "L"},  {"LL", "L"}, {"L", "LL"},  {"LL", "LL"},
  };
  const std::vector<std::string> armies = small_armies();
  CHECK_EQ(armies.size(), std::size_t{28});
  int checked = 0, drawn = 0;
  for (const std::string& white : armies) {
    for (const std::string& black : armies) {
      const std::string fen = signature_fen(white, black);
      Position pos;
      std::string error;
      CHECK_MSG(pos.set_fen(fen, &error), fen << ": " << error);
      const bool expected =
          std::find(draws.begin(), draws.end(), std::make_pair(white, black)) != draws.end();
      CHECK_MSG(pos.insufficient_material() == expected, "K" << white << " v K" << black << " " << fen);
      ++checked;
      drawn += expected;
    }
  }
  CHECK_EQ(checked, 28 * 28);
  CHECK_EQ(drawn, 19);
}

// Upcoming repetition (think tank R12, the engine survey's F7): the
// reversible-move table holds each knight, bishop, rook, queen and king move
// between two squares once (both directions in one entry), counted here from
// the attack tables on an empty board, and find() returns each by its key
// change; key changes no move makes are not found.
TEST_CASE("draws", "revisit table: every reversible piece move once, found by its key change") {
  init();
  // Each pair is reached from both ends, and both colours have the same
  // pairs: the count for one colour from both ends is the table's size.
  int expected = 0;
  for (PieceType t : {Knight, Bishop, Rook, Queen, King})
    for (Square a = 0; a < 64; ++a) expected += popcount(attacks(t, a, 0));
  CHECK_EQ(revisit::stored(), expected);
  CHECK(2 * revisit::stored() <= revisit::Slots);
  int found = 0;
  for (Color c : {White, Black})
    for (PieceType t : {Knight, Bishop, Rook, Queen, King})
      for (Square a = 0; a < 64; ++a)
        for (Square b = 0; b < 64; ++b) {
          if (!(attacks(t, a, 0) & bb(b))) continue;
          const Piece p = piece_of(c, t);
          const int slot =
              revisit::find(zobrist::piece_square[p][a] ^ zobrist::piece_square[p][b] ^ zobrist::side);
          CHECK_MSG(slot >= 0, "piece " << int(p) << " " << int(a) << "-" << int(b));
          if (slot < 0) continue;
          const revisit::Shuttle& m = revisit::moves[slot];
          CHECK(m.piece == p && m.a == std::min(a, b) && m.b == std::max(a, b));
          ++found;
        }
  CHECK_EQ(found, 2 * expected);
  // Without the side key, or for a pawn, no entry.
  CHECK_EQ(revisit::find(zobrist::piece_square[piece_of(White, Knight)][1] ^
                         zobrist::piece_square[piece_of(White, Knight)][18]),
           -1);
  CHECK_EQ(revisit::find(zobrist::piece_square[piece_of(White, Pawn)][12] ^
                         zobrist::piece_square[piece_of(White, Pawn)][20] ^ zobrist::side),
           -1);
  CHECK_EQ(revisit::find(0), -1);
}

// revisit_available against making every legal move: it is true exactly
// when some legal move leads to a position the repetition rule counts
// (repetition_count() >= 2 after it), over random games that mostly shuffle
// pieces (so many positions repeat), from several starts, one with a null
// move in its history.
TEST_CASE("draws", "revisit_available equals some legal move reaching a repetition") {
  static constexpr std::string_view Starts[] = {
      Position::StartFen, "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
      "8/2k5/8/3r4/8/2N5/5K2/3Q4 w - - 0 1", "4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1"};
  std::uint64_t seed = 31;
  int positions = 0, available = 0;
  for (std::string_view fen : Starts)
    for (int game = 0; game < 40; ++game) {
      Position pos;
      CHECK(pos.set_fen(fen));
      if (game % 4 == 3) pos.make_null();
      for (int ply = 0; ply < 80; ++ply) {
        MoveList legal;
        generate<GenMode::Legal>(pos, legal);
        if (legal.size() == 0) break;
        bool brute = false;
        for (std::size_t i = 0; i < legal.size() && !brute; ++i) {
          pos.make(legal[i]);
          brute = pos.repetition_count() >= 2;
          pos.unmake(legal[i]);
        }
        const bool fast = pos.revisit_available();
        CHECK_MSG(fast == brute, pos.fen() << ": revisit_available " << fast << ", by making every move " << brute);
        ++positions;
        available += brute;
        // Mostly a reversible piece move, so positions recur.
        MoveList shuffles;
        for (std::size_t i = 0; i < legal.size(); ++i)
          if (!legal[i].is_capture() && !legal[i].is_promotion() && !legal[i].is_castle() &&
              kind_of(pos.piece_at(legal[i].from())) != Pawn)
            shuffles.add(legal[i]);
        const bool shuffle = shuffles.size() > 0 && splitmix_next(seed) % 10 != 0;
        const MoveList& from = shuffle ? shuffles : legal;
        pos.make(from[splitmix_next(seed) % from.size()]);
      }
    }
  CHECK_MSG(available > 500, "only " << available << " of " << positions << " positions had a move back");
}
