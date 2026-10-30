// SPDX-License-Identifier: GPL-3.0-or-later

#include "eval/nnue/accumulator.hpp"

#include <algorithm>
#include <cstring>

#if defined(__AVX2__)
#include <immintrin.h>
#endif

#include "core/material.hpp"
#include "eval/eval_scale.hpp"

namespace forkeng {

namespace {

const std::int16_t* column(const NetFile& net, int feature) { return net.ft_weights + feature * NetHidden; }

int clamp_cp(std::int64_t cp) {
  return static_cast<int>(std::clamp<std::int64_t>(cp, -(EvalLimit - 1), EvalLimit - 1));
}

// The feature columns a delta subtracts and adds, for one perspective.
struct DeltaColumns {
  const std::int16_t* sub[2];
  const std::int16_t* add[2];
  int sub_rows[2], add_rows[2];
  int subs = 0, adds = 0;
};

DeltaColumns columns_for(const NetFile& net, const FeatureDelta& d, Color perspective, Frame f) {
  DeltaColumns c;
  for (int i = 0; i < d.removed_count; ++i) {
    c.sub_rows[c.subs] = feature_index(perspective, d.removed_piece[i], d.removed_square[i], f);
    c.sub[c.subs] = column(net, c.sub_rows[c.subs]);
    ++c.subs;
  }
  for (int i = 0; i < d.added_count; ++i) {
    c.add_rows[c.adds] = feature_index(perspective, d.added_piece[i], d.added_square[i], f);
    c.add[c.adds] = column(net, c.add_rows[c.adds]);
    ++c.adds;
  }
  return c;
}

[[maybe_unused]] void advance_values_scalar(const std::int16_t* src, const DeltaColumns& c,
                                            std::int16_t* dst) {
  for (int i = 0; i < NetHidden; ++i) {
    int x = src[i];
    for (int k = 0; k < c.subs; ++k) x -= c.sub[k][i];
    for (int k = 0; k < c.adds; ++k) x += c.add[k][i];
    dst[i] = static_cast<std::int16_t>(x);
  }
}

#if defined(__AVX512BW__)
// 32 int16 lanes per vector.
void advance_values(const std::int16_t* src, const DeltaColumns& c, std::int16_t* dst) {
  for (int i = 0; i < NetHidden; i += 32) {
    __m512i x = _mm512_load_si512(src + i);
    for (int k = 0; k < c.subs; ++k) x = _mm512_sub_epi16(x, _mm512_load_si512(c.sub[k] + i));
    for (int k = 0; k < c.adds; ++k) x = _mm512_add_epi16(x, _mm512_load_si512(c.add[k] + i));
    _mm512_store_si512(dst + i, x);
  }
}
#elif defined(__AVX2__)
// 16 int16 lanes per vector.
void advance_values(const std::int16_t* src, const DeltaColumns& c, std::int16_t* dst) {
  for (int i = 0; i < NetHidden; i += 16) {
    __m256i x = _mm256_load_si256(reinterpret_cast<const __m256i*>(src + i));
    for (int k = 0; k < c.subs; ++k)
      x = _mm256_sub_epi16(x, _mm256_load_si256(reinterpret_cast<const __m256i*>(c.sub[k] + i)));
    for (int k = 0; k < c.adds; ++k)
      x = _mm256_add_epi16(x, _mm256_load_si256(reinterpret_cast<const __m256i*>(c.add[k] + i)));
    _mm256_store_si256(reinterpret_cast<__m256i*>(dst + i), x);
  }
}
#else
void advance_values(const std::int16_t* src, const DeltaColumns& c, std::int16_t* dst) {
  advance_values_scalar(src, c, dst);
}
#endif

#if defined(__AVX2__)
[[maybe_unused]] std::int64_t horizontal_sum(__m256i v) {
  const __m128i s = _mm_add_epi32(_mm256_castsi256_si128(v), _mm256_extracti128_si256(v, 1));
  const __m128i s2 = _mm_add_epi32(s, _mm_shuffle_epi32(s, 0x4E));
  const __m128i s3 = _mm_add_epi32(s2, _mm_shuffle_epi32(s2, 0xB1));
  return _mm_cvtsi128_si32(s3);
}
#endif

// One perspective's sums from scratch, in frame `f`, over the pieces
// `for_each` names; also the side lanes (XGR).
template <class ForEach>
void sum_perspective(const NetFile& net, Color perspective, Frame f, ForEach for_each, Accumulator& out) {
  std::int16_t* v = out.values[perspective];
  std::memcpy(v, net.ft_bias, sizeof net.ft_bias);
#if FORK_NET_ARCH == 5
  std::memcpy(out.side[perspective], net.side_bias, sizeof net.side_bias);
#endif
  for_each([&](Piece p, Square s) {
    const int row = feature_index(perspective, p, s, f);
    const std::int16_t* w = column(net, row);
    for (int i = 0; i < NetHidden; ++i) v[i] = static_cast<std::int16_t>(v[i] + w[i]);
#if FORK_NET_ARCH == 5
    for (int k = 0; k < 4; ++k)
      out.side[perspective][k] =
          static_cast<std::int16_t>(out.side[perspective][k] + net.side_weights[row][k]);
#else
    (void)row;
#endif
  });
}

[[maybe_unused]] int phase_bucket(const NetFile& net, const Position& pos) {
  return net.phase_table[game_phase(pos)];
}

#if FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3 || FORK_NET_ARCH == 5
// sum over both halves (side to move first) of v * (v * w), v the clipped
// value: S-512's and H-512's output, and each of XGR's experts.
std::int64_t squared_sum_scalar(const std::int16_t* stm, const std::int16_t* ntm, const std::int16_t* w) {
  std::int64_t s = 0;
  for (int half = 0; half < 2; ++half) {
    const std::int16_t* v = half == 0 ? stm : ntm;
    for (int i = 0; i < NetHidden; ++i) {
      const int x = std::clamp<int>(v[i], 0, NetQa);
      s += std::int64_t{x} * (x * w[half * NetHidden + i]);
    }
  }
  return s;
}

#if defined(__AVX2__)
// v * w is exact in 16 bits (|w| <= 128 is the loader's bound), and each
// int32 lane adds 2 * 2H / 16 products of at most 8,323,200 (128 at H = 512),
// far below the int32 limit, so the sum equals the scalar one.
std::int64_t squared_sum(const std::int16_t* stm, const std::int16_t* ntm, const std::int16_t* w) {
  const __m256i zero = _mm256_setzero_si256(), qa = _mm256_set1_epi16(NetQa);
  __m256i sum = _mm256_setzero_si256();
  for (int half = 0; half < 2; ++half) {
    const std::int16_t* v = half == 0 ? stm : ntm;
    const std::int16_t* wh = w + half * NetHidden;
    for (int i = 0; i < NetHidden; i += 16) {
      const __m256i x = _mm256_min_epi16(
          _mm256_max_epi16(_mm256_load_si256(reinterpret_cast<const __m256i*>(v + i)), zero), qa);
      const __m256i t = _mm256_mullo_epi16(x, _mm256_load_si256(reinterpret_cast<const __m256i*>(wh + i)));
      sum = _mm256_add_epi32(sum, _mm256_madd_epi16(t, x));
    }
  }
  return horizontal_sum(sum);
}
#else
std::int64_t squared_sum(const std::int16_t* stm, const std::int16_t* ntm, const std::int16_t* w) {
  return squared_sum_scalar(stm, ntm, w);
}
#endif
#endif

#if FORK_NET_ARCH == 4
// AF-S's pairwise products: per perspective (side to move first),
// (v[j] * v[j + H/2] + 256) >> 9 of the clipped values, in [0, 127].
void pair_products_scalar(const Accumulator& acc, Color stm, std::uint8_t* x) {
  for (int half = 0; half < 2; ++half) {
    const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
    for (int j = 0; j < NetHidden / 2; ++j) {
      const int a = std::clamp<int>(v[j], 0, NetQa), b = std::clamp<int>(v[j + NetHidden / 2], 0, NetQa);
      x[half * NetHidden / 2 + j] = static_cast<std::uint8_t>((a * b + 256) >> 9);
    }
  }
}

std::int32_t l1_sum_scalar(const std::uint8_t* x, const std::int8_t* w) {
  std::int32_t s = 0;
  for (int i = 0; i < NetHidden; ++i) s += x[i] * w[i];
  return s;
}

#if defined(__AVX2__)
void pair_products(const Accumulator& acc, Color stm, std::uint8_t* x) {
  // (a * b + 256) >> 9 = high half of (a << 6) * b with rounding:
  // ((64ab + 2^14) >> 15) (design-accuracy.md §5.3), exact for a, b <= 255.
  const __m256i zero = _mm256_setzero_si256(), qa = _mm256_set1_epi16(NetQa);
  for (int half = 0; half < 2; ++half) {
    const std::int16_t* v = acc.values[half == 0 ? stm : ~stm];
    for (int j = 0; j < NetHidden / 2; j += 32) {
      __m256i out[2];
      for (int k = 0; k < 2; ++k) {
        const auto* p = reinterpret_cast<const __m256i*>(v + j + 16 * k);
        const auto* q = reinterpret_cast<const __m256i*>(v + j + 16 * k + NetHidden / 2);
        const __m256i a = _mm256_min_epi16(_mm256_max_epi16(_mm256_load_si256(p), zero), qa);
        const __m256i b = _mm256_min_epi16(_mm256_max_epi16(_mm256_load_si256(q), zero), qa);
        out[k] = _mm256_mulhrs_epi16(_mm256_slli_epi16(a, 6), b);
      }
      // packus interleaves the 128-bit halves; the permute restores order.
      const __m256i packed = _mm256_permute4x64_epi64(_mm256_packus_epi16(out[0], out[1]), 0xD8);
      _mm256_storeu_si256(reinterpret_cast<__m256i*>(x + half * NetHidden / 2 + j), packed);
    }
  }
}

// maddubs adds two products of at most 127 x 127 into an int16 (32,258, no
// saturation); madd with ones widens the pairs into int32 lanes.
std::int32_t l1_sum(const std::uint8_t* x, const std::int8_t* w) {
  const __m256i ones = _mm256_set1_epi16(1);
  __m256i sum = _mm256_setzero_si256();
  for (int i = 0; i < NetHidden; i += 32) {
    const __m256i p = _mm256_maddubs_epi16(_mm256_loadu_si256(reinterpret_cast<const __m256i*>(x + i)),
                                           _mm256_load_si256(reinterpret_cast<const __m256i*>(w + i)));
    sum = _mm256_add_epi32(sum, _mm256_madd_epi16(p, ones));
  }
  return static_cast<std::int32_t>(horizontal_sum(sum));
}
#else
void pair_products(const Accumulator& acc, Color stm, std::uint8_t* x) { pair_products_scalar(acc, stm, x); }
std::int32_t l1_sum(const std::uint8_t* x, const std::int8_t* w) { return l1_sum_scalar(x, w); }
#endif

// L1's sums for stack k, then the shared small layers (design-accuracy.md
// §5.4): clamp(y >> 2, 0, 2032) squared >> 11, L2, clamp(y >> 13, 0, 2016)
// squared >> 11, L3, (y3 * M) >> 32.
template <bool Scalar>
int af_output(const NetFile& net, const Accumulator& acc, const Position& pos) {
  alignas(32) std::uint8_t x[NetHidden];
  const Color stm = pos.side_to_move();
  if constexpr (Scalar)
    pair_products_scalar(acc, stm, x);
  else
    pair_products(acc, stm, x);
  const int k = phase_bucket(net, pos);
  std::int32_t q1[NetL1];
  for (int o = 0; o < NetL1; ++o) {
    const std::int32_t y = net.af1_bias[k][o] + (Scalar ? l1_sum_scalar(x, net.af1_weights[k][o])
                                                        : l1_sum(x, net.af1_weights[k][o]));
    const std::int32_t c = std::clamp<std::int32_t>(y >> 2, 0, 2032);
    q1[o] = (c * c) >> 11;
  }
  std::int32_t q2[NetL2];
  for (int o = 0; o < NetL2; ++o) {
    std::int32_t y = net.af2_bias[k][o];
    for (int i = 0; i < NetL1; ++i) y += q1[i] * net.af2_weights[k][o][i];
    const std::int32_t c = std::clamp<std::int32_t>(y >> 13, 0, 2016);
    q2[o] = (c * c) >> 11;
  }
  std::int32_t y3 = net.af3_bias[k];
  for (int i = 0; i < NetL2; ++i) y3 += q2[i] * net.af3_weights[k][i];
  return clamp_cp((std::int64_t{y3} * net.output_multiplier) >> 32);
}
#endif

#if FORK_NET_ARCH == 5
// XGR: the accumulator plus the exposed pieces' rows (summed at every
// evaluation, no incremental state), then the two experts blended by the
// gate (design-novelty.md §5.1).
template <bool Scalar>
int xgr_output(const NetFile& net, const Accumulator& acc, const Position& pos) {
  Accumulator a = acc;
  const Bitboard exposed = exposed_pieces(pos);
  const int first = NetPieceSquares * net.region_count;
  for (const Color perspective : {White, Black}) {
    const Frame f = frame_of(net, perspective, pos.king_square(perspective));
    for (Bitboard b = exposed; b;) {
      const Square s = pop_lsb(b);
      const Piece p = pos.piece_at(s);
      const Square seen = perspective == White ? s : s ^ 56;
      const int row = first + 320 * (side_of(p) != perspective) + 64 * kind_of(p) + (seen ^ f.flip);
      const std::int16_t* w = column(net, row);
      std::int16_t* v = a.values[perspective];
      for (int i = 0; i < NetHidden; ++i) v[i] = static_cast<std::int16_t>(v[i] + w[i]);
      for (int k = 0; k < 4; ++k)
        a.side[perspective][k] = static_cast<std::int16_t>(a.side[perspective][k] + net.side_weights[row][k]);
    }
  }
  const Color stm = pos.side_to_move();
  std::int64_t o[2];
  for (int e = 0; e < 2; ++e) {
    const std::int64_t s = Scalar ? squared_sum_scalar(a.values[stm], a.values[~stm], net.expert_weights[e])
                                  : squared_sum(a.values[stm], a.values[~stm], net.expert_weights[e]);
    o[e] = s / NetQa + net.expert_bias[e] + 128 * (a.side[stm][1 + e] - a.side[~stm][1 + e]);
  }
  const std::int64_t g = std::clamp(a.side[stm][0] + a.side[~stm][0], 0, NetQa);
  const std::int64_t out = (o[1] * NetQa + g * (o[0] - o[1])) / NetQa;
  return clamp_cp(out * net.scale / (NetQa * NetQb));
}
#endif

template <bool Scalar>
int evaluate_with(const NetFile& net, const Accumulator& acc, const Position& pos) {
#if FORK_NET_ARCH == 1
  return Scalar ? output_layer_scalar(net, acc, pos.side_to_move())
                : output_layer(net, acc, pos.side_to_move());
#elif FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3
  const Color stm = pos.side_to_move();
  const int k = phase_bucket(net, pos);
  const std::int64_t s = Scalar ? squared_sum_scalar(acc.values[stm], acc.values[~stm], net.out_weights[k])
                                : squared_sum(acc.values[stm], acc.values[~stm], net.out_weights[k]);
  const std::int64_t y = s / NetQa + net.out_bias[k];
  return clamp_cp(y * net.scale / (NetQa * NetQb));
#elif FORK_NET_ARCH == 4
  return af_output<Scalar>(net, acc, pos);
#elif FORK_NET_ARCH == 5
  return xgr_output<Scalar>(net, acc, pos);
#endif
}

}  // namespace

Frame frame_of([[maybe_unused]] const NetFile& net, Color perspective, Square own_king) {
  if constexpr (!NetMirrored) {
    return {};
  } else {
    const Square seen = perspective == White ? own_king : own_king ^ 56;
    const int flip = (seen & 7) < 4 ? 7 : 0;
    const Square k = seen ^ flip;
    const int region = NetRegioned ? net.regions[(k >> 3) * 4 + (k & 7) - 4] : 0;
    return {flip, NetPieceSquares * region};
  }
}

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
    const Frame f = frame_of(net, perspective, pos.king_square(perspective));
    sum_perspective(
        net, perspective, f,
        [&](auto&& visit) {
          for (Bitboard b = pos.pieces(); b;) {
            const Square s = pop_lsb(b);
            visit(pos.piece_at(s), s);
          }
        },
        out);
  }
}

void advance_perspective(const NetFile& net, const Accumulator& from, const FeatureDelta& d,
                         Color perspective, Frame frame, Accumulator& to) {
  const DeltaColumns c = columns_for(net, d, perspective, frame);
  advance_values(from.values[perspective], c, to.values[perspective]);
#if FORK_NET_ARCH == 5
  for (int k = 0; k < 4; ++k) {
    int x = from.side[perspective][k];
    for (int i = 0; i < c.subs; ++i) x -= net.side_weights[c.sub_rows[i]][k];
    for (int i = 0; i < c.adds; ++i) x += net.side_weights[c.add_rows[i]][k];
    to.side[perspective][k] = static_cast<std::int16_t>(x);
  }
#endif
}

int evaluate_position(const NetFile& net, const Accumulator& acc, const Position& pos) {
  return evaluate_with<false>(net, acc, pos);
}

int evaluate_position_scalar(const NetFile& net, const Accumulator& acc, const Position& pos) {
  return evaluate_with<true>(net, acc, pos);
}

#if FORK_NET_ARCH == 5
Bitboard exposed_pieces(const Position& pos) {
  constexpr int Class[6] = {1, 2, 2, 3, 4, 5};
  const Bitboard occ = pos.pieces();
  Bitboard out = 0;
  for (Bitboard b = occ & ~pos.pieces(King); b;) {
    const Square s = pop_lsb(b);
    const Piece p = pos.piece_at(s);
    const Color c = side_of(p);
    const Bitboard attackers = pos.attackers_to(s, occ);
    const Bitboard enemy = attackers & pos.pieces(~c);
    if (!enemy) continue;
    int lowest = 5;
    if (enemy & pos.pieces(Pawn))
      lowest = 1;
    else if (enemy & (pos.pieces(Knight) | pos.pieces(Bishop)))
      lowest = 2;
    else if (enemy & pos.pieces(Rook))
      lowest = 3;
    else if (enemy & pos.pieces(Queen))
      lowest = 4;
    if (lowest < Class[kind_of(p)] || !(attackers & pos.pieces(c))) out |= Bitboard{1} << s;
  }
  return out;
}
#endif

#if FORK_NET_ARCH == 1

namespace {

// The final step every B0 path shares: the output sum, scaled and clamped.
int scale_output(const NetFile& net, std::int32_t sum) {
  return clamp_cp((std::int64_t{sum} + net.out_bias) * net.scale / (NetQa * NetQb));
}

}  // namespace

void advance_accumulator_scalar(const NetFile& net, const Accumulator& from, const FeatureDelta& d,
                                Accumulator& to) {
  for (const Color perspective : {White, Black})
    advance_values_scalar(from.values[perspective], columns_for(net, d, perspective, Frame{}),
                          to.values[perspective]);
}

void advance_accumulator(const NetFile& net, const Accumulator& from, const FeatureDelta& d,
                         Accumulator& to) {
  for (const Color perspective : {White, Black})
    advance_values(from.values[perspective], columns_for(net, d, perspective, Frame{}),
                   to.values[perspective]);
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
  return scale_output(net, static_cast<std::int32_t>(horizontal_sum(sum)));
}

#else

int output_layer(const NetFile& net, const Accumulator& acc, Color stm) {
  return output_layer_scalar(net, acc, stm);
}

#endif
#endif  // FORK_NET_ARCH == 1

void FeatureStack::reset(const NetFile& net, const Position& root) {
  Entry& e = entries_[0];
  for (const Color perspective : {White, Black}) {
    e.frame[perspective] = frame_of(net, perspective, root.king_square(perspective));
    e.computed[perspective] = true;
  }
  accumulate_board(net, root, e.acc);
}

void FeatureStack::push_move(const NetFile& net, int ply, const Position& before, Move m) {
  const Entry& parent = entries_[ply];
  Entry& e = entries_[ply + 1];
  e.delta = delta_for_move(before, m);
  e.computed[White] = e.computed[Black] = false;
  if constexpr (NetMirrored) {  // B0's frames are always the identity
    e.frame[White] = parent.frame[White];
    e.frame[Black] = parent.frame[Black];
    const Color us = before.side_to_move();
    if (kind_of(before.piece_at(m.from())) == King) {
      const Square to = m.is_castle() ? Position::castle_landing(m.from(), m.to()).king : m.to();
      const Frame f = frame_of(net, us, to);
      if (f != parent.frame[us]) {
        // The mover's perspective sees a new frame: its sums from the board
        // after the move (the parent's pieces with the delta applied).
        e.frame[us] = f;
        const FeatureDelta& d = e.delta;
        sum_perspective(
            net, us, f,
            [&](auto&& visit) {
              for (Bitboard b = before.pieces(); b;) {
                const Square s = pop_lsb(b);
                const Piece p = before.piece_at(s);
                bool gone = false;
                for (int i = 0; i < d.removed_count; ++i)
                  gone |= d.removed_square[i] == s && d.removed_piece[i] == p;
                if (!gone) visit(p, s);
              }
              for (int i = 0; i < d.added_count; ++i) visit(d.added_piece[i], d.added_square[i]);
            },
            e.acc);
        e.computed[us] = true;
      }
    }
  }
}

int FeatureStack::evaluate(const NetFile& net, int ply, const Position& pos) {
#if FORK_NET_ARCH == 1
  // B0 never changes a frame, so both perspectives are computed together.
  int base = ply;
  while (!entries_[base].computed[White]) --base;  // ply 0 is always computed
  for (int p = base + 1; p <= ply; ++p) {
    advance_accumulator(net, entries_[p - 1].acc, entries_[p].delta, entries_[p].acc);
    entries_[p].computed[White] = entries_[p].computed[Black] = true;
  }
#else
  for (const Color perspective : {White, Black}) {
    int base = ply;
    while (!entries_[base].computed[perspective]) --base;  // ply 0 is always computed
    for (int p = base + 1; p <= ply; ++p) {
      advance_perspective(net, entries_[p - 1].acc, entries_[p].delta, perspective,
                          entries_[p].frame[perspective], entries_[p].acc);
      entries_[p].computed[perspective] = true;
    }
  }
#endif
#ifdef FORK_DEBUG
  Accumulator check;
  accumulate_board(net, pos, check);
  if (std::memcmp(&check, &entries_[ply].acc, sizeof check) != 0) __builtin_trap();
#endif
  return evaluate_position(net, entries_[ply].acc, pos);
}

}  // namespace forkeng
