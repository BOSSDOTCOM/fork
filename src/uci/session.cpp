#include "uci/session.hpp"

#include <algorithm>
#include <chrono>
#include <exception>
#include <filesystem>
#include <sstream>
#include <system_error>
#include <utility>

#include "core/movegen.hpp"
#include "core/perft.hpp"
#include "eval/eval.hpp"
#include "search/endgame_tables.hpp"
#include "search/search_bench.hpp"
#include "search/time_budget.hpp"
#include "tune/params.hpp"

namespace forkeng {

namespace {

constexpr std::string_view Commands[] = {"uci",        "debug",    "isready", "setoption", "register",
                                         "ucinewgame", "position", "go",      "stop",      "ponderhit",
                                         "quit",       "d",        "bench"};

bool is_command(std::string_view t) { return std::ranges::find(Commands, t) != std::end(Commands); }

// The first command word of `line` (empty if none), found without
// allocating (so it still works when the tokenizer could not).
std::string_view first_command(std::string_view line) {
  std::size_t i = 0;
  while (i < line.size()) {
    while (i < line.size() && is_uci_space(line[i])) ++i;
    std::size_t j = i;
    while (j < line.size() && !is_uci_space(line[j])) ++j;
    const std::string_view word = line.substr(i, j - i);
    if (is_command(word)) return word;
    i = j;
  }
  return {};
}

// "e2e4", "e7e8q" or "(none)" without allocating: info lines and the
// out-of-memory path.
void write_move_text(Move m, char (&text)[8]) {
  if (m.is_none()) {
    (void)std::snprintf(text, sizeof text, "(none)");
    return;
  }
  const Square to = m.is_castle() ? Position::castle_landing(m.from(), m.to()).king : m.to();
  int n = 0;
  for (Square s : {m.from(), to}) {
    text[n++] = static_cast<char>('a' + file_of(s));
    text[n++] = static_cast<char>('1' + rank_of(s));
  }
  if (m.is_promotion()) text[n++] = "nbrq"[m.promo_type() - Knight];
  text[n] = '\0';
}

// Writes the info lines of a search into a fixed buffer: no allocation
// while the search runs (DESIGN.md §5.2, hot-path rules).
class InfoWriter final : public SearchListener {
 public:
  explicit InfoWriter(OutputChannel& out) : out_(out) {}
  void on_iteration(const Position&, const IterationReport& r) override {
    char* const line = line_;
    const std::uint64_t ms = static_cast<std::uint64_t>(std::max<std::int64_t>(r.elapsed_ms, 0));
    const std::uint64_t nps = r.nodes * 1000 / std::max<std::uint64_t>(ms, 1);
    const bool mate = is_mate_score(r.score);
    int n = std::snprintf(
        line, sizeof line_,
        "info depth %d seldepth %d score %s %d%s nodes %llu nps %llu hashfull %d tbhits %llu time %llu",
        r.depth, std::max(r.max_ply_reached, 1), mate ? "mate" : "cp",
        mate ? mate_in_moves(r.score) : r.score,
        r.bound > 0   ? " lowerbound"
        : r.bound < 0 ? " upperbound"
                      : "",
        static_cast<unsigned long long>(r.nodes), static_cast<unsigned long long>(nps), r.fill_permille,
        static_cast<unsigned long long>(r.table_hits), static_cast<unsigned long long>(ms));
    if (r.pv->length > 0) n += std::snprintf(line + n, sizeof line_ - static_cast<std::size_t>(n), " pv");
    for (int i = 0; i < r.pv->length; ++i) {
      char move[8];
      write_move_text(r.pv->moves[i], move);
      n += std::snprintf(line + n, sizeof line_ - static_cast<std::size_t>(n), " %s", move);
    }
    length_ = static_cast<std::size_t>(n);
    sent_after_ = out_.send_line(std::string_view(line_, length_));
  }
  // Sends the last line again if another line (readyok, say) came after it,
  // so the final info line is always right before bestmove.
  void repeat_if_interrupted() {
    if (length_ > 0 && out_.lines_sent() != sent_after_) out_.send_line(std::string_view(line_, length_));
  }

 private:
  OutputChannel& out_;
  char line_[4096];
  std::size_t length_ = 0;
  std::uint64_t sent_after_ = 0;
};

std::string hex16(std::uint64_t v) {
  char buf[17];
  (void)std::snprintf(buf, sizeof buf, "%016llx", static_cast<unsigned long long>(v));
  return buf;
}

std::int64_t ms_since(std::chrono::steady_clock::time_point start) {
  return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start)
      .count();
}

// Counts Syzygy table files in a SyzygyPath value: directories separated by
// ':' on Linux and ';' on Windows; a missing directory is reported, not an error.
std::string describe_syzygy_path(const std::string& paths) {
#ifdef _WIN32
  constexpr char Separator = ';';
#else
  constexpr char Separator = ':';
#endif
  int wdl = 0, dtz = 0, dirs = 0, listed = 0;
  std::string missing;
  std::size_t begin = 0;
  while (begin <= paths.size()) {
    std::size_t end = paths.find(Separator, begin);
    if (end == std::string::npos) end = paths.size();
    const std::string dir = paths.substr(begin, end - begin);
    begin = end + 1;
    if (dir.empty()) continue;
    ++listed;
    std::error_code ec;
    std::filesystem::directory_iterator it(std::filesystem::path(dir), ec);
    if (ec) {
      missing += (missing.empty() ? "" : ", ") + dir;
      continue;
    }
    ++dirs;
    for (; !ec && it != std::filesystem::directory_iterator(); it.increment(ec)) {
      const std::filesystem::path ext = it->path().extension();
      wdl += ext == ".rtbw";
      dtz += ext == ".rtbz";
    }
  }
  std::string report = "SyzygyPath: " + std::to_string(dirs) + " of " + std::to_string(listed) +
                       " directories found, " + std::to_string(wdl) + " .rtbw and " + std::to_string(dtz) +
                       " .rtbz files";
  if (!missing.empty()) report += "; not found: " + missing;
  return report;
}

}  // namespace

UciSession::UciSession(OutputChannel& out, SessionConfig config)
    : out_(out), config_(config), searcher_(std::make_unique<Searcher>(tt_)) {
  declare_options();
}

// The options and what setting each one does (DESIGN.md §5.1, "Options").
void UciSession::declare_options() {
  options_.add_spin("Hash", config_.default_hash_mb, 1, config_.max_hash_mb,
                    [this](const OptionEntry&, std::string&) { return hash_pending_ = true; });
  options_.add_button("Clear Hash",
                      [this](const OptionEntry&, std::string&) { return clear_pending_ = true; });
  options_.add_spin("Threads", 1, 1, config_.max_threads);
  options_.add_spin("Move Overhead", 100, 0, 10000);
  options_.add_string("SyzygyPath", "", [this](const OptionEntry& e, std::string& message) {
    syzygy_path_ = e.text;
    tables_pending_ = config_.allow_files;
    if (e.text.empty()) return true;
    message = config_.allow_files ? describe_syzygy_path(e.text) : "SyzygyPath: file access disabled";
    return true;
  });
#ifdef FORK_TUNE
  // Tuning builds only (CMake FORK_TUNE; DESIGN.md §1 and §5.2): each search
  // switch as a check option, so an SPRT can compare a technique on and off
  // in one binary. Released and TCEC builds never declare these.
  struct SwitchOption {
    const char* name;
    bool SearchSwitches::* field;
  };
  for (const SwitchOption s :
       {SwitchOption{"UseTT", &SearchSwitches::use_tt}, SwitchOption{"UsePvs", &SearchSwitches::use_pvs},
        SwitchOption{"UseAspiration", &SearchSwitches::use_aspiration},
        SwitchOption{"UseMateDistance", &SearchSwitches::use_mate_distance},
        SwitchOption{"UseQuiesce", &SearchSwitches::use_quiesce},
        SwitchOption{"UseSeeQuiesce", &SearchSwitches::use_see_quiesce},
        SwitchOption{"UseHistory", &SearchSwitches::use_history},
        SwitchOption{"UseHistoryMalus", &SearchSwitches::use_history_malus},
        SwitchOption{"UseRfp", &SearchSwitches::use_rfp}, SwitchOption{"UseNmp", &SearchSwitches::use_nmp},
        SwitchOption{"UseLmr", &SearchSwitches::use_lmr}, SwitchOption{"UseLmp", &SearchSwitches::use_lmp},
        SwitchOption{"UseFutility", &SearchSwitches::use_futility},
        SwitchOption{"UseSeePrune", &SearchSwitches::use_see_prune},
        SwitchOption{"UseTtAgeBlend", &SearchSwitches::tt_age_blend},
        SwitchOption{"UseTtKeepExact", &SearchSwitches::tt_keep_exact},
        SwitchOption{"UseTtEvalRefine", &SearchSwitches::use_tt_eval_refine},
        SwitchOption{"UseTables", &SearchSwitches::use_tables}}) {
    options_.add_check(s.name, searcher_->switches.*s.field,
                       [this, field = s.field](const OptionEntry& e, std::string&) {
                         searcher_->switches.*field = e.number != 0;
                         return true;
                       });
  }
  // And every numeric search parameter as a spin option (deliverable 8b; the
  // table and its ranges are src/tune/params.hpp), for SPSA.
  for (const TuneParam& p : param_table()) {
    options_.add_spin(std::string(p.name), p.default_value, p.lowest, p.highest,
                      [name = p.name](const OptionEntry& e, std::string&) {
                        return set_param(name, static_cast<int>(e.number));
                      });
  }
#endif
  options_.add_string("LogFile", "", [this](const OptionEntry& e, std::string& message) {
    if (!config_.allow_files) {
      message = "LogFile: file access disabled";
      return false;
    }
    std::string error;
    if (out_.open_log(e.text, &error)) return true;
    message = "LogFile: cannot open " + e.text + ": " + error;
    return false;
  });
}

// From the size actually allocated, which a refused Hash makes smaller than
// the option (review 2026-10-24: 16 MB was cleared by 1024 threads).
unsigned UciSession::hash_workers() const {
  return config_.use_threads ? clear_workers(hash_.bytes(), options_.number("Threads")) : 1;
}

bool UciSession::apply_pending() {
  if (tables_pending_) {
    // Never during a search: this runs only where the Hash work runs. An
    // empty path (or "<empty>", the GUIs' way to clear it) unloads quietly.
    tables_pending_ = false;
    const bool cleared = syzygy_path_.empty() || syzygy_path_ == "<empty>";
    const std::string report = load_endgame_tables(cleared ? std::string() : syzygy_path_);
    if (!cleared) out_.send_info_string(report);
  }
  if (hash_pending_) {
    const std::size_t bytes = hash_bytes_for_mb(static_cast<std::uint64_t>(options_.number("Hash")));
    const auto start = std::chrono::steady_clock::now();
    std::string report;
    // resize() frees the old table and may then throw (its report string), so
    // the TT is unbound first and rebound from whatever the memory holds on
    // every way out (review, 2026-10-24: it was left on freed memory). If it
    // throws, the Hash stays pending and the next isready or go tries again.
    struct Rebind {
      TransTable& table;
      const HashMemory& source;
      ~Rebind() { table.bind_memory(source.data(), source.bytes()); }
    } rebind{tt_, hash_};
    tt_.bind_memory(nullptr, 0);
    const bool ok = hash_.resize(bytes, report);
    // A Clear Hash in the same batch also forgets the history (audit-1, V-2).
    if (clear_pending_) searcher_->clear_history();
    hash_pending_ = clear_pending_ = false;
    tt_.bind_memory(hash_.data(), hash_.bytes());
    const unsigned workers = hash_workers();
    hash_.clear(workers);
    const std::int64_t ms = ms_since(start);
    if (!ok) out_.send_info_string(report);
    out_.send_info_string("Hash " + std::to_string(hash_.bytes() / BytesPerMB) +
                          " MB allocated and cleared in " + std::to_string(ms) + " ms by " +
                          std::to_string(workers) + " threads");
    return true;
  }
  if (clear_pending_) {
    clear_pending_ = false;
    hash_.clear(hash_workers());
    searcher_->clear_history();  // Clear Hash forgets all search memory (review, deliverable 5)
    return true;
  }
  return false;
}

UciSession::~UciSession() {
  try {
    stop_search();
  } catch (...) {
    // ignored: nothing may escape a destructor, and a failed join leaves no thread to join
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
  go_answered_ = false;
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
    // A go that failed before its search started (no memory to tokenize the
    // line, say) still gets its one bestmove, and an isready its readyok
    // (audit-1, R-2: a Hash resize that ran out of memory lost it).
    const std::string_view command = first_command(line);
    if (command == "go" && !go_answered_) {
      try {
        stop_search();
      } catch (...) {
        // ignored: a join that fails leaves no search to wait for
      }
      answer_without_memory(root_, NoMove, false);
    }
    try {
      out_.send_info_string(std::string("error: ") + e.what());
    } catch (...) {
      // ignored: no memory for the message either
    }
    if (command == "isready") {
      try {
        out_.send_line("readyok");
      } catch (...) {
        // ignored: only a failing mutex can throw here
      }
    }
  }
  return true;
}

void UciSession::dispatch(const std::vector<LineToken>& tokens, std::size_t first, std::string_view line) {
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
      cmd_position(tokens, first + 1, line);
    } else if (cmd == "go") {
      cmd_go(tokens, first + 1);
    } else if (cmd == "bench") {
      cmd_bench();
    } else if (cmd == "setoption") {
      cmd_setoption(tokens, first + 1, line);
    } else if (cmd == "ucinewgame") {
      cmd_ucinewgame();
    }
  }
}

void UciSession::cmd_uci() {
  out_.send_line(std::string("id name Fork ") + engine_version());
  out_.send_line("id author BOSSDOTCOM");
  for (const std::string& line : options_.option_lines()) out_.send_line(line);
  out_.send_line("uciok");
}

void UciSession::cmd_isready() {
  if (!search_running()) {
    stop_search();  // joins a search that already printed bestmove
    apply_pending();
  }
  out_.send_line("readyok");
}

// setoption name <id> [value <x>]: the name is the text between `name` and
// `value` (the option table folds its whitespace), the value is the rest of
// the line as sent.
void UciSession::cmd_setoption(const std::vector<LineToken>& tokens, std::size_t first,
                               std::string_view line) {
  std::size_t i = first;
  while (i < tokens.size() && !iequals(tokens[i].text, "name")) ++i;
  if (i == tokens.size()) {
    out_.send_info_string("setoption: expected 'name'");
    return;
  }
  const std::size_t name_from = tokens[i].offset + tokens[i].text.size();
  for (++i; i < tokens.size() && !iequals(tokens[i].text, "value");) ++i;
  const std::size_t name_to = i < tokens.size() ? tokens[i].offset : line.size();
  const std::string_view name = line.substr(name_from, name_to - name_from);
  std::optional<std::string_view> value;
  if (i < tokens.size())
    value = rest_of_line(line, i + 1 < tokens.size() ? tokens[i + 1].offset : line.size());
  std::string message;
  options_.set(name, value, message);
  if (!message.empty()) out_.send_info_string(message);
}

void UciSession::cmd_ucinewgame() {
  if (!apply_pending()) hash_.clear(hash_workers());
  searcher_->clear_history();
}

void UciSession::cmd_ponderhit() {
  pondering_.store(false);
  {
    std::scoped_lock lock(signals_.mutex);
    signals_.ponder = false;
  }
  signals_.wake.notify_all();
}

void UciSession::cmd_position(const std::vector<LineToken>& tokens, std::size_t first,
                              std::string_view line) {
  Position pos;
  std::size_t i = first;
  if (i < tokens.size() && tokens[i].text == "startpos") {
    ++i;
  } else if (i < tokens.size() && tokens[i].text == "fen") {
    // The FEN is the text between `fen` and `moves`; set_fen splits its fields.
    const std::size_t fen_from = tokens[i].offset + tokens[i].text.size();
    for (++i; i < tokens.size() && tokens[i].text != "moves";) ++i;
    const std::size_t fen_to = i < tokens.size() ? tokens[i].offset : line.size();
    const std::string_view fen = line.substr(fen_from, fen_to - fen_from);
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
    go_answered_ = true;  // a Fork extension, not a search: no bestmove
    cmd_perft(tokens, first + 1);
    return;
  }
  const auto go_time = std::chrono::steady_clock::now();  // time limits count from here
  std::vector<std::string> warnings;
  const GoLimits go = parse_go(tokens, first, root_, warnings);
  for (const std::string& w : warnings) out_.send_info_string(w);
  if (go.restrict_sent && go.restrict_to.empty())
    out_.send_info_string("go: no legal move in searchmoves; searching every move");
  apply_pending();
  SearchQuota limits = quota_for_go(go, root_.side_to_move(), options_.number("Move Overhead"));
  limits.go_received = go_time;
  const bool infinite = go.infinite;
  {
    std::scoped_lock lock(signals_.mutex);
    signals_.stop = !config_.use_threads;  // no thread: nothing could stop it later
    signals_.ponder = go.ponder && config_.use_threads;
    signals_.finished = false;
  }
  stop_flag_.store(!config_.use_threads);
  pondering_.store(go.ponder && config_.use_threads);
  if (!config_.use_threads) {
    search_main(root_, limits, infinite);
    go_answered_ = true;
    return;
  }
  try {
    search_thread_ = std::thread(&UciSession::search_main, this, root_, limits, infinite);
  } catch (...) {
    // No thread (std::system_error) or no memory for its copy of the
    // position: answer at once on this thread, without allocating, so the go
    // still gets its one bestmove (a go infinite then ends at once too).
    answer_without_memory(root_, NoMove, false);
    std::scoped_lock lock(signals_.mutex);
    signals_.finished = true;
  }
  go_answered_ = true;
}

bool UciSession::search_running() {
  std::scoped_lock lock(signals_.mutex);
  return search_thread_.joinable() && !signals_.finished;
}

void UciSession::stop_search() {
  if (!search_thread_.joinable()) return;
  {
    std::scoped_lock lock(signals_.mutex);
    signals_.stop = true;
  }
  stop_flag_.store(true);
  signals_.wake.notify_all();
  search_thread_.join();
}

// A ponder search ignores time until ponderhit (the session's pondering flag,
// not the limits).
SearchQuota quota_for_go(const GoLimits& go, Color us, std::int64_t move_overhead_ms) {
  SearchQuota l;
  if (go.depth) l.depth = static_cast<int>(std::clamp<std::int64_t>(*go.depth, 1, MaxPly - 1));
  if (go.nodes) l.nodes = static_cast<std::uint64_t>(std::max<std::int64_t>(*go.nodes, 1));
  if (go.mate && *go.mate > 0) l.mate_moves = static_cast<int>(std::min<std::int64_t>(*go.mate, MaxPly));
  for (Move m : go.restrict_to) l.restrict_to.add(m);
  if (!go.infinite) {
    ClockInput clock;
    clock.remaining_ms = go.remaining_ms[us];
    clock.increment_ms = go.increment_ms[us];
    clock.movestogo = go.movestogo;
    clock.movetime = go.movetime;
    clock.overhead_ms = move_overhead_ms;
    const TimeBudget budget = plan_time(clock);
    l.soft_ms = budget.soft_ms;
    l.hard_ms = budget.hard_ms;
  }
  return l;
}

void UciSession::search_main(Position pos, SearchQuota limits, bool infinite) {
  const auto start = std::chrono::steady_clock::now();
  Move best = NoMove;
  bool picked = false;
  try {
    InfoWriter writer(out_);
    const SearchResult r = searcher_->deliberate(pos, limits, stop_flag_, &pondering_, &writer);
    best = r.best;
    picked = true;
    {
      // go infinite and go ponder never end by themselves.
      std::unique_lock<std::mutex> lock(signals_.mutex);
      signals_.wake.wait(lock, [&] { return signals_.stop || (!infinite && !signals_.ponder); });
    }
    if (r.depth == 0)
      report_unfinished(pos, r, ms_since(start));
    else
      writer.repeat_if_interrupted();
    char move[8];
    write_move_text(best, move);
    char line[32];
    const int n = std::snprintf(line, sizeof line, "bestmove %s", move);
    out_.send_line(std::string_view(line, static_cast<std::size_t>(n)));
  } catch (...) {
    // Out of memory while formatting (a failed send_line throws before it
    // writes anything): answer the go once, without allocating.
    answer_without_memory(pos, picked ? best : NoMove, picked);
  }
  std::scoped_lock lock(signals_.mutex);
  signals_.finished = true;
}

// The last info line when no iteration finished (stopped early, or no legal
// move), from fixed buffers.
void UciSession::report_unfinished(const Position& pos, const SearchResult& r, std::int64_t elapsed_ms) {
  const std::uint64_t ms = static_cast<std::uint64_t>(std::max<std::int64_t>(elapsed_ms, 0));
  const std::uint64_t nps = r.nodes * 1000 / std::max<std::uint64_t>(ms, 1);
  char line[160];
  int n;
  if (r.best.is_none()) {
    n = std::snprintf(line, sizeof line, "info depth 0 seldepth 0 score %s nodes %llu nps %llu time %llu",
                      pos.in_check() ? "mate 0" : "cp 0", static_cast<unsigned long long>(r.nodes),
                      static_cast<unsigned long long>(nps), static_cast<unsigned long long>(ms));
  } else {
    // Stopped before depth 1 finished: the static evaluation is the score.
    char move[8];
    write_move_text(r.best, move);
    n = std::snprintf(line, sizeof line,
                      "info depth 0 seldepth 1 score cp %d nodes %llu nps %llu time %llu pv %s",
                      pos.in_check() ? 0 : static_eval(pos), static_cast<unsigned long long>(r.nodes),
                      static_cast<unsigned long long>(nps), static_cast<unsigned long long>(ms), move);
  }
  out_.send_line(std::string_view(line, static_cast<std::size_t>(n)));
}

// The last-resort answer to a go: a scored info line and a bestmove, built in
// fixed buffers. With `known` false the move is the first legal one.
void UciSession::answer_without_memory(const Position& pos, Move best, bool known) noexcept {
  try {
    if (!known) {
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      best = legal.size() ? legal[0] : NoMove;
    }
    char move[8];
    write_move_text(best, move);
    char line[96];
    int n = best.is_none()
                ? std::snprintf(line, sizeof line, "info depth 0 seldepth 0 score %s nodes 1 nps 0 time 0",
                                pos.in_check() ? "mate 0" : "cp 0")
                : std::snprintf(line, sizeof line,
                                "info depth 1 seldepth 1 score cp 0 nodes 1 nps 0 time 0 pv %s", move);
    out_.send_line(std::string_view(line, static_cast<std::size_t>(n)));
    n = std::snprintf(line, sizeof line, "bestmove %s", move);
    out_.send_line(std::string_view(line, static_cast<std::size_t>(n)));
  } catch (...) {
    // ignored: only a failing mutex can throw here; nothing more can be said
  }
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
  const SearchBenchResult r = run_search_bench();
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
