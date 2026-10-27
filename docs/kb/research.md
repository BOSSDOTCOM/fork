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
  fetched page; re-checked 2026-10-24: GitHub API reports **GPL-3.0** for
  official-stockfish/nnue-pytorch (do not copy code either way). Verified 2026-10-23. Tag: **REFERENCE ONLY**.

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
