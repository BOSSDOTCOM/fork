# Sources

Part of the rare-ideas survey of 2026-11-15 (README.md). Every source the four groups list, deduplicated and sorted by
project. **Every page was opened on 2026-11-15** by the group(s) named, unless the row says failed or not opened.
Authors and licences are as the pages state them (or as the 2026-11-10 survey recorded them, not re-read). Every
engine source is **REFERENCE ONLY**, used for concepts and the engine's own figures; its code, nets and data are
**OFF-LIMITS**.

**Source kinds.** "PR text" is pull-request titles and descriptions read through the GitHub API
(`api.github.com/repos/<owner>/<repo>/pulls?state=all`, and individual PRs at `https://github.com/<owner>/<repo>/pull/<n>`);
"commit text" is commit messages through the API's commit, `git/commits` or `search/commits` endpoints (messages only,
no file lists or diffs). Fenced blocks were removed by script before reading; groups 1, 2 and 3 kept the OpenBench or
fastchess result lines inside such blocks (README.md, flag 1). No source file, diff, code view or blame was opened by
any group, and nothing was cloned.

## Engines and projects

| Project (author; licence) | Source | What | Group | Opened |
|---|---|---|---|---|
| Alexandria (PGG106; GPL-3.0) | api.github.com/repos/PGG106/Alexandria pulls (570 merged); PRs #456, #543, #569, #574, #581, #596, #609, #640 | PR text | G1 | 2026-11-15 |
| Astra (h1me01) | api.github.com/repos/h1me01/Astra pulls (5), releases (14), README | PR text, release notes | G2 | 2026-11-15 |
| Berserk (jhonnold; GPL-3.0) | api.github.com/repos/jhonnold/berserk pulls (530 merged); PRs #494, #496, #497, #522, #536, #546, #549, #551, #574, #576, #611 | PR text | G1 | 2026-11-15 |
| Bread (Nour Berakdar; GPL-3.0) | https://wiki.chessdom.org/Bread_questionnaire_20260429; GitHub API readme and metadata of Nonlinear2/Bread-Engine | TCEC questionnaire; README (reading stopped at a code listing) | G4 | 2026-11-15 |
| Caissa (Michał Witanowski; MIT) | api.github.com/repos/Witek902/Caissa pulls (4), releases (37), README | PR text, release notes 1.12-1.26, README | G2 | 2026-11-15 |
| Cataphract (masceron; MIT) | CCRL engine page; GitHub API readme and metadata of masceron/Cataphract | README | G4 | 2026-11-15 |
| CatGPT (Nikhil Reddy; PolyForm Noncommercial) | https://wiki.chessdom.org/CatGPT_questionnaire_20260525; GitHub API readme and metadata of butter76/CatGPT | TCEC questionnaire; README | G4 | 2026-11-15 |
| Chess System Tal, Rebel (Chris Whittington, Ed Schröder) | not reopened; the 2026-11-10 survey and the network survey's group-h record | prior records | G4 | (not reopened) |
| Cinder (brunocodutra; GPL-3.0) | api.github.com/repos/brunocodutra/cinder pulls (1,088 merged); commit messages of PRs #1007, #1015, #1067, #1069, #1106, #1112-#1114, #1191; releases | PR and commit text, release notes | G1 | 2026-11-15 |
| Clockwork | https://wiki.chessdom.org/Clockwork_questionnaire_20260617 | TCEC questionnaire ("confidential", no content) | G4 | 2026-11-15 |
| Clover (lucametehau; GPL-3.0) | api.github.com/repos/lucametehau/CloverEngine pulls (386), releases (33), README | PR titles (descriptions mostly empty), release notes | G2 | 2026-11-15 |
| Coda (Adam Twiss; GPL-3.0-or-later) | github.com/adamtwiss/coda PRs #1-#4 and README | PR text, README | G1 | 2026-11-15 |
| DeepFin (jjosh) | https://wiki.chessdom.org/Deepfin_questionnaire_20260618 | TCEC questionnaire | G4 | 2026-11-15 |
| Devre (Ömer Faruk Tutkun; GPL-3.0) | api.github.com/repos/OmerFarukTutkun/Devre pulls (68), releases; README | PR text, release notes | G3 | 2026-11-15 |
| Dragon by Komodo 3.3 (commercial) | https://komodochess.com/dragon-3.3.htm | product page | G1 | **failed** (expired certificate) |
| Dragon by Komodo 3.3 | https://talkchess.com/viewtopic.php?p=953167 | release thread | G1 | **failed** (connection refused) |
| Ethereal (Andrew Grant; code GPL-3.0, nets all rights reserved) | api.github.com/repos/AndyGrant/Ethereal pulls (2 pages), commits (15 pages, 1,440 messages), releases; README | PR and commit text (commits 993abdc, 75bfcfb, 05e1cc4, bdeaaae, 0b605f2, 37ccbfe; #141-#143) | G3 | 2026-11-15 |
| Ethereal | https://wiki.chessdom.org/Ethereal_questionnaire_20251109 | TCEC questionnaire | G3 | 2026-11-15 |
| Fritz 20 (ChessBase; engine by Frank Schneider) | https://en.chessbase.com/post/brand-new-release-fritz-20 | announcement | G3 | 2026-11-15 |
| Gaia (jromang; GPL-3.0-or-later) | https://github.com/jromang/gaiachess/releases | release notes 4.1.2-4.4.3 | G1 | 2026-11-15 |
| Ginkgo Santiago (Frank Schneider) | https://wiki.chessdom.org/Ginkgo_questionnaire_20251013 | TCEC questionnaire | G3 | 2026-11-15 |
| Halogen (Kieren Pearson; GPL-3.0) | api.github.com/repos/KierenP/Halogen pulls (9 pages, 883 PRs), releases; README; api.github.com/repos/KierenP/Halogen-Networks/releases | PR text, release notes, network release notes | G3 | 2026-11-15 |
| Heimdall, Peras, Pseudo, Spaghet BologNNese, Turbulence, Farzin, Equisetum, Prune | CCRL engine pages (Blitz and 40/15); GitHub API metadata of ksw0518/Turbulence_v4, ar-karkon/farzin, justNo4b/Equisetum | ranks, homepages, creation dates | G4 | 2026-11-15 |
| Hobbes (Dan Kelsey; MIT) | api.github.com/repos/kelseyde/hobbes-chess-engine pulls (423), releases (5, including 4.0 of 2026-11-13), README | PR text, release notes | G2 | 2026-11-15 |
| Horsie (liamt19) | api.github.com/repos/liamt19/Horsie pulls (39), releases (2), README | PR text | G2 | 2026-11-15 |
| Icarus (Sp00ph; AGPL-3.0) | GitHub API readme, pulls (closed; bodies of #25, #29, #32, #65, #76, #78) and metadata of Sp00ph/icarus; https://wiki.chessdom.org/Icarus_questionnaire_20260617 ("confidential"); CCRL rating graph | README, PR text | G4 | 2026-11-15 |
| Igel (Volodymyr Shcherbyna; GPL-3.0) | api.github.com/repos/vshcherbyna/igel pulls (4 pages, 332 PRs), releases; README; https://chess.grantnet.us/test/40987/ and /40905/ | PR text, OpenBench pages (no description) | G3 | 2026-11-15 |
| Incipit (Adam Twiss; GPL-3.0) | GitHub API readme, contents (top level and docs/ names only), releases of adamtwiss/incipit; commits 1f209f78, 8806cbcc, eab51452, 98667dc8, a1ef39e1, bef53319, 964a9286, 548f4490, 4b4d3b1e, 93a3eaa7 | README, release notes, commit text | G4 | 2026-11-15 |
| Integral (aronpetko; no licence detected) | api.github.com/repos/aronpetko/integral pulls (252), releases (8), README | PR text | G2 | 2026-11-15 |
| Jackal (snekkers; GPL-3.0) | https://wiki.chessdom.org/Jackal_questionnaire_20260625 | TCEC questionnaire | G4 | 2026-11-15 |
| JustBot (HasanFakih21; AGPL-3.0) | api.github.com/repos/HasanFakih21/JustBot pulls (2 pages, 200 PRs), releases; README; https://ob.justchess.xyz/test/389/, /760/, /86/, /1171/ | PR text, OpenBench pages (branch names only) | G3 | 2026-11-15 |
| Lc0 (the LCZero authors; GPL-3.0; posts by borg, Naphthalin, ghostway and crem) | https://lczero.org/blog/ and /blog/page/2/ to /page/8/; /blog/2023/07/the-lc0-v0.30.0-wdl-rescale/contempt-implementation/; /blog/2024/03/gm-matthew-sadler-on-wdl-contempt/; /play/flags/; /blog/2023/01/2022-progress/; /blog/2022/12/lc0-release-v0.29.0/; /blog/2020/04/wdl-head/; https://wiki.chessdom.org/LCZero_questionnaire_20251107 | blog posts, flags page, TCEC questionnaire | G4 | 2026-11-15 |
| Lizard (liamt19) | api.github.com/repos/liamt19/Lizard pulls (121), releases (16), README | PR text | G2 | 2026-11-15 |
| Minke (enfmarinho; GPL-3.0) | api.github.com/repos/enfmarinho/Minke pulls (3 pages, 236 PRs), releases; README; MinkeNets history.txt (contents API) | PR text; network history (skimmed) | G3 | 2026-11-15 |
| Motor (Martin Novak; no licence seen) | GitHub API martinnovak/motor pulls (closed, pages 1-3); bodies of #114, #145, #146, #177, #178, #181, #182, #194, #200, #214, #217, #223 | PR text | G4 | 2026-11-15 |
| Obsidian (gab8192; GPL-3.0) | github.com/gab8192/Obsidian commits since 2024-10-01 (API, 100 messages) and pull requests | commit and PR text | G1 | 2026-11-15 |
| pawnocchio (Jonathan Hallström; GPL-3.0, nets CC-BY-SA-4.0) | api.github.com/repos/JonathanHallstrom/pawnocchio pulls (55 merged); PRs #19, #31, #52, #59, #61, #65, #68, #69 | PR text | G1 | 2026-11-15 |
| PlentyChess (Yoshie2000; GPL-3.0) | api.github.com/repos/Yoshie2000/PlentyChess pulls (474 merged); PRs #216, #227, #273, #281, #283, #285, #332, #337, #338, #395, #399, #410, #422, #460, #496, #500 | PR text | G1 | 2026-11-15 |
| Potential (Eren Araz; GPL-3.0) | GitHub API readme and pulls (closed, pages 1-8) of ProgramciDusunur/Potential; bodies of #323, #387, #427, #436, #456, #505, #537, #545, #557, #559, #568, #608; https://wiki.chessdom.org/Potential_questionnaire_20260617 | README, PR text, TCEC questionnaire | G4 | 2026-11-15 |
| Prune (Thomas Girolami, Joachim Bienvenue; MIT) | https://wiki.chessdom.org/Prune_questionnaire_20260618; GitHub API readme of tgirolami09/Prune | TCEC questionnaire, README | G4 | 2026-11-15 |
| PZChessBot (kevlu8 and co-author; AGPL-3.0) | api.github.com/repos/kevlu8/PZChessBot pulls (4 pages, 375 PRs), releases; README; https://sscg13.pythonanywhere.com/test/1062/ | PR text, OpenBench page (branch name "qs-pre-ext") | G3 | 2026-11-15 |
| Quanticade Cronus (Haxk20; GPL-3.0) | api.github.com/repos/Quanticade/Quanticade pulls (5 pages, 435 PRs), releases; README | PR text (mostly titles) | G3 | 2026-11-15 |
| Raphael (Orbital-Web; AGPL-3.0) | api.github.com/repos/Orbital-Web/Raphael pulls (156), releases (24), README | PR text | G2 | 2026-11-15 |
| Reckless (codedeliveryservice; AGPL-3.0 from 0.9.0) | api.github.com/repos/codedeliveryservice/Reckless pulls (1,039 merged); PRs #244, #298, #393, #563, #565, #644, #645, #649, #667, #676, #699, #706, #711, #716, #720, #729, #737, #740, #772, #780, #827, #844, #847, #851, #853, #878, #926, #934, #939, #958, #964, #1022, #1025, #1032, #1038, #1044, #1055, #1087, #1107, #1108, #1124, #1126, #1127, #1130 | PR text | G1 | 2026-11-15 |
| Renegade (Krisztián Peőcz, pkrisz99; MIT) | GitHub API pkrisz99/Renegade pulls (closed, pages 1-8); bodies of #30, #61, #66, #71, #73, #74, #88, #103, #105, #106, #107, #129; https://wiki.chessdom.org/Renegade_questionnaire_20251015 | PR text, TCEC questionnaire | G4 | 2026-11-15 |
| Revenge (Fabio Gobbato; free, closed) | https://revengechess.com/; https://www.chessprogramming.org/Revenge | home page, CPW | G3 | 2026-11-15 |
| rofChade (Ronald Friederich) | http://rofchade.nl/; https://wiki.chessdom.org/RofChade_questionnaire_20251112 | home page, TCEC questionnaire | G4 | 2026-11-15 |
| RubiChess (Matthies; GPL-3.0) | api.github.com/repos/Matthies/RubiChess pulls (452), releases (36), README | PR text | G2 | 2026-11-15 |
| Seer (Connor McMonigle; GPL-3.0) | GitHub API connormcmonigle/seer-nnue pulls (closed, pages 1-3, titles); bodies and squash messages of #7, #12, #32, #55, #75, #99, #101, #104, #109, #111, #136, #158, #159, #160, #180, #181, #183, #185, #197, #200, #204, #205; commit search "history extension"; releases; https://raw.githubusercontent.com/connormcmonigle/seer-nnue/HEAD/README.md; https://chess.grantnet.us/test/34932/; https://wiki.chessdom.org/Seer_questionnaire_20251030 | PR and commit text, README, OpenBench page, TCEC questionnaire | G4 | 2026-11-15 |
| Soul (Aethdv; AGPL-3.0) | https://wiki.chessdom.org/Soul_questionnaire_20260620 | TCEC questionnaire | G4 | 2026-11-15 |
| SSSimpler (Kirill Timofeev; GPL-3.0) | https://wiki.chessdom.org/SSSimpler_questionnaire_20260617; GitHub API readme, pulls, releases and commit search ("output", "bucket", "king") of Kirill020708/SSSimpler | TCEC questionnaire, README, commit text | G4 | 2026-11-15 |
| Starzix (zzzzz151; WTFPL) | api.github.com/repos/zzzzz151/Starzix pulls (195), releases (7), README | PR titles (descriptions empty), release notes | G2 | 2026-11-15 |
| Stockfish (the Stockfish developers; GPL-3.0, nets CC0) | github.com/official-stockfish/Stockfish commits since 2025-01-01 (API, 897 messages); commits 39c077f1, 8ecfc3c8, 61c68717, 8b6d8def, 645b636d, e7ab6d44, 319d61ef, 75f07da9, 4f4f78f8, 5f7348f0, 93ed4b53, 0f602f90, 7988de4a, 2e2d2778, f590767b, 57f0fe08, c475024b, 447f66ac, ced9f698, 7b370328, 1cebdafc, d7c04a94, 16cd38db, a47a1c18, ff3a6c50, 218c74ec (`https://github.com/official-stockfish/Stockfish/commit/<sha>`) | commit text with fishtest results | G1 | 2026-11-15 |
| Stockfish | https://github.com/official-stockfish/Stockfish/issues/6742 and its comments | issue thread (TCEC elementary-mate failure) | G1 | 2026-11-15 |
| Stoofvlees II (Gian-Carlo Pascutto; proprietary) | https://wiki.chessdom.org/Stoofvlees_questionnaire_20251109; the ICGA Journal article named there | TCEC questionnaire; the article **not opened** (paywalled; an abstract page carries a notice against AI use) | G4 | 2026-11-15 |
| Stormphrax (Ciekce) | api.github.com/repos/Ciekce/Stormphrax pulls (341), releases (9), README | PR text | G2 | 2026-11-15 |
| Tarnished (Bobingstern; GPL-3.0) | api.github.com/repos/Bobingstern/Tarnished pulls (155), releases (13), README | PR text, README | G2 | 2026-11-15 |
| Tcheran (jgilchrist; AGPL-3.0) | api.github.com/repos/tcheran-chess/tcheran pulls (1), commits (16 pages, 1,597 messages), releases; CHANGELOG.md, NET.md, README.md (contents API, raw) | commit text, changelog, network history | G3 | 2026-11-15 |
| Titan (jeff-pow; GPL-3.0) | api.github.com/repos/jeff-pow/Titan pulls (3 pages, 225 PRs), releases; README | PR text | G3 | 2026-11-15 |
| Torch (Andrew Grant; private) | https://talkchess.com/viewtopic.php?p=965599 | TalkChess post (2024-06-18) | G1 | 2026-11-15 |
| Torch | https://www.chess.com/news/view/torch-chess-engine | listed in search results | G1 | **not opened** |
| Triumviratus (Tors3; GPL-3.0 with a section 7(b) term) | https://github.com/Tors3/Triumviratus/blob/master/docs/project/NOVELTIES.md (rev. 2026-11-07); https://github.com/Tors3/Triumviratus/blob/master/docs/development/archive/DEVELOPMENT_8.0.md (sections 38, 41, appendix); pull requests (API; one merged, nothing relevant) | project prose documents | G1 | 2026-11-15 |
| Uralochka (Ivan Maklyakov; GPL-3.0) | https://gitlab.com/api/v4/projects/freemanzlat%2Furalochka3/releases; https://wiki.chessdom.org/Uralochka_questionnaire_20251107 | release notes, TCEC questionnaire (a code illustration in it skipped) | G4 | 2026-11-15 |
| Velvet (Martin Honert; GPL-3.0) | api.github.com/repos/mhonert/velvet-chess pulls (3), commits (7 pages, 601 messages), releases; README | commit text, release notes 5.2.0-8.1.0 | G3 | 2026-11-15 |
| Viridithas (cosmobobak; MIT to 20.0.0, AGPL-3.0 after) | api.github.com/repos/cosmobobak/viridithas pulls (451), releases (33), README; https://raw.githubusercontent.com/cosmobobak/viridithas/master/notes/IDEAS.txt; .../notes/networkhistory.txt (keyword search only) | PR text, release notes, prose notes | G2 | 2026-11-15 |
| ZigQueen (Matthias Stier; GPL-3.0-or-later; AI-assisted) | api.github.com/repos/stierms/zigqueen pulls (0), commits (52 messages), releases (11); README.md, ORIGINALITY.md, docs/NETWORK.md, PROVENANCE.md (skimmed), STRENGTH.md, TUNING.md, QUALITY_GATES.md, PERFORMANCE_PRINCIPLES.md, release notes 6.0.0-6.5.0, RELEASE_VALIDATION_6.4.0 | commit text, prose documents (some fetched, not used) | G3 | 2026-11-15 |

## Lists, wikis and other pages

| Source | What | Group | Opened |
|---|---|---|---|
| https://computerchess.org.uk/ccrl/404/ and its engine pages (Incipit 0.6.0, Icarus 1.0, Heimdall 1.5.0, Cataphract 1.5.1, Prune 4.0.1, Turbulence 0.0.8, Farzin 0.5.2, Equisetum 1.0) | CCRL Blitz list ("computed on November 14, 2026", 2,190,694 games) | G4 | 2026-11-15 |
| https://computerchess.org.uk/ccrl/4040/ and engine pages (Peras 3.6.0, Pseudo 1.1, Spaghet BologNNese 1.0, SSSimpler 2.0.0, Icarus 1.1.1) | CCRL 40/15 list (computed November 13, 2026) | G4 | 2026-11-15 |
| https://computerchess.org.uk/ccrl/404/rating-history-by-day-graphs/ (Icarus 1.0, Cataphract 1.5.1); /ccrl/404/history.html | rating graphs, history index | G4 | 2026-11-15 |
| https://wiki.chessdom.org/TCEC_Swiss_10, TCEC_Swiss_9, TCEC_Swiss_8, TCEC_Leagues_Season_30_Engines, Main_Page, Engines_by_TCEC_Questionnaire, TCEC_Swiss_11 (empty) | TCEC wiki (CC BY-SA 3.0) | G4 | 2026-11-15 |
| https://www.chessprogramming.org/Ginkgo, /Revenge, /Fritz, /Velvet, /Halogen, /Igel, /Ethereal (Igel, Halogen and Velvet re-fetched later the same day) | Chess Programming Wiki (CC BY-SA 3.0) | G3 | 2026-11-15 |
| https://www.chessprogramming.org/Minke, /JustBot | CPW | G3 | **failed** (404) |
| https://www.chessprogramming.org/Titan | CPW (a different 1990s engine of that name) | G3 | 2026-11-15 (not used) |
| https://talkchess.com/viewtopic.php?p=989164 and https://talkchess.com/viewtopic.php?t=85845&start=0 to 210 (22 pages) | TalkChess "New engine releases & news H1 2026" | G4 | 2026-11-15 |
| https://www.chess.com/computer-chess-championship | CCC page | G4 | **failed** (JavaScript application, no data) |
| GitHub repository searches (5 queries for AI-assisted chess engines); NoaChess, seajay-chess, zchezz and an agent-written engine on TalkChess surfaced | search results | G4 | 2026-11-15 |

## Searches (result lists only; every fact used came from a page above)

| Query | Group | Note |
|---|---|---|
| Torch v4 technique; Dragon 3.3 notes | G1 | leads only |
| "factorized LMR" | G2 | no prose found; result pages not opened: en.wikipedia.org/wiki/Late_move_reductions, chessprogramming.org/Late_Move_Reductions, talkchess.com viewtopic p=732918 and p=561353, mediocrechess.sourceforge.net/guides/lmr.html |
| CCC 2026 newcomers (2 queries); TalkChess "New engine releases & news H2 2026"; the Stoofvlees ICGA article title | G4 | CCC participants UNVERIFIED; the article not found |

## Failed or empty fetches

- komodochess.com Dragon 3.3 page (expired certificate) and the TalkChess Dragon 3.3 thread (connection refused) (G1).
- `api.github.com/repos/cosmobobak/viridithas/contents/docs`: 404, no such folder (G2).
- CPW Minke and JustBot pages: 404 (G3).
- chess.com CCC page: a JavaScript application with no data (G4).
- Clockwork and Icarus TCEC questionnaires: "confidential", no content (G4).
- Empty PR descriptions: most of Clover's, Starzix's and Astra's; Viridithas #248, #337, #373, #378, #391; Integral
  #174; RubiChess #461, #517, #533 (G2). ZigQueen has no PRs (G3).
- The OpenBench pages opened gave no descriptions (G3, G4). OpenBench, furybench, viri.dev and other test servers
  were otherwise not opened; figures come from result summaries pasted into PR descriptions or release notes (G2).
- Commit messages not fetched for Halogen, Quanticade, Igel, PZChessBot, Devre, JustBot, Minke and Titan; their PR
  text was used instead (G3).
- The full text of the Stoofvlees ICGA article: not opened (paywall; an abstract page with a notice against AI use).

## Fork's own documents read (read-only, origin/phase-4)

docs/research/engine-survey-2026-11/ (README, comparison, engines, ranking, sources); network-survey-2026-11/
(README, matrix, shortlist, records group-b, group-d, group-g, group-h); phase4-think-tank/ (phase-b-specialists,
phase-c-synthesis); novel-ideas-2026-11-11.md; vision-ideas-2026-11-14.md and vision-step0-2026-11-14.md; docs/ideas.md;
docs/DESIGN.md; docs/nets.md; docs/history/phase-4/sprt-log.md; and, to set Fork's status, Fork's own
src/search/searcher.hpp, searcher.cpp, trans_table.hpp, move_selector.hpp and src/datagen/self_play.cpp. The
synthesis also read the KB entry docs/kb/lazy-smp.md on branch kb.
