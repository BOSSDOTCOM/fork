// uci_message: is a line a well-formed UCI engine-to-GUI message?
//
// Purpose: the one check, shared by the UCI tests (tests/test_uci.cpp) and the
// fuzz target (fuzz/fuzz_uci.cpp), that Fork prints nothing but UCI on stdout;
// and, for the UCI tests, whether a search's info and bestmove lines make
// sense for the position the search was given (audit-1 Q-2).
// Invariants: follows the UCI spec's "Engine to GUI" section as summarized
// in docs/kb/uci.md section 4 (id, uciok, readyok, bestmove, option, info);
// copyprotection and registration are never sent by Fork, so they fail it.
// Move texts are matched against names built here from each legal move's
// squares, never with Fork's own move printers.
#pragma once

#include <cstdlib>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "core/movegen.hpp"
#include "core/position.hpp"
#include "search/score_bounds.hpp"
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

// The legal move of `pos` whose UCI text is `text`, or NoMove. Each legal
// move's text is built here from its squares: a castling move (stored king to
// rook) as the king's two-square step, the UCI spec's notation; a promotion
// with its lower-case letter. Independent of Position::move_to_uci and of the
// session's own printer (src/uci/session.cpp).
inline Move legal_move_named(const Position& pos, std::string_view text) {
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  for (Move m : legal) {
    const Square from = m.from();
    Square to = m.to();
    if (m.is_castle())
      to = make_square(file_of(from) + (file_of(to) > file_of(from) ? 2 : -2), rank_of(from));
    std::string name{static_cast<char>('a' + file_of(from)), static_cast<char>('1' + rank_of(from)),
                     static_cast<char>('a' + file_of(to)), static_cast<char>('1' + rank_of(to))};
    if (m.is_promotion()) name += "nbrq"[m.promo_type() - Knight];
    if (name == text) return m;
  }
  return NoMove;
}

// What is wrong with a search's output line for the position `root` that the
// search was given (empty: nothing; other lines always pass):
// - bestmove: a legal move, "(none)" exactly when there is none, and a
//   ponder move legal after it;
// - info: every pv move legal in turn; "score cp" below the mate band,
//   "score mate N" within MaxPly / 2 moves; on an exact line (no
//   lowerbound/upperbound) with a pv, "mate N" means the pv ends in
//   checkmate after exactly 2N - 1 plies (N > 0) or 2|N| plies (N < 0), and
//   "mate 0" means the root itself is checkmated.
inline std::string search_line_problem(const Position& root, std::string_view line) {
  const std::vector<LineToken> t = split_tokens(line);
  if (t.empty()) return "";
  if (t[0].text == "bestmove") {
    if (t.size() < 2) return "bestmove without a move";
    MoveList legal;
    generate<GenMode::Legal>(root, legal);
    if (t[1].text == "(none)") return legal.size() == 0 ? "" : "bestmove (none), but there are legal moves";
    const Move m = legal_move_named(root, t[1].text);
    if (m.is_none()) return "bestmove " + std::string(t[1].text) + " is not a legal move";
    if (t.size() >= 4 && t[2].text == "ponder") {
      Position after = root;
      after.make(m);
      if (legal_move_named(after, t[3].text).is_none())
        return "ponder " + std::string(t[3].text) + " is not legal after the bestmove";
    }
    return "";
  }
  if (t[0].text != "info" || (t.size() > 1 && t[1].text == "string")) return "";
  Position pos = root;
  int plies = 0;
  bool exact = true, has_pv = false;
  std::optional<std::int64_t> mate;
  for (std::size_t i = 1; i < t.size(); ++i) {
    const std::string_view key = t[i].text;
    if (key == "lowerbound" || key == "upperbound") {
      exact = false;
    } else if (key == "score") {
      if (i + 2 >= t.size()) return "score without a kind and a value";
      const std::optional<std::int64_t> v = parse_int64(t[i + 2].text);
      if (!v) return "score without a number";
      if (t[i + 1].text == "mate") {
        if (std::abs(*v) > MaxPly / 2)
          return "score mate " + std::to_string(*v) + " is beyond MaxPly / 2 moves";
        mate = *v;
      } else if (t[i + 1].text == "cp") {
        if (std::abs(*v) >= MateScore - MaxPly)
          return "score cp " + std::to_string(*v) + " is in the mate band";
      } else {
        return "score of an unknown kind: " + std::string(t[i + 1].text);
      }
      i += 2;
    } else if (key == "pv") {
      has_pv = true;
      for (++i; i < t.size(); ++i) {
        const Move m = legal_move_named(pos, t[i].text);
        if (m.is_none())
          return "pv move " + std::string(t[i].text) + " is not legal after " + std::to_string(plies) +
                 " plies";
        pos.make(m);
        ++plies;
      }
    }
  }
  if (!mate || !exact) return "";
  MoveList left;
  if (*mate == 0) {
    generate<GenMode::Legal>(root, left);
    return left.size() == 0 && root.in_check() ? "" : "score mate 0, but the root is not checkmated";
  }
  if (!has_pv) return "";
  const std::int64_t want = *mate > 0 ? 2 * *mate - 1 : -2 * *mate;
  generate<GenMode::Legal>(pos, left);
  if (plies != want || left.size() != 0 || !pos.in_check())
    return "score mate " + std::to_string(*mate) + ", but the pv (" + std::to_string(plies) +
           " plies) does not end in checkmate after " + std::to_string(want) + " plies";
  return "";
}

}  // namespace forkeng::test
