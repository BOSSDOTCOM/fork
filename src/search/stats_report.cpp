// SPDX-License-Identifier: GPL-3.0-or-later

#include "search/stats_report.hpp"

#if defined(FORK_EVAL_NNUE)
#include "eval/nnue/accumulator.hpp"
#endif

namespace forkeng {

#ifdef FORK_SEARCH_STATS

void print_counter_summary(const SearchCounters& c, const FeatureStackTally* tally, std::FILE* out) {
  // The earlier lines, unchanged (moved here from search_bench.cpp).
  std::fprintf(
      out, "stats: %llu beta cutoffs, %.1f%% on the first move, mean cutoff index %.4f\n",
      static_cast<unsigned long long>(c.beta_cutoffs),
      c.beta_cutoffs ? 100.0 * static_cast<double>(c.first_move_cutoffs) / static_cast<double>(c.beta_cutoffs)
                     : 0.0,
      c.beta_cutoffs ? static_cast<double>(c.cutoff_index_sum) / static_cast<double>(c.beta_cutoffs) : 0.0);
  std::fprintf(out, "stats: %llu makes\n", static_cast<unsigned long long>(c.makes));
  std::fprintf(out, "stats: cuts rfp %llu null %llu; prunes lmp %llu futility %llu see %llu\n",
               static_cast<unsigned long long>(c.rfp_cuts), static_cast<unsigned long long>(c.null_cuts),
               static_cast<unsigned long long>(c.lmp_prunes),
               static_cast<unsigned long long>(c.futility_prunes),
               static_cast<unsigned long long>(c.see_prunes));
  std::fprintf(
      out, "stats: %llu reduced searches, %llu re-searched at full depth (%.1f%%)\n",
      static_cast<unsigned long long>(c.lmr_searches), static_cast<unsigned long long>(c.lmr_researches),
      c.lmr_searches ? 100.0 * static_cast<double>(c.lmr_researches) / static_cast<double>(c.lmr_searches)
                     : 0.0);
  std::fprintf(
      out, "stats: mean reduction %.3f plies\n",
      c.lmr_searches ? static_cast<double>(c.lmr_plies_sum) / static_cast<double>(c.lmr_searches) : 0.0);
  std::fprintf(out, "stats: LMR rule ran at %llu sites, fired at %llu, changed the reduction at %llu\n",
               static_cast<unsigned long long>(c.lmr_rule_sites),
               static_cast<unsigned long long>(c.lmr_rule_fires),
               static_cast<unsigned long long>(c.lmr_rule_changes));
  std::fprintf(out,
               "stats: SEE pruning: good captures %llu (skipped), tested: bad captures %llu, quiets %llu, "
               "other %llu\n",
               static_cast<unsigned long long>(c.see_tests_good_captures),
               static_cast<unsigned long long>(c.see_tests_bad_captures),
               static_cast<unsigned long long>(c.see_tests_quiets),
               static_cast<unsigned long long>(c.see_tests_other));
  std::fprintf(out, "stats: bad captures after LMP stopped quiets %llu, of them SEE-pruned %llu\n",
               static_cast<unsigned long long>(c.bad_captures_after_stop),
               static_cast<unsigned long long>(c.bad_captures_after_stop_pruned));
  std::fprintf(out, "stats: futile nodes %llu, quiets taken there %llu, searched %llu\n",
               static_cast<unsigned long long>(c.futile_nodes),
               static_cast<unsigned long long>(c.futile_quiets_taken),
               static_cast<unsigned long long>(c.futile_quiets_searched));
  std::fprintf(out, "stats: quiescence nodes PV %llu, non-PV %llu\n",
               static_cast<unsigned long long>(c.quiesce_nodes_pv),
               static_cast<unsigned long long>(c.quiesce_nodes_non_pv));
  std::fprintf(out, "stats: multi-cut cuts %llu, negative extensions %llu\n",
               static_cast<unsigned long long>(c.multi_cut_cuts),
               static_cast<unsigned long long>(c.negative_extensions));
  std::fprintf(out, "stats: nodes reduced for having no TT move %llu\n",
               static_cast<unsigned long long>(c.no_move_reductions));
  std::fprintf(out, "stats: singular tests %llu, TT move singular %llu (%.1f%%)\n",
               static_cast<unsigned long long>(c.singular_tests),
               static_cast<unsigned long long>(c.singular_extended),
               c.singular_tests
                   ? 100.0 * static_cast<double>(c.singular_extended) / static_cast<double>(c.singular_tests)
                   : 0.0);
  for (int d = 1; d < SearchCounters::CutoffDepths; ++d) {
    std::fprintf(out, "stats: quiet cutoffs at depth %d by quiet index:", d);
    for (int i = 0; i < SearchCounters::CutoffIndices; ++i)
      std::fprintf(out, " %llu", static_cast<unsigned long long>(c.quiet_cutoff_index[d][i]));
    std::fprintf(out, "\n");
  }

  // Phase 4 step 1, X1 (DESIGN.md §5.7): appended lines.
  const auto ratio = [](std::uint64_t a, std::uint64_t b) {
    return b ? static_cast<double>(a) / static_cast<double>(b) : 0.0;
  };
  const std::uint64_t quiesce_nodes = c.quiesce_nodes_pv + c.quiesce_nodes_non_pv;
  const std::uint64_t nodes = c.root_nodes + c.main_nodes + quiesce_nodes;
  const std::uint64_t evals = c.evals_main + c.evals_quiesce + c.evals_horizon;
  std::fprintf(
      out,
      "stats: nodes %llu (root %llu, main %llu, quiescence %llu); evaluations per node %.4f (main %.4f, "
      "quiescence %.4f, horizon %llu)\n",
      static_cast<unsigned long long>(nodes), static_cast<unsigned long long>(c.root_nodes),
      static_cast<unsigned long long>(c.main_nodes), static_cast<unsigned long long>(quiesce_nodes),
      ratio(evals, nodes), ratio(c.evals_main, nodes), ratio(c.evals_quiesce, nodes),
      static_cast<unsigned long long>(c.evals_horizon));
  std::fprintf(out,
               "stats: TT-eval hits main %.1f%% (%llu), quiescence %.1f%% (%llu); in check main %llu, "
               "quiescence %llu\n",
               100.0 * ratio(c.tt_eval_hits_main, c.tt_eval_hits_main + c.evals_main),
               static_cast<unsigned long long>(c.tt_eval_hits_main),
               100.0 * ratio(c.tt_eval_hits_quiesce, c.tt_eval_hits_quiesce + c.evals_quiesce),
               static_cast<unsigned long long>(c.tt_eval_hits_quiesce),
               static_cast<unsigned long long>(c.check_nodes_main),
               static_cast<unsigned long long>(c.check_nodes_quiesce));
  std::fprintf(out, "stats: quiescence share of nodes %.1f%%, of evaluations %.1f%%\n",
               100.0 * ratio(quiesce_nodes, nodes), 100.0 * ratio(c.evals_quiesce, evals));
  std::fprintf(out, "stats: pawn moves %.1f%% of makes (%llu), in the quiescence search %llu\n",
               100.0 * ratio(c.pawn_makes, c.makes), static_cast<unsigned long long>(c.pawn_makes),
               static_cast<unsigned long long>(c.pawn_makes_quiesce));
#if defined(FORK_EVAL_NNUE)
  if (tally) {
    const FeatureStackTally& t = *tally;
    std::fprintf(
        out,
        "stats: network evaluations %llu, perspective updates %llu, rows per update %.3f, refreshes "
        "per 1,000 updates %.3f (root %llu, frame %llu), plies walked per evaluation %.3f, link-update "
        "share %.1f%%, pushes %llu (null %llu)\n",
        static_cast<unsigned long long>(t.evaluations),
        static_cast<unsigned long long>(t.perspective_updates), ratio(t.update_rows, t.perspective_updates),
        1000.0 * ratio(t.frame_refreshes + t.root_refreshes, t.perspective_updates),
        static_cast<unsigned long long>(t.root_refreshes), static_cast<unsigned long long>(t.frame_refreshes),
        ratio(t.walked_plies, t.evaluations), 100.0 * ratio(t.link_updates, t.perspective_updates),
        static_cast<unsigned long long>(t.move_pushes), static_cast<unsigned long long>(t.null_pushes));
  }
#else
  (void)tally;
#endif
  // X2 (DESIGN.md §5.7): where the LMR history term (|ordering score| >=
  // LmrHistoryProbeDivisor) would act, and the histograms.
  std::fprintf(
      out,
      "stats: LMR history term would act at %.2f%% of LMR sites (reduce less %llu, more %llu), change "
      "the reduction at %llu; sites without a reply arrival %llu, without a follow arrival %llu; late "
      "captures %llu\n",
      100.0 * ratio(c.lmr_history_fire_less + c.lmr_history_fire_more, c.lmr_rule_sites),
      static_cast<unsigned long long>(c.lmr_history_fire_less),
      static_cast<unsigned long long>(c.lmr_history_fire_more),
      static_cast<unsigned long long>(c.lmr_history_changes),
      static_cast<unsigned long long>(c.lmr_reply_absent),
      static_cast<unsigned long long>(c.lmr_follow_absent),
      static_cast<unsigned long long>(c.late_capture_sites));
  const auto bins_line = [&](const char* name, const std::uint64_t* bins, int count) {
    std::fprintf(out, "stats: %s bins:", name);
    for (int i = 0; i < count; ++i) std::fprintf(out, " %llu", static_cast<unsigned long long>(bins[i]));
    std::fprintf(out, "\n");
  };
  bins_line("LMR ordering score", c.lmr_order_bins, OrderBins);
  bins_line("LMR quiet history", c.lmr_quiet_bins, TableBins);
  bins_line("LMR reply history", c.lmr_reply_bins, TableBins);
  bins_line("LMR follow history", c.lmr_follow_bins, TableBins);
  bins_line("late capture take history", c.late_take_bins, TableBins);
}

void print_counter_dump(const SearchCounters& c, const FeatureStackTally* tally, std::FILE* out) {
  std::fprintf(out, "search_counters");
#define FORK_COUNTER_MEMBER(member) \
  std::fprintf(out, " " #member "=%llu", static_cast<unsigned long long>(c.member));
  FORK_SEARCH_COUNTERS(FORK_COUNTER_MEMBER)
#undef FORK_COUNTER_MEMBER
#if defined(FORK_EVAL_NNUE)
  if (tally) {
    const FeatureStackTally& t = *tally;
    std::fprintf(
        out,
        " evaluations=%llu move_pushes=%llu null_pushes=%llu perspective_updates=%llu update_rows=%llu "
        "link_updates=%llu frame_refreshes=%llu root_refreshes=%llu walked_plies=%llu",
        static_cast<unsigned long long>(t.evaluations), static_cast<unsigned long long>(t.move_pushes),
        static_cast<unsigned long long>(t.null_pushes),
        static_cast<unsigned long long>(t.perspective_updates),
        static_cast<unsigned long long>(t.update_rows), static_cast<unsigned long long>(t.link_updates),
        static_cast<unsigned long long>(t.frame_refreshes), static_cast<unsigned long long>(t.root_refreshes),
        static_cast<unsigned long long>(t.walked_plies));
  }
#else
  (void)tally;
#endif
  std::fprintf(out, "\n");
  // The histograms (X2), one line each: `search_hist NAME bins...`.
  const auto hist_line = [&](const char* name, const std::uint64_t* bins, int count) {
    std::fprintf(out, "search_hist %s", name);
    for (int i = 0; i < count; ++i) std::fprintf(out, " %llu", static_cast<unsigned long long>(bins[i]));
    std::fprintf(out, "\n");
  };
  hist_line("lmr_order", c.lmr_order_bins, OrderBins);
  hist_line("lmr_quiet", c.lmr_quiet_bins, TableBins);
  hist_line("lmr_reply", c.lmr_reply_bins, TableBins);
  hist_line("lmr_follow", c.lmr_follow_bins, TableBins);
  hist_line("late_take", c.late_take_bins, TableBins);
}

#else

void print_counter_summary(const SearchCounters&, const FeatureStackTally*, std::FILE*) {}
void print_counter_dump(const SearchCounters&, const FeatureStackTally*, std::FILE*) {}

#endif

}  // namespace forkeng
