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
