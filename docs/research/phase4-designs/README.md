# Phase 4 design documents (owner's order, 2026-11-09)

The owner's order: "the Phase 4 design docs (idea 53 structure experts,
factorial removal round, structure-class calibration, final retune with
RfpMargin's lower bound widened to ~30), docs only." **Designs for review:
nothing here is adopted, queued or built**, no DESIGN.md or ideas.md text is
changed, and no name or constant here has been screened yet.

| document | order step | what it decides | GitHub cost (UNVERIFIED) |
|---|---|---|---|
| [idea53-structure-experts.md](idea53-structure-experts.md) | 14 (the network screen; R26's family) | per-pawn-class output heads on S512+PP: classes, head, trainer, probe, small-net test at equal data, screens | 2-3 stages plus a network SPRT of 1-13 stages; 4-6 Kaggle runs; 3-5 CPU-hours |
| [structure-class-calibration.md](structure-class-calibration.md) | 17 (R33) | a per-class scale on the eval, fitted on SPRT games, adopted on fresh games (decision 16) | about 4-8 STC stages plus an LTC test |
| [factorial-removal-round.md](factorial-removal-round.md) | 18 (R30, decision 6) | which of 8 low-prior switches are removed, by a k = 8, m = 3 factorial with B14's four fixes | 21-43 STC stages (about 6-13 h) |
| [final-retune.md](final-retune.md) | 19 (R24, decisions 4 and 21) | the STC and LTC SPSA passes by scaling class, the floor problem (RfpMargin and others), validation and the VLTC spot check | about 30-40 GitHub-hours |

**The owner's decisions of 2026-11-09 (about 8 PM EST)** are recorded in
each document and in DESIGN.md's decisions log: the final retune's eleven
range widenings applied (src/tune/params.hpp) and a pinned-at-bound flag in
`spsa.py report`; the factorial round removes at "estimate <= 0", its
tooling built when step 18 comes up; idea 53's 2e-5 probe line and the
calibration's 30% line are diagnostics only; the calibration's SPRTs are
design R; the VLTC check uses a non-regression rule (final-retune.md §5).
The recurring question below is settled by the third of these.

Each document lists its decisions for the owner, its names and constants for
the screens, and its unverified items. Two questions recur in more than one:
- **Offline stop-losses against the 2026-11-09 testing rule** (offline
  metrics are diagnostics, never a gate): idea 53's probe (2e-5) and R33's
  cross-validated residual cut (30%) are kill criteria recorded before that
  rule; both documents keep them as stop-losses before any GPU or GitHub
  spend and ask the owner to confirm.
- **The class function** is shared: idea 53 and R33 compute pawn-structure
  classes from the same primitives, implemented and tested once; R33 is
  refitted if idea 53 is adopted (the two fix different things: the training
  labels show little of the structure-class bias the games show).

New since the records these designs read: R14's tuned-values STC SPRT
(spsa-r14-m2-stc) passed, +37.93 ± 10.03 Elo after 1,600 games, at 7:27 PM EST
2026-11-09 (local driver log; not yet in the SPRT log), and LmpQuietAllowance
was pinned at its SPSA floor in R14 as RfpMargin was (final-retune.md §1).
