# Originality: what TCEC allows, what it bans, and precedents

Checked 2026-10-23. Sources are listed in `docs/kb/_sources-competition.md`.
All wording is paraphrased. **UNVERIFIED** marks anything I could not confirm
on a page I opened.

---

## 1. TCEC's own rules

### 1.1 TCEC NNUE Guideline (unofficial)

Link: https://wiki.chessdom.org/TCEC_NNUE_Guideline (last edited 10 Jan 2022).
Verified 2026-10-23.

- TCEC trusts authors' statements in good faith; the guideline is
  unofficial and applied at TCEC's discretion.
- NNUE code may be treated like a library even if it is not packaged as one.
- Authors are strongly encouraged to modify the base NNUE code; it is a
  starting point, not a finished product.
- All training data must be produced by that engine's own search and/or
  evaluation.
- It applies only to NNUE, not to other technology.

Why it matters: rule 3 is the key one. Data from Stockfish, Lc0 or any other
engine breaks the guideline. Fork's plan (self-generated data only) complies.
Tag: USE (as a compliance target).

Note: several top engines say in their READMEs that their nets are trained
on Lc0 data (Stockfish, Obsidian, Alexandria). They still play TCEC, so the
guideline is clearly not enforced as an entry ban for them. In Swiss 7, TCEC
put new engines using "leela data" into a separate, harder playoff (Cat 3)
than new engines with "own data" (Cat 2). So in practice, borrowed data
costs a newcomer placement, not necessarily entry. How TCEC weighs this in
S30 categories is not written down: **UNVERIFIED**.

### 1.2 TCEC Questionnaire v2.4 (mandatory since S29)

Link: https://wiki.chessdom.org/TCEC_Questionnaire (edited 9 Nov 2025).
Verified. Answers are published (v2.1+) unless the author opts out.
Originality-relevant questions (paraphrased):

- Does the engine contain AI-generated code? Which parts, when, which tools?
- Licenses of all code.
- If an NN is used: whose training code.
- Origin of training data, and whether permission was obtained from the
  original authors where needed.
- Other engines (and authors) whose code is used, including NN code.
- Compliance with the NNUE Guideline, and why.
- What makes the engine unique.

The page also points to the "Chess Programmer Code of Honor" (rebel13.nl);
that page returned HTTP 526 on 2026-10-23 and again on 2026-10-24 (the
http URL redirects to https, which fails with 526), so its contents are
**UNVERIFIED**.

### 1.3 Categories and the S30 AI policy

- Swiss 10 (S30): Category 4 = engines with major help from AI. Their code
  must be public open source during the whole participation, and TCEC admins
  must be allowed to build from the repository. Category 5 = engines TCEC
  cannot feature (none listed). An engine may not change architecture
  mid-season into a higher-numbered category. Link:
  https://wiki.chessdom.org/TCEC_Swiss_10 (edited 22 Oct 2026). Verified.
- TD statement (Anton Mihailov, 31 Aug 2026): S30 is a test season for AI
  engines; they enter only via the Swiss (Cat 3+4 playoff, one spot); they
  are not eligible for the regular Leagues regardless of Swiss result; a
  separate gauntlet will be organised for them; the rules committee will
  consider separate or joint competitions later. Link:
  https://www.chessdom.com/tcec-announces-ai-integration-plans-as-a-new-generation-of-engines-enters-the-arena/
  Verified.
- Swiss 7 (S27): Cat 4 was "no questionnaire or failed originality test".
  What the originality test measures is not described anywhere I opened:
  **UNVERIFIED**.
- A formal TCEC clone/derivative rule (e.g. "engines derived from another
  engine's code are not admitted") or a net-similarity threshold: **not found
  on any page opened** (Rules, Leagues rules, Swiss rules, Further info,
  NNUE Guideline, Questionnaire). Wiki search for "derivative" and
  "Fat Fritz" returned nothing relevant. **UNVERIFIED**.

### 1.4 Precedent inside TCEC: Potential (Swiss 10, S30)

Potential declared itself an HCE engine (questionnaire and emails) and
qualified through the lighter HCE playoff, but its later repository versions
used NNUE with no notice. Found during Swiss 10. Decision: categories not
rolled back; Potential finishes Swiss 10 but its results cannot qualify it
for later S30 events (Entrance League); it may re-enter next season's
playoff. TCEC now requires authors to keep the questionnaire current and to
report architecture changes promptly. Verified (Swiss 10 page).

Lesson for Fork: declare everything up front (AI involvement, NN, data
source) and update TCEC by email on every architecture change (e.g. HCE to
NNUE in Phase 4).

---

## 2. Outside precedents

| Case | What happened | Status | Source |
|---|---|---|---|
| Rybka / ICGA (2011) | ICGA board ruled 5-0 (28 Jun 2011) that Rybka was derived from Fruit 2.1 and Crafty, breaching the WCCC originality rule; WCCC 2007-2010 titles annulled, author banned for life from ICGA events. CSVN refused to enforce. Rajlich complained to the FIDE Ethics Commission (2012); the outcome is not stated on the page opened. | Verified (secondary: chessprogramming.org); FIDE outcome **UNVERIFIED** | chessprogramming.org/Rybka_Controversy |
| Fat Fritz 2 and Houdini 6 / ChessBase (2021-22) | Stockfish project said both products were Stockfish derivatives sold without GPL source or license text; FF2 DVD recalled and Houdini 6 sales stopped; lawsuit filed in Munich (Jul 2021); settled Nov 2022: ChessBase stops selling Stockfish-based products, appoints a FOSS compliance officer, credits Stockfish, releases nets for Stockfish under GPL-compatible terms; license restored after a year; no damages sought. | Verified (official Stockfish blog) | stockfishchess.org blog 2021, 2022 |
| Houdini / Fire at TCEC (removal or bans) | Not confirmed on any opened TCEC page. | **UNVERIFIED** | none |
| Fat Fritz 2 at TCEC | No TCEC wiki match for "Fat Fritz". | **UNVERIFIED** | wiki search |
| Ethereal- or Stockfish-based engines rejected or told to change by TCEC | Not found on opened pages. | **UNVERIFIED** | none |
| Engines on Lc0 data | Stockfish, Obsidian, Alexandria state Lc0-data training (ODbL licensed) in their READMEs and play TCEC; S27 Swiss placed new "leela data" engines in a harder playoff. | Verified (READMEs; Swiss 7 page) | repos; wiki TCEC_Swiss_7 |
| CCRL policy | CCRL explicitly does not judge originality and listing implies nothing about an engine's status. | Verified | CCRL 40/15 About |
| CEGT policy | Not found. | **UNVERIFIED** | none |

---

## 3. What counts as using someone else's data or code (for Fork)

OFF-LIMITS for Fork (any of these makes Fork a derivative or breaks the NNUE
Guideline):

- Any source code from another engine, translated or not, including NNUE
  inference code, move generators, search code, tuned constant tables.
- Any network file from another engine, as weights, initialisation, teacher
  for distillation, or "fine-tune starting point".
- Training data produced by another engine: Lc0 training data
  (storage.lczero.org, even though ODbL permits reuse), Stockfish-scored
  positions, positions rescored by any other engine, CCRL/CEGT/TCEC game
  PGNs used as training labels (their moves and results come from other
  engines).
- Opening books or EPD suites built from other engines' evals, used for
  training data generation.
- Texel/SPSA tuning against positions labelled by another engine.

Allowed (USE), with logging:

- Self-play data generated by Fork's own search and eval (the NNUE Guideline
  standard).
- Third-party libraries under compatible licenses, declared in the
  questionnaire: Fathom (MIT) for Syzygy probing, a training framework if
  it is a general tool (bullet is used by many engines; declaring it is
  required by Q7). Writing Fork's own trainer is the cleanest option.
- Published facts used as test oracles (perft counts, TB results).
- Opening positions for data generation that carry no engine evals (e.g.
  random legal moves from startpos, or human opening theory without evals).
  Note Integral uses the UHO book for data-gen openings; an opening book
  built with Stockfish evals is a grey area: avoid.
- Opponent engines as binaries in gauntlets (Phase 8). Their games must never
  enter Fork's training data.

Grey areas to avoid entirely: human game databases rescored by Fork
(Viridithas did this with Lichess Elite; allowed by the guideline's letter
since Fork does the scoring, but it adds a permission question under Q8).

---

## 4. How Fork should document provenance to pass review

1. **Public repository from day one of the application** (required for
   Category 4). License chosen by the owner and stated in `LICENSE` and the
   questionnaire.
2. **AI disclosure.** State plainly that Fork is written by an AI coding
   agent under the owner's direction: which tool (Claude Code), which
   model(s), time span, and that all parts are AI-written or AI-assisted.
   Keep the session trailer in every commit (`Claude-Session` /
   `Co-Authored-By`), so the git log is itself the record.
3. **`docs/ORIGINALITY.md`** (already exists): every reference consulted with
   date and purpose; every library with license; every build tool.
4. **Training data log** (Phase 4): for every net, the generator binary
   (commit hash), the data-gen command line, opening source, position count,
   date range, parent net (if any), trainer commit, and the SHA-256 of data
   shards and the resulting net. Nets must form a chain back to a net
   trained from Fork's own HCE or random init.
5. **Opponent isolation**: Phase 8 gauntlet outputs stored apart from
   training data, with a check in the data-gen pipeline that refuses any PGN
   not produced by a Fork binary.
6. **Questionnaire draft** kept in the repo (`docs/tcec-questionnaire.md`
   when the time comes), answering all 14 questions in plain language
   without unexplained acronyms, as TCEC asks.
7. **Change notices**: email TCEC whenever architecture changes (HCE to
   NNUE, new net family, GPU use), per the Potential decision.
