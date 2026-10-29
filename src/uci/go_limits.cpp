// SPDX-License-Identifier: GPL-3.0-or-later

#include "uci/go_limits.hpp"

#include <algorithm>

namespace forkeng {

namespace {

constexpr std::string_view Keywords[] = {"searchmoves", "ponder", "wtime", "btime", "winc",     "binc",
                                         "movestogo",   "depth",  "nodes", "mate",  "movetime", "infinite"};

bool is_keyword(std::string_view t) { return std::ranges::find(Keywords, t) != std::end(Keywords); }

}  // namespace

Move parse_uci_move(const Position& pos, std::string_view text) {
  if (text.size() != 4 && text.size() != 5) return NoMove;
  std::string s(text);
  if (s.size() == 5 && s[4] >= 'A' && s[4] <= 'Z') s[4] = static_cast<char>(s[4] - 'A' + 'a');
  return pos.parse_uci(s);
}

GoLimits parse_go(const std::vector<LineToken>& tokens, std::size_t first, const Position& pos,
                  std::vector<std::string>& warnings) {
  GoLimits g;
  std::size_t i = first;
  auto number = [&](std::optional<std::int64_t>& slot, std::string_view name) {
    if (i + 1 >= tokens.size()) {
      warnings.push_back("go: " + std::string(name) + " without a value");
      return;
    }
    std::optional<std::int64_t> v = parse_int64(tokens[i + 1].text);
    if (!v) {
      warnings.push_back("go: bad value for " + std::string(name) + ": " + std::string(tokens[i + 1].text));
      if (is_keyword(tokens[i + 1].text)) return;  // let the next keyword be parsed
    } else {
      slot = v;
    }
    ++i;
  };
  for (; i < tokens.size(); ++i) {
    std::string_view t = tokens[i].text;
    if (t == "searchmoves") {
      g.restrict_sent = true;
      while (i + 1 < tokens.size() && !is_keyword(tokens[i + 1].text)) {
        ++i;
        Move m = parse_uci_move(pos, tokens[i].text);
        if (m.is_none())
          warnings.push_back("go: searchmoves: not a legal move: " + std::string(tokens[i].text));
        else if (std::ranges::find(g.restrict_to, m) == g.restrict_to.end())
          g.restrict_to.push_back(m);
      }
    } else if (t == "ponder") {
      g.ponder = true;
    } else if (t == "infinite") {
      g.infinite = true;
    } else if (t == "wtime") {
      number(g.remaining_ms[White], t);
    } else if (t == "btime") {
      number(g.remaining_ms[Black], t);
    } else if (t == "winc") {
      number(g.increment_ms[White], t);
    } else if (t == "binc") {
      number(g.increment_ms[Black], t);
    } else if (t == "movestogo") {
      number(g.movestogo, t);
    } else if (t == "depth") {
      number(g.depth, t);
    } else if (t == "nodes") {
      number(g.nodes, t);
    } else if (t == "mate") {
      number(g.mate, t);
    } else if (t == "movetime") {
      number(g.movetime, t);
    } else {
      warnings.push_back("go: unknown token: " + std::string(t));
    }
  }
  return g;
}

}  // namespace forkeng
