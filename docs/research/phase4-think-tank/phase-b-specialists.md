# Phase 4 think tank, Phase B: the specialists

Fourteen reports, each written by a separate agent on 2026-11-07 after
reading Phase A (phase-a-evidence.md). The three clean-room surveys used
public release notes, documentation, papers, forum posts and commit or PR
messages only, never engine source code, and record no other engine's
constants. The nine specialists each followed the same standard: mechanism,
derivation, credited literature, a falsifiable prediction, the cheapest
first experiment and a kill criterion. The two skeptics then checked every
proposal's arithmetic and premises against the primary files and gave each
a verdict (SOUND / PLAUSIBLE / WEAK / REFUTED). **Read a proposal together
with its skeptic verdict** (B13 for the network side, B14 for the search
side). The ranked, deduplicated result is phase-c-synthesis.md.

Every Elo figure here is a model prediction or a placeholder unless it
cites a logged run. Nothing in this file was implemented or run against
the engine. References to `tank/...` scratch scripts are to the session's
temporary working folder (not committed).

Proposal ID prefixes: M mathematics, T training, S search theory (also S1
for the Stockfish survey's file label, by context), O tuning, ST
statistics, H systems, C chess knowledge, I search-evaluation interaction,
W wildcard.

## Contents

- B1. Clean-room survey: the Stockfish lineage (S1)
- B2. Clean-room survey: open-source NNUE engines (S2), with a Stormphrax supplement
- B3. Clean-room survey: TCEC conditions, long time controls, closed engines and Leela (S3)
- B4. Mathematics (M)
- B5. Training science (T)
- B6. Search theory (S)
- B7. Tuning and optimization (O)
- B8. Statistics and testing (ST)
- B9. Systems and hardware (H)
- B10. Chess knowledge (C)
- B11. Search-evaluation interaction (I)
- B12. Cross-domain wildcard (W)
- B13. Skeptic 1: network, training, data and evaluation knowledge
- B14. Skeptic 2: search, interaction, tuning, testing, systems and TCEC


---

# B1. Clean-room survey: the Stockfish lineage (S1)

## Survey S1: the Stockfish lineage (12 to 19) against Fork

Clean-room survey for the Phase 4 think tank (agent S1), written 2026-11-07.
**Summary.** Stockfish's NNUE era (SF 12, 2020-09, to SF 19, 2026-09, plus
the post-19 SFNNv17 net) grew in three ways that matter for Fork. (1) **Eval:**
a long run of wider nets. Then threat inputs (SF 18) paid for by a narrower
first layer, i8 threat weights and a separate threat accumulator. Then pawn
pairs (SF 19, the same idea as Fork's pawn links). It also removed things: the
small "dual" net was retired in SF 19, and the PSQT shortcut went in SFNNv17.
(2) **Search:** a steady stream of +1 to +2 Elo changes. These include
correction histories (pawn, then non-pawn, minor and continuation; "major"
was later removed), history updates on fail-low, low-ply history, capture and
cut-node LMR, post-LMR re-search depth changes, node-share time management,
and parameter sets tuned at very long TC that *fail STC and pass VLTC*. (3)
**Practice:** STC then LTC for every change, on bounds in normalized Elo, plus
non-regression bounds for simplifications. Speed is priced by time-odds
games, and when an LMR term is added, the base reduction is offset so the
mean reduction stays the same.

Against Fork's search (read in `src/search/`), the largest gaps are:
- no dynamic time management at all (static soft limit, KB time-management
  §1);
- LMR that only touches quiet moves, with no node-type, TT-PV,
  improving, TT-move-capture or history terms. The history term failed at
  −10.8, against +14 to +28 in other engines, which points to a centring
  problem;
- no improving flag in LMP or LMR;
- only the pawn correction table (undecided).

The best practice imports are cheap:
- mean-preserving LMR terms;
- checkpoint choice by fixed-node games, not by validation loss;
- a λ schedule;
- a small-odds point in the speed-to-Elo measurement;
- a combined guard SPRT after the removal round;
- long-TC SPSA for the extension parameters.

Little in Fork is something this lineage removed: Fork already lacks
killers, countermoves and check or recapture extensions. The main thing *not
to build* is a dual net, a PSQT path, or the "major" correction table (and
"material" is doubtful; see section 7.3).

Conventions:
- **SF** = Stockfish.
- Elo figures marked **(derived)** I computed from the win/loss/draw totals
  printed in the commit message. They come from SPRT-passed tests, which the
  fishtest FAQ warns are biased upward.
- "nElo" = normalized Elo.
- Fork evidence is cited as SL = `docs/history/phase-4/sprt-log.md`, DL =
  DESIGN.md §6, KB = `docs/kb/` on branch kb.
- No SF source file, diff or code view was opened. Commit messages were
  read through GitHub's commit-search API, which returns message text only.
  No SF constant, margin or layer size is recorded here.

---

## 1. The releases, 12 to 19, as their notes describe them

| Release (date) | Claimed gain vs predecessor | Headline content (concepts only) | Source |
|---|---|---|---|
| SF 12 (2020-09-02) | "at least ten times more game pairs" won than lost vs SF 11 | NNUE evaluation introduced (concept from shogi), classical eval still available; "associated tuning of the engine as a whole" | [release sf_12](https://github.com/official-stockfish/Stockfish/releases/tag/sf_12) |
| SF 13 (2021-02-19) | at least +35 Elo vs SF 12 | net retrained on billions of positions, much faster net code, "significantly improved search heuristics" | [sf_13](https://github.com/official-stockfish/Stockfish/releases/tag/sf_13) |
| SF 14 (2021-07-02) | 4x more pairs won than lost vs SF 13 | Leela-scored data mixed with SF-scored data; larger net that "deals better with large material imbalances" and "can specialize for multiple phases" (PSQT path + layer stacks); the pytorch trainer | [sf_14](https://github.com/official-stockfish/Stockfish/releases/tag/sf_14) |
| SF 14.1 (2021-10-28) | about +17 Elo | more advanced net architecture, search refinements | [sf_14.1](https://github.com/official-stockfish/Stockfish/releases/tag/sf_14.1) |
| SF 15 (2022-04-18) | +36 Elo vs SF 14 | 4th net generation; "nearly 13000 different changes" tested, "the best 200" kept | [sf_15](https://github.com/official-stockfish/Stockfish/releases/tag/sf_15) |
| SF 15.1 (2022-12-04) | 2x pairs won vs lost | net v5; FRC positions added to training data; eval normalized so +1 = 50% win chance | [sf_15.1](https://github.com/official-stockfish/Stockfish/releases/tag/sf_15.1) |
| SF 16 (2023-06-30) | up to +50 Elo | SFNNv6; inference exploiting sparsity; net compression; search tuned "particularly in longer analyses" (VLTC tune 472e726b) | [sf_16](https://github.com/official-stockfish/Stockfish/releases/tag/sf_16) |
| SF 16.1 (2024-02-24) | up to +27 Elo | SFNNv8; handcrafted eval removed; **dual NNUE** (a small net for "easily decided" positions); new Lichess-derived test book 10x larger | [sf_16.1](https://github.com/official-stockfish/Stockfish/releases/tag/sf_16.1) |
| SF 17 (2024-09-06) | up to +46 Elo | PV to mate/TB win; NUMA policy (up to 2.8x on dual-socket); "at least 6 times" faster analysis than SF 14 at equal quality | [sf_17](https://github.com/official-stockfish/Stockfish/releases/tag/sf_17) |
| SF 17.1 (2025-03-30) | up to +20 Elo | `speedtest`; thread cap lifted; TB and time-management fixes; fishtest moved to fastchess | [sf_17.1](https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1) |
| SF 18 (2026-01-31) | up to +46 Elo | **SFNNv10 threat inputs**; shared-memory net weights; "heavily refined search, utilizing Correction History" (credited with better stalemate and fortress handling); reproducible training recipes | [sf_18](https://github.com/official-stockfish/Stockfish/releases/tag/sf_18) |
| SF 19 (2026-09-05) | up to +44 Elo | **SFNNv16**: redundant threat features removed, **pawn-pair features** added; **small net retired** ("enhancing strength in positions where the small net previously underperformed"); **QAT**; all data rescored by a Leela net | [sf_19](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19) |

Pattern: about +35 to +50 Elo per major release in self-play, at a top
level with high draw rates. From SF 16 on, the notes give the net
architecture most of the credit. The 20%-time-odds table on the SF wiki
shows each version gaining about the same +28 to +35 Elo from 20% more
time ([Useful data](https://github.com/official-stockfish/Stockfish/wiki/Useful-data),
"Elo gain with time odds"; the TC of that table is not stated,
**UNVERIFIED**).

---

## 2. NNUE architecture evolution (concepts, no sizes)

Primary source: nnue-pytorch's
[nnue.md](https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md)
and [nnue_architecture_history.md](https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue_architecture_history.md)
(documentation, opened 2026-11-07), plus commit messages e8d64af1, 8e5392d7
and a17c0ce2.

1. **HalfKP (SFNNv1, 2020-08 to 2021-05).** The first architecture: inputs
   relative to the own king, kings themselves not encoded as pieces.
2. **HalfKAv2 + PSQT path + layer stacks (SFNNv2, 2021-05).**
   - Kings are encoded, merged into one plane, which saves about 8%.
   - The board is flipped for black instead of rotated.
   - The feature transformer gains a direct "PSQT" output per bucket. The
     commit says this lets the net learn piece values directly and fixes
     evaluations "skewed towards zero" in high-imbalance positions.
   - Gain: +21.7 at 10+0.1 and +5.9 at 60+0.6 (fixed-length runs; the
     commit message reports these Elo directly).
3. **Horizontal mirroring, HalfKAv2_hm (SFNNv3, 2021-08).** The board is
   mirrored so the own king sits on one half. This halves the transformer,
   and nnue.md says "the strength difference is hardly measurable". Fork's
   S-512 is mirrored too.
4. **Pairwise multiplication of the activated accumulator halves (SFNNv4,
   2022-02).** PR #3927 says it gives a non-linearity like their earlier
   sigmoid variant, "while being slightly faster". It also adds a direct
   shortcut from the first hidden layer to the output.
5. **Squared-CReLU duplicated activation (SFNNv5, 2022-05)**, then the first
   layer widened in steps (SFNNv6 to v9, 2023-05 to 2024-04). SF 16
   introduced sparse-input inference for the layer after the transformer:
   most activations are zero, so only the non-zero ones are processed.
6. **Dual NNUE (SF 16.1, 2024-01, commit 584d9efe).**
   - A much smaller net, trained only on positions with a large material
     difference, evaluates "easily decided" positions.
   - **Retired in SF 19.** The release says this improved strength exactly
     where the small net had underperformed.
7. **Full threat inputs (SFNNv10, 2025-11, commit 8e5392d7).**
   - Pairs (attacker piece on its square, attacked piece on its square),
     mirrored per perspective, added on top of HalfKAv2_hm.
   - Per nnue.md: they live in a **separate accumulator** because their
     refresh pattern differs. They are refreshed only when the king crosses
     the centre files, not on every king move.
   - **Deduplication:** a pair implied by its reverse is dropped. So are
     same-type duplicates and king-king pairs.
   - The weights are stored as **i8 and widened to i16** when accumulated.
     Measured: +5% speed on x86 and +10% on ARM, "with negligible loss".
   - nnue.md notes that a midgame position has 3-4x as many *changing*
     threat features as piece features, so memory bandwidth becomes the
     bottleneck.
   - The architecture history shows the **first layer made narrower** in
     the same commit.
   - Gains **(derived)**: STC +2.0, LTC +3.8, VVLTC +7.0. **The gain grows
     with time control.**
8. **Pruning the threat set (SFNNv11/12, 2026-02).** First piece-to-king
   threats were removed, then king-to-piece threats. One hidden layer was
   then widened (v13).
9. **Opposed-pawn features (v14), quantization changes (v14.1), pawn-pair
   inputs (v16, 2026-07; credited in ORIGINALITY.md, 2026-11-05).** Pawn-to-pawn attacks were
   removed from the threat set to avoid duplication.
10. **PSQT path removed (SFNNv17, 2026-09-30, a17c0ce2).** It passed
    non-regression at STC and LTC (derived +1.8 and +1.9), and the commit
    says training became "significantly faster".

Lessons for Fork, stated as concepts:
- SF priced threat inputs with three moves together: (a) a narrower piece
  accumulator; (b) a separate accumulator with its own refresh rule; (c) i8
  storage plus deduplication, later also cutting whole classes (king
  threats).
- Fork's S512cl was built as full recomputation per evaluation and measured
  at 0.195x nps (ideas.md 41). Most of that gap is the recomputation, not
  the idea.
- The PSQT path and the small net both helped high-imbalance positions, and
  both were later removed. Fork's endgame slice (idea 45: 351 to 8
  misjudgments of 900) attacked the same weakness through *data*, which SF's
  history suggests is the more durable route.

---

## 3. Training pipeline and data practices (concepts)

Sources: the nnue-pytorch wiki pages
[Training datasets](https://github.com/official-stockfish/nnue-pytorch/wiki/Training-datasets),
[Basic training procedure (train.py)](https://github.com/official-stockfish/nnue-pytorch/wiki/Basic-training-procedure-(train.py))
and [Training workflows](https://github.com/official-stockfish/nnue-pytorch/wiki/Basic-training-procedure-(training-workflows));
the [nettest README](https://github.com/vondele/nettest); PR descriptions
[#3927](https://github.com/official-stockfish/Stockfish/pull/3927),
[#4020](https://github.com/official-stockfish/Stockfish/pull/4020) and
[#4100](https://github.com/official-stockfish/Stockfish/pull/4100).
Leela-derived data is off-limits to Fork. Only the *processes* are noted.

1. **"What makes a good dataset: we don't really know."**
   - The wiki says better evaluations "don't always give better results",
     because there is "a tradeoff between quality and learnability", and
     datasets are chosen by experiment.
   - Fork's evidence agrees. Idea 13's cheap/expensive split-search data
     beat normal data by +65.5, and S512r2's +151 came from 5x the data plus
     a better labeller.
2. **Staged training.**
   - First train from scratch on self-play data from the engine itself. In
     SF's case that was a shallow fixed depth, then a fixed node budget; the
     wiki says the fixed-node data "produces the best playing nets for the
     UHO books".
   - Then retrain the good net on better-labelled data.
   - "Training solely on" the better data "doesn't produce as good results,
     presumably" because of coverage, or because the concepts are "too hard
     to learn from scratch".
   - Fork's warm-start recipe (S512ppr2) is the same shape.
3. **λ schedule.**
   - The first session trains on pure score targets. The retraining
     session moves λ linearly from pure score toward a score/result blend
     over the run (PR #4020 and #4100 both describe this direction).
   - Fork trains with a constant result weight of 0.5
     (`tools/train/kaggle/*.py`, `RESULT_WEIGHT = 0.5`).
4. **Checkpoints chosen by games, not loss.**
   - PR #3927: "Every 20th net was saved and its playing strength measured
     against some baseline at 25k nodes per move", to "sift good candidates
     from bad ones".
   - The trainer wiki repeats that validation loss compares runs, but
     "engine matches are needed to assess playing strength", and asks for
     several seeds.
   - Fork keeps the checkpoint with the lowest validation loss
     (`retrain_g3s2.py`, `min(curve, key=...)`).
5. **Subsampling.** "Random fen skipping" thins out correlated positions
   from the same game (PR #4020 and #3927). Fork's KB already catalogues
   filters (nnue-design.md §6.5, phase4-pipeline.md §2.2).
6. **Targeted mixing in the final round.**
   - PR #4100 mixed a significant fraction of DFRC data into the final
     training round only. That gave large FRC and DFRC gains while still
     passing for standard chess.
   - Fork's Syzygy slice is the same move for endgames.
7. **Self-play generation details (concepts).**
   - SF's generator turned shallow-depth pruning *off* while labelling.
   - It used randomized multi-PV move choice within a score window to
     diversify games.
   - Fork's datagen uses node-limited searches with the full engine search
     (pruning on) and Lichess openings, and adds no in-game randomization
     (`src/datagen/self_play.cpp`, read 2026-11-07).
8. **Reproducible recipes (SF 18).**
   - A YAML recipe chains the training stages, restarts, conversion and
     engine testing, with data and compute caching.
   - The nettest README mentions hyperparameter optimization with
     nevergrad. The recipes' contents were not opened (YAML in a code
     repository).
9. **QAT (SF 19)** and **consistent rescoring** of all data by one labeller
   (SF 19). Fork's equivalents are idea 44 (built, not run) and the recorded
   relabelling experiment (HANDOFF §6).

---

## 4. Search ideas in the NNUE era (from commit messages)

Each row lists the idea, the commit (date) and its result. "Derived" Elo is
from the message's W/L/D, as STC / LTC unless marked. The bounds shown are
fishtest's nElo bounds of the time.

| Idea | Commit (date) | Result |
|---|---|---|
| Pawn correction history (idea credited to Caissa): search-vs-static differences per pawn structure adjust the static eval | b4d995d0 (2023-12-31) | STC +1.2, LTC +1.6 (derived) |
| Material correction history (Caissa) | ddc9f48b (2024-09-09) | +1.0 / +1.1 (derived) |
| Major, minor and non-pawn (per side) correction histories (Sirius, Starzix); weights by two SPSA sessions, 75k games | 60351b9d (2024-09-17) | SPSA; result in a part of the message not read |
| Continuation correction history, last 2 moves (Motor; earlier Ice4) | 6592b13d (2024-10-12) | +0.8 / +1.6 (derived) |
| LMR adjusted by the correction magnitude, **with the base raised to keep the mean reduction** | e7e78aa0 (2024-12-22) | +1.4 / +2.0 (derived) |
| **Major correction history removed** | 831cb01c (2025-01-26) | non-regression passed, +1.5 / +1.3 (derived) |
| 4-ply continuation correction history | e18ed795 (2025-10-07) | +1.3 / +1.8 (derived); VLTC non-regression passed |
| Correction history shared between threads | 1a67ccc7 (2025-12-23) | 1 thread neutral; 8 threads +2.3 STC, +3.6 LTC; 64 threads at 60+0.6 +4.9 (derived) |
| Low-ply history kept across moves | d940e59d (2020-05-23) | passed STC and LTC |
| Root history refactored into low-ply history (a butterfly table for the first plies) | 7ac745a7 (2024-10-04) | +1.0 / +2.7 (derived) |
| Extra history bonus for the prior (opponent's) move when a node fails low, larger for bad fail-lows | 64656f85 (2022-12-24) | +1.1 / +1.4 (derived) |
| The same for a prior *capture* | 70bb317a (2024-12-08) | +1.4 / +1.3 (derived) |
| LMR on captures | 8493c8c6 (2016-08-19) | +9.7 / +1.9 (derived; pre-NNUE) |
| LMR always for captures at cut nodes | 10d2ebc6 (2019-08-21) | +3.3 / +1.5 (derived) |
| More "deeper" post-LMR re-searches at expected cut nodes | a8330d5c (2021-10-31) | +1.8 / +1.7 (derived) |
| Search-explosion detection (double extensions throttled per thread when sustained) | 73018a03 (2021-09-23) | safety fix |
| **VLTC search tune** (much more singular/double extension) | 84b1940f (2022-02-17) | **failed STC (−14.3 derived)**, LTC +3.4 (fixed 30k games), passed VLTC |
| **VLTC search tune** (~100k games at 120+1.2) | 472e726b (2023-02-24) | **failed STC (−5.9)**, LTC +0.8, VLTC 180+1.8 +5.4, SMP 8-thread VLTC +12.0 (derived) |
| VVLTC search tune (60+0.6, 8 threads; triple-extension threshold lowered "to improve scaling") | ededadcd (2024-02-03) | passed VVLTC, +3.4 (derived) |
| Check extension removed | 96837bc4 (2024-02-09) | non-regression passed STC and LTC |
| Killers removed (with a compensating fill of history so the pre-LMR **history average** did not drop) | 2343f71f (2024-07-28) | non-regression passed |
| Node-count time management ("stop when almost all nodes are on a single move"; idea credited to Koivisto) | bf2c7306 (2024-02-14) | +1.6 / +1.2 (derived) |

KB `search-techniques.md` §1 already carries SF's own removal-test "Elo
impact" figures from a 2024 snapshot (for example LMR about 117, singular
extension about 94, RFP about 40, null move about 35, futility about 13,
ProbCut about 10, IIR about 9, LMP about 8, razoring about 1). They are not
repeated here.

---

## 5. Time management and SMP (as publicly described)

- **Time management.** KB `time-management.md` (§4.2 to §4.4) already traces
  SF's lineage from commit messages. The pieces are:
  - best-move stability, made smooth in fe7b9b14, which passed LTC after
    407k games;
  - falling-eval and score-trend factors (20484ccd, 18f2b12c);
  - node-share early stopping (bf2c7306, above).
  
  The whole TM was also tuned separately at 180+1.8 by SPSA (0f01a516, per
  KB). In a mature engine each term is worth +1 to +2. In younger engines
  node share alone measured +5 to +20 (KB §4.4).
- **Speed is worth Elo, measured by time odds** (SF wiki "Elo from
  speedups", issue [#2593](https://github.com/official-stockfish/Stockfish/issues/2593)).
  - With 2020 data, small speedups were linear: about **2.1 Elo per 1% at
    10+0.1 and 1.43 at 60+0.6**.
  - Raw points at STC: 16% gave +32.4, 8% gave +13.7, 4% gave +9.0 and 2%
    gave +3.5.
  - The policy that followed: about a 0.5% speedup is needed, verified on
    several machines, with `perf stat` instruction and cycle counts
    recommended.
- **Incremental accumulator updates are worth a lot.** Turning them off cost
  46% of the speed and **−67.6 Elo at LTC** (SF wiki "The impact of
  efficient (incremental) updates").
- **Hash.** The SF wiki says keeping average hashfull **below about 30%**
  preserves strength. Losses grow fast past 50% fill (SF 15.1 data at LTC
  and VLTC).
- **SMP.** Stockfish uses Lazy SMP.
  - At fixed node budgets, efficiency falls with thread count but rises with
    the budget. The wiki extrapolates **80% or more at TCEC budgets** with
    over 300 threads.
  - 8 threads vs 1 measured +327 Elo at STC and +179 at LTC.
  - SF 18 says it refined "how threads interact". The related commits are
    correction history shared between threads (above), shared pawn history
    (969285fa) and shared continuation history (f9b002cf). Only their titles
    were read, **UNVERIFIED** detail.
  - This is Fork's Phase 6, but it is by far the largest Elo factor at TCEC
    (Threads 512; `config/tcec.json`).

---

## 6. Fishtest methodology

Sources: the fishtest wiki pages
[Creating my first test](https://github.com/official-stockfish/fishtest/wiki/Creating-my-first-test)
and [Fishtest FAQ](https://github.com/official-stockfish/fishtest/wiki/Fishtest-FAQ),
fishtest commits 8308edf4 and c56d8fff (normalized Elo), and the SF wiki.

- **Two stages for every functional change.**
  - STC 10+0.1, then LTC 60+0.6. A pass at both is needed before a pull
    request. SMP tests (8 threads) run monthly in regression testing.
  - "Scalers", patches expected to gain at longer TC, may test at 180+1.8
    on 1 thread, or 60+0.6 on 8 threads.
- **Bounds in normalized Elo since 2021-04** (fishtest 8308edf4). Normalized
  Elo is "inversely proportional to the square root of the number of games
  it takes" to detect a difference (c56d8fff).
  - Bounds seen in 2023-2026 commit messages are **narrower than Fork's at
    both STC and LTC, with a separate non-regression band for
    simplifications** (values not recorded here).
  - Fork uses [0, 3] for search, [0, 5] for nets and [−3, 0] for removals,
    all in nElo.
- **Simplifications** must be used for every functional removal. The rule:
  "even a neutral patch can fail", but simpler code does not need the
  stricter standard.
- **Unions**: at most 2 failed-but-positive trivial tweaks bundled. A
  concept "shall pass individually".
- **"Four or five tries"** on one idea is the limit, against lucky passes.
- **SPRT Elo estimates of passed patches are biased**, so a regression test
  shows less than the sum of the patches' estimates (FAQ).
- **Test cost ∝ game duration / nElo²** (FAQ, comparing books and TCs). The
  FAQ also prefers unbalanced books, measured by time-odds self-play.
- **nodestime** (node-budget clock) is used for new NNUE architectures to
  gauge "intrinsic strength". It does "not substitute tests under real TC".
  Fork's fixed-node screen is the same idea.
- **SPSA guidance.**
  - ck must be large enough to make a measurable Elo difference.
  - Tune few values at once: many values give random drift.
  - Stop a run whose values do not move after a few thousand games.
  - Long TC (60+0.6) is "best to get better scaling values".
  - The FAQ suggests fixed-length runs of 20,000 games around a direction
    for manual tweaks.
- **Speedups**: sub-1% speedups are accepted for simple patches after
  multi-machine verification; a complex patch goes through normal STC and
  LTC SPRTs instead.

---

## 7. Comparison with Fork

Fork's inventory comes from `src/search/searcher.cpp` and `searcher.hpp`,
read 2026-11-07:
- **Switches on:** TT, PVS, aspiration, mate distance, qsearch with SEE,
  butterfly history plus malus, RFP, NMP, LMR (quiet only), LMP, futility,
  SEE pruning, the TT-refined pruning eval, forced-move stop, tables, LMR
  check relief, LMR on evasions, singular extension, multi-cut, reply
  (1-ply) and follow (2-ply) tables, take history, IIR.
- **Off:** negative extension.
- **Stored but unused:** the TT-PV bit.
- **Time:** `time_budget.cpp` gives a static soft limit of one share and a
  hard limit of four shares, with no dynamic term.
- **Threads:** one search thread.
- **Planned:** batch 4 (DESIGN §5.6) and the KB catalogue (T1 to T58).

### 7.1 What the lineage has that Fork lacks, ranked

Fork-specific estimates are **mine** (marked EST). They follow one rule.
Fork's tier 2 features gained 3 to 10 times what SF reports for the same
idea:
- SF's singular-related and IIR terms are worth 1 to 2 Elo per tweak in a
  mature engine;
- Fork's IIR gained +21 at STC and +26 at LTC, and its reply table +11.5 (SL).

So for an idea that is missing entirely, I use the range other engines
reported when adding it (KB), not SF's late-stage increments.

| # | Item | In Fork's queue? | Public evidence | Fork EST (STC) |
|---|---|---|---|---|
| 1 | Dynamic TM: node share, then best-move stability, then score trend | Phase 5 (KB TM §7) | SF bf2c7306 +1.6/+1.2 (derived, mature TM); other engines +5 to +20 for node share alone (KB §4.4) | **+8 to +20** |
| 2 | LMR node-type (cut-node) and TT-PV terms | batch 4 | KB T16: SF +3.8/+6.8 (cut), +2.2/+2.9 (PV); Berserk, Halogen +7 to +9 | +4 to +10 |
| 3 | LMR on late captures (by take history), and "TT move is a capture" | **no** | SF 8493c8c6 +9.7/+1.9 (derived), 10d2ebc6 +3.3/+1.5; KB T16 (Weiss +5.8/+15) | +3 to +8 |
| 4 | Improving flag in LMP and LMR (not RFP) | listed (DL 2026-11-02), only RFP tried | SF 2013: LMP and LMR uses passed STC and LTC; KB: Alexandria +12 | +3 to +8 |
| 5 | LMR history term done SF's way: summed histories, **centred**, base offset to keep mean reduction | idea 42 (after H0) | others +14 to +28 (KB T16); SF e7e78aa0 and 2343f71f show the compensation | +3 to +10 if the failure was the offset |
| 6 | Correction tables orthogonal to pawn links: non-pawn per side, continuation (2-ply, then 4-ply) | deferred until after SPSA | SF +0.8 to +1.8 each (derived); KB lesson: about 3x at LTC (Seer) | +2 to +6 at LTC |
| 7 | Post-LMR re-search depth change (deeper when far above, shallower when barely above) | **no** (B-3's shallower re-search is a different thing) | SF a8330d5c +1.8/+1.7 (derived); KB T16 c228f319 +1.8/+1.9 | +1 to +4 |
| 8 | Fail-low bonus to the prior move (quiet and capture) | **no** (not in KB) | SF 64656f85 +1.1/+1.4, 70bb317a +1.4/+1.3 (derived) | +1 to +4 |
| 9 | Low-ply history (butterfly table for the first plies, carried across moves) | **no** (not in KB) | SF 7ac745a7 +1.0/+2.7 (derived), d940e59d passed | +1 to +3 |
| 10 | Double/triple extensions with an explosion guard | batch 4 | SF 73018a03 (guard), VVLTC tune ededadcd | 0 at STC, + at LTC (EST) |
| 11 | Threat knowledge in the net, paid for SF's way | idea 41 (held by the speed gate) | SF 18: +2.0 / +3.8 / +7.0 at STC/LTC/VVLTC (derived) | see 7.1.k |
| 12 | Lazy SMP | Phase 6 | SF wiki: +327 STC, +179 LTC for 8 vs 1 thread | huge at TCEC; 0 in Phase 4 tests |

Details for each item follow, with mechanism, evidence, transfer, the
cheapest experiment and a kill criterion.

**7.1.a Dynamic time management (item 1).**
- *Mechanism.* After each finished iteration, scale the soft limit by:
  - the share of nodes spent under the best root move (high share: stop
    early; low share: extend);
  - the number of recent best-move changes;
  - the score trend.
  The hard limit and reserve stay as they are.
- *Model.* At 8+0.08, Fork's soft limit is about 8000/30 + 0.75·80 ≈ 327 ms
  early in the game. TM gains by moving time from settled positions to
  unsettled ones. If that is worth an effective +10% to +15% of thinking
  time where it matters, then at SF's measured ~1.5 to 2.1 Elo per 1% (SF
  wiki) it gives +15 to +30. Engines without TM measured +5 to +20 for node
  share alone (KB §4.4), so I predict +8 to +20 at STC.
- *Why it fits Fork.*
  - Fork already computes each root move's node share every iteration
    (`RootEntry::share`, used by the LMR context), so the input exists.
  - Data generation is node-limited (DL 2026-10-30), so a TM change does
    **not** change the data and does not trigger the labeller policy's
    part seal.
  - TCEC's 30'+3" (the `config/tcec.json` Swiss) has a large bank, and the
    KB reports gains holding or growing at LTC in four engines.
- *Cost.* Zero nps.
- *Cheapest experiment.* Node-share scaling only, with the factor curve
  chosen by a 2- to 3-value SPRT ladder, then STC [0, 3].
- *Kill.* H0 at STC with the best ladder value. *Refuted if* the gain is
  below +3.
- *Caveat.* DESIGN puts TM in Phase 5. Pulling it forward is the owner's
  call, but nothing in Phase 4 depends on a static TM.

**7.1.b LMR terms: cut node, TT-PV, captures, TT-move capture (items 2-3).**
- *Mechanism.* Fork's LMR covers quiets only, with the log-log table and
  check relief (`searcher.cpp` lines 430-457).
  - SF reduces more at expected cut nodes and less at nodes that were on a
    PV.
  - It reduces quiets more when the TT move is a capture.
  - It also reduces late captures, by capture history.
- *Evidence.* The table above and KB T16.
- *Transfer.*
  - Fork's TT already stores the TT-PV bit (`trans_table.hpp`, flag bit 2),
    and batch 4 builds node types.
  - Capture LMR is **missing from batch 4** even though KB T16 lists it.
  - Fork's take history (+4.5, SL 2026-11-01) supplies the ordering signal
    capture LMR needs.
- *Cheapest experiment.* Capture LMR as one switch: reduce captures from
  the bad-capture stage by the quiet table's value less one ply. That is a
  derived placeholder, set by a ladder. Then STC [0, 3].
- *Kill.* H0, or nps change below −1% with no gain.

**7.1.c Improving (item 4).**
- *Mechanism.* "Improving" means the static eval is higher than two plies
  earlier, for the same side.
  - Allow fewer late quiets in LMP when not improving.
  - Reduce more in LMR when not improving.
- *Evidence.* SF 5ee16a18 and fff6b9f0 (2013) passed STC and LTC; KB T18
  and T16.
- *Fork's evidence.* The only use tried was RFP relief when rising, H0 at
  −3.78 ± 2.92 (SL 2026-11-06). That is the use with the weakest public
  record. LMP and LMR are untested.
- *Cheapest experiment.* LMP's allowance at a 2:1 ratio of improving to
  non-improving, from a ladder (2:1, 3:2). Then STC [0, 3].
- *Kill.* H0 at both ladder values.

**7.1.d Why Fork's LMR history term may have failed (item 5).**
- *Fork's result.* −10.81 ± 5.01 at STC (SL 2026-11-05). Others report +14
  to +28.
- *SF's commits show a discipline Fork did not apply.*
  - e7e78aa0: "a positive constant increase in base reduction is applied to
    counter the decrease in average reduction".
  - 2343f71f: the removal of killers "resulted in a substantial decrease in
    pre-LMR history average, so a negative history fill is applied to
    counter it".
- *Hypothesis.* Fork's butterfly history has a non-zero mean after malus
  updates (malus is applied to every earlier quiet). So the term shifted
  the *average* reduction, a de facto base-table change, as well as
  ranking moves.
- *Test.* Fork's stats build already counts `lmr_plies_sum` and
  `lmr_searches`.
  - Measure the mean reduction with the term off and on.
  - Subtract a constant so the means match.
  - Re-SPRT once, with the continuation tables summed in (idea 42).
- *Prediction.* If the offset explains the failure, the mean-matched term
  lands at 0 or better and the summed version goes positive. *Refuted if*
  the mean-matched term still loses more than 5 Elo.
- *Cost.* One stats bench and one SPRT.

**7.1.e Correction tables (item 6).**
- *Fork's evidence.* The pawn drift table was undecided at LTC, −0.35 ±
  3.72 (SL 2026-11-02), tested on S512r2.
- *New argument.* Since then the default gained 608 **pawn-link inputs**
  (S512+PP, +32.7). The net now models pawn structure directly, so the
  residual a pawn-keyed table can capture plausibly shrank further.
- *Better candidates.* Non-pawn tables keyed per side, and continuation
  tables keyed by the last moves. They target errors orthogonal to pawn
  structure. SF has both, and both passed STC and LTC.
- *Skip.* SF removed the "major" table (831cb01c), and KB T47 says the
  material table was removed in SF and Viridithas.
- *Cheapest experiment.* The non-pawn per-side table on tier2/drift's
  infrastructure, straight to LTC per Fork's list.
- *Kill.* H0, or undecided at the cap like the pawn table.

**7.1.f Post-LMR depth change, prior-move fail-low bonus, low-ply history
(items 7-9).** Each is small and cheap.
- *Fail-low bonus.* In a zero-window search the parent already rewards a
  move whose child fails low (it is the parent's cutoff). The gain comes
  from a *larger* bonus when the fail-low was severe, and from PV nodes.
  That is why SF's commits are refinements worth about +1 each.
- *Low-ply history.* It sharpens ordering near the root, where Fork orders
  only by "move to front" (`search_root`).
- *Order.* After items 1 to 6. Each gets one ladder and one SPRT.

**7.1.k Threat knowledge at Fork's speed (item 11): arithmetic, and one
proposal.**
- *Break-even.* Use a log model, Elo(speed ratio r) = E2·log2(r).
  - SF's 2020 STC points give E2 ≈ 123 to 159 Elo per doubling; LTC gives
    about 97 (16% point: 20.85 / log2(1.16)).
  - S512+X's swing (fixed nodes +25.7, STC −30.0 at 0.818x nps) implies
    E2 ≈ (25.7 + 30.0) / 0.29 ≈ 192 for Fork at STC.
  - A threat-type gain of g at fixed nodes breaks even at r = 2^(−g/E2).
    With g ≈ 26 to 31 (S512+X, XGR) and E2 = 192, r ≈ 0.90 to 0.91. That is
    exactly Fork's speed gate, so the gate is consistent with Fork's data.
  - With an LTC-like E2 ≈ 120, r ≈ 0.84 to 0.86.
  - SF 18's threat gain also *grew* with TC (+2.0 / +3.8 / +7.0), so at
    TCEC lengths the break-even moves lower again.
  - XGR-512 still failed at LTC (−30.6), so its speed loss was well past
    any break-even.
- *Cost model for S512cl done SF's way* (Fork's measured numbers, ideas.md
  41):
  - The S512r2 profile spends 17.6% on the incremental accumulator update.
  - Contact and link inputs change about 5.48 per move, against about 2 to
    3 piece-feature changes per perspective (my estimate; Fork has not
    measured it).
  - Full-width incremental threat rows would add about 0.176 × 2.2 ≈ 39%,
    so r ≈ 0.72. i8 rows (SF reports +5% on x86) bring that to about 0.75.
  - That fails the gate unless the active set shrinks a lot. SF cut king
    threats and duplicates, and that was not enough for SF either: it also
    narrowed the first layer.
- *Proposal (NOVEL for Fork, unverified whether any engine does it):* a
  **narrow threat side-accumulator**.
  - Threat and contact rows feed their own narrow accumulator, 64 to 128
    wide (a placeholder to measure).
  - It is concatenated to the 512-wide piece accumulator before the output
    layer, instead of being summed at full width.
  - Update cost scales with width, so 128 wide adds about 39% × 128/512 ≈
    10%: r ≈ 0.91 before feature-enumeration overhead.
  - nnue.md says SF keeps the two accumulators separate and "combined at
    evaluation time". The combination method and width are not stated in
    what I read (**UNVERIFIED**).
- *Prediction.* At r ≥ 0.90, the fixed-node gain keeps at least +15, so
  STC lands at 0 or better and LTC above zero. *Kill* if the fixed-node
  screen is below +15 or the identical-tree nps is below 0.90.
- *Cost.* One trainer change, one Kaggle session and one fixed-node screen.

### 7.2 Practices (testing, tuning, data) that Fork lacks

1. **Mean-preserving reduction and pruning terms** (SF e7e78aa0, 2343f71f).
   - Every new LMR or pruning term is offset so the node's average
     reduction is unchanged.
   - The SPRT then tests the term's *discrimination*, not a shift in
     overall aggressiveness, which the SPSA retune handles separately.
   - Fork already has the counters (`FORK_SEARCH_STATS`).
   - Cost: one stats bench per feature.
2. **Pick checkpoints by fixed-node games, not by minimum validation loss**
   (PR #3927; trainer wiki).
   - Fork's own data say loss is a poor proxy. S512+PP's validation loss
     "barely moved" but it gained +32.7 at STC and +46.1 at fixed nodes.
     S512+X had 2.2% lower loss and lost on speed (HANDOFF §2; DESIGN
     §5.4).
   - Cheapest: at the next retrain, convert the last 3 to 4 checkpoints of
     the best seed and play each at 800k fixed nodes against the
     minimum-loss one (1,600 games each, local or one GitHub run).
   - *Kill:* no checkpoint beats the minimum-loss one by more than its
     error bar in two consecutive retrains.
3. **λ schedule in retraining** (PR #4020, #4100; KB nnue-design §6.1 and
   §6.3).
   - Score-heavy at the start, moving toward the result over the retrain.
   - Interaction: λ changes the eval scale (KB §6.3). Fork's scale matching
     (S chosen per net) absorbs that, but the search margins see the new
     scale.
   - Cheapest: one extra seed in the next retrain with a linear schedule
     ending at Fork's 0.5, compared on the same validation set and then at
     fixed nodes.
   - *Kill:* no fixed-node gain beyond seed spread.
4. **Speed-to-Elo by small time odds, not only 2:1** (SF wiki; #2593).
   - Fork's item 4 plans 2:1 odds at STC (DESIGN line 399 and §5.4 item 8),
     which measures E2 directly.
   - The speed gate lives at r = 0.82 to 0.95. SF's points between 2% and
     16% gave E2 between 123 and 159, so log-linearity held only to about
     ±20% in SF's data.
   - Add one point at 1.15:1 (a 15% odds), about 4,000 games. It checks the
     extrapolation where the gate decides.
   - *Prediction:* if Fork's E2 ≈ 190 at STC, the 15% point gives about
     +38 ± 10 Elo (190 × log2 1.15). *Refuted if* it falls outside
     [+20, +55].
5. **A combined guard after the removal round** (fishtest simplification
   philosophy).
   - Fork's removals use [−3, 0] nElo. Fork's ratio is about 0.59 Elo per
     nElo (SL rising-RFP: −3.78 Elo = −6.37 nElo).
   - So a removal costing about 1.5 nElo (about 0.9 Elo) passes about half
     the time. Over 15 or more features, a few such losses add up.
   - A band about two-thirds as wide would cost about (3/2)² ≈ 2.25x the
     games, more than Fork's cap allows.
   - Cheaper fix: after the round, **one SPRT of "all accepted removals
     together" against the pre-round engine on [−3, 0]**. It catches
     accumulated loss for the price of one test.
6. **Long-TC tuning for scaling parameters** (SF 84b1940f, 472e726b,
   ededadcd).
   - SF's extension-heavy tunes failed STC by 6 to 14 Elo and passed VLTC
     or SMP-VLTC.
   - Fork already sends extensions straight to LTC (Testing setup), but
     item 12's SPSA is planned "STC then LTC".
   - Proposal: tune the singular and extension parameters only at LTC (or
     longer), and the pruning margins at STC.
   - Expect the LTC-tuned extension values to be *more* aggressive than the
     STC ones. *Refuted if* the LTC SPSA moves them the other way.
7. **A regression check against a fixed anchor** (fishtest FAQ: summed SPRT
   estimates are biased upward).
   - Fork's Elo chain is head-to-head SPRT estimates.
   - A fixed-length match (say 4,000 games, STC) of the current default
     against a frozen anchor (`phase-3` tag, or the S512r2-era 3902d00
     gauntlet build) gives an unbiased cumulative figure. It is cheaper
     than a gauntlet and comparable across time.
8. **Instruction counts as the noise-free speed metric** (fishtest wiki,
   "Speedups").
   - `perf stat -e instructions:u,cycles:u` on bench in WSL, beside
     `bench/ab.py`.
   - On Fork's shared, noisy machine, instructions per bench are nearly
     deterministic. That would let changes below Fork's 3% noise rule be
     judged.
9. **Check the test conditions' hash fill** (SF wiki: strength drops above
   about 30% hashfull).
   - Fork's STC is 8+0.08 with Hash 16 MB. Read the hashfull from a sample
     of STC game logs.
   - If it is high, TT-dependent features (singular, IIR, TT-PV) are
     measured under pressure that TCEC's hash cap (`config/tcec.json`)
     never applies.
10. **Explosion guard with double extensions** (SF 73018a03). Batch 4's
    double extensions should ship with a per-line cap and a node-window
    throttle, since TCEC's long searches are where explosions show.
11. **Data generation diversity** (SF generator concept). Randomized
    multi-PV choice within a score window was SF's diversity tool. Fork
    relies on 591,871 Lichess openings. It is worth a duplicate-position
    rate check on g3g before adding anything; I did not measure it.

### 7.3 What Fork has, or plans, that the lineage removed (removal and skip candidates)

| Fork item | Lineage evidence | Recommendation |
|---|---|---|
| Planned "material" and "major" correction tables (DESIGN §5.6 "Further correction tables": material listed) | SF removed major corrhist (831cb01c, non-regression passed); KB T47: material table removed in SF and Viridithas | Drop both from the plan; keep non-pawn and continuation |
| Razoring (batch 4) | SF removed it in 2020 and re-added it in 2022, worth about 1-2 Elo (KB T34); SF 2024 removal figure about 1 | Last in batch 4; accept only on a clear pass |
| ProbCut (rejected, no retest) | SF keeps it at about 10 Elo (KB §1) | No change (owner's rule). Note that SF's ProbCut sits beside cut-node logic Fork does not yet have |
| Fifty-move eval scaling (measured, off) | SF has a form | Fork's measurement stands |
| A dual or small net, a PSQT shortcut (neither in Fork) | SF 19 retired the small net; SFNNv17 removed the PSQT path (non-regression, faster training) | **Do not build** either |
| Killers, countermoves, check extension, recapture extension (none in Fork) | SF removed killers (2343f71f), countermoves, check extension (96837bc4) and recapture extension (KB T40) | Fork already matches; keep them out |
| Quadruple or unbounded extensions | Tried and removed three times in SF (KB T39) | Do not add beyond double (triple at most, LTC-tested) |
| Check relief in LMR (on; removal cost about 3, undecided) | No public SF evidence opened on its current check handling in LMR (**UNVERIFIED**) | Keep |

No current Fork search feature has public SF evidence of being harmful.
Fork's removal round (§5.6 item 11) should rely on its own SPRTs.

### 7.4 Suggested order (fits §5.6, cheapest first)

1. Practice imports 7.2.1 (mean-matched terms) and 7.2.4 (the 15% odds
   point, beside item 4). Both are nearly free.
2. In batch 4: node types and TT-PV in LMR (item 2), **plus capture LMR**
   (item 3, not yet listed); improving in LMP (item 4).
3. The LMR history term rerun with mean matching and summed tables (item 5
   folded into §5.6 item 8).
4. Next retrain: checkpoint choice by fixed-node games and a λ-schedule
   seed (7.2.2, 7.2.3).
5. TM node share (7.1.a), if the owner moves TM forward. Otherwise first in
   Phase 5.
6. Non-pawn and continuation correction tables at LTC (item 6); the narrow
   threat side-accumulator design (7.1.k) as an idea-41 variant.
7. Item 12's SPSA split by scaling class (7.2.6); the combined removal
   guard after item 11 (7.2.5).

---

## 8. Sources opened (2026-11-07)

Stockfish releases API (sf_12 to sf_19, dev pre-release 2026-11-06); nnue-pytorch `docs/nnue.md` (architecture section) and `docs/nnue_architecture_history.md`; nnue-pytorch wiki (Home, Training datasets, train.py, Training examples, Training workflows); vondele/nettest README; Stockfish PR bodies #3927, #4020, #4100; issue #2593 with comments; Stockfish wiki Useful data (also fetched, unused: Advanced topics, Regression tests, Terminology, FAQ, Home); fishtest wiki Home, Creating my first test, Fishtest FAQ (404: Fishtest-mathematics, Fishtest-Testing-Methodology, Regression-Tests); GitHub commit-search API, message text only (Stockfish: correction history, killers, countermove, check extension, low-ply history, prior countermove, hindsight, deeper LMR, cut-node reduction, improving, ttPv, capture LMR, double extension; hashes 472e726, 584d9ef, bf2c7306, e8d64af1, 8e5392d7, a17c0ce2; fishtest: normalized Elo, c56d8fff, 8308edf4). Fork (read-only): HANDOFF.md; DESIGN.md §5.6, Testing setup, §6; phase-4 sprt-log; ideas.md 41; `src/search/*`, `src/datagen/self_play.cpp`, `tools/train/kaggle/*.py` (grep); KB search-techniques, time-management, nnue-design, phase4-pipeline (sections).

## 9. What I could not verify

- The time control of the SF wiki's "20% time odds across versions" table
  is not stated on the page.
- Whether SF combines its threat and piece accumulators by summing at equal
  width or otherwise. nnue.md says only "combined at evaluation time", so
  the narrow side-accumulator proposal (7.1.k) may or may not have a
  precedent.
- The 60351b9d result: the message was cut in my read before its SPRT
  lines. The major, minor and non-pawn tables' individual gains are unknown
  (only the SPSA sessions are cited).
- SF's current handling of checks in LMR, and whether the material
  correction table is still in SF (I rely on KB T47 for "removed").
- The bodies of the shared pawn history (969285fa) and shared continuation
  history (f9b002cf) commits: titles only.
- Fork's piece-feature changes per move per perspective (about 2 to 3,
  my estimate). The 7.1.k cost arithmetic depends on it, and it should be
  measured like the contact counts in ideas.md 41.
- Every "Fork EST" figure in 7.1 is my estimate from other engines'
  reported gains and Fork's tier 2 history, not a measurement.
- Derived Elo values come from SPRT-passed tests and are biased upward
  (fishtest FAQ). Treat them as upper-leaning point estimates.
- SF's training recipes (nettest YAML) and trainer options were not opened
  (repository files). λ and skipping are described only as far as the PR
  prose states them.


---

# B2. Clean-room survey: open-source NNUE engines (S2)

## S2: what the open-source alpha-beta NNUE family does that Fork does not (clean-room survey, 2026-11-07)

**Summary.** I read the public release notes of 20 engines (19 used; one excluded, see §1), their READMEs,
about 45 pull-request descriptions (prose and result blocks only), Viridithas's public network log,
the Chess Programming Wiki's correction-history page and the CCRL Blitz list, then compared them with
Fork's search code, HANDOFF.md, DESIGN.md §5.6 and the KB. Four findings stand out.
(1) **Fork has never had an SPSA pass on its NNUE.** Every search margin still sits in bootstrap-eval
centipawns, and Fork's last four search SPRTs all failed (rising RFP −3.8, the LMR history term −10.8,
ProbCut −5.3, threat ordering −6.1). Those techniques gain in nearly every engine in this family.
In the same family, the first long-TC SPSA after a network change gave +11 to +20 Elo at LTC.
Halogen #484 and #656 and Viridithas #220 show it. I rank an early SPSA pass first; it is the
cheapest large item.
(2) **Fork's time management has no node-fraction, best-move-stability or score-trend scaling.**
Halogen measured +13.4 LTC from node TM alone, plus +4.7 from stability. Viridithas measured
+4 to +6 for each. This is the largest LTC-specific gap. Fork's plan puts it in Phase 5.
(3) **Correction histories pay as an ensemble and at LTC, not as one table at STC.** That matches
Fork's undecided pawn table. The family also found one table, keyed on material, useless and
removed it. Sharing the tables between threads is worth +20 to +44 Elo at 8 to 32 threads, which
is TCEC-relevant.
(4) **Data and network.** Five practices recur in this family:
- self-play scaled toward billions of positions;
- old, weak-labeller data purged and the newest upsampled;
- a WDL-heavier end of training;
- king buckets once data allowed;
- threat inputs, adopted at 0.85 to 0.9 of the old speed, and only after making them incremental.
Fork's S512cl, at 0.195 of the default's speed, is the opposite case. The early public records
show threat inputs losing at STC exactly as Fork's exposure inputs did. PlentyChess's first threat
net scored +45 at fixed nodes, −3 at STC and +1.8 at LTC.
I also list the removal candidates: fractional depth is about worth zero, a material correction
table cost Elo, and a pure net-output relabel cost Elo. For each item I give the cheapest Fork
experiment.

Notation: STC/LTC are each engine's own conditions (mostly 8+0.08 and 40+0.4 or 60+0.6). FN means
fixed nodes. "Pass" means an SPRT that accepted H1. Numbers come from a different engine, at a
different strength and stage, so they are priors, not predictions for Fork (KB search-techniques.md
§0 explains why). Fork evidence is cited as SL (docs/history/phase-4/sprt-log.md), HO (HANDOFF.md),
D5.6 (DESIGN.md §5.6).

---

## 1. Scope, sources and method

- **Read (2026-11-07):**
  - GitHub release notes, via the releases API (bodies only), for Viridithas, PlentyChess,
    Obsidian, Alexandria, Berserk, Ethereal, Weiss, Koivisto, Caissa, Clover, Integral, Reckless,
    Starzix, Seer, Halogen, Altair, Midnight, Sirius and Patricia;
  - the READMEs of the same projects;
  - PR descriptions (the PR conversation text, never the diff):
    - Halogen #484, 517, 575, 576, 601, 606, 638, 656, 680, 689, 698, 738, 749, 753, 757, 761, 808, 842;
    - Viridithas #31, 54, 103, 136, 155, 158, 166, 173, 174, 179, 196, 197, 206, 208, 212, 220, 229,
      263, 335, 343, 387, 390, 391, 409, 458;
    - PlentyChess #95, 227, 246, 250, 311, 325, 379, 400, 450, 457;
    - Reckless #632, #728; Berserk #603;
  - Viridithas's public network log (`notes/networkhistory.txt`, a prose and results table, not
    code);
  - CPW "Static Evaluation Correction History";
  - the CCRL 40/2 Blitz single-CPU list.
- **Not opened:** any source file, diff, patch or GitHub code or tree view. No constants, layer
  sizes or tables of another engine are recorded here. Where I say "smaller" or "wider", that is
  deliberate.
- **Stormphrax:** left out of this pass because its README contains instructions addressed to AI
  agents (ignored as data). The owner then ruled (2026-11-07) that Stormphrax is included at
  concept level like every other engine, and that the KB's existing citations stay; it is covered
  by the supplement at the end of this section.
- Fork side: `src/search/searcher.cpp`, `.hpp`, `quiet_history.hpp`, `time_budget.cpp`,
  `src/eval/nnue/accumulator.hpp`, `tools/train` (result weight), HO, D5.6, SL (drift, rising RFP,
  ProbCut, threat set), ideas.md 13 and 40-47, and KB nnue-design.md, nnue-inputs.md and
  search-techniques.md.

## 2. Where Fork sits

| Engine (best single-CPU version) | CCRL Blitz, fetched 2026-11-07 |
|---|---|
| PlentyChess 8.0.0 | 3773 |
| Reckless 0.9.0 | 3765 |
| Caissa 2.0 | 3748 |
| Viridithas 20.0.0 | 3747 |
| Obsidian 16.0 | 3746 |
| Berserk 14 | 3737 |
| Clover 9.1 | 3726 |
| Halogen 16 | 3720 |
| Ethereal 14.25 | 3683 |
| Seer 2.8.0 | 3639 |
| Altair 7.0.0 | 3579 |
| Midnight 9 | 3477 |
| Marvin 6.3.0 (a Fork gauntlet opponent) | 3458 |

Fork's last gauntlet was 3445.8 ± 21.6 (S512r2 era, HO §1). Two promotions since then add about
+53 head to head (not a gauntlet), so about 3500 is a rough guess (UNVERIFIED). The open-source top
cluster is therefore 220-280 Elo above Fork.

Most of the engines above crossed Fork's current level in 2023-2024. Their release-to-release steps
from there were +20 to +60 Elo, typically:
- a new net on more data;
- one LTC SPSA tune;
- a dozen search patches of +1 to +5 each.

No single trick closed a 250-Elo gap. Section 4's ranking follows that shape.

## 3. Engine digest (what the public record says)

Architecture terms are qualitative. "KB" means king input buckets, "mirr." horizontal mirroring,
"OB" output buckets by material, "ML" a multi-layer head after the accumulator, "TI" threat inputs,
"PP" pawn-pair inputs.

| Engine | Net (as described publicly) | Data practice | Notable per-release evidence |
|---|---|---|---|
| **Viridithas** (AGPL-3.0 now; MIT up to 20.0.0) | KB + mirr. + OB + pairwise ML (v14); TI + PP (v20) | Own self-play only (README); early nets labelled by its HCE; generations relabelled by each new net; Lichess-elite positions rescored by itself; high-node data upsampled | v13: corrhist +12.25 STC; more king buckets with a bigger dataset +23.6 STC. v14 ML: +9.4 LTC (FN +42.9). v19 "evaluation scaling" (a WDL schedule plus output rescale): +9.3 VLTC in its log. v20: activation research plus TI and PP, release +60.8 LTC |
| **PlentyChess** (GPL-3.0 per KB) | KB, ML with OB; TI (7.0.2) + PP (8.0) | Lc0 data until 2.1; own data from 3.0 (7.2 B positions, about −15 Elo for the net vs the Lc0 net); README now says 15 B+ self-generated positions and "self-distillation for part of the training" | 4.0: "a different way of generating data", STC +23.5 / LTC +41.5. #227: start-position piece distribution for datagen, +13.2 STC at equal net and data. #400: TI first net FN +45.5, STC −3.1 (fail), LTC +1.8. 8.0: +41.8 STC / +47.4 LTC |
| **Caissa** (MIT) | many KB (grown in steps), mirr., pairwise, ML with OB (2.0); QAT; factoriser | Own self-play only, purely progressive: old games purged; data grew from 0.17 B (2022) to 20.5 B (2026); SPRT games (STC+LTC) and 7-man TB endgame positions added; endgame-book self-play added | 2.0 ML: +40 LTC / +29 STC (bundle; the last layer was also SPSA-tuned). 1.26: endgame-book data **+51 on an endgame book**. 1.25: shared corrhist +6 at 4T. Its CPU trainer (12 h on a desktop for 170 M positions) was used until 1.25 |
| **Halogen** (GPL-3.0 per KB) | Single layer, then ML (#680) | Trained from zero by TDLeaf(λ) (8-16 h runs), then supervised on self-play (#517) | ML: +13.2 LTC / +6.3 STC. LTC SPSA tunes: +18.6, +20.0, +10.2. Node TM: +13.4 LTC. Pawn / non-pawn / continuation corrhist: +3.3 STC / +1.6 LTC / +2.0 STC. Sharing corrhist per NUMA node: 0 at 1T, +19.8 at 8T, +44 at 32T |
| **Integral** (no licence file per KB) | factorised KB, mirr., TI, PP, **fifty-move-rule inputs**, ML, OB (README) | Hundreds of millions of games; mostly fixed soft-node searches of tens of thousands of nodes; **5-man Syzygy guides datagen**; datasets public on Hugging Face; early HCE-era data thrown away | v8 (16.7 B positions, TI, fifty-move inputs): +99 STC / +110 LTC |
| **Berserk** (licence not read) | Mirrored KB, TI, squared clipped activation, OB (README) | About 8 B self-play positions at v9; later mixed with Koivisto data (off-limits for Fork) | v10 tried a wider layer and returned to the narrower one. #603: pairing int8 threat rows, +1.9 to +2.2% nps |
| **Reckless** (AGPL-3.0) | KB, ML; TI from 0.9 | From random weights, iterated (0.5); bullet | 0.9: +62 LTC with TI. #632/#728: setwise threat generation and SIMD incremental threat updates, each +1.8 to +2.3 at VSTC |
| **Alexandria** (GPL-3.0 per KB) | KB (from 8.0), mirr., OB, ML with dual activation (9.0) | **Lc0 data** (README); WDL and piece-count filtering; "better WDL scheduling" | 7.1: pawn, non-pawn and continuation corrhist, eval-stability TM. 9.0: ML, +28.8 LTC (bundle). 9.1: pawn history, 6-ply conthist, score-stability TM |
| **Obsidian** | ML from 15.0 | **Lc0 data** (README) | +27 to +57 per release; no details |
| **Ethereal** (GPL-3.0; NNUE commercial) | Narrow L1, grown in steps | 13.78-13.86: datasets of 100 M games, labels re-generated at rising node budgets; much larger final LR drop than tenfold; L1 widened twice on the same data; each new net used to generate the next set | 14.00 vs 13.75: +45.5 LTC (drawish book) |
| **Seer** | WDL net | Retrograde learning from 6-man EGTB, then self-play iterations | 2.3: blending game result and search score "far superior". 2.8: a net **fine-tuned exclusively on game result**, part of +50 |
| **Clover** | KB (from 4.1, +15-20), factoriser (9.0) | Self-play; data volume limited by disk ("other net arches require more data"); 9.0 mixes data from two node budgets | Releases +10 to +45 |
| **Koivisto** | Own input mapping meant to avoid overfitting "the restricted self-play dataset" | 6.0: one week for about 16.8 M games, about 1 B positions, shallow fixed-depth labels: "surpassed expectations"; 9.0 shared data with Berserk | Node-count TM introduced at 6.0 ("never tested in any other engine" then) |
| **Altair** | KB + OB | Zero-knowledge restart (HCE reset to zero, then self-play), 2-3 B positions | 7.0 |
| Starzix, Midnight, Patricia, Weiss, Sirius | Starzix on Lc0 data; Patricia on Willow data plus an "aggressive" fine-tune subset; Weiss and Sirius HCE | — | Low relevance |

Data-provenance note: Alexandria, Obsidian and Starzix train on Lc0 data, and Berserk on Koivisto
data. Their network results are therefore not evidence for Fork's self-play-only route. The
self-play-only engines are Viridithas, Caissa, Halogen, Integral, Seer, Reckless, Altair, Clover
and PlentyChess from 3.0 on.

## 4. What the family has that Fork lacks, ranked

Ranked by expected Elo for Fork at STC and LTC per unit of cost. Every Fork estimate is mine
(**EST**). The public column gives the record's number.

| # | Item | Public record (engine, condition) | Fork EST | Cost | In Fork's plan? |
|---|---|---|---|---|---|
| 1 | First SPSA pass of all search params on the NNUE | Halogen #484 +18.6 LTC / +25.2 STC; #656 +20.0 LTC; #738 +10.2 LTC; Viridithas #220 +11.6 LTC / +18.6 STC; Caissa retunes at 80+0.8 in every release | **+15 to +35** | 0.5-1 day of GitHub | yes, item 12 (late) |
| 2 | Time management: node fraction, then best-move stability, then score trend | Halogen #638 +7.9 STC / +13.4 LTC / +6.0 at 8T; #757 +2.7 / +4.7 LTC; #761 +1.2; Viridithas #54 +5.6 / +4.2; #31 +5.8 at 60+0.6; Alexandria 7.1, 9.1; Koivisto 6 | **+10 to +20 LTC** | 1-2 days | Phase 5 |
| 3 | History mechanics: linear bonus, update on TT cutoff, eval-difference update | Viridithas #196 linear +12.1 STC; #166 +3.1; #229 +11.6 STC / +2.9 LTC | **+5 to +15** | days | no |
| 4 | Correction-history ensemble (pawn, non-pawn per side, minor/major, continuation) plus its uses in pruning | Viridithas #155 first table +12.25 STC; #197 "many tables" −2.1 STC but **+8.7 LTC**; PlentyChess #95 +5.9, #246 +7.1, #250 +2.1; Halogen +3.3 / +1.6 LTC / +2.0; uses in RFP / LMR +1.7 to +1.9 | **+4 to +10 LTC** (about 0 at STC) | 2-4 days | deferred after SPSA |
| 5 | Improving flag in LMR and LMP; node types (expected cut) for NMP and LMR; TT-PV | Viridithas #154 +4.1, #151 +2.6, #90 / #91 +2.2 / +3.0; Halogen #808 NMP only in cut nodes +4.1 / +2.0 LTC, #630 LMP | **+5 to +12** | batch 4 has node types | partly |
| 6 | LMR breadth: reduce bad and late noisy moves; deeper or shallower re-search by the result | Viridithas #86 +2.8, #88 +5.9; Reckless 0.6 #30 | **+3 to +8** | days | no |
| 7 | Fail-medium returns (RFP returns a value between eval and beta; the same at the qsearch stand-pat) | Viridithas #102 +2.1; Halogen #626, #627 (passed); Alexandria 8.1 | **+1 to +4** | hours | no |
| 8 | Quiet history pruning (overlaps LMP) | Halogen #689 +1.7 STC, LTC inconclusive; Viridithas #133 +4.1 | **+1 to +4** | built | batch 4 |
| 9 | Hindsight depth adjustment; reducing the LMR depth after a small-margin fail high | Halogen #753 +1.3 STC; #743 | **+1 to +3** | hours | KB T48, unplanned |
| 10 | Shared corrhist and histories across threads | Halogen #842 +19.8 at 8T, +44 at 32T; PlentyChess #450 +3.9 at 8T; Viridithas #390 +3.9 at 4T; Caissa +6 at 4T | 0 at 1T; **large at TCEC threads** | Phase 6 | ideas.md 17 |

### 4.1 First SPSA pass now, not at item 12

**Mechanism.**
- Fork's RFP, futility, SEE, null-move, LMP, singular and aspiration constants were set for the
  bootstrap HCE (searcher.cpp header: "margins are in the bootstrap evaluation's centipawns and are
  retuned after Phase 4").
- The eval since then is a net whose error distribution is far tighter: S512ppr2 misjudges 8 of
  900 simple endings, against 351 for its predecessor.
- Pruning margins track eval error. A better eval wants tighter margins, and features layered on a
  mis-set base are judged on the wrong landscape.

**Evidence.**
- Halogen ran an LTC SPSA shortly after each net change: +18.6 LTC (#484) and +20.0 LTC (#656).
  Later tunes gave diminishing returns (+10.2, #738).
- Viridithas: two tunes, +11.6 LTC / +18.6 STC (#220).
- One caution: Halogen's VLTC tune run with 8 threads lost at 1 thread, −9.4 STC (#749). Tune at the
  condition you test.

**Fork-specific.**
- The last four search SPRTs (rising RFP, the LMR history term, ProbCut, the cheaper-attacker threat
  set) all reached H0 (SL 2026-11-05/06).
- That pattern is improbable if each were a fair +1 to +3 feature on a tuned base. It is what one
  expects when interacting margins sit far from their optimum. For example, ProbCut's margin is
  only useful relative to RFP's and NMP's. This is a hypothesis.

**Model.** The prior is the mean of the four post-net-change tunes above, about +17 LTC. Fork has
never tuned at all, so I put it at +15 to +35 STC.

**Prediction.** An SPSA at STC, about 40,000-60,000 games, then an STC SPRT [0, 5] against the
default, passes with a point estimate of +12 or more.
- Scope: params.hpp has 37 tunables, about 30 of them search. Tune the centipawn-valued margins and
  the history scales first. The small-integer depth gates (step 1) are noisy under SPSA; leave them
  fixed or give them their own ladder.
- **Refuted if** H0, or under +5.
- **Corollary test:** re-run one of batch 4's ladders on the tuned base. If its verdict flips from
  the untuned base, the "tune first" ordering is confirmed.

**Cost.** Each GitHub stage is 1,600 games in about 18 minutes, roughly 5,300 games an hour. So 50k
games is about 10 hours of shards, plus one SPRT. The FORK_TUNE build already exists (CI).

**Why it conflicts with D5.6.** The current rule is "SPSA after the search settles". I argue for a
first pass now and a second at the end; the family does exactly this. Halogen's notes list more
than a dozen SPSA tunes across releases 14-16, interleaved with feature patches. Fractional depth (idea 43) was placed "before SPSA" as a refactor; §6 argues it should
not block this.

**Kill criterion.** H0 on [0, 5] means the margins were not the problem. Keep the D5.6 order.

### 4.2 Time management that reallocates thinking time

**Mechanism.**
- Fork's soft limit is a fixed share of the clock, with a hard limit at a multiple of it
  (time_budget.cpp).
- Nothing scales the soft limit by how settled the search is.
- The family uses three signals:
  1. the fraction of root nodes spent on the best move (node TM: stop early when the best move
     absorbs most of the effort, extend when it does not);
  2. how many iterations the best move has survived (stability);
  3. the score trend versus earlier iterations (falling score: think longer).

**Evidence.**

| Signal | Halogen | Viridithas | Others |
|---|---|---|---|
| Node fraction | #638: +7.9 STC, **+13.4 LTC**, +6.0 at 8 threads | #54 (subtree sizes): +5.6 STC, +4.2 LTC | Koivisto 6 introduced node-count TM |
| Best-move stability | #757: +2.7 STC, +4.7 LTC | #31: +5.8 at 60+0.6 | Reckless 0.7 used both stability signals |
| Score trend | #761: +1.2 STC | | Alexandria 7.1 and 9.1 |

**Fork-specific.**
- The data to do this already exists: searcher.cpp records each root move's share of the iteration's
  nodes (`branch_share_`) and the root score trend (`score_trend_`) for the LMR context.
- TCEC plays long games with increment, and Halogen's gain was larger at LTC than at STC.

**Model.** The three signals are not additive. I take the node-fraction rule's two published LTC
values (+13.4, +4.2) and add a partial stability term, for +10 to +20 at LTC.

**Prediction.** A node-fraction rule alone, its two constants from a short ladder, passes STC
[0, 5] at about +5 and LTC at about +10.
- **Refuted if** the LTC SPRT gives H0 on [0, 3].

**Cost.** No nps cost. The node-fraction scaling of the soft limit is about 30 lines.

**Note.** CLAUDE.md and DESIGN put time management in Phase 5. If the owner wants Phase 4 strength
at LTC, this is the cleanest +10 available. The constants need the usual constant screen; the
idea itself is generic.

### 4.3 History mechanics (three small, independent changes)

1. **Linear bonus.**
   - Fork's cutoff bonus grows with depth squared, capped (quiet_history.hpp).
   - Viridithas's switch to a linear-in-depth bonus gained +12.1 STC (#196). Reckless 0.6 lists a
     linear history formula too.
   - Mechanism: with a gravity update, a quadratic bonus saturates entries after a few deep cutoffs,
     which compresses the ordering signal.
   - Fork's LMR history term failed at −10.8 (SL 2026-11-05). A saturated, depth-squared history is
     a plausible contributor (UNVERIFIED).
2. **Update the history on a TT cutoff.** When a TT cutoff happens at a node and the TT move is
   quiet, give it the cutoff bonus (Viridithas #166, +3.1). Fork returns at the TT cutoff without
   touching any history (searcher.cpp).
3. **Eval-difference update.**
   - After a quiet move, compare the child's static eval with the parent's.
   - A move that made the static eval much worse for the mover gets a malus, and a much better one
     a bonus, scaled and clamped.
   - Viridithas #229: +11.6 STC / +2.9 LTC.

**Prediction.** Each change passes STC [0, 3]. The linear bonus is the most likely to pass, by
+4 to +10.
- **Kill:** H0 on its ladder's best value.

**Cost.** Nothing at runtime; one ladder each. The linear bonus changes every history scale, so run
it before the SPSA pass, or tune it inside it.

### 4.4 Correction histories (focus item c)

**What the record says.**

- **First table, early in an engine's life:** Viridithas +12.25 STC (#155); PlentyChess +5.9 STC
  (#95).
- **More tables:**
  - Viridithas #197 added "a range of additional" tables: STC −2.1 (fail), **LTC +8.7** (pass).
  - PlentyChess minor/major tables: +7.1 STC (#246).
  - Continuation tables: +2.1 STC (PlentyChess #250), +2.0 STC (Halogen #698) and +1.0 STC
    (Viridithas #335, after 310,718 games).
  - Halogen non-pawn: +1.6 LTC (LLR 2.39 at 59,048 games), −2.7 STC (fail).
- **Uses beyond the eval:**
  - a larger RFP margin when the correction is large (Viridithas #263, +1.9);
  - reducing less when the correction is large (Viridithas #343, +1.8);
  - reducing more by the correction (PlentyChess #311, +1.7). The two engines' directions differ.
- **Update form:** Alexandria 9.0 and Viridithas #341 moved to a gravity-style update; CPW describes
  both an EMA and the gravity form.
- **Removed:** the material-keyed table. Removing it gained +6.0 STC and +3.3 LTC (Viridithas #208).
- **Threads:** see item 10.
- **CPW credits:**
  - Caissa (Oct 2023) as the first user;
  - Sirius for the minor and major tables;
  - Motor for the threat and continuation tables;
  - ice4 for last-move;
  - Starzix for non-pawn.

**Fork's evidence.**
- The pawn drift table at LTC was −0.35 ± 3.72 Elo after 9,984 games, undecided (SL 2026-11-02).
  Its nElo interval of −7.5 to +6.2 is fully consistent with the +1 to +3 that one pawn table shows
  in Halogen.
- The record says the value is in the ensemble and at LTC. It does not show that the pawn table
  failed.

**Prediction.** Pawn plus non-pawn (one per side) plus continuation (one and two plies), summed
with separately weighted terms, via a gravity update:
- LTC SPRT [0, 3] passes at +4 to +10;
- STC shows about 0 (Viridithas #197's pattern).
- **Refuted if** LTC H0 with an interval centred at or below 0. Then shelve the whole family for
  this net.

**Fork-specific design advice.**
- Skip the material table (removed elsewhere).
- Defer threat-keyed tables: CPW lists them, but I found no isolated result. Idea 46 lists them;
  the evidence is thin.
- Use only one key per table type.

**Cost.**
- One probe per table per node, which can be prefetched beside the TT (Caissa 1.26: prefetching
  correction entries gained +2.4 STC).
- Fork's speed-to-Elo (2 ± 1 Elo per 1% nps) means the probes must stay under about 1% of nps.
  Measure with bench/ab.py.

**D5.6 says** "deferred after SPSA". I agree with deferring, as long as it goes straight to LTC (it
is on the LTC-sensitive list).

### 4.5 Improving, node types, TT-PV

**Fork state.**
- Fork has no improving flag in use: rising RFP was rejected (−3.8, SL).
- No expected-cut-node tracking (IIR applies at every node type: searcher.cpp).
- No TT-PV use.
- Batch 4 includes "node types with their LMR uses".

**Public record.**

| Use | Result |
|---|---|
| Improving in LMR | Viridithas #154: +4.1 |
| TT-PV | Viridithas #151: +2.6 |
| Cut nodes in LMR / TT reductions | Viridithas #90 / #91: +2.2 / +3.0 |
| NMP only at expected cut nodes | Halogen #808: +4.1 STC, +2.0 LTC (Caissa 1.23 the same) |
| Improving in LMP | Halogen #630 (passed) |
| Improving in RFP | Halogen #629 (passed) |

Fork's RFP use failed. The LMR and LMP uses are the ones most often kept elsewhere.

**Prediction.** Improving in LMP (allow fewer quiets when not improving) and in LMR (reduce more when
not improving), each passes STC [0, 3]. NMP restricted to expected cut nodes passes once node types
exist.
- **Kill:** two H0s among the three means Fork's static eval along a line is too noisy for the
  signal. Drop the flag.

### 4.6 LMR breadth and re-search depth

**Fork state.**
- Fork reduces only quiet moves (`quiet` gate in searcher.cpp).
- It re-searches a reduced move that beats alpha at exactly the full depth.

**Family practice.**
- Reduce late captures too, especially losing ones, by a smaller amount (Viridithas #86, +2.8).
- Make the re-search one ply deeper when the reduced score beat alpha by a wide margin, and one ply
  shallower when it barely did (Viridithas #88, +5.9; Reckless 0.6 #30).

**Prediction.** Each passes STC [0, 3]. The deeper/shallower re-search is worth +2 to +5.
**Cost.** None at runtime. The margins need a ladder.

### 4.7 Smaller items (one line each)

- **Fail-medium returns:** return a value between the static eval and beta on an RFP cut instead of
  the eval itself (Viridithas #102, +2.1; Halogen #626).
- **Qsearch futility:** skip captures whose stand-pat plus the victim cannot reach alpha (Viridithas
  #135, +3.0). Fork has only SEE filtering in qsearch.
- **Pawn-structure history:** a quiet history keyed by the pawn hash (Halogen #575, +1.7 LTC; Alexandria
  9.1). Already in batch 4.
- **Threat-indexed main history:** history indexed by whether the from and to squares are attacked
  (Viridithas #80, +9.5; Halogen #576, +1.5 LTC / +2.9 STC; Caissa 1.13; Koivisto about +5).
  - Fork's T56 bundle failed (−6.1). It combined indexing with an escape bonus, an en-prise penalty
    and a capture-history change, under a "cheaper attacker" definition.
  - The family's version is the bare two-bit index.
  - The owner closed T56 for this net. If reopened, only as the bare index (a new idea, per the
    owner's rule).

## 5. Network and training practices Fork lacks, and how peers scaled

### 5.1 How peers at hobby compute scaled (focus item b)

**Caissa: one developer, a desktop CPU trainer until 1.25.**
- Dataset sizes per release grew roughly 1.3-2x each time: 0.17, 0.24, 0.4, 0.75, 1.2, 1.6, 1.9,
  2.3, 3.1, 3.5, 4.5, 6.9, 7.1, 9.3, 12.6, 13, 15, 17, then 20.5 B positions.
- Each release gained +15 to +35 in self-play (bundled with search work).
- The architecture grew only when the data had grown: king buckets at 2.3 B, more at 12.6 B, many
  more at 20.5 B; ML only at 20.5 B.

**Viridithas.**
- Adding 450 M fresh positions to about 0.9 B gave +7 (viri53).
- A wider net on that data gave +20 more.
- Widening further with the same data was worth about zero at LTC: FN +19, VLTC −0.2 ("sentinel").
- The same arch "with more high-quality data" gave FN +22.5 and LTC +2.9 ("inimical").
- The cleanest data-quality test: two small, identical nets, one trained on old data only and one
  on new data only, equal amounts. The new data won by FN +13.6, **STC +20.8, LTC +19.6**
  ("sol-old/sol-new").

**Koivisto.** One week of datagen, about 1 B positions with shallow fixed-depth labels, was a large jump (6.0).

**Ethereal.**
- At fixed games, raising the label node budget several-fold gave measurable gains at each step.
- A much deeper final LR decay than tenfold was adopted for every net in that series.
- L1 was widened twice on the same data.

**Fork today.**
- 1.24 B positions in g3s2, plus g3e, g3f and g3g. g3g runs at about 2,700 positions a second, about
  234 M a day on 10 threads (HO §3-4).
- That is Caissa's 2023-24 regime. **Volume is no longer Fork's binding constraint; label quality,
  recency and architecture speed are.**
- Back-of-envelope: S-512 plus pawn links has about 0.7 M first-layer weights, about 1,800 training
  positions per first-layer weight. Four king buckets on the piece rows give (4 × 768 + 608) × 512 ≈ 1.9 M weights, about 650 per weight
  (EST).
- I estimate that the bucketed engines' published dataset sizes and architecture descriptions put
  them at a few hundred per weight (UNVERIFIED). Fork could afford buckets now.

### 5.2 Ranked list (network and data)

| # | Practice | Public record | Fork EST | Cheapest experiment |
|---|---|---|---|---|
| N1 | **Purge the oldest, weakest-labeller data and upsample the newest** | Viridithas "perseverance" +8.4 LTC, "falke" +13.9 LTC, sol-new +20 STC; Caissa's purge policy | **+5 to +15 STC** | Two arms of the standard recipe on Kaggle, equal positions seen: g3s2 as is, against g3s2 minus g2s1 with g3e/g3f weighted up. Judge by an FN screen and STC. Kill: FN < +5 |
| N2 | **WDL-heavier end of training** (final superbatches at a higher result weight, on the full data) | Viridithas "eleison" (weight rising toward result, plus output rescale) +9.3 VLTC; "noumena" (final fine-tune on result only) +2.3 STC / +2.4 LTC; Seer 2.8; **but** "vestal" (fine-tune on recent data only, result only, low LR) **−57 STC**; "kismet" (material-dependent blend) −21 LTC | **+2 to +8** | Fork trains at a constant result weight of 0.5 (tools/train/kaggle/retrain.py). One warm run with the last ~20% of superbatches at a higher weight, then re-match S and FN. **Validation loss cannot compare different targets: use the FN screen** |
| N3 | **King buckets, retested** (with a factoriser, warm-started from S512ppr2) | Viridithas more buckets with a larger dataset +23.6 STC; Clover +15-20; Alexandria 8.0 (buckets added, in a release bundle) +14.9 LTC balanced / +42.3 unbalanced; Caissa at each data milestone; Viridithas: "factorisation is massive, even for fine-tuning" | **+5 to +20** (low confidence) | H-512 lost at FN (−12, round 2, 615 M). The record is from cold-trained, heavily data-limited runs. Retest: S512ppr2's weights copied into every bucket plus a factoriser, fine-tuned on g3s2. Kill: FN < +10, or nps < 0.95 (bucket refreshes; measure) |
| N4 | **SPSA on the eval scale and output buckets** | Caissa 2.0 SPSA-tuned the last layer; the KB (nnue-design §6.3) notes a net at the wrong scale lost strength | **+2 to +6** | Fork matches S to the opponent's mean absolute eval, a heuristic. One ladder S ∈ {0.9 S, S, 1.1 S}, then fold S into the SPSA of §4.1 |
| N5 | **Start-position distribution for datagen** | PlentyChess #227: +13.2 STC at equal net size and volume (its mechanism is not described; UNVERIFIED); PlentyChess 4.0's unexplained datagen change, LTC +41.5 against STC +23.5 | **+3 to +10** | Fork uses one opening file (lichess-2016-09, 0.59 M positions); lichess-2026-09 (13.9 M) is unused (HO §3). A part from the larger file at the next labeller change; compare like N1 |
| N6 | **Endgame and special-book self-play slices** | Caissa: endgame-book self-play data **+51 on an endgame book**; 7-man TB endgame positions; Halogen played out Syzygy endings; Integral's Syzygy-guided datagen | Fork has the slice (8 of 900 misjudged). Next: **endgame-start self-play** (not one-move games), to teach conversion | A small part started from ≤ 10-piece positions, labelled by Fork, run against the slice-only baseline on an endgame book. Kill: no gain on that book |
| N7 | **Fifty-move-rule inputs in the net** | Integral v8 lists them (bundled; no isolated number, UNVERIFIED) | unknown | Fork rejected search-side fifty-move scaling. An input carrying the halfmove-clock bucket costs one feature row; FN only |
| N8 | **Multi-layer head, done the family's way** (QAT, sparse first dense layer, int8 with SIMD) | Halogen #680 +13.2 LTC / +6.3 STC; Viridithas #179 +9.4 LTC (FN +42.9); Caissa 2.0, Obsidian 15, Alexandria 9.0 bundles +27 to +40 LTC | **+5 to +15 LTC** if speed holds | Fork's AF-S failed with a **32 cp quantization loss** and a speed hit. QAT (idea 44) first, then retry with a float or QAT head. Kill: qloss > 15 cp or FN < +25 |
| N9 | **Threat inputs, made cheap first** | §5.3 | +10 to +40 at TCEC TC if nps ≥ 0.85; negative below 0.8 | §5.3 |
| N10 | **Distillation from a larger Fork teacher** | Viridithas #458: student +3.7 LTC (teacher FN +35); "alembic" (distilled) −26 STC; "voltarine" and "equilibrium" (search scores replaced by a static net's output) −3; PlentyChess "self-distillation for part of the training" (no numbers) | **0 to +4** | Idea 46 lists distillation from S512+X. The record says it rarely pays and can lose. Keep it low; mix teacher outputs with search scores, never replace them |

### 5.3 Threat inputs: how the family made them cheap (focus item a)

The KB (nnue-inputs.md §1.4-§1.6) already catalogues the mechanics. What the release-level record
adds for Fork:

1. **Everyone first lost at STC.**
   - PlentyChess's first threat net (#400): FN +45.5, then STC −3.1 (failed), then LTC +1.8 (passed).
   - That is Fork's S512+X pattern (FN +25.7, STC −30.0 at 0.818 nps), only milder.
   - Months of speed work followed: incremental threat tracking, setwise generation, int8 threat
     rows, paired-row SIMD (Berserk #603, +2%), merged accumulators.
   - Release 8.0 then shows +42 STC / +47 LTC against the pre-threat release.
   - Reckless's speed PRs each bought +1.8 to +2.3 Elo at VSTC.
2. **Adopters accepted about 0.85-0.9 of the old speed** (Viridithas about 0.87 on AVX-512, per the
   KB). They paid for it by narrowing a wide first layer.
   - Fork's first layer is already narrow (512), and its output stage is a single 512×8 dot
     product, so accumulator updates are a large share of Fork's eval cost (UNVERIFIED: no profile
     read).
   - Threats change 3-4x as many features per move as pieces do (KB §1.5).
   - So for Fork, threats multiply the dominant cost rather than trading against a large
     forward-pass cost. **The family's "narrow L1 to pay for threats" trade is not available to
     Fork.**
3. **S512cl's 0.195 comes from recomputing contacts per evaluation** (D5.6: "recomputed per
   evaluation"). Every adopter updates threat features incrementally from attack-bitboard deltas
   in make-move.

**Model.** Let *u* be the share of nps spent on accumulator updates (unmeasured; I assume 0.4-0.6
for an L1-512 single-layer net, EST), and let threats multiply update cost by *k* ≈ 3-4.
- Relative speed ≈ 1 / (1 − u + u·k).
- With u = 0.5 and k = 3.5, that is 0.44.
- With incremental updates plus int8 rows, effectively k ≈ 2 at the same u: 0.67.
- With Fork's speed-to-Elo slope of 2 ± 1 Elo per 1%, 0.67 costs about 66 ± 33 Elo, which a
  +45 FN gain does not cover at STC.

**Prediction.** An incremental S512cl will not pass the 0.90 speed gate on x86-64-v3 (EST below
0.75).
- **Refuted if** a profile shows u < 0.25, or an incremental prototype measures ≥ 0.85.

**Cheapest experiment.** Do not train. First, profile S512ppr2's bench and record the time in
accumulator updates (*u*). Then count changed threat features per move over the bench positions
with a non-evaluating counter (KB §1.5's "paths that never evaluate"). The two numbers give the
expected nps before any GPU time.

**TCEC angle.** The KB records threat gains growing with time and threads, and TCEC's x86-64-v4
machine favours int8 and VNNI paths. A threat net could fail the STC gate and still be right for
TCEC. That is a decision for the owner (S512+X is already parked as an LTC candidate).

## 6. What the family removed or simplified (focus item d), and Fork removal candidates

| Removed or simplified | Record | Fork relevance |
|---|---|---|
| **Fractional ("granular") depth** | Viridithas #212 removed it: non-regression pass, +0.26 STC. PlentyChess #379 fractional depth −2.05 STC (fail), +3.25 VLTC (pass); #457 fractional extensions −2.37 STC (fail), +0.95 LTC (non-regression); #325 fractional LMR: VLTC LLR 2.44, not decisive | **Idea 43 (D5.6 item 10) is a refactor "before the SPSA retune".** The record says it is worth 0 at STC and at most +3 at very long TC. **Recommend:** do not let it gate SPSA; if built at all, test only at LTC |
| **Material-keyed correction table** | Viridithas #208: removal +6.0 STC, +3.3 LTC | Drop "material" from D5.6's further correction tables |
| **Replacing search scores with a static net's output** | Viridithas "equilibrium" (own net) −3.1 LTC; "voltarine" (a bigger teacher) −3.2 STC | **Constrains idea 47's relabel.** Relabel by **search** with the newer net, never by the static output. Viridithas's sol-new result (+20 STC for fresher search labels) supports the search version |
| **Fine-tune on recent data only at a high result weight** | Viridithas "vestal" −57 STC; "aureus" (same, lower weight) −9.7 | Fork's standard recipe (a warm start on the full snapshot) is the safe variant. Keep it |
| **Very wide or very heavy nets** | Viridithas "colossus" FN +24 / LTC −21.5; Berserk 10 went back to the narrower layer | Matches Fork's S512cl and XGR lessons |
| **Internal iterative deepening** | Viridithas #158 removed it: non-regression +0.6; IIR on shallow TT entries +2.2 (#174) | Fork already uses IIR, not IID. Consider IIR also when the TT entry is much shallower than the node |
| **History pruning removed, later restored** | Berserk 10 removed history and counter-history pruning; 11 re-added history pruning with LMR-depth use | Quiet history pruning in batch 4: use the reduced (LMR) depth in its condition, as Berserk 11 and Caissa 1.26 note |
| **Special endgame code** | Caissa removed KRvKR and KQvKQ specialty code (it caused low-time blunders) and simplified endgame eval | Fork has none beyond Syzygy. Nothing to remove |
| **"Has non-pawn material" guards** | Caissa 1.26 removed them from several pruning heuristics (the NMP zugzwang guard was not mentioned) | Fork applies the guard only to NMP, its main zugzwang protection, where TCEC endgames make it worth keeping. Not a candidate |
| **Killers, countermoves** | Removed in several engines (KB §1); Caissa went to one killer | Fork has neither: its reply/follow tables are continuation histories. Nothing to remove |
| **Twofold repetition in search** | Viridithas #206 moved to threefold (no result in the PR body; UNVERIFIED) | Fork scores one earlier occurrence as a draw inside the search. Low priority; a [−3, 0] test only if the queue idles |
| **Verification search** | Halogen +23 by removing it (KB §1) | Fork has none |

**Fork removal candidates, in order.**
1. Take idea 43 off the critical path.
2. Never build the material correction table.
3. Keep check relief: Fork measured its removal at about −3 (HO §1).
4. Revisit `use_lmr_in_check` and the other re-validation switches only in the planned removal
   round.

## 7. Suggested order (my synthesis; the owner decides)

1. **The speed-to-Elo measurement (D5.6 item 4), as planned.** It also feeds §5.3's model.
2. **History-scale fix (§4.3 item 1), then the first SPSA pass (§4.1)** at STC, roughly 50k games.
   Confirm with SPRT [0, 5].
3. **Batch 4 on the tuned base.** Order: node types plus NMP at cut nodes, improving in LMR and LMP,
   quiet history pruning with the LMR depth, the rest.
4. **Time management (§4.2)** if the owner allows it in Phase 4: STC then LTC.
5. **Kaggle, in parallel with 2-4:**
   - N1 (data purge or upsample);
   - N2 (a WDL-heavier final segment);
   - N3 (king buckets warm-started).
   Two arms each, FN screen, then STC.
6. **Correction-history ensemble at LTC (§4.4)** after SPSA, as D5.6 already says.
7. **Threats:** the profile and count of §5.3 before any training. QAT (idea 44) before any new ML
   head.
8. **Second SPSA at the end** (D5.6 item 12), at LTC.

## 8. What I could not verify

- The Fork-specific Elo estimates (all marked EST). The family's numbers are for other engines at
  other strengths. SPRT stopping bias inflates passing tests.
- Fork's actual share of time in accumulator updates (*u* in §5.3): no profile was run (I may not
  run anything). The threat-speed model depends on it.
- Fork's current CCRL-scale strength: the 3446 gauntlet predates two promotions, and +53 is head to
  head.
- The mechanism of PlentyChess #227 ("piece probability distribution for datagen positions") and of
  PlentyChess 4.0's datagen change: neither description explains the method.
- Integral's fifty-move-rule inputs: listed in its README and v8 notes with no isolated result.
- Viridithas #206 (threefold repetition): the PR body has no result.
- Viridithas v19's "trivial breakthrough in evaluation scaling" being exactly the network log's
  "eleison" entry (a WDL schedule rising toward the result, plus output rescaling, +9.3 VLTC). That
  is my reading of the log's chronology, not a stated link.
- The licences of Berserk, Seer, Clover, Obsidian, Koivisto, Midnight and Starzix: their licence
  files were not read. PlentyChess's, Halogen's and Alexandria's are taken from the KB.
- That Fork's four recent H0s share a cause in the untuned margins (§4.1): a hypothesis, testable as
  stated.
- The "few hundred positions per first-layer weight" figure for bucketed engines (§5.1): my
  estimate from public descriptions, not stated by any source.

## 9. Sources (all opened 2026-11-07)

Release notes (GitHub releases pages / API bodies):
- https://github.com/cosmobobak/viridithas/releases
- https://github.com/Yoshie2000/PlentyChess/releases
- https://github.com/Witek902/Caissa/releases
- https://github.com/KierenP/Halogen/releases
- https://github.com/aronpetko/integral/releases
- https://github.com/jhonnold/berserk/releases
- https://github.com/codedeliveryservice/Reckless/releases
- https://github.com/PGG106/Alexandria/releases
- https://github.com/gab8192/Obsidian/releases
- https://github.com/AndyGrant/Ethereal/releases
- https://github.com/connormcmonigle/seer-nnue/releases
- https://github.com/lucametehau/CloverEngine/releases
- https://github.com/Luecx/Koivisto/releases
- https://github.com/Alex2262/AltairChessEngine/releases
- https://github.com/zzzzz151/Starzix/releases
- https://github.com/TerjeKir/weiss/releases
- https://github.com/mcthouacbb/Sirius/releases
- https://github.com/archishou/MidnightChessEngine/releases
- https://github.com/Adam-Kulju/Patricia/releases
- https://github.com/Ciekce/Stormphrax/releases (read, then excluded: §1)

READMEs: the same repositories' README files (via the GitHub readme API).

PR descriptions (conversation text only), https://github.com/OWNER/REPO/pull/N:
- KierenP/Halogen: 484, 517, 575, 576, 601, 606, 638, 656, 680, 689, 698, 738, 749, 753, 757, 761,
  808, 842;
- cosmobobak/viridithas: 31, 54, 103, 136, 155, 158, 166, 173, 174, 179, 196, 197, 206, 208, 212,
  220, 229, 263, 335, 343, 387, 390, 391, 409, 458;
- Yoshie2000/PlentyChess: 95, 227, 246, 250, 311, 325, 379, 400, 450, 457;
- codedeliveryservice/Reckless: 632, 728;
- jhonnold/berserk: 603.

Other sources:
- Viridithas network log: https://raw.githubusercontent.com/cosmobobak/viridithas/master/notes/networkhistory.txt
- CPW, Static Evaluation Correction History: https://www.chessprogramming.org/Static_Evaluation_Correction_History
- CCRL 40/2 Blitz, single-CPU best versions: https://computerchess.org.uk/404/cgi/compare_engines.cgi?class=Single-CPU+engines&only_best_in_class=on&num_best_in_class=1&print=Rating+list

Fork evidence:
- HANDOFF.md §1-§6;
- DESIGN.md §5.6 and the §6 rows of 2026-10-31 to 2026-11-06;
- sprt-log 2026-11-02 (ltc-drift-vs-base), 2026-11-06 (rising-rfp, ProbCut, threat-set);
- src/search/searcher.cpp, quiet_history.hpp, time_budget.cpp;
- src/eval/nnue/accumulator.hpp;
- tools/train/kaggle/retrain.py (`RESULT_WEIGHT`);
- ideas.md 13, 43, 46, 47;
- KB nnue-design.md §3.2-§6.10, nnue-inputs.md §1, search-techniques.md §0-§2.


## B2 supplement: Stormphrax (owner ruling 2026-11-07)

**Summary.** Stormphrax (Ciekce; GPL-3.0 per the GitHub licence API; a Chess960-focused UCI engine,
successor of the author's HCE engine Polaris) is surveyed at concept level only, per the owner's
2026-11-07 ruling. Sources, all read 2026-11-07: the README, all nine release bodies (v1.0.0 to
v8.0.0), and the titles, prose and result blocks of its PRs #2-#349. No source file, diff, code view
or OpenBench tune page was opened; no layer size, learning rate, WDL value, node budget or search
constant is recorded. The README contains instructions addressed to AI agents; they were ignored as
data, per the owner's ruling. (The README also states the author does not want LLMs mining the engine
for ideas; the owner may want to weigh that.) Four findings:
1. **Data curriculum:** deeper-labelled data alone lost at STC and won only at long TC with threads;
   a staged recipe mixing old and new data recovered STC (+22.6 STC / +10.3 LTC for the last step).
2. **WDL-heavier ending:** a high-WDL fine-tune on a finished net gave about +11 STC / +13 LTC.
3. **Correction histories paid at STC** in Stormphrax, table by table: a partial contradiction of the
   open-source survey's "about 0 at STC".
4. **SPSA at the target condition:** the first post-rewrite tune gained +18 LTC; one 8-thread LTC
   tune was merged despite costing about 19 Elo at STC.

Notation: S = 8+0.08, L = 40+0.4 (60+0.6 in release tests), FN = fixed nodes, nT = threads. Numbers
are Stormphrax's own OpenBench SPRT point estimates, mostly on Elo-gainer bounds; stopping bias inflates passes.
They are priors, not predictions for Fork. EST = my estimate for Fork.

### 1. What the public record says

**Claimed Elo per release** (self-play vs the previous release, from the release pages):

| Release (date) | STC | LTC | Other | Headline content |
|---|---|---|---|---|
| 1.0.0 (2023-07) | +358 vs Polaris | +357 | FRC +466 | NNUE from random weights, five self-play generations on DFRC data ("zero" engine) |
| 2.0.0 (2023-09) | +147 | +128 | FRC +190 | singular extensions, LMP, LMR work, eval scaling, SMP stability |
| 3.0.0 (2023-11) | +57 | +45 | FRC +23 | first king-bucketed net; standard-chess data added; win-probability score normalisation |
| 4.0.0 (2023-12) | +89 | +70 | 3T +106 | new net, SMP time management, NMP verification, "tuned (almost) everything" |
| 4.1.0 (2024-03) | +38 | +27 | | large tuning run of all params, same net |
| 5.0.0 (2024-06) | +60 | +45 | | search rewritten from scratch; net twice as large yet faster |
| 6.0.0 (2024-10) | +87 | +77 | DFRC +136 | datagen bug fixed, whole dataset regenerated; TM improvements |
| 7.0.0 (2025-06) | +68 | +88 | | larger multi-layer net, MultiPV |
| 8.0.0 (2026-06) | +62 | +82 | 8T +95 | threat inputs, pawn-pawn inputs, new net |

The README claims 3747 CCRL Blitz for 8.0.0 (README only; the CCRL list was not opened for this).
Since 7.0, the LTC gain exceeds the STC gain in each release; in 8.0.0 the 8-thread gain exceeds both.

**Network (qualitative).** King-bucketed, horizontally mirrored piece inputs (#166), later more
buckets (#177); output buckets replaced a material scaling of the eval (#48, #49); pairwise
multiplication (#183). Multi-layer head (#237): FN +41, STC +8 (non-regression bounds), LTC +23;
then a dual activation on the first dense layer +6 to +12 (#239), a wider second layer merged on
long-TC faith (FN +10, STC −1.4, LTC +0.4; #286), and a skip connection (FN +4.5, STC −2.7, LTC
+1.8; #329). **Threat inputs** (#293), Stockfish-style with no king threats (the last ones removed
as a non-regression, #285): FN +33.5, STC +2.7 (37,524 games), LTC +9.9, 4T +13.0. To pay for them
the accumulator was made *narrower* and the next layer wider (#280, #293). Enabling speed work:
incremental threat updates (#289, +10 VSTC), separate piece and threat accumulators (#291, +9 S),
fused updates (#295, +2.2), sparse first-layer matmul (#246, +13.7 S). Pawn-pawn inputs (credited
to Pawnocchio, #341): FN +6.4, S +2.1, L +3.1. Quantising the whole net cost about 6 Elo, accepted
for cross-platform consistency (#233); better precision won it back (#234 +12.5 FN; #342 +3.3 S).

**Training recipe (qualitative).** Self-generated data only (README); trained with bullet. Three
stages (#242): a short low-WDL pretrain, a main stage with rising WDL, a short low-LR high-WDL stage.
A constant high-WDL fine-tune on a finished net: **+5.6 FN / +10.6 S / +12.8 L** (#238). The Ranger
optimiser: +5.8 FN / +7.3 S / +5.5 L (#240). L1-norm regularisation of the feature transformer:
FN −2.2, S +3.2 (#283).

**Data history.**

| Step | Result |
|---|---|
| Datagen bug fixed, everything regenerated, first net on it (#198) | +47.5 S |
| Data regenerated at a several-fold higher soft-node budget, "draw scaling" off, net on it alone (#311) | FN −49, S −28, L −7.4, **L 8T +13.6** ("most extreme scaling" the author had seen) |
| Stage 1 on old data, stage 2 on new data at full WDL (#314) | about +25 at FN, S and L; +17 at 8T |
| Trainer skips early plies and a random share of positions (#318) | S fail, L +3.0 |
| 0.7 B extra positions (#319) | +2.1 S / +1.1 L |
| All low-budget data purged; only SEE-passing captures dropped as noisy (#324) | +4.4 S / +2.6 L |
| New data also in stage 1 (#347) | FN +40, S −15, 8T +3.2 |
| Stage-1 data included in stage 2 (#349) | **+24 FN / +22.6 S / +10.3 L** |

**Search (selected PRs).**
- Corrections: pawn +10.6 (#163), non-pawn +7.6 (#189), continuation +8.4 (#190), major-piece +3.3
  (#188); gravity update +2.1 / +4.3 L (#220); 2- and 4-ply continuation +2.8 / +2.4 L and +2.0
  (#250, #251); larger continuation table +2.7 / +4.0 L (#327); "more corrhist" +22.7 S (#346,
  undescribed). Uses: less LMR when the correction is large (+1.4 / +2.1 L, #212), correction size
  in the RFP margin (+2.2 / +2.5 L, #230). Shared across threads, split per NUMA node: +8.6 at 4T,
  +10.6 at 8T (#282).
- History: persisting between searches +15.2 (#118), more ageing between searches +3.9 / +1.2 L
  (#345); continuation history at 1, 2, 4 plies +15 / +9.7 / +3.6 (#117, #120, #153);
  threat-indexed butterfly +7.4 (#107); capture history by defended target +3.7 / +1.6 L (#209);
  larger bonus when the static eval failed low +5.4 (#152); TT-move bonus on a TT cutoff +1.9
  (#182); one joint soft cap over a move's continuation terms +8.6 / +5.8 L (#267); main history
  mixed into the continuation update +3.9 / +1.3 L (#270); prior-countermove bonus +2.0 / +4.1 L
  (#323); ordering bonus for SEE-safe quiet checks +6.6 / +2.8 L (#320).
- Extensions and node types: singular +9.5, double +22.3, triple +4.4 (#113-#115); negative
  extension at cut nodes +8.7 (#150) and when the TT score is at or above beta +5.2 (#125); cut-node
  LMR +5.1 (#175); TT-PV uses +1 to +10 each (#144, #223, #226, #268, #298); fewer singular searches
  in formerly-PV nodes +4.0 / +4.3 L (#265).
- Eval-change rules: extend a heavily reduced move whose static eval improved, **+4.3 S / +11.9 L**
  (#253); reduce one whose eval dropped hard, +1.7 / +3.4 L (#300).
- Other: fail-firm RFP +6.8 / +2.1 L (#207); depth-dependent fail-firm +5.7 / +2.9 L (#252);
  upcoming repetition +5.8 and +16.0 (#52, #127); optimism +2.8 / +4.1 L (#301); non-pawn-material
  eval scaling +10.5 S (#200); ProbCut "p-hacked into working", **+0.6 S / +4.0 L** (#147); qsearch
  TT cutoffs +17.9 (#138), qsearch futility +7.9 (#139).
- Time management: node fraction **+11.5 S / +20.8 L** (#137, at node-scaled TCs); best-move
  stability +6.7 / +4.9 L (#197); score trend +6.2 / +2.6 L (#187); less time in decisive
  positions, non-regression (#315). The README says TM is built and tested only for increment TCs.
- SPSA: 20+0.2 tune +12.1 S / +8.6 L (#53); LTC tunes +8.3 / +13.3 L, then +4.8 / +4.7 L, then
  +4.4 L (#64, #65, #199); first tune after the search rewrite **+14.3 S / +17.7 L** (#161);
  8-thread tunes: S −2.8, L +5.6, 8T +13.7 (#321) and **S −18.7**, L −1.8, 60+0.6 8T +14.5, merged
  (#325).

**Removals and simplifications** (non-regression passes): check extensions (#67); killers (one at
#180, all at #331); twofold repetition only inside the tree (+1.25, #219); the side-to-move
dimension of the continuation correction (#326) and the side split of the non-pawn correction
(#328); NMP reduction terms (#259, #260); the LMR minimum-move rule (#215). Unmerged #333 (secondary
TT ageing, crediting a Stockfish PR) says it "curbs the enormous explosions seen in endgames at TCEC
and CCC"; it passed non-regression at S and L.

### 2. What Stormphrax reports that Fork lacks, ranked

Fork's state: src/search (switch list in searcher.hpp, time_budget.cpp), HANDOFF.md, sprt-log.

| # | Item | Stormphrax record | Fork EST | Note |
|---|---|---|---|---|
| 1 | SPSA of the NNUE-era search | #161 +18 L; #64 +13 L | **+15 to +30** | margins still in bootstrap-HCE centipawns (searcher.cpp header) |
| 2 | Node-fraction, stability, score-trend TM | #137 +21 L; #197 +4.9 L; #187 +2.6 L | **+10 to +20 L** | fixed share now (time_budget.cpp); `branch_share_` and `score_trend_` already recorded |
| 3 | WDL-heavier final fine-tune | #238 +10.6 S / +12.8 L | **+3 to +10** | Fork trains at a constant result weight; fits the warm-start recipe |
| 4 | Staged old-to-new data, old kept in the last stage | #314 +25; #349 +22.6 S / +10.3 L | **+5 to +15** | Kaggle only; see §3 |
| 5 | Correction ensemble, gravity update, thread sharing | +3 to +11 per table at S; #346 +22.7 S; #282 +10.6 at 8T | **+4 to +12** | no correction table in Fork's default |
| 6 | History: between-search ageing, eval-fail-low bonus, joint continuation cap, TT-cutoff bonus, quiet-check bonus | #345, #152, #267, #182, #320: +1.9 to +8.6 each | **+5 to +12** | Fork keeps history all game with no ageing, cleared only at ucinewgame (`clear_history`) |
| 7 | Node types: cut-node negative extension and LMR, TT-PV | #150 +8.7; #175 +5.1; TT-PV +1 to +10 | **+4 to +10** | Fork's unconditional negative extension reached H0; Stormphrax's first gain was cut-node only |
| 8 | Eval-change extension or reduction after a reduced search | #253 +11.9 L; #300 +3.4 L | **+2 to +6 L** | close to hindsight depth (open-source survey item 9) |
| 9 | Fail-firm returns | #207 +6.8 S; #252 +5.7 S | **+1 to +4** | |
| 10 | Upcoming repetition | #52 +5.8; #127 +16 | **+2 to +6** | already in batch 4 |
| 11 | Optimism; non-pawn-material eval scaling | #301 +4.1 L; #200 +10.5 S | **+1 to +5** | Fork rejected fifty-move scaling; material scaling is a separate test |

### 3. Effect on the open-source survey's top findings

- **Early SPSA: confirmed.** The first post-rewrite tune gained most; later tunes gave +4 to +5 L.
  Stormphrax tunes at the condition it targets, even merging an SMP-LTC tune that lost about 19 at
  STC (#325). For TCEC: choose the target condition first; an STC-only tune may under-serve LTC.
- **Node-share TM: confirmed and strengthened.** Its largest single LTC search gain (+20.8, #137);
  each later signal added +3 to +5 at LTC.
- **History mechanics: confirmed.** Between-search ageing (#118, #345) is a cheap Fork gap. The bare
  threat index passed again (#107), matching the advice to retest only the bare index, never T56.
- **Correction ensembles: partly contradicted.** Every Stormphrax table passed at STC (+3 to +11;
  #346 +22.7). The survey's "about 0 at STC" rests mainly on Viridithas #197. Revised view: first
  tables pay at STC; marginal ones show at LTC. Fork's undecided LTC pawn table fits either reading.
  Thread sharing (+10.6 at 8T) again supports idea 17 for TCEC.
- **Threat inputs: confirmed.** Large FN gain, near-zero STC, growing at LTC and with threads (#293).
  Stormphrax paid by narrowing its accumulator, a trade the survey says Fork cannot make at 512. Its
  incremental-update and accumulator-split PRs were each worth about +9 to +14, supporting "profile
  and make them incremental before training".
- **Data recency: refined.** Purging low-budget data passed (#324) and fresh deeper data is the
  biggest lever (#311, #314, #349). But the deeper data *alone* lost 28 at STC, and keeping old data
  in the final stage was worth +22.6 STC. For Fork's N1: purge the weakest-labeller data, but test
  "old, then new, then both" rather than a hard cut-over, judged at STC and LTC. Label depth
  changes TC scaling; a link to idea 13's split-search result is plausible (UNVERIFIED).
- **Removals: consistent.** Stormphrax removed killers and check extensions; Fork has neither (no
  check extension found in searcher.cpp). It *added* NMP verification as a non-regression (#205),
  against Halogen's removal gain: neutral for Fork, which has none.
- **ProbCut (Fork H0, −5.3 STC):** Stormphrax's was neutral at STC and +4.0 at LTC (#147). That
  supports "no retest" at STC, but leaves an LTC-only retest open.

### 4. Removal candidates for Fork

None beyond the open-source survey's. The record supports keeping Fork free of killers and check
extensions, building any future correction table without a side-to-move split (#326, #328), and
dropping king threat features in any S512cl redesign (#285). Do not delete Fork's
`use_negative_extension` (off) before a cut-node-only retest, once batch 4's node types exist.

### 5. Credits (all opened 2026-11-07)

- README: https://github.com/Ciekce/Stormphrax ; licence GPL-3.0 per
  https://api.github.com/repos/Ciekce/Stormphrax/license
- Releases: https://github.com/Ciekce/Stormphrax/releases (v1.0.0 to v8.0.0)
- PR descriptions (conversation text only), https://github.com/Ciekce/Stormphrax/pull/N, N in:
  output buckets 48, 49; corrections 163, 188-190, 212, 220, 230, 250, 251, 282, 326-328, 346; history 107, 117, 118, 120,
  152, 153, 182, 209, 267, 270, 320, 323, 345; search 52, 113-115, 125, 127, 137-139, 144, 147, 150,
  175, 187, 197, 200, 205, 207, 219, 223, 226, 252, 253, 265, 268, 298, 300, 301, 315; SPSA 53, 64,
  65, 161, 199, 321, 325; network 166, 177, 183, 233, 234, 237-240, 242, 246, 280, 283, 285, 286,
  289, 291, 293, 295, 329, 341, 342; data 198, 311, 314, 318, 319, 324, 347, 349; removals 67,
  180, 215, 259, 260, 331; unmerged 333.
- Stormphrax credits threat-input ideas to Monty, Yukari, PlentyChess, Stockfish and Reckless (#293),
  and pawn-pawn inputs to Pawnocchio (#341).

### What I could not verify

- What "draw scaling" in the old datagen was (#311, #324): not described.
- What #346 "northphrax: more corrhist" added, and what "northphrax" names: result block only.
- Whether #144 ("reduce more when ttpv") means what its title says: it reads against common
  practice, and there is no prose.
- The #137 and #161 test conditions (13+0.13 to 70+0.70): presumably node-rate-scaled OpenBench TCs
  during the rewrite.
- The 3747 CCRL figure (README only). Forum posts were not searched. All Fork EST values.


---

# B3. Clean-room survey: TCEC conditions, long time controls, closed engines and Leela (S3)

## S3 survey: what TCEC's long time controls and big hardware demand of Fork (clean room)

**Summary.** At TCEC every engine Fork would meet runs 256-512 threads with 256 GiB of hash. My
analysis of all 624 Swiss 10 games in TCEC's public archive shows what that means. The top
alpha-beta engines search **5-20 G nodes and depth 37-45 per move** in the middlegame. Fork's STC
screen sees about 0.5 M nodes and depth in the teens per move, roughly 14 doublings less. Games
are long (median 81.5 moves; decisive games median 91). Openings are heavily biased: **303 of
310 decisive games were White wins**. Measured against those conditions, single-thread STC/LTC
testing hides four things.

1. **Fork has no parallel search at all.** The `Threads` option only sizes the hash clear; the
   search is one thread (`src/uci/session.cpp`, DESIGN.md Phase 6). Public scaling data put the
   gap between 1 and 512 threads at several hundred Elo. That is more than everything else in
   this file combined.
2. **Depth-dependent search rules and STC tunes can turn "anti-scaling".** Stockfish's own
   commit record shows this repeatedly: tunes and reduction tweaks gain at STC and lose at
   VLTC, while extension changes lose at STC and gain at 180+1.8. Fork's §5.6 items 11-12 (the
   re-validation and the SPSA retune) are exactly where this bites.
3. **Long-TC time management.** Every top engine at TCEC spreads its move times 2-4x between
   the median and the 90th-percentile move. Fork has no dynamic term, even though it already
   computes the per-root-move node shares that node-share TM needs.
4. **SMP engineering decides nps at 512 threads.** This covers NUMA placement, shared counters
   and hash warm-up. Stockfish reports up to 2.8x nps from NUMA awareness alone on dual-socket
   100+ core machines.

Smaller items:
- TT pressure at TCEC is **not** negligible for Fork. By my arithmetic it is comparable to STC
  with 16 MB in the opening phase.
- 7-man Syzygy is worth only a few Elo. Its real risks are DTZ reads from the HDD and
  correctness on long DTZ.
- Contempt has no supporting evidence at this level.

The closed and premier engines (Dragon, Torch, Revenge, Ginkgo, rofChade, Ethereal commercial)
publish almost nothing technical. The useful public material is Lc0's blog, Stockfish's
documentation and commit messages, CPW and TCEC's own data. I recommend no change to the Phase 4
order. I do recommend:
- a scaling lane: an Elo-per-doubling ladder plus VLTC spot checks, at a stated cost;
- node-share TM as Phase 5's first experiment;
- an explicit "TCEC readiness" note that Phase 4 results are 1-thread results.

Method: only public prose and data were read: TCEC JSON/PGN archive, TCEC pages already
summarised in the KB, CPW, the Stockfish wiki and release notes, Stockfish and Reckless commit
messages and release pages (message text only, no diffs), talkchess threads, the Lc0 blog, the
AlphaZero preprint, and AMD and GitHub specification pages. No engine source was opened, cloned
or downloaded. No other engine's constants are recorded here; where a commit message stated a
number, only the direction of the change is described. The TCEC game statistics below are
observed behaviour from public games (time, depth, nodes), not code constants. Nothing was
written to the KB (orchestrator's override). Pages opened are listed in §7.

---

## 0. Fork's current state (verified in the code, branch phase-4, 2026-11-07)

| Area | Fork today | Where |
|---|---|---|
| Parallel search | **None.** `Threads` (1-4096) is declared, but it is used only to pick the number of workers for the hash clear. One `Searcher` runs on one search thread. Per-thread search state is already isolated in `Searcher` (DESIGN Phase 3 note), and TT entries are self-verifying (the key XORed with a digest of the data), ready for lockless sharing. | `src/uci/session.cpp` lines ~174, ~224; `src/search/trans_table.hpp` header; DESIGN.md §5 "Phase 6" |
| Time management | Soft limit = one share (the clock less the overhead, divided by 30 or by movestogo, plus three quarters of the increment). Hard limit = four shares, capped by a reserve of a tenth of the clock. The soft limit is checked only between iterations. Iteration-growth rule against the hard limit. Forced-move stop. **No dynamic term.** | `src/search/time_budget.cpp`; `searcher.cpp` ~816-828 |
| Root node shares | **Already computed** every iteration (each root move's per-mille share of the iteration's nodes), but used only as an LMR input for the next iteration | `searcher.cpp` ~798-806 |
| TT | 64-byte buckets of five 12-byte entries; 24-bit check; 8-bit age; 8-bit depth; qsearch results stored at depth 0; Lemire range reduction (exact up to 4 TiB) | `trans_table.hpp` |
| Depth-indexed tables | LMR table clamps depth at 63 (fine; TCEC root depths for top engines are 37-60 in the middlegame and higher in endgames); history bonus capped; `MaxPly` 250 | `lmr_table.hpp`, `quiet_history.hpp`, `score_bounds.hpp` |
| Draw score | 0; table cursed wins and blessed losses at ±1; no contempt | `searcher.cpp` ~75-78 |
| Syzygy | Fathom; WDL in search from `TableProbeMinDepth`; root DTZ; 3-4-5 locally only | `endgame_tables.*`, HANDOFF §3 |
| Testing | STC 8+0.08 with Hash 16; LTC 40+0.4 with Hash 64; UHO book; 1 thread; Syzygy 3-4-5. The "Straight to LTC" list covers extensions, IIR, TT-PV uses, correction history and capture history; everything else is decided at STC (DESIGN Testing setup, 2026-11-06) | HANDOFF §5; DESIGN ~1295 |

---

## 1. TCEC conditions that 1-thread STC/LTC testing does not reveal (ranked by plausible Elo)

### 1.1 What TCEC actually looks like: Swiss 10 archive analysis (new, primary data)

Source: tcec-chess.com archive, `TCEC_Season_30_-_Swiss_10_{1..624}.pgn`, plus `_Schedule.sjson`
and `_Crosstable.cjson`, fetched 2026-11-07. Each move's comment carries the engine's depth `d`,
seldepth `sd`, move time `mt`, time left `tl`, nps `s`, nodes `n`, hashfull `h` (percent as the
engine reports it), `tb` hits and more. My scripts (scratchpad, not repo) parsed every game.

**Format facts (Swiss 10, 30'+3", 48 engines, 13 double rounds):**
- Results: 314 draws, 303 White wins, 7 Black wins.
- Terminations: 303 + 6 mates, 247 TCEC draw rule, 47 threefold, 17 fifty-move rule,
  3 insufficient material, 1 disconnect.
- **No time forfeits** occurred in the event itself.
- Pair outcomes over 312 game pairs:
  - one engine wins with White and holds with Black: 186 pairs (128 + 58);
  - both draws: 64;
  - both White wins: 55;
  - a Black win appears in 7.
- **The Swiss is decided by converting a biased White position and surviving the reverse.**
- Game length: median 81.5 moves (mean 86.7, p90 130).
  - Decisive games: median 91 moves. Draws: median 63.5.
  - Median remaining moves: 71.5 at move 10, 43 at move 40, 32 at move 60, about 20-22 from
    move 80 on.
- Score compression: the winner scored 17.5/26 and the last engine 7.5/26. Engines rated
  3377-3755 cluster at 13-14 points. Potential (rating 3377) scored 13.5, the same as Obsidian
  (3733).
  - With 26 games, a score's standard deviation is about 1.8 points (Fork's arithmetic:
    √(26 × p(1−p) × (1 − draw rate)), roughly).
  - **The Swiss result is a very noisy function of Elo.** The Cat 3+4 playoff (12 DRR, 48 games
    per engine in S30) is the real gate for Fork, and there Elo does matter.
- Hardware used: nearly every engine ran `Threads=512` (some 256 or 500) with `Hash=262144`.
  - The Cat 3+4 playoff used the same settings: Cinder ran 512 threads and 256 GiB.
  - Serendipity chose 256 threads, 20 GiB and a raised Move Overhead
    (`Category_3+4_Playoff_1.pgn` header).

**Search statistics of the top alpha-beta engines (middlegame, moves 15-30; medians):**

| Engine (final place) | Threads | depth | nodes/move | nps | move time p50 / p90 | clock left at move 40 / 60 / 80 |
|---|---|---|---|---|---|---|
| Stockfish (1) | 506 | 37 | 8.4 G | 277 M | 30 s / 65 s | 415 / 42 / 11 s |
| PlentyChess (2) | 512 | 43 | 11.0 G | 280 M | 37 / 108 | 284 / 93 / 14 |
| Reckless (3) | 512 | 35 | 8.1 G | 258 M | 30 / 110 | 327 / 4 / 4 |
| Integral (5) | 512 | 41 | 3.6 G | 140 M | 24 / 90 | 573 / 274 / 135 |
| Torch (6) | 512 | 42 | 7.7 G | 259 M | 28 / 78 | 602 / 158 / 14 |
| Berserk (16) | 500 | 44 | 13.7 G | 480 M | 28 / 97 | 509 / 191 / 59 |
| Obsidian (21) | 512 | 39 | 10.1 G | 305 M | 33 / 90 | 348 / 127 / 40 |
| KomodoDragon (33) | 256 | 38 | 8.6 G | 218 M | 36 / 89 | 423 / 157 / 76 |

Readings (my interpretation; the per-move fields are as TCEC records them):
- **Depth regime.** Middlegame depths of 35-45 and node counts of 4-14 G per move are about
  10⁴ times Fork's STC budget. Fork at STC: about 2.3 M nps (bench nps on a loaded machine,
  nets.md S512+PP) × about 0.2 s ≈ 0.5 M nodes. Every depth-gated rule, log-depth reduction and
  depth-scaled margin runs at TCEC in a range Fork's tests never visit.
- **Time shape.** The top three run their clock down hard. Stockfish has 42 s left at move 60
  and Reckless 4 s; both then live on the 3-second increment for the rest of a game whose median
  is 81.5 moves. Integral, Dragon and Berserk keep much more.
  - Fork's formula keeps much more late (my simulation of `plan_time` at 30'+3", book exit at
    move 9):
    - every move spending exactly the soft limit: 631 s at move 40, 332 s at move 60, 179 s at
      move 80;
    - moves overrunning the soft limit by 1.4x (iteration granularity): 393 / 149 / 55 s.
  - So Fork plans like the conservative half of the field.
  - Which shape is better at 30'+3" is not settled by this data: Stockfish and Integral finished
    1st and 5th with opposite shapes.
- **Dynamic spread.** In moves 15-30, every top engine's 90th-percentile move takes 2.2-3.7
  times its median move. That is the footprint of stability, score-trend and node-share terms
  (time-management.md §4.2-4.4). Fork's only spread comes from iteration overshoot.
- **First move out of book.** Only Stockfish spends markedly more on it: the median ratio of
  the first move to the next five is 2.39. All others sit at 0.86-1.55. This is not a common
  practice; low priority.
- **Hashfull.** Engines report 8-33 % in moves 0-15 at 256 GiB, falling later. The definitions
  differ by engine (some report 90-100 % throughout), so only the order of magnitude is usable:
  the TT is meaningfully loaded in the opening phase even at 256 GiB.

### 1.2 Ranked list

| # | What 1-thread STC/LTC hides | Plausible Elo at TCEC conditions | Evidence |
|---|---|---|---|
| 1 | **Parallel search exists at all** (1 vs 512 threads) | **+200 to +450** for Fork vs its own 1-thread self. Central guess about +300 (**UNVERIFIED** extrapolation, derivation below) | Stockfish wiki "Useful data": 8 threads vs 1 at 60+0.6 = +178.6 ± 14 (1,000 games), and +327 at 10+0.1. Grant (talkchess t=76190, 2020-12-30), Ethereal-NNUE at 10+0.1: 2 vs 1 core +86, 4 vs 2 +76, 8 vs 4 +63. SMT 384 vs 192 threads about +20 (Noobpwnftw, as quoted by Grant). Stockfish wiki: about 80 % or more efficiency projected for 300+ threads at TCEC TCs if nps scales (an extrapolation) |
| 2 | **Depth scaling of search rules and tunes** (extensions, reductions, depth-gated conditions, SPSA results) | ±5 to ±25 summed over the parameter set (**UNVERIFIED**; SF's single changes move 1-3 Elo at VLTC each, and a whole STC tune can be anti-scaling) | SF commits (messages only, below): f030a1c5 (2023-05) VLTC tune: failed STC, neutral LTC, passed 180+1.8 and 8-thread 60+0.6. 36db936e (2023-12) VLTC tune: passed VLTC and VLTC SMP, neutral LTC. 6db47ed7 (2024-05) reduction adjustments: +4.28 ± 0.8 at STC but −1.48 ± 1.0 at VLTC. adfddd2c (2025-09) notes that STC/LTC tunes are "susceptible to become anti-scaling", with two examples reverted at VVLTC. 78532af9 (2023-03) more singular extensions: −2.5 at STC, passed 180+1.8 and 8 threads. 37bd1e77 (2024-01) more double extensions: failed STC fast, passed VLTC and VVLTC. 54cf2266 (2024-11) reverted a VLTC regression "since depth modifications affect scaling". 5372f81c (2022-05) a depth-gated singular-extension condition that "should have nearly no influence at STC as [the threshold depth] is rarely reached" |
| 3 | **Time management at long Fischer TC with long games** (dynamic terms, the time curve) | +5 to +20 (node share alone +5 to +20 in nine engines, often larger at LTC) | time-management.md §4.2-4.4 (Ethereal, Alexandria, Stormphrax, Weiss and Halogen results at 40+0.4 and 60+0.6); §1.1 above: every top TCEC engine has a strongly dynamic profile |
| 4 | **nps at 512 threads** (NUMA, false sharing, polling, hash warm-up) | 0 to +70 relative to a naive SMP (a 2x nps loss at about 30-50 Elo per doubling at TCEC depths; **UNVERIFIED** for Fork) | Stockfish 17 release notes (2024-09-06): NUMA policy, "speedups of up to 2.8x" on dual-socket 100+ core systems. Wasp author (talkchess t=68154, 2018-08): per-thread data allocated on one node cost "almost 50 %" of speed in TCEC 12. Zulli (t=71027, 2019-06-17): Stockfish's local/remote memory-access ratio was 1.0 against Cfish's 1.8, which per-thread local allocation explains. Kaufman (CPW Komodo, 2018-10): Komodo needed "several minutes to reach full speed" with large hash on many cores until fixed. Reckless v0.9.0 notes: NUMA-aware threads; SMP test +70.9 ± 3.2 at 8 threads 20+0.2 (with other changes) |
| 5 | **Eval quality vs speed trade-off** shifts toward quality at huge node counts | 0 to +15 for "slow-but-smart" nets (**UNVERIFIED**; Fork's own LTC data shows no recovery within noise) | Stockfish wiki: SF14 → SF17 is worth about 6x time at STC but about 16x at LTC, so quality gains are worth more doublings at long TC, and Elo per doubling falls with TC (from the same table: about 59 Elo per doubling near 40-80 s, about 42 near 240-480 s; Fork's arithmetic). Fork: XGR-512 −34.4 at STC → −30.6 at LTC (sprt-log 2026-11-02), unchanged within ±12 |
| 6 | **TT pressure, layout and latency at 256 GiB** | 0 to +5 | §2.E arithmetic below; Stockfish wiki hash table: below about 30 % average hashfull costs nothing measurable, and Elo falls fast as hashfull exceeds 50 % |
| 7 | **7-man Syzygy in search** | +0 to +5 Elo; one time loss costs a full point | Stockfish wiki: 6-man vs none +2.7 ± 1.4 for SF15 at STC, +10.6 ± 2.3 at 60+0.6 in the HCE era. CPW Syzygy: Stash's author put the TCEC value at about 5 Elo (2021-03-25). Ethereal 14.00 commercial notes (talkchess p=942809, 2023-02-08): several Syzygy fixes "geared toward" TCEC's 7-man (long DTZ, wide DTZ tables, read-ahead on Linux, root filtering), with the Elo "hard to quantify" |
| 8 | **Contempt and draw handling in a Swiss** | about 0 (no evidence of gain at this level) | §1.1: biased exits make White wins the decisive mode; Lc0's WDL contempt posts (2023-07-20, 2024-03-24) report no measured Elo; CPW Contempt Factor lists only anecdotes |

**Derivation for row 1.**
- Ethereal-NNUE's measured per-doubling gains at 10+0.1 decline by about 12 % a doubling
  (86 → 76 → 63).
- Continuing that decay over the 8 core doublings from 1 to 256 cores gives
  86 + 76 + 63 + 55 + 48 + 42 + 37 + 33 ≈ 440. SMT adds about 20 (Grant's quote).
- Stockfish's own data show each doubling is worth less at longer TCs, so I halve it: about 230.
- The range is therefore about 230-460.
- This is Fork against a 1-thread Fork. Against opponents who all have SMP, a 1-thread Fork
  plays at roughly 1/150 to 1/300 effective time odds.
- **Nothing in Phase 4's queue is in the same league for TCEC.** For CCRL Blitz 1-CPU ratings
  and for Fork's STC/LTC SPRTs it is worth exactly 0, which is why no current test shows it.

---

## 2. What Fork lacks for that environment

Each item follows the brief's standard. Items A, D and E are Phase 6, F is Phase 5 or 8. B and C
touch Phase 4's own items 11-12 and are the only ones I would act on before Phase 4 closes.

### A. Lazy SMP (Phase 6), designed for 512 threads from day one

- **Mechanism.** N threads search the same root. They share only the TT; histories and stacks
  are per thread (Fork's `Searcher` already holds them). They are kept diverse by staggered
  depths: a helper skips an iteration when enough other threads are already at that depth or
  deeper. This is the scheme Grant, the Wasp author and the Rodent author describe in "Lazy SMP
  and 44 cores" (talkchess t=68154, Aug-Nov 2018; Rodent reported no gain beyond 16 threads
  before the skip scheme and a clear gain after).
- **Lineage:**
  - CPW Lazy SMP: Marcel coined the name (2012-12-27); Homan and Sedlak developed it further;
    Stockfish 7 adopted it (2016-01).
  - Result selection is either the main thread's move (Cheng, Ethereal: Grant reports that
    picking the best thread did not work for him) or a vote weighted by score and depth
    (Berserk; PlentyChess's multi-move voting; CPW).
  - Wasp reports both about equal (t=68154).
- **Quantitative model.** About +60-90 Elo for 2 vs 1 thread at STC, and less per doubling
  after that (Grant's data). This is the acceptance yardstick for Fork's first prototype.
- **Fork fit:**
  - TT entries are already torn-write-proof (Hyatt-Mann style, CPW Shared Hash Table; Hyatt and
    Mann, ICGA J. 25(1), 2002).
  - Per-thread state is already isolated.
  - The open design questions are already listed in DESIGN Phase 6: thread agreement,
    diversity, and memory per thread.
- **Falsifiable prediction.**
  - A minimal prototype (shared TT, depth skipping, main-thread move) scores ≥ +50 Elo at
    2 threads vs 1 at STC on a quiet machine.
  - A result below +30 means a bug or a contention problem (e.g. shared counters).
- **Cost:**
  - Speed: none at 1 thread if the code paths are guarded; the TT accesses become relaxed
    atomics (DESIGN).
  - Cheapest experiment: an nps-scaling check (bench at 1, 2, 4 and 6 threads on the quiet
    6-core PC, with datagen paused), then a 2-thread vs 1-thread SPRT on GitHub at concurrency 2
    per 4-vCPU runner.
- **Kill criterion:** none for SMP itself (mandatory). Kill a specific diversity or voting
  scheme if it is not ≥ 0 against main-thread-only at 4 threads.
- **Timing advice:**
  - Do not pull SMP into Phase 4.
  - Do add one line to Phase 4's close: "all Phase 4 Elo figures are 1-thread; TCEC readiness
    requires Phase 6".
  - Every new piece of search state added in Phase 4 should be per-thread or explicitly
    shareable. That costs nothing now and saves a refactor.

### B. A scaling lane for depth-sensitive changes (applies to Phase 4 items 11-12 now)

- **Mechanism.** Changes whose effect depends on depth can flip sign between 0.5 M and 10 G
  nodes per move:
  - extension and reduction formulas;
  - depth-gated conditions;
  - margins multiplied by depth;
  - whole-vector SPSA tunes.
- **Evidence:** the Stockfish commit series in §1.2 row 2.
  - Seven independent cases across 2022-2025 in which the STC verdict and the VLTC verdict
    disagreed.
  - Fishtest's response was a VLTC (120+1.2 to 180+1.8) and VLTC-SMP gate for tunes and for
    depth-related changes.
- **Transfer argument for Fork:**
  - Fork's LTC (40+0.4) is only about 2.3 doublings above STC. TCEC is about 14 above.
  - Fork's "Straight to LTC" list already covers extensions, IIR and TT-PV. It leaves
    reductions and pruning to STC alone.
  - SF's strongest anti-scaling case was exactly a reduction tweak: +4.3 at STC, −1.5 at VLTC
    (6db47ed7).
  - Fork's §5.6 item 12 (an SPSA retune) is the highest-risk item: an STC SPSA optimises the
    whole vector for the STC depth regime.
- **Quantitative model.** Let an effect be linear in log₂(nodes): E(n) = a + b·log₂(n / n_STC).
  - SF's 6db47ed7 has a ≈ +4.3 and E ≈ −1.5 about 4 doublings later, so b ≈ −1.4 Elo per
    doubling.
  - At TCEC (about 14 doublings) that projects to about −15 Elo for a change that passed STC
    comfortably.
  - The linearity is an assumption (**UNVERIFIED**); the point is that a sign flip within
    4 doublings is documented.
- **Cheapest experiments:**
  1. Run the SPSA retune's output through an LTC SPRT **and** one VLTC non-regression run:
     120+1.2, Hash 256 MB, bounds [−3, 1], 2 stages.
  2. For batch 4 and later items, move these from STC-only to LTC: reduction-formula changes
     with a large STC gain (> +8), node-type-dependent LMR (batch 4) and double extensions
     (already listed).
- **Cost:**
  - A 40+0.4 game is about 2.3 min (Fork's arithmetic: 2 × (40 + 0.4 × about 80 moves) s).
  - At 120+1.2 a game is about 6.5 min, so a 1,664-game stage takes about 3x an LTC stage.
  - **UNVERIFIED** whether one VLTC stage fits GitHub's per-job time limit; split it across
    more shards if not.
- **Falsifiable prediction.** At least one of the SPSA-retuned parameters' gains will be
  smaller at VLTC than at STC. The retune as a whole will show a lower point estimate at VLTC
  than at STC. Refuted if VLTC ≥ STC within error.
- **Kill criterion.** If three consecutive scaling checks agree with STC within error, drop
  the VLTC step for that class of change.

### C. Elo-per-doubling ladder: the number that converts STC evidence to TCEC value

- **Mechanism.** Measure Fork-vs-Fork at 2:1 node odds at several budgets, using fixed nodes
  for determinism, or at 2:1 time odds at STC, LTC and VLTC. Then fit Elo per doubling as a
  function of log₂(nodes).
- **Why it matters for Fork specifically:**
  - Fork's speed gate (0.90 of the default's nps) and its nps-to-Elo planning figure (2 ± 1 Elo
    per 1 % nps; HANDOFF §5) are STC numbers.
  - At TCEC the Elo per doubling is lower: Stockfish's table falls from about 59 to about
    42 per doubling over one 6x step in TC.
  - So the TCEC-optimal network is slower and more accurate than the STC-optimal one.
  - S512+X (FN +25.7, nps 0.818) is already parked as an "LTC/TCEC-conditions candidate"
    (sprt-log 2026-11-05). Without this curve the parking has no decision rule.
- **Quantitative model.**
  - Value at TCEC = FN gain at depth − s_TCEC × |log₂(nps ratio)|.
  - For S512+X: log₂ 0.818 = −0.29, so it breaks even at s_TCEC ≈ 89 Elo per doubling, if its
    fixed-node gain survives at TCEC depth.
  - Fork's STC pair (FN +25.7, STC −30.0) implies an effective s near 190, which is implausibly
    high. So part of the fixed-node gain does not carry into timed play even at STC (the
    sprt-log already says so; **UNVERIFIED** why).
  - Hence the second half of the experiment: the fixed-node gain itself must be measured at a
    larger node budget.
- **Cheapest experiment:**
  - (i) The §5.6 item 4 time-odds measurement, extended from STC alone to STC plus one LTC
    stage.
  - (ii) A fixed-node doubling ladder: Fork(N) vs Fork(2N) at N = 0.2 M, 0.8 M and 3.2 M nodes.
    About 1,600 games each. CPU cost: about 80 moves × 3N nodes per game at about 1.5-2.3 Mnps
    per vCPU, so about 1-6 hours of 64 GitHub slots in total, the largest N dominating (Fork's
    estimate).
  - (iii) The best FN-positive, STC-negative net pair re-run at FN 6.4 M nodes instead of 0.8 M.
- **Falsifiable prediction.** Elo per doubling falls by at least 20 % from N = 0.2 M to
  N = 3.2 M. Refuted if it is flat, in which case STC speed rules can be trusted for TCEC.
- **Kill criterion.** If the fixed-node gain of the slow net shrinks with N at least as fast as
  Elo per doubling does, slow nets stay rejected for TCEC too.

### D. NUMA-aware placement and SMP hygiene (Phase 6)

TCEC's machine: 2x EPYC 9754, each with 128 cores / 256 threads, 256 MB L3, 12 memory channels
and 460.8 GB/s per socket (AMD product page, opened 2026-11-07). TCEC runs 512 threads, so SMT
is in use.

- **Mechanism:**
  1. Pin each search thread to a NUMA node.
  2. Have each thread allocate and first-touch its own `Searcher` (histories, stacks), so that
     memory is local.
  3. Interleave the TT across nodes. Fork's parallel first-touch clear already does this if the
     clearing workers are spread across nodes.
  4. Replicate the network weights per node.
  5. Keep node counters per thread and sum them on demand.
  6. Let only the main thread poll the clock (time-management.md §4.8: Reckless #707 and #797,
     +6.1 at 8 threads).
- **Evidence:** §1.2 row 4. Stockfish reports up to 2.8x on dual-socket 100+ cores; the Wasp
  author lost almost 50 % to remote per-thread data; Cfish vs Stockfish local/remote ratios.
- **Fork-specific transfer:**
  - Fork's network is about 1.4 MB (HANDOFF §1), small next to the 16 MB L3 shared by each
    group of 8 Zen 4c cores. Weight replication should matter less than it does for engines
    with much larger nets (**UNVERIFIED**).
  - Per-thread histories and the TT are the remote-memory risk. The TT is unavoidably half
    remote unless it is split per node, which would break sharing.
- **Cheapest experiment:**
  - No dual-socket machine is available. The 6-core PC has one NUMA node, and GitHub runners
    are presumably single-node (**UNVERIFIED**).
  - So the cheapest is design-level plus an instrumentation hook: report nps per thread group
    in `info` lines.
  - The first real measurement is TCEC's own testing slot, which TCEC grants before events
    (competition.md §2 "Builds and submission").
  - A rented dual-socket box is possible (netcup is pinned in DESIGN), but that is an owner
    decision.
- **Prediction.** On a dual-socket host, threads allocating their own state lose < 10 % nps
  against a single-socket run per core; main-thread allocation loses > 25 %.
- **Kill criterion.** Replication of the weights is dropped if it gains < 3 % nps on a
  dual-socket test.

### E. TT behaviour at 256 GiB: pressure, latency and the replacement policy

- **Arithmetic (Fork's, assumptions marked).** Fork's TCEC nps is unknown.
  - Scale: bench about 2.3 M nps on the 7600X3D, × about 0.55 for the EPYC's lower clock,
    × about 0.6 per SMT thread, × 512 threads ≈ 390 M nps. **UNVERIFIED**; the observed field
    is 140-480 M nps.
  - Capacity: 256 GiB / 64 B × 5 = 21.5 G entries.
  - An opening-phase move of about 35 s writes up to about 13 G entries, i.e. about 0.6 of
    capacity per move. Qsearch results are stored, so writes are close to nodes; this is an
    upper bound.
  - Fork's STC: about 0.5 M nodes per move into 1.4 M entries, about 0.35 per move.
  - Fork's LTC: about 2.3 M into 5.6 M, about 0.4 per move.
  - **So TCEC's opening-phase TT pressure is at least as high as Fork's test conditions.** The
    common intuition "huge hash, replacement doesn't matter" is wrong for Fork's first 30-40
    moves. It becomes right late in the game (3 s moves, about 0.05 per move).
  - The observed hashfull of the field (8-33 % early) is consistent with this.
- **Implications:**
  - (i) The deferred keep-deeper TT rule (audit-1 B-5, ideas.md idea 30, "deferred to Phase 6")
    is a TCEC-relevant item, not a dead one.
  - (ii) TLB reach: 256 GiB in 2 MiB pages is 131,072 pages, far beyond the core's TLB. A TT
    probe will typically miss the TLB and walk the page tables. Prefetch hides part of this.
    DESIGN's Phase 8 "TT prefetch at 4 GB" A/B is the right shape; 1 GiB pages are TCEC
    Discord question 7.
  - (iii) The 24-bit key check: false matches per probe ≈ 5 × 2⁻²⁴ ≈ 3 × 10⁻⁷. At about 4 × 10⁸
    probes per second that is about 100 false matches a second, harmless per Hyatt and Cozzie
    (2005; CPW). No action.
- **Cheapest experiment.** Run LTC with the hash scaled to TCEC's entries-per-node ratio rather
  than a fixed 64 MB: about 32-48 MB at LTC, about 8-12 MB at STC. Do it for any TT-policy
  change (B-5, aging), so the test sees TCEC-like pressure. It costs nothing extra.
- **Prediction.** B-5 (keep deeper) shows a larger effect at the scaled-down hash than at 64 MB
  LTC. Refuted if both are null.

### F. Long-TC time management (Phase 5; the KB already covers the techniques)

time-management.md is thorough. The new TCEC data and Fork's code add three points.
1. **Node share is nearly free in Fork.** The searcher already computes each root move's
   per-mille share of the iteration's nodes for its LMR context (`searcher.cpp` ~798-806).
   - A soft-limit factor from the best move's share needs no new counters, only the decision
     rule.
   - Published gains: +5 to +20, holding or growing at LTC (time-management.md §4.4).
   - **Cheapest Phase 5 experiment:** an STC SPRT with the factor on the soft limit only, then
     LTC. Kill if LTC is < 0 within error.
2. **The time curve.** The field splits: front-loaders (Stockfish, Reckless and PlentyChess,
   with ≤ 93 s left at move 60) and keepers (Integral, Dragon, Berserk and Fork's formula).
   - Fork's late-game budget matters because decisive TCEC games are long (median 91 moves) and
     are decided by conversion.
   - Experiment: a TCEC-ratio control (60+0.1, time-management.md §6) with the Baier-Winands
     "distribution" control. Compare Fork's curve against a front-loaded variant that differs
     only in the base allocation.
   - Prediction: the difference is < 5 Elo either way at 60+0.1. If larger, the curve is worth
     tuning before any dynamic term.
3. **Game-length statistics.** TCEC's median remaining moves (43 at move 40, about 20-22 from
   move 80) could inform a moves-left estimate.
   - Using statistics of other engines' games to set a Fork constant is a data-policy question
     (brief rule 4 bans other engines' games as training data; TM calibration is not training,
     but the owner should rule).
   - The clean route is the same statistic from Fork's own UHO self-play at the long control.
     The TCEC numbers serve only as a cross-check.

### G. Syzygy at 6-7 men: correctness and I/O, not Elo

- **Mechanism.** At TCEC the WDL and DTZ tables for up to 7 men are on NVMe, and 7-man DTZ is
  also on HDD (competition.md §2). Fork probes WDL in search and DTZ at the root through Fathom.
- **Evidence:**
  - Ethereal's commercial 13.94-13.99 changelog (talkchess p=942809) lists fixes for very long
    endgames (DTZ above 1000), "wide" DTZ tables, read-ahead on Linux and root-move filtering,
    all aimed at TCEC's 7-man set.
  - time-management.md §4.8: Stockfish lost TCEC games on time when DTZ on HDD was slow.
  - CPW: one 7-man WDL probe classifies a position; DTZ is single-sided and may need a 1-ply
    search.
- **Transfer.** Whether Fathom at Fork's pinned commit handles DTZ above 1000 and the wide
  7-man DTZ tables correctly is **UNVERIFIED** (I did not open Fathom's code, by the
  clean-room rule for this task).
- **Cheapest experiments:**
  - (i) Download a handful of the largest 7-man DTZ files that contain long-DTZ positions
    (Syzygy tables are allowed data) and compare Fathom's root ranking with the lichess
    tablebase API answer for chosen positions. A Fork-side test, no engine code involved.
  - (ii) Fault-inject a slow TB path (DESIGN Phase 8 "7-piece cold-cache cost").
  - (iii) Optional: 6-man WDL locally (67.8 GiB, CPW) to exercise Fathom on real file sizes in
    the probe-depth tests.
- **Kill criterion.** None; this is a safety item.
- **Elo expectation.** A few Elo at most. The value is avoiding a lost won ending or a time
  loss.

### H. Deep-search robustness audit (cheap, Phase 4 or 5)

- **Mechanism.** TCEC root depths reach 40-60 in the middlegame and 80+ in endgames (§1.1).
  Fork's tests rarely pass depth 25, so code paths at deep depth are effectively unexercised.
  These include:
  - depth-indexed tables (the LMR table clamps at 63, fine);
  - depth² bonuses (capped, fine);
  - aspiration widening at high scores;
  - mate and table score bands with `MaxPly` 250;
  - the iteration-growth rule at depths where one iteration takes minutes;
  - seldepth near `MaxPly` (the top engines' seldepth reaches 95-106).
- **Cheapest experiment.** Twenty long single-thread searches (`go movetime 600000` on
  endgame-heavy and middlegame positions) under the UBSan and ASan presets, plus three runs
  with `go depth 120` on simple endings. Pass if there is no sanitizer report and the scores
  are sane.
- **Kill criterion.** Nothing to kill; it is a one-off check (about 4 machine-hours, one heavy
  job).

---

## 3. Testing methodology for long-TC strength under Fork's compute

1. **Keep UHO.**
   - The TCEC Swiss is decided by biased exits: 303 of 310 decisive games were White wins, and
     186 of 312 pairs went 1.5-0.5.
   - Fork's UHO book and pentanomial pair statistics already model exactly this.
   - Do not switch to balanced books for TCEC-oriented tests.
2. **Scaling ladder (§2.C).** One-off: Elo per doubling at three budgets, by fixed nodes or
   time odds.
   - It converts every later "FN positive, STC negative" result into a TCEC projection.
   - It also sets a TC-specific speed gate.
   - Repeat it after each large network change: Elo per doubling depends on the eval.
3. **VLTC spot checks (§2.B).**
   - 120+1.2, Hash 256 MB, bounds [−3, 1], at most 2 stages.
   - Only for:
     - the SPSA retune output;
     - reduction and pruning formula changes with large STC gains;
     - anything depth-gated;
     - extension changes (which already go to LTC).
   - This is about 3x an LTC stage per stage. Budget about 2-4 such checks for the rest of
     Phase 4.
4. **Hash scaled to TCEC pressure (§2.E)** for TT-policy tests: about 8-12 MB at STC and
   32-48 MB at LTC. This replaces the fixed 16/64 MB only for those tests.
5. **SMP tests once Phase 6 exists:**
   - An nps-scaling check in CI: bench at 1 and 4 threads on the runner; fail on a ratio drop
     larger than noise.
   - An SMP SPRT at 2 threads per game, concurrency 2 on each 4-vCPU runner (whether the four
     vCPUs are four cores or two cores with SMT is **UNVERIFIED**; GitHub's spec page does not
     say). Stockfish's practice: tunes and depth changes also pass "VLTC SMP" (60+0.6, 8
     threads).
   - Fork's affordable analogue: LTC at 2 threads for SMP-specific changes.
6. **TCEC-ratio TM tests:**
   - 60+0.1 keeps TCEC's 1/600 increment ratio (time-management.md §6).
   - Add a zero-margin runner and count forfeits separately.
   - A sudden-death and a cyclic non-regression check stay, for local and rating-list play.
7. **Use TCEC's archive as a free post-event probe.**
   - Once Fork plays any TCEC testing or playoff game, the per-move `d/n/s/mt/tl/h` fields give
     its real nps, depth, hashfull and clock curve at 512 threads.
   - My scripts are throwaway, but the method is a 100-line parser.
   - TCEC grants testing games before events (competition.md §2): ask for them early, and
     treat them as the only real NUMA and 512-thread measurement Fork will get.
8. **Expect Swiss noise.** A 26-game Swiss has a standard deviation of about 1.8 points, and
   48 engines spanning about 550 rating points (3291-3844) landed within 10 points of each other. Optimise
   Elo (SPRT), not Swiss placement. For Fork the gate that responds to Elo is the Cat 3+4
   playoff's 12 DRR.

---

## 4. Do not spend time on (or remove)

| Item | Why not |
|---|---|
| Contempt or a draw-score bias for TCEC | No measured gain at engine-vs-engine top level in any source opened (CPW lists anecdotes only; Lc0's WDL-contempt posts give no Elo and say must-win settings are "not meaningful" at top level). TCEC's biased exits already make White's job winning and Black's drawing; a contempt term would bias Black into losing a drawable biased position. Phase 7's contempt item can stay low |
| A first-move-out-of-book time bonus | Only 1 of 17 top engines does it visibly (§1.1); no published test found |
| Recapture or "easy move" TM shortcuts | Added and then removed elsewhere (time-management.md §4.5); node share covers it |
| "Will the next iteration finish" allocation rules beyond safety | Conflicting published evidence (time-management.md §4.6); at TCEC's 512 threads iteration timing is even noisier (Grant's 6-thread non-reproduction) |
| Tuning anything for TB or eval adjudication | TCEC has no TB adjudication and no win adjudication (competition.md). The ≤6-piece ±0.25 draw rule only shortens dead draws |
| Scorpio bitbases, pondering, opening books | Not offered to engines or disabled at TCEC (competition.md) |
| An MCTS mode (the Komodo MCTS precedent) | Komodo's MCTS was "lower raw strength" (CPW); no TCEC case for it |
| Optimising the STC TT replacement at fixed 16 MB without the scaled-hash check | It tunes for a pressure that only approximately matches TCEC's; scale the hash instead (§2.E) |
| Chasing closed engines' techniques | Dragon, Torch, Revenge, Ginkgo and rofChade publish essentially no technical detail (§5) |
| Pulling SMP forward into Phase 4 | Its value is entirely at TCEC; Phase 4's SPRTs, the gauntlet and data generation are 1-thread; the Phase 6 spec already lists the design questions. Only keep new search state thread-friendly |

---

## 5. Closed, commercial and TCEC-premier engines: what is public

| Engine | Public technical content found | Takeaway for Fork |
|---|---|---|
| Komodo Dragon | CPW Komodo: NNUE "trained with Komodo games and evaluation" (2020-11); a classical search with the usual techniques. Kaufman (2018-10): large hash on many cores took "several minutes to reach full speed" until fixed (tested up to 36 cores). Dailey (2013): parallel search should be judged by strength, not speedup; idle cores might be better used on lines the single-thread search reduces heavily | Measure nps over the first moves at full hash and threads (warm-up); judge SMP by Elo, never by time-to-depth. komodochess.com was not opened (TLS failures recorded in the KB) |
| Torch | CPW: authors from Ethereal, Koivisto, Berserk and Dragon; closed; "entirely original" code claim; no technical detail; development redirected to product use (2024-06) | None |
| Ethereal (commercial era) | 14.00 notes: TB fixes for TCEC's 7-man set; TT clearing with a fraction of the threads; ProbCut and LMR tweaks; +45.5 ± 1.6 at 60+0.6, 1 thread, vs 13.75 | Long-DTZ and wide-DTZ correctness is a real TCEC issue (§2.G) |
| Revenge | CPW: commercial successor of Pedone (2021); a pure neural eval; parallel search; no detail | None |
| Ginkgo | CPW: private; parallel PVS with a shared TT; the GridGinkgo cluster version at WCCC 2016 and 2018 | Cluster search is out of scope (TCEC is one machine per side) |
| rofChade | CPW: classical alpha-beta feature list; Lazy SMP; TCEC since S14 | None specific |
| Lc0 (as a TCEC opponent) | S17 Superfinal report (lczero.org, 2020-04-21): Lc0 won 52.5-47.5 on 4x RTX 2080 Ti against Stockfish on 176 threads at 90'+5"; Lc0 strong in long positional grinds and closed structures; Stockfish strong in sharp tactics and perpetual-check defence; Lc0 often short of time in endgames. "Achilles heel" post (2018-10-08): fortresses defeat both kinds of engine; anecdotal. Swiss 10: LCZero 15th and Ceres 10th, both 14/26 | Alpha-beta's edge is tactical depth and defence; TCEC's biased exits plus long endgames reward conversion technique. Nothing to copy; confirms that Fork's endgame and eval quality (idea 45's slice) matters at TCEC |
| Ceres | README: MCTS over Lc0-type networks; a lock-free parallel descent; batch overlap; NUMA, prefetch and false-sharing work; GPL-3.0 | The same hygiene list as §2.D |
| AlphaZero (preprint 1712.01815, 2017-12-05) | 80 thousand positions per second against Stockfish's 70 million, and AlphaZero's MCTS "scaled more effectively with thinking time" than Stockfish 8 or Elmo; draws compress Elo in chess (footnote) | Historical support for "evaluation quality gains in value at long TC" (§2.C); the alpha-beta engines have since closed the gap with NNUE (TCEC results), so it is no case for MCTS |

---

## 6. Proposals in priority order (for the orchestrator)

1. **Now (Phase 4, cheap):**
   - §2.B: VLTC non-regression for the SPSA retune output, and LTC for large-gain reduction
     changes.
   - §2.C: extend the speed-to-Elo measurement to a second budget.
   - §2.H: the deep-search sanitizer audit.
   - §2.E: run TT-policy tests with a hash scaled to TCEC pressure.
   - Note in the Phase 4 close that all Elo is 1-thread.
2. **Phase 5:**
   - node share on the soft limit first (nearly free in Fork's code);
   - then stability and score trend (KB);
   - the curve experiment at 60+0.1;
   - the TB slow-path safety tests.
3. **Phase 6:**
   - Lazy SMP with depth skipping;
   - main-thread result selection first and voting as an SPRT;
   - NUMA-local per-thread allocation, main-thread clock polling, per-thread node counters;
   - an nps-scaling CI check;
   - the 2-thread SPRT gate;
   - B-5 (keep deeper) retested at TCEC-scaled pressure.
4. **Phase 8:**
   - 7-man DTZ correctness against an independent oracle;
   - ask TCEC for early testing games and parse them as in §1.1.

---

## 7. Sources opened (2026-11-07)

TCEC data and pages:
- https://tcec-chess.com/tournament.json and https://tcec-chess.com/live.json: current event
  (Cup 17 testing); used only to confirm that the season is current.
- https://tcec-chess.com/gamelist.json: event names for S30.
- https://tcec-chess.com/archive/json/TCEC_Season_30_-_Swiss_10_Schedule.sjson: 624 games'
  results, terminations, lengths and durations (§1.1).
- https://tcec-chess.com/archive/json/TCEC_Season_30_-_Swiss_10_Crosstable.cjson: final scores
  and ratings.
- https://tcec-chess.com/archive/json/TCEC_Season_30_-_Swiss_10_{1..624}.pgn: per-move engine
  statistics (§1.1). All 624 fetched. The first pass got 607 and a re-parse after the
  background download finished found all 624.
- https://tcec-chess.com/archive/json/TCEC_Season_30_-_Category_3%2B4_Playoff_{1..12}.pgn:
  engine options in the headers (threads, hash); only the headers were used.
- KB pages read for context: `docs/kb/competition.md`, `docs/kb/time-management.md` (kb
  worktree).

Documentation, release notes, commit messages:
- https://github.com/official-stockfish/Stockfish/wiki/Useful-data: thread scaling, hash vs
  Elo, Elo vs TC, Syzygy Elo (§1.2).
- https://github.com/official-stockfish/Stockfish/releases/tag/sf_17: NUMA up to 2.8x.
- https://github.com/official-stockfish/Stockfish/releases/tag/sf_14: checked for contempt and
  TM; nothing relevant.
- Stockfish commit messages via api.github.com (search "VLTC", then the messages of f030a1c5,
  36db936e, 6db47ed7, adfddd2c, 54cf2266, 78532af9, 37bd1e77 and 5372f81c; text only, no
  diffs): scaling evidence (§1.2 row 2, §2.B). The numeric constants in those messages are
  deliberately not recorded.
- https://github.com/codedeliveryservice/Reckless/releases/tag/v0.9.0: NUMA-aware threads; SMP
  test conditions and result.
- https://github.com/dje-dev/Ceres (README only): MCTS engineering list; GPL-3.0.
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners: 4 CPU, 16 GB
  Linux runners for public repositories.
- https://www.amd.com/en/products/processors/server/epyc/4th-generation-9004-and-8004-series/amd-epyc-9754.html:
  128 cores, 256 threads, 256 MB L3, 12 channels, 460.8 GB/s per socket, launched 2023-06-13.
  WebFetch timed out; curl with a browser User-Agent worked.
- **Failed:**
  - https://github.com/official-stockfish/Stockfish/wiki/UCI-&-Commands (and the %26 form):
    returned the wiki's new-page editor; not used.
  - https://github.com/official-stockfish/Stockfish/blob/master/README.md: the README
    documents no options; not used further.

Chess Programming Wiki (CC BY-SA 3.0):
- Lazy_SMP, Parallel_Search, Shared_Hash_Table, NUMA, Syzygy_Bases, Contempt_Factor, Komodo
  (including the quotes of Dailey 2013 and Kaufman 2018), Torch, Ceres, RofChade, Ginkgo,
  Revenge.
- **Failed:** https://www.chessprogramming.org/Dragon (404).

Forums and blogs:
- talkchess t=76190, Grant, "Dispelling the Myth of NNUE with LazySMP" (2020-12-30): SMP
  per-doubling Elo.
- talkchess t=68154, "Lazy SMP and 44 cores" (2018-08 to 2018-11): depth skipping; the NUMA
  per-thread data loss.
- talkchess t=71027, "Some NUMA data for Stockfish-dev and Cfish-dev" (2019-06-17): local and
  remote ratios. Poster attribution as CPW lists it (Zulli); my parse of the page's author
  fields was ambiguous.
- talkchess p=942809, Grant, "Commercial Release of Ethereal 14.00" (2023-02-08): the
  TCEC-oriented TB fixes; Elo.
- lczero.org blog:
  - /blog/2020/04/tcec-s17-super-final-report/
  - /blog/2018/10/achilles-heel-of-chess-engines-neural/
  - /blog/2023/07/the-lc0-v0.30.0-wdl-rescale/contempt-implementation/
  - /blog/2024/03/gm-matthew-sadler-on-wdl-contempt/
  - blog index pages 1-8, for the post list.
- **Failed:** talkchess t=68293 ("Ethereal 10.88 NUMA"): connection reset twice; not used.

Papers:
- arXiv 1712.01815 (Silver et al., 2017-12-05), the PDF v1: nodes per second; scaling with
  thinking time.
- Hyatt and Mann (ICGA J. 25(1), 2002) and Hyatt and Cozzie (ICGA J. 28(3), 2005): cited only
  as CPW describes them; not opened (**UNVERIFIED** detail).

Web searches (snippets not relied on): "lczero.org blog TCEC superfinal …" and "Ethereal NNUE
commercial …"; both only led to the pages above.

---

## What I could not verify

1. Fork's nps, depth and hashfull at 512 threads on the EPYC 9754. Every TCEC-side number for
   Fork in §1.2 and §2.E is a scaled estimate (about 390 M nps assumed). Only a TCEC testing
   slot or a rented dual-socket machine can measure it.
2. The 1→512-thread Elo for Fork (+200 to +450): an extrapolation from Ethereal's 1-8 core data
   and Stockfish's 8-thread LTC data, halved for TC. Not measured anywhere at 512 threads.
3. Whether the linear-in-log(nodes) model of §2.B holds. SF documents sign flips; the
   projection to 14 doublings is an assumption.
4. How much NUMA weight replication matters for a 1.4 MB network; Stockfish's 2.8x figure is
   for its own (much larger) network and implementation.
5. Whether GitHub's 4-vCPU runners are 4 cores or 2 cores with SMT, and whether one VLTC stage
   fits a job's time limit.
6. Whether Fathom at Fork's pinned commit handles 7-man DTZ above 1000 and wide DTZ tables
   (Ethereal needed fixes for both). Fathom's code was not opened here.
7. The meaning of TCEC's `h` field across engines (it is engine-reported hashfull, but the
   definitions differ); used only as an order of magnitude.
8. Why S512+X's fixed-node gain translated so badly at STC (an implied Elo per doubling near
   190): the sprt-log also leaves it UNVERIFIED.
9. Whether using TCEC game-length statistics to calibrate a time-management constant is
   allowed under Fork's data policy (owner's call; §2.F point 3 proposes Fork's own games
   instead).
10. Torch's and Dragon's data provenance and techniques: not publicly documented in any page
    opened.


---

# B4. Mathematics (M)

## B-math: mathematics of Fork's network, labels, loss and quantization (Phase 4 think tank, specialist M)

## 1. Summary

**Summary.** I ran four read-only measurements on committed nets and sealed
shards (§2.1) and derived what they imply. Seven things follow.

1. **Validation loss gives equal credit to two kinds of knowledge.** A
   single S-512 net is a sum of 1,024 ridge functions. Fork's own same-recipe
   pairs show that eval knowledge that quiescence or a shallow search already
   resolves (exposure and threats) earns about **5.5 Elo per 1e-4** of loss.
   Knowledge that no horizon resolves (pawn links) earns about **100 Elo per
   1e-4**, an 18x gap. A loss computed on the *quiescence value* instead of
   the static eval should rank architectures the way games do (M1).
2. **The result half of the target is mostly noise, and it is correlated.**
   - The result residual E[(r − σ(s/S))²] is **0.047**, and its within-game
     correlation is **0.674**. That is a design effect of about 24, so a game
     gives about 1.5 independent result observations for its ~35 kept
     positions.
   - The search-score label's white noise (the nugget of the score variogram)
     is about **0.0004 in probability units, about 17 cp**.
   - On noise alone the result weight should be about 0. It is worth 0.5 only
     because it carries information no labeller search has (U-knowledge).
   - Scores *later in the same game* carry much of that information at a third
     of the noise. Hence **n-step (TD) score targets** (M2), the strongest
     training idea here.
3. **Pawn links are used non-additively.** Removing one non-pawn piece changes
   the links' contribution to the eval by 0.88 of its spread; moving the own
   king one square changes it by 0.38. Explicit pair inputs pay because they
   let SCReLU form third-order terms. That points to the next family: pawn
   features on the same pawn-structure trigger, passed pawns first, chosen by
   a residual screen (M3).
4. **Mean-|eval| matching is the wrong normalisation for search margins.** By
   the variance identity Var(V) = Var(eval) + Var(error), each better net is
   *compressed* by the matching (S_play went 101 → 89). Fixed-cp margins
   therefore grow more conservative with every promotion. One margin-scale
   factor set by error matching fixes this (M4).
5. **Cross-entropy** gives decided positions 7x to 160x more gradient than the
   current MSE-on-sigmoid. That matters for TCEC conversion, where there is
   no win adjudication (M5).
6. **The training scale S = 92 is about 8% above the scale the data fits**
   (84-87 on every g2/g3 part). That is a cheap correction, worth little Elo
   (M6).
7. **Quantization is not where S-512's Elo is.** The output-weight grid
   dominates: modelled noise sd 2.6 cp from the output weights against 1.6 cp
   from the first layer, mean |error| 2.4 cp modelled against 2.0 measured.
   Removing all of it is worth at most about 1-2 Elo. Do adaptive rounding of
   the output layer for free, and drop idea 44's dedicated Kaggle validation
   (M7).

| ID | Title | Expected Elo at LTC (range) | Effort (days) | Confidence | NOVEL? |
|---|---|---|---|---|---|
| M1 | Search-resolved validation loss (quiescence / depth-2 value against the target) as the yardstick for ranking architectures and targets; backtest on the existing nets | enabler: +5 to +15 indirect, from fewer failed designs and better picks | 1.5 | medium | yes (UNVERIFIED) |
| M2 | n-step score targets: the target takes the score k plies later in the same game, replacing most of the result weight | +3 to +12 (STC +3 to +10) | 2-3 + one Kaggle session | medium-low | yes for NNUE practice (UNVERIFIED); classical TD |
| M3 | Passed-pawn inputs on the links' pawn-structure trigger, chosen (with other U-type families) by a residual-interaction screen priced in Elo per cycle | +3 to +10 net of speed | 5-8 | low-medium | partly |
| M4 | One eval-margin scale factor, set at each promotion by matching error spread, not mean \|eval\| | 0 to +6 | 1 + a two-value ladder | medium on direction, low on size | no (extends A2 O4) |
| M5 | Cross-entropy loss arm, aimed at conversion (TCEC) | 0 to +6 (more at TCEC) | 0.5 + an arm in M2's session | low | no |
| M6 | Training scale refit to the data (about 85, not 92) | 0 to +2 | 0.5 | high (fact), low (Elo) | no |
| M7 | Quantization: adaptive rounding of the output layer, QAT only as a final fine-tune, idea 44's validation plan retired | +0.5 to +1.5 | 1 | high on the size | no |

---

## 2. Measurements and shared derivations

### 2.1 What I measured (read-only, this session)

All figures below were computed with the repo's `.venv` Python and its own
readers (`tools/nnue/models.py`, `netformat.py`, the shard layout from
`tools/datagen/verify_games.py`). No engine was run and no file was
written. Nothing was changed.

**(a) S512ppr2's weights** (`nets/s512ppr2.fnet`, S = 89):

| Tensor | Mean \|w\| (int) | p99 | max | Share above 127 |
|---|---|---|---|---|
| piece rows (768 x 512) | 34.8 | 177 | 505 | 2.84% |
| link rows (608 x 512) | 21.3 | 106 | 287 | 0.41% |
| output weights (8 x 1024) | 15.5 | 91 | **127** | 0 (26 sit at ±127, the trainer's ±1.98 clip) |

- Output-weight L2 norm per phase bucket falls from 629 (bucket 0, the
  lowest-material bucket) to 389 (bucket 7). Endgame buckets use sharper
  output functions.

**(b) Activations on the 446 parity positions** (`tests/nnue/parity.epd`):
- 23.8 active inputs per perspective, 5.6 of them links.
- Per position, **31.7%** of the 1,024 hidden values lie strictly inside the
  linear region (0, QA), **66.6%** are clipped to 0 and **1.7%** are
  saturated at QA.
- No unit is dead; 15 are active in under 2% of positions.

**(c) Quantization error model.**
- Each first-layer weight is perturbed by its rounding cell: N(0, n/12) per
  accumulator value, n the number of active inputs plus the bias. Each output
  weight is perturbed by U(−½, ½).
- Propagated exactly through clip-square and the output:
  - first layer: sd **1.55 cp**;
  - output weights: sd **2.57 cp**;
  - combined: sd 3.0 cp, so a mean |error| of about 2.4 cp.
- The measured quantization loss of S512ppr2 is mean 2.0, p99 6.1, max 7.9
  (docs/nets.md). The engine's final division also truncates toward zero
  (up to 1 cp).

**(d) Link interaction test** (S512ppr2, 446 positions, bucket held fixed):
- The links' contribution (eval with link rows minus eval without) has sd
  **36.1 cp** (mean |·| 24.4).
- Removing one random non-pawn, non-king piece changes that contribution by
  rms **31.6 cp (0.88 of its sd)**.
- Moving the side to move's king one square changes it by rms **13.6 cp
  (0.38)**.

**(e) Score variogram and result residuals.**
- Data: 20,000 games of `~/fork-data/kaggle/g3f/g3f-w09-val.vf` (S512+PP's
  labels; 94.2 records per game, 54.4% saved, 81.2% decisive); p = σ(s/92),
  White's view.
- E[(r − p_t)²] = **0.0470**.
- Within-game correlation of r − p_t: **0.674**.
- D_p(k) = E[(p_{t+k} − p_t)²]: 0.00099 (k = 1), 0.00140 (2), 0.00285 (4),
  0.00635 (8), 0.0143 (16), 0.0312 (32).
- E[(r − p_{t+k})²]: 0.0443 (1), 0.0402 (4), 0.0354 (8), **0.0273 (16)**,
  0.0156 (32), 0.0046 (64).

**(f) The outcome-fitted scale per part.** The S minimising
MSE(σ(s/S), r), over 4,000 games of each part's validation shard:

| Part | Labeller | Fitted S |
|---|---|---|
| g1s1 | B0r1 | 99.9 |
| g2 | S512 | 86.6 |
| g3 | S512r2 | 85.5 |
| g3f | S512+PP | 84.2 |

The trainer uses 92 for every run.

Caveats:
- (e) and (f) do not apply the training filter (checks and captures stay in).
- (b) to (d) use one 446-position set.
- (e) uses one part.

Each is a first measurement, not a final one.

### 2.2 What S-512 can and cannot represent

Per perspective p and phase bucket b, the output is

  f(x) = c_b + Σ_p Σ_j v^{(b)}_{p,j} · clip(a_{p,j}(x), 0, 1)²,
  a_{p,j} = bias_j + Σ_{i active} W_{ij}.

Each term is a **ridge function**: a fixed 1-D nonlinearity of one sparse
linear form. This has three consequences.

1. **Inside a unit's linear zone, f is a quadratic form in the features.**
   The pairwise coefficient of features i and k is 2Σ_j v_j W_ij W_kj, summed
   over the units in their linear zone. So the net's pairwise interaction
   matrix has rank at most the number of linear-zone units, about 325 per
   position by (b).
2. **A sparse, local conjunction costs about one unit per pattern.** "Pawn on
   a AND pawn on b, nothing else implied" is a local conjunction. Without
   spurious cross terms, a ridge sum can express it only with a dedicated
   unit whose bias sits so that only the pair crosses zero. A local
   neighbour graph like the 608 links has near-full rank, so it needs about
   one unit per pattern: 608 patterns against 512 units per perspective, and
   the units also serve everything else. Smooth, low-rank interactions are
   cheap. King position against piece placement is mostly smooth in the
   king square, and mirroring already removes one axis.
   - This is why **pawn links paid and king regions (H-512) did not**: links
     add 608 conjunctions the body could not afford; regions add a low-rank
     dependence the body already had.
3. **Higher-order terms arise only through the clip.** Once a pair is an
   input, the quadratic multiplies it with every other feature: pair × piece
   is a third-order term in squares. Measurement (d) shows exactly this.
   - The links' value moves by 0.88 of its spread when one piece leaves, and
     by 0.38 when the king steps aside.
   - **Explicit pair inputs pay twice:** once for the conjunction, and once
     for the third-order terms they unlock.

What the body cannot easily do:
- conjunctions of three or more specific squares;
- set-absence conditions over long spans (e.g. "no enemy pawn on these 15
  squares") combined with further conditions;
- anything depending on attack geometry through occupancy (line of sight).

Line-of-sight is the threat family. It is high-rank too, but it is also
search-resolvable (§2.3).

### 2.3 The T/U decomposition: why loss misranks architectures

Write the true value as V(x) = T(x) + U(x):
- **T** is the part a shallow search recovers from a T-blind eval:
  captures, hanging pieces, immediate threats.
- **U** is the part no horizon in the tree recovers: slow structure,
  conversion knowledge beyond the horizon.

An eval error in T costs nodes and some wrong prunes, because the search
fixes it. An error in U passes straight into the root score. So

  ΔElo ≈ α·ΔL_T + β·ΔL_U, with β ≫ α.

Fork's same-recipe pairs give both rates. All are warm at 1e-3 on g2s1 +
g3s1, scored on g3s1-val, with S512r3 as the no-new-inputs control (A1 §3.1,
SL):

| Net | Inputs added | Δ loss vs S512r3 | FN vs S512r2 | Elo per 1e-4 |
|---|---|---|---|---|
| S512+X | exposure (T-type) | −4.67e-4 | +25.7 | **α ≈ 5.5** |
| S512+PP | links (U-type) | −0.45e-4 | +46.1 | **β ≈ 102** |

β/α ≈ 18. Static validation loss weights the two equally. That is the whole
reason "loss barely moved, +46 Elo" and "loss −2.2%, lost" happened in the
same week. It also explains idea 46's pessimism about threats from first
principles: a T-type design must buy about 18 times more loss than a U-type
design for the same Elo.

### 2.4 Price of a cycle

- S512r2 is about 1,300 cycles per node (idea 46, judge). S512ppr2 is about
  1,300/0.895 ≈ 1,450, and with C4's +4% about 1,395.
- With A1/A3's k = 152 Elo per e-fold of nps, Δc extra cycles per node cost
  152·ln(1 + Δc/1395) ≈ **0.11 Elo per cycle per node** at STC (about 0.10
  at LTC, using R_LTC/R_STC ≈ 0.94).
- An extra 512-wide int16 row change in both perspectives is about 32-64
  cycles on AVX2 (32 ymm adds per perspective with their loads; an
  estimate). That is **3.5-7 Elo per extra row change per node**.
- Check against links: 0.895 → 152·ln(1/0.895) = 16.9 Elo, for about 1.3
  row changes per move plus a ~200-instruction pair search (ideas.md 40).
  Consistent.

This turns every input proposal into one inequality: the FN gain must exceed
0.11·Δc. With §2.3's rates, the static-loss gain needed is ΔL_U ≥ 0.11·Δc/β
for U-type inputs, or ΔL_T ≥ 0.11·Δc/α for T-type ones.

### 2.5 What the labels contain: noise, correlation, and the result weight

Target t = (1 − w)·p_t + w·r, with p_t = σ(s_t/S) and w = 0.5.

**Noise** (from §2.1e):
- **Score nugget.** A quadratic fit of D_p(k) at k = 1, 2, 4 gives an
  intercept of 0.00079 = 2σ_n², so **σ_n² ≈ 0.0004** (about 17 cp in logit
  terms at S = 92, from the logit variogram's intercept of about 0.07). It
  is a lower bound: datagen keeps its TT between moves, so consecutive
  errors are correlated. This is the label noise A1 asked a 20k-vs-320k
  relabel to measure, obtained from existing shards for free.
- **Result.** Var(r | x) ≤ 0.047, and positions of one game share the
  realised future: ICC ρ = 0.674. With about 35 kept positions per game,
  the design effect is D = 1 + 34ρ ≈ 24.

**Target noise and the loss.**
- At w = 0.5 the target's noise variance is about 0.25·0.047 + 0.25·0.0004
  ≈ **0.0118**. That is 62% of the 0.019 validation loss, which agrees with
  A1's 0.010-0.016 estimate.
- The reducible part is therefore at most about 0.007, and a 1e-4 loss
  change is about 1.4% of it.

**Variance-optimal w.** Inverse-variance weighting gives
w_v = σ_n² / (σ_n² + D·Var(r|x)) ≈ 0.0004 / (0.0004 + 1.13) ≈ **0.0004**.
On noise alone, the result should carry no weight at all.

**Bias-optimal w, with enough compute and no overfitting** (A1 §3.3: there
is no generalisation gap):
- The net converges to E[t | x] = m + (1 − w)·b_s + w·b_r. Here m is the
  wanted value (the expected score under test-condition play), b_s is the
  labeller search's bias and b_r is the datagen-play outcome's bias.
- Minimising E[((1 − w)b_s + w·b_r)²] gives
  w* = E[b_s(b_s − b_r)] / E[(b_s − b_r)²], which is about
  E[b_s²] / (E[b_s²] + E[b_r²]) when the biases are uncorrelated.
- Target noise does not enter the limit. It enters only through
  optimisation speed, which is binding: A1's B1 shows Fork's nets are
  compute-limited.

**The generational recursion** is the key result.
- The labeller's search adds T-knowledge but not U-knowledge. So a net's
  U-estimate after one generation is u_{n+1} = (1 − w)·u_n + w·u_r, where
  u_r is the U-signal in datagen outcomes.
- The U-error therefore shrinks by (1 − w) per generation toward b_r, the
  datagen-vs-test outcome bias.
- **The result half is the only channel through which knowledge beyond the
  labeller enters the loop.** w sets the speed of that learning, not its
  limit. That is why links (U-type) could gain +46 even though no labeller
  "knew" their structure. Their knowledge came through w·r.

**Bits per position.**
- Result: H(r) ≈ 1.51 bits per game at 81% decisive, about 0.043 bits per
  kept position before the design effect.
- Score: its innovation per ply is about ½·log₂(1 + (D_z(1) − 2σ_n²)/σ_n²)
  ≈ 0.8 bits per position (logit units: D_z(1) = 0.11, σ_n² ≈ 0.036).
- Scores carry about 20x more bits per position, but about *different*
  things.

**When U-information becomes visible.** Measurement (e) shows the result
residual being absorbed into later scores: E[(r − p_{t+k})²] falls from
0.047 to 0.027 at k = 16 and to 0.016 at k = 32. Within 16-32 plies, half
to two-thirds of what the result "knows" beyond p_t has turned into
labeller-visible score. That gives M2.

---

## 3. Proposals

### M1. Search-resolved validation loss as the network yardstick [NOVEL] (UNVERIFIED novelty)

- **Mechanism.** Score a candidate net with the value of a **quiescence search** (and, second, a depth-2 search)
  that uses that net, against the training target and the outcome. This
  replaces its static eval on the same positions. Search-resolvable (T)
  knowledge then earns little credit, because quiescence finds it with or
  without the inputs. Horizon-invisible (U) knowledge keeps full credit.
  Report three numbers per net: L_static (today's), L_QS and L_d2. Report
  each against the blended target and against the outcome alone (a Brier
  score that does not depend on the target, needed when the training
  targets differ: M2, M5, M6).
- **Math.** From §2.3, ΔElo ≈ α·ΔL_T + β·ΔL_U with β/α ≈ 18. If quiescence
  resolves a share ρ_T of T-errors, then ΔL_QS ≈ (1 − ρ_T)·ΔL_T + ΔL_U, so
  Elo/ΔL_QS becomes roughly constant across input types once ρ_T is large.
  On static loss the ratio of the X and PP gains over S512r3 is
  4.67e-4/0.45e-4 = **10.4**; their FN ratio is 25.7/46.1 = **0.56**.
  - A yardstick that tracks Elo must cut that ratio by about 18x.
  - Quiescence resolves captures by the side to move. Threats against the
    mover's own pieces are resolved only at depth 2 (the mover moves the
    piece; the opponent's capture is then searched). So L_QS should cut the
    ratio partly and L_d2 most of the way.
- **Theory.** Quiescence search: Beal (1990), "A generalised quiescence search algorithm", Artificial
  Intelligence 43 (UNVERIFIED citation details). The idea that an eval's
  worth is its contribution after search: Buro's ProbCut model of
  shallow-to-deep regression (Buro 1995; KB research.md). Evaluating learned
  evals through search rather than statically echoes TDLeaf(λ) (Baxter,
  Tridgell and Weaver, "TDLeaf(lambda): Combining Temporal Difference
  Learning with Game-Tree Search", 1998; UNVERIFIED exact title), which
  trains on the leaf of the principal variation for the same reason. I know
  of no engine that ranks *architectures* by searched loss (UNVERIFIED).
- **Why Fork.**
  - The mispredictions in A3 §2.3 (S512+X, XGR, the "loss barely moved"
    S512+PP) are the evidence this fixes.
  - `tools/nnue/exposure_pretest.py` admitted XGR on a larger *static*
    residual where pieces are exposed. That is precisely the T-signal
    quiescence removes, so the pretest was structurally biased toward
    threat inputs.
  - Idea 46's residual study (rank 0) will repeat that bias unless it uses
    quiescence-resolved residuals.
  - Fork already has `fork evalfens` (src/main.cpp), a static-eval batch
    tool. A quiescence counterpart is the same twenty lines.
- **Prediction (falsifiable).**
  - (i) Against S512r3 on the same 200k g3s1-val positions, the X-to-PP gain
    ratio falls from 10.4 to **below 3 for L_QS and below 1.5 for L_d2**.
  - (ii) Over the backtest set (S512r2, S512r3, S512+X, S512+PP, plus the
    round-2 XGR, AF-S and H-512 where their files exist), the L_d2 ranking
    matches the FN ranking with Spearman ≥ 0.8. Static loss gives
    Spearman ≤ 0.3, with S512+PP near the bottom.
  - Refuted if the L_d2 ratio stays ≥ 5, or the Spearman is not better than
    static loss's.
- **Speed cost; compute.** No engine cost. One build per architecture (they
  are compile-time) and 200k positions × a few hundred quiescence nodes per
  net: under a minute of one thread each. Depth 2 about 10x that. Local
  CPU, low priority beside datagen.
- **Cheapest first experiment.** Only the four g3s1-era nets (X, PP, r3, r2)
  on 50k positions, at quiescence and depth 2: about 1 CPU-hour including
  builds. The full backtest only if (i) holds.
- **Kill criterion.** Prediction (i) fails at depth 2. Then searched loss
  does not separate T from U, and the fallback is A3's speed-adjusted FN
  screen.
- **Originality notes.** Fork's own construction from classical concepts
  (quiescence search, TD-leaf's idea); credit Beal, Buro and Baxter et al.
  in ORIGINALITY.md. No constants involved.
- **Effort and dependencies.** 1.5 days: a `qsfens`-style offline command
  (name to screen) plus a scoring script. It serves §5.6 item 6 (idea 46's
  kill tests: run the residual study on quiescence residuals), every future
  architecture triage, and M2/M3/M5/M6's arm comparisons. Do it before
  item 6.

### M2. n-step score targets from the same game (TD-k) [NOVEL for NNUE practice] (UNVERIFIED novelty)

- **Mechanism.** Replace most of the result in the target with the stored search score **k plies
  later in the same game**:

    t = (1 − w)·σ(s_t/S) + w·[(1 − c)·σ(s_{t+k}/S) + c·r].

  - If ply t+k lies past the game's end, or carries a mate or unsaved
    score, use the nearest later saved score, or r at the end (the TD
    convention: the terminal value is the result).
  - Placeholders to measure: k ∈ {8, 16, 32}, c ∈ {0.25, 0.5}, w = 0.5.
  - A λ-return (an exponentially weighted average of all later scores, mean
    horizon 1/(1 − λ)) is the smooth variant.
- **Math** (all from §2.1e, §2.5):
  - **Noise.** The control's target noise is ≤ 0.25·0.047 = 0.0118. For
    k = 16 and c = 0.25 the second component's variance is at most
    (0.75·√0.0143 + 0.25·√0.047)² = 0.0207, so the target noise is
    ≤ 0.25·0.0207 = **0.0052, a cut of at least 55%**. Both are upper
    bounds, since D_p(k) contains predictable signal.
  - **Gradient noise.** The per-sample error variance E[(σ(f) − t)²] is the
    validation loss, 0.019: about 0.007 model error plus 0.0118 target
    noise. The arm cuts it to about 0.012-0.013, **−32 to −37% gradient
    noise power**.
  - In the compute-limited regime A1 documents (still falling at superbatch
    360; the 1e-3 phase on a noise floor), the stationary excess loss of
    SGD/Adam at a fixed LR scales roughly with gradient-noise power. That is
    worth about 1.5x more low-LR samples. With A1 B1's +8 to +20 for 3x
    low-LR samples and log scaling, about **+3 to +7**.
  - **Information.** The k-step score has absorbed 42% (k = 16) to 67%
    (k = 32) of the result residual variance, so most of the U-signal that
    surfaces within the horizon arrives with a third of the noise.
  - **Momentum check.** Regressing r − p_t on p_{t+16} − p_t gives slope
    β = (0.00135 + 0.0143)/0.0143 ≈ **1.09** (from the cross term 0.0027 in
    the decomposition 0.047 = 0.0273 + 0.0143 + 0.0027). A martingale would
    give 1.0. Scores at S = 92 are slightly under-confident, consistent with
    M6's fitted S ≈ 85.
- **Theory.** TD learning and n-step returns: Sutton, "Learning to predict by the methods of temporal
  differences", Machine Learning 3 (1988); the bias-variance trade-off
  between Monte Carlo and TD targets, Sutton and Barto, *Reinforcement
  Learning: An Introduction*, 2nd ed., ch. 7 and 12. Chess precedents:
  KnightCap's TDLeaf(λ) (Baxter et al.) and Giraffe (Lai 2015,
  arXiv:1509.01549). Halogen trained from zero by TDLeaf(λ) (survey S2).
  What is new here (UNVERIFIED) is using the *stored labeller scores of
  later plies* as a low-variance stand-in for the result in supervised NNUE
  training. Survey S2's "self-distillation" and S1's λ schedules are
  different things.
- **Why Fork.**
  - Fork's results are unusually noisy as labels. 81% of training games are
    decisive at 20k-node play, and 40% end by a 700 cp score adjudication.
    For those games r is literally the sign of a later score, so the result
    is a coarsened k-step score already.
  - The ICC of 0.674 means positions of a game repeat one noisy outcome.
  - Idea 40's L4 asks for "a higher weight on the game result, a
    long-horizon auxiliary target". M2 is its principled form: long horizon
    without the noise.
  - Data generation stores every saved position's score, so no new data is
    needed.
- **Prediction.**
  - The TD arm (k = 16, c = 0.25), warm from S512ppr2 with the standard
    recipe, beats a same-length control continuation by **+3 to +10 at
    STC**.
  - It shows a lower outcome-Brier of its quiescence value (M1's
    target-independent yardstick).
  - Its endgame check is unchanged (the slice is exempt: one-move games,
    t+k beyond the end, so the target is r anyway).
  - Refuted if the arm's FN point estimate is ≤ 0 over 1,600 games and its
    outcome-Brier is not lower than the control's.
- **Speed cost; compute.** No engine cost.
  - One Kaggle session with three warm continuations of 360 superbatches
    (about 2.15 h each on a T4): control, TD k = 16, and TD k = 32 or M5's
    arm.
  - Then the parity chain and an FN screen of the best arm (1,600 games on
    GitHub), then STC [0, 5].
- **Cheapest first experiment.**
  - First, offline and free: recompute §2.1e on a g3s2 sample *with the
    training filter* to fix k (the k where E[(r − p_{t+k})²] + D_p(k) is
    smallest relative to the result's 0.047).
  - Then the session above. The control *must* be a same-length
    continuation, not S512ppr2 itself: B1 says longer training alone gains.
- **Kill criterion.** Both TD arms ≤ control on the outcome-Brier of the
  quiescence value, or the FN of the better arm ≤ 0. Then keep the result
  target.
- **Originality notes.** Credit Sutton (1988), Sutton and Barto, Baxter et
  al. and Lai in ORIGINALITY.md. No engine code or constants are involved;
  k and c are measured placeholders.
- **Effort and dependencies.** About 1 day in `tools/train/src/main.rs`'s
  reader: rewrite each game's stored scores in memory before viriformat's
  conversion, behind a flag; scores stay within ±20000 and the trainer's
  `mapper` is unchanged. Plus about 1 day of tests (a hand-made game with
  known targets) and the session. It touches the next retrain (the
  successor of §5.6 item 7). It replaces S2 N2's "WDL-heavier end" as the
  first target experiment: that idea *raises* target noise in a
  compute-limited regime, which the derivation above says is the wrong
  direction unless the bias term dominates.

### M3. Passed-pawn inputs on the pawn-structure trigger, chosen by a residual-interaction screen (partly NOVEL)

- **Mechanism.** Two steps.
  1. **Screen.** For each candidate input family F, fit the residual of
     frozen S512ppr2, with M1's *quiescence-resolved* value against the
     target, on F's binary features crossed with phase bucket and own-king
     half. Use ridge regression on 2-5 M positions. Read the held-out
     ΔMSE_U(F), and count Δc(F), the cycles per node from rows changed per
     move (a counting pass over game records, KB nnue-inputs §1.5's "paths
     that never evaluate").
  2. **Build the best family** whose predicted FN gain β·ΔMSE_U exceeds
     0.11·Δc + 5.
- **Candidates**, all U-type and none a T-type threat family:
  - (a) **passed-pawn inputs**: pawn square × "passed" per colour, 96 rows
    mirrored per perspective;
  - (b) king-relative pawn shelter and storm: own and enemy pawns at
    relative offsets inside a small box ahead of the own king, shared over
    king squares, about 40-80 rows;
  - (c) minor piece × supporting pawn (outposts).
- **Math.**
  - From §2.2: a passed pawn is "pawn on s AND no enemy pawn on up to 15
    span squares". The body can express each with a dedicated unit carrying
    large negative weights, about 96 units of 512. Its value then depends on
    king distances and blockers (third-order), which costs more units. The
    links (rank limit 1) cannot see spans of more than one rank, so passed
    status is genuinely absent from today's explicit inputs.
  - **Cost.** Passed status changes only when the pawn structure changes,
    which is exactly the links' existing pawn-change flag (ideas.md 40,
    4ef9172).
    - Detection is a few bitboard fills, about 20-30 instructions, paid
      only on structure-changing moves (a share f_ps of moves, plausibly
      0.25-0.35, UNVERIFIED).
    - Rows change only when a passer appears, vanishes or advances: about
      0.1-0.3 row changes per move (EST).
    - So Δc ≈ 0.3·25 + 0.2·48 ≈ 17 cycles, about **0.99x nps, about 2 Elo**
      (§2.4).
  - (b) costs more: every king move changes all of its active features, a
    partial refresh. EST Δc 40-80, so 4-9 Elo. That is why (a) goes first
    unless the screen says otherwise.
  - **Expected gain.** If (a) recovers even 10% of the links' static-loss
    gain (4.5e-6) at β ≈ 100, the FN is about +4.5. At 25% it is +11. Net
    of 2 Elo of speed: **+3 to +10**, wide and low-confidence.
- **Theory.**
  - Ridge-function approximation and its limits: Pinkus, "Approximation
    theory of the MLP model in neural networks", Acta Numerica 8 (1999);
    Barron (1993), IEEE Trans. Inf. Theory 39 (UNVERIFIED page details).
  - Explicit conjunction features in linear models are the classic "feature
    crosses".
  - The passed-pawn concept: CPW "Passed Pawn".
  - Pawn-pair inputs in NNUE: KB nnue-inputs.md §2 (Stockfish 19's pawn
    pairs as a concept).
  - I have not seen passed-pawn *inputs* on a structure-change trigger
    described (UNVERIFIED).
- **Why Fork.**
  - Measurement (d) shows the links are used through third-order terms, the
    mechanism this family relies on.
  - Fork's links already run in the main int16 accumulator with a
    pawn-change flag, so (a) reuses the speed work that took the links from
    0.666 to 0.895 (ideas.md 40).
  - TCEC plays out endgames (no win adjudication, A3 §1.6), where passers
    decide.
- **Prediction.**
  - The screen ranks (a) above (b) in ΔMSE_U per cycle.
  - An S512ppr2 + passers net, warm with the new rows at zero (reproducing
    the parent exactly), keeps **≥ 0.98x nps** and scores **FN ≥ +5**.
    STC then lands at ≥ +3.
  - Refuted if the screen's ΔMSE_U for (a) is under 1.5e-6, or the FN is
    below 0.11·Δc + 5.
- **Speed cost; compute.**
  - Screen: local CPU, hours, low priority.
  - Build: engine feature code, parity tests and a link-style bound.
  - Train: one Kaggle warm session (about 2.2 h).
  - Test: FN 1,600 games, then STC.
- **Cheapest first experiment.** The screen for (a) alone, with the
  rows-changed counter on 200 games (as idea 41's per-move count was done):
  about half a day. Nothing is built unless it passes.
- **Kill criterion.** Screen ΔMSE_U(a) < 1.5e-6, or measured nps < 0.97x,
  or FN < 0.11·Δc + 5.
- **Originality notes.**
  - Fork's own encoding; the names (feature family, flag) need the
    four-engine screen.
  - Pawn-pair inputs are already credited.
  - Passed pawns are CPW vocabulary.
  - No constants beyond the box sizes in (b), which are geometry choices to
    sweep.
- **Effort and dependencies.** 5-8 days. It fits §5.6 item 14 ("idea 40's
  later layers") but should **replace** idea 40's L1 (the separate cached
  pawn-and-king net): measurement (d) shows the pawn knowledge that matters
  interacts with the pieces inside the main body, which an additive side net
  cannot reproduce. It also replaces S512cl's speed work (§4).

### M4. One eval-margin scale factor, set by error matching at each promotion

- **Mechanism.** Introduce one search parameter m that multiplies every eval-cp margin: RFP,
  futility, the singular margin, aspiration's half-width and NMP's surplus
  divisor. At each net promotion, set m_new = m_old · σ_err,new/σ_err,old.
  Here σ_err is the rms of (static eval − 20k-node shard score) on a fixed
  held-out set labelled by the *newest* labeller, each net at its matched S.
  Ladder {m_new, m_old} at STC.
- **Math.**
  - For a calibrated eval e = E[V | x] in logit units,
    **Var(V) = Var(e) + E[(V − e)²]**.
  - A better net has a smaller error variance, so its spread Var(e) *grows*
    by the same amount. Mean-|eval| matching then shrinks it by
    c = sd(e_old)/sd(e_new) < 1. Fork's matched scale did fall at every
    promotion: S512 101, S512r2 92, S512+PP 90, S512ppr2 89 (nets.md).
  - A margin is a quantile of the error: the share of wrong prunes is about
    Φ(−M/σ_err), with M the margin in cp. Under mean-|eval| matching the
    error in matched cp is c·σ_err,new.
  - So the z-score of a fixed-cp margin multiplies by
    σ_err,old/(c·σ_err,new) > 1 at each promotion, and **margins become more
    conservative as nets improve**.
  - Example: a 12% spread growth at constant Var(V), from 0.6 to 0.75 of
    Var(V), takes σ_err down 21%. With c = 0.89 that makes fixed margins
    1/(0.79 · 0.89) ≈ 1.42x more conservative in z.
  - Mean-|eval| matching is right for *calibration-type* thresholds
    (datagen's 400 cp discard and 700 cp adjudication, SPRT
    resign/draw adjudication): those are about win probability. It is wrong
    for *error-type* margins.
- **Theory.** Buro (1995), ProbCut: a margin is a quantile of a shallow-to-deep regression
  residual (KB research.md). The variance decomposition is the law of total
  variance. A2 O4 already proposes measuring margins from Fork's error
  distribution. M4 adds the identity, the predicted direction, and a
  one-scalar mechanism that tracks promotions.
- **Why Fork.**
  - Every eval margin is bootstrap-era (A2 §1.4).
  - The bench node count moves with each net under the same search (A2
    §3.3).
  - Promotions arrive every few days, while an SPSA retune is days of
    GitHub. One scalar per promotion keeps the tuned optimum's prune rates.
- **Prediction.**
  - (i) Measured σ_err: S512ppr2 < S512r2 by ≥ 5% at matched S on the same
    positions. Refuted if within ±2%.
  - (ii) Item 12's SPSA moves RFP and futility margins *down* from today's
    values, roughly by the cumulative ratio. Refuted if it raises both.
  - (iii) The m_new ladder value scores ≥ m_old.
- **Speed cost; compute.** None. Measurement: `fork evalfens` with two builds
  on 100k g3g positions (local, minutes). Ladder: 2 values × 2 STC stages.
- **Cheapest first experiment.** Prediction (i), offline (about 1 hour). If
  it holds, m becomes one SPSA parameter in item 12, not a separate SPRT.
- **Kill criterion.** (i) is refuted, or the ladder prefers m_old at both
  stages. Then keep the margins and leave them to SPSA.
- **Originality notes.** A margin multiplier is generic. Credit Buro. No
  engine constant is proposed: m comes from Fork's own measurement.
- **Effort and dependencies.** One day. It feeds §5.6 item 12 (SPSA) and
  every future promotion; it does not reorder anything.

### M5. Cross-entropy loss arm (for conversion at TCEC)

- **Mechanism.** Train one arm with log loss (or a higher loss exponent) instead of MSE on
  σ(f). Compare it on M1's target-independent yardstick, the endgame check,
  A1's KRK conversion test and a "won position, no adjudication" suite.
- **Math.** For a small logit error δ at predicted probability p:
  - MSE-on-σ weighs δ² by **p²(1 − p)²**;
  - cross-entropy weighs it by **p(1 − p)/2**.

  Relative to a balanced position, at S = 92:

  | Eval | MSE weight | CE weight |
  |---|---|---|
  | 300 cp | 1/49 | 1/7 |
  | 600 cp | 1/28,000 | 1/167 |

  - The current trainer gives decided positions essentially no gradient. It
    cannot learn which of several winning moves wins *efficiently*, which
    is conversion technique. The KRK runs still drew 3 of 20 by the
    fifty-move rule (ideas.md 45).
  - Both losses are proper scoring rules with the same minimiser E[t | x],
    so with unlimited capacity and compute they agree. The difference is
    where a finite, compute-limited net spends its fit.
  - The scale interacts: under CE the tail of |eval| grows, so mean-|eval|
    matching is distorted by the tail. Match with M4's error spread or the
    median |eval| instead.
- **Theory.** Proper scoring rules: Gneiting and Raftery, "Strictly proper scoring rules,
  prediction, and estimation", JASA 102 (2007). The KB records loss-exponent
  gains in other engines and one case fading at LTC (nnue-design.md §6.2;
  no values copied).
- **Why Fork.**
  - TCEC has no win adjudication (A3 §1.6).
  - Fork's data stops 8 plies past 700 cp, so the net sees little of
    conversion.
  - The slice's targets saturate near p = 1, where MSE's gradient vanishes.
- **Prediction.**
  - STC 0 ± 5 (balanced positions lose some fit).
  - Conversion suite: fewer fifty-move draws from won starts (KRK 3/20 →
    ≤ 1/20 is a target, not a forecast).
  - Endgame check not worse.
  - Refuted if FN ≤ −5, or conversion is not improved.
- **Speed cost; compute.** None. One arm of M2's Kaggle session; the loss is
  a trainer flag (bullet's graph supports other losses: UNVERIFIED which
  operation; else a small custom loss node).
- **Cheapest first experiment.** The arm, plus the conversion runner already
  written in scratch for idea 45 (ideas.md 45, "tools written").
- **Kill criterion.** As refuted above.
- **Originality notes.** Generic ML; no engine constants.
- **Effort and dependencies.** Half a day plus a session slot. It shares M2's
  session; it never runs alone.

### M6. Refit the training scale to the data (about 85, not 92)

- **Mechanism.** Set the trainer's S, the cp-to-probability map of the score half, to the
  outcome-fitted value of the snapshot being trained (fit_scale.py's own
  rule) at each retrain. Today it is fixed at 92, fitted on g2s1 in round 2.
- **Math.**
  - The g2, g3 and g3f fits give 86.6, 85.5 and 84.2 (§2.1f).
  - At 92 the score half is under-confident relative to the result half.
    At |s| = 272 cp (g3f's mean), σ(272/92) = 0.9505 against
    σ(272/85.5) = 0.960. The two halves of every target then disagree
    systematically, by about 0.005 in the blend.
  - The squared-bias contribution is about 1e-5 of loss: by A1's 6-10 Elo
    per 1e-4, **0-2 Elo**.
  - The parts within g3s2 differ by only 2.8% in S, so *per-part* S (one
    per labeller) is not worth building. B0r1's g1 data at 99.9 is not in
    g3s2.
  - The momentum slope 1.09 (M2) is the same miscalibration seen from the
    variogram.
- **Theory.** Calibration of probabilistic forecasts (Gneiting and Raftery 2007). The KB
  notes that λ and the scale interact (nnue-design.md §6.3).
- **Why Fork.** A one-number change in the Kaggle script, measured by
  Fork's own tool on Fork's own data. S_play is re-matched afterwards as
  usual (M4 or mean |eval|), so the search sees no scale change.
- **Prediction.** fit_scale.py on 2 M filtered g3s2 positions returns
  83-88. The retrain at that S has a lower outcome-Brier (M1) than at 92.
  Refuted if the fit lands within ±2 of 92.
- **Speed cost; compute.** None. One CPU-minute for the fit; it rides along
  with the next retrain (as a setting, not an arm).
- **Cheapest first experiment.** The fit itself.
- **Kill criterion.** A fit within ±2 of 92: keep 92.
- **Originality notes.** Fork's own tool and data.
- **Effort and dependencies.** Half a day, in the next retrain. It also
  defines S for M2's targets.

### M7. Quantization: adaptive rounding of the output layer; QAT only as a fine-tune; retire idea 44's validation plan

- **Mechanism.**
  1. Post-training, choose each output weight's rounding direction (up or
     down) to minimise E[(Σ_j δw_j·v_j²)²] over a position sample. This is
     a 1,024-variable binary quadratic problem per bucket, solved greedily.
     Leave the first layer as it is.
  2. Use `--qat` only as the last 20-40 superbatches of a retrain that runs
     anyway.
  3. Drop idea 44's separate validation session.
- **Math** (§2.1c):
  - The output grid (QB = 64; step 1/64 against SCReLU values up to 1)
    contributes sd 2.57 cp; the first layer's 1/255 grid over about 25
    active rows contributes 1.55 cp. The output is 73% of the error
    variance.
  - QB cannot rise: the SIMD output computes v·w in int16 (`squared_sum`,
    |w| ≤ 128 and v ≤ 255), and the 26 output weights at ±127 already sit
    at the clip.
  - **Loss-equivalent of all quantization:** ΔMSE ≈ E[(p(1 − p))²]·(σ_q/S)².
    With σ_q = 3 cp at S_play = 89 (0.034 logit) and E[(p(1 − p))²] ≈ 0.02
    for this data's spread (EST), that is about **2.3e-5**, so **1.4-2.3
    Elo** at 6-10 Elo per 1e-4. That is an upper bound for removing
    *everything*.
  - Adaptive rounding typically recovers about half the rounding error of
    the layer it treats (UNVERIFIED for this net): about +0.5-1 Elo. QAT on
    top adds little.
  - Idea 44's validation rule ("both QAT runs below both plain runs by more
    than the seed spread") compares an expected effect of about 2e-5 with a
    warm seed spread of 1.2e-5. That is close to a coin flip, so it spends
    a Kaggle session to learn little.
  - Quantization noise costs real Elo only when it is *systematic*:
    clipping of large weights, as int8 rows would cause (2.84% of piece
    rows exceed 127), or a scale too small for the layer. That is where QAT
    belongs (KB nnue-design.md §5.6 agrees).
- **Theory.** Nagel et al., "Up or Down? Adaptive Rounding for Post-Training Quantization",
  ICML 2020 (arXiv:2004.10568). STE/QAT: Bengio et al. (arXiv:1308.3432),
  Jacob et al. (arXiv:1712.05877), as the KB cites.
- **Why Fork.** The S-512 family is all-int16, and the converter's legs
  already measure the quantization loss deterministically on 446 positions
  (`reference.py legs`), a better test than validation loss for this
  question.
- **Prediction.**
  - Adaptive rounding cuts S512ppr2's mean quantization loss from 2.0 cp to
    ≤ 1.4 cp and p99 from 6.1 to ≤ 4.5. Refuted if the reduction is < 15%.
  - Elo is unmeasurable at this size: it ships only on non-regression.
- **Speed cost; compute.** None at runtime; local CPU for minutes. Bench
  changes (new weights).
- **Cheapest first experiment.** A converter option (Fork's own code) and the
  legs on 446 positions plus a 10k held-out set.
- **Kill criterion.** < 15% qloss reduction: drop it, and record that S-512's
  quantization is done.
- **Originality notes.** Credit Nagel et al. Generic.
- **Effort and dependencies.** One day. It replaces §5.6 item 14's QAT entry
  for this family. QAT stays the method for any int8 design.

---

## 4. Critique of the current plan in my domain

1. **§5.6 item 6, idea 46's residual study: redesign it before running it.**
   - Measured against the static eval, threat features will "explain"
     residual that quiescence removes anyway, as exposure_pretest.py did for
     XGR.
   - Use M1's quiescence-resolved residuals, with a threshold set from M1's
     backtest calibration, not idea 46's 0.2% / 0.5% static-loss rule.
   - By §2.3 a T-type design pays at about α ≈ 5.5 Elo per 1e-4. At 0.95x
     (7.8 Elo) it needs about 1.4e-4 of static loss, about 30% of S512+X's
     entire gain.
   - **Demote the distillation-from-S512+X arm:** it distils T-knowledge
     (worth at most a fraction of S512+X's own +25.7 FN) at the cost of a
     relabelling job. M2/M5 should take that Kaggle slot first.
2. **S512cl's speed work (item 14): drop it.** Contacts are T-type (§2.3).
   The incremental estimate is 0.5-0.6x (ideas.md 41), which at 0.11 Elo
   per cycle is −80 to −105 Elo against a plausible FN of +30-50. No
   realistic speed path closes that.
3. **Idea 40's L1 (a separate pawn-and-king network, cached): shrink it or
   drop it.**
   - Measurement (d): the links' value depends strongly on the pieces (0.88)
     and the king (0.38). An *additive* side network keyed by pawns and
     kings cannot represent piece-dependence at all.
   - The pawn knowledge left to add should enter the main body as inputs
     (M3).
   - **L4 (teaching targets) is M2:** do it as n-step targets, not as a
     larger result weight (§2.5: more result weight raises noise in a
     compute-limited regime).
4. **The λ / result-weight experiments other agents propose** (A1 B4; S2 N2's
   "WDL-heavier end"; S1's λ schedule).
   - The derivation says the result is justified by bias (U-information),
     not by its information per sample, and that its noise is large and
     correlated.
   - Test **n-step targets first** (M2), the variance-reduced form of the
     same information.
   - A plain w ladder is a second arm only if M2 fails.
   - Every such arm is judged on a target-independent yardstick (M1's
     outcome-Brier of the quiescence value) and FN, never on validation
     loss (different targets).
5. **Idea 44 (QAT): retire the validation session** (M7). The expected
   effect is at the seed-spread scale. Keep `--qat` for int8 designs and as
   a free fine-tune.
6. **The speed gate.** State it as **0.11 Elo per cycle per node** and an FN
   hurdle of 0.11·Δc (§2.4), not as a ratio alone. Two consequences:
   - **A U-type family can afford about 3x the cycles a T-type one can** for
     the same static loss (β/α ≈ 18 on loss, before the cost of finding
     features).
   - Families that piggyback on an existing trigger (M3's pawn-structure
     flag) are the cheapest place to add knowledge.

   A3's caveat stands: measure cycles in the build that plays (AVX2 g++ v3).
7. **King buckets (S2 N3).** By §2.2 the king × piece interaction is mostly
   smooth (low-rank), already partly covered by mirroring and the quadratic.
   That is H-512's measured null.
   - The high-rank part is king × nearby pawns, M3's candidate (b), at about
     1/20 of the parameters of 4 buckets and without bucket refreshes.
   - Prediction: a bucketed retest gains ≤ +10 FN and fails the speed
     hurdle. Screen (b) first.
8. **Output buckets and widening.** No dead units; output weights at the clip
   are 0.3%. Data per bucket is ample: each phase octile has about 1/8 of
   1.2 B positions. I see no approximation-theoretic case for more buckets
   or more width at Fork's speed price: width costs about linearly in
   cycles, at 0.11 Elo per cycle.
9. **The validation set.** Besides A1's fixes, the measured ICC of 0.674
   means the 20k positions from about 490 games carry about 490·1.5
   effective outcome observations. Report the score-MSE and result-MSE
   components separately, and use a set of several thousand games, about
   one position per game, for the outcome part.

---

## 5. What I could not verify

- The generality of the 446-position measurements (b)-(d). The link
  interaction shares (0.88, 0.38) come from one position set and one
  perturbation scheme. Removing a piece is a large change, so part of the
  0.88 is ordinary clip nonlinearity rather than "structure × piece"
  knowledge.
- The variogram (e) and the S fits (f) skip the training filter, use one
  part for (e), and treat 20k-node datagen scores as noisy but unbiased.
  The nugget (σ_n² ≈ 0.0004) is a lower bound, because of TT carry-over
  between moves.
- The quantization model (c) assumes the float weights are uniform inside
  their rounding cells. E[(p(1 − p))²] ≈ 0.02 is an estimate.
- α ≈ 5.5 and β ≈ 102 come from two same-recipe pairs whose 1e-3 warm
  starts had large seed spreads (A1 §3.2). β/α could be anywhere from about
  8 to 30.
- The cycle prices (a row change of about 32-64 cycles on AVX2, about 1,395
  cycles per node) are estimates from A3's profile and the judge's clock
  assumption.
- Novelty claims for M1, M2 and M3 rest on my not having seen these methods
  described; UNVERIFIED.
- Literature details marked UNVERIFIED (Beal 1990's venue; the exact
  TDLeaf title; Barron 1993's pages) were not re-fetched this session.
- Whether bullet's graph offers a cross-entropy operation directly (M5).
- Whether the round-2 bake-off net files needed for M1's full backtest still
  exist locally.


---

# B5. Training science (T)

## B-T: training science (Phase 4 think tank, Phase B, specialist T)

## 1. Summary

I re-read Fork's own Kaggle curves (`~/fork-data/kaggle/*/result/*/run.json`, read only).
They change the picture A1 drew in one important way. **The warm retrain's loss is set by
its final learning rate, not by how long it trains.** S512ppr2's two warm runs sit flat at
0.01935-0.01942 (40-superbatch window means) through all 180 superbatches at LR 1e-4. The
mean drops 1.6-1.9e-4 within about 20 superbatches of the drop to 1e-5. It then stays flat,
within 3e-5, for the remaining 160 superbatches (§2.1). Every Fork net before S512ppr2
finished at LR 1e-4. S512ppr2 was the first to be annealed lower. At A1's same-architecture
rate (about 9 Elo per 1e-4), the anneal alone could account for most of its +20.1 Elo
(INFERRED; T6 tests it for 15 GPU-minutes).

Three consequences follow:
1. "Train 3x longer at low LR" (A1 B1) is mostly refuted for warm retrains.
2. The cheap levers are a deeper cooldown and checkpoint averaging (T2). Each is worth an
   estimated +2 to +7 Elo and costs nothing.
3. The next retrain's gain must come from labels and data, and that gain is smaller than the
   last one suggests: **+5 to +18 STC, central +11** (T1).

The decision instruments are also weaker than they look:
- Each reported "best" loss is the minimum of 180-360 noisy readings of the same 20,000
  positions, and is optimistic by about 8e-5 (§2.2). That is twice the 4e-5 "resolved"
  threshold.
- The g3s2 validation set's scored prefix probably holds no new-source positions (§2.3).

So I propose one cheap gold-label validation set, built by deep search on CPU in about an
hour (T3). It serves every later data decision: recency (T4), relabelling, λ (T5) and quiet
filters. I also propose:
- deriving the never-tuned result weight from a TC-calibration playout instead of guessing
  (T5);
- an endgame-start self-play part for conversion and drawish endings, the TCEC-relevant
  coverage gap (T7);
- datagen settings for the next part (T8);
- an equal-compute scratch control that tests whether the warm lineage is a moat or only
  banked compute (T9).

Every proposal runs on Kaggle T4s or this PC with Fork-pure data.

### Ranked proposals

Elo is at STC unless noted. The LTC figures assume an eval gain carries over with little loss
(A1 §4.3, A3 §1.4). "Effort" is wall-clock days of human or agent work, not GPU time.

| ID | Title | Expected Elo, LTC (range) | Effort (days) | Confidence | NOVEL? |
|---|---|---|---|---|---|
| T1 | The next retrain (g3s3), concretely: all data, cooldown and averaging, recency arm, gold scoring | +11 (+5 to +18) | 1.5 + waiting for g3g | medium | no |
| T2 | Warmup-stable-decay schedule with branch cooldowns, plus checkpoint averaging | +4 (+2 to +7); also halves GPU per retrain | 0.5 | high on the loss, medium on Elo | no (new to Fork) |
| T3 | Gold-label validation set and label-noise measurement | enabler (protects every later decision) | 0.5 | high | NOVEL for Fork's process |
| T4 | Recency weighting: down-weight S512-labelled g2s1 (replaces idea 47.1's gen-1 test) | +4 (0 to +10) | 0.5 | medium-low | no |
| T5 | Result weight derived from a TC-calibration playout, then one λ arm | +3 (−2 to +8); sign predicted (lower w) | 1 | low-medium | NOVEL (the derivation) |
| T6 | Anneal-only attribution control for S512ppr2's +20 | enabler (sets datagen versus training priority) | 0.2 | high | no |
| T7 | Endgame-start self-play part (conversion, drawish endings) | +2 STC (0 to +5); more at TCEC | 1.5 | low-medium | no (Caissa-like) |
| T8 | Next datagen part: the 2026-09 book and a 25% save-share arm | +3 (0 to +8) | 0.5 + CPU days | low-medium | no |
| T9 | Equal-compute scratch control (5.4 B samples, one T4 session) | 0 directly; frees architecture changes | 0.3 | medium | no |

---

## 2. New evidence this section rests on (READ from Kaggle records, COMPUTED by me)

### 2.1 The g3s2 curves by window

Validation loss on g3s2-val is shown as the mean over a superbatch window, with the standard
deviation (sd) inside the window. Warm runs used LR 1e-4 for superbatches 1-180 and 1e-5 for
181-360. Scratch runs used 1e-3, then 1e-4. Source:
`g3s2-out/result/s512pp-{warm,scratch}-s{1,2}/run.json`.

| window | warm s1 | warm s2 | scratch s1 | scratch s2 |
|---|---|---|---|---|
| 1-20 | 0.019395 | 0.019393 | n/a | n/a |
| 21-60 | 0.019363 | 0.019366 | | |
| 61-100 | 0.019400 | 0.019417 | | |
| 101-140 | 0.019352 | 0.019346 | | |
| 141-180 | 0.019356 (sd 8.9e-5) | 0.019372 (sd 7.8e-5) | 0.020767 (sd 2.8e-4) | 0.020998 (sd 2.9e-4) |
| 181-200 | **0.019164** (sd 2.4e-5) | **0.019208** (3.1e-5) | 0.019791 | 0.020284 |
| 200-240 | 0.019184 | 0.019204 | 0.019834 | 0.020080 |
| 240-280 | 0.019172 | 0.019181 | 0.019758 | 0.019887 |
| 280-320 | 0.019159 | 0.019167 | 0.019714 | 0.019814 |
| 320-360 | 0.019167 (sd 3.8e-5) | 0.019174 (sd 3.8e-5) | 0.019678 | 0.019781 |

Readings (COMPUTED):
- **Warm, LR 1e-4:** flat to within ±3e-5 for 180 superbatches (0.9 B samples). The loss
  shows no progress while the LR is at 1e-4. It sits about 5e-5 *above* the starting net's
  0.019305, because the starting checkpoint was itself a selected minimum (§2.2).
- **Warm, the drop to 1e-5:** −1.87e-4 (s1) and −1.64e-4 (s2), within 20 superbatches.
- **Warm, LR 1e-5 tail:** from window 181-200 to window 320-360 the change is +0.3e-5 (s1)
  and −3.4e-5 (s2). That is about −1.6e-5 for 160 superbatches, or 57 GPU-minutes per run:
  **≤ 2 Elo at 9.3 Elo per 1e-4**.
- **Scratch, LR 1e-4:** still falling at 360 (s1: −1.1e-4 from 181-200 to 320-360; s2:
  −5.0e-4). Scratch never ran at 1e-5. Its 4.2e-4 "loss" to warm therefore contains a
  missing anneal of about 1.7e-4 (the warm runs' drop) plus about 2.5e-4 of genuinely missing
  compute (INFERRED).
- **Earlier nets, same pattern** (`r2a-out`, `pp-out`, `r3v2-out`). S512r2, S512+PP and
  S512r3 all ended at LR 1e-4 on a floor of 0.0195-0.0198 (window 320-360). S512r3's floor
  (0.019555 on g3s1-val) is above its starting net's 0.019304. "S512r3 never beat its start"
  is therefore what one expects when a net is restarted at 1e-3 and annealed only back to the
  same final LR (INFERRED).

**A noise-floor model.** Take L(η) ≈ L* + c·η^α for the stationary loss at LR η (standard for
SGD and Adam near a minimum: excess loss grows with the LR's noise temperature; e.g. Mandt,
Hoffman and Blei, "Stochastic Gradient Descent as Approximate Bayesian Inference",
arXiv:1704.04289, UNVERIFIED as exactly applicable to Adam).
- With α = 1: c·(1e-4 − 1e-5) = 1.75e-4, so c = 1.94, and the excess still present at 1e-5 is
  c·1e-5 = **1.9e-5**.
- With α = 0.5: excess(1e-5) = 1.75e-4 / (√10 − 1) = **8.1e-5**.
- The observed fluctuation sd ratio between LR phases is 8.9/3.5 = 2.5, closer to the α ≈ 0.5
  end. So **2e-5 to 8e-5 of loss, +2 to +7 Elo, is still available** from removing the LR
  noise at the end (T2).

### 2.2 Best-of-N selection bias (COMPUTED)

At 1e-5 the per-checkpoint sd is 3.5e-5. The expected minimum of about 180 nearly independent
draws lies about 2.6 sd below the mean, so **about 9e-5 optimistic**. Observed:
- warm s1: best 0.019089, window mean 0.019167, so 7.8e-5;
- warm s2: best 0.019100, mean 0.019174, so 7.4e-5.

The recipe threshold `SEED_SPREAD = 4e-5` (retrain_g3s2.py) is half this bias. Warm seeds
differ by only 1.2e-5 at their best and 0.7e-5 by window mean. So **one seed per warm arm is
enough, and arms must be compared by window means or averaged weights, never by best-of-N.**
This also reconciles A1's claim of "seed spread 10x larger before g3s2": most of the old
spread was best-of-N picking noise at LR 1e-4 (sd 1-3e-4), plus file-order effects.

### 2.3 What g3s2-val actually scores (partly verified)

- The trainer scores the first 20,000 kept positions (main.rs `read_positions`).
- `g3s1-val.vf` and `g3s2-val.vf` are byte-identical for their first 9,916 bytes (`cmp`).
- S512+PP's loss is 0.01929241 on g3s1-val and 0.019305 on g3s2-val, only 1.3e-5 apart.

Both facts are consistent with A1's suspicion that the scored prefix is mostly or entirely
g3s1-era (S512r2-labelled) positions, with no slice and no g3b-g3e. The exact composition is
UNVERIFIED (it needs a parse of the file). Consequence: **the warm/scratch decision and
S512ppr2's loss say nothing about the slice or the newer parts.**

### 2.4 Kaggle arithmetic (READ, COMPUTED)

- One superbatch is 16,384 × 305 = 4,997,120 samples.
- S512+PP on one T4: 7,741 s for 360 superbatches = **21.5 s per superbatch, 232k samples
  per second, about 0.84 B samples per GPU-hour**.
- A run of 1.8 B samples takes 2.15 h. Two runs fit side by side on T4 x2. Whether that
  counts as one session-hour of quota is expected but UNVERIFIED (KB phase4-pipeline §7).
- Thirty GPU-hours a week is therefore about 25 B samples a week. **GPU is not the binding
  resource; CPU datagen and decision quality are.**

### 2.5 New data arriving (READ from manifests and the g3g part record, COMPUTED)

- **g3f** (S512+PP labels): 62.17 M records, of which 28.35 M unsaved, so 33.8 M saved. At
  the 67.7% kept share (A1 §1) that is about 22.9 M kept.
- **g3g** (S512ppr2 labels): target 366,424,464 **records**. The part record shows
  `previous_target 428,596,558 − previous_positions 62,172,094`, which is the g3f count
  including unsaved records. At about 54.4% saved, that is about 199 M saved and **about
  135 M kept**.
- The g3g log at 9:42 AM showed 87.4 M records at 2,700 per second, so the target falls about
  **2:25 PM EST 2026-11-08** (COMPUTED; HANDOFF says about 2:20 PM).
- New kept positions total about 158 M against g3s2's about 848 M: **+19%, 0.25 doublings**.
- **Mean labeller chain Elo** (A1's chain: S512 +966, S512r2 +1117, S512+PP about +1150,
  S512ppr2 about +1170), weighted by kept positions:
  - g3s2 without the slice: (416·966 + 406·1117)/822 = 1041;
  - with g3f and g3g: (416·966 + 406·1117 + 22.9·1150 + 135·1170)/980 = **1061, i.e. +20**;
  - with g2s1 at half weight (T4): (208·966 + 406·1117 + 22.9·1150 + 135·1170)/772 =
    **1083, i.e. +42**, at −0.15 doublings of data versus g3s2.

---

## 3. Proposals

### T1. The next retrain (g3s3), concretely

- **Mechanism.** Fold in the two freshest, best-labelled parts (g3f, g3g: 158 M kept). Remove
  the LR-noise floor at the end (T2). Score on a yardstick that sees the new data (T3). Test
  one recency arm (T4) and, if T5's measurement says so, one λ arm. The labeller policy then
  loops: candidate → promotion → g3h labelled by it.
- **Math / derivation.** A1's crude model is ΔElo = a·Δlog₂(data) + b·Δ(mean labeller
  Elo), with a ≈ 10-30 per doubling at this scale and b ≈ 0.31.
  - Uniform all-data arm: 0.25·(10 to 30) + 0.31·20 = 2.5-7.5 + 6.2 = **+9 to +14**.
  - Discounted for self-play inflation of the chain (A1 §2.2, about 1.7x on the labeller
    term): +6 to +11.
  - T2's averaging and cooldown add +2 to +7. But the 1e-5 anneal is already banked in
    S512ppr2 (§2.1), so only the residual 2-8e-5 counts.
  - Recency arm, if it wins: +0 to +8 on top (T4).
  - **Candidate against S512ppr2: +5 to +18, central +11.**
  - Caveat: if T6 shows the anneal explains most of S512ppr2's +20, then the model's
    data/label term is overstated, and I would move the centre to about +7.
- **Theory and literature.** Generational self-play distillation (KataGo, Wu,
  arXiv:1902.10565); staged retraining on better labels (nnue-pytorch wiki, per survey S1 §3);
  Viridithas's sol-old/sol-new result, where new labels alone gave +20 STC (survey S2 §5.1).
- **Why Fork.** A1 §2 (label quality is the proven engine); §2.1 above (the schedule is now
  understood); HANDOFF §3 (g3f sealed, g3g sealing tomorrow).
- **Concrete plan (to declare before the run).**
  1. *Data (no new code):* g3s2's 81 training files + g3f + g3g (the training shards; held-out
     games as in step 3), read `--interleave`, S = 92 in the trainer (unchanged), result
     weight 0.5 in arms A and B.
  2. *Uploads:* g3f (0.29 GB) and g3g (1.69 GB, the part record's `need_bytes`) as Kaggle
     datasets. Use a CPU session for the hash check (no GPU quota).
  3. *Validation:* a new multi-source held-out set. Take 300 games from each of g3f and g3g,
     and 60 from each older source as before. Order it so the trainer's prefix samples every
     source, by interleaving games across sources when building the file. Raise
     `--val-positions` to 100,000 (cost: the per-superbatch validation is single-position
     evaluation; measure its time, UNVERIFIED). Add T3's gold set for the decision.
  4. *Arms, warm from S512ppr2's float weights (T2's schedule), one seed each (§2.2):*
     - **A (uniform):** all data.
     - **B (recency, T4):** every other g2s1 file dropped (half its 416 M kept), g3g listed
       twice in `--data` (the interleaved reader opens one reader per entry, so a repeated
       path is read twice per pass: zero code; duplicates fall inside one 16.8 M shuffle
       buffer, a small correlation, acceptable).
     - **C (λ, only if T5 indicates):** as A, result weight from T5.
     - **R (continuity, optional):** the old standard recipe on A's data, to measure T2's
       gain once.
  5. *Schedule per arm (T2):* LR 1e-4 for 100 superbatches, a linear cooldown to 1e-6 over 40,
     then 10 at 1e-6. Weights averaged over the last 30 checkpoints (an offline average of
     the float `weights.bin` files; keep them, about 2.8 MB each). That is 150 superbatches,
     54 GPU-minutes per arm, so A + B + C + R fit one T4 x2 session in under 2.5 h. The
     lengths are placeholders until T2's branch probe has run. If T2 has not run, use 180 +
     40 + 10.
  6. *Scoring:*
     - A against R (same target): averaged-weight loss on the new validation set and on the
       gold set.
     - A against B (different data mix, same target): **gold-set loss only**, because a
       validation set drawn from the newest data favours B.
     - C against A (different target): loss cannot compare them. Use an 800k-node FN screen,
       1,600 games (±10).
     - The winner then goes through the usual path: parity, scale match, the endgame check
       (≤ 8 of 900 misjudged, S512ppr2's level), STC SPRT [0, 5] against S512ppr2.
- **Prediction.**
  - Arm A's averaged weights beat S512ppr2 on the gold set by ≥ 5e-5, and the candidate passes
    STC at +5 to +18.
  - B beats A on the gold set by ≥ 2e-5 (T4).
  - **Refuted if** the promoted arm's SPRT point estimate is below +5 after 3,200 games, or if
    A's gold loss is not below S512ppr2's by ≥ 2e-5. Either would mean the label/data model
    is wrong at this scale.
- **Speed cost; compute.** None at runtime (same architecture). About 3 GPU-hours, one
  session. Uploads take hours on the home link (UNVERIFIED). CPU: T3's gold set, about 1 h on
  2 threads beside g3g.
- **Cheapest first experiment.** Arm A alone, 150 superbatches, about 1 GPU-hour, on
  2026-11-08 evening after g3g seals.
- **Kill criterion.** A's gold loss not below S512ppr2's by 2e-5 → do not spend an SPRT; wait
  for g3h (more S512ppr2-class labels) instead.
- **Originality notes.** No constants from other engines. The LR values are Fork's existing
  ones; the cooldown length and averaging window are placeholders measured by T2. Credit
  KataGo and the WSD papers (T2) in ORIGINALITY.md.
- **Effort and dependencies.** About 1.5 days around waiting. It is **not in §5.6's order**:
  the order's item 8 is idea 42, and the brief's "item 8" is the next retrain. Insert it as
  "7b" right after g3g seals. It runs on Kaggle beside the GitHub queue (item 4's speed-to-Elo
  measurement, batch 4) and competes with nothing there, except one STC SPRT slot.

### T2. Warmup-stable-decay schedule with branch cooldowns, plus checkpoint averaging

- **Mechanism.** Replace the step schedule (lr·0.1^⌊(sb−1)/180⌋, main.rs) and the best-of-N
  pick with three changes:
  1. A **stable phase** at the working LR.
  2. A **short cooldown** toward about 1e-6, linear or cosine.
  3. **Averaging the float weights** of the last K checkpoints (Polyak averaging / SWA).
  
  Averaging K decorrelated checkpoints cuts the weight-noise variance about K times, which is
  equivalent to annealing further. It also removes selection bias, because there is nothing
  left to select. **Branch cooldowns** are short cooldowns forked from the stable phase at
  several points. They reveal the annealed loss as a function of stable-phase compute, which
  is the curve the flat 1e-4 phase hides (§2.1).
- **Math / derivation.**
  - The available gain is the residual noise floor at 1e-5: 2e-5 to 8e-5 (§2.1), so **+2 to +7
    Elo** at 9.3 Elo per 1e-4.
  - Compute: today a retrain spends 180 superbatches at 1e-5 that gain ≤ 2e-5 (§2.1), which is
    57 GPU-min of waste per run.
  - The branch probe costs 4 branches × 40 superbatches = 160 superbatches (57 GPU-min), the
    same as that tail. It tells us whether the stable phase does anything for warm retrains. If
    an anneal branched at superbatch 20 reaches the same loss as one at 180, a retrain needs
    about 60 superbatches (22 GPU-min) instead of 360.
- **Theory and literature.**
  - Warmup-stable-decay (WSD): Hu et al., "MiniCPM", arXiv:2404.06395. Hägele et al., "Scaling
    Laws and Compute-Optimal Training Beyond Fixed Training Durations", arXiv:2405.18392,
    shows that a short cooldown from a constant-LR run matches cosine, and that branching
    cooldowns measure intermediate points.
  - SGDR (Loshchilov and Hutter, arXiv:1608.03983).
  - Averaging: Polyak and Juditsky (1992, SIAM J. Control Optim.); SWA (Izmailov et al.,
    arXiv:1803.05407).
  - Survey S2 §5.1: Ethereal's "much larger final LR drop than tenfold" is concept only, no
    values.
  - The exact contents of the arXiv papers are UNVERIFIED beyond their titles and claims as I
    recall them; the experiment does not depend on them.
- **Why Fork.** §2.1: Fork's loss is LR-floor limited, every pre-S512ppr2 net stopped at 1e-4,
  and S512ppr2's tail is flat. §2.2: best-of-N bias is about 8e-5. A1 §5.2(b) saw the same
  noise floor at 1e-3.
- **Prediction.**
  - (a) An averaged-30 S512ppr2 (re-averaged from its own run's last checkpoints, if any were
    kept; otherwise from the T2 run) scores ≥ 2e-5 below the 1e-5 window mean on the same set.
  - (b) A cooldown to 1e-6 from the same point reaches ≥ 2e-5 below that mean.
  - (c) The STC difference against S512ppr2 is +2 to +7 (rarely worth an SPRT alone; it rides
    in T1).
  - Branch prediction: the annealed loss from superbatch 20 is within 3e-5 of that from 180
    on warm retrains (no stable-phase progress). If so, retrains can be shortened 3-6x.
  - **Refuted if** neither averaging nor the 1e-6 cooldown beats the 1e-5 window mean by
    ≥ 1e-5. The floor is then irreducible; drop T2 except for the compute saving.
- **Speed cost; compute.** Zero at runtime. Code:
  - a `--lr-schedule` option (a constant phase, then linear decay to a floor) in main.rs, about
    20 lines;
  - keep the last K checkpoints' `weights.bin` instead of deleting them (retrain_g3s2.py
    `drop_old_checkpoints`);
  - a small averaging script, CPU-side, operating on bullet's float file (KB bullet-internals
    §2.1 layout).
  
  Branching needs no code: `--resume <ckpt> --start k+1 --lr 1e-5 --lr-step 100000` gives a
  constant 1e-5 (the formula's exponent stays 0). A second resume gives 1e-6. Caveat: a resumed
  reader restarts its data pass (KB §5.7). That matters little for 30-40 superbatches on
  1.2 B positions.
- **Cheapest first experiment.** One Kaggle session, one T4, on g3s2 (no new data needed;
  runnable today):
  - warm from S512ppr2 at 1e-4, constant, 240 superbatches, keeping every checkpoint's weights;
  - branches from superbatches 20, 80, 160 and 240: 30 superbatches at 1e-5, then 10 at 1e-6;
  - an average over each branch's last 20.
  
  Total 240 + 4·40 = 400 superbatches = **2.4 GPU-hours**. Score on g3s2-val with 100,000
  positions and on the gold set (T3).
- **Kill criterion.** As "refuted". For branch lengths: if the branch from 240 beats the
  branch from 20 by ≥ 5e-5, stable-phase compute matters, and T1 uses the longer stable phase.
- **Originality notes.** Generic optimisation practice. The 1e-6 floor, K and the branch points
  are placeholders, recorded with this measurement in the constants table.
- **Effort and dependencies.** 0.5 day. It feeds T1 and replaces "the standard retrain recipe"
  (HANDOFF §5) after the owner's approval.

### T3. Gold-label validation set and label-noise measurement [NOVEL for Fork's process]

- **Mechanism.**
  1. Draw a fixed, stratified sample of kept positions from every training source: equal
     games per labeller generation, plus the slice, plus g3f/g3g held-out games. The sample
     comes from held-out games only, never training games.
  2. Label each with a much deeper Fork search: the current default, 1 M nodes, fresh 16 MB TT,
     Syzygy on.
  3. Measure every candidate net's loss against `σ(gold/S)` on this set. That gives a
     λ-independent, labeller-age-independent yardstick for "is the eval closer to a deep
     search's value?". Report it per stratum: generation, phase band, |eval| band.
  4. **Label noise:** the same positions' original 20k-node labels against gold give the
     variance of the training labels' score half. That settles A1 B2's open question.
- **Math / derivation.**
  - Cost: 50,000 positions × 1 M nodes = 5e10 nodes. At about 3.5 M nps per thread on 2
    threads (A3 §1.1, bench nps; datagen-like positions are UNVERIFIED), that is 7,100 s,
    **about 2 h on 2 threads**, or 1 h at 500k nodes.
  - Statistical power: a 2e-5 difference between two nets on 50k positions is easily resolved,
    because it is a *paired* comparison on fixed positions. The noise is in which positions
    are chosen, not in re-measurement. The paired sd of per-position squared-error differences
    is about 1e-3 (UNVERIFIED), so SE ≈ 1e-3/√50,000 ≈ 4.5e-6.
  - The gold labels' own error: at 50x the nodes they are not exact. But their error is shared
    by all candidates, so it biases rankings only toward nets that mimic S512ppr2's deep
    search. All candidates descend from it, so this bias is acceptable and is stated.
- **Theory and literature.** Using a stronger oracle as the test target is standard; it
  corrects label noise in evaluation (Natarajan et al., "Learning with Noisy Labels", NeurIPS
  2013, as general background, UNVERIFIED as precise). In chess, A1 §3.2 shows the current
  validation is dominated by result noise.
- **Why Fork.**
  - Today's set is 20k positions from about 490 games, from old sources (§2.3), scored at
    best-of-N (§2.2), with a target half made of result noise (A1 §3.2).
  - T4's recency decision is impossible on a validation set drawn from either old or new data:
    old-labelled positions favour old-trained nets, new ones favour new-trained nets.
  - Gold labels are by construction "newest labeller, deeper".
- **Prediction.**
  - (a) The 20k-node label noise, as RMS of σ(s20k/S) − σ(gold/S), is 0.04-0.08, so its
    variance (2e-3 to 6e-3) is 10-30% of today's total loss of 0.019 (UNVERIFIED magnitude).
  - (b) Ranking agreement: S512ppr2 < S512+PP < S512r2 on gold loss, matching their SPRT order.
    **Refuted** (the instrument is useless) if gold loss mis-orders those three, which are
    separated by +20 and +33 Elo.
- **Speed cost; compute.** Local CPU only, through jobctl, about 1-2 h on 2 threads beside g3g
  (one "measure" job). Code: a relabel mode. `fork_datagen` or a `fork` subcommand reads
  positions (EPD) and prints the score. If `fork` can already take EPD plus `go nodes`, a
  Python UCI driver suffices: zero engine code (UNVERIFIED whether a batch EPD scorer exists).
  The trainer needs a loader for the gold file. Simplest: write it as viriformat one-move games
  with the gold score (the slice's method, endgame_slice.py), then run fork-train with
  `--result-weight 0` and `--val gold.vf`. Zero trainer code.
- **Cheapest first experiment.** 10,000 positions at 500k nodes (about 25 min on 2 threads).
  Check prediction (b) on S512r2, S512+PP and S512ppr2 with `--superbatches 0` validation runs
  (each a minute on a GPU, or CPU-side if the CPU build can evaluate; KB §13.7 says the mock
  device cannot run graphs, so use Kaggle, a few minutes).
- **Kill criterion.** Prediction (b) fails → drop the gold set, keep the enlarged multi-source
  validation set only.
- **Originality notes.** Fork's own engine and own positions only (A+). Positions are drawn
  from held-out games, so gold-labelled positions never train. Node counts are placeholders.
- **Effort and dependencies.** 0.5 day. Gates T1's B arm, T4, idea 47.1 and 47.2's scoring,
  and the λ arm's secondary report.

### T4. Recency weighting: down-weight S512-labelled g2s1

- **Mechanism.** About half of g3s2 (g2s1, about 416 M kept) was labelled by S512, the weakest
  labeller still in the set: −151 Elo against S512r2 and about −200 against S512ppr2 (A1
  §8). There is no generalisation gap at this scale (A1 §3.3), so volume is not binding.
  Old labels then add bias more than they add information. Down-weighting them, or dropping
  them, moves the mean labeller up at a small cost in volume.
- **Math / derivation** (§2.5):
  - half-weight g2s1 gives Δ(mean labeller) = +42 versus g3s2 (+22 versus uniform g3s3) at
    −0.33 doublings versus uniform g3s3;
  - model difference B − A = 0.31·22 − 0.33·(10 to 30) = 6.8 − (3.3 to 9.9) = **−3 to +3.5**;
  - dropping g2s1 entirely: Δlabeller +70 versus uniform → 0.31·70 = +21.7, minus 0.80
    doublings·(10 to 30) = 8-24, so **−2 to +14**.
  
  The model cannot sign this; external evidence leans positive (below). Hence a cheap
  measurement, and confidence medium-low.
- **Theory and literature.** Survey S2 N1: Viridithas purged old data (+8.4 and +13.9 LTC in
  its log) and the sol-new result (+20 STC); Caissa's purely progressive data policy. The
  counter-evidence is the nnue-pytorch wiki's "training solely on better data doesn't produce
  as good results" (coverage), survey S1 §3.2.
- **Why Fork.** A1 §8 ("old-label share" row). Idea 47.1 plans to relabel generation 1 first,
  but **generation 1 is not in g3s2 at all** (HANDOFF §3: g3s2 = g2s1 + g3 parts + slice). The
  planned test would measure data that no current training uses. The question that matters is
  g2s1.
- **Prediction.** Arm B (half g2s1, double g3g) beats arm A on the gold set by ≥ 2e-5 and at FN
  by ≥ +3 (underpowered at 1,600 games; the gold set decides). A further arm "no g2s1" is worth
  running only if B wins. **Refuted if** B's gold loss ≥ A's.
- **Speed cost; compute.** None at runtime. One extra 54-min arm in T1's session.
- **Cheapest first experiment.** T1 arm B (above). If B wins, the follow-up for g3h onward is to
  relabel g2s1's positions with the then-default at 20k nodes: 416 M kept at about 1,700 per
  second = **2.8 days of the 10-thread CPU** (A1 §8). Compare: about 4.8 days for that many
  fresh kept positions. Do that only if "no g2s1" loses to "half g2s1", i.e. if the positions
  carry coverage value that fresh games do not.
- **Kill criterion.** B ≤ A on gold → keep uniform weighting, and drop idea 47.1 for this
  phase (relabelling cannot help where old labels do not hurt).
- **Originality notes.** Data mixing by file list; no constants (the 0.5 weight is a
  placeholder, not tuned).
- **Effort and dependencies.** 0.5 day. Rides in T1. **Replaces idea 47.1's generation-1 test**
  (§4).

### T5. Result weight derived from a TC-calibration playout, then one λ arm [NOVEL]

- **Mechanism.** The trainer's target is (1 − w)·σ(s/S) + w·r with w = 0.5 since B0 (main.rs
  `mapper`; DESIGN constants: "tuned per generation", never done). With ample data the net
  learns E[target | x] = (1 − w)·σ(s(x)/S) + w·p₂₀ₖ(x), where p₂₀ₖ is the expected score of
  20k-node self-play from x. The value the eval should approximate for long-TC play is closer
  to p_deep(x), the expected score under much deeper play. Both halves are biased:
  - **the score half** by the 20k search's horizon errors;
  - **the result half** by shallow play's conversion rate. Training games are 81% decisive
    (g3f: 124,547 draws of 660,770 = 18.8%). That is far more decisive than LTC self-play or
    TCEC, so the result half teaches that small edges convert. That is wrong at TCEC depth, and
    it steers the engine into drawish "advantages" (A1 §8, "draw and adjudication share").
- **Math / derivation.**
  - Choose w to minimise E[((1 − w)(σ − p_deep) + w(p₂₀ₖ − p_deep))²]. Setting the derivative
    to zero gives **w\* = Cov(p_deep − σ, p₂₀ₖ − σ) / Var(p₂₀ₖ − σ)**, a regression of the
    deep-play residual on the shallow-play residual.
  - p₂₀ₖ and p_deep are estimated by playing pairs of games from the same positions at the two
    budgets. Result noise in p₂₀ₖ attenuates the regression. Use the two-game pairs as
    independent replicates: E[r₁·r₂] removes noise from the variance term, the classic
    errors-in-variables correction.
  - Sample size: per position, Var(p̂) with 2 games is about 0.1. Over 4,000 positions the
    variance of a covariance estimate is about 0.1²/4000, so SE ≈ 1.6e-3, against a residual
    variance on the order of 1e-2. **w\* resolves to about ±0.1.**
  - Cost: 4,000 positions × 2 games × about 70 remaining plies:
    - 20k nodes: 1.1e10 nodes;
    - 200k nodes (about depth 13-14, LTC-like, UNVERIFIED): 1.1e11 nodes;
    - total 1.2e11 nodes, at 7 M nps on 2 threads about 4.8 h, or at a 100k "deep" budget
      about 2.6 h.
  - The engine for both budgets is the current default, with datagen's rules: Syzygy-5
    adjudication and score adjudication on. The comparison is of play depth, not of rules.
- **Theory and literature.**
  - Survey S1 §3.3: nnue-pytorch's λ schedule, score-first and moving toward a blend.
  - Survey S2 N2: Viridithas "eleison" (rising toward the result) +9.3 VLTC; "vestal" (recent
    data, result-only fine-tune) −57; Seer's result-only fine-tune as part of +50.
  - The evidence is mixed in sign, and a deployment-TC argument is absent from all of it. The
    regression framing is my own (NOVEL as far as I know, UNVERIFIED that nobody has done it).
- **Why Fork.** A1 §8 row 1 (never tuned; 81% decisive); A1 §3.2 (the result half dominates
  the loss noise); TCEC has no win adjudication and draws only at ≤ 6 pieces (A3 §1.6), so the
  drawish-conversion bias matters there more than in Fork's SPRTs.
- **Prediction.** Decisive share at 200k nodes from datagen-like positions ≥ 8 points lower than
  at 20k (for example 81% → ≤ 73%), and **w\* < 0.5** (point estimate 0.2-0.4). An arm at w\*
  (S re-matched) gains 0 to +8 at FN and is neutral or better at STC. **Refuted if** w\* ≥ 0.5
  or the decisive share drops < 3 points: keep 0.5. If w\* > 0.6, test the other direction.
- **Speed cost; compute.** Zero at runtime. Effects of changing w:
  - S must be re-matched (match_scale.py), because w changes the eval's spread (KB nnue-design
    §6.3);
  - search margins see a new shape (A2 §3.2);
  - loss is not comparable across w, so the λ arm is decided by FN, then STC.
  
  Playout: CPU 3-5 h on 2 threads (jobctl "measure"). λ arm: one 54-min Kaggle arm in T1.
- **Cheapest first experiment.** 1,000 positions at 20k and 100k nodes (about 40 min on 2
  threads). Read the decisive-share gap first. If it is < 3 points, stop: w\* cannot differ
  much from today's.
- **Kill criterion.** As "refuted". Arm C at w\*: FN ≤ 0 → keep 0.5.
- **Originality notes.** Positions from Fork's held-out self-play games. Playouts are Fork
  against Fork, measurement only, never training data (they are not test-match games, but they
  are kept out of training to keep the yardstick clean). w\* is derived; no constant is copied.
  Credit the survey sources for the concept of λ scheduling.
- **Effort and dependencies.** 1 day. The measurement can run now. The arm rides in T1.

### T6. Anneal-only attribution control for S512ppr2's +20

- **Mechanism.** S512ppr2 differs from S512+PP in four ways: new data and labels, the slice,
  interleaving, and **the first-ever anneal to 1e-5** (§2.1). An anneal-only control asks how
  much of +20.1 came from the anneal. It takes S512+PP's float weights and runs 40 superbatches
  at 1e-5 on S512+PP's own data (g2s1 + g3s1, interleaved, no slice). That answer sets
  priorities: CPU datagen (10 threads continuously) against training-side work.
- **Math / derivation.**
  - If the anneal alone takes S512+PP from its 1e-4-floor window, about 0.01935 on g3s2-val,
    to about 0.01917, its FN gain should be about 9.3 Elo per 1e-4 × 1.8e-4 = **+17**. That
    would leave only about +3 for data, labels and slice.
  - Alternatively the control gains ≤ 5e-5 (≤ +5 Elo), and A1's data/label model stands.
  - Cost: 40 superbatches × 21.5 s = **14 GPU-minutes**. Add a second arm (the same on g3s2,
    i.e. S512ppr2's recipe shortened) for 14 more.
- **Theory and literature.** A plain ablation; LR-noise floor (§2.1).
- **Why Fork.** §2.1. A1 §2.1 lists S512ppr2's gains as "not separable from this one run".
  This separates the biggest candidate cheaply.
- **Prediction.** The control reaches within 5e-5 of S512ppr2's window mean (0.01917) on g3s2's
  scored prefix, and FN against S512+PP lands at +8 to +20. **Refuted if** the control gains
  < 5e-5 over S512+PP's 1e-4 window, which would mean the anneal explains little.
- **Speed cost; compute.** 0.5 GPU-hour. One FN match (1,600 games locally or one GitHub stage)
  is optional; the loss alone (same architecture, same set) is enough by A1's rule.
- **Cheapest first experiment.** As above, in T2's session (same notebook, second GPU).
- **Kill criterion.** None needed; it is a measurement. The result is logged in nets.md beside
  S512ppr2.
- **Originality notes.** None.
- **Effort and dependencies.** 0.2 day. Informs T1's forecast and the priority of datagen
  against training work (§4).

### T7. Endgame-start self-play part: conversion and drawish endings

- **Mechanism.** Datagen censors the late game. Score adjudication (700 cp for 8 plies) ends
  40% of games, Syzygy entry 21%, and no draw adjudication shapes fortresses (A1 §6). The
  slice teaches ≤ 5-piece *static* WDL, not how to convert or hold 6-12-piece endings, and
  TCEC plays every game to mate or a rules draw (A3 §1.6).
- **The part.**
  - *Starts:* positions sampled from Fork's own sealed games, 8-14 pieces, not in check,
    |score| ≤ a band (placeholder), one per game.
  - *Play:* datagen at 20k nodes with the split search as today.
  - *Adjudication:* score adjudication raised or off (placeholder: off; mate, rules and Syzygy-5
    still end games), so conversion phases are recorded.
- **Math / derivation.**
  - Share: the slice's 2.1% fixed 97.7% of misjudgments (A1 §6); a similar 3-5% share
    (placeholder) is about 30-50 M kept positions.
  - Endgame games are short and cheap: about 40-60 records, positions with fewer pieces search
    faster per node, and early Syzygy exits. Cost about 1-1.5 days of CPU (COMPUTED from the
    1,000 kept per second rate, UNVERIFIED for endgames).
  - Elo: in SPRT conditions both engines probe 3-4-5 in search, and the UHO book rarely reaches
    long endings at STC, so **0 to +5 STC**. On an endgame-start book the effect is larger.
    Caissa's endgame-book self-play data gained +51 measured on an endgame book (survey S2 §3);
    I predict +10 to +30 for Fork.
- **Theory and literature.** Caissa's endgame-book data and 7-man TB positions; Integral's
  Syzygy-guided datagen; Halogen playing out Syzygy endings (survey S2 N6). Ideas 11 and 45.
- **Why Fork.** Idea 45's KRK conversion test: 3 of 20 won KRK starts drawn by the fifty-move
  rule (S512r2). The slice fixed the static check (8 of 900), but no data covers playing these
  endings. The 18.8% draw share underrepresents holding draws.
- **Prediction.** The candidate trained with the part (warm, T2 schedule) scores +10 to +30
  against the same recipe without it, on an endgame-start book built from Lichess 2026-09
  positions with ≤ 12 pieces. That source is disjoint from training starts (Fork games) and from
  UHO. STC on UHO is within [−3, +5]. **Refuted if** the endgame-book gain is < +5.
- **Speed cost; compute.** Zero at runtime. Code:
  - datagen must start from a given position list (it already takes an EPD openings file;
    whether `--openings` accepts arbitrary FENs with random plies 0 is UNVERIFIED but likely);
  - a sampler script over sealed shards;
  - an owner decision, because it is a datagen setting change. The labeller policy is unchanged
    (current default).
  
  The test book needs a new disjoint EPD (CC0 positions; data decision 6 keeps UHO for tests
  only, and this is a second test book: owner decision).
- **Cheapest first experiment.** A 6-hour part (about 20 M records), an S512ppr2 warm
  continuation with and without it (2 arms × 54 min), and an endgame-book FN of 1,600 games.
- **Kill criterion.** Endgame-book FN < +5 → drop. Keep the slice.
- **Originality notes.** Credit Caissa, Integral and Halogen release notes (concepts) in
  ORIGINALITY.md. The piece bands and the share are placeholders.
- **Effort and dependencies.** 1.5 days, after T1. TCEC-relevant; idea 11's "re-evaluate"
  status becomes this.

### T8. Next datagen part: the 2026-09 book and a 25% save-share arm

- **Mechanism.**
  - **(a) Openings.** Every part since g0 uses lichess-2016-09 (591,871 starts). g2+g3 played
    about 25 M games, about 42 per opening, with only 2-4 random plies at creation and 2-4 per
    game. The 13.9 M-position 2026-09 book (HANDOFF §3) gives about 1.8 uses per start over the
    same volume.
  - **(b) Games as the unit of data.** Idea 13's +65.5 fits "games, not positions" (A1 §7 H1).
    Saving 25% instead of 50% plays about 1.5x the games for 0.75x the saved labels per
    CPU-hour (A1 §7).
- **Math / derivation.**
  - (a) Duplicates: same-opening games share early positions until the random plies and
    TT-state diverge. The early-position duplicate rate is unmeasured (A1 §8). If ≥ 10% of kept
    positions are near-duplicates of others, the effective data is 10% smaller (−0.15 doublings,
    about −2 Elo). The bigger expected effect is distribution breadth: PlentyChess #227 gained
    +13.2 STC from a datagen start-distribution change (mechanism not described; survey S2 N5).
    **0 to +5.**
  - (b) At today's scale (no overfitting, A1 §3.3) the diversity gain shrinks, while the label
    count falls 25%. Net −3 to +6.
- **Theory and literature.** KataGo playout-cap randomisation (Wu, arXiv:1902.10565, as idea 13
  credits); survey S2 N5.
- **Why Fork.** HANDOFF §3 (the unused book); ideas.md 13 (the split search's measured gain);
  A1 §7.
- **Prediction.**
  - (a) A duplicate count (64-bit Zobrist over one shard per part) finds ≥ 5% of kept positions
    with ply ≤ 20 duplicated. **Refuted if** < 2%; then the book switch is cosmetic but still
    harmless.
  - (b) A B0-sized two-arm test (idea 13's design, minutes of GPU) shows 25% ≥ 50% by ≥ +10 at
    the small-net scale. **Refuted if** ≤ 0 with seeds within ±15.
- **Speed cost; compute.** (a) No extra CPU (the book switch is a setting). (b) Two 6-hour parts
  for the small-net test. That displaces 12 h of g3h-style data: expensive in the scarcest
  resource, so (b) only if the owner wants it before Phase 4's end.
- **Cheapest first experiment.** (a) The duplicate histogram (minutes of CPU). Then switch g3h
  to the 2026-09 book at its start: an owner decision, recorded in g3h's manifest.
- **Kill criterion.** (b) as refuted. (a) none: if the count is low, switch anyway, since there
  is no cost.
- **Originality notes.** Settings are Fork's (Lichess CC0 positions under strategy A+).
- **Effort and dependencies.** 0.5 day for (a). (b) competes with datagen CPU: defer unless the
  owner prioritises it.

### T9. Equal-compute scratch control

- **Mechanism.** The warm lineage's edge over scratch (4.2e-4) is about 1.7e-4 of missing anneal
  (§2.1) plus about 2.5e-4 of missing compute. A scratch run at the lineage's total compute (5.4
  B samples), with T2's schedule, measures whether the lineage is a moat (stale old-label biases
  locked in, warm seeds that stop exploring) or just banked compute. If scratch matches warm,
  future architecture changes (hidden layers, king buckets, a wider L1) can train from scratch
  without a handicap. Idea 40's layers, survey S2's N3/N8 and idea 46's designs all need that.
- **Math / derivation.** 1,080 superbatches × 21.5 s = **6.45 h on one T4**, which fits one
  session beside T2 on the other GPU. Scratch s1 fell 1.1e-4 over its 1e-4 phase and was still
  falling (§2.1). Extrapolating 3x compute plus an anneal: 0.01968 (window) − 1.7e-4 (anneal) −
  about 1e-4 (compute) ≈ 0.01941 to 0.0192, against warm's 0.01917 (window).
- **Theory and literature.** A1 §5.3 ("the fair control is still missing"); compute-optimal
  training (Hoffmann et al., arXiv:2203.15556) as general context only.
- **Why Fork.** A1 §5.2(d); the recipe decision of 2026-11-06 compared unequal compute and
  unequal final LR.
- **Prediction.** Scratch-5.4B with a cooldown lands within 5e-5 of warm (window or averaged) on
  the gold set. **Refuted if** it is > 1e-4 worse. The warm lineage then carries something
  beyond compute, and architecture changes must stay zero-initialised widenings.
- **Speed cost; compute.** 6.5 GPU-hours, about a fifth of a week's quota. No CPU.
- **Cheapest first experiment.** As stated, on g3s2 (or on g3s3 once it exists).
- **Kill criterion.** As refuted. Then do not plan from-scratch architecture retrains in Phase 4.
- **Originality notes.** None.
- **Effort and dependencies.** 0.3 day. Its value depends on Phase 4 still planning an
  architecture change (idea 40's later layers, QAT-plus-head, king buckets): an owner
  priority call.

---

## 4. Critique of the current plan in my domain

1. **The standard retrain recipe (HANDOFF §5) wastes half its GPU and picks noise.**
   - Its 180-superbatch 1e-5 tail gains ≤ 2e-5 (§2.1).
   - Its best-of-360 pick is optimistic by about 8e-5 (§2.2), twice the 4e-5 "resolved"
     threshold.
   - Its second seed is redundant for warm runs (spread 0.7-1.2e-5).
   - **Redesign:** one seed per arm, T2's schedule, averaged weights, window or averaged losses,
     and the gold set for cross-data decisions.
   - Saving: about 50-75% of a retrain's GPU, which funds T2's branches and T9.
2. **"Warm start wins, so warm is the standard" overstates what was learned.** The comparison
   put warm at a final LR of 1e-5 against scratch at 1e-4, with 3x the lineage compute (§2.1).
   That is two confounds. Keep warm as the default (it is cheaper), but record the reason
   correctly, and run T9 before concluding that architecture changes need warm widening.
3. **A1 B1 ("3x longer low-LR, +8 to +20") should be shrunk.**
   - For warm retrains, Fork's curve shows no stable-phase progress visible at 1e-4 and a flat
     1e-5 tail.
   - What remains is the residual floor (+2 to +7, T2), plus whatever the branch probe shows
     about stable-phase compute.
   - For scratch runs, B1 holds (T9).
4. **Adam without bias correction (A1 §5.2a) is real but no longer matters.**
   - At a warm LR of 1e-4, the first-superbatch bump is +4e-5 and recovers within the noise
     (warm s1: 0.019305 → 0.019345 → within window by superbatch 20).
   - It mattered at 1e-3, where the dominant harm was the high-LR noise floor and forgetting
     rare patterns, not the bias itself.
   - Cheap hygiene: keep `optimiser_state` (moments) of the promoted checkpoint in the result
     folder (about 11 MB more), so a future warm start can resume moments.
   - Do not raise warm LRs: nothing in the curves says a warm 1e-4 phase is too slow, and 1e-3
     demonstrably scrambles unanchored knowledge (KQK 0 → 59).
5. **Catastrophic forgetting and EWC: drop.**
   - Fork trains on the full snapshot every time (complete replay), so EWC-style penalties
     (Kirkpatrick et al., arXiv:1612.00796) solve a problem Fork does not have.
   - The "endgame knowledge loss" was rare, absent patterns perturbed by LR 1e-3 (A1 §6.4).
   - The slice (anchoring data) plus low LR fixed it: 351 → 8.
   - Keep the slice in every snapshot. Keep the 900-position check as the guard.
6. **Idea 47.1 (relabel generation 1 first) targets data no current snapshot contains.**
   Replace it with T4. Relabel g2s1 only if dropping it hurts and down-weighting helps.
   Relabelling keeps old trajectories and old results; fresh generation renews both, at only
   about 1.7x the CPU per kept position (A1 §8).
7. **Idea 47.2 (quiet-position filter): shrink to the offline count, at low priority.**
   - The KB's own reading of arXiv 2412.17948 is "weak evidence, no ablation" (KB research §2).
   - Fork already filters in-check and played-capture positions. There is no overfitting, so
     discarding 20k-node labels costs data. The training-serving mismatch at quiescence
     stand-pat nodes is a real risk (KB §3.6).
   - Expected Elo 0 to +3. If run, decide on the gold set, with the slice exempt.
8. **Idea 46's distillation from S512+X: lowest priority in my domain.**
   - Replacing or mixing search labels with a static net's output removes search amplification.
     The public record is mostly negative (survey S2 N10: −3 for static-output relabels; −26
     for "alembic"; +3.7 once).
   - **The better use of a stronger-at-fixed-nodes net is as a labeller.** Datagen is
     node-limited, so labeller value is FN strength per CPU, not STC strength. Using A1's model
     with nps ratio r and FN gain g: student Δ ≈ a·log₂r + b·g.
     - S512+X: 15·log₂0.818 + 0.31·25.7 = −4.3 + 8.0 ≈ **+4**.
     - XGR r2: −9.7 + 9.5 ≈ 0.
   - Marginal, and it breaks the labeller policy's simplicity. Not recommended now; worth
     recording as a principle for a future large teacher (a Fork-own wide net built only for
     labelling: if its FN gain exceeds about 50·log₂(1/r), it pays).
9. **The result weight was promised "tuned per generation" (DESIGN constants table) and never
   was.** T5 gives a derivation rather than a blind ladder. Note: survey S1 §7.2's "λ schedule
   seed" is a cheaper blind test, but its kill rule ("no FN gain beyond seed spread") cannot
   resolve +3-5 effects at 1,600 games.
10. **Checkpoint choice by games** (survey S1 §7.2.2: every 20th net played at fixed nodes) does
    not suit Fork's power budget. A 1,600-game FN match resolves ±10 (A3 §2.5), while candidate
    checkpoints of one warm run differ by ≤ 3e-5 (≤ 3 Elo). Average instead (T2). Use games
    only across targets or architectures, where loss cannot compare.
11. **Cadence: when to retrain.** Each loop (promotion → new part → retrain) is now about 1.5
    days of datagen for about 135 M kept (g3g). By the model, a retrain pays an SPRT slot only
    when new-label share × labeller jump is large enough. Here 0.31·Δ(mean labeller) +
    a·Δlog₂(data) ≥ about +8, which means new labels ≥ about 15-20% of the set when the labeller
    jump is about +20-30 chain Elo. g3f + g3g (16% of g3s3) is at that threshold. After g3s3,
    retrain each time a part adds ≥ 150 M kept from a promoted labeller, and down-weight the
    oldest generation (T4) instead of growing indefinitely.
12. **Curriculum: not proposed.** No Fork evidence and weak external evidence for value
    regression. Interleaving (already on) is the important ordering fix (A1 §3.4).
13. **Score clipping and filters.** |score| > 20000 drops mate and TB scores and unsaved records.
    Sigmoid saturation (σ(700/92) = 0.9995) already makes clipping lopsided targets a no-op.
    Nothing to change. The played-capture filter stays until 47.2's offline count says otherwise.
14. **The Syzygy slice.** Keep it at about 2%. Do not chase 6-7-piece slices: at TCEC those
    positions are probed in search, so their static eval matters little. The 8-14-piece
    conversion region is the gap (T7). Run a slice ablation only if T1's endgame check regresses.

**Proposed order in my domain** (Kaggle and local CPU, beside GitHub's queue):
1. Now: T3's gold set (CPU, about 1-2 h on 2 threads) and T5's 1,000-position pilot (CPU, about
   40 min). Both are "measure" jobs beside g3g.
2. Now: one Kaggle session (T4 x2, about 6.5 h), with T2's branch probe and T6 on GPU 0
   (2.9 h) and T9 on GPU 1 (6.45 h).
3. 2026-11-08 after g3g seals (about 2:25 PM): uploads, then T1's session (arms A, B, optional
   C and R, about 2.5 h), then parity, scale, endgame check, STC SPRT.
4. g3h starts from the 2026-09 book (T8a, owner decision). T7's part follows if the owner wants
   TCEC endgame coverage in Phase 4.

GPU total ≈ 9-10 session-hours (if T4 x2 counts once) out of 30 a week.

---

## 5. What I could not verify

- The exact composition of g3s2-val's scored 20,000 positions. The first 9,916 bytes match
  g3s1-val, and S512+PP's loss differs by 1.3e-5 between the two, but I did not parse the file.
- The noise-floor exponent α. The residual gain available at 1e-5 (2e-5 to 8e-5) rests on the
  two warm plateaus and the fluctuation-sd ratio, not on a run at 1e-6.
- That the anneal explains most of S512ppr2's +20.1 (INFERRED from §2.1; T6 tests it).
- Elo per 1e-4 of loss (9.3) on any validation set other than g3s2-val, and on the proposed gold
  set at all.
- Whether two parallel trainings on T4 x2 count once against the weekly quota.
- Whether `fork` or `fork_datagen` can score an EPD list at a node budget without new code, and
  whether datagen accepts arbitrary FEN starts with zero random plies (T3, T7).
- The 20k-node label noise and its share of the loss (T3 measures it).
- Nodes-to-depth at 100k-200k nodes on the current net (used as "LTC-like" in T5).
- Throughput of datagen from endgame starts (T7) and the early-position duplicate rate (T8).
- The g3g kept count assumes A1's 67.7% kept share of saved records and the 54.4% saved share.
- Literature details (WSD papers' exact claims, Mandt et al.'s applicability to Adam, Natarajan
  et al.) are cited from memory as concepts; titles and arXiv numbers are believed correct,
  contents UNVERIFIED. No engine source was opened. No other engine's constant appears here;
  every number proposed is a placeholder or derived from Fork's own records.


---

# B6. Search theory (S)

## B-S: search theory applied to Fork (Phase 4 think tank, specialist S)

## 1. Summary

Fork's search record fits one simple model, which I check against the
logged numbers. A selectivity feature is worth R(TC)·log2(N_off/N_on), its
node saving priced at about 106 Elo per doubling at STC and 95 at LTC (A1
§4, A3 §1.4), less an accuracy cost. Call the ratio of accuracy cost to
speed value ρ. From bench node counts and SPRT results, every adopted
selectivity change has ρ well below 1:
- IIR has ρ ≈ 0.4;
- multi-cut is verified by a search;
- SE is negative-cost: it buys accuracy with nodes.

Every failed one has ρ ≈ 1.2-1.6: the negative extension, rising RFP,
threat buckets, and (by mechanism) ProbCut and RfpMargin 40. The difference
is not "Fork prunes enough". **Features that defer or verify information**
(IIR's re-search next iteration, multi-cut's half-depth proof, SE's test)
**lose few Elo per node saved. Features that trust the static eval or a
stale history more lose many.**

Three theoretical results follow, each falsifiable cheaply:
1. **The optimal marginal error rate of a prune is depth-independent** if
   the decision-critical skeleton of the tree has constant width per depth
   layer: the nodes saved and the cost of an error both scale as g^d.
   Fork's two measured rules that passed are both equal-error rules: LMP's
   uniform 1% bound and SE's ≥90% precision at every depth. RFP's measured
   error, by contrast, falls tenfold from depth 1 to depth 6. So RFP is too
   loose at depth 1 and too tight at depth 4-6, which one-sided tests
   (RfpMargin 40, rising RFP) could never find. This gives a concave
   margin (about 20 + 61·d in bootstrap units, a derived placeholder).
2. **"Round once" fractional LMR (idea 43's level 1) gives an exactly
   linear mean response.** A term worth a ply/4 shifts the mean reduction
   by 0.25 ply over Fork's (d, m) table (computed). That removes the
   step-function problem without idea 43's full refactor. **Centring has to
   be over the LMR-candidate population**, which the selector has already
   sorted to the low-history end. That explains the −10.8 of the LMR
   history term better than "history does not work".
3. **Time reallocation by node share is worth the time-equivalent
   exp(ρ²_s·CV²/2).** At plausible predictive power that is a 5-8% time
   equivalent, **+8 to +12 Elo at STC and as much or more at LTC**. The
   soft-limit overshoot from geometric iteration growth costs only about
   1.5 Elo of noise.

So: node-share time management should move into Phase 4 (a plan change for
the owner). Batch 4 should shrink to the items with information-adding
mechanisms. My predictions: cut-node LMR is the most likely pass; upcoming
repetition is correct but undervalued by UHO SPRTs; razoring, bad-capture
futility and the malus balance are near zero.

### Ranked proposals

| ID | Title | Expected Elo at LTC (range) | Effort (days) | Confidence | NOVEL? |
|---|---|---|---|---|---|
| S1 | Node-share TM plus a resolution-aware soft stop, the curve derived from Fork's own instability data; moved into Phase 4 (plan change) | +8 to +15 | 1.5-2 | medium-high | the derivation (for Fork) |
| S2 | "Round once" fractional LMR (idea 43 level 1 only) with mean-preserving, candidate-centred LMR terms (history, cut node, check relief re-fit) | +4 to +10 (sum over the terms it unlocks) | 1-1.5, then SPRTs | medium | partly (centring on the candidate population) |
| S3 | Concave RFP and futility margins from Fork's own error data (equal marginal error across depths) | +2 to +6 | 0.5 + one local measurement | medium-low | yes (derivation) |
| S4 | Equal-marginal-error calibration of all selectivity: sampled verification searches, then shape-first SPSA seeds | +3 to +10 (realised through S3 and SPSA) | 2-3 of local CPU | medium-low | yes |
| S5 | Batch-4 triage: per-item predictions, a node-saving screen, reorder and demotions | +2 to +5 from the survivors; saves about 20 GitHub-hours | 0 | medium | no |
| S6 | Node types beyond LMR: NMP and IIR gated by expected type; post-LMR re-search depth | +2 to +7 | 1-2 | medium-low | no |
| S7 | Depth-concave singular margin, extension parameters tuned only at LTC, explosion guard in node terms | +1 to +5 at LTC (≤ 0 at STC) | 1 + an LTC run | low-medium | partly |
| S8 | History hygiene: per-search scaling, the malus as a re-centring (SPSA, not SPRT) | 0 to +4; an enabler for history-gated pruning | 0.5 | low-medium | no |
| S9 | Time-control scaling classifier (two-depth bench) to route tests to LTC and to design the removal round | enabler | 0.5 | medium | yes |

---

## 2. Models shared by the proposals

### M1. Speed side: Elo per node, per ply and per doubling

- **Rate.** R_STC ≈ 106 Elo per doubling of nps, about 1.5 Elo per 1%;
  R_LTC ≈ 95 (A1 §4.1, A3 §1.4; the orchestrator's Phase-B note).
- **Growth.** Iteration growth g = 1.66 (median, depths 8-14, bootstrap;
  DESIGN "Iteration growth"). One doubling of time buys
  1/log2(1.66) = **1.37 plies**, so one ply is worth about
  106 × log2 1.66 = **77 Elo at STC** and 70 at LTC.
- **Depths.** STC moves reach about depth 15 (A3 §1.1). LTC is 2.32
  doublings more, so about +3.2 plies (depth about 18). TCEC is about 7-8
  single-thread doublings beyond STC (A3 §1.6), so about +10 plies (depth
  about 25 before threads). All of this assumes g stays 1.66, which is
  UNVERIFIED at depth > 14.
- **Constant-factor saving.** A change that saves a fraction s of nodes at
  equal accuracy is worth R·log2(1/(1−s)): 1% ≈ 1.5 Elo, 5% ≈ 7.9, 20% ≈ 34
  at STC.
- **Rate saving.** A change to the growth rate (g → g′) saves
  1 − (g′/g)^D at depth D. For example g 1.66 → 1.65 saves 8.7% at D = 15,
  10.3% at 18, 14% at 25 and 16.6% at 30 (computed). Its speed value
  therefore **grows with TC**, while a constant-factor saving is worth a
  fixed log2 fraction times R(TC), which falls slightly with TC.

### M2. Effective branching factor under reductions (Knuth-Moore extended)

- **Minimal tree.** For a perfectly ordered uniform tree, the leaf count is
  b^⌈D/2⌉ + b^⌊D/2⌋ − 1 (Knuth and Moore 1975), so the growth rate is
  √b ≈ 5.9 for b = 35.
- **With reductions.** Alternating cut and all nodes, with all-node
  children i searched at depth d − 1 − r_i, the growth per ply g solves
  **g² = Σ_i g^(−r_i)**.
- **Worked case** (3 moves unreduced, 32 late moves reduced by r):

| r | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| g | 5.92 | 3.49 | 2.71 | 2.34 | 2.13 |

  Fork's 1.66 comes from LMR plus everything else: LMP, futility, NMP, RFP
  and TT cutoffs.
- **Sensitivity.** g is most sensitive to the reductions of the many late
  moves, and LMR's r grows with log d. So **LMR-class changes are rate
  changes, and frontier prunes (d ≤ 6) are constant factors.** This is the
  quantitative reason behind KB §1 lesson 3 and SF's VLTC experience
  (survey S1 §4): rate changes and depth-precision gains favour LTC.
- **Ordering at all-nodes.** At an all node every child is searched
  whatever the order. Ordering quality matters only at cut nodes (and PV
  nodes). This is used in S6.

### M3. Accuracy side: the speed/accuracy decomposition of Fork's own results

These use bench nodes at fixed depth (or time to depth) as the speed proxy,
with R = 106, against the SPRT results (A2 §2, DESIGN constants rows,
sprt-log via A2/A3):

| Change | Node change | Speed value (Elo) | SPRT | Implied accuracy term | ρ = cost/speed |
|---|---|---|---|---|---|
| IIR (d ≥ 8, every node type) | −20.8% to depth 14 | +35.7 | +21.45 | −14.3 | **0.40** |
| Negative extension | −28.3% | +50.8 | −8.73 | −59.5 | 1.17 |
| Rising RFP | −5.9% | +9.3 | −3.78 | −13.1 | 1.41 |
| Threat buckets (includes nps cost) | −6.4% | +10.1 | −6.08 | −16.2 | 1.60 |
| LMR history term | −0.27% | +0.4 | −10.81 | −11.2 | ≈ 28 (anomaly; S2) |
| Singular extension | +30.6% | −40.8 | +14.12 | **+54.9** | (buys accuracy) |
| Razoring at its placeholders | **+1.7%** at depth 10 (DESIGN batch-4 row) | −2.6 | not run | ? | (adds nodes) |

Caveats:
- The node changes are at fixed depth on the bench with fresh state. In
  games, TT and history carry-over change them.
- nps changes are not included; none was measured (A2 "could not verify").

The pattern is still sharp. **Information-preserving selectivity has
ρ ≈ 0.4. Static-evidence selectivity has ρ ≈ 1.2-1.6.** A batch-4 item
with a frontier-prune mechanism and a few % node saving is therefore
predicted at **R·log2(1/(1−s))·(1 − ρ) ≈ −1 to −3 Elo** unless its
mechanism is in the low-ρ class. This is the screen used in S5.

### M4. Where errors cost: an equal-marginal-error condition

- **Setup.** Let a heuristic prune when a statistic z (for RFP,
  (prune_eval − β)/σ_d) passes a threshold θ_d at remaining depth d. As θ
  moves, the nodes saved change at rate f(θ)·S(d) and the errors at rate
  f(θ)·P(wrong | z = θ)·C(d). Here f is the density of z at the
  threshold, S(d) the subtree saved (∝ g^d) and C(d) the expected Elo cost
  of a wrong bound returned from depth d.
- **Condition.** Maximising accuracy for a node budget (a Lagrangian with
  multiplier λ) gives, for every heuristic and depth,
  **P(wrong | at threshold) = λ·S(d)/C(d)**. The density f cancels, so the
  condition does not depend on how many nodes sit near the threshold.
- **Hypothesis H_crit.** The number of decision-critical nodes per depth
  layer (the PV skeleton and its close alternatives) is roughly constant.
  Then the share of nodes at remaining depth d that are critical scales as
  1/(nodes in that layer) ∝ g^d, so C(d) ∝ g^d, and **the optimal marginal
  error rate is the same at every depth and for every heuristic**. If
  instead C(d) ∝ h^d, the optimum scales as (g/h)^d. The first
  re-partition SPRT (S3) tests H_crit directly.
- **Literature.** Error-propagation results support the premise that
  frontier errors are damped by deeper search in chess-like trees. Minimax
  "pathology" arises for independent leaf values (Nau 1982; Beal 1980;
  Pearl 1983). In trees whose sibling values are correlated, as in chess,
  deeper search filters leaf noise (Pearl 1983; Nau 1982 on dependence).
  Exact page references are UNVERIFIED.
- **Fork's record agrees** (A2 §6.5):
  - LMP's constant came from a uniform 1% bound at depths 1-3 (DESIGN
    `LmpQuietAllowance`);
  - SE's three constants came from a uniform 90% precision at depths 6-12;
  - the mean-cutoff-index metric scores ordering directly.

  These are exactly the measurements that predicted their SPRTs. RFP's 80
  was justified only as a lower bound, and its linear shape was never an
  equal-error shape.

### M5. Time as a resource across moves

- **Setup.** If move i's expected Elo grows as c_i·ln t_i, maximising
  Σ c_i ln t_i subject to Σ t_i = T gives **t_i ∝ c_i**.
- **Gain.** Against uniform allocation the gain is
  Σ c_i ln(c_i/c̄), about the time-equivalent factor exp(CV²/2), where CV is
  the coefficient of variation of c. A noisy predictor (node share)
  recovers only the explained part, about exp(ρ_s²·CV²/2).
- **Numbers** (CV ≈ 1, computed):

| ρ_s²·CV² | Time equivalent | Elo at R = 106 |
|---|---|---|
| 0.05 | ×1.025 | +3.8 |
| 0.10 | ×1.051 | +7.6 |
| 0.15 | ×1.078 | +11.5 |
| 0.20 | ×1.105 | +15.3 |

- **Across the game.** R falls only from 106 to 95 between 8+0.08 and
  40+0.4 (M1). So the "spend more early or late" question is a
  second-order lever next to per-position difficulty. Node share should
  come before base-allocation tuning.
- **Overshoot.** With the soft limit checked between iterations, the spend
  is X = g^U (U uniform). Its mean is (g − 1)/ln g = 1.30 soft limits
  (A2 §4). The allocation noise this injects costs E[ln X] = −0.0107 in log
  time at g = 1.66 (−0.031 at the p90 growth of 2.38). That is about
  **−1.6 Elo** (−4.7 at p90) (computed). **Fixing the granularity is worth
  little; reallocating by difficulty is worth a lot.**

---

## 3. Proposals

### S1. Node-share time management with a resolution-aware soft stop (move into Phase 4)

- **Mechanism.** After each finished iteration, scale the soft limit by a
  decreasing function of the best move's share of that iteration's nodes,
  normalised so the mean spend is unchanged. Separately, at the soft check,
  do not stop while the last iteration ended with the best move changed or
  a root fail high or fail low unresolved; continue up to a capped
  multiple of soft, inside the hard limit. Fork already computes
  `root_moves_[i].nodes` and `.share` every iteration (searcher.cpp lines
  800-805), today only for idea 23's LMR context.
- **Math / derivation.**
  - By M5, with the share explaining ρ_s² of the variance in move
    difficulty: ρ_s²·CV² of 0.10-0.15 gives a time-equivalent of 5-8%, so
    **+7.6 to +11.5 at STC**.
  - At LTC, R is 10% lower, but the share is a better predictor at depth
    (KB time-management §4.4: "a deep iteration's node distribution is a
    better estimate"), so ρ_s² rises. Net about +7 to +14.
  - The resolution-aware stop. 626 of 34,254 node-limited searches (1.8%)
    ended with a fail high pending (ideas.md 29), and playing those lost
    (−14.6). If a third of them hold, and holding moves a game-relevant
    decision in about 1 in 20 cases, that is worth roughly +1 to +3
    (low-confidence arithmetic).
  - The granularity fix alone is worth ≤ 1.6 Elo (M5), so it is not
    pursued separately.
- **Theory and literature.**
  - Allocation by expected decision value is standard (Hyatt 2013 thread
    and Šolak and Vučković 2009, via KB time-management §4.2-4.4).
  - Baier and Winands (2016, via KB §6) separate "real" TM gains from a
    mere shift of time across move numbers. Their control design applies
    here.
  - The published node-share gains, +4 to +21 across about ten engines,
    hold or grow at 40+0.4 in four of them (KB §4.4). Survey S2 §4.2 reports
    +13.4 at LTC for one engine.
- **Why Fork.**
  - Fork has **no** dynamic term (A2 §4).
  - TCEC's 30'+3" makes every start/stop decision a large block of time
    (KB §3).
  - Data generation is node-limited, so labels are unaffected (orchestrator
    note; survey S1 7.1.a).
  - Every later LTC test, the SPSA retune and the final gauntlet will play
    with whatever TM exists. Tuning margins under a TM that is replaced
    later wastes part of that work.
- **Prediction.** The node-share term alone passes STC [0, 3] at +5 to +12
  within 2-4 stages, and an LTC confirmation is ≥ the STC point estimate.
  **Refuted if** STC is H0 at the better of two ladder slopes, or LTC ≤ 0.
- **Speed cost; data / compute.**
  - Zero nps: the term acts once per iteration and is deterministic in
    nodes, outside bench (`go depth`).
  - GitHub: a 2-value ladder (≤ 4 stages), an SPRT (up to 12 stages) and an
    LTC run (≤ 6 stages).
- **Cheapest first experiment: derive the curve from Fork, not from other
  engines.**
  - On about 2,000 positions from g3 games (the same pool as
    clock_positions.py), run node-limited searches at about 2 M nodes (a
    local CPU job via jobctl, about 1 hour at low priority).
  - Log per iteration the best move's share s_k, and whether the best move
    at iteration k+2 differs from the one at k.
  - The fitted P_change(s) directly gives (a) the curve shape (t ∝
    P_change^γ, normalised) and (b) ρ_s², hence the predicted Elo from
    M5's table **before any game**.
  - Deriving the slope from Fork's data also avoids the constant-screen
    collisions that copied curves invite (non-negotiable 6).
- **Kill criterion.**
  - If ρ_s² < 0.03 (time-equivalent < 1.5%, < +2.3 Elo predicted), skip
    the SPRT and try the stability signal instead.
  - If the SPRT is H0 at both ladder values, drop the term.
- **Originality notes.** The idea is generic and credited in the KB (§4.4
  lineage). Use no other engine's curve or constants. The shape and slope
  come from the measurement. Credit the KB lineage in ORIGINALITY.md.
- **Effort and dependencies.**
  - 1.5-2 days.
  - **A plan change:** DESIGN §5 puts TM in Phase 5 (line ~425). I propose
    the node-share term and the resolution-aware stop as a Phase 4 item
    placed before §5.6 item 12 (SPSA). The rest of Phase 5 stays where it
    is: base allocation at a TCEC-shaped control, safety, tablebase
    latency. The owner decides.

### S2. "Round once" fractional LMR, with mean-preserving, candidate-centred terms

- **Mechanism.**
  - Compute the LMR reduction in 1/64 ply, without its final rounding (the
    table already works in fixed point: lmr_table.hpp). Add every
    adjustment in the same units: history, check relief, cut node, PV
    trace, idea 42's continuation terms. Round once to whole plies for the
    child.
  - Child depth, TT depth and every threshold stay whole plies. This is
    **idea 43's level 1 only** (KB §3.35 "levels 1-3").
  - Every new term is offset so the **mean reduction over LMR sites** is
    unchanged. The counters exist: `lmr_plies_sum` / `lmr_searches`.
- **Math / derivation.**
  - *Linear response.* For Fork's table L(d, m) = log2 d · log2 m / 4.5,
    the fractional parts of L are close to uniform. Over d 3-24 and m 4-30,
    weighted by node frequency g^(−d), the decile masses are 0.07-0.12
    (computed).
  - So E[round(L + a) − round(L)] = 0.25 for a = 0.25, 0.50 for 0.5, and
    0.12 for 0.1 (computed). **A sub-ply term acts continuously in
    expectation**, as a dithered whole ply: a term of 0.3 ply flips the
    rounding of about 30% of sites.
  - Today's form is `order_score / 24000` in integer division, truncated
    toward zero. It is **exactly 0 for |score| < 24,000** and ±1 ply beyond
    that, a step function with a dead zone over about 70% of its range.
  - *Selection bias.* The selector orders quiets by the same ordering
    score that the history term reads (move_selector, quiet_order_score).
    LMR applies only from move 4 on (`LmrMinMove`), so LMR candidates are,
    by construction, the moves with low scores.
  - So a term centred at zero over *all* quiets has a negative mean over
    the candidates, and **adds reductions on average**. That is the
    direction every Fork failure shares (A2 §3.1).
  - The bench agrees: with the term on, nodes fell by 0.27%, a net
    increase in reduction.
  - The fix is to subtract the candidates' mean, c = E[score | LMR site],
    before scaling. Equivalently, offset the base so the mean reduction is
    unchanged. That is the discipline SF's commit messages describe
    (survey S1 7.1.d, e7e78aa0, 2343f71f).
- **Theory and literature.**
  - Fractional depth: Levy, Broughton and Taylor's SEX algorithm (1989);
    CPW "Fractional Plies"; KB §3.35.
  - The evidence that matters: level 1 (fractional LMR arithmetic) passed
    in several engines. Level 2 (full fractional depth) was removed after
    five years without gain in one lineage, and in another failed at STC
    while passing at VLTC (KB §3.35 evidence; survey S2 §6).
  - History as a reduction signal: Schaeffer 1989 (the history heuristic)
    for ordering. The LMR use is engine practice (KB T16).
- **Why Fork.**
  - A2's mechanism (1) is "whole plies". The check relief's value shrank
    from +11.3 to about +3 (A2 §2.1), which suggests the optimal relief is
    now below 1 ply.
  - Batch 4's cut-node and PV-trace terms are whole-ply placeholders
    (DESIGN batch-4 rows "the smallest unit").
  - Idea 23's correction slot returns whole plies too.
  - SPSA on LMR parameters sees step functions today (KB §3.35 "smooth
    parameters").
- **Prediction.**
  1. The refactor is bench-identical with every new term at 0. This is a
     check, not an SPRT.
  2. A stats build shows E[order score | LMR site] < 0, by at least 10% of
     its ±35,000 range, on game positions. **Refuted if** |mean| < 5%:
     then the selection-bias explanation of −10.8 fails, and the
     persistence and speed explanations remain (A2 O3).
  3. A centred, mean-preserving history term at about 1/3 to 1 ply per
     score SD passes STC [0, 3] at +3 to +7. **Refuted if** H0 at both
     ladder values.
  4. A fractional cut-node term (S5) beats the whole-ply one in a
     head-to-head ladder.
- **Speed cost; data / compute.**
  - The arithmetic is a few adds per LMR site, at no measurable cost.
  - The ordering score must not be recomputed per made move. The batch-4
    build recomputes `quiet_order_score` for every quiet when the term is
    on: three table reads, two of them in 1.2 MB tables (A2 §2.2 item 3).
    Carry the selector's stored score instead.
  - Measure nps with bench/ab.py beside each SPRT (A2 O8.2).
- **Cheapest first experiment.** One stats bench plus 20 stats-build
  self-play games, measuring:
  - the mean and SD of the candidate score by depth band;
  - the share of sites with |score| ≥ 24,000, bench against in-game (A2
    O3's test, folded in).

  About 1-2 CPU hours, no GitHub.
- **Kill criterion.** The refactor is kept if bench-identical and nps-neutral
  (it serves SPSA). Each term dies by its own SPRT. If the centred history
  term is H0, do not run idea 42's continuation variant (same mechanism).
- **Originality notes.**
  - Fixed-point LMR is already Fork's own (lmr_table.hpp).
  - Mean preservation is a published practice, described in commit prose
    (survey S1), with no constants involved.
  - Offsets and slopes come from Fork's counters.
- **Effort and dependencies.**
  - About 1 day plus the stats run.
  - **Replaces §5.6 item 10 as planned** (the full refactor, 2-3 days) for
    now. Level 2 is deferred to after Phase 4, to be tested only at LTC if
    ever.
  - Moves ahead of batch 4's LMR items and §5.6 item 8.

### S3. Concave RFP and futility margins from equal marginal error [NOVEL derivation]

- **Mechanism.** Replace RFP's linear margin M·d by a + b·d with a > 0 and
  b < M. It is tighter, relative to d, at depth 1 and looser at depths 3-6.
  The total prune rate stays about unchanged: a re-partition, not a
  loosening.
- **Math / derivation.**
  - Fork measured RFP's error share at M = 80 (audit-1, bootstrap eval;
    DESIGN `RfpMargin` row): 0.31% at d = 1 and 0.03% at d = 6.
  - Reading these as Gaussian tails: z₁ = Φ⁻¹(0.0031) = −2.74, so
    σ₁ ≈ 80/2.74 = 29 cp; z₆ = −3.43, so σ₆ ≈ 480/3.43 = 140 cp. Then
    σ_d ∝ d^0.87 (computed).
  - By M4 under H_crit, the optimal marginal error is equal at all depths.
    Holding depth 1's rate (t = 2.74) gives margin(d) = 2.74·σ_d:
    **80, 147, 209, 269, 326, 383 for d = 1-6, against today's 80-480**.
    A two-parameter fit is about **20 + 61·d** (81 … 386).
  - The same arithmetic explains RfpMargin 40's loss. At d = 1, z falls to
    40/29 = 1.37, an error rate of about 8.5%: ×27 at the most numerous
    depth. At d = 6, 240/140 = 1.71, only 4.4%. A uniform loosening
    concentrates its damage at shallow depth.
  - Rising RFP's −25 cp is 31% of the margin at d = 1 and 5% at d = 6 (A2
    §2.2): the same shape error.
  - **Corollary:** RFP's depth cap of 6 is conservative under H_crit, since
    the error at d = 6 is ten times below d = 1. The equal-error optimum
    extends RFP to depth 7-8.
  - Futility (100 + 70·d) already has an offset form. The same measurement
    decides whether its slope is too steep.
- **Theory and literature.**
  - Buro's ProbCut model: deep ≈ a·shallow + b + ε, with margins as
    quantiles of ε (Buro 1995; Jiang and Buro 2003).
  - Heinz's futility and razoring scaling arguments (Heinz 1998, "Extended
    futility pruning", ICCA J 21(2); Heinz 2000, *Scalable Search in
    Computer Chess*): margins as a function of remaining depth. Exact
    content UNVERIFIED.
  - The equal-error condition (M4) is my derivation.
- **Why Fork.**
  - Every eval-gated loosening lost. Every one was one-sided (A2 §3.1),
    and none changed the *shape*.
  - The margins are bootstrap-era (A2 §1.4).
  - A2's O4 asks for exactly this calibration. This proposal gives it a
    criterion and a shape.
- **Prediction.**
  - Re-measured on S512ppr2 (the same audit-1 RFP-off tool), the error at
    d = 6 is still at least 3× below d = 1 at M = 80. **Refuted if** the
    ratio is under 1.5×: then the linear margin is already near
    equal-error.
  - The concave RFP (fit refreshed on S512ppr2's σ_d), with bench nodes
    within −2% to −6% of today, passes STC [0, 3] at +2 to +5.
  - **Refuted if** H0 at both ladder shapes. That also refutes H_crit for
    RFP; then fit C(d) ∝ h^d from the result.
- **Speed cost; data / compute.**
  - Zero nps.
  - One local measurement, about 2-3 CPU hours on the bench plus 300
    evolve positions, as in audit-1.
  - Ladder: 2 shapes (the equal-error fit, and the fit at 0.7× the error
    level) at ≤ 2 stages each, then an SPRT.
- **Cheapest first experiment.** Re-run the audit-1 RFP fail-low
  measurement on S512ppr2 with the TT-refined `prune_eval` (what RFP
  actually uses), at d = 1-8, recording the error share near the threshold
  (z within ±0.25), not the tail average.
- **Kill criterion.** Error-ratio < 1.5× (no shape change indicated), or H0
  at both ladder values.
- **Originality notes.** The constants come from Fork's own measurement.
  "Offset plus slope" is the generic form; still, the constant screen runs
  before the commit.
- **Effort and dependencies.**
  - Half a day plus the measurement.
  - It precedes item 12's SPSA and seeds it: tune a and b, not M.
  - It replaces the SPSA's "RfpMargin 40 among the candidates" idea, which
    this analysis predicts is wrong.

### S4. Equal-marginal-error calibration of all selectivity [NOVEL]

- **Mechanism.** One stats build that, on a 1/N sample of decisions near
  each heuristic's threshold, also runs the unpruned search and records
  whether the decision was wrong. The decisions:
  - RFP or futility pruned but the full search does not fail high (or low);
  - LMP-skipped quiets that would cut;
  - NMP cut but the real search fails low;
  - an LMR reduced search fails low where the full depth would beat alpha
    (the **LMR miss rate**);
  - SEE-pruned moves that would raise alpha.

  The output is a table of marginal error rates by heuristic × depth (×
  move number for LMR).
- **Math.**
  - M4: at the optimum, every cell has the same rate under H_crit, or the
    rate ∝ (g/h)^d otherwise.
  - Cells far above the common level are over-aggressive and far below are
    over-conservative. A re-partition that moves prune volume between cells
    at constant total nodes gains accuracy at no speed cost.
  - Size of the prize: if the cells' log-error rates spread by a factor of
    10 (RFP alone spans 10× over d = 1-6), equalising at constant nodes
    cuts the error-weighted cost by roughly the spread's convexity. That
    is plausibly 10-30% of the accuracy cost term.
  - Fork's pruning block was worth +439 STC / +555 LTC in total (A2 §2.1),
    so a few Elo is a conservative order of magnitude. The figure is
    UNVERIFIED.
- **Theory and literature.**
  - M4.
  - Buro's per-depth regression (1995) is the single-heuristic precedent.
  - Fork's own SE precision rule and LMP 1% rule are the in-house
    precedents, and both passed (A2 §6.5).
- **Why Fork.**
  - Fork's best pre-SPRT predictors measured mechanisms (A2 §6.5). Its
    worst used an end-to-end, baseline-biased proxy (A2 §6.1).
  - S4 is a mechanism measurement for *all* selectivity at once.
  - It also gives the SPSA (item 12) principled starting points and
    ranges, and a refit after every net promotion (bench moves with the
    net: A2 §3.3).
- **Prediction.**
  - The measured rates span more than 5× across heuristics at equal depth.
    Concretely, I expect LMR's miss rate at late move numbers to sit
    *below* RFP's at d = 1, i.e. LMR is under-reduced relative to RFP.
    This is consistent with "LMR under-informed, not under-reduced" (A2
    §3.1) only if the miss rate is uniform across history buckets.
    **Refuted if** all cells are within 2× of each other: then the margins
    are already balanced and SPSA alone suffices.
- **Speed cost; data / compute.**
  - Measurement only.
  - Local CPU, 3-6 hours at low priority beside datagen. The verification
    searches dominate; sample 1/200 of threshold-near decisions.
- **Cheapest first experiment.** RFP and LMR only, which is S3's
  measurement plus an LMR miss-rate counter, on 300 evolve positions at
  depth 14.
- **Kill criterion.** Rates within 2×, or re-partition SPRTs H0 twice: then
  drop the principle for Fork and leave the values to SPSA.
- **Originality notes.** Measurement tooling only. No constants copied.
- **Effort and dependencies.**
  - 2-3 days of tooling and CPU.
  - Feeds S3, S5 (history skip, cut-node amount), S7 and item 12.
  - Must not reuse the label-and-sweep proxy (A2 §6.1).

### S5. Batch-4 triage: predictions per item, a screen, reorder and demotions

- **Mechanism.** Before any ladder, run the bench with each switch on at
  its placeholder: node change at fixed depth, plus nps with bench/ab.py
  (minutes each). Price each item with M3 as
  R·log2(N_off/N_on)·(1 − ρ_class), with ρ about 0.4 for
  verified or deferred mechanisms and about 1.3 for static-evidence prunes.
  Send to GitHub only the items with a positive predicted value or an
  accuracy-buying mechanism.
- **Math: predictions per item.**
  - P(H1) uses A3's power table for [0, 3] with a 13-stage cap: P(H1) is
    0.05 at +1.8 Elo true, 0.21 at +3.0, 0.50 at +4.2 and 0.89 at +6.0.
  - "E" is my point estimate at STC, ± a belief SD.

| Item (batch-4 switch) | Mechanism class | E (STC) | P(H1 STC [0, 3]) | LTC view | Recommendation |
|---|---|---|---|---|---|
| Cut-node LMR (`use_cut_node_lmr`) | rate change at nodes whose late moves rarely matter (M2: at a true cut node only the refutation matters) | +3 ± 3 whole ply; +3.5 ± 2.5 fractional (S2) | 0.28 | ≥ STC (rate change, M1) | **first**, after S2, fractional amount by ladder (½ and 1 ply) |
| Upcoming repetition (`use_cycle_draw`) | exactness (earlier draw scores, cheap cutoffs) | +1.5 ± 2 | 0.10 on [0, 3] | larger at TCEC: long games, no draw adjudication before 6 pieces | test on **[−3, 0]** as a correctness change (B-1's precedent); see the notes below |
| PV-trace LMR (`use_pv_trace_lmr`) | relief on critical lines; LTC-sensitive per the list | +1 ± 2 | 0.08 | +2 ± 2 | LTC only (already on the list); fractional amount |
| Double extension (`use_double_extension`) | buys accuracy with nodes; precision rises with depth | −2 ± 3 | 0.02 | +1 ± 3 | LTC only, after S7's margin shape; node guard (S7) |
| Pawn-structure history (`use_structure_history`) | ordering information (search-invisible structure) at a 768 KB cost | +0.5 ± 2.5 | 0.08 | ≈ STC | **gate:** SPRT only if the mean cutoff index improves ≥ 1.5% relative (the metric that predicted 3 of 3) and nps ≥ −1% on a v3 build |
| Quiet history pruning (`use_history_skip`) | static evidence plus stale history | −1 ± 3 | 0.07 | ≈ | after S8 and S2's in-game distribution; threshold from S4's error table |
| Razoring (`use_horizon_drop`) | static gate, QS-verified, but **+1.7% nodes at its placeholders** | 0 ± 1.5 | 0.03 | ≈ | demote: SPSA dimension or idle filler |
| Bad-capture futility (`use_bad_capture_stop`) | static gate on a tiny move class already filtered by SEE pruning (−100·d) and node futility | 0 ± 1 | 0.01 | ≈ | demote (overlap) |
| Malus balance (`use_malus_scale`) | re-centring of history (S8 math), not new information | 0 ± 2 | 0.05 | ≈ | **make it an SPSA parameter** (ideas.md 28's own plan), no SPRT |

  - Expected H1 count over the nine: about 0.9. Expected Elo adopted:
    about 3-4 at STC.
  - The cost, by A3 §2.6's estimate: about 140 stages, about 43 h.
  - **Running only the first four or five, with A3's stage-2 futility stop,
    keeps about 85% of the expected Elo for about 45% of the stages.**
- **Theory and literature.**
  - Overlap and marginal sets. A heuristic added after others prunes only
    their survivors. Those nodes lie near the others' decision boundaries,
    so its marginal error per prune exceeds its stand-alone rate. This is
    the mechanism behind ProbCut's −5.3 next to NMP and multi-cut (A2 §2.2)
    and bad-capture futility's expected null.
  - Knuth-Moore node types for cut-node LMR (M2).
  - Van Kervinck's cycle detection for the upcoming-repetition item (KB
    §3.29). Its paper reports +9 at 40 s + 2 s and a tree change under
    0.4% (KB).
- **Why Fork.**
  - Upcoming repetition at TCEC versus SPRTs. UHO openings are unbalanced,
    so SPRT games repeat less than TCEC games, which start from
    balanced-ish books and are never win-adjudicated. A repetition feature
    is therefore *undervalued* by Fork's SPRT conditions. Testing it on
    non-regression bounds is the right instrument for a correctness change.
  - Two implementation notes, read from tier2/batch4's
    `Position::has_return_move`:
    1. It walks the history up to the halfmove window, so its cost grows in
       long shuffling endgames, exactly TCEC's long games. Measure nps on
       an endgame-heavy position set, not only the bench.
    2. It inherits Fork's "one earlier occurrence is a draw, also before
       the root" convention. KB §3.29 records a published correction for
       exactly that case, so idea 31 and this item interact. Decide idea
       31 first, or count a pre-root occurrence only if it occurred twice.
- **Prediction.**
  - At most two of the nine pass STC [0, 3]. Cut-node LMR is the likeliest.
  - Razoring's and bad-capture futility's bench node changes are under 3%,
    and their predicted value is ≤ 0.
  - **Refuted if** three or more of the five items I rate lowest pass.
- **Speed cost; data / compute.** The screen is 9 bench runs plus 9 short
  A/B runs (about 2 hours local). It saves about 20 GitHub-hours.
- **Cheapest first experiment.** The screen itself.
- **Kill criterion (for this triage).** If the screen's predicted sign
  disagrees with the SPRT sign on the first three items run, abandon the
  screen and run batch 4 as planned.
- **Originality notes.** The placeholders stay placeholders. This adds no
  constants.
- **Effort and dependencies.** Reorders §5.6 item 5. Cut-node and PV-trace
  wait for S2. History skip waits for S8 and S4.

### S6. Node types beyond LMR: gate NMP and IIR by expected type; post-LMR re-search depth

- **Mechanism.** Use batch 4's `expected_cut` (already built) for three
  more decisions:
  - **(a) NMP only at expected cut nodes** (and not at expected all nodes);
  - **(b) IIR gated by node type:** a ladder of {every type (today), cut
    and PV only, cut only with a larger step once S2 allows fractions};
  - **(c) re-search depth after LMR:** when the reduced search beats alpha
    by a wide margin, re-search one unit deeper; when it barely beats it,
    re-search one unit shallower.
- **Math / derivation.**
  - (a) At a true all node, the null search fails high only if the
    prediction was wrong. Its probes there are mostly wasted. Each probe
    costs about a d/2-depth subtree, g^(d/2) relative to the node's g^d.
    At d = 8 that is 1.66^4/1.66^8 ≈ 13% of the node, and at d = 12 about
    5%.
  - If NMP probes at expected all nodes succeed a fraction p of the time,
    the gate saves (1 − p)·13% of those nodes at d = 8 and loses p of the
    cuts. It is positive when p is small. **Measure p with the stats
    build** (`null_cuts` split by `expected_cut`).
  - (b) M2: ordering affects only cut and PV nodes. IIR is justified by
    poor ordering ("no TT move"), so at all nodes it only removes depth.
    On the other side, it also cheapens all nodes. This is a re-partition
    question with an unknown sign at all nodes, so it gets a ladder, not an
    SPRT of one form. The constant screen records cut-node-only IIR forms
    elsewhere (DESIGN `NoMoveReduceMinDepth` row), consistent with the
    theory.
  - (c) The reduced search's result is information. Its margin above alpha
    estimates how decisive the move is. It is low-ρ selectivity (M3).
- **Theory and literature.**
  - Knuth and Moore 1975 (node types); Marsland and Popowich 1985 (the
    PV/CUT/ALL naming, UNVERIFIED citation).
  - Survey S2 §4.5-4.6 records NMP-at-cut-nodes and re-search-depth
    results in other engines (+2 to +6).
- **Why Fork.**
  - Fork has no expected types yet (A2 §1.3). Batch 4 builds them for LMR
    only.
  - IIR's +21/+26 says Fork's selectivity pays where information is
    deferred.
  - Fork's NMP runs at every non-PV node with eval ≥ β.
- **Prediction.**
  - (a) passes [0, 3] at +2 to +4.
  - (b) the cut-and-PV form beats every-type by +1 to +4. **Refuted if**
    both gated forms are H0 against today's IIR.
  - (c) +2 to +5.
- **Speed cost; data / compute.**
  - Zero nps for (a) and (b) (a flag read).
  - (c) one comparison per re-search.
  - Stats counters first (minutes), then a ladder plus SPRT each.
- **Cheapest first experiment.** One stats bench: NMP success rate and IIR
  firing counts split by `expected_cut`. If NMP success at expected all
  nodes exceeds 30%, drop (a).
- **Kill criterion.** As each prediction's refutation.
- **Originality notes.** Generic CPW concepts. The margin for (c) comes
  from S4's LMR miss-rate data, not from other engines.
- **Effort and dependencies.** 1-2 days. After batch 4's node types land.
  (c) after S2.

### S7. Depth-concave singular margin, extension parameters tuned only at LTC, explosion guard in node terms

- **Mechanism.**
  1. Re-measure SE precision at depths 12-20, from deeper searches with the
     same tool (`tools/singular_measure.py`). Fit a concave margin
     (a + b·d, or capped) in place of 6·d.
  2. Choose the double-extension margin as a precision quantile of the
     same residual (precision ≥ a higher bar).
  3. Guard explosions by a **node-share** rule: double extensions allowed
     on a line only while the line's extension count stays below a
     fraction of the root depth. This is Fork's own form; the fraction
     comes from a ladder.
  4. Tune SE and extension parameters **only at LTC** in item 12.
- **Math / derivation.**
  - Fork's SE precision rises with depth: 0.91 at d6, 0.97-0.98 at d7-12
    (A2 §5). Under the equal-precision rule that picked 6·d, the margin per
    ply needed for 90% precision falls with depth. At d = 20 today's bar is
    120 cp below the TT score, so SE almost never fires near the root of
    deep searches, exactly the nodes that decide TCEC games.
  - Cost of double extensions, from SE's numbers: SE adds 30.6% nodes when
    22% of tests extend (DESIGN singular row). If a fraction q of singular
    extensions become double, the extra nodes are about q × 0.306 × g:
    q = 0.1 gives +5% (−7.4 Elo-equivalent at STC), q = 0.2 gives +10%
    (−14.5), q = 0.33 gives +16% (−23) (computed).
  - The benefit must exceed that. It rises with depth (precision), so
    expect STC ≤ 0 and LTC ≥ 0. That is the same sign pattern as SF's
    extension-heavy tunes (survey S1 §4: failed STC, passed VLTC).
- **Theory and literature.**
  - Anantharaman, Campbell and Hsu, "Singular extensions: adding
    selectivity to brute-force searching", Artificial Intelligence 43
    (1990). KB §3.21 covers caps and explosions.
- **Why Fork.**
  - Fork's SE constants were measured on S-512, about 200 Elo of eval ago
    (A2 §1.4).
  - The LTC-sensitive list already routes extensions to LTC (A2 §5).
  - SE and multi-cut have no LTC confirmation.
- **Prediction.**
  - At d = 16-20, 90% precision is reached at ≤ 4 cp per ply. **Refuted
    if** ≥ 6.
  - The concave SE margin passes LTC [0, 3] at +1 to +4 and is neutral at
    STC.
- **Speed cost; data / compute.**
  - Zero nps.
  - The measurement needs deeper searches: local CPU, about 4-6 hours.
  - LTC: ≤ 6 stages per test.
- **Cheapest first experiment.** The deeper precision measurement only, on
  the existing tool with depth-20 searches of 80 evolve positions.
- **Kill criterion.** Precision at depth does not rise above d7-12's, or
  LTC H0.
- **Originality notes.** Margins from Fork's measurement. The cap's form
  (a fraction of root depth) is a ladder value. Do not adopt the absolute
  cap of 6 that matched another engine in the batch-4 screen (DESIGN
  `DoubleExtensionsMax` row).
- **Effort and dependencies.** About 1 day plus measurement and LTC.
  Replaces the batch-4 double-extension ladder.

### S8. History hygiene: per-search scaling, and the malus as a re-centring

- **Mechanism.**
  - (a) At each `go`, scale every history entry by s ∈ {1 (today), 3/4,
    1/2} (a ladder). The scan is about 1.2 M int16 values, under a
    millisecond.
  - (b) Treat the malus ratio as a **centring parameter** for SPSA, not an
    SPRT feature.
- **Math / derivation.**
  - The gravity update v ← v + b − v·|b|/H is an exponential moving
    average with time constant H/b updates.
  - With Fork's bonus 12.5·d² capped at 1,250 (quiet_history.hpp), that is
    about 830 updates at d = 1, 89 at d = 3, 22 at d = 6 and 8 at d ≥ 10.
    Entries touched by deep cutoffs refresh fast. Entries touched only at
    shallow depth persist across moves almost unchanged.
  - Fork never decays between moves (session.cpp clears only at
    ucinewgame; A2 §1.1).
  - For a move that cuts with probability p (bonus b) and otherwise takes
    malus k·b, the equilibrium is **v* = H·(p − (1−p)k)/(p + (1−p)k)**.
    The zero crossing sits at p₀ = k/(1+k): 0.5 at k = 1 and 0.43 at k =
    0.75.
  - So k shifts *where zero is*. For pure ordering it is close to a
    monotone transform and matters little. For anything thresholded on the
    sign or level of history (LMR history, history pruning) it matters a
    lot. That is why it belongs in SPSA together with those thresholds.
- **Theory and literature.**
  - Schaeffer 1989 (the history heuristic and its ageing).
  - The gravity form is cited in ORIGINALITY.md.
  - KB T9 and T55.
- **Why Fork.** A2 O3's persistence hypothesis. Batch 4's history-gated
  items (HistorySkip, the malus balance) depend on in-game distributions
  that the bench (cleared per position) never shows.
- **Prediction.**
  - (a) is neutral to slightly positive for ordering alone: 0 ± 2,
    P(H1) ≈ 0.07. It matters as a prerequisite: with s = 1/2, the share of
    in-game LMR sites with |score| ≥ 24,000 falls to within 2× of the
    bench's.
  - **Refuted if** the in-game distribution already matches the bench
    (A2 O3's kill). Then drop (a).
- **Speed cost; data / compute.** Zero nps. The stats games are shared with
  S2's experiment.
- **Cheapest first experiment.** The S2 stats games with s ∈ {1, 1/2}.
- **Kill criterion.** In-game and bench distributions match at s = 1.
- **Originality notes.** Generic. Values come from a ladder.
- **Effort and dependencies.** Half a day. Precedes history skip and any
  rerun of LMR history.

### S9. Time-control scaling classifier for routing tests [NOVEL for Fork]

- **Mechanism.** For each candidate, run the bench (or the evolve set) at
  two fixed depths, D₁ = 12 and D₂ = 16, with the switch off and on. Fit
  log2(N_off/N_on) = c + Δ·D: c is the constant-factor saving, Δ the rate
  change per ply (M1).
- **Math.**
  - Speed-side Elo at a control = R(TC)·(c + Δ·D(TC)), with D about 15 at
    STC, 18 at LTC and 25 or more at TCEC.
  - Example: c = 0.05, Δ = 0.005 gives 106·0.125 = 13.3 Elo at STC,
    95·0.14 = 13.3 at LTC and about 85·0.175 = 14.9 at TCEC. With Δ = 0.01
    instead: 21, 22 and 25.5 Elo respectively.
  - A feature with Δ > 0 should get LTC routing (or at least an LTC check
    of an STC H0).
  - A feature with Δ ≈ 0 whose value is accuracy at a fixed horizon (check
    relief, LMR on evasions, SEE in qsearch: "horizon patches") is expected
    to *lose* value with depth, because the deeper search finds what the
    patch found. Its removal test belongs at LTC. Check relief's shrinking
    value (+11.3 to about +3; A2 §2.1) is consistent with this, though
    confounded by the net change.
- **Theory and literature.**
  - Heinz's diminishing-returns and scalable-search work (Heinz 2000;
    "DarkThought goes deep", ICCA J 21(4), 1998; content UNVERIFIED here).
  - KB §1 lesson 3.
- **Why Fork.**
  - The testing policy keeps LTC for an LTC-sensitive list (BRIEF rule 6).
  - S9 makes the list measurable rather than declared.
  - The removal round (item 11) is about 80 GitHub-hours at low power (A3
    §2.6). The classifier says which removals need LTC and which can be
    skipped.
- **Prediction.**
  - IIR has Δ > 0: its saving at depth 16 exceeds its saving at depth 12.
    **Refuted if** the saving is flat or falls; then IIR's LTC gain was
    accuracy, not rate.
  - Cut-node LMR shows Δ > 0. Razoring and bad-capture futility show
    Δ ≈ 0.
- **Speed cost; data / compute.** Two bench runs per feature, minutes. No
  GitHub.
- **Cheapest first experiment.** IIR off/on at depths 12 and 16.
- **Kill criterion.** If Δ estimates are noisier than ±0.005 at the bench's
  46 positions, use the 300 evolve positions. If still noisy, drop.
- **Originality notes.** Tooling only.
- **Effort and dependencies.** Half a day. It informs item 11's design and
  the LTC list.

---

## 4. Critique of the current plan (search and time management)

1. **Move node-share TM (S1) from Phase 5 into Phase 4, before item 12.**
   - It has the best expected Elo per GitHub stage in my domain: +8 to +12
     at STC for about 6-12 stages, against about 0.1 Elo per stage for
     batch 4's tail (S5).
   - Every later LTC test, the SPSA retune and the final gauntlet should
     run with the TM that TCEC will see.
   - This is a plan change for the owner (DESIGN §5, Phase 5 outline). The
     rest of Phase 5 stays: base allocation at a TCEC-shaped control,
     safety, tablebase latency.
2. **Item 10, fractional depth: shrink it to level 1 (S2) and move it
   ahead of batch 4's LMR items and item 8.**
   - Level 1 delivers what idea 43 is for: smooth LMR terms and smooth SPSA
     parameters. It costs about 1 day against 2-3, touches no TT or
     threshold semantics, and has the better published record (KB §3.35).
   - Level 2 is deferred: if ever, as an LTC-only test after Phase 4.
3. **Item 5, batch 4: reorder and shrink (S5).**
   - Order: cut-node LMR (fractional), then upcoming repetition on
     [−3, 0], then structure history (only if its cutoff-index gate
     passes), with PV-trace LMR and double extensions at LTC (after S7).
   - Demote to SPSA or filler: razoring (it adds nodes at its
     placeholders), bad-capture futility (overlap) and the malus balance
     (a centring parameter).
   - History skip waits for S8 and S4.
   - Add A3's stage-2 futility stop to every search SPRT.
4. **Item 8, continuation histories in LMR (idea 42).**
   - Run it only after S2's centred term passes. It uses the same
     mechanism, so if the centred butterfly-plus-pair term fails, the
     continuation variant will too.
   - Its planned measurement is "the same way as the term was"
     (ideas.md 42): the label-and-sweep proxy. That proxy cannot see node
     savings, and it favours "off" by construction (A2 §6.1: ρ ≈ −0.3
     against SPRTs). Replace it with S4's LMR miss-rate surface.
5. **Item 12, SPSA retune: shape first, then tune, split by scaling
   class.**
   - (a) RFP and futility as a + b·d (S3), so SPSA tunes shapes.
   - (b) The cp margins at STC.
   - (c) The extension, SE and NMP-depth parameters at LTC only (S7; survey
     S1 7.2.6).
   - (d) The LMR parameters only after S2, so they are smooth.
   - (e) The malus ratio (S8) and HorizonDrop/BadCaptureStop, if kept, as
     extra SPSA dimensions initialised at "off-equivalent".
   - An early SPSA pass on the cp margins (survey S2 §4.1) is compatible
     with this: S3's shapes first, then the pass.
6. **Item 11, the full re-validation.**
   - Classify each feature with S9.
   - Rate-class features (LMR, NMP, IIR, LMP) are removal-tested at STC,
     where their value is smallest, so a pass there is conservative.
   - Horizon patches (check relief, LMR on evasions, SEE in qsearch,
     aspiration) are tested at LTC, where their value is smallest.
   - Use fixed-length estimates, not SPRTs to a verdict, per A3 §2.6. A
     neutral feature is "confirmed removable" only 5% of the time at the
     current design.
7. **Rejected ideas: no retests, but the reasons matter for new work.**
   - The owner's no-retest rule for ProbCut, rising RFP and threat ordering
     stands.
   - But the mechanism (one-sided loosening, overlap with existing fail-high
     prunes, whole-ply steps) says that **a symmetric "improving"
     re-partition** (A2 O5) and **NMP at expected cut nodes** (S6) are
     different ideas, not retests.
8. **Idea 23's long run (item 13).** Its fitness funnel is the same
   baseline-biased proxy. By M3, that proxy cannot see the speed side of
   any selectivity change: it evaluates at fixed node budgets against
   labels from the "off" engine. Do not start the long run before the proxy
   is repaired (A2 O8.3) or replaced by S4-style mechanism measurements.
9. **The re-validation queue (B-3, root fail-high fix).** Fold the root
   fail-high questions into S1's resolution-aware stop. It is the time
   decision that idea 29 itself recommends ("the cleaner answer may be a
   time decision"). Do not spend filler stages on the move-decision
   variants.
10. **Constants to measure, not reason.** Two Fork constants have
    depth-scaling consequences at TCEC that no current test sees:
    - the NMP depth d/2 − 1: a reduction of 16 plies at d = 30;
    - the singular margin 6·d: 180 cp at d = 30.

    Both should be in the LTC-only SPSA group.

---

## 5. What I could not verify

- **Iteration growth.** g = 1.66 was measured at depths 8-14 on the
  bootstrap with no tier 2. Its value on S512ppr2 at depths 15-30 is
  unknown, and every depth and TCEC figure in M1 and S9 depends on it.
- **The RFP error shares and σ_d.** Both come from the bootstrap-era
  audit-1 measurement and a Gaussian-tail reading of tail averages. Real
  tails are fatter, and marginal rates differ from averages. S3's
  placeholder (20 + 61·d) must be re-derived on S512ppr2 before use.
- **H_crit.** "Critical nodes per depth layer roughly constant" is a
  hypothesis. S3's SPRT is its test.
- **The M3 decomposition.** It uses bench node counts at fixed depth with
  fresh state as the speed side, and no nps. In-game node savings and the
  nps costs (threat buckets, LMR history, ProbCut) were never measured.
- **S1's ρ_s² range (0.10-0.15).** It is assumed, not measured. S1's first
  experiment measures it. The CV ≈ 1 of move difficulty is also an
  assumption.
- **Batch-4 probabilities.** They combine my belief distributions with
  A3's simulated power table. They are not Fork measurements.
- **Literature details.** Page numbers and exact claims for Pearl 1983,
  Nau 1982, Beal 1980, Heinz 1998/2000 and Marsland and Popowich 1985 are
  from memory: UNVERIFIED. Knuth and Moore 1975, Buro 1995 and
  Anantharaman et al. 1990 are cited as the KB and CPW cite them.
- **`has_return_move`'s cost** in long endgames: not measured. My concern
  rests on reading the code (a loop over the halfmove window).
- **The candidate-population mean** of the ordering score at LMR sites
  (S2's central premise). It is inferred from the selector ordering by the
  same score, not measured.


---

# B7. Tuning and optimization (O)

## B-tuning: SPSA design, alternatives, the constant ladder and idea 23 (think tank, Phase B, prefix O)

**Summary.** Fork has never tuned a search constant against games. Every
eval-dependent margin is still a bootstrap-era value set by reasoning or by a
safety rule (A2 §1.4). The 37-entry parameter table and the `FORK_TUNE` build
exist, but there is no SPSA driver: the shards build release binaries, and
`sprt.yml` passes options only per match, not per game pair. I derived SPSA's
arithmetic for Fork's measured noise (pair-score sd 0.21 at STC, which is
146 Elo per game pair) and checked it by simulation
(`tank/b/spsa_sim.py`, `spsa_sim2.py`, `ladder_sim.py`; the model is
separable quadratic, with a 3x steeper side and uncertain curvature).

Main results:
1. **One game pair informs every parameter at once.** SPSA's cost per
   parameter is therefore about 1,000-1,500 STC games for 60-80% recovery of
   that parameter's misplaced Elo. A 2-3-value ladder spends 9,600 games on
   one constant and does no better.
2. **The perturbation c should cost about 1-3 Elo per side at the optimum.**
   Fork's table steps (a twentieth of the range) are probably too small for
   some parameters and are not calibrated to anything.
3. **Set the gain from a stationary-loss budget:** a/c² = ε/(1.92·p) in
   pair-score units. Clamp each update to 0.5·c. Batching 800 pairs per
   GitHub stage is then harmless.
4. **Every parameter with nothing to gain costs about 0.17 Elo** at 20k games.

**Recommendation.** Run an **early SPSA of the 8 eval-dependent margins now,
before batch 4**: 20k STC games, about 4 GitHub hours, plus a validation SPRT
and a short LTC guard. Expect **+4 to +12 STC (central +7) and +3 to +10
LTC**. That is below the survey's +15-35: the survey's numbers are
SPRT-selected, come from other engines' larger parameter sets, and my model
recovers about 65-80% of what is there. A final pass split by scaling class
follows later: shallow margins at STC, depth-scaling constants at LTC, time
management never at a base/increment ratio of 100. Two NOVEL tools:
- an **antithetic screen** for features that have a continuous strength
  (+c against −c gives up to 4x the signal of on against off, so about 16x
  fewer games in the ideal case);
- **perturbation sizes calibrated from FORK_SEARCH_STATS firing rates**.

**Idea 23** should not run on its current label proxy, which has no
demonstrated predictive validity. If it runs at all, it should be a capped
pilot after idea 43, scored by antithetic fixed-node games. Expect 0 to
+4 Elo.

## Ranked proposals

| ID | Title | Expected Elo at LTC (range) | Effort (days) | Confidence | NOVEL? |
|---|---|---|---|---|---|
| O1 | Early SPSA of the 8 eval-dependent margins before batch 4 | +3 to +10 (STC +4 to +12) | 1-2 to build O4, then about 9 GitHub-hours | medium | no |
| O10 | The final retune (§5.6 item 12) rescoped: groups, budgets, order around the removal round | +2 to +6 beyond O1 | about 2 GitHub-days | medium | no |
| O5 | Tune by scaling class: shallow margins at STC, depth-scaling at LTC, time management at a TCEC-shaped control, S never in SPSA | +1 to +4 (over tuning everything at STC) | 0 (a plan rule) | low-medium | no |
| O3 | Perturbation sizes calibrated from FORK_SEARCH_STATS firing rates | +1 to +4 (raises O1 and O10) | 0.5 local | medium-low | **NOVEL** |
| O7 | Antithetic screening for strength-parameterised features | indirect: +1 to +3 through triage; saves 30-60% of screen stages | 0.5 | medium | **NOVEL** |
| O8 | Replace the 3-value ladder with tune-then-test (mini-SPSA) or a 1-stage sanity ladder | +0 to +2; saves about 15-25 stages in batch 4 | 0.5 | medium | no |
| O9 | Idea 23 with a repaired fitness (antithetic fixed-node games), capped, after idea 43; otherwise drop it | 0 to +4 | 3-5 (with tokens) | low | partly |
| O2 | SPSA design rules for Fork's noise (c, a, A, clamps, batch, which parameters) | enabler | 0 (rules) | high (math), medium (model) | no |
| O4 | The GitHub SPSA driver (FORK_TUNE shards, per-pair micro-matches, gradient merge, jobctl driver) | enabler | 1-2 | high | no |
| O6 | Validation protocol: STC [0, 5], an LTC 3-stage sign guard, disjoint openings, a second-book check | protective (avoids adopting a 0 to −3 tune) | 0 | high | no |

Conventions: **[derived]** = my arithmetic; **[sim]** = my simulation (model
stated with each table); **[read]** = from a file; UNVERIFIED where unsure.
nElo↔Elo: STC Elo ≈ 0.6·nElo, LTC ≈ 0.55·nElo (A3 §2.5). GitHub throughput:
an STC stage is 1,600 games in about 18.5 min, so about **5,200 STC games per
hour**. An LTC stage is 1,664 games in about 75 min (UNVERIFIED, A3), so about
1,330 LTC games per hour.

---

## 0. The arithmetic everything below uses [derived]

**Noise.** A game pair (same opening, colours reversed) between θ⁺ = θ + cΔ
and θ⁻ = θ − cΔ has a mean pair score s̄ with sd 0.21 at STC on the current
nets (A3 §2.5: 0.208-0.214; LTC 0.193-0.198). The logistic slope at equality
is dE/dElo = ln10/1600 = 0.0014391 per Elo, so one pair measures the Elo
difference D = Elo(θ⁺) − Elo(θ⁻) with **sd σ = 0.21/0.0014391 = 146 Elo**
(136 at LTC).

**Landscape.** For parameter i, let w_i be its 1-Elo half-width: the distance
from its optimum at which the engine loses 1 Elo. Write x_i = θ_i − θ*_i, so
the loss is (x_i/w_i)² and c_i = γ_i·w_i. With Rademacher Δ,
D = Σ_l Δ_l·h_l, where h_l = f_l(x_l + c_l) − f_l(x_l − c_l) is the central
difference (−4x_l·c_l/w_l² for a symmetric quadratic). The SPSA estimate
ĝ_i = y·Δ_i/(2c_i) carries:
- noise variance σ²/(4c_i²) from the game, plus
- cross-talk Σ_{l≠i} h_l²/(4c_i²) from the other parameters.

Cross-talk is small: 20 parameters at about 4 Elo of h each add 320 Elo²
against σ² = 21,300. **So p parameters cost almost nothing extra per pair.**
That is SPSA's whole advantage (Spall 1992, KB research.md "Spall (1992)").

**Update and stationary loss.** Update with x_i ← x_i + a_i·ĝ_i and write
a_i = α·c_i². Then:
- the mean dynamics contract x_i by r_i = 2α·γ_i² per pair;
- the noise per step is a_i·σ/(2c_i);
- the stationary variance is (a_i σ/2c_i)²/(2r_i) = (σ²/16)·α·w_i².

So the **stationary loss per parameter is σ²/16 · α = 1,332·α Elo at STC
(1,156 at LTC), independent of w_i and of γ_i.** Two consequences follow:

1. **Set α from a total loss budget ε:** α = ε/(1,332·p). In the driver's
   natural units (pair score minus 0.5) this is
   **R = a/c² = ε/(1.92·p)** at STC and ε/(1.66·p) at LTC.
2. **Convergence speed grows with γ²** (r = 2αγ²), while the stationary
   loss does not depend on γ. So a large c is free in a symmetric quadratic
   world. It is bounded only by non-quadratic shape (c-smoothing shifts the
   fixed point toward the gentle side: for a 3x steeper side by
   c(√3 − 1)/(√3 + 1) = 0.27c) and by legal ranges.

**What the simulation says** [sim]. Base case: p = 16, T = 15 Elo of total
recoverable misplacement (heavy-tailed across parameters), γ median 1 with
log-sd 0.6 (we do not know w), a 3x steeper side on a random side, ε = 0.5,
Spall gains a_k ∝ (k + A)^−0.602 with A = 0.1N, a 0.5c step clamp,
100 pairs per update, the mean of the last 30% of updates, 600 runs per row.

| games | mean gain | p10 | median | P(gain < 0) |
|---|---|---|---|---|
| 5k | +6.1 | +2.8 | +6.2 | 0.005 |
| 10k | +7.9 | +4.8 | +8.2 | 0.003 |
| 20k | +9.5 | +6.7 | +9.9 | 0.000 |
| 40k | +10.8 | +8.6 | +11.2 | 0.002 |
| 80k | +11.6 | +9.8 | +12.0 | 0.002 |

| recoverable T (p = 16, 20k games) | 0 | 3 | 6 | 10 | 15 | 25 |
|---|---|---|---|---|---|---|
| mean gain | −2.5 | −0.1 | +2.4 | +5.5 | +9.5 | +17.5 |
| P(gain < 0) | 1.00 | 0.45 | 0.05 | 0.01 | 0.00 | 0.00 |

| p (T = 15 shared, 20k) | 4 | 8 | 16 | 24 | 32 | 48 |
|---|---|---|---|---|---|---|
| mean gain | +13.3 | +11.8 | +9.5 | +7.7 | +6.3 | +4.0 |

| p (T = p: 1 Elo per parameter, 20k) | 4 | 8 | 16 | 32 |
|---|---|---|---|---|
| mean gain (share of T) | +2.8 (70%) | +5.6 (70%) | +10.3 (64%) | +17.6 (55%) |

| γ0 = c/w (20k) | 0.25 | 0.5 | 1.0 | 1.5 | 2.0 |
|---|---|---|---|---|---|
| asymmetric 3x | +3.3 | +7.0 | **+9.5** | +8.2 | +4.7 (P<0 0.11) |
| symmetric | +2.0 | +5.4 | +10.0 | +12.2 | +13.3 |

| uncertainty of w (log-sd of γ) | 0.0 | 0.3 | 0.6 | 1.0 |
|---|---|---|---|---|
| mean gain (20k, p = 16) | +12.3 | +11.5 | +9.5 | +2.6 (P<0 0.21) |

Readings:
- **Budget.** About 1,250 games per parameter recovers about 60-65% of the
  recoverable Elo. Each doubling adds about 8-10 points of recovery.
- **Joint tuning.** Joint tuning is cheap when every parameter has something
  to recover. Parameters with nothing to gain are pure noise: going from 16
  to 48 parameters at fixed T costs 5.5 Elo, about **0.17 Elo per dead
  parameter** at 20k games.
- **Tuning when nothing is wrong costs about 2.5 Elo** at ε = 0.5. That is
  why the validation SPRT (O6) is mandatory.
- **c too small** (γ = 0.25, roughly a table step on a flat parameter) leaves
  most of the Elo unrecovered. **c too large** on an asymmetric landscape
  costs Elo through smoothing bias.
- **Not knowing w** costs the most of anything here. That is O3's case.
- Two earlier runs **diverged**: ε = 1, γ up to about 5, 800 pairs per update
  with no clamp. Synchronous large batches are dangerous with Spall's large
  early gains (B·r·4.2 > 1 on steep parameters). With ε ≤ 0.5 and a 0.5c
  clamp, any batch from 25 to 1,600 pairs per update gives the same result
  (+9.5 to +9.8).

---

## 1. Proposals

### O1. Early SPSA of the eval-dependent margins, before batch 4

- **Mechanism.** Tune 8 parameters jointly at STC: RfpMargin,
  FutilityOffset, FutilityGrowth, NullSurplusPerPly, AspirationHalfWidth,
  QuietSeeFloor, CaptureSeeFloor and LmpQuietAllowance. Most are in bootstrap
  centipawns. The LMP allowance was measured with butterfly-only ordering,
  before the pair tables cut the mean cutoff index 0.650 → 0.579 (DESIGN.md
  constants table, `FollowWeight` row).
  - Excluded now:
    - LMR (wait for idea 43);
    - the singular and IIR constants (depth-scaling, O5);
    - the history weights (measured on S-512 by the cutoff-index metric,
      which predicted well, A2 §6.5, so little to recover);
    - depth gates (integer steps, mostly flat);
    - time management (O5);
    - LmrCorrectionStrength (no effect).
- **Math.**
  - From §0 at p = 8: 20k games recovers about 79% of T (+11.8 of 15) [sim].
  - The prior on T for these 8 is **6-15 Elo at STC**. Grounds:
    - the margins were never tuned on any evaluator;
    - the net's error shrank by hundreds of Elo of net quality while mean
      |eval| was held constant (A2 §3.2);
    - RfpMargin 40 against 80 measured about −44 ± 22 Elo in the bootstrap
      gauntlet (ideas.md 34). Read through the quadratic model, that means
      w_RFP is of order 6-10 cp, a steep parameter, so misplacements of a few
      w are plausible elsewhere;
    - other engines' first post-net tunes gained +10 to +20 LTC with many
      more parameters (b-survey-opensource §4.1).
  - So the expected gain is **+4 to +12 STC, central +7** (about +12 nElo).
  - GitHub cost: SPSA 20k games ≈ 3.9 h, then a validation SPRT [0, 5]
    (about 4 stages at +12-15 nElo ≈ 1.2 h), then an LTC guard of 3 stages
    (about 3.75 h, UNVERIFIED stage time). **About 9 GitHub-hours in total.**
  - Comparison: under the current policy, batch 4 yields about 0.20 nElo per
    stage, about 0.12 Elo per stage, for about 140 stages (A3 §2.6). That is
    about 0.4 Elo per GitHub-hour. O1 gives about 0.8 Elo per GitHub-hour
    (+7 over about 9 h), about **2x batch 4's yield**, and it improves batch
    4's decisions (below).
- **Theory and literature.** Spall (1992), as in the KB. Kiiski's Stockfish
  method (CPW "Stockfish's Tuning Method", KB research.md: 7-35 variables at
  once, important ones improve while the rest random-walk, "choosing which
  variables to tune matters a lot"). My dead-parameter cost (0.17 Elo each)
  is the quantitative form of that warning. Other engines' records for the
  first tune after a net change: b-survey-opensource §4.1 (Halogen #484 and
  #656, Viridithas #220), as reported there, not re-checked.
- **Why Fork.**
  - A2 §3.1: every loosening on static evidence lost (−3.8, −5.3, −8.7,
    −10.8). A2 §3.1 also notes those were one-sided perturbations of
    bootstrap values. SPSA moves all 8 at once, so it can find a different
    *shape*, such as tighter at depth 1 and looser at depth 6 through the
    offset/growth pair, which one-sided SPRTs cannot.
  - Batch 4 (razoring, quiet history pruning, bad-capture futility) consists
    of substitutes and complements of these margins. On a base that over- or
    under-prunes, a substitute's measured gain includes recovering the base's
    misplacement, and a complement's is depressed. Tuning first makes batch
    4's SPRTs measure the features themselves.
  - Data generation labels with the default engine. A stronger default is a
    better labeller (A1 §2.2: about 0.3 student Elo per labeller Elo,
    low confidence). Shallow margins act the same at datagen's depth 8-10 as
    at STC, so they transfer. Depth-scaling constants would not (O5).
- **Prediction.**
  - The tuned set beats the default by +4 to +12 Elo at STC; it passes
    [0, 5] within 6 stages with about 0.9 probability if the gain is at least
    +9 Elo (O6 table).
  - The LTC guard's 3-stage estimate is above 0 with about 0.95 probability.
  - Shape prediction: the parameters set by reasoning (FutilityOffset,
    FutilityGrowth, NullSurplusPerPly, CaptureSeeFloor) move further, in
    units of c, than the ones set by measurement (RfpMargin, AspirationHalfWidth).
  - LmpQuietAllowance moves down (prunes earlier), because ordering improved
    since it was measured.
  - **Refuted if** the validation SPRT reaches H0, or its 6-stage estimate is
    below +3 nElo. Then the margins were not the problem, and the final pass
    shrinks to the LTC group.
- **Speed cost; compute.** No nps cost: constants only. GitHub only (the PC
  is busy with data generation). The tuning build's variables cost a little
  nps, equally on both sides.
- **Cheapest first experiment.**
  - O4's driver dry-run: 1 stage of SPSA (1,600 games) whose θ updates are
    logged but not applied.
  - Check that each parameter's gradient z-score lies within a plausible
    range (|z| < 3) and that the stage's game rate matches an SPRT stage.
  - Then the full 20k.
- **Kill criterion.** The validation SPRT reaches H0, or its estimate is
  ≤ +3 nElo at its cap. Then keep the defaults and record the trajectory as
  evidence about the landscape.
- **Originality notes.** SPSA is generic (Spall). The gain rules are derived
  here, not copied from any tool's defaults. Every tuned value is a search
  constant: it needs its recorded justification (the SPSA log plus the
  SPRT), and the originality-checker screens the final values before the
  commit (owner, 2026-10-25). A tuned value can land on a famous constant by
  chance, as RfpMargin 80 matched Berserk; that goes to the owner as before.
- **Effort and dependencies.** Needs O4 (1-2 days). It reorders §5.6: a
  first half of item 12 moves before item 5. Item 4 (speed-to-Elo) runs
  first or in between; neither blocks the other. Item 10 (idea 43) does not
  gate it, because no LMR parameter is in the group.

### O2. SPSA design rules for Fork's noise

- **Mechanism.** Concrete settings, all derived in §0:
  1. **Parameters in c-units.** Each parameter gets its own c_i, and
     a_i = R·c_i², so the tuner works in dimensionless x_i/c_i. This is the
     KB pitfall "scale parameters so one perturbation size fits all", made
     exact.
  2. **c_i ≈ w_i** (γ ≈ 1). The perturbation should cost about 1 Elo per side
     on the gentle side, about 3 on the steep side. Go up to γ ≈ 1.5 only if
     the landscape is believed symmetric.
  3. **R from a loss budget.** R_end = ε/(1.92·p) at STC, with ε = 0.5 Elo
     total. For p = 8 that is R_end = 0.033 per unit of pair score; at LTC,
     ε/(1.66·p).
  4. **Spall's decay:** a_k = R_end·c²·((N + A)/(k + A))^0.602 with
     A = 0.1N (Spall's practical guideline, the 1998 implementation note,
     UNVERIFIED citation details). Hold c fixed, or decay it by
     (k + 1)^−0.101. My simulation held it fixed.
  5. **Clamp each update to 0.5·c_i**, and clamp to the parameter table's
     range.
  6. **One update per GitHub stage** (800 pairs) is safe with rules 3 and 5.
     Without them it diverged in my runs.
  7. **Include a parameter only if its expected recoverable Elo is at least
     about 0.5.** Each dead parameter costs about 0.17 Elo at 20k games.
  8. **Integers.** Round randomly per micro-match (θ = 6.3 plays 6 with
     probability 0.7 and 7 with probability 0.3). The expected Elo is then
     piecewise linear and SPSA sees a smooth function. Coarse parameters
     (SingularMarginPerPly, step 1 on 6) are better rescaled to finer units
     before tuning: a code change, bench-neutral at the default.
  9. **Report** the final θ as the mean of the last 30% of updates (it
     hardly matters at these gains [sim]), with each parameter's trajectory.
  10. **Openings** disjoint from every validation SPRT's ranges (O6).
- **Math.** Shown in §0. Units check: y_score = s̄ − 0.5 = 0.0014391·y_Elo.
  So R(score units) = α/0.0014391 = ε/(1,332·p·0.0014391) = ε/(1.917·p).
- **Theory and literature.**
  - Spall (1992), convergence conditions, as in the KB.
  - Spall (1998), "Implementation of the simultaneous perturbation algorithm
    for stochastic optimization", IEEE Trans. Aerospace and Electronic
    Systems 34(3): the 0.602 and 0.101 exponents and A ≈ 10% of iterations
    (UNVERIFIED: from memory, not in the KB).
  - Polyak and Juditsky (1992), iterate averaging (SIAM J. Control Optim.
    30(4); UNVERIFIED citation details).
  - Kocsis, Szepesvári and Winands (2006), RSPSA (KB research.md): common
    random numbers and antithetic variables gave more than 10x (authors'
    estimate). Fork's colour-reversed same-opening pairs are exactly the
    common random numbers.
- **Why Fork.** The noise (0.21) and the throughput (5,200 games per hour)
  are Fork's own measurements. Fork's table steps (range/20, DESIGN.md 8b)
  are bounds for a tuner, chosen by rule, not calibrated to Elo. For
  RfpMargin the step (6 cp) happens to be close to the w implied by the
  40-against-80 result. For the others it is unknown (O3).
- **Prediction.** With these rules, a 20k-game run of 8 parameters moves
  every steep parameter's trajectory monotonically for its first half. Flat
  ones random-walk within about ±2c.
  - **Refuted if** the trajectories of the measured-steep parameters
    (RfpMargin) are indistinguishable from random walks (|net move| < 1c).
    That means c is too small for them.
- **Cost.** None (rules).
- **Cheapest first experiment.** None needed beyond O4's dry-run.
- **Kill criterion.** Not applicable (a design).
- **Originality notes.** Generic. No other tool's defaults are used.
- **Effort and dependencies.** Part of O4.

### O3. Perturbation sizes calibrated from FORK_SEARCH_STATS firing rates [NOVEL]

- **Mechanism.**
  - SPSA's largest avoidable loss is not knowing w (§0: log-sd of γ
    1.0 → 0.3 lifts the 20k-game gain from +2.6 to +11.5 at p = 16).
  - Elo curvature cannot be measured cheaply, but each margin's mechanism
    can. On a stats-build bench, set c_i so that ±c_i changes the firing
    count of its rule by a fixed relative amount, about ±10%: the share of
    RFP-eligible nodes pruned, futility skips, LMP skips, NMP attempts that
    fail high, SEE skips, aspiration re-searches.
  - This equalises the mechanistic effect of each perturbation, a proxy for
    equal γ. It does not equalise Elo.
- **Math.** If Elo loss is roughly proportional to the square of the
  relative change in a rule's decisions (a local assumption), equal relative
  firing changes give equal γ up to that proportionality. If that constant
  varies across rules by a factor of 3 (log-sd about 0.5), the result is
  still better than an uncalibrated log-sd of about 1.0 [sim: +9.5 at 0.6,
  +2.6 at 1.0].
- **Theory and literature.** None that I know of for engines. It is an
  application of the standard SPSA advice to scale parameters (Spall 1998,
  UNVERIFIED) using a measured surrogate. A2 §6.5 found that mechanism
  metrics (cutoff index, singular precision) predicted SPRTs well, while
  end-to-end label agreement did not.
- **Why Fork.** FORK_SEARCH_STATS already counts most of these decisions
  (DESIGN.md constants table: RFP fail-low share, LMP cutoff histogram,
  singular test counts). It is one bench per parameter at two values, about
  16 benches of about 1 minute.
- **Prediction.** The calibrated c differs from the table step by more than
  2x for at least 2 of the 8 parameters. In O1's run, the calibrated
  parameters show gradient z-scores within a 3x band of each other after
  10k games. **Refuted if** the table steps already land within ±30% of the
  calibrated c for all 8 (then skip O3 in future).
- **Speed cost; compute.** Local, minutes, beside data generation (the
  searches are node-limited).
- **Cheapest first experiment.** The 16 benches.
- **Kill criterion.** As the refutation.
- **Originality notes.** Fork's own procedure. Credit the generic SPSA
  scaling advice.
- **Effort and dependencies.** 0.5 day, before O1.

### O4. The GitHub SPSA driver (infrastructure)

- **Mechanism.** The pieces, all Fork's own:
  - a `tune` workflow, or a `build: tune` input to the SPRT workflow, that
    builds the FORK_TUNE binary once (update.sh passes no FORK_TUNE today);
  - a shard script that plays micro-matches of n = 4-8 pairs per random Δ
    with fastchess (`-engine ... option.RfpMargin=86 ...` for θ⁺ and θ⁻,
    `-repeat`, concurrency 3), on openings from a book range reserved for
    tuning;
  - output per shard: Σ_j (s̄_j − 0.5)·Δ_ij per parameter, the pair count and
    the pentanomial;
  - the merge job sums the shards;
  - a local driver under jobctl updates θ by O2's rules, logs it to the
    ledger and dispatches the next stage with the new θ (one stage = one
    update, 800 pairs).
- **Math.** 20k games = 12.5 stages = 3.9 h. Per-stage overhead is about the
  same as an SPRT stage, since both build in about 5 minutes. Reusing the
  first stage's artifact would save about 25% (UNVERIFIED).
- **Theory.** OpenBench and fishtest run SPSA with workers. Neither fits
  Fork: no server since AWS was suspended, and the shards are ephemeral.
  Fork's sharded stages map naturally onto synchronous SPSA updates.
- **Why Fork.** No SPSA tooling exists (grep: `spsa` appears only in
  ci.yml's FORK_TUNE build check). The SPRT workflow already passes per-match
  options (`test_opts`/`base_opts`), but not per pair.
- **Prediction.** A stage of SPSA plays its 1,600 games within ±10% of an
  SPRT stage's time. **Refuted if** micro-match restarts cost more than 10%
  (then raise n).
- **Cost.** 1-2 days of code, plus tests in the style of tools/github. The
  name check covers new names.
- **Cheapest first experiment.** A local run of the shard script with
  2 micro-matches.
- **Kill criterion.** None (enabler).
- **Originality notes.** Fork's code. Per the rules, no other tool's code is
  read.
- **Effort and dependencies.** Needed by O1, O5, O7 (GitHub version), O8 and
  O10.

### O5. Tune by scaling class

- **Mechanism.** Four classes:
  - **(a) Shallow-horizon margins** (RFP, futility, LMP, SEE pruning, NMP
    surplus, aspiration) act on subtrees within about 6 plies of the
    horizon. Their optimum depends on the eval's error at shallow depth,
    which does not depend on the time control. Tune them at STC.
  - **(b) Depth-scaling constants** (SingularMarginPerPly, SingularMinDepth,
    SingularEntrySlack, NoMoveReduceMinDepth, the LMR divisor after idea 43,
    double-extension limits) change what happens at depths STC rarely
    reaches. Tune them at LTC, with p of about 5-6.
  - **(c) Time management.** Tune only at a control with TCEC's
    base/increment ratio (A2 O8: 600 against Fork's 100), in Phase 5.
  - **(d) The eval scale S** never goes into SPSA beside the margins. Scaling
    S is nearly equivalent to scaling every cp margin at once. That direction
    is degenerate and slows SPSA, and S also sets the adjudication and label
    scales.
- **Math** [sim]. LTC group: p = 6, T = 6, σ = 136. 8k LTC games gives +3.8
  (63%), 16k gives +4.3; 8k costs about 6 GitHub-hours (UNVERIFIED stage
  time). If T = 3, 16k LTC games gives +1.6. **Do not run an LTC SPSA unless
  the group plausibly holds at least 5 Elo.**
- **Theory and literature.**
  - b-survey-stockfish §5: SF's VLTC search tunes failed STC (−5.9, −14.3
    derived) and passed at VLTC, with much more singular/double extension.
  - b-survey-opensource §4.1: a VLTC 8-thread tune lost at 1 thread (−9.4
    STC), "tune at the condition you test".
  - KB best-practices "Fixed-depth vs. timed testing": a change triggered
    only at high depth needs a control that reaches that depth.
  - Fork's own data: IIR +21.5 STC → +26.3 LTC; SE precision rises with depth
    (0.91 at d6 → 0.97-0.98 at d7-12).
- **Why Fork.** The plan says "SPSA at STC, then at LTC" for everything
  (§5.6). That tunes every parameter twice at about 4x the cost per Elo of
  resolution at LTC (A3 §2.5). The split tunes each parameter once, at the
  condition that matters for it.
- **Prediction.** An LTC tune of class (b) moves the extension constants
  toward more extension (a lower SingularMarginPerPly, or a lower
  SingularMinDepth) than an STC tune of the same constants would.
  **Refuted if** the LTC run moves them the other way by more than 1c.
  Corollary: O1's STC-tuned margins keep at least 60% of their STC gain at
  LTC (the O6 guard's estimate). Refuted if the LTC estimate is ≤ 0.
- **Speed cost; compute.** GitHub: 8-12k LTC games, 6-9 h.
- **Cheapest first experiment.** O1's LTC guard already tests (a)'s
  transfer.
- **Kill criterion.** If class (b)'s LTC SPSA plus validation gives
  ≤ +3 nElo at LTC, stop tuning class (b) in Phase 4.
- **Originality notes.** Generic. Credit the survey's sources for the
  VLTC-tune observation.
- **Effort and dependencies.** Class (b) waits for idea 43 (LMR) and batch
  4's double extensions. Class (c) is Phase 5 (owner's plan). Running it
  earlier would be a plan change for the owner to decide.

### O6. Validation protocol for any tune

- **Mechanism.**
  1. **STC SPRT, tuned against default, [0, 5] nElo, cap 6 stages.** If it
     caps with a positive estimate, extend to [0, 3] cap 13, or apply A3's
     accept-at-cap rule (estimate > +3 nElo) if the owner adopts it.
  2. **LTC sign guard:** 3 fixed LTC stages (4,992 games); pass if the nElo
     estimate is above 0. It is not an SPRT, because [−3, 0] cannot decide
     small effects (below).
  3. **Openings:** the tune plays a book range disjoint from every SPRT's
     ranges (`sprt_merge` already refuses overlaps among SPRT stages; the
     tune needs its own reserved range or a second shuffle seed).
  4. **Second-book check** (optional, TCEC-relevant): 1 stage on a balanced
     book (Fork's own random 8-ply openings, as idea 23's match book), with
     the requirement that the estimate is not below −1 SE. UHO's lopsided
     positions may reward aggressive pruning more than TCEC's balanced
     openings would (UNVERIFIED).
- **Math** [sim, normal GSPRT checked at stage ends, 20,000 trials]:

| true nElo | STC [0,5] cap 6: P(H1) / mean stages | STC [0,3] cap 13: P(H1) / stages | LTC [−3,0] cap 6: P(H1) | LTC [0,3] cap 6: P(H1) |
|---|---|---|---|---|
| 0 | 0.00 / 5.9 | 0.00 / 12.9 | 0.00 | 0.00 |
| +5 | 0.09 / 5.9 | 0.20 / 12.5 | 0.06 | 0.01 |
| +10 | 0.53 / 5.3 | 0.89 / 9.3 | 0.46 | 0.17 |
| +15 | 0.93 / 4.2 | 1.00 / 6.2 | 0.91 | 0.68 |
| +20 | 1.00 / 3.2 | 1.00 / 4.6 | 1.00 | 0.97 |

  - The 3-stage LTC sign guard (SE 8.5/√3 = 4.9 nElo) passes a true
    +9 nElo with probability Φ(9/4.9) = 0.97, and a true −5 with 0.15.
  - O1's central +7 Elo is about +12 nElo. It passes [0, 5] in about
    5-6 stages with probability of about 0.7 (between the +10 and +15 rows). At +9 Elo (+15 nElo): 0.93
    within 6.
- **Theory.** Wald (1945) and the pentanomial GSPRT (KB). Smith and Winkler
  (2006, the optimizer's curse, A1 §3.2): the tune's own games always look
  better than fresh ones, so validate on fresh openings.
- **Why Fork.** T = 0 still produces a −2.5 Elo "tuned" set [sim]. Without
  an SPRT, Fork would ship noise.
- **Prediction.** If O1's tune is real, the [0, 5] SPRT passes within
  6 stages. The second-book estimate lies within 1 SE of the UHO estimate.
  **Refuted if** the second book shows the tune below −1 SE while UHO shows
  H1. Then tune on a mixed book next time.
- **Cost.** About 4 STC stages plus 3 LTC stages per tune.
- **Cheapest first experiment.** None separate.
- **Kill criterion.** As in O1.
- **Originality notes.** Generic statistics.
- **Effort and dependencies.** None.

### O7. Antithetic screening for strength-parameterised features [NOVEL]

- **Mechanism.**
  - For any feature that has a continuous strength s (s = 0 is "off", and
    negative s means the opposite action), screen by playing **s = +c
    against s = −c** head to head, not "on against off". Examples: an LMR
    adjustment (reduce less against reduce more), an extension amount after
    idea 43, a history or correction weight, idea 23's residual
    (`LmrCorrectionStrength` extended to negative), a time-management slope
    (node share: more against less time when dominant), a margin offset.
  - The screen estimates the sign of dElo/ds at 0, which is what matters
    first.
- **Math** [derived]. Take a quadratic response with optimum gain G at s*:
  Elo(s) = G·[1 − (1 − s/s*)²]. Then:
  - on against off at s*: D = G;
  - antithetic at ±c: D = Elo(c) − Elo(−c) = **4G·c/s***, so 4G at c = s*
    and 2G at c = s*/2.
  - With the same games, signal 4x means **16x fewer games** for equal power
    (4x at c = s*/2).
  - One stage (800 pairs) has SE 0.21/√800/0.0014391 = **5.16 Elo**. With the
    rule "proceed if D > +1 SE":

| true G (Elo at s*) | on/off P(proceed) | antithetic c = s*/2 | antithetic c = s* |
|---|---|---|---|
| −3 | 0.06 | 0.02 | 0.00 |
| 0 | 0.16 | 0.16 | 0.16 |
| +2 | 0.27 | 0.41 | 0.71 |
| +3 | 0.34 | 0.56 | 0.91 |
| +5 | 0.49 | 0.83 | 1.00 |

  - **Caveat.** If the negative dose is disproportionately harmful (an
    asymmetric landscape), D is inflated by asymmetry rather than by benefit.
    A rule that "reduces less" can screen positive because "reducing more"
    is catastrophic. So the screen is **triage only**: it kills candidates
    (D ≤ 0) cheaply. Survivors get a dose (a mini-SPSA, O8), then the normal
    SPRT, on against off.
  - Realistic amplification is about 2-3x, not 4x, at c ≈ s*/2 [inferred].
- **Theory and literature.** Central differences: Kiefer and Wolfowitz
  (1952, Ann. Math. Statist. 23(3); UNVERIFIED citation details). SPSA's
  antithetic pair (Spall). RSPSA's antithetic variables (KB research.md).
  Using it as a go/no-go screen for engine features is, to my knowledge, not
  a documented practice (NOVEL for Fork's process, not claimed as
  world-first).
- **Why Fork.**
  - A3 §2.6: search features return about 0.8 Elo per stage, and [0, 3]
    passes a +3 Elo feature 21% of the time. Most stages go to features that
    are null or negative.
  - Fork's rejected features sat at −8.7, −10.8, −5.3, −3.8, −6.1 (A2 §2.2).
    For strength-type features, an antithetic stage would have shown D < 0
    in one stage with high probability.
  - Batch 4's LMR node-type terms, the malus balance and idea 42's
    continuation terms are all strength-type.
- **Prediction.** On batch 4's strength-type items, the 1-stage antithetic
  screen's sign agrees with the item's final SPRT sign in at least 4 of 5
  cases where the SPRT decides. **Refuted if** 2 or more of the decided
  SPRTs disagree with the screen's sign.
- **Speed cost; compute.** 1 STC stage per screen. A feature with a per-node
  cost needs its nps measured separately (bench/ab), since both sides run
  the code.
- **Cheapest first experiment.** A retrospective calibration on a known
  result. Check relief as a strength (±1 ply, whole plies today) is expected
  strongly positive. The LMR history term in its tested form (±1 at its
  divisor) is expected ≤ 0 (its SPRT −10.8). 2 stages.
- **Kill criterion.** The calibration gets either sign wrong. Then drop the
  screen.
- **Originality notes.** Fork's own procedure.
- **Effort and dependencies.** Needs a strength option per feature, which
  is cheap behind FORK_TUNE. Fractional doses need idea 43.

### O8. Replace the constant ladder with tune-then-test

- **Mechanism.**
  - The streamlined ladder tests 2-3 values of a new feature's constant,
    each against "feature off", in up to 2 stages (3,200 games), then keeps
    the best point estimate.
  - Replace it, for constants with a continuous scale, by a **mini-SPSA of
    the feature's 1-3 constants with the feature on** (θ⁺ against θ⁻,
    3,200-6,400 games), then the feature's SPRT at the tuned value against
    off.
  - Keep a **1-stage "sanity ladder"** only where a value must be shown
    non-catastrophic for originality, or where the constant is categorical.
- **Math** [sim; the same landscape model, one constant, a 3x steeper side;
  the ladder at spacing δ in units of w, each value vs off, 3,200 games,
  Elo SE 3.7]:

| misplacement T | ladder, 9,600 games: gain (δ = 1w / 2w / 3w) | P(ladder picks best of 3) | mini-SPSA p = 1, 3,200 games | p = 1, 6,400 | p = 2, 6,400 |
|---|---|---|---|---|---|
| 2 Elo | +1.0 / +0.4 / −0.8 | 0.62 / 0.56 / 0.78 | +1.3 | +1.5 | +1.2 |
| 4 Elo | +2.5 / +2.8 / +0.4 | 0.74 / 0.75 / 0.56 | +3.0 | +3.3 | +2.9 |
| 8 Elo | +4.9 / +7.1 / +6.4 | 0.86 / 0.93 / 0.91 | +6.3 | +6.9 | +6.2 |

  - At a third to two thirds of the games, the mini-SPSA matches or beats the
    best-spaced ladder and does not depend on guessing the spacing. It also
    tunes 2-3 constants at once; the ladder picks one.
  - A3's independent estimate for the ladder (P(best) 0.48-0.62 for
    small-effect constants) agrees with my T = 2 row.
  - Cost per batch-4 item: ladder 4-6 stages; mini-SPSA 2-4 stages. Over
    about 9 items that saves **about 15-25 stages (5-8 GitHub-hours)**.
  - What the ladder gives that the mini-SPSA does not: an on/off estimate
    and an early H0 drop-out. O7's antithetic screen (1 stage) covers the
    kill function where a strength exists.
- **Theory.** §0. Also the ladder compares values only through their
  difference against "off". Each estimate has SE 6.1 nElo, so the
  difference between two values has SE 8.7. A direct comparison would
  resolve the same difference with SE 6.1.
- **Why Fork.** The owner's rule makes the ladder "Fork's own measurement"
  for originality. A mini-SPSA log serves the same purpose (Fork's games,
  Fork's procedure).
- **Prediction.** On the first two batch-4 items run both ways, the
  mini-SPSA's value differs from the ladder's pick by less than the ladder's
  spacing, or it beats the ladder's pick in the feature's SPRT estimate.
  **Refuted if** the mini-SPSA's values perform worse in the item's SPRT
  than the ladder's would have (the ladder's own 2-stage estimate at that
  value, compared at equal openings).
- **Cost.** Needs O4.
- **Cheapest first experiment.** Batch 4's first strength-type item: run a
  mini-SPSA (4,800 games) beside its planned ladder.
- **Kill criterion.** As the refutation. Then keep ladders.
- **Originality notes.** Owner's policy decision, since the ladder is the
  recorded originality measurement.
- **Effort and dependencies.** A §5.2 Testing setup change: the owner
  decides.

### O9. Idea 23: what to optimise, the fitness, the budget, and whether to run it

- **Mechanism.** Keep the harness (gate, critic, islands, held-out check).
  **Replace the proxy fitness** with an antithetic fixed-node game screen of
  the residual's strength:
  - the candidate rule r(ctx) enters as base + s·r;
  - play s = +c against s = −c, local, at fixed nodes per move;
  - stop sequentially: drop at D ≤ 0 after 200 pairs;
  - promote the top 5 of the run to a 1-stage GitHub antithetic screen;
  - the best one or two get a dose mini-SPSA (O8) and an SPRT.
  - Region: after idea 43, a **fractional** LMR correction. Today
    `lmr_correction(c) * LmrCorrectionStrength / 64` is integer plies, so
    residual doses are coarse. Alternatively, the owner's SE-margin
    correction, which is TC-sensitive and so needs larger node budgets.
- **Why the current proxy cannot be used** [read, A2 §6.1 and DESIGN.md
  8c]:
  - labels come from the baseline (or off) engine, so agreement measures
    similarity to the baseline;
  - fresh state per position removes history and TT carry-over;
  - the score-error term penalises legitimate rescaling;
  - it never scored any SPRTed change above off (0 of 5 gains predicted;
    Spearman ρ about −0.3);
  - the validation run's four best gains (+0.005 to +0.011) **vanished on
    the 4x set** (−0.0069 to −0.0005), which is the winner's curse.
  - RSPSA's move-score success (KB research.md) tuned weights inside a fixed
    structure. Idea 23 changes structure, which is exactly where
    baseline-labelled agreement fails.
- **Math** [derived].
  - Local throughput: data generation holds 10 of 12 threads, so about
    2 threads are free.
  - At 200k nodes per move (depth about 11; DESIGN.md 8c's proxy budget)
    and about 3.5 M nps, a move takes about 57 ms; a game of about 130 plies
    takes about 7.4 s.
  - A 400-game screen takes about 25 min on 2 threads (SE 10.3 Elo). At
    c = s* it proceeds (D > 0.5 SE) with probability 0.75 for G = +3, 0.61
    for G = +2 and 0.31 for G = 0. One-stage GitHub screen follows for the
    top 5.
  - Budget for a capped pilot: 60 candidates (10 generations of 6) ≈ 25 h
    local on 2 threads (12 h on 4), about 0.75 M tokens (about 12k per
    candidate, DESIGN.md 8c), 5 GitHub stages plus at most 2 dose runs and
    SPRTs (about 10-15 stages).
  - Yield, with a guessed prior: if 5-10% of critic-passed LMR corrections
    have G ≥ +2, then 60 candidates hold 3-6 such rules. The funnel keeps
    about 60-70% of them and about 16-30% of the nulls. Overlap among LMR
    corrections means only the best one or two add up.
  - **Expected +0 to +4 Elo, P(at least one adoption) about 25-40%**
    (low confidence: the prior is a guess).
- **Theory and literature.** AlphaEvolve, FunSearch and MAP-Elites (KB
  research.md §9). David-Tabibi et al. (2010; KB) as a warning: a
  suite-fitness evolution produced +6 ± about 40 Elo in its own match. CPW
  and Kiiski: tuning needs a stop rule.
- **Why Fork.** A2's O2 (fractional depth, then a centred history term and
  cut-node LMR) attacks the same "under-informed LMR" with known terms at
  +3 to +10 for less effort. Idea 23 should come **after** them, so it
  searches for something beyond the known terms.
- **Prediction.** With the repaired fitness, the screen ranks the 2
  calibration rules correctly (check relief positive; the LMR history term
  as tested ≤ 0). At least 1 of the top 5 passes the 1-stage GitHub screen
  at D > +1 SE. **Refuted if** the calibration fails, or 0 of 5 pass.
- **Speed cost; compute.** Local CPU (or pause one data-generation thread
  pair), tokens and a few GitHub stages. The candidate's per-node cost is
  measured at the gate (bench/ab) before any SPRT.
- **Cheapest first experiment.** The 2 calibration screens locally (about
  1 h).
- **Kill criterion.** The calibration fails, or 0 of the top 5 pass the
  GitHub screen. Then archive idea 23 per its spec ("if no-go: archived").
- **Originality notes.** Survivors still need the originality-checker on
  structure and constants. Model memory reproduces famous LMR formulas; the
  critic already screens for that.
- **Effort and dependencies.** After idea 43, node types and idea 42.
  Replaces §5.6 item 13's "3+ days, 40 generations" with a 10-generation
  capped pilot.

### O10. The final retune (§5.6 item 12), rescoped

- **Mechanism.** After batch 4, idea 43 and idea 42 settle, and after the
  removal round (see the critique on order):
  1. **STC pass:** class (a) margins again; history and ordering weights;
     LMR (divisor, minimum move, fractional adjustments); batch 4's adopted
     constants. That is p of about 18-24. Run 30-40k games (6-8 h).
  2. **LTC pass:** class (b), p of about 5-6, 8-12k LTC games (6-9 h,
     UNVERIFIED stage time), only if O5's precondition (T ≥ 5) is plausible.
  3. Validation per O6 for each pass.
- **Math** [sim]. p = 24 at 40k: +9.2 of T = 15. If O1 already took the
  first chunk, the remaining T is the misplacement re-accumulated by
  adoptions (about 0.3-1 Elo per interacting adoption, 3-6 adoptions:
  1-6 Elo), plus the untouched groups' T (LMR, history: 2-6). So
  **+2 to +6 at LTC** across both passes. GitHub cost of about 22-26 h
  (about 1 day of slot), against §5.6's "4-7 days".
- **Theory.** §0 and O5.
- **Why Fork.** Mapping it out:
  - the history weights were measured once on S-512;
  - LMR is bootstrap-era and will change with idea 43;
  - batch 4's constants come from ladders or mini-SPSAs on partial bases.
- **Prediction.** The combined STC pass passes [0, 5] or caps with an
  estimate above +3 nElo. **Refuted if** H0, which would mean the parameter
  set had no headroom left after O1.
- **Cost.** About 1 GitHub-day.
- **Cheapest first experiment.** None separate.
- **Kill criterion.** STC H0 → skip the LTC pass.
- **Originality notes.** As O1.
- **Effort and dependencies.** After items 5, 8, 10 and 11.

---

## 2. Alternatives to SPSA: when each wins

Noise is the binding fact: about 146 Elo per pair, against effects of 1-5
Elo. Any method's information comes from game outcomes, so methods differ in
**how many parameters each game informs** and **how they use structure**.

| Method | Information per game | Fork verdict, with arithmetic |
|---|---|---|
| **SPSA** (paired, antithetic) | all p parameters at once (cross-talk negligible, §0) | **default for p ≥ 4.** About 1,250 games per parameter for 60-65% recovery |
| **Coordinate methods** (ladders, one-at-a-time sweeps) | 1 parameter | p times the games of SPSA for the same precision. Ladder: 9,600 games per constant (O8 table) |
| **CLOP / GP-based BO** (quadratic-logistic or GP surrogate over match results; Coulom 2012 in the KB; Snoek et al. 2012, NeurIPS; TPE, Bergstra et al. 2011, NeurIPS; UNVERIFIED citation details) | 1 scalar per evaluated point, smoothed by a surrogate that must learn about p²/2 curvature terms | **wins for p ≤ 3** where a confidence region or curvature is wanted (eval scale S as a ladder, a time-management slope, O3's w estimate for one key parameter). For p = 8 a full quadratic has 45 coefficients; at about 1,000 games per point and 10-20 points per dimension that is 80-160k games, worse than SPSA's about 10-20k [derived, rough] |
| **CMA-ES** (Hansen and Ostermeier 2001; noise-handling variant, Hansen et al. 2009; UNVERIFIED citation details) | ranks a population; each member's Elo must be resolved | with λ = 4 + ⌊3 ln p⌋ = 10 for p = 8, resolving members to 3 Elo needs about 2,400 pairs each (146/√n ≤ 3), so about **48k games per generation** over tens of generations. Infeasible. Antithetic ES (Salimans et al. 2017, arXiv:1703.03864, UNVERIFIED) is SPSA with Gaussian Δ |
| **Nevergrad / Optuna** (libraries; Rapin and Teytaud 2018, UNVERIFIED) | as the method chosen inside | a convenience layer only; the noise limit is unchanged. A dependency the driver does not need |
| **Local quadratic fit** from fixed-length matches (3-5 values × 3,200 games) | 1 parameter, gives curvature | the only cheap way to **measure w** for one parameter (10-16k games). Use it to check SPSA's optimum and curvature for the single most important parameter (RfpMargin) if O1's result is surprising |
| **Racing / successive halving with SPRTs** | categorical | right for on/off choices and integer gates with big jumps; that is the SPRT itself |
| **LLM structural search** (idea 23) | changes the form, not the constants | complementary to SPSA; needs a game-based fitness (O9) |

Chess practice in the open-source family is SPSA on OpenBench, and
fishtest's SPSA for Stockfish (surveys). Their guidance that c "must be large
enough to make a measurable Elo difference" and that one should "tune few
values at once" (b-survey-stockfish §6) are the qualitative forms of §0's
γ ≈ 1 and dead-parameter cost.

---

## 3. Critique of the current plan in my domain

1. **Item 12 (SPSA retune, "after the search and the network settle",
   STC then LTC, 4-7 days).**
   - **Split it:** O1 now (8 margins, about 9 GitHub-hours), then O10 at
     the end (about 1 GitHub-day).
   - Tune by class, not "everything at STC, then everything at LTC" (O5):
     that doubles the cost and tunes shallow margins where they are
     expensive to measure.
   - **Remove time-management parameters** from any STC or LTC SPSA (O5c).
   - **Keep S out** (O5d).
   - Arithmetic: O1 gives about 2x batch 4's Elo per GitHub-hour, and it
     makes batch 4's verdicts cleaner.
   - Risk of tuning a search that will change: interacting adoptions shift
     the optimum by about 0.3-1 Elo each. O10 recovers that, so at most
     1-6 Elo is temporarily "lost" against +4-12 gained now.
2. **Item 10 (idea 43 "must precede the SPSA retune").** True only for the
   LMR group. It should not gate O1. The open-source survey's §6 record
   (fractional depth about 0 at STC, at most +3 at VLTC elsewhere) also
   suggests keeping idea 43 for what it enables (sub-ply LMR terms, O7
   doses), not as a precondition for tuning.
3. **Item 5 (batch 4 ladders).** Replace 3-value ladders by tune-then-test
   (O8) for continuous constants. Screen strength-type items antithetically
   (O7). That saves about 15-25 stages, and the values come out better.
4. **Item 11 (the full removal round) and the tune order.** Removal SPRTs on
   [−3, 0] cannot confirm neutral removals (A3 §2.6: 5%). Run in a fixed
   order:
   - O1;
   - batch 4;
   - the removal round, limited to bootstrap-era and small features as A3
     proposes;
   - O10;
   - the final SPRT of the phase-end engine against the phase start.

   Removing features **before** the final tune lets the tune re-optimise the
   margins for the remaining set. Tuning before removals would tune a set
   that then changes. Where a feature has a continuous strength, O10's SPSA
   can include it: a strength tuned to about 0 is a removal candidate
   without a separate SPRT.
5. **Item 13 (idea 23's long run, "3+ days, 40 generations").** Not on the
   current proxy (O9). It should be a capped 10-generation pilot with
   antithetic fixed-node fitness, after idea 43, node types and idea 42.
   Otherwise archive it. Expected 0 to +4 Elo.
6. **Idea 34 (RfpMargin 40).** Do not SPRT it separately: it is one point on
   O1's RfpMargin axis (§5.6 already sends it to the retune). SPSA will
   report which side the optimum lies on.
7. **Data-generation interaction.** A tuned default is a labeller change. By
   the labeller policy that means a new data part. Group (a) transfers to
   datagen's depth; group (b) does not. So do not promote LTC-tuned
   depth-scaling constants into datagen without considering that its
   searches are about 20k nodes.
8. **The streamlined policy's "SPSA refines later".** Correct in spirit. The
   arithmetic says SPSA should also be the *primary* value-setter for
   continuous constants, not only a refiner (O8).

---

## 4. What I could not verify

- **The landscape.** My w values, the 3x asymmetry, the heavy-tailed spread
  of T across parameters, and separability are assumptions. Real RFP,
  futility and NMP margins interact (cross terms), which SPSA handles but my
  simulation does not test. Every [sim] number is model-conditional.
- **The total recoverable Elo T** for Fork's margins (6-15 STC) is a
  judgement. Its anchors are the bootstrap-era RfpMargin 40-against-80
  gauntlet (2 SE, a different evaluator), other engines' first-tune results
  (SPRT-selected, from the survey, not re-checked), and A2's mechanism
  arguments.
- **LTC stage wall time** (about 75 min) and therefore every LTC GitHub-hour
  figure.
- **Whether micro-matches** (fastchess restarted every 4-8 pairs) keep a
  stage's game rate. Whether the shards' build step can reuse one tuning
  binary across stages.
- **The pair sd for θ⁺ against θ⁻ games** is assumed equal to the SPRT
  pairs' 0.21. It should be, because both are near-equal engines. It will
  fall as draws rise, so recompute R from the latest pentanomial.
- **Spall (1998)'s exact guidelines** (0.602, 0.101, A ≈ 10%),
  Polyak-Juditsky, Kiefer-Wolfowitz, CMA-ES, TPE, GP-BO, Salimans et al. and
  Nevergrad citations are from memory (UNVERIFIED). Only Spall (1992), CLOP,
  RSPSA, Kiiski (CPW) and David-Tabibi et al. are verified entries in the
  KB.
- **The UHO book's size**, and whether a disjoint tuning range plus all
  future SPRT ranges fit without reuse.
- **Idea 23's yield prior** (5-10% of critic-passed LMR corrections at
  G ≥ +2) is a guess. No Fork data exists on structural-proposal hit rates
  with a valid fitness.
- **O7's real amplification** on asymmetric responses (I estimate 2-3x
  rather than the ideal 4x). The calibration experiment measures it.
- **That FORK_TUNE builds** play at the same depth as release builds on the
  shards. Variables replace constexpr; the nps cost is unmeasured but
  symmetric.


---

# B8. Statistics and testing (ST)

## ST: statistics and testing (Phase 4 think tank, Phase B)

## 1. Summary

Fork's search tests are designed for effect sizes Fork cannot afford to resolve.
They spend most of their GitHub time on runs that end with no verdict. I fitted
an empirical-Bayes prior to Fork's own 15 search SPRTs (they are ignorable to
the stopping rule, so no bias correction is needed). Effects are **not** tiny
on average: the fit gives μ ≈ 0, τ ≈ 10 nElo for non-classic features, so the
typical candidate is worth about ±8 nElo, which is about ±5 Elo. The current
design is [0, 3] nElo with α = β = 0.05 and a 13-stage cap. Its expected
sample size at its own upper bound is about 49 stages, so the cap truncates it
into something closer to a 13-stage estimate with a very strict acceptance
rule.

Under that prior, a design matched to the budget gets the same or more Elo per
test from **2.6x fewer stages**: [0, 6] nElo, α 0.05, β 0.20, cap 8, a futility
stop at stage 2, and a pre-declared accept-at-cap rule. The cost is a false
discovery rate of about 2.5% and an expected harm of −0.01 nElo per test.

Replayed on the nine logged tests that have stage-wise data, the proposed
design reaches the same nine verdicts in **30 stages instead of 59**. The LTC
design is worse than the STC one: [0, 3] capped at 9,984 games passes a
+8 nElo (+4.4 Elo) feature 5% of the time, so the drift-table test could only
have ended undecided.

The other proposals:
- empirical-Bayes reporting with a cumulative block check (the winner's curse
  is about 8-16% of the claimed +68 Elo of tier 2);
- a speed-to-Elo measurement with a throttled 0.5x build (R ± 9 instead of
  ± 27, for fewer stages);
- node-odds screens for networks in place of plain fixed-node screens;
- the removal round rebuilt as a block test, then a factorial screen of only
  the low-prior switches, then one combined guard: about 25 stages instead of
  about 260, and it can actually decide;
- constants chosen head-to-head, which halves the ladder's regret;
- a cut in per-stage overhead, estimated at up to +25% stages per hour,
  UNVERIFIED.

Two negative results:
- Changing the opening book is not worth testing. Fork's pentanomial
  frequencies pin the STC game draw rate to 42-58%, and in an ordered-probit
  model the current bias sits within about 3% of maximum sensitivity.
- Fixed-node games are not variance reduction: their pair sd is 0.212-0.219,
  against 0.208-0.214 at STC.

**Ranked proposals**

"Elo" means the expected Elo effect on the strength Fork ships by the end of
Phase 4. For methodology items it comes from Elo bought or protected, not from
a change to the engine.

| ID | Title | Expected Elo at LTC (range) | Effort (days) | Confidence | NOVEL? |
|---|---|---|---|---|---|
| ST1 | Budget-matched sequential design for features (STC and LTC) | +3 to +8 direct (more accepted gainers); saves about 25 GitHub-hours on batch 4 alone | 0.5 (driver/merge options) + owner decision | high (math, replayed on the log) | for Fork; the method is standard (group-sequential, empirical Bayes) |
| ST5 | Removal round = block test + factorial screen + combined guard | 0 to +3 (keeps a harmful switch from surviving; frees about 70 GitHub-hours) | 2 (per-shard options, WLS script) | medium-high | **NOVEL** for engine testing as far as I know (UNVERIFIED) |
| ST3 | Speed-to-Elo measurement: throttled 0.5x, STC + LTC, plus a depth-confound test | indirect: prices every speed and network decision (each 1% nps ≈ 1.5 Elo) | 1 (test-only build flag) + about 2 STC + 1-2 LTC stages | high | no (time-odds lineage), design is Fork's |
| ST2 | Empirical-Bayes reporting, stopping-bias correction, cumulative block check | 0 direct; prevents mis-planning (claimed +68 → about +57-63) | 0.5 | high | no |
| ST6 | Constants chosen head-to-head, 1 stage per comparison | +1 to +2 (less regret per constant), about 3 stages saved per feature | 0 (dispatch only) | medium-high | small twist, standard design |
| ST4 | Node-odds screens for networks (emulate the shard and TCEC nps ratios) | 0 to +5 (avoids a wrong promotion when shard and TCEC speed ratios differ) | 0.5 (UNVERIFIED that fastchess per-engine `nodes=` works via TEST_OPTS) | medium | **NOVEL** (related to fishtest's nodestime) |
| ST7 | Stage throughput: overhead audit, engine-build cache, poll interval, queue depth | indirect: +15-25% stages per GitHub-hour (UNVERIFIED) | 0.5-1 | medium (estimate) | no |
| ST8 | Phase 4 GitHub budget by expected Elo per stage | reorders §5.6; no Elo of its own | 0 | medium | no |

Units throughout: nElo is Fork's bound scale. Fork's STC is about 0.595 Elo
per nElo, LTC about 0.553 (computed from the logged pentanomials below). One
STC stage is 800 pairs, with an SE of 8.69 nElo, and lasts about 18.5 minutes,
so about 3.2 stages per GitHub-hour. One LTC stage is 832 pairs and lasts about
75 minutes (UNVERIFIED), about 4 STC-stage equivalents. C = 800/(ln 10 · √2) =
245.67. All simulations are mine (scripts in `tank/b/scratch-st/`). They use
the normal approximation in tools/cloud/sprt_merge.py, LLR = n/(2C²)·[(θ̂−θ0)²
− (θ̂−θ1)²]. The simulator reproduces A3 §2.6's table exactly: P(H1) at +5 nElo
is 0.214, and at 0 the expected length is 12.89 stages.

---

## 2. Proposals

### ST1. A budget-matched sequential design for search features

- **Mechanism.** Choose the bounds, β, the cap and the stopping rules for the
  effect sizes Fork actually meets and the games it can afford. Do not take
  α = β = 0.05 on [0, 3] and then truncate it at 13 stages. Proposed **design
  R** (STC):
  - GSPRT on **[0, 6] nElo** (about [0, 3.6] Elo), **α = 0.05, β = 0.20**:
    LLR bounds +2.77 / −1.56;
  - **cap 8 stages** (12,800 games);
  - **futility:** stop after stage 2 if the cumulative nElo estimate is below 0;
  - **R+cap (the owner's option):** at the cap, accept if the estimate exceeds
    +3 nElo, otherwise shelve.

  Everything is pre-declared, so each test still ends in a verdict ("untested
  changes never ship" holds).

  LTC version for the LTC-sensitive list: the same bounds, a cap of 4-6 LTC
  stages and the same cap rule.
- **Math / derivation.**
  - *Why [0, 3] cannot work.* The LLR drift per pair at true θ is
    (θ1−θ0)(2θ−θ0−θ1)/(2C²). At θ = θ1 = 3 that is 9/120,707 = 7.5e-5 per pair,
    so the expected length is about 2.944/7.5e-5 ≈ 39,500 pairs ≈ **49
    stages**, against a cap of 13. Truncation turns it into a test that passes
    +5 nElo (+3 Elo) 21% of the time and leaves **41%** of all tests at "cap,
    shelved" under the fitted prior (simulation).
  - *The prior* (ST2): a hierarchical normal fit to Fork's 15 search SPRTs.
    All 15 give μ 4.6, τ 13.3. Leaving out the three classic big wins (SE,
    IIR, reply) gives **μ 0.1, τ 9.8 (95% range 6.5-16.2)**, the prior for
    batch-4-type candidates.
  - *Operating characteristics* (simulation, 8,000 trials per point; P(accept)
    with the expected number of stages in brackets):

| true nElo (Elo) | current [0,3] cap 13 | R | R+cap |
|---|---|---|---|
| −5 (−3) | 0.000 (10.1) | 0.001 (2.6) | 0.004 (2.6) |
| −2 | 0.000 | 0.002 (3.5) | 0.042 (3.5) |
| 0 | 0.003 (12.9) | 0.018 (4.4) | 0.134 (4.4) |
| +3 (+1.8) | 0.051 | 0.113 (5.6) | 0.412 (5.6) |
| +5 (+3.0) | 0.214 (12.5) | 0.260 (6.0) | 0.637 (6.0) |
| +8 (+4.8) | 0.661 | 0.605 (5.8) | 0.872 (5.8) |
| +12 (+7.1) | 0.981 | 0.931 (4.5) | 0.976 (4.5) |

  - *Value under the priors.* "Gain" is the expected true nElo accepted per
    test, counting accepted negatives against it. FDR is P(true θ < 0 |
    accepted). Harm is the expected negative nElo accepted per test.

| prior | design | gain/test | stages/test | gain/stage | FDR | harm/test |
|---|---|---|---|---|---|---|
| N(0, 10) (batch-4 fit) | current | 3.00 | 9.74 | 0.31 | 0.000 | 0.000 |
| | R | 3.00 | 3.73 | 0.81 | 0.003 | −0.001 |
| | **R+cap** | **3.48** | **3.73** | **0.93** | 0.025 | −0.012 |
| N(0, 6.5) (tight) | current | 1.42 | 11.13 | 0.13 | 0.001 | 0.000 |
| | R+cap | 1.97 | 4.11 | 0.48 | 0.044 | −0.018 |
| N(−2, 8) (pessimistic) | current | 1.39 | 10.24 | 0.14 | 0.000 | 0.000 |
| | R+cap | 1.82 | 3.64 | 0.50 | 0.040 | −0.014 |
| N(4.6, 13.3) (all 15) | current | 7.00 | 8.62 | 0.81 | 0.000 | 0.000 |
| | R+cap | 7.43 | 3.60 | 2.07 | 0.011 | −0.007 |

    Under every prior, R+cap gains **more Elo per test** with **2.4-2.7x
    fewer stages**. Its accepted negatives cost about −0.01 to −0.02 nElo per
    test. Over 20 tests that is about −0.3 nElo in total, against +40-70
    gained.
  - I simulated 14 designs in all (scratch `compare.py`, `compare2.py`). The
    alternatives:
    - A pure fixed-length estimate (2 stages, accept above +4) has the best
      gain per stage, but a 10-16% FDR and 25% acceptance of null changes.
    - A posterior-probability rule (accept at P(θ > 0) ≥ 0.95, cap 8)
      performs like R+cap, but is harder to explain.
    - [0, 8] β 0.2 cap 8, without the cap rule, keeps gain/test at 3.07 for
      3.47 stages.
    R / R+cap sits at the knee of the curve and keeps Fork's GSPRT machinery.
  - *The futility rule's price.* P(stopped at stage 2 | θ) = Φ(−θ/6.14): 31%
    at +3 nElo, 21% at +5, 10% at +8, 2.5% at +12. That is included above.
    Every adopted net-era feature survives it on its logged path (stage-2
    estimates: MC +6.6, reply +6.1, follow +7.0, take +1.3 Elo).
  - *Replay on Fork's log* (stage-wise estimates from sprt-log, converted at
    each era's Elo/nElo ratio):

| test | stages played | under R+cap |
|---|---|---|
| SE [0,5] | 3, H1 | H1 after 3 |
| MC | 6, H1 | H1 after 5 |
| negative extension | 5, H0 | H0 after 1 |
| reply [0,5] | 4, H1 | H1 after 3 |
| follow | 8, H1 | H1 after 5 |
| take | 14, H1 (past the cap) | accept at the cap, 8 (estimate +7.2 nElo); **plain R would shelve it** |
| IIR | 3, H1 | H1 after 2 |
| LMR history | 4, H0 | H0 after 1 |
| rising RFP | 12, H0 | H0 after 2 (futility) |

    **59 → 30 stages, the same nine decisions.** ProbCut and threat ordering
    (8 stages each, stage-wise values not logged) would most likely also have
    ended by stages 2-4. The total for those 11 tests drops from about 75
    stages to about 36, about 12 GitHub-hours saved.
  - *LTC.* The current [0, 3] capped at 6 LTC stages: P(pass) at +8 nElo is
    0.051, at +12 is 0.31, and the mean length at 0 is 6.0 stages. With R+cap
    and an LTC cap of 4: 0.84 at +8, 0.22 at 0, mean 3.0 stages. With a cap of
    6: 0.86 at +8, 0.17 at 0. The drift table (true value plausibly 0 to +3
    nElo) had essentially no chance to pass under the old design.
- **Theory and literature.**
  - Wald, "Sequential tests of statistical hypotheses", Ann. Math. Stat. 16
    (1945).
  - The GSPRT with MLE plug-ins and the pentanomial model: the fishtest
    mathematics page
    (https://official-stockfish.github.io/docs/fishtest-wiki/Fishtest-Mathematics.html,
    opened 2026-11-07), and M. Van den Bergh's notes linked there
    (GSPRT_approximation.pdf, normalized_elo_practical.pdf, sprta.pdf at
    cantate.be/Fishtest; repositories github.com/vdbergh/simul and
    vdbergh/pentanomial).
  - Group-sequential designs, futility and spending: Pocock (Biometrika 64,
    1977), O'Brien and Fleming (Biometrics 35, 1979), Lan and DeMets
    (Biometrika 70, 1983), and Jennison and Turnbull, *Group Sequential
    Methods* (2000). Page and volume details are from memory, UNVERIFIED.
  - Bayesian decision-theoretic stopping: Berry, *Bayesian Statistics and the
    Ethics of Clinical Trials* (UNVERIFIED as a title). The likelihood
    principle (stopping rules are ignorable for the posterior): Berger and
    Wolpert, *The Likelihood Principle* (1988).
  - fishtest itself uses tighter bounds, affordable only with far more games
    (S1 §6). Fork's budget is the binding difference.
- **Why Fork.**
  - A3 §2.6 measured the power gap.
  - A2 §2.2 shows that 4 of 14 net-era search tests ran 12 or more stages.
  - reval-no-check-relief and the LTC drift table both capped.
  - The fitted τ ≈ 10 nElo says Fork's candidates are usually clearly good or
    clearly bad, which is exactly when short sequential designs win.
- **Prediction.**
  - Over batch 4 and item 8 (about 10 tests), R+cap averages **≤ 4.5 stages
    per test**, against 9-10 under the current design.
  - It returns at least as many acceptances as the current design would have.
  - Refuted if the mean exceeds 6 stages, or if a later block check (ST2)
    finds the accepted set worth less than half the sum of their shrunk
    estimates.
- **Speed cost; compute.**
  - No engine change.
  - Tooling: sprt_merge.py already takes `--alpha/--beta`. sprt_run.sh needs
    a cap argument (it has LAST), a stage-2 futility check and the cap rule:
    about 20 lines.
- **Cheapest first experiment.**
  - Run batch 4's first feature under R+cap, beside a shadow evaluation of
    the current rule on the same stages (the current rule's verdict can be
    computed from the same merged counts at no extra cost).
  - Report both verdicts for each of the first 5 tests.
- **Kill criterion.** Return to the old design only if, in the first 5 tests,
  R+cap accepts something the current rule would have rejected outright
  (H0 at its own bounds) on the same games. Under the prior that happens less
  than 1% of the time.
- **Originality notes.** Methodology only. The bounds and caps are derived
  here from Fork's own data; no engine constant is involved.
- **Effort and dependencies.** 0.5 day of tooling plus a standing owner
  decision (it changes Testing setup's bounds policy for features; nets keep
  [0, 5]). It touches §5.6 items 5, 8, 9 and 15 (LTC confirmations), and
  shortens all of them.

### ST2. Empirical-Bayes reporting, stopping-bias correction and a cumulative block check

- **Mechanism.** Report every adopted feature's Elo three ways:
  - the raw estimate;
  - the **posterior mean under Fork's own fitted prior**, which is valid
    despite sequential stopping;
  - fishtest's bias-corrected estimate from the Brownian approximation
    (brownian_approximation.pdf, formula 6.1, linked from the fishtest
    mathematics page).

  Re-fit the prior after every 5 tests. Every 4-6 adoptions, verify the sum by
  a **block check**: the current default against the same commit with the
  block's switches off, at a fixed length of 2 stages.
- **Math / derivation.**
  - The stopping rule depends only on the observed data, so the likelihood of
    θ is N(θ̂; θ, C²/n) whatever the stopping rule. The hierarchical marginal
    likelihood ∏ N(θ̂_i; μ, τ² + s_i²) therefore gives a valid
    empirical-Bayes fit from the logged (θ̂, n) alone (`ebfit.py`).
  - Posterior means for the six tier-2 adoptions, in Elo at each era's ratio:

| feature | raw Elo | posterior, all-15 prior | posterior, batch-4 prior |
|---|---|---|---|
| SE | 14.1 | 12.7 | 11.2 |
| MC | 9.2 | 8.8 | 8.1 |
| reply | 11.5 | 10.6 | 9.6 |
| follow | 7.2 | 7.0 | 6.6 |
| take | 4.5 | 4.5 | 4.3 |
| IIR | 21.5 | 19.2 | 17.0 |
| **sum** | **68.0** | **62.8** | **56.8** |

  - The winner's curse is therefore **8-16%** of the claim. It is small
    because Fork's adopted effects are large relative to their SEs.
  - Conditional on true θ, though, the frequentist bias of a reported estimate
    is large for small true effects. E[θ̂ − θ | accepted] under the current
    design is +6.0 nElo at θ = +3, +4.4 at +5, +2.3 at +8 and +1.1 at +12
    (simulation). So any future small passer's reported value should be
    roughly halved.
  - Under R+cap the bias at θ = +5 is +2.4, because accept-at-cap stops
    selecting on lucky paths.
  - The **self-play to third-party** discrepancy is a separate effect, not a
    statistical one. Head-to-head SPRTs summed to +219 against a gauntlet move
    of +130 (A1 §2.2). Shrinkage explains about 10 Elo of that 89 Elo gap; the
    rest is self-play inflation and the change of anchors. Plan TCEC
    expectations on gauntlets, not on summed SPRTs.
  - *Block check precision.* With 2 stages (1,600 pairs), the SE is 6.1 nElo
    ≈ 3.7 Elo. The tier-2 block (SE, MC, reply, follow, take, IIR; shrunk sum
    about 57-63 Elo, about 95-105 nElo) is resolved to ±12 nElo (95%), enough
    to show whether its value on S512ppr2 is still of the order claimed on
    S-512/S512r2.
- **Theory and literature.**
  - Whitehead, "On the bias of maximum likelihood estimation following a
    sequential test", Biometrika 73 (1986), UNVERIFIED details.
  - Efron, "Tweedie's formula and selection bias", JASA 106 (2011).
  - Smith and Winkler, "The optimizer's curse", Management Science 52 (2006),
    already cited by A1.
  - The fishtest FAQ's warning that SPRT estimates of passed patches are
    biased (S1 §6).
- **Why Fork.**
  - A3 §2.7 flags the winner's curse.
  - The re-validation (item 11) needs a calibrated prior per feature.
  - SPSA headroom estimates and idea 46's speed hurdles both use these sums.
- **Prediction.**
  - The block check of tier 2 on S512ppr2 gives +80 to +115 nElo.
  - Refuted (meaning the features interact or have faded on the new net) if
    it is below +60 nElo.
- **Speed cost; compute.** 2 stages per block check, about 40 minutes. No
  engine change: the switches exist (SearchSwitches, TUNE build).
- **Cheapest first experiment.** One tier-2 block check (2 stages) as
  GitHub filler. It doubles as ST5's step 0.
- **Kill criterion.** None for the reporting; it is free. Drop the block
  checks if two in a row match the shrunk sums within 1 SE (additivity
  holds).
- **Originality notes.** Methods only; cite fishtest's Brownian
  approximation document if its estimator is used.
- **Effort and dependencies.** 0.5 day: a `--prior` option in a report
  script, beside sprt_merge.py. It feeds ST5 and ST8, and changes nothing in
  §5.6's order.

### ST3. The speed-to-Elo measurement: a throttled 0.5x build at STC and LTC, plus a depth-confound test

- **Mechanism.**
  - A test-only build flag burns a calibrated number of cycles per network
    evaluation, for example the output layer evaluated k extra times behind
    a compiler barrier, so that ab_search shows 0.50 ± 0.01 of the base's
    nps on the identical tree. The base is the same commit without the flag.
  - Play 2 STC stages and 1-2 LTC stages.
  - Optional cross-check with no code: a node-odds self-match, the test at
    400k nodes per move against the base at 800k, which measures R at the
    fixed-node screen's own budget.
- **Math / derivation.**
  - The Elo SE at a −106 Elo deficit: pair-score mean m ≈ 0.35, dElo/dm =
    400/(ln 10 · m(1−m)) = 764, pair sd ≈ 0.24. That gives 183 Elo-units per
    pair, and **SE(R) = 4.6 at 1,600 pairs (±9.0 at 95%)**.
  - The planned 0.85x with 4,000 games: dElo/dm 699, pair sd 0.21, SE 3.28
    Elo over |log2 0.85| = 0.2345, so SE(R) = 14 (±27).
  - **The proposed design is 3x more precise for 80% of the games.**
  - LTC, 1 stage (832 pairs, pair sd ≈ 0.22): SE ≈ 5.8, R_LTC ± 11.4 (±8.1
    with 2 stages). The ratio R_LTC/R_STC is resolved to about ±0.13.
  - *Linearity.* The gate decides at r = 0.82-0.95, but the measurement is at
    0.5. Optional 0.8x point (2 stages): about −34 ± 7 Elo, so R_0.8 to ±22.
    That detects curvature above about 25%. S1 reports that SF's log-linearity
    held to about ±20% across small odds.
  - *The depth confound.* A1 and A3 fitted R from FN − STC gaps over 8 nets:
    R = 106 ± 10 statistically, with χ² 1.9x the expected value. A1's fit with
    an intercept gives c ≈ +17 (FN overstating), with R = 115 ± 59. Once R is
    measured directly, c becomes identifiable as the mean residual,
    mean(FN − STC − R̂·log2(1/r)). A residual near 0 means the 800k-node
    screen carries no depth bias. A residual near +10 means it overstates
    eval gains by about 10 Elo, and the screen budget should be lowered to
    STC-equivalent nodes (ST4).
- **Theory and literature.**
  - Time-odds measurement is long-standing practice (CPW Engine Testing; the
    fishtest wiki's speed-up guidance, S1 §6).
  - Diminishing returns with depth: Heinz, "Diminishing returns for
    additional search in chess" (Advances in Computer Chess 9, 2001?
    UNVERIFIED); Ferreira, "The impact of search depth on chess playing
    strength", ICGA Journal 36(2), 2013 (UNVERIFIED details).
- **Why Fork.**
  - The rate decides the speed gate (A3 §1.4: 0.90 costs about 16 Elo),
    idea 46, S512cl, the LTC-candidate bucket and the return on speed work.
    C4's +4% was worth about +6 Elo.
  - A3 §1.5 flags the Move Overhead trap in time odds: the overhead
    (100 ms) exceeds the increment (80 ms), so 4+0.04 is not 2:1. The
    throttled build avoids it.
- **Prediction.**
  - R_STC = 85-125 Elo per doubling (1.2-1.8 Elo per 1%); refuted if outside
    60-150.
  - R_LTC/R_STC ≥ 0.8; refuted if below 0.6.
  - Node odds at 800k/400k give R_FN within ±20% of R_STC.
  - The 8-net mean residual is |c| < 8 Elo; refuted if above 12 (then FN
    screens need a depth correction).
- **Speed cost; compute.** The flag never ships. 2 STC stages (37 minutes)
  plus 1-2 LTC stages (1.25-2.5 hours, UNVERIFIED stage time).
- **Cheapest first experiment.** The node-odds cross-check needs no code: 1
  stage with TEST_OPTS `nodes=400000`. UNVERIFIED: whether fastchess's
  per-engine `nodes=` overrides `-each`; check it on the first shard log.
- **Kill criterion.** If the throttled build cannot hold 0.50 ± 0.02 of
  identical-tree nps across 10 bench rounds, use node odds alone.
- **Originality notes.** Method only.
- **Effort and dependencies.** 1 day for the flag. It replaces the method of
  §5.6 item 4, not its slot, and settles the "LTC candidate" bucket (A3 §1.4
  item 4) with its LTC half.

### ST4. Node-odds screens for networks [NOVEL]

- **Mechanism.** For a network candidate whose identical-tree nps ratio is r
  (measured **in the build that will play**), play test = candidate at r·N
  nodes per move against base = the default at N nodes per move. Choose N as
  the STC median nodes per move on the shards: about 500k (A3 §1.1),
  UNVERIFIED, so measure it from shard logs.
  - This emulates a timed match at speed ratio r with no R and no timing
    noise.
  - Its real use is **ratios the shards cannot play**: TCEC's clang-19 build
    (x86-64-v3, or v4 with the AVX-512 output layer) can have a different r
    from the shards' g++ v3 build (A3 §1.6). A node-odds match at the TCEC
    ratio is the only cheap way to see a design that is "neutral on the
    shards but positive at TCEC".
- **Math / derivation.**
  - The speed-adjusted FN rule predicted the STC sign for 8 of 8 nets, but
    with a residual RMSE of about 14 Elo. That is about twice the pure noise
    of 1,600-game results (each about ±10 at 95%, so the difference has an
    SD of about 7).
  - A node-odds screen removes two error sources: the R uncertainty
    (±10-20%, or ±2-5 Elo at r = 0.85) and the depth mismatch (the c term,
    ST3).
  - Expected residual against STC: about 7-9 Elo (noise plus TM differences),
    so P(correct sign) rises for marginal candidates. For a true STC effect
    of +8 Elo, P(sign right) goes from Φ(8/14) = 0.72 to Φ(8/8) = 0.84.
- **Theory and literature.** fishtest's "nodestime" mode for new
  architectures (S1 §6, which says it does not replace real-TC tests). The
  asymmetric node budget is my addition (NOVEL as far as I know; UNVERIFIED
  that no engine project does it).
- **Why Fork.** Six of six FN→STC sign flips came from speed not being
  priced (A3 §2.3). A1 §4.2 suspects S512+X's runner ratio differs from the
  local 0.818. TCEC runs a different build from the SPRTs.
- **Prediction.**
  - For the next 3 or more network candidates, node-odds results at the shard
    ratio predict the STC result with a residual RMSE ≤ 10 Elo, against about
    14 for speed-adjusted FN.
  - Refuted if the RMSE is ≥ 12 over at least 4 candidates.
- **Speed cost; compute.** It replaces the 800k FN stage, so the cost is 1
  stage either way. Node-limited stage time does depend on runner CPU speed,
  so expect stragglers.
- **Cheapest first experiment.** For the next candidate, run both the
  standard FN screen and the node-odds screen (+1 stage) and compare each
  with the STC result.
- **Kill criterion.** No improvement in residual over 4 candidates: keep FN
  as diagnostic only, or skip it (§3).
- **Originality notes.** Method only.
- **Effort and dependencies.** About 0.5 day: run_shard.sh/TEST_OPTS, and an
  nps-ratio measurement in the shard and TCEC builds, which is A3 §1.7 item 1.
  It modifies the kept rule "the fixed-node screen for new networks"; owner
  decision.

### ST5. The removal round rebuilt: block test, factorial screen, combined guard [NOVEL]

- **Mechanism.** Item 11 as planned switches every search feature off in turn
  and runs an SPRT on [−3, 0] for each. Proposed instead:
  - **(0) Triage by posterior.** Leave out of the round every feature whose
    network-era measurement puts P(value ≤ 0) below 1%: SE, MC, reply,
    follow, IIR, check relief (just measured, +5.2 ± 4.7 nElo), and the
    tier-1 core (PVS, TT, QS, NMP, LMR, RFP, futility, SEE pruning, Syzygy).
    These go to SPSA, not to removal.
  - **(1) Block check** of tier 2 (ST2), 2 stages.
  - **(2) A factorial screen** of the remaining low-prior switches, k ≈ 8-12:
    lmr-in-check, SEE-in-quiescence, aspiration, mate distance,
    TT-refine (never verified), the futile-node filter, the forced-move stop,
    take history, LMP and any batch-4 adoption with a small estimate. Each of
    the 16 shards of a stage plays one design row (a TEST_OPTS string with
    m = 3 switches off) against the full engine. The per-shard pentanomials
    are fit by weighted least squares: nElo_row = Σ_j β_j·x_row,j, with no
    intercept because the base is the full engine.
  - **(3) Decide:** remove switch j if its posterior mean value is ≤ +1 nElo
    (the price of keeping the code).
  - **(4) One combined guard:** all removals together against the full
    engine, with R-type bounds [−6, 0] (or a fixed 4 stages, accepting the
    removal set if the estimate is above −3 nElo).
- **Math / derivation.**
  - *Why the planned round cannot decide.* Certifying that a neutral feature
    costs less than 3 nElo with α = β = 0.05 needs n = (3.29·C/3)² ≈ 72,600
    pairs ≈ **91 stages per feature**. With power 0.8 it is still about 52
    stages. Under the 13-stage cap a neutral feature reaches H1 5% of the
    time (A3). About 20 switches × 12.9 stages ≈ 260 stages ≈ 80 GitHub-hours
    would remove almost nothing.
  - *Factorial efficiency.* (`factorial2.py`, A-optimal 16-row designs; mean
    per-feature SE)

| design | stages | per-feature SE (nElo) | 95% ± | equivalent dedicated stages per feature | efficiency |
|---|---|---|---|---|---|
| k = 8, m = 1 (one off per row) | 16 | 6.14 | 12.0 | 2.0 | 1.0x |
| k = 8, m = 3 | 16 | 4.10 | 8.0 | 4.5 | 2.2x |
| k = 8, m = 3 | 24 | 3.35 | 6.6 | 6.7 | 2.2x |
| k = 12, m = 4 | 16 | 4.48 | 8.8 | 3.8 | 2.8x |
| k = 12, m = 4 | 24 | 3.66 | 7.2 | 5.6 | 2.8x |

  - Analytically, for a balanced design with r offs per feature and λ
    co-occurrences, Var(β_j) ∝ [1/(r−λ)]·[1 − λ/(r−λ+kλ)]. For k = 8, m = 3
    that is 3.38σ²/N, against 8σ²/N for dedicated tests: **2.4x**.
  - *Decision quality at SE ≈ 4.* P(remove | true value θ) = P(posterior
    mean ≤ 1): about 50% at θ = 0, 23% at +3, 11% at +5, 2.5% at +8.
    Expected Elo lost per kept-or-removed decision is below 1 nElo, against a
    planned round that removes nothing.
  - *Interactions.* β_j is the effect of removing j while about m−1 others
    are also off. A redundant partner l (removing both costs more than the
    sum) biases j toward "keep" by about γ·(λ/r). That is conservative. A
    synergistic partner (j only works when l is on) biases toward "remove".
    The combined guard (step 4) catches that, because it tests the joint
    removal directly.
  - *Cost.* (1) 2 + (2) 16-24 + (4) 4-6 = **22-32 stages ≈ 7-10
    GitHub-hours**, against about 80, with a decision for every switch.
- **Theory and literature.**
  - Fisher, *The Design of Experiments* (1935).
  - Plackett and Burman, "The design of optimum multifactorial experiments",
    Biometrika 33 (1946).
  - Box, Hunter and Hunter, *Statistics for Experimenters* (2nd ed. 2005).
  - Balanced incomplete block designs (Yates 1936, UNVERIFIED citation).
  - The combined guard is S1 §7.2.5's suggestion; the fishtest
    simplification philosophy is in S1 §6.
  - I know of no chess engine project using factorial screens in its test
    framework (UNVERIFIED).
- **Why Fork.**
  - A3 §2.6: about 80 hours for little decided output.
  - reval-no-check-relief spent 13 stages with no decision.
  - The switches exist and stay until item 11 (Quality control 6).
  - 16 shards per stage map one-to-one onto 16 design rows.
- **Prediction.**
  - Of the 8-12 low-prior switches, 2-4 come out with posterior mean ≤ +1
    nElo and are simplified away. The combined guard of those removals
    estimates ≥ −3 nElo.
  - At least one switch (likely aspiration or mate distance) has |β| < 3.
  - Refuted if the factorial estimates disagree with dedicated estimates
    where both exist. Check relief can be included as a known control (−5.2
    measured): the factorial should give −5 ± 8 for it.
- **Speed cost; compute.** 22-32 STC stages. All switch configs need the
  TUNE build on both sides (same speed).
- **Cheapest first experiment.** A pilot of 1 stage with k = 4 known
  switches, including check relief as the control, with m = 2. The tooling is
  validated if the WLS reproduces the control's sign.
- **Kill criterion.** If the pilot's control estimate is off by more than
  2.5 SE, or the rows show unequal shard counts or opening reuse, go back to
  dedicated tests but under ST1's design (fixed 4 stages each, decide by
  posterior).
- **Originality notes.** Method only; Fork's own switches.
- **Effort and dependencies.** About 2 days: a sprt.yml input mapping each
  shard to its own TEST_OPTS (a workflow change; owner), a "design" mode in
  run_shard metadata, an exemption in sprt_merge.py's same-options check for
  design runs, and a WLS analysis script. It replaces §5.6 item 11's method,
  keeps its place after the last feature, and shrinks it from 3-5 days of
  GitHub to about 0.5 day. The same per-shard tooling serves ST6's parallel
  arms.

### ST6. Constants chosen head-to-head, at 1-1.5 stages per comparison

- **Mechanism.** The streamlined ladder tests each of 2-3 values against
  "feature off", 2 stages each, picks the best point estimate, then runs the
  feature SPRT on fresh openings. Proposed instead:
  - select by **direct matches between values**, for three values: v1 vs v2,
    and v2 vs v3, 1.5 stages each, the same budget as one stage per value;
  - the winner goes into ST1's design against "off".
  - The originality rule's "Fork's own measurement" is met by the logged
    head-to-head results.
- **Math / derivation.**
  - The difference of two "vs off" estimates has variance 2σ²/n. A direct
    match has σ²/n, so for the same games head-to-head halves the variance
    of the comparison that actually decides.
  - Simulation (`ladder.py`; three values with truths spaced s nElo apart,
    random order):

| spacing | budget | each-vs-off: P(best), regret | head-to-head: P(best), regret |
|---|---|---|---|
| 4 nElo | 3 stages | 0.53, 2.50 | 0.64, 1.83 |
| 4 nElo | 6 stages | 0.61, 2.01 | 0.73, 1.27 |
| 6 nElo | 3 stages | 0.62, 2.88 | 0.75, 1.76 |
| 2 nElo | 3 stages | 0.43, 1.61 | 0.49, 1.40 |

  - The current ladder's extra 3 stages, going from 1 stage per value to 2,
    buy 0.5 nElo of regret: **0.17 nElo per stage**, against ST1's 0.8-0.9.
    SPSA refines the value later anyway.
- **Theory and literature.** Paired comparison designs, ranking and selection
  (Bechhofer, Ann. Math. Stat. 25, 1954, UNVERIFIED); successive elimination
  and racing (Maron and Moore 1994; Even-Dar, Mannor and Mansour 2006,
  UNVERIFIED details).
- **Why Fork.** A3 §2.6 puts the ladder's pick-best probability at 0.48-0.62.
  The ladder exists mainly for originality (DESIGN Testing setup,
  2026-11-06).
- **Prediction.** Head-to-head selection plus R+cap averages ≤ 7 stages per
  feature, including selection, against about 16 for ladder plus SPRT today.
  Refuted if it is above 9.
- **Speed cost; compute.** None beyond the stages.
- **Cheapest first experiment.** The first batch-4 item with two candidate
  values: one head-to-head of 2 stages, then ST1.
- **Kill criterion.** If the owner's originality rule requires the
  "vs off" form, keep 1 stage per value; that still saves 3 stages per
  feature.
- **Originality notes.** It changes how constants are justified: the
  constants table gets "head-to-head, N games, Δ ± e".
- **Effort and dependencies.** Dispatch only. It amends Testing setup's
  streamlined standard; owner decision. It applies to §5.6 items 5 and 8.

### ST7. Stage throughput: an overhead audit, a cached engine build, a shorter poll interval and queue depth

- **Mechanism and model.**
  - Phase 3 measured a mean STC game at 23.6 s (Testing setup, adjudication
    validation). A stage plays 1,600 games over 48 slots (16 shards × 3), so
    about 33 games per slot ≈ **13.1 minutes of play**, against a stage
    spacing of 18.5 minutes. That leaves about 5.4 minutes (29%) of fixed
    cost (estimate, UNVERIFIED).
  - Candidate sources of that fixed cost:
    - the driver's 120 s poll, about 60 s of average detection latency;
    - the build job rebuilding both engines in a fresh ubuntu:22.04 container
      every stage (apt-get plus two builds, about 3 minutes est.), though the
      commits do not change between stages;
    - shard setup (checkout, tools and book fetch, table cache restore);
    - the merge job;
    - the straggler tail: the slowest of 48 slots runs about +1 minute at a
      game-time sd of about 5 s.
  - Caching `engines/` by (base SHA, test SHA, arch, compiler) and polling
    every 20 s could bring a stage to about 14-15 minutes: **+25% stages per
    hour** (estimate).
  - **Utilisation matters more.** A3 §2.7 counts 161 STC + 9 LTC stages over
    about 9 days, about 61 GitHub-hours of about 216: **about 28%
    utilisation**. The binding constraint has been ready candidates and
    decisions, not shard capacity.
- **Theory.** Amdahl's law for fixed per-stage cost. Little's law: keep the
  queue non-empty.
- **Why Fork.** One run at a time (DESIGN Testing setup). CI pushes (about
  35 minutes) block SPRT stages.
- **Prediction.**
  - Job timings of the last 10 STC runs show ≥ 3 minutes of each stage
    outside game play. Refuted if under 2 minutes; then drop the cache idea.
  - With a cache and a 20 s poll, spacing falls below 16 minutes.
- **Speed cost; compute.** None.
- **Cheapest first experiment.** Read-only: `gh run view <id> --json jobs`
  for 10 recent runs, comparing each job's start and finish with the shard
  play time (I did not run this, per the brief).
- **Kill criterion.** Fixed cost under 2 minutes per stage.
- **Originality notes.** None.
- **Effort and dependencies.** 0.5-1 day (actions/cache step and driver
  POLL). Plus a policy: **keep two ready SPRTs queued** (supervised waiters
  already exist), so idle hours are filled by work, not by filler. Owner
  decision on the workflow edit.

### ST8. The Phase 4 GitHub budget by expected Elo per stage

- **Mechanism.** Rank the remaining GitHub work by expected Elo per
  STC-stage equivalent, with LTC stages counted as 4. Fill the queue in that
  order, subject to dependencies.
- **Math / derivation** (rates from Fork's history and the priors above;
  every Elo figure is a placeholder estimate):

| work | stages | expected Elo (STC) | Elo/stage | basis |
|---|---|---|---|---|
| network promotions (retrains on g3s2+g3f+g3g, idea 46's distillation) | 1-3 each | +10 to +40 each | 5-40 | A3 §2.7: nets 12.5 Elo/stage; Kaggle- and datagen-bound |
| time management, node share and stability (if moved into Phase 4) | about 6 STC + 2-3 LTC ≈ 16 | +5 to +12 (A2 O1; S2 §4.2) | 0.3-0.75 | zero nps |
| SPSA of the eval-dependent margins at STC (S2 §4.1: +15-35, an engine-family prior; A2 more cautious, +3-10) | about 31 (50k games) + 4 confirmation | +3 to +20 | 0.1-0.6 | resolves each parameter's ±c slope to ±1.55 nElo (1σ) after 25k pairs: SE = C/√N |
| batch 4 + item 8 under ST1/ST6 | about 10 × 6.7 ≈ 67 | 10 × 3.48 nElo × 0.595 ≈ +21 (N(0,10) prior) | 0.31 | ST1 table |
| batch 4 + item 8 under the current design | about 10 × 15.5 ≈ 155 | 10 × 3.0 × 0.595 ≈ +18 | 0.11 | A3 §2.6 |
| removal round under ST5 | about 25 | 0 to +3 (catches harm), plus simplicity | 0-0.1 | ST5 |
| removal round as planned | about 260 | about 0 | about 0 | A3 |
| re-validation filler (B-4, keep-exact, B-3, root fail-high fix) | about 4 × 4 under ST1 | posterior means about 0 or below (−4.1, −0.6, +0.65, −14.6 Elo bootstrap-era) | below 0.1 | only when nothing else is queued |
| LTC confirmations of STC passes outside the LTC list | 4 per feature | 0: a single LTC stage has SE about 8.5 nElo, which cannot resolve a ratio | 0 | keep the 2026-11-06 policy |

  - Batch 4 and item 8 under ST1/ST6, plus the removal round under ST5,
    free about **88 + 235 ≈ 320 stages ≈ 100 GitHub-hours** against the
    planned methods. That covers SPSA at STC and LTC for the extension
    parameters, plus time management, with room left over.
- **Why Fork.** A3 §2.7: search features have returned 0.77 Elo/stage, nets
  12.5. Utilisation is 28% (ST7).
- **Prediction.** Under ST1/5/6, Phase 4's remaining search work (batch 4,
  item 8, SPSA STC, removal, TM) fits in **≤ 250 STC-equivalent stages
  (about 80 GitHub-hours)**. The current methods would need ≥ 550. Refuted if
  ST1's mean exceeds 6 stages per test (see ST1).
- **Cheapest first experiment.** None; it is a scheduling rule.
- **Kill criterion.** None.
- **Originality notes.** None.
- **Effort and dependencies.** 0 days. It argues for two **plan changes for
  the owner**:
  - (a) SPSA at STC, margins only, before or interleaved with batch 4: its
    Elo per stage is at least comparable, and batch 4's features are
    otherwise judged against bootstrap-era margins (A2 §1.4);
  - (b) time management before item 12 (A2 O1).
  Both reorder §5.6; neither adds GitHub load beyond what ST1 and ST5 free.

---

## 3. Critique of the current plan in my domain

1. **Item 4 (speed-to-Elo, 0.85x, about 4,000 games): redesign.**
   - It gives R ± 27 (±26%).
   - It inherits the Move Overhead distortion: 100 ms of overhead against an
     80 ms increment.
   - ST3's 0.5x throttled build gives ±9 in 2 STC stages, and adds R_LTC for
     1-2 LTC stages, which settles the LTC-candidate bucket.
   - Keep the item's slot.
2. **Item 5 (batch 4): keep the content, change the method.**
   - Its 9 items under ladder plus [0, 3] cost about 140-155 stages (A3: about
     43 hours). They would return about 1.8 Elo per test.
   - Under ST6 + ST1 they cost about 60-67 stages for about 2.1 Elo per test.
   - Order inside batch 4 by prior: items with an information-adding
     mechanism first (node types, TT-PV, double extensions on the LTC list).
     The history-gated items wait for A2 O3's persistence diagnosis, because
     their thresholds are miscalibrated if histories saturate in games.
3. **Item 9 (re-validation filler): shrink to "only when nothing is
   queued".**
   - Posterior means of the four filler items are near 0 or below.
   - Each would cost about 4 stages under ST1, and about 12 under the current
     design.
   - Idea 29's measurement (local, no GitHub) is the useful part of B-3 and
     the root fail-high fix.
4. **Item 11 (full re-validation): redesign as ST5.**
   - The planned round cannot reach H1 on a neutral feature: it needs about
     91 stages per feature, and the cap gives 13.
   - The planned round costs about 260 stages, and will mostly end at "cap,
     kept".
   - The result is that *every* switch survives by default, which is not a
     re-validation.
5. **Item 12 (SPSA, STC then LTC): move earlier and split.**
   - SPSA at STC for the eval-dependent margins first (ST8a).
   - LTC SPSA only for the extension and singular parameters (S1 §7.2.6). LTC
     costs about 4.3x STC per unit of Elo resolution (A3 §2.5), so a full LTC
     SPSA of about 30 parameters (≈ 50k LTC games ≈ 30 LTC stages ≈ 37 hours)
     is poor value.
   - Confirm SPSA output with an R-type SPRT and report the shrunk gain. SPSA
     output is an optimiser's-curse estimate.
6. **LTC policy.**
   - The 2026-11-06 restriction (LTC only for the LTC-sensitive list) is
     statistically right: one LTC stage resolves about ±17 nElo (95%), so
     confirmations of STC passes say almost nothing per feature.
   - But the LTC SPRT itself ([0, 3], 6 stages) passes a +8 nElo feature
     **5%** of the time. LTC-list items must use ST1's design, or they can
     never pass.
7. **"Fixed-node screen for new networks" (kept rule): demote to a
   diagnostic.**
   - For a promotion candidate, an STC [0, 5] stage costs the same as an FN
     stage and answers the real question. Network effects are large, so STC
     usually decides in 1-2 stages.
   - FN is worth playing only where the decomposition (per-node quality
     against speed) informs design, for example a new input type. Even then,
     use ST4's node-odds form.
   - Retrains of the same architecture (S512ppr2's case) should skip it, as
     already happened.
8. **The seed-noise rule (dropped 2026-11-06): agree, with one caveat.** A
   single-seed network SPRT carries about ±10-15 Elo of seed luck (A3 §2.3;
   i13 arm B −14.8). Promotions under +15 Elo are partly seed. That is
   harmless for promotion, because the candidate is still at least as good in
   expectation, but it matters when attributing *recipe* effects.
9. **Opening book: no change (negative result).**
   - Assume the two games of a pair are conditionally independent given the
     opening. Then P(pair = ½) + P(pair = 1½) = 2·E[p_d(1−p_d)].
   - Fork's S512r2-era STC tests show 0.486-0.493, so E[p_d(1−p_d)] ≈ 0.243
     and the **mean game draw rate lies in 42-58%**. A3's bound was 24-70%.
     At LTC (drift test, 0.481) the rate is 40-60%.
   - In an ordered-probit model calibrated to that (draw band h = 0.84, book
     bias B = 0.68 latent units, so the advantaged side scores 68.5%), the
     sensitivity in nElo per unit of strength is 300 at the current bias,
     against 308 at the best (B = 0, balanced). That is at most **5% fewer
     games** for a balanced book, and less with spread in opening bias
     (`book.py`).
   - fishtest's preference for UHO comes from draw rates far above Fork's.
     Revisit only if STC draw rates pass about 75%.
10. **Fixed nodes are not variance reduction.** FN round-2 pair sd was
    0.212-0.219, against 0.208-0.214 at STC (A3 §2.5). Game outcomes dominate
    the variance. Use FN for control (node odds), not for cheaper tests.
11. **The proxy funnel in idea 23 (item 13).** A2 §6 shows the label-and-sweep
    proxy biased toward "off", with Spearman ρ ≈ −0.3 against SPRT outcomes.
    - Statistically, a screen is worth running only if P(screen passes |
      bad) × cost saved > screen cost.
    - A proxy with ρ ≤ 0 saves nothing; every candidate needs an SPRT anyway.
    - Until the repaired proxy (A2 O8.3) reproduces at least IIR's sign and
      two of the four failures, idea 23's long run should feed candidates
      straight into ST1 at a fixed number of SPRTs per generation, not
      through the proxy.
12. **Multiple testing across Phase 4.**
    - About 20 more feature tests under R+cap give an expected 2-3
      null-effect acceptances: harmless, but they add code.
    - Expected accepted harm is about −0.25 nElo in total.
    - The combined guard in ST5 and ST2's block checks are the controls.
      fishtest's "4-5 tries per idea" rule (S1 §6) should be adopted. Each
      retry of a failed idea spends α again: three retries at α 0.13 (R+cap
      at θ = 0) give about 35% chance of a spurious pass for a null idea.

---

## 4. What I could not verify

- **LTC stage wall time** (about 75 minutes) and the STC per-stage fixed
  overhead (about 5.4 minutes). Both are derived from ledger spacing and
  Phase 3's 23.6 s mean game, not from GitHub job timings, which I did not
  query.
- **The prior's shape.** It is a normal fit to 15 tests. A heavier-tailed or
  bimodal truth would shift the optimum, though R+cap beat the current design
  under all five priors I tried. The stopping-rule-ignorability argument
  assumes all tests are logged, which sprt-log states.
- **Stage-wise nElo for the S-512-era tests.** These are converted from the
  logged Elo with each test's final Elo/nElo ratio (0.65-0.67), not
  recomputed from per-stage pentanomials. ProbCut's and threat ordering's
  stage paths are not logged.
- **The draw-rate bound (42-58%)** assumes the two games of a pair are
  conditionally independent given the opening. Exact rates need the shard
  logs' per-game results.
- **The book model** is an ordered-probit idealisation. Real UHO openings
  include some that are effectively decided, and these waste pairs.
- **fastchess per-engine `nodes=`/`tc=` through TEST_OPTS** overriding
  `-each`: untested (ST3, ST4).
- **Factorial interaction sizes** among Fork's switches: unknown. The bias
  direction is argued, not measured.
- **SPSA Elo** (+3 to +35) rests on other engines' records (S2) and A2's
  reasoning, not on any Fork measurement.
- **Literature details** marked UNVERIFIED: volume, page and title details
  for Pocock, O'Brien-Fleming, Lan-DeMets, Whitehead, Heinz, Ferreira,
  Bechhofer, Yates and racing/elimination papers are from memory. The fishtest
  mathematics page and its linked Van den Bergh documents were confirmed by
  fetching the page on 2026-11-07; the PDFs themselves were not opened.
- **"No engine project uses factorial screens / node-odds screens"**: I have
  not surveyed this; NOVEL is claimed only for Fork's process.


---

# B9. Systems and hardware (H)

## B-H: systems and hardware (Phase 4 think tank, Phase B)

## 1. Summary

Fork's speed has been measured in a single place: native AVX-512 clang on a
Ryzen 7600X3D with a 96 MB L3, a 16 MB Hash and one thread. It is accepted
by one rule: both A/B estimators must move by more than 3%. Those two facts
explain most of the speed record (A3 §1.3).

**The 3% rule throws away real Elo.** At ~1.5 Elo per 1% nps (A1 §4.1, A3
§1.4), it rejects every change worth less than about 4.5 Elo. Audit-1
already found two such changes (P-2 +2.4%, P-3 +2.3%).

**Three latency-bound candidates were judged in the wrong regime.** C2
(prefetch rows at make), C3 (earlier TT prefetch) and E1 (refresh cache)
lost in the one environment where memory latency is cheapest. My arithmetic
in §2 (H6) suggests the GitHub shards are TT-DRAM-bound. Six engine
processes on a 32 MB L3 already hold about 120 MB of hot data. TCEC is far
more so: a 256 GiB TT, about 1 MB of L3 per hardware thread, and dual-socket
NUMA.

**The TCEC binary is unmeasured and probably under-built.** update.sh's
default is clang-19, x86-64-v3, no PGO, and the output layer has no AVX-512
path at all. All of these fixes are free at TCEC and can be checked
bench-identically on the local Zen 4, which is the same core as TCEC's
Zen 4c.

My proposals, each with first-principles cycle arithmetic:

- **(H1) Build the TCEC binary properly**: x86-64-v4 + VNNI behind a safe
  launcher, C1 un-parked, PGO and the compiler chosen by measurement. Expect
  +4 to +18% nps at TCEC, about +5 to +15 TCEC Elo. Local data generation
  also gains +2-3.5%, because it already builds native.
- **(H2) A measurement stack that resolves 1% changes**:
  - cycles:u and instructions:u per bench node, as perf stat already gave
    for idea 40;
  - deterministic cachegrind counts with a TCEC-shaped cache;
  - an A/B workflow on the shard runners;
  - the missing counters.
- **(H3) A zero-row/zero-lane cost-calibration build.** It prices every
  input design by formula before any GPU time. The same build provides the
  throttle for §5.6 item 4.
- **(H4) Share the pawn-link pair enumeration between perspectives**:
  +2-3% nps.
- **(H5) Fuse the last ply's accumulator update with the output dot
  product.** This balances a load-bound loop against a multiply-bound one:
  +2-5% nps.
- **(H6) Overlap the child's accumulator update with the in-flight TT
  prefetch in quiescence** [NOVEL for Fork]. I predict it is negative
  locally and positive on the runners and at TCEC.
- **(H7) Copy the network weights (and history tables) into
  huge-page-backed memory.** The embedded net sits in file-backed .rodata,
  which transparent huge pages do not cover.
- **(H8) The threat-input budget.** Only a narrow int8 side lane, with
  incremental set-wise discovery, can reach 0.90x. Below about 0.86x the
  design is dead by arithmetic.
- **(H9) Phase 6 guardrails** on per-thread memory.

None needs SPRT time except H8. Everything except H8 is bench-identical.

| ID | Title | Expected Elo, LTC (range) | Effort (days) | Confidence | NOVEL? |
|---|---|---|---|---|---|
| H1 | TCEC build: v4+VNNI launcher, C1, PGO, compiler matrix | 0 on shards by construction; **TCEC +5 to +15**; datagen +2-3.5% throughput | 2-3 | medium | no |
| H5 | Fused last-ply update + SCReLU output (port balancing) | +3 to +7 (2-5% nps) | 2 | medium-low | no (fused kernels known; the port-balance argument is mine) |
| H4 | One link-pair enumeration per move for both perspectives | +3 to +4.5 (2-3% nps) | 1 | medium | no |
| H6 | Eager child update in quiescence to hide the TT miss | +3 to +7 on shards/TCEC (2-5% nps); about −1% locally | 2 | low-medium | **NOVEL** (for Fork; no public description known, UNVERIFIED) |
| H7 | Weights and history tables on huge pages (TLB) | +1.5 to +4 (1-3% nps; more at TCEC) | 0.5-1 | medium-low | no |
| H2 | Measurement stack: cycles/instructions rule, cachegrind TCEC geometry, runner A/B workflow, counters | enabler: unlocks sub-3% gains, est. +5 to +15 over Phase 4 | 2 | high (that it is needed) | partly (runner-regime A/B) |
| H3 | Zero-row/zero-lane cost calibration and throttle build | enabler (prices idea 41/46, runs §5.6 item 4) | 1-2 | high | extends Fork's identical-tree method |
| H8 | Threat side lane within 0.90x: cost budget and go/kill math | 0 to +15 (if it passes its gates) | 10-15 | low | builds on S1 §7.1.k |
| H9 | Phase 6 guardrails: per-thread memory budget, NUMA-ready weights | 0 now; avoids TCEC losses later | 0 (rules) | medium | no |

Conventions: **[read]** is from a file (cited). **[derived]** is my
arithmetic on read numbers. **[est]** is a reasoned estimate. Hardware
facts I know only from memory are marked UNVERIFIED. Speed converts to Elo
at 1.5 per 1% nps at STC and about 1.4 at LTC (XGR: R_LTC/R_STC ≈ 0.94,
A3 §1.4). At TCEC I discount this to 0.5-1.0 per 1% (UNVERIFIED: deeper
searches and higher draw rates lower the value of speed; the Stockfish
wiki's 2.1 → 1.43 from 10+0.1 to 60+0.6 shows the direction, S1 §5).

---

## 2. Proposals

### Common base: a cycle budget per node [derived]

- Profile, perf-log 2026-11-06, S512r2 before C4: about 278 ns per node at
  3.6 M bench nps.
- C4 gives +4%, so 267 ns.
- S512ppr2 runs at 0.895 of S512r2, so **≈ 298 ns ≈ 1,400 cycles per node**
  at an assumed 4.7 GHz (clock UNVERIFIED).

| Component | ns per node | Share | Note |
|---|---|---|---|
| Accumulator update (`advance_values`) | ≈ 48 + link rows ≈ 55-60 | ≈ 19% | profile 17.2% on S512r2; links add rows on pawn moves |
| Link pair search (`link_changes`) | ≈ 15-20 | ≈ 5-7% | idea 40: about 200 instructions per node; branch misses about 20% of the links' extra cycles |
| Output (`squared_sum`) | ≈ 40 | ≈ 13.5% | AVX2 path even on native |
| Refresh, glue (`sum_perspective`, `evaluate_with`, `column`) | ≈ 17 | ≈ 6% | |
| TT | ≈ 35 | ≈ 12% | `TtEntry::bound` 8.3% is the first read (L3 hit locally) |
| Ordering, movegen, search, make | ≈ 120 | ≈ 40% | |

Per evaluation, assuming about 0.8 evaluations per node (UNVERIFIED; H2
measures it), the output layer costs about 50 ns, about 235 cycles. The
first-principles minimum, computed in H1, is about 80 cycles. The gap
(about 150 cycles) is memory stalls and overhead. That gap matters for
every estimate below, so I give ranges that span "compute-bound" and
"stall-bound".

---

### H1. Build the TCEC binary on purpose: x86-64-v4 + VNNI behind a safe launcher, C1 un-parked, PGO and the compiler by measurement

**Mechanism.** update.sh's default (clang++-19 first, x86-64-v3, no PGO;
update.sh lines 13-20 [read]) produces a binary that:

- runs the AVX2 accumulator kernel on AVX-512 hardware;
- runs the AVX2 output kernel everywhere (there is no AVX-512 path for
  architectures 2-8: accumulator.cpp `squared_sum` is `#if __AVX2__` only;
  C1 is parked on archive/sprint-candidates);
- never uses the profile-guided layout that data generation already uses
  (cmake/pgo.cmake, the generation's "fresh PGO build").

The proposal:

1. **ISA.** update.sh detects `avx512bw` and `avx512_vnni` in
   /proc/cpuinfo. It then builds x86-64-v4 plus `-mavx512vnni` (the
   existing `FORK_VNNI` option), and otherwise builds v3. `FORK_ARCH` still
   overrides.
2. **Safety.** The KB says TCEC "may build on one server and run on
   another". So update.sh builds both a v3 and a v4 binary and prints the
   path of a three-line POSIX `sh` launcher. The launcher `exec`s the v4
   binary if `/proc/cpuinfo` has the flags and the v3 binary otherwise. A
   `exec`ed engine is UCI-transparent. A cheaper alternative is a startup
   check in `main`: `__builtin_cpu_supports` on the compiled features,
   failing loudly at `uci` instead of with SIGILL mid-game. This is
   not runtime dispatch in a hot path, so it is within .claude/rules/simd.md.
3. **C1**: the AVX-512 output layer, four independent int32 sums, with
   `vpdpwssd` where VNNI is compiled. It is already written.
4. **PGO by default** in update.sh, driven by `fork bench`, with a silent
   fallback to the plain build if any PGO step fails. The pgo target
   already exists.
5. **Compiler and tuning by measurement.** Build all four TCEC compilers ×
   {v3, v4+VNNI} × {no PGO, PGO}, plus `-mtune=znver4` (or `znver3` where
   the compiler lacks it), all bench-identical, and A/B them on the local
   Zen 4. Make the fastest legal combination update.sh's default.

**Math [derived; µarchitecture facts from memory, UNVERIFIED].** For the
output layer at H = 512 (both halves, 1,024 lanes):

- AVX2: 64 iterations of {2 loads, max, min, mullo, madd, add}, so
  448 µops.
- Zen 4 resources:
  - 4 vector ALU pipes;
  - 2 of them able to multiply (UNVERIFIED);
  - 2 × 256-bit loads per cycle;
  - 6-wide dispatch;
  - 512-bit ops run as two 256-bit halves ("double-pumped": half the
    µops, the same pipe-cycles; KB design-speed.md §3.3, UNVERIFIED).
- Per-iteration bounds for AVX2: ALU 5/4 = 1.25 cycles; multiply 2/2 = 1;
  loads 2/2 = 1; dispatch 7/6 = 1.17. So about **80 cycles**,
  ALU-bound.
- AVX-512 + VNNI: 32 iterations of {2 loads, max, min, mullo, dpwssd}, so
  192 µops. ALU: 4 ops × 2 halves / 4 pipes = 2 cycles per iteration, so
  64. Multiply: 2 × 2 / 2 = 2, so 64. Loads: 64 cycles. So about **64
  cycles**: −20% of the compute-bound part, and −57% of front-end µops.
- If the measured 235 cycles per evaluation is roughly 80 compute + 155
  stall, C1 saves 16-35 cycles per evaluation. At 0.8 evaluations per node
  that is 13-28 of 1,400 cycles, **+1-2%**. If the AVX2 kernel is partly
  front-end-limited (448 µops share dispatch with the surrounding code),
  the saving approaches 30-40% of the layer: **+3-4%**. Range **+1.5 to
  +3.5% nps**.
- **VNNI needs several accumulators.** `vpdpwssd` carries the sum through
  a 4-5 cycle latency (UNVERIFIED), so a single accumulator would make the
  loop latency-bound at 32 × 4 = 128 cycles, slower than AVX2's 80. C1's
  "four independent sums" is exactly right. Keep it in any rewrite.
- **The accumulator update on v4** (the native profile already used it,
  so its share on the shard and TCEC builds is at least the local 19%).
  Per perspective, a quiet move:
  - AVX2: 32 × {3 loads, 2 add/sub, 1 store} = 192 µops;
  - AVX-512: 96 µops;
  - bytes either way: 3 KB loaded and 1 KB stored;
  - at 64 B/cycle loads and 32 B/cycle stores (UNVERIFIED), the floor is
    48 cycles, bandwidth-bound in both.
  
  Gain 0-10% of update time, so **+0-2% nps**.
- **PGO**: no Fork log measures it [read: grep of DESIGN, the perf logs,
  ideas]. About 50% of node time is branchy scalar code (ordering, TT,
  movegen, search). My estimate is **+2-8%** (UNVERIFIED; measure).
- **Compiler and tune**: unknown, ±5%. Audit-1 P-1 found g++ 11.4 failing
  to inline `lmr_move_facts` where clang did [read: searcher.hpp comment].
  Compilers differ on this code.
- **Total: +4 to +18% nps at TCEC, central about +9%.**

**Theory and literature.** Intel and AMD ISA documentation for
VPDPWSSD (instruction semantics). The double-pumped Zen 4 AVX-512 claim is
from memory, as in KB design-speed.md §3.3, UNVERIFIED. The source to read
is AMD's *Software Optimization Guide for AMD Family 19h* (Zen 4), which
also settles the open question 8 in KB competition.md about VNNI on EPYC
9754. PGO and LTO are standard compiler practice (GCC and LLVM manuals).

**Why Fork.** A3 §1.6:
- the SPRT binary (g++ v3), the speed-gate binary (clang native) and the
  TCEC binary (clang-19 v3) are three different builds;
- the parking reason for C1 ("the shards build v3") does not apply to the
  TCEC build, nor to data generation, which builds native (cmake/pgo.cmake
  `ARCH native` default [read]).

C1 therefore speeds up data generation today. Generation is node-limited,
so +2-3.5% nps is +2-3.5% positions per CPU-hour at unchanged label
quality.

**Prediction.**
- On the local Zen 4, in the update.sh build, C1 + v4 gives **+3 to +6%**
  over v3 (identical tree).
- PGO adds **+2 to +8%**.
- The best combination is not clang-19 v3 no-PGO; I expect a v4 PGO build
  to lead by ≥ 6%.
- Refuted if v4+C1 is < +1.5% over v3, or if PGO is < +1% on every
  compiler. Then update.sh stays as it is, apart from whichever axis
  passes.

**Speed cost; data and compute.** None at runtime. About 2-3 hours of a
quiet local machine (16 builds × 10 interleaved rounds; data generation
paused, the owner's call). No GitHub, no Kaggle.

**Cheapest first experiment.**
- (a) Read the AMD optimization guide or Zen 4 ISA documentation, and dump
  `/proc/cpuinfo` flags from a CI job that lands on an EPYC 9V74 (Zen 4;
  A3 §2.1 lists them among the runners). That confirms Zen 4 server parts
  report `avx512_vnni`. That Zen 4c is ISA-identical to Zen 4 is a claim
  from memory, UNVERIFIED.
- (b) Run `bench/ab_search.py` on clang-19 v3 against clang-19 v4+VNNI+C1,
  both via update.sh, 10 rounds. One hour.

**Kill criterion.** Axis by axis: any axis below +1% in cycles per node
(H2's rule) or below the harness rule is dropped. The launcher is dropped
if the owner prefers the startup check.

**Originality notes.** C1 is Fork's own code. "Several accumulators to
hide FMA latency" is textbook loop optimisation. No engine constants are
involved.

**Effort and dependencies.** 2-3 days including the matrix. It resolves
ideas 20 and 21 (BOLT stays parked: llvm-bolt and LBR sampling are unlikely
on TCEC's build host, UNVERIFIED). It touches §5.6 "Speed" (C1 parked) and
should run before the final gauntlet, which should play the TCEC build.
The questionnaire and update.sh documentation must say which binary TCEC
runs.

---

### H2. A measurement stack that resolves 1% changes, in the regimes that matter

**Mechanism.** Five pieces:

1. **Cycles and instructions per bench node** as the primary local metric.
   - Run `perf stat -e cycles:u,instructions:u` over the A/B harness's
     interleaved bench runs (same nodes by construction).
   - perf stat already works in Fork's WSL: idea 40's log reports "the pair
     search about 200 [instructions] per node" and branch misses [read].
   - cycles:u removes the clock-boost and thermal variance that wall-clock
     nps carries on the X3D. Instructions:u is nearly deterministic.
   - Proposed acceptance rule: a bench-identical change is kept when
     cycles per node improve by ≥ 1.0%, with a 95% interval excluding 0
     over ≥ 10 interleaved rounds, and the wall-clock estimators do not
     regress.
2. **Deterministic counts with cachegrind** (valgrind) on the v3 build:
   - Fork already runs valgrind with x86-64-v3 builds [read:
     .claude/rules/testing.md];
   - use a reduced-depth bench;
   - run twice with different simulated last-level caches: `--LL` set to
     the local 96 MB, and to about 1 MB per thread (TCEC Zen 4c: 16 MB L3
     per 8-core CCX with SMT, UNVERIFIED);
   - this gives instruction counts that are identical run to run, and a
     **miss rate per bench node at TCEC geometry** that no local run can
     show.
3. **An A/B speed workflow on GitHub runners.**
   - Build A and B with update.sh exactly as sprt.yml does (g++, v3).
   - Run interleaved identical-tree benches on a matrix of 8 runners, also
     in a "loaded" mode of 3 concurrent benches (the shards' concurrency
     3).
   - Report the median ratio and the CPU model.
   - This is the regime whose nps enters every SPRT verdict and the R fit
     (A1 §4.2 hypothesis 1: S512+X's outlier may be a runner ratio of 0.70
     against 0.818 locally).
4. **The missing counters** (A3 §1.2; design-speed.md §3.4), in one
   FORK_SEARCH_STATS bench and one 20-game stats run:
   - evaluations per node;
   - TT-eval hits;
   - refreshes per 1,000 updates;
   - plies walked per evaluation;
   - rows per update by move kind;
   - pawn-move share and link rows per pawn move;
   - the quiescence share of evaluations;
   - TT cutoffs before the evaluation (needed by H6).
5. **A large-Hash regime bench** (local): Hash 16 MB against 4,096 MB with
   transparent huge pages, against 4,096 MB without them (4 KB pages,
   which over-emulates TLB pressure). Report nps, cycles and dTLB misses.
   This is A3 §1.7 item 2, refined with a TLB arm.

**Math [derived].**
- **The 3% rule's cost.** At 1.5 Elo per 1%, the rule's blind band is
  about 0-4.5 Elo per change. Phase 3 and 4 produced at least four
  sub-threshold "probably real" gains: P-2 +2.4%, P-3 +2.3% (both
  consistent across g++ and clang), E2 +1.0%, and the C4/E2 overlap.
  Over a phase, 4-6 such changes at +1.5-2.5% each sum to about +6-15%
  nps, **+9 to +22 Elo**, now invisible.
- **Noise floor.** The A/A noise is −0.4% median, −1.1% best (Phase 3 perf
  log [read]); run thresholds are 3.0-6.6%. Part of the run-to-run spread
  is clock variance, which cycles:u removes. The remainder is cache
  interference from data generation sharing the L3, which cycles do not
  remove; that keeps the "quiet machine" rule.
- I predict the cycles-per-node spread at about ⅓ of the wall-clock
  spread (UNVERIFIED), which makes a 1% threshold reachable at 10 rounds.
- **Why the runner regime differs, by footprint.**
  - Per engine: TT 16 MB + weights 1.41 MB + pair histories 2 × 1.18 MB
    (quiet_history.hpp: 768 × 768 int16 [read]) + stacks ≈ 20 MB.
  - Six processes on a 4-vCPU EPYC 7763 VM (3 searching at a time): about
    60-120 MB of hot data against one CCD's 32 MB L3, which other tenants
    may share (UNVERIFIED).
  - So most TT probes on the shards go to DRAM: about 90-120 ns, plus
    nested-paging costs on a TLB miss. Locally they are about 12-15 ns
    from the 96 MB L3.
  - **A3's "16 MB Hash L3-resident on every runner" is likely wrong for
    the loaded runner.**
  - Consistency check: B0 ran about 2.4 M nps in shard games against about
    4.6 M local bench (S512 local 3.6 M at 0.78 of B0) [derived], a 0.52x
    ratio. The clock (about 3.5 vs 4.7 GHz) explains only about 0.74x.
    The rest (about 0.7x) fits a memory-heavier regime (UNVERIFIED:
    in-game against bench nodes).

**Theory and literature.**
- Valgrind's cachegrind manual (simulated I1/D1/LL caches; deterministic
  counts).
- The Linux perf documentation.
- The fishtest wiki's "Speedups" page recommends instruction and cycle
  counts from perf stat (S1 §7.2 item 8; read by S1).
- Mytkowicz et al., "Producing wrong data without doing anything obviously
  wrong!" (ASPLOS 2009): layout and environment bias in speed A/B tests.
  Citation from memory, UNVERIFIED.

**Why Fork.**
- Every speed verdict so far is native-local (A3 §1.3 "Pattern").
- C2, C3 and E1 were latency-hiding ideas judged where latency is
  cheapest.
- The speed gate (0.895) and the R fit (A1 §4.1) both use local ratios.

**Prediction.**
- (a) The runner A/B of S512ppr2 against S512r2-with-zero-links gives
  **0.86-0.89** (AVX2 doubles the µops per extra link row; more misses on
  the 1.41 MB table). Refuted if ≥ 0.895.
- (b) cycles:u spread ≤ ½ of the wall-clock spread over 10 rounds.
- (c) Large-Hash 4 GB THP costs ≥ 5% nps against 16 MB, and the no-THP
  arm ≥ 10% (refuted if both < 3%; then TT-latency work waits for
  Phase 6).
- (d) The cachegrind LL miss rate per node at 1 MB LL is ≥ 5x the rate at
  96 MB.

**Speed cost; data and compute.** None at runtime.
- Local: about 3 hours spread over quiet windows.
- GitHub: one runner-A/B job, about 15 minutes. It must not run during an
  SPRT, because SPRTs run one GitHub job at a time.
- cachegrind runs about 50x slower, so use a depth-limited bench (minutes).

**Cheapest first experiment.** perf stat cycles:u alongside the existing
harness on one already-decided pair (C4 against its parent, known +4%).
Check that cycles see +4% with a smaller spread. 30 minutes.

**Kill criterion.**
- If cycles:u spread is not < 0.7x the wall-clock spread, keep the 3% rule
  and use only instructions:u as a tie-breaker.
- If the runner A/B spread exceeds 5% even with 8 runners × 10 rounds, keep
  it only for large effects (the speed gate).

**Originality notes.** Tools only.

**Effort and dependencies.** 2 days: perf wrapper, cachegrind script, CI
workflow, counters. It gates H4-H7 (all expected below or near 3%) and
improves §5.6 item 4 (R measured on runners) and the speed gate.

---

### H3. Zero-row and zero-lane cost calibration, and the throttle build

**Mechanism.** This generalises Fork's own identical-tree method (idea 40:
S512r2's weights with link weights zero, so bench is unchanged) into a
calibration build with three test-only knobs. Each keeps bench identical,
because the extra data is zero but is loaded at runtime and cannot be
elided:

1. **k zero rows per update per perspective**: k extra row pointers into
   an all-zero 1 KB row. This measures c_row, the cost of one extra
   full-width int16 row.
2. **A zero side lane of width w**: a second accumulator of w lanes,
   updated by k' zero rows per move, whose output weights are zero. It
   measures the cost of a narrow side accumulator (H8) without any
   training.
3. **Throttle**: the output layer evaluated m extra times behind a compiler
   barrier. This is A3 §1.5's proposal for §5.6 item 4. It gives an
   exactly-known nps ratio with an unchanged tree and time management.

Fitting time per node = T0 + k·c_row + c_lane(w) + m·c_out gives a cost
formula: any input design's nps ratio follows from its counted active rows
per move and its width, before any GPU time.

**Math [derived from the base table].**
- The update is about 19% of time for about 2.4 row-equivalents of weights
  per perspective per update, plus the source read and destination write
  (about 2 more row-equivalents of traffic).
- So one extra weight row per perspective per update is about 19% ×
  1/4.4 ≈ **4% of node time if rows cost the same as the L1-resident
  src/dst traffic, and 4-6% if rows come from L2/L3** (they do: the
  1.41 MB table exceeds the 1 MB L2).
- Cross-check against links:
  - pawn moves are about 25-30% of moves (UNVERIFIED);
  - about 2-3 link rows per perspective per pawn move at R = 1
    (UNVERIFIED);
  - that is 0.6-0.9 extra rows per update, 2.5-5% of time;
  - plus the pair search at about 200 instructions (≈ 65 cycles at IPC 3)
    and its branch misses (≈ 30 cycles), together ≈ 7%;
  - total 9.5-12%, against the measured 10.5% (0.895). Consistent.
- **What the gate allows.** 0.90x is +11.1% time per node, about 155
  cycles; 0.95x is about 74 (the idea-46 judge found 145/70 at 1,300
  cycles). Full-width int16 rows at about 60 cycles each (4.3% of 1,400)
  allow **at most about 2.5 extra rows per perspective per update** at
  0.90 with zero discovery cost. Threat inputs change 3-4x the piece
  features (KB nnue-inputs.md §1.5; S512cl measured 5.48 contact and link
  changes per move per perspective, ideas.md 41 [read]). **Full-width
  threat rows cannot pass the gate.** This is arithmetic, not opinion.
  H8 follows from it.

**Theory and literature.** Fork's identical-tree method (ideas.md 40).
"Throttled build" (A3 §1.5). Linear cost models of the kind in KB
design-speed.md §3.

**Why Fork.**
- §5.6 item 4 needs a throttle anyway (A3 §1.5: fixed Move Overhead biases
  time odds).
- Idea 46's attack-map pricing and S512cl's speed work need per-row
  prices.
- Every speed-gate decision so far was taken after training (S512+X,
  S512cl).

**Prediction.**
- c_row = 50-80 cycles per row per perspective on the local native build,
  and 15-30% more on the runner v3 build.
- c_lane(128, k' = 7 int16 zero rows) = 3-6% of node time.
- The linear model predicts S512+PP's 0.895 within ±0.02 from its counted
  rows plus the measured pair-search instructions. Refuted if off by more
  than 0.04; then rows are not the dominant term and the model is
  re-fitted with a discovery term.

**Speed cost; data and compute.** None (test-only flags). About 1 hour
local plus one runner-A/B job.

**Cheapest first experiment.** k ∈ {0, 1, 2, 4} zero rows, local and
runner. Half a day including the build flag.

**Kill criterion.** If time per node is not linear in k (R² < 0.9 over the
four points), report the raw numbers and price designs by direct
prototype only.

**Originality notes.** Fork's own method extended. No engine numbers.

**Effort and dependencies.** 1-2 days. It feeds §5.6 item 4 (the throttle
replaces 0.85x time odds) and item 6 (idea 46's pricing), and supersedes
S512cl's "speed work in order" (item 14) with a go/kill formula.

---

### H4. One link-pair enumeration per move, shared by both perspectives

**Mechanism.**
- `columns_for` runs per perspective. For architecture 8 it calls
  `link_changes(before, after, perspective, flip, ...)`, which enumerates
  the changed pawns' partner pairs twice (gone, came) for **each**
  perspective (accumulator.cpp lines 65-80, contacts.cpp lines 171-204
  [read]).
- The set of changed pairs is the same for both perspectives. Only the
  final index mapping differs (`key` and `slot_base` depend on the
  perspective and flip).
- Proposal: enumerate the changed pairs once per ply-delta, in a canonical
  perspective-free form. Map each to the two perspectives' row indices by
  one load each from a precomputed table indexed [perspective][flip]
  [canonical pair].
- Cache the canonical list in the FeatureStack entry, so the second
  perspective's walk reuses it. It is lazy, computed only when the ply is
  first evaluated, so nodes that are never evaluated pay nothing.

**Math [derived].**
- Links cost about 150 cycles per node in total (0.895 → +11.7% of about
  1,300 cycles).
- Pair search: about 200 instructions per node, about 65 cycles at IPC 3,
  plus branch misses (about 20% of the links' extra cycles, so about
  30 cycles; idea 40 [read]).
- Enumeration is about 60% of the search's instructions: `pop_lsb` loops,
  partner masks, the pool update. The index lookups are the other 40%
  [est].
- Sharing halves the enumeration: −60 instructions, about −20 cycles. Half
  the data-dependent loop exits mispredict half as often: about −15
  cycles.
- **≈ 35 of 1,400 cycles: +2.5% nps** (range +1.5 to +3.5%), about **+2 to
  +5 Elo at STC and LTC**, also at TCEC and in data generation.

**Theory and literature.** Common-subexpression hoisting; no outside
source needed.

**Why Fork.** Idea 40's speed log found that every win came from **fewer
instructions** (the tight pair pass +4.3%, R = 1) and every cache or
prefetch step lost [read]. This is the same kind of change. Fork's default
has carried the link cost since 2026-11-06.

**Prediction.** instructions:u per bench node −1.5% to −3%. cycles:u per
node −1.5% to −3.5%. Bench identical (14,626,377). Refuted if
instructions fall < 1%.

**Speed cost; data and compute.** It is a speed gain. About 2 KB more
static table. Bench-identical, so no SPRT. Needs H2's 1% rule to be
accepted, since the expected gain sits under the 3% rule.

**Cheapest first experiment.**
- First, a counter: how often both perspectives walk the same pawn-move
  ply in one `evaluate`. It should be near 100%, except across mirror
  crossings.
- Then the change, instructions:u and cycles:u, 10 rounds.

**Kill criterion.** cycles:u gain < 1%: revert.

**Originality notes.** Fork's own code. New identifiers go through the
name screen.

**Effort and dependencies.** About 1 day. Independent of everything else.

---

### H5. Fuse the last ply's accumulator update with the SCReLU output (port balancing)

**Mechanism.**
- At an evaluated node, `FeatureStack::evaluate` writes the last ply's two
  1 KB perspectives (`advance_values`), then `squared_sum` reloads both and
  computes Σ clamp(v)²·w.
- The two loops stress different resources:
  - the update is load- and store-bound: 3 loads, 2 add/sub and 1 store
    per chunk;
  - the output is ALU- and multiply-bound: 2 loads, 5 ALU ops per chunk,
    2 of them multiplies.
- A fused last-ply kernel computes each new chunk, stores it (children
  still need it), and folds it into the output sum while it is still in a
  register. Each perspective's half uses its stm or ntm weight half.
- Earlier plies of a lazy walk keep the plain update. A perspective
  already computed (a mirror refresh) uses the plain output for its half.

**Math [derived; same UNVERIFIED Zen 4 resources as H1].**

| AVX2, per 16-lane chunk | Loads | ALU | Multiply | Store | Cycles (2 loads, 4 ALU, 2 mul, 1 store per cycle) |
|---|---|---|---|---|---|
| Update alone (quiet move) | 3 | 2 | 0 | 1 | 1.5 (load-bound) |
| Output alone | 2 | 5 | 2 | 0 | 1.25 (ALU-bound) |
| Separate, sum | 5 | 7 | 2 | 1 | **2.75** |
| Fused (the accumulator reload disappears) | 4 | 7 | 2 | 1 | **2.0** (loads 2.0, ALU 1.75) |

- That is −27% on the compute-bound part of the last-ply update plus the
  output. Those two together are about (19% × about 0.8 that is the last
  ply) + 13.5% ≈ 29% of node time [est].
- If half of that is compute-bound, the saving is 0.27 × 0.145 ≈ 4%. If a
  quarter is, 2%. **+2 to +5% nps**, about **+3 to +7 Elo**. The gain
  scales with AVX2's narrower register file, so it applies to the shards
  and to the TCEC build without v4.
- A3 §1.7 item 6 estimated +1-2% from the saved reload alone. The larger
  number comes from letting load-bound and ALU-bound work share cycles,
  which two sequential loops cannot do: the out-of-order window, 320
  entries on Zen 4 (UNVERIFIED), covers only about 40 chunks of one loop.

**Theory and literature.** Loop fusion for port balance (standard compiler
and HPC practice). KB nnue-design.md §2.2 notes "fused updates" for
multi-row updates. Fusing the update into the forward pass is my
extension; no public description was consulted.

**Why Fork.**
- Single-layer net: the output is one dot product over exactly the values
  just written. Deeper heads would make this harder.
- 32% of node time is in these two functions [read].
- E4 (both perspectives in one pass) lost −0.6% because AVX2's 16
  registers cannot hold both. This fusion needs only about 5 live
  registers per chunk.

**Prediction.** cycles:u per node −2% to −5% on the v3 build. Bench
identical. Refuted if < 1% on v3; then it is the stall part, not compute,
that dominates the network, and H7 and H6 become the network's levers.

**Speed cost; data and compute.** It is a speed gain. More code: one fused
kernel with a scalar reference and an equivalence test per simd.md. That
is a maintenance cost to report to the owner (DESIGN.md §7).

**Cheapest first experiment.** A fork_micro kernel benchmark first: an
update plus output pair against the fused kernel, on random accumulators,
v3 and v4 builds (an hour). Then the engine A/B.

**Kill criterion.** < 1% cycles:u in the engine A/B (or < 3% under the
current rule), or a micro gain < 10% of the two kernels' time.

**Originality notes.** Fork's own. Names screened.

**Effort and dependencies.** About 2 days. Compatible with C1 (H1): with
AVX-512 the fused kernel holds a whole perspective in 16 zmm registers
(KB design-speed.md §3.3).

---

### H6. Overlap the child's accumulator update with the in-flight TT prefetch [NOVEL]

**Mechanism.**
- Today the child's TT bucket is prefetched just before make
  (`tt_.prefetch_bucket(pos.predicted_key(m))`, searcher.cpp 589).
- The child (quiescence) then does a few cheap checks and **reads** the
  bucket: a demand load that blocks retirement until the line arrives.
- Only then, if it does not cut off and has no TT eval, does it run the
  accumulator update and the output.
- Prefetches retire at once; demand loads do not. So any independent work
  placed **between** the prefetch and the first read hides latency, and
  the update is exactly such work.
- Proposal (quiescence first): at entry to a non-check quiescence node,
  run the child's accumulator update eagerly (the update part of
  `FeatureStack::evaluate`, not the output), then read the TT.
- Nodes that then cut off or reuse the TT eval have wasted the update.
- This is a pure ordering change with the same tree and the same bench.

**Math [derived; latencies UNVERIFIED].**
- Lead time today: make + repetition/insufficient-material/fifty checks +
  PV reset ≈ 50-100 cycles (≈ 10-20 ns).
- Lead time added: one ply update ≈ 150-250 cycles (≈ 30-55 ns).
- Locally (L3 hit about 12-15 ns), today's lead already hides most of it.
  The eager update is mostly **waste** at the nodes that would not have
  updated: the TT-cut and TT-eval share f, unmeasured, say 15-25%. Cost
  f × 55 ns ≈ 8-14 ns per quiescence node, **−1 to −2% nps locally**.
- On a runner (DRAM about 100 ns, H2):
  - unhidden stall today ≈ 80-90 ns per miss;
  - the update hides another 30-55 ns;
  - with a miss rate of about 0.6-0.8 and the waste above, the net is
    ≈ 15-30 ns per quiescence node;
  - the quiescence share of nodes is about 0.5-0.7 (UNVERIFIED; H2
    measures it);
  - at about 400 ns per node on runners, **+2 to +5% nps**.
- At TCEC (DRAM, NUMA remote half the time, 256 GiB under TLB pressure;
  per-probe latency plausibly 120-200 ns): the hidden part is capped at
  the update's 30-55 ns, so the same or a little more.
- Why the out-of-order core does not already do this: after the blocking
  TT read, the window (about 320 µops) fills in about 80 cycles. The
  update (about 400-800 µops) does not fit. A software reorder places it
  before the blocking load.

**Theory and literature.**
- Software prefetching and "prefetch distance" (Mowry, Lam and Gupta,
  ASPLOS 1992, from memory, UNVERIFIED).
- The ROB-blocking argument is standard out-of-order microarchitecture
  (Hennessy and Patterson).
- I know no public description of reordering an NNUE update ahead of the
  TT read (UNVERIFIED; hence NOVEL for Fork, low confidence that it is
  new anywhere).

**Why Fork.**
- C3 (earlier TT prefetch) lost −0.8% locally, which is exactly the local
  prediction above.
- A3 §1.3 notes that the TT stall "varied 5-45 ns per node between
  repeated runs": evidence that local TT latency is mostly hidden, and
  noisy.
- Fork's lazy FeatureStack makes "update now or later" a two-line change
  in the call order.

**Prediction.**
- Local quiet A/B: **−2% to +1%**.
- Local Hash 4 GB without THP (H2 item 5): **+2 to +5%**.
- Runner A/B (H2 item 3): **+2 to +5%**.
- Refuted if the runner A/B is < +1% while H2's large-Hash arm shows a TT
  penalty ≥ 5%. Then hardware already hides it and the idea dies.

**Speed cost; data and compute.** Local cost as above. One runner-A/B job.
H2's counters for f and the quiescence share come first.

**Cheapest first experiment.** H2's counters (f, the quiescence share),
then the reorder behind a build flag, measured in the three regimes. About
1 day.

**Kill criterion.** Runner A/B < +1%: drop. If the runner shows > +2% but
local < 0: one build must serve both, so **adopt on the runner and
large-Hash evidence**. That needs the owner's sign-off on measuring speed
in the regime that plays (a methodology change).

**Originality notes.** Fork's own idea, as far as I know. Credit the
prefetch literature.

**Effort and dependencies.** 1-2 days after H2. It extends to negamax
nodes only if quiescence pays, because negamax has more TT cutoffs and so
more waste.

---

### H7. Network weights and history tables on huge pages (TLB reach)

**Mechanism.**
- The Hash already uses a 2 MiB-aligned block with `madvise(MADV_HUGEPAGE)`
  (hash_memory.cpp [read]).
- The **network is embedded in the binary** (embedded_net.cpp), so its
  1.41 MB of rows sit in file-backed .rodata on 4 KB pages. Transparent
  huge pages do not back file mappings by default. TCEC's "Large pages:
  enabled automatically" (KB competition.md) does not help them
  (UNVERIFIED: depends on CONFIG_READ_ONLY_THP_FOR_FS, normally off).
- The two 1.18 MB pair-history tables live inside the Searcher object.
- Proposal: at startup, copy the weights into an anonymous 2 MiB-aligned
  `madvise(MADV_HUGEPAGE)` block (reuse the HashMemory allocator), and do
  the same for the Searcher's history tables. On Windows, keep the current
  path, since large pages need a privilege.

**Math [derived; TLB sizes from memory, UNVERIFIED].**
- Hot 4 KB pages: weights about 345; pair tables about 577; stacks and
  frames about 40; code about 100+.
- Zen 4's L1 DTLB has about 72 entries and its L2 DTLB about 3,072
  (UNVERIFIED).
- Each update touches 4-8 row pages and each quiet scoring touches 2
  history rows, so about 8-12 L1-DTLB misses per node. At about 7 cycles
  per L2-TLB hit, partly overlapped, that is about 30-80 of 1,400 cycles:
  **+1-3% locally** if the copy removes them.
- At TCEC the TT's random probes over 131,072 huge pages (256 GiB / 2 MiB)
  sweep the L2 DTLB, evicting the 4 KB entries. The weight and history
  accesses then pay page walks: 4 levels, partly cached, about 20-40
  cycles. That makes the gain larger there: **+2-5% (UNVERIFIED)**.

**Theory and literature.**
- Linux kernel documentation, transparent hugepage (admin-guide/mm/
  transhuge), and KB os-memory.md §3.
- TLB reach is standard (Hennessy and Patterson).

**Why Fork.**
- C2 (prefetch rows) lost.
- The cost of row access may partly be translation, not data. Prefetches
  do not walk the page table early on every CPU (UNVERIFIED for Zen 4).
- Fork already owns the allocator and its fallback.

**Prediction.**
- Local 16 MB Hash: cycles:u −0.5% to −3%.
- Local 4 GB-THP Hash (H2 item 5): −1.5% to −4%.
- dTLB load misses per node fall ≥ 50% (`perf stat -e dTLB-load-misses`,
  if WSL exposes it, UNVERIFIED).
- Refuted if dTLB misses fall but cycles do not move. Then translation was
  hidden, and the idea is dropped.

**Speed cost; data and compute.** About 1.4 MB + 2.4 MB of extra resident
memory per process; trivial. 1 hour of local A/B.

**Cheapest first experiment.** `perf stat -e dTLB-load-misses,
dTLB-loads` on bench as it stands. If L1 DTLB misses are < 2 per node,
skip the change.

**Kill criterion.** < 1% cycles in both the 16 MB and the 4 GB regime.

**Originality notes.** Standard OS practice.

**Effort and dependencies.** 0.5-1 day. Idea 19 (MAP_HUGETLB or 1 GiB
pages for the TT) stays Phase 6, pending TCEC's answer on a hugetlbfs pool
(KB competition.md question 7).

---

### H8. Threat inputs within 0.90x: the cost budget and the go/kill math

**Mechanism.** I take S1's narrow threat side-accumulator (S1 §7.1.k)
and make it buildable within the gate:

- (a) A side lane of width w ∈ {64, 128} (a placeholder to measure), fed
  only by threat rows and concatenated into the output (SCReLU over 2·w
  more lanes, a 8 × (2·512 + 2·w) output).
- (b) **int8 threat rows widened to int16** on add (only the new rows;
  piece rows unchanged). S512cl's data shows trained weights fit int8 for
  98-99% of entries at scale 255 (ideas.md 41 [read]), so clipping-aware
  training (`--qat`, idea 44) is needed.
- (c) **Incremental set-wise discovery at make-move**: threat deltas from
  the moved piece, the captured piece and the sliders whose rays pass
  through the from or to squares, computed from attack-bitboard
  differences. Recomputation is S512cl's 82% (ideas.md 41).
- (d) **A reduced feature class** in the first version: threats by a
  lower-valued attacker and attacks on undefended pieces. That is
  S512+X's and XGR's exposure concept, worth +25.7 FN, now as pairs in a
  side lane rather than full-width rows.

**Math [derived; H3 calibrates every term].** Extra time per node:
rows + output + discovery.

- **Rows.** An int8 row of w = 128 is 128 B = 2 cache lines, against 16
  lines for a 512-wide int16 row. AVX2 needs 8 chunks of {load, widen,
  add}, about 24 µops, against 96 for a full-width row.
  - At about 7 changed threat features per perspective per move (3-4x the
    piece changes; S512cl: 4.2 contacts per move per perspective):
    7 × 24 × 2 = 336 µops, close to a whole quiet update's 384 µops.
  - In bandwidth: 7 × 2 × 2 = 28 lines against the update's about 96, so
    +29%.
  - So **+4% (bandwidth-bound) to +10% (µop-bound)** of node time at
    w = 128; **+2-5%** at w = 64.
- **Output.** +2w/1,024 of the output layer: w = 128 gives +25% × 13.5% =
  **+3.4%**; w = 64 gives +1.7%.
- **Discovery.** The idea-46 judge put full exposure finding at about 150
  cycles (≈ 11%) [read]. Incremental, ray-local discovery should be about
  ⅓-½ of that: **+3.5-5.5%** [est, UNVERIFIED]. Its cost moves to make
  (paid at every node, not only at evaluated ones), so multiply by about
  1/0.8: +4.5-7%.
- **Totals.**
  - w = 128: 4-10 + 3.4 + 4.5-7 = **12-20% → 0.83-0.89x**: fails the gate
    at the central estimate.
  - w = 64: 2-5 + 1.7 + 4.5-7 = **8-14% → 0.88-0.93x**: borderline.
- **Discovery dominates.** The design lives or dies on making discovery
  cost ≤ about 40 cycles per node, in line with idea 46's attack-map
  pricing rule (≤ 60 cycles keeps the designs alive). Discovery could
  share work with move generation. The idea-46 judge warned that most
  evaluations are at quiescence stand-pat, where quiet ordering does not
  run, so sharing saves less than it seems.
- **Elo.** At 0.90x the gate costs about 16 Elo (A3 §1.4, 1). A side lane
  keeping XGR/S512+X's FN +25-31 would net about **+9 to +15** at STC. At
  0.93x, +14 to +20. The FN gain of a w = 64 lane is unknown and could be
  well below the full-width +26 (UNVERIFIED). Net range **0 to +15**.

**Theory and literature.**
- KB nnue-inputs.md §1.4-1.6 (threat inputs; incremental updates).
- S2 §5.3: adopters accepted about 0.85-0.9x after months of speed work;
  int8 threat rows; set-wise generation.
- S1 §2: a separate accumulator with its own refresh rule; i8 storage.
- No engine constants used.

**Why Fork.** A3 and A1: every input recomputed per evaluation failed
(S512+X, XGR, S512cl), and the incremental links passed. A1 §3.5 argues
threat knowledge is "search-resolvable", so its FN gain may shrink with
depth. SF's threat gain grew with TC (S1 §2, +2.0/+3.8/+7.0), which is
evidence the other way, for a different engine.

**Prediction.**
- H3's zero-lane prototype (w = 64, 7 zero int8 rows per perspective,
  zero output weights, bench identical) measures **0.93-0.96x without
  discovery**. Adding the discovery code (also bench-identical: compute
  the deltas, feed zero rows) gives **0.88-0.92x**.
- Refuted (design killed) if the runner-build ratio is < 0.88 with
  discovery. At 0.88 the gate cost is about 19-20 Elo, more than the
  likely FN gain of a narrow lane.

**Speed cost; data and compute.**
- Speed: as computed.
- Data: the existing g3s2 plus the newer parts.
- Training: one Kaggle session for warm-started side lanes, with zero-init
  lane weights so the parent is reproduced.
- Testing: FN screen, then STC SPRT [0, 5].

**Cheapest first experiment.** The H3 zero-lane prototype with the real
discovery code, measured on the runner build. No training. 3-4 days of
build, then 1 hour of measurement.

**Kill criterion.** Ratio < 0.88 on the runner build, or FN < 16 + 5 =
+21 at 0.90 (A1 §4.4: FN must exceed 152·ln(1/r) + 5).

**Originality notes.** Credit S1's side-lane proposal, the KB's threat
concepts and set-wise generation as public concepts. Fork's own indexing
and deduplication (idea 41). No widths from any engine: 64 and 128 are
placeholders chosen to make the cost arithmetic concrete.

**Effort and dependencies.** 10-15 days in total. It replaces §5.6 item
14's "S512cl speed work" (full-width incremental contacts, which by the H3
arithmetic cannot pass: 5.5 rows × 4-6% ≈ 22-33% before discovery) and
competes with idea 46 ranks 2-5. H3 comes first.

---

### H9. Phase 6 guardrails for Phase 4 choices (comment only)

SMP is Phase 6. These Phase 4 choices change how hard it will be.

- **The per-thread hot set against TCEC's cache per thread [derived;
  TCEC cache geometry UNVERIFIED].**
  - EPYC 9754 (Zen 4c): 1 MB L2 per core shared by 2 SMT threads; 16 MB L3
    per 8-core CCX (16 threads). So about **0.5 MB L2 + 1 MB L3 per
    thread**.
  - Fork's per-thread tables today: pair histories 2.36 MB, butterfly
    16 KB, take 9 KB. Allocated stacks are FeatureStack about 0.53 MB and
    PlyFrames ≤ 0.67 MB, of which only the plies reached are touched.
  - Shared: weights 1.41 MB (one copy per CCX in L3, but duplicated per
    L2).
  - So per-thread tables already exceed a thread's L3 share. History
    reads that are L3 hits locally will be DRAM reads at TCEC.
  - **Rule for Phase 4:** no new per-thread table above about 256 KB
    without a TCEC-footprint note. That covers deeper continuation
    histories (+1.18 MB each at the current indexing), threat-split
    histories, refresh caches, and per-thread correction tables (size them
    ≤ 64-128 KB, or design them shareable; S2 §4 item 10 reports large
    multi-thread gains from shared correction tables).
- **Weight tables: keep them ≤ about 4 MB.**
  - S512cl's 53.9 MB table (ideas.md 41) fits only the X3D's 96 MB L3. At
    TCEC (16 MB per CCX, shared with every thread's TT, history and stack
    traffic) every row would be a DRAM access, about 100+ ns, about 4
    rows per update.
  - That is fatal regardless of SMP. The rule kills the full-width S512cl
    on hardware grounds alone.
- **NUMA.**
  - The weights should be replicated per socket in Phase 6. Keep the
    weight pointer an indirection (NetFile already is), so a per-node copy
    needs no Phase 4 change.
  - H7's copy-to-huge-pages is the natural place to allocate per node
    later.
- **TT.**
  - Self-verifying 12-byte entries are already designed for torn writes
    (trans_table.hpp [read]).
  - At TCEC, about 46 G nodes per move (512 threads × about 1.5 M nps ×
    60 s, est) against about 21 G entries at 256 GiB. **The TT fills
    within a move or two even at 256 GiB**, so ideas 24 and 30
    (replacement under pressure) are real Phase 6 work.
  - Hash initialisation must stay multithreaded, or TCEC caps the Hash
    at 32 or 64 GiB (KB competition.md item 3).
- **Lazy accumulators are SMP-friendly.** They are per-thread, no sharing,
  and Lazy SMP's shared TT raises TT-eval hits (KB nnue-design.md §2.5).
  Nothing to change.
- **Measurement.** Phase 6 needs H2's runner workflow plus a local
  12-thread bench. Building the runner A/B now amortises.

---

## 3. Critique of the current plan in my domain

1. **§5.6 "Speed": un-park C1 now** (H1).
   - The reason given ("shards build v3, so it would never run there")
     ignores data generation, which builds native with PGO and runs C1's
     path every node, and the TCEC build.
   - C1 is bench-identical, already written, and needs one hour of A/B.
2. **Item 4 (speed-to-Elo): run it as a throttle build, at 0.5x, on
   runners** (A3 §1.5; H3 supplies the throttle).
   - 0.85x time odds carries the Move Overhead bias (100 ms overhead
     against an 80 ms increment) and a ±26% error on R.
   - Add one LTC stage.
   - Also measure the throttle build's nps ratio **on the runner** (H2):
     R must be fitted with ratios from the regime that plays.
3. **The speed gate's ratio must come from the shard build, measured on a
   runner** (H2).
   - The 0.895 for S512+PP is native AVX-512 with a 96 MB L3.
   - I predict 0.86-0.89 on runners.
   - If confirmed, the R fit (A1, A3) is slightly biased: S512+X's
     outlier moves toward the line (A1 §4.2 hypothesis 1).
   - Cost: about 15 minutes of one GitHub job.
4. **Replace the 3% acceptance rule with a cycles-per-node rule at 1%**
   (H2).
   - Expected value: about +9-22 Elo over the phase from changes now
     discarded.
   - This changes DESIGN.md §7's "measured gain", so it is the owner's
     call.
5. **Re-judge C2, C3 and E1 in the shard and large-Hash regimes before
   closing them.**
   - Each lost by an amount within or near the noise rule (−2.9%, −0.8%,
     −5.3%) in the most latency-forgiving machine available.
   - E1 is the most likely to stay dead: refreshes are 2.5% of time and
     E1 adds a 1 KB copy per frame change.
   - C3 is the most likely to flip, because it targets DRAM latency.
   - Cost: one runner-A/B job each. The code is archived.
6. **S512cl's speed work (item 14): redesign or drop.**
   - Full-width incremental contacts cost about 5.5 rows × 4-6% ≈
     22-33% before discovery (H3 arithmetic), so they cannot reach 0.90x.
   - Its 54 MB table is DRAM-bound at TCEC (H9).
   - Replace the item with H8's side-lane prototype, or close it.
7. **Idea 46 rank 0 (attack-map pricing) becomes part of H3.**
   - Price "finding" in cycles per node in the engine (the zero-row
     method), not only in fork_micro. That keeps the cost in context
     (cache, branch history).
   - Its ≤ 60/120-cycle rule is consistent with H8's arithmetic: keep it.
8. **Eval avoidance has a low ceiling. Do not invest beyond counters.**
   - At non-PV, non-check nodes the static eval is consumed by RFP
     (depth ≤ 6), futility (≤ 6) and NMP (≥ 3), so every such node needs
     it (searcher.cpp lines 232-273 [read]).
   - Quiescence needs it for stand-pat.
   - Fork already reuses `hit.eval`, and evaluation is already lazy.
   - Window-dependent lazy evaluation is unsafe (idea-46 judge). The only
     safe remaining saving is at PV nodes, under 1% of nodes.
   - H2's counters will show evaluations at about 0.75-0.85 per node; I
     predict that rules out eval-skipping as a speed lever (refuted if
     < 0.6).
9. **Ideas 9 and 37 (layout) and idea 36 (SIMD pick).**
   - Idea 36 is done (E2 +1.0%, not kept): close it.
   - Ideas 9 and 37 had every candidate below 3%. Re-test only under H2's
     1% rule, and with Phase 6's multi-thread footprint (H9).
10. **Idea 21 (BOLT): drop from Phase 4.** It needs llvm-bolt and
    hardware branch sampling on TCEC's build host, and PGO (H1) takes most
    of the same layout gain.
11. **Ordering of speed work in §5.6.** H2 (half a day of its first
    piece) and H3 (1 day) should come **before** item 4 and item 6, which
    both consume their outputs. H1's local matrix fits any quiet window.
    H4, H5 and H7 are filler for quiet windows. None uses GitHub except
    H2's runner job.
12. **Data generation is a hidden beneficiary of every speed gain.**
    - At node-limited labels, +X% nps is +X% data per CPU-hour.
    - At A1's estimate of 10-20 Elo per doubling of data at today's scale,
      +5% data is +0.7-1.4 Elo per generation. Small but free, and it
      compounds.

---

## 4. What I could not verify

- **Zen 4 and Zen 4c microarchitecture.** All from memory: double-pumped
  512-bit execution; 4 vector ALU pipes with 2 multipliers; 2 × 256-bit
  loads per cycle; `vpdpwssd` latency; ROB about 320; L1 DTLB about 72
  and L2 DTLB about 3,072 entries; Zen 4c ISA identical to Zen 4
  including AVX-512 VNNI. EPYC 9754's 16 MB L3 per 8-core CCX is from
  memory too. Every cycle figure in H1, H5, H7 and H8 inherits this.
  AMD's Zen 4 optimization guide would settle it.
- **The 7600X3D's clock** under bench (4.7 GHz assumed). The KB records a
  4.1 GHz Windows-reported maximum. At 4.1 GHz the cycle budget per node is
  about 1,220, not 1,400; the percentages are unaffected.
- **Runner cache sharing**: whether a 4-vCPU VM shares its CCD's L3 with
  other tenants, and whether its vCPUs are SMT siblings. The "shards are
  TT-DRAM-bound" claim (H2, H6) rests on footprint arithmetic, not on a
  measurement.
- **Evaluations per node, the quiescence share, the TT-cut share before
  evaluation, plies walked, pawn-move share and links per pawn move.** No
  NNUE-era counter is logged; H2 item 4.
- **PGO's gain for Fork**: never measured. The +2-8% is an estimate.
- **Whether perf exposes dTLB events in WSL**: instructions and cycles
  evidently work (idea 40's log), but TLB events are UNVERIFIED.
- **Whether TCEC's kernel backs read-only file mappings with huge pages**
  (H7's premise that the embedded net sits on 4 KB pages at TCEC).
- **The Elo value of 1% nps at TCEC conditions** (single thread at 30'+3",
  or 512 threads later). My 0.5-1.0 discount is a direction from public
  time-odds data, not a measurement.
- **H6's novelty**: I know no public description, but did not search
  exhaustively.
- **H8's FN gain for a narrow lane**: unknown. The +25-31 references are
  full-width exposure/XGR results.


---

# B10. Chess knowledge (C)

## B-chess (C): what Fork's network still lacks, measured from Fork's own games

**Summary.** Before proposing anything I mined Fork's existing games and data. No engine was run:
read-only python-chess scripts in `tank/b/scratch-c/` parsed 25,600 STC and 12,657 LTC S512r2
SPRT games, 4,800 S512ppr2 / S512+PP STC games, the 1,200-game gauntlet (S512r2 era, both
engines' evals in the PGN) and one g3 data shard (10,406 games of S512r2 labels). Five findings
change what "knowledge to add" means for Fork.

1. **Fork's eval is calibrated to its own 20k-node games, and the gap to stronger play grows
   with depth.** The same net (S512r2) and the same positions categories give different
   results at different depths. At a given searched eval, drawish endgames (pawns on one wing,
   ≤ 4 pawns, pure opposite-coloured bishops) convert **2 points less in the training data, 4.5-6
   points less at STC and 5.6-8 points less at LTC** than other endgames at the same eval. Some
   advantages convert more than their eval says, and that excess also grows (data → STC → LTC):
   the opponent's pawn islands −0.4 → +5.7 → +6.9; an open position +1.1 → +6.7 → +7.5.
   Fork's eval learned which advantages win under shallow play, and that knowledge drifts
   further from the truth as depth grows (TCEC is about 14 doublings deeper).
2. **Pawn links did not touch those residuals.** S512r2 and S512ppr2 have the same signs and
   sizes. Links (R = 1) encode contact; islands, one-wing structures and passers are defined by
   *absence* or by global counts, so links cannot see them.
3. **Against other engines, Fork loses in early middlegames with queens on and kings under
   attack, not in endgames.** Of 217 losses to the three strongest anchors:
   - in 36% the opponent's eval turned ≥ 6 plies before Fork's;
   - in 22% the opponent already rated the start ≤ −1 while Fork did not.

   At Fork's blind spots, "Fork's king zone hit by ≥ 3 pieces" is over-represented 2.5-4.8x
   against agreement positions, the opening phase 1.6-2.1x and queens on 1.3-1.5x. Endgames are
   *under*-represented (0.05-0.24x). About 30-45% of the blind spots are tactical (material
   falls ≥ 2 within 12 plies).
4. **Unconverted advantages grow with TC.** One side holds ≥ +1.00 for ≥ 20 of its moves and
   the game is drawn in 3.8% of STC games and 4.9% of LTC games. Rook endings with an extra
   pawn top the list.
5. **Simple event studies show no measurable decision loss at STC** (trade-downs, endgame pawn
   trades). That caps how much Elo I can promise for calibration fixes, and I say so below.

**The plan these findings support:** measure the gaps per net and against deeper labels
(C1, C2); test whether calibration matters with a zero-speed eval-side scale (C3); then give the
net king-relative pawn knowledge (C4) and depth-matched endgame outcomes (C5). Pawn-status
planes (C7) come last, and the acceptance test is extended as a guard (C6).

| ID | Title | Expected Elo at LTC (range) | Effort (days) | Confidence | NOVEL? |
|---|---|---|---|---|---|
| C1 | Knowledge-gap ledger per net plus a blind-spot suite verified by Fork's own deep search | enabler (decides C3-C7); 0 directly | 1-2 | high (as information) | partly (the suite) |
| C2 | Horizon study: deep against 20k-node labels, split by chess category | enabler / kill test for C4, C5, C7 and idea 46's family | 0.5 + about 1.5 CPU-h | high (as information) | NOVEL for Fork's process |
| C3 | Structure-class calibration scale on the eval (cached, no training) | +2 to +6 (STC +1 to +5) | 2-3 | low-medium | no (classical scale-factor idea, refit as calibration) |
| C4 | King-zone pawn links: own king square × pawns in its box, idea 40's L1 continued | +3 to +12 net of speed (STC +2 to +10) | 5-8 | low-medium | NOVEL (UNVERIFIED) |
| C5 | Depth-matched endgame-start slice (Fork self-play from 8-16-piece positions at 4x nodes) | +3 to +8 (STC +2 to +6) | 3-4 (about 10 h CPU, 1 Kaggle session) | low-medium | partly |
| C6 | Endgame acceptance test extended to 4-5-man signatures, plus a TB audit of unconverted advantages | guard (prevents regressions like KQK 0 → 59) | 1 | high (as a guard) | no |
| C7 | Pawn-status planes (passed / isolated / backward), the absence-defined concepts links cannot see | +1 to +8 net of speed | 4-6 | low | NOVEL for NNUE (UNVERIFIED) |

Conventions: **READ** = from a file (cited); **MEASURED** = my read-only script on Fork's own
PGNs/data, numbers below are its output; **COMPUTED** = my arithmetic; **INFERRED** = my
interpretation; **UNVERIFIED** = unsure. Residuals are in score points (percent of a game).
Speed is priced at the Phase A rate, **Elo cost = 152·ln(1/r)** (about 1.5 Elo per 1% nps;
A1 §4, A3 §1.4).

---

## 0. The evidence I measured (read-only; scripts in tank/b/scratch-c/)

### 0.1 Method

- `feat.py` defines the categories from python-chess boards. All are **from the leader's
  view**, the leader being the side the searched eval favours. Fork's own definitions:
  - phase by non-pawn material (N/B 3, R 5, Q 9): ≥ 44 is "open", 20-43 "mid", < 20 "end";
  - pawn-structure flags: passed pawns (no enemy pawn ahead on its own or adjacent files),
    islands, rams (blocked head-on), all pawns on one wing, ≤ 4 pawns;
  - king shelter: own pawns on the king's file ±1, 1-2 ranks ahead;
  - king-zone attackers: enemy N/B/R/Q attacking the king ring or the square in front;
  - material and imbalance flags (bishop pair, exchange, opposite-coloured bishops).
- `calib2.py` takes every second position with a searched eval in [50, 300) cp, folds it to the
  leader's view, and sets its game score against the mean of all positions in the same 50-cp
  band **and the same phase**. The mean residual per category is clustered by game for its
  standard error.
  - Sources: fastchess PGNs (`{+0.27/15 ...}` comments) and viriformat shards, whose score is
    white-relative, decoded as tools/datagen/verify_games.py does.
- `gauntlet.py` / `gauntlet_strong.py` find Fork's blind spots and compare them with control
  positions. A blind spot is the first Fork move of a lost game at which the opponent's next
  eval (turned to Fork's view) is ≤ −T while Fork's own is ≥ −25, with the opponent at ≤ −T/2 on
  3 of its next 4 moves. Controls are positions where both evals agree within 50 cp.
- `lossmap.py` sorts losses by who saw the loss first. `draws.py` and `fifty.py` cover
  unconverted advantages and fifty-move draws. `gtrade.py` and `ptrade.py` are the event
  studies. `gcal.py` is the gauntlet calibration with a baseline per (band, phase, opponent).

Data sets (READ paths, MEASURED counts):

| Set | Source | Games (with rows) | Positions in band |
|---|---|---|---|
| data | `~/fork-data/g3-full/g3-w03-0000.vf` (first 12,000 games; S512r2 labels, 20k nodes, split search 50% at 4k) | 10,406 | 132,561 |
| STC-r2 | `~/fork-data/sprt/probcut-d9r5m80-vs-base` + `threat-set-cheaper-vs-base` (S512r2 both sides) | 24,450 | 834,144 |
| LTC-r2 | `ltc-drift-vs-base` + `ltc-iir-on-vs-off` (S512r2, 40+0.4) | 12,657 | 448,528 |
| STC-ppr2 | `s512ppr2-stc` + `s512pp-r1-stc` (S512ppr2 / S512+PP / S512r2) | 4,618 | 152,345 |
| gauntlet | `~/fork-data/gauntlet/run-41465146207/gauntlet.pgn` (S512r2-era Fork, 10+0.1) | 531 (Fork's rows) | 13,797 |

### 0.2 E1. Conversion by phase at the same searched eval (MEASURED; score %, leader's view)

| Set | Phase | 50-99 cp | 100-149 | 150-199 | 200-249 |
|---|---|---|---|---|---|
| data (20k/4k-node play) | open / mid / end | 71.3 / 69.8 / 63.7 | 82.8 / 81.4 / 78.5 | 89.7 / 90.5 / 88.8 | 94.3 / 94.6 / 94.6 |
| STC-r2 | open / mid / end | 74.5 / 69.2 / 56.4 | 89.5 / 85.7 / 75.9 | 96.7 / 95.4 / 89.6 | 99.4 / 98.6 / 96.0 |
| LTC-r2 | open / mid / end | 75.0 / 67.1 / 56.0 | 91.1 / 84.7 / 75.0 | 97.6 / 95.2 / 86.3 | 99.5 / 97.6 / 94.0 |
| STC-ppr2 | open / mid / end | 75.9 / 70.5 / 59.7 | 90.1 / 86.7 / 78.5 | 98.3 / 96.1 / 94.4 | 99.6 / 99.3 / 97.3 |
| gauntlet (Fork's evals) | open / mid / end | 71.8 / 77.8 / 59.4 | 79.2 / 87.4 / 73.8 | 88.1 / 93.5 / 82.3 | 95.4 / 96.4 / 87.9 |

COMPUTED, the mid − end gap at 100-149 cp:
- data 2.9;
- STC-r2 9.8; LTC-r2 9.7;
- STC-ppr2 8.2;
- gauntlet 13.6.

All gauntlet opponents also convert endgame evals worse than middlegame ones (Altair 70.5 / 63.9,
Marvin 62.9 / 55.3, Laser 77.0 / 57.7; small samples). So a phase gap as such is common to
engine evals and is **not by itself a Fork defect**. What is Fork-specific is that its training
data has almost no gap while its play has a large one (INFERRED).

### 0.3 E2. Endgame categories, against the phase-matched baseline: the bias grows with depth (MEASURED)

Same net (S512r2) at three depths, plus S512ppr2. Residual in score points (z in brackets, game-clustered):

| Endgame category (leader's view) | data (20k) | STC-r2 | LTC-r2 | STC-ppr2 |
|---|---|---|---|---|
| all pawns on one wing | −2.25 (−2.2) | −5.93 (−16.0) | **−6.73** (−11.0) | −6.05 (−6.2) |
| ≤ 4 pawns on the board | −1.51 (−2.1) | −4.47 (−15.4) | **−5.58** (−12.7) | −4.13 (−5.0) |
| opposite bishops, nothing else | −2.11 (−0.9) | −5.76 (−5.3) | **−8.02** (−5.8) | −5.62 (−1.3) |
| rook ending (one rook each) | **+2.89** (+3.4) | −1.71 (−5.2) | −1.36 (−2.8) | −2.91 (−3.2) |
| leader up material | −0.50 (−1.0) | −1.11 (−4.6) | −0.98 (−2.7) | −1.18 (−2.0) |
| leader ahead with equal material | +2.21 (+2.6) | +5.34 (+14.1) | +3.63 (+6.7) | +5.04 (+5.1) |
| opponent has ≥ 3 pawn islands | −0.42 (−0.4) | +5.71 (+11.9) | **+6.90** (+11.7) | +4.63 (+4.1) |
| opponent has a passed pawn | +0.04 (+0.1) | +2.97 (+8.7) | **+4.28** (+9.3) | +2.61 (+3.4) |
| no rams, ≥ 8 pawns (open) | +1.06 (+1.2) | +6.71 (+12.4) | **+7.47** (+11.0) | +6.88 (+6.6) |
| leader has the bishop pair alone | −4.74 (−1.5) | +3.71 (+2.8) | +4.42 (+2.2) | +7.30 (+3.4) |

In the middlegame:
- ≤ 4 pawns: −1.95 (data), −6.77 (STC), −8.17 (LTC), −6.97 (ppr2);
- opposite bishops with pieces: −0.37, −2.30, −3.51, −2.81;
- the bishop pair: −0.82, +2.18, +2.91, +2.72.

**Reading (INFERRED).**
- The net overrates material-based leads in reduced, one-wing and opposite-bishop endings, and
  underrates leads that come from structure, activity and the bishop pair.
- The data sees little of this: its results come from 20k-node games in which half the moves
  are 4k-node moves (manifest g3.json: save_percent 50, unsaved_nodes 4000), and shallow
  defenders do not hold drawish endings or exploit weak pawns.
- Every column moves the same way from 20k → STC (~depth 15) → LTC (~depth 19).
- TCEC is about 14 doublings beyond STC (b-survey-tcec §0). Its decisive games are White
  converting biased exits, median 91 moves (same survey), which is exactly the region where these
  biases live.

**Caveat.** These are searched evals, not static evals, and the categories are correlational.
"Convert less than the eval says" can mean the eval is too high, or that the play is too weak to
realise it. In self-play both sides share the weakness, which makes the first reading more
likely for drawish classes (the defender holds) and the second for "islands" (the attacker
exploits). Both readings call for the same remedy: targets from deeper play.

### 0.4 E3. What pawn links changed (MEASURED)

S512r2 against S512ppr2 at STC: every endgame category in E2 keeps its sign, and the residuals
stay within about 1.5 points (islands +5.7 → +4.6, one wing −5.9 → −6.1, passer_opp +3.0 →
+2.6). The overall endgame conversion rose at 150-199 cp (89.6 → 94.4), so the links improved
the endgame eval's *level*. They did not fix the *structure-class* biases.

That fits the definition (net_shape.hpp: `link_squares`, same or adjacent file and at most
NetLinkRanks = 1 rank apart). Several concepts lie outside what such pairs can express:
- passers: no enemy pawn ahead, over up to 6 ranks;
- islands and isolated pawns: absence on neighbouring files;
- one-wing structures: a global property;
- backward pawns: a relation 2+ ranks apart.

KB nnue-inputs.md §2.3 makes the same point from the definitions.

Links' +32.7 STC (S512+PP, sprt-log) must therefore have come from ranking *within* categories,
which calibration cannot see (INFERRED).

### 0.5 E4. Where Fork loses to other engines (MEASURED, gauntlet run 41465146207)

Results (READ via the PGN): against Altair 38-52-110 (W-D-L), Marvin 69-68-63, Laser 124-32-44;
the three weaker anchors 489-54-57.

`lossmap.py`, the 217 losses to Altair, Marvin and Laser:

| How the loss happened | Games | Share |
|---|---|---|
| bad start, both engines ≤ −100 for Fork at the first move (unbalanced random 8-ply openings) | 77 | 35.5% |
| the opponent rated the start ≤ −100, Fork did not | 47 | 21.7% |
| the opponent's eval reached −100 ≥ 6 plies before Fork's | 78 | 35.9% |
| both within 6 plies | 14 | 6.5% |
| Fork saw it first | 1 | 0.5% |

Blind spots against agreement controls (`gauntlet_strong.py`, strong three only; lift = share in
blind spots / share in controls):

| T (cp) | blind spots | tactical | Fork's king zone hit by ≥ 3 | opp. king zone hit by ≥ 3 | opp. king weak shelter | opening phase | queens on | endgame |
|---|---|---|---|---|---|---|---|---|
| 75 | 70 | 21 (30%) | 3.69 (7) | 3.13 (5) | 1.62 | 2.07 | 1.52 | 0.05 |
| 100 | 59 | 23 (39%) | 2.50 (4) | 2.97 (4) | 1.81 | 1.84 | 1.37 | 0.13 |
| 150 | 31 | 14 (45%) | 4.76 (4) | 2.83 (2) | 2.58 | 1.63 | 1.30 | 0.24 |

Notes:
- The counts behind the king lifts are small (4-7), but the direction holds at all three
  thresholds and with all six anchors (lifts 2.0-3.6).
- Fork's king with weak shelter lifts 1.38-1.40; passers and material-up positions are
  *under*-represented.
- Hand-read examples from `spots100.tsv` (positions, not code):
  - Fork's king stuck in the centre with queens on (e.g. Fork's king on d8, castling lost, a
    white queen on h5, against Altair at ply 29: Fork −0.11, Altair +1.06);
  - an uncastled king on d1 with the f-file open (against Marvin at ply 24: Fork −0.20, Marvin
    +2.81);
  - several king attacks with pawn storms in random openings.
- Self-play shows **no** king-safety residual (STC-ppr2: Fork's king zone hit by ≥ 3, open
  phase, +0.44 at z +0.5). The net is calibrated to Fork-vs-Fork play: **a blind spot both
  sides share is invisible to self-play calibration and to self-play SPRT outcome statistics.**

### 0.6 E5. Unconverted advantages and fifty-move draws (MEASURED)

| Set | Draw rate | Drawn after one side held ≥ +1.00 for ≥ 20 own moves | Fifty-move draws |
|---|---|---|---|
| STC-r2 | 47.9% | 980 (3.8%) | 961 (3.75%) |
| LTC-r2 | 51.6% | 658 (4.9%) | 477 (3.6%) |
| STC-ppr2 | 45.3% | 174 (3.6%) | 181 (3.8%) |

- Pieces at the end of those stretches (LTC): 4-7 pieces 252, 8-11 pieces 228, 12+ 178.
- Top LTC signatures: KRPPvKRP 19, KRPvKRPP 11, KRPPPvKRPP 11 (rook endings a pawn up),
  KRNvKR 9, KRBvKR 8.
- **Fifty-move draws** (`fifty.py`): the eval is ≥ 50 cp 30 plies before the end in 65% of
  them (STC) and 52% (LTC), but only 10 plies before in 14% (STC) and 0.6% (LTC). The search
  sees the fifty-move draw about 10-30 plies ahead.

### 0.7 E6. Decision-level event studies (MEASURED): no visible loss

| Event (first per game, leader 75-250 cp) | Set | n | Score | Baseline |
|---|---|---|---|---|
| middlegame → endgame within 8 plies, still leading | STC-r2 | 7,754 | 0.842 | mid at the eval before 0.833 |
| same | LTC-r2 | 3,985 | 0.833 | 0.818 |
| same | gauntlet (Fork leads) | 128 | 0.852 | 0.874 (SE ≈ 0.03) |
| endgame, ≥ 2 pawns off within 6 plies, pieces kept | STC-r2 | 6,011 | 0.827 | no pawn change: 0.827 (7,828) |

When Fork chooses to trade down or trade pawns, the result is no worse than staying. The
selection effects are large (the eval rose after the event: 128 → 140), so this is **weak
evidence that the calibration gap costs little at STC through these decisions**. I use it to
cap C3's and C5's predictions.

### 0.8 E7. A signal I retracted

In the gauntlet, "Fork leads with less material" (open phase) scored +13.4 points over the
baseline (z +6.9), which looked like a strong "Fork undervalues compensation" finding. With
the baseline taken per opponent (`gcal.py`) it **disappears** (not significant). It was an
opponent-strength confound: Fork's leads without material come against weak anchors. It is
not used below.

---

## 1. Proposals

### C1. Knowledge-gap ledger per net, plus a blind-spot suite verified by Fork's own deep search [NOVEL] (the suite)

- **Mechanism.**
  - Turn §0's scripts into a standing report produced for every promoted net and every
    gauntlet:
    - (a) E1/E2 calibration tables by category from the net's promotion SPRT games, at STC and
      at LTC when available;
    - (b) E4's loss map and blind-spot lifts from each gauntlet;
    - (c) E5's unconverted-advantage and fifty-move rates.
  - From the gauntlet losses where the opponent saw the turn first, build a **blind-spot
    suite**: each FEN is re-searched by Fork itself at a deep budget (e.g. 50 M nodes, a
    placeholder). Keep only positions where Fork's deep verdict agrees with the game's turn
    (≥ 100 cp in the same direction), so the label is Fork's own.
  - The suite metric: the share of suite positions where Fork at an STC-like budget (500k
    nodes) is already on the right side of 0.
- **Math.**
  - The suite's size: 59-78 positions per gauntlet (E4), about 60% surviving the deep check
    (a guess) → about 40 positions per gauntlet; 3 gauntlets → ~120.
  - With p ≈ 0.3 correct at 500k nodes, the binomial SE at n = 120 is
    √(0.3·0.7/120) = 0.042. So a net or feature that fixes a quarter of the blind spots
    (+0.07) is visible at about 1.7σ. That is weak alone, and useful beside the SPRT.
  - Cost of the deep check: 120 × 5·10⁷ = 6·10⁹ nodes ≈ 180 s at datagen's ~34 M nodes/s
    (A1 §8), or about 15 min at 2 threads beside data generation.
- **Theory.**
  - Calibration analysis is standard (Guo et al., "On Calibration of Modern Neural Networks",
    ICML 2017, arXiv:1706.04599). Reliability diagrams by subgroup are the usual tool.
  - Self-play blind spots: a shared bias cannot be seen in self-play outcome statistics, the
    reason AlphaZero-style projects test against external opponents (general knowledge,
    UNVERIFIED as a specific citation).
  - Using another engine's eval only to *select* test positions, never as a label, keeps
    data-policy rule 4 intact: the label is Fork's deep search. **This needs an owner
    ruling first** (orchestrator's note, from the originality screen): the suite must
    never be used for training, and only FENs plus Fork's own labels may ever be
    committed, never the opponents' evaluations (non-negotiable 8).
- **Why Fork.**
  - E4 shows the self-play SPRT cannot reveal king-safety biases both sides share.
  - The 2026-11-02 gauntlet is the only external evidence, and it is S512r2-era.
  - §5.6's "final gauntlet" is the only gauntlet planned.
  - The ledger also gives idea 40's L5 ("proof set") a concrete, cheap form.
- **Prediction.**
  - A gauntlet with S512ppr2 (same anchors and openings, one GitHub run of 12 shards) shows
    king-zone lifts ≥ 1.5 at T = 100 and endgame lift ≤ 0.5. Refuted if the king lift is
    ≤ 1.1: then pawn links fixed it and C4 drops in priority.
  - The E2 endgame residuals of S512ppr2's next successor stay within ±1.5 points of today's
    unless C3/C5 lands. Refuted if they shrink by half without either.
- **Speed cost; compute.** None for the engine. CPU minutes for the scripts. One GitHub
  gauntlet run (already planned at the end; I propose one now as well).
- **Cheapest first experiment.** Run `calib2.py` / `gauntlet_strong.py` (exist, read-only) on
  the next gauntlet; build the suite from the existing gauntlet's 59 T = 100 spots (FENs are in
  `spots100.tsv` / `spotsS100.tsv`).
- **Kill criterion.** None as tooling. Stop extending the suite if deep verification keeps
  < 30% of the spots (then the spots are mostly eval-scale differences between engines, not
  Fork errors).
- **Originality.** Fork's own scripts and categories; CPW concepts (pawn islands, passed pawn,
  king safety) credited in ORIGINALITY.md when committed. Opponents' evals are used only to
  pick positions, locally; they are never committed or trained on (owner ruling needed).
- **Effort and dependencies.** 1-2 days to move the scripts into `tools/` with tests (owner's
  call). It replaces idea 40's L5 "held-out strategic test set" design work, and runs before
  §5.6 item 6, because it decides which knowledge family item 6 and item 14 should pursue.

### C2. Horizon study: deep against 20k-node labels, split by chess category [NOVEL for Fork's process]

- **Mechanism.**
  - A1 §8 already proposes relabelling 100k kept positions at 20k and 320k nodes to measure
    label noise. Do the same run and **split the label difference by C1's categories**:
    - mean signed shift (deep − shallow), from the leader's view;
    - variance per category.
  - Add idea 46's residual study, but with the **deep** label as the target. Fit frozen
    S512ppr2's static-eval residual (static − deep label, in WDL space) on three feature
    families separately:
    - (i) king-zone features (shelter, storm pawns, attackers by type, open files at the
      king);
    - (ii) pawn-status features (passers by rank, islands, isolated, backward, one wing);
    - (iii) threat features (hanging, attacked-by-lower).
  - Rank the families by explained variance.
- **Why deep labels matter (derivation).**
  - Idea 46's residual study, as approved, fits residuals against the *training* labels (20k
    nodes). A net trained to those labels has, by construction, a near-zero mean residual on
    every feature the labeller itself gets right or wrong. E2's data column shows exactly that
    (most data residuals within ±2.3).
  - So the study can only detect *fitting capacity* gaps, not *knowledge* gaps the labeller
    shares.
  - The categories that matter at LTC/TCEC are those whose bias grows with depth (E2). They
    show up only against a deeper target.
  - Expected sizes: E2's LTC endgame residuals of 5-8 points are, at the endgame slope
    (75.0 − 56.0)/50 ≈ 0.38 points per cp at 50-150 cp (E1 LTC end row), **about 15-30 cp of
    eval**. The shift between 20k and 320k labels should be of that order in those categories
    if the mechanism is real.
- **Theory.** The horizon effect (Berliner 1973, "Some Necessary Conditions for a Master Chess
  Program", IJCAI; UNVERIFIED as the exact first source). Label depth against learnability: the
  nnue-pytorch wiki's "quality and learnability" remark (b-survey-stockfish §3.1).
- **Why Fork.**
  - It turns E2's correlational finding into a mechanism test, at the same CPU cost A1 already
    budgets.
  - It decides between C4 (king), C7 (pawn status) and idea 46's threat designs *before* any
    Kaggle session or speed work.
  - S512+X's history (loss −2.2%, STC −30) is a warning against judging an input family by fit
    to shallow labels.
- **Prediction.**
  - (a) In drawish endgame categories (one wing, ≤ 4 pawns, pure OCB), the deep label is closer
    to 0 than the 20k label by ≥ 10 cp on average (leader's view).
  - (b) In "opponent has ≥ 3 islands", the deep label favours the leader more by ≥ 10 cp.
  - (c) In queens-on positions with the king zone hit by ≥ 3, the |shift| has ≥ 1.5x the
    control's standard deviation.
  - (d) For the residual families, king-zone features explain ≥ 1.5x the variance that threat
    features explain in queens-on middlegames.
  - **Refuted if (a) and (b) shifts are both < 5 cp.** Then the depth growth in E2 is a play
    effect, not a label effect: C5 stays, C3 is weakened, and C7 loses its rationale.
- **Speed cost; compute.**
  - 100k × (320k + 20k) nodes = 3.4·10¹⁰ nodes ≈ 1,000 s on 10 threads (A1 §8's 34 M
    nodes/s), or about 1.4 h at 2 threads beside data generation through jobctl.
  - The regression is minutes of Python.
- **Cheapest first experiment.**
  - Sample 100k kept positions from g3s2's validation file (any shard works), stratified so
    that each E2 category has ≥ 3,000 positions.
  - Relabel through a `fork_datagen`-style relabel mode, or a UCI driver at `go nodes`, with
    TT cleared per position (fresh state is fine for labels).
  - **Rules declared before the run:** the thresholds in the prediction.
- **Kill criterion.** As "refuted" above. For the residual part: if no family explains ≥ 0.5%
  of the residual variance (idea 46 rule 3's scale), the dense-input and class-head families
  are killed, as idea 46 already says.
- **Originality.** Fork's own measurement; no constants.
- **Effort and dependencies.** About 0.5 day of scripting. It shares the run with A1's
  label-noise measurement (B2) and replaces the target of idea 46's residual study (§5.6
  item 6). Gate for C4, C5 and C7.

### C3. Structure-class calibration scale on the eval (cached, zero training)

- **Mechanism.**
  - After the network, multiply the eval by a scale s[k] ∈ (0, 1.2]. The key k is a small
    structure-and-material class:
    - phase bucket (3);
    - pawn-count bucket (≤ 4, 5-8, ≥ 9);
    - all pawns on one wing (2);
    - pure opposite-coloured bishops (2);
    - rook-only ending (2).
  - That is at most 72 cells, most empty, shrunk toward 1.0.
  - Fit s by maximum likelihood so that the outcome curve per class matches the pooled
    middlegame curve (E1's "mid" row). The fit uses Fork's own deeper games, at STC-like or
    longer budgets, and is cross-validated on halves.
  - The scale applies at leaves, so the search compares, for example, "rook ending a pawn up,
    pawns on one wing" against "keep the minor pieces" on calibrated terms, for both the leader
    and the defender.
- **Math.**
  - E2 gives the overrating in score points: one wing −6.7, ≤ 4 pawns −5.6, pure OCB −8.0
    (LTC).
  - Converting at the band slope gives an expected s between 0.7 and 0.85 for those cells
    (a placeholder to be fitted). For example, at +100 cp in a one-wing ending the LTC data
    imply the conversion that a 70-80 cp middlegame eval gets (E1 LTC: mid 50-99 67.1%,
    100-149 84.7%; end 100-149 75.0% − 6.7 = 68.3% ≈ the mid band at about 55-60 cp).
    So s ≈ 0.6-0.8.
  - **Elo model (COMPUTED, low confidence):**
    - per game, P(reaching an affected endgame while leading by 50-300 cp) ≈ 0.3 (E1: end
      rows are 32% of band positions; the affected categories are about 40% of those);
    - about 2 decisions per such game where candidates differ by less than the 15-30 cp bias
      and lead to different classes;
    - P(the scale flips the choice) ≈ 0.25;
    - gain per flip ≈ half the bias, 2.5 points.
    - That gives 0.3 × 2 × 0.25 × 0.025 = 0.0038 score per game ≈ **+2.6 Elo** (range +1 to
      +5). E6's null event studies argue for the low end at STC.
    - E2's growth with TC, and TCEC's long conversion games, argue for more at LTC.
- **Theory.**
  - Classical evaluation functions scale drawish endgames toward zero (CPW "Evaluation"
    topics on drawish endgames and opposite-coloured bishops; the exact page names are
    UNVERIFIED).
  - Here the scale is instead a *post-hoc calibration* in the sense of Platt (1999,
    "Probabilistic Outputs for SVMs") and Zadrozny and Elkan (2002), fitted per subgroup.
  - Idea 10 (steer into TB-drawn endings when worse) is the defender-side special case. C3
    generalises it beyond tablebase range.
- **Why Fork.**
  - Fork's eval is the bare network (eval.hpp: `static_eval` returns the net's value; no hand
    term).
  - The bias is measured, stable across two nets (E3) and growing with TC (E2).
  - A scale is the one remedy that needs no training data from deeper play, so it is the
    cheapest way to learn whether calibration matters for Elo at all.
- **Prediction.**
  - Offline: on held-out games, the fitted scale cuts the summed squared category residual
    (E2's categories) by ≥ 50%.
  - Online: STC SPRT [0, 3] reaches H1, or a fixed 4-stage estimate (A3 §2.6) gives +1 to +5.
  - LTC ≥ STC, because the bias grows from STC to LTC in E2.
  - **Refuted if** offline variance falls < 30% (the classes are wrong), or STC is H0 and the
    LTC point estimate is ≤ 0.
- **Speed cost.**
  - The key needs pawn bitboard popcounts, a file-span test for one wing, and the bishops'
    square colours: about 10-20 instructions, cacheable by pawn key and material.
  - One multiply. Expected < 0.3% nps (UNVERIFIED; bench/ab.py) → < 0.5 Elo price.
  - Bench changes (new signature).
- **Data and compute.**
  - The fit data: either the existing SPRT PGNs, which are Fork's own games, *if the owner
    allows fitting a few dozen calibration constants on test games* (a tuning use, like SPSA,
    not training data);
  - or a dedicated local run: 4,000 games at 300k nodes per move ≈ 4,000 × 130 × 3·10⁵ =
    1.6·10¹¹ nodes ≈ 1.3 h of the 10-thread machine.
  - Refit per promoted net, since s depends on the net.
- **Cheapest first experiment.**
  - The offline fit and cross-validation on STC-r2 (exists) and STC-ppr2, with no engine work.
  - Then one build behind a switch (`UseStructureScale`, a name to be screened), an STC ladder
    of 2 shrink strengths, then the SPRT.
  - Then LTC (it changes eval scale in long games: add it to the LTC-sensitive list).
- **Kill criterion.** As "refuted". If H0 at STC and the LTC estimate is within ±2, keep it
  off and use E2's evidence only through C5.
- **Originality.** The concept of drawish-ending scaling is decades old and public. No engine's
  scale values are used: s is fitted on Fork's games. The constant screen applies to the
  shrink strength.
- **Effort and dependencies.**
  - 2-3 days.
  - Independent of the search queue (zero speed, one switch), so it fits GitHub idle slots.
  - It interacts with SPSA's eval-gated margins (A2 O4): run it before item 12, or refit after.
  - It subsumes idea 10's re-evaluation and makes the fifty-move scaling closure moot for
    these classes.

### C4. King-zone pawn links: own king square × pawns in its box (idea 40's L1, continued) [NOVEL] (UNVERIFIED that no engine does it)

- **Mechanism.**
  - A new input family per perspective: (own king square in the mirrored frame) × (pawn
    colour) × (pawn offset inside a box on the king's file ±1, from 1 rank behind to 3 ranks
    ahead).
  - The box covers shelter pawns, storming and rammed enemy pawns, and in endgames the king's
    proximity to pawns.
  - Size: 32 mirrored king squares × 2 colours × (3 × 5 − 1) offsets = **896 inputs**, folded
    into the main int16 sums like the links.
  - Active per perspective: about 3-6.
  - Changes happen only on a move of that perspective's king (remove and add its box's pawns:
    about 4-10 row operations) or a pawn move or capture inside either king's box (1-2 rows).
  - The sum for a perspective depends only on (king square, pawns), so it is also cacheable
    by pawn key and king square.
  - Trained as a **zero-initialised widening of S512ppr2** (A1 §5: the warm recipe; new rows at
    zero reproduce the parent exactly, so the identical-tree speed method applies).
- **Math.**
  - **Why king-relative pawn pairs are not already learnable.** S-512 has no king buckets (768
    mirrored inputs). A first-layer neuron sums piece-square weights, so "a pawn on g2 *and*
    the king on g1" needs a neuron whose SCReLU thresholds the sum of two independent
    terms. With 512 neurons and kings and pawns on many squares, those AND-relations compete
    for capacity, as pawn-pawn relations did before links.
  - **Speed estimate (COMPUTED, UNVERIFIED).**
    - Piece updates cost about 4 row operations per make (2 per perspective), at 17.2% of time
      (A3 §1.2).
    - Kings move on roughly 10% of moves × about 8 rows = 0.8; pawn moves in a box about 5% ×
      2 rows × 2 sides = 0.2. That is +1.0 rows per make, +25% of the update cost: **about 4%
      nps**, or 2-3% with the pawn-key cache.
    - Price at 0.96: 152·ln(1/0.96) = **6.2 Elo**. At 0.975: 3.8.
  - **Elo model.**
    - In the gauntlet, 125 of 217 strong-anchor losses (58%) had the opponent's eval ahead of
      Fork's (E4).
    - If king knowledge removed 10-20% of those (half of them turning into draws): 12-25 games
      × 0.5 point / 600 games = 1.0-2.1% score ≈ +7 to +15 Elo against strong engines.
    - Self-play SPRT sees less, because the base shares the blind spot only partly; the test
      side exploits it, so self-play does see some.
    - Net of a 4-6 Elo speed price: **+2 to +10 STC, more at LTC** (king attacks are deep
      plans).
- **Theory.**
  - King-relative inputs are the original NNUE design (Nasu 2018, HalfKP for shogi; KB
    nnue-design.md). Pawn shelter and storm are classical king-safety terms (CPW "King
    Safety", "Pawn Shield", "Pawn Storm").
  - The *local* king-pawn-pair family is my design, a sparse sub-family of HalfKP limited to
    pawns near the king. **NOVEL (UNVERIFIED)**: I found no public description.
  - It is the "pawn-and-king" half of idea 40's L1 as the owner first described it ("a small
    learned network on pawns and kings only, cached by pawn_structure_key").
- **Why Fork.**
  - E4: king zones are the top blind-spot category against strong engines (lift 2.5-4.8), and
    endgames are not.
  - H-512 (4 king regions over *all* pieces) failed (FN −12.2 r2, A1 §1), but it was trained
    cold on non-interleaved data (A1 §3.4) with about 2.0 M first-layer weights. C4 adds 0.46 M
    rows' worth (896 × 512) of a targeted relation. It is warm-started, so it cannot start
    below the parent.
  - The pawn-change flag and pawn key already exist (S512+PP's speed steps, ideas.md 40).
  - C4 is a more targeted, cheaper retry than full king buckets; the network specialist's
    king-bucket proposals (b-survey-opensource N3) are the alternative to race it against at
    fixed nodes.
- **Prediction.**
  - Identical-tree nps ≥ 0.96 (refuted if < 0.94 after the tight-pass treatment links got).
  - FN screen against S512ppr2 at 800k nodes: +8 to +20 (pawn links gave +46 at 0.895).
  - STC [0, 5] passes if FN − 152·ln(1/r) ≥ +5.
  - C1's gauntlet king lift falls from ~2.5-3 to ≤ 1.7 with the new net.
  - **Refuted if** FN < 6.2 + 5 = +11 at r = 0.96 (the speed-adjusted rule, A3 §1.4).
- **Speed cost; data and compute.**
  - About 3-5% nps (estimate above).
  - Data: 1.6 B positions × ~4 active rows over ~300 frequently used rows ≈ 2·10⁷ touches per
    row, above design-accuracy.md's 12.8 M anchor (A1 B7).
  - One Kaggle session (the warm recipe, about 6.5 h on one T4, A1 §5.3).
- **Cheapest first experiment.**
  1. C2's residual study first: king-zone features must explain ≥ 0.5% of the deep-label
     residual variance in queens-on middlegames, or C4 is not built.
  2. Then the engine side behind the architecture id, with rows at zero: the identical-tree
     A/B (bench/ab.py, 12 rounds), 1 day.
  3. Then the Kaggle session and the FN screen (1,600 games).
- **Kill criterion.**
  - The residual gate fails;
  - or identical-tree nps < 0.94;
  - or FN < price + 5;
  - or STC H0.
- **Originality.** Concepts from Nasu (2018) and CPW (credited). The index layout and box shape
  are Fork's own. Name screening is needed for any new identifier ("king-pawn" names
  especially, given HalfKP's lineage).
- **Effort and dependencies.**
  - 5-8 days.
  - It is §5.6 item 14's "idea 40's later layers", pulled forward behind C2's gate.
  - It competes for the same Kaggle and speed-gate slot as king-bucket proposals. Race them at
    FN on the same data, if both are built.

### C5. Depth-matched endgame-start slice (deeper outcomes where the bias lives)

- **Mechanism.**
  - A data part of Fork self-play games **started from Fork's own positions with 8-16
    pieces**: endgames and late middlegames, sampled from existing kept data with
    |label| ∈ [50, 400] cp.
  - Played with 4x the normal nodes (80k, no split search) to the end, under datagen's
    adjudication (5-man table entry, 700 cp × 8 plies).
  - Records carry their 80k-node scores and the deeper games' results.
  - Mixed evenly at about 1% of the next snapshot (the Syzygy slice's recipe, idea 45: evenly
    interleaved).
  - The result half of the target then reflects deeper conversion and defence exactly in the
    classes E2 flags.
- **Math.**
  - **Cost (COMPUTED).** 34 M nodes/s / 80k = 425 positions/s; 16 M positions → 37,600 s ≈
    **10.5 h of the 10-thread machine** (about 1.4% of a 1.6 B snapshot at about 68% kept).
    Normal generation at about 2,700 records/s (HO §4) would make about 100 M records in the
    same time, so the slice costs about 6% of a week's data.
  - **What to expect (INFERRED).** The Syzygy slice fixed 343 of 351 misjudgments with 2.1% of
    the positions (DESIGN §5.6), so coverage slices are very data-efficient. Here the issue is
    label *strength*, not coverage, so expect a partial fix: E2's residuals shrinking by
    one third to one half at STC.
  - Elo ≈ C3's model with the bias halved but applied by the net in every class, not only the
    5 coded ones: **+2 to +6 STC, +3 to +8 LTC**.
- **Theory.**
  - The nnue-pytorch wiki's staged retraining on better-labelled data (b-survey-stockfish
    §3.2).
  - Targeted mixing in the final round (same survey, §3.6).
  - Endgame-start self-play appears in the open-source family's record (b-survey-opensource N6,
    Caissa's endgame-book data; no numbers copied).
  - The depth argument is E2 (Fork's own).
- **Why Fork.**
  - The data's results come from 20k/4k-node games (g3.json).
  - E2 shows the biases are absent in that data and grow with depth.
  - TCEC's decisive games are long conversions from biased openings (b-survey-tcec §1.1), and
    TCEC plays to mate (idea 12's note).
  - Idea 11 (TB boundary data) was framed for 6-piece adjudication, which no longer exists. The
    relevant boundary for Fork is "8-16 pieces converting into ≤ 7".
- **Prediction.**
  - Two warm retrains at equal samples (Kaggle T4 x2, one session), with and without the
    slice. The slice arm's E2 residuals at STC (from its FN or SPRT games) shrink by ≥ 1/3 in
    one wing, ≤ 4 pawns and islands.
  - FN ≥ 0; STC +2 to +6.
  - **Refuted if** the residuals move by less than 1 point (80k-node outcomes are still too
    shallow; then try 320k nodes on a smaller slice, or rely on C3).
- **Speed cost.** None (data only).
- **Cheapest first experiment.**
  - Generate a 4 M-position pilot (about 2.6 h of the machine through jobctl, between parts).
  - Measure its calibration with `calib2.py vf`, before any training: its one-wing residual
    against its own labels should be closer to STC's −6 than the normal data's −2.25.
  - If it is not, stop before Kaggle.
- **Kill criterion.** The pilot's residuals look like normal data's (within 1.5 points), or the
  equal-sample arm comparison shows no residual shrinkage.
- **Originality.** Fork's own games, Fork's own labels: strategy A+ intact. No other engine's
  data.
- **Effort and dependencies.**
  - 3-4 days, mostly unattended CPU.
  - It needs a datagen mode that starts from a position file (the openings tool exists:
    tools/datagen/datagen_openings.py; UNVERIFIED that it accepts arbitrary FENs and node
    settings per part).
  - It slots into the next snapshot after g3g, beside A1's B1/B2 Kaggle arms (one arm pair).

### C6. Endgame acceptance test extended to 4-5-man signatures, plus a TB audit of unconverted advantages

- **Mechanism.**
  - The standing test (tools/nnue/endgame_check.py) covers KPK/KQK/KRK only: 900 positions,
    3 pieces.
  - Add 4-5-man classes the slice teaches and Fork's games reach, verified by local 3-4-5
    Syzygy (test only):
    - KRPvKR, KRPPvKR, KQvKR, KBNvK;
    - KBPvK with the wrong-coloured bishop and the rook pawn;
    - KBPvKB with opposite bishops, KPPvKP, KNPvK.
  - 6-7-man spot checks (KRPPvKRP same-side, KRBvKR) through the public Lichess tablebase API
    as test labels only. The API is 7-man Syzygy, which data policy allows as labels (rule 4),
    and here they are only test targets.
  - Separately, audit E5's unconverted-advantage games: for the stretches that end with ≤ 7
    pieces, ask the tables whether the leader ever had a win.
- **Math.**
  - E5: 252 of 658 LTC stretches end with 4-7 pieces.
  - If ≥ 30% of them pass through a TB-won position, conversion technique (search, DTZ use) is
    losing about 0.3 × 252 / 13,312 = 0.6% of games' half points; else it is calibration
    (C3/C5).
  - KQK went 0 → 59 → 0 across warm starts with no test catching it in time (A1 §5.1). One
    such regression costs a few Elo in KQK-reaching games and is invisible to STC SPRTs with
    3-4-5 tables (both sides probe).
- **Theory.** Syzygy tablebases (R. de Man; KB). Idea 12's conversion suite (100 of 100) and
  idea 45's check.
- **Why Fork.**
  - The slice is permanent now; every retrain can lose rare patterns (A1 §6 point 4).
  - TCEC plays to mate with 7-man tables: ≤ 7 pieces are probed, so the net's job is the
    8-16-piece region. Within the probed range, only regressions matter.
- **Prediction.** S512ppr2 misjudges ≥ 10% of KBPvK wrong-bishop and KRPvKR-drawn positions
  (classes the slice saw only as a share of "signatures Fork's games reach"). Refuted if
  ≤ 3%.
- **Speed cost.** None.
- **Cheapest first experiment.** Extend endgame_check.py's generator (it already samples and
  verifies with python-chess's syzygy module). 1,500 more positions; minutes.
- **Kill criterion.** None (a guard). The audit's conversion branch dies if < 15% of stretches
  pass through TB wins.
- **Originality.** Test data from tables; no engine output.
- **Effort and dependencies.**
  - 1 day.
  - **Drop idea 45's part 3** (conversion without tables, KRK 3 of 20 drawn): with tables at
    TCEC (7-man) and in every SPRT (3-4-5), mating without tables never decides a game.
  - The 3-of-20 KRK result is real but irrelevant to Elo unless the tables are missing.

### C7. Pawn-status planes: the absence-defined concepts links cannot see [NOVEL for NNUE] (UNVERIFIED)

- **Mechanism.**
  - Three or four planes of 96 inputs each (pawn slot = colour × square): "passed", "isolated",
    "backward", optionally "candidate".
  - A plane input is on when that pawn has that status.
  - Statuses are recomputed with bitboard fills only when the pawn structure changes (the
    existing pawn-change flag), and the diff against the previous statuses gives row
    operations: about 1-3 per pawn move.
  - Zero-initialised widening of the current default, as C4.
- **Math.**
  - Pawn moves are about 15-20% of moves (UNVERIFIED) × about 2 rows ≈ 0.35 rows per make
    (+9% of the update cost) → **about 1.5-2% nps**, price 2.3-3.1 Elo.
  - E2's islands and passer residuals (+4.6 to +6.9 and +2.6 to +4.3 points) are the targets.
  - The data column says the *labels* barely see them (−0.4 and +0.0). So C7's FN gain depends
    on whether the 20k-node scores contain structure the net cannot fit (links' +46 FN says
    such headroom existed for contact relations) or only the deep-play biases (then only C5
    helps).
  - Expect FN +3 to +12, net +1 to +8.
- **Theory.** Passed, isolated and backward pawns are classical evaluation terms (CPW
  "Passed Pawn", "Isolated Pawn", "Backward Pawn"). KB nnue-inputs §2.3: pair features cannot
  state absence. Status planes as NNUE inputs: I found no public description (UNVERIFIED).
- **Why Fork.** E3 shows links left these residuals unchanged. They are cheap to update in
  Fork's design and fully cacheable by pawn key.
- **Prediction.** FN +3 to +12 at identical-tree nps ≥ 0.98. Refuted if FN < price + 5 ≈ +8.
- **Cheapest first experiment.** C2's residual study must show pawn-status features explaining
  ≥ 0.5% of the deep-label residual variance in endgames. Then the identical-tree speed A/B.
  Then a Kaggle arm, *shared with C4's session* (two arms).
- **Kill criterion.** The C2 gate fails; nps < 0.97; FN < +8.
- **Originality.** Classical concepts (credited); Fork's encoding. Screen names.
- **Effort and dependencies.** 4-6 days; after C2, beside or after C4; idea 40 L1.

---

## 2. Critique of the current plan in my domain (§5.6 and the ideas)

1. **Idea 40, reordered.**
   - **L5 first, as C1** (the ledger and blind-spot suite). It is cheap and decides the rest.
   - **L1's next step is C4 (king-pawn) or C7 (pawn status), behind C2's gate.** It is not a
     separate small network: S512+PP showed that folding a family into the main sums beats a
     structure-key cache (ideas.md 40: cache 0.809-0.824 against the tight pass 0.818, "no
     gain").
   - **Drop L2's pawn drift table**: undecided at LTC (−0.35 ± 3.72), and its target overlaps
     the links (A2 O7; both surveys agree).
   - **Shrink L3 (root planner)**, for three reasons:
     - none of my evidence points at long plans the search misses: Fork's losses are early
       king and tactical turns (E4);
     - the long-draw problem (E5) is endgame calibration;
     - the near-tie gate has not been measured.

     Keep only the gate's measurement (cheap) and defer the planner past Phase 4 unless the
     gate shows ≥ 20% of root decisions within 10 cp *and* C1's suite shows structural blind
     spots.
   - **L4 needs a caution.** "A higher weight on the game result" imports the *data's*
     outcome biases. E2 shows those differ from deep play and sometimes have the opposite sign:
     rook endings convert more than their score in the data (+2.9) and less at STC (−1.7).

     A higher w should make the net overrate rook endings and other shallow-convertible
     classes *more*. That is a falsifiable prediction for A1's B4 and the surveys' "WDL-heavier
     end of training" (N2): a w = 0.7 arm will show a more negative STC end_rook residual than
     the w = 0.5 arm. Refuted if it moves toward 0.

     A long-horizon auxiliary target makes sense only with deeper outcomes (C5's games).
2. **Idea 46 (§5.6 item 6), re-scoped.**
   - (a) The residual study must use **deep labels** (C2), or it measures fit to the labeller,
     not knowledge.
   - (b) Re-rank toward **king-zone danger**:
     - tactics are 30-45% of blind spots, and hanging-piece knowledge is search-resolvable
       (A1 §3.5: exposure-type gains run about 6 Elo per 1e-4 against links' ≥ 41);
     - the non-tactical majority sits at kings with queens on (E4).

     So the dense danger vector (rank 4) should carry king-zone attackers, and only if C2's
     king family wins.
   - (c) Distillation from S512+X (rank 1) inherits S512+X's exposure knowledge, which is the
     search-resolvable kind. Expected 0 to +3; I would run it only after C2.
3. **Idea 41 (S512cl): drop the contact family as designed.** At 0.195x the price is
   152·ln(1/0.195) = 249 Elo (A1 §4.4); even at the incremental estimate of 0.5-0.6 it is
   78-105 Elo. Nothing in E4 asks for general contact knowledge. If threat inputs return, only
   king-zone threats (C4's box, extended to pieces) are worth pricing.
4. **Idea 45: keep parts 1-2 and extend part 2 (C6). Drop part 3** (conversion without
   tables): it never decides a game with tables present.
5. **Ideas 10 and 11.**
   - Idea 10 (steer into drawn 6-piece endings) is subsumed by C3's defender side and by C5;
     close it as "replaced".
   - Idea 11's boundary moves to 8-16 pieces (C5).
   - A 6-man WDL slice is worth it only if the tables can be obtained and stored. Their size
     is UNVERIFIED; I recall roughly 70 GB for 6-man WDL, which is not checked. Its Elo in
     SPRT conditions is ≤ +2 (6-piece positions are a small share), so keep it low.
6. **Fifty-move eval scaling: keep it closed at STC.** E5 shows the search already sees the
   fifty-move draw 10-30 plies ahead. Fifty-move draws are 3.6-3.75% of games, and in only
   about half of them did the leader still hold ≥ 50 cp 30 plies out.

   Even converting 10% of those gives 0.036 × 0.6 × 0.1 × 0.5 ≈ 0.1% score ≈ +0.7 Elo.
   **Not worth a GitHub slot.** (A2 is right that the proxy was a scale artifact; the game data
   say the true value is small anyway.)
7. **S512+X as an LTC candidate: drop** (A3 §1.4 point 4). E4 adds that exposure knowledge is
   not where Fork loses.
8. **Order.** I would insert C1 and C2 before §5.6 item 6, because both are cheap (CPU hours,
   no GitHub). C3 can go as GitHub filler with zero speed cost. C4 or C7 goes behind C2's gate
   in item 14's slot, moved ahead of SPSA (item 12) only if its FN screen is large, since a new
   eval shifts every margin (A2 §3.3). C5 fits the next snapshot.

---

## 3. What I could not verify

- **The gauntlet evidence is S512r2-era**, before pawn links. Its king-zone lifts rest on 4-7
  positions per threshold, consistent in direction but statistically thin. A gauntlet with
  S512ppr2 (C1) is needed.
- **Opponents' eval scales** differ from Fork's. "The opponent saw it first" (E4) is biased
  toward the opponent if its scale is larger, and so are the 47 "bad start by the opponent only"
  losses. The random 8-ply openings are those the run used (READ in DESIGN decisions log); their
  balance was not checked.
- **The data column is one shard** (the first 12,000 games of g3-w03). It is S512r2-labelled
  with the split search, and its openings (Lichess 2016 plus random plies) differ from UHO.
- **Phase thresholds** (non-pawn material 20 and 44) and all category definitions are mine,
  not tuned. Categories overlap and are correlational; no causal claim is made.
- **SPRT PGNs mix test and base engines** (and in STC-ppr2 three nets). The evals in comments
  are searched scores at the engine's depth, not static evals.
- **Adjudication shapes outcomes:** resign at 1000 cp × 5, draw at |10| cp × 10 from move 40
  (A3 §2.1). Positions within those regimes are in the samples.
- **Speed estimates for C4 (3-5%) and C7 (1.5-2%) are reasoned, not measured.** So are the
  move-type frequencies behind them (king moves about 10%, pawn moves about 15-20%).
- **C3's and C4's Elo models** rest on assumed decision counts and flip rates. E6's null event
  studies suggest C3's low end.
- Whether `datagen_openings.py` / `fork_datagen` can start parts from arbitrary FEN files with
  per-part node settings (C5).
- The size of 6-man WDL Syzygy, and whether the Lichess tablebase API's terms allow batch test
  queries (C6).
- No NNUE engine's use of local king-pawn pairs (C4) or pawn-status planes (C7) was found; that
  is not proof that none exists. Both are marked NOVEL with UNVERIFIED.
- Citations marked UNVERIFIED above (Berliner 1973 as the first horizon-effect source; CPW page
  names) were not re-opened in this session.


---

# B11. Search-evaluation interaction (I)

## B-I: search-evaluation interaction (think tank, Phase B, specialist I)

**Summary.** I derive a decision model for Fork's eval-gated pruning, then fit it to the numbers Fork
already has. The model sets each margin by three things:
- the residual r = (depth-d search result − static eval);
- the value of a saved subtree;
- the cost of a wrong prune.

From these, the optimal margin satisfies P(r < −m*) = q_d, where q_d is the ratio of savings to cost.
So **m* scales with the residual's scale**. That scale is the eval's *error*, not its magnitude, so
matching mean |eval| from net to net holds the cp units but not the margins' meaning.

What Fork's data say:
- **The residual is a mixture.** I fit two figures from the drift measurement (mean |r| about 36 cp,
  p99 |r| about 270 cp; S512r2). The fit is a Gaussian core with σ_c ≈ 31-37 cp plus a tactical
  tail of about 6-15% with scale about 100-150 cp.
- **At RFP's depth-1 margin (80 cp) the tail causes 60-90% of wrong prunes** ("tail-limited").
- **A better net helps the margins less than the folk rule says.** The folk rule is "a better eval
  allows tighter margins". A 10% smaller core σ cuts wrong prunes at 80 cp by only 6-20%. The
  tail is horizon tactics, and S512ppr2's gains (pawn links, endgames) are core gains.
- **Fork's past results agree.** I split each SPRT into a speed term (k · ln of the bench node
  ratio, k = 152 Elo per e-fold) and a quality term Q.
  - Every eval-gated loosening that failed sits just past break-even. The quality cost per e-fold
    of nodes saved is 164-214, against k = 152 (rising RFP 214, qs-delta 164). So **the current
    margins are near their optimum at shallow depth**.
  - IIR's quality cost shrank from −14 at STC to about −6 at LTC. So selectivity gets cheaper with
    depth.

Consequences:
1. The SPSA retune's margin share is probably small (≤ +5), not +15-35. A cheap global-multiplier
   ladder (4 STC stages) can falsify this before the SPSA is planned (I2).
2. The Elo that is left lies in **shape and partition**, not level:
   - concave depth profiles, because the share of wrong prunes falls about tenfold from depth 1 to 6
     under 80·d;
   - **tail-risk-classed margins**: a cheap tactical-risk bit moves margin from "hot" to "cold"
     nodes at an unchanged prune count. In simulation that gives 11-39% fewer wrong prunes.
3. A sampled-counterfactual **decision ledger** (I1) measures all of this in about an hour of local
   CPU before any GitHub time.
4. Correction tables should be chosen by passive measurement on S512ppr2 first. Key them where the
   net is blind (no king buckets: a non-pawn key that includes the king; recent moves: a
   continuation key). The pawn table is probably made redundant by the pawn links.

| ID | Title | Expected Elo at LTC (range) | Effort (days) | Confidence | NOVEL? |
|---|---|---|---|---|---|
| I2 | Global margin-multiplier ladder: the regime test that sizes the SPSA retune | 0 to +3 direct; decides 10-40 h of SPSA scope | 0.2 (no code: params only) + 4 STC stages | medium | no (method new for Fork) |
| I1 | Decision ledger: sampled-counterfactual calibration of every eval-gated decision | enabler (feeds I3-I7) | 2 | high (that it informs) | NOVEL as a process (UNVERIFIED) |
| I4 | Tail-risk-classed margins (mean-preserving re-partition by a cheap tactical-risk bit) | +2 to +8 (RFP, futility, later razoring and bad-capture stop) | 3 + SPRTs | medium-low | partly (idea 46 judge: "partly public") |
| I3 | Concave, σ_d-indexed margin shapes (m_d = K·σ̂_d) | 0 to +6 | 1-2 + SPRTs | medium-low | no |
| I5 | Correction tables re-scoped: passive ranking on S512ppr2 (pawn vs king-inclusive non-pawn vs continuation), count-based gain | 0 to +5 at 1 thread (more with threads, Phase 6) | 2-4 | low-medium | count-based gain: NOVEL (UNVERIFIED) |
| I7 | Improving as a measured mean shift, mean-preserving, on prune_eval | +1 to +4 | 1 + SPRT | medium-low | no |
| I6 | Margin credit for tail-reducing nets (ledger per candidate net) | 0 to +4 per qualifying net | 0.5 per net | low-medium | NOVEL (UNVERIFIED) |
| I8 | TT-eval refinement hygiene (stand-pat refined only by main-search entries) | 0 to +3 | 0.5 + SPRT | low | no |
| I9 | Aspiration and TM in calibrated units (heteroscedastic window; expected-score trend terms) | 0 to +2 (more inside O1's TM) | 0.5 | medium | no |

Conventions: **[read]** = taken from a file; **[derived]** = my arithmetic (scripts in my
scratchpad: `model.py`, `tail.py`, `qtot.py`); **[model]** = output of the model under stated
assumptions; UNVERIFIED where unsure. Sources: SL = docs/history/phase-4/sprt-log.md; DC = DESIGN.md
§5.2 "Search constants"; A1/A2/A3 = Phase A files; S1/S2 = the clean-room surveys. k = 152 Elo per
e-fold of nodes (A1, about 1.5 Elo per 1%) at STC, about 137 at LTC (A1 §4.3 = A3's 95 per
doubling). No engine source was opened and no other engine's constants appear here.

---

## 0. The model

### 0.1 Setup and the optimal-margin condition

Take an eval-gated decision, with RFP as the example; futility, razoring and bad-capture
futility are symmetric.

- **Quantities.** At a non-PV node of depth d, let ê = prune_eval, g = ê − β (the gap), and let
  v_d be the value a full depth-d search would return. The residual is r_d = v_d − ê.
- **The prune.** RFP prunes when g ≥ m_d. It is a wrong prune when v_d < β, i.e. r_d < −g.
- **The trade at the margin.** Moving m_d down by dm adds the nodes with g ∈ [m_d − dm, m_d]. Each
  one:
  - saves its subtree, C_d nodes, worth λ·C_d (λ = Elo per node at fixed quality);
  - costs F_d(−m_d)·L_d, where F_d is the CDF of r_d and L_d the expected Elo cost of one wrong
    prune.
- **Optimum:**

  F_d(−m*_d) = q_d ≡ λ·C_d / L_d.                                          (1)

- **Gaussian residual** N(μ_d, σ_d²): m*_d = −μ_d + σ_d·z(q_d), with z = Φ⁻¹(1 − q). The margin is
  linear in σ_d. It depends on the cost ratio only through z ≈ √(2 ln(1/q)): halving q moves z
  from 2.33 to 2.58, about 10%.
- **Exponential (Laplace) tail** with mass π and scale τ: m* = τ·ln(π / 2q). The margin is linear in
  the tail scale τ and depends on the tail mass only logarithmically.

So **margins scale with the scale of the residual, an error, not with the scale of the eval.**
Fork's mean-|eval| matching (match_scale.py: S chosen so mean |eval| matches the previous default
on shared positions) fixes the cp spread of the eval. A better net keeps that spread while its
error shrinks, so fixed cp margins become relatively more conservative with each net. That is A2's
O4 premise. The rest of this section asks how large the effect is for Fork.

### 0.2 Fork's residual distribution: what the drift measurement already shows

Two figures exist [read], both for S512r2:
- p99 of |exact result − raw eval| < 280 cp. From the drift-off run of tools/drift_measure.py:
  120 STC games, 200k nodes per move, 1,019,064 exact results (DC `DriftLimit`).
- mean raw error 36.42 cp at the learning nodes. This is from the 3-game pipeline test in
  drift_measure.py's docstring. Bound results count only the part the bound proves, so this
  understates |r| [read].

A single Gaussian with mean |r| = 36.4 has σ = 45.6 and p99 |r| = 117 cp, far below the 270 that
was seen. A Laplace distribution gives p99 = 4.6 × 36.4 = 168, still too low. **The residual is
heavier-tailed than Laplace.** A two-part fit uses a Gaussian core σ_c plus a two-sided exponential
tail of mass π and scale τ. Matching both moments [derived, `model.py`]:

| τ (cp) | π | σ_c (cp) |
|---|---|---|
| 100 | 0.149 | 31.7 |
| 125 | 0.087 | 35.1 |
| 150 | 0.060 | 36.5 |
| 200 | 0.039 | 37.4 |

Caveats:
- These are learning nodes at mixed depths, not RFP candidates at depth d.
- The 36.4 cp figure comes from only 3 games.
- The fits are illustrative, which is why I1 exists. But every plausible fit has the same shape:
  **a core of about 30-37 cp and a tail of 4-15% at 100-200 cp.**
- The fifty-move scaling measurement's 24-26 cp score errors (A2 §3.2), between short searches and
  25 M-node labels, are consistent with the core scale.

### 0.3 Core-limited or tail-limited? What a better net changes

One-sided wrong-prune rate at the margin, F(−m) = (1 − π)·Φ(−m/σ_c) + π·½e^(−m/τ), and the effect
of a 10% smaller core σ [model, `model.py`]:

| m (cp) | σ_c 33, π 0.074, τ 125: total (tail share) | after σ_c −10% | σ_c 31, π 0.15, τ 100 | after −10% | σ_c 36, π 0.06, τ 150 | after −10% |
|---|---|---|---|---|---|---|
| 40 | 0.131 (0.20) | ×0.83 | 0.134 (0.38) | ×0.86 | 0.148 (0.16) | ×0.84 |
| 60 | 0.055 (0.42) | ×0.78 | 0.064 (0.65) | ×0.86 | 0.065 (0.31) | ×0.77 |
| **80** | **0.027 (0.73)** | **×0.86** | **0.038 (0.89)** | **×0.94** | **0.030 (0.59)** | **×0.80** |
| 120 | 0.014 (0.99) | ×0.99 | 0.023 (1.00) | ×1.00 | 0.014 (0.97) | ×0.98 |
| 160 | 0.010 (1.00) | ×1.00 | 0.015 (1.00) | ×1.00 | 0.010 (1.00) | ×1.00 |

Readings:
1. **At RFP's depth-1 margin (80 cp), the tail causes 59-89% of wrong prunes.** Above about 100
   cp it causes nearly all of them. The deeper margins (160-480 cp) are wholly tail-limited.
2. **A 10% smaller core σ cuts wrong prunes at 80 cp by only 6-20%**, and at depth ≥ 2 by
   nothing. A pure Gaussian model would predict about 45% (Φ(−2.69)/Φ(−2.42)). So eval accuracy
   reaches the margins mostly at depth 1, and only partly.
3. **Which error a net fixes matters more than how much.**
   - Pawn links and the endgame slice (S512+PP, S512ppr2) fix core, positional error that depth
     cannot resolve.
   - Threat or exposure knowledge (S512+X, XGR) attacks the tail. That is the error the margins
     are bound by (I6).
4. **Two Fork results fit the tail-limited reading:**
   - **Rising RFP failed after +200 Elo of net gains** (−3.78 ± 2.92, S512r2; SL 2026-11-06).
   - **The pawn drift table was null at LTC** (−0.35 ± 3.72; SL 2026-11-02), although the measured
     cut in passive error was 8% (fitness 0.919). In a core-limited regime an 8% error cut would
     cut wrong prunes at the margin by about 40%, which should be several Elo. In the tail-limited
     regime it is about 10%, i.e. 1-3 Elo, which the drift table's unmeasured nps cost could
     cancel (I5).

   Both are also consistent with other explanations (A2 §2.2), so this is corroboration, not proof.

### 0.4 Splitting Fork's SPRTs into speed and quality

A feature that changes the fixed-depth tree by a node ratio N1/N0 at unchanged per-depth quality
is worth k·ln(N0/N1). That is the speed-to-Elo rate applied to nodes. The rest is the quality term
Q = Elo − k·ln(N0/N1). Bench node ratios [read, DC and SL], k = 152 [derived]:

| Feature (era) | ln(N0/N1) | speed term | SPRT Elo | Q | ρ = −Q / ln(N0/N1) |
|---|---|---|---|---|---|
| IIR (S512r2) | 0.233 | +35.4 | +21.45 | −13.9 | 60 |
| Negative extension | 0.332 | +50.5 | −8.73 | −59.2 | 178 |
| Rising RFP | 0.061 | +9.2 | −3.78 | −13.0 | **214** |
| qs-delta (B0r1) | 0.033 | +5.0 | −0.40 | −5.4 | **164** |
| Singular extension | −0.267 | −40.5 | +14.12 | +54.7 | (quality gain 205 per e-fold of cost) |

- **Break-even is ρ = k.** A selectivity change pays only if its quality cost per e-fold of
  nodes saved is below the rate at which nodes buy Elo.
- **The eval-gated loosenings sit at 1.1-1.4 k: just past break-even.** That is the signature of
  margins near their optimum. If the margins were far too conservative, loosening would show
  ρ < k and pass. If they were far too aggressive, ρ would be several times k.
- **How near.** Under the Gaussian core, a 25-cp step at depth 1 multiplies the marginal
  wrong-prune rate about fivefold (Φ(−55/35)/Φ(−80/35) ≈ 5.3). An average ρ of 1.4k over the step
  therefore puts the marginal ρ at 80 cp near 0.5-1.0 k, i.e. **the optimum within about 10-20% of
  80 at depth 1** [model]. RfpMargin 40's bootstrap-era gauntlet loss (about −44 ± 22; ideas.md 34)
  points the same way.
- **The tests cover shallow depth only.** Rising RFP's flat −25 cp is 31% of the margin at d = 1
  and 5% at d = 6, so nothing above depth 2 has been probed.
- **The quality cost of selectivity shrinks with time control.** IIR: Q = −13.9 at STC. At LTC,
  26.25 − 137·0.233 = **−5.7**, a ratio of 0.41, with wide error (each SPRT is about ±6). This agrees
  with tier 1's +439 STC → +555 LTC (A2 §5).
  - Reading [inferred]: a wrong prune deep in the tree is more often repaired by later
    iterations, so L_d falls as the total depth grows.
  - In (1) that raises q_d, so **optimal margins should be smaller at LTC than at STC**.
  - It also makes near-break-even loosenings such as rising RFP (Q ×0.41 = −5.3 against an LTC
    speed term of 8.3) LTC-neutral to slightly positive. I do not propose retests (owner's rule);
    this is a prediction for the LTC SPSA (§2).
- **Caveat.** These are bench nodes at fixed depth, not nodes in games (UNVERIFIED transfer), and
  this is one LTC point.

### 0.5 Heteroscedastic and risk-classed margins

If the residual's spread varies from node to node and a cheap signal predicts it, margins can be
moved to where they are needed at an unchanged prune count.

- **Core variation only** [model, `model.py`, 400k simulated candidate nodes, gaps exponential
  with mean 120 cp, uniform margin 80]:
  - with log σ varying so that the top quintile's σ is 2x / 3x / 5.4x the bottom's, per-node
    margins cut wrong prunes by 63% / 88% / 97% at equal prune count;
  - **with an unpredictable 7.4% tail added, only 5% / 14% / 26%.**
  - So an uncertainty signal that predicts only the *core* (net confidence, variance heads, phase
    disagreement) is worth little where Fork's margins sit.
- **A tail-risk signal** [model, `tail.py`]: a binary "hot" class flags 10-20% of candidate nodes
  that carry a larger share of the tail. Class margins (hot raised, cold lowered, equal prune
  count):

| hot share | tail rate hot / mean | indicator accuracy | wrong prunes vs uniform | hot margin | cold margin |
|---|---|---|---|---|---|
| 0.2 | 3.4x | perfect | −25% | +90 | 65 |
| 0.2 | 3.4x | 70% | −11% | +80 | 67 |
| 0.2 | 4.1x | perfect | −39% | +120 | 63 |
| 0.2 | 4.1x | 70% | −21% | +90 | 65 |
| 0.1 | 5.4x | perfect | −30% | +190 | 70 |
| 0.1 | 5.4x | 70% | −19% | +90 | 73 |

- **Converting to Elo.** Under the §0.3 model, rising RFP's sliver (improving nodes, g in
  [55, 80] at d = 1) carries 1/1.6 to 1/2.7 of the wrong prunes RFP makes at 80 cp
  [model, `qtot.py`]. Its measured quality cost was −13 Elo, so **RFP's total wrong-prune cost is
  about 20-35 Elo**. A 15-30% cut is +3 to +10 for RFP at zero nps (placeholder range; I4 states
  the measured go rule). Futility and razoring add smaller amounts.

### 0.6 Scale: S, cp, logits; what matching holds

- **The units.** Fork's eval is cp = S × (the net's logit of expected score)
  (accumulator.cpp `out * net.scale / (QA·QB)`; net_file.hpp "S: centipawns per unit of the
  network's output"). S fell 105 → 101 → 92 → 90 → 89 across B0r2 … S512ppr2 at matched mean
  |eval| of about 217-226 cp [read, nets.md].
  - So each better net's logits grew (about 18% from S = 105 to 89), and matching compressed them
    back into the same cp.
  - Search scores are minimaxed static evals, so they scale with S as well. Residuals in cp
    therefore scale as S × (logit error). The margin/σ ratio, the only thing (1) cares about,
    changes with S only through the net's own logit error.
- **What S512ppr2's accuracy implies for the bootstrap-era margins:**
  1. **The cp units are held** (matching), so no rescale is owed from S.
  2. **The core σ probably fell 5-10% against S512r2.** A1: about 1% relative validation loss for
     about +53 Elo of chain; the endgame fix sits inside Syzygy's reach in search. In the
     tail-limited regime that warrants at most about 5% smaller margins at depth 1 and nothing
     deeper. That is far inside SPSA's noise, worth well under 1 Elo [model].
  3. **The bootstrap → NNUE step was the big one, and was never matched.** The bootstrap's
     residual scale is UNVERIFIED. Fork's post-NNUE evidence (§0.4: rising RFP on S512r2, qs-delta
     on B0r1) still says the shallow margins are near optimal.
  4. **The upside is in shape and partition:**
     - the depth profile: σ_d is plausibly sublinear in d while the margins are linear; audit-1's
       wrong-prune share at 80·d fell from 0.31% at d = 1 to 0.03% at d = 6 [read, DC `RfpMargin`];
     - per-node tail risk (§0.5).

### 0.7 Testable predictions of the model (each is used by a proposal below)

- **P1 (regime).** On S512ppr2, the ledger's (I1) fit at RFP candidates, d = 1, puts ≥ 50% of
  wrong prunes at m = 80 in the tail component (beyond 3σ_c). Refuted if a single Gaussian fits
  (tail share < 25%).
- **P2 (core scale).** σ_c at d = 1 is 25-40 cp. Its change from S512r2 to S512ppr2 is −3% to −12%.
  The tail mass π changes by less than ±10%.
- **P3 (shape).** σ_d grows as d^α with α ∈ [0.3, 0.7] over d = 1-6. Refuted if α ≥ 0.9 (then
  linear margins are right).
- **P4 (level).** A global ×0.8 on the pruning margins does not gain (−6 to 0 Elo at STC). A ×1.25
  is within ±3. Refuted (core regime) if ×0.8 ≥ +5.
- **P5 (risk concentration).** At least one free or near-free indicator flags ≤ 20% of RFP
  candidates and holds ≥ 50% of wrong prunes (tail rate hot/cold ≥ 4). Candidates: our ≥ 2
  non-pawn pieces attacked by enemy pawns, or a minor attacking a major; the last move's eval
  swing; TT-refined minus raw eval; TT move a capture; the arriving move a capture or check.
  Refuted if every indicator is below 2x.
- **P6 (LTC direction).** An LTC SPSA of the pruning margins ends below the STC SPSA's values
  (more pruning), because Q shrinks with depth (§0.4). Refuted if the LTC values are higher.
- **P7 (pawn redundancy).** The passive pawn-table fitness on S512ppr2 is ≥ 0.94 (S512r2: 0.919).
  A non-pawn-plus-king key reaches ≤ 0.92. Refuted if pawn ≤ 0.92.
- **P8 (tail-reducing nets).** S512+X's tail mass π at d = 1 is ≥ 20% below S512r2's in the
  ledger. Refuted if < 10%.

---

## 1. Proposals

### I2. Global margin-multiplier ladder: the regime test that sizes the SPSA retune

- **Mechanism.**
  - Two builds with every pruning margin in cp scaled by 0.8 and by 1.25:
    - `RfpMargin` 64 / 100;
    - `FutilityOffset` 80 / 125, `FutilityGrowth` 56 / 88;
    - `NullSurplusPerPly` 240 / 375.
  - Left out:
    - the SEE floors (material units, not eval);
    - the singular margin (search against search, measured on S-512);
    - aspiration (I9).
  - Each runs 2 STC stages against the default, as a ladder under the streamlined policy.
  - The parameters already exist in params.hpp, so this needs **no code**, only changed defaults.
- **Math.**
  - Near the optimum, Elo is quadratic in log(margin).
  - **Tail-limited** (P1) and near-optimal (§0.4): ×0.8 moves depth 1 from 80 to 64 cp. In the
    §0.3 model that raises the marginal wrong-prune rate about 1.8x, at a speed gain of a few
    percent of nodes. Expect −2 to −6. ×1.25 trades about 33% fewer marginal tail wrong prunes
    (e^(−20/125) ≈ 0.85 at d = 1, compounding over depths) for lost savings. Expect −3 to +3.
  - **Core-limited**, with the bootstrap margins about 1.5-2x too wide for the NNUE's σ: ×0.8
    recovers a large part of a quadratic gap. Expect ≥ +5.
  - Two stages (3,200 games) resolve about ±7 Elo (A3 §2.5), so the ladder can separate the two
    regimes but not tune.
- **Theory.**
  - The optimal-margin condition (1).
  - Buro's ProbCut model: margins as quantiles of a regression residual (Buro 1995; KB research.md
    notes that the PDF's text layer was unreadable; details UNVERIFIED).
  - Heinz 1998 on futility margins.
- **Why Fork.**
  - The margins are bootstrap-era (A2 §1.4).
  - S2's estimate of +15-35 from SPSA assumes they are far from optimal, while §0.4 says the
    shallow ones are near it.
  - Item 12's SPSA is the most expensive search item left in §5.6. A3 §2.6 puts about 10 h of
    shards per tune, with more at LTC.
- **Prediction.**
  - P4: ×0.8 ≤ 0 and ×1.25 within ±3 at STC.
  - **Refuted if ×0.8 ≥ +5** (core regime: then SPSA on the margin levels is high value and should
    move earlier, as S2 argues).
  - Both null means the margin SPSA is worth ≤ +5. Spend its games on shape (I3), partition (I4)
    and the non-margin parameters (LMR, LMP, history).
- **Speed cost; compute.** Zero code. 4 STC stages, about 75 GitHub-minutes.
- **Cheapest first experiment.** That is the experiment itself. It could run as filler in any idle
  slot.
- **Kill criterion.** None needed (it is a measurement). Do not adopt either value without the
  normal SPRT.
- **Originality.** The multipliers are round, derived perturbations, not values from any engine.
  The values in range were screened when the originals were (DC).
- **Effort and dependencies.**
  - It replaces idea 34's RfpMargin 40 retest: 40 is ×0.5, past the region the model allows.
  - It reshapes §5.6 item 12's scope.
  - It does not depend on I1.

### I1. Decision ledger: sampled-counterfactual calibration of every eval-gated decision [NOVEL as a process, UNVERIFIED]

- **Mechanism.**
  - A FORK_SEARCH_STATS mode logs every node where an eval-gated decision is reached, i.e. where
    all of its conditions except the margin hold:
    - RFP, futility, NMP's gate, LMP;
    - batch 4's razoring (`HorizonDrop*`) and bad-capture stop.
  - Each row records:
    - the technique and d;
    - the gap g, raw static eval, prune_eval and the TT bound and depth;
    - the improving flag and the last move's eval swing;
    - |e|, phase and the risk bits of P5;
    - ply and move number.
  - **The outcome:**
    - Where the margin does *not* fire, the node is searched anyway, so the outcome (search result
      against β or α) is free.
    - Where it *would* fire, a deterministic sampler (Zobrist key mod 32) skips the prune for 1 in
      32 such nodes. It searches at full depth on the same zero window and logs the
      counterfactual outcome, weighted ×32.
    - All other decisions apply normally, so the tree stays the real tree (not an unpruned one).
  - Positions: replay 120-200 of Fork's own STC games with drift_measure.py's harness. That is one
    engine per game, `ucinewgame`, positions in order, with TT and histories carried as in play,
    which avoids A2 §6's fresh-state bias.
  - Budgets: 200k and 2M nodes per move (the second is an LTC proxy).
- **Math (what is fitted).**
  - Per technique and depth, a censored probit with a tail floor:
    P(wrong | g) = (1 − π_d)·Φ((−g − μ_d)/σ_d) + π_d·½e^(−g/τ_d), by maximum likelihood.
  - Then a heteroscedastic extension, log σ = θ·features, and π_d by risk class.
  - **Sample size.** To estimate a 2% marginal rate to ±20% needs about 1,200 wrong-prune events,
    so about 60k sampled nodes near the margin per depth.
  - The drift run searched about 1.5 × 10⁹ nodes (7,516 positions × 200k) in what amounts to
    minutes per thread. A 2M-node replay is about 1-2 hours on 1-2 threads at low priority.
  - It runs through jobctl beside data generation (searches are node-limited, so load does not
    bias the results; DL 2026-11-05).
- **Theory.**
  - Probit analysis (Bliss 1934; Finney's *Probit Analysis*, Cambridge 1947/1971, UNVERIFIED
    edition).
  - Buro's linear residual model.
  - Counterfactual logging with known propensities, i.e. inverse-propensity weighting (Horvitz and
    Thompson 1952). Fork's sampling is deterministic, so the weight is exact.
  - The method copies Fork's own successes, which measured the *mechanism* (cutoff index, SE
    precision), and avoids the label-and-sweep proxy (A2 §6).
- **Why Fork.**
  - Audit-1's statistic (share of pruned nodes failing low) averaged over all g ≥ M·d, so it could
    not see the marginal rate. It called 40-160 equally safe, and 40 then lost (DC `RfpMargin`).
  - The ledger measures the marginal rate, which is what (1) needs.
  - It feeds I3, I4, I5, I6, I7 and the SPSA's starting points and ranges.
  - It is re-runnable at each net promotion (bench moves 13.9-14.6 M with the same search across
    nets, A2 §3.3).
- **Prediction.**
  - P1, P2 and P3, with σ̂_1 reported with a bootstrap CI over games.
  - The marginal wrong-prune rate at the current margin falls with depth by ≥ 3x from d = 1 to
    d = 5 (audit-1's average fell about 10x).
  - Refuted if it is flat.
- **Speed cost; compute.** Nothing ships. Local CPU of about 1-3 h total, no GitHub.
- **Cheapest first experiment.**
  - RFP and futility only, 120 games, 200k nodes.
  - From that: σ̂_d, π_d, tail share at the margin, and each P5 indicator's concentration.
- **Kill criterion.** For the follow-ups:
  - every depth's current margin within ±15% of the fitted K·σ̂_d shape **and** every indicator
    concentration < 2x → close I3 and I4;
  - margins go to plain SPSA.
- **Originality.** A Fork tool. CPW and the KB describe prune counters but no counterfactual
  calibration (UNVERIFIED whether any engine documents one). New names need the usual name screen.
- **Effort and dependencies.**
  - About 2 days, reusing drift_measure.py's game harness and FORK_SEARCH_STATS.
  - Before item 12. Parallel to batch 4 (it also gives batch 4's eval-gated margins
    `HorizonDropMargin` and `BadCaptureStopMargin` data-derived starting values instead of ladder
    guesses).

### I4. Tail-risk-classed margins: a mean-preserving re-partition by a cheap tactical-risk bit

- **Mechanism.**
  - At an RFP candidate, compute one cheap risk bit. Use a raised margin m_d + Δ_h on "hot" nodes
    and a lowered margin m_d − Δ_c on "cold" ones.
  - Δ_c is set so the bench count of RFP cuts is unchanged (`counters.rfp_cuts`). The SPRT then
    tests the bit's information, not a change in aggressiveness. That is S1 §7.2.1's
    mean-preservation discipline.
  - The same for futility, with the risk read from the other side.
  - The bit is chosen by the ledger (I1) from candidates, cheapest first:
    - (a) **pawn fork bit**: ≥ 2 of the side's non-pawn pieces are attacked by enemy pawns (two
      shifts, an AND, a popcount). Also a minor-on-major bit (enemy knight attacks from the attack
      table on our queen or rook);
    - (b) the last move's static swing |e_ply + e_(ply−1)| above 2σ̂_1 (free: both evals sit in the
      frames);
    - (c) |prune_eval − static_eval| above 2σ̂_1 (free);
    - (d) the TT move is a capture (free);
    - (e) the arriving move was a capture or gave check (free).
  - A qsearch arm, idea 46 rank 8 reduced to its cheapest form:
    - when the side to move has ≥ 2 non-pawn pieces attacked by pawns, stand-pat is lowered by the
      cheaper attacked piece's material value;
    - a material constant, not a tuned margin;
    - only if the ledger's qsearch rows show such stand-pats wrong ≥ 5x more often than others.
- **Math.**
  - §0.5: at equal prune count, a bit flagging 10-20% of nodes with 3.4-5.4x the mean tail rate
    cuts wrong prunes by 25-39% if exact and 11-21% at 70% accuracy.
  - RFP's total wrong-prune cost is about 20-35 Elo (§0.5).
  - So the RFP arm is +2 to +7 [model]. Futility is smaller: Fork's futility keeps checking quiets,
    and its tail is the side's own quiet threats.
  - **Bit cost:**
    - (a) is about 10 cycles at candidate nodes only, < 0.1% of a 1,300-cycle node (idea 46
      judge's cycle count);
    - (b)-(e) are free.
- **Theory.**
  - Heteroscedastic decision thresholds. Aleatoric against epistemic uncertainty (Kendall and Gal,
    "What Uncertainties Do We Need in Bayesian Deep Learning?", NeurIPS 2017) is why core-only
    signals underperform here.
  - Mixture-model tail risk.
  - Public engines use risk-like gates (S2 §4.4: RFP margin raised when the correction is large;
    KB §3.16: RFP skipped when the TT move is quiet, and similar). The idea 46 judge rates
    "uncertainty-scaled margins" as partly public. What I add is the *tail-class* framing, the
    mean preservation and the ledger-based choice.
- **Why Fork.**
  - Fork's eval-gated loosenings fail just past break-even (§0.4). A re-partition that cuts
    wrong prunes at equal savings moves a ρ of 1.4k toward 1.0k. That is the lever that turns
    near-misses into wins.
  - S-512 has no threat inputs, so hanging-piece tactics are exactly its tail (A1 §3.5 item 1).
  - The bits avoid the attack-map cost that sank threat-aware ordering (−6.1; A2 §2.2).
- **Prediction.**
  - P5 first.
  - Then: the RFP arm passes STC [0, 3] at +2 to +5 with bench cuts within ±2%. Futility +1 to +3.
    The qsearch arm 0 to +2.
  - Refuted if the arm with the best P5 indicator reaches H0 at both ladder values of Δ_h.
- **Speed cost; compute.** ≤ 0.1% nps. 1 ladder (2 Δ values × 2 stages) + 1 SPRT per arm.
- **Cheapest first experiment.** I1's RFP rows: the concentration table per indicator. No build
  needed.
- **Kill criterion.**
  - No indicator reaches ≥ 2x concentration at ≤ 20% flagged → do not build.
  - H0 at both Δ values → drop that arm.
- **Originality.** Bits (a)-(e) are generic chess concepts (CPW: attack maps, pawn attacks). Δ
  values come from the ledger's fitted τ and the equal-count rule, not from any engine. Screen
  names and constants as usual.
- **Effort and dependencies.**
  - 3 days after I1.
  - Better after fractional depth only for its LMR extension (a ½-ply less reduction on hot
    nodes).
  - Replaces idea 46 rank 7's "volatility table" (I5 explains why a threat *key* churns) and
    folds in rank 8.

### I3. Concave, σ_d-indexed margin shapes

- **Mechanism.**
  - Replace the linear profiles with m_d = K·σ̂_d:
    - RFP 80·d;
    - futility 100 + 70·d;
    - later razoring 250·d and bad-capture stop 150·d (batch 4 placeholders).
  - σ̂_d is the ledger's per-net, per-depth table and K is one multiplier per technique.
  - Before I1, a placeholder shape for a ladder: keep d = 1-2 as now and halve the slope beyond
    d = 2. For RFP that is 80, 160, 200, 240, 280, 320 against 80 … 480.
- **Math.**
  - Under (1) with q_d constant across depth (C_d and L_d both growing with subtree size), m*_d ∝
    σ_d.
  - If σ_d ∝ d^α with α = 0.5, a linear margin is √d times too conservative at d relative to
    d = 1: 2.4x at d = 6 [derived].
  - Audit-1's numbers fit that direction: under 80·d the wrong-prune share fell from 0.31% (d = 1)
    to 0.03% (d = 6) [read], which is not a constant tail probability.
  - If L_d grows more slowly than C_d, q_d grows with depth and the case for concavity is stronger.
    If L_d grows faster, it is weaker. So the sign is plausible and the size must be measured.
- **Theory.** Buro's depth-pair regression (σ depends on the depth pair). Heinz's extended futility
  (pre-frontier margins larger than frontier ones, not proportionally larger: UNVERIFIED reading
  of the paper's figures).
- **Why Fork.**
  - Every loosening tested so far acted at d = 1-2 (rising RFP is 31% of the margin at d = 1 and
    5% at d = 6). The deep region is untested.
  - Selectivity gains more at LTC in Fork (IIR, tier 1; §0.4).
  - K·σ̂_d also makes the margins transferable: at a net promotion, re-measure σ̂_d (I1) and keep K.
- **Prediction.**
  - P3, then a concave RFP shape passes STC [0, 3] at +1 to +4. LTC is the same or more (P6).
  - Refuted if H0 at both ladder shapes, or α ≥ 0.9 in I1.
- **Speed cost; compute.** Zero nps (a 7-entry table read). Ladder 2 × 2 stages, SPRT, then LTC
  (selectivity is plausibly LTC-sensitive).
- **Cheapest first experiment.** I1's σ̂_d table (local). If it is unavailable, the placeholder
  shape's 2-stage ladder.
- **Kill criterion.** Above. Also, if I2 shows ×1.25 > 0 (margins too aggressive overall), lower
  the priority.
- **Originality.** The shape comes from Fork's own measured σ̂_d. The placeholder slope halving is
  a derived perturbation. Screen the resulting table.
- **Effort and dependencies.**
  - 1-2 days.
  - **It also changes item 12's parametrization:** one K per technique (about 4 parameters)
    instead of offset, slope and max depth each (about 10). SPSA resolves fewer parameters better
    (S1 §6: "few values at once").

### I5. Correction tables re-scoped: rank them passively on S512ppr2 before any SPRT

- **Mechanism.** Re-run tools/drift_measure.py's passive method (learning on, not applied; Fork's
  own STC games; game replay), extended to three keys:
  1. the existing pawn key;
  2. a **non-pawn key per side that includes the king square**. S-512 is mirrored with no king
     buckets, so king-relative error (king safety) is systematic within a game;
  3. a **continuation key** (the arrival slots of plies −1 and −2, already in the frames).

  Four fitness readings for each:
  - (i) the existing summed-error fitness;
  - (ii) fitness on the tail bins only (|r| > 100 cp);
  - (iii) **decision accuracy**: at I1's RFP and futility rows, how often the corrected eval's
    decision matches the outcome where it differs from the raw one;
  - (iv) the same at 2M nodes (LTC proxy).

  Plus a **count-based gain** arm [NOVEL, UNVERIFIED]:
  - each slot keeps a small update count n;
  - the step is max(1/(n+n0), w_floor), the Kalman/empirical-Bayes gain for a stationary bias;
  - a new structure is corrected quickly while old ones stay stable.

  Plus the drift table's own nps cost (bench/ab.py on tier2/drift with the switch on against
  off). It was never measured (A2).
- **Math.**
  - **Online bias correction.** r = b_key + u, with b ~ (0, τ_b²) systematic for the game and u
    noise of variance σ_u² (core plus tail).
  - An EMA with step w estimates b with variance about w·σ_u²/2. The corrected residual's variance
    is σ_u² + wσ_u²/2 (plus lag) against the raw σ_u² + τ_b².
  - **Fork's drift run** chose the slowest learning tried (max step 4/256, still at the grid's
    edge), with MAE fitness 0.919. MAE scales like σ, so the variance ratio is about 0.845:
    τ_b²/(σ_u² + τ_b²) ≈ 0.15-0.18 for the pawn key on S512r2.
  - Slow learning winning means σ_u² ≫ τ_b²: a bias small against per-node noise. A count-based
    gain helps exactly there (fast early, low floor).
  - **With pawn links the net models structure globally,** so τ_b² for the pawn key should
    shrink (P7).
  - **The Elo link** is §0.3's: correction reduces mostly core error, so its pruning value is
    about 1/4-1/3 of the Gaussian estimate. That is why the decision-accuracy fitness (iii) and the
    tail-bin fitness (ii) are the ones to rank by.
  - The continuation key groups "after this move the eval is off", i.e. game-specific tactical
    motifs, so it is the one key that can reach the tail.
- **Theory.**
  - Correction history as public concept (CPW "Static Evaluation Correction History"; KB §3.23;
    S1 §4, S2 §4.4).
  - Empirical-Bayes shrinkage (Robbins 1956; Efron and Morris, JASA 1975).
  - The Kalman gain for a static or random-walk bias (Kalman 1960).
  - An analogue is test-time adaptation of a fixed model to a narrow local distribution (Sun et
    al., "Test-Time Training", ICML 2020; analogy only).
  - Why it gains more at LTC: deeper search gives less noisy targets, so σ_u falls, and positional
    errors, the ones keys capture, dominate at depth (§0.4) [inferred]. Seer's 3x LTC ratio (KB
    §1 lesson 3) agrees.
- **Why Fork.**
  - The pawn table was undecided at LTC on S512r2, before the links (SL 2026-11-02).
  - §5.6 defers further tables until after SPSA.
  - The passive measurement costs no GitHub time and can run now beside data generation.
  - **King-inclusive non-pawn keys** target S-512's one structural blind spot (no king buckets;
    H-512's king regions failed only as a cold-trained architecture, A1 §9 B7).
- **Prediction.**
  - P7.
  - The continuation key gives the best tail-bin fitness (ii) of the three.
  - Fitness at 2M nodes is ≥ 0.01 better than at 200k for every key (the LTC proxy).
  - The drift table costs 0.5-2% nps.
  - Refuted if pawn ≤ 0.92 on S512ppr2 (then the links did not absorb it) or if no key improves
    with budget.
- **Speed cost; compute.**
  - Per table, one probe per evaluated node (prefetchable with the TT) plus key upkeep in make and
    unmake (2 XORs per move for the non-pawn key).
  - At 1.5 Elo per 1%, each table must stay under about 1% nps or bring > 1.5 Elo.
  - Passive measurement: local CPU, about 2-4 h per key at 200k, ×10 at 2M.
- **Cheapest first experiment.** The pawn key on S512ppr2 at 200k (the tool exists, about an
  hour), plus the drift table's bench/ab.py nps (30 min quiet).
- **Kill criterion.**
  - Every key's decision-accuracy gain (iii) < 2% of flipped decisions → shelve all correction
    tables until Phase 6, where thread sharing is the real gain (idea 17; S2 item 10: +20 to +44 at
    8-32 threads elsewhere).
  - An LTC SPRT of the best key ending H0 → stop.
- **Originality.**
  - The keys are generic CPW variants (credit as listed there).
  - The count-based gain is my proposal; check novelty against public write-ups before claiming it.
  - Do not reuse other engines' totals or limits: the drift table's 256 already matched others and
    was kept with credit (DC), and new constants come from the passive grid.
- **Effort and dependencies.**
  - 2-4 days: the passive tool exists, and the keys are new code behind switches.
  - **Reorders §5.6 item 14 (correction tables):** the measurement moves before SPSA, while the
    SPRTs stay after it. Drop the material and threat-keyed tables (S1 §7.3, S2 §6; a threat key
    changes almost every move, so slots never accumulate updates).
  - Apply corrections to prune_eval only, not to the qsearch stand-pat, unless an arm shows
    otherwise. The stand-pat form was circular in the drift measurement (docstring: 0.68 fitness
    from self-reinforcement).

### I7. Improving as a measured mean shift, mean-preserving, on prune_eval

- **Mechanism.**
  - Compute "improving" from prune_eval, the quantity RFP actually uses. Rising RFP compared raw
    evals (A2 §2.2).
  - Measure in the ledger the residual shift Δμ_d between improving and non-improving nodes, and
    any σ ratio.
  - Set margins m_d ∓ Δμ_d/2 for the two classes, with no tuned constant: the offset *is* the
    measured shift, and it is mean-preserving by construction.
  - For LMP, split the existing quiet-cutoff-index histogram (FORK_SEARCH_STATS
    `quiet_cutoff_index`) by improving, and set each class's allowance by LMP's own 1% rule (DC
    `LmpQuietAllowance`).
- **Math.**
  - Rising RFP moved only one class (−25 cp on improving nodes): a net loosening, ρ = 214 (§0.4).
  - A re-partition at constant prune count costs nothing in speed. Its gain is the
    wrong-prune reduction from separating two residual distributions shifted by Δμ.
  - With Δμ = 0.3σ_c and the tail share at 80 cp, that is about a 5-10% cut [model], so +1 to +3
    for RFP.
  - LMP: if the non-improving 1% index is 0.7x the improving one, separate allowances prune about
    a quarter more quiets on non-improving nodes at the same 1% bound.
- **Theory.** CPW "Improving"; KB §3.15 (graded improving; first LMP use passed STC and LTC
  elsewhere, S1 §7.1.c). The KB leaves raw against corrected open (§6 item 9), and Fork's prune_eval
  is its "refined" case.
- **Why Fork.** The flag's best-evidenced uses elsewhere (LMP, LMR) are untested in Fork. The one
  use tested was the wrong form: one-sided, on raw eval, and a flat cp offset over depth.
- **Prediction.**
  - Δμ ≥ 0.3σ̂_1 at d ≤ 3 → the RFP re-partition passes [0, 3] at +1 to +3 with bench cuts within
    ±2%.
  - The LMP split gives a non-improving 1% index ≤ 0.75x the improving one.
  - Refuted if Δμ < 0.15σ̂_1 (do not build the RFP use) or the indices differ by < 10%.
- **Speed cost; compute.** Zero (evals are in the frames). Histogram split: one stats bench. SPRT
  per use.
- **Cheapest first experiment.** The LMP histogram split (one stats bench, minutes).
- **Kill criterion.** As refuted. Two H0s among the RFP and LMP uses → drop the flag (S2 §4.5's
  rule).
- **Originality.** Generic CPW concept. The offsets are measured.
- **Effort and dependencies.** 1 day + SPRTs. In batch 4's slot for the improving uses (DL
  2026-11-02's order).

### I6. Margin credit for tail-reducing nets [NOVEL, UNVERIFIED]

- **Mechanism.**
  - Run the ledger (I1) on each candidate net, especially threat-type ones (idea 46's designs, an
    incremental S512cl).
  - A net that cuts the tail mass π deserves smaller margins: m* = τ·ln(π/2q) falls by
    τ·ln(π_old/π_new), bounded below by the core's ≈ 2.5σ_c.
  - The fixed-node screen and STC SPRT run with the default's margins and so under-credit it.
  - Before such a net's STC SPRT, re-derive its margins as K·σ̂_d (I3), or at least report the
    expected credit.
- **Math.**
  - From §0.3's model, a 20% cut in π at d = 1 lowers the marginal wrong-prune rate at 80 cp by
    15-18%, and allows m*_1 about 5-10 cp lower.
  - Over RFP's 20-35 Elo of wrong-prune cost, that is +2 to +5 of hidden value [model].
  - It does **not** rescue S512+X (−30 STC, a gap of about 30 Elo of speed, A1 §4). It matters for
    idea 46's "0 to +5" class, where the go/kill line sits inside that range.
- **Theory.** §0.3. The KB already says ProbCut and other margins must be refit per evaluation
  (KB T31 pitfall). I add *which* error to refit on.
- **Why Fork.** Idea 46's ranked designs are threat-type (tail reducers) with expected gains of 0
  to +5, and A3 §1.4's speed-adjusted screen leaves this term out.
- **Prediction.** P8 on the existing S512+X net (no training needed). Also P2: S512ppr2's π is
  within ±10% of S512r2's while its core σ falls.
- **Speed cost; compute.** Local, about 1 h per net.
- **Cheapest first experiment.** I1's RFP rows on S512r2 against S512+X (both nets exist).
- **Kill criterion.** P8 refuted (< 10% tail cut) → threat inputs do not reach the margin-binding
  error, and the credit is dropped from idea 46's accounting.
- **Originality.** A process proposal; no constants.
- **Effort and dependencies.** 0.5 day per net once I1 exists. Feeds idea 46's experiment rules 3
  and 4 (the residual study's volatility criterion "top quintile ≥ 2x bottom" is the same statistic
  as P5).

### I8. TT-eval refinement hygiene

- **Mechanism.**
  1. **Stand-pat refined only by main-search entries** (TT depth ≥ 1). B-4 refined the stand-pat by
     any TT bound and lost (−4.11 ± 3.93, H0). Most qsearch TT entries are depth-0 qsearch results
     from window-dependent searches, so the "refinement" feeds the qsearch's own bounds back into
     itself (A2's diagnosis).
  2. In negamax, prune_eval is today refined by entries of **any** depth, including depth-0
     qsearch entries (searcher.cpp: no depth condition). The ledger splits refined decisions by
     source depth (0 against ≥ 1) and checks whether depth-0 refinements help (they carry
     capture-resolved values, a free tail reducer) or hurt.
- **Math.**
  - A depth-0 lower bound s > e at an RFP node replaces e with a capture-resolved value. In §0.3's
    terms it removes the capture part of the tail at that node.
  - An upper bound below e at a futility node does the same.
  - Expected: refined-by-depth-0 decisions at least as accurate as raw at equal prune counts.
- **Theory.** KB §3.24 (T50; Lefler 2010 thread; variants restricted to PV or to "more
  informative" entries; the instability caveat).
- **Why Fork.** `UseTtEvalRefine` ships by owner exception (SPRT stopped undecided, +14.6 ± 17.8;
  testing.md), so its form was never verified. B-4's failure has a specific, fixable mechanism.
- **Prediction.**
  - (1) passes [−3, 0] and lands at 0 to +3.
  - (2): the ledger shows depth-0 refinements improve decision accuracy by ≥ 5%. Refuted if they
    worsen it; then try a depth ≥ 1 condition for prune_eval too.
- **Speed cost; compute.** One comparison. One SPRT for (1); (2) is ledger data.
- **Cheapest first experiment.** (2) from I1's rows, free.
- **Kill criterion.** H0 on (1) → stays off for good.
- **Originality.** Generic KB concept; the depth condition is Fork's own choice.
- **Effort and dependencies.** 0.5 day. Belongs to the re-validation queue (B-4 is already listed
  there; DL 2026-11-06): run the depth ≥ 1 variant instead of a plain B-4 retest.

### I9. Aspiration windows and time management in calibrated units

- **Mechanism.**
  1. **Re-measure aspiration** with Phase 3's own method (bench, depth ≥ 5, p90 of |score −
     previous|) on S512ppr2. Also bin it by |previous score|.
     - If p90 grows with |score|, use half-width w = w0 + c·|previous| (heteroscedastic), with w0
       and c from the fit.
  2. **A design rule for A2's O1 time management** (Phase 5 or earlier, the owner's call): express
     score-trend and falling-eval terms in **expected-score units**, Δp = σ(new/S) − σ(old/S),
     not in cp.
     - A 30-cp drop at +20 is a real change in win chance; at +500 it is not.
     - S is the net's own calibration (cp per logit), so the rule carries across net promotions.
- **Math.**
  - Logit errors near zero map to cp linearly, but the net's training in sigmoid space weighs
    decided positions lightly (A1 §3.5 item 5). So cp volatility should grow with |eval|.
  - The optimal half-width is about z·σ_Δ(|score|). A fixed 12 cp re-searches more at large
    |score| and wastes width near zero.
- **Theory.** Calibration and temperature scaling (Guo et al., "On Calibration of Modern Neural
  Networks", ICML 2017): S is a temperature. KB §3.6 (aspiration).
- **Why Fork.** 12 cp was measured on the bootstrap at depth 8-14 (DC), before the NNUE, before tier
  2 and with a different score distribution.
- **Prediction.**
  - p90 at depth ≥ 5 on S512ppr2 differs from 12 cp by > 25%.
  - p90 in the |score| > 300 band is ≥ 2x the < 100 band.
  - Refuted if both differences are within 15%; then keep 12 and skip this.
- **Speed cost; compute.** Zero. One bench run (minutes). Ladder only if the measurement moves.
- **Cheapest first experiment.** The bench measurement.
- **Kill criterion.** As refuted.
- **Originality.** Fork's own rule and measurement. The widening rule stays as it is.
- **Effort and dependencies.** 0.5 day. The TM half sits inside O1, with no separate test.

---

## 2. Critique of the current plan in my domain

1. **§5.6 item 12, the SPSA retune: size it before it runs, and reparametrize it.**
   - The plan retunes "every eval-dependent margin", and S2 expects +15-35.
   - Fork's own evidence (§0.4) says the shallow margins are near optimal: loosenings fail at ρ
     about 1.1-1.4k, and RFP 40 lost in a gauntlet. The model says better nets barely move them
     (§0.3, §0.6).
   - **Run I2 first** (4 STC stages). If it is null, cap the margin share of SPSA and put its games
     on LMR, LMP and history scales, where Fork is "under-informed, not over-pruned" (A2 §3.1).
   - **Parametrize margins as K·σ̂_d** (I3): one K per technique (RFP, futility, NMP surplus,
     razoring, bad-capture stop) instead of offset, slope and max depth each. That cuts about 10
     margin parameters to about 5, in line with S1 §6's "tune few values".
   - **Tune pruning margins at both STC and LTC and expect LTC lower** (P6). This is S1's
     scaling-class split, applied to margins in the direction §0.4's quality shrink predicts.
2. **§5.6 item 14, correction tables after SPSA: keep the SPRTs there, move the measurement
   forward.**
   - The passive ranking (I5) costs no GitHub time and decides which table, if any, to build.
   - Drop "material" (removed elsewhere, S1 §7.3, S2 §6) and "threat" (keys change almost every
     move, so slots never accumulate updates).
   - Keep "pawn" off unless S512ppr2's passive fitness is ≤ 0.92 (P7).
   - Add the king-inclusive non-pawn key, justified by S-512's lack of king buckets.
3. **Batch 4's eval-gated items** (razoring `HorizonDropMargin` 250·d, bad-capture stop 150·d,
   double-extension margin 30): two-to-three-value ladders on these are near-blind.
   - A3 §2.6: the ladder picks the best of 3 values only 48-62% of the time.
   - The model says these margins are tail-limited, with flat optima.
   - Seed their values from I1's σ̂_d (a data-derived starting point, which also serves the
     originality rule better than a ladder guess) and test them last. Razoring's public value is
     about 1-2 Elo (S1 §7.3).
4. **Idea 46 ranks 7 and 8** (threat-keyed correction and volatility tables; stand-pat check).
   - Replace rank 7's threat *key* with I4's tail-risk *class*: the same goal without key churn,
     and nearly free bits instead of attack maps.
   - Fold rank 8 into I4's qsearch arm, gated on the ledger's frequency × error.
   - Reuse rule 3's criterion ("top quintile ≥ 2x bottom") as P5's concentration test, so one
     measurement serves both.
5. **Idea 34 (RfpMargin 40): retire it** as a standalone test. It is ×0.5 at every depth, outside
   what §0.4 allows. I2's ×0.8 point tests the same direction more safely.
6. **The re-validation queue's B-4 retest:** run I8's depth ≥ 1 variant instead. Plain B-4 has a
   known mechanism for losing.
7. **The fixed-node and speed-adjusted screens for new nets** (A3 §1.4) should carry I6's note: a
   tail-reducing net is screened with margins tuned for a tail-heavier net. The term is small (2-5
   Elo) but sits exactly at idea 46's go/kill lines.
8. **No reordering argued for fractional depth** from my domain. I4's LMR extension (about ½ ply on
   hot nodes) needs it, and nothing else here does.

---

## 3. What I could not verify

- **The residual distribution.**
  - Mean |r| = 36.4 cp comes from drift_measure.py's 3-game pipeline test (bound-clipped, learning
    nodes).
  - p99 < 280 cp comes from the 120-game drift-off run's exact results.
  - Both are S512r2, at mixed depths, not RFP candidates by depth.
  - The mixture fits in §0.2-0.3 are illustrative.
  - The run's 10-cp histogram bins would sharpen them; I did not find the output files on this
    machine (looked in ~/fork-data on Windows and in WSL; nothing found by name).
- **The speed/quality decomposition** uses bench node ratios at fixed depth, not nodes in games, and
  k fitted on networks (A1) applied to search features. IIR's LTC quality shrink rests on one LTC
  SPRT (±6.7).
- **RFP's total wrong-prune cost (20-35 Elo)** is a model inference from rising RFP's sliver. The
  gap distribution (exponential, mean 80-200 cp) is assumed.
- **That L_d (cost of one wrong prune) grows more slowly than subtree size**, which decides I3's
  sign at depth. Not measured.
- **The drift table's nps cost** (it may explain part of its LTC null) was never measured.
- **Buro 1995's exact model and figures:** the KB records the PDF's text layer as unreadable. My
  use (linear regression residual, threshold as quantile) is the standard description, UNVERIFIED
  against the paper.
- **Citations marked UNVERIFIED:** Finney's edition; Heinz's figure reading; the test-time-training
  analogy. Kendall and Gal 2017, Guo et al. 2017, Horvitz and Thompson 1952, Robbins 1956, Efron
  and Morris 1975 and Kalman 1960 are cited from memory as standard references (titles and venues
  believed correct, not re-fetched).
- **Whether any engine documents counterfactual calibration of pruning decisions** (I1) or a
  count-based correction gain (I5), which bears on the NOVEL labels.
- **That S512ppr2's gains are "core" rather than "tail"** is inferred from what changed (links,
  endgame slice), not measured. P2 tests it.
- **Every Elo range above is a model placeholder.** None is a Fork measurement.


---

# B12. Cross-domain wildcard (W)

## B-W: cross-domain wildcard proposals (Phase 4 think tank, Phase B)

**Summary.** This file brings in ideas from outside alpha-beta engine practice: machine-learning
optimisation, mixture-of-experts theory, variance reduction from RL, metareasoning and best-arm
identification. Each one is tied to a measured Fork weakness.

One new reading of evidence Fork already has drives three of the proposals. In the
standard warm retrain, validation loss *averaged over the whole LR-1e-4 half* (0.019371,
seed 1) is **worse than the starting net** (0.019305). All of the gain arrives after the drop
to 1e-5 (mean 0.019159 over superbatches 271-360). Within each phase the loss wanders with a
lag-1 autocorrelation of about 0.8. Its standard deviation is 1.0e-4 at 1e-4 and 3.6e-5 at
1e-5, a ratio of 2.8, close to √10 (COMPUTED from the four `val.txt` files of the g3s2 run).
So Fork's nets are limited by **optimiser temperature and schedule**, not by data. This
supports A1's B1 and adds three things: **iterate averaging** (W5), a **warm-up/stable/decay
"trunk" schedule** for the generational lineage (W3), and a criterion for choosing checkpoints
that is free of the optimizer's curse.

The other proposals come from different domains:
- **W2** treats the 8 phase buckets as a hard-gated mixture of experts. It picks better
  gates with a frozen-accumulator linear probe, which runs on CPU in minutes, before any GPU
  training. Speed cost is about zero.
- **W4** derives **lower-variance value targets** from Fork's own stored trajectories:
  λ-returns and an inverse-variance weight on the result. KataGo states the mechanism
  directly: "the game outcome value target is highly data-limited". Positions inside one game
  share one result, so the result half of Fork's target carries about 35x fewer independent
  samples than its position count suggests.
- **W1** treats time management as a value-of-computation problem. It fits a
  best-move-change model on Fork's own iteration logs. A concave-utility derivation shows
  that Fork's static schedule wastes about 0.21 e-folds of thinking time at TCEC's 30'+3",
  against 0.07 at the STC and LTC test controls. No current test can see the difference.
- **W6** replaces per-feature SPRTs-to-verdict in the search queue with **sequential
  halving** (fixed-budget best-arm identification). In simulation it keeps A3's best
  Elo per stage (3.4x the current policy) and cuts the false-accept rate from 10% to about 3%.
- **W7** and **W8** are cheaper capacity and ordering levers, each gated by an offline census.

| ID | Title | Expected Elo at LTC (range) | Effort (days) | Confidence | NOVEL? |
|---|---|---|---|---|---|
| W1 | Value-of-computation time management fitted to Fork's own iteration logs, plus a horizon set by a quantile of game length | +8 to +18 (LTC); TCEC-shape upside +5 to +20 more | 3-4 (plan change: Phase 5 to Phase 4) | medium | NOVEL (method) |
| W2 | Output experts chosen by frozen-accumulator linear probes (MoE view of the phase buckets) | +3 to +12 | 2-4 (CPU probe 1, Kaggle fine-tune 1, tests) | medium-low | NOVEL (method) |
| W3 | Warm-up/stable/decay "trunk" schedule for the generational lineage, with three diagnostic arms | +5 to +15 (overlaps A1 B1; not additive with it) | 1 Kaggle session + 2 days | medium | partly (application) |
| W4 | Lower-variance value targets: λ-returns from stored scores, or an inverse-variance result weight; derived from an offline variance study | +3 to +12 | 1 (offline) + 1 Kaggle session + tests | low-medium | NOVEL (as far as I know) |
| W5 | Iterate averaging (EMA/LAWA) and two-seed "soups"; final-EMA checkpoint replaces best-of-360 | +1 to +4 directly; also saves compute for W3 | 0.5-1 | medium-high (loss), medium (Elo) | no (known ML, new here) |
| W6 | Sequential halving for the search queue (batch 4, item 8, idea 23's funnel) | enabler: about 3x Elo per GitHub stage vs today, P(false accept) about 2-4% | 0.5 (policy) | high (math), medium (prior) | NOVEL for engine testing (UNVERIFIED) |
| W7 | Width frontier: low-utility neuron census, then structured narrowing (or function-preserving widening) | 0 to +8 | 1 (census) + 2-3 | low | no (known ML) |
| W8 | Depth-gated policy ordering read from the existing accumulator (idea 16 reborn) | 0 to +8 | 6-10 (plan change: idea 16 is parked) | low | NOVEL (combination) |

Labels: **READ** = from a file (cited). **COMPUTED** = my arithmetic on read numbers (the
scripts were short inline Python runs; no repo file was changed). **INFERRED** = my
interpretation. **UNVERIFIED** = unsure. A1/A2/A3 = Phase A files; S1/S2 = the clean-room
surveys; SL = docs/history/phase-4/sprt-log.md; NM = docs/nets.md; HO = HANDOFF.md.
The rate for speed is A1/A3's **k ≈ 150 Elo per e-fold of nps at STC (1.5 Elo per 1%)**. The
rate for loss within one architecture is A1's **6-10 Elo per 1e-4**.

---

## 0. The new evidence these proposals rest on (COMPUTED, READ files)

Source: `~/fork-data/kaggle/g3s2-out/result/<run>/val.txt` (item 7's runs; validation on the
first 20,000 kept positions of g3s2-val, the same set for all four runs). Recipe
(retrain_g3s2.py, READ): AdamW, batch 16,384 x 305 per superbatch (5 M samples), 360
superbatches, LR × 0.1 after superbatch 180. Warm runs start at 1e-4 from S512+PP (0.019305
on this set). Scratch runs start at 1e-3.

| Run | Superbatches 1-180: mean / sd / min | 181-270 mean | 271-360: mean / sd / min | lag-1 autocorrelation |
|---|---|---|---|---|
| warm s1 | **0.019371** / 1.03e-4 / 0.019104 | 0.019181 | **0.019159** / 3.8e-5 / 0.019089 | 0.66 / 0.82 |
| warm s2 | 0.019377 / 0.98e-4 / 0.019151 | 0.019203 | 0.019167 / 3.6e-5 / 0.019100 | 0.68 / 0.78 |
| scratch s1 | 0.021244 / 6.9e-4 | 0.019814 | 0.019690 / 1.0e-4 / 0.019476 | 0.79 / 0.63 |
| scratch s2 | 0.021438 / 6.9e-4 | 0.020074 | 0.019794 / 9.6e-5 / 0.019559 | 0.79 / 0.62 |

What this shows (INFERRED):
1. **At LR 1e-4 the warm net is, on average, worse than where it started** (0.019371 against
   0.019305). A1 §5.1 describes "a smooth fall to 0.01912 by superbatch 180". That holds at
   the sampled point 180, but the curve swings between 0.0191 and 0.0195 throughout the
   first half. The 1e-4 phase carries the new data's information at a high noise
   "temperature". The 1e-5 phase turns it into lower loss.
2. **The fluctuation ratio between phases is 2.8, close to √10.** An iterate's spread around
   a minimum grows as √η under a constant learning rate. A loss wander that scales like √η
   means a term linear in the displacement dominates: the validation set's own gradient at
   the training optimum is not zero, which fits A1's "validation is an easier mix". That term
   has mean zero, so **averaging the iterates removes it**.
3. **The quadratic (mean) excess is bounded.** The 10x LR drop lowered the mean by 2.1e-4.
   Even if all of that were excess proportional to η, the excess left at 1e-5 is at most
   about 2.1e-4 / 9 ≈ 2.3e-5. Continued learning also contributes to the 2.1e-4, so this is
   an upper bound.
4. **Best-of-360 is optimistic by about 1.9σ.** The kept checkpoint (0.019089) sits about
   7e-5 below its own phase mean. This is the optimizer's curse A1 §3.2 named, now
   quantified.

---

## W1. Value-of-computation time management fitted to Fork's own iteration logs [NOVEL] (as a method)

- **Mechanism.** Two separable parts.
  - **(a) When to stop the current move.** After each iteration, estimate p = P(the best
    move changes if the search continues one more iteration). Use Fork's existing per-root
    counters (`root_moves_[i].nodes` and `.share`, A2 §4) plus best-move stability and the
    score delta. Continue while p · G > c · Δt, where Δt is the expected next-iteration
    cost: g ≈ 1.66 times the elapsed time, Fork's measured growth. c is the price of time
    under the clock schedule. G is the expected gain when the move changes, and it is
    absorbed into c. This is Russell and Wefald's value-of-computation rule. The point of
    the method is that **the soft-limit multipliers come from a logistic fit to Fork's own
    logs**, so they are measured rather than copied from other engines' TM factors. That
    serves non-negotiable 6 directly.
  - **(b) How much of the bank a move may plan for.** Replace the fixed horizon (clock/30)
    with a horizon H set to a high quantile of the remaining-game-length distribution,
    conditioned on cheap features (move number, material). Section (b) of the derivation
    shows why a quantile and not the mean.

- **Math / derivation.**
  - *(b), concave utility.* Take A1's speed model at face value: a move's Elo-value grows as
    k·ln t. Maximise Σ_i a_i ln t_i subject to Σ_i t_i ≤ B + N·inc. The Lagrangian gives
    t_i ∝ a_i, so **time should be proportional to a move's importance** and uniform when
    importances are equal.
    - Let the game end at move i with survival S(i), and spend only on moves reached. The
      objective becomes Σ S(i) a_i ln t_i, with S(i) weighting the budget too, so uniform
      spending stays optimal.
    - The binding constraint is not running out in *long* games. So the planned horizon
      should be a high quantile of the remaining length, not 30 and not the mean.
  - Fork's present schedule, simulated (COMPUTED). Spend per move = (clock − 0.1 s)/30 +
    ¾·inc, optionally times A2's mean overspend of 1.30. The efficiency loss against uniform
    spending, ln(mean t / geometric-mean t), is the Elo loss in e-folds under log utility:

    | Control | 60-move game | 80-move game | 80 moves, with the 1.30 overspend |
    |---|---|---|---|
    | 8+0.08 (STC) | 0.050 | 0.066 | 0.112 |
    | 40+0.4 (LTC) | 0.050 | 0.067 | 0.113 |
    | **30'+3" (TCEC Swiss)** | **0.129** | **0.206** | **0.328** |

    At TCEC, an 80-move game starts at 62 s per move and ends at 7 s (81 s and 5.4 s with
    overspend). The *excess* loss specific to TCEC's shape is about 0.14-0.22 e-folds over
    what STC and LTC already contain. The time-to-Elo rate at TCEC length and 512 threads is
    unknown. With k_TCEC between 50 and 100 per e-fold (UNVERIFIED; it must be below STC's
    150), that is **+7 to +22 Elo available at TCEC that no Fork test can see**. This is an
    upper bound: if late moves matter less (decided endings, 7-man tables), the optimal
    t_i ∝ a_i is front-loaded too.
  - *(a)* The surveys' node-share gains (+4 to +13 at LTC in S2's table; KB time-management
    §4.4) are the prior. Fitting the factors to Fork's own p(change) should land at the upper
    half of that range: the factors suit Fork's growth rate and ordering rather than another
    engine's.

- **Theory and literature.**
  - S. Russell and E. Wefald, *Do the Right Thing: Studies in Limited Rationality*, MIT
    Press, 1991 (value of computation, metareasoning).
  - N. Hay, S. Russell, D. Tolpin and S. E. Shimony, "Selecting Computations: Theory and
    Applications", UAI 2012 (value of information for allocating search effort).
  - Classic chess TM: KB time-management.md §4.2-4.4 (Hyatt; Šolak and Vučković 2009).
  - Node-count TM's public lineage: S1 §4 (credited there to Koivisto); S2 §4.2.
  - The log-utility allocation is a standard Lagrangian argument; the "spend only when
    reached" survival form is my derivation.

- **Why Fork.**
  - A2 §4: TM is entirely static, the counters exist, and spend is 1.30 times the soft limit
    *for reasons unrelated to the position*, which is pure noise in allocation.
  - A2 O8.1: no Fork control has TCEC's base/increment ratio of 600.
  - A3 §1.6: TCEC thinks about 7-8 single-thread doublings longer.
  - Data generation is node-limited (orchestrator note), so labels are unaffected.

- **Prediction.**
  - (a) alone, with c chosen by a two-value ladder, passes STC [0, 3] at +5 to +10, and LTC
    is at least STC. **Refuted if** H0 at STC with both ladder values.
  - The fit's own falsifiable output: on held-out logged positions, the logistic model's
    AUC for "best move changes in the next iteration" is ≥ 0.75 with share, stability and
    |Δscore|. **Refuted (method dead, fall back to plain node share) if** AUC < 0.65.
  - (b) at a ratio-600 control (A2's 48+0.08, Move Overhead lowered for both engines; A3
    §1.5 notes the 100 ms default exceeds the 80 ms increment): a quantile horizon beats
    /30 by +3 to +10. At 8+0.08 the same change is within ±3, because the table says STC
    loses only 0.05-0.07 e-folds. **Refuted if** ratio-600 and ratio-100 give the same sign
    and size, since that would mean the shape argument does not matter.

- **Speed cost; data / compute need.**
  - Zero nps.
  - Measurement: a debug print of per-iteration (best move, share, score) on about 5,000
    positions from Fork's own games, `go depth` to a fixed depth on a quiet core. About
    2-4 CPU-hours through jobctl as a `measure` job, beside data generation.
  - Game-length distribution: from Fork's own LTC SPRT PGNs (they adjudicate at 1000 cp x 5,
    so they understate length; UNVERIFIED by how much). TCEC's public game archives would
    give TCEC-true lengths, but even as statistics only that is a data-policy call for the
    owner.

- **Cheapest first experiment.** The logging run and the logistic fit (offline). Then a
  two-value ladder for c at STC (2 stages each), then STC SPRT [0, 3], then LTC.
- **Kill criterion.** AUC < 0.65, or H0 at both ladder values. Part (b) is killed if the
  ratio-600 ladder shows no difference between the /30 horizon and the quantile horizon at
  3,200 games.
- **Originality notes.** Fit Fork's own curve. Do not adopt any engine's multiplier tables.
  The S1 and S2 lineages are credited for the idea of node-share TM. Constants come from
  the fit (justification recorded in the constants table).
- **Effort and dependencies.**
  - DESIGN puts TM in Phase 5, so this is a **plan change for the owner**.
  - It touches nothing in §5.6 except that every later LTC test plays with it, so
    A2 O1's argument applies: do it before item 12's SPSA.
  - It adds the ratio-600 control to the test setup, for TM changes only.

---

## W2. Output experts chosen by frozen-accumulator linear probes [NOVEL] (as a method)

- **Mechanism.** S512ppr2's 8 phase-selected output heads are a hard-gated mixture of
  experts: one shared 1,024-wide SCReLU representation, and a gate (phase) that picks one
  linear readout.
  - MoE theory says capacity grows with the number of experts at constant per-sample
    compute, and that the gate should split the input space where the optimal readout
    differs most. Phase is one plausible gate. Others are untested: queens on or off,
    non-pawn material imbalance, pawn count, kings castled on opposite wings, and 2-D
    products of these with phase.
  - **The output layer is linear given frozen features.** So a candidate gating can be
    scored without GPU training:
    1. freeze S512ppr2's first layer (its float `weights.bin`);
    2. compute the 1,024 activations for about 2-4 M kept positions (the trainer's existing
       feature dump, then a numpy accumulator);
    3. fit one readout per bucket of each candidate gating by Gauss-Newton on the
       sigmoid-MSE target (each step is a weighted ridge solve with a 1,025 x 1,025 matrix
       per bucket, accumulated in a stream);
    4. compare held-out loss.
  - The winner is fine-tuned warm: each new sub-bucket starts as a copy of its parent's
    weights, which reproduces S512ppr2 exactly at step 0 and satisfies A1's
    function-preserving rule for warm starts.

- **Math / derivation.**
  - Cost. A 16-bucket head is 16 x 1,024 x 2 B = 32 KB. Only one 2 KB row is read per
    evaluation, and the bucket rarely changes within a subtree. The bucket index costs a
    few popcounts on bitboards already in the position. Expected nps 0.99-1.00 (INFERRED).
    At k = 150 per e-fold, 0.99 costs 1.5 Elo.
  - Value. The rate is 6-10 Elo per 1e-4, since inputs and speed do not change. The probe is
    a **lower bound**: in fine-tuning, the first layer co-adapts to the new gate.
  - Size of the effect (INFERRED). Phase already separates the biggest regime change. A
    second axis should be worth 2e-5 to 1.5e-4, so **+1 to +12 FN**, and STC within about 2
    of FN.
  - Overfitting risk: at 848 M kept positions and 16-32 heads of 1,025 weights, each head
    sees more than 25 M positions. Nil.
  - Probe compute (COMPUTED): 4 M x 1,025² x 2 ≈ 8.4 TFLOP per Gauss-Newton pass, about
    3-5 minutes per pass at roughly 30-50 GFLOP/s of shared-core BLAS. About 5 passes per
    gating, so a 10-gating screen fits in an afternoon of CPU at low priority.
  - The same toolkit answers "**is the current readout at its optimum?**": refit the 8 phase
    heads and compare with the trained heads. If the refit gains > 2e-5, the trained output
    layer is under-converged, which is extra evidence for W3/W5.

- **Theory and literature.**
  - R. A. Jacobs, M. I. Jordan, S. J. Nowlan and G. E. Hinton, "Adaptive Mixtures of Local
    Experts", *Neural Computation* 3(1), 1991.
  - N. Shazeer et al., "Outrageously Large Neural Networks: The Sparsely-Gated
    Mixture-of-Experts Layer", ICLR 2017.
  - G. Alain and Y. Bengio, "Understanding intermediate layers using linear classifier
    probes", arXiv:1610.01644 (2016).
  - Function-preserving expansion: T. Chen, I. Goodfellow and J. Shlens, "Net2Net", ICLR
    2016.
  - Output buckets by material are common public NNUE practice (KB nnue-design §3.3; S2
    "OB"). Using probes to *choose* the gate is the new part, and so is a 2-D gate over
    phase.

- **Why Fork.**
  - A1 B7: "capacity with no per-move work (small post-accumulator or output-side layers)"
    is the direction consistent with the speed constraint.
  - A1 §3.3: no generalisation gap, so capacity that is cheap at inference is the open
    lever.
  - Every input-side capacity attempt failed on speed (H-512, XGR, AF-S, S512+X).
  - S2 §5.1: Fork has far more positions per weight than the bucketed engines.

- **Prediction.**
  - The probe finds at least one gating whose held-out loss beats the refit-phase baseline by
    ≥ 3e-5 (with a declared 2 M-position held-out set and a bootstrap CI excluding zero).
  - Fine-tuned (warm, 1e-5, 60-120 superbatches), FN +4 to +12 against S512ppr2, STC within
    3 of FN.
  - **Refuted if** every candidate's probe gain is < 2e-5 (the phase gate is already the
    right MoE split), or FN < +3 after fine-tuning a probe gain ≥ 5e-5. The second case
    would mean probe gains do not transfer, and the method is dead.

- **Speed cost; data / compute need.**
  - About 1% nps (to be measured by bench/ab.py).
  - The probe on local CPU: hours, low priority.
  - Fine-tune: one Kaggle run of about 1 h.
  - FN screen, then STC [0, 5].
- **Cheapest first experiment.** The probe alone: 10 declared gatings (phase x {queens,
  imbalance class, pawn class, opposite castling}, plus 3 single gates), on positions from
  g3s2-val plus held-out shards. No training, no engine change.
- **Kill criterion.** Max probe gain < 2e-5, or the speed-adjusted FN (A3 §1.4 rule) ≤ 0.
- **Originality notes.**
  - Gate variables are generic chess quantities. No other engine's bucket count or
    boundaries are taken, and the boundaries are chosen by the probe on Fork's data (record
    the probe log as the constants' justification).
  - Credit the papers above and the general NNUE output-bucket concept (KB §3.3).
- **Effort and dependencies.**
  - New, not in §5.6; fits under item 14 ("the rest", network).
  - Must use the network file loader's bucket count. A format change goes through
    parity/netcheck.
  - Independent of search work; it can run while GitHub is busy.

---

## W3. Warm-up/stable/decay "trunk" schedule for the generational lineage (with diagnostic arms)

- **Mechanism.** Fork's lineage is in effect *continual pre-training*: each generation warm
  starts from a cooled (low-LR) net, re-heats to 1e-4, then steps down to 1e-5.
  - §0 shows the reheated phase averaging worse than its start, and A1 §5.2(a) shows that
    bullet's AdamW without bias correction inflates the first ~1,000 steps 1.3-6.5x.
  - The LLM literature's answer to this regime is warm-up-stable-decay (WSD), plus
    **keeping the un-decayed checkpoint as the trunk**. Each new snapshot continues from
    the end-of-stable trunk (short warm-up, same stable LR, replay of all data, which Fork
    already does). Only the decay branch is redone per release.
  - The decay is linear toward about 0 instead of a single step to 1e-5, so training ends at
    a lower noise temperature.

- **Math / derivation.**
  - From §0, the step to 1e-5 bought about 2.1e-4 of mean loss. Its remaining iterate
    excess is ≤ 2.3e-5. A decay to about 0 removes most of that: about 1-2e-5, so **+1 to
    +2 Elo from shape alone**.
  - The bigger term is A1 B1: the curves are still falling at 360, and A1 guesses
    −1e-4 to −2.5e-4 from a 3x longer low-LR phase, which is **+6 to +25**.
  - The trunk adds no Elo by itself. It removes the re-heat spike, so each generation spends
    its whole stable phase learning the new data rather than recovering. In Fork's warm run
    the re-heat cost is the gap between the 1-180 mean and the start, about 7e-5.
  - Kaggle cost (A1 §5.3, READ): 21.5 s per superbatch on one T4.
    - 180 superbatches: 1.1 h;
    - 360: 2.15 h;
    - 1,080: 6.5 h.
    The arms below fit one session on T4 x2.

- **Theory and literature.**
  - S. Hu et al., "MiniCPM: Unveiling the Potential of Small Language Models with Scalable
    Training Strategies", arXiv:2404.06395 (2024): introduces WSD.
  - A. Hägele, E. Bakouch, A. Kosson, L. Ben Allal, L. Von Werra and M. Jaggi, "Scaling Laws
    and Compute-Optimal Training Beyond Fixed Training Durations", NeurIPS 2024,
    arXiv:2405.18392: constant LR plus cooldown matches cosine and lets one run be reused at
    several lengths. SWA improves along the trajectory. My memory says their best cooldown
    shape was (1 − √) and cooldowns of about 20% of steps sufficed; both UNVERIFIED (abstract
    and README read, not the full text).
  - A. Ibrahim, B. Thérien et al., "Simple and Scalable Strategies to Continually Pre-train
    Large Language Models", arXiv:2403.08763 (2024, TMLR): LR re-warming, re-decaying and
    replay match full retraining.
  - K. Gupta et al., "Continual Pre-Training of Large Language Models: How to (re)warm your
    model?", arXiv:2308.04014 (2023): UNVERIFIED as to exact title and findings.
  - Warm-up and Adam's early variance: L. Liu et al., "On the Variance of the Adaptive
    Learning Rate and Beyond" (RAdam), ICLR 2020; Kingma and Ba, arXiv:1412.6980; Goyal et
    al., arXiv:1706.02677.
  - KB nnue-design §6.4: in the family's short runs the schedules tested were hard to tell
    apart (cosine slightly ahead), with a recommendation for linear decay. S2: Ethereal
    adopted a much deeper final decay.

- **Why Fork.** §0 (new); A1 §5 (warm 1e-3 destroyed nets; no bias correction; compute is
  the lever); A1 §3.3 (no overfitting).

- **Prediction.** The arms are declared now, all from S512+PP's float weights on g3s2, with
  validation on g3s2-val. The existing warm s1/s2 runs are the control, so **no control GPU
  time is needed**.
  - **D1 "decay only"**: 180 superbatches at 1e-5, no 1e-4 phase (1.1 h). Prediction: its
    final loss is within 3e-5 of the control's 1e-5-phase mean (0.01916). Its endgame check
    is worse than S512ppr2's 8 of 900 (> 30), because the slice is learned mainly at the
    higher LR.
    - **If the loss is worse by > 5e-5**, the stable phase carries real learning, and W3's
      trunk is the way to keep it.
    - If D1 matches on both loss and endgame, the stable phase is mostly heat, and future
      warm retrains can be short.
  - **D2 "WSD, same length"**: 5 superbatches of linear warm-up 0 → 1e-4, stable to 180,
    linear decay to 0 over 181-360 (2.15 h). Prediction: final EMA loss (W5) ≤ control
    mean − 3e-5. **Refuted if** above the control mean.
  - **D3 "WSD long"**: warm-up, stable to 540, linear decay over 541-1,080 (6.5 h; this is
    A1 B1's arm). Prediction: ≤ D2 − 5e-5, then FN +5 to +15 against S512ppr2. **Refuted
    if** D3 − D2 > −3e-5 (no gain from compute), which would mean Fork has reached its
    architecture's floor.
  - The trunk itself is tested at the next snapshot (g3s3). Warm start from D3's
    end-of-stable checkpoint against warm start from its decayed end, both re-warmed to
    1e-4. Prediction: the trunk start's superbatch-1-20 mean loss is ≥ 5e-5 lower (less
    re-heat), and the final is ≤ the decayed-start final.

- **Speed cost; data / compute need.** No engine change. About 10 GPU-h of Kaggle (one
  session) on existing data. The trainer needs a linear-decay and warm-up LR closure (bullet
  ships a warm-up scheduler, A1 §5.2) and the EMA of W5.
- **Cheapest first experiment.** D1 and D2 together on T4 x2 (2.15 h wall time).
- **Kill criterion.** D2 > control mean and D3 − D2 > −3e-5: keep the current recipe.
- **Originality notes.** Training-schedule concepts from ML papers (credit above). No
  engine's LR values. Fork's LR values stay Fork's (1e-4 measured in item 7).
- **Effort and dependencies.**
  - It complements A1 B1: run it *as* B1's session, adding D1 and the trunk save.
  - It changes "the standard retrain recipe" (HO §5) only if D2 or D3 wins.
  - It feeds §5.6's next retrain (g3s3 when g3g seals).

---

## W4. Lower-variance value targets from Fork's own trajectories [NOVEL] (λ-returns for NNUE targets; heteroscedastic result weight)

- **Mechanism.** Fork's target is (1 − w)·σ(s/S) + w·r with w = 0.5, never tuned (A1 §8).
  - **The result r is shared by every position of a game.** In survey-sampling terms the
    design effect is 1 + (m − 1)ρ, with m ≈ 35 kept positions per game and ρ = 1 for the
    result half. So the result half carries about **one independent sample per game**:
    roughly 25 M results in g3s2, against 848 M scores (COMPUTED from A1's 35 kept per game).
  - This is exactly KataGo's diagnosis: "the game outcome value target is highly
    data-limited" (Wu 2019, §playout cap randomization). Fork's idea 13 (+65.5) is the same
    lever applied to data generation.
  - Two ways to cut the variance without new data:
    1. **λ-return target.** Replace r by G_t^λ, an exponentially weighted average of the
       game's later stored scores σ(s_{t+k}/S) (saved plies only; unsaved ones carry 32767)
       with the result as the terminal value: TD(λ)'s target computed from data Fork
       already stores (viriformat keeps every ply's score). λ = 1 gives back the result;
       λ = 0 gives back the next score.
    2. **Inverse-variance (heteroscedastic) weight.** The score half and the result half
       are two noisy estimates of the same win probability p. The minimum-variance
       combination weights each by the inverse of its noise variance:
       w(p) = σ_s² / (σ_s² + Var(r | p)). Here Var(r | p) = p_w + p_d/4 − p², with
       p = p_w + p_d/2, and the win and draw rates p_w, p_d are estimated per eval band and
       phase from Fork's own games. Balanced positions, where the result
       is nearly a coin toss, then lean on the score. Decided positions, where the result is
       almost certain and σ(s/S) saturates, lean on the result.
  - Both are trainer-only changes, computed per game in the shard reader before the shuffle
    buffer. The simplest hook writes the new target back into the score field as
    S·logit(target), so the mapper is unchanged.

- **Math / derivation.**
  - Model the per-ply estimate as p_t = V_t + e_t. V_t is the true value under self-play (a
    martingale, E[V_{t+k} | t] = V_t). e_t is search error, with autocorrelation ρ_e(k)
    along the game. Then G_t^λ is unbiased for V_t. Its variance trades search noise
    (averaged over about 1/(1 − λ) plies, divided by an effective count of
    n_eff ≈ (1 + λ)/(1 − λ) if ρ_e decays fast) against game noise (the martingale
    increments, weighted by λ^k).
  - **The optimal λ is therefore measurable offline.** Over one shard per part, estimate
    Var(p_t − p_{t+k}) for k = 1..40 and Var(r − p_t) by eval band and phase. These
    autocovariances determine the optimal λ (and σ_s² for the inverse-variance weight) **with
    no training and no guessed constant**.
  - Size of the effect (INFERRED). A1 §3.2 puts the irreducible floor at 0.010-0.016 of the
    0.019 loss, most of it from the result half. Halving the result-half noise lowers the
    floor, but *loss on different targets is not comparable* (A1 §8 row 1). The Elo route
    is cleaner gradients, which act like more effective data. Using A1's 30 Elo per doubling
    discounted to 10-20 at today's scale, with the result half's effective samples rising by
    a factor of 1.5-3, the gain is **+3 to +12 FN** (low confidence).
  - Risk: S2's records show that pushing the target far toward the result can lose badly (a
    result-only fine-tune −57 STC; a material-dependent blend −21 LTC). Both arms stay
    between the endpoints, and the inverse-variance arm moves w only where the theory says
    to.

- **Theory and literature.**
  - R. S. Sutton, "Learning to predict by the methods of temporal differences", *Machine
    Learning* 3:9-44 (1988).
  - J. Baxter, A. Tridgell and L. Weaver, "Learning to Play Chess Using Temporal
    Differences", *Machine Learning* 40(3), 2000 (TDLeaf(λ)).
  - G. Tesauro, "Temporal Difference Learning and TD-Gammon", *CACM* 38(3), 1995.
  - L. Kish, *Survey Sampling*, Wiley, 1965 (the design effect).
  - W. G. Cochran, "The combination of estimates from different experiments", *Biometrics*
    10, 1954 (inverse-variance weighting).
  - D. J. Wu, "Accelerating Self-Play Learning in Go", arXiv:1902.10565 (read via ar5iv
    2026-11-07: the quoted sentence, and playout cap randomization worth a 1.37x factor in
    its ablation).
  - Leela-style training mixes the game result with the root search value ("q") for its
    value target; that practice is noted here as a concept only (UNVERIFIED details).
  - Novelty: TD(λ) is classical, and so is supervised NNUE training on score/result blends.
    A λ-return computed from stored per-ply search scores as an NNUE target, and a per-position
    inverse-variance w, are not in the KB or the surveys. I am not aware of either in public
    NNUE practice (UNVERIFIED).

- **Why Fork.**
  - A1 §8: w = 0.5 has never been tuned, and draws are 18-20%.
  - A1 §3.2: the result half dominates the noise floor.
  - A1 §7: H1, games as the unit of data.
  - ideas.md 13: the split search's gain.
  - The data are already on disk, so this costs no CPU for data generation.

- **Prediction.**
  - **Offline study (falsifiable, no training).** Search error decorrelates within about
    4-12 saved plies, and the variance-optimal λ (in units of saved plies) is between 0.7
    and 0.95. **Refuted if** ρ_e(k) stays above 0.8 out to k = 20: then later scores are no
    independent help and the λ-return arm is dropped.
  - **Training.** One Kaggle session with three arms (control = standard warm recipe;
    λ-return; inverse-variance w), two seeds for the best arm, each scale-matched. Judged
    by the FN screen and not by loss. The secondary yardstick, the same for all arms, is the
    Brier score against the *result* on a held-out set (proper and target-agnostic,
    reported but not decisive).
    - Expect the better arm at FN +4 to +12 against control, and STC [0, 5] to pass.
    - **Refuted if** both arms are within ±4 FN of control (keep w = 0.5 as a measured
      choice, which also settles A1 B4's question).

- **Speed cost; data / compute need.** No engine change. The offline study is 1-2
  CPU-hours (a Python pass over about 10 shards; through jobctl). Training is one Kaggle
  session on existing data.
- **Cheapest first experiment.** The variance study only. It also delivers the first direct
  measurement of label noise by ply distance (A1 B2 asked for one).
- **Kill criterion.** As in Prediction. Also killed if the endgame check gets worse than
  30 of 900 for the chosen arm (the slice's saturated targets must be exempt from both
  transforms; declare that in advance).
- **Originality notes.** Methods from the papers credited above. λ and w(p) are derived
  from Fork's own data (record the study as the justification). No engine's blend values.
- **Effort and dependencies.**
  - Replaces A1 B4's "w sweep": the derivation picks w instead of a grid.
  - Pair it with W3's session if GPU time is short (an arm swap).
  - Interacts with S (rematch) and with every eval-dependent margin (KB §6.3): run it
    before item 12's SPSA, not after.

---

## W5. Iterate averaging (EMA/LAWA) and two-seed soups; the final EMA replaces best-of-360

- **Mechanism.**
  - **(a)** Keep an exponential moving average of the float weights during the low-LR phase
    (or average the last K superbatch checkpoints, LAWA) and ship the average. This removes
    the mean-zero wander §0 measured (sd 3.6e-5, autocorrelation 0.8). It also removes the
    selection bias of "the best of 360 checkpoints on the very set that scores them".
  - **(b)** Average the float weights of the two warm seeds. They share a starting point and
    a basin, so they sit on one linearly connected low-loss region, which makes this a
    "model soup".

- **Math / derivation.**
  - Expected-loss gain against a *random* late checkpoint is at most the quadratic excess at
    1e-5: about 1-2.3e-5 (§0 point 3). That is **+1 to +2 Elo**.
  - Against today's best-of-360 the *measured* gain may be about 0, because best-of-360
    already has −7e-5 of selection luck. The *true* loss gain is the same 1-2.3e-5 plus
    whatever overfitting to the 20,000 validation positions the selection carried.
  - The soup averages two independent wanders, which halves the variance term, and averages
    two different data orders. Expect −0.5 to −1.5e-5 over the better seed.
  - EMA in the **1e-4 phase** is the bigger lever: SWA at high LR approximates part of a
    cooldown (Hägele et al.). If an EMA of superbatches 90-180 reaches within 5e-5 of the
    1e-5 phase, the decay phase can be shortened and the GPU time moved to W3's stable
    phase.
  - Side benefit: averaged weights tend to sit in flatter regions, so quantization error
    (qloss) should not grow; prediction ≤ today's 7.9 / 6.1 cp.

- **Theory and literature.**
  - B. T. Polyak and A. B. Juditsky, "Acceleration of stochastic approximation by
    averaging", *SIAM J. Control Optim.* 30(4), 1992.
  - P. Izmailov, D. Podoprikhin, T. Garipov, D. Vetrov and A. G. Wilson, "Averaging Weights
    Leads to Wider Optima and Better Generalization", UAI 2018 (SWA).
  - J. Kaddour, "Stop Wasting My Time! Saving Days of ImageNet and BERT Training with Latest
    Weight Averaging", arXiv:2209.14981 (2022) (LAWA).
  - S. Sanyal et al., "Early Weight Averaging meets High Learning Rates for LLM
    Pre-training", arXiv:2306.03241 (2023) (UNVERIFIED exact author list).
  - M. Wortsman et al., "Model soups", ICML 2022.
  - J. Frankle, G. K. Dziugaite, D. Roy and M. Carbin, "Linear Mode Connectivity and the
    Lottery Ticket Hypothesis", ICML 2020.
  - B. Neyshabur, H. Sedghi and C. Zhang, "What is being transferred in transfer learning?",
    NeurIPS 2020 (nets fine-tuned from one start stay in one basin).
  - Hägele et al. 2024 (as W3). The optimizer's curse: Smith and Winkler 2006 (A1 §3.2).

- **Why Fork.** §0, and A1 §3.2 (best-of-360, a small validation set, a 4e-5 threshold below
  the jitter).

- **Prediction.**
  - **Today, no new training:** average warm s1 and s2's float `weights.bin` (both on disk
    in `~/fork-data/kaggle/g3s2-out/result/`) and score the result with `--superbatches 0`
    on g3s2-val (a few GPU-minutes on Kaggle, or a numpy forward pass on CPU).
    - Expect ≤ min(0.01908862, 0.01910044) − 0.5e-5.
    - **Control:** the same average of the two *scratch* seeds should be far worse (>
      0.0200), because independent inits are not linearly connected.
    - **Refuted (basin argument wrong) if** the warm soup is worse than the worse warm seed.
  - In the next training session, with EMA on, the final EMA is ≤ the run's own 271-360
    mean − 2e-5 and within ±2e-5 of its best single checkpoint. Then FN of EMA against
    best-checkpoint at 1,600 games is ≥ 0 (an expected +1 to +3 that the screen cannot
    resolve).
  - Adopt EMA on the loss and qloss evidence plus a non-regression check, not a gainer SPRT.

- **Speed cost; data / compute need.** None at inference. The soup costs minutes. EMA in the
  trainer is a small change: one more float copy of the weights, updated per batch or per
  superbatch.
- **Cheapest first experiment.** The soup and the scratch control, today.
- **Kill criterion.** The warm soup is worse than both seeds, and EMA ≥ the run mean − 1e-5.
- **Originality notes.** Generic ML (credited). No engine values.
- **Effort and dependencies.** 0.5-1 day. A precondition for W3's decision rule (compare
  final EMAs, not best-of-N), and it replaces the 4e-5 "seed spread" threshold with
  EMA-to-EMA comparisons.

---

## W6. Sequential halving for the search queue [NOVEL] (for engine testing; UNVERIFIED that nobody does it)

- **Mechanism.** Batch 4 has nine built switches, and item 8 and idea 23's survivors join
  them. Fork tests each with a ladder and then an SPRT to a verdict. A3 §2.6 shows that
  [0, 3] with a 13-stage cap returns about 0.20 nElo per stage, against 0.68 for "fixed 4
  stages, accept if the estimate > +2". The latter accepts a negative change 10% of the
  time.
  - **Fixed-budget best-arm identification**, by sequential halving, spends little on
    obvious losers and much on contenders:
    1. play every candidate for 1 stage;
    2. keep the top 4 for 2 more stages;
    3. keep the top 2 for 3 more;
    4. accept those whose cumulative estimate exceeds a threshold;
    5. confirm with an SPRT if the owner wants.

- **Math / derivation.** Pure-Python simulation (COMPUTED, 40,000 trials of 9 candidates).
  - Prior N(μ, σ) of true nElo, as A3's priors.
  - Per-stage nElo SE 8.69 (1,600 games; A3's 245.7/√pairs).
  - Sequential halving uses 9 + 8 + 6 = 23 stages per batch.

  | Prior (nElo) | Fixed 4 stages x 9 (36 stages): gain/stage, P(accepted < 0) | Sequential halving 9 → 4 → 2, threshold +2 | threshold +4 |
  |---|---|---|---|
  | N(0, 8) | 0.68, **0.103** | 0.69, **0.039** | 0.67, 0.021 |
  | N(2, 8) | 0.95, 0.077 | 0.86, 0.022 | 0.85, 0.012 |
  | N(4, 15) | 1.98, 0.040 | 1.83, 0.004 | 1.83, 0.002 |

  - Sequential halving matches A3's most efficient design in Elo per stage, about **3.4x
    today's [0, 3] SPRT policy** (0.20). It cuts the false-accept rate 3-10x and uses 23
    stages per nine-candidate batch instead of A3's estimated ~140 for batch 4.
  - What it gives up: at most 2 adoptions per batch, and less total Elo per *batch*
    (15.9 against 24.6 nElo under N(0, 8)). A second batch from the queue recovers that, at
    23 more stages.
  - Ladders fold in naturally: each ladder value is one arm.

- **Theory and literature.**
  - Z. Karnin, T. Koren and O. Somekh, "Almost Optimal Exploration in Multi-Armed Bandits",
    ICML 2013 (sequential halving).
  - J.-Y. Audibert, S. Bubeck and R. Munos, "Best Arm Identification in Multi-Armed
    Bandits", COLT 2010.
  - K. Jamieson and A. Talwalkar, "Non-stochastic Best Arm Identification and
    Hyperparameter Optimization", AISTATS 2016.
  - L. Li et al., "Hyperband", JMLR 18, 2018.
  - Fishtest's two-stage STC/LTC and its "four or five tries" rule (S1 §6) are the engine
    practice it replaces for screening only.

- **Why Fork.**
  - A3 §2.6-2.7: search features returned 0.77 Elo per stage against 12.5 for nets, and 57%
    of search stages bought rejections or caps.
  - A2 §6.5: the mechanism measurements (cutoff index, SE precision) are good priors to
    *order* arms before round 1.
  - The owner's "untested changes never ship" holds: every survivor still faces a
    confirmation, and the false-accept rate is lower than fixed-length designs.

- **Prediction.** On batch 4 (nine arms plus ladder values as separate arms), sequential
  halving with threshold +2 adopts 1-3 changes in ≤ 30 stages. Any confirmation SPRT on
  [0, 3] for a survivor passes in ≥ 70% of cases (the simulation's P(true > 0 | accepted)
  ≈ 0.96 suggests it should). **Refuted if** the confirmations fail more than half the time:
  then the prior is too optimistic or features interact.

- **Speed cost; data / compute need.** GitHub only; fewer stages than today.
- **Cheapest first experiment.** Run batch 4 this way, ordered by mechanism priors.
- **Kill criterion.** Two batches with confirmation failure rates > 50%.
- **Originality notes.** Bandit literature (credited); no engine data.
- **Effort and dependencies.**
  - A policy change for the owner (DL 2026-11-06 set ladders, then SPRTs).
  - Touches §5.6 items 5, 8 and 13. For idea 23, the arms are candidate heuristics, and
    sequential halving replaces the proxy stage A2 §6 showed to be biased.
  - Not for removals (item 11). A null effect is the hardest case for any bandit; S1 §7.2.5's
    combined guard fits there.

---

## W7. Width frontier: low-utility neuron census, then structured narrowing (or function-preserving widening)

- **Mechanism.** S-512's width was chosen in round 1 at 93.5 M positions. Data is now
  1.24 B, and speed is worth 1.5 Elo per 1%. Jones (2021) shows that train-time and
  test-time compute substitute for each other. In an engine, test-time compute is nps, so
  the right width is a frontier question, not a fixed choice. The cheap direction is first:
  a **census** of the 512 SCReLU neurons on 1 M positions (W2's frozen-feature tooling),
  measuring each neuron's activation rate and its output-weighted contribution variance per
  bucket. Neurons with negligible contribution can be removed in multiples of 16 (AVX2
  int16 lanes), followed by a short warm fine-tune. That is free speed. The other direction
  is Net2Net widening: new neurons with zero output weights reproduce the parent exactly.
- **Math / derivation.**
  - The network is about 45% of node time (A3 §1.2), and the accumulator update and output
    layer scale with width. Removing 32 neurons (6.25%) cuts about 6.25% of roughly 35% of
    time, so +2.2% nps, **+3.3 Elo** at k = 150, minus whatever accuracy those neurons held.
  - Widening to 640 costs about −9% nps (−14 Elo), so it needs FN ≥ +19 (A3 §1.4 rule
    plus 5). S2 reports that widening on the same data was about zero at long TC elsewhere,
    so I expect widening to fail. It is listed only as the frontier's other side.
- **Theory and literature.**
  - A. L. Jones, "Scaling Scaling Laws with Board Games", arXiv:2104.03113 (2021): the
    train/test compute trade-off in AlphaZero on Hex.
  - Y. LeCun, J. Denker and S. Solla, "Optimal Brain Damage", NeurIPS 1990.
  - H. Li et al., "Pruning Filters for Efficient ConvNets", ICLR 2017.
  - Chen, Goodfellow and Shlens, Net2Net, ICLR 2016.
  - J. Kaplan et al., arXiv:2001.08361, and J. Hoffmann et al., arXiv:2203.15556, as
    general scaling evidence only (NNUE's sparse first layer does not follow transformer
    laws).
- **Why Fork.** A3 §1.3: speed gains came from fewer instructions and row width. A1 §4:
  speed prices. A1 §3.3: there is no data shortage, so the open question is where capacity
  is cheap.
- **Prediction.** The census finds ≥ 16 neurons whose removal (with the readout refit by
  the W2 probe) costs < 1e-5 of held-out loss. A 480- or 496-wide fine-tuned net then scores
  FN within −2 of S512ppr2 at ≥ 1.02x nps, so speed-adjusted ≥ +1. **Refuted if** fewer
  than 16 such neurons exist (the net uses its width), and in that case no narrowing is
  tried.
- **Speed cost; data / compute need.** CPU census in hours. Fine-tune is one Kaggle hour.
  The engine needs a width constant made per-net (netcheck and parity, plus the loader's
  bounds).
- **Cheapest first experiment.** The census, reusing W2's activations.
- **Kill criterion.** As in Prediction, or a measured nps gain under 1.5% (below
  bench/ab.py's useful resolution).
- **Originality notes.** Generic; width chosen by Fork's census.
- **Effort and dependencies.** Item 14 (network, "the rest"). Shares tooling with W2. It
  changes the network format's width field.

---

## W8. Depth-gated policy ordering read from the existing accumulator [NOVEL] (combination; idea 16 reborn)

- **Mechanism.** At an interior node the evaluation's accumulator is already computed, and
  most nodes are evaluated for RFP and NMP. A tiny policy head reads it:
  - project the 1,024 activations to a small vector once per node (P·h);
  - score each quiet move by dot products of that vector with learned (piece, from) and
    (piece, to) embeddings;
  - add the policy score to the history score in ordering.

  The cost is paid **only at nodes with depth ≥ D and no TT move**, the IIR nodes. There the
  subtree is large and ordering is known to be bad: IIR's +21.5/+26.3 says so (A2 §2.1).
  These nodes are a tiny fraction of all nodes, so the per-node cost hardly shows in nps.
  - Labels are free: in Fork's self-play the played move is the 20k-node search's best move
    (no in-game randomisation after the opening plies; S1 §3 point 7).
  - The head can be trained on frozen accumulator features with W2's tooling, or jointly on
    Kaggle.
- **Math / derivation.**
  - Cost per policy call (INFERRED): a 32 x 1,024 int16 projection is about 2,000 AVX2
    multiply-add instructions, plus about 35 moves x 64 MACs, roughly 1.5-2 nodes' worth
    (about 1,300 cycles per node, A3).
  - At depth ≥ 8 the share of nodes is perhaps 0.3-1% (UNVERIFIED; a stats counter decides).
    The aggregate cost is then 0.5-2% nps, which is −1 to −3 Elo.
  - Benefit model: if the first-move cutoff rate at those nodes rises from f₀ to f₁, the
    expected nodes before a cutoff fall by about (1/f₀ − 1/f₁) child subtrees, each huge at
    depth ≥ 8. A 10-point gain in first-move cutoff at IIR nodes plausibly saves 3-8% of
    nodes to equal depth, which is +4 to +12 Elo at k = 150 per e-fold. The net is −3 to
    +10.
- **Theory and literature.**
  - L. Kocsis, J. Uiterwijk and J. van den Herik, "Move Ordering using Neural Networks"
    (IEA/AIE 2001, tested on Lines of Action) and "The Neural MoveMap Heuristic in Chess"
    (Computers and Games 2002, LNCS 2883); venues and years UNVERIFIED (found 2026-11-07 via
    Maastricht's research portal).
  - D. Silver et al., "A general reinforcement learning algorithm that masters chess, shogi,
    and Go through self-play", *Science* 362(6419), 2018 (policy priors).
  - M. Lai, "Giraffe", arXiv:1509.01549 (2015).
  - The new combination: a policy read from the NNUE accumulator that already exists, gated
    by remaining depth and the absence of a TT move.
- **Why Fork.** A2 §2.1 (IIR) and §6.5 (the mean-cutoff-index metric predicted ordering
  gains well, so a pre-SPRT measurement exists). ideas.md 16 (parked until after Phase 8).
- **Prediction.**
  - **Offline oracle first.** At logged no-TT-move nodes with depth ≥ 8, measure the policy
    head's top-1 agreement with the eventual best move against history ordering's first
    quiet. Expect +10 points or more.
  - Then a stats build: mean cutoff index at those nodes falls ≥ 15%, and bench nodes to
    equal depth fall ≥ 3%.
  - **Refuted if** top-1 agreement does not beat history by ≥ 5 points, or the nodes saving
    is < 2%.
- **Speed cost; data / compute need.** 0.5-2% nps (measured). Training is CPU or one Kaggle
  run, on data Fork already has.
- **Cheapest first experiment.** A counter of no-TT-move nodes by depth (fraction of nodes),
  plus the offline top-1 comparison on positions from shards (policy from frozen features,
  trained on CPU).
- **Kill criterion.** As in Prediction, or the speed-adjusted bench estimate ≤ 0.
- **Originality notes.** Old public idea (credited) in a new form. Names and constants are
  Fork's own; screen new identifiers as usual.
- **Effort and dependencies.** **Plan change** (idea 16 is parked until after Phase 8).
  6-10 days. Low priority behind W1-W5. It needs the network file to carry the head
  (parity), and it interacts with the reply and follow tables (offline, measure the ordering
  with both).

---

## 3. Critique of the current plan in my domain

1. **§5.6 item 6, idea 46 rank 1 (distillation from S512+X plus auxiliary threat targets):
   demote it.**
   - Theory: for a *scalar* regression target, distillation's gain is mainly regularisation
     and label denoising (Mobahi, Farajtabar and Bartlett, "Self-Distillation Amplifies
     Regularization in Hilbert Space", NeurIPS 2020; Furlanello et al., "Born-Again Neural
     Networks", ICML 2018). Fork has no generalisation gap (A1 §3.3), so regularisation is
     worth about zero.
   - The teacher's extra knowledge (threats) is exactly what A1 §3.5 calls
     "search-resolvable" (6 Elo per 1e-4, the weakest kind). A student without threat
     inputs can copy only a smoothed shadow of it.
   - S2's records: distilled or teacher-relabelled nets −3 to −26, one +3.7.
   - KataGo's auxiliary targets paid (a 1.65x factor for its value auxiliaries, 1.30x for
     the opponent-policy target) *because its value target came only from game outcomes*.
     Fork's score labels are already a dense per-position target. The mechanism does not
     transfer.
   - **Prediction:** both arms within ±3 FN of control; **refuted if** either exceeds +6 FN.
     If Kaggle has a free slot, W4 or W3 should take it first. The same reasoning lowers
     **idea 14** (auxiliary targets) to a free rider on another session.

2. **§5.6 item 7's recipe rule "best checkpoint by validation loss, 4e-5 = unresolved":
   replace it with final-EMA comparisons (W5).** The best of 360 sits 1.9σ below its phase
   mean (§0). A 4e-5 threshold compares two selection-biased minima. This costs nothing to
   fix.

3. **The next snapshot (g3s3) should be recency-weighted, not purged blind.**
   Quantitatively, A1's crude model (a ≈ 10-30 Elo per doubling of data now, b ≈ 0.31 per
   labeller Elo):
   - Dropping g2s1 (S512-labelled, about 416 M of about 848 M kept) halves data: −10 to −30.
   - It raises the mean labeller from about 1,040 to 1,117 chain Elo: +0.31 x 77 ≈ +24.
   - Net −6 to +14, roughly break-even now, and more positive as g3f and g3g (about 0.4 B
     newer labels) arrive.
   - A sampler weight of about 0.5 on S512-labelled parts (instead of 0 or 1) captures most
     of the labeller term at a fraction of the data cost.
   - This supports S2's N1 experiment and gives it a declared prediction: the weighted arm
     beats g3s3-uniform by +3 to +10 FN; refuted if ≤ 0.

4. **Idea 13's split share.** The design-effect argument (W4) and KataGo's own ablation
   (playout cap randomization, a 1.37x factor) agree with A1 B3: test a lower save share in
   the next part. KataGo's lesson is "decouple data quantity (games) from label quality
   (deep searches)". Fork could go further toward fewer saved positions per game. The cost
   arithmetic is in A1 §7. This is endorsed, not duplicated.

5. **Item 4 (speed-to-Elo).** Endorse A3's throttled build at 0.5x and 1.0x (§1.5). In
   Jones's terms, the same measurement also prices *training* compute against nps: an
   extra 1e-4 of loss (about 6-10 Elo) is worth about 4-7% nps. W3's arms are the cheapest
   way to buy loss today.

6. **Item 13 (idea 23's long run).** It is an evolutionary search under noisy fitness. The
   KB's own Part C cites evaluation-illusion results, and A2 §6 shows the proxy rates
   "similarity to off", not strength. In bandit terms the funnel should allocate *games*
   to candidates by sequential halving (W6) after the gate, and drop the proxy stage or use
   it only as an ordering prior. **Prediction:** a proxy-ranked run adopts at most 1 change
   in 40 generations. Refuted if ≥ 2 survivors pass confirmation SPRTs.

7. **Item 12 (SPSA).** SPSA is a stochastic-approximation method with a gradient-noise
   budget. W1's measured TM should precede it (A2 O1). W4's target change also shifts the
   eval scale (KB §6.3), so do W4 *before* SPSA or plan to redo the margin tune.

8. **QAT (idea 44).** It is low value for the all-int16 S-512 family (qloss 7.9/6.1 cp,
   A1 B8). Run it only on W2/W7 nets if their qloss grows; W5's averaged weights should not
   raise qloss.

9. **Nothing to drop in search from my domain.** I would *reorder* §5.6 as follows:
   - W5 (today, free);
   - W3 and W4 as the next Kaggle session (replacing idea 46's distillation slot);
   - W2's probe (CPU, beside data generation);
   - W1 before item 12 (owner's plan change);
   - W6 as the policy for batch 4.

---

## 4. What I could not verify

- Hägele et al.'s best cooldown shape ((1 − √)) and the "about 20% cooldown suffices" figure
  come from memory. I read the abstract and the code README only.
- The exact author list of Sanyal et al. (2023), Gupta et al. (2023)'s title and findings,
  and the venues and years of Kocsis, Uiterwijk and van den Herik's two move-ordering
  papers.
- Leela's value-target mixing practice (concept only).
- Whether any public NNUE trainer already uses λ-return targets or a per-position
  result weight. I found none in the KB or the surveys and did not search further.
- k (time-to-Elo) at TCEC length with 512 threads. W1's +7 to +22 assumes 50-100 per e-fold.
- TCEC game lengths. The 60- and 80-move columns in W1 are illustrative.
- The fraction of nodes at depth ≥ 8 with no TT move (W8's cost model), and whether any of
  S512ppr2's neurons are low-utility (W7).
- Whether S512ppr2's validation-loss wander is the same on a larger, multi-source validation
  set. §0 uses the existing 20,000-position set, and its √η signature assumes the wander is
  iterate noise, not a data-order artefact (the warm runs used `--interleave`).
- That the warm seeds lie in one linearly connected basin (W5's soup test decides it in
  minutes).
- The sequential-halving simulation uses A3's normal approximation and assumed priors. It
  ignores feature interactions and opening-pair correlation across stages.
- No engine source was opened. No other engine's constants appear here. KataGo's settings
  are described qualitatively; only its published ablation factors are quoted.

Sources consulted on the web (2026-11-07): arXiv:1902.10565 abstract and its ar5iv full text
(KataGo: playout cap randomization, auxiliary targets, ablation factors); NeurIPS 2024
proceedings page and arXiv:2405.18392 listing (Hägele et al.); arXiv:2104.03113 listing
(Jones); arXiv:2209.14981 listing (Kaddour); arXiv:2403.08763 listing (Ibrahim et al.);
Maastricht University research portal entries for Kocsis, Uiterwijk and van den Herik.


---

# B13. Skeptic 1: network, training, data and evaluation knowledge

## Skeptic 1: network, training, data and evaluation (Phase 4 think tank, Phase B)

**Summary.** I re-derived the load-bearing numbers in b-training (T), b-math (M), b-wildcard
(W), b-chess (C), the network parts of the two surveys (S1, S2) and b-systems H3/H8. I checked
them against the Kaggle curves and the shards myself: read-only Python in `tank/b/scratch-sk1/`,
no engine run, nothing changed. Six findings change the picture.

1. **On warm retrains, T and W are right and A1 is wrong. On scratch runs, A1 is right.**
   - In the warm runs' LR-1e-4 phase the loss slope is −0.2e-5 ± 2.9e-5 per 100 superbatches
     (pooled over both seeds, autocorrelation-corrected).
   - The whole measurable gain comes at the drop to 1e-5.
   - Two corrections to T: the 1e-5 tail is not flat (−2.6e-5 ± 1.5e-5 per 100 superbatches,
     1.7σ), and the residual noise floor is about 2e-5 (W's bound), not T's 2-8e-5.
   - So cooldown plus averaging is worth about +1 to +3 Elo, not +2 to +7.
2. **"All of S512ppr2's +20 may be the anneal" is plausible but not shown, and the argument
   behind it is partly circular.**
   - T's "+17 from the anneal" uses 9.3 Elo per 1e-4. That rate was itself computed from the
     S512ppr2 versus S512+PP pair.
   - With the independent rates (6-10.6 per 1e-4) the anneal maps to +10 to +23. That is
     consistent with anything from half to all of the +20.1.
   - T6 settles it for under an hour of GPU plus one fixed-node stage.
3. **The g3s2-val claim is mostly refuted.** I parsed both files.
   - The validation file is interleaved round-robin over its 30 sources.
   - The scored prefix (the first 20,000 kept positions, from 494 games) holds 64 games from
     g3b-g3e (2,142 positions, 10.7%) and 16 slice positions (0.08%).
   - What is true: the set is nearly blind to the slice (26x under-represented). It sees the new
     parts at about their share of sources.
4. **The training scale: M6's premise does not hold under the training filter.** With
   fit_scale.py's filter I get:
   - S = 89.2 on the mixed g3s2-val;
   - 83.8 on g3f (S512+PP labels);
   - 94.7 on part g2 (S512 labels).

   The snapshot's mix fits about 89, within 3% of 92, so leave S at 92. If anything,
   per-labeller S is the variant to consider, and it is worth about 0 Elo.
5. **M's β ≈ 102 Elo per 1e-4 for pawn links is noise, so the 18x "T/U" rate cannot be used
   quantitatively.**
   - M's figure compares best-of-360 losses. On window means (superbatches 271-360, same recipe,
     same initial weights, same data, same validation set), S512+PP is *worse* than the
     no-links control S512r3 by 1.1e-4 (0.019640 against 0.019531, both seeds).
   - S512+PP's played checkpoint sits 2.8e-4 below its own run's window mean.
   - The qualitative point stands, and is stronger: static loss says nothing about link-type
     knowledge.
6. **Distillation from S512+X is refuted, not just demoted.** S512+X is now about 40
   fixed-node (FN) Elo *weaker* than the default:
   - S512+X: FN +25.7 against S512r2;
   - S512+PP: FN +46.1 against S512r2;
   - S512ppr2: +20.1 over S512+PP.

   Its only distinctive content, the exposure terms, is already in the 20k-node search labels in
   resolved form.

My recommendations:
- **Item 7b:** keep the owner's standard recipe intact as the control. Add three cheap arms: an
  anneal-only arm (D1), a zero-code staircase cooldown branched from the control, and a
  recency arm that runs only if a deep-label gold set exists. Expect +4 to +12 Elo against
  S512ppr2 (central +7), not +11 to +20.
- **The result weight:** keep w = 0.5 in 7b. The cheapest decisive step is T5's
  decisive-share pilot (about 40 CPU-minutes), with two fixes: randomised replicates and
  datagen's split search in the shallow arm. It gates a w* measurement, then a single arm.
- **Input families:** no family has a strong prior. Screen first:
  - H3's zero-row pricing;
  - one combined deep-label relabel job (T3 + C2);
  - M1's searched loss;
  - W2's output-gate probe.

  Then build the pawn-structure-triggered family (M3a/C7) or king-zone pawns (C4), whichever
  the screen favours. Park threats (H8/S1): expected net −8 (−20 to +5) at 1.5 Elo per 1%.

Conventions: **[V]** verified by me against the primary file; **[C]** computed by me (scripts
in `tank/b/scratch-sk1/`: `curves.py`, `slope.py`, `valcomp.py`, `sfit.py`); **[I]** my
inference. K = `~/fork-data/kaggle/`. Elo is STC head-to-head unless marked. Loss-to-Elo
within one architecture: 6-10 per 1e-4 (A1's pairs, excluding the circular S512ppr2 pair).
Speed: 1.5 Elo per 1% (synthesis).

---

## 1. Verdict table

| ID | Proposal (short) | Verdict | Adjusted Elo at LTC | Main issue |
|---|---|---|---|---|
| T1 | Next retrain g3s3 with cooldown, averaging, recency arm, gold scoring | PLAUSIBLE | +4 to +12 (central +7) | the anneal is already banked in S512ppr2; the label/data model is zero-dof |
| T2 | WSD schedule, branch cooldowns, checkpoint averaging | SOUND (loss), small Elo | +1 to +3 | residual floor ≈ 2e-5 (W's α = 1 bound), not 2-8e-5; the real value is compute saved and the branch measurement |
| T3 | Gold-label validation set (deep relabel) + label noise | PLAUSIBLE | enabler | still a *static* loss: credits search-resolvable knowledge, so not an architecture yardstick; its kill test is biased toward passing |
| T4 | Recency: half-weight g2s1, double g3g | PLAUSIBLE | −2 to +6 | the model cannot sign it; needs the gold set to decide; = S2 N1 |
| T5 | Result weight w* from paired playouts | PLAUSIBLE (with fixes) | −2 to +6 | fixed-node games are deterministic (replicates need randomisation); the shallow arm must mimic the 50% split search; realistic SE ±0.15-0.2 |
| T6 | Anneal-only attribution of S512ppr2's +20 | SOUND | enabler | decide it by Elo (1 FN or STC stage), since the loss→Elo rate is circular here |
| T7 | Endgame-start self-play part (adjudication off) | PLAUSIBLE | 0 to +4 (more at TCEC) | overlaps C5; C5's deeper outcomes target the measured bias better |
| T8 | 2026-09 book; 25% save share | (a) PLAUSIBLE, (b) WEAK | (a) 0 to +3; (b) −3 to +4 | (b) spends the scarcest resource (datagen CPU) on a small-net test |
| T9 | Equal-compute scratch control (6.5 GPU-h) | PLAUSIBLE, low value | 0 | warm widening covers every Phase 4 design, including a zero-init skip head |
| M1 | Searched (QS/depth-2) validation loss to rank architectures | PLAUSIBLE | enabler (+0 to +10 indirect) | its stated ratio test rests on best-of-N losses; run it on the played nets over a fresh 200k set |
| M2 | n-step (TD-k) score targets | WEAK-PLAUSIBLE | −3 to +5 | arithmetic slip (slope 1.19, not 1.09); its Elo derivation leans on A1 B1, now undermined; cuts long-horizon result weight 4x |
| M3 | Passed-pawn inputs on the pawn trigger, residual screen | PLAUSIBLE-WEAK | 0 to +5 | the β pricing is invalid; the passer/island residuals in C's data are confounded |
| M4 | One margin scale factor set by error matching | WEAK | 0 to +3 | the "S fell at every promotion" evidence is the training-S change (105 → 92); the play/train ratio is flat at 0.96-1.00 |
| M5 | Cross-entropy loss arm | WEAK-PLAUSIBLE | −3 to +3 (TCEC +) | the data barely contains conversion phases (700 cp × 8 adjudication), so the extra gradient mostly lands on the slice |
| M6 | Refit S to about 85 | WEAK | 0 to +1 | the filtered fit on the mixed snapshot is about 89 [V]; 85 was an unfiltered fit on single parts |
| M7 | Adaptive rounding of the output layer; retire idea 44's session | SOUND | +0.5 to +1.5 | tiny; fine as a free step |
| W1 | Value-of-computation TM | PLAUSIBLE (a), WEAK (b, size) | +5 to +12 (a) | TM domain (Skeptic 2); the log-utility "uniform is optimal" premise ignores that early moves matter more, so (b) is an upper bound. Arithmetic verified |
| W2 | Output experts chosen by frozen-feature probes | PLAUSIBLE | +1 to +6 | the cheapest capacity lever; absorbs idea 46 rank 2 (threat-class heads) as one candidate gate |
| W3 | WSD "trunk" plus D1/D2/D3 | D1/D2 PLAUSIBLE; D3/trunk WEAK | +1 to +3 | the re-heat rise is the 1e-4 noise floor, not a cost; D3's length premise is not supported by the curves |
| W4 | λ-return targets; inverse-variance w(p) | WEAK-PLAUSIBLE | −3 to +5 | variance-only weighting ignores the shallow-outcome bias C measured; = M2 |
| W5 | Iterate averaging / two-seed soup | SOUND | +1 to +2 | the soup test is free today (CPU) |
| W6 | Sequential halving for the search queue | PLAUSIBLE | enabler | testing domain (Skeptic 2) |
| W7 | Width census / narrowing | WEAK | 0 to +3 | M found no dead units; 15 active in < 2% of positions |
| W8 | Accumulator policy ordering | WEAK | −3 to +5 | plan change (idea 16 parked), 6-10 days |
| C1 | Knowledge-gap ledger + blind-spot suite | SOUND (tooling) | enabler | gauntlet king lifts rest on 4-7 positions per threshold |
| C2 | Deep vs 20k labels by category (+ residual on deep labels) | SOUND | enabler | merge with T3 and A1's label-noise run into one job |
| C3 | Structure-class calibration scale | PLAUSIBLE | 0 to +3 | E6 null; fitting on test games is an owner decision |
| C4 | King-zone pawn links (896 inputs, about 0.96x) | PLAUSIBLE-WEAK | 0 to +5 | thin evidence; self-play shows no king residual; H-512's null |
| C5 | Depth-matched endgame-start slice (80k nodes) | PLAUSIBLE | 0 to +4 STC (TCEC +) | 10.5 h of datagen CPU; the pilot-calibration gate is good |
| C6 | Extended endgame acceptance test + TB audit | SOUND | guard | none |
| C7 | Pawn-status planes | WEAK | 0 to +4 | "islands" is positive for the leader's own islands too (+4.6 STC) [V]: a position-type effect, not a weak-pawn signal |
| S1 7.1.k | Narrow threat side accumulator (about 0.91x) | WEAK | −10 to +5 | uses E2 = 192 (now 106); omits discovery cost; a concatenated lane cannot interact with piece features |
| S1 7.2.2 | Pick checkpoints by fixed-node games | WEAK for Fork | 0 | late checkpoints differ ≤ 3 Elo against ±10 resolution; average instead |
| S1 7.2.3 / S2 N2 | λ schedule / WDL-heavier end | WEAK now | −5 to +4 | Fork's results come from 20k/4k-node play and are biased in known directions (C, E2) |
| S2 N1 | Purge/upsample by labeller | PLAUSIBLE | −2 to +6 | = T4 |
| S2 N3 | King buckets retest | WEAK | −5 to +5 | refresh cost; H-512 null; C4 and M3(b) are cheaper probes of the same need |
| S2 N4 | Eval scale into SPSA | PLAUSIBLE | 0 to +3 | fold into item 12 |
| S2 N5 | Start-position distribution | PLAUSIBLE | 0 to +3 | = T8(a) |
| S2 N6 | Endgame/special-book slices | PLAUSIBLE | = C5 | = C5/T7 |
| S2 N7 | Fifty-move inputs | WEAK | 0 to +1 | C E5: search already sees fifty-move draws 10-30 plies ahead |
| S2 N8 | Multi-layer head | WEAK for Phase 4 | −10 to +8 | speed (the output is 13.5% of node time); AF-S's quantization loss; a zero-init skip head keeps it warm-startable |
| S2 N10 / idea 46 rank 1 | Distillation from S512+X (+ auxiliary heads) | REFUTED | −3 to +2 | the teacher is weaker than the student; no generalisation gap to regularise |
| H3 | Zero-row / zero-lane calibration + throttle | SOUND | enabler | none; it prices C4/M3/H8 before any training |
| H8 | int8 narrow threat lane (0.88-0.93x) | WEAK | −8 (−20 to +5) | needs FN ≥ +19 to +24; a narrow additive lane is unlikely to keep S512+X's +25.7 |

---

## 2. My own checks (the evidence this file adds)

### 2.1 The g3s2 training curves, with trends [V][C]

Validation loss on g3s2-val, from K `g3s2-out/result/s512pp-*/val.txt`. "Slope" is OLS per 100
superbatches, with its SE inflated by (1 + r₁)/(1 − r₁) for lag-1 autocorrelation.

| Run | LR phase | Window means | Slope per 100 sb (± SE) |
|---|---|---|---|
| warm s1 | 1e-4, superbatches 21-180 | 0.019363 / 0.019400 / 0.019352 / 0.019356 | −0.27e-5 ± 4.1e-5 |
| warm s2 | 1e-4, superbatches 21-180 | 0.019366 / 0.019417 / 0.019346 / 0.019372 | −0.13e-5 ± 4.2e-5 |
| warm s1 | 1e-5, superbatches 201-360 | 0.019186 / 0.019173 / 0.019159 / 0.019165 | −2.1e-5 ± 2.1e-5 |
| warm s2 | 1e-5, superbatches 201-360 | 0.019205 / 0.019182 / 0.019168 / 0.019173 | −3.1e-5 ± 2.1e-5 |
| scratch s1 | 1e-4, superbatches 201-360 | 0.019834 → 0.019676 | −13.4e-5 ± 3.6e-5 |
| scratch s2 | 1e-4, superbatches 201-360 | 0.020079 → 0.019778 | −25.6e-5 ± 4.3e-5 |

Pooled over the two warm seeds (treated as independent):
- 1e-4 phase: **−0.2e-5 ± 2.9e-5 per 100 superbatches**;
- 1e-5 phase: **−2.6e-5 ± 1.5e-5**.

The drop at superbatch 181 is −1.9e-4 (s1) and −1.6e-4 (s2) within 20 superbatches.

The same recipe on the pre-g3s2 nets (K `pp-out`, `r3v2-out`; warm at 1e-3 then 1e-4,
non-interleaved, validation g3s1-val, window 271-360):

| Net | seed 1 | seed 2 | best kept |
|---|---|---|---|
| S512r3 (no new inputs) | 0.019525 | 0.019537 | never beat its initial 0.01930359 |
| S512+X | 0.019083 | 0.019057 | 0.01887023 (s2, superbatch 303) |
| S512+PP | 0.019708 | 0.019572 | 0.01929241 (s2, superbatch 350) |

S512+PP's played checkpoint is **2.8e-4 below its own run's window mean**: a 2.5σ selection on
a 20k-position set. Its run was still falling at 1e-4 (181-270 → 271-360: −4.0e-4, s2).

### 2.2 What g3s2-val's scored prefix contains [V]

`valcomp.py` splits both validation files into games and replays them with the trainer's
filter (saved, |score| ≤ 20000, not in check, not a capture or promotion):
- g3s2-val holds 1,800 games, 73,517 kept positions;
- the trainer's 20,000 are reached at game index 493;
- the order is round-robin over 30 sources: 25 old ones, then the 5 new (game indices 25-29,
  55-59, 85-89, ...).

The prefix therefore contains:
- 414 g3s1-era games;
- **64 games of g3b-g3e (2,142 positions, 10.7%)**;
- **16 slice positions (0.08%; 2.1% in training)**.

The files differ from byte 9,917 because the new sources are interleaved, not appended. T §2.3
and A1 §3.2 ("none of the five new sources") are refuted. The narrower true statement: the set
cannot see the slice, and sees the new parts at 1/6 of games.

### 2.3 The scale fit with and without the training filter [V]

`sfit.py` uses fit_scale.py's own `fit()`, over the first 150k positions of each file:

| File | Labeller | S (filtered) | S (unfiltered) | MSE at fit / at 92 (filtered) |
|---|---|---|---|---|
| g3f-w00 | S512+PP | 83.8 | 82.8 | 0.04937 / 0.04953 |
| g2s1-g2 | S512 | 94.7 | 88.7 | 0.05270 / 0.05271 |
| g3s2-val (all sources) | mix | 89.2 | 88.7 | 0.05107 / 0.05108 |

- S falls with labeller strength: newer labellers are more confident relative to the outcome.
- The snapshot's mix sits near 89; g3s3 adds 16% S512+PP/S512ppr2 labels, so about 88.
- The outcome-MSE gain from refitting is 1e-5 on the mix. M6 is worth about 0 Elo.

### 2.4 Other spot-checks [V]

- **g3g's size.** The part record's `positions_target` 366,424,464 equals g3f's target minus
  g3f's positions *including unsaved* (62,172,094, of which 28,353,253 unsaved). `need_bytes`
  1.69 GB = 366 M × 4.6 B. So the target counts every record: about 199 M saved and about
  135 M kept (T §2.5 is right; HANDOFF's UNVERIFIED note resolves this way). The arrival
  estimate is about 2:20 PM 2026-11-08 (285.8 M left at 2,707 per second from 9:00 AM).
- **Kaggle rate.** Warm s1: 7,741 s for 360 superbatches = 21.5 s per superbatch on one T4.
  The whole four-run session took 15,570 s.
- **The trainer.** The LR is lr·0.1^⌊(sb−1)/lr_step⌋ (main.rs ~1214); `--resume` loads the
  optimiser state; a branch at constant LR needs no code. Validation runs at batch 1, one
  position at a time with a host transfer each (main.rs ~1166-1187). Raising
  `--val-positions` 4x therefore adds measurable time per superbatch: score large sets offline
  with `--superbatches 0` instead.
- **C's tables** (scratch-c `c2-*.json`) reproduce C's E2 numbers exactly. They also show that
  `end:islands_lead_ge3`, the leader's *own* ≥ 3 islands, is +4.56 (STC) and +5.15 (LTC). That
  is the same sign as "the opponent has ≥ 3 islands" (+5.71 / +6.90). Fragmented structure
  converts more *for whoever leads*. This is a variance or position-type effect, not knowledge
  that weak pawns lose.
- **M2's martingale slope.** From M's own moments: 0.047 = 0.0273 + 0.0143 + 2E[eΔ], so
  E[eΔ] = 0.0027 and the slope is (0.0143 + 0.0027)/0.0143 = **1.19**, not 1.09 (M halved the
  cross term twice). Same direction, stronger: S = 92 is under-confident on g3f.

---

## 3. Contradiction rulings

### 3.1 Undertrained (A1) against "the final LR sets the loss" (T2, W3)

**Ruling: T2/W3 are right for warm retrains. A1 is right for scratch runs. A1's main argument
is a non sequitur.**

- **Warm.** The 1e-4 phase has no detectable trend (−0.2e-5 ± 2.9e-5 per 100 superbatches).
  - A1 B1 claims −1e-4 to −2.5e-4 from 360 more stable superbatches. That needs −2.8e-5 to
    −6.9e-5 per 100. The upper half is excluded at about 2.4σ; the low end is about 1σ away.
  - The caveat that keeps this from being a refutation: the trend of the *1e-4-floor* loss need
    not equal the trend of the *annealed* loss. Only T2's branch cooldowns measure the latter.
- **The 1e-5 tail** shows a weak decline, −2.6e-5 ± 1.5e-5 per 100 superbatches. T's "flat"
  overstates; low-LR length is worth perhaps +1 to +2 Elo per 100 superbatches, diminishing.
- **Scratch** falls 7-13 standard errors per 100 superbatches at 1e-4, so it is
  compute-limited, as A1 says.
- **The warm-versus-scratch gap at the same LR** (1e-4 floors: warm 0.01937, scratch
  0.0197-0.0198 at 360) is banked lineage compute. A1's "the lineage effect is a compute
  effect" stands.
- **"No generalisation gap, therefore undertrained" does not follow.** No gap means no
  overfitting. Validation lies below training because the validation mix weights all 30
  sources equally, an easier mix.
- **The size of what is left.** W3's bound is better founded than T2's α = 0.5 alternative.
  Under Adam with noise-dominated gradients the stationary weight variance scales with η, so
  the quadratic excess scales with η (α = 1). The √10 ratio of loss standard deviations comes
  from the linear term (W3's reading).

  So the excess left at 1e-5 is about 1.6e-4/9 to 1.9e-4/9 ≈ **2e-5**. Cooldown plus averaging
  is worth **+1 to +3 Elo**, not +2 to +7.

**What it implies for S512ppr2's +20.1 (± 7.2).** Every Fork net before it ended at 1e-4, and
S512ppr2 was the first annealed to 1e-5. Its window loss is 2.2e-4 below S512+PP's 1e-4
equilibrium, estimated on this set: the first warm superbatches sit at 0.01937-0.01940.

T's "+17 from the anneal" is circular. 9.3 Elo per 1e-4 *is* 20.1/2.16e-4, the same pair. With
the independent rates (S512 against the B0 control 10.6, XGR 6.4, S512+X 6.0, all FN) the
anneal maps to +10 to +23.

| Component | Evidence | My share of +20.1 |
|---|---|---|
| Anneal to 1e-5 (one-time, already banked) | all of the measurable loss gain arrives at the drop | **+8 to +15** |
| New data and labels (+25% data, +16 mean labeller Elo) | the validation set sees new parts at 11%, so it under-measures them; A1's model gives +15 but is zero-dof | **+3 to +10** |
| Syzygy slice | 351 → 8 misjudgments, all 3-piece positions that both engines probe in SPRTs | **0 to +3** |
| Interleaving | changes the 1e-4 equilibrium (an iid stream), effect unseparated | 0 to +4 |

These ranges overlap and sum to 11-32, bracketing 20.1. **T6 decides it**: S512+PP's float
weights, 40 superbatches at 1e-5 on its own data (g2s1 + g3s1), 14 GPU-minutes, then **one FN
stage of 1,600 games against S512+PP**. Judge by Elo, not loss, since the loss rate is the
circular quantity:
- ≥ +12 means the anneal explains most of the gain;
- ≤ +5 means data and labels explain most of it.

**For 7b:** the anneal cannot be re-banked. 7b gains only from data and labels plus about
+1 to +3 from a deeper cooldown and averaging.

### 3.2 The result weight λ: M2, W4, T5, S2's WDL-heavier end, C's rook-ending prediction

The agents describe two different quantities.

- **Variance (M2, W4).** The result half is noisy and correlated (ICC 0.674, design effect
  about 24). TD-k or λ-return targets are lower-variance, unbiased stand-ins *if* scores are a
  calibrated martingale. In an ample-data run, variance affects only optimisation noise, and
  the cooldown and averaging (§3.1) already remove most of that floor. M2's Elo derivation
  ("worth 1.5x more low-LR samples, so +3 to +7 via B1") rests on B1's stable-phase premise,
  which §3.1 undermines.
- **Bias (M's generational recursion, T5, C).** The result is the only channel through which
  horizon-invisible knowledge enters the loop: u_{n+1} = (1 − w)·u_n + w·u_r. But Fork's
  results come from games in which **half the moves are 4k-node moves**: g3/g3f settings
  `save_percent 50, unsaved_nodes 4000` [V]. Their bias is measurable and class-dependent:
  - drawish endings: data −2.25, STC −5.93. The result half pushes the right way, too
    weakly; raising w helps.
  - rook endings: data +2.89, STC −1.71. The result half pushes the wrong way; raising w
    hurts, as C predicts.
  - islands and open positions: data ≈ 0, STC +5-7. The shallow result carries nothing;
    w is irrelevant.

  The class signs disagree, so a global w is a compromise. TD-k cuts the weight on
  beyond-16-ply outcomes 4x (w·c = 0.125), slowing exactly the long-horizon conversion
  knowledge C flags.
- **S2's "WDL-heavier end helped elsewhere"** is SPRT-selected, from engines whose WDL comes
  from different (often deeper) play, and includes a −57. It does not transfer as a prior for
  Fork's 20k/4k-node results.

**One recommendation.**
1. Keep w = 0.5 in 7b's control and main arms.
2. Do not run a blind w ladder, a WDL-heavier end, or TD-k yet.
3. Measure the bias directly, because w* is the regression of the deep-play outcome residual on
   the shallow-play one (T5's formula). M's bias-optimal formula is the same quantity.

**The cheapest decisive experiment.** T5's pilot, corrected:
- **Positions:** 1,000 held-out kept positions.
- **Shallow arm:** datagen's exact rules (20k nodes, 50% of moves at 4k, adjudication 700 cp
  × 8, Syzygy 5).
- **Deep arm:** 100k nodes, same rules, no split.
- **Two replicate games per position per arm, made independent.** Fixed-node single-thread
  games from one position are otherwise identical; use a per-game node jitter or a random TT
  seed (to be checked).
- **Cost:** about 1-1.5 h on 2 threads (jobctl `measure`).
- **Read first:** the decisive-share gap.
  - **< 3 points:** stop. w cannot matter much; record 0.5 as measured.
  - **≥ 8 points:** run the full 4,000-position w* estimate (about 5 h on 2 threads). Its SE is
    ±0.15-0.2, not T5's ±0.1, unless the true residual variance is ≥ 0.02.
  - **w* ≤ 0.35:** one arm in the retrain after 7b (7c), S re-matched, decided by FN then STC
    [0, 5].
- **C's prediction made cheaply falsifiable:** compare the arm's *static* eval against Syzygy
  WDL on 5-man KRPvKR and KPPvKP sets, minutes, instead of rook-ending residuals from 1,600
  games, which cannot resolve 1-2 points (SE ≈ 1.3).

TD-k (M2/W4) becomes a second-line arm only if the variogram recomputed *with the training
filter* (free, existing shards) still shows the result residual absorbed ≥ 40% within k plies.

### 3.3 The training scale (M6)

The trainer uses S = 92 for every run (retrain_g3s2.py `SCALE = 92`; main.rs `mapper`) [V].
M's 84-87 came from single parts without the training filter. With the filter the snapshot's
mix fits about 89 (§2.3) [V].

What changing S would do:
- it shifts the score half's confidence by about 3%;
- outcome-MSE improves by about 1e-5;
- S_play is re-matched afterwards anyway.

Ruling: keep 92 in 7b. Run fit_scale.py on 2 M positions of the actual g3s3 mix as a free
pre-step, and change S only if it lands outside 88-96. Per-labeller S (84-95) is the only
variant with any spread. It is not worth building.

### 3.4 The g3s2-val claim

Refuted as stated (§2.2). The decisions it was said to invalidate are not invalidated for the
new *parts*: the warm/scratch choice and S512ppr2's loss saw g3b-g3e at 10.7% of positions. They
are blind to the *slice*.

For g3s3's validation set:
- the existing interleaving tool already spreads sources;
- add 60 held-out games from each of g3f and g3g;
- keep the per-superbatch 20k for monitoring (batch-1 validation is slow);
- score final and averaged checkpoints offline on all kept positions (about 80k) with
  `--superbatches 0`.

### 3.5 Threat inputs against king-zone pawns against the rest

Prices at 1.5 Elo per 1%. Hurdle = 152·ln(1/r) + 5 at FN.

| Direction | nps (source) | Price | FN needed | My FN expectation | Net | Effort |
|---|---|---|---|---|---|---|
| H8 threat lane, w = 64, int8 + discovery | 0.88-0.93 (H8, estimate) | 11-19 | +16 to +24 | +6 to +18 | **−8 (−20 to +5)** | 10-15 d |
| S1 narrow threat accumulator, w = 128 | 0.83-0.89 once discovery is added (H8's own total) | 18-28 | +23 to +33 | +8 to +20 | −12 | 10-15 d |
| C4 king-zone pawn links | 0.95-0.97 (C, reasoned) | 4.6-7.8 | +10 to +13 | +4 to +15 | **+1 (−5 to +6)** | 5-8 d |
| M3(a)/C7 passers (pawn-change trigger) | 0.98-0.99 (M, C, reasoned) | 1.5-3 | +7 to +8 | +2 to +10 | **+2 (−3 to +6)** | 5-8 d |
| W2 output experts (not an input) | 0.99-1.00 | 0-1.5 | +2 to +7 | +2 to +8 | **+2 (0 to +6)** | 2-4 d |

Why threats come last:
- **(a)** S1's break-even uses E2 = 192 (from S512+X). With E2 = 106 the hurdle at 0.91 is 14
  Elo.
- **(b)** S1 omits discovery. H8 adds it and lands at 0.83-0.89 for w = 128.
- **(c)** A lane concatenated before the output adds threat terms *additively*. It cannot form
  the threat × piece interactions that M's measurement (d) shows Fork's net actually uses
  (links move by 0.88 of their spread when a piece leaves). Idea 46's judge reached the same
  conclusion: "a separate narrow lane is dominated" by column-restricted rows. So the lane
  keeps less than S512+X's full-width +25.7.
- **(d)** The base is stronger now. S512+X's +25.7 was measured against S512r2, and threat
  knowledge's marginal FN on S512ppr2 is likely lower.
- **(e)** Fork's only T-type data point (S512+X) sits 26 Elo *below* the speed line (3.3σ).

SF's threat gain does grow with TC (S1 §2). That keeps threats alive as a TCEC-only build
question for the owner. It is not a Phase 4 SPRT item.

**Ruling.** None of C4, M3(a)/C7 or W2 has a strong prior:
- C4's king evidence is 4-7 positions per threshold, S512r2-era, and invisible in self-play.
- M3/C7's island and passer evidence is confounded (§2.4).
- The β pricing behind M3 is noise (§2.1).

So the best Elo per effort is **the screen, not a family**:
1. H3's zero-row/zero-lane build: about 1 day, then exact nps for every design.
2. One combined deep-relabel job (T3 + C2 + A1's label noise): about 2 h on 2 threads. Then
   the residual of frozen S512ppr2 against *deep* labels, by family (king-zone pawns,
   pawn-status, threats), with M1's quiescence-resolved residual as the T/U separator.
3. W2's probe: CPU hours, which also screens idea 46 rank 2's threat-class heads as one gate.

Then build at most one input family: the one whose (deep-residual gain) / (H3 price) is best.
Kill all of them if none explains ≥ 0.5% of the deep-label residual variance (idea 46 rule 3's
scale).

### 3.6 Distillation from S512+X (idea 46 rank 1)

**Confirmed demoted. I go further: REFUTED for Phase 4.** New decisive point: by the chain,
S512+X (FN +25.7 against S512r2) is about 20 FN Elo below S512+PP (+46.1 against S512r2) and
about 40 below S512ppr2 (+20.1 more). A teacher weaker than the student at fixed nodes can only
help through its distinctive knowledge, and that knowledge fails on two counts:
- it is exposure/threat knowledge, which the 20k-node search labels already contain in
  resolved form, so the student's limit is capacity, not target information;
- distillation's other benefits (regularisation, label denoising) have nothing to fix: there
  is no generalisation gap, and the cooldown removes noise.

The auxiliary-head arm (threat targets) is at most a free rider (0 to +2). T's alternative,
S512+X *as a labeller*, is also dominated now: it labels worse than the default at fixed nodes.
Re-opening needs an S512ppr2+X teacher, which costs a training session and an engine
architecture for a mechanism with nothing to act on.

---

## 4. Item 7b: the next retrain on g3s2 + g3f + g3g

**Data and timing.**
- g3s3 = g3s2's training files + g3f + g3g. New kept positions about 158 M against g3s2's about
  848 M: +19%, 0.25 doublings. Mean labeller +20 chain Elo [V counts].
- g3g reaches its target about 2:20 PM on 2026-11-08.
- Then: seal, verify, upload g3f (0.29 GB) and g3g (1.69 GB; upload time UNVERIFIED), and the
  hash check in a CPU session.
- Validation g3s3-val: the existing interleaving tool plus 60 held-out games from each of g3f
  and g3g. Monitor the 20k prefix per superbatch; score finals offline on all kept positions.
- Fixed settings: S = 92 unless the free fit leaves 88-96 (§3.3); w = 0.5; `--interleave`.

**Arms.** All warm from S512ppr2's float weights, one Kaggle session on T4 x2.

| Arm | What | GPU-h | Purpose |
|---|---|---|---|
| **R1, R2 (control)** | the owner's standard recipe, unchanged: LR 1e-4, tenfold drop after 180, 360 superbatches, seeds 1 and 2, best checkpoint by validation loss. **Script change only:** keep R1's superbatch-180 checkpoint (with optimiser state) and the float weights of superbatches 331-360 | 4.3 | the decision baseline; also yields the free averaged candidate R1-avg |
| **CD (cooldown branch)** | `--resume` R1's superbatch-180 checkpoint; a zero-code staircase: 20 superbatches at 1e-5, 15 at 3e-6, 15 at 1e-6 (constant-LR resumes with a huge `--lr-step`); average the last 15 | 0.3 | tests the residual floor (§3.1: expect −1e-5 to −2.5e-5 against R1's 1e-5 window mean) at a sixth of the tail's GPU |
| **D1 (anneal only)** | S512ppr2 at 1e-5 for 60 superbatches on g3s3, no 1e-4 phase | 0.36 | does a warm retrain need the stable phase to absorb new data? If D1 matches R1, future retrains cost about 20 minutes |
| **B (recency), conditional** | as R1, with every other g2s1 file dropped and g3g listed twice | 2.15 | runs only if the deep-label gold set (T3 + C2) exists by then; otherwise dropped (no unbiased yardstick for a data-mix change) |
| T6 (attribution), optional | S512+PP + 40 superbatches at 1e-5 on g2s1 + g3s1 | 0.24 | settles §3.1's split (Elo-judged); can instead run before 7b |

Total: 5.2 GPU-h without B, 7.3 with B. Wall time about 3-4.5 h (GPU0: R1 then B; GPU1: R2, D1,
CD after R1 passes superbatch 180, T6). That is well inside the 30 GPU-h week. The
T4-x2-counts-once assumption is UNVERIFIED.

**Decision rule** (declare before the run).
1. **Validity.** Every warm arm reproduces S512ppr2's superbatch-0 loss on g3s3-val.
2. **Candidate** (same target, same data). Compare on *all* of g3s3-val's kept positions,
   offline, never by best-of-N:
   - R-best (the owner's rule);
   - R1-avg (the mean of superbatches 331-360);
   - CD-avg.

   Take the lowest. If an averaged candidate is within 1e-5 of R-best, prefer the average: it
   carries no selection bias. Differences under 1e-5 are ties.
3. **Gates as today:** parity chain, netcheck, scale match against S512ppr2, endgame check
   ≤ 15 of 900 (S512ppr2: 8), quantization loss max ≤ 12 cp. Add C6's 4-5-man classes as
   report-only.
4. **STC SPRT [0, 5] against S512ppr2** (the standard).
   - **Prediction:** +4 to +12 Elo (central +7). If T6 has run and shows the anneal ≥ +12,
     move the central value to +5.
   - **Refuted** if H0, or the final estimate is < +3. Then the data/label model overstates
     this scale, and the next retrain waits for ≥ 150 M new kept positions from a promoted
     labeller (T's cadence rule).
5. **Information** (logged; nothing ships on it).
   - **D1 against R1's 1e-5-phase window mean:** within 3e-5 with an equal endgame check →
     propose the short recipe to the owner. Worse by > 5e-5 → the stable phase carries learning,
     and the recipe stays.
   - **CD-avg against R1's window mean:** confirms or refutes the about-2e-5 floor.
   - **B against R1 on the gold set (≥ 2e-5):** B wins → 7c adopts half-weight g2s1; else
     uniform stays and idea 47.1's relabel is dropped for Phase 4.
6. **No λ, TD-k, cross-entropy or new-S arms in 7b.** Each changes the target, needs its own S
   rematch and FN/STC, and their measurement (§3.2) has not run. Exception: if T5's corrected
   measurement finishes before the session with w* ≤ 0.35 at SE ≤ 0.1, arm C (w = w*)
   replaces B.

**Before 7b** (all cheap, all before 2026-11-08 afternoon if the owner approves):
- W5's soup: average warm s1 and s2's `weights.bin` and score on g3s2-val. CPU or a
  `--superbatches 0` run; minutes.
- T6 on Kaggle: about 0.5 GPU-h, then 1 FN stage.
- The combined deep relabel (T3 + C2), a jobctl `measure` job of about 2 h on 2 threads beside
  g3g. It needs a UCI driver or a relabel mode (UNVERIFIED whether one exists).
- fit_scale.py on the g3s3 mix.
- T5's corrected pilot (§3.2).

---

## 5. Per-proposal notes (only where I have something substantive)

**T1.**
- Its forecast stacks the A1 model's +9 to +14 on T2's +2 to +7, then discounts. Two
  corrections:
  - T2's part is +1 to +3 (§3.1);
  - the data/label model's only validation point, S512ppr2's "+15 predicted against 20.1
    observed", is contaminated by the anneal (§3.1).

  So **+4 to +12, central +7.**
- T1's own caveat ("if T6 shows the anneal explains most, about +7") is the scenario I consider
  more likely.
- T1's schedule (100 superbatches at 1e-4, then 40 down to 1e-6, then 10) drops the owner's
  control. My version keeps the control intact and branches from it (§4), which costs less
  GPU and keeps continuity.
- Its arm R ("continuity") becomes the main control, as the owner's recipe requires.

**T2.**
- Mechanics confirmed [V]: the window means, the best-of-N bias (7.8e-5 and 7.4e-5), and seeds
  agreeing within 0.8e-5 by window mean.
- Its noise-floor exponent argument is backwards (§3.1). Keep the experiment; shrink the Elo.
- The branch probe is the right measurement of what A1 B1 and W3 D3 wanted, at a third of the
  GPU.
- Code needed: none for staircase branches (constant-LR resumes, main.rs ~1214); a Python
  change in the Kaggle script to keep the checkpoints.
- Caveat T noted: a resumed reader restarts its data pass. That is harmless at 30-50
  superbatches on 1.4 B positions.

**T3.**
- Cost and design are fine. Two corrections:
  - gold loss is still a static-eval loss against search-resolved targets, so it credits T-type
    knowledge just as validation loss does. Use it to compare *data mixes and recipes within
    one architecture*, never architectures: M1 serves that.
  - its kill test (gold ranks S512ppr2 < S512+PP < S512r2) is biased toward passing, because
    the gold labels come from S512ppr2's own deep search.

  Sharper kill: the gold-loss *differences* must order the two known promotions by size
  (S512+PP over S512r2 at +32.7 STC; S512ppr2 over S512+PP at +20.1), and the S512+X against
  S512r2 comparison must be reported as the known failure mode.
- Merge it with C2 and A1's label-noise run: one sample, one relabel, four outputs.

**T5.**
- Three fixes:
  - (1) independent replicates (determinism, §3.2);
  - (2) the shallow arm with the split search and adjudication, or w* measures the wrong
    bias;
  - (3) SE: per-position Var(p̂) ≈ 0.1 with 2 games, so SE(Cov) ≈ √(0.1²/4000) = 1.6e-3. Over a
    residual variance of 1e-2 that is ±0.16, plus denominator noise, so ±0.15-0.2 unless the
    variance is larger.
- The idea is right: it is the one proposal that estimates the bias directly.

**T6.** SOUND. Add the Elo readout (§3.1); the loss readout alone uses the circular rate.

**T7 / C5.**
- Same need. C5's 80k-node outcomes attack the measured depth bias (E2), and its pilot gate
  (calibration of the pilot data before any training) is a good cheap kill.
- T7's "score adjudication off" belongs inside C5, so conversion phases are recorded.
- Cost: 10.5 h of the 10-thread machine, displacing about 100 M normal records.
- Elo in SPRT conditions is small (+0 to +4). It is a TCEC-relevance bet for the owner. Not in
  7b.

**T8.**
- (a) The 2026-09 book at g3h's start is free. Expected 0 to +3; the duplicate count first,
  minutes.
- (b) Defer.

**T9.** A zero-init skip head (new MLP head added to the old linear head with zero output
weights) keeps even multi-layer designs warm-startable. That removes T9's main motivation.

**M1.**
- Plausible and cheap, and the most useful new instrument here. It needs `evalfens`' QS twin
  (a new command, name screening).
- Run it on the *played* nets over a fresh 200k set. M's prediction (i) uses best-of-N losses
  (10.4 ratio). On window means the static PP gain is negative (§2.1), so restate (i) as: on a
  fresh set, X's L_d2 gain over S512r3 is ≤ 2x PP's, where static loss gives X ≫ PP.

**M2.**
- Corrections: the slope is 1.19 (§2.4). Its "noise" bound measures departure from p_t, which
  includes signal. Under W4's martingale model, p_{t+k} − p_t is innovation noise relative to
  V_t, and both targets are unbiased: the gain is variance only, hence small after the
  cooldown.
- The Elo path through B1 fails (§3.1).
- Kept as a second-line target arm after T5 (§3.2).

**M3.** Mechanism sound (ridge-function conjunctions; links' third-order use, measurement d).
But:
- the pricing rule ΔL_U ≥ 0.11Δc/β is unusable (β is noise, §2.1);
- C's passer and island evidence is confounded (§2.4).

Screen it; do not build on its numbers.

**M4.**
- The identity Var(V) = Var(e) + E[(V − e)²] is right, and the "error spread shrinks as nets
  improve" argument stands on its own.
- But the cited trend is wrong. S_play/S_train is S512 101/105 = 0.96, S512r2 92/92 = 1.00,
  S512+PP 90/92 = 0.98, S512ppr2 89/92 = 0.97 (nets.md [V]). There is no compression trend; the
  101 → 89 is mostly round 1's S = 105 against round 2's 92.
- Fold m into item 12's SPSA as one parameter; no separate ladder.

**M5.**
- With 700 cp × 8 adjudication, the data holds few post-advantage positions. CE's extra
  gradient on decided positions lands mostly on the 2.1% slice and the adjudication run-in.
- Low value until C5-type data exists. Then it is a sensible arm.

**M7.** Fine. Idea 44's validation session compares a 2e-5 effect against 1.2e-5 seed spread,
so retire it.

**W1.**
- [C] I reproduced the e-fold losses: 0.050/0.066 (STC), 0.050/0.067 (LTC), 0.129/0.206 (TCEC,
  60/80 moves).
- "Uniform spend is optimal" assumes equal move importance. Front-loading may be correct, so
  (b) is an upper bound.
- Part (a) is the node-share family the synthesis already ranks.

**W2.**
- Best capacity-per-effort item in my domain. The probe also tests "is the current readout
  converged?" (refit the 8 phase heads), which cross-checks §3.1.
- Add idea 46 rank 2's threat classes as candidate gates (overlap).
- Keep the 2 M-position held-out set disjoint from the fit set.

**W3.** D1 and the cooldown are in 7b. D3's length premise is not supported by the 1e-4
slopes. The trunk saves nothing: the re-heat rise *is* the 1e-4 noise floor, which the anneal
removes regardless of the starting point.

**W4.**
- The inverse-variance w(p) gives decided positions the result and balanced ones the score.
  That is variance-optimal but ignores b_r. C shows b_r is large and signed per class, in
  endgames exactly where w(p) would lean on the result.
- Not before T5.

**W5.** SOUND. The soup test is free and checks the averaging premise before 7b.

**C1.** Run one gauntlet with S512ppr2 (one GitHub run) before trusting the king lifts. They
are S512r2-era, and 4-7 positions per threshold.

**C3.**
- Plausible, zero speed. Its E2 basis is the strongest of C's findings (one-wing, ≤ 4 pawns,
  pure opposite bishops: −4.5 to −8 points at STC/LTC, z 5-16).
- But STC → LTC growth is only about 1 point (z about 1-2). The big step is data → STC, which
  is confounded with openings, split-search play and adjudication.
- Fitting on SPRT games is an owner decision (test-data use).

**C4.**
- The arithmetic checks: 12-25 games × 0.5/600 → +7 to +15 against strong anchors. But the
  "10-20% of losses fixed" is assumed, and self-play shows no king residual (z 0.5).
- Gate it behind the deep-label residual screen, as C itself proposes.

**C7.** Evidence confounded (§2.4). Fold the passer plane into M3(a)'s screen candidate and
drop the rest unless the screen favours them.

**S2 N8.** If a head is ever tried, use a zero-init skip head (warm-startable) and price it with
H3's throttle knob first. The output layer is already 13.5% of node time, and AF-S's 32 cp
quantization loss is the warning.

**H8.**
- The cost arithmetic is careful. The gap is on the value side: a narrow additive lane, a
  stronger base, and the T-type outlier (§3.5).
- Keep the H3 zero-lane measurement (bench-identical, about 1 day plus 1 h) as the go/kill
  before any of H8's 10-15 days.

---

## 6. Overlap map (same idea, best version named)

| Idea | Proposals | Best version |
|---|---|---|
| Cooldown / averaging instead of best-of-N | T2, W3 (D2), W5, A1 B1 (part), S2 (deeper final decay, concept) | T2's staircase branch from the control plus W5's averaging (§4 arm CD) |
| Anneal attribution | T6, W3 D1 | T6 on S512+PP's data (Elo-judged) plus D1 on g3s3 in 7b |
| Longer low-LR training | A1 B1, W3 D3, T9 (scratch) | T2's branch probe (measures annealed loss against stable compute); T9 only for scratch |
| Label recency / purge | T4, S2 N1, W critique 3, A1 B2 / synthesis M13, idea 47.1 | T4 arm B, gold-set judged |
| Deep relabel measurements | T3, C2, A1 label noise (synthesis M7), M's nugget, idea 46's residual target | one combined job: stratified held-out sample, deep labels, four outputs |
| Searched yardstick | M1 (QS/depth-2), C2 (deep labels as the residual target) | both: deep labels as the *target*, QS-resolved eval as the *prediction* |
| Result weight / target | T5, M2, W4, A1 B4, S1 λ schedule, S2 N2, M5, C's L4 caution | T5's corrected measurement first; one arm after |
| Scale | M6, S2 N4, M4 (margins) | none for 7b; fold S and m into item 12's SPSA |
| Endgame-start data | T7, C5, S2 N6, idea 11 | C5 with T7's adjudication setting, pilot-gated |
| Pawn-structure inputs | M3(a), C7 | one passer plane behind the screen |
| King-relative pawns | C4, M3(b), S2 N3 (buckets) | C4 behind the screen; buckets later |
| Threat inputs | H8, S1 7.1.k, S2 N9, idea 46 ranks 3-5 | H8 (it prices discovery), parked |
| Output-side capacity | W2, idea 46 rank 2, S2 N4 (output tuning) | W2's probe with threat classes as candidate gates |
| Distillation | idea 46 rank 1, S2 N10, T's labeller variant | none (refuted) |
| Speed pricing | H3, M §2.4 (0.11 Elo per cycle), A3's throttle | H3 |
| Validation-set repair | T1 step 3, A1 B6, synthesis M8, W5 | interleaved set plus g3f/g3g sources, offline full-set scoring, no best-of-N |

---

## 7. Corrections to Phase A and to other specialists (summary list)

1. **A1 §3.2 and T §2.3:** the scored prefix holds 10.7% new-part positions and 0.08% slice,
   not none (§2.2).
2. **A1 §3.1's "≈ 41 Elo per 1e-4" for links and M's β ≈ 102** are best-of-N artefacts. On
   window means the links run's static loss is worse than its control (§2.1).
3. **A1 §5.1's "smooth fall to 0.01912 by superbatch 180"** is a single point in a band of
   0.0191-0.0195. The 1e-4 phase is trendless (§2.1), as W said.
4. **T's "+17 from the anneal"** is circular (§3.1).
5. **T's residual floor (2-8e-5)** should be about 2e-5 (§3.1).
6. **M's martingale slope** is 1.19 (§2.4). M's "S = 92 is 8% too high" holds per part for the
   newest labellers but not for the snapshot's mix (§2.3).
7. **M4's compression trend** is the training-S change (§5).
8. **C's island finding** is a position-type effect (§2.4).
9. **S1 7.1.k's break-even** uses the retired E2 = 192.
10. **Synthesis rank 2** ("undertrained, +8 to +20 at stake") should read: "warm nets are
    LR-floor limited and already annealed: +1 to +3 from cooldown and averaging, plus whatever
    stable-phase compute buys (unmeasured, 95% CI roughly 0 to 1e-4 per 160 superbatches);
    scratch nets are compute-limited".

---

## 8. What I could not verify

- **Whether the 1e-4 phase carries learning that only an anneal reveals.** The floor-loss trend
  is flat, but the annealed-loss trend needs T2's branches.
- **The split of S512ppr2's +20.1.** T6 is needed; my ranges are inferred.
- **Whether two parallel trainings on T4 x2 count once against Kaggle's weekly quota**, and the
  upload time for g3g's 1.69 GB.
- **Whether a relabel mode or batch-EPD scorer exists** for the deep-label job, and whether
  datagen accepts arbitrary FEN starts with zero random plies (C5/T7).
- **How fixed-node playouts can be made independent** for T5's replicates (node jitter or
  hash seeding): not checked in the source.
- **Every input design's nps** (C4 0.96, M3 0.99, H8 0.88-0.93). All are reasoned estimates
  until H3's build.
- **My scale fits** use the first 150k positions of one file each (about 4,000 games). The SE
  of each S is perhaps ±2-3. The 2 M-position fit on the g3s3 mix is the real check.
- **The two warm seeds' independence** in the pooled slope (they share initial weights and
  data, differ in order). The pooled SE may be optimistic by up to √2.
- **Whether averaging the warm seeds helps** (W5's soup): not run; it needs a forward pass I
  did not execute.
- **The external Elo figures quoted from S1/S2** (λ schedules, purges, threat gains). They are
  SPRT-selected results of other engines, used only as priors; none was re-checked here.
- **No engine source was opened** and no engine was run. Every computation was read-only
  Python over Fork's own Kaggle records, shards and the specialists' saved outputs. No other
  engine's constants appear in this file.


---

# B14. Skeptic 2: search, interaction, tuning, testing, systems and TCEC

## Skeptic 2: search, search-eval interaction, tuning, statistics, systems, TCEC conditions

**Summary.** I re-derived the load-bearing arithmetic in the S, I, O, ST, H and W1/W6
proposals, re-ran the SPRT operating characteristics myself, and checked the premises
against `src/search/`, `src/tune/params.hpp`, `src/uci/session.cpp`, `src/datagen/`,
`update.sh`, `tools/github/sprt_run.sh`, `tools/cloud/{sprt_merge.py,build_pair.sh,run_shard.sh}`,
`.github/workflows/{sprt,ci}.yml`, DESIGN.md (§5.2 constants rows on tier2/batch4, §6
decisions log) and the KB's competition.md. Most of the arithmetic holds. Seven findings change
recommendations:

1. **The resolution-aware soft stop (S1, A2 O1 part 2) rests on a premise the code refutes.**
   Fork checks the soft limit only after a *completed* iteration (searcher.cpp ~816), and an
   iteration completes only after its aspiration re-searches resolve. So no root fail high can
   be pending at a soft stop. Idea 29's 626/34,254 figure comes from *node-limited bench*
   searches cut mid-iteration. In timed play that only happens at the hard limit (4x soft). What
   remains of the idea is a best-move-stability term.
2. **I2 (the margin-multiplier ladder) cannot size the SPSA.** A global x0.8/x1.25 is a 1-D
   slice. It is null whenever the margins are mis-shaped in different directions, which is
   exactly the case S3/I3 argue for. Its 2-stage resolution (±7 Elo) also covers both predicted
   outcomes. It may run as filler, but must not gate O1. The +15-35 survey figure is inflated.
   My range for O1 (8 margins, STC) is **+2 to +8, central about +4**.
3. **Fork cannot run SPSA today; verified, and the gap is a little larger than O4 says.** The
   shards build release binaries (build_pair.sh → update.sh, no FORK_TUNE), so the 37
   parameters are not even settable on GitHub. TEST_OPTS is one string per dispatch. run_shard
   runs one fastchess per shard. Budget **2-3 days** for O4, not 1-2. The same blocker hits
   I2's "no code" claim (it needs commits) and ST5's factorial (a tune build plus per-shard
   options).
4. **TT regime: systems (H) is more right than A3 about the runners, but its supporting
   evidence does not discriminate.**
   - Most shards ran on EPYC 7763 (gauntlet records in DL 2026-10-31 and 11-02: 9/12 and 5/12
     shards). Its L3 is 32 MB per CCD, shared with other tenants (from memory, UNVERIFIED).
     Three concurrent ~20 MB hot sets do not fit.
   - But H's "B0 ran 0.52x of local" check is confounded by 3 searches on 4 vCPUs, which are
     probably SMT siblings, and by in-game against bench nodes.
   - Only H2's runner A/B job (~15 min) settles it.
5. **The SPRT redesign is right, but the owner should take "R" before "R+cap".** I reproduced
   ST1's tables. Under R+cap a truly null feature is accepted **12.7%** of the time. Under a
   mature-engine prior for batch 4 (N(0, 4) nElo), 20% of acceptances are features worth
   under +0.9 Elo. Plain R (futility at stage 2, [0, 6], β 0.2, cap 8) already gives 80-90% of
   R+cap's Elo per stage, with false acceptance at 1.6%.
6. **ST5's factorial is valid as a main-effects screen.** It needs row-to-shard randomisation
   per stage (runner CPUs differ by shard), a FORK_TUNE build and a workflow change. Its
   combined guard ("4 stages, accept if > −3 nElo") passes a true −5 nElo removal set 32% of
   the time. Use [−6, 0] R-bounds for the guard instead.
7. **H2's "the 3% rule threw away +9-22 Elo" is overstated.** P-2 (+2.4%) and P-3 (+2.3%) were
   adopted anyway, for simplicity (A3 §1.3). And **H1's VNNI arm conflicts with a standing
   owner rule** (competition.md Q8: "no Fork design may depend on VNNI until TCEC answers").

The node-share term should move into Phase 4 (an owner decision). It is zero-nps, and
labels are provably untouched: datagen sets only `limits.nodes`, and `soft_ms = -1`. Its honest
value is **+3 to +8 STC, +4 to +10 LTC**. The argument that it "must precede SPSA" is weak. The
argument that it buys the best Elo per GitHub stage among search items is strong.

Labels: [V] verified in a primary file; [C] computed by me (scripts in
`tank/b/scratch-sk2/`: `oc.py`, `oc2.py`); [I] my inference; UNVERIFIED as usual.

---

## 1. Verdict table (every proposal in my files)

"Adj. LTC" is my adjusted head-to-head Elo at 40+0.4 for the proposal's own direct effect.
"enabler" means no Elo of its own. Ranges are placeholders, not measurements.

| ID | Verdict | Adj. LTC Elo | Main issue |
|---|---|---|---|
| **S1** node-share TM + resolution-aware stop | PLAUSIBLE (node share) / partly REFUTED (stop) | +4 to +10 (node share); stop part 0 to +1 | ρ_s² assumed; the "pending fail high at soft stop" cannot occur in Fork's loop [V] |
| S2 round-once fractional LMR, centred terms | PLAUSIBLE | refactor 0; unlocked terms +2 to +6 (shared with S5/idea 42) | the table stores whole plies (uint8), so it is not "already fixed point"; centring premise unmeasured |
| S3 concave RFP/futility from equal marginal error | WEAK-PLAUSIBLE | 0 to +3 | σ_d read from tail *averages* on the bootstrap eval; H_crit untested |
| S4 equal-marginal-error calibration of all selectivity | PLAUSIBLE (as measurement) | enabler (Elo arrives via O1/O10) | gives P(wrong), not the cost of a wrong prune L_d, so it fixes shape, not level |
| S5 batch-4 triage | PLAUSIBLE | +1 to +4 from survivors | the ρ-class screen rests on 4-5 points; useful as an order, weak as a filter |
| S6 node types for NMP/IIR; post-LMR re-search depth | PLAUSIBLE | +1 to +5 | needs batch 4's `expected_cut`; NMP-at-cut-nodes is the best-evidenced part |
| S7 concave SE margin, LTC-only extension tuning | WEAK-PLAUSIBLE | 0 to +3 (≤ 0 STC) | LTC-only is costly; deep precision measurement first |
| S8 history hygiene (per-search scaling; malus to SPSA) | PLAUSIBLE (diagnostic) | 0 to +2 | value hinges on M1's in-game distribution |
| S9 two-depth scaling classifier | PLAUSIBLE | enabler | bench Δ per ply is noisy at 46 positions |
| I1 decision ledger | PLAUSIBLE | enabler | same L_d limit as S4; 1/32 counterfactual sampling is sound |
| **I2** global margin multiplier ladder | WEAK (as an SPSA gate) | 0 | 1-D slice; ±7 Elo resolution covers both predictions; needs commits, not "no code" |
| I3 σ_d-indexed concave margins | WEAK-PLAUSIBLE | 0 to +3 (same as S3) | the shape is a hypothesis; reparametrisation for SPSA is the real value |
| I4 tail-risk-classed margins | WEAK | 0 to +3 | "RFP costs 20-35 Elo of wrong prunes" is inferred from one SPRT sliver |
| I5 correction tables, passive ranking first | PLAUSIBLE | 0 to +3 at 1 thread | cheap and correct ordering; the count-based gain is untested |
| I6 margin credit for tail-reducing nets | WEAK | 0 to +2 | model-only; small next to speed terms |
| I7 improving as a measured mean shift | PLAUSIBLE | 0 to +3 | the LMP split is the best-evidenced use; overlaps A2 O5 and the surveys |
| I8 TT-eval refinement hygiene | PLAUSIBLE | 0 to +2 | fits the queue's B-4 slot |
| I9 aspiration in calibrated units | PLAUSIBLE | 0 to +1 | cheap bench measurement |
| **O1** early SPSA of 8 margins | PLAUSIBLE | **+2 to +7** (STC +2 to +8) | T prior (6-15) is a judgement; driver missing; 12 synchronous updates |
| O2 SPSA rules | SOUND (math) | enabler | separable-quadratic model; cross terms untested |
| O3 c from firing rates | PLAUSIBLE | 0 to +2 (via O1) | a mechanism proxy for Elo curvature, unvalidated |
| O4 GitHub SPSA driver | SOUND (need) | enabler | 2-3 days, not 1-2 (see §2.O4) |
| O5 tune by scaling class | SOUND (rule) | 0 to +3 protective | consistent with TCEC survey §2.B evidence |
| O6 validation protocol | SOUND | protective | the 3-stage LTC sign guard passes a true −5 nElo tune 15% of the time; acceptable |
| O7 antithetic screen | WEAK (for selectivity features) | indirect | asymmetric harm of the negative dose makes "be more careful" features screen positive |
| O8 mini-SPSA replaces ladder | PLAUSIBLE | 0 to +2 | needs O4; ST6 gets most of the benefit now |
| O9 idea 23 with repaired fitness, capped | PLAUSIBLE (as a decision to shrink) | 0 to +2 | prior on hit rate is a guess; archiving is a fine outcome |
| O10 final retune rescoped | PLAUSIBLE | +1 to +5 | depends on adoptions in between |
| **ST1** budget-matched sequential design | SOUND (math, reproduced) | indirect +2 to +6 | R+cap's null-acceptance rate needs an explicit owner trade |
| ST2 EB reporting, block check | SOUND | 0 (protective) | prior mixes eras; fine for reporting |
| ST3 throttled 0.5x speed-to-Elo | SOUND, with one fix | indirect | throttle ratio must be measured on the runners (compute burn ≠ memory-bound slowdown) |
| ST4 node-odds network screens | PLAUSIBLE | 0 to +3 | fastchess per-engine `nodes=` via TEST_OPTS UNVERIFIED; no TM in the screen |
| **ST5** removal round as factorial | PLAUSIBLE | 0 to +2 + simplicity | needs randomised row-shard mapping, tune build, workflow change; guard too lax |
| ST6 head-to-head constant selection | SOUND | +0.5 to +1.5 | originality-rule wording is the owner's |
| ST7 stage throughput | PLAUSIBLE | indirect | per-stage rebuild in a fresh container verified [V]; utilisation is the bigger lever |
| ST8 budget by Elo per stage | SOUND (as scheduling) | 0 | inputs are priors |
| H1 TCEC build (v4, C1, PGO, compiler matrix) | PLAUSIBLE | 0 in tests; TCEC +3 to +10 | VNNI conflicts with an owner rule; launcher legality UNVERIFIED; Elo/1% at TCEC unknown |
| H2 measurement stack | SOUND (need) | enabler; +2 to +6 over the phase | "+9 to +22 thrown away" overstated (P-2/P-3 were adopted) |
| H3 zero-row calibration + throttle build | SOUND | enabler | linearity check built in |
| H4 shared link-pair enumeration | PLAUSIBLE | +1.5 to +4 | the "60% of pair-search instructions" share is an estimate |
| H5 fused last-ply update + output | PLAUSIBLE | +1 to +4 | port-balance gain optimistic; maintenance cost to report |
| H6 eager child update before TT read | WEAK-PLAUSIBLE | 0 to +3 (runners/TCEC only) | predicted negative locally; adopting on runner evidence is a doctrine change |
| H7 weights/histories on huge pages | PLAUSIBLE | 0 to +3 | premise on file-backed THP UNVERIFIED; cheap to falsify with dTLB counters |
| H8 threat side lane within 0.90x | WEAK-PLAUSIBLE | 0 to +10 | 10-15 days; FN gain of a narrow lane unknown (network skeptic's domain) |
| H9 Phase 6 guardrails | SOUND | 0 (protective) | rules only |
| W1 value-of-computation TM | PLAUSIBLE (a); WEAK at STC/LTC (b) | (a) same as S1, not additive; (b) 0 at LTC | (b)'s 0.14-0.22 e-fold TCEC loss assumes equal move importance |
| W6 sequential halving | PLAUSIBLE | indirect | needs a ready batch; ignores dependencies and stacking; ST1 simpler |
| TCEC-A Lazy SMP (Phase 6) | SOUND | 0 in Phase 4 | out of scope by design |
| TCEC-B scaling lane / VLTC checks | PLAUSIBLE | protective | one VLTC stage ≈ 3 LTC stages; budget 2-4 checks |
| TCEC-C Elo-per-doubling ladder | PLAUSIBLE | info | the largest N dominates cost; same family as ST3 |
| TCEC-D NUMA hygiene (Phase 6) | SOUND | 0 now | — |
| TCEC-E TT pressure, scaled hash | PLAUSIBLE | 0 to +3 at TCEC | the "entries per node" scaling is a good free test rule |
| TCEC-F long-TC TM | PLAUSIBLE | covered by S1/W1 | the TCEC-statistics data-policy question is real |
| TCEC-G Syzygy 7-man safety | SOUND | few Elo; safety | — |
| TCEC-H deep-search sanitizer audit | SOUND | safety | cheap |
| SF-survey 7.1.a-f, 7.2.1/4-10 (search, TM, testing) | mostly PLAUSIBLE | see overlaps | Fork EST ranges (+8-20 TM, +4-10 node-type LMR) inflated by SPRT-selected sources |
| OS-survey 4.1 SPSA (+15-35) | WEAK as a magnitude | see O1 | other engines' LTC tunes of ~30 parameters, SPRT-selected PR numbers |
| OS-survey 4.2 TM (+10-20 LTC) | PLAUSIBLE, inflated | +4 to +10 | Halogen +13.4 LTC is the top of a two-engine sample |
| OS-survey 4.3 history mechanics | PLAUSIBLE | +1 to +5 combined | the linear bonus changes every history scale; do it before or inside SPSA |
| OS-survey 4.5-4.7 improving, node types, LMR breadth, fail-medium, QS futility | PLAUSIBLE | +1 to +3 each | overlap with S6, I7, A2 O5 |
| OS-survey §6 fractional depth ≈ 0 | SOUND for level 2 | — | does not contradict round-once arithmetic (§3.6) |

---

## 2. Per-proposal notes (only where substantive)

### S1. Node-share TM and the resolution-aware stop

- **Arithmetic [C].** M5's gain, Σ c_i ln(c_i/c̄) ≈ σ²_log/2, is right. The overshoot noise
  cost is ln((g−1)/ln g) − (ln g)/2 = 0.2641 − 0.2534 = 0.0107 e-folds at g = 1.66, so
  152 × 0.0107 = 1.6 Elo. That is right too. The whole Elo claim hinges on ρ_s²·CV² = 0.10-0.15,
  which is assumed. S1's own first experiment measures it, and that is the right order.
- **Premise refuted for the stop half [V].** In `deliberate()` the aspiration loop runs inside
  the iteration until `score` lies inside the window (searcher.cpp ~760-770). The soft check
  (line 816) and the iteration rule (line 828) run only after the iteration's bookkeeping.
  `root_fail_high_` matters only when `stopped_` is set mid-iteration, by the hard limit or a
  node limit.
  - So, contrary to A2 §4 ("the iteration rule ... can stop with a fresh fail high pending")
    and S1's "+1 to +3", **a timed Fork search never stops at the soft limit with a root fail
    high pending.**
  - The 1.8% in ideas.md 29 is "node-limited searches over the bench". That is the analogue of
    a hard stop. In time mode the hard limit is 4x soft and binds rarely, except at a low clock.
  - What survives is "extend when the best move changed in the last iteration", i.e. a
    stability term. Score it as part of the node-share package, not as an extra +1 to +3.
- **Elo.** The priors are other engines adding node share to a TM with no dynamic term:
  Halogen +7.9 STC / +13.4 LTC, Viridithas +5.6 / +4.2 (OS-survey §4.2). SF's +1.6 / +1.2 is
  for a mature TM. All are SPRT-selected PR figures. Shrink them: **+3 to +8 STC, +4 to +10
  LTC.**
  - The iteration granularity limits reallocation. The soft limit can be scaled, but the stop
    still lands only at iteration ends (g = 1.66). A share-scaled soft limit of 0.6x moves the
    realised spend less than 0.6x on average. This trims the gain slightly [I].
- **Labels untouched [V].** `SelfPlay` sets only `limits.nodes` (self_play.cpp ~105-110), so
  `soft_ms = -1` and every TM branch is skipped (searcher.cpp 816-828). The implementation must
  keep the share term inside the `soft_ms >= 0` guard.
  - The root shares also feed idea 23's LMR context (`branch_share_`, line 624). The TM term
    must read them, not change how they are computed.
- **Sharper prediction.** Fit P(best move changes within 2 iterations | share) on Fork's logs
  (S1's experiment). Predict the STC SPRT's Elo from M5's table *before* the run. Kill the
  method, not just the term, if the measured Elo is outside 0.5-2x the prediction.

### S2. Round-once fractional LMR

- **Premise check [V].** lmr_table.hpp computes fixed-point logs, but stores
  `std::uint8_t plies[64][64]`, rounded at construction. "The table already works in fixed
  point" is half true.
  - Round-once needs a 1/64-ply table, plus a proof of bench identity with every term at 0:
    rounding the fixed-point value must reproduce the stored rounding exactly, including the 18
    entries that sit one ply low.
  - The check relief is subtracted after the table (`base + correction − relief`, line 457), so
    it can move into the same fixed-point sum unchanged.
- **The centring argument is sound and is the real content.** `moves_searched + 1 >=
  LmrMinMove` counts *all* moves, including the TT move and captures (line 430). So the first
  late quiets can include high-history moves. The bias is weaker than "by construction", but
  the direction holds.
  - The malus hits every earlier quiet at every cutoff (quiet_history.hpp header [V]). So the
    unconditional mean of entries is negative as well.
- **Elo.** Round-once alone has no value. A centred history term plus fractional cut-node LMR
  are the payload. My range is +2 to +6, shared with S5's cut-node item and idea 42 (not
  additive with them).

### S3 / I3 / S4 / I1. Margin shape and the ledger

- **Arithmetic [C].** z = Φ⁻¹(0.0031) = −2.74 and Φ⁻¹(0.0003) = −3.43 are right, so
  σ_d ∝ d^0.87 follows. But audit-1's 0.31% / 0.03% are the share of *all pruned nodes*
  (g ≥ M·d) that fail low: tail averages, not tail probabilities at the threshold. A Gaussian
  read of averages understates σ at every depth, and by different amounts at each depth.
  S3's "20 + 61·d" is not usable even as a placeholder before the re-measurement. S3 says so;
  I agree.
- **The decisive limit.** Both the ledger and S4 measure P(wrong | g, d). The optimal margin
  needs q_d = λC_d/L_d, and L_d (Elo cost per wrong prune at depth d) is unobservable from the
  ledger. Shape follows only under H_crit (C ∝ L). So these tools set **SPSA's parametrisation,
  starting points and ranges**. The level must come from games (O1/O10). That is the right
  use, and enough to justify about 2 days.
- **I1 counterfactual design [I].** Deterministic 1/32 skip by Zobrist key with ×32 weights is
  a valid Horvitz-Thompson estimator. The perturbed tree differs from the real one by about 3%
  of prunes. That is fine.

### I2. Global margin multiplier: why it cannot gate O1

- §0.4's "loosenings sit at 1.1-1.4k" rests on one clean point, rising RFP:
  ρ = 214, with a 95% interval of about 166-262 from its ±2.92 Elo. qs-delta's ρ = 164 has an
  interval of about 75-253, consistent with ρ < k. So "the margins sit just past break-even"
  is a one-test inference, about depth 1-2 of RFP only.
- Rising RFP also compared raw evals while RFP prunes on prune_eval (A2 §2.2), which muddies
  even that point.
- A global ×0.8 moves RFP, futility and NMP together. If RFP is slightly too loose at d = 1 and
  futility too tight at d = 4, the slice is flat. Null I2 ⇏ SPSA ≤ +5.
- 2 stages per value (SE ≈ 3.7 Elo) cannot separate the predicted "−2 to −6" from "−3 to +3".
- Release builds compile the defaults in (params.hpp header [V]), so each multiplier is a
  commit with a new bench, not "params only".
- **Verdict: run it only as idle filler. O1 does not wait for it.**

### O1, O2, O4. Early SPSA

- **Magnitude ruling: see §3.1.**
- **Driver gap [V].** build_pair.sh builds via update.sh with no FORK_TUNE, so the 37 params
  exist only as constexpr on the shards. `session.cpp` declares them as spin options only under
  `#ifdef FORK_TUNE`. The workflow passes one `test_opts`/`base_opts` string per dispatch, and
  run_shard.sh runs a single fastchess with `-each`. O4 must add:
  - a build input for FORK_TUNE;
  - micro-match looping in the shard;
  - per-pair θ± option strings;
  - a gradient merge;
  - a tune-run title format that jobctl and the ledger attribute (sprt_run.sh's
    title-matching rules);
  - tests in the style of test_sprt_run.sh.
  
  **2-3 days** is the realistic figure.
- **Synchronous batch [I].** One update per stage means 20k games = 12.5 updates. Each update
  averages about 100-200 random Δ (one per micro-match). That is a large-batch gradient step,
  so the 0.5c clamp caps total travel at about 6c. If a margin's optimum lies more than about
  4c away (a step of 6 cp for RfpMargin), 20k games will not reach it. Tuning's simulation
  claims batch insensitivity, but under its own separable model with optima near the start.
  Prediction to add: report whether any parameter hit the clamp in ≥ 8 of 12 updates. If so,
  the run was step-limited, not noise-limited.
- **The cost of a null tune is right:** about 2.5 Elo at T = 0 [sim, O]. O6's validation SPRT
  is mandatory.

### O7. Antithetic screen

- The 4x signal assumes a symmetric response. For selectivity features the negative dose (reduce
  more, prune earlier) is often far more harmful than the positive dose is helpful. Fork's own
  record is that loosening loses.
- So an antithetic screen of "reduce less" will usually show D > 0 even when "reduce less" is
  worth 0. The screen fails exactly at its kill function for half of batch 4.
- Keep it for symmetric strengths only: history weights, a TM slope, correction weights.

### ST1. The SPRT redesign (reproduced)

- My simulation (`oc.py`, 20,000 trials per point) reproduces ST1's table to ±0.005:
  P(accept | 0) = 0.001 / 0.016 / 0.127 for current / R / R+cap, and P(accept | +5) = 0.206 /
  0.262 / 0.636.
- **The prior.** ebfit.py fits a hierarchical normal to 15 logged tests. The stopping-rule
  ignorability argument is correct: the likelihood of θ given (θ̂, n) does not depend on the
  stopping rule.
  - Two cautions. Dropping "the three classics" is an outcome-based choice. And batch 4's
    items are the kind that gain +1 to +3 Elo in mature engines (SF-survey §4; OS-survey
    §4.7), i.e. N(0-1, 4-5) nElo, tighter than N(0, 10).
  - I re-ran under N(1, 5) and N(0, 4) [C, `oc2.py`]:

| prior | design | gain/test (nElo) | stages/test | gain/stage | P(accept) | accepted with true < +1.5 nElo (≈ +0.9 Elo) |
|---|---|---|---|---|---|---|
| N(1, 5) | current | 1.14 | 11.8 | 0.097 | 0.14 | 0.6% |
| | R | 1.12 | 4.5 | 0.250 | 0.15 | 3.3% |
| | R+cap (> +3) | 1.76 | 4.5 | 0.394 | 0.32 | 11.6% |
| | R+cap (> +5) | 1.50 | 4.5 | 0.335 | 0.23 | 6.2% |
| N(0, 4) | current | 0.43 | 12.2 | 0.036 | 0.07 | 1.8% |
| | R | 0.49 | 4.3 | 0.113 | 0.09 | 6.8% |
| | R+cap (> +3) | 0.93 | 4.3 | 0.215 | 0.23 | 20.3% |

- **Reading.** R alone is 2.6-3x the current design's Elo per stage under every prior, with
  almost no extra false acceptances. R+cap adds another 40-90% per stage, but under tight
  priors a fifth of its acceptances are near-null code.
- **Recommended design:** R (futility at stage 2, [0, 6] nElo, α 0.05, β 0.20, cap 8) as the
  standard for features. Take R+cap at a **+5 nElo** cap threshold if the owner wants more
  acceptances (6% near-null). Use the same R for the LTC list, with a cap of 4-6 LTC stages.
- **What the owner accepts with R:**
  - about 2% of truly null features adopted, plus the loss of roughly a third of +3 nElo
    features (futility stop, early H0);
  - in exchange, about 60% fewer stages per test.
- **With R+cap (> +3):** null features are adopted 12.7% of the time and −2 nElo features
  4.1%. Over 20 tests, expect about 2-3 near-null adoptions and about −0.3 nElo of accepted
  harm. In return, a few extra real gainers get through.
- Either way the "4-5 tries per idea" rule (fishtest) must be adopted. Each retry spends α
  again.

### ST3. Throttled speed-to-Elo measurement

- **Arithmetic [C].** At a −106 Elo deficit, pair-score mean ≈ 0.35 gives dElo/dm =
  400/(ln10 · 0.35 · 0.65) = 764. With pair sd 0.24 and 1,600 pairs: SE = 0.24/40 × 764 =
  4.6 Elo, so R ± 9 (95%). Planned 0.85x at 4,000 games: 3.26 Elo / 0.2345 = SE 13.9, ±27.
  Both are right.
- **One flaw, shared with A3 §1.5 and H3.** A throttle that burns ALU cycles behind a compiler
  barrier slows a compute-bound node by the designed ratio. A node whose time is partly DRAM
  stall slows by less. If the shards are as memory-bound as H argues, a 0.50x local throttle
  may play at about 0.55-0.60x on a 7763 runner [I]. That would bias R *low* by 10-25%.
- **Fix (cheap):** each shard benches base and test (the same `fork bench`, under the shard's
  concurrency) before its games. It records the per-CPU-model ratio in result.json meta, and R
  is fitted on the realised ratio. gauntlet.yml already logs `lscpu` [V]; run_shard can do the
  same.
- **Ruling against the planned 0.85x time odds.** Throttle 0.5x, 2 STC stages and 1 LTC stage,
  plus in-situ ratios. An optional 0.85x *throttle* point (not time odds), 2-3 stages, checks
  log-linearity where the gate decides (SF-survey 7.2.4's concern). Time odds carry the
  per-move latency skew (synthesis §1.1g).

### ST5. Removal round as a factorial

- **Arithmetic [C].** The 91 stages per neutral feature for α = β = 0.05 at 3 nElo are right
  ((3.29 × 245.67/3)² = 72,600 pairs). The planned round cannot certify anything.
- **Validity.**
  - (a) *Main-effects model.* Two-factor interactions alias into main effects in a 16-row
    design. ST5's redundant-pair argument (bias toward keep) is right. Likely redundant pairs in
    its list: LMP with the futile-node filter (both cut low-depth quiets); TT-refine with RFP
    and futility, through prune_eval; SEE-in-QS with nothing else in the list.
  - (b) *Tier-2 dependencies.* Multi-cut lives inside the singular test, and check relief and
    lmr-in-check live inside LMR [V: searcher.cpp 430-457]. ST5 rightly keeps SE, MC and LMR
    out of the screen. Any switch whose parent is also in a row must not be in the design, or
    a row "parent off, child off" double-counts. Rule: a switch and its parent are never both
    factors.
  - (c) *Runner heterogeneity.* Each shard lands on a different CPU model (DL: 7763, 9V74,
    9V45, Xeon). Speed-type switches (the futile-node filter was +12.7% nps) have CPU-dependent
    value. Fix the row-to-shard map and the confounding never averages out. **Randomise the
    map per stage** (seeded, logged).
  - (d) *The guard.* "4 fixed stages, accept the set if the estimate > −3 nElo" has SE 4.34
    nElo. A true −5 nElo set passes 32%, a −3 set 50% [C]. Use R-type bounds [−6, 0], β 0.2,
    cap 8 for the guard.
  - (e) *Tooling.* sprt.yml's matrix passes one TEST_OPTS to every shard [V], and switches
    exist as options only in FORK_TUNE builds. Both need workflow changes (owner).
- **Decision rule.** "Remove if posterior mean ≤ +1 nElo" removes a true +3 nElo feature 23%
  of the time. That is the price of a decision for every switch. The owner should see it.
- Verdict PLAUSIBLE. It is the only design that can decide anything within budget.

### H1. TCEC build

- **Verified [V].**
  - update.sh: CXX first of clang++-19, clang++-16, clang++, g++-12, g++; FORK_ARCH default
    x86-64-v3; no PGO.
  - The output layer `squared_sum` has an AVX2 path and a scalar path only (accumulator.cpp
    ~175-196). The update has an AVX512BW path.
  - Datagen's PGO build defaults to `ARCH native` (cmake/pgo.cmake line 8). So C1 would speed
    data generation today, and **that part needs no TCEC decision**.
- **Rules.**
  - TCEC: "builds for AVX-512 / AVX2 / SSE4.2 preferred; authors may supply an update.sh that
    clones and compiles"; Category 4 is built by TCEC from the repo (competition.md, "Builds
    and submission").
  - Nothing found forbids building two binaries. Whether TCEC's harness accepts a *shell
    launcher* as the engine path is UNVERIFIED. Ask on Discord, or prefer H1's alternative:
    a startup CPU check that fails at `uci`.
  - simd.md bans runtime dispatch only "in hot paths", so a launcher or startup check complies.
- **Conflict.** competition.md open question 8: "no Fork design may depend on VNNI until TCEC
  answers" (owner, 2026-10-28). Ship a v4 (AVX-512BW, no VNNI) C1 path first. VNNI is an
  owner decision.
- **Elo.** The +4-18% nps estimate is reasoned, mostly from memory of Zen 4 resources. The
  value of 1% at TCEC is unknown; systems' own discount is 0.5-1.0. Adjusted: TCEC +3 to +10.
  The local A/B costs one quiet hour and settles the nps part.

### H2. Measurement stack

- The cycles:u rule is a good idea. Fishtest's speedup page recommends perf counts
  (SF-survey §6).
- But the "+9 to +22 Elo now invisible" figure counts P-2 and P-3, which audit-1 adopted
  (A3 §1.3). It also counts E2, which C4 had already absorbed. Realistic: +2 to +6 over the
  rest of the phase.

### H6. Eager update before the TT read

- The local prediction (−1 to −2%) matches C3's −0.8%. Adoption would need the owner to accept
  "keep a change that is slower on the development machine".
- Do H2's runner A/B and its large-Hash profile first. If 4 GB THP costs under 3% against
  16 MB locally, drop H6 until Phase 6.

### W1(b). The TCEC-shaped horizon

- The 0.14-0.22 e-fold "excess loss at 30'+3"" assumes equal importance per move under log
  utility.
- TCEC's own data cut against using it as a target: front-loaders (SF, Reckless) and keepers
  (Integral) finished 1st, 3rd and 5th (TCEC survey §1.1). In TCEC's biased openings, the
  early middlegame is plausibly where games are won.
- (b) belongs in Phase 5 at a ratio-600 control. It is not a Phase 4 item.

### W6. Sequential halving

- The simulation is plausible (it matches A3's efficiency class).
- But it needs ≥ 6 arms ready at once. Batch 4's items have dependencies: cut-node after S2,
  history skip after M1/S8, double extension at LTC. Arms are tested against a base without
  the others, so two winners need a joint confirmation.
- ST1 adopts as items become ready and stacks correctly. Prefer ST1; use W6 only if a genuine
  batch of independent arms exists.

---

## 3. Contradiction rulings

### 3.1 Early SPSA magnitude: +15-35 (OS survey) vs +4-12 STC (O1) vs ≤ +5 (I2)

- **The +15-35 is inflated.**
  - It is the mean of four LTC tunes in two engines (Halogen #484 +18.6, #656 +20.0; #738
    +10.2; Viridithas #220 +11.6). Each tuned the whole parameter set, LMR and history
    included, and each figure is a published, SPRT-confirmed tune.
  - The survey then *raised* it for Fork ("never tuned at all"). But part of Fork's set *was*
    measured on networks: SE on S-512, the history weights by cutoff index (3 of 3 predicted),
    and IIR's depth.
  - The survey's supporting argument ("four H0s are improbable on a tuned base") does not
    follow either. Each of the four failures has a feature-specific mechanism (A2 §2.2), and
    H0 is the modal outcome for ordinary features in mature engines.
- **O1's +4-12 STC (central +7) is the better-built number, but its T prior (6-15 Elo of
  misplacement in 8 parameters) is a judgement.**
  - Its main anchor, RfpMargin 40 at −44 ± 22 in a bootstrap-era gauntlet, says the RFP
    landscape is *steep near 80*. That supports small c, not large misplacement.
- **I2's ≤ +5 rests on one SPRT (§2.I2) and covers only depth 1-2 RFP.**
- **Ruling: O1 (8 margins, STC 20k games) +2 to +8 STC, central about +4; LTC +2 to +7.** The
  full program (O1 + O10 + LTC class b) is +5 to +12 at LTC in total.
- **I2 should not precede O1** (§2.I2). It may run as filler while O4 is built. Its only
  decisive outcome is ×0.8 ≥ +8, which would raise O1's priority.
- **O4 verified:** Fork cannot run SPSA today (§2.O4). The cost is 2-3 days.

### 3.2 TT and caches: L3-resident (A3) vs DRAM-bound (systems)

- **What the files say [V].**
  - Shards build g++ 11.4 x86-64-v3 in an ubuntu:22.04 container (sprt.yml build job), so
    there is no AVX-512 on any shard.
  - Hash 16 MB at STC, 64 MB at LTC. Concurrency nproc−1 = 3 on 4-vCPU runners
    (run_shard.sh line 38).
  - Runner CPUs from the two gauntlets (DL 2026-10-31 and 11-02): EPYC 7763 (9 and 5 of 12
    shards), EPYC 9V74, EPYC 9V45, Xeon Platinum 8573C, Xeon 6973P-C.
- **Cache sizes, from memory (UNVERIFIED).**
  - 7763 (Zen 3): 512 KB L2, 32 MB L3 per 8-core CCD.
  - 9V74 / 9V45 (Zen 4 / Zen 5 Azure parts): 1 MB L2, 32 MB L3 per CCD.
  - The Xeons: 2 MB L2 and a large shared L3, shared with every tenant on the socket.
  - The KB records no runner cache data (phase4-pipeline.md lists "runner CPU model" among the
    UNVERIFIED items).
- **Footprint [I].**
  - Six engine processes are alive per runner. Three search at a time, each with a 16 MB TT,
    2.4 MB of pair histories and a 1.4 MB first layer. The waiting engine's lines are evicted
    by the others.
  - About 60 MB of hot data competes for at most 32 MB of L3 on the Zen parts, less what
    neighbours use. So most TT probes on a 7763 shard miss L3.
  - **A3's "16 MB Hash L3-resident on every runner" is very likely wrong for the majority
    (EPYC) shards.** It may roughly hold on the big-L3 Xeons.
- **But H's corroboration does not discriminate.**
  - B0 played at 0.52x of local bench nps. GitHub's public-repo runners are 4 vCPUs, very
    likely 2 cores with SMT (UNVERIFIED; TCEC survey §3.5 found no spec).
  - Three concurrent searches on 2 physical cores alone gives about 0.6-0.7x per engine.
    In-game against bench nodes and clock speed add more.
  - The memory share of the slowdown is unidentified.
- **Consequences.**
  - C2 and C3 (latency-hiding) were judged in the wrong regime for shards and TCEC. E1 (a
    compute and copy cost, refreshes at 2.5%) was not: it stays dead.
  - Nothing here biases SPRT *verdicts* between two engines on the same runner. It biases
    *speed claims* and the gate ratio, and through them the R fit.
- **Ruling: systems is directionally right, A3 overstated L3 residency; neither has a
  measurement.** One runner-A/B job (H2 item 3, ~15 min, with `lscpu` logged) on S512ppr2 vs
  S512r2-zero-links and C3 vs parent settles both. Do it before ST3's run, since R must be
  fitted on runner ratios.

### 3.3 Time management: S1 +8-12 STC, W1 +8-18 LTC, surveys +10-20, A2's 1.30x overshoot vs search's 1.6 Elo

- **The overshoot numbers do not conflict.**
  - (g−1)/ln g = 1.30 is the *mean* overspend.
  - 1.6 Elo is the *noise* cost of the spread around that mean (§2.S1 arithmetic) [C]. Both
    are right.
  - The mean overspend is a deterministic re-shaping: Fork effectively plans about 23 moves,
    not 30. Its cost is a time-curve question, Phase 5's ratio-600 work. Fixing granularity
    alone is worth about 1.6 Elo at STC, so it should not be a separate project.
- **Expected value of node share** (the only dynamic term with strong priors):
  - **STC +3 to +8; LTC +4 to +10** (Halogen grew 7.9 → 13.4, Viridithas fell 5.6 → 4.2; SF
    mature +1.6/+1.2).
  - **TCEC: plausibly larger.** At base/increment 600 more of the time is bankable, but this
    is unmeasurable in Fork's tests (UNVERIFIED).
  - W1(a) is the same term with fitted factors. It is not additive with S1. W1's
    logistic-AUC kill test is the best cheap falsifier: build only if AUC ≥ 0.70.
  - The survey "+10-20" figures are the top of the published range.
- **Is moving TM into Phase 4 justified?**
  - **Yes, for node share (plus best-move stability) only, as an owner plan change.**
  - Zero nps, about 2 days, about 6-12 STC + 2-4 LTC stages.
  - Labels provably untouched [V: self_play.cpp sets only `nodes`; `soft_ms = -1` gates every
    TM branch]. Note the other side: TM gains do *not* flow into labels, so the generational
    loop does not amplify them.
  - The "must precede SPSA" argument is weak. TM reallocates time across moves; it does not
    move the margins' optimum. The real ordering argument is that LTC confirmations and the
    final gauntlet should play with the TM TCEC will see.
  - Base allocation, the curve and anything tuned at ratio 600 stay in Phase 5.

### 3.4 SPRT redesign: ST1, A3 futility, W6, O7, O8, ST6

- **Simulation assumptions.** The normal-approximation GSPRT (same as sprt_merge.py),
  stage-end checks, independent stages, a constant pair variance (sd 0.21), and priors from the
  ebfit. All are reasonable. The prior is the weakest link (§2.ST1), and the ranking of designs
  is robust to it. I re-ran it under four priors.
- **Recommended package.**
  1. **ST1 design R** as standard (A3's futility stop is inside it). R+cap at a +5 nElo
     threshold is an owner option.
  2. **ST6 head-to-head selection** for ladder constants now. It is dispatch-only and halves
     the decision variance.
  3. **O8's mini-SPSA** replaces ladders for continuous constants once O4 exists.
  4. **O7** only for symmetric strengths.
  5. **W6** not as standard (§2.W6).
- **The risk trade the owner accepts:** §2.ST1, the bullets under "What the owner accepts".
  The key line: R costs about 2% null adoptions; R+cap (> +3) about 13%.

### 3.5 The removal round (ST5)

Valid as a main-effects screen with four fixes (§2.ST5):
- no parent-child pairs as factors;
- row-to-shard randomisation per stage;
- an R-bounds guard;
- the owner's explicit acceptance of the remove-a-+3-nElo-feature-23%-of-the-time rate.

The interaction biases go the safe way (redundant pairs bias toward "keep"), and the joint
guard catches synergy. Tier-2 dependencies are handled by triaging SE, MC and LMR out. 22-32
stages against about 260 is real. It changes the owner's checklist method (item 8), so it is
an owner decision.

### 3.6 Fractional depth: A2/S2 round-once vs survey ≈ 0 vs synthesis

There is no real contradiction:
- The survey's "≈ 0" is about level 2, fractional depth throughout the tree (Viridithas
  removal +0.26; PlentyChess −2.05 STC / +3.25 VLTC), plus one inconclusive fractional-LMR
  run.
- Round-once is arithmetic inside the reduction formula. Alone it is worth exactly 0 and is
  bench-identical by construction (with the caveat in §2.S2).

**Ruling: build level 1 when the first sub-ply term is tested** (centred history or fractional
cut-node). Do not let it gate SPSA. Drop the full idea-43 refactor from Phase 4 (LTC-only if
ever). The synthesis §3.2 position is right.

### 3.7 Batch-4 triage (S5) and the LMR history term's failure

- **The three explanations are not alternatives; they compose.**
  1. **Non-centred / asymmetric term (the mechanism of the loss).** order_score/24000
     truncates toward zero [V: synthesis §1c], so the term fires only beyond ±24,000. Late
     quiets have low scores (selection plus a negative-mean malus), so most firings *add* a
     ply. Bench −0.27% nodes = net more reduction, consistent with this.
  2. **Never-decayed histories (the amplifier).** Persistence raises how often entries reach
     the threshold in games. The gravity rule self-limits, but a move that keeps failing
     saturates near −HistoryMax in every table.
  3. **Integer division (why the instruments were blind).** It explains 0.27% of bench nodes
     and the fresh-state proxy. It is not itself a loss.
  4. *(Secondary)* recomputing `quiet_order_score` for every made quiet: at 1-2% nps
     (unmeasured) that is 1.5-3 Elo, which cannot explain −10.8 alone.
- **Sharp test (M1 + one A/B, about 2 h local).** Prediction: the share of in-game LMR sites
  with |score| ≥ 24,000 is ≥ 5x bench, and ≥ 85% of firings are on the "reduce more" side.
  Refuted if the share is within 2x of bench: then attribute the loss to speed and measure the
  branch's nps.
- **S5 triage.** Agree with the order and the demotions:
  - cut-node LMR first after S2;
  - upcoming repetition on non-regression bounds as a correctness change, after deciding idea
    31's pre-root convention;
  - structure history gated by the cutoff-index metric;
  - history skip after M1;
  - double extensions at LTC;
  - razoring (verified: +1.7% nodes at depth 10 at its placeholders, DESIGN batch-4 row) and
    bad-capture futility to filler;
  - the malus balance into O10's SPSA.
  
  The ρ-class screen is a prior, not a filter (4-5 calibration points, bench nodes with fresh
  state).

### 3.8 The TCEC build (H1)

- update.sh may clone and compile (TCEC rule). A runtime CPU check outside hot paths is
  compliant with simd.md.
- PGO in update.sh is allowed (it is just a build). It should fall back to the plain build on
  failure, and needs one TCEC-toolchain CI run (gcc 11.4 / clang 16, 19).
- VNNI is blocked by the owner's rule until TCEC answers. AVX-512BW C1 is not.
- The **final gauntlet should play the TCEC build** if it differs, or Fork's last pre-TCEC
  number describes a binary TCEC will not run.

### 3.9 Speed-to-Elo design (ST3 vs planned 0.85x time odds)

- ST3 wins on precision (±9 vs ±27 on R) and avoids the latency skew.
- Add the in-situ ratio (§2.ST3): without it the throttle can bias R low on memory-bound
  runners, by about as much as time odds bias it high.
- Add 1 LTC stage. An optional 0.85x throttle point checks linearity at the gate.

---

## 4. Overlap map (same idea, different agents; best version named)

| Idea | Versions | Best version |
|---|---|---|
| Node-share TM (+ stability) | A2 O1, S1, W1(a), OS-survey 4.2, SF-survey 7.1.a, TCEC-F.1, ST8(b) | **S1's "fit the curve on Fork's logs" + W1's AUC kill test**; drop the resolution-stop half (§2.S1) |
| TCEC-shaped TM control (ratio 600) | A2 O8.1, W1(b), TCEC §3.6, O5(c) | TCEC §3.6 / A2 O8.1, in Phase 5 |
| Early SPSA of margins | O1, OS-survey 4.1, ST8(a), synthesis rank 1, I2 (as a gate) | **O1 + O2 + O6**; I2 as filler only |
| Final retune by scaling class | O5, O10, SF-survey 7.2.6, S7(4), TCEC-B, I-critique 1 | **O5 + O10**, with TCEC-B's VLTC spot check on the output |
| Margin calibration measurement | A2 O4, S3, S4, I1, I3 | **I1 (ledger) with S4's LMR miss-rate row**; I3's K·σ̂_d as the SPSA parametrisation |
| Round-once LMR + centred terms | A2 O2, S2, SF-survey 7.1.d, synthesis §3.2, idea 42 | **S2** (with the uint8-table caveat) |
| History persistence | A2 O3, S8, M1, OS-survey 4.3 (linear bonus) | **M1 measurement first**, then S8(a) |
| Speed-to-Elo measurement | A3 §1.5, ST3, H3 throttle, M5, SF-survey 7.2.4, TCEC-C, M10 | **ST3 + H3 + in-situ ratios**; TCEC-C's ladder later |
| SPRT efficiency | A3 futility, ST1, W6, O7, O8, ST6 | **ST1 (R) + ST6 now, O8 after O4** |
| Removal round | A3 #1, ST5, SF-survey 7.2.5 (combined guard), S9 routing | **ST5 with the fixes in §2.ST5** |
| Node types | A2 O6, S6, OS-survey 4.5, batch 4 | batch 4 + **S6(a)** (NMP at cut nodes) |
| Improving flag | A2 O5, I7, SF-survey 7.1.c, OS-survey 4.5 | **I7's measured-shift form, LMP use first** |
| Correction tables | A2 O7, I5, SF-survey 7.1.e, OS-survey 4.4 | **I5's passive ranking first**, SPRTs at LTC after SPSA |
| TCEC build | A3 §1.7 items 1, 3, 4, H1, synthesis M2 | **H1 without VNNI** |
| Runner speed regime | A3 §1.7 item 2, H2 items 3 and 5, TCEC-E, synthesis M3 | **H2 item 3** (runner A/B) |
| Fused update and output | A3 §1.7 item 6, H5 | H5 |
| Block and anchor checks | ST2, SF-survey 7.2.7 | ST2's block check |
| Scaled hash for TT-policy tests | TCEC-E, SF-survey 7.2.9 | TCEC-E |

---

## 5. Recommended order in my domain (for the orchestrator)

1. **Free or local first:**
   - M1 + the LMR-history branch's nps;
   - H2's runner A/B job (also measures the gate ratio and C3);
   - S1's share-fit logging;
   - I1's RFP/futility rows;
   - H1's local build matrix (no VNNI), plus C1 for datagen.
2. **Owner decisions:** ST1-R (and ST6) as the testing standard; node-share TM into Phase 4;
   ST5 as the removal method; the PGO/v4 update.sh change.
3. **GitHub:**
   - ST3 (with in-situ ratios);
   - node-share TM (ladder of two slopes, R-SPRT, LTC);
   - O4 → O1 (+ O6 validation);
   - batch 4 under S5's order and ST1;
   - ST5;
   - O10.

---

## 6. What I could not verify

- Runner cache geometry and SMT topology (the L3/L2 sizes above are from memory). Whether
  4-vCPU public runners are 2 SMT cores. The share of shard slowdown that is memory stall.
- Whether TCEC's harness accepts a shell launcher as the engine command.
- VNNI on EPYC 9754 (owner rule: unverified until TCEC answers).
- The in-game history-magnitude distribution (M1), and the LMR-history branch's nps.
- ρ_s² for node share on Fork; every TM Elo figure above is a shrunk external prior.
- The T (recoverable Elo) of Fork's margins; every SPSA figure is model-conditional.
- That a local 0.50x throttle plays at 0.50x on runners (my "0.55-0.60x on a 7763" is an
  inference).
- The stage-wise paths of ProbCut and threat ordering (not logged), and hence ST1's full
  replay.
- fastchess per-engine `nodes=`/`tc=` via TEST_OPTS overriding `-each` (ST3/ST4).
- H1's nps figures (Zen 4 resources from memory), PGO's gain, and the Elo value of 1% nps at
  TCEC.
- Bench identity of a 1/64-ply LMR table against the current uint8 table: not built, only
  reasoned.
