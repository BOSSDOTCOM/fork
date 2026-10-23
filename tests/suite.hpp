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

}  // namespace fork::test
