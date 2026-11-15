# Clean-room network survey, November 2026

Written 2026-11-14 for the owner's brief of the same day. Branch
`research/network-survey-2026-11`, from `phase-4` at b7ea9bf. For the owner's review; not
merged, not pushed.

## What this is

For each of the top 51 engines of the CCRL Blitz list, a record of what the engine publishes
in prose about its evaluation network: inputs, body, activations, quantisation, inference
speed work, training data and recipe. It builds on
[the engine survey of 2026-11-10](../engine-survey-2026-11/README.md) (its sections H, I and
J) and does not repeat that survey's search work.

| File | Contents |
|---|---|
| [matrix.md](matrix.md) | The 51 networks side by side (inputs; body, activations and quantisation; data), the published king-bucket layouts, and what the tables show |
| [shortlist.md](shortlist.md) | The brief's items 2 and 3 (owner's order of 2026-11-14, about 7:30 PM EST): the cost of every network change the survey surfaces under Fork's cost lesson (nps ratio, the fixed-node Elo it needs, data needs, GPU and engineering cost, fit with idea 180's phase-scale finding), and a ranked shortlist of 7 additions with their cheapest deciding tests |
| [speed.md](speed.md) | The brief's item 4: every network-speed technique the engines report, with reported gains, Fork's status and result, the expected gain on this PC and on TCEC's EPYC, and the untried ones ranked |
| [records/](records/) | The full record of every engine, in eight files by survey group, each with its own source table, credit lines and clean-room statement |
| [sources.md](sources.md) | Where each group's sources are, and the pages the coordinator opened |

**The brief arrived incomplete.** Its first part ended mid-sentence ("training data size and
type,") and its item 4 arrived separately. **Items 2 and 3 are answered in
[shortlist.md](shortlist.md)**, from the owner's order of 2026-11-14 (about 7:30 PM EST), which
restated them. The records also cover the training recipe and each engine's measured gains for
network changes, on the guess that the cut-off sentence went on to ask for them.

## Method

- **Clean room.** Eight research agents (kb-researcher) read public prose only: READMEs and
  other prose documents, release notes, papers, the Chess Programming Wiki, forum posts,
  OpenBench pages, TCEC questionnaires, vendor pages, and, as in the earlier survey, the
  text of pull requests, issues and commit messages (title and description, never the diff).
  No engine was cloned. No source file, header, build file, training script, trainer
  configuration, diff or network file was opened, and nothing was downloaded but prose
  pages. Every page was opened on 2026-11-14. Each record ends with the agent's own
  clean-room statement, which lists every page that came close (code fragments inside
  prose, review comments, bot summaries) and what was done about it.
- **The brief's source list names no pull-request or commit text.** I allowed it because the
  earlier survey used it and most network detail lives there. Every fact carries its source
  type, so facts resting on PR, issue or commit text can be told apart or struck.
- **Recorded**, because the brief asks for them: layer widths, bucket counts and layouts,
  input counts, layer stacks, output buckets and selectors, data sizes, the node or depth
  budget of data generation, net file sizes, speed figures, Elo figures.
- **Not recorded:** search constants; quantisation scales; clipping bounds; learning rates,
  result-blend weights and other trainer settings; code; identifiers; source file names.
  The agents saw such values on several prose pages and describe them as concepts only.
- **This write-up** opened three web pages (the CCRL list, twice, and through a fetch agent
  Wikipedia's Zen 4 and Epyc articles for cache sizes). The matrix and the speed file
  condense the agents' records; I did not reopen the engines' pages. Fork's side comes from
  the repository at phase-4 b7ea9bf: `docs/history/phase-4/perf-log.md`,
  `docs/research/tcec-hardware-test-plan.md`, `docs/ideas.md` (ideas 40 and 41),
  `docs/nets.md`, DESIGN.md §7, and the header comments of `src/eval/nnue/accumulator.hpp`
  and `net_file.hpp`.
- **Numbers.** Every Elo and nps figure is the engine's own, under its own conditions; SPRT
  stopping inflates passing estimates. They are priors for Fork, not predictions.
- **Tags.** Every engine and idea here is REFERENCE ONLY. Every engine's code, nets and data
  are OFF-LIMITS. What could not be confirmed is marked UNVERIFIED or "not published".

## The CCRL list and its date

CCRL Blitz, all engines, best versions only, "Computed on November 14, 2026 with Bayeselo
based on 2'190'694 games" (computerchess.org.uk/404/, fetched 2026-11-14). The earlier survey
used the list of November 7. What changed in the top 51:

- **Triumviratus 8.1** replaces 8.0 at #2 (3796).
- **Dragon by Komodo is listed as 3.2** (3755); the earlier survey's table says 3.3.
- **Incipit 0.6.0 is new at #23** (3728). It is by Coda's author and trains only on its own
  data.
- rofChade moves to #51. I kept it so that all 50 engines of the earlier survey are covered.

| Rank | Engine | Elo | ± | Games |
|---|---|---|---|---|
| 1 | Stockfish 19 8CPU | 3803 | 22 | 629 |
| 2 | Triumviratus 8.1 | 3796 | 18 | 800 |
| 3 | Torch v4 8CPU | 3777 | 14 | 1210 |
| 4 | Obsidian 16.0 8CPU | 3773 | 12 | 1949 |
| 5 | PlentyChess 8.0.0 | 3771 | 11 | 2383 |
| 6 | Coda 0.9.4 | 3768 | 13 | 1545 |
| 7 | Reckless 0.9.0 | 3765 | 10 | 3487 |
| 8 | Gaia 4.4.1 | 3763 | 15 | 1109 |
| 9-10 | Berserk 20250606 8CPU | 3759 | 14 | 1208 |
| 9-10 | Cinder 0.6.1 | 3759 | 12 | 2338 |
| 11 | Dragon by Komodo 3.2 8CPU | 3755 | 8 | 6081 |
| 12-13 | Alexandria 8.0.0 8CPU | 3754 | 10 | 3078 |
| 12-13 | pawnocchio 2.0 | 3754 | 11 | 2833 |
| 14 | Integral 8 | 3751 | 11 | 2373 |
| 15-16 | Caissa 2.0 | 3747 | 12 | 1892 |
| 15-16 | Viridithas 20.0.0 | 3747 | 11 | 2617 |
| 17 | Stormphrax 8.0.0 | 3744 | 11 | 2832 |
| 18 | Hobbes 3.0 | 3742 | 11 | 2321 |
| 19 | Horsie 1.1.0 8CPU | 3735 | 12 | 1947 |
| 20 | Lizard 11.2 8CPU | 3732 | 9 | 4909 |
| 21-22 | Astra 7.0 | 3729 | 10 | 3256 |
| 21-22 | Raphael 4.2.0 | 3729 | 12 | 2083 |
| 23 | Incipit 0.6.0 | 3728 | 17 | 797 |
| 24-26 | RubiChess 20240817 8CPU | 3727 | 9 | 4416 |
| 24-26 | Starzix 6.0 8CPU | 3727 | 9 | 4064 |
| 24-26 | Tarnished 6.0 (Eternal) | 3727 | 24 | 356 |
| 27 | Clover 9.1 | 3725 | 8 | 6849 |
| 28 | Ethereal 14.25 8CPU | 3722 | 8 | 6403 |
| 29 | Fritz 20 8CPU | 3721 | 12 | 1951 |
| 30 | Halogen 16.0.0 | 3720 | 8 | 7830 |
| 31 | Quanticade Cronus 3.0 | 3716 | 10 | 3759 |
| 32 | Igel 3.8.0 | 3714 | 15 | 1110 |
| 33 | PZChessBot 7.1 | 3711 | 11 | 2332 |
| 34 | ZigQueen 6.5.0 | 3709 | 14 | 1120 |
| 35 | Devre 7.0 | 3704 | 12 | 1903 |
| 36 | JustBot 0.5.0 | 3703 | 13 | 1439 |
| 37-38 | Titan 1.1.0 8CPU | 3702 | 9 | 4358 |
| 37-38 | Velvet 8.1.0 8CPU | 3702 | 10 | 2799 |
| 39 | Minke 7.0.0 | 3701 | 14 | 1177 |
| 40-41 | Ginkgo Santiago 1.0 8CPU | 3698 | 9 | 3808 |
| 40-41 | Revenge 4.0 8CPU | 3698 | 10 | 3380 |
| 42 | Tcheran 14.0 | 3697 | 14 | 1211 |
| 43-44 | Seer 2.8.0 8CPU | 3696 | 9 | 5053 |
| 43-44 | Uralochka 3.41a 8CPU | 3696 | 9 | 4942 |
| 45 | Lc0 0.29.0 w753723 RTX2080 | 3695 | 10 | 3258 |
| 46 | Motor 0.9.0 | 3694 | 9 | 4462 |
| 47-49 | Chess System Tal 3.00 | 3693 | 12 | 1743 |
| 47-49 | Renegade 1.3.0 | 3693 | 11 | 2250 |
| 47-49 | Stoofvlees II b5 RTX2080 | 3693 | 12 | 2063 |
| 50 | Rebel 17.0 | 3688 | 15 | 981 |
| 51 | rofChade 3.1 8CPU | 3686 | 8 | 5639 |

Groups: A Stockfish, Torch, Dragon, Ethereal; B Triumviratus, Obsidian, PlentyChess, Coda,
Reckless, Incipit; C Gaia, Cinder, Berserk, Alexandria, pawnocchio, Integral; D Caissa,
Viridithas, Stormphrax, Hobbes, Horsie, Lizard; E Astra, Raphael, RubiChess, Starzix,
Tarnished, Clover, Halogen; F Quanticade, Igel, PZChessBot, ZigQueen, Devre, JustBot, Titan;
G Velvet, Minke, Tcheran, Seer, Uralochka, Motor, Renegade; H Fritz, Ginkgo, Revenge, Lc0,
Chess System Tal, Stoofvlees, Rebel, rofChade.

**How much is published.** Six closed engines publish nothing about their architecture
(Fritz, Ginkgo, Revenge, Chess System Tal, Rebel, Dragon); Torch and Obsidian publish
fragments; Lc0 and Stoofvlees are GPU engines, not NNUE. Of the rest, several state their
architecture only for an earlier net (Astra, pawnocchio, Reckless, Clover, RubiChess), and
those cells are marked.

## Key findings

1. **One design dominates, and Fork's net is outside it on every axis.** The usual strong net
   is: mirrored piece inputs in 8 to 16 king buckets; an accumulator of 640 to 2048 whose two
   halves are multiplied pairwise; then 16 -> 32 -> 1 in 8 copies picked by piece count,
   with an int8, sparsely evaluated first dense layer. Of the 42 NNUE engines with a
   published body, 33 have such a head. The nine single-layer nets are all 1024 or wider.
   Fork has no king buckets, no head and 512 (matrix.md §4).
2. **The top of the list adds threat inputs and pawn pairs, and pays for them with width.**
   16 rated nets have threat inputs (about 60,000 per perspective) and 11 have pawn-pair
   inputs; 7 more engines added threats after their rated version. Every one that reports
   the step cut its accumulator when threats arrived (to 384, 640, 768 or 1024), and every
   threat net has a multi-layer head. Fork's two threat nets kept 512 on a single layer.
   Stockfish's own single-layer attempt (256 wide) was "−90 Elo with +50% time odds".
3. **Threat inputs were a net loss until three things were built**, by the engines' own
   account: incremental updates from a per-move list of changed threats, int8 threat rows,
   and lazy threat updates. Stockfish's branch stood at −9 STC before the first two;
   PlentyChess's first threat net failed STC (−3.1) with +45.5 at fixed nodes; PZChessBot
   lost about 30% nps and then regained two SPRTs of +28 and +22 from speed work alone.
   Fork's S512cl summed its contact inputs from scratch at every evaluation (0.195 of the
   default's nps) and S512+X added its exposure rows at every evaluation (0.818). By the
   peers' record those are tests of an unfinished implementation, not of the idea
   (speed.md, A7 to A11).
4. **Fork's fixed-nodes-up, clock-down pattern is everyone's, and they resolve it at a longer
   time control.** Larger nets won at fixed nodes, lost or drew at short control and passed
   at 40+0.4 or 60+0.6 in at least fifteen engines: for example Alexandria's 16-bucket net
   (−1.3 STC, +12.9 LTC), Raphael's head (−3.7, +6.6), Devre's new architecture (+0.4,
   +24.1), JustBot's 1024 width (−4.9, +8.9), Stormphrax's 24,000-node data (−28 STC, −7
   LTC, +13.6 at 60+0.6 on 8 threads). Counter-examples exist: pawnocchio's 1024 width lost
   at every single-thread control, Berserk reverted a wide single layer, and Fork's XGR-512
   lost at LTC as well (−30.56).
5. **Fork has a tenth to a thirtieth of its peers' data.** Nets trained wholly or mostly on
   the engine's own games used 6.6 B to 37.5 B positions; Fork has about 1.2 B after its
   filter. The three engines that publish both figures merged their first four king buckets
   at 1.7 B, 2.5 B and 3.0 B positions and reached sixteen at 10.7 B to 17 B (matrix.md §3).
   The earlier survey's reading, that buckets were grown with data, holds in every record.
6. **The own-data engines closest to Fork.** Incipit (33 B positions at 8,000 nodes per
   move, bootstrapped from a hand-written evaluation, every architecture step measured:
   buckets with a refresh cache, a QAT int8 hidden layer, pairwise, calibrated labels, pawn
   pairs, threats), Hobbes (37.5 B, with a prose log of every net), Raphael (29.8 B, the
   same), Minke, Tarnished, Integral, Halogen and Renegade. Their records are the most
   useful reading in `records/` for Fork's own route.
7. **What a head needs, against what AF-S had.** AF-S had pairwise products and an int8
   first dense layer, evaluated densely, and lost with a 32 cp quantisation loss. The
   engines pair the head with a sparse first dense layer, a neuron permutation and often a
   sparsity penalty in training (Raphael: 1.12 times faster in all; non-zero groups from 153
   to 71 of 256). For the rounding loss they train against the integer grid (Stockfish
   +4.4 STC, Caissa, ZigQueen, Incipit, Triumviratus) or keep the small later layers in
   float (Viridithas, Coda, Reckless, Incipit). Sparsity is not automatic: Coda measured the
   sparse kernel 1.8 to 2.4 times slower than dense when 58 to 67% of its inputs were
   non-zero.
8. **Speed: for Fork's present net the engines' list is nearly used up.** Of the 18
   techniques that apply to a single-layer net, Fork has 7, has measured and rejected 6 on
   this PC, has partly measured 1 and has never tried 4. What is left to measure now is the same code on other
   hardware or another compiler: the TCEC build target and compilers (Stockfish found a
   register spill worth up to 17% nps and a rolled loop worth about 41% on AVX-512 builds;
   Cinder gained 40 Elo from the same kind of fix), huge pages at a
   TCEC-sized hash, and int8 rows under cache pressure. NUMA placement is the largest
   unknown and waits for Phase 6 (speed.md §5).
9. **Labels.** The common own-data label is 5,000 soft nodes per move, with a second tier of
   12,000 to 25,000 added later; Fork labels everything at 20,000. Relabelling by a much
   larger own network gained +11 to +12 for pawnocchio and +3 to +4 for Tarnished;
   Viridithas's distillation from a large teacher gained +3.7 at LTC, and its relabelling by
   static output lost. A result-heavy final stage shifts the output scale: Viridithas
   measured 28 Elo between the same net with and without rescaling.
10. **Data hygiene with measured gains:** piece-count balancing (Halogen +13.2 LTC, Rebel's
    net author about +10), dropping positions where result and score disagree (Halogen
    +4.0 LTC), a 65/35 blend of adjudicated and unadjudicated games (Halogen +21 to +25
    against either alone), no TT or history sharing between data-generation games (Raphael
    +5.8).

## For the owner's attention

1. **Incipit's pawn-pair window has 608 inputs by the same rule as Fork's 608 pawn links**
   (pairs of pawns at most one rank apart on the same or adjacent files). Incipit merged
   its pawn pairs on 2026-10-20/21 (group B record; that its 0.6.0 net uses the 608 window
   is the agent's inference from the file size). Fork's links were planned on 2026-11-02 and
   built on 2026-11-05/06 (ideas.md 40), before either survey opened an Incipit page; the
   count follows from the geometry. Both descend from pawnocchio's pawn-pair idea, which
   ORIGINALITY.md already credits. I added a credit line for Incipit to ORIGINALITY.md on
   this branch. By the owner's order of 2026-11-14 (about 7:30 PM EST), one sentence recording the
   independent timeline is in ideas.md 40, under the R = 1 speed step.
2. **One second-hand source.** A Triumviratus design note holds a table of other engines'
   network shapes that its authors compiled by reading those engines' source. The group B
   agent used it only where tagged "second-hand" and never as the only basis of a field
   (PlentyChess's 640 width, Reckless's row types and later width). It is public prose,
   but it is one step from source code; those tagged facts can be struck.
3. **One restricted page.** The group H agent opened a public abstract page of the Stoofvlees
   journal article and only then saw its notice against use with AI tools. The two claims it
   added are removed from the record; only the fact that the page was opened remains.
4. **Close calls with code**, all disclosed in the statements and none used: two declaration
   lines of a Halogen review comment (group E), five lines of non-network diff context in two
   PZChessBot review comments (group F), two inline fragments in Uralochka's TCEC
   questionnaire (group G), ten lines of pseudocode in the Chessformer paper (group H), and a
   screenshot of Stockfish code in a third-party slide deck, deleted unread (group A).
5. **The CPU's name.** The repository's documents call this PC's CPU "Ryzen 7 7600X3D". The
   part is listed as Ryzen 5 7600X3D (Wikipedia; AMD's page would not load). I changed no
   document.
6. **Agents' reports.** The harness refused five agents' attempts to write their report
   file; they returned the report as text instead, and the records were assembled from that
   text. Nothing was lost.

## Corrections to the earlier survey

Found by the agents on the way; the earlier survey's files are not edited on this branch.

- **Minke 7.0.0's net is minke39, trained on 17 B positions**, not 23 B (that is minke44,
  merged eight weeks after the 7.0.0 tag).
- **"QAT: Motor +8, +12"** (comparison.md, J14) is a new net on a restart branch against its
  predecessor, with more positions, described as QAT. It is not an isolated test of
  quantisation-aware training.
- **Igel's "+13.8 refresh cache"** (I2) is its "cache accumulator" item of 3.8.0; its Finny
  table of 3.7.0 has no figure.
- **Dragon's rated version** on today's list is 3.2, not 3.3.
- Five of the group G engines have a TCEC questionnaire the earlier survey did not open
  (Velvet, Tcheran, Seer, Uralochka, Renegade).

## UNVERIFIED items that most affect a decision

Each record lists its own (roughly 500 fields or items in all are "not published" or
UNVERIFIED by the agents' counts).

- Everything about Torch v4's, Dragon's, Fritz's, Ginkgo's, Revenge's, Rebel's and Chess
  System Tal's networks beyond the fragments recorded.
- Obsidian 16.0's whole architecture (only in code).
- The rated nets' widths for Reckless 0.9.0, pawnocchio 2.0, Astra 7.0, Clover 9.1 and
  RubiChess (last published strings only).
- Most king-bucket layouts (six are published).
- Every expected gain in speed.md, and the EPYC 9754's cache sizes against AMD's own pages.
- Every estimate in shortlist.md (marked "(est.)"), and its three round 3 results taken from the
  coordinator's brief, not yet in the decisions log at b7ea9bf.
