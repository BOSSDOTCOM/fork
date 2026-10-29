// SPDX-License-Identifier: GPL-3.0-or-later

#include "eval/nnue/accumulator.hpp"

#include <algorithm>
#include <cstring>

#if defined(__AVX2__)
#include <immintrin.h>
#endif

#include "eval/eval_scale.hpp"

namespace forkeng {

namespace {

const std::int16_t* column(const NetFile& net, int feature) { return net.ft_weights + feature * NetHidden; }

// The final step every path shares: the output sum, scaled and clamped.
int scale_output(const NetFile& net, std::int32_t sum) {
  const std::int64_t cp = (std::int64_t{sum} + net.out_bias) * net.scale / (NetQa * NetQb);
  return static_cast<int>(std::clamp<std::int64_t>(cp, -(EvalLimit - 1), EvalLimit - 1));
}

// The feature columns a delta subtracts and adds, for one perspective.
struct DeltaColumns {
  const std::int16_t* sub[2];
  const std::int16_t* add[2];
  int subs = 0, adds = 0;
};

DeltaColumns columns_for(const NetFile& net, const FeatureDelta& d, Color perspective) {
  DeltaColumns c;
  for (int i = 0; i < d.removed_count; ++i)
    c.sub[c.subs++] = column(net, feature_index(perspective, d.removed_piece[i], d.removed_square[i]));
  for (int i = 0; i < d.added_count; ++i)
    c.add[c.adds++] = column(net, feature_index(perspective, d.added_piece[i], d.added_square[i]));
  return c;
}

}  // namespace

FeatureDelta delta_for_move(const Position& before, Move m) {
  FeatureDelta d;
  const Color us = before.side_to_move();
  const Square from = m.from(), to = m.to();
  const Piece mover = before.piece_at(from);
  auto remove = [&](Piece p, Square s) {
    d.removed_piece[d.removed_count] = p;
    d.removed_square[d.removed_count++] = s;
  };
  auto add = [&](Piece p, Square s) {
    d.added_piece[d.added_count] = p;
    d.added_square[d.added_count++] = s;
  };
  if (m.is_castle()) {  // encoded king to its own rook's square
    const auto landing = Position::castle_landing(from, to);
    remove(mover, from);
    remove(before.piece_at(to), to);
    add(mover, landing.king);
    add(piece_of(us, Rook), landing.rook);
    return d;
  }
  remove(mover, from);
  if (m.is_capture()) {
    const Square captured = before.capture_square(m);
    remove(before.piece_at(captured), captured);
  }
  add(m.is_promotion() ? piece_of(us, m.promo_type()) : mover, to);
  return d;
}

void accumulate_board(const NetFile& net, const Position& pos, Accumulator& out) {
  for (const Color perspective : {White, Black}) {
    std::int16_t* v = out.values[perspective];
    std::memcpy(v, net.ft_bias, sizeof net.ft_bias);
    for (Bitboard b = pos.pieces(); b;) {
      const Square s = pop_lsb(b);
      const std::int16_t* w = column(net, feature_index(perspective, pos.piece_at(s), s));
      for (int i = 0; i < NetHidden; ++i) v[i] = static_cast<std::int16_t>(v[i] + w[i]);
    }
  }
}

void advance_accumulator_scalar(const NetFile& net, const Accumulator& from, const FeatureDelta& d, Accumulator& to) {
  for (const Color perspective : {White, Black}) {
    const DeltaColumns c = columns_for(net, d, perspective);
    const std::int16_t* src = from.values[perspective];
    std::int16_t* dst = to.values[perspective];
    for (int i = 0; i < NetHidden; ++i) {
      int x = src[i];
      for (int k = 0; k < c.subs; ++k) x -= c.sub[k][i];
      for (int k = 0; k < c.adds; ++k) x += c.add[k][i];
      dst[i] = static_cast<std::int16_t>(x);
    }
  }
}

int output_layer_scalar(const NetFile& net, const Accumulator& acc, Color stm) {
  std::int32_t sum = 0;
  for (int half = 0; half < 2; ++half) {
    const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
    const std::int16_t* w = net.out_weights + half * NetHidden;
    for (int i = 0; i < NetHidden; ++i) sum += std::clamp<std::int32_t>(v[i], 0, NetQa) * w[i];
  }
  return scale_output(net, sum);
}

#if defined(__AVX512BW__)

// 32 int16 lanes per vector.
void advance_accumulator(const NetFile& net, const Accumulator& from, const FeatureDelta& d, Accumulator& to) {
  for (const Color perspective : {White, Black}) {
    const DeltaColumns c = columns_for(net, d, perspective);
    const std::int16_t* src = from.values[perspective];
    std::int16_t* dst = to.values[perspective];
    for (int i = 0; i < NetHidden; i += 32) {
      __m512i x = _mm512_load_si512(src + i);
      for (int k = 0; k < c.subs; ++k) x = _mm512_sub_epi16(x, _mm512_load_si512(c.sub[k] + i));
      for (int k = 0; k < c.adds; ++k) x = _mm512_add_epi16(x, _mm512_load_si512(c.add[k] + i));
      _mm512_store_si512(dst + i, x);
    }
  }
}

int output_layer(const NetFile& net, const Accumulator& acc, Color stm) {
  const __m512i zero = _mm512_setzero_si512(), qa = _mm512_set1_epi16(NetQa);
  __m512i sum = _mm512_setzero_si512();
  for (int half = 0; half < 2; ++half) {
    const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
    const std::int16_t* w = net.out_weights + half * NetHidden;
    for (int i = 0; i < NetHidden; i += 32) {
      const __m512i a = _mm512_min_epi16(_mm512_max_epi16(_mm512_load_si512(v + i), zero), qa);
#if defined(__AVX512VNNI__)
      sum = _mm512_dpwssd_epi32(sum, a, _mm512_load_si512(w + i));
#else
      sum = _mm512_add_epi32(sum, _mm512_madd_epi16(a, _mm512_load_si512(w + i)));
#endif
    }
  }
  return scale_output(net, _mm512_reduce_add_epi32(sum));
}

#elif defined(__AVX2__)

// 16 int16 lanes per vector.
void advance_accumulator(const NetFile& net, const Accumulator& from, const FeatureDelta& d, Accumulator& to) {
  for (const Color perspective : {White, Black}) {
    const DeltaColumns c = columns_for(net, d, perspective);
    const std::int16_t* src = from.values[perspective];
    std::int16_t* dst = to.values[perspective];
    for (int i = 0; i < NetHidden; i += 16) {
      __m256i x = _mm256_load_si256(reinterpret_cast<const __m256i*>(src + i));
      for (int k = 0; k < c.subs; ++k)
        x = _mm256_sub_epi16(x, _mm256_load_si256(reinterpret_cast<const __m256i*>(c.sub[k] + i)));
      for (int k = 0; k < c.adds; ++k)
        x = _mm256_add_epi16(x, _mm256_load_si256(reinterpret_cast<const __m256i*>(c.add[k] + i)));
      _mm256_store_si256(reinterpret_cast<__m256i*>(dst + i), x);
    }
  }
}

int output_layer(const NetFile& net, const Accumulator& acc, Color stm) {
  const __m256i zero = _mm256_setzero_si256(), qa = _mm256_set1_epi16(NetQa);
  __m256i sum = _mm256_setzero_si256();
  for (int half = 0; half < 2; ++half) {
    const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
    const std::int16_t* w = net.out_weights + half * NetHidden;
    for (int i = 0; i < NetHidden; i += 16) {
      const __m256i x = _mm256_load_si256(reinterpret_cast<const __m256i*>(v + i));
      const __m256i a = _mm256_min_epi16(_mm256_max_epi16(x, zero), qa);
      sum = _mm256_add_epi32(
          sum, _mm256_madd_epi16(a, _mm256_load_si256(reinterpret_cast<const __m256i*>(w + i))));
    }
  }
  const __m128i s = _mm_add_epi32(_mm256_castsi256_si128(sum), _mm256_extracti128_si256(sum, 1));
  const __m128i s2 = _mm_add_epi32(s, _mm_shuffle_epi32(s, 0x4E));
  const __m128i s3 = _mm_add_epi32(s2, _mm_shuffle_epi32(s2, 0xB1));
  return scale_output(net, _mm_cvtsi128_si32(s3));
}

#else

void advance_accumulator(const NetFile& net, const Accumulator& from, const FeatureDelta& d, Accumulator& to) {
  advance_accumulator_scalar(net, from, d, to);
}

int output_layer(const NetFile& net, const Accumulator& acc, Color stm) {
  return output_layer_scalar(net, acc, stm);
}

#endif

void FeatureStack::reset(const NetFile& net, const Position& root) {
  accumulate_board(net, root, entries_[0].acc);
  entries_[0].computed = true;
}

int FeatureStack::evaluate(const NetFile& net, int ply, const Position& pos) {
  int base = ply;
  while (!entries_[base].computed) --base;  // ply 0 is always computed
  for (int p = base + 1; p <= ply; ++p) {
    advance_accumulator(net, entries_[p - 1].acc, entries_[p].delta, entries_[p].acc);
    entries_[p].computed = true;
  }
#ifdef FORK_DEBUG
  Accumulator check;
  accumulate_board(net, pos, check);
  if (std::memcmp(&check, &entries_[ply].acc, sizeof check) != 0) __builtin_trap();
#endif
  return output_layer(net, entries_[ply].acc, pos.side_to_move());
}

}  // namespace forkeng
