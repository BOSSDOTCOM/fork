# Bug review follow-up: T1, T4 and T5 (2026-11-11)

The owner's decisions on the bug review (docs/research/bug-review-2026-11-11.md; DESIGN.md §6, 2026-11-11,
about 6:20 PM EST) asked for three pieces of tooling work: a held-out endgame check (T1), the transfer ratio's
stopping bias (T4) and a check of the scale matching (T5). Order and gating (owner, about 6:40 PM EST): T1 and T5
before the next network decision (8c), T4 before the next gauntlet reading. Done the same evening on phase-4
e63101a; tools and documents only, the engine and bench unchanged (10,166,167 / d874b380155a2e8c). Every number
below comes from a run on the local machine (Python 3.12, python-chess, the integer reference evaluation R-int
of tools/nnue/models.py; Syzygy 3-4-5 at `~/fork-data/syzygy/3-4-5` on Windows, the same 290 files by name and
size as the WSL copy `~/fork-tools/syzygy/3-4-5`, four of the tables used here (KQvKR, KBNvK, KPvKP, KRvKP)
identical by SHA-256).

## T1. A held-out endgame check

**The old check measures recall, confirmed and widened.** tools/nnue/endgame_check.py's 900 positions (seed
20261105) were matched exactly (board and side to move) against every record of the endgame slice:

| Slice file | Records | SHA-256 (first 16) | Old check positions found |
|---|---|---|---|
| slice1-00.vf | 2,600,000 | 9a1af94dd06e1c28 | 517 |
| slice1-01.vf | 2,600,000 | d4258f69fed3cfd8 | **509** (KPK 184, KQK 170, KRK 155: the review's figures) |
| slice1-02 to slice1-09 | 2,600,000 each | as data/manifests/g3s2.json | 522 to 537 each |
| g3s2-slice1-00-rest.vf | 2,599,940 | 4694e2b0b1c2ff25 | 517 |
| **all eleven files** | 28,599,940 | | **898 of 900** (KPK 300, KQK 300, KRK 298) |

The review's 509 was one file; the slice as trained holds 898 of the 900. So the "351 → 8" result says that the
nets learned the slice's own positions; it says nothing about endings the slice does not contain. Ten of the
eleven files match g3s2's manifest by SHA-256 (slice1-00.vf itself is not in the manifest; its rest file, which
is, holds the same 517 matches).

**What the slice can generate** (tools/datagen/endgame_slice.py): random legal placements, either colour on
either side, of KPvK, KQvK or KRvK (half the positions) or of a signature Fork's games reach at table entry (the
other half, in proportion). A capture removes one piece at a time from 32, so the first position of at most 5
pieces has exactly 5: the signature list (signatures.json, 60,000 games) holds 103 five-piece material classes
and no four-piece one. The slice files confirm it: their material-class histogram has 3 three-piece and 103
five-piece classes, nothing else.

**The construction** (tools/nnue/endgame_heldout.py, `generate`; the positions committed as
tools/nnue/endgame_heldout.tsv, 3,800 lines, SHA-256 6e2e6fcc0b601061..., reproduced byte for byte by a second
run):
- 16 four-piece classes (none can come from the slice): KQvKR, KQvKP, KRvKP, KRvKB, KRvKN, KPvKP, KQvKQ, KRvKR,
  KBvKP, KNvKP, KBNvK, KBBvK, KNNvK, KBPvK, KNPvK, KPPvK;
- 3 five-piece classes absent from the slice's signature list: KQvKBN, KQvKBB, KQvKNN;
- 200 positions per class, seed 20261111, no (board, side to move) twice;
- **endgame_check.py's rules unchanged:** random placement with the strong side's colour and the side to move
  drawn at random, pawns on ranks 2-7, kept when legal, not in check, no capture available and not over; the
  label is the Syzygy WDL from the side to move; misjudged as declared before the first run of the old check:
  won below +100 cp, lost above -100 cp, drawn beyond ±200 cp, by each net's R-int at its own scale. As in the
  old check a cursed win counts as won and a blessed loss as lost (9 positions, all KQvKBB blessed losses; the
  WDL is in the file, so they can be split out). endgame_check.py was refactored to share its rules (a
  `positions()` function and a main guard); its output on r8brft1 and S512+PP is byte for byte the old
  script's (7 and 351).

**Zero overlap, proved by an exact match** (`overlap`, the slice's own 24 board bytes plus the side-to-move bit,
the same key that finds the old check's 898): **0 of the 3,800 positions in any of the eleven files**, and none
of the 19 classes appears in the files' histogram at all. A unit test plants a check position in a fake slice
file and finds it (and not its other-side-to-move twin).

**What was not checked:** the Kaggle datasets were not downloaded again (the local files match the manifest the
datasets were built from; g3s3 and g4s1 reuse the same slice files by their manifests and nets.md); endgame
slice v2 (`slice2-*.vf`) has not been generated (design only; no file on this machine or in WSL); the
positional and defense slices are not endgame slices and were not scanned; the self-play shards were not
scanned (their games stop at table entry, so they hold no 4-piece position; a 5-piece queen-against-two-minors
position could in principle be a game's last position: UNVERIFIED, though none occurs in signatures.json's
60,000 games).

**Results** (misjudged positions of 200 per class):

| Class | r8brft1 | S512+PP | S512ppr3 | r8btd90 | S512ppr2 | S512r2 |
|---|---|---|---|---|---|---|
| KQvKR | 57 | 132 | 31 | 48 | 7 | 35 |
| KQvKP | 5 | 38 | 5 | 4 | 5 | 6 |
| KRvKP | 20 | 115 | 18 | 18 | 19 | 73 |
| KRvKB | 7 | 10 | 6 | 6 | 9 | 10 |
| KRvKN | 26 | 42 | 20 | 23 | 18 | 37 |
| KPvKP | 30 | 61 | 30 | 29 | 30 | 69 |
| KQvKQ | 6 | 10 | 6 | 6 | 7 | 10 |
| KRvKR | 4 | 5 | 4 | 4 | 5 | 5 |
| KBvKP | 2 | 8 | 2 | 2 | 5 | 13 |
| KNvKP | 9 | 3 | 9 | 9 | 6 | 9 |
| KBNvK | 77 | 189 | 73 | 73 | 70 | 165 |
| KBBvK | 94 | 199 | 83 | 82 | 82 | 175 |
| KNNvK | 60 | 3 | 79 | 77 | 82 | 14 |
| KBPvK | 16 | 8 | 11 | 10 | 5 | 3 |
| KNPvK | 6 | 6 | 3 | 5 | 4 | 4 |
| KPPvK | 4 | 1 | 5 | 4 | 3 | 3 |
| KQvKBN | 73 | 33 | 54 | 51 | 37 | 6 |
| KQvKBB | 84 | 68 | 56 | 56 | 48 | 16 |
| KQvKNN | 32 | 14 | 19 | 19 | 12 | 5 |
| **4-piece (3,200)** | **423** | **830** | 385 | 400 | 357 | 631 |
| **5-piece (600)** | **189** | **115** | 129 | 126 | 97 | 27 |
| **all (3,800)** | **612 (16.1%)** | **945 (24.9%)** | 514 (13.5%) | 526 (13.8%) | 454 (11.9%) | 658 (17.3%) |

The asked-for pair, the default r8brft1 against S512+PP (nets/s512pp.fnet, the same blob as bake/s512pp 412b13f):
**612 against 945**; S512ppr3 and r8btd90 were cheap and added, S512ppr2 and S512r2 for the lineage. The won /
drawn / lost split per class is in the tool's output (`check`).

What it shows:
- **The slice did generalise to some unseen endings:** on the four-piece classes the slice-trained nets
  misjudge 357-423 against S512+PP's 830 (KQvKR, KRvKP, KPvKP, KBNvK and KBBvK improve most).
- **Queen against two minor pieces got worse:** S512r2 misjudged 27 of 600, S512+PP 115, the slice-trained
  nets 97-189. Two knights against a bare king (a draw) are misjudged by the slice-trained nets: 60-82 of 200
  beyond ±200 cp, against S512+PP's 3.
- **The errors sit on one side to move:** most misjudged KBNvK, KBBvK and KQvKR positions are the ones where the
  defending side is to move and lost (r8brft1 KBNvK: 73 of 101 lost positions misjudged, 4 of 98 won ones).
- **The lineage drifts on held-out endings while the recall check stays flat:** S512ppr2 454, S512ppr3 514,
  r8btd90 526, r8brft1 612 (its result fine-tune adds most of the five-piece rise, 126 → 189), all at 7-8 of 900
  on the old check.

**Records corrected** (Python edits, line endings kept): DESIGN.md (the §5.6 order row for idea 45, item 8a's
gate, the S512ppr2 promotion row), docs/nets.md (the endgame rows of S512+PP, S512ppr2, S512ppr3, r8btd90,
r8brft1, now with the held-out figure), docs/ideas.md idea 45, the sprt-log's S512ppr2 entry, endgame slice v2's
design (its evidence table) and the engine survey's comparison row. The ≤ 15 of 900 gate itself is unchanged:
it still catches a net that lost the slice, but it is a recall gate. The gates script
(`~/fork-data/8b/gates.sh`) lives outside the repo and was not changed. The think tank's research documents
(docs/research/phase4-think-tank/) and the transfer-testing report quote "351 → 8" as written at the time; they
were left as historical records.

## T5. Scale matching

The inputs each shipped net's gate used were found and the gate's numbers reproduced: tools/nnue/match_scale.py,
the first 4,000 positions passing the training filter in the validation file of the net's snapshot, the control
at its own S, the candidate at S = 92 (r8brft1: control r8btd90, g4s1-val, `~/fork-data/8b-rft/gates-r8brft1.log`:
213.84 and 224.24, S = 88). The matched S for each method is 92 × statistic(control) / statistic(candidate at 92).

| Net (control, file) | Games | Share of Σ\|eval\| above 400 cp (control; candidate) | Positions above 400 | Mean (shipped S) | Median | Mean, \|control\| ≤ 400 | Mean, both ≤ 400 | Slope, \|control\| ≤ 400 | Slope, all | 90% bootstrap over games: mean; median; ≤ 400 |
|---|---|---|---|---|---|---|---|---|---|---|
| S512+PP (S512r2, g3s1-val) | 92 | 46.7%; 47.4% | 18.4% | 90.24 (90) | 90.83 | 90.34 | 90.60 | 89.81 | 89.53 | 89.4-91.1; 86.6-92.6; 89.3-91.5 |
| S512ppr2 (S512+PP, g3s2-val) | 96 | 48.0%; 50.9% | 19.0% | 89.16 (89) | 90.82 | 90.31 | 90.48 | 89.61 | 87.91 | 88.7-89.7; 88.9-92.0; 89.6-91.1 |
| S512ppr3 (S512ppr2, g3s3-val) | 96 | 46.0%; 49.0% | 17.4% | 88.59 (89) | 88.97 | 88.70 | 88.74 | 88.76 | 88.47 | 88.4-88.8; 87.8-90.0; 88.4-89.0 |
| r8btd90 (S512ppr3, g4s1-val) | 96 | 44.6%; 47.5% | 16.7% | 88.82 (89) | 89.32 | 88.94 | 88.97 | 88.90 | 88.71 | 88.7-89.0; 87.7-90.0; 88.7-89.1 |
| r8brft1 (r8btd90, g4s1-val) | 96 | 44.7%; 48.0% | 16.7% | 87.73 (88) | 87.61 | 87.54 | 87.60 | 87.32 | 87.77 | 87.4-88.0; 86.6-89.2; 87.1-87.9 |

- **The share is 45-48% for the control and 47-51% for the candidate, not 56%** (the review's figure was not
  reproduced on these inputs; its exact input is not known). About 17-19% of the positions are above 400 cp, so
  they do carry about half of the mean.
- **The robust statistics move S by at most 1-2 units, on the two oldest nets only:** S512+PP 90 → 91 by the
  median or the both-≤ 400 mean (90 by the others); S512ppr2 89 → 90 or 91 by every robust statistic (88 by the
  all-position slope). S512ppr3, r8btd90 and r8brft1 keep their S under every statistic except a slope
  (S512ppr3 88 by the all-position slope, r8brft1 87 by the ≤ 400 one). One unit of S is about 1.1% of every
  evaluation.
- **The sampling noise is the same size:** the 4,000 positions come from 92-96 consecutive games of one source,
  and a bootstrap over those games moves the mean-based S by ±0.2 to ±0.9 (the median's by ±1.1 to ±3).
- **No bug; recommendation:** keep the statistic for now. If the gate is revised, use the mean |eval| over the
  positions where the control's |eval| ≤ 400 (as stable as the mean, less weight on decided positions) and draw
  the positions from many games (for example 40 positions from each of 100+ games across the file's sources),
  which narrows the interval more than any choice of statistic. No shipped net's S needs changing: the largest
  difference (S512ppr2, 1-2 units) is on a retired net.
- Found on the way: docs/nets.md had S512+PP's two means swapped (S512r2's mean is 217.63, S512+PP's at S = 92
  is 221.88); corrected.

## T4. The transfer ratio's stopping bias

**Model and code** (tools/gauntlet/stopbias.py, tested in test_stopbias.py, used by report.py): under the normal
model of tools/cloud/sprt_merge.py the nElo estimate after n pairs is normal around the true value with SD
C/√n (C = 800 / (ln 10 √2)), and the LLR is a linear function of it, so each stage boundary is a pair of limits
on the estimate. Each design (design R at STC: [0, 6], α 0.05, β 0.20, cap 8, futility after 2; network at STC:
[0, 5], α = β = 0.05, cap 13; stages of 800 pairs) is computed exactly as a Gaussian random walk checked at stage
boundaries (lattice 0.25 nElo; the outcome probabilities sum to 1 within rounding). Checks: the limits give sprt_merge's verdicts on random
pentanomial counts; the outcome probabilities agree with an independent Monte Carlo (20,000 trials) and with the
review's power table (e.g. design R at 0: 1.55% pass, 38.0% H0, 35.9% futility, 24.5% capped); the pass bias
E[estimate | H1] − θ reproduces the review's +7.6, +5.1, +3.2 nElo at θ = 3, 6, 9 (here +7.69, +5.08, +3.15);
fault injection (design R without its futility look) fails the test.

**Two corrections per adopted entry, from its design and stop stage** (transfer.json now records each SPRT's
design, stages played and nElo, from the sprt-log):
1. **Median-unbiased at the stop stage** (stage-wise ordering: an earlier H1 is more extreme than a later one,
   at the same stage a larger estimate is more extreme; the θ at which the observed outcome is the median).
   Principled and stable, but it removes only the stopping rule's share: in Monte Carlo of the passed tests its
   bias is still +7.0, +4.4, +2.5 nElo for design R at θ = 3, 6, 9 (raw +7.6, +5.0, +3.1), and +4.9, +2.5, +1.1
   for the network design at 3, 6, 9.
2. **Plug-in selection correction:** the median-unbiased estimate minus the design's pass bias at that estimate.
   A sensitivity figure, not an unbiased estimate: a passed test does not pin down its own true effect, and the
   selection bias depends on it. Removing it properly needs a prior over the true effects of tested ideas
   (empirical Bayes over every SPRT, passed or not, whose likelihood does not depend on the stopping rule); not
   done.

| Entry (design, stages, nElo) | Recorded Elo | Median-unbiased | Plug-in |
|---|---|---|---|
| S512+PP (network, 1, 53.37) | +32.67 | +32.67 | +31.86 |
| select_best (no SPRT: a speed pricing) | +6.00 | +6.00 | +6.00 |
| S512ppr2 (network, 2, 33.60) | +20.11 | +20.09 | +19.60 |
| S512ppr3 (network, 5, 11.98) | +7.12 | +6.98 | +6.16 |
| Time management (b) (design R, 2, 31.40) | +18.69 | +18.45 | +17.58 |
| R14 SPSA margins (design R, 1, 64.91) | +37.93 | +37.93 | +37.92 |
| r8btd90 (network, 3, 20.96) | +12.17 | +12.03 | +11.34 |
| r8brft1 (network, 7, 9.69) | +5.74 | +5.41 | +4.38 |
| cut-node (design R, 7, 10.55) | +6.02 | +4.86 | +2.92 |
| T56 any-attack (design R, 4, 13.04) | +7.49 | +7.25 | +6.16 |

**Today's ratios both ways** (report.py --level0 on the archived runs, the same anchor gains as recorded: +19.4
over 32c5517's gauntlet, +73.6 over the baseline 41465146207):

| Ratio | Recorded sum, ratio (95%) | Median-unbiased sum, ratio (95%) | Plug-in sum, ratio (95%) |
|---|---|---|---|
| Window since 32c5517 (5 changes) | +69.3, **0.28** (0.02-0.56) | +67.5, **0.29** (0.02-0.58) | +62.7, **0.31** (0.02-0.63) |
| Running since 3902d00 (10 changes) | +153.9, **0.48** (0.33-0.66) | +151.7, **0.49** (0.33-0.67) | +143.9, **0.51** (0.35-0.71) |

**Reading:** the stopping bias explains little of the gap. The window's sum is dominated by R14 (+37.9 Elo,
stopped at stage 1 far above its limit, so almost no bias); the marginal late passes (cut-node, r8brft1, T56)
carry most of the correction, a few Elo in all. Even with the plug-in correction the window transfers about 0.31
of its self-play gain, so the engineering review's reading (transfer well below 1 in balanced gauntlets) stands;
the open question remains self-play inflation and the book (DESIGN.md §6, 2026-11-11, the transfer diagnostic).
The plug-in is not a bound: if the marginal entries' true effects were near 3 nElo, their overstatement would be
about 7.7 nElo (4.5 Elo) each.

report.py prints the two corrected sums and ratios beside the recorded one in every gauntlet report from now on,
with each design's pass bias at 3, 6 and 9 nElo; an entry without an "sprt" record counts as recorded, and if no
entry has one the section says the ratio is not corrected and understated.

## Files

- tools/nnue/endgame_heldout.py, tools/nnue/endgame_heldout.tsv, tools/nnue/test_endgame_heldout.py;
  tools/nnue/endgame_check.py (refactor, output unchanged; its docstring states the recall finding).
- tools/gauntlet/stopbias.py, tools/gauntlet/test_stopbias.py; tools/gauntlet/report.py (the stopping-bias
  lines), tools/gauntlet/test_report.py, tools/gauntlet/transfer.json (the "sprt" records).
- The T5 measurement script was a one-off (it reuses match_scale.py's position filter and models.r_int) and is
  not committed.

## UNVERIFIED

- Whether any self-play shard holds a 5-piece queen-against-two-minors position identical to a check position
  (not scanned; 4-piece positions cannot occur there).
- The Kaggle copies of the slice files (not re-downloaded; the local files match g3s2's manifest).
- The review's 56% share (not reproduced on the gates' inputs; 45-51% here).
- The size of the selection bias in today's sum: only bracketed (median-unbiased and plug-in), not estimated.
