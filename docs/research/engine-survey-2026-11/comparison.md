# Comparison: technique → engines → reported gains → Fork's status

Survey of 2026-11-10 (README.md). One table, split by area. How to read it:

- **Engines and reported gains.** Each engine's own measurement under its
  own conditions: "a / b" is STC / LTC, "FN" is fixed nodes, "4T" or "8T" a
  thread count. "(b)" marks a gain bundled with other changes. Engines are
  named without a number when they list the technique without a figure.
- **Prior.** The think tank's entry: S1, S2 or S3 section, or an R item.
  "new" means no prior survey covered it.
- **Fork's status**, from `origin/phase-4`. Fork's Elo figures come from
  `docs/history/phase-3/sprt-log.md` and `docs/history/phase-4/sprt-log.md`,
  with STC 8+0.08 and LTC 40+0.4, one thread, ± the 95% interval.
  - **have** (with its result);
  - **tried, failed** (with Fork's result);
  - **in progress** or **queued** (where: a §5.6 step, an R item or an
    ideas.md number);
  - **parked**;
  - **never tried**;
  - **excluded** (an owner rule, or out of Fork's scope).
- ⚑ flags a **shared idea**: four or more independent engines in the top 50
  report a measured gain.

Engines with the same author or lineage count once: Horsie and Lizard,
Coda and Incipit, Fritz and Ginkgo, Rebel and Chess System Tal.

## A. Time management

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| A1 ⚑ | Node-fraction time management (scale the soft limit by the best move's node share) | JustBot +29.7 / +22.4; PZChessBot +24.4 / +16.3; Tcheran +10.9 / +16.0; Raphael +15.0 / +10.1; Ethereal +9.85 / +9.66 (40/10 +20.9); Devre +15.4; Hobbes +10.1; Minke +6.7 / +8.5; Titan +4.2; Integral +16.7 (a borrowed scheme); Tarnished +56.8 (weak base); Coda, Cinder, Renegade, RubiChess | S2 4.2, R8 | **have**: variant (b), stability plus node share, +18.69 ± 7.18 STC, +10.23 ± 5.14 LTC (2026-11-08) |
| A2 ⚑ | Best-move stability | Lizard +16.2 / +17.9; Minke +9.5 / +4.1; Hobbes +6.6 / +8.0; Devre +7.8; Raphael +2.4 / +4.2; JustBot +1.9; Renegade, ZigQueen | S2 4.2, R8 | **have**: in variant (b) (same test) |
| A3 ⚑ | Score or eval-stability (trend) time | JustBot +4.5; Lizard +4.2; Raphael +3.6 / +2.85; Minke +3.2 / +3.4; Devre +3.1; Hobbes +6.2 / +2.4; Alexandria 9.1 (b) | S2 4.2 | **parked**: idea 64, score-fall extension; an equal-time replay showed no gain over (b); no SPRT (owner, 2026-11-09) |
| A4 | Complexity time management | Tarnished +4.5 / +6.6; PZChessBot +8.8, later removed (removal non-regression) | new | **never tried** |
| A5 | Less time when behind on the clock | Stockfish +1.1 / +1.1; Triumviratus +5.2 at 6+0.06, about 0 at 30+0.3 | new | **never tried** (Phase 5 scope) |
| A6 | Surprise rule; more time in defence | Triumviratus +6.2 and +7.3 at 40+0.4 | new | **never tried** (Phase 5 scope) |
| A7 | SPSA of time-management constants | Raphael +8.15 LTC | new | **excluded**: time-management parameters are never in SPSA (think-tank decision 4) |

## B. Pruning and node-level selectivity

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| B1 | Tier-1 pruning: RFP, NMP, LMR, LMP, futility, SEE pruning | universal | KB | **have**: tier-1 bundle H1 (Phase 3); SEE pruning +21.16 ± 10.08 |
| B2 ⚑ | A full SPSA pass of search margins on the NNUE eval | Igel +24.9 / +19.5 (400k games); Tcheran +24.4, +16.6; Hobbes LTC tunes up to +20.1; Raphael +14.6 LTC; Tarnished +12.0 LTC; Horsie +10.3 / +11.2; Integral +11.3 LTC; Berserk +10.0 LTC; Quanticade +6.1 VVLTC; Cinder +4.9, +5.8 | S2 4.1, R14 | **have**: R14's early SPSA of seven margins, +37.93 ± 10.03 STC, +29.93 ± 8.71 LTC (2026-11-09); final retune queued (step 19, R24) |
| B3 ⚑ | Fail-firm or blended returns (RFP, stand-pat, fail-high) | PZChessBot +16.6, RFP +10.0; Hobbes RFP +9.8, stand-pat +4.0; Integral +7.6 / +2.0; Tcheran RFP +7.2, qsearch +2.9; Lizard qsearch +5.9; pawnocchio +5.3, ProbCut +2.9 LTC; Tarnished +4.5, +3.0; Halogen fail-medium +4.0 / +4.6; ZigQueen (b) | S2 4.7, R7 | **queued**: R7, first in §5.6 step 12 |
| B4 ⚑ | Razoring | Tarnished +12.5; Hobbes +8.0; Tcheran +7.7; Lizard +2.8; Halogen +1.35 / +2.1; Stockfish all-nodes-only form +1.35 / +2.6 | S1 7.3 | **queued**: built on tier2/b4, demoted to a final-retune SPSA dimension (owner, 2026-11-10; step 19) |
| B5 ⚑ | NMP only at expected cut nodes | Tcheran +8.6; Cinder +5.0; PZChessBot +4.0 (merged at LLR 1.95); Halogen +4.1 / +2.0 (S2); Renegade | S2 4.5, R6 | **queued**: R6, step 12 |
| B6 | NMP verification search | Igel +2.0 / +2.5; Lizard +2.0; Raphael non-regression; Halogen gained by removing it (KB) | S2 6 | **never tried** |
| B7 | NMP and RFP gates from the TT bound; NMP eval margin | Hobbes gates +4.5 and +5.0, margin +13.05; Raphael +2.0; Halogen extra NMP margin +1.2 / +3.4 | new | **never tried** (UNVERIFIED: Fork's NMP entry conditions were not read in full) |
| B8 | Improving flag in RFP | Raphael +9.2; Ethereal +1.8 / +2.9; Hobbes | S1 7.1.c | **tried, failed**: rising RFP −3.78 ± 2.92 (H0, 19,200 games) |
| B9 | Improving flag in LMP and LMR | Tarnished +3.7 (LMR); Hobbes +1.6 (LMP); Lizard | S1 7.1.c, R17 | **queued**: R17, step 12 |
| B10 ⚑ | Opponent-worsening RFP | Raphael +6.4; Hobbes +3.5; Quanticade +1.85; Berserk +1.1 LTC; Starzix (title only) | new | **never tried** |
| B11 ⚑ | History-scaled pruning margins (SEE, futility, LMP, qsearch SEE) | Ethereal SEE +7.0 / +2.3; Halogen +4.8; Reckless qsearch SEE +4.5 / +3.6; Raphael futility +3.3, LMP +2.0 LTC; Quanticade RFP +3.0; Tarnished futility +2.3 | new | **never tried** |
| B12 ⚑ | Check-aware pruning: an LMP guard or no futility for checking quiets, also in qsearch | Reckless LMP guard +2.8 / **+9.5**; pawnocchio LMP +3.6 / **+9.0**, qsearch +5.5; Raphael +2.2, qsearch +5.2; Viridithas checks tactical in SEE pruning +3.1 STC | new | **never tried**. Fork relieves checking quiets in LMR only (check relief, +11.26 ± 5.54) |
| B13 | Quiet history pruning | Tarnished +8.9; Halogen, Viridithas (S2); Gaia, Astra | S2 4 item 8, R29 | **never tried in a firing form** (owner, 2026-11-10): built on tier2/b4 as "history-skip" and dropped untested; that variant changed only 30 bench nodes, so it hardly fired. Eligible for a test with a threshold that fires |
| B14 | Bad-capture futility | Hobbes +6.5; Tarnished +2.6 | KB T36 | **queued**: a final-retune SPSA dimension (owner, 2026-11-10) |
| B15 ⚑ | ProbCut and small (TT) ProbCut | Integral +13.4 LTC; pawnocchio +8.7 LTC; Halogen +5.0 / +6.3; Quanticade +5.5 at 60+0.6; Hobbes +5.3 / +3.7; Lizard evasion form +4.2; Raphael +3.5; Tcheran +3.6; JustBot +2.3; Alexandria 8.0 (b) | S1 7.3, S2 supplement | **tried, failed**: −5.29 ± 3.58 (H0); no retest, at LTC either (owner) |
| B16 | Qsearch LMP (move-count pruning) | Raphael +5.1; Tarnished +4.1; Hobbes +3.3; Obsidian (commit title) | new | **never tried** |
| B17 | Qsearch futility or delta pruning | Hobbes +14; Quanticade +4.1; Minke gained +6.6 by removing it | S2, synthesis §2.1 | **tried, failed**: delta form inconclusive, −0.40 ± 2.93 after 27,200 games; qsearch futility "filler only" |
| B18 | No check extension | removal gains: JustBot +10.0; Halogen +8.3 STC (LTC non-regression); Astra, Raphael, Renegade, Cinder | S1 7.3 | **have**: Fork never had one |
| B19 | Mate-seeking mode, SPRTed as non-regression against a disabled control | Stockfish (matetrack +167 mates) | new | **never tried** (idea 22, related, untested) |

## C. Extensions and reductions

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| C1 ⚑ | Singular extension | Tcheran +19.9 / +34.0; Hobbes +25; Ethereal wrapper form +16.8 / +3.7; Tarnished +15.9; Devre 5.0 | KB T27 | **have**: +14.12 ± 6.55 STC; LTC on/off +25.83 ± 6.38 |
| C2 | Multi-cut | Tcheran +8.0; Raphael +3.6, fail-firm +5.2 / +4.1; Tarnished +2.1 | KB T28 | **have**: +9.19 ± 4.62 STC; LTC on/off +6.65 ± 3.65 |
| C3 ⚑ | Negative extension | Tarnished +10.8; Lizard +7.1; Hobbes +6.4; Ethereal +3.4 / +6.4; Halogen double-negative +5.0; Raphael, Tarnished cut-node forms +2.9, +3.0 | S2 supplement, R40 | **tried, failed**: ungated −8.73 ± 4.98 (H0). The cut-node form is queued as a new idea (R40, LTC) |
| C4 ⚑ | Double and triple extensions | Tarnished +5.8 / +12.1; Halogen triple +7.8 LTC; Ethereal +6.8 / +8.9; Raphael +2.8; Lizard triple +2.8 LTC; Hobbes PV +2.2 LTC | S1 7.2.10, R28 | **queued**: R28, LTC only |
| C5 ⚑ | Low-depth singular extension | ZigQueen +9; Triumviratus low-depth hash-move extension +4.5; Horsie +3.4 LTC; Hobbes +2.3 LTC; Raphael +2.2 | new | **queued** indirectly: SingularMinDepth's SPSA range widened down to 3 for the final retune (step 19) |
| C6 | Singular refinements (TT-PV window, beta from TT-move history, cutoff when the singular bar beats beta) | Tcheran +7.0; Hobbes +5.3 / +3.9, +2.6 / +3.0, +5.6 / +5.2; Integral +4.0 LTC | new | **never tried** |
| C7 ⚑ | Internal iterative reduction (and its node-type gates) | Igel IID +4.0 / +14.5; Ethereal cut-node +4.4 / +2.9, shallow-TT +2.9 / +3.3, PV +1.4 / +2.1; Lizard +2.6, +4.7; Halogen +4.0 / +2.2 | KB T26, R6 | **have**: +21.45 ± 5.98 STC, +26.25 ± 6.65 LTC; node-type gating queued (R6) |
| C8 ⚑ | More reduction at expected cut nodes | Hobbes +20.8; Tarnished +4.7; Lizard +2.7; Raphael +2.4 | S1 7.1.b, R4 | **queued**: R4; kept in the 2026-11-10 trim (head-to-head, then design R) |
| C9 | TT-PV in LMR | Tarnished +9.6; Lizard +2.5; Horsie (TT-PV fail-low +2.5) | S1 7.1.b, R4 | **queued**: PV-trace deferred to the end-of-phase re-validation (owner, 2026-11-10) |
| C10 ⚑ | History term in LMR | Hobbes +17.3; Raphael +8.65; Lizard conthist weighting +5.3; Tarnished +5.0; Cinder +5.0 | S1 7.1.d, R20 | **tried, failed**: −10.81 ± 5.01 (H0); a centred, mean-preserving form queued (R20) |
| C11 ⚑ | Deeper or shallower re-search after LMR | Integral +6.1; Tarnished +5.8; Hobbes +4.5; pawnocchio +3.5 / +4.6; Ethereal +2.7 / +2.3; Raphael +2.5 | S1 item 7, R10 | **queued**: R10 |
| C12 ⚑ | Hindsight extension or reduction (eval change after a reduction) | Hobbes +7.9, +4.8; Tcheran +4.5, +3.3; JustBot +2.35 / +3.9, +3.8; Raphael +3.0; Devre +2.4; Lizard +2.25; Tarnished +1.65 | S2 4 item 9, R41 | **queued**: R41, LTC |
| C13 | LMR for late captures | Lizard non-PV captures +4.25, capture history in LMR +2.5; RubiChess | S1 item 3, R18 | **queued**: R18 |
| C14 | Check-related LMR terms | Quanticade less reduction for checks +6.6; Raphael +3.05 | KB T16 | **have**: check relief +11.26 ± 5.54; LMR on evasions +4.21 ± 2.89 |
| C15 ⚑ | Correction size ("corrplexity") in LMR, RFP or futility | Tarnished +4.1; Reckless +3.8 LTC; Raphael +2.6 twice; Devre +2.6; Minke +2.6; JustBot +1.85; Motor +1.7 | new | **never tried**: needs a correction table first (E2, E3) |
| C16 | Child fail-high count in LMR; null-move fail-high count | Tarnished +9.8; Stockfish +1.3 / +1.3 | new | **never tried** |
| C17 | Alpha-raise reduction (less depth for the remaining moves once alpha rises) | Hobbes +12.5 (early); pawnocchio folded it into LMR (non-regression); Stockfish | new | **never tried** |
| C18 | Fractional depth or fractional LMR | Raphael 0 / +7.35; Cinder +4.0; PlentyChess (S2: LTC-only) | S2 6, R20 | **queued**: round-once LMR (R20); idea 43's full refactor left out of Phase 4 |

## D. History and move ordering

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| D1 | Butterfly history with malus | universal | KB | **have**: Phase 3 (history H1) |
| D2 | Continuation history, 1 and 2 plies | universal; Tarnished 2-ply +4.9 | KB T10 | **have**: reply table +11.46 ± 5.57, follow table +7.22 ± 3.92 |
| D3 | Continuation history at 4 to 6 plies | Halogen +4.6; Hobbes +2.0 / +1.5; Alexandria 9.1, Astra (b) | new | **never tried** |
| D4 | Capture history | Tarnished +7.1; Igel +2.9 / +7.0 | KB T11 | **have**: take history +4.53 ± 2.99 |
| D5 ⚑ | Threat-indexed quiet history | Quanticade +11.4; PZChessBot +11.0 / +17.0; Cinder +10.2; Tcheran +9.3 LTC; Raphael +5.7; Integral +5.7; Halogen +5.15; Hobbes +4.7; Tarnished +4.0; Lizard +2.7; pawnocchio +2.5; Ethereal +2.3 / +2.9; Igel +1.75 / +2.85; Coda, ZigQueen, Renegade | KB T56 | **tried, failed**: T56 is the common form (the butterfly history in four buckets by whether an enemy piece attacks the from- and the to-square; see ranking.md 3.2). Any enemy attack, the peers' set: lost in the declared measurement, not SPRTed; cheaper-attacker set: −6.08 ± 3.59 (H0). T56 closed for this network |
| D6 | Threat-aware capture history | Raphael +3.3 / +4.15; Ethereal +2.3 / +1.4; Motor +2.0; Renegade | new | **never tried** (UNVERIFIED whether T56's set also touched the take history) |
| D7 ⚑ | Pawn-structure history | Reckless +4.4 / +2.1; Raphael +2.7 LTC; Igel +2.5 / +3.0; Tarnished +2.2; Devre +1.8; PZChessBot −0.5 / +3.9; Astra | KB T12, R21 | **queued**: structure history at weight 5, kept in the 2026-11-10 trim |
| D8 ⚑ | Summed continuation score as each continuation table's update base | Hobbes +10.6; Tcheran +9.1; Tarnished +2.2 / +2.5; Integral +2.4 / +1.5; Quanticade +1.6 | new | **never tried** |
| D9 ⚑ | Bonus to the prior move when the child fails low (prior-countermove) | Hobbes +8.65; Halogen +6.4 / +2.65; Integral +2.0 LTC; Stockfish +1.1 / +1.4, +1.4 / +1.3 (S1) | S1 item 8; R15 optional extra | **never tried** |
| D10 | History bonus on a TT cutoff | JustBot +1.6; Viridithas (S2) | S2 4.3, R15 | **queued**: R15 |
| D11 ⚑ | Bonus shape and caps (linear or quadratic, hard and soft caps) | Tarnished +11.0; Raphael soft cap +6.6; Cinder +5.6; Halogen +3.45; Hobbes +3.1; Ethereal +2.2 / +1.4 | S2 4.3, R15 | **queued**: R15's linear bonus |
| D12 | Malus decayed by the number of moves searched | Berserk +2.0 LTC; Integral +2.0 LTC | new | **never tried** (the malus scale became a final-retune SPSA dimension, a different form) |
| D13 | Direct-check ordering bonus | pawnocchio +6.4; Raphael +6.3 / +2.8; Integral +4.1 | new | **never tried** |
| D14 | Factorised or dual-indexed quiet history | Hobbes +17.2, +7.8 | new | **never tried** |
| D15 | Low-ply history; no history updates from shallow cutoffs | Lizard +2.7, +7.0; Stockfish (S1) | S1 item 9 | **never tried** |
| D16 | No killers or countermoves | removals at non-regression: PZChessBot, Minke, Raphael, Quanticade, Renegade | S1 7.3 | **have**: Fork has neither |
| D17 | History ageing between searches | Stormphrax (S2 supplement) | R16 | **queued**: R16 |

## E. Correction history

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| E1 ⚑ | Pawn correction table | Tcheran +21.8; Devre +20.5 (first table); Tarnished +20.0; Hobbes +12.6; Raphael +11.3; Motor +6; Titan +4.1; Berserk depth-weighted +3.2 LTC | S2 4.4 | **tried, failed**: the drift table −0.35 ± 3.72 at LTC, undecided at the 9,984-game cap; not adopted |
| E2 ⚑ | Non-pawn correction tables | Tarnished +27.0; Tcheran +12.7; Devre +11.9; Hobbes +10.6; Raphael +6.6; Berserk +3.6 LTC; Quanticade +3.25; Lizard +2.6 | S1 7.1.e, S2 4.4, R34 | **queued**: R34, a **gateway item** (its table unblocks C15 and E5; (owner, 2026-11-10)), passive ranking then the best key at LTC (step 16) |
| E3 ⚑ | Continuation correction tables | Hobbes +11.6, +10.6; Tcheran +8.2; Raphael +7.1, +1.85; Berserk +5.5 LTC; Devre +5.3; Cinder +3.0, +4.7, +2.2; Alexandria 4-ply +2.7; Stockfish 6-ply +1.4 / +1.1; PlentyChess +0.9 | S1 7.1.e, R34 | **queued**: R34 |
| E4 ⚑ | Minor, major, material or threat correction tables | Tarnished minor +16.9, major +4.3; Tcheran major and minor +18.9, threat +9.3; Raphael major +6.8; PZChessBot material +5.2, threat +5.1; Devre material +4.1; Motor | S1 7.3 | **excluded**: dropped by the owner (think-tank decision 20) |
| E5 ⚑ | Correction update rules: gravity, divide after summing, update on a losing-capture best move, update toward a draw on an upcoming repetition | Integral +6.3, +3.4 LTC; Hobbes +3.9, +4.9, +4.0, +4.6 LTC; Berserk +3.4 LTC; Tcheran +3.3; Viridithas +2.3 LTC; pawnocchio +2.2 LTC | new | **never tried**: depends on R34 producing a table |

## F. Transposition table, draws and evaluation scaling

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| F1 ⚑ | Clustered TT and prefetch | Raphael clusters +29.7 at 1 MB / +23.1; Tarnished prefetch +14.3, clusters +6.75; Hobbes prefetch +9.1; Halogen +6.4; Ethereal +5.4 | KB | **have**: five entries per cache-line bucket, prefetch on make (Phase 3; TT +173.76) |
| F2 | Static eval stored in the TT entry and reused | Igel +8.0; Tarnished +4.8 | KB | **have**: review 2 claim (b) |
| F3 ⚑ | Early eval-only TT write (before the node's search finishes) | Integral +14.2; Lizard +14.7; Hobbes +12.2; Raphael +8.4 / +5.3; Quanticade +8.0; Ethereal +2.6 (8T +9.9 / +6.1) | new | **never tried**. Fork writes the eval only with a finished result; an empty slot is marked by bound None, so an eval-only entry needs a new state |
| F4 ⚑ | TT cutoffs gated by node type or by agreement of score and node type | Raphael +8.5; Hobbes +5.1 / +3.0; Halogen +2.3; Ethereal +2.45 LTC (STC failed); Integral +1.7 LTC; Triumviratus TT damping (Coda's idea) +2.2 | new | **never tried**. Fork cuts at any non-PV node when the entry is deep enough and its bound settles |
| F5 | TT replacement favouring recent or current-search entries | Integral +7.1 LTC, +14.0; Berserk +5.8 LTC | KB | **have**: current-search-first policy; the age blend was inconclusive (+5.7 ± 13.8) |
| F6 | Keep the TT move when the new result has none | Hobbes +20.9; Ethereal (not on an upper bound) +4.5 / +3.5 | new | **have** (partial): an existing move is kept when the new store has none |
| F7 ⚑ | Upcoming-repetition (cuckoo) detection | Lizard +12.3; Integral +7.3; pawnocchio +4.6 / +3.8; Hobbes +3.25; Tcheran +3.1; Raphael +2.9; Astra, Minke, Coda | S2 supplement, R12 | **queued**: R12 (idea 31 first) |
| F8 ⚑ | Fifty-move eval scaling | Tcheran +9.6 on a fortress book; PZChessBot +9.4 / +6.5 on endgame books, about 0 on the normal book; Hobbes +1.9; Lizard +1.7; Renegade | KB T52 | **tried, failed**: measurement, every span lost to "off"; no retest (owner, 2026-11-06) |
| F9 | Fifty-move buckets in the hash key, or halfmove-clock net inputs | Integral inputs +3.7 LTC, +3.7 on a fortress book; Hobbes hash buckets +2.3 on a fortress book, neutral on a normal book | S2 N7 | **never tried** |
| F10 ⚑ | Material-based eval scaling | Stormphrax +10.5 (S2); Motor +6.75; Hobbes +6.5; Tarnished +5.4; Raphael +2.9 LTC (failed STC); Alexandria | S2 supplement item 11 | **never tried**; nearest queued item: R33's structure-class scale (step 17) |
| F11 | Optimism (scale a consistently good score up) | Raphael +5.9 LTC; pawnocchio +5.2 STC; PlentyChess +1.3 LTC (STC H0); Stockfish (simplified) | S2 supplement | **never tried** |
| F12 | Pin-aware SEE | Tcheran +7.6; Triumviratus +4.5; ZigQueen, Renegade (b) | new | **never tried** (UNVERIFIED: Fork's SEE code not read here) |
| F13 | Huge pages for the TT and net | Viridithas +3.15 | R19 | **queued**: R19 |
| F14 | Syzygy probing in search | universal | KB | **have**: +17.5 ± 7.2 |

## G. Threads (Phase 6)

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| G1 | Lazy SMP | universal (Titan 2T +91; Horsie 2T +81) | S3 §2.A | **queued**: Phase 6 |
| G2 ⚑ | Correction and pawn histories shared across threads | pawnocchio corrhist +9.7 at 8T, pawn history +4.9 at 4T and +7.5 at 32T; Integral +6.9 at 4T; JustBot +6.4 at 8T; Raphael +5.1 at 8T; Berserk +4.2 at 8T; PZChessBot +8.5, later removed (neutral) | S2 4 item 10 | **queued**: Phase 6 (ideas.md 17) |
| G3 ⚑ | Thread voting | JustBot +12.1 at 8T; Raphael +9.8; Halogen +8.4; Hobbes +5.0; Ethereal +4.9 / +3.7 | S3 §6 | **queued**: Phase 6 (S3's plan) |
| G4 ⚑ | SPSA under SMP conditions | Reckless +10.0 at 8T (−6.5 at 1T); Raphael +7.6 at 8T; Integral +5.6, Hobbes +4.5, pawnocchio +4.6 at 4T; Halogen −7.3 and −4.2 at 1T | S2 4.1 caution | **never tried** (Phase 6 scope) |
| G5 | NUMA placement | Integral about +25 on a many-core box; Gaia +16 to +92% nps | S3 §2.D | **queued**: Phase 6 |

## H. Network architecture

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| H1 | Horizontal mirroring | Tarnished +28.2 LTC; Raphael +16.5; Tcheran +7.5; Minke | KB | **have**: S-512 family |
| H2 | Material or phase output buckets | Raphael +12.7; Tcheran +9.9 | KB | **have**: 8 outputs picked by phase |
| H3 ⚑ | King input buckets (with a factoriser, grown with data) | Raphael +25 to +33 per step early, then +8 to +10; Tarnished +8.8, +26.7, +15.8 LTC; Lizard +14.9 (+82 in DFRC with a factoriser); Titan +14.7 LTC; Motor +11; Alexandria doubled buckets +10.6 LTC; Tcheran +19.0 (with data), +2.95; Hobbes +2 to +7 per step; Minke, JustBot, PZChessBot | S2 N3 | **tried, failed**: H-512 (4 king regions and a factoriser) FN +32.23 but STC −24.36 (round 1); FN −12.17 (round 2). **Bake-off round 3 candidate** (owner, 2026-11-10): Fork's data has roughly tripled since H-512 |
| H4 ⚑ | Multi-layer head after the accumulator | Integral +29.5 LTC; Obsidian 15 +27 LTC; Tarnished +20.7 LTC; Hobbes +20.3 LTC; Minke +17.9 LTC; PZChessBot +16.0 LTC; Tcheran +16.5; Horsie +13.7 LTC; Raphael +6.6 LTC (float first −4.6 STC); Quanticade +6.2 LTC (lost STC); pawnocchio +10 STC | S2 N8 | **tried, failed**: AF-S FN +41.67 / +10.43, STC −48.52 / −55.85 (speed, 32 cp quantization loss) |
| H5 ⚑ | Dual activation in the head | Hobbes +16.5 LTC; Tcheran +7.2; Minke +6.0 LTC; pawnocchio +6.3 LTC; Tarnished +3.5 LTC; Raphael no gain | new | **never tried**: needs a multi-layer head (H4) |
| H6 ⚑ | Pawn-pair inputs | Devre +24.1 LTC; ZigQueen +15 to +23; Alexandria TI→TI+PP +13.5 LTC; Integral +7.2 LTC; Berserk +1.9 LTC; pawnocchio (origin, bundle +30.3 LTC); Hobbes, Triumviratus, Gaia, Cinder, Coda | S2 | **have**: Fork's own 608 pawn links, FN +46.09 ± 10.37, STC +32.67 ± 10.48 |
| H7 ⚑ | Threat inputs | Devre +30.6 LTC; Integral +24.4 LTC; Hobbes +23.7 LTC; PZChessBot +14.9 LTC at about 30% slower; Alexandria +13.4 LTC; Halogen +10.4 LTC; Quanticade +7.7 LTC; Raphael +6.7 at about 36% slower; Stockfish, Triumviratus, Coda, Gaia, Cinder, Berserk, ZigQueen, Igel | S1 7.1.k, S2 5.3 | **tried, failed**: XGR-512 FN +30.70, STC −34.42, LTC −30.56; S512+X FN +25.67, STC −30.04 at 0.818 nps; S512cl parked |
| H8 | Passed-pawn input block | Triumviratus +7.0 (net alone) | new | **queued**: a candidate family in R36's screen (M3a) |
| H9 | Material- or queen-routed input buckets ("experts") | Triumviratus +10.3 (net alone); Stockfish K32Q2 bundle +4.2 / +3.6; Starzix enemy-queen buckets (title) | new | **never tried** |
| H10 | Separate endgame net | PZChessBot about +20 (early) | S1 7.3 | **never tried**; S1 advises not to build it |
| H11 | DFRC data or a separate FRC net | Hobbes +6.2 standard STC from DFRC data; Ethereal FRC net | new | **excluded**: no Chess960 support (decision 2026-10-23) |

## I. Inference speed

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| I1 | Lazy accumulator updates | Lizard +27.5; Hobbes +18.3; Tarnished +14.7; Halogen "even lazier" threat deltas | S2 5.3 | **have** for the single-layer net (UNVERIFIED: Fork's update timing was not read in this survey) |
| I2 ⚑ | Refresh cache ("Finny tables") | Igel +13.8; Ethereal +8.6; Raphael +6.1; Tarnished +5.8 | S2 5.3 | **tried, failed**: a refresh cache for mirror-frame changes, −5.3% nps (speed round 2) |
| I3 ⚑ | Sparse first-dense-layer inference with neuron permutation | Tcheran +12.1; pawnocchio +10.2 VSTC; Hobbes; Integral; Raphael about 12% faster | S2 N8 | **never tried**: needs a multi-layer head |
| I4 | 8-bit feature-transformer rows, widened when accumulated | Stockfish (int8 everywhere; pairing +5 to +11% nps); Velvet 8.1; ZigQueen; Gaia T7; Triumviratus 8.1; Berserk pairing about +2% nps | S1 7.1.k | **never tried** (QAT built behind `--qat`, idea 44) |
| I5 | PGO and compiler choice | Lizard clang with LTO and PGO +11.4; Cinder dropped PGO; Clover "worthless" | S3 | **have**: PGO for data generation; the TCEC build plan (R11) |
| I6 | Quantisation-scale tricks | Horsie +7.7; Raphael +2.6; Quanticade +1.7, +4.6 | R25 | **queued**: R25, adaptive rounding of the output layer |

## J. Training recipe

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| J1 | Warm-start retrain from the previous net | Fork's own finding; common practice | — | **have**: the standard recipe (warm beat scratch by 0.00042 validation loss) |
| J2 | Average the weights of the last checkpoints | Triumviratus final net; Stockfish SWA experiments (open) | S1 7.2.2 | **have**: R1-avg, S512ppr3 +7.12 ± 4.53 STC |
| J3 ⚑ | Pure-result or result-heavy final fine-tune | Ethereal **+42.7 / +35.6**; Raphael +18.3, +3.5, +3.5; Berserk +11.7 LTC; Hobbes +5.4 LTC, newest data +8.9 LTC; Minke +8.1 LTC, +3.6 LTC; Halogen +6.9 LTC (0 STC); Tcheran +5.0; pawnocchio +4.2 LTC (STC H0); Tarnished +3.9; Seer 2.8 (b). Against: Viridithas −57 on recent data only; Hobbes's newest recipe ends at a low result weight (b) | S2 N2, R39 | **in progress**: idea 70, prepared and approved (owner, 2026-11-10), from td90; R39's high-WDL branch was not run in 8a |
| J4 | Result-weight ramp in the main stage | Halogen linear ramp +5.4 LTC (b); Raphael, Minke; against: Raphael −8.5, Tcheran −7.0 | S1 7.2.3, R27 | **queued**: R27's result-weight arm (Fork trains at a constant 0.5) |
| J5 | Feature-transformer weight decay | Stockfish +4.0 / +5.3 | new | **queued**: idea 71 (8c arm) |
| J6 | Activation or feature-transformer-output regularisation (L1 or sparsity loss) | Integral +5.2 LTC; Minke +5.0 / +3.7; Tcheran +16.0 (with 1 B more data); Coda (0.9.4), Cinder #1119, Raphael (light, with its sparse layer), Stormphrax (S2) | S2 | **never tried** |
| J7 | Ranger optimiser | Tcheran +3.5; Integral +3.2 STC; Halogen beta change (b) +5.4 LTC | S2 | **never tried** |
| J8 | Longer or deeper low-LR final stage | Raphael linear LR +4.8; Ethereal +2.6 / +2.2; Stockfish +0.6 / +1.8 | S1, R2 | **tried, failed**: 8a's cooldown branch and anneal-only arm did not beat R1-avg |
| J9 | Fine-tune on the newest data only | pawnocchio +3.4 / +13.6 (4T LTC +19.3); Hobbes +6.65, +8.9 LTC (with a high result weight); against: Viridithas −57, −9.7 | S2 6 | **never tried** |
| J10 | Purge or down-weight old data | Minke +11.8, +3.8 LTC; Viridithas (S2); Raphael, Lizard, RubiChess, Caissa (b) | S2 N1, R3 | **queued**: R3's half-weight arm, run in neither 8a nor 8b (8b had no old-data down-weighting arm (owner, 2026-11-10)) |
| J11 | Relabel with a larger own teacher | Devre transformer teacher +21.7; pawnocchio +4.7, +11.0, +4.0 LTC; Tarnished +3 to +4 LTC; PlentyChess "self-distillation" (b); against: Viridithas static-output relabels −3 | S2 N10 | **never tried**: idea 58 (plan only); the ensemble teacher (idea 63) killed at step 0 |
| J12 | Relabel old data by search with each new net | Viridithas, RubiChess, rofChade, Igel, Revenge | S2 | **have**: decision A+ (rescoring with newer Fork nets) and the labeller policy |
| J13 | SPSA of the net's last layer, or of the net in games | Berserk +17.2 LTC; Caissa 2.0 (b); Stockfish (no figure); RubiChess last-layer rescale +2 to +6 | S2 N4 | **never tried** |
| J14 | Quantisation-aware training | Motor +8, +12; ZigQueen; Caissa; Stockfish QAT warm-ups | idea 44 | **in progress**: built behind `--qat`, not yet run (validation session retired) |
| J15 | Piece-count or class filtering and balancing | Halogen +13.2 LTC; Minke +10.8 LTC; Rebel W/D/L balance about +10; Alexandria 9.0; Stockfish; against: Raphael −2.7 LTC | new | **in progress**: idea 69's "cw" arm in retrain 8b |
| J16 | Filters for disagreement between result and eval, or between result and tablebase | Halogen +4.0 LTC; Minke +2.3 | new | **never tried** |
| J17 | Random position skipping | Hobbes +8.9; Minke +5.3 FN; Raphael +2.4; Gaia | new | **have** in a different form: the split search saves a random share of positions (idea 13; UNVERIFIED that the effect is equivalent) |
| J18 | Loss shape (power above 2, pessimistic skew) | Motor +24 (early); Halogen +3.2 LTC; Starzix, Cinder (no figure) | M5 | **never tried** (cross-entropy judged not for Phase 4) |
| J19 | WDL or draw head; auxiliary heads | Lc0 (WDL since 2019), Seer, Stoofvlees | ideas 65, 67 | **queued**: plan only, after the conversion-and-defense results |
| J20 | Value targets from the game's later search values (TD-style) | Lc0 (search-value and result blend); Seer 2.3 blend "far superior" | idea 51, R37 | **have**: td90 is TD(0.9) labels, retrain 8b's arm (idea 51); STC +12.17 ± 5.71 against S512ppr3 (r8b-stc-1, 4,800 games), the default net since 2026-11-10 |

## K. Data generation and labels

| # | Technique | Engines and reported gains | Prior | Fork's status |
|---|---|---|---|---|
| K1 | Own self-play, iterated from a bootstrap or from zero | 24 of the 50 (provenance.md) | S2 | **have**: decision A+, chained to the bootstrap eval |
| K2 ⚑ | Label budget raised in steps or mixed budgets | Ethereal +6 to +19 per step; Tcheran add-on +19.2; Raphael +7.8; Minke +8.0; Hobbes −0.9 STC / +2.6 LTC; Tarnished mixed fine-tune +6.5 to +6.9 LTC; Clover, Renegade | S2 | **in progress**: idea 62's label-depth arms |
| K3 | Tablebase guidance, adjudication and rescoring | Lc0 rescoring; Integral Syzygy-guided; ZigQueen rescoring at 5 pieces or fewer; Seer retrograde start | KB | **have**: Syzygy WDL labels and adjudication at 5 pieces or fewer; ChessTB slice v2 queued (idea 68) |
| K4 | Endgame slices or endgame-start self-play | Caissa +51 on an endgame book (S2) | S2 N6, R32 | **have**: the Syzygy endgame slice (8 of 900 misjudged); R32 queued |
| K5 | Start-position distribution | PlentyChess +13.2 (S2); random opening plies (PZChessBot, Tarnished, Motor) | S2 N5, R1 | **queued**: R1, the 2026-09 book |
| K6 | Clear TT and history between data-generation games | Raphael +5.8 | new | **have**: `SelfPlayGame::play` clears both per game |
| K7 | Blend of adjudicated and unadjudicated games | Halogen (the blend won) | new | **never tried** |
| K8 | Games against other engines (adversarial data) | Ethereal +2.4 to +5.6 per round, +3.9 / +5.3 with result labels; Torch (second-hand); Dragon, Uralochka | new | **excluded**: not Fork-pure data (training-data decision 1, owner 2026-11-10) |
| K9 | Lc0 data or Lc0 relabelling | ten engines (provenance.md) | KB | **excluded**: decision A+ (no Lc0 data) |

## L. Testing practice

| # | Technique | Engines | Prior | Fork's status |
|---|---|---|---|---|
| L1 | Fixed-node screen before a timed SPRT | Hobbes, Minke, PZChessBot, Tcheran (FN columns in their logs) | S1 7.2.2 | **have**: retrain candidates gated by the FN screen (2026-11-07) |
| L2 | Wider nets lose at STC but win at LTC until data grows | PZChessBot, JustBot, Minke, pawnocchio, Ethereal, Hobbes | S2 | **have** as a known pattern (bake-off rules) |
| L3 | A long-TC check for scaling-sensitive changes | Stockfish "scaler suspect"; Halogen WDL weight passing only at VLTC; Clover VLTC tune | S1 7.2.6, S3 §2.B | **queued**: R24's VLTC spot check |
| L4 | Non-regression against a feature-disabled control | Stockfish's mate-seeking patches | S1 | **have**: the removal round (R30) uses this form |

## Counts

Each row counts once, by its status in the last column. **K8 and K9 are
excluded** and counted under "excluded", with A7 and H11. "Have (partial)"
or "have in a different form" counts as have. A "queued indirectly" row
counts as queued.

| Status | Rows | Count |
|---|---|---|
| have | A1, A2, B1, B2, B18, C1, C2, C7, C14, D1, D2, D4, D16, F1, F2, F5, F6, F14, H1, H2, H6, I1, I5, J1, J2, J12, J17, K1, K3, K4, K6, L1, L2, L4, J20 | 35 |
| tried, failed | B8, B15, B17, C3, C10, D5, E1, F8, H3, H4, H7, I2, J8 | 13 |
| in progress or queued | B3, B4, B5, B9, B14, C4, C5, C8, C9, C11, C12, C13, C18, D7, D10, D11, D17, E2, E3, F7, F13, G1, G2, G3, G5, H8, I6, J3, J4, J5, J10, J14, J15, J19, K2, K5, L3 | 37 |
| parked | A3 | 1 |
| never tried | A4, A5, A6, B6, B7, B10, B11, B12, B13, B16, B19, C6, C15, C16, C17, D3, D6, D8, D9, D12, D13, D14, D15, E5, F3, F4, F9, F10, F11, F12, G4, H5, H9, H10, I3, I4, J6, J7, J9, J11, J13, J16, J18, K7 | 44 |
| excluded | A7, E4, H11, K8, K9 | 5 |
| **total** | | **135** |
