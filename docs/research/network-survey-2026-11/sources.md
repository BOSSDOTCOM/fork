# Sources

Clean-room network survey of 2026-11-14 ([README](README.md)). Every page was opened on
2026-11-14. Each group record carries its own numbered source table (URL, what it is, source
type, engines it was used for, failed fetches included), its credit lines (engine, author as
the page names them, licence where a page states it) and its clean-room statement. The
bracketed numbers in a record refer to that record's table.

| Group | Engines | Record | Rows in its source table |
|---|---|---|---|
| A | Stockfish, Torch, Dragon by Komodo, Ethereal | [records/group-a.md](records/group-a.md) | 60 |
| B | Triumviratus, Obsidian, PlentyChess, Coda, Reckless, Incipit | [records/group-b.md](records/group-b.md) | 53 |
| C | Gaia, Cinder, Berserk, Alexandria, pawnocchio, Integral | [records/group-c.md](records/group-c.md) | 46 |
| D | Caissa, Viridithas, Stormphrax, Hobbes, Horsie, Lizard | [records/group-d.md](records/group-d.md) | 54 |
| E | Astra, Raphael, RubiChess, Starzix, Tarnished, Clover, Halogen | [records/group-e.md](records/group-e.md) | 55 |
| F | Quanticade, Igel, PZChessBot, ZigQueen, Devre, JustBot, Titan | [records/group-f.md](records/group-f.md) | 64 |
| G | Velvet, Minke, Tcheran, Seer, Uralochka, Motor, Renegade | [records/group-g.md](records/group-g.md) | 45 |
| H | Fritz, Ginkgo, Revenge, Lc0, Chess System Tal, Stoofvlees, Rebel, rofChade | [records/group-h.md](records/group-h.md) | 88 |

## How the pages were opened

- Plain fetches of prose pages (READMEs, release pages, wikis, forum threads, vendor pages,
  papers), and the signed-in `gh api` for prose endpoints only: release lists, pull-request
  and issue text, commit-message lists. No endpoint that returns file contents or a diff was
  called. Each record states its number of API calls.
- Source types used in the tags: README, prose document, release notes, PR text, commit
  text, prose log, blog, slides, paper, forum, OpenBench or fishtest, TCEC, CPW, CCRL,
  vendor, release asset list (names and byte sizes shown by a release page; nothing was
  downloaded), prior survey, other.
- Pages the agents could not open are listed as failed in each table: among them the
  fishtest test pages, most archived Komodo pages, the Chess Programming Wiki pages of
  several newer engines (none exist), Kaggle dataset pages (script-rendered), the paywalled
  Stoofvlees article, and Discord.
- One page carries a notice against use with AI tools (the abstract page of the Stoofvlees
  article, group H's table). Nothing from it is recorded.
- One source is second-hand about other engines' code: a Triumviratus design note with a
  table of other engines' network shapes (group B's table, tagged "second-hand" where used).

## Pages the coordinator opened (2026-11-14)

| URL | What it is | Used for |
|---|---|---|
| https://computerchess.org.uk/404/ | CCRL Blitz home page, "Computed on November 14, 2026" | the list's date |
| https://computerchess.org.uk/404/cgi/compare_engines.cgi?print=Rating+list+%28text%29&class=all+engines&only_best_in_class=1 | CCRL Blitz rating list, all engines, best versions only (the CCRL team) | the 51 engines, their versions, ranks and ratings (README) |
| https://en.wikipedia.org/wiki/Zen_4 (and /wiki/Zen_4c, which redirects to it) | Wikipedia, read through a fetch agent | Zen 4 and Zen 4c cache per core; the Ryzen 5 7600X3D's cores and L3 (speed.md §1). Second-hand |
| https://en.wikipedia.org/wiki/Epyc | Wikipedia, read through a fetch agent | the EPYC 9754's cores and threads; 16 MB of L3 per group of 8 Zen 4c cores (speed.md §1). Second-hand |
| https://en.wikipedia.org/wiki/List_of_AMD_Ryzen_processors | Wikipedia, read in part through a fetch agent | the 7600X3D's name and L3 |
| https://www.amd.com/en/products/processors/server/epyc/4th-generation-9004-and-8004-series/amd-epyc-9754.html | AMD product page | **failed** (timeout, twice) |
| https://www.amd.com/en/products/specifications/server-processor.html | AMD specifications | **failed** (timeout) |
| https://www.amd.com/en/newsroom/press-releases/2023-6-13-amd-expands-4th-gen-epyc-cpu-portfolio-with-leadership.html | AMD press release | **failed** (timeout, twice) |
| https://www.amd.com/en/products/processors/desktops/ryzen/7000-series/amd-ryzen-5-7600x3d.html | AMD product page | **failed** (timeout, twice) |

## Fork's own files (read 2026-11-14, branch `phase-4` at b7ea9bf)

`docs/research/engine-survey-2026-11/` (README, comparison.md sections H to K, engines.md's
header and first record); `docs/history/phase-4/perf-log.md`;
`docs/research/tcec-hardware-test-plan.md`; `docs/research/network-novelty-2026-11-14.md`
(its snapshot and evidence table); `docs/ideas.md` (ideas 40 and 41); `docs/nets.md` (the
S512+PP entries); DESIGN.md §7; `config/tcec.json` as the hardware test plan quotes it; the
header comments of `src/eval/nnue/accumulator.hpp`, the weight declarations of
`net_file.hpp`, the comment above `squared_sum` in `accumulator.cpp`, and
`embedded_net.cpp`.
