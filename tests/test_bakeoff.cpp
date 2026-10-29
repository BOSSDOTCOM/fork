// SPDX-License-Identifier: GPL-3.0-or-later

// The bake-off candidates' inference (EXPERIMENT BRANCH; DESIGN.md §5 plan
// step 4): S-512 and the hybrid H-512 on the shared single-layer framework,
// AF-S (eval/nnue/stacked.hpp) and XGR-512 (eval/nnue/gated.hpp, with its
// exposure sets checked against python-chess's attacker sets), with random
// networks within validate()'s bounds. For each: incremental
// updates (king moves that change the mapping included) against refreshes,
// the SIMD kernels against their scalar references, the two symmetries the
// mirrored inputs give exactly (a position and its colour mirror, and a
// position and its left-right mirror with castling rights dropped, evaluate
// the same), and parity with an independent Python reference
// (tools/nnue/reference_s512.py; the bakeoff_parity test).
//
// Test positions: the CPW perft suite (tests/suite.hpp, cited there) and
// random legal games from it; tests/nnue/parity.epd for parity.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "eval/nnue/gated.hpp"
#include "eval/nnue/single_layer.hpp"
#include "eval/nnue/stacked.hpp"
#include "harness.hpp"
#include "suite.hpp"

namespace forkeng::test {

namespace {

using S512 = SingleLayerNet<MirroredPieceSquare, 512, PieceCountBuckets>;
using H512 = SingleLayerNet<RegionMirroredPieceSquare, 512, PhaseBuckets>;

int uniform(std::uint64_t& rng, int lo, int hi) {
  return lo + static_cast<int>(splitmix_next(rng) % static_cast<std::uint64_t>(hi - lo + 1));
}

template <class Net>
std::unique_ptr<Net> random_net(std::uint64_t seed) {
  auto net = std::make_unique<Net>();
  std::uint64_t rng = seed;
  for (auto& w : net->ft_weights) w = static_cast<std::int16_t>(uniform(rng, -900, 900));
  for (auto& b : net->ft_bias) b = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
  for (auto& bucket : net->out_weights)
    for (auto& w : bucket) w = static_cast<std::int16_t>(uniform(rng, -128, 128));
  for (auto& b : net->out_bias) b = uniform(rng, -100000, 100000);
  net->scale = 400;
  return net;
}

template <class Net>
int full_eval(const Net& net, const Position& pos) {
  typename Net::Acc acc;
  net.refresh(pos, acc);
  return net.output(acc, pos);
}

// The position with files mirrored (a <-> h); castling rights and the en
// passant square dropped, side to move and clocks kept.
std::string files_mirrored(const Position& pos) {
  std::istringstream in(pos.fen());
  std::string board, stm;
  in >> board >> stm;
  std::string out, rank;
  for (char c : board + "/") {
    if (c == '/') {
      std::reverse(rank.begin(), rank.end());
      out += rank + "/";
      rank.clear();
    } else {
      rank += c;
    }
  }
  out.pop_back();
  return out + " " + stm + " - - 0 1";
}

template <class Net, class Features>
void check_incremental(const Net& net) {
  int checked = 0, refreshes = 0;
  for (const auto& sp : perft_suite()) {
    for (std::uint64_t game = 1; game <= 6; ++game) {
      Position pos;
      pos.set_fen(sp.fen);
      auto acc = std::make_unique<typename Net::Acc>();
      net.refresh(pos, *acc);
      std::uint64_t rng = game * 104729 + checked;
      for (int ply = 0; ply < 60; ++ply) {
        MoveList legal;
        generate<GenMode::Legal>(pos, legal);
        if (legal.size() == 0) break;
        const Move m = legal[splitmix_next(rng) % legal.size()];
        Position before = pos;
        pos.make(m);
        for (const Color c : {White, Black})
          refreshes += Features::needs_refresh(c, before.king_square(c), pos.king_square(c));
        auto next = std::make_unique<typename Net::Acc>();
        net.advance(before, pos, m, *acc, *next);
        auto fresh = std::make_unique<typename Net::Acc>();
        net.refresh(pos, *fresh);
        CHECK_MSG(std::memcmp(next->values, fresh->values, sizeof fresh->values) == 0, pos.fen());
        if constexpr (requires { fresh->side; })
          CHECK_MSG(std::memcmp(next->side, fresh->side, sizeof fresh->side) == 0, pos.fen());
        acc = std::move(next);
        ++checked;
      }
    }
  }
  CHECK(checked > 1000);
  CHECK(refreshes > 10);
}

template <class Net>
void check_simd(std::uint64_t seed) {
  auto net = random_net<Net>(seed);
  std::uint64_t rng = 7;
  constexpr int H = Net::HiddenSize;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    for (int round = 0; round < 40; ++round) {
      typename Net::Acc acc;
      for (auto& side : acc.values)
        for (auto& v : side) v = static_cast<std::int16_t>(uniform(rng, -32768, 32767));
      CHECK_EQ(net->output(acc, pos), net->output_scalar(acc, pos));
      const std::int16_t* sub[2] = {net->ft_weights + uniform(rng, 0, Net::Inputs - 1) * H,
                                    net->ft_weights + uniform(rng, 0, Net::Inputs - 1) * H};
      const std::int16_t* add[2] = {net->ft_weights + uniform(rng, 0, Net::Inputs - 1) * H,
                                    net->ft_weights + uniform(rng, 0, Net::Inputs - 1) * H};
      alignas(64) std::int16_t a[H], b[H];
      Net::update(acc.values[0], a, sub, 2, add, 2);
      Net::update_scalar(acc.values[0], b, sub, 2, add, 2);
      CHECK(std::memcmp(a, b, sizeof a) == 0);
    }
    for (const int edge : {0, SlQa, SlQa + 1, -1, -32768, 32767}) {
      typename Net::Acc acc;
      for (auto& side : acc.values)
        for (auto& v : side) v = static_cast<std::int16_t>(edge);
      CHECK_EQ(net->output(acc, pos), net->output_scalar(acc, pos));
    }
  }
}

template <class Net>
void check_symmetry(std::uint64_t seed) {
  auto net = random_net<Net>(seed);
  std::string error;
  CHECK_MSG(net->validate(error), error);
  int checked = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    std::uint64_t rng = 99 + checked;
    for (int ply = 0; ply < 40; ++ply) {
      CHECK_EQ(full_eval(*net, pos), full_eval(*net, pos.mirrored()));
      Position flipped;
      if (flipped.set_fen(files_mirrored(pos))) {
        CHECK_MSG(full_eval(*net, pos) == full_eval(*net, flipped), pos.fen());
        ++checked;
      }
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      if (legal.size() == 0) break;
      pos.make(legal[splitmix_next(rng) % legal.size()]);
    }
  }
  CHECK(checked > 100);
}

template <class Net>
void check_parity(const char* name) {
  // tools/nnue/reference_s512.py write DIR --arch NAME writes a random network
  // and its R-int values (the bakeoff_parity test, python label, sets DIR).
  const char* dir = std::getenv("FORK_BAKEOFF_PARITY_DIR");
  if (!dir) SKIP("FORK_BAKEOFF_PARITY_DIR not set (run through the bakeoff_parity test)");
  std::ifstream bin(std::string(dir) + "/" + name + ".bin", std::ios::binary);
  auto net = std::make_unique<Net>();
  auto read = [&](void* p, std::size_t n) {
    bin.read(static_cast<char*>(p), static_cast<std::streamsize>(n));
  };
  read(net->ft_weights, sizeof net->ft_weights);
  read(net->ft_bias, sizeof net->ft_bias);
  read(net->out_weights, sizeof net->out_weights);
  read(net->out_bias, sizeof net->out_bias);
  read(&net->scale, sizeof net->scale);
  CHECK(bin.good());
  std::string error;
  CHECK_MSG(net->validate(error), error);
  std::ifstream expect(std::string(dir) + "/" + name + ".expect");
  std::string line;
  int positions = 0;
  while (std::getline(expect, line)) {
    const std::size_t bar = line.rfind('|');
    Position pos;
    CHECK(pos.set_fen(line.substr(0, bar)));
    typename Net::Acc acc;
    net->refresh(pos, acc);
    const int want = std::stoi(line.substr(bar + 1));
    CHECK_MSG(net->output(acc, pos) == want, line);
    CHECK_MSG(net->output_scalar(acc, pos) == want, line);
    ++positions;
  }
  CHECK(positions > 400);
}

std::unique_ptr<GatedNet> random_xgr(std::uint64_t seed) {
  auto net = std::make_unique<GatedNet>();
  std::uint64_t rng = seed;
  for (auto& w : net->ft_weights) w = static_cast<std::int16_t>(uniform(rng, -500, 500));
  for (auto& w : net->ft_side) w = static_cast<std::int16_t>(uniform(rng, -8, 8));
  for (auto& w : net->x_weights) w = static_cast<std::int16_t>(uniform(rng, -500, 500));
  for (auto& w : net->x_side) w = static_cast<std::int16_t>(uniform(rng, -8, 8));
  for (auto& b : net->ft_bias) b = static_cast<std::int16_t>(uniform(rng, -1500, 1500));
  for (auto& b : net->side_bias) b = static_cast<std::int16_t>(uniform(rng, -50, 50));
  for (auto& e : net->expert_w)
    for (auto& w : e) w = static_cast<std::int16_t>(uniform(rng, -127, 127));
  for (auto& b : net->expert_b) b = uniform(rng, -100000, 100000);
  net->scale = 40;
  return net;
}

std::unique_ptr<StackedNet> random_afs(std::uint64_t seed) {
  auto net = std::make_unique<StackedNet>();
  std::uint64_t rng = seed;
  for (auto& w : net->ft_weights) w = static_cast<std::int16_t>(uniform(rng, -900, 900));
  for (auto& b : net->ft_bias) b = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
  for (auto& k : net->l1_w)
    for (auto& o : k)
      for (auto& w : o) w = static_cast<std::int8_t>(uniform(rng, -127, 127));
  for (auto& k : net->l1_b)
    for (auto& b : k) b = uniform(rng, -20000, 20000);
  for (auto& k : net->l2_w)
    for (auto& o : k)
      for (auto& w : o) w = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
  for (auto& k : net->l2_b)
    for (auto& b : k) b = uniform(rng, -1000000, 1000000);
  for (auto& k : net->l3_w)
    for (auto& w : k) w = static_cast<std::int16_t>(uniform(rng, -20000, 20000));
  for (auto& b : net->l3_b) b = uniform(rng, -1000000, 1000000);
  net->out_multiplier = 105000;
  return net;
}

int afs_eval(const StackedNet& net, const Position& pos) {
  StackedNet::Acc acc;
  net.refresh(pos, acc);
  return net.output(acc, pos);
}

}  // namespace

TEST_CASE("bakeoff", "AF-S: the SIMD paths equal their scalar references, edges included") {
  auto net = random_afs(8);
  std::string error;
  CHECK_MSG(net->validate(error), error);
  std::uint64_t rng = 13;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    for (int round = 0; round < 30; ++round) {
      StackedNet::Acc acc;
      for (auto& side : acc.values)
        for (auto& v : side) v = static_cast<std::int16_t>(uniform(rng, -600, 600));
      CHECK_EQ(net->output(acc, pos), net->output_scalar(acc, pos));
      alignas(32) std::uint8_t a[StackedNet::L1In], b[StackedNet::L1In];
      StackedNet::pairwise(acc, pos.side_to_move(), a);
      StackedNet::pairwise_scalar(acc, pos.side_to_move(), b);
      CHECK(std::memcmp(a, b, sizeof a) == 0);
    }
    for (const int edge : {0, 255, 256, -1, -32768, 32767}) {
      StackedNet::Acc acc;
      for (auto& side : acc.values)
        for (auto& v : side) v = static_cast<std::int16_t>(edge);
      CHECK_EQ(net->output(acc, pos), net->output_scalar(acc, pos));
    }
  }
  // The largest L1 inputs (127) against weights of +-127: no saturation.
  alignas(32) std::uint8_t x[StackedNet::L1In];
  alignas(32) std::int8_t w[StackedNet::L1In];
  for (int i = 0; i < StackedNet::L1In; ++i) {
    x[i] = 127;
    w[i] = static_cast<std::int8_t>(i % 2 ? 127 : -127);
  }
  CHECK_EQ(StackedNet::l1_dot(x, w), StackedNet::l1_dot_scalar(x, w));
  for (auto& v : w) v = 127;
  CHECK_EQ(StackedNet::l1_dot(x, w), StackedNet::l1_dot_scalar(x, w));
}

TEST_CASE("bakeoff", "AF-S: colour and left-right mirrors evaluate the same") {
  auto net = random_afs(9);
  int checked = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    std::uint64_t rng = 5 + checked;
    for (int ply = 0; ply < 30; ++ply) {
      CHECK_EQ(afs_eval(*net, pos), afs_eval(*net, pos.mirrored()));
      Position flipped;
      if (flipped.set_fen(files_mirrored(pos))) {
        CHECK_MSG(afs_eval(*net, pos) == afs_eval(*net, flipped), pos.fen());
        ++checked;
      }
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      if (legal.size() == 0) break;
      pos.make(legal[splitmix_next(rng) % legal.size()]);
    }
  }
  CHECK(checked > 100);
}

TEST_CASE("bakeoff", "AF-S parity: Fork's inference equals the independent reference exactly") {
  const char* dir = std::getenv("FORK_BAKEOFF_PARITY_DIR");
  if (!dir) SKIP("FORK_BAKEOFF_PARITY_DIR not set (run through the bakeoff_parity test)");
  std::ifstream bin(std::string(dir) + "/afs.bin", std::ios::binary);
  auto net = std::make_unique<StackedNet>();
  auto read = [&](void* p, std::size_t n) { bin.read(static_cast<char*>(p), static_cast<std::streamsize>(n)); };
  read(net->ft_weights, sizeof net->ft_weights);
  read(net->ft_bias, sizeof net->ft_bias);
  read(net->l1_w, sizeof net->l1_w);
  read(net->l1_b, sizeof net->l1_b);
  read(net->l2_w, sizeof net->l2_w);
  read(net->l2_b, sizeof net->l2_b);
  read(net->l3_w, sizeof net->l3_w);
  read(net->l3_b, sizeof net->l3_b);
  read(&net->out_multiplier, sizeof net->out_multiplier);
  CHECK(bin.good());
  std::string error;
  CHECK_MSG(net->validate(error), error);
  std::ifstream expect(std::string(dir) + "/afs.expect");
  std::string line;
  int positions = 0;
  while (std::getline(expect, line)) {
    const std::size_t bar = line.rfind('|');
    Position pos;
    CHECK(pos.set_fen(line.substr(0, bar)));
    StackedNet::Acc acc;
    net->refresh(pos, acc);
    const int want = std::stoi(line.substr(bar + 1));
    CHECK_MSG(net->output(acc, pos) == want, line);
    CHECK_MSG(net->output_scalar(acc, pos) == want, line);
    ++positions;
  }
  CHECK(positions > 400);
}

TEST_CASE("bakeoff", "S-512: incremental updates equal refreshes, king mirror crossings included") {
  check_incremental<S512, MirroredPieceSquare>(*random_net<S512>(1));
}
TEST_CASE("bakeoff", "AF-S: incremental updates equal refreshes, region and mirror crossings included") {
  check_incremental<StackedNet, RegionMirroredPieceSquare>(*random_afs(10));
}
TEST_CASE("bakeoff", "XGR-512: incremental updates equal refreshes, side lanes included") {
  check_incremental<GatedNet, XgrRegionPieceSquare>(*random_xgr(11));
}
TEST_CASE("bakeoff", "XGR-512: the SIMD path equals the scalar reference, edges included") {
  auto net = random_xgr(12);
  std::string error;
  CHECK_MSG(net->validate(error), error);
  std::uint64_t rng = 17;
  int interior = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    for (int round = 0; round < 30; ++round) {
      auto acc = std::make_unique<GatedNet::Acc>();
      for (auto& side : acc->values)
        for (auto& v : side) v = static_cast<std::int16_t>(uniform(rng, -400, 600));
      for (auto& side : acc->side)
        for (auto& v : side) v = static_cast<std::int16_t>(uniform(rng, -200, 300));
      interior += acc->side[0][0] + acc->side[1][0] > 0 && acc->side[0][0] + acc->side[1][0] < 255;
      CHECK_EQ(net->output(*acc, pos), net->output_scalar(*acc, pos));
    }
    for (const int edge : {0, 255, 256, -1, -32768, 32767}) {
      auto acc = std::make_unique<GatedNet::Acc>();
      for (auto& side : acc->values)
        for (auto& v : side) v = static_cast<std::int16_t>(edge);
      CHECK_EQ(net->output(*acc, pos), net->output_scalar(*acc, pos));
    }
  }
  CHECK(interior > 20);  // the gate blends, not just picks an expert
}
TEST_CASE("bakeoff", "XGR-512: colour and left-right mirrors evaluate the same") {
  auto net = random_xgr(13);
  int checked = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    std::uint64_t rng = 21 + checked;
    for (int ply = 0; ply < 30; ++ply) {
      CHECK_EQ(full_eval(*net, pos), full_eval(*net, pos.mirrored()));
      Position flipped;
      if (flipped.set_fen(files_mirrored(pos))) {
        CHECK_MSG(full_eval(*net, pos) == full_eval(*net, flipped), pos.fen());
        ++checked;
      }
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      if (legal.size() == 0) break;
      pos.make(legal[splitmix_next(rng) % legal.size()]);
    }
  }
  CHECK(checked > 100);
}
TEST_CASE("bakeoff", "XGR-512 parity: exposure sets and evaluations equal the independent reference") {
  const char* dir = std::getenv("FORK_BAKEOFF_PARITY_DIR");
  if (!dir) SKIP("FORK_BAKEOFF_PARITY_DIR not set (run through the bakeoff_parity test)");
  std::ifstream bin(std::string(dir) + "/xgr.bin", std::ios::binary);
  auto net = std::make_unique<GatedNet>();
  auto read = [&](void* p, std::size_t n) { bin.read(static_cast<char*>(p), static_cast<std::streamsize>(n)); };
  read(net->ft_weights, sizeof net->ft_weights);
  read(net->ft_side, sizeof net->ft_side);
  read(net->x_weights, sizeof net->x_weights);
  read(net->x_side, sizeof net->x_side);
  read(net->ft_bias, sizeof net->ft_bias);
  read(net->side_bias, sizeof net->side_bias);
  read(net->expert_w, sizeof net->expert_w);
  read(net->expert_b, sizeof net->expert_b);
  read(&net->scale, sizeof net->scale);
  CHECK(bin.good());
  std::string error;
  CHECK_MSG(net->validate(error), error);
  std::ifstream expect(std::string(dir) + "/xgr.expect");
  std::string line;
  int positions = 0, exposed = 0;
  while (std::getline(expect, line)) {
    const std::size_t bar2 = line.rfind('|'), bar1 = line.rfind('|', bar2 - 1);
    Position pos;
    CHECK(pos.set_fen(line.substr(0, bar1)));
    auto acc = std::make_unique<GatedNet::Acc>();
    net->refresh(pos, *acc);
    const int want = std::stoi(line.substr(bar1 + 1, bar2 - bar1 - 1));
    const int count = std::stoi(line.substr(bar2 + 1));
    CHECK_MSG(popcount(GatedNet::exposed(pos)) == count, line);
    CHECK_MSG(net->output(*acc, pos) == want, line);
    CHECK_MSG(net->output_scalar(*acc, pos) == want, line);
    exposed += count > 0;
    ++positions;
  }
  CHECK(positions > 400);
  CHECK(exposed > 100);
}
TEST_CASE("bakeoff", "S-512: the SIMD kernels equal their scalar references") { check_simd<S512>(2); }
TEST_CASE("bakeoff", "S-512: colour and left-right mirrors evaluate the same") { check_symmetry<S512>(3); }
TEST_CASE("bakeoff", "S-512 parity: Fork's inference equals the independent reference exactly") {
  check_parity<S512>("s512");
}

TEST_CASE("bakeoff", "H-512: incremental updates equal refreshes, region and mirror crossings included") {
  check_incremental<H512, RegionMirroredPieceSquare>(*random_net<H512>(4));
}
TEST_CASE("bakeoff", "H-512: the SIMD kernels equal their scalar references") { check_simd<H512>(5); }
TEST_CASE("bakeoff", "H-512: colour and left-right mirrors evaluate the same") { check_symmetry<H512>(6); }
TEST_CASE("bakeoff", "H-512 parity: Fork's inference equals the independent reference exactly") {
  check_parity<H512>("h512");
}

}  // namespace forkeng::test
