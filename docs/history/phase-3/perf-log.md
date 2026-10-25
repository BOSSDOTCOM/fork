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
