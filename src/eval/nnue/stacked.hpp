// SPDX-License-Identifier: GPL-3.0-or-later

// stacked: the bake-off candidate AF-S's inference (EXPERIMENT BRANCH; KB
// phase4-designs/design-accuracy.md §5, judgement.md: AF-S shares H-512's
// fitted region map). Inference only: no training program yet, and its
// constants await the owner's decision on their screen.
//
// Purpose: a 512-wide int16 accumulator per perspective over
// RegionMirroredPieceSquare, the pairwise product of each accumulator's two
// halves, then three small layers duplicated per game-phase stack (8):
// 512 -> 16 (int8 weights), 16 -> 32 and 32 -> 1 (int16 weights), squared
// clipped activations between them.
// Invariants (the design's §5, all integer, exact on every path):
// - v = clamp(acc, 0, 255); a[j] = (v[j] * v[j + 256] + 256) >> 9 in
//   [0, 127] for j < 256, side to move's half first: 512 inputs to L1.
// - y1 = b1 + sum x * W1 with |W1| <= 127: the AVX2 byte multiply-add
//   pairs stay <= 2 * 127 * 127 = 32,258, so they never saturate.
// - c1 = clamp(y1 >> 2, 0, 2032), q1 = (c1 * c1) >> 11; y2 = b2 + sum q1 * W2;
//   c2 = clamp(y2 >> 13, 0, 2016), q2 = (c2 * c2) >> 11; y3 = b3 + sum q2 * W3;
//   eval = (y3 * M) >> 32 in 64 bits, clamped inside +-EvalLimit.
// - validate() enforces the bounds that keep every sum inside int32.
#pragma once

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <string>

#if defined(__AVX2__)
#include <immintrin.h>
#endif

#include "eval/nnue/single_layer.hpp"

namespace forkeng {

struct StackedNet {
  using Features = RegionMirroredPieceSquare;
  using Stacks = PhaseBuckets;
  static constexpr int Inputs = Features::Size;
  static constexpr int Hidden = 512;
  static constexpr int L1In = Hidden;  // two halves of Hidden / 2 pairwise products
  static constexpr int L1Out = 16, L2Out = 32;
  static constexpr int StackCount = Stacks::Count;

  alignas(64) std::int16_t ft_weights[Inputs * Hidden];
  alignas(64) std::int16_t ft_bias[Hidden];
  alignas(64) std::int8_t l1_w[StackCount][L1Out][L1In];
  std::int32_t l1_b[StackCount][L1Out];
  alignas(64) std::int16_t l2_w[StackCount][L2Out][L1Out];
  std::int32_t l2_b[StackCount][L2Out];
  alignas(64) std::int16_t l3_w[StackCount][L2Out];
  std::int32_t l3_b[StackCount];
  std::int64_t out_multiplier = 0;  // M: eval = (y3 * M) >> 32

  using Kernel = SingleLayerNet<Features, Hidden, Stacks>;  // its accumulator and update
  using Acc = Kernel::Acc;

  bool validate(std::string& error) const {
    for (int j = 0; j < Hidden; ++j) {
      int largest = 0;
      for (int f = 0; f < Inputs; ++f) largest = std::max(largest, std::abs(int{ft_weights[f * Hidden + j]}));
      if (std::abs(int{ft_bias[j]}) + 32 * largest > std::numeric_limits<std::int16_t>::max())
        return error = "a hidden unit can leave int16", false;
    }
    for (int k = 0; k < StackCount; ++k) {
      for (int o = 0; o < L1Out; ++o) {
        for (int i = 0; i < L1In; ++i)
          if (l1_w[k][o][i] == -128) return error = "an L1 weight of -128", false;
        if (std::abs(std::int64_t{l1_b[k][o]}) > (std::int64_t{1} << 30))
          return error = "an L1 bias beyond 2^30", false;
      }
      for (int o = 0; o < L2Out; ++o) {
        std::int64_t worst = std::abs(std::int64_t{l2_b[k][o]});
        for (int i = 0; i < L1Out; ++i) worst += 2016 * std::abs(std::int64_t{l2_w[k][o][i]});
        if (worst >= (std::int64_t{1} << 31)) return error = "an L2 sum can leave int32", false;
      }
      std::int64_t worst = std::abs(std::int64_t{l3_b[k]});
      for (int i = 0; i < L2Out; ++i) worst += 1984 * std::abs(std::int64_t{l3_w[k][i]});
      if (worst >= (std::int64_t{1} << 31)) return error = "the L3 sum can leave int32", false;
    }
    if (out_multiplier <= 0 || out_multiplier >= (std::int64_t{1} << 31))
      return error = "bad output multiplier", false;
    return true;
  }

  void refresh(const Position& pos, Color p, Acc& acc) const {
    std::int16_t* v = acc.values[p];
    std::copy(ft_bias, ft_bias + Hidden, v);
    const Square king = pos.king_square(p);
    for (Bitboard b = pos.pieces(); b;) {
      const Square s = pop_lsb(b);
      const std::int16_t* w = ft_weights + Features::index(p, pos.piece_at(s), s, king) * Hidden;
      for (int i = 0; i < Hidden; ++i) v[i] = static_cast<std::int16_t>(v[i] + w[i]);
    }
  }

  void refresh(const Position& pos, Acc& acc) const {
    refresh(pos, White, acc);
    refresh(pos, Black, acc);
  }

  // As SingleLayerNet::advance.
  void advance(const Position& before, const Position& after, Move m, const Acc& from, Acc& to) const {
    const MoveChanges c = move_changes(before, m);
    for (const Color p : {White, Black}) {
      const Square king_before = before.king_square(p), king_after = after.king_square(p);
      if (Features::needs_refresh(p, king_before, king_after)) {
        refresh(after, p, to);
        continue;
      }
      const std::int16_t* sub[2];
      const std::int16_t* add[2];
      for (int k = 0; k < c.nr; ++k)
        sub[k] = ft_weights + Features::index(p, c.removed[k].piece, c.removed[k].square, king_before) * Hidden;
      for (int k = 0; k < c.na; ++k)
        add[k] = ft_weights + Features::index(p, c.added[k].piece, c.added[k].square, king_after) * Hidden;
      Kernel::update(from.values[p], to.values[p], sub, c.nr, add, c.na);
    }
  }

  // The pairwise products of both perspectives, side to move first.
  static void pairwise_scalar(const Acc& acc, Color stm, std::uint8_t out[L1In]) {
    for (int half = 0; half < 2; ++half) {
      const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
      for (int j = 0; j < Hidden / 2; ++j) {
        const int a = std::clamp<int>(v[j], 0, 255), b = std::clamp<int>(v[j + Hidden / 2], 0, 255);
        out[half * (Hidden / 2) + j] = static_cast<std::uint8_t>((a * b + 256) >> 9);
      }
    }
  }

  static void pairwise(const Acc& acc, Color stm, std::uint8_t out[L1In]) {
#if defined(__AVX2__)
    const __m256i zero = _mm256_setzero_si256(), top = _mm256_set1_epi16(255);
    for (int half = 0; half < 2; ++half) {
      const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
      for (int j = 0; j < Hidden / 2; j += 32) {
        __m256i r[2];
        for (int t = 0; t < 2; ++t) {
          const __m256i a = _mm256_min_epi16(
              _mm256_max_epi16(_mm256_load_si256(reinterpret_cast<const __m256i*>(v + j + 16 * t)), zero),
              top);
          const __m256i b = _mm256_min_epi16(
              _mm256_max_epi16(
                  _mm256_load_si256(reinterpret_cast<const __m256i*>(v + Hidden / 2 + j + 16 * t)), zero),
              top);
          // ((64 a) * b + 2^14) >> 15 = (a b + 256) >> 9, exactly (design §5.3).
          r[t] = _mm256_mulhrs_epi16(_mm256_slli_epi16(a, 6), b);
        }
        // Pack 2 x 16 int16 (each 0..127) into 32 uint8, fixing the lane order.
        const __m256i packed = _mm256_permute4x64_epi64(_mm256_packus_epi16(r[0], r[1]), 0xD8);
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(out + half * (Hidden / 2) + j), packed);
      }
    }
#else
    pairwise_scalar(acc, stm, out);
#endif
  }

  static int l1_dot_scalar(const std::uint8_t* x, const std::int8_t* w) {
    int sum = 0;
    for (int i = 0; i < L1In; ++i) sum += int{x[i]} * int{w[i]};
    return sum;
  }

  static int l1_dot(const std::uint8_t* x, const std::int8_t* w) {
#if defined(__AVX2__)
    const __m256i ones = _mm256_set1_epi16(1);
    __m256i sum = _mm256_setzero_si256();
    for (int i = 0; i < L1In; i += 32) {
      const __m256i p = _mm256_maddubs_epi16(_mm256_loadu_si256(reinterpret_cast<const __m256i*>(x + i)),
                                             _mm256_loadu_si256(reinterpret_cast<const __m256i*>(w + i)));
      sum = _mm256_add_epi32(sum, _mm256_madd_epi16(p, ones));
    }
    const __m128i s = _mm_add_epi32(_mm256_castsi256_si128(sum), _mm256_extracti128_si256(sum, 1));
    const __m128i s2 = _mm_add_epi32(s, _mm_shuffle_epi32(s, 0x4E));
    return _mm_cvtsi128_si32(_mm_add_epi32(s2, _mm_shuffle_epi32(s2, 0xB1)));
#else
    return l1_dot_scalar(x, w);
#endif
  }

  static int square_clip(std::int32_t y, int shift, int top) {
    const int c = std::clamp(y >> shift, 0, top);
    return (c * c) >> 11;
  }

  template <bool Simd>
  int output_impl(const Acc& acc, const Position& pos) const {
    const int k = Stacks::index(pos);
    alignas(32) std::uint8_t x[L1In];
    if constexpr (Simd)
      pairwise(acc, pos.side_to_move(), x);
    else
      pairwise_scalar(acc, pos.side_to_move(), x);
    int q1[L1Out];
    for (int o = 0; o < L1Out; ++o) {
      const int dot = Simd ? l1_dot(x, l1_w[k][o]) : l1_dot_scalar(x, l1_w[k][o]);
      q1[o] = square_clip(l1_b[k][o] + dot, 2, 2032);
    }
    int q2[L2Out];
    for (int o = 0; o < L2Out; ++o) {
      std::int32_t y = l2_b[k][o];
      for (int i = 0; i < L1Out; ++i) y += q1[i] * l2_w[k][o][i];
      q2[o] = square_clip(y, 13, 2016);
    }
    std::int32_t y3 = l3_b[k];
    for (int i = 0; i < L2Out; ++i) y3 += q2[i] * l3_w[k][i];
    const std::int64_t cp = (std::int64_t{y3} * out_multiplier) >> 32;
    return static_cast<int>(std::clamp<std::int64_t>(cp, -(EvalLimit - 1), EvalLimit - 1));
  }

  int output(const Acc& acc, const Position& pos) const { return output_impl<true>(acc, pos); }
  int output_scalar(const Acc& acc, const Position& pos) const { return output_impl<false>(acc, pos); }
};

}  // namespace forkeng
