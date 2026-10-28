// Syzygy endgame tables through Fathom (DESIGN.md §5.2, deliverable 7).
//
// The 7-piece cases use the smallest 7-man pair, KPPPPPvK, downloaded by
// CMake into .cache/syzygy7 with pinned SHA-256s (KB tools.md §6.9). Their
// positions and answers are from the KB record of 2026-10-26 (tools.md §6.9),
// where Fathom at the pin and the lichess tablebase API agreed:
//   k7/8/8/8/8/8/PPPPP3/7K w - - 0 1: win, 13 winning moves;
//   k7/8/8/8/8/8/PPPPP3/7K b - - 0 1: loss, 3 legal moves, all losing.
// No capture is possible in them, so no smaller table is needed.
// The 3-4-5 cases use a few small tables in .cache/syzygy345, downloaded the
// same way (CMakeLists.txt); their positions are cited below.
#include <algorithm>
#include <atomic>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "core/movegen.hpp"
#include "harness.hpp"
#include "search/endgame_tables.hpp"
#include "search/score_bounds.hpp"
#include "search/searcher.hpp"

namespace forkeng::test {

namespace {

constexpr std::string_view WhiteWins = "k7/8/8/8/8/8/PPPPP3/7K w - - 0 1";
constexpr std::string_view BlackLoses = "k7/8/8/8/8/8/PPPPP3/7K b - - 0 1";

std::string seven_man_dir() { return FORK_SYZYGY7_DIR; }

// Every file named is in `dir`; a missing one is a failure, not a skip: CMake
// downloads them, and a skip let a failed download pass unseen (audit-1 Q-6).
bool tables_present(const std::string& dir, std::initializer_list<const char*> files) {
  bool all = true;
  for (const char* f : files) {
    const bool here = std::filesystem::exists(dir + "/" + f);
    CHECK_MSG(here, f << " is missing from " << dir << " (CMake downloads it)");
    all = all && here;
  }
  return all;
}

bool seven_man_present() { return tables_present(seven_man_dir(), {"KPPPPPvK.rtbw", "KPPPPPvK.rtbz"}); }

Position at(std::string_view fen) {
  Position pos;
  CHECK_MSG(pos.set_fen(fen), fen);
  return pos;
}

// Records the probe count each iteration reports (UCI tbhits).
struct TableHitCounter final : SearchListener {
  std::uint64_t hits = 0;
  void on_iteration(const Position&, const IterationReport& r) override { hits = r.table_hits; }
};

// A fresh directory under the system temp folder, removed at the end.
struct ScratchDir {
  std::filesystem::path path;
  explicit ScratchDir(const char* name) : path(std::filesystem::temp_directory_path() / name) {
    std::filesystem::remove_all(path);
    std::filesystem::create_directories(path);
  }
  ~ScratchDir() {
    load_endgame_tables("");  // release the mappings before deleting
    std::error_code ec;
    std::filesystem::remove_all(path, ec);
  }
};

}  // namespace

TEST_CASE("tables", "no tables: an empty path, a missing directory, an empty directory") {
  load_endgame_tables("");
  CHECK_EQ(endgame_table_pieces(), 0);
  CHECK(!probe_table_wdl(at(WhiteWins)).has_value());
  MoveList kept;
  CHECK(!rank_root_by_tables(at(WhiteWins), false, kept) && kept.size() == 0);
  load_endgame_tables((std::filesystem::temp_directory_path() / "fork-no-such-dir").string());
  CHECK_EQ(endgame_table_pieces(), 0);
  ScratchDir empty("fork-tables-empty");
  load_endgame_tables(empty.path.string());
  CHECK_EQ(endgame_table_pieces(), 0);
  CHECK(!probe_table_wdl(at(BlackLoses)).has_value());
}

// Audit-1, R-1: Fathom's tb_init counts a separator at the end of the path as
// one more, empty, directory and then reads past its copy of the string
// looking for it (a heap-buffer-overflow under ASan in the clang-debug build).
TEST_CASE("tables", "empty directories in the path (a trailing separator, or only one) are ignored") {
#ifdef _WIN32
  const std::string separator = ";";
#else
  const std::string separator = ":";
#endif
  for (const std::string& path : {separator, separator + separator}) {
    CHECK_MSG(load_endgame_tables(path).find("no tables") != std::string::npos, "path '" << path << "'");
    CHECK_EQ(endgame_table_pieces(), 0);
  }
  if (seven_man_present()) {
    for (const std::string& path : {seven_man_dir() + separator, separator + seven_man_dir() + separator}) {
      CHECK_MSG(load_endgame_tables(path).find("7 pieces") != std::string::npos, "path '" << path << "'");
      CHECK_EQ(endgame_table_pieces(), 7);
    }
  }
  load_endgame_tables("");
}

TEST_CASE("tables", "7 pieces: the largest count comes from the files, and the probes answer") {
  if (!seven_man_present()) return;
  CHECK(load_endgame_tables(seven_man_dir()).find("7 pieces") != std::string::npos);
  CHECK_EQ(endgame_table_pieces(), 7);
  const auto w = probe_table_wdl(at(WhiteWins));
  CHECK(w.has_value() && *w == TableWdl::Win);
  const auto b = probe_table_wdl(at(BlackLoses));
  CHECK(b.has_value() && *b == TableWdl::Loss);
  // The fifty-move-safe conditions: a running halfmove clock gets no answer.
  CHECK(!probe_table_wdl(at("k7/8/8/8/8/8/PPPPP3/7K w - - 3 1")).has_value());
  // More pieces than the tables cover: no answer.
  CHECK(!probe_table_wdl(at("k7/p7/8/8/8/8/PPPPP3/7K w - - 0 1")).has_value());
  load_endgame_tables("");
}

TEST_CASE("tables", "root ranking keeps every winning move, and all of a lost side's moves") {
  if (!seven_man_present()) return;
  load_endgame_tables(seven_man_dir());
  MoveList kept;
  CHECK(rank_root_by_tables(at(WhiteWins), false, kept));
  CHECK_EQ(kept.size(), std::size_t{13});
  const Position w = at(WhiteWins);
  MoveList legal;
  generate<GenMode::Legal>(w, legal);
  for (Move m : kept) CHECK(legal.contains(m));
  CHECK(rank_root_by_tables(at(BlackLoses), false, kept));
  CHECK_EQ(kept.size(), std::size_t{3});
  load_endgame_tables("");
}

TEST_CASE("tables", "a path with only the win/draw/loss file: probes work, the root ranks by it") {
  if (!seven_man_present()) return;
  ScratchDir partial("fork-tables-wdl-only");
  std::filesystem::copy_file(seven_man_dir() + "/KPPPPPvK.rtbw", partial.path / "KPPPPPvK.rtbw");
  load_endgame_tables(partial.path.string());
  CHECK_EQ(endgame_table_pieces(), 7);
  const auto w = probe_table_wdl(at(WhiteWins));
  CHECK(w.has_value() && *w == TableWdl::Win);
  MoveList kept;
  CHECK(rank_root_by_tables(at(WhiteWins), false, kept));  // the win/draw/loss fallback
  CHECK_EQ(kept.size(), std::size_t{13});
}

TEST_CASE("tables", "the search reports the tables' result and counts its probes") {
  if (!seven_man_present()) return;
  load_endgame_tables(seven_man_dir());
  std::vector<TtBucket> buckets(16384);
  TransTable tt;
  tt.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  auto searcher = std::make_unique<Searcher>(tt);
  const std::atomic<bool> stop{false};
  SearchQuota q;
  q.depth = 6;
  Position w = at(WhiteWins);
  TableHitCounter counter;
  const SearchResult rw = searcher->deliberate(w, q, stop, nullptr, &counter);
  CHECK_MSG(rw.score >= TbWinScore - MaxPly && rw.score < MateScore - MaxPly, "score " << rw.score);
  CHECK_MSG(counter.hits > 0, "tbhits " << counter.hits);
  Position b = at(BlackLoses);
  const SearchResult rb = searcher->deliberate(b, q, stop, nullptr, nullptr);
  CHECK_MSG(rb.score <= -(TbWinScore - MaxPly) && rb.score > -(MateScore - MaxPly), "score " << rb.score);
  // Off: the same search knows only its evaluation.
  searcher->switches.use_tables = false;
  Position w2 = at(WhiteWins);
  CHECK(!is_tb_or_mate(searcher->deliberate(w2, q, stop, nullptr, nullptr).score));
  load_endgame_tables("");
}

// ---- The 3-4-5 tables (audit-1 Q-6) ----
// Only the KPPPPPvK pair was used before, so only wins and losses were ever
// probed: draws, cursed wins, blessed losses, promotions, the root ranking's
// repetition rule and its filter were untested (mutants M34-M37 passed every
// test). The positions are constructed (found with python-chess's own Syzygy
// prober on these files) and each result below is the lichess tablebase API's
// (https://tablebase.lichess.ovh/standard?fen=<FEN>, fetched 2026-10-27;
// Syzygy, the fifty-move rule counted; a move's category is the opponent's
// after it). Legality and the mates are checked by
// tools/check_search_positions.py.
namespace {

std::string small_dir() { return FORK_SYZYGY345_DIR; }

bool small_present() {
  return tables_present(small_dir(), {"KPvK.rtbw", "KQvK.rtbw", "KRvK.rtbw", "KBvK.rtbw", "KNvK.rtbw",
                                      "KQvKP.rtbw", "KNNvKP.rtbw", "KNNvK.rtbw", "KNvKP.rtbw", "KPvK.rtbz",
                                      "KQvK.rtbz", "KRvK.rtbz", "KBvK.rtbz", "KNvK.rtbz"});
}

// The moves the root ranking keeps, as sorted UCI texts.
std::vector<std::string> kept_moves(const Position& pos, bool repeated) {
  MoveList kept;
  CHECK_MSG(rank_root_by_tables(pos, repeated, kept), pos.fen());
  std::vector<std::string> out;
  for (Move m : kept) out.push_back(pos.move_to_uci(m));
  std::sort(out.begin(), out.end());
  return out;
}

std::string joined(const std::vector<std::string>& moves) {
  std::string s;
  for (const std::string& m : moves) s += (s.empty() ? "" : " ") + m;
  return s;
}

// A fresh search with the tables loaded and default switches.
SearchResult search_tables(Position& pos, int depth) {
  std::vector<TtBucket> buckets(16384);
  TransTable tt;
  tt.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  auto searcher = std::make_unique<Searcher>(tt);
  const std::atomic<bool> stop{false};
  SearchQuota q;
  q.depth = depth;
  return searcher->deliberate(pos, q, stop, nullptr, nullptr);
}

// The API's results, cited above:
// KNNvKP, Black to move: blessed loss (dtz -111); every Black move, a5a4
// included, leaves White a cursed win.
constexpr std::string_view BlessedLossFen = "8/8/8/pK6/5k1N/8/2N5/8 b - - 0 1";
// After a5a4, White to move: cursed win (dtz 124); only c2a3 keeps it (to a
// blessed loss), every other move draws.
constexpr std::string_view CursedWinFen = "8/8/8/1K6/p4k1N/8/2N5/8 w - - 0 1";
// KPvK, White to move: a draw; all six moves draw.
constexpr std::string_view KpkDraw = "k7/8/8/8/2P5/8/8/6K1 w - - 0 1";
// KPvK, White to move: a win; b7b8q, b7b8r and the eight king moves win,
// b7b8b and b7b8n draw.
constexpr std::string_view KpkPromotion = "8/1P6/8/2k2K2/8/8/8/8 w - - 0 1";
// KPvK, White to move: a win only by h3h4; g2g3, g2g4, h3h2 and h3g3 draw.
constexpr std::string_view KpkOneWin = "8/8/8/5k2/8/7K/6P1/8 w - - 0 1";
// KQvKP, Black to move: a loss; c7c6 and c7c5 are its only moves, each
// answered by a mate in one (python-chess).
constexpr std::string_view KqkpMated = "8/2p5/8/8/2Q5/k7/2K5/8 b - - 0 1";
// KQvK, White to move: a win; g1c5 alone reaches the smallest DTZ (its
// child's -10; the other winning moves -12 to -18), and g1e3, g1d4 draw.
constexpr std::string_view KqkFastest = "8/8/8/8/6K1/3k4/8/6Q1 w - - 0 1";

}  // namespace

TEST_CASE("tables", "3-4-5: draw, cursed win, blessed loss, win and loss probes") {
  if (!small_present()) return;
  CHECK(load_endgame_tables(small_dir()).find("5 pieces") != std::string::npos);
  struct Probe {
    std::string_view fen;
    TableWdl wdl;
  };
  for (const Probe& p :
       {Probe{BlessedLossFen, TableWdl::BlessedLoss}, Probe{CursedWinFen, TableWdl::CursedWin},
        Probe{KpkDraw, TableWdl::Draw}, Probe{KpkPromotion, TableWdl::Win}, Probe{KqkpMated, TableWdl::Loss},
        Probe{KqkFastest, TableWdl::Win}}) {
    const std::optional<TableWdl> w = probe_table_wdl(at(p.fen));
    CHECK_MSG(w.has_value() && *w == p.wdl, p.fen << ": " << (w ? static_cast<int>(*w) : 99));
  }
  load_endgame_tables("");
}

TEST_CASE("tables", "3-4-5 root ranking: a draw keeps every move, a promotion, the WDL fallback") {
  if (!small_present()) return;
  load_endgame_tables(small_dir());
  CHECK_EQ(joined(kept_moves(at(KpkDraw), false)), std::string("c4c5 g1f1 g1f2 g1g2 g1h1 g1h2"));
  // Every winning move, the queen and rook promotions among them.
  CHECK_EQ(joined(kept_moves(at(KpkPromotion), false)),
           std::string("b7b8q b7b8r f5e4 f5e5 f5e6 f5f4 f5f6 f5g4 f5g5 f5g6"));
  CHECK_EQ(joined(kept_moves(at(KpkOneWin), false)), std::string("h3h4"));
  // No KNNvKP distance-to-zero file here: the ranking falls back to the
  // win/draw/loss tables, and only c2a3 keeps the cursed win.
  CHECK_EQ(joined(kept_moves(at(CursedWinFen), false)), std::string("c2a3"));
  load_endgame_tables("");
}

// M34 (a cursed win scored as a blessed loss): a5a4 resets the clock, so the
// child is probed (a cursed win for White, TableNearDrawScore); Black's king
// moves leave the clock running and are searched (two knights down). The
// root score is minus the near-draw score.
TEST_CASE("tables", "3-4-5 search: a blessed loss scores just below a draw") {
  if (!small_present()) return;
  load_endgame_tables(small_dir());
  Position pos = at(BlessedLossFen);
  const SearchResult r = search_tables(pos, 3);
  CHECK_MSG(r.score == -1 && pos.move_to_uci(r.best) == "a5a4",
            "score " << r.score << ", move " << pos.move_to_uci(r.best));
  load_endgame_tables("");
}

// M35 (a tablebase win taken as exact): after either pawn move the child is
// a probed win for White, a lower bound only: the search must go on and find
// the mate in one behind it.
TEST_CASE("tables", "3-4-5 search: a tablebase win is a lower bound, a mate behind it is found") {
  if (!small_present()) return;
  load_endgame_tables(small_dir());
  Position pos = at(KqkpMated);
  CHECK_EQ(search_tables(pos, 3).score, mated_score(2));
  load_endgame_tables("");
}

// M37 (the root keeps every move): at depth 1 the evaluation alone decides
// among the moves searched; only h3h4 wins.
TEST_CASE("tables", "3-4-5 search: only the moves the tables keep are searched") {
  if (!small_present()) return;
  load_endgame_tables(small_dir());
  Position pos = at(KpkOneWin);
  CHECK_EQ(pos.move_to_uci(search_tables(pos, 1).best), std::string("h3h4"));
  load_endgame_tables("");
}

// M36 (the ranking ignores an earlier repetition): after a king shuffle back
// to the position (g4h5 d3e4 h5g4 e4d3, clock 4), the ranking must avoid
// walking into a repetition and keep only the fastest win, g1c5; without the
// repetition every winning move ranks the same.
TEST_CASE("tables", "3-4-5 root ranking: after a repetition only the fastest win is kept") {
  if (!small_present()) return;
  load_endgame_tables(small_dir());
  Position pos = at(KqkFastest);
  CHECK_EQ(kept_moves(pos, false).size(), std::size_t{22});
  for (const char* uci : {"g4h5", "d3e4", "h5g4", "e4d3"}) {
    const Move m = pos.parse_uci(uci);
    CHECK_MSG(!m.is_none(), uci);
    if (!m.is_none()) pos.make(m);
  }
  CHECK_EQ(pos.repetition_count(), 2);
  CHECK_EQ(joined(kept_moves(pos, true)), std::string("g1c5"));
  CHECK_EQ(pos.move_to_uci(search_tables(pos, 1).best), std::string("g1c5"));
  load_endgame_tables("");
}

#ifdef __linux__
// TCEC asks 7-man users to advise random access on the mapped tables
// (MADV_RANDOM, KB competition.md); Fathom does so when tbprobe.c is built
// as C++ (CMakeLists.txt). The kernel marks such mappings "rr" in VmFlags.
TEST_CASE("tables", "Linux: the mapped tables are advised random access (MADV_RANDOM)") {
  if (!seven_man_present()) return;
  load_endgame_tables(seven_man_dir());
  CHECK(probe_table_wdl(at(WhiteWins)).has_value());  // tables map lazily, on the first probe
  std::ifstream smaps("/proc/self/smaps");
  std::string line;
  bool in_table = false, found = false, random = false;
  while (std::getline(smaps, line)) {
    if (line.find("KPPPPPvK.rtbw") != std::string::npos) {
      in_table = found = true;
    } else if (in_table && line.rfind("VmFlags:", 0) == 0) {
      random = line.find(" rr") != std::string::npos;
      in_table = false;
    }
  }
  CHECK_MSG(found, "KPPPPPvK.rtbw is not mapped");
  CHECK_MSG(random, "KPPPPPvK.rtbw is mapped without the random-access advice");
  load_endgame_tables("");
}
#endif

}  // namespace forkeng::test
