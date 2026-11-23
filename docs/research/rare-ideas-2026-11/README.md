# Clean-room "rare ideas" survey, November 2026

Written 2026-11-15 for the owner's order of the same morning. Branch `research/rare-ideas-2026-11`, from
`origin/phase-4` at 31701e3. For the owner's review; not merged.

## Flags for the owner

1. **Sources beyond the owner's list.** The order named READMEs, release notes, wikis, papers, blog posts, forums
   and OpenBench or fishtest summaries. The groups also read **GitHub pull-request titles and descriptions and
   commit messages** (prose, through the GitHub API), and that text carries most of the measured results here.
   Fenced code blocks were stripped by script before reading. Groups 1, 2 and 3 each state that they kept the
   result-only lines inside fenced blocks (Elo, SPRT or LLR, Games, Penta or Ptnml, and test links); group 4 does
   not describe a fence filter, but states it requested no diffs or file lists and recorded no parameter values.
   (The coordinator's note named groups 1 and 3; group 2's own clean-room statement says the same of itself.)
   **rare.md's index has a "Sources" column: "PR/commit only" marks every entry that rests only on that text,**
   so the owner can exclude them. Of the 45 rare entries, 34 rest on PR/commit text only; the other 11 also have
   a README, release note, project document, TCEC questionnaire or GitHub issue thread behind them (RI-01, RI-08,
   RI-16, RI-17, RI-29, RI-32, RI-33, RI-40, RI-41, RI-42, RI-43), and three of those rest on no PR/commit text at
   all (RI-16, RI-42, RI-43). An issue thread (Stockfish #6742) is GitHub discussion, closer to a forum than to a
   PR, but it is not on the owner's list either.
2. **Merged after the rated release.** Several entries come from changes merged after the CCRL-rated version
   (flagged by the groups): Seer's hidden-state correction key (after 2.8.0), JustBot's continuation split, child
   fail-high count and eval-difference update (after 0.5.0), Igel's "static history" (after 3.8.0), Berserk's
   continuous LMR history (2026-11-08), Titan's items after 1.1.0, RubiChess's SMP fixes, Hobbes 4.0's notes; and
   Ethereal's 2019-2022 commits may not all survive in 14.25 (a 2022 commit standardised its LMR). rare.md's index
   has an "After release" column; most entries were not checked.
3. **Process note.** During the survey, group 1 deleted shared scratchpad folders, including group 3's scripts;
   group 3 re-did the affected reading, and no source of the survey was lost.

## What this is

Across the top ~50 CCRL engines, plus notable newcomers and AI-assisted engines, the techniques used by only one
to three engines that report a measured gain, with Fork's status, fit and the cheapest test for each, ranked by
evidence x fit / cost. It builds on, and does not repeat, docs/research/engine-survey-2026-11/ (the 135-row
comparison table) and docs/research/network-survey-2026-11/; techniques already there, or in the think tank's
R1-R41, appear only in evidence.md when the evidence is new.

The owner's order (verbatim, from the common brief): "Clean-room 'rare ideas' survey (kb-researcher agents; public
sources only: READMEs, release notes, wikis, papers, blog posts, forum and OpenBench/fishtest summaries; never
engine source code; concepts only; credit every source in ORIGINALITY.md). Builds on, and must not repeat,
docs/research/engine-survey-2026-11/ (135 techniques) and docs/research/network-survey-2026-11/. Goal: across the
top ~50 CCRL engines (plus notable newcomers and AI-assisted engines), find techniques used by ONLY ONE TO THREE
engines that report a measured gain: unusual search heuristics, time management, evaluation or network tricks,
training or data-generation methods, SMP techniques, and testing/tuning practices. For each: what it does (plain
language), which engine(s), the reported gain with its conditions (TC, games, error bars) and evidence quality
(SPRT vs anecdote), why it may not have spread (cost, niche, untested elsewhere, unknown), Fork's status (have /
tried / never tried), its fit with Fork's evidence (king-region net, the cost lesson, the calibrated residual
line, Lazy SMP next, TCEC long TC), and the cheapest test. Rank by evidence x fit / cost, and flag any that look
like undervalued gems. Write to docs/research/rare-ideas-2026-11/ on a branch; stop for my review. Web reading
only; no builds, jobs or GitHub runs."

| File | Contents |
|---|---|
| [rare.md](rare.md) | The 45 rare techniques (RI-01 to RI-45), merged across groups, each with every field the order asks for; then the results found but not ranked, and the rare ideas with no published figure |
| [ranking.md](ranking.md) | All 45 ranked by evidence x fit / cost, the scoring stated, the gems and why each is undervalued |
| [common.md](common.md) | Techniques used by four or more engines that comparison.md lacks (CG-1 to CG-11), scored on the same scale |
| [evidence.md](evidence.md) | New evidence on known rows (comparison.md, matrix.md, R1-R41), tied to Fork's own results |
| [smp.md](smp.md) | Everything found on Lazy SMP practice, cross-referenced to the KB entry docs/kb/lazy-smp.md (branch kb) |
| [sources.md](sources.md) | Every source, with the date opened, failed fetches included |

## Method

- **Four survey agents** (kb-researcher), one per slice of the CCRL Blitz list fetched on 2026-11-15 ("computed on
  November 14, 2026"): group 1 ranks 1-13 (Stockfish, Triumviratus, Torch, Obsidian, PlentyChess, Coda, Reckless,
  Gaia, Cinder, Berserk, Dragon, Alexandria, pawnocchio); group 2 ranks 14-26 (Integral, Caissa, Viridithas,
  Stormphrax, Hobbes, Horsie, Lizard, Astra, Raphael, RubiChess, Starzix, Tarnished, Clover); group 3 ranks 27-41
  (Ethereal, Fritz, Halogen, Quanticade, Igel, PZChessBot, ZigQueen, Devre, JustBot, Minke, Titan, Velvet, Ginkgo,
  Revenge, Tcheran); group 4 ranks 42-50 (Uralochka, Lc0, Seer, Chess System Tal, Rebel, Motor, Renegade,
  Stoofvlees, rofChade) plus newcomers and AI-assisted engines (Incipit, Icarus, Prune, Potential, SSSimpler, Bread,
  Clockwork, Jackal, Soul, CatGPT, DeepFin and others). The slices follow the 2026-11-10 survey's list of November
  7; Incipit entered since at #23.
- **Dates.** Every page was opened on 2026-11-15. The groups read Fork at origin/phase-4 69e1080; this synthesis
  checked the conflicts below against 31701e3 (docs only changed between them).
- **Public prose only.** PR and commit text through the GitHub API, release notes, READMEs and other prose documents,
  TCEC questionnaires, CPW, TalkChess, the Lc0 blog, CCRL pages and a few OpenBench test pages (sources.md).
- **One synthesis agent** merged the four section files into this folder. It opened no web page and no engine source;
  it read only the four sections, their common brief, Fork's own documents, and the KB entry on branch kb.

### The clean-room boundary as practised

- No engine was cloned or downloaded; no source file, header, build script, trainer configuration, diff, "files
  changed" view or blame was opened by any group.
- Prose was fetched through the GitHub API and plain fetches into each agent's own temporary folder, outside every
  repository, and deleted before hand-back. Fenced blocks were removed by script before reading, except the result
  lines noted in flag 1; group 2 also replaced inline code spans with a placeholder.
- **Near-misses, all reported by the groups, none recorded:** some PR bodies, commit messages and project documents
  name parameters or values in prose (Berserk #611, Coda #4, Triumviratus's appendix, Stormphrax #264, Incipit and
  Potential commits, Seer squash messages, the Lc0 blog); the Uralochka questionnaire has a short code illustration
  (skipped); Bread's README has a SIMD listing and quantisation values (reading stopped); the TCEC Swiss 10 page
  prints Lc0's time-manager values (not recorded); the Stoofvlees article was not opened (paywall and a notice
  against AI use on an abstract page).
- **Fork's own code** was read (read-only) by groups 2, 3 and 4 to set Fork's status: the switch list and RFP,
  aspiration, NMP and LMR code in src/search, the TT depth rule, the move selector, and the self-play loop.
- **Constants.** No other engine's constant, margin, threshold, table value or code identifier is recorded. The
  synthesis dropped the few numbers in the section files that could be read as another engine's settings (below).
  Fork's own identifiers (switch names) appear where they set Fork's status. Every Elo figure is the engine's own
  report under its own conditions.
- Engines that say they checked novelty by reading other engines' source (Triumviratus) are not relied on for that.

### How rarity was counted

- An engine counts toward an entry when its prose describes the same mechanism, from a description or from a title
  that names the mechanism unambiguously. Engines linked only by an ambiguous title, or whose mechanism the prose
  does not state, are listed as "possible" and not counted.
- Counts combine all four groups (the same idea found by two groups is one entry) and the 2026-11-10 survey's
  tables. **Four or more counted engines moves an entry to common.md.** An entry at three or fewer that would pass
  three with its possible engines is marked **borderline** in rare.md (RI-02, RI-17, RI-20, RI-35).
- A count is of engines read in this survey, not a census: an engine outside a group's slice may use an idea
  unseen (UNVERIFIED for every count).

### Scoring

Score = evidence (1-5) x fit (1-5) / cost (1-3), defined in ranking.md, with two stated discounts (a much weaker
engine's results count one level lower; intervals across zero do not count as passes). The groups' own scores were
re-done on this one scale after the merges.

## Results in brief

- **Rare entries: 45** (rare.md), after merging the groups' candidates and moving the threat-gated RFP to
  common.md.
  Top of the ranking: root LMR keyed to the aspiration state (RI-12); Lazy SMP hygiene (RI-34, already in the KB's
  suggested v1); depth-relaxed TT cutoffs (RI-27); the history bonus scaled by moves searched (RI-02); the
  correction update toward the mean of raw and corrected eval (RI-31); extra reduction for king-move evasions
  (RI-13); staying out of quiescence with a TT move (RI-20); thread diversity (RI-35); elementary-mate suites
  (RI-41); the bonus scaled by the margin over beta (RI-05).
- **Gems: 9** (ranking.md): RI-12, RI-34, RI-27, RI-20, RI-35, RI-41, RI-01, RI-39, RI-42.
- **Common gaps: 10 techniques Fork lacks or tried only in another form, plus one Fork has** (common.md). The top
  three: the eval-difference history update (CG-1; groups 1, 2 and 3 found it independently), the threat-gated RFP (CG-2) and
  LMR extensions (CG-3).
- **New evidence: about 50 rows** (evidence.md), including LTC-led peer results for F10 (dropped; record only), two
  more peer results and a false-positive warning for F7 (upcoming repetition), thread-growing gains for F3, and
  nets that lose at STC but win at long TC (and the reverse) for L1-L3.

## Reconciliations (conflicts between the groups, or with Fork's records)

1. **T56.** Group 1 wrote that Fork's threat buckets failed. The SPRT log shows the cheaper-attacker set lost
   (-6.08, 2026-11-06), but the any-attack threat-aware quiet ordering was **adopted** on 2026-11-11 (STC +7.49 ±
   4.89, LTC +8.07 ± 5.15). rare.md RI-01 uses the log.
2. **Aspiration fail-high depth reduction.** Group 2 reported it absent (reading the aspiration loop); group 3 found
   audit-1 B-3 (the root fail high re-searched one ply shallower), which reached its cap undecided (+0.65 ± 3.56) and
   was reverted (DESIGN.md decisions log, 2026-10-28; ideas.md 29). common.md CG-6 records it as tried.
3. **Window-aware LMR.** Group 1 called idea 61 part 5 "a cousin" of the loose-window LMR; the SPRT log credits the
   same Stockfish commit (5f7348f0) at concept level for it (futility stop, -2.93 ± 7.16, retired). rare.md RI-15.
4. **Net output scale.** Group 2 asked whether Fork rescales each net's output for the search (UNVERIFIED); group 3
   noted Fork matches each promoted net's S to the previous default's mean |eval|. docs/nets.md confirms the
   matching for every promoted net, so the rescale group 2 asked about is in place (evidence.md).
5. **Quiescence TT depth.** Group 1 left Fork's stored qsearch depth UNVERIFIED; group 2 read trans_table.hpp
   (depths below 0 stored as 0). Recorded from group 2's reading; the synthesis did not read the code.
6. **Threat-gated RFP.** Group 2 counted three engines and made it its top gem; group 3 found Halogen's
   threat-raised margin separately. Merged, it counts four and moved to common.md (CG-2).
7. **Staying out of quiescence with a TT move.** Group 1 (Reckless, PlentyChess, Stockfish) and group 3 (PZChessBot)
   found it separately; PZChessBot's meaning rests on a title and a branch name, so the merged entry counts three
   and is borderline (RI-20).
8. **Factorised LMR.** Groups 1 (Cinder) and 2 (Tarnished, Hobbes; Viridithas's "FLKR" possible) merged: three,
   borderline (RI-17).
9. **Null-move refutation bonus.** Groups 2 (Viridithas) and 4 (Potential) merged (RI-06).
10. **Fifty-move TT guard.** Groups 1 (Stockfish, Cinder) and 2 (Stormphrax) merged (RI-26).
11. **Thread diversity.** Groups 1 (Stockfish, Reckless) and 4 (Potential's helper bias) merged; Clover's title is
    possible (RI-35).
12. **Bayesian optimisation.** Groups 1 (Reckless) and 3 (Ethereal) merged (RI-45).
13. **Pawn-structure refutation move.** Group 4's Renegade entry and group 2's Clover title (#324) merged, Clover as
    possible (RI-10).
14. **Numbering.** Group 2's candidates were named R1-R10, which collides with the think tank's R1-R41; they are
    G2-1 to G2-10 here. Group 3's R3-n are G3-n.
15. **TT-PV fail-low reduction.** Group 2 listed it as common and absent; it is comparison.md's C9 family (Horsie's
    figure is in C9), so it is in evidence.md, not common.md.

## Dropped (constants or identifiers) and not reconciled

**Dropped from the section files**, as numbers that could be read as another engine's settings: Reckless's TT
key-check width (group 1); Caissa's three history-retention fractions (group 2; the gains are kept); the ply of
Tcheran's continuation correction table (group 3; written "a deeper-ply table"); SSSimpler's output-head count
(group 4); the parameter counts of Coda's SPSA and Triumviratus's ordering SPSA. No code identifier of another
engine was found in the sections; option names in Lc0's TCEC configuration are described, not given.

**Not reconciled (UNVERIFIED, carried over):**
- Whether Renegade's "bonuses as many times as failing high" and Starzix's "bigger bonus the more times PVS fails
  high" are RI-02's idea (if so, RI-02 is common).
- Viridithas's "FLKR" (if factorised LMR, RI-17 is common); which side's capture Viridithas's RFP guard tests.
- PZChessBot #136's mechanism (RI-20); Seer #185's link to the hidden-state key (RI-33).
- Which four "small novelties" Renegade's TCEC questionnaire names.
- Stockfish's use of the eval-difference update, the bonus-by-margin form, the tactical continuation split and the
  capture SEE threshold (groups 2 and 3 did not re-read Stockfish).
- Mechanisms without prose: Stockfish's "adaptive beta cut" and "risk tolerance"; Reckless's "correct expectation"
  reduction and laterality's exact definition; Berserk's "trivial" best move; RubiChess's "native depth"; Igel's
  "adaptive LMR" and "static history"; Halogen's "thread meritocracy"; Potential's "valuable piece" and "old TT
  move"; Motor's "material structure history"; several Quanticade, JustBot and Titan titles.
- TCs not stated: Coda's biased-start SPSA, Incipit's "STC", Reckless's deterministic helper bias.
- The share of PlentyChess's +32.9 data result due to mixing nets.
- The Stockfish issue comment that Stormphrax probes WDL only at the root (second-hand).
- Velvet's "lost sacrifices" label adjustment (named by the 2026-11-10 survey; CPW's page does not mention it).
- CCC 2026 participants (the page could not be read); the Stoofvlees article.
- Fork facts not read in code by any group: whether Fork's upcoming-repetition form checks that the opponent's moves
  cancel (F7); whether Fork's pair-table key includes the earlier move's capture flag (RI-09); whether move-loop
  pruning runs inside the singular search (CG-5); whether the 768-row map keeps dead pawn rows; whether T56's attack
  sets can serve RI-01's terms.
- Licences copied from the 2026-11-10 survey were not re-read.
- Every threshold the groups marked "estimate" in a cheapest test.
