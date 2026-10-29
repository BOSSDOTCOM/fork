// SPDX-License-Identifier: GPL-3.0-or-later

// B0's inference (DESIGN.md §5.3, deliverable 5), on random networks drawn
// within the net file's bounds: the feature index, the net file's reader,
// incremental updates against refreshes, every SIMD path against its scalar
// reference (.claude/rules/simd.md), and colour symmetry. The parity test
// against the trainer's own model (deliverable 6) needs a trained net and
// comes with it.
//
// Test positions: the CPW perft suite (tests/suite.hpp, cited there) and
// random legal games from it.
#include <cstdint>
#include <cstring>
#include <memory>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "eval/nnue/accumulator.hpp"
#include "eval/nnue/net_file.hpp"
#include "harness.hpp"
#include "suite.hpp"

#if defined(FORK_EVAL_NNUE)
#include <atomic>
#include <string>

#include "eval/eval.hpp"
#include "search/hash_memory.hpp"
#include "search/searcher.hpp"
#endif

namespace forkeng::test {

namespace {

int uniform(std::uint64_t& rng, int lo, int hi) {
  return lo + static_cast<int>(splitmix_next(rng) % static_cast<std::uint64_t>(hi - lo + 1));
}

// Feature weights within +-900 and biases within +-2000 keep every hidden
// unit inside int16 (2000 + 32 x 900 < 32767); output weights within +-2000
// keep the output sum inside int32 (255 x 512 x 2000 < 2^31).
std::unique_ptr<NetFile> random_net(std::uint64_t seed) {
  auto net = std::make_unique<NetFile>();
  std::uint64_t rng = seed;
  for (auto& w : net->ft_weights) w = static_cast<std::int16_t>(uniform(rng, -900, 900));
  for (auto& b : net->ft_bias) b = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
  for (auto& w : net->out_weights) w = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
  net->out_bias = uniform(rng, -100000, 100000);
  net->scale = 400;
  return net;
}

int full_eval(const NetFile& net, const Position& pos) {
  Accumulator acc;
  accumulate_board(net, pos, acc);
  return output_layer(net, acc, pos.side_to_move());
}

}  // namespace

TEST_CASE("nnue", "feature indices follow bullet's 768-input convention") {
  // Worked by hand from the convention (accumulator.hpp): a white pawn on e2
  // (square 12) and a black king on e8 (square 60), seen by each side.
  CHECK_EQ(feature_index(White, piece_of(White, Pawn), 12), 12);
  CHECK_EQ(feature_index(Black, piece_of(White, Pawn), 12), 384 + 52);
  CHECK_EQ(feature_index(White, piece_of(Black, King), 60), 384 + 5 * 64 + 60);
  CHECK_EQ(feature_index(Black, piece_of(Black, King), 60), 5 * 64 + 4);
}

TEST_CASE("nnue", "net files round-trip and the reader rejects bad ones") {
  auto net = random_net(1);
  const std::vector<std::uint8_t> bytes = write_net_file(*net);
  CHECK_EQ(bytes.size(), NetHeaderBytes + NetPayloadBytes);
  auto back = std::make_unique<NetFile>();
  std::string error;
  CHECK_MSG(read_net_file(bytes, *back, error), error);
  CHECK(std::memcmp(back->ft_weights, net->ft_weights, sizeof net->ft_weights) == 0);
  CHECK(std::memcmp(back->ft_bias, net->ft_bias, sizeof net->ft_bias) == 0);
  CHECK(std::memcmp(back->out_weights, net->out_weights, sizeof net->out_weights) == 0);
  CHECK_EQ(back->out_bias, net->out_bias);
  CHECK_EQ(back->scale, net->scale);

  auto rejects = [&](std::vector<std::uint8_t> bad, const char* what) {
    std::string why;
    CHECK_MSG(!read_net_file(bad, *back, why) && !why.empty(), what);
  };
  rejects({bytes.begin(), bytes.end() - 1}, "truncated");
  auto magic = bytes;
  magic[0] = 'X';
  rejects(magic, "magic");
  auto payload = bytes;
  payload[NetHeaderBytes + 1000] ^= 1;
  rejects(payload, "a flipped payload bit (checksum)");
  auto hidden = bytes;
  hidden[20] = 128;
  rejects(hidden, "hidden size");
  auto scale = bytes;
  std::memset(&scale[32], 0, 4);
  rejects(scale, "scale 0");
  auto loud = random_net(2);
  loud->ft_bias[7] = 32000;
  rejects(write_net_file(*loud), "a hidden unit beyond int16");
  auto wide = random_net(3);
  for (auto& w : wide->out_weights) w = 32000;
  rejects(write_net_file(*wide), "an output sum beyond int32");
}

TEST_CASE("nnue", "incremental updates equal refreshes along random games") {
  auto net = random_net(4);
  auto stack = std::make_unique<FeatureStack>();
  int checked = 0;
  for (const auto& sp : perft_suite()) {
    for (std::uint64_t seed = 1; seed <= 8; ++seed) {
      Position pos;
      pos.set_fen(sp.fen);
      stack->reset(*net, pos);
      std::uint64_t rng = seed * 7919 + checked;
      for (int ply = 0; ply < 80 && ply < MaxPly - 1; ++ply) {
        // Evaluate at a random subset of plies, so the lazy path skips some.
        if (splitmix_next(rng) % 3 == 0) {
          CHECK_EQ(stack->evaluate(*net, ply, pos), full_eval(*net, pos));
          ++checked;
        }
        MoveList legal;
        generate<GenMode::Legal>(pos, legal);
        if (legal.size() == 0) break;
        if (!pos.in_check() && splitmix_next(rng) % 10 == 0) {
          stack->push_null(ply);
          pos.make_null();
        } else {
          const Move m = legal[splitmix_next(rng) % legal.size()];
          stack->push_move(ply, pos, m);
          pos.make(m);
        }
      }
    }
  }
  CHECK(checked > 300);
}

TEST_CASE("nnue", "every move kind's delta matches a refresh") {
  // Each legal move of each perft-suite position (castling, en passant,
  // promotions and capture-promotions among them), one step from a refresh.
  auto net = random_net(5);
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    Accumulator root, child, fresh;
    accumulate_board(*net, pos, root);
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    for (Move m : legal) {
      const FeatureDelta d = delta_for_move(pos, m);
      advance_accumulator(*net, root, d, child);
      pos.make(m);
      accumulate_board(*net, pos, fresh);
      CHECK_MSG(std::memcmp(&child, &fresh, sizeof child) == 0, pos.fen());
      pos.unmake(m);
    }
  }
}

TEST_CASE("nnue", "the SIMD kernels equal their scalar references") {
  auto net = random_net(6);
  std::uint64_t rng = 99;
  Accumulator acc, a, b;
  auto check_output = [&](const char* what) {
    for (const Color stm : {White, Black})
      CHECK_MSG(output_layer(*net, acc, stm) == output_layer_scalar(*net, acc, stm), what);
  };
  for (int round = 0; round < 200; ++round) {
    for (auto& side : acc.values)
      for (auto& v : side) v = static_cast<std::int16_t>(uniform(rng, -32768, 32767));
    check_output("random accumulator");
    FeatureDelta d;
    d.removed_count = uniform(rng, 0, 2);
    d.added_count = uniform(rng, 0, 2);
    for (int i = 0; i < 2; ++i) {
      d.removed_piece[i] = piece_of(Color(uniform(rng, 0, 1)), PieceType(uniform(rng, 0, 5)));
      d.added_piece[i] = piece_of(Color(uniform(rng, 0, 1)), PieceType(uniform(rng, 0, 5)));
      d.removed_square[i] = uniform(rng, 0, 63);
      d.added_square[i] = uniform(rng, 0, 63);
    }
    advance_accumulator(*net, acc, d, a);
    advance_accumulator_scalar(*net, acc, d, b);
    CHECK(std::memcmp(&a, &b, sizeof a) == 0);
  }
  for (const int edge : {0, NetQa, NetQa + 1, -1, -32768, 32767}) {
    for (auto& side : acc.values)
      for (auto& v : side) v = static_cast<std::int16_t>(edge);
    check_output("constant accumulator at an edge");
  }
}

TEST_CASE("nnue", "a position and its colour mirror evaluate the same") {
  auto net = random_net(7);
  int checked = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    std::uint64_t rng = 31 + checked;
    for (int ply = 0; ply < 40; ++ply) {
      CHECK_EQ(full_eval(*net, pos), full_eval(*net, pos.mirrored()));
      ++checked;
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      if (legal.size() == 0) break;
      pos.make(legal[splitmix_next(rng) % legal.size()]);
    }
  }
  CHECK(checked > 100);
}

#if defined(FORK_EVAL_NNUE)
TEST_CASE("nnue", "searches through the evaluator hooks keep every accumulator exact") {
  // The search makes every move through Searcher::play and evaluates through
  // FeatureStack; in debug builds FeatureStack::evaluate checks each
  // incremental accumulator against a refresh and stops the program on a
  // difference, so these searches check every node they evaluate.
  auto table = std::make_unique<TransTable>();
  HashMemory memory;
  std::string report;
  if (!memory.resize(std::size_t{4} << 20, report)) SKIP("no memory for the table: " << report);
  table->bind_memory(memory.data(), memory.bytes());
  auto searcher = std::make_unique<Searcher>(*table);
  const std::atomic<bool> stop{false};
  SearchQuota limits;
  limits.depth = Optimized ? 8 : 5;
  std::uint64_t nodes = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    const SearchResult r = searcher->deliberate(pos, limits, stop, nullptr, nullptr);
    CHECK(r.best != NoMove);
    CHECK_EQ(pos.fen(), Position(pos).fen());
    nodes += r.nodes;
  }
  CHECK(nodes > 1000);
  // The embedded network evaluates a position the same through static_eval
  // (from scratch) as through the search's root accumulator.
  Position start;
  CHECK_EQ(static_eval(start), full_eval(embedded_net(), start));
}
#endif

}  // namespace forkeng::test
