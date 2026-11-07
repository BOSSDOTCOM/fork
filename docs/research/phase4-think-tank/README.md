# Phase 4 think tank (2026-11-07)

A research exercise the owner commissioned: pure thinking and ideas for
the rest of Phase 4 (the network, training and data, search, speed,
tuning, testing methodology and idea 23), aimed at maximum strength at
long time controls (STC as the screen, LTC to confirm). **Nothing here has
been implemented.** Every proposal waits for the owner's review, and every
Elo figure is a model prediction or a placeholder unless it cites a logged
run.

## The standard

Every proposal states its mechanism, a quantitative model or derivation,
the theory or literature behind it (credited), a falsifiable prediction,
why it fits Fork specifically, its speed and compute cost, the cheapest
first experiment and a kill criterion. Novel ideas are labelled NOVEL and
held to the same standard.

## Files, in reading order

| File | What it is |
|---|---|
| [phase-c-synthesis.md](phase-c-synthesis.md) | **Start here.** The judge's ranked synthesis: executive summary, every surviving idea ranked by expected LTC Elo per unit of effort, enablers ranked by information per cost, novel ideas, the removal list, the recipe for the next retrain ("item 8"), a proposed order for the rest of Phase 4, the owner decisions needed, and the contradictions resolved. |
| [phase-a-evidence.md](phase-a-evidence.md) | Phase A: what Fork's own evidence shows. A verified synthesis (claims re-checked against the code, logs and Kaggle records; the quantitative models Fork can plan with; a ranked diagnosis of the bottlenecks), then the three analyst reports as appendices: A1 network, training and data; A2 search; A3 speed, systems and testing methodology. |
| [phase-b-specialists.md](phase-b-specialists.md) | Phase B: three clean-room engine surveys (the Stockfish lineage, open-source NNUE engines with a Stormphrax supplement, TCEC conditions and long time controls), nine specialists (mathematics, training science, search theory, tuning, statistics and testing, systems and hardware, chess knowledge, search-evaluation interaction, a cross-domain wildcard) and two skeptics who checked every proposal against the primary files. |

## How it was made

About twenty separate agents, in three phases: three Phase A analysts and
a merger that verified their load-bearing claims; three clean-room surveys,
nine specialists and two skeptics in Phase B; one judge in Phase C. Two
originality screens checked every file before the commit (no other
engine's constants or code, no personal data, no data-policy breach), and
their fixes were applied.

## Rules every file follows

- **Clean room.** The surveys used public release notes, READMEs, docs,
  papers, forum posts and commit or PR message text only, never engine
  source code, and they record no other engine's constants. Ideas are
  credited to their sources. Any instruction addressed to AI agents found
  in a source's text was treated as data and ignored (owner ruling,
  2026-11-07, on Stormphrax).
- **Fork-pure data.** Every training proposal uses only Fork's own games,
  Lichess CC0 positions and Syzygy tablebase labels. Where a proposal would
  touch other engines' games even for test selection (the blind-spot
  suite), it is flagged for an owner ruling and is never committed or
  trained on.
- **Compute.** This PC (shared with data generation), Kaggle's free GPUs
  and GitHub Actions. No AWS.
- References to `HANDOFF.md` are to the project's untracked session notes,
  which are not public; the facts they cite are also in DESIGN.md §5.6
  and §6, docs/nets.md and data/manifests/. References to `tank/...` are
  to the session's temporary working folder (scratch scripts, not
  committed).
