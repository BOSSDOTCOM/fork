// params: the parameter table (DESIGN.md §1 and §5.2, deliverable 8b).
//
// Purpose: every tunable numeric search parameter in one place, with its
// default, its range and its SPSA step. Release and TCEC builds compile the
// defaults in as constants, the same code as constants written in place, so
// bench does not change. Tuning builds (CMake FORK_TUNE) make each one a
// variable that the UCI session declares as a spin option, beside the
// technique switches.
// Invariants:
// - Each default lies in [lowest, highest], and 1 <= step <= highest - lowest
//   (tests/test_params.cpp).
// - The defaults are justified in DESIGN.md §5.2 ("Search constants"); the
//   ranges and steps follow the rule recorded there (they bound a tuner, they
//   are never played as such).
// - A tuning build changes a value only through set_param, between searches
//   (UCI setoption); nothing writes them during a search.
// - Constants that are not tuned stay where they are, each with its reason in
//   DESIGN.md §5.2: the stop-poll interval, the fail-report delay, the
//   near-draw table score, the history scale, the move-ordering scores and
//   the movetime floor (an owner's rule).
#pragma once

#include <span>
#include <string_view>

// X(name, default, lowest, highest, step), in groups: aspiration and the
// iteration rule; reverse futility and the null move; endgame tables; late
// move reductions and pruning; futility and SEE pruning; history; the TT
// victim policy; the time budget.
#define FORK_SEARCH_PARAMS(X)             \
  X(AspirationMinDepth, 5, 2, 10, 1)      \
  X(AspirationHalfWidth, 12, 6, 24, 1)    \
  X(IterationGrowthThirds, 5, 3, 10, 1)   \
  X(ForcedMoveFraction, 8, 4, 16, 1)      \
  X(RfpMaxDepth, 6, 3, 12, 1)             \
  X(RfpMargin, 80, 40, 160, 6)            \
  X(NullMinDepth, 3, 1, 6, 1)             \
  X(NullSurplusPerPly, 300, 150, 600, 23) \
  X(NullSurplusPliesMax, 2, 0, 4, 1)      \
  X(TableProbeMinDepth, 1, 1, 4, 1)       \
  X(LmrMinDepth, 3, 1, 6, 1)              \
  X(LmrMinMove, 4, 2, 8, 1)               \
  X(LmrDivisorTenths, 45, 23, 90, 3)      \
  X(LmrCorrectionStrength, 64, 0, 128, 6) \
  X(LmpMaxDepth, 4, 2, 8, 1)              \
  X(LmpQuietAllowance, 12, 6, 24, 1)      \
  X(FutilityMaxDepth, 6, 3, 12, 1)        \
  X(FutilityOffset, 100, 50, 200, 8)      \
  X(FutilityGrowth, 70, 35, 140, 5)       \
  X(SeePruneMaxDepth, 6, 3, 12, 1)        \
  X(QuietSeeFloor, 60, 30, 120, 5)        \
  X(CaptureSeeFloor, 100, 50, 200, 8)     \
  X(HistoryBonusFactor, 25, 12, 50, 2)    \
  X(HistoryBonusCap, 1250, 625, 2500, 94) \
  X(StaleDepthPerSearch, 2, 1, 4, 1)      \
  X(AssumedMovesLeft, 30, 15, 60, 2)      \
  X(MaxMovesToGo, 40, 20, 80, 3)          \
  X(HardOverSoft, 4, 2, 8, 1)             \
  X(ReserveDivisor, 10, 5, 20, 1)         \
  X(DangerZoneOverheads, 2, 1, 4, 1)

// Functions that read a parameter are constexpr only where the parameter is
// (inline either way: they are defined in headers).
#ifdef FORK_TUNE
#define FORK_TUNABLE_CONSTEXPR inline
#define FORK_PARAM_DECLARE(name, value, lowest, highest, step) inline int name = value;
#else
#define FORK_TUNABLE_CONSTEXPR constexpr
#define FORK_PARAM_DECLARE(name, value, lowest, highest, step) inline constexpr int name = value;
#endif

namespace forkeng {

FORK_SEARCH_PARAMS(FORK_PARAM_DECLARE)

struct TuneParam {
  std::string_view name;
  int default_value;
  int lowest;
  int highest;
  int step;
};

using ParamTable = std::span<const TuneParam>;

// Every parameter, in the order of FORK_SEARCH_PARAMS.
ParamTable param_table();

// The entry named `name`, or nullptr.
const TuneParam* find_param(std::string_view name);

#ifdef FORK_TUNE
// Tuning builds: sets the parameter (clamped to its range) and rebuilds what
// is derived from the parameters (the LMR table). False for an unknown name.
bool set_param(std::string_view name, int value);
#endif

}  // namespace forkeng

#undef FORK_PARAM_DECLARE
