# Never-tried techniques: ranking, shared-idea flags and test proposals

Survey of 2026-11-10. Row IDs refer to [comparison.md](comparison.md). Every
figure is the engine's own and every Fork estimate is a judgement
(UNVERIFIED until tested). Ideas are taken at concept level: Fork's form,
names and constants are its own, chosen by head-to-head selection and
screened before use (DESIGN.md §8).

## 1. How the score is built

**Evidence E (1-5).**
- Start from the number of independent engines with a measured gain that is
  not bundled with other changes, capped at 5.
- Add 1 if at least two of those gains were measured at LTC (each engine's
  own long control).
- Subtract 1 if an engine measured a loss with the idea, or gained by
  removing it.

**Fit F (1-5): fit for Fork.** Fork's constraints:
- the speed budget, priced at 1.72 Elo per 1% nps (DESIGN.md §5.6);
- about 1.5 B saved positions per retrain;
- single-digit GPU-hours per Kaggle arm;
- single-threaded STC and LTC testing on GitHub's shards, one SPRT at a
  time.

| F | Meaning |
|---|---|
| 5 | No runtime cost (or a negligible one). Existing tooling. Decided by one STC design-R test, or one Kaggle arm with Fork's standard gates |
| 4 | Also needs one of: an LTC confirmation (a pruning or TT change); a TT format change; a constant head-to-head with an interaction risk |
| 3 | Several constants, an LTC-only test, a hot-path change with an nps risk, or the owner must first rule that it is a new idea, not a retest |
| 2 | Heavy compute (a bigger net on GPU plus CPU relabelling), or Fork's own measurement already points the other way |
| 1 | Blocked: needs a feature Fork lacks or failed with, or it is outside Phase 4 |

**Score = E × F.** Ties are broken by the number of LTC results, then by
cost.

**Cost units** (Fork's own):
- an STC stage is 1,600 games, about 18 minutes of the 16-shard workflow;
- an LTC stage is 1,664 games at 40+0.4 and counts as 4 STC stages;
- design R stops for futility after 2 stages and is capped at 8 (at LTC,
  capped at 4-6 LTC stages);
- a head-to-head choice of a constant is 2 STC stages;
- a fixed-node (FN) screen is 1 stage;
- a Kaggle retrain arm is about 2-5 GPU-h, a fine-tune of a finished net
  about 0.3-1 GPU-h (the think tank's estimates; UNVERIFIED for 8c's data
  size);
- a quiet A/B speed check (`bench/ab.py`) is about 0.5-1 CPU-h.

## 2. The ranking (all 44 never-tried rows)

| Rank | Row | Technique | Evidence (engines; TC) | E | F | Score | Fit note |
|---|---|---|---|---|---|---|---|
| 1 | D8 ⚑ | Summed continuation score as each continuation table's update base | 5 engines: Hobbes +10.6, Tcheran +9.1, Quanticade +1.6 (STC); Tarnished +2.5 LTC, Integral +1.5 LTC | 5 | 5 | 25 | Fork has reply and follow tables updated like the butterfly table; no nps cost |
| 2 | D9 ⚑ | Bonus to the prior move when the child fails low | 4 engines: Hobbes +8.65 (STC); Halogen +2.65 LTC, Integral +2.0 LTC, Stockfish +1.4 / +1.3 LTC | 5 | 5 | 25 | S1 item 8 and R15's optional extra; history code already touched by R15 |
| 3 | B12 ⚑ | Check-aware pruning: LMP and futility relief for checking quiets (and in qsearch) | 4 engines: Reckless **+9.5 LTC**, pawnocchio **+9.0 LTC**, Raphael +2.2 / qsearch +5.2, Viridithas +3.1 STC | 5 | 4 | 20 | Fork's LMR check relief gained +11.26; a pruning change, so an LTC check too |
| 4 | F3 ⚑ | Early eval-only TT write | 6 engines: Integral +14.2, Lizard +14.7, Hobbes +12.2, Quanticade +8.0, Raphael +8.4 / +5.3 LTC, Ethereal +2.6 (8T +9.9 / +6.1) | 5 | 4 | 20 | Needs an eval-only entry state (bound None means empty) that passes the torn-write digest. Fork's eval is a cheap single layer, so the gain should be smaller than the peers' |
| 5 | F4 ⚑ | TT cutoffs gated by node type, or by score and node type agreeing | 6 engines: Raphael +8.5, Halogen +2.3 (STC); Hobbes +3.0 LTC, Ethereal +2.45 LTC (STC failed), Integral +1.7 LTC; Triumviratus damping +2.2 | 5 | 4 | 20 | Needs R4 and R6's expected-node-type label; a TT policy change, so tested at a TCEC-scaled hash (X23) |
| 6 | F10 ⚑ | Material-based eval scaling | 5 engines: Stormphrax +10.5, Motor +6.75, Hobbes +6.5, Tarnished +5.4 (STC); Raphael +2.9 LTC (failed STC) | 5 | 4 | 20 | Zero cost. It changes the evaluation the labeller searches with, so adoption seals a data part. Overlaps R33 |
| 7 | B10 ⚑ | Opponent-worsening RFP | 4 engines: Raphael +6.4, Hobbes +3.5, Quanticade +1.85 (STC); Berserk +1.1 LTC | 4 | 4 | 16 | Fork's own "rising" RFP lost (−3.78); this uses a different signal (the opponent's trend). A pruning change |
| 8 | B11 ⚑ | History-scaled pruning margins | 6 engines: Ethereal +7.0 / +2.3, Reckless +4.5 / +3.6, Raphael +2.0 LTC, Halogen +4.8, Quanticade +3.0, Tarnished +2.3 | 5 | 3 | 15 | Fork's LMR history term failed on magnitude (−10.81): X2's in-game magnitudes first, then one margin at a time |
| 9 | J6 | Activation or feature-transformer-output regularisation | Integral +5.2 LTC, Minke +5.0 / +3.7 LTC; Tcheran +16.0 bundled with data; Coda, Cinder, Raphael, Stormphrax use it | 3 | 5 | 15 | A trainer-only arm beside idea 71. On a single-layer net only the regularising effect applies, not the sparsity speed-up |
| 10 | D13 | Direct-check ordering bonus | 3 engines: pawnocchio +6.4, Integral +4.1 (STC); Raphael +6.3 / +2.8 LTC | 3 | 5 | 15 | One ordering term |
| 11 | B16 | Qsearch LMP | 3 engines: Raphael +5.1, Tarnished +4.1, Hobbes +3.3 (STC only) | 3 | 5 | 15 | Cheap; the think tank judged qsearch pruning's ceiling low (H §3.8) |
| 12 | C6 | Singular refinements (TT-PV window, beta from TT-move history, cutoff when the singular bar beats beta) | Hobbes +3.9 / +3.0 / +5.2 LTC, Integral +4.0 LTC, Tcheran +7.0 | 4 | 3 | 12 | LTC-only tests; Fork's singular constants are measured, so each refinement needs its own measurement |
| 13 | D6 | Threat-aware capture history | Raphael +4.15 LTC, Ethereal +2.3 / +1.4, Motor +2.0 | 4 | 3 | 12 | T56's quiet form lost; the owner must rule whether this is a new idea |
| 14 | D12 | Malus decayed by moves searched | Berserk +2.0 LTC, Integral +2.0 LTC | 3 | 4 | 12 | Overlaps the malus-scale SPSA dimension |
| 15 | F11 | Optimism | Raphael +5.9 LTC, pawnocchio +5.2 STC, PlentyChess +1.3 LTC (STC H0) | 3 | 4 | 12 | Zero cost; sign-dependent scaling; LTC-sensitive |
| 16 | B7 | NMP and RFP gates from the TT bound; NMP eval margin | Hobbes +4.5, +5.0, +13.05; Raphael +2.0; Halogen +3.4 LTC | 3 | 4 | 12 | UNVERIFIED which conditions Fork's NMP already has |
| 17 | J9 | Fine-tune on the newest data only | pawnocchio +13.6 LTC, Hobbes +8.9 LTC; against: Viridithas −57, −9.7 | 2 | 5 | 10 | A second arm of idea 70 at almost no extra cost (proposal below) |
| 18 | J16 | Result-against-eval and result-against-tablebase filters | Halogen +4.0 LTC, Minke +2.3 | 2 | 5 | 10 | A trainer-side filter; Fork's at most 5-piece positions are already tablebase-labelled |
| 19 | C16 | Child fail-high count in LMR | Tarnished +9.8; Stockfish null fail-high count +1.3 LTC | 2 | 5 | 10 | |
| 20 | D3 | Continuation history at 4 to 6 plies | Halogen +4.6, Hobbes +1.5 LTC | 2 | 4 | 8 | 1.2 MB per table per searcher |
| 21 | D15 | Low-ply history; no updates from shallow cutoffs | Lizard +2.7, +7.0; Stockfish +2.7 LTC (S1) | 2 | 4 | 8 | S1 item 9 |
| 22 | J18 | Loss shape (power above 2, pessimistic skew) | Motor +24 (early), Halogen +3.2 LTC | 2 | 4 | 8 | |
| 23 | J7 | Ranger optimiser | Tcheran +3.5, Integral +3.2 STC; Halogen (b) | 2 | 4 | 8 | |
| 24 | J11 | Relabel with a larger own teacher | Devre +21.7, pawnocchio +11.0 LTC, Tarnished +3-4 LTC; against: Viridithas −3 for static-output relabels | 3 | 2 | 6 | Idea 58. A bigger net plus a search relabel of about 1.5 B positions is heavy; idea 63's step 0 found more nodes on one net beat averaging three |
| 25 | J13 | SPSA of the net's last layer | Berserk +17.2 LTC; RubiChess rescale +2 to +6 | 2 | 3 | 6 | 8 outputs × 1,024 inputs is far more than R14's 7 parameters; a reduced form first (bias and scale per output) |
| 26 | I4 | 8-bit feature-transformer rows | speed only: Stockfish +5 to +11% nps, Berserk +2% nps | 2 | 3 | 6 | +5% nps ≈ +8.6 Elo by Fork's price if accuracy holds; quantization loss is the risk; `--qat` exists |
| 27 | F12 | Pin-aware SEE | Tcheran +7.6, Triumviratus +4.5 | 2 | 3 | 6 | SEE cost; UNVERIFIED whether Fork's SEE handles pins |
| 28 | E5 ⚑ | Correction update rules (gravity; losing-capture and repetition events) | 6 engines, four at LTC | 5 | 1 | 5 | Needs R34 |
| 29 | H5 ⚑ | Dual activation | 5 engines, four at LTC | 5 | 1 | 5 | Needs a multi-layer head (H4 failed) |
| 30 | C15 ⚑ | Correction size in LMR, RFP and futility | 7 engines, Reckless +3.8 LTC | 5 | 1 | 5 | Needs a correction table (R34) |
| 31 | G4 ⚑ | SPSA under SMP conditions | 5 engines (multi-thread gains, 1-thread losses) | 5 | 1 | 5 | Phase 6 |
| 32 | C17 | Alpha-raise reduction | Hobbes +12.5 (early) | 1 | 5 | 5 | |
| 33 | B6 | NMP verification | Igel +2.5 LTC, Lizard +2.0; against: Halogen gained by removing it | 1 | 4 | 4 | |
| 34 | F9 | Fifty-move hash buckets or halfmove inputs | Integral +3.7 LTC, Hobbes +2.3 (fortress books) | 2 | 2 | 4 | Fork's fifty-move scaling measurement lost to "off"; normal-book gains about 0 |
| 35 | I3 ⚑ | Sparse first-dense-layer inference | 4 engines (speed) | 4 | 1 | 4 | Needs H4 |
| 36 | D14 | Factorised quiet history | Hobbes +17.2 STC | 1 | 4 | 4 | |
| 37 | K7 | Adjudicated and unadjudicated data blend | Halogen | 1 | 4 | 4 | |
| 38 | A4 | Complexity time management | Tarnished +6.6 LTC; PZChessBot removed it | 1 | 3 | 3 | Phase 5 |
| 39 | A5 | Less time when behind on the clock | Stockfish +1.1 LTC; Triumviratus about 0 at 30+0.3 | 1 | 3 | 3 | Phase 5 |
| 40 | A6 | Surprise rule; more time in defence | Triumviratus only | 1 | 3 | 3 | Phase 5 |
| 41 | B19 | Mate-seeking mode | Stockfish (matetrack, not Elo) | 1 | 3 | 3 | Idea 22 |
| 42 | H9 | Material- or queen-routed input buckets | Triumviratus +10.3 (net alone); Stockfish (b) | 1 | 2 | 2 | Refresh cost, as H-512's king regions |
| 43 | H10 | Separate endgame net | PZChessBot (early) | 1 | 1 | 1 | S1: do not build |
| — | B13 | Quiet history pruning | Tarnished +8.9; 4 more engines | — | — | — | Not ranked yet: untested in a firing form (the dropped variant changed 30 bench nodes); eligible for a test with a threshold that fires (owner, 2026-11-10) |

## 3. Shared-idea flags

### 3.1 Shared ideas Fork never tried

Each of these has four or more engines with measured gains (⚑ in
comparison.md):
- **History and ordering:** D8 (summed continuation update) and D9 (prior
  move fail-low bonus).
- **Pruning:** B10 (opponent-worsening RFP), B11 (history-scaled margins)
  and B12 (check-aware pruning).
- **TT:** F3 (early eval-only write) and F4 (node-type cutoff gating).
- **Evaluation scaling:** F10 (material scaling).
- **Blocked by a missing prerequisite:** C15 and E5 (both need a correction
  table; R34 is their **gateway item** (owner, 2026-11-10)), H5 and I3 (both need a multi-layer head), and G4 (Phase 6).

### 3.2 Shared ideas Fork tried and lost

| Row | Idea | Peers | Fork | What the peers' record says about the gap | Recommendation |
|---|---|---|---|---|---|
| D5 | Threat-indexed quiet history | 15 or more engines, +1.75 to +17 | −6.08 ± 3.59 (cheaper-attacker buckets) | Most peers index by whether the from- and to-squares are attacked, a cheap boolean form. Fork's measured set lost to "off" in both variants | No retest of the quiet form on this net (T56's closure). The capture-history form (D6) is ranked separately; the owner rules whether it counts as new |
| H3 | King input buckets | near-universal; grown with data | H-512: FN +32, STC −24 at about 0.5 B positions; a bake-off round 3 candidate, the data having roughly tripled (owner, 2026-11-10) | Peers added buckets step by step as data grew, warm-started with a factoriser; several first tries failed on old data (Raphael) | Not before 8c. A warm-started bucket net (S2 N3) only with its refresh cost measured first; the think tank rated it WEAK |
| H4 | Multi-layer head | near-universal in the top 30 | AF-S: FN +42 / +10, STC −49 / −56 (speed, 32 cp quantization loss) | Peers' heads became cheap with integer or QAT inference and sparse first-layer matmuls; Raphael's float-head first try also lost at STC | Only after QAT and int8 work exist; not in Phase 4 (think tank WEAK) |
| H7 | Threat inputs | near-universal in the top 30 | XGR-512 and S512+X lost on speed (0.818 nps) | Peers took 30-36% speed losses and recovered them with incremental, lazy and SIMD updates, then widened the layer; the gains are LTC-heavy | Parked, as decided (S512cl dropped) |
| B15 | ProbCut | 10 engines, several at LTC (Integral +13.4, pawnocchio +8.7, Halogen +6.3) | −5.29 ± 3.58 | Peers' LTC-heavy record matches S2's caution | The owner's no-retest rule stands; listed only for the record |
| C10 | LMR history term | 5 engines, +5 to +17 | −10.81 ± 5.01 | The think tank's diagnosis (a mean shift) stands | R20 (centred form) as queued |
| E1 | Pawn correction table | 8 engines, often +10 to +22 at STC for the first table | −0.35 ± 3.72 at LTC, undecided | Peers' first tables came before pawn-structure inputs; Fork's net already has 608 pawn links | R34's passive ranking as queued |
| B8 | Improving flag in RFP | 3 engines | −3.78 ± 2.92 | Peers' gains are mostly in LMP and LMR uses | R17 as queued |
| C3 | Ungated negative extension | 5 engines | −8.73 ± 4.98 | Peers' gains come from gated forms (cut node, PV) | R40 as queued |
| F8 | Fifty-move eval scaling | 4 engines, mostly on fortress or endgame books | measured loss at every span | Peers' gains are near 0 on normal books | Stays closed |
| I2 | Refresh cache | 4 engines with king buckets | −5.3% nps for mirror-frame changes | The cache pays where king buckets force refreshes; Fork has none | Stays closed unless H3 returns |
| J8 | Longer low-LR final stage | 3 engines, small | 8a's cooldown and anneal-only arms lost to R1-avg | — | Closed |

## 4. Test proposals (top of the ranking, plus one cheap add-on)

Each proposal states the decision it could change and its cost (DESIGN.md
§1, the owner's standing principle of 2026-11-10). They are written as
candidates for the §5.6 order. None is scheduled.

| Row | Proposal | Decision it could change | Cost | Placement |
|---|---|---|---|---|
| D8 | Update each continuation table toward the summed continuation score instead of its own. No new constant | The reply and follow tables' update rule, before step 19's final retune tunes ReplyWeight and FollowWeight. H0 closes D8 and confirms the current rule | 0.5 eng day; bench change; 0.2 CPU-h stats; design R STC 2-8 stages (about 0.6-2.4 GitHub-h); 0 GPU-h | Step 12, right after R15 (same code) |
| D9 | A bonus to the prior quiet move when its child fails low, sized by a head-to-head | Whether history gets a third update event, and whether R15's optional extra becomes a documented item | 0.5 eng day; head-to-head 2 stages; design R 2-8 stages; 0 GPU-h | Step 12, with D8 |
| B12 | Exempt or relieve checking quiet moves in LMP and futility (and qsearch futility, if it ever returns), as check relief does in LMR | Whether Fork's check handling extends beyond LMR; the switch list of the removal round (R30) | 0.5 eng day; design R STC 2-8 stages, then LTC design R 2-6 LTC stages (8-24 STC-equivalents) as a pruning change | Step 12, after R7 |
| F3 | An eval-only entry state written at a node before its moves are searched; X1's TT-eval hit counters before and after; `bench/ab.py` for nps | Whether the TT entry format gains an eval-only state before Phase 6 fixes the shared-table layout and its torn-write check | 1 eng day (format, digest, tests); 0.5-1 quiet CPU-h A/B; design R STC 2-8 stages; LTC only if STC passes | Step 12, beside R13 (TT-eval hygiene), or speed sprint 3 |
| F4 | Allow a TT cutoff at a non-PV node only when the entry's score and the node's expected type agree (Fork's own rule, chosen by head-to-head) | The TT cutoff rule; whether R4 and R6's node-type labels also gate TT cutoffs | 0.25 eng day once R4 or R6 exists; design R STC 2-8 stages at the hash X23 prescribes; LTC 2-6 LTC stages (Ethereal's form passed only at LTC) | Step 12, after R6 |
| F10 | One material-dependent scale on the evaluation, with the material term chosen by head-to-head | Whether R33 starts from a single material term instead of fitted structure classes. A pass also changes the labeller's evaluation (a part seal) | 0.25 eng day; head-to-head 2 stages; design R STC 2-8; LTC 2-6 LTC stages (Raphael's pass was LTC-only); 0 GPU-h | Step 17, as R33's first variant |
| B10 | An RFP margin term from the opponent's eval trend (two plies apart), its size by head-to-head | Whether any trend term enters RFP after rising RFP's H0. A second H0 closes the RFP trend family for Phase 4 | 0.5 eng day; head-to-head 2; design R 2-8; LTC 2-6 LTC stages | Step 12, after R17 |
| B11 | One history-scaled margin (SEE pruning first) once X2's in-game magnitudes are known | Whether pruning margins read history at all, given the LMR history term's failure on magnitude | X2 (1-2 CPU-h, already step 1); 1 eng day; head-to-head 2; design R 2-8; LTC 2-6 LTC stages | After R20 (centred history) |
| J6 | An activation-regularisation arm in retrain 8c beside idea 71's weight-decay arm, the same control, data and seed | Which regulariser(s) join 8c; whether the standard recipe gains one | One Kaggle arm, about 2-5 GPU-h (UNVERIFIED for 8c); FN screen 1 stage; STC SPRT [0, 5] 1-5 stages if the screen reaches +5 | Retrain 8c (step 13) |
| D13 | An ordering bonus for quiet moves that give check directly, sized by head-to-head | The ordering score of checking quiets | 0.25 eng day; head-to-head 2; design R 2-8 | Step 12, with D8 and D9 |
| J9 (add-on) | A second arm of idea 70: the same result fine-tune on 8b's newest part only | Idea 70's data choice (all of 8b's data or the newest part); Viridithas's −57 says it can fail, so it never runs alone | +0.3-1 GPU-h; +1 FN stage; the SPRT only for the better arm | With idea 70, after 8b's SPRT |

**Budget.** The eight search proposals together cost about:
- 30-60 STC stages (9-18 GitHub-hours);
- plus up to 5 LTC confirmations (about 20-120 STC-equivalents);
- about 4 engineering days;
- and none of them costs GPU time.

The two training proposals add about 2.5-6 GPU-h, 2 FN stages and up to
two SPRTs. Step 12's existing queue is about 40 GitHub-hours (DESIGN.md
§5.6), so these would lengthen it by roughly a third to a half.

## 5. Open questions for the owner

1. **Which proposals join step 12, and where?**
   - *Recommendation:* add D8, D9 and D13 as one history-and-ordering group
     right after R15, before step 19's final retune. Add B12 after R7. Add
     F3 and F4 as a TT pair after R13 and R6. Do B10 after R17, and B11
     only after R20.
   - The ranking puts D8 and D9 first: five and four independent engines,
     zero nps cost.
2. **Idea 70's shape.**
   - *Recommendation:* run the newest-part arm (J9) beside the whole-data
     arm if 8b leaves at least 1 GPU-h of quota. Otherwise whole data only.
     Never newest-part alone.
3. **A regularisation arm in 8c beside idea 71.**
   - *Recommendation:* yes, as its own arm against the same control (J6).
     If both pass, test them together before the recipe changes.
4. **Retest policy for shared ideas Fork lost (§3.2).**
   - *Recommendation:* no blind retests.
   - King buckets and a multi-layer head only as new designs after QAT or
     int8 work, with their speed measured first.
   - The capture-history threat form (D6) needs a ruling: is it a new idea
     or a retest under T56's closure? The survey treats it as new but ranks
     it 13th.
5. **Material scaling (F10).**
   - *Recommendation:* make it R33's first and simplest variant, one SPRT,
     before fitting structure classes.
   - Report the labeller consequence (a part seal) before adoption.
6. **Int8 feature-transformer rows (I4).**
   - *Recommendation:* price it with X12's zero-row and throttle build
     first, then speed sprint 3. Adopt only with an A/B speed gain and
     parity within the quantization limits.
7. **Category 4 disclosure (precedents.md).**
   - *Recommendation:* add a short disclosure section to README.md on the
     ZigQueen model. It would state that Fork is written with AI agents
     under the owner's direction, describe the clean-room method, name the
     data provenance, and point to ORIGINALITY.md.
   - Keep the `.claude/` tooling public: removing it would read as
     concealment.
8. **The forensics page.**
   - *Recommendation:* no action beyond (7). Fork's repository would be
     labelled AI-generated, which is accurate and declared.
9. **Credit format.**
   - *Recommendation:* name authors as well as engines in new
     ORIGINALITY.md rows where the author is public. This was the
     attribution standard requested in Coda's dispute. This survey's rows
     already do.
10. **Which CCRL view for future surveys.**
    - *Recommendation:* the all-engines best-versions list as the reference
      for versions, with the single-CPU view beside it for strength, since
      Fork tests one thread.
11. **TCEC's view of AI-assisted entries (UNVERIFIED).**
    - *Recommendation:* ask in Fork's TCEC questionnaire when it is filed.
      Whether TCEC treats Coda or Triumviratus as derivatives was not
      checked on any TCEC page.

## 6. UNVERIFIED in this file

- Every engine figure is self-reported.
- Kaggle hours per 8c arm.
- Whether Fork's NMP already gates on the TT bound (B7).
- Whether Fork's SEE handles pins (F12).
- Whether Fork's eval cost makes F3's gain small (X1 measures it).
- The step-12 budget figure is the think tank's estimate.
