// SPDX-License-Identifier: GPL-3.0-or-later

// engine_process: runs the fork binary as a child process over pipes, the way
// a GUI does, for the UCI tests.
//
// Purpose: write to the engine's stdin, read its stdout line by line with
// arrival times, close stdin (EOF), and collect the exit status.
// Invariants:
// - A reader thread collects every stdout line (CR and LF stripped) as it
//   arrives; waiting functions never block longer than their timeout.
// - The destructor kills a child that is still running and joins the reader,
//   so no test leaves a process behind.
// - stderr is inherited (it shows in the test log and is not checked).
#pragma once

#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <functional>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

namespace forkeng::test {

using Clock = std::chrono::steady_clock;

struct OutputLine {
  std::string text;
  Clock::time_point at;
};

class EngineProcess {
 public:
  explicit EngineProcess(const std::string& exe);
  ~EngineProcess();
  EngineProcess(const EngineProcess&) = delete;
  EngineProcess& operator=(const EngineProcess&) = delete;

  bool started() const { return started_; }

  // Writes `text` as is (no newline added). Returns false if the pipe is closed.
  bool send_raw(std::string_view text);
  bool send(std::string_view line) { return send_raw(std::string(line) + '\n'); }
  void close_input();

  // Index of the first line at or after `from` for which `match` holds,
  // waiting up to `timeout`; nullopt on timeout or end of output.
  std::optional<std::size_t> wait_for(const std::function<bool(const std::string&)>& match, std::size_t from,
                                      std::chrono::milliseconds timeout);
  // The same for a line starting with `prefix`.
  std::optional<std::size_t> wait_prefix(std::string_view prefix, std::size_t from,
                                         std::chrono::milliseconds timeout);

  std::vector<OutputLine> lines() const;
  std::size_t line_count() const;

  // Exit status once the child has exited within `timeout`; its output is
  // then read to the end (up to 10 s more), so lines() holds every line.
  std::optional<int> wait_exit(std::chrono::milliseconds timeout);

 private:
  void read_loop();
  void add_bytes(const char* data, std::size_t n);

  bool started_ = false;
  bool exited_ = false;
  int exit_code_ = -1;
  mutable std::mutex mutex_;
  std::condition_variable grew_;
  std::vector<OutputLine> lines_;
  std::string partial_;
  bool output_closed_ = false;
  std::thread reader_;
#ifdef _WIN32
  void* process_ = nullptr;
  void* stdin_write_ = nullptr;
  void* stdout_read_ = nullptr;
#else
  int pid_ = -1;
  int stdin_write_ = -1;
  int stdout_read_ = -1;
#endif
};

}  // namespace forkeng::test
