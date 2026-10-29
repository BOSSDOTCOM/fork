// SPDX-License-Identifier: GPL-3.0-or-later

// The bake-off candidates' inference (EXPERIMENT BRANCH; DESIGN.md §5 plan
// step 4): S-512 on the shared single-layer framework, with random networks
// within validate()'s bounds. Incremental updates (king moves across the
// mirror line included) against refreshes, the SIMD kernels against their
// scalar references, and the two symmetries S's inputs give exactly: a
// position and its colour mirror, and a position and its left-right mirror
// (castling rights dropped), evaluate the same.
//
// Test positions: the CPW perft suite (tests/suite.hpp, cited there) and
// random legal games from it.
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
#include "eval/nnue/single_layer.hpp"
#include "harness.hpp"
#include "suite.hpp"

namespace forkeng::test {

namespace {

using S512 = SingleLayerNet<MirroredPieceSquare, 512, PieceCountBuckets>;

int uniform(std::uint64_t& rng, int lo, int hi) {
  return lo + static_cast<int>(splitmix_next(rng) % static_cast<std::uint64_t>(hi - lo + 1));
}

std::unique_ptr<S512> random_s512(std::uint64_t seed) {
  auto net = std::make_unique<S512>();
  std::uint64_t rng = seed;
  for (auto& w : net->ft_weights) w = static_cast<std::int16_t>(uniform(rng, -900, 900));
  for (auto& b : net->ft_bias) b = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
  for (auto& bucket : net->out_weights)
    for (auto& w : bucket) w = static_cast<std::int16_t>(uniform(rng, -128, 128));
  for (auto& b : net->out_bias) b = uniform(rng, -100000, 100000);
  net->scale = 400;
  return net;
}

int full_eval(const S512& net, const Position& pos) {
  S512::Acc acc;
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

}  // namespace

TEST_CASE("bakeoff", "S-512: incremental updates equal refreshes, king mirror crossings included") {
  auto net = random_s512(1);
  int checked = 0, crossings = 0;
  for (const auto& sp : perft_suite()) {
    for (std::uint64_t seed = 1; seed <= 6; ++seed) {
      Position pos;
      pos.set_fen(sp.fen);
      auto acc = std::make_unique<S512::Acc>();
      net->refresh(pos, *acc);
      std::uint64_t rng = seed * 104729 + checked;
      for (int ply = 0; ply < 60; ++ply) {
        MoveList legal;
        generate<GenMode::Legal>(pos, legal);
        if (legal.size() == 0) break;
        const Move m = legal[splitmix_next(rng) % legal.size()];
        Position before = pos;
        pos.make(m);
        crossings +=
            MirroredPieceSquare::needs_refresh(White, before.king_square(White), pos.king_square(White)) ||
            MirroredPieceSquare::needs_refresh(Black, before.king_square(Black), pos.king_square(Black));
        auto next = std::make_unique<S512::Acc>();
        net->advance(before, pos, m, *acc, *next);
        S512::Acc fresh;
        net->refresh(pos, fresh);
        CHECK_MSG(std::memcmp(next.get(), &fresh, sizeof fresh) == 0, pos.fen());
        acc = std::move(next);
        ++checked;
      }
    }
  }
  CHECK(checked > 1000);
  CHECK(crossings > 10);
}

TEST_CASE("bakeoff", "S-512: the SIMD kernels equal their scalar references") {
  auto net = random_s512(2);
  std::uint64_t rng = 7;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    for (int round = 0; round < 40; ++round) {
      S512::Acc acc;
      for (auto& side : acc.values)
        for (auto& v : side) v = static_cast<std::int16_t>(uniform(rng, -32768, 32767));
      CHECK_EQ(net->output(acc, pos), net->output_scalar(acc, pos));
      const std::int16_t* sub[2] = {net->ft_weights + uniform(rng, 0, 767) * 512,
                                    net->ft_weights + uniform(rng, 0, 767) * 512};
      const std::int16_t* add[2] = {net->ft_weights + uniform(rng, 0, 767) * 512,
                                    net->ft_weights + uniform(rng, 0, 767) * 512};
      alignas(64) std::int16_t a[512], b[512];
      S512::update(acc.values[0], a, sub, 2, add, 2);
      S512::update_scalar(acc.values[0], b, sub, 2, add, 2);
      CHECK(std::memcmp(a, b, sizeof a) == 0);
    }
    for (const int edge : {0, SlQa, SlQa + 1, -1, -32768, 32767}) {
      S512::Acc acc;
      for (auto& side : acc.values)
        for (auto& v : side) v = static_cast<std::int16_t>(edge);
      CHECK_EQ(net->output(acc, pos), net->output_scalar(acc, pos));
    }
  }
}

TEST_CASE("bakeoff", "S-512: colour and left-right mirrors evaluate the same") {
  auto net = random_s512(3);
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

TEST_CASE("bakeoff", "S-512 parity: Fork's inference equals the independent reference exactly") {
  // tools/nnue/reference_s512.py write DIR writes a random network and its
  // R-int values (the bakeoff_parity test, python label, sets the folder).
  const char* dir = std::getenv("FORK_BAKEOFF_PARITY_DIR");
  if (!dir) SKIP("FORK_BAKEOFF_PARITY_DIR not set (run through the bakeoff_parity test)");
  std::ifstream bin(std::string(dir) + "/s512.bin", std::ios::binary);
  auto net = std::make_unique<S512>();
  auto read = [&](void* p, std::size_t n) { bin.read(static_cast<char*>(p), static_cast<std::streamsize>(n)); };
  read(net->ft_weights, sizeof net->ft_weights);
  read(net->ft_bias, sizeof net->ft_bias);
  read(net->out_weights, sizeof net->out_weights);
  read(net->out_bias, sizeof net->out_bias);
  read(&net->scale, sizeof net->scale);
  CHECK(bin.good());
  std::string error;
  CHECK_MSG(net->validate(error), error);
  std::ifstream expect(std::string(dir) + "/s512.expect");
  std::string line;
  int positions = 0;
  while (std::getline(expect, line)) {
    const std::size_t bar = line.rfind('|');
    Position pos;
    CHECK(pos.set_fen(line.substr(0, bar)));
    S512::Acc acc;
    net->refresh(pos, acc);
    CHECK_MSG(net->output(acc, pos) == std::stoi(line.substr(bar + 1)), line);
    CHECK_MSG(net->output_scalar(acc, pos) == std::stoi(line.substr(bar + 1)), line);
    ++positions;
  }
  CHECK(positions > 400);
}

}  // namespace forkeng::test
