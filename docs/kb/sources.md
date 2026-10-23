# Sources consulted

Every page opened while building this knowledge base, with the date it was checked. Grouped by the KB file that used it. Pages that failed to load are listed as such.


## Tools (tools.md, install.sh, versions.lock)


Every page or file opened for this research. Format: URL | what it is | date checked | used for.
"API" means a GitHub REST API JSON response (repository metadata, which includes the license field, or the releases list).
"raw" means a file fetched from raw.githubusercontent.com at the stated ref.
"ls-remote" means `git ls-remote` against the repo (tags, HEAD and peeled commit SHAs).

## Match runners
- https://api.github.com/repos/Disservin/fastchess (+ /releases) | API: license, push date, releases and asset sha256 digests | 2026-10-23 | fastchess licence, v1.8.2-alpha date, binary sha256
- https://github.com/Disservin/fastchess (ls-remote) | tags/HEAD | 2026-10-23 | tag commit f618e345
- https://raw.githubusercontent.com/Disservin/fastchess/master/README.md | README | 2026-10-23 | build steps, --compliance invocation, features
- https://raw.githubusercontent.com/Disservin/fastchess/v1.8.2-alpha/man.md | man page at tag | 2026-10-23 | all CLI options (SPRT, adjudication, books, concurrency, pgnout)
- https://api.github.com/repos/Disservin/fastchess/git/trees/v1.8.2-alpha?recursive=1 | API tree | 2026-10-23 | locating compliance.hpp, LICENSE, Makefile
- https://raw.githubusercontent.com/Disservin/fastchess/v1.8.2-alpha/app/src/engine/compliance.hpp | source of the compliance checker | 2026-10-23 | what --compliance checks
- https://api.github.com/repos/cutechess/cutechess (+ /releases) | API | 2026-10-23 | licence, v1.5.1 date, AppImage sha256
- https://github.com/cutechess/cutechess (ls-remote) | tags | 2026-10-23 | v1.5.1 peeled commit 45e92394
- https://raw.githubusercontent.com/cutechess/cutechess/master/README.md and .../v1.5.1/README.md | README | 2026-10-23 | Qt >= 6.8 requirement, modules, licence text
- https://raw.githubusercontent.com/cutechess/cutechess/v1.5.1/CMakeLists.txt | build file at tag | 2026-10-23 | no CLI-only option; WITH_TESTS; cli target
- https://raw.githubusercontent.com/cutechess/cutechess/master/docs/cutechess-cli.6 and .../v1.5.1/docs/cutechess-cli.6 | man page | 2026-10-23 | CLI options (repeat, draw/resign/tb, sprt, openings)
- https://github.com/cutechess/cutechess/wiki/Building-from-source | wiki | 2026-10-23 | Ubuntu apt package list
- https://packages.ubuntu.com/search?keywords=qt6-base-dev... | Ubuntu package search | 2026-10-23 | attempted, connection reset (so the Qt version per Ubuntu release is UNVERIFIED)
- https://api.launchpad.net/1.0/ubuntu/+archive/primary?ws.op=getPublishedSources&source_name=qt6-base... | Launchpad API | 2026-10-23 | attempted, no response

## Testing frameworks, SPRT, SPSA
- https://api.github.com/repos/AndyGrant/OpenBench (+ /releases) | API | 2026-10-23 | licence, no releases, push date
- https://raw.githubusercontent.com/AndyGrant/OpenBench/master/README.md | README | 2026-10-23 | what OpenBench is, uses fastchess
- https://github.com/AndyGrant/OpenBench/wiki | wiki index | 2026-10-23 | list of wiki pages
- https://github.com/AndyGrant/OpenBench/wiki/SPSA-Tuning-Workloads | wiki | 2026-10-23 | SPSA input format, defaults
- https://github.com/AndyGrant/OpenBench/wiki/Creating-Your-OpenBench-Instance | wiki | 2026-10-23 | private instance requirements
- https://api.github.com/repos/official-stockfish/fishtest (+ /releases, /contents) | API | 2026-10-23 | no licence metadata, root file list
- https://raw.githubusercontent.com/official-stockfish/fishtest/master/README.md and /pyproject.toml | README, project file | 2026-10-23 | what fishtest is; no licence field
- https://www.chessprogramming.org/Sequential_Probability_Ratio_Test | CPW | 2026-10-23 | SPRT overview, list of tools/calculators
- https://tests.stockfishchess.org/sprt_calc | Fishtest SPRT calculator | 2026-10-23 | attempted, bot wall (UNVERIFIED)
- https://api.github.com/repos/jnlt3/weather-factory (+ /releases) and raw .../main/README.md | API and README | 2026-10-23 | MIT, usage, no releases
- https://api.github.com/repos/kiudee/chess-tuning-tools (+ /releases), raw .../master/README.rst, raw .../master/LICENSE | API, README, licence | 2026-10-23 | Apache-2.0, v0.9.5 date, needs cutechess-cli
- https://pypi.org/pypi/chess-tuning-tools/json | PyPI JSON | 2026-10-23 | latest version 0.9.5 and upload date

## Rating tools
- https://api.github.com/repos/michiguel/Ordo (+ /releases, /commits) | API | 2026-10-23 | licence, release tags, last commit 2016
- https://raw.githubusercontent.com/michiguel/Ordo/master/README.md and /LICENSE.txt | README, licence | 2026-10-23 | usage, GPL-3.0
- https://raw.githubusercontent.com/michiguel/Ordo/v1.2.6/Makefile | Makefile at tag | 2026-10-23 | build and install targets for install.sh
- https://www.remi-coulom.fr/Bayesian-Elo/ | author's BayesElo page | 2026-10-23 | licence (GPL), latest history date, downloads
- https://www.chessprogramming.org/Match_Statistics | CPW | 2026-10-23 | rating tool list and Ordo history
- https://www.chessprogramming.org/Bayeselo, /BayesElo, /Ordo | CPW | 2026-10-23 | attempted, 404

## Opening books
- https://api.github.com/repos/official-stockfish/books (+ /contents), raw .../master/README.md, raw .../master/LICENSE | API, README, licence | 2026-10-23 | CC0-1.0, book list and sizes
- https://www.sp-cc.de/ | Stefan Pohl SPCC home page | 2026-10-23 | UHO sets overview
- https://www.sp-cc.de/uho_2024.htm | UHO 2024 page | 2026-10-23 | how UHO 2024 was made, windows, terms
- https://www.sp-cc.de/uho_2025.htm | attempted | 2026-10-23 | 404 (no UHO 2025 page)
- https://www.chessprogramming.org/Opening_Book | CPW | 2026-10-23 | other test suites
- https://tcec-chess.com/articles/TCEC_Openings_FAQ.html | TCEC official FAQ | 2026-10-23 | TCEC book structure, bias, pairing
- https://github.com/TCEC-Chess/tcecgames | TCEC games archive repo | 2026-10-23 | PGN licence CC BY-SA 3.0, compacted format with book-exit markers
- WebSearch "TCEC opening book download season openings" | search (used only to find the FAQ URL) | 2026-10-23 | discovery only; no facts taken from snippets

## Syzygy and Fathom
- https://www.chessprogramming.org/Syzygy_Bases | CPW | 2026-10-23 | WDL/DTZ roles, sizes, probing-code licences
- https://syzygy-tables.info/metrics | official site | 2026-10-23 | attempted, Anubis access denied
- https://api.github.com/repos/niklasf/syzygy-tables.info and /git/trees/master?recursive=1 | API | 2026-10-23 | AGPL-3.0 site code; checksums directory
- https://raw.githubusercontent.com/niklasf/syzygy-tables.info/master/checksums/bytes.tsv | file sizes | 2026-10-23 | computed per-piece-count sizes
- https://raw.githubusercontent.com/niklasf/syzygy-tables.info/master/checksums/sha256 | sha256 list | 2026-10-23 | checksum list (hash pinned)
- https://raw.githubusercontent.com/niklasf/syzygy-tables.info/master/syzygy_tables_info/views.py | site source | 2026-10-23 | official size table (KiB), mirror list, checksum links
- https://tablebase.lichess.ovh/tables/ and /tables/standard/ | mirror directory listings | 2026-10-23 | directory layout, checksum files
- https://tablebase.lichess.ovh/tables/standard/3-4-5-wdl/, /3-4-5-dtz/, /6-wdl/, /6-dtz/ | mirror listings | 2026-10-23 | file counts (145/145/365/365)
- https://tablebase.lichess.ovh/tables/standard/sha256 | mirror sha256 list | 2026-10-23 | byte-identical to the repo copy (sha256 6dc75697…)
- https://tablebase.lichess.ovh/tables/standard/download.txt | URL list | 2026-10-23 | URL pattern for install.sh
- http://tablebase.sesse.net/syzygy/ | second mirror | 2026-10-23 | reachability only (HTTP 200)
- https://raw.githubusercontent.com/jdart1/Fathom/master/README.md and /LICENSE | README, licence | 2026-10-23 | maintenance status, API, Cfish lineage, MIT
- https://raw.githubusercontent.com/basil00/Fathom/master/README.md; https://api.github.com/repos/basil00/Fathom (+ /releases) | README, API | 2026-10-23 | original Fathom, v1.0 from 2015, MIT
- https://api.github.com/repos/jdart1/Fathom (+ /releases); ls-remote | API, tags | 2026-10-23 | no releases; master commit pinned
- https://raw.githubusercontent.com/AndyGrant/Pyrrhic/master/LICENSE; ls-remote | licence | 2026-10-23 | Pyrrhic MIT

## NNUE trainers and data formats
- https://api.github.com/repos/jw1912/bullet; raw .../main/README.md, /LICENSE, /docs/0-contents.md, /docs/2-getting-started.md, /docs/3-data.md | API, README, licence, docs | 2026-10-23 | MIT, features, data loaders, bullet-utils
- https://api.github.com/repos/official-stockfish/nnue-pytorch; raw .../master/README.md, /LICENSE | API, README, licence | 2026-10-23 | GPL-3.0, requirements, data needs
- https://api.github.com/repos/jnlt3/marlinflow; raw .../main/README.md | API, README | 2026-10-23 | GPL-3.0 metadata, legacy text format, utils
- https://api.github.com/repos/Luecx/Grapheus (+ /contents); raw .../main/README.md | API, README | 2026-10-23 | no licence file
- https://raw.githubusercontent.com/Luecx/CudAD/main/LICENSE | licence | 2026-10-23 | GPL-3.0
- https://api.github.com/repos/cosmobobak/viriformat (+ /contents); raw .../main/README.md, /Cargo.toml | API, spec, crate manifest | 2026-10-23 | format spec, MIT, v3.0.0
- https://raw.githubusercontent.com/jw1912/bulletformat/main/LICENSE and /Cargo.toml | licence | 2026-10-23 | MIT
- github.com/{jnlt3,dsekercioglu,Ciekce}/marlinformat (ls-remote) | repo probes | 2026-10-23 | not found (UNVERIFIED)
- https://github.com/official-stockfish/Stockfish (ls-remote, heads) | branches | 2026-10-23 | tools branch head
- https://raw.githubusercontent.com/official-stockfish/Stockfish/tools/docs/generate_training_data.md and /tools/Copying.txt | Stockfish data-generation doc and licence | 2026-10-23 | what the tool does (OFF-LIMITS), GPL-3.0

## Profilers
- https://perfwiki.github.io/main/ | perf wiki | 2026-10-23 | what perf is, in kernel tools/perf
- https://valgrind.org/downloads/current.html | valgrind downloads | 2026-10-23 | 3.27.1, date, md5/sha1
- https://sourceware.org/git/?p=valgrind.git;a=blob_plain;f=COPYING;hb=HEAD | valgrind COPYING | 2026-10-23 | licence text (GPLv3 at HEAD)
- https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler-download.html | VTune download page | 2026-10-23 | version from installer names, EULA, apt/Docker options
- https://www.amd.com/en/developer/uprof.html | AMD uProf page | 2026-10-23 | 5.3 (2026-06-17), OS support, EULA download
- https://api.github.com/repos/KDAB/hotspot (+ /releases, /contents); raw .../master/README.md, /LICENSE.GPL.txt | API, README, licence | 2026-10-23 | GPL v2+, v1.6.0 AppImage and sha256

## PGN utilities
- https://www.cs.kent.ac.uk/people/staff/djb/pgn-extract/ | pgn-extract home | 2026-10-23 | version 26-04, GPL-3, features
- https://api.github.com/repos/niklasf/python-chess (+ /releases); raw .../master/README.rst; ls-remote | API, README, tags | 2026-10-23 | GPL-3.0, features, v1.11.2
- https://pypi.org/pypi/chess/json | PyPI JSON | 2026-10-23 | 1.11.2, licence, sdist sha256

## Other repo probes (ls-remote only)
- TCEC-Chess/{TCEC-Openings,openings,tcec-openings}: not found. Disservin/fast-chess: redirects to fastchess. official-stockfish/WDL_model, Disservin/chess-library, raklaptudirm/arbiter and AndyGrant/Ethereal exist but were not researched further.

## Research and techniques (research.md, techniques.md)


Every page below was fetched (WebFetch) on 2026-10-23. Search-result
snippets were used only to find URLs, never as evidence.

URL | what it is | date checked | used for
---|---|---|---
https://arxiv.org/abs/2402.04494 | arXiv abstract, Ruoss et al., v2 "Amortized Planning with Large-Scale Transformers" | 2026-10-23 | research §2 searchless chess, ChessBench labels (Stockfish 16)
https://arxiv.org/abs/2402.04494v1 | arXiv v1 "Grandmaster-Level Chess Without Search" | 2026-10-23 | research §2 original title, 2895 Elo
https://github.com/google-deepmind/searchless_chess | official repo page | 2026-10-23 | research §2/§7 ChessBench size and licenses
https://raw.githubusercontent.com/google-deepmind/searchless_chess/main/README.md | repo README | 2026-10-23 | NeurIPS 2024 venue, license wording
https://arxiv.org/abs/2308.09175 | Zahavy et al., Diversifying AI (AZ_db) | 2026-10-23 | research §4
https://arxiv.org/abs/2211.00241 | Wang et al., Adversarial Policies Beat Superhuman Go AIs | 2026-10-23 | research §5
https://arxiv.org/abs/2406.12843 | Tseng et al., Can Go AIs be adversarially robust? | 2026-10-23 | research §5
https://arxiv.org/abs/2306.09983 | Fluri et al., Consistency Checks (abstract) | 2026-10-23 | research §5
https://arxiv.org/html/2306.09983v3 | same, full text HTML | 2026-10-23 | Lc0 version and failure rates
https://arxiv.org/abs/2409.20553 | Maia-2 abstract | 2026-10-23 | research §3
https://github.com/CSSLab/maia2 | Maia-2 repo | 2026-10-23 | MIT license, training data, Maia-3 recommendation
https://arxiv.org/abs/2507.21488 | Maia4All abstract | 2026-10-23 | research §3
https://arxiv.org/abs/2006.01855 | original Maia (KDD 2020) | 2026-10-23 | research §3 background
https://lichess.org/@/ashtonanderson/blog/introducing-maia-3-free-and-open-source/vCPPRtX3 | Lichess blog, Maia-3 announcement | 2026-10-23 | FAILED (HTTP 403); not used
https://huggingface.co/UofTCSSLab/Maia3-79M | Maia-3 model card | 2026-10-23 | research §1 Maia-3, AGPLv3
https://arxiv.org/abs/2605.19091 | Chessformer (ICLR 2026) abstract | 2026-10-23 | research §1
https://arxiv.org/abs/2409.12272 | Mastering Chess with a Transformer Model | 2026-10-23 | research §2
https://lczero.org/blog/2024/02/transformer-progress/ | Lc0 blog, transformer progress (BT1-BT4) | 2026-10-23 | research §6
https://arxiv.org/abs/2510.20783 | OOD compositionality in chess transformers (abstract) | 2026-10-23 | research §2
https://arxiv.org/html/2510.20783 | same, full text | 2026-10-23 | label source (Stockfish 16 via ChessBench), Lichess ratings
https://arxiv.org/abs/2603.29761 | Tracking vs Deciding (searchless transformers) | 2026-10-23 | research §2
https://arxiv.org/abs/2604.05134 | How Reasoning Evolves from Post-Training Data (LLM chess) | 2026-10-23 | research §2
https://arxiv.org/abs/2412.12119 | MAV / external and internal planning with LMs (abstract) | 2026-10-23 | research §2
https://arxiv.org/html/2412.12119v3 | same, full text | 2026-10-23 | Stockfish labels, Elo table
https://arxiv.org/abs/2306.09200 | ChessGPT | 2026-10-23 | research §2
https://arxiv.org/abs/2412.17948 | Study of the Proper NNUE Dataset | 2026-10-23 | research §6, techniques §5
https://www.chessprogramming.org/NNUE | CPW NNUE | 2026-10-23 | research §6, techniques §4
https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md | nnue-pytorch docs (GitHub view) | 2026-10-23 | page body truncated; content read via raw URL below
https://raw.githubusercontent.com/official-stockfish/nnue-pytorch/master/docs/nnue.md | nnue-pytorch docs raw (read in two parts) | 2026-10-23 | research §6 features, threats, quantisation, loss; techniques §4-5
https://github.com/official-stockfish/nnue-pytorch/wiki/Training-datasets | nnue-pytorch wiki, training datasets | 2026-10-23 | research §7 data provenance
https://github.com/jw1912/bullet | bullet trainer repo | 2026-10-23 | research §6 (MIT), techniques §5
https://github.com/jw1912/bullet/blob/main/docs/0-contents.md | bullet docs contents | 2026-10-23 | doc structure
https://raw.githubusercontent.com/jw1912/bullet/main/docs/1-basics.md | bullet docs NNUE basics | 2026-10-23 | perspective nets, beginner advice
https://raw.githubusercontent.com/jw1912/bullet/main/docs/3-data.md | bullet docs training data | 2026-10-23 | data formats, text format, shuffling
https://stockfishchess.org/blog/2026/stockfish-18/ | Stockfish 18 release post | 2026-10-23 | threat inputs, correction history, Lc0 data
https://stockfishchess.org/blog/2026/stockfish-19/ | Stockfish 19 release post | 2026-10-23 | SFNNv16, pawn pairs, QAT, Leela rescoring
https://stockfishchess.org/blog/2024/stockfish-17/ | Stockfish 17 release post | 2026-10-23 | NumaPolicy, Lc0 data
https://github.com/official-stockfish/Stockfish | Stockfish repo page | 2026-10-23 | GPL-3.0 license; REFERENCE ONLY note
https://lczero.org/blog/2021/06/the-importance-of-open-data/ | Lc0 blog, open data | 2026-10-23 | Lc0 data ODbL/DbCL, storage location
https://talkchess.com/viewtopic.php?p=896060 | TalkChess post quoting Lc0 data license | 2026-10-23 | cross-check of ODbL statement
https://database.lichess.org/ | Lichess database page (first 100k chars) | 2026-10-23 | CC0; evaluations DB produced by Stockfish
https://wiki.chessdom.org/Rules | TCEC official rules page | 2026-10-23 | time controls, ponder/book rules
https://en.wikipedia.org/wiki/Top_Chess_Engine_Championship | Wikipedia TCEC (secondary) | 2026-10-23 | clone bans, Linux, ponder off
https://www.chessprogramming.org/Correction_History | CPW (wrong title) | 2026-10-23 | FAILED (404); replaced by next row
https://www.chessprogramming.org/Static_Evaluation_Correction_History | CPW correction history | 2026-10-23 | research §6, techniques §3
https://www.chessprogramming.org/Bitboards | CPW | 2026-10-23 | techniques §1
https://www.chessprogramming.org/Magic_Bitboards | CPW | 2026-10-23 | techniques §1
https://www.chessprogramming.org/BMI2 | CPW (PEXT) | 2026-10-23 | techniques §1
https://www.chessprogramming.org/Zobrist_Hashing | CPW | 2026-10-23 | techniques §1
https://www.chessprogramming.org/Move_Generation | CPW | 2026-10-23 | techniques §2
https://www.chessprogramming.org/Perft | CPW | 2026-10-23 | techniques §2
https://www.chessprogramming.org/Principal_Variation_Search | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Aspiration_Windows | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Quiescence_Search | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Static_Exchange_Evaluation | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Transposition_Table | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Move_Ordering | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Killer_Heuristic | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/History_Heuristic | CPW (incl. continuation/capture history) | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Countermove_Heuristic | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Null_Move_Pruning | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Late_Move_Reductions | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Reverse_Futility_Pruning | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Futility_Pruning | CPW (incl. move-count pruning) | 2026-10-23 | techniques §3
https://www.chessprogramming.org/ProbCut | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Singular_Extensions | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Check_Extensions | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Mate_Distance_Pruning | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Internal_Iterative_Deepening | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Internal_Iterative_Reductions | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Repetitions | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Fifty-move_Rule | CPW | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Syzygy_Bases | CPW (incl. Fathom MIT) | 2026-10-23 | techniques §3
https://www.chessprogramming.org/Search_Progression | CPW feature-order lists | 2026-10-23 | techniques intro, §3, §6
https://www.chessprogramming.org/Tapered_Eval | CPW | 2026-10-23 | techniques §4
https://www.chessprogramming.org/Texel%27s_Tuning_Method | CPW | 2026-10-23 | techniques §4
https://www.chessprogramming.org/Time_Management | CPW | 2026-10-23 | techniques §6
https://www.chessprogramming.org/Lazy_SMP | CPW | 2026-10-23 | techniques §7
https://www.chessprogramming.org/NUMA | CPW | 2026-10-23 | techniques §7
https://learn.microsoft.com/en-us/windows/win32/procthread/processor-groups | Microsoft Learn, processor groups (updated 2025-07-14) | 2026-10-23 | techniques §7 Windows 11 behaviour
https://www.chessprogramming.org/Sequential_Probability_Ratio_Test | CPW SPRT | 2026-10-23 | techniques §7 testing

## Competition and originality (competition.md, originality.md, config/tcec.json)


All pages opened on 2026-10-23.

| URL | What it is | Date checked | Used for |
|---|---|---|---|
| https://wiki.chessdom.org/Rules | TCEC wiki, rules for all event types | 2026-10-23 | Event formats, TCs, draw rule, outage rules, Cup and FRD rules |
| https://tcec-chess.com/ | TCEC home (script-rendered shell) | 2026-10-23 | Nothing usable; noted links only |
| https://wiki.chessdom.org/TCEC_Season_Further_information | TCEC wiki, hardware and engine settings (edited 24 Feb 2026) | 2026-10-23 | Hardware, threads, hash caps, large pages, ponder, TBs, books, builds |
| https://wiki.chessdom.org/Main_Page | TCEC wiki main page | 2026-10-23 | Current season (S30), event list |
| https://wiki.chessdom.org/TCEC_Leagues_Season_Rules | TCEC Leagues rules (edited 21 Jul 2025) | 2026-10-23 | League structure, TCs, draw rule, updates, crashes |
| https://wiki.chessdom.org/TCEC_Questionnaire | Entry questionnaire v2.4 (edited 9 Nov 2025) | 2026-10-23 | Entry requirements, originality questions, links |
| https://wiki.chessdom.org/TCEC_Swiss_10 | S30 Swiss 10 page (edited 22 Oct 2026) | 2026-10-23 | Categories, Cat 4 AI rules, Potential decision, participants |
| https://wiki.chessdom.org/Current_Engine_Status | Engine status page (edited 16 Oct 2026) | 2026-10-23 | Engine placements S30/S31 |
| https://wiki.chessdom.org/TCEC_NNUE_Guideline | Unofficial NNUE guideline (edited 10 Jan 2022) | 2026-10-23 | NNUE originality rules |
| https://wiki.chessdom.org/TCEC_Swiss_Tournament_System | Swiss seeding description | 2026-10-23 | Seeding (no category info) |
| https://wiki.chessdom.org/TCEC_Swiss_rules | Swiss rules (edited 22 Dec 2025) | 2026-10-23 | Swiss TC, paired openings, draw rule |
| https://wiki.chessdom.org/index.php?search=category+AI-assisted&fulltext=1 | Wiki search | 2026-10-23 | Locating category definitions |
| https://wiki.chessdom.org/Category:Regulations | Wiki category | 2026-10-23 | Locating rule pages |
| https://wiki.chessdom.org/index.php?search=%22Category+4%22&fulltext=1 | Wiki search | 2026-10-23 | Locating Cat 4 definitions |
| https://wiki.chessdom.org/Category:Rules | Wiki category | 2026-10-23 | List of rule pages |
| https://wiki.chessdom.org/TCEC_Swiss_9 | S29 Swiss page | 2026-10-23 | Older category scheme |
| https://wiki.chessdom.org/TCEC_Swiss_7 | S27 Swiss page | 2026-10-23 | "own data" vs "leela data" categories, originality test label |
| https://wiki.chessdom.org/TCEC_Swiss_8 | S28 Swiss page | 2026-10-23 | Older category scheme |
| https://wiki.chessdom.org/TCEC_Leagues_Season_29 | S29 Leagues page (edited 4 Feb 2026) | 2026-10-23 | Questionnaire mandatory from S29 |
| https://wiki.chessdom.org/TCEC_Season_20_Rules | S20 rules | 2026-10-23 | Historical comparison (TCs, draw rule, 6-man TB) |
| https://tcec-chess.com/tournament.json | TCEC live site data | 2026-10-23 | Current season/division |
| https://tcec-chess.com/live.json | TCEC live game PGN data | 2026-10-23 | TC 1800+3, Threads 512, Hash 262144, SyzygyPath syzygy7 |
| https://www.chess.com/computer-chess-championship | CCC page (script-rendered) | 2026-10-23 | Nothing usable |
| https://computerchess.org.uk/ccrl/4040/ | CCRL 40/15 list (23 Oct 2026) | 2026-10-23 | Top 10, conditions |
| https://computerchess.org.uk/ccrl/404/ | CCRL Blitz list (17 Oct 2026) | 2026-10-23 | Top 10, conditions |
| https://computerchess.org.uk/ccrl/404FRC/ | CCRL 40/2 FRC list (4 Oct 2026) | 2026-10-23 | Top 10, conditions |
| https://computerchess.org.uk/ccrl/about.html | (404 Not Found) | 2026-10-23 | Nothing |
| https://computerchess.org.uk/ccrl/4040/about.html | CCRL 40/15 About | 2026-10-23 | Testing method, originality stance |
| https://www.cegt.net/ | CEGT home (HTTPS TLS error) | 2026-10-23 | Nothing (retried over HTTP) |
| http://www.cegt.net/ | CEGT home (via curl) | 2026-10-23 | List index |
| http://www.cegt.net/rating.htm | CEGT 40/40 index (18 Oct 2026) | 2026-10-23 | List date |
| http://www.cegt.net/blitz.htm | CEGT 40/4 index (6 Jun 2025) | 2026-10-23 | List date |
| http://www.cegt.net/rating5plus3pbon.htm | CEGT 5'+3" PB on | 2026-10-23 | Testing conditions example |
| http://www.cegt.net/40_40%20Rating%20List/40_40%20BestVersion/rangliste.html | CEGT best versions 40/20 | 2026-10-23 | Top 10 |
| http://www.cegt.net/40_4_Ratinglist/40_4_single/rangliste.html | CEGT 40/4 single | 2026-10-23 | Top 10 |
| https://api.github.com/repos/{official-stockfish/Stockfish, LeelaChessZero/lc0, jhonnold/berserk, gab8192/Obsidian, Witek902/Caissa, AndyGrant/Ethereal, aronpetko/integral, codedeliveryservice/Reckless, Yoshie2000/PlentyChess, cosmobobak/viridithas, PGG106/Alexandria, Ciekce/Stormphrax, JonathanHallstrom/pawnocchio} (repo, releases/latest, readme) | Official engine repos via GitHub API | 2026-10-23 | License, latest release, NN/data provenance |
| https://api.github.com/repos/aronpetko/integral/contents/ | Integral repo root listing | 2026-10-23 | No LICENSE file present |
| https://komodochess.com/ | Komodo/Dragon site (TLS certificate expired, not read) | 2026-10-23 | Nothing |
| https://www.chess.com/news/view/torch-chess-engine | chess.com Torch announcement (updated 17 Jul 2023) | 2026-10-23 | Torch team, closed, original code claim |
| https://www.chessprogramming.org/Computer_Chess_Championship | (404 Not Found) | 2026-10-23 | Nothing |
| https://www.chess.com/blog/AndrewGrantEthereal | CCC organiser's blog index | 2026-10-23 | Latest CCC events |
| https://www.chess.com/blog/AndrewGrantEthereal/ccc25-rapid | CCC25 Rapid write-up (17 Nov 2025) | 2026-10-23 | CCC format and TC |
| https://stockfishchess.org/blog/2021/our-lawsuit-against-chessbase/ | Stockfish official blog (20 Jul 2021) | 2026-10-23 | Fat Fritz 2 / Houdini 6 precedent |
| https://stockfishchess.org/blog/2022/chessbase-stockfish-agreement/ | Stockfish official blog (18 Nov 2022) | 2026-10-23 | Settlement terms |
| https://www.chessprogramming.org/Rybka_Controversy | Chess Programming Wiki (secondary) | 2026-10-23 | Rybka/ICGA precedent |
| https://wiki.chessdom.org/index.php?search=derivative&fulltext=1&limit=50 | Wiki search | 2026-10-23 | Checking for derivative rules (none) |
| https://wiki.chessdom.org/index.php?search=%22Fat+Fritz%22&fulltext=1&limit=50 | Wiki search | 2026-10-23 | Checking FF2 at TCEC (none) |
| https://www.chessdom.com/tcec-announces-ai-integration-plans-as-a-new-generation-of-engines-enters-the-arena/ | Official TCEC TD statement on AI engines (31 Aug 2026); WebFetch got 429, read via curl | 2026-10-23 | S30 AI policy |
| http://rebel13.nl/download/programmer-c-ode-of-honor.html | Chess Programmer Code of Honor (HTTP 526) | 2026-10-23 | Nothing (UNVERIFIED) |
| https://wiki.chessdom.org/Openings_FAQ | Openings FAQ (edited 5 Feb 2022) | 2026-10-23 | Paired openings, bias, bookmakers |
| https://wiki.chessdom.org/Viridithas_questionnaire_20251013 | Example questionnaire answers | 2026-10-23 | Model for Fork's answers |
| https://wiki.chessdom.org/index.php?search=CatGPT&fulltext=1 | Wiki search | 2026-10-23 | Cat 4 engine history |

Search engine queries (results used only to find URLs, never as facts):
"TCEC NNUE Guideline wiki.chessdom.org", "Torch chess engine chess.com
official page download", "chess.com Computer Chess Championship CCC 2026
hardware time control".

## Best practices and independent verification (best-practices.md)

Opened by the coordinating session on 2026-10-23 to write best-practices.md and to re-check the most consequential competition claims independently of the research agents.

| URL | What it is | Date checked | Used for |
|---|---|---|---|
| https://www.chessprogramming.org/Perft | CPW perft page | 2026-10-23 | Perft, divide, hashing caveat |
| https://www.chessprogramming.org/Perft_Results | CPW perft results | 2026-10-23 | Suite FENs and counts (character-by-character check) |
| https://www.chessprogramming.org/Sequential_Probability_Ratio_Test | CPW SPRT page | 2026-10-23 | SPRT method, gainer and non-regression bounds, pentanomial note |
| https://www.chessprogramming.org/Engine_Testing | CPW engine testing | 2026-10-23 | Fixed vs timed testing, TC sensitivity, paired openings |
| https://www.chessprogramming.org/Match_Statistics | CPW match statistics | 2026-10-23 | Statistics background |
| https://wiki.chessdom.org/Rules | TCEC rules | 2026-10-23 | Re-checked: draw rule (6 pieces, ±0.25, 8 plies), wins only by mate/illegal/resign, TCs 30'+3", 60'+6", 120'+12" |
| https://wiki.chessdom.org/TCEC_Season_Further_information | TCEC hardware and settings | 2026-10-23 | Re-checked: 512 threads, 256 GiB hash (multithreaded init), 7-men Syzygy, large pages automatic, no ponder |
| https://wiki.chessdom.org/TCEC_Swiss_10 | TCEC S30 Swiss 10 | 2026-10-23 | Re-checked: Category 4 (major AI help) rules, open-source requirement |
| https://www.chessdom.com/tcec-announces-ai-integration-plans-as-a-new-generation-of-engines-enters-the-arena/ | TD statement 2026-08-31 | 2026-10-23 | Re-checked: AI engines only via the Swiss, not eligible for the regular Leagues |
| https://tcec-chess.com/live.json | TCEC live game data | 2026-10-23 | Re-checked: S30 Swiss 10, TimeControl 1800+3 |
| https://api.github.com/repos/{Disservin/fastchess,cutechess/cutechess,jdart1/Fathom,jw1912/bullet} | GitHub API | 2026-10-23 | Re-checked: fastchess v1.8.2-alpha MIT, cutechess v1.5.1 GPL-3.0, Fathom MIT, bullet MIT |
