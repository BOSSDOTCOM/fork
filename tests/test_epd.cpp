// Large public perft suites, downloaded at configure time (not committed; see
// docs/ORIGINALITY.md) and checked against a pinned SHA-256 by CMake:
//   perftsuite.epd   126 positions to depth 6 (the Roce suite, via Mediocre)
//   perft-random.epd 6838 random positions to depth 6 (Marcel van Kervinck, Rookie)
// Positions are spread over all cores; each worker has its own Position.
#include <atomic>
#include <fstream>
#include <mutex>
#include <sstream>
#include <thread>

#include "core/perft.hpp"
#include "harness.hpp"

using namespace forkeng;
using namespace forkeng::test;

namespace {

struct EpdEntry {
  std::string fen;
  std::vector<std::uint64_t> counts;  // counts[d - 1]
};

std::string data_path(const char* name) { return std::string(FORK_EPD_DIR) + "/" + name; }

// "FEN ;D1 20 ;D2 400 ..." per line.
std::vector<EpdEntry> load_perftsuite() {
  std::vector<EpdEntry> out;
  std::ifstream in(data_path("perftsuite.epd"));
  std::string line;
  while (std::getline(in, line)) {
    std::size_t semi = line.find(';');
    if (semi == std::string::npos) continue;
    EpdEntry e{line.substr(0, semi), {}};
    std::istringstream ss(line.substr(semi));
    std::string tag;
    std::uint64_t n;
    while (ss >> tag >> n) e.counts.push_back(n);  // tags are ;D1 ;D2 ... in order
    out.push_back(e);
  }
  return out;
}

// Blocks of "epd <4-field FEN>" followed by "perft <d> <n>" lines.
std::vector<EpdEntry> load_perft_random() {
  std::vector<EpdEntry> out;
  std::ifstream in(data_path("perft-random.epd"));
  std::string line;
  while (std::getline(in, line)) {
    if (line.starts_with("epd ")) {
      out.push_back({line.substr(4), {}});
    } else if (line.starts_with("perft ") && !out.empty()) {
      std::istringstream ss(line.substr(6));
      std::size_t d;
      std::uint64_t n;
      ss >> d >> n;
      if (out.back().counts.size() + 1 == d) out.back().counts.push_back(n);
    }
  }
  return out;
}

// Runs every entry to min(max_depth, deepest count) on all cores.
void run(const std::vector<EpdEntry>& entries, std::size_t expected_entries, int max_depth,
         const char* name) {
  CHECK_MSG(entries.size() == expected_entries, name << ": loaded " << entries.size()
                                                     << " positions, expected " << expected_entries
                                                     << " (missing download? see CMake configure output)");
  std::atomic<std::size_t> next{0};
  std::mutex mutex;
  std::vector<std::string> failures;
  std::uint64_t total = 0;
  auto worker = [&] {
    std::uint64_t local = 0;
    for (std::size_t i; (i = next++) < entries.size();) {
      const EpdEntry& e = entries[i];
      Position pos;
      std::string error;
      if (!pos.set_fen(e.fen, &error)) {
        std::scoped_lock lock(mutex);
        failures.push_back(e.fen + ": " + error);
        continue;
      }
      int depth = std::min<int>(max_depth, static_cast<int>(e.counts.size()));
      std::uint64_t nodes = perft(pos, depth);
      local += nodes;
      if (nodes != e.counts[depth - 1]) {
        std::scoped_lock lock(mutex);
        failures.push_back(e.fen + " depth " + std::to_string(depth) + ": got " + std::to_string(nodes) +
                           ", expected " + std::to_string(e.counts[depth - 1]));
      }
    }
    std::scoped_lock lock(mutex);
    total += local;
  };
  std::vector<std::thread> threads;
  unsigned n = std::max(1u, std::thread::hardware_concurrency());
  threads.reserve(n);
  for (unsigned t = 0; t < n; ++t) threads.emplace_back(worker);
  for (std::thread& t : threads) t.join();
  for (const std::string& f : failures) CHECK_MSG(false, name << ": " << f);
  std::printf("  %s: %zu positions to depth <= %d, %llu nodes, %zu mismatches\n", name, entries.size(),
              max_depth, static_cast<unsigned long long>(total), failures.size());
}

}  // namespace

TEST_CASE("perft_epd", "perftsuite.epd and perft-random.epd") {
  run(load_perftsuite(), 126, Optimized ? 6 : 4, "perftsuite");
  run(load_perft_random(), 6838, Optimized ? 4 : 3, "perft-random");
}

TEST_CASE("perft_epd_deep", "perft-random.epd to depth 5") {
  run(load_perft_random(), 6838, 5, "perft-random");
}

TEST_CASE("perft_epd_full", "perft-random.epd to depth 6 (sign-off run)") {
  run(load_perft_random(), 6838, 6, "perft-random");
}
