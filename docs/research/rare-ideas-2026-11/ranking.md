# Ranking of the rare techniques (evidence x fit / cost)

Part of the rare-ideas survey of 2026-11-15 (README.md). All 45 entries of rare.md, ranked. The score orders the
list; it does not predict Elo. Every figure behind it is the engine's own report (rare.md). The four groups each
scored their own candidates on similar scales; the scores below are re-done on one scale after the merges, so
they differ from the section files in places (README.md, reconciliations).

## Scoring

**Score = E x F / C**, ties broken by higher E, then higher F, then more engines.

| Axis | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| **E, evidence** | anecdote, bundled release, or no separable figure | one engine, one STC SPRT; or non-regression only | one engine with STC and LTC passes; or two engines at STC | two or more engines including an LTC pass; or one engine with several LTC passes | three engines including LTC passes |
| **F, fit** | conflicts with Fork's evidence or decisions | overlaps something Fork tried and lost, or has an nps cost that the cost lesson makes hard | neutral | zero nps cost and builds on an adopted Fork feature, or speaks to the king-region net, TCEC long TC or Lazy SMP | directly addresses one of Fork's open questions (Lazy SMP next, TCEC long TC or many threads, the cost lesson) at no single-thread cost |

| **C, cost** | 1 | 2 | 3 |
|---|---|---|---|
| | one switch with no new constant (or a natural value), one STC SPRT, or offline CPU minutes | a new constant (placeholder and screen), an LTC-first test, an nps A/B first, a multi-thread runner, or an arm in a run that happens anyway | a dedicated training arm, SPSA budget or tooling build |

Two discounts, stated so they can be undone: results from an engine far weaker than Fork, or measured in a
hand-crafted-eval era by such an engine (Potential), count one evidence level lower; an interval that includes
zero (fixed games, early stops) does not count as a pass.

**Gem** marks an entry whose evidence is stronger, or whose fit with Fork is closer, than its spread among engines
suggests. The groups proposed most of them; "(synthesis)" marks the one added here.

## Ranked list

| Rank | Id | Technique | Engines | Best evidence | Fork | E | F | C | Score | Gem |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | RI-12 | Root LMR keyed to the aspiration state | Ethereal | +2.98 at 12+0.12, +3.14 at 60+0.6, [0, 5] | never tried; plain root LMR adopted 2026-11-13 | 3 | 5 | 1 | 15 | **gem** |
| 2 | RI-34 | Lazy SMP hygiene (barrier, no stores from aborted helpers) | Tarnished, RubiChess | +14.48 at 2 threads, +20.08 at 4 threads (bundle, partly a bug fix) | n/a yet; already in the KB entry's suggested v1 | 3 | 5 | 1 | 15 | **gem** (already captured) |
| 3 | RI-27 | Depth-relaxed TT cutoffs | Ethereal, Halogen | Ethereal +4.34 at 10+0.1, +4.59 at 60+0.6, +3.43 at 8 threads | never tried | 4 | 3 | 1 | 12 | **gem** (synthesis) |
| 4 | RI-02 | History bonus scaled by moves searched before the cutoff | Stockfish, PlentyChess, Alexandria (borderline) | Stockfish +0.92 / +2.27; PlentyChess +2.12 STC | never tried | 4 | 3 | 1 | 12 | |
| 5 | RI-31 | Correction update toward the mean of raw and corrected eval | Motor, Renegade | Motor +7.91 ± 3.82 at 10+0.1 | never tried; drift table adopted | 3 | 4 | 1 | 12 | |
| 6 | RI-13 | Extra reduction for king-move evasions | Ethereal | +2.15 at 10+0.1, +6.53 at 60+0.6, [0, 5] | never tried | 3 | 4 | 1 | 12 | |
| 7 | RI-20 | Stay out of quiescence when the TT holds a move | Reckless, PlentyChess, Stockfish (borderline) | LTC passes in all three; PlentyChess STC H0, LTC +1.88 | never tried | 5 | 4 | 2 | 10 | **gem** |
| 8 | RI-35 | Thread diversity: per-thread offsets, helper reduction bias | Stockfish, Reckless, Potential (borderline) | Stockfish SMP STC and LTC passes; Reckless +3.19 at 8 threads | never tried; Phase 6 roadmap | 4 | 5 | 2 | 10 | **gem** |
| 9 | RI-41 | Elementary-mate regression suites | Stockfish | a documented TCEC failure and its fix | not run on TT or TB changes | 2 | 5 | 1 | 10 | **gem** (practice) |
| 10 | RI-05 | History bonus scaled by the margin over beta | Integral, Viridithas | +2.79 and +4.33 at 8+0.08 | never tried | 3 | 3 | 1 | 9 | |
| 11 | RI-06 | History bonus for the null move's refutation | Viridithas, Potential | Viridithas +2.32 STC; Potential +10.05 / +7.92 (weak engine) | never tried | 3 | 3 | 1 | 9 | |
| 12 | RI-32 | Correction keys by material band or halfmove clock | Reckless, Triumviratus | Reckless +1.27 / +2.30 | never tried | 3 | 3 | 1 | 9 | |
| 13 | RI-03 | Continuation update scaled by cross-ply consistency | Stockfish | +1.39 / +2.48 | never tried | 3 | 3 | 1 | 9 | |
| 14 | RI-29 | TT replacement penalising window-mismatched entries | Stockfish | +0.71 / +1.73; a VVLTC revert failed | never tried | 3 | 3 | 1 | 9 | |
| 15 | RI-01 | King-attack and threat knowledge in quiet ordering | Reckless, Coda, Triumviratus | Reckless seven SPRTs at STC and LTC | D13 and T56 any-attack adopted; king terms never tried | 4 | 4 | 2 | 8 | **gem** |
| 16 | RI-26 | No TT cutoff near the fifty-move horizon | Stockfish, Cinder, Stormphrax | Stockfish +1.27 / +1.04; Stormphrax LTC non-reg +3.79 | never tried | 4 | 4 | 2 | 8 | |
| 17 | RI-15 | Less LMR in loose alpha windows | Stockfish, Reckless | Reckless +2.19 / +4.27 | a relative retired (idea 61 part 5) | 4 | 2 | 1 | 8 | |
| 18 | RI-08 | Surprise-weighted history bonus | Tcheran, Stormphrax, Velvet | Tcheran +2.66 at 8+0.08 | never tried | 2 | 4 | 1 | 8 | |
| 19 | RI-28 | An exact result may replace a lower-bound entry | Halogen | +3.29 at 8+0.08 | never tried in this form | 2 | 4 | 1 | 8 | |
| 20 | RI-17 | Factorised LMR | Tarnished, Hobbes, Cinder (borderline) | Tarnished +4.03 / +6.35, [0, 5] | never tried | 5 | 3 | 2 | 7.5 | |
| 21 | RI-36 | Majority thread vote for the soft stop | Reckless | +4.48 at 8 threads, 25+0.25 | never tried | 3 | 5 | 2 | 7.5 | |
| 22 | RI-09 | Continuation history split by tactical state | Ethereal, JustBot | Ethereal +2.50 / +3.72; JustBot LTC +2.90 | never tried | 4 | 3 | 2 | 6 | |
| 23 | RI-21 | Quiescence check before an RFP cutoff | Hobbes | +4.55 / +2.19 | never tried | 3 | 4 | 2 | 6 | |
| 24 | RI-25 | Skip SEE when the destination is unattacked | Hobbes, pawnocchio | non-regression only (speed) | never tried | 2 | 3 | 1 | 6 | |
| 25 | RI-07 | Fixed positive intercept on the history bonus | Integral | +5.24 at 8+0.08 | never tried | 2 | 3 | 1 | 6 | |
| 26 | RI-16 | Causal reduction | Triumviratus | +4.27 ± 4.13, early stop | never tried | 2 | 3 | 1 | 6 | |
| 27 | RI-18 | Double extension with a single legal move | Renegade | +2.66 at 10+0.1 | never tried in the tree | 2 | 3 | 1 | 6 | |
| 28 | RI-22 | Improving in RFP only under a high-value threat | PlentyChess | +1.85 at 8+0.08 | plain form failed (B8); gated form untested | 2 | 3 | 1 | 6 | |
| 29 | RI-39 | Output-bucket factoriser in training | Incipit | H1 +9.4 at [0, 2]; the same data without it H0 | never tried | 2 | 5 | 2 | 5 | **gem** |
| 30 | RI-38 | Table sizes scaled with the thread count | Potential | +11.73 and +8.96 at 8 threads, 20+0.2 (weak engine) | never tried | 2 | 5 | 2 | 5 | |
| 31 | RI-42 | Elo by game length in release gauntlets | Velvet | a diagnostic (anecdote) | never tried | 1 | 5 | 1 | 5 | **gem** (tooling) |
| 32 | RI-14 | LMR by laterality and best-move chain length | Reckless | +6.13 / +2.21; +2.03 / +1.82 | never tried | 3 | 3 | 2 | 4.5 | |
| 33 | RI-33 | Correction keyed by the net's hidden state | Seer | +3.08 / +3.93 (mapping UNVERIFIED; after rated) | never tried | 2 | 4 | 2 | 4 | |
| 34 | RI-04 | King-square-relative quiet history | Cinder | +2.26 and +1.55 at 1+0.01 | never tried | 2 | 4 | 2 | 4 | |
| 35 | RI-44 | SPSA from a biased start | Coda | +12.3 at [0, 5] (TC UNVERIFIED) | never tried | 2 | 4 | 2 | 4 | |
| 36 | RI-10 | Pawn-structure refutation move | Renegade | +2.14, tuned +2.64 | never tried | 2 | 2 | 1 | 4 | |
| 37 | RI-23 | More LMP when the eval suggests a fail high | Integral | +3.13 STC; LTC unresolved | never tried | 2 | 2 | 1 | 4 | |
| 38 | RI-11 | Gain history | Incipit | +1.6 ± 1.2 STC | left out as not novel | 2 | 2 | 1 | 4 | |
| 39 | RI-30 | GHI mitigation for transpositions | Reckless, Alexandria | +9.74 on a fortress book; Alexandria H0 | never tried | 2 | 3 | 2 | 3 | |
| 40 | RI-19 | SE and double-extension margins by correction or history | Potential | LTC +9.13; +4.85 (weak engine) | never tried | 2 | 3 | 2 | 3 | |
| 41 | RI-24 | NMP skipped for a valuable piece's TT move | Potential | +12.42 / +10.14 (weak engine) | never tried | 2 | 3 | 2 | 3 | |
| 42 | RI-37 | SMP-only TT store of intermediate results | Reckless | 8 threads +3.99; 1 thread -3.61 | never tried | 2 | 3 | 2 | 3 | |
| 43 | RI-43 | Hardware-sensitivity checks | Triumviratus | anecdote | not done | 1 | 3 | 1 | 3 | |
| 44 | RI-45 | Bayesian optimisation of a constant group | Ethereal, Reckless | Ethereal +3.62 / +3.26 | never tried | 4 | 2 | 3 | 2.7 | |
| 45 | RI-40 | Label shrink toward a draw for drawish material | Velvet | bundled release estimate | never tried | 1 | 2 | 3 | 0.7 | |

## The gems, and why each is undervalued

- **RI-12, root LMR keyed to the aspiration state:** one engine, old and hand-crafted-era, so nobody copied it; for
  Fork it is a constant-free refinement of root LMR, which just gained +17.71 STC and +14.94 LTC.
- **RI-34, Lazy SMP hygiene:** treated everywhere as a bug fix, so never counted as a technique, yet Tarnished's
  bundle gained +14 to +20; free for Fork, and already in the KB entry's suggested v1.
- **RI-27, depth-relaxed TT cutoffs (synthesis):** developers distrust relaxing TT cutoffs, but Ethereal's
  constant-free form passed at STC, LTC and 8 threads, which is Fork's next condition.
- **RI-20, stay out of quiescence with a TT move:** invisible at STC (PlentyChess's H0) and passed at LTC in three
  engines, so STC-first pipelines, Fork's included, filter it out.
- **RI-35, thread diversity:** SMP tests are rare in most engines, so it is under-measured; Fork is about to build
  Lazy SMP for a many-thread tournament, at no single-thread cost.
- **RI-41, elementary-mate suites:** only an engine at TCEC scale meets the failure; Fork will be at TCEC scale,
  and the check costs CPU minutes.
- **RI-01, king-attack ordering knowledge:** its cost is nps, not Elo, and Reckless's seven STC and LTC passes show
  the Elo is there; Fork's net is built around king regions, and search-side king knowledge adds no rows.
- **RI-39, output-bucket factoriser:** short training runs hide it (+0.8 at a quarter length), and it costs nothing
  at inference: by Fork's cost lesson any fixed-node gain is net Elo.
- **RI-42, Elo by game length:** a diagnostic, not a technique, so no one reports it as a gain; Fork's PGNs exist
  and the conversion question (idea 172) is open.

## Gems that are common, so not ranked here

Two group gems are used by four or more engines, so they are in common.md: the **threat-gated RFP** (group 2's
gem at three engines; with group 3's Halogen it counts four: Integral, Viridithas, Caissa, Halogen; CG-2) and the
**capture-history-scaled SEE threshold** (group 3's gem, already four engines in its group; CG-7). Common.md scores
them on the same scale, with the **eval-difference history update** (CG-1), the top common gap.
