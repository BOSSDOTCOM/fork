# Fork KB: Research (2023 to present)

Papers, releases and results relevant to Fork, **newest first**. Written
2026-10-23. Every entry was checked against a page that was actually opened
(see `_sources-research.md`). Anything not confirmed on an opened page is
marked **UNVERIFIED** with the reason.

Tags:

- **USE**: Fork may use it directly (permissive library, or data Fork may
  legally and under its own rules train on or test with).
- **REFERENCE ONLY**: study the idea, write Fork's own code. Default for
  papers and techniques.
- **OFF-LIMITS**: must not enter Fork in any form (Stockfish code or nets,
  Stockfish-labelled data, data from other engines' search/eval).

Fork's own rule (docs/ORIGINALITY.md): NNUE nets are trained **only** on data
Fork generated itself. So any dataset whose labels come from another engine is
OFF-LIMITS as training data even when its license would allow it.

---

## 0. Quick takeaways for Fork's plan

1. **Training-data traps are everywhere.** ChessBench (DeepMind), the MAV
   data, the Lichess evaluation database, Stockfish's nnue-pytorch datasets
   and the HF "relabel" sets are all labelled by Stockfish or Lc0. All are
   OFF-LIMITS as Fork training data. Lichess *game* exports (CC0, human
   moves) are fine as a source of starting positions, but their embedded
   evals are not.
2. **Stockfish itself trains on Lc0 data** (SF17/18/19 release notes) and
   since SF19 rescored everything with a Leela net. Fork's
   "own self-play only" rule is stricter than what the top engine does, so
   expect a slower path to strength. Plan the bootstrapping chain early
   (section on training in techniques.md).
3. **Threat inputs are now mainstream at the top.** SF18 (2026-01-31) added
   "Threat Inputs" to the NNUE input layer (up to +46 Elo for the whole
   release); SF19 (2026-09-05) pruned redundant threat features and added
   pawn-pair features. Fork's Phase 4 NNUE plan (HalfKA-style only) should
   reserve a slot for a threat-feature accumulator as a later step.
4. **Correction history is now standard** (introduced Oct 2023 in Caissa,
   listed in SF18 notes, on CPW's recommended feature list). Its gain grows
   with time control, which matters for TCEC's long TC. Put it in Phase 3.
5. **Robustness:** the Go adversarial-policy work shows that superhuman
   engines can have exploitable, systematic blind spots that survive
   adversarial training. No chess-specific adversarial-policy paper was
   found. For an alpha-beta engine the practical takeaway is consistency
   testing (mirrored positions, forced moves) and fortress/blockade testing.
6. **Searchless transformers are not a threat to the plan.** The best
   searchless models play around 2900 Lichess blitz vs humans; MCTS-guided
   transformer play reaches more, but none are near a TCEC-class alpha-beta
   engine. They are REFERENCE ONLY.

---

## 1. Engine releases and architecture (2026)

### Stockfish 19 (release post dated 2026-09-05)
- **What:** New net architecture SFNNv16: removes redundant threat features
  (smaller binary), adds pawn-pair features, retires the secondary ("small")
  net introduced in SF16.1. Training used hundreds of billions of positions,
  added quantization-aware training (QAT), and every position was rescored
  with a strong Leela net. Up to +44 Elo vs SF18.
- **Why it matters for Fork:** confirms the direction of NNUE input design
  (threats + pawn structure features on top of king-relative piece
  features), and that QAT is worth having in a trainer. Also confirms that
  the top engine's training data is Lc0-labelled, so Fork cannot copy its
  data recipe.
- **Search changes:** the post does not mention any (UNVERIFIED whether any
  were made; the page simply lists none).
- Source: https://stockfishchess.org/blog/2026/stockfish-19/
- Verified 2026-10-23. Tag: **REFERENCE ONLY** for ideas; nets/code/data
  **OFF-LIMITS** (GPL-3.0 code; nets trained on Lc0-rescored data).

### Stockfish 18 (2026-01-31)
- **What:** SFNNv10 adds "Threat Inputs" to the input layer so the net sees
  attacked pieces directly. Search notes mention Correction History,
  better stalemate and fortress handling, and a fix for a rare
  repetition/en-passant/pin bug. Training pipeline made reproducible and
  chained, using over 100 billion positions of Lc0 evaluation data. Shared
  memory lets several processes share net weights. Up to +46 Elo vs SF17.
- **Why it matters:** threat inputs are the most important NNUE input change
  since HalfKAv2_hm. The nnue-pytorch docs (section 4) describe the
  feature design. The repetition/ep/pin bug is a reminder to include such
  positions in Fork's Phase 1/3 tests.
- Source: https://stockfishchess.org/blog/2026/stockfish-18/
- Verified 2026-10-23. Tag: **REFERENCE ONLY** (ideas); code/nets/data
  **OFF-LIMITS**.

### Chessformer: A Unified Architecture for Chess Modeling (ICLR 2026; arXiv 2605.19091, submitted 2026-05-18)
- **Authors:** Daniel Monroe, George Eilender, Philip Chalmers, Zhenwei Tang,
  Ashton Anderson.
- **What:** Encoder-only transformer with squares as tokens, a dynamic
  positional scheme called Geometric Attention Bias, and an attention-based
  from-to policy head. Integrated into Lc0 it adds over 100 Elo (authors'
  claim); the same architecture powers Maia-3 (human-move prediction,
  57.1% move matching). The Lc0 blog notes the BT4 net is this architecture
  and that this paper supersedes the 2024 preprint and blog.
- **Why it matters:** reference for the state of NN+MCTS engines Fork will
  meet at TCEC (Lc0). Not applicable to Fork's CPU NNUE.
- Source: https://arxiv.org/abs/2605.19091 (paper CC BY 4.0). Code/model
  license for the Lc0 integration not stated on the abstract page.
- Verified 2026-10-23. Tag: **REFERENCE ONLY**.

### Maia-3 (model card UofTCSSLab/Maia3-79M)
- **What:** 79M-parameter Chessformer-based model predicting the move a
  human of a given rating would play. Trained on Lichess human games
  Jan 2023 to Jul 2025. Model license AGPLv3. Explicitly "not intended for
  maximum playing strength". The Maia-2 README now recommends Maia-3.
- **Why it matters:** only relevant if Fork ever wants a human-style or
  odds-play mode. AGPLv3 is copyleft, so do not link it into Fork.
- Source: https://huggingface.co/UofTCSSLab/Maia3-79M
- Verified 2026-10-23 (model card). The Lichess announcement post
  returned HTTP 403; the code repo github.com/CSSLab/maia3 was not opened,
  so the **code license is UNVERIFIED**. Tag: **REFERENCE ONLY**.

---

## 2. LLM-based and searchless chess

### How Reasoning Evolves from Post-Training Data: An Empirical Study Using Chess (arXiv 2604.05134, 2026-04-06, ICML 2026)
- Dionisopoulos, Majamaki, Ammanabrolu. Studies SFT then RL on a 7B language
  model for chess. Direct best-move SFT gives the best results but RL then
  produces reasoning that does not match the chosen move; multi-move
  trajectory SFT is comparably strong and more faithful.
- **For Fork:** none directly; LLM chess is far from engine strength.
- Source: https://arxiv.org/abs/2604.05134. Verified 2026-10-23.
  Tag: **REFERENCE ONLY**.

### Tracking vs. Deciding: The Dual-Capability Bottleneck in Searchless Chess Transformers (arXiv 2603.29761, 2026-03-31)
- Li, Jiang. Move-sequence-only transformers (28M to 120M params); argues
  strength is capped by the weaker of board-state tracking and decision
  quality. Elo-weighted training helps decisions; dropping low-rated games
  hurts tracking. 120M model about 2570 Lichess bullet without search; 55.2%
  human top-1 move prediction (above Maia-2).
- **For Fork:** none directly. Training-set dataset is not named in the
  abstract (UNVERIFIED).
- Source: https://arxiv.org/abs/2603.29761. Verified 2026-10-23.
  Tag: **REFERENCE ONLY**.

### Out-of-distribution Tests Reveal Compositionality in Chess Transformers (arXiv 2510.20783, 2025-10-23)
- Meszaros, Reizinger, Huszar. 270M searchless transformer trained on
  ChessBench behaviour-cloning data (labels: Stockfish 16 best moves;
  evaluated against Stockfish 17). Legal-move extrapolation is good; on
  Chess960 it adapts but trails search engines. Lichess results: about 1550
  bullet, 1571 Chess960, 1493 blitz (authors note opponent selection bias).
- **For Fork:** confirms searchless nets degrade out of distribution (e.g.
  Chess960), a reason to keep search central.
- Source: https://arxiv.org/abs/2510.20783 and HTML full text. Verified
  2026-10-23. Tag: **REFERENCE ONLY**; its data is **OFF-LIMITS**.

### Mastering Board Games by External and Internal Planning with Language Models (arXiv 2412.12119, v1 2024-12-02, v3 2025-05-23)
- Schultz, Adamek, Jusup, Lanctot et al. (16 authors, DeepMind). A 2.7B
  "multi action-value" (MAV) transformer for chess, Chess960, Connect Four,
  Hex. External search = MCTS guided by the model; internal search = model
  writes a linearised search tree in context. Chess labels come from
  Stockfish (version not stated). Reported external Elo estimates: MAV about
  2923; MAV-MCTS with 2000 simulations about 3209 (approximate).
- **For Fork:** MCTS+transformer reaches strong-human/superhuman level with
  small search budgets; still far below top engines at TCEC time control.
- Venue: arXiv page lists none; ICML 2025 (PMLR 267) comes only from a
  search result, **UNVERIFIED**.
- Source: https://arxiv.org/abs/2412.12119, https://arxiv.org/html/2412.12119v3.
  Verified 2026-10-23. Tag: **REFERENCE ONLY**; data **OFF-LIMITS**
  (Stockfish labels).

### Mastering Chess with a Transformer Model (arXiv 2409.12272, v1 2024-09-18, v2 2024-10-28)
- Monroe, Chalmers. First "Chessformer" preprint; claims it beats AlphaZero
  with about 8x less compute and matches prior GM-level transformer agents
  with about 30x less. Superseded by the ICLR 2026 paper above.
- Source: https://arxiv.org/abs/2409.12272. Verified 2026-10-23.
  Tag: **REFERENCE ONLY**.

### Grandmaster-Level Chess Without Search / Amortized Planning with Large-Scale Transformers: A Case Study on Chess (arXiv 2402.04494, v1 2024-02-07, v2 2024-10-21; NeurIPS 2024)
- Ruoss, Deletang, Medapati, Grau-Moya, Wenliang, Catt, Reid, Lewis, Veness,
  Genewein (DeepMind). v1 title "Grandmaster-Level Chess Without Search";
  v2 retitled "Amortized Planning with Large-Scale Transformers: A Case
  Study on Chess". Supervised transformers up to 270M params; best policy
  reaches Lichess blitz Elo 2895 vs humans with no search. Paper concludes
  perfect distillation of Stockfish's search is still out of reach.
- **ChessBench dataset:** 10M games, about 15 billion data points (legal
  move + action-value / state-value annotations). **All labels from
  Stockfish 16.** Action-value set about 1.1 TB in 2,148 shards. Licenses
  per README: code Apache-2.0; weights CC-BY 4.0; dataset partly CC0
  (Lichess-derived parts) and the rest CC-BY 4.0. Venue "NeurIPS 2024" is
  stated in the repo README.
- **For Fork:** **ChessBench is OFF-LIMITS as Fork training data**: its
  values and moves are Stockfish 16 output. The permissive license does not
  change that; using it would make Fork's net Stockfish-derived in TCEC's
  eyes and breaks ORIGINALITY.md. The paper itself is REFERENCE ONLY. The
  puzzles file could be used only as a *test* set if its provenance is
  checked first (UNVERIFIED how puzzles were built).
- Sources: https://arxiv.org/abs/2402.04494, https://arxiv.org/abs/2402.04494v1,
  https://github.com/google-deepmind/searchless_chess (+ README).
  Verified 2026-10-23. Tags: paper **REFERENCE ONLY**; ChessBench data and
  weights **OFF-LIMITS** for Fork.

### ChessGPT: Bridging Policy Learning and Language Modeling (arXiv 2306.09200, 2023-06-15, NeurIPS 2023)
- Feng et al. GPT-style model mixing game data and chess text; releases
  code, model, dataset at github.com/waterhorse1/ChessGPT. Dataset and code
  licenses not on the abstract page (**UNVERIFIED**; repo not opened).
- **For Fork:** none. Source: https://arxiv.org/abs/2306.09200. Verified
  2026-10-23. Tag: **REFERENCE ONLY**.

---

## 3. Human-like engines

### Maia4All: Learning to Imitate with Less: Efficient Individual Behavior Modeling in Chess (arXiv 2507.21488, 2025-07-29)
- Tang, Jiao, Xue, McIlroy-Young, Kleinberg, Sen, Anderson. Builds on
  Maia-2: an enrichment step with prototypes, then individual embeddings
  initialised from ability level/prototypes; models an individual from 20
  games instead of 5,000.
- **For Fork:** none for strength. Source: https://arxiv.org/abs/2507.21488.
  Verified 2026-10-23. Tag: **REFERENCE ONLY**.

### Maia-2: A Unified Model for Human-AI Alignment in Chess (arXiv 2409.20553, 2024-09-30, NeurIPS 2024)
- Tang, Jiao, McIlroy-Young, Kleinberg, Sen, Anderson. One model for all
  skill levels via skill-aware attention combining player rating with the
  position encoding.
- Repo CSSLab/maia2: code MIT; rapid and blitz weights downloadable;
  trained on Lichess rated rapid/blitz games May 2018 to Nov 2023 (BOT games
  excluded). **Weight license not stated (UNVERIFIED).**
- Sources: https://arxiv.org/abs/2409.20553, https://github.com/CSSLab/maia2.
  Verified 2026-10-23. Tag: **REFERENCE ONLY**.

### Maia (background, 2020)
- "Aligning Superhuman AI with Human Behavior: Chess as a Model System",
  McIlroy-Young, Sen, Kleinberg, Anderson, KDD 2020 (arXiv 2006.01855).
  Pre-2023 but the base of the line above. Exact accuracy figure not on the
  abstract page (not needed).
- Source: https://arxiv.org/abs/2006.01855. Verified 2026-10-23.
  Tag: **REFERENCE ONLY**.

---

## 4. Diversity and creativity

### Diversifying AI: Towards Creative Chess with AlphaZero (arXiv 2308.09175, v1 2023-08-17, v3 2024-07-31)
- Zahavy, Veeriah, Hou, Waugh, Lai, Leurent, Tomasev, Schut, Hassabis,
  Singh. AZ_db: a league of AlphaZero agents in one latent-conditioned
  network, trained with behavioural diversity objectives; picks among
  ideas via sub-additive planning. Solves twice as many hard puzzles as AZ
  (including Penrose positions); choosing a specialist per opening gives
  +50 Elo over AZ.
- **For Fork:** two transferable ideas for an alpha-beta engine: (a)
  diversity in self-play data generation (varied openings, randomised
  early moves, several parameter "personalities") to avoid a narrow
  training distribution; (b) per-opening specialisation is a real effect,
  which supports testing Fork with varied/unbalanced books. No code, data or
  weights released per the abstract page (**UNVERIFIED** that nothing exists
  elsewhere). No 2024-26 follow-up by the same group was found.
- Source: https://arxiv.org/abs/2308.09175. Verified 2026-10-23.
  Tag: **REFERENCE ONLY**.

---

## 5. Adversarial robustness

### Can Go AIs be adversarially robust? (arXiv 2406.12843, v1 2024-06-18, v3 2025-01-14; AAAI 2025)
- Tseng, McLean, Pelrine, Wang, Gleave. Tested three defences for KataGo
  (adversarial training on hand-made positions, iterated adversarial
  training, architecture change). Some block known attacks; none survive
  freshly trained adversaries. Most successful new attacks are variants of
  the "cyclic" attack class.
- Source: https://arxiv.org/abs/2406.12843. Verified 2026-10-23.
  Tag: **REFERENCE ONLY**.

### Adversarial Policies Beat Superhuman Go AIs (arXiv 2211.00241, v4 2023-07-13; ICML 2023)
- Wang, Gleave, Tseng, Pelrine, Belrose, Miller, Dennis, Duan, Pogrebniak,
  Levine, Russell. Adversary wins over 97% against KataGo at superhuman
  settings by inducing blunders, transfers zero-shot to other Go AIs, and
  humans can execute it. Vulnerability persists after adversarial training.
- Source: https://arxiv.org/abs/2211.00241. Verified 2026-10-23.
  Tag: **REFERENCE ONLY**.

### Evaluating Superhuman Models with Consistency Checks (arXiv 2306.09983, v1 2023-06-16, v3 2023-10-19)
- Fluri, Paleka, Tramer. Tests Lc0 (release/0.29, net T807785) and
  Stockfish 15.1 for evaluation consistency. At 400 nodes, about 20% of
  board-transformed (pawnless rotations/mirrors) pairs differ by more than
  0.05 in win prob, about 6% by more than 0.1; forced-move and
  recommended-move checks also fail at measurable rates. Adversarial search
  finds up to 9x more failures than random; 8x more nodes cuts failures only
  3 to 6.6x.
- **For Fork:** cheap, automatable tests: eval(position) vs eval(colour-
  flipped position) must be exactly equal for a symmetric NNUE/PST; forced
  moves; consistency along the PV. Add to Phase 4 tests.
- Source: https://arxiv.org/abs/2306.09983, https://arxiv.org/html/2306.09983v3.
  Verified 2026-10-23. Tag: **REFERENCE ONLY**.

### Chess-specific adversarial attacks
- Searches found **no** chess-specific adversarial-policy paper (2023-2026).
  This is an absence in searches, not a verified absence: **UNVERIFIED**.
- **Implications for Fork:** (1) search-heavy engines are less exposed than
  pure-policy nets, but systematic eval blind spots (fortresses, blockades,
  long-term zugzwang) are the chess analogue; SF18's notes explicitly
  mention fortress-evaluation work. (2) Self-play-only training can share
  blind spots across generations; add diversity (section 4) and test
  against a gauntlet of different engines (Phase 8). (3) Keep evaluation
  symmetric and deterministic so consistency tests are meaningful.

---

## 6. NNUE architecture and training (2023+)

### nnue-pytorch documentation (Stockfish trainer docs, living document)
- Core ideas (own words): keep active inputs few and slowly changing so the
  first layer can be huge yet cheap; accumulate first layer incrementally;
  run inference in integers.
- **Feature sets:** "A" = 768 (piece x colour x square). HalfKP = 64 king
  squares x 64 x 10 piece kinds = 40,960, no king features, full refresh on
  king move. HalfKA adds kings. HalfKAv2 merges both kings into one
  "king" piece slot (about 8% smaller). HalfKAv2_hm mirrors horizontally so
  the own king is on files e-h, halving king buckets.
- **Threat features (Full_Threats):** attacker-piece/target-piece pairs from
  each side's perspective; redundant pairs dropped (e.g. king-king, attacks
  on kings, duplicates); stored as int8, widened to int16 when accumulated;
  kept in a separate accumulator; only refreshed when the king crosses the
  d/e file boundary. PP_3Wide: unordered pawn pairs on same or adjacent
  files (removes pawn-pawn threats from the threat set).
- **Factorisers:** training-only "virtual" features (e.g. piece-square
  ignoring king) that share learning across king buckets; folded into real
  weights after training so inference cost is unchanged; mostly help early.
- **Layer stacks / output buckets:** 8 sub-networks chosen by
  (piece_count - 1) / 4; implemented as one wide layer and gathered.
- **Quantisation:** feature transformer int16 accumulation, clipped to
  0..127 then int8; hidden weights int8 with scale 64 (max about 1.98);
  powers-of-two scaling so divisions are shifts.
- **SIMD:** AVX2 16 int16 lanes / 16 registers (32 on AVX-512); int8 dense
  layers via multiply-add into int32; VNNI fuses it; first dense layer is
  sparse (about 15% non-zero) so sparse kernels pay off.
- **Loss:** cp scores mapped to win probability with a sigmoid (scale around
  400); lambda blends engine score target with game result; MSE-style loss
  with exponent around 2.6 found good for Stockfish.
- **For Fork:** the most complete public description of design choices;
  read it for ideas, write Fork's own trainer or use bullet (MIT).
- Source: https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md
  (read via raw.githubusercontent.com). Repo license not seen on the
  fetched page (**UNVERIFIED**, presumed GPL like Stockfish; do not copy
  code either way). Verified 2026-10-23. Tag: **REFERENCE ONLY**.

### Chess Programming Wiki: NNUE page
- History (Nasu 2018 for Shogi, Stockfish NNUE 2020 / SF12), perspective
  accumulators, quantisation constants commonly QA=255, QB=64, SCALE=400 (as
  of 2024), SCReLU overflow handling, output buckets by piece count, king
  input buckets (bucket crossing forces refresh), Finny tables (accumulator
  cache per king bucket, credited to Finn Eggers / Koivisto), pairwise
  multiplication, lazy updates, Lizard SCReLU SIMD trick. States bullet is
  the most widely used trainer among top engines as of 2025. Threat inputs
  are not on the page.
- Source: https://www.chessprogramming.org/NNUE. Verified 2026-10-23.
  Dates for Finny tables and pairwise multiplication not given (UNVERIFIED).
  Tag: **REFERENCE ONLY**.

### bullet trainer (jw1912/bullet)
- Rust NNUE training library; CUDA, ROCm, Metal backends; **MIT license**.
  Examples go from (768 -> N)x2 -> 1 up to input buckets, output buckets
  and multi-layer nets. Data: loaders for Stockfish, Monty and Viridithas
  binpacks (viriformat recommended), plus a fast "ChessBoard" format that
  drops side-to-move/halfmove/castling. Text format
  `<FEN> | <score cp, white-relative> | <result 1/0.5/0>`. bullet-utils
  shuffles/interleaves. Docs advise: start with 768 inputs and widen the
  hidden layer (>=1024) before adding depth; do not copy Stockfish
  architectures without the data to support them.
- **For Fork:** strongest candidate for Phase 4 training. Using a trainer is
  allowed by Fork's rules (it is a tool, not an engine); log version in
  ORIGINALITY.md. Fork's net file format and inference code remain Fork's.
- Sources: https://github.com/jw1912/bullet, docs 0-contents, 1-basics,
  3-data. Verified 2026-10-23. Tag: **USE** (MIT tool). Note: whether TCEC
  counts a shared trainer against "uniqueness" is UNVERIFIED (see 8).

### Study of the Proper NNUE Dataset (arXiv 2412.17948, 2024-12-23)
- Tan, Watkinson Medina. Algorithm to generate and filter "quiet" positions
  for NNUE training; reports significant gains. Filtering details not on
  the abstract page (**UNVERIFIED**).
- Source: https://arxiv.org/abs/2412.17948. Verified 2026-10-23.
  Tag: **REFERENCE ONLY**.

### Lc0 transformer progress (blog 2024-02-28, Daniel Monroe)
- T78 conv baseline vs BT1..BT4. BT4: 191.3M params, 15 layers, embedding
  1024, FFN 1536, 32 heads, about +270 policy Elo over T78. Gains from
  learned attention bias (like +50% size), "smolgen" position-dependent
  attention (like +50% size for about 10% throughput), board-aware
  embedding. MoE/GLU did not help. Page later updated to point to the
  Chessformer ICLR 2026 paper as the citation.
- Source: https://lczero.org/blog/2024/02/transformer-progress/. Verified
  2026-10-23. Tag: **REFERENCE ONLY**.

### Correction history (Caissa, October 2023) - see techniques.md
- CPW: first introduced in Caissa in Oct 2023 and quickly adopted; gains grow
  with longer time controls. Source:
  https://www.chessprogramming.org/Static_Evaluation_Correction_History.
  Verified 2026-10-23. Tag: **REFERENCE ONLY**.

### Stockfish 17 (2024-09-06)
- New `NumaPolicy` option: automatic NUMA optimisation on large machines
  (typically dual-socket 100+ cores), up to 2.8x speedup measured; no
  benefit on consumer hardware. Notes Lc0 open data is essential for SF
  nets. +46 Elo vs SF16.
- **For Fork:** confirms NUMA awareness is worth real speed on TCEC-class
  hardware (Phase 6).
- Source: https://stockfishchess.org/blog/2024/stockfish-17/. Verified
  2026-10-23. Tag: **REFERENCE ONLY**.

---

## 7. Datasets: provenance summary

| Dataset | Labels from | License | Fork tag |
|---|---|---|---|
| ChessBench (searchless_chess) | Stockfish 16 | CC0 (Lichess parts) + CC-BY 4.0 | **OFF-LIMITS** for training |
| MAV data (2412.12119) | Stockfish (version not stated) | not released on page | **OFF-LIMITS** |
| Stockfish nnue-pytorch datasets (SF self-play, Lc0-rescored, mixed) | Stockfish and/or Lc0 | not stated on wiki page | **OFF-LIMITS** |
| HF linrock_relabel_* | rescored with an Lc0 net (some sets mixed with SF self-play) | not stated | **OFF-LIMITS** |
| Lc0 training data (storage.lczero.org) | Lc0 self-play | ODbL 1.0 / DbCL 1.0 | Legally reusable, but **OFF-LIMITS** under Fork's own-data rule |
| Lichess evaluations database | Stockfish in users' browsers | CC0 | **OFF-LIMITS** for training |
| Lichess standard game exports (moves only) | humans | CC0 | **USE** for opening/start positions and test books; strip `[%eval]` comments (their engine source UNVERIFIED) |
| Lichess puzzles | generation engine UNVERIFIED | CC0 | test only, after provenance check |

Sources: searchless_chess README, nnue-pytorch wiki "Training datasets",
lczero.org open-data blog (2021-06-14), TalkChess announcement
(2021-06-15), database.lichess.org. All opened 2026-10-23.

---

## 8. Competition context (TCEC)

- Official TCEC rules page (wiki.chessdom.org/Rules, last edited 2026-07-08):
  time controls 30'+3" for most leagues/cups/FRD, Premier Division 60'+6",
  Superfinal 120'+12"; engines must allow disabling internal book and
  pondering. Updates only between events. Verified 2026-10-23. Useful for
  `config/tcec.json`.
- Wikipedia (secondary source): engines run on Linux on identical hardware,
  pondering off, clone bans (DeusX in S13; Houdini, Fire, Rybka, Critter in
  S20). Verified on the page 2026-10-23, but secondary.
- **UNVERIFIED:** TCEC's current written rules on NNUE originality and
  training data (e.g. "two of three parts unique", "no Stockfish data")
  appear only in forum posts; the official rules page opened does not
  address them. Ask TCEC organisers directly before Phase 4.
- **UNVERIFIED:** current season hardware (core count, sockets, NUMA nodes).

---

## Research library (classic and foundational papers)

Older papers that Fork's design rests on, grouped by topic. Added 2026-10-23.
Every citation below was confirmed on a page that was actually opened (Crossref
DOI record, arXiv, publisher, author/institution page, or a Chess Programming
Wiki page giving the citation); see "Research library" in `sources.md`. Page
ranges for ICCA/ICGA Journal papers come from the Crossref records of the
journal's DOIs (prefix 10.3233/icg-). Summaries are in our own words. Items
not fully confirmed are under "Unverified" at the end.

Overlap with the rest of this file: none of these papers had an entry. Nasu
(2018) was only mentioned in passing in the CPW NNUE entry (section 6); it now
has a full entry below. The CPW Lazy SMP page was already used for
techniques.md section 7; it is summarised here, not repeated there.

Paywall note: "publisher page" means the DOI landing page. ScienceDirect,
Springer and science.org refused automated fetches (HTTP 403 or login
redirect), so open access was **not checked**; assume paywalled unless a free
copy is linked.

### Foundations

#### Shannon (1950): Programming a Computer for Playing Chess
- **Citation:** Claude E. Shannon, "XXII. Programming a computer for playing
  chess", *The London, Edinburgh, and Dublin Philosophical Magazine and Journal
  of Science*, Vol. 41, No. 314, pp. 256-275, March 1950.
  DOI 10.1080/14786445008521796.
- **Link:** https://doi.org/10.1080/14786445008521796 (publisher; access not
  checked). Free scan at the Computer History Museum:
  https://www.computerhistory.org/chess/doc-431614f453dde/
- **Summary:** Lays out the skeleton of every chess program: an evaluation
  function, minimax search of the game tree, and the choice between searching
  all moves to a fixed depth ("type A") or only plausible moves selectively
  ("type B"). Also argues that search should not stop in the middle of an
  exchange or other unstable situation (the seed of quiescence search).
- **What it means for Fork:** Conceptual base for Phase 3. Fork is a type A
  searcher that buys back selectivity with pruning/reductions; the "don't
  stop on unstable positions" rule is Fork's qsearch.
- **Phase:** 3. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Zobrist (1970): hashing for game playing
- **Citation:** Albert L. Zobrist, "A New Hashing Method with Application for
  Game Playing", Technical Report #88 (TR88), Computer Sciences Department,
  University of Wisconsin, Madison, 1970. Reprinted in *ICCA Journal*,
  Vol. 13, No. 2, pp. 69-73, June 1990 (DOI 10.3233/ICG-1990-13203).
- **Link:** https://minds.wisc.edu/items/992e8337-5597-4a51-89d3-3fbe3559201a
  (UW repository record). Free scanned PDF (image only, no text layer):
  https://research.cs.wisc.edu/techreports/1970/TR88.pdf
- **Summary:** Give every (piece, square) a fixed random bit string; a
  position's key is the XOR of the strings of its pieces, so a move updates
  the key with a couple of XORs instead of a full recompute. The report also
  covers catching retrieval errors with extra stored bits, trading error rate
  against table space.
- **What it means for Fork:** Fork's Position keys (Phase 1) and TT (Phase 3)
  already follow this. Pitfalls: include side to move, castling rights and the
  en-passant file (only when an ep capture is actually possible, or
  repetitions get missed); keep enough verification bits per TT entry; treat
  a TT move as untrusted until a legality check passes.
- **Phase:** 1, 3. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Knuth & Moore (1975): An Analysis of Alpha-Beta Pruning
- **Citation:** Donald E. Knuth, Ronald W. Moore, "An analysis of alpha-beta
  pruning", *Artificial Intelligence*, Vol. 6, No. 4, pp. 293-326, 1975.
  DOI 10.1016/0004-3702(75)90019-3.
- **Link:** https://doi.org/10.1016/0004-3702(75)90019-3 (publisher; access
  not checked).
- **Summary:** The formal treatment of alpha-beta: proves it correct and shows
  that with perfect move ordering it examines roughly the square root of the
  minimax tree (about b^(d/2) leaves instead of b^d). Introduces the
  classification of nodes into the three types later called PV, cut and all
  nodes.
- **What it means for Fork:** The square-root bound is only reached with good
  ordering, so every Phase 3 ordering heuristic (TT move, SEE-ordered
  captures, killers, history) exists to approach it. Fork's PV/non-PV and
  expected-cut-node logic comes from this node taxonomy.
- **Phase:** 3. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Slate & Atkin (1977): CHESS 4.5
- **Citation:** David J. Slate, Lawrence R. Atkin, "CHESS 4.5 - The
  Northwestern University chess program", in *Chess Skill in Man and
  Machine*, Springer, 1977, pp. 82-118 (DOI 10.1007/978-3-662-06239-5_4).
  Reprinted in *Computer Chess Compendium*, Springer, 1988, pp. 80-103
  (DOI 10.1007/978-1-4757-1968-0_9).
- **Link:** https://doi.org/10.1007/978-3-662-06239-5_4 (publisher; access
  not checked).
- **Summary:** Describes the program that made full-width brute-force search
  with iterative deepening the norm, together with 64-bit bitboards for piece
  sets and attacks and a transposition table. Searching depth 1, 2, 3, ...
  gives good move ordering for the next iteration and makes stopping on time
  natural.
- **What it means for Fork:** Fork's bitboard core (Phase 1) and its
  iterative-deepening driver (Phase 3, 5) descend from this design; time
  management (Phase 5) relies on being able to stop after any finished
  iteration.
- **Phase:** 1, 3, 5. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23
  (editor not shown on the opened record).

#### Campbell, Hoane & Hsu (2002): Deep Blue
- **Citation:** Murray Campbell, A. Joseph Hoane Jr., Feng-hsiung Hsu, "Deep
  Blue", *Artificial Intelligence*, Vol. 134, No. 1-2, pp. 57-83, January
  2002. DOI 10.1016/S0004-3702(01)00129-1.
- **Link:** https://doi.org/10.1016/S0004-3702(01)00129-1 (publisher; access
  not checked).
- **Summary:** System description of the machine that beat Kasparov in 1997:
  a software search on general-purpose processors handing the last plies to
  many custom chess chips, strongly non-uniform search driven by selective
  extensions (including a "dual credit" form of singular extensions), and an
  evaluation built from thousands of hardware features.
- **What it means for Fork:** Mostly history. Two lessons carry over:
  well-chosen extensions mattered as much as raw speed, and efficient
  parallel search over many processors is hard (Phase 6).
- **Phase:** 3, 6. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

### Search (Phase 3)

#### Schaeffer (1989): the history heuristic
- **Citation:** Jonathan Schaeffer, "The history heuristic and alpha-beta
  search enhancements in practice", *IEEE Transactions on Pattern Analysis
  and Machine Intelligence*, Vol. 11, No. 11, pp. 1203-1212, 1989.
  DOI 10.1109/34.42858.
- **Link:** https://doi.org/10.1109/34.42858 (publisher; access not checked).
- **Summary:** Moves that produce cutoffs anywhere in the tree earn a score
  that grows with the depth of the subtree they cut, and quiet moves are
  ordered by that score. The paper also measures how much each standard
  alpha-beta enhancement (TT, killers, history, aspiration and minimal
  windows, iterative deepening) contributes alone and combined, finding
  history and the TT do most of the work.
- **What it means for Fork:** Base of Fork's quiet-move ordering. Modern
  versions use bounded "gravity" updates with penalties for quiets that
  failed, plus continuation and capture history (techniques.md section 3).
  Pitfall: unbounded counters saturate and stop discriminating.
- **Phase:** 3. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Reinefeld (1983): NegaScout / principal variation search
- **Citation:** Alexander Reinefeld, "An Improvement to the Scout Tree Search
  Algorithm", *ICCA Journal*, Vol. 6, No. 4, pp. 4-14, December 1983.
  DOI 10.3233/ICG-1983-6402.
- **Link:** https://doi.org/10.3233/ICG-1983-6402 (publisher; access not
  checked). The free copy CPW links at top-5000.nl returned an HTML page, not
  the PDF (failed).
- **Summary:** Search the first move with the full window and every later move
  with a null window that only asks "does this beat the best so far?"; re-search
  with a real window only when that test fails high. With good ordering the
  cheap tests usually fail low, saving nodes over plain alpha-beta. (CPW
  quotes Breuker that the 1983 text has minor errors and that he cites
  Reinefeld's 1989 version.)
- **What it means for Fork:** This is Fork's PVS. Pitfalls: re-search at the
  right window and depth (drop the LMR reduction first), and carry the
  PV/non-PV flag into TT-cutoff and pruning decisions.
- **Phase:** 3. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Donninger (1993): null move pruning
- **Citation:** Chrilly (Christian) Donninger, "Null Move and Deep Search:
  Selective-Search Heuristics for Obtuse Chess Programs", *ICCA Journal*,
  Vol. 16, No. 3, pp. 137-143, September 1993. DOI 10.3233/ICG-1993-16304
  (Crossref carries the short title "Null Move and Deep Search").
- **Link:** https://doi.org/10.3233/ICG-1993-16304 (publisher; access not
  checked).
- **Summary:** Let the side to move "pass" and search the opponent's reply at
  reduced depth (reduction R, typically 2); if the score still reaches beta,
  cut the node, since a real move is almost always at least as good as
  passing. Argues that applying this recursively lets a simple, fast program
  reach much greater depth.
- **What it means for Fork:** Core Phase 3 pruning. Pitfalls: zugzwang
  (disable with only king and pawns, verify at high depth); never in check or
  twice in a row; the null move must update the Zobrist key, clear the ep
  square and keep the repetition history consistent.
- **Phase:** 3. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Heinz (1998): Extended Futility Pruning
- **Citation:** Ernst A. Heinz, "Extended Futility Pruning", *ICCA Journal*,
  Vol. 21, No. 2, pp. 75-83, June 1998. DOI 10.3233/ICG-1998-21202.
- **Link:** author's web preprint (free):
  https://people.csail.mit.edu/heinz/dt/node18.html
- **Summary:** At frontier nodes (one ply left), quiet moves whose static eval
  plus a margin cannot reach alpha are skipped; the paper extends this to
  pre-frontier nodes with a larger margin and adds "limited razoring" (a
  depth reduction) one ply further up, measuring node savings and tactical
  cost in DarkThought.
- **What it means for Fork:** Origin of Fork's futility/razoring margins
  (Phase 3); modern engines scale margins with depth and tune them by SPSA.
  Pitfalls: never prune checks or in-check nodes; keep mate scores out of
  margin arithmetic.
- **Phase:** 3. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Heinz (1999): Adaptive Null-Move Pruning
- **Citation:** Ernst A. Heinz, "Adaptive Null-Move Pruning", *ICCA
  Journal*, Vol. 22, No. 3, pp. 123-132, September 1999.
  DOI 10.3233/ICG-1999-22302.
- **Link:** https://doi.org/10.3233/ICG-1999-22302 (publisher; access not
  checked). CPW lists an author PostScript copy at
  people.csail.mit.edu/heinz/ps/adpt_null.ps.gz (not opened).
- **Summary:** Makes the null-move reduction depend on remaining depth (and
  material): R=3 far from the leaves, R=2 near them. This keeps most of the
  node savings of R=3 while losing less tactical accuracy.
- **What it means for Fork:** First step toward depth-dependent R; current
  practice grows R with depth and with (eval - beta). Tune by SPRT, don't
  copy constants.
- **Phase:** 3. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Buro (1995): ProbCut
- **Citation:** Michael Buro, "ProbCut: An Effective Selective Extension of
  the Alpha-Beta Algorithm", *ICCA Journal*, Vol. 18, No. 2, pp. 71-76, June
  1995. DOI 10.3233/ICG-1995-18202.
- **Link:** author's PDF (free): https://skatgame.net/mburo/ps/probcut.pdf
  (downloaded; its text layer was not readable with our tools).
- **Summary:** A shallow search result predicts the deep result well through
  a linear model, so if a shallow search says the value lies beyond beta by
  a sufficient margin, the deep search is skipped with a controlled error
  probability. Developed and measured in Othello (Logistello).
- **What it means for Fork:** Phase 3. Chess engines use a simplified form:
  try captures against a raised beta at reduced depth after a qsearch
  pre-check. Pitfall: the margin is tied to Fork's own eval scale; refit it
  whenever the evaluation changes (e.g. each new NNUE).
- **Phase:** 3. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Anantharaman, Campbell & Hsu (1990): Singular Extensions
- **Citation:** Thomas Anantharaman, Murray S. Campbell, Feng-hsiung Hsu,
  "Singular extensions", *Artificial Intelligence*, Vol. 43, No. 1,
  pp. 99-109, April 1990. DOI 10.1016/0004-3702(90)90073-9. (The longer
  title with the subtitle "Adding selectivity to brute-force searching" was
  not shown on any opened page; see Unverified.)
- **Link:** https://doi.org/10.1016/0004-3702(90)90073-9 (publisher; access
  not checked).
- **Summary:** A move is "singular" when it is clearly better than every
  alternative; searching such moves one ply deeper finds tactics a
  fixed-depth search misses. Describes the method as used in the Deep
  Thought / Deep Blue line.
- **What it means for Fork:** Phase 3, in the modern TT-based form: if the TT
  move has a deep enough lower bound, search the other moves at reduced depth
  with a null window just below it; if all fail low, extend (otherwise
  multi-cut or negative extension). Pitfalls: the verification search must
  exclude the TT move without overwriting its TT entry, and total extensions
  must be capped to avoid explosion.
- **Phase:** 3. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

### Parallel search (Phase 6)

#### Hyatt (1997): The Dynamic Tree-Splitting Parallel Search Algorithm
- **Citation:** Robert M. Hyatt, "The Dynamic Tree-Splitting Parallel Search
  Algorithm", *ICCA Journal*, Vol. 20, No. 1, pp. 3-19, March 1997.
  DOI 10.3233/ICG-1997-20102.
- **Link:** https://doi.org/10.3233/ICG-1997-20102 (publisher; access not
  checked). Author's HTML copy at craftychess.com/hyatt/search.html failed
  (expired TLS certificate).
- **Summary:** Processors share the whole tree; an idle processor may pick a
  split point at any node of any active subtree, not just where its parent
  is working, and help search the remaining moves there. Built for Cray
  Blitz on shared-memory Crays, it gave the best reported speedups of its
  time.
- **What it means for Fork:** Background for Phase 6. DTS is very hard to do
  in a recursive search, and modern engines use Lazy SMP instead. CPW also
  lists a 1994 DTS item with a different title; see Unverified.
- **Phase:** 6. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Lazy SMP (forum sources; no peer-reviewed paper found)
- **What exists:** The CPW page (https://www.chessprogramming.org/Lazy_SMP)
  credits **Julien Marcel** with the name ("Lazy SMP", TalkChess,
  2012-12-27), then **Daniel Homan** ("Lazy SMP, part 2", 2013-01-12;
  "part 3", 2013-03-09; "Lazy SMP and Work Sharing", 2013-07-03) and Martin
  Sedlak (Cheng pseudo-code, 2015-02-02); traces the shared-hash idea to
  Vincent David's 1993 thesis; and notes Stockfish 7 (January 2016) moved
  from YBW to Lazy SMP. CPW lists **no peer-reviewed paper** measuring it;
  the only academic item is Emil Fredrik Ostensen's 2016 M.Sc. thesis "A
  Complete Chess Engine Parallelized Using Lazy SMP" (University of Oslo),
  which was not opened (repository link redirected). **The evidence is
  essentially forum posts.**
- **Primary post opened:** Daniel Homan, "Lazy SMP, part 2", TalkChess,
  2013-01-12 (https://talkchess.com/viewtopic.php?t=46858). In EXchess,
  threads search the same root with the same window and share only the
  hash table. In a 6s+0.1s gauntlet he reports about +70 Elo for 2 threads
  and +140 for 4, versus about +105 for one thread at double time, although
  time to fixed depth improved by less than 2x. He attributes the gap to
  some threads reaching an extra ply and to per-thread history/killer tables.
- **Summary:** Every thread runs the full iterative-deepening search on the
  same position, cooperating only through the shared TT; differences between
  threads (depth offsets, timing noise, private heuristics) spread the work.
  Simple to build and scales well in Elo even though time-to-depth speedup
  looks poor.
- **What it means for Fork:** The Phase 6 design. Pitfalls: (1) measure Elo
  per thread count, not time to depth; (2) the TT must survive torn
  reads/writes (verify keys and moves); (3) history, killers and NNUE
  accumulators are per thread, the TT is the only shared mutable state;
  (4) choose the reported move consistently (main thread or thread voting);
  (5) at TCEC scale (about 512 threads) NUMA placement and TT initialisation
  dominate (see the SF17 NumaPolicy entry in section 6).
- **Phase:** 6, 8. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23 (CPW
  page and one Homan post; other posts only as listed by CPW).

### Evaluation and learning (Phase 4)

#### Nasu (2018): NNUE for computer shogi (original NNUE paper)
- **Citation:** Yu Nasu (Ziosoft Computer Shogi Club), "Efficiently
  Updatable Neural-Network-based Evaluation Functions for Computer Shogi",
  April 28, 2018. Japanese text with English title and abstract, part of the
  appeal document of the shogi program "the end of genesis T.N.K.evolution
  turbo type D" for the 28th World Computer Shogi Championship. Japanese
  title (wording as in the author's repo README; the PDF's Japanese text
  could not be extracted cleanly): 高速に差分計算可能なニューラルネットワーク型将棋評価関数.
- **Links:** original PDF (free):
  https://www.apply.computer-shogi.org/wcsc28/appeal/the_end_of_genesis_T.N.K.evolution_turbo_type_D/nnue.pdf
  (English title, author, affiliation, date and abstract read from it).
  Author's repo https://github.com/ynasu87/nnue (a YaneuraOu fork, **GPLv3**).
  English translation: https://github.com/asdfjkl/nnue (nnue_en.pdf;
  translator not named, license not stated).
- **Summary:** Proposes a nonlinear neural-network evaluation that runs fast
  on a CPU: a very wide, sparse first layer over king-relative piece features
  whose output (the accumulator) is updated incrementally move by move,
  followed by small integer layers. Claims speed comparable to the linear
  evaluations then standard in shogi.
- **What it means for Fork:** The root of Fork's Phase 4 design (incremental
  accumulator, king-relative inputs, integer inference). The ideas are free
  to use; the ynasu87/nnue **code** is GPLv3 and **OFF-LIMITS** for copying,
  and the translation has no stated license (read, don't copy). Later
  chess-specific developments: see the CPW NNUE and nnue-pytorch entries in
  section 6.
- **Phase:** 4. **Tag:** REFERENCE ONLY (paper); repo code OFF-LIMITS.
  **Verified:** 2026-10-23.

#### Baxter, Tridgell & Weaver: KnightCap and TDLeaf(lambda)
- **Citations:**
  1. J. Baxter, A. Tridgell, L. Weaver, "TDLeaf(lambda): Combining Temporal
     Difference Learning with Game-Tree Search", *Australian Journal of
     Intelligent Information Processing Systems*, Vol. 5, No. 1, pp. 39-43,
     Autumn 1998 (also Proc. ACNN'98, pp. 168-172). arXiv cs/9901001.
  2. J. Baxter, A. Tridgell, L. Weaver, "KnightCap: A chess program that
     learns by combining TD(lambda) with game-tree search", *Machine
     Learning: Proceedings of the Fifteenth International Conference (ICML
     '98)*, Madison, July 1998, pp. 28-36. arXiv cs/9901002.
  3. J. Baxter, A. Tridgell, L. Weaver, *Machine Learning*, Vol. 40, No. 3,
     pp. 243-263, 2000, DOI 10.1023/A:1007634325138: title **not confirmed**
     (see Unverified).
- **Links:** https://arxiv.org/abs/cs/9901001 and
  https://arxiv.org/abs/cs/9901002 (free).
- **Summary:** TDLeaf applies temporal-difference learning to the leaf of the
  principal variation rather than to the root position, so the program
  learns the evaluation that its search actually uses. KnightCap tuned its
  weights this way while playing on an internet chess server; the authors
  report a climb from about 1650 to about 2150 in 308 games.
- **What it means for Fork:** An early instance of Fork's self-play-only
  learning (Phase 4). Lesson: learn from the positions search really
  evaluates (quiet leaves), the same reason NNUE data is filtered to quiet
  positions. Modern practice fits offline to self-play scores/results
  (Texel-style or NNUE training) rather than online TD.
- **Phase:** 4. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23 (items 1-2
  fully; item 3 without title).

#### Lai (2015): Giraffe
- **Citation:** Matthew Lai, "Giraffe: Using Deep Reinforcement Learning to
  Play Chess", MSc dissertation, arXiv:1509.01549 (v1 2015-09-04).
- **Link:** https://arxiv.org/abs/1509.01549 (free).
- **Summary:** A chess engine whose evaluation is a neural network learned
  through TD-Leaf-style self-play with very little hand-coded knowledge; the
  network also learns features and patterns rather than just tuning given
  terms. The author reports evaluation quality comparable to strong
  conventional engines on test positions, with slow search as the limit.
- **What it means for Fork:** Evidence that a self-taught evaluation can get
  far (supports Fork's own-data rule), and an illustration of why a full
  network per node is too slow for alpha-beta, which NNUE's incremental
  update solves.
- **Phase:** 4. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Silver et al. (2017/2018): AlphaZero
- **Citations:**
  1. D. Silver, T. Hubert, J. Schrittwieser, I. Antonoglou, M. Lai, A. Guez,
     M. Lanctot, L. Sifre, D. Kumaran, T. Graepel, T. Lillicrap, K. Simonyan,
     D. Hassabis, "Mastering Chess and Shogi by Self-Play with a General
     Reinforcement Learning Algorithm", arXiv:1712.01815, 2017-12-05.
  2. Same 13 authors, "A general reinforcement learning algorithm that masters
     chess, shogi, and Go through self-play", *Science*, Vol. 362, No. 6419,
     pp. 1140-1144, 2018-12-07. DOI 10.1126/science.aar6404.
- **Links:** https://arxiv.org/abs/1712.01815 (free);
  https://doi.org/10.1126/science.aar6404 (publisher returned 403; access not
  checked).
- **Summary:** One deep residual network outputs a move policy and a value,
  is trained purely from self-play starting from random play, and guides
  Monte-Carlo tree search in place of alpha-beta. It beat the strongest
  programs of the day in chess, shogi and Go with no game knowledge beyond
  the rules.
- **What it means for Fork:** The blueprint Lc0 follows, so it is context for
  Phase 7/8 (what Fork faces at TCEC), not Fork's architecture. The idea that
  transfers is tabula-rasa self-play producing all training data, which is
  exactly Fork's originality rule.
- **Phase:** 4, 7. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Schrittwieser et al. (2020): MuZero
- **Citation:** J. Schrittwieser, I. Antonoglou, T. Hubert, K. Simonyan,
  L. Sifre, S. Schmitt, A. Guez, E. Lockhart, D. Hassabis, T. Graepel,
  T. Lillicrap, D. Silver, "Mastering Atari, Go, chess and shogi by
  planning with a learned model", *Nature*, Vol. 588, No. 7839, pp. 604-609,
  2020-12-23. DOI 10.1038/s41586-020-03051-4. Preprint arXiv:1911.08265
  (2019-11-19).
- **Links:** https://arxiv.org/abs/1911.08265 (free);
  https://doi.org/10.1038/s41586-020-03051-4 (publisher; access not checked).
- **Summary:** Extends AlphaZero by not giving the search the rules: the
  network learns its own hidden-state dynamics, reward and value, and MCTS
  plans inside that learned model. Matches AlphaZero on board games and also
  handles Atari.
- **What it means for Fork:** No direct use; Fork has an exact, fast move
  generator, so a learned model adds nothing. Context only.
- **Phase:** 4. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

### Tablebases (Phase 3-4)

#### Thompson (1986): Retrograde Analysis of Certain Endgames
- **Citation:** Ken Thompson, "Retrograde Analysis of Certain Endgames",
  *ICCA Journal*, Vol. 9, No. 3, pp. 131-139, September 1986.
  DOI 10.3233/ICG-1986-9302.
- **Link:** free PDF listed by CPW (reachable, not read in full):
  https://pdos.csail.mit.edu/~rsc/thompson86endgame.pdf
- **Summary:** Builds complete endgame databases backwards from the final
  results: label positions one move from a known outcome, then the next
  layer, until nothing changes, giving exact distance to mate for every
  position of a material combination. Produced new results in five-piece
  endings.
- **What it means for Fork:** The method behind every table Fork will probe
  (Phase 3). Fork won't generate production tables, but a tiny 3-piece
  retrograde generator makes a cheap test oracle for the probing code.
- **Phase:** 3, 4. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Nalimov, Haworth & Heinz (2000): Space-efficient indexing of endgame tables
- **Citation:** E. V. Nalimov, G. McC. Haworth, E. A. Heinz, "Space-Efficient
  Indexing of Chess Endgame Tables", *ICGA Journal*, Vol. 23, No. 3,
  pp. 148-162, September 2000. DOI 10.3233/ICG-2000-23304.
- **Link:** https://doi.org/10.3233/ICG-2000-23304 (publisher; access not
  checked). University of Reading repository copy (centaur.reading.ac.uk/4562)
  blocked by a bot wall.
- **Summary:** Shows how to map positions to compact table indices by
  removing symmetric duplicates, impossible king placements and
  interchangeable placements of identical pieces, which shrinks
  distance-to-mate tables greatly and made the Nalimov tables practical.
- **What it means for Fork:** Background: Fork uses Syzygy WDL/DTZ, not
  Nalimov DTM. It explains why probing depends on exact canonicalisation
  (colour flip, mirroring), which Fork's probing tests must exercise.
- **Phase:** 3, 4. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Syzygy tablebases (Ronald de Man): format, generator and probing code
- **What:** https://github.com/syzygy1/tb holds the generator (rtbgen,
  rtbgenp, verifiers, tbcheck). Its README is the format documentation that
  matters for an engine: `.rtbw` = WDL including 50-move-rule information,
  two-sided, the only files touched during search; `.rtbz` = DTZ/DTZ50
  (moves to the next capture or pawn move), single-sided, needed only at the
  root. Sizes: about 68.2 GB WDL + 81.9 GB DTZ for 6 pieces; 378 MB + 561 MB
  up to 5 pieces. DTZ may be off by one unless tables were generated with
  `-p`, and the original tables were not.
- **Licenses (checked):** generator repo **GPL-2.0** (GitHub license
  metadata). Probing code lives in https://github.com/syzygy1/probetool,
  whose README states the access code's license as essentially "do whatever
  you want with it" (no GitHub license metadata). Fathom (MIT) is the usual
  engine-side wrapper (tools.md).
- **What it means for Fork:** Phase 3: WDL in search, DTZ at the root only.
  Pitfalls: probe WDL only with halfmove clock 0 and no castling rights;
  handle cursed wins / blessed losses (results decided by the 50-move rule)
  explicitly; use DTZ at the root to keep making progress. Log whichever
  probing code is used in ORIGINALITY.md; run the GPL generator only as an
  external tool.
- **Phase:** 3, 4, 8. **Tag:** USE (tables, permissive probing code);
  generator code REFERENCE ONLY (GPL-2.0). **Verified:** 2026-10-23.

### Testing and tuning (Phase 8)

#### Wald (1945): Sequential Tests of Statistical Hypotheses
- **Citation:** A. Wald, "Sequential Tests of Statistical Hypotheses", *The
  Annals of Mathematical Statistics*, Vol. 16, No. 2, pp. 117-186, June
  1945. DOI 10.1214/aoms/1177731118.
- **Link:** https://doi.org/10.1214/aoms/1177731118 (Project Euclid; fetch
  returned an empty page, access not checked).
- **Summary:** Introduces the sequential probability ratio test: after each
  observation add the log-likelihood ratio of H1 over H0 and stop as soon as
  the running sum crosses one of two bounds set by the chosen error rates
  (alpha, beta). On average this needs far fewer samples than a fixed-size
  test with the same error rates.
- **What it means for Fork:** Basis of every Phase 8 patch test. Fork should
  run the pentanomial GSPRT (Fishtest entry below) rather than Wald's
  original form. Pitfall: stopping by hand, or peeking and restarting, voids
  the error guarantees.
- **Phase:** 8. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Spall (1992): SPSA
- **Citation:** J. C. Spall, "Multivariate stochastic approximation using a
  simultaneous perturbation gradient approximation", *IEEE Transactions on
  Automatic Control*, Vol. 37, No. 3, pp. 332-341, March 1992.
  DOI 10.1109/9.119632.
- **Link:** author's free PDF https://www.jhuapl.edu/spsa/PDF-SPSA/Spall_TAC92.pdf;
  SPSA site https://www.jhuapl.edu/spsa/ (maintained by Spall, JHU APL).
- **Summary:** Estimates a gradient from just two noisy measurements per step,
  however many parameters there are, by perturbing all parameters at once
  with random +/- signs. Gives convergence conditions on the step-size and
  perturbation-size sequences; the SPSA site notes that gain constants still
  need some trial-and-error.
- **What it means for Fork:** The standard way to tune many search constants
  with real games (OpenBench/Fishtest SPSA, Phase 8). Pitfalls: scale
  parameters so one perturbation size fits all; tune near the target time
  control (TCEC is long); always confirm tuned values with an SPRT.
- **Phase:** 8. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Coulom: BayesElo
- **What:** Remi Coulom's Elo estimator, https://www.remi-coulom.fr/Bayesian-Elo/.
  Maximum-likelihood Bradley-Terry ratings computed with Hunter's
  minorization-maximization algorithm (the page cites D. R. Hunter, "MM
  Algorithms for Generalized Bradley-Terry Models", *Annals of Statistics*
  32(1), DOI 10.1214/aos/1079120141, and Zermelo 1929). Models first-move
  advantage and draws with two fitted parameters (page: eloAdvantage about
  32.8, eloDraw about 97.3, fitted on 29,610 WBEC games) and uses a prior that
  pulls ratings together. GPL source; last version 2010.03.31. No journal
  paper describes BayesElo itself.
- **What it means for Fork:** Rates Phase 8 gauntlets/round robins (alongside
  Ordo, tools.md). BayesElo's scale differs from the logistic Elo of SPRT
  tools, so never compare numbers across tools. Run it as an external GPL
  program; never link it.
- **Phase:** 8. **Tag:** USE (external tool). **Verified:** 2026-10-23.

#### Coulom (2012): CLOP
- **Citation:** Remi Coulom, "CLOP: Confident Local Optimization for Noisy
  Black-Box Parameter Tuning", in *Advances in Computer Games* (ACG 13),
  Lecture Notes in Computer Science, Springer, 2012, pp. 146-157.
  DOI 10.1007/978-3-642-31866-5_13.
- **Links:** paper PDF (free) https://www.remi-coulom.fr/CLOP/CLOP.pdf; page
  https://www.remi-coulom.fr/CLOP/ (software 0.0.9; **license not stated**).
- **Summary:** Fits a weighted local quadratic model of win rate as a function
  of the parameters, discarding samples that are confidently worse than the
  average so the search concentrates on the promising region; designed for
  very noisy game outcomes. Reports beating the other tested methods on
  smooth problems.
- **What it means for Fork:** A Phase 8 alternative to SPSA for a handful of
  parameters; SPSA scales better and is what OpenBench supports, so CLOP is a
  fallback. Don't adopt the CLOP software until its license is known.
- **Phase:** 8. **Tag:** REFERENCE ONLY. **Verified:** 2026-10-23.

#### Fishtest and OpenBench statistical methodology
- **Fishtest:** wiki page "Fishtest Mathematics"
  (https://github.com/official-stockfish/fishtest/wiki/Fishtest-Mathematics).
  Uses a **generalized SPRT** (unknown parameters replaced by maximum
  likelihood estimates) on the **pentanomial** distribution of game-pair
  outcomes (LL, LD, DD/WL, WD, WW), which the page says saves substantial
  resources versus a trinomial W/D/L model because each opening is played
  with both colours. Bounds are in **normalized Elo**, so expected test
  length depends only on the bounds, not on draw rate or book. The math is
  in PDFs by Michel Van den Bergh, e.g. "Comments on Normalized Elo"
  (https://www.cantate.be/Fishtest/normalized_elo_practical.pdf, opened,
  author shown on the PDF); the GSPRT reference (Liu et al.,
  stat.columbia.edu) was not opened.
- **OpenBench:** wiki "SPRT and Fixed-Game Workloads" defines `Bounds`
  [elo0, elo1], `Confidence` (type I/II errors, 0.05 suggested) and
  `Workload Size` in game pairs. `OpenBench/stats.py` (GPL-3.0 header) says
  its PentanomialSPRT is "taken directly from Fishtest", implements the
  normalized-Elo document, and keeps a trinomial SPRT as well.
- **What it means for Fork:** Phase 8 tests should use paired openings,
  pentanomial GSPRT and normalized-Elo bounds, so test cost stays
  predictable as draw rates rise at long time controls. Pitfalls: count
  crashes and time losses as results, never drop them; logistic-Elo and
  normalized-Elo bounds are different scales.
- **Phase:** 8. **Tag:** REFERENCE ONLY (methodology); OpenBench itself as an
  external tool: USE (GPL-3.0, outside Fork; see tools.md). **Verified:**
  2026-10-23.

### Unverified

- **Hyatt (1994), "The DTS high-performance parallel tree search
  algorithm":** CPW lists it under 1994 with no venue; Hyatt's own page
  failed (expired TLS certificate). Venue, date and its relation to the 1997
  ICCA paper are **not confirmed**. Use the verified 1997 citation above.
- **Baxter, Tridgell & Weaver, *Machine Learning* 40(3):243-263 (2000):**
  authors, volume, issue, pages and year confirmed (Crossref); the **title**
  is not (Crossref record has none, Springer redirected to a login). It is
  often given as "Learning to Play Chess Using Temporal Differences".
- **Lazy SMP primary sources:** Julien Marcel's 2012 post, Homan's part 3 and
  "Work Sharing" posts, and Ostensen's 2016 M.Sc. thesis are known only from
  the CPW listing. No peer-reviewed paper measuring Lazy SMP was found.
- **Nasu (2018) translation:** translator of github.com/asdfjkl/nnue not named
  on the repo page (CPW separately lists a 2021 forum post "Translation of Yu
  Nasu's NNUE paper" by Dominik Klein, without linking it to that repo);
  license not stated.
- **Anantharaman et al. subtitle** ("Adding selectivity to brute-force
  searching") and **Slate & Atkin's book editor** (P. W. Frey): from common
  usage, not shown on any opened page.
- **Licenses:** CLOP software license and Fishtest repository license were
  not found.
