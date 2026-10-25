// trans_table: the transposition table (DESIGN.md §5.2, deliverable 3).
//
// Purpose: remember, per position, the best move found, its score with the
// kind of bound, the depth searched and the static evaluation, so that
// revisits can cut off or at least try the best move first.
// Invariants:
// - Lives in the `Hash` option's memory (HashMemory); TransTable is a view
//   over it and owns nothing. All-zero memory is an empty table.
// - One 64-byte bucket per cache line, five 12-byte entries plus 4 spare
//   bytes (Fork's own layout). An entry holds 32 key-check bits (the key's
//   low half), the move, the score (node-relative for mates and tablebase
//   results, score_bounds.hpp), the static eval, the depth, and 8 bits for
//   the bound (2), the TT-PV flag (1, T19) and the age (5).
// - The bucket is chosen by a multiply-high range reduction of the full
//   64-bit key (Lemire; docs/ORIGINALITY.md): the high half of the 64 x 64-bit
//   product, so any bucket count up to 2^42 / 64 (the 4 TiB maximum Hash) is
//   exact.
// - The age is 5 bits and wraps every 32 searches: an entry that survived
//   exactly 32 (64, ...) searches untouched looks current again (hashfull,
//   replacement). Accepted: such entries are rare, as entries are replaced
//   long before that (review, 2026-10-24).
// - An entry is read and written whole (a copy), as Phase 6's lockless
//   sharing needs; a read never returns a half-written entry to the caller
//   on one thread.
#pragma once

#include <cstddef>
#include <cstdint>

#include "core/types.hpp"

namespace forkeng {

enum class TtBound : std::uint8_t { None = 0, Upper = 1, Lower = 2, Exact = 3 };

struct TtEntry {
  std::uint32_t key_check;
  std::uint16_t move;
  std::int16_t score;
  std::int16_t eval;
  std::uint8_t depth;
  std::uint8_t meta;  // bits 0-1 bound, bit 2 TT-PV, bits 3-7 age

  TtBound bound() const { return TtBound(meta & 3); }
  bool was_pv() const { return meta & 4; }
  int age() const { return meta >> 3; }
};
static_assert(sizeof(TtEntry) == 12);

constexpr std::size_t EntriesPerBucket = 5;

struct alignas(64) TtBucket {
  TtEntry entries[EntriesPerBucket];
  std::uint32_t spare;
};
static_assert(sizeof(TtBucket) == 64);

// What a successful fetch returns, already unpacked.
struct TtHit {
  Move move;
  int score;  // node-relative: convert with score_from_tt
  int eval;
  int depth;
  TtBound bound;
  bool was_pv;
};

class TransTable {
 public:
  // Uses `bytes` of `memory` (64-byte aligned) as the table; null or fewer
  // than 64 bytes leave it empty and unusable (fetch misses, deposit is ignored).
  void bind_memory(std::byte* memory, std::size_t bytes);

  // Starts a new search: entries from earlier searches age.
  void advance_age() { age_ = (age_ + 1) & 31; }

  static std::size_t bucket_index(Key key, std::size_t bucket_count);

  void prefetch_bucket(Key key) const {
    if (count_) __builtin_prefetch(&buckets_[bucket_index(key, count_)]);
  }
  bool fetch(Key key, TtHit& hit) const;
  // `score` must already be node-relative (score_to_tt). Depth below 0 is
  // stored as 0 (the quiescence search).
  void deposit(Key key, Move move, int score, int eval, int depth, TtBound bound, bool pv);

  // Per mille of a sample of entries written in the current search (UCI hashfull).
  int fill_permille() const;

  std::size_t bucket_count() const { return count_; }

 private:
  TtBucket* buckets_ = nullptr;
  std::size_t count_ = 0;
  std::uint8_t age_ = 0;
};

}  // namespace forkeng
