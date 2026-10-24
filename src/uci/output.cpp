#include "uci/output.hpp"

#include <cerrno>
#include <chrono>
#include <cstring>
#include <ctime>

namespace forkeng {

OutputChannel::~OutputChannel() {
  if (log_) std::fclose(log_);
}

void OutputChannel::send_line(std::string_view line) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (out_) {
    std::fwrite(line.data(), 1, line.size(), out_);
    std::fputc('\n', out_);
    std::fflush(out_);
  }
  write_log('<', line);
}

void OutputChannel::log_input(std::string_view line) {
  std::lock_guard<std::mutex> lock(mutex_);
  write_log('>', line);
}

bool OutputChannel::open_log(const std::string& path, std::string* error) {
  std::FILE* f = nullptr;
  if (!path.empty()) {
    f = std::fopen(path.c_str(), "a");
    if (!f) {
      if (error) *error = std::strerror(errno);
      return false;
    }
  }
  std::lock_guard<std::mutex> lock(mutex_);
  if (log_) std::fclose(log_);
  log_ = f;
  return true;
}

// "2026-10-24T12:34:56.789Z > isready": '>' for input, '<' for output.
void OutputChannel::write_log(char direction, std::string_view line) {
  if (!log_) return;
  const auto now = std::chrono::system_clock::now();
  const std::time_t secs = std::chrono::system_clock::to_time_t(now);
  const auto ms =
      std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count() % 1000;
  std::tm utc{};
#ifdef _WIN32
  gmtime_s(&utc, &secs);
#else
  gmtime_r(&secs, &utc);
#endif
  char stamp[32];
  std::strftime(stamp, sizeof stamp, "%Y-%m-%dT%H:%M:%S", &utc);
  std::fprintf(log_, "%s.%03dZ %c %.*s\n", stamp, static_cast<int>(ms), direction,
               static_cast<int>(line.size()), line.data());
  std::fflush(log_);
}

}  // namespace forkeng
