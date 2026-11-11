# Clean-room engine survey, November 2026

Written 2026-11-10 for the owner's brief of the same day. Branch
`research/engine-survey-2026-11`, from `origin/phase-4` at 95f49c7.
For the owner's review; not merged.

## What this is

A survey of the 50 engines at the top of the CCRL Blitz list: what each one
publishes about its search, its network, its training data and labels, its
training recipe, and the Elo it measured per feature. It is compared with
Fork's own status for each technique. It builds on the Phase 4 think tank's
three surveys and does not repeat them:
- S1, the Stockfish lineage (`docs/research/phase4-think-tank/phase-b-specialists.md`, B1);
- S2, the open-source NNUE engines, with the Stormphrax supplement (B2);
- S3, TCEC conditions and the closed engines (B3);
- the synthesis's ranked list R1 to R41 (`phase-c-synthesis.md`).

Where a technique is already in S1 to S3 or the R list, this survey cites that
entry and adds only what is new: more engines, newer numbers, LTC results and
counter-evidence.

| File | Contents |
|---|---|
| [engines.md](engines.md) | One condensed record per engine, with sources |
| [comparison.md](comparison.md) | The table: technique, engines, reported gains, Fork's status |
| [ranking.md](ranking.md) | Never-tried techniques ranked by evidence × fit, shared-idea flags, test proposals with the decision each could change and its cost |
| [provenance.md](provenance.md) | Each engine's training data, classified, and Fork's positioning |
| [precedents.md](precedents.md) | AI-assisted precedents for a Category 4 entry |
| [sources.md](sources.md) | Every source, with the date opened, failed fetches included |

## Method

- **Clean room.** Six survey agents read public prose only: READMEs, release
  notes, PR and issue text, commit messages, project documents written as
  prose (network logs, changelogs), CPW, TCEC questionnaires, TalkChess,
  OpenBench pages, vendor pages and papers. They read it through the GitHub
  and GitLab APIs or plain fetches. No engine was cloned. No source file,
  diff or code view was opened. Code fragments found inside prose were
  skipped. No search constant, margin or threshold was recorded. Every page
  was opened on 2026-11-10 (sources.md).
- **This write-up** opened no web pages. It condenses the six reports and
  reads Fork's own repository at `origin/phase-4`:
  - `docs/DESIGN.md` (Search constants, the decisions log, §5.6);
  - both SPRT logs;
  - `docs/ideas.md`, ideas 1 to 71;
  - `docs/nets.md`;
  - the feature switches in `src/search/searcher.hpp`, and a few lines of
    Fork's own TT, search and data-generation code to confirm what exists.
- **Numbers.** Every Elo figure is the engine's own self-reported result
  (SPRT point estimates, release regressions, fixed-node or fixed-game
  matches) under its own conditions. SPRT stopping inflates passing
  estimates. They are priors for Fork, not predictions. Fork's numbers come
  from Fork's SPRT log, at 8+0.08 (STC) or 40+0.4 (LTC), one thread.
- **Tags.** Every engine and idea here is REFERENCE ONLY. Every engine's
  code, nets and data are OFF-LIMITS. Whatever could not be confirmed is
  marked UNVERIFIED with its reason.

## The CCRL list and its date

- **List:** CCRL Blitz rating list, all engines, best versions only (2'+1"
  equivalent on an i7-4770K, ponder off, a general book up to 12 moves,
  6-piece tablebases).
- **Date:** "Computed on November 7, 2026 with Bayeselo based on 2,181,233
  games". Fetched 2026-11-10 at https://computerchess.org.uk/404/ (the
  home page's /ccrl/404/ redirects there).
- CCRL's home page says it does not judge engine originality.

| Rank | Engine | Version | Elo (±) | Class |
|---|---|---|---|---|
| 1 | Stockfish | 19 8CPU | 3803 (22) | open source |
| 2 | Triumviratus | 8.0 | 3784 (13) | open source; CCRL note: developed with significant AI help |
| 3 | Torch | v4 8CPU | 3778 (14) | private |
| 4 | Obsidian | 16.0 8CPU | 3774 (12) | open source |
| 5 | PlentyChess | 8.0.0 | 3773 (12) | open source |
| 6 | Coda | 0.9.4 | 3769 (13) | open source; CCRL note: written by Claude Code under human direction |
| 7 | Reckless | 0.9.0 | 3765 (10) | open source |
| 8 | Gaia | 4.4.1 | 3762 (15) | open source |
| 9 | Cinder | 0.6.1 | 3760 (12) | open source |
| 10 | Berserk | 20250606 8CPU | 3759 (14) | open source |
| 11 | Dragon by Komodo | 3.3 8CPU | 3756 (9) | commercial |
| 12-13 | Alexandria | 8.0.0 8CPU | 3755 (10) | open source |
| 12-13 | pawnocchio | 2.0 | 3755 (11) | open source |
| 14 | Integral | 8 | 3751 (11) | open source |
| 15 | Caissa | 2.0 | 3748 (12) | open source |
| 16 | Viridithas | 20.0.0 | 3747 (11) | open source |
| 17 | Stormphrax | 8.0.0 | 3744 (11) | open source |
| 18 | Hobbes | 3.0 | 3743 (11) | open source |
| 19 | Horsie | 1.1.0 8CPU | 3735 (12) | open source (a port of Lizard) |
| 20 | Lizard | 11.2 8CPU | 3732 (9) | open source |
| 21-22 | Astra | 7.0 | 3730 (10) | open source |
| 21-22 | Raphael | 4.2.0 | 3730 (12) | open source |
| 23-25 | RubiChess | 20240817 8CPU | 3727 (9) | open source |
| 23-25 | Starzix | 6.0 8CPU | 3727 (9) | open source |
| 23-25 | Tarnished | 6.0 | 3727 (24) | open source |
| 26 | Clover | 9.1 | 3726 (8) | open source |
| 27 | Ethereal | 14.25 8CPU | 3722 (8) | commercial (links a GitHub repo) |
| 28 | Fritz | 20 8CPU | 3721 (12) | commercial (Ginkgo versions) |
| 29 | Halogen | 16.0.0 | 3720 (8) | open source |
| 30 | Quanticade | Cronus 3.0 | 3716 (10) | open source |
| 31 | Igel | 3.8.0 | 3712 (18) | open source |
| 32 | PZChessBot | 7.1 | 3711 (11) | open source |
| 33 | ZigQueen | 6.5.0 | 3709 (15) | open source; CCRL note: Claude wrote most of the code under continuous human direction |
| 34 | Devre | 7.0 | 3704 (12) | open source |
| 35 | JustBot | 0.5.0 | 3703 (13) | open source |
| 36-38 | Minke | 7.0.0 | 3702 (14) | open source |
| 36-38 | Titan | 1.1.0 8CPU | 3702 (9) | open source |
| 36-38 | Velvet | 8.1.0 8CPU | 3702 (10) | open source |
| 39 | Ginkgo | Santiago 1.0 8CPU | 3699 (9) | private |
| 40-41 | Revenge | 4.0 8CPU | 3698 (10) | free, closed |
| 40-41 | Tcheran | 14.0 | 3698 (14) | open source |
| 42 | Uralochka | 3.41a 8CPU | 3697 (9) | open source |
| 43-44 | Lc0 | 0.29.0 w753723 RTX2080 | 3696 (10) | open source |
| 43-44 | Seer | 2.8.0 8CPU | 3696 (9) | open source |
| 45-48 | Chess System Tal | 3.00 | 3694 (12) | free, closed |
| 45-48 | Motor | 0.9.0 | 3694 (9) | open source |
| 45-48 | Renegade | 1.3.0 | 3694 (11) | open source |
| 45-48 | Stoofvlees II | b5 RTX2080 | 3694 (12) | private (GPU) |
| 49 | Rebel | 17.0 | 3689 (16) | free, closed |
| 50 | rofChade | 3.1 8CPU | 3687 (8) | free, closed |

Counts: 40 open source, 3 commercial, 4 free closed, 3 private. CCRL's
notes mark three engines as AI-assisted: Triumviratus (#2), Coda (#6) and
ZigQueen (#33).

**Rank discrepancies (recorded, not resolved).** Two survey agents read the
single-CPU view of the same list ("games added on November 7, 2026"), so
their ranks differ from the table above. This table is the reference.
- Single-CPU view (family 2): Stockfish 19 at 3792; Torch v4d at 3774 (#3);
  **Obsidian 16.0 #14 at 3746**, not #4 (its 3774 above is the 8-CPU entry);
  PlentyChess to Cinder at #4 to #8. The engine-detail pages show yet other
  "#" numbers (Coda #6, Gaia #8, Cinder #9, PlentyChess #5, Reckless #7).
- Single-CPU view (family 3): pawnocchio #9 (3755); **Alexandria 9.1.0** (not
  8.0.0) and Integral 8 both at 3751; Caissa #12, Viridithas #13,
  Stormphrax #15, Hobbes #16; **Berserk 14** #17 (3737). "Berserk 20250606"
  exists only as an 8-CPU entry.
- S2 (2026-11-07) also used the single-CPU view: Ethereal 14.25 at 3683
  there against 3722 for the 8-CPU entry here.
- Family 4 did not reopen the list and used the ranks it was given.

All Fork tests are one thread, so the single-CPU view is the fairer
yardstick for strength comparisons. The all-engines view is the reference
for which engine and version this survey describes.

## Key findings

1. **Fork's think-tank picks were confirmed and have paid.** Each of
   Fork's Phase 4 search adoptions has peers among the 50 reporting the same
   idea, and Fork's own gains fall within or above the range others report:
   IIR (+21.45
   STC, +26.25 LTC), singular extension (+14.12 STC, LTC on/off +25.83),
   node-share and stability time management (+18.69 STC, +10.23 LTC), and
   the early SPSA (+37.93 STC, +29.93 LTC). Peers report +10 to +30 for
   their first NNUE-era tunes and +8 to +22 at LTC for node-fraction time
   management.
2. **The strongest shared training result is a result-weighted final
   stage.** Ten engines report a gain from it. The largest figure is Ethereal's
   pure-result fine-tune of its best net (+42.7 STC, +35.6 LTC). Others:
   Berserk +11.7 LTC, Raphael +18.3, Hobbes +8.9 LTC, Minke +8.1 LTC and
   Halogen +6.9 LTC. Counter-evidence: Viridithas lost 57 Elo doing it on
   recent data only, and some gains are LTC-only (Halogen 0 at STC,
   pawnocchio H0 at STC). Already queued as idea 70; the survey proposes a
   cheap second arm on the newest data only (ranking.md §4, J9).
3. **Several cheap search and ordering ideas, each reported by three to six
   independent engines, were never tried by Fork** (ranking.md, top ten):
   - summed continuation scores as the history update base;
   - a bonus for the prior move when a child fails low;
   - pruning relief for checking quiet moves beyond LMR (two engines
     report about +9 at LTC);
   - an early eval-only TT write (six engines);
   - TT cutoffs gated by node type;
   - material-based eval scaling;
   - opponent-worsening RFP;
   - history-scaled pruning margins;
   - a direct-check ordering bonus.
   On the training side: activation and feature-transformer regularisation,
   a natural partner for idea 71.
4. **Consensus ideas Fork tried and lost** (comparison.md, flagged):
   - threat-indexed quiet history (15 or more engines report gains; Fork
     −6.08);
   - king input buckets and a multi-layer head (near-universal; Fork's H-512
     and AF-S lost on speed);
   - threat inputs (near-universal in the top 30; Fork's XGR-512 and
     S512+X lost on speed);
   - ProbCut (ten engines; Fork −5.29, no retest);
   - the improving flag in RFP and the LMR history term.

   The peers' record shows that most of these needed either a larger data
   volume (buckets grown with data) or the speed work done first (threat
   inputs made incremental, lazy and int8). It does not show that Fork's
   form was wrong. ranking.md recommends no blind retests and lists the
   owner's choices.
5. **Data provenance (provenance.md):**
   - of the top 10, only PlentyChess (#5) is confirmed own-self-play;
   - five of the top 10 train on Lc0 data (Stockfish, Triumviratus,
     Obsidian, Coda, Cinder), Torch is mixed, and Berserk mixes in another
     engine's data;
   - Reckless and Gaia are unknown;
   - over all 50: 23 own self-play (5 of them with a caveat), 11 Lc0 or
     Lc0-relabelled, 8 mixed (another engine's data, games against other
     engines, or an Lc0-seeded lineage), and 8 unknown.

   Own-data engines span #5 to #45-48. Fork's data route has precedent
   at the top (PlentyChess at 3773). The owner's 2026-11-10 rule classes
   Ethereal's, Dragon's and Uralochka's use of games against other engines
   as not Fork-pure.
6. **Category 4 precedents (precedents.md):**
   - Coda is the warning case. Its code was written by Claude Code, and
     clean-room failures (one agent reading AGPL code and then writing,
     foreign constants as seeds) brought a public dispute.
   - Triumviratus is not clean: it carried Stockfish code up to the rated
     8.0.
   - ZigQueen shows a disclosure model (ORIGINALITY and PROVENANCE files,
     an inherited-constant exception disclosed).
   - Incipit, by Coda's author, forbids its agents from reading any other
     engine's code, commits or docs, and trains only on its own data. It
     is the closest match to Fork's rules.
   - A public "engine forensics" page labels repositories as AI-generated
     from commit shape and tooling files. Fork's public repository would be
     labelled AI-generated; that matches its declared category.
7. **Status counts** (comparison.md, 135 technique rows):
   - 35 have (J20, td90, moved from queued on 2026-11-10);
   - 13 tried, failed;
   - 37 in progress or queued (33 queued, 4 in progress; Phase 6 items
     included);
   - 1 parked;
   - 44 never tried (5 of them blocked by a missing prerequisite or Phase 6
     scope, and one dropped untested by the owner);
   - 5 excluded by an owner rule or out of scope.

   49 rows are shared ideas (four or more engines with measured gains).
   Of those, Fork:
   - has 7;
   - failed 10;
   - has 17 in progress or queued;
   - parked 1;
   - never tried 13;
   - excluded 1.

## Owner corrections and follow-ups (2026-11-10)

Recorded only; planning waits until the queue clears.
1. **Corrections.** J20: td90 is TD(0.9) labels, retrain 8b's arm; it
   passed STC (+12.17 ± 5.71) and is the default net. J10: 8b had no
   old-data down-weighting arm. J3: idea 70 is prepared and approved (it
   started on Kaggle at 6:50 PM EST from td90).
2. **T56 against the common peer form (D5).** Fork's T56 is the common
   form: the quiet (butterfly) history split into four buckets by whether
   an enemy piece attacks the move's from-square and its to-square, read
   and updated in the bucket of the position before the move
   (`threat_bucket`, commits 2f6f4ac and 541ea70). Two sets of "attacked"
   were declared (tools/tier2_measure/threat_set.json): **any enemy
   attack**, the peers' form, and **an attack by a cheaper piece**. In the
   declared measurement both lost to "off" (any attack −0.0208, cheaper
   −0.0162); the cheaper set, the better of the two, was SPRTed and lost
   (−6.08 ± 3.59). So the common form is not a new idea: it is T56's first
   set, measured and beaten but never played in an SPRT. Differences from
   some peers, UNVERIFIED per engine: Fork split only the butterfly table
   (no continuation or capture history), and the measurement ran on
   S512r2. T56 stays closed for this network; a later net may re-test it
   only as a new idea (the existing rule).
3. **B13, quiet history pruning:** untested in a firing form (the dropped
   history-skip variant changed only 30 bench nodes); eligible for a test
   with a threshold that actually fires.
4. **H3, king buckets:** a bake-off round 3 candidate, since Fork's data
   has roughly tripled since H-512.
5. **R34, non-pawn correction tables:** a gateway item; its table
   unblocks C15 (correction size in pruning) and E5 (correction update
   rules).

## Items already queued from the survey (owner, 2026-11-10)

- **ideas.md 70**, the result fine-tune of the base net: queued right
  after retrain 8b's SPRT decides the base net. It fine-tunes the winner
  (td90 or the control) on existing 8b data with a 100% game-result target
  at a low learning rate, two seeds, then the usual gates, a fixed-node
  screen and an SPRT. Kaggle hours are reported before launch.
- **ideas.md 71**, feature-transformer weight decay: a candidate arm for
  retrain 8c (Stockfish's recent trainer change, +4.0 STC / +5.3 LTC there).
- **Training-data decision 1 amended:** games against other engines are not
  Fork-pure data (DESIGN.md, phase-4 95f49c7).

## Open questions for the owner

Each question has its reasoning in [ranking.md §5](ranking.md#5-open-questions-for-the-owner).

1. **Which never-tried proposals join §5.6 step 12?** Recommended:
   - D8, D9 and D13 after R15;
   - B12 after R7;
   - F3 and F4 beside R13 and R6;
   - B10 after R17;
   - B11 only after R20.
2. **Idea 70's shape.** Recommended: add a newest-data arm beside the
   whole-data arm if quota allows; never the newest-data arm alone.
3. **A regularisation arm (J6) in 8c beside idea 71.** Recommended: yes,
   as its own arm.
4. **Retests of shared ideas Fork lost.** Recommended:
   - no blind retests;
   - king buckets and a multi-layer head only as new designs after QAT or
     int8 work;
   - a ruling on whether threat-aware capture history (D6) is new.
5. **Material scaling (F10).** Recommended: R33's first variant; report the
   labeller consequence before adoption.
6. **Int8 feature-transformer rows (I4).** Recommended: price them with
   X12 first; then speed sprint 3.
7. **A disclosure section in README.md** (the ZigQueen model).
   Recommended: yes; keep the AI tooling public.
8. **The forensics page.** Recommended: no action beyond (7).
9. **Credit authors as well as engines** in ORIGINALITY.md. Recommended:
   yes (this survey's rows do).
10. **CCRL view for future surveys.** Recommended: the all-engines list as
    the reference, with the single-CPU view beside it.
11. **TCEC's view of AI-assisted entries.** Recommended: ask in Fork's
    questionnaire (UNVERIFIED today).

## UNVERIFIED items

The main ones are listed in each file. The ones that most affect a
decision:
- the TCEC view of Coda and Triumviratus (no TCEC page was opened on
  this);
- Torch's data and techniques (all second-hand);
- Reckless's and Gaia's data after their early nets;
- whether Integral's rated v8 net predates its Vine data;
- whether pawnocchio's "chonker" relabels by static output or by search;
- a few Fork code facts not checked here (pins in SEE, lazy accumulator
  updates, the NMP gate conditions).
