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
2. **Engines get 7-man Syzygy through the UCI `SyzygyPath` option**
   (`/home/syzygy7`), identically in the Swiss, its playoffs, the Cup and the
   Leagues (archived game headers, see §2 "Tablebases available to
   engines"). The servers hold WDL and DTZ; a separate
   `/home/syzygy7_no_dtz` directory exists and was used for one engine in
   S29 bonus events, which implies the default path carries DTZ (strong
   inference, not stated: **UNVERIFIED**). The 6-man Scorpio bitbases on the
   server are not passed to engines through any UCI option seen in archived
   games; Fork has no use for them. Fork must probe 7-man tables (Fathom
   handles 7-man) and should `madvise(MADV_RANDOM)` the mapped files, which
   TCEC asks of 7-man users. Re-read 2026-10-26 (revision 8475): the
   wording is unchanged. Fathom at the pinned commit already makes that
   call for every mapped table when compiled as C++ or GNU C; strace and
   `/proc/self/smaps` confirmed it (tools.md §6.4). Tablebases are never
   used for adjudication now (§2).
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

Re-checked 2026-10-23 against the wiki TCEC_Swiss_10 page (current text and
revisions 9159, 9185, 9410, 9411), the categorisation flowchart image, the
S30 season flowchart image, the Main Page, the Questionnaire page, the
Current_Engine_Status page, the Cat 3 and Cat 4 entrants' questionnaires,
the TD statement and the chessdom TCEC tag feed. Full category definitions:
"Swiss categories in full" below.

1. **Apply.** The wiki Main Page says developers must take the initiative
   and apply by sending a fully completed TCEC Questionnaire (v2.4); the
   Questionnaire page says it is sent by email. No address is printed on
   either page (**UNVERIFIED** address; the Swiss 10 page names the TD, Kan
   and Aloril as appeal recipients, reply-all on the invitation email).
   Swiss 10 deadline: 1 Jul 2026, 12:00 UTC. The first categorisation was
   posted 18 Jun 2026 and invitations went out on 24 Jun 2026 (revision
   comments). No minimum strength or rating for the Swiss is published
   (**UNVERIFIED**; the 3000+ TCEC Elo bar is a Leagues rule).
2. **Be categorised.** TCEC assigns the category and announces it in chat
   and Discord; authors then have 24 h to appeal by email with substantial
   arguments; the TD's decision is final. Swiss 10 categorisation became
   final on 8 Sep 2026, 00:28 CEST, with no appeal. An engine that qualifies
   under one category may not change architecture mid-season so that it
   would fall into a higher-numbered category; the Potential decision
   (Swiss 10) adds that authors must keep the questionnaire current and
   notify TCEC promptly of architecture changes.
3. **Fork will be Category 4.** Any engine "created with major help from AI
   technology" is Cat 4, whatever the originality flowchart would say.
   Requirements: source open and publicly viewable (e.g. GitHub) at
   submission and throughout participation; TCEC admins must be allowed to
   build the binary from that repository.
4. **Cat 4 pre-stage.** Cat 4 engines compete for **one** place in the Cat 3
   playoff. From 21 Jun to 6 Sep 2026 (revisions 9185-9410) the page said
   this Cat 4 playoff would be "at least 1 DRR at 30+3 as needed"; the final
   text (revision 9411, 6 Sep 2026) keeps the single place but drops the
   format. With only one Cat 4 entrant in S30 (CatGPT) no pre-stage was
   played. Format with several Cat 4 entrants: **UNVERIFIED**.
5. **Cat 3+4 playoff:** 12 DRR at 30'+3" for 1 Swiss spot (Swiss 10 values;
   the organisers fix the spot counts x, y, z per event depending on
   applicants; an intermediate revision had 9 DRR). Qualification on points
   only, extra game pairs (2 tied) or extra DRRs (3+) as needed. S30: 3
   engines (Cinder, Serendipity, CatGPT as the only Cat 4), 72 games,
   9-12 Sep 2026; Cinder 31.5/48 qualified, CatGPT 27/48, Serendipity
   13.5/48 (TCEC archive crosstable JSON). Cinder is a top-10 CCRL engine
   (§4), so the bar is high.
6. **Swiss.** The qualifier joins the 48-engine Swiss. In S30 an AI engine
   is not eligible for the Leagues whatever its Swiss result (TD statement,
   31 Aug 2026); for other engines, the 17 Swiss entrants without a Leagues
   place play for 7 Entrance League spots.
7. **Extra gauntlet.** The TD statement promises a dedicated extra gauntlet
   as a separate path for AI engines. As of 2026-10-23 there is no wiki
   page (TCEC_AI_Gauntlet 404), no archive event and no later chessdom
   article (TCEC tag feed: nothing after 31 Aug 2026). Format, date and
   entry: **UNVERIFIED** (re-checked 2026-10-24: TCEC_AI_Gauntlet still 404,
   tag feed still ends at 31 Aug 2026).
8. **Season 31.** The Main Page lists Swiss 11 and Leagues S31 as upcoming,
   but TCEC_Swiss_11, TCEC_Leagues_Season_31 and TCEC_Season_31 do not exist
   yet (404). S31 categories, Cat 4 policy and deadlines: **UNVERIFIED**
   (not published; all three pages still 404 on 2026-10-24). By the S30 timeline (deadline 1 Jul, Swiss in October)
   an S31 application window might fall around mid-2027; that is an
   extrapolation, not a published date.

**Decision (owner, 2026-10-23): Fork's entry path is Category 4 via the
Cat 3+4 playoff** (steps 1-6 above). Consequences for the repository: it
must be public before the application, and TCEC builds Fork from source.

### Open questions to ask in TCEC's Discord

None of these is answered on any page opened on 2026-10-23.

1. **Questionnaire address:** which email address takes the completed
   questionnaire (v2.4)? No address is printed on the wiki Main Page or the
   Questionnaire page.
2. **Minimum strength:** is there a minimum strength or rating for a Swiss
   or Cat 3+4 playoff entry? None is published (the 3000+ TCEC Elo bar
   applies to the Leagues).
3. **License requirement:** does Category 4 require an OSI-approved
   open-source license, or is a source-available license enough? The
   published rule only asks for public, buildable source; the CatGPT
   precedent was accepted with PolyForm Noncommercial. *Note (2026-10-24):*
   Fork is licensed GPL-3.0 (owner's choice, 2026-10-24), an OSI-approved
   license (https://opensource.org/license/gpl-3-0), so it meets the
   stricter reading either way; the question stays open only as general
   information and is no longer blocking for Fork.
4. **Match runner:** what match runner and version do TCEC servers
   currently use? TCEC's cutechess fork (TCEC-Chess/tceccutechess) has had
   no pushes since 2023-04-09, so it may no longer be what runs. Until
   answered, Fork's compliance testing uses `fastchess --compliance` plus
   standard cutechess-cli (tools.md).
5. **Move Overhead:** what `Move Overhead` value does TCEC recommend for
   its servers and GUI? Fork defaults to 100 ms (owner, 2026-10-24);
   TCEC's own example sets Reckless's `MoveOverhead=1000`. (Added
   2026-10-24.)
6. **Kernel and overcommit:** what Linux kernel version and overcommit
   setting (`vm.overcommit_memory`, and `vm.overcommit_ratio` if mode 2)
   do the TCEC servers use? Fork checks each Hash request against
   `MemAvailable` before allocating, and in the default mode 0 the kernel
   tests each request alone: against RAM + swap since Linux 5.2, against
   free memory + swap before ([os-memory.md](os-memory.md) §2). Knowing
   the setting confirms how a too-large Hash is refused on the servers.
   (Added 2026-10-24, owner.)
7. **Explicit huge pages:** "Large pages: enabled automatically" reads as
   transparent huge pages. Do the servers also reserve a hugetlbfs pool, and
   may an engine use `MAP_HUGETLB` (2 MiB or 1 GiB pages) for its hash?
   Fork uses `madvise(MADV_HUGEPAGE)` today (main's ideas.md idea 19).
   (Added 2026-10-25, owner.)
8. **CPU features:** do both servers' CPUs (EPYC 9754, EPYC 9175F) support
   AVX-512 VNNI, and which `-march` should TCEC's build use for them?
   (Main's ideas.md idea 20; to check in the CPU documentation as well.)
   (Added 2026-10-25.)

Training-data questions (added 2026-10-24, background in
[training-data.md](training-data.md) §5):

6. **One category per engine?** Does the Category 4 (AI) trait override
   the flowchart's data-origin branch? Would data origin matter for a
   Cat 4 engine now, or if AI engines later join the Leagues or a joint
   event? (CatGPT, with over 99 % Lc0 data, was placed in Cat 4.)
7. **NNUE Guideline:** is rule 3 (own search/eval data only) still
   applied, given that it has not been in the formal rules since S20 and
   Cup 7/8? Does it apply to Category 4 engines?
8. **"Hybrid" and "Other" data:** how does the flowchart classify
   human-game (Lichess CC0) positions rescored by the engine itself,
   Syzygy WDL/DTZ used as labels, and own self-play started from
   human-game openings?
9. **Bootstrapped chains:** if a net chain started on Lc0 data and was
   later trained only on the engine's own self-play, is that "own data"?
10. **Mid-season rule:** does "architecture" in the no-higher-category
    rule include a change of training-data source?
11. **GPU Competition:** is the new TCEC GPU Competition (wiki pages
    created 2026-10-24) the AI gauntlet promised on 31 Aug 2026? Will
    CPU-only Category 4 engines get a path?
12. **Archive terms:** are there terms of use for tcec-chess.com data
    beyond the tcecgames README's CC BY-SA 3.0 note?

### Swiss categories in full (S30 / Swiss 10)

Sources: TCEC_Swiss_10 regulations; categorisation flowchart
(File:TCEC_playoff_categorizing.png, uploaded 8 Apr 2025, embedded unchanged
on the Swiss 9 and Swiss 10 pages); S30 season flowchart
(File:TCEC_S30+_cats_flowchart.png, "v1", uploaded 18 Jun 2026). Checked
2026-10-23. Tag: REFERENCE ONLY.

How categories 1-3 are decided (flowchart; my reading of the image, rows
are the evaluation and data-origin branches, columns the "original
inventions" answer):

| Evaluation / data origin | Inventions: many or important | some | none |
|---|---|---|---|
| HCE | Cat 1 (every HCE engine goes to Cat 1) | Cat 1 | Cat 1 |
| NNUE, original data | Cat 1 | Cat 1 or 2 (TD decides) | Cat 2 |
| NNUE, hybrid data | Cat 1 | Cat 2 | Cat 2 or 3 (TD decides) |
| NNUE, other data | Cat 1 | Cat 1, 2 or 3 (TD decides) | Cat 3 |

The S30 season flowchart labels Cat 1 "highest originality", Cat 2 "second
highest priority" and Cat 3 "lowest priority". Precedent: Cinder (Cat 3)
declares NNUE data generated by Stockfish and Lc0 (Cinder questionnaire,
19 Jun 2026), i.e. "other" data. The same flowchart says an engine promoted
into League 2, League 1 or the Premier Division moves up one category
(3 → 2 → 1 → 0) and later relegation does not undo it; in S30 that path is
closed to Cat 4. Note the S30 flowchart "v1" shows older numbers (44 Swiss
places, 11 double rounds, 9 DRR Cat 3 playoff, no Cat 4); the event page's
48 / 13 / 12 DRR govern.

| Cat | Who | Route to the Swiss (Swiss 10) | Leagues (S30) |
|---|---|---|---|
| 0 | Engines with a Leagues place, not relegated from the lowest league (organisers' discretion; the flowchart says "unless outdated") | placed directly (32 in Swiss 10) | holds its place |
| 1 | HCE engines and highly original NN engines; new entrants are categorised by the flowchart | 1 DRR playoff at 30'+3" for 10 spots | via Swiss result (7 EL spots among non-Leagues entrants) |
| 2 | NN engines with own data but few inventions, or hybrid data with some | 2 DRR playoff at 30'+3" for 5 spots | same |
| 3 | NN engines trained on other engines' data with no notable inventions | joint Cat 3+4 playoff, 12 DRR at 30'+3", 1 spot | same |
| 4 | "Created with major help from AI technology" (revision 9185 heading: "Vibe coded engines") | one place in the Cat 3+4 playoff, decided among Cat 4 engines first | **not eligible**; separate extra gauntlet promised |
| 5 | Engines TCEC cannot feature (numbered Cat 4 until 21 Jun 2026, and in Swiss 9) | none | none |

What each may and may not do, as written:

- All playoff categories: playoffs decided on points only, with extra game
  pairs or DRRs between tied qualifiers; 24 h appeal after final
  categorisation; no mid-season architecture change into a higher-numbered
  category; questionnaire kept current.
- Cat 3: same rights as Cat 1-2, with a smaller quota and a longer playoff;
  a Cat 3 engine that reaches the Swiss can earn an Entrance League place
  (the Current_Engine_Status page lists Quanticade, a Leagues engine, as
  category 3). No source or binary rule beyond the general submission
  rules (update.sh or binary, §2).
- Cat 4: public open-source repository at submission and throughout
  participation; TCEC admins build the binary from it; one playoff place
  only; no Leagues in S30. Precedent: CatGPT (questionnaire 25 May 2026)
  declared virtually all code AI-generated with an AI IDE, licensed its code
  under PolyForm Noncommercial (source-available, not an OSI open-source
  license) and trained on Leela data; TCEC listed it as Cat 4 with "open
  repository present". Whether TCEC requires an OSI license is
  **UNVERIFIED** (no rule page says; Discord question 3). Moot for Fork:
  the owner chose GPL-3.0 on 2026-10-24 (main-branch `LICENSE`, commit
  2e1e445), which OSI lists as approved (opensource.org/license/gpl-3-0:
  approved 5 Sep 2007, SPDX `GPL-3.0`; checked 2026-10-24).
- Cat 5: cannot play.

What this means for Fork: plan for Cat 4. That means a public repo with a
clean source build on the TCEC servers' toolchains (Ubuntu 22.04; gcc 11.4,
g++-12, clang 16/19, §2), an `update.sh` that clones and builds, an honest
questionnaire (AI use, own-data provenance), and enough strength to beat
Cat 3 engines over a 12 DRR. A non-AI engine with Fork's originality (own
code, own data) would land in Cat 1 or 2, but under S30 rules the AI
criterion overrides that.

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
changes UNVERIFIED** (TCEC_Leagues_Season_30 and TCEC_Season_30 still 404 on
2026-10-24).

### Swiss 10 engine categories (S30)

Full definitions (from the categorisation flowchart) and rights: see
"Swiss categories in full" in the Swiss section above. Entrants per
category in Swiss 10:

- Cat 0: placed automatically (32 engines: Stockfish, Reckless, LCZero,
  PlentyChess, Torch, Integral, Obsidian, Berserk, Ceres, Pawnocchio, Halogen,
  KomodoDragon, RubiChess, Viridithas, Caissa, Stormphrax, Clover, Ethereal,
  Quanticade, Ginkgo, Tarnished, Uralochka, rofChade, Seer, Stoofvlees, Horsie,
  Velvet, Heimdall, Renegade, Igel, Winter, c4ke).
- Cat 1: 1 DRR playoff for 10 spots (14 engines; HCE engines and highly
  original NN engines per the flowchart).
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
- Storage on both: 1 TiB NVMe system, 14 TiB NVMe for Syzygy 3-7, 14 TiB
  HDD for 7-man DTZ (how WDL/DTZ files split across the two drives beyond
  that is not stated).
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
| Tablebases | 7-man Syzygy via UCI `SyzygyPath=/home/syzygy7` in all divisions; 6-man Scorpio bitbases on the server but no engine option for them seen; see "Tablebases available to engines" | Further info; live.json; archived game headers | verified (DTZ in the default path: inferred) |
| Opening books | engine books removed/disabled; hidden book use = disqualification | Further info | verified |
| Other UCI options | left at default unless the author asks (e.g. Reckless runs with `MoveOverhead=1000`) | Further info; live.json | verified |
| Protocol | UCI or XBoard | Further info | verified |
| Contempt | default unless author asks | Further info | verified |

### Tablebases available to engines (checked 2026-10-23)

Tag: REFERENCE ONLY (facts). Why it matters: Fork's tablebase probing
(Syzygy via Fathom) and the UCI option name it must expose (`SyzygyPath`).

- **Rule text.** Further information page (current revision 8475,
  24 Feb 2026): for all divisions, 6-man Scorpio and 7-man Syzygy are
  available on NVMe and some RAM is reserved to cache them; 7-man Syzygy
  users should `madvise(MADV_RANDOM)`. That wording dates from revision
  6470 (11 Mar 2025, new S28 hardware) and the madvise sentence from 6471;
  before that the page said 5-man Nalimov/Gaviota/Scorpio and 6-man Syzygy.
- **WDL and DTZ.** Both servers: 14 TiB NVMe "Syzygy3-7" plus a 14 TiB HDD
  for "Syzygy7 DTZ". So 7-man DTZ exists on the machines (on HDD, which the
  tablebase paragraph's "on NVMe" does not mention). Verified for storage.
- **How engines get them: UCI `SyzygyPath`.** I parsed the engine options
  stored in game 1 of each of 57 S29/S30/Cup 16 archived events (TCEC
  archive `archive/json/<event>_1.pgn`), the live Swiss 10 game and Cat 3+4
  playoff games 2-4. Every engine that receives a TB setting gets it as
  `SyzygyPath`; values seen: `/home/syzygy7` (standard, all of Swiss,
  Cat 1/2/3+4 playoffs, Cup, EL, L2, L1, Premier, Superfinal, FRD),
  `/home/syzygy6` (Ginkgo in Swiss 9 and an FRD tiebreak, presumably at the
  author's request: **UNVERIFIED** why), and `/home/syzygy7_no_dtz`
  (Stockfish in four S29 bonus events). Author-chosen probe options also
  appear (`SyzygyProbeDepth`, `SyzygyProbeRootOnly`, `SyzygyProbeDepth6`,
  KomodoDragon's `Syzygy Probe Limit=7`). Engines without TB support get
  no path.
- **DTZ in `/home/syzygy7`.** Not stated anywhere; the existence of a
  separate `_no_dtz` directory strongly implies the default directory
  includes DTZ: **UNVERIFIED** (inference). Fork should handle both
  (WDL-only search probing, DTZ at the root when present).
- **Scorpio bitbases.** No option naming Scorpio, egbb or bitbases appears
  in any sampled game. The only ScorpioNN game checked (Swiss 8 game 7,
  16 May 2025) lists no options except the protocol, so if ScorpioNN used
  the bitbases it read their location from its own config file. Whether
  any engine actually uses them now: **UNVERIFIED**. No ScorpioNN entry in
  any S29/S30 crosstable (79 event crosstables checked). Fork: irrelevant.
- **Leagues vs Swiss.** No difference: same path in the Leagues, the Swiss,
  its playoffs and the Cup.
- **Adjudication.** No TB adjudication in the current rules (see
  "Adjudication re-verification").

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
| Integral | no license file detected (all rights reserved by default) | v8 (11 Sep 2026) | github.com/aronpetko/integral | NNUE, self-play data (bullet) | tag `v8` binary/build for testing only | OFF-LIMITS; opponent USE (re-checked 2026-10-24: GitHub API `license: null`, no LICENSE file in the root listing, so no license is granted; ask before redistributing) |
| Obsidian | GPL-3.0 | v16.0 (21 May 2025) | github.com/gab8192/Obsidian | NNUE trained on Lc0 data (README) | tag `v16.0` | OFF-LIMITS; opponent USE |
| Berserk | GPL-3.0 | 14 (24 May 2026) | github.com/jhonnold/berserk | NNUE; data source not stated in README excerpt | tag `14` | OFF-LIMITS; opponent USE |
| Caissa | MIT | 2.0 (19 Sep 2026) | github.com/Witek902/Caissa | NNUE, self-play data (20.5B+ positions) | tag `2.0` | OFF-LIMITS code (MIT allows reuse, but Fork's policy is no copying); opponent USE |
| Viridithas | AGPL-3.0 per GitHub (questionnaire says MIT: **conflict**) | v20.0.0 (27 Jun 2026) | github.com/cosmobobak/viridithas | NNUE, own data (+ Lichess Elite rescored by itself) | tag `v20.0.0` + matching net from viridithas-networks | OFF-LIMITS; opponent USE |
| Alexandria | GPL-3.0 | v9.1.0 (4 Oct 2026) | github.com/PGG106/Alexandria | NNUE trained on Lc0 data (README) | tag `v9.1.0` + net from Alexandria-networks | OFF-LIMITS; opponent USE |
| Stormphrax | GPL-3.0 | v8.0.0 (27 Jun 2026) | github.com/Ciekce/Stormphrax | NNUE from zero, self-generated data only; no LLM code | tag `v8.0.0` | OFF-LIMITS; opponent USE |
| pawnocchio | GPL-3.0 (assets CC-BY-ND) | v2.0.1 (29 Jun 2026) | github.com/JonathanHallstrom/pawnocchio | NNUE, own self-play + Vine games | tag `v2.0.1` + submodule net | OFF-LIMITS; opponent USE |
| Ethereal | GPL-3.0 (repo) | v14.00 (8 Feb 2023); NNUE versions sold commercially | github.com/AndyGrant/Ethereal | HCE in public repo; NNUE commercial | tag `v14.00` | OFF-LIMITS; opponent USE |
| Torch | closed (chess.com) | v4 / v4d on CCRL | none public | NN (chess.com: original code; some versions partly trained on Lc0 data per search snippet, not confirmed) | not obtainable | OFF-LIMITS; cannot pin |
| Dragon (Komodo) | commercial | 3.3 on CCRL/CEGT | none public | NNUE | komodochess.com (TLS certificate expired on 2026-10-23 and again on 2026-10-24, not opened): **UNVERIFIED** | OFF-LIMITS; buy only if needed |

Not checked (named in brief or lists, not opened): Coda, Cinder, Hobbes,
Triumviratus, Ceres, Halogen. **UNVERIFIED**.

Recommended Phase 8 gauntlet ladder (all open-source, all buildable on Linux
and Windows from a tag): Stormphrax v8.0.0, Caissa 2.0, Alexandria v9.1.0,
Berserk 14, PlentyChess b-v8.0.0, Reckless v0.9.0, Stockfish sf_19 (with
`Threads`/`Hash` matched). Record each binary's SHA-256 and net hash in the
gauntlet log. Add weaker anchors (e.g. Ethereal v14.00) for early phases.

### Elo-baseline anchors (weak engines)

Verified 2026-10-25. Purpose: Phase 3 Milestone A needs a first strength
estimate for Fork (alpha-beta + TT + quiescence, material-plus-placement
eval, no pruning). Its rating is unknown; the 3400+ ladder above is
useless at that level. These engines are opponent binaries only (tag:
**REFERENCE ONLY** for their code, which must never be read for
implementation; **USE** as opponent binaries in local testing). None of
them needs a network file at the pinned tag, so nothing net-related is
involved even as an opponent.

Ratings are quoted from the CCRL complete lists (all versions), opened
2026-10-25: **CCRL Blitz 2'+1"** "Computed on October 24, 2026" and
**CCRL 40/15** "Computed on October 23, 2026". The version string is the
exact name CCRL prints. "n/l" = that version is not on that list. Errors
are the list's own +/- figure. Repo facts (licence, tags, commit SHAs)
come from the GitHub REST API; build commands from each tag's README or,
where the README has none, from the build file at the tag (marked).

| Target | Engine (CCRL name) | Blitz 2'+1" | 40/15 | Repo | Tag and commit | Licence | Linux build | UCI | Net |
|---|---|---|---|---|---|---|---|---|---|
| ~1600 | Shallow Blue 2.0.0 64-bit | 1578 +/-19 (1119 games) | 1618 +/-21 (776) | github.com/GunshipPenguin/shallow-blue | `v2.0.0` = a04fbd9861770c897eb566d83b0d2e3b17aa9fc0 (release 2019-01-16) | MIT (API and LICENSE at tag) | `make` in repo root (README); C++11 | yes (README: "A UCI chess engine") | none; hand-written eval (PST, pawns, king safety, mobility per README) |
| ~1900 | Stash 12.0 64-bit | 1883 +/-22 (750) | n/l | gitlab.com/mhouppin/stash-bot (CCRL's link); GitHub mirror github.com/mhouppin/stash-bot | `v12` = c59e2739e3d33eef9b177f2063187dbe2795233c (tag is named `v12`, CCRL says "12.0") | GPL-3.0 (LICENSE at tag) | `make` in repo root (README at v12 has no build text; root Makefile's default target builds `stash-bot`: from the Makefile, not the README) | yes (later READMEs; v12 README is one line) | none in tag listing |
| ~2000 | BBC 1.1 64-bit | 2020 +/-17 (1243) | n/l | github.com/maksimKorzh/bbc | `1.1` = eaca662a6b89219d65506caccb75e9ba22c8ec99 (release 2020-09-29, Linux binary attached) | GPL-3.0 per API (LICENCE file added 2020-10-18, after the 1.1 tag; the tag itself has no licence file) | `make` in `src/` (makefile at tag; README gives no command); single C file | yes (README feature list) | none at 1.1. **Do not use 1.3/1.4**: those releases embed Stockfish NNUE (`nn-eba324f53044.nnue`) |
| ~2200 | Stash 15.3 64-bit | 2173 +/-19 (982) | n/l | as Stash 12.0 | `v15.3` = 7d17ff80eb53b9d4808fd285c7439e641f1c5a3b | GPL-3.0 | `cd src && make` (README; optional `ARCH=x86-64`, `x86-64-modern`, `x86-64-bmi2`) | yes ("UCI-compliant", README) | none in tag listing |
| ~2500 | Stash 19.0 64-bit | 2473 +/-18 (1052) | n/l | as Stash 12.0 | `v19.0` = de408a3e8d8ffbd41f4b1608b19f18c69eac2512 | GPL-3.0 | `cd src && make` (README, same ARCH options) | yes | none in tag listing |
| ~2700 | Blunder 8.5.5 64-bit | 2662 +/-11 (2541) | 2693 +/-11 (2075) | github.com/deanmchris/blunder (CCRL links algerbrex/blunder, which now redirects) | `v8.5.5` = 89230a74a966b3400610271eca49c4be241e94cd (release 2022-07-20) | MIT (API and LICENSE at tag) | Go toolchain: `make build` in root, or `go build` in `blunder/blunder` (README) | yes (README) | none; Texel-tuned hand-written eval (README) |
| ~2900 | Weiss 1.0 64-bit | 2896 +/-17 (895) | 2847 +/-20 (560) | github.com/TerjeKir/weiss | `v1.0` = f44a4c654c67139ecbd5f3afd9da1ebe41241464 (release 2020-06-02, Windows zip only) | GPL-3.0 (COPYING.txt at tag) | `cd src && make` (from the makefile: the first target builds `weiss` with gcc `-march=native`; README has no build text) | yes ("a UCI chess engine") | none; built-in Syzygy probing (Fathom) and an online-book option `NoobBook` |

Alternates (also verified the same day): **Napoleon 1.8 64-bit** (Blitz
2203 +/-15, 40/15 2300 +/-14; github.com/crybot/Napoleon, tag `v1.8` =
83c3b2975cba6373e21b6ad9acf7f0f0b8cf7dc4, C++). Gives a non-Stash anchor
near 2200, but its LICENSE (GPL-3.0) was committed 2017-07-06, after the
v1.8 release (2017-06-28), and its root Makefile is qmake-generated with
`-march=native -mbmi2` and a Qt mkspecs include path, so a plain `make`
build is **UNVERIFIED**; the README gives no build command and still says
"Current Version: 1.7.0". Others on the Blitz list in range but not
checked further: Vice 1.0 (1978; source is a zip on bluefever.net, the
GitHub repo bluefeversoft/vice has no tags), Rustic Alpha 3.0.0 (1793; the
GitHub repo now only says it has moved to Codeberg), MinimalChess 0.6
(2439, C#/.NET, MIT, tag `v0.6`), WyldChess 1.51 (2603, C, GPL-3.0, tag
`v1.51`), GreKo 2021.06 (2767; home page greko.su, no repo opened).

Notes:
- Stash fills three slots from one code base. That keeps the build
  identical across levels but correlates the anchors' styles; swap in BBC
  1.1 or Napoleon 1.8 if diversity matters more than spacing.
- Only Shallow Blue, Blunder and Weiss are on both lists; the rest are
  Blitz-only. Use the Blitz figures as the common scale.
- CCRL ratings are at CCRL's conditions (2'+1" on an i7-4770K equivalent,
  12-move book, ponder off, up to 6-piece TBs); a local gauntlet at
  another TC and hardware gives a rating relative to these anchors, not a
  CCRL rating.
- Disable engine books and online lookups: Shallow Blue's `OwnBook` is off
  unless set (README); set Weiss `NoobBook` false explicitly (its default
  is **UNVERIFIED**: the README does not state it).
- Builds use `-march=native` in Weiss's and Shallow Blue's build files;
  fine for local opponents, but record the binary's SHA-256 per run.
- Stash's README ratings (about 2160 at v15.3, 2470 at v19.0) agree with
  CCRL to within about 15 Elo; whether every Stash tag up to v21 is
  hand-crafted-eval only is inferred from the absence of net files in the
  tag listings: **UNVERIFIED** beyond that.
- Not run: nothing here was downloaded, built or played. Whether each
  tag builds cleanly with today's gcc/Go on Ubuntu 22.04 is **UNVERIFIED**
  until the first build.

### Milestone B anchor set

Verified 2026-10-25. Owner's brief: keep Stash 15.3 and 19.0, add two or
three anchors rated about 2000-2600 on CCRL Blitz from code bases unrelated
to Stash and to each other, one of them replacing BBC 1.1 (its makefile at
`1.1` = eaca662 did not find its source, and the tag has no licence file).
Same rules as above: opponent binaries only, **REFERENCE ONLY** for code
(never read for implementation), **USE** as local test opponents. Only the
README, licence file and build files were opened for each engine; nothing
was downloaded, cloned or built.

Ratings: CCRL Blitz 2'+1" complete list (all versions), "Computed on
October 24, 2026", re-opened 2026-10-25; 40/15 complete list "Computed on
October 23, 2026" for the second column. The engine name is exactly as CCRL
prints it. Tags were resolved with `git ls-remote` (all three new tags are
lightweight, so the SHA is the commit) and the commit confirmed with the
GitHub commits API; licences from the GitHub repository API and the licence
file at the tag.

| Name (CCRL string) | CCRL Blitz | 40/15 | Repo | Tag = commit | Licence | Build directory and make arguments | Net |
|---|---|---|---|---|---|---|---|
| Belette 2.0.0 64-bit (replaces BBC 1.1) | 2115 +/-19 (938 games) | n/l | github.com/vincentbab/Belette (CCRL details link) | `v2.0.0` = 93b88300f8fdf0126f79326fbfce5b5911275935 (commit 2024-03-13; release "Belette 2.0.0" the same day, Linux and Windows AVX2-BMI2 binaries attached) | GPL-3.0 (API; file named `LICENCE` at the tag, GPL v3 text) | repo root, `make release` (README); binary at `build/Release/bin/belette`. C++20 with g++; flags hard-code `-mavx2 -mbmi2 -mpopcnt` and the release link is `-static` | none: README lists a tapered material + PeSTO PSQT eval |
| Stash 15.3 64-bit (kept) | 2173 +/-19 (982) | n/l | gitlab.com/mhouppin/stash-bot (mirror github.com/mhouppin/stash-bot) | `v15.3` = 7d17ff80eb53b9d4808fd285c7439e641f1c5a3b | GPL-3.0 | `src/`, `make` (optional `ARCH=x86-64`, `x86-64-modern`, `x86-64-bmi2`) | none in tag listing |
| Chal 1.3.0 64-bit | 2285 +/-17 (1078) | n/l | github.com/namanthanki/chal (CCRL details link) | `1.3.0` = 3e4ee1a135fceb41e2e8bf69eacf8a7a093d8fe7 (commit 2026-03-08; release "Chal 1.3.0" the same day, Linux and Windows zips) | MIT (API and `LICENSE` at the tag) | repo root, `make` (README; Makefile sets `VERSION = 1.3.0`, gcc `-O2 -std=gnu99`); binary at `bin/chal`. One C99 file | none: README describes a hand-written tapered eval (PeSTO tables plus a few terms) |
| Stash 19.0 64-bit (kept) | 2473 +/-18 (1052) | n/l | as Stash 15.3 | `v19.0` = de408a3e8d8ffbd41f4b1608b19f18c69eac2512 | GPL-3.0 | `src/`, `make` (same ARCH options) | none in tag listing |
| WyldChess 1.51 64-bit | 2603 +/-12 (2339) | 2679 +/-12 (1569) | github.com/Mk-Chan/WyldChess (CCRL details link) | `v1.51` = 322b028cb5e8ba4d8596ca71071d4a9428782f31 (commit 2017-07-03; release "WyldChess 1.51" the same day, from branch `v1.5patch`, Linux/Windows/Android binaries attached) | GPL-3.0 (API and `LICENSE` at the tag) | `src/`, `make` (README says the makefile is in `src`; makefile default target builds `wyldchess` with gcc `-std=c11 -O3 -flto`; `make popcnt` or `make bmi` add `-mpopcnt` / `-mbmi -mbmi2 -mpopcnt`). Do not pass `RELEASE=` (that path needs `TARGET` and writes to `../binaries/`) | none: hand-written eval per README; optional Syzygy probing (Fathom) |

Spacing: 2115, 2173, 2285, 2473, 2603 (gaps 58-188 Elo). Four unrelated
code bases (Stash, Belette, Chal, WyldChess).

Toolchain notes (from the README and build files only; nothing compiled):
- Belette: README says "Tested on Windows and Linux with GCC >= 12" (2024
  code, C++20), so a modern gcc is its intended toolchain. Needs an AVX2 +
  BMI2 CPU (README: other architectures unsupported). The `-static` link
  needs the static libstdc++/libc archives, which Ubuntu's normal g++ and
  libc6-dev packages provide (**UNVERIFIED** until the first build).
- Chal: written in 2026 for any C99 compiler (README); no old-toolchain
  signs.
- WyldChess: 2017 C11 code built then with gcc and MinGW (build.sh). gcc 10
  and later default to `-fno-common`, which breaks some older C code that
  defines globals in headers; whether WyldChess hits this is **UNVERIFIED**
  (it would need the source, which Fork does not read). If the build fails
  with "multiple definition" link errors, adding `-fcommon` through
  `CC_FLAGS` is the usual workaround, also **UNVERIFIED** here.

Engine options to set in the gauntlet:
- Chal: README states a fixed 16 MB TT (1,048,576 entries); whether it
  exposes a `Hash` UCI option is **UNVERIFIED**. Record the hash
  mismatch in the gauntlet log if so.
- WyldChess speaks both UCI and CECP (README); run it as UCI. No book is
  mentioned in the README.
- Belette exposes `Hash` and a debug log file option (README).

Why not the others (all checked 2026-10-25):
- Smallbrain 1.1 64-bit (Blitz 2114 +/-19): good fallback for Belette's
  slot. C++, GPL-3.0 (API and LICENSE at tag `1.1.0` =
  7e3caf5b6f088b6110b817a4aa14911ad7aed823), README says `make` in `src`;
  README eval is material + PSQT. The makefile itself was not opened, and
  CCRL's "1.1" vs the tag `1.1.0` is a naming match by inference
  (**UNVERIFIED**).
- Berserk 1.2.2 64-bit (2115 +/-26, 489 games): no licence file at tag
  `1.2.2` (root listing), fewer games.
- Shuffle 1.2.1 64-bit (2042): its README says it is not compatible with
  Unix-based systems, and its Makefile builds `shuffle.exe`.
- Language rule (Go, Rust, .NET avoided; language from the GitHub API):
  Maelstrom 2.0.0 (Go), Camel 1.4.0, Trinket 3.0.0, Ratsu 1.1.0 (Rust),
  MinimalChess 0.6 (C#, from the earlier check). Cosette, Pedantic and
  Tcheran (CCRL links to github.com/Tearth/Cosette, JoAnnP38/PedanticRF,
  jgilchrist/chess-engine) were not opened, so their languages are
  **UNVERIFIED**. Rustic (moved to Codeberg) was not reopened.
- Kojiro 0.1.3: GitHub API reports no licence. Horowitz: repo API answers
  "Moved Permanently", not followed.
- Halogen 4 and Zagreus 4.1 (C++, GPL-3.0 / AGPL-3.0 per API): tags exist
  but README and build files were not opened; whether those versions use a
  net is **UNVERIFIED**.
- Napoleon 1.8, Vice, GreKo: unchanged from the list above (licence date,
  qmake makefile, no tags, no repo).
- Chal 1.3.2 (2470) sits on top of Stash 19.0, so 1.3.0 was chosen.

Shared ideas, not shared code: Belette and Chal both cite PeSTO's
published piece-square tables in their READMEs, so their evals start from
the same public numbers; the code bases are separate repos by different
authors.

Not run: none of these was downloaded, built or played; every build line is
from the README or build file at the tag.

### Milestone C anchor set

Verified 2026-10-26. Owner's brief: one anchor (two if a good second exists)
rated about 2650-2800 on CCRL Blitz, to fill the gap between WyldChess 1.51
(2603) and Weiss 1.0 (2896, added as the top anchor). Same rules as the
Milestone B set: a code base unrelated to Stash, Belette, Chal, WyldChess and
Weiss; C or C++ built on Linux with a plain make or cmake command from the
README or a build file; no net at the pinned tag; a licence file at the tag;
UCI. Opponent binaries only: **REFERENCE ONLY** for code (never read for
implementation), **USE** as local test opponents. Only READMEs, licence
files, build files (Makefile, CMakeLists.txt, CI workflow), tag listings and
GitHub API metadata (tags, releases, commit messages, issue and PR titles)
were opened; nothing was downloaded, cloned or built.

Ratings: CCRL Blitz 2'+1" complete list (all versions), "Computed on
October 24, 2026", fetched again 2026-10-26; 40/15 complete list "Computed
on October 23, 2026". Names exactly as CCRL prints them (K2's entry has no
"64-bit" suffix). Repo links come from each engine's CCRL details page. Tags
were resolved with `git ls-remote` (both tags are lightweight: no peeled
`^{}` entry, and the GitHub refs API reports object type `commit`) and each
commit confirmed with the GitHub commits API.

| Name (CCRL string) | CCRL Blitz | 40/15 | Repo | Tag = commit | Licence | Build directory and make arguments | Net |
|---|---|---|---|---|---|---|---|
| Supernova 2.4 64-bit | 2679 +/-10 (3586 games) | 2678 +/-10 (2461) | github.com/MichaeltheCoder7/Supernova (CCRL details link; author Minkai Yang) | `v2.4` = e2de2259c717c7611b5f0db1aaef224257a8d3c6 (commit 2021-09-14, message "Update"; release "Supernova 2.4" the same day, Windows exe only) | MIT (API and `LICENSE` at the tag, copyright 2020-2021 Minkai Yang) | repo root, `make linux` (a Makefile target; the README gives the same gcc line). Binary: `bin/Supernova_2.4_linux`. Plain `make` runs the first target, `windows`, which writes `bin/Supernova_2.4.exe`, so name the target. gcc with `-std=c99 -static -flto -Ofast`, linking pthread and libm; C99, no `-march` | none: the README lists a hand-written eval (PSTs, mobility, trapped pieces, passed-pawn terms, king safety, eval and pawn hash tables). Syzygy probing through a bundled copy of Fathom (the same third-party library Fork, WyldChess and Weiss use; not engine code) |
| K2 0.99 | 2750 +/-10 (3355) | 2714 +/-11 (2107) | github.com/serg-meus/k2 (CCRL details link; author Sergey Meus) | `099` = 028f32f62f0fa914755e9154122546d53a5ade45 (commit 2021-01-01, "Release of engine version 0.99"; release "K2 chess engine v0.99 (updated: fix for Xboard mode)" published 2021-01-01, one asset `k2_099.exe` uploaded 2021-01-03) | GPL. The GitHub API reports GPL-3.0 (today's default branch), but the `LICENSE` file at tag `099` is the GPL **version 2** text: record GPL-2.0 for this pin | repo root, `make` (the Makefile's only target, `all`, is one g++ line over the seven root `.cpp` files with `-DNDEBUG=1 -std=c++0x -O3 -pthread`, no `-march`). Binary: `k2_099` in the repo root. The flags are hard-coded (no `CXX`/`CXXFLAGS` variables), so any extra flag means running that g++ line by hand | none: the README describes a hand-written eval with separate middlegame and endgame terms (material, PSTs, pawn structure, king safety, mobility, rook files and ranks, some endgame cases) |

Spacing with the existing set: 2115, 2173, 2285, 2473, 2603, **2679**,
**2750**, 2896 (the two new gaps are 76 and 71 Elo; the K2-to-Weiss gap
stays 146). Both new anchors have among the smallest error bars in the
range (+/-10) and more than 3,000 Blitz games each. Six unrelated code bases (Stash,
Belette, Chal, WyldChess, Supernova, K2) below Weiss.

K2 release note (release `099`, GitHub releases API): the author asks users
not to build from the tag's source archive, because a build from it plays
without its hash table when installed as an Xboard/WinBoard engine. He
points to commit 9797c31576beb51afae98a56e41ad275ffe56d83 (2021-01-03,
"Fixed 'memory' command for Xboard protocol", the tag commit's direct child,
changing only `main.cpp`) and says UCI use is the same in both. Fork runs
K2 as UCI, so the tag stays the pin; 9797c31 is the author's own alternative
if the gauntlet ever needs it. Which binary CCRL tested (the release exe
uploaded 2021-01-03, or another build) is **UNVERIFIED**.

Toolchain risks (from the README, build files and GitHub metadata only;
nothing compiled):
- K2: 2021 C++ built as `-std=c++0x`. Pull request #10 (merged 2022-08-07)
  reports that a then-current g++ refused to compile an operator declared
  without a return type in `hash.cpp`'s unit-test code, an error the
  compiler marks as `-fpermissive`. `hash.cpp` was refactored after the tag
  (commit 04b699e, 2021-02-21, "Refactoring of transposition table"), so
  whether the `099` source has the same construct is **UNVERIFIED** (it
  would need the source, which Fork does not read). If the build fails that
  way, adding `-fpermissive` to the g++ line is the usual workaround, also
  **UNVERIFIED**. Commit 7449be4 (2021-03-21, "Fixed compile errors on some
  systems") also post-dates the tag. Do not move the pin to a later commit
  to dodge a build error: later commits change the engine that CCRL rated.
- K2's `Makefile` puts a blank line between `all:` and its recipe line.
  Whether GNU make on Ubuntu accepts that layout is **UNVERIFIED** until the
  first build; running the g++ line by hand is the fallback.
- Supernova: `-static` with glibc needs the static libc and libpthread
  archives (Ubuntu's libc6-dev provides them; **UNVERIFIED** until the first
  build). The README says GCC 10 or later is preferable and that builds may
  fail below GCC 5, so Ubuntu 22.04's gcc 11.4 is inside the author's range.
  The README's Linux route builds from the release's source archive; the
  git tag holds the same `src/` and `bin/` layout (the tag listing has
  `bin/Supernova_2.4.exe`, so the output directory exists).

Engine options to set in the gauntlet:
- Supernova (README): `Hash` 1-4096 MB (default 32; set the gauntlet's
  value), `Threads` (default 1; keep 1), `Clear Hash`, `Ponder` (the README
  says it changes nothing; keep pondering off in the runner),
  `SyzygyPath` (set it the same way as for the other anchors, or leave it
  empty for all of them), `SyzygyProbeDepth` (default 1). The README says
  Supernova has no opening book of its own and mentions no online feature.
- K2: run it as UCI (the README says it speaks UCI and Xboard). The README
  names no UCI options, so whether it offers `Hash`, or has a book to
  disable, is **UNVERIFIED**: read its `uci` reply on the first run, set
  `Hash` to the gauntlet value if offered, disable any book option, and
  record what it lists. No online feature is mentioned.
- Record each built binary's SHA-256 per run, as for the other anchors.

Why not the others (checked 2026-10-26). Screened: every entry the Blitz
complete list marks as open source from 2680 to 2806, plus some from 2650
to 2680; languages and licences come from the GitHub repository API.
- Same code base as an existing anchor: Belette 3.0.0 (2806), Chal 1.4.1
  (2755), Stash 21.0 (2713), Weiss 0.8, 0.9 and 0.10 (2608, 2650, 2847).
- Language rule: Go: Tofiks 1.6.0, Zahak 5.0, Donna 4.1, Mess 0.3.0. Rust:
  Odonata 0.6.2-0.8.0, Simbelmyne 1.5.1/1.6.0, Inanis 1.0.1/1.1.0, Velvet
  1.2.0, Princhess 0.12.0, Trinket 3.5.0, Ratsu 2.0.0, Javelin 3.0.0,
  Fatalii 0.10.0, Dual 0.3.2, Tcheran 5.0 (repo now tcheran-chess/tcheran),
  Reyna 1.0. C#: Boychesser 1.0, Pedantic 0.3, Leorik 2.2, Puffin 3.0. Java:
  Eubos 4.4, Jacky Chess 23.12-24.06, Scoria 4.4.7. D: Dumb 1.9/2.0. Nim:
  Nalwald 1.11, Annie 1.2 (also no licence). Zig: Lambergar 0.4.1. Pascal:
  Yakka 1.1. MadChess 3.2/3.3 links only to madchess.net (not opened;
  language **UNVERIFIED**); akimbo 0.4.0 has no link on CCRL.
- Net at the tag: Eleanor 1.0 (`nnue.bin` in the tag root), Arcanum 2.1
  (`arcanum-net-v2.fnnue`), Prelude 1.0 (`nnue.bin`), PZChessBot 1.0
  (`nnue.bin`), Casanchess 0.9 (README at the tag describes an NNUE eval
  loaded from a net file), Prune 1.0.1 (2670; an NNUE source file and
  `model.bin` at the tag). Qapla 0.2.057 (2768, C++, AGPL-3.0) has an
  `nnue768/` directory at the tag; its README was not opened, so its eval
  type is **UNVERIFIED** and it was not chosen.
- No licence (API reports none): Facon 1.6 Temple, Turbulence 0.0.4, Admete
  1.6.0, Revolver 1.0, Apotheosis 4.0.1 (CCRL's link now resolves to
  spamdrew128/Apotheosis), Cepimetheus 16.0.0, Rengar 1.3.0. Midnight 5
  (2791): no licence file in the `v5` tag listing (the API reports MIT
  for the repository today).
- Nothing to pin on GitHub (CCRL's link not followed further): GreKo
  2020.01-2021.12 (greko.su), CT800 1.45/1.46 (ct800.net), Octochess r5506
  (octochess.org), Fridolin 4.00 (Google Sites), Pawny 1.2 (own site),
  Bison 9.11 (sdchess.ru), Coiled 1.1/1.2 (author's site), RuyDos and
  Vengeance (Bitbucket), RedQueen 1.1.4 (SourceForge). Zevra 2.6, Prophet
  5.1/5.2 and Nawito 22.07 have no link on CCRL. Keele 1.0 (2648): the
  linked repo returns 404.
- Build or protocol problems: Renegade 0.11.0 (only a Visual Studio
  solution at the tag root), Amira 1.82 (no build file at the tag; the
  README gives only a g++ line), Solo 1.6.0 (README asks for C++23, a risk
  with Ubuntu 22.04's gcc 11), Drosophila 1.6 (2653; CECP interface only at
  the tag, ships `data/book.bin`), Clovis 2.0 (the tag is named `II`; its
  Makefile builds with `-Werror`), Lux 4.2 (no build file in the tag root;
  not checked further). Cwtch 1 (2700): CCRL's link now resolves to a
  different owner's repo (Bastiball21/cwtch); not followed up.
- Usable but not chosen (fallbacks, in order):
  - Polaris 1.5.0 64-bit (Blitz 2715 +/-18, 986 games; 40/15 2677
    +/-21): C++20 by Ciekce, GPL-3.0 (API and `LICENSE` at the tag), `v1.5.0`
    = f4e661ffd3d10ead50781e65f0d4388c58723629 (commit 2023-04-17, "1.5.0").
    README: Texel-tuned hand-written eval, CMake build
    (`cmake -DCMAKE_BUILD_TYPE=Release -S . -B build/`, then
    `cmake --build build/ --target polaris-<native|bmi2|modern|popcnt|compat>`),
    tested with GCC 11 on Linux, `Hash` option (default 64), and no book
    option in its options table. Not chosen because it sits 35 Elo below K2. The binary's path
    inside `build/` is **UNVERIFIED**. First choice if K2 will not build.
  - Lishex 1.1.1 64-bit (Blitz 2688 +/-12, 2100 games; 40/15 2668 +/-11):
    C++20, GPL-3.0 (API, `LICENSE.md` at the tag), `v1.1.1` =
    ad54b19952fa33025b61233068d3a44b992099cd (commit 2023-08-08). The README
    says `make`, but the Makefile writes objects into `build/` without
    creating it; the tag's CI workflow runs `mkdir build` first and then
    `make lishex CXX=g++-12` on ubuntu-22.04. The flags hard-code
    `-mbmi2 -mpopcnt`. The `src/` listing has a book source file and the
    README says nothing about a book option (**UNVERIFIED**). Supernova
    sits at almost the same level with more games and a README that rules
    out a book.
  - Peacekeeper 1.50 64-bit (Blitz 2789 +/-17, 949 games): C++17, GPL-3.0,
    `v1.50` = 0dbc7ddf8857e9fd9923984dcb7f1713c022d477 (from ls-remote and
    the refs API). The README describes a Texel-tuned PST eval, but
    `src/eval.h` at the tag is 200,385 bytes, far more than PST tables need,
    so a hand-written-only eval cannot be confirmed without the source
    (**UNVERIFIED**). It would also sit only 39 Elo above K2.
  - Not opened beyond the API (README and tag tree unchecked, so
    **UNVERIFIED**): Bit-Genie 7 (2712; its README at the tag does not
    describe the eval), 4ku 2.0 (2723; README does not describe the eval),
    Illumina 1.0 (2740; git submodules), Aramis 1.4.0 (2758), Seawall
    20230316 (2756), Bread 1.4.0 (2803).

Not run: none of these was downloaded, built or played; every build line is
from the README or build file at the tag.

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
