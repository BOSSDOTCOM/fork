# Common techniques missing from the 2026-11-10 comparison table

Part of the rare-ideas survey of 2026-11-15 (README.md). These are used by **four or more** of the engines read, so
they are not rare, but none has a row in docs/research/engine-survey-2026-11/comparison.md (A1-L4). They matter
because Fork lacks most of them. Every idea is **REFERENCE ONLY**; every Elo figure is the engine's own report
(TCs as in rare.md: mostly 8+0.08 / 40+0.4 for OpenBench engines, 10+0.1 / 60+0.6 for fishtest and Ethereal).
Engine lists combine the four groups; counts are of engines read in this survey, not a census of the top 50.
Scores use ranking.md's scale (E x F / C).

## Summary

| Id | Technique | Engines | Best evidence | Fork | E | F | C | Score |
|---|---|---|---|---|---|---|---|---|
| CG-1 | Eval-difference history update | Stockfish, Reckless, PlentyChess, Obsidian, Tarnished, Viridithas, Integral, JustBot; titles or UNVERIFIED: Clover, Igel | Viridithas +11.57 / +2.89; JustBot LTC +8.44 | never tried | 5 | 4 | 1 | 20 |
| CG-2 | Threat-gated or threat-raised RFP | Integral, Viridithas, Caissa, Halogen | Halogen +3.72; Integral +2.80; Viridithas +2.16 (STC) | never tried | 3 | 5 | 1 | 15 |
| CG-3 | LMR extensions | Hobbes, Integral, Viridithas, Stormphrax, Halogen, Quanticade, PZChessBot | Hobbes +2.26 / +2.82; Halogen +3.93 / +2.20 | never tried (reduced depth clamped) | 4 | 3 | 1 | 12 |
| CG-4 | NMP adjusted when the TT move is a capture | Viridithas, Hobbes, Clover, Starzix | Viridithas LTC +1.88; Hobbes +3.23 STC | never tried | 4 | 3 | 1 | 12 |
| CG-5 | No pruning inside the singular test's search | PZChessBot, JustBot, Quanticade, Minke | PZChessBot +12.98 STC, LTC non-reg | **have** at node level; move loop UNVERIFIED | 3 | 3 | 1 | 9 |
| CG-6 | Aspiration fail-high depth reduction | Lizard, Hobbes, Stormphrax, Raphael, Stockfish | Lizard +11.60 STC; Stockfish +1.04 / +1.18 | **tried**: audit-1 B-3, inconclusive, reverted | 4 | 2 | 1 | 8 |
| CG-7 | Capture-history-scaled SEE threshold for good and bad captures | Tcheran, Halogen, Minke, Quanticade | Tcheran +13.97; Minke +9.98; Halogen +4.82 (STC) | never tried (plain SEE sign) | 3 | 4 | 2 | 6 |
| CG-8 | Aspiration window sized by score volatility or stability | Reckless, PlentyChess, Obsidian, Stockfish | Reckless +4.58 / +2.08 | never tried (fixed half-width; R22 re-measure planned) | 4 | 3 | 2 | 6 |
| CG-9 | Draw-score randomisation | Ethereal, Berserk, Alexandria, pawnocchio, Reckless, Quanticade, Halogen, Velvet | Ethereal LTC +3.63 (STC not passed) | never tried | 3 | 4 | 2 | 6 |
| CG-10 | Evaluation grain (rounding the eval) | PlentyChess, Alexandria, Reckless, older Stockfish | Reckless +1.85 | never tried | 2 | 2 | 1 | 4 |
| CG-11 | TT-score-refined eval for pruning | Raphael, Tarnished, Viridithas, Tcheran, Titan, PZChessBot, Halogen, Velvet | Titan +10.15 LTC; PZChessBot +10.14 | **have** (`use_tt_eval_refine`) | | | | closed |

The table is ordered by score, ties by evidence. The ids are this file's own (CG = common gap). CG-2 outranks
CG-3 and CG-4 on fit (Fork's net has no threat inputs) although its evidence is STC-only; CG-6 is a gap only in
the peers' form, since Fork tried a single-ply version.

---

### CG-1. Eval-difference history update
- **What:** a quiet move's history moves with the change in static evaluation it caused (the eval after the move
  against the eval before it, sign-adjusted), clamped; the prior move is credited or penalised by what it did to the
  position.
- **Engines:** Stockfish; Reckless (introduced 2025-04; refined 2026-05 to skip repeat high-depth visits, +2.34 /
  +2.35); PlentyChess; Obsidian (+2.96, +4.17 at 10+0.1); Tarnished (engines.md); Viridithas (#229, +11.57 ± 4.75 STC
  and +2.89 ± 2.05 LTC, [0, 3]); Integral (#155, a pawn-history form, +2.39 ± 1.83 STC; #65 +1.46 ± 1.78 unfinished);
  JustBot (#196, +8.44 ± 3.85 at 40+0.4, [0, 3], 7,326 games, 2026-11-06, after its rated 0.5.0). Titles only:
  Clover #333 and #382. Igel's "static history" (#368, +11.16 ± 3.76 STC, +7.89 ± 3.08 LTC, [0, 2], after 3.8.0) may
  be the same idea (title and branch name only: UNVERIFIED). Stockfish's use was not re-read by group 2 or 3
  (group 1 lists it).
- **Prior coverage:** the think tank's B list had it (OS 4.3 item 3), but R15 kept only the linear and TT-cutoff
  bonus items, and comparison.md has no row. Groups 1, 2 and 3 found it independently, and all three call it the
  biggest common gap.
- **Fork:** never tried (no ideas.md entry). D9 (prior-move credit, a different update) went H0 and was rejected.
- **Fit:** ordering only, no nps cost; Fork's drift tables already compute the corrected static eval it would use.
- **Cheapest test:** one design R STC SPRT of a clamped bonus or malus on the prior quiet move from the change in
  static eval, at natural values. *Decision:* adopt or not. *Cost:* one SPRT.

### CG-2. Threat-gated or threat-raised reverse futility pruning
- **What:** RFP is skipped, or its margin raised, when the side to move has pieces under threat (the opponent has a
  capture that wins material); a static eval that ignores a hanging piece overstates the position, so those are the
  cuts most likely to be wrong.
- **Engines:** Integral (#123, +2.80 ± 2.06 at 8+0.08, [0, 3], 2024-11); Viridithas (#307, +2.16 ± 1.67 at 8+0.08,
  [0, 3], 2025-08; which side's capture it tests is UNVERIFIED); Caissa (1.17 release notes, bundled); Halogen (#696,
  threat-raised margin, +3.72 ± 2.44 at 8+0.08, [0, 3], 21,218 games; engines.md named it). No LTC figure in any.
  Group 2 counted the first three (rare, its top gem); with group 3's Halogen it counts four.
- **Related rare entries:** RI-21 (a quiescence check before an RFP cutoff, Hobbes, STC and LTC passes) and RI-22
  (improving in RFP only under a high-value threat, PlentyChess).
- **Fork:** never tried; Fork's RFP has no threat term; not B10 (opponent worsening), B7 (TT-bound gates) or B8
  (improving, failed).
- **Fit:** strong. Fork's net has no threat inputs (XGR-512 and S512+X lost on speed; x_lower is only a compact
  plane), which is the situation Integral and Viridithas were in when they gained (their threat nets came later).
  The attack sets exist (T56 any-attack ordering, adopted; the threat drift key). No accumulator rows change.
- **Cheapest test:** one ledger study with RI-21: run the X10 decision ledger (stats builds, RFP ledger lines) over
  the bench and evolve positions; split RFP candidates by "the side not to move has a capture with positive SEE";
  compare how often the RFP-off side search ends below beta in each class; stop if the hanging class's error rate is
  under 1.5 times the other's or the class is under 2% of candidates (group 2's estimates, UNVERIFIED); else one
  design R STC SPRT of the skip form (no constant) against off. *Decision:* whether RFP gets a threat guard.
  *Cost:* about 1-2 CPU-h, then one SPRT.

### CG-3. LMR extensions
- **What:** a reduced search may go deeper than the normal depth (by one ply, at PV or expected cut nodes) when the
  reduction formula comes out negative.
- **Engines:** Hobbes (#324, +2.26 ± 1.82 STC, +2.82 ± 2.18 LTC, [0, 4]); Integral (#134, +4.35 ± 2.67 STC);
  Viridithas (#382, +1.97 ± 1.54 LTC, bundled); Stormphrax (#258, #268); Halogen (#838, +3.93 ± 2.57 STC, +2.20 ±
  1.68 LTC, [0, 3], at PV nodes); Quanticade (#244 PV +1.73, #253 cut node +1.89); PZChessBot (#239, +3.57 STC).
- **Fork:** never tried. Fork clamps the reduced depth to at most the normal depth (DESIGN.md `LmrMinDepth`;
  searcher.cpp).
- **Fit:** neutral to good; no nps cost; evidence at STC and LTC in two engines.
- **Cheapest test:** one design R STC SPRT of a one-ply cap on the extension. *Decision:* adopt or not. *Cost:* one
  SPRT.

### CG-4. Null-move pruning adjusted when the TT move is a capture
- **What:** no null move (or more reduction for it) when the TT move is a capture.
- **Engines:** Viridithas (#412, NMP skipped, +1.88 ± 1.48 LTC); Hobbes (#94, +3.23 ± 2.92 STC); Clover (#307) and
  Starzix (#121) by title.
- **Related rare entry:** RI-24 (Potential, NMP skipped when the TT move is a valuable piece's).
- **Fork:** never tried; Fork's NMP has no TT-move term.
- **Cheapest test:** one design R STC SPRT of the skip form. *Decision:* an NMP gate. *Cost:* one SPRT.

### CG-5. No pruning inside the singular test's search
- **Engines:** PZChessBot (#268, +12.98 STC, +3.55 LTC on non-regression bounds); JustBot (#164, razoring, +1.07);
  Quanticade (#112) and Minke (#184) for IIR.
- **Fork:** **have** at node level: node pruning and IIR are off in the singular search (`can_prune_node` excludes
  it). Whether move-loop pruning runs there is UNVERIFIED.
- **Cheapest test:** read the move loop; if pruning runs in the singular search, one non-regression SPRT of turning
  it off. *Decision:* close the question. *Cost:* a code read, maybe one SPRT.

### CG-6. Aspiration fail-high depth reduction
- **What:** after a root fail high, the re-search runs at a lower depth (some engines lower it per consecutive fail
  high and let it recover gradually).
- **Engines:** Lizard (#47, +11.60 ± 4.74 STC, +5.92 ± 3.55 at 20+0.2 unresolved); Hobbes (#213, +5.51 ± 3.64 STC,
  [0, 4]); Stormphrax (#155, +3.15 ± 2.54 at 13+0.13, [0, 5]); Raphael (#100, +1.58 ± 1.22 STC, [0, 4]); Stockfish
  (depth recovering gradually after a fail high, +1.04 / +1.18). Counter-evidence: Triumviratus -1.82 ± 4.54,
  removed.
- **Fork:** **tried.** Audit-1 B-3 (the root fail high re-searched one ply shallower) reached its cap undecided on
  [0, 3], +0.65 ± 3.56, and was reverted (DESIGN.md decisions log, 2026-10-28); ideas.md 29 says to run its
  measurement (how often unconfirmed root fail highs hold) before B-3 is revisited. Group 2 reported it as absent,
  reading only the aspiration loop; group 3 found the B-3 record (README.md, reconciliations).
- **Fit:** low-medium: Fork's own test was flat, but the peers' form (lower per consecutive fail high, gradual
  recovery) differs from B-3's single ply.
- **Cheapest test:** ideas.md 29's measurement first (CPU only); a retry of the peers' form only if it supports it.
  *Decision:* whether B-3 is revisited. *Cost:* CPU hours, then maybe one SPRT.

### CG-7. Capture-history-scaled SEE threshold for the good and bad capture split in move ordering
- **What:** whether a capture is ordered with the good captures or deferred with the bad ones is decided by SEE
  against a threshold that moves with the capture's history (or its ordering score), not by the SEE sign alone.
- **Engines:** Tcheran (3f00a00, +13.97 ± 6.76 at 8+0.08, [0, 5], 3,184 games; "from a discussion in the Stockfish
  Discord"); Halogen (#712, +4.82 ± 2.86, [0, 3], 15,206 games); Minke (#111, +9.98 ± 5.68, [0, 4], 4,144 games);
  Quanticade (#154, +1.09 ± 1.43, merged unresolved, LLR 0.84). All STC. Stockfish's use not re-read (UNVERIFIED).
- **Fork:** never tried. Fork defers captures that lose by SEE and orders the rest by victim and take history
  (move_selector.hpp, `use_take_history`). Distinct from B11 (history-scaled pruning margins).
- **Fit:** good; no nps cost; one scale constant (placeholder, then the screen). Group 3's gem.
- **Cheapest test:** one design R STC SPRT; LTC if it passes. *Decision:* the capture split rule. *Cost:* one SPRT
  plus the constant's screen.

### CG-8. Aspiration window sized by recent score volatility or stability
- **Engines:** Reckless (narrowed when the search has been stable, +4.58 / +2.08); PlentyChess (+2.32); Obsidian (a
  squared average of past scores, +1.24); Stockfish (averaged root scores).
- **Fork:** never tried; Fork uses a fixed half-width. The think tank's R22 plans a re-measure of the half-width
  "(and score-dependent)", which overlaps only in part (score size, not volatility).
- **Cheapest test:** fold into R22: add a volatility-sized arm to its measurement. *Decision:* the aspiration rule.
  *Cost:* within R22, plus one SPRT.

### CG-9. Draw-score randomisation
- **What:** a tiny varying draw score, so threads and iterations do not all settle on the same repetition line.
- **Engines:** Ethereal (37ccbfe: STC +1.28 ± 2.10 not passed, LLR -0.43; **LTC +3.63 ± 2.88 passed**, 60+0.6,
  [0, 5], 21,050 games; the commit says it helps "especially at longer TCs"); Quanticade (#53, +2.99 ± 2.94,
  non-regression bounds); Halogen (#730, -0.15 ± 1.61, neutral, merged); Velvet (no figure); Berserk, Alexandria,
  pawnocchio, Reckless (mostly non-regression).
- **Fork:** never tried (no ideas.md entry).
- **Fit:** LTC-only evidence suits TCEC; also a source of Lazy SMP thread diversity (RI-35).
- **Cheapest test:** an LTC SPRT on non-regression bounds, then again under SMP. *Decision:* adopt or not. *Cost:*
  one LTC SPRT (and the amplitude's screen).

### CG-10. Evaluation grain (rounding the eval)
- **Engines:** PlentyChess, Alexandria, Reckless (+1.85), older Stockfish.
- **Fork:** never tried. **Fit:** unclear (group 1). **Cheapest test:** none proposed.

### CG-11. TT-score-refined eval for pruning
- **Engines:** Raphael (#105 +3.23, #110 +3.84, #136 +4.70, STC), Tarnished (#92 +2.87), Viridithas (#385), Tcheran
  (+4.11), Titan (#165, +10.15 LTC), PZChessBot (#170, +10.14), Halogen (#509, +5.16 LTC), Velvet.
- **Fork:** **have** (`use_tt_eval_refine`; RFP's pruning eval is TT-refined). Listed only to close the question.
