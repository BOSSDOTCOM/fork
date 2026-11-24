import re, sys
p = sys.argv[1]
s = open(p, encoding='utf-8', newline='').read()
start = s.index('<<<<<<< HEAD\n')
mid = s.index('=======\n', start)
end = s.index('>>>>>>> 3b40d1e\n', mid)
head = s[start + len('<<<<<<< HEAD\n'):mid]
s = s[:start] + head + s[end + len('>>>>>>> 3b40d1e\n'):]
old_status = [l for l in head.splitlines() if l.startswith('| Status | **The default network since 2026-11-14**')]
assert len(old_status) == 1
new_status = ("| Status | The default network from 2026-11-14 (owner: promotion pre-approved on H1 with the gates passing and no "
  "held-out flag; H1 at about 5:12 PM EST) until r3kr1 replaced it the same day (default 2026-11-14 until r3kr1; owner's "
  "order, about 7:20 PM EST). The labeller switch to it (pending at generation 4's next part, g4d, and the cloud VM's next "
  "run) is superseded by the switch to r3kr1 (one switch per day, no running generator switched; DESIGN.md §5.3, labeller "
  "policy; §6, the decisions log). Still buildable with `-DFORK_NET=nets/r8ceplo2.fnet` (tests/bench-r8ceplo2.ref), checked "
  "in CI's `nets` job, which also runs its nnue suite: the cases of architecture 8, which the default build (architecture 9) "
  "no longer compiles |")
s = s.replace(old_status[0], new_status)
entry = '''
## r3kr1, bake-off round 3's option (a): H512+PP, king regions with a refresh cache (2026-11-14)

| Item | Value |
|---|---|
| File | `nets/r3kr1.fnet` (branch bake/r3-kr1 3b40d1e, the net that played its tests; byte for byte the gated cand.fnet), 3,785,952 bytes, Fork checksum 7c1d7d61077e6dbb, SHA-256 a650ef23b15d2cb7797aea7eef909e0c1fc7b47f94aa6ea65c1010352d10dcc8 |
| Architecture | **Architecture 9, H512+PP**, the first default of that architecture: S512+PP's 768 piece inputs per own-king region, four regions (M4, read from the net file's 32-entry map of the mirrored own-king cell: e1 / f1-h1 / rank 2 / ranks 3-8), then the 608 pawn-link inputs of rank limit 1 shared by every region; 512 SCReLU; 8 outputs by game phase; QA 255, QB 64. Trained with a 768-input factoriser, merged into every region when saved (3,680 saved inputs, 4,448 in training). The engine refreshes a perspective whose frame changes lazily, from a per-thread refresh cache (16 frame snapshots, 2 perspectives x 2 file flips x 4 regions, about 18 KB per thread). Design and verification: docs/research/bakeoff-r3/option-a-plan.md (the design report docs/research/bakeoff-r3/king-inputs-design.md on branch proto/r3-king-a); S = 89 |
| Data | Retrain 8c's control files on g4s2 (196 training files: TD(0.9) copies of the parts labelled by S512ppr3 or later, blend copies of the older ones, the fresh Syzygy endgame slice slice1b), result weight 0; validation on g4s2-val |
| Training | Kaggle kernel fork-bakeoff-r3 version 1 (tools/train/kaggle/bakeoff_r3.py at retrain/r3-kr4 b96a514; session A: arm kr1 and its same-recipe S512+PP control pp1 side by side, seed 1, the same data order): warm from **r8ceplo2's float window average** (r8ceplo2-avg.bin, dataset fork-r3-init-8c, SHA-256 4118015e47ca596a966ee29821a43ae613155af9b0c9a95913d6fc81e06f3539) laid out as H512+PP (tools/nnue/extend_weights.py --arch h512pp: regions zero, the factoriser r8ceplo2's piece rows; its float loss equal to r8ceplo2's, 0.02011181, and its quantisation identical, both checked in the session), 8c's control recipe (LR 1e-4 dropped tenfold after superbatch 180, 360 superbatches of 305 x 16,384 positions, S = 92), the window average of superbatches 331-360. Full g4s2-val loss (a diagnostic only): **0.01925385** against the control pp1's 0.01955113 and r8ceplo2's 0.01969502; at the result target 0.05670459 (r8ceplo2 0.05711598). No result fine-tune (rft-ep-lo) was run on it |
| Scale | S = 89, matched to r8brft1's mean \|eval\| on 4,000 g4s2-val positions (230.65 cp against 229.47; 238.44 cp at the trainer's S = 92; the gates' control was r8brft1, the default when the chain was written) |
| Conversion | 1 of 311,296 link weights clamped to its unit's allowance under the reader's 64-link bound (1 of 512 units over it; no unit over the bound by its piece weights alone); the unclamped net passes every leg with the same losses |
| Parity (tests/nnue/r3kr1.parity, 446 positions) | trainer leg at most 0.00019 cp; netcheck exact on all 446; quantization loss max 10.2 cp, p99 7.6 cp, mean 2.2 cp, checked against S-512's limits (21 / 16 cp; architecture 9 has no limits row of its own approved in the table above) |
| Endgame check | tools/nnue/gates.sh (LAYOUT=tools/nnue/h512pp.json, SLICE_TRAINED=1, exit 0; ~/fork-data/r3/state/gates-r3kr1.log): the integrity/recall gate **5 of 900 misjudged (0.6%), r8brft1 7** (KPK 4 of 300, KRK 1 of 300, KQK 0 of 300; at most 15: passed). Held-out 4-5 pieces (tools/nnue/endgame_heldout.py, 3,800 positions): **522 misjudged against the then default r8brft1's 612, ratio 0.853** (not flagged); against its warm start r8ceplo2 522 against 525 (-3, -0.6%). Held-out 6-7 pieces (tools/nnue/heldout_67.py, 5,599 positions): **722 against r8brft1's 770, ratio 0.938** (not flagged); against r8ceplo2 722 against 756 (-34, -4.5%). The 8-12-piece deep-label check was not run for this net. UHO/SF19 diagnostic (report only; ~/fork-data/r3/state/uho-diag.md): adv static +38 cp (r8ceplo2 +42, pp1 +39), levelql static +24 (+24, +23): neither declared movement |
| Speed | Production code, bench/ab_search.py (identical trees on r8brft1kr4, x86-64-v3, WSL, 40 interleaved rounds): **0.941 (0.936-0.947)** of S512+PP's nps (docs/research/bakeoff-r3/option-a-plan.md §5); in-situ in the screens' own games 0.933-0.935. Passes the speed gate's 0.90, misses the 0.95 goal |
| Tests | Fixed nodes, 800,000 per move, 1,600 games: against its same-recipe control r3pp1 (bake/r3-pp1), run 43639332954: **+23.92 +/- 9.12 Elo** (nElo +44.80 +/- 17.02), in-situ r 0.9333, speed-adjusted FN_adj +12.18; against r8brft1 (phase-4 7a7f99b), run 43644769111: +21.09 +/- 8.77 (nElo +41.05 +/- 17.02), r 0.935, FN_adj +9.66. Then STC 8+0.08 [0, 5] against **r8ceplo2** (phase-4 5041eb2; r3kr1-promo-stc, `--kind network`), runs 43649791429, 43651376277, 43652992128 and 43654530597: **+8.04 +/- 4.75 Elo (nElo +14.42 +/- 8.51), H1 accepted** (LLR 3.16) after 4 stages, 6,400 games, Ptnml [42, 739, 1506, 855, 58], no time losses (H1 at about 7:00 PM EST; docs/history/phase-4/sprt-log.md). LTC confirmation against r8ceplo2: ordered as non-blocking, no auto-revert (pending) |
| Bench | 5,205,904 nodes, signature dfe99ebe03b0972d (tests/bench-r3kr1.ref), the same on the bake branch's engine (7a7f99b) and on phase-4's at the promotion (b7ea9bf) |
| Status | **The default network since 2026-11-14** (owner's order, about 7:20 PM EST, after the STC H1). The labeller of new data from the next part on, pending: by the one-switch-per-day rule the data generation switches to it at generation 4's next part (g4d) and the cloud VM at its next run; no running generator is switched (DESIGN.md §5.3, labeller policy; §6, the decisions log) |
'''
anchor = '\n## The bake-off entries in CI (2026-10-31)\n'
assert anchor in s
s = s.replace(anchor, entry + anchor, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
