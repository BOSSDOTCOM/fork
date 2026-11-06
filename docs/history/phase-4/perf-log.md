# Phase 4 performance log

Speed changes to the default engine that keep bench identical (nodes and
signature): no SPRT, each verified by `bench/ab_search.py` (interleaved, core
4, identity-checked, `--same-nodes`) on a quiet machine; a change counts only
if both estimators move the same way by more than 3% or twice the
round-to-round spread (the harness's rule), and is kept only then (owner,
2026-11-06). WSL Ubuntu, clang 21.1.8, Release, `-march=native`, Ryzen 7
7600X3D.

## The speed sprint of 2026-11-06 (owner)

**Profile** (the default engine, S512r2 with IIR, phase-4 at 684bac6; perf
cpu-clock at 4 kHz over 64 UHO positions, every 4,000th line of
`UHO_Lichess_4852_v1.epd`, `go movetime 250` each after `ucinewgame`, Hash
16, 1 thread; self time by source function as `llvm-addr2line -f` names
the sampled address, so inlined code is counted under the inlined function
(`TtEntry::bound`, for example, is the inlined read of a TT entry, not a
call; corrected 2026-11-06); shares of Fork's samples):

| area | share | largest functions |
|---|---|---|
| network | 41.5% | `advance_values` 17.2 (the accumulator update), `squared_sum` 14.5 (the output layer), `sum_perspective` 2.5 (refreshes), `evaluate_with` 1.9, `column` 1.7 |
| move ordering | 14.7% | `MoveSelector::select_best` 5.9, `see_at_least` 3.1, `take_next` 2.8, `score_quiets` 1.8, `score_captures` 0.9 |
| TT | 12.7% | `TtEntry::bound` 8.3 (the first read of the bucket: the stall), `predicted_key` 1.6, `deposit` 1.0, `splitmix_finalize` 0.8 |
| move generation | 10.8% | `SliderEntry::table_index` 2.4 (PEXT), `fill_moves` 2.4, `add_piece_moves` 1.8, `attackers_to` 1.7 |
| search | 5.7% | `negamax` 3.6, `quiesce` 1.2 |
| make/unmake | 2.0% | `make` 0.7, `toggle_keys` 0.6 |
| other | 12.6% | spread thin (largest 0.7) |

Two of the owner's candidates were already in place: lazy accumulator updates
(FeatureStack computes a ply's sums only when its evaluation is needed) and
the TT bucket prefetched at make-move (`predicted_key`, review 2), on a table
with transparent huge pages (`madvise`).

**Candidates**, each behind a build flag in one tree (perf/sprint), every
bench 14180299 / 4cf778ff753861f7; 10 interleaved rounds each against the
same base:

| candidate | median | best | verdict |
|---|---|---|---|
| C1: the output layer on AVX-512 (VNNI's `dpwssd` where compiled), four independent sums | not measured | | **parked** (owner): the SPRT shards build x86-64-v3 only, so the path would never run there; to be revisited for TCEC's x86-64-v4 builds. AVX2 stays the default path. Its code is kept on archive/sprint-candidates. |
| C2: the delta's feature rows prefetched at make-move, all 16 lines | −2.9% | −2.7% | no significant difference: not kept |
| C2, 4 lines per row | −1.4% | −1.1% | no significant difference: not kept |
| C3: the child's TT bucket prefetched before the pruning tests (not after them) | −0.8% | −0.9% | no significant difference: not kept |
| **C4: `select_best` keeping the best score in a register** (the same first maximum, so the same order) | **+4.0%** | **+3.3%** | **faster: kept** |
| C2 (4 lines) + C3 together (owner: every candidate below the threshold, combined) | −2.0% | | no significant difference: not kept |

C4's loop compared each score with the score at the best index, a load that
depended on the previous iteration's choice; keeping the best score in a
register leaves only the compare and two moves per element. Ties keep the
first maximum, so the order of moves, and bench, are unchanged.

**Cumulative speedup of the kept changes: +4.0% median, +3.3% best (C4
alone).**

### Round 2 (2026-11-06, the owner's "new candidates from the profile")

On phase-4 with C4 (9f368d6) as the base, each behind a build flag on
archive/sprint-candidates-2, every bench 14180299 / 4cf778ff753861f7; a
debug build with all three passed the consistency, search, ordering,
pruning and nnue suites (its every incremental accumulator checked against
a refresh); 10 interleaved rounds each on a quiet machine (g3e and the
SPRT driver suspended):

| candidate | median | verdict |
|---|---|---|
| E1: a per-thread slot per perspective and file flip holding that frame's last sums and their pieces, so a frame change (the king across the d/e line) applies only the pieces that differ instead of summing every piece (the refresh-cache concept publicly described for NNUE engines, "Finny tables") | −5.3% | **slower**: not kept |
| E2: `select_best`'s scan on AVX2 (the largest score 16 at a time, then the first index holding it: the same first maximum) for lists of 16 or more | +1.0% | no significant difference: not kept |
| E4: both perspectives advanced in one pass when both need the same plies | −0.6% | no significant difference: not kept |
| E2 + E4 together (owner: every candidate below the threshold, combined) | −0.2% (noise threshold 5.1% in that run) | no significant difference: not kept |

Round 2 keeps nothing; **the cumulative speedup stays +4.0% (C4)**. E1's
loss likely comes from copying 1 KB per slot at every frame change and the
larger FeatureStack, against refreshes that were only 2.5% of the time
(UNVERIFIED, not profiled).
