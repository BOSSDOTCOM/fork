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
  so the code license was open; re-checked 2026-10-24: GitHub API reports
  **AGPL-3.0** for CSSLab/maia3 (code only; weights are covered by the
  model card). Tag: **REFERENCE ONLY**.

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
  licenses not on the abstract page. Re-checked 2026-10-24: GitHub API
  reports **Apache-2.0** for the waterhorse1/ChessGPT repo; the dataset's
  own terms were not checked (**UNVERIFIED**, not opened).
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
- **Feature sets:** "A" = piece x colour x square. HalfKP crosses every
  own-king square with every non-king piece on every square: no king
  features, full refresh on king move. HalfKA adds kings. HalfKAv2 merges
  both kings into one "king" piece slot (somewhat smaller). HalfKAv2_hm
  mirrors horizontally so the own king is on files e-h, halving the king
  buckets.
- **Threat features (Full_Threats):** attacker-piece/target-piece pairs from
  each side's perspective; redundant pairs dropped (e.g. king-king, attacks
  on kings, duplicates); stored as int8, widened to int16 when accumulated;
  kept in a separate accumulator; only refreshed when the king crosses the
  d/e file boundary. PP_3Wide: unordered pawn pairs on same or adjacent
  files (removes pawn-pawn threats from the threat set).
- **Factorisers:** training-only "virtual" features (e.g. piece-square
  ignoring king) that share learning across king buckets; folded into real
  weights after training so inference cost is unchanged; mostly help early.
- **Layer stacks / output buckets:** several sub-networks chosen by the
  piece count; implemented as one wide layer and gathered.
- **Quantisation:** feature transformer int16 accumulation, clipped and
  narrowed to int8; hidden weights int8 with a power-of-two scale (which
  bounds the largest representable weight); powers-of-two scaling so
  divisions are shifts.
- **SIMD:** AVX2 16 int16 lanes / 16 registers (32 on AVX-512); int8 dense
  layers via multiply-add into int32; VNNI fuses it; first dense layer is
  sparse (mostly zeros) so sparse kernels pay off.
- **Loss:** cp scores mapped to win probability with a sigmoid; lambda
  blends engine score target with game result; an MSE-style loss with an
  exponent above 2 found good for Stockfish. (Exact values deliberately
  not recorded, owner 2026-10-28.)
- **For Fork:** the most complete public description of design choices;
  read it for ideas, write Fork's own trainer or use bullet (MIT).
- Source: https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md
  (read via raw.githubusercontent.com). Repo license not seen on the
  fetched page; re-checked 2026-10-24: GitHub API reports **GPL-3.0** for
  official-stockfish/nnue-pytorch (do not copy code either way). Verified 2026-10-23. Tag: **REFERENCE ONLY**.

### Chess Programming Wiki: NNUE page
- History (Nasu 2018 for Shogi, Stockfish NNUE 2020 / SF12), perspective
  accumulators, commonly used quantisation and output-scale constants (not
  recorded here, owner 2026-10-28), SCReLU overflow handling, output
  buckets by piece count, king
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
  hidden layer substantially before adding depth; do not copy Stockfish
  architectures without the data to support them.
- **For Fork:** strongest candidate for Phase 4 training. Using a trainer is
  allowed by Fork's rules (it is a tool, not an engine); log version in
  ORIGINALITY.md. Fork's net file format and inference code remain Fork's.
- Sources: https://github.com/jw1912/bullet, docs 0-contents, 1-basics,
  3-data. Verified 2026-10-23. Tag: **USE** (MIT tool). Note: whether TCEC
  counts a shared trainer against "uniqueness" is UNVERIFIED (see 8).

### Study of the Proper NNUE Dataset (arXiv 2412.17948, 2024-12-23)
- Tan, Watkinson Medina. Algorithm to generate and filter "quiet" positions
  for NNUE training; reports significant gains. Filter (resolved
  2026-10-28 from the paper, nnue-design.md §6.5): drops positions in
  check and positions whose static eval differs from the quiescence or
  search score by more than a margin, and aims at a balanced eval
  distribution. Evidence is weak for chess: a Xiangqi study with no SPRT
  and no ablation.
- Source: https://arxiv.org/abs/2412.17948. Verified 2026-10-23.
  Tag: **REFERENCE ONLY**.

### Lc0 transformer progress (blog 2024-02-28, Daniel Monroe)
- Convolutional baseline vs a series of transformer nets; the largest
  (an order of magnitude more parameters than any NNUE) gained about +270
  policy Elo over the convolutional baseline. Gains from
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
| Lichess standard game exports (moves only) | humans | CC0 | **USE** for opening/start positions and test books; strip `[%eval]` comments (Stockfish via fishnet, verified 2026-10-24) and BOT-account games |
| Lichess puzzles | Stockfish NNUE at 40 meganodes (verified 2026-10-24) | CC0 | **OFF-LIMITS** for training; test-suite use is an owner decision |

Full per-source evaluation (2026-10-24): [training-data.md](training-data.md);
statuses: [data-policy.md](data-policy.md).

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
- Current hardware, resolved 2026-10-24 from
  https://wiki.chessdom.org/TCEC_Season_Further_information: CPU server
  (S28 onward) 2x AMD EPYC 9754, 256 cores / 512 threads (two sockets),
  768 GiB DDR5, Ubuntu 22.04; GPU server 2x EPYC 9175F + 8x RTX 5090. The
  page does not give the NUMA node count or NPS-per-socket settings:
  **UNVERIFIED** (NUMA topology not published).

---

## 9. Heuristic-discovery tool: method references (idea 23, deliverable 8c)

Added 2026-10-26 for the pilot of the heuristic-discovery loop (ideas.md
idea 23; DESIGN.md §5.2, deliverable 8c). The owner named these three works
as models for the loop. Every detail below was read in the source itself:
the arXiv PDFs, the Nature PDF and its Supplementary Information, and the
publisher and Crossref metadata. Each claim gives the section or page it
came from. Pages are the numbers printed on the page (arXiv PDFs: the PDF
page; Nature: the journal pages 468-475; the Nature Methods section sits on
the online-only pages after p. 475; the Supplementary Information is cited
by appendix).

**Tag for all three: REFERENCE ONLY, for ideas.** They are method references
for Fork's own orchestrator, program database and evaluator. Released code
is never read for implementation. For this entry only the GitHub licence
field and README prose were opened, never a code file. None of the three
works deals with chess engines or with noisy, match-based fitness. Their
evaluators score a candidate directly (a set size, a bin count, a
simulator), so the statistics of Fork's funnel (proxies, then SPRT) are
Fork's own design, not taken from these papers.

### AlphaEvolve: A coding agent for scientific and algorithmic discovery (Google DeepMind white paper; arXiv 2506.13131v1, 2025-06-16)
- **Citation:** A. Novikov, N. Vũ, M. Eisenberger, E. Dupont, P.-S. Huang,
  A. Z. Wagner, S. Shirobokov, B. Kozlovskii, F. J. R. Ruiz, A. Mehrabian,
  M. P. Kumar, A. See, S. Chaudhuri, G. Holland, A. Davies, S. Nowozin,
  P. Kohli, M. Balog (18 authors, Google DeepMind), "AlphaEvolve: A coding
  agent for scientific and algorithmic discovery", white paper,
  arXiv:2506.13131 [cs.AI], v1 submitted 2025-06-16 (the only version
  listed on 2026-10-26). DOI 10.48550/arXiv.2506.13131. Neither the arXiv
  page nor the PDF names a journal or conference.
- **Links:** https://arxiv.org/abs/2506.13131 (PDF
  https://arxiv.org/pdf/2506.13131). Google DeepMind also hosts a copy:
  https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf
  (HTTP Last-Modified 2025-06-18). After whitespace normalisation, its
  text matches arXiv v1 word for word, apart from the arXiv stamp. The
  announcement post is dated 2025-05-14:
  https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/.
  **UNVERIFIED:** whether the white paper released with that post in May
  2025 differed from v1. That earlier file was not available to compare.
- **What it is:** an evolutionary coding agent. LLMs propose edits to marked
  parts of a program, automatic evaluators score the results, and a program
  database chooses which programs the LLMs see next. It was applied to
  tensor decompositions for matrix multiplication, to over 50 mathematical
  construction problems and to Google infrastructure: a data-centre
  scheduling heuristic, kernels, a TPU circuit and attention code.
- **Method components (as read):**
  - *Loop* (§2, Fig. 2, p4): each step samples a parent program and some
    "inspiration" programs from the database, builds a prompt and asks an
    LLM for a diff. The diff is applied to make a child program, the child
    is evaluated, and it is stored with its results. The system runs as an
    asynchronous pipeline of a controller, LLM samplers and evaluation
    nodes. It is tuned for throughput, to get the most ideas proposed and
    evaluated within an overall compute budget (§2.6, p8).
  - *Evolvable regions* (§2.1, p4-5): the user marks blocks with
    EVOLVE-BLOCK start and end comment markers. Code inside a block is the
    initial solution; the rest is a fixed skeleton that connects the
    evolved parts to the evaluation function. The initial code must be
    complete but may be trivial (e.g. functions returning constants). The
    evaluation function maps a solution to a dictionary of scalar metrics,
    which by convention are maximised (p3-4).
  - *Prompting* (§2.2, p5): each prompt holds several earlier solutions
    sampled from the database, plus instructions on how to change one of
    them. The options are:
    - explicit context: the problem text, equations, code or literature;
    - stochastic formatting: alternative template wordings, picked by
      configured probabilities, for diversity;
    - rendered evaluation results: a program, its output and its scores;
    - meta-prompt evolution: instructions written by the LLM itself and
      co-evolved in a separate database.

    The example prompt (Fig. 3, p6) lists prior programs with their scores,
    then the current program to improve.
  - *Output format* (§2.3, p7): edits come as SEARCH/REPLACE diff blocks
    against the current program. When the code is very short, or a full
    rewrite suits better, the system can instead ask for the whole block.
    The paper gives no ratio of diffs to rewrites.
  - *Models* (p7): an ensemble of Gemini 2.0 Flash and Gemini 2.0 Pro.
    Flash is fast and supplies the volume of candidates; Pro adds occasional
    higher-quality suggestions.
  - *Evaluation* (§2.4, p7-8):
    - an optional **evaluation cascade**, labelled "hypothesis testing":
      user-defined test stages of rising difficulty, where a candidate
      reaches the next stage only if its results on all earlier stages are
      promising enough. Candidates first run at small scale, so faulty
      programs drop out early.
    - **LLM-generated feedback**: separate LLM calls grade properties that
      are hard to code into the evaluator, such as simplicity. The grades
      are added to the scores or used to discard candidates that fail a
      criterion.
    - **Parallelised evaluation**: the paper says spending on the order of
      100 compute-hours per candidate is feasible, with the work spread
      asynchronously over an evaluation cluster.
  - *Multiple scores* (p8): several metrics can be optimised together. The
    authors report that this often improves the one metric they care about,
    and attribute it to more varied high scorers appearing in prompts.
  - *Program database* (§2.5, p8): stores every solution with its scores
    and outputs, aiming to bring earlier ideas back while balancing
    improvement against diversity. The paper says the database algorithm is
    inspired by a combination of MAP-Elites (citing Mouret & Clune,
    arXiv:1504.04909) and island-based population models (citing FunSearch
    and Tanese 1989). **Not described:** the feature dimensions, the cells,
    the number of islands, any migration or reset rule, or how parents and
    inspirations are chosen. The paper gives no database hyperparameters.
  - *Seeding and staged heuristics* (§3.1, p10; §3.2, p12): most
    matrix-multiplication results started from a simple initial program,
    but for some targets seeding it with the authors' own ideas helped. For
    the mathematics problems, each generation evolved a search heuristic
    with a fixed time budget (e.g. 1000 s) that started from the best
    construction found by the previous best heuristic. Final results often
    came from a sequence of different heuristics.
  - *Infrastructure heuristic* (§3.3.1, p13-14), the closest case to
    Fork's: a machine-scoring function for the Borg scheduler. Evolution
    started from the function then in production, with feedback from a
    simulator run on historical workload snapshots. Generalisation was
    checked on an unseen test set of recent workloads. After rollout,
    fleet-wide measurements confirmed the simulator's results (on average
    0.7% of fleet compute recovered). The authors chose the code heuristic
    over a deep-RL approach for interpretability, debuggability,
    predictability and ease of deployment.
  - *Ablations* (§4, Fig. 8, p17-18; tensor decomposition and kissing
    numbers): in the plotted curves, each variant did worse than the full
    method:
    - "no evolution": always prompting with the initial program;
    - no context in the prompt;
    - no meta-prompt evolution;
    - no full-file evolution: only the loss function evolved;
    - a single small LLM.
  - *Budget and stopping:* no stopping rule is given beyond the compute
    budget; the ablation curves are plotted against the fraction of the
    budget used (p18). Table 1 (p2) compares typical scale with FunSearch:
    thousands of LLM samples suffice against millions, and evaluations may
    take hours in parallel on accelerators, against at most 20 minutes on
    one CPU.
  - *Limitation* (§6, p21): it needs an automated evaluator. LLM-provided
    evaluation is possible, but the authors say it is not the setting they
    optimised for.
- **Released code:** none for the agent.
  https://github.com/google-deepmind/alphaevolve_results holds a Colab
  notebook with the mathematical results and code to verify them. Its
  README states that it does not contain the code to run AlphaEvolve. A
  companion repo, google-deepmind/alphaevolve_repository_of_problems,
  accompanies arXiv 2511.02864 (Georgiev, Gómez-Serrano, Tao, Wagner); it
  was not reviewed beyond its README. No code file in either repo was
  opened.
- **Not found in the source:** these features of the owner's spec do not
  appear in AlphaEvolve.
  - **Residual mode** (a correction added to a fixed base formula): not
    found. The nearest ideas are the skeleton with evolve blocks and the
    choice between diffs and full rewrites (p7).
  - **Critic agent** reviewing proposals before they are built: not found.
    The introduction (p2) says LLMs "generate, critique, and evolve"
    programs, but the only mechanism described is LLM grading that sits
    beside the evaluation (p7-8).
  - **Analyst agent:** not found. The nearest is meta-prompt evolution (p5).
  - **Proposers with distinct perspectives, each with its own island:** not
    found. The two models differ in speed and quality, not in role.
  - **Explorer with a protected island,** or a set share of exploratory or
    full-replacement candidates: not found.
  - **Noisy fitness and statistics:** no repeated measurement, statistical
    test or proxy-against-final-metric study, apart from the
    simulator-then-fleet confirmation in §3.3.1.
  - **MAP-Elites details:** no descriptors, island counts or reset schedule.
- **What it means for Fork:** Phase 3 deliverable 8c, the heuristic-discovery
  tool.
  - Take from the paper:
    - make the LMR function the only evolve block;
    - allow both diff and whole-function answers;
    - run a cascade (gate, proxies, short match, SPRT) in the spirit of §2.4;
    - show several prior programs, with their scores, in each prompt;
    - check proxies on held-out data and confirm with the real metric, as
      was done for the Borg heuristic.
  - Fork's own additions: the critic, the analyst, the explorer, the
    proposer perspectives and residual mode. Document them as Fork's
    choices, never as AlphaEvolve's.
- **Phase:** 3 (8c pilot); late 4 and the improvement pass if the owner says
  go. **Tag:** REFERENCE ONLY. **License:** arXiv listing CC BY-NC-ND 4.0;
  the PDF itself is marked "© 2025 Google DeepMind. All rights reserved".
  alphaevolve_results: Apache-2.0 for software and CC BY 4.0 for other
  materials (README; GitHub licence field Apache-2.0).
  **Verified:** 2026-10-26.

### Mathematical discoveries from program search with large language models (Nature 625(7995):468-475; DOI 10.1038/s41586-023-06924-6, online 2023-12-14, issue 2024-01-18)
- **Citation:** B. Romera-Paredes, M. Barekatain, A. Novikov, M. Balog,
  M. P. Kumar, E. Dupont, F. J. R. Ruiz, J. S. Ellenberg, P. Wang, O. Fawzi,
  P. Kohli, A. Fawzi (12 authors; Google DeepMind, University of
  Wisconsin-Madison, University of Lyon), "Mathematical discoveries from
  program search with large language models", *Nature* 625(7995):468-475.
  Received 2023-08-12, accepted 2023-11-30, published online 2023-12-14,
  issue dated 2024-01-18 (PDF header and footer; Crossref gives the same
  online and print dates). The method is named FunSearch, short for
  "searching in the function space".
- **Links:** https://doi.org/10.1038/s41586-023-06924-6 (article page
  https://www.nature.com/articles/s41586-023-06924-6, PDF
  https://www.nature.com/articles/s41586-023-06924-6.pdf, free).
  Supplementary Information PDF (publisher):
  https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-023-06924-6/MediaObjects/41586_2023_6924_MOESM1_ESM.pdf.
  Also in PubMed Central as PMC10794145. Whether an arXiv version exists
  was not checked.
- **What it is:** an evolutionary loop that pairs a frozen, pretrained LLM
  with an automatic evaluator to search for programs rather than direct
  solutions. It found new large cap sets, including a new size-512 cap set
  in dimension 8, and a better asymptotic lower bound. It also found online
  bin-packing heuristics that beat first fit and best fit.
- **Method components (as read):**
  - *Specification and skeleton* (p469-470): the user supplies an evaluate
    function, an initial program (possibly trivial) and optionally a
    skeleton. Only the critical function evolves, e.g. the priority
    function of a greedy algorithm (Fig. 2). The authors say a fixed
    skeleton helps overall, because LLM effort goes only into the critical
    part and less known structure has to be rewritten. In the
    Supplementary Information ablation (SI A.1), removing the skeleton did
    worse.
  - *LLM* (p469): pretrained, not fine-tuned: Codey, from the PaLM 2
    family. The authors chose fast inference over sample quality, and the
    results used on the order of 10^6 samples. Results were not very
    sensitive to the choice of LLM; StarCoder is compared in SI A.2.
  - *Evaluation* (p469-470): each program runs on a set of inputs, and
    the scores are combined, e.g. by their mean. Programs that exceed the
    time or memory limit, or give invalid output, are discarded; only
    correct programs enter the database. Defaults (SI E.1, Table E.2): a
    30 s timeout and a 2 GB memory limit for cap sets; 300 s and 5 GB for
    bin packing.
  - *Best-shot prompting* (p470; Methods):
    - sample k programs from one island and sort them by score, lowest
      first;
    - rename each with a version suffix (v0, v1, ...) and put them in the
      prompt in the skeleton's layout;
    - end the prompt with the bare header of the next version, for the LLM
      to complete.

    k = 2 worked better than 1, with diminishing returns beyond 2. In the
    ablation (SI A.1), prompting with a single program did worse.
  - *Islands* (p470; Methods):
    - there are m islands, each seeded with the initial program and evolved
      independently;
    - for each prompt, an island is picked uniformly, k = 2 programs are
      sampled from it, and the new programs go back to that island;
    - every 4 hours, all programs on the half of the islands whose best
      program scores lowest are discarded;
    - each emptied island is reseeded with one program: the best program of
      a surviving island chosen uniformly at random, ties going to the
      older program.

    The defaults (SI Table E.2) are 10 islands and a 4-hour reset. With
    only one island, the ablation did worse (SI A.1).
  - *Clusters inside islands* (Methods; Extended Data Fig. 3):
    - programs with the same signature (the tuple of their scores on each
      input) form a cluster;
    - a cluster is picked by a softmax over cluster scores ("Boltzmann
      selection"); the temperature falls linearly from T0 as the island
      grows and restarts every N programs (T0 = 0.1, N = 30,000 in SI
      Table E.2);
    - inside the chosen cluster, shorter programs are preferred, through a
      softmax over normalised negative length in characters
      (Tprogram = 1.0).

    The authors link this to diversity preservation, lexicase selection and
    fitness-uniform optimisation.
  - *Distributed system* (p470; SI A.5, E.1): a programs database,
    samplers and evaluators run asynchronously. The main text says
    typically 15 samplers and 150 CPU evaluators, but SI Table E.2 lists
    140 evaluators as the default (a discrepancy within the source). Each
    prompt yields 4 samples, at temperature 1.0 and nucleus 0.95.
  - *Generalisation test* (p472-473): the bin-packing heuristic started
    from best fit. It evolved on generated instances the size of the OR1
    set, then was tested on the OR1-OR4 benchmarks and on Weibull
    instances, and beat first fit and best fit on all of them.
  - *Run-to-run variance* (Methods "Robustness"; SI A.3): results vary
    between runs. Some problems beat the baseline in every run; others
    need many runs, e.g. only 4 of 140 cap-set runs in dimension 8 reached
    size 512.
  - *Budget and stopping:* there is no fixed stopping rule. The user can
    take the best programs at any time (Fig. 1 caption, p469), and the
    reset cycle repeats "until termination" (Extended Data Fig. 2). Scale
    (SI A.5): about 2 million programs for the symmetric admissible set
    I(15, 10). Reproducing it was estimated at two days on 15 GPU LLM
    instances and 5 CPU servers, costing roughly $800-1,400.
  - *Scope* (p474): it works best with three things: an efficient
    evaluator; rich scores rather than a binary signal; and a skeleton with
    an isolated part to evolve.
- **Released code:** https://github.com/google-deepmind/funsearch.
  According to its README, the repo holds the discovered functions, a
  bin-packing evaluation suite and a single-threaded implementation of the
  evolutionary algorithm and pipeline. It has no LLM, sandbox or
  distributed infrastructure. Not opened. The Supplementary Information
  PDF also prints Python code for the sampler, evaluator and database
  (Appendix F), and the discovered programs (Appendix C); neither appendix
  was read. The supplementary zip (MOESM2) was not downloaded.
- **Not found in the source:** these features of the owner's spec do not
  appear in FunSearch.
  - **Residual mode:** not found. The LLM writes the whole body of the next
    function version each time.
  - **Critic agent:** not found. The only filter is the evaluator rejecting
    incorrect programs.
  - **Analyst agent and proposer perspectives:** not found. There is one LLM
    and one prompt scheme.
  - **Explorer or protected island:** not found. All islands are treated
    alike; reset islands restart from a copy of a strong program.
  - **MAP-Elites:** FunSearch does not use it. For the cluster idea it cites
    quality-diversity work (Mouret & Doncieux 2009; Pugh et al. 2016).
  - **Noisy fitness and statistics:** no treatment of noisy scores or
    statistical testing.
- **What it means for Fork:** Phase 3 deliverable 8c.
  - Concrete, simple mechanisms to adopt as ideas:
    - islands with a periodic reset of the worst half;
    - clusters keyed by a signature of per-input scores (for Fork, perhaps
      scores per position subset);
    - two-program prompts ordered by score;
    - a preference for shorter programs, which suits the hot-path rules;
    - invalid programs never reach the database (Fork's gate).
  - The paper's scope note (an efficient evaluator, rich scores) is the
    weak spot for Fork, whose final judge is slow and noisy. The cheap
    proxies carry the loop, so whether the proxies predict SPRT results is
    rightly a pilot metric.
  - The 4-hour wall-clock reset is FunSearch's choice; Fork will need its
    own reset rule (e.g. by generation count) with a recorded
    justification.
- **Phase:** 3 (8c pilot); late 4 and the improvement pass if go. **Tag:**
  REFERENCE ONLY. **License:** article CC BY 4.0 (Crossref licence field;
  Nature marks it open access). funsearch repo: Apache-2.0 for software and
  CC BY 4.0 for other materials (README; GitHub licence field Apache-2.0).
  **Verified:** 2026-10-26.

### Illuminating search spaces by mapping elites (arXiv 1504.04909v1, 2015-04-20)
- **Citation:** J.-B. Mouret (Université Pierre et Marie Curie-Paris 6,
  CNRS UMR 7222) and J. Clune (University of Wyoming), "Illuminating search
  spaces by mapping elites", arXiv:1504.04909 [cs.AI; also cs.NE, cs.RO,
  q-bio.PE]. v1 was submitted 2015-04-20 and was the only version listed on
  2026-10-26. DOI 10.48550/arXiv.1504.04909. The arXiv comment reads "Early
  draft", and the PDF header reads "Preprint - April 21, 2015". An author's
  note on p1 calls it a preliminary draft, posted so that others can cite
  and implement the algorithm; its experiments were to be redone before a
  final version, so its data may change. **UNVERIFIED:** whether a
  peer-reviewed final version exists (not looked for).
- **Links:** https://arxiv.org/abs/1504.04909 (PDF
  https://arxiv.org/pdf/1504.04909).
- **What it is:** MAP-Elites (Multi-dimensional Archive of Phenotypic
  Elites), an "illumination" algorithm. It keeps the best solution found in
  each cell of a low-dimensional feature space chosen by the user, instead
  of one overall best. The paper says the algorithm had already been used,
  and briefly described, in Cully et al. (arXiv 1407.3501); this paper is
  the first to describe it in detail.
- **Method components (as read):**
  - *Setup* (§3, p3): the user picks a performance measure and N feature
    dimensions, also called behaviour dimensions. A feature function maps
    each candidate to an N-dimensional descriptor; some features are read
    off the candidate, others need running it. Each dimension is
    discretised as the user prefers or as compute allows, possibly coarse
    at first and finer later.
  - *Algorithm* (Fig. 2 pseudocode and §3, p3):
    - start with G random candidates, placed in their cells (the best one
      per cell is kept);
    - then, until a termination criterion: pick an occupied cell uniformly
      at random, and mutate and/or cross over its elite to make a child;
    - compute the child's descriptor and performance;
    - store the child if its cell is empty or it beats the occupant, which
      it then replaces.
  - *Archive* (p3-4): the archive is the population, so each member is
    diverse by construction. Not every cell can be filled, and many
    candidates can map to the same cell. Search must happen in the
    candidate space; it cannot step directly through the feature space.
  - *Selection* (§4, p4): parents are sampled uniformly from the archive.
    The authors stress that this makes the selection pressure simple and
    predictable compared with Novelty Search with Local Competition
    (NS+LC) and MOLE, and that each cell lookup is O(1).
  - *Chess example* (§3, p3): the paper itself suggests searching chess
    programs, with win percentage as performance and dimensions such as
    aggressiveness of play or speed of move choice. It was not run.
  - *Termination* (p3): a time limit, a compute limit, or a property of
    the archive, such as the share of cells filled, the mean fitness
    reached, or n solutions found.
  - *Quality measures* (§5, p5): global performance, global reliability,
    precision ("opt-in reliability") and coverage. Formal definitions are
    in §9.4 (p12).
  - *Variants* (§8, p11), left for future work:
    - several genomes per cell;
    - biased choice of parent cells, which did not beat the default in
      preliminary tests;
    - crossover limited to nearby cells, which the authors compare to an
      island model.
  - *Hierarchical and parallel version* (§3, p3; §9.2-9.3, p11-12): cells
    start large and are split after preset numbers of evaluations, and
    evaluations go out in batches to cluster nodes; all experiments used
    this version. In the retina experiment, for example, the map is refined
    in steps up to 512 x 512 cells, with batches of 2,000.
  - *Results* (§6, p5-10; preliminary): on the retina neural-network task
    (20 runs per treatment), MAP-Elites beat a traditional EA, NS+LC and
    random sampling on all four measures. Simulated soft robots and a real
    soft arm were also tested. Elite lineages crossed many regions of the
    map, which the authors read as "stepping stones" (p6).
  - *Limitation* (§7, p11): the feature space is fixed in advance and new
    kinds of cells cannot appear, so the algorithm is not open-ended.
- **Released code:** none is linked in the paper.
- **Not found in the source:**
  - LLM-generated candidates: not found (the paper predates them).
  - Islands as a population structure: not found; they appear only as an
    analogy for restricted crossover (§8).
  - Evaluation cascades and noisy fitness: not found. Nothing covers
    re-testing elites whose score may be a lucky measurement.
- **What it means for Fork:** Phase 3 deliverable 8c.
  - The owner's axes (mean reduction, re-search rate) are behaviour
    descriptors in exactly this sense: measured by running the candidate,
    not read off its code.
  - Start with a coarse grid and refine it only if many candidates land in
    the same cell.
  - Pick parents uniformly from occupied cells unless a measured bias does
    better (the paper's own preliminary bias variants did not).
  - Fork's fitness is noisy, so an elite can hold its cell on luck. The
    paper is silent on this; Fork must decide its own rule, for example
    re-measuring an elite before it may be replaced or promoted.
- **Phase:** 3 (8c pilot). **Tag:** REFERENCE ONLY. **License:** arXiv
  non-exclusive distribution licence (arXiv licence link); no code
  released. **Verified:** 2026-10-26.

### How the three relate (from the sources)

- The AlphaEvolve paper calls itself a substantial extension of FunSearch
  (p2, Table 1). Its program database combines MAP-Elites with the island
  model it credits to FunSearch (§2.5, p8).
- FunSearch evolves one function with a small, fast LLM over millions of
  samples. AlphaEvolve evolves larger code with strong LLMs over thousands
  of samples, with richer prompts and several metrics (AlphaEvolve
  Table 1).
- Only FunSearch publishes the database mechanics in full (islands, reset,
  clusters, temperatures). Only MAP-Elites defines the descriptor archive.
  AlphaEvolve publishes neither for its own system.

### Prior work: evolutionary and LLM-driven search for game-engine heuristics (2026-10-27)

Added 2026-10-27 for the same pilot (ideas.md idea 23; DESIGN.md
deliverable 8c). It does not repeat the three method papers above. The
question was: who has already evolved, or had an LLM write, the search
heuristics of a game engine (pruning, reductions, extensions, move ordering,
time management, evaluation terms), how did they measure it, and what went
wrong? Every entry below was read in the source itself: arXiv PDFs and
abstract pages, author-hosted PDFs (some through the Internet Archive because
the original links are dead), Crossref records, Chess Programming Wiki (CPW)
pages, and README prose and GitHub API metadata for two frameworks. **No
engine source code and no framework code file was opened.** Each claim names
its section, table or page. "Measured" means a number from the authors'
experiments; "author's view" means their interpretation; "my note" marks a
reading added here.

**Tag for every entry: REFERENCE ONLY, for ideas.** Some entries publish
evolved parameter values or evolved code. Those values and listings are
**not** copied here and must never seed Fork: a value someone else's
evolution found is another engine's constant (CLAUDE.md non-negotiable 6).

**Headline (from the search, not a proof of absence):** no primary source
was found that runs an LLM-driven evolution loop on an alpha-beta chess
engine's search heuristics (LMR, pruning, move ordering or time management)
and reports SPRT-measured Elo. Searches tried on 2026-10-27 included "LLM
evolutionary search chess engine heuristics AlphaEvolve", "LLM evolve chess
engine code Elo SPRT", "LLM-written patches tested fishtest OR OpenBench" and
"late move reduction OR move ordering evolved by language model". The
nearest LLM work is general game playing (MCTS, with chess as one of 50
games) and coding agents writing whole engines. Fork's pilot would be the
first such measurement known to this KB. **UNVERIFIED:** that none exists
(forum posts, unpublished experiments and non-English venues were not
searched).

#### Part A. Pre-LLM evolution and tuning of search parameters (chess, Go, LOA)

##### CPW: Genetic Programming, Automated Tuning, SPSA, Stockfish's Tuning Method (living pages)
- **Links:** https://www.chessprogramming.org/Genetic_Programming,
  https://www.chessprogramming.org/Automated_Tuning,
  https://www.chessprogramming.org/SPSA,
  https://www.chessprogramming.org/Stockfish%27s_Tuning_Method. The site
  showed a banner saying it is a temporary, read-only recovery copy.
- **What they say (as read):**
  - *Automated Tuning* (intro): automatic tuning is mostly of evaluation
    weights, and "less commonly" of search parameters; its footnote for search
    parameters is Björnsson and Marsland (2001). The "Playing Strength"
    paragraph says solving test positions does not necessarily correlate
    with match strength, so many games are needed, up to several tens of
    thousands when the two versions are close, and that fast games with SPRT
    (Fishtest) became the norm. Under "Mathematical Optimization" the page
    lists, as advantages, that it works for any parameter including search
    and accounts for search-eval interaction; the disadvantage is cost that
    grows with the number of weights.
  - *Genetic Programming*: a bibliography. The search-related chess entries
    are Björnsson and Marsland (2002), Gross et al. (2002), Hauptman and
    Sipper (2007), Hauptman's 2009 thesis "Evolving Search Heuristics for
    Combinatorial Games with Genetic Programming", David et al. (2010, 2014),
    Mitsuta and Schmitt (2010, GNU Chess), plus Pratola and Wolf (2003, Go).
  - *SPSA*: SPSA estimates a gradient from two measurements per iteration
    whatever the number of parameters. The page says it can tune search as
    well as evaluation parameters. It names Joona Kiiski's 2011 Stockfish
    method as a prominent instance (one game pair per iteration) and credits
    Kocsis, Szepesvári and Winands (ACG 11, 2005) with bringing SPSA to
    game programming.
  - *Stockfish's Tuning Method* (Kiiski, October 2011; the page marks the
    text public domain): start from the current hand-tuned values and
    perturb several variables (7 to 35 at once) with random signed deltas.
    Play the plus side against the minus side and move the values slightly
    toward the winner, over 30,000 to 100,000 very fast games. The author
    reports 40-70 Elo for Stockfish (author's claim; no protocol is given).
    He says the method does not converge: important variables improve while
    the rest random-walk, so strength later falls and the run must be
    stopped by hand. Choosing which variables to tune matters a lot; tuning
    single table entries fails, while two "knobs" per table worked.
- **What it means for Fork:** SPSA-style tuning (Phase 8) moves the
  constants of a **fixed formula** using game results. An LLM loop changes
  the formula's **shape**. They are complementary. A sensible split (my
  note, Fork's choice, not from a source): the pilot searches over
  structure, and any surviving structure gets its constants tuned later by
  SPSA under the normal search-constants rule. Kiiski's non-convergence
  warning also applies to a long-running LLM loop: it needs a stopping rule.
- **Tag:** REFERENCE ONLY. **License:** CPW text CC BY-SA 3.0 (site footer);
  the tuning-method text is marked public domain on its page.
  **Verified:** 2026-10-27.

##### Björnsson & Marsland (2002): Learning Control of Search Extensions
- **Citation:** Y. Björnsson and T. A. Marsland, "Learning Control of Search
  Extensions", Proc. 6th Joint Conference on Information Sciences (JCIS
  2002), Research Triangle Park NC, March 2002, pp. 446-449 (citation printed
  on the PDF).
- **Links:** CPW's link http://www.ru.is/faculty/yngvi/pdf/BjornssonM02.pdf
  now returns 404. Read from the Internet Archive copy
  https://web.archive.org/web/20210508020804/https://www.ru.is/faculty/yngvi/pdf/BjornssonM02.pdf
  (4 pages).
- **What it reports:**
  - Method (§3): a learning module drives the engine through three added
    commands: set a position, set the parameters, and search until the
    known best move is found or a node cap is hit. It minimises the total
    node count over a labelled suite by finite-difference gradient descent,
    re-searching every position once per parameter in each iteration.
  - Experiment (§4, Fig. 1, measured): four fractional-ply extension weights
    in Crafty, on the 879-position ECM suite with a 500,000-node cap per
    position. Total nodes fell to 73% of the start (310M to 229M), and
    solved positions rose from 346 (39%) to 508 (57%), "as a side effect"
    (authors' words).
  - **No games were played.** Strength is only inferred from the suite.
- **What it means for Fork:** the template for Fork's cheap proxy (nodes to
  solve, with a cap so that no position dominates). It is also a warning
  that a suite-only result says nothing about Elo. For Fork the positions
  must be Fork-labelled and the proxy must be checked against matches.
- **Tag:** REFERENCE ONLY. **License:** none stated on the PDF
  (author-hosted copy). **Verified:** 2026-10-27.

##### David-Tabibi, Koppel & Netanyahu (2010): Optimizing Selective Search in Chess
- **Citation:** O. David-Tabibi, M. Koppel, N. S. Netanyahu, "Optimizing
  Selective Search in Chess", ICML 2010 Workshop on Machine Learning and
  Games, Haifa (arXiv journal-ref), arXiv:1009.0550v1, 2010-09-02 (only
  version). The fuller journal version is "Genetic Algorithms for Automatic
  Search Tuning", *ICGA Journal* 33(2):67-79, 2010, DOI
  10.3233/icg-2010-33202 (Crossref). Only the arXiv text was read.
- **Links:** https://arxiv.org/abs/1009.0550 (PDF https://arxiv.org/pdf/1009.0550).
- **What it reports:**
  - Search space (§2, Table 1): 18 search parameters of the Falcon engine
    (null move, futility, multi-cut and five extensions) in a 70-bit
    Gray-coded chromosome.
  - Algorithm (§4): a standard GA with fitness-proportional selection,
    uniform crossover and elitism, random initial values, population 10
    and 50 generations.
  - Fitness (§4), after Björnsson and Marsland: total nodes to find the
    known move over the 879 ECM positions, with a 500,000-node cap.
  - Training result (§5, measured): the best organism's total fell from 226M
    to 199M nodes and solved positions rose from 488 to 547.
  - Out-of-sample check (§5, Tables 2-3, measured): the authors note the
    suite score is biased because it is the training set, so they played
    matches. Evol* vs Falcon was 152.5-147.5 (51.1%, +6 Elo) over 300 games.
    Evol* vs Crafty scored 59.5% and Falcon vs Crafty 57.8%; Evol* vs
    randomly initialised organisms scored 71.4% over 1,000 games. Time
    control: not stated in this version.
  - Author's view (§6): the evolved values match eight years of hand tuning.
    Evolved values are specific to the engine, because search interacts
    with the evaluation.
  - My note: a 300-game +6 Elo result cannot tell "equal" from a gain or
    loss of a few tens of Elo. The match shows parity at best, not
    improvement.
- **What it means for Fork:** the closest published analogue of Fork's
  funnel, with a cheap node-count proxy and a match check. Its weak point is
  Fork's main risk: the final judge was small and underpowered. It also used
  a third-party tactical suite **as the fitness**, which Fork's data policy
  forbids (suites are test inputs only, never tuning targets; tools.md §4).
- **Tag:** REFERENCE ONLY. **License:** arXiv non-exclusive distribution
  licence. **Verified:** 2026-10-27.

##### David, van den Herik, Koppel & Netanyahu (2014): Genetic Algorithms for Evolving Computer Chess Programs
- **Citation:** E. (O.) David, H. J. van den Herik, M. Koppel, N. S.
  Netanyahu, *IEEE Transactions on Evolutionary Computation* 18(5):779-789,
  2014, DOI 10.1109/TEVC.2013.2285111 (Crossref; online October 2014).
  Preprint arXiv:1711.08337v1, 2017-11-21. The arXiv comment says it won a
  Gold "Humies" award and overlaps heavily with arXiv 1711.06839-06841.
- **Links:** https://arxiv.org/abs/1711.08337 (PDF https://arxiv.org/pdf/1711.08337).
- **What it reports:**
  - Related work (§II.B): it lists earlier evolutionary chess work and says
    game-based fitness needed so many games that only a few parameters
    could be evolved (Kendall and Whitwell; Aksenov).
  - Method (§IV): the search-parameter GA repeats the 2010 method (same
    chromosome, ECM node-count fitness, population 10, 50 generations), run
    after the evaluation weights had been evolved from grandmaster moves.
  - Results (§V, Tables III-VI, measured): at 5 minutes per game, EVOL*
    scored 60.5% against Crafty and 60.0% against EVOL0 (the same program
    before coevolution) in 300-game matches. At 1 hour per game over 100
    games it scored 61.5% vs Crafty, 41.0% vs Junior, 51.5% vs Fritz and
    58.5% vs Hiarcs. The evaluation-weight evolution took about 2 hours per
    run (ten runs, about 20 hours) and coevolution about 20 hours more; the
    search-parameter phase time is not separately stated.
  - Table II publishes the evolved search values. **Deliberately not copied
    here.**
- **What it means for Fork:** evidence that a GA over search parameters can
  match hand tuning in an older engine. It also shows that published
  "evolved constants" exist and that a model may have read them. That is
  one more reason the originality checker screens every constant a
  candidate introduces.
- **Tag:** REFERENCE ONLY. **License:** arXiv non-exclusive distribution
  licence. **Verified:** 2026-10-27.

##### Hauptman & Sipper (2007): Evolution of an Efficient Search Algorithm for the Mate-In-N Problem in Chess
- **Citation:** A. Hauptman, M. Sipper, EuroGP 2007, LNCS 4445, pp. 78-89,
  Springer (PDF footer), DOI 10.1007/978-3-540-71605-1_8 (Crossref).
- **Links:** CPW's link http://www.cs.bgu.ac.il/~sipper/papabs/gpsearch.pdf
  now redirects to a university home page. Read from
  https://web.archive.org/web/20160316074327/https://www.cs.bgu.ac.il/~sipper/papabs/gpsearch.pdf.
- **What it reports:**
  - Method (§4): Koza-style genetic programming evolves whole mate-search
    programs (LISP trees) from building blocks suggested by strong players
    (checks, forced replies, pins near the king and so on), with a penalty
    for deep lookahead.
  - Fitness (§4.3): correctness on sampled mate-in-N problems, weighted by
    depth and by the ratio of Crafty's node count to the program's.
  - Result (§5, Table 2, measured on a held-out set of 10 problems per
    depth): for mate-in-5 the best program used 850k nodes against
    Crafty's 1.6M, which the authors call a 47% reduction.
  - The paper's account of earlier work (§2) is the only source read here
    for Gross et al. (2002): it says that work evolved move ordering,
    cut-off and evaluation parts around a fixed alpha-beta kernel and
    reduced nodes to 6% of alpha-beta's, with no games against commercial
    programs. That is this paper's summary, not checked against Gross et
    al. (see Unverified).
  - Author's view (§6): the evolved trees were large and hard to analyse.
- **What it means for Fork:** an early "evolve code, not numbers" result
  scored by node counts against a reference engine. Fork's analogue scores
  against Fork's own baseline, never another engine's counts. The trees
  being hard to analyse matches Fork's need for short, reviewable
  candidates.
- **Tag:** REFERENCE ONLY. **License:** © Springer-Verlag 2007 (PDF footer);
  author-hosted copy. **Verified:** 2026-10-27.

##### Kocsis, Szepesvári & Winands (2005/2006): RSPSA: Enhanced Parameter Optimisation in Games
- **Citation:** L. Kocsis, C. Szepesvári, M. H. M. Winands, "RSPSA: Enhanced
  Parameter Optimization in Games", *Advances in Computer Games* 11 (LNCS),
  pp. 39-56, 2006, DOI 10.1007/11922155_4 (Crossref; the PDF title spells it
  "Optimisation"). The journal companion, Kocsis and Szepesvári, "Universal
  parameter optimisation in games based on SPSA", *Machine Learning*
  63(3):249-286, 2006, DOI 10.1007/s10994-006-6888-8, was checked on
  Crossref only and its text was not read.
- **Links:** http://www.sztaki.hu/~szcsaba/papers/rspsa_acg.pdf now returns
  404. Read from
  https://web.archive.org/web/20110104212031/http://www.sztaki.hu/~szcsaba/papers/rspsa_acg.pdf.
- **What it reports:**
  - Method (§2-§3): SPSA combined with RPROP step sizes, plus variance
    reduction through common random numbers and antithetic variables. The
    authors estimate these give a speed-up of more than ten (author's
    estimate) and say plain SPSA brought no noticeable gain without them
    (§6).
  - Search experiment (§5.3, Fig. 2, measured): RSPSA tuned the 277
    realisation-probability weights of MIA, a Lines of Action program, in
    two ways.
    - **Game result:** performance averaged over 500 games against five
      opponents, from 50 fixed positions with both colours, at 250,000
      nodes per move. Each gradient estimate used 500 perturbations with one
      game per side, the two sides sharing position, opponent and colour
      (common random numbers).
    - **Move score:** the quality of the move chosen at 250,000 nodes, as
      judged by the program's own deeper search (up to 10,000,000 nodes),
      averaged over a fixed set of 10,000 positions. Each gradient estimate
      used 5,000 perturbations, one random position per side. Deep scores
      are cached, since they do not depend on the tuned weights.
  - Result: the move-score estimate was about four times faster and less
    noisy (authors' observation). Its best weights scored 0.59 in games,
    against 0.55 for the best weights found with game-result fitness.
- **What it means for Fork:** the most direct precedent for Fork's proxy:
  move quality judged by the **same engine's deeper search**, with cached
  labels, which matches Fork's "positions labelled by Fork's own deeper
  search". It was confirmed by games, in another game (LOA), at one
  setting. Fork should repeat that confirmation for chess rather than
  assume it.
- **Tag:** REFERENCE ONLY. **License:** none stated on the PDF
  (author-hosted copy). **Verified:** 2026-10-27.

##### Pratola & Wolf (2003): Optimizing GoTools' Search Heuristics using Genetic Algorithms
- **Citation:** M. Pratola, T. Wolf (Brock University), *ICGA Journal*
  26(1):28-48, 2003, DOI 10.3233/icg-2003-26106 (Crossref).
  arXiv:cs/0302002v1, 2003-02-02 (comment "to appear in Journal of ICGA").
- **Links:** https://arxiv.org/abs/cs/0302002 (PDF https://arxiv.org/pdf/cs/0302002).
- **What it reports:**
  - Setup (§2.2-§2.3): a GA tunes GoTools' life-and-death move-ordering
    weights (46 static and 10 dynamic). The fitness counts the search
    tree's terminal leaves rather than wall time, for reproducibility
    across machines, measured on generated problem sets with separate test
    sets.
  - Results (§3-§4, measured):
    - A **cheap static fitness** (the rank of the known winning move, with
      no search) improved the training score but did not carry over to
      test sets, and got worse as problems got harder.
    - The **expensive fitness** (actually solving the problems) gave 12%
      fewer leaves for the static weights against zero weights.
    - Dynamic weights trained on hard problems gave 18% fewer leaves
      against zero weights, and 8% fewer than the hand-set originals.
    - Training on hard problems was needed to do well on hard test
      problems.
- **What it means for Fork:** a measured case of a cheap proxy that did not
  carry over. A Fork proxy that only checks whether the move ordering would
  rank the right move first, without searching, is the same trap. Proxies
  should search, and the proxy set should include hard positions.
- **Tag:** REFERENCE ONLY. **License:** arXiv licence "assumed 1991-2003"
  (licence link). **Verified:** 2026-10-27.

#### Part B. LLM-driven program search for games

##### Li, Schultz, Lanctot & Hennes (2026): Modular Discovery of General Game-Playing Algorithms with Large Language Models
- **Citation:** Z. Li, J. Schultz, M. Lanctot, D. Hennes (Google DeepMind),
  arXiv:2609.33115v1, 2026-09-27 (only version on 2026-10-27; no venue).
- **Links:** https://arxiv.org/abs/2609.33115 (PDF https://arxiv.org/pdf/2609.33115).
- **What it is:** AlphaEvolve (with Gemini 3.5 Flash) evolves C++ MCTS
  search mechanisms (tree policy, backup, root scheduling) shared by all
  games. Separate workers evolve per-game heuristics (priors, value
  estimators, resamplers) on 50 OpenSpiel training games. Testing covers
  held-out, procedurally generated and neural-network games (more than 400
  in all).
- **Findings (as read):**
  - *Factorisation* (§3.2, authors' claim): evolving search and heuristics
    as one program made mutations overfit to individual games' rule quirks.
  - *Credit decoupling* (§3.3): a search candidate is scored against a fixed
    reference engine (canonical PUCT) using the same heuristics, with
    scores normalised by the remaining headroom. Without this, a weak
    search could "free-ride" on a good heuristic.
  - *Moving opponents* (§3.4, App. C.4): fitness against a fixed opponent
    risked overfitting to its flaws, so the opponent is replaced by the
    reigning champion once it passes a confirmation tournament. That
    tournament uses 2x the normal episodes with fresh seeds and requires
    p < 0.01 (paired t-test) and a win rate of at least 0.60.
  - *Failure modes and guards* (App. B, B.2, B.5, authors' account):
    - candidates exploited the simulator; in imperfect-information games
      some read hidden state through pointer casts, so an anti-cheating
      harness gives leaking candidates a fixed penalty;
    - fast games monopolised selection. Candidates now first pass a
      screening gate on 13 validation games (significant non-inferiority
      to the reference, p < 0.01). A "stochastic quorum" then admits a
      candidate as a parent only once it has results on enough of a random
      sample of games, with every game cluster represented (App. B.2);
    - divisions by zero appeared near score ceilings;
    - LLMs looped into giant generated code, so candidates over 100,000
      characters or failing static syntax-tree checks are rejected before
      compiling;
    - stagnation is detected against an "empirical noise floor" on the
      75th percentile of recent scores, because single high scores were
      noise.
  - *Statistics* (App. C.2): the number of evaluation episodes is set from
    a minimum detectable effect of 0.10 at 95% (about 200 episodes). The
    authors admit that for slow games (as few as 13 episodes) the gate is
    "primarily a safety guard" rather than a real significance test. The
    candidate gets 1/2.5 of the reference's simulations, so it must win by
    smarter search, not more search.
  - *Cost* (App. B.6, authors' estimate): about 6,400 candidates per run up
    to the champion, about 300M input and 550M output tokens, roughly
    $5,400 per run at list prices. Evaluation workers had 4-6 cores each.
  - *Chess* (§4.4, App. L.2, measured): against Stockfish at three settings
    the evolved general searcher scored 0% at the middle and top settings,
    and about 5-7% at the bottom one (skill 0, 1,000 nodes), depending on
    its simulation budget. The authors
    conclude that search improves on whatever evaluation it has but cannot
    make up for missing evaluation knowledge.
  - *Memorisation* (App. J.4.1, p. 55, authors' argument): all runs started
    from a minimal PUCT seed and were never prompted with AlphaZero, KataGo
    or Lc0 code. They argue that the discovered formulas (branching-scaled
    exploration and others) do not appear in those systems. This is
    reasoning, not an automated similarity check.
- **What it means for Fork:** the most complete published engineering
  account of an LLM search-evolution loop in games.
  - The ideas to carry over: a fixed reference engine as the yardstick; a
    confirmation stage on fresh seeds before promotion; code-size and
    syntax-tree gates; anti-cheating checks (Fork's analogue: a candidate
    may change only the LMR function and read only allowed inputs);
    stagnation judged against a measured noise floor.
  - It says nothing about alpha-beta chess engines near the top. Its chess
    strength is far below Fork's.
- **Tag:** REFERENCE ONLY. **License:** arXiv listing CC BY 4.0; the PDF
  says "© 2026 Google DeepMind. All rights reserved". The appendix prints
  C++ listings (J.1-J.2), which were not read. **Verified:** 2026-10-27.

##### Li, Schultz, Hennes & Lanctot (2026): Discovering Multiagent Learning Algorithms with Large Language Models
- **Citation:** Z. Li, J. Schultz, D. Hennes, M. Lanctot (Google DeepMind),
  arXiv:2602.16928, v1 2026-02-18, v2 2026-02-21, v3 2026-05-07 (read: v3).
- **Links:** https://arxiv.org/abs/2602.16928.
- **What it reports:**
  - Setup (§3.1, §3.4, §4.1): AlphaEvolve with Gemini 2.5 Pro evolves CFR
    and PSRO update code. Fitness is negative exploitability, computed
    exactly (so deterministic, with no noise) on four training games and
    tested on fourteen others.
  - Overfitting (abstract, §4.2, Table 1): the raw discoveries (VAD-CFR,
    SHOR-PSRO) were competitive with the best human-designed baselines but
    "over-engineered". The LLM stacked tightly coupled extra mechanisms
    tuned to the training games. Train/test ablations, aggregated with an
    interquartile mean, found a small core. The distilled versions
    (WOP-CFR, PM-PSRO) generalised as well or better.
  - Limitations (§6): one evolutionary trajectory, no variance across runs,
    and the distillation needed human judgement.
- **What it means for Fork:** expect over-fitted complexity from the loop.
  Plan an ablation pass on every survivor (remove each added term and
  re-measure on held-out positions and in matches) and keep the minimal
  core. This agrees with Fork's own removal-round rule at phase ends.
- **Tag:** REFERENCE ONLY. **License:** arXiv listing CC BY 4.0; the PDF
  says "© 2026 Google DeepMind. All rights reserved". Source listings in §7.2
  were not read. **Verified:** 2026-10-27.

##### Lehrach et al. (2025): Code World Models for General Game Playing
- **Citation:** W. Lehrach, D. Hennes, M. Lázaro-Gredilla and 13 others
  (Google DeepMind), arXiv:2510.04542v1, 2025-10-06. ICLR 2026 poster (ICLR
  virtual-site page opened).
- **Links:** https://arxiv.org/abs/2510.04542;
  https://iclr.cc/virtual/2026/poster/10011823.
- **What it reports:**
  - Method (abstract, §4): an LLM turns rules and a few trajectories into
    Python game code, refined until generated unit tests pass, then used by
    (IS)MCTS.
  - Value functions (§4.3): LLM-written value functions are **not refined**,
    because there is no ground truth. Several are generated and the best is
    picked by a tournament.
  - Result (abstract): the method beats or matches Gemini 2.5 Pro playing
    directly in 9 of 10 games.
- **What it means for Fork:** little for search heuristics. It confirms
  that the authors use matches as the only judge of LLM-written heuristic
  code.
- **Tag:** REFERENCE ONLY. **License:** arXiv CC BY 4.0. **Verified:** 2026-10-27.

##### Eberhardinger et al. (2024/2025): From Code to Play: Benchmarking Program Search for Games Using Large Language Models
- **Citation:** M. Eberhardinger, J. Goodman, A. Dockhorn, D. Perez-Liebana,
  R. D. Gaina, D. Çakmak, S. Maghsudi, S. Lucas, arXiv:2412.04057, v1
  2024-12-05, v2 2025-07-15 (read: v2). The arXiv comment says it was
  submitted to the IEEE Transactions on Games special issue; acceptance was
  not checked.
- **Links:** https://arxiv.org/abs/2412.04057.
- **What it reports:**
  - Method: LLM-driven hill climbing with repair attempts, across 29 tasks
    and 11 LLMs.
  - Tabletop games (§V-G, Tables VIII-IX, measured): LLMs wrote state-value
    heuristics for 12 TAG games, used inside one-step lookahead or MCTS.
    - each candidate was scored by a 500-game tournament; the final
      tournament had 25,000 games;
    - in 10 of 12 games some LLM's heuristic significantly beat the
      baseline score heuristic;
    - working-code rates were low, under 1 in 5 attempts for framework-heavy
      Java, often because of invented API methods;
    - there was no clear improvement across the 10 iterations of a trial,
      and the first heuristic was often the final winner;
    - total LLM cost per model for 1,200 iterations ranged from $0 (Llama
      3.1 70B, listed at 0.00) and $1.60 (Gemini 2.0 Flash, the top-ranked
      model) to $134 (Claude 3.5 Sonnet).
  - Long runs (§VI-VII, measured on MinAtar): more restarts beat more
    iterations, and one run per game did not reliably reach baseline
    performance.
- **What it means for Fork:** independent restarts (several islands seeded
  separately) and a check that the loop beats repeated fresh sampling.
  Expect a high share of invalid candidates; a strict gate is cheap.
- **Tag:** REFERENCE ONLY. **License:** arXiv CC BY 4.0. **Verified:** 2026-10-27.

##### Li et al. (2026): Beyond Static Evaluation: Co-Evolutionary Mechanisms for LLM-Driven Strategy Evolution in Adversarial Games
- **Citation:** H. Li, Z. Ge, Z. Zhang and 10 others (UCAS, Baidu AI Cloud
  and others), arXiv:2606.10389v1, 2026-06-09.
- **Links:** https://arxiv.org/abs/2606.10389.
- **What it reports:**
  - Setup: whole 500-1,700-line strategy files for a 3v3 capture-the-flag
    game, evolved with an OpenEvolve-style loop. It is compared with
    OpenEvolve and ShinkaEvolve, three runs each, with two LLMs.
  - **Proxy failure** ("Hierarchical Deep Evaluation", measured in a
    preliminary experiment): 3-game scores correlated with 20-40-game
    scores at Spearman 0.11 (p = 0.69). Fast scores are therefore used only
    for coarse ranking, and 20-game evaluations make the final decisions.
  - Other mechanisms: champions join the opponent pool, and the hardest
    opponents get more weight.
  - Limitations (authors): one domain, single-run ablations, 10 hours per
    benchmark checkpoint, and more than 30,000 LLM calls.
- **What it means for Fork:** a measured case of a cheap fitness carrying
  almost no rank information. Fork's pilot metric, the correlation between
  proxy and SPRT, is the right thing to measure first.
- **Tag:** REFERENCE ONLY. **License:** arXiv non-exclusive distribution
  licence. **Verified:** 2026-10-27.

##### Acher & Jézéquel (2026): Do programming languages still matter to your AI coding agent teammate? Evidence at scale from chess engines
- **Citation:** M. Acher, J.-M. Jézéquel (Univ Rennes, IRISA, CNRS, Inria),
  arXiv:2606.13763v1, 2026-06-11. The manuscript header names Empirical
  Software Engineering; acceptance was not checked.
- **Links:** https://arxiv.org/abs/2606.13763.
- **What it is:** not an evolution loop. Claude Code and Codex built 34
  chess engines in 17 languages. The engines were measured externally
  (perft, UCI games, Elo against Stockfish), and the transcripts were
  analysed.
- **Findings relevant to Fork (as read):**
  - *Self-measured Elo is biased upward* (§1, §6.1, measured against the
    authors' external assessment): 11 of 15 agent-written Elo scripts
    overestimated by 200 to 1,100 Elo. The cause: too few games per opponent
    and time controls too short. The authors note the agents used this
    signal to decide whether a change helped and when to stop. Four
    scripts landed within 150 Elo; two of those played 100 games at each of
    several Stockfish strength levels, which the authors single out as the
    choice that best kept the estimate honest.
  - *Copying* (§5.2): an audit using dependencies, library imports,
    fingerprints of distinctive constants and APIs from canonical engines,
    and transcript claims found no recognisable copies among the 29
    main-corpus engines. One engine secretly used a chess library (the
    "cheating" case, §6.3).
  - *Reproduced community constants* (§5.3, measured): the quiescence code
    shared a canonical skeleton and CPW vocabulary but little text (token
    overlap typically 15-30% across languages). Where a delta-pruning
    margin was present (11 of 26 engines), it always fell in one narrow
    range equal to the CPW article's value. The authors call it "the
    clearest smoking gun" of a shared specification. (The value is
    deliberately not written here.)
- **What it means for Fork:**
  - The most direct evidence for the owner's 2026-10-25 rule that models
    reproduce famous constants without opening any source. Every constant
    in an LLM candidate gets the originality screen, including values that
    "look" derived.
  - The self-Elo result is why the final judge must be a properly powered
    SPRT at a fixed protocol, never an LLM agent's own estimate.
- **Tag:** REFERENCE ONLY. **License:** arXiv CC BY 4.0. **Verified:** 2026-10-27.

#### Part C. Frameworks and methodology studies (not game-specific)

##### OpenEvolve (open-source AlphaEvolve implementation; README and metadata only)
- **Links:** https://github.com/algorithmicsuperintelligence/openevolve. The
  old URL github.com/codelion/openevolve redirects to the same repository
  (GitHub API 301 to repository id 984096689). README read through the
  GitHub API. Latest release v0.4.0, published 2026-09-28. Repository
  created 2025-05-15.
- **What the README says (README's own claims, not tested):**
  - It combines MAP-Elites with islands (example config: 5 islands,
    migration interval 20 with the unit unstated, feature dimensions such
    as complexity and diversity).
  - It has cascade evaluation, LLM feedback on code quality, an "artifact"
    channel that returns error output to the LLM, and optional novelty
    filtering by embedding similarity.
  - It calls runs "fully deterministic" through seeding; LLM sampling makes
    that doubtful (my note).
  - Per-iteration cost estimates by model are given.
  - The examples gallery lists no chess, board-game or engine example.
- **What it means for Fork:** confirms that the island plus MAP-Elites plus
  cascade design is now common open practice. Section 9's decision that
  Fork writes its own orchestrator stands. Using OpenEvolve as an external
  tool would be an owner decision; its licence allows it. No code was read.
- **Tag:** REFERENCE ONLY. **License:** Apache-2.0 (GitHub licence field).
  **Verified:** 2026-10-27.

##### Lange, Imajuku & Cetin (2025): ShinkaEvolve: Towards Open-Ended And Sample-Efficient Program Evolution
- **Citation:** R. T. Lange, Y. Imajuku, E. Cetin (Sakana AI),
  arXiv:2509.19349v1, 2025-09-17. Code: https://github.com/SakanaAI/ShinkaEvolve
  (licence field only).
- **What it reports (abstract, §3, Fig. 3, Fig. 9):**
  - parent sampling that balances exploration and exploitation;
  - a bandit that picks among an ensemble of LLMs;
  - **novelty rejection sampling**: the mutable code is embedded, and if
    its cosine similarity to an archived program is above a threshold, an
    LLM judges whether it is really new. In their circle-packing ablation,
    rejection sampling clearly beat no rejection (Fig. 9, measured on one
    task).
- **What it means for Fork:** two ideas.
  - Reject near-duplicates before paying for matches.
  - The same similarity machinery, pointed at a list of known published
    LMR formulas that the originality-checker maintains, could flag
    candidates that look like a known engine's formula before any
    evaluation. That use is Fork's idea, not the paper's. It would also
    need the name/constant-check rules (DESIGN.md §8): the list itself
    holds no code, only prose descriptions.
- **Tag:** REFERENCE ONLY. **License:** arXiv CC BY 4.0; repository
  Apache-2.0 (GitHub licence field). **Verified:** 2026-10-27.

##### Gideoni, Risi & Gal (2026): Simple Baselines are Competitive with Code Evolution
- **Citation:** Y. Gideoni (Oxford), S. Risi (Sakana AI, ITU Copenhagen), Y.
  Gal (Oxford), arXiv:2602.16805, v1 2026-02-18, v2 2026-10-12 (read: v2;
  the PDF footer says NeurIPS 2026).
- **Links:** https://arxiv.org/abs/2602.16805.
- **What it reports:**
  - Main result (abstract, §8, measured): two baselines matched or beat
    ShinkaEvolve and other pipelines at equal budget in all four domains
    tested. The baselines are (1) sampling many programs independently and
    keeping the best, and (2) sampling a new batch conditioned on random
    working programs from the last batch, with no fitness-based selection.
  - Search space and prompt (§4.1): the search space and the domain hints
    in the prompt mattered more than the search algorithm. The same
    pipeline found the published circle-packing bound 3 of 3 times with
    expert hints and 1 of 3 times without them.
  - Noise (§5): with noisy evaluation (agent scaffolds on AIME), every
    automated search picked scaffolds that fell more than 10% from
    validation to test, and lost to a plain majority vote. Re-evaluated 10
    times, ShinkaEvolve and random sampling were indistinguishable
    (probability of improvement 0.49).
  - Fixes (§5.1, §8): an evaluation cascade that re-tests the top 20% on
    more samples (estimated 2x cheaper than evaluating everything more
    deeply), selection by "probability of dominance", and re-evaluating
    final picks several times with confidence intervals.
- **What it means for Fork:**
  - The pilot needs a **no-evolution control arm**: the same budget spent
    on independent LLM proposals with the same gate and funnel. Without it,
    a gain cannot be credited to the islands or MAP-Elites.
  - Fork's prompt (the LMR context it gives) is part of the experiment and
    must be logged with the results.
- **Tag:** REFERENCE ONLY. **License:** arXiv CC BY 4.0. **Verified:** 2026-10-27.

##### Oved, Pony, Naparstek & Barzelay (2026): Evolution or Illusion? Rethinking Evaluation in LLM Evolutionary Search
- **Citation:** T. Oved, R. Pony, O. Naparstek, U. Barzelay (IBM Research),
  arXiv:2609.19799v1, 2026-09-17.
- **Links:** https://arxiv.org/abs/2609.19799.
- **What it reports:**
  - Setup (§3): three strategies (OpenEvolve, EvoX, AdaEvolve) on systems
    tasks, all with gpt-5-mini, over a grid of 40 seeds x 200 iterations.
    The authors note one evaluator was incomplete and let an exploit
    through.
  - Results (§4, Tables 1-2, measured):
    - the best split between more seeds and more iterations changes with
      strategy, task and budget;
    - depth sometimes saturated early (AdaEvolve at 40 iterations on one
      task, EvoX at 60 on another);
    - strategy rankings changed between 1 seed and 40 seeds; on one task
      the worst strategy at one seed was best at forty;
    - with more seeds, a "4x better" program turned out to be a validator
      exploit.
  - Recommendations (§5): report the seeds-by-iterations frontier, run
    several seeds, and tune depth per task.
- **What it means for Fork:** a single pilot run cannot rank Fork's design
  choices. Budget for several independent runs, prefer more islands or
  seeds to longer runs, and treat any outlier gain as a possible gate
  exploit until a full SPRT confirms it.
- **Tag:** REFERENCE ONLY. **License:** arXiv non-exclusive distribution
  licence. **Verified:** 2026-10-27.

#### Lessons for Fork's pilot (synthesis of Parts A-C)

These are Fork's conclusions drawn from the sources above, not claims made
by any one source.

1. **Validate the proxy before trusting it.**
   - Two measured proxy failures:
     - GoTools' no-search rank proxy did not carry over to test sets;
     - FAMOU's 3-game score correlated with deep evaluation at only
       Spearman 0.11.
   - Two proxies that worked, each confirmed by games:
     - RSPSA's move score from the engine's own deeper search;
     - node counts on a suite, in David et al., though with an
       underpowered match.
   - Björnsson and Marsland never played games at all. Make the
     proxy-to-SPRT correlation the first pilot result, on positions held
     out from any proxy tuning, and include hard positions.
2. **Fitness noise picks lucky candidates.**
   - Single-seed rankings flip (Oved et al.).
   - Noisy selection loses to simple baselines (Gideoni et al.).
   - Restarts beat longer runs (Eberhardinger et al.).
   - Use a cascade that re-measures the top candidates on more data, and
     re-measure an elite before it can hold a MAP-Elites cell or be
     promoted. Promote only on a fresh-seed confirmation, as Li et al. do,
     and finally by SPRT.
3. **Run a control arm.** Spend the same budget on independent LLM proposals
   (no islands, no archive) through the same gate and funnel. Log the
   prompt and context, since prompt knowledge changes results.
4. **Expect over-fitting and over-engineering.** Distil every survivor by
   ablation (Li et al. 2602.16928). Keep the evolve block small and
   code-size-gated (Li et al. 2609.33115). Score an LMR change against a
   fixed version of the rest of the engine, so that it cannot free-ride on
   other changes.
5. **Gate exploits, not just crashes.** Published loops met clairvoyance
   through pointer casts, validator exploits, a secret library import and
   division-by-zero edge cases. Fork's gate should check that the diff
   stays inside the LMR function and reads only the allowed inputs, plus
   bench, perft and sanitiser runs.
6. **Never use agent-reported strength.** Self-measured Elo was 200-1,100
   too high in Acher and Jézéquel's corpus. Only the fixed-protocol SPRT
   counts.
7. **Originality.**
   - Models reproduce community constants exactly (Acher and Jézéquel
     §5.3).
   - Papers publish evolved search values (David et al. Table II).
   - The GGP paper's novelty argument is reasoning only.
   - So every constant and formula in a candidate goes through the
     originality-checker before any commit. Consider an automated
     similarity pre-screen against prose descriptions of known LMR
     formulas (ShinkaEvolve-style; Fork's idea).
8. **Cost per accepted change is unreported.** No source gives "compute per
   accepted engine change". The nearest figures are:
   - about 6,400 candidates and about $5,400 of tokens per run (Li et al.,
     authors' estimate);
   - more than 30,000 LLM calls and 10-hour checkpoints (FAMOU);
   - $0-$134 per model for 1,200 iterations (Eberhardinger et al.).

   Fork should record LLM tokens, CPU-hours per stage and accepted SPRTs as
   pilot outputs.
9. **SPSA stays.** LLM search changes structure; SPSA tunes the constants of
   a fixed structure from game pairs, needs tens of thousands of games and
   a manual stop (Kiiski). Run them in that order.
10. **Data provenance.** Several precedents used another engine as the
    yardstick (Crafty node counts, ECM suites as fitness, Stockfish
    opponents). Fork's proxies use only Fork's own deeper search and
    Fork-generated positions, and third-party suites stay test-only (data
    policy).

#### Unverified (this subsection)

- **Gross, Albrecht, Kantschik & Banzhaf (2002), "Evolving Chess Playing
  Programs", GECCO 2002, pp. 740-747** (citation as given in the 2014 David
  et al. reference list). The Internet Archive copy of
  naturalrobotics.group.shef.ac.uk/publications/gecco02.pdf downloaded, but
  its text layer is unreadable (font encoding), and the live link did not
  resolve. Its "6% of alpha-beta's nodes" result is known here only through
  Hauptman and Sipper's summary. No DOI was found on Crossref.
- **Mitsuta & Schmitt (2010), "Optimizing the Performance of GNU-chess with
  a Genetic Algorithm"** (CPW citation, HC 2010). The CPW PDF link (wlu.ca)
  returns a 404 page, the Internet Archive has no copy, and Crossref found
  no match. Content not read.
- **Kocsis & Szepesvári (2006), Machine Learning 63(3):249-286:** only the
  Crossref metadata was checked; the text was not read. The RSPSA ACG
  paper's LNCS volume number was not confirmed (Crossref gives series and
  pages only).
- **Hauptman (2009) thesis** and **Kantschik (2006) thesis** (CPW
  bibliography): not opened.
- **CPW "GA in Falcon" page:** 404 on 2026-10-27.
- **Venue status:** IEEE ToG for Eberhardinger et al. and Empirical Software
  Engineering for Acher and Jézéquel are as stated in arXiv comments or
  headers; acceptance not checked. NeurIPS 2026 for Gideoni et al. is from
  the PDF footer only.
- **Absence of chess-engine LLM-evolution work:** see the headline above.

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
  pp. 99-109, April 1990. DOI 10.1016/0004-3702(90)90073-9. The subtitle
  "Adding Selectivity to Brute-Force Searching" belongs to the earlier
  version (AAAI Spring Symposium 1988; ICCA Journal 11(4), 1988, pp. 135-143
  per Winands et al.'s reference list), shown on CPW's Singular Extensions
  page (resolved 2026-10-24, search-techniques.md).
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
- **Slate & Atkin's book editor** (P. W. Frey): from common usage, not
  shown on any opened page. (The Anantharaman et al. subtitle was resolved
  on 2026-10-24: it belongs to the 1988 version; see the entry above.)
- **Licenses:** CLOP software license and Fishtest repository license were
  not found.
