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

## Research library

Opened on 2026-10-23 for the "Research library (classic and foundational papers)" section of research.md. "Crossref" means the REST API record at https://api.crossref.org/works/<DOI>, or a Crossref bibliographic search limited to *ICGA Journal*, fetched with curl. Searches were used only to find records. Every citation was read from the record itself.

| URL | What it is | Date checked | Used for |
|---|---|---|---|
| https://api.crossref.org/works/10.1080/14786445008521796 | Crossref: Shannon 1950 | 2026-10-23 | Shannon citation (41(314):256-275, March 1950) |
| https://api.crossref.org/works/10.1016/0004-3702(75)90019-3 | Crossref: Knuth & Moore 1975 | 2026-10-23 | Citation (AI 6(4):293-326) |
| https://api.crossref.org/works/10.1016/S0004-3702(01)00129-1 | Crossref: Deep Blue 2002 | 2026-10-23 | Citation (AI 134(1-2):57-83) |
| https://api.crossref.org/works/10.1109/34.42858 | Crossref: Schaeffer 1989 | 2026-10-23 | Citation (IEEE PAMI 11(11):1203-1212) |
| https://api.crossref.org/works/10.1016/0004-3702(90)90073-9 | Crossref: Singular extensions 1990 | 2026-10-23 | Citation (AI 43(1):99-109) |
| https://api.crossref.org/works/10.1023/A:1007634325138 | Crossref: Baxter et al., Machine Learning 2000 | 2026-10-23 | Vol/pages/year; record has no title (title UNVERIFIED) |
| https://api.crossref.org/works/10.1126/science.aar6404 | Crossref: AlphaZero, Science 2018 | 2026-10-23 | Citation (362(6419):1140-1144) |
| https://api.crossref.org/works/10.1038/s41586-020-03051-4 | Crossref: MuZero, Nature 2020 | 2026-10-23 | Citation (588(7839):604-609) |
| https://api.crossref.org/works/10.1214/aoms/1177731118 | Crossref: Wald 1945 | 2026-10-23 | Citation (16(2):117-186) |
| https://api.crossref.org/works/10.1109/9.119632 | Crossref: Spall 1992 | 2026-10-23 | Citation (IEEE TAC 37(3):332-341) |
| https://api.crossref.org/works/10.1007/978-3-642-31866-5_13 | Crossref: CLOP | 2026-10-23 | Citation (Advances in Computer Games, LNCS, 2012, pp 146-157) |
| https://api.crossref.org/works/10.3233/icg-1995-18202 | Crossref: Buro ProbCut | 2026-10-23 | Citation (ICCA J 18(2):71-76) |
| https://api.crossref.org/works?query.bibliographic=...&query.container-title=ICGA+Journal | Crossref searches limited to ICGA Journal | 2026-10-23 | Records for Reinefeld 1983 (6(4):4-14), Donninger 1993 (16(3):137-143), Heinz 1998 (21(2):75-83), Heinz 1999 (22(3):123-132), Nalimov et al. 2000 (23(3):148-162), Thompson 1986 (9(3):131-139), Zobrist reprint 1990 (13(2):69-73), Hyatt DTS 1997 (20(1):3-19) |
| https://api.crossref.org/works?query.bibliographic=CHESS+4.5+Northwestern+... | Crossref search | 2026-10-23 | Slate & Atkin chapter records (1977 pp 82-118; 1988 reprint pp 80-103) |
| https://api.crossref.org/works?...&filter=prefix:10.3233 | Crossref searches with a wrong filter | 2026-10-23 | FAILED (irrelevant hits or empty responses); redone as above |
| https://export.arxiv.org/api/query?id_list=1509.01549,1712.01815,1911.08265,cs/9901001,cs/9901002 | arXiv API records | 2026-10-23 | Giraffe, AlphaZero preprint, MuZero preprint, TDLeaf and KnightCap (titles, authors, dates, journal refs) |
| http://export.arxiv.org/api/query?... | arXiv API over HTTP | 2026-10-23 | FAILED (empty); retried over HTTPS |
| https://www.sciencedirect.com/science/article/pii/0004370275900193 | ScienceDirect, Knuth & Moore | 2026-10-23 | FAILED (HTTP 403); Crossref used |
| https://www.sciencedirect.com/science/article/pii/S0004370201001291 | ScienceDirect, Deep Blue | 2026-10-23 | FAILED (HTTP 403); Crossref used |
| https://link.springer.com/article/10.1023/A:1007634325138 | Springer, Baxter et al. 2000 | 2026-10-23 | FAILED (redirect to login) |
| https://www.science.org/doi/10.1126/science.aar6404 | Science, AlphaZero | 2026-10-23 | FAILED (HTTP 403) |
| https://doi.org/10.1038/s41586-020-03051-4 | Nature, MuZero | 2026-10-23 | Reachability only (HTTP 200) |
| https://projecteuclid.org/journals/annals-of-mathematical-statistics/volume-16/issue-2/Sequential-Tests-of-Statistical-Hypotheses/10.1214/aoms/1177731118.full | Project Euclid, Wald 1945 | 2026-10-23 | FAILED (empty page) |
| https://dblp.org/search/publ/api?... | dblp search API | 2026-10-23 | FAILED (HTTP 429 rate limit) |
| https://api.semanticscholar.org/graph/v1/paper/search?... | Semantic Scholar API | 2026-10-23 | FAILED (HTTP 429) |
| https://www.chessprogramming.org/Claude_Shannon | CPW | 2026-10-23 | CHM scan link; no journal details on page |
| https://www.computerhistory.org/chess/doc-431614f453dde/ | Computer History Museum record | 2026-10-23 | Shannon scan; Philosophical Magazine, March 1950 |
| https://www.chessprogramming.org/Albert_Zobrist | CPW | 2026-10-23 | TR88 and ICCA 1990 reprint |
| https://minds.wisc.edu/items/992e8337-5597-4a51-89d3-3fbe3559201a | UW-Madison MINDS record (reached via minds.wisconsin.edu/handle/1793/57624) | 2026-10-23 | Zobrist TR88 title, year, abstract |
| https://research.cs.wisc.edu/techreports/1970/TR88.pdf | Zobrist TR88 PDF | 2026-10-23 | Exists (image-only scan, not readable) |
| https://www.chessprogramming.org/David_Slate | CPW | 2026-10-23 | Slate & Atkin listing (no pages); Crossref used |
| https://www.chessprogramming.org/NegaScout | CPW | 2026-10-23 | Reinefeld citation, Breuker note on errors |
| http://www.top-5000.nl/ps/An%20improvement%20to%20the%20scout%20tree%20search%20algorithm.pdf | Reinefeld PDF link from CPW | 2026-10-23 | FAILED (returned HTML, not the PDF) |
| https://www.chessprogramming.org/Chrilly_Donninger | CPW | 2026-10-23 | Donninger full title |
| https://www.chessprogramming.org/Ernst_A._Heinz | CPW | 2026-10-23 | Heinz 1998/1999 and Nalimov et al. listings and links |
| https://people.csail.mit.edu/heinz/dt/node18.html | Heinz web preprint, Extended Futility Pruning | 2026-10-23 | Confirms ICCA J 21(2):75-83, June 1998; section structure |
| https://centaur.reading.ac.uk/4562/ | Univ. of Reading repository, Nalimov et al. | 2026-10-23 | FAILED (Anubis bot wall) |
| https://www.chessprogramming.org/ProbCut | CPW | 2026-10-23 | Buro listing, author PDF link |
| https://skatgame.net/mburo/ps/probcut.pdf | Buro's PDF | 2026-10-23 | Exists (HTTP 200 PDF); text not extractable |
| https://www.chessprogramming.org/Dynamic_Tree_Splitting | CPW | 2026-10-23 | Hyatt 1994 (no venue) and 1997 ICCA listings |
| http://www.craftychess.com/hyatt/search.html | Hyatt's DTS page | 2026-10-23 | FAILED (expired TLS certificate) |
| https://www.chessprogramming.org/Lazy_SMP | CPW | 2026-10-23 | Lazy SMP history, forum post list, thesis listing, no peer-reviewed paper |
| https://talkchess.com/viewtopic.php?t=46858 | TalkChess, Daniel Homan "Lazy SMP, part 2" (2013-01-12) | 2026-10-23 | Primary forum source; Elo and time-to-depth figures |
| https://www.duo.uio.no/handle/10852/53769 (also hdl.handle.net/10852/53769 and the bitstream PDF link) | Ostensen 2016 thesis | 2026-10-23 | FAILED (redirects to nva.sikt.no, not read) |
| https://www.chessprogramming.org/Ken_Thompson | CPW | 2026-10-23 | Thompson 1986 listing, PDF link |
| https://pdos.csail.mit.edu/~rsc/thompson86endgame.pdf | Thompson 1986 PDF | 2026-10-23 | Reachability (HTTP 200 PDF) |
| https://swtch.com/~rsc/thompson86endgame.pdf | alternate URL tried | 2026-10-23 | FAILED (404) |
| https://www.chessprogramming.org/NNUE | CPW | 2026-10-23 | Nasu 2018 listing, PDF and translation links |
| https://www.apply.computer-shogi.org/wcsc28/appeal/the_end_of_genesis_T.N.K.evolution_turbo_type_D/nnue.pdf | Nasu 2018 original PDF (read locally with pdftotext) | 2026-10-23 | English title, author, affiliation, date 2018-04-28, abstract, WCSC28 appeal context |
| https://github.com/ynasu87/nnue | Nasu's repo | 2026-10-23 | GPLv3 (YaneuraOu fork); README wording of the Japanese title |
| https://github.com/asdfjkl/nnue | English translation repo | 2026-10-23 | Translation exists; translator and license not stated |
| https://github.com/asdfjkl/nnue/raw/main/nnue_en.pdf | translation PDF | 2026-10-23 | Reachability only |
| https://api.github.com/repos/syzygy1/tb (+ /contents); https://raw.githubusercontent.com/syzygy1/tb/master/README.md | Syzygy generator repo | 2026-10-23 | GPL-2.0; rtbw/rtbz roles; sizes; -p DTZ note |
| https://api.github.com/repos/syzygy1/probetool (+ /contents); https://raw.githubusercontent.com/syzygy1/probetool/master/README.md | Syzygy probing code repo | 2026-10-23 | Permissive "do whatever you want" license statement |
| https://www.remi-coulom.fr/CLOP/ | CLOP page | 2026-10-23 | Paper/software links, version 0.0.9, no license stated |
| https://www.remi-coulom.fr/CLOP/CLOP.pdf | CLOP paper PDF | 2026-10-23 | Title, author, abstract |
| https://www.remi-coulom.fr/Bayesian-Elo/ | BayesElo page | 2026-10-23 | MM method, draw/advantage model, GPL, 2010.03.31, Hunter citation |
| https://www.jhuapl.edu/spsa/ | Spall's SPSA site | 2026-10-23 | Maintainer, link to Spall_TAC92.pdf, gain-tuning note |
| https://www.jhuapl.edu/spsa/PDF-SPSA/Spall_TAC92.pdf | Spall 1992 PDF | 2026-10-23 | Reachability (HTTP 200 PDF) |
| https://github.com/official-stockfish/fishtest/wiki | Fishtest wiki index | 2026-10-23 | Locating the mathematics page |
| https://github.com/official-stockfish/fishtest/wiki/Fishtest-Mathematics | Fishtest Mathematics | 2026-10-23 | GSPRT, pentanomial, normalized Elo, PDF links |
| https://www.cantate.be/Fishtest/normalized_elo_practical.pdf | Van den Bergh, "Comments on Normalized Elo" | 2026-10-23 | Author; definition of normalized Elo |
| https://github.com/AndyGrant/OpenBench/wiki | OpenBench wiki index | 2026-10-23 | Locating the SPRT page |
| https://github.com/AndyGrant/OpenBench/wiki/SPRT-and-Fixed%E2%80%90Game-Workloads | OpenBench SPRT page | 2026-10-23 | Bounds, Confidence, game pairs |
| https://api.github.com/repos/AndyGrant/OpenBench/git/trees/master?recursive=1; https://raw.githubusercontent.com/AndyGrant/OpenBench/master/OpenBench/stats.py | OpenBench tree and stats.py | 2026-10-23 | Pentanomial SPRT taken from Fishtest; GPL-3.0 header |

## Competition update: TCEC Swiss, adjudication re-verification, Reckless (competition.md, config/tcec.json)

All opened on 2026-10-23 with curl (browser User-Agent) or the GitHub REST API; HTML stripped locally. "Archive JSON" means files under https://tcec-chess.com/archive/json/ (path found in the site's own script).

| URL | What it is | Date checked | Used for |
|---|---|---|---|
| https://wiki.chessdom.org/TCEC_Swiss_rules | Swiss rules (edited 22 Dec 2025) | 2026-10-23 | Swiss format, game pairs, tiebreaks, TC, draw rule, outage rules, updates |
| https://wiki.chessdom.org/index.php?title=TCEC_Swiss_rules&type=revision&diff=8076&oldid=7923 | Revision diff (TD amendment) | 2026-10-23 | 12→11 rounds change (21 Nov 2025); "winner" added to points-only tiebreak rule (22 Dec 2025) |
| https://wiki.chessdom.org/TCEC_Swiss_10 | S30 Swiss 10 page (edited 22 Oct 2026) | 2026-10-23 | 13 double rounds, 48 engines, categories, Cat 3+4 playoff format, seeding groups, promotion, time margin note |
| https://wiki.chessdom.org/TCEC_Swiss_Tournament_System | Swiss pairing system (edited 15 Jun 2023) | 2026-10-23 | Pairing order, Blossom viability check, colours, seeding, byes |
| https://wiki.chessdom.org/Rules | All-events rules (edited 8 Jul 2026) | 2026-10-23 | Draw rule and win conditions in every section; 4k has no draw rule; outage wording |
| https://wiki.chessdom.org/TCEC_Leagues_Season_Rules | Leagues rules (edited 21 Jul 2025) | 2026-10-23 | Draw rule, win conditions, outage rules |
| https://wiki.chessdom.org/TCEC_Season_Further_information | Hardware/settings (edited 24 Feb 2026) | 2026-10-23 | Re-check: 7-men Syzygy for all divisions, no TB adjudication text |
| https://wiki.chessdom.org/TCEC_Season_20_Rules | S20 rules (edited 18 Jan 2021) | 2026-10-23 | Win rule dropped from S20 onward; 6-man TB adjudication; move-35 ±0.15 draw rule |
| https://wiki.chessdom.org/TCEC_Season_19_Rules | S19 rules (edited 3 Sep 2020) | 2026-10-23 | ±10.00 / 10-ply win rule still present |
| https://wiki.chessdom.org/TCEC_Season_18_Rules | S18 rules (edited 29 May 2020) | 2026-10-23 | ±10.00 win rule, ±0.15 draw rule |
| https://wiki.chessdom.org/TCEC_Season_17_Rules | S17 rules (edited 17 Mar 2020) | 2026-10-23 | ±10.00 win rule, ±0.08 draw rule (matches the brief) |
| https://wiki.chessdom.org/TCEC_Season_21_Rules | — | 2026-10-23 | FAILED (404; no per-season rule pages after S20) |
| https://wiki.chessdom.org/Category:Rules | Wiki category | 2026-10-23 | List of rule pages (season pages stop at S20) |
| https://wiki.chessdom.org/index.php?search=win+rule&fulltext=1&limit=50 and ?search=%22win+adjudication%22... | Wiki searches | 2026-10-23 | Locating win-rule pages only |
| https://wiki.chessdom.org/index.php?title=TCEC_Leagues_Season_Rules&action=history&limit=500 | Revision history | 2026-10-23 | Revision dates |
| https://wiki.chessdom.org/index.php?title=TCEC_Leagues_Season_Rules&oldid=N&action=raw for N = 1970, 3268, 3614, 3615, 3663, 3693, 3712, 3713, 3759, 3860, 4383, 4701, 5306, 5381, 6018, 6876 | Old revisions (wikitext) | 2026-10-23 | Draw-rule history; TB adjudication removed between 6018 (13 Oct 2024) and 6876 (4 May 2025) |
| https://wiki.chessdom.org/TCEC_Leagues_Season_29 | S29 Leagues overview | 2026-10-23 | Questionnaire mandatory from S29 (no Superfinal result on page) |
| https://wiki.chessdom.org/TCEC_Leagues_Season_28 | S28 Leagues overview | 2026-10-23 | Nothing on Reckless's League 2 placement |
| https://wiki.chessdom.org/TCEC_Swiss_8 | S28 Swiss 8 page | 2026-10-23 | Reckless as Cat 2 entrant, testing time losses |
| https://wiki.chessdom.org/TCEC_Swiss_7 | S27 Swiss 7 page | 2026-10-23 | Reckless 0.7.0 conditional entry, Cat 0+2 playoff format |
| https://wiki.chessdom.org/Reckless | — | 2026-10-23 | FAILED (404) |
| https://wiki.chessdom.org/index.php?search=Reckless+questionnaire&fulltext=1&limit=50; ?search=Reckless+%22League+2%22+%22Season+28%22... | Wiki searches | 2026-10-23 | Finding the questionnaire page; S28 placement (not found) |
| https://wiki.chessdom.org/Reckless_questionnaire_20251024 | Reckless questionnaire (v2.3) | 2026-10-23 | Confidential, no content |
| https://tcec-chess.com/ | TCEC site HTML/JS | 2026-10-23 | Archive JSON path (`archive/json`) only |
| https://tcec-chess.com/tournament.json | Current event | 2026-10-23 | season30, div sw |
| https://tcec-chess.com/live.json | Live game | 2026-10-23 | Swiss 10 round 9.42, 1800+3, engine options (Threads 512, Hash 262144, SyzygyPath, MoveOverhead) |
| https://tcec-chess.com/crosstable.json | Swiss 10 crosstable | 2026-10-23 | 48 engines, Reckless 8th after 17 games |
| https://tcec-chess.com/schedule.json | Swiss 10 schedule | 2026-10-23 | 624 games, game pairs, terminations (212 decisive all by mate, 129 with ≤6 men; 169 TCEC draw rule) |
| https://tcec-chess.com/gamelist.json | Event index for all seasons | 2026-10-23 | S30 divisions incl. Cat 3+4 playoff; S22-S30 division names |
| https://tcec-chess.com/bayeselo.txt | TCEC rating list | 2026-10-23 | Fetched only; not used |
| https://tcec-chess.com/archive.json | — | 2026-10-23 | FAILED (404) |
| https://tcec-chess.com/json/TCEC_Season_30_-_Category_3+4_Playoff_Crosstable.cjson (and %2B and _Schedule variants) | — | 2026-10-23 | FAILED (404; wrong path) |
| https://tcec-chess.com/archive/json/TCEC_Season_30_-_Category_3%2B4_Playoff_Crosstable.cjson and _Schedule.sjson | Archive JSON | 2026-10-23 | Cat 3+4 result (Cinder 31.5, CatGPT 27, Serendipity 13.5 of 48), 72 games, 9-12 Sep 2026 |
| https://tcec-chess.com/archive/json/TCEC_Season_29_-_Superfinal_Crosstable.cjson and _Schedule.sjson | Archive JSON | 2026-10-23 | S29 Superfinal Stockfish 59 - Reckless 41, dates |
| https://tcec-chess.com/archive/json/TCEC_Season_29_-_Swiss_9_Crosstable.cjson | Archive JSON | 2026-10-23 | Reckless 8th of 44 |
| https://tcec-chess.com/archive/json/{event}_Crosstable.cjson for the 247 non-testing S22-S30 and Cup 10-16 events listed in gamelist.json | Archive JSON | 2026-10-23 | Reckless results per event (S27-S30). All Cup files FAILED (404; Cup brackets use another format) |
| https://tcec-chess.com/archive/json/TCEC_Cup_16_event.json, TCEC_Cup_15/16_Eventcrosstable.cjson | — | 2026-10-23 | FAILED (404); Cup results UNVERIFIED |
| https://www.chessdom.com/tcec-announces-ai-integration-plans-as-a-new-generation-of-engines-enters-the-arena/ | TD statement (31 Aug 2026) | 2026-10-23 | AI engines: Swiss only via Cat 3+4 playoff, not Leagues, extra gauntlet |
| https://www.chessdom.com/?s=Reckless | Chessdom search | 2026-10-23 | Finding articles only |
| https://www.chessdom.com/reckless-breaks-a-duopoly-in-a-historic-computer-chess-shake-up/ | Chessdom (23 Mar 2026) | 2026-10-23 | S29 Premier final standings, first TCEC application Aug 2024, Swiss 8 22nd, Swiss 9 8th |
| https://www.chessdom.com/stockfish-claims-its-19th-tcec-title-defeating-reckless-in-the-superfinal/ | Chessdom (21 Apr 2026) | 2026-10-23 | S29 Superfinal 59-41; S20 dates (Dec 2020-Feb 2021), S27/S28 dates |
| https://www.chessdom.com/when-code-meets-class-stockfish-and-reckless-agree-to-restart-tcec-superfinal-in-spirit-of-fair-play/ | Chessdom (27 Mar 2026) | 2026-10-23 | Superfinal restart, compiler speed issue |
| https://www.chessdom.com/interview-with-arseniy-surkov-author-of-reckless/ | Chessdom interview (27 Mar 2026) | 2026-10-23 | Team, contributors, Kaggle origin, Stockfish-search study |
| https://api.github.com/repos/codedeliveryservice/Reckless | GitHub API repo | 2026-10-23 | Created 31 Dec 2022, AGPL-3.0, Rust, last push |
| https://api.github.com/repos/codedeliveryservice/Reckless/releases?per_page=100 | GitHub API releases | 2026-10-23 | Release dates and notes (v0.1.0-v0.10.0-dev) |
| https://api.github.com/repos/codedeliveryservice/Reckless/commits?per_page=1 (and repositories/583888641/commits?page=1809) | GitHub API commits | 2026-10-23 | ~1,809 commits; first commit 3 Dec 2022 |
| https://api.github.com/repos/codedeliveryservice/Reckless/contributors | GitHub API contributors | 2026-10-23 | Commit counts per author |
| https://raw.githubusercontent.com/codedeliveryservice/Reckless/main/README.md | README | 2026-10-23 | CCRL rating table per release, OpenBench/bullet acknowledgements, UCI options |
| https://raw.githubusercontent.com/codedeliveryservice/Reckless/v0.7.0/LICENSE | Licence at v0.7.0 | 2026-10-23 | MIT |
| https://raw.githubusercontent.com/codedeliveryservice/Reckless/v0.8.0/LICENSE | — | 2026-10-23 | FAILED (404); tree confirms no LICENSE in v0.8.0 |
| https://api.github.com/repos/codedeliveryservice/Reckless/git/trees/v0.8.0 and /git/trees/main?recursive=1 | GitHub API trees | 2026-10-23 | File lists (licence, workflows); no source read |
| https://raw.githubusercontent.com/codedeliveryservice/Reckless/main/Makefile and /build/build.rs | Build files (grep for URLs only) | 2026-10-23 | Net download location (RecklessNetworks) |
| https://api.github.com/repos/codedeliveryservice/RecklessNetworks (+ /releases); raw .../main/README.md | Network storage repo | 2026-10-23 | No licence, no data provenance stated |
| https://api.github.com/search/issues?q=repo:codedeliveryservice/Reckless+{leela,lc0,training+data,datagen} | GitHub issue search | 2026-10-23 | Looking for data provenance |
| https://api.github.com/repos/codedeliveryservice/Reckless/issues/74, /987, /881 | PR #74, issues #987, #881 | 2026-10-23 | PR #74: dataset regenerated with Reckless itself (Oct 2024); others not relevant |
| https://recklesschess.space/ and /users/ | Reckless OpenBench instance | 2026-10-23 | Confirms it is an OpenBench instance |

## Competition update 2: tablebase access and Swiss categories 3/4 (competition.md, config/tcec.json)

| URL | What it is | Date checked | Used for |
|---|---|---|---|
| https://wiki.chessdom.org/index.php?title=TCEC_Season_Further_information&action=raw | Further information page (rev 8475) | 2026-10-23 | TB wording (6-man Scorpio, 7-man Syzygy, madvise), storage (NVMe Syzygy3-7, HDD Syzygy7 DTZ), compilers |
| https://wiki.chessdom.org/api.php?action=query&prop=revisions&titles=TCEC_Season_Further_information | Revision list | 2026-10-23 | Dating the TB wording (rev 6470/6471, Mar 2025) |
| https://wiki.chessdom.org/index.php?oldid={2470,3788,6470,6471}&action=raw | Old revisions of the Further information page | 2026-10-23 | TB wording history (5-man Scorpio/6-man Syzygy before Mar 2025) |
| https://tcec-chess.com/live.json | Live game | 2026-10-23 | Engine options (Pawnocchio vs PlentyChess, Swiss 10 round 9.43): SyzygyPath=/home/syzygy7, no other TB option |
| https://tcec-chess.com/tournament.json | Current event | 2026-10-23 | season30, div sw |
| https://tcec-chess.com/crosstable.json, https://tcec-chess.com/schedule.json | Swiss 10 crosstable and schedule | 2026-10-23 | Swiss 10 entrants (no Scorpio engine) |
| https://tcec-chess.com/gamelist.json | Event index | 2026-10-23 | S29/S30 event names |
| https://tcec-chess.com/ | GUI HTML/JS | 2026-10-23 | Archive game URL pattern `archive/json/<event>_<game>.pgn` |
| https://tcec-chess.com/archive/json/<event>_Crosstable.cjson for 98 S29/S30/Cup 16 events | Archive crosstables | 2026-10-23 | 79 loaded, 8 FAILED (HTML 404 page) + testing events; no ScorpioNN entrant |
| https://tcec-chess.com/archive/json/<event>_1.pgn for non-testing S29/S30/Cup 16 events | Archived games (PGN with engine options) | 2026-10-23 | 57 parsed: SyzygyPath values (/home/syzygy7, /home/syzygy6, /home/syzygy7_no_dtz); no Scorpio/egbb option |
| https://tcec-chess.com/archive/json/TCEC_Season_30_-_Category_3+4_Playoff_{2,3,4}.pgn | Cat 3+4 playoff games | 2026-10-23 | CatGPT/Cinder/Serendipity options |
| https://tcec-chess.com/archive/json/TCEC_Season_28_-_Swiss_8_Schedule.sjson and TCEC_Season_28_-_Swiss_8_7.pgn | Swiss 8 schedule, ScorpioNN game | 2026-10-23 | ScorpioNN options (Protocol only) |
| https://wiki.chessdom.org/index.php?title=TCEC_Swiss_10&action=raw | Swiss 10 page | 2026-10-23 | Regulations, Cat 3/4 rules, deadline, appeal, categorisation final date |
| https://wiki.chessdom.org/api.php?action=query&prop=revisions&titles=TCEC_Swiss_10 | Swiss 10 revision list (233 revisions) | 2026-10-23 | Dates: Cat 4 added (9185, 21 Jun 2026), invites sent, definitions added (9411) |
| https://wiki.chessdom.org/index.php?oldid={9159,9185,9410,9411}&action=raw | Swiss 10 revisions | 2026-10-23 | Cat 4 pre-playoff wording ("at least 1 DRR as needed"), x/y/z changes |
| https://wiki.chessdom.org/images/f/f8/TCEC_playoff_categorizing.png (+ api imageinfo) | Categorisation flowchart (8 Apr 2025) | 2026-10-23 | Category 1-3 definitions |
| https://wiki.chessdom.org/images/2/22/TCEC_S30%2B_cats_flowchart.png | S30 season flowchart v1 (18 Jun 2026) | 2026-10-23 | Category labels, category promotion via Leagues |
| https://wiki.chessdom.org/index.php?title=TCEC_Swiss_9&action=raw | Swiss 9 page | 2026-10-23 | S29 category scheme (1a/1b/2/3, Cat 4 = cannot feature) |
| https://wiki.chessdom.org/index.php?title={TCEC_Swiss_rules,Rules,TCEC_Leagues_Season_Rules}&action=raw | Rule pages | 2026-10-23 | No category or TB-access text |
| https://wiki.chessdom.org/index.php?title=Main_Page&action=raw | Wiki main page | 2026-10-23 | Application by questionnaire; S31 events listed as upcoming |
| https://wiki.chessdom.org/index.php?title=Current_Engine_Status&action=raw | Engine status page | 2026-10-23 | Per-engine categories (e.g. Quanticade cat 3) |
| https://wiki.chessdom.org/index.php?title=TCEC_Questionnaire&action=raw | Questionnaire v2.4 | 2026-10-23 | Submission by email |
| https://wiki.chessdom.org/index.php?title=CatGPT_questionnaire_20260525&action=raw | CatGPT questionnaire | 2026-10-23 | Cat 4 precedent (AI-generated code, PolyForm NC license, Leela data) |
| https://wiki.chessdom.org/index.php?title=Cinder_questionnaire_20260619&action=raw | Cinder questionnaire | 2026-10-23 | Cat 3 precedent (Stockfish/Lc0 data) |
| https://wiki.chessdom.org/index.php?title={TCEC_Swiss_11,TCEC_Season_31,TCEC_Leagues_Season_30,TCEC_Leagues_Season_31,TCEC_Cup_17,TCEC_AI_Gauntlet}&action=raw | — | 2026-10-23 | FAILED (404, pages not created): S31 and AI gauntlet unpublished |
| https://wiki.chessdom.org/index.php?title={TCEC_Cup_8_rules,TCEC_Swiss_8,TCEC_Season_20_Further_information,TCEC_Cup_10,TCEC_Season_16_Rules}&action=raw | Older pages found by wiki search "Scorpio" | 2026-10-23 | Scorpio history only |
| https://wiki.chessdom.org/api.php?action=query&list=search (Scorpio, DTZ, no_dtz, syzygy7, bitbases) and index.php?search=... | Wiki search | 2026-10-23 | API search returned 0 hits (index unreliable); HTML full-text search for "Scorpio" gave the page list above |
| https://www.chessdom.com/tcec-announces-ai-integration-plans-as-a-new-generation-of-engines-enters-the-arena/ | TD statement (31 Aug 2026) | 2026-10-23 | AI engines: Swiss via Cat 3+4 playoff, no Leagues, extra gauntlet |
| https://www.chessdom.com/?s={AI+gauntlet,TCEC+Season+31,CatGPT,TCEC+AI} | Chessdom search | 2026-10-23 | No results parsed |
| https://www.chessdom.com/tag/tcec/feed/ | Chessdom TCEC tag feed | 2026-10-23 | Latest TCEC article is the 31 Aug 2026 statement; no gauntlet/S31 news |
