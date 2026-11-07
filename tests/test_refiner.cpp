// SPDX-License-Identifier: GPL-3.0-or-later

// The Boundary Refiner's oracle (ideas.md 59, step 2; oracle builds only,
// FORK_REFINER_NET): the plain base network read into the architecture-6
// layout, its evaluation without the exposure plane, the embedded refiner,
// the window gate at its edges, and the refined value replacing the base one
// at a gated quiescence site and staying in the TT. The oracle's searches
// as a whole are checked by bench: with the gate off it equals the base
// network's own bench (refiner_off_bench), and both refiner schedules give
// the same bench (refiner_lazy_bench); the refiner's inference by its
// trainer parity file (nnue_netcheck_refiner).
//
// Test positions: tests/nnue/parity.epd (its sources are cited in the file),
// filtered at run time.
#include <atomic>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iterator>
#include <memory>
#include <string>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "eval/eval.hpp"
#include "eval/nnue/accumulator.hpp"
#include "eval/nnue/net_file.hpp"
#include "eval/nnue/refiner_net.hpp"
#include "harness.hpp"
#include "search/refiner_gate.hpp"
#include "search/searcher.hpp"

namespace forkeng {
extern const unsigned char* const refiner_net_bytes;
extern const std::size_t refiner_net_size;
}  // namespace forkeng

namespace forkeng::test {

TEST_CASE("refiner", "the reader takes a plain S-512 file into this layout, exposure rows zero") {
  // A net in this build's layout with small random weights (inside the
  // reader's bounds): `inputs` rows of them, the rest zero.
  auto random_rows = [](std::uint64_t seed, int inputs) {
    auto net = std::make_unique<NetFile>();
    std::uint64_t rng = seed;
    auto draw = [&](int span) { return static_cast<int>(splitmix_next(rng) % (2 * span + 1)) - span; };
    for (int p = 0; p < 25; ++p) net->phase_table[p] = static_cast<std::uint8_t>(p * 8 / 25);
    net->inputs = inputs;
    for (int i = 0; i < NetInputs * NetHidden; ++i)
      net->ft_weights[i] = static_cast<std::int16_t>(i < inputs * NetHidden ? draw(400) : 0);
    for (auto& b : net->ft_bias) b = static_cast<std::int16_t>(draw(2000));
    for (auto& row : net->out_weights)
      for (auto& w : row) w = static_cast<std::int16_t>(draw(128));
    for (auto& b : net->out_bias) b = draw(100000);
    net->scale = 400;
    return net;
  };
  auto plain = random_rows(1, NetPieceSquares);
  std::vector<std::uint8_t> bytes = write_net_file(*plain);
  bytes[12] = 2;  // architecture 2: a plain S-512 file (the header's u32 at byte 12)
  auto back = std::make_unique<NetFile>();
  for (auto& w : back->ft_weights) w = 77;  // not zero before the read
  std::string error;
  CHECK_MSG(read_net_file(bytes, *back, error), error);
  CHECK_EQ(back->inputs, NetPieceSquares);
  CHECK(std::memcmp(back->ft_weights, plain->ft_weights, sizeof plain->ft_weights) == 0);  // rows 768+ zero
  // An architecture-2 header over a full S512+X payload is not a plain file.
  auto full = random_rows(2, NetPieceSquares + NetExposureRows);
  bytes = write_net_file(*full);
  bytes[12] = 2;
  CHECK(!read_net_file(bytes, *back, error));
  // Any other architecture is still refused.
  bytes[12] = 8;
  CHECK(!read_net_file(bytes, *back, error));
}

TEST_CASE("refiner", "a plain net's evaluation never adds the exposure rows") {
  // A net in this build's layout with small random weights (inside the
  // reader's bounds): `inputs` rows of them, the rest zero.
  auto random_rows = [](std::uint64_t seed, int inputs) {
    auto net = std::make_unique<NetFile>();
    std::uint64_t rng = seed;
    auto draw = [&](int span) { return static_cast<int>(splitmix_next(rng) % (2 * span + 1)) - span; };
    for (int p = 0; p < 25; ++p) net->phase_table[p] = static_cast<std::uint8_t>(p * 8 / 25);
    net->inputs = inputs;
    for (int i = 0; i < NetInputs * NetHidden; ++i)
      net->ft_weights[i] = static_cast<std::int16_t>(i < inputs * NetHidden ? draw(400) : 0);
    for (auto& b : net->ft_bias) b = static_cast<std::int16_t>(draw(2000));
    for (auto& row : net->out_weights)
      for (auto& w : row) w = static_cast<std::int16_t>(draw(128));
    for (auto& b : net->out_bias) b = draw(100000);
    net->scale = 400;
    return net;
  };
  auto parity_fens = [] {  // the parity file's positions (FEN before the bar)
    std::vector<Position> out;
    std::ifstream in(std::string(FORK_SOURCE_DIR) + "/tests/nnue/parity.epd");
    std::string line;
    while (std::getline(in, line)) {
      if (line.empty() || line[0] == '#') continue;
      if (line.back() == '\r') line.pop_back();
      Position pos;
      if (pos.set_fen(line.substr(0, line.find('|')))) out.push_back(pos);
    }
    return out;
  };
  auto from_scratch = [](const NetFile& net, const Position& pos) {
    Accumulator acc;
    accumulate_board(net, pos, acc);
    return evaluate_position(net, acc, pos);
  };
  auto plain = random_rows(3, NetPieceSquares);
  auto loud = std::make_unique<NetFile>(*plain);  // the same, with exposure rows set
  std::uint64_t rng = 5;
  for (int i = NetPieceSquares * NetHidden; i < NetInputs * NetHidden; ++i)
    loud->ft_weights[i] = static_cast<std::int16_t>(static_cast<int>(splitmix_next(rng) % 801) - 400);
  int exposed = 0, differs = 0;
  auto full = std::make_unique<NetFile>(*loud);  // the same rows read as an S512+X net
  full->inputs = NetPieceSquares + NetExposureRows;
  for (const Position& pos : parity_fens()) {
    if (!exposed_pieces(pos)) continue;
    ++exposed;
    CHECK_MSG(from_scratch(*loud, pos) == from_scratch(*plain, pos), pos.fen());
    differs += from_scratch(*full, pos) != from_scratch(*plain, pos);  // the rows do matter
  }
  CHECK(exposed > 100);
  CHECK(differs > exposed / 2);
}

TEST_CASE("refiner", "the embedded refiner is FORK_REFINER_NET's file; the base is read plain") {
  std::ifstream in(FORK_REFINER_NET, std::ios::binary);
  const std::vector<unsigned char> file((std::istreambuf_iterator<char>(in)),
                                        std::istreambuf_iterator<char>());
  CHECK_EQ(file.size(), refiner_net_size);
  CHECK(file.size() == refiner_net_size && std::memcmp(file.data(), refiner_net_bytes, file.size()) == 0);
  CHECK_EQ(refiner_net().inputs, NetPieceSquares + NetExposureRows);
  CHECK_EQ(embedded_net().inputs, NetPieceSquares);
}

TEST_CASE("refiner", "the window gate at its edges") {
  const Position pos;
  RefinerGate g;
  g.margin_main = 25;
  g.margin_quiesce = 10;
  auto fires = [&](int eval, int alpha, int beta, bool quiesce) {
    return gate_fires(g, GateSite{pos, eval, alpha, beta, quiesce ? 0 : 3, 5, quiesce});
  };
  // Inclusive margins, the nearer finite bound, each kind its own margin.
  CHECK(fires(125, 100, 101, false));   // 24 from beta
  CHECK(fires(126, 100, 101, false));   // 25
  CHECK(!fires(127, 100, 101, false));  // 26
  CHECK(fires(75, 100, 101, false));    // 25 below alpha
  CHECK(!fires(74, 100, 101, false));
  CHECK(fires(111, 100, 101, true));  // 10
  CHECK(!fires(112, 100, 101, true));
  CHECK(fires(100, 50, 150, false) == false);  // 50 from either bound
  // One finite bound: that one counts; none: never.
  CHECK(fires(120, -ScoreInfinite, 100, false));
  CHECK(!fires(130, -ScoreInfinite, 100, false));
  CHECK(fires(-120, -100, ScoreInfinite, false));
  CHECK(!fires(0, -ScoreInfinite, ScoreInfinite, false));
  CHECK(!fires(TbWinScore, mated_score(3), mate_score(4), false));
  // A margin of -1 never fires, even on the bound.
  g.margin_main = -1;
  CHECK(!fires(100, 100, 101, false));
  CHECK(fires(100, 100, 101, true));
}

TEST_CASE("refiner", "a gated quiescence site uses the refiner's value, and the TT keeps it") {
  auto parity_fens = [] {  // the parity file's positions (FEN before the bar)
    std::vector<Position> out;
    std::ifstream in(std::string(FORK_SOURCE_DIR) + "/tests/nnue/parity.epd");
    std::string line;
    while (std::getline(in, line)) {
      if (line.empty() || line[0] == '#') continue;
      if (line.back() == '\r') line.pop_back();
      Position pos;
      if (pos.set_fen(line.substr(0, line.find('|')))) out.push_back(pos);
    }
    return out;
  };
  auto from_scratch = [](const NetFile& net, const Position& pos) {
    Accumulator acc;
    accumulate_board(net, pos, acc);
    return evaluate_position(net, acc, pos);
  };
  std::vector<TtBucket> buckets(16384);
  TransTable table;
  auto searcher = std::make_unique<Searcher>(table);
  const std::atomic<bool> stop{false};
  searcher->refiner_gate = RefinerGate{};  // the build's margins: quiescence 10 cp
  int tested = 0;
  for (Position pos : parity_fens()) {
    // A quiet position: no capture or promotion, not in check, so the
    // quiescence search's value is its stand-pat evaluation.
    if (pos.in_check()) continue;
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    bool quiet = legal.size() > 0;
    for (const Move m : legal) quiet = quiet && !m.is_capture() && !m.is_promotion();
    if (!quiet) continue;
    const int base = from_scratch(embedded_net(), pos);
    const int refined = from_scratch(refiner_net(), pos);
    if (refined <= base || refined - base >= 290) continue;  // above it, so the TT's eval slot is read back
    ++tested;
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
    // Far from the window: the base network's value.
    CHECK_MSG(searcher->probe_zero_window(pos, base + 300, 0, stop) == base, pos.fen());
    CHECK_EQ(searcher->refiner_tally().quiesce_calls, 0u);
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    // On the window (alpha = base): the refiner's, computed from scratch here.
    CHECK_MSG(searcher->probe_zero_window(pos, base + 1, 0, stop) == refined, pos.fen());
    CHECK_EQ(searcher->refiner_tally().quiesce_calls, 1u);
    // Again far from the window, the TT entry from that search (a lower
    // bound below this window, so no cutoff): its stored evaluation is the
    // refined one, reused without a call.
    CHECK_MSG(searcher->probe_zero_window(pos, base + 300, 0, stop) == refined, pos.fen());
    CHECK_EQ(searcher->refiner_tally().quiesce_calls, 0u);
    CHECK_EQ(searcher->refiner_tally().quiesce_evals, 0u);
  }
  CHECK(tested >= 10);
}

}  // namespace forkeng::test
