// UCI protocol tests: the fork binary driven over pipes, as a GUI drives it
// (DESIGN.md §5.1, "Tests and acceptance checks", test 1).
//
// Constructed positions (all checked with python-chess 1.11.2, an independent
// implementation, on 2026-10-24):
//   7k/6Q1/6K1/8/8/8/8/8 b - - 0 1   Black is checkmated (0 legal moves, in check)
//   7k/5Q2/6K1/8/8/8/8/8 b - - 0 1   Black is stalemated (0 legal moves, not in check)
//   8/4P3/8/8/8/8/k7/4K3 w - - 0 1   e7e8q gives 4Q3/8/8/8/8/8/k7/4K3 b - - 0 1
//   startpos, e2e4 e7e5 gives rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2,
//   where e1e3 is illegal
//   startpos, 1000 x (g1f3 g8f6 f3g1 f6g8) is 4000 legal plies back to the
//   start placement: rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 4000 2001
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

#include "core/position.hpp"
#include "engine_process.hpp"
#include "harness.hpp"
#include "search/hash_memory.hpp"
#include "uci/tokens.hpp"

namespace forkeng::test {

namespace {

using namespace std::chrono_literals;

// Generous: sanitizer builds on a loaded machine are slow. The timing suite
// (uci_timing) holds the real limits.
constexpr auto Patience = 10000ms;

bool starts_with(std::string_view s, std::string_view prefix) { return s.substr(0, prefix.size()) == prefix; }

bool is_move_text(std::string_view m) {
  auto square = [](std::string_view s) { return s[0] >= 'a' && s[0] <= 'h' && s[1] >= '1' && s[1] <= '8'; };
  if (m.size() != 4 && m.size() != 5) return false;
  if (!square(m.substr(0, 2)) || !square(m.substr(2, 2))) return false;
  return m.size() == 4 || std::string_view("nbrq").find(m[4]) != std::string_view::npos;
}

// Is `line` a well-formed engine-to-GUI message (UCI spec, "Engine to GUI")?
bool valid_engine_line(const std::string& line) {
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

// One engine, plus a read cursor over its output.
struct Gui {
  EngineProcess engine{FORK_EXE_PATH};
  std::size_t cursor = 0;

  void send(std::string_view line) { CHECK_MSG(engine.send(line), "write failed: " << line); }

  // The next line starting with `prefix` (skipping others); moves the cursor past it.
  std::optional<std::string> next(std::string_view prefix, std::chrono::milliseconds wait = Patience) {
    const std::optional<std::size_t> i = engine.wait_prefix(prefix, cursor, wait);
    if (!i) return std::nullopt;
    cursor = *i + 1;
    return engine.lines()[*i].text;
  }

  // Sends isready and waits for readyok: everything before it was handled.
  bool sync() {
    send("isready");
    return next("readyok").has_value();
  }

  std::vector<std::string> texts(std::size_t from = 0) const {
    std::vector<std::string> out;
    const std::vector<OutputLine> all = engine.lines();
    for (std::size_t i = from; i < all.size(); ++i) out.push_back(all[i].text);
    return out;
  }

  int count(std::string_view prefix, std::size_t from = 0) const {
    int n = 0;
    for (const std::string& s : texts(from)) n += starts_with(s, prefix);
    return n;
  }

  // The FEN printed by the `d` extension.
  std::optional<std::string> board_fen() {
    send("d");
    std::optional<std::string> line = next("info string fen ");
    if (!line) return std::nullopt;
    return line->substr(std::string_view("info string fen ").size());
  }

  // Checks the whole transcript: every line valid UCI, and a scored info
  // line right before every bestmove.
  void check_transcript() const {
    const std::vector<std::string> all = texts();
    for (std::size_t i = 0; i < all.size(); ++i) {
      CHECK_MSG(valid_engine_line(all[i]), "not a UCI engine message: '" << all[i] << "'");
      if (starts_with(all[i], "bestmove")) {
        const bool scored_info = i > 0 && starts_with(all[i - 1], "info ") &&
                                 !starts_with(all[i - 1], "info string") &&
                                 all[i - 1].find(" score ") != std::string::npos;
        CHECK_MSG(scored_info, "no final scored info line before '" << all[i] << "'");
      }
    }
  }

  // quit, then exit status 0.
  void quit() {
    send("quit");
    const std::optional<int> code = engine.wait_exit(Patience);
    CHECK_MSG(code && *code == 0, "exit after quit: " << (code ? std::to_string(*code) : "still running"));
  }
};

// The bestmove's move text, if it names one.
std::string bestmove_of(const std::string& line) { return line.substr(std::string_view("bestmove ").size()); }

}  // namespace

TEST_CASE("uci_protocol", "handshake: id name, id author, uciok") {
  Gui g;
  CHECK(g.engine.started());
  g.send("uci");
  CHECK(g.next("uciok").has_value());
  const std::vector<std::string> out = g.texts();
  const std::vector<std::string> options = {
      "option name Hash type spin default 16 min 1 max 33554432",
      "option name Clear Hash type button",
      "option name Threads type spin default 1 min 1 max 1024",
      "option name Move Overhead type spin default 100 min 0 max 5000",
      "option name SyzygyPath type string default <empty>",
      "option name LogFile type string default <empty>",
  };
  CHECK_EQ(out.size(), options.size() + 3);
  if (out.size() == options.size() + 3) {
    CHECK_MSG(starts_with(out[0], "id name Fork 0."), out[0]);
    CHECK_EQ(out[1], std::string("id author BOSSDOTCOM"));
    for (std::size_t i = 0; i < options.size(); ++i) CHECK_EQ(out[2 + i], options[i]);
    CHECK_EQ(out.back(), std::string("uciok"));
  }
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "isready while idle and during go infinite; stop ends the search") {
  Gui g;
  CHECK(g.sync());
  g.send("position startpos");
  g.send("go infinite");
  CHECK(g.sync());  // answered at once, search still running
  std::this_thread::sleep_for(100ms);
  CHECK_EQ(g.count("bestmove"), 0);  // infinite never ends by itself
  g.send("stop");
  CHECK(g.next("bestmove").has_value());
  CHECK(g.sync());
  CHECK_EQ(g.count("bestmove"), 1);
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "stop and ponderhit with no search print nothing") {
  Gui g;
  CHECK(g.sync());  // the hash is allocated here
  const std::size_t mark = g.cursor;
  g.send("stop");
  g.send("ponderhit");
  g.send("stop");
  CHECK(g.sync());
  const std::vector<std::string> out = g.texts(mark);
  CHECK_EQ(out.size(), std::size_t{1});  // just readyok
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "go twice in a row, and go during go infinite: one bestmove each") {
  Gui g;
  g.send("position startpos");
  g.send("go depth 1");
  g.send("go depth 1");
  CHECK(g.next("bestmove").has_value());
  CHECK(g.next("bestmove").has_value());
  g.send("go infinite");
  g.send("go movetime 10");  // the infinite search is stopped first
  CHECK(g.next("bestmove").has_value());
  CHECK(g.next("bestmove").has_value());
  CHECK(g.sync());
  CHECK_EQ(g.count("bestmove"), 4);
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "ponder: bestmove only after ponderhit or stop") {
  Gui g;
  g.send("position startpos moves e2e4");
  g.send("go ponder wtime 1000 btime 1000");
  std::this_thread::sleep_for(100ms);
  CHECK(g.sync());
  CHECK_EQ(g.count("bestmove"), 0);
  g.send("ponderhit");
  CHECK(g.next("bestmove").has_value());
  g.send("go ponder wtime 1000 btime 1000");
  std::this_thread::sleep_for(50ms);
  CHECK_EQ(g.count("bestmove"), 1);
  g.send("stop");
  CHECK(g.next("bestmove").has_value());
  g.send("go infinite ponder");
  g.send("ponderhit");  // still infinite: waits for stop
  std::this_thread::sleep_for(50ms);
  CHECK(g.sync());
  CHECK_EQ(g.count("bestmove"), 2);
  g.send("stop");
  CHECK(g.next("bestmove").has_value());
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "quit during a search: bestmove, then exit status 0") {
  Gui g;
  g.send("go infinite");
  CHECK(g.sync());
  g.quit();
  CHECK_EQ(g.count("bestmove"), 1);
  g.check_transcript();
}

TEST_CASE("uci_protocol", "EOF on stdin: exit status 0, idle or searching") {
  {
    Gui g;
    CHECK(g.sync());
    g.engine.close_input();
    const std::optional<int> code = g.engine.wait_exit(Patience);
    CHECK(code && *code == 0);
  }
  {
    Gui g;
    g.send("go infinite");
    CHECK(g.sync());
    g.engine.close_input();
    const std::optional<int> code = g.engine.wait_exit(Patience);
    CHECK(code && *code == 0);
    CHECK_EQ(g.count("bestmove"), 1);
    g.check_transcript();
  }
  {
    Gui g;  // a last command without a line terminator still counts
    g.engine.send_raw("isready");
    g.engine.close_input();
    CHECK(g.next("readyok").has_value());
    CHECK(g.engine.wait_exit(Patience).has_value());
  }
}

TEST_CASE("uci_protocol", "line endings: LF, CRLF and lone CR; whitespace; empty and unknown lines") {
  Gui g;
  g.engine.send_raw("isready\r\nisready\risready\n");
  CHECK(g.next("readyok").has_value());
  CHECK(g.next("readyok").has_value());
  CHECK(g.next("readyok").has_value());
  g.engine.send_raw("\n\r\n   \t \n");
  g.send("  \t isready \t ");
  CHECK(g.next("readyok").has_value());
  g.send("xyzzy");
  g.send("xyzzy isready");  // the spec: unknown tokens before a command are skipped
  CHECK(g.next("readyok").has_value());
  g.send("debug on");
  g.send("debug off");
  g.send("register later");
  CHECK(g.sync());
  for (const std::string& s : g.texts())
    CHECK_MSG(s == "readyok" || starts_with(s, "info string"), "unexpected: " << s);
  CHECK_EQ(g.count("readyok"), 6);  // exactly one per isready
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "position: startpos, fen, moves; illegal move and bad FEN") {
  Gui g;
  g.send("position startpos moves e2e4 e7e5");
  CHECK_EQ(g.board_fen().value_or(""),
           std::string("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"));
  // An illegal move keeps the position reached before it.
  std::size_t mark = g.cursor;
  g.send("position startpos moves e2e4 e7e5 e1e3 g8f6");
  CHECK_EQ(g.board_fen().value_or(""),
           std::string("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"));
  CHECK_EQ(g.count("info string illegal move e1e3", mark), 1);
  // A malformed FEN leaves the position unchanged.
  mark = g.cursor;
  g.send("position fen rnbqkbnr/pppppppp/9/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 moves e2e4");
  CHECK_EQ(g.board_fen().value_or(""),
           std::string("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"));
  CHECK_EQ(g.count("info string invalid FEN", mark), 1);
  mark = g.cursor;
  g.send("position");
  g.send("position nonsense");
  CHECK(g.sync());
  CHECK_EQ(g.count("info string position:", mark), 2);
  // Promotion letters in either case; a 4-field FEN; moves without "moves" are ignored.
  g.send("position fen 8/4P3/8/8/8/8/k7/4K3 w - - 0 1 moves e7e8Q");
  CHECK_EQ(g.board_fen().value_or(""), std::string("4Q3/8/8/8/8/8/k7/4K3 b - - 0 1"));
  g.send("position fen 8/4P3/8/8/8/8/k7/4K3 w - - moves e7e8q");
  CHECK_EQ(g.board_fen().value_or(""), std::string("4Q3/8/8/8/8/8/k7/4K3 b - - 0 1"));
  g.send("position startpos moves");
  CHECK_EQ(g.board_fen().value_or(""), std::string(Position::StartFen));
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "a 4000-ply move list") {
  Gui g;
  std::string cmd = "position startpos moves";
  for (int i = 0; i < 1000; ++i) cmd += " g1f3 g8f6 f3g1 f6g8";
  g.send(cmd);
  CHECK_EQ(g.board_fen().value_or(""),
           std::string("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 4000 2001"));
  g.send("go wtime 1000 btime 1000");
  const std::optional<std::string> best = g.next("bestmove");
  CHECK(best.has_value());
  if (best) {
    Position start;
    CHECK_MSG(!start.parse_uci(bestmove_of(*best)).is_none(), *best);
  }
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "bestmove (none) on checkmate and stalemate, after a scored info line") {
  Gui g;
  g.send("position fen 7k/6Q1/6K1/8/8/8/8/8 b - - 0 1");
  g.send("go depth 5");
  CHECK_EQ(g.next("bestmove").value_or(""), std::string("bestmove (none)"));
  g.send("position fen 7k/5Q2/6K1/8/8/8/8/8 b - - 0 1");
  g.send("go infinite");
  CHECK(g.sync());
  CHECK_EQ(g.count("bestmove"), 1);
  g.send("stop");
  CHECK_EQ(g.next("bestmove").value_or(""), std::string("bestmove (none)"));
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "go arguments: every argument, combined, negative and huge numbers, junk") {
  Gui g;
  g.send("position startpos");
  CHECK(g.sync());
  std::size_t mark = g.cursor;
  g.send("go wtime -100 btime 0 winc 0 binc 0 movestogo 1 depth 3 nodes 100 mate 2 movetime 50");
  CHECK(g.next("bestmove").has_value());
  g.send("go wtime 99999999999999999999999 btime -99999999999999999999999");
  CHECK(g.next("bestmove").has_value());
  g.send("go wtime 100");  // fastchess --compliance sends wtime alone
  CHECK(g.next("bestmove").has_value());
  g.send("go");  // a bare go
  CHECK(g.next("bestmove").has_value());
  CHECK(g.sync());
  CHECK_EQ(g.count("info string", mark), 0);  // all of that was valid
  mark = g.cursor;
  g.send("go wtime abc depth movetime 5 frobnicate");
  CHECK(g.next("bestmove").has_value());
  CHECK(g.sync());
  CHECK(g.count("info string go:", mark) >= 3);
  // searchmoves restricts the choice, and stops at the next keyword.
  g.send("go searchmoves a2a3 b2b3 depth 1");
  const std::string best = bestmove_of(g.next("bestmove").value_or("bestmove ?"));
  CHECK_MSG(best == "a2a3" || best == "b2b3", best);
  g.send("go infinite searchmoves h2h4");
  CHECK(g.sync());
  g.send("stop");
  CHECK_EQ(g.next("bestmove").value_or(""), std::string("bestmove h2h4"));
  // No legal move in searchmoves (python-chess sends 0000 for an empty list).
  mark = g.cursor;
  g.send("go searchmoves 0000");
  CHECK(g.next("bestmove").has_value());
  CHECK_EQ(g.count("info string go: no legal move in searchmoves", mark), 1);
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "exactly one bestmove per go over a mixed session") {
  Gui g;
  int gos = 0;
  g.send("uci");
  g.send("ucinewgame");
  g.send("position startpos");
  for (int i = 0; i < 20; ++i) {
    g.send("go movetime 1");
    ++gos;
    if (i % 3 == 0) {
      g.send("go infinite");
      ++gos;
      g.send("isready");
      g.send("stop");
    }
    if (i % 5 == 0) g.send("stop");
    g.send("position startpos moves e2e4");
  }
  g.send("go ponder");
  ++gos;
  g.send("ponderhit");
  CHECK(g.next("uciok").has_value());
  for (int i = 0; i < gos; ++i) CHECK(g.next("bestmove").has_value());
  CHECK(g.sync());
  std::this_thread::sleep_for(50ms);
  CHECK_EQ(g.count("bestmove"), gos);
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_protocol", "Fork extensions: d, go perft, bench print only info lines") {
  Gui g;
  g.send("position startpos");
  g.send("go perft 3");
  CHECK(g.next("info string time").has_value());
  CHECK_EQ(g.count("info string nodes 8902"), 1);
  CHECK_EQ(g.count("info string e2e4: 600"), 1);
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_options", "setoption: case, spaces, unknown names, bad values") {
  Gui g;
  CHECK(g.sync());
  std::size_t mark = g.cursor;
  for (const char* good : {"setoption name Threads value 4", "setoption name move overhead value 250",
                           "setoption name   Move \t Overhead   value   0  ",
                           "setoption name THREADS value 1", "setoption name Clear Hash",
                           "setoption name SyzygyPath value <empty>", "setoption name Hash value 1"})
    g.send(good);
  CHECK(g.sync());
  CHECK_EQ(g.count("info string", mark), 1);  // only the allocation report
  CHECK_EQ(g.count("info string Hash 1 MB allocated", mark), 1);
  mark = g.cursor;
  const std::vector<std::string> bad = {"setoption name Ponder value true",
                                        "setoption name Hash value 0",
                                        "setoption name Hash value 33554433",
                                        "setoption name Threads value 1025",
                                        "setoption name Move Overhead value -1",
                                        "setoption name Move Overhead value abc",
                                        "setoption name Threads",
                                        "setoption Threads value 2",
                                        "setoption name Hash value 16 MB",
                                        "setoption name Move Overhead value 5001"};
  for (const std::string& b : bad) g.send(b);
  CHECK(g.sync());
  CHECK_EQ(g.count("info string", mark), static_cast<int>(bad.size()));
  CHECK_EQ(g.count("info string Hash", mark), 3);  // the three rejected Hash values; no reallocation
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_options", "Hash is allocated after all options are set (Threads sent after Hash)") {
  Gui g;
  g.send("setoption name Hash value 256");
  g.send("setoption name Threads value 64");
  CHECK(g.sync());
  // 256 MB in 2 MiB slices allows 128 workers; Threads 64 means 64. Had the
  // table been cleared at setoption Hash, Threads would still have been 1.
  int reports = 0;
  for (const std::string& line : g.texts())
    if (starts_with(line, "info string Hash 256 MB allocated and cleared in")) {
      ++reports;
      CHECK_MSG(line.find(" by 64 threads") != std::string::npos, line);
    }
  CHECK_EQ(reports, 1);
  // Threads 1024: still fine (16 MB allows 8 workers).
  g.send("setoption name Threads value 1024");
  g.send("setoption name Hash value 16");
  CHECK(g.sync());
  CHECK_EQ(g.count("info string Hash 16 MB allocated"), 1);
  g.send("ucinewgame");
  g.send("setoption name Clear Hash");
  CHECK(g.sync());
  CHECK_EQ(g.count("info string Hash"), 2);  // clearing reports nothing
  g.send("go depth 1");
  CHECK(g.next("bestmove").has_value());
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_options", "Hash too large: 1 TB, and just above available memory, fall back cleanly") {
  Gui g;
  CHECK(g.sync());  // 16 MB
  std::size_t mark = g.cursor;
  g.send("setoption name Hash value 1048576");  // 1 TB
  CHECK(g.sync());
  CHECK_EQ(g.count("info string Hash 1048576 MB is more than", mark), 1);
  CHECK_EQ(g.count("info string Hash 16 MB allocated", mark), 1);
  // Just above what is available now (with a margin, as other processes
  // come and go): refused before any page is touched.
  const std::size_t available_mb = available_memory() / BytesPerMB;
  const std::size_t ask = available_mb + std::max<std::size_t>(1024, available_mb / 10);
  mark = g.cursor;
  g.send("setoption name Hash value " + std::to_string(ask));
  CHECK(g.sync());
  CHECK_MSG(g.count("info string Hash " + std::to_string(ask) + " MB is more than", mark) == 1,
            "asked " << ask << " MB with " << available_mb << " MB available");
  CHECK_EQ(g.count("info string Hash 16 MB allocated", mark), 1);
  g.send("go depth 1");  // still plays
  CHECK(g.next("bestmove").has_value());
  g.check_transcript();
  g.quit();
}

TEST_CASE("uci_options", "SyzygyPath counts table files; a missing directory is reported") {
  namespace fs = std::filesystem;
  const fs::path dir = fs::temp_directory_path() / "fork-uci-test-syzygy";
  const fs::path missing = fs::temp_directory_path() / "fork-uci-test-no-such-dir";
  fs::remove_all(dir);
  fs::create_directories(dir);
  for (const char* name : {"KQvK.rtbw", "KQvK.rtbz", "KRvK.rtbw", "notes.txt"})
    std::ofstream(dir / name) << "x";
#ifdef _WIN32
  const char separator = ';';
#else
  const char separator = ':';
#endif
  Gui g;
  g.send("setoption name SyzygyPath value " + dir.string() + separator + missing.string());
  CHECK(g.sync());
  CHECK_EQ(g.count("info string SyzygyPath: 2 WDL and 1 DTZ table files in 1 directories; not found: " +
                   missing.string()),
           1);
  g.check_transcript();
  g.quit();
  fs::remove_all(dir);
}

TEST_CASE("uci_options", "LogFile records input and output with timestamps") {
  namespace fs = std::filesystem;
  const fs::path log = fs::temp_directory_path() / "fork-uci-test-log.txt";
  fs::remove(log);
  Gui g;
  g.send("setoption name LogFile value " + log.string());
  g.send("isready");
  CHECK(g.next("readyok").has_value());
  g.send("setoption name LogFile value <empty>");  // closes it
  const std::size_t mark = g.cursor;
  g.send("setoption name LogFile value " + (fs::temp_directory_path() / "no-such-dir" / "log.txt").string());
  CHECK(g.sync());
  CHECK_EQ(g.count("info string LogFile: cannot open", mark), 1);
  g.quit();
  std::ifstream in(log);
  std::vector<std::string> lines;
  for (std::string line; std::getline(in, line);) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    lines.push_back(line);
  }
  CHECK(!lines.empty());
  // "2026-10-24T12:34:56.789Z > text": digits where the pattern has 9.
  auto stamped = [](const std::string& line) {
    const std::string_view shape = "9999-99-99T99:99:99.999Z ? ";
    if (line.size() < shape.size()) return false;
    for (std::size_t i = 0; i < shape.size(); ++i) {
      const char c = line[i];
      if (shape[i] == '9'   ? !(c >= '0' && c <= '9')
          : shape[i] == '?' ? (c != '<' && c != '>')
                            : c != shape[i])
        return false;
    }
    return true;
  };
  for (const std::string& line : lines) CHECK_MSG(stamped(line), line);
  auto has = [&](std::string_view tail) {
    return std::any_of(lines.begin(), lines.end(), [&](const std::string& l) {
      return l.size() >= tail.size() && l.compare(l.size() - tail.size(), tail.size(), tail) == 0;
    });
  };
  CHECK(has("Z > isready"));
  CHECK(has("Z < readyok"));
  CHECK(has("Z > setoption name LogFile value <empty>"));
  CHECK(!has("Z < info string LogFile: cannot open"));  // sent after the log was closed
  in.close();
  fs::remove(log);
}

}  // namespace forkeng::test
