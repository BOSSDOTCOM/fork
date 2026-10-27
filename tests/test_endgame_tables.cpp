// Syzygy endgame tables through Fathom (DESIGN.md §5.2, deliverable 7).
//
// The 7-piece cases use the smallest 7-man pair, KPPPPPvK, downloaded by
// CMake into .cache/syzygy7 with pinned SHA-256s (KB tools.md §6.9). Their
// positions and answers are from the KB record of 2026-10-26 (tools.md §6.9),
// where Fathom at the pin and the lichess tablebase API agreed:
//   k7/8/8/8/8/8/PPPPP3/7K w - - 0 1: win, 13 winning moves;
//   k7/8/8/8/8/8/PPPPP3/7K b - - 0 1: loss, 3 legal moves, all losing.
// No capture is possible in them, so no smaller table is needed.
#include <atomic>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
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

bool seven_man_present() {
  return std::filesystem::exists(seven_man_dir() + "/KPPPPPvK.rtbw") &&
         std::filesystem::exists(seven_man_dir() + "/KPPPPPvK.rtbz");
}

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

TEST_CASE("tables", "7 pieces: the largest count comes from the files, and the probes answer") {
  if (!seven_man_present())
    SKIP("the KPPPPPvK pair is missing from " << seven_man_dir() << " (CMake downloads it)");
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
  if (!seven_man_present())
    SKIP("the KPPPPPvK pair is missing from " << seven_man_dir() << " (CMake downloads it)");
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
  if (!seven_man_present())
    SKIP("the KPPPPPvK pair is missing from " << seven_man_dir() << " (CMake downloads it)");
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
  if (!seven_man_present())
    SKIP("the KPPPPPvK pair is missing from " << seven_man_dir() << " (CMake downloads it)");
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

#ifdef __linux__
// TCEC asks 7-man users to advise random access on the mapped tables
// (MADV_RANDOM, KB competition.md); Fathom does so when tbprobe.c is built
// as C++ (CMakeLists.txt). The kernel marks such mappings "rr" in VmFlags.
TEST_CASE("tables", "Linux: the mapped tables are advised random access (MADV_RANDOM)") {
  if (!seven_man_present())
    SKIP("the KPPPPPvK pair is missing from " << seven_man_dir() << " (CMake downloads it)");
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
