// output: the single path for everything the engine writes in UCI mode.
//
// Purpose: whole lines to the GUI, from any thread, plus the optional
// LogFile transcript of input and output.
// Invariants:
// - send_line() writes the line, a newline and a flush under one mutex, so
//   lines from the input and search threads never interleave and nothing
//   waits in a buffer.
// - In UCI mode nothing else writes to stdout: every line sent is a UCI
//   engine-to-GUI message (id, uciok, readyok, bestmove, option, info).
// - The log, when open, records input and output in the order they were
//   handled, each line with a UTC timestamp. A failed write never throws.
#pragma once

#include <cstdio>
#include <mutex>
#include <string>
#include <string_view>

namespace forkeng {

class OutputChannel {
 public:
  // `out` may be nullptr: lines are then discarded (the fuzz target).
  explicit OutputChannel(std::FILE* out) : out_(out) {}
  ~OutputChannel();
  OutputChannel(const OutputChannel&) = delete;
  OutputChannel& operator=(const OutputChannel&) = delete;

  void send_line(std::string_view line);
  void send_info_string(std::string_view text) { send_line(std::string("info string ") += text); }

  // Records a received line in the log (if one is open).
  void log_input(std::string_view line);

  // Opens `path` for appending as the log; an empty path closes the log. On
  // failure the previous log stays as it was and `error` says why.
  bool open_log(const std::string& path, std::string* error);

 private:
  void write_log(char direction, std::string_view line);  // caller holds mutex_

  std::mutex mutex_;
  std::FILE* out_;
  std::FILE* log_ = nullptr;
};

}  // namespace forkeng
