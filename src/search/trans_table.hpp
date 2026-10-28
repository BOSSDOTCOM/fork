// SPDX-License-Identifier: GPL-3.0-or-later

// trans_table: the transposition table (DESIGN.md §5.2, deliverable 3).
//
// Purpose: remember, per position, the best move found, its score with the
// kind of bound, the depth searched and the static evaluation, so that
// revisits can cut off or at least try the best move first.
// Invariants:
// - Lives in the `Hash` option's memory (HashMemory); TransTable is a view
//   over it and owns nothing. All-zero memory is an empty table.
// - One 64-byte bucket per cache line, five 12-byte entries plus 4 spare
//   bytes (Fork's own layout). An entry holds 24 key-check bits (the key's
//   low bits) with a whole byte for the age of the search that wrote it, the
//   move, the score (node-relative for mates and tablebase results,
//   score_bounds.hpp), the static eval, the depth, and a byte of flags: the
//   bound and the TT-PV flag (T19). With 24 check bits and every TT move
//   validated before use, a false match is harmless (Hyatt and Cozzie 2005,
//   KB search-techniques.md T4).
// - Replacement follows the KB's description (techniques.md, "Transposition
//   table"): prefer deeper and current-search entries, replace stale ones.
// - The bucket is chosen by a multiply-high range reduction of the full
//   64-bit key (Lemire; docs/ORIGINALITY.md): the high half of the 64 x 64-bit
//   product, so any bucket count up to 2^42 / 64 (the 4 TiB maximum Hash) is
//   exact.
// - The age wraps after 256 searches: an entry that survived exactly 256
//   searches untouched would look current again. Accepted: entries are
//   replaced long before that.
// - Torn writes (owner, 2026-10-24, for Phase 6's shared table): an entry is
//   12 bytes, which x86-64 cannot store atomically, so it is self-verifying
//   instead. Its stored check is the key's 24 bits XORed with a 24-bit digest
//   of all its other fields (age included); an entry whose words come from
//   two different writes fails the check (but for a 1 in 2^24 digest
//   collision) and reads as a miss. Entries are read and written as whole
//   copies. Phase 6 must still make the accesses relaxed atomics (or
//   equivalent) so concurrent reads are not undefined behaviour, and adds
//   the torn-write stress test under TSan (DESIGN.md §5, Phase 6).
#pragma once

#include <cstddef>
#include <cstdint>

#include "core/types.hpp"

namespace forkeng {

enum class TtBound : std::uint8_t { None = 0, Upper = 1, Lower = 2, Exact = 3 };

struct TtEntry {
  std::uint32_t
      key_and_age;  // bits 8-31: key check (key bits XOR data digest); bits 0-7: the writing search's age
  std::uint16_t move;
  std::int16_t score;
  std::int16_t eval;
  std::uint8_t depth;
  std::uint8_t flags;  // bits 0-1 bound, bit 2 TT-PV

  std::uint32_t key_check() const { return key_and_age >> 8; }
  int age() const { return key_and_age & 0xFF; }
  TtBound bound() const { return TtBound(flags & 3); }
  bool was_pv() const { return flags & 4; }
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

// Whether a score with this bound settles a node searched with the window
// (alpha, beta): an exact score always, a lower bound at or above beta, an
// upper bound at or below alpha.
constexpr bool bound_settles(TtBound bound, int score, int alpha, int beta) {
  return bound == TtBound::Exact || (bound == TtBound::Lower && score >= beta) ||
         (bound == TtBound::Upper && score <= alpha);
}

// The bound a fail-soft result carries for a node searched with the window
// (alpha_start, beta): exact only at PV nodes, the only ones searched with a
// full window.
constexpr TtBound result_bound(int best, int alpha_start, int beta, bool on_pv) {
  return best >= beta ? TtBound::Lower : on_pv && best > alpha_start ? TtBound::Exact : TtBound::Upper;
}

class TransTable {
 public:
  // Uses `bytes` of `memory` (64-byte aligned) as the table; null or fewer
  // than 64 bytes leave it empty and unusable (fetch misses, deposit is ignored).
  void bind_memory(std::byte* memory, std::size_t bytes);

  // Starts a new search: entries from earlier searches become stale.
  void advance_age() { ++search_age_; }
  // The victim policy (owner's experiment, 2026-10-26): off, every entry of
  // the current search outranks every stale one (then depth decides); on,
  // a slot is worth its depth minus StaleDepthPerSearch plies per search of
  // age, so a deep stale entry can outrank a shallow current one.
  void set_age_blend(bool on) { age_blend_ = on; }
  // Off: within one search, any result at least as deep replaces the
  // position's entry. On (review 2, claim (e), 2026-10-26): an exact entry is
  // not replaced by a bound of the same depth, which carries less.
  void set_keep_exact(bool on) { keep_exact_ = on; }
  // On (audit-1, B-5): the position's entry from an earlier search is kept
  // against an inexact result while it is still deeper after losing
  // StaleDepthPerSearch plies per search of age.
  void set_keep_deeper(bool on) { keep_deeper_ = on; }

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
  std::uint8_t search_age_ = 0;  // wraps at 256
  bool age_blend_ = false;
  bool keep_exact_ = false;
  bool keep_deeper_ = false;
};

}  // namespace forkeng
