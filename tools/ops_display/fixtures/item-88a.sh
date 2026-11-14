#!/usr/bin/env bash
[ -f /c/Users/user/fork-jobs/night/state/gate-e1.done ] || { echo "$(TZ=EST5 date "+%Y-%m-%d %I:%M %p EST") gated: waits for state/gate-e1.done (owner 2026-11-11: E1 fix and its SPRT before new additions)"; exit 20; }
export FORK_GH_JOBS=${FORK_GH_JOBS:-40}  # GitHub Pro since 2026-11-10 9:20 PM EST (owner): 40 concurrent jobs
# Idea 59's follow-up 1 / idea 78, variant DS (owner, 2026-11-12 2:05 PM EST: the depth-scaled, and window-gated,
# variant of minor@32 + pieces@32, shares summing to 64, tested against the minor@32 head; the offline gate a safety
# check only, the SPRT decides adoption): the pieces table at PieceDriftShare 32 on top of the adopted minor table at
# 32, the sum scaled by depth (UseDriftDepthScale). No constant to choose (no retry item). Design R at STC ([0, 6]
# nElo, beta 0.20, cap 8, futility look after 2 stages) of the switch-on commit sprt/i59-ds 8ccbb69 (bench 9,964,398
# / 096eb8cbc6356538) against the switch-off commit tier2/corr-i59 9fb17c0 (phase-4 016d952's engine with the depth
# scale and window gate built in, off; bench 9,118,607 / 208629aa15e140a9, phase-4's), from stage 0; resumes at the
# first stage without a recorded run. Offline gate passed (-0.06 cp [-1.27, +1.28] against the head, <= 0.013% of
# visits at the limit). Ledger idea i59-corr-ds, try 1. Nothing is merged: the result goes to the owner. See
