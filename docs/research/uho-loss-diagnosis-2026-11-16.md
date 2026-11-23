# UHO games against Stockfish 19: a game diagnosis, the shared blind spot, and a hold test (2026-11-16)

A read-only analysis (Fable, 2026-11-16; the owner's order to keep these three parts). Nothing was built,
tested or changed for it. Three parts: (1) what the UHO games against Stockfish 19 show, move by move and in
numbers; (2) a note on what self-play tests cannot see; (3) a proposal for a "hold test", tied to the north-star
metric. Parts 1 and 2 are findings; part 3 is a proposal only: nothing in it is built, logged in ideas.md or
scheduled.

**Source.** Gauntlet run 43668560394 (2026-11-14/15 EST), Fork 1425f3a (default network r3kr1), book
`uho-reserved`, 10+0.1, one thread, Hash 16, no adjudication: the four Stockfish 19 shards, 400 games, each
opening played with both colours. Archived at `~/fork-data/gauntlet/run-43668560394`. Read with one-off
python-chess scripts fed to the interpreter inline (not kept; every definition they used is in §1.3).

**Data policy.** These games and Stockfish's scores in them are another engine's output: a diagnostic
reference only, **never training data, never a fitness signal** (docs/ORIGINALITY.md, "Training data
provenance"; the rule of tools/nnue/uho_diag.py). No position from them is recorded here. Stockfish's scores are
used as a coach's second opinion on Fork's moves; every figure below that leans on them says so.

**Relation to the analysis of 2026-11-13** (DESIGN.md decisions log; ideas.md idea 172): that analysis used the
earlier runs 43492072142 and 43492038248 and found 0 wins from 200 advantaged starts, the edge lost in 198 of
200, every loss beginning queens-on, and "no clear excess trade preference". This one repeats on the newer run
and agrees. What it adds: the costs by kind of move (§1.3), the timing of the losses on both sides (§1.2), and
the count of declined repetitions (§1.4).

## 1. The game diagnosis

### 1.1 The scoreboard, and the north star

The gauntlet report's own line for this run: **Fork 73.5/400 (18.4%), +0 =147 −253; Elo −259.0, 95% interval
−277.8 to −241.4** (pentanomial, 200 pairs, Ptnml(0-2) [54, 145, 1, 0, 0]). This is the north-star metric: the
UHO pair score against Stockfish, reported as the gauntlet's Stockfish gap on the UHO book.

Split by the side Fork was dealt (the favoured side is the sign of Stockfish's first score in the game):

| Fork had | Games | Won | Drew | Lost | Stockfish's first score for Fork (mean) | Fork's own first score (mean) |
|---|---|---|---|---|---|---|
| the better side | 200 | 0 | 145 | 55 | +0.96 | +0.47 |
| the worse side | 200 | 0 | 2 | 198 | −1.03 | −0.46 |

- The worse side is held in 1% of games. The better side is never won and is lost in 27.5%.
- Of 200 pairs, 54 score 0, 145 score half a point, 1 scores one point, none more.
- Depth is not the gap at this clock: both engines report a median depth of 17 (the two engines' depth figures
  are not the same quantity; taken only as "no large difference").
- The two score columns are in different units. Fork's search score maps to results on a logistic scale of 56-69
  cp against the network's 88 (idea 172's calibration, on r8brft1), and r8brft1's static and 100k-node scores
  were 0.42 and 0.51 of Stockfish's on the advantaged starts (uho_diag's baselines, ideas.md idea 172). So Fork's
  smaller numbers are mostly units, not by themselves a misjudgment.

### 1.2 What the games look like (25 read move by move)

Seven worse-side losses in full and six more through their first 18 moves, six failed conversions, five losses
from the better side, both holds; chosen by a fixed-seed sample within each class.

**Worse side.** The same story in nearly every game. Fork develops and then waits: knight tours, king steps,
rook lifts with no target. Stockfish spends the same moves bringing pawns and pieces toward Fork's king with
quiet moves. Fork's own score stays level while Stockfish's falls by a few tenths every move. No single Fork
move is a blunder; by the time Fork's score moves, the attack has landed.

- Stockfish's score for Fork first reaches −2.0 at Fork's **11th move after the book** (median).
- At that moment Fork's own score is −0.65 (median; quartiles −0.83, −0.46). Fork's own score reaches −2.0
  **13 moves later** (median; quartiles 9, 19). (The gap is partly the unit difference of §1.1. The
  conversion-and-defense analysis measured the same lag another way, as quoted in
  docs/research/novel-ideas-2026-11-11.md, E11: "opponents see +150 a median 4.5–11.5 moves before Fork sees
  −150, against 0.5 moves between two Forks.")
- 177 of the 198 losses passed that point with both queens on the board.
- Over its first ten moves after the book Fork's score, as Stockfish sees it, falls by 0.74 (median; mean 0.98).

**Better side, drawn.** The edge is not lost in an ending. It is gone before the middlegame is over, and it is
never built on.

- Stockfish's view of Fork's edge first drops below +0.30 at Fork's **14th move after the book** (median;
  quartiles 10, 19); in the games Fork went on to lose, at the 10th.
- Over its first ten moves Fork gives up 0.46 of the edge (median).
- The largest edge Fork reaches in a game has a median of +1.04, about the starting value. **3% of the 200 games
  ever reach +1.5, 1% reach +2.0, none reach +3.0.**
- The leak is small moves (about 0.05 a move), with now and then one careless pawn move costing half a pawn.
- Once the edge is gone Fork's own score stays at +0.3 to +0.6 for dozens of moves: over all positions where
  Stockfish says 0.00 ± 0.2, Fork's median is +0.26 (the "level queenless positions overrated" side of the
  adopted explanation, seen here in every phase).

**Better side, lost.** Four of the five games read are accidents to Fork's own king: pawn moves in front of its
castled king in a quiet position, followed by the opponent's break; winning pawns, in one game even promoting,
while a file opens on its king (Fork's own score at its highest of the game as this happens); a pawn capture
that opens lines to its king. The fifth is a blocked position in which Fork shuffles for 25 moves at about +0.55
of its own score while Stockfish, at 0.00, prepares the one pawn break and wins a 215-ply game.

**The two holds.** Neither was a defence: in one, Stockfish's edge was gone by move 18 through its own choices;
the other was drawn very late from a position Stockfish scored below −5.

### 1.3 Measurements over all 400 games

Definitions. The **cost** of a Fork move is Stockfish's score for Fork at Stockfish's next move minus its score
at its previous move (negative: Fork's position got worse by Stockfish's judgement; the difference includes one
Stockfish move). Only moves where the earlier score is within ±5 and the later within ±8 are counted. **King
ring**: Fork's king square and its neighbours; the pressure count is the number of distinct enemy pieces other
than pawns and the king that attack at least one of those squares before Fork's move. **Quiet**: not a capture.

| Kind of Fork move | Moves | Mean cost | Share costing half a pawn or more |
|---|---|---|---|
| all | 23,988 | −0.058 | |
| captures | 3,297 | −0.067 | 4.8% |
| quiet piece moves | 18,220 | −0.052 | 3.4% |
| quiet pawn moves | 2,471 | −0.092 | 5.9% |
| quiet pawn moves on the king's file or a neighbouring file | 971 | −0.081 | 5.5% |
| queen takes queen | 200 | −0.008 | 0.5% |
| with 2 or more enemy pieces on the king ring | 2,611 | −0.105 | 7.7% |
| with none | 10,675 | −0.053 | 3.1% |
| captures with 2 or more on the king ring | 527 | −0.114 | 8.2% |
| while ahead (Stockfish +0.5 or more for Fork), quiet | 2,391 | −0.046 | 1.5% |
| while behind (−0.5 or worse), quiet | 5,476 | −0.174 | 12.7% |
| Fork's own score 0.5 or more above Stockfish's | 9,744 | −0.107 | 8.2% |
| Fork's own score within 0.2 of Stockfish's | 7,319 | −0.019 | 0.7% |
| played in under 0.15 s | 13,643 | −0.031 | 2.3% |
| took 0.6 s or more | 2,186 | −0.139 | 7.9% |

Reading it:

- **Where Fork's evaluation disagrees with Stockfish's, Fork plays badly**: about ten times the rate of
  expensive moves (8.2% against 0.7%). The evaluation's blind spots are where the mistakes are.
- **Pressure on Fork's king about doubles its error rate** (7.7% against 3.1%). Captures made under that
  pressure are no worse than other moves made under it, so the pattern is the pressure, not greed.
- **Quiet pawn moves are Fork's most expensive ordinary moves**: nearly twice the mean cost of quiet piece
  moves. Caution: Stockfish's score may react at once to a change of structure and only later to a piece
  shuffle, so part of this may be when the cost is booked, not how large it is. A Fork-only check would settle
  it: Fork at a much larger node count re-judging its own pawn and piece moves in its own games.
- **Queen trades cost nothing at the moment they are made**, in line with the 2026-11-13 finding. What differs
  is who keeps the queens: with Fork on the better side the first queen-takes-queen was Stockfish's in 89 games,
  Fork's in 70, and absent in 41; with Stockfish on the better side, Stockfish's in 77, Fork's in 51, absent in
  72. At Fork's 25th move after the book both queens are still on in 45% of the games where Fork had the better
  side and in 72% of those where Stockfish had it.
- **Fork already thinks longest where it is in trouble, and it does not help**: its slow moves are its most
  expensive. The long thinks come after the damage. Fork spends 31% of its thinking time (median) on its first
  ten moves after the book.

### 1.4 Were draws on offer?

For every Fork move in the lost games: did Fork have a legal move that repeated an earlier position of the game,
and play something else?

| Class | Games | Games with such a moment | ... while Stockfish already had Fork at −0.3 or worse |
|---|---|---|---|
| worse side, lost | 198 | 0 | 0 |
| better side, lost | 55 | 12 | 0 |

So on the worse side no draw was ever on offer to decline: a different value for a draw (contempt of either
sign) cannot rescue those games. On the better side it could change at most 12 of 200 games, and only by taking
a repetition before Fork is worse. (docs/research/novel-ideas-2026-11-11.md left out a trend-driven draw value
partly because "the evidence that drawing lines existed in the lost games is missing"; this is that evidence,
and it is negative for the worse side.)

### 1.5 What the diagnosis does not show

- A single moment where the better side is thrown away. The edge leaks about a twentieth of a pawn a move for
  fourteen moves; that is general strength.
- A trade-seeking habit (as on 2026-11-13).
- A depth gap.

## 2. Self-play tests cannot see a blind spot both sides share

Fork's own record already states this; it is repeated here because it decides how some changes must be judged.

- The think tank's evidence (docs/research/phase4-think-tank/phase-b-specialists.md, "B-chess (C): what Fork's
  network still lacks", its summary item 3 and section "0.5 E4. Where Fork loses to other engines", measured on
  gauntlet run 41465146207): of 217 losses to the three strongest anchors, "Fork loses in early
  middlegames with queens on and kings under attack, not in endgames"; at Fork's blind spots "Fork's king zone
  hit by ≥ 3 pieces" is over-represented 2.5-4.8x; and "Self-play shows **no** king-safety residual ... The net
  is calibrated to Fork-vs-Fork play: **a blind spot both sides share is invisible to self-play calibration and
  to self-play SPRT outcome statistics.**"
- §1.3 above is the same pattern on a different set of games and a different opponent: error doubles under king
  pressure, and follows the evaluation's disagreement with a stronger engine.
- The transfer measurements point the same way: self-play gains have shown against the anchors at 0.65
  (0.36-0.99; 2026-11-09), 0.28 for the 2026-11-11 window (0.02-0.56), 0.48 running (0.33-0.66), and 0.66 on the
  UHO book (0.31-1.05) (docs/research/transfer-testing/report.md; DESIGN.md decisions log, 2026-11-11).

Consequences for testing:

1. A change aimed at a shared blind spot (king danger is the clear case) can be worth Elo against other engines
   and read **zero in an ordinary SPRT**, because the opponent in that SPRT does not make the attacks the change
   defends against, nor defend against the attacks it finds.
2. For such a change an SPRT **loss** still counts (it costs something against an equal), but a **flat** result
   is not evidence that it does nothing. Only games against other engines can say.
3. The check that exists for this, the paired anchor match (1,600 games against Clover 6.1 and Altair 7.0.0, SE
   about 10 Elo), resolves gains of 20 Elo and more. Most single changes are smaller. This is the gap the
   proposal in §3 is meant to narrow.
4. A stronger *Fork* (more time, nodes or threads) shares Fork's blind spots, so it is no substitute for another
   engine where the change is about knowledge. It can stand in only where the change is about time or depth.

## 3. Proposal: a hold test, read on the north star's scale

**Status: proposal only.** Not built, not in ideas.md, not scheduled; the owner decides whether it is logged.
Every cost and Elo figure in this section is an estimate, marked UNVERIFIED where it is not from a Fork
measurement.

### 3.1 The problem it answers

The north star (§1.1) is the UHO pair score against Stockfish. As a *test* it is at its floor: the pair
distribution is [54, 145, 1, 0, 0], the worse side is held in 2 games of 200 and the better side won in none. A
change would have to be very large to move those counts, so the metric that matters most cannot at present tell
two candidate versions apart. The tests that can tell them apart are between equals, with the limits of §2. And
the record has set ideas aside for exactly this reason (docs/research/novel-ideas-2026-11-11.md, the ideas left
out: a trend-driven draw value "cannot be tested in self-play").

### 3.2 The test

The north star's own measurement, moved down to a rung where it can move:

- **Format:** the gauntlet's: the `uho-reserved` book, every opening with both colours, 10+0.1, one thread, the
  same report (mean pair score, logistic Elo, pentanomial interval). No new statistic.
- **Opponent:** one that is stronger than Fork by roughly 100 Elo instead of 259, so that held and won pairs are
  common enough to count.
  - Preferred: **another engine** about a class above Fork. The current anchor list has none: on this run's
    Ordo table Fork is 3597.5 ± 19.2 on the UHO book and the strongest anchor, Clover 6.1, is fixed at 3639.
    Choosing one is a kb-researcher task (licence, a build pinned by hash, its CCRL rating), as for the
    existing anchors.
  - Second, for changes about time or depth only (§2 item 4): **Fork itself at a node or time advantage**, the
    advantage chosen so that the gap is about 100 Elo. Fork's thread-odds matches give the order of magnitude
    (2 threads against 1: +34.20 ± 6.13 at STC; 4 against 1: +138.99 ± 22.64 on the PC); the node ratio that
    gives 100 Elo is UNVERIFIED and is measured first.
- **Read-outs, beside the pair score:** the hold rate of the worse side and the win rate of the better side,
  each with its pentanomial interval, since the north star is the sum of exactly those two.
- **Use:** a second judge, beside the SPRT, for changes whose point is behaviour against a stronger opponent or
  knowledge of a shared blind spot. It never replaces the SPRT and never adopts anything by itself: "untested
  changes never ship" stays as it is, and the owner decides what a hold-test result means for adoption.

### 3.3 Why it is tied to the north star and not a new metric

It measures the same thing on the same book in the same format; only the opponent's distance changes. A result
on the rung is a statement about the north star's two components at a distance where they are measurable. If
the rung and the north star ever disagree in sign, the north star wins.

### 3.4 The first measurement, which can kill it

Before any use: run the rung for two Fork versions whose difference against the anchors is already measured by
the gauntlets (for example 117d26a and 1425f3a, both of which played the balanced and the UHO gauntlet; their
paired gains are in those runs' reports).

- About 2,000 games per version against the chosen opponent (1,000 pairs): by the gauntlet's own shard times,
  hours of runner time (UNVERIFIED until a shard is timed against the new opponent). No GPU.
- **Kill:** if the rung's pair score does not separate the two versions in the direction the anchors do, or its
  interval is no narrower than the Stockfish reference's would be for the same games, it adds nothing and is
  dropped.
- **Keep:** if it separates them, record its standard error per 1,000 pairs and the smallest gain it resolves,
  and only then decide what it is used for.

### 3.5 Limits

- One opponent is one style. A change can help against this engine and not against Stockfish; the rung narrows
  the gap between self-play and the north star, it does not close it.
- A stronger Fork as the opponent cannot see knowledge changes (§2 item 4).
- It costs runner time that SPRT shards also use; it is for the few changes of §3.2's kind, not for every
  search constant.
