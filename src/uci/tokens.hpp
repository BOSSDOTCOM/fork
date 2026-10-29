// SPDX-License-Identifier: GPL-3.0-or-later

// tokens: splitting a UCI input line into words, and reading numbers.
//
// Purpose: the one tokenizer and number parser every command parser uses,
// so whitespace and number rules are the same everywhere.
// Invariants:
// - Tokens are maximal runs of non-whitespace bytes; whitespace is space, tab,
//   CR, LF, VT and FF (UCI allows any amount of spaces and tabs between
//   tokens, and a stray CR from a Windows GUI must not stick to a token).
// - Each token keeps its byte offset in the line, so a parser can take "the
//   rest of the line" verbatim (setoption values keep their inner spacing).
// - Every byte value is accepted; nothing here allocates per byte or throws
//   except std::bad_alloc from the token vector.
#pragma once

#include <charconv>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <string_view>
#include <vector>

namespace forkeng {

struct LineToken {
  std::string_view text;
  std::size_t offset;  // of text[0] in the line
};

constexpr bool is_uci_space(char c) {
  return c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\v' || c == '\f';
}

inline std::vector<LineToken> split_tokens(std::string_view line) {
  std::vector<LineToken> tokens;
  std::size_t i = 0;
  while (i < line.size()) {
    while (i < line.size() && is_uci_space(line[i])) ++i;
    std::size_t j = i;
    while (j < line.size() && !is_uci_space(line[j])) ++j;
    if (j > i) tokens.push_back({line.substr(i, j - i), i});
    i = j;
  }
  return tokens;
}

// ASCII case-insensitive comparison (option names, keywords).
constexpr bool iequals(std::string_view a, std::string_view b) {
  if (a.size() != b.size()) return false;
  for (std::size_t i = 0; i < a.size(); ++i) {
    char x = a[i], y = b[i];
    if (x >= 'A' && x <= 'Z') x = static_cast<char>(x - 'A' + 'a');
    if (y >= 'A' && y <= 'Z') y = static_cast<char>(y - 'A' + 'a');
    if (x != y) return false;
  }
  return true;
}

// A decimal integer with an optional sign. Values beyond the 64-bit range
// clamp to it; anything else that is not a number gives nullopt.
inline std::optional<std::int64_t> parse_int64(std::string_view s) {
  bool negative = false;
  if (!s.empty() && (s[0] == '+' || s[0] == '-')) {
    negative = s[0] == '-';
    s.remove_prefix(1);
  }
  if (s.empty() || s[0] < '0' || s[0] > '9') return std::nullopt;
  std::uint64_t magnitude = 0;
  auto [end, ec] = std::from_chars(s.data(), s.data() + s.size(), magnitude);
  // On overflow from_chars still consumes every digit, so anything left over
  // is junk ("12ab").
  if (end != s.data() + s.size()) return std::nullopt;
  const auto max = static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());
  if (ec == std::errc::result_out_of_range || magnitude > max)
    return negative ? std::numeric_limits<std::int64_t>::min() : std::numeric_limits<std::int64_t>::max();
  return negative ? -static_cast<std::int64_t>(magnitude) : static_cast<std::int64_t>(magnitude);
}

// The line from `from` to its end, without trailing whitespace.
inline std::string_view rest_of_line(std::string_view line, std::size_t from) {
  std::string_view rest = line.substr(from < line.size() ? from : line.size());
  while (!rest.empty() && is_uci_space(rest.back())) rest.remove_suffix(1);
  return rest;
}

}  // namespace forkeng
