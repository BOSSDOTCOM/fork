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
