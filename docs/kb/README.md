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
| [tools.md](tools.md) | Match runners (fastchess, cutechess-cli), OpenBench, SPRT/SPSA, Ordo/BayesElo, opening books, Syzygy and Fathom, NNUE trainers, data tools, profilers, PGN utilities |
| [uci.md](uci.md) | UCI protocol (April 2006 spec) summarised for Phase 2, standard options, timing rules, and how fastchess, cutechess and python-chess handle the gaps |
| [techniques.md](techniques.md) | Board, movegen, search, evaluation/NNUE, training, time management, SMP, each mapped to a Fork phase |
| [research.md](research.md) | Papers and results from 2023 on, newest first |
| [best-practices.md](best-practices.md) | Testing discipline, determinism, SPRT, TCEC-condition testing, originality hygiene |
| [competition.md](competition.md) | TCEC Season 30 rules, CCC, CCRL/CEGT, the engines Fork will face, with pinned builds |
| [originality.md](originality.md) | What TCEC allows and bans, precedents, how Fork documents provenance |
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
   the mapped files `MADV_RANDOM`.
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
7. **Techniques now considered standard:** correction history (Phase 3) and
   threat inputs in NNUE (Phase 4). See [techniques.md](techniques.md).

## Keeping this current

- **Before each phase:** re-check the entries that phase depends on (for
  example tools and Syzygy before Phase 3, TCEC rules before Phases 5 and 8),
  update the "verified" dates, and log new pages in sources.md.
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
