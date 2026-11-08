// SPDX-License-Identifier: GPL-3.0-or-later

#include "eval/nnue/refiner_file.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>

#include "eval/eval_scale.hpp"
#include "eval/nnue/net_file.hpp"

namespace forkeng {

namespace {

constexpr char RefinerMagic[8] = {'F', 'O', 'R', 'K', 'R', 'F', 'N', 0};

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
};

// Whether every layer's worst-case sum stays within int32 (refiner_file.hpp).
bool sums_in_range(const RefinerFile& r) {
  for (int o = 0; o < RefinerL1Width; ++o) {
    std::int64_t dense = 0;
    for (const std::int8_t w : r.entry_weights[o]) dense += NetQa * std::int64_t{std::abs(w)};
    // The largest RefinerMaxActive row values of this unit.
    std::int64_t rows[RefinerRows];
    for (int i = 0; i < RefinerRows; ++i) rows[i] = std::abs(std::int64_t{r.row_weights[i][o]});
    std::partial_sort(rows, rows + RefinerMaxActive, rows + RefinerRows,
                      [](auto a, auto b) { return a > b; });
    std::int64_t active = 0;
    for (int i = 0; i < RefinerMaxActive; ++i) active += rows[i];
    if (std::abs(std::int64_t{r.entry_bias[o]}) + dense + active > std::numeric_limits<std::int32_t>::max())
      return false;
  }
  for (int m = 0; m < RefinerL2Width; ++m) {
    std::int64_t dense = 0;
    for (const std::int8_t w : r.middle_weights[m]) dense += NetQa * std::int64_t{std::abs(w)};
    if (std::abs(std::int64_t{r.middle_bias[m]}) + dense > std::numeric_limits<std::int32_t>::max())
      return false;
  }
  for (int h = 0; h < RefinerHeads; ++h) {
    std::int64_t dense = 0;
    for (const std::int16_t w : r.head_weights[h]) dense += NetQa * std::int64_t{std::abs(w)};
    if (std::abs(std::int64_t{r.head_bias[h]}) + dense > std::numeric_limits<std::int32_t>::max())
      return false;
  }
  return true;
}

}  // namespace

bool read_refiner_file(std::span<const std::uint8_t> bytes, RefinerFile& out, std::string& error) {
  if (bytes.size() < NetHeaderBytes) return error = "shorter than a header", false;
  const std::uint8_t* h = bytes.data();
  if (std::memcmp(h, RefinerMagic, sizeof RefinerMagic) != 0) return error = "not a Fork refiner file", false;
  if (get_u32(h + 8) != RefinerFormatVersion) return error = "unknown format version", false;
  if (get_u32(h + 12) != static_cast<std::uint32_t>(RefinerArchitecture))
    return error = "refiner architecture " + std::to_string(get_u32(h + 12)) + ", this build reads " +
                   std::to_string(RefinerArchitecture),
           false;
  if (get_u32(h + 16) != static_cast<std::uint32_t>(RefinerL1Width) ||
      get_u32(h + 20) != static_cast<std::uint32_t>(RefinerL2Width) ||
      get_u32(h + 24) != static_cast<std::uint32_t>(RefinerHeads))
    return error = "wrong layer sizes", false;
  const auto scale = static_cast<std::int32_t>(get_u32(h + 28));
  if (scale < 1 || scale > 100000) return error = "output scale out of range", false;
  const auto cap = static_cast<std::int32_t>(get_u32(h + 32));
  if (cap < 0 || cap > EvalLimit) return error = "cap out of range", false;
  if (get_u32(h + 36) != static_cast<std::uint32_t>(RefinerDenseBound))
    return error = "dense-weight bound " + std::to_string(get_u32(h + 36)) + ", this build reads " +
                   std::to_string(RefinerDenseBound),
           false;
  for (std::size_t i = 56; i < NetHeaderBytes; ++i)
    if (h[i] != 0) return error = "nonzero reserved header bytes", false;
  const std::span<const std::uint8_t> payload = bytes.subspan(NetHeaderBytes);
  if (net_checksum(payload) != get_u64(h + 40)) return error = "checksum mismatch", false;

  Cursor c{payload.data(), payload.data() + payload.size()};
  for (auto& row : out.entry_weights)
    for (auto& w : row) w = c.i8();
  for (auto& b : out.entry_bias) b = c.i32();
  for (auto& row : out.row_weights)
    for (auto& w : row) w = NetQa * c.i16();
  for (auto& row : out.middle_weights)
    for (auto& w : row) w = c.i8();
  for (auto& b : out.middle_bias) b = c.i32();
  for (auto& row : out.head_weights)
    for (auto& w : row) w = c.i16();
  for (auto& b : out.head_bias) b = c.i32();
  if (!c.ok) return error = "payload too short", false;
  if (c.p != c.end) return error = "payload too long", false;
  out.scale = scale;
  out.cap = cap;
  out.base_checksum = get_u64(h + 48);
  auto in_bound = [](const auto& table) {
    return std::all_of(&table[0][0], &table[0][0] + sizeof table,
                       [](std::int8_t v) { return v >= -RefinerDenseBound && v <= RefinerDenseBound; });
  };
  if (!in_bound(out.entry_weights) || !in_bound(out.middle_weights))
    return error = "a dense weight outside [-" + std::to_string(RefinerDenseBound) + ", " +
                   std::to_string(RefinerDenseBound) + "]",
           false;
  if (!sums_in_range(out)) return error = "weights could overflow a layer's sum", false;
  return true;
}

std::vector<std::uint8_t> write_refiner_file(const RefinerFile& r) {
  std::vector<std::uint8_t> payload;
  auto put_i16 = [&](std::int32_t v) {
    payload.push_back(static_cast<std::uint8_t>(v));
    payload.push_back(static_cast<std::uint8_t>(v >> 8));
  };
  auto put_i32 = [&](std::int32_t v) { put_u32(payload, static_cast<std::uint32_t>(v)); };
  for (const auto& row : r.entry_weights)
    for (const auto w : row) payload.push_back(static_cast<std::uint8_t>(w));
  for (const auto b : r.entry_bias) put_i32(b);
  for (const auto& row : r.row_weights)
    for (const auto w : row) put_i16(w / NetQa);
  for (const auto& row : r.middle_weights)
    for (const auto w : row) payload.push_back(static_cast<std::uint8_t>(w));
  for (const auto b : r.middle_bias) put_i32(b);
  for (const auto& row : r.head_weights)
    for (const auto w : row) put_i16(w);
  for (const auto b : r.head_bias) put_i32(b);

  std::vector<std::uint8_t> out(RefinerMagic, RefinerMagic + sizeof RefinerMagic);
  put_u32(out, RefinerFormatVersion);
  put_u32(out, static_cast<std::uint32_t>(RefinerArchitecture));
  put_u32(out, static_cast<std::uint32_t>(RefinerL1Width));
  put_u32(out, static_cast<std::uint32_t>(RefinerL2Width));
  put_u32(out, static_cast<std::uint32_t>(RefinerHeads));
  put_u32(out, static_cast<std::uint32_t>(r.scale));
  put_u32(out, static_cast<std::uint32_t>(r.cap));
  put_u32(out, static_cast<std::uint32_t>(RefinerDenseBound));
  put_u64(out, net_checksum(payload));
  put_u64(out, r.base_checksum);
  out.resize(NetHeaderBytes, 0);
  out.insert(out.end(), payload.begin(), payload.end());
  return out;
}

}  // namespace forkeng
