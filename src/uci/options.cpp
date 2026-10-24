#include "uci/options.hpp"

#include <cassert>
#include <utility>

#include "uci/tokens.hpp"

namespace forkeng {

namespace {

// Lower-case ASCII with whitespace runs folded to one space, for matching
// names the way a GUI may type them.
std::string name_key(std::string_view name) {
  std::string key;
  for (const LineToken& t : split_tokens(name)) {
    if (!key.empty()) key += ' ';
    for (char c : t.text) key += (c >= 'A' && c <= 'Z') ? static_cast<char>(c - 'A' + 'a') : c;
  }
  return key;
}

}  // namespace

void OptionTable::add_check(std::string name, bool value, decltype(OptionEntry::on_set) on_set) {
  OptionEntry e;
  e.name = std::move(name);
  e.kind = OptionKind::Check;
  e.number = value;
  e.default_text = value ? "true" : "false";
  e.on_set = std::move(on_set);
  entries_.push_back(std::move(e));
}

void OptionTable::add_spin(std::string name, std::int64_t value, std::int64_t min, std::int64_t max,
                           decltype(OptionEntry::on_set) on_set) {
  assert(min <= value && value <= max);
  OptionEntry e;
  e.name = std::move(name);
  e.kind = OptionKind::Spin;
  e.min = min;
  e.max = max;
  e.number = value;
  e.default_text = std::to_string(value);
  e.on_set = std::move(on_set);
  entries_.push_back(std::move(e));
}

void OptionTable::add_button(std::string name, decltype(OptionEntry::on_set) on_set) {
  OptionEntry e;
  e.name = std::move(name);
  e.kind = OptionKind::Button;
  e.on_set = std::move(on_set);
  entries_.push_back(std::move(e));
}

void OptionTable::add_string(std::string name, std::string value, decltype(OptionEntry::on_set) on_set) {
  OptionEntry e;
  e.name = std::move(name);
  e.kind = OptionKind::String;
  e.default_text = value.empty() ? "<empty>" : value;
  e.text = std::move(value);
  e.on_set = std::move(on_set);
  entries_.push_back(std::move(e));
}

std::vector<std::string> OptionTable::option_lines() const {
  std::vector<std::string> lines;
  for (const OptionEntry& e : entries_) {
    std::string line = "option name " + e.name + " type ";
    switch (e.kind) {
      case OptionKind::Check:
        line += "check default " + e.default_text;
        break;
      case OptionKind::Spin:
        line += "spin default " + e.default_text + " min " + std::to_string(e.min) + " max " +
                std::to_string(e.max);
        break;
      case OptionKind::Button:
        line += "button";
        break;
      case OptionKind::String:
        line += "string default " + e.default_text;
        break;
    }
    lines.push_back(std::move(line));
  }
  return lines;
}

const OptionEntry* OptionTable::find(std::string_view name) const {
  const std::string key = name_key(name);
  for (const OptionEntry& e : entries_)
    if (name_key(e.name) == key) return &e;
  return nullptr;
}

std::int64_t OptionTable::number(std::string_view name) const {
  const OptionEntry* e = find(name);
  assert(e && (e->kind == OptionKind::Spin || e->kind == OptionKind::Check));
  return e ? e->number : 0;
}

const std::string& OptionTable::text(std::string_view name) const {
  static const std::string none;
  const OptionEntry* e = find(name);
  assert(e && e->kind == OptionKind::String);
  return e ? e->text : none;
}

bool OptionTable::set(std::string_view name, std::optional<std::string_view> value, std::string& message) {
  const OptionEntry* found = find(name);
  if (!found) {
    message = "unknown option: " + std::string(name);
    return false;
  }
  OptionEntry& e = entries_[static_cast<std::size_t>(found - entries_.data())];
  OptionEntry proposed = e;
  proposed.on_set = nullptr;
  switch (e.kind) {
    case OptionKind::Button:
      break;  // a value, if any, is ignored
    case OptionKind::Check:
      if (value && iequals(*value, "true")) {
        proposed.number = 1;
      } else if (value && iequals(*value, "false")) {
        proposed.number = 0;
      } else {
        message = e.name + ": expected true or false";
        return false;
      }
      break;
    case OptionKind::Spin: {
      const std::optional<std::int64_t> n = value ? parse_int64(*value) : std::nullopt;
      if (!n || *n < e.min || *n > e.max) {
        message = e.name + ": expected an integer from " + std::to_string(e.min) + " to " +
                  std::to_string(e.max) +
                  (value ? ", got '" + std::string(*value) + "'" : std::string(", got no value"));
        return false;
      }
      proposed.number = *n;
      break;
    }
    case OptionKind::String:
      if (!value) {
        message = e.name + ": no value given";
        return false;
      }
      proposed.text = iequals(*value, "<empty>") ? std::string() : std::string(*value);
      break;
  }
  if (e.on_set && !e.on_set(proposed, message)) return false;
  e.number = proposed.number;
  e.text = std::move(proposed.text);
  return true;
}

}  // namespace forkeng
