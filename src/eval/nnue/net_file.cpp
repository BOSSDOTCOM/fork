// SPDX-License-Identifier: GPL-3.0-or-later

#include "eval/nnue/net_file.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>

#include "core/splitmix.hpp"

namespace forkeng {

namespace {

constexpr char Magic[8] = {'F', 'O', 'R', 'K', 'N', 'E', 'T', 0};
constexpr int MaxActivePieces = 32;
constexpr int MaxExposed = 30;  // every piece but the kings

std::uint32_t get_u32(const std::uint8_t* p) {
  return std::uint32_t{p[0]} | std::uint32_t{p[1]} << 8 | std::uint32_t{p[2]} << 16 |
         std::uint32_t{p[3]} << 24;
}

std::uint64_t get_u64(const std::uint8_t* p) { return get_u32(p) | std::uint64_t{get_u32(p + 4)} << 32; }

void put_u32(std::vector<std::uint8_t>& out, std::uint32_t v) {
  for (int i = 0; i < 4; ++i) out.push_back(static_cast<std::uint8_t>(v >> (8 * i)));
}

void put_u64(std::vector<std::uint8_t>& out, std::uint64_t v) {
  put_u32(out, static_cast<std::uint32_t>(v));
  put_u32(out, static_cast<std::uint32_t>(v >> 32));
}

// Reads little-endian values in file order, never past the end.
struct Cursor {
  const std::uint8_t* p;
  const std::uint8_t* end;
  bool ok = true;
  bool take(std::size_t n) {
    if (static_cast<std::size_t>(end - p) < n) ok = false;
    return ok;
  }
  std::int16_t i16() { return take(2) ? (p += 2, static_cast<std::int16_t>(p[-2] | (p[-1] << 8))) : 0; }
  std::int8_t i8() { return take(1) ? static_cast<std::int8_t>(*p++) : 0; }
  std::int32_t i32() { return take(4) ? (p += 4, static_cast<std::int32_t>(get_u32(p - 4))) : 0; }
  std::int64_t i64() { return take(8) ? (p += 8, static_cast<std::int64_t>(get_u64(p - 8))) : 0; }
};

// The largest |weight| of first-layer unit `j` over rows [from, to) of a
// row-major table with `width` values per row.
int largest(const std::int16_t* table, int width, int j, int from, int to) {
  int out = 0;
  for (int f = from; f < to; ++f) out = std::max(out, std::abs(int{table[f * width + j]}));
  return out;
}

bool first_layer_in_range(const std::int16_t* weights, const std::int16_t* bias, int width, int piece_rows,
                          int rows, std::string& error) {
  for (int j = 0; j < width; ++j) {
    const std::int64_t worst = std::abs(int{bias[j]}) +
                               MaxActivePieces * largest(weights, width, j, 0, piece_rows) +
                               MaxExposed * largest(weights, width, j, piece_rows, rows);
    if (worst > std::numeric_limits<std::int16_t>::max()) {
      error = "first-layer unit " + std::to_string(j) + " can leave the int16 range";
      return false;
    }
  }
  return true;
}

// The overflow bounds of the header comment; false names the first broken one.
bool sums_in_range(const NetFile& net, std::string& error) {
  const int piece_rows = NetPieceSquares * net.region_count;
  if (!first_layer_in_range(net.ft_weights, net.ft_bias, NetHidden, piece_rows, net.inputs, error))
    return false;
#if FORK_NET_ARCH == 1
  std::int64_t total = 0;
  for (int i = 0; i < 2 * NetHidden; ++i) total += std::abs(int{net.out_weights[i]});
  if (NetQa * total + std::abs(std::int64_t{net.out_bias}) > std::numeric_limits<std::int32_t>::max())
    return error = "the output layer can leave the int32 range", false;
#elif FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3 || FORK_NET_ARCH == 5
  // Squared outputs: each product v * (v * w) needs |w| <= 128 so that v * w
  // stays in int16; the sums run in int64.
#if FORK_NET_ARCH == 5
  const auto& outs = net.expert_weights;
  constexpr int Count = 2;
#else
  const auto& outs = net.out_weights;
  constexpr int Count = NetBuckets;
#endif
  for (int b = 0; b < Count; ++b)
    for (int i = 0; i < 2 * NetHidden; ++i)
      if (std::abs(int{outs[b][i]}) > std::numeric_limits<std::int16_t>::max() / NetQa)
        return error = "an output weight is too large for the squared output", false;
#if FORK_NET_ARCH == 5
  std::int16_t side[NetInputs * 4];
  for (int f = 0; f < net.inputs; ++f)
    for (int k = 0; k < 4; ++k) side[f * 4 + k] = net.side_weights[f][k];
  if (!first_layer_in_range(side, net.side_bias, 4, piece_rows, net.inputs, error)) return false;
#endif
#elif FORK_NET_ARCH == 4
  // L1 sums at most H products of 127 x 127, L2 16 of 2016 x |w|, L3 32 of
  // 1984 x |w| (design-accuracy.md §5.3-5.4).
  for (int k = 0; k < NetBuckets; ++k) {
    for (int o = 0; o < NetL1; ++o)
      if (std::abs(std::int64_t{net.af1_bias[k][o]}) > (std::int64_t{1} << 30))
        return error = "an L1 bias is out of range", false;
    for (int o = 0; o < NetL2; ++o) {
      std::int64_t s = std::abs(std::int64_t{net.af2_bias[k][o]});
      for (int i = 0; i < NetL1; ++i) s += 2016 * std::abs(int{net.af2_weights[k][o][i]});
      if (s > std::numeric_limits<std::int32_t>::max()) return error = "L2 can leave the int32 range", false;
    }
    std::int64_t s = std::abs(std::int64_t{net.af3_bias[k]});
    for (int i = 0; i < NetL2; ++i) s += 1984 * std::abs(int{net.af3_weights[k][i]});
    if (s > std::numeric_limits<std::int32_t>::max()) return error = "L3 can leave the int32 range", false;
  }
  if (net.output_multiplier <= 0 || net.output_multiplier > (std::int64_t{1} << 40))
    return error = "bad output output_multiplier", false;
#endif
  return true;
}

}  // namespace

std::uint64_t net_checksum(std::span<const std::uint8_t> payload) {
  std::uint64_t h = payload.size();
  for (std::size_t i = 0; i < payload.size(); i += 8) {
    std::uint64_t word = 0;
    for (std::size_t k = 0; k < 8 && i + k < payload.size(); ++k)
      word |= std::uint64_t{payload[i + k]} << (8 * k);
    h = splitmix_finalize(h ^ word);
  }
  return h;
}

bool read_net_file(std::span<const std::uint8_t> bytes, NetFile& out, std::string& error) {
  if (bytes.size() < NetHeaderBytes) return error = "shorter than a header", false;
  const std::uint8_t* h = bytes.data();
  if (std::memcmp(h, Magic, sizeof Magic) != 0) return error = "not a Fork net file", false;
  if (get_u32(h + 8) != NetFormatVersion) return error = "unknown format version", false;
  if (get_u32(h + 12) != static_cast<std::uint32_t>(NetArchitecture))
    return error = "architecture " + std::to_string(get_u32(h + 12)) + ", this build reads " +
                   std::to_string(NetArchitecture),
           false;
  const auto inputs = static_cast<int>(get_u32(h + 16));
  if (get_u32(h + 20) != NetHidden || inputs < NetPieceSquares || inputs > NetInputs)
    return error = "wrong layer sizes", false;
  if (static_cast<std::int32_t>(get_u32(h + 24)) != NetQa ||
      static_cast<std::int32_t>(get_u32(h + 28)) != NetQb)
    return error = "wrong quantization factors", false;
  const auto scale = static_cast<std::int32_t>(get_u32(h + 32));
  if (scale < 1 || scale > 100000) return error = "output scale out of range", false;
  if (get_u32(h + 36) != (NetFormatVersion == 1 ? 0u : static_cast<std::uint32_t>(NetBuckets)))
    return error = "wrong bucket count", false;
  for (std::size_t i = 48; i < NetHeaderBytes; ++i)
    if (h[i] != 0) return error = "nonzero reserved header bytes", false;
  const std::span<const std::uint8_t> payload = bytes.subspan(NetHeaderBytes);
  if (net_checksum(payload) != get_u64(h + 40)) return error = "checksum mismatch", false;

  Cursor c{payload.data(), payload.data() + payload.size()};
  out.inputs = inputs;
  out.region_count = 1;
  if constexpr (NetFormatVersion == 2) {
    if (!c.take(NetMapBytes)) return error = "no map block", false;
    std::memcpy(out.regions, c.p, sizeof out.regions);
    std::memcpy(out.phase_table, c.p + 32, sizeof out.phase_table);
    for (std::size_t i = 57; i < NetMapBytes; ++i)
      if (c.p[i] != 0) return error = "nonzero reserved map bytes", false;
    c.p += NetMapBytes;
    int most = 0;
    for (const std::uint8_t r : out.regions) most = std::max(most, int{r});
    if (most >= NetMaxRegions) return error = "too many king regions", false;
    out.region_count = NetRegioned ? most + 1 : 1;
    if (!NetRegioned && most != 0) return error = "regions in a network without them", false;
    for (int p = 0; p < 25; ++p)
      if (out.phase_table[p] >= NetBuckets || (p > 0 && out.phase_table[p] < out.phase_table[p - 1]))
        return error = "bad phase table", false;
  }
  const int expected_inputs = NetPieceSquares * out.region_count + (NetExposure ? NetExposureRows : 0);
  if (inputs != expected_inputs) return error = "inputs do not match the region map", false;
  for (int i = 0; i < inputs * NetHidden; ++i) out.ft_weights[i] = c.i16();
  for (int i = 0; i < NetHidden; ++i) out.ft_bias[i] = c.i16();
#if FORK_NET_ARCH == 1
  for (int i = 0; i < 2 * NetHidden; ++i) out.out_weights[i] = c.i16();
  out.out_bias = c.i32();
#elif FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3
  for (auto& row : out.out_weights)
    for (auto& w : row) w = c.i16();
  for (auto& b : out.out_bias) b = c.i32();
#elif FORK_NET_ARCH == 4
  for (auto& stack : out.af1_weights)
    for (auto& row : stack)
      for (auto& w : row) w = c.i8();
  for (auto& stack : out.af1_bias)
    for (auto& b : stack) b = c.i32();
  for (auto& stack : out.af2_weights)
    for (auto& row : stack)
      for (auto& w : row) w = c.i16();
  for (auto& stack : out.af2_bias)
    for (auto& b : stack) b = c.i32();
  for (auto& stack : out.af3_weights)
    for (auto& w : stack) w = c.i16();
  for (auto& b : out.af3_bias) b = c.i32();
  out.output_multiplier = c.i64();
#elif FORK_NET_ARCH == 5
  for (int f = 0; f < inputs; ++f) {
    for (int k = 0; k < 3; ++k) out.side_weights[f][k] = c.i16();
    out.side_weights[f][3] = 0;
  }
  for (int k = 0; k < 3; ++k) out.side_bias[k] = c.i16();
  out.side_bias[3] = 0;
  for (int e = 0; e < 2; ++e) {
    for (auto& w : out.expert_weights[e]) w = c.i16();
    out.expert_bias[e] = c.i32();
  }
#endif
  if (!c.ok || c.p != c.end) return error = "size " + std::to_string(bytes.size()) + " does not match", false;
  out.scale = scale;
  return sums_in_range(out, error);
}

std::vector<std::uint8_t> write_net_file(const NetFile& net) {
  std::vector<std::uint8_t> payload;
  auto put_i16 = [&](std::int16_t v) {
    payload.push_back(static_cast<std::uint8_t>(v));
    payload.push_back(static_cast<std::uint8_t>(static_cast<std::uint16_t>(v) >> 8));
  };
  auto put_i32 = [&](std::int32_t v) { put_u32(payload, static_cast<std::uint32_t>(v)); };
  if constexpr (NetFormatVersion == 2) {
    payload.insert(payload.end(), net.regions, net.regions + 32);
    payload.insert(payload.end(), net.phase_table, net.phase_table + 25);
    payload.resize(NetMapBytes, 0);
  }
  for (int i = 0; i < net.inputs * NetHidden; ++i) put_i16(net.ft_weights[i]);
  for (int i = 0; i < NetHidden; ++i) put_i16(net.ft_bias[i]);
#if FORK_NET_ARCH == 1
  for (int i = 0; i < 2 * NetHidden; ++i) put_i16(net.out_weights[i]);
  put_i32(net.out_bias);
#elif FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3
  for (const auto& row : net.out_weights)
    for (const auto w : row) put_i16(w);
  for (const auto b : net.out_bias) put_i32(b);
#elif FORK_NET_ARCH == 4
  for (const auto& stack : net.af1_weights)
    for (const auto& row : stack)
      for (const auto w : row) payload.push_back(static_cast<std::uint8_t>(w));
  for (const auto& stack : net.af1_bias)
    for (const auto b : stack) put_i32(b);
  for (const auto& stack : net.af2_weights)
    for (const auto& row : stack)
      for (const auto w : row) put_i16(w);
  for (const auto& stack : net.af2_bias)
    for (const auto b : stack) put_i32(b);
  for (const auto& stack : net.af3_weights)
    for (const auto w : stack) put_i16(w);
  for (const auto b : net.af3_bias) put_i32(b);
  put_u64(payload, static_cast<std::uint64_t>(net.output_multiplier));
#elif FORK_NET_ARCH == 5
  for (int f = 0; f < net.inputs; ++f)
    for (int k = 0; k < 3; ++k) put_i16(net.side_weights[f][k]);
  for (int k = 0; k < 3; ++k) put_i16(net.side_bias[k]);
  for (int e = 0; e < 2; ++e) {
    for (const auto w : net.expert_weights[e]) put_i16(w);
    put_i32(net.expert_bias[e]);
  }
#endif

  std::vector<std::uint8_t> out(Magic, Magic + sizeof Magic);
  put_u32(out, NetFormatVersion);
  put_u32(out, static_cast<std::uint32_t>(NetArchitecture));
  put_u32(out, static_cast<std::uint32_t>(net.inputs));
  put_u32(out, NetHidden);
  put_u32(out, static_cast<std::uint32_t>(NetQa));
  put_u32(out, static_cast<std::uint32_t>(NetQb));
  put_u32(out, static_cast<std::uint32_t>(net.scale));
  put_u32(out, NetFormatVersion == 1 ? 0u : static_cast<std::uint32_t>(NetBuckets));
  put_u64(out, net_checksum(payload));
  out.resize(NetHeaderBytes, 0);
  out.insert(out.end(), payload.begin(), payload.end());
  return out;
}

}  // namespace forkeng
