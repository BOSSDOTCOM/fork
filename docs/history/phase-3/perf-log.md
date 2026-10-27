# Phase 3 performance gate log

The gate of DESIGN.md §5.2, Quality control 2, after every deliverable:
search nps and bench nodes against the previous deliverable
(`bench/ab_search.py`, 6 interleaved rounds, pinned to core 4), and one
`perf` profile of `fork bench` with the top functions by self time. Run with
`tools/perf_gate.sh NEW [OLD]` in WSL (Ubuntu, clang 21.1.8, Release,
`-march=native`, Ryzen 7 7600X3D; the machine is shared, so only the
interleaved harness counts). Inlined code counts for the function it was
inlined into.

**Noise floor** (A/A run of deliverable 2 against a copy of itself,
2026-10-24): medians -0.4%, best runs -1.1%, so the harness's minimum
threshold of 3% applies. A change of search nps beyond 3% in both
estimators needs a stated reason or a fix.

## Deliverable 2: core search (ad4b848)

- Bench 24,919,232 nodes, signature 2c0623965a6bf2be (depth 6, 46
  positions). Search nps about 12.0 M (median of 6 runs, 11,978,692).
  First deliverable with a search: no earlier search to compare with.
- Profile (self time): `Searcher::negamax<false>` 21.2%,
  `generate<Legal>` 20.6%, bootstrap eval `side_score` 16.0% plus
  `bootstrap_eval` 6.3%, `Position::refresh_check_info` 14.2%,
  `Position::make` 10.0%, `Searcher::order_moves` 6.2%, `Position::unmake`
  3.5%, `Position::insufficient_material` 1.3%.
- Verdict: nothing out of place for a full-width search that evaluates
  every leaf. Note: interior nodes also compute a static evaluation that
  nothing reads until deliverable 6's pruning uses it; it is kept because
  the pruning needs it there.

## Deliverable 3: transposition table (0d32d51, against ad4b848)

- Bench 7,773,794 nodes (was 24,919,232 at the same depth 6), signature
  e86cc3c139e88831.
- nps: median 11,786,980 -> 11,036,343 (-6.4%), best 11,983,227 ->
  11,199,725 (-6.5%): **slower, beyond the 3% floor. Reason: a deliberate
  trade.** The TT costs work at every node (fetch, deposit, the child's
  bucket prefetch through `predicted_key`), and its cutoffs remove whole
  subtrees, so the nodes that remain are the more expensive ones. Bench
  time to the same depth: 24.9 M / 12.0 M nps = 2.08 s before, 7.77 M /
  11.0 M nps = 0.70 s now, about 3 times faster.
- Profile: `negamax<false>` 29.3%, `generate<Legal>` 14.8%, eval 17.1%
  (`side_score` 12.1, `bootstrap_eval` 5.0), `refresh_check_info` 11.9%,
  `order_moves` 6.6%, `make` 5.4%, `predicted_key` 4.2% (the prefetch),
  `insufficient_material` 3.3%, `unmake` 3.2%, `TransTable::deposit` 1.1%,
  `fetch` 1.0%.
- To measure later, not now (no premature micro-optimization): whether the
  prefetch pays for its `predicted_key` call, with the A/B harness.

## Deliverable 4: quiescence search and SEE (8d6b283, against 0d32d51)

- Bench 7,541,768 nodes, signature 04b78e8a995bb470 (depth 6).
- nps: median 11,668,129 -> 9,294,019 (-20.3%), best 11,908,261 ->
  9,428,906 (-20.8%): **slower, beyond the 3% floor. Reason: a deliberate
  trade.** The horizon now runs a capture search instead of one static
  evaluation, and every capture there is judged by SEE before it is
  ordered; the qsearch's strength is measured by its SPRT (Milestone A).
- Profile: `negamax<false>` 13.1%, `quiesce<false>` 10.7%,
  `refresh_check_info` 10.6%, eval 12.6% (`side_score` 10.0,
  `bootstrap_eval` 2.6), `generate<Legal>` 9.1%, `see_value` 8.1%,
  `generate<Captures>` 6.9%, `make` 5.3%, `order_moves` 5.1%, `unmake`
  4.3%, `predicted_key` 4.1%, `TransTable::fetch` 3.5%, `deposit` 2.9%,
  `insufficient_material` 1.5%.
- No hotspot out of place. Candidates for later, each only with a measured
  gain: SEE only for the captures the staged selector (deliverable 5)
  actually reaches, instead of all of them before ordering; null windows
  for later moves in PV quiescence nodes (the deliverable 4 reviewer
  measured a twelve-queen position at 19 M nodes for depth 1 with full
  windows, 4.2 M with null windows; random-game positions stay under 80 k);
  `piece_value` as an inline constant table.

## Milestone A originality fixes (bea68ed, against 2beb9e3)

- Bench 7,533,640 nodes, signature 2711c23a13969520 (TT replacement and root
  order changed; the self-verifying check and the `OnPv` rename did not
  change it).
- nps: median 9,731,198 -> 9,602,978 (-1.3%), best 9,813,713 -> 9,710,365
  (-1.1%): no significant difference (3% floor).
- Profile: `TransTable::deposit` 5.8% (was 2.9%: the data digest of the
  self-verifying check and the two-pass slot choice), `fetch` 3.8% (was
  3.5%); the rest as before (`negamax<false>` 12.0%, eval 13.3%,
  `generate<Legal>` 10.2%, `refresh_check_info` 10.1%, `quiesce<false>`
  9.4%, `generate<Captures>` 7.3%, `see_value` 7.0%).

## Deliverable 5: staged move selector and history (4fac691, against f736dc7)

- Bench 4,962,467 nodes (was 7,533,640 at the same depth 6), signature
  4c45aa80f71dfd99: better ordering searches a third fewer nodes.
- nps: two A/B runs, both disturbed by load outside WSL (the owner's
  browser; WSL idle): run 1 median -1.2%, best +3.4%, noise threshold
  15.1%; run 2 median -36.8% (disturbed rounds), best -1.7%, threshold
  69.1%. Both verdicts "no significant difference"; the best-run estimates,
  the most load-robust, show no slowdown. To re-measure on a quiet machine
  if a later gate needs this baseline.
- Profile: `MoveSelector::take_next` 16.2% (move picking, now including
  the selection sort that `order_moves`/`pick_next` did inside the
  searcher), `refresh_check_info` 10.9%, `generate<Captures>` 10.4%,
  eval 11.8% (`side_score` 9.7, `bootstrap_eval` 2.1), `quiesce<false>`
  9.3%, `negamax<false>` 8.1%, `see_value` 6.5%, `make` 4.8%, `unmake`
  4.2%, `predicted_key` 4.1%, TT 6.5%, `generate<Quiets>` 2.8% (quiets
  are generated only when reached).
- Ordering counters (FORK_SEARCH_STATS): 96.7% of cutoffs on the first
  move, mean cutoff index 0.08.

## Deliverable 6: tier 1 pruning and reductions (40fdf8f, against 4fac691)

- Bench depth 6 -> 13: 10,351,634 nodes, signature 96fed387a8512132.
- nps: median 9,775,786 -> 5,702,060 (-41.7%), best -41.7%, noise
  threshold 3.0% (a quiet run). A trade, not a regression: a pruned move
  costs its selection, SEE and gives_check but is not a node (nodes count
  negamax and quiescence entries). FORK_SEARCH_STATS bench: 8.14M
  futility prunes, 1.37M SEE prunes and 0.32M LMP skips against 9.78M
  makes. Strength is the SPRTs' to judge.
- Profile: `take_next` 26.5% (was 16.2%), `see_value` 10.6% (6.5%), eval
  10.8%, `negamax<false>` 7.9%, `generate<Captures>` 7.8%,
  `refresh_check_info` 6.8%, `quiesce<false>` 4.4%, `generate<Quiets>`
  3.5%, TT 5.6%, `gives_check` 2.8%, make/unmake 5.2%.
- Candidate optimizations (measure later, only after the SPRTs, with the
  A/B harness): in a futile node, skip the history scoring and the
  selection sort for quiets (only checking quiets survive); test futility
  before the SEE prune; a cheaper pre-filter for gives_check (direct-check
  squares only, then discovered checks). Each must keep bench identical.

## Fork's own constants (69e830a, against 40fdf8f)

- Bench 16,540,472 nodes, signature 779d36c67f079e12 (40fdf8f: 10,351,634
  at the same depth 13: the milder late move pruning and null move search
  more nodes).
- nps: median 5,642,910 -> 5,916,238 (+4.8%), best +4.5%, noise threshold
  3.0%: B faster. Fewer moves are pruned per node, so less selection and
  SEE work is spent on moves that are never made.
- Profile: `take_next` 25.9%, `side_score` 11.0%, `see_value` 10.8%,
  `negamax<false>` 8.6%, `generate<Captures>` 7.6%, `refresh_check_info`
  7.1%, `quiesce<false>` 5.1%, TT 6.1%, `generate<Quiets>` 3.3%,
  make/unmake 5.8%, `gives_check` 2.5%, `predicted_key` 2.0%,
  `bootstrap_eval` 1.9%.

## Milestone C (91365e2, against the Milestone B build f919c01)

- Bench 17,309,921 nodes, signature 372dc2e2d8a88e4b (f919c01: 16,540,472,
  779d36c67f079e12: different trees, the TT-refined eval's default).
- nps: median 5,953,901 -> 6,625,718 (+11.3%), best +12.6%, noise threshold
  4.7%: B faster (6 interleaved rounds, identity checked on all 12 runs).
- Profile: `take_next` 19.5% (25.9% at 69e830a), `see_at_least` 12.9%,
  `side_score` 10.8%, `generate<Captures>` 9.5%, `refresh_check_info` 7.7%,
  `negamax<false>` 7.7%, `quiesce<false>` 5.6%, `deposit` 4.3%, `fetch`
  3.7%, `make` 3.9%, `unmake` 2.8%, `generate<Quiets>` 3.5%,
  `predicted_key` 2.2%, `bootstrap_eval` 1.9%. The futile-node filter
  (3a8a1b6) moved most of take_next's share.
- The gate's profile step failed (`perf_symbols.py` resolved from a relative
  path after a cd); `tools/perf_gate.sh` fixed; the profile taken by hand.
