#!/usr/bin/env bash
# Owner's order 2026-11-14 ~12:30 PM EST: 'screen 8c's control (both seeds) vs r8brft1 immediately, using both lanes, ahead
# of other items'. r8cc1 against r8brft1 (b49d6f5: the engine the 8c bakes share, default r8brft1), 1,600 games at 800,000 nodes
# per move, stage 0's openings; commits from fork-data/8c/a1-state/bakes.txt. Same format as 15-r8c-*.
export W=C:/Users/user/fork-runners/wt-b4-ru2  # lane A runner worktree
export STATE=C:/Users/user/fork-data/8c/a1-state
exec bash C:/Users/user/fork-data/8c/r8c_screen.sh r8cc1 r8brft1 0
