# Training-data audit: the validation/training overlap check (2026-11-11)

The owner's gating of the bug review's work (DESIGN.md §6, 2026-11-11, about 6:40 PM EST) put "the training-data
audit's validation/training overlap check" before the next network decision (retrain 8c). No document defined the
check further, so the definition below was fixed before anything was computed. Run on the local machine, 9:57 to
10:42 PM EST, as the jobctl measure job `overlap-audit2`. Tools only: the engine and bench are unchanged.

## Definition

- **Position:** the position each record's move was played in. Every record counts: saved, unsaved (score 32767)
  and slice records.
- **Overlap of a position (key K1):** the same piece placement, side to move, castling rights and en passant
  square. The en passant square counts only when a capture there is legal; Fork's `Position` normalises this, so
  K1 equals the first four FEN fields. The halfmove and fullmove counters are ignored. **K0** is coarser (placement
  and side to move only). It differed from K1 for at most 2 positions in any set, so the tables give K1.
- **Kept:** the trainer's filter as idea 52's 8b-sites.json records it: saved, not in check, the move played
  neither a capture nor a promotion, and |score| <= 20,000. The validation loss is measured on these positions.
  Reported both ways: query positions found anywhere in training, and found as kept training positions.
- **Game overlap:** the same game. That means the packed start board (including both counters) and the same move
  codes; scores and the result are ignored, so relabelled copies such as bl-, td80- and td90- files would match.
  **Opening overlap:** the game's start position (the book exit) also starts some training game.
- A hash hit is counted only after an exact comparison of the FEN fields or the game bytes.
- **Training files:** retrain 8b's arm c list (its files.json, 129 files), grouped by the snapshot that added
  them:
  - s2: item 7's g3s2;
  - s3: what 8a's g3s3 added;
  - s4: what 8b's g4s1 added.

  Then 8c's sealed new part, g4b: w00-w08, plus g4b-w09-val after its first 60 games, which the snapshot tool's
  hold rule gives to the validation file. Then, provisionally, the data that may join 8c, copied at about 9:10 PM EST:
  - the label-depth arms ld-arms and ld-arms2 (still being written);
  - the first segment of the positional slice (slice-pos-td90).

  g4c had not started. The TD and blend copies hold the same games as the control's files, so the result applies
  to every 8b arm and to r8brft1's fine-tune (arm c's files).
- **Query sets:**
  - the validation files g3s2-val (item 7), g3s3-val (8a) and g4s1-val (8b and the fine-tune);
  - g4b-w09-val's first 60 games (8c's likely addition);
  - the held-out sets: tools/nnue/endgame_heldout.tsv (3,800 positions); the 8-12-piece heldout_deep positions
    (1,500; SHA-256 cfcee27a85822e40...); the 6-7-piece heldout_67.tsv (5,600; f5a12a38d815734a...); idea 51's H
    (5,000 sites; 64862be3...); the teacher's H2 sample (20,000; d2721f1c...); idea 52's i52-held (10,000) and
    i52-controls (2,000).

**Input checks:**
- Every training file and every query .vf file matched its manifest's SHA-256 (data/manifests, with retrain/8b-prep's
  r8b-*.json and g4s1-pre.json).
- The games, records and saved counts of the 138 training files with per-file manifest counts matched exactly.
- The kept rule reproduces idea 52's count for g3j-w00..w04: 62,144,106.
- The provisional files are not in any manifest; they are snapshots of files that were still being written.

## Results

Validation against training (K1; "kept" = the validation file's kept positions):

| Retrain | Validation | Training files | Positions in training | Kept positions in training | Of those, kept in training too | Monitoring prefix (first 20,000 kept) | Identical games | Start position in training |
|---|---|---|---|---|---|---|---|---|
| item 7 | g3s2-val | s2 | 3,158 of 160,213 (1.97%) | 1,681 of 73,517 (2.29%) | 1,416 | 288 (1.44%) | 14 of 1,800 | 42 |
| 8a | g3s3-val | s2+s3 | 3,431 of 171,261 (2.00%) | 1,812 of 77,335 (2.34%) | 1,519 | 330 (1.65%) | 14 of 1,920 | 45 |
| 8b, r8brft1 | g4s1-val | s2+s3+s4 | 3,739 of 193,039 (1.94%) | 1,950 of 84,951 (2.30%) | 1,625 | 344 (1.72%) | 14 of 2,160 | 45 |
| 8c (sealed inputs) | g4s1-val + g4b's 60 | + g4b | 3,906 of 199,502 (1.96%) | 2,021 of 87,285 (2.32%) | 1,676 | 345 (1.73%) | 14 of 2,220 | 45 |
| 8c (with provisional inputs) | the same | + ld arms, positional slice | 3,974 of 199,502 (1.99%) | 2,057 of 87,285 (2.36%) | 1,707 | | 14 of 2,220 | 45 |
| (g4b's 60 alone) | g4b-w09-val's first 60 | s2+s3+s4+g4b | 152 of 6,463 (2.35%) | 63 of 2,334 (2.70%) | 47 | | 0 of 60 | 0 |

**What the overlap is (8b's g4s1-val):**

- **No self-play game of more than one move is repeated.** All 14 identical games have a single move, and they
  are the same 14 under every snapshot (the newer validation files contain g3s2-val's streams):
  - 13 are endgame-slice placements: the slice's 60 held games against other slice files. Random 3- and 5-piece
    placements recur, and 31 of the 60 slice validation positions occur in slice training files.
  - 1 is a self-play game that ended after one move (g3s2-val game 678). The same book exit and the same move also
    appear in g3s1-g3.vf.
- **By ply:**
  - 46 start positions: book exits shared with training games;
  - 55 positions at plies 1-9, 4 at plies 10-19 and none at plies 20-39;
  - 171 positions at plies 40-79;
  - 3,463 positions at ply 80 or later.
- **By piece count:**
  - 3,097 of the 3,739 have 6 or 7 pieces;
  - 535 have 8-12 pieces;
  - 76 have 13 or more.

  Games that reach simple endings converge on the same positions. Fork's Syzygy adjudication ends games at 5
  pieces, so its 6-7-piece positions are the most frequent. This is position recurrence across independent games,
  with each game's own score and result as the label, not leaked games.
- The rates are flat across item 7, 8a, 8b and 8c: about 2% of positions and about 1.5-1.7% of the monitoring
  prefix. **Past validation losses were not materially contaminated.** At most about 2% of their positions were
  also training positions, and validation loss decides nothing (owner, 2026-11-09).

**Held-out sets against everything scanned (the owner's zero-overlap rule):**

| Set | In training | Where |
|---|---|---|
| endgame_heldout.tsv (4- and 5-piece) | **0 of 3,800** | none: the rule holds against every file, not just the slice |
| heldout_67.tsv (6-7 pieces) | **1 of 5,600** | s2 (so in every current net's training): `8/1Q6/8/5p2/8/5pq1/6k1/3K4 b - -` (item 2355) |
| heldout_deep (8-12 pieces) | **7 of 1,500** | s2 for 6 and s4 for 1; all in 8b's files. Items 618, 643, 901, 1054 (s4), 1094, 1210 and 1328. heldout_deep.py's own check found only 1 (item 1054, in g4-w08) because it scanned g4 and the label-depth data, not the whole snapshot. The committed tools/nnue/heldout_deep.tsv (a95e269, 1,499 positions) leaves 1054 out (heldout_deep_excluded.txt). **The other 6 are still in it**: `8/8/p6P/P5p1/6P1/K1k5/2b5/8 w - -`, `8/8/5kp1/2R4p/r7/5KP1/5P2/8 b - -`, `8/8/p7/1p2k2p/1P4pP/P2K2P1/8/8 w - -`, `8/5p2/3Kp1p1/4P2p/5P1P/6k1/8/8 w - -`, `8/8/4p2R/r3k1pP/6P1/5K2/8/8 b - -`, `8/4k3/6p1/3Kp1P1/4P2p/7P/8/8 b - -` |
| idea 51's H | 54 of 5,000 (1.08%) | 41 of them have 6-7 pieces; the games were held out, the positions recur as above |
| the teacher's H2 | 237 of 20,000 (1.19%) | 193 have 6-7 pieces; same cause |
| i52-held, i52-controls | 10,000 of 10,000 and 2,000 of 2,000 | by construction: the sites are positions of g3j-w00..w04, which arm c trained on with their own labels. Only the deep labels were held out. Idea 52 is retired |

## Conclusions

- **8c is not blocked by the validation data.** No validation game is in training except 14 one-move games (13
  slice placements and 1 one-move self-play game). About 2% of validation positions recur in training, the same
  for item 7, 8a, 8b and 8c's sealed inputs. Optional and cheap for 8c: drop the validation positions whose K1
  occurs in training (this tool's `-queries.tsv` lists them). Also optional: leave the slice's held games out of
  the validation file, since slice placements recur.
- **The zero-overlap rule fails for two held-out sets as committed (phase-4 e005049), by 7 positions in all:**
  - 6 of the 1,499 positions in tools/nnue/heldout_deep.tsv (8-12 pieces);
  - 1 of the 5,600 positions in tools/nnue/heldout_67.tsv (6-7 pieces; d33a4db, the same file by SHA-256 as the
    one checked here).

  All 7 are in the training data of the nets now in use (s2). Neither check is a gate (they are reported in every
  network decision), so this does not block 8c. Before those checks are reported for 8c, the 7 positions should
  be removed from the sets, or the checks reported both with and without them. The FENs are above.
- H and H2 overlap at about 1% at the position level. They were held out by game, as declared. A label study that
  needs positions unseen in training should drop those 291 positions.

## How to run it

    bash tools/overlap/build.sh                       # build/overlap/fork_overlap_audit (core + reader only)
    python -I tools/overlap/overlap_audit.py fens SET.tsv|SET.jsonl --out SET.fens
    python -I tools/overlap/overlap_audit.py train-list --files-json FILES.json --manifests DIR \
        --roots DIR... [--extra GROUP=PATH[:SKIP]]... --sha256 --out TRAIN.lst
    build/overlap/fork_overlap_audit QUERIES.lst TRAIN.lst OUT        # one streaming pass, ~50 MB of memory
    python -I tools/overlap/overlap_audit.py summary OUT --pairs PAIRS.json --manifests DIR --json OUT.json

The 2.62 billion training records (53.8 M games, every group above) took 44 minutes on one thread at below-normal priority. Its
memory is the query keys only (about 250,000).

**Not verified:**
- The trainer itself was not run. The kept rule is the documented one and reproduces idea 52's count, but castling
  is treated as non-tactical, as Fork's move flags have it.
- 8c's validation file is assumed to be g4s1-val plus g4b-w09-val's first 60 games (the snapshot tool's hold rule),
  and 8c's training data is assumed to be g4s1 plus g4b and maybe the provisional parts. g4c and later slices were
  not checked.
- The Kaggle copies were not downloaded; the local files match the manifests the datasets were built from.
