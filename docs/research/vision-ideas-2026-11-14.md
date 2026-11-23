# What else Fork's network could see: four lenses, ranked (read-only research, 2026-11-14)

Owner's order (2026-11-14, ~11:30 PM EST): propose new things for the network to see through four lenses (shogi NNUE,
classical chess theory, the Lichess puzzle-theme taxonomy, KataGo/Go engines), 3-4 ideas per lens, ranked by
expected Elo per cost, best three overall. Read-only session: nothing was built, run, trained, edited or committed.
Clean room: no engine source was opened by any lens agent (each lens's statement is in its appendix).

**Every Elo, chance, speed ratio and cost below is an estimate (est.) unless it cites a Fork measurement.** EU = one
engineering day or 10 GPU-hours. Speed price (Fork's): a candidate at speed ratio r needs about −118·log2(r) Elo at
fixed nodes to break even (r 0.99 → +1.7; 0.98 → +3.4; 0.975 → +4.3; 0.95 → +8.7; 0.93 → +12.4).

How it was made: four research agents, one per lens, each from the same brief (Fork's inputs, the cost lesson,
the in-flight work: idea 178, d_lite/b2 on r3kr1, the sparse int8 head). Their full sections are Appendices A-D,
unedited. This front part is the coordinator's synthesis: it merges overlapping ideas across lenses, and where two
lenses priced the same idea differently it says so.

---

## 1. The three cross-lens findings

1. **The residual kill line has never been calibrated, and three lenses found this independently** (lens 1's
   "decision for the owner", lens 2's L2-4, lens 3's F0). Idea 175's rule kills a state family whose share of the
   net's held-out residual is under 0.5%. But no input known to win has been measured with that tool. E10: the pawn
   links cut the loss by only 0.06% yet gained +32.7 at STC (+46.09 at fixed nodes). If a winner reads under 0.5%,
   the line could have killed Fork's best input, and idea 175's kill (0.006%) means less than it seemed. This is
   cheap to settle (CPU only, about 1 EU) and it gates most of the input ideas below, so it comes first (section 2).
2. **What a single SCReLU layer can and cannot form** (lenses 2 and 3, the same argument from different starts).
   Each column is a clipped square of a weighted sum, so the net forms pair relations (a piece with a pawn pattern,
   a piece attacked by a pawn) and low-rank structure, but not relations through empty squares (lines, pins,
   x-rays), negations ("no defender") or counts (attackers vs defenders). Most of classical theory (outposts, holes,
   bad bishop, 7th rank, space) is pair/low-rank, which fits idea 175's null. What remains is threat-like, which
   fits the threat inputs' fixed-node gains (+17.6 x_lower, +25.7 the full exposure plane) and their speed losses.
   A testable prediction (lens 3): x_lower's gain comes mostly from **slider** attackers, not pawn/knight ones.
3. **Head routing is nearly free speed and nobody has tested it** (lens 1's progress router and wing-class heads,
   lens 4's self-routed heads). Choosing which of the 8 heads runs costs no accumulator rows. Shogi's progress
   router gained +30.72 ± 12.10 in a tanuki- SPRT (against king-position buckets, so most of it won't transfer to
   chess, where material phase already tracks progress). One frozen-body head refit on CPU decides all three
   routings. Caution: idea 180 (rescaling heads by phase/queen state) measured zero, and idea 82's refit method is
   the probe.

## 2. Step 0: one calibrated CPU pass (about 1.5 EU, no GPU, no engine change)

Merges lens 2's L2-4, lens 3's F0 and lens 1's CPU pass. Idea 175's held-out ridge study (state_rows_study.py's
design) on the g4c 600 k and g4s2-val sets, against r3kr1 (and r8brft1 for comparability):
- **(a) Calibrate the line** on families already measured in games: x_lower's state and the full exposure plane
  (mover only and opponent only); the 608 pawn links on S512r2 if the loader can read it (UNVERIFIED). Set the kill
  line from their shares (for example half the smaller winner's share); if both clear 0.5%, idea 175's line stands.
- **(b) The order test:** "attacked by a cheaper pawn or knight" vs "attacked by a cheaper slider". If the slider
  half doesn't carry x_lower's share, lens 3's premise fails and its row ideas stop.
- **(c) The panel**, each by square, pooled and by output bucket: pins (absolute and to the queen), the opponent's
  next-move fork squares and discovery candidates, under-defended mover pieces, the file-line contact state, the
  blockade occupant, loose/overprotected bits, the KK pair, captured-material ordinals, trapped pieces and the back
  rank; plus two predicted-null controls (the absolute 7th, the bad bishop) that test the filter itself.
- **(d) The head-routing refit:** r3kr1's body frozen, heads refit under phase (control), learned linear progress,
  phase × kings' wings, and phase × one self-chosen hidden column; held-out loss and a quick fixed-node screen for
  any routing that beats phase.

Deciding readings: the calibrated line rules each family in or out; (b) decides lens 3; (d) decides lens 1's L1-1
and L1-2(b) and lens 4's self-routed heads. Interaction with in-flight work: idea 178's own falsifier 1 is relative
(mover's share against the opponent's), so it doesn't need the calibration; but its pin and attack-balance
extensions (L3-1, L3-3, L2-3) share its 64-column block and are decided here.

## 3. The best three overall

| | Idea (merged) | Lenses | Form | Speed (est.) | Elo (est.) / chance | Kill cost | Elo per EU (est.) |
|---|---|---|---|---|---|---|---|
| **1** | **Routed heads**: progress score, kings' wings, or a self-chosen column picks among the heads | L1-1, L1-2(b), L4-4 | head index only | about 1.00 | +3 / 30% (progress); +2 / 15% (self-routed) | 1 EU, CPU (step 0 d) | 0.30 |
| **2** | **Reply-square and square-fate auxiliary targets**: training-only heads predict the next move's and the reply's squares, and which side holds each square H plies later | L4-1, L4-2 | training only | 1.00 (no inference cost) | +3 / 25%, +2 / 20% | about 3 EU (a target carrier in the loader, UNVERIFIED ~1.5 EU, plus a three-arm fine-tune) | 0.25, +0.5 marginal for the second |
| **3** | **Pinned-piece rows in idea 178's liabilities block** | L3-1, L4-3 | extra rows in the 64-column block | 0.975-0.985 | +4 to +10 FN, 0 to +5 STC / 25% | step 0 (c), then a zero-weight prototype on 178's branch | 0.4 (lens 3) vs 0.05 (lens 4) |

Why these three: (1) costs no speed and is decided by one CPU run; (2) asks for threat knowledge, the one kind
Fork has measured as worth +17 to +26 at fixed nodes, at no inference price (risk: Fork's data-rich supervised
regime may not be where auxiliary targets pay: E5, E10); (3) is the one motif a single layer provably can't form,
its finder (`pinned()`) already runs for legality, it covers a known blind spot (Fork's SEE counts a pinned piece as
a defender), and it shares 178's block, so it costs little once 178 exists. The two lenses' prices for (3) differ
because lens 4 priced 640 full-width rows across both sides, lens 3 the mover's half in 178's 64-column block; the
block form is the one to build, and lens 4's low prior (idea 175's null) is exactly what step 0 tests.

Runner-up: **the KK row** (L1-2(a): 2,048 king-pair rows shared across regions, changing only on king moves; it
restores the exact king-against-king conjunction that four coarse regions lose, the cheap path M8 didn't find;
0.98-0.99, +4 / 25% with the wing heads, 0.22 Elo/EU).

## 4. Every idea, merged and ranked by expected Elo per EU

| Rank | Idea | Lens | Form | Speed (est.) | Central Elo (est.) | Chance | Kill (EU) | Elo/EU (est.) | Gate |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Calibrated residual pass + head refit (step 0) | L1, L2-4, L3-F0 | CPU study | n/a | enabler | n/a | 1.5 | decides ~20 EU | none |
| 1 | Routed heads (progress / wings / self-chosen) | L1-1, L1-2b, L4-4 | head index | ~1.00 | +2 to +3 | 15-30% | 1 | 0.12-0.30 | step 0 (d) |
| 2 | Reply-square + square-fate auxiliary targets | L4-1, L4-2 | training only | 1.00 | +3, +2 | 25%, 20% | 3 | 0.25 (+0.5 marginal) | the carrier |
| 3 | Pinned-piece rows in 178's block | L3-1, L4-3 | rows (block) | 0.975-0.985 | +4 to +10 FN | 25% | 0.5 + 178 | 0.05-0.4 | step 0 (b, c); idea 178 |
| 4 | KK row (king pair) | L1-2a | 2,048 rows, king moves only | 0.98-0.99 | +4 (with wings) | 25% | 1.5 | 0.22 | step 0 (c) |
| 5 | Defence surplus / attack-balance class (loose, overprotected, attacked twice defended once) | L2-3, L3-3 | rows on 178's L-exact | 0.93-0.95 total | +2 | 15% | 0.2 | 0.10 if 178's exact cut is built, else 0 | idea 178 L-exact |
| 6 | Captured-material ordinals | L1-4 | ~38 rows, captures only | 0.97-0.99 | +2 | 15% | 0.8 | 0.09 | step 0 (c) |
| 7 | File-line contact state for rooks and queens | L2-1 | 768 rows (block) | 0.975-0.99 | +2 | 20% | 0.3 | 0.08 | step 0 (c) |
| 8 | King-zone square-state lane (occupant × attack counts) | L1-3 | output-layer lane | 0.90-0.93 | +4 | 12% | 1.5 | 0.07 (0.2 if b2/d_lite's finder is paid) | b2 or d_lite adopted |
| 9 | Next-move double-threat counts (fork squares, pawn-push forks, discovery candidates) | L3-2 | 6 values into d_lite's vector | 0.97-0.98 | 0 to +3 | 20% | in step 0 | ~0.06 | step 0 (c); d_lite |
| 10 | Blockade occupant of passed pawns | L2-2 | 384 rows beside the links | 0.985-0.995 | +1.5 | 15% | 0.2 | 0.06 | step 0 (c) |
| 11 | Trapped pieces and back rank | L3-4 | counts with d_mob | ~0.955 (with d_mob) | small | 10% | in step 0 | low | step 0 (c); back rank expected null |

Ruled out by the lenses (with Fork's or the field's evidence): HalfKPE9-style attack-count row choices (states flip
on most moves: 2 row operations per flip, ~28 MB table); all piece pairs (85 vs 480 knps in shogi); mobility inputs
(shogi −47 to −155 Elo at 0.76 nps, like Fork's E4/E10); general x-ray rows (Coda gained by removing them, per
Fork's survey records); KataGo's literal pooled-bias layer (0.85-0.90); the classical pair/low-rank concepts
(outposts, holes, bad bishop, 7th rank, space: the net forms them; tested only as step 0's null controls).

## 5. Decisions for the owner

1. **Run step 0 first** (about 1.5 EU CPU, no GPU, no engine change; at low priority beside data generation). It
   recalibrates idea 175's kill line, so if the winners read far under 0.5%, idea 175's kill should be re-read
   against the new line (your call) before more state ideas are killed by it.
2. **The Lichess puzzle database** (CC0, 6,193,530 puzzles, updated 2026-11-11) as a motif-tagged diagnostic set
   (Fork's static eval vs its own search per theme)? Its positions come from human games, but Stockfish selected and
   solved the puzzles and a program tagged them, so non-negotiable 6 bars training on it; whether even diagnostic use
   is allowed is yours to decide (lens 3; UNVERIFIED as permissible).
3. **The target carrier for idea 2** (the loader passes later moves of the game to the trainer: the current decoder
   change carries only the halfmove clock and castling rights in 3 spare bytes). Approve its design when step 0 is
   in, or now if you want the auxiliary-target arm to run in parallel.
4. **Names and constants:** every name and count in this file is a placeholder, none screened. Lens 1 flags that
   "24 king-zone squares" and "attack counts capped at 2" echo a published shogi design (tttak's) and must be
   screened as such.

## 6. Sources and clean room

Each appendix carries its lens's sources table (title, author, URL, date opened) and clean-room statement. In short:
- Lens 1 (15 sources): shogi developer blogs (nodchip's tanuki- blog), YaneuraOu's release-note prose and wiki
  changelog, a note.com post, Gikou's and Nasu's (2018) appeal PDFs, a store listing. Source-file and code-PR links
  stayed closed; one fact rests on search-result prose (UNVERIFIED).
- Lens 2: Capablanca, *Chess Fundamentals* (Project Gutenberg #33870); Nimzowitsch, *My System* (1930 Hereford
  translation, Part I chs 2-4, Wikisource); Lasker, *Common Sense in Chess* (archive.org; *Lasker's Manual of Chess*
  was not reachable); six Chess Programming Wiki pages; Wikipedia. Quotes came through fetch summaries (UNVERIFIED).
- Lens 3: lichess.org/training/themes and database.lichess.org (prose only; the puzzle tagger's code was not opened);
  Fork's own docs and source.
- Lens 4: David Wu, "Accelerating Self-Play Learning in Go" (arXiv 1902.10565, via summarising fetches: numbers
  UNVERIFIED); KataGo's methods document (formulas only); Leela Zero's README (prose); the AlphaGo Zero paper (PDF
  not readable here: its claim is from memory, UNVERIFIED).
- Fork's own files: docs/research (bakeoff-r3, network-survey-2026-11, network-novelty-2026-11-14, novel-ideas,
  idea175-screens), docs/ideas.md, the plans folder's novelty files, src/ (read only).

---


# Appendix A: lens1-shogi.md (the lens agent's section, unedited)

# Lens 1: Shogi NNUE (read-only research, 2026-11-14)

**Status.** Research only. Nothing was built, run, edited or committed. Every Elo and nps figure that Fork did not
measure is marked (est.) or is quoted from a shogi source and labelled with that source. Names are placeholders and
none has been screened. Japanese sources were read through a summarising fetch tool and translated. Where I give a
quote, it is the fetch tool's quotation.

## What shogi tried, and where it stands (the evidence used below)

| # | Shogi finding | Source |
|---|---|---|
| S1 | **Progress-routed layer stacks.** tanuki- replaced *king-position* bucket selection with buckets picked by **progress** (進行度: a 0.0-1.0 estimate of how far the game has gone, "estimated with logistic regression, as Gekisashi and Gikou did"), mapped to 8 buckets. Self-play at 8+0.08 s: **+30.72 ± 12.10 Elo** (1608-1341-79, SPRT). Validation loss 0.0123 to 0.0122. The author's reading: progress "groups similar positions into the same bucket". | nodchip blog, 2026-02-04 (B3) |
| S2 | YaneuraOu added progress as an NNUE bucket on 2026-07-28. Its progress file is "a double array of 81 × 1548 weights, no header, no separate bias", read from its own file, not from nn.bin. That shape is king square × BonaPiece, so the estimator is **linear in KP features** (my reading; the page does not say what the dimensions index). Bucket families on 2026-07-31: hand4-hand1024 (hand-material buckets), king-pair buckets k9k9, k13k13z, k21k21, k29k29, and progress2-32. Until then a layer stack was picked by **both kings' rank bands (3 × 3 = 9)**. | YaneuraOu wiki changelog 2026 (B5) |
| S3 | **A dedicated bucket for a rare two-king regime.** An external trainer's bucket mode puts "both kings entered" positions (先手玉 on ranks 1-5 and 後手玉 on ranks 5-9, as summarised) in their own bucket 8, and progress octiles in buckets 0-7. | rshogi/tatara PR title and summary, seen only in search-result prose (B6); **UNVERIFIED** |
| S4 | **HalfKPE9 (tttak, 2020-03-25).** HalfKP with each non-king piece's row also indexed by the attack counts on its square, capped at 2 per side (3 × 3 = 9 states). It is 9 times HalfKP's size, about 552 MB. nps about 2/3 of HalfKP (B8). In an informal 8-core parallel measurement, 360 against 480 knps (0.75; B9). It was kept alive into 2024 (a 2024-03-13 net) and built into Gikou 2. No public Elo figure. **HalfKPE4** (presence only, 2 × 2) was released 2020-05-07 as the faster cut, also without numbers. | tttak release notes (B1, B2); tama's note (B8); 48's diary (B9) |
| S5 | **HalfKP-KingSafety (KSDG).** HalfKP plus one-hot states for the **24 squares near the king**: each square's occupant (empty and off-board included) × attack counts capped at 3 per side (4 × 4). That is 24 × 33 × 4 × 4 = 12,672 inputs, and 24 more active. To make the block incrementally updatable, gold was told apart from the promoted minors. It was retrained from scratch at 512x2-8-96 in 2024. No public Elo figure. Six other variants were released, also without Elo: **HalfKP-KK** (a one-hot 81 × 81 block for the two kings' squares, one extra active input, warm-started at zero; informal 430/480 knps), HalfKP-PP (all piece pairs, 85/480 knps), HalfKP-GSGS (pairs of golds and silvers only), HalfKPKfile (HalfKP × the other king's file), and GamePly40x4 (buckets by ply). | tttak release notes (B2); 48's diary (B9) |
| S6 | **Mobility inputs lost, though loss fell.** tanuki- added one-hot mobility counts for the long-range pieces to HalfKP. Validation loss went down, but strength did not follow: **−154.9 ± 10.6** (from scratch), **−73.8 ± 9.9** (fine-tuned), and in a 2024-12 rerun **−47.6 / −46.2 ± 9.7**. nps 1.00 M against 1.32 M (0.76). The author could not find a way to keep mobility incrementally. This matches Fork's E4 and E10. | nodchip blog, 2024-09-29 and 2024-12-09 (B10, B11) |
| S7 | **Effect counts in classical shogi evaluation.** Gikou (2015) evaluated "piece efficiency (two-piece relations, each piece's effects)" and "king hardness (the placement of pieces around the king and its effect counts)". It computed per-square effect counts with SIMD over a byte-per-square board, up to 16 squares at once. | Gikou PR document (B12) |
| S8 | **NNUE's origin.** Nasu built HalfKP from Bonanza-style KP relations and excluded the enemy king's KP from each half. The side to move is handled by perspective ordering, and training shares parameters by decomposing the features (the factoriser). | Nasu 2018 (B13) |

---

## Idea L1-1. Progress-routed heads (shogi's 進行度 router, put into Fork's 8 heads)

- **What the network gains.** Heads chosen by a learned estimate of how far the game has gone, not by material phase
  octiles. Two positions with the same material can then use different heads: queens on with pawns advanced, kings
  stripped and pieces committed (late) against a fresh middlegame (early). Idea 180 found Fork's score-to-result scale
  varies mainly by output bucket (k from 106.9 cp in bucket 0 to 55.4 cp in bucket 7 at STC). So the routing axis is
  where the scale lives, and a sharper axis could sort positions by it better.
- **Why it can't learn it today.** The head index is fixed by the material phase. The 512 columns can carry
  "lateness" features, but all positions of one phase share one head's weights. One linear head per phase cannot
  give early and late positions of equal material different scales or different column mixes.
- **Cheapest form.** An **output-layer router**, with no new rows.
  - Progress is p = sigmoid(sum of w[colour, kind, square]) over the pieces, 768 weights. With king regions it could
    use 4 × 768, the analogue of shogi's KP-linear estimator (S2).
  - Keep it incrementally as one extra int32 per position, added and subtracted with each piece change: one scalar
    add per feature change. Or compute it from the piece list at evaluation: about 32 lookups.
  - Head = octile of p, with boundaries fitted on Fork's data, as the phase octiles were.
  - Training target: the fraction of the game elapsed, ply / final ply, from Fork's own game records, fitted by
    logistic regression. Shogi's exact target is UNVERIFIED (B3 and B4 do not state it).
  - A variant aimed at idea 180's finding: route by predicted plies to the end.
- **Estimated speed cost.** About 0.995-1.00 (est.). That is one scalar per feature change, or about 32 lookups per
  evaluation, against roughly 1,300 cycles per node (ideas.md 46). Break-even is +0.9 Elo at fixed nodes (est.).
- **Data needs.** 768-3,072 router weights fitted once, on millions of positions: trivial. The heads keep today's
  ~1,025 weights each.
- **Cheapest falsifying test.**
  1. CPU, about half an EU: fit the router on g4 game records. Then freeze r3kr1's accumulator and refit only the 8
     heads twice on the same ~2 M positions, once routed by phase octiles (the control, which also refits) and once
     by progress octiles. Score both on a held-out set, with the folds of idea 175's tool. **Kill** if the progress
     routing's held-out loss is not lower than the control's by more than two fold standard errors.
  2. The deciding test: write both refit head sets into net files (the engine's router change, about half an EU).
     Then run an FN screen of progress-refit against phase-refit, to remove the effect of refitting alone.
     **Kill** at ≤ 0.
  3. Only then: a 60-superbatch fine-tune with the router in the trainer (0.4 GPU-h per seed), then STC.
- **Novelty and nearest relatives.**
  - Shogi: S1 and S2 (tanuki-, YaneuraOu, 2026), and the logistic-regression progress of Gekisashi and Gikou.
  - Chess: output buckets by piece count or phase are standard (survey C11). I know of no chess engine that routes
    heads with a *learned* progress estimate (UNVERIFIED).
  - Fork: idea 183 (knot-tied heads, which could blend along p instead of phase), 159 (material-class experts), 180
    (killed: rescaling heads, not re-routing them), and survey C11 (piece-count buckets: 0, because it only re-cuts
    the same axis).
  - The key difference: shogi's baseline was king-position buckets, because shogi material never leaves the game. In
    chess, material phase is already a strong proxy for progress, so most of S1's +30.7 will not transfer.
- **Rough expected Elo and chance.** +3 (−2 to +8), chance 30% (est.). Cost to kill 1 EU, full cost about 3 EU.
  **About 0.30 Elo per EU.**

## Idea L1-2. Two-king inputs: a KK row, and heads routed by the kings' wings (Bonanza's KK, tttak's HalfKP-KK, YaneuraOu's k3k3)

- **What the network gains.** The exact conjunction of **both kings' squares**:
  - opposite-wing castling (pawn storms, open files aimed at a king);
  - king against king in endings (opposition, distance, which king reaches a passer's square: idea 161's endings);
  - a king that has walked into the centre against one that is castled.
- **Why it can't learn it today.**
  - In H512+PP the enemy king is one row of the region's 768, indexed by (own region, enemy king square), with only
    four coarse own-king regions (M4). Within a region, the own king's exact square and the enemy king's square meet
    only through SCReLU's pairwise products, which compete for 512 columns.
  - Engines with 32-64 king buckets get KK implicitly, because the enemy king's row is per own-king bucket. Fork gave
    that up when M8 was killed (0.961, cache bound).
  - A KK row restores the fine own-king × enemy-king conjunction for 2,048 rows instead of 4 times the table.
- **Cheapest form.** Two parts, both cheap.
  - (a) **An extra-row family** of 2,048 inputs per perspective: the own king's mirrored square (32) × the enemy
    king's square (64), shared across regions like the pawn links. One input is active per perspective. It changes
    only on a king move: 2 row operations per perspective, 0 on other moves. Warm start at zero, as tttak did, gives
    a bench-identical prototype.
  - (b) **Routing, which is free**: heads by phase × a king-pair class {same wing, opposite wings}, or 3 classes with
    "a king in the centre files", so 16-24 heads. This is shogi's k3k3 idea (S2), and S3's dedicated rare-regime
    bucket for opposite-wing positions.
- **Estimated speed cost.**
  - (a) About 0.98-0.99 (est.). If 8-12% of makes are king moves (UNVERIFIED; one counting run on bench gives it),
    that adds about 0.2-0.25 row operations per perspective update against 3.09 today. That is roughly 7% more update
    work at 26% of cycles, so about 1.5-2%. Plus one more row in each refresh.
  - Warning from shogi: HalfKP-KK measured 430/480 knps (0.90), informally and under parallel load (S5). The cause is
    unknown, possibly implementation; Fork's own prototype decides.
  - (b) About 1.00.
- **Data needs.**
  - (a) 2,048 × 512 = 1.05 M weights. With 2 active rows per position over ~1.2 B kept positions, that is about 1.2 M
    examples per row on average. It is skewed: rare king pairs (both kings central in a middlegame) get few, so a
    shared factor (own-king-square row plus enemy-king-square row, merged at export) helps.
  - (b) 16-24 heads × ~1,025 weights: ample.
- **Cheapest falsifying test.**
  1. CPU, half an EU, with idea 175's residual tool: an additive table over (own king mirrored square, enemy king
     square), fitted beside the base table, gives KK's share of r3kr1's held-out residual.
     - **Calibrate the line first** with the tool's injected-effect checker, and on one known-good family. For
       example, the pawn-link pairs' share on S512r2 (the pre-link net), as idea 23's revamp B0 asks. If even links
       show far below 0.5%, the 0.5% line kills everything and must be set relative to a family that paid.
     - **Kill** KK at under one third of the calibrating family's share.
  2. (b) rides on L1-1's head-refit pipeline at no extra cost: refit 16 heads (phase × wing class) on the frozen body.
     **Kill** on the same rule.
  3. (a) A zero-weight speed prototype. **Kill** below 0.98. Then a session arm beside a same-recipe control
     (4.4 GPU-h) and the speed-adjusted FN screen.
- **Novelty and nearest relatives.**
  - Shogi: Bonanza's KK/KKP (three-piece relations; Nasu 2018 describes the lineage), tttak's HalfKP-KK, YaneuraOu's
    king-pair layer-stack buckets (k3k3 to k29k29), and S3's both-kings-entered bucket.
  - Chess: KK arises implicitly in full-bucket HalfKA nets. A standalone KK row beside coarse king regions, and heads
    routed by the kings' wings, I have not seen (UNVERIFIED).
  - Fork: idea 157 (king offsets, parked), 179 (offset lane, parked), M8 (killed), R3 option (b)'s enemy-king half
    ("no cheap inference path found"; KK is the one-row path), and option d's shelter and king-zone counts.
- **Rough expected Elo and chance.** +4 for (a) and (b) together (−3 to +10), chance 25% (est.). Cost to kill
  1.5 EU, full cost 4.5 EU. **About 0.22 Elo per EU.** (b) alone: +1 (est.) at about 0.3 EU, so worth running on
  L1-1's pipeline either way.

## Idea L1-3. Effect (利き) features: HalfKPE9's row choice is dominated in chess; the king-zone square-state lane (HalfKP-KingSafety) is the form that survives the cost lesson

- **What the network gains.** For each of the 24 squares around a king (the 5 × 5 window less the king, side-relative
  and mirrored), a learned value for the conjunction **occupant × own attackers × enemy attackers**. For example:
  - an empty g2-type square hit twice by the enemy and once by us;
  - an enemy knight on a zone square that we do not cover;
  - our defender standing where only the enemy's attacks arrive.

  Raw counts cannot express these, because the count's meaning depends on what stands on the square.
- **Why it can't learn it today.**
  - Fork's inputs hold occupancy, not control. Control is a function of every slider's line and its blockers, so the
    single layer would have to rebuild ray geometry from piece-square pairs.
  - The exposure plane and x_lower show the value exists: +25.67 and +17.60 FN.
  - b2 and d_kzone feed *counts* into the head, which cannot express occupant × control per square.
- **Form A, row choice: rejected on Fork's cost lesson.** HalfKPE9's form is each piece's row indexed by (own count,
  enemy count) on its square (S4).
  - In chess, one slider move changes the control of up to ~14 squares and opens discovered lines, so several pieces
    flip state on most moves (est. 2-5 per perspective).
  - A row choice costs **2** operations per flip (subtract the old row, add the new); an extra row costs 1.
  - The table grows 9 times: 4 regions × 768 × 9 rows × 1 KB ≈ 28 MB.
  - **The rule (from idea 175 and this):** a state pays as a row choice only if it flips on fewer than half as many
    moves as the extra-row form would add rows on. Pawn-clocked states pass that test. Control states fail it.
  - So E9/E4 is dominated by the exposure plane's extra-row form (S512+X, x_lower, idea 178), which Fork has already
    measured.
- **Form B, the cheapest surviving form: a king-zone lane as an output-layer embedding.**
  - Per king, 24 zone squares; per square, a state of 12 occupant classes (empty, off-board, 5 own and 5 enemy
    non-king kinds) × min(own attackers, 2) × min(enemy attackers, 2), 108 states. That is 2,592 inputs per king
    side.
  - Each active input indexes a 16-wide int16 vector (one 256-bit register).
  - Per evaluation: 24 adds per king, 48 in all, into a 16 + 16 vector. Pass it through SCReLU into the head, beside
    the 1,024 accumulator values.
  - It is recomputed every evaluation, never kept incrementally: S6 shows how badly an effect input does without an
    update path.
- **Estimated speed cost.**
  - The lane's sums are nearly free. The **finder** is the price: attack counts by both colours on 48 squares.
  - Fork measured d_kzone (b2's zone counts) at about 7% and b2 at 0.914-0.919. Form B needs per-square two-colour
    counts, a bit more than b2 computes.
  - Estimate 0.90-0.93 (est.). Break-even is +12 to +18 at fixed nodes.
  - Two levers from shogi and Fork:
    - Gikou's per-square SIMD counting over a byte board, 16 squares at once (S7);
    - sharing the finder with b2/d_lite if either is adopted, so the lane's *marginal* cost is the sums only, about
      0.99 (est.).
- **Data needs.** 2 × 2,592 × 16 ≈ 83,000 weights. Most states are common, and the rarest (an enemy queen on a zone
  square with two of our attackers) still occur thousands of times in 1.2 B. No new data is needed.
- **Cheapest falsifying test.**
  1. CPU, half an EU: residual share of an additive table over (zone offset, state) on r3kr1's held-out residual, with
     L1-2's calibrated line. Report b2's raw counts in the same run for comparison. **Kill** if the square-state table
     explains no more than b2's counts do.
  2. A finder-only speed build: count maps for both zones, no weights. **Kill** below 0.93 stand-alone, or below 0.98
     marginal on top of b2 if b2 is in.
  3. Only then a fine-tune arm with the lane, at zero output weight to start (bench-identical), against the
     same-recipe control.
- **Novelty and nearest relatives.**
  - Shogi: HalfKPE9 and E4 (S4), HalfKP-KingSafety and KSDG (S5), Gikou's king-hardness effect terms (S7), and
    mobility (S6, the negative case).
  - Chess: king-zone attack counts are classical, and attacker-victim threat inputs are known (survey C7). A one-hot
    occupant × two-colour control state per king-zone square, used as an NNUE input or embedding, I have not seen in
    chess (UNVERIFIED).
  - Fork: b2 and d_kzone (counts, reserve), idea 158 (king-zone piece pairs), 178 (side-to-move exposure block), 157
    and 179 (king offsets), and idea 46 rank 4 (dense danger vector).
- **Rough expected Elo and chance.** +4 net at STC (−8 to +10), chance 12% (est.). Most of the risk is the finder's
  speed. Cost to kill 1.5 EU, full cost about 7 EU. **About 0.07 Elo per EU**, or about 0.2 if b2's finder is
  already paid for.

## Idea L1-4. Captured-material ordinals (shogi's hand-piece encoding, put into chess)

- **What the network gains.** Count-dependent material knowledge: the bishop pair, a second rook, minor pieces
  against a queen, the last pawn. In shogi HalfKP, as I understand BonaPiece (UNVERIFIED), each piece in hand is a
  separate feature by its ordinal: having 3 pawns in hand activates the 1st, 2nd and 3rd. Counts are therefore
  thermometer-coded and king-relative. tttak's Material1/2 nets (material-only NNUE, 85 and 130 inputs; B2) show the
  same family used alone.
- **Why it can't learn it today.** The accumulator is linear in piece inputs, so a count enters only as a sum over
  squares. A threshold such as "two bishops" or "no pawns left" needs columns whose SCReLU turns on at that sum,
  spending capacity at every square's rows. Option d's bishop-pair flag fed linearly into the head cannot interact
  with anything else. As an accumulator row, it can.
- **Cheapest form.** An **extra-row family** of about 38 inputs per perspective: own and enemy × P≥1..P≥8, N≥1..3,
  B≥1..3, R≥1..3, Q≥1..2, shared across regions.
  - Captures and promotions toggle exactly one ordinal (the highest of the kind that changed). Quiet moves toggle
    none.
  - Warm start at zero gives bench-identical prototypes.
- **Estimated speed cost.** One extra row operation per perspective on each capture or promotion. Captures are a
  large share of makes in quiescence (UNVERIFIED share), so about 0.97-0.99 (est.).
- **Data needs.** 38 × 512 ≈ 19,000 weights, every position activating about 20: ample.
- **Cheapest falsifying test.**
  1. CPU, under half an EU: residual share of an additive table over the thermometer bits, and the bishop-pair and
     opposite-bishop pairs, against r3kr1's residual, with L1-2's calibrated line. **Kill** below one third of the
     calibrating family's share.
  2. A zero-weight speed prototype. **Kill** below 0.985.
- **Novelty and nearest relatives.**
  - Shogi: hand-piece ordinal features in HalfKP/BonaPiece (UNVERIFIED as described), and tttak's Material nets.
  - Chess: material-imbalance tables and output buckets by piece count are classical. A thermometer-coded material
    family *inside* the accumulator I have not seen (UNVERIFIED).
  - Fork: idea 159 (material-class output experts, round 3 priority, which is the head-side form), option d's d_bpair
    (0.996-1.010, linear), and the drift tables keyed by material (idea 78).
  - Idea 175's finding (pawn states explain about 0.006%) makes a large residual share unlikely.
- **Rough expected Elo and chance.** +2 (−3 to +5), chance 15% (est.). Cost to kill 0.8 EU, full cost 3.5 EU.
  **About 0.09 Elo per EU.**

---

## Ranking (expected Elo per EU, est.)

| Rank | Idea | Central Elo | Chance | Kill cost (EU) | Full (EU) | Elo/EU |
|---|---|---|---|---|---|---|
| 1 | L1-1 Progress-routed heads | +3 | 30% | 1 | 3 | 0.30 |
| 2 | L1-2 Two-king KK row and wing-class heads | +4 | 25% | 1.5 | 4.5 | 0.22 (part b alone about 0.3) |
| 3 | L1-4 Captured-material ordinals | +2 | 15% | 0.8 | 3.5 | 0.09 |
| 4 | L1-3 King-zone square-state lane | +4 | 12% | 1.5 | 7 | 0.07 (0.2 if b2's finder is paid) |

**Suggested order.**
- L1-1 and L1-2(b) share one pipeline: a frozen r3kr1 body and head-only refits under three routings (phase, progress,
  phase × wing). That is about 1 EU of CPU and no GPU, and it decides both.
- Run L1-2(a)'s and L1-4's residual shares in the same pass of idea 175's tool, after calibrating its line on a
  family that paid (pawn links on S512r2). Idea 175's 0.006% suggests the uncalibrated 0.5% line may reject
  everything.
- L1-3 only if b2 or d_lite is adopted, so its finder is already paid for.

**Considered and left out.**
- **HalfKP-PP / all piece pairs.** 85/480 knps in shogi (B9). Survey C7 and idea 41 cover it.
- **GSGS** (pairs of defensive pieces only). This is idea 158's family.
- **HalfKPKfile** (HalfKP × the other king's file). Superseded by L1-2's cheaper KK row.
- **Mobility.** Shogi's own result is −47 to −155 Elo at 0.76 nps (S6).
- **HalfKP_vm.** The file mirror, which Fork already has.
- **Turn-dependent KPPT terms.** The perspective ordering already carries the side to move (Nasu 2018, §2.6).
- **Progress-range filtering of training data** (nodchip 2023-01-04 and 2023-01-08). That is data selection, outside
  this lens. Its result (keep nearly the full range: max 0.9 about equal to 1.0) also argues against narrowing.

## Sources (all opened 2026-11-14; prose only)

| # | Title / author | URL |
|---|---|---|
| B1 | Release NNUE-HalfKPE9, tttak (release notes, 2020-03-25 and addenda) | https://github.com/tttak/YaneuraOu/releases/tag/V4.89_NNUE-HalfKPE9 |
| B2 | Releases page, tttak/YaneuraOu (HalfKPE4, KingSafety, KSDG, HalfKP-KK/PP/GSGS/Kfile/GamePly, Material nets; release prose) | https://github.com/tttak/YaneuraOu/releases (the 2020-04-01 variant release: .../tag/V4.89_NNUE-features_20200401; KSDG: .../tag/V4.89_NNUE-features_20200406) |
| B3 | "tanuki- 2026-02-04 SFNNwoP1536 進行度によるバケット選択", nodchip | https://nodchip.hatenablog.com/entry/2026/02/04/000000 |
| B4 | "tanuki- 2026-04-01 progress.bin を PyTorch Lightning で学習する", nodchip | https://nodchip.hatenablog.com/entry/2026/04/01/000000 |
| B5 | やねうら王の更新履歴2026 (YaneuraOu wiki changelog, prose), yaneurao and contributors | https://github.com/yaneurao/YaneuraOu/wiki/%E3%82%84%E3%81%AD%E3%81%86%E3%82%89%E7%8E%8B%E3%81%AE%E6%9B%B4%E6%96%B0%E5%B1%A5%E6%AD%B42026 |
| B6 | Search-result summaries of rshogi/tatara PR titles (bucket modes progress8kpabs, progresskpabsq16ek). **Not opened** (code PRs); UNVERIFIED | https://github.com/rshogi/tatara/pull/8 (not opened) |
| B7 | NAGISA listing (BOOTH), ngs436: a progress file adapted from tanuki-'s; trained with tatara | https://booth.pm/ja/items/8639574 |
| B8 | "HalfKPE9型の評価関数の検証を始めました", たま (2020-03-28) | https://note.com/m_tamachan_m/n/ndf6e40297cbb |
| B9 | "色々な特徴量を使用したNNUE評価関数ですって", 48's diary (the48), 2020-04-02 | https://bleu48.hatenablog.com/entry/2020/04/02/170612 |
| B10 | "tanuki- 2024-09-29 HalfKP+Mobility", nodchip | https://nodchip.hatenablog.com/entry/2024/09/29/000000 |
| B11 | "tanuki- 2024-12-09 駒の可動性", nodchip | https://nodchip.hatenablog.com/entry/2024/12/09/000000 |
| B12 | 技巧 PR文書, 出村洋介 (denou 2015) | https://denou.jp/tournament2015/img/PR/Gikou.pdf |
| B13 | Yu Nasu, "Efficiently Updatable Neural-Network-based Evaluation Functions for Computer Shogi", WCSC28 appeal document, 2018-04-28 (text partly unreadable from the PDF's font encoding; abstract and section structure read) | https://www.apply.computer-shogi.org/wcsc28/appeal/the_end_of_genesis_T.N.K.evolution_turbo_type_D/nnue.pdf |
| B14 | nodchip, "tanuki- 2021-11-14 HalfKP_vm"; "2023-01-08 ... max_progress"; "2026-06-04 SFNN_halfka2_1536_7_32_p" (context only) | https://nodchip.hatenablog.com/entry/2021/11/14/000000 ; .../2023/01/08/000000 ; .../2026/06/04/000000_1 |
| B15 | Gekisashi/Gikou logistic-regression progress: cited in B3. The 2008 IPSJ report on 進行度 in the Bonanza method was not reachable (HTTP 503); UNVERIFIED | https://ipsj.ixsq.nii.ac.jp/records/58472 |
| F | Fork's own files (read-only): docs/research/network-novelty-2026-11-14.md, docs/ideas.md (157-184, 41, 46), docs/nets.md, docs/research/idea175-screens.md, docs/research/network-survey-2026-11/shortlist.md, and proto/r3-king-a and proto/r3-king-d's reports (by `git show`) | local |

## Clean-room statement

- I opened no engine source code, chess or shogi: no source files, diffs, headers, training scripts or configs.
- What I read: GitHub *release pages* and a *wiki changelog* (prose), blog posts, a note.com post, two PR/appeal PDFs
  (Gikou's; Nasu's, partly unreadable) and a store listing.
- Search results listed source-file pages (docs.rs source views of rshogi-core, a Hugging Face .cpp, GitHub PRs of
  rshogi/tatara). **I did not open any of them.** B6 is used only as search-result prose and is marked UNVERIFIED.
- Some fetched pages mentioned code-level details in passing, and I used none of them:
  - the YaneuraOu changelog listed feature-set hash constants and a function name;
  - nodchip's 2026-06-04 post listed training-configuration settings (bucket-mode and progress-file option names,
    loss settings).

  What I took from those pages is only the published results and concepts.
- No constant from any engine is proposed here. Every count above (24 zone squares, caps at 2, 8 octiles, 38
  ordinals, the 16-wide lane) is a placeholder for Fork's own design. Each still needs Fork's own justification and
  the originality screens. "24 squares" and "capped at 2" echo tttak's published designs and should be screened as
  such.


# Appendix B: lens2-classical.md (the lens agent's section, unedited)

# Lens 2: classical chess theory (public-domain texts) and what Fork's network cannot see

Read-only research, 2026-11-14 (EST). Nothing was built, run, edited or committed. Every Elo and nps figure here is an
estimate, marked "(est.)", unless it cites a Fork measurement. Names are placeholders and have not been screened.

## 0. The filter: which classical concepts the current net can already form

To decide which human concepts are worth inputs, I asked what one SCReLU layer over Fork's inputs can build cheaply.
This is reasoning, not a measurement.

- **What a column computes.** Each hidden column computes clip(b + w.x, 0, 1)^2. In the unclipped range that is a
  quadratic form, so the 512 columns per perspective give a pairwise interaction matrix over the inputs of rank at
  most 512 (1,024 over both perspectives). The clip adds thresholds: a column can represent an AND of specific
  inputs, or an AND with some inputs negated ("this piece here, and none of those pawns"). But it represents one such
  pattern per column, because the first layer shares no weights across squares.
- **Cheap concepts.** A concept is cheap if it is a *low-rank* pairwise product, or a negation over **pawns** only.
  Pawns sit in the accumulator as inputs, and the 608 links already carry their geometry.
- **Expensive concepts.** A concept is expensive if it needs a **line of sight through arbitrary occupancy** (a
  slider's relation to another piece with every square between empty of all 12 piece kinds), or a **count of
  attackers against defenders** on a square. Such a concept is a disjunction over hundreds or thousands of
  geometric instances. Each instance is a many-input conjunction, and each needs its own column direction.

The classical concepts in the brief, sorted by this filter:

| Classical concept (source) | Structure | Today's net | Verdict |
|---|---|---|---|
| Outpost / strong point: a piece on a square guarded by its own pawn that no enemy pawn can attack (Nimzowitsch I.2 §6; Lasker No. 7-8 "weak point"; CPW Outposts) | piece x own pawn, AND no enemy pawn on the two adjacent files ahead: negation over pawns only | idea 175: "defended by own pawn" 0.000%, "attacked by enemy pawn" 0.025% | already formed; not proposed (the "never attackable" half is folded into idea L2-4's panel) |
| Hole: "a square ... that cannot be controlled by a pawn" (Wikipedia glossary; Capablanca §31, §33) | pawns only | links + pawns | already formed |
| Bad bishop: a bishop "limited by" own pawns on its colour (Capablanca §14; CPW Bad Bishop) | bishop colour (a linear sum of bishop rows) x own pawns on that colour, rammed or not (a ram is one of the 608 links) | a low-rank pairwise product | cheap; not proposed |
| Bishop against knight by structure (Capablanca §14) | bishop and knight presence x pawn spread | low rank | cheap |
| Seventh rank: a rook attacking pawns on the 7th, the "absolute" 7th with the king shut on the 8th (Nimzowitsch I.3 §1-3; CPW Rook on Seventh) | rook-on-rank-7 sum x king-on-rank-8 sum: **rank 1** | trivial | cheap; only the *entry route* (the clear file) is not, see L2-1 |
| Space (CPW Space: safe central squares behind own pawns, weighted by piece count) | pawns x piece count | cheap | not proposed |
| Minority attack (a pawn plan) | pawns only; its value lies beyond a 20,000-node horizon | the input is present, the **label** is blind | a label-depth question (in-flight larger-teacher relabelling), not an input question |
| **Open-file control and the fight for the file** (Nimzowitsch I.2 §3, §6: the file is a route to "ultimate penetration"; doubling is "the only sure sign that a file is controlled"; Lasker No. 6-8; Capablanca §29) | a heavy piece's line along its file **through all pieces**: who it meets first | not quadratic: about 1,800 (est.) file-pair x piece-kind patterns, each a conjunction with a negation over up to 6 squares x 12 kinds | **L2-1** |
| **Blockade of a passed pawn by a piece**, and which piece (Nimzowitsch I.4 §2-4: a minor "can stand up to an attack", the queen "reacts to the slightest attack", the king is poor except in endings; Capablanca §31: a passer "increases in strength as the number of pieces on the board diminishes") | passer status (a negation over up to 15 enemy-pawn squares) x the kind of piece on the stop square x phase | a three-way conjunction with phase-dependent sign | **L2-2** |
| **Overprotection and loose pieces** (Nimzowitsch I.4 §3a: a blockader "insufficiently or imperfectly protected" is driven off, so protect it more than necessary; CPW Connectivity: "the less mobile a piece is, the more protection it needs", loose pieces penalised; Capablanca §28: tying the enemy rooks to the defence of pawns) | defender count against attacker count per piece: needs full attack and defence maps | not representable | **L2-3** |

**Why idea 175's null does not close the question.** Idea 175 tested exactly the cheap half of this table:
pawn-relation states, which are pawn-only conjunctions. The filter predicts the net already forms them, and the study
found it did (0.006%). The three proposals below are the other half, the relations to **non-pawn occupancy** and
**attack counts**. They differ in kind from tier A. Section L2-4 explains why the study's 0.5% line would be unreliable
even for them, and how to recalibrate it cheaply.

---

## L2-1. File-line contact state for rooks and queens ("the fight for the open file")

- **What the network gains.** For each rook and queen: what it first meets going forward along its file. The
  candidate values:
  - the board edge with nothing in the way (a truly clear file: Nimzowitsch's route to the 7th and 8th ranks);
  - an enemy pawn (a half-open file with a target);
  - an own pawn (closed);
  - an own rook or queen (doubled: a battery, the file's control);
  - an enemy rook or queen with nothing between (a contested file);
  - a minor piece or king (a blocked or x-ray line).

  These are the classical facts about files that idea 175's rook file state (pawns only) left out. Its
  closed/half-open/open state explained 0.000%: the net knows where the pawns are. It does not know whether *pieces*
  close the file, whether the rooks see each other, or whether an enemy rook stands opposite.
- **Why it can't learn it today.** "Rook on d1, nothing on d2-d6, enemy rook on d7" is a conjunction of 2 positive
  inputs and negations over 5 squares x 12 piece kinds. Over 8 files, the 28 square pairs per file and the
  heavy-piece kind pairs, that is roughly 1,800 such patterns per perspective (est.), each needing its own column
  direction. Fork's 512 columns are already carrying the piece-square and link knowledge.
  - The exposure plane does not cover it: x_lower is "attacked by a *lower* class", and the full rule's "attacked and
    undefended" misses a defended rook facing a rook.
  - Threat inputs in the field encode such attacker-victim pairs, but as about 60,000 pair inputs (network survey
    matrix), which Fork cannot afford (survey shortlist C7, 0.55-0.70 nps, est.).
- **Cheapest form.** Extra rows confined to **the 64-column block that idea 178 builds** (shared infrastructure). A
  state-folded row choice would multiply with the M4 regions, as idea 175's report warned for its own states.
  - Encoding: only the three informative non-default states get rows: doubled (own heavy ahead), contested (enemy
    heavy ahead) and clear to the edge. That is 2 colours x {rook, queen} x 64 squares x 3 = **768 rows x 64
    columns** (49,152 weights, about 98 KB int16), side-relative and mirrored with the piece.
  - The default states (own pawn, enemy pawn, minor or king ahead) add no row; their pawn-only part is already known.
  - Optional variant: "backward" doubling (an own heavy behind the rook) is the same relation seen from the other
    piece, so it is not encoded twice.
- **Estimated speed cost (est.).**
  - Finder: at each push, from the Position (E3: carrying the board in the delta is free), take the heavy pieces on
    the files of the moved piece's from- and to-squares and of any captured piece. For each, recompute its first
    piece forward: a file mask, the occupancy, one bit scan. That is a few dozen instructions on every push, against
    idea 175's push-time states, which raised push_move from 6.5% to 7.9% of samples.
  - Flips: 0.1-0.3 per update (est.), each at one-eighth width.
  - Ratio **0.975-0.99 (est.)**, once idea 178's block kernel exists. Kill line: below 0.97, which would need about
    +5 at fixed nodes (−118 log2 0.97 = 5.2).
- **Data needs.** About 49 k weights. Heavy pieces are present in most positions, and the three states are common in
  the middlegame (frequencies UNVERIFIED; a CPU count on g4c settles it). This is orders of magnitude more instances
  per weight than idea 175 had for its rarest states. Fork's ~1.2 B kept positions suffice.
- **Cheapest falsifying test.**
  1. A new family in `state_rows_study.py`, with the state found through python-chess's attack and ray queries, as
     `state_rows_net.py evals` did. Run it on g4c 600 k and g4s2-val, by square, pooled, **and by output bucket**
     (see L2-4). CPU minutes, about 0.3 EU with the frequency count.
     **Kill:** under the calibrated line from L2-4. If L2-4 is not run, under 3x tier A's best (0.1%) on both sets.
  2. Only then: a zero-weight speed prototype inside 178's block (0.5-1 EU, one quiet hour). **Kill** below 0.97.
  3. Then two fine-tune seeds beside a same-recipe control, a speed-adjusted fixed-node screen, and an STC SPRT.
- **Novelty and nearest relatives.**
  - In Fork: idea 175 (the rook file state from pawns only, killed), idea 178 (the column block), x_lower and the
    exposure plane (attacks by class), idea 41/S512cl contacts (pairwise attacker-victim inputs, unaffordable), and
    idea 158 (king-zone piece pairs).
  - In the field: threat inputs (attacker-victim pairs; survey matrix, 16 rated nets), and classical terms for a
    rook on an open file and doubled rooks (CPW, concept level).
  - Compressing a slider's line relation into **one per-piece state** (first piece met along the file) is, as far
    as I know, not done in NNUE inputs. UNVERIFIED: no prior-art search was made.
- **Rough expected Elo and chance (est.).** Fixed nodes +5 (−2 to +10). Net STC +2 (−5 to +7) after a speed price of
  2-4. Chance it passes its SPRT: 20%. Full cost about 5 EU, which gives **about 0.08 expected Elo per EU**.
  Falsifier alone: 0.3 EU.

## L2-2. Blockade state of a passed pawn: who stands on its stop square

- **What the network gains.** For each passed pawn, the occupant of its stop square (the square directly ahead):
  - empty;
  - an enemy minor piece (Nimzowitsch's good blockader);
  - an enemy rook or queen (poor blockaders: "the Queen reacts to the slightest attack");
  - the enemy king (good in endings);
  - an own piece (a self-block).

  Classically the blockader's kind and the phase decide whether a passer is a winning asset or a weakness that cramps
  its own side. Nimzowitsch I.4 §2c says a blockaded pawn leaves the pieces behind it "prisoners in their own camp";
  Capablanca §31 says the passer grows stronger as pieces come off.
- **Why it can't learn it today.** Passed status is a negation over up to 15 enemy-pawn squares, which the net forms
  (idea 175: the passer state explained 0.012%). Blockade multiplies that by the stop-square occupant's kind, a third
  factor, and its value changes **sign by phase**: a knight blockade is good in the middlegame, a king blockade
  matters mostly in endings. That makes about 48 squares x 4 occupant kinds x phase patterns per perspective. Each is
  a three-way conjunction.

  The phase-dependent sign is also the specific reason idea 175's study could miss it: one additive table pooled over
  all phases averages opposite-signed effects toward zero (see L2-4).
- **Cheapest form.** A small **extra-row family shared across king regions, beside the 608 links**. Like the links,
  it describes the structure, so it need not multiply with M4.
  - Encoding: 2 colours (of the passer) x 48 squares x 4 non-empty occupant classes = **384 rows** (0.39 MB at full
    width; or the 178 block, 49 KB).
  - An empty stop square adds nothing: the bare passer is already known.
  - Alternative: the passer's own row choice by occupant class would touch the region-multiplied piece table, so it
    is not preferred.
- **Estimated speed cost (est.).**
  - Finder: keep the passer set and its stop-square mask in the stack entry, recomputed only on pawn-changing deltas
    (a few shifts, not idea 175's per-piece recomputation). On every push, test the moved piece's from- and to-squares
    and the captured piece's square against the stop mask: two or three ANDs.
  - Flips: a piece entering or leaving a passer's stop square on about 2-5% of moves (est., UNVERIFIED), or a pawn
    move changing passer status.
  - Ratio **0.985-0.995 (est.)**. Kill below 0.98.
- **Data needs.** 384 rows (197 k weights at full width). Passers: 1.03 per position (idea 175's g4c count). The
  blockaded share is UNVERIFIED (a CPU count on g4c). Even at 10% of passers, that is about 120 M instances over 384
  rows. Ample.
- **Cheapest falsifying test.** Same as L2-1: a family in `state_rows_study.py`, by square and by output bucket, plus
  **the endgame buckets alone (0-2)**. Fork's held-out 6-7-piece errors concentrate there (E9, idea 161). It runs in
  the same CPU pass as L2-1 and L2-4, about 0.2 EU extra.
  **Kill:** under the calibrated line in every bucket group.
- **Novelty and nearest relatives.**
  - In Fork: idea 175 (passer state), idea 161 (passed-pawn races), option (d)'s d_pawn (passer counts and ranks, an
    output-layer form, 0.957) and the pawn links (the family this joins).
  - In the field: classical "blocked passed pawn" and stop-square terms (CPW Square Control: "control of the stop and
    telestop squares of passed pawns", concept level).
  - A network input keyed by the blockader's *kind* is unknown to me. UNVERIFIED.
- **Rough expected Elo and chance (est.).** Fixed nodes +2.5 (−2 to +6). Net STC +1.5. Chance 15%. Full cost about
  4 EU, which gives **about 0.06 expected Elo per EU**. Falsifier alone: 0.2 EU. Its realistic role is as a cheap
  family in the shared study run.

## L2-3. Defence surplus: loose and overprotected pieces, on idea 178's finder

- **What the network gains.** For each non-pawn, non-king piece, its defence balance:
  - **loose**: not defended, whether attacked or not. Attacked and undefended is already the exposure plane; this
    adds the unattacked latent targets.
  - **overprotected**: defenders exceed attackers by at least two. These are Nimzowitsch's strong points that
    "stand up to an attack", and Lasker's "attack only with tangible superiority" turned around.

  Classically, loose pieces are what tactics feed on a move later. Overprotected blockaders and outposts are what
  makes a positional edge durable. Fork's measured problem is edges eroding over many quiet moves with queens on (E8).
- **Why it can't learn it today.** A defender count needs every piece's attack set through occupancy. That is the
  same not-quadratic structure as L2-1, but over all piece pairs. It is exactly the information the exposure plane
  showed is worth Elo at fixed nodes (+25.67 for S512+X, +17.60 for x_lower), and exactly the part x_lower dropped:
  x_lower needs "no defence map" (proto/r3-king-c report).
- **Cheapest form.** **Conditional on idea 178's L-exact cut** (the full rule needs the defence map). The finder is
  then already paid for, and this adds per-piece bits read from the same maps, as extra rows in the same 64-column
  block.
  - Encoding: 2 sides x 4 kinds x 64 squares x 2 states (loose, overprotected) = **1,024 rows x 64 columns** (131 k
    weights).
  - Without L-exact it would carry the finder's full cost: x_find_only alone was 0.939 (E2). That does not pay, so
    the idea is dead unless L-exact lives.
- **Estimated speed cost (est.).** On top of L-exact: bit tests on maps already built, plus about 1-2 more rows per
  evaluation at one-eighth width, added per evaluation as in x_eval. Ratio relative to L-exact **0.985-0.995
  (est.)**. Standalone: about 0.92-0.93 (est.), killed.
- **Data needs.** 131 k weights. Loose pieces are common (count UNVERIFIED; a CPU count settles it). Fine for 1.2 B
  positions.
- **Cheapest falsifying test.** Run a family in the same study pass: loose and overprotected per (colour, kind,
  square), found by python-chess attack queries, side to move and opponent separately, as idea 178's own share test
  splits them. **Kill:** a share under one third of x_lower's family share in the same run (L2-4 measures that
  share). Then it rides on 178's prototype: one more variant, under 0.5 EU.
- **Novelty and nearest relatives.**
  - In Fork: the exposure rule (S512+X, x_lower, idea 178), option (d)'s mobility component (0.955), and idea 46's
    dense danger vector ("restricted pieces").
  - In the field: classical connectivity terms (Kopec, Northam, Podber and Fouda 1989, as described on CPW
    Connectivity, concept level), and threat inputs, whose public descriptions include attacks on pieces. Whether
    they include own-piece defence is UNVERIFIED.
  - Overprotection as a network input: unknown to me. UNVERIFIED.
- **Rough expected Elo and chance (est.).** If L-exact exists: fixed nodes +3 (−3 to +7), net STC +2, chance 15%,
  added cost about 3 EU, which gives **about 0.10 expected Elo per EU** (conditional). Otherwise 0.

## L2-4. The classical panel, with the kill line calibrated on Fork's known winners (the shared falsifier)

- **What it gains (for decisions, not the net).** One CPU run decides whether L2-1 to L2-3, and any future
  "state" input, should be judged by idea 175's rule at all. It fixes three reasons the study as run could miss a
  real classical concept:
  1. **The line was never calibrated against an input known to win.** E10: S512+PP's pawn links cut the loss by
     only 0.06% yet gained +32.7 STC (+46.09 at fixed nodes). If an input's Elo value comes from decision-relevant
     positions and not from variance, its residual-variance share can be tiny. The 0.5% line could then have killed
     Fork's best-ever input. Treating loss reduction as comparable to residual-variance share is UNVERIFIED (the
     trainer's loss exponent may differ).
  2. **One additive table across all phases.** Nimzowitsch calls the 7th rank an "end-game weapon". Capablanca says
     a passer gains strength as pieces come off, and that the knight beats the bishop only in blocked one-sided
     structures. These are classical effects whose sign or size changes by phase, and pooling cancels them.
  3. **The labels' horizon.** Residuals against 20,000-node self-play labels can only show what those searches see.
     Long-horizon concepts (bad bishop, minority attack, space) are where shallow labels are blind. So a null
     residual there says "the labels don't know" as much as "the net knows".
- **Mechanism.**
  1. **Calibrate.** In the same tool, measure the share of two input families already measured in games:
     - (a) x_lower's state (a piece attacked by a lower class), on r8brft1's residual. Its game value is +17.60 at
       fixed nodes. Idea 175's "attacked by an enemy pawn" is a subset of it, and scored 0.025%.
     - (b) If the study's net loader can evaluate S512r2 (UNVERIFIED), the 608 links as a 608-cell additive family
       on S512r2's residual. Their game value is +46.09 at fixed nodes.

     Set the line at about half the smaller of the two shares. If both clear 0.5%, idea 175's line stands.
  2. **Panel.** In the same pass, add these families, each by square, pooled, and **state x output bucket**:
     - L2-1's file-line state;
     - L2-2's blockade occupant;
     - L2-3's loose and overprotected bits;
     - the "outpost proper" (own-pawn guarded and never attackable by an enemy pawn: the conjunction tier A did not
       test);
     - the absolute 7th (rook on the 7th with the enemy king on the 8th);
     - the bad bishop (own rammed pawns on the bishop's colour).

     The last two are predicted null by section 0's filter; they are controls for the filter itself.
  3. When the deep-label set (X7 or the larger-teacher relabel) exists, rerun the panel against it. That is the only
     way to test reason 3.
- **Cheapest form, speed cost, data needs.** None in the engine. CPU only, on the existing g4c 600 k and g4s2-val
  dumps; about 1-2 CPU-hours with the new families' python-chess state functions.
- **Cheapest falsifying test.** It is a measurement. The deciding readings:
  - If calibration shows the known winners at or above 0.5%, idea 175's kill stands as calibrated. L2-1 to L2-3
    must clear 0.5% too, and the classical-state line closes cheaply if they don't.
  - If the winners fall far below 0.5%, the line is miscalibrated. Idea 175's states should be re-read against the
    new line (the owner decides) before more state ideas are killed by it.
  - If the two predicted-null controls show material shares, section 0's filter is wrong, and the cheap-concept
    rows of its table need testing too.
- **Novelty and nearest relatives.** Fork's own R36 rule and `state_rows_study.py` (idea 175). Using the rule's
  known positives as calibration is standard practice in measurement. It is not on file for this rule as far as I
  found. A grep of ideas.md for calibration of R36 found none; UNVERIFIED beyond that grep.
- **Rough expected Elo and chance.** No Elo of its own. It decides about 12 EU of input work (L2-1 to L2-3 plus any
  re-read of idea 175). Cost about 0.75 EU (est.).

---

## Ranking (this lens)

| Rank | Idea | Cost to kill (EU) | Full cost (EU) | Net STC central (est.) | Chance | Expected Elo per EU (est.) |
|---|---|---|---|---|---|---|
| 1 | **L2-4. Calibrated classical panel** (shared falsifier) | 0.75 | 0.75 | n/a (decides ~12 EU) | n/a | enabler |
| 2 | **L2-1. File-line contact state** (open-file fight, doubling, clear file) | 0.3 | 5 | +2 | 20% | 0.08 |
| 3 | **L2-3. Defence surplus** (loose / overprotected), only on L-exact | 0.2 | 3 (on top of 178) | +2 | 15% | 0.10 conditional, else 0 |
| 4 | **L2-2. Blockade occupant of passed pawns** | 0.2 | 4 | +1.5 | 15% | 0.06 |

Read it this way: the classical lens' main finding is negative. Most of what the books teach (outposts, holes, bad
bishop, 7th rank, space, bishop against knight) is low-rank pawn-and-piece structure that one SCReLU layer forms
cheaply, which is what idea 175 measured. What a single layer cannot form is the part of classical theory about
**lines through pieces and counts of protection**: the fight for the file, the protected blockade, overprotection.
That is the same territory as Fork's threat work, where the fixed-node gains were real and the speed price killed
them. These three proposals are its cheapest per-piece compressions. One CPU run (L2-4) should decide whether any of
them deserves an engine day. Run it before 178's prototype, since L2-1 and L2-3 would share 178's block.

## Sources

| # | Source | Author / edition | URL | Opened | Used for |
|---|---|---|---|---|---|
| 1 | *Chess Fundamentals* | J. R. Capablanca; Harcourt, Brace & World / G. Bell, copyright 1921 (17th printing, preface 1934); Project Gutenberg eBook #33870 (2010) | https://gutenberg.org/files/33870/33870-h/33870-h.htm | 2026-11-14 | §14 (bishop limited by own pawns; knight against bishop by structure; value by squares commanded), §28 (tying rooks to defence), §29 (open file, freedom of manoeuvre), §31 (holes; a passer grows stronger as pieces leave), §33 (influence of a hole), §4/§19 (co-ordination) |
| 2 | *My System*, Part I ch. 2 (On Open Files), ch. 3 (The 7th and 8th Ranks), ch. 4 (The Passed Pawn) | A. Nimzowitsch, tr. P. Hereford; Harcourt, Brace & Co., 1930; Wikisource transcription | https://en.wikisource.org/wiki/My_System/Part_1/Chapter_2 , .../Chapter_3 , .../Chapter_4 | 2026-11-14 | the outpost and its "hinterland", doubling as file control, penetration; the 7th as "end-game weapon", "absolute" 7th; blockade, the blockader's kind, "prisoners in their own camp", protect the blockader more than necessary |
| 3 | *My System*, table of contents and file page | Wikisource index; Wikimedia Commons (1930 Harcourt edition, marked public domain in the US) | https://en.wikisource.org/wiki/My_System ; https://commons.wikimedia.org/wiki/File:My_System.pdf | 2026-11-14 | edition and public-domain status; Part II ch. 5 (Over-protection) **not transcribed and not read**, so overprotection rests on I.4 §3a and CPW |
| 4 | "My System" (article) | Wikipedia | https://en.wikipedia.org/wiki/My_System | 2026-11-14 | publication history, the list of elements |
| 5 | *Common Sense in Chess* | Emanuel Lasker; J. S. Ogilvie, New York (lectures of 1895); Internet Archive OCR | https://archive.org/stream/commonsenseinche00laskrich/commonsenseinche00laskrich_djvu.txt | 2026-11-14 | the "weak point" / strong point (Nos. 7-8), open file and doubled rooks (Nos. 6-8), "don't attack unless you have some tangible superiority", blockade by a queen |
| 6 | *Lasker's Manual of Chess* | archive.org item (Russell Enterprises 2010, access-restricted); HathiTrust record (HTTP 403) | https://archive.org/details/laskersmanualofc0000lask ; https://catalog.hathitrust.org/Record/010248965 | 2026-11-14 | **not read** (no free text reachable); Lasker is represented by source 5 instead |
| 7 | CPW: Outposts; Rook on Seventh; Bad Bishop; Square Control; Connectivity; Space | Chess Programming Wiki | https://www.chessprogramming.org/Outposts (and /Rook_on_Seventh, /Bad_Bishop, /Square_Control, /Connectivity, /Space) | 2026-11-14 | how classical evaluations framed these terms (concepts only); Connectivity's Kopec et al. 1989 description; Square Control's stop and telestop control. /Blockade_of_the_Stop returned 404 |
| 8 | Glossary of chess; "Overprotection" (disambiguation) | Wikipedia | https://en.wikipedia.org/wiki/Glossary_of_chess ; https://en.wikipedia.org/wiki/Overprotection | 2026-11-14 | definitions of hole, blockade, bad bishop; overprotection has no glossary text in the parts read |
| 9 | Web searches (Gutenberg, archive.org, HathiTrust listings) | search results only | (as listed in the rows above) | 2026-11-14 | locating editions |
| 10 | Fork's own files (read-only) | this repository, branch phase-4 and proto branches | `docs/research/idea175-screens.md`, `docs/research/network-novelty-2026-11-14.md` (E1-E13), `docs/ideas.md` (40, 41, 46, 86, 157-161, 175-184), `proto/r3-king-d:docs/research/bakeoff-r3/option-d-context-vector.md`, `proto/r3-king-c:docs/research/bakeoff-r3/exposure-finder.md`, `docs/research/network-survey-2026-11/{shortlist,matrix}.md` (grep), `src/search/*.hpp` (grep for attack sets: none kept at evaluation) | 2026-11-14 | the cost lesson, idea 175's null, finder costs, the field's threat inputs |

## Clean-room statement

No chess, shogi or go engine's source code was opened: no GitHub source files, code listings, diffs, headers or
training scripts. The Chess Programming Wiki pages were read through a summarising fetcher told to report prose
concepts only and to reproduce no code, pseudocode, constants or weights. It reported that none of the six pages
contained code.
- The CPW Space and Outposts pages describe, in prose, terms used by named engines (a space count over central
  squares; an outpost bonus attributed to Toga's documentation). I took the concepts only, propose neither, and
  recorded no value.
- No constant, FEN or rule above is typed from memory as fact. The only numbers are Fork's own measurements (cited)
  and my estimates (marked "(est.)").
- Quotations from Capablanca, Nimzowitsch and Lasker are short phrases from public-domain editions, as returned by
  the fetcher's summaries. They were not checked against page scans character by character: treat each quote's
  exact wording as UNVERIFIED and its section number as the fetcher reported it.


# Appendix C: lens3-tactics.md (the lens agent's section, unedited)

# Lens 3: the Lichess puzzle-theme taxonomy (tactical motifs Fork's network cannot compose)

Read-only research, 2026-11-14 (late evening EST). Nothing was built, run, downloaded, edited or committed. Every
Elo or nps figure not citing a Fork measurement is an estimate, marked (est.). Names are placeholders; none has
been screened. The Lichess puzzle database was **not** downloaded (read-only session: no data jobs); its theme
frequencies are therefore unknown here (UNVERIFIED).

## 0. The frame: which relations a single SCReLU layer can and cannot form

This part is my own reasoning, not a measurement; it gives a falsifiable prediction (section 0.3).

### 0.1 What the layer computes
Fork's output is a linear head over SCReLU(a_c) = clamp(a_c, 0, 1)^2 for each of 512 columns per perspective, where
a_c = b_c + sum over active inputs i of W_ic. Inside the unclipped range this is a **quadratic form in the inputs**:
(sum_i W_ic x_i)^2 contains every pairwise product W_ic W_jc x_i x_j. So the layer can represent **two-body
relations** (piece A on square s together with piece B on square t) directly, up to its rank (1,024 columns over
both perspectives). Three-body relations, and relations that need a **negation over many squares** ("every square
between them is empty", "no defender exists"), are only reachable through the clipping corners, which is expensive
in columns and data. King regions (row choice by the own king's region) add a coarse third body (the region), not an
exact king square.

### 0.2 The Lichess themes sorted by that frame
Theme names and descriptions from lichess.org/training/themes (opened 2026-11-14). "Mover" = the side to move at the
evaluated leaf. Search facts are Fork's (DESIGN.md: quiescence = stand-pat, captures and queen promotions only, **no
checks**, at most 2 moves out of check since B16; SEE ignores pins, src/search/see.hpp; the training filter drops
in-check positions and positions whose best move is a capture or promotion).

| Theme (Lichess) | Relation the network must form | Order | Who suffers at a stand-pat leaf | Resolved by search? |
|---|---|---|---|---|
| Hanging piece ("undefended or insufficiently defended") | attacker present AND no (or too few) defenders | negation over all pieces | opponent's: quiescence takes it. Mover's: invisible to stand-pat | opponent's yes (qsearch); mover's no (2 plies) |
| Fork ("attacks two or more pieces simultaneously") | once played: two exposures at once; as a threat: a safe square hitting two targets | already-played: pairwise of exposures; threat: 3-body + safety | mover's (two exposed, only one saved) | already-played mover's: no at stand-pat; the opponent's next-move fork: 2 plies |
| Pin ("unable to move without revealing an attack on a higher value piece") | slider, pinned piece, king/queen collinear, squares between empty | 3-body + emptiness | both: the pinned piece neither escapes nor truly defends | partly: legality is exact in generated moves, but **SEE counts a pinned recapturer** (pruning may misjudge); piling on a pinned piece is a quiet move (depth >= 1) |
| Skewer, X-Ray attack ("attacks or defends a square, through an enemy piece") | slider, front piece, rear piece collinear | 3-body + emptiness | both | the capture after the front piece moves: depth >= 2 |
| Discovered attack / discovered check / double check | own slider, own blocker, enemy target collinear | 3-body + emptiness | the side facing it | mover's: depth >= 1 (qsearch has no checks); opponent's against the mover: 2 plies |
| Capture the defender, Deflection ("sometimes also called overloading"), Interference, Attraction | defender's duty set: one piece guarding two liabilities | counts per square (attackers vs defenders) | mover's at stand-pat; opponent's at depth 1-2 | opponent's partly by qsearch (2-capture cap); mover's no |
| Trapped piece ("unable to escape capture as it has limited moves") | piece AND every flight square unsafe | negation over 2-8 squares | both | **no**: the loss lands several plies later (attack, then win) |
| Back rank mate ("trapped there by its own pieces") | king on rank 1, flight squares blocked by own pieces, no own heavy piece guarding, enemy heavy piece can arrive | 4+ bodies | both | short mates yes (depth >= 3); the latent weakness, no |
| Exposed king, kingside/queenside attack, mate patterns | king zone x attackers | many-body | both | partly; owned by (b2)/d_kzone (in flight) |
| Advanced pawn, promotion | pawn rank (one body) or pawn + stoppers | 1-2 body | | learnable today (pawn links, piece-square rows) |
| Quiet move, Intermezzo, Zugzwang, Clearance, Collinear move | properties of a *sequence* | not a static feature | | search's job; no input proposed |

### 0.3 The prediction, and the evidence for it so far
- **Two-body relations are already learned.** Idea 175's residual study found that pawn-attack and pawn-defence states
  explain 0.032% or less of r8brft1's residual (docs/research/idea175-screens.md): "a piece attacked by an enemy pawn"
  is a pair relation, and the quadratic form holds it.
- **Relations with a line or a negation are not.** The exposure plane (attacked by a cheaper piece, or attacked and
  undefended: a negation) gained +25.67 at fixed nodes; x_lower (only "attacked by a cheaper piece") +17.60 (brief,
  SPRT log). If pawn attacks explain ~0, x_lower's gain must come mostly from **slider** attackers (bishop on a rook or
  queen, rook on a queen: a line through empty squares) and perhaps knights. That is testable offline (falsifier F0
  below), and it decides this whole lens: if line relations also explain ~0, every idea here dies cheaply.
- **Field evidence against x-rays as rows**: Fork's engine survey records that Coda gained +12.5 STC / +15.1 LTC by
  *removing* x-ray threats from its threat inputs, and that Stockfish's threat set has no x-rays
  (docs/research/network-survey-2026-11/speed.md A9, matrix.md rows 1 and 6; survey records, not code). So the
  proposals below avoid general x-ray rows and use narrow, already-computed line relations.

### 0.4 Which motifs the leaf evaluation needs (and which search covers)
- **Covered by search, leave alone:** the opponent's hanging pieces (quiescence captures them), the mover's own
  discovered attacks and forks (one quiet move, then captures: depth 1), short back-rank mates (depth 3+), sequence
  motifs (intermezzo, clearance, zugzwang).
- **Needed at the leaf:** (a) the mover's liabilities, since stand-pat assumes the mover keeps everything (idea 178's
  argument, which this lens supports); (b) the opponent's **next-move** double threats against the mover (forks,
  discovered attacks): 2 plies, never seen at stand-pat or at depth-1 cut nodes; (c) **pins**, because Fork's SEE
  treats a pinned piece as a defender, so SEE-based pruning can misjudge exactly those exchanges; (d) **slow
  motifs** (trapped pieces, back-rank weakness), whose cost lands beyond any leaf's horizon on both sides.
- **The training filter matters:** positions whose best move is a capture are dropped, so the net trains on quiet
  positions, yet it evaluates noisy ones at stand-pat. The mover's opportunities are what the search resolves; the
  mover's liabilities and the slow motifs are what the labels can teach and the search cannot.

---

## Idea L3-1. Pinned-piece rows in the liabilities block

- **What the network gains:** for each absolutely pinned piece (both sides; tier B: pinned to the queen) it knows
  the piece cannot leave the line and does not really defend, so "attack the pinned piece with a pawn" and "the
  defender is pinned" become visible at a quiet leaf. This also offsets Fork's SEE, which ignores pins.
- **Why it can't learn it today:** a pin is king square x pinned piece x slider, collinear, with every square
  between them empty. That is three bodies plus a negation over up to 5 squares. The quadratic form gets pairs, and
  H512's four regions place the king only coarsely. The links and piece rows have no line information.
- **Cheapest form:** extra rows, but few, kept in **idea 178's 64-column block**, found at evaluation as x_eval found
  exposure (not incremental). Encoding: per perspective, own/enemy x {P, N, B, R, Q} x 64 squares = 640 inputs. The
  king is never pinned, so there are no king rows. Each is trained factored (one shared delta per piece type plus
  per-square deltas), so the rare squares still train. Finder: Fork's `lone_shields` for both kings. The mover's set
  is the lazily cached `pinned()` that move generation reads at every node that generates moves (src/core/movegen.cpp),
  so at those nodes the mover's half is shared work. Tier B (pins to the queen) is one more `lone_shields` per queen.
- **Estimated speed cost (est.):** finder 2 `lone_shields` calls, about 4-6 slider lookups, about 1-2%. Rows: x_eval's
  rows cost about 7% at about 1.15 rows on 37% of evaluations, full width. Pins are rarer (their share of positions is
  UNVERIFIED; count it in F0), and at 64 of 512 columns about 1/8 of the row work, so under 1%. Ratio **0.975-0.985
  (est.)**, break-even +2.6 to +4.3 Elo at fixed nodes. If idea 178 is built, the block, loader bound and trainer
  split already exist, and the pin rows are one more input family in them. The idea-46 caution stands: rows confined
  to a column block break the net loader's int16 bound, which assumes at most 32 piece features, so the bound must be
  redone.
- **Data needs:** 640 rows x 64 columns = 41,000 weights. Even if only 10% of positions hold one pin (UNVERIFIED),
  1.2 B kept positions give about 120 M instances, thousands per weight. Ample, with the factoriser for rare squares.
- **Cheapest falsifying test:** F0 (below), the pin family's held-out residual share. **Kill** under R36's 0.5% line,
  once F0's positive control has calibrated that line. Then a zero-weight speed prototype on idea 178's block (or
  x_eval's code): **kill** below 0.97. Then a fine-tune arm (60 superbatches, warm start at zero deltas,
  bench-identical) with 2 seeds beside a control, then FN, then STC.
- **Novelty and nearest relatives:** pins are classical hand-crafted evaluation terms (CPW-style "pinned piece"
  terms; UNVERIFIED which engines use them). As a network input in a column block, I know of no precedent (UNVERIFIED).
  Nearest in Fork: idea 178 (same block, the same "liability" reading), d_kzone's "sliders on open and x-ray lines to
  the king" (a count, not per piece), and the State's pinned/discoverers bitboards. In the field: threat inputs
  without x-rays (survey A9). A pin is the one x-ray relation already computed for legality.
- **Rough expected Elo and chance (est.):** +4 to +10 at fixed nodes, net STC 0 to +5; chance 25%. Cost to a
  decision about 3 EU: F0 1 (shared), speed 1, fine-tune and screens 1. That is about **0.4 Elo per EU** expected.

## Idea L3-2. Next-move double threats against the mover (fork squares and discovery candidates)

- **What the network gains:** whether the opponent, on its next move, has a safe square from which a knight or a
  pawn push hits two of the mover's valuable pieces (king, queen, rook, or an undefended minor), and whether the
  opponent holds discovered-check candidates. These are Lichess's Fork and Discovered attack/check themes seen one move
  early: the mover's static score must pay for them because stand-pat and depth-1 cut nodes never see them.
- **Why it can't learn it today:** a knight fork threat is enemy knight x fork square x two targets x the square's
  safety. That is three or four bodies plus a negation (the square is not covered by the mover's pawns). The
  quadratic form gives knight-target pairs, not "two targets share one reachable square". A discovered-check
  candidate is king x blocker x slider on a line: the same structure as a pin.
- **Cheapest form:** an **output-layer feature**, appended to d_lite's vector (the vector machinery is in flight).
  Six values, side-to-move relative. Per side: knight fork squares (squares in the knight-attack sets of at least two
  of the opponent's K/Q/R or undefended-minor targets, reachable by an own knight, not attacked by enemy pawns, 0-3
  capped); pawn-push forks (pushes after which the pawn attacks two non-pawn pieces, 0-2); discovered-check candidates
  (the side's `discoverers()`, which `lone_shields` already computes, as a popcount). A linear head fits here, because
  the expected loss is about the smaller target's value: nearly additive, unlike E11's structure terms.
- **Estimated speed cost (est.):** knight-table lookups from at most about 5 targets per side, pairwise ANDs, one
  shift for pawn safety, and 2 `lone_shields` calls (shared with L3-1 if both are built). Compare d_pawnatk, 6 values
  from 2 shifts and 6 popcounts, which measured 0.983, and d_kzone, 8 magic lookups, 0.930. Estimate **0.97-0.98**,
  break-even +3.4 to +5.2 FN.
- **Data needs:** 6 values x 8 heads = 48 weights. Data is trivially ample. Positions with an open fork square are
  probably a few percent (UNVERIFIED).
- **Cheapest falsifying test:** F0's fork and discovery families (counts, pooled). **Kill** under 0.5% held out. Note
  the counter-risk: a 20k-node label already contains the fork, so the residual exists only if r8brft1 misses it.
  Then the zero-weight vector prototype, **kill** below 0.97, then a fine-tune of the head only (cheap: about 0.4
  GPU-hours).
- **Novelty and nearest relatives:** fork-threat terms are classical. Hand-crafted evaluations score "safe knight
  checks" and threats (UNVERIFIED which). Nearest in Fork: idea 46 rank 4 (dense danger vector: hanging,
  lower-attacked, safe checks, restricted pieces), d_kzone's safe-check-like counts, idea 46 rank 8 (stand-pat check
  under multiple threats: a search-side relative that would act on the same signal). A next-move fork-square count as
  a network output feature is novel as far as I know (UNVERIFIED).
- **Rough expected Elo and chance (est.):** +2 to +6 FN, net 0 to +3; chance 20%. About 2.5 EU to a decision,
  roughly **0.25 Elo per EU**.

## Idea L3-3. Attack-balance class for the mover's pieces (insufficient defence and overload), on idea 178

- **What the network gains:** Lichess's "insufficiently defended" half of Hanging piece, which also underlies
  Capture the defender and Deflection/overloading. A mover's piece attacked by at least two enemy pieces and defended
  by at most one (or attacked twice where a single defender guards two such pieces) is a liability even when no
  attacker is cheaper. Exposure (cheaper attacker, or attacked and undefended) misses it.
- **Why it can't learn it today:** it is a count comparison over every attacker and defender of a square, each a line
  relation for sliders: many bodies plus a threshold. Today no input carries a defence map. x_lower carries none
  either: its rule needs none, which is why it is cheaper.
- **Cheapest form:** one more class in idea 178's L-exact block. Per perspective: the mover's pieces {P, N, B, R, Q}
  x 64 squares flagged "under-defended" = enemy double-attack set AND NOT own double-defence set AND attacked. Each
  side's "attacked at least twice" set is built as att2 |= att & a; att |= a over its per-piece attack sets. L-exact
  already needs the mover's defence map, so this adds the two double sets. Overload proper (identifying the shared
  defender) is left out: it needs per-defender duty sets, too costly.
- **Estimated speed cost (est.):** L-exact itself is estimated at 0.95-0.96 (idea 178's file, UNVERIFIED). The
  double sets need per-piece attack sets rather than per-class unions: about the full finder's cost again for those
  pieces, plus rare extra rows in the block. Estimate **0.93-0.95 total**, against 178's control 0.95-0.96, so this
  increment must buy +2 to +4 FN by itself.
- **Data needs:** 320 rows x 64 columns = 20,000 weights. Under-defended mover pieces are common in tense middlegames
  (UNVERIFIED share). Ample.
- **Cheapest falsifying test:** F0's "under-defended, not exposed" family for the mover. **Kill** if its share is
  under a quarter of the mover's exposure share, or under 0.5% absolute. Built only if idea 178 survives its own
  screens. Decide after 178's result, not before.
- **Novelty and nearest relatives:** "squares attacked twice" maps are classical hand-crafted evaluation material,
  and SEE is the search's version. In Fork: the exposure plane (S512+X), x_lower, idea 178 L-exact, Fork's SEE. As a
  network input class: unknown (UNVERIFIED).
- **Rough expected Elo and chance (est.):** +2 to +5 FN over L-exact, net −2 to +2; chance 15%. About 3 EU after
  178's build, roughly **0.1 Elo per EU**.

## Idea L3-4. Slow motifs: trapped pieces and the back rank, as output-layer counts

- **What the network gains:** Lichess's Trapped piece (a piece with no safe flight square) and Back rank mate's
  precondition (king on the home rank, flight squares on the second rank blocked by its own pieces, no own rook or
  queen on the back rank, enemy rook or queen present). Both cost material or the game several plies after the leaf,
  so no leaf search resolves them, for either side.
- **Why it can't learn it today:** "every flight square unsafe" is a negation over 2-8 squares, each defined by enemy
  attacks. The back-rank precondition is king plus 2-3 own blockers plus the absence of guards plus an enemy heavy
  piece: four or more bodies. Idea 175's **king-shield class explained about 0%** of the residual, a warning: the
  pawn-only part of back-rank weakness is probably already learned, and only the heavy-piece part may be missing.
- **Cheapest form:** output-layer values appended to the context vector. Per side: trapped knights or bishops (0-2),
  trapped rooks or queens (0-2), with safe mobility from **d_mob's per-piece sets** (squares not own-occupied and not
  attacked by an enemy pawn; zero means trapped), plus back-rank-weak (0/1). Six values.
- **Estimated speed cost (est.):** the back-rank bit is a few bitboard operations (about 0.99-1.00). Trapped needs
  d_mob's attack lookups (d_mob measured 0.955). Riding on d_mob, if d_mob is ever adopted, it is nearly free (one
  compare per piece). Alone, about 0.955.
- **Data needs:** 48 weights. Trapped minors are rare (UNVERIFIED, perhaps under 1% of positions), but a linear head
  needs few examples.
- **Cheapest falsifying test:** F0's trapped and back-rank families. **Kill** each under 0.5%. Expect the back-rank bit
  to fail, by idea 175's shield result. Build trapped only as an add-on to d_mob, never alone at 0.955.
- **Novelty and nearest relatives:** classical terms (ideas.md line ~1393 already lists "Trapped Pieces" among
  classical topics), d_mob (mobility by type), idea 46 rank 4 ("restricted pieces"). Nothing new as a concept. The
  new part is only the pairing with Fork's output vector.
- **Rough expected Elo and chance (est.):** +0 to +3 FN, net about 0 unless d_mob is in; chance 10%. About 1.5 EU,
  about **0.1 Elo per EU**.

---

## The shared falsifier F0: one residual pass, families grouped by relation order (about 1 EU, CPU only)

Method: idea175-screens.md's held-out ridge study (state_rows_study.py's design: base table plus family table,
8 block folds, a share of held-out residual variance), on the same g4c 600,000 and g4s2-val 103,254 positions,
against the **current default** (r3kr1; r8brft1 too, for comparability with idea 175). Motif features come from a
Python bitboard finder checked against Fork's own `pinned()`/`discoverers()` on a sample, through a debug
`evalfens`-style dump or the C++ reference. Python-chess's pin helper could serve as a second check (its exact API
is UNVERIFIED).

Families, in one pass:
1. **Positive control:** the exposure plane, both cuts (x_lower, full rule), mover only and opponent only. These are
   known to gain +17.6 and +25.7 at fixed nodes. Their shares **calibrate the 0.5% line**: if the full exposure plane
   explains, say, 0.3%, then R36's line is too strict for threat inputs, and the owner should set a relative line
   (for example "half the exposure share") before reading anything else. Without this control, a family reading
   under 0.5% proves nothing, since E10 says loss and strength diverge.
2. Order test: "attacked by a cheaper **pawn or knight**" (pair relations) against "attacked by a cheaper **slider**"
   (line relations). The prediction of section 0.3: the slider half carries most of x_lower's share. If it does not,
   this lens's premise is wrong and L3-1 to L3-3 stop.
3. Pins (absolute; to the queen), per side.
4. Opponent's next-move fork squares and discovery candidates, against the mover.
5. Under-defended mover pieces that are not exposed.
6. Trapped pieces and the back-rank bit, per side.
Also count each family's share of positions (the UNVERIFIED prevalences above). Kill lines as each idea states.

**Optional, owner's ruling needed:** the Lichess puzzle database (CC0, 6,193,530 puzzles, last updated 2026-11-11)
could later serve as a motif-tagged **diagnostic** set: how far Fork's static evaluation sits from its own search
at each puzzle's start position, by theme. Its positions come from human games, but puzzle selection and the
solutions were made by Stockfish ("re-analyzed with Stockfish NNUE at 40 meganodes"), and the themes by a program
tagger. Non-negotiable 6 bars engine-generated data, so it should never be used for training. Whether even
diagnostic use of an engine-selected position set is allowed is for the owner (UNVERIFIED as permissible).

## Ranking (this lens)

1. **F0, the shared residual pass with the exposure positive control** (about 1 EU, no GPU): it settles the lens's
   premise, which line relations are missing, and calibrates the 0.5% line that killed idea 175, for every later
   threat-input proposal.
2. **L3-1, pinned-piece rows in the liabilities block:** the only motif whose relation the net provably cannot form,
   whose finder Fork already runs for legality, and which also covers a known blind spot of Fork's SEE. Best alongside
   idea 178 (shared block).
3. **L3-2, next-move double-threat counts:** cheap, nearly additive, and aimed at the 2-ply blind spot of stand-pat.
4. **L3-3, the attack-balance class:** only as an increment on 178's L-exact, decided after 178.
5. **L3-4, trapped and back rank:** only as an add-on to d_mob. The back-rank bit is expected to fail.

## Sources

| Source | Author | URL / path | Opened | Used for |
|---|---|---|---|---|
| Puzzle themes page | Lichess (lichess.org) | https://lichess.org/training/themes | 2026-11-14 | the theme list and one-line descriptions (pin, skewer, x-ray, fork, hanging piece, trapped piece, deflection = "overloading", back rank mate, discovered attack/check, quiet move, etc.) |
| Lichess open database, puzzles section | Lichess (database.lichess.org) | https://database.lichess.org/ (puzzles section) | 2026-11-14 | CC0 licence, 6,193,530 puzzles, CSV fields, FEN/Moves conventions, "only moves", Stockfish NNUE 40-meganode verification, automatic tagging, last update 2026-11-11 |
| (not opened) lichess-puzzler tagger and generator | ornicar | github.com/ornicar/lichess-puzzler (linked from the database page) | **not opened** (code) | nothing |
| Fork: brief, idea 175's screens, idea 178, ideas 46/175-184 | Fork project | the lens agents' common brief (not committed); docs/research/idea175-screens.md; docs/ideas.md (ideas 46, 175-184) | 2026-11-14 | residual method, 0.5% line, prior that pawn relations explain ~0, idea 178's design and costs |
| Fork: novelty proposal | Fork project (Fable) | docs/research/network-novelty-2026-11-14.md (evidence E1-E13, idea 4) | 2026-11-14 | the cost lesson, the liabilities-plane reasoning |
| Fork: exposure finder report | Fork project | proto/r3-king-c: docs/research/bakeoff-r3/exposure-finder.md | 2026-11-14 | finder vs row costs (x_find_only 0.939, x_eval 0.865, x_lower 0.932) |
| Fork: context-vector report | Fork project | proto/r3-king-d: docs/research/bakeoff-r3/option-d-context-vector.md | 2026-11-14 | per-component output-feature costs (d_pawnatk 0.983, d_mob 0.955, d_kzone 0.930, d_lite 0.923) |
| Fork: engine survey | Fork project | docs/research/network-survey-2026-11/matrix.md, speed.md (A9) | 2026-11-14 | field evidence on x-ray threats (Coda's removal, Stockfish's set without x-rays); survey records, no engine code |
| Fork: source (own code) | Fork project | src/core/position.hpp, position.cpp, movegen.cpp; src/search/see.hpp; docs/DESIGN.md (qsearch, training filter) | 2026-11-14 | lazy `pinned()`/`discoverers()` via `lone_shields`, movegen reads `pinned()`, SEE ignores pins, qsearch has no checks, 2-move cap |

## Clean-room statement

No engine's source code was opened: no chess, shogi or go engine source, no code listing, diff, header, training
script or config. That includes the Lichess puzzler's tagger and generator, which are linked from the database page
and deliberately not opened. The only pages read were two Lichess prose pages (the themes list and the database
documentation) and Fork's own files and source. Field facts about other engines come only from Fork's survey records
(prose summaries of public notes), cited as such. No page turned out to show code. The SCReLU "quadratic form"
argument and every motif encoding are my own reasoning. No constant, FEN or rule was typed from memory as a fact.
Lichess's theme descriptions are quoted from the page as fetched.


# Appendix D: lens4-go.md (the lens agent's section, unedited)

# Lens 4: KataGo and the Go engines (read-only, 2026-11-14)

**Status.** Read-only research. Nothing was built, run, trained or committed; no job was started. Every Elo, nps or
training-time figure that does not cite a logged Fork measurement is an estimate, marked "(est.)". Names are
placeholders; none has been screened. KataGo's numbers below come from two summarising fetches of the paper's
HTML (v5), not a character-by-character reading, so treat them as **UNVERIFIED** until someone checks the text.

## What the Go sources say, in one table (concepts only)

| Go method (source) | What it does in Go | Reported effect | Where it already sits in Fork |
|---|---|---|---|
| Playout cap randomisation (KataGo §3.1) | about a quarter of turns get a full search and are recorded for the policy; the rest are fast and unrecorded | 1.37x compute factor when removed (Table 2) | **done**: idea 13, H1 at +65.47 ± 12.90 STC. Not proposed again |
| Global pooling bias (KataGo §3.3) | per-channel mean, scaled mean and max over the board, through a small linear layer, added back as channel biases; lets a local convolutional net condition on global context (ko, "simplify when winning") | 1.60x | output buckets by phase; XGR's learned phase gate. **Idea 4 below** |
| Ownership and score targets (KataGo §4.1) | predict who owns each point at game end, and the final score distribution; training-only heads; the stated reason is credit assignment ("direct feedback on which area of the board was mispredicted") | 1.65x for ownership and score removed **together** (not separated) | ideas 14, 65 (material ahead, mobility, king danger), 67 (draw head). **Idea 2 below** |
| Opponent's reply policy (KataGo §3.4) | a second policy head predicting the opponent's next move, loss weight 0.15, "for regularization only and never actually used for play" | 1.30x | idea 46's rank 1 (auxiliary threat targets), idea 54 (policy head at inference). **Idea 1 below** |
| Hand-made input features (KataGo §4.2; AlphaGo 2016) | liberties 1-3, ladder status, pass-alive regions: things a net finds hard to compute | 1.55x (with two pass-handling tweaks) | threats, exposure, pawn links, king regions (all tried). **Idea 3 below** (the ladder lesson) |
| Forced playouts and policy target pruning (KataGo §3.2) | MCTS root exploration with the extra playouts removed from the target | 1.25x | MCTS only; not applicable |
| Policy surprise weighting (KataGo methods doc) | sample positions more often where search and prior disagree | "one of the larger" gains, no number | idea 155 (surprise-guided saving); reweighting has lost twice in Fork (class weights −7.60; idea 52's oversampling) |
| Short-term value targets and error-prediction heads (methods doc) | heads trained on averaged future search values; heads predicting the value's own squared error | partial test; 75 Elo with variance-scaled cPUCT | idea 51 (credited to KataGo), ideas 50, 56, 153 |
| Subtree value bias correction (methods doc) | learn the net-vs-search error by local pattern, correct node values | 30-60 Elo | Fork's correction history (idea 17 family) is the alpha-beta form |
| AlphaGo Zero (Silver et al. 2017) | one residual tower with joint policy and value heads; 17 raw planes, no hand features | from memory: the joint ("dual") net beat separate nets, the paper saying the shared policy target regularises the value. **UNVERIFIED**: the PDF could not be read here | relevant to idea 1 |
| Leela Zero (README) | a "fairly faithful reimplementation" of AlphaGo Zero, 18 input planes; no auxiliary heads or data-efficiency methods described | n/a | nothing new to take |

The paper also says the auxiliary policy targets and global pooling "showed little effect early on compared to later
in the run", and the ownership and score targets helped "even up through the ends of those runs" (§4.1, §5.2, as
fetched). Read the 1.3-1.65x factors with care: they are measured inside an RL loop (a better net plays better games,
which train a better net) and on a 19x19 board at low data per weight. Fork trains supervised on fixed data, with
about 600 positions per first-layer weight on r3kr1's body (E5: training levers are nearly spent; E10: loss does not
predict strength). I expect the transfer to be a small fraction of the Go figures.

**Constraint found while reading (applies to ideas 1 and 2).** The KB's bullet notes (bullet-internals.md §7, branch
kb) say custom input types at Fork's pin "see only the `ChessBoard`": side to move, pieces, score, result. A target
that depends on the **future** (the next moves, a later position) is not in that record. Ideas 1 and 2 therefore need
a carrier for per-position extra targets beside the `ChessBoard` (spare record bytes, or a side buffer in Fork's own
loader built on the lower-level API). Whether either works at the pin is **UNVERIFIED**; I put it at 1.5 engineering
days (est.). The same notes list `exp` but no `log` among the pointwise ops, so a softmax cross-entropy may not be
expressible. Both ideas are written below with per-output sigmoid and squared error, the form the main loss already
uses. `build_custom` returning (output, loss) does allow a summed loss (KB §7, "activation-sparsity penalty" row).

---

## Idea 1. Reply-square auxiliary head ("the opponent's reply", training only)

- **What the network gains.** The first layer is pushed to encode **what happens next**: where the side to move's
  chosen quiet move goes, and where the opponent's reply lands. That is threat knowledge ("this piece is about to be
  hit", "this square is where the action is"), learned from the search's own verdicts rather than from hand-written
  threat maps. Fork's evidence says this is the missing knowledge: every threat input won at fixed nodes and lost on
  the clock (E4: S512+X +25.67 FN, −30 STC; x_lower +17.60 FN, −3.16 speed-adjusted). This idea asks for some of that
  fixed-node gain at **zero inference cost**.
- **Why it can't learn it today.** The only gradient into the 512-wide layer comes from one scalar per position, a
  blend of a 20,000-node score and the result. A threat that the search resolves (the reply wins a piece, the
  stand-pat is wrong) shows up only as a small, noisy shift of that scalar, spread over every active row. Nothing
  tells the layer *which* piece or square carried it. That is KataGo's credit-assignment argument, moved from
  territory to tactics. The training filter keeps only positions whose played move is quiet (no capture, promotion or
  check; idea175-screens §1), so for a kept position the reply is where the opponent's threats show up.
- **Cheapest form.** A training-only head, dropped at export.
  - From the same 2 x 512 SCReLU activations, 256 sigmoid outputs: own move's from-square (64) and to-square (64), the
    opponent's reply from-square (64) and to-square (64), all side-to-move relative (flipped as the inputs are).
  - The targets are one-hot, with squared error on the sigmoid, weighted by λ_reply (a placeholder: a constant that
    needs its own justification. KataGo's 0.15 is a different loss on a different scale and must not be copied; a
    2-point sweep on a fine-tune decides it).
  - The targets come from the game records: the move played from the position, and the next move. Unsaved records
    are still in the stream, so the reply exists even when the next position is not kept. Fork's datagen plays the
    search's best move at saved positions, but whether any randomness is added after the opening is **UNVERIFIED**.
  - No row, no output feature, no change to the shipped net.
- **Estimated speed cost.** Inference: **zero**. The exported file has to be byte-for-byte the shape of today's
  architecture 9 (check file size, layer shapes, bench nps with `bench/ab.py`, as idea 14 requires). Training: a dense
  1024 x 256 matmul per position, about 8x the sparse first-layer forward. On the GPU I expect +30-60% per superbatch
  (est.).
- **Data needs.** About 262,000 head weights, training-only, so about 4,500 kept positions per weight on 1.2 B. No new
  positions; one CPU pass over the shards builds the 4-byte target per record (a few CPU-hours, est.).
- **Cheapest falsifying test.**
  1. A fine-tune pair from r3kr1: 60 superbatches with the head at the chosen λ against the same-recipe fine-tune
     without it, 2 seeds each (about 1.6 GPU-hours with the slowdown, est.).
  2. FN screens of both seeds against the control. **Kill:** pooled FN at or below 0.
  3. A diagnostic only, not the decision: the head's top-1 accuracy on held-out games, and the residual on positions
     where the reply was a capture.
  - Caveat: KataGo found these targets matter more late in a run, and a warm start has its representation already
    set. A flat fine-tune is therefore weak evidence against a full retrain; the owner decides whether a 2.2
    GPU-hour retrain arm follows.
- **Novelty and nearest relatives.**
  - In Fork: idea 46's rank 1 ("auxiliary threat targets: a training-only head predicting hanging pieces and king-zone
    attacks"). That one uses static maps from a threat finder; this one uses the search's played moves, so it needs
    no finder and covers only threats that mattered.
  - Idea 54: the same head kept at inference for ordering. This is its training-only half; if 54 is ever built, it
    reuses this head.
  - Ideas 14 and 65: scalar extra targets.
  - In the field: KataGo's opponent-reply target (the direct source); AlphaGo Zero's joint policy and value
    (UNVERIFIED); Lc0's policy head, used at inference.
  - I know of no alpha-beta NNUE value net trained with a move head that is dropped at export. **UNVERIFIED**: no
    prior-art search was made, and a forum may have tried it.
- **Rough expected Elo and chance (est.).** +3 (−2 to +8) at STC, chance 25%. Cost: target carrier 1.5 EU, target
  builder and head 1 EU, GPU and screens 0.5 EU, so 3 EU to a decision. **0.25 Elo per EU.**

## Idea 2. Square-fate auxiliary target (the ownership analogue, training only)

- **What the network gains.** A dense, local picture of how the game goes from here: which squares each side still
  holds pieces on at a later point in the same game, and which piece types survive. KataGo's argument applies
  directly. The result is a function of finer variables, and predicting those gives "direct feedback on which area of
  the board was mispredicted". In chess that means which wing collapsed, which pawns fell and which pieces were
  traded off. This feedback is local, and the scalar target cannot give it.
- **Why it can't learn it today.** As for idea 1: one scalar per position. The TD(0.9) blend carries future
  information, but only as a level, never as a location. A defence that fails on the queenside teaches the same
  gradient to every active row, kingside pieces included.
- **Cheapest form.** A training-only head, dropped at export.
  - Main block, 128 sigmoid outputs: for each square, an own piece or an enemy piece stands on it H plies later.
    Side-to-move relative, H a placeholder: KataGo uses game end. Fork's games often end by adjudication, which is
    still a future position, so "game end" and one short horizon are the two candidates, chosen by a 2-point sweep.
    No value typed from memory.
  - Plus 10 sigmoid outputs: the fraction of each side's knights, bishops, rooks, queens and pawns still on the board
    at H.
  - Squared error, weight λ_fate (placeholder, swept).
  - Distinct from idea 65's mobility and king danger. Those are functions of the **present** position: code could
    compute them exactly, so the head would learn a hand feature. Fate is an observed **future** outcome: new
    information, like the result but local and dense.
  - Idea 65's "material balance some plies ahead" is the scalar sum of the 10 type outputs. This is its dense
    refinement, the step from KataGo's score target to its ownership target.
- **Estimated speed cost.** Inference: **zero** (same shipped shape; verify as in idea 1). Training: a 1024 x 138 dense
  head, +20-40% per superbatch (est.).
- **Data needs.** About 141,000 head weights, so about 8,500 positions per weight. No new positions. The targets need
  each game replayed to H: one CPU pass, a few CPU-hours (est.). The record needs 17-18 bytes per position (128 bits +
  10 fractions at 8 bits), so the carrier question of idea 1 is sharper here.
- **Cheapest falsifying test.** The same design as idea 1, and **run together with it**: one carrier, one builder, a
  three-arm fine-tune (control, reply, fate) at 2 seeds each, about 2.4 GPU-hours (est.). **Kill:** pooled FN at or
  below 0. Diagnostic only: held-out fate accuracy by output bucket. The prediction that would support the mechanism
  is a larger gain on queens-on material-level positions (E8).
- **Novelty and nearest relatives.** KataGo's ownership target (the direct source). In Fork: idea 14 (material change
  over the next moves), idea 65 (material ahead, iteration change, mobility, king danger), idea 67 (draw head, a
  result refinement). Novelty for chess NNUE: **UNVERIFIED**; I know of no NNUE trained on future square occupancy.
- **Rough expected Elo and chance (est.).** +2 (−3 to +6), chance 20%. Standalone 3 EU (0.13 Elo/EU). As the second
  arm on idea 1's carrier, the marginal cost is about 0.8 EU (**0.5 Elo/EU marginal**).

## Idea 3. Pin and discoverer delta rows (the ladder lesson)

- **What the network gains.** Long-range forcing geometry: "this piece is pinned to its king" and "this piece shields
  a slider's line to the enemy king" (a discovered-attack candidate).
  - KataGo's and AlphaGo's lesson is that a net struggles with a precise long-range condition, the ladder, which a
    few lines of code compute exactly. Pins are chess's nearest equivalent.
  - A pin is a conjunction of three pieces plus the emptiness of every square between them. A single 512-wide SCReLU
    layer forms at most pairwise products of rows, and it cannot see emptiness at all (there are no empty-square
    inputs).
- **Why it can't learn it today.** Today's inputs are piece-square rows, pawn links and the king region, and none
  encodes "nothing between these two". The net can learn "a bishop on b5 and a king on e8 with a knight on d7" as a
  pairwise statistic. It cannot learn that a piece on c6 breaks the pin.
- **Cheapest form.** Extra delta rows, not fused row choices.
  - A pinned non-king piece adds one delta row indexed by (colour relative to the perspective, piece type, square):
    5 x 64 x 2 = 640 rows per perspective. Optional tier 2: discoverers on the same layout, another 640.
  - The delta rows are **shared across king regions**, so H512+PP's table does not multiply. Folded variants would
    multiply it by 4 (the trap that made idea 175 an alternative to option (a)). Table: +0.64 MB (+1.3 MB with tier 2).
  - The finder already exists. `Position::pinned()` is a lazily computed, cached bitboard (src/core/position.hpp,
    `lone_shields`), and so is `discoverers()`. Movegen's legality usually reads the side to move's pin set at a node,
    so only the other colour's set is new work (whether movegen reads it at most evaluated nodes is **UNVERIFIED**).
  - The update stores both colours' pin sets in the accumulator entry and applies an XOR diff: one row per pin that
    starts or ends, two when a pinned piece slides along its ray.
- **Estimated speed cost.**
  - Rows: pins change on a minority of moves (slider moves, king moves, interpositions). I guess 0.1-0.2 extra rows
    per perspective update against today's 3.09 (est.; one stats run settles it). That is +3-6% of update work, about
    1-1.5% of cycles.
  - Finding: one `lone_shields` call per colour per updated node. Idea 175's lesson is that the finder can dominate
    (its finder alone ran at 0.923), but this one is a single ray scan from each king, not a test per piece.
  - Ratio 0.96-0.985 (est.). The break-even at 0.97 is +5.2 Elo at fixed nodes (−118·log2 0.97).
- **Data needs.** 640 rows x 512 = 328,000 weights. Prevalence is the open question: how many kept quiet positions
  hold a pin, and how many per (type, square) cell. That is **UNVERIFIED**; one `fork-train stats`-style pass counts
  it. At a guessed 10% of positions, each delta row would see about 190,000 pinned instances (est.). The training
  filter drops tactical positions, so pins in kept positions are mostly the quiet, long-lived kind, which is the kind
  that matters to a static eval.
- **Cheapest falsifying test.**
  1. CPU, about half a day: the idea 175 residual study, unchanged (tools/nnue/state_rows_study.py's method). Fit an
     additive table over (relative colour, type, square, pinned) beside the base table, 8 block folds, held out, on
     r3kr1's residual on g4c and g4s2-val. **Kill** under 0.5% of residual variance: R36's line, which every idea 175
     state missed by a factor of 15 or more. Tier 2 (discoverers) is tested in the same pass.
  2. Only then a zero-delta speed prototype (bench-identical, 20 interleaved rounds). **Kill** below 0.95.
  3. Then two seeds beside a same-recipe control, speed-adjusted FN, STC.
  - Honest prior: idea 175's pawn-relation states explained 0.006-0.107% together, and quiescence resolves the
    tactical half of pins (an attacked pinned piece gets captured in the qsearch line). My chance that step 1 clears
    0.5% is about 20%.
- **Novelty and nearest relatives.**
  - Classical handcrafted pin terms are textbook.
  - NNUE threat inputs (survey) encode attacker-victim pairs, not x-rays through a third piece. Whether any NNUE has
    a pin input is **UNVERIFIED**.
  - In Fork: idea 175 (state-folded rows: same family, different state, killed by its residual share and speed),
    idea 178 (side-to-move exposure rows), x_lower, the exposure plane.
  - In Go: ladder features (AlphaGo 2016; KataGo §4.2).
- **Rough expected Elo and chance (est.).** +2 at STC net of speed (−6 to +8), chance 15%. Cost to kill 0.5 EU, full
  cost about 6 EU. **0.05 Elo per EU** to the end; **the kill test is cheap** (0.5 EU, no GPU).

## Idea 4. Self-routed heads (the global-pooling analogue)

- **What the network gains.** The chance to pick its own context for the output layer.
  - KataGo's global pooling exists because a convolutional net cannot condition local judgement on global state; its
    own example is "simplify when winning, complicate when losing". An NNUE accumulator is already global, so the
    pooling half is free. What Fork lacks is the **conditioning** half: the head is chosen by a hand-written phase
    count, and idea 180 found that rescaling by phase or queen state adds nothing.
  - The proposal: let a hidden unit the network itself learned choose the head.
- **Why it can't learn it today.** The output is one linear function per phase bucket of the squared activations.
  "Unit 37 is active" cannot change how every other unit is weighed. That needs a product of three activations, and a
  linear head over squared activations cannot form one. Idea 176's count found 74 of 512 columns with queens-on use
  4x or more their queens-off use, so the layer already builds context-detector units. Nothing downstream uses them
  as context.
- **Cheapest form.** An output-layer change with **no per-eval work**.
  - Head index = (phase bucket, bit). The bit says whether a designated hidden column j is active (pre-activation
    above 0) in the side to move's accumulator. This is one int16 read and a compare; 0 and SCReLU's saturation point
    are the natural thresholds, so no new constant.
  - 8 heads become 16: +16 KB in the file, the same single dot product per eval.
  - Training: blend the two heads by a steep sigmoid of column j in training, hardened at the end. This could be
    built from the existing pointwise ops, but the `broadcast_across_rows` gate's compile is **UNVERIFIED** (KB §7).
    Alternatively, a refit only (step 1 below).
  - Rejected variant: KataGo's literal form, k pooled channels added back as biases to all 512 columns, costs about
    2k 512-wide row-equivalents per evaluation. At 0.524 evaluations per node that is 0.85-0.90 (est.) for k = 4, and
    it fails the gate.
- **Estimated speed cost.** About 1.00 (est.): one load and a compare per evaluation. The head table doubles but stays
  in L1/L2.
- **Data needs.** +8,192 head weights: trivial against 1.2 B.
- **Cheapest falsifying test.**
  1. CPU, about 1 hour (est.), no training: idea 82's probe method (tools/measure/head_probes.py; r3kr1's first layer
     frozen). Pre-rank the 1,024 candidate columns cheaply, e.g. by how differently the residual depends on the
     activations on either side of the split. Then refit 16 heads for the top 32 by least squares and measure
     held-out squared win-probability error against an 8-head refit on the same records. **Kill** if the best column
     gains less than idea 82's seed spread (0.00016 there; re-measure it for r3kr1).
  2. If it passes: one FN screen with the refitted heads. The only engine change is the head index, about half a day.
     **Kill:** FN at or below 0.
  3. Only then joint training (the soft gate).
  - Honest prior: idea 82's head refits were flat, and idea 180 was zero, so the head has shown little room.
- **Novelty and nearest relatives.**
  - XGR's learned phase gate: soft, and both outputs computed. Here the gate is hard, with one output.
  - Output buckets by phase or material (common); Triumviratus's material routing (survey); idea 159 (output experts
    by material class); idea 183/knot-tied heads; idea 176 (split-clone columns, regime capacity inside the
    accumulator).
  - In ML: hard-gated mixtures of experts and conditional computation (Jacobs et al. 1991, as idea 53 credits;
    Shazeer et al. 2017 from memory, **UNVERIFIED**).
  - Routing an NNUE head on one of the net's own hidden units: novelty **UNVERIFIED**.
- **Rough expected Elo and chance (est.).** +2 (−2 to +5), chance 15%. Cost to kill 0.7 EU (CPU probe plus one FN
  screen); full cost about 2.5 EU. **0.12 Elo per EU.**

---

## Ranking (this lens)

| Rank | Idea | Central Elo (est.) | Chance | Cost to kill (EU) | Full cost (EU) | Elo per EU |
|---|---|---|---|---|---|---|
| 1 | 1. Reply-square auxiliary head | +3 | 25% | 3 (needs the carrier) | 3 | 0.25 |
| 2 | 2. Square-fate auxiliary target | +2 | 20% | +0.8 on idea 1's carrier | 0.8 marginal / 3 alone | 0.5 marginal / 0.13 alone |
| 3 | 4. Self-routed heads | +2 | 15% | 0.7 | 2.5 | 0.12 |
| 4 | 3. Pin and discoverer delta rows | +2 | 15% | 0.5 | 6 | 0.05 |

Read it as two groups.

- **Ideas 1 and 2 are one project.** One target carrier, one CPU builder and a three-arm fine-tune test both
  KataGo-style auxiliary targets at zero inference cost. Their shared risk is that Fork's data-rich supervised regime
  is not where auxiliary targets pay (E5, E10). Idea 1 ranks first because it aims at threat knowledge, the one kind
  of knowledge Fork has measured as worth +17 to +26 at fixed nodes, and asks for it at no speed price.
- **Ideas 4 and 3 have cheap kills** (a CPU probe each, no GPU) but low priors from ideas 82, 180 and 175. Run them
  only if a quiet CPU hour is free.

## Considered and left out

- Playout cap randomisation: idea 13, done (+65.47).
- Policy surprise weighting: idea 155; reweighting has lost twice in Fork.
- Short-term value targets: idea 51.
- Uncertainty heads: ideas 50, 56, 153.
- Score or WDL distribution heads: idea 67, survey J19.
- Forced playouts and target pruning: MCTS only.
- Subtree bias correction: correction history.
- Multi-board-size masking: no analogue.
- Nested bottleneck blocks: a depth change, the AF-S family.
- KataGo's literal pooled-bias structure: priced and rejected under idea 4.

## Sources

| Source | Author / owner | URL | Opened |
|---|---|---|---|
| "Accelerating Self-Play Learning in Go", arXiv:1902.10565 (abstract page; v1 27 Feb 2019 … v5 9 Nov 2020) | David J. Wu | https://arxiv.org/abs/1902.10565 | 2026-11-14 |
| Same paper, HTML v5 (§3.1-3.4, §4.1-4.2, §5.2, Table 2; read through two summarising fetches) | David J. Wu | https://arxiv.org/html/1902.10565v5 | 2026-11-14 |
| "KataGo Methods" (docs/KataGoMethods.md; prose methods document) | David J. Wu (lightvector) | https://raw.githubusercontent.com/lightvector/KataGo/master/docs/KataGoMethods.md | 2026-11-14 |
| Leela Zero README (prose) | Leela Zero contributors (Gian-Carlo Pascutto et al.) | https://github.com/leela-zero/leela-zero/blob/next/README.md | 2026-11-14 |
| "Mastering the game of Go without human knowledge", Nature 550:354-359 (2017): PDF fetched but unreadable here (no PDF text tool); its dual-network claim is from memory, UNVERIFIED | Silver et al. (DeepMind) | https://rose-hulman.edu/class/cs/csse313/schedule/day17/AlphaGoZero.pdf | 2026-11-14 |
| Blog summary of the AlphaGo Zero paper (17 input planes, single network, Elo ratings) | Adrian Colyer, "the morning paper" | https://blog.acolyer.org/2017/11/17/mastering-the-game-of-go-without-human-knowledge/ | 2026-11-14 |
| Search results (bibliographic details of the AlphaGo Zero paper only) | various | https://ideas.repec.org/a/nat/nature/v550y2017i7676d10.1038_nature24270.html , https://arxiv.org/pdf/2502.10303 | 2026-11-14 (titles only) |
| AlphaGo (Silver et al., Nature 2016) ladder and liberty features: from memory, not opened, UNVERIFIED | Silver et al. | n/a | n/a |
| Jacobs, Jordan, Nowlan and Hinton (1991); Shazeer et al. (2017): from memory, UNVERIFIED | | n/a | n/a |
| Fork's own files (read-only): common brief; docs/research/network-novelty-2026-11-14.md; docs/research/idea175-screens.md (summary, §1-2); docs/ideas.md (ideas 13, 14, 46, 54, 65-67, 82, 153-156, headers); docs/DESIGN.md (XGR design-screen credits); tools/train/src/main.rs (header); src/core/position.hpp (pinned/discoverers, grep only); KB docs/kb/bullet-internals.md §0, §7 (branch kb) | Fork project | local | 2026-11-14 |

## Clean-room statement

I opened no engine's source code: no chess, shogi or Go engine source file, header, diff, training script or
config.

- KataGo's methods document is a markdown prose file in KataGo's repository. The fetch reported that its fenced
  blocks hold formulas and example probability distributions, not program code, and I used concepts only.
- The Leela Zero README contains shell build and command-line blocks. I did not read or use them, only the prose
  description of the network.
- The only code I read is Fork's own (the trainer header and a grep of position.hpp).
- The bullet facts come from Fork's KB notes. bullet is a training library, not an engine, and I did not open its
  source.
- No constant from any engine is proposed. Every weight, horizon and threshold above is a placeholder to be swept;
  the two natural thresholds are 0 and SCReLU's saturation point.
