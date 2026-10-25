// Fork's entry point. Without arguments it speaks UCI on stdin/stdout
// (src/uci/session.hpp); with a subcommand it runs that tool: perft, divide,
// bench (the search bench), perftbench, version, difftest.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <iostream>
#include <string>
#include <string_view>
#include <vector>

#include "core/bitboard.hpp"
#include "core/movegen.hpp"
#include "core/perft.hpp"
#include "core/position.hpp"
#include "search/search_bench.hpp"
#include "uci/output.hpp"
#include "uci/session.hpp"

// Generated at build time: the variant label and git commit of this build.
#include "build_id.hpp"

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

namespace {

std::string_view compiler_name() {
#if defined(__clang__)
  return "clang " __clang_version__;
#elif defined(__GNUC__)
  return "gcc " __VERSION__;
#else
  return "unknown";
#endif
}

void print_version() {
  std::cout << "Fork " << forkeng::engine_version() << '\n'
            << "compiler " << compiler_name() << '\n'
            << "arch " << FORK_ARCH_NAME << '\n'
            << "build " << FORK_BUILD_TYPE << '\n'
            << "sliders " << (FORK_USE_PEXT ? "pext" : "magic")
            << '\n'
            // For bench/ab_search.py's identity check (cmake/build_id.cmake).
            << "variant " FORK_BUILD_VARIANT " | commit " FORK_BUILD_COMMIT " |\n";
}

// One line per ply for differential testing against an independent
// generator (tools/difftest): fen | sorted legal moves, '+' marking checks |
// in check | insufficient material | fifty-move clock reached | repetitions (max 3).
void print_ply(const forkeng::Position& pos) {
  forkeng::MoveList list;
  forkeng::generate<forkeng::GenMode::Legal>(pos, list);
  std::vector<std::string> moves;
  for (forkeng::Move m : list) moves.push_back(pos.move_to_uci(m) + (pos.gives_check(m) ? "+" : ""));
  std::ranges::sort(moves);
  std::string line = pos.fen() + '|';
  for (std::size_t i = 0; i < moves.size(); ++i) line += (i ? " " : "") + moves[i];
  line += '|' + std::to_string(pos.in_check()) + '|' + std::to_string(pos.insufficient_material()) + '|' +
          std::to_string(pos.fifty_move_reached()) + '|' +
          std::to_string(std::min(3, pos.repetition_count()));
  std::cout << line << '\n';
}

// Reads "fen|move move ..." lines; prints every ply, then "end".
int difftest() {
  std::ios::sync_with_stdio(false);
  std::string line;
  while (std::getline(std::cin, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    std::size_t bar = line.find('|');
    forkeng::Position pos;
    std::string error;
    if (bar == std::string::npos || !pos.set_fen(line.substr(0, bar), &error)) {
      std::cout << "error bad input: " << line << ' ' << error << "\nend\n" << std::flush;
      continue;
    }
    print_ply(pos);
    std::string rest = line.substr(bar + 1), uci;
    for (std::size_t i = 0; i <= rest.size(); ++i) {
      if (i < rest.size() && rest[i] != ' ') {
        uci += rest[i];
        continue;
      }
      if (uci.empty()) continue;
      forkeng::Move m = pos.parse_uci(uci);
      if (m.is_none()) {
        std::cout << "error illegal move " << uci << '\n';
        break;
      }
      pos.make(m);
      print_ply(pos);
      uci.clear();
    }
    std::cout << "end\n" << std::flush;  // the driver waits for this line
  }
  return 0;
}

// Zero-padded 16-digit hex. Not std::format: libstdc++ has <format> only from
// GCC 13, and TCEC builds with gcc 11.4 and g++-12 (DESIGN.md §5.1).
std::string hex16(std::uint64_t v) {
  char buf[17];
  (void)std::snprintf(buf, sizeof buf, "%016llx", static_cast<unsigned long long>(v));
  return buf;
}

int usage() {
  std::cerr << "usage: fork perft <depth> [fen]\n"
               "       fork divide <depth> [fen]\n"
               "       fork bench        (the search bench)\n"
               "       fork perftbench   (the Phase 1 perft workload)\n"
               "       fork difftest   (stdin: fen|moves, see tools/difftest)\n"
               "       fork version\n";
  return 2;
}

// Reads "<depth> [fen...]" from argv starting at index 2.
bool read_depth_and_position(int argc, char** argv, int& depth, forkeng::Position& pos) {
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

// The UCI loop. stdin is switched to binary mode on Windows so that line
// endings reach the reader as sent (it accepts LF, CRLF and CR) and a stray
// Ctrl-Z byte is not taken for end of input; stdout stays in the platform's
// text mode.
static int uci_main() {
#ifdef _WIN32
  (void)_setmode(_fileno(stdin), _O_BINARY);
#endif
  forkeng::OutputChannel out(stdout);
  forkeng::UciSession session(out);
  return session.run(stdin);
}

static int run(int argc, char** argv) {
  forkeng::init();
  if (argc < 2) return uci_main();
  std::string cmd = argv[1];

  if (cmd == "version") {
    print_version();
    return 0;
  }
  if (cmd == "difftest") return difftest();
  if (cmd == "bench") {
    const forkeng::SearchBenchResult r = forkeng::run_search_bench();
    std::cout << "nodes " << r.nodes << '\n'
              << "signature " << hex16(r.signature) << '\n'
              << "nps "
              << static_cast<std::uint64_t>(static_cast<double>(r.nodes) / std::max(r.seconds, 1e-9)) << '\n';
    return 0;
  }
  if (cmd == "perftbench") {
    forkeng::BenchResult r = forkeng::bench();
    std::cout << "nodes " << r.nodes << '\n'
              << "signature " << hex16(r.signature) << '\n'
              << "nps "
              << static_cast<std::uint64_t>(static_cast<double>(r.nodes) / std::max(r.seconds, 1e-9)) << '\n';
    return 0;
  }
  if (cmd == "perft" || cmd == "divide") {
    int depth = 0;
    forkeng::Position pos;
    if (!read_depth_and_position(argc, argv, depth, pos)) return usage();
    auto start = std::chrono::steady_clock::now();
    std::uint64_t nodes =
        cmd == "perft" ? forkeng::perft(pos, depth) : forkeng::divide(pos, depth, std::cout);
    double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    if (cmd == "perft") std::cout << "nodes " << nodes << '\n';
    std::cout << "time " << secs << " s\n"
              << "nps " << static_cast<std::uint64_t>(static_cast<double>(nodes) / std::max(secs, 1e-9))
              << '\n';
    return 0;
  }
  return usage();
}

int main(int argc, char** argv) {
  try {
    return run(argc, argv);
  } catch (const std::exception& e) {
    std::cerr << "fatal: " << e.what() << '\n';
    return 1;
  }
}
