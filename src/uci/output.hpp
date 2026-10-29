// SPDX-License-Identifier: GPL-3.0-or-later

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

#include <cstdint>
#include <cstdio>
#include <mutex>
#include <string>
#include <string_view>
#include <vector>

namespace forkeng {

class OutputChannel {
 public:
  // `out` may be nullptr: lines are then discarded (the fuzz target).
  explicit OutputChannel(std::FILE* out) : out_(out) {}
  ~OutputChannel();
  OutputChannel(const OutputChannel&) = delete;
  OutputChannel& operator=(const OutputChannel&) = delete;

  // Returns the line's sequence number (1, 2, ...), taken under the same lock
  // as the write, so a caller can tell later whether another line followed.
  std::uint64_t send_line(std::string_view line);
  // Lines sent so far (any thread).
  std::uint64_t lines_sent() {
    std::scoped_lock lock(mutex_);
    return sent_;
  }
  // "info string <text>". Control bytes in `text` (it may echo input) become
  // '?', so every line stays one printable line.
  void send_info_string(std::string_view text);

  // Also keeps every line sent in `lines` (nullptr stops it): lets the fuzz
  // target check the output without a file.
  void capture(std::vector<std::string>* lines) {
    std::scoped_lock lock(mutex_);
    capture_ = lines;
  }

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
  std::vector<std::string>* capture_ = nullptr;
  std::uint64_t sent_ = 0;
};

}  // namespace forkeng
