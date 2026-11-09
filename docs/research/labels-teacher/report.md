# Label depth and an ensemble teacher: two designs with costs

Written 2026-11-09, about 6 PM EST. **Design only: no code, no jobs, no data generation and no training were run for this report.** Each design waits for the owner's review. Every figure is cited to a committed file or is marked as an estimate with its derivation. UNVERIFIED marks anything not checked.

The owner's items (verbatim):

> 2. Label depth experiment: equal-generation-time data arms at 20k vs 50k (and 100k) nodes for saved positions; small nets trained on each; fixed-node screen. Estimate cost.
>
> 3. Ensemble teacher: design training 3-4 independent S512 nets on Kaggle and using their averaged eval (with search) to label or relabel data for the main net; compare with idea 58's big teacher.

Sources read: DESIGN.md §5.3 deliverable 2 (split search, labeller policy, disk margin), §5.4 (speed gate, fixed-node rules), §5.6 (checklist and order), Testing setup (design R, kinds), the decisions log (2026-10-30 to 2026-11-09); ideas.md 13, 47, 48, 51, 52, 58, 59; docs/nets.md; data/manifests/g2d, g2e, g3, g3g, g3h, g3i, g3j, g3s3; tools/cloud/datagen-rates.tsv; tools/train/kaggle/idea13.py; docs/research/idea52/report.md; the think tank's phase-a-evidence.md, phase-b-specialists.md §2.4 and phase-c-synthesis.md §5.3; branch idea52/8b-sites (docs/research/idea52/8b-sites.json and its ideas.md diff); branch idea51/td-labels (docs/research/label-pretests/declaration-8b.md and results-8b.md); branch exp/oracle commit messages 0a40491, ab1abce and dcbe8fb, plus its refiner_gate.hpp; src/search/trans_table.hpp and src/datagen/. No chess engine's source was opened.

---

## 0. Shared facts and the cost model

### 0.1 What one generated record costs (the split search)

The standing setting since 2026-10-31 (DESIGN.md §5.3 deliverable 2; decisions log 2026-10-31) is `--nodes 20000 --save-percent 50 --unsaved-nodes 4000 --check-nodes 2000`, Hash 1 MB, with score adjudication at 700 cp for 8 plies. A position not in check is **saved** with probability 50% and searched at `--nodes`. Otherwise it is **unsaved**: searched at 4,000 nodes, it only moves the game along and records score 32767, which the trainer drops. Positions in check are searched at 2,000 nodes and recorded as saved (ideas.md 13, arm B), but the trainer drops them. **In this report, "label depth" means the `--nodes` value of the saved searches only.** The unsaved and in-check searches stay at 4,000 and 2,000 nodes in every arm.

**The node model, checked against a measured manifest.** In g3 (data/manifests/g3.json) there were 500,000,697 records, 227,791,196 of them unsaved, and `nodes_spent` was 5,578,338,512,874. Each non-check position is saved with probability 0.5, so the saved non-check count is about the same as the unsaved count. That leaves 500.0 M − 2 × 227.8 M = 44.4 M in-check records (8.9%). The model gives 227.8 M × 20,000 + 227.8 M × 4,000 + 44.4 M × 2,000 = 5.556e12 nodes, which is **99.6% of the measured `nodes_spent`**. I use the model below with g3j's shares (data/manifests/g3j.json): unsaved 45.6%, in check 8.8%, saved 54.4%.

| saved `--nodes` | nodes per record | nodes per saved non-check label | label yield at equal nodes |
|---|---|---|---|
| 20,000 | 11,117 | 24,387 | 1 |
| 50,000 | 24,794 | 54,387 | **0.448** |
| 100,000 | 47,587 | 104,387 | **0.234** |

This is an estimate. It assumes the time per node does not depend on the node limit and that the shares (saved, unsaved, in check, kept) do not change with depth. §1.6 covers the rate probe that checks both assumptions.

### 0.2 Measured rates

| source | net | threads | records/s | note |
|---|---|---|---|---|
| g3.json | S512r2 | 10 | 2,734 (500.0 M / 182,879 s) | 3.05 M nodes/s per thread (nodes_spent / s / 10) |
| g3g.json | S512ppr2 | 10 | 2,680 (111.2 M / 41,485 s) | |
| g3j.json | S512ppr3 | 6 | 1,606 (212.5 M / 132,344 s) | 115.6 M saved; 2,277,510 games, 93.3 records per game |
| g4 (running) | S512ppr3 | 10 | **2,250-2,300** | the figure from the running part; **not in a committed file (UNVERIFIED here)**; used below as 2,275 |
| results-8b.md (idea51/td-labels) | S512ppr3, UCI driver, Hash 16 | 2 workers | 5,000 labels at 1 M nodes in 22 minutes | **1.89 M nodes/s per worker** (one search per position, fresh TT) |
| datagen-rates.tsv | S512 | 8 vCPU | c8a.2xlarge 2,075, c7a.2xlarge 1,640 | AWS only; the account is suspended (DESIGN.md Testing setup, 2026-11-05) |

The trainer keeps 67.7% of saved records (phase-b-specialists.md §2.5, quoting A1 §1). That gives **0.368 kept positions per record**, so g4's rate is **about 838 kept positions per second on 10 threads at 20k** (an estimate: 2,275 × 0.544 × 0.677).

### 0.3 Small-net training cost (recorded runs)

The ideas.md group rule for the novel NNUE ideas: "Each is tested at equal data with a small net first (B0's size, 768 -> 256, training in minutes)". B0r2, the same shape trained from scratch at 80 superbatches (400 M positions seen), took **1,083 s on one T4** (docs/nets.md, B0r2). idea13.py trains this shape two runs at a time on T4 x2, one per GPU. **So one small-net run is about 0.30 T4 GPU-hours.** A full S512+PP run of 360 superbatches is **7,741 s, about 2.15 GPU-h** (nets.md S512ppr2; phase-b-specialists.md §2.4). The weekly Kaggle quota is about 30 GPU-h (phase-a-evidence.md). Whether two parallel runs on T4 x2 count once or twice against it is UNVERIFIED (same source).

### 0.4 Screen conventions (DESIGN.md)

- **The fixed-node screen** is 1,600 games at 800,000 nodes per move for both engines, as one GitHub stage (decisions log 2026-11-01, 2026-11-02 and 2026-11-07; `tools/github/sprt_run.sh --kind fixed --cap N`, Testing setup). Its 95% interval for nets of similar strength is about ±9-10 Elo (for example +15.65 ± 9.26 and +9.56 ± 9.45; nets.md, ideas.md 59).
- **Retrain candidates** are gated by a fixed-node screen of at least +5 Elo, then an STC SPRT (decisions log 2026-11-07).
- **Network SPRTs** use `--kind network`: [0, 5] Elo, alpha = beta = 0.05, 13 STC stages. **Design R** ([0, 6] nElo, beta 0.20, cap 8, futility after 2) is for search features and does not apply to either item. Every run carries `--idea ID`, and each SPRT is a try of its idea, at most two per idea and time control.
- **Seed noise in small nets is large.** In idea 13 the seeds of one arm differed by +3.3 ± 12.6 and −14.8 ± 12.4 Elo at STC (ideas.md 13). Both designs below therefore pair seeds (seed 1 against seed 1, seed 2 against seed 2) and do not pick a "best seed".

---

## 1. Item 2: label depth at equal generation time

### 1.1 The question

Does the same CPU time give a better network if it buys fewer positions with deeper saved searches (50k or 100k nodes) instead of more positions at 20k? Idea 13 answered the opposite trade (cheap unsaved moves, +65.47 ± 12.90 Elo at STC; ideas.md 13). This asks whether the saved search itself is too shallow.

### 1.2 Arms

All arms come from **one PGO build** of the current default engine (S512ppr3 plus every adopted search change, bench-checked) and use the standing settings except where stated. They also share the opening book (lichess-2026-09.epd), seed, adjudication, tables and the unsaved and in-check node counts.

| arm | saved `--nodes` | Hash | why that Hash |
|---|---|---|---|
| D20 | 20,000 | 1 MB | the standing setting: 16,384 buckets × 5 entries = 81,920 entries (trans_table.hpp: 12-byte entries, five per 64-byte bucket), 4.1 per saved-search node |
| D50 | 50,000 | 3 MB | 245,760 entries, 4.9 per node |
| D100 | 100,000 | 5 MB | 409,600 entries, 4.1 per node |

The Hash is scaled so that a deeper search is not crippled by a table sized for 20k. Any bucket count is valid, because the index uses a multiply-high range reduction (trans_table.cpp `bucket_index`). The rate probe (§1.6) measures whatever speed cost the larger tables add. **The same seed in every arm** gives game *i* the same opening, random plies and save decisions in each arm until the games diverge. The deeper arms play fewer games, so their openings are approximately a prefix of D20's (a paired design). That save decisions and openings follow (seed, game index) is from DESIGN.md §5.3. That the worker-to-game-index assignment keeps this pairing exact across arms with different speeds is UNVERIFIED. It may hold only roughly, which does not bias the comparison.

**Volume controls (GPU only, no extra generation):** D20/50 and D20/100 are D20's data cut to D50's and D100's kept-position counts, using each worker's first games, as idea 13 cut arm B. They separate quality per position from volume. **They are for interpretation only and do not enter the decision.**

### 1.3 Equal CPU time: layout and predicted sizes

**Recommended layout (A): the three arms run at the same time, 3 threads each (9 threads), for 40 hours.** Each arm gets 120 thread-hours, and machine load, thermal state and other jobs affect all three equally, so equal wall time means equal CPU. This replaces the main generation (g4) for 40 hours: the one-data-job rule. All three arms are labelled by the default engine, so under the labeller policy they are valid training data. They are sealed as their own parts with their own manifests, and an adoption during the run does **not** end them: one binary for the whole experiment (declared up front, an exception to the policy that the owner must approve).

**Alternative (B): sequential parts at 10 threads, 12 hours each.** D20 is simply 12 hours of g4, then D50 and D100 run as parts. This is idea 13's pattern, but load can differ between the parts. If the load logs differ by more than 5%, the longer arm is cut to equal CPU from its own log.

Predicted sizes per arm at 120 thread-hours (estimate: §0.1 yield × §0.2 rate, 2,275 records/s on 10 threads, 0.368 kept per record):

| arm | records/s (10-thread equivalent) | kept/s | records per arm | **kept per arm** | passes at 400 M seen |
|---|---|---|---|---|---|
| D20 | 2,275 | 838 | 98.3 M | **36.2 M** | 11 |
| D50 | 1,020 | 376 | 44.1 M | **16.2 M** | 25 |
| D100 | 531 | 196 | 23.0 M | **8.5 M** | 47 |

For scale, idea 13's arms had 35.6 M and 43.4 M saved records (ideas.md 13).

**Disk** (estimate, at 4.6 bytes per record from the disk-margin policy): 165.4 M records ≈ 0.76 GB, far inside the margin.

**What it costs the main generation** (estimate). Run as standard 20k data, the same 360 thread-hours would give 108.6 M kept positions. The arms give 60.9 M, so the experiment forgoes about **47.7 M kept positions, about 16 hours of normal 10-thread production** (47.7 M / 838 per second). Layout A also leaves one of the ten threads idle (about 12 M more kept positions). Retrains 8b and 8c come every 150 M new kept positions (§5.6 step 13), so the experiment delays the next retrain by less than a day.

### 1.4 Small nets and training recipe

- **Architecture:** B0 (768 -> 256 -> 1, clipped ReLU, QA 255 / QB 64; nets.md), the group's small-net standard, as idea 13 used.
- **Recipe:** idea13.py's settings. From scratch, AdamW, LR 0.001 dropped tenfold every 40 superbatches, batch 16,384 × 305, **80 superbatches (400 M positions seen by every run)**, result weight 0.5, and the checkpoint with the lowest validation loss on the arm's own held-out shard. There is **one S for every arm**, fitted on D20 with fit_scale.py (idea 13 fitted on arm A and used it for both).
- **Seeds:** 2 per arm. Runs: D20, D50, D100, D20/50 and D20/100, two seeds each, **10 runs**.
- **Overfitting watch:** D100 sees its data about 47 times. Best-checkpoint selection guards against it, and the validation curves are reported. A best checkpoint before superbatch 40 is flagged as volume-starved: the result then reflects D100's volume, not its labels.

### 1.5 Screen, decision rule and confirmation (declared before any data)

1. **Fixed-node screen, seed-paired:** D50-s1 against D20-s1 and D50-s2 against D20-s2, one 1,600-game stage each at 800,000 nodes per move (`--kind fixed --cap 1`). The same for D100 against D20. **4 stages.** The two stages of each comparison are pooled into one 3,200-game estimate (pentanomial sums, as sprt_merge.py does).
2. **Optional, for interpretation:** D50 against D20/50 and D100 against D20/100 (quality at equal volume), 2 stages each.
3. **Decision rule:**
   - **Deeper wins** if a deeper arm's pooled estimate against D20 is at least **+5 Elo** with its 95% interval above 0. If both qualify, the higher estimate wins. That arm then plays its **confirmation**: an STC SPRT `--kind network` [0, 5] against D20 with seed 1's nets. The networks are the same size, so equal nodes is close to equal time.
   - **20k stays** if no deeper arm qualifies, including an inconclusive result. This is idea 13's rule: the simpler setting stays when the result is unclear.
   - A pass is a recommendation, not an adoption. Changing the standing data-generation setting is the owner's decision, and it starts a new part under the labeller policy.
4. **Ideas ledger:** a new idea id (for example `label-depth`); the confirmation SPRT is its first try.

### 1.6 Rate probe (how the estimate is checked)

Before committing 40 hours, run a **short probe**: the three arm binaries for **30 minutes in layout A** (3 threads each, at the same time), in a quiet window such as a part boundary. Record records/s, kept share, `nodes_spent` per record, nodes/s per thread and the median completed depth (from a 200-position `go nodes` sample per arm through the `fork` binary, since fork_datagen does not record depth). It tests the model's two assumptions: whether nodes/s holds at 1, 3 and 5 MB of Hash, and whether the saved, unsaved and in-check shares hold when the saved moves get stronger. If the measured yield ratios differ from 0.448 and 0.234 by more than 10%, the arm sizes in §1.3 are restated before the full run. The design itself still holds, because layout A equalises CPU directly. Cost: 4.5 thread-hours.

**Optional offline step 0 (shared with item 3, §2.5):** label the existing held-out set H (5,000 g3j validation sites with S512ppr3 1 M-node labels; declaration-8b.md) at 20k, 50k and 100k nodes. This gives each depth's error against 1 M nodes, which shows how much label noise each depth removes before any data is generated. It is **report only**: the same-network bias (§2.1) favours the deeper arms here by construction, so it cannot decide.

### 1.7 Costs (item 2)

| resource | amount | derivation |
|---|---|---|
| CPU, generation | 360 thread-hours, **40 h wall** at 9 threads | 3 arms × 120 thread-hours |
| CPU, probe | 4.5 thread-hours, 30 min | §1.6 |
| CPU, step 0 (optional) | about 0.25 worker-hours | 5,000 × 170k nodes = 8.5e8 nodes at 1.89 M nodes/s |
| Lost production | about 47.7 M kept positions (about 16 h of 10-thread g4) | §1.3 |
| Seal, verify, upload | about 1.5-2 h per part, run beside other work (g3g: stopped 12:16 PM, verified 1:53 PM EST; decisions log 2026-11-07) | three small parts |
| GPU | **about 3.0 T4 GPU-h** (10 runs × 0.30), about 1.5-2 h wall on T4 x2 plus the build and hash check | §0.3 |
| GitHub | 4 fixed-node stages (+2 optional), then 1-13 STC stages only if a deeper arm passes | §1.5 |
| Wall time, end to end | **about 3 days** (40 h generation, half a day for seal and upload, a Kaggle session, a GitHub afternoon) | the wall time of a fixed-node stage is not in the files read (UNVERIFIED; an STC stage is about 18 minutes, §5.6) |
| Cloud alternative | **AWS is unavailable** (account suspended, DESIGN.md Testing setup). If it returns: one c8a.2xlarge per arm for 12 h runs the arms in parallel with no local displacement (S512's measured 2,075 records/s at 20k on 8 vCPU; S512ppr3's rate there is unmeasured), and the launcher prices by expected cost per million positions (`tools/cloud/spot_pools.py`). GitHub runners and Kaggle are not set up for data generation. | datagen-rates.tsv |

### 1.8 Confounders and limits

1. **Play changes with depth.** On a saved ply the move played comes from the deeper search, so D50 and D100 games are a little stronger on half their plies. That shifts the position distribution, game results (the result is half of every target) and adjudication timing (8 saved scores in a row at 700 cp or more). The experiment measures "deeper saved searches as implemented", as idea 13 did, not labels alone. The cleaner alternative is a **relabel design**: re-search D20's saved positions at 50k and 100k nodes. That isolates the label exactly, but it needs a relabel driver that replays each game with a per-game TT (none exists in C++; tools/measure/label_pretest.py `deep` and committee_sites.py search positions one by one through UCI with a fresh TT). Relabel costs only the saved search per label, so the yield is 24,387 / 50,000 = 0.49 and 24,387 / 100,000 = 0.24 of D20's labels, not 0.448 and 0.234. The generation design is recommended because its answer is the setting that would actually change.
2. **Opening set:** one book and one seed in every arm (paired). The result holds for lichess-2026-09.epd.
3. **Labeller network:** one binary (S512ppr3). The value of depth may change with the net's strength: a stronger net needs less search to correct it. The result is for this labeller.
4. **Data volume against quality:** D20/50 and D20/100 show which one drives the result. With 400 M seen, D100's 47 passes may hit a volume limit that a long production generation would not.
5. **Small-net transfer:** B0 has about 197k first-layer weights per perspective (768 × 256), while S512+PP has 768 × 512 plus 608 links. Whether a larger net gains more or less from deeper labels is UNVERIFIED. If D50 or D100 wins, the confirmation is a real retrain arm (S512+PP warm recipe) at equal data, through the retrain gate.
6. **Scale S:** one S for every arm, fitted on D20. Deeper labels may have a wider |score| spread; if fit_scale.py on D100 lands outside about ±4 of D20's S, that is reported.
7. **TT size:** scaled per arm (§1.2). With 1 MB at every depth instead, the deeper arms would carry a handicap that a real setting change would not.
8. **Time of day and machine load:** removed by layout A.

---

## 2. Item 3: an ensemble teacher

### 2.1 The problem it addresses: same-network bias

Every label Fork trains on today is a 20,000-node search by the current default network. The 8b label pre-tests (results-8b.md on idea51/td-labels) show the consequence. The deep gold labels were S512ppr3 at 1 M nodes and the stored labels S512ppr3 at 20k, so "any label that leans on the stored scores and away from the result looks closer. The test cannot tell how much of the gap is label quality and how much is the shared network." The exploratory grid found λ = 0, the stored score itself, closest to the gold. Errors the default net makes systematically, and which a 20k search does not correct, come back as training targets. The game result (weight 0.5) is the only independent signal, and a game carries only about 1.5 independent result observations (ideas.md 51).

**Evidence that independent nets carry independent errors:**

- Idea 52: a scratch pair (independent initialisations) disagrees most where S512ppr3's predecessor S512ppr2 errs 1.6-1.7 times more than elsewhere at equal |eval|. A warm pair (in effect one net) carries no such signal (docs/research/idea52/report.md).
- Idea 59 f1c: blending S512ppr3 with the independent s512pp-scratch-s1, (base + second) / 2 at 3.8% of evaluations (the window gate), scored **+9.56 ± 9.45 Elo at fixed nodes** against S512ppr3 alone. Replacing instead of blending scored +3.47 ± 9.34 (ideas.md 59). This is below the +10 bar declared for step 3b, so it is weak evidence, but it points the same way.
- The two nets' static evaluations correlate at 0.995, with a mean disagreement of 21.6 cp on g3j (8b-sites.json). They are close but not identical.

**What an ensemble cannot fix:** every member is trained on data labelled by the same lineage of searches (S512, S512r2, S512+PP, S512ppr2, S512ppr3), so whatever bias those labels share is common to all members, and averaging removes only the part of the error that varies between members. If the members' errors have correlation ρ, averaging K members leaves an error variance of σ²(ρ + (1 − ρ)/K). The ensemble helps only as far as ρ is below 1, and ρ is unmeasured (UNVERIFIED). Idea 58's big teacher has the same limit: it learns from the same labels.

### 2.2 Members

| member | origin | GPU-h | status |
|---|---|---|---|
| S512ppr3 | the default (warm lineage from S512r2) | 0 | exists |
| s512pp-scratch-s1 | item 7's scratch run, seed 1, g3s2, LR 0.001 from a seeded random start, best val loss 0.01947642, S matched to 90 (exp/oracle ab1abce) | 0 | exists, with a parity file on exp/oracle |
| s512pp-scratch-s2 | item 7's scratch run, seed 2 (converted at S = 89 in the idea 52 report) | 0 | exists (float weights in the item 7 output; parity file and bench reference not yet made, UNVERIFIED) |
| 8b's scratch run | the standing rule since 2026-11-07: every retrain keeps one from-scratch run as the independent member (about 2.2 T4 GPU-h, already budgeted) | 0 extra | arrives with 8b, **unless idea 52's keep-or-drop rule retires the scratch-run rule** |
| new scratch seeds (optional) | S512+PP from scratch on g3s3 + g3j, 360 superbatches; 720 if trained longer ("scratch still falling at 360", phase-a-evidence.md) | 2.15 each at 360, about 4.3 at 720 | not trained |

**Architecture:** the brief says "S512 nets". Recommended: **S512+PP (architecture 8), the default's**. The scratch members already exist in it, and one architecture lets members share inference code (exp/oracle a8d08ad already accepts two networks of one architecture). Plain S-512 (architecture 2) would work the same way at somewhat lower member strength. The owner decides.

**Independence:** members must not share warm-start ancestry with each other. S512ppr3 descends from S512r2 by warm starts, and the scratch runs start from seeded random weights (ab1abce's note). Optionally, each new member could also train on a different three-quarters of the files (bagging) for more diversity.

**Ensemble sizes:**

- **E3** = {S512ppr3, scratch-s1, scratch-s2}: **0 new GPU-h**.
- **E2i** = {scratch-s1, scratch-s2}: independent only, for the offline comparison.
- **E4** = E3 + 8b's scratch run: 0 extra GPU-h when 8b runs.
- **E4n**: four new members at 720 superbatches, about 17 GPU-h (over half a week's quota). Only if E3 passes and member strength turns out to be the limit.

Scratch members are weaker than the warm lineage: on g3s2-val the scratch mean was 0.01951758 against the warm mean of 0.01909453 (nets.md, DESIGN.md §5.6 item 7). Whether the weaker members hurt the average more than their independence helps is what the tests measure.

### 2.3 Four ways to use an averaged evaluation

| method | what | engine code | CPU per label | notes |
|---|---|---|---|---|
| **M1 static** | the members' static evaluations averaged, no search | none (`fork evalfens` per member build) | negligible | relabelling with a net's static output instead of a search lost about 3 Elo (ideas.md 58, think tank B2); **a cheap control only** |
| **M2 separate searches, averaged** | each member's own build (`-DFORK_NET=...`) searches the saved position at N nodes; the K scores are averaged | none in the engine; **a relabel driver** is needed (§2.6) | K × N nodes | K different trees; the default's 20k label is one of the K inputs |
| **M3 ensemble inside one search** | one search whose evaluation at every node is the mean of the K members | yes (§2.6), a data-generation-only build | about (1 + (K − 1)c) × N node-time | one coherent tree shaped by the averaged evaluation; can also **generate games** with ensemble moves |
| **M4 targeted** | M2 or M3 only on idea 52's top-disagreement sites | as M2 or M3 | a fraction | the 8b sites arm is the natural place |

**The nps cost of M3** (estimate). exp/oracle's blend build (dcbe8fb) keeps a second S512+PP accumulator updated at every computed evaluation and runs the second output layer only where the gate fires (3.8% of evaluations). Its bench nps was **1.87-1.89 M against the base's 2.57-2.66 M** (three runs each beside data generation, indicative; the commit message), a ratio of about 0.72. That puts the extra accumulator at about c_acc ≈ 0.39 of a single net's time per node. Evaluating every member's output layer at every evaluation adds more. Rough arithmetic: an update moves about 3.1 rows of 1,024 int16 values per move (X1, ideas.md 59), while an output pass is about 1,024 multiply-accumulates at 0.54 evaluations per node (X1). That makes the output about 0.17 of the update cost, so **c ≈ 0.45 per extra member**. The ratio is then about **0.53 for K = 3** (1.9 × the time per node) and about **0.43 for K = 4** (2.35 ×). These are UNVERIFIED estimates; the quiet A/B harness measures them when the build exists. Per label at 20k nodes per member, M3 costs about 1.9-2.35 × 20k node-time against M2's 3-4 × 20k. M3 is cheaper per label, and it is the only method that changes the games themselves.

**Combining scores: win-probability space, not cp.** The trainer's target is already in win-probability space, (1 − w)σ(s/S) + wz. For M2 and M4, average p̄ = mean_k σ(s_k / S_k) with each member's own matched S (S512ppr3 89, scratch-s1 90, scratch-s2 89; 8b's member matched the same way), then store s = S_ref · logit(p̄) in the record's 16-bit score at the trainer's S_ref, so the trainer stays unchanged (as td_labels.py writes a shard copy for the unchanged trainer). Averaging in cp lets one confident outlier dominate (one member at +800 cp); win-probability averaging saturates it. **Inside a search (M3)** the evaluation must stay in cp, because the margins compare cp. The mean of scale-matched cp values (f1c's (base + second)/2 toward zero) is the simple form. A logit-mean through an integer lookup table is a possible later variant (UNVERIFIED cost).

**Mate scores (M2):** if a strict majority of members report a mate for the same side, the mate is stored (the trainer then drops it at |score| > 20,000, as today). Otherwise the members' finite scores are averaged and any mate member is left out. This is a constant to declare (§2.8).

**Variance shrink:** averaged evaluations are compressed toward 0.5 compared with any one member. fit_scale.py is rerun on the ensemble labels (S re-matched), and mean |eval| is reported for each label type.

### 2.4 How it fits idea 51 (TD labels) and idea 52 (committee disagreement)

- **The same nets serve both.** Idea 52's independent pair is two of E3's members. With K = 3-4, the committee's disagreement becomes the members' standard deviation in win probability, a better query-by-committee detector than one |a − b|. The 8b sites arm (200,000 top-D sites, being labelled by the default engine at 200,000 nodes; 8b-sites.json) is the natural M4 target: these are exactly the positions where one net's search label is least trustworthy. An E3 label at 3 × 20k = 60k nodes per site costs about 1.2e10 nodes, about **1.8 h on 2 workers** (estimate at 1.89 M nodes/s per worker).
- **Idea 51:** TD(λ) is built from a game's later stored scores, so with ensemble-relabelled games (every saved non-check record of a game relabelled in order) TD runs on ensemble scores. That makes a 2 × 2 factorial: {default labels, ensemble labels} × {the 0.5 blend, TD(0.8) or TD(0.9)}. The owner named TD(0.8) and TD(0.9) as 8b's arms.
- **The bias check idea 51 needs:** the TD pre-test's gold shared the stored labels' network. Re-scoring its declared comparison against gold labels by **scratch-s1 and scratch-s2 at 1 M nodes** on the same 5,000 sites (H) shows how much of the TD and stored-score advantage was same-network bias. This is part of step 0; its result is a **new dated section of results-8b.md, report only**, because the declaration forbids changing its rules after the results.

### 2.5 Experiment design (staged, each stage gated)

**Step 0 (offline, CPU only; shared with item 2).** Run as one `measure` job on 2 workers beside data generation.

- **Sites:** H (5,000 g3j-w05-val sites with S512ppr3 1 M-node labels) plus **H2**: 20,000 new sites drawn the same way from the same validation shard with a new seed. H2 gives the result-based yardstick enough power and needs no 1 M labels.
- **Labels:**
  - on H and H2: S512ppr3 at 20k, 50k, 60k and 100k; scratch-s1 and scratch-s2 at 20k (giving E3 and E2i at 20k per member);
  - on H only: scratch-s1 and scratch-s2 at 1 M nodes (the independent golds).
- **Yardsticks:**
  - **Y1, network-independent:** the Brier score of σ(label/S) against the game result z, on kept records with one site per game. It is noisy but no network judges it. It is still play-dependent: the games were played by S512ppr3.
  - **Y2:** the mean squared error in win probability against each of the three 1 M golds and against their win-probability mean, reported with the shared members visible. E3 shares one member with every gold, and S512ppr3 at 60k shares S512ppr3's gold, so neither gold is neutral. **A fourth gold from a net in neither candidate**, 8b's scratch run once it exists, would be.
  - 95% percentile intervals from 10,000 game resamples (declaration-8b's method).
- **Outputs:**
  - for item 2, the error-against-depth curve;
  - for item 3, E3 at 3 × 20k against S512ppr3 at 60k (**equal total nodes**), E2i against S512ppr3 at 40k, and M1 (static E3) as a floor;
  - for idea 51, the bias re-score.
- **Gate to step 2 (declared now):** E3 at 20k each beats S512ppr3 at 60k on **Y1** (point estimate) **and** on the gold-mean Y2 with its interval below 0. **Kill:** S512ppr3 at 60k is at least as good on both, meaning more nodes on one net buy the same thing. Otherwise the owner decides.
- **Cost:** 25,000 sites × (20k + 50k + 60k + 100k + 2 × 20k) nodes = 6.75e9, plus 2 × 5,000 × 1 M = 1.0e10, for **1.68e10 nodes, about 2.5 worker-hours, about 1.25 h on 2 workers** (estimate at 1.89 M nodes/s per worker). It needs a build of each scratch member (`-DFORK_NET`, netcheck and a bench reference): scratch-s1's exists on exp/oracle, scratch-s2's does not.

**Step 1 (GitHub, no new code; a premise check for M3).** In exp/oracle's blend build, the gate fires wherever the window gap is within the margin (refiner_gate.hpp). A margin far above any evaluation, set through the UCI options RefinerMarginMain and RefinerMarginQuiesce, blends S512ppr3 and scratch-s1 at almost every computed evaluation (not where both bounds are in the mate or tablebase band). **One fixed-node stage** of that "always blend" against S512ppr3 alone tests whether a K = 2 ensemble search is stronger per node, which is the premise of M3 labels at equal nodes. Whether the options' declared ranges allow such a margin is **UNVERIFIED** (not checked in options.cpp). This is report only, because fixed nodes does not charge the second network's cost (§2.3).

**Step 2 (small nets at equal data; only if step 0 passes).**

- **Positions:** about 10 M kept positions from a sealed S512ppr3 part, g3j's training shards or g4's. That is about 12.4 M saved non-check records relabelled, every saved non-check record of the chosen games, so that TD is possible.
- **Relabel arms** (M2, through the relabel driver, §2.6):
  - **C0'**: S512ppr3 at 20k through the driver, like for like with the others;
  - **C1**: S512ppr3 at K × 20k, the equal-node control;
  - **E**: the E3 mean in win probability, 20k per member;
  - optional **ES**: M1, the static E3 mean.
- **Training:** B0 shape, idea 13's recipe (§1.4), two seeds per arm. S is fitted once on C0' and the ensemble's scale is reported. Optional TD(0.8) versions of C0' and E (the factorial, +4 runs).
- **Screen:** seed-paired fixed-node stages, E against C1 (2 stages) and E against C0' (2 stages); ES against E is optional (2 stages).
- **Decision rule (declared now):**
  - **Go to step 3** if E's pooled estimate against **C1** is at least **+5 Elo** with its 95% interval above 0, and E is not below C0'.
  - **Retire** if E's point estimate against C1 is at or below 0: a deeper search by the default buys the same.
  - Otherwise the owner decides.
- **Cost (estimates):**
  - CPU, K = 3: 12.4 M × (20k + 60k + 60k) = 1.74e12 nodes, which is **about 16 h on 10 threads** at datagen's 3.05 M nodes/s per thread, or **about 26 h** at the UCI driver's 1.89 M. K = 4: 12.4 M × 180k = 2.2e12 nodes, about 20-33 h.
  - GPU: 6-8 small runs, **1.8-2.4 GPU-h** (+1.2 with the TD factorial).
  - GitHub: 4-6 fixed-node stages.

**Step 3 (at scale; only if step 2 passes).** The production form is **M3 data generation**: games played and labelled by the ensemble search. Two reasons. At scale, M2's relabel of a retrain's 150 M new kept positions (about 185 M saved non-check records × 60k) is 1.1e13 nodes, **about 4-7 days of the whole machine** (estimate), comparable to generating the data outright. M3 also changes the moves. The test then becomes an arm of item 2's design: **E3 in-search at 20k (about 1.9 × time per node) against the single-net setting at equal CPU** (about 40k nodes, or item 2's winner), and then an arm in the next retrain through the retrain gate (fixed-node screen at least +5, STC SPRT).

### 2.6 Code needed later (not now)

- **Relabel driver (for M2, M4 and item 2's relabel variant).** A fork_datagen mode or a small C++ tool. It reads a sealed viriformat shard, replays each game in order with a per-game TT cleared at game start (as in self-play), searches each saved non-check record at N nodes with the build's network, and writes a **derived shard copy** with the new scores. Moves, results and unsaved records are kept, and the manifest names the labeller and the source shard's SHA-256. Sealed data is never changed. Then a Python combiner averages K derived copies in win-probability space with the mate rule into one shard, as td_labels.py's `labels` writes a copy for the unchanged trainer. Tests:
  - a relabel at the generation's own N with the same binary reproduces the stored scores (exact if the TT and history state can be matched; otherwise a declared tolerance, UNVERIFIED which);
  - every derived shard round-trips the format reader;
  - verify_games.py passes on the derived shards;
  - the combiner's mean is checked by hand on fixtures.
- **Ensemble build (M3),** for data generation only, never in the TCEC binary:
  - a CMake list `FORK_ENSEMBLE_NETS`, generalising exp/oracle's `FORK_REFINER_NET` second-network embedding (a8d08ad: two networks of one architecture);
  - K feature stacks pushed with every move (the oracle's second FeatureStack, generalised);
  - an evaluation that is the integer mean of the scale-matched members, rounded toward zero, as GateKind::Blend;
  - the TT and the correction tables see only the blended value, so unlike the gated refiner every node has one evaluation function (no mixed-evaluation TT problem, ideas.md 59's watch item);
  - netcheck per member, and a bench reference per ensemble build;
  - fork_datagen's manifest records `"evaluator": "nnue ensemble (a, b, c)"`, which `upload_batch.py seal` must accept under the labeller-naming rule;
  - tests: K = 1 gives the single net's bench exactly; blend parity on the 446 parity positions; no_alloc; the datagen suite under TSan.
- **The trainer is unchanged** in every method: labels arrive as shard copies.

### 2.7 Side by side with idea 58 (the big teacher)

| | **Ensemble teacher (this design)** | **Idea 58: a giant teacher** |
|---|---|---|
| What labels | K independent fast nets, through search (M2 or M3) | one large, slow net (for example wider, deeper, with threat inputs), statically or inside a shallow search |
| GPU | **0** for E3 (members exist); 0 extra for E4 (8b's scratch run); about 4.3-17 GPU-h for new members (§2.2) | one Kaggle session for training. The size is not specified in ideas.md 58, so the GPU-h are unknown (UNVERIFIED); plus T4 inference for static relabelling |
| CPU per label | M2: K × 20k nodes; M3: about 1.9-2.35 × 20k node-time (estimate) | static: none on CPU. Inside a search: Fork's search with a net "far too slow for search"; at S512+X's 0.818 nps it would already cost more, and a giant net would be much slower (unmeasured) |
| Engine code | none for M2 (a relabel driver only); M3 generalises existing exp/oracle code | a new architecture in the trainer and the inference code (or a GPU inference pipeline), and a slow-net search mode for the searching variant |
| Evidence so far | for: idea 52's scratch pair (error ratio 1.6-1.7), idea 59 f1c's blend (+9.56 ± 9.45 FN at 3.8% of sites). Against or unknown: scratch members are weaker in loss; error correlation unmeasured | against: distillation from S512+X refuted (that teacher was weaker at fixed nodes, B13); static relabel lost about 3 Elo (B2). Its gate (gold error at least 10% lower) is unmeasured |
| Same-network bias | addresses the variance part directly (independent inits); shares the lineage's label bias | a teacher trained on the same labels learns their bias; measuring it against a same-net gold is circular |
| Expected gain | unknown. Its first gate, step 0, costs about 1.25 h on 2 workers | unknown. Its first gate is a Kaggle session plus the X7 gold |
| Risk | low: every stage is cheap and reversible. Main risk: no gain over C1 (more nodes on one net) | high: engineering cost, an unknown teacher strength, and evaluation against a biased gold |
| Originality | ensembles of independently initialised networks and distilling an ensemble into one model are general ML (concept level; Hansen and Salamon, "Neural network ensembles", 1990; Breiman, "Bagging predictors", 1996; Hinton, Vinyals and Dean, "Distilling the Knowledge in a Neural Network", 2015, which distils an ensemble; Lakshminarayanan, Pritzel and Blundell, "Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles", 2017; **all UNVERIFIED as exact citations, none opened**). Idea 52's query by committee covers the disagreement side. **No chess-specific prior-art search done**: required before any public claim. Fork's own nets, data and code only (strategy A+) | distillation (Hinton et al. 2015, as ideas.md 58 cites); the same data-policy footing |

### 2.8 Names and constants to screen before use

**Candidate names**, to be screened by the §8 procedure (a separate research agent; match / no match only):

- the CMake option `FORK_ENSEMBLE_NETS`;
- the C++ names `EnsembleEval`, `ensemble_eval`, `member_scale` and `GateKind::Always`;
- the fork_datagen options `--relabel`, `--relabel-out` and `--members`;
- the tools `tools/datagen/relabel_combine.py` and `tools/measure/teacher_pretest.py` (step 0);
- the combiner options `--combine wdl|cp` and `--mate-majority`;
- the part and arm names `D20`, `D50`, `D100`, `E3`, `E2i`, `E4`, `C0'`, `C1`, `ES`;
- the idea ids `label-depth` and `ensemble-teacher`.

**Constants** to be screened by the originality-checker, each with its justification:

| constant | value | justification |
|---|---|---|
| deeper saved node counts | 50,000; 100,000 | the owner's grid (2.5 × and 5 × the standing 20,000); round values, not from any engine |
| arm Hash | 3 MB; 5 MB | keeps about 4 TT entries per saved-search node, as 20k at 1 MB has (§1.2) |
| per-arm budget | 120 thread-hours | sized so that D100 keeps at least about 8 M kept positions at 400 M seen (§1.3) |
| members K | 3 (E3), 4 (E4) | the members that exist or are already budgeted (§2.2) |
| per-member nodes | 20,000 | the standing saved-search depth, so E3 is compared at equal total nodes with C1 = 60k |
| combine space | win probability, each member's matched S | the trainer's target space (§2.3) |
| mate rule | strict majority | a single member's mate is not trusted alone; placeholder, measurable on step 0's sites |
| decision bars | +5 Elo with the 95% interval above 0, seed-paired 3,200 games | the retrain gate's +5 (decisions log 2026-11-07); pairing because of idea 13's seed noise |
| step 0 sizes | H 5,000 (exists); H2 20,000 | H as declared in declaration-8b.md; H2 gives Y1 power (estimate) |

---

## 3. Recommendation

1. **Step 0 first, for both items** (about 1.25 h on 2 workers, CPU only, beside data generation, as one `measure` job). It gives:
   - item 2's error-against-depth curve;
   - item 3's gate (E3 against S512ppr3 at equal total nodes, on a network-independent yardstick);
   - idea 51's same-network bias re-score of the 8b TD pre-test.

   Step 1, one fixed-node stage of exp/oracle's always-blend build, tests M3's premise without new code, if the option range allows it (UNVERIFIED).
2. **Item 2: worth running.** It costs about 360 thread-hours (40 h wall in layout A), about 3 GPU-h and 4-6 fixed-node stages. Every arm is usable default-labelled data, so the real price is about 47.7 M kept positions (about 16 h of production) and less than a day of 8b or 8c's cadence. Run the 30-minute rate probe first.
3. **Item 3: take E3 through step 0, and to step 2 only if step 0's gate passes.** E3 needs no new GPU time. Prefer it to idea 58 as the first teacher experiment: it is cheaper at every stage, it uses nets that already search inside Fork, and it targets the same-network bias the TD pre-test exposed. Idea 58 stays parked until the ensemble's step 2 result. If the ensemble cannot beat a deeper single-net search at equal nodes, a giant teacher's case is weaker too, since both learn from the same labels.
4. **Order with 8b:** step 0 does not block 8b. Item 2's arms and item 3's step 2 relabel each displace about a day of the whole machine, so schedule them at part boundaries (decision 24: at most one part switch per day).

## 4. UNVERIFIED items

- g4's rate of 2,250-2,300 records/s on 10 threads (no committed manifest yet).
- The node model's assumptions: constant nps across node limits and Hash sizes, and unchanged shares at deeper saves (§1.6 probe).
- The exact pairing of openings across arms of different speed (§1.2).
- Small-net transfer of a label-depth result to S512+PP (§1.8.5).
- Whether two parallel T4 runs count once against the Kaggle quota; the quota itself (about 30 GPU-h per week, phase-a-evidence.md).
- The wall time of one fixed-node stage.
- M3's nps (c ≈ 0.45 per extra member is an estimate from dcbe8fb's indicative bench nps and X1's counts).
- Whether exp/oracle's margin options allow an always-firing gate.
- Whether scratch-s2 has a parity file and bench reference.
- The members' error correlation ρ.
- Whether a relabel at the generation's own N can reproduce stored scores exactly.
- Every literature citation in §2.7 (concept-level, none opened).
- No chess-specific prior-art search for ensemble labelling was done.
