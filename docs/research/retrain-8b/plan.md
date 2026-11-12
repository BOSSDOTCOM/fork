# Retrain 8b: the plan (declared before any 8b training)

Written 2026-11-09 (branch retrain/8b-prep), before any 8b run, from the
owner's order of 2026-11-09 (verbatim): "Retrain 8b: write the full plan
(control with 8a's anneal findings; idea 52's arm; TD(0.8) and TD(0.9) arms;
one from-scratch committee run; equal data; GPU-hour estimate), finish the
Kaggle kernel, build the TD label shards and idea 52's training input, and
pre-upload everything that doesn't depend on g4's final part, so 8b can launch
as soon as g4 seals and I approve." Earlier: "8b label arms: TD(0.8) and
TD(0.9), using the tested lambda definition (the position's own score at
lambda 0). Record the same-network bias caveat in the 8b plan." And (owner,
2026-11-09): "keep the 2% endgame slice in every arm. It fixed simple endings
so decisively (39% to under 1% misjudged) that dropping it from any arm would
make the comparison about the slice rather than the idea being tested."

**Nothing is launched or adopted by this plan.** The training session waits
for g4's seal and the owner's approval. Nothing here changes after a result;
a later change is a new, dated section.

Tools (branch retrain/8b-prep): `tools/train/kaggle/retrain_8b.py` (the
kernel), `tools/datagen/retrain_8b_inputs.py` (inputs, manifests, upload),
`tools/datagen/td_labels.py` (`labels`, `blend`, `check`),
`tools/measure/committee_sites.py` (`arm`), `tools/datagen/snapshot_parts.py`
(`hold`, `val`, `record`).

## 1. Data: the snapshot g4s1

The standard recipe trains on every sealed part (item 7's g3s2, 8a's g3s3 =
g3s2 + g3f + g3g). 8b's snapshot **g4s1** is g3s3 unchanged plus every part
sealed since: g3h and g3i (S512ppr2's labels, sealed after g3s3 was built),
g3j (S512ppr3's, 115.6 M saved positions) and g4 (S512ppr3's, about 34.4 M
saved expected at its 64 M-record target). The cadence rule's 150 M new kept
positions from the promoted labeller are g3j + g4.

| Part | Files that train | Records | Saved positions | Labeller |
|---|---|---|---|---|
| 8a's g3s3 (g2s1, g3s1, g3b-g3e, g3s2, g3f, g3g, g3s3's rests) | 101 (data/manifests/g2s1 ... g3s3.json; the kernel's MANIFESTS) | 2,084,701,252 | 1,302,633,571 | B0r2 ... S512ppr2 |
| of which the Syzygy endgame slice | 10 (slice1-01..09.vf, g3s2-slice1-00-rest.vf) | 25,999,940 | 25,999,940 | Syzygy WDL |
| g3h | 5 shards + g4s1-g3h-w05-val-rest.vf | 37,103,060 | 20,182,795 | S512ppr2 |
| g3i | 5 shards + g4s1-g3i-w05-val-rest.vf | 5,595,571 | 3,046,547 | S512ppr2 |
| g3j | 5 shards + g4s1-g3j-w05-val-rest.vf | 210,203,794 | 114,379,873 | S512ppr3 |
| g4 (at its seal) | its training shards + its rest | about 64 M | about 34.4 M (UNVERIFIED until the seal) | S512ppr3 |
| **g4s1** | about 125 files | about 2.40 B | **about 1.475 B** | |

(Records and saved counts from the manifests and the splits' own counts; for
part shards without per-file saved counts, the part's unsaved share; the
kept share of saved positions is about 0.645 on g3j's pool, 62,144,106 of
96.4 M, so g4s1 holds about 0.95 B kept positions, UNVERIFIED.)

**The splits** (`snapshot_parts.py hold`, as g3s2 and g3s3 did): the first 60
games of each new part's validation shard (g3h-w05-val, g3i-w05-val,
g3j-w05-val, g4's) go to the validation file, the rest trains. One addition:
**the games of idea 51's held-out set H (5,000 sites) and the ensemble
teacher's H2 sample (20,000) are kept out of g3j-w05-val's rest** (24,730
games, about 1.2 M saved positions), so every 8b network stays unseen on the
gold sets the label studies score networks on. Check of the tool: rebuilding
g3s3's two rests and g3s3-val.vf gives the SHA-256 values in
data/manifests/g3s3.json byte for byte.

**Validation:** g4s1-val.vf = g3s3-val.vf's 32 streams plus 60 held games
each of g3h, g3i, g3j and g4, merged one game at a time (2,160 games). A
diagnostic only (owner, 2026-11-09): the per-superbatch prefix of 20,000
positions for monitoring, and the full file offline.

**The endgame slice in every arm (owner, 2026-11-09).** Every arm reads the
same 10 slice files unchanged: 26.0 M one-move games, 1.76% of g4s1's saved
positions (2.1% of g3s2's when it was added; the share falls as data grows, and
is the same in every arm). Its target is the same at any result weight
(sigmoid(+-2,000 / 92) is the WDL within 1e-9), so the TD arms read the
original files; `td_labels.py` copies such a one-move game unchanged in both
`labels` and `blend` (`settled_one_move`: one record whose score already says
its result; tested: before the rule, TD(0.8) turned a slice win's 2,000 into
about 2,148), and the kernel passes the slice files to every arm by name.

## 2. The arms (seed 1 each; 360 superbatches of 305 x 16,384)

Every arm sees exactly 360 x 305 x 16,384 = 1,798,963,200 positions (about
1.9 passes over g4s1's kept positions), read interleaved; what differs is
which files carry which target.

| Arm | Start | LR schedule | Result weight | Files (kernel `arm_files`) | Validation |
|---|---|---|---|---|---|
| **c**, control | S512ppr3's float weights (8a's R1-avg, SHA-256 02215858...7ecc3) | 0.0001, tenfold drop after 180 | 0.5 | g4s1's training files | g4s1-val.vf |
| **i52**, idea 52 | the same | the same | 0.5 | c's, with g3j-w00..w04 replaced by i52-g3j-w0N.vf, plus i52-sites.vf | g4s1-val.vf |
| **td80**, TD(0.8) | the same | the same | **0** | the slice unchanged; g3j's and g4's files (and their rests) as td80- copies; every other file as its bl- copy | bl-g4s1-val.vf |
| **td90**, TD(0.9) | the same | the same | **0** | as td80 with td90- copies | bl-g4s1-val.vf |
| **scr**, committee member | seeded random weights | 0.001, tenfold drop after 180 (item 7's scratch recipe) | 0.5 | c's | g4s1-val.vf |

**The control applies 8a's findings:** the standard recipe with no cooldown
branch (CD did not beat R1's own average) and no anneal-only arm (D1 was worse
than R1-avg); the candidate of each arm is **its window average**, the mean of
superbatches 331-360's float weights, quantised by the trainer itself (8a's
method: a one-batch run at LR 0 whose checkpoint keeps the same weights byte
for byte). Each arm's best checkpoint and its superbatch-180 and -360
checkpoints (optimiser state included) are kept too.

**Idea 52's arm** (committee_sites.py `arm`; the arm stays by the owner's rule:
matched ratio 1.42 [1.26, 1.62], docs/research/idea52/8b-check.json):
- Sites: the 200,000 top-disagreement sites of S512ppr3 against item 7's
  scratch seed 1 on g3j-w00..w04 (docs/research/idea52/8b-sites.json),
  labelled at 200,000 nodes by S512ppr3 (labels.tsv, SHA-256 7255a627...7baa).
  The last 10,000 in draw order (a uniform sample) are held out, never
  trained; 190,000 train.
- **Target (declared): `blend`.** Each site is a one-move game: its position,
  the move played there, the deep label as the score (White's view; a mate
  +-20,000; a table win clamped to +-20,000) and **the site's own game result**,
  so the trainer's target is the standard 0.5 sigmoid(deep / 92) + 0.5 z with
  the 200,000-node search in place of the game's 20,000-node one: the arm
  changes which positions and how deep their score, not the label's
  definition (whose result half guards against the labeller's own biases).
  The alternative, `--target label` (the deep label alone: z the result
  nearest p = sigmoid(deep / 92) leaving 2p - z in [0, 1], the score
  92 logit(2p - z), so 0.5 sigmoid(s / 92) + 0.5 z = p), is built and tested
  but not used unless the owner chooses it.
- **Oversampling factor 16 (proposed).** The 190,000 trained sites are a
  uniform 6% sample of the 3,173,657-position top set; 16 copies give them the
  weight the whole top set has in the pool (3,173,657 / 190,000 = 16.7, rounded
  down), a Neyman-style allocation of the deep labels to the region the
  committee flags, at 0.32% of g4s1's kept positions (about 30 presentations
  per site over the run). Overfitting to 190,000 positions is the risk; the
  held-out 10,000 sites measure it (below).
- **Equal data: oversampling replaces.** In copies of g3j-w00..w04, each trained
  site's own record and 15 more per trained site, drawn uniformly (seed
  20261109 with its own salt) from the pool's other kept records (never a site
  or control), get the unsaved marker 32767, which the trainer drops:
  190,000 + 2,850,000 = 3,040,000 of the pool's 62,144,106 kept records (4.9%)
  leave, 190,000 x 16 = 3,040,000 site games come in. The arm's kept positions
  equal the control's exactly (verify_arm reads everything back), and every
  other file, the slice included, is the control's.
- Evaluation only: i52-held.vf (the 10,000 held sites) and i52-controls.vf
  (the 2,000 controls), with the deep label alone as their target at result
  weight 0.5, scored offline for every candidate.

**The TD arms** (idea 51; td_labels.py `labels`, the tested definition:
lambda 0 is the record's own score, plies outside the chain take the next
chain value, positions in check and unsaved records out of the chain, the
stored result as the terminal value; S = 92): TD copies of S512ppr3's data
only (g3j's five shards and rest; g4's at the seal), as the owner ordered.
The trainer applies one result weight to every file, so the TD arms run at
--result-weight 0 and every older file is read as its **blend copy**
(td_labels.py `blend`: the score whose sigmoid is 0.5 sigmoid(s / 92) + 0.5 z),
which gives the older data the control's target to the integer rounding
(at most 0.0014 in probability, zero-mean). The TD arms therefore see the same
positions in the same order as the control (the copies keep every board, move
and filter decision), with TD targets on g3j and g4 and the control's
everywhere else. Every copy is checked (td_labels.py `check`: boards, moves and
terminators identical, scores changed only where allowed, and every 100th game
recomputed by an independent formula, the forward view of TD(lambda) or the
blend, equal within 1).

**The from-scratch committee run** (decision of 2026-11-07, "Idea 52: the
independent committee"): scr, item 7's scratch recipe on the control's data.
Not a candidate; its window average is converted and kept as the next
retrain's independent committee member, unless idea 52 is retired (then the
rule lapses and 8c drops it).

## 3. Selection and tests (declared before any result)

1. **Integrity gates (blocking, per candidate):** the kernel's validity
   (every input matches its manifest; S512ppr3's weights reproduce their
   g3s3-val prefix loss 0.01960772 within 1e-6; c's and i52's superbatch 0
   equal S512ppr3's g4s1-val prefix loss within 1e-6, td80's and td90's on
   the blend copy at weight 0 within 1e-5; the run ended with exit 0;
   the window complete and quantised unchanged); conversion at the scale
   matched to S512ppr3's mean |eval| on 4,000 g4s1-val positions; the parity
   chain (trainer leg, netcheck exact on 446 positions, quantisation loss
   within S-512's 21 / 16 cp). A candidate failing one is out.
2. **The endgame check** (tools/nnue/endgame_check.py, 900 positions) for
   every candidate, reported; non-blocking (owner, 2026-11-09), and a large
   regression flagged to the owner: more than 15 of 900 misjudged (S512ppr3:
   8).
3. **Fixed-node screens, all competing candidates first** (the testing rule
   of 2026-11-09): c-avg, i52-avg, td80-avg, td90-avg, each 1,600 games at
   800,000 nodes per move against S512ppr3 (the same architecture: no speed
   adjustment), one at a time on GitHub.
4. **Head-to-head screens for the ideas' keep-or-drop rules:** i52-avg,
   td80-avg and td90-avg each against c-avg, 1,600 games at 800,000 nodes.
5. **Promotion:** the candidate with the highest screen against S512ppr3
   goes to the STC SPRT [0, 5] against S512ppr3. If it fails, the
   second-best goes only if its screen was +5 Elo or more; at most two SPRTs.
   An H1 goes to the owner for promotion (the labeller policy's part switch
   follows a promotion). Validation loss decides nothing.
6. **Idea 52 (the owner's rule of 2026-11-07):** kept if i52-avg beats c-avg
   by +5 Elo or more in its head-to-head screen, or passes an STC SPRT if it
   is SPRTed; otherwise retired and the scratch-run rule dropped; the record
   stays. Reported beside it: each candidate's loss on i52-held.vf and
   i52-controls.vf (whether the arm generalised to sites it never saw).
7. **Idea 51:** a TD arm is kept only if its head-to-head against c-avg is
   above +4 Elo (idea 51's kill rule: within +-4 of the control kills it) and
   its endgame check is not worse than c-avg's; its gold-set loss part lapsed
   with the 2e-5 margin (owner, 2026-11-09).
8. The scratch run's network is checked like a candidate (gates 1-2) and
   kept, not screened.

## 4. GPU hours (from recorded runs)

- One 360-superbatch run of S512+PP's architecture on Kaggle T4 x2, two runs
  side by side (one per GPU): **7,741 s = 2.15 GPU-h** (item 7's warm seed 1;
  8a's R1 and R2 each 7,740.8 s at 232,400 positions/s, retrain.json of
  fork-retrain-g3s3 v1). 8b's runs read the same number of positions at the
  same batch size, so the same time is expected (UNVERIFIED for the larger
  file set: 8a mounted 111 files, 8b about 280, about 24 GB).
- **Five runs: 10.75 GPU-h** of training. Plus setup (rustup, the build,
  hashing about 24 GB of inputs; 8a's build took 35 s) and the offline step
  (five window averages and quantisations, 11 networks scored on four files):
  about 0.5 h on one GPU, UNVERIFIED.
- **Parallelism:** GPU 0 runs c, td80, scr (6.45 h); GPU 1 runs i52, td90
  (4.3 h); one session of about **7.0 h of wall time** (under Kaggle's 12-hour
  limit).
- **Quota:** 30 GPU-h a week (KB training-data.md). Whether a T4 x2 session is
  charged at wall time or per GPU is UNVERIFIED (8a's prep noted the same):
  about **7 or 14 quota hours**. Either fits one week beside the label-depth
  study (ideas.md 62), which starts after 8b launches.
- An optional sixth run, **c2** (the control at seed 2, +2.15 GPU-h, GPU 1
  after td90), would measure seed noise in Elo (a c2-against-c screen) for
  reading the head-to-heads; not in the declared design (owner's choice).

## 5. The same-network bias caveat

The TD pre-tests (docs/research/label-pretests/results-8b.md on
idea51/td-labels: MSE against deep labels TD(0.5) 0.001428, TD(0.8) 0.002126,
TD(0.9) 0.003817, control 0.010535) scored labels against S512ppr3 at 1 M
nodes on positions S512ppr3 labelled at 20,000 nodes. The gold shares the
labelling network's biases, so any label leaning on the stored scores and
away from the game result looks closer to it; the test cannot say how much
of the TD labels' advantage is label quality and how much is the shared
network, and lambda 0.8 / 0.9 may weight the result too little for training
(the result is what corrects the network's own biases). Idea 52's deep labels
are S512ppr3's own search too. The arms' games decide.

**The measured bias (placeholder):** the ensemble teacher's step 0
(docs/research/labels-teacher/step0-declaration.md, dc90302 on
research/labels-teacher; jobctl measure job teacher-step0, running since
6:46 PM EST on 2026-11-09) scores the same labels against the 1 M-node gold
of item 7's two scratch seeds and their mean, which share no network with the
labels. Its result goes here, as a dated addition, before 8b's results are
read: _pending_.

**Added 2026-11-09, 10:05 PM EST, before any 8b result:** measured, about
zero. Step 0's independent golds (scratch-s1 and scratch-s2 at 1 M nodes on
H) give bias = (candidate − control under S512ppr3's gold) − (the same under
the independent gold mean): TD(0.8) +0.000020 [−0.000163, +0.000198], TD(0.9)
−0.000015 [−0.000177, +0.000142], every interval containing 0, against
differences of 0.003-0.009 (results-8b.md on idea51/td-labels 68d1527). The
gold is not what made the stored-score-heavy labels look close; the other half
of the caveat stands (every TD label leans on S512ppr3's 20,000-node game
scores, and only games say whether a lower lambda trains better).

## 6. The endgame-start slice (R32): the owner's choice

R32 (docs/research/phase4-think-tank/phase-c-synthesis.md: Fork self-play from
its own 8-16-piece positions with |label| 50-400 cp at 80,000 nodes, no split
search, adjudication raised or off, about 1% of the next snapshot; a 4 M
pilot first, about 2.6 h, then about 10.5 h of the 10-thread machine). DESIGN
§5.6 step 13 defers the decision until 8a's result, which is in (S512ppr3:
the endgame check 8 of 900, unchanged by 8a). Options:
- **(a) Defer to 8c** (recommended): run R32's pilot during g4b's generation,
  and if it passes its gate, generate the slice into 8c's snapshot as its own
  arm. 8b launches at g4's seal as planned.
- (b) Include it in 8b: 8b waits about 13 hours more (pilot + generation),
  and the slice must go into every arm (as the Syzygy slice does) or become a
  sixth arm (+2.15 GPU-h).
- (c) Drop R32.
This is separate from the Syzygy slice, which stays in every arm.

## 7. Timeline (EST; from g4's seal, expected about 11 PM on 2026-11-09)

| When | What | Lane |
|---|---|---|
| 7:59 PM (started) | `r8b-pre`: blend copies (103 files), TD(0.8)/TD(0.9) of g3j, the splits, idea 52's arm; each checked; manifests | jobctl slice, below normal |
| when r8b-pre ends (about 2 AM, UNVERIFIED: the machine is fully loaded) | `r8b-upload-pre` (already waiting): the five pre-seal datasets, each downloaded back and hashed | jobctl upload |
| g4's seal + r8b-pre's end | `r8b-post`: g4 checked, split, g4s1-val.vf and its blend copy, g4's TD copies (about 64 M records, about 1 h); then `r8b-upload-post` | slice, upload |
| then | commit g4.json, r8b-g4.json and the pre manifests; set the kernel's COMMIT; push; `--check-inputs` on the local copies | E |
| **owner's approval** | kernel push (fork-retrain-8b): about 7 h of wall time | K |
| session end + about 1 h | gates locally (conversion, parity, netcheck, endgame check) | L |
| then | 7 fixed-node screens (about 7 stages), then 1-2 STC SPRTs (up to 12 stages each) | G |

## 8. What is uploaded when

| Dataset | Contents | When |
|---|---|---|
| fork-g2s1, fork-g3s1, fork-g3rest, fork-g3bcd, fork-g3e, fork-g3s2, fork-g3f, fork-g3g, fork-g3s3 | 8a's inputs (g3s3-val.vf, the slice) | already on Kaggle |
| fork-g3hij | g3h, g3i, g3j whole; their three rests; s512ppr3-weights.bin | pre-seal (r8b-upload-pre) |
| fork-r8b-blend-1, -2, -3 | the 103 blend copies (50, 50, 3 files) | pre-seal |
| fork-r8b-arms | td80-/td90- copies of g3j's six training files; idea 52's eight files | pre-seal |
| fork-g4 | g4 whole | after the seal |
| fork-r8b-g4 | g4's rest, g4s1-val.vf, bl-g4s1-val.vf, g4's TD copies | after the seal |

The kernel mounts 16 datasets (8a mounted 9; Kaggle's limit on a kernel's
data sources is UNVERIFIED). Manifests (data/manifests): g4s1-pre.json,
r8b-blend.json, r8b-arms.json now; g4.json (the seal) and r8b-g4.json after.

The commands after the seal (each also in ~/fork-data/8b/):

    python -I tools/jobs/jobctl.py start slice r8b-post -- bash ~/fork-data/8b/post-job.sh
    python -I tools/jobs/jobctl.py start upload r8b-upload-post -- bash ~/fork-data/8b/upload-post-job.sh

## 8b. The launch (added 2026-11-09, 10:05 PM EST, before any 8b result)

The owner pre-approved 8b for the night (about 9:35 PM EST) with the plan's
recommended options taken for the open questions below (factor 16, `blend`,
g3h and g3i in, H and H2 out, no c2, R32 deferred to 8c), and "if the kaggle
quota (30hrs week) is reached then drop the least promising of the 5 runs
until it fits". The quota (`kaggle quota`, CLI 2.2.5, at 9:44 PM EST): 27.04 h
of 30 remaining (2.96 h used; it refreshes 2026-11-13 at 7 PM EST); five runs
need about 7.2 h of T4 x2 wall time, at most about 14.3 h if counted per GPU,
so all five run (the declared drop order, unused: scr, td90, i52; never c).

Candidates' branches: bake/r8bc, bake/r8bi52, bake/r8btd80, bake/r8btd90 (the
net names without separators, as the Control Center's parser requires), each
from origin/phase-4's head at the time, which since 85253a2 carries the R14
SPSA margins (bench 10,374,064 / 677c436fa145e07f with S512ppr3): the screens'
base is that same commit, so each screen compares nets on one engine. A dry run
of the branch script with S512ppr3's own net (rebuilt from 8a's R1-avg by the
gate script, byte for byte nets/s512ppr3.fnet) gave that bench exactly. The
screens and SPRTs run as the night queue's items 15-8b-a to 15-8b-i, in the
order screens, SPRT(s), head-to-heads; nothing is promoted.

## 9. Open questions for the owner

1. The oversampling factor 16 for idea 52's arm (8 would halve the weight and
   the overfitting risk) and its target (`blend` declared, `label` built).
2. g3h and g3i (S512ppr2's labels, sealed after g3s3) are in g4s1 as the
   standard recipe's "every sealed part"; the order named g3j + g4 only.
3. H's and H2's games kept out of g3j-w05-val's rest (24,730 games).
4. c2, a second control seed (+2.15 GPU-h), for a seed-noise reading.
5. R32: (a), (b) or (c) above.
