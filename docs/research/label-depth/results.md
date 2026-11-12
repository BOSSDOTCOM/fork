# Label depth: the sealed arms, the B0 nets, their gates and bakes

Written 2026-11-12, about 10:30 AM EST. The design is section 1 of docs/research/labels-teacher/report.md (branch
research/labels-teacher), approved by the owner on 2026-11-09; the rate probe and the arms' start are in probe.md.
Every number below is from the runs named. Nothing here is adopted, and nothing here decides: the declared decision
(section 1.5) comes from the fixed-node screens, which the night queue's items 16-ld-a..h run (ld.sh) once
state/ld-ready.json exists and the E1 gate is open.

## 1. The sealed data

ld-chain4 sealed the arms after their 40-hour end (segment 1 18,896 s, seed 2026110900; segment 2 125,108 s, seed
2026110901), 2026-11-12 01:43-07:19 AM EST; manifests committed as data/manifests/ld-*.json (phase-4 b6c6f90, this
branch 3b6a6f8).

| run | games | positions | unsaved | files |
|---|---|---|---|---|
| ld-d20 | 1,101,658 | 104,619,213 | 47,750,972 | 6 training + ld-d20-w02-val.vf |
| ld-d50 | 478,636 | 45,908,474 | 21,010,887 | 6 + ld-d50-w02-val.vf |
| ld-d100 | 245,317 | 23,439,070 | 10,753,565 | 6 + ld-d100-w02-val.vf |
| ld-d20c50 (volume control) | 486,095 | 46,136,449 | 21,057,730 | 6 (validates on ld-d20's) |
| ld-d20c100 (volume control) | 248,238 | 23,572,230 | 10,759,420 | 6 (validates on ld-d20's) |

**Kaggle datasets** (private): bossdotcom/fork-ld-d20, -d50, -d100, -d20c50, -d20c100, 2026-11-12 7:31-7:42 AM
EST. Every local file matched its manifest's SHA-256 before the upload, and all 33 files were downloaded back one by
one and matched again.

## 2. Scale S (design section 1.4, confounder 6)

fit_scale.py, 2,000,000 kept positions (idea 13's count), each arm's training files in the kernel's order:

| arm | S | error at S | at S/2 | at 2S |
|---|---|---|---|---|
| D20 | **81** (used for every arm, as declared) | 0.046334 | 0.053712 | 0.055775 |
| D100 (report only) | 75 | 0.037910 | 0.045133 | 0.046973 |

**D100's own fit is 6 below D20's, outside the design's "about +/-4", so it is reported here.** Every arm trains at
81 as declared. That slightly mismatches D100's labels to the output scale the training assumes, so it is a
small handicap for D100 (and for the D20/100 control, which shares D20's labels and so not this one). It belongs in
any reading of D100's screen.

## 3. The B0 runs (Kaggle fork-label-depth v1, research/label-depth 06d1f63)

Kernel tools/train/kaggle/label_depth.py, idea 13's recipe: from scratch, 80 superbatches of 5 M positions (400 M
seen by every run), LR 0.001 dropped tenfold every 40, result weight 0.5, S = 81, seeds 1 and 2, two runs at a time
on T4 x2; the checkpoint with the lowest validation loss on the arm's own held-out file (the controls on D20's).
Before the push the shard glob was fixed: it read RUN-w*.vf and would have missed segment 2's RUN-s2-wNN.vf files
(the hash check would have refused to train). On Kaggle the hash check passed: 7, 7, 7, 6, 6 shards, no
mismatch. Pushed 7:45 AM, complete 9:36 AM EST; 1.79 GPU hours of the weekly quota (17.49 h left before, 15.70 h
after).

| net | kept superbatch | val loss, own held-out | val loss, D20's held-out | volume-starved (< 40) |
|---|---|---|---|---|
| ld-d20-s1 | 75 | 0.022958 | 0.022958 | no |
| ld-d20-s2 | 79 | 0.022728 | 0.022728 | no |
| ld-d50-s1 | 57 | 0.025330 | 0.024077 | no |
| ld-d50-s2 | 46 | 0.024769 | 0.023771 | no |
| ld-d100-s1 | **4** | 0.023079 | 0.026309 | **yes** |
| ld-d100-s2 | **5** | 0.022545 | 0.026398 | **yes** |
| ld-c50-s1 | 51 | 0.024384 | 0.024384 | no |
| ld-c50-s2 | 58 | 0.024111 | 0.024111 | no |
| ld-c100-s1 | 12 | 0.026076 | 0.026076 | yes |
| ld-c100-s2 | 11 | 0.025761 | 0.025761 | yes |

Readings (none of them a decision input):
- **D100 is volume-starved, as the design anticipated (section 1.4).** Its validation loss is lowest at superbatch
  4-5 and rises after it (seed 1: 0.02308 at 4, 0.02383 at 20, 0.02425 at 80), so the kept nets saw about 20-25 M
  positions. By the design's rule, D100's screen result then reflects its volume, not its labels. D20/100 starves
  the same way (best at 11-12), which places the volume limit near 23 M positions at this recipe.
- Losses on different held-out files are not comparable across arms (D100's own file is easier from superbatch 1:
  0.0248 against D20's 0.0291). On D20's held-out file every deeper arm's net is worse than D20's, and D50 is about
  as far behind D20 as the D20/50 control (0.02408 / 0.02377 against 0.02438 / 0.02411).

## 4. Gates (tools/nnue/gates.sh, phase-4 7eae81a)

The gates and both held-out endgame checks read B0 nets from 7eae81a on (models.evaluator; gates.sh's CONTROL_LAYOUT
and HELDOUT_LAYOUT; no link clamp for a layout without links). Settings for all ten: TRAINED_S 81, the scale matched
to r8brft1's mean |eval| (the default the search's margins are tuned on) on 4,000 positions of ld-d20's held-out file,
the same positions for every net; the endgame check and both held-out checks against r8brft1; netcheck on a B0
build. **All ten passed.**

| net | S matched | quant. loss max / p99 (cp) | endgame check, of 900 (r8brft1 7) | held-out 4-5, of 3,800 (r8brft1 612) | held-out 6-7, of 5,599 (r8brft1 770) |
|---|---|---|---|---|---|
| ld-d20-s1 | 91 | 9.1 / 7.3 | 39 | 436 | 963 |
| ld-d20-s2 | 92 | 10.1 / 9.2 | 22 | 474 | 942 |
| ld-d50-s1 | 87 | 7.7 / 6.8 | 28 | 530 | 1,026 |
| ld-d50-s2 | 88 | 7.7 / 6.6 | 53 | 415 | 1,022 |
| ld-d100-s1 | 92 | 6.9 / 5.9 | 116 | 551 | 1,121 |
| ld-d100-s2 | 91 | 8.0 / 6.3 | 98 | 532 | 1,120 |
| ld-c50-s1 | 91 | 9.0 / 5.9 | 28 | 403 | 958 |
| ld-c50-s2 | 90 | 10.8 / 8.9 | 52 | 440 | 989 |
| ld-c100-s1 | 93 | 9.5 / 8.3 | 73 | 527 | 1,022 |
| ld-c100-s2 | 94 | 12.1 / 10.4 | 70 | 514 | 991 |

Every B0 is flagged on the 6-7-piece check against r8brft1 (ratio above 1.15). That is expected of a small net and is
reported, not gated. On the 4-5-piece set most B0s misjudge fewer positions than r8brft1.

## 5. Bakes

Each net is the default network of its own branch, bake/ld-<arm>-s<seed> (net file nets/ld<arm>s<seed>.fnet: the
Control Center reads the default net's name as [a-z0-9_]+). All bakes share the same engine code: phase-4 b5c4c14
(r8brft1 default; bench 8,773,005 / 413d5ae2f1af08de), with E4's minor drift table and D8 adopted. bake/ld-d20-s1 is on b5c4c14
itself. The others are on a21f049, which is b5c4c14 plus a tests-only fix: go mate 2's depth check became a bound,
3 to 5, after ld-d20-s2's net stopped at depth 4 with the right mate and the pre-commit hook blocked its bake
(coordinator's decision). The engine binaries are identical in code. Bench per branch below (each branch's tests/bench-ld*.ref). bake/ld-d20-s1's commit message and nets.md row print the kernel's
validation-run mapping instead of the run's name (run.json's val_run key is overwritten by the settings dict); the
branch is left as is, a cosmetic slip only.

| branch | commit | base | bench (nodes / signature) |
|---|---|---|---|
| bake/ld-d20-s1 | e72ad2d | b5c4c14 | 9,102,623 / 2e06eab03997aa80 |
| bake/ld-d20-s2 | b2e8d2a | a21f049 | 9,682,160 / 64dd8b49aeb59ccc |
| bake/ld-d50-s1 | 4213c62 | a21f049 | 12,155,891 / 8db081cc69cff156 |
| bake/ld-d50-s2 | c38add2 | a21f049 | 12,281,497 / e053d9c7fe1562a7 |
| bake/ld-d100-s1 | b38de90 | a21f049 | 10,227,026 / 1ba6a3df14da13c0 |
| bake/ld-d100-s2 | 82a7e9c | a21f049 | 9,521,598 / 6d506f6f5e69ec05 |
| bake/ld-c50-s1 | 17ca3a5 | a21f049 | 10,100,556 / 46f76592e70b0bee |
| bake/ld-c100-s1 | 3316c5c | a21f049 | 10,369,915 / de595850b9cc2256 |

ld-c50-s2 and ld-c100-s2 passed their gates but are not baked: ld.sh uses only the controls' seed 1.

state/ld-ready.json (the night queue's ld.sh format, written 2026-11-12 10:50 AM EST) names each of the eight branches' commits: d20, d50 and d100
for both seeds, and the controls' seed 1.
