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
// deterministic). With the split search on (--save-percent below 100),
// game g's save decisions come from their own stream, seeded by finalizing
// the random plies' seed. Each worker stops after the game that brings it to its
// share of --positions. A game that ends before any position is recorded
// is not written.
//
// --interleave K (K > 1 only in FORK_DATAGEN_INTERLEAVE builds, a prototype
// of ideas.md idea 165) plays a worker's games K at a time on its one
// thread, switching game at every search node, and commits them in the same
// order: the shards are byte for byte those of --interleave 1.
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
#include <map>
#include <memory>
#include <mutex>
#include <span>
#include <string>
#include <thread>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "datagen/self_play.hpp"
#ifdef FORK_DATAGEN_INTERLEAVE
#include "datagen/game_fibers.hpp"
#endif
#include "search/endgame_tables.hpp"
#include "uci/session.hpp"

namespace forkeng {
namespace {

struct Options {
  std::string openings, out_dir, run = "run", tables;
  std::uint64_t positions = 0, nodes = 0, seed = 1;
  int threads = 1;
  int interleave = 1;  // games per worker thread (FORK_DATAGEN_INTERLEAVE builds)
  std::size_t hash_mb = 16, shard_mb = 1024;
  int decided_cp = 400, max_plies = 500;
  int random_min = 2, random_max = 4;
  int adjudicate_cp = 0, adjudicate_plies = 0;
  int save_percent = 100;
  std::uint64_t unsaved_nodes = 0, check_nodes = 0;
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
  std::atomic<std::uint64_t> games{0}, positions{0}, unsaved{0}, nodes_spent{0};
};

int usage() {
  std::fprintf(stderr,
               "usage: fork_datagen --openings FILE --out DIR --positions N --nodes N\n"
               "         [--threads T] [--seed S] [--run NAME] [--hash-mb M] [--shard-mb M]\n"
               "         [--tables PATH] [--decided-cp CP] [--max-plies P]\n"
               "         [--random-min N] [--random-max N]\n"
               "         [--adjudicate-cp CP --adjudicate-plies N]\n"
               "         [--save-percent P --unsaved-nodes N] [--check-nodes N]\n"
               "         [--interleave K]   (K > 1 only in FORK_DATAGEN_INTERLEAVE builds)\n");
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
      else if (a == "--interleave")
        o.interleave = std::stoi(v);
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
      else if (a == "--adjudicate-cp")
        o.adjudicate_cp = std::stoi(v);
      else if (a == "--adjudicate-plies")
        o.adjudicate_plies = std::stoi(v);
      else if (a == "--save-percent")
        o.save_percent = std::stoi(v);
      else if (a == "--unsaved-nodes")
        o.unsaved_nodes = std::stoull(v);
      else if (a == "--check-nodes")
        o.check_nodes = std::stoull(v);
      else
        return false;
    } catch (const std::exception&) {
      return false;
    }
  }
  return !o.openings.empty() && !o.out_dir.empty() && o.positions > 0 && o.nodes > 0 && o.threads > 0 &&
         o.hash_mb > 0 && o.shard_mb > 0 && o.max_plies > 0 && 0 <= o.random_min &&
         o.random_min <= o.random_max && o.adjudicate_cp >= 0 && o.adjudicate_plies >= 0 &&
         (o.adjudicate_plies == 0 || o.adjudicate_cp > 0) && 1 <= o.save_percent && o.save_percent <= 100 &&
         (o.save_percent == 100 || o.unsaved_nodes > 0) && 1 <= o.interleave && o.interleave <= 64
#ifndef FORK_DATAGEN_INTERLEAVE
         && o.interleave == 1
#endif
      ;
}

std::string shard_name(const Options& o, int worker, int index) {
  char buf[64];
  std::snprintf(buf, sizeof buf, "-w%02d-%04d.vf", worker, index);
  return o.run + buf;
}

SelfPlayConfig player_config(const Options& o) {
  SelfPlayConfig config;
  config.nodes = o.nodes;
  config.hash_bytes = o.hash_mb << 20;
  config.decided_cp = o.decided_cp;
  config.max_plies = o.max_plies;
  config.adjudicate_cp = o.adjudicate_cp;
  config.adjudicate_plies = o.adjudicate_plies;
  config.save_percent = o.save_percent;
  config.unsaved_nodes = o.unsaved_nodes;
  config.check_nodes = o.check_nodes;
  return config;
}

// Game g's start: its opening with the random plies played; returns the
// split search's save seed for the game.
std::uint64_t game_start(const Options& o, const std::vector<std::string>& openings,
                         const std::vector<std::uint32_t>& order, std::uint64_t g, Position& opening) {
  // FENs, not Positions, are kept: every Position reserves its state
  // history (about 57 KB), too much for millions of openings.
  opening.set_fen(openings[order[g % order.size()]]);  // checked when loaded
  std::uint64_t stream = splitmix_finalize(o.seed ^ splitmix_finalize(g + 1));
  const std::uint64_t save_seed = splitmix_finalize(stream);  // the split's own stream for game g
  const int plies =
      o.random_min +
      static_cast<int>(splitmix_next(stream) % static_cast<std::uint64_t>(o.random_max - o.random_min + 1));
  for (int i = 0; i < plies; ++i) {
    MoveList legal;
    generate<GenMode::Legal>(opening, legal);
    if (legal.size() == 0) break;
    opening.make(legal[splitmix_next(stream) % legal.size()]);
  }
  return save_seed;
}

// One worker's shard files and counts. Games are committed in the worker's
// game order; the worker stops after the game that brings it to its share
// of positions (or once any worker failed).
class WorkerShards {
 public:
  WorkerShards(const Options& o, int worker, Totals& totals, std::atomic<bool>& failed)
      : o_(o),
        worker_(worker),
        totals_(totals),
        failed_(failed),
        quota_((o.positions + static_cast<std::uint64_t>(o.threads) - 1) / o.threads) {}

  bool done() const { return written_ >= quota_ || failed_; }

  // Counts the next game in order, and writes it if it was written with at
  // least one position.
  void commit(const SelfPlayOutcome& outcome, std::span<const std::uint8_t> bytes, int positions, int unsaved,
              std::uint64_t nodes_spent) {
    totals_.nodes_spent += nodes_spent;
    {
      std::lock_guard lock(totals_.mutex);
      ++totals_.ends[static_cast<int>(outcome.end)];
      if (outcome.written) ++totals_.results[static_cast<int>(outcome.result)];
    }
    if (!outcome.written || positions == 0) return;
    if (!file_.is_open()) {
      shard_ = ShardInfo{shard_name(o_, worker_, shard_index_++), worker_};
      file_.open(o_.out_dir + "/" + shard_.file, std::ios::binary | std::ios::trunc);
      if (!file_) {
        std::fprintf(stderr, "worker %d: cannot create %s\n", worker_, shard_.file.c_str());
        failed_ = true;
        return;
      }
    }
    file_.write(reinterpret_cast<const char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    file_.flush();
    if (!file_) {
      std::fprintf(stderr, "worker %d: write failed on %s\n", worker_, shard_.file.c_str());
      failed_ = true;
      file_.close();  // not listed: a failed shard is not reported as written
      return;
    }
    shard_.games += 1;
    shard_.positions += static_cast<std::uint64_t>(positions);
    shard_.bytes += bytes.size();
    written_ += static_cast<std::uint64_t>(positions);
    totals_.games += 1;
    totals_.positions += static_cast<std::uint64_t>(positions);
    totals_.unsaved += static_cast<std::uint64_t>(unsaved);
    if (shard_.bytes >= (o_.shard_mb << 20)) close();
  }

  void close() {
    if (!file_.is_open()) return;
    file_.close();
    if (shard_.games) {
      std::lock_guard lock(totals_.mutex);
      totals_.shards.push_back(shard_);
    }
  }

 private:
  const Options& o_;
  int worker_;
  Totals& totals_;
  std::atomic<bool>& failed_;
  std::uint64_t quota_, written_ = 0;
  ShardInfo shard_;
  std::ofstream file_;
  int shard_index_ = 0;
};

// Worker w of T plays games w, w + T, w + 2T, ... one at a time.
void run_worker(const Options& o, int worker, const std::vector<std::string>& openings,
                const std::vector<std::uint32_t>& order, Totals& totals, std::atomic<bool>& failed) {
  std::string report;
  auto player = SelfPlayGame::create(player_config(o), report);
  if (!player) {
    std::fprintf(stderr, "worker %d: %s\n", worker, report.c_str());
    failed = true;
    return;
  }
  WorkerShards shards(o, worker, totals, failed);
  GameWriter writer;
  for (std::uint64_t g = static_cast<std::uint64_t>(worker); !shards.done(); g += o.threads) {
    Position opening;
    const std::uint64_t save_seed = game_start(o, openings, order, g, opening);
    const SelfPlayOutcome outcome = player->play(opening, writer, save_seed);
    shards.commit(outcome, writer.bytes(), writer.positions(), player->unsaved_positions(),
                  player->nodes_spent());
  }
  shards.close();
}

#ifdef FORK_DATAGEN_INTERLEAVE
// The interleaved worker (--interleave K; ideas.md idea 165, prototype):
// the same games as run_worker, played K at a time on one thread, each in a
// slot with its own player (table and history), writer and stack. At every
// search node's pause point the running game hands the thread to the next
// slot in a ring. A finished game waits until every earlier game of the
// worker is committed, so the shards are byte for byte run_worker's: each
// game is a pure function of its opening, settings and save seed (the table
// and the history are cleared before every game; the table's age is used
// only through equality and 8-bit differences, which a shifted start does
// not change).
struct InterleavedWorker;

struct GameSlot {
  InterleavedWorker* owner = nullptr;
  std::unique_ptr<SelfPlayGame> player;
  GameWriter writer;
  FiberStack stack;
  void* sp = nullptr;        // the stack pointer saved while switched out
  GameSlot* next = nullptr;  // the next slot still playing (a ring)
  bool playing = false;
};

struct FinishedGame {
  SelfPlayOutcome outcome{};
  std::vector<std::uint8_t> bytes;
  int positions = 0, unsaved = 0;
  std::uint64_t nodes_spent = 0;
};

struct InterleavedWorker {
  const Options& o;
  const std::vector<std::string>& openings;
  const std::vector<std::uint32_t>& order;
  int worker;
  WorkerShards& shards;
  std::vector<std::unique_ptr<GameSlot>> slots;
  std::map<std::uint64_t, FinishedGame> finished;  // by the worker's game number
  std::uint64_t next_game = 0, next_commit = 0;
  void* main_sp = nullptr;
  int live = 0;
  // Games played past the worker's end and never committed, and their nodes
  // (the cost of finishing K games at a time; reported on stderr).
  std::uint64_t discarded_games = 0, discarded_nodes = 0;

  // Commits every finished game that is next in order; once the worker is
  // done, asks the games still in flight to stop (none of them will be
  // committed) and forgets the finished ones waiting.
  void commit_ready() {
    for (auto it = finished.find(next_commit); it != finished.end() && !shards.done();
         it = finished.find(next_commit)) {
      const FinishedGame& f = it->second;
      shards.commit(f.outcome, f.bytes, f.positions, f.unsaved, f.nodes_spent);
      finished.erase(it);
      ++next_commit;
    }
    if (!shards.done()) return;
    for (const auto& [n, f] : finished) {
      ++discarded_games;
      discarded_nodes += f.nodes_spent;
    }
    finished.clear();
    for (const auto& s : slots)
      if (s->playing) s->player->abandon();
  }
};

void pause_game(void* arg) {
  GameSlot* s = static_cast<GameSlot*>(arg);
  if (s->next != s) forkeng_fiber_switch(&s->sp, s->next->sp);
}

void play_slot(void* arg) {
  GameSlot& s = *static_cast<GameSlot*>(arg);
  InterleavedWorker& w = *s.owner;
  while (!w.shards.done()) {
    const std::uint64_t n = w.next_game++;
    Position opening;
    const std::uint64_t save_seed = game_start(
        w.o, w.openings, w.order,
        static_cast<std::uint64_t>(w.worker) + n * static_cast<std::uint64_t>(w.o.threads), opening);
    s.playing = true;
    const SelfPlayOutcome outcome = s.player->play(opening, s.writer, save_seed);
    s.playing = false;
    if (w.shards.done()) {  // abandoned, or past the worker's end: never committed
      ++w.discarded_games;
      w.discarded_nodes += s.player->nodes_spent();
      break;
    }
    FinishedGame& f = w.finished[n];
    f.outcome = outcome;
    if (outcome.written) f.bytes.assign(s.writer.bytes().begin(), s.writer.bytes().end());
    f.positions = s.writer.positions();
    f.unsaved = s.player->unsaved_positions();
    f.nodes_spent = s.player->nodes_spent();
    w.commit_ready();
  }
  // Leave the ring for good; the last slot out resumes the worker's thread.
  if (--w.live == 0) forkeng_fiber_switch(&s.sp, w.main_sp);
  GameSlot* before = s.next;
  while (before->next != &s) before = before->next;
  before->next = s.next;
  forkeng_fiber_switch(&s.sp, s.next->sp);
}

void run_worker_interleaved(const Options& o, int worker, const std::vector<std::string>& openings,
                            const std::vector<std::uint32_t>& order, Totals& totals,
                            std::atomic<bool>& failed) {
  WorkerShards shards(o, worker, totals, failed);
  InterleavedWorker w{o, openings, order, worker, shards, {}, {}, 0, 0, nullptr, 0, 0, 0};
  for (int k = 0; k < o.interleave; ++k) {
    auto s = std::make_unique<GameSlot>();
    std::string report;
    s->owner = &w;
    s->player = SelfPlayGame::create(player_config(o), report);
    if (!s->player) {
      std::fprintf(stderr, "worker %d: %s\n", worker, report.c_str());
      failed = true;
      return;
    }
    if (!s->stack.map(FiberStackBytes)) {
      std::fprintf(stderr, "worker %d: cannot map a game's stack\n", worker);
      failed = true;
      return;
    }
    s->sp = s->stack.prepare(play_slot, s.get());
    s->player->set_pause(pause_game, s.get());
    w.slots.push_back(std::move(s));
  }
  for (std::size_t k = 0; k < w.slots.size(); ++k) w.slots[k]->next = w.slots[(k + 1) % w.slots.size()].get();
  w.live = o.interleave;
  forkeng_fiber_switch(&w.main_sp, w.slots[0]->sp);  // returns once every slot has left the ring
  shards.close();
  std::fprintf(stderr, "worker %d: discarded %" PRIu64 " games past its end (%" PRIu64 " nodes)\n", worker,
               w.discarded_games, w.discarded_nodes);
}
#endif

void write_manifest(const Options& o, const Totals& t, double seconds, std::size_t opening_count) {
  std::ofstream f(o.out_dir + "/" + o.run + ".json", std::ios::trunc);
  f << "{\n  \"tool\": \"fork_datagen\",\n  \"version\": \"" << engine_version() << "\",\n"
    << "  \"evaluator\": \"" << FORK_EVALUATOR_NAME
#if defined(FORK_EVAL_NNUE)
    << " (" << FORK_NET_NAME << ')'  // the labelling network: data from different nets stays apart
#endif
    << "\",\n"
    << "  \"arch\": \"" << FORK_ARCH_NAME << "\",\n"
    << "  \"settings\": {\"openings\": \""
    << std::string(o.openings.substr(o.openings.find_last_of("/\\") + 1))
    << "\", \"openings_count\": " << opening_count << ", \"positions_target\": " << o.positions
    << ", \"nodes\": " << o.nodes << ", \"threads\": " << o.threads << ", \"seed\": " << o.seed
    << ", \"hash_mb\": " << o.hash_mb << ", \"shard_mb\": " << o.shard_mb << ", \"tables\": \""
    << (o.tables.empty() ? "none" : "syzygy " + std::to_string(endgame_table_pieces()) + "-piece")
    << "\", \"decided_cp\": " << o.decided_cp << ", \"max_plies\": " << o.max_plies
    << ", \"random_min\": " << o.random_min << ", \"random_max\": " << o.random_max
    << ", \"adjudicate_cp\": " << o.adjudicate_cp << ", \"adjudicate_plies\": " << o.adjudicate_plies
    << ", \"save_percent\": " << o.save_percent << ", \"unsaved_nodes\": " << o.unsaved_nodes
    << ", \"check_nodes\": " << o.check_nodes;
  if (o.interleave > 1) f << ", \"interleave\": " << o.interleave;
  f << "},\n"
    << "  \"games\": " << t.games.load() << ",\n  \"positions\": " << t.positions.load() << ",\n"
    << "  \"positions_unsaved\": " << t.unsaved.load() << ",\n  \"nodes_spent\": " << t.nodes_spent.load()
    << ",\n"
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
  auto worker_main = run_worker;
#ifdef FORK_DATAGEN_INTERLEAVE
  if (o.interleave > 1) worker_main = run_worker_interleaved;
#endif
  for (int w = 0; w < o.threads; ++w)
    workers.emplace_back(worker_main, std::cref(o), w, std::cref(openings), std::cref(order),
                         std::ref(totals), std::ref(failed));
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
