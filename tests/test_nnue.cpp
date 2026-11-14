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
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iterator>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include "core/material.hpp"
#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "eval/eval_scale.hpp"
#include "eval/nnue/accumulator.hpp"
#include "eval/nnue/contacts.hpp"
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
// squared outputs need |w| <= 128 and QA^2 times a bucket's sum of |w|
// within int32, so their weights stay within +-30 but for one +128 and one
// -128 per bucket (the edge values): at most 1,022 x 30 + 256 = 30,916, below
// 2^31 / 255^2 = 33,025.
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
  net->inputs = NetPieceSquares * net->region_count + (NetExposure ? NetExposureRows : 0) +
                (NetContacts ? NetContactInputs + NetLinkInputs : 0) + (NetLinks ? NetLinkInputs : 0);
  for (auto& w : net->ft_weights) w = static_cast<std::int16_t>(uniform(rng, -400, 400));
  // S512+PP's link rows sit in the same int16 sums, up to 64 at once, after
  // the piece rows (H512+PP: after every region's; S512+PPXL: after the
  // exposure rows, which stay within +-400, summed in 32 bits): within +-150
  // (2000 + 32 x 400 + 64 x 150 < 32767). Each region's piece rows are drawn
  // on their own, so every region differs.
  if constexpr (NetLinks) {
    const int first = NetPieceSquares * net->region_count + (NetExposure ? NetExposureRows : 0);
    for (int i = first * NetHidden; i < (first + NetLinkInputs) * NetHidden; ++i)
      net->ft_weights[i] = static_cast<std::int16_t>(uniform(rng, -150, 150));
  }
  for (auto& b : net->ft_bias) b = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
#if FORK_NET_ARCH == 1
  for (auto& w : net->out_weights) w = static_cast<std::int16_t>(uniform(rng, -2000, 2000));
  net->out_bias = uniform(rng, -100000, 100000);
#elif FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3 || FORK_NET_ARCH == 6 || FORK_NET_ARCH == 7 || \
    FORK_NET_ARCH == 8 || FORK_NET_ARCH == 9 || FORK_NET_ARCH == 10
  for (auto& row : net->out_weights) {
    for (auto& w : row) w = static_cast<std::int16_t>(uniform(rng, -30, 30));
    row[uniform(rng, 0, NetHidden - 1)] = 128;
    row[NetHidden + uniform(rng, 0, NetHidden - 1)] = -128;
  }
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
  for (auto& row : net->expert_weights) {
    for (auto& w : row) w = static_cast<std::int16_t>(uniform(rng, -30, 30));
    row[uniform(rng, 0, NetHidden - 1)] = 128;
    row[NetHidden + uniform(rng, 0, NetHidden - 1)] = -128;
  }
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
#if FORK_NET_LINKS
  // One link weight that the most links at once (64 at S512+PP's rank limit)
  // would take past int16 whatever unit 3's bias: its largest piece weight
  // is near the test bound 400, and 32 x 300 + 64 x 400 = 35,200 already
  // exceeds 32,767.
  auto linked = random_net(4);
  const int first_link = NetPieceSquares * linked->region_count + (NetExposure ? NetExposureRows : 0);
  linked->ft_weights[(first_link + 500) * NetHidden + 3] = 400;
  rejects(write_net_file(*linked), "a link weight that 64 links would take beyond int16");
#endif
#if FORK_NET_ARCH == 10
  // S512+PPXL's exposure rows are summed in 32 bits, so the reader bounds
  // only the piece and link rows: an exposure weight of 20,000 (the last
  // exposure row) is accepted, the same weight in the first link row refused.
  auto exposed_big = random_net(4);
  exposed_big->ft_weights[(first_link - 1) * NetHidden + 3] = 20000;
  CHECK_MSG(read_net_file(write_net_file(*exposed_big), *back, error), "a large exposure weight: " << error);
  auto link_big = random_net(4);
  link_big->ft_weights[first_link * NetHidden + 3] = 20000;
  rejects(write_net_file(*link_big), "a large weight in the first link row");
#endif
#if FORK_NET_ARCH == 9
  // The piece bound ranges over every region's rows: one weight of the last
  // region at 1,000 takes unit 5 past int16 (2000 + 32 x 1000 > 32,767) though
  // the first region's rows are all within 400.
  auto regional = random_net(4);
  regional->ft_weights[(NetPieceSquares * 3 + 100) * NetHidden + 5] = 1000;
  rejects(write_net_file(*regional), "a last-region piece weight beyond the int16 bound");
  // The map must fit the build: a fifth region is refused.
  auto five = random_net(4);
  five->regions[31] = 4;
  five->region_count = 5;
  rejects(write_net_file(*five), "a fifth king region");
#endif
#if FORK_NET_ARCH == 1
  auto wide = random_net(3);
  for (auto& w : wide->out_weights) w = 32000;
  rejects(write_net_file(*wide), "an output sum beyond int32");
#elif FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3 || FORK_NET_ARCH == 6
  auto wide = random_net(3);
  wide->out_weights[2][5] = 129;
  rejects(write_net_file(*wide), "an output weight beyond the squared output's bound");
#endif
#if FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3 || FORK_NET_ARCH == 5 || FORK_NET_ARCH == 6 || \
    FORK_NET_ARCH == 7 || FORK_NET_ARCH == 8 || FORK_NET_ARCH == 9 || FORK_NET_ARCH == 10
  // Bug review 2026-11-11, E3: every output weight within the |w| <= 128
  // bound, but one bucket's QA^2 sum of |w| beyond int32, where the AVX2
  // path's 32-bit lane sums could overflow (all 2H weights at 128: 255^2 x
  // 1,024 x 128 = 8.5e9). The reader refuses it; one weight less than the
  // bound's limit is accepted. 2^31 / 255^2 = 33,025.5, so a bucket summing
  // to 33,025 fits (2,147,450,625) and 33,026 does not (2,147,515,650).
#if FORK_NET_ARCH == 5
  auto bucket = [](NetFile& n) -> auto& { return n.expert_weights[1]; };
#else
  auto bucket = [](NetFile& n) -> auto& { return n.out_weights[NetBuckets - 1]; };
#endif
  auto set_sum = [&](NetFile& n, int sum) {
    auto& row = bucket(n);
    for (auto& w : row) w = 0;
    for (int i = 0; sum > 0; ++i, sum -= 128) row[i] = static_cast<std::int16_t>(std::min(sum, 128));
  };
  auto loud_out = random_net(3);
  for (auto& w : bucket(*loud_out)) w = 128;
  rejects(write_net_file(*loud_out), "a bucket whose squared sum can leave int32 (every weight 128)");
  auto edge = random_net(3);
  set_sum(*edge, 33026);
  rejects(write_net_file(*edge), "a bucket at 255^2 x 33,026, one past int32");
  set_sum(*edge, 33025);
  CHECK_MSG(read_net_file(write_net_file(*edge), *back, error), "a bucket at 255^2 x 33,025: " << error);
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

#if FORK_NET_ARCH == 9
// H512+PP's evaluation the obvious way, an oracle independent of
// accumulate_board, feature_index and frame_of: per perspective, the bias,
// each piece's row in the block of its own king's region (the mirrored cell
// read in the net's map) and each pawn link's row after all the region
// blocks, summed in 64 bits, clipped to [0, QA], then the squared output of
// the phase's bucket.
int h512pp_reference(const NetFile& net, const Position& pos) {
  const Color stm = pos.side_to_move();
  const int bucket = net.phase_table[game_phase(pos)];
  std::int64_t total = 0;
  for (int half = 0; half < 2; ++half) {
    const Color persp = half == 0 ? stm : ~stm;
    const int vertical = persp == White ? 0 : 56;  // Black sees the board upside down
    const int king = pos.king_square(persp) ^ vertical;
    const int files = king % 8 < 4 ? 7 : 0;  // mirrored when the own king is on files a-d
    const int cell = (king ^ files) / 8 * 4 + (king ^ files) % 8 - 4;
    const int block = NetPieceSquares * net.regions[cell];
    std::vector<int> rows;
    for (Bitboard b = pos.pieces(); b;) {
      const Square s = pop_lsb(b);
      const Piece p = pos.piece_at(s);
      rows.push_back(block + 384 * (side_of(p) != persp) + 64 * kind_of(p) + ((s ^ vertical) ^ files));
    }
    std::int32_t links[LinkMaxActive];
    const int n = link_inputs(pos.pieces(White, Pawn), pos.pieces(Black, Pawn), persp, files, links);
    for (int k = 0; k < n; ++k) rows.push_back(NetPieceSquares * net.region_count + links[k]);
    for (int i = 0; i < NetHidden; ++i) {
      std::int64_t v = net.ft_bias[i];
      for (const int r : rows) v += net.ft_weights[r * NetHidden + i];
      const std::int64_t x = std::clamp<std::int64_t>(v, 0, NetQa);
      total += x * x * net.out_weights[bucket][half * NetHidden + i];
    }
  }
  const std::int64_t y = total / NetQa + net.out_bias[bucket];
  return static_cast<int>(
      std::clamp<std::int64_t>(y * net.scale / (NetQa * NetQb), -(EvalLimit - 1), EvalLimit - 1));
}

TEST_CASE("nnue", "H512+PP's regions follow the M4 map of the mirrored own-king cell") {
  // Worked by hand from the map (e1 | f1-h1 | rank 2 | ranks 3-8, in the
  // perspective's view, files a-d mirrored onto e-h); squares a1 = 0 ... h8 = 63.
  auto net = random_net(9);
  const struct {
    Color perspective;
    Square king;
    int region, flip;
  } cases[] = {
      {White, 4, 0, 0},   // e1
      {White, 3, 0, 7},   // d1: e1 mirrored
      {White, 6, 1, 0},   // g1
      {White, 1, 1, 7},   // b1: g1 mirrored
      {White, 7, 1, 0},   // h1
      {White, 12, 2, 0},  // e2
      {White, 8, 2, 7},   // a2: h2 mirrored
      {White, 20, 3, 0},  // e3
      {White, 63, 3, 0},  // h8
      {Black, 60, 0, 0},  // e8, Black's e1
      {Black, 62, 1, 0},  // g8, Black's g1
      {Black, 50, 2, 7},  // c7, Black's c2: f2 mirrored
      {Black, 4, 3, 0},   // e1, Black's e8
  };
  for (const auto& c : cases) {
    const Frame f = frame_of(*net, c.perspective, c.king);
    CHECK_MSG(f.offset == NetPieceSquares * c.region && f.flip == c.flip,
              "king on " << int{c.king} << ": region " << f.offset / NetPieceSquares << ", flip " << f.flip);
  }
}

TEST_CASE("nnue", "H512+PP's evaluation equals the obvious reference along random games") {
  // Every region of both perspectives is reached (the games walk the kings
  // about), and the stack's incremental evaluations equal the reference too.
  auto net = random_net(14);
  auto stack = std::make_unique<FeatureStack>();
  int checked = 0;
  bool seen[2][4] = {};
  for (const auto& sp : perft_suite()) {
    for (std::uint64_t seed = 1; seed <= 4; ++seed) {
      Position pos;
      pos.set_fen(sp.fen);
      stack->reset(*net, pos);
      std::uint64_t rng = seed * 6007 + checked;
      for (int ply = 0; ply < 100 && ply < MaxPly - 1; ++ply) {
        const int want = h512pp_reference(*net, pos);
        CHECK_MSG(full_eval(*net, pos) == want, pos.fen());
        CHECK_MSG(stack->evaluate(*net, ply, pos) == want, pos.fen());
        for (const Color c : {White, Black})
          seen[c][frame_of(*net, c, pos.king_square(c)).offset / NetPieceSquares] = true;
        ++checked;
        MoveList legal;
        generate<GenMode::Legal>(pos, legal);
        if (legal.size() == 0) break;
        Move m = legal[splitmix_next(rng) % legal.size()];
        for (Move k : legal)  // king moves favoured, so regions change often
          if (kind_of(pos.piece_at(k.from())) == King && splitmix_next(rng) % 3 == 0) {
            m = k;
            break;
          }
        stack->push_move(*net, ply, pos, m);
        pos.make(m);
      }
    }
  }
  CHECK(checked > 1000);
  for (const auto& side : seen)
    for (const bool region : side) CHECK(region);
}
#endif

#if FORK_NET_ARCH == 10
// S512+PPXL's evaluation the obvious way, an oracle independent of
// accumulate_board, feature_index, frame_of and exposed_lower: per
// perspective, the bias, each piece's row, each pawn link's row (after the
// 768 piece rows and the 640 exposure rows) and each exposed piece's
// exposure row (exposed_lower_reference's set, square by square; 768 + 320 x
// [enemy] + 64 x type + the perspective's square), summed in 64 bits,
// clipped to [0, QA], then the squared output of the phase's bucket. `beyond`
// counts the units whose sum leaves int16.
namespace {

int s512ppxl_reference(const NetFile& net, const Position& pos, int* beyond = nullptr) {
  const Bitboard exposed = exposed_lower_reference(pos);
  const Color stm = pos.side_to_move();
  const int bucket = net.phase_table[game_phase(pos)];
  std::int64_t total = 0;
  for (int half = 0; half < 2; ++half) {
    const Color persp = half == 0 ? stm : ~stm;
    const int vertical = persp == White ? 0 : 56;  // Black sees the board upside down
    const int files = (pos.king_square(persp) ^ vertical) % 8 < 4 ? 7 : 0;  // own king on files a-d: mirrored
    std::vector<int> rows;
    for (Bitboard b = pos.pieces(); b;) {
      const Square s = pop_lsb(b);
      const Piece p = pos.piece_at(s);
      const int seen = (s ^ vertical) ^ files;
      rows.push_back(384 * (side_of(p) != persp) + 64 * kind_of(p) + seen);
      if (exposed & (Bitboard{1} << s))
        rows.push_back(768 + 320 * (side_of(p) != persp) + 64 * kind_of(p) + seen);
    }
    std::int32_t links[LinkMaxActive];
    const int n = link_inputs(pos.pieces(White, Pawn), pos.pieces(Black, Pawn), persp, files, links);
    for (int k = 0; k < n; ++k) rows.push_back(768 + 640 + links[k]);
    int out_of_range = 0;
    for (int i = 0; i < NetHidden; ++i) {
      std::int64_t v = net.ft_bias[i];
      for (const int r : rows) v += net.ft_weights[r * NetHidden + i];
      out_of_range += v < -32768 || v > 32767;
      const std::int64_t x = std::clamp<std::int64_t>(v, 0, NetQa);
      total += x * x * net.out_weights[bucket][half * NetHidden + i];
    }
    if (beyond) *beyond += out_of_range;
  }
  const std::int64_t y = total / NetQa + net.out_bias[bucket];
  return static_cast<int>(std::clamp<std::int64_t>(y * net.scale / (std::int64_t{NetQa} * NetQb),
                                                   -(EvalLimit - 1), EvalLimit - 1));
}

}  // namespace

TEST_CASE("nnue", "S512+PPXL's exposure rule is the lower-class half") {
  // Worked by hand (a1 = 0 ... h8 = 63). 4k3/8/3p4/4N3/8/1q6/2B5/4K2R: the
  // knight on e5 is attacked by the pawn on d6 (exposed though a pawn is the
  // only attacker class below it); the queen on b3 by the bishop on c2
  // (exposed); the bishop on c2 only by the queen, a higher class (not
  // exposed, though undefended: the dropped half of XGR's rule); the rook on
  // h1 by nothing; the pawn never.
  // 6k1/8/5b2/8/3R4/8/8/3qQ1K1: the rook on d4 is attacked by the bishop on
  // f6 (exposed); the black queen on d1 by the rook on d4 (exposed); the
  // white queen on e1 only by the queen on d1, the same class (not exposed);
  // the bishop on f6 by nothing.
  const struct {
    const char* fen;
    Bitboard want;
  } cases[] = {
      {"4k3/8/3p4/4N3/8/1q6/2B5/4K2R w - - 0 1", (Bitboard{1} << 36) | (Bitboard{1} << 17)},
      {"6k1/8/5b2/8/3R4/8/8/3qQ1K1 w - - 0 1", (Bitboard{1} << 27) | (Bitboard{1} << 3)},
      {"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 0},
  };
  for (const auto& c : cases) {
    Position pos;
    CHECK(pos.set_fen(c.fen));
    CHECK_MSG(exposed_lower_reference(pos) == c.want, c.fen);
    CHECK_MSG(exposed_lower(pos) == c.want, c.fen);
  }
}

TEST_CASE("nnue", "S512+PPXL's exposed set matches the square-by-square reference along random games") {
  int checked = 0, nonempty = 0;
  for (const auto& sp : perft_suite()) {
    for (std::uint64_t seed = 1; seed <= 4; ++seed) {
      Position pos;
      pos.set_fen(sp.fen);
      std::uint64_t rng = seed * 4099 + checked;
      for (int ply = 0; ply < 100; ++ply) {
        const Bitboard want = exposed_lower_reference(pos);
        CHECK_MSG(exposed_lower(pos) == want, pos.fen());
        CHECK_MSG(!(want & (pos.pieces(Pawn) | pos.pieces(King))), pos.fen());
        nonempty += want != 0;
        ++checked;
        MoveList legal;
        generate<GenMode::Legal>(pos, legal);
        if (legal.size() == 0) break;
        pos.make(legal[splitmix_next(rng) % legal.size()]);
      }
    }
  }
  CHECK(checked > 1000);
  CHECK(nonempty > 200);
}

// The exposed sets of the 446 parity positions (tests/nnue/parity.epd) equal
// the Python reference's, computed on python-chess's attack sets
// (tests/nnue/s512ppxl-exposed.txt, written by `tools/nnue/reference.py
// exposed --epd tests/nnue/parity.epd --layout tools/nnue/s512ppxl.json`):
// the engine's half of the feature parity with the trainer, whose half is
// the feature leg against the same reference.
TEST_CASE("nnue", "S512+PPXL's exposed sets equal the Python reference's") {
  std::ifstream in(std::string(FORK_SOURCE_DIR) + "/tests/nnue/s512ppxl-exposed.txt");
  CHECK_MSG(in.good(), "tests/nnue/s512ppxl-exposed.txt is missing");
  int compared = 0, nonempty = 0;
  for (std::string line; std::getline(in, line);) {
    const std::size_t a = line.find('|');
    if (a == std::string::npos) continue;
    Position pos;
    CHECK_MSG(pos.set_fen(line.substr(0, a)), line.substr(0, a));
    Bitboard want = 0;
    std::istringstream is(line.substr(a + 1));
    for (int s; is >> s;) want |= Bitboard{1} << s;
    CHECK_MSG(exposed_lower(pos) == want, line.substr(0, a));
    CHECK_MSG(exposed_lower_reference(pos) == want, line.substr(0, a));
    nonempty += want != 0;
    ++compared;
  }
  CHECK_EQ(compared, 446);
  CHECK(nonempty > 50);
}

TEST_CASE("nnue", "S512+PPXL's evaluation equals the obvious reference along random games") {
  // Ordinary weights (exposure rows within +-400), then exposure rows of up to
  // +-20,000 per unit, so a few exposed pieces take a unit's sum past int16:
  // the reader accepts them (the exposure rows are not bounded) and the 32-bit
  // sums give the 64-bit reference's values. The stack's incremental
  // evaluations equal the reference too.
  for (const bool large : {false, true}) {
    auto net = random_net(16);
    std::uint64_t rng = 2026111402;
    if (large)
      for (int f = NetPieceSquares; f < NetPieceSquares + NetExposureRows; ++f)
        for (int i = 0; i < NetHidden; ++i)
          net->ft_weights[f * NetHidden + i] = static_cast<std::int16_t>(uniform(rng, -20000, 20000));
    auto back = std::make_unique<NetFile>();
    std::string error;
    CHECK_MSG(read_net_file(write_net_file(*net), *back, error), error);
    auto stack = std::make_unique<FeatureStack>();
    int checked = 0, exposed = 0, beyond = 0;
    for (const auto& sp : perft_suite()) {
      for (std::uint64_t seed = 1; seed <= 3; ++seed) {
        Position pos;
        pos.set_fen(sp.fen);
        stack->reset(*back, pos);
        std::uint64_t game = seed * 7907 + checked;
        for (int ply = 0; ply < std::min(80, MaxPly - 1); ++ply) {
          int units = 0;
          const int want = s512ppxl_reference(*back, pos, &units);
          CHECK_MSG(full_eval(*back, pos) == want, pos.fen());
          CHECK_MSG(evaluate_position_scalar(
                        *back,
                        [&] {
                          Accumulator acc;
                          accumulate_board(*back, pos, acc);
                          return acc;
                        }(),
                        pos) == want,
                    pos.fen());
          CHECK_MSG(stack->evaluate(*back, ply, pos) == want, pos.fen());
          exposed += exposed_lower_reference(pos) != 0;
          beyond += units > 0;
          ++checked;
          MoveList legal;
          generate<GenMode::Legal>(pos, legal);
          if (legal.size() == 0) break;
          const Move m = legal[splitmix_next(game) % legal.size()];
          stack->push_move(*back, ply, pos, m);
          pos.make(m);
        }
      }
    }
    CHECK(checked > 1000);
    CHECK(exposed > 200);
    if (large) CHECK(beyond > 20);  // positions where some unit's sum left int16
  }
}
#endif

// FeatureStack along a search tree: a random walk with backtracking, king
// moves favoured so frames change often (in H512+PP a frame's snapshot is
// then several pieces and pawn links away from the board it is brought to),
// null moves among the moves, every evaluation of a random half of the nodes
// against a refresh (H512+PP: against the reference too).
TEST_CASE("nnue", "frame changes keep evaluations exact along a search tree") {
  auto net = random_net(15);
  auto stack = std::make_unique<FeatureStack>();
  int checked = 0, frame_changes = 0;
  std::uint64_t rng = 2026111401;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    stack->reset(*net, pos);
    const auto walk = [&](auto&& self, int ply, int depth) -> void {
      if (splitmix_next(rng) % 2 == 0) {
        const int got = stack->evaluate(*net, ply, pos);
        CHECK_MSG(got == full_eval(*net, pos), pos.fen());
#if FORK_NET_ARCH == 9
        CHECK_MSG(got == h512pp_reference(*net, pos), pos.fen());
#elif FORK_NET_ARCH == 10
        CHECK_MSG(got == s512ppxl_reference(*net, pos), pos.fen());
#endif
        ++checked;
      }
      if (depth == 0) return;
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      if (legal.size() == 0) return;
      for (int child = 0; child < 3; ++child) {
        if (!pos.in_check() && splitmix_next(rng) % 8 == 0) {
          stack->push_null(ply);
          pos.make_null();
          self(self, ply + 1, depth - 1);
          pos.unmake_null();
          continue;
        }
        Move m = legal[splitmix_next(rng) % legal.size()];
        if (splitmix_next(rng) % 2 == 0)
          for (Move k : legal)
            if (kind_of(pos.piece_at(k.from())) == King && splitmix_next(rng) % 2 == 0) {
              m = k;
              break;
            }
        const Color us = pos.side_to_move();
        const Frame before = frame_of(*net, us, pos.king_square(us));
        stack->push_move(*net, ply, pos, m);
        pos.make(m);
        frame_changes += frame_of(*net, us, pos.king_square(us)) != before;
        self(self, ply + 1, depth - 1);
        pos.unmake(m);
      }
    };
    walk(walk, 0, 6);
  }
  CHECK(checked > 1000);
  if constexpr (NetMirrored) CHECK(frame_changes > 100);
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

#if FORK_NET_ARCH == 5 || FORK_NET_ARCH == 6
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

// The rule square by square, from each piece's attackers (the first
// implementation's method), as the reference for the set-wise one.
Bitboard exposed_reference(const Position& pos) {
  constexpr int Class[6] = {1, 2, 2, 3, 4, 5};
  const Bitboard occ = pos.pieces();
  Bitboard out = 0;
  for (Bitboard b = occ & ~pos.pieces(King); b;) {
    const Square s = pop_lsb(b);
    const Color c = side_of(pos.piece_at(s));
    const Bitboard attackers = pos.attackers_to(s, occ);
    const Bitboard enemy = attackers & pos.pieces(~c);
    if (!enemy) continue;
    int lowest = 5;
    for (const PieceType t : {Queen, Rook, Bishop, Knight, Pawn})
      if (enemy & pos.pieces(t)) lowest = Class[t];
    if (lowest < Class[kind_of(pos.piece_at(s))] || !(attackers & pos.pieces(c))) out |= Bitboard{1} << s;
  }
  return out;
}

TEST_CASE("nnue", "XGR's exposure rule matches the square-by-square reference along random games") {
  int checked = 0, nonempty = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    std::uint64_t rng = 91 + checked;
    for (int ply = 0; ply < 80; ++ply) {
      const Bitboard got = exposed_pieces(pos), want = exposed_reference(pos);
      CHECK_MSG(got == want, pos.fen());
      nonempty += want != 0;
      ++checked;
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      if (legal.size() == 0) break;
      pos.make(legal[splitmix_next(rng) % legal.size()]);
    }
  }
  CHECK(checked > 200);
  CHECK(nonempty > 50);
}
#endif

#if FORK_NET_ARCH == 6
// S512+X's evaluation the obvious way: per perspective, the bias, every
// piece's row and every exposed piece's exposure row (the square-by-square
// rule) summed in 64 bits, clipped to [0, QA], then S-512's squared output
// in the phase's bucket. `beyond` counts the units whose sum leaves int16.
int s512x_reference(const NetFile& net, const Position& pos, int* beyond = nullptr) {
  const Bitboard exposed = exposed_reference(pos);
  const Color stm = pos.side_to_move();
  const int k = net.phase_table[game_phase(pos)];
  std::int64_t total = 0;
  for (int half = 0; half < 2; ++half) {
    const Color persp = half == 0 ? stm : ~stm;
    const Frame f = frame_of(net, persp, pos.king_square(persp));
    for (int i = 0; i < NetHidden; ++i) {
      std::int64_t v = net.ft_bias[i];
      for (Bitboard b = pos.pieces(); b;) {
        const Square s = pop_lsb(b);
        const Piece p = pos.piece_at(s);
        v += net.ft_weights[feature_index(persp, p, s, f) * NetHidden + i];
        if (exposed & (Bitboard{1} << s)) {
          const Square seen = persp == White ? s : s ^ 56;
          const int row = NetPieceSquares + 320 * (side_of(p) != persp) + 64 * kind_of(p) + (seen ^ f.flip);
          v += net.ft_weights[row * NetHidden + i];
        }
      }
      if (beyond && (v < -32768 || v > 32767)) ++*beyond;
      const std::int64_t x = std::clamp<std::int64_t>(v, 0, NetQa);
      total += x * x * net.out_weights[k][half * NetHidden + i];
    }
  }
  const std::int64_t y = total / NetQa + net.out_bias[k];
  return static_cast<int>(
      std::clamp<std::int64_t>(y * net.scale / (NetQa * NetQb), -(EvalLimit - 1), EvalLimit - 1));
}

TEST_CASE("nnue", "S512+X sums its exposure rows beyond the int16 range exactly") {
  // Exposure rows of up to +-20,000 per unit: a few exposed pieces take a
  // unit's sum past int16, which the reader accepts (only the piece rows are
  // bounded) and the evaluation handles as the 64-bit reference does.
  auto net = random_net(12);
  std::uint64_t rng = 77;
  for (int f = NetPieceSquares; f < net->inputs; ++f)
    for (int i = 0; i < NetHidden; ++i)
      net->ft_weights[f * NetHidden + i] = static_cast<std::int16_t>(uniform(rng, -20000, 20000));
  auto back = std::make_unique<NetFile>();
  std::string error;
  CHECK_MSG(read_net_file(write_net_file(*net), *back, error), error);
  int checked = 0, beyond = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    std::uint64_t game = 5 + checked;
    for (int ply = 0; ply < 60; ++ply) {
      int units = 0;
      CHECK_MSG(full_eval(*back, pos) == s512x_reference(*back, pos, &units), pos.fen());
      beyond += units > 0;
      ++checked;
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      if (legal.size() == 0) break;
      pos.make(legal[splitmix_next(game) % legal.size()]);
    }
  }
  CHECK(checked > 200);
  CHECK(beyond > 20);  // positions where some unit's sum left int16
}

TEST_CASE("nnue", "S512+X's evaluation equals the reference with ordinary weights") {
  auto net = random_net(13);
  int checked = 0;
  for (const auto& sp : perft_suite()) {
    Position pos;
    pos.set_fen(sp.fen);
    std::uint64_t game = 17 + checked;
    for (int ply = 0; ply < 60; ++ply) {
      CHECK_MSG(full_eval(*net, pos) == s512x_reference(*net, pos), pos.fen());
      ++checked;
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      if (legal.size() == 0) break;
      pos.make(legal[splitmix_next(game) % legal.size()]);
    }
  }
  CHECK(checked > 200);
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

// S512cl's contact and link inputs (ideas.md 41; contacts.hpp): the index
// space has the sizes net_shape.hpp gives (the reference's and the
// trainer's too), and each perspective's inputs on 200 parity positions are
// the Python reference's (tests/nnue/s512cl-contacts.txt, written by
// `tools/nnue/contacts.py lists tests/nnue/parity.epd --count 200` from
// python-chess's attack sets; compared as sorted lists). Any build but
// S512+PP's and H512+PP's, whose links have a rank limit (the frame's file
// flip is computed here, not taken from the network).
#if !FORK_NET_LINKS
TEST_CASE("nnue", "S512cl's contact and link inputs equal the Python reference's") {
  CHECK_EQ(contact_table_size(), NetContactInputs);
  CHECK_EQ(link_table_size(), NetLinkInputs);
  std::ifstream in(std::string(FORK_SOURCE_DIR) + "/tests/nnue/s512cl-contacts.txt");
  CHECK_MSG(in.good(), "tests/nnue/s512cl-contacts.txt is missing");
  const auto numbers = [](const std::string& text) {
    std::vector<std::int32_t> v;
    std::istringstream is(text);
    for (std::int32_t x; is >> x;) v.push_back(x);
    return v;
  };
  int compared = 0;
  for (std::string line; std::getline(in, line);) {
    const std::size_t a = line.find('|'), b = line.find('|', a + 1);
    if (a == std::string::npos || b == std::string::npos) continue;
    Position pos;
    CHECK_MSG(pos.set_fen(line.substr(0, a)), line.substr(0, a));
    const std::vector<std::int32_t> want[2] = {numbers(line.substr(a + 1, b - a - 1)),
                                               numbers(line.substr(b + 1))};
    for (int k = 0; k < 2; ++k) {
      const Color perspective = k == 0 ? pos.side_to_move() : ~pos.side_to_move();
      const Square seen =
          perspective == White ? pos.king_square(perspective) : pos.king_square(perspective) ^ 56;
      std::int32_t out[ContactMaxActive];
      const int n = contact_inputs(pos, perspective, (seen & 7) < 4 ? 7 : 0, out);
      std::vector<std::int32_t> got(out, out + n);
      std::sort(got.begin(), got.end());
      CHECK_MSG(got == want[k], line.substr(0, a) << (k == 0 ? " (side to move)" : " (the other side)"));
      ++compared;
    }
  }
  CHECK_EQ(compared, 400);
}
#endif

// The added-rows kernel's vector path (AVX-512 or AVX2 as built) equals its
// scalar reference bit for bit: random rows and counts up to the most active
// inputs, and rows at the int16 extremes, whose sums pass the int16 range
// both ways and must saturate.
TEST_CASE("nnue", "the added-rows kernel equals its scalar reference, saturation included") {
  std::uint64_t rng = 2026110541;
  std::vector<std::int16_t> pool(std::size_t{ContactMaxActive + 2} * NetHidden);
  alignas(64) std::int16_t base[NetHidden], vec[NetHidden], ref[NetHidden];
  std::vector<const std::int16_t*> rows(ContactMaxActive);
  int saturated = 0;
  for (int round = 0; round < 60; ++round) {
    const bool extreme = round % 3 == 0;
    for (auto& v : pool)
      v = static_cast<std::int16_t>(extreme ? (splitmix_next(rng) % 2 ? 32767 : -32768)
                                            : uniform(rng, -600, 600));
    for (auto& v : base) v = static_cast<std::int16_t>(uniform(rng, -32768, 32767));
    const int count = round < 3 ? round : uniform(rng, 0, ContactMaxActive);
    for (int r = 0; r < count; ++r)
      rows[r] =
          pool.data() + std::size_t{static_cast<unsigned>(uniform(rng, 0, ContactMaxActive + 1))} * NetHidden;
    sum_rows_saturated(base, rows.data(), count, vec);
    sum_rows_saturated_scalar(base, rows.data(), count, ref);
    CHECK_MSG(std::memcmp(vec, ref, sizeof vec) == 0, "round " << round << ", " << count << " rows");
    for (int i = 0; i < NetHidden; ++i) saturated += ref[i] == 32767 || ref[i] == -32768;
  }
  CHECK(saturated > 1000);  // the extreme rounds reached both limits
}

// The link inputs from the pawns alone equal the reference's links
// (tools/nnue/contacts.py), ascending: in S512+PP's builds those of its rank
// limit (tests/nnue/s512pp-links.txt, written by `contacts.py links
// tests/nnue/parity.epd --ranks 1 --count 200`), in the others S512cl's (the
// link block of tests/nnue/s512cl-contacts.txt).
TEST_CASE("nnue", "the link inputs from the pawns equal the Python reference's") {
  CHECK_EQ(link_table_size(), NetLinkInputs);
  const std::string file = NetLinkRanks == 1 ? "s512pp-links.txt" : "s512cl-contacts.txt";
  const int offset = NetLinkRanks == 1 ? 0 : NetContactInputs;  // the link block's first number in the file
  std::ifstream in(std::string(FORK_SOURCE_DIR) + "/tests/nnue/" + file);
  CHECK_MSG(in.good(), "tests/nnue/" << file << " is missing");
  int compared = 0, nonempty = 0;
  for (std::string line; std::getline(in, line);) {
    const std::size_t a = line.find('|'), b = line.find('|', a + 1);
    if (a == std::string::npos || b == std::string::npos) continue;
    Position pos;
    CHECK_MSG(pos.set_fen(line.substr(0, a)), line.substr(0, a));
    for (int k = 0; k < 2; ++k) {
      std::istringstream is(k == 0 ? line.substr(a + 1, b - a - 1) : line.substr(b + 1));
      std::vector<std::int32_t> want;
      for (std::int32_t x; is >> x;)
        if (x >= offset) want.push_back(x - offset);
      const Color perspective = k == 0 ? pos.side_to_move() : ~pos.side_to_move();
      const Square seen =
          perspective == White ? pos.king_square(perspective) : pos.king_square(perspective) ^ 56;
      std::int32_t out[LinkMaxActive];
      const int n = link_inputs(pos.pieces(White, Pawn), pos.pieces(Black, Pawn), perspective,
                                (seen & 7) < 4 ? 7 : 0, out);
      const std::vector<std::int32_t> got(out, out + n);
      CHECK_MSG(std::is_sorted(got.begin(), got.end()), line.substr(0, a));
      std::sort(want.begin(), want.end());
      CHECK_MSG(got == want, line.substr(0, a) << (k == 0 ? " (side to move)" : " (the other side)"));
      nonempty += n > 0;
      ++compared;
    }
  }
  CHECK_EQ(compared, 400);
  CHECK(nonempty > 200);
}

// S512+PP's incremental link change equals the difference of the full lists
// before and after each move, along random games from the perft suite
// (captures of pawns, promotions and en passant among the moves), both
// perspectives in both frames.
TEST_CASE("nnue", "a move's link changes equal the difference of the full link lists") {
  int moves = 0, changed = 0;
  for (const auto& sp : perft_suite()) {
    for (std::uint64_t seed = 1; seed <= 6; ++seed) {
      Position pos;
      pos.set_fen(sp.fen);
      std::uint64_t rng = seed * 104729 + moves;
      for (int ply = 0; ply < 60; ++ply) {
        MoveList legal;
        generate<GenMode::Legal>(pos, legal);
        if (legal.size() == 0) break;
        const Move m = legal[splitmix_next(rng) % legal.size()];
        const Bitboard before[2] = {pos.pieces(White, Pawn), pos.pieces(Black, Pawn)};
        pos.make(m);
        const Bitboard after[2] = {pos.pieces(White, Pawn), pos.pieces(Black, Pawn)};
        for (const Color perspective : {White, Black})
          for (const int flip : {0, 7}) {
            std::int32_t was[LinkMaxActive], now[LinkMaxActive], removed[LinkMaxActive], added[LinkMaxActive];
            const int a = link_inputs(before[White], before[Black], perspective, flip, was);
            const int b = link_inputs(after[White], after[Black], perspective, flip, now);
            std::vector<std::int32_t> want_removed, want_added;
            std::set_difference(was, was + a, now, now + b, std::back_inserter(want_removed));
            std::set_difference(now, now + b, was, was + a, std::back_inserter(want_added));
            int subs = 0, adds = 0;
            link_changes(before, after, perspective, flip, removed, subs, added, adds);
            std::vector<std::int32_t> got_removed(removed, removed + subs), got_added(added, added + adds);
            std::sort(got_removed.begin(), got_removed.end());
            std::sort(got_added.begin(), got_added.end());
            CHECK_MSG(got_removed == want_removed && got_added == want_added,
                      pos.fen() << " (after the move), flip " << flip);
            changed += subs + adds > 0;
          }
        ++moves;
      }
    }
  }
  CHECK(moves > 1000);
  CHECK(changed > 500);
}

}  // namespace forkeng::test
