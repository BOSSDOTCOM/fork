#include "tune/params.hpp"

#include <algorithm>
#include <array>

#ifdef FORK_TUNE
#include "search/lmr_table.hpp"
#endif

namespace forkeng {

namespace {

#define FORK_PARAM_ENTRY(name, value, lowest, highest, step) TuneParam{#name, value, lowest, highest, step},
constexpr std::array Entries{FORK_SEARCH_PARAMS(FORK_PARAM_ENTRY)};
#undef FORK_PARAM_ENTRY

}  // namespace

ParamTable param_table() { return Entries; }

const TuneParam* find_param(std::string_view name) {
  const auto it =
      std::find_if(Entries.begin(), Entries.end(), [&](const TuneParam& p) { return p.name == name; });
  return it == Entries.end() ? nullptr : &*it;
}

#ifdef FORK_TUNE
bool set_param(std::string_view name, int value) {
  const TuneParam* p = find_param(name);
  if (!p) return false;
  const int v = std::clamp(value, p->lowest, p->highest);
#define FORK_PARAM_ASSIGN(param, dflt, lowest, highest, step) \
  if (name == #param) param = v;
  FORK_SEARCH_PARAMS(FORK_PARAM_ASSIGN)
#undef FORK_PARAM_ASSIGN
  rebuild_lmr_table();
  return true;
}
#endif

}  // namespace forkeng
