#!/usr/bin/env bash
[ -f /c/Users/user/fork-jobs/night/state/gate-e1.done ] || { echo "$(TZ=EST5 date "+%Y-%m-%d %I:%M %p EST") gated: waits for state/gate-e1.done (owner 2026-11-11: E1 fix and its SPRT before new additions)"; exit 20; }
export FORK_GH_JOBS=${FORK_GH_JOBS:-40}  # GitHub Pro since 2026-11-10 9:20 PM EST (owner): 40 concurrent jobs
# The engine survey's F11, the root lean (optimism; ideas.md idea 143), at its natural values (RootLeanThreshold
# 100, RootLeanCap 400, RootLeanScale 4000, 3 iterations; owner, 2026-11-12: builder 3's design approved, LTC-first;
# a z-item, after lane A's STC-only items). Item z70b is the retry. Design R at 40+0.4 ([0, 6] nElo, beta 0.20;
# survey-hist.sh direct, ltc) of the switch-on commit sprt/f11-root-lean e2b42d5 (bench 9,613,389 /
# a5c9207fab1d17d6) against the switch-off commit tier2/f11-root-lean 0a49342 (phase-4 32384e1's engine with it
# built in, off; bench 9,639,207 / 07f7ae19b9250f38, r8brft1), from stage 0; resumes at the first stage without a
# recorded run. Ledger idea f11-root-lean at LTC, try 1. The switch stays off in data generation's labeller whatever
