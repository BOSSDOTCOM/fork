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
  - **Qt ≥ 6.8 by Ubuntu release** (resolved 2026-10-24 from the Launchpad API, published `qt6-base` sources in the primary archive): 22.04 jammy 6.2.4, 24.04 noble 6.4.2, 25.04 plucky 6.8.3, 25.10 questing 6.9.2, 26.04 resolute 6.10.2. So 26.04 is the first **LTS** that can build cutechess v1.5.1 from source; 22.04 (TCEC's toolchain release) and 24.04 cannot. The local WSL (Ubuntu 26.04.1) has `qt6-base-dev` 6.10.2 and its source-built `cutechess-cli` reports "cutechess-cli 1.5.1, Using Qt version 6.10.2" (run 2026-10-24). install.sh checks the Qt version at runtime; if Qt is too old, it falls back to extracting the AppImage.
  - **The AppImage does contain `cutechess-cli`** (resolved 2026-10-24): the v1.5.1 AppImage downloaded fresh matched the pinned sha256 `d9448693…`, and `unsquashfs -l` on its embedded squashfs lists `usr/bin/cutechess-cli` (plus `usr/bin/cutechess` and the `cutechess-cli.6` man page). Running that extracted binary on 22.04 was not tested.
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

### TCEC's cutechess fork (deferred)
- **Status (owner, 2026-10-23): deferred.** https://github.com/TCEC-Chess/tceccutechess
  has had no pushes since 2023-04-09 (`master`, commit `a324a3e6`), and whether
  TCEC's servers still run it is unconfirmed; the question is on the Discord
  list in competition.md. Phase 2 acceptance uses `fastchess --compliance` plus
  standard cutechess-cli. If TCEC confirms the fork, it is added then.
- The prepared install step (Qt5 build, pinned commit, notes) is on branch
  `tcec-cutechess`, not merged.

**Mapping TCEC adjudication to runner flags (Phase 8).** Re-checked 2026-10-24. The premise above this paragraph used to be out of date: `config/tcec.json` now records TCEC's current rule, a draw once the position has ≤ 6 pieces (kings counted, pawns not) and the eval stays within ±25 cp for 8 consecutive plies, with no minimum move number, no reset on captures or pawn moves, and **no** win adjudication. How the runners count, read from the source at the pinned versions:
  - **cutechess v1.5.1** (`projects/lib/src/gameadjudicator.cpp`, `chessgame.cpp`): every engine move's eval is checked in turn, so both engines' scores alternate in one counter. Draw fires when `plyCount/2 >= movenumber` and the counter of consecutive in-band evals reaches `2 × movecount`; the counter resets on any capture or pawn move and on book or forced moves. Resign keeps one counter per side (that side's own consecutive moves at or below `-score`); with `twosided=true` the opponent's count at or above `+score` must also reach `movecount`.
  - **fastchess v1.8.2-alpha** (`app/src/matchmaking/match/match.hpp` and `match.cpp`): the same model. One draw counter over both engines' evals, reset when the halfmove clock is 0 or a score is missing, with mate scores not counting; it fires when `fullmove number − 1 >= movenumber` and the counter reaches `2 × movecount`. A source comment says fastchess uses the board's fullmove counter where cutechess uses `plyCount/2`, which differs for EPD starts. Resign with `twosided` counts consecutive plies in which |score| ≥ `score` (or mate) and needs `2 × movecount`; without it, it is per side, `movecount` of that side's moves.
  - **Consequence:** `movecount` means full moves (2 plies). Neither runner can express TCEC's piece-count condition or its "not reset by captures/pawn moves" rule. The closest approximation is `-draw movenumber=1 movecount=4 score=25` (8 plies; not `movenumber=0`, because cutechess only enables draw adjudication when `movenumber > 0`), which will adjudicate more often than TCEC because it ignores material; use no `-resign` to match TCEC. Whether TCEC requires *both* engines' evals in band is still UNVERIFIED (competition.md); both runners do test both engines' evals.
  - Sources: https://raw.githubusercontent.com/cutechess/cutechess/v1.5.1/projects/lib/src/gameadjudicator.cpp, https://raw.githubusercontent.com/Disservin/fastchess/f618e34540f94f4719ad3817950618dabe441318/app/src/matchmaking/match/match.hpp and `.../match.cpp`.

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
- **License:** none declared (re-checked 2026-10-24: no LICENSE file in the root, GitHub API `license: null`, no license field in the root, `server/` or `worker/` `pyproject.toml`). With no grant, treat it as all rights reserved; Fork only studies its statistics and does not reuse its code.
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

### Tactical and mate suites for the pruning regression guard (DESIGN.md §5.2)

Checked 2026-10-25. DESIGN.md §5.2 asks for a tactical suite and a mate suite run at fixed nodes after every pruning change, as a guard that never replaces SPRT. These suites are **test inputs only**: they never become training data, tuning targets or SPRT gates, which keeps them clear of the data-policy rules whatever their provenance. Every file below was downloaded into a fresh temporary folder, hashed there, and deleted afterwards; nothing third-party is committed.

#### Win at Chess (WAC), Bergbom copy (the file `tools/solve_suite.py` pins)
- **Tag:** USE (test input; keep downloading it, do not commit it).
- **What:** 300 tactical positions from Fred Reinfeld's book *Win at Chess*, as one EPD record per line with only `bm` and `id` operations (`id "WAC.001"` to `id "WAC.300"`). 22 records list more than one `bm` move. All 300 parse and pass python-chess 1.11.2's `is_valid()` (run 2026-10-25). CRLF line endings.
- **Pin confirmed (2026-10-25):** `http://www.bergbomconsulting.se/chess/epdfiles/wac.epd` returned HTTP 200 with `Content-Length: 22995` and `Last-Modified: Mon, 12 Sep 2005 20:48:33 GMT`. The download is 22,995 bytes and 300 lines, with SHA-256 `e1eab24c3c609012b1aa6d8b4f532429ce61c2217402efd051297303e78a09e8`, which matches `solve_suite.py` exactly. The server has a plain directory index (`/chess/epdfiles/`) with 20 suites, all dated 2005-09-12 except `perftsuite.epd` (2007).
- **Provenance:**
  - *The book.* CPW credits Fred Reinfeld with compiling the 300 positions in 1958 from tournament play, and says Fred Wilson revised the book in 2001 and moved it to algebraic notation. The Google Books record for the 2001 edition (Dover, ISBN 0-486-41878-2, 105 pages) also says it was revised by Fred Wilson. Lang and Smith (1993) cite a different first date: "Win at chess, Dover 1945, ISBN 0-486-20438-3". **UNVERIFIED:** whether the first edition was 1945 or 1958. The two sources disagree and I did not open the book itself.
  - *The machine-readable set.* Lang and Smith (1993) say they got the 300 WAC positions from Hans Berliner, with answers that Berliner and HITECH had checked. They also say Steven J. Edwards was converting their database into the format he was standardising, which became EPD. **UNVERIFIED:** who produced the EPD file that Bergbom hosts. John Bergbom (author of the Amundsen engine) hosts it on a page of suites "collected" for Amundsen's `testsuite` command, but no page names who made the EPD. The Edwards route is an inference, not a documented fact.
- **Licence / copyright:** none stated. Bergbom's pages, the file itself and CPW give no licence. The book is still sold by Dover in Wilson's 2001 revision. **UNVERIFIED:** the copyright status of the 1958 text and of the solutions. The Stanford copyright-renewal database refused a scripted query (JavaScript wall), and I am not giving a legal opinion. Since no licence grants redistribution, **keep the current design: download at test time, check the SHA-256, never commit**. That is what `solve_suite.py` already does.
- **Known errata (bm operations):**
  - Lang and Smith (1993) report that years of testing had found 10 cooks (alternative solutions of equal value, most of them minor) and 8 wrong answers in the 300 positions. They don't list which positions in the text I could extract.
  - **WAC.230** is the most disputed record. The Bergbom file has `bm Rb4`, a position from Kmoch vs Nimzowitsch, Bad Niendorf 1927. In 2001 Alex Szabo argued on CCC that 1...Rb4 does not win (5.Re2! holds) and that a dozen other moves hold just as well. Dann Corbit re-examined this in 2005 and 2009, and in 2010 posted a Stockfish 1.8 line claiming to refute Szabo's refutation. The question is unsettled. CPW's Alexander Szabo page summarises it, with the 2009 and 2010 TalkChess threads as the primary posts.
  - Other positions raised on forums: WAC.041 (b7), WAC.100, WAC.102, WAC.109, WAC.123, WAC.163, WAC.002 (all listed on CPW's WAC page). Robert Hyatt (2020) reported that **WAC.223** is not a clear win: his program and other posters' engines scored the book move Nxe4 and several alternatives at about the same value. Dann Corbit (2007) reported engine preferences differing from the book in **WAC.264** and **WAC.287**.
  - Szabo's 2001 correction list itself (stmintz.com CCC archive, id 163035, and Corbit's analysis, id 163177) **could not be opened**: the archive URLs now redirect to an unrelated LinkedIn profile. **UNVERIFIED:** its exact list of positions.
- **Corrected versions:**
  1. **CPW "EPD Wacnew" block** (https://www.chessprogramming.org/Win_at_Chess; CPW text is CC BY-SA 3.0; the page is currently a read-only recovery copy, last modified 2026-08-05). It has the same 300 FENs as Bergbom's file, and **22 records differ**, always by added alternatives: extra `bm` moves in WAC.031, 038, 041, 052, 096, 100, 105, 120, 123, 140, 146, 150, 199, 216, 235, 252, 264, 273, 275, 279 and 287; for WAC.274, `am Rd6; bm Rb6 Rg5+;`; and `c0` comments on WAC.150 ("all win but e3 is best") and WAC.252 ("Bg4 wins, but Re2 is far better"). WAC.230 is unchanged (`bm Rb4`). (Diff run locally 2026-10-25; the block was extracted from the page HTML.) CPW cites `wacnew.epd` on tropo.googlecode.com as the block's source, but that URL now returns 404, so **there is no stable downloadable file to hash**. A hash of a page extraction would not be a pin.
  2. **Albert Silver, "WAC cleaned and revised (201 positions)"** (TalkChess, 2018-05-16). He removed positions with wrong, multiple or "right for the wrong reason" solutions, plus WAC.230, leaving 201. He checked every position in multi-PV with Komodo 11, so the selection is **engine-vetted**. It exists only as a forum code block, with no licence and no file to hash. A copy named `wac-revised.epd` sits in the unlicensed TerjeKir/EngineTests repo. **UNVERIFIED:** that it is the same set; I did not hash it.
  - **Conclusion:** no better-maintained primary source of a corrected WAC with a stable URL exists. Keep the Bergbom pin. Two optional refinements for `solve_suite.py`: also accept CPW's alternative moves for the 22 records above (a list of IDs and moves written into Fork's own code, citing CPW), and report WAC.230 separately or exclude it.
- **Sources:** https://www.chessprogramming.org/Win_at_Chess ; https://www.chessprogramming.org/Alexander_Szabo ; http://www.bergbomconsulting.se/chess/testsuites.html ; Lang and Smith 1993 (http://scorevoting.net/WarrenSmithPages/homepage/testpos.ps, linked from CPW Test-Positions) ; TalkChess threads t=17824, 28900, 35669, 67469, 72733. Verified 2026-10-25.

#### Mate suite: matetrack (`matetrack.epd`, pinned commit)
- **Tag:** USE as a test input only (never training, tuning or a gate). The suite is **solver/engine-produced and Stockfish-maintained**, see below. **Owner decision needed** before it becomes the §5.2 mate suite.
- **Search result:** I found **no human-made mate suite** that is a downloadable EPD file with a few hundred positions, `dm` (or equivalent) operations, a stable URL and a licence. Candidates I checked and rejected:
  - Uri Blass's mates from human ICCF correspondence games (TalkChess 2018), and his 2021 suite: forum posts only, mates proved with engine help ("chest"), no file, no licence.
  - Lichess puzzle database: CC0 and from human games, but generated with Stockfish NNUE at 40 meganodes, and the CSV grows every month so it can't be pinned. data-policy.md already limits it to diagnostic reports.
  - TerjeKir/EngineTests `mate_in_1..8.epd`: no licence, no provenance, engine-style `ce +M3; pv` fields.
  - python-chess `endgame-dm-4/5.epd`: tablebase-exact, GPL-3.0, but too small (under 2 KB each).
  - YACPDB and other composed-problem databases: no export or licence page I could load (JavaScript app). **UNVERIFIED:** whether a licensed dump exists.
- **What:** https://github.com/vondele/matetrack (GPL-3.0 per the GitHub API), a repo of EPD files and Python scripts that tracks how well Stockfish finds mates. It is not engine source. Its README describes `matetrack.epd` as the successor to `ChestUCI_23102018.epd` (derived from public `ChestUCI.epd` files), with illegal positions removed and known errors corrected. It holds 6,554 problems from #1 to #126, with 4 to 32 pieces; in 26 of them the side to move gets mated.
- **Pin (downloaded 2026-10-25):**
  - `https://raw.githubusercontent.com/vondele/matetrack/8085413b46d6d4f1bb9612353a6385dec784dae7/matetrack.epd`
  - 449,928 bytes, 6,554 lines, SHA-256 `8ba5712234ba0cb2a1f1b1934872d1d30ba5e01c80482844dccccd4bc2eefd72`.
  - master moves often (its last push was on the day of checking), so pin the commit, not the branch.
- **Syntax:** not standard EPD `dm`. Each line is the four FEN fields, then `bm #N;`, where N is the fastest known mate in full moves (negative when the side to move is mated). Most lines then carry further fields with no opcode: solver timings such as `00:00;`, `@ C2/R0/K3/P1/X2`, and `Duals(n);`. python-chess 1.11.2's `Board.from_epd` **rejects these lines** (`invalid san: '#4'`, tested), so Fork's runner must split the fields itself.
- **Suggested subset (a few hundred, moderate length):** lines with `bm #1` to `bm #5` and N positive give **297 positions**: 4 at #1, 17 at #2, 23 at #3, 67 at #4 and 186 at #5, with 5 to 28 pieces. All 297 pass python-chess `is_valid()`. Every #1 and #2 claim (21 positions) was confirmed exactly by my own brute-force search with no shorter mate; #3 to #5 were not verified (2026-10-25). Pass criterion: Fork reports a mate score of the stated length (or shorter) within the node budget. There is no single best move to compare, because several mating moves may exist.
- **Provenance and originality flag:** from the handful of lines I inspected, the positions look like composed problems (unnatural piece placements); this is an impression, not a documented fact. Their mate lengths come from the Chest mate solver (judging by its output fields) and later Stockfish-assisted corrections. That makes the data **engine-generated**. It is unsuitable as training data under any reading of data-policy.md rule 2, and acceptable only as a test input. **UNVERIFIED:** where ChestUCI's positions came from. The FishCooking post the README cites is behind a Google Groups permission wall. The repo's other suites are not recommended for this role: `mates2000.epd` was explicitly selected by Stockfish solvability at 1M nodes, and `classic280.epd` holds 280 tablebase-style endgames from #10 to #21 (SHA-256 `f94222e76c95a64ccbc68c34d393d4adae1e81a55bdc3e801370704d50a6936d`, 10,470 bytes), which is long and endgame-only.
- **Licence:** GPL-3.0 (repo-level, GitHub API). It is compatible with Fork's GPL-3.0-or-later, so committing a frozen copy with attribution would be legally possible. Downloading at test time with the SHA pin is still preferred, to keep third-party data out of Fork's history.
- **Sources:** https://github.com/vondele/matetrack (README at master, API metadata and tree, raw files at the pinned commit). Verified 2026-10-25.

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
  - Correction 2026-10-24: TCEC no longer adjudicates with tablebases (removed between 13 Oct 2024 and 4 May 2025, `config/tcec.json` `tablebase`); its current draw rule only *counts* pieces (≤ 6 including kings, excluding pawns). The 6-piece WDL set (72.8 GB) is still useful to mimic TB-assisted play in Phase 8; DTZ is optional.
  - **Engines get 7-man Syzygy** during play: `engine_access_pieces` is 7 in `config/tcec.json`, from the `SyzygyPath=/home/syzygy7` option in archived TCEC games and the live Swiss 10 game (competition.md §2 "Tablebases available to engines", verified 2026-10-23). This replaces the earlier open note, which predated that check.
  - The smallest downloadable 7-man pair, KPPPPPvK (3.55 MiB WDL + 1.58 MiB DTZ, sha256-checked), and how to test with it are in §6.9 (2026-10-26).
- **Sources:** https://www.chessprogramming.org/Syzygy_Bases, https://github.com/niklasf/syzygy-tables.info and https://tablebase.lichess.ovh/tables/standard/. Verified 2026-10-23.

## 6. Fathom (Syzygy probing library)

- **Tag:** USE. The owner approved it on 2026-10-24 as the one vendored third-party library: `third_party/fathom/`, built as its own CMake target. It serves Phase 3 deliverable 7: WDL probes in the search and DTZ ranking of root moves (DESIGN.md "7. Syzygy probing, designed for 7 pieces"). Record it in ORIGINALITY.md under Third-party libraries.
- **Licence:** MIT (details in 6.2).
- **Maintained repo:** **jdart1/Fathom**, a GitHub fork of basil00/Fathom (API, 2026-10-26). The jdart1 README says basil00/Fathom is no longer maintained (re-read 2026-10-26). From the 2026-10-23 pass, not re-checked: CPW lists the jdart1 fork as the one with bug fixes and 7-man support, and basil00/Fathom is v1.0 from 2015, MIT.
- **Alternative:** Pyrrhic (AndyGrant/Pyrrhic), a cleaned-up Fathom; its LICENSE is MIT with Basil's 2015 copyright (2026-10-23 pass, not re-checked). REFERENCE ONLY unless Fork chooses it instead.
- **How this section was checked (2026-10-26).** I made a temporary clone outside both repositories, read every file at the pin, and ran build and probe tests: WSL Ubuntu 22.04 with gcc 11.4, g++-12, clang 16 and clang 19; Windows with llvm-mingw clang 23.1.3 and WinLibs gcc 16.2.0. The clone was deleted afterwards. All results below come from those runs unless marked "source reading". Sources: the GitHub API, raw files at the commit, and the PR and issue pages listed in sources.md.

### 6.1 The pinned commit

- **Full SHA:** `c9c6fef0dddc05d2e242c183acf5833149ab676d`. It exists on jdart1/Fathom and is still the `master` head (`git ls-remote`, 2026-10-26).
  - Author and committer: Jon Dart, 2025-12-24 01:45:52 UTC.
  - Message: "Fix possible integer alignment issues". It touches only `src/tbprobe.c`; its parent is `f08df228fcc62883a577ce66d4d72473f608aadd`.
- **No releases.** The only tag, `v1.0`, is at `70d0091f`.
- **SHA-256 of the files at the pin**, as committed (LF line endings). Two sources give identical values: the clone's git blobs and raw.githubusercontent.com at the commit.

  | File | Bytes | SHA-256 |
  |---|---|---|
  | `LICENSE` | 1,149 | `c8038055839bd02f995cd7d1bba19657720097f5604411a7977ebcb5b4a37759` |
  | `README.md` | 5,924 | `8a44c2a068f97fb237cea30f8039f4942950668c97b8f37092d1065b26cd074b` |
  | `src/tbprobe.c` | 73,434 | `7ed0cc80626271342bfe413d6c421756b6851f977a064461f5f555e1b598df35` |
  | `src/tbprobe.h` | 12,815 | `dc7808dc58c2a1af921a612f94041b917dfac94d3215a76a2b2b0c53c94ea561` |
  | `src/tbconfig.h` | 5,648 | `69fe1821b471164bd759cf46c486d55b7fa727e348a5ee306b18d19537ac3a03` |
  | `src/tbchess.c` | 31,292 | `119f19fa8714686798ca7be011e5b234f99c93aec751e9492f2664757d6c029d` |
  | `src/stdendian.h` | 8,925 | `e5b8187eec89ef83e731ea92be8ca0df4b533d8d21075fc4e2c86b4b00d7b7c3` |
  | `src/apps/fathom.c` | 21,767 | `3d466fae6e9c5cb3028df61634c638fa2f9b1aa553ce6288fcd618da396b03c8` |
  | `src/apps/Makefile` | 797 | `bf2486c1c6c30f80d6f3baaabc83ff9ea578bc1085fe4ad702771d1aff35ecfb` |
  | `Makefile` | 807 | `8c7a0f5c9ed34aa6d25212a954d044c62f294c7eef82b3ad4b33dae49e7a5a4d` |

- **Line endings.** On this Windows machine (`core.autocrlf=true`) a clone checks the files out with CRLF, and their hashes then differ from the table (observed). Check vendored copies against the git blob, not the working file. A `.gitattributes` rule keeping `third_party/fathom/` LF-only would avoid the problem (a suggestion, not tested).

### 6.2 Licence and lineage (for ORIGINALITY.md)

- **`LICENSE`:** the MIT text with three copyright lines: Ronald de Man 2013-2018, basil00 2015, and Jon Dart 2016-2025.
- **Per-file headers** (all MIT permission text unless noted):
  - `tbprobe.c`: Ronald de Man 2013-2018, basil00 2015, and "Modifications" by Jon Dart 2016-2024.
  - `tbchess.c`: basil00 2015, and modifications by Jon Dart 2016-2020.
  - `tbprobe.h`: "(C) 2015 basil, all rights reserved", followed by the MIT grant.
  - `tbconfig.h`: the same as `tbprobe.h`, plus modifications by Jon Dart 2016-2017.
  - `apps/fathom.c`: basil 2015 and Jon Dart 2018-2019.
  - **`stdendian.h` is different:** it says it comes from a public gist by GitHub user michaeljclark (gist `3b4fd912f6fa8bb598b3`), modified, and marks itself **Public Domain**. I did not open the gist.
- **Lineage stated in the README:**
  - Ronald de Man created the Syzygy tables.
  - Basil Falcinelli's original Fathom combined de Man's probing code, first written for Stockfish, with Basil's own chess support code.
  - The current probing code instead derives from `tbprobe.c` of **Cfish** (a Stockfish derivative). Ronald de Man wrote it, and it includes 7-man support; the README says he released it "for unrestricted distribution and use".
  - Jon Dart replaced Cfish's board and move-generation code with Basil's MIT code and split the code into `tbchess.c` (chess) and `tbprobe.c` (probing).
- **Lineage traces in the code** (source reading):
  - a comment comparing the KvK key with Cfish's;
  - a comment that Fathom's white and black values are the reverse of Stockfish's;
  - two comments citing Stockfish PR #1829 as the reason for the random-access hints (6.4, 6.6).
- **For the TCEC originality record:** Fork's binary will contain Cfish-derived probing code, under MIT and unrestricted-use terms. **UNVERIFIED (kept):** whether TCEC has ruled on this; ask before applying (UNVERIFIED summary item 6).

### 6.3 Seven-piece support and the reported piece count

- **The 7-piece limit is fixed in the code.** `tbprobe.c` defines `TB_PIECES` as 7 unconditionally; it is not a `tbconfig.h` option. Table capacity is sized for that limit: 650 piece-only and 861 pawn entries, and a 2^12-slot hash.
  - The 6- and 7-piece names are only enumerated when `size_t` is 64-bit (source reading).
  - A consistency check: with 3 tables present, strace counted 1,511 failed opens. That fits 1,508 absent WDL names plus the 3 absent DTM files of the tables found, so 1,511 names were tried. That is the number of Syzygy tables for 3 to 7 pieces (5 + 30 + 110 + 365 + 1,001). I did not check the failed names one by one.
- **How the piece count is reported:** through the global `unsigned TB_LARGEST`, set by `tb_init` (declared in `tbprobe.h`).
  - Value: the largest piece count among tables whose `.rtbw` file was found (or among DTM `.rtbm` tables, if those are larger). A DTZ file without its WDL file is ignored.
  - With no tables, `TB_LARGEST` is 0. An empty path or the string `<empty>` unloads everything.
  - Two internal globals hold the same information (`TB_MaxCardinality`, `TB_MaxCardinalityDTM`); they are not in the header.
  - `tb_init` has no failing return at this commit: both of its return statements return true, and fatal problems call `exit()` (source reading).
  - Observed: `TB_LARGEST` was 3 with three 3-piece tables loaded.
- **7-man probing works (run 2026-10-26).** Only the smallest 7-man pair (KPPPPPvK `.rtbw` + `.rtbz`, 6.9) was in the directory. The `fathom` tool built from the pin then probed two positions, and the lichess tablebase API gave the same answers:
  - `k7/8/8/8/8/8/PPPPP3/7K w - - 0 1`: Fathom says Win, DTZ 1, 13 winning moves. Lichess says `win`, `dtz` 1, all 13 moves winning.
  - `k7/8/8/8/8/8/PPPPP3/7K b - - 0 1`: Fathom says Loss, DTZ 2, 3 losing moves. Lichess says `loss`, `dtz` -2, 3 moves.
  - The same results came on Linux (gcc tool) and on Windows (MinGW gcc tool).
  - The tool rejects positions with more pieces than `TB_LARGEST` (it refused a 6-piece FEN when only 3-piece tables were loaded), so `TB_LARGEST` was at least 7 here.

### 6.4 Linux file mapping and `madvise(MADV_RANDOM)` (TCEC's request)

- **TCEC's request** (Further information page, revision 8475, 2026-02-24, re-read 2026-10-26): engines using 7-man Syzygy should mark the memory-mapped tables for random access with `madvise(..., MADV_RANDOM)` (competition.md §2).
- **Where Fathom maps tables.** `map_file()` in `tbprobe.c` (called from `map_tb()` and `init_table()`) maps each file whole, read-only and shared.
  - Mapping is lazy: it happens at the first probe of each material and table type, under the global mutex.
  - `tb_init` only opens each file, checks its size and closes it again. strace showed no mapping at init; the mmap and madvise calls came at probe time.
- **The pinned code already gives the advice.** Right after `mmap`, `map_file()` calls `posix_madvise(..., POSIX_MADV_RANDOM)` on the whole mapping, guarded by `#ifdef POSIX_MADV_RANDOM`; the return value is ignored.
  - glibc implements `posix_madvise` with `madvise(2)`; only the DONTNEED advice becomes a no-op (posix_madvise(3), man-pages 6.19). So on Linux this is `madvise(MADV_RANDOM)`.
  - Observed under strace on Ubuntu 22.04 (glibc 2.35): one `madvise(addr, file size, MADV_RANDOM) = 0` per mapped table. That includes both 7-man files (3,721,360 and 1,652,304 bytes).
  - `/proc/self/smaps` showed `rr` in VmFlags for each mapping. The kernel's proc.rst defines `rr` as "random read advise provided".
- **The catch: the advice can silently disappear.** glibc only defines `POSIX_MADV_RANDOM` when its feature macros enable `__USE_XOPEN2K`. That guard is in Ubuntu 22.04's `bits/mman-linux.h` (read locally), and posix_madvise(3) lists the matching `_POSIX_C_SOURCE >= 200112L` requirement.
  - Advice present: g++ and clang++ in C++ mode (they predefine `_GNU_SOURCE`) and C with `-std=gnu99` (glibc's default `_DEFAULT_SOURCE`). These gave the madvise calls and the `rr` flag (observed).
  - Advice missing: strict `-std=c99` or `-std=c11`. These compiled without any warning, made no madvise calls, and left no `rr` flag (observed).
- **Conclusion for Fork: no code change is needed**, provided `tbprobe.c` is compiled as C++. Fork's project is CXX-only. Set `LANGUAGE CXX` on the file; CMake 3.22 then passes `-x c++` to g++ and clang++ (observed). Keep the vendored copy byte-identical to the pin.
- **Suggested Linux test:** after one probe, read `/proc/self/smaps` and require `rr` on every mapping of a `.rtbw`/`.rtbz` file. A throwaway driver did exactly this on 3-piece tables.
- **Optional hardening patch, if the owner wants a build-time guarantee instead of a test.** It adds two lines inside `map_file()`: after the `posix_madvise` call and before its `#endif`, an `#elif defined(__linux__)` branch with an `#error` message saying the advice is not visible.
  - Tested: `git apply --check` succeeds on the pin. Strict C99 now fails with the message. gcc gnu99 and all four TCEC C++ compilers still build, and the madvise calls are unchanged.
  - The diff's SHA-256 is `ceb91a8c8d20c7826640242b47449d2e3f7d98b07e39fbf619ecd1958e7bf08b`. The exact text went to the main session in the 2026-10-26 research report; if adopted, store it beside the vendored copy and list it in ORIGINALITY.md.
  - Its cost: the vendored `tbprobe.c` would no longer match the pinned hash.

### 6.5 Thread safety

- **How the code works** (source reading): a table and type is set up lazily inside `probe_table()` with double-checked locking.
  - Each table has an atomic "ready" flag per type. One global mutex serves all types: `std::mutex` when built as C++11 or later, otherwise a pthread or Win32 mutex.
  - WDL, DTZ and DTM all take this same path.
  - An atomic error flag makes a failed setup safe when two threads race on it. That came from PR #11, merged 2024-12-08 into the history the pin contains.
  - Defining `TB_NO_THREADS` turns the locks into no-ops. **Fork must not define it.** The `fathom` tool's own Makefile does define it, which is fine for a single-threaded tool.
  - Two more fixes Fork depends on are in the pin's history (`git merge-base --is-ancestor`, checked). PR #13 (2025-09-07) fixed the crash when `tb_init` and `tb_free` are called repeatedly (issue #14); Fork re-runs `tb_init` on every `SyzygyPath` change. PR #16 (2025-09-27) fixed a crash in C++20 builds.
- **The documentation conflicts:**
  - `tbprobe.h` says `tb_probe_wdl` is thread-safe unless `TB_NO_THREADS` is set. It says `tb_probe_root` is **not** thread-safe and should be called once per search at the root.
  - The README says the root-probe functions are thread-safe too.
- **The maintainer's comments explain the conflict** (PR #10, "Remove note about tb_probe_root being thread unsafe", closed unmerged 2024-12-05):
  - He said the not-thread-safe note dates from the original Fathom documentation, before he took over.
  - He reported several days of testing the root-probe functions on 12 cores with no errors.
  - So the old header note survives at the pin.
- **For Fork:** DESIGN.md's plan, one DTZ root probe per search on the search thread plus WDL probes from every thread, is safe under either reading.
  - What is never safe: calling `tb_init` or `tb_free` while any probe runs, because they unmap and free the tables (source reading). Change `SyzygyPath` only when no search is running (DESIGN.md already says this).
  - Concurrent probing was not tested here; it is a Phase 6 test.

### 6.6 Windows mapping path

- **Opening:** `CreateFile` with read access, read sharing, open-existing and `FILE_FLAG_RANDOM_ACCESS`.
  - The narrow-string (ANSI) variant is used unless `_UNICODE` is defined; then the path is converted with `mbstowcs_s`.
  - Microsoft's CreateFileA page describes `FILE_FLAG_RANDOM_ACCESS` as a hint for optimising file caching. **UNVERIFIED:** whether it changes read-ahead for page faults in a mapped view. This does not matter for TCEC, which runs Linux.
  - **Caution** (source reading, not tested): defining `UNICODE` without `_UNICODE` would select the wide `CreateFile` with a narrow string and fail to compile. Fork defines neither.
- **Mapping:**
  - `GetFileSize`, then `CreateFileMapping` with `PAGE_READONLY` and the full file size, then `MapViewOfFile` with `FILE_MAP_READ` and length 0. Microsoft's pages say length 0 maps to the end of the mapping, and that read-only views need `PAGE_READONLY` or wider protection.
  - Unmapping: `UnmapViewOfFile` plus `CloseHandle`.
  - There is no Windows counterpart of the madvise call.
- **Paths:** separator `;` on Windows and `:` elsewhere. On Windows, directories are joined to file names with a backslash.
- **POSIX-only code:** `fcntl.h`, `pthread.h`, `unistd.h`, `sys/mman.h` and `sys/stat.h`, and the calls `open`, `close`, `fstat`, `mmap`, `munmap`, `posix_madvise` and `perror`, all sit in the non-`_WIN32` branch.
  - The Windows branch includes only `windows.h`, with `NOMINMAX`.
  - In the WinLibs g++ build, `pthread.h` does show up, but it comes through libstdc++'s own `<atomic>` threading headers (that toolchain's winpthreads thread model), not from Fathom (observed with `-H`).
- **MinGW builds, all observed:**
  - `tbprobe.c` compiles with llvm-mingw clang 23.1.3 and WinLibs gcc 16.2.0, as C (gnu99 and c99) and as C++20.
  - The `fathom` tool, built with either compiler (C, gnu99), probed the staged tables correctly: KQvK Win, DTZ 13, identical to Linux. A `;`-separated path list worked.
  - A C++20 build of `tbprobe.c` linked into the tool also worked with both compilers.

### 6.7 What to vendor, definitions, warnings

- **Minimum file set:**
  - `src/tbprobe.c`, the one translation unit to compile;
  - `src/tbprobe.h`, the public API;
  - `src/tbconfig.h`, which `tbprobe.h` includes with angle brackets, so the source directory must be on the `-I` path;
  - `src/tbchess.c`, which `tbprobe.c` includes as text, so it must be present but **not** compiled on its own;
  - `src/stdendian.h`, included by `tbprobe.c`;
  - `LICENSE`, because MIT requires the notice to ship with the code;
  - `README.md`, recommended because it holds the lineage credits.
  - Optional, for tests only: `src/apps/fathom.c` (the tool, 6.8).
- **Build:** compile only `tbprobe.c`, as C++ (6.4), with the Fathom source directory as an include directory.
- **Compile definitions:** none are required.
  - Never define `TB_NO_THREADS`.
  - Optional `TB_NO_HELPER_API`: the header advises engines to set it. It compiled cleanly as C++ and removes nine exported helpers (`tb_pop_count`, `tb_lsb`, the attack functions and so on).
  - Optional: a Fork copy of `tbconfig.h` earlier in the include path, for custom popcount, LSB or attack functions, or for the score constants. Those constants set the scale of `tbScore` in root results: pawn 100, mate 32000, maximum mate ply 255. So a TB win scores 31744 (observed in the tool's output). Fork can ignore `tbScore` and use `tbRank` instead.
  - Release builds should define `NDEBUG`, because Fathom uses `assert`.
- **Warnings** at `-O2 -Wall -Wextra -Wpedantic -Wshadow` (all observed):

  | Build | Warnings |
  |---|---|
  | C++20, g++ 11.4 and g++-12 (Linux), WinLibs g++ 16.2 | none; with `-march=x86-64-v3`, one `-Wsign-compare` (`tbprobe.c` line 2511) |
  | C++20, clang++ 16 and 19 (Linux, libstdc++) | one `-Wsign-compare` (line 2511) |
  | C++20, llvm-mingw clang++ 23 (libc++) | three: `-Wsign-compare` (2511), `-Wunused-but-set-global` (510, a counter set but never read), `-Wdeprecated-declarations` (744: libc++ deprecates `atomic_init` in C++20) |
  | C, gcc `-std=gnu99`/`c99` | one `-Wpedantic` (unnamed union, line 474) |
  | C, clang `-std=gnu99`/`c99` | `-Wc11-extensions` (same union) plus `-Wsign-compare`; llvm-mingw clang 23 adds `-Wunused-but-set-global` |
  | adding `-Wconversion` | many sign and narrowing conversions (at least a dozen distinct lines per compiler; output was truncated) |

  - So the Fathom target must not use `-Werror`, or must suppress these warnings. Note that `-Wunused-but-set-global` is unknown to older compilers.
  - The public header is clean: a C++20 file including `tbprobe.h`, built with Fork's flags plus `-Werror`, gave zero diagnostics on all six compilers, with and without `-march=x86-64-v3`.
- **Exported symbols** (`nm`, C++ build): besides the `tb_*` API and `TB_LARGEST`, the object exports `TB_MaxCardinality` and `TB_MaxCardinalityDTM`, plus the C++ functions `num_tables`, `first_ei`, `leading_pawn` and `encode` in the global namespace.
  - A clash needs an identical global-namespace C++ signature in Fork. Fork code inside its own namespace is safe.
  - Built as C, those names would be unmangled C symbols.
- **Behaviour Fork's spec relies on:**
  - A missing table makes the probe fail (`TB_RESULT_FAILED`, or 0 from the root-move functions); it is not an error. Observed: a 7-man PV stopped at the first capture that needed a 6-man table.
  - `tb_probe_wdl` refuses a nonzero halfmove clock (observed) and nonzero castling rights (source). It returns the failure value 0xFFFFFFFF.
  - A file whose size is not 16 mod 64 is skipped at init. Fathom then prints a line on stderr and an `info string Incomplete tablebase file ...` line on **stdout**; the suffix gets a doubled dot (source reading, not run).
  - A bad magic number prints "Corrupted table." on stderr and the probe fails (source reading).
  - **A mapping failure after a successful open calls `exit(EXIT_FAILURE)`**, ending the engine; so does running out of memory at init. Fork cannot catch these without patching (source reading, not run).
- **Root-probe results:**
  - `tb_probe_root_dtz` and `tb_probe_root_wdl` never write the `pv` or `pvSize` fields of `struct TbRootMove`; only DTM helpers that the public API does not use touch them (source reading). Ignore those fields.
  - `struct TbRootMoves` is 101,908 bytes (measured: gcc, x86-64 Linux), so keep it off small thread stacks.
  - DTZ ranks (source reading; the tool's KQvK output showed 1000 for every winning move and 0 for the drawing ones):
    - 1000 for a win whose DTZ plus the halfmove clock is at most 99, provided the caller's `hasRepeated` flag is false;
    - 1000 − (DTZ + clock) for other wins;
    - 0 for draws;
    - for losses (DTZ taken as a magnitude), −1000 while 2 × DTZ + clock is below 100, otherwise −1000 + (DTZ + clock).
  - WDL ranks: ±1000 for wins and losses, ±899 for cursed wins and blessed losses.
- **Board encoding:**
  - Squares are 8 × rank + file, so a1 = 0 and h8 = 63 (`fathom.c`'s FEN parser; consistent with every run above).
  - The en-passant argument is a square index, with 0 meaning none.
  - A root move (`TbMove`) packs the destination in bits 0-5, the origin in bits 6-11 and the promotion in bits 12-14 (1 queen, 2 rook, 3 bishop, 4 knight).

### 6.8 The `fathom` command-line tool

- **Build:** `make` in `src/apps` builds `fathom.linux` (the Makefile also has macOS and `x86_64-w64-mingw32-gcc` Windows targets).
  - Flags: `-std=gnu99 -O2 -Wall -Wshadow -DTB_NO_THREADS`. It compiles `fathom.c` together with `../tbprobe.c`.
  - Observed: it built with gcc 11.4 and with both MinGW compilers; the stripped Linux binary is 59,752 bytes.
  - The top-level Makefile builds `libfathom.so` instead; Fork does not need it.
- **Usage:** `fathom --path=DIR "FEN"`, or `TB_PATH` from the environment if `--path` is missing.
  - `--test` prints only the result (`1-0`, `1/2-1/2` or `0-1`).
  - Full output: PGN-style tags for Result, WDL (side to move) and DTZ (absolute value, in plies), then the winning, drawing and losing move lists, a pseudo-PV, and per-move rank and score lists from `tb_probe_root_dtz` and `tb_probe_root_wdl`.
  - It exits 1 with a message when no tables are found, the position has too many pieces, or the probe fails.
  - It needs the DTZ files, because it uses `tb_probe_root`.
- **Caveats for Fork's tests:**
  - The SAN strings in the move lists are sometimes malformed (observed "dd3" and "b2b3"). My reading is that the tool's disambiguation uses a file mask with file a at bit 7, while the board uses bit 0. Compare the WDL/DTZ tags or `--test` output, not SAN.
  - The tool runs the same probing code Fork will vendor. It therefore checks Fork's integration (board conversion, probe conditions, score mapping), not Fathom's table decoding.
  - Independent oracles on a different code base:
    - python-chess `chess.syzygy` (GPL-3.0+, test scripts only, never linked into the engine). Its docs cover WDL and DTZ up to 7 pieces, and say probing is thread-safe across separate board objects. **UNVERIFIED:** whether it was ported from de Man's probing code; the docs are silent.
    - The lichess API (6.9), served by shakmaty-syzygy (Rust, GPL-3.0).

### 6.9 Seven-piece test data

- **lichess tablebase API.**
  - Endpoint: `GET https://tablebase.lichess.org/standard?fen=<FEN>`, with spaces or underscores in the FEN. The lichess OpenAPI spec says the host is `tablebase.lichess.org`, not `lichess.org`; the lila-tablebase README shows the same path on `tablebase.lichess.ovh`.
  - Optional parameter `dtc` (`never`, `auxiliary` or `always`). A second endpoint, `/standard/mainline`, returns a DTZ main line, or 404 if the position is not in the tables.
  - **Response fields:**
    - Position: `category` (`win`, `unknown`, `syzygy-win`, `maybe-win`, `cursed-win`, `draw`, `blessed-loss`, `maybe-loss`, `syzygy-loss` or `loss`) plus `dtz`, `precise_dtz`, `dtc`, `dtm`, `dtw`, `checkmate`, `stalemate`, `variant_win`, `variant_loss` and `insufficient_material`.
    - `moves` (best first), each with `uci`, `san`, `category`, the same distance fields, and `zeroing`, `conversion`, `checkmate`, `stalemate`, `insufficient_material` and the variant flags.
    - Meanings: `dtz` is DTZ50'' with rounding, in plies, signed for the side to move and covering up to 7 pieces. `precise_dtz` is given only when it is known not to be rounded. `dtm` covers at most 6 pieces.
  - **Rate limits:** the general API rule is to make only one request at a time. After an HTTP 429, a minute's pause is usually enough, though some limits need longer. **UNVERIFIED:** no numeric limit is published for the tablebase host.
    - Observed: two sequential requests on 2026-10-26 got HTTP 200 with `Cache-Control: max-age=1209600` (14 days) and no rate-limit headers.
  - **Terms:**
    - The lichess terms let anyone use its services, the API included, for personal, commercial or research use, subject to limits set at Lichess's discretion. Abusing the API is prohibited.
    - **UNVERIFIED:** no licence is stated for API responses.
    - The server is lila-tablebase (AGPL-3.0, built on shakmaty-syzygy). Its answers are exact tablebase facts, not engine evaluations, which data-policy.md allows. Fork uses them only as cached test fixtures (DESIGN.md: fetched once, cited, cached).
- **Smallest downloadable 7-man table: KPPPPPvK** (king and five pawns against king).
  - WDL: https://tablebase.lichess.ovh/tables/standard/7/6v1_pawnful/KPPPPPvK.rtbw. 3,721,360 bytes (3.55 MiB), SHA-256 `f2e587b1acd940ef836ea80e0c64eb6093255b8273e1f8b049ab8f9f2631cc0b`.
  - DTZ: https://tablebase.lichess.ovh/tables/standard/7/6v1_pawnful/KPPPPPvK.rtbz. 1,652,304 bytes (1.58 MiB), SHA-256 `397a03d6d11823b2ead174c14f0c9e0a9be54c5b4b30890715a36d5fd1c16519`.
  - Sizes come from `checksums/bytes.tsv` (niklasf/syzygy-tables.info master `09a5a9cd`) and the hashes from the mirror's `sha256` list. Both files were downloaded on 2026-10-26: sizes matched Content-Length and hashes matched the list. Last-Modified was 2018-04-24.
  - The next-smallest files are KNNNNNvK.rtbw (6,957,648 bytes) and KQQQQQvK.rtbz (6,513,424 bytes). The next-smallest WDL+DTZ pair is KNPPPPvK (35.44 MiB).
  - Mirror layout: `7/` has six subdirectories (`4v3_`, `5v2_`, `6v1_` × `pawnful`/`pawnless`). The mirror's `download.txt` lists the URLs above.
  - **Limit:** without the 6-man tables, a WDL probe only works where the side to move has no capture available, because Fathom resolves captures by probing the smaller tables before its own (source reading; observed in the PVs). A root DTZ probe also needs every line it explores to stay capture-free. Pick test positions accordingly, like the two in 6.3, whose root probes succeeded.

- **Sources** (full list in sources.md, "Fathom and Syzygy probing, Phase 3 deliverable 7"):
  - https://github.com/jdart1/Fathom at `c9c6fef0`, with PRs #10, #11 and #16 and issues #14 and #17; PR #13 was identified from issue #14's closing comment and the git history;
  - https://github.com/basil00/Fathom (2026-10-23 pass only);
  - man7 posix_madvise(3) and madvise(2);
  - kernel `Documentation/filesystems/proc.rst`;
  - Microsoft's CreateFileA, CreateFileMappingA and MapViewOfFile pages;
  - lichess-org/api and lichess-org/lila-tablebase;
  - https://lichess.org/terms-of-service;
  - niklasf/syzygy-tables.info and https://tablebase.lichess.ovh/tables/standard/.
  - Verified 2026-10-26 (the first pass was 2026-10-23).

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
| OpenBench "Data Generation Workloads" | USE | GPL-3.0 | Read 2026-10-24 (wiki page Data-Generation-Workloads): a datagen workload runs the dev engine as `./engine "genfens N seed S book <None\|file> <extra>" "quit"`; the engine must print N lines `info string genfens <fen>` (opening positions it generates itself), seeding its RNG from all 64 bits of S (upper 32 = workload id, lower 32 = book offset); a worker is aborted if 15 s pass without a new line. Extra "Genfens Args" are passed through; "Play Reverses" defaults to No for fixed-node/depth self-play. Fork would need a `genfens` command to use it (a Phase 7+ tooling item). |

Fork's datagen should be Fork's own code. Self-play with random-move openings, positions written in viriformat (or a Fork-defined format), and provenance logged as DESIGN.md requires.

---

## 9. Profilers

| Tool | Tag | License | Version | Notes |
|---|---|---|---|---|
| **perf** | USE | GPL-2.0 (resolved 2026-10-24: it lives in the kernel tree at `tools/perf`; the kernel's `COPYING` declares `GPL-2.0 WITH Linux-syscall-note` and perf sources such as `tools/perf/builtin-stat.c` carry `SPDX-License-Identifier: GPL-2.0-only`). A standalone tool, not linked into Fork. | distro package (`linux-tools-generic`; on the local Ubuntu 26.04.1 WSL `/usr/bin/perf` belongs to `linux-perf` 7.0.0-38.38 and reports perf version 6.18.54.1) | Commands: `perf stat`, `record`, `report`, `annotate`, `top`. **WSL2 works on this machine** (run 2026-10-24, kernel 6.18.54.1-microsoft-standard-WSL2): `perf stat -e task-clock,cycles,instructions true` returned real cycle and instruction counts (user mode, `:u`), and `perf record -e cycles` captured 908 samples that `perf report` resolved. Kernel-mode counting was not tried. |
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

## 11. Cloud compute for test matches

### Cloud SPRT: GitHub Actions and AWS facts (2026-10-27)

**What it is.** The facts needed before writing tooling that shards Fork-vs-Fork SPRT matches
(fastchess, 8+0.08 s, thousands of games) across (A) GitHub-hosted runners on the public repo
BOSSDOTCOM/fork and (B) one AWS EC2 Spot Instance (c7a.16xlarge or c8a.16xlarge).
**Why it matters for Fork:** test infrastructure (match runner orchestration), Phase 3 onward
(SPRT gating of search changes), later Phase 4 re-validation. **Date verified:** 2026-10-27 for
every item below. **Tags:** GitHub Actions: USE, within the terms quoted in A1; AWS EC2 Spot: USE
(paid service, owner's account). **Licence:** not applicable (service terms, not software
licences). Source rows are in [sources.md](sources.md), section "Cloud SPRT".

GitHub Docs pages were read as markdown through the docs site's article endpoint
(`https://docs.github.com/api/article/body?pathname=/en/...`), which serves the same article body
as the HTML page. AWS pages were fetched with curl and converted to text locally.

#### A. GitHub Actions

**A1. Permitted use (terms).** Source:
[GitHub Terms for Additional Products and Features](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features),
"Version Effective Date: August 27, 2026", section "Actions". Exact wording:

> Actions and any elements of the Actions product or service may not be used in violation of the Agreement, the GitHub Acceptable Use Policies, or the GitHub Actions service limitations set forth in the Actions documentation. Additionally, regardless of whether an Action is using self-hosted runners, Actions should not be used for:
>
> * Cryptomining;
> * Disrupting, gaining, or attempting to gain unauthorized access to, any service, device, data, account, or network (other than those authorized by the GitHub Bug Bounty program);
> * The provision of a stand-alone or integrated application or service offering the Actions product or service, or any elements of the Actions product or service, for commercial purposes;
> * Any activity that places a burden on our servers, where that burden is disproportionate to the benefits provided to users (for example, don't use Actions as a content delivery network or as part of a serverless application, but a low benefit Action could be ok if it’s also low burden); or
> * If using GitHub-hosted runners, any other activity unrelated to the production, testing, deployment, or publication of the software project associated with the repository where GitHub Actions are used.

and, from the same section:

> In order to prevent violations of these limitations and abuse of GitHub Actions, GitHub may monitor your use of GitHub Actions. Misuse of GitHub Actions may result in termination of jobs, restrictions in your ability to use GitHub Actions, disabling of repositories created to run Actions in a way that violates these Terms, or in some cases, suspension or termination of your GitHub account.

(Link targets inside the quoted bullets were dropped; the words are unchanged.)

[GitHub Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies),
section "4. Spam and Inauthentic Activity on GitHub", which opens "We do not allow content or activity on GitHub that is:", lists among others:

> * automated excessive bulk activity and coordinated inauthentic activity, such as
>   * spamming
>   * cryptocurrency mining;

> * using our servers for any form of excessive automated bulk activity, to place undue burden on our servers through automated means, or to relay any form of unsolicited advertising or solicitation through our servers, such as get-rich-quick schemes;

Reading for Fork (my interpretation, not a GitHub ruling): SPRT matches of Fork's own builds
are testing of the software project in the repository where the workflow runs, so they fall
inside the GitHub-hosted-runner clause. The "burden ... disproportionate to the benefits" clause
and the AUP's "excessive automated bulk activity" are judgement calls GitHub makes; no GitHub page
defines a threshold. **UNVERIFIED:** whether GitHub considers sustained, all-runner engine-match
workloads acceptable; no GitHub statement on this kind of workload was found. Running other
people's engines, or using runners as general compute unrelated to Fork, would fall outside the
clause.

**A2. Billing for public repositories.** Source:
[GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
(the older path `/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions`
returns the identical article).
- Usage is free for self-hosted runners and for public repositories that use standard GitHub-hosted runners; the per-plan quota of minutes, artifact storage and cache storage is described as applying to private repositories.
- "The use of standard GitHub-hosted runners is free" in public repositories (also for Pages and Dependabot).
- Larger runners are always charged, even in public repositories, and are blocked until a payment method is set up. Larger runners exist only for organizations and enterprises on GitHub Team and Enterprise Cloud ([runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), "Larger runners").
- Which sizes are "standard": the labels in the table in A3 (the runners reference section "Standard GitHub-hosted runners for public repositories" says their use "is free and unlimited on public repositories"). For comparison, the [runner pricing reference](https://docs.github.com/en/billing/reference/actions-runner-pricing) lists private-repo rates (Linux 2-core x64 $0.006 per minute; minutes rounded up per job).

**A3. Standard Linux runner hardware, public repositories.** Source:
[GitHub-hosted runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
"Standard GitHub-hosted runners for public repositories".

| Label(s) | CPU | RAM | SSD | Arch |
|---|---|---|---|---|
| `ubuntu-latest`, `ubuntu-24.04`, `ubuntu-22.04`, `ubuntu-26.04` | 4 | 16 GB | 14 GB | x64 |
| `ubuntu-24.04-arm`, `ubuntu-22.04-arm`, `ubuntu-26.04-arm` | 4 | 16 GB | 14 GB | arm64 |
| `ubuntu-slim` (container on a shared VM) | 1 | 5 GB | 14 GB | x64 |

Private repositories get 2 CPU / 8 GB / 14 GB on the same Ubuntu labels. `ubuntu-slim` jobs have
a 15-minute job timeout and are described as unsuitable for heavy builds. Linux and Windows
runners are VMs in Microsoft Azure
([About GitHub-hosted runners](https://docs.github.com/en/actions/using-github-hosted-runners/using-github-hosted-runners/about-github-hosted-runners)).
**UNVERIFIED:** the CPU model and whether the 4 "Processor (CPU)" units are physical cores or SMT
threads; the docs give neither. Measure on a runner (`lscpu`) before relying on per-core nps.

**A4. Limits.** Source: [Actions limits](https://docs.github.com/en/actions/reference/limits)
(the page says the limits "are subject to change"), plus the pages named per row.

| Limit | Figure | Source |
|---|---|---|
| Concurrent jobs, standard runners, GitHub Free | 20 total (5 macOS); Pro 40, Team 60, Enterprise 500; Support can raise them | Actions limits, "Job concurrency limits" |
| Job execution time, GitHub-hosted | 6 hours; the job is terminated and fails | Actions limits |
| `timeout-minutes` | job default 360; step maximum 360 | [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) |
| Workflow run time | 35 days per run, including waiting and approval time | Actions limits |
| Matrix | 256 jobs per workflow run (hosted and self-hosted) | Actions limits; Workflow syntax |
| Re-runs | 50 per workflow run | Actions limits |
| Queued runs | 500 workflow runs per 10 seconds; trigger events 1500 per 10 s per repository | Actions limits |
| `workflow_dispatch` inputs | at most 25 top-level properties; payload at most 65,535 characters; types `boolean`, `choice`, `number`, `environment`, `string`; trigger only fires when the workflow file is on the default branch | Workflow syntax, `on.workflow_dispatch.inputs`; [Manually running a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow) ("up to 25") |
| Artifact retention, public repo | default 90 days, settable from 1 to 90 days (private: 1 to 400); per-artifact `retention-days` cannot exceed the repository limit. Since 2026-10-01 the same retention also covers checks, workflow runs and commit statuses | [Managing GitHub Actions settings for a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository); [Store and share data](https://docs.github.com/en/actions/tutorials/store-and-share-data) |
| Artifacts per job | 500 (`actions/upload-artifact` README on `main`; latest release v7.0.2, published 2026-10-07; artifacts from v4 on are immutable, replaceable only with `overwrite: true`) | [upload-artifact README](https://github.com/actions/upload-artifact) |
| Artifact storage quota | GitHub Free 500 MB (shared with Packages), cache 10 GB per repository; usage updates every 6 to 12 hours | Actions limits, "Storage limits"; billing page |
| Cache retention, public repo | default 7 days, up to 90 | repository settings page |
| `GITHUB_TOKEN` API rate | 1,000 requests per hour per repository | Actions limits |

**UNVERIFIED:** whether the 500 MB artifact storage quota is enforced for public repositories.
The billing page ties the quota to private repositories and says public-repo usage on standard
runners is free, but the storage table itself does not separate public from private. Keep match
artifacts small (PGN and result files) and set short `retention-days` regardless.
**UNVERIFIED:** which GitHub plan the BOSSDOTCOM account is on (the plan field is not public); the
20-job figure applies if it is GitHub Free.

#### B. AWS EC2 Spot

**B5. Instance specs.** Source:
[Specifications for Amazon EC2 compute optimized instances](https://docs.aws.amazon.com/ec2/latest/instancetypes/co.html),
"Performance specifications"; [C7a product page](https://aws.amazon.com/ec2/instance-types/c7a/);
[C8a product page](https://aws.amazon.com/ec2/instance-types/c8a/).

| | c7a.16xlarge | c8a.16xlarge |
|---|---|---|
| vCPUs / cores / threads per core | 64 / 64 / 1 | 64 / 64 / 1 |
| Memory | 128 GiB | 128 GiB |
| Processor (docs table) | AMD EPYC 9R14 | AMD EPYC 9R45 |
| Generation (product page) | 4th gen EPYC, code name Genoa, max 3.7 GHz | 5th gen EPYC, formerly code named Turin, max 4.5 GHz |
| SMT | none: product page says every vCPU is a physical core | none: same statement |
| Nitro | v4 | v6 |
| Network (docs) | 25 Gigabit | 30 Gigabit |

C7a also lists AVX-512, VNNI and bfloat16 support on its product page. **C8a availability:**
general availability announced 2025-12-02 in
[What's New](https://aws.amazon.com/about-aws/whats-new/2025/12/compute-optimized-amazon-ec2-c8a-instances/)
(launch Regions US East (N. Virginia), US East (Ohio), US West (Oregon); Savings Plans, On-Demand
and Spot). The current
[instance types by Region](https://docs.aws.amazon.com/ec2/latest/instancetypes/ec2-instance-regions.html)
page lists C8a in us-east-1, us-east-2, us-west-2, ap-northeast-1, eu-central-1, eu-west-1 and
eu-south-2; C7a is listed in us-east-1. The Region page lists families, not sizes or
Availability Zones: **UNVERIFIED** which us-east-1 AZs offer c8a.16xlarge (check with
`aws ec2 describe-instance-type-offerings --location-type availability-zone`, not run).

**B6. Prices, us-east-1, Linux.**
- On-Demand, from the AWS Price List bulk file
  `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv`
  (Publication Date 2026-10-23T22:13:55Z, Version 20261023221355; rows filtered locally to
  TermType OnDemand, Linux, Shared tenancy, no pre-installed software, CapacityStatus Used):
  - c7a.16xlarge **$3.28448 per hour** (EffectiveDate 2026-10-01, SKU 4UQPTQNA6W2TZ4Q8);
  - c8a.16xlarge **$3.44864 per hour** (EffectiveDate 2026-10-01, SKU 5PKRJNJJEJJQCWX9).
  The [On-Demand pricing page](https://aws.amazon.com/ec2/pricing/on-demand/) renders its table
  in JavaScript, so the figures above come from the Price List, not the rendered page.
- Spot, live figure: the [Spot pricing page](https://aws.amazon.com/ec2/spot/pricing/) says its
  table is updated every 5 minutes and shows the lowest price per instance type in the Region. Its
  data file (`https://website.spot.ec2.aws.a2z.com/spot.json`, referenced by the page) read at
  about 2026-10-27T19:50Z gave us-east-1 Linux **c7a.16xlarge $0.9276/h** and **c8a.16xlarge
  $0.9533/h**. This is a snapshot, not a planning constant: Spot prices move, and the figure is
  the Region's lowest AZ price.
- How to get the current price: `aws ec2 describe-spot-price-history` with
  `--instance-types`, `--product-descriptions "Linux/UNIX"`, optional `--availability-zone`, and
  `--start-time`/`--end-time` (history goes back at most 90 days; with a time range the call also
  returns the last price change before the start time, i.e. the price in effect at the start)
  ([CLI reference, AWS CLI 2.38.6](https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-spot-price-history.html);
  [Spot price history guide](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-spot-instances-history.html)).
  At launch a Spot Instance pays the current Spot price, never more than the On-Demand price.
- Typical savings: the Spot pricing page says "up to 90%" off On-Demand. The
  [Spot Instance Advisor](https://aws.amazon.com/ec2/spot/instance-advisor/) shows 30-day
  averages of savings and interruption frequency. Its data file
  (`https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json`) for us-east-1 Linux gives
  c7a.16xlarge `s: 55, r: 2` and c8a.16xlarge `s: 61, r: 3`, where the file's `ranges` table maps
  index 2 to "10-15%" and 3 to "15-20%". Read as: c7a.16xlarge about 55% savings with a 10-15%
  interruption frequency; c8a.16xlarge about 61% with 15-20%. **UNVERIFIED:** that `s` is savings
  percent and `r` the interruption-range index; the JSON carries no field documentation and the
  rendered advisor table was not visible (JavaScript). The live Spot price implies about 72%
  below On-Demand for both, so the 30-day average and today's snapshot differ.

**B7. Interruption signals.** Sources:
[Spot Instance interruption notices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html),
[Rebalance recommendations](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/rebalance-recommendations.html),
[Instance Metadata Service](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html).
- The interruption notice comes two minutes before EC2 stops or terminates the instance (no
  two-minute warning when the behaviour is hibernate). It is best effort; AWS recommends polling
  every 5 seconds. It also arrives as an EventBridge event "EC2 Spot Instance Interruption Warning".
- Metadata item: `http://169.254.169.254/latest/meta-data/spot/instance-action`, returning JSON
  with `action` (`stop`, `terminate` or `hibernate`) and `time` (UTC); HTTP 404 when no
  interruption is pending. `spot/termination-time` is kept only for backward compatibility.
- IMDSv2: first `PUT http://169.254.169.254/latest/api/token` with header
  `X-aws-ec2-metadata-token-ttl-seconds` (TTL from 1 second to 6 hours; the docs use 21600), then
  send `X-aws-ec2-metadata-token: <token>` on each GET; the token can be reused until it expires.
  run-instances `--metadata-options HttpTokens=required` disables IMDSv1.
- Rebalance recommendation: metadata item `latest/meta-data/events/recommendations/rebalance`,
  returning `{"noticeTime": "<UTC>"}` when emitted; EventBridge event "EC2 Instance Rebalance
  Recommendation". It signals elevated interruption risk, may come earlier than the two-minute
  notice or together with it, is best effort, and AWS recommends checking every 5 seconds.
  Supported for Spot Instances launched after 2020-11-05.

**B8. Launch command.** Source:
[aws ec2 run-instances, AWS CLI 2.38.6](https://docs.aws.amazon.com/cli/latest/reference/ec2/run-instances.html);
[Spot interruption behaviour](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/interruption-behavior.html).
- `--instance-market-options`, JSON form:
  `{"MarketType": "spot", "SpotOptions": {"SpotInstanceType": "one-time", "InstanceInterruptionBehavior": "terminate"}}`.
  Other `SpotOptions` keys: `MaxPrice` (AWS advises against it: it raises interruptions; omitted
  means the current Spot price is paid), `ValidUntil` (persistent requests only),
  `BlockDurationMinutes` (deprecated). With run-instances, persistent requests need stop or
  hibernate, so a one-time request with terminate is the valid pairing. Terminate is also the
  default interruption behaviour.
- `--instance-initiated-shutdown-behavior terminate` (values `stop` | `terminate`, default
  `stop`): an OS shutdown from inside the instance then terminates it.
- c7a.16xlarge and c8a.16xlarge both appear in the CLI's `--instance-type` value list.
- Ubuntu 22.04 AMI: Canonical's
  [Find Ubuntu images on AWS](https://documentation.ubuntu.com/aws/aws-how-to/instances/find-ubuntu-images/)
  gives the template `/aws/service/canonical/ubuntu/{product}/{release}/stable/{serial}/{arch}/hvm/{vol}/ami-id`
  with volume type `ebs-gp2` for releases up to 23.04, which yields
  `/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id`. It can be
  passed directly as `--image-id resolve:ssm:<parameter>` (Canonical's page shows the form; AWS's
  [public-parameter page](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/finding-an-ami-parameter-store.html)
  documents `resolve:ssm:` for its own AMIs). **UNVERIFIED:** that this exact parameter resolves
  today; it is built from the template, and `aws ssm get-parameters` was not run (no AWS
  credentials on this machine).

**B9. Per-second billing.** Source: [On-Demand pricing page](https://aws.amazon.com/ec2/pricing/on-demand/):
On-Demand capacity is paid by the hour or second with a 60-second minimum, and partial hours are
billed per second for Linux (SUSE is billed by the full hour).
[Billing for interrupted Spot Instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/billing-for-interrupted-spot-instances.html):
for Linux (not SUSE), if you stop or terminate the Spot Instance yourself you pay for the seconds
used; if EC2 interrupts it in the first hour there is no charge, and after the first hour you pay
for the seconds used. **UNVERIFIED:** that the 60-second minimum applies to Spot as well; the Spot
billing page does not state a minimum.

---

### Cloud SPRT: the tools and how to run them (2026-10-27)

Tag: **USE** (Fork's own tooling, in the main repository: `tools/cloud/`,
`.github/workflows/sprt.yml`). Facts and prices: the section above.

**How a sharded SPRT works.** One SPRT is split into shards. Every shard
plays the same two Fork commits at the same conditions as `tools/sprt.sh`
(Hash, one thread, the same adjudication, each opening with both colours)
on its own slice of `UHO_Lichess_4852_v1.epd` (sequential order: shard *i*
of stage *s* starts at opening 1 + (s·N + i)·G/2; the book has 2,632,036
positions, so slices never overlap), for a fixed number of games, and
records its pentanomial counts. Pairs are independent, so the counts add
up and the combined SPRT is the SPRT on the sum. A stage is one batch of
shards; if the merged LLR is still between the bounds, run the next stage
(new openings) and merge every stage's results. Looking only at stage
boundaries makes the test slightly conservative, never anti-conservative.

**The pieces** (all tested locally, 2026-10-27):
- `tools/cloud/sprt_merge.py`: `snapshot` (a shard's counts from its
  fastchess log: pairs counted from the finished games themselves, games
  2k-1 and 2k sharing an opening, so a shard stopped between fastchess's
  periodic reports keeps every finished pair; on two complete 5,000-game
  logs the counts equal fastchess's own, bin for bin) and `merge` (sums the
  counts, refuses shards of different commits or conditions, or two shards
  with the same openings, and prints Elo, nElo, LLR and the verdict). The
  statistics are fastchess's normalized model; Elo, nElo and their error
  bars match fastchess on 18 of Fork's logged SPRTs to its two decimals,
  the LLR to within 0.01 (fastchess's own computation differs slightly, so
  a verdict within 0.01 of a bound wants more games). Tests:
  `tools/cloud/test_sprt_merge.py`.
- `tools/cloud/run_shard.sh`: one shard; writes `result.json` every minute
  and on exit, runs a checkpoint command (e.g. an S3 upload), and on SIGTERM
  stops fastchess and records status `interrupted`. Tested: a complete
  8-game shard, and a 40-game shard stopped by SIGTERM after 45 s that kept
  its 3 finished pairs; their merge.
- `tools/cloud/build_pair.sh`: both commits built as TCEC builds Fork
  (`update.sh`, on Ubuntu 22.04 with `CXX=g++`, gcc 11.4, `x86-64-v3`).
- `tools/cloud/fetch_tools.sh`: the pinned fastchess release
  (v1.8.2-alpha, SHA-256 checked) and the book (official-stockfish/books at
  a804a97e, the unpacked file's SHA-256 checked).
- `.github/workflows/sprt.yml` (GitHub Actions): manual
  (`workflow_dispatch`), only in BOSSDOTCOM/fork, one at a time (a
  concurrency group). A build job in an `ubuntu:22.04` container, at most
  **16 shard jobs** (`max-parallel: 16`, against the Free plan's 20
  concurrent jobs, so CI can still run), a merge job writing the verdict
  to the run summary. Inputs: base, test, bounds, tc, hash, games, shards,
  stage, test and base options; they reach the shell only through
  environment variables. **Not run yet** (the owner starts the first run;
  the workflow must be on the default branch for `workflow_dispatch`, so it
  works once milestone-c is merged into main).
- `tools/cloud/aws_spot_sprt.sh` (AWS): run on the owner's machine with the
  owner's AWS CLI configuration; launches one one-time spot instance per
  shard (c7a or c8a), Ubuntu 22.04 from the Canonical SSM parameter, with an
  instance profile the owner creates (only `s3:PutObject` on the result
  prefix). The instance arms a shutdown after `--max-hours` (default 3:
  the cost cap), builds, plays with every vCPU but two, uploads
  `result.json` every minute, polls the interruption notice every 5 s
  (IMDSv2) and on one stops the shard so its pairs are uploaded, then
  uploads the log and games and shuts down, which terminates it.
  `--dry-run` prints the instance's script without calling AWS (checked:
  it parses). **Not run** (no AWS account here); the SSM parameter and the
  launch options follow the section above. No credentials, account ids or
  bucket names are in the repository.

**Terms (GitHub).** The Actions terms allow GitHub-hosted runners only for
"the production, testing, deployment, or publication of the software
project associated with the repository" and forbid activity that "places a
burden on our servers, where that burden is disproportionate to the
benefits provided to users" (quotes and source above). Fork's use is
testing its own changes: two of its own commits, at most 16 jobs, one SPRT
at a time, manual starts only. Whether sustained engine matches stay within
"disproportionate burden" is GitHub's judgement: **UNVERIFIED**; keep runs
occasional and say so if GitHub asks.

**Cost of one 5,000-game SPRT at 8+0.08** (estimates; the throughput is
measured, the setup times are not). Throughput: games run on the clock, so
a game slot plays about **148 games per hour** at 8+0.08 whatever the CPU
(measured on the owner's machine: 1,478 games per hour at concurrency 10,
DESIGN.md §5.2 testing conditions).

| Option | Slots | Games per hour | Wall time | Cost |
|---|---|---|---|---|
| Local (7600X3D, concurrency 10) | 10 | about 1,480 | about 3.4 h | electricity only |
| GitHub Actions, 16 jobs × 3 games (4-CPU runners) | 48 | about 7,100 | about 42 min of games + about 5 min setup per job (UNVERIFIED), about 50 min | **$0**: standard runners are free and unlimited in public repositories (about 760 runner-minutes, not billed) |
| AWS c7a.16xlarge spot, 1 instance, 62 games | 62 | about 9,200 | about 33 min + about 8 min boot and build (UNVERIFIED), about 41 min | about **$0.63** at the 2026-10-27 snapshot of $0.9276/h (on-demand $3.28448/h: about $2.25) |
| AWS c8a.16xlarge spot, 1 instance | 62 | about 9,200 (the faster CPU searches deeper, not faster) | about 41 min | about **$0.65** at $0.9533/h (on-demand $3.44864/h: about $2.36) |
| AWS c7a.16xlarge spot, 2 instances | 124 | about 18,400 | about 17 + 8 = 25 min | about $0.78 (the fixed setup is paid twice) |

Billing is per second (a 60-second minimum on-demand); a spot instance
interrupted by AWS in its first hour is not charged; disk and S3 cost
cents at most. Spot prices move all the time: check
`aws ec2 describe-spot-price-history` before a run. The Spot Instance
Advisor's interruption frequency (30-day): c7a.16xlarge 10-15%, c8a.16xlarge
15-20%; an interrupted shard keeps its finished pairs, and the missing games
are run as a further stage. Caveats: GitHub's 4 CPUs may be SMT threads
(**UNVERIFIED**); if a shard shows time losses, run 2 games per job instead
of 3 (32 slots, about 63 min). Time losses are counted per shard and in the
merge.

## UNVERIFIED items (summary)

1. ~~Which Ubuntu release ships Qt ≥ 6.8; whether the AppImage contains `cutechess-cli`.~~ Resolved 2026-10-24 (§ cutechess: 25.04 first, 26.04 first LTS; AppImage has `usr/bin/cutechess-cli`).
2. ~~Whether `movecount` counts plies or moves.~~ Resolved 2026-10-24: full moves, both engines' evals in one counter (§ mapping paragraph). Still open: whether TCEC's draw rule needs both engines' evals (TCEC rule text is silent).
3. ~~Fishtest's licence~~ (resolved 2026-10-24: none declared). Still open: the inputs of the Fishtest SPRT calculator (bot wall; not re-checked this pass).
4. BayesElo: no version number, no checksum, no maintained repo (kept: the author's page publishes none; not re-checked this pass).
5. Where TCEC publishes its opening books (FAQ silent; kept). ~~Which piece count TCEC gives engines~~ resolved: 7-man (`config/tcec.json`).
6. Whether TCEC has ruled on Fathom's Cfish-derived `tbprobe.c` lineage (kept on 2026-10-26: no TCEC page mentions Fathom; a question for TCEC's Discord before applying).
7. How each Stockfish-repo book was built (which engine evaluated it) (kept: the books README does not say; provenance rule makes them test-only anyway).
8. ~~perf's licence and perf/hardware counters under WSL2~~ resolved 2026-10-24 (GPL-2.0; counters and sampling work locally). Still open: VTune's release date and AMD/WSL support (not re-checked this pass).
9. A standalone marlinformat repo, the "carbon" trainer and Scid (not re-checked this pass). ~~OpenBench's datagen details~~ resolved 2026-10-24.
10. pgn-extract checksum (upstream publishes none; kept). Apt versions are distro-decided; on the local Ubuntu 26.04.1 WSL (2026-10-24): `linux-perf` 7.0.0-38.38, `valgrind` 1:3.26.0-0ubuntu1.
11. Test suites (2026-10-25, §4 "Tactical and mate suites"): who made the WAC EPD; whether WAC was first published in 1945 or 1958; WAC's copyright status; Szabo's 2001 correction list (archive dead); whether TerjeKir's `wac-revised.epd` is Silver's 201-position set; where ChestUCI/matetrack positions came from; whether YACPDB or other problem databases offer a licensed dump; mate lengths #3 to #5 in the matetrack subset (only #1 and #2 checked by brute force).
12. Fathom, from the 2026-10-26 pass (§6):
    - whether `FILE_FLAG_RANDOM_ACCESS` affects page-fault read-ahead on Windows mapped views (Microsoft documents it only as a file-caching hint);
    - Fathom's behaviour under concurrent probing: not tested; it is a Phase 6 test, and the evidence so far is the source plus the maintainer's PR #10 report;
    - the error paths, which I read but did not exercise: an incomplete file printing on stdout, the bad-magic message, and the `exit()` calls on mapping failure and out of memory.
13. lichess tablebase API (§6.9): no numeric rate limit is published for `tablebase.lichess.org`; no licence is stated for API responses.
14. Whether python-chess's `chess.syzygy` was ported from Ronald de Man's probing code or written independently (its docs are silent; either way it is a code base separate from Fathom).
15. Cloud SPRT (§11, 2026-10-27): whether GitHub accepts sustained engine-match workloads under the "disproportionate burden" clause (no GitHub statement found); the CPU model and core/thread nature of the 4-CPU public runner; whether the 500 MB artifact quota applies to public repos; the owner's GitHub plan; which us-east-1 AZs offer c8a.16xlarge; the meaning of the Spot Advisor JSON fields `s` and `r`; whether the Ubuntu 22.04 SSM parameter built from Canonical's template resolves (not queried, no AWS credentials); whether the 60-second minimum applies to Spot.

## OFF-LIMITS (summary)

- Stockfish source code, including the `tools` branch `generate_training_data`.
- Stockfish and Leela nets, and any network not trained by Fork.
- Stockfish and Leela training datasets and binpacks, and any data generated or rescored by another engine.
- nnue-pytorch, marlinflow, Grapheus and CudAD code may be read but not copied (REFERENCE ONLY). Running nnue-pytorch to produce Fork's nets is advised against.
