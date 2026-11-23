# Bake-off round 3, option (a): H512+PP built, and its training and test plan

Written 2026-11-14 from the coordinator's brief after the owner's decisions of that morning (DESIGN.md decisions log,
"Bake-off round 3: the king-input designs measured and decided"): "(1) train option (a) only for now; (2) M4 (4
buckets, refresh cache); ... (5) screen (a) against a same-recipe control trained alongside it, plus the speed-adjusted
screen vs the current default, then STC SPRT; (6) warm-start from the 8c winner once promoted (r8brft1 if 8c isn't
promoted); (7) fix the trainer's input-index collision now." The design report is
docs/research/bakeoff-r3/king-inputs-design.md (branch proto/r3-king-a), option (a) in its section 2; its prototype
(ac4c179, ab0339e) was re-implemented on phase-4 37b5d30, not merged. **Nothing here was pushed, launched or
trained.** Branch nets/r3-kr4.

## 1. What was built

**Architecture 9, H512+PP** (the bake-off name: S512+PP with H-512's king regions): S512+PP's 768 piece inputs
copied per own-king region, the region read from the net file's 32-entry map of the mirrored own-king cell (M4: e1 |
f1-h1 | rank 2 | ranks 3-8), then the 608 pawn-link inputs of rank limit 1, shared by every region; 512 SCReLU; 8
outputs picked by the game phase; QA 255, QB 64. Saved inputs 3,680 (net file 3,785,952 bytes); in training 4,448 (the
768-input factoriser between the region rows and the links, merged into every region when saved).

- **Engine** (src/eval/nnue): `FORK_NET_ARCH` 9 from the embedded net's header (CMake, as every architecture); the
  default stays r8brft1 (architecture 8), whose code paths are unchanged (the snapshot code compiles only for 9; the
  link row offset is the constant 768 for 8). Region selection is `frame_of`'s (as H-512's); a king move into another
  region or across the d/e line changes the mover's frame. **Refresh cache:** per thread, one `FrameSnapshot` per
  perspective, file flip and region (2 x 2 x 4 = 16 snapshots, about 18 KB), each the sums last computed in that frame
  with the board they belong to. A frame change is refreshed lazily (speed sprint 3's design, b477ba2): at the first
  evaluation that needs that perspective at or below the changed ply, the snapshot is brought to the current board by
  the pieces that differ and the links of the pawns that differ (`link_changes` holds for any two pawn sets), through
  the existing register-tiled kernel (at most 96 rows each way), and copied to the evaluated ply. Non-king moves are
  incremental as in S512+PP. No allocation; the kernels are the existing SIMD paths with their scalar references.
- **Net file:** the reader takes architecture 9 (version 2), checks the map (at most 4 regions) and the int16 bound
  with the piece weights over every region's rows (`net_file.cpp`, unchanged rule).
- **Warm-start expansion** (`tools/nnue/extend_weights.py --arch h512pp`), the source an argument (r8brft1 now; 8c's
  winner later): from an S512+PP net file, the architecture 9 file with every region's rows the source's (bench
  identical); from S512+PP's float weights, the trainer's warm start (regions zero, the factoriser the source's piece
  rows, the links copied: S512+PP's first layer with 3,072 zero inputs put first). `--perturb SEED` writes a test net
  whose regions 1-3 differ (each weight stepped toward zero, so no bound breaks).
- **Test net** `nets/r8brft1kr4.fnet` = r8brft1 expanded (a Python test checks it is reproducible), with
  `tests/bench-r8brft1kr4.ref` (r8brft1's bench) and `tests/nnue/r8brft1kr4.parity`; CI's `nets` job builds it, runs
  netcheck and bench parity, and (new, `NET_SUITE=nnue`) builds fork_tests and runs the nnue suite, the only place
  architecture 9's own test cases are compiled.
- **Trainer** (tools/train, `--arch h512pp`): the regions (M4 by default, `--regions` to override), the factoriser,
  the links after both (the layout fix a468268), the merge (region + factoriser, links kept), no first-layer clip
  (the warm start's factoriser holds r8brft1's piece rows, 917 of them beyond 0.99, the largest 1.979), the S-512
  output; `tools/nnue/models.py` mirrors it (`h512pp`), `tools/nnue/h512pp.json` describes the saved file;
  `pp_bound.py` (the link clamp) and `gates.sh` take architecture 9.
- **Kernel** `tools/train/kaggle/bakeoff_r3.py` (section 3), not pushed.

## 2. Verification (all run 2026-11-14 on this machine)

- **Failing first.** The engine's new cases (H512+PP's evaluation against an independent reference along random games;
  a search-tree walk with king moves, null moves and snapshot refreshes against a refresh and the reference) failed on
  an architecture 9 build before the link offset and the snapshots were written (7,848 failures; the region-map case
  and the existing cases passed), and pass after (14 of 14 nnue cases). The Python cases (`RegionedLinks`, 8) failed
  on the base tools (7 errors: no h512pp) and pass; the Rust cases (3 new) failed on the base trainer ("unknown
  --arch h512pp") and pass.
- **The checks can fail (fault injection, reverted):** a snapshot that does not record its pawns made 3 nnue cases fail
  (4,885 failures), and a Debug build (FORK_DEBUG: every evaluation against a refresh from the board) stopped at the
  first mismatch (illegal-instruction trap, exit 132) in bench on the perturbed net.
- **Debug bench on the perturbed net** (regions 1-3 differ; no fault): no mismatch over the whole bench (5,326,268 /
  c8eef85b992853c3 for that net).
- **Bench identity:** the build with nets/r8brft1kr4.fnet gives **5,386,021 / 5ecd49d976e215e1**, r8brft1's, on
  clang-release (native, AVX-512), clang-v3 (AVX2), clang-avx512, clang-scalar, gcc-release, clang-debug (ASan+UBSan,
  FORK_DEBUG checking every evaluation) and gcc-debug (Windows), each with the nnue suite passing (14 of 14) and
  netcheck exact on 446 positions. The default build (r8brft1) passed `check.sh quick` at the engine commit.
- **Parity:** the feature leg (the trainer's `features` against the reference, 446 positions): 0 differ. The trainer's
  own export of a random-initialised h512pp net (`fork-train check`: every region and the factoriser distinct,
  merged by bullet's save list) equals the reference's quantisation (R-quant), its R-int against R-float loss is max
  1.76 cp, and the architecture 9 engine's netcheck on it is exact (446 of 446). r8brft1's float weights, laid out as
  the warm start, quantised by the reference (bullet's save list redone) and converted at S = 88 then link-clamped,
  are **nets/r8brft1kr4.fnet byte for byte**; the same float weights as S512+PP differ from r8brft1.fnet in exactly one
  weight (r8brft1's one clamped link weight). The trainer's float leg (`fork-train eval`) and its quantised file of
  the warm start need the GPU (the CPU build is bullet's mock runtime): **not run here**; the kernel runs both and
  checks the warm start's float loss and quantised identity in the session (section 3).
- **Tests run:** cargo test (9 of 9, WSL; no CI job runs them), the Python tool tests (`unittest discover -s
  tools/nnue`, and the kernel's `test_bakeoff_r3.py`), the nnue suite of architecture 9 on the presets above, the
  pre-commit `check.sh quick` (the default net) on every commit.

## 3. Training plan (not launched)

**Kernel:** `tools/train/kaggle/bakeoff_r3.py`, written from retrain 8c's A1 kernel (retrain/8c-prep 178f16b): two
arms side by side, one T4 each, seed 1 both (the same data order):

| Arm | Architecture | Warm start | Data, recipe |
|---|---|---|---|
| kr1 | H512+PP (9), M4 | SOURCE laid out in the session (`extend_weights.py --arch h512pp`): regions zero, factoriser = SOURCE's piece rows | retrain 8c's control files (TD(0.9) copies of the S512ppr3-or-later parts, blend copies of the older, the fresh slice slice1b), result weight 0, LR 1e-4, tenfold drop after 180, 360 superbatches of 305 x 16,384, S = 92, interleaved; candidate = the window average 331-360 |
| pp1 | S512+PP (8), the same-recipe control | SOURCE as it is | the same |

- **SOURCE** (parameter, one edit): r8brft1's float weights, `r8brft1-avg.bin` = fork-retrain-8b-rft v1's
  avg-rft1/weights.bin (SHA-256 2d70ebcc...1dba1, on this machine at ~/fork-data/kaggle/r8b-rft-out), to be uploaded as
  dataset `fork-r3-kr4-init`; if 8c's winner is promoted first, its window average instead.
- **Validity, blocking:** inputs against the manifests; SOURCE's SHA-256; the warm start's float loss equals SOURCE's
  on bl-g4s2-val.vf (result weight 0) within 1e-6; the trainer's quantised files of SOURCE and of the warm start,
  converted, satisfy regioned_net(SOURCE) == warm start (so the converted warm start has SOURCE's bench); each arm's
  superbatch 0 equals the reference within 1e-5; the trainer leg files of the warm start are kept (result/warm/).
- **Before the push:** COMMIT must contain the trainer's h512pp (this branch, once merged), tools/nnue and retrain
  8c's manifests (on retrain/8c-prep until merged); the dataset `fork-r3-kr4-init` uploaded and hashed back; the 8c
  datasets as A1 mounted them (fork-r8c-i80 not needed). A **smoke copy** (`SMOKE = True`, about 0.3-0.5 h) first is
  recommended: it runs every check and both arms for 4 short superbatches and measures H512+PP's lap time on the T4,
  which no one has measured.

**GPU hours (estimate).** S512+PP's 360-superbatch run took 2.18 h on one T4 with two runs side by side (8b arm c;
8c's preflight lapped at 21.5 s per superbatch, the same). H512+PP's per-superbatch cost is **unmeasured**: about 1.7
times the active inputs (each piece twice, region and factoriser, plus the links) and round 1's H-512 trained at about
half S-512's positions per second (two runs per session), so **1.5-2.0x: kr1 about 3.3-4.4 h**, pp1 2.18 h beside it.
Session: about 0.5 h setup + 3.3-4.4 h + about 0.3 h offline = **about 4.1-5.2 h of wall time**, the quota's charge if
it counts session wall time (8c plan fact 2, strong evidence); about 6.5-7.6 h if it counts each GPU. With the smoke
copy, about 4.5-5.7 h. **Left of the 22.86 h this week:** about 17.2-18.3 h after it at wall-time charging; then retrain
8c's A2 (pos and lam arms, 4.86 h wall in 8c's plan) and arm Q (one 360-superbatch pair, about 2.7 h wall,
UNVERIFIED: not costed in a plan read here) leave about **9.6-10.8 h**. At per-GPU charging the three sessions would
take about 21.6-23.0 h of the 22.86 h, so one would wait for the next week.

## 4. Test plan (declared before any result)

The standing rules (DESIGN.md §5.2 Testing setup; the decisions log of 2026-11-09 and 2026-11-14), in order:

1. **Integrity gates, blocking** (kr1 and pp1): the session's validity (section 3); `tools/nnue/gates.sh` with
   `LAYOUT=tools/nnue/h512pp.json` for kr1 (`CONTROL_LAYOUT`/`HELDOUT_LAYOUT` s512pp.json for r8brft1), SLICE_TRAINED=1:
   the legs (R-quant against the trainer's quantised.bin, R-float against the trainer within 0.01 cp, quantisation
   loss within 21 / 16 cp), the scale matched to r8brft1, the link clamp at most 8 weights and no unit over the bound
   by its piece weights alone (pp_bound.py's new `piece_bound_units`), netcheck exact, the integrity/recall gate (at
   most 15 of 900); the held-out counts reported, never a gate. Watch item: with the factoriser and a region row each
   clipped at bullet's default 1.98, a merged piece weight can reach 3.96 (1,010 quantised); the reader's bound (|bias|
   + 32 x the largest piece weight + 64 x the largest link weight) has a slack of 29 on r8brft1kr4's tightest unit
   (median 15,460), and 2 of its 512 units would need link clamps if their largest piece weight grew 10%. So the clamp
   count is the gate to read first; **no quantisation range needs changing** for the warm start (r8brft1's rows are
   within 1.98), and a first-layer clip below 1.98 would move r8brft1's weights at step 0 (the identity).
2. **Speed-adjusted fixed-node screen against the current default** (r8brft1 until a promotion): kr1-avg against it,
   800,000 nodes per move, 1,600 games; FN_adj = FN + 118 log2(r), r = kr1's nps over the default's **from the screen's
   own games**; passes if FN_adj > 0. At this branch's measured local ratio (section 5: 0.941) the screen must show
   about +10.3 Elo (UNVERIFIED on the runners, which decide).
3. **Same-recipe control screen:** kr1-avg against pp1-avg, the same settings (1,600 games at 800,000 nodes): the gain
   of the regions themselves at equal training. Read with 8c's seed noise (two seeds of one recipe differed by -6.08 +/-
   9.42), so a single-seed difference under about 10 Elo is not a result; a second seed pair (kr2/pp2) is the remedy
   if it is close (one more session).
4. **STC SPRT [0, 5]** (8+0.08, Hash 16, UHO book, Syzygy 3-4-5; `--kind network`), against the current default, if
   screen 2 passes.
5. **UHO/SF19 diagnostic** (tools/nnue/uho_diag.py `run --net CAND.fnet --bin FORK`, then `table`) on kr1-avg, pp1-avg
   and r8brft1, static and 100k-node search; report only. Declared reading (the design report's §5 item 5): the
   queens-on part moves if adv's static median rises by more than 8 cp over **both** r8brft1 and pp1, the search column
   moving the same way; the queenless part moves if levelql's static median falls by more than 8 cp over both; a rise
   of adv with an equal rise of levelql is a scale shift, read with the matched scale S; qtrade and ptrade only as
   checks. `--bin` for kr1 is an architecture 9 build with kr1's net embedded (`-DFORK_NET=`); `--net` finds its layout
   by the header's architecture id (h512pp.json), so the binary's static evaluations are checked against the
   reference's R-int as for every net.

## 5. Speed of the production code (bench/ab_search.py)

The identical-tree method of the design report (DESIGN.md §5.4's speed gate): A = phase-4 37b5d30 with r8brft1, B =
this branch (3120b35, the engine of f06f6ca) with nets/r8brft1kr4.fnet, both bench 5,386,021 / 5ecd49d976e215e1
(checked on every run); WSL Ubuntu, clang 21.1.8, Release, LTO, **x86-64-v3**, `FORK_BUILD_TESTS=OFF`, core 4,
interleaved rounds through bench/ab_search.py's own `Side` (a scratch wrapper adds the per-round lists and the paired
interval: geometric mean of B/A per round, normal 95% interval on the log ratios). 2026-11-14, about 9:38-9:49 AM EST,
started only when WSL had no build and no other speed measurement running (another agent's sessions ran before and
after); load average 0.5-1.05.

| Session | A/A before | A/B: nps ratio B/A (95%) | ab_search-style median change | A/A after |
|---|---|---|---|---|
| 1, 20 rounds | 0.980 (0.963-0.998) | 0.936 (0.922-0.949) | -7.3% (best -5.4%) | 0.990 (0.976-1.005) |
| **2, 40 rounds** | 1.004 (0.991-1.017) | **0.941 (0.936-0.947)** | -5.8% (best -5.9%) | 1.000 (0.995-1.004) |

**Reading:** the production code keeps the prototype's speed (a1 M4 0.944 (0.939-0.949) and 0.937 in the design
report): session 2, whose A/A pairs both sit at 1.00, gives 0.941; session 1 was noisier (its first A/A 0.98) and
agrees within its interval. It passes the speed gate's 0.90 and misses the 0.95 goal, as the prototype did. The fixed-
node screen therefore needs about **+10.3 Elo** (−118 log2 0.941) at this local ratio; the runners' ratio decides.
Not measured: an AVX-512 (native) pair, in-game (non-bench) refresh rates.

## 6. New names (for the coordinator's screen before merging)

Cleared already (the brief): KingRegion, king_region, region_of, RegionMap, region_map, own_king_region,
FrameSnapshot, SnapshotSlots, snapshot_slot, refresh_from_snapshot, snapshots_, FORK_NET_LINKS, king_pushes (the
first six are not used in the code).

Not yet screened:

| Name | Kind | Where |
|---|---|---|
| `link_start` | function (C++) | accumulator.cpp (the trainer's `link_start()` and models.py's `link_start` already exist) |
| `H512+PP`, `h512pp`, `H512pp` | architecture name, `--arch` value, Rust enum variant | net_shape.hpp, tools/train, tools/nnue |
| `h512pp.json` | file | tools/nnue |
| `regioned_weights`, `regioned_net`, `toward_zero`, `pp_links` | functions | tools/nnue/extend_weights.py |
| `--perturb` | option | extend_weights.py |
| `piece_bound_units`, `MAX_REGIONS` | function, constant | tools/nnue/pp_bound.py |
| `SQUARED`, `ADDED_ROWS` | constants | tools/nnue/models.py |
| `r8brft1kr4` | net file name | nets/, tests/ |
| `NET_SUITE` | environment variable | .github/ci/net-check.sh, ci.yml |
| `bakeoff_r3.py`, `test_bakeoff_r3.py` | files | tools/train/kaggle |
| `identity_probe`, `originals`, `SOURCE`, `NOT_TRAINED`, `WARM_TOLERANCE`, `START_TOLERANCE`, `kr1`, `pp1`, `fork-r3-kr4-init` | function, names, arms, dataset | bakeoff_r3.py |
| `RegionedLinks`, `h512pp_reference` | test class, test function | test_bakeoff.py, test_nnue.cpp |
| `option-a-plan.md` | file | docs/research/bakeoff-r3 |

Constants: the map M4 (screened, no match, per the brief); the snapshot count 2 x 2 x 4 (derived); `--perturb`'s step
0-8 (a test value, not a search or network constant).
