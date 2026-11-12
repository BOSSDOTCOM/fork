# Endgame slice v2: 6-7-piece (and selected 8-piece) positions labelled by ChessTB WDL (design only)

Owner's order, 2026-11-09, item 3: random legal 6-7 (and selected 8) piece
positions in the material classes where Fork's error is highest, labelled
by ChessTB WDL, with a disk and download budget, tested as a retrain arm
against the current 2% slice. **Design only**: nothing here was run, no
table was downloaded, no data was generated. It stops for the owner's
review. Every estimate is marked as one; facts about ChessTB are cited
from the KB entry `docs/kb/chesstb.md` (branch kb, verified 2026-11-09),
which also carries the proposed data-policy line this design depends on.

## 0. Preconditions (owner decisions)

1. **The data-policy line** (KB chesstb.md §8): ChessTB WDL labels allowed
   alongside Syzygy as exact retrograde results from a public-domain
   source (CC0 1.0 data), labels only, provenance and hashes recorded.
   Until it is adopted, no ChessTB file is downloaded.
2. **The python-chess fork as a tool dependency**: `chess.chesstb` from
   noobpwnftw/python-chess at commit
   38c108efd992538dc078750cba9fee30b9f030ce (GPL-3.0, pure Python), in a
   separate virtual environment (Fork's tools keep their pinned upstream
   python-chess). It never enters the engine.
3. **A download budget** (section 6).

## 1. What the findings say, and what waits

| Finding | Source | Status | Use here |
|---|---|---|---|
| Conversion failures cluster in rook against minor piece, queen endings with a queen imbalance, piece against pawns, and one-wing pawn structures | conversion-defense analysis (branch research/conversion-defense, docs/research/conversion-defense/report.md; method committed 385cb74, results being computed) | **preliminary** | The four classes below; the one-wing bias |
| S512ppr3's static evaluation is most conservative in queen imbalances and queen endings (about -290 to -356 cp of bias) | same, preliminary | **preliminary** | Class C3's share; C3's materials mix queen-versus-queen and queen-versus-rook-and-minor |
| Seed disagreement is concentrated in endgames: the top-5% disagreement set holds 9.6% of the positions with 2-6 pieces and 9.1% of those with 7-12, against 5.3% at 13-18, 3.5% at 19-24 and 1.2% at 25-32 (about 1.9 and 1.8 times the 5% base rate) | idea 52's 8b selection (branch idea52/8b-sites, docs/research/idea52/8b-sites.json, `top_share_by_pieces`; g3j, 62.1 M kept positions) | final for g3j | Endgames are where the net is least sure; it does not separate 6-7 from 8-12, so it supports the slice as a whole, not a piece-count split |
| The current slice (at most 5 pieces, Syzygy WDL, about 2.1% of g3s2's positions) took the 900-position check from 351 misjudged (S512+PP) to 8 (S512ppr2); a recall figure, since 898 of the 900 are slice positions (bug review T1, 2026-11-11); on the held-out check (tools/nnue/endgame_heldout.py) 945 to 454 | DESIGN.md §5.6 order table; docs/nets.md | final | The template, the record format, and the control arm |
| Keep the 2% slice in every 8b arm | owner, 2026-11-09 (as given in the order) | decided | v2 is added beside v1, not instead of it (section 7) |

**Waits for the final conversion-defense results:**
- the class shares (equal for now, section 3);
- whether one-wing structures are a real cluster (the bias in section 4 is
  provisional);
- which imbalance sub-types lead inside C2 and C3 (for example queen against
  rook and minor versus queen against two rooks).

**Declared re-weighting rule** (to apply once item 5 of the analysis, "data
gaps", is final, before any position is generated): each class's share is
proportional to its gap ratio (its share of the game-deciding positions over
its share of the training sample T), clipped to between half and twice the
equal share, then renormalised; a class with fewer than 15 deciding
positions keeps the equal share. The rule is fixed now so the final numbers
choose the shares, not a later judgement.

## 2. Why 6-7 pieces, and the TCEC caveat

- Self-play adjudicates at table entry (Syzygy 3-4-5 locally), so positions of
  at most 5 pieces come only from v1; positions of 6-7 pieces are in the
  self-play data, but labelled by Fork's own search and the game result,
  which are least reliable exactly in the endings the analysis names.
- **TCEC supplies 7-man Syzygy** (KB competition.md), so at TCEC Fork's
  search probes tables from 7 pieces down and rarely uses its evaluation
  there. The value of v2 at TCEC is indirect: better judgement of the 8-12
  piece positions that lead into these endings (the net generalising
  upwards), and of 8-piece positions with an opposing pawn pair (no table at
  TCEC). Locally the case is direct: SPRTs and screens use only 3-4-5 tables
  and the gauntlet none.
- Consequence: part of any local gain may come from 6-7-piece positions that
  TCEC's tables would cover. The test (section 8) reports that share.

## 3. Material classes and shares

Positions in total: **26,000,000**, the same count as v1's slice (g3s2's
`slice_positions`: 25,999,940 after its 60 held-out games), in 10 files of
2,600,000. Class shares are provisional (equal) until section 1's rule
applies.

| Class | Share (provisional) | 6-piece materials | 7-piece materials (budget R / F) | 8-piece (budget F only) |
|---|---:|---|---|---|
| C1 rook endings | 25% | KRPvKRP, KRPPvKR | KRPPvKRP (R); KRPPPvKR (F) | KRPPP v KRP with one opposing pair (ChessTB `KRPPpKRp`) |
| C2 rook against minor | 25% | KRPvKBP, KRPvKNP, KRvKBPP, KRvKNPP, KRPPvKB, KRPPvKN | KRPPvKNP (R); KRPPvKBP (F) | none |
| C3 queen endings and queen imbalances | 25% | KQPvKQP, KQPPvKQ, KQvKRBP, KQvKRNP, KQPvKRR, KQvKRRP, KQPvKRB, KQPvKRN | KQPPPvKQ (R); KQPPvKRB, KQPPvKRN (F) | none |
| C4 piece against pawns | 25% | KBvKPPP, KNvKPPP, KRvKPPP, KBPvKPP, KNPvKPP, KRPvKPP, KQvKPPP | KBPvKPPP, KRvKPPPP (R); KNPvKPPP, KRPvKPPP, KBvKPPPP, KNvKPPPP, KQvKPPPP (F) | none |

- **Piece-count split inside a class**: half 6-piece, half 7-piece (and, in
  budget F, a tenth of C1 from the 8-piece table). Provisional; the idea 52
  result does not separate the two.
- **Material weights inside a piece count**: in proportion to how often
  Fork's own games enter each material, counted from sealed g3j shards by
  the slice tool's `signatures` command extended to a 7-piece entry point,
  with a floor of 5% per listed material so rare ones still appear. This is
  v1's "own games" half, applied per class.
- **Expected label mix** (anticipation only): ChessTB's published statistics
  (stats.json, all legal positions, both sides to move) give draw shares
  from 4% (KRPPvKN) to 55% (KRvKNPP); the balanced materials (KRPvKRP 45%,
  KRvKBPP 50%, KQPvKQP 39%, KQvKRBP 39%) are where the information is. The
  quiet filter (section 4) changes these shares; the generator reports the
  real ones.
- **No resampling by label.** Balancing wins and draws by rejecting on the
  label would shift each material's base rate and teach the net a wrong
  prior; balance comes from the choice of materials instead.

## 4. Random legal positions (v1's rules as the template)

Template: `tools/datagen/endgame_slice.py` (`place`, `generate`). Changes
are marked.

- **Placement**: kings and pieces on random free squares; pawns on ranks
  2-7; the stronger side's colour White or Black at random; side to move at
  random (half each); no castling rights, no en-passant square, halfmove
  clock 0 (as v1).
- **Kept only if** (v2 is stricter than v1, which required only that the
  recorded move be quiet):
  - the board is legal (`is_valid`) and the side to move is not in check;
  - **the side to move has no capture and no promotion available** (the
    endgame check's quiet rule; "not immediately decided": a hanging piece
    or a promotion on the next move is search's job, through quiescence,
    while the static evaluation is used at quiet positions);
  - a quiet legal move exists that does not end the game (v1's rule; that
    move is the recorded one, chosen at random among them);
  - the position (board and side to move) is new within the slice and not in
    the held-out check set (section 8).
- **One-wing bias** (provisional, waits for the final results): in half of
  the pawnful placements all pawns go on files a-d or all on files e-h
  (one half chosen at random), so one-wing structures are well represented;
  the other half place pawns anywhere.
- **8-piece opposing pair** (budget F): one white and one black pawn on the
  same file, the black one above, placed first; then the other pieces.
  ChessTB's 8-piece tables cover exactly the positions with at least one
  such pair.
- **Rejection cost**: placements of 6-7 men fail the quiet filter often
  (estimate, **UNVERIFIED**: perhaps half or more); generation is cheap next
  to probing, and the rate probe measures both.

## 5. Labels: how the probes run

- **Local tables only**, the `full/` WDL form of each chosen material, one
  material per process. KB chesstb.md §2: a `full/` file decodes on its own
  except for en-passant captures, which the placement never creates; the
  shipping files may have a dropped or relaxed frame that needs every
  capture and promotion child material (for a pawnful 7-piece material,
  other 7-piece files), which is why they are not used. Each file is probed
  alone in an otherwise empty directory, so any hidden dependency raises
  `MissingTableError` and stops the run; nothing is skipped silently.
- **Prober**: `chess.chesstb.open_tablebase(dir).probe_wdl(board)`, which
  returns +2 (win) to -2 (loss) for the side to move (fork documentation,
  docs/chesstb.rst). As in v1, +2 is a win, -2 a loss, and everything else
  a draw (cursed wins and blessed losses are draws in play). `python-lz4`
  installed for speed (the documentation says it is used when present).
- **Where the tables live**: a case-sensitive folder (the ChessTB README
  requires one). Either an NTFS folder on C: switched to case sensitivity
  (needs an Administrator prompt once), with the job run from Windows
  Python, or WSL's ext4. The NTFS folder is preferred: WSL's virtual disk
  grows on C: (DESIGN.md §5.3), and whether it gives the space back after
  a 35 GB file is deleted depends on the WSL settings (**UNVERIFIED** for
  this machine).
- **The online explorer is not a labelling route.** It allows 300 probes a
  minute per IP (verified from its response headers, KB chesstb.md §6.2),
  and each probe ranks every legal move under every metric: 26 M positions
  would take about 60 days at the full limit and would load a free
  community service. It is used only for the spot check in section 5.1.

### 5.1 Verification before the labels are used (all must pass)

1. **Against Syzygy at 3-5 pieces**: ChessTB's shipping WDL up to 5 pieces
   (0.19 GiB, self-sufficient within the set) against Fork's local Syzygy
   3-4-5 through upstream python-chess, on 100,000 random legal positions
   (v1's placement, all 3-5-piece materials in proportion): every class
   equal, cursed and blessed included. A single disagreement stops the work
   and is reported.
2. **Independent spot checks at 6-7 pieces**: 300 positions drawn from the
   finished slice (stratified by class) against the Lichess Syzygy
   tablebase API (an independent generator; one request at a time, a pause
   of a minute after any HTTP 429, KB tools.md §6.9), and the same 300
   against the ChessTB explorer at one request every 2 seconds (a tenth of
   its limit; about 10 minutes). Every WDL class must match (the API's
   cursed and blessed classes mapped to draws as above).
3. **Format checks** as for v1: `tools/datagen/verify_games.py` on every file
   (it needs an option for one-move games of 6-8 pieces whose result comes
   from the slice's own label, since the local 3-4-5 tables cannot confirm
   it; a tooling change, below).

## 6. Disk and download budget

Sizes are the `full/` WDL files from the Hugging Face bucket's file list
(KB chesstb.md §3.2; GiB = 2^30 bytes).

| Budget | What | Files | Download |
|---|---|---:|---:|
| S (6 pieces only) | every 6-piece material of section 3 | 23 | **23.8 GiB** |
| R (recommended) | S + KRPPvKRP 34.48, KRPPvKNP 17.91, KQPPPvKQ 8.67, KBPvKPPP 10.14, KRvKPPPP 1.90 | 28 | **96.9 GiB** |
| F (full list) | R + KRPPPvKR 3.70, KRPPvKBP 23.75, KQPPvKRB 26.37, KQPPvKRN 23.64, KNPvKPPP 8.77, KRPvKPPP 6.88, KBvKPPPP 1.04, KNvKPPPP 0.71, KQvKPPPP 1.77, and the 8-piece KRPPpKRp 44.94 | 38 | **238.5 GiB** |

Plus 0.19 GiB once for the verification set (section 5.1, step 1).

- **One material at a time**: download one file, check it (size and Xet hash
  from the listing; SHA-256 computed and recorded), generate that material's
  positions, write them to per-material intermediate files, delete the table.
  **Peak disk** is then the largest single file plus the output: about
  3.0 GiB for S (KQvKRBP), 34.5 GiB for R (KRPPvKRP), 44.9 GiB for F (KRPPpKRp), plus the 1.04 GB slice.
  The total download is still the budget above.
- **The disk margin (DESIGN.md §5.3, standing since 2026-11-06)** comes first:
  a running data-generation part keeps its room (remaining target at 4.6
  bytes per position, once on WSL's disk and twice on C:, plus 20 GB reserve
  on each). The slice job starts a material only if, after that, C: still
  has the material's file size plus 20 GB free. On 2026-11-09 C: had 190 GB
  free (checked once for this design; WSL's free space not checked).
- **Mirror**: the Hugging Face bucket (`hf buckets cp` with the exact path
  under `full/wdl/`, or HTTPS `.../resolve/full/wdl/<file>`); the FTP mirror as
  a fallback. The Lichess mirror's `full/wdl/` entries were 0-byte
  placeholders on 2026-11-09.
- **Output**: 26,000,000 records of 40 bytes (v1's one-move layout,
  2,600,000 to a file: 104,000,000 bytes, as v1's files in
  data/manifests/g3s2.json) = **1.04 GB**, uploaded as one immutable Kaggle
  dataset per the storage rules.
- Download time depends on the owner's connection (**UNVERIFIED**); at an
  assumed 50 MB/s, R takes about 35 minutes, F about 1.4 hours.

## 7. The record format and the score field

Unchanged from v1, so the two slices differ only in content:
- one-move viriformat games: the 32-byte board, one quiet legal move with its
  score, the terminator (40 bytes);
- the result from White's view, from the WDL;
- the score `SLICE_SCORE` (2000 cp) for a White win, -2000 for a Black win,
  0 for a draw, from White's view, so that the trainer's target (a blend of
  sigmoid(score / S) and the result) equals the WDL (v1's docstring:
  sigmoid(2000 / 92) is within 4e-10 of 1);
- files `slice2-00.vf` to `slice2-09.vf`, 60 games of `slice2-00.vf` held out
  for validation as v1 did; listed in the snapshot manifest and read
  interleaved with the self-play files.

A smaller saturating score for 6-7-piece wins (the network then learning
"winning" rather than "won") is a possible later variant, not part of this
test.

## 8. The retrain arm test

**Arms** (same snapshot, recipe, warm start, schedule and seed; equal total
positions):

| Arm | Data |
|---|---|
| A, control | the retrain's standard data with v1's slice (the owner's 2026-11-09 decision keeps it in every 8b arm) |
| V, v2 | the same, with v2's 26 M positions added and the same number of self-play positions removed (whole games, taken evenly from every self-play file) |

So both arms keep v1, and V tests v2 against an equal amount of self-play
data. (An alternative, v2 replacing half of v1, is an owner question.)

**Which retrain**: 8b if the owner adds the arm before 8b launches;
otherwise the next one (8c). One seed per arm at first (about 5 GPU-hours
each, DESIGN.md §5.6 order, row 13); a second seed only if the screens are
close.

**Diagnostics** (reported, never a gate, per the testing rule of
2026-11-09):
- validation loss on the shared validation set;
- the standing 900-position check (`tools/nnue/endgame_check.py`); a large
  regression against the default is flagged to the owner;
- **the extended check, 6-7 pieces**: 1,200 held-out positions, 300 per class,
  materials in the slice's proportions, generated by section 4's rules with
  their own seed and removed from the slice, labelled by ChessTB WDL, with
  the thresholds declared now and equal to the existing check's (a won
  position misjudged below +100 cp, a lost one above -100, a drawn one
  beyond +-200); reported per class and per piece count, for the default,
  A and V. Report-only, like X19.

**Decision path** (DESIGN.md "Which test a candidate gets", 2026-11-09):
1. integrity checks block (parity, quantization limits, bench, tests);
2. competing candidates are all screened first: A and V each play the
   fixed-node screen against the default (same architecture, so the speed
   ratio r is close to 1; FN_adj = FN + 118 log2(r) is computed anyway), and
   V plays A head-to-head at fixed nodes (1,600 games, about +-10 Elo);
3. the better FN_adj goes to its STC SPRT [0, 5] against the default.

**Keep-or-drop rule for v2** (proposed; to be declared by the owner before
any result): v2 joins later retrains if V beats A head-to-head by +5 Elo or
more at fixed nodes (idea 52's bar), or if V wins step 2 and passes its STC
SPRT. Otherwise v2 is retired and the result recorded.

**Transfer report**: every screen reports the share of its games that reached
a 6- or 7-piece position, and the score of V against A on games that did and
did not. A gain found only in games reaching 6-7 pieces is flagged: TCEC's
7-man tables would cover part of it (section 2).

## 9. Costs (estimates unless stated)

| Item | Cost |
|---|---|
| Verification set download | 0.19 GiB |
| Table downloads | 23.8 / 96.9 / 238.5 GiB (budget S / R / F; measured sizes) |
| Peak disk | 3.0 / 34.5 / 44.9 GiB plus 1.04 GB output, within the disk margin |
| Rate probe | 30 minutes, one measure job, at most 2 workers beside data generation (think-tank decision 13) |
| Generation | 26 M positions / (probe rate x workers); the pure-Python prober's rate is **UNVERIFIED**. At an assumed 500 positions a second per worker and 2 workers, about 7 hours; the rate probe replaces this before the run is sized. If the rate is too low, the slice shrinks (for example 13 M) before the arm runs, and both arms keep equal totals |
| Verification | CPU minutes for 100,000 3-5-piece positions; about 10 minutes each for the two 300-position spot checks |
| Training | one extra retrain (about 5 GPU-hours), a second if needed |
| Runner time | three fixed-node screens of 1,600 games and one STC SPRT |
| Kaggle | one new dataset of about 1.04 GB |

## 10. Tooling changes (for the implementing session)

- `endgame_slice.py`: a ChessTB prober option alongside Syzygy, a
  maximum-piece setting for `signatures` (7 instead of the fixed 5), the
  class and material list as an input file, the quiet filter (no capture or
  promotion available), the one-wing option, the opposing-pair placement,
  per-material runs with a merge step that shuffles and splits into 10
  files.
- `verify_games.py`: accept one-move slice games of 6-8 pieces with the label
  as recorded (the local tables cannot confirm it); the ChessTB result check
  is section 5.1 instead.
- `endgame_check.py`: an extended-check mode reading a committed set of
  held-out FENs with their ChessTB labels (the set's FENs and labels are
  tablebase facts and can be committed with their provenance).
- A download helper that fetches one file by exact path, checks the size and
  Xet hash, records the SHA-256, and deletes the file after its material is
  done.
- ORIGINALITY.md: the ChessTB rows (tables: CC0 1.0, mirror, per-file
  hashes; prober: the python-chess fork at its SHA, GPL-3.0).

## 11. Names and constants to screen later

None is introduced yet; the implementing session sends each to the name and
constant screens (match / no match, DESIGN.md §8) before use.
- **Names**: the file prefix `slice2`; any new command-line options (for
  example a prober switch, a maximum-piece setting, a one-wing switch, a
  materials file); new functions or modules (for example a one-wing
  placement or a ChessTB probe wrapper); the extended-check mode's name.
- **Constants** (data-design values, each with its reason here): 26,000,000
  positions (v1's count); class shares 0.25 each (provisional, section 1's
  rule); 6/7-piece split 0.5 (no evidence either way); per-material floor
  0.05; one-wing share 0.5 (provisional); 300 positions per class in the
  extended check (the existing check's 300 per kind); reused unchanged:
  `SLICE_SCORE` 2000 and the check thresholds +100 / -100 / +-200; spot-check
  pacing one request every 2 seconds (a tenth of the explorer's limit).

## 12. Questions for the owner

1. Adopt the data-policy line (KB chesstb.md §8)?
2. Which budget: S (23.8 GiB, 6 pieces only), R (96.9 GiB, recommended) or F
   (238.5 GiB, with the 8-piece table)? What is the connection's real
   download speed?
3. Arm V adds v2 beside v1 and removes self-play positions (this design), or
   replaces half of v1?
4. Which retrain carries the arm: 8b (if not yet launched) or 8c?
5. The python-chess fork (pure Python, GPL-3.0, pinned) as the prober, or
   ask for ChessTB's own C++ probe library to be evaluated (Unlicense; its
   API and batch use are UNVERIFIED) if the Python rate is too low?
6. Tables in a case-sensitive NTFS folder (one Administrator command) or in
   WSL (its virtual disk grows on C:)?
7. The keep-or-drop rule in section 8, declared before any result?
8. Confirm that the class shares, the one-wing bias and the C2/C3 sub-types
   wait for the final conversion-defense numbers under section 1's rule.

## Owner's decisions (2026-11-09)

The questions above are answered (DESIGN.md decisions log, 2026-11-09; ideas.md 68):

- (a) The data-policy line is **adopted** (DESIGN.md training-data decision 1; KB data-policy.md).
- (b) **Budget R** (about 97 GiB downloaded, 34.5 GiB peak disk, one table file at a time).
- (c) **v2 replaces half of v1**: the slice stays 2% of a retrain's positions, half the 3-5-piece Syzygy slice and half
  v2. Arm V is therefore the standard data with that mixed slice, against arm A with the current slice; the extra
  self-play removal of the original arm V design no longer applies.
- (d) The arm runs in **retrain 8c**.
- (e) The **pure-Python prober first**, its rate measured on a 30-minute probe; ChessTB's C++ library is evaluated
  only if labelling would exceed about one day.
- (f) Tables are stored **in WSL** (case-sensitive file system).
- (g) **Keep rule, declared before any data:** v2 is kept if its arm's fixed-node screen interval is not entirely
  below 0 **and** the held-out 6-7-piece misjudgment falls by at least 25% against the control arm. This replaces the
  keep rule proposed above.
- (h) The class shares, the one-wing bias and the C2/C3 sub-types **wait for the final conversion-and-defense
  numbers**.
