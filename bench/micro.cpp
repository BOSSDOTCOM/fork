// SPDX-License-Identifier: GPL-3.0-or-later

// Microbenchmarks for core operations, with repeated timed runs on a pinned
// core. Reports median ns/op and the p10-p90 spread, flags noisy results, and
// saves/compares baselines.
//
//   fork_micro [--core N] [--reps N] [--save FILE] [--compare FILE] [--filter NAME]
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <exception>
#include <fstream>
#include <functional>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "build_id.hpp"

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <pthread.h>
#include <sched.h>
#endif

#include "core/movegen.hpp"
#include "core/perft.hpp"
#if defined(FORK_EVAL_NNUE)
#include <array>
#include <memory>

#include "eval/eval.hpp"
#include "eval/nnue/danger_summary.hpp"
#include "eval/nnue/refiner.hpp"
#include "search/refiner_gate.hpp"
#endif

using namespace forkeng;

namespace {

using Clock = std::chrono::steady_clock;
volatile std::uint64_t sink;

constexpr double NoisySpread = 0.03;  // (p90 - p10) / median above this is flagged
// Run-to-run drift between separate invocations is about 1% on the dev
// machine, so smaller changes are never called significant.
constexpr double NoiseFloor = 0.02;

struct Result {
  std::string name;
  double median, p10, p90, min;  // ns per op
  double spread() const { return (p90 - p10) / median; }
};

bool pin_to_core(int core) {
#ifdef _WIN32
  SetPriorityClass(GetCurrentProcess(), HIGH_PRIORITY_CLASS);
  SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_HIGHEST);
  return SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << core) != 0;
#else
  cpu_set_t set;
  CPU_ZERO(&set);
  CPU_SET(core, &set);
  return pthread_setaffinity_np(pthread_self(), sizeof set, &set) == 0;
#endif
}

// Runs `pass` (one pass over the workload, returns ops done) repeatedly for
// at least `target` seconds per sample, `reps` samples after one warm-up.
Result measure(const std::string& name, const std::function<std::uint64_t()>& pass, int reps, double target) {
  pass();
  std::vector<double> samples;
  for (int r = 0; r < reps; ++r) {
    std::uint64_t ops = 0;
    auto start = Clock::now();
    double elapsed;
    do {
      ops += pass();
      elapsed = std::chrono::duration<double>(Clock::now() - start).count();
    } while (elapsed < target);
    samples.push_back(elapsed * 1e9 / static_cast<double>(ops));
  }
  std::ranges::sort(samples);
  auto at = [&](double q) {
    return samples[static_cast<std::size_t>(std::lround(q * static_cast<double>(samples.size() - 1)))];
  };
  return {name, at(0.5), at(0.1), at(0.9), samples.front()};
}

// Deterministic workload: positions from random playouts of the suite
// positions, so every build measures the same positions.
std::vector<Position> make_positions() {
  const char* starts[] = {
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
      "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
      "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
      "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
      "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
  };
  std::uint64_t rng = 0x9E37'79B9'7F4A'7C15ULL;
  auto next = [&rng] {
    rng ^= rng << 13;
    rng ^= rng >> 7;
    rng ^= rng << 17;
    return rng;
  };
  std::vector<Position> out;
  for (const char* fen : starts) {
    for (int game = 0; game < 40; ++game) {
      Position pos;
      pos.set_fen(fen);
      for (int ply = 0; ply < 120; ++ply) {
        MoveList list;
        generate<GenMode::Legal>(pos, list);
        if (!list.size() || pos.halfmove_clock() >= 100) break;
        Position snapshot;
        snapshot.set_fen(pos.fen());  // keep stored positions free of history
        out.push_back(snapshot);
        pos.make(list[next() % list.size()]);
      }
    }
  }
  return out;
}

std::map<std::string, Result> load(const std::string& path) {
  std::map<std::string, Result> m;
  std::ifstream in(path);
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') continue;
    std::istringstream ss(line);
    Result r;
    if (ss >> r.name >> r.median >> r.p10 >> r.p90) {
      if (!(ss >> r.min)) r.min = r.p10;
      m[r.name] = r;
    }
  }
  return m;
}

// Starts with "variant <name> | commit <hash>[-dirty]": bench/ab.py parses
// these two fields to check that it runs the binaries it was asked to compare.
std::string build_info() {
  std::string s = "variant " FORK_BUILD_VARIANT " | commit " FORK_BUILD_COMMIT " | ";
#if defined(__clang__)
  s += "clang " __clang_version__;
#elif defined(__GNUC__)
  s += "gcc " __VERSION__;
#endif
  s += std::string(" | arch ") + FORK_ARCH_NAME + " | " + (FORK_USE_PEXT ? "pext" : "magic");
  return s;
}

}  // namespace

static int run(int argc, char** argv) {
  int core = 2, reps = 15;
  double target = 0.15;
  std::string save, compare, filter;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    auto value = [&] { return i + 1 < argc ? std::string(argv[++i]) : std::string(); };
    if (a == "--core")
      core = std::stoi(value());
    else if (a == "--reps")
      reps = std::stoi(value());
    else if (a == "--target")
      target = std::stod(value());
    else if (a == "--save")
      save = value();
    else if (a == "--compare")
      compare = value();
    else if (a == "--filter")
      filter = value();
    else {
      (void)std::fprintf(stderr, "unknown argument %s\n", a.c_str());
      return 2;
    }
  }

  init();
  bool pinned = pin_to_core(core);
  std::vector<Position> positions = make_positions();
  std::vector<MoveList> legal(positions.size());
  std::uint64_t total_moves = 0;
  for (std::size_t i = 0; i < positions.size(); ++i) {
    generate<GenMode::Legal>(positions[i], legal[i]);
    total_moves += legal[i].size();
  }
  // Probe moves for validation: every legal move plus 16 random encodings.
  std::vector<std::vector<Move>> probes(positions.size());
  std::uint64_t rng = 12345, total_probes = 0;
  for (std::size_t i = 0; i < positions.size(); ++i) {
    probes[i].assign(legal[i].begin(), legal[i].end());
    for (int k = 0; k < 16; ++k) {
      rng = rng * 6364136223846793005ULL + 1442695040888963407ULL;
      probes[i].push_back(Move::from_raw(static_cast<std::uint16_t>(rng >> 48)));
    }
    total_probes += probes[i].size();
  }

  std::printf("fork_micro | %s | core %d%s | %zu positions, %llu moves | %d reps x %.2f s\n",
              build_info().c_str(), core, pinned ? "" : " (pinning failed)", positions.size(),
              static_cast<unsigned long long>(total_moves), reps, target);

  using Bench = std::pair<std::string, std::function<std::uint64_t()>>;
  std::vector<Bench> benches = {
      {"init_tables",
       [] {
         build_bitboard_tables();
         return std::uint64_t{1};
       }},
      {"perft_bench", [] { return bench().nodes; }},
      {"movegen_legal",
       [&] {
         for (const Position& p : positions) {
           MoveList l;
           generate<GenMode::Legal>(p, l);
           sink = sink + l.size();
         }
         return static_cast<std::uint64_t>(positions.size());
       }},
      {"movegen_captures",
       [&] {
         for (const Position& p : positions) {
           MoveList l;
           generate<GenMode::Captures>(p, l);
           sink = sink + l.size();
         }
         return static_cast<std::uint64_t>(positions.size());
       }},
      {"movegen_quiets",
       [&] {
         for (const Position& p : positions) {
           MoveList l;
           generate<GenMode::Quiets>(p, l);
           sink = sink + l.size();
         }
         return static_cast<std::uint64_t>(positions.size());
       }},
      {"make_unmake",
       [&] {
         for (std::size_t i = 0; i < positions.size(); ++i)
           for (Move m : legal[i]) {
             positions[i].make(m);
             sink = sink + positions[i].key();
             positions[i].unmake(m);
           }
         return total_moves;
       }},
      {"null_move",
       [&] {  // state copy + check-info update, without piece moves
         std::uint64_t n = 0;
         for (Position& p : positions)
           if (!p.in_check()) {
             p.make_null();
             sink = sink + p.key();
             p.unmake_null();
             ++n;
           }
         return n;
       }},
      {"gives_check",
       [&] {
         for (std::size_t i = 0; i < positions.size(); ++i)
           for (Move m : legal[i]) sink = sink + positions[i].gives_check(m);
         return total_moves;
       }},
      {"predicted_key",
       [&] {
         for (std::size_t i = 0; i < positions.size(); ++i)
           for (Move m : legal[i]) sink = sink + positions[i].predicted_key(m);
         return total_moves;
       }},
      {"attackers_to",
       [&] {
         for (const Position& p : positions)
           for (Square s = 0; s < 64; ++s) sink = sink + p.attackers_to(s, p.pieces());
         return static_cast<std::uint64_t>(positions.size() * 64);
       }},
      {"is_pseudo_legal",
       [&] {
         for (std::size_t i = 0; i < positions.size(); ++i)
           for (Move m : probes[i]) sink = sink + positions[i].is_pseudo_legal(m);
         return total_probes;
       }},
      {"is_legal",
       [&] {
         for (std::size_t i = 0; i < positions.size(); ++i)
           for (Move m : legal[i]) sink = sink + positions[i].is_legal(m);
         return total_moves;
       }},
  };
#if defined(FORK_EVAL_NNUE)
  // The Boundary Refiner's parts (ideas.md 59, step 3; the plan's M2), per
  // call, on the first 2,000 positions not in check with their accumulators
  // computed beforehand, labelled by the function each one times: the
  // exposure pass (exposed_pieces), the danger summary, packing the clipped
  // accumulator (refiner_pack), all the rows (refiner_rows: the exposure pass
  // and the rows' encoding, the danger summary in architecture 2, the
  // context), the entry layer (refiner_l1), the middle layer and the heads
  // (refiner_l2_heads), the gate's test (gate_fires; it runs at every
  // computed evaluation, not only at calls), the layers together
  // (refiner_layers), and a whole call (refiner_call: pack, rows, layers; the
  // accumulator walk of a reused evaluation not included). The refiner
  // build's embedded refiner, else one of zero weights: the integer kernels
  // take the same time whatever the weights.
  const NetFile& base_net = embedded_net();
#ifdef FORK_REFINER
  const RefinerFile& refiner_weights = embedded_refiner();
#else
  const auto zero_refiner = std::make_unique<RefinerFile>();
  const RefinerFile& refiner_weights = *zero_refiner;
#endif
  std::vector<std::size_t> picked;
  for (std::size_t i = 0; i < positions.size() && picked.size() < 2000; ++i)
    if (!positions[i].in_check()) picked.push_back(i);
  auto accumulators = std::make_unique<Accumulator[]>(picked.size());
  auto inputs = std::make_unique<RefinerInputs[]>(picked.size());
  std::vector<int> base_evals(picked.size());
  for (std::size_t k = 0; k < picked.size(); ++k) {
    const Position& p = positions[picked[k]];
    accumulate_board(base_net, p, accumulators[k]);
    base_evals[k] = evaluate_position(base_net, accumulators[k], p);
    pack_clipped(accumulators[k], p.side_to_move(), inputs[k].bytes);
    inputs[k].row_count = refiner_rows(base_net, p, base_evals[k], inputs[k].rows);
  }
  const auto calls = static_cast<std::uint64_t>(picked.size());
  benches.push_back({"exposed_pieces", [&] {
                       for (const std::size_t i : picked) sink = sink + exposed_pieces(positions[i]);
                       return calls;
                     }});
  benches.push_back({"danger_summary", [&] {
                       for (const std::size_t i : picked) {
                         Bitboard exposed;
                         const DangerSummary d = danger_summary(positions[i], exposed);
                         sink = sink + exposed + static_cast<std::uint64_t>(d.safe_checks[White]);
                       }
                       return calls;
                     }});
  benches.push_back({"refiner_pack", [&] {
                       alignas(64) std::uint8_t bytes[RefinerInputBytes];
                       for (std::size_t k = 0; k < picked.size(); ++k) {
                         pack_clipped(accumulators[k], positions[picked[k]].side_to_move(), bytes);
                         sink = sink + bytes[k % RefinerInputBytes];
                       }
                       return calls;
                     }});
  benches.push_back({"refiner_rows", [&] {
                       int rows[RefinerMaxActive];
                       for (std::size_t k = 0; k < picked.size(); ++k)
                         sink = sink + static_cast<std::uint64_t>(
                                           refiner_rows(base_net, positions[picked[k]], base_evals[k], rows));
                       return calls;
                     }});
  benches.push_back({"refiner_l1", [&] {
                       alignas(32) std::int32_t sums[RefinerL1Width];
                       for (std::size_t k = 0; k < picked.size(); ++k) {
                         refiner_l1(refiner_weights, inputs[k], sums);
                         sink = sink + static_cast<std::uint64_t>(sums[k % RefinerL1Width]);
                       }
                       return calls;
                     }});
  std::vector<std::array<std::int32_t, RefinerL1Width>> entry_sums(picked.size());
  for (std::size_t k = 0; k < picked.size(); ++k)
    refiner_l1(refiner_weights, inputs[k], entry_sums[k].data());
  benches.push_back({"refiner_l2_heads", [&] {
                       for (std::size_t k = 0; k < picked.size(); ++k) {
                         const RefinerOutput o = refiner_l2_heads(refiner_weights, entry_sums[k].data());
                         sink = sink + static_cast<std::uint64_t>(o.correction + o.confidence);
                       }
                       return calls;
                     }});
  // The gate's test at every evaluation site (computed ones, about 0.53 per
  // node in game): a window around each base evaluation, half of them gated.
  const RefinerGate gate{25, 25, false};
  benches.push_back({"gate_fires", [&] {
                       for (std::size_t k = 0; k < picked.size(); ++k) {
                         const int e = base_evals[k], shift = k % 2 ? 10 : 60;
                         sink =
                             sink + gate_fires(gate, GateSite{positions[picked[k]], e, e - shift, e + shift,
                                                              static_cast<int>(k % 8), 4, k % 3 == 0});
                       }
                       return calls;
                     }});
  benches.push_back({"refiner_layers", [&] {
                       for (std::size_t k = 0; k < picked.size(); ++k) {
                         const RefinerOutput o = run_refiner(refiner_weights, inputs[k]);
                         sink = sink + static_cast<std::uint64_t>(o.correction + o.confidence);
                       }
                       return calls;
                     }});
  benches.push_back({"refiner_call", [&] {
                       RefinerInputs in;
                       for (std::size_t k = 0; k < picked.size(); ++k) {
                         const Position& p = positions[picked[k]];
                         pack_clipped(accumulators[k], p.side_to_move(), in.bytes);
                         in.row_count = refiner_rows(base_net, p, base_evals[k], in.rows);
                         const RefinerOutput o = run_refiner(refiner_weights, in);
                         sink = sink + static_cast<std::uint64_t>(o.correction + o.confidence);
                       }
                       return calls;
                     }});
#endif

  std::map<std::string, Result> base;
  if (!compare.empty()) base = load(compare);
  std::vector<Result> results;

  std::printf("\n%-18s %12s %10s %8s", "benchmark", "ns/op", "spread", "");
  if (!base.empty()) std::printf(" %12s %9s", "baseline", "change");
  std::printf("\n");
  for (auto& [name, fn] : benches) {
    if (!filter.empty() && name.find(filter) == std::string::npos) continue;
    Result r = measure(name, fn, reps, target);
    results.push_back(r);
    std::printf("%-18s %12.2f %9.1f%% %8s", name.c_str(), r.median, 100 * r.spread(),
                r.spread() > NoisySpread ? "NOISY" : "");
    if (auto it = base.find(name); it != base.end()) {
      const Result& b = it->second;
      double change = (r.median - b.median) / b.median;
      bool significant = std::abs(change) > std::max({r.spread(), b.spread(), NoiseFloor});
      std::printf(" %12.2f %+8.1f%%%s", b.median, 100 * change, significant ? "" : " (within noise)");
    }
    std::printf("\n");
  }

  if (!save.empty()) {
    std::ofstream out(save);
    out << "# " << build_info() << "\n# name median_ns p10_ns p90_ns min_ns\n";
    for (const Result& r : results)
      out << r.name << ' ' << r.median << ' ' << r.p10 << ' ' << r.p90 << ' ' << r.min << '\n';
    out.close();
    if (!out) {
      std::fprintf(stderr, "\ncannot write %s\n", save.c_str());
      return 1;
    }
    std::printf("\nsaved %s\n", save.c_str());
  }
  return 0;
}

int main(int argc, char** argv) {
  try {
    return run(argc, argv);
  } catch (const std::exception& e) {
    (void)std::fprintf(stderr, "fatal: %s\n", e.what());
    return 1;
  }
}
