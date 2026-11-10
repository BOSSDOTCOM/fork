# Positional-advantage and defense-start slices: the pilot (declared before any data)

Owner's decision, 2026-11-10 (DESIGN.md decisions log; ideas.md 66): the conversion-and-defense
analysis's fixes 1 and 2 (docs/research/conversion-defense/report.md on research/conversion-defense,
be86410, "Synthesis: ranked weaknesses" items 1 and 2) are one generation run, **a pilot first** (about 16
CPU-h); the full slices only if the pilot's rates and label checks look right; then arms in retrain 8c.

This document was committed **before any start was selected or any pilot game played**. Everything below
it that depends on data is in "Results" and was added afterwards; anything not run is marked UNVERIFIED.
The pilot generates no training snapshot, trains nothing and adopts nothing.

## 1. Sources: Fork's own datagen records only

- **g4**, generation 4's sealed part (data/manifests/g4.json): 686,482 games, 64,000,658 positions
  (29,188,391 unsaved by the split search), labelled by Fork 0.3.0-dev+d0e876b (S512ppr3) at 20,000
  nodes, Syzygy 5-piece table ends, score adjudication 700 cp over 8 plies, decided-opening cut 400 cp,
  openings lichess-2026-09.epd plus 2-4 random plies. The local files (`~/fork-data/gen4/g4-wNN-0000.vf`)
  are checked against the manifest's SHA-256s before use.
- **Pool for the pilot's starts: shards w00-w08** (the training shards). **Gold set: shard w09** (g4's
  validation shard, `g4-w09-val.vf` in the manifest), held out from every pilot start and from any later
  slice, so retrain 8c can score its arms on it.
- Never used: gauntlet games, SPRT games, any other engine's games or evaluations (ideas.md 66's data
  policy as tightened by the owner on 2026-11-10: datagen records only).

## 2. How the stored scores and labels are read

A viriformat game (src/datagen/game_record.hpp) is a 32-byte start board with the stored result (0 Black
won, 1 draw, 2 White won), then one (move, score) record per position played. The **score of record k is
the search score of the position before move k, from White's view** (i16). The tool replays each game
with python-chess, decoding the move codes as game_record.hpp defines them (castling as king to its own
rook's square, en passant type 1, promotions type 3), and reads at each position:

- **score** for the side to move: the stored score if White is to move, its negation otherwise;
- **result** for the side to move: 1, 0.5 or 0;
- skipped as a label: an unsaved record (score 32767, `UnsavedScore`), and any |score| > 20,000 (the
  trainer's `max_eval`, tools/train/src/main.rs `MAX_SCORE`: mate and table scores).

That score is the selection label below ("|label| 80-400" in the owner's decision is this 20,000-node
score). The trainer's target for a kept position is `(1 - w) * sigmoid(score / S) + w * result` with
S = 92 and w = 0.5 (tools/train/kaggle/retrain_g3s3.py `SCALE`, `RESULT_WEIGHT`), and the gate (section 7,
check 5) is measured on that target.

## 3. Selection rules

Both slices (each position as it stands before its recorded move):
1. the score is saved and |score| <= 20,000;
2. the side to move is not in check, and the recorded move is neither a capture (en passant included)
   nor a promotion: the trainer's `filter_check` and `filter_tactical`, so the start's score is a label
   the trainer would read, not a mid-exchange score;
3. **queens on**: each side has at least one queen.

**Positional-advantage slice** (fix 1): additionally
- **equal pieces**: knights, bishops, rooks and queens equal in number for the two sides. This is the
  report's taxonomy class "equal-pieces"; bishop against knight with equal counts is its own class
  (B-vs-N) there and is not included (the owner's words are "equal pieces"; Q-MG B-vs-N positions with a
  side to move at -100 to -300 enter the defense slice);
- **level or one pawn apart**: |white pawns - black pawns| <= 1;
- **80 <= |score| <= 400** (either side ahead), bounds inclusive.

**Defense-start slice** (fix 2): additionally
- **-300 <= score <= -100** for the side to move, bounds inclusive; no material rule beyond queens on.

No phase restriction in either slice (the owner's rules name none; queen endings with equal pieces are
themselves an under-trained class, report.md item 5).

**The draw.** From each g4 game at most one start per slice, drawn uniformly among the game's eligible
positions (Python's `random.Random` seeded by the seed, shard and game). Reason: consecutive positions of
one game are near-duplicates, and a long, slowly drifting game would otherwise contribute dozens of
starts. The defense draw never takes the position the positional draw took. The per-game starts are then
shuffled (seeded), and a position (board, side to move, castling rights) is kept only at its first
appearance across both slices; positions that are in the gold set are dropped from the pool. The pilot
plays the first N starts of each shuffled list.

Seeds: **20261110** for the pool (w00-w08), **20261111** for the gold set (w09): the decision's date, and
the next number so the two draws differ.

## 4. The start-position tool

`tools/datagen/defense_starts.py` (new; tests in `tools/datagen/test_defense_starts.py`, which failed
before the tool existed):
- `select SHARD... --out PREFIX --seed S [--exclude TSV...]`: the rules and draw above; writes each
  slice's drawn starts in draw order as TSV (id `shard:game:ply`, the full FEN with the halfmove clock
  and move number, the g4 score and result from the side to move, phase count, pawn difference, men) and
  a pool summary (eligible positions and games per slice).
- `openings TSV --count N --out FILE`: the first N starts as a fork_datagen openings file.
- `played TSV SHARD...`: matches every pilot game's start board back to its start (an error if a start
  is played twice or a game has no start), with the pilot's first score and result from the start's side
  to move and the game's length.
- `gate TSV PLAYED LABELS`: check 5 below.

The tests cover the bands and their bounds, the White-to-side-to-move conversion of scores and results,
the queens, equal-pieces and pawn rules, the check, capture, promotion and unsaved exclusions, the
castling and promotion move codes, one start per game and slice, no position twice, the seeded draw, the
exclusion list, the TSV and openings round trip, the start matching and the gate's arithmetic. A fault
injected into the sign conversion fails four of them.

## 5. The engine and fork_datagen's settings

**Engine**: phase-4's head, 4eba8f7 (the tuned search of R14, net S512ppr3), built in its own WSL clone
(`~/fork-defense-build`, never ~/fork or the Control Center's clone) as the Control Center's
start_part.sh builds a datagen part: `cmake -P cmake/pgo.cmake` with clang, then fork and fork_datagen
from build/clang-pgo. Checked: `fork version` = Fork 0.3.0-dev+4eba8f7, net s512ppr3; **bench 10,374,064
/ 677c436fa145e07f**, equal to tests/bench-s512ppr3.ref; SHA-256 f90ae34b...c971c (fork), e7b71a7a...e8e8
(fork_datagen). The bench is checked again after the last stage.

Every flag below was checked in src/datagen/datagen_main.cpp's parser and src/datagen/self_play.cpp:

| Flag | Value | Reason |
|---|---|---|
| `--openings` | the slice's openings file (section 4) | the starts |
| `--random-min` / `--random-max` | **0 / 0** | the game starts at the drawn position itself (the defaults, 2-4 random plies, would move it) |
| `--nodes` | **80,000** | the owner's decision (report.md item 1) |
| `--decided-cp` | **31,000** | "no decided-opening cut": the cut fires on a first search beyond decided_cp (mates excepted); 31,000 is `ScoreInfinite` (src/search/score_bounds.hpp), which no search score exceeds, so the cut never fires |
| `--adjudicate-cp` / `--adjudicate-plies` | **1,500 / 16** | the owner's decision (report.md: 1,500 cp over 16 plies); the count is of consecutive recorded positions (`ScoreStreak`) |
| `--tables` | `~/fork-tools/syzygy/3-4-5` | as g4: a game ends at table entry with the exact result |
| `--save-percent` | **100** (default; no split search) | every move is searched at 80,000 nodes: the slice's point is the result of a defended game, and g4's split (half the moves at 4,000 nodes) would weaken the defence it records; every position also gets a label. Cost: higher per position than a split run (section 6) |
| `--check-nodes` | **0** (default: the full 80,000) | in-check positions are not trained on, but their moves decide the game |
| `--hash-mb` | **4** | g4 searched 20,000 nodes with 1 MB (81,920 entries of 12 bytes, src/search/trans_table.hpp); 4 MB keeps that ratio of entries to nodes at 80,000 |
| `--max-plies` | 500 (default) | bullet's game reader stops at 512 records (self_play.hpp) |
| `--threads` | **2** | the measure slot's limit beside data generation (think-tank decision 13) |
| `--seed` | 20261110 | shuffles the openings' order only (no random plies) |
| `--shard-mb` | 1024 (default) | |

Runs: `dp-pos` (positional), `dp-def` (defense), `dp-gold-pos`, `dp-gold-def` (gold starts, played the
same way). Output under `~/fork-data/defense-pilot/`. Each fork_datagen run is timed (bash `time`: wall,
user and system CPU) and run with `nice -n 19`.

## 6. Size (about 16 CPU-h)

**Rate estimate before any data**, from g4's own manifest: 714.4 G nodes in 33,340.8 s on 10 threads is
2.14 M nodes per thread-second on this machine (6 cores, 12 threads, SMT shared). At 80,000 nodes for
every position (no split) that is 37.3 ms a position, **about 10.4 CPU-h per million positions**, so the
report's 4 M-position pilot would cost about 42 CPU-h, and the report's own rate (about 4 CPU-h per
million, scaled from g3j, which ran the split search) is about 2.6 times too low for these settings. The
pilot is therefore sized to the budget, not to 4 M positions:

| Run | Starts provided | Positions target | Estimated CPU-h |
|---|---:|---:|---:|
| dp-gold-pos | 4,000 | 120,000 | 1.2 |
| dp-gold-def | 4,000 | 120,000 | 1.2 |
| dp-pos | 30,000 | 840,000 | 8.7 |
| dp-def | 15,000 | 420,000 | 4.4 |
| gold labels, 1 M nodes | the gold starts played (expected 500-3,000 per slice) | | about 0.5 |
| **Total** | | **1,500,000** | **about 16** |

- Defense gets half of the positional slice's positions, as the report proposes ("about half of 1's
  positions").
- fork_datagen plays game g from opening `perm[g mod N]`: with no random plies, a run that played more
  games than it has starts would repeat games exactly. The starts provided are 1.4-2 times the games
  expected at the shortest declared game length (40 positions, check 2), and `played` fails on any start
  played twice.
- The gold runs take 120,000 positions each, so the gold set is whichever starts get played (a random
  subset of the shuffled list): about 1,000 per slice at 120 positions a game (the report's "about 2,000
  positions" over both slices).
- Order: the gold runs first (a cheap early read of the rates and of the gate), then dp-pos, then dp-def.
  If the measured rate in the gold runs is more than 1.5 times the estimate, the main runs' targets are cut
  in proportion so the pilot stays at about 16 CPU-h (recorded in Results if it happens).

## 7. Pass checks (declared now)

"CPU-h" is fork_datagen's user plus system CPU time (bash `time`), the time it actually ran; with nice 19
beside g4b's 10 threads its wall time is longer. Wall time times threads is reported beside it. Each check
is evaluated per slice (positional, defense) on the main runs, and the gold runs are reported alongside.

1. **Generation rate** (CPU-h per million positions written).
   - (a) *Model check*: within 0.67-1.5 times the estimate of section 6 (10.4). Outside it, the sizing
     model is wrong, and the reason is found before any full run.
   - (b) *Budget*: the full slices the report proposed (30 M positional + 15 M defense) at the measured
     rate, against the owner's approved **about 180 CPU-h** (report.md: 120 + 60): pass if at most 1.5
     times it (270 CPU-h). From the estimate this is expected to **fail as sized** (about 470 CPU-h);
     then the recommendation gives the slice sizes that fit 180 CPU-h and the share of a snapshot they
     make, for the owner to choose.
2. **Game length**: mean positions per written game between 40 and 250, and games discarded as too long
   (500 plies) at most 2% of games played. Reason: below 40 the games are decided almost at once from the
   start (adjudication alone takes 16) and the slice adds little beyond its starts; above 250 the cost per
   start is high and fifty-move shuffling dominates.
3. **Result shares** (from the start's side to move):
   - positional: the side the g4 score favours scores at least 0.55 (wins plus half the draws), and draws
     are at most 80%. Reason: the band says one side is better; if that side does not score clearly above
     half, the 20,000-node labels of this class are noise;
   - defense: the defender scores below 0.5, and **holds (draws or wins) at least 10%** of the games.
     Reason: a slice in which nearly every start is lost adds little beyond the standard data's
     adjudicated losses; the report's S defense windows were held 14.9% of the time.
4. **Game ends**: score adjudication ends at most 50% of the written games (g4: 299,742 of 535,349
   written, 56%, at 700 cp over 8 plies; raising it should move games to their real ends), too-long
   discards as in check 2; the shares of table, rules (checkmate, stalemate, repetition, fifty moves,
   insufficient material), mate-score and adjudication ends are reported.
5. **The offline gate** (report.md item 1, test (a)): the gold set, the gold starts played by
   dp-gold-pos and dp-gold-def, each labelled at **1,000,000 nodes** by the same build (1 thread, Hash 64
   MB, `ucinewgame` before each position, Syzygy 3-4-5, the last reported score; the conversion-and-defense
   labeller's settings). On the starts whose gold label is at least 50 cp from 0 (report.md item 4's floor
   for a signed error), the trainer's target t (section 2) for the **standard data** (g4's 20,000-node
   score and g4's game result at that position) and for the **pilot** (its 80,000-node first score and its
   game result) is measured as `(t - 0.5) * sign(gold)`: larger is less compressed. **Pass, per slice,
   when the paired bootstrap 95% interval (2,000 resamples, seed 20261110) of pilot minus standard lies
   above 0.** Reported beside it: the score part and the result part of the difference separately, and
   the gold label's own `sigmoid(gold / 92) - 0.5` on the same sign scale. A result part below 0 with a
   passing total (the gain only from the deeper score) is flagged.
6. **Integrity** (blocking): `tools/datagen/verify_games.py` with `--table-pieces 5` and `--manifest` on
   every shard (the manifest supplies the 1,500 / 16 adjudication); `played` matches every game to one
   start and none twice; the bench is unchanged after the last stage.

Also reported, not a check: each slice's pool (eligible positions and games in w00-w08), against the
games the full slices would need at the measured game length; the phase and pawn-difference mix of the
starts; the share of written positions the trainer would keep (not in check, quiet, |score| <= 20,000).

**Decision rule.** The recommendation is to generate the full slices if checks 1a, 2, 3, 4, 5 and 6 pass
for that slice. Check 1b decides only their size: at the measured rate, within the budget the owner sets.
A slice that fails 3 or 5 is not recommended, whatever the rate.

## 8. Constants introduced here

| Constant | Value | Reason |
|---|---|---|
| Positional band, defense band, 80,000 nodes, 1,500 cp / 16 plies | | owner's decision, 2026-11-10 (report.md) |
| `--decided-cp` | 31,000 | `ScoreInfinite`: no cut |
| `--hash-mb` | 4 | g4's entries-per-node ratio at 4 times the nodes |
| Pilot targets | 120,000 / 120,000 / 840,000 / 420,000 | about 16 CPU-h at section 6's estimate; defense half of positional |
| Starts provided | 4,000 / 4,000 / 30,000 / 15,000 | at least 1.4 times the games at 40 positions a game |
| Gold floor | 50 cp | report.md item 4's floor for a signed error |
| Seeds | 20261110, 20261111 | the decision's date; the next for the gold draw |
| Check thresholds | section 7 | each with its reason there |

## Results

(Added after the runs.)
