// SPDX-License-Identifier: GPL-3.0-or-later

// The Boundary Refiner (ideas.md 59, step 3; docs/research/boundary-refiner/
// step3-plan.md): the window gate at its edges; the refiner's kernels against
// their scalar references and an independent reference written here; the
// reader against its writer and every bad field; the committed zero refiner
// (written by tools/nnue/refiner.py, an independent writer); the rows and
// the danger summary against slow square-by-square counts. Refiner builds
// (FORK_REFINER) also check the embedded refiner's binding to the base
// network, the refined value at a gated site, in the TT and reused (G0, G1),
// and the UCI options and info line. A refiner build's searches as a whole
// are checked by bench: with a zero refiner they equal the base network's
// own bench, with the gate on, off and with G1 (bench_parity,
// refiner_off_bench, refiner_reused_bench).
//
// Test positions: tests/nnue/parity.epd (its sources are cited in the file).
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iterator>
#include <limits>
#include <memory>
#include <string>
#include <vector>

#include "core/material.hpp"
#include "core/splitmix.hpp"
#include "eval/eval.hpp"
#include "eval/nnue/accumulator.hpp"
#include "eval/nnue/danger_summary.hpp"
#include "eval/nnue/net_file.hpp"
#include "eval/nnue/refiner.hpp"
#include "eval/nnue/refiner_file.hpp"
#include "harness.hpp"
#include "search/refiner_gate.hpp"
#ifdef FORK_REFINER
#include "engine_process.hpp"
#include "search/hash_memory.hpp"
#include "search/searcher.hpp"
#endif

#ifdef FORK_REFINER
namespace forkeng {
extern const unsigned char* const embedded_net_bytes;
}  // namespace forkeng
#endif

namespace forkeng::test {

TEST_CASE("refiner", "window_gap and the gate: the nearest finite bound, inclusive margins, -1 never") {
  CHECK_EQ(window_gap(10, 0, 50), 10);
  CHECK_EQ(window_gap(40, 0, 50), 10);
  CHECK_EQ(window_gap(-30, 0, 50), 30);  // below the window: still the distance
  CHECK_EQ(window_gap(10, -ScoreInfinite, 50), 40);
  CHECK_EQ(window_gap(10, 0, ScoreInfinite), 10);
  CHECK_EQ(window_gap(0, -ScoreInfinite, ScoreInfinite), -1);
  CHECK_EQ(window_gap(0, -(TbWinScore - 3), mate_score(5)), -1);
  const Position pos;
  RefinerGate g;
  g.margin_main = 25;
  g.margin_quiesce = 10;
  auto fires = [&](int eval, int alpha, int beta, bool quiesce) {
    return gate_fires(g, GateSite{pos, eval, alpha, beta, quiesce ? 0 : 3, 4, quiesce});
  };
  CHECK(fires(25, 0, 100, false));   // 25 from alpha: inclusive
  CHECK(!fires(26, 0, 100, false));  // 26: outside
  CHECK(fires(75, 0, 100, false));   // 25 from beta
  CHECK(!fires(25, 0, 100, true));   // quiescence has its own margin
  CHECK(fires(110, 0, 100, true));   // 10 above beta
  CHECK(!fires(0, -ScoreInfinite, ScoreInfinite, false));
  g.margin_main = -1;
  CHECK(!fires(0, 0, 100, false));  // -1 never fires, even on a bound
  g.margin_main = 0;
  CHECK(fires(0, 0, 100, false));
  CHECK(!fires(1, 0, 100, false));
#ifndef FORK_REFINER
  const RefinerGate none;  // builds without a refiner never consult one
  CHECK_EQ(none.margin_main, -1);
  CHECK_EQ(none.margin_quiesce, -1);
#endif
}

TEST_CASE("refiner",
          "pack_clipped: the vector path equals the scalar one, the clip at QA, side to move first") {
  auto acc = std::make_unique<Accumulator>();
  std::uint64_t rng = 59;
  const std::int16_t edges[] = {-32768, -256, -1, 0, 1, 127, 128, 254, 255, 256, 1000, 32767};
  for (int round = 0; round < 64; ++round) {
    for (int c = 0; c < 2; ++c)
      for (int i = 0; i < NetHidden; ++i)
        acc->values[c][i] = round % 4 == 0 ? edges[splitmix_next(rng) % std::size(edges)]
                                           : static_cast<std::int16_t>(splitmix_next(rng));
    for (const Color stm : {White, Black}) {
      alignas(64) std::uint8_t vec[RefinerInputBytes], ref[RefinerInputBytes];
      pack_clipped(*acc, stm, vec);
      pack_clipped_scalar(*acc, stm, ref);
      CHECK(std::memcmp(vec, ref, sizeof vec) == 0);
      bool clipped = true;
      for (int half = 0; half < 2; ++half)
        for (int i = 0; i < NetHidden; ++i) {
          const int v = acc->values[half == 0 ? stm : ~stm][i];
          clipped &= ref[half * NetHidden + i] == (v < 0 ? 0 : v > 255 ? 255 : v);
        }
      CHECK_MSG(clipped, "round " << round);
    }
  }
}

// The middle layer and heads alone (DESIGN.md §7: the vector path beside its
// scalar reference, bit for bit): random weights and entry sums, and the
// bound's edge, where every activation is 255 and every middle weight +-64
// (each 8-bit multiply-add pair at +-32,640) with biases that bring the
// middle units back to chosen mid-range values, so a lost product shows.
TEST_CASE("refiner", "refiner_l2_heads: the vector path equals the scalar one and a plain 64-bit reference") {
  std::uint64_t rng = 67;
  auto draw = [&](int span) { return static_cast<int>(splitmix_next(rng) % (2 * span + 1)) - span; };
  auto plain = [](const RefinerFile& r, const std::int32_t* sums) {
    std::int64_t a[RefinerL1Width], b[RefinerL2Width], y[RefinerHeads];
    for (int o = 0; o < RefinerL1Width; ++o)
      a[o] = sums[o] <= 0 ? 0 : std::min<std::int64_t>(sums[o] / 64, 255);
    for (int m = 0; m < RefinerL2Width; ++m) {
      std::int64_t s = r.middle_bias[m];
      for (int o = 0; o < RefinerL1Width; ++o) s += a[o] * r.middle_weights[m][o];
      b[m] = s <= 0 ? 0 : std::min<std::int64_t>(s / 64, 255);
    }
    for (int h = 0; h < RefinerHeads; ++h) {
      std::int64_t s = r.head_bias[h];
      for (int m = 0; m < RefinerL2Width; ++m) s += b[m] * r.head_weights[h][m];
      y[h] = s;
    }
    RefinerOutput out;
    out.correction = static_cast<int>(std::clamp<std::int64_t>(y[0] * r.scale / (255 * 64), -r.cap, r.cap));
    out.confidence = static_cast<int>(std::clamp<std::int64_t>(y[1] * 1000 / (255 * 64), 0, 1000));
    return out;
  };
  int compared = 0, nonzero = 0, edges = 0;
  for (int round = 0; round < 400; ++round) {
    auto r = std::make_unique<RefinerFile>();
    std::int32_t sums[RefinerL1Width];
    const bool edge = round % 4 == 0;
    for (int m = 0; m < RefinerL2Width; ++m) {
      std::int64_t dense = 0;
      for (int o = 0; o < RefinerL1Width; ++o) {
        r->middle_weights[m][o] =
            static_cast<std::int8_t>(edge ? (splitmix_next(rng) % 2 ? 64 : -64) : draw(64));
        dense += 255 * r->middle_weights[m][o];
      }
      // At the edge: the bias leaves the unit at a chosen value in [1, 254].
      r->middle_bias[m] = edge ? static_cast<std::int32_t>(-dense + 64 * (1 + draw(126) + 127)) : draw(40000);
    }
    for (auto& unit : r->head_weights)
      for (auto& w : unit) w = static_cast<std::int16_t>(draw(round % 3 == 0 ? 32767 : 300));
    for (auto& b : r->head_bias) b = draw(100000);
    r->scale = round % 3 == 0 ? 1 : 89;
    r->cap = EvalLimit;
    for (auto& s : sums) s = edge ? 255 * 64 + static_cast<int>(splitmix_next(rng) % 64) : draw(25000);
    const RefinerOutput vec = refiner_l2_heads<false>(*r, sums), scalar = refiner_l2_heads<true>(*r, sums);
    const RefinerOutput ref = plain(*r, sums);
    CHECK_MSG(vec.correction == scalar.correction && vec.confidence == scalar.confidence,
              "round " << round << ": " << vec.correction << "/" << vec.confidence << " vs "
                       << scalar.correction << "/" << scalar.confidence);
    CHECK_MSG(scalar.correction == ref.correction && scalar.confidence == ref.confidence, "round " << round);
    ++compared;
    nonzero += ref.correction != 0;
    edges += edge;
  }
  CHECK_EQ(compared, 400);
  CHECK_EQ(edges, 100);
  CHECK_MSG(nonzero > 300, nonzero);
}

TEST_CASE("refiner",
          "run_refiner equals its scalar path and a plain 64-bit reference; the reader takes "
          "the writer's files and refuses every bad field") {
  // A refiner with random weights inside the reader's bounds: dense weights
  // in [-dense, dense], rows (file values) in [-row, row].
  auto random_refiner = [](std::uint64_t seed, int dense, int row) {
    auto r = std::make_unique<RefinerFile>();
    std::uint64_t rng = seed;
    auto draw = [&](int span) { return static_cast<int>(splitmix_next(rng) % (2 * span + 1)) - span; };
    for (auto& unit : r->entry_weights)
      for (auto& w : unit) w = static_cast<std::int8_t>(draw(dense));
    for (auto& b : r->entry_bias) b = draw(200000);
    for (auto& rw : r->row_weights)
      for (auto& w : rw) w = NetQa * draw(row);
    for (auto& unit : r->middle_weights)
      for (auto& w : unit) w = static_cast<std::int8_t>(draw(64));
    for (auto& b : r->middle_bias) b = draw(20000);
    for (auto& unit : r->head_weights)
      for (auto& w : unit) w = static_cast<std::int16_t>(draw(300));
    for (auto& b : r->head_bias) b = draw(100000);
    r->scale = 89;
    r->cap = EvalLimit;
    return r;
  };
  // The refiner's output computed plainly in 64 bits (the format's
  // arithmetic as refiner_file.hpp states it): an independent reference.
  auto plain_output = [](const RefinerFile& r, const RefinerInputs& in) {
    std::int64_t a[RefinerL1Width], b[RefinerL2Width], y[RefinerHeads];
    for (int o = 0; o < RefinerL1Width; ++o) {
      std::int64_t s = r.entry_bias[o];
      for (int i = 0; i < RefinerInputBytes; ++i) s += std::int64_t{in.bytes[i]} * r.entry_weights[o][i];
      for (int k = 0; k < in.row_count; ++k) s += r.row_weights[in.rows[k]][o];
      a[o] = s <= 0 ? 0 : std::min<std::int64_t>(s / 64, 255);
    }
    for (int m = 0; m < RefinerL2Width; ++m) {
      std::int64_t s = r.middle_bias[m];
      for (int o = 0; o < RefinerL1Width; ++o) s += a[o] * r.middle_weights[m][o];
      b[m] = s <= 0 ? 0 : std::min<std::int64_t>(s / 64, 255);
    }
    for (int h = 0; h < RefinerHeads; ++h) {
      std::int64_t s = r.head_bias[h];
      for (int m = 0; m < RefinerL2Width; ++m) s += b[m] * r.head_weights[h][m];
      y[h] = s;
    }
    RefinerOutput out;
    out.correction = static_cast<int>(std::clamp<std::int64_t>(y[0] * r.scale / (255 * 64), -r.cap, r.cap));
    out.confidence = static_cast<int>(std::clamp<std::int64_t>(y[1] * 1000 / (255 * 64), 0, 1000));
    return out;
  };
  std::uint64_t rng = 61;
  int compared = 0, nonzero = 0;
  for (int round = 0; round < 120; ++round) {
    const int dense = round % 3 == 0 ? 1 : round % 3 == 1 ? 4 : 64;
    const auto r = random_refiner(1000 + round, dense, round % 2 ? 40 : 4000);
    for (int k = 0; k < 4; ++k) {
      RefinerInputs in;
      for (auto& v : in.bytes)
        v = splitmix_next(rng) % 3 == 0 ? 0 : static_cast<std::uint8_t>(splitmix_next(rng));
      in.row_count = static_cast<int>(splitmix_next(rng) % (RefinerMaxActive + 1));
      for (int i = 0; i < in.row_count; ++i) in.rows[i] = static_cast<int>(splitmix_next(rng) % RefinerRows);
      const RefinerOutput vec = run_refiner(*r, in), scalar = run_refiner_scalar(*r, in),
                          plain = plain_output(*r, in);
      CHECK_MSG(vec.correction == scalar.correction && vec.confidence == scalar.confidence,
                "round " << round << ": " << vec.correction << "/" << vec.confidence << " vs "
                         << scalar.correction << "/" << scalar.confidence);
      CHECK_MSG(scalar.correction == plain.correction && scalar.confidence == plain.confidence,
                "round " << round << ": " << scalar.correction << "/" << scalar.confidence << " vs "
                         << plain.correction << "/" << plain.confidence);
      ++compared;
      nonzero += plain.correction != 0;
    }
  }
  CHECK_EQ(compared, 480);
  CHECK_MSG(nonzero > 100, nonzero);  // the comparisons are not all of zeros

  // The bound's edge: every byte 255 and every dense weight +-64, so each
  // 8-bit multiply-add pair reaches +-32,640; a bias brings the entry sums
  // back to an activation of 100, which the heads turn into a correction
  // that any lost product would change.
  auto edge = std::make_unique<RefinerFile>();
  for (int o = 0; o < RefinerL1Width; ++o) {
    const int sign = o % 2 ? -1 : 1;
    for (auto& w : edge->entry_weights[o]) w = static_cast<std::int8_t>(64 * sign);
    edge->entry_bias[o] = -sign * RefinerInputBytes * 255 * 64 + 64 * 100;
  }
  for (auto& unit : edge->middle_weights)
    for (auto& w : unit) w = 1;
  for (auto& unit : edge->head_weights)
    for (auto& w : unit) w = 100;
  edge->scale = 89;
  edge->cap = EvalLimit;
  RefinerInputs full;
  std::fill(std::begin(full.bytes), std::end(full.bytes), std::uint8_t{255});
  const RefinerOutput e = run_refiner(*edge, full);
  // a = 100 in every unit; b = 16 x 100 / 64 = 25 (8 units: 12); y = 32 x b x 100.
  const int middle = RefinerL1Width * 100 / 64;
  CHECK_EQ(e.correction, static_cast<int>(std::int64_t{32} * middle * 100 * 89 / (255 * 64)));
  CHECK_EQ(e.correction, plain_output(*edge, full).correction);
  CHECK_EQ(run_refiner_scalar(*edge, full).correction, e.correction);

  // Every weight zero: a zero correction and confidence for any input.
  auto zero = std::make_unique<RefinerFile>();
  zero->scale = 89;
  zero->cap = EvalLimit;
  bool all_zero = true;
  for (int k = 0; k < 50; ++k) {
    RefinerInputs in;
    for (auto& v : in.bytes) v = static_cast<std::uint8_t>(splitmix_next(rng));
    in.row_count = RefinerMaxActive;
    for (int i = 0; i < in.row_count; ++i) in.rows[i] = static_cast<int>(splitmix_next(rng) % RefinerRows);
    const RefinerOutput o = run_refiner(*zero, in);
    all_zero &= o.correction == 0 && o.confidence == 0;
  }
  CHECK(all_zero);

  // The reader against the writer, and every bad field.
  {
    const auto r = random_refiner(77, 64, 300);
    r->cap = 500;
    r->base_checksum = 0x0123456789abcdefULL;
    const std::vector<std::uint8_t> bytes = write_refiner_file(*r);
    CHECK_EQ(bytes.size(), std::size_t{64} + RefinerL1Width * RefinerInputBytes + 4 * RefinerL1Width +
                               2 * RefinerRows * RefinerL1Width + RefinerL2Width * RefinerL1Width +
                               4 * RefinerL2Width + 2 * RefinerHeads * RefinerL2Width + 4 * RefinerHeads);
    auto back = std::make_unique<RefinerFile>();
    std::string error;
    CHECK_MSG(read_refiner_file(bytes, *back, error), error);
    CHECK(std::memcmp(back->entry_weights, r->entry_weights, sizeof r->entry_weights) == 0);
    CHECK(std::memcmp(back->entry_bias, r->entry_bias, sizeof r->entry_bias) == 0);
    CHECK(std::memcmp(back->row_weights, r->row_weights, sizeof r->row_weights) == 0);
    CHECK(std::memcmp(back->middle_weights, r->middle_weights, sizeof r->middle_weights) == 0);
    CHECK(std::memcmp(back->middle_bias, r->middle_bias, sizeof r->middle_bias) == 0);
    CHECK(std::memcmp(back->head_weights, r->head_weights, sizeof r->head_weights) == 0);
    CHECK(std::memcmp(back->head_bias, r->head_bias, sizeof r->head_bias) == 0);
    CHECK_EQ(back->scale, 89);
    CHECK_EQ(back->cap, 500);
    CHECK_EQ(back->base_checksum, 0x0123456789abcdefULL);

    // One field changed: the reader refuses with the matching reason.
    auto refused = [&](std::vector<std::uint8_t> b, const std::string& reason) {
      std::string why;
      const bool ok = read_refiner_file(b, *back, why);
      CHECK_MSG(!ok && why.find(reason) != std::string::npos,
                "wanted '" << reason << "', got '" << why << "'");
    };
    auto patched = [&](std::size_t at, std::uint32_t v) {
      std::vector<std::uint8_t> b = bytes;
      for (int i = 0; i < 4; ++i) b[at + i] = static_cast<std::uint8_t>(v >> (8 * i));
      return b;
    };
    // The checksum recomputed after a payload change, so the payload's own
    // checks are reached.
    auto resealed = [&](std::vector<std::uint8_t> b) {
      const std::uint64_t sum = net_checksum(std::span<const std::uint8_t>(b).subspan(64));
      for (int i = 0; i < 8; ++i) b[40 + i] = static_cast<std::uint8_t>(sum >> (8 * i));
      return b;
    };
    refused({bytes.begin(), bytes.begin() + 40}, "shorter than a header");
    refused(patched(4, 0x0054454e), "not a Fork refiner file");  // "FORKNET": a net file's magic
    refused(patched(8, 2), "unknown format version");
    refused(patched(12, RefinerArchitecture == 1 ? 2 : 1), "refiner architecture");
    refused(patched(16, RefinerL1Width == 16 ? 8 : 16), "wrong layer sizes");
    refused(patched(20, 16), "wrong layer sizes");
    refused(patched(24, 3), "wrong layer sizes");
    refused(patched(28, 0), "output scale out of range");
    refused(patched(28, 100001), "output scale out of range");
    refused(patched(32, static_cast<std::uint32_t>(-1)), "cap out of range");
    refused(patched(32, EvalLimit + 1), "cap out of range");
    refused(patched(36, 1), "nonzero reserved header bytes");
    refused(patched(60, 1), "nonzero reserved header bytes");
    {
      std::vector<std::uint8_t> b = bytes;
      b[100] ^= 1;
      refused(b, "checksum mismatch");
      std::vector<std::uint8_t> shorter(bytes.begin(), bytes.end() - 1);
      refused(resealed(shorter), "payload too short");
      std::vector<std::uint8_t> longer = bytes;
      longer.push_back(0);
      refused(resealed(longer), "payload too long");
    }
    CHECK_MSG(read_refiner_file(patched(32, EvalLimit), *back, error), error);
    CHECK_MSG(read_refiner_file(patched(32, 0), *back, error), error);

    // The dense weights' bound, [-64, 64] (two products of a byte and such a
    // weight fit an int16 exactly): 64 and -64 pass, 65 and -65 do not.
    for (const int w : {64, -64, 65, -65}) {
      for (int layer = 0; layer < 2; ++layer) {
        auto bad = std::make_unique<RefinerFile>(*r);
        (layer == 0 ? bad->entry_weights[RefinerL1Width - 1][7] : bad->middle_weights[5][3]) =
            static_cast<std::int8_t>(w);
        const std::vector<std::uint8_t> b = write_refiner_file(*bad);
        if (w == 64 || w == -64)
          CHECK_MSG(read_refiner_file(b, *back, error), error);
        else
          refused(b, "a dense weight outside [-64, 64]");
      }
    }

    // A layer whose worst-case sum leaves int32: at the limit it passes, one
    // more and it does not (the worst case computed here from the weights).
    {
      auto bad = std::make_unique<RefinerFile>(*r);
      std::int64_t dense = 0;
      for (const auto w : bad->entry_weights[2]) dense += 255 * std::int64_t{w < 0 ? -w : w};
      std::vector<std::int64_t> rows;
      for (int i = 0; i < RefinerRows; ++i) rows.push_back(std::abs(std::int64_t{bad->row_weights[i][2]}));
      std::sort(rows.rbegin(), rows.rend());
      std::int64_t active = 0;
      for (int i = 0; i < RefinerMaxActive; ++i) active += rows[static_cast<std::size_t>(i)];
      const std::int64_t room = std::numeric_limits<std::int32_t>::max() - dense - active;
      bad->entry_bias[2] = static_cast<std::int32_t>(room);
      CHECK_MSG(read_refiner_file(write_refiner_file(*bad), *back, error), error);
      bad->entry_bias[2] = static_cast<std::int32_t>(room + 1);
      refused(write_refiner_file(*bad), "overflow");
      bad = std::make_unique<RefinerFile>(*r);
      bad->middle_bias[0] = std::numeric_limits<std::int32_t>::max();
      refused(write_refiner_file(*bad), "overflow");
      bad = std::make_unique<RefinerFile>(*r);
      bad->head_bias[1] = std::numeric_limits<std::int32_t>::min() + 1;
      refused(write_refiner_file(*bad), "overflow");
    }
  }
}

#if FORK_REFINER_ARCH == 1 && FORK_REFINER_L1 == 16 && FORK_NET_ARCH != 1 && FORK_NET_ARCH != 5
// tests/nnue/refiner-zero.frnet, written by tools/nnue/refiner.py zero
// --base nets/s512ppr3.fnet --arch 1 --l1 16 --cap 20000: every weight zero,
// S512ppr3's scale (S = 89) and payload checksum (5861c1a319ca267b; both
// from docs/nets.md), the cap at EvalLimit.
TEST_CASE("refiner",
          "the committed zero refiner reads as all zeros, bound to S512ppr3, and writes back the same") {
  std::ifstream in(std::string(FORK_SOURCE_DIR) + "/tests/nnue/refiner-zero.frnet", std::ios::binary);
  const std::vector<std::uint8_t> bytes{std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
  CHECK_EQ(bytes.size(), std::size_t{38536});
  auto r = std::make_unique<RefinerFile>();
  std::string error;
  CHECK_MSG(read_refiner_file(bytes, *r, error), error);
  bool zero = true;
  for (const auto& unit : r->entry_weights)
    zero &= std::all_of(std::begin(unit), std::end(unit), [](auto w) { return w == 0; });
  for (const auto& row : r->row_weights)
    zero &= std::all_of(std::begin(row), std::end(row), [](auto w) { return w == 0; });
  for (const auto& unit : r->middle_weights)
    zero &= std::all_of(std::begin(unit), std::end(unit), [](auto w) { return w == 0; });
  for (const auto& unit : r->head_weights)
    zero &= std::all_of(std::begin(unit), std::end(unit), [](auto w) { return w == 0; });
  zero &= std::all_of(std::begin(r->entry_bias), std::end(r->entry_bias), [](auto b) { return b == 0; });
  zero &= std::all_of(std::begin(r->middle_bias), std::end(r->middle_bias), [](auto b) { return b == 0; });
  zero &= r->head_bias[0] == 0 && r->head_bias[1] == 0;
  CHECK(zero);
  CHECK_EQ(r->scale, 89);
  CHECK_EQ(r->cap, 20000);
  CHECK_EQ(r->base_checksum, 0x5861c1a319ca267bULL);
  CHECK(write_refiner_file(*r) == bytes);  // Fork's writer and the Python one agree byte for byte
}
#endif

TEST_CASE("refiner", "danger_summary and refiner_rows against slow square-by-square counts") {
  // The bench and parity positions (tests/nnue/parity.epd).
  auto parity_fens = [] {
    std::vector<std::string> fens;
    std::ifstream in(std::string(FORK_SOURCE_DIR) + "/tests/nnue/parity.epd");
    for (std::string line; std::getline(in, line);) {
      if (!line.empty() && line.back() == '\r') line.pop_back();
      if (!line.empty() && line[0] != '#') fens.push_back(line);
    }
    return fens;
  };

  // Attacker class: pawn 0, knight and bishop 1, rook 2, queen 3, king 4.
  auto attacker_class = [](PieceType t) {
    return t == Pawn ? 0 : t == Knight || t == Bishop ? 1 : t == Rook ? 2 : t == Queen ? 3 : 4;
  };

  // XGR's rule square by square: a non-king piece attacked by an enemy piece of
  // a lower class, or attacked and not defended.
  auto slow_exposed = [&](const Position& pos) {
    Bitboard out = 0;
    for (Square s = 0; s < 64; ++s) {
      const Piece p = pos.piece_at(s);
      if (p == NoPiece || kind_of(p) == King) continue;
      const Color c = side_of(p);
      const Bitboard att = pos.attackers_to(s, pos.pieces());
      const Bitboard enemy = att & pos.pieces(~c), own = att & pos.pieces(c);
      int lowest = 5;
      for (Bitboard b = enemy; b;)
        lowest = std::min(lowest, attacker_class(kind_of(pos.piece_at(pop_lsb(b)))));
      if ((enemy && lowest < attacker_class(kind_of(p))) || (enemy && !own)) out |= bb(s);
    }
    return out;
  };

  // The danger counts square by square (danger_summary.hpp's definitions).
  auto slow_danger = [&](const Position& pos) {
    DangerSummary d;
    const Bitboard occ = pos.pieces();
    const Bitboard exposed = slow_exposed(pos);
    for (const Color x : {White, Black}) {
      const Color them = ~x;
      const Square king = pos.king_square(x);
      for (Square s = 0; s < 64; ++s) {
        const Bitboard att = pos.attackers_to(s, occ);
        const bool in_zone = s == king || (king_attacks(king) & bb(s));
        if (in_zone && (att & pos.pieces(them))) {
          ++d.zone_attacked[x];
          if (!(att & pos.pieces(x) & ~pos.pieces(King))) ++d.zone_weak[x];
        }
        // A safe check: not their own piece's square, not attacked by x, and
        // some knight, bishop, rook or queen of theirs both reaches it and
        // would check from it.
        if ((pos.pieces(them) & bb(s)) || (att & pos.pieces(x))) continue;
        bool check = false;
        for (const PieceType t : {Knight, Bishop, Rook, Queen}) {
          const Bitboard reach = attacks(t, s, occ);
          check |= (reach & pos.pieces(them, t)) && (reach & bb(king));
        }
        d.safe_checks[x] += check;
      }
      // Pinned: x's pieces whose removal lets an enemy slider see x's king.
      for (Bitboard b = pos.pieces(x) & ~pos.pieces(King); b;) {
        const Square s = pop_lsb(b);
        const Bitboard lifted = occ & ~bb(s);
        const Bitboard before = (rook_attacks(king, occ) & pos.pieces(them, Rook, Queen)) |
                                (bishop_attacks(king, occ) & pos.pieces(them, Bishop, Queen));
        const Bitboard after = (rook_attacks(king, lifted) & pos.pieces(them, Rook, Queen)) |
                               (bishop_attacks(king, lifted) & pos.pieces(them, Bishop, Queen));
        d.pinned_count[x] += (after & ~before) != 0;
      }
      d.exposed_count[x] = popcount(exposed & pos.pieces(x));
    }
    return d;
  };
  int positions = 0, with_checks = 0, with_pins = 0;
  for (const std::string& fen : parity_fens()) {
    Position pos;
    CHECK_MSG(pos.set_fen(fen), fen);
    Bitboard exposed = 0;
    const DangerSummary d = danger_summary(pos, exposed);
    const DangerSummary slow = slow_danger(pos);
    CHECK_MSG(exposed == exposed_pieces(pos) && exposed == slow_exposed(pos), fen);
    for (const Color x : {White, Black}) {
      CHECK_MSG(d.zone_attacked[x] == slow.zone_attacked[x], fen << " side " << int(x));
      CHECK_MSG(d.zone_weak[x] == slow.zone_weak[x], fen << " side " << int(x));
      CHECK_MSG(d.safe_checks[x] == slow.safe_checks[x], fen << " side " << int(x));
      CHECK_MSG(d.pinned_count[x] == slow.pinned_count[x], fen << " side " << int(x));
      CHECK_MSG(d.exposed_count[x] == slow.exposed_count[x], fen << " side " << int(x));
      with_checks += slow.safe_checks[x] > 0;
      with_pins += slow.pinned_count[x] > 0;
    }
    ++positions;
  }
  CHECK_EQ(positions, 446);
  CHECK_MSG(with_checks > 20 && with_pins > 20,
            with_checks << " with safe checks, " << with_pins << " with pins");

  // refiner_rows: the exposed pieces from the side to move's view, the
  // danger rows, the context.
  {
    auto net = std::make_unique<NetFile>();
    for (int p = 0; p < 25; ++p) net->phase_table[p] = static_cast<std::uint8_t>(p * NetBuckets / 25);
    // The base evaluation's bins (the plan's §2.2 (v)): [-1,000, 999] in 16
    // bins of 125 cp, values outside clamped to the end bins.
    const int evals[] = {-20000, -1001, -1000, -876, -875, -1, 0, 124, 125, 874, 875, 999, 1000, 20000};
    const int bins[] = {0, 0, 0, 0, 1, 7, 8, 8, 9, 14, 15, 15, 15, 15};
    int index = 0;
    for (const std::string& fen : parity_fens()) {
      Position pos;
      pos.set_fen(fen);
      const int k = index % static_cast<int>(std::size(evals));
      ++index;
      int rows[RefinerMaxActive];
      const int n = refiner_rows(*net, pos, evals[k], rows);
      std::vector<int> got(rows, rows + n), want;
      const Color stm = pos.side_to_move();
      const int flip = NetMirrored && (pos.king_square(stm) & 7) < 4 ? 7 : 0;
      for (Bitboard b = slow_exposed(pos); b;) {
        const Square s = pop_lsb(b);
        const Piece p = pos.piece_at(s);
        want.push_back(320 * (side_of(p) != stm) + 64 * kind_of(p) + ((stm == White ? s : s ^ 56) ^ flip));
      }
      int next = 640;
#if FORK_REFINER_ARCH == 2
      const DangerSummary d = slow_danger(pos);
      for (const Color x : {stm, ~stm}) {
        want.push_back(next + std::min(d.zone_attacked[x], 4));
        want.push_back(next + 5 + std::min(d.zone_weak[x], 2));
        want.push_back(next + 8 + std::min(d.safe_checks[x], 2));
        want.push_back(next + 11 + std::min(d.pinned_count[x], 2));
        want.push_back(next + 14 + std::min(d.exposed_count[x], 3));
        next += 18;
      }
#endif
      want.push_back(next + net->phase_table[game_phase(pos)]);
      want.push_back(next + NetBuckets + bins[k]);
      CHECK_MSG(got.back() == want.back(), fen << " eval " << evals[k]);  // the bin row comes last
      std::sort(got.begin(), got.end());
      std::sort(want.begin(), want.end());
      CHECK_MSG(got == want, fen);
      CHECK(n <= RefinerMaxActive);
    }
    CHECK_EQ(index, 446);
  }
}

#ifdef FORK_REFINER
TEST_CASE("refiner", "the embedded refiner is bound to the embedded base network") {
  std::uint64_t base = 0;
  for (int i = 7; i >= 0; --i) base = base << 8 | embedded_net_bytes[40 + i];
  CHECK_EQ(embedded_refiner().base_checksum, base);
}

// The search's use of the refiner (the plan's §2.1, §2.6, §2.7). The embedded
// refiner's correction head is given a bias for the test (restored after):
// every call then corrects by +S cp. The root of a one-ply zero-window
// search is a main-search site; its TT entry shows the value the node used.
TEST_CASE("refiner",
          "a gated site uses base + correction, stores it refined, and a stored refined value sticks") {
  auto& r = const_cast<RefinerFile&>(embedded_refiner());
  const std::int32_t saved = r.head_bias[0];
  r.head_bias[0] = NetQa * NetQb;  // y = QA x QB: a correction of S cp
  const int correction = std::min(r.scale, r.cap);
  auto table = std::make_unique<TransTable>();
  HashMemory memory;
  std::string report;
  if (!memory.resize(std::size_t{1} << 20, report)) {
    r.head_bias[0] = saved;
    SKIP("no memory for the table: " << report);
  }
  table->bind_memory(memory.data(), memory.bytes());
  auto searcher = std::make_unique<Searcher>(*table);
  // No node-level pruning, so the root always reaches its TT write.
  searcher->switches.use_rfp = searcher->switches.use_nmp = searcher->switches.use_futility = false;
  searcher->switches.use_lmp = searcher->switches.use_see_prune = searcher->switches.use_lmr = false;
  searcher->refiner_gate.margin_main = 25;
  searcher->refiner_gate.margin_quiesce = 25;
  const std::atomic<bool> stop{false};
  Position pos;
  pos.set_fen("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4");
  const int base = static_eval(pos);
  TtHit hit{};

  // Gated (beta 20 above the base): the refined value is used and stored.
  memory.clear(1);
  searcher->clear_history();
  searcher->probe_zero_window(pos, base + 20, 1, stop);
  CHECK(table->fetch(pos.key(), hit));
  CHECK_EQ(hit.eval, base + correction);
  CHECK(hit.refined);
  CHECK(searcher->refiner_tally().main_calls >= 1);
  // A stored refined value is used as it is, whatever the window (the sticky
  // rule): not taken for a base value at a far window, and not refined a
  // second time at a gated one, even with G1. The entry is stored shallow,
  // so it cannot cut the node before its evaluation site.
  searcher->refiner_gate.refine_reused = true;
  for (const int offset : {400, correction + 20}) {
    memory.clear(1);
    table->deposit(pos.key(), NoMove, 0, base + correction, 0, TtBound::Upper, false, true);
    searcher->probe_zero_window(pos, base + offset, 1, stop);
    CHECK_MSG(table->fetch(pos.key(), hit) && hit.eval == base + correction && hit.refined,
              "beta " << offset << " above the base: eval " << hit.eval << (hit.refined ? " refined" : ""));
  }
  searcher->refiner_gate.refine_reused = false;

  // Not gated (beta 400 above): the base value, unrefined.
  memory.clear(1);
  searcher->probe_zero_window(pos, base + 400, 1, stop);
  CHECK(table->fetch(pos.key(), hit) && hit.eval == base && !hit.refined);

  // A stored base value at a gated site: kept as it is under G0, refined
  // (and stored refined) under G1.
  for (const bool reused : {false, true}) {
    memory.clear(1);
    table->deposit(pos.key(), NoMove, 0, base, 0, TtBound::Upper, false, false);
    searcher->refiner_gate.refine_reused = reused;
    searcher->probe_zero_window(pos, base + 20, 1, stop);
    CHECK(table->fetch(pos.key(), hit));
    CHECK_MSG(hit.eval == (reused ? base + correction : base) && hit.refined == reused, "G" << int(reused));
    CHECK_EQ(searcher->refiner_tally().reused_calls > 0, reused);
    CHECK(searcher->refiner_tally().reused_near >= 1);
  }
  r.head_bias[0] = saved;
}

TEST_CASE("refiner", "UCI: the gate's options and the info string refiner line before bestmove") {
  EngineProcess engine{FORK_EXE_PATH};
  CHECK(engine.started());
  constexpr auto patience = std::chrono::milliseconds(20000);
  auto line_at = [&](std::string_view prefix, std::size_t from) -> std::optional<std::size_t> {
    return engine.wait_prefix(prefix, from, patience);
  };
  engine.send("uci");
  const auto margin_main = line_at("option name RefinerMarginMain ", 0);
  const auto margin_quiesce = line_at("option name RefinerMarginQuiesce ", 0);
  const auto reused = line_at("option name RefineReused ", 0);
  CHECK(margin_main && margin_quiesce && reused);
  if (!margin_main || !margin_quiesce || !reused) return;
  const std::vector<OutputLine> options = engine.lines();
  CHECK_EQ(options[*margin_main].text, "option name RefinerMarginMain type spin default " +
                                           std::to_string(FORK_REFINER_MARGIN_MAIN) + " min -1 max 255");
  CHECK_EQ(options[*margin_quiesce].text, "option name RefinerMarginQuiesce type spin default " +
                                              std::to_string(FORK_REFINER_MARGIN_QUIESCE) +
                                              " min -1 max 255");
  CHECK_EQ(options[*reused].text, std::string("option name RefineReused type check default false"));
  CHECK(line_at("uciok", 0).has_value());
  auto calls_after = [&](std::size_t from) -> std::optional<std::string> {
    engine.send("position startpos moves e2e4 e7e5");
    engine.send("go depth 6");
    const auto tally = line_at("info string refiner nodes ", from);
    const auto best = line_at("bestmove ", from);
    if (!tally || !best || *tally > *best) return std::nullopt;
    const std::vector<OutputLine> seen = engine.lines();
    CHECK(seen[*best - 1].text.starts_with("info depth"));  // the score line stays last
    return seen[*tally].text;
  };
  const std::optional<std::string> on = calls_after(engine.line_count());
  CHECK(on.has_value());
  if (on) CHECK_MSG(on->find(" main_calls 0 ") == std::string::npos, *on);  // the gate fired
  engine.send("setoption name RefinerMarginMain value -1");
  engine.send("setoption name RefinerMarginQuiesce value -1");
  const std::optional<std::string> off = calls_after(engine.line_count());
  CHECK(off.has_value());
  if (off)
    CHECK_MSG(off->find(" main_calls 0 ") != std::string::npos &&
                  off->find(" quiesce_calls 0 ") != std::string::npos,
              *off);
  engine.send("quit");
  CHECK(engine.wait_exit(patience).value_or(-1) == 0);
}
#endif

}  // namespace forkeng::test
