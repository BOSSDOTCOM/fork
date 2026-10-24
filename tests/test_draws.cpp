// Draw rules: repetition counting and insufficient material.
#include <algorithm>
#include <array>
#include <string>
#include <vector>

#include "core/position.hpp"
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
