// libFuzzer target: arbitrary bytes into the UCI command handler, split into
// lines the way the input loop splits them (LF, CR). Checks only that
// nothing crashes, hangs or trips a sanitizer: output is discarded.
//
// The session runs with the fuzz limits of SessionConfig: no bench or
// go perft (seconds each), no files (LogFile could create any path), and a
// small Hash (1 MB default, 4 MB max) and Threads (4 max), so each input is
// fast and touches little memory. Searches still run on their own thread,
// and the session's destructor stops and joins them (go infinite cannot
// hang an input).
#include <cstdint>
#include <string_view>

#include "uci/output.hpp"
#include "uci/session.hpp"

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
  static const bool initialized = (forkeng::init(), true);
  (void)initialized;
  if (size > 4096) return 0;
  forkeng::SessionConfig config;
  config.allow_heavy_commands = false;
  config.allow_files = false;
  config.default_hash_mb = 1;
  config.max_hash_mb = 4;
  config.max_threads = 4;
  forkeng::OutputChannel out(nullptr);
  forkeng::UciSession session(out, config);
  const std::string_view input(reinterpret_cast<const char*>(data), size);
  std::size_t begin = 0;
  for (std::size_t i = 0; i <= input.size(); ++i) {
    if (i < input.size() && input[i] != '\n' && input[i] != '\r') continue;
    if (i > begin && !session.handle_line(input.substr(begin, i - begin))) break;
    begin = i + 1;
  }
  return 0;
}
