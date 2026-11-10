# Idea 23, the ordering pilot: declaration before results

Owner's order, 2026-11-09 (verbatim): "Unpark idea 23 for a capped pilot on
the quiet move-ordering score: 1. Prerequisites: the evolve gate's Linux
end-to-end run; two-compiler gating of candidates. 2. Retarget the harness:
region = the quiet ordering score; fitness = nodes to fixed depth on the
large position set; held-out set; equivalence guard (same best move/score
within tolerance on a check set); the determinism requirements (self-check,
full candidate log, fixed seeds, replay mode tested on a tiny run). 3. Pilot:
5 generations x 8 candidates, low priority on spare threads beside data
generation (node counts don't need a quiet machine); base = current phase-4
(tuned values). 4. Report the best candidate's node reduction on the
held-out set, and the replay check. A design R SPRT of the winner only with
my OK."

This file fixes, before any pilot result exists, what is measured, how a
candidate is refused, and what is reported. It is committed before the
pilot starts; the pilot's numbers go in a separate results file. Nothing
here is changed after the pilot starts.

## 1. Base and region

- **Base:** branch `evolve/ordering-pilot`, from phase-4 at d42c248 (R14's
  adopted tuned values) plus the refactor that gives the quiet ordering
  score one function (src/search/quiet_score.hpp). Bench unchanged by the
  refactor: 10,374,064 / 677c436fa145e07f. The run pins the commit it
  starts from to its full hash (orchestrator.py).
- **Region `quiet_order`:** the body of `constexpr int quiet_score(const
  QuietScoreInputs& s)`, the combination of a quiet move's history entries
  into its ordering score. Inputs: the butterfly, reply and follow entries
  (each in [-10000, 10000]), whether the reply and follow arrivals exist,
  ReplyWeight and FollowWeight (quarters; ranges 0-12 and 0-8). The
  committed body: butterfly + reply * ReplyWeight / 4 + follow *
  FollowWeight / 4, each pair term only with its arrival. The caller clamps
  to int16. The score orders quiet moves only: LMR reads the butterfly
  entry directly, and no pruning reads the ordering score
  (src/search/searcher.cpp), so a candidate changes the move order and
  nothing else.
- **The take history** (the owner's restart plan names "take terms") scores
  captures, not quiet moves (move_selector.cpp score_captures). It is
  outside this region; a capture-order region would be a later target.

## 2. The gate (every candidate, before it is measured)

In order, the first failure refusing the candidate (tools/evolve/gate.py):
the static rules on the body (a lexer; no allocation, exceptions, floating
point, statics, preprocessor lines, digraphs or splices, I/O, threads,
balanced brackets); the guard (only the region's body differs from the
base, on disk); for each compiler, g++ 11.4 and clang++-19 (TCEC's, WSL
Ubuntu-22.04), the preprocessed text of every unit that includes the region
equal to the base's outside the body, and those units compiling with Fork's
flags (warnings are errors); then for each compiler a Release x86-64-v3
build of the engine and the tests, perft equal to the base's, the suites
search (the minimax oracle), pruning, params, tt, ordering and no_alloc,
and two equal benches; finally the two compilers' benches must be equal.
The `ordering` suite includes a static_assert that the body is a constant
expression without int overflow at every input extreme; the committed
formula's own checks are in suite `quiet_score`, which the gate leaves out.

## 3. Fitness

- **Measure:** each position searched to **depth 12** from a fresh state
  (`ucinewgame`: the hash table and every history table cleared), one
  thread, Hash 16 MB, one engine process per share of the positions; the
  last iteration's node count, best move and score. A node count to a fixed
  depth does not depend on the machine, its load, the number of processes
  or the order of the positions.
- **Generation set:** the `evolve` split of tools/evolve/positions.jsonl,
  **4,794 positions**, all of them (no sample: the wall-time estimate below
  stays under the owner's 24-hour line).
- **Fitness (higher is better):** the node reduction against the base on
  the same positions, 1 - (candidate's total nodes) / (base's total nodes);
  0 for the base. Its uncertainty over the positions: a paired percentile
  bootstrap of that ratio (2,000 rounds, 95%, seeded with 20261109 plus the
  candidate's id).
- **Held-out set:** the `holdout` split, **940 positions**, the same
  measure. Measured for every candidate that passes the guard, shown on the
  dashboard, never shown to an agent and never used to choose parents,
  elites or the best so far.
- **Depth 12, why:** deep enough that the order matters through the whole
  tree (the base needs a median of about 172,000 nodes per position, 167 ms
  on one thread, measured on 100 seeded evolve positions on 2026-11-09),
  shallow enough for 40 candidates in the time box.

## 4. The equivalence guard

- **Per position:** a candidate's answer is equivalent to the base's if
  the best move is the same and the scores are within **25 cp** (both
  centipawn scores), or both are mate scores for the same side.
- **Check set:** the generation set: its fixed-depth searches already give
  each position's best move and score, so the guard costs no extra search.
- **Rule:** a candidate is refused (status `guard: not equivalent`; not
  placed in the grid, never the best so far, never promoted) if its
  equivalent share of the check set is below the **threshold = the lowest
  equivalent share of the two calibration bodies, less 0.02**.
- **Calibration bodies** (config_quiet_order.json, measured by the harness
  at the run's start, before generation 1, and logged as the
  `guard_threshold` event): the committed combination with both weights one
  step down (ReplyWeight 5, FollowWeight 3) and one step up (7 and 5): the
  parameter table's smallest changes around the R14-tuned values, which the
  tuner treats as neighbours of the same search.
- **Reasoning:** the same best move and score at every position is not a
  usable rule: any change of move order changes which moves LMR reduces and
  which LMP and futility prune, so a few positions change their answer even
  for a change nobody would call a different search. The calibration
  measures how much such a change moves the answers, and the guard refuses
  a candidate that moves them clearly more. The margin, 0.02, is about three
  standard errors of a share near one half on 4,794 positions (the largest
  standard error, sqrt(0.25 / 4794) = 0.0072). The 25 cp tolerance (a
  quarter of a pawn) is a judgement, not a measurement: small enough that a
  changed assessment of the position counts as a difference, large enough
  that the few centipawns a changed order moves a fixed-depth score do not;
  the calibration then sets the share it is read against. The held-out
  set's equivalent share is reported but not used.

## 5. Determinism

- **Self-check:** at the start the base is measured twice on both sets, the
  second time split across one more engine process (3 instead of 2); every
  position's node count, best move and score must be identical, or the run
  stops.
- **Candidate log:** candidates.jsonl in the run folder, one line per
  candidate: the agent and island, the mode, the rationale, the source
  body, the critic's verdict, the gate's verdict (step, compiler, bench),
  the fitness, the guard's share and result, the held-out result and the
  SHA-256 of each set's answers (the per-position answers are in the run's
  database). replies.jsonl: every agent call's role, prompt SHA-256 and
  reply, in order.
- **Fixed seeds:** the run's seed 20261109 drives parent choice, the
  bootstrap and every other draw.
- **Replay:** `orchestrator.py --replay-from RUN` runs the logged run again
  with the logged replies in place of the agents and compares every
  candidate's body, status, fitness and answers; `--replay-candidates IDS`
  rebuilds and remeasures chosen candidates (and the base). Tested on a tiny
  live run (one generation, two candidates) before the pilot.

## 6. The pilot

- **Size:** 5 generations x 8 candidates: per generation, 3 from each of two
  proposers (prompts/quiet_order/: a bold one and a careful one, residual
  mode: keep the committed combination and change one thing) and 2 full
  replacements from the explorer (its island protected for 3 generations).
  The critic reviews every proposal before the gate; its rejections are not
  gated (critic_audit_share 0, to save wall time). The analyst summarizes
  after generation 3. All agents work under the clean-room rules
  (prompts/quiet_order/context.md), with no tools (CliAgent).
- **Agents:** the Claude Code CLI (`claude -p`, model sonnet), live
  (--live); token cap 10,000,000 for the run (the owner's budget, 2026-11-09, about 9:55 PM),
  counting every CLI call's reported usage (input, output, cache creation and cache reads), checked
  before each request, so the run stops cleanly at a request boundary; the tokens used are reported.
- **No match, no SPRT:** promotion only marks a candidate (games 0). A
  design R SPRT of the winner only with the owner's OK.
- **Resources:** a jobctl job of type `evolve`, at nice 19 in WSL
  Ubuntu-22.04, with 2 build jobs and 2 engine processes, beside data
  generation. **Estimate:** per candidate about 20 minutes (the gate with
  both compilers 8, measured by the Linux end-to-end run's clean body at
  464 s; the generation set about 7 at two processes; the stats build about
  2; the held-out set about 1.3; the agents about 1), the start (base
  self-check and calibration) about an hour: about **14 hours** in all,
  under the owner's 24-hour line, so the generation set is not shrunk. The
  machine's load (data generation on 10 threads) can stretch this; node
  counts are unaffected.

## 7. What is reported

- **The best candidate:** the highest node reduction on the generation set
  among the candidates that passed the guard.
- For it: the **held-out node reduction** with its 95% interval, the base's
  and its node totals, a per-position paired summary (positions with fewer,
  equal and more nodes; the median and geometric mean of the per-position
  ratio), its equivalent share on both sets, its source body, and the
  **replay check** (`--replay-candidates` of it: its node counts on both
  sets reproduced exactly).
- **A candidate worth the owner's SPRT decision:** a held-out reduction
  whose 95% interval lies above zero, from a candidate that passed the
  guard. Whether any candidate is, the report says; the SPRT waits for the
  owner.
- Also: every candidate's outcome (from candidates.jsonl), the tokens used,
  the wall time, the guard's threshold and calibration shares.
