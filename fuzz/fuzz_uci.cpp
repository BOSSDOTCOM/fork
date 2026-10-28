// SPDX-License-Identifier: GPL-3.0-or-later

// libFuzzer target: arbitrary bytes into the UCI command handler, split into
// lines the way the input loop splits them (LF, CR).
//
// The command parsers in isolation (owner, 2026-10-24): the session runs
// with SessionConfig::use_threads off, so no thread is ever started (go is
// answered on this thread at once, the Hash cleared here), and with the
// other fuzz limits: no bench or go perft (seconds each), no files (LogFile
// could create any path), Hash 1 MB by default and 4 MB at most.
//
// Checked for every input, besides no crash, hang or sanitizer report:
// - every line the engine prints is a well-formed UCI engine-to-GUI
//   message (tests/uci_message.hpp, the check the UCI tests use);
// - a line without any command word (unknown or malformed input) prints
//   nothing, except "info string unknown command: ..." in debug builds.
//
// Seeds in fuzz/corpus/uci/seed-*: one hand-written example of each command.
#include <cstdint>
#include <cstdlib>
#include <string>
#include <string_view>
#include <vector>

#include "uci/output.hpp"
#include "uci/session.hpp"
#include "uci_message.hpp"

namespace {

void require(bool ok) {
  if (!ok) std::abort();  // libFuzzer reports the crash with its input
}

constexpr std::string_view Commands[] = {"uci",        "debug",    "isready", "setoption", "register",
                                         "ucinewgame", "position", "go",      "stop",      "ponderhit",
                                         "quit",       "d",        "bench"};

// True if no whitespace-separated word of `line` is a command (the session
// then ignores the line). An independent restatement of the session's rule.
bool has_no_command(std::string_view line) {
  for (const forkeng::LineToken& t : forkeng::split_tokens(line))
    for (std::string_view c : Commands)
      if (t.text == c) return false;
  return true;
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
  static const bool initialized = (forkeng::init(), true);
  (void)initialized;
  if (size > 65536) return 0;  // room for position lines of a few thousand plies
  forkeng::SessionConfig config;
  config.allow_heavy_commands = false;
  config.allow_files = false;
  config.default_hash_mb = 1;
  config.max_hash_mb = 4;
  config.use_threads = false;
  forkeng::OutputChannel out(nullptr);
  std::vector<std::string> printed;
  out.capture(&printed);
  forkeng::UciSession session(out, config);
  const std::string_view input(reinterpret_cast<const char*>(data), size);
  std::size_t begin = 0;
  for (std::size_t i = 0; i <= input.size(); ++i) {
    if (i < input.size() && input[i] != '\n' && input[i] != '\r') continue;
    const std::string_view line = input.substr(begin, i - begin);
    begin = i + 1;
    if (line.empty()) continue;
    const std::size_t before = printed.size();
    const bool more = session.handle_line(line);
    for (std::size_t k = before; k < printed.size(); ++k)
      require(forkeng::test::valid_engine_line(printed[k]));
    if (has_no_command(line)) {
      for (std::size_t k = before; k < printed.size(); ++k)
        require(std::string_view(printed[k]).starts_with("info string unknown command: "));
#ifndef FORK_DEBUG
      require(printed.size() == before);
#endif
    }
    if (!more) break;
  }
  return 0;
}
