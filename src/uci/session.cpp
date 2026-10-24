#include "uci/session.hpp"

#include <algorithm>
#include <chrono>
#include <exception>
#include <sstream>
#include <system_error>
#include <utility>

#include "core/movegen.hpp"
#include "core/perft.hpp"
#include "uci/placeholder.hpp"

namespace forkeng {

namespace {

constexpr std::string_view Commands[] = {"uci",        "debug",    "isready", "setoption", "register",
                                         "ucinewgame", "position", "go",      "stop",      "ponderhit",
                                         "quit",       "d",        "bench"};

bool is_command(std::string_view t) {
  return std::find(std::begin(Commands), std::end(Commands), t) != std::end(Commands);
}

std::string hex16(std::uint64_t v) {
  char buf[17];
  std::snprintf(buf, sizeof buf, "%016llx", static_cast<unsigned long long>(v));
  return buf;
}

std::int64_t ms_since(std::chrono::steady_clock::time_point start) {
  return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start)
      .count();
}

}  // namespace

UciSession::UciSession(OutputChannel& out, SessionConfig config) : out_(out), config_(config) {}

UciSession::~UciSession() {
  try {
    stop_search();
  } catch (...) {  // nothing may escape a destructor; join failing means no thread is left to join
  }
}

int UciSession::run(std::FILE* in) {
  std::string line;
  for (;;) {
    const int c = std::getc(in);
    if (c == EOF) break;
    if (c == '\n' || c == '\r') {
      if (!line.empty() && !handle_line(line)) return 0;
      line.clear();
    } else {
      line.push_back(static_cast<char>(c));
    }
  }
  // End of input: a last line without a terminator still counts, then the
  // same as quit.
  if (!line.empty()) handle_line(line);
  stop_search();
  return 0;
}

bool UciSession::handle_line(std::string_view line) {
  try {
    out_.log_input(line);
    const std::vector<LineToken> tokens = split_tokens(line);
    // The spec: unknown tokens before a command are skipped.
    std::size_t i = 0;
    while (i < tokens.size() && !is_command(tokens[i].text)) ++i;
    if (i == tokens.size()) {
#ifdef FORK_DEBUG
      if (!tokens.empty()) out_.send_info_string("unknown command: " + std::string(rest_of_line(line, 0)));
#endif
      return true;
    }
    if (tokens[i].text == "quit") {
      stop_search();
      return false;
    }
    dispatch(tokens, i, line);
  } catch (const std::exception& e) {
    out_.send_info_string(std::string("error: ") + e.what());
  }
  return true;
}

void UciSession::dispatch(const std::vector<LineToken>& tokens, std::size_t first, std::string_view line) {
  (void)line;
  const std::string_view cmd = tokens[first].text;
  if (cmd == "uci") {
    cmd_uci();
  } else if (cmd == "isready") {
    cmd_isready();
  } else if (cmd == "stop") {
    stop_search();
  } else if (cmd == "ponderhit") {
    cmd_ponderhit();
  } else if (cmd == "d") {
    cmd_board();
  } else if (cmd == "debug" || cmd == "register") {
    // Accepted and ignored.
  } else {
    // Everything else changes what a search depends on.
    stop_search();
    if (cmd == "position") {
      cmd_position(tokens, first + 1);
    } else if (cmd == "go") {
      cmd_go(tokens, first + 1);
    } else if (cmd == "bench") {
      cmd_bench();
    } else if (cmd == "setoption") {
      out_.send_info_string("no options yet");
    } else if (cmd == "ucinewgame") {
      // Nothing to clear yet.
    }
  }
}

void UciSession::cmd_uci() {
  out_.send_line(std::string("id name Fork ") + engine_version());
  out_.send_line("id author BOSSDOTCOM");
  out_.send_line("uciok");
}

void UciSession::cmd_isready() {
  if (!search_running()) stop_search();  // joins a search that already printed bestmove
  out_.send_line("readyok");
}

void UciSession::cmd_ponderhit() {
  {
    std::lock_guard<std::mutex> lock(signals_.mutex);
    signals_.ponder = false;
  }
  signals_.wake.notify_all();
}

void UciSession::cmd_position(const std::vector<LineToken>& tokens, std::size_t first) {
  Position pos;
  std::size_t i = first;
  if (i < tokens.size() && tokens[i].text == "startpos") {
    ++i;
  } else if (i < tokens.size() && tokens[i].text == "fen") {
    std::string fen;
    for (++i; i < tokens.size() && tokens[i].text != "moves"; ++i) (fen += tokens[i].text) += ' ';
    std::string error;
    if (!pos.set_fen(fen, &error)) {
      out_.send_info_string("invalid FEN, position unchanged: " + error);
      return;
    }
  } else {
    out_.send_info_string("position: expected startpos or fen; position unchanged");
    return;
  }
  while (i < tokens.size() && tokens[i].text != "moves") ++i;
  for (++i; i < tokens.size(); ++i) {
    const Move m = parse_uci_move(pos, tokens[i].text);
    if (m.is_none()) {
      out_.send_info_string("illegal move " + std::string(tokens[i].text) + "; position kept before it");
      break;
    }
    pos.make(m);
  }
  root_ = std::move(pos);
}

void UciSession::cmd_go(const std::vector<LineToken>& tokens, std::size_t first) {
  if (first < tokens.size() && tokens[first].text == "perft") {
    cmd_perft(tokens, first + 1);
    return;
  }
  std::vector<std::string> warnings;
  const GoLimits limits = parse_go(tokens, first, root_, warnings);
  for (const std::string& w : warnings) out_.send_info_string(w);
  if (limits.restrict_sent && limits.restrict_to.empty())
    out_.send_info_string("go: no legal move in searchmoves; searching every move");
  {
    std::lock_guard<std::mutex> lock(signals_.mutex);
    signals_.stop = false;
    signals_.ponder = limits.ponder;
    signals_.finished = false;
  }
  try {
    search_thread_ = std::thread(&UciSession::search_main, this, root_, limits);
  } catch (const std::system_error& e) {
    // No thread: answer at once on this one, so the go still gets its bestmove.
    out_.send_info_string(std::string("cannot start the search thread: ") + e.what());
    {
      std::lock_guard<std::mutex> lock(signals_.mutex);
      signals_.stop = true;
    }
    search_main(root_, limits);
  }
}

bool UciSession::search_running() {
  std::lock_guard<std::mutex> lock(signals_.mutex);
  return search_thread_.joinable() && !signals_.finished;
}

void UciSession::stop_search() {
  if (!search_thread_.joinable()) return;
  {
    std::lock_guard<std::mutex> lock(signals_.mutex);
    signals_.stop = true;
  }
  signals_.wake.notify_all();
  search_thread_.join();
}

void UciSession::search_main(Position pos, GoLimits limits) {
  const auto start = std::chrono::steady_clock::now();
  Move best = NoMove;
  std::uint64_t nodes = 1;
  bool sent = false;
  try {
    const PlaceholderPick pick = pick_placeholder_move(pos, limits.restrict_to);
    best = pick.move;
    nodes = pick.nodes;
    const bool waits = limits.infinite || limits.ponder;
    if (waits) report_search(pos, best, nodes, ms_since(start));
    {
      std::unique_lock<std::mutex> lock(signals_.mutex);
      signals_.wake.wait(lock, [&] { return signals_.stop || (!limits.infinite && !signals_.ponder); });
    }
    report_search(pos, best, nodes, ms_since(start));
    sent = true;
    out_.send_line("bestmove " + (best.is_none() ? std::string("(none)") : pos.move_to_uci(best)));
  } catch (...) {
    // Out of memory while formatting: still answer the go, once.
    if (!sent) {
      try {
        out_.send_line("bestmove (none)");
      } catch (...) {}
    }
  }
  std::lock_guard<std::mutex> lock(signals_.mutex);
  signals_.finished = true;
}

void UciSession::report_search(const Position& pos, Move best, std::uint64_t nodes, std::int64_t elapsed_ms) {
  const std::uint64_t nps = nodes * 1000 / static_cast<std::uint64_t>(std::max<std::int64_t>(elapsed_ms, 1));
  std::string line;
  if (best.is_none()) {
    line = std::string("info depth 0 seldepth 0 score ") + (pos.in_check() ? "mate 0" : "cp 0");
  } else {
    line = "info depth 1 seldepth 1 score cp 0";
  }
  line += " nodes " + std::to_string(nodes) + " nps " + std::to_string(nps) + " time " +
          std::to_string(elapsed_ms);
  if (!best.is_none()) line += " pv " + pos.move_to_uci(best);
  out_.send_line(line);
}

void UciSession::cmd_perft(const std::vector<LineToken>& tokens, std::size_t first) {
  if (!config_.allow_heavy_commands) {
    out_.send_info_string("go perft: disabled");
    return;
  }
  const std::optional<std::int64_t> depth =
      first < tokens.size() ? parse_int64(tokens[first].text) : std::nullopt;
  if (!depth || *depth < 1 || *depth > 20) {
    out_.send_info_string("go perft: expected a depth from 1 to 20");
    return;
  }
  Position pos = root_;
  std::ostringstream text;
  const auto start = std::chrono::steady_clock::now();
  divide(pos, static_cast<int>(*depth), text);
  const std::int64_t ms = ms_since(start);
  std::string row;
  std::istringstream rows(text.str());
  while (std::getline(rows, row))
    if (!row.empty()) out_.send_info_string(row);
  out_.send_info_string("time " + std::to_string(ms) + " ms");
}

void UciSession::cmd_bench() {
  if (!config_.allow_heavy_commands) {
    out_.send_info_string("bench: disabled");
    return;
  }
  const BenchResult r = bench();
  out_.send_info_string("nodes " + std::to_string(r.nodes));
  out_.send_info_string("signature " + hex16(r.signature));
  out_.send_info_string("nps " + std::to_string(static_cast<std::uint64_t>(static_cast<double>(r.nodes) /
                                                                           std::max(r.seconds, 1e-9))));
}

void UciSession::cmd_board() {
  for (int rank = 7; rank >= 0; --rank) {
    std::string row = "info string " + std::to_string(rank + 1) + " ";
    for (int file = 0; file < 8; ++file) {
      const Piece p = root_.piece_at(make_square(file, rank));
      char c = '.';
      if (p != NoPiece) {
        c = "pnbrqk"[kind_of(p)];
        if (side_of(p) == White) c = static_cast<char>(c - 'a' + 'A');
      }
      (row += ' ') += c;
    }
    out_.send_line(row);
  }
  out_.send_info_string("   a b c d e f g h");
  out_.send_info_string("fen " + root_.fen());
  out_.send_info_string("key " + hex16(root_.key()));
}

}  // namespace forkeng
