// SPDX-License-Identifier: GPL-3.0-or-later

// The network inference of this build's architecture (DESIGN.md §5.3,
// deliverable 5; §5.4), on random networks drawn within the net file's
// bounds: the feature index, the net file's reader, incremental updates
// against refreshes (king moves across the mirror line and the regions
// included), every SIMD path against its scalar reference
// (.claude/rules/simd.md), colour symmetry and, for mirrored networks,
// left-right symmetry. The parity test against the trainer's own model
// (deliverable 6) is the netcheck of a trained net (CMakeLists.txt).
//
// Test positions: the CPW perft suite (tests/suite.hpp, cited there) and
// random legal games from it.
#include <cstdint>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "eval/nnue/accumulator.hpp"
#include "eval/nnue/net_file.hpp"
#include "harness.hpp"
#include "suite.hpp"

#if defined(FORK_EVAL_NNUE)
#include <atomic>

#include "eval/eval.hpp"
#include "search/hash_memory.hpp"
#include "search/searcher.hpp"
#endif

namespace forkeng::test {

namespace {

int uniform(std::uint64_t& rng, int lo, int hi) {
  return lo + static_cast<int>(splitmix_next(rng) % static_cast<std::uint64_t>(hi - lo + 1));
}

// Feature weights within +-400 and biases within +-2000 keep every
// first-layer sum inside int16 (2000 + 62 x 400 < 32767); B0's output
// weights within +-2000 keep its sum inside int32 (255 x 512 x 2000 < 2^31);
// squared outputs need |w| <= 128.
std::unique_ptr<NetFile> random_net(std::uint64_t seed) {
  auto net = std::make_unique<NetFile>();
  std::uint64_t rng = seed;
  if constexpr (NetRegioned) {
    // Regions of the mirrored king cell: e1; f1-h1; rank 2; the rest.
    for (int c = 0; c < 32; ++c)
      net->regions[c] = static_cast<std::uint8_t>(c == 0 ? 0 : c < 4 ? 1 : c < 8 ? 2 : 3);
    net->region_count = 4;
  }
  for (int p = 0; p < 25; ++p)
    net->phase_table[p] = static_cast<std::uint8_t>(NetPhasePicked ? p * 8 / 25 : 0);
  net->inputs = NetPieceSquares * net->region_count + (NetExposure ? NetExposureRows : 0);
  for (auto& w : net->ft_weights) w = static_cast<std::int16_t>(uniform(rng, -400, 400));
  for (auto& b : net->ft_bias) b = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
#if FORK_NET_ARCH == 1
  for (auto& w : net->out_weights) w = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
  net->out_bias = uniform(rng, -100000, 100000);
#elif FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3
  for (auto& row : net->out_weights)
    for (auto& w : row) w = static_cast<std::int16_t>(uniform(rng, -128, 128));
  for (auto& b : net->out_bias) b = uniform(rng, -100000, 100000);
#elif FORK_NET_ARCH == 4
  for (auto& stack : net->af1_weights)
    for (auto& row : stack)
      for (auto& w : row) w = static_cast<std::int8_t>(uniform(rng, -127, 127));
  for (auto& stack : net->af1_bias)
    for (auto& b : stack) b = uniform(rng, -20000, 20000);
  for (auto& stack : net->af2_weights)
    for (auto& row : stack)
      for (auto& w : row) w = static_cast<std::int16_t>(uniform(rng, -16000, 16000));
  for (auto& stack : net->af2_bias)
    for (auto& b : stack) b = uniform(rng, -1000000, 1000000);
  for (auto& stack : net->af3_weights)
    for (auto& w : stack) w = static_cast<std::int16_t>(uniform(rng, -16000, 16000));
  for (auto& b : net->af3_bias) b = uniform(rng, -1000000, 1000000);
  net->output_multiplier = 40000;
#elif FORK_NET_ARCH == 5
  for (int f = 0; f < NetInputs; ++f)
    for (int k = 0; k < 3; ++k) net->side_weights[f][k] = static_cast<std::int16_t>(uniform(rng, -300, 300));
  for (int k = 0; k < 3; ++k) net->side_bias[k] = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
  for (auto& row : net->expert_weights)
    for (auto& w : row) w = static_cast<std::int16_t>(uniform(rng, -128, 128));
  for (auto& b : net->expert_bias) b = uniform(rng, -100000, 100000);
#endif
  net->scale = 400;
  return net;
}

int full_eval(const NetFile& net, const Position& pos) {
  Accumulator acc;
  accumulate_board(net, pos, acc);
  return evaluate_position(net, acc, pos);
}

// A FEN with its files reversed (a <-> h), without castling rights and with
// the en passant file reversed: the left-right mirror of the position.
std::string flip_files(const std::string& fen) {
  std::string board = fen.substr(0, fen.find(' ')), out;
  std::size_t start = 0;
  while (true) {
    const std::size_t end = board.find('/', start);
    std::string rank = board.substr(start, end == std::string::npos ? std::string::npos : end - start);
    out += std::string(rank.rbegin(), rank.rend());
    if (end == std::string::npos) break;
    out += '/';
    start = end + 1;
  }
  std::string rest = fen.substr(fen.find(' ') + 1);  // "w KQkq e3 0 1"
  const char side = rest[0];
  std::string fields[4];
  std::size_t at = 2;
  for (auto& f : fields) {
    const std::size_t sp = rest.find(' ', at);
    f = rest.substr(at, sp == std::string::npos ? std::string::npos : sp - at);
    at = sp == std::string::npos ? rest.size() : sp + 1;
  }
  std::string ep = fields[1];
  if (ep != "-") ep[0] = static_cast<char>('a' + 'h' - ep[0]);
  return out + ' ' + side + " - " + ep + ' ' + fields[2] + ' ' + fields[3];
}

}  // namespace

TEST_CASE("nnue", "feature indices follow bullet's 768-input convention") {
  // Worked by hand from the convention (accumulator.hpp): a white pawn on e2
  // (square 12) and a black king on e8 (square 60), seen by each side.
  CHECK_EQ(feature_index(White, piece_of(White, Pawn), 12), 12);
  CHECK_EQ(feature_index(Black, piece_of(White, Pawn), 12), 384 + 52);
  CHECK_EQ(feature_index(White, piece_of(Black, King), 60), 384 + 5 * 64 + 60);
  CHECK_EQ(feature_index(Black, piece_of(Black, King), 60), 5 * 64 + 4);
  // With a frame: files flipped and the region's rows (a white king on c1,
  // seen by White: mirrored, so the pawn on e2 becomes d2, region 2's rows).
  CHECK_EQ(feature_index(White, piece_of(White, Pawn), 12, Frame{7, 2 * 768}), 2 * 768 + 11);
  if constexpr (NetMirrored) {
    auto net = random_net(9);
    CHECK_EQ(frame_of(*net, White, 2).flip, 7);   // c1: files a-d
    CHECK_EQ(frame_of(*net, White, 6).flip, 0);   // g1
    CHECK_EQ(frame_of(*net, Black, 58).flip, 7);  // c8, seen from Black: c1
  }
}

TEST_CASE("nnue", "net files round-trip and the reader rejects bad ones") {
  auto net = random_net(1);
  const std::vector<std::uint8_t> bytes = write_net_file(*net);
#if FORK_NET_ARCH == 1
  CHECK_EQ(bytes.size(), NetHeaderBytes + NetPayloadBytes);
#endif
  auto back = std::make_unique<NetFile>();
  std::string error;
  CHECK_MSG(read_net_file(bytes, *back, error), error);
  CHECK(write_net_file(*back) == bytes);
  CHECK(std::memcmp(back->ft_weights, net->ft_weights, sizeof(std::int16_t) * net->inputs * NetHidden) == 0);
  CHECK_EQ(back->scale, net->scale);
  CHECK_EQ(back->region_count, net->region_count);

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
  auto arch = bytes;
  arch[12] ^= 7;
  rejects(arch, "another architecture");
  auto scale = bytes;
  // Byte by byte: GCC at -O1 takes a memset here for a write past an empty
  // vector (-Warray-bounds, a false positive; CI, 2026-10-29).
  for (std::size_t i = 32; i < 36; ++i) scale[i] = 0;
  rejects(scale, "scale 0");
  auto loud = random_net(2);
  loud->ft_bias[7] = 32000;
  rejects(write_net_file(*loud), "a first-layer unit beyond int16");
#if FORK_NET_ARCH == 1
  auto wide = random_net(3);
  for (auto& w : wide->out_weights) w = 32000;
  rejects(write_net_file(*wide), "an output sum beyond int32");
#elif FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3
  auto wide = random_net(3);
  wide->out_weights[2][5] = 129;
  rejects(write_net_file(*wide), "an output weight beyond the squared output's bound");
#endif
  if constexpr (NetPhasePicked) {
    auto unsorted = random_net(4);
    unsorted->phase_table[3] = 7;
    rejects(write_net_file(*unsorted), "a phase table that is not sorted");
  }
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
          stack->push_move(*net, ply, pos, m);
          pos.make(m);
        }
      }
    }
  }
  CHECK(checked > 300);
}

TEST_CASE("nnue", "every move kind's delta matches a refresh") {
  // Each legal move of each perft-suite position (castling, en passant,
  // promotions and capture-promotions among them), one step from a refresh,
  // for every perspective whose frame the move leaves unchanged.
  auto net = random_net(5);
  int stepped = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    Accumulator root, child, fresh;
    accumulate_board(*net, pos, root);
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    for (Move m : legal) {
      const FeatureDelta d = delta_for_move(pos, m);
      const Frame before[2] = {frame_of(*net, White, pos.king_square(White)),
                               frame_of(*net, Black, pos.king_square(Black))};
      pos.make(m);
      accumulate_board(*net, pos, fresh);
      for (const Color perspective : {White, Black}) {
        if (frame_of(*net, perspective, pos.king_square(perspective)) != before[perspective]) continue;
        advance_perspective(*net, root, d, perspective, before[perspective], child);
        CHECK_MSG(
            std::memcmp(child.values[perspective], fresh.values[perspective], sizeof fresh.values[0]) == 0,
            pos.fen());
#if FORK_NET_ARCH == 5
        CHECK_MSG(std::memcmp(child.side[perspective], fresh.side[perspective], sizeof fresh.side[0]) == 0,
                  pos.fen());
#endif
        ++stepped;
      }
      pos.unmake(m);
    }
  }
  CHECK(stepped > 100);
}

TEST_CASE("nnue", "the SIMD kernels equal their scalar references") {
  auto net = random_net(6);
  std::uint64_t rng = 99;
  Accumulator acc, a;
  int compared = 0;
  auto check_output = [&](const char* what) {
    for (const auto& sp : perft_suite()) {
      Position pos;
      pos.set_fen(sp.fen);
      CHECK_MSG(evaluate_position(*net, acc, pos) == evaluate_position_scalar(*net, acc, pos), what);
      ++compared;
    }
  };
  for (int round = 0; round < 100; ++round) {
    for (auto& side : acc.values)
      for (auto& v : side) v = static_cast<std::int16_t>(uniform(rng, -32768, 32767));
#if FORK_NET_ARCH == 5
    for (auto& side : acc.side)
      for (auto& v : side) v = static_cast<std::int16_t>(uniform(rng, -8000, 8000));
#endif
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
    const Frame f{uniform(rng, 0, 1) * 7, NetPieceSquares * uniform(rng, 0, net->region_count - 1)};
    for (const Color perspective : {White, Black}) {
      advance_perspective(*net, acc, d, perspective, f, a);
      // The scalar meaning: the parent's sums minus the removed rows plus the
      // added rows, in 16-bit wrapping arithmetic.
      bool same = true;
      for (int i = 0; i < NetHidden; ++i) {
        int x = acc.values[perspective][i];
        for (int k = 0; k < d.removed_count; ++k)
          x -= net->ft_weights[feature_index(perspective, d.removed_piece[k], d.removed_square[k], f) *
                                   NetHidden +
                               i];
        for (int k = 0; k < d.added_count; ++k)
          x +=
              net->ft_weights[feature_index(perspective, d.added_piece[k], d.added_square[k], f) * NetHidden +
                              i];
        same &= a.values[perspective][i] == static_cast<std::int16_t>(x);
      }
      CHECK(same);
    }
#if FORK_NET_ARCH == 1
    Accumulator b;
    advance_accumulator(*net, acc, d, a);
    advance_accumulator_scalar(*net, acc, d, b);
    CHECK(std::memcmp(&a, &b, sizeof a) == 0);
    for (const Color stm : {White, Black})
      CHECK(output_layer(*net, acc, stm) == output_layer_scalar(*net, acc, stm));
#endif
  }
  for (const int edge : {0, NetQa, NetQa + 1, -1, -32768, 32767}) {
    for (auto& side : acc.values)
      for (auto& v : side) v = static_cast<std::int16_t>(edge);
    check_output("constant accumulator at an edge");
  }
  CHECK(compared > 500);
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

TEST_CASE("nnue", "mirrored networks evaluate a position and its left-right mirror the same") {
  if constexpr (!NetMirrored) SKIP("B0 does not mirror");
  auto net = random_net(8);
  int checked = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    std::uint64_t rng = 57 + checked;
    for (int ply = 0; ply < 40; ++ply) {
      Position flipped;
      std::string error;
      CHECK_MSG(flipped.set_fen(flip_files(pos.fen()), &error), flip_files(pos.fen()) + ": " + error);
      CHECK_MSG(full_eval(*net, pos) == full_eval(*net, flipped), pos.fen());
      ++checked;
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      if (legal.size() == 0) break;
      pos.make(legal[splitmix_next(rng) % legal.size()]);
    }
  }
  CHECK(checked > 100);
}

#if FORK_NET_ARCH == 5
TEST_CASE("nnue", "XGR's exposure rule") {
  // A white knight attacked by a pawn (a lower class) is exposed though
  // defended; an undefended bishop attacked by the queen is exposed; a rook
  // defended by its king and attacked by nothing is not (the same position
  // as tools/nnue/test_bakeoff.py's check of the reference).
  Position pos;
  pos.set_fen("4k3/8/3p4/4N3/8/1q6/2B5/4K2R w - - 0 1");
  const Bitboard exposed = exposed_pieces(pos);
  CHECK(exposed & (Bitboard{1} << 36));    // e5
  CHECK(exposed & (Bitboard{1} << 10));    // c2
  CHECK(!(exposed & (Bitboard{1} << 7)));  // h1
}
#endif

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
