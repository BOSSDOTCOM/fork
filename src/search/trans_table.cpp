#include "search/trans_table.hpp"

#include <algorithm>
#include "tune/params.hpp"

namespace forkeng {

namespace {

// Buckets sampled for fill_permille (200 x 5 = 1000 entries).
constexpr std::size_t FillSampleBuckets = 200;

constexpr std::uint32_t KeyCheckBits = 24;

constexpr std::uint32_t KeyCheckMask = (1u << KeyCheckBits) - 1;

std::uint32_t key_check_of(Key key) { return static_cast<std::uint32_t>(key) & KeyCheckMask; }

// A 24-bit digest of everything an entry stores besides its check: the
// stored check is the key's 24 bits XORed with it, so an entry whose words
// come from two different writes (a torn write under Phase 6's shared
// table) fails the check and reads as a miss, unless the 24-bit digests
// collide (Fork's own design, DESIGN.md §5.2 deliverable 3).
std::uint32_t data_digest(std::uint16_t move, std::int16_t score, std::int16_t eval, std::uint8_t depth,
                          std::uint8_t flags, std::uint8_t age) {
  std::uint64_t x = move | std::uint64_t{static_cast<std::uint16_t>(score)} << 16 |
                    std::uint64_t{static_cast<std::uint16_t>(eval)} << 32 | std::uint64_t{depth} << 48 |
                    std::uint64_t{flags} << 56;
  x ^= std::uint64_t{age} * 0x9E3779B97F4A7C15ULL;
  x *= 0xD6E8FEB86659FD93ULL;
  return static_cast<std::uint32_t>(x >> 40) & KeyCheckMask;
}

// The check an entry would carry for `key` given its own data.
std::uint32_t expected_check(const TtEntry& e, std::uint32_t key_bits) {
  return key_bits ^
         data_digest(e.move, e.score, e.eval, e.depth, e.flags, static_cast<std::uint8_t>(e.age()));
}

// StaleDepthPerSearch (src/tune/params.hpp): plies a stored depth loses per
// search of age under the blended policy. Between two of Fork's searches in a
// game two plies are played, so a stored position is two plies nearer the new
// root, and the new search asks it for two plies more depth than the one that
// wrote it (DESIGN.md §5.2, "Search constants").

// How much a slot is worth keeping. Lexicographic (the default): every entry
// of the current search ranks above every stale one; within each group,
// deeper ranks higher. Blended: depth minus StaleDepthPerSearch per search of
// age (the age wraps at 256, so the gap is taken modulo 256).
// Above any depth (a uint8), so a current entry outranks every stale one.
constexpr int CurrentSearchBonus = 256;

int slot_rank(const TtEntry& e, std::uint8_t search_age, bool age_blend) {
  if (age_blend) {
    const int age_gap = static_cast<std::uint8_t>(search_age - static_cast<std::uint8_t>(e.age()));
    return e.depth - StaleDepthPerSearch * age_gap;
  }
  return (e.age() == search_age ? CurrentSearchBonus : 0) + e.depth;
}

}  // namespace

void TransTable::bind_memory(std::byte* memory, std::size_t bytes) {
  buckets_ = reinterpret_cast<TtBucket*>(memory);
  count_ = memory ? bytes / sizeof(TtBucket) : 0;
}

// Lemire's multiply-high range reduction: the high 64 bits of key * count
// lie in [0, count) and spread the keys evenly.
std::size_t TransTable::bucket_index(Key key, std::size_t bucket_count) {
  __extension__ using Uint128 = unsigned __int128;
  return static_cast<std::size_t>((static_cast<Uint128>(key) * bucket_count) >> 64);
}

bool TransTable::fetch(Key key, TtHit& hit) const {
  if (!count_) return false;
  const TtBucket& b = buckets_[bucket_index(key, count_)];
  const std::uint32_t check = key_check_of(key);
  for (const TtEntry& slot : b.entries) {
    const TtEntry e = slot;  // one copy, then only the copy is read
    if (e.bound() == TtBound::None || e.key_check() != expected_check(e, check)) continue;
    hit = {Move::from_raw(e.move), e.score, e.eval, e.depth, e.bound(), e.was_pv()};
    return true;
  }
  return false;
}

void TransTable::deposit(Key key, Move move, int score, int eval, int depth, TtBound bound, bool pv) {
  if (!count_) return;
  TtBucket& b = buckets_[bucket_index(key, count_)];
  const std::uint32_t check = key_check_of(key);
  const int stored_depth = std::clamp(depth, 0, 255);

  // This position's own entry, if it has one.
  TtEntry* own = nullptr;
  for (TtEntry& e : b.entries)
    if (e.bound() != TtBound::None && e.key_check() == expected_check(e, check)) {
      own = &e;
      break;
    }
  TtEntry* target = own;
  if (own) {
    // A deeper result of this same search is worth more than a shallower,
    // inexact one; and the position keeps its best move if the new search
    // found none.
    if (own->age() == search_age_ && bound != TtBound::Exact &&
        (stored_depth < own->depth ||
         (keep_exact_ && stored_depth == own->depth && own->bound() == TtBound::Exact)))
      return;
    // An earlier search's result for this position, still deeper once aged
    // (it is that many plies nearer the root now), is worth more than an
    // inexact shallower one (audit-1, B-5).
    if (keep_deeper_ && own->age() != search_age_ && bound != TtBound::Exact) {
      const int age_gap = static_cast<std::uint8_t>(search_age_ - static_cast<std::uint8_t>(own->age()));
      if (own->depth - StaleDepthPerSearch * age_gap > stored_depth) return;
    }
    if (move.is_none()) move = Move::from_raw(own->move);
  } else {
    // An empty slot, else the slot least worth keeping (first on ties).
    for (TtEntry& e : b.entries) {
      if (e.bound() == TtBound::None) {
        target = &e;
        break;
      }
      if (!target || slot_rank(e, search_age_, age_blend_) < slot_rank(*target, search_age_, age_blend_))
        target = &e;
    }
  }
  TtEntry e;
  e.key_and_age = search_age_;
  e.move = move.raw();
  e.score = static_cast<std::int16_t>(score);
  e.eval = static_cast<std::int16_t>(eval);
  e.depth = static_cast<std::uint8_t>(stored_depth);
  e.flags = static_cast<std::uint8_t>(static_cast<int>(bound) | (pv ? 4 : 0));
  e.key_and_age |= expected_check(e, check) << 8;
  *target = e;  // written whole
}

int TransTable::fill_permille() const {
  const std::size_t n = std::min(count_, FillSampleBuckets);
  if (!n) return 0;
  std::size_t used = 0;
  for (std::size_t i = 0; i < n; ++i)
    for (const TtEntry& e : buckets_[i].entries) used += e.bound() != TtBound::None && e.age() == search_age_;
  return static_cast<int>(used * 1000 / (n * EntriesPerBucket));
}

}  // namespace forkeng
