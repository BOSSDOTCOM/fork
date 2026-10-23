// The CPW perft suite (chessprogramming.org "Perft Results"): published
// counts used as test oracles.
#pragma once

#include <cstdint>
#include <string_view>
#include <vector>

namespace fork::test {

struct PerftPosition {
  const char* name;
  std::string_view fen;
  std::vector<std::uint64_t> counts;  // counts[d - 1] = perft(d)
  int release_depth;                  // perft_suite depth in optimized builds
  int debug_depth;                    // perft_suite depth in sanitizer builds
};

inline const std::vector<PerftPosition>& perft_suite() {
  static const std::vector<PerftPosition> suite = {
      {"startpos", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
       {20, 400, 8902, 197281, 4865609, 119060324}, 6, 4},
      {"kiwipete", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
       {48, 2039, 97862, 4085603, 193690690}, 5, 4},
      {"position3", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
       {14, 191, 2812, 43238, 674624, 11030083, 178633661}, 7, 5},
      {"position4", "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
       {6, 264, 9467, 422333, 15833292, 706045033}, 5, 5},
      {"position5", "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
       {44, 1486, 62379, 2103487, 89941194}, 5, 5},
      {"position6", "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
       {46, 2079, 89890, 3894594, 164075551, 6923051137}, 5, 5},
  };
  return suite;
}

struct EdgePosition {
  std::string_view fen;
  std::vector<std::uint64_t> counts;  // perft(1..3), from python-chess 1.11.2 (independent generator)
  const char* what;
};

// Positions where special rules interact. Counts were produced by
// python-chess, an independent move generator, and match Fork.
inline const std::vector<EdgePosition>& edge_positions() {
  static const std::vector<EdgePosition> edges = {
      {"8/8/8/2k5/3Pp3/8/8/4K3 b - d3 0 1",
       {9, 50, 379}, "ep captures the checking pawn"},
      {"8/8/8/KPp4r/8/8/8/7k w - c6 0 1",
       {4, 56, 259}, "ep would expose a rank pin"},
      {"1b5k/8/8/3pP3/8/8/7K/8 w - d6 0 1",
       {6, 46, 282}, "ep along a diagonal pin"},
      {"k6b/8/8/3pP3/8/8/8/K7 w - d6 0 1",
       {3, 21, 135}, "ep off a diagonal pin"},
      {"r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
       {26, 568, 13744}, "all castling"},
      {"r3k2r/8/8/8/8/8/5q2/R3K2R w KQkq - 0 1",
       {2, 75, 1446}, "castling out of check"},
      {"1r2k2r/8/8/8/8/8/8/R3K1R1 b Qk - 0 1",
       {24, 560, 13937}, "castling through attack"},
      {"r3k2r/8/8/8/8/8/8/R3K1r1 w Qkq - 0 1",
       {3, 120, 1774}, "castling into attack"},
      {"4k3/8/8/8/8/8/1p4p1/R3K2R b KQ - 0 1",
       {21, 282, 4716}, "capture-promotions on rook squares"},
      {"4k3/8/8/8/1b6/8/8/r3K2R w K - 0 1",
       {2, 56, 905}, "double check"},
      {"4k3/8/5n2/8/8/8/4r3/4K3 w - - 0 1",
       {3, 62, 205}, "single check"},
      {"n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1",
       {24, 496, 9483}, "promotions and underpromotions"},
      {"R6R/3Q4/1Q4Q1/4Q3/2Q4Q/Q4Q2/pp1Q4/kBNN1KB1 w - - 0 1",
       {218, 99, 19073}, "218 legal moves"},
      {"3Q4/1Q4Q1/4Q3/2Q4R/Q4Q2/3Q4/1Q4Rp/1K1BBNNk w - - 0 1",
       {218, 20, 4072}, "many promoted pieces"},
      {"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
       {20, 400, 8902}, ""},
      {"4k3/8/8/2KPp2q/8/8/8/8 w - e6 0 1",
       {7, 143, 974}, "ep with king on the rank, queen behind"},
      {"8/8/3k4/8/1B1pP3/8/8/4K3 b - e3 0 1",
       {5, 69, 446}, "ep capture that leaves check by bishop"},
  };
  return edges;
}

}  // namespace fork::test
