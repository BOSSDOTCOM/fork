# Idea 70: the result fine-tune of retrain 8b's winner (plan, declared before any run)

Written 2026-11-10 (about 7 PM EST), branch retrain/8b-rft from retrain 8b's launch commit 320c0be, before any
fine-tune exists. The owner's instruction (ideas.md 70, phase-4 95f49c7): right after 8b's SPRT decides the base
net, fine-tune the winner with a 100% game-result target (no search-score target) at a low learning rate (the form
Ethereal reports at concept level, +42.7 STC / +35.6 LTC on its own net, one engine's self-report), on the existing
8b data, two seeds; the usual gates (the endgame check included); a fixed-node screen of each seed's net against the
base net; an STC SPRT [0, 5] against the base. **Nothing is launched on Kaggle before the owner has the hours (section
4).** Ethereal's own values were not looked up and are not used; every number below has its reason here.

## 1. The base net (the winner)

- **td90** (bake/r8btd90 115daad, screened +17.39 ± 9.71 against S512ppr3) if 8b's first STC SPRT (r8b-stc-1, its
  pick td90) accepts H1.
- **c** (bake/r8bc 33da6a5, +13.03 ± 9.37) if instead the second SPRT (15-8b-f, r8b-stc-2: the second-best screen, at
  +5 or more) runs and accepts H1.
- If no 8b candidate passes, the fine-tune waits for the owner to name one (the chain stops with that question; the
  kernel holds the window averages of c, i52, td80 and td90, so any of the four can start: `WINNER=<arm>`).

**The warm start is the winner's window average** (8b's candidate itself: the mean of superbatches 331-360's float
weights, the net that was baked, gated and screened), taken in float form from fork-retrain-8b's output
(result/avg-<arm>/weights.bin; SHA-256 in the kernel's INITS and data/manifests/r8b-rft-init.json), not its best
checkpoint (8a: the window average beat the best checkpoint; 8b's c had its best prefix loss at superbatch 33, a
monitoring artefact, not a candidate).

## 2. The data

Arm c's 129 training files of g4s1 (the originals, the Syzygy slice included), already on Kaggle. At result weight
1.0 the target is the stored result alone, which every copy of a position (originals, blend copies, TD copies)
carries identically, and the trainer's filter keeps the same positions in each, so the originals serve whichever
arm won. The slice's target stays its WDL (its score and result agree). Validation: g4s1-val.vf.

## 3. The recipe (every number justified)

| Setting | Value | Why |
|---|---|---|
| Result weight | **1.0** | The owner's instruction: the game result alone, no search-score target. |
| Learning rate | **1e-5, constant** | The rate the base net itself ended at (8b's recipe: 1e-4 dropped tenfold after superbatch 180, so its last 180 superbatches, the averaged window included, ran at 1e-5): a fine-tune at that rate takes steps the net was already converged under, so it can move toward the new target without the larger 1e-4 steps that would undo the score-trained fit. Fork's one measured low-LR run from a converged warm start is 8a's D1 (S512ppr2 at 1e-5 for 60 superbatches): stable, and it moved the full-set loss by 7e-5 (0.01968472 to 0.01975487), so 1e-5 for 60 superbatches does change a net measurably. No decay: 8a's cooldown branch (1e-5 to 3e-6 to 1e-6) did not beat a plain average. |
| Superbatches | **60** (305 x 16,384 positions each: 300 M) | About 0.32 of a pass over g4s1's about 0.95 B kept positions (UNVERIFIED estimate, plan.md section 1), so no position is seen twice: a game result is shared by about 35 kept positions per game with a within-game correlation of 0.674 (ideas.md 51, B4 M2/B12 W4), so repeated passes would fit individual games' outcomes. The same length as 8a's D1, Fork's only measured run of this kind. Cost about 0.36 GPU-h per seed (section 4). |
| Schedule | constant LR, no drop (`--lr-step 1000000`, 8a's NO_DROP) | As above. |
| Candidate | **the mean of superbatches 46-60** (the last 15) | 8a's and 8b's finding: a window average of the last superbatches beat the best checkpoint and the cooldown; 15 of 60 is the window 8a's 60-superbatch arm D1 used. |
| Seeds | **1 and 2**, side by side (one T4 each) | The owner's two seeds; the warm start fixes the weights, so the seed sets the data order (bullet's shuffle). |
| Everything else | 8b's: S = 92, AdamW, batch 16,384 x 305, read interleaved, the 16 datasets, the input checks | The kernel is 8b's with exact replacements (tools/train/kaggle/make_rft_kernel.py; its test regenerates it). |
| Kept | each seed's best checkpoint by the monitoring prefix, ck-60 (optimiser state included), the window's float weights | 8b's layout. |

## 4. Kaggle cost and quota

- **Rate, measured in 8b:** arm c's 360 superbatches took 7,860.8 s with two runs side by side (21.84 s per superbatch,
  228,852 positions/s). 60 superbatches: **1,310 s = 0.36 GPU-h per seed; 0.73 GPU-h for both** (in parallel: about
  0.36 h of training wall time).
- **Overhead, estimated (UNVERIFIED):** rustup, the trainer's build (8a: 35 s), hashing the 289 mounted files (about
  11.5 GB), the warm-start checks, then two averages, two quantisations and 3 nets x 5 scores offline: about 0.3 h.
  **Session: about 0.7 h of wall time.**
- **Quota** (`kaggle quota`, at 6:35 PM EST 2026-11-10): **18.05 h of 30 left** (11.95 h used; it refreshes Thursday
  2026-11-13 at 7 PM EST). The week's use since 9:44 PM on 2026-11-09 (8.99 h: 8b's session of about 6.2 h, idea 69's
  preflights and its cw/c2 session of about 2.6 h) matches the sessions' wall times, not two GPUs each, so a T4 x2
  session seems to be charged at wall time (UNVERIFIED: no single-session reading). **The fine-tune: about 0.7 h
  (1.4 h if charged per GPU).** Label-depth's B0 nets (about 3 GPU-h) still fit: 18.05 - 1.4 - 3 = 13.6 h left.

## 5. Gates, branches and tests (declared before any result)

1. **Validity (blocking, in the session):** 8b's inputs check; the winner's weights reproduce their own g4s1-val
   prefix loss of 8b's session (td90-avg 0.01938369, c-avg 0.01940656) within 1e-6; each seed's superbatch 0 equals the
   winner's prefix loss at result weight 1.0 (computed in the session) within 1e-6; the runs end with exit 0, the
   window complete and quantised unchanged.
2. **Gates (8b's gates.sh, per seed):** conversion at the scale matched to **the base net's** mean |eval| on 4,000
   g4s1-val positions (a result-only target may stretch or squeeze evals; the match keeps the screen about the
   evaluation, not its scale), the link clamp, the parity legs (quantization loss within 21 / 16 cp), netcheck exact;
   **the endgame check against the base net**, reported, flagged to the owner if more than 15 of 900 (the standing
   line; non-blocking, owner, 2026-11-09).
3. **Branches:** bake/r8brft1 and bake/r8brft2 on **c67fd26**, the engine base of every 8b bake (bake/r8btd90^ and
   bake/r8bc^), each with its bench reference.
4. **Fixed-node screens:** each seed's net against the base net's bake commit, 1,600 games at 800,000 nodes per move
   (8b's screen settings) - night items 15-8b-n and 15-8b-o.
5. **STC SPRT [0, 5] (`--kind network`, idea `result-finetune`)** of the better-screened seed against the base net's
   bake commit - item 15-8b-p. Nothing is promoted: the owner reviews.

## 6. What is prepared, and what waits

- Prepared on retrain/8b-rft: the kernel (generated, tested), this plan, data/manifests/r8b-rft-init.json.
- Prepared locally (~/fork-data/8b-rft/): the upload folder fork-r8b-rft-init (the four window averages, 11.4 MB), the
  kernel's metadata (17 datasets: 8b's 16 and fork-r8b-rft-init), the chain chain-rft.sh (winner, upload, quota,
  push, watch, download, gates, branches, the ready file; it ends with fork_chain_done), the night items 15-8b-n/o/p
  (each waits for ~/fork-jobs/night/state/r8b-rft-ready.json; own state and SPRT names r8b-rft-*).
- **Not done:** no upload and no kernel push. The launch is one command after the owner's go-ahead:
  `python -I tools/jobs/jobctl.py start kaggle r8b-rft-chain -- bash ~/fork-data/8b-rft/chain-rft.sh`
  (it waits for 8b's SPRT verdicts by itself).
