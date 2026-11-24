import sys
p = sys.argv[1]
s = open(p, encoding='utf-8', newline='').read()
lines = s.split('\n')
# Section 5.6: a status row for bake-off round 3 after item 8's row.
i8 = [i for i, l in enumerate(lines) if l.startswith('| Item 8, the retrain loop (8a, 8b, ...) |')]
assert len(i8) == 1
row56 = ("| Bake-off round 3 (the king inputs; option (a), H512+PP) | **r3kr1 promoted to the default network** (owner's order, "
 "2026-11-14, about 7:20 PM EST): architecture 9, H512+PP (S512+PP's inputs per own-king region, four regions M4, a "
 "factoriser in training, a per-thread refresh cache in the engine; docs/research/bakeoff-r3/option-a-plan.md), trained "
 "warm from r8ceplo2's float weights with 8c's control recipe (Kaggle fork-bakeoff-r3 v1, session A, beside its "
 "same-recipe control r3pp1); fixed nodes against r3pp1 **+23.92 ± 9.12** (FN_adj +12.18 at the in-situ r 0.933), "
 "against r8brft1 +21.09 ± 8.77 (FN_adj +9.66); the STC SPRT [0, 5] against r8ceplo2 **H1 accepted, +8.04 ± 4.75** "
 "(nElo +14.42 ± 8.51) after 6,400 games (runs 43649791429 to 43654530597; sprt-log); gates passed (integrity/recall "
 "5 of 900; held-out 522 / 722, no flag); speed 0.941 (0.936-0.947) of S512+PP's nps; bench 5,205,904 / "
 "dfe99ebe03b0972d (docs/nets.md). **Owed:** the LTC confirmation against r8ceplo2 (non-blocking, no automatic revert); "
 "the labeller switch (pending, one per day); the refresh cache on TCEC's hardware "
 "(docs/research/tcec-hardware-test-plan.md). x_lower (xl1, architecture 10): FN_adj +5.94 against r3pp1, −3.16 "
 "against r8ceplo2, not promoted. Options (b) and (c) parked or held as recorded in the decisions log |")
lines.insert(i8[0] + 1, row56)
# Decisions log: the promotion row after the warm-start row.
iw = [i for i, l in enumerate(lines) if l.startswith("| 2026-11-14 | **Round 3's warm-start source is r8ceplo2")]
assert len(iw) == 1
row = ("| 2026-11-14 | **r3kr1 (bake-off round 3's option (a): H512+PP, king regions M4 with a refresh cache) promoted to the "
 "default network (owner's order, about 7:20 PM EST, after its STC H1 at about 7:00 PM).** **The order, verbatim:** "
 "\"Promote round 3 option (a) (king regions M4 + refresh cache) as the new default: prepare the promotion branch "
 "(default switch, bench refs, records, bench parity on all presets), and verify the TCEC build path (update.sh, "
 "x86-64-v3 and v4) builds and runs it with exact parity. Then run an LTC SPRT confirmation vs r8ceplo2 as "
 "non-blocking (report if it fails; no auto-revert). Labeler switch at the next part boundary (one per day). Add king "
 "regions to the TCEC hardware test plan (refresh cache behavior on EPYC's smaller L3 per core).\" **The evidence:** "
 "r3kr1-promo-stc (bake/r3-kr1 3b40d1e against phase-4 5041eb2, r8ceplo2; `--kind network`, STC 8+0.08, [0, 5], "
 "alpha = beta = 0.05, try 1 of 2 of idea bakeoff-r3-a; the comparison against r8ceplo2 by the owner's order of about "
 "5:25 PM): **+8.04 ± 4.75 Elo (nElo +14.42 ± 8.51), H1 accepted** after 4 stages, 6,400 games, LLR 3.16, Ptnml [42, "
 "739, 1506, 855, 58], no time losses (runs 43649791429 to 43654530597; sprt-log). Fixed nodes (800,000 per move, "
 "1,600 games): against its same-recipe control r3pp1 +23.92 ± 9.12 (in-situ r 0.9333, FN_adj +12.18; run "
 "43639332954), against r8brft1 +21.09 ± 8.77 (r 0.935, FN_adj +9.66; run 43644769111). **Gates** (tools/nnue/gates.sh, "
 "LAYOUT=tools/nnue/h512pp.json, SLICE_TRAINED=1, exit 0): S = 89, 1 of 311,296 link weights clamped, netcheck exact "
 "on 446, quantization loss max 10.2 cp, p99 7.6 cp; the integrity/recall gate 5 of 900 (r8brft1 7); no held-out "
 "flag: 4-5 pieces 522 against the then default r8brft1's 612 of 3,800 (0.853; r8ceplo2 525), 6-7 pieces 722 against "
 "770 of 5,599 (0.938; r8ceplo2 756). The UHO/SF19 diagnostic (report only): no declared movement. **Training:** "
 "Kaggle fork-bakeoff-r3 v1, session A (kr1 with the control pp1; retrain/r3-kr4 b96a514), warm from r8ceplo2's float "
 "window average (r8ceplo2-avg.bin, SHA-256 4118015e...), 8c's control recipe and files; full g4s2-val loss 0.01925385 "
 "(pp1 0.01955113, r8ceplo2 0.01969502). **Speed:** 0.941 (0.936-0.947) of S512+PP's nps by bench/ab_search.py "
 "(production code, x86-64-v3); 0.933-0.935 in the screens' own games. Promoted under its bake name (nets/r3kr1.fnet, "
 "SHA-256 a650ef23b15d2cb7797aea7eef909e0c1fc7b47f94aa6ea65c1010352d10dcc8, the gated cand.fnet byte for byte), **the "
 "first default of architecture 9**: the default build now compiles H512+PP's inference and test cases; r8ceplo2 and "
 "r8brft1 stay buildable, r8ceplo2 joins CI's `nets` job with its nnue suite (architecture 8's own cases, which the "
 "default build no longer compiles), and the second-network exact-search case uses r8brft1kr4 in architecture 9 "
 "builds; the web page adds r3kr1 as its default at its next redeploy; tools/gauntlet/transfer.json gains its "
 "`adopted` entry (+8.04, ci95 4.75); tools/nnue/gates.sh's held-out reference moves to r3kr1 (with its layout, "
 "h512pp.json, as the default when HELDOUT_REF is not given). Bench 5,205,904 / dfe99ebe03b0972d, the bake branch's "
 "own, the same on phase-4 b7ea9bf's engine (every other reference unchanged: each belongs to its own net). **LTC "
 "confirmation against r8ceplo2: non-blocking, no automatic revert** (a failure is reported to the owner). **The "
 "labeller (pending, one switch per day):** the data generation switches to r3kr1 at generation 4's next part (g4d), "
 "and the cloud VM at its next run, each from a fresh build of the promoting commit bench-checked against "
 "tests/bench-r3kr1.ref; this supersedes the pending switch to r8ceplo2; no running generator is switched. **TCEC "
 "hardware:** the refresh cache and the larger net (3.79 MB against 1.43 MB) on EPYC's L3 join the TCEC hardware "
 "test plan (docs/research/tcec-hardware-test-plan.md). |")
lines.insert(iw[0] + 1, row)
open(p, 'w', encoding='utf-8', newline='').write('\n'.join(lines))
