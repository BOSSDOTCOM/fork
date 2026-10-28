// SPDX-License-Identifier: GPL-3.0-or-later

// The parameter table (DESIGN.md §5.2, deliverable 8b): every entry is
// well-formed, moving the LMR divisor into the table kept the table exactly,
// and a tuning build's set_param reaches the search.
#include <set>
#include <string>

#include "harness.hpp"
#include "search/lmr_table.hpp"
#include "search/quiet_history.hpp"
#include "tune/params.hpp"

namespace forkeng::test {

TEST_CASE("params", "every default lies in its range, steps fit, names are unique") {
  const ParamTable table = param_table();
  CHECK(!table.empty());
  std::set<std::string> names;
  for (const TuneParam& p : table) {
    const std::string name(p.name);
    CHECK_MSG(names.insert(name).second, "duplicate " << name);
    CHECK_MSG(p.lowest <= p.default_value && p.default_value <= p.highest, name);
    CHECK_MSG(p.step >= 1 && p.step <= p.highest - p.lowest, name);
    CHECK_MSG(find_param(p.name) == &p, name);
  }
  CHECK(find_param("NoSuchParameter") == nullptr);
  CHECK(find_param("RfpMargin") != nullptr);
  // A tuned bonus cap must stay within the history scale (int16 headroom).
  CHECK(find_param("HistoryBonusCap")->highest <= HistoryMax);
}

// Deliverable 8b moved the divisor 4.5 into the table as 45 tenths: the
// table must equal the one built with the earlier constants,
// (L + 147456) / 294912, entry by entry.
TEST_CASE("params", "the LMR table at 45 tenths equals the earlier formula") {
  const LmrTable table = make_lmr_table(45);
  for (int d = 1; d < LmrMaxDepth; ++d)
    for (int m = 1; m < LmrMaxMove; ++m) {
      const int earlier =
          (fixed_log2(static_cast<std::uint32_t>(d)) * fixed_log2(static_cast<std::uint32_t>(m)) + 147456) /
          294912;
      CHECK_MSG(table.plies[d][m] == earlier, "d " << d << " m " << m);
    }
}

#ifdef FORK_TUNE
// Tuning builds: a value set by name reaches the search (the derived LMR
// table is rebuilt), is clamped to its range, and the defaults come back.
TEST_CASE("params", "tuning build: set_param changes, clamps and rebuilds") {
  const int before = reduction_for(20, 30);
  CHECK(set_param("LmrDivisorTenths", 30));
  CHECK_EQ(LmrDivisorTenths, 30);
  CHECK(reduction_for(20, 30) > before);
  CHECK(set_param("RfpMargin", 100000));
  CHECK_EQ(RfpMargin, find_param("RfpMargin")->highest);
  CHECK(set_param("HistoryBonusFactor", 0));
  CHECK_EQ(HistoryBonusFactor, find_param("HistoryBonusFactor")->lowest);
  CHECK(!set_param("NoSuchParameter", 1));
  for (const TuneParam& p : param_table()) CHECK(set_param(p.name, p.default_value));
  CHECK_EQ(reduction_for(20, 30), before);
  CHECK_EQ(RfpMargin, 40);
}
#endif

}  // namespace forkeng::test
