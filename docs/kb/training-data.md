# Training data for Fork's NNUE: sources and strategy

Written 2026-10-24 for the Phase 4 data decision. Research and planning only:
no pipeline, no bulk downloads. Every fact below comes from a page or file
opened on 2026-10-24 (logged in [sources.md](sources.md), section "Training
data"). Anything not confirmed is marked **UNVERIFIED**. Statements marked
*estimate* are Fork's own arithmetic, with the assumptions given. The
status of each source is summarised in [data-policy.md](data-policy.md).

Samples inspected (106 MB plus 47 MB, kept only in the session scratchpad,
none in the repo, opened only by inspection scripts): one Lc0 test91 chunk, one Lc0
"cleanvisits" V7 chunk, the full Lichess 2013-01 month, the first 20 MB of
the Lichess 2026-09 month and of the Lichess eval DB, the first 5 MB of the
puzzle DB, one CCRL per-engine PGN, one TCEC archive PGN.

---

## 0. Summary

- **Fork is Category 4 whatever data it uses (today).** TCEC put CatGPT
  (AI-written, over 99 % Lc0 training data) in Category 4, not Category 3
  or 5. Cinder, a non-AI engine on Stockfish and Lc0 data that admits it
  breaks the NNUE Guideline, was placed in Category 3 and won the S30
  Cat 3+4 playoff. No written rule says how the AI trait and the data trait
  combine (**UNVERIFIED** as a rule; it is a precedent).
- **Category 2 is closed to Fork regardless of data**, because Category 4
  is about how the code was written. So "lock-in if Fork ever wants
  Category 2" only matters if TCEC changes its AI policy (the TD statement
  mentions possible "separate and/or joint competitions"). In that case
  data origin could start to matter again.
- **What Lc0 data really costs Fork** is therefore not a category but:
  - the NNUE Guideline's rule 3 (questionnaire Q10). The guideline is
    unofficial, but it is still asked about;
  - the originality story. "AI-written code plus Lc0 data" is exactly the
    CatGPT profile;
  - the clean provenance chain. Once one net in the chain has seen Lc0
    data, every later self-play label comes from a search guided by that
    net, and restoring a clean chain means starting again from scratch;
  - the risk that TCEC's rules tighten.
- **Every Stockfish-touched source is OFF-LIMITS.** That covers the
  Lichess eval DB, `[%eval]` comments in Lichess games, the puzzles,
  CCRL/CEGT/TCEC/fishtest games, laion, ChessBench, the Stockfish books and
  the relabel sets.
- **Clean external inputs exist and cost Fork nothing in originality:**
  - Lichess game moves (CC0, human), as start positions;
  - Syzygy WDL, as exact labels for positions with 7 pieces or fewer.
- **Recommendation: strategy A+.** Use own self-play labels only, and add
  the two clean external inputs above. Lc0 data stays excluded, with a
  documented review gate (section 3.4). Two hardware limits affect every
  strategy and need the owner's decision first (section 3.1): **no CUDA
  GPU** (bullet trains only on CUDA, ROCm or Metal) and **45 GB free disk**.

---

## 1. Per-source evaluation

Columns used throughout: **TCEC** = the category effect for Fork as a
Category 4 engine, and for a hypothetical non-AI Fork in brackets.

### 1.1 Lc0 public training data (storage.lczero.org)

**What it is**
- About **28 TB** of self-play games from Leela Chess Zero training runs,
  under https://storage.lczero.org/files/training_data/.
- Each run is a `testNN` folder; there are no "T80" or "BT4" names.
- Files are one `.tar` per hour, each holding one gzip file per game.

| Run | Size | Dates | Notes |
|---|---|---|---|
| test60 | 5.72 TB | 2019-07 to 2022-04 | used in nnue-pytorch's examples |
| test75 | 6.13 TB | 2021-03 to 2021-12 | |
| test79 | 2.67 TB | 2022-02 to 2022-05 | |
| test80 | 9.36 TB | listing starts 2024-04; last non-empty 2025-09-24 | runs page: started 2022-04-04, 10,000 visits; where the 2022-24 part went is **UNVERIFIED** |
| test91 | 1.62 TB | 2025-12-20 to today | **still growing**; 800 visits, BT4 RL "debug run" |
| cleanvisits, k2hybrid (V7) | 0.06 / 0.04 TB | July 2026 | third-party "Kovax" sets: 800-visit self-play by lc0 forks, **UHO openings among others**, rescored with 7-man Syzygy |
| test30, test40, others | about 2.9 TB | 2018-2021 | older and weaker nets |

**Format**
- Version 6 records are 8,356 bytes each; version 7 records are 8,396 bytes.
- Per position a record holds:
  - 104 bitboard planes (the current position plus 7 earlier ones);
  - the policy target: 1,858 floats giving the root visit distribution;
  - Q/D/M (expected score, draw probability, moves left) at the root, for
    the best move, for the played move, and the raw net eval;
  - the game result, plies left and visit count.
- Whole games are recorded, not sampled positions.
- Measured in the samples:
  - about 200-290 bytes per position gzipped;
  - about 3.3-4.8 million positions per GB of tar;
  - so test80 alone holds about 45 billion positions (*estimate*).

**Labels**
- These are Lc0's own search statistics (MCTS visits) and game results,
  produced by Lc0 nets.
- Raw test91 is not rescored (the sample is V6 and its `q_st` field is
  zero).
- Lc0's `rescorer` tool can apply Syzygy, "deblunder" the labels, and write
  Stockfish's `.plain` format, with Q converted to centipawns by a fixed
  formula.
- **No Stockfish involvement in the raw self-play runs** (Lc0 vs Lc0).
- Two caveats:
  - The Kovax V7 sets use UHO openings, whose selecting engine is
    **UNVERIFIED** and is likely Stockfish.
  - The linrock relabel sets on Hugging Face mix in Stockfish data; they
    are a different source and are OFF-LIMITS.

**License**
- **ODbL 1.0** covers the collection and **DbCL 1.0** the contents
  (LICENSE.txt in the folder and inside every tar). VERIFIED.
- ODbL §4.3 asks for a notice on any public "Produced Work". Stockfish and
  Alexandria put an acknowledgement line in their README.
- The catch is §4.4c with §4.6: if a public Produced Work is made from a
  *Derivative Database*, that database (or the method used to build it)
  must also be offered. A converted or filtered binpack is a Derivative
  Database.
- Whether a trained net legally counts as a "Produced Work" is
  **UNVERIFIED**. Projects act as if it does.

**TCEC**
- For Fork (Cat 4): no change (CatGPT precedent).
- For a non-AI Fork: Category 3 ("leela data" in Swiss 7; "Other" in the
  flowchart).
- Breaks the NNUE Guideline rule 3 in either case.

**Positives**
- The best freely available labels in chess: deep MCTS evaluations, a
  draw probability and a game result for every position.
- Effectively unlimited scale (tens of billions of positions).
- Proven: Stockfish's README says its nets were trained on it; the SF18
  notes say over 100 billion positions, and the SF17 notes call it
  "essential". Alexandria, Obsidian and CatGPT use it too.
- **Compute saved**: generating the labels costs Fork nothing. It would
  take Fork's own self-play months to match the volume (section 3).
- **Time saved**: weeks for the first strong net (section 3).

**Negatives**
- **Storage**
  - 1 billion positions is about 210-300 GB of tars, against 45 GB free.
  - So the data must be streamed (download a tar, convert it, delete it).
  - Converted to a compact format of about 2-3 bytes per position, a
    billion positions is about 2-3 GB (*estimate*; Stockfish binpack doc).
  - Conversion speed is **UNVERIFIED**.
  - The rescorer streams one game at a time, so RAM should be fine.
- **Style and blind spots**
  - Fork would learn Lc0's evaluations of the positions Lc0 chooses to
    play: its opening repertoire, its preference for certain structures,
    and at 800 visits its tactical misses.
  - The labels are value-net and MCTS outputs, not alpha-beta search.
  - Stockfish's own wiki says training only on Lc0 data was worse than
    first training on Stockfish data and then retraining on Lc0 data. In
    short, Lc0 data alone is not the whole recipe.
- **Originality perception**: AI code plus borrowed data leaves Fork with
  little that is its own beyond search. This is the CatGPT profile.
- **Rule risk**: the NNUE Guideline appeared in formal rules up to S20 and
  Cup 7/8. If TCEC turns it back into a rule, or applies it to joint
  competitions, Fork would have to retrain from scratch on short notice.
- **Lock-in**: a provenance chain that includes Lc0 cannot be cleaned
  later without restarting from HCE or a random init.
- **Licence**: share-alike obligations apply to any converted dataset that
  is published or used for a public net.

### 1.2 Lichess open game database (database.lichess.org)

**What it is**
- 8.22 billion rated standard games in 165 monthly PGN files (zstd),
  about 2.6 TB compressed. Recent months are about 29-31 GB and about 90
  million games each.
- Measured: 2013-01 holds 121,331 games (about 459 million positions per
  compressed GB, 67 plies per game). A slice of 2026-09 gives about 203
  million positions per compressed GB.

**Labels**
- Human moves, game result, Elo, and `[%clk]` clock comments from 2017.
- About 6 % of games carry `[%eval]` comments. These are **Stockfish**
  evals from fishnet; fishnet's submodule today points at Stockfish 19,
  and older months used older versions (**UNVERIFIED** per month).
- Games by BOT accounts (`[WhiteTitle "BOT"]`) contain engine moves.

**License**
- **CC0**, stated on the database page. VERIFIED.

**TCEC**
- Moves as start positions: no category effect (it is not engine data).
- Positions rescored by Fork are "own search and eval" under the
  guideline's letter. How the flowchart's "Hybrid" class treats them is
  **UNVERIFIED** (Discord question).
- Game results as labels: unclear. Human results are not engine data, but
  they are "not own data" either (**UNVERIFIED**).

**Positives**
- Huge variety of realistic positions and openings, which solves
  datagen opening diversity cheaply.
- No licence friction.
- Viridithas trains on Lichess Elite positions rescored by itself
  (competition.md).

**Negatives**
- Human-level positions, including many blunders and lopsided positions.
- Results from amateur games are noisy labels; using them directly is
  weak and of questionable value.
- Every file must be stripped of `[%eval]` and BOT games before use.
- Storage: one month of positions is about 30 GB compressed, so a small
  filtered extract (millions of start FENs) is the practical form.
- Rescoring with Fork costs the same compute as self-play labelling; only
  the game moves are saved.

**Status**
- **ALLOWED** for start positions and opening books, after the
  `[%eval]` and BOT filters.
- **ALLOWED** as positions to be rescored by Fork, with this marked as a
  grey area in originality.md §3 and as a Discord question.
- **OFF-LIMITS**: the `[%eval]` values.

### 1.3 Lichess evaluated-positions database

**What it is**
- `lichess_db_eval.jsonl.zst`: 22.4 GB, 416 million positions, CC0.
- Each position has a list of evals with depth, knodes and multi-PV
  lines. Measured median depth 28 and median knodes 35k.

**Labels**
- **Stockfish**, "various flavours" running in users' browsers.
  VERIFIED.

**Status**
- **OFF-LIMITS** (Stockfish labels).
- Using only its FENs as start positions is also excluded, because the
  positions were chosen by Stockfish-assisted analysis. The plain game
  database is cleaner for that.

### 1.4 Lichess puzzles

**What it is**
- 6.16 million puzzles, CC0.
- Generated by re-analysing positions "with Stockfish NNUE at 40
  meganodes".

**Status**
- **OFF-LIMITS** for training.
- Using them as a tactics test suite is an owner decision. They would not
  enter any net.

### 1.5 Other human-game collections

| Collection | Size | Licence | Notes | Status |
|---|---|---|---|---|
| Lichess Elite (database.nikonoel.fr) | about 4 GB plus monthly zips | **UNVERIFIED** (derived from CC0) | 2400+ vs 2200+ players, later 2500+ vs 2300+; eval stripping **UNVERIFIED** | UNVERIFIED (licence) |
| Lichess Broadcasts (HF Lichess/tournament-chess-games) | 931k games | CC-BY-SA 4.0 | OTB and online tournaments; has `[%eval]` comments | ALLOWED (moves; attribution) |
| FICS games DB | 269 million stored | **UNVERIFIED** | includes computer-vs-computer and computer-vs-human sets | UNVERIFIED |
| Caissabase / KingBase / angeluriot/chess_games | 4-14 million master games | **UNVERIFIED** (opinion "moves are facts") | curated master games | UNVERIFIED |
| Chess.com PubAPI | per player only | **UNVERIFIED** terms | no bulk dump | UNVERIFIED |

These add nothing that Lichess CC0 lacks for start positions, so none is
needed.

### 1.6 CCRL, CEGT and other engine-game archives

**What they are**
- CCRL 40/15: 2.47 million games in one 477 MB 7z, or 1.48 GB with
  comments. The comments look like `{+0.19/13 23s}`, the playing engine's
  own eval. 4,776 programs, Stockfish 19 among them.
- CEGT: about 1.4 GB of commented 40/20 games, plus other lists.
- Fishtest: per-run PGN downloads of Stockfish vs Stockfish games.
- OpenBench instances: games of whatever engines each instance tests.

**Licence**
- **UNVERIFIED** for CCRL, CEGT and fishtest; none is stated.

**Status**
- **OFF-LIMITS**. Moves and evals come from many engines, including
  Stockfish and its many derivatives and Lc0-data engines.
- Filtering out "Stockfish games" cannot make them clean, because one
  cannot certify which engines use Stockfish code or data.
- **REFERENCE ONLY** for rating context and opponent study.

### 1.7 TCEC game archives (github.com/TCEC-Chess/tcecgames)

**What it is**
- 780 PGN files (about 2.4 GB), plus release packs up to "S29-final"
  (7 Jun 2026; the full pack is 507 MB as 7z).
- The "full" format keeps per-move engine comments: depth, seldepth,
  nodes, pv, tablebase hits and `wv` (eval).

**Licence**
- PGNs are **CC BY-SA 3.0** and scripts Apache-2.0, per the README. There
  is no LICENSE file. tcec-chess.com terms are **UNVERIFIED**.

**Status**
- **OFF-LIMITS** for training: Stockfish and Lc0 moves and evals
  throughout.
- **REFERENCE ONLY** for time-use statistics, adjudication behaviour and
  opening-book analysis (Phase 5 and 8).

### 1.8 Syzygy tablebases

**What it is**
- Exact win/draw/loss (WDL) and distance-to-zeroing (DTZ) for every
  position with 7 pieces or fewer, aware of the 50-move rule.

| Pieces | WDL | DTZ |
|---|---|---|
| 3-4-5 | 0.40 GB | 0.59 GB |
| 6 | 72.8 GB | 87.4 GB |
| 7 | 9.3 TB | 9.1 TB |

- 3-4-5 are already installed in WSL (`~/fork-tools/syzygy`, 939 MiB).

**Labels**
- These are **not produced by an engine's search**; they are retrograde
  analysis.
- The generator `syzygy1/tb` is GPL-2.0, but it is a tool and none of its
  code enters Fork. No licence on the table files was found
  (**UNVERIFIED**). They are distributed freely and used by every engine.

**TCEC**
- No rule mentions tablebases as training labels (**UNVERIFIED** how the
  flowchart classifies them; Discord question).
- Using them is the same knowledge Fork already probes in search via
  Fathom.

**Positives**
- Perfect labels, free.
- Fixes the classic weakness of self-play nets in endgames: draws
  mislabelled as wins, and the 50-move rule.
- Already on disk for 5 pieces.

**Negatives**
- They only cover positions with 7 pieces or fewer. The share of such
  positions in typical NNUE training data is **UNVERIFIED**; a biased
  sample showed about 17 %. They are a label *correction*, not a data
  source.
- 6-man WDL (73 GB) does not fit in the current 45 GB free.
- 7-man tables are out of reach on this machine.
- During search the engine probes the tablebases anyway, so the gain is
  in eval quality near the 6- and 7-man boundary, not inside it.

**Status**
- **ALLOWED** (WDL rescoring of Fork's own self-play and positions with
  7 pieces or fewer, plus adjudicating self-play games).

### 1.9 Other public datasets

| Dataset | Labeller | Licence | Status |
|---|---|---|---|
| ChessBench (DeepMind searchless_chess) | Stockfish 16 | CC0 + CC-BY 4.0 | OFF-LIMITS |
| laion/strategic_game_chess | Stockfish self-play (3.2 billion games) | CC-BY 4.0 | OFF-LIMITS |
| Stockfish nnue-pytorch datasets, HF linrock_relabel_* | Stockfish and/or Lc0 | not stated | OFF-LIMITS |
| chessdb/snapshots (chessdb.cn, 64 billion positions) | **UNVERIFIED** scorer | LGPL-3.0 | OFF-LIMITS until the scorer is verified |
| official-stockfish/books (UHO, 8moves, popularpos) | UHO selected by an engine-eval window, engine **UNVERIFIED** | CC0 | OFF-LIMITS (Stockfish project; selection likely Stockfish) |
| mitermix/chess-selfplay | **UNVERIFIED** (empty card) | Apache-2.0 | UNVERIFIED |
| Kaggle sets | not reviewed | | UNVERIFIED |

---

## 2. Machine constraints that shape every strategy

| Resource | Value | Effect |
|---|---|---|
| CPU | Ryzen 5 7600X3D, 12 threads, AVX-512 | Datagen is CPU-bound and linear in threads. One heavy job at a time (owner rule), so datagen blocks `check.sh full`, benchmarks and tests while it runs. |
| RAM | about 15 GB, shared with other sessions | Fine for datagen (small hash per game) and streaming conversion. Not enough for in-memory shuffling of billions of positions; shuffle on disk instead. |
| Disk | **45 GB free** on C: (WSL lives there too) | About 15 billion positions at about 3 bytes each (binpack-like), but only about 1.4 billion at 32 bytes each (*estimate*). Bulk Lc0 tars must be streamed. 6-man Syzygy WDL does not fit. |
| GPU | **Radeon RX 580** (4 GB, Polaris/gfx803), no NVIDIA | bullet trains on CUDA, ROCm or Metal only; there is no CPU backend. Whether ROCm/HIP supports gfx803 is **UNVERIFIED**; current ROCm releases are widely reported not to support it. So training needs one of: a rented or other CUDA GPU, a working HIP setup, or Fork's own CPU trainer (techniques.md already lists that option). |

The GPU question is independent of the data strategy, but it decides the
timeline more than the data does. The owner's answer is in section 2.1.

### 2.1 Training compute: Kaggle, Colab, ROCm (checked 2026-10-24)

The owner's plan (2026-10-24): datagen on the local CPU, training on
Kaggle first, Colab as backup, rented CUDA last. The Kaggle pages block
plain fetching, so they were rendered in a headless browser; the official
pages themselves were read, not mirrors.

**Kaggle Notebooks** (kaggle.com/docs/notebooks, /docs/efficient-gpu-usage;
Kaggle CLI docs kernels.md, 2026-10-22)

| Limit | Value | Status |
|---|---|---|
| Weekly GPU quota | 30 h, "sometimes more" depending on demand; resets weekly | VERIFIED |
| Session length | 12 h, including "Save & Run All" batch (commit) runs | VERIFIED |
| GPU session hardware | T4 x2 (default) or P100, each with 4 CPU cores and 29 GB RAM | VERIFIED |
| Newer GPU types | The CLI lists A100, L4, H100 and RTX Pro 6000, some only for competitions or admins | Which ones a free user gets: **UNVERIFIED** |
| Persistent output | `/kaggle/working`, 20 GB, saved | VERIFIED |
| Scratch disk | Exists, lost at session end; size not stated | **UNVERIFIED** |
| Idle timeout (interactive) | 20 min on one official page, 60 min on another | **conflicting**; commit runs are unaffected |
| Internet | A per-notebook setting, on by default | GPU plus internet together (needed for `cargo` to build bullet) **UNVERIFIED**. Fallback: build bullet once and attach the binary as a dataset |
| Phone verification for GPU or internet | Stated only on forums | **UNVERIFIED** |

**Kaggle Datasets** (kaggle.com/docs/datasets; Kaggle CLI docs datasets.md)

| Limit | Value | Status |
|---|---|---|
| Size per dataset | 200 GB | VERIFIED |
| Private datasets per account | 200 GB total (make some public or delete them beyond that) | VERIFIED |
| Files | at most 50 top-level files; use subfolders for more | VERIFIED |
| Archives | ZIP/7z are unpacked on Kaggle's side | VERIFIED; so upload the shards as plain files |
| Upload | web, remote URL, GitHub, notebook output, kagglehub, CLI | VERIFIED |
| CLI commands | `kaggle datasets create -p DIR` (private by default), `kaggle datasets version -p DIR -m MSG [-d]` (`-d` deletes old versions) | VERIFIED |
| Data sources per notebook | several allowed | VERIFIED |
| Max file size, per-method upload limit, resumable uploads, read speed | not stated | **UNVERIFIED** |

**Kaggle terms** (kaggle.com/terms and /aup, both effective 2025-06-22)
- Use must be personal and non-commercial. A GPL hobby engine looks
  compatible; that is a reading, not legal advice.
- The AUP bans "activity unrelated to ML data science", along with mining
  and server farming. NNUE training is ML. Self-play datagen on Kaggle
  could be read as unrelated, which is one more reason datagen stays
  local.
- Kaggle takes a licence to operate the service with user content, but
  ownership is not affected. No claim on trained outputs was found, so
  publishing nets under GPL-3.0 is not blocked.

**Google Colab** (research.google.com/colaboratory/faq.html, made binding
by the Colab Additional Terms tos_v5, 2024-05-14)
- **"Chess training" is on the list of activities not allowed on free
  runtimes** without a positive compute-unit balance. Such runtimes may
  be ended without warning. VERIFIED.
- So **the free Colab tier cannot be the backup**. Only paid Colab with
  compute units (where the restriction does not apply) or rented CUDA
  can.
- Other limits:
  - Free sessions last at most 12 h.
  - Usage limits are dynamic and not published.
  - Which GPU the free tier gets is not stated (**UNVERIFIED**).
  - Disk size is not stated (**UNVERIFIED**).
  - Google Drive gives 15 GB shared with Gmail and Photos.
  - Using several accounts to dodge limits is banned.

**ROCm and the RX 580 (gfx803)**
- Not supported:
  - The current Linux ROCm compatibility matrix lists gfx908 and newer
    only.
  - The Windows HIP SDK 7.2.0 starts at the RX 6600.
  - ROCm 7.0.0 deprecated gfx8 on Windows.
  - All VERIFIED. The release in which gfx803 first left official
    support is **UNVERIFIED**.
- The RX 580 cannot be used for training.

**Practical constraints for Phase 4**
- About 30 GPU hours a week, in runs of at most 12 h each. Training must
  checkpoint to `/kaggle/working` and resume across runs.
- bullet uses one T4 unless multi-GPU is set up.
- Training data:
  - Keep each dataset at about 50-100 GB, so that versions fit under the
    200 GB private quota, or delete old versions with `-d`.
  - Shard it into at most 50 top-level files or subfolders, uploaded
    unarchived.
  - With 29 GB of RAM, anything larger has to be streamed from the input
    mount, not loaded whole.
- The upload goes over the owner's home connection: a 30 GB dataset at
  50 Mbit/s up is about 1.5 h (*estimate*).
- Before relying on Kaggle, check with one test session:
  - phone verification;
  - whether internet works in GPU sessions;
  - scratch disk size;
  - which idle timeout applies;
  - the maximum file size.

---

## 3. Strategy comparison

Common assumptions for the estimates (*estimate*, not measured: Phase 3
search does not exist yet):

- Self-play datagen at about 5k nodes per move. Fork's NPS is assumed at
  about 0.7-1.5 M per thread with a small net (HCE is faster), on 10 of
  the 12 threads.
- That gives about 1,500-3,000 positions per second, or **about 130-260
  million positions per day**.
- A "strong first net" here means a single-layer 768→N net with king
  buckets trained on 0.5-1 billion positions.
- For calibration from other engines:
  - Reckless v0.5.0 went from HCE to about CCRL 3240 with its own data
    from a random net (competition.md).
  - PlentyChess and Caissa report 15-20+ billion positions of their own
    data for their mature nets (competition.md).
- Training time is excluded, because it depends on the GPU answer. On a
  rented consumer CUDA GPU, a 1-billion-position run is hours, not days
  (**UNVERIFIED** for Fork's net size).

### 3.1 A) Own self-play data only

| | |
|---|---|
| Time to a strong first net | Gen 0: 100-200 million positions labelled by Fork's PST search, about 1 day. Then 3-5 generations of 200 million to 1 billion positions each: **about 3-6 weeks of machine time** (*estimate*), interleaved with training. |
| Compute | About 1-2 billion positions for the first strong net, about 10-15 billion for a mature one. At about 200 million per day the mature set is **2-3 months of continuous CPU** on this machine, or less on rented or donated CPU. |
| TCEC | Cat 4 (unchanged). Fully meets the NNUE Guideline; questionnaire Q8 and Q10 are trivial to answer; the clean chain back to HCE holds. If TCEC ever merges AI engines into the normal flowchart, this is the "Original" branch (the best placement). |
| Long-term upside | Highest. Fork's data improves with Fork's search, its style is Fork's own, there is no rule risk, and the originality story is "the AI wrote it, Fork taught itself". The infrastructure (datagen, filtering, rescoring) is needed in every strategy anyway. |
| Downside | Slowest start; early generations inherit PST blind spots. The machine is the bottleneck for months. |

### 3.2 B) External data only (in practice: Lc0, the only strong non-Stockfish source)

| | |
|---|---|
| Time to a strong first net | Building the conversion pipeline is about 1 week (lc0 rescorer to a plain or binpack-like format, a Q-to-centipawn mapping, filtering). Streaming 1 billion positions means about 210-300 GB of downloads converted and deleted on the fly: **days** (*estimate*; throughput **UNVERIFIED**). First strong net in **about 1-2 weeks** if the GPU question is solved. |
| Compute | Almost no datagen; only conversion, and network bandwidth. |
| TCEC | Cat 4 (unchanged today, per CatGPT). Breaks NNUE Guideline rule 3, so Q10 must answer "no". A hypothetical non-AI Fork would be Cat 3. |
| Long-term upside | Lowest. Strength is capped by Lc0's positions and labels (Stockfish's wiki: Lc0 data alone underperformed a mixed recipe). Fork would have no datagen of its own, inherit Lc0's style, and carry a permanent ODbL notice. Rule-tightening risk and lock-in are both total. |
| Downside | It is also not "free": the pipeline is different from the one Fork needs later, and labels converted from Q to centipawns need their own tuning. |

### 3.3 C) Hybrid: bootstrap from Lc0, then Fork's own self-play

| | |
|---|---|
| Time to a strong first net | As B (about 1-2 weeks), then the transition: Fork's datagen labelled by the Lc0-bootstrapped net. |
| Compute | As B at first, then as A. It saves roughly the first 3-5 weeks of A's generations (*estimate*). |
| TCEC | Cat 4 today. The guideline is broken for every net in the chain, including the later "own data" nets, because their labels came from a search guided by an Lc0-trained eval. "Own data" in TCEC's sense is ambiguous here (**UNVERIFIED**; Discord question). A clean status needs a full restart from HCE. |
| Long-term upside | Close to A in strength once transitioned, but the provenance is permanently mixed. Building both pipelines costs more engineering than A or B alone. |
| Downside | It buys about a month of early strength at the price of the one thing a Category 4 engine can still claim as its own. Phase 4's first net only has to beat Fork's PST eval, and early on Fork's strength is limited by search more than by net quality. |

### 3.4 A+) Own labels, clean external inputs (the recommended variant)

Strategy A, plus:

1. **Lichess CC0 game positions as datagen openings.** Take a few million
   FENs from the 8-16 ply range of games between 2000+ rated players,
   after dropping BOT games and `[%eval]` comments, then randomise a few
   plies further. This solves opening diversity without any engine
   labels.
2. **Syzygy WDL as labels.**
   - Adjudicate self-play games as soon as 5 pieces or fewer remain
     (6 once the disk allows).
   - Overwrite the result label of positions with 7 pieces or fewer that
     the local tables cover.
   - This saves datagen time (shorter games) and fixes endgame labels.
3. **Rescoring with newer Fork nets**, already planned in techniques.md
   §5.

Effect:
- Same category and compliance as A.
- It removes A's two practical weaknesses: poor opening variety from
  random moves, and noisy endgame labels.
- It shortens games by about 10-20 % (*estimate*).
- Time to a strong first net is still **about 3-6 weeks of machine
  time**.

**Review gate** (owner, 2026-10-24): revisit Lc0 data, whichever comes
first:
- two consecutive net generations each gain less than about 10 Elo
  (SPRT against the previous generation), or
- 4 generations, or 2 billion own positions.

Revisiting means an owner decision on measured numbers. Revisiting is
cheap if the datagen pipeline already exists. Leaving Lc0 data is not.

---

## 4. Recommendation

**Decision (owner, 2026-10-24): A+ adopted.** The decisions are recorded in
[data-policy.md](data-policy.md) "Owner decisions", for the Phase 4 spec.

**Adopt A+ (own self-play labels; Lichess CC0 positions only as openings;
Syzygy WDL labels; no Lc0 data).** This is DESIGN.md's current Phase 4
rule ("trained only on Fork self-play data"), refined. It needs no change
on main.

Reasoning:

1. **Category gives no reason to take Lc0 data, and no reason to avoid
   it.** Fork is Category 4 either way. So the decision rests on
   originality, rule risk and lock-in, and all three favour own data.
2. **Originality is Fork's differentiator as an AI engine.** CatGPT shows
   that TCEC already sees AI code combined with Lc0 data. A Category 4
   engine whose nets come only from its own search is a clearer story for
   the questionnaire (Q8 and Q10), for the AI gauntlet, and for any future
   "joint competition".
3. **The time saved is small relative to the project.** B and C save
   roughly 3-5 weeks of machine time on the first net. Phase 4 comes after
   Phases 2-3, and early on search, not the net, will limit Fork's
   strength. Reckless reached about 3240 CCRL with its first own-data
   nets.
4. **The pipeline is needed anyway.** A+ builds one pipeline. C builds
   two, and B builds one that is thrown away.
5. **The choice is asymmetric.** Starting clean and adding Lc0 later is
   always possible (the review gate). Starting with Lc0 and becoming clean
   later means retraining from scratch.
6. **The real bottleneck is hardware, not data.** The missing CUDA GPU and
   the 45 GB free disk affect all strategies. Long-term, A's cost is CPU
   time; rented or donated CPU for datagen is a plain scaling lever that
   keeps provenance clean.

What A+ costs: a slower first net (weeks), a machine busy with datagen for
long stretches (it conflicts with the one-heavy-job rule), and a mature
data set that takes months of CPU on this machine alone.

---

## 5. Open questions

### For the owner (answered 2026-10-24)

1. **Training GPU:** Kaggle first, Colab as backup, rented CUDA last.
   Datagen stays on the local CPU. The RX 580 is not supported
   (section 2.1). **Still open:** free Colab bans chess training, so the
   backup has to be paid Colab or rented CUDA.
2. **Disk:** 45 GB constraint recorded. An external SSD will be added
   before Phase 4, and a compact data format is planned regardless.
3. **Lichess puzzles:** diagnostic report only (data-policy.md).
4. **Review gate:** section 3.4.

### For TCEC's Discord

Also added to competition.md "Open questions to ask in TCEC's Discord".

1. Does an engine get exactly one category, and does the Category 4 (AI)
   trait override the data-origin branch of the flowchart? Would data
   origin matter for a Cat 4 engine now, or if AI engines join the Leagues
   or a joint event later?
2. Is the NNUE Guideline (own search/eval data only) still applied, given
   that it has not been in formal rules since S20 and Cup 7/8? Is it
   applied to Category 4 engines?
3. How are "Hybrid" and "Other" data defined in the categorisation
   flowchart? Specifically: (a) human-game positions (Lichess CC0)
   rescored by the engine itself; (b) Syzygy WDL/DTZ as labels; (c) own
   self-play from human-game openings.
4. If a net chain was bootstrapped on Lc0 data and later trained only on
   its own self-play, is that "own data"?
5. Does "architecture" in the mid-season category rule include a change
   of training-data source?
6. Is the new TCEC GPU Competition the AI gauntlet promised in the
   31 Aug 2026 statement, and will CPU-only Category 4 engines get a path?
7. Are there terms of use for tcec-chess.com data beyond the tcecgames
   CC BY-SA 3.0 note?
