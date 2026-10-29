// SPDX-License-Identifier: GPL-3.0-or-later

// single_layer: the shared kernel framework for the bake-off's single-layer
// candidates (DESIGN.md §5 multi-agent plan, step 4; KB phase4-designs/
// judgement.md: S-512 and the hybrid H-512). EXPERIMENT BRANCH: inference
// only, no training yet, and the candidates' constants (bucket counts,
// tables) await the owner's decision on their screen.
//
// Purpose: one accumulator of Hidden int16 values per perspective over a
// feature set (a policy type: its size, its index, and when a king move
// forces a refresh), squared clipped ReLU, and one output layer per
// bucket (a policy type choosing the bucket from the position).
// Invariants:
// - SCReLU in integers: a = clamp(x, 0, QA); each term is (a * w) in 16
//   bits (|w| <= 128, checked by validate(), so |a * w| <= 32,640), times
//   a, summed in 32 bits per SIMD lane (at most 2 * Hidden / 8 terms per
//   lane on AVX2, each below 2^23.0, so below 2^31 for Hidden <= 1,024) and
//   in 64 bits overall. The output is trunc(sum / QA) + bias, times S,
//   divided by QA * QB, truncated, clamped inside +-EvalLimit.
// - Every SIMD path equals the scalar reference bit for bit (no overflow
//   is possible within validate()'s bounds).
// - An incrementally updated accumulator equals a refresh; a king move
//   that changes a perspective's feature mapping refreshes that
//   perspective.
#pragma once

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <string>

#if defined(__AVX2__)
#include <immintrin.h>
#endif

#include "core/material.hpp"
#include "core/position.hpp"
#include "eval/eval_scale.hpp"

namespace forkeng {

constexpr int SlQa = 255;
constexpr int SlQb = 64;

template <class Features, int Hidden, class Buckets>
struct SingleLayerNet {
  static constexpr int Inputs = Features::Size;
  static constexpr int OutBuckets = Buckets::Count;
  static constexpr int HiddenSize = Hidden;
  static_assert(Hidden % 32 == 0, "Hidden must fill whole AVX-512 vectors");

  alignas(64) std::int16_t ft_weights[Inputs * Hidden];
  alignas(64) std::int16_t ft_bias[Hidden];
  alignas(64) std::int16_t out_weights[OutBuckets][2 * Hidden];
  std::int32_t out_bias[OutBuckets];
  std::int32_t scale = 0;

  struct alignas(64) Acc {
    std::int16_t values[2][Hidden];
  };

  // The bounds every kernel relies on; false names the first one broken.
  bool validate(std::string& error) const {
    for (int j = 0; j < Hidden; ++j) {
      int largest = 0;
      for (int f = 0; f < Inputs; ++f) largest = std::max(largest, std::abs(int{ft_weights[f * Hidden + j]}));
      if (std::abs(int{ft_bias[j]}) + 32 * largest > std::numeric_limits<std::int16_t>::max())
        return error = "a hidden unit can leave int16", false;
    }
    for (int b = 0; b < OutBuckets; ++b)
      for (int i = 0; i < 2 * Hidden; ++i)
        if (std::abs(int{out_weights[b][i]}) > 128) return error = "an output weight beyond +-128", false;
    if (scale < 1 || scale > 100000) return error = "scale out of range", false;
    return true;
  }

  void refresh(const Position& pos, Color perspective, Acc& acc) const {
    std::int16_t* v = acc.values[perspective];
    std::memcpy(v, ft_bias, sizeof ft_bias);
    const Square king = pos.king_square(perspective);
    for (Bitboard b = pos.pieces(); b;) {
      const Square s = pop_lsb(b);
      const std::int16_t* w = ft_weights + Features::index(perspective, pos.piece_at(s), s, king) * Hidden;
      for (int i = 0; i < Hidden; ++i) v[i] = static_cast<std::int16_t>(v[i] + w[i]);
    }
  }

  void refresh(const Position& pos, Acc& acc) const {
    refresh(pos, White, acc);
    refresh(pos, Black, acc);
  }

  // The parent's accumulator advanced by a move of `before` (not yet made;
  // `after` is the position after it). A perspective whose king mapping
  // changes is refreshed from `after`.
  void advance(const Position& before, const Position& after, Move m, const Acc& from, Acc& to) const {
    struct Change {
      Piece piece;
      Square square;
    };
    Change removed[2], added[2];
    int nr = 0, na = 0;
    const Color us = before.side_to_move();
    const Piece mover = before.piece_at(m.from());
    if (m.is_castle()) {
      const auto landing = Position::castle_landing(m.from(), m.to());
      removed[nr++] = {mover, m.from()};
      removed[nr++] = {before.piece_at(m.to()), m.to()};
      added[na++] = {mover, landing.king};
      added[na++] = {piece_of(us, Rook), landing.rook};
    } else {
      removed[nr++] = {mover, m.from()};
      if (m.is_capture()) {
        const Square cs = before.capture_square(m);
        removed[nr++] = {before.piece_at(cs), cs};
      }
      added[na++] = {m.is_promotion() ? piece_of(us, m.promo_type()) : mover, m.to()};
    }
    for (const Color p : {White, Black}) {
      const Square king_before = before.king_square(p), king_after = after.king_square(p);
      if (Features::needs_refresh(p, king_before, king_after)) {
        refresh(after, p, to);
        continue;
      }
      const std::int16_t* sub[2];
      const std::int16_t* add[2];
      for (int k = 0; k < nr; ++k)
        sub[k] = ft_weights + Features::index(p, removed[k].piece, removed[k].square, king_before) * Hidden;
      for (int k = 0; k < na; ++k)
        add[k] = ft_weights + Features::index(p, added[k].piece, added[k].square, king_after) * Hidden;
      update(from.values[p], to.values[p], sub, nr, add, na);
    }
  }

  static void update_scalar(const std::int16_t* src, std::int16_t* dst, const std::int16_t* const* sub,
                            int nr, const std::int16_t* const* add, int na) {
    for (int i = 0; i < Hidden; ++i) {
      int x = src[i];
      for (int k = 0; k < nr; ++k) x -= sub[k][i];
      for (int k = 0; k < na; ++k) x += add[k][i];
      dst[i] = static_cast<std::int16_t>(x);
    }
  }

  static void update(const std::int16_t* src, std::int16_t* dst, const std::int16_t* const* sub, int nr,
                     const std::int16_t* const* add, int na) {
#if defined(__AVX2__)
    for (int i = 0; i < Hidden; i += 16) {
      __m256i x = _mm256_load_si256(reinterpret_cast<const __m256i*>(src + i));
      for (int k = 0; k < nr; ++k)
        x = _mm256_sub_epi16(x, _mm256_load_si256(reinterpret_cast<const __m256i*>(sub[k] + i)));
      for (int k = 0; k < na; ++k)
        x = _mm256_add_epi16(x, _mm256_load_si256(reinterpret_cast<const __m256i*>(add[k] + i)));
      _mm256_store_si256(reinterpret_cast<__m256i*>(dst + i), x);
    }
#else
    update_scalar(src, dst, sub, nr, add, na);
#endif
  }

  int finish(std::int64_t sum, int bucket) const {
    const std::int64_t out = sum / SlQa + out_bias[bucket];
    const std::int64_t cp = out * scale / (SlQa * SlQb);
    return static_cast<int>(std::clamp<std::int64_t>(cp, -(EvalLimit - 1), EvalLimit - 1));
  }

  int output_scalar(const Acc& acc, const Position& pos) const {
    const int bucket = Buckets::index(pos);
    const Color stm = pos.side_to_move();
    std::int64_t sum = 0;
    for (int half = 0; half < 2; ++half) {
      const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
      const std::int16_t* w = out_weights[bucket] + half * Hidden;
      for (int i = 0; i < Hidden; ++i) {
        const int a = std::clamp<int>(v[i], 0, SlQa);
        sum += static_cast<std::int64_t>(static_cast<std::int16_t>(a * w[i])) * a;
      }
    }
    return finish(sum, bucket);
  }

  int output(const Acc& acc, const Position& pos) const {
#if defined(__AVX2__)
    const int bucket = Buckets::index(pos);
    const Color stm = pos.side_to_move();
    const __m256i zero = _mm256_setzero_si256(), qa = _mm256_set1_epi16(SlQa);
    __m256i lanes = _mm256_setzero_si256();
    for (int half = 0; half < 2; ++half) {
      const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
      const std::int16_t* w = out_weights[bucket] + half * Hidden;
      for (int i = 0; i < Hidden; i += 16) {
        const __m256i x = _mm256_load_si256(reinterpret_cast<const __m256i*>(v + i));
        const __m256i a = _mm256_min_epi16(_mm256_max_epi16(x, zero), qa);
        const __m256i aw = _mm256_mullo_epi16(a, _mm256_load_si256(reinterpret_cast<const __m256i*>(w + i)));
        lanes = _mm256_add_epi32(lanes, _mm256_madd_epi16(aw, a));
      }
    }
    alignas(32) std::int32_t parts[8];
    _mm256_store_si256(reinterpret_cast<__m256i*>(parts), lanes);
    std::int64_t sum = 0;
    for (const std::int32_t p : parts) sum += p;
    return finish(sum, bucket);
#else
    return output_scalar(acc, pos);
#endif
  }
};

// S-512's feature set (KB phase4-designs/design-speed.md): 768 piece-square
// inputs per perspective, ranks flipped for Black, and files mirrored when
// the perspective's own king stands on files a-d, so that king is always on
// e-h.
struct MirroredPieceSquare {
  static constexpr int Size = 768;
  static constexpr bool mirrored(Color perspective, Square king) {
    const Square seen = perspective == White ? king : king ^ 56;
    return (seen & 7) < 4;
  }
  static constexpr int index(Color perspective, Piece piece, Square sq, Square own_king) {
    Square seen = perspective == White ? sq : sq ^ 56;
    if (mirrored(perspective, own_king)) seen ^= 7;
    return 384 * (side_of(piece) != perspective) + 64 * kind_of(piece) + seen;
  }
  static constexpr bool needs_refresh(Color perspective, Square king_before, Square king_after) {
    return mirrored(perspective, king_before) != mirrored(perspective, king_after);
  }
};

// S-512's output buckets: by the total number of pieces (kings included)
// through a table, 4 counts per bucket to start (design-speed.md §1).
// CANDIDATE CONSTANT, flagged by the judge's screen note (8 buckets).
struct PieceCountBuckets {
  static constexpr int Count = 8;
  static int index(const Position& pos) {
    const int n = popcount(pos.pieces());
    return std::min(Count - 1, (n - 1) / 4);
  }
};

// The hybrid H-512's feature set (KB phase4-designs/judgement.md: AF's
// fitted king regions on S's kernel): 768 mirrored piece-square inputs per
// king region. The region of the perspective's own king comes from its
// mirrored square (32 cells: cell = 4 * rank + file - 4, files e-h, rank 0 the
// perspective's own first rank) through a map fitted to Fork's data
// (tools/nnue/fit_regions.py on the generation-0 snapshot g0s1, 400,030
// positions, theta 10%, at most 4 regions; shares 24.7%, 24.2%, 34.4%,
// 16.7%). CANDIDATE CONSTANTS: the map is data-fitted; "at most 4 regions"
// is flagged by the judge's screen note.
struct RegionMirroredPieceSquare {
  static constexpr int Regions = 4;
  static constexpr int Size = 768 * Regions;
  static constexpr std::uint8_t RegionOfCell[32] = {0, 2, 1, 1, 2, 2, 1, 1, 2, 2, 3, 3, 3, 3, 3, 3,
                                                    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3};
  static constexpr int region(Color perspective, Square king) {
    const Square seen = perspective == White ? king : king ^ 56;
    const int file = seen & 7, rank = seen >> 3;
    return RegionOfCell[4 * rank + (file < 4 ? 7 - file : file) - 4];
  }
  static constexpr int index(Color perspective, Piece piece, Square sq, Square own_king) {
    return 768 * region(perspective, own_king) + MirroredPieceSquare::index(perspective, piece, sq, own_king);
  }
  static constexpr bool needs_refresh(Color perspective, Square king_before, Square king_after) {
    return MirroredPieceSquare::needs_refresh(perspective, king_before, king_after) ||
           region(perspective, king_before) != region(perspective, king_after);
  }
};

// H-512's output buckets: game_phase (0-24, core/material.hpp) through a
// table cut at the octiles of Fork's own phase histogram (fit_regions.py,
// the same 400,030 positions). CANDIDATE CONSTANTS (8 buckets, flagged).
struct PhaseBuckets {
  static constexpr int Count = 8;
  static constexpr std::uint8_t BucketOfPhase[25] = {0, 0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 3, 4,
                                                     4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 7, 7};
  static int index(const Position& pos) { return BucketOfPhase[game_phase(pos)]; }
};

}  // namespace forkeng
