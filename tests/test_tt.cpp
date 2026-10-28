// The transposition table (DESIGN.md §5.2, deliverable 3).
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>

#include "core/splitmix.hpp"
#include "harness.hpp"
#include "search/score_bounds.hpp"
#include "search/trans_table.hpp"

namespace forkeng::test {

namespace {

// A table over `buckets` buckets of plain aligned memory, zeroed (empty).
struct TestTable {
  explicit TestTable(std::size_t buckets) : storage(buckets ? buckets : 1) {
    table.bind_memory(memory_bytes(), buckets * sizeof(TtBucket));
  }
  std::byte* memory_bytes() { return reinterpret_cast<std::byte*>(storage.data()); }
  std::vector<TtBucket> storage;
  TransTable table;
};

}  // namespace

// Audit-1 Q-8: the band clamp of score_from_tt (review, 2026-10-24). The
// conversion cases of this suite use scores that stay inside their band, so
// removing the clamp passed every test (mutant M08). Every mate and
// tablebase score, read back at any ply, must stay a score of its own kind
// and sign (score_bounds.hpp's bands).
TEST_CASE("tt", "score_from_tt keeps every mate and tablebase score in its band at every ply") {
  for (int ply = 0; ply <= MaxPly; ++ply) {
    for (int n = 0; n <= MaxPly; ++n) {
      const int mate = score_from_tt(mate_score(n), ply), mated = score_from_tt(mated_score(n), ply);
      CHECK_MSG(is_mate_score(mate) && mate > 0, "mate at " << n << ", read at ply " << ply << ": " << mate);
      CHECK_MSG(is_mate_score(mated) && mated < 0,
                "mated at " << n << ", read at ply " << ply << ": " << mated);
      const int win = score_from_tt(TbWinScore - n, ply), loss = score_from_tt(-(TbWinScore - n), ply);
      CHECK_MSG(is_tb_or_mate(win) && !is_mate_score(win) && win > 0,
                "win " << n << " at ply " << ply << ": " << win);
      CHECK_MSG(is_tb_or_mate(loss) && !is_mate_score(loss) && loss < 0,
                "loss " << n << " at ply " << ply << ": " << loss);
    }
  }
}

TEST_CASE("tt", "deposit then fetch returns the entry; other keys miss; an unbound table misses") {
  TestTable t(1024);
  const Key key = 0x123456789abcdef0ULL;
  t.table.deposit(key, Move(12, 28, Quiet), 57, -13, 9, TtBound::Lower, true);
  TtHit hit{};
  CHECK(t.table.fetch(key, hit));
  CHECK(hit.move == Move(12, 28, Quiet));
  CHECK_EQ(hit.score, 57);
  CHECK_EQ(hit.eval, -13);
  CHECK_EQ(hit.depth, 9);
  CHECK(hit.bound == TtBound::Lower);
  CHECK(hit.was_pv);
  CHECK(!t.table.fetch(key ^ 1, hit));  // another key-check value in the same bucket
  TransTable unbound;
  CHECK(!unbound.fetch(key, hit));
  unbound.deposit(key, NoMove, 0, 0, 1, TtBound::Exact, false);  // ignored, no crash
  CHECK_EQ(unbound.fill_permille(), 0);
}

TEST_CASE("tt", "a bucket holds five positions; a sixth replaces the shallowest, then older searches first") {
  TestTable t(1);  // every key maps to bucket 0
  for (int i = 0; i < 5; ++i) t.table.deposit(Key(i + 1), NoMove, i, 0, 10 + i, TtBound::Exact, false);
  TtHit hit{};
  for (int i = 0; i < 5; ++i) CHECK(t.table.fetch(Key(i + 1), hit));
  t.table.deposit(Key(6), NoMove, 0, 0, 20, TtBound::Exact, false);
  CHECK(!t.table.fetch(Key(1), hit));  // depth 10 was the shallowest
  CHECK(t.table.fetch(Key(6), hit));
  // Entries from earlier searches are replaced before any of the current
  // search's, however deep they are.
  for (int i = 0; i < 6; ++i) t.table.advance_age();
  t.table.deposit(Key(7), NoMove, 0, 0, 1, TtBound::Exact, false);
  CHECK(t.table.fetch(Key(7), hit));
  t.table.deposit(Key(8), NoMove, 0, 0, 1, TtBound::Exact, false);
  CHECK(t.table.fetch(Key(7), hit));  // the current search's entry survives
  CHECK(t.table.fetch(Key(8), hit));
}

TEST_CASE("tt",
          "same position: a much shallower result does not overwrite; an exact one does; the move is kept") {
  TestTable t(64);
  const Key key = 42;
  t.table.deposit(key, Move(1, 2, Quiet), 10, 0, 12, TtBound::Lower, false);
  t.table.deposit(key, NoMove, 20, 0, 3, TtBound::Upper, false);
  TtHit hit{};
  CHECK(t.table.fetch(key, hit));
  CHECK_EQ(hit.depth, 12);
  t.table.deposit(key, NoMove, 30, 0, 3, TtBound::Exact, false);
  CHECK(t.table.fetch(key, hit));
  CHECK_EQ(hit.depth, 3);
  CHECK_EQ(hit.score, 30);
  CHECK(hit.move == Move(1, 2, Quiet));                           // no new move: the old one stays
  t.table.deposit(key, NoMove, 0, 0, -3, TtBound::Upper, false);  // quiescence depths store as 0
  CHECK(t.table.fetch(key, hit));
}

// Owner, 2026-10-24: a torn write (Phase 6's shared table) must read as a
// miss. Two writes of the same position are spliced at every 4-byte
// boundary, as a reader racing a writer could see them.
TEST_CASE("tt", "an entry mixing the words of two writes is not returned") {
  TestTable t(1);
  const Key key = 0x0123456789abcdefULL;
  TtHit hit{};
  t.table.deposit(key, Move(12, 28, Quiet), 57, -13, 9, TtBound::Lower, false);
  const TtEntry first = t.storage[0].entries[0];
  t.table.deposit(key, Move(6, 21, Quiet), -340, 88, 11, TtBound::Exact, true);
  const TtEntry second = t.storage[0].entries[0];
  CHECK(t.table.fetch(key, hit) && hit.score == -340);
  int spliced = 0;
  for (std::size_t cut : {std::size_t{4}, std::size_t{8}}) {
    for (int order = 0; order < 2; ++order) {
      const TtEntry& head = order ? second : first;
      const TtEntry& tail = order ? first : second;
      TtEntry mixed;
      std::memcpy(&mixed, &head, cut);
      std::memcpy(reinterpret_cast<char*>(&mixed) + cut, reinterpret_cast<const char*>(&tail) + cut,
                  sizeof(TtEntry) - cut);
      t.storage[0].entries[0] = mixed;
      CHECK_MSG(!t.table.fetch(key, hit), "cut " << cut << " order " << order);
      ++spliced;
    }
  }
  CHECK_EQ(spliced, 4);
  t.storage[0].entries[0] = second;  // and the whole entry still reads
  CHECK(t.table.fetch(key, hit) && hit.depth == 11);
}

TEST_CASE("tt", "mate and tablebase scores convert between root and node distance") {
  for (int ply = 0; ply < 40; ++ply) {
    for (int s : {mate_score(ply + 3), mated_score(ply + 2), TbWinScore - ply - 5, -(TbWinScore - ply - 1), 0,
                  137, -EvalLimit}) {
      CHECK_EQ(score_from_tt(score_to_tt(s, ply), ply), s);
    }
    // The stored value is the distance from the node: a mate 3 plies below
    // this node reads the same at any ply.
    CHECK_EQ(score_to_tt(mate_score(ply + 3), ply), mate_score(3));
  }
}

TEST_CASE("tt", "bucket index: 64-bit exact up to the 4 TiB maximum, spread over the table") {
  // 4 TiB of Hash = 2^42 bytes = 2^36 buckets: more than 2^32 (DESIGN.md §5.1 note).
  const std::size_t max_buckets = (std::size_t{1} << 42) / sizeof(TtBucket);
  CHECK_EQ(max_buckets, std::size_t{1} << 36);
  CHECK_EQ(TransTable::bucket_index(0, max_buckets), std::size_t{0});
  CHECK_EQ(TransTable::bucket_index(~Key{0}, max_buckets), max_buckets - 1);
  CHECK_EQ(TransTable::bucket_index(Key{1} << 63, max_buckets), max_buckets / 2);
  // Indexes above 2^32 are reached, and every index is in range, for this and
  // an odd count.
  std::uint64_t seed = 20261024;
  for (std::size_t count : {max_buckets, max_buckets - 7, std::size_t{16384}, std::size_t{3}}) {
    bool above_32_bits = false;
    std::vector<int> quarters(4, 0);
    for (int i = 0; i < 100000; ++i) {
      const std::size_t idx = TransTable::bucket_index(splitmix_next(seed), count);
      CHECK(idx < count);
      above_32_bits |= idx > 0xFFFFFFFFULL;
      ++quarters[idx * 4 / count];
    }
    if (count > (std::size_t{1} << 33)) CHECK(above_32_bits);
    if (count >= 4)
      for (int q : quarters) CHECK_MSG(q > 22000 && q < 28000, "count " << count << " quarter " << q);
  }
}

TEST_CASE("tt", "fill_permille counts the current search's entries in the sample") {
  TestTable t(1000);
  CHECK_EQ(t.table.fill_permille(), 0);
  for (Key k = 0; k < 200; ++k) {
    // One position per sampled bucket: bucket i holds keys near i/1000 of the range.
    const Key key = (~Key{0} / 1000) * k + 12345;
    t.table.deposit(key, NoMove, 0, 0, 1, TtBound::Exact, false);
  }
  CHECK_EQ(t.table.fill_permille(), 200);  // 200 of 1000 sampled entries
  t.table.advance_age();
  CHECK_EQ(t.table.fill_permille(), 0);  // all from an earlier search
}

// Review (Phase 3 deliverable 3, 2026-10-24): the 5-bit age wraps after 32
// searches, so an entry from 32 searches ago reads as one from the current
// search: hashfull counts it, and it blocks a fresh shallower result for
// the same position ("keep a deeper result from this search").
// Review 2026-10-24 found the first layout's 5-bit age wrapping after 32
// searches; the age is now a whole byte (wrap at 256, documented in
// trans_table.hpp): up to 255 searches back, an entry is old.
TEST_CASE("tt", "review: an entry from 1 to 255 searches ago is not from the current search") {
  TestTable t(1000);
  for (Key k = 0; k < 200; ++k)
    t.table.deposit((~Key{0} / 1000) * k + 12345, NoMove, 0, 0, 1, TtBound::Exact, false);
  const Key key = 42;
  t.table.deposit(key, Move(1, 2, Quiet), 10, 0, 20, TtBound::Lower, false);
  for (int i = 0; i < 255; ++i) t.table.advance_age();
  CHECK_MSG(t.table.fill_permille() == 0, "hashfull after 255 searches: " << t.table.fill_permille());
  t.table.deposit(key, Move(3, 4, Quiet), 99, 0, 5, TtBound::Lower, false);
  TtHit hit{};
  CHECK(t.table.fetch(key, hit));
  CHECK_MSG(hit.depth == 5 && hit.score == 99,
            "the stale depth-20 entry kept: depth " << hit.depth << " score " << hit.score);
}

// The blended victim policy (owner's experiment, 2026-10-26): a deep entry
// from the previous search outranks a shallow one from the current search,
// which the default (lexicographic) policy never allows.
TEST_CASE("tt", "victim policy: lexicographic keeps current entries, blended keeps deep stale ones") {
  for (const bool blend : {false, true}) {
    TestTable t(1);  // every key maps to bucket 0
    t.table.set_age_blend(blend);
    for (int i = 0; i < 5; ++i) t.table.deposit(Key(i + 1), NoMove, 0, 0, 20 + i, TtBound::Exact, false);
    t.table.advance_age();
    // Stale depths 20-24; the new entry replaces the shallowest stale one under
    // both policies (blended ranks 18-22).
    t.table.deposit(Key(6), NoMove, 0, 0, 3, TtBound::Exact, false);
    TtHit hit{};
    CHECK(!t.table.fetch(Key(1), hit));
    CHECK(t.table.fetch(Key(6), hit));
    // Now the current depth-3 entry (blended rank 3) against stale depths
    // 21-24 (blended ranks 19-22): which one goes depends on the policy.
    t.table.deposit(Key(7), NoMove, 0, 0, 2, TtBound::Exact, false);
    CHECK(t.table.fetch(Key(7), hit));
    CHECK_MSG(t.table.fetch(Key(6), hit) == !blend, "blend " << blend << ": the current shallow entry");
    CHECK_MSG(t.table.fetch(Key(2), hit) == blend, "blend " << blend << ": the stale depth-21 entry");
  }
}

// Review 2, claim (e), 2026-10-26: within one search, a fail-low (upper
// bound) at the same depth replaced the position's exact entry. With the
// switch on, the exact entry stays.
TEST_CASE("tt", "same depth, same search: a bound replaces an exact entry unless keep-exact is on") {
  for (const bool keep : {false, true}) {
    TestTable t(1024);
    t.table.set_keep_exact(keep);
    const Key key = 0x0123456789abcdefULL;
    t.table.deposit(key, Move(12, 28, Quiet), 40, 0, 10, TtBound::Exact, false);
    t.table.deposit(key, Move(12, 20, Quiet), -15, 0, 10, TtBound::Upper, false);
    TtHit hit{};
    CHECK(t.table.fetch(key, hit));
    CHECK_MSG((hit.bound == TtBound::Exact) == keep,
              "keep " << keep << ": bound " << static_cast<int>(hit.bound));
    // A deeper bound still replaces it, and an exact result always does.
    t.table.deposit(key, NoMove, 5, 0, 11, TtBound::Upper, false);
    CHECK(t.table.fetch(key, hit) && hit.depth == 11);
  }
}

}  // namespace forkeng::test
