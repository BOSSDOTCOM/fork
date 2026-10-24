# Fork data policy

Created 2026-10-24. Until now the rules were spread across DESIGN.md (Phase 4:
"trained only on Fork self-play data"), [originality.md](originality.md) §3
and [research.md](research.md) §7. This file collects them in one place and
gives every external data source a status. The evidence behind each status
is in [training-data.md](training-data.md).

## Rules

1. **Labels come from Fork.** Every eval, score or search statistic used to
   train a Fork net comes from a Fork binary, with two exceptions: game
   results, and Syzygy tablebase results (exact facts, not engine output).
2. **Stockfish-touched data is OFF-LIMITS.** This covers any source whose
   labels, moves or position selection came from Stockfish (or is likely
   to have), and it holds whatever the license says or TCEC tolerates.
3. **Other engines' data is OFF-LIMITS by default.** Lc0 data is the only
   candidate for an exception, and only by an explicit owner decision
   recorded here (status ALLOWED WITH CATEGORY CHANGE).
4. **Every net chains back to Fork's HCE or a random init** (originality.md
   §4). The training-data log records each source and its status.
5. **UNVERIFIED sources are treated as OFF-LIMITS** until verified.

## Statuses

| Status | Meaning |
|---|---|
| **ALLOWED** | Can be used under the rules above; logging required. |
| **ALLOWED WITH CATEGORY CHANGE** | Legally usable, but it changes Fork's TCEC standing, or would change it under the plain flowchart or a stricter future rule (NNUE Guideline rule 3, "own data"). For Fork as a Category 4 engine, the category itself does not change today (CatGPT precedent). Requires an explicit owner decision; **not adopted**. |
| **OFF-LIMITS** | Never in Fork's training, openings or tuning. |
| **UNVERIFIED** | Provenance or license not confirmed; treated as OFF-LIMITS. |

## Source status (verified 2026-10-24)

| Source | Use | Status | Why |
|---|---|---|---|
| Fork self-play (own search/eval labels) | labels, positions | **ALLOWED** | The NNUE Guideline standard; DESIGN.md Phase 4 |
| Syzygy tablebases (WDL/DTZ) | labels for positions with 7 pieces or fewer, adjudication | **ALLOWED** | Exact retrograde results, no engine search; table-file license **UNVERIFIED** but they are universally distributed |
| Lichess standard game DB, moves and results (CC0) | datagen start positions, opening books | **ALLOWED** | Human moves, CC0; **strip `[%eval]` and drop BOT-account games** |
| Lichess game positions rescored by Fork | positions | **ALLOWED** (grey area) | Labels are Fork's; how TCEC classifies it is **UNVERIFIED** (Discord question) |
| Lichess game results as training labels | labels | **UNVERIFIED** | Human results are not engine data but not own data either; the TCEC view is not stated |
| Lichess `[%eval]` comments | anything | **OFF-LIMITS** | Stockfish via fishnet |
| Lichess Broadcasts (HF, CC-BY-SA 4.0), moves only | start positions | **ALLOWED** | Human games; attribution required; strip `[%eval]` |
| Lc0 training data, raw runs (storage.lczero.org, ODbL/DbCL) | labels, positions | **ALLOWED WITH CATEGORY CHANGE** | Lc0 labels; breaks NNUE Guideline rule 3; a non-AI engine would be Cat 3; ODbL notice and share-alike. **Not adopted** (A+, owner 2026-10-24); revisited only through the review gate below |
| Lc0 Kovax V7 sets (cleanvisits, k2hybrid) | any | **UNVERIFIED** | As raw Lc0, plus UHO openings whose selecting engine is unknown (likely Stockfish) |
| Lichess evaluations DB | any | **OFF-LIMITS** | Stockfish in browsers |
| Lichess puzzles | training, tuning, acceptance gates | **OFF-LIMITS** | Stockfish NNUE at 40 meganodes |
| Lichess puzzles | diagnostic report only | **ALLOWED** (owner, 2026-10-24) | A solve-rate report to look at, never a tuning target, an acceptance or SPRT gate, or a training input |
| CCRL, CEGT game archives | any | **OFF-LIMITS** | Many engines' moves and evals, including Stockfish and derivatives |
| TCEC game archives (tcecgames, CC BY-SA 3.0) | any | **OFF-LIMITS** | Stockfish and Lc0 moves and evals; REFERENCE ONLY for statistics |
| Fishtest games | any | **OFF-LIMITS** | Stockfish vs Stockfish |
| OpenBench instance games | any | **OFF-LIMITS** | Other engines' games |
| FICS games DB | any | **UNVERIFIED** | No terms found; includes computer games |
| Lichess Elite DB (nikonoel) | start positions | **UNVERIFIED** | No license statement; eval stripping not stated |
| Caissabase, KingBase, angeluriot/chess_games, Chess.com PubAPI | start positions | **UNVERIFIED** | No license or terms confirmed; not needed while Lichess CC0 exists |
| ChessBench, laion/strategic_game_chess | any | **OFF-LIMITS** | Stockfish labels or Stockfish self-play |
| nnue-pytorch datasets, HF linrock_relabel_* | any | **OFF-LIMITS** | Stockfish data, and/or Lc0 relabels mixed with Stockfish data |
| chessdb/snapshots (chessdb.cn) | any | **OFF-LIMITS** (UNVERIFIED scorer) | The scoring engine is not stated |
| official-stockfish/books (UHO, 8moves, popularpos) | training, datagen openings, tuning | **OFF-LIMITS** | Stockfish project; UHO selected by an engine-eval window (engine **UNVERIFIED**, likely Stockfish) |
| `UHO_Lichess_4852_v1.epd` (official-stockfish/books) | opening positions for SPRT and other test matches only | **ALLOWED, test openings only** (owner, 2026-10-24; decision 6 below) | Test matches measure Fork against Fork; nothing from them trains or tunes a net. Never training data |
| mitermix/chess-selfplay, Kaggle sets | any | **UNVERIFIED** | Not reviewed, or the producing engine is unknown |
| Opponent games from Fork's own gauntlets (Phase 8) | any | **OFF-LIMITS** | Opponents' moves; stored apart from training data (originality.md §4) |

## Owner decisions (2026-10-24): Phase 4 spec input

The Phase 4 spec in DESIGN.md on main must carry these decisions. main was
not changed here; the Phase 4 spec session copies them over.

1. **Strategy A+.**
   - Labels come from Fork's own self-play only.
   - Datagen openings are Lichess CC0 game positions (with `[%eval]`
     stripped and BOT games dropped).
   - Positions with 7 pieces or fewer are labelled and adjudicated with
     Syzygy WDL.
   - Fork rescores old data with newer Fork nets.
   - No Lc0 data. Details: training-data.md §3.4.
2. **Compute split.**
   - Self-play datagen runs on the owner's CPU (12 threads).
   - Training runs on **Kaggle** (free CUDA) first, and on **rented CUDA**
     only if Kaggle falls short. Colab was the original backup and has
     been dropped (see below).
   - The local Radeon RX 580 is **not supported** for training.
   - Kaggle and Colab limits are in training-data.md §2.1.
   - **Colab dropped** (owner, 2026-10-24). Its FAQ bans "chess training"
     on free runtimes. The order is now Kaggle, then rented CUDA.
3. **Disk.**
   - 45 GB free on C: (2026-10-24). The owner adds an external SSD before
     Phase 4.
   - Phase 4 plans around a **compact data format** (a few bytes per
     position, binpack-like) regardless.
   - **Storage** (owner, later on 2026-10-24):
     - Kaggle Datasets holds the only copy of the training data, with no
       archive copies.
     - Local shards are deleted after the Kaggle hash check passes.
     - Each net and its data manifests go to GitHub Releases.
     - Accepted risk: lost data means regeneration.
     - Details: training-data.md §2.2.
4. **Lichess puzzles** are allowed as a **diagnostic report only**:
   - never a tuning target;
   - never an acceptance or SPRT gate;
   - never a training input.
5. **Review gate for Lc0 data.** Revisit, whichever comes first:
   - two consecutive net generations each gain less than about 10 Elo
     (SPRT-measured against the previous generation), or
   - 4 generations, or 2 billion own positions.

   Revisiting means a new owner decision on measured numbers, not an
   automatic switch.
6. **UHO_Lichess: test openings only** (owner, 2026-10-24, approving the
   Phase 3 spec). `UHO_Lichess_4852_v1.epd` is the opening book for SPRT and
   other test matches. It is **never training data**: not datagen
   openings, not labelled positions, not a tuning set, and positions from
   test-match games are not kept for training either. The book is selected
   by engine evaluations, which rule 2 keeps out of training (the same
   reasoning as ideas.md idea 7 for TCEC books). This narrows the earlier
   OFF-LIMITS row for official-stockfish/books to training, datagen and
   tuning use.

## Changing a status

Change a status only on new primary-source evidence (cite it in
training-data.md and sources.md) or on an owner decision (record the date
here). A change from or to ALLOWED WITH CATEGORY CHANGE also needs a
questionnaire update and an email to TCEC (the Potential precedent).
