// SPDX-License-Identifier: GPL-3.0-or-later

// gated: the bake-off candidate XGR-512's inference (EXPERIMENT BRANCH; KB
// phase4-designs/design-novelty.md §1, §2.2-2.3, §5.1; judgement.md:
// XGR-512 enters with the exposure plane X and the phase gate G, without the
// revision head). Inference only: no training program yet, and its
// constants await the owner's decision.
//
// Purpose: per perspective, 512 hidden lanes plus 8 side lanes (lane 0 the
// gate, lanes 1-2 the experts' linear lanes, 3-7 reserved and zero) over
// 768 mirrored piece-square inputs per king region (XGR's hand map: e1;
// f1-h1; e2-h2; ranks 3-8, on the mirrored own-king square), plus the
// exposure plane: one input per non-king piece that an enemy piece of a
// strictly lower value class attacks, or that is attacked and undefended,
// summed from scratch at each evaluation. Two SCReLU experts blended by the
// gate.
// Invariants (design §5.1):
// - |hidden or side lane| <= 63 * 505 < 32,767 (validate()); wrapping adds.
// - Experts: v = clamp(y, 0, 255), int16(v * w) * v with |w| <= 127, 32-bit
//   lanes (at most 256 terms per lane), 64-bit sums; S_k = trunc(sum / 255);
//   o_k = S_k + c_k + 128 * (lane_k,stm - lane_k,ntm).
// - Gate: g = clamp(gate_stm + gate_ntm, 0, 255); out = trunc((o_B * 255 +
//   g * (o_A - o_B)) / 255); eval = trunc(out * S / 16,320), clamped inside
//   +-EvalLimit. All in 64 bits.
// - Exposure classes: pawn 1 < knight = bishop 2 < rook 3 < queen 4; a king
//   attacks as class 5 (never "lower"), and attacks and defends like any
//   piece (Fork's reading of the rule's gap; tools/nnue/exposure_pretest.py).
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

// XGR's hand-drawn regions (design-novelty.md §2.1), on the mirrored cells.
struct XgrRegionPieceSquare {
  static constexpr int Regions = 4;
  static constexpr int Size = 768 * Regions;
  static constexpr int region(Color perspective, Square king) {
    const Square seen = perspective == White ? king : king ^ 56;
    const int file = seen & 7, rank = seen >> 3;
    const int f = file < 4 ? 7 - file : file;  // mirrored to e-h
    if (rank == 0) return f == 4 ? 0 : 1;
    return rank == 1 ? 2 : 3;
  }
  static constexpr int index(Color perspective, Piece piece, Square sq, Square own_king) {
    return 768 * region(perspective, own_king) + MirroredPieceSquare::index(perspective, piece, sq, own_king);
  }
  static constexpr bool needs_refresh(Color perspective, Square king_before, Square king_after) {
    return MirroredPieceSquare::needs_refresh(perspective, king_before, king_after) ||
           region(perspective, king_before) != region(perspective, king_after);
  }
};

struct GatedNet {
  using Features = XgrRegionPieceSquare;
  static constexpr int Inputs = Features::Size;
  static constexpr int Exposure = 640;  // own/enemy x 5 non-king types x 64 squares
  static constexpr int Hidden = 512;
  static constexpr int Side = 8;
  using Kernel = SingleLayerNet<Features, Hidden, PhaseBuckets>;  // its accumulator update

  alignas(64) std::int16_t ft_weights[Inputs * Hidden];
  alignas(64) std::int16_t ft_side[Inputs * Side];
  alignas(64) std::int16_t x_weights[Exposure * Hidden];
  alignas(64) std::int16_t x_side[Exposure * Side];
  alignas(64) std::int16_t ft_bias[Hidden];
  std::int16_t side_bias[Side];
  alignas(64) std::int16_t expert_w[2][2 * Hidden];  // A, then B; side to move's half first
  std::int32_t expert_b[2];
  std::int32_t scale = 0;

  struct alignas(64) Acc {
    std::int16_t values[2][Hidden];
    std::int16_t side[2][Side];
  };

  static constexpr int value_class(PieceType t) {
    return t == Pawn ? 1 : t <= Bishop ? 2 : t == Rook ? 3 : t == Queen ? 4 : 5;
  }

  static int exposure_index(Color perspective, Piece piece, Square sq, Square own_king) {
    Square seen = perspective == White ? sq : sq ^ 56;
    if (MirroredPieceSquare::mirrored(perspective, own_king)) seen ^= 7;
    return 320 * (side_of(piece) != perspective) + 64 * kind_of(piece) + seen;
  }

  // Bit set of the exposed non-king pieces' squares.
  static Bitboard exposed(const Position& pos) {
    Bitboard out = 0;
    const Bitboard occ = pos.pieces();
    for (Bitboard b = occ & ~pos.pieces(King); b;) {
      const Square s = pop_lsb(b);
      const Piece p = pos.piece_at(s);
      const Color own = side_of(p);
      const Bitboard attackers = pos.attackers_to(s, occ);
      const Bitboard enemy = attackers & pos.pieces(~own);
      if (!enemy) continue;
      bool lower = false;
      for (Bitboard e = enemy; e && !lower;)
        lower = value_class(kind_of(pos.piece_at(pop_lsb(e)))) < value_class(kind_of(p));
      if (lower || !(attackers & pos.pieces(own))) out |= bb(s);
    }
    return out;
  }

  bool validate(std::string& error) const {
    auto lane_ok = [&](auto base, auto xrow, int width, int lane, int bias) {
      int bmax = 0, xmax = 0;
      for (int f = 0; f < Inputs; ++f) bmax = std::max(bmax, std::abs(int{base[f * width + lane]}));
      for (int f = 0; f < Exposure; ++f) xmax = std::max(xmax, std::abs(int{xrow[f * width + lane]}));
      return std::abs(bias) + 32 * bmax + 30 * xmax <= std::numeric_limits<std::int16_t>::max();
    };
    for (int j = 0; j < Hidden; ++j)
      if (!lane_ok(ft_weights, x_weights, Hidden, j, ft_bias[j]))
        return error = "a hidden lane can leave int16", false;
    for (int j = 0; j < Side; ++j)
      if (!lane_ok(ft_side, x_side, Side, j, side_bias[j]))
        return error = "a side lane can leave int16", false;
    for (const auto& e : expert_w)
      for (const std::int16_t w : e)
        if (std::abs(int{w}) > 127) return error = "an expert weight beyond +-127", false;
    if (scale < 1 || scale > 100000) return error = "scale out of range", false;
    return true;
  }

  void refresh(const Position& pos, Color p, Acc& acc) const {
    std::copy(ft_bias, ft_bias + Hidden, acc.values[p]);
    std::copy(side_bias, side_bias + Side, acc.side[p]);
    const Square king = pos.king_square(p);
    for (Bitboard b = pos.pieces(); b;) {
      const Square s = pop_lsb(b);
      const int f = Features::index(p, pos.piece_at(s), s, king);
      for (int i = 0; i < Hidden; ++i)
        acc.values[p][i] = static_cast<std::int16_t>(acc.values[p][i] + ft_weights[f * Hidden + i]);
      for (int i = 0; i < Side; ++i)
        acc.side[p][i] = static_cast<std::int16_t>(acc.side[p][i] + ft_side[f * Side + i]);
    }
  }

  void refresh(const Position& pos, Acc& acc) const {
    refresh(pos, White, acc);
    refresh(pos, Black, acc);
  }

  // As SingleLayerNet::advance, with the side lanes carried along.
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
      int side[Side];
      for (int i = 0; i < Side; ++i) side[i] = from.side[p][i];
      for (int k = 0; k < c.nr; ++k) {
        const int f = Features::index(p, c.removed[k].piece, c.removed[k].square, king_before);
        sub[k] = ft_weights + f * Hidden;
        for (int i = 0; i < Side; ++i) side[i] -= ft_side[f * Side + i];
      }
      for (int k = 0; k < c.na; ++k) {
        const int f = Features::index(p, c.added[k].piece, c.added[k].square, king_after);
        add[k] = ft_weights + f * Hidden;
        for (int i = 0; i < Side; ++i) side[i] += ft_side[f * Side + i];
      }
      Kernel::update(from.values[p], to.values[p], sub, c.nr, add, c.na);
      for (int i = 0; i < Side; ++i) to.side[p][i] = static_cast<std::int16_t>(side[i]);
    }
  }

  template <bool Simd>
  int output_impl(const Acc& acc, const Position& pos) const {
    // The pre-activations with the exposure plane added (stateless).
    alignas(64) std::int16_t y[2][Hidden];
    std::int32_t side[2][Side];
    const Bitboard exp = exposed(pos);
    const Color stm = pos.side_to_move();
    for (int half = 0; half < 2; ++half) {
      const Color p = half == 0 ? stm : ~stm;
      std::copy(acc.values[p], acc.values[p] + Hidden, y[half]);
      for (int i = 0; i < Side; ++i) side[half][i] = acc.side[p][i];
      const Square king = pos.king_square(p);
      for (Bitboard b = exp; b;) {
        const Square s = pop_lsb(b);
        const int f = exposure_index(p, pos.piece_at(s), s, king);
        for (int i = 0; i < Hidden; ++i)
          y[half][i] = static_cast<std::int16_t>(y[half][i] + x_weights[f * Hidden + i]);
        for (int i = 0; i < Side; ++i) side[half][i] += x_side[f * Side + i];
      }
    }
    std::int64_t o[2];
    for (int k = 0; k < 2; ++k) {
      std::int64_t sum = 0;
#if defined(__AVX2__)
      if constexpr (Simd) {
        const __m256i zero = _mm256_setzero_si256(), qa = _mm256_set1_epi16(255);
        __m256i lanes = _mm256_setzero_si256();
        for (int half = 0; half < 2; ++half)
          for (int i = 0; i < Hidden; i += 16) {
            const __m256i v = _mm256_min_epi16(
                _mm256_max_epi16(_mm256_load_si256(reinterpret_cast<const __m256i*>(y[half] + i)), zero), qa);
            const __m256i vw = _mm256_mullo_epi16(
                v, _mm256_load_si256(reinterpret_cast<const __m256i*>(expert_w[k] + half * Hidden + i)));
            lanes = _mm256_add_epi32(lanes, _mm256_madd_epi16(vw, v));
          }
        alignas(32) std::int32_t parts[8];
        _mm256_store_si256(reinterpret_cast<__m256i*>(parts), lanes);
        for (const std::int32_t t : parts) sum += t;
      } else
#endif
      {
        for (int half = 0; half < 2; ++half)
          for (int i = 0; i < Hidden; ++i) {
            const int v = std::clamp<int>(y[half][i], 0, 255);
            sum += std::int64_t{static_cast<std::int16_t>(v * expert_w[k][half * Hidden + i])} * v;
          }
      }
      o[k] = sum / 255 + expert_b[k] + 128 * (std::int64_t{side[0][1 + k]} - side[1][1 + k]);
    }
    const std::int64_t g = std::clamp<std::int64_t>(std::int64_t{side[0][0]} + side[1][0], 0, 255);
    const std::int64_t out = (o[1] * 255 + g * (o[0] - o[1])) / 255;
    const std::int64_t cp = out * scale / 16320;
    return static_cast<int>(std::clamp<std::int64_t>(cp, -(EvalLimit - 1), EvalLimit - 1));
  }

  int output(const Acc& acc, const Position& pos) const { return output_impl<true>(acc, pos); }
  int output_scalar(const Acc& acc, const Position& pos) const { return output_impl<false>(acc, pos); }
};

}  // namespace forkeng
