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
| Lc0 training data, raw runs (storage.lczero.org, ODbL/DbCL) | labels, positions | **ALLOWED WITH CATEGORY CHANGE** | Lc0 labels; breaks NNUE Guideline rule 3; a non-AI engine would be Cat 3; ODbL notice and share-alike. **Not adopted** (recommendation A+, training-data.md §4) |
| Lc0 Kovax V7 sets (cleanvisits, k2hybrid) | any | **UNVERIFIED** | As raw Lc0, plus UHO openings whose selecting engine is unknown (likely Stockfish) |
| Lichess evaluations DB | any | **OFF-LIMITS** | Stockfish in browsers |
| Lichess puzzles | training | **OFF-LIMITS** | Stockfish NNUE at 40 meganodes; test-suite use is an owner decision |
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
| official-stockfish/books (UHO, 8moves, popularpos) | openings | **OFF-LIMITS** | Stockfish project; UHO selected by an engine-eval window (engine **UNVERIFIED**, likely Stockfish) |
| mitermix/chess-selfplay, Kaggle sets | any | **UNVERIFIED** | Not reviewed, or the producing engine is unknown |
| Opponent games from Fork's own gauntlets (Phase 8) | any | **OFF-LIMITS** | Opponents' moves; stored apart from training data (originality.md §4) |

## Changing a status

Change a status only on new primary-source evidence (cite it in
training-data.md and sources.md) or on an owner decision (record the date
here). A change from or to ALLOWED WITH CATEGORY CHANGE also needs a
questionnaire update and an email to TCEC (the Potential precedent).
