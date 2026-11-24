# Bake-off round 3: launching session A (kr1 + pp1) and session X (xl1) from retrain 8c's candidate

**Update, 2026-11-14 ~6:15 PM EST: the default warm-start source is now r8ceplo2** (owner, ~5:55 PM EST: "set the
warm-start source for all future round 3 training to r8ceplo2, using its float weights from 8c's A1 outputs (verify
the quantized export of those weights reproduces r8ceplo2's bench exactly before use)"; verified: the float file
quantised and converted at S = 87 with its one link clamp is nets/r8ceplo2.fnet byte for byte, bench 5,403,414 /
34c916638218aa11, netcheck exact). From retrain/r3-kr4 **3650403** on, the kernel's own SOURCE is r8ceplo2
(r8ceplo2-avg.bin, SHA-256 4118015e47ca596a966ee29821a43ae613155af9b0c9a95913d6fc81e06f3539, dataset
fork-r3-init-8c), so a later round 3 session needs no `--source`:

```bash
$PY -I $S/make_kernel.py --repo $S/wt --commit 3650403 --out $S/launch/A-next --arms A   # or --arms X, --smoke
$K kernels push -p "$S/launch/A-next"
```

(make_kernel.py reads the kernel's own SOURCE block at the commit; `--source NAME FILE SHA256 DATASET` still replaces
it.) The commands below are the ones prepared at b96a514 (SOURCE r8brft1, replaced by `--source`); the first two
sessions were launched from launch/A-r8ceplo2 and launch/X-r8ceplo2, i.e. already from r8ceplo2.

Prepared 2026-11-14 (about 11:30 AM-12:00 PM EST). Nothing here has been pushed to Kaggle: these are the commands for
the coordinator, run once 8c's candidate is chosen. Owner's decisions (2026-11-14): (a) and the same-recipe control
as soon as 8c's candidate is chosen, warm-started from it; x_lower in its own session, one seed, warm-started from
the same candidate, compared against session A's control pp1 (a second seed only if its fixed-node result against
pp1 lands between about +5 and +20).

## What is in place

- Branch **retrain/r3-kr4** at **b96a5143b6be30631bf6468b23ba0d6757427ff3** (pushed): phase-4 d63ddc6 (H512+PP, x_lower
  S512+PPXL, both trainers) + retrain 8c's manifests + the kernel `tools/train/kaggle/bakeoff_r3.py` with ARM_SET 'A'
  (kr1 on GPU 0, pp1 on GPU 1) and 'X' (xl1 on GPU 0).
- Dataset **bossdotcom/fork-r3-init-8c** (private, every file downloaded back and its SHA-256 checked, 11:35 AM EST),
  each an S512+PP float weights file of 2,852,944 bytes (l0w 1376 x 512, l0b 512, l1w 8 x 1024, l1b 8), the window
  averages of 8c's A1 output (`~/fork-data/8c/a1-out/result/avg-<arm>/weights.bin`):

  | Candidate | File in the dataset | SHA-256 |
  |---|---|---|
  | r8cc1 | r8cc1-avg.bin | cb3a989d96431ba1fddd8c6f91cf77be73787801919d664a6e95bb279ce579ad |
  | r8cc2 | r8cc2-avg.bin | 350c38567f813af00e193b96ba163dc26289653341826c3fe470cd1fd60e7233 |
  | r8ceplo1 | r8ceplo1-avg.bin | 248949506c64b87d30f1b7d92de2b4091a6b8c2c0c53cbe19e3309a6509ed533 |
  | r8ceplo2 | r8ceplo2-avg.bin | 4118015e47ca596a966ee29821a43ae613155af9b0c9a95913d6fc81e06f3539 |

- The eight kernel folders are already generated (dry run, not pushed) under
  `~/fork-runners/scratch-r3kr4/launch/<A|X>-<candidate>/` by the commands below; each differs from the
  repository's file in COMMIT, SOURCE and (X) ARM_SET only. Their 27 data sources (8c A1's but fork-r8c-i80a/b and
  fork-r8b-rft-init, plus fork-r3-init-8c) were checked against the kernel's input check by file name
  (`check_full_sources.py`: 465 files mounted, every one sealed, none twice, nothing unresolved, the source found once;
  each arm's 196 files equal 8c A1's c1 list exactly).

## Commands (PowerShell or Git Bash; one session = one push)

Set once (Git Bash):

```bash
S=$(cygpath -m ~/fork-runners/scratch-r3kr4)
PY=~/fork/.venv/Scripts/python.exe
K=~/fork/.venv/Scripts/kaggle.exe
$K quota          # read before and after each push
```

Then for the chosen candidate, session A and session X (the folders exist already; re-running make_kernel.py
rewrites them identically):

### r8cc1
```bash
$PY -I $S/make_kernel.py --repo $S/wt --commit b96a514 --out $S/launch/A-r8cc1 --arms A --source r8cc1 r8cc1-avg.bin cb3a989d96431ba1fddd8c6f91cf77be73787801919d664a6e95bb279ce579ad fork-r3-init-8c
$K kernels push -p "$S/launch/A-r8cc1"
$PY -I $S/make_kernel.py --repo $S/wt --commit b96a514 --out $S/launch/X-r8cc1 --arms X --source r8cc1 r8cc1-avg.bin cb3a989d96431ba1fddd8c6f91cf77be73787801919d664a6e95bb279ce579ad fork-r3-init-8c
$K kernels push -p "$S/launch/X-r8cc1"
```

### r8cc2
```bash
$PY -I $S/make_kernel.py --repo $S/wt --commit b96a514 --out $S/launch/A-r8cc2 --arms A --source r8cc2 r8cc2-avg.bin 350c38567f813af00e193b96ba163dc26289653341826c3fe470cd1fd60e7233 fork-r3-init-8c
$K kernels push -p "$S/launch/A-r8cc2"
$PY -I $S/make_kernel.py --repo $S/wt --commit b96a514 --out $S/launch/X-r8cc2 --arms X --source r8cc2 r8cc2-avg.bin 350c38567f813af00e193b96ba163dc26289653341826c3fe470cd1fd60e7233 fork-r3-init-8c
$K kernels push -p "$S/launch/X-r8cc2"
```

### r8ceplo1
```bash
$PY -I $S/make_kernel.py --repo $S/wt --commit b96a514 --out $S/launch/A-r8ceplo1 --arms A --source r8ceplo1 r8ceplo1-avg.bin 248949506c64b87d30f1b7d92de2b4091a6b8c2c0c53cbe19e3309a6509ed533 fork-r3-init-8c
$K kernels push -p "$S/launch/A-r8ceplo1"
$PY -I $S/make_kernel.py --repo $S/wt --commit b96a514 --out $S/launch/X-r8ceplo1 --arms X --source r8ceplo1 r8ceplo1-avg.bin 248949506c64b87d30f1b7d92de2b4091a6b8c2c0c53cbe19e3309a6509ed533 fork-r3-init-8c
$K kernels push -p "$S/launch/X-r8ceplo1"
```

### r8ceplo2
```bash
$PY -I $S/make_kernel.py --repo $S/wt --commit b96a514 --out $S/launch/A-r8ceplo2 --arms A --source r8ceplo2 r8ceplo2-avg.bin 4118015e47ca596a966ee29821a43ae613155af9b0c9a95913d6fc81e06f3539 fork-r3-init-8c
$K kernels push -p "$S/launch/A-r8ceplo2"
$PY -I $S/make_kernel.py --repo $S/wt --commit b96a514 --out $S/launch/X-r8ceplo2 --arms X --source r8ceplo2 r8ceplo2-avg.bin 4118015e47ca596a966ee29821a43ae613155af9b0c9a95913d6fc81e06f3539 fork-r3-init-8c
$K kernels push -p "$S/launch/X-r8ceplo2"
```

Kernel ids: session A `bossdotcom/fork-bakeoff-r3`, session X `bossdotcom/fork-bakeoff-r3-xl`. Kaggle runs at most two
GPU sessions at a time (8c's smoke chain met that limit): A and X fit together only if nothing else (8c A2, arm Q)
is running; otherwise push the second when a slot frees.

## After each session

- Watch and download: as `watch_smoke.sh` does (status every 2 minutes, then `kaggle kernels output <id> -p <dir>`).
- Validity: `result/bakeoff_r3.json` → `validity.ok`, `checks.ok` (the warm start's float identity within 1e-6 and its
  quantised identity, the feature leg, `check` of each architecture), each arm's superbatch 0 at the reference.
- Gates per candidate (`tools/nnue/gates.sh NAME result/avg-<arm> result/avg-<arm>/parity-trainer-<arm>-avg.txt
  CONTROL_FNET VAL OUT`, SLICE_TRAINED=1; the control net is 8c's candidate's own clamped net):
  kr1 `LAYOUT=tools/nnue/h512pp.json`; xl1 `LAYOUT=tools/nnue/s512ppxl.json`; pp1 `LAYOUT=tools/nnue/s512pp.json`;
  `CONTROL_LAYOUT=HELDOUT_LAYOUT=tools/nnue/s512pp.json` for all; `HELDOUT_WARM=<candidate's net>`; FORK_BIN an engine
  of the candidate's architecture (9 for kr1, 10 for xl1, 8 for pp1). The smokes ran the same chain by hand
  (`post_smoke.sh`, `post_xl_smoke.sh`): netcheck exact on 446 for every arm.

## Projected quota (wall-time charging, as every reading so far: the smokes cost 0.07 h each for about 6 minutes)

Measured laps on the T4 (smoke sessions, 4 full-size superbatches on 5 small files, laps 2-4): kr1 19.23 s, pp1 19.0 s
(session A smoke, 10:27 AM), xl1 17.9 s (session X smoke, 11:34 AM). 8c's real-data S512+PP lap was 21.5 s, so the
real files may add about 2.5 s per lap to each.

| Session | Training (360 laps) | + setup and offline | Projected quota-h (if charged per GPU) |
|---|---|---|---|
| A (kr1 + pp1, side by side) | about 1.9-2.2 h | + about 0.5-0.7 h | **about 2.5-2.9 h** (5.0-5.8) |
| X (xl1 alone) | about 1.8-2.1 h | + about 0.5-0.6 h | **about 2.3-2.7 h** (the same: one GPU) |

Quota at 11:41 AM EST: 22.72 h left (7.28 used of 30, resets Fri 11-20 7:00 PM EST). After A and X: about 17.1-17.9 h;
then 8c's A2 (4.86 h in its plan) and arm Q (about 2.7 h, an estimate) leave about 9.5-10.3 h.
