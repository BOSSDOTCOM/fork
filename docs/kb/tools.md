# Tools knowledge base

Tools for testing, rating, tuning, training and profiling Fork. Each entry was checked
on 2026-10-23 against the primary sources listed in [_sources-tools.md](_sources-tools.md).
Pinned versions are in [`tools/versions.lock`](../../tools/versions.lock).
[`tools/install.sh`](../../tools/install.sh) installs the core set on WSL2 Ubuntu.

**`tools/install.sh` has not been tested.** WSL is not installed on the development machine
yet, so the script was only syntax-checked (`bash -n`). Expect to fix something on its first real run.

## Tags

| Tag | Meaning |
|---|---|
| **USE** | Fork's workflow can use it: an external program, a permissive library, or data that does not come from another engine. |
| **REFERENCE ONLY** | Read it for ideas and write Fork's own version. Copy no code. Usually GPL code, unlicensed code, or Stockfish-org tooling. |
| **OFF-LIMITS** | Do not use. This covers Stockfish (or other engine) code, nets, and engine-generated training data. |

Licence rule of thumb: running a GPL program **as a separate tool** (match runner, rating
calculator, profiler) puts no licence terms on Fork's source. Linking GPL code into the engine
or copying it would. TCEC's originality rule is stricter than any licence. Even permissively
licensed *engine* code is not copied. The only exception is a documented library such as Fathom.

---

## 1. Match runners

### fastchess
- **Tag:** USE (the primary match runner)
- **License:** MIT (LICENSE file; the man page says the same). Building with `ZLIB=true` pulls in gzstream, which is LGPL. The default build leaves it out.
- **Version:** v1.8.2-alpha, released 2026-07-26. The project marks every release "-alpha", and this is the latest. Tag commit `f618e345`. master was last pushed 2026-10-11.
- **What:** a C++17 command-line tournament manager for UCI engines. Fishtest and OpenBench use it as their game runner.
- **Why it matters for Fork:** Fork's local SPRT tests, TCEC-condition matches (Phase 8) and the UCI compliance gate.
- **TCEC-relevant features** (from `man.md` at the pinned tag):
  - **Paired openings:** `-repeat` (the same as `-games 2`) plays each opening with both colours. `-rounds N` sets the number of pairs. `-noswap` and `-reverse` also exist.
  - **Books:** `-openings file=F format=epd|pgn order=sequential|random plies=N start=N`, plus `-srand` for the shuffle seed.
  - **Adjudication:**
    - `-draw movenumber=N movecount=N score=CP`.
    - `-resign movecount=N score=CP twosided=true|false`.
    - `-maxmoves N`.
    - `-tb PATHS` (colon-separated on Linux, WDL files only) with `-tbpieces N`, `-tbignore50` and `-tbadjudicate BOTH|WIN_LOSS|DRAW`.
  - **Concurrency:** `-concurrency N` is capped at the hardware thread count unless `-force-concurrency` is given. `-use-affinity` pins engines to CPUs.
  - **SPRT built in:** `-sprt elo0= elo1= alpha= beta= model=normalized|logistic|bayesian`. normalized (nElo) is the default. A pentanomial report is on by default (`-report penta=true`).
  - **Other:**
    - `-pgnout` can record nodes, seldepth, nps, hashfull, tbhits, pv, time left and latency.
    - `-epdout`.
    - `-recover` restarts crashed engines.
    - `-config` resumes a match. Autosave runs every 20 games by default.
    - `-check-mate-pvs` checks that mate PVs have the right length.
    - `-show-latency`.
    - `-strict` turns warnings into exit code 1.
    - `-log ... engine=true` writes the engine I/O log.
    - Timeouts: `-startup-ms`, `-ucinewgame-ms`, `-ping-ms`.
    - `-variant fischerandom` covers TCEC's FRC events.
  - Only the UCI protocol is supported.
- **`--compliance` UCI checker.** Invoke it as `fastchess --compliance ./fork [ARGS]`. It runs the engine through a fixed script and stops at the first failing step. On a failure it prints the engine's stdout and stderr. At the pinned tag (`app/src/engine/compliance.hpp`) it checks these things:
  - The engine starts and answers `isready`.
  - It sends `id name` and `id author`.
  - It accepts `ucinewgame`, `position startpos`, `position fen ...` (white to move and black to move) and `position startpos moves e2e4 e7e5`. It answers `isready` after each one.
  - It returns `bestmove` for these searches: `go wtime 100`, `go btime 100`, `go wtime 100 winc 100 btime 100 binc 100` (and the same with the arguments in the other order), and `go wtime 100 btime 100`.
  - After each search, the last `info` line must exist, must contain `score`, and must parse. Values after `time`, `nps` and `score` must be integers.
  - **It does NOT check** `setoption`, `go depth/nodes/movetime/infinite`, `stop`, ponder, `quit`, MultiPV, mate-score output or `UCI_Chess960`. Fork needs its own tests for those (Phase 2 UCI tests).
  - Make passing it a gate for every release build.
- **Install:** `make -j`, then `make install PREFIX=...`. Alternatively, use a prebuilt `fastchess-linux-x86-64.tar` (its sha256 is in versions.lock).
- **Source:** https://github.com/Disservin/fastchess. Verified 2026-10-23.

### cutechess-cli (Cute Chess)
- **Tag:** USE (a second runner, for cross-checking fastchess and for tools that need it, such as chess-tuning-tools)
- **License:** GPLv3+, except `projects/*/components`, which are MIT (README). The API reports GPL-3.0.
- **Version:** v1.5.1, released 2026-06-14. Tag commit `45e92394` (annotated tag). Release assets are a Windows exe/zip and a Linux AppImage.
- **What:** a Qt-based GUI, CLI and library. `cutechess-cli` runs engine tournaments and speaks both UCI and xboard.
- **Building (important):**
  - The README requires **Qt 6.8 or newer**, a C++17 compiler and cmake. The Qt modules needed are widgets, svg, concurrent, printsupport and qt5-compat.
  - There is **no CLI-only build option**. `CMakeLists.txt` asks for all the Qt components (Core, Gui, Widgets, Concurrent, Svg, PrintSupport, Core5Compat) and only offers `WITH_TESTS`.
  - You can still build only the CLI target: `cmake -S . -B build -DWITH_TESTS=OFF && cmake --build build --target cli`. The CLI links only Qt Core and Core5Compat, but configuring still needs the Qt development packages.
  - The wiki's apt list is `build-essential cmake qt6-base-dev qt6-svg-dev qt6-base-dev-tools qt6-5compat-dev`.
  - **UNVERIFIED:** which Ubuntu release ships Qt ≥ 6.8 (packages.ubuntu.com and Launchpad were unreachable). install.sh checks the Qt version at runtime. If Qt is too old, it falls back to extracting the AppImage. **UNVERIFIED** whether the AppImage contains `cutechess-cli`; the script searches for it and fails cleanly if it is missing.
- **TCEC-relevant features** (man page `docs/cutechess-cli.6` at the tag):
  - Paired openings: `-repeat [n]` plus `-games`/`-rounds`, with `-noswap` and `-reverse`.
  - Books: `-openings file= format=epd|pgn order= plies= start= policy=default|encounter|round`, and Polyglot books via `-bookmode`.
  - Adjudication:
    - `-draw movenumber= movecount= score=`. Captures and pawn moves reset the counters.
    - `-resign movecount= score= [twosided=]`.
    - `-maxmoves`.
    - `-tb paths` (semicolon-delimited, WDL only) with `-tbpieces` and `-tbignore50`.
  - Concurrency and statistics: `-concurrency`, `-sprt elo0 elo1 alpha beta`, `-recover`, `-pgnout [min] [fi]` and `-epdout`.
  - Tournament types: round-robin, gauntlet, knockout and pyramid.
  - `-version` prints the version.
- **Source:** https://github.com/cutechess/cutechess. Verified 2026-10-23.
- **Installed 2026-10-23:** built from source at v1.5.1 against Qt 6.10.2,
  at `~/fork-tools/bin/cutechess-cli`.

### tcec-cutechess-cli (TCEC's cutechess fork)
- **Tag:** USE (compliance testing under the GUI TCEC runs)
- **Source:** https://github.com/TCEC-Chess/tceccutechess (GPLv3+, inherited
  from cutechess). Checked 2026-10-23 with `git ls-remote` and a clone.
- **Version:** no tags. 24 branches; the default branch `master` is the most
  recent (commit `a324a3e6`, 2023-04-09, "Update chessgame.cpp"). Other
  branches are older (`allow_uci_options` 2020-07, `Cup5` 2020-05,
  `nTCEC` 2018-09). Pinned by commit in versions.lock. **UNVERIFIED** that
  TCEC's servers run exactly this commit; the repository has had no pushes
  since April 2023.
- **Building:** qmake (`cutechess.pro`), rejects Qt < 5.7. It **fails against
  Qt 6.10** (QStringList forward declaration, QString += int, enum
  conversions), so install.sh builds it against Qt5 (`qtbase5-dev`, 5.15 on
  Ubuntu 26.04). The library and CLI need only QtCore. The library is shared
  (`libcutechess.so` in the source tree), so install.sh installs a wrapper,
  `tcec-cutechess-cli`, that sets `LD_LIBRARY_PATH`.
- **Why it matters:** it is TCEC's GUI code and differs from upstream
  cutechess; for example it bundles its own Fathom copy (`lib.pro` includes
  `3rdparty/fathom/src/tb.pri`). Fork's UCI behaviour should be checked under
  it, not only under upstream cutechess and fastchess. Which TCEC-specific
  changes `master` contains (branch names suggest JSON output, UCI option
  passing, Berger schedules): **UNVERIFIED**, not yet read.

**Mapping TCEC adjudication to runner flags (Phase 8).** `config/tcec.json` has draw from move 35, |eval| ≤ 8 cp for 10 plies by both engines, and a win at ≥ 1000 cp for 10 plies. Both runners count `movecount` in "consecutive moves". **UNVERIFIED** whether that means plies or full moves, and whether both engines' scores are tested in the way TCEC does it. Read the runner source before trusting a mapping such as `-draw movenumber=35 movecount=? score=8` and `-resign movecount=? score=1000 twosided=true`.

---

## 2. Distributed testing, SPRT and SPSA

### OpenBench
- **Tag:** USE (if Fork ever needs distributed testing or SPSA across machines)
- **License:** GPL-3.0 (GitHub license metadata).
- **Version:** no releases. master at commit `dd03aaff`, last pushed 2026-10-22.
- **What:** a Django web server plus Python clients for SPRT tests, fixed-game tests, SPSA tuning and data-generation workloads. The clients run fastchess. It is Ethereal's main testing framework, and its main public instance serves many other engines.
- **Private instance:** the wiki says to fork the repo first. The server needs Python ≥ 3.9 (the guide uses 3.10) and the packages in `requirements.txt`; clients need Python ≥ 3.6. Engines are configured in `Config/config.json`. The guide covers only local `runserver`, not production hosting.
- **SPSA (wiki):**
  - The input is one line per parameter: `name, int|float, value, min, max, C_end, R_end`.
  - Parameters must be UCI options. Floats must be exposed as `string` options, because UCI spin options cannot hold floats.
  - Suggested settings: R_end ≈ 0.002 and C_end ≈ 1/20 of the parameter's range.
  - Defaults: alpha 0.602, gamma 0.101, A-ratio 0.1.
  - Recommended mode: Batched reporting, Single distribution, 8 pairs per point.
- **Source:** https://github.com/AndyGrant/OpenBench and its wiki. Verified 2026-10-23.

### Fishtest
- **Tag:** REFERENCE ONLY. It is Stockfish's infrastructure, built around Stockfish. Studying its statistics is fine; Fork does not need to run it.
- **License:** the repo has no LICENSE file at its root and GitHub reports none. **UNVERIFIED.**
- **Version:** no releases. master at commit `5a8a229a`.
- **What:** a distributed task queue. Workers download fastchess, the book and the engine sources, play batches, and upload the results.
- **Source:** https://github.com/official-stockfish/fishtest. Verified 2026-10-23.

### SPRT calculators
- **fastchess `-sprt`** (above) is the SPRT that Fork will actually use. It offers normalized, logistic and bayesian Elo models and a pentanomial report.
- **cutechess-cli `-sprt`** is trinomial only. The CPW SPRT page recommends fastchess because it supports pentanomial statistics.
- **Fishtest SPRT calculator** (https://tests.stockfishchess.org/sprt_calc) is linked from the CPW SPRT page. **UNVERIFIED:** the page returned a bot-verification wall, so its inputs could not be read. It is a web tool, so using it to plan test bounds would carry no originality risk.
- I found no standalone, verified SPRT calculator repo. If Fork needs offline power estimates, it can write a small one from the published formulas.

### SPSA and tuning tools
| Tool | Tag | License | Version | Notes |
|---|---|---|---|---|
| OpenBench SPSA | USE | GPL-3.0 | master `dd03aaff` | See above. The best fit for distributed tuning. |
| weather-factory (jnlt3, formerly dsekercioglu) | USE | MIT | no releases. main `19b4805c`, last push 2024-12-23 | Local SPSA tuner. Uses fastchess or cutechess. Each parameter maps to a UCI spin option with value, min, max and step. The README calls it WIP. |
| chess-tuning-tools (kiudee) | USE | Apache-2.0 (LICENSE file; the API shows NOASSERTION) | v0.9.5, 2023-07-19 (PyPI and GitHub) | Bayesian optimisation with a pentanomial scoring model. Needs `cutechess-cli` on PATH. No release since 2023. |

---

## 3. Elo / rating calculators

### Ordo
- **Tag:** USE
- **License:** GPL-3.0 (`LICENSE.txt`; the README says "GPL").
- **Version:** v1.2.6. The tag commit `17eec774` is dated 2016-04-19. GitHub lists 1.2.x releases from 2016 as pre-releases. No commits since 2016 on master (the repo's last push was 2023-09-15). Treat it as finished, unmaintained software.
- **What:** computes ratings from a PGN file, fitting all results at once. Options include `-a` for the average, `-A` for an anchor and `-c` for CSV output, and it accepts multiple PGNs after `--`. Its own `make install` copies into `/usr/local/bin`, so install.sh copies the binary instead.
- **Maintained source:** https://github.com/michiguel/Ordo (by the author, Miguel Ballicora). CPW also links the older Google Sites page. Verified 2026-10-23.

### BayesElo
- **Tag:** USE
- **License:** GNU GPL according to the author's page. The page names no version number.
- **Version:** no version number. The newest history entry is 2010-03-31, a source fix for compiler warnings. Downloads are `bayeselo.tar.bz2` (source) and `bayeselo.exe`.
- **Maintained source:** only the author's page at https://www.remi-coulom.fr/Bayesian-Elo/. CPW's Match Statistics page links the older `remi.coulom.free.fr` address. I found no maintained repository. **UNVERIFIED:** checksums, and whether it builds with current compilers.
- **Note:** fastchess's `model=bayesian` SPRT uses the BayesElo model, so a separate binary is only needed for rating lists.

---

## 4. Opening books and test suites

Books are lists of starting positions, not engine code. They are used to schedule test games and never enter the engine binary or the training data. The care needed is about **provenance**: who evaluated the positions, and with which engine.

### Stockfish `books` repository
- **Tag:** USE for match testing. Do not use it to seed training-data generation (see below).
- **License:** CC0-1.0 (LICENSE file), a public-domain dedication with no conditions.
- **Version:** no releases. master at commit `a804a97e`, last pushed 2026-10-16.
- **Contents:** about 40 zipped books, listed in `books.json`. Examples:
  - `UHO_Lichess_4852_v1.epd`: 2,632,036 positions. The fastchess man page uses it as its SPRT example.
  - `UHO_4060_v1` to `v4`: 241,670–246,759 positions each.
  - UHO_XXL 2022 PGN sets.
  - `8moves_v3.pgn` (34,700), `2moves_v1.epd`, `noob_3moves.epd`.
  - FRC and DFRC opening sets (`FRC_openings.epd` has all 960).
- **Is using a book from the Stockfish org a problem?** For testing, no. TCEC's clone rule targets engine code, nets and training data, and CC0 removes any copyright question. Two cautions:
  1. Many of these books were selected using evaluations from Stockfish or other engines. **UNVERIFIED** exactly how each one was made. Do not use them as the starting positions for Fork's self-play data generation. Use random-move or Fork-generated openings there, so the training-data provenance stays purely Fork.
  2. Record which book and version each test used, in ORIGINALITY.md and the test logs.
- **Source:** https://github.com/official-stockfish/books. Verified 2026-10-23.

### UHO books from Stefan Pohl (SPCC)
- **Tag:** USE for testing (unbalanced books bring the draw rate close to TCEC conditions). Keep the files out of the repo.
- **License:** none stated. The page carries "(C) 2024 Stefan Pohl (SPCC)". Do not redistribute; download them yourself.
- **Version:** UHO 2024 (`./files/uho_2024.7z` on sp-cc.de). The page gives no exact release date.
- **How they were made** (from the page):
  - Source games: Megabase 2024, both players ≥ 2200, cut at 6 or 8 moves.
  - Evaluation: **KomodoDragon 3.3**, 10 s per position.
  - Sets are published in eval windows from +0.85..+0.94 up to +1.20..+1.29, in 6-move, 8-move and "8mvs_big" variants.
  - Pohl recommends picking a window that gives a draw rate of about 45–60%.
  - The older UHO 2022 sets are in the "Anti Draw Openings" package.
- **Source:** https://www.sp-cc.de/uho_2024.htm. Verified 2026-10-23.

### TCEC openings
- **Tag:** USE (for building a TCEC-like test set)
- **What** (TCEC Openings FAQ):

  | Stage | Book | Selection | Bias |
  |---|---|---|---|
  | Qualifying League | 4-move, 557 positions | random | no bias |
  | League 2 | 6-move, 629 positions | random | no bias |
  | League 1 | 8-move, 1000 positions | random | low/moderate bias, about ±0.40–0.65 |
  | Premier League | 8-move, 1000 positions | random | moderate/high bias, about ±0.50–0.80 |
  | Superfinal | new book each season, 50 positions, varied length | sequential | high/very high bias, sometimes above ±1.00 |

  - Nelson Hernandez selects the league books; Jeroen Noomen selects the Superfinal book.
  - The league books are reused from season to season.
  - Every opening is played twice with colours reversed, so **paired games are mandatory**. The target draw rate is 65–80%.
- **Where to get them:** **UNVERIFIED.** The FAQ does not say whether or where the books are published.
  - The TCEC game archive https://github.com/TCEC-Chess/tcecgames has the PGNs under CC BY-SA 3.0 (its scripts are Apache-2.0).
  - Its "compacted" format marks where each game left the book, so TCEC openings could be extracted from the archive with attribution.
- **Note:** the stage names in the FAQ (Qualifying League, League 2, …) differ from those in `config/tcec.json`.
- **Sources:** https://tcec-chess.com/articles/TCEC_Openings_FAQ.html and https://github.com/TCEC-Chess/tcecgames. Verified 2026-10-23.

### Other suites (CPW)
CPW's Opening Book page lists older suites (Nunn, Noomen 2-move, HERT, SALC and others), mostly as forum links. They are not verified here and are lower priority than UHO or 8moves.

**Recommendation for Fork:**
- SPRT on `UHO_Lichess_4852_v1.epd` or a UHO 2024 window: unbalanced books are standard practice and need fewer games.
- A second, balanced check on `8moves_v3.pgn`.
- Phase 8: a TCEC-style set of 8-move biased openings, played paired.

---

## 5. Syzygy tablebases

- **Tag:** USE. Ronald de Man generated them; the generator is GPL-2 per CPW. The tables are data and contain no engine code.
- **Format** (CPW):
  - Each endgame has a **WDL** file (`.rtbw`) and a **DTZ** file (`.rtbz`).
  - WDL is probed during search and holds full information for both sides. It is 50-move-rule aware, distinguishing cursed wins and blessed losses.
  - DTZ is meant for root use. It uses the DTZ50 metric and stores only one side's data to save space.
  - Runners (fastchess, cutechess) only need the WDL files for adjudication.
- **Sizes** (computed from `checksums/bytes.tsv` in niklasf/syzygy-tables.info; they match the KiB table in that site's source and CPW's MiB/GiB table):

  | Pieces | Tables | WDL | DTZ | Total |
  |---|---|---|---|---|
  | 3-4-5 | 145 (290 files) | 396.1 MB (378 MiB) | 587.9 MB (562 MiB) | **0.98 GB (939 MiB)** |
  | 6 | 365 (730 files) | 72.8 GB (67.8 GiB) | 87.4 GB (81.4 GiB) | **160.2 GB (149.2 GiB)** |
  | 7 | 1001 (2002 files) | 9.32 TB (8.5 TiB) | 9.07 TB (8.3 TiB) | **18.4 TB (16.7 TiB)** |

  So "~150 GB" for the 6-piece set is really 149.2 GiB, which is 160.2 GB.
- **Download mirrors** (listed in the syzygy-tables.info source; syzygy-tables.info itself blocked automated fetching):
  - https://tablebase.lichess.ovh/tables/standard/ (http/https, EU).
    - Directories: `3-4-5-wdl/` (145 files), `3-4-5-dtz/` (145 files plus `3-4-5.txt`), `6-wdl/` (365), `6-dtz/` (365), `7/`, and `*-dtz-nr` variants.
    - The site also hosts checksum lists and a `download.txt` URL list.
  - http://tablebase.sesse.net/ (http, EU). Responded with HTTP 200; its layout was not inspected.
- **Checksums:** md5, sha1, **sha256**, sha512, sha3-224, b2, b3 and tbcheck lists.
  - They are published both in the repo (`checksums/`) and on the lichess mirror. The two sha256 lists are byte-identical: sha256 `6dc75697…a783`, pinned in versions.lock.
  - The list covers 3-7 pieces: 10, 60, 220, 730 and 2002 files.
  - install.sh downloads 3-4-5 and checks all 290 files against it.
  - **Installed 2026-10-23** (first install.sh run, WSL2 Ubuntu 26.04):
    `~/fork-tools/syzygy/3-4-5`, 145 .rtbw + 145 .rtbz, sha256 OK,
    939 MiB on disk. 6-piece declined. Recorded for test scripts in
    `config/local-test.json` on main.
- **For Fork:**
  - The engine needs a `SyzygyPath` option.
  - The 3-4-5 set is enough for development.
  - TCEC adjudicates at 6 pieces (`config/tcec.json`). For faithful Phase-8 adjudication, get at least **6-piece WDL (72.8 GB)**. DTZ is optional.
  - **UNVERIFIED:** which piece count TCEC gives engines during play (`engine_access_pieces` is still null in tcec.json).
- **Sources:** https://www.chessprogramming.org/Syzygy_Bases, https://github.com/niklasf/syzygy-tables.info and https://tablebase.lichess.ovh/tables/standard/. Verified 2026-10-23.

## 6. Fathom (Syzygy probing library)

- **Tag:** USE. It is the one external library DESIGN.md plans to vendor (Phase 3). Record it in ORIGINALITY.md.
- **Maintained repo:** **jdart1/Fathom**. Its README says basil00/Fathom "is no longer being maintained", and the CPW page lists the jdart1 fork as the one with bug fixes and 7-man support.
  - jdart1/Fathom: no GitHub releases. Its only tag, v1.0, is old. master is at `c9c6fef0`, last pushed 2025-12-24; pin that commit.
  - basil00/Fathom: v1.0 from 2015, MIT.
- **License:** MIT (LICENSE: "Copyright (c) 2013-2018 Ronald de Man" plus the README).
- **Provenance:** this matters for the TCEC originality record.
  - The jdart1 README says the probing code now comes from `tbprobe.c` of **Cfish**, which is a Stockfish derivative.
  - Ronald de Man wrote that code and released it for unrestricted use.
  - The board and move-generation code was replaced with MIT code from Basil's original Fathom.
  - Document this lineage explicitly in ORIGINALITY.md. **UNVERIFIED:** whether TCEC has ruled on Fathom. Check the current TCEC rules before submitting.
- **API notes:**
  - `tb_init(path)` and `tb_free()`.
  - `tb_probe_wdl(...)` is for use during search. It is thread-safe unless `TB_NO_THREADS` is defined.
  - `tb_probe_root(...)` gives a DTZ-based best move and per-move DTZ/WDL results.
  - `tb_probe_root_dtz` and `tb_probe_root_wdl` score and rank every root move.
  - Configure through `tbconfig.h`, which is included with angle brackets, so a project copy earlier in the include path overrides it. Through it, Fork can supply its own attack and popcount functions.
  - It compiles as C99 or C++.
  - It also builds a `fathom` command-line tool (`fathom --path=... "FEN"`), useful for checking Fork's TB results.
- **Alternative:** Pyrrhic (AndyGrant/Pyrrhic) is a cleaned-up Fathom; its LICENSE is MIT with Basil's 2015 copyright. REFERENCE ONLY unless Fork chooses it instead.
- **Sources:** https://github.com/jdart1/Fathom and https://github.com/basil00/Fathom. Verified 2026-10-23.

---

## 7. NNUE trainers

Rule for Fork: train **only on data Fork generated itself**. A trainer is a tool, like a compiler. The trained net is Fork's if the data and the architecture choices are Fork's. Never copy trainer code into Fork's repo. Never start from another engine's net or its training data.

| Trainer | Tag | License | Version | Notes |
|---|---|---|---|---|
| **bullet** (jw1912) | **USE** (recommended) | MIT | no releases; main `579b78b3`, pushed 2026-10-23 (active) | A Rust machine-learning library for NNUE and value nets, used by many top engines. Runs on CUDA, ROCm or Metal GPUs. Training runs are written as Rust examples (`simple`, `progression`, `advanced`) or by depending on the `bullet_lib` crate. `bullet-utils` converts, shuffles, interleaves and validates data, and needs no GPU. Fork's own C++ inference code must be written from scratch to match the net layout Fork chooses. |
| **nnue-pytorch** (official-stockfish) | **REFERENCE ONLY** | GPL-3.0 | no releases; master `ed84cc1f` | Stockfish's trainer. Its README points to the Stockfish data recipes (800+ GB). It needs Docker or conda, ≥ 8 GB VRAM and ≥ 16 GB RAM. Legally, GPL would allow running it on Fork's own data, but its defaults, loaders and recipes are built around Stockfish's architecture and data. TCEC reviewers could see a net from it as Stockfish-derived. Read the docs for ideas; do not run it to produce Fork's nets. |
| marlinflow (jnlt3, formerly dsekercioglu) | REFERENCE ONLY | GPL-3.0 (GitHub metadata; no `LICENSE` at main root) | no releases; main `a2a3c17d`, pushed 2025-04-14 | The older PyTorch and Rust trainer for Black Marlin, superseded by bullet. Its `marlinflow-utils` documents the legacy text format `FEN \| eval \| wdl`. |
| Grapheus (Luecx) | REFERENCE ONLY | **No licence file** (README is one line), so no reuse rights | no releases; main `21193123`, pushed 2025-03-08 | A C++/CUDA trainer. Without a licence its code cannot be reused. |
| CudAD (Luecx) | REFERENCE ONLY | GPL-3.0 | main `339fa667` | An older CUDA trainer from Koivisto's author. |
| "carbon" | — | — | — | **UNVERIFIED:** no repo found or opened. |

## 8. Training-data formats and generation tools

| Item | Tag | License | Notes |
|---|---|---|---|
| **viriformat** (cosmobobak) | USE (spec) | MIT (`Cargo.toml`; no LICENSE file) | Crate v3.0.0, main `0238b315`. A game-based binpack. Each game is a 32-byte marlinformat `PackedBoard` (occupancy bitboard, 4-bit pieces with an unmoved-rook flag for castling, stm/ep byte, halfmove, fullmove, score, result), then 16-bit move and 16-bit score pairs, ending in 4 zero bytes. It has a reserved-extension record. The README is a full spec, so Fork's C++ datagen writer can be written from it directly. bullet calls it "the most commonly used" format among people who generate their own data. |
| **bulletformat** (jw1912) | USE | MIT | main `eddd9a2d`. A simple fixed-size per-position record. It is stored side-to-move relative and drops castling and halfmove data. Fine for small nets. |
| marlinformat | REFERENCE | — | **UNVERIFIED** standalone repo: `jnlt3`, `dsekercioglu` and `Ciekce` `/marlinformat` were all missing. Its `PackedBoard` is specified inside the viriformat README. |
| Stockfish binpack (`.binpack`) | REFERENCE ONLY | GPL (its reader lives in nnue-pytorch and Stockfish) | bullet can read it (`SfBinpackLoader`), but the only reason to read it would be Stockfish data, which is off-limits. |
| **Stockfish `generate_training_data`** (Stockfish `tools` branch, head `9a4c7cf4`) | **OFF-LIMITS** | GPL-3.0 | Stockfish code (self-play at fixed depth with random moves). Any data it produces is Stockfish-generated, which TCEC bans for Fork. The same applies to every published Stockfish or Leela dataset and binpack. |
| bullet-utils | USE | MIT | Converts, shuffles, interleaves and validates bullet data. |
| marlinflow-utils | REFERENCE ONLY | GPL-3.0 | txt-to-data, shuffle and interleave. Rewrite the same ideas rather than use them. |
| OpenBench "Data Generation Workloads" | USE | GPL-3.0 | The wiki has a page for distributed datagen with Fork's own engine. Its details were not read: **UNVERIFIED**. |

Fork's datagen should be Fork's own code. Self-play with random-move openings, positions written in viriformat (or a Fork-defined format), and provenance logged as DESIGN.md requires.

---

## 9. Profilers

| Tool | Tag | License | Version | Notes |
|---|---|---|---|---|
| **perf** | USE | **UNVERIFIED** (the perf wiki states none; it ships in the Linux kernel tree at `tools/perf`) | distro package (`linux-tools-generic`) | Commands: `perf stat`, `record`, `report`, `annotate`, `top`. **UNVERIFIED in WSL2:** Ubuntu ships no perf build for the WSL kernel, so the `/usr/bin/perf` wrapper may refuse. install.sh links `/usr/lib/linux-tools/*/perf` directly. Hardware counters inside WSL2 are also unverified. Check `perf stat -e cycles`. |
| **valgrind / callgrind** | USE | GPL (the COPYING file at git HEAD holds the GPLv3 text; the download page states none) | 3.27.1, 2026-05-20 (upstream); apt gives the distro version | Upstream publishes md5 `9b819b1a…` and sha1 `0b113f5c…` for `valgrind-3.27.1.tar.bz2`, but no sha256. Use `valgrind --tool=callgrind ./fork bench`. |
| **hotspot** (KDAB) | USE | GPL v2+ (README and LICENSE.GPL.txt) | v1.6.0, 2026-02-27 (plus a `continuous` pre-release, 2026-10-14) | A Qt GUI for perf.data with flame graphs. The AppImage sha256 is in versions.lock. install.sh fetches it only with `FORK_TOOLS_HOTSPOT=1`. It needs WSLg to display. |
| **Intel VTune Profiler** | USE (manual install) | Proprietary EULA (download page) | 2026.4.0.23 per the installer filenames; **release date UNVERIFIED** (the version table was "Service Currently Unavailable") | Available through the oneAPI apt repo (`intel-oneapi-vtune`), a .sh installer, a Windows .exe or Docker. **UNVERIFIED:** hardware-event support on AMD CPUs and under WSL2. |
| **AMD uProf** | USE (manual install) | Proprietary EULA (click-through download) | 5.3, 2026-06-17 | Builds for Windows, Linux and FreeBSD. The best fit if the test machine is AMD. |

install.sh installs perf and valgrind and prints instructions for VTune and uProf. It does not automate them because their licences must be accepted by hand.

## 10. PGN utilities

| Tool | Tag | License | Version | Notes |
|---|---|---|---|---|
| **pgn-extract** (David J. Barnes) | USE | GPL-3.0 | 26-04, 2026-06-03 (`pgn-extract-26-04.tgz`) | Handles millions of games and Chess960. Detects duplicates and filters by moves, position, tags or material. Output can be SAN, LAN, UCI or EPD; ECO classification is supported. No checksums are published: **UNVERIFIED** hash. |
| **python-chess** (`chess` on PyPI) | USE (scripts and tests only; never linked into the engine) | GPL-3.0+ | 1.11.2, 2025-02-25 (sdist sha256 in versions.lock); master still active (pushed 2026-08-22) | PGN, EPD and FEN parsing, a UCI engine driver, and Syzygy probing. Good for test harnesses, perft cross-checks and book conversion. |
| Ordo PGN input | USE | GPL-3.0 | v1.2.6 | Reads results straight from PGN (see §3). |
| books repo `pgn2epd.py` / `epd2pgn.py` | USE | CC0-1.0 | `a804a97e` | Small converters in the books repo. |
| Scid | — | — | — | **UNVERIFIED:** no primary page opened. |

---

## UNVERIFIED items (summary)

1. Which Ubuntu release ships Qt ≥ 6.8, which cutechess v1.5.1 needs. Also whether the cutechess AppImage contains `cutechess-cli`.
2. Whether fastchess and cutechess `movecount` counts plies or moves, and how that maps to TCEC's "10 plies, both engines" rules.
3. Fishtest's licence, and the inputs of the Fishtest SPRT calculator (bot wall).
4. BayesElo: no version number, no checksum, no maintained repo.
5. Where TCEC publishes its opening books. Also which piece count TCEC gives engines during play.
6. Whether TCEC has ruled on Fathom's Cfish-derived `tbprobe.c` lineage.
7. How each Stockfish-repo book was built (which engine evaluated it).
8. perf's licence statement, perf and hardware counters under WSL2, and VTune's release date and AMD/WSL support.
9. A standalone marlinformat repo, the "carbon" trainer, OpenBench's datagen details, and Scid.
10. pgn-extract checksum, and the apt versions of perf and valgrind.

## OFF-LIMITS (summary)

- Stockfish source code, including the `tools` branch `generate_training_data`.
- Stockfish and Leela nets, and any network not trained by Fork.
- Stockfish and Leela training datasets and binpacks, and any data generated or rescored by another engine.
- nnue-pytorch, marlinflow, Grapheus and CudAD code may be read but not copied (REFERENCE ONLY). Running nnue-pytorch to produce Fork's nets is advised against.
