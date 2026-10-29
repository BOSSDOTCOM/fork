// SPDX-License-Identifier: GPL-3.0-or-later

// fork_datagen: self-play training data (DESIGN.md §5.3, deliverable 2).
// A separate program, never part of the engine binary TCEC builds.
//
// Worker w of T plays games w, w + T, w + 2T, ... and writes them to its own
// shard files, so a run is reproducible byte for byte for the same build,
// openings, settings and worker count. Game g starts from opening perm[g mod
// N], perm being a shuffle of the N openings seeded by --seed, then plays
// --random-min to --random-max uniformly random legal plies drawn from a
// stream seeded by (--seed, g), so an opening used more than once still
// starts different games (owner, 2026-10-28; the search itself is
// deterministic). Each worker stops after the game that brings it to its
// share of --positions. A game that ends before any position is recorded
// is not written.
//
// Outputs in --out: <run>-wWW-KKKK.vf shards (viriformat, game_record.hpp),
// rotated once a shard reaches --shard-mb, and <run>.json: the settings,
// build identity, per-shard counts and the run's statistics. SHA-256s are
// added by tools/datagen's upload step, which reads this file.
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdio>
#include <fstream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "datagen/self_play.hpp"
#include "search/endgame_tables.hpp"
#include "uci/session.hpp"

namespace forkeng {
namespace {

struct Options {
  std::string openings, out_dir, run = "run", tables;
  std::uint64_t positions = 0, nodes = 0, seed = 1;
  int threads = 1;
  std::size_t hash_mb = 16, shard_mb = 1024;
  int decided_cp = 400, max_plies = 500;
  int random_min = 2, random_max = 4;
};

struct ShardInfo {
  std::string file;
  int worker;
  std::uint64_t games = 0, positions = 0, bytes = 0;
};

struct Totals {
  std::mutex mutex;
  std::vector<ShardInfo> shards;
  std::uint64_t ends[GameEndCount] = {};
  std::uint64_t results[3] = {};
  std::atomic<std::uint64_t> games{0}, positions{0};
};

int usage() {
  std::fprintf(stderr,
               "usage: fork_datagen --openings FILE --out DIR --positions N --nodes N\n"
               "         [--threads T] [--seed S] [--run NAME] [--hash-mb M] [--shard-mb M]\n"
               "         [--tables PATH] [--decided-cp CP] [--max-plies P]\n"
               "         [--random-min N] [--random-max N]\n");
  return 2;
}

bool parse(int argc, char** argv, Options& o) {
  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    if (i + 1 >= argc) return false;
    const std::string v = argv[++i];
    try {
      if (a == "--openings")
        o.openings = v;
      else if (a == "--out")
        o.out_dir = v;
      else if (a == "--run")
        o.run = v;
      else if (a == "--tables")
        o.tables = v;
      else if (a == "--positions")
        o.positions = std::stoull(v);
      else if (a == "--nodes")
        o.nodes = std::stoull(v);
      else if (a == "--seed")
        o.seed = std::stoull(v);
      else if (a == "--threads")
        o.threads = std::stoi(v);
      else if (a == "--hash-mb")
        o.hash_mb = std::stoull(v);
      else if (a == "--shard-mb")
        o.shard_mb = std::stoull(v);
      else if (a == "--decided-cp")
        o.decided_cp = std::stoi(v);
      else if (a == "--max-plies")
        o.max_plies = std::stoi(v);
      else if (a == "--random-min")
        o.random_min = std::stoi(v);
      else if (a == "--random-max")
        o.random_max = std::stoi(v);
      else
        return false;
    } catch (const std::exception&) {
      return false;
    }
  }
  return !o.openings.empty() && !o.out_dir.empty() && o.positions > 0 && o.nodes > 0 && o.threads > 0 &&
         o.hash_mb > 0 && o.shard_mb > 0 && o.max_plies > 0 && 0 <= o.random_min && o.random_min <= o.random_max;
}

std::string shard_name(const Options& o, int worker, int index) {
  char buf[64];
  std::snprintf(buf, sizeof buf, "-w%02d-%04d.vf", worker, index);
  return o.run + buf;
}

void run_worker(const Options& o, int worker, const std::vector<std::string>& openings,
                const std::vector<std::uint32_t>& order, Totals& totals, std::atomic<bool>& failed) {
  SelfPlayConfig config;
  config.nodes = o.nodes;
  config.hash_bytes = o.hash_mb << 20;
  config.decided_cp = o.decided_cp;
  config.max_plies = o.max_plies;
  std::string report;
  auto player = SelfPlayGame::create(config, report);
  if (!player) {
    std::fprintf(stderr, "worker %d: %s\n", worker, report.c_str());
    failed = true;
    return;
  }
  const std::uint64_t quota = (o.positions + static_cast<std::uint64_t>(o.threads) - 1) / o.threads;
  GameWriter writer;
  ShardInfo shard;
  std::ofstream file;
  int shard_index = 0;
  auto close_shard = [&] {
    if (!file.is_open()) return;
    file.close();
    if (shard.games) {
      std::lock_guard lock(totals.mutex);
      totals.shards.push_back(shard);
    }
  };
  std::uint64_t written = 0;
  for (std::uint64_t g = static_cast<std::uint64_t>(worker); written < quota && !failed; g += o.threads) {
    // FENs, not Positions, are kept: every Position reserves its state
    // history (about 57 KB), too much for millions of openings.
    Position opening;
    opening.set_fen(openings[order[g % order.size()]]);  // checked when loaded
    std::uint64_t stream = splitmix_finalize(o.seed ^ splitmix_finalize(g + 1));
    const int plies = o.random_min + static_cast<int>(splitmix_next(stream) %
                                                      static_cast<std::uint64_t>(o.random_max - o.random_min + 1));
    for (int i = 0; i < plies; ++i) {
      MoveList legal;
      generate<GenMode::Legal>(opening, legal);
      if (legal.size() == 0) break;
      opening.make(legal[splitmix_next(stream) % legal.size()]);
    }
    const SelfPlayOutcome outcome = player->play(opening, writer);
    {
      std::lock_guard lock(totals.mutex);
      ++totals.ends[static_cast<int>(outcome.end)];
      if (outcome.written) ++totals.results[static_cast<int>(outcome.result)];
    }
    if (!outcome.written || writer.positions() == 0) continue;
    if (!file.is_open()) {
      shard = ShardInfo{shard_name(o, worker, shard_index++), worker};
      file.open(o.out_dir + "/" + shard.file, std::ios::binary | std::ios::trunc);
      if (!file) {
        std::fprintf(stderr, "worker %d: cannot create %s\n", worker, shard.file.c_str());
        failed = true;
        return;
      }
    }
    const auto bytes = writer.bytes();
    file.write(reinterpret_cast<const char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    file.flush();
    if (!file) {
      std::fprintf(stderr, "worker %d: write failed on %s\n", worker, shard.file.c_str());
      failed = true;
      return;
    }
    shard.games += 1;
    shard.positions += static_cast<std::uint64_t>(writer.positions());
    shard.bytes += bytes.size();
    written += static_cast<std::uint64_t>(writer.positions());
    totals.games += 1;
    totals.positions += static_cast<std::uint64_t>(writer.positions());
    if (shard.bytes >= (o.shard_mb << 20)) close_shard();
  }
  close_shard();
}

void write_manifest(const Options& o, const Totals& t, double seconds, std::size_t opening_count) {
  std::ofstream f(o.out_dir + "/" + o.run + ".json", std::ios::trunc);
  f << "{\n  \"tool\": \"fork_datagen\",\n  \"version\": \"" << engine_version() << "\",\n"
    << "  \"evaluator\": \"" << FORK_EVALUATOR_NAME << "\",\n"
    << "  \"arch\": \"" << FORK_ARCH_NAME << "\",\n"
    << "  \"settings\": {\"openings\": \""
    << std::string(o.openings.substr(o.openings.find_last_of("/\\") + 1))
    << "\", \"openings_count\": " << opening_count << ", \"positions_target\": " << o.positions
    << ", \"nodes\": " << o.nodes << ", \"threads\": " << o.threads << ", \"seed\": " << o.seed
    << ", \"hash_mb\": " << o.hash_mb << ", \"shard_mb\": " << o.shard_mb << ", \"tables\": \""
    << (o.tables.empty() ? "none" : "syzygy " + std::to_string(endgame_table_pieces()) + "-piece")
    << "\", \"decided_cp\": " << o.decided_cp << ", \"max_plies\": " << o.max_plies
    << ", \"random_min\": " << o.random_min << ", \"random_max\": " << o.random_max << "},\n"
    << "  \"games\": " << t.games.load() << ",\n  \"positions\": " << t.positions.load() << ",\n"
    << "  \"seconds\": " << seconds << ",\n  \"results\": {\"white\": " << t.results[2]
    << ", \"draw\": " << t.results[1] << ", \"black\": " << t.results[0] << "},\n  \"ends\": {";
  for (int i = 0; i < GameEndCount; ++i)
    f << (i ? ", " : "") << '"' << game_end_name(static_cast<GameEnd>(i)) << "\": " << t.ends[i];
  f << "},\n  \"shards\": [\n";
  for (std::size_t i = 0; i < t.shards.size(); ++i) {
    const ShardInfo& s = t.shards[i];
    f << "    {\"file\": \"" << s.file << "\", \"worker\": " << s.worker << ", \"games\": " << s.games
      << ", \"positions\": " << s.positions << ", \"bytes\": " << s.bytes << '}'
      << (i + 1 < t.shards.size() ? ",\n" : "\n");
  }
  f << "  ]\n}\n";
}

int run(int argc, char** argv) {
  Options o;
  if (!parse(argc, argv, o)) return usage();
  init();

  std::vector<std::string> openings;
  {
    std::ifstream in(o.openings);
    if (!in) {
      std::fprintf(stderr, "cannot read %s\n", o.openings.c_str());
      return 1;
    }
    std::string line, error;
    for (int n = 1; std::getline(in, line); ++n) {
      if (!line.empty() && line.back() == '\r') line.pop_back();
      if (line.empty() || line[0] == '#') continue;  // blank lines and comments
      Position check;
      if (!check.set_fen(line, &error)) {
        std::fprintf(stderr, "%s:%d: %s\n", o.openings.c_str(), n, error.c_str());
        return 1;
      }
      openings.push_back(line);
    }
  }
  if (openings.empty()) {
    std::fprintf(stderr, "no openings in %s\n", o.openings.c_str());
    return 1;
  }
  if (openings.size() > UINT32_MAX) return 1;
  if (!o.tables.empty()) std::fprintf(stderr, "%s\n", load_endgame_tables(o.tables).c_str());

  // Fisher-Yates over the opening indices, from Fork's splitmix stream.
  std::vector<std::uint32_t> order(openings.size());
  for (std::uint32_t i = 0; i < order.size(); ++i) order[i] = i;
  std::uint64_t state = o.seed;
  for (std::size_t i = order.size() - 1; i > 0; --i)
    std::swap(order[i], order[splitmix_next(state) % (i + 1)]);

  Totals totals;
  std::atomic<bool> failed{false};
  const auto start = std::chrono::steady_clock::now();
  std::vector<std::thread> workers;
  for (int w = 0; w < o.threads; ++w)
    workers.emplace_back(run_worker, std::cref(o), w, std::cref(openings), std::cref(order), std::ref(totals),
                         std::ref(failed));
  std::atomic<bool> done{false};
  std::thread progress([&] {
    auto next = start + std::chrono::seconds(30);
    while (!done) {
      std::this_thread::sleep_for(std::chrono::milliseconds(200));
      if (std::chrono::steady_clock::now() < next) continue;
      next += std::chrono::seconds(30);
      const double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
      std::fprintf(stderr, "%.0f s: %" PRIu64 " games, %" PRIu64 " positions, %.0f positions/s\n", s,
                   totals.games.load(), totals.positions.load(),
                   static_cast<double>(totals.positions.load()) / s);
    }
  });
  for (auto& t : workers) t.join();
  done = true;
  progress.join();
  const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
  write_manifest(o, totals, seconds, openings.size());
  std::fprintf(stderr, "done: %" PRIu64 " games, %" PRIu64 " positions in %.1f s (%.0f positions/s)\n",
               totals.games.load(), totals.positions.load(), seconds,
               static_cast<double>(totals.positions.load()) / seconds);
  return failed ? 1 : 0;
}

}  // namespace
}  // namespace forkeng

int main(int argc, char** argv) { return forkeng::run(argc, argv); }
