// SPDX-License-Identifier: GPL-3.0-or-later

// stats_report: the stats build's counter output (DESIGN.md §5.2 debug
// counters; §5.7, Phase 4 step 1 measurements).
//
// Purpose: print a stats build's SearchCounters (and the network's update
// counts) in two forms: the human `stats:` lines of `fork bench`, and a
// machine-read dump after each search for tools/measure/.
// Invariants:
// - Both functions do nothing in a build without FORK_SEARCH_STATS: normal
//   builds have no counters.
// - The summary's earlier lines keep their exact text (tools/evolve/
//   proxies.py and tools/singular_measure.py parse them); new lines are
//   only appended.
// - The dump is cumulative (one line `search_counters name=value ...` with
//   every scalar counter of FORK_SEARCH_COUNTERS and every tally field, then
//   one `search_hist <name> <bins...>` line per histogram); the reader takes
//   differences between searches. Integers only, no allocation.
#pragma once

#include <cstdio>

#include "search/searcher.hpp"

namespace forkeng {

struct FeatureStackTally;  // eval/nnue/accumulator.hpp (network builds)

// The `stats:` lines of `fork bench`; `tally` may be null (no network).
void print_counter_summary(const SearchCounters& c, const FeatureStackTally* tally, std::FILE* out);

// The per-search dump (FORK_STATS_REPORT); `tally` may be null.
void print_counter_dump(const SearchCounters& c, const FeatureStackTally* tally, std::FILE* out);

}  // namespace forkeng
