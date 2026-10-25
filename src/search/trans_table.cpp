#include "search/trans_table.hpp"

#include <algorithm>

namespace forkeng {

namespace {

// How much one search of age difference counts against an entry's depth when
// choosing what to replace (Fork's own choice).
constexpr int AgePenalty = 4;
// Buckets sampled for fill_permille (200 x 5 = 1000 entries).
constexpr std::size_t FillSampleBuckets = 200;

constexpr std::uint8_t pack_meta(TtBound bound, bool pv, int age) {
  return static_cast<std::uint8_t>(static_cast<int>(bound) | (pv ? 4 : 0) | (age << 3));
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
  const auto check = static_cast<std::uint32_t>(key);
  for (const TtEntry& slot : b.entries) {
    const TtEntry e = slot;  // one copy, then only the copy is read
    if (e.key_check != check || e.bound() == TtBound::None) continue;
    hit = {Move::from_raw(e.move), e.score, e.eval, e.depth, e.bound(), e.was_pv()};
    return true;
  }
  return false;
}

void TransTable::deposit(Key key, Move move, int score, int eval, int depth, TtBound bound, bool pv) {
  if (!count_) return;
  TtBucket& b = buckets_[bucket_index(key, count_)];
  const auto check = static_cast<std::uint32_t>(key);
  // The slot: this position's own entry, else an empty one, else the entry
  // worth least (shallowest, older searches counting less).
  TtEntry* target = nullptr;
  int least = 1 << 30;
  for (TtEntry& e : b.entries) {
    if (e.bound() == TtBound::None || e.key_check == check) {
      target = &e;
      break;
    }
    const int worth = e.depth - AgePenalty * ((age_ - e.age()) & 31);
    if (worth < least) {
      least = worth;
      target = &e;
    }
  }
  const int stored_depth = std::clamp(depth, 0, 255);
  TtEntry e = *target;
  if (e.key_check == check && e.bound() != TtBound::None) {
    // Same position: keep a deeper result from this search unless the new
    // one is exact; keep the old move when the new search found none.
    if (bound != TtBound::Exact && e.age() == age_ && stored_depth + 2 < e.depth) return;
    if (move.is_none()) move = Move::from_raw(e.move);
  }
  e.key_check = check;
  e.move = move.raw();
  e.score = static_cast<std::int16_t>(score);
  e.eval = static_cast<std::int16_t>(eval);
  e.depth = static_cast<std::uint8_t>(stored_depth);
  e.meta = pack_meta(bound, pv, age_);
  *target = e;  // written whole
}

int TransTable::fill_permille() const {
  const std::size_t n = std::min(count_, FillSampleBuckets);
  if (!n) return 0;
  std::size_t used = 0;
  for (std::size_t i = 0; i < n; ++i)
    for (const TtEntry& e : buckets_[i].entries) used += e.bound() != TtBound::None && e.age() == age_;
  return static_cast<int>(used * 1000 / (n * EntriesPerBucket));
}

}  // namespace forkeng
