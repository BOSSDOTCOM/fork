# Idea 59, step 3: the Boundary Refiner, trained and built (plan for the owner's review)

Status: **approved by the owner on 2026-11-08, with two amendments**
(the next section). Written as a plan only: when it was approved, nothing
here was built, trained or running, and no job had been started for it.
The base is phase-4 at d89814f;
the default network is S512ppr3 (bench 14,149,617 / 1cb0717f040c294d,
tests/bench-s512ppr3.ref). The owner's requirements of 2026-11-08 and the
six additions of the same day (docs/ideas.md idea 59, commit 0e99c31) are
each designed below; idea 61 (boundary-gated decisions) is not designed
here, only the interfaces it will need (section 10).

How numbers are marked: **[measured]** with its file, commit or run;
**[derived]** computed in this plan from measured numbers (the arithmetic
is shown); **[estimate]** reasoning only, UNVERIFIED until measured. Paths
are relative to the repository or written from `~`.

The prior-art search for gated, boundary-specific refiners ran separately
(kb-researcher; KB branch kb e96e314,
docs/kb/research-boundary-refiner-prior-art.md; idea 59's literature line
was corrected from it in d89814f). This plan does not repeat it.

## Owner decision, 2026-11-08

The owner approved this plan with two amendments; everything else stands as
written, the recommendations of section 11 included.

1. **The near-window residual's mean is verified, and the target is
   centred.** The preview's mean of deep - static at near-window sites
   (+123 cp, section 1.3) is checked in the offline pre-check P0 (section
   5) before the pilot's labels are used: the sign and perspective
   conventions of both values (side to move's view), mate- and
   tablebase-adjacent scores (near, not only inside, the bands that 3.3
   leaves out), and selection effects (for example, sites that were
   selected by lying near the window of a search whose result then moved).
   The training target is **centred**: its mean over the training split is
   subtracted, so the refiner must learn position-specific corrections
   rather than a shift. The exact form (the mean in cp or in the loss's
   win-probability space, plain or weighted as the loss is) is fixed when
   the trainer is built, and reported. Acceptance check A3 (beat a constant
   shift, 3.8) stays.
2. **Every name reused from exp/oracle is screened before reuse** (its
   commits C1-C4: 0a40491, 56dacaf, d5bb138, 92aa87c), as every new name
   is (section 7, DESIGN.md §8).

**Order of work:** the zero-output speed A/B first (M1, section 4.5), then
the 3,000-site labelling pilot (3.3); P0 runs before the pilot's labels are
used. The speed A/B runs only in a quiet window the owner chooses (data
generation shares the machine).

**Owner's answers on the zero-output build (2026-11-08, with the name
screen):**
- Centring: the mean is subtracted in training and **not added back** in
  the engine (adding it back would be a constant shift, the bias-only
  control that lost 14.56 Elo).
- The dense weights' bound: |w| <= 64 (1.0 in float), exactness first;
  the reader rejects larger dense weights and the trainer clips to match
  (section 2.5, amended).
- The sparse first layer is deferred entirely from this build (no sparse
  experiment, no transposed weights); it returns to the owner, with an
  originality-checker review, only if the speed budget needs it (sections
  2.3, 4.2 and M1's variants read accordingly).
- The build's layout: the refiner's inference (reader, kernels, rows, the
  danger summary) is compiled and tested in every network build; the
  search's use of it and the embedded refiner file sit behind
  `FORK_REFINER`, set by CMake `FORK_REFINER_NET`; the committed zero
  refiner has its cap at EvalLimit (20,000), so bench equality shows the
  refiner really outputs zero rather than a cap of 0 hiding it.
- The new search and refiner constants (the margins 25/25, the 16 bins of
  125 cp, the danger buckets, the layer sizes 16/32/2 and the weight bound
  64) go through the originality-checker's constant screen before the
  commit that introduces them.

**Owner's additions for the quiet-machine A/B (2026-11-08):**
- **A call's breakdown,** each part in ns per call from fork_micro's
  component cases through bench/ab.py (interleaved, repeated), and, where
  useful, a sampling profile of the bench run: the accumulator read and
  pack, the exposure features (the rows), the entry layer, the middle layer
  and heads, and the overhead without calls (the gate's test, the TT flag).
- **The fallback order if over budget,** base-preserving first: (a) a
  faster exposure computation; (b) the narrower entry layer (8); (c) VNNI
  (an AVX-512 VNNI path, which needs TCEC's VNNI answer before it can ship;
  the AVX2 path must stay within budget on its own or be named as the
  bottleneck). The refiner lanes in the base accumulator (2.9) only if
  those fail, and only with the owner's approval. This replaces section
  4.4's last item (setting (a) stays a gate-rate fallback, priced by the
  same report).
- **The report gives the nps cost** of the whole-search A/B at the real
  gate rate (the bench's per-call cost scaled to the in-game call rate:
  (b) 6.97%, (a) 3.81% of nodes, section 1.1) **beside the break-even
  estimate:** the oracle's fixed-node gain against S512r2 as an upper-bound
  proxy for what a trained refiner might keep ((b) +41.0 +/- 10.0, (a)
  +29.8 +/- 9.8) against the speed price at 1.5 Elo per 1% of nps
  (1.26-1.80), so the nps loss at which the expected gain is zero is
  L* = G / k: (b) 27.3% [17.2%, 40.5%], (a) 19.9% [11.1%, 31.4%] [derived;
  the interval pairs the gain's ends with the price's opposite ends]. The
  break-even is a ceiling, not a target: the design line (3%) and hard line
  (5%) stand, since a trained refiner keeps only part of the oracle's gain
  (F1's line, section 5).

**XGR's exposure rule** (`exposed_pieces`, the refiner's exposure rows) was
screened on 2026-11-08 (verdict: a note; no network input in the four
engines flags each piece this way; related concepts credited):
ORIGINALITY.md, the row "XGR's exposure rule and plane" (phase-4 395ce1a,
cherry-picked onto idea59/step3).

**The constant screen (2026-11-08)** found the widths 16 / 32 and the
alternative 8 in other engines' layers and the safe-check buckets a near
match by role; the owner kept them with credit (ORIGINALITY.md). The entry
layer's four-unit hadd reduction resembled a common idiom and became one
horizontal_sum per unit (AF-S's form); whether that costs speed is read in
the quiet A/B.

**The speed gate S1, measured (2026-11-08, quiet window 12:22-12:48 PM EST;
tools/measure/refiner_speed.sh at 2b1c78b, results in ~/fork-measure/i59s3;
Windows, the A/B not pinned to a core, residual load under one core; every
binary's bench 14,149,617 / 1cb0717f040c294d):**

| Shape, setting | bench nps, gate off -> on | cost per call in the search | nps loss at the in-game rate | price, Elo [1.26-1.80 per 1%] | net against the oracle proxy | lines |
|---|---|---|---|---|---|---|
| entry 16, (b) 25/25 | -10.7% | 410 ns | 9.0% | 13.5 [11.4, 16.2] | +27.5 [+14.8, +39.6] | over 5% |
| entry 16, (a) 25/10 | -5.9% | 405 ns | 5.1% | 7.6 [6.4, 9.1] | +22.2 [+10.9, +33.2] | over 5% |
| entry 8, (b) | -7.5% | 278 ns | 6.3% | 9.5 [8.0, 11.4] | +31.5 [+19.6, +43.0] | over 5% |
| entry 8, (a) | -4.4% | 300 ns | 3.8% | 5.7 [4.8, 6.9] | +24.1 [+13.1, +34.8] | within 5%, over 3% |
| entry 16 + danger summary, (b) | -11.7% | 466 ns | 9.9% | 14.8 [12.5, 17.8] | +26.2 [+13.2, +38.5] | over 5% |
| entry 16 + danger summary, (a) | -7.4% | 520 ns | 6.4% | 9.6 [8.1, 11.5] | +20.2 [+8.5, +31.5] | over 5% |

The bench calls the refiner at 8.40% of nodes at (b) and 4.47% at (a); the
in-game rates are the oracle's S512r2 replays (6.97%, 3.81%). Other A/Bs:
G1 -0.7% (not significant; +0.62% of nodes called); the overhead without
calls (release against the refiner build with its gate off) -2.8% median,
-1.7% best (not significant at the 3% threshold); the release build against
the refiner build at its defaults -12.8%; phase-4 d89814f against this
branch's release build +0.1% (none). A call's parts:

| Part (ns per call, entry 16; A/A medians of 10 interleaved rounds) | ns |
|---|---|
| pack the clipped accumulator (refiner_pack) | 23.8 |
| all rows (refiner_rows; the exposure pass alone, exposed_pieces, 14.6) | 22.3 |
| **entry layer (refiner_l1)** | **246.2** |
| middle layer and heads (refiner_l2_heads) | 34.8 |
| a whole call (refiner_call: pack, rows, layers) | 337.0 |
| the gate's test, per computed evaluation (gate_fires) | 1.17 |
| the danger summary (danger_summary) | 26.5 |

The 8-wide entry layer takes 117.3 ns (-52%), its whole call 208 ns
(-38%). The danger summary adds 55% to the rows and 20% to a call (410 ns).
In the search a call costs about 70 ns more than in fork_micro (cache
pressure and bookkeeping, UNVERIFIED). perf in WSL (gate on): refiner_l1
6.83% of samples, refiner_l2_heads 1.59%, refined_eval_at 1.13% (pack and
rows inlined), exposed_pieces 0.77%. **The AVX2 entry layer is the
bottleneck** (73% of a call, multiply-throughput bound): every shape misses
the 3% design line, and only the 8-wide shape at setting (a) is within the
5% hard line. Break-even against the oracle proxy: (b) 27.3% [17.2%,
40.5%], (a) 19.9% [11.1%, 31.4%], a ceiling; F1's line (max(+8.6, price +
5)) would ask about +18.5 Elo of entry 16 at (b), +14.5 of entry 8 at (b),
+10.7 of entry 8 at (a).

**Owner decision after the A/B (2026-11-08):** build, on the 8-wide entry
shape, (i) a dense-weight bound of [-32, 32] (two 8-bit multiply-add
results then sum exactly in int16 before one widening, halving those
widenings) and (ii) an AVX-512 VNNI entry layer; measure both in a second
quiet window, judging the AVX2 path first (GitHub's SPRT shards run
x86-64-v3, so the AVX2 cost is what the SPRT charges). **TCEC's hardware
supports AVX-512 VNNI** (the owner, 2026-11-08; DESIGN.md §6, KB
competition.md question 8): the VNNI path can ship in the TCEC build, with
its scalar reference and an exactness test; the AVX2 path is still judged
first, for the GitHub SPRTs. The offline acceptance must show the
[-32, 32] clip costs no judgement: refiners trained at +-64 and at +-32
compared on the held-out near-window set (explained variance, flip accuracy
at crucial sites, and A3, beating a constant shift). The refiner lanes stay
untouched. Meanwhile the 3,000-site labelling pilot and P0 run.

**P0 and the labelling pilot (2026-11-08; measure jobs i59s3-p0-seeds,
i59s3-pilot-replay2, i59s3-pilot-labels, 2 threads, one at a time; data in
~/fork-measure/i59s3/p0 and /pilot; the scripts used are scratch tools, to
be committed as the plan's D1 tools once their names are screened):**

*P0 (i), the oracle's knowledge on the new base.* On the crucial-point sites
(SPRT games, report only; 5,433 sites, deep values at 1M nodes by the
2026-11-07 engine), each network evaluated by R-int: at the sites within
25 cp of the base's own evaluation, S512+X over S512ppr3 fixes 152 and
breaks 125 of 919 gated sites, net flips **+0.029** (McNemar z +1.62, not
significant at p < 0.01), against **+0.076** over S512r2 (164 / 98 of 864,
z +4.08): the ratio is **0.38**. Most of what S512+X knew that S512r2 did
not, S512ppr3 knows already; the oracle's +41.0 is an optimistic prior for
S512ppr3 (scaled by the ratio, about +16 [derived, a rough reading, not a
measurement]). P0 informs, it does not kill.

*P0 (ii), the residual's +123 cp mean* (deep - static at sites within
25 cp; owner's amendment 1):
- **Sign and perspective are right:** both values are the side to move's
  at the site (the stats build's frame value and the deep search of the
  site's FEN); the static evaluation correlates +0.90 with the side to
  move's material, the deep value +0.69, the two +0.79; 12 of 4,948 sites
  disagree in sign beyond +-300 cp.
- **Mates and tables do not make it:** 420 of 5,368 deep values are mates
  (44 of 898 within 25 cp; out of every mean here), none lies in the
  tablebase band, 11 are decisive (|v| >= 2,000), 63 positions have at most
  5 pieces; leaving those out moves the mean from +122.6 to +118.3 / +124.1.
  The mean is heavy-tailed: the **median is +24.5**, the mean of
  |r| <= 1,000 is +94.9, 68% of the residuals are positive.
- **Selection: not the window's.** The residual grows away from the
  window (median by gap band: 0-25 +24.5, 26-80 +43, 81-200 +89, 201-500
  +142, over 500 +179 cp; means +123 to +241), so selecting sites near the
  window shrinks it. It is a property of positions inside the tree, at
  zero-window nodes (+124.8, n 838), reached by inferior moves whose
  refutation the static evaluation does not see; at the open-window (PV)
  sites it is +7.2 (n 16). On the pilot's own sites (below, 1M labels) the
  same holds: within 25 cp +134.1 (median +34.5, n 1,064), PV sites +25.7
  (median +4.0, n 29); sites from searches whose root score moved by more
  than 30 cp over their last two iterations +150.9 (median +39.0, n 73),
  from stable searches (<= 10 cp) +119.0 (median +26.0, n 766): a search
  whose result moved adds a little, not the bulk.
- **The centring** (decided): over the pilot's 80 cp set, decision-weighted
  (h = 25 cp), the mean residual is +139.4 cp, +0.0875 in win probability
  (S = 89); the training split's own mean replaces it at training. The
  weights' n_eff is 0.60 n (idea 48's rule, at least 0.5 n: h = 25 stands).

*The labelling pilot (3.3).* 150 validation games of the sealed part g3i
(g3i-w05-val.vf, seed 20261108) replayed through the stats build at
200,000 nodes per move (16,237 sites sampled, 6,496 within 80 cp); 3,000
of those picked (seed 20261108; 1,129 within 25 cp; main 1,835,
quiescence 1,165, reused 1,355) and labelled at 100k, 300k and 1M nodes by
the pinned default engine (~/fork-measure/bin/fork-release-2b1c78b.exe,
SHA-256 17ab2b41...0b34; hash and bench 14,149,617 / 1cb0717f040c294d
checked before the first label and after the last). Median label depth 11,
14 and 17. Against the 1M label at the gated sites (<= 25 cp): side
agreement 0.942 at 100k, 0.964 at 300k; win-probability residual
correlation 0.987 and 0.993; at the 1M-crucial sites (n 432) agreement
0.910 and 0.956. **By the plan's rule (90% agreement, 0.8 correlation),
the training labels' budget is N = 100k nodes** (13.9 thread-hours for
1 M sites, 6.9 h on 2 threads); validation and test sites stay at 1M. 172
of the 3,000 1M labels are mates (5.7%).

**Owner decision: step 3 continues with a cost gate (2026-11-08, declared
before the second window).** The [-32, 32] bound and the AVX-512 VNNI entry
layer are built on the 8-wide shape and measured in a second quiet window:
x86-64-v3 builds judge the AVX2 path (what the GitHub SPRT shards run), the
VNNI preset is measured separately (TCEC). **Labelling and training go on
only if the AVX2 path's cost at the chosen gate setting is at most about
3.5% of nps in game (a price of at most about 5 Elo at 1.5 Elo per 1%);
otherwise step 3 pauses and the oracle's findings are kept.** The case
being priced: P0's prior is about +16 Elo (S512+X's net flips over
S512ppr3 are 0.38 of those over S512r2, applied to the oracle's +41.0; a
rough reading), against the first window's 3.8% for the 8-wide shape at
setting (a) and 6.3% at (b). If the gate passes: the 1 M training sites are
labelled at 100k nodes (the pilot's pick by the plan's rule) on 10 threads
while the owner suspends data generation in place (the labels are
node-based, so threads do not change them), by the pinned engine with its
hash and bench checked before the first label and after the last;
validation and test sites stay at 1M.

**The second window, measured (2026-11-08, 2:13-2:45 PM EST;
tools/measure/refiner_speed.sh `second` at 5ea2ad1, results in
~/fork-measure/i59s3/second; Windows, not pinned; every bench 14,149,617 /
1cb0717f040c294d):**

| Build (entry 8) | Setting | bench nps, gate off -> on | cost per call in the search | nps loss in game | price, Elo [1.26-1.80 per 1%] | line |
|---|---|---|---|---|---|---|
| x86-64-v3, bound 64 | (a) 25/10 | -2.94% | 206 ns | **2.52%** | 3.8 [3.2, 4.5] | within 3% |
| x86-64-v3, bound 64 | (b) 25/25 | -5.55% | 215 ns | **4.65%** | 7.0 [5.9, 8.4] | within 5% |
| x86-64-v3, bound 32 | (a) | -3.20% | 226 ns | 2.74% | 4.1 [3.5, 4.9] | within 3% |
| x86-64-v3, bound 32 | (b) | -5.72% | 219 ns | 4.79% | 7.2 [6.0, 8.6] | within 5% |
| VNNI, bound 64 | (a) | -2.97% | 192 ns | 2.55% | 3.8 [3.2, 4.6] | within 3% |
| VNNI, bound 64 | (b) | -6.30% | 221 ns | 5.29% | 7.9 [6.7, 9.5] | over 5% |
| VNNI, bound 32 | (a) | -3.54% | 227 ns | 3.03% | 4.5 [3.8, 5.5] | within 3.5% |
| VNNI, bound 32 | (b) | -6.90% | 243 ns | 5.80% | 8.7 [7.3, 10.4] | over 5% |

Each target's overhead without calls (its baseline against the refiner
build with the gate off): x86-64-v3 -1.2%, VNNI -1.0% (neither significant);
the whole price on the bench at 25/25 against each baseline: v3 -7.6% /
-6.5% (bounds 64 / 32), VNNI -7.2% / -7.0%. A call's parts:

| Part (ns per call, entry 8) | v3, bound 64 | v3, bound 32 | VNNI, bound 64 | VNNI, bound 32 |
|---|---|---|---|---|
| pack | 24.1 | 24.1 | 24.1 | 24.1 |
| rows | 23.1 | 23.1 | 22.6 | 22.7 |
| entry layer | 79.8 | 76.9 | 74.3 | 74.3 |
| middle layer and heads | 34.9 | 34.9 | 37.3 | 37.1 |
| a whole call | 173.0 | 170.2 | 167.0 | 166.5 |

Bound 32 against 64 on the AVX2 path: the entry layer -3.9% (significant),
the call -1.7% and the whole search nothing measurable; VNNI against AVX2:
the entry layer -7.3%, the call -3.6%, the cost per call in the search about
the same. The restructured AVX2 kernel (64 bytes a step, two independent
products) took the 8-wide entry layer from 117 to 80 ns and the call in the
search at (b) from 278 to 215 ns, more than the bound or VNNI. **The cost
gate on the x86-64-v3 builds: passed at setting (a) (2.52% in game, 3.8 Elo),
failed at (b) (4.65%).**

**Owner decision (2026-11-08): step 3 proceeds at gate setting (a), main
25 / quiescence 10 cp, with the dense-weight bound +-64.** Bound 32 stays in
the code, tested but unused (it buys nothing measurable and would constrain
training; the +-64 against +-32 offline check is dropped). The VNNI entry
layer stays for the TCEC build. The price to beat is about 3.8 Elo at (a)
(P0's prior there, the oracle's +29.8 at (a) times the ratio 0.38, is about
+11 Elo: a rough reading); the fixed-node screen F1's line becomes max(+8.6,
3.8 + 5) = +8.8 Elo, with the price recomputed in the shard build. The
labelling plan follows (to the owner first).

**The labelling plan (owner-approved, 2026-11-08).**
- **The split, a departure from 3.5:** by sealed shard, not by a CRC-32 of
  the game id. Training: 3,000 games of g3i's shards w00-w04 (seed
  20261109; 1,000,000 sites labelled at 100k nodes). Validation: g3i's
  validation shard g3i-w05-val, the pilot's 150 games extended to 450 by
  the same seeded shuffle (seed 20261108; the first 150 are the pilot's,
  byte for byte), 10,000 sites at 1M: the pilot's 3,000 and 7,000 new.
  Test: 450 games of another generation's validation shard, g3h-w05-val
  (seed 20261110), 10,000 sites at 1M (3.5 asked for a different sealed
  part's games; its 20,000 sites become 10,000 for validation and 10,000
  for test, the same labelling total as 3.4's row). The shards are sealed
  and disjoint by game, so no fold rule is needed.
- **Deduplication (3.2), by the position** (the FEN without its move
  counters: placement, side, castling, en passant): the first site by id
  of each position within a selection; test's positions left out of
  validation's new sites (and the pilot's 3,000 out of them too), and every
  position of a validation or test game's sites left out of training.
  near_window_sites.py `select --dedup --exclude` (706c724).
- **Replay settings:** test and validation as the pilot (200,000 nodes a
  move, sampling every 45,000th main-search and 90,000th quiescence site,
  iteration rows; validation resumes the pilot's replay folder after its
  150 games); training samples every 6,400th and 7,700th site without
  iteration rows (the pilot's yield, 26.7 main-search and 16.9 quiescence
  sites within 80 cp a game, scaled: about 1.16 M within 80 cp before
  deduplication and exclusion). Window gap at most 80 cp, as the pilot.
- **Decision weights per stratum (amends 3.7):** h = 25 cp at main-search
  sites and 10 cp at quiescence sites, matching setting (a)'s margins.
  n_eff is rechecked on the training split after selection and recorded
  here. **On the pilot's sites it falls below idea 48's rule:** 0.47 n on
  the pilot's 3,000 (0.47 on all its 6,496 within 80 cp), against 0.60 at
  a single h = 25; with main search at 25, quiescence needs h = 13 (the
  3,000) or 14 (the 6,496) for 0.5 n. **Owner decision (2026-11-08,
  declared before the training split is selected):** main search h = 25
  cp; quiescence h = the smallest whole h giving n_eff >= 0.5 n on the
  training split, computed after its selection (near_window_sites.py
  `select` prints it, 29e6a25) and recorded here. The labels do not depend
  on it.
- **Labels with the tables (owner decision, 2026-11-08):** every label
  searches with the Syzygy 3-4-5 tables, as 3.3 says (crucial_points.py
  `deep --syzygy`, 29e6a25; the pilot's labels had been made without
  them, the tool setting no path). The pilot's 3,000 validation sites are
  labelled again at 1M with the tables in the same window, so every label
  shares one protocol; their table-less labels are kept aside, renamed
  (pilot/n1m/deep-notables.tsv). The budget pilot's 100k and 300k labels,
  and its N = 100k, stay as measured without tables.
- **One window (owner change, 2026-11-08):** collection and labelling run
  in one window on 10 processes while the owner suspends data generation
  in place. First, **the determinism check, declared before it runs:** the
  pilot's first 20 games are replayed with 10 processes into a fresh
  folder and must equal the pilot's 2-process game files byte for byte
  (every record: sites, counters, histograms, iteration rows, best moves);
  any difference stops the window. A game's results cannot depend on the
  process count: each game is replayed, in order, by its own engine process
  (one search thread, Hash 16, a new process per game), every search stops
  at a node count and never at a time, the site sampling counts
  evaluations inside that process, the processes share only read-only
  files (the engine, the tables), and the selection is a seeded shuffle
  sorted by id. The resumed validation replay must leave the pilot's 150
  game files unchanged (SHA-256 before and after), and validation's site
  list must begin with the pilot's 16,237 sites, ids included. Then the
  three replays and site lists, the selections, and the labels:
  validation (the pilot's 3,000 again, then the 7,000 new) and test at 1M
  first, then training at 100k, by the pinned engine with its hash and
  bench checked before the first label and after the last.

**The window, measured (2026-11-08, 3:19:43-5:32:32 PM EST, 2 h 12 min
49 s; data generation suspended in place by the owner; tools at bf70264,
the job i59s3-window, results in ~/fork-measure/i59s3):**

| Phase (10 processes) | Start - end (EST) | Length |
|---|---|---|
| 1. Determinism check | 3:19:44 - 3:20:23 PM | 39 s |
| 2a. Validation replay (resumed after game 150) and site list | 3:20:23 - 3:25:21 PM | 4 min 58 s |
| 2b. Test replay and site list | 3:25:21 - 3:31:07 PM | 5 min 46 s |
| 2c. Training replay and site list | 3:31:07 - 4:06:53 PM | 35 min 46 s |
| 3. Selections | 4:06:53 - 4:07:20 PM | 27 s |
| 4. Labels (both engine checks included) | 4:07:20 - 5:32:32 PM | 1 h 25 min 12 s |

- **Determinism: passed.** The pilot's first 20 games replayed by 10
  processes equal its 2-process game files byte for byte (whole files).
  The resumed validation replay left the pilot's 150 game files unchanged
  (SHA-256 before and after) and validation's site list begins with the
  pilot's 16,237 sites, ids included; the stats build's hash was the same
  before and after the replays.
- **Sites:**

| Split | Games | Sites sampled | Within 80 cp | Selected (dropped) | Main / quiescence | n_eff at h = 25 / 10 cp |
|---|---|---|---|---|---|---|
| Validation, new | 450 (the pilot's 150 among them) | 49,347 | 16,472 | 7,000 (the pilot's 3,000 excluded, 2 duplicates) | 4,330 / 2,670 (38.1% quiescence) | 0.46 n |
| Validation, the pilot's | 150 | 16,237 | 6,496 | 3,000 (the pilot's pick) | 1,835 / 1,165 (38.8%) | 0.47 n |
| Test | 450 | 48,362 | 19,375 | 10,000 (3 duplicates) | 6,114 / 3,886 (38.9%) | 0.47 n |
| Training | 3,000 | 2,825,463 | 1,122,981 | 1,000,000 (709 duplicates; none excluded) | 476,658 / 523,342 (**52.3%**) | 0.42 n |

- **The training's quiescence h: 17 cp** (n_eff 0.500 n with the main
  search at 25 cp; the rule declared before the selection). Validation and
  test would give 15 and 14.
- **The training split's stratum mix** (the open item, closed below).
  52.3% of its sites are quiescence sites against about 39% in the pilot,
  in validation and in test: training sampled every 6,400th main-search and
  every 7,700th quiescence site, 7.0 and 11.7 times as densely as the
  pilot's 45,000 / 90,000, so its ratio of quiescence to main-search sites
  is 1.10 against 0.62-0.64 in validation and test (1.7 times).
- **The training mix (owner decision, 2026-11-08; closes the open item).**
  The loss weights main-search and quiescence sites to the refiner's real
  call mix at gate (a), not to the validation and test mix: **44.1% main
  search, 55.9% quiescence**, from the oracle's in-game call rates at (a),
  1.68% and 2.13% of nodes (1.68 / 3.81 and 2.13 / 3.81; section 1.1's row
  "Oracle in-game call rates, 800k nodes, (a)"). (The acceptance metrics
  first took the same weights; the owner's next decision, below, gives them
  the deployment weighting instead.) h stays 25 cp at main-search
  sites and 17 cp at quiescence sites. **The normalisation, as the
  orchestrator reads "match the call mix" (recorded as that reading):**
  after the closeness kernel `exp(-g^2 / (2 h^2))`, each stratum gets one
  factor so that its total weight (kernel x factor) is in the ratio 1.68 :
  2.13 in every split, the weights then averaging 1. On the labelled sites
  each split uses (mate-flagged labels and the table band, |label| >=
  29,250, left out as 3.3 says):

| Split | Sites used (left out) | Main / quiescence | Kernel's main share | Factor, main / quiescence | n_eff, kernel only | n_eff, with the factors |
|---|---|---|---|---|---|---|
| Training | 937,645 (62,355) | 47.5% / 52.5% | 0.577 | 2.089 / 3.609 | 0.501 n | **0.468 n** |
| Validation (the pilot's 3,000 and the 7,000) | 9,180 (820) | 61.4% / 38.6% | 0.707 | 1.623 / 4.972 | 0.526 n | **0.392 n** |
| Test | 9,187 (813) | 60.9% / 39.1% | 0.704 | 1.587 / 4.790 | 0.535 n | **0.403 n** |

  The factors make each split's main-search share of the total weight
  0.4409 (checked). **With the factors, training's n_eff (0.468 n) falls
  below idea 48's 0.5 n line (A8, 3.8)**; it was 0.501 n with the kernel
  alone. h stays as decided; A8 is decided below (the kernel's n_eff).
  Validation's and test's n_eff fall further (0.39-0.40 n), their mix
  being about 61 / 39.
- **A8 and the acceptance weighting (owner decisions, 2026-11-08,
  recorded before any acceptance metric is computed).**
  1. **A8 judges the n_eff of the closeness weights alone:** training's
     0.501 n passes. The n_eff with the call-mix factors (0.468 n) is
     reported beside it, for information.
  2. **The acceptance metrics use deployment weighting:** only sites inside
     gate (a)'s margins count (main-search sites within 25 cp of the
     window, quiescence sites within 10 cp), weighted equally within each
     kind, times the call-mix factor, so the two kinds' totals are 44.1 :
     55.9 (1.68 : 2.13). The constant-shift baseline (A3) and every other
     A-check use the same weighting. The training-objective version
     (closeness x call mix, "The training mix" above) is reported beside
     it for diagnosis only; acceptance is judged on the deployment
     weighting alone.
  3. 3.8's margins are setting (a)'s, 25 / 10 (the owner's decision
     "step 3 proceeds at gate setting (a)", 2026-11-08, above); its earlier
     "(25 / 25)" predated that decision.

  On the labelled sites each split uses (mate-flagged labels and the table
  band left out, as for the training weights):

| Split | Inside gate (a): main search (<= 25 cp) | Quiescence (<= 10 cp) | Factor, main / quiescence | n_eff of the deployment weights |
|---|---|---|---|---|
| Validation (the pilot's 3,000 and the 7,000) | 2,096 (2,275 with the left-out labels) | **559** (604) | 0.559 / 2.655 | 1,534 of 2,655 (0.578 n) |
| Test | 2,175 (2,343) | **582** (632) | 0.559 / 2.648 | 1,596 of 2,757 (0.579 n) |
| Training (for reference) | 168,495 | 75,873 | 0.640 / 1.801 | 189,637 of 244,368 (0.776 n) |

  **Flag: the quiescence counts are too small for a per-stratum NF of
  P0's size.** The plan declares no resolution for 3.8's checks; as the
  yardstick, P0's fixed + broken share of gated sites (277 of 919, 0.30)
  and its NF (+0.029) give the smallest NF that reaches McNemar p < 0.01
  (z 2.576) as 2.576 sqrt(0.30 / n): about 0.030 for test's 2,175
  main-search sites, **0.058 for its 582 quiescence sites** (0.060 for
  validation's 559), and 0.035 for the deployment-weighted whole (n_eff
  1,596). An NF of P0's size (+0.03) is then resolvable in the main search
  alone, not in quiescence alone, and only marginally in the weighted
  whole. Resolving +0.03 in quiescence would take about 2,200 gated
  quiescence sites, about four times the current count (more test sites
  labelled from test/all's games, for example): for the owner.
- **The test set, enlarged about three times (owner decision, 2026-11-08;
  recorded before the new sites are labelled).** So that the
  deployment-weighted whole resolves about 0.02 (McNemar p < 0.01 at P0's
  discordance), the test fold's games grow from 450 to 1,350: the same
  shard (g3h-w05-val.vf), the same seeded shuffle (seed 20261110; its first
  450 picks are the current games, checked byte for byte), replayed with
  the pilot's settings into the same folder (the 450 game files unchanged,
  SHA-256 before and after; the site list must begin with the current
  48,362 sites), beside data generation on 3 processes at below-normal
  priority (the owner accepted it; labels and replays are node-based).
  20,000 new sites are picked by the same rule (window gap at most 80 cp,
  deduplicated, seed 20261110), leaving out every position already
  selected in any split (the pilot's 3,000, validation's 7,000, test's
  10,000, training's 1,000,000), and labelled at 1M nodes with the tables
  by the pinned engine, its hash and bench checked before and after
  (folder test/n1m2; the test split is test/n1m and test/n1m2 together).
  **Targets, from the current test set's rates** (2,175 main-search and 582
  quiescence sites inside gate (a) per 10,000 picked): about 6,500 and
  1,750 inside gate (a) of 30,000, a deployment-weighted n_eff of about
  4,800, so the smallest NF reaching p < 0.01 becomes about 0.020 for the
  weighted whole, 0.017 for the main search and 0.034 for quiescence
  alone (2.576 sqrt(0.30 / n)). **The offline acceptance (O1) waits for
  the enlarged test set.** The selection's real counts are recorded here
  before the labels start.
- **Labels (Syzygy 3-4-5; the pinned engine, SHA-256 17ab2b41...0b34,
  bench 14,149,617 / 1cb0717f040c294d as referenced before the first label
  and after the last).** Nodes per second are nominal (sites x the node
  limit / wall time; deep.tsv does not record the nodes searched):

| Labels | Sites | Nodes each | Wall time | Nominal nodes/s (10 workers) | Mate-flagged |
|---|---|---|---|---|---|
| The pilot's, again with the tables | 3,000 | 1M | 1 min 56 s | 25.9 M | 164 |
| Validation, new | 7,000 | 1M | 4 min 28 s | 26.1 M | 387 |
| Test | 10,000 | 1M | 6 min 50 s | 24.4 M | 560 |
| Training | 1,000,000 | 100k | 71 min 48 s | 23.2 M | 42,662 (4.3%) |

  In all, 1.2 x 10^11 nodes in 85 minutes, about 23.5 M nodes/s (about
  2.35 M per worker; 2.87 M per worker with 2 workers beside data
  generation). At 100k nodes a site's fixed costs (`ucinewgame`, the
  `isready` round trip, the label's write) weigh more than at 1M.
- **The pilot's labels with and without the tables.** Median depth 17 both;
  2,138 of the 3,000 values identical. The 862 that changed lie in
  positions of few pieces: 440 of 571 sites of 3-8 pieces, 368 of 569 of
  9-12, 52 of 514 of 13-16, 2 of 881 of 17-24, none of 465 of 25 or more.
  The two at 17 and 18 pieces (sites 8796 and 12882) were labelled again,
  each alone in a fresh process at 1M nodes on the pinned engine: with the
  tables each gives exactly the window's label (1,216 and 973), without
  them exactly the old pilot label (1,193 and 1,245). So the labels do not
  depend on the sites a worker searched before; the tables change them.
  The table-less labels stay in pilot/n1m/deep-notables.tsv.

## 0. The design in brief

1. S512ppr3 evaluates everywhere, unchanged. Where the gate fires (the base
   evaluation within 25 cp of the nearest finite window bound, main search
   and quiescence alike: setting (b)), a small refiner computes a
   correction and the search uses `base + correction`.
2. The refiner reads S512ppr3's own accumulator, clipped to [0, 255] as the
   base's output already clips it (1,024 bytes, side to move first), plus
   sparse rows computed on demand: the exposed pieces first (XGR's rule,
   640 square rows), then a bitboard danger summary (36 rows) as a variant,
   then threats only if they fit the speed budget. No second accumulator.
3. Layers: 1,024 (+ active rows) -> 16 -> 32 -> 2 heads (the correction
   and a confidence), clipped ReLU, int8 weights, about 28,000 parameters,
   a file of about 40 KB. The correction is capped at a data-derived C
   (preview: the 75th percentile of |deep - base| near the window, 183 cp).
4. The refiner never sees the window: its output is a function of the
   position alone; only whether it is consulted depends on the window. The
   TT stores the value used with a new "refined" flag bit (a free bit of
   the flags byte), and a refined value is sticky while its entry lives.
5. Training data: near-window sites (window gap <= 80 cp) logged by the
   stats build while replaying Fork's own data-generation games at 200,000
   nodes per move; deep-labelled at N nodes (a pilot picks N from 100k,
   300k, 1M) by a pinned, bench-checked binary; target `deep - base` in
   win-probability space (S = 89); weighted by closeness to the window
   (idea 48's kernel, h = 25 cp); about 1 M training sites to start.
6. The refiner is new, so nothing of it is warm-startable on its first
   training: the base is frozen, the correction head starts at zero (so the
   refined evaluation starts equal to the base's, a checkable identity),
   and the warm 1e-4 recipe applies to every later refiner retrain.
7. Speed is the crux and is measured **before** any data work: a zero-output
   refiner of the final shape searches S512ppr3's exact tree (bench
   unchanged), so plain interleaved rounds price it (the identical-tree
   method). Estimates put a call at 140-230 ns, 3-5% of nps at setting
   (b)'s 6.97% call rate (4.5-7.5 Elo at 1.5 Elo per 1%); the design line
   is 3% (133 ns per call), the hard line 5%. No speed claim is made
   before the build is measured on a quiet machine with bench/ab.py and in
   the runners' in-situ speed job.
8. Gates in order: the speed gate, offline acceptance against declared
   lines (calibrated against the oracle's own offline score), a fixed-node
   screen against S512ppr3 (pass at least the speed price + 5 Elo, and at
   least +8.6), the quiescence-margin head-to-head (25 against 40 cp, at
   STC), the STC SPRT on network bounds [0, 5], then LTC. Two tries.

## 1. What step 3 starts from

### 1.1 The evidence

| Item | Number | Source |
|---|---|---|
| Near-window call rates, step 1 (200k nodes, computed evaluations) | 25 cp: main 10.1% of main evaluations, 1.48% of nodes; quiescence 14.8%, 5.58% of nodes | [measured] DESIGN.md §5.7 on measure/step1, b17e089 (stats build d7de27b); ~/fork-measure/i59/i59-n200k.json |
| Reused (TT) evaluations within 25 cp, step 1 | main 3.54% of nodes (20.9% of reused), quiescence 0.74% (48.6%) | [measured] same; recomputed here from the per-search histograms |
| Step 2 oracle, setting (a) 25/10 cp | +29.82 +/- 9.78 Elo at fixed nodes, run 42436884886 | [measured] ideas.md idea 59 (e389204); exp/oracle d5bb138 |
| Step 2 oracle, setting (b) 25/25 cp | **+41.01 +/- 9.97** (nElo +70.68), run 42439918061 | [measured] same |
| Random gate at (a)'s call rate | +7.60 +/- 9.93, run 42451958660 | [measured] same; exp/oracle 92aa87c |
| Bias only (+10.776 cp at (a)'s gate) | **-14.56 +/- 9.96**, run 42448595388 | [measured] same |
| Oracle in-game call rates, 800k nodes, (a) | main 82,641,827 of 823,342,940 computed (10.0%, 1.68% of nodes); quiescence 104,509,985 of 1,793,107,938 (5.8%, 2.13%); 3.81% of nodes; 0.533 evaluations per node; reused near-window 3.17% of nodes; mean refinement +10.8 cp, mean abs 25.6 | [measured] ~/fork-jobs/jobs/oracle-rates-a.json (job ended 2026-11-07 7:33 PM EST), its replay records in ~/fork-measure/i59/oracle-a-800k |
| Same, (b) | main 84,674,170 of 823,779,120 (10.3%, 1.73% of nodes); quiescence 257,383,267 of 1,795,909,778 (14.3%, 5.24%); **6.97% of nodes**; 0.534 per node; reused near-window 3.25%; +10.2 / 24.9 cp | [measured] oracle-rates-b.json, ~/fork-measure/i59/oracle-b-800k |
| Same, random gate | 3.82% of nodes; +11.2 / 36.9 cp | [measured] oracle-rates-random.json |
| Replay throughput (oracle build, 2 processes beside data generation on 6 threads) | 4,907,027,440 nodes in 1,194 s: **2.05 M nodes/s per process** | [derived] oracle-rates-a's nodes and start/end times |
| Crucial sites (static and deep value on opposite sides of the nearest bound) | 18.6% of 5,433 sampled sites, both strata; window gap alone recalls 0.30 (main) / 0.25 (quiescence) of crucial sites at 4% of nodes; the logistic gate 0.34 / 0.26 | [measured] measure/step1 daca926 §5.7 |
| Search counters in game (S512ppr2) | 0.538-0.543 evaluations per node; TT-eval hit rate main 47.5-52.1%; 1.20-1.21 plies walked per evaluation; 16.2-16.6 refreshes per 1,000 updates | [measured] X1, measure/step1 §5.7 (stats build 68c00b8) |
| Node time and its parts (S512r2, native, before C4) | 278 ns per node; accumulator update 48, output layer 40, refresh 7, other network 10 ns per node | [measured profile] docs/research/phase4-think-tank/phase-a-evidence.md §1.2 (perf-log 2026-11-06) |
| Node time, S512ppr2 (same architecture as S512ppr3) | about 298 ns per node | [derived] phase-b-specialists.md §2 "Common base" (278 / 1.04 / 0.895) |
| S512+X's speed (exposure computed at every evaluation) | 0.818 of S512r2's nps | [measured] DESIGN.md §5.4 "The speed gate"; sprt-log |
| Speed-to-Elo | 1.53 Elo per 1% nps (1.26-1.80); priced at 1.5 (decision 8) | [measured fit] phase-a-evidence.md; DESIGN.md §6 2026-11-07 |
| Reused evaluations among idea 60's gated depth-1 sites | 44% (bench, switch off) | [measured] idea60/extension 4f4ddf2 |

### 1.2 What changes between step 2 and step 3

- **The base.** Step 2 refined S512r2. S512ppr3 is the default now: S512+PP
  beat S512r2 by +46.09 at fixed nodes and +32.67 at STC, S512ppr2 and
  S512ppr3 added +20.11 and +7.12 at STC (docs/nets.md). S512+X was
  +25.67 against S512r2 at fixed nodes, so it is very likely weaker than
  S512ppr3 overall: the oracle's knowledge may not all be new to S512ppr3.
  Pre-check P0 (section 5) measures this offline before anything is built.
- **The refiner.** The oracle's refiner was a whole second network
  (architecture 6, 1,459,424 bytes) with its own accumulator, kept up to
  date at every computed evaluation. Step 3's refiner is a small trained
  head on the base's accumulator; it may hold less than S512+X did. The
  offline acceptance (section 3.8) scores it against the oracle's own
  offline score on the same sites, so "how much of the oracle it keeps" is
  read before any game.
- **Training.** S512+X was trained like any network (quiet positions,
  every position equal). The refiner is trained only on near-window sites
  of Fork's own searches, against deep labels: the signal the oracle used
  by accident is the refiner's target by design.

### 1.3 A preview of the target (not used to set anything)

From the crucial-point sites (daca926's data, ~/fork-measure/crucial/out;
S512ppr2's static evaluations, deep values at 1,000,000 nodes). These
sites come from SPRT games with UHO openings, which the data decisions
allow only as test data (DESIGN.md §5.3, decision 6), so they preview the
distribution and are **never** used to fit or select a constant; the cap
and every other choice are taken on the training split (section 3).
Recounted by this plan, mate and tablebase deep values excluded:

| Sites within 25 cp of the nearest bound | n | crucial | mean (deep - static) | abs residual p50 / p75 / p90 / p95 / p99 |
|---|---|---|---|---|
| Main search | 421 | 187 | +148 cp | 46 / 213 / 579 / 850 / 1,264 |
| Quiescence | 433 | 177 | +98 cp | 45 / 144 / 449 / 666 / 1,076 |
| Both | 854 | 364 | +123 cp | 45 / 183 / 478 / 807 / 1,175 |

Crucial share by window-gap band (strict opposite sides; daca926's rule
also counts a tie at the bound, so its totals are slightly higher):

| Band (cp) | 0-10 | 11-25 | 26-40 | 41-50 | 51-100 | over 100 |
|---|---|---|---|---|---|---|
| Main, computed | 40% (50) | 33% (76) | 20% (64) | 12% (42) | 13% (196) | 8% (811) |
| Main, reused from the TT | 43% (145) | 36% (169) | 28% (151) | 13% (92) | 16% (335) | 20% (509) |
| Quiescence, computed | 41% (165) | 30% (243) | 21% (242) | 24% (140) | 15% (557) | 11% (1,273) |

Two readings carry into the design. The residual is heavy-tailed and
strongly positive on average (the side to move's search finds gains the
static evaluation misses), so a refiner that learned mostly the mean would
behave like the bias-only control, which lost 14.56 Elo: the offline
acceptance must beat a constant shift (section 3.8). And reused
evaluations near the window are as often crucial as computed ones, while
in the main search they are 2.4 times as many (3.54% against 1.48% of
nodes): the gate's treatment of reused evaluations matters (section 2.6).

## 2. Architecture

### 2.1 The data flow at an evaluation site

1. The site obtains the base evaluation `b` as today (computed by
   S512ppr3, or reused from the TT entry).
2. If `b` came from a TT entry whose refined bit is set, `b` is already
   refined: it is used as it is (the sticky rule, 2.7). Done.
3. The gate tests `window_gap(b, alpha, beta) <= margin` for the site's
   stratum (2.6). If it does not fire, `b` is used. Done.
4. Otherwise (a computed evaluation; or a reused unrefined one when the
   reused-evaluation switch is on), the base accumulator at this ply is
   brought up to date if it is not (only for a reused evaluation; a
   computed one has it already), and the refiner runs: the on-demand
   features, the small layers, the two heads.
5. The value used is `v = clamp(b + clamp(delta, -C, C), -(EvalLimit - 1),
   EvalLimit - 1)`. The ply frame records `b`, `v`, `delta`, the confidence
   and a refined flag; the node's TT deposit stores `v` with the refined
   bit.

### 2.2 Inputs

**(i) The accumulator.** Both perspectives' 512 int16 sums of S512ppr3's
accumulator, each clipped to [0, 255] exactly as the base's output clips
them before squaring (accumulator.cpp `squared_sum`), side to move first,
packed as 1,024 unsigned bytes. Reasons: QA = 255 fits a byte exactly (the
B0 design kept that path open, DESIGN.md §5.3 "Quantization"); the clip is
work the base's output already does; and the bytes feed an 8-bit
multiply-add directly. **No slice:** every one of the 1,024 values is a
trained feature, and halving the input saves no more than halving the
first layer's width, which loses less (2.3). **Not squared:** the base's
square costs a multiply per value and breaks the byte packing; it is an
offline variant only if the plain clip trains clearly worse.

**(ii) Exposure (try 1).** The exposed pieces by XGR's rule, the code that
already exists for architectures 5 and 6 (`exposed_pieces` in
accumulator.cpp: a non-king piece attacked by a lower-class enemy piece, or
attacked and undefended, on set-wise attack maps). Encoded from the side
to move's view only (the refiner has one view): own or enemy (2) x pawn to
queen (5) x square (64, ranks flipped for Black and files flipped by the
side to move's frame, as the base's features) = **640 rows**, plus a
10-row factoriser (side x type) merged into the rows when saved, as the
S512+X trainer does (tools/train `s512x`). Each active row adds a column of
the first layer's width to its sums: no incremental state.

**(iii) The danger summary (variant; built and measured beside try 1, in
the candidate only by the rules of 4.5 and 5).** Counts read off the same
attack maps, for each side X (the side to move and the opponent), each
bucketed and one-hot encoded:

| Count | Buckets | Rows per side |
|---|---|---|
| King-zone pressure: squares of X's king zone (its square and neighbours) attacked by the other side | 0, 1, 2, 3, 4+ | 5 |
| Weak king-zone squares: of those, the ones only X's king defends | 0, 1, 2+ | 3 |
| Safe checks against X: squares from which a knight, bishop, rook or queen of the other side would check X's king, that such a piece attacks, and that X does not attack | 0, 1, 2+ | 3 |
| X's pieces pinned to X's king | 0, 1, 2+ | 3 |
| X's exposed pieces (the fork count the square rows do not sum) | 0, 1, 2, 3+ | 4 |

36 rows in all. Its cost over the exposure pass: the per-type attack sets
are kept apart instead of OR-ed (no extra lookups), plus two king-zone
lookups, three check-square lookups per king (knight, bishop, rook; the
queen is their union), one pin computation for the opponent
(`Position::pinned()` is cached for the side to move), and about twenty
AND and popcount operations: **15-30 ns [estimate]**.

**(iv) Threats (a later variant, only within the speed budget).** One row
per (attacking piece type, attacked piece type, attacked square, side):
6 x 5 x 64 x 2 = 3,840 rows plus a 60-row type-pair factoriser; about
5-25 active per position [estimate]. It needs per-piece attack sets kept
from the pass and a loop over attacked enemy pieces: **50-120 ns more
[estimate]**. Admitted only by the rule of 4.5.

**(v) Context rows.** The base's phase bucket (8 rows, the base's own
25-entry phase table) and the base evaluation itself, clamped to
[-1,000, 999] cp and cut into 16 bins of 125 cp (16 rows): the residual's
size and skew vary with the evaluation's level, and the refiner cannot
recompute the base's squared output from the clipped bytes.

**Never an input:** alpha, beta, the gap, the depth, the ply, the node
type, the TT entry. The correction must be a property of the position, so
that the value the TT stores means the same thing whatever window later
finds it, and so that training (position to label) and use agree. The
window decides only whether the refiner is consulted.

### 2.3 Layers and sizes

| Layer | Shape | Weights | Activation |
|---|---|---|---|
| L1 | 1,024 bytes -> 16, plus the active rows (exposure 640 (+10 merged), danger 36, context 24) | int8 dense part [16][1,024]; rows int16 [rows][16], expanded to int32 at load | clipped ReLU to [0, 255] |
| L2 | 16 -> 32 | int8 [32][16] | clipped ReLU to [0, 255] |
| Heads | 32 -> 2 (correction, confidence) | int16 [2][32] | none |

Parameters: 16,384 (L1 dense) + 10,240 (exposure rows) + 576 (danger) +
384 (context) + 16 + 512 + 32 + 64 + 2, about **28,200**; the file about
40 KB (rows stored as int16), about 61 KB in memory (rows expanded to
int32). Sizes: L1 is where the cost is (section 4), so it is as narrow as
the input's size allows; 16 int32 sums are one AVX-512 or two AVX2
registers, and 16 and 32 are the widths of Fork's own AF-S body (the
`af1`/`af2` layers of architecture 4), whose kernels and quantization are
the precedent. The speed gate (4.5) may replace L1's 16 by 8, or use a
sparse first layer that skips zero bytes (its benefit depends on how many
of S512ppr3's clipped values are zero at the gated sites: measurement M3).

### 2.4 Output, scaling and how the correction combines with the base

- Correction: `delta = clamp(y_delta * S / (255 * 64), -C, C)` cp, with
  S = 89, S512ppr3's own output scale (docs/nets.md), because the refiner
  is trained in the base's win-probability space (3.7).
- Combination: `v = clamp(b + delta, -(EvalLimit - 1), EvalLimit - 1)`.
  `v` never reaches the mate or tablebase bands (EvalLimit = 20,000,
  eval_scale.hpp; the bands start at 29,250).
- Confidence: the predicted absolute error of `v` in win probability, in
  thousandths (0-1,000). How it is trained and used: 3.7.
- The cap C is a constant stored in the refiner file (the trained function
  and the engine apply the same cap), chosen as in 3.7.

### 2.5 Quantization and integer arithmetic

- Dense weights int8 at a scale of 64, **bounded to [-64, 64], 1.0 in
  float, clipped in training** (amended, owner, 2026-11-08: two products of a
  byte, at most 255, and a weight are summed into an int16 by the 8-bit
  multiply-add, exactly only while 2 x 255 x |w| <= 32,767; at 127 a pair
  would reach 64,770 and saturate, so the bound keeps every path exact; the
  reader rejects larger dense weights); the input bytes are the clipped
  values at 255 per 1.0; so L1's sums are in units of 255 x 64 (QA x QB, bullet's convention
  that Fork keeps, credited in ORIGINALITY.md; not a tuned constant, so not
  screened: owner, 2026-10-28).
- Rows stored int16 at a scale of 64 and multiplied by 255 when loaded (a
  row is an input fixed at 1.0), so they add into the same int32 sums.
- Biases int32 at 255 x 64. Activations `clamp(sum >> 6, 0, 255)` as bytes.
- Overflow: L1's dense part is at most 1,024 x 255 x 64 = 16,711,680 in
  magnitude, far inside int32; the reader rejects a file whose bias plus
  dense bound plus its largest possible row sum (at most 30 exposure rows,
  as net_file.cpp's `MaxExposed`, plus the danger and context rows) can
  leave int32, as `sums_in_range` does for the base.
- SIMD: a scalar reference always compiled; AVX2 and AVX-512BW paths
  bit-identical to it, with equivalence tests on randomized and edge inputs
  (.claude/rules/simd.md); a VNNI path behind `FORK_VNNI` (amended,
  2026-11-08: TCEC's hardware supports AVX-512 VNNI, so the path can ship
  in the TCEC build; the AVX2 path is still what the GitHub SPRTs charge).

### 2.6 The gate

- **Sites:** step 1's two: negamax after the tablebase probe, where the
  static evaluation is set (not in check), and the quiescence stand-pat
  (not in check). Every depth: deeper main-search sites are rarely near
  the window (step 1: within 25 cp, depth 2 0.21%, depth 3-4 0.09%, 5-7
  0.01% of nodes) and cost almost nothing.
- **Rule:** the oracle's window gate unchanged (exp/oracle 92aa87c,
  src/search/refiner_gate.hpp): `window_gap` over the nearest finite bound,
  inclusive margins, -1 never fires, one margin per stratum.
- **Margins:** main 25, quiescence 25 cp, setting (b): the best measured
  (+41.01 at fixed nodes) at 6.97% of nodes. Setting (a) (25/10, 3.81%) is
  the speed fallback (4.5).
- **A wider quiescence margin (owner addition 1): 25 against 40 cp, by
  head-to-head at STC.** Why 40: step 1's quiescence calls per node rise
  almost linearly with the margin (2.30% at 10, 5.58% at 25, 8.92% at 40,
  11.06% at 50; recomputed here from step 1's histograms, 200k nodes), so
  40 is the next step of equal cost to (a) -> (b) (+3.34 points of nodes
  against +3.28), and its added band (26-40 cp) is still crucial 21% of the
  time against 30% for (a) -> (b)'s band (11-25) and 15% beyond 50 (1.3):
  about 0.7 of the previous step's yield per call. 50 cp would double the
  call rate with a band (41-50) that the preview cannot tell from noise
  (24% of 140 sites). The head-to-head runs at STC, not fixed nodes,
  because the wider margin costs time that fixed nodes do not charge.
  Declared value 25: 40 wins only by more than 0.5 e (DESIGN.md §6
  2026-11-07, design R settings).
- **SPSA (owner addition 1).** Both margins become parameter-table entries
  (`X(name, default, lowest, highest, step)`, src/tune/params.hpp) tuned in
  the final retune by scaling class (R24, §5.6 step 19; they are shallow,
  eval-dependent margins, so STC class), not in the early R14 pass (§5.6
  step 11), which is scheduled before the refiner can exist; if R14 runs
  later than that, they may join it. Range by the half-to-twice rule:
  12-50 cp for both (20-80 for quiescence if 40 is adopted). Step c by
  R14's rule (c about the 1-Elo half-width, calibrated from firing rates on
  a stats bench; phase-c-synthesis.md R14 "Rules"): provisionally c = 5 cp,
  the change that moves its stratum's call rate by about 20% at (b), since
  the rate is nearly proportional to the margin there (main 0.62 / 1.48 /
  2.87% of nodes at 10 / 25 / 50 cp; quiescence 2.30 / 5.58 / 11.06%);
  recalibrated once the speed measurement and the screen give an Elo per
  point of call rate. Updates clamped to 0.5c, integers by random rounding,
  as R14. The SPSA plays timed games, so it charges the cost of a wider
  margin by itself.
- **TT-reused evaluations (owner addition 2).** Two settings, one switch:
  - G0 (declared): only computed evaluations are refined; a reused
    evaluation is used as stored. With the refined bit, a reused value that
    was refined when stored is still refined (the sticky rule), so G0
    already covers every position the gate fired on while its entry lived.
  - G1 (switch, off): a reused evaluation whose bit is clear and on which
    the gate fires is refined too, after bringing the accumulator at that
    ply up to date (`advance_to`, exp/oracle's FeatureStack addition). Upper
    bound of its extra calls: the oracle's reused near-window rate, 3.25%
    of nodes at (b) (some of these were refined when stored and need no
    call: measurement M4 counts both kinds). Its extra cost per call: the
    accumulator walk, about 1.2 plies, 40-80 ns [derived: 48 ns per node of
    updates over 0.54-0.66 evaluations per node, part of it later reused by
    the children]. The case for it: in the main search, reused near-window
    evaluations are 2.4 times the computed ones and as often crucial (1.3).
    Decided by an STC head-to-head after the margin's (declared G0, the
    cheaper).
- **The logistic gate** (the gap plus simple features; daca926) is not in
  try 1: the decision of 2026-11-07 brings it in only once step 3's screens
  pass. It is a candidate for try 2 or a later head-to-head; GateSite
  already carries the facts it needs.

### 2.7 The TT, the frames, the improving flag and the correction tables

- **The TT's stored evaluation:** the value used, `v`, and a refined bit:
  bit 3 of the entry's flags byte, unused today (trans_table.hpp: bits 0-1
  the bound, bit 2 the TT-PV flag). The entry's self-check digest covers
  every non-key field, flags included, so a torn write still reads as a
  miss. No entry grows.
- **The sticky rule:** a stored refined value is used as it is wherever the
  entry is found, whatever the window. Because the correction depends on
  the position only, a position has at most two static values (base and
  refined), and within an entry's life it moves from the first to the
  second at most once, never back. That bounds the window-dependent
  inconsistency the owner flagged (idea 59, "Watch"): a re-search with
  another window (PVS, aspiration) reads the same value. It can still
  differ after the entry is replaced, as in step 2.
- **Frames:** the ply frame keeps `base_eval`, the used `static_eval`, the
  refined flag, `delta` and the confidence (one call per node at most; idea
  61 reads them, section 10).
- **The TT-refined pruning evaluation** (`UseTtEvalRefine`, the TT score's
  bound correcting the static evaluation for pruning) applies on top of the
  used value, unchanged.
- **The improving flag:** Fork has none (no such code in src/ at d89814f).
  If one is added later, it compares the frames' `base_eval` values (one
  estimator's trend, never a refined value against a base one), recorded
  now as the rule.
- **Correction tables:** Fork has none today; §5.6 step 16 (R34) plans
  non-pawn and continuation keys. The rule for when one arrives: base, then
  the table's correction, then the gate's test, then the refiner on the
  corrected value; the table learns from the used value; and the refiner
  is retrained after the table is adopted, since its input distribution
  changes.
- **Data generation:** if the refiner is adopted, the labeller policy's
  fresh PGO build of the promotion commit includes it, as any adopted
  change.

### 2.8 Network files, versioning, bench and the net hash

- **Two files** (recommended): the base stays `nets/s512ppr3.fnet` byte for
  byte, and the refiner is its own file (`nets/<name>.frnet`, embedded by
  CMake `FORK_REFINER_NET`, as the oracle did). Its 64-byte header: a magic
  of 8 bytes, the refiner format version (1), a refiner architecture id
  (1 exposure, 2 exposure + danger, 3 + threats), the base's payload
  checksum it was trained on (S512ppr3: 5861c1a319ca267b), L1 and L2
  widths, the head count, S, the cap C, the payload checksum (Fork's
  `net_checksum`), zero padding. The reader refuses a file whose base
  checksum differs from the embedded base's: a refiner read on another
  base's accumulator is meaningless. One file (a version-3 net file with an
  appended block) was considered and rejected: it changes the base's bytes
  and checksum, its parity file and its nets.md entry for no gain.
- **Bench:** with the refiner on (the adopted default), bench changes:
  a new `tests/bench-s512ppr3-<name>.ref` becomes the default's reference,
  and the commit message states nodes and signature (non-negotiable 3).
  The refiner switched off must give tests/bench-s512ppr3.ref exactly
  (a `refiner_off_bench` test, the oracle's precedent). `fork version`
  prints both checksums, and build_pair.sh's identity check and the shard
  results are extended to record both.
- **CI and tooling:** a refiner parity file (`tests/nnue/<name>.parity`:
  delta and confidence on the 446 parity positions, not gated) and netcheck
  in the `nets` job; quantization-loss limits set from the first healthy
  refiner (docs/nets.md's rule); docs/nets.md gets a refiner entry; the
  Control Center's check that nets.md names CMake's default net covers the
  refiner too; a fuzz target for the new reader (CLAUDE.md: a fuzz target
  for any new parser).

### 2.9 Alternatives considered

| Alternative | Why not first | When it comes back |
|---|---|---|
| Refiner lanes inside the accumulator (16 extra lanes per perspective, ignored by the base's output, updated with every move) | per call about 20 ns plus features instead of a 1,024-wide layer, but a fixed per-move cost (about +3% of the update's share, about +0.6% of node time [estimate]) and a changed base file: no longer "shares S512ppr3's accumulator" as the owner specified | the fallback if no dense or sparse L1 meets the 5% line (4.5); an owner decision |
| A slice of the accumulator | discards trained features arbitrarily; L1 width is the cleaner lever | no |
| S512+X itself with a lazily refreshed accumulator | the oracle's shape; its nps was never measured; a refresh per call costs many incremental updates (X1: 3.10 rows per update) | no |
| The logistic gate in try 1 | owner's 2026-11-07 decision: after the screens pass | try 2 or a head-to-head after adoption |

## 3. Training

### 3.1 Sources and the data policy

- **Positions:** Fork's own data-generation games only (viriformat parts;
  their openings are the Lichess CC0 book positions and their endings are
  Syzygy-adjudicated, as the training-data decisions allow; DESIGN.md
  §5.3, decisions 1 and 6). Never SPRT, screen or gauntlet games:
  UHO_Lichess_4852_v1.epd is test-only, and "positions from test-match
  games are never kept for training" (decision 6). So step 1's sites and
  the crucial-point sites (games of `s512ppr2-stc`) serve only as a
  report-only acceptance set and the preview of 1.3.
- **Labels:** Fork's own search only (strategy A+); positions within the
  tables get their value from the engine's own probes (3.3).
- **Which games:** a sealed generation-3 part (g3i or g3j, re-downloaded
  from Kaggle Datasets, which hold the only copy once a part's hash check
  passed, decision 3), or the running part's local shards before its seal.
  The positions and moves matter, not the stored scores.

### 3.2 The site logger

- **Build:** the stats build only (`FORK_SEARCH_STATS`, preset
  clang-stats), extending measure/step1's `FORK_EVAL_SITES` printer (FEN,
  window, static and TT-refined evaluation, depth, ply, parent evaluation,
  TT entry, last-move capture flag) with a gap filter: an environment
  variable `FORK_EVAL_SITES_GAP=80` keeps only sites whose window gap is at
  most 80 cp. Normal builds unchanged (the release presets' `.text` hash, as
  step 1 checked). Step 1's tooling is on measure/step1, not yet on
  phase-4; the step 3 branch takes it (merge or cherry-pick, the owner's
  call: open question 13).
- **Where:** the gate's two sites, computed and reused evaluations (tagged),
  not in check, with a finite nearest bound.
- **What is stored, per site:** the FEN, alpha, beta, the gap, the base
  evaluation as the engine computed it (an integer, also a parity check for
  the trainer, 3.6), the stratum, the reused flag, the TT entry's bound,
  depth and score, the depth, the ply, the parent's evaluation, the
  last-move capture flag, the game id and the position's index in it.
- **Sampling:** counter-based (deterministic) 1 in K per stratum, K set so
  a 200,000-node search yields about four sites per stratum (sites inside
  one search are strongly correlated; spreading over positions buys
  independent information); output buffered (X10's lesson: unbuffered rows
  made bench 17 times slower, measure/step1 §5.7 settings).
- **Why 80 cp:** the training set must cover the gate (25), the head-to-head
  candidate (40), the SPSA range (up to 50) and the weighting kernel's tail
  (3.7).
- **Replay:** game_replay.py over the chosen games, consecutive positions of
  a game with the in-game TT and histories (as X2 and X6), 200,000 nodes
  per move (step 1's STC proxy), Hash 16, Threads 1, Syzygy 3-4-5, two
  processes at below-normal priority through jobctl (kind `measure`).
- **Volume:** 150,000 positions (about 4,000 games x 40 positions) at 4 + 4
  sites each, about 1.2 M sites before deduplication; 3 x 10^10 nodes,
  about **2-3 hours** on 2 threads [derived: 2.05 M nodes/s per process,
  1.1].
- **Deduplication:** by Zobrist key over the whole set (the first kept); every
  key of a validation or test game is removed from the training split.

### 3.3 Deep labels

- **A pinned, bench-checked binary.** The labeller is S512ppr3's engine with
  the refiner off: built once (update.sh's TCEC settings, never `native`),
  copied to `~/fork-label/bin/<commit>/fork` (outside `build/`), its SHA-256
  written into every label file's header, and `fork bench` checked against
  tests/bench-s512ppr3.ref before the first and after the last label of
  every job; a mismatch voids the job. Never `build/clang-release`: the
  orchestrator reports that a rebuild of that directory once changed the
  binary under a labelling job and contaminated its labels (not recorded in
  a committed document; the rule stands either way). crucial_points.py's
  `deep` step checks bench once at its start, so the end check is new.
- **The search:** `go nodes N`, 1 thread, Hash 16, `ucinewgame` before each
  site, Syzygy 3-4-5 (crucial_points.py's protocol). The label is the last
  reported score, side to move's view, in cp.
- **Mates and tables:** a deep score in the mate or tablebase band
  (|score| >= 29,250, crucial_points.py's threshold) is left out of the
  regression and counted (the preview: 44 of 898 near-window sites, 4.9%);
  a tablebase draw (0) stays. The search already probes the tables in the
  main search, and the refiner's job is judgement in undecided positions.
- **cp, not WDL:** the label is a score; the loss compares it in win
  probability (3.7), which saturates large values the way the base's
  training does. No game-result term (the base's lambda 0.5 does not
  apply): a site is a node inside a search tree, and the game's result
  belongs to the game's own positions, not to it.
- **The budget N, by a pilot:** 3,000 validation sites labelled at 100k,
  300k and 1M nodes; N is the smallest budget whose label falls on the same
  side of the site's nearest bound as the 1M label for at least 90% of the
  gated sites and whose residual correlates with the 1M residual at 0.8 or
  more in win probability. Validation and test sites are always labelled
  at 1M (the crucial-point standard).

### 3.4 How much data, and its cost

About 28,200 parameters, 16,384 of them in L1's dense part. A start of
**1 M training sites** (about 36 per parameter; the exposure rows see about
1 M x 2 / 640, some 3,000 activations each, at an assumed two exposed
pieces per site [estimate]), with a learning curve on validation at 125k,
250k, 500k and 1M sites: grow to 2 M only if the last doubling raised the
validation net flip rate (3.8) by at least 10% of its value. A pinned
small model on 1 M noisy residuals is under-determined if the curve is
still rising steeply; the curve, not this estimate, decides.

Labelling cost, locally on 2 threads at 2.0 M nodes/s each (1.1; the
default build is somewhat faster than the oracle's, so this is
conservative):

| Job | Sites | Nodes per site | Thread-hours | Wall time on 2 threads |
|---|---|---|---|---|
| Budget pilot (100k + 300k + 1M) | 3,000 | 1.4 M | 0.6 | 0.3 h |
| Validation and test | 20,000 | 1 M | 2.8 | 1.4 h |
| Crucial-point set, relabelled by S512ppr3 (report only) | 5,433 | 1 M | 0.8 | 0.4 h |
| Training, if N = 100k | 1,000,000 | 100k | 13.9 | 6.9 h |
| Training, if N = 300k | 1,000,000 | 300k | 41.7 | **20.8 h** |
| Training, if N = 1M | 1,000,000 | 1M | 139 | 69 h (2.9 days) |
| Training grown to 2 M at 300k | 2,000,000 | 300k | 83 | 42 h |

Where: **locally** (the measurement lane, 2 threads beside data generation,
one heavy job at a time) is the plan. Kaggle's GPU sessions have 4 CPU
cores and 12-hour sessions (KB phase4-pipeline.md); whether CPU-only
sessions match, how fast their cores are, and whether Kaggle's terms permit
long engine searches are UNVERIFIED (a KB check before any use). GitHub
runners are not used: that lane runs one job at a time, and labelling
would hold up the SPRT queue.

### 3.5 Train, validation and test split

By game, with a CRC-32 of the game id (crucial_points.py's fold rule):
90% training, 10% validation (early stopping and every offline choice:
the weighting arm, the cap, the confidence rule, the learning curve). The
**test set** is 20,000 sites from a different sealed part's games, labelled
at 1M, used only for the acceptance numbers. The crucial-point set is
reported beside it and selects nothing.

### 3.6 Initialisation and the warm start

- **Nothing of the refiner is warm-startable on its first training:** its
  layers are new. The base is not trained at all: S512ppr3's float weights
  (R1-avg, item 8a's artifact, SHA-256 recorded) are loaded and frozen.
  The trainer's float base evaluation must match the logged integer one
  within S512ppr3's quantization loss (max 9.4, p99 7.5 cp; docs/nets.md),
  site by site: a check that the frozen base is the engine's base.
- **Initial values:** the correction head's weights and bias zero, so
  `delta = 0` and the refined evaluation equals the base exactly at step 0.
  **Validity check:** the weighted validation loss before the first update
  equals the base's own on the same sites within 1e-6 (as S512+PP's start
  with its link inputs at zero reproduced S512r2's loss within 1e-6). All
  row weights zero (each feature starts silent); L1 and L2 the trainer's
  seeded default; the confidence head's bias the training split's mean base
  error.
- **Schedule:** the from-scratch form (LR 0.001, AdamW, a tenfold drop at
  half the run, early stopping with patience 8 on the weighted validation
  loss), because the standard warm recipe (LR 0.0001; DESIGN.md §6
  2026-11-06) retrains a trained net. Two seeds per arm.
- **The warm recipe from the second refiner on:** every refiner retrain (a
  new base from item 8b on, or more labelled sites) starts from the
  previous refiner's float weights at LR 0.0001 with the tenfold drop, and
  checks its first loss against the previous refiner's within 1e-6 on an
  unchanged base, or reports the jump when the base changed.
- **Trainer:** fork-train (tools/train, on bullet's trainer crate) gains an
  architecture `refiner`, with AF-S's small layers as the precedent and
  S512+X's exposure inputs and factoriser reused. Whether bullet supports
  frozen tensors and per-sample loss weights was UNVERIFIED; fallbacks:
  the base's tensors at learning rate 0 in their own group, and weights by
  resampling (each site drawn with probability proportional to its weight,
  the same expected loss). **Settled from
  bullet's source at the pin** (da426a49, read 2026-11-08 in a temporary
  folder, deleted after; ORIGINALITY.md): (i) **frozen tensors: not exposed,
  but reachable exactly.** The model definition's backward lowering takes a
  set of frozen weights (no gradient), but the pinned run loop (`train`,
  `train_with_observer`) always passes an empty set and expects a gradient
  buffer for every weight. Instead, `detach()` on the base's outputs (the
  accumulator the refiner reads and the base evaluation; a copy with no
  gradient) leaves the base's weights an exact zero gradient ("weights with
  no path to the loss have zero gradient"), and `set_params_for_weight`
  gives them decay 0 and a clip range holding their values: the pinned
  AdamW update (weight x (1 - decay x lr); momentum and velocity from the
  gradient; step = momentum / (sqrt(velocity) + 1e-8); weight - lr x step,
  then the clip) then leaves each such weight bit for bit unchanged, its
  momentum, velocity and step staying 0. That is the first fallback in
  substance (learning rate 0 for the base), without a parameter group.
  (ii) **Per-sample loss weights: no built-in, but expressible.** The graph
  takes named per-sample dense inputs (fork-train's `target` is one) and
  multiplies same-size nodes elementwise, so a weight input multiplies
  each sample's squared error before the batch sum (gradients are averaged
  over the batch, so weights of mean 1 keep the loss's scale); resampling
  is not needed. That this product compiles for batched one-wide nodes is
  UNVERIFIED until the refiner architecture's first build (the parity
  chain); resampling stays the fallback if it does not. A converter and Fork's independent references
  (R-float, R-quant, R-int in tools/nnue) extend to the refiner, and the
  parity chain (trainer = R-float within tolerance, R-int = engine exactly)
  passes before any game, as for every network (DESIGN.md §5, "Step 0
  requirement").
- **Compute:** about 80 epochs of 1 M sites is 80 M samples against the 1.8
  B of a base retrain: well under one T4 GPU-hour per arm [estimate].

### 3.7 Loss, decision weighting, confidence, cap

- **Loss:** `L = sum_i w_i [sigmoid((b_i + delta_i) / S) - sigmoid(d_i / S)]^2
  / sum_i w_i`, with S = 89, d the deep label, and `delta_i` capped at +-C
  inside the graph, as the engine caps it. **Amended (owner, 2026-11-08):**
  the target is centred, its training-split mean subtracted (the section
  "Owner decision, 2026-11-08"). **The form (orchestrator, within the plan,
  2026-11-08):** mu = the training-weighted mean of (deep - base) in cp over
  the sites used (the weights of `deep_labels.py weights`); the target is
  `sigmoid((d_i - mu) / S)` with S = 89, S512ppr3's output scale
  (docs/nets.md, "S512ppr3": S = 89, matched to S512ppr2's mean |eval|);
  mu is not added back in the engine and its value is reported. The base
  sits in the trainer's graph, frozen: `detach()` on its outputs, decay 0
  and a clip range holding its weights (3.6, settled); its float weights
  are item 8a's R1-avg (weights.bin, SHA-256 02215858...c8b37ecc3),
  checked against the engine's net before use.
- **Decision weighting (owner addition 4; idea 48 applied):**
  `w_i = exp(-g_i^2 / (2 h^2))`, g_i the site's window gap, h = 25 cp (the
  gate's margin), normalised to mean 1. Idea 48's variance rule applies:
  `n_eff = (sum w)^2 / sum w^2` must stay at least half of n. Over gaps
  spread evenly on 0-80 cp it is about 0.55 n [derived: mean w 0.391, mean
  w^2 0.277]; if the logged spread gives less than 0.5 n, h grows to the
  smallest value that meets it. **Offline check:** two arms at equal data,
  weighted (declared, the owner's request) and plain; the weighted arm stays
  unless the plain one's validation net flips at the gate (3.8) are higher
  by more than the seed spread; n_eff reported. **Amended (owner,
  2026-11-08):** h = 25 cp at main-search sites and 17 cp at quiescence
  sites (the smallest whole h giving n_eff >= 0.5 n on the training split),
  and each stratum's total weight scaled to the refiner's call mix at gate
  (a), 44.1 : 55.9 (the labelling section, "The training mix").
- **Confidence (owner addition 3):** the second head predicts `e_i = |sigmoid(
  (b_i + delta_i) / S) - sigmoid(d_i / S)|`, trained on `w_i |e_i - c_i|`
  with `delta` held fixed (a second short run with everything else frozen,
  if the trainer cannot stop the gradient). **Use in step 3: U0, declared:
  the correction applied in full, the confidence computed, exported and
  counted but not read by the search.** Reason: the squared-loss correction
  is already the weighted conditional mean, which shrinks by itself where
  the refiner knows little; a further shrink pays only for decisions with
  unequal costs. Two variants are scored offline on validation: U1 skips
  the correction when the confidence is at least kappa times its size; U2
  scales it by `clamp(1 - c / tau, 0, 1)` (kappa, tau set on validation).
  One enters the candidate only if its validation net flips beat U0's by
  more than the seed spread; no separate game test in step 3. The
  confidence's real consumer is idea 61 (section 10).
- **The cap C (owner addition 5):** from the training split's sites within
  25 cp, the distribution of |deep - base| (mates excluded). Candidates its
  50th, 75th (declared) and 90th percentiles; the preview's values are 45,
  183 and 478 cp (1.3; never used to set it). Chosen on validation by the
  net flips at the gate's bound and at the depth-1 pruning thresholds
  (`prune_eval - RfpMargin >= beta`, RfpMargin 80; the futility value with
  FutilityOffset 100 and FutilityGrowth 70; computed offline from the
  logged window); the smaller one is kept unless a larger one wins by more
  than its error. Why a cap at all: any correction beyond the gap flips the
  gate's comparison already, so a larger one changes only how far the
  stored value moves the other thresholds (reverse futility, futility, the
  null move's surplus), and that is where a wrong large correction does its
  damage; the tail above the 75th percentile is mostly material won by
  force, which the next plies or quiescence find anyway. It is a search
  constant: its justification goes in the constants table and it goes
  through the originality-checker's constant screen before the commit
  that sets it.

### 3.8 Offline acceptance (declared before any training run)

On the **test set** (3.5), at the gate's margins (25 / 10: setting (a), the
owner's decision of 2026-11-08, "step 3 proceeds at gate setting (a)"; the
plan first said 25 / 25), per stratum
and together. Definitions: a gated site is **fixed** when the base and the
deep label lie on opposite sides of the nearest bound and the refined value
lies on the deep label's side; **broken** when the base was on the deep
label's side and the refined value is not; **net flips NF** = (fixed -
broken) / gated sites.

| Check | Line | Why |
|---|---|---|
| A1 validity | zero correction reproduces the base's loss within 1e-6 | the frozen base is the base |
| A2 NF | > 0, McNemar p < 0.01 on fixed against broken | a refiner that does not fix more decisions than it breaks has nothing to sell |
| A3 against a constant shift | NF above the NF of `delta = ` the training split's mean residual (capped), McNemar p < 0.01 | the offline analogue of the bias-only control, which lost 14.56 Elo |
| A4 against the oracle | q_off = NF(refiner over S512ppr3) / NF(S512+X over S512r2) on the same sites, both by R-int; **kill below 1/3** | the oracle's NF has a known game result (+41.01 at (b)); one third mirrors step 2's own kill line (one third of S512+X's gain). Caveat: the two bases differ, so q_off is a calibration, not an identity |
| A5 explained variance of the win-probability residual at gated sites | reported, with a game-bootstrap interval | the regression's own score |
| A6 the corrections | mean and abs mean at gated sites; the share at the cap (over 10% sends the cap back to 3.7) | catches a mean-shift refiner and a cap that binds too often |
| A7 the endgame check (900 positions), correction applied everywhere | reported; the standing default's target is at most 15 misjudged | the refiner must not break the base's endgames where it is consulted |
| A8 n_eff of the weighted arm | at least 0.5 n, of the closeness weights alone (owner, 2026-11-08) | idea 48's rule |
| Crucial-point set (SPRT games, relabelled) | NF reported only | test data by decision 6 |

**Amended (owner, 2026-11-08; the labelling section, "A8 and the
acceptance weighting"):** every check, the constant-shift baseline (A3)
included, uses deployment weighting: only the sites inside setting (a)'s
margins (main search 25 cp, quiescence 10 cp), equal within each kind,
times the call-mix factor (44.1 : 55.9). The training-objective weighting
(closeness x call mix) is reported beside it for diagnosis only. A8 judges
the n_eff of the closeness weights alone (training: 0.501 n, a pass); the
n_eff with the call-mix factors (0.468 n) is reported for information.

Kill at this stage: A2 or A3 fails, or q_off < 1/3. The result is recorded
in ideas.md and step 3 stops before any game.

## 4. Speed

### 4.1 The model

Per node, the time is `t_node + r x t_call` (plus G1's walks), so the nps
ratio is `1 / (1 + r x t_call / t_node)` and its price is 1.5 Elo per 1% of
nps lost (decision 8). r is the measured calls per node, which already
includes the 0.533-0.534 evaluations per node of the oracle's replays
(1.1): (a) 3.81%, (b) 6.97%, (main 25, quiescence 40) 10.40% [derived
from step 1: 1.48% + 8.92%]. t_node = 300 ns, S512ppr2's derived figure
on the local machine (1.1); the GitHub runners' t_node is longer (DRAM-
bound TT probes; phase-b-specialists.md), which lowers the refiner's share
there if its cost does not grow alike, and their v3 build has no AVX-512.

### 4.2 Per-call cost, by component (local Zen 4, native build)

| Component | Estimate | Basis |
|---|---|---|
| Gate test (paid at every computed evaluation, about 0.53 per node) | about 1 ns per evaluation, about 0.2% of node time | [estimate] two compares and a branch |
| Attack maps and the exposed set | 60-90 ns | [derived] S512+X's 0.818 ratio is +61 ns per node over 278 (`(1/0.818 - 1) x 278`), about 95-115 ns per evaluation at 0.54-0.66 evaluations per node, which includes its two perspectives' 512-wide row sums (about 20-30 ns [estimate]) |
| Danger summary on the same maps | 15-30 ns | [estimate] (2.2) |
| Clip and pack 1,024 values to bytes | 5-10 ns | [estimate] 64 AVX2 pack operations |
| L1 dense, 1,024 -> 16, AVX2 or AVX-512 without VNNI | 100-120 ns | [estimate, first principles] 16,384 byte products are 512 `maddubs` + 512 `madd` on AVX2, about 1,024 multiply operations over Zen 4's two multiply pipes, about 512 cycles at 4.7 GHz; Zen 4 runs 512-bit operations as two 256-bit halves, so AVX-512 is no faster here (pipe counts, clock and double-pumping as phase-b-specialists.md H1 states them, UNVERIFIED) |
| L1 dense with VNNI (not in the TCEC build for now) | 55-65 ns | [estimate] one `dpbusd` per 32 products |
| L1 dense at width 8 | 50-60 ns | [estimate] half of the above |
| L1 sparse (skip zero bytes), if at least 60% are zero | 40-70 ns | [estimate]; zero share unmeasured (M3) |
| Active rows (3-15 rows of 16 int32) | 3-8 ns | [estimate] |
| L2, heads, scaling | 10-15 ns | [estimate] about 600 products |
| G1 only: the accumulator walk for a reused evaluation | 40-80 ns | [derived] 48 ns per node of updates over 0.54-0.66 evaluations per node, 73-89 ns per walk, part of it reused by the children |

Assembled: exposure with L1 = 8 dense, or L1 = 16 sparse, about **140-160
ns**; exposure with L1 = 16 dense on AVX2, about **190-230 ns**; add 15-30
for the danger summary. These are estimates with wide error, and the
oracle's own nps (the pessimistic two-network figure) was never measured
(the A/B awaits a quiet machine, ideas.md idea 59).

### 4.3 Scenarios: nps ratio, loss and Elo price

Each cell: nps ratio / nps loss / price at 1.5 Elo per 1% [derived from
4.1's model, t_node = 300 ns]:

| t_call | (a) 25/10, r = 3.81% | (b) 25/25, r = 6.97% | 25/40, r = 10.40% | (b) + G1, 6.97% + 3.25% reused (+60 ns walk each) |
|---|---|---|---|---|
| 50 ns | 0.994 / 0.63% / 0.9 | 0.989 / 1.15% / 1.7 | 0.983 / 1.70% / 2.6 | 0.977 / 2.30% / 3.4 |
| 100 ns | 0.987 / 1.25% / 1.9 | 0.977 / 2.27% / 3.4 | 0.966 / 3.35% / 5.0 | 0.961 / 3.90% / 5.8 |
| 150 ns | 0.981 / 1.87% / 2.8 | 0.966 / 3.37% / 5.1 | 0.951 / 4.94% / 7.4 | 0.946 / 5.45% / 8.2 |
| 200 ns | 0.975 / 2.48% / 3.7 | 0.956 / 4.44% / 6.7 | 0.935 / 6.48% / 9.7 | 0.931 / 6.95% / 10.4 |
| 250 ns | 0.969 / 3.08% / 4.6 | 0.945 / 5.49% / 8.2 | 0.920 / 7.98% / 12.0 | 0.916 / 8.40% / 12.6 |
| 350 ns | 0.957 / 4.26% / 6.4 | 0.925 / 7.52% / 11.3 | 0.892 / 10.82% / 16.2 | 0.888 / 11.17% / 16.8 |

The per-call budget for each line [derived: `(1/line - 1) x 300 / r`]:

| Line | (a) | (b) | 25/40 | (b) + G1 |
|---|---|---|---|---|
| 3% loss (4.5 Elo) | 244 ns | **133 ns** | 89 ns | 72 ns |
| 5% loss (7.5 Elo) | 414 ns | 227 ns | 152 ns | 135 ns |

For scale: the oracle's (b) gained +41.01 at fixed nodes against a weaker
base. A trained refiner keeping half of that, +20, would net about +15 at
STC at the 3% line by the think tank's fit (STC about fixed-node gain
minus the speed price; phase-a-evidence.md); keeping a third, about +9.

### 4.4 The budget and the feature order (owner addition 6)

- **Design line: at most 3% nps lost at setting (b) with G0, so at most
  133 ns per call** on the local quiet machine; **hard line 5%** (227 ns)
  for any variant; the speed gate for new input types (0.90; DESIGN.md
  §5.4) stays the formal floor.
- **Order:** exposure first (try 1). The danger summary is built and timed
  beside it and enters only if (i) its measured cost keeps the call under
  the design line and (ii) it raises validation NF by at least 10%.
  **Threats** only if the measured cost of everything before them leaves
  room for their measured pass under the 133 ns line: the threat pass is
  estimated at 50-120 ns, so the rest would have to come in at about 13-83
  ns, and on the estimates above no shape does (the exposure pass alone is
  estimated at 60-90). So threats enter only if the measurements come in
  well under the estimates, and then only as a later variant, never in
  try 1.
- **If even the cheapest shape misses the 5% line:** setting (a) (its 3%
  budget is 244 ns), then the refiner lanes of 2.9 (an owner decision),
  else stop. *Replaced (owner, 2026-11-08):* faster exposure, then the
  8-wide entry layer, then VNNI; the lanes last and only with the owner's
  approval (the section "Owner decision, 2026-11-08").

### 4.5 What must be measured, and how

**No speed claim before measurement.** The build is measured on a quiet
machine (every other CPU job suspended, decision 13's seal windows) with
`bench/ab.py` (interleaved, identity-checked) and, for the SPRT
conditions, the runners' in-situ speed job (X3, §5.6 step 6; not built as
of this plan, so it is a dependency), before any number here is reported as
a result.

- **M1, the speed gate before any data work:** a zero-output refiner (the
  final shape, every weight zero, so `delta = 0`) leaves the tree exactly
  S512ppr3's (bench 14,149,617 / 1cb0717f040c294d) while paying the whole
  per-call cost: the identical-tree method the owner prefers (DESIGN.md
  §5.4), so interleaved bench rounds measure the cost alone. Variants: L1
  16 dense, 16 sparse, 8 dense; with and without the danger summary; G0
  and G1. Bench runs the gate at 25/25 (its call rate on bench is reported;
  the oracle's bench at 25/10 called at 5.2% of nodes, exp/oracle 0a40491).
  The shape for try 1 is the largest that meets the design line.
- **M2:** fork_micro cases for the exposure pass, the danger summary and
  the L1 kernel on the bench positions, to check 4.2's components.
- **M3:** the zero share of S512ppr3's clipped accumulator at gated sites
  (a stats-build counter), which decides whether a sparse L1 pays.
- **M4:** among reused evaluations on which the gate fires, the share
  already refined (a counter in the step 3 build), which gives G1's real
  call rate.

## 5. Tests and gates, in order

Each step's pass line and kill criterion is declared here, before any
result. The SPRT log and ideas.md record every result, failures included.

| # | Step | Lane | Pass | Kill |
|---|---|---|---|---|
| P0 | Pre-check, offline: on the crucial-point sites within 25 cp, NF of S512+X over S512ppr3 (both by R-int, crucial_points.py `seeds`), against NF of S512+X over S512r2; and (owner, 2026-11-08) the +123 cp mean of deep - static checked for sign and perspective, mate- and tablebase-adjacent scores and selection effects, before the pilot's labels are used | L, about 1 h | information | none: a low ratio lowers the prior (the oracle's gain may have been S512r2's weakness), reported to the owner before E1 |
| E1 | Build the gate, the TT bit, the refiner's inference with a zero-output file (2.1-2.8) | E | every check (full CI, bench parity with the refiner off, equivalence tests, no_alloc) | none |
| S1 | Speed gate, M1-M3 | L (quiet), G (X3) | the design line for some shape | every shape above 5% at (b) and at (a), and the lanes not approved: stop |
| D1 | Logger, replay, label pilot, labelling (3.2-3.4) | L | the pilot's 90% agreement at some budget | none at 1M (the budget then is 1M) |
| K1 | Training: two arms x two seeds (3.6-3.7) | K | A1 | A1 fails: fix the pipeline, not a try |
| O1 | Offline acceptance (3.8) | L | A2, A3 and q_off >= 1/3 | otherwise stop before games |
| F1 | Fixed-node screen: S512ppr3 + refiner against S512ppr3 alone, 1,600 games at 800,000 nodes per move (step 2's and the retrain gate's setup) | G, 1 stage | **Elo >= max(+8.6, P + 5)**, P = 1.5 x the nps loss in percent measured in the shard build (S1) | below the line: the try fails |
| H1 | Head-to-head at STC: quiescence margin 25 against 40 (refiner on in both) | G, 2 stages | declared 25 unless 40 wins by more than 0.5 e | none (a selection) |
| H2 | Head-to-head at STC: G0 against G1 (only if M4 shows G1 adds at least 1% of nodes in calls) | G, 2 stages | declared G0 unless G1 wins by more than 0.5 e | none |
| T1 | STC SPRT, the chosen setting against S512ppr3 alone (refiner off) | G, up to the cap | H1 accepted on **[0, 5]**, alpha = beta = 0.05 | H0: the try fails |
| T2 | LTC SPRT (40+0.4) | G, up to 6 LTC stages | H1 on [0, 5] | H0: not adopted |
| A | Adoption: the refiner on by default behind its switch (kept until the factorial removal round, R30), bench reference, nets.md entry | E | owner's go-ahead | |

**Why F1's line.** By the think tank's fit, an STC result is about the
fixed-node gain minus the speed price (phase-a-evidence.md, all eight
pairs), so a screen below P cannot be expected to pass at STC; +5 is the
owner's margin for a retrain's screen (DESIGN.md §6 2026-11-07), and +8.6
is step 2's kill line (a third of S512+X's +25.67), kept as a floor. At
1,600 games the screen's error is about +-10 Elo, so it filters, the SPRT
decides.

**Why network bounds for T1 and T2, not design R.** The candidate is a
trained network: networks keep [0, 5] with alpha = beta = 0.05 (DESIGN.md
§6 2026-11-07, decision 2: "networks keep [0, 5]"), while design R ([0, 6],
beta 0.20, the futility stop) is the standard for search features. Its
gate margins are search constants, and they are chosen as design R chooses
constants: by head-to-head (H1, H2). Design R's beta of 0.20 accepts
losing about a third of +3 nElo features; for a step that costs days of
engineering and labelling, a false rejection is the expensive error.

**Why LTC.** The refiner is an evaluation correction, the kind the
"Straight to LTC" list already names (correction history, T32; DESIGN.md
§5.2 "Long time controls"), and the owner asked for it. The speed price
"barely falls from STC to LTC" (decision 20), so an STC pass is not
expected to grow at LTC.

**The two-try limit** (decision 2; counted per time control, an LTC
confirmation of an STC pass is not a retry; every SPRT carries the idea id
59). Try 1: exposure, setting (b), G0 or H2's pick, U0. Try 2, if try 1
fails at F1 or T1: one variant declared in advance from the offline
numbers, the first that applies of (i) the danger summary, if it raised
validation NF by 10% or more; (ii) the logistic gate; (iii) setting (a),
if the speed price was the reason; (iv) twice the training data, if the
learning curve was still rising. After a second failure, step 3 closes and
ideas.md records both tries. Refiner retrains after an adoption follow the
retrain loop's rule (each on new data is its own idea), not this limit.

## 6. Place in §5.6's order, dependencies and lanes

- **Where:** after item 8a (done 2026-11-07) and after idea 60's tests,
  which come before idea 59's step 3 (ideas.md idea 60; DESIGN.md §6
  2026-11-07, ideas 48-60). Step 3 needs no GitHub time until F1, so E1,
  S1, D1, K1 and O1 run beside idea 60's head-to-head and SPRT and beside
  the rest of §5.6. If idea 60 is adopted first, the step 3 branch takes
  it, and F1, H1, H2, T1 and T2 run on that default.
- **Item 8b:** due when about 150 M new kept positions from a promoted
  labeller exist (§5.6 step 13). The refiner is bound to its base's
  checksum. If 8b promotes a new default before F1, the refiner is
  retrained on it (the warm recipe, 3.6) from the same labelled sites, the
  offline acceptance rerun, and the screen runs on the new pair; step 3
  never holds 8b back. The deep labels stay valid across that change (they
  are search values), except that their gaps were measured under the old
  base: a small shift, reported.
- **The GitHub queue:** one run at a time. Step 3 asks for 1 stage (F1),
  2-4 stages (H1, H2), an STC SPRT of typically 2-6 stages (cap 12.5 at
  20,000 games), and up to 6 LTC stages (24 stage-equivalents): about 10-35
  stage-equivalents, behind idea 60 and 8b's screen and SPRT.
- **Other dependencies:** measure/step1's tooling (the eval-site printer,
  crucial_points.py) and exp/oracle's gate code reach the step 3 branch; the
  design R tooling (tools/design-r) for the head-to-heads; the runners'
  in-situ speed job X3 (§5.6 step 6) for S1's shard-build ratio; a quiet
  window for S1's local A/B; R24 (step 19) for the margins' SPSA.

| Lane | Work | Estimate |
|---|---|---|
| E | gate, TT bit, refiner inference with SIMD paths and tests, file reader, fuzz target | 2-3 days |
| E | trainer architecture, converter, references, parity chain | 2 days |
| E | logger filter, label job's pinning and end check | 0.5 day |
| L | P0, S1 (quiet hours), replay (2-3 h), pilot (0.3 h), labels (7-69 h by N; 20.8 h at 300k), test labels (1.8 h) | 1-4 days of the measurement lane |
| K | two arms x two seeds, plus the confidence pass | under 4 T4 GPU-hours |
| G | F1, H1, H2, T1, T2 | 10-35 stage-equivalents |

## 7. New names, for the name screen (none introduced yet)

Each goes through the §8 procedure (a separate research subagent, the four
engines, exact and case- and separator-insensitive, match / no match only)
before first use. Names that exist on exp/oracle or measure/step1 are
marked: whether they were screened there is not recorded in a committed
document (UNVERIFIED), so they are screened again.

| Kind | Names |
|---|---|
| Files | `src/eval/nnue/refiner.hpp`, `src/eval/nnue/refiner.cpp`, `src/eval/nnue/refiner_file.hpp`, `src/eval/nnue/refiner_file.cpp`, `src/eval/nnue/danger_summary.hpp`, `src/eval/nnue/danger_summary.cpp`, `src/search/refiner_gate.hpp` (exp/oracle), `tests/test_refiner.cpp` (exp/oracle), `fuzz/fuzz_refiner_file.cpp`, `tools/nnue/refiner.py`, `tools/nnue/refiner.json`, `tools/measure/near_window_sites.py`, `tools/measure/deep_labels.py`, `tools/train/kaggle/refiner_train.py`, the extension `.frnet` |
| Types | `Refiner`, `RefinerFile`, `RefinerOutput`, `RefinerInputs`, `DangerSummary`, `RefinerGate` (exp/oracle), `GateSite` (exp/oracle), `GateKind` (exp/oracle), `RefinerTally` (exp/oracle) |
| Functions | `refine_at`, `refined_eval_at` (exp/oracle), `pack_clipped`, `exposure_rows`, `danger_summary`, `read_refiner_file`, `write_refiner_file`, `gate_fires` (exp/oracle), `window_gap` (measure/step1), `advance_to` (exp/oracle), `was_refined` |
| Members and switches | `base_eval`, `refined` (PlyFrame), `refined` (TtHit), `use_refiner`, `refine_reused` |
| Constants | `RefinerL1Width`, `RefinerL2Width`, `RefinerHeads`, `RefinerCap`, `RefinerMarginMain`, `RefinerMarginQuiesce`, `RefinerFormatVersion`, `RefinerMagic`, `RefinedFlag` |
| UCI options | `UseRefiner`, `RefinerMarginMain` (exp/oracle), `RefinerMarginQuiesce` (exp/oracle), `RefineReused`, `RefinerConfidenceMode` |
| CMake, environment, trainer | `FORK_REFINER_NET` (exp/oracle), `FORK_REFINER` (exp/oracle), `FORK_EVAL_SITES_GAP`, fork-train `--arch refiner`, the Kaggle kernel `fork-refiner` |

## 8. New constants and their intended justification

Search constants get a row in the "Search constants" table and the
originality-checker's constant screen before the commit that sets them
(non-negotiable 6); training and measurement settings get a recorded
reason.

| Constant | Proposed | Intended justification | Screen |
|---|---|---|---|
| Main margin | 25 cp | step 2's measured setting (b), +41.01 at fixed nodes; step 1's distribution | yes |
| Quiescence margin | 25 cp; candidate 40 | (b); 40 as the next equal-cost step (2.6), chosen by H1 | yes |
| Margins' SPSA range and step | 12-50 cp, c = 5, update clamp 2.5 | the half-to-twice rule; R14's c rule with step 1's rates (2.6) | yes |
| Correction cap C | the 75th percentile of |deep - base| at near-window training sites (preview 183 cp), against the 50th and 90th | validation net flips at the gate and the depth-1 thresholds (3.7) | yes |
| Confidence parameters kappa, tau | only if U1 or U2 is chosen | validation net flips (3.7) | yes, if used |
| L1 width 16, L2 width 32, 2 heads | | cost (section 4) and Fork's AF-S precedent; S1 may set L1 to 8 | yes |
| Danger buckets (2.2) | as tabled | reasoning: small counts carry the tactic, the tail is rare | yes |
| Exposure rule | XGR's, as in Fork's existing code | already Fork's (architectures 5 and 6) | already screened with XGR (UNVERIFIED: check the record) |
| Context rows | 8 phase buckets (the base's), 16 evaluation bins of 125 cp over [-1,000, 999] | the base's own table; bins covering the near-window range coarsely | yes |
| Weight scale 64, activation 255 | bullet's QA / QB convention | owner, 2026-10-28 | no (convention) |
| Logging margin | 80 cp | covers 25, 40, the SPSA range and the kernel's tail | training setting |
| Weight bandwidth h | 25 cp | the gate's margin; n_eff at least 0.5 n | training setting |
| Weight bandwidth h, amended (owner, 2026-11-08) | main search 25 cp, quiescence 17 cp | 17: the smallest whole h giving n_eff >= 0.5 n on the training split (the window, measured) | training setting |
| Stratum mix of the weights (owner, 2026-11-08) | 44.1% main search, 55.9% quiescence | the oracle's in-game call rates at (a), 1.68% and 2.13% of nodes (1.1) | training setting |
| Label budget N | the pilot's pick of 100k, 300k, 1M | 90% side agreement with 1M (3.3) | measurement setting |
| Sampling 1 in K | about 4 sites per stratum per search | independence over volume (3.2) | measurement setting |
| Split | 90 / 10 by CRC-32 of the game id; a separate test part | crucial_points.py's fold rule | setting |

## 9. Risks

| Risk | What could happen | Mitigation |
|---|---|---|
| The oracle's gain does not transfer | S512+X's corrections helped S512r2; S512ppr3 may already know much of it, and a small head may hold less | P0 before building; q_off against the oracle (A4); F1 |
| Mean-shift refiner | the residual is heavily skewed (mean +123 cp near the window, 1.3); a refiner that mostly adds its mean acts like the bias-only control (-14.56) | A3 (beat a constant shift), A6, the cap |
| Quiescence double counting | the target includes captures quiescence would search; a refined stand-pat may cut before searching them | the cap; per-stratum acceptance; the quiescence margin can be -1 (off) as a fallback setting |
| TT inconsistency | a position's static value depends on the window it was first gated in | a position-only correction, the stored value used, the sticky refined bit (2.7); the minimax tests run with the refiner off (as the oracle's did) |
| Search instability | fail-high then fail-low on a re-search with another window | the sticky rule; the correction is bounded by C; counted in the stats build (re-search counts with and without the refiner) |
| Speed worse than estimated | the attack pass or L1 cost more; the runners differ | S1 first, before any data work; shapes and fallbacks (4.4) |
| Data leakage | SPRT or UHO positions in training; validation games in training | the source rule (3.1); split by game; key dedup across splits |
| Label contamination | the labelling binary changes mid-job | the pinned copy, SHA-256 in each file, bench before and after (3.3) |
| Base change mid-step | 8b promotes a new default | the checksum binding; the warm retrain on the same sites (6) |
| Interactions | idea 60 (the same depth-1 sites), later correction tables (R34), SPSA (R24) | idea 60 decided first; the ordering rule for tables (2.7); the margins tuned in R24 with the refiner on |
| PGO and AVX-512 paths | a path no test reaches, or a profile without the refiner | bench exercises the gate (the PGO driver), scalar = SIMD tests on every preset, VNNI only behind FORK_VNNI |
| TCEC build | CMake 3.22 floor, libstdc++ 11's C++20, Ubuntu 22.04's compilers | the full check includes TCEC's four compilers; the refiner file embedded through the existing CMake path |
| Phase 6 | the TT flag under threads | the flag is inside the digested entry; the threaded suites under TSan |

## 10. After step 3

- **The retrain loop gains a refiner step.** Every base retrain (8b, 8c,
  ...) changes the accumulator the refiner reads, so each promoted base
  needs a refiner retrained on it (the warm recipe, the same or refreshed
  labelled sites, the offline acceptance, a fixed-node screen of the pair)
  before the pair ships. New sites are logged and labelled at each base
  change if the learning curve calls for more.
- **Idea 61, boundary-gated decisions** (owner, 2026-11-08; plan only,
  after the refiner exists): refiner-checked pruning near a prune's
  threshold; quiescence checks only near the window; near-window deep
  labelling for training data; later a gated move scorer (idea 54). Each is
  measured and SPRT-tested on its own after the refiner exists. Step 3 is
  built so as not to preclude them, with these interfaces:
  1. a call independent of the gate: `refine_at(ply)` returns the
     correction and the confidence for the position at that ply, bringing
     the accumulator up to date on demand, so a prune site can consult the
     refiner against its own threshold;
  2. a per-ply memo (the frame's base value, used value, refined flag,
     correction and confidence), so a later decision at the same node
     never calls twice;
  3. the gate as a predicate over a site with an arbitrary threshold and a
     margin per decision kind (GateKind is already extensible);
  4. the TT's refined bit, so a decision at a TT-hit node knows whether the
     stored value is refined;
  5. the packed clipped accumulator bytes produced once per node and
     readable by a second head (idea 54's move scorer);
  6. the site logger and the pinned deep-label job as standalone tools
     whose records (position, gap, base value, deep label) can feed the
     base network's trainer too (part 3);
  7. the confidence in a fixed unit (thousandths of win probability) and
     the tally per call kind (main, quiescence, each prune kind) in the
     `info string refiner` line.
- **Publication plan** (owner, 2026-11-07): only if T1 and T2 pass, the
  reproduction guide in docs/research/boundary-refiner/, then the owner's
  go-ahead for anything outside the repository, placed in the lazy and
  two-tier evaluation family as the prior-art search advises (idea 59's
  literature line).

## 11. Open questions for the owner, each with a recommendation

1. **Run P0 first?** The offline check of whether S512+X still corrects
   S512ppr3 near the window, about an hour of the measurement lane.
   *Recommendation: yes;* it informs, it does not kill.
2. **S1 before data work, with the zero-output refiner?** *Yes:* speed is
   the crux the idea names, and the identical-tree method prices it before
   any labelling hour is spent.
3. **The speed lines:** 3% (133 ns per call at (b)) as the design line and
   5% as the hard line. *Recommendation: as stated;* setting (a) and the
   refiner lanes are the fallbacks, the lanes only by your decision since
   they change the base file.
4. **Where to label:** locally on 2 threads (about 21 hours at 300k nodes
   for 1 M sites), or Kaggle CPU after a KB check of its cores and terms.
   *Recommendation: locally*, with Kaggle only if the pilot picks 1M nodes.
5. **Target:** `deep - base` (yours), or a variant that removes what
   quiescence would find? *Recommendation: yours*, with the cap and the
   per-stratum acceptance as the guard; the variant recorded in ideas.md.
6. **Confidence use:** U0 (exported, unused by step 3's search) declared,
   U1 or U2 only on an offline win. *Recommendation: U0;* the confidence's
   first real use is idea 61.
7. **G1 (refining reused evaluations):** behind a switch, decided by an STC
   head-to-head only if M4 shows it adds at least 1% of nodes in calls.
   *Recommendation: as stated.*
8. **Wider quiescence margin: 40 cp** as the head-to-head's candidate
   (rather than 50). *Recommendation: 40* (2.6).
9. **SPRT bounds: network [0, 5] at alpha = beta = 0.05**, with the margins
   chosen by design R's head-to-heads. *Recommendation: as stated.*
10. **Two files**, the refiner bound to its base by checksum.
    *Recommendation: two files.*
11. **Base during step 3:** S512ppr3, retrained on a new default if 8b
    promotes one before F1; step 3 never delays 8b. *Recommendation: as
    stated.*
12. **Try 1's features:** exposure only (your order), the danger summary
    built and timed beside it for try 2 or a later variant.
    *Recommendation: as stated.*
13. **The step 1 and oracle code** (measure/step1's tooling, exp/oracle's
    gate) on the step 3 branch: merge measure/step1 into phase-4 first, or
    cherry-pick? *Recommendation: merge measure/step1 into phase-4 (it is
    measurement-only code with the default build's `.text` unchanged), and
    cherry-pick only the gate and the FeatureStack addition from exp/oracle
    (not its two-network code).*

## 12. Sources

- docs/ideas.md ideas 48, 54, 59, 60 and 61 (phase-4 d89814f, 0e99c31,
  e389204); idea 60's branch idea60/extension (4f4ddf2).
- docs/DESIGN.md §5.2 (Testing setup, Long time controls, the streamlined
  standard), §5.3 (training-data decisions; B0's quantization), §5.4 (the
  speed gate), §5.6 (the order), §6 (2026-11-06 and 2026-11-07 entries),
  §7, §8.
- measure/step1 DESIGN.md §5.7 (b17e089: step 1; daca926: the crucial
  points; 68c00b8: X1); tools/measure/crucial_points.py there.
- exp/oracle DESIGN.md §5.7 and its commits 0a40491 (C1, the oracle build),
  56dacaf (C2, the base), d5bb138 (C3, the test), 92aa87c (C4, the
  controls); src/search/refiner_gate.hpp there.
- ~/fork-jobs/jobs/oracle-rates-a.json, oracle-rates-b.json,
  oracle-rates-random.json and their logs (the logs hold only progress
  lines; the rates come from the replay records in
  ~/fork-measure/i59/oracle-*-800k, summed by the oracle session's
  rates_report.py, rerun read-only for this plan).
- ~/fork-measure/i59/n200k (step 1's per-search histograms) and
  ~/fork-measure/crucial/out (sites.jsonl, deep.tsv): recounted read-only
  for 1.3 and 2.6.
- docs/research/phase4-think-tank/phase-a-evidence.md (§1.2 profile, the
  speed-to-Elo fit), phase-b-specialists.md (§2 common base, H1's
  arithmetic), phase-c-synthesis.md (R14).
- docs/research/idea52/report.md (deep labels at 1M nodes, the committee
  check).
- docs/nets.md (S512ppr3: S = 89, checksum 5861c1a319ca267b, quantization
  loss); src/eval/nnue (accumulator, net_file, net_shape),
  src/search/searcher.cpp and trans_table.hpp at d89814f.
