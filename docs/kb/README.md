# Fork knowledge base

This is a maintained reference covering tools, research, techniques and
competition rules, organized around one goal: competing in TCEC with an
original engine. Each entry says what something is, why it matters for
Fork, where the information came from, and when it was verified.

## Tags

| Tag | Meaning |
|---|---|
| **USE** | Fine to use with or in Fork (permissive license, or a tool that isn't part of the engine). |
| **REFERENCE ONLY** | Study the idea and write Fork's own code. |
| **OFF-LIMITS** | Never use in Fork: other engines' code, nets, or engine-labelled data. |
| **UNVERIFIED** | Couldn't be confirmed from a primary source. Treat it as unknown, not as true. |

## Index

| File | Contents |
|---|---|
| [tools.md](tools.md) | Match runners (fastchess, cutechess-cli), OpenBench, SPRT/SPSA, Ordo/BayesElo, opening books, tactical and mate suites (WAC, matetrack), Syzygy and Fathom, NNUE trainers, data tools, profilers, PGN utilities |
| [uci.md](uci.md) | UCI protocol (April 2006 spec) summarised for Phase 2, standard options, timing rules, and how fastchess, cutechess and python-chess handle the gaps |
| [os-memory.md](os-memory.md) | OS facts behind the Hash memory code, checked against man pages, kernel docs/source and Microsoft Learn: MemAvailable, overcommit mode 0, MADV_HUGEPAGE/THP, VirtualAlloc commit, CRT text mode, mmap/munmap |
| [techniques.md](techniques.md) | Board, movegen, search, evaluation/NNUE, training, time management, SMP, each mapped to a Fork phase |
| [search-techniques.md](search-techniques.md) | Phase 3 idea mining: every search technique with tier, phase, dependencies and expected value from published SPRT results (Stockfish, 15 OpenBench engines, CPW, papers), plus clean-room descriptions of the tier 1 and 2 techniques, and (§3A, 2026-10-26) TT-refined eval, razoring, capture futility, delta pruning, check extension, upcoming repetition, fifty-move scaling, SMP voting and diversity, history malus balance (T50-T55) |
| [research.md](research.md) | Papers and results from 2023 on, newest first |
| [best-practices.md](best-practices.md) | Testing discipline, determinism, SPRT, TCEC-condition testing, originality hygiene |
| [competition.md](competition.md) | TCEC Season 30 rules, CCC, CCRL/CEGT, the engines Fork will face, with pinned builds |
| [originality.md](originality.md) | What TCEC allows and bans, precedents, how Fork documents provenance |
| [training-data.md](training-data.md) | External NNUE training-data sources (Lc0, Lichess, engine archives, Syzygy, datasets) evaluated, own vs external vs hybrid strategies, recommendation |
| [data-policy.md](data-policy.md) | Fork's data rules and the status of every external source (ALLOWED / ALLOWED WITH CATEGORY CHANGE / OFF-LIMITS / UNVERIFIED) |
| [nnue-design.md](nnue-design.md) | Phase 4 step 1 (2026-10-28): clean-room NNUE design concepts (inputs, accumulators, bodies, activations, quantization, training, SIMD, trainer-engine parity), evidence as cited ranges, no engine constants, and the design space for Fork |
| [phase4-pipeline.md](phase4-pipeline.md) | Phase 4 pipeline facts (2026-10-28): bullet (build, checkpoints, quantized layout, FEN evaluation), viriformat, Kaggle in practice, Fathom thread safety, Lichess openings, streamlining options, the Kaggle test session checklist |
| [phase4-designs/](phase4-designs/) | Phase 4 steps 2-3: three competing architecture proposals (speed-, accuracy- and novelty-first) and the judge's comparison |
| [sources.md](sources.md) | Every page consulted, with the date checked |
| [../../tools/install.sh](../../tools/install.sh) | Installs and smoke-tests the toolbase in WSL Ubuntu |
| [../../tools/versions.lock](../../tools/versions.lock) | Pinned versions of every tool |

## Findings that change Fork's plan (2026-10-23)

1. **Fork is a TCEC "Category 4" engine** (created with major help from AI).
   In Season 30, AI engines enter only through the Swiss (via a
   Category 3+4 playoff for one spot) and **are not eligible for the regular
   Leagues**. A separate gauntlet is planned for them instead. Category 4
   code must be public and open source, and TCEC admins build the binary from
   it. The questionnaire (v2.4) is mandatory and asks about AI use.
   See [competition.md](competition.md).
2. **The adjudication values in the original brief are outdated.**
   - Current draw rule: 6 or fewer pieces (kings counted, pawns not), with the
     eval within ±0.25 for 8 consecutive plies. Captures and pawn moves don't
     reset the count, and there is no minimum move.
   - There is no eval-based win adjudication. The ±10.00 and ±0.15 after
     move 35 rules apply only after a server outage.
3. **Engines get 7-man Syzygy**, not 6. TCEC asks engines to `madvise`
   the mapped files `MADV_RANDOM`. The pinned Fathom already does this when
   compiled as C++, but strict ISO C silently drops it (tools.md §6.4).
4. **Scale target: up to 512 threads and 256 GiB of hash.** The 256 GiB
   applies only if the hash is initialized by multiple threads; otherwise
   the cap is 32 or 64 GiB.
5. **Large pages are on automatically** on TCEC hardware. Fork still must not
   depend on them.
6. **Training-data traps.**
   - ChessBench, the Lichess eval database and Stockfish/Leela datasets are
     engine-labelled, so they're OFF-LIMITS.
   - Top engines now train on Lc0 data, so Fork's self-play-only route needs
     an early bootstrapping plan.
   - *2026-10-24:* full source evaluation in
     [training-data.md](training-data.md), statuses in
     [data-policy.md](data-policy.md). The CatGPT precedent (AI code plus
     Lc0 data, still Category 4) means Lc0 data would not change Fork's
     category today. The recommendation is still own labels (strategy A+),
     pending the owner's decision.
7. **Techniques now considered standard:** correction history (Phase 3) and
   threat inputs in NNUE (Phase 4). See [techniques.md](techniques.md).

## Keeping this current

- **Before each phase:** re-check the entries that phase depends on (for
  example tools and Syzygy before Phase 3, TCEC rules before Phases 5 and 8),
  update the "verified" dates, and log new pages in sources.md.
- **At every phase-end checklist (owner, 2026-10-24):** merge `main`
  into `kb` so the branches stay in sync. `docs/DESIGN.md` on kb is only
  a pointer to main's copy, so on a conflict take main's version. The
  step belongs in the phase-end checklist in main's `CLAUDE.md` (add it
  there at the next phase end).
- **Each TCEC season:**
  - Re-read the official rule pages listed in competition.md.
  - Update `config/tcec.json`. Set `verified` only for values confirmed on
    an official page.
  - Record what changed in competition.md.
- **Tool upgrades:** change `tools/versions.lock` first, then re-run
  `tools/install.sh` (it's idempotent and verifies each tool), then re-run
  bench parity and a short match before relying on the new version.
- **Rules for entries:**
  - Primary sources only, opened rather than taken from search snippets.
  - Written in our own words.
  - Anything unconfirmed is marked UNVERIFIED.
  - Every entry carries a tag and a license where one applies.
- **Status:** `tools/install.sh` hasn't been run yet. It needs WSL Ubuntu,
  which isn't installed as of 2026-10-23.
