# Sources

## How these were opened

- **Who opened them.** Every external page below was opened on
  **2026-11-10** by one of six clean-room survey agents, which reported in
  prose. This write-up opened no web page: it condenses their reports and
  reads Fork's own repository.
- **How.** Pages were read through the GitHub and GitLab APIs (README,
  release, PR, issue and commit text; licence detection) or by plain fetch.
  TCEC wiki pages were fetched with a browser User-Agent.
- **What was not opened.** No engine repository was cloned, and no engine
  source file, diff or code view was opened. The agents reported deleting
  their downloaded prose copies.
- **Licences.** Where a licence is given in the survey, it comes from
  GitHub or GitLab licence detection or the README, not the licence text,
  unless noted.
- **Missing logs.** KB rule 6 asks for every page to be logged in the KB's
  `docs/kb/sources.md`. The survey agents were told to write no files, so
  that log was not updated. This file is the complete list, ready to be
  copied there.

## Fork's own files (read 2026-11-10, branch `origin/phase-4` at 95f49c7)

- `docs/research/phase4-think-tank/phase-b-specialists.md` (B1-B3: S1, S2
  with the Stormphrax supplement, S3) and `phase-c-synthesis.md` (R1-R41,
  X1-X23).
- `docs/DESIGN.md`:
  - "Search constants";
  - training-data decisions;
  - §5.6, including the order;
  - the decisions log through 2026-11-10.
- `docs/history/phase-3/sprt-log.md`, `docs/history/phase-4/sprt-log.md`.
- `docs/ideas.md` (ideas 1-71) and `docs/nets.md`.
- Feature switches and a few lines of Fork's own code:
  - `src/search/searcher.hpp` (the switch list);
  - `src/search/searcher.cpp` (TT cutoff and qsearch TT use);
  - `src/search/trans_table.hpp` and `.cpp` (entry fields, store rule,
    prefetch);
  - `src/datagen/self_play.cpp` (per-game clearing);
  - the file list of `src/eval/`.

## CCRL

- https://computerchess.org.uk/404/ — CCRL Blitz, all engines, best
  versions; "Computed on November 7, 2026". The reference list. Reached by
  redirect from https://computerchess.org.uk/ccrl/404/.
- https://computerchess.org.uk/4040/ — the 40/15 list of the same date (not
  used).
- https://computerchess.org.uk/ccrl/ — home page (the originality
  statement).
- https://computerchess.org.uk/404/cgi/compare_engines.cgi?class=Single-CPU+engines&only_best_in_class=on&num_best_in_class=1&print=Rating+list
  — the single-CPU view (families 2 and 3).
- engine_details.cgi pages (computerchess.org.uk/404/cgi/engine_details.cgi)
  for all 50 engines, for notes, authors and homepages.
- **Failed:** https://computerchess.org.uk/ccrl/404/rating_list_best.html
  (HTTP 404).

## Stockfish, Torch, Dragon, Ethereal (family 1)

**Stockfish and its trainer:**
- github.com/official-stockfish/Stockfish commit messages since 2026-09-05,
  including:
  - search and time management: 598ae2c4, 0c5892a9, 9c11e231, 3a7b56a4,
    7a372f3f, 0f602f90, 5ca4bfe7, 61c68717, 400c23f9, 513ce075, a35e229e,
    1548538e, ff3a6c50;
  - networks: 5c4cef0b, ff7cee42, 26647279, e08dfa80;
  - training: def601cc, 2d54ef33, bc944563;
  - other: 6a9ec5c3, dbe600b7.
- Issue comments on PRs #7215, #7265, #7296, #7301, #7213, #7153.
- https://raw.githubusercontent.com/official-stockfish/nnue-pytorch/master/docs/nnue_architecture_history.md
- nnue-pytorch PRs #563, #570 and recent commit titles.
- vondele/nettest PRs #462, #488, #537, #584, #587, #560, #562, #564, #565,
  #566, #575, #576, #580, #588, #590, #591, #592.
- https://wiki.chessdom.org/Stockfish_questionnaire_20251019

**Torch:**
- https://www.chess.com/news/view/torch-chess-engine
- https://www.chess.com/news/view/torch-engine-available-on-chesscom
- https://www.chessprogramming.org/Torch
- https://talkchess.com/viewtopic.php?p=965569 (via p=965599)
- https://talkchess.com/viewtopic.php?p=981490
- https://www.chessdom.com/torch-enters-tcec-season-29/ (WebFetch returned
  429; read with curl)
- https://wiki.chessdom.org/Torch_questionnaire_20250620 (confidential)
- https://wiki.chessdom.org/Plentychess_questionnaire_20251012
- https://wiki.chessdom.org/Tarnished_questionnaire_20251016
- https://wiki.chessdom.org/Engines_by_TCEC_Questionnaire
- https://wiki.chessdom.org/Current_Engine_Status
- a TCEC wiki search for "Torch".

**Dragon:**
- https://www.chessprogramming.org/Komodo
- https://www.chessprogramming.org/Dragon_by_Komodo_Chess
- https://talkchess.com/viewtopic.php?p=870317
- https://talkchess.com/viewtopic.php?p=872672
- https://talkchess.com/forum3/viewtopic.php?f=2&t=82669
- https://talkchess.com/forum3/viewtopic.php?f=2&t=81715
- https://talkchess.com/viewtopic.php?p=925166 (page 2 only)
- Wayback Machine copies of komodochess.com dragon-3.3.htm, dragon-3.htm,
  dragon-2.htm
- https://wiki.chessdom.org/KomodoDragon_questionnaire_20251108

**Ethereal:**
- https://github.com/AndyGrant/Ethereal (README, releases v12.50-v14.00,
  the last 100 commit messages)
- http://chess.grantnet.us/Ethereal/
- https://talkchess.com/viewtopic.php?p=953753
- https://talkchess.com/viewtopic.php?p=942809
- https://www.chessprogramming.org/Ethereal
- https://wiki.chessdom.org/Ethereal_questionnaire_20251109

**Failed:**
- komodochess.com live (certificate expired; curl TLS error 35);
- https://talkchess.com/viewtopic.php?p=989569 (login wall);
- TCEC wiki pages Torch, Ethereal, KomodoDragon, Komodo_Dragon, Dragon and
  Stockfish (no such pages);
- CPW Komodo_Dragon (404);
- chessdom by WebFetch (429).

**Web searches**, leading only to pages then opened: Torch 4, Torch v4 CCRL,
Komodo Dragon 3, Dragon by Komodo 2020, Ethereal 14.25.

## Triumviratus, Obsidian, PlentyChess, Coda, Reckless, Gaia, Cinder (family 2)

**Triumviratus:** https://github.com/Tors3/Triumviratus
- README;
- COPYING (via the licence API);
- all releases;
- docs/networks/NETWORKS.md and docs/project/NOVELTIES.md;
- HISTORY.md and CONTRIBUTING.md;
- docs/development/archive/DEVELOPMENT_6.0.md, _7.0.md, _8.0.md and
  EXPERT_BLEND_8.0.md;
- the issues list.

**Coda:** https://github.com/adamtwiss/coda
- README, CLAUDE.md, NOTICES.md;
- docs/license_analysis_2026-07-13.md and
  docs/license_compliance_review_2026-07-11.md;
- releases;
- issues #5, #9, #11, #14, #15, #16, #17.

**Coda's OpenBench:**
- https://ob.atwiss.com/test/4419/
- https://ob.atwiss.com/test/3274/
- https://ob.atwiss.com/test/3007/
- https://ob.atwiss.com/greens/

**Coda's author's other repositories:**
- https://github.com/adamtwiss/incipit (README)
- https://github.com/adamtwiss/gochess (README)

**Gaia:**
- https://github.com/jromang/gaiachess (README, releases)
- https://huggingface.co/jromanghf/gaiachess-networks (README and API)
- the Hugging Face datasets and models API for jromanghf.

**Cinder:** https://github.com/brunocodutra/cinder (README, releases, all
merged PR descriptions, comments on 12 PRs).

**Obsidian:** https://github.com/gab8192/Obsidian (README, releases, commit
titles since 2025-06, licence API).

**PlentyChess:** https://github.com/Yoshie2000/PlentyChess (README, releases,
PRs #458-#501).

**Reckless:** https://github.com/codedeliveryservice/Reckless (README,
releases, 88 merged PR descriptions).

**TalkChess:** p=995255, 995412, 995440, 995651, 986073, 986037, 986051,
983600, 990470.

**Not found:** a claim that CCRL testers are reluctant to test AI-made
engines appeared only in a search snippet; the 8 TalkChess pages opened did
not contain it (UNVERIFIED).

## Berserk, Alexandria, pawnocchio, Integral, Caissa, Viridithas, Stormphrax, Hobbes (family 3)

**pawnocchio:**
- https://github.com/JonathanHallstrom/pawnocchio (README via the API,
  releases, PR conversation text #1-#71)
- https://api.github.com/repos/JonathanHallstrom/pawnocchio/license
- https://github.com/JonathanHallstrom/pawnocchio-nets (README, releases
  list, licence)

**Hobbes:**
- https://github.com/kelseyde/hobbes-chess-engine (README, releases, PR text
  #1-#445, licence API)
- https://github.com/kelseyde/hobbes-chess-engine/blob/main/network_history.txt
  (a prose log)
- https://github.com/kelseyde/hobbes-networks (releases list; no licence
  detected)

**Vine:** https://github.com/vine-chess/vine (README empty; PR titles and
text; GPL-3.0).

**Berserk:** README, https://github.com/jhonnold/berserk/releases, PR text
#561-#611, licence API.

**Alexandria:** README, https://github.com/PGG106/Alexandria/releases
(7.1.0-9.1.0), PR text #627-#640, licence API.

**Integral:**
- README, https://github.com/aronpetko/integral/releases (v6-v8), PR text
  #2-#271
- https://api.github.com/repos/aronpetko/integral/license (**404: no
  licence**)

**Caissa:** README, releases list, licence API.

**Viridithas:** releases list, PR text #463-#481, licence API at master and
at refs v19.0.1 and v20.0.0.

**Stormphrax:** releases list, PR listing, licence API.

**Failed or empty:** the Integral licence endpoint (404); the Vine README
(empty); the pawnocchio-nets and hobbes-networks release bodies (empty).

## Horsie, Lizard, Astra, Raphael, RubiChess, Starzix, Tarnished, Clover, Halogen, Quanticade, Igel (family 4)

**Repository metadata and licences** (GitHub API): liamt19/Horsie,
liamt19/Lizard, h1me01/Astra, h1me01/Sorei, Orbital-Web/Raphael,
Matthies/RubiChess, Matthies/NN, zzzzz151/Starzix, zzzzz151/Starway,
Bobingstern/Tarnished, Bobingstern/tarnished-nets,
lucametehau/CloverEngine, KierenP/Halogen, KierenP/Halogen-Networks,
Quanticade/Quanticade, vshcherbyna/igel.

**READMEs** (API): the 15 engine and tool repositories above (all but
tarnished-nets' data README use).

**Release notes:**
- the engine repositories above;
- https://github.com/liamt19/lizard-nets/releases
- https://github.com/Bobingstern/tarnished-nets/releases
- https://github.com/KierenP/Halogen-Networks/releases (including tags
  4264b7e5, c57e7be4, 637096c1)
- the igel release tag 0.8 asset list.

**PR descriptions:**
- Horsie #1-39, Lizard #1-126, Astra #11-15, Raphael #6-164;
- Starzix #1-203 (titles; bodies of #183, 184, 195, 200);
- Tarnished #1-160, Clover #286-407;
- Halogen #690-912 (bodies of #789, 826, 837, 844, 857, 858, 862, 863, 864,
  870, 878, 885, 887, 890);
- Quanticade, all PRs (bodies of #212, 213, 282, 299, 343, 404);
- igel #292-375 (bodies of #326, 358, 359, 368, 371, 375).

**Prose logs:**
- https://github.com/Orbital-Web/Raphael/blob/main/src/eval/net/history.txt
- https://github.com/Matthies/RubiChess/blob/master/ChangeLog.txt

**Other:**
- https://huggingface.co/datasets/h1me01/astra-selfplay
- CPW: https://chessprogramming.org/Clover,
  https://chessprogramming.org/Halogen, https://chessprogramming.org/Igel,
  https://chessprogramming.org/RubiChess (the last two fetched, not used).
- One web search to find Astra's repository (its result text not used).

**Failed:** CPW 404 for Lizard, Starzix and Quanticade;
`liamt19/horsie-nets` (404).

## PZChessBot, ZigQueen, Devre, JustBot, Minke, Titan, Velvet, Tcheran, Uralochka, Seer, Motor, Renegade (family 5)

**Repository metadata and licence detection** (GitHub API):
kevlu8/PZChessBot, stierms/zigqueen, OmerFarukTutkun/Devre,
HasanFakih21/JustBot, enfmarinho/Minke, jeff-pow/Titan,
mhonert/velvet-chess, tcheran-chess/tcheran, connormcmonigle/seer-nnue,
connormcmonigle/seer-training, martinnovaak/motor, pkrisz99/Renegade,
FreemanZlat/Uralochka3 (an older mirror).

**READMEs and all release notes:** the 12 engine repositories, plus
kevlu8/PZChessBot-Networks.

**Project documents:**
- https://github.com/stierms/zigqueen — docs/NETWORK.md,
  docs/PROVENANCE.md, ORIGINALITY.md
- https://github.com/tcheran-chess/tcheran — NET.md, CHANGELOG.md
- https://github.com/enfmarinho/MinkeNets — history.txt
- the repository-root file listing of martinnovaak/motor (licence check).

**PR descriptions and comments:**
- PZChessBot: #35, 36, 47, 65, 110, 128, 130, 143, 160, 163, 191, 208, 261,
  265, 267, 270, 279, 293, 294, 303, 306, 312, 323, 331, 337, 341, 347,
  352, 357, 358, 364, 369, 370, 371, 373, 376, 377, 378, 383 (and PR lists
  1-3).
- Devre: #21, 23, 24, 41, 44, 45, 49, 51, 52, 53, 54, 55, 63, 64, 68, 69,
  72, 75, 78, 79, 81, 82.
- JustBot: #24, 43, 74, 75, 89, 93, 97, 99, 117, 135, 136, 141, 144, 149,
  151, 152, 160, 163, 165, 168, 170.
- Minke: #10, 31, 102, 136, 148, 154, 158, 160, 163, 164, 177, 188, 190,
  205, 226.
- Titan: #85, 86, 125, 167, 177, 186, 213, 216, 224, 225.
- Seer: #174, 176, 177, 182, 183, 185, 196, 197, 199, 200, 201, 202, 203,
  204, 205, 209, 210, 211.
- Motor: #164, 170, 184, 196, 200, 201, 212-225.

**GitLab API** (freemanzlat/uralochka3): project metadata; README at main,
at tag v.3.41 and at v.3.42; releases v.3.40-v.3.42; the tag list.

**CPW:** https://www.chessprogramming.org/Velvet,
https://www.chessprogramming.org/Seer, https://www.chessprogramming.org/Titan
(a different 1993 engine; not used).

**Failed:**
- CPW 404 for Devre, Minke, Motor, Renegade, Uralochka, Tcheran,
  PZChessBot, JustBot and ZigQueen;
- the enfmarinho/MinkeTrainer README (404);
- the connormcmonigle/seer-training README and contents (404; release
  bodies empty);
- the martinnovaak/forge README (no output);
- the Uralochka README at ref master ("404 Commit Not Found").

**Web searches:** two (a CCRL query, a Motor data query); nothing usable.

## Lc0 and the closed engines (family 6)

**CPW** (CC BY-SA 3.0): Stoofvlees, Ginkgo, Fritz, Revenge, Pedone,
Chess_System_Tal, Rebel, RofChade, Leela_Chess_Zero.

**TCEC wiki** (curl with a browser User-Agent):
- https://wiki.chessdom.org/Stoofvlees_questionnaire_20251109
- https://wiki.chessdom.org/Ginkgo_questionnaire_20251013
- https://wiki.chessdom.org/RofChade_questionnaire_20251112
- https://wiki.chessdom.org/LCZero_questionnaire_20251107
- https://wiki.chessdom.org/LCZero_questionnaire_20261106
- https://wiki.chessdom.org/Engines_by_TCEC_Questionnaire
- https://wiki.chessdom.org/TCEC_Questionnaire
- searches for Stoofvlees, Revenge, rofChade, Ginkgo and "questionnaire".
- **Failed:** /Stoofvlees, /Revenge, /RofChade, /Ginkgo, /Rebel and
  /Chess_System_Tal (no such pages).

**Lc0:**
- https://github.com/LeelaChessZero/lc0/releases/tag/v0.29.0 and the API
  tag date; the raw README (licence section).
- https://lczero.org/blog/ and index pages 2-12.
- Blog posts:
  - 2020/04/wdl-head;
  - 2018/10/understanding-training-against-q-as;
  - 2018/09/tb-rescoring;
  - 2021/04/jumping-on-the-nnue-bandwagon and 2021/04/joking-ftw-seriously;
  - 2021/06/the-importance-of-open-data;
  - 2024/02/transformer-progress;
  - 2023/01/2022-progress;
  - 2022/12/lc0-release-v0.29.0;
  - 2023/07/the-lc0-v0.30.0-wdl-rescale/contempt-implementation.
- lczero.org/dev/wiki/ pages: technical-explanation-of-leela-chess-zero,
  training-runs, training-data-format-versions, best-nets-for-lc0, networks,
  neural-net-training, why-zero, the wiki index; play/networks/bestnets.
- storage.lczero.org/files/training_data/LICENSE.txt

**Papers:**
- arXiv 2605.19091 (Chessformer; abstract and HTML; CC BY 4.0).
- **Failed:** journals.sagepub.com/doi/10.1177/13896911251360654
  (Cloudflare challenge); the api.crossref.org lookup of that DOI (not
  found) and a bibliographic search (no match).
- icga.org/?p=3864 (the WCCC 2023 winner).

**CCRL:** engine_details for Fritz 20 8CPU, Stoofvlees II b5, CSTal 3.00,
Rebel 17.0, rofChade 3.1 8CPU, Revenge 4.0 8CPU, Ginkgo Santiago 1.0 8CPU
and Lc0 0.29.0 w753723.

**Vendor and author sites:**
- en.chessbase.com/post/brand-new-release-fritz-20
- en.chessbase.com/post/review-fritz-20-a-revolutionary-leap-forward-in-chess-software
- revengechess.com (index and getit.html)
- rebel7775.wixsite.com/rebel: home, downloads, guest-engines, about-1,
  about-1-1, kopie-van-rebel-eas-2-0, copy-of-kasparov, blank-1, absurd-1-0
- whittingtonchess.com: home, /chess-system-tal, /engine-analysis/,
  /chessenginesimilarities/ (the "engine forensics" pages)
- api.github.com metadata and releases for ChrisWhittington/ChessSystemTal3
  and ChrisWhittington/Chess-System-Tal-NNUE-2 (release text only)
- rofchade.nl (home blog)
- **Failed:** revengechess.com /get-it and /support (404);
  rebel13.nl/windows/rebel-16.html (HTTP 526).

**TalkChess:**
- p=974682, 974743 and 975362 (Revenge 4.0);
- p=899066 (Revenge 1.0) and p=915276 (Revenge 2.0);
- p=883632 (Pedone 3.0);
- p=925751 (rofChade 3.0) and p=952948 (rofChade 3.1);
- p=938739 (Rebel 16) and p=920074 (four new Rebels);
- p=941432 and 941426 ("Games for Training NNUE?");
- p=954580 (REBEL-Dev);
- p=993164 (Maverick NNUE guest engine);
- p=987998, 978682 and 950084 (page 6 only) (CSTal).
- **Failed:** p=929347 and p=929354 (Revenge 3.0, "topic does not exist");
  p=891014 (Pedone 3.1, information page).

**Web searches** (snippets used only to find pages): Chessformer; the
Stoofvlees ICGA paper (two); Revenge 4.0; Pedone 3.0; Fritz 20; CSTal 2.00;
Rebel 16 data; rofChade 3.1.
