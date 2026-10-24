#include "engine_process.hpp"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX  // libstdc++ for MinGW defines it already
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cerrno>
#include <csignal>
#endif

namespace forkeng::test {

#ifdef _WIN32

EngineProcess::EngineProcess(const std::string& exe) {
  SECURITY_ATTRIBUTES inherit{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
  HANDLE in_read = nullptr, in_write = nullptr, out_read = nullptr, out_write = nullptr;
  if (!CreatePipe(&in_read, &in_write, &inherit, 0)) return;
  if (!CreatePipe(&out_read, &out_write, &inherit, 0)) {
    CloseHandle(in_read);
    CloseHandle(in_write);
    return;
  }
  // The parent's ends must not leak into the child, or EOF never arrives.
  SetHandleInformation(in_write, HANDLE_FLAG_INHERIT, 0);
  SetHandleInformation(out_read, HANDLE_FLAG_INHERIT, 0);
  STARTUPINFOA si{};
  si.cb = sizeof si;
  si.dwFlags = STARTF_USESTDHANDLES;
  si.hStdInput = in_read;
  si.hStdOutput = out_write;
  si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
  PROCESS_INFORMATION pi{};
  std::string command = "\"" + exe + "\"";
  const BOOL ok =
      CreateProcessA(nullptr, command.data(), nullptr, nullptr, TRUE, 0, nullptr, nullptr, &si, &pi);
  CloseHandle(in_read);
  CloseHandle(out_write);
  if (!ok) {
    CloseHandle(in_write);
    CloseHandle(out_read);
    return;
  }
  CloseHandle(pi.hThread);
  process_ = pi.hProcess;
  stdin_write_ = in_write;
  stdout_read_ = out_read;
  started_ = true;
  reader_ = std::thread(&EngineProcess::read_loop, this);
}

EngineProcess::~EngineProcess() {
  if (!started_) return;
  close_input();
  if (!wait_exit(std::chrono::milliseconds(0))) {
    TerminateProcess(static_cast<HANDLE>(process_), 255);
    WaitForSingleObject(static_cast<HANDLE>(process_), INFINITE);
  }
  if (reader_.joinable()) reader_.join();
  CloseHandle(static_cast<HANDLE>(stdout_read_));
  CloseHandle(static_cast<HANDLE>(process_));
}

bool EngineProcess::send_raw(std::string_view text) {
  if (!stdin_write_) return false;
  while (!text.empty()) {
    DWORD wrote = 0;
    if (!WriteFile(static_cast<HANDLE>(stdin_write_), text.data(), static_cast<DWORD>(text.size()), &wrote,
                   nullptr))
      return false;
    text.remove_prefix(wrote);
  }
  return true;
}

void EngineProcess::close_input() {
  if (stdin_write_) CloseHandle(static_cast<HANDLE>(stdin_write_));
  stdin_write_ = nullptr;
}

void EngineProcess::read_loop() {
  char buf[4096];
  DWORD got = 0;
  while (ReadFile(static_cast<HANDLE>(stdout_read_), buf, sizeof buf, &got, nullptr) && got > 0)
    add_bytes(buf, got);
  add_bytes(nullptr, 0);
}

std::optional<int> EngineProcess::wait_exit(std::chrono::milliseconds timeout) {
  if (exited_) return exit_code_;
  if (!started_) return std::nullopt;
  if (WaitForSingleObject(static_cast<HANDLE>(process_), static_cast<DWORD>(timeout.count())) !=
      WAIT_OBJECT_0)
    return std::nullopt;
  DWORD code = 0;
  GetExitCodeProcess(static_cast<HANDLE>(process_), &code);
  exited_ = true;
  exit_code_ = static_cast<int>(code);
  return exit_code_;
}

#else

EngineProcess::EngineProcess(const std::string& exe) {
  (void)std::signal(SIGPIPE, SIG_IGN);  // a dead engine must fail a write, not kill the test
  int in[2], out[2];
  if (pipe2(in, O_CLOEXEC) != 0) return;
  if (pipe2(out, O_CLOEXEC) != 0) {
    close(in[0]);
    close(in[1]);
    return;
  }
  const pid_t pid = fork();
  if (pid == 0) {
    // Child: only async-signal-safe calls until exec. dup2 clears CLOEXEC on 0 and 1.
    dup2(in[0], 0);
    dup2(out[1], 1);
    execl(exe.c_str(), exe.c_str(), static_cast<char*>(nullptr));
    _exit(127);
  }
  close(in[0]);
  close(out[1]);
  if (pid < 0) {
    close(in[1]);
    close(out[0]);
    return;
  }
  pid_ = pid;
  stdin_write_ = in[1];
  stdout_read_ = out[0];
  started_ = true;
  reader_ = std::thread(&EngineProcess::read_loop, this);
}

EngineProcess::~EngineProcess() {
  if (!started_) return;
  close_input();
  if (!wait_exit(std::chrono::milliseconds(0))) {
    kill(pid_, SIGKILL);
    int status = 0;
    waitpid(pid_, &status, 0);
  }
  if (reader_.joinable()) reader_.join();
  close(stdout_read_);
}

bool EngineProcess::send_raw(std::string_view text) {
  if (stdin_write_ < 0) return false;
  while (!text.empty()) {
    const ssize_t n = write(stdin_write_, text.data(), text.size());
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) return false;
    text.remove_prefix(static_cast<std::size_t>(n));
  }
  return true;
}

void EngineProcess::close_input() {
  if (stdin_write_ >= 0) close(stdin_write_);
  stdin_write_ = -1;
}

void EngineProcess::read_loop() {
  char buf[4096];
  for (;;) {
    const ssize_t n = read(stdout_read_, buf, sizeof buf);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) break;
    add_bytes(buf, static_cast<std::size_t>(n));
  }
  add_bytes(nullptr, 0);
}

std::optional<int> EngineProcess::wait_exit(std::chrono::milliseconds timeout) {
  if (exited_) return exit_code_;
  if (!started_) return std::nullopt;
  const auto deadline = Clock::now() + timeout;
  for (;;) {
    int status = 0;
    const pid_t r = waitpid(pid_, &status, WNOHANG);
    if (r == pid_) {
      exited_ = true;
      exit_code_ = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
      return exit_code_;
    }
    if (Clock::now() >= deadline) return std::nullopt;
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
}

#endif

// data == nullptr marks the end of output.
void EngineProcess::add_bytes(const char* data, std::size_t n) {
  const auto now = Clock::now();
  std::scoped_lock lock(mutex_);
  if (!data) {
    if (!partial_.empty()) lines_.push_back({partial_, now});
    partial_.clear();
    output_closed_ = true;
  } else {
    for (std::size_t i = 0; i < n; ++i) {
      if (data[i] == '\n') {
        if (!partial_.empty() && partial_.back() == '\r') partial_.pop_back();
        lines_.push_back({partial_, now});
        partial_.clear();
      } else {
        partial_ += data[i];
      }
    }
  }
  grew_.notify_all();
}

std::optional<std::size_t> EngineProcess::wait_for(const std::function<bool(const std::string&)>& match,
                                                   std::size_t from, std::chrono::milliseconds timeout) {
  const auto deadline = Clock::now() + timeout;
  std::unique_lock<std::mutex> lock(mutex_);
  for (;;) {
    for (; from < lines_.size(); ++from)
      if (match(lines_[from].text)) return from;
    if (output_closed_) return std::nullopt;
    if (grew_.wait_until(lock, deadline) == std::cv_status::timeout) {
      for (; from < lines_.size(); ++from)
        if (match(lines_[from].text)) return from;
      return std::nullopt;
    }
  }
}

std::optional<std::size_t> EngineProcess::wait_prefix(std::string_view prefix, std::size_t from,
                                                      std::chrono::milliseconds timeout) {
  return wait_for([prefix](const std::string& s) { return std::string_view(s).starts_with(prefix); }, from,
                  timeout);
}

std::vector<OutputLine> EngineProcess::lines() const {
  std::scoped_lock lock(mutex_);
  return lines_;
}

std::size_t EngineProcess::line_count() const {
  std::scoped_lock lock(mutex_);
  return lines_.size();
}

}  // namespace forkeng::test
