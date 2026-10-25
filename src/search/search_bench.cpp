#include "search/search_bench.hpp"

#include <cassert>
#include <chrono>
#include <memory>
#include <string_view>

#include "search/searcher.hpp"

namespace forkeng {

namespace {

// The CPW perft suite (the same FENs as the perft workload, src/core/bench.cpp,
// checked against chessprogramming.org "Perft Results"), then 40 positions
// sampled from the Lichess CC0 export for January 2013 by
// tools/make_bench_positions.py (seed 20261024; game URLs in the comments;
// docs/ORIGINALITY.md).
constexpr std::string_view BenchFens[] = {
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",                  // perft suite
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",      // perft suite
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",                                 // perft suite
    "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",          // perft suite
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",                 // perft suite
    "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",  // perft suite
    "r2qkbnr/pp1bpppp/2np4/1B6/3pP3/2P2N2/PP3PPP/RNBQK2R w KQkq - 0 6",          // opening,
                                                                           // https://lichess.org/ui2g2idg
    "r2qk2r/pp3pp1/2ppbn1p/2b1p3/3nP3/2NPBNPP/PPP2PB1/R2Q1RK1 w kq - 2 10",  // opening,
                                                                               // https://lichess.org/8gpxwk4e
    "r1bqkbnr/pppp1ppp/2n5/8/3pP3/5N2/PPP2PPP/RNBQKB1R w KQkq - 0 4",        // opening,
                                                                               // https://lichess.org/qgsga9fp
    "rnbqk2r/ppppppbp/5np1/8/2PP4/2N5/PP2PPPP/R1BQKBNR w KQkq - 2 4",        // opening,
                                                                               // https://lichess.org/wreeq43f
    "rnbqkb1r/1p3ppp/p3pn2/2pp4/3P1P2/2P1PN2/PP4PP/RNBQKB1R w KQkq - 0 6",   // opening,
                                                                               // https://lichess.org/546b9giz
    "rnbqk2r/pppp1ppp/5n2/2b1p3/2B1P3/3P3P/PPP2PP1/RNBQK1NR b KQkq - 0 4",   // opening,
                                                                               // https://lichess.org/4didrva6
    "rn1qkbnr/pp2pppp/8/2p5/5Pb1/2N2N2/PPPP2PP/R1BQKB1R w KQkq - 4 6",       // opening,
                                                                               // https://lichess.org/s10mnfdd
    "r4rk1/pp1q1ppp/2nbbn2/2ppp3/8/1P1PP1PP/PBP1NPBK/RN1Q1R2 b - - 6 10",    // opening,
                                                                               // https://lichess.org/p8mm6msj
    "r4rk1/pp1b2pp/4pp2/3p2B1/PPnP4/2N5/5PPP/R4RK1 w - - 0 17",  // middlegame, https://lichess.org/l9vbwjsg
    "4rrk1/1B2qp1p/p5p1/5b2/2Q2p2/7P/PPP2PP1/RN4K1 b - - 0 20",  // middlegame, https://lichess.org/lvgg5cfk
    "r5k1/pp3ppp/8/6r1/1b6/4NB1b/PPP2PPP/R2q1RK1 w - - 0 17",    // middlegame, https://lichess.org/fveyply9
    "1r3rk1/p4ppp/1b2pP2/2p1P3/3p4/PP4N1/1BP3KP/R4R2 b - - 0 22",  // middlegame,
                                                                     // https://lichess.org/awljc558
    "5rk1/pr3p2/4p1pp/5n2/2B5/PP6/1bP3PP/2BRR2K b - - 7 23",  // middlegame, https://lichess.org/0ub1zd6g
    "2r2r1k/1p1b3p/7p/1Pp1pp2/P2p2P1/1P1P1P2/4B3/2R3K1 w - - 0 26",  // middlegame,
                                                                       // https://lichess.org/eoend3kr
    "r6r/p1p3k1/1p1b4/3b2p1/3P4/1P2K3/P1P2R1P/5R2 b - - 0 30",  // middlegame, https://lichess.org/uwo92dr9
    "r4rk1/3q1pp1/2pp3p/1pn1p2Q/p3P3/P2PP2P/1PP3PN/R4RK1 b - - 0 20",  // middlegame,
                                                                         // https://lichess.org/c2wr73hb
    "8/4qp2/2P2k2/6p1/p2Pp1Q1/4P3/6K1/8 w - - 0 49",             // middlegame, https://lichess.org/csdb5yh4
    "1rb3k1/p4ppp/P1p5/2Ppr1q1/8/3BP3/5PPP/R2Q1RK1 w - - 2 20",  // middlegame, https://lichess.org/oh5re6gq
    "r3r1k1/1p4pp/2p2q2/PbP5/1P3P2/3pp1PP/1RR4K/4QB2 w - - 0 42",  // middlegame,
                                                                     // https://lichess.org/g7t0atft
    "5rk1/5p2/3Q4/1BnPp3/3nP1pp/8/1PPN1PPP/R4K2 w - - 5 30",    // middlegame, https://lichess.org/qyz4993n
    "5r2/p1k5/1pp3n1/3pPbPB/3P1P2/1Pr3P1/P7/3K2R1 b - - 1 25",  // middlegame, https://lichess.org/2phg31dj
    "4r1Q1/pp1nkr2/2p1p3/5n2/8/2P3R1/P1P5/2K5 w - - 2 40",      // middlegame, https://lichess.org/s6c9m5ub
    "1k1r4/p2p3p/PpP1p1r1/3nPp2/3P3q/2P2Q1P/3N2P1/R2R2K1 b - - 0 26",  // middlegame,
                                                                         // https://lichess.org/45eeez1k
    "r3qrk1/p4p1p/1p4p1/2pp1PB1/8/2nP3B/P1P3RP/R4K2 w - - 1 25",       // middlegame,
                                                                         // https://lichess.org/kpfydmfl
    "5k2/pp4p1/2p5/5K1P/6P1/8/Pb6/8 b - - 2 37",              // endgame, https://lichess.org/rklpc7mk
    "8/8/2kb1B2/6p1/4P1Pp/1p1K1P1P/8/8 w - - 0 46",           // endgame, https://lichess.org/qbtfy560
    "r1b2k2/ppp3pp/8/4p1N1/8/2P1n3/PPP2PPP/2K4R w - - 0 15",  // endgame, https://lichess.org/e9z2p4yt
    "6k1/5pp1/4pn1p/3p4/1B1N1P2/4P1KP/6P1/8 b - - 2 32",      // endgame, https://lichess.org/yltl47oi
    "3R4/5r1p/6k1/p2R1p2/P6P/1P2B1P1/2P5/2K5 w - - 0 37",     // endgame, https://lichess.org/qz7zxgqr
    "r6b/2R5/2p3kP/pp6/3Pp3/P3B3/BPP5/2K5 w - - 0 33",        // endgame, https://lichess.org/hcc68avw
    "8/5pk1/3p2p1/8/3N1Pp1/7r/6K1/1R6 b - - 0 44",            // endgame, https://lichess.org/syxfdun4
    "8/8/8/4p1k1/4B2p/7K/6P1/8 b - - 5 49",                   // endgame, https://lichess.org/io38twrk
    "8/5k1p/P4b2/1K1Nn3/1P2PN2/r7/8/8 b - - 0 37",            // endgame, https://lichess.org/7adgqrw0
    "8/4Rpkp/2np2p1/2p4n/p1P2P2/P1PK1P2/7P/2B5 b - - 0 26",   // endgame, https://lichess.org/4eaefb3n
    "r1bq1rk1/1p3ppp/p1n5/2P5/5QPb/4P3/P1PP3P/RNB1K1NR w KQ - 1 15",  // check, https://lichess.org/ios3q849
    "rnb1k2r/pppp1p1p/1B4pQ/3N4/2B2P2/8/P1P3PP/q3K2R w Kkq - 0 13",   // check, https://lichess.org/54ztb1ca
    "r3kbnr/pp3ppp/2n1q3/8/6b1/2N2N2/PP1B1PPP/R2QKB1R w KQkq - 5 13",  // check,
                                                                         // https://lichess.org/vntlrdzd
    "8/2r3p1/5k1p/6P1/3pp2P/8/5PKN/b7 b - - 0 32",                    // check, https://lichess.org/zpqi3inb
    "r1b1kbnr/pppp1Npp/8/8/2Bnq3/8/PPPP1P1P/RNBQKR2 w Qkq - 0 7",     // check, https://lichess.org/1fqhjrc0
    "r2qkb1r/pQp2ppp/5n2/1Bn1p3/8/4P3/PPPB1PPP/RN2K2R b KQkq - 4 9",  // check, https://lichess.org/so617xo4
};

constexpr int BenchDepth = 6;

std::uint64_t signature_mix(std::uint64_t signature, std::uint64_t value) {
  signature ^= value;
  signature *= 0x9E3779B97F4A7C15ULL;
  return signature ^ (signature >> 29);
}

}  // namespace

std::span<const std::string_view> search_bench_fens() { return BenchFens; }

SearchBenchResult run_search_bench() {
  SearchBenchResult r{0, 0, 0.0};
  auto searcher = std::make_unique<Searcher>();
  const std::atomic<bool> stop{false};
  SearchLimits limits;
  limits.depth = BenchDepth;
  const auto start = std::chrono::steady_clock::now();
  for (const std::string_view fen : BenchFens) {
    Position pos;
    const bool ok = pos.set_fen(fen);
    assert(ok);
    (void)ok;
    const SearchResult s = searcher->explore(pos, limits, stop, nullptr, nullptr);
    r.nodes += s.nodes;
    r.signature = signature_mix(r.signature, s.nodes);
    r.signature = signature_mix(r.signature, s.best.raw());
    r.signature = signature_mix(r.signature, static_cast<std::uint64_t>(static_cast<std::int64_t>(s.score)));
    r.signature = signature_mix(r.signature, static_cast<std::uint64_t>(s.depth));
  }
  r.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
  return r;
}

}  // namespace forkeng
