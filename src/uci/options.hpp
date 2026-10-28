// SPDX-License-Identifier: GPL-3.0-or-later

// options: the UCI option table.
//
// Purpose: declare Fork's options, print them for `uci`, and apply
// `setoption` with validation.
// Invariants:
// - Names are declared in exactly the case TCEC types them (runners match
//   names case-sensitively) but looked up case-insensitively, as the spec
//   asks; a name may contain spaces, and runs of whitespace in a sent name
//   match one space.
// - A value is stored only if it is valid for the option (spin within
//   [min, max], check true/false) and the option's handler accepts it;
//   otherwise nothing changes and set() returns the reason.
// - Options are printed in declaration order.
#pragma once

#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace forkeng {

enum class OptionKind : std::uint8_t { Check, Spin, Button, String };

struct OptionEntry {
  std::string name;
  OptionKind kind = OptionKind::Button;
  std::int64_t min = 0, max = 0;  // Spin
  // Current value: the number for Spin and Check (0/1), the text for String.
  std::int64_t number = 0;
  std::string text;
  std::string default_text;  // the printed default
  // Called with the proposed value before it is stored (for a Button, on
  // every press). Returning false rejects it; `message` (if set) is
  // reported either way.
  std::function<bool(const OptionEntry& proposed, std::string& message)> on_set;
};

class OptionTable {
 public:
  void add_check(std::string name, bool value, decltype(OptionEntry::on_set) on_set = nullptr);
  void add_spin(std::string name, std::int64_t value, std::int64_t min, std::int64_t max,
                decltype(OptionEntry::on_set) on_set = nullptr);
  void add_button(std::string name, decltype(OptionEntry::on_set) on_set);
  void add_string(std::string name, std::string value, decltype(OptionEntry::on_set) on_set = nullptr);

  // `option name ...` lines for the uci command.
  std::vector<std::string> option_lines() const;

  // Applies a setoption. `value` is nullopt when the command had no `value`
  // part. Returns false if nothing changed; `message` says why, or carries
  // the handler's report.
  bool set(std::string_view name, std::optional<std::string_view> value, std::string& message);

  const OptionEntry* find(std::string_view name) const;
  std::int64_t number(std::string_view name) const;      // Spin or Check; the name must exist
  const std::string& text(std::string_view name) const;  // String; the name must exist

 private:
  std::vector<OptionEntry> entries_;
};

}  // namespace forkeng
