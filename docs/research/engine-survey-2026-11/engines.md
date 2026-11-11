# Engine records (CCRL Blitz top 50, list of 2026-11-07)

Survey of 2026-11-10, condensed from six clean-room family reports (README,
Method).

**How to read these records.**
- Every record is **REFERENCE ONLY** for ideas. Every engine's code, nets
  and data are **OFF-LIMITS** for Fork.
- Elo figures are each engine's own, under its own conditions; "a / b" is
  STC / LTC.
- No search constant, margin, threshold or quantisation scale is recorded.
- Licences are as GitHub's or GitLab's licence detection, or the README,
  states them; licence texts were not read unless noted.
- Sources are listed per engine in short form; full URLs are in
  [sources.md](sources.md).
- "Prior" points to the think tank's survey that already covered an engine;
  where it did, only what is new is recorded here.

**Shorthand.**
- KB: king input buckets. OB: output buckets.
- ML: a multi-layer head after the accumulator.
- TI: threat inputs. PP: pawn-pair inputs.
- FN: fixed nodes.
- corrhist: correction history.
- TM: time management.

---

### 1. Stockfish 19 (#1, 3803; GPL-3.0, nets CC0). Prior: S1

New since S1: Stockfish commits from 2026-09-05 to 2026-11-10. Elo below is
derived from the commits' W/L/D totals and leans high.
- **Search:**
  - razoring only at expected all-nodes: +1.35 / +2.6;
  - a 6-ply continuation corrhist: +1.4 / +1.1;
  - the count of null-move fail-highs as an input: +1.3 / +1.3;
  - depth climbing back gradually after an aspiration fail-high: +1.0 /
    +1.2;
  - less time when behind on the clock: +1.1 / +1.1;
  - SMP null-move diversity on odd threads: SMP +0.8 / +0.9;
  - legal-only move generation with a reused threat bitboard: +0.9 and
    2.2% faster;
  - a cap on chains of negative LMR reductions (a safety fix);
  - longer TT keys (non-regression, about 32x fewer collisions).
- **Mate-seeking mode:** each patch SPRTed for non-regression against a
  control with the mode off. A useful testing pattern.
- **Simplifications** passing non-regression: the LMR divisor, singular
  depth, the quiet bonus, optimism, TT conditions and move-picker stages.
- **NNUE:**
  - SFNNv18: king buckets conditioned on the opponent's queen, 32 layer
    stacks, all feature-transformer rows int8 (+4.2 / +3.6);
  - SFNNv19: a block for "no rooks or queens" (+2.4 / +2.7);
  - SFNNv20: factorised and pruned layer-stack keys (+2.8 / +2.1);
  - int8 row pairing: +5 to +11% nps.
- **Training:**
  - predominantly Lc0 data rescored by a Leela net;
  - net weights also SPSA-tuned in games;
  - feature-transformer weight decay +4.0 / +5.3 (now Fork's idea 71);
  - a longer stage-2 fine-tune +0.6 / +1.8.
  - Open experiments, outcome UNVERIFIED: mixture-of-experts routing,
    tablebase draw targets, endgame fine-tunes, SWA.
- **AI use:** several merged patches say they were written with AI agents.
- **Sources:** official-stockfish/Stockfish commits (GitHub API); the
  nnue-pytorch architecture history; vondele/nettest PRs; the TCEC
  questionnaire of 2025-10-19.

### 2. Triumviratus 8.0 (#2, 3784; Francesco Torsello with Maurizio Platino; GPL-3.0 with a §7(b) term)

- **Lineage:**
  - from BBC (GPLv3);
  - Stockfish-derived NNUE inference and search up to 8.0;
  - 8.1 (2026-11-07) rewritten from a specification (precedents.md).
- **Search** (own SPRTs, 10+0.1 to 40+0.4):
  - restructuring onto SF 19's algorithmic base plus SPSA: +85.8;
  - small adopted items, about +2 to +6 each:
    - hash-move extension;
    - qsearch hash depth;
    - pins in SEE: +4.5;
    - per-material-band corrhist: +3.2;
    - TT-cutoff damping (Coda's idea): +2.2;
    - cycle filter;
    - a cap on extensions from negative reductions;
    - a "causal reduction" of quiets.
- **Time management:**
  - surprise rule: +6.2 at 40+0.4;
  - less time when behind: +5.2 at 6+0.06, about 0 at 30+0.3;
  - more time in defence: +7.3.
- **A speed-only fix** (buffered output, a high-resolution clock): +29.8
  at 5+0.05 with an identical tree.
- **NNUE:**
  - Stockfish's SFNNv16 shape plus its own passed-pawn block (+7.0 for the
    net);
  - 8.0's material-routed input "experts" (+27.3 for the release, about +15
    of it the net);
  - 8.1's learnable routing and a cached pawn-king subnetwork (+10.3 for
    the net alone).
- **Training:**
  - Stockfish's trainer;
  - about 700 GB of Leela and Stockfish binpacks relabelled by BT4;
  - a fixed WDL-leaning lambda after a plateau;
  - the final net averages its last epochs' weights.
- **Removed:**
  - a near-miss TT cutoff;
  - endgame null-move verification;
  - a mobility input block (−16% nps);
  - expert blending (−24).
- **AI use:**
  - AI research agents and parallel agents;
  - PRs flag AI-generated code;
  - novelty checked by reading nine engines' source.
- **Sources:** Tors3/Triumviratus README, NOVELTIES.md, the
  DEVELOPMENT_6.0-8.0 notes, NETWORKS.md, releases.

### 3. Torch v4 (#3, 3778; Chess.com, private)

- **Team:** Andrew Grant, Finn Eggers, Kim Kåhre, Jay Honnold, Michael
  Whiteley and Dietrich Kappe, with advisers.
- **What is public:**
  - claimed entirely original code;
  - "a heavily modified alpha-beta" with many principal variations per
    search;
  - "plenty of secret sauce";
  - a light net and a full net.
- **No** architecture or per-technique Elo is published. Its TCEC
  questionnaire is confidential.
- **Data:** some 2023 nets partly on Lc0 data. Adversarial games against
  Stockfish are reported second-hand (UNVERIFIED).
- **Tag:** OFF-LIMITS; no technique detail usable even as reference.
- **Sources:** Chess.com articles (2023); CPW Torch; TalkChess; chessdom;
  the TCEC wiki's Plentychess and Tarnished questionnaires (second-hand
  remarks).

### 4. Obsidian 16.0 (#4, 3774 as 8-CPU; #14 at 3746 single-CPU; GPL-3.0). Prior: S2

- **Release regressions:**
  - 16.0 over 15.0: +34.8 STC, +38.7 at 60+0.6;
  - 15.0 ("finally with layers"): +27.2 LTC.
- **Net:** trained on Lc0 data with bullet.
- **Releases:** none since 2025-05-21.
- **Commit titles after 16.0** (not in the rated version): continuation
  corrhist, complexity in LMR, qsearch LMP, TT-cutoff tweaks.
- **Sources:** gab8192/Obsidian README, releases, commit titles.

### 5. PlentyChess 8.0.0 (#5, 3773; GPL-3.0). Prior: S2

- **8.0:**
  - fractional depth in more heuristics;
  - corrhist shared between threads;
  - SMP tuning;
  - NUMA;
  - DFRC +49.5.
- **After 8.0** (not in the rated version):
  - L3 SPSA under SMP: +4.6 at 4T LTC, 1T inconclusive;
  - optimism: STC H0, merged on LTC +1.3;
  - LMR capture tweaks: +1 to +3.6;
  - "real" continuation corrhist: +0.9;
  - captures that failed ProbCut marked bad: +1.0.
- **Data:** 15 B+ own self-generated positions, standard and FRC, with
  self-distillation for part of the training.
- **Sources:** Yoshie2000/PlentyChess README, releases, PRs #458-#501.

### 6. Coda 0.9.4 (#6, 3769; Adam Twiss; Rust; GPL-3.0-or-later)

- **Search** (README list): the modern standard set, with these histories
  and corrections:
  - histories: threat-aware 4D main history, capture history,
    continuation history at four plies, pawn history;
  - corrhist: pawn, non-pawn, continuation and a "transition" table;
  - TT score damping at non-PV cutoffs;
  - TM by node fraction, stability and score trend (constants initially
    from MIT-era Viridithas, then SPSA-retuned).
- **Releases:**
  - 0.9.4 over 0.9.3: +38.3 / +36.5;
  - 0.9.5 over 0.9.4: +19.9 / +23.6 at 1 thread;
  - the memory-mapped Syzygy fix: +17.9.
- **NNUE:**
  - king buckets plus threat features;
  - a pairwise accumulator, a small dual-activation head, material OB;
  - 0.9.5 adds PP and a linear readout.
- **Training:**
  - mostly Lc0 data (BT4-relabelled pool, +15.0), CC0 Kaggle data and some
    own datagen;
  - a bullet fork;
  - an L1 activation penalty.
- **Removed:**
  - x-ray threats;
  - contempt;
  - Lazy SMP depth offsets;
  - Reckless-derived SIMD kernels and bucket layouts (licence remediation,
    about 3% nps).
- **AI use:** written entirely by Claude Code (precedents.md).
- **Sources:** adamtwiss/coda README, CLAUDE.md, NOTICES.md, the licence
  analyses, issues #5-#17; ob.atwiss.com tests 3007, 3274, 4419 and greens;
  TalkChess.

### 7. Reckless 0.9.0 (#7, 3765; AGPL-3.0 from 0.9.0). Prior: S2

- **Licence note:** AGPL, so its source is especially OFF-LIMITS (Coda's
  case).
- **After 0.9.0** (not in the rated version):
  - LMR by "laterality": +6.1 / +2.2;
  - LMR by best-move chain length: +2.0 / +1.8;
  - a narrower first aspiration window when stable: +4.6 / +2.1;
  - qsearch SEE margin from history: +4.5 / +3.6;
  - correction size in futility: +1.8 / +3.8;
  - an LMP guard for checks: +2.8 / **+9.5**;
  - pawn history: +4.4 / +2.1;
  - BCH-code Zobrist keys: +2.7 under hash pressure;
  - SMP SPSA: +10.0 at 8T but −6.5 at 1T;
  - recapture extension removed (non-regression).
- **Data after 0.5:** not stated (UNVERIFIED).
- **Sources:** codedeliveryservice/Reckless README, releases, 88 PR
  descriptions.

### 8. Gaia 4.4.1 (#8, 3762; Jean-François Romang, David Rabel; Rust; GPL-3.0-or-later)

- **Licence note:** 4.2.1 carried a restrictive notice; it is
  GPL-3.0-or-later now.
- **Search:**
  - the standard set, with a history set like Coda's;
  - joint SPSA of all search parameters over 432,000 games;
  - a NUMA policy: +16 to +92% nps on dual sockets;
  - embedded 3-4-piece DTM tables.
- **NNUE** (model card): king buckets plus PP and filtered threat blocks,
  a pairwise accumulator, a small head, material OB plus a PSQT head. T7 is
  fully integer with sparse and gated layers.
- **Training:** in-house bullet trainers; fine-tunes at stepped result
  weights; random skipping; partly self-generated (full source UNVERIFIED).
- **AI use:** no statement found.
- **Sources:** jromang/gaiachess README and releases; the Hugging Face
  model card.

### 9. Cinder 0.6.1 (#9, 3760; Bruno Dutra; Rust; GPL-3.0)

- **Search** (mostly at 1+0.01):
  - threats in history: +10.2;
  - SEE pruning split quiet and noisy: +6.1;
  - LMR by continuation history: +5.0;
  - NMP at cut nodes only: +5.0;
  - singular extension when the TT score is below beta: +8.8;
  - singular factorizers: +8.0;
  - a capped moves-left prediction in TM: +7.5;
  - a limited history bonus: +5.6;
  - counter, follow-up and threat continuation corrections: +3.0, +4.7,
    +2.2;
  - fractional depth: +4.0;
  - SPSA: +4.9, +5.8 at 20+0.2.
- **Releases:** 0.5.0 +113.7 LTC; 0.6.x +55.0 LTC.
- **NNUE:**
  - mirrored king buckets, a wide pairwise layer, a 3-layer stack with a
    residual, OB;
  - TI and pawn-pawn inputs in 0.6;
  - the eval kept in f32: +8.3;
  - a per-bucket accumulator cache: +9.9.
- **Training:**
  - bullet on Leela data;
  - recipe PRs without numbers: scores only, an asymmetric penalty, L1
    sparsity, probabilistic ply filtering, a longer fine-tune.
- **Removed:**
  - blind NMP;
  - blanket check extensions;
  - PGO (+4.7 to remove);
  - TT depth-deficit pruning.
- **Sources:** brunocodutra/cinder README, releases, merged PR descriptions.

### 10. Berserk 20250606 (#10, 3759 as 8-CPU; GPL-3.0). Prior: S2

- **Rated version:** "20250606" appears to be main after #583 (an inference
  from the date, UNVERIFIED). The single-CPU best is Berserk 14 (#17, 3737).
- **Up to the rated version:**
  - #583, SPSA of the net's final layer: +17.2 LTC;
  - #582, search SPSA: +10.0 LTC;
  - corrhist items: depth-weighted +3.2, continuation +5.5, gravity +3.4;
  - TT replacement preferring recent entries: +5.8 LTC;
  - malus decayed by moves searched: +2.0 LTC.
- **After it** (2026-10 and 11, not rated):
  - a new architecture (king buckets, TI, pairwise, an ML head): +3.3, then
    +4.0 and +7.2 with more data;
  - non-pawn corrhist: +3.6;
  - PP: +1.9;
  - shared corrhist: +4.2 at 8T;
  - **a short result-only training stage: +11.7 LTC**.
- **Data:** own FenGen data mixed with Koivisto data; the 2026 source
  unstated.
- **AI use:** #594 and #597 are openly AI-assisted.
- **Sources:** jhonnold/berserk releases, PRs #561-#611, licence API.

### 11. Dragon by Komodo 3.3 (#11, 3756; commercial, private repository)

- **Search:**
  - Komodo's search plus an optional MCTS mode;
  - implementation details are trade secrets;
  - releases: Komodo 14.1 TM and LMR changes +10;
  - Dragon 3 +107 (1 thread), 3.3 +8 (+12 to +15 on UHO).
- **NNUE:**
  - not Stockfish code; Pervov's inference, Kappe's training;
  - 3.3's net about 50% larger than 3.2's;
  - eval scaled so +1.00 marks the win-draw edge.
- **Data:** Komodo games and Komodo evals, then reinforcement learning;
  some games against other programs (Komodo's moves only).
- **Sources:** CPW Komodo and Dragon; TalkChess; archived komodochess.com
  pages; the TCEC questionnaire of 2025-11-08.

### 12-13. Alexandria 8.0.0 (#12-13, 3755 as 8-CPU; GPL-3.0). Prior: S2

- **Rated version:** the single-CPU best is 9.1.0 (3751).
- **8.0.0:**
  - single layer with king buckets and mirroring, OB;
  - Finny tables;
  - ProbCut;
  - singular extension hand-tuned for long TC;
  - +14.9 LTC balanced.
- **9.x:**
  - "GHI prevention";
  - material-based eval scaling;
  - 2-step training, a WDL loss term, piece-count filtering;
  - pawn history, 6-ply continuation history, score-stability TM (9.1
    +18.3 LTC).
- **After 9.1:**
  - TI: +13.4 LTC;
  - TI plus PP: +13.5 LTC;
  - king buckets doubled: +10.6 LTC.
- **Data:** Lc0 (T79, BT4); more BT4 data gave +25.0 LTC.
- **Sources:** PGG106/Alexandria README, releases, PRs #627-#640.

### 12-13. pawnocchio 2.0 (#12-13, 3755; Jonathan Hallstrom; Zig; GPL-3.0, nets CC-BY-SA-4.0)

- **Search** (STC 10+0.1, LTC 40+0.4):
  - corrhist shared per NUMA node: +9.7 at 8T;
  - **pawn history shared between threads: +4.9 LTC 4T, +7.5 at 32T**;
  - ProbCut: +8.7 LTC;
  - fail-firm: +5.3, +2.9 LTC;
  - LMP relief for checks: **+9.0 LTC**;
  - no qsearch futility for checks: +5.5;
  - deeper re-searches: +4.6 LTC;
  - direct-check ordering: +6.4;
  - optimism: +5.2;
  - upcoming repetition: +3.8 LTC;
  - SPSA at 4T: +4.6.
- **NNUE:**
  - a multi-layer net with mirrored king buckets: +10.0;
  - dual activation: +6.3 LTC;
  - sparse matmul;
  - **TI plus PP: +26.7 / +30.3** (PP is its own innovation, credited by
    Stormphrax, Integral, Berserk and Hobbes);
  - a larger first layer merged despite STC and LTC H0 (no reason
    published).
- **Training:**
  - bullet; own self-play from zero, plus Vine games from v1.9;
  - relabelled by a much larger own net (+4.7, +11.0, +4.0 LTC; static or
    searched UNVERIFIED);
  - a fine-tune on new data: **+13.6 LTC, +19.3 LTC 4T**;
  - a pure-result retrain: STC H0, +4.2 LTC.
- **Sources:** JonathanHallstrom/pawnocchio README, releases, PRs #1-#71;
  pawnocchio-nets.

### 14. Integral 8 (#14, 3751; GitHub aronpetko; no licence detected: all rights reserved)

- **Search:**
  - TM "taken from Berserk/SF": +16.7;
  - cuckoo repetition: +7.3;
  - TT quality and replacement: +14.0, +7.1 LTC;
  - interpolated fail-firm: +2.0 LTC;
  - draw-score corrhist on repetition (Hobbes's idea): +3.4 LTC;
  - shared corrhist: +6.9 at 4T;
  - NUMA pinning: about +25 on many cores;
  - singular margin from TT-move history: +4.0 LTC;
  - quiet moves in qsearch after a quiet TT move: +11.6 LTC (called
    "largely inflated" by its author);
  - LTC SPSA passes of +2.5 to +11.3.
- **NNUE:**
  - TI: +24.4 LTC;
  - PP: +7.2 LTC;
  - **fifty-move inputs: +3.7 LTC and +3.7 on a fortress book**;
  - L1 regularisation of the feature-transformer output: +5.2 LTC;
  - merged accumulators (about 6% faster);
  - Ranger: +3.2;
  - a multi-layer head: +29.5 LTC.
- **Data:**
  - own self-play, Syzygy-guided, datasets public;
  - Vine and extra data added after v8 (+14.9 LTC); the rated net probably
    predates them (UNVERIFIED).
- **Sources:** aronpetko/integral README, releases, PRs #2-#271.

### 15. Caissa 2.0 (#15, 3748; MIT). Prior: S2

- **New in the README:**
  - 32 king buckets with a factoriser;
  - QAT on all layers and an int8 head;
  - 8 output variants by piece count;
  - sparse inference with neuron reordering;
  - its own CUDA trainer;
  - fixed-node or fixed-depth self-play from UHO or DFRC openings.
- **Provenance note:** version 0.6 used a Stockfish net; the source of
  0.7's first data is unstated (UNVERIFIED).
- **Releases:** none since 2.0 (2026-09-19).
- **Sources:** README, releases, licence API.

### 16. Viridithas 20.0.0 (#16, 3747; MIT up to 20.0.0, AGPL-3.0 on master). Prior: S2

- **Since S2:**
  - correction on detected game cycles: +2.3 LTC;
  - avoiding corrhist collision bias: +3.7;
  - huge pages: +3.15;
  - checks treated as tactical in SEE pruning: +3.1 STC;
  - futility at higher depth: +1.4 LTC;
  - ProbCut and SEE-pruning simplifications.
- **Data:** own self-play only.
- **Sources:** releases, PRs #463-#481, licence API by ref.

### 17. Stormphrax 8.0.0 (#17, 3744). Prior: S2 supplement

- Nothing new since 2026-09-15 (no release, no PRs).
- Data: own self-play.
- Cited as an inspiration by pawnocchio and Hobbes.
- **Sources:** releases, PR listing, licence API.

### 18. Hobbes 3.0 (#18, 3743; Dan Kelsey; Rust; MIT, nets without a licence)

Over 400 PRs with results (STC 8+0.08, LTC 40+0.4).
- **TM:**
  - node fraction: +10.1;
  - best-move stability: +6.6 / +8.0;
  - score stability: +6.2 / +2.4;
  - a TM result confounded by time losses, then restored.
- **Corrhist:**
  - pawn +12.6, non-pawn +10.6, counter- and follow-up-keyed +11.6 and
    +10.6;
  - gravity +3.9;
  - draw-score update on repetition: +4.6 LTC.
- **History:**
  - **factorised quiet history: +17.2**;
  - dual indexing: +7.8;
  - summed continuation base: +10.6;
  - prior-countermove bonus: +8.65;
  - 4-ply continuation: +1.5 LTC.
- **Pruning:**
  - NMP eval margin: +13.05;
  - TT-bound gates on NMP and RFP: +4.5 / +5.0;
  - opponent-worsening RFP: +3.5;
  - mini-ProbCut: +3.7 LTC;
  - razoring: +8.0;
  - qsearch futility: +14.
- **Extensions:**
  - singular +25, double +3.25, negative +6.4;
  - hindsight +7.9 and +4.8;
  - singular refinements at +2.6 to +5.6 LTC;
  - a reversed-boolean bug fix: +16.7 LTC.
- **LMR:**
  - log formula +30.8, cut node +20.8, history +17.3;
  - alpha-raise reduction: +12.5.
- **TT:**
  - keep the existing move: +20.9;
  - early static-eval write: +12.2;
  - cutoffs only below alpha or at cut nodes: +3.0 LTC.
- **Draws:** fifty-move hash buckets: +2.3 on a fortress book.
- **SMP:** voting +5.0 at 8T; several LTC SPSA passes up to +20.1.
- **NNUE:**
  - mirrored king buckets grown 4→16 with data (+2 to +7 each);
  - a large TI block (+23.7 LTC), PP, pairwise;
  - dual activation (+16.5 LTC);
  - an ML head (+20.3 LTC);
  - lazy updates (+18.3 VSTC).
- **Training:**
  - own self-play from random init since 2025-09-17;
  - data steps +4.7 to +15.7;
  - DFRC data +6.2 for standard play;
  - random skipping +8.9;
  - a fine-tune on the newest data at a high result weight: **+8.9 LTC**;
  - its newest recipe ends at a low result weight (bundled).
- **Community note:** its release notes complain about "vibe-coded slop
  engines" (precedents.md).
- **Sources:** kelseyde/hobbes-chess-engine README, releases,
  network_history.txt, PRs #1-#445.

### 19-20. Horsie 1.1.0 (#19, 3735; GPL-3.0) and Lizard 11.2 (#20, 3732; MIT); author liamt19

- **Lineage:** Horsie is a near-identical C++ port of Lizard (+30.5 from
  speed alone, identical games at fixed nodes).
- **Search:**
  - futility +8.5;
  - NMP verification +2.0;
  - triple extensions +2.8 LTC;
  - hindsight +2.25;
  - aspiration depth adjustment on fails: +11.6 / +5.9 at 20+0.2;
  - no history updates from shallow cutoffs: +7.0;
  - low-ply history: +2.7;
  - **removing quiet checks from qsearch: +21.4**;
  - saving eval in non-hit TT entries: +14.7;
  - cuckoo: +12.3;
  - best-move stability TM: +16.2 / +17.9;
  - lazy updates: +27.5;
  - SPSA: +10.3 / +11.2.
- **NNUE:**
  - king buckets with Finny tables (−6 STC, +14 LTC at first);
  - pairwise (neutral in standard, +43.8 in DFRC);
  - a factoriser;
  - an ML head (+13.7 LTC in Horsie);
  - "utilitarian quantisation" (+7.7).
- **Data:** Lc0 T80 through 10.5, then self-play seeded by that net. The
  switch cost −33 / −36 at first.
- **Sources:** liamt19/Horsie and Lizard READMEs, releases, PRs, lizard-nets
  releases.

### 21-22. Astra 7.0 (#21-22, 3730; h1me01; GPL-3.0)

- **Search** (releases): pawn history, corrhist, capture history, 6-ply
  continuation history, history pruning, ProbCut, cuckoo, check extensions
  removed. Release gains: +113, +21, +128, +99.
- **NNUE:** king buckets, squared clipped ReLU; whether 7.0 shipped a
  proposed ML head is UNVERIFIED.
- **Data:** Lc0 games up to 6.1.1; 7.0 is own self-play from random weights
  (21 generations to beat the Lc0 net, about 12 B positions, public).
- **Sources:** h1me01/Astra README, releases, PRs #11-#15; the Hugging Face
  dataset card.

### 21-22. Raphael 4.2.0 (#21-22, 3730; Orbital-Web; AGPL-3.0 since 2026-07-03; README: no LLM-generated code)

- **Search:**
  - TT clusters +29.7 at 1 MB / +23.1 LTC;
  - TT eval in padding +8.4 / +5.3;
  - TT cutoff only at or below alpha or at cut nodes: +8.5;
  - NMP depth-scaled +23.4 LTC;
  - improving RFP +9.2;
  - opponent-worsening RFP +6.4;
  - corrhist tables +1.85 to +11.3, and correction size in LMR and RFP
    +2.6;
  - history in LMR +8.65;
  - direct-check ordering +6.3 / +2.8;
  - no futility for direct checks: +2.2, qsearch +5.2;
  - qsearch LMP +5.1;
  - optimism +5.9 LTC;
  - fractional depth: 0 / +7.35.
- **TM:** node +10.1 LTC; stability +4.2 LTC; eval stability +2.85 LTC;
  SPSA of TM +8.15 LTC.
- **SMP:** voting +9.8 at 8T; shared corrhist +5.1.
- **Releases:** 4.2 +57 / +75.
- **NNUE** (public net log):
  - mirroring;
  - OB +12.7;
  - king buckets grown with data (+25 to +33 early, then +8 to +10);
  - an integer ML head +6.6 LTC (float first lost);
  - threat inputs, modelled on Stormphrax, at about 36% speed loss
    (+6.7, then +7.9 LTC after widening).
- **Training:**
  - own self-play since 3.0, about 30 B positions;
  - a higher label budget +7.8;
  - a WDL-heavier fine-tune +18.3, plus +3.5, +3.5;
  - not sharing TT or history between datagen games +5.8;
  - a laptop GPU, about 5 h per net.
- **Sources:** Orbital-Web/Raphael README, releases, PRs #6-#164,
  history.txt.

### 23-25. RubiChess 20240817 (#23-25, 3727 as 8-CPU; Matthies; GPL-3.0)

- **Search:** OpenBench SPSA, corrhist, Finny tables, double extensions;
  node-fraction TM since 2022.
- **NNUE:** Stockfish's architecture and trainers.
- **Data:** own games labelled by its HCE, then its own nets; old data
  rotated out; rescaling the last layer after training +2 to +6.
- **Status:** "end of development most probably" (2024-08).
- **Sources:** Matthies/RubiChess README, ChangeLog.txt, Matthies/NN.

### 23-25. Starzix 6.0 (#23-25, 3727 as 8-CPU; zzzzz151; WTFPL). Prior: S2

- **Net:** mirrored single-layer net on Lc0 data. 6.0-era PR titles:
  enemy-queen input buckets, a power-2.5 loss, a "pieces" corrhist, gravity
  corrhist.
- **Search:** no results in its PR descriptions.
- **Sources:** README, PR titles #1-#203, Starway README.

### 23-25. Tarnished 6.0 (#23-25, 3727; Bobingstern; GPL-3.0)

- **Search:**
  - SEE pruning +14.8;
  - razoring +12.5;
  - quiet history pruning +8.9;
  - TT-PV in LMR +9.6;
  - fail-high count in LMR +9.8;
  - factorised LMR +6.35 LTC;
  - singular +15.9, negative +10.8, double +12.1 LTC;
  - corrhist: pawn +20.0, non-pawn +27.0, minor +16.9;
  - material scaling +5.4;
  - TT prefetch +14.3;
  - lazy updates +14.7;
  - complexity TM +6.6 LTC;
  - SPSA up to +12.0 LTC;
  - SMP rewrite +20.1 at 4T.
- **NNUE:**
  - mirroring +28.2 LTC;
  - king buckets +8.8, +26.7, +15.8 LTC;
  - an ML head (Alexandria-based) +20.7 LTC;
  - dual activation +3.5 LTC.
- **Training:**
  - own self-play from a random net, about 22 B positions;
  - all data relabelled by a much larger teacher (+3 to +4 LTC; teacher
    origin UNVERIFIED);
  - a mixed-budget fine-tune +6.5 to +6.9 LTC;
  - a high fine-tune WDL +3.9.
- **Sources:** Bobingstern/Tarnished README, releases, PRs #1-#160,
  tarnished-nets releases.

### 26. Clover 9.1 (#26, 3726; lucametehau; GPL-3.0). Prior: S2

- **Net:** SCReLU; king buckets chosen from king-square frequency, with a
  factoriser.
- **Data:** own self-play at two node budgets, about half DFRC; a final net
  on deeper data plus a linear-WDL retrain.
- **Datagen fixes:** early adjudication, dropping lopsided openings.
- **Search titles:** an eval-difference history update, LMR by correction
  size, continuation corrhist at 3-4 plies, ProbCut at cut nodes, a VLTC
  tune.
- **Removed:** PGO and ponder.
- **Sources:** lucametehau/CloverEngine README, releases, PRs #286-#407;
  CPW.

### 27. Ethereal 14.25 (#27, 3722 as 8-CPU; Andrew Grant; code GPL-3.0, nets all rights reserved)

- **Search** (commit messages):
  - node-share TM: +9.85 / +9.66;
  - singular wrapper: +16.8 / +3.7;
  - double extensions: +6.8 / +8.9;
  - negative extensions: +3.4 / +6.4;
  - cut-node IIR: +4.4 / +2.9;
  - history-scaled SEE margins: +7.0 / +2.3;
  - keep the TT move on an upper bound: +4.5 / +3.5;
  - no TT cutoffs at all-nodes: LTC +2.45 (STC failed);
  - lower-depth TT entries before a re-search: +4.3 / +4.6;
  - threatened-square butterfly history: +2.3 / +2.9;
  - TT-gated ProbCut: +3.6 / +4.2;
  - early TT eval store: +2.6, +9.9 at 8T;
  - SMP voting with fail-highs: +4.9 at 8T.
- **NNUE:**
  - mirrored HalfKP grown in steps (wider layers failed STC and passed LTC
    until the data grew);
  - Finny tables +8.6;
  - tiling +9.95.
- **Training:**
  - its own CPU trainer;
  - 100 M-game sets;
  - the label node budget raised in steps (+6 to +19 per step);
  - a deep final LR drop;
  - adversarial games against Stockfish;
  - **a pure-result fine-tune of the best net: +42.7 / +35.6 (2024-04,
    after 14.25)**.
- **Regression:** 14.25 over 14.00: +61.5 at 60+0.6.
- **Sources:** AndyGrant/Ethereal README, releases, the last 100 commits;
  the 14.25 page; TalkChess; CPW; the TCEC questionnaire of 2025-11-09.

### 28. Fritz 20 (#28, 3721 as 8-CPU; ChessBase, commercial)

- A Ginkgo-based engine, credited to Frank Schneider.
- Vendor claims: a neural evaluation, over +100 against Fritz 19, about
  3580.
- **Data:** not stated (presumably Ginkgo self-play, UNVERIFIED).
- **Sources:** ChessBase announcement and review; CCRL details.

### 29. Halogen 16.0.0 (#29, 3720; KierenP; GPL-3.0). Prior: S2

- **Search, not in S2:**
  - triple extensions +7.8 LTC;
  - double negative extensions +5.0;
  - removing in-check extensions +8.3 STC;
  - a threat-raised RFP margin +3.7;
  - fail-medium +4.6 LTC;
  - root fail-high depth reduction +5.1 LTC;
  - prior-countermove +6.4 / +2.65;
  - history caps +3.45;
  - knight-takes-bishop counted as a threat +4.5;
  - 4-ply continuation +4.6;
  - thread voting +8.4 at 8T;
  - SMP SPSA mixed (1T losses).
- **Releases:** 16 over 15: +57 / +59.
- **NNUE:** TI only after v16 (+10.4 LTC), then widened.
- **Training:**
  - own data only (TDLeaf from zero);
  - piece-count filtering +13.2 LTC;
  - result-against-eval filtering +4.0 LTC;
  - a WDL 1.0 fine-tune +6.9 LTC (0 STC);
  - a linear WDL ramp with Ranger +5.4 LTC;
  - a pessimistic loss skew +3.2 LTC;
  - a higher WDL weight passing only at VLTC.
- **Sources:** KierenP/Halogen PRs #690-#912; Halogen-Networks releases;
  CPW.

### 30. Quanticade Cronus 3.0 (#30, 3716; Haxk20; C; GPL-3.0)

- **Lineage:** from the BBC tutorial engine; 0.6b ran a Stockfish net.
- **Search:**
  - threat history +11.4;
  - early TT eval +8.0;
  - TT score qualified by static eval +6.1;
  - corrhist items;
  - opponent-worsening RFP +1.85;
  - less LMR for checks +6.6;
  - qsearch futility +4.1;
  - ProbCut +5.5 at 60+0.6;
  - tunes up to +7.2 LTC and +6.1 VVLTC.
- **NNUE:** mirrored king buckets, an ML head (+6.2 LTC, lost at STC).
- **Data:** Lc0 for Cronus. Self-play afterwards: +14.7 LTC over the Lc0
  net, then TI +7.7 LTC.
- **Sources:** Quanticade/Quanticade README, releases, PRs.

### 31. Igel 3.8.0 (#31, 3712; vshcherbyna; GPL-3.0; forked from GreKo)

- **Search:**
  - SPSA of 42 parameters over 400k games: +24.9 / +19.5;
  - corrhist retune: +9.7 LTC;
  - capture history: +7.0 LTC;
  - TT replacement: +5.5 LTC;
  - in-check futility guard: +4.8 STC;
  - IID: +14.5 LTC (3.6.0).
- **NNUE:** Stockfish's feature set and trainer. Whether 3.8.0's net has
  threats is UNVERIFIED.
- **Data:** own data since late 2020 (HCE, then own nets).
- **Sources:** vshcherbyna/igel README, releases, PRs #292-#375; CPW.

### 32. PZChessBot 7.1 (#32, 3711; kevlu8 and a co-author; C++; AGPL-3.0)

- **Search:**
  - soft-node TM: +24.4 / +16.3;
  - complexity TM: +8.8 (later removed);
  - fail-firm: +16.6;
  - RFP mean return: +10.0;
  - threat history: +11.0 / +17.0;
  - corrhist items;
  - shared corrhist: +8.5 (removed later, neutral);
  - NMP at cut nodes: +4.0 (partial);
  - pawn history: +3.9 LTC;
  - fifty-move scaling on endgame books: +6.5 LTC.
- **NNUE:**
  - mirrored king buckets, pairwise, an ML head (+16.0 LTC), OB;
  - after 7.1: TI +14.9 LTC at about 30% slower, then speed work.
- **Data:** own self-play from a random net since v4.0 (+134 LTC over the
  Lc0-trained 3.0); an early endgame net about +20.
- **Sources:** kevlu8/PZChessBot README, releases, PRs; PZChessBot-Networks.

### 33. ZigQueen 6.5.0 (#33, 3709; Matthias Stier; Zig; GPL-3.0-or-later)

- **AI use:** Claude and Codex wrote most of the code under the author's
  direction (precedents.md).
- **Search:**
  - a PV bug fix: +36 at 20+0.2;
  - TT move before generation: +7;
  - low-depth singular: +9;
  - a corrhist bundle feeding RFP, futility and LMR: +18.0 at 60+0.6;
  - pin-aware SEE and a new TM in 6.5.
- **NNUE:** mirrored king buckets, full threats, PP, an ML head, full QAT.
- **Data:** 131 B positions of Stockfish and Lc0 binpacks relabelled by
  BT4; tablebase rescoring at 5 pieces or fewer.
- **Sources:** stierms/zigqueen README, docs/NETWORK.md, docs/PROVENANCE.md,
  ORIGINALITY.md.

### 34. Devre 7.0 (#34, 3704; GitHub OmerFarukTutkun; GPL-3.0)

- **Search:**
  - corrhist first table +20.5, non-pawn +11.9;
  - corrhist in LMR +2.6;
  - node TM +15.4;
  - stability +7.8;
  - eval-stability +3.1.
- **NNUE:** king buckets plus PP: +24.1 LTC (neutral at STC). After 7.0:
  TI +30.6 LTC.
- **Training:** **an NNUE distilled from its own transformer teacher, +21.7**
  (after 7.0).
- **Data:** built-in self-play from 7.0. Leela data in 4.0; whether any
  remains in 7.0 is UNVERIFIED.
- **Sources:** OmerFarukTutkun/Devre README, releases, PRs #21-#82.

### 35. JustBot 0.5.0 (#35, 3703; GitHub HasanFakih21; Rust; AGPL-3.0; README: no LLM-generated code)

- **Search:**
  - node TM: **+29.7 / +22.4**;
  - removing check extensions: +10.0;
  - hindsight: +3.9 LTC;
  - thread voting: +12.1 at 8T;
  - shared corrhist: +6.4 at 8T.
- **NNUE:** a wider layer failed STC and passed LTC (+8.9).
- **Data:** own self-play from the PeSTO eval.
- **Sources:** HasanFakih21/JustBot README, releases, PRs.

### 36-38. Minke 7.0.0 (#36-38, 3702; enfmarinho; GPL-3.0)

- **Search:**
  - node TM: +8.5 LTC;
  - PV stability: +4.1 LTC;
  - score stability: +3.4 LTC;
  - complexity in RFP: +2.6;
  - removing qsearch futility: **+6.6**.
- **NNUE** (log): an ML head +17.9 LTC; dual activation +6.0 LTC.
- **Training:**
  - own self-play from random init since 2026-06, 23 B positions;
  - old-data purge: +11.8, +3.8 LTC;
  - piece-count filter: +10.8 LTC;
  - tablebase-consistency filter: +2.3;
  - a sparsity regulariser: +3.7 LTC;
  - a higher fine-tune WDL: +8.1 LTC.
- **Sources:** enfmarinho/Minke README, releases, PRs; MinkeNets
  history.txt.

### 36-38. Titan 1.1.0 (#36-38, 3702 as 8-CPU; jeff-pow; Rust; GPL-3.0)

- Node TM +4.2.
- SCReLU +111.
- Lazy SMP: 2T +91, 4T +136.
- Mirrored king buckets: +14.7 LTC.
- **Data:** Lc0, filtered with Primer.
- **Sources:** jeff-pow/Titan README, releases, PRs.

### 36-38. Velvet 8.1.0 (#36-38, 3702 as 8-CPU; Martin Honert; Rust; GPL-3.0)

- **Search:** the standard set (CPW).
- **NNUE:** king buckets × 768 inputs; **8.1.0 moved the input layer to
  8-bit weights**; two embedded style nets.
- **Data:** own self-play since 2.0, labelled by its own search, with
  score adjustments for lost sacrifices and material statistics.
- **Sources:** mhonert/velvet-chess README, releases; CPW Velvet.

### 39. Ginkgo Santiago 1.0 (#39, 3699 as 8-CPU; Frank Schneider; private)

- **Search:** parallel PVS with a shared TT (CPW).
- **NNUE:** the incremental update is done per side and per full move;
  scores are transformed before training and back after evaluation.
- **Data:** about 6.7 B positions of self-play of earlier versions;
  Guideline-compliant by the author's statement.
- **Sources:** the TCEC questionnaire of 2025-10-13; CPW.

### 40-41. Revenge 4.0 (#40-41, 3698 as 8-CPU; Fabio Gobbato; free, closed)

- **Search:** releases list reverse futility, history reductions, ProbCut
  and better parallel search.
- **Releases:** +90 (2.0), +38 (4.0; an independent tester measured +58.2).
- **NNUE:** "pure neural network".
- **Data:** a chain from Pedone's HCE labels (stated for 1.0); later data
  UNVERIFIED.
- **Sources:** revengechess.com; TalkChess release threads; CPW.

### 40-41. Tcheran 14.0 (#40-41, 3698; jgilchrist; Rust; AGPL-3.0)

- **Search** (CHANGELOG):
  - TT in qsearch: +40.2;
  - singular: **+34.0 LTC**;
  - corrhist: pawn +21.8, major and minor +18.9, non-pawn +12.7, threat
    +9.3, 1-ply continuation +8.2;
  - threat history: +9.3 LTC;
  - node TM: +16.0 LTC;
  - NMP at cut nodes: +8.6;
  - pinned pieces in SEE: +7.6;
  - summed continuation base: +9.1;
  - hindsight: +4.5 and +3.3;
  - upcoming repetition with a corrhist update;
  - NNZ sparse inference: +12.1;
  - SPSA up to +24.4.
- **NNUE:** mirroring, king buckets, an ML head (+16.5), dual activation
  (+7.2), Ranger (+3.5), a sparsity loss with more data (+16.0).
- **Data:** own self-play only, public; a deeper-label add-on +19.2; a
  WDL fine-tune +5.0; a first-stage ramp −7.0.
- **Sources:** tcheran-chess/tcheran README, NET.md, CHANGELOG.md.

### 42. Uralochka 3.41a (#42, 3697 as 8-CPU; Ivan Maklyakov; GPL-3.0-or-later)

- **Releases:** 3.41 +140.9 at 10+0.1, +69.0 at 60+0.6.
- **NNUE:** HalfKP-like inputs, a wide accumulator, 6 OB; uses
  nnue-pytorch's sparse class (credited).
- **Data:** own self-play at very short searches, plus positions from its
  games against other engines, scored by itself.
- **Sources:** gitlab.com/freemanzlat/uralochka3 README at v.3.41 and
  v.3.42, releases.

### 43-44. Lc0 0.29.0 (#43-44, 3696 on an RTX 2080 with a 2022 net; GPL-3.0-or-later)

- **Search:** PUCT MCTS; graph search sharing transpositions ("outperforms",
  no number).
- **Net:** transformers since 2022. The Chessformer paper (arXiv 2605.19091)
  reports +105 to +112 against the CNN.
- **WDL head** since 2019.
- **Value target:** search value blended with the game result.
- **Tablebase rescoring** of game results.
- **Rich training records** (search value, played-move value, moves left,
  adjudication flags).
- **Data:** its own self-play, ODbL/DbCL.
- **Sources:** LeelaChessZero/lc0 README and v0.29.0 release; lczero.org
  blog and wiki; arXiv 2605.19091; TCEC questionnaires 20251107 and
  20261106.

### 43-44. Seer 2.8.0 (#43-44, 3696 as 8-CPU; GitHub connormcmonigle; GPL-3.0). Prior: S2

- **Provenance:** v1.x nets were Stockfish-derived; 2.0 and later are own
  data only.
- **2.8.0** includes a result-only fine-tune, repetition-detection work, an
  SPSA tune and probably eval corrhist (UNVERIFIED by merge dates).
- **Later:** continuation corrhist; threading +3.4 at 4T.
- **Sources:** connormcmonigle/seer-nnue README, releases, PRs #174-#211;
  CPW.

### 45-48. Chess System Tal 3.00 (#45-48, 3694; Chris Whittington, nets by Ed Schroder; free binary, all rights reserved)

- **Search:** Whittington's own (shared with Rebel).
- **NNUE:** a freshly trained, larger net (inferred from binary size,
  UNVERIFIED); style nets trade Elo for aggression.
- **Data:** not stated.
- **Its author runs the "engine forensics" page** (precedents.md).
- **Sources:** whittingtonchess.com; GitHub release text; TalkChess.

### 45-48. Motor 0.9.0 (#45-48, 3694; Martin Novak; C++20; no licence)

- **0.7.0:**
  - MPE loss +24;
  - pawn corrhist +6;
  - material scaling +6.75;
  - qsearch check evasions +12.5.
- **0.9.0:** mostly corrhist experiments plus a bullet net, +50.5 LTC.
- **Data:** not stated (UNVERIFIED). A fully public zero-knowledge restart
  began 2026-10-31.
- **Sources:** martinnovaak/motor README, releases, PRs #164-#225.

### 45-48. Renegade 1.3.0 (#45-48, 3694; pkrisz99; MIT)

- **1.3.0:**
  - history pruning;
  - low-depth singular and triple extensions;
  - fractional LMR;
  - NMP and IIR at cut nodes;
  - pin-aware SEE;
  - +78.3 / +91.6 over 1.2.0.
- **1.2.0:** corrhist, threat capture history, RFP mean return.
- **NNUE:** mirrored king buckets, OB, half-move scaling.
- **Data:** own self-play from a king-tropism eval; 8.4 B positions,
  published.
- **Sources:** pkrisz99/Renegade README, releases.

### 45-48. Stoofvlees II b5 (#45-48, 3694 on an RTX 2080; Gian-Carlo Pascutto; private)

- MCTS plus a neural net, mostly the author's own design; won the 2023
  WCCC.
- **Data:** own self-play plus Leela data.
- An ICGA Journal paper (vol. 47(3)) could not be opened (UNVERIFIED).
- **Sources:** the TCEC questionnaire of 2025-11-09; CPW; icga.org.

### 49. Rebel 17.0 (#49, 3689; Whittington's code, Schroder's net; free, closed)

- The same net as 16.3, yet +55 from code alone.
- Schroder's data tools balance W/D/L outcomes (about +10).
- **Data:** not stated.
- **Sources:** the rebel7775 site; TalkChess; CPW.

### 50. rofChade 3.1 (#50, 3687 as 8-CPU; Ronald Friederich; free, closed)

- **Search:** the classical feature list; a PeSTO fallback at large scores.
- **NNUE:** HalfKA in 3.0, then a simpler net in 3.1 on about 10 B
  repeatedly relabelled positions.
- **Data:** own until dev 3.105; after that, Lc0-derived Stockfish data,
  declared Guideline non-compliant.
- **Sources:** the TCEC questionnaire of 2025-11-12; rofchade.nl; TalkChess;
  CPW.
