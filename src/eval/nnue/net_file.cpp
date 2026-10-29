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

std::int16_t get_i16(const std::uint8_t* p) { return static_cast<std::int16_t>(p[0] | (p[1] << 8)); }

// The overflow bounds of the header comment; false names the first broken one.
bool sums_in_range(const NetFile& net, std::string& error) {
  for (int j = 0; j < NetHidden; ++j) {
    int largest = 0;
    for (int f = 0; f < NetInputs; ++f)
      largest = std::max(largest, std::abs(int{net.ft_weights[f * NetHidden + j]}));
    if (std::abs(int{net.ft_bias[j]}) + 32 * largest > std::numeric_limits<std::int16_t>::max()) {
      error = "hidden unit " + std::to_string(j) + " can leave the int16 range";
      return false;
    }
  }
  std::int64_t total = 0;
  for (int i = 0; i < 2 * NetHidden; ++i) total += std::abs(int{net.out_weights[i]});
  if (NetQa * total + std::abs(std::int64_t{net.out_bias}) > std::numeric_limits<std::int32_t>::max()) {
    error = "the output layer can leave the int32 range";
    return false;
  }
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
  if (bytes.size() != NetHeaderBytes + NetPayloadBytes) {
    error = "size " + std::to_string(bytes.size()) + ", expected " +
            std::to_string(NetHeaderBytes + NetPayloadBytes);
    return false;
  }
  const std::uint8_t* h = bytes.data();
  if (std::memcmp(h, Magic, sizeof Magic) != 0) return error = "not a Fork net file", false;
  if (get_u32(h + 8) != NetFormatVersion) return error = "unknown format version", false;
  if (get_u32(h + 12) != NetArchitectureB0) return error = "unknown architecture", false;
  if (get_u32(h + 16) != NetInputs || get_u32(h + 20) != NetHidden) return error = "wrong layer sizes", false;
  if (static_cast<std::int32_t>(get_u32(h + 24)) != NetQa ||
      static_cast<std::int32_t>(get_u32(h + 28)) != NetQb)
    return error = "wrong quantization factors", false;
  const auto scale = static_cast<std::int32_t>(get_u32(h + 32));
  if (scale < 1 || scale > 100000) return error = "output scale out of range", false;
  if (get_u32(h + 36) != 0) return error = "nonzero reserved header bytes", false;
  for (std::size_t i = 48; i < NetHeaderBytes; ++i)
    if (h[i] != 0) return error = "nonzero reserved header bytes", false;
  const std::span<const std::uint8_t> payload = bytes.subspan(NetHeaderBytes);
  if (net_checksum(payload) != get_u64(h + 40)) return error = "checksum mismatch", false;

  const std::uint8_t* p = payload.data();
  for (int i = 0; i < NetInputs * NetHidden; ++i, p += 2) out.ft_weights[i] = get_i16(p);
  for (int i = 0; i < NetHidden; ++i, p += 2) out.ft_bias[i] = get_i16(p);
  for (int i = 0; i < 2 * NetHidden; ++i, p += 2) out.out_weights[i] = get_i16(p);
  out.out_bias = static_cast<std::int32_t>(get_u32(p));
  out.scale = scale;
  return sums_in_range(out, error);
}

std::vector<std::uint8_t> write_net_file(const NetFile& net) {
  std::vector<std::uint8_t> payload;
  payload.reserve(NetPayloadBytes);
  auto put_i16 = [&](std::int16_t v) {
    payload.push_back(static_cast<std::uint8_t>(v));
    payload.push_back(static_cast<std::uint8_t>(static_cast<std::uint16_t>(v) >> 8));
  };
  for (int i = 0; i < NetInputs * NetHidden; ++i) put_i16(net.ft_weights[i]);
  for (int i = 0; i < NetHidden; ++i) put_i16(net.ft_bias[i]);
  for (int i = 0; i < 2 * NetHidden; ++i) put_i16(net.out_weights[i]);
  put_u32(payload, static_cast<std::uint32_t>(net.out_bias));

  std::vector<std::uint8_t> out(Magic, Magic + sizeof Magic);
  put_u32(out, NetFormatVersion);
  put_u32(out, NetArchitectureB0);
  put_u32(out, NetInputs);
  put_u32(out, NetHidden);
  put_u32(out, static_cast<std::uint32_t>(NetQa));
  put_u32(out, static_cast<std::uint32_t>(NetQb));
  put_u32(out, static_cast<std::uint32_t>(net.scale));
  put_u32(out, 0);
  put_u64(out, net_checksum(payload));
  out.resize(NetHeaderBytes, 0);
  out.insert(out.end(), payload.begin(), payload.end());
  return out;
}

}  // namespace forkeng
