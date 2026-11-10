# Conversion and defense: where Fork's games are decided (analysis only)

Owner's request, 2026-11-09: an analysis of conversion and defense from the
recent gauntlet games (Stockfish 19, Clover, Altair, Marvin), recent SPRT
games and held-out deep-labelled positions; six questions, then a ranked
list of weaknesses with a proposed data-generation fix, its cost and a test
design. **Analysis only**: no engine change, no data generation, no
training; it stops for the owner's review. Game files are analysed and never
used as training data (DESIGN.md §5.3, training-data decisions 1 and 6);
nothing derived from another engine's games becomes training data, and no
other engine labels or analyses anything here. The opponents' own in-game
evaluation comments are read only as an aggregate cross-check, never stored
per position and never committed.

## Method (declared 2026-11-09 before any deep label was searched)

This section was committed before the labelling job started. Results that
depend on deep labels follow it; anything not run is marked UNVERIFIED.

### Sources

- **G, the gauntlet** run 42538371594 (phase-4 32c5517: S512ppr3 and time
  management (b); 10+0.1, 1 thread, Fork's Hash 16 MB, no Syzygy tables for
  either side; fastchess, no adjudication: every game played out). 200
  random 8-ply openings (tools/make_openings.py, seed 20261025), each played
  with both colours. **Core set**: Stockfish 19 (400 games, all 200
  openings), Clover 6.1, Altair 7.0.0 and Marvin 6.3.0 (200 games each,
  openings 1-100). **Context**: Laser 1.7, Winter 0.9, Monolith 2.01, Weiss
  1.0 (200 each). Every move carries the mover's `{eval/depth time}`.
  Book exit = the PGN's `[FEN]` (the position after the 8 random plies).
- **S, SPRT games, Fork against Fork**: idea60-stc and idea61-stc (3,200
  games each, 6,400 in all; both engines S512ppr3 with a search variant,
  both tests rejected, so the sides are near equal), 8+0.08, Hash 16, the
  UHO_Lichess_4852_v1 openings (unbalanced by design), Syzygy 3-4-5 in both
  engines, fastchess adjudication: resign when both report at least 1000 cp
  for 5 moves, draw after move 40 when both report at most 10 cp for 10
  moves. Both sides report evaluations, so every ply has a Fork eval. Left
  out: s512ppr3-stc (one side S512ppr2), the i59 fixed-node runs (oracle
  blends, one run failed), older nets.
- **H, held-out deep labels** (generation-3 part g3j, labelled by S512ppr3
  itself and not in S512ppr3's training data g3s3): idea 51's 3,131 kept
  positions of g3j-w05-val with 1,000,000-node S512ppr3 labels; idea 52's
  2,000 uniform controls of g3j w00-w04 with 200,000-node labels and their
  game results. Idea 52's 200,000 top-disagreement sites are a biased
  sample and are used, if at all, only as a separate stratum.
- **T, training shares**: every 500th kept training position (offset 137)
  of g3j w00-w04 (124,288 of 62.1 M, with stored score and S512ppr3's static
  evaluation). g3j is one part of the current mix (g3s3 = g3s2 + g3f + g3g
  trained S512ppr3; 8b adds later parts); it lacks the Syzygy endgame slice
  that g3s2 carries (about 2.1% of g3s2's positions) and was generated with
  the 2026-09 opening book, so it represents the mix only partly.
- **Deep labeller**: the pinned release build fork-release-2ebacd8
  (S512ppr3, bench 14,149,617 / 1cb0717f040c294d, checked before and after
  every job), 1 thread, Hash 64 MB, `ucinewgame` before each position,
  Syzygy 3-4-5, at a fixed node count; the last reported score is the label
  (side to move's view). At most 2 workers, `nice -n 19`, started through
  jobctl.py's measure slot.

### Score conventions

Scores are centipawns from the side to move's view (in-game comments: the
mover's view). Mates are written as +-10,000 in game evaluations and
+-20,000 in labels, table wins as Fork reports them (about +-29,250); every
analysis clamps scores to +-2,000 cp. "Win probability" is sigmoid(cp / 89)
(S512ppr3's scale).

### Item 1: opening pairs

- A **pair** is the two games against one opponent from one book-exit FEN
  with colours reversed. Outcome classes from Fork's view: won both (2),
  won one and drew one (1.5), drew both or won one and lost one (1: split
  as WL and DD), drew one and lost one (0.5), lost both (0).
- **Bias at book exit**: an 8,000,000-node search of each of the 200
  book-exit FENs, converted to White's view. Classes by |bias|: balanced
  below 50 cp, slight 50-99, clear 100-199, large 200 or more. The
  **favourable side** is the colour the bias favours (balanced pairs have
  none). Fork's score from the favourable and from the unfavourable side,
  per opponent, with Wilson 95% intervals.

### Item 2: turning points

- **Decisive**: 1-0 or 0-1. The loser is the side that lost.
- **TP_g, the in-game turning point** (all G decisive games): the first
  Fork move from which Fork's own reported eval stays at or below -150
  (Fork lost) or at or above +150 (Fork won) at every later Fork move.
- **TP, the deep turning point** (G core decisive games): 2,000,000-node
  labels at every position of a window, the positions before plies
  TP_g - 12 to TP_g + 1 for Fork's losses and TP_g - 5 to TP_g + 1 for its
  wins. TP is the first window position from which the label, from the
  loser's view, stays at or below -200 to the window's end (the TP_g rule
  then holds for the rest of the game, which anchors it to the result).
  If the window's first position already qualifies, the TP is
  **censored** (earlier than the window); if none qualifies, the deep
  search disagrees with the in-game collapse ("no deep TP"). Both are
  counted, not dropped. The **turning move** is the move played into the
  TP position: by the loser (the loser's error) or by the winner (a
  resource the loser's earlier search did not foresee).
- **TP for S games** (no deep labels; both sides are Fork): the first ply
  from which every reported eval, converted to the eventual loser's view,
  is at or below -200 to the end.
- **Misjudgment or horizon** (Fork's G core losses with a deep TP): F is
  Fork's last move at or before the TP (position p_F, Fork to move, move
  m_F, Fork's in-game eval G). An 8,000,000-node search of p_F gives s8
  and its best move b8.
  - **seen**: G <= -100. Fork's eval at that move already showed the
    trouble; the error lies earlier.
  - **horizon**: G > -100, s8 > -100 and b8 differs from m_F. A deeper
    search with the same network finds a holding move: the evaluation was
    adequate and the game-time search missed the reply.
  - **misjudgment**: G > -100 and either s8 <= -100 (even before Fork's
    move the deep search finds no hold, so the losing process started
    earlier while Fork's labels said otherwise) or b8 = m_F (the deep search
    plays the losing move and still believes it holds; the result says it
    does not). The two sub-cases are reported apart; the second is
    "misjudgment or deeper horizon", undetermined.
  - Same-network caveat: every label is Fork's own net; a systematic
    misjudgment can hide at every depth, so "horizon" is an upper bound for
    search-only failures and "misjudgment" a lower bound for evaluation
    failures. The result (and Syzygy where it applies) is the anchor.
  - Supporting measures: the static evaluation (`fork evalfens`) at the TP
    position against its 2M label; and, aggregate only, the share of TPs at
    which the opponent's own last reported eval already gave it +100 or
    more.
- Phase of a TP: the TP position's move number (gauntlet: book exit is
  move 5), material count and taxonomy class (below), from the loser's
  view.

### Item 3: conversion and defense

- **Conversion window**: 10 or more consecutive moves of one Fork side
  with its own eval at or above +150. **Conversion failure**: such a game
  drawn or lost; successes are won. Characterised at the window's first
  position and, for failures, at the **drop point**: the first later move
  of that side with its eval below +50 (none: the eval stayed above +50 and
  the game was drawn by rule; the termination is recorded). Deep labels
  (2M) at both points for G games tell a real advantage from an inflated
  one.
- **Defense window**: 5 or more consecutive moves of one Fork side with
  its eval in [-300, -100]. Lost against held (drawn or won), characterised
  at the window's first position.
- G: Fork's side only. S: each side of each game is a Fork perspective.

### Taxonomy (one for items 2-5)

Computed from a FEN and a point of view (the loser, the converting or
defending side, or the side to move for training positions):

- **Phase count** P = knights and bishops 1, rooks 2, queens 4, both sides
  (0-24); buckets P19-24, P13-18, P7-12, P1-6, P0. Move number buckets
  1-20, 21-40, 41-60, 61+.
- **Material signature**: Q-MG (a queen on, P >= 13), Q-EG (a queen on,
  P <= 12), noQ-MG (no queens, rooks and minors, P >= 10), R+minor-EG (no
  queens, rooks and minors, P <= 9), R-EG (rooks only), minor-EG (minors
  only; one each: B-B opposite colours, B-B same, N-N, B-N; else
  multi/uneven), pawn-EG (kings and pawns). Syzygy range (5 men or fewer)
  flagged.
- **Imbalance**: Q-imbalance (queen counts differ), R-vs-minors (rook and
  minor counts differ in opposite directions), minor-up (only the minor
  count differs), other-imbalance, B-vs-N (equal counts, bishops and
  knights differ), equal-pieces; for equal pieces the pawn balance: level,
  pawn+ or pawn-. The **material class** joins the signature and either
  the imbalance or, for equal pieces, the pawn balance.
- **Pawn structure**: passed pawns (own, opponent's, both, none; most
  advanced passer's rank), pawns on both wings (files a-c and f-h) or
  one, total pawns (0-4, 5-8, 9-12, 13-16), isolated and doubled counts,
  pawn islands, kings on opposite wings, the bishop pair. The structure
  label for tables joins the passer class and the wing class.
- **|eval| band** (item 4): 0-49, 50-149, 150-299, 300-599, 600+ cp.

### Item 4: network error

On H: S512ppr3's static evaluation (`fork evalfens` of the pinned build,
side to move) against the deep label: absolute error in cp (decided labels,
mates and table scores, left out) and in win probability (all), by phase,
|label| band, material class and imbalance, with bootstrap 95% intervals.
On idea 52's controls also against the game result (Brier score of
sigmoid(eval / 89) against 0 / 0.5 / 1), for the static evaluation and the
label itself (the same-network check).

### Item 5: data gaps

Each category's share of T against its share of the **game-deciding
positions**: G TP positions (Fork's losses and wins), S TP positions,
conversion-failure drop points and defense-loss window starts. The ratio
(deciding share over training share) ranks the gaps; categories with fewer
than 15 deciding positions are flagged as small. T holds only quiet,
not-in-check positions (the trainer's filter), the deciding positions any
position: the material taxonomy is little affected, which is why the
comparison uses it.

### Item 6: time use

At each G TP with Fork the loser (and separately the winner), Fork's time
for its move F, and for its last 3 moves up to F, divided by Fork's mean
move time in that game; the baseline is the same ratio at every Fork move
in the same move-number bucket over all G games. Medians with bootstrap
intervals, and the share of TP moves above the game's mean.

### Budget

Stage 1 (book exits at 8M, the windows at 2M, conversion-failure points at
2M): 7,851 positions, 16.9 G nodes, about 2 hours at 2 workers. Stage 2
(8M at each p_F, about 540, plus one extension of censored windows if
there are few): about 0.6 hours. Total about 2.6 hours of measure-job
time, within the 4-hour budget.

## Notes on running the Method (2026-11-09, 8:53 PM to 11:56 PM EST)

- **Labeller**: the pinned fork-release-2ebacd8 (S512ppr3, bench 14,149,617 / 1cb0717f040c294d, SHA-256
  fa8be62a...9132aa), checked before and after each of the three jobs (identical each time). Phase-4 adopted R14's tuned
  search margins tonight (85253a2, bench 10,374,064 / 677c436fa145e07f); the pinned build is the gauntlet
  engine's family (32c5517, the same net and the search before R14), which is the right one for analysing those games.
- **Jobs** (jobctl measure slot, 2 workers, nice 19, Syzygy 3-4-5, Hash 64): cd-stage1 (8:53 PM, exit 127 at once:
  started from Git Bash, whose path conversion broke the /mnt/c argument; nothing searched), cd-stage1b (8:53 PM to
  11:48 PM: 7,851 positions, 10,457 s), cd-stage2 (11:48 to 11:55 PM: 843 positions), cd-stage3 (11:55 to 11:56 PM:
  15 positions). **Measure-job time: about 3 h 2 min**, within the 4-hour budget. Stage 1 ran at about 0.7-1.8 s per
  2M-node position (the machine was shared with g4, the 8b slice and its upload), so it took 2 h 55 min, not the
  planned 2 h.
- Choices taken inside the plan (recorded): stage 2 searched p_F at 8M only where the class needs it (Fork's in-game
  eval above -100 at F: 51 positions, plus 15 in stage 3); the censored windows were extended once by 12 plies (66
  losses: 15 then found a TP, 51 stayed censored). **Added after the declaration** (not part of the declared tests,
  marked where used): item 5's comparison against the training positions with |stored score| 100-600 ("matched"),
  and two in-game cross-checks: the swing at the TP and the realization lag (below).

## 1. Opening pairs

**The openings are strongly unbalanced.** The 200 random 8-ply book exits, by Fork's own 8M-node search (White's view):
88 balanced (|bias| < 50 cp), 43 slight (50-99), 33 clear (100-199), 36 large (200+); median |bias| 59.5 cp, mean +99
cp for White. Every opening is played with both colours, so each non-balanced pair gives Fork one favourable and one
unfavourable game.

**"Fork never wins both games of a pair against Stockfish": confirmed, and stronger.** Over 200 pairs: lost both 75,
drew one and lost one 76, won one and lost one 49; won both 0, won one and drew one 0, drew both 0 (pentanomial [75, 76,
49, 0, 0], as in summary.md; all 900 pairs verified as the same FEN with colours reversed). Fork never scored more than 1
point in a pair, and every one of its 49 wins was paired with a loss. In 48 of the 49 wins Fork had the side its own
book-exit search favours by 50 cp or more (median bias from Fork's side +265 cp); the other came from a balanced opening.

Fork's score per game by side (95% bootstrap intervals; games from balanced openings under "balanced"):

| Opponent | Pairs | Favourable side | Unfavourable side | Balanced openings |
|---|---|---|---|---|
| Stockfish 19 | 200 | 0.638 [0.571, 0.701] (W48 D47 L17, n 112) | **0.000** (L112) | 0.088 [0.060, 0.119] (W1 D29 L146) |
| Clover 6.1 | 100 | 0.721 [0.635, 0.798] (W26 D23 L3) | **0.000** (L52) | 0.162 [0.115, 0.214] |
| Altair 7.0.0 | 100 | 0.808 [0.731, 0.875] | 0.048 [0.010, 0.106] (W1 D3 L48) | 0.354 [0.292, 0.422] |
| Marvin 6.3.0 | 100 | 0.962 [0.923, 0.990] | 0.173 [0.106, 0.250] (W2 D14 L36) | 0.573 [0.500, 0.646] |
| Laser 1.7 | 100 | 1.000 | 0.317 [0.202, 0.442] | 0.859 |
| Winter 0.9 | 100 | 0.990 | 0.606 [0.490, 0.731] | 0.906 |
| Monolith 2.01 | 100 | 1.000 | 0.654 [0.529, 0.779] | 0.990 |
| Weiss 1.0 | 100 | 1.000 | 0.702 [0.577, 0.817] | 0.995 |

Pair classes (Fork's view):

| Opponent | Won both | Won one, drew one | Won one, lost one | Drew both | Drew one, lost one | Lost both |
|---|---|---|---|---|---|---|
| Stockfish 19 | 0 | 0 | 49 | 0 | 76 | 75 |
| Clover 6.1 | 0 | 0 | 27 | 2 | 48 | 23 |
| Altair 7.0.0 | 1 | 4 | 40 | 12 | 37 | 6 |
| Marvin 6.3.0 | 7 | 27 | 43 | 12 | 9 | 2 |

Against Stockfish by bias class: large (36 pairs) won one and lost one 34, drew one and lost one 2 (Fork's
favourable-side score 0.97); clear (33) WL 13, DL 15, LL 5 (0.62); slight (43) WL 1, DL 30, LL 12 (0.37); balanced (88)
WL 1, DL 29, LL 58.

Reading: against the two strongest opponents **Fork scores nothing from an unfavourable book exit** (0 of 164 games, not
one draw) and loses 69-83% of balanced-opening games; its wins come almost only from openings already 100-200+ cp in its
favour (from Stockfish's large-bias openings it wins 34 of its 36 favourable games and draws 2). The gap is in holding
level or worse positions, not in converting good ones.

## 2. Where games are decided

### Gauntlet core, deep turning points (2M-node windows)

All 541 core losses accounted for:

| Opponent | Losses | TP in window | TP after the extension | Censored (earlier than 24 plies back) | From book exit | No deep TP |
|---|---|---|---|---|---|---|
| Stockfish 19 | 275 | 130 | 11 | 44 | 20 | 70 |
| Clover 6.1 | 121 | 54 | 3 | 7 | 14 | 43 |
| Altair 7.0.0 | 89 | 40 | 0 | 0 | 13 | 36 |
| Marvin 6.3.0 | 56 | 27 | 1 | 0 | 14 | 14 |
| All | 541 | 251 | 15 | 51 | 61 | 163 |

"No deep TP" (163, 30%): Fork's 2M search never stays at -200 or below inside the 14-ply window around the in-game
collapse, although the game was lost. "From book exit" (61, 11%): the loss was already at -200 by Fork's own search when
the game started.

Phase of the 378 loss TPs (with a TP position; loser's view = Fork's): median move 31 [29, 33] (quartiles 20, 31, 43);
moves 1-20 26.5%, 21-40 45.2%, 41-60 19.0%, 61+ 9.3%. Phase count median 18; P19-24 49.5%, P13-18 20.4%, P7-12 16.9%,
P1-6 12.4%, P0 0.8%. Signature: **Q-MG 69.3%**, R+minor-EG 9.5%, Q-EG 7.9%, noQ-MG 5.0%, R-EG 3.4%, minor and pawn
endings 4.8%. Material class: Q-MG level material 15.9%, Q-MG a minor up or down 13.8%, Q-MG B-vs-N 12.7%, Q-MG rook
against minors 9.3%, Q-MG a pawn down 8.5%, a pawn up 4.2%. Imbalance: equal pieces 39.7%, B-vs-N 18.3%, minor-up 16.9%,
R-vs-minors 15.6%, Q-imbalance 6.1%. Structure: no passer, two wings 42.9%; both sides with passers 20.5%; the opponent
only 19.8%; Fork only 15.6%; one-wing structures 4.8%. Per opponent the median TP move is 31 (Stockfish), 30.5 (Clover),
31 (Altair) and 25 (Marvin). Turning move: Fork's own 59.0%, the opponent's 24.9%, book exit 16.1%.

**The turn is gradual, not a blunder**: the deep label's swing over the turning move has median 82 cp [69, 93]; only
41.4% [35.6, 47.4] of turns are 100 cp or more (266 TPs with a previous label).

**Misjudgment or horizon** (266 losses with a TP inside a window; Wilson 95%):

| Class | All | Stockfish | Clover | Altair | Marvin |
|---|---|---|---|---|---|
| seen (Fork's in-game eval already <= -100 at F) | 212 (79.7% [74.5, 84.1]) | 108 | 48 | 35 | 21 |
| misjudgment: the 8M search at p_F finds no hold either | 41 (15.4% [11.6, 20.2]) | 29 | 4 | 2 | 6 |
| misjudgment or deeper horizon: the 8M search plays m_F and believes it holds | 0 | 0 | 0 | 0 | 0 |
| horizon: the 8M search at p_F finds a holding move | 13 (4.9% [2.9, 8.2]) | 4 | 5 | 3 | 1 |

"Seen" is the declared class for "the error lies earlier": Fork's own eval had been sliding for moves before the label
crossed -200. Together with the 163 no-deep-TP, 51 censored and 61 book-exit losses, **at most 13 of the 541 core losses
(2.4%) are a search horizon in the declared sense**; the rest are slow slides that Fork's evaluation registers late, at
the game's depth, at 2M and (for the 41) at 8M nodes. Same-network caveat: every label is S512ppr3's, so the misjudgment
counts are lower bounds; the result is the anchor.

Supporting measures:
- **Static evaluation at the TP**: S512ppr3's static eval minus the 2M label (Fork's view) has median +170 cp [154, 186];
  at 52.9% of loss TPs the static eval is above -100 while the 2M label is at -200 or below.
- **Realization lag, aggregate cross-check from the opponents' own comments** (never stored per game): the opponent's
  sustained +150 came a median 11.5 moves [9.5, 13.5] before Fork's sustained -150 against Stockfish (78.5% of losses at
  least 5 moves earlier), 10.5 [7.5, 13.5] against Clover, 4.5 [2.5, 6.5] against Altair and 9.5 [5.5, 16.5] against
  Marvin. At Fork's in-game turning point the opponent's own median report was +5.99 (Stockfish), +4.99 (Clover), +3.06
  (Altair) and +7.23 (Marvin), against Fork's -1.90, -1.81, -1.78 and -1.91. (Engines' scales differ; this is a timing
  check, not a calibration.) In 367 of the 368 loss TPs with an opponent eval, the opponent already reported +100 or more.
- **The control**: between two Forks (S) the winner's sustained +150 and the loser's sustained -150 come a median 0.5
  moves apart (quartiles -0.5, 0.5; 3,287 games): no lag when both sides share the evaluation.

**Fork's wins** (206 core wins): 100 have a TP position; 78 of those are at the book exit (Fork's own search already +200
there, median opening bias +310 cp from Fork's side), so the opponent was lost from the start; median TP move 5. Fork's
in-game eval at its first move at or after the TP was +100 or more in 98 of 100. 106 wins have no deep TP: Fork's 2M
labels for its own winning side stayed below +200 inside the window (the same compression as in item 4).

### S games (Fork against Fork, in-game evals, threshold -200)

All 3,287 decisive games have a TP. Median move 46 (quartiles 36, 58); moves 1-20 1.3%, 21-40 35.1%, 41-60 41.9%, 61+
21.7%. Phase count median 9: P1-6 36.8%, P7-12 28.0%, P13-18 22.5%, P19-24 12.2%, P0 0.5%. Signature: Q-MG 34.1%,
R+minor-EG 24.1%, Q-EG 14.0%, R-EG 11.5%, noQ-MG 6.2%, minor-piece endings 9.6% (B-N 3.1, multi/uneven 2.8, N-N 1.3, B-B
same 1.3, B-B opposite 1.1), pawn endings 0.5%. Leading classes (loser's view): Q-MG B-vs-N 11.0%, R-EG a pawn down
8.4%, R+minor-EG rook against minors 7.7%, Q-MG a pawn down 5.7%, R+minor-EG B-vs-N 5.5%. Structure: the opponent has a
passer 34.5%, both sides 30.9%, none 22.9%, the loser only 11.8%. Turning move by the loser 71.3%, by the winner 28.7%.
**Against an equal opponent games are decided some 15 moves later and in the endgame; against stronger engines they
are decided in the queens-on middlegame.**

## 3. Conversion and defense

### Conversion (10+ moves at +150 or more by Fork's own eval)

| Set | Windows | Won | Drawn | Lost | Failure rate (Wilson 95%) |
|---|---|---|---|---|---|
| G core | 218 | 204 | 14 | 0 | 6.4% [3.9, 10.5] |
| G context | 650 | 646 | 4 | 0 | 0.6% [0.2, 1.6] |
| S (both sides) | 3,270 | 3,198 | 72 | 0 | 2.2% [1.8, 2.8] |

G core failures by opponent: Clover 6 of 33 windows, Stockfish 5 of 53, Altair 2 of 47, Marvin 1 of 85. **No conversion
window was ever lost.** Failures end by repetition (G 5, S 28), the fifty-move rule (G 5, S 22), insufficient material
(G 3, S 12), adjudication (S 9) and stalemate (G 1, S 1). Every failure has a drop point (eval below +50).

Material signatures at the drop point: S (72): R+minor endings 26 (16 rook against minors), queen endings 18 (10 with a
queen imbalance), minor-piece endings 17 (8 a piece against pawns, 5 opposite bishops), rook endings 9 (6 a pawn up);
structures: no passer on one wing 22, own passer on one wing 15, both passers on two wings 11. G core (14): minor-piece
endings 5 (4 a piece against pawns), R+minor 4 (3 rook against minors), queen endings 2, others 3; no passer on one wing
6. At the window's start the failure rates are 1-3% in every large class; the highest (S) are minor-piece multi/uneven 9
of 66 (13.6%), one-wing without a passer 10 of 85 (11.8%), one-wing with only the opponent's passer 5 of 23 (21.7%,
small), four or fewer pawns 18 of 329 (5.5%) and move 61+ 16 of 410 (3.9%).

### Defense (5+ moves with Fork's own eval in [-300, -100])

| Set | Windows | Lost | Drawn | Won | Loss rate (Wilson 95%) |
|---|---|---|---|---|---|
| G core | 432 | 422 | 7 | 3 | 97.7% [95.8, 98.7] |
| G context | 94 | 50 | 17 | 27 | 53.2% [43.2, 63.0] |
| S | 3,584 | 3,051 | 523 | 10 | 85.1% [83.9, 86.3] |

G core by opponent (windows, lost): Stockfish 212 / 211, Clover 99 / 99, Altair 76 / 72, Marvin 45 / 40. G core windows
start early (median move 24.5 against Stockfish, 39 of 212 by move 8) and in queens-on middlegames (Q-MG 344 of 432,
P19-24 282): there is no class in which Fork holds against the core opponents (every class with n >= 15 loses 92-100%).

S, held against lost by class at the window's start (loss rates): Q-MG 88.6% [87.2, 89.9] (n 2,157), noQ-MG 80.9%,
R+minor-EG 80.9%, Q-EG 82.6%, R-EG 75.0% [67.2, 81.4], minor multi/uneven 60.8% (n 51); one-wing without passers
47.5% [35.3, 60.0] (n 59) against two-wing without passers 86.2%; four or fewer pawns 60.2% [51.5, 68.2] (n 128) against
13-16 pawns 89.3%; phase P1-6 76.9% against P19-24 89.4%. **Fork defends drawish endgames reasonably and queens-on
middlegames hardly at all**, even against itself.

## 4. Network error map (S512ppr3's static evaluation, held-out g3j)

Two held-out sets, both labelled by S512ppr3 itself: idea 51's 3,131 kept positions of g3j-w05-val at 1M nodes (3,042
with a non-decided label) and idea 52's 2,000 uniform controls of g3j w00-w04 at 200k nodes with their game results.
The static evaluation is `fork evalfens` of the pinned build (equal to idea 52's stored eval_a on all 2,000 controls).
Error = static minus label, side to move's view; "signed" is that error times the label's sign (labels of 50 cp or
more), so negative means the static eval is closer to 0 than the search. 95% bootstrap intervals.

| Set | n | MAE cp | MAE win prob. | Signed cp | Brier vs result: static / label |
|---|---|---|---|---|---|
| i51, 1M | 3,131 | 116.4 [109.4, 123.1] | 0.050 [0.047, 0.053] | -126.4 [-135.2, -117.7] | - |
| idea 52 controls, 200k | 2,000 | 76.0 [70.2, 82.5] | 0.053 [0.049, 0.056] | -78.7 [-87.5, -71.3] | 0.063 / 0.052 |

**The systematic pattern is compression**: the static eval is nearer 0 than the search in every category, and the gap
grows with |label| (i51: 50-149 cp -11, 150-299 -39, 300-599 -95, 600+ -387; partly a selection effect, since bands are
by label). In win probability the errors sit in the 0-149 cp bands (0.076-0.079), where games are decided, against
0.012-0.032 above 300 cp.

By category (i51, 1M; n >= 60):

| Category | n | MAE cp | MAE win prob. | Signed cp |
|---|---|---|---|---|
| Q-MG level material | 244 | 31.4 | 0.068 | -32 |
| Q-MG B-vs-N | 227 | 72.5 | **0.080** | -77 |
| Q-MG a pawn up / down | 107 / 113 | 82.6 / 60.0 | 0.065 / 0.082 | -91 / -57 |
| Q-MG rook against minors | 100 | 145.9 | **0.084** | -141 |
| Q-MG minor-up | 537 | 98.6 | 0.038 | -87 |
| Q-MG queen imbalance | 68 | 147.7 | 0.017 | -147 |
| Q-EG (all) | 224 | 258.3 | 0.044 | -291 |
| Q-EG queen imbalance | 101 | 338.9 | 0.038 | -356 |
| noQ-MG | 307 | 72.6 | 0.050 | -70 |
| R+minor-EG rook against minors | 184 | 122.9 | 0.050 | -130 |
| R+minor-EG minor-up | 286 | 140.0 | 0.016 | -141 |
| R-EG | 189 | 119.1 | 0.053 | -150 |
| minor-EG minor-up | 64 | 350.7 | 0.030 | -372 |
| phase P19-24 / P13-18 / P7-12 / P1-6 | 1,024 / 580 / 702 / 808 | 61.5 / 136.2 / 145.4 / 147.9 | 0.057 / 0.054 / 0.045 / 0.040 | -58 / -147 / -154 / -173 |
| passers on both sides, two wings | 439 | 173.3 | 0.055 | -198 |
| no passer, two wings | 1,428 | 73.6 | 0.050 | -74 |

Against game results (idea 52's controls) the static eval is calibrated on average (mean predicted 0.492, label 0.500,
result 0.497), but its Brier score is worse than the label's in every category, most for passers on both sides (0.051
against 0.030), rook against minors (0.060 against 0.042) and phase P13-18 (0.072 against 0.052): there the 200k search
adds most over the net. Same-network caveat: the labels are S512ppr3's own; the Brier comparison against results is the
check that does not depend on them.

## 5. Data gaps (training share against game-deciding share)

T: 124,288 kept g3j positions (1 in 500), 67,154 of them with |stored score| 100-600 ("matched", added after the
declaration). Deciding positions: 478 G TPs (losses and wins), 3,287 S TPs, 90 conversion-failure drop points, 3,523
defense-loss window starts; 7,378 in all. Ratio = deciding share / training share (above 1: under-trained).

| Category (symmetric) | Training | Matched | Deciding (all) | Ratio | Matched ratio | G TPs only: share, ratio, matched |
|---|---|---|---|---|---|---|
| Q-MG, level material | 7.6% | **2.4%** | 9.4% | 1.23 | 3.96 | **23.0%**, 3.02, **9.74** |
| Q-MG, B-vs-N | 7.5% | 5.1% | 15.8% | 2.11 | 3.10 | 10.9%, 1.45, 2.14 |
| Q-MG, a pawn up or down | 5.3% | 3.8% | 9.7% | 1.84 | 2.56 | 9.2%, 1.75, 2.43 |
| Q-MG, passers on both sides | 2.5% | 2.8% | 6.7% | 2.68 | 2.39 | 2.68 (ratio) |
| Q-MG, rook against minors | 3.4% | 4.1% | 5.1% | 1.49 | 1.23 | 7.3%, 2.17, 1.78 |
| Q-EG, B-vs-N | 0.34% | 0.28% | 1.0% (76) | 2.99 | 3.68 | small |
| Q-EG, a pawn up or down | 0.73% | 0.57% | 1.8% (135) | 2.50 | 3.23 | small |
| R-EG, a pawn up or down | 2.4% | 1.6% | 3.8% | 1.56 | 2.34 | 1.9%, 0.77 |
| R-EG, passers on both sides | 1.8% | 1.4% | 3.2% | 1.77 | 2.32 | - |
| equal pieces, level pawns (all signatures) | 13.1% | **3.9%** | 14.9% | 1.14 | **3.85** | G 1.96 |
| equal pieces, a pawn up or down | 13.3% | 9.5% | 21.7% | 1.64 | 2.29 | G 1.07 |
| phase P13-18 | 15.8% | 17.6% | 23.7% | 1.50 | 1.35 | G 1.11 |
| at most 5 men | **0.0%** | 0.0% | 0.5% (40) | - | - | - |
| Over-trained: R+minor-EG | 25.1% | 26.9% | 17.3% | 0.69 | 0.64 | G 0.31 |
| Over-trained: R+minor-EG minor-up | 9.1% | 11.0% | 2.0% | 0.22 | 0.18 | - |
| Over-trained: Q-MG minor-up | 12.6% | 20.4% | 6.5% | 0.52 | 0.32 | G 1.17 |
| Over-trained: minor-EG B-B opposite | 1.75% | 0.70% | 0.62% | 0.36 | 0.89 | - |

Ranked gaps (deciding share large, matched ratio high, counts of 50 or more): (1) **queens-on middlegames with level
material** (matched 3.96 overall, 9.74 in the gauntlet): the positions where Fork loses to stronger engines, at decisive
scores, are about 2% of the training data at those scores; (2) **equal pieces, level pawns at any signature** (3.85
matched); (3) Q-MG B-vs-N (3.10) and Q-MG a pawn up or down (2.56); (4) queen endings with equal pieces (3.2-3.7, small
counts); (5) passers on both sides (2.3-2.4 for Q-MG and R-EG); (6) P13-18 (1.35-1.50). Why: g3j's games end by
score adjudication at 700 cp over 8 plies (44% of its 2.28 M games) or as decided openings at 400 cp (22%), and Lichess
openings with 2-4 random plies rarely give level-material positions with decisive scores; at decisive scores the data is
dominated by material imbalances (the three minor-up classes hold about a third of the matched positions). Positions of 5 men or fewer are absent
from g3j (table adjudication at 5 pieces; g3s2's Syzygy slice holds them, about 2.1% of g3s2); this matters for the
gauntlet, which plays without tables, not for TCEC. Caveat: g3j is one part of the mix (S512ppr3 trained on g3s3; 8b adds
later parts), the training sample is filtered to quiet positions, and G's random openings inflate the level-material
class among Fork's wins (50 of the 100 win TPs are Q-MG level material at book exit); among the 378 loss TPs the class
is 15.9%, still about 6.7 times its matched training share.

## 6. Time use at the turning points (TM (b) on)

Fork's time for its move F (the last at or before the TP) over its mean move time in that game (bootstrap 95%):

| Group | n | Median ratio | Last 3 moves | Share above the game mean | Baseline, same move buckets |
|---|---|---|---|---|---|
| Losses, all core | 327 | 0.70 [0.60, 0.81] | 0.82 [0.75, 0.88] | 38.8% [33.7, 44.2] | median 0.65, share 31.9% |
| Stockfish losses | 186 | 0.69 [0.57, 0.84] | 0.82 | 38.7% | 0.65, 32.5% |
| Clover losses | 67 | 0.62 [0.46, 0.81] | 0.78 | 34.3% | 0.65, 30.5% |
| Altair losses | 43 | 1.14 [0.79, 1.45] | 0.98 | 51.2% [36.8, 65.4] | 0.65, 29.9% |
| Marvin losses | 31 | 0.65 [0.46, 1.10] | 0.74 | 32.3% (small) | 0.65, 33.9% |
| Wins, all core | 88 | 0.69 [0.64, 0.75] | 0.71 | 21.6% | 1.34, 54.4% (mostly book exit) |

By class (losses): seen 0.79 [0.68, 0.98] (n 212), horizon 0.65 [0.29, 1.10] (n 13, small), **misjudgment 0.43 [0.31,
0.58]** (n 41). Baseline over all 115,813 Fork moves: median ratio 1.34 at moves 1-20, 0.65 at 21-40, 0.41 at 41-60, 0.42
at 61+. **Fork does not spend extra time at its turning points** (about the baseline for the same stage of the game), and
spends least where it misjudges: time management cannot react to danger the evaluation does not see. Not a data issue.

## Synthesis: ranked weaknesses

Costs use g3j's measured rate (212.5 M positions in 132,344 s on 6 threads: about 1.0 CPU-hour per million positions at
20,000 nodes) and about 5 GPU-hours per retrain arm (DESIGN.md §5.6, step 13). Every test follows the project's
conventions: a network candidate goes to the fixed-node screen against the default (800,000 nodes per move, 1,600 games)
and then the STC SPRT `--kind network` [0, 5] (alpha = beta = 0.05), each retrain its own idea; data arms are compared at
equal positions, from the same warm start and seed.

1. **Late realization of non-material disadvantages in queens-on middlegames (evaluation, not search).**
   Evidence: 541 core losses: 13 horizon (2.4%), 41 misjudgment at 8M, 212 gradual ("seen"), 163 with no deep turning
   point, 51 censored, 61 lost from book exit; turning swing median 82 cp; the opponents' sustained +150 a median 4.5-11.5
   moves before Fork's own -150 (aggregate), against 0.5 moves Fork against Fork; loss TPs Q-MG 69%, median move 31,
   P median 18; static eval above -100 at 53% of loss TPs; Q-MG level material 15.9% of the loss TPs (23% of all G
   deciding positions) against 2.4% of matched training positions; S512ppr3's largest win-probability errors in Q-MG B-vs-N and rook-against-minors.
   Size: most of the 541 core losses; directly the 204 misjudgment and no-deep-TP losses.
   Fix (data): a **positional-advantage slice**: starting positions from Fork's own datagen games (never gauntlet or
   SPRT games), queens on, equal pieces (level or one pawn apart), |label| 80-400 cp, drawn uniformly from g4 records;
   played out by Fork self-play at 80,000 nodes with score adjudication raised to 1,500 cp over 16 plies and no
   decided-opening cut, so the result half carries whether such advantages convert; labels as the standard recipe
   (score plus result), weighted at about 3% of the next snapshot (the matched gap is 3-10x, so 3% roughly doubles the
   class at decisive scores). Optionally, deeper labels (idea 51's TD(lambda), which passed its pre-test) on the same
   class.
   Cost: pilot 4 M positions at 80k nodes, about 16 CPU-hours (about 1.6 h on 10 threads); slice of 30 M positions,
   about 120 CPU-hours (12 h of the 10-thread machine), displacing about 30 M standard positions; 2 retrain arms
   (control and slice), about 10 GPU-hours.
   Test: (a) offline gate before training: a held-out gold set of 2,000 Fork-self-play positions of the class labelled
   at 1M nodes (about 0.5 h at 2 workers): the pilot's own labels must show a larger |label| (less compression) than the
   standard data on matched positions, else stop; (b) the slice arm against the control: validation loss on the class
   and its compression must fall by at least a third; (c) fixed-node screen, then STC SPRT [0, 5]; (d) a diagnostic
   rerun of the reference opponent (400 games, the same 200 openings), with Fork's balanced-opening score (0.088
   [0.060, 0.119] now) and the realization lag as secondary measures, never as the gate. Kill: H0 at STC, or no change in
   the class's compression.

2. **No defense in queens-on middlegames (the measurable symptom of 1).**
   Evidence: 0 of 164 games from unfavourable book exits against Stockfish and Clover; defense windows lost 97.7% in the
   core, 85.1% against Fork itself (Q-MG 88.6% against R-EG 75.0%, one wing without passers 47.5%, four or fewer pawns
   60.2%), 53.2% against the context anchors. Size: 422 core and 3,051 S defense losses; pentanomial: 151 of Stockfish's
   200 pairs are DL or LL.
   Fix (data): a **defense-start slice**, the mirror of 1: Fork's own datagen positions where the side to move is at -100
   to -300 with queens on, played out with adjudication raised as in 1, so the data holds defended middlegames and their
   true outcomes (today a -150 game is usually adjudicated or decided within 8 plies of reaching 700). It can share the
   generation run with 1 (one setting change, two selection rules), at about half of 1's positions.
   Cost: about 60 CPU-hours on top of 1; no separate retrain if merged with 1's arm; 5 GPU-hours if tested alone.
   Test: as 1; plus the SPRT's own pentanomial from UHO openings (both sides are defended in turn) and, as diagnostics,
   Fork's unfavourable-side score against Marvin (0.173 [0.106, 0.250]) in a gauntlet rerun.

3. **Compression of large advantages, especially queen and minor-piece imbalances (static against search).**
   Evidence: signed error -126 cp overall (i51), -356 in queen endings with a queen imbalance, -372 in minor-piece
   endings with a piece against pawns, -141 in R+minor minor-up, -387 in the 600+ band; 106 core wins without a deep
   TP. Size: few games: conversion failed in 14 of 218 core and 72 of 3,270 S windows, never lost; the drop points
   concentrate in rook against minors, queen imbalances and piece against pawns.
   Fix (data): the deferred **endgame-start slice R32** (8-16 pieces, |label| 50-400, 80k nodes, adjudication off) with
   its selection widened to rook-against-minor, queen-imbalance and piece-against-pawns classes, about 1% of a snapshot;
   or rescoring the existing positions of those classes at 200k nodes, which costs about 0.17 CPU-seconds per position:
   10 M positions about 470 CPU-hours (too dear), so the slice is the cheaper route.
   Cost: R32's estimate, about 10.5 h of the 10-thread machine (100 CPU-hours) plus a 4 M pilot (about 16 CPU-hours); 5
   GPU-hours for an arm. Test: R32's pilot gate and the endgame check (at most 15 of 900), then the fixed-node screen and
   STC SPRT [0, 5]; an LTC check if it passes, since conversion depth matters more at long time controls. Expected
   gain small (conversion is not where the gauntlet points are lost).

4. **Under-weighted deciding classes in the existing data (no new games needed).**
   Evidence: item 5's matched ratios: equal pieces with level pawns 3.85, Q-MG B-vs-N 3.10, Q-MG a pawn apart 2.56, both
   sides with passers 2.3-2.4, P13-18 1.35; over-weighted: R+minor-EG minor-up 0.18, Q-MG minor-up 0.32, R+minor-EG 0.64.
   Fix (data weighting): a class-weighted sampler in the trainer's loader (each position's class from its FEN, weights
   capped at 2x up and 0.5x down, normalised to equal positions seen).
   Cost: about 0 CPU-hours of data generation; a loader change (DESIGN review first); 5 GPU-hours per arm.
   Test: an 8c-style arm at equal positions against the control; per-class validation loss on g3j held-out records;
   fixed-node screen, STC SPRT [0, 5]. Kill: validation loss worse overall by more than the seed spread.

5. **Not weaknesses to fix with data**: search horizon (13 of 541 core losses), conversion (no window ever lost; 2-6%
   drawn), and time use (Fork spends its normal share at turning points; less where it misjudges). Time management at
   misjudged positions is a search or TM question, out of scope here.

Order and total: 1 and 2 as one generation run with two selection rules (pilot about 16 CPU-hours, then about 180
CPU-hours, 1 arm and its control: 10 GPU-hours); 4 as an arm in the next retrain (5 GPU-hours, no datagen); 3 after 1's
result (R32's existing plan). Every proposal is plan only, for the owner's review; nothing was generated, trained or
adopted.

## Unverified or not run

- The misjudgment counts depend on S512ppr3's own labels; a deeper or independent labeller was not used (not allowed).
- 51 core losses stayed censored after one extension (the slide began more than 24 plies before Fork's in-game turn);
  they were not extended further.
- The idea 52 top-disagreement stratum was not used.
- The cost figures for the proposed slices are estimates from g3j's measured rate and R32's plan, UNVERIFIED for 80k-node
  playouts with raised adjudication (longer games: likely more CPU per position).
- The training share comes from g3j only (not g3s3's full mix, nor 8b's).

## Files

Beside this report: item1-pairs.json, item2-turning-points.json, item3-conversion-defense.json,
item4-network-error.json, item5-data-gaps.json, item6-time.json (aggregates only: no FENs, no opponent evaluations).
Scripts and bulky data stayed outside the repository (the session's scratch folder and ~/fork-measure/cd).
