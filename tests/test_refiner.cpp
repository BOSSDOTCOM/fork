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
#include <algorithm>
#include <atomic>
#include <cmath>
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

#if FORK_NET_ARCH == 6  // the prototype's pair: an S-512 base read plain inside an S512+X build
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
#else  // two networks of one architecture (idea 59 step 3's second opinion): one layout, nothing read plain
TEST_CASE("refiner", "the embedded refiner is FORK_REFINER_NET's file; the base is read plain") {
  std::ifstream in(FORK_REFINER_NET, std::ios::binary);
  const std::vector<unsigned char> file((std::istreambuf_iterator<char>(in)),
                                        std::istreambuf_iterator<char>());
  CHECK_EQ(file.size(), refiner_net_size);
  CHECK(file.size() == refiner_net_size && std::memcmp(file.data(), refiner_net_bytes, file.size()) == 0);
  CHECK_EQ(refiner_net().inputs, embedded_net().inputs);
}
#endif

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
  searcher->refiner_gate.kind = GateKind::Window;
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
    // The blend kind (idea 59 step 3's second opinion): on the window, the mean of the two, toward zero.
    searcher->refiner_gate.kind = GateKind::Blend;
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    CHECK_MSG(searcher->probe_zero_window(pos, base + 1, 0, stop) == (base + refined) / 2, pos.fen());
    CHECK_EQ(searcher->refiner_tally().quiesce_calls, 1u);
    searcher->refiner_gate.kind = GateKind::Window;
  }
  CHECK(tested >= 10);
}

// The controls (owner, 2026-11-07, after setting (a)'s screen).
TEST_CASE("refiner", "the shift gate adds the measured mean at gated sites and never consults the refiner") {
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
  table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  auto searcher = std::make_unique<Searcher>(table);
  const std::atomic<bool> stop{false};
  searcher->refiner_gate = RefinerGate{};  // quiescence margin 10 cp
  searcher->refiner_gate.kind = GateKind::Shift;
  searcher->refiner_gate.shift_millicp = 10776;  // oracle-rates-a's mean refinement
  int tested = 0, plus_one = 0;
  for (Position pos : parity_fens()) {
    if (pos.in_check()) continue;  // a quiet position: the value is the stand-pat evaluation
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    bool quiet = legal.size() > 0;
    for (const Move m : legal) quiet = quiet && !m.is_capture() && !m.is_promotion();
    if (!quiet) continue;
    ++tested;
    const int base = from_scratch(embedded_net(), pos);
    // 10 cp, and one more where the key's hash, modulo a thousand, is below 776.
    const int shift = 10 + (splitmix_finalize(pos.key()) % 1000 < 776 ? 1 : 0);
    plus_one += shift == 11;
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    CHECK_MSG(searcher->probe_zero_window(pos, base + 300, 0, stop) == base, pos.fen());  // far: no call
    CHECK_EQ(searcher->refiner_tally().quiesce_calls, 0u);
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    CHECK_MSG(searcher->probe_zero_window(pos, base + 1, 0, stop) == base + shift, pos.fen());
    CHECK_EQ(searcher->refiner_tally().quiesce_calls, 1u);
    CHECK_EQ(searcher->refiner_tally().shift_sum, shift);
    CHECK_EQ(searcher->refiner_tally().consults, 0u);
  }
  CHECK(tested >= 20);
  CHECK(plus_one > 0 && plus_one < tested);
  // A negative constant: its whole part rounds down and the fraction is added.
  searcher->refiner_gate.shift_millicp = -10776;  // -11, plus 1 at 224 per mille
  for (Position pos : parity_fens()) {
    if (pos.in_check()) continue;
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    bool quiet = legal.size() > 0;
    for (const Move m : legal) quiet = quiet && !m.is_capture() && !m.is_promotion();
    if (!quiet) continue;
    const int base = from_scratch(embedded_net(), pos);
    const int shift = -11 + (splitmix_finalize(pos.key()) % 1000 < 224 ? 1 : 0);
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    CHECK_MSG(searcher->probe_zero_window(pos, base, 0, stop) == base + shift, pos.fen());  // gap 1 to alpha
    CHECK_EQ(searcher->refiner_tally().consults, 0u);
  }
}

TEST_CASE("refiner", "the hashed gate samples by position key at its rates, whatever the window") {
  // Positions: the parity file's, and up to 24 random legal plies from each
  // (a fixed seed).
  std::vector<Position> positions;
  {
    std::ifstream in(std::string(FORK_SOURCE_DIR) + "/tests/nnue/parity.epd");
    std::string line;
    std::uint64_t rng = 59;
    while (std::getline(in, line)) {
      if (line.empty() || line[0] == '#') continue;
      if (line.back() == '\r') line.pop_back();
      Position pos;
      if (!pos.set_fen(line.substr(0, line.find('|')))) continue;
      for (int ply = 0; ply < 24; ++ply) {
        positions.push_back(pos);
        MoveList legal;
        generate<GenMode::Legal>(pos, legal);
        if (legal.size() == 0) break;
        pos.make(legal[splitmix_next(rng) % legal.size()]);
      }
    }
  }
  RefinerGate g;
  g.kind = GateKind::Hashed;
  g.sample_main_ppm = 100374;    // oracle-rates-a's calls per computed evaluation, main search
  g.sample_quiesce_ppm = 58284;  // and quiescence
  int fired_main = 0, fired_quiesce = 0;
  for (const Position& pos : positions) {
    const std::uint64_t h = splitmix_finalize(pos.key()) % 1000000;
    for (const bool quiesce : {false, true}) {
      const bool want = h < static_cast<std::uint64_t>(quiesce ? g.sample_quiesce_ppm : g.sample_main_ppm);
      // On the window, far from it, with no finite bound: the same answer.
      CHECK(gate_fires(g, GateSite{pos, 0, 0, 1, 3, 4, quiesce}) == want);
      CHECK(gate_fires(g, GateSite{pos, 0, 900, 901, 3, 4, quiesce}) == want);
      CHECK(gate_fires(g, GateSite{pos, 0, -ScoreInfinite, ScoreInfinite, 3, 4, quiesce}) == want);
      (quiesce ? fired_quiesce : fired_main) += want;
    }
  }
  const double n = static_cast<double>(positions.size());
  CHECK(n > 5000);
  CHECK_MSG(std::abs(fired_main / n - 0.100374) < 0.012, fired_main / n);
  CHECK_MSG(std::abs(fired_quiesce / n - 0.058284) < 0.01, fired_quiesce / n);
  g.sample_main_ppm = g.sample_quiesce_ppm = 0;  // a rate of zero never fires
  for (const Position& pos : positions) CHECK(!gate_fires(g, GateSite{pos, 0, 0, 1, 3, 4, false}));

  // In a search: a quiet position the hash selects is refined even far from
  // the window, and one it does not select is not, even on the window.
  auto from_scratch = [](const NetFile& net, const Position& pos) {
    Accumulator acc;
    accumulate_board(net, pos, acc);
    return evaluate_position(net, acc, pos);
  };
  std::vector<TtBucket> buckets(16384);
  TransTable table;
  table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  auto searcher = std::make_unique<Searcher>(table);
  const std::atomic<bool> stop{false};
  searcher->refiner_gate.kind = GateKind::Hashed;
  searcher->refiner_gate.sample_quiesce_ppm = 500000;
  int selected = 0, skipped = 0;
  for (Position& pos : positions) {
    if (pos.in_check()) continue;
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    bool quiet = legal.size() > 0;
    for (const Move m : legal) quiet = quiet && !m.is_capture() && !m.is_promotion();
    if (!quiet) continue;
    const int base = from_scratch(embedded_net(), pos);
    const int refined = from_scratch(refiner_net(), pos);
    if (refined == base || std::abs(refined - base) > 250) continue;
    const bool chosen = splitmix_finalize(pos.key()) % 1000000 < 500000;
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    const int beta = chosen ? base + 400 : base + 1;  // chosen: far from the window; not: on it
    const int got = searcher->probe_zero_window(pos, beta, 0, stop);
    CHECK_MSG(got == (chosen ? refined : base), pos.fen() << (chosen ? " (chosen)" : " (not chosen)"));
    CHECK_EQ(searcher->refiner_tally().consults, chosen ? 1u : 0u);
    (chosen ? selected : skipped) += 1;
    if (selected >= 20 && skipped >= 20) break;
  }
  CHECK(selected >= 10 && skipped >= 10);
}

}  // namespace forkeng::test
