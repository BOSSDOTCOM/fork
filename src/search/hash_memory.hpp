// hash_memory: the memory behind the transposition table (the TT itself is
// Phase 3).
//
// Purpose: allocate the `Hash` option's memory from the operating system and
// clear it in parallel, so a 256 GiB table is ready in seconds.
// Invariants:
// - The size is a whole number of MiB, computed in std::size_t bytes (no
//   32-bit overflow: 33554432 MB = 2^45 bytes).
// - The table is one block, 2 MiB aligned on Linux, where transparent huge
//   pages are requested with madvise(MADV_HUGEPAGE) (a hint: nothing depends
//   on getting them). No chunked fallback (owner, 2026-10-24): Linux checks
//   each mmap against RAM + swap on its own, so chunks would slip past that
//   check and the clear would then summon the OOM killer.
// - A size is tried only if it fits in the physical memory available now
//   (plus the current table, which is freed first if both do not fit), so
//   an overcommitted mmap never reaches the clear.
// - resize() never leaves the table half-built: if the size cannot be had,
//   the previous size (else 1 MiB) is used and the call reports it. Nothing
//   here throws, and a worker thread that cannot start is replaced by the
//   calling thread.
// - After resize() or clear() every byte is zero, written by `workers`
//   threads (first touch: each thread faults in its own slice).
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace forkeng {

constexpr std::size_t BytesPerMB = std::size_t{1} << 20;

// Bytes for a Hash value in MB.
constexpr std::size_t hash_bytes_for_mb(std::uint64_t mb) {
  return static_cast<std::size_t>(mb) * BytesPerMB;
}

// Physical memory available to a new allocation now: MemAvailable from
// /proc/meminfo on Linux, ullAvailPhys on Windows. SIZE_MAX if unknown.
std::size_t available_memory();

class HashMemory {
 public:
  HashMemory() = default;
  ~HashMemory() { release(); }
  HashMemory(const HashMemory&) = delete;
  HashMemory& operator=(const HashMemory&) = delete;

  // Replaces the table with one of `bytes` (a multiple of MiB), cleared by up
  // to `workers` threads. Returns false if that size could not be had;
  // `report` then says why and what size the table has instead.
  bool resize(std::size_t bytes, unsigned workers, std::string& report);
  void clear(unsigned workers);

  std::byte* data() const { return base_; }
  std::size_t bytes() const { return bytes_; }

 private:
  bool fits(std::size_t bytes) const;  // in available memory plus the current table
  bool allocate(std::size_t bytes);    // requires an empty table
  void release();

  std::byte* base_ = nullptr;
  std::size_t bytes_ = 0;
};

// How many threads clear `bytes`: max(threads option, hardware threads), but
// at least 2 MiB per thread, and at least one.
unsigned clear_workers(std::size_t bytes, std::int64_t threads_option);

}  // namespace forkeng
