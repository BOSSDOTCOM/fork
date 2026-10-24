#include "search/hash_memory.hpp"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <limits>
#include <thread>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX  // libstdc++ for MinGW defines it already
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <sys/mman.h>
#endif

namespace forkeng {

namespace {

constexpr std::size_t PageAlign = 2 * BytesPerMB;  // a transparent huge page on x86-64 Linux

// Zeroed memory straight from the OS, or nullptr. Not operator new: a
// refused request must come back as nullptr in every build (sanitizer
// allocators abort on huge requests by default), and the pages should not
// be touched until the parallel clear touches them.
std::byte* os_allocate(std::size_t bytes) {
#ifdef _WIN32
  return static_cast<std::byte*>(VirtualAlloc(nullptr, bytes, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
#else
  // Over-allocate, then trim to a 2 MiB-aligned block.
  const std::size_t padded = bytes + PageAlign;
  void* p = mmap(nullptr, padded, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (p == MAP_FAILED) return nullptr;
  const auto start = reinterpret_cast<std::uintptr_t>(p);
  const std::uintptr_t aligned = (start + PageAlign - 1) & ~std::uintptr_t{PageAlign - 1};
  const std::size_t head = aligned - start;
  const std::size_t tail = padded - head - bytes;
  if (head) munmap(p, head);
  if (tail) munmap(reinterpret_cast<void*>(aligned + bytes), tail);
#ifdef MADV_HUGEPAGE
  madvise(reinterpret_cast<void*>(aligned), bytes, MADV_HUGEPAGE);  // a hint; failure is fine
#endif
  return reinterpret_cast<std::byte*>(aligned);
#endif
}

void os_free(std::byte* p, std::size_t bytes) {
#ifdef _WIN32
  (void)bytes;
  VirtualFree(p, 0, MEM_RELEASE);
#else
  munmap(p, bytes);
#endif
}

}  // namespace

std::size_t available_memory() {
#ifdef _WIN32
  MEMORYSTATUSEX status{};
  status.dwLength = sizeof status;
  if (!GlobalMemoryStatusEx(&status)) return std::numeric_limits<std::size_t>::max();
  return static_cast<std::size_t>(status.ullAvailPhys);
#else
  // "MemAvailable:   12345678 kB" (Linux 3.14+): free memory plus what the
  // kernel can reclaim without swapping.
  std::FILE* f = std::fopen("/proc/meminfo", "r");
  if (!f) return std::numeric_limits<std::size_t>::max();
  char line[256];
  unsigned long long kb = 0;
  bool found = false;
  while (!found && std::fgets(line, sizeof line, f))
    found = std::sscanf(line, "MemAvailable: %llu kB", &kb) == 1;
  std::fclose(f);
  return found ? static_cast<std::size_t>(kb) * 1024 : std::numeric_limits<std::size_t>::max();
#endif
}

unsigned clear_workers(std::size_t bytes, std::int64_t threads_option) {
  const std::int64_t hardware = std::max<std::int64_t>(1, std::thread::hardware_concurrency());
  const std::int64_t wanted = std::max(threads_option, hardware);
  const auto by_size = static_cast<std::int64_t>(std::max<std::size_t>(1, bytes / PageAlign));
  return static_cast<unsigned>(std::max<std::int64_t>(1, std::min(wanted, by_size)));
}

bool HashMemory::fits(std::size_t bytes) const {
  const std::size_t available = available_memory();
  return available == std::numeric_limits<std::size_t>::max() || bytes <= available ||
         bytes - available <= bytes_;
}

bool HashMemory::allocate(std::size_t bytes) {
  base_ = os_allocate(bytes);
  bytes_ = base_ ? bytes : 0;
  return base_ != nullptr;
}

void HashMemory::release() {
  if (base_) os_free(base_, bytes_);
  base_ = nullptr;
  bytes_ = 0;
}

bool HashMemory::resize(std::size_t bytes, unsigned workers, std::string& report) {
  if (bytes == bytes_) {
    clear(workers);
    return true;
  }
  const std::size_t old_bytes = bytes_;
  const bool room = fits(bytes);
  if (room) {
    // First beside the old table, then, if there is no room for both, alone.
    std::byte* const old_base = base_;
    base_ = nullptr;
    bytes_ = 0;
    const bool beside = allocate(bytes);
    if (old_base) os_free(old_base, old_bytes);
    if (beside || allocate(bytes)) {
      clear(workers);
      return true;
    }
  } else {
    release();
  }
  report = room ? "cannot allocate " + std::to_string(bytes / BytesPerMB) + " MB of hash"
                : "Hash " + std::to_string(bytes / BytesPerMB) + " MB is more than the " +
                      std::to_string(available_memory() / BytesPerMB) + " MB of memory available";
  for (std::size_t fallback : {old_bytes, BytesPerMB}) {
    if (fallback && fallback < bytes && fits(fallback) && allocate(fallback)) {
      clear(workers);
      report += "; using " + std::to_string(fallback / BytesPerMB) + " MB";
      return false;
    }
  }
  report += "; no hash table";
  return false;
}

void HashMemory::clear(unsigned workers) {
  if (bytes_ == 0) return;
  workers = std::max(1u, workers);
  // Each worker zeroes one contiguous slice.
  const std::size_t slice = (bytes_ + workers - 1) / workers;
  auto zero_slice = [this, slice](unsigned w) {
    const std::size_t begin = std::min(bytes_, w * slice), end = std::min(bytes_, begin + slice);
    std::memset(base_ + begin, 0, end - begin);
  };
  std::vector<std::thread> helpers;
  try {
    helpers.reserve(workers - 1);
  } catch (...) {  // no room for the list: every slice on this thread
  }
  for (unsigned w = 1; w < workers; ++w) {
    try {
      if (helpers.size() == helpers.capacity()) throw std::bad_alloc();
      helpers.emplace_back(zero_slice, w);
    } catch (...) {  // no thread to be had: do that slice here
      zero_slice(w);
    }
  }
  zero_slice(0);
  for (std::thread& t : helpers) t.join();
}

}  // namespace forkeng
