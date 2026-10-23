# Competition knowledge base: TCEC, CCC, rating lists, opponents

Checked 2026-10-23. Every fact below comes from a page opened on that date
(see `docs/kb/_sources-competition.md`). Anything not confirmed on an opened
page is marked **UNVERIFIED** with the reason. Text is summarized, not quoted.

Tags: **USE** (Fork may use it directly), **REFERENCE ONLY** (read for facts or
ideas, never copy code, nets or data), **OFF-LIMITS** (Fork must not use it in
any form: code, nets, data, binaries inside Fork).

---

## 0. Findings that change Fork's plan (read first)

1. **AI-coded engines cannot enter the TCEC Leagues in Season 30.** The TCEC
   Tournament Director's statement of 31 Aug 2026 says that in S30 AI engines
   enter only through the Swiss (via the Category 3+4 playoff, one Swiss spot),
   are not eligible for the regular Leagues however they score, and get a
   separate "extra gauntlet" instead. The Swiss 10 page defines Category 4 as
   engines with major help from AI, and requires their code to be open source
   and publicly viewable (e.g. GitHub) at submission and during participation,
   with TCEC admins allowed to build the binary from that repository. The
   questionnaire (v2.4) asks whether the engine contains AI-generated code,
   which parts, when, and with which tools. Fork is being written by an AI
   coding agent, so it will almost certainly be Category 4. Consequences:
   - Fork needs a public repository before it applies.
   - In S30 the ceiling is the Swiss plus the AI gauntlet, not the Leagues.
     TCEC says it will revisit this ("separate and/or joint competitions");
     S31 rules are not yet published (**UNVERIFIED** for S31).
   - Hiding AI involvement is not an option: the Potential case (Swiss 10) shows
     TCEC penalizes architecture misdeclaration found after the fact.
   - **The TCEC Swiss is therefore Fork's primary target event; the Leagues
     are secondary** (closed to AI engines in S30, maybe open later). See
     "TCEC Swiss (primary target)" below.
   Source: chessdom.com statement (31 Aug 2026); wiki TCEC_Swiss_10; wiki
   TCEC_Questionnaire.
2. **Engines get 7-man Syzygy.** Live game headers on 2026-10-23 show
   `SyzygyPath=/home/syzygy7`, and the hardware page says 3-7 man Syzygy is on
   NVMe for all divisions. Fork must probe 7-man tables (Fathom handles 7-man)
   and should `madvise(MADV_RANDOM)` the mapped files, which TCEC asks of
   7-man users.
3. **Threads 512, Hash 262144 MB (256 GiB)** in the live Swiss 10 game. Fork's
   TT, thread pool and NUMA handling must scale to that. Hash initialisation
   must be multithreaded, or TCEC caps hash at 32 or 64 GiB.
4. **The brief's adjudication values do not match the current written rules.**
   Brief: draw from move 35 at ±0.08 for 10 plies, win at ±10.00 for 10 plies,
   6-piece TB. Current TCEC rules (Leagues, Swiss and the all-events Rules
   page): the only eval-based draw rule is: 6 or fewer pieces (kings counted,
   pawns not), eval of the move into the position within [-0.25, +0.25],
   8 consecutive plies, no minimum move number; counter is reset by an eval
   outside the band or a missing eval, or a promotion producing a 7th piece;
   captures and pawn moves do not reset it. No eval-based win adjudication
   appears in the written rules (wins: mate, illegal move, resignation). The
   ±10 win and ±0.15/35-move draw values only apply after a server outage.
   Re-verified 2026-10-23 (see §2 "Adjudication re-verification"): there is
   no tablebase adjudication either (removed from the Leagues rules between
   Oct 2024 and May 2025), and the ±10.00 win rule was indeed dropped in
   Season 20 (confirmed on the S19 and S20 rule pages). Historical note: S20
   used move 35, ±0.15, 10 plies, no win rule, 6-man TB auto-adjudication.
   The brief's ±0.08 draw band and ±10.00 win rule match the S17 rules page
   (2020), i.e. the brief describes rules that are six-plus years old.
5. **Time controls are 30'+3" (EL, L2, L1, Swiss, Cup), 60'+6" (Premier),
   120'+12" (Superfinal)**, not the S20 values.
6. **Pondering is off**, books are removed or disabled, and engines found
   using hidden books are disqualified.

---

## TCEC Swiss (primary target)

Checked 2026-10-23. Status: verified unless marked. Tag: REFERENCE ONLY
(facts). Machine-readable copy: `config/tcec.json` → `swiss`.

**Why primary.** In S30 an AI-coded engine (Category 4) can only play the
Swiss, reached through the Category 3+4 playoff, and is barred from the
Leagues whatever it scores (TD statement, chessdom.com, 31 Aug 2026). The
Leagues (EL → L2 → L1 → Premier → Superfinal) are therefore Fork's
**secondary** target: relevant only if TCEC opens them to AI engines in a
later season (the statement mentions future "separate and/or joint
competitions"; S31 rules not published: **UNVERIFIED**).

### Route in for Fork (S30 scheme)

1. Apply by email with the questionnaire before the Swiss deadline (Swiss 10:
   1 Jul 2026, 12:00 UTC). Organisers invite; nothing on the pages says
   what minimum strength gets an invitation (**UNVERIFIED**).
2. TCEC sorts applicants into categories and announces them; authors have
   24 h to appeal to the TD, whose decision is final. An engine may not
   change architecture during the season into a higher-numbered category.
3. Categories for Swiss 10 (wiki TCEC_Swiss_10, edited 22 Oct 2026):
   - Cat 0: placed automatically (engines holding a Leagues place and not
     relegated from the lowest league, at the organisers' discretion); 32.
   - Cat 1: newer/additional engines; 1 DRR playoff at 30'+3" for 10 Swiss
     spots. The Potential decision describes this as the lighter group for
     HCE engines.
   - Cat 2: 2 DRR playoff at 30'+3" for 5 spots.
   - Cat 3: joint **Cat 3+4 playoff, 12 DRR at 30'+3", for 1 Swiss spot**.
   - Cat 4 (major help from AI): gets **one** place in that Cat 3+4 playoff;
     code must be public open source at submission and throughout, and
     TCEC admins must be allowed to build the binary from the repository.
     How several Cat 4 engines would contest that single place is not
     stated (**UNVERIFIED**).
   - Cat 5: cannot be featured.
   Playoff qualification is decided on points only; ties for a qualifying
   place go to extra game pairs (two engines) or extra DRRs (three or more).
4. S30 precedent: the Cat 3+4 playoff had 3 engines (Cinder, Serendipity,
   CatGPT as the only Cat 4 engine), 72 games, 9-12 Sep 2026. Final: Cinder
   31.5/48 (qualified), CatGPT 27/48, Serendipity 13.5/48 (TCEC archive
   crosstable JSON). So the Cat 4 entrant has to beat the Cat 3 engines over
   24 games each; Cinder is a top-10 CCRL engine (§4), so the bar is high.
5. AI engines get a separate "extra gauntlet" instead of the Leagues; its
   format is not published on any page opened (**UNVERIFIED**).

### Swiss format (Swiss 10, S30)

| Item | Value | Source | Status |
|---|---|---|---|
| Field | 48 engines | Swiss 10 page; crosstable.json | verified |
| Rounds | 13 double rounds (26 games per engine). The generic Swiss rules page says 11 (edited from 12 on 21 Nov 2025); the event page and the 624-game schedule.json (13 × 24 pairs × 2) agree on 13 | Swiss 10 page; schedule.json; TCEC_Swiss_rules | verified (13 for Swiss 10) |
| Game pairs | yes: each pairing plays twice, same opening, colours reversed, back to back | Swiss rules 2.b; schedule.json (every completed pair has colours swapped; opening labels match except where the post-book line was named differently) | verified |
| Pairing system | TCEC Swiss Tournament System: deterministic, Monrad-like. Engines are ranked by score, then seed. The top unpaired engine is matched with the highest-ranked engine it has not yet met, provided colour balance holds and a full pairing of the rest stays possible (checked with a Blossom matching); if no full pairing exists, the oldest round is dropped from the "already met" history | wiki TCEC_Swiss_Tournament_System (edited 15 Jun 2023) | verified |
| Colours | double rounds: the first engine of a pair (higher in the pairing order) has Black in game 1, White in game 2; every engine's colour count is level after each round | Tournament System page | verified |
| Seeding | group seeding by strength into an even number of groups (Swiss 10: 10 groups A-J); seeds A1, B1, …, J1, A2, …; round 1 pairs A1-B1, C1-D1, …; previous Swiss winner is A1 | Swiss rules 1.c-d, 2.a; Swiss 10 page | verified |
| Rating input | only through seeding: organisers order engines by last Leagues standings and/or Elo after testing (Swiss 10 combined the list with TCEC's Elo; the page links a seeding script and an Elo snapshot in a tcecgames fork). After round 1 pairings use score and seed only | Swiss 10 page; Tournament System page | verified |
| Byes | only with an odd field: one per round, scored as a win | Tournament System page | verified |
| Openings | a random book exit for each pairing, from a book made by the TCEC book team (Swiss 10 book by Bastiaan, kbg519v1a) | Swiss rules 2.c, 4; Swiss 10 page | verified |
| Time control | 30'+3"; a time loss is a loss and is not replayed | Swiss rules 5; live.json `TimeControl 1800+3` | verified |
| Time margin | Swiss 10 page notes "a one second margin" in the actual event next to a time-loss report; what it applies to is not explained | Swiss 10 page | **UNVERIFIED** meaning |
| Tiebreaks | winner, promotions and anything that affects later events: points only, then extra game pairs (2 tied) or extra DRRs (3+ tied). Other places: Sonneborn-Berger, then r-mobility, then most wins, then direct encounter, else shared. (TD amendment of 22 Dec 2025 added "the winner" to the points-only rule) | Swiss rules 3; revision diff 7923→8076 | verified |
| Hardware / settings | same servers as all S30 events (§2). Live Swiss 10 game: `Threads=512`, `Hash=262144`, `SyzygyPath=/home/syzygy7`; other options default unless the author asks (Reckless: `MoveOverhead=1000`) | live.json; Further information page | verified |
| Draw rule / adjudication | identical to the Leagues text: see §2 "Adjudication re-verification" | Swiss rules 6-7 | verified |
| Crashes, updates | crash = loss; testing for all invited engines before the event; no updates or fixes once it starts | Swiss rules 7-8 | verified |
| Promotion out of Swiss 10 | top 32 → Cup 17. The 17 engines without a Leagues place compete for 7 Entrance League places (top 5 direct, next 10 play a tiebreak match for 2, bottom 2 out). Category 4 engines cannot take League places in S30 | Swiss 10 page; TD statement | verified |

Observed in Swiss 10 games so far (schedule.json, 2026-10-23, 425 games
finished): no win adjudication occurs; all 212 decisive games are recorded as
mates, 129 of them with 6 or fewer men left (so no tablebase adjudication
either). 169 draws came from the TCEC draw rule, the earliest after 28 moves.
Bug list on the Swiss 10 page shows typical failure modes in testing: time
losses fixed by raising MoveOverhead, crashes, an under-promotion blunder.

**What this means for Fork:** with game pairs and a random biased exit,
every pairing is a mini-match on one opening; losing both sides of a book
exit is the costly case. Only score and seed drive pairings, so a strong
early score quickly brings top opponents. Fork must survive 26 games at
30'+3" on 512 threads with no crash or time loss and no chance to patch.
Points in the Swiss decide nothing for a Cat 4 engine beyond the event
itself in S30.

---

## 1. TCEC: which season is current

- tcec-chess.com/tournament.json on 2026-10-23: `season30`, division `sw`.
- tcec-chess.com/live.json: Event "TCEC Season 30 - Swiss 10", round 9.41,
  TimeControl 1800+3.
- TCEC wiki Main Page: Season 30 current event is Swiss 10. Still to come in
  S30: Cup 17, Leagues Season 30 (EL, L2, L1, Premier, Superfinal), FRD 6.
  Completed in S30: 4kVII, HCE Competition 1. Season 31 is listed as
  upcoming (4kVIII, HCE 2, Swiss 11, Cup 18, Leagues S31, FRD 7).
- S29 is the last completed Leagues season. S29 Superfinal (28 Mar-15 Apr
  2026, 100 games): Stockfish dev-20260318 beat Reckless 0.10.0-dev-b5462f11
  59-41 (+41 =36 -23 from Stockfish's side). Sources: TCEC archive JSON
  `TCEC_Season_29_-_Superfinal_Crosstable.cjson` and `_Schedule.sjson`;
  chessdom.com report of 21 Apr 2026. Verified 2026-10-23.

Status: verified 2026-10-23. Tag: REFERENCE ONLY (facts).

### Season structure (S30)

Order of events in a season (wiki Main Page and Rules): 4k, HCE Competition,
Swiss, Cup, Leagues (EL, L2, L1, Premier Division, Superfinal), FRD.

| Event | Entrants | Format | TC | Book |
|---|---|---|---|---|
| Swiss 10 (current) | 48 | 13 double rounds (Swiss 10 page); generic Swiss rules page says 11 | 30'+3" | random exit per game |
| Cup | 32 | knockout; game pairs R32 2, R16 3, QF 4, SF 6, bronze 8, final 12 | 30'+3" | six books, rising bias |
| Entrance League | 16 | 1x DRR; top 4 up, bottom 6 out | 30'+3" | medium bias |
| League 2 | 12 | 2x DRR; top 4 up, bottom 4 down | 30'+3" | medium bias |
| League 1 | 12 | 2x DRR; top 2 up, bottom 4 down | 30'+3" | high bias |
| Premier Division | 8 | 4x DRR; top 2 to SuFi, bottom 2 down | 60'+6" | high bias |
| Superfinal | 2 | 100 games (50 DRR), all played | 120'+12" | very high bias, sequential |
| FRD | varies | FRC leagues then DFRC | 30'+3" | 1-move FRC exits / DFRC start positions |
| HCE Competition | invited HCE engines | 1 RR | 30'+3" | earlier exits |
| 4k | 6 | 4x DRR + minifinal | 30'+3" | provided |

Leagues eligibility: rating 3000+ on TCEC's BayesElo list; all engines are
invited; questionnaire required. Superfinal tie: 24 games at 120'+12", then
game pairs. Source: wiki TCEC_Leagues_Season_Rules (last edited
21 Jul 2025), wiki Rules, wiki TCEC_Swiss_rules (22 Dec 2025), wiki
TCEC_Swiss_10 (22 Oct 2026). Verified 2026-10-23.

Note: the Leagues rules page carries no season number. It is the rules page
linked from the current wiki and the S29 Leagues page; I treat it as current
for S30. Leagues S30 page itself does not exist yet: **S30-specific Leagues
changes UNVERIFIED**.

### Swiss 10 engine categories (S30)

The Swiss 10 page sorts entrants into categories (definitions are partly
inferred; the page has no formal definitions):

- Cat 0: placed automatically (32 engines: Stockfish, Reckless, LCZero,
  PlentyChess, Torch, Integral, Obsidian, Berserk, Ceres, Pawnocchio, Halogen,
  KomodoDragon, RubiChess, Viridithas, Caissa, Stormphrax, Clover, Ethereal,
  Quanticade, Ginkgo, Tarnished, Uralochka, rofChade, Seer, Stoofvlees, Horsie,
  Velvet, Heimdall, Renegade, Igel, Winter, c4ke).
- Cat 1: 1 DRR playoff for 10 spots (14 engines; the page implies this is the
  lighter HCE path).
- Cat 2: 2 DRR playoff for 5 spots (11 engines).
- Cat 3: 12 DRR playoff with Cat 4 for 1 spot (Cinder, Serendipity).
- Cat 4: AI-assisted engines (CatGPT); must be public open source buildable by
  TCEC admins.
- Cat 5: cannot be featured by TCEC; none listed.
- An engine may not change architecture mid-season into a higher-numbered
  category. Authors have 24 h to appeal categorisation.

Earlier seasons used different meanings: Swiss 7 labelled categories by
"own data" (Cat 2) versus "leela data" (Cat 3), with Cat 4 for "no
questionnaire or failed originality test". The originality test itself is not
described anywhere I opened (**UNVERIFIED**). Tag: REFERENCE ONLY.

---

## 2. TCEC: technical conditions

### Hardware (wiki TCEC_Season_Further_information, edited 24 Feb 2026; "S28 onward")

- CPU server: 2x AMD EPYC 9754 (256 cores / 512 threads), 768 GiB DDR5.
- GPU server: 2x AMD EPYC 9175F (32 cores / 64 threads), 8x RTX 5090
  (32 GiB each), 768 GiB DDR5.
- Storage on both: 1 TiB NVMe system, 14 TiB NVMe for Syzygy 3-7 (WDL+DTZ
  layout as stated), 14 TiB HDD for 7-man DTZ.
- From S30, an engine may use both the CPU and the GPU machine during its own
  turn.
- Verified 2026-10-23. Why it matters: Fork's search must scale to 512
  threads on two sockets (NUMA). Tag: REFERENCE ONLY.

### Engine settings

| Item | Value | Source | Status |
|---|---|---|---|
| Threads | up to 512 per engine; live game uses `Threads=512` | Further info page; live.json | verified |
| Hash | up to 256 GiB if init is multithreaded, else 32 or 64 GiB cap; live game uses `Hash=262144` | Further info; live.json | verified |
| Total engine RAM | 320 GiB cap (excluding OS-cached TB files) | Further info | verified |
| Large pages | enabled automatically | Further info | verified |
| Pondering | off (one machine) | Further info | verified |
| Tablebases | 7-man Syzygy (plus 6-man Scorpio bitbases) for all divisions; `SyzygyPath=/home/syzygy7` | Further info; live.json | verified |
| Opening books | engine books removed/disabled; hidden book use = disqualification | Further info | verified |
| Other UCI options | left at default unless the author asks (e.g. Reckless runs with `MoveOverhead=1000`) | Further info; live.json | verified |
| Protocol | UCI or XBoard | Further info | verified |
| Contempt | default unless author asks | Further info | verified |

### Builds and submission

- 64-bit preferred; builds for AVX-512 / AVX2 / SSE4.2 preferred; authors may
  supply an `update.sh` that clones and compiles; keep debug info in the
  optimised binary (recommended). Source: Further info page. Verified.
- OS: TCEC runs Linux (the FRD rules require engines that play DFRC natively
  under Linux; the 4k rules list x86-64 glibc). A general "Linux binary
  required" rule for the Leagues is not stated on an opened page:
  **UNVERIFIED** as a formal rule, but plan for Linux x86-64.
- Category 4 (AI-assisted) engines: public source, TCEC builds the binary
  from the repository. Verified (Swiss 10 page).
- Application: email a fully completed TCEC Questionnaire (v2.4, edited
  9 Nov 2025). Mandatory since S29. Answers are published unless the author
  opts out. Questions cover: name and repo, main author, chat handles, credit
  name, AI-generated code (which parts, when, which tools), licenses, NN
  training code and its authors, training data origin and permission, other
  engines' code used, compliance with the TCEC NNUE Guideline and why,
  what makes the engine unique, approximate Elo, publication consent.
  Authors must keep the questionnaire current and notify TCEC of
  architecture changes (Potential decision, Swiss 10).
- Updates: submission deadline is the last game of the current event unless
  set otherwise; no updates during an event; testing slots before EL and
  between L1 and Premier. Engines that crash more than once may only fix the
  crash. Crashes count as losses; time losses stand.
- How a brand-new engine first gets invited (e.g. a minimum CCRL rating):
  not stated beyond "invited by organizers" and the 3000+ Leagues bar:
  **UNVERIFIED**.

### Openings and pairing

- Every opening is played twice in consecutive games with colours reversed
  (Openings FAQ, edited 5 Feb 2022; Swiss rules page). Verified.
- Bias rises with level (medium EL/L2, high L1/Premier, very high SuFi).
  Swiss: random exit per game. Book makers are the TCEC book team. The
  bookmaker table on the Openings FAQ is from 2022 and lists old league
  names, so current book lengths/exit counts are **UNVERIFIED**.
- In the Superfinal the Premier winner takes Black first in each pair; in the
  Cup the lower seed has White first.

### Adjudication re-verification (2026-10-23)

Re-checked against the current rule pages: wiki TCEC_Swiss_rules (edited
22 Dec 2025), TCEC_Leagues_Season_Rules (edited 21 Jul 2025) and the
all-events Rules page (edited 8 Jul 2026); plus the history pages
TCEC_Season_17/18/19/20_Rules and the revision history of the Leagues rules
page. Results:

- **Draw rule** (Swiss, Cup, Leagues, HCE and FRD sections, identical text):
  unchanged from what is recorded below (≤6 pieces counting kings but not
  pawns, eval of the move into the position within ±0.25, 8 consecutive
  plies, resets on an out-of-band or missing eval or a promotion that makes
  a 7th piece, no reset on captures or pawn moves, no minimum move). The 4k
  event has no TCEC draw rule at all.
- **Win adjudication during play: none.** Wins come only from mate, the
  opponent's illegal move, the opponent's resignation or (stated in the 4k
  and Swiss sections) loss on time. Removed from `config/tcec.json`.
- **Season 20 claim confirmed.** The S17, S18 and S19 rule pages all contain
  a win rule (both engines at ±10.00 or beyond for 10 plies, active from
  move 1). The S20 rule page (last edited 18 Jan 2021) says outright that the
  win rule of former seasons is dropped from that season onward. No later
  rule page brings it back. S20 ran Dec 2020-Feb 2021 (chessdom's table of
  Superfinals).
- **Tablebase adjudication: none now.** The S20 page and Leagues rules up to
  revision 6018 (13 Oct 2024) had cutechess adjudicate positions with 6
  pieces via Syzygy; revision 6876 (4 May 2025) deleted that, along with a
  clause adjudicating outage positions with 7 men by EGTB. By date this
  falls after the S27 Superfinal (ended Jan 2025) and before S28 (Jun 2025),
  so probably from S28 on; the season number is not stated anywhere
  (**UNVERIFIED**). Swiss 10 practice agrees (decisive games are played to
  mate, see "TCEC Swiss (primary target)").
- **Draw rule history** from the same revision history: S19-S20 and the
  Leagues page until at least 28 Mar 2022: from move 35, both evals within
  ±0.15 for 10 plies, reset by pawn move or capture (S17 used ±0.08). From at
  least 15 Aug 2022: ≤8 pawns and ≤8 pieces, both evals within ±0.20 for 10
  plies. From at least 5 Jan 2023: the current 6-piece ±0.25 8-ply rule.
- **Resignation**: listed as a way to win, but no page says what triggers it
  (engine or GUI rule): **UNVERIFIED**. In Swiss 10 none of 212 decisive
  games ended other than by mate.
- **Server outage only** (not adjudication during normal play): both evals
  at ±10 or beyond → win; both within ±0.15 and both engines past 35 moves →
  draw; otherwise restart from the reached position with time compensation.
  Wording differs slightly: the numbered Swiss/Cup/Leagues copies say "equal
  to or more than ABS(10)", the prose copies on the Rules and Leagues pages
  say "more than +10 / less than -10"; they also say "five" or "four"
  scenarios while listing four. Kept in `tcec.json` as `outage_only`.

### Adjudication and game end (current written rules)

- Draw: threefold, 50-move rule, stalemate, TCEC draw rule.
- TCEC draw rule: position has ≤ 6 pieces counting kings, not pawns; eval of
  the move leading to it within [-0.25, 0.25]; draw after 8 consecutive plies
  meeting the rule; reset by an out-of-band or missing eval or a promotion
  that makes a 7th piece; not reset by captures or pawn moves; no minimum
  move number. (The rule is worded per move; whether both engines' evals
  must satisfy it is not spelled out: **UNVERIFIED** "both engines".)
- Win: mate, illegal move by the opponent, resignation, loss on time. No
  eval-threshold win adjudication in the current rules (re-verified
  2026-10-23); who/what triggers "resignation" (engine or GUI rule) is
  **UNVERIFIED**.
- Server outage only (not normal-play adjudication): both evals ≥ +10 or
  ≤ -10 → win; both within ±0.15 and both engines past move 35 → draw;
  otherwise restart with time compensation.
- Tablebase adjudication: none in the current rules (removed between
  Oct 2024 and May 2025, see re-verification above). S20 rules had cutechess
  adjudicate with 6-man Syzygy.
- Why it matters for Fork: Fork must report honest evals (DESIGN rule). The
  draw rule only fires in sparse endings, so Fork's endgame eval near 0 for
  ≤6 pieces decides how quickly dead draws end; it should not affect search
  decisions.

### NN and GPU rules

- GPU engines (Lc0, Ceres, CatGPT) run on the GPU server; from S30 any engine
  may use both machines on its turn. Verified (Further info page).
- TCEC NNUE Guideline (unofficial, edited 10 Jan 2022): NNUE code may be used
  as if it were a library; modifying it is strongly encouraged; all training
  data must be generated by the engine's own search and/or eval. Applies only
  to NNUE. Questionnaire Q10 asks for compliance. See `originality.md`.
- No rule on net uniqueness (e.g. a similarity threshold between nets) found
  on any opened page: **UNVERIFIED / not found**.

### Changes vs older seasons

| Item | S20 (2020-21) | Current (S28-S30) |
|---|---|---|
| Structure | QL, L4, L3, L2, L1, Premier, SuFi | Swiss, Cup, EL, L2, L1, Premier, SuFi, plus 4k, HCE, FRD |
| TC | 30'+5" (QL-L2), 45'+5" (L1), 60'+7" (Prem), 120'+10" (SuFi) | 30'+3", 60'+6" (Prem), 120'+12" (SuFi) |
| Draw rule | from move 35, both evals within ±0.15 for 5 moves (10 plies), reset by pawn move/capture | ≤6 pieces, ±0.25, 8 plies, no minimum move |
| Win rule | dropped in S20 (S19 had ±10.00 for 10 plies; confirmed on the S19 and S20 rule pages) | none |
| TB | 6-man Syzygy adjudication | no TB adjudication (removed Oct 2024-May 2025); 7-man Syzygy for engines |
| CPU | 4x Xeon E5-4669v4, 176 threads (to S21) | 2x EPYC 9754, 512 threads |
| Entry | invitation | invitation + mandatory questionnaire (S29+), categories, AI policy (S30) |

---

## 3. CCC (chess.com Computer Chess Championship)

- Latest event write-up opened: "CCC25 Rapid" (Andrew Grant's chess.com
  blog, 17 Nov 2025): TC 10+3; three qualifiers (3x DRR), main stage of 12
  (4x DRR: Stockfish, Torch, Reckless, Obsidian, Leela, Integral,
  PlentyChess, Berserk + 4 qualifiers), semifinal 16x DRR, challenger and
  final 250 games each. Seeding from CCC25 Blitz, where Stockfish beat Torch
  276.5/500 in the final. Engines are chosen by the organisers; no public
  application route found.
- Hardware, hash, threads, TBs, adjudication for current CCC: not on any
  page I could open (chess.com CCC page is script-rendered): **UNVERIFIED**.
  Search-result snippets mention 6-man Syzygy in early events; not relied on.
- CCC events after Nov 2025: **UNVERIFIED**.
- Why it matters: secondary venue; uses short TCs (bullet to rapid) where
  Fork's time management differs from TCEC. Tag: REFERENCE ONLY.

---

## 4. Rating lists

### CCRL (computerchess.org.uk/ccrl)

Testing conditions (40/15 About page, 23 Oct 2026): TC equivalent to 40
moves/15 min repeating on an i7-4770k, calibrated with Stockfish 10; hash
256 or 512 MB (equal within an event; 4-CPU engines may get up to 4x);
4/5/6-piece TBs; ponder off; generic book up to 12 moves, engine books
must be disabled (engines that cannot disable their book are excluded);
learning off. Members test what they choose; CCRL explicitly does not judge
originality, and listing an engine implies nothing about its status.
Submission procedure for authors: not on the page (**UNVERIFIED**; the
page points to the CCRL forum).

CCRL 40/15 (computed 23 Oct 2026, best versions):

| # | Engine | Elo |
|---|---|---|
| 1 | Stockfish 19 4CPU | 3650 |
| 2 | Reckless 0.9.0 4CPU | 3645 |
| 3 | PlentyChess 7.0.0 4CPU | 3643 |
| 4 | pawnocchio 2.0.1 4CPU | 3642 |
| 5 | Torch v4d 4CPU | 3640 |
| 6 | Coda 0.9.4 4CPU | 3639 |
| 7 | Integral v8 4CPU | 3638 |
| 8-9 | Cinder 0.6.1 4CPU | 3637 |
| 8-9 | Obsidian 16.0 4CPU | 3637 |
| 10-12 | Alexandria 9.0.0 / Hobbes 3.0 / Stormphrax 8.0.0 4CPU | 3635 |

CCRL Blitz 2'+1" (list dated 17 Oct 2026; up to 6-piece TB, 12-move book,
ponder off):

| # | Engine | Elo |
|---|---|---|
| 1 | Stockfish 19 8CPU | 3804 |
| 2 | Triumviratus 7.0 8CPU | 3780 |
| 3 | Torch v4 8CPU | 3779 |
| 4-5 | Obsidian 16.0 8CPU | 3774 |
| 4-5 | PlentyChess 8.0.0 | 3774 |
| 6 | Coda 0.9.4 | 3770 |
| 7 | Reckless 0.9.0 | 3766 |
| 8 | Cinder 0.6.1 | 3762 |
| 9 | Berserk 20250606 8CPU | 3760 |
| 10 | Dragon by Komodo 3.3 8CPU | 3757 |

CCRL 40/2 FRC (4 Oct 2026; 5-piece TB, 256 MB hash, random FRC starts with
colours switched):

| # | Engine | Elo |
|---|---|---|
| 1 | Stockfish 19 | 4116 |
| 2 | Reckless 0.9.0 | 4101 |
| 3 | Lc0 0.32.1 RTX 5050 BT4-it332 | 4082 |
| 4 | Torch v4 | 4082 |
| 5 | pawnocchio 2.0.1 | 4082 |
| 6 | PlentyChess 8.0.0 | 4076 |
| 7 | Stormphrax 8.0.0 | 4071 |
| 8 | Viridithas 20.0.0 | 4070 |
| 9 | Caissa 2.0 | 4055 |
| 10 | Hobbes 3.0 | 4055 |

Tag: REFERENCE ONLY. Why it matters: a CCRL rating is the usual public proof
of strength before TCEC invites an engine (the 3000+ bar is on TCEC's own
list, but new engines get a provisional TCEC rating from testing).

### CEGT (cegt.net; HTTPS fails, read over HTTP)

- "40/40" index page (last update 18 Oct 2026, Ordo, 2,250,721 games); best
  versions list is titled "40/20 (AMD 4200+)":

| # | Engine | Elo |
|---|---|---|
| 1 | Stockfish 19.0 1CPU | 3649 |
| 2 | Integral v8 1CPU | 3623 |
| 3 | Stockfish dev-20251114 | 3621 |
| 4 | Stockfish 18.0 1CPU | 3621 |
| 5 | Torch 4d 1CPU | 3619 |
| 6 | PlentyChess 8.0.0 1CPU | 3617 |
| 7 | Stockfish 17.0 1CPU | 3617 |
| 8 | Cinder 0.6.1 1CPU | 3616 |
| 9 | Reckless 0.9.0 1CPU | 3615 |
| 10 | Stockfish 16.1 1CPU | 3612 |

- Blitz 40/4 (last update 6 Jun 2025, stale): top 3 Stockfish 17.1 3668,
  Torch 3 3663, Obsidian 15.0 3634, then Komodo Dragon 3.3, Alexandria 8.0.0,
  PlentyChess 5.0.0, Berserk 13.0, Caissa 1.22, Integral 7, Horsie 1.0.
- 5'+3" ponder-on list (9 Jul 2025): 1 core per engine, 256 MB hash, 3-4
  piece EGTB, no learning; anchor Revenge 4.0 = 3550.
- 40/20 testing conditions (hash, TBs, hardware) and any derivative or
  submission policy: not on pages opened (**UNVERIFIED**). CEGT has a forum
  (cegt.forumieren.net) and a testers page, not opened.

---

## 5. Engines Fork will face (pinned builds for Phase 8 gauntlets)

All repo facts from the GitHub API and READMEs on 2026-10-23. "Pin" means the
exact tag (and, where nets are separate, the exact net file) to fetch. Fork
uses these only as opponent binaries in testing: **never** read their source
for implementation, and never use their nets or data in Fork.

| Engine | License | Latest release (date) | Repo | Eval | Pinned build | Tag |
|---|---|---|---|---|---|---|
| Stockfish | GPL-3.0 | sf_19 (5 Sep 2026) | github.com/official-stockfish/Stockfish | NNUE; nets trained on Lc0 data (ODbL) per README | tag `sf_19`, `make build ARCH=x86-64-avx2`, nets fetched by makefile (record hash) | OFF-LIMITS for code/nets; opponent binary USE |
| Lc0 | GPL-3.0 | v0.32.1 (23 Nov 2025) | github.com/LeelaChessZero/lc0 | large NN (GPU) | tag `v0.32.1` + a named network file (e.g. BT4 as on CCRL) | OFF-LIMITS (code/nets/data); opponent USE if GPU available |
| Reckless | AGPL-3.0 (from v0.9.0; v0.7.0 was MIT) | v0.9.0 (1 Mar 2026) latest stable; dev pre-releases up to v0.10.0-dev-7300f044 (1 May 2026); TCEC runs 0.10.0-dev | github.com/codedeliveryservice/Reckless | NNUE (bullet trainer); current data source not stated (see §7) | tag `v0.9.0` | OFF-LIMITS code; opponent USE |
| PlentyChess | GPL-3.0 | b-v8.0.0 (27 Jun 2026) | github.com/Yoshie2000/PlentyChess | NNUE, self-generated data (15B+ positions) | tag `b-v8.0.0`, `make` embeds net | OFF-LIMITS code; opponent USE |
| Integral | no license file detected (all rights reserved by default) | v8 (11 Sep 2026) | github.com/aronpetko/integral | NNUE, self-play data (bullet) | tag `v8` binary/build for testing only | OFF-LIMITS; opponent USE (license **UNVERIFIED**, ask before redistributing) |
| Obsidian | GPL-3.0 | v16.0 (21 May 2025) | github.com/gab8192/Obsidian | NNUE trained on Lc0 data (README) | tag `v16.0` | OFF-LIMITS; opponent USE |
| Berserk | GPL-3.0 | 14 (24 May 2026) | github.com/jhonnold/berserk | NNUE; data source not stated in README excerpt | tag `14` | OFF-LIMITS; opponent USE |
| Caissa | MIT | 2.0 (19 Sep 2026) | github.com/Witek902/Caissa | NNUE, self-play data (20.5B+ positions) | tag `2.0` | OFF-LIMITS code (MIT allows reuse, but Fork's policy is no copying); opponent USE |
| Viridithas | AGPL-3.0 per GitHub (questionnaire says MIT: **conflict**) | v20.0.0 (27 Jun 2026) | github.com/cosmobobak/viridithas | NNUE, own data (+ Lichess Elite rescored by itself) | tag `v20.0.0` + matching net from viridithas-networks | OFF-LIMITS; opponent USE |
| Alexandria | GPL-3.0 | v9.1.0 (4 Oct 2026) | github.com/PGG106/Alexandria | NNUE trained on Lc0 data (README) | tag `v9.1.0` + net from Alexandria-networks | OFF-LIMITS; opponent USE |
| Stormphrax | GPL-3.0 | v8.0.0 (27 Jun 2026) | github.com/Ciekce/Stormphrax | NNUE from zero, self-generated data only; no LLM code | tag `v8.0.0` | OFF-LIMITS; opponent USE |
| pawnocchio | GPL-3.0 (assets CC-BY-ND) | v2.0.1 (29 Jun 2026) | github.com/JonathanHallstrom/pawnocchio | NNUE, own self-play + Vine games | tag `v2.0.1` + submodule net | OFF-LIMITS; opponent USE |
| Ethereal | GPL-3.0 (repo) | v14.00 (8 Feb 2023); NNUE versions sold commercially | github.com/AndyGrant/Ethereal | HCE in public repo; NNUE commercial | tag `v14.00` | OFF-LIMITS; opponent USE |
| Torch | closed (chess.com) | v4 / v4d on CCRL | none public | NN (chess.com: original code; some versions partly trained on Lc0 data per search snippet, not confirmed) | not obtainable | OFF-LIMITS; cannot pin |
| Dragon (Komodo) | commercial | 3.3 on CCRL/CEGT | none public | NNUE | komodochess.com (TLS certificate expired on 2026-10-23, not opened): **UNVERIFIED** | OFF-LIMITS; buy only if needed |

Not checked (named in brief or lists, not opened): Coda, Cinder, Hobbes,
Triumviratus, Ceres, Halogen. **UNVERIFIED**.

Recommended Phase 8 gauntlet ladder (all open-source, all buildable on Linux
and Windows from a tag): Stormphrax v8.0.0, Caissa 2.0, Alexandria v9.1.0,
Berserk 14, PlentyChess b-v8.0.0, Reckless v0.9.0, Stockfish sf_19 (with
`Threads`/`Hash` matched). Record each binary's SHA-256 and net hash in the
gauntlet log. Add weaker anchors (e.g. Ethereal v14.00) for early phases.

---

## 6. Rating-list entry procedures

- CCRL: testers choose engines; no author submission route on the pages
  opened. CCRL does not rule on originality. **UNVERIFIED** how to request
  testing (forum link points to kirill-kryukov.com board).
- CEGT: no procedure on the pages opened. **UNVERIFIED**.
- TCEC: email the questionnaire; organisers invite. See §2.

---

## 7. Reference case: Reckless (new engine → S29 Superfinal)

Tag: **REFERENCE ONLY** (history and practices as ideas; Reckless code,
nets and data are OFF-LIMITS to Fork, see §5). Checked 2026-10-23.

**Claim checked: confirmed.** Reckless played the TCEC Season 29 Superfinal
and lost 41-59 to Stockfish (TCEC archive crosstable JSON; chessdom.com,
21 Apr 2026). It qualified as runner-up of the S29 Premier Division (34/56,
one point behind Stockfish, ahead of Lc0, PlentyChess, Torch, Integral,
Obsidian, Berserk). Chessdom called it the first Superfinal in many seasons
without Lc0. The match was restarted from game 1 after observers noticed
Reckless running at about half its Premier speed; TCEC's admin traced it to
a newer compiler, and all three parties agreed to rebuild the same version
with another Rust toolchain (chessdom.com, 27 Mar 2026).

### Repository facts (GitHub API and releases, 2026-10-23)

- Repo `codedeliveryservice/Reckless`, Rust. First commit 3 Dec 2022
  ("Initial commit", author Arseny); repo created 31 Dec 2022; about 1,800
  commits; still active (push on 23 Oct 2026).
- Authors: Arseniy Surkov (lead, GitHub `codedeliveryservice`, ~1,350
  commits); co-authors Shahin M. Shahin (`peregrineshahin`, Stockfish /
  Fishtest contributor, ~160 commits) and Styx (`styxdoto`, NNUE, testing
  infrastructure and hardware). Other contributors named by the author:
  CJ (Alexandria), Lily, Protonspring (Torch), Viren (Monty) (chessdom
  interview, 27 Mar 2026; GitHub contributors list).
- License: MIT at v0.7.0; no LICENSE file in the v0.8.0 tag; AGPL-3.0 from
  v0.9.0 (stated in the v0.9.0 notes).

| Release | Date | Highlights (release notes) | CCRL Blitz (README table) |
|---|---|---|---|
| v0.1.0 | 16 May 2023 | basic PVS, aspiration, NMP, LMR, killers/history; HCE from the "simplified evaluation" recipe | 2005 |
| v0.2.0 | 6 Oct 2023 | tapered eval with tuning, RFP, fail-soft, copy-make | 2349 |
| v0.3.0 | 5 Nov 2023 | king-relative PST, gradient-descent tuning, time management, LMP | 2616 |
| v0.4.0 | 13 Dec 2023 | IIR, futility, "improving", history-adjusted LMR, persistent history | 2934 |
| v0.5.0 | 4 Feb 2024 | NNUE replaces HCE; data from self-play starting from a random net, retrained iteratively; own trainer | 3240 |
| v0.6.0 | 21 Mar 2024 | Lazy SMP, SCReLU, continuation histories, SPSA session, AVX2 SIMD; thanks Andrew Grant for OpenBench and CPU time | 3386 |
| v0.7.0 | 23 Aug 2024 | (768→384)x2→1x4 net, time management by score/best-move stability, SEE, multithreaded TT init | 3500 |
| v0.8.0 | 30 Aug 2025 | search rebuilt after the FIDE & Google Kaggle efficient-chess challenge (team 2nd place, with Shahin); bullet trainer, 30+ nets, multi-layer net on "billions of positions"; 7-man Syzygy via Fathom; Chess960/DFRC. +335 Elo STC vs v0.7.0 | 3765 |
| v0.9.0 | 1 Mar 2026 | threat-input NNUE on top of king-bucketed PSQ inputs; NUMA-aware threads; MultiPV; AGPL. +62 Elo LTC, +71 SMP vs v0.8.0 | 3767 |
| v0.10.0-dev builds | Apr-May 2026 | +12 Elo STC/LTC vs v0.9.0 | n/a |

### TCEC history (TCEC archive crosstable JSON per event; wiki Swiss pages)

| Season | Event | Version | Result |
|---|---|---|---|
| — | first TCEC application | — | Aug 2024 (chessdom, 23 Mar 2026) |
| S27 | Cat 0+2 playoff (1 DRR, 4 Swiss spots) | 0.7.0 | 8th of 9 (6/16), did not reach Swiss 7. Swiss 7 page made entry conditional on multithreaded hash init (98 GB) |
| S28 | Cat 2 playoff | 0.8.0-dev | 1st of 13 (17/24) |
| S28 | Swiss 8 | 0.8.0-dev | 22nd of 44 (11/22) |
| S28 | League 2 | 0.8.0-dev | 1st of 12 (29/44), promoted |
| S28 | League 1 | 0.8.0-dev | 3rd of 12 (25.5/44), missed promotion by one place |
| S28 | FRD 4 | 0.9.0-dev | won Semileague 2 and League C; 3rd of 6 in Final League |
| S29 | Swiss 9 | 0.9.0-dev | 8th of 44 (12.5/22), won tiebreak for seeds 6-8 |
| S29 | League 1 | 0.9.0-dev | 1st of 12 (28.5/44) |
| S29 | Premier Division | 0.9.0-dev | 2nd of 8 (34/56) → Superfinal |
| S29 | Superfinal | 0.10.0-dev | lost 41-59 to Stockfish |
| S29 | FRD 5 | 0.10.0-dev | 2nd in Semileague 2, won League C, 4th of 6 in Final League |
| S30 | Swiss 10 (Cat 0, placed directly) | 0.10.0-dev | 8th of 48 after 17 games (in progress) |

How Reckless went from Swiss 8 into League 2 rather than the Entrance League
in S28 is not explained on the pages opened (**UNVERIFIED**). Cup results
(the Cup bracket JSON was not found) are **UNVERIFIED**.

### Training data provenance

- v0.5.0 (Feb 2024): data from Reckless's own self-play, starting from a
  random net and regenerated each iteration (release notes). PR #74
  (Oct 2024): whole dataset regenerated with Reckless itself after an SPSA
  session. Both are own-engine data, consistent with the TCEC NNUE
  Guideline.
- v0.8.0 onward: bullet trainer, "billions of positions"; neither the
  README, the release notes nor the `RecklessNetworks` repo states where the
  current data comes from, and the S29 questionnaire (v2.3, 24 Oct 2025) is
  confidential on the TCEC wiki. Current provenance: **UNVERIFIED**.
- For Fork: the early Reckless pipeline (own self-play from a random net,
  own trainer, regenerate and retrain) is a pattern Fork may copy as an
  *idea*. Reckless's nets or data themselves are not acceptable for Fork in
  any case (another engine's output, AGPL project), and nothing about the
  current nets can be cited as a clean-data model until provenance is
  confirmed.

### What got it there (timeline and practices)

- Timeline: first commit to first release ~5.5 months; HCE to NNUE in 14
  months; first TCEC application ~20 months after the first commit;
  application to Superfinal ~19 months; first commit to Superfinal ~3 years
  4 months. The big jump (CCRL Blitz 3500 → 3765, +335 Elo self-play) came in
  one year after a team formed around strong search specialists.
- Testing: OpenBench from early on (Andrew Grant's instance, then its own at
  recklesschess.space, test IDs past 14,000 by May 2026) with fastchess;
  every release reports STC 8+0.08 and LTC 40+0.4 results with pentanomial
  stats; SMP and DFRC tests before release; SPSA tuning; donated hardware.
- Engineering: GitHub Actions workflow files named for architectures, bench
  check, games, PGO and release; AVX2/AVX-512 builds, multithreaded TT init, NUMA
  binding, 7-man Syzygy, Chess960 — the TCEC-specific items (big hash, 512
  threads, NUMA, TBs) were in place before its Superfinal run.
- Cautions: Reckless lost two Swiss 8 testing games on time (Swiss 8 page),
  and its Superfinal
  build lost half its speed to a toolchain change. The author says search was
  rebuilt after a deep study of Stockfish search; Fork's originality rules
  rule out that route (ideas only from papers/CPW, never another engine's
  code).

### What Fork can adopt (ideas only)

1. SPRT on an OpenBench-style setup from day one, STC + LTC + SMP gates,
   published pentanomial results per release.
2. Own-data NNUE bootstrapped from self-play, regenerated as the engine
   improves (the v0.5.0 recipe), with written provenance for the
   questionnaire.
3. Ship TCEC must-haves early: multithreaded hash init, NUMA-aware threads,
   7-man Syzygy, MoveOverhead option, speed check of the exact TCEC build
   (`bench` NPS against the release binary).
4. Release notes with Elo evidence per version; a public repo (mandatory for
   Category 4 anyway).
5. Expect a multi-season climb: Reckless needed S27 (failed playoff) to S29.
   For Fork as Cat 4 in S30 rules, the reachable steps are the Cat 3+4
   playoff, the Swiss, and the AI gauntlet.
