// SPDX-License-Identifier: GPL-3.0-or-later

#include "eval/nnue/refiner.hpp"

#include <algorithm>
#include <cstdint>

#if defined(__AVX2__)
#include <immintrin.h>
#endif

#include "core/material.hpp"
#if FORK_REFINER_ARCH == 2
#include "eval/nnue/danger_summary.hpp"
#endif

namespace forkeng {

static_assert(RefinerInputBytes % 32 == 0, "the AVX2 entry layer's blocking");

// The entry layer's sums (units of QA x QB): the bias, the dense part over
// the input bytes, the active rows. Integer sums of the same terms, so every
// path gives the same values.
void refiner_l1_scalar(const RefinerFile& r, const RefinerInputs& in, std::int32_t* sums) {
  for (int o = 0; o < RefinerL1Width; ++o) {
    std::int32_t s = r.entry_bias[o];
    for (int i = 0; i < RefinerInputBytes; ++i) s += in.bytes[i] * r.entry_weights[o][i];
    sums[o] = s;
  }
  for (int k = 0; k < in.row_count; ++k) {
    const std::int32_t* row = r.row_weights[in.rows[k]];
    for (int o = 0; o < RefinerL1Width; ++o) sums[o] += row[o];
  }
}

#if defined(__AVX2__)
// Each unit as AF-S's l1_sum (accumulator.cpp): maddubs adds two products of
// a byte (at most 255) and a weight (|w| <= 64, the reader's bound) into an
// int16 exactly (at most 32,640); madd with ones widens the pairs into int32
// lanes; horizontal_sum adds the lanes.
void refiner_l1(const RefinerFile& r, const RefinerInputs& in, std::int32_t* sums) {
  const __m256i ones = _mm256_set1_epi16(1);
  for (int o = 0; o < RefinerL1Width; ++o) {
    __m256i acc = _mm256_setzero_si256();
    for (int i = 0; i < RefinerInputBytes; i += 32) {
      const __m256i x = _mm256_load_si256(reinterpret_cast<const __m256i*>(in.bytes + i));
      const __m256i w = _mm256_load_si256(reinterpret_cast<const __m256i*>(r.entry_weights[o] + i));
      acc = _mm256_add_epi32(acc, _mm256_madd_epi16(_mm256_maddubs_epi16(x, w), ones));
    }
    sums[o] = static_cast<std::int32_t>(horizontal_sum(acc)) + r.entry_bias[o];
  }
  for (int k = 0; k < in.row_count; ++k) {
    const std::int32_t* row = r.row_weights[in.rows[k]];
    for (int o = 0; o < RefinerL1Width; ++o) sums[o] += row[o];
  }
}
#else
void refiner_l1(const RefinerFile& r, const RefinerInputs& in, std::int32_t* sums) {
  refiner_l1_scalar(r, in, sums);
}
#endif

// The entry layer's clipped ReLU, the middle layer, the heads and the
// output's scaling (refiner_file.hpp's units): the scalar reference, and on
// AVX2 the vector path. The vector path computes the middle layer unit by
// unit as the entry layer does (maddubs within the exactness bound, madd
// with ones, horizontal_sum), and each head as the dot product of the middle
// layer's bytes, widened to int16, with its int16 weights (madd,
// horizontal_sum): integer sums of the same terms, so both paths give the
// same values (refiner_file.hpp's bounds keep each one inside int32).
template <bool Scalar>
RefinerOutput refiner_l2_heads(const RefinerFile& r, const std::int32_t* sums) {
  alignas(16) std::uint8_t a[16] = {};  // the entry layer's activations; zero beyond RefinerL1Width
  for (int o = 0; o < RefinerL1Width; ++o)
    a[o] = static_cast<std::uint8_t>(std::clamp(sums[o] / NetQb, 0, NetQa));
  alignas(32) std::uint8_t b[RefinerL2Width];
  std::int64_t y[RefinerHeads];
#if defined(__AVX2__)
  if constexpr (!Scalar) {
    static_assert(RefinerL1Width <= 16 && RefinerL2Width == 32, "the vector path's shapes");
    const __m128i x = _mm_load_si128(reinterpret_cast<const __m128i*>(a));
    const __m128i ones = _mm_set1_epi16(1);
    for (int m = 0; m < RefinerL2Width; ++m) {
      const auto* row = reinterpret_cast<const __m128i*>(r.middle_weights[m]);
      const __m128i w = RefinerL1Width == 16 ? _mm_loadu_si128(row) : _mm_loadl_epi64(row);
      const __m128i p = _mm_madd_epi16(_mm_maddubs_epi16(x, w), ones);
      const auto s = static_cast<std::int32_t>(r.middle_bias[m] + horizontal_sum(_mm256_zextsi128_si256(p)));
      b[m] = static_cast<std::uint8_t>(std::clamp(s / NetQb, 0, NetQa));
    }
    const __m256i lo = _mm256_cvtepu8_epi16(_mm_load_si128(reinterpret_cast<const __m128i*>(b)));
    const __m256i hi = _mm256_cvtepu8_epi16(_mm_load_si128(reinterpret_cast<const __m128i*>(b + 16)));
    for (int h = 0; h < RefinerHeads; ++h) {
      const auto* w = reinterpret_cast<const __m256i*>(r.head_weights[h]);
      const __m256i d = _mm256_add_epi32(_mm256_madd_epi16(lo, _mm256_load_si256(w)),
                                         _mm256_madd_epi16(hi, _mm256_load_si256(w + 1)));
      y[h] = r.head_bias[h] + horizontal_sum(d);
    }
  } else
#endif
  {
    for (int m = 0; m < RefinerL2Width; ++m) {
      std::int32_t s = r.middle_bias[m];
      for (int o = 0; o < RefinerL1Width; ++o) s += a[o] * r.middle_weights[m][o];
      b[m] = static_cast<std::uint8_t>(std::clamp(s / NetQb, 0, NetQa));
    }
    for (int h = 0; h < RefinerHeads; ++h) {
      std::int32_t s = r.head_bias[h];
      for (int m = 0; m < RefinerL2Width; ++m) s += b[m] * r.head_weights[h][m];
      y[h] = s;
    }
  }
  constexpr std::int64_t Unit = std::int64_t{NetQa} * NetQb;
  RefinerOutput out;
  out.correction = static_cast<int>(std::clamp<std::int64_t>(y[0] * r.scale / Unit, -r.cap, r.cap));
  out.confidence = static_cast<int>(std::clamp<std::int64_t>(y[1] * 1000 / Unit, 0, 1000));
  return out;
}

template RefinerOutput refiner_l2_heads<false>(const RefinerFile& r, const std::int32_t* sums);
template RefinerOutput refiner_l2_heads<true>(const RefinerFile& r, const std::int32_t* sums);

void pack_clipped_scalar(const Accumulator& acc, Color stm, std::uint8_t* out) {
  for (int half = 0; half < 2; ++half) {
    const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
    for (int i = 0; i < NetHidden; ++i)
      out[half * NetHidden + i] = static_cast<std::uint8_t>(std::clamp<int>(v[i], 0, NetQa));
  }
}

#if defined(__AVX2__)
// packus saturates int16 to [0, 255], which is the clip at QA = 255; it
// interleaves the 128-bit halves, and the permute restores order.
static_assert(NetQa == 255, "pack_clipped's saturation is the clip at QA");
void pack_clipped(const Accumulator& acc, Color stm, std::uint8_t* out) {
  for (int half = 0; half < 2; ++half) {
    const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
    for (int i = 0; i < NetHidden; i += 32) {
      const __m256i lo = _mm256_load_si256(reinterpret_cast<const __m256i*>(v + i));
      const __m256i hi = _mm256_load_si256(reinterpret_cast<const __m256i*>(v + i + 16));
      const __m256i packed = _mm256_permute4x64_epi64(_mm256_packus_epi16(lo, hi), 0xD8);
      _mm256_store_si256(reinterpret_cast<__m256i*>(out + half * NetHidden + i), packed);
    }
  }
}
#else
void pack_clipped(const Accumulator& acc, Color stm, std::uint8_t* out) {
  pack_clipped_scalar(acc, stm, out);
}
#endif

int refiner_rows(const NetFile& base, const Position& pos, int base_eval, int* rows) {
  const Color stm = pos.side_to_move();
  int n = 0;
  Bitboard exposed;
#if FORK_REFINER_ARCH == 2
  const DangerSummary d = danger_summary(pos, exposed);
#else
  exposed = exposed_pieces(pos);
#endif
  // The exposed pieces from the side to move's view: own/enemy x type x
  // square, ranks flipped for Black and files by the side to move's frame.
  const Frame f = frame_of(base, stm, pos.king_square(stm));
  for (Bitboard b = exposed; b;) {
    const Square s = pop_lsb(b);
    const Piece p = pos.piece_at(s);
    const Square seen = stm == White ? s : s ^ 56;
    rows[n++] = 320 * (side_of(p) != stm) + 64 * kind_of(p) + (seen ^ f.flip);
  }
  int next = NetExposureRows;
#if FORK_REFINER_ARCH == 2
  for (const Color x : {stm, ~stm}) {
    rows[n++] = next + std::min(d.zone_attacked[x], 4);
    rows[n++] = next + 5 + std::min(d.zone_weak[x], 2);
    rows[n++] = next + 8 + std::min(d.safe_checks[x], 2);
    rows[n++] = next + 11 + std::min(d.pinned_count[x], 2);
    rows[n++] = next + 14 + std::min(d.exposed_count[x], 3);
    next += RefinerDangerRows / 2;
  }
#endif
  rows[n++] = next + base.phase_table[game_phase(pos)];
  constexpr int Half = RefinerEvalBins / 2 * RefinerEvalBinCp;
  rows[n++] = next + NetBuckets + (std::clamp(base_eval, -Half, Half - 1) + Half) / RefinerEvalBinCp;
  return n;
}

RefinerOutput run_refiner(const RefinerFile& r, const RefinerInputs& in) {
  alignas(32) std::int32_t sums[RefinerL1Width];
  refiner_l1(r, in, sums);
  return refiner_l2_heads(r, sums);
}

RefinerOutput run_refiner_scalar(const RefinerFile& r, const RefinerInputs& in) {
  alignas(32) std::int32_t sums[RefinerL1Width];
  refiner_l1_scalar(r, in, sums);
  return refiner_l2_heads<true>(r, sums);
}

}  // namespace forkeng
