# Retrain 8c: the plan (decided by the owner on 2026-11-12, about 4:05 PM EST; section 10)

Written 2026-11-12, about 3:30-4:30 PM EST, from the owner's order of about 3:20 PM EST: "Plan retrain 8c for
launch after g4c seals (~Friday): (1) snapshot = all generation data since 8b (g4b, g4c, VM filler), the
label-depth arms (all usable), the positional slice (within the 5% cap), and the fresh endgame slice; (2) rank the
candidate arms by expected value and GPU cost within this week's 30 GPU-hours (two seeds each): control first, then
idea 80, the positional slice, the slice-preserving fine-tune, per-class lambda, slice v2 (if generated in time),
regularization; (3) report the plan, the arm order and GPU estimates before launching."

Sources read: retrain/8b-prep docs/research/retrain-8b/plan.md; retrain/8b-rft rft-plan.md; docs/nets.md
(r8btd90, r8brft1); DESIGN.md decisions log (2026-11-09 to 2026-11-12 rows on 8c, the 5% cap, slice v2, the
overlap audit, ideas 80/85, the split-search re-check), item 8's status row, §5.3 labeller policy; ideas.md 48, 59
(follow-up plan item 3), 62, 66, 68, 69, 70, 71, 80, 85; research/label-depth results.md and the labels-teacher
design §1.5; data/manifests g4, g4b, ld-*; docs/research/endgame-slice-v2/design.md; the bug-review follow-up (T1);
HANDOFF.md's 8c item list (43-49); MORNING.md; the training-data memory. Measured now: `kaggle quota` (3:24 PM EST)
and WSL ~/fork-data/gen4c/g4c.log (3:27 PM EST); the positional slice's done.json.

## 0. Facts that shape the plan (each checked today)

1. **The quota resets Friday 11-13 at 7:00 PM EST, not Saturday 7 PM.** `kaggle quota` at 3:24 PM EST: GPU 14.30 h
   used, **15.70 h remaining** of 30, `refreshAt 2026-11-14T00:00:00+00:00` = Saturday 00:00 UTC = **Friday 11-13,
   7:00 PM EST**. "This week's 30 GPU-hours" is therefore read as **the quota week Fri 11-13 7:00 PM to Fri 11-20
   7:00 PM EST**. 8c launches after g4c's seal (Friday afternoon/evening), so all 30 h of that week are available;
   the current 15.70 h expire unused at 7:00 PM Friday unless something g4c-independent runs before then (§7).
2. **The quota is charged at session wall time, not per GPU** (strong evidence, not proven on one reading): 8b's
   five 360-superbatch runs on T4 x2 cost 27.04 - 20.92 = **6.12 quota-h** (6:39 AM to 12:48 PM EST, 2026-11-10),
   where per-GPU charging would have been about 11-13 h; the cw + c2 session (two runs side by side) cost about
   2.7 h. So two seeds side by side (one per GPU) cost about one run's wall time. Every estimate below gives both
   figures; the plan's cut line holds under the worse one where it says so.
3. **One 8b-size run:** 360 superbatches of 305 x 16,384 = 1.80 B positions took **7,860.8 s = 2.18 h** on one T4
   with two runs side by side (8b arm c, 21.84 s per superbatch). A 60-superbatch fine-tune: about **0.36 h**
   (rft-plan §4, from the same rate). Session setup (hashing inputs, build) and the offline averaging: about 0.5 h
   per session (8b's estimate, UNVERIFIED for 8c's larger file set). Kaggle's session limit: 12 h.
4. **g4c's seal: about 11 AM to 2 PM Friday for the target, then the seal itself.** g4c.log at 3:27 PM EST:
   64,137,078 positions at 30,120 s of its clock (MORNING.md: started about 7:22 AM EST); run average 2,129 positions/s, the last hour
   2,420-2,495/s. The 165.4 M left take 18.8 h at 2,450/s (about 10:15 AM Fri) to 21.6 h at 2,129/s (about
   1:05 PM Fri), **plus about 1 h** for speed sprint 3's suspension: **target reached about 11 AM-2 PM Friday**.
   The seal's game verification took about 1 h for g4b (46.5 M) and about 2 h for ld-d20 (104.6 M), so g4c's
   229.5 M takes **about 2-4 h (UNVERIFIED)**: sealed **about 2-5 PM Friday**.
5. **"Slice-preserving" needs a definition (owner decision O1).** r8brft1's fine-tune already read the Syzygy slice
   unchanged at its normal share: nets.md's r8brft1 row and rft-plan §2 ("arm c's 129 training files ... the Syzygy
   slice included ... the slice's target stays its WDL (its score and result agree)"). At result weight 1.0 a slice
   record's target is its WDL either way. So the arm as worded is r8brft1's own recipe; what rose (4-5 pieces
   526 -> 612 of 3,800; 6-7 pieces 732 -> 770 of 5,599) are endings the slice does not contain. §3 proposes a
   definition that targets them.
6. **The fresh endgame slice does not exist yet; slice v2 does not exist yet.** No `slice2-*` file and no
   regenerated Syzygy slice on this machine or in WSL (bug-review follow-up; WSL ~/fork-data listing today).
   "The fresh endgame slice" is read as HANDOFF item 49: **v1's Syzygy 3-5-piece slice regenerated with new seeds
   under the zero-overlap rule** (the 900-position check's positions and every held-out set excluded), replacing
   v1 by the cap rule's "newer slices of a kind replace older ones" (owner decision O2). `endgame_slice.py generate`
   has no `--exclude` today (heldout_67.py has one); its generation rate is not recorded in anything read
   (UNVERIFIED; a rate probe first). Slice v2: designed, prober installed and verified (2026-11-11), shares set,
   KQvKRBP materials added, held-out 6-7 positions to be excluded; **its tooling (design §10) is not built and its
   rate probe has not run**; the design's 7 h generation figure assumes 500 positions/s per worker (UNVERIFIED).
7. **The positional slice exists:** WSL ~/fork-data/gcp/slice-pos-td90: 12,500,535 positions in 128,245 complete
   games, **0 unsaved** (every record searched at 80,000 nodes), labelled by r8btd90 (bench 9,594,307 /
   4eb36793548711d4 in done.json), verified (8 shards; ends: 71,645 mate score, 31,891 table, 12,596 rules draw,
   12,113 score adjudication), finished 2:10 PM EST 2026-11-11. Not yet sealed as a manifest or uploaded (as far as
   the files show; UNVERIFIED).
8. **Idea 52 is retired** (owner, 2026-11-11), so 8b's from-scratch committee run lapses: no `scr` arm in 8c
   (saves 2.2 h).

## 1. The snapshot g4s2

Naming as before (g3s1, g3s2, g3s3, g4s1): **g4s2** = g4s1 unchanged + every part sealed since + the slices.
"Saved" counts the records the trainer can keep (positions minus unsaved); "kept" is after the trainer's filter
(about 0.645 of saved on g3j's pool, 8b plan §1, UNVERIFIED for the new parts).

| Part | Records | Saved | Labeller (engine) | Status / source | In 8c |
|---|---|---|---|---|---|
| g4s1 (8b arm c's 129 files, incl. v1 slice 26.0 M) | about 2.40 B | 1,475,055,053 (incl. 25,999,940 slice) | B0r2 ... S512ppr3 | on Kaggle (16 datasets) | yes; v1 slice files replaced by the fresh slice (O2) |
| g4b | 46,524,651 | 25,288,058 | S512ppr3 (2f38fe8) | data/manifests/g4b.json | yes |
| ld-d20 | 104,619,213 | 56,868,241 | S512ppr3 (a4ee674), 20k nodes | ld-d20.json; Kaggle fork-ld-d20 | yes |
| ld-d50 | 45,908,474 | 24,897,587 | S512ppr3, 50k nodes | ld-d50.json; fork-ld-d50 | yes |
| ld-d100 | 23,439,070 | 12,685,505 | S512ppr3, 100k nodes | ld-d100.json; fork-ld-d100 | yes |
| ld-d20c50, ld-d20c100 | 46.1 M, 23.6 M | - | (cuts of ld-d20) | volume controls | **no**: each is ld-d20's first games per file, so including them duplicates about 70 M records |
| g4c | 229.5 M at target | about 124.8 M (g4/g4b's 45.6% unsaved share; UNVERIFIED until the seal) | r8brft1 (75d53f0: ProbCut + E1 + B13) | running; seal about 2-5 PM Fri | yes |
| VM filler g4-gcp-20261111T191107Z | 27.3 M | about 14.8 M | r8brft1 (b5f11ae; per the 11-11 memory, UNVERIFIED here) | VM ~/opt/fork/out/filler | yes, as its own part |
| VM filler g4-gcp-20261112T041330Z | 33.6 M | about 18.3 M | r8brft1 (b5f11ae) | VM | yes, own part |
| VM filler, 75d53f0 run | about 90 M by Fri noon (about 4 M records/h, measured 11-11 night; UNVERIFIED: the VM was lent to the staleness audit until about 1:50 PM today; **fresh count at the cut**) | about 50 M | r8brft1 (75d53f0) | running | yes: cut at a game boundary at g4c's seal and sealed as its own part (coordinator's action) |
| positional slice slice-pos-td90 | 12,500,535 | 12,500,535 | r8btd90 at 80k nodes | WSL ~/fork-data/gcp/slice-pos-td90 | **arm data** (pos arm, §3); targeted |
| fresh endgame slice (v1 regenerated, zero overlap) | 25,999,940 (v1's count) | the same | Syzygy WDL | **to generate** | every arm, replacing v1 (O2); targeted |
| slice v2 (ChessTB 6-7) | 13 M in the v2 arm (half of 26 M; owner 2026-11-09 (c)) | the same | ChessTB WDL | **to generate** | v2 arm only (session B) |

**Totals (estimates):** new self-play saved about **327.7 M** (g4b 25.3 + ld 94.5 + g4c 124.8 + filler about
83.1), kept about 211 M: **the cadence rule's 150 M new kept positions is met** (g4c + filler alone, r8brft1's
labels, are about 133 M kept; with g4b and ld, S512ppr3's, about 211 M). g4s2 holds about **1.80 B saved
(control)**, about 1.17 B kept; 360 superbatches = about **1.53 passes** (8b: 1.9).

**Targeted share against the 5% cap** (saved basis, as 8b's plan counted the slice; kept basis beside it):
control: fresh slice 26.0 M = **1.44%**; pos arm: + 12.5 M = **2.12%** (kept basis about 2.9%, the slices'
records being nearly all kept); v2 arm: 13 M v1-fresh + 13 M v2 (+ 12.5 M pos only if pos has won) = 1.44-2.12%.
Every arm is under 5%; headroom about 2.9 points (about 50 M positions) for later targeted data (for example idea
59's near-window oversampling, 8d).

**Labellers (DESIGN §5.3):** parts are never merged; each new part's manifest names its labeller and engine; the
two b5f11ae filler runs and the 75d53f0 run are separate parts (different engines, same net). Training mixes
labellers by part as every snapshot since g3s2 has (B0r2 ... S512ppr3, and now r8btd90's positional slice and
r8brft1's g4c/filler). No new mixing rule is introduced.

**Labels (standard recipe since 8b: TD(0.9) stays; result weight 0 with label copies, as r8btd90):** TD(0.9) copies
(td_labels.py `labels`, lambda 0.9, S = 92) of every part labelled by S512ppr3 or later: g3j and g4 (8b's copies,
on Kaggle), and new copies of g4b, ld-d20/d50/d100, g4c, the three filler parts and the positional slice (complete
games, so TD applies); blend copies of every older file (8b's bl- copies, on Kaggle); the endgame slices unchanged
(their score already says the WDL). Owner decision O5 (TD scope): this 8b form (recommended) or TD on all parts.

**How the label-depth data are treated (O3).** d20, d50 and d100 go into every arm as ordinary S512ppr3 parts at
their stored labels (TD(0.9) copies like the other S512ppr3 parts), with no extra weight; c50/c100 stay out.
Screen 1's -53.85 +/- 11.36 (B0 d50-s1 against d20-s1 at 800k nodes) compares two small from-scratch nets where d50
had 44% of d20's positions; results.md shows D50's validation loss on D20's held-out file at its volume control's
level (0.02408/0.02377 against c50's 0.02438/0.02411), so nothing so far says a deeper label hurts per position.
Inside 8c the deeper parts are 37.6 M of 1.80 B saved (2.1%), so they cannot move the comparison either way, and
they are equal in every arm. Whether 50k becomes the generation setting is idea 62's decision (its pooled screens
and the c50 control, item f), not 8c's. Check before use: the three arms share their seeds (layout A), so the
overlap tool (tools/overlap) counts identical games across d20/d50/d100 and g4b/g4c; identical games are dropped
from all but one part (expected few: the searches differ from the first saved move).

**Validation g4s2-val** (diagnostic only, decides nothing): g4s1-val's 2,160 games + 60 held games of each new
self-play part (g4b, g4c, the three filler parts; for ld-* the first 60 games of each arm's own -w02-val file), by
`snapshot_parts.py hold`, merged one game at a time; its blend copy bl-g4s2-val for the weight-0 arms; the overlap
audit's optional step (drop the validation positions found in training) applied if the owner agrees (O10). H and H2
stay out of training as in 8b.

**Zero-overlap rule (blocking before launch):** tools/overlap's check of every new training file (g4b, g4c, filler,
ld, pos, the fresh slice, v2) against endgame_heldout.tsv, heldout_67.tsv and heldout_deep.tsv, as the overlap
audit ran it for 8b's files.

## 2. Arm table (two seeds each; 360 superbatches; the standard recipe unless stated)

**Common to every 360-superbatch arm:** warm start from **r8brft1's float weights** (the default's, as the standard
recipe says; O4: or r8btd90's, the last TD-trained base), LR 1e-4 dropped tenfold after superbatch 180, AdamW,
batch 305 x 16,384, S = 92, **result weight 0 on label copies** (as td90), seeds 1 and 2, candidate = the window
average (superbatches 331-360) quantised by the trainer; best, 180 and 360 checkpoints kept. Equal positions: every
arm sees exactly 1,798,963,200.

| # | Arm | Definition | What it tests | Expected value and evidence | GPU-h per seed | 2 seeds: wall / per-GPU | Dependencies |
|---|---|---|---|---|---|---|---|
| 1 | **c**, control | g4s2 as §1: TD(0.9) copies of S512ppr3+ parts, blend copies of older, fresh slice | the new data (+22% saved, r8brft1's labels) under 8b's winning recipe; the baseline for every keep rule | baseline. Past data rounds: 8a +7.12 STC over its base; 8b's control +13.03 FN vs S512ppr3, td90 +17.39 FN / +12.17 STC. Here un-fine-tuned against a fine-tuned default, so its own screen against r8brft1 may be near 0 | 2.18 | 2.18 / 4.37 | g4c sealed and copied; fresh slice (else v1 kept, O2) |
| 2 | **i80**, idea 80 | c's files, but every TD-labelled part (S512ppr3+) read as a copy where the **unsaved records also carry a TD(0.9) label** (variant A: the lambda-return through the next saved records, td_labels.py's `next` chain; positions in check stay out) | whether the 45.6% of records the split search discards add value at equal steps: the pool grows by about 400 M records (about 258 M kept, about +22%) | owner's kill: h2h vs c at or below 0 on both seeds. No direct evidence yet; **high decision value**: with idea 62 it sets the next save share and node budgets (owner, 2026-11-12 1:30 PM) | 2.18 | 2.18 / 4.37 | **tool change**: td_labels.py writes labels for unsaved records (new option + `check` coverage); copies of g3j, g4 (from Kaggle if local shards were deleted), g4b, ld, filler, g4c |
| 3 | **pos**, positional slice | c + slice-pos-td90 (TD(0.9) copy), with 12.5 M saved self-play positions removed by whole games evenly from every self-play file (unsaved marker, as 8b's i52 arm), so totals stay equal | fix 1 of the conversion-and-defense analysis: queens-on, equal-piece positions with an advantage, played out with raised adjudication | pilot's offline gate +0.030 [+0.021, +0.040] (research/defense-slices 5e42e4a); cap rule: must win its arm test to stay (keep rule O6) | 2.18 | 2.18 / 4.37 | seal + manifest + upload of slice-pos-td90; removal copies |
| 4 | **ft**, the fine-tune trio (on c's window averages; 60 superbatches each, LR constant, window = superbatches 46-60) | **rft**: r8brft1's recipe (result weight 1.0 on the originals, LR 1e-5); **rft-ep**: the slice-preserving form proposed in O1: result target only on records with **8 or more pieces**, the base's own target (TD(0.9)/blend copy) kept on records with **7 or fewer**, the slices at their WDL, LR 1e-5; **rft-ep-lo**: rft-ep at **LR 5e-6** (the lower-LR variant; half, a placeholder for the constant screen) | whether the fine-tune's +5.74 STC can be kept without the held-out endgame regression | evidence for the problem: 4-5 pieces 526 -> 612, 6-7 pieces 732 -> 770 (58 to 20 discordant) after r8brft1's fine-tune; r8brft1 +5.74 +/- 3.81 STC. **Cheapest arms per decision** | 0.36 each | 3 pairs: 1.09 / 2.18 | c finished (same session, chained); rft-ep copies (piece-count mask of the td90/bl copies: CPU over about 2.4 B records) |
| 5 | **lam**, idea 85 | c's files with the TD copies relabelled at a **per-record lambda**: 0.35 for queens-on middlegames (a queen on, phase >= 13), 0.65 for endgames (no queen, phase <= 9), 0.9 for the rest, with the class definitions exactly as label_probes.py `tdclass` (tools/probes-1111) | idea 85: a class-matched TD horizon at the same games and steps as c | probe passed (0.35/0.65 against the 1M golds, kill line 0.05). **Against it:** the same yardstick picks 0.40 overall while TD(0.9) won in games, and 8b's td80 (0.8 everywhere) screened -1.09 against td90's +17.39 (both vs S512ppr3); this arm puts about 83% of the probe's records below 0.8. **Low expected value** (risk flagged, O8) | 2.18 | 2.18 / 4.37 | **tool change**: per-ply lambda in td_labels.py (the backward recursion takes lambda_t by record t's class) + test |
| 6 | **v2**, endgame slice v2 | c with its slice half fresh-v1 (13 M) and half v2 (13 M), equal totals (owner 2026-11-09 (c)) | 6-7-piece ChessTB labels in the classes Fork errs most, KQvKRBP and kin included | declared keep rule (2026-11-09): FN screen interval not entirely below 0 AND held-out 6-7 misjudgments down 25% vs c. TCEC's 7-man tables cover part of any gain (design §2) | 2.18 | 2.18 / 4.37 | **v2 generated in time**: tooling (design §10), name/constant screens, rate probe, generation (7 h at 1,000/s assumed, UNVERIFIED), verification, upload; CPU beside g4c |
| 7 | **wd**, regularisation (idea 71) | c with weight decay on the feature transformer's weights only | Stockfish's recent trainer change at concept level | external report +4.0 STC / +5.3 LTC in another engine (concept only); uncertain transfer; **the decay coefficient is a new constant** (justification + constant screen before use) | 2.18 | 2.18 / 4.37 | **trainer change** + a Kaggle preflight (all-zero decay reproduces c; speed within 1%) |
| - | (reserve) **c+X** combination | c with every arm that passes its keep rule, if two or more pass (they are tested one at a time against c) | whether passing arms stack | stacking evidence (search): about 0.5-0.6 of the sum | 2.18 | 2.18 / 4.37 | session B |
| - | (reserve) J6 activation / FT-output regularisation; old-data down-weighting (HANDOFF 47-48) | own arms | | no evidence yet | 2.18 each | 2.18 / 4.37 each | trainer changes |
| - | **not ready for 8c's launch**: idea 48 closeness-weighted training; idea 59 item 3 near-window oversampling | closeness needs a per-record distance to the window (no such field; an offline search or a datagen field, costed first) and per-position loss weights (cw's trainer path, merge only with the owner's OK); oversampling "in data generation" cannot apply to g4c, which is already running at the standing settings | | owner (1:20 PM): two seeds "if the quota allows" | - | - | 8d, or session B only if both are built and preflighted |

## 3. The slice-preserving fine-tune, defined (O1)

Proposed declaration (before any result): **rft-ep** ("endgame-preserving") = the result fine-tune with its target
split by piece count: records with **8 or more pieces** get the game result (r8brft1's target), records with **7 or
fewer** keep the base's own target (the TD(0.9) or blend copy's score), and the endgame slices keep their WDL. Built
with no trainer change, as the TD arms were: a copy of each td90-/bl- file in which every keepable score of a record
with 8 or more pieces is replaced by the result's code (+2,000 / 0 / -2,000, the slice's own convention, whose
sigmoid at S = 92 is the result within 1e-9), run at result weight 0. Why 7: the two regressions are at 4-5 and 6-7
pieces (the held-out sets), and 7 is TCEC's table limit. Alternatives for the owner: (b) the slice oversampled
during the fine-tune (it would not reach the 4-5-piece classes the slice cannot generate, nor 6-7); (c) a fine-tune
at result weight below 1.0 (a new constant). **rft-ep-lo** = rft-ep at LR 5e-6 (half of 1e-5; to be screened as a
constant; a natural factor). The plain **rft** runs beside them on the same base, so each comparison is like for
like. Both "7 or fewer" and "5e-6" are new values: recorded with this reasoning and sent to the constant screen
before use.

## 4. Order, GPU hours and the cut line

**The owner's order** (control, idea 80, positional slice, slice-preserving fine-tune, per-class lambda, slice v2,
regularisation) is kept as the priority order. Two scheduling changes, not priority changes: the fine-tune trio
runs **right after c in the same session** (it starts from c's window averages and costs 0.36 h a pair), and slice
v2 and regularisation go to a later session because neither can be ready by Friday evening.

| Session | When (EST) | Contents (seed 1 on GPU 0, seed 2 on GPU 1) | Wall quota-h | If per-GPU |
|---|---|---|---|---|
| A1 | Fri 11-13 about 8-10 PM, after the 7 PM reset and the owner's go | setup 0.5; **c** 2.18; **rft, rft-ep, rft-ep-lo** 1.09; **i80** 2.18 | **5.95** | 11.4 |
| A2 | right after A1 (Sat about 3-4 AM to 8-9 AM) | setup 0.5; **pos** 2.18; **lam** 2.18 | **4.86** | 9.2 |
| B | Mon 11-16 to Wed 11-18, when ready | setup 0.5; **v2** 2.18 (if generated); **wd** 2.18 (if built); the chosen fine-tune on the winning base 0.36 (only if the winner is not c) | **5.2** | 9.9 |
| Reserve | by Fri 11-20 7 PM | combination arm c+X 2.18 + its fine-tune 0.36; J6 or old-data down-weighting 2.18 each; a third seed for a close call 1.1-2.2 | up to about 14 | - |
| **Total planned** | | ranks 1-7 | **about 16.0 of 30** | **about 30.5** |

**Cut line.** At wall-time charging (the evidence of fact 2), **all seven ordered arms fit with about 14 h to
spare**; the reserve funds a combination arm and one more arm. If A1's quota reading shows per-GPU charging, A1 + A2
cost about 20.6 h and session B must shrink to about 9.4 h: **v2 stays, regularisation (wd) moves to the next
week** (cut line after slice v2). The quota reading before and after A1 (`kaggle quota`) decides which case holds;
nothing else in the plan depends on it. A1 alone (about 6 h) answers the three highest-value questions (the new
data, idea 80, the fine-tune recipe) even if everything later slips. Splitting A into A1/A2 costs one extra setup
(about 0.5 h) and keeps each session well under Kaggle's 12-hour limit; one combined session would be about 10.3 h
(possible, with less margin for a slower 8c file set).

## 5. Evaluation (declared before any result)

1. **Integrity gates, blocking, per candidate** (8b's): every input matches its manifest; r8brft1's weights
   reproduce their prefix loss on g4s2-val's blend copy; each arm's superbatch 0 equals that within 1e-6 (1e-5 on
   label copies); exit 0; window complete and quantised unchanged; the scale matched to r8brft1's mean |eval| on
   4,000 g4s2-val positions; the parity chain (trainer leg, netcheck exact on 446, quantisation loss within 21 / 16
   cp); tools/nnue/gates.sh on the clamped net (T2).
2. **Endgame reports, every candidate, never a gate** (owner 2026-11-11): the 900-position check (now **a held-out
   check** if the fresh slice excludes its positions; its earlier figures, 7-8 of 900, were recall, so 8c's numbers
   are not comparable with them and the 15-of-900 target needs re-reading, O2); **the 4-5-piece held-out check**
   (endgame_heldout.py, 3,800; r8brft1 612) and **the 6-7-piece check** (heldout_67.py, 5,599; r8brft1 770), both
   flagged above **1.15 times** the default's count (cursed wins and blessed losses drawn; 200 per material); the
   8-12-piece deep check (heldout_deep.py, 1,337 classed; r8brft1 80) beside them. Paired discordant counts against
   c for every arm (as 732 vs 770 was read).
3. **Fixed-node screens** (1,600 games at 800,000 nodes, one GitHub stage each, all competing candidates first;
   seed-paired and pooled to 3,200 games per arm, because c2 against c measured -6.08 +/- 9.42 of seed noise):
   - base arms against c: i80-sK vs c-sK, pos-sK vs c-sK, lam-sK vs c-sK (K = 1, 2): 6 stages; v2 and wd: 4 more;
   - fine-tunes: rft-ep vs rft (2 stages), and rft-ep-lo vs rft-ep (2 stages, run only if rft-ep's held-out counts
     improved but its screen did not, so that the stage can change the decision);
   - the final candidate (the best base with the chosen fine-tune) against **r8brft1**: 2 stages (one per seed).
   About 12-16 stages in the first wave; validation loss decides nothing.
4. **Keep rules** (owner's where given; proposed where not, O6):
   - idea 80: **killed if its head-to-head against c is at or below 0 on both seeds** (owner); kept as the data
     setting's input otherwise, adopted into the recipe at +5 pooled or a passing STC SPRT;
   - positional slice: stays in the standard snapshot only if it **wins its arm test** (cap rule); proposed bar:
     pooled h2h of +5 or more vs c, or a passing STC SPRT (idea 69's bar), and no held-out check worse by more
     than 1.15x;
   - per-class lambda: proposed in idea 51's form: kept only if the pooled h2h vs c is above +4 and no held-out
     check is worse;
   - slice v2: as declared 2026-11-09 (FN interval not entirely below 0 AND held-out 6-7 down 25% vs c);
   - fine-tune: rft-ep replaces rft as the standard fine-tune if its held-out 4-5 and 6-7 counts are both below
     rft's (paired) and its h2h vs rft is not entirely below 0; rft-ep-lo replaces rft-ep under the same rule;
   - wd: +5 pooled h2h or a passing STC SPRT.
5. **Promotion:** the final candidate's better seed (higher FN screen against r8brft1) goes to the **STC SPRT,
   `--kind network`, [0, 5] Elo, alpha = beta = 0.05**, against r8brft1; if it fails, the other seed only if its
   screen was +5 or more; at most two SPRTs. An H1 goes to the owner for promotion (then the labeller policy's part
   switch). Every run carries `--idea` and its try count; results go in the SPRT log.

## 6. Preparation and timeline (EST; plan only, nothing started)

| When | What | Lane / where |
|---|---|---|
| Thu 11-12 evening - Fri morning | tool changes with tests: td_labels.py unsaved labelling (i80), per-record lambda (lam), the piece-count mask (rft-ep); `endgame_slice.py generate --exclude` and new seeds for the fresh slice; the 8c kernel (8b's retrain kernel + the rft chain after c); name screen (new option and file names) and constant screen (7 pieces, 5e-6, the new seeds' none) | builders; screens by a separate research agent |
| Thu night - Fri | pre-seal copies: TD(0.9), i80 and lam copies of g4b, ld-d20/d50/d100, the two finished filler runs, the positional slice; i80/lam copies of g3j and g4 (download from Kaggle if deleted locally); rft-ep masks of the td90/bl files (the largest job: about 2.4 B records; 8b's 103 blend copies took about 6 h under load); fresh slice rate probe, then generation; overlap checks; g4s2-val pre-part | slice lane, one heavy job at a time, below g4c's priority; the cloud VM can take the Kaggle-sourced copies |
| Fri before 7 PM | **optional, on the expiring 15.70 h** (§7): the 8c kernel's preflight on the pre-seal inputs | Kaggle (owner's go) |
| Fri about 11 AM-2 PM | g4c reaches 229.5 M; the 75d53f0 filler run cut at a game boundary at the same time and sealed (coordinator) | WSL, VM |
| Fri about 2-5 PM | g4c sealed (about 2-4 h of verification, UNVERIFIED) | WSL |
| Fri about 4-8 PM | post-seal: g4c's TD/i80/lam/mask copies (8b's g4 copies took about 25 min for 64 M records, so about 1.5 h), its 60 validation games, overlap check, upload (about 1 GB per variant) with download-back hashing; manifests committed; kernel COMMIT set | slice, upload |
| Fri 7 PM | quota reset (30 h) | |
| **Fri about 8-10 PM** | **A1 pushed after the owner's approval** (about 6 h wall) | Kaggle |
| Sat about 3-4 AM | A2 (about 5 h) | Kaggle |
| Sat morning | gates and all held-out checks for c, the fine-tune trio and i80; bakes; the first screens (A1's) | local, GitHub |
| Sat-Sun | A2's gates and screens; the final candidate's FN screens | GitHub |
| Sun-Mon | the STC SPRT (up to 13 stages) | GitHub |
| Mon-Wed | session B (v2 if generated, wd if built, the fine-tune on a non-c winner, a combination arm if two arms passed) | Kaggle |
| by Fri 11-20 7 PM | everything inside this quota week | |

## 7. This week's remaining 15.70 h (expire Fri 7 PM EST)

8c's arms cannot use them (they need g4c). Two g4c-independent uses, for the owner (O7):
- **P1, the 8c kernel preflight on the pre-seal inputs (about 0.5 h; recommended):** mounts every dataset (8c needs
  about 25 data sources against 8b's 16 and rft's 17; Kaggle's limit is UNVERIFIED, so this also tests it),
  checks inputs, reproduces r8brft1's superbatch-0 loss, measures the speed with the larger file set (the 2.18 h
  figure), and confirms the trainer keeps the i80 copies' newly labelled unsaved records. A failure found Thursday
  night costs nothing; found Friday night it delays the launch.
- **P2, the fine-tune question on 8b's base, now (about 0.7-1.1 h):** of the trio, only a lower-LR form of the
  plain fine-tune needs no new data: r8btd90, g4s1, LR 5e-6, seeds 1-2, on inputs already on Kaggle
  (fork-r8b-rft-init) and compares directly with r8brft1 and r8brft2 (same base, data and seeds). rft-ep on 8b's
  base needs the mask copies first (about 6 h of CPU; tight before 7 PM Fri). Value: the fine-tune recipe is known
  a week sooner and on quota that otherwise expires; 8c's A1 then runs only the chosen fine-tune (saves about
  0.7 h). The owner's order names the fine-tune as an 8c arm, so this is an option, not the plan.

## 8. Risks

1. **Quota accounting** (fact 2): per-GPU charging would cut regularisation; A1's before/after reading settles it.
2. **Kaggle data-source count** (UNVERIFIED limit; about 25 needed): consolidate the new small parts (g4b, filler,
   ld copies, slices) into two or three datasets; P1 tests it.
3. **g4c's seal slips** (speed sprint pause, seal verification time, the Friday CPU load): A1 waits; nothing else
   moves. If g4c seals after about 10 PM Friday, A1 launches Saturday morning; A2 follows the same day.
4. **CPU contention:** the copies (about 0.9 B records per label variant, plus the 2.4 B-record mask job), the fresh
   slice and slice v2 compete with g4c's 10 threads and the local queue; "one heavy job at a time" orders them; the
   cloud VM can do the Kaggle-sourced copies. The mask job is the long pole; if it cannot finish, rft-ep moves to
   session B (A1 still runs rft and, if P2 did not, the plain rft at 5e-6).
5. **Per-class lambda's expected value is low** (td80's -18 Elo gap to td90 in 8b), and it costs 2.18 h; kept in the
   owner's order, flagged.
6. **The fresh slice changes the 900-check's meaning** (recall to held-out): 8c's counts there will rise against
   past nets' 7-8 by construction; read the 4-5 and 6-7 held-out sets for comparisons with r8brft1.
7. **Shared seeds in the label-depth arms:** identical games are counted and dropped before use.
8. **The control competes un-fine-tuned against a fine-tuned default:** the base arms are compared against c, and
   only the fine-tuned final candidate plays r8brft1.
9. **Fewer passes** (1.53 against 8b's 1.9; i80 about 1.25 over its larger pool): a recipe change by data growth,
   equal in every arm except i80, where it is the point of the test.
10. **Seed noise** of about +/-6 Elo between seeds: every keep rule reads pooled seed pairs.

## 9. Open owner decisions

- **O1** The slice-preserving fine-tune's definition: rft-ep (piece-count split at 7, recommended) or (b)/(c) of §3;
  the lower LR 5e-6 (half). Both new values go to the constant screen.
- **O2** "The fresh endgame slice" = v1 regenerated with new seeds and every held-out position (the 900 check's
  included) excluded, replacing v1 in every arm without its own arm test (recommended: same generator, size and
  kind); the 15-of-900 acceptance target re-read as a held-out figure.
- **O3** The label-depth data: d20, d50 and d100 in every arm as ordinary S512ppr3 parts at TD(0.9), c50/c100 out,
  identical games dropped (recommended; screen 1's -53.85 is a volume effect on small nets and does not bear on
  mixing; idea 62 keeps the setting decision).
- **O4** Warm start: r8brft1's float weights (the recipe's "the default", recommended) or r8btd90's.
- **O5** TD scope: TD(0.9) on S512ppr3-and-later parts, blend on older (8b's form, recommended), or on all parts.
- **O6** Keep rules not yet declared: the positional slice (+5 pooled h2h or STC pass), per-class lambda (above +4),
  the fine-tune variants (held-out counts down and h2h not below 0), wd (+5 or STC pass).
- **O7** Use of the expiring 15.70 h: P1 (recommended), P2 (option).
- **O8** Per-class lambda: run as declared (0.35 / 0.65 / 0.9), or a variant whose record-weighted mean stays near
  0.9 (keeps the probe's contrast without td80's shift); as declared is the default of this plan.
- **O9** The filler cut: the 75d53f0 run cut at a game boundary at g4c's seal and sealed as its own part (needs the
  coordinator's VM action; "no cuts touching production" applied to this plan, so it is not done here).
- **O10** Validation: drop the validation positions found in training (the overlap audit's optional step).
- Not decided here: whether idea 48 / idea 59 item 3 get 8c arms in the reserve (neither can be built and
  preflighted before session B at the earliest; near-window oversampling cannot apply to g4c's data at all).

## 10. The owner's decisions (2026-11-12, about 4:05 PM EST) and their execution

Verbatim: "O1 rft-ep definition approved (result targets for >= 8 pieces, base targets for <= 7) plus the 5e-6 LR
variant; O3 label-depth data in every arm; O4 warm start from r8btd90, with the rft-ep fine-tune applied after; O7
use the expiring 15.7 h for P1 (preflight of the 25-source setup) and P2 (lower-LR fine-tune now); O9 cut the VM
filler run at g4c's seal, then start a new run. Other plan decisions: as recommended in the plan. Confirm idea 80's
TD labels for the unsaved positions are computed for all included parts before launch."

So: O2 the fresh slice replaces v1 (v1 kept if it is not ready); O5 TD(0.9) on S512ppr3-and-later parts, blend copies
of the older; O6 the keep rules of section 5.4 as proposed; O8 per-class lambda as declared; O10 the validation
positions found in training dropped.

**The new values and their reasons** (constant screen by the coordinator's originality agent, 2026-11-12: no match
in Stockfish, nnue-pytorch, Ethereal, Berserk, Weiss or bullet for either value or for the +-2,000 / 0 result code
in that role; credited as Fork's own):

| Value | Where | Reason |
|---|---|---|
| 7 pieces (kings included): at or below keep the base's target, 8 or more get the result | rft-ep (`td_labels.py split --max-pieces 7`) | The plain result fine-tune's regressions were at 4-5 pieces (held-out 526 to 612 of 3,800) and 6-7 pieces (732 to 770 of 5,599); 7 is TCEC's table limit, so Fork's own evaluation matters most above it |
| LR 5e-6 | rft-ep-lo (8c), and P2 on 8b's base | Half of 1e-5, the rate the base ended at and r8brft1's fine-tune used: a smaller step toward the result target, to test whether the fine-tune's gain survives with less drift in the endings |
| +2,000 / 0 / -2,000 (White's view) | the result code `split` writes | The endgame slice's own convention (endgame_slice.py SLICE_SCORE): sigmoid(2000 / 92) is the result within 1e-9, inside the trainer's +-20,000 |

**Tooling on retrain/8c-prep** (no launch):
- `tools/datagen/td_labels.py labels --label-unsaved` (idea 80, variant A): each unsaved record not in check gets the
  lambda-return of its own ply (its G_t(0) is the next chain value), with two exclusions: an unsaved position in
  check stays unsaved (none in g4b-w00: every one of its 2,127,645 unsaved records was out of check, consistent with fork_datagen
  searching positions in check with its check nodes; UNVERIFIED in the generator's code), and so does one whose
  label reaches the trainer's limit of +-20,000 (saturated by the mate or table scores after it, whose saved records
  the trainer drops: 50,798 of g4b-w00's 2,127,645 unsaved records, 2.4%, in a first probe; a definitional choice
  made here so the i80 arm adds no record class the control lacks, flagged to the coordinator). The saved records'
  labels equal the plain TD(0.9) copy's. `check --label-unsaved` recomputes the new labels by the forward view.
- `tools/datagen/td_labels.py split` (rft-ep): the copy's keepable scores on records with 8 or more pieces replaced
  by the result code; the piece count from an occupancy-only replay, recomputed by python-chess in `check --mode
  split`.
- `tools/train/kaggle/retrain_8c.py`: session A1 (c1/c2 warm from r8btd90; then rft, ep (rft-ep) and eplo
  (rft-ep-lo) on each cK's window average; then i801/i802), every arm's file list and validity check;
  `test_retrain_8c.py`. Its MANIFESTS include the parts sealed later (g4c, the filler parts in FILLER, g4s2-pre,
  r8c-td, r8c-i80, r8c-split), set before the launch.
- `tools/train/kaggle/preflight_8c.py` (P1) and data/manifests/pos1.json: the positional slice slice-pos-td90 sealed
  as part pos1 (files renamed slice-pos-td90-s00-wNN-0000.vf to pos1-wNN.vf, bytes unchanged, every SHA-256 equal to
  its done.json), so that no kernel's "slice" name rule takes it for the endgame slice.

**Measured rates** (one process, Windows venv, Idle priority beside g4c, 2026-11-12 4:10 PM EST): TD(0.9) labels
89,900 records/s (g4b-w00, 4,664,430 records, 51.9 s); with --label-unsaved 73,900 records/s (63.1 s), its check
7.1 s; split 790,000 records/s (td90-g4-w00, 6,400,034 records, 8.1 s), its check 7.9 s. The split of all of
8c's c files (about 2.4 B records) is therefore about 51 minutes of one core plus about as much for the checks,
not the 6 hours that section 6 and risk 4 assumed.
