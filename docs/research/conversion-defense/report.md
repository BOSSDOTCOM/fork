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
