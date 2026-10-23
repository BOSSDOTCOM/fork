// Fork command line. Phase 1: perft, divide, bench, version.
// The UCI loop arrives in Phase 2.
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <iostream>
#include <string>

#include "core/bitboard.hpp"
#include "core/perft.hpp"
#include "core/position.hpp"

namespace {

std::string compiler_name() {
#if defined(__clang__)
  return "clang " __clang_version__;
#elif defined(__GNUC__)
  return "gcc " __VERSION__;
#else
  return "unknown";
#endif
}

void print_version() {
  std::cout << "Fork (Phase 1)\n"
            << "compiler " << compiler_name() << '\n'
            << "arch " << FORK_ARCH_NAME << '\n'
            << "build " << FORK_BUILD_TYPE << '\n'
            << "sliders " << (FORK_USE_PEXT ? "pext" : "magic") << '\n';
}

int usage() {
  std::cerr << "usage: fork perft <depth> [fen]\n"
               "       fork divide <depth> [fen]\n"
               "       fork bench\n"
               "       fork version\n";
  return 2;
}

// Reads "<depth> [fen...]" from argv starting at index 2.
bool read_depth_and_position(int argc, char** argv, int& depth, fork::Position& pos) {
  if (argc < 3) return false;
  try {
    depth = std::stoi(argv[2]);
  } catch (...) {
    return false;
  }
  if (depth < 0) return false;
  if (argc > 3) {
    std::string fen;
    for (int i = 3; i < argc; ++i) fen += std::string(i > 3 ? " " : "") + argv[i];
    std::string error;
    if (!pos.set_fen(fen, &error)) {
      std::cerr << "invalid FEN: " << error << '\n';
      return false;
    }
  }
  return true;
}

}  // namespace

int main(int argc, char** argv) {
  fork::init();
  if (argc < 2) return usage();
  std::string cmd = argv[1];

  if (cmd == "version") {
    print_version();
    return 0;
  }
  if (cmd == "bench") {
    fork::BenchResult r = fork::bench();
    char sig[17];
    std::snprintf(sig, sizeof sig, "%016llx", static_cast<unsigned long long>(r.signature));
    std::cout << "nodes " << r.nodes << '\n'
              << "signature " << sig << '\n'
              << "nps " << static_cast<std::uint64_t>(r.nodes / std::max(r.seconds, 1e-9)) << '\n';
    return 0;
  }
  if (cmd == "perft" || cmd == "divide") {
    int depth = 0;
    fork::Position pos;
    if (!read_depth_and_position(argc, argv, depth, pos)) return usage();
    auto start = std::chrono::steady_clock::now();
    std::uint64_t nodes = cmd == "perft" ? fork::perft(pos, depth) : fork::divide(pos, depth, std::cout);
    double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    if (cmd == "perft") std::cout << "nodes " << nodes << '\n';
    std::cout << "time " << secs << " s\n"
              << "nps " << static_cast<std::uint64_t>(nodes / std::max(secs, 1e-9)) << '\n';
    return 0;
  }
  return usage();
}
