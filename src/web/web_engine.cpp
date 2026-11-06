// SPDX-License-Identifier: GPL-3.0-or-later

#include "web/web_engine.hpp"

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>
#include <string_view>

#include "core/movegen.hpp"
#include "core/position.hpp"
#include "eval/eval.hpp"
#include "search/hash_memory.hpp"
#include "search/score_bounds.hpp"
#include "search/searcher.hpp"

#if defined(__EMSCRIPTEN__)
#include <emscripten/emscripten.h>
#define FORK_WEB_EXPORT EMSCRIPTEN_KEEPALIVE
// Hands an iteration's line to the page's worker, if it set Module.onIteration.
EM_JS_DEPS(fork_web_iteration_deps, "$UTF8ToString");
EM_JS(void, fork_web_iteration_to_page, (const char* line), {
  if (Module.onIteration) Module.onIteration(UTF8ToString(line));
});
#else
#define FORK_WEB_EXPORT
#endif

namespace forkeng {
namespace {

struct WebEngine {
  HashMemory memory;
  TransTable table;
  std::unique_ptr<Searcher> searcher;
  Position pos;
  std::string text;      // the buffer every text result points into
  std::string san_text;  // fork_web_san's, apart: it may run during a search
};

WebEngine& engine() {
  static WebEngine e;
  return e;
}

// Plays `moves` (UCI, separated by spaces) on `pos`; false at the first
// illegal or malformed move.
bool play_moves(Position& pos, std::string_view moves) {
  std::size_t i = 0;
  while (i < moves.size()) {
    while (i < moves.size() && moves[i] == ' ') ++i;
    std::size_t j = i;
    while (j < moves.size() && moves[j] != ' ') ++j;
    if (j > i) {
      const Move m = pos.parse_uci(moves.substr(i, j - i));
      if (m == NoMove) return false;
      pos.make(m);
    }
    i = j;
  }
  return true;
}

// `m` (legal in `pos`) in standard algebraic notation, then played on `pos`:
// the piece letter (none for a pawn), the origin's file, rank or both when
// another piece of the kind could also go there, "x" for a capture (a pawn
// capture names its file), the destination, "=" and the piece of a
// promotion, and "+" for check or "#" for mate; castling as O-O or O-O-O.
std::string move_san(Position& pos, Move m) {
  const std::string uci = pos.move_to_uci(m);
  const PieceType kind = kind_of(pos.piece_at(m.from()));
  std::string s;
  if (m.is_castle()) {
    s = file_of(m.to()) > file_of(m.from()) ? "O-O" : "O-O-O";
  } else if (kind == Pawn) {
    if (m.is_capture()) s = std::string(1, uci[0]) + 'x';
    s += uci.substr(2, 2);
    if (m.is_promotion()) s += std::string("=") + "NBRQ"[m.promo_type() - Knight];
  } else {
    s = "PNBRQK"[kind];
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    bool rival = false, rival_file = false, rival_rank = false;
    for (const Move o : legal) {
      if (o == m || o.to() != m.to() || o.is_castle() || kind_of(pos.piece_at(o.from())) != kind) continue;
      rival = true;
      rival_file |= file_of(o.from()) == file_of(m.from());
      rival_rank |= rank_of(o.from()) == rank_of(m.from());
    }
    if (rival && (!rival_file || rival_rank)) s += uci[0];
    if (rival && rival_file) s += uci[1];
    if (m.is_capture()) s += 'x';
    s += uci.substr(2, 2);
  }
  pos.make(m);
  if (pos.in_check()) {
    MoveList replies;
    generate<GenMode::Legal>(pos, replies);
    s += replies.size() == 0 ? '#' : '+';
  }
  return s;
}

std::string score_text(int score) {
  return is_mate_score(score) ? "mate " + std::to_string(mate_in_moves(score))
                              : "cp " + std::to_string(score);
}

fork_web_iteration_hook iteration_hook = nullptr;

// The principal variation of the last finished iteration, kept by a
// listener (the search reports each iteration; the last one wins), and
// each finished iteration passed on as it ends.
class LineKeeper final : public SearchListener {
 public:
  void on_iteration(const Position& root, const IterationReport& report) override {
    if (report.bound != 0) return;  // aspiration fails carry no full line
    Position p = root;
    line_.clear();
    for (int i = 0; i < report.pv->length; ++i) {
      const Move m = report.pv->moves[i];
      if (!line_.empty()) line_ += ' ';
      line_ += p.move_to_uci(m);
      p.make(m);
    }
    const std::string text = "depth " + std::to_string(report.depth) + " score " + score_text(report.score) +
                              " nodes " + std::to_string(report.nodes) + " pv " + line_;
#if defined(__EMSCRIPTEN__)
    fork_web_iteration_to_page(text.c_str());
#endif
    if (iteration_hook) iteration_hook(text.c_str());
  }
  const std::string& line() const { return line_; }

 private:
  std::string line_;
};

}  // namespace
}  // namespace forkeng

extern "C" {

FORK_WEB_EXPORT int fork_web_init(int hash_mb) {
  forkeng::init();
  forkeng::WebEngine& e = forkeng::engine();
  std::string report;
  if (hash_mb < 1 || !e.memory.resize(static_cast<std::size_t>(hash_mb) << 20, report)) return 0;
  e.table.bind_memory(e.memory.data(), e.memory.bytes());
  e.searcher = std::make_unique<forkeng::Searcher>(e.table);
  e.memory.clear(1);
  return e.pos.set_fen(forkeng::Position::StartFen) ? 1 : 0;
}

FORK_WEB_EXPORT int fork_web_set_position(const char* fen, const char* moves) {
  forkeng::WebEngine& e = forkeng::engine();
  forkeng::Position p;
  const std::string_view f = fen ? fen : "";
  if (!p.set_fen(f == "startpos" ? forkeng::Position::StartFen : f)) return 0;
  if (!forkeng::play_moves(p, moves ? moves : "")) return 0;
  e.pos = p;
  return 1;
}

FORK_WEB_EXPORT const char* fork_web_fen() {
  forkeng::WebEngine& e = forkeng::engine();
  e.text = e.pos.fen();
  return e.text.c_str();
}

FORK_WEB_EXPORT const char* fork_web_legal_moves() {
  forkeng::WebEngine& e = forkeng::engine();
  forkeng::MoveList legal;
  forkeng::generate<forkeng::GenMode::Legal>(e.pos, legal);
  e.text.clear();
  for (const forkeng::Move m : legal) {
    if (!e.text.empty()) e.text += ' ';
    e.text += e.pos.move_to_uci(m);
  }
  return e.text.c_str();
}

FORK_WEB_EXPORT const char* fork_web_status() {
  forkeng::WebEngine& e = forkeng::engine();
  forkeng::MoveList legal;
  forkeng::generate<forkeng::GenMode::Legal>(e.pos, legal);
  if (legal.size() == 0) return e.pos.in_check() ? "checkmate" : "stalemate";
  if (e.pos.insufficient_material()) return "insufficient";
  if (e.pos.fifty_move_reached()) return "fifty-move";
  if (e.pos.repetition_count() >= 3) return "repetition";
  return "playing";
}

FORK_WEB_EXPORT const char* fork_web_san(const char* fen, const char* moves, const char* line) {
  forkeng::WebEngine& e = forkeng::engine();
  e.san_text.clear();
  forkeng::Position p;
  const std::string_view f = fen ? fen : "";
  if (!p.set_fen(f == "startpos" ? forkeng::Position::StartFen : f)) return e.san_text.c_str();
  if (!forkeng::play_moves(p, moves ? moves : "")) return e.san_text.c_str();
  const std::string_view text = line ? line : "";
  std::size_t i = 0;
  while (i < text.size()) {
    while (i < text.size() && text[i] == ' ') ++i;
    std::size_t j = i;
    while (j < text.size() && text[j] != ' ') ++j;
    if (j == i) break;
    const forkeng::Move m = p.parse_uci(text.substr(i, j - i));
    if (m == forkeng::NoMove) break;
    if (!e.san_text.empty()) e.san_text += ' ';
    e.san_text += forkeng::move_san(p, m);
    i = j;
  }
  return e.san_text.c_str();
}

FORK_WEB_EXPORT int fork_web_evaluate() { return forkeng::static_eval(forkeng::engine().pos); }

FORK_WEB_EXPORT void fork_web_set_iteration_hook(fork_web_iteration_hook hook) { forkeng::iteration_hook = hook; }

FORK_WEB_EXPORT const char* fork_web_search(double nodes) {
  forkeng::WebEngine& e = forkeng::engine();
  if (std::string_view(fork_web_status()) != "playing") {
    e.text = "bestmove none";
    return e.text.c_str();
  }
  forkeng::SearchQuota limits;
  limits.nodes = nodes < 1 ? 1 : static_cast<std::uint64_t>(nodes);
  const std::atomic<bool> stop{false};
  forkeng::LineKeeper keeper;
  const forkeng::SearchResult r = e.searcher->deliberate(e.pos, limits, stop, nullptr, &keeper);
  e.text = "bestmove " + e.pos.move_to_uci(r.best) + " score " + forkeng::score_text(r.score) + " depth " +
           std::to_string(r.depth) + " nodes " + std::to_string(r.nodes);
  if (!keeper.line().empty()) e.text += " pv " + keeper.line();
  return e.text.c_str();
}

FORK_WEB_EXPORT void fork_web_new_game() {
  forkeng::WebEngine& e = forkeng::engine();
  e.memory.clear(1);
  e.searcher->clear_history();
}

}  // extern "C"
