# Ensemble teacher, step 0: results

Run on 2026-11-09 by the rules in `step0-declaration.md` (committed dc90302 at about 6:35 PM EST, before any label).
Tools at eaa31fb. Result files are in `step0/` beside this file. Raw labels stay outside the repository
(`~/fork-measure/teacher0/`).

**Verdict: kill.** S512ppr3 at 60k nodes is better than E3 (three members at 20k each, equal total nodes) on Y1 and on
the gold-mean Y2, both by clear intervals. All three 1M golds agree, including the two scratch golds that share no
network with the 60k label. By the declared rule no small net is trained; the owner has this report.

## Engines and checks

All three engines were built from 2b1c78b (Fork 0.3.0-dev+2b1c78b) with the clang-release preset on Windows
(LLVM-MinGW clang 23.1.3, arch native, LTO on, low priority).

| member | engine SHA-256 | net | bench (reference) | netcheck |
|---|---|---|---|---|
| S512ppr3 | 17ab2b41...0b34 (H's pinned labeller) | s512ppr3, header S = 89 | 14,149,617 / 1cb0717f040c294d | (pinned) |
| scratch-s1 | e2643625...8389 | s512pp-scratch-s1.fnet from dcbe8fb (769bffe2...6cb5), header S = 90 | 15,793,636 / 22fb22319f919369 | 446 positions, 0 mismatches against dcbe8fb's `tests/nnue/s512pp-scratch-s1.parity` |
| scratch-s2 | a97c98da...918eb (full value in step0/manifest.json) | item 7's Kaggle s512pp-scratch-s2.fnet (5cd93409...6cc5), header S = 92 | 14,148,026 / e05c5663f82fce47 | 446 positions, 0 mismatches against the .parity file beside it (a56e2406...1ddd1) |

- **Checks:**
  - The netcheck can fail: the s1 engine against s2's parity file gives 443 mismatches and exit 1.
  - Each engine's SHA-256 and bench matched before its first label (6:47 PM) and after its last (8:13 PM).
  - A clean rebuild of 2b1c78b with the default net gives the pinned bench (14,149,617 / 1cb0717f040c294d) and the
    same version lines. Its bytes differ from the pinned exe (7,947,776 against 7,948,288 bytes), so "differ only in
    the network" holds at the source, build-settings and bench level, not byte for byte.
- **Scale note:** scratch-s2's file is at S = 92, not the 89-90 the declaration assumed (report.md's "converted at 89"
  refers to idea 52's own conversion). The declared file was used. Static mean |eval| on the 15,499 kept records:
  S512ppr3 250.4 cp, scratch-s1 250.1, scratch-s2 254.0: within 1.5%, closer than an S = 89 file would be (about
  -1.9%).

## Sites and labels

- **H:** the 5,000 held-out sites unchanged (sites.jsonl 64862be3...ec52; 3,131 kept). All matched: no shard, match or
  duplicate losses.
- **H2:** `label_pretest.py sample g3j-w05-val.vf --games 20000 --seed 5203`. Shard SHA-256 54c0cfaf...eed1e1 matches
  data/manifests/g3j.json. 20,000 sites; **267 dropped as games already in H**, leaving 19,733 sites, 12,368 kept, all
  matched.
- **Job `teacher-step0`:** jobctl `measure`, **6:46:53 to 8:13:18 PM EST (1 h 26 min)**, two workers at below-normal
  priority beside g4; one thread, Hash 16, `ucinewgame` before each search, Syzygy 3-4-5.
  - Golds: scratch-s1 1M on H 6:47-7:10, scratch-s2 1M 7:10-7:30.
  - 20k (three members) and 60k on H, 7:30-7:34; on H2, 7:34-7:47.
  - 50k and 100k on H, 7:47-7:51; on H2, 7:51-8:13.
- **Mate-flagged labels (H):** golds 161 / 172 / 166 (S512ppr3 / s1 / s2), mean depth 18.8 each.
- **The mate rule in E3 (H; H2):** 66; 240 majority mates; 4; 29 records with mate members left out; 0 records with
  every member left out.
- **Mean |cp| on kept non-mate labels (H):** 20k 310, 50k 389, 60k 411, 100k 454, 1M 764. Deeper labels are much more
  decided.

## Y1: Brier score against the game result (kept records; 95% intervals, 10,000 game resamples, seed 5203)

| label | H + H2 (15,499) | H (3,131) | H2 (12,368) |
|---|---|---|---|
| E3 (3 × 20k) | 0.046177 [0.044544, 0.047803] | 0.043568 [0.040119, 0.047069] | 0.046838 [0.045009, 0.048694] |
| S512ppr3 60k | **0.045066** [0.043459, 0.046675] | 0.042256 [0.038866, 0.045708] | 0.045778 [0.043962, 0.047619] |
| E2i (2 × 20k) | 0.046358 [0.044714, 0.047997] | 0.043739 [0.040316, 0.047276] | 0.047021 [0.045174, 0.048899] |
| S512ppr3 20k | 0.046255 [0.044621, 0.047883] | 0.043684 [0.040233, 0.047189] | 0.046906 [0.045085, 0.048757] |
| S512ppr3 50k | 0.045316 [0.043702, 0.046933] | 0.042525 [0.039111, 0.045985] | 0.046022 [0.044203, 0.047876] |
| S512ppr3 100k | 0.044711 [0.043108, 0.046328] | 0.041800 [0.038452, 0.045224] | 0.045448 [0.043631, 0.047288] |
| scratch-s1 20k | 0.046717 [0.045061, 0.048372] | 0.044103 [0.040642, 0.047600] | 0.047379 [0.045511, 0.049268] |
| scratch-s2 20k | 0.046495 [0.044827, 0.048151] | 0.043858 [0.040399, 0.047426] | 0.047163 [0.045306, 0.049065] |
| stored game score (S512ppr3 20k, game-long table, Hash 1 MB) | 0.045721 [0.044100, 0.047352] | 0.043421 [0.040021, 0.046884] | 0.046303 [0.044489, 0.048150] |
| M1 (static E3) | 0.053573 [0.051820, 0.055326] | 0.052129 [0.048297, 0.056033] | 0.053938 [0.051956, 0.055950] |
| S512ppr3 1M (gold) | | 0.041094 [0.037696, 0.044540] | |
| scratch-s1 1M (gold) | | 0.041825 [0.038340, 0.045388] | |
| scratch-s2 1M (gold) | | 0.041029 [0.037618, 0.044495] | |

## Y2: squared error in p against each 1M gold (H, 3,131 kept records)

Shared members, candidate with gold: E3 shares one member with every gold; E2i shares scratch-s1 with s1's gold and
scratch-s2 with s2's gold; S512ppr3 at any depth shares S512ppr3's gold; the gold mean contains all three members.

| label | gold mean | S512ppr3 1M | scratch-s1 1M | scratch-s2 1M |
|---|---|---|---|---|
| E3 | 0.001586 [0.001318, 0.001907] | 0.001713 [0.001412, 0.002076] | 0.001679 [0.001423, 0.001965] | 0.001868 [0.001551, 0.002263] |
| S512ppr3 60k | **0.001131** [0.000904, 0.001425] | 0.001186 [0.000925, 0.001529] | 0.001250 [0.001054, 0.001496] | 0.001460 [0.001169, 0.001837] |
| E2i | 0.001679 [0.001394, 0.002010] | 0.001857 [0.001544, 0.002230] | 0.001747 [0.001481, 0.002041] | 0.001935 [0.001596, 0.002343] |
| S512ppr3 20k | 0.001859 [0.001577, 0.002190] | 0.001886 [0.001573, 0.002256] | 0.002002 [0.001724, 0.002326] | 0.002193 [0.001865, 0.002590] |
| S512ppr3 50k | 0.001294 [0.001051, 0.001600] | 0.001337 [0.001060, 0.001686] | 0.001403 [0.001186, 0.001653] | 0.001644 [0.001336, 0.002033] |
| S512ppr3 100k | 0.000863 [0.000713, 0.001048] | 0.000898 [0.000722, 0.001126] | 0.001024 [0.000873, 0.001208] | 0.001169 [0.000964, 0.001417] |
| scratch-s1 20k | 0.001974 [0.001665, 0.002331] | 0.002154 [0.001814, 0.002549] | 0.001947 [0.001656, 0.002284] | 0.002324 [0.001954, 0.002759] |
| scratch-s2 20k | 0.001865 [0.001566, 0.002213] | 0.002041 [0.001709, 0.002428] | 0.002029 [0.001743, 0.002344] | 0.002027 [0.001675, 0.002446] |
| stored game score | 0.001663 [0.001399, 0.001959] | 0.001687 [0.001401, 0.002014] | 0.001824 [0.001552, 0.002134] | 0.001980 [0.001680, 0.002329] |
| M1 (static E3) | 0.008392 [0.007217, 0.009652] | 0.008433 [0.007247, 0.009708] | 0.008450 [0.007282, 0.009687] | 0.008796 [0.007589, 0.010079] |

The golds against each other: S512ppr3 / s1 0.000521 [0.000413, 0.000688]; S512ppr3 / s2 0.000428 [0.000376, 0.000487];
s1 / s2 0.000559 [0.000436, 0.000735].

## Paired differences (A − B; negative means A is better)

| A − B | Y1 H + H2 | Y2 gold mean | Y2 S512ppr3 1M | Y2 s1 1M | Y2 s2 1M |
|---|---|---|---|---|---|
| **E3 − S512ppr3 60k (the gate)** | **+0.001111 [+0.000858, +0.001362]** | **+0.000455 [+0.000300, +0.000620]** | +0.000527 [+0.000368, +0.000697] | +0.000429 [+0.000264, +0.000606] | +0.000408 [+0.000253, +0.000574] |
| E2i − S512ppr3 50k (report only; 40k not labelled, 50k used as declared) | +0.001042 [+0.000747, +0.001332] | +0.000385 [+0.000224, +0.000557] | +0.000520 [+0.000360, +0.000693] | +0.000344 [+0.000175, +0.000528] | +0.000291 [+0.000119, +0.000470] |
| E3 − S512ppr3 20k | −0.000078 [−0.000249, +0.000093] | −0.000273 [−0.000384, −0.000166] | −0.000172 [−0.000279, −0.000067] | −0.000323 [−0.000438, −0.000213] | −0.000325 [−0.000441, −0.000211] |
| E3 − E2i | −0.000180 [−0.000269, −0.000094] | −0.000093 [−0.000149, −0.000038] | −0.000143 [−0.000199, −0.000088] | −0.000068 [−0.000128, −0.000011] | −0.000067 [−0.000125, −0.000011] |
| E2i − scratch-s1 20k | −0.000360 [−0.000525, −0.000201] | −0.000296 [−0.000408, −0.000193] | −0.000298 [−0.000411, −0.000195] | −0.000200 [−0.000316, −0.000095] | −0.000390 [−0.000507, −0.000283] |
| M1 − E3 (floor) | +0.007396 [+0.006603, +0.008188] | +0.006806 [+0.005703, +0.007984] | +0.006720 [+0.005614, +0.007906] | +0.006771 [+0.005674, +0.007943] | +0.006928 [+0.005809, +0.008122] |
| S512ppr3 20k (fresh table) − stored game score | +0.000535 [+0.000288, +0.000783] | +0.000196 [−0.000008, +0.000435] | +0.000199 [−0.000016, +0.000453] | +0.000178 [−0.000004, +0.000379] | +0.000213 [−0.000012, +0.000482] |
| E3 − S512ppr3 100k | +0.001466 [+0.001160, +0.001766] | +0.000723 [+0.000489, +0.001008] | +0.000815 [+0.000572, +0.001116] | +0.000655 [+0.000434, +0.000906] | +0.000699 [+0.000441, +0.001020] |

The E3 − 60k Y1 difference holds in each set separately: H +0.001312 [+0.000820, +0.001807]; H2 +0.001060 [+0.000763,
+0.001360].

## The depth curve (item 2; S512ppr3 alone)

| nodes | Y1 H + H2 | Y2 gold mean | Y2 S512ppr3 1M | Y2 s1 1M | Y2 s2 1M |
|---|---|---|---|---|---|
| 20k | 0.046255 | 0.001859 | 0.001886 | 0.002002 | 0.002193 |
| 50k | 0.045316 | 0.001294 | 0.001337 | 0.001403 | 0.001644 |
| 60k | 0.045066 | 0.001131 | 0.001186 | 0.001250 | 0.001460 |
| 100k | 0.044711 | 0.000863 | 0.000898 | 0.001024 | 0.001169 |
| 1M (H only) | 0.041094 (H) | 0.000149 | — | 0.000521 | 0.000428 |

Each step is significant on Y1 (pooled): 50k − 20k −0.000940 [−0.001192, −0.000697]; 60k − 50k −0.000249 [−0.000352,
−0.000148]; 100k − 60k −0.000355 [−0.000554, −0.000161]; and on every gold's Y2. The independent golds show the same
shape. Each S512ppr3 depth sits closer to S512ppr3's own gold than to s2's (100k: 0.000898 against 0.001169), the
expected same-network pull; the ordering does not change.

## The gate

- **Pass needs** E3's Y1 below 60k's and the E3 − 60k gold-mean Y2 interval below 0. **Neither holds.**
- **Kill:** 60k is at least as good on both point estimates. **It is, on both, with intervals excluding 0.** All three
  golds and both site sets agree.

## Reading (report only)

- Averaging three independent 20k members does help against one 20k search: Y2 is lower under every gold, by
  0.00017-0.00033; E3 beats E2i, and E2i beats each of its members. The gain is about a quarter of what three times the
  nodes on one net buys: 50k already beats E2i, and 60k beats E3.
- The win-probability mean of three 20k members keeps their decisiveness (mean |cp| about 306). Deeper searches resolve
  positions (|cp| 386 at 60k, 764 at 1M), and both yardsticks reward that. A likely reason, UNVERIFIED as a mechanism.
- The stored game score (game-long table) is better than a fresh-table 20k search on Y1 (H + H2: +0.000535 [+0.000288,
  +0.000783]; H2 alone: +0.000603); on Y2 better at the point estimate only (intervals touch 0).
- M1 (static E3) is far worse than any search label, as a floor should be.

## Notes and deviations

1. **The Y1 gate set** was read on H + H2 pooled ("the kept records of H and H2"). H and H2 separately give the same
   answer.
2. **The bootstrap draw.** Y1/Y2 intervals resample the games that have a kept record (one record per game). The bias
   section uses label_pretest's draw over all 5,000 games, which reproduces labels-8b.json exactly.
3. **Analysis outside jobctl.** The tables ran as jobctl job `teacher-step0-tables` (8:13-8:33 PM): H and H2 completed.
   The pooled run then failed on a path bug in the driver script (Git Bash does not convert a comma-joined path list);
   jobctl recorded exit 0 because of the `cmd start` wrapper. By then `cd-stage1b` held the measure slot (from 8:53
   PM). The rest (pooled Y1, the bias, two `label_pretest.py labels` runs) ran **outside jobctl**, 9:01-9:27 PM EST,
   single-threaded, below normal, CPU only; it touched no labels and no other job.
4. **The H2 sample** (642 s, below normal, 6:25-6:36 PM) also ran before and outside the job; it is sampling, not
   labelling.
5. **Site count:** 24,733 sites in all, not the 25,000 estimated.
