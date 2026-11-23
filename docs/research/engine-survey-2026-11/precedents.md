# AI-assisted precedents for a Category 4 entry

Survey of 2026-11-10. Fork enters TCEC as a Category 4 engine, one written
with major AI help, whose code must stay public, buildable and
demonstrably original (CLAUDE.md). This file records how four AI-assisted
engines in or near the CCRL top 50 handled originality, what went wrong,
and what follows for Fork.

All of it comes from the engines' own public prose (README, CLAUDE.md,
ORIGINALITY and PROVENANCE files, licence analyses, issues) and TalkChess
threads. No TCEC page about these engines was opened, so **how TCEC views
any of them is UNVERIFIED**.

## Coda (CCRL #6, 3769): the warning case

**What it is.**
- A Rust engine by Adam Twiss.
- Its README says "every line of code was written by Claude Code, with
  direction, testing and review by a human". CCRL's note says the same.
- It started in January 2026 as GoChess, in Go and built the same way, and
  was rewritten in Rust in late March.
- Its OpenBench tests are authored by an account named "Claude".
- Licence: GPL-3.0-or-later. It was briefly MIT, corrected after
  GPL-only dependencies were pointed out.

**Its public rules** (its CLAUDE.md):
- ideas yes, expression never;
- no foreign constants, even as placeholders;
- close the reference before writing;
- on contamination, delete and rebuild the branch;
- AGPL engines excluded, and no AGPL source kept on its machines.

Its methodology notes, cross-engine study notes and agent "skills" moved to
a private repository after the dispute.

**The dispute** (issues #5, #9, #11, #14 to #17; TalkChess "CODA now has a
released page"):
- Andrew Grant found code resembling Reckless (AGPL) and Viridithas.
- The author's own July 2026 audit admitted three things:
  - the threat-feature index construction was "closely modelled" on
    Reckless's;
  - some SIMD kernels were too close;
  - some bucket tables were too close.

  These were removed or reimplemented, at about 3% nps, but the public
  git history was not rewritten.
- Critics said that one agent analysing the original and then writing the
  replacement is not a clean room. The author withdrew the "clean-room"
  label.
- A proposed AGPL relicence (PR #11) was declined.
- Several developers reacted with strong hostility. There were also
  complaints that the author's replies were themselves LLM-written.
- An attribution standard was requested: credit the author as well as the
  engine (citing the Leiden Declaration).

**What failed, and Fork's matching rule:**

| Coda's failure | Fork's rule that covers it |
|---|---|
| The same agent studied other engines' source, then wrote the code | Separate spec and implementer agents; the implementer never opens other engines' code; research agents read prose only; name screens clone into a temporary folder, report match or no match, and delete at once (CLAUDE.md non-negotiable 6) |
| Foreign constants used as seeds | Every search constant has a recorded justification and is screened against known engines before commit; matches are replaced or credited with the owner's approval (DESIGN.md §8, ORIGINALITY.md) |
| Study notes holding other engines' code were kept | No engine source, copied file or identifier dump is kept on the machine; reports hold prose only |
| AGPL-close code reached a public repository, and the history stayed | A history audit before Fork went public (2026-10-26); a personal-data and secrets scan before every push (`scripts/scan-push.sh`) |
| A licence mislabelled against its dependencies | GPL-3.0-or-later from the start; Fathom (MIT) vendored with its lineage recorded |

**Lesson for Fork.** Disclosure alone did not protect Coda. The damage came
from process failures that the code itself then showed. Fork's protection
is that its process leaves a record: ORIGINALITY.md rows, constant screens
and clean-room reports. One point Fork does not yet cover: **who writes
Fork's public replies** if its originality is questioned. Coda drew
criticism for answers that read as LLM-written. Recommendation: the owner
writes such replies personally, citing the records.

## Incipit: closest to Fork's rules

- **What it is.** Coda's author's later engine (from 2026-09-29; not on
  the CCRL list).
- **Rules:**
  - its agents may not read **any** other engine's code, commits or
    documentation;
  - its data is 100% its own self-play, about 33 B positions, published
    under a CC licence.
- **Against Fork:**
  - Incipit is stricter on reading. Fork's research agents read other
    engines' prose (READMEs, PR text, release notes) to collect ideas at
    concept level, and Fork credits them in ORIGINALITY.md.
  - Fork is equal on code (never opened by the implementer) and on data
    (own self-play only, no Lc0).
  - Fork is stricter on data purity: no other-engine games, by the owner's
    rule of 2026-11-10.
- **Lesson.** The two routes differ in one way that matters. Incipit
  forgoes the peer record. Fork uses it but keeps it at concept level, with
  every constant measured by Fork. Fork's ORIGINALITY.md should keep making
  that difference visible, idea by idea.

## Triumviratus (CCRL #2, 3784): not a clean precedent

- **What it is.** A C++ engine by Francesco Torsello, with Maurizio
  Platino; GPL-3.0. CCRL's note: "developed openly and with significant AI
  assistance".
- **Lineage:**
  - it started from BBC (GPLv3), and its board and move generation descend
    from it;
  - **up to 8.0, the rated version, it contained Stockfish code**: NNUE
    inference ported from SFNNv16, and a search written "on the
    algorithmic base of Stockfish 19" (its own docs); version 4.0 shipped
    Stockfish's own networks;
  - 8.1 (2026-11-07) says its inference was rewritten "from a
    specification" and every search block "in the project's own code and
    order".
- **AI use:**
  - research agents ("Claude Fable 5.1", as the project names it, not
    checked) proposed search ideas;
  - parallel agents audited, ported and wrote speed patches;
  - pull requests must say whether code was AI-generated;
  - novelty was checked by **reading the source of nine engines**, Coda's
    included.
- **Data:** Leela and Stockfish binpacks relabelled by Lc0 BT4.
- **Lesson.** Triumviratus shows that disclosure of AI use and a high
  rating can coexist with a derivative codebase. It is no model for Fork,
  whose rules forbid reading other engines' source, porting, and other
  engines' data. Its open development notes are useful only as a record of
  measured results.

## ZigQueen (CCRL #33, 3709): a disclosure model

- **What it is.** A Zig engine by Matthias Stier, GPL-3.0-or-later.
  - CCRL's note: "Claude wrote most of the source code. It did so under
    continuous human direction".
  - Its README: developed with Anthropic's Claude and OpenAI's Codex, which
    write and review code and run experiments, while the author decides what
    ships.
- **Disclosure.** It publishes ORIGINALITY.md and PROVENANCE.md. PROVENANCE
  says the record exists because agentic engines face community audits; it
  cites "Coda's 2026-07 audit" (not opened).
- **A disclosed exception.**
  - Its reduction and pruning formulas and initial constants (in 6.1.0)
    are Stormphrax 8.0.0's published defaults, scaled by one unit factor.
  - Later local SPSA runs moved most of them; the rest remain and are
    attributed.
- **Data:** Lc0- and Stockfish-derived binpacks relabelled by BT4, with ODbL
  terms honoured through a published alteration archive. No self-play.
- **Lesson.**
  - The disclosure form is worth copying: a provenance file that says,
    before anyone asks, what was written by AI, what was inherited, from
    whom, and under what licence.
  - The content is not Fork's standard. Fork does not inherit constants,
    even disclosed ones; it measures its own and credits any match the
    screen finds.

## The "engine forensics" page

- **What it is.** Chris Whittington (author of Chess System Tal) runs a
  public page (whittingtonchess.com, engine analysis and engine
  similarities) that reads public engine repositories. It labels each one
  AI-generated, AI-assisted or human, from commit shape and leftover tooling
  files.
- **What it implies for Fork.** Fork's public repository would certainly be
  labelled AI-generated:
  - it commits `CLAUDE.md` and a `.claude/` folder (agents, hooks, rules);
  - its commits carry AI co-author trailers;
  - its commit cadence is agent-like.

  That label is accurate and matches Fork's declared Category 4.
- **Risk.** The risk is not the label but a *similarity* finding. The same
  page also compares engines. Fork's protection is the clean-room record
  above, and its ORIGINALITY.md, which lists every reference and every
  constant-screen result.
- **Recommendation.**
  - Do not remove or hide the AI tooling: that would read as concealment.
  - Add a short disclosure section to README.md (the ZigQueen model).
  - Keep ORIGINALITY.md current, so a forensic reader finds the answers in
    the repository.

## Community context

- **Hostile to AI-built engines:**
  - Hobbes 3.0's release notes complain about "low-effort, vibe-coded slop
    engines" entering rating lists and tournaments;
  - Stormphrax's README takes a similar stance (S2);
  - Raphael's and JustBot's READMEs state they contain no LLM-generated
    code.
- **Accepting, in established projects:**
  - several Stockfish patches merged after SF 19 say they were written with
    AI agents;
  - Berserk merged PRs openly marked as AI-assisted (#594 carries an AI
    co-author line, #597 links an AI session).
- **Rating lists.** CCRL says it does not judge originality. A claim that
  CCRL testers are reluctant to test AI-made engines appeared only in a
  search snippet and was not found on the TalkChess pages opened
  (UNVERIFIED).

## What Fork should take from this

1. Keep the clean-room process exactly as it is. Every failure in Coda's
   dispute maps to a Fork rule already in force.
2. Disclose up front, in the repository, on the ZigQueen model; Fork's
   ORIGINALITY.md is most of the way there.
3. Credit authors as well as engines (the standard requested in the Coda
   dispute). This survey's ORIGINALITY.md rows do.
4. Have the owner, not an agent, answer public originality questions.
5. Ask TCEC, in Fork's questionnaire, how it treats AI-assisted entries
   (UNVERIFIED today).

## UNVERIFIED in this file

- TCEC's view of Coda, Triumviratus and ZigQueen.
- The CCRL reluctance claim.
- "Claude Fable 5.1" as named by Triumviratus.
- ZigQueen's citation of Coda's audit.
- The forensics page's classification of any particular engine (its
  method was read; no verdict on Fork exists).
