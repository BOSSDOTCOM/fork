#include "core/position.hpp"
#include "harness.hpp"
#include "suite.hpp"

using namespace fork;
using namespace fork::test;

namespace {

Key key_of(std::string_view fen) {
  Position p;
  bool ok = p.set_fen(fen);
  CHECK_MSG(ok, fen);
  return p.key();
}

}  // namespace

TEST_CASE("fen", "round trip") {
  std::vector<std::string_view> fens;
  for (const PerftPosition& pp : perft_suite()) fens.push_back(pp.fen);
  fens.emplace_back("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3");
  fens.emplace_back("4k3/8/8/8/8/8/8/4K2R w K - 37 90");
  fens.emplace_back("r3k3/8/8/8/8/8/8/4K3 b q - 0 1");
  fens.emplace_back("4k3/8/8/4pP2/8/8/8/4K3 w - e6 0 1");
  for (std::string_view fen : fens) {
    Position p;
    std::string error;
    CHECK_MSG(p.set_fen(fen, &error), fen << ": " << error);
    CHECK_MSG(p.fen() == fen, fen << " -> " << p.fen());
    CHECK_EQ(p.key(), p.compute_state().key);
  }
}

TEST_CASE("fen", "optional move counters") {
  Position p;
  CHECK(p.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"));
  CHECK_EQ(p.fen(), std::string(Position::StartFen));
  CHECK(p.set_fen("  rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR   w KQkq - 0 1  "));
  CHECK_EQ(p.fen(), std::string(Position::StartFen));
}

TEST_CASE("fen", "malformed input is rejected without changing the position") {
  const char* bad[] = {
      "",
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",                 // too few fields
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0",      // 5 fields
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP w KQkq - 0 1",             // 7 ranks
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR/8 w KQkq - 0 1",  // 9 ranks
      "rnbqkbnr/pppppppp/9/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",    // bad digit
      "rnbqkbnr/ppppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",   // rank too long
      "rnbqkbnr/ppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",     // rank too short
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNX w KQkq - 0 1",    // bad piece
      "rnbq1bnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQ - 0 1",      // no black king
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBKKBNR w kq - 0 1",      // two white kings
      "rnbqkbnr/pppppppp/8/8/8/P7/PPPPPPPP/RNBQKBNR w KQkq - 0 1",   // 9 pawns
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNP w Qkq - 0 1",     // pawn on rank 1
      "4k3/8/8/8/8/8/8/4K2R x K - 0 1",                              // bad side
      "4k3/8/8/8/8/8/8/4K2R w KK - 0 1",                             // repeated right
      "4k3/8/8/8/8/8/8/4K2R w Q - 0 1",                              // right without rook
      "4k3/8/8/8/8/8/8/3K3R w K - 0 1",                              // right without king
      "4k3/8/8/8/8/8/8/4K2R w KX - 0 1",                             // bad castling char
      "4k3/8/8/8/8/8/8/4K2R w K e9 0 1",                             // bad ep square
      "4k3/8/8/8/8/8/8/4K2R w K e3 0 1",                             // ep on wrong rank
      "4k3/8/8/8/8/8/8/4K2R w K e6 0 1",                             // ep without pushed pawn
      "4k3/4p3/8/4pP2/8/8/8/4K3 w - e6 0 1",                         // ep with occupied origin
      "4k3/8/8/8/8/8/8/4K2R w K - -1 1",                             // negative clock
      "4k3/8/8/8/8/8/8/4K2R w K - x 1",                              // non-numeric clock
      "4k2R/8/8/8/8/8/8/4K3 w - - 0 1",                              // side not to move in check
  };
  Position p;
  const std::string before = p.fen();
  for (const char* fen : bad) {
    std::string error;
    CHECK_MSG(!p.set_fen(fen, &error) && !error.empty(), "accepted: " << fen);
    CHECK_EQ(p.fen(), before);
  }
}

TEST_CASE("zobrist_ep", "ep square counts only when a legal ep capture exists") {
  // After 1.e4 no black pawn can capture: the ep square is dropped.
  const char* no_capturer = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1";
  Position p;
  CHECK(p.set_fen(no_capturer));
  CHECK_EQ(p.ep_square(), NoSquare);
  CHECK_EQ(p.key(), key_of("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"));

  // e5xf6 is legal: the ep square is kept and changes the key.
  const char* usable = "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3";
  CHECK(p.set_fen(usable));
  CHECK_EQ(p.ep_square(), 45);
  CHECK(p.key() != key_of("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3"));

  // b5xc6 would expose the king on a5 to the rook on h5: unusable.
  const char* pinned = "8/8/8/KPp4r/8/8/8/7k w - c6 0 1";
  CHECK(p.set_fen(pinned));
  CHECK_EQ(p.ep_square(), NoSquare);
  CHECK_EQ(p.key(), key_of("8/8/8/KPp4r/8/8/8/7k w - - 0 1"));

  // e5 is pinned on the b8-h2 diagonal, but e5xd6 stays on it: usable.
  CHECK(p.set_fen("1b5k/8/8/3pP3/8/8/7K/8 w - d6 0 1"));
  CHECK_EQ(p.ep_square(), 43);

  // e5 is pinned on the a1-h8 diagonal and e5xd6 leaves it: unusable.
  CHECK(p.set_fen("k6b/8/8/3pP3/8/8/8/K7 w - d6 0 1"));
  CHECK_EQ(p.ep_square(), NoSquare);
  CHECK_EQ(p.key(), key_of("k6b/8/8/3pP3/8/8/8/K7 w - - 0 1"));
}

TEST_CASE("zobrist_ep", "make sets the ep square under the same rule") {
  Position p;
  p.make(p.parse_uci("e2e4"));
  CHECK_EQ(p.ep_square(), NoSquare);
  CHECK_EQ(p.key(), key_of("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"));
  for (const char* mv : {"a7a6", "e4e5", "d7d5"}) p.make(p.parse_uci(mv));
  CHECK_EQ(p.ep_square(), 43);  // d6
  CHECK_EQ(p.fen(), std::string("rnbqkbnr/1pp1pppp/p7/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3"));
  CHECK_EQ(p.key(), p.compute_state().key);
}
