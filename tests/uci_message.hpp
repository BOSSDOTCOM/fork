// uci_message: is a line a well-formed UCI engine-to-GUI message?
//
// Purpose: the one check, shared by the UCI tests (tests/test_uci.cpp) and the
// fuzz target (fuzz/fuzz_uci.cpp), that Fork prints nothing but UCI on stdout.
// Invariants: follows the UCI spec's "Engine to GUI" section as summarized
// in docs/kb/uci.md section 4 (id, uciok, readyok, bestmove, option, info);
// copyprotection and registration are never sent by Fork, so they fail it.
#pragma once

#include <string_view>
#include <vector>

#include "uci/tokens.hpp"

namespace forkeng::test {

inline bool is_move_text(std::string_view m) {
  auto square = [](std::string_view s) { return s[0] >= 'a' && s[0] <= 'h' && s[1] >= '1' && s[1] <= '8'; };
  if (m.size() != 4 && m.size() != 5) return false;
  if (!square(m.substr(0, 2)) || !square(m.substr(2, 2))) return false;
  return m.size() == 4 || std::string_view("nbrq").find(m[4]) != std::string_view::npos;
}

// Is `line` a well-formed engine-to-GUI message (UCI spec, "Engine to GUI")?
inline bool valid_engine_line(std::string_view line) {
  // No control bytes (a NUL can cut a GUI's line short; CR or LF would split it).
  for (char c : line)
    if ((static_cast<unsigned char>(c) < 0x20 && c != '\t') || c == 0x7f) return false;
  const std::vector<LineToken> t = split_tokens(line);
  if (t.empty()) return false;
  const std::string_view cmd = t[0].text;
  if (cmd == "uciok" || cmd == "readyok") return t.size() == 1;
  if (cmd == "id") return t.size() >= 3 && (t[1].text == "name" || t[1].text == "author");
  if (cmd == "bestmove") {
    if (t.size() != 2 && t.size() != 4) return false;
    if (t[1].text != "(none)" && !is_move_text(t[1].text)) return false;
    return t.size() == 2 || (t[2].text == "ponder" && is_move_text(t[3].text));
  }
  if (cmd == "option") {
    if (t.size() < 5 || t[1].text != "name") return false;
    for (std::size_t i = 2; i + 1 < t.size(); ++i)
      if (t[i].text == "type") {
        const std::string_view type = t[i + 1].text;
        return type == "check" || type == "spin" || type == "combo" || type == "button" || type == "string";
      }
    return false;
  }
  if (cmd == "info") return t.size() >= 2;
  return false;
}

}  // namespace forkeng::test
