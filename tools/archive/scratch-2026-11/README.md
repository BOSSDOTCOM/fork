# Scratch tooling archive, November 2026

The tooling scripts that agents wrote in five scratch folders (`~/fork-runners/scratch-*`) during Phase 4's
bake-off round 3, idea 178 and the r8ceplo2 and r3kr1 promotions (2026-11-14 and 2026-11-15), kept by the owner's
order of 2026-11-23. **Archived as used, not maintained:** nothing here is run by a check, a job or CI, and a script
may refer to files, worktrees (`wt/`), branches or Kaggle datasets that no longer exist. The repository's own tools
(`tools/train/kaggle/bakeoff_r3.py`, `tools/nnue/`, `bench/ab_search.py`, `tools/nnue/gates.sh`) are where this work
continued.

One folder here per scratch folder, file names kept. The results, data and logs they produced stay in the scratch
folders for the phase-end cleanup (list at the end).

## What changed in the copies

Only paths: every literal path under the user's home folder was rewritten, so nothing personal is published
(CLAUDE.md, non-negotiable 8). The logic is unchanged.

- Python: `'C:/Users/<user>/x'` became `Path('~/x').expanduser()` (or `str(...)` of it).
- Git Bash scripts: a base folder handed to Windows programs is `$(cygpath -m ~/...)` (Windows form, as
  `tools/jobs/check_paths.py` requires; the originals used `/c/...` literals); Windows programs are `~/fork/.venv/...`;
  a backslash path became `$(cygpath -w ~/...)`. In `scratch-i178m/check_i178.sh`, `wslp` converts with `cygpath -u`
  first, since its arguments are now in `C:/` form.
- WSL scripts: the Windows home has no `~` form inside WSL, so `/mnt/c/Users/<user>/` became `$WIN_HOME/`, which
  the script now requires (`WIN_HOME=/mnt/c/Users/<user>`).
- `LAUNCH.md`: the same forms; the push commands use `"$S/launch/NAME"`.

`python -I tools/jobs/check_paths.py tools/archive/scratch-2026-11` passes with no exception markers.
`scratch-promote-kr1/fix_nets_md.py` raises Python's invalid-escape warning (`'\|'`), the same in the original.

## scratch-r3kr4: bake-off round 3, option (a) (2026-11-14)

Kaggle sessions `bossdotcom/fork-bakeoff-r3` (A: kr1, H512+PP with king regions, beside its control pp1), `-xl`
(X: xl1, x_lower S512+PP+XL) and `-xl2` (X2: xl2, xl1's second seed), warm-started from retrain 8c's candidates
(r8ceplo2 from the owner's order of about 5:55 PM EST). Kernel r3kr1 came from session A.

| File | What it did |
|---|---|
| `LAUNCH.md` | The launch notes: the datasets and their SHA-256, one command pair per 8c candidate, the post-session checks and the quota projection |
| `make_kernel.py` | A kernel folder from `tools/train/kaggle/bakeoff_r3.py` at a pushed commit: exact replacements of COMMIT, SMOKE, ARM_SET (A, X, X2) and SOURCE, plus `kernel-metadata.json` |
| `upload_init.py` | Dataset `fork-r3-kr4-init` (r8brft1's float window average): stage hard links, create, wait, download every file back and check its SHA-256 |
| `upload_8c.py` | The same for dataset `fork-r3-init-8c` (retrain 8c's four candidates' float window averages) |
| `check_full_sources.py` | A full session's data sources against the kernel's input check without downloading: Kaggle file lists, empty stand-ins, `bakeoff_r3.resolve(hashes=False)` |
| `work/check_lists.py` | `check_full_sources.py` that also writes each arm's file lists (`<launch dir>-lists.json`) |
| `edit_kernel_xl.py` | One-off edit of `bakeoff_r3.py`: the xl1 arm and the session sets A / X |
| `edit_source.py` | One-off edit: the warm-start SOURCE becomes r8ceplo2 (kernel, its test, `extend_weights.py`) |
| `edit_xl2.py` | One-off edit: xl2 (xl1 with seed 2) and session X2, with a test |
| `watch_smoke.sh`, `watch_xl_smoke.sh` | Wait for a smoke kernel to end (status every 2 minutes), then download its output |
| `post_smoke.sh`, `post_xl_smoke.sh` | The smoke outputs checked locally: the summary, the warm start's quantised identity, conversion, link clamp, legs and the engine's netcheck |
| `run-cargo.sh` | WSL: build or test `fork-train` with a throwaway CARGO_HOME and target folder |
| `run-chain.sh` | WSL: the trainer-side chain on the CPU for H512+PP's warm start (check, feature leg, float evaluations, an LR-0 quantising step) |
| `run-presets.sh` | Architecture 9's nnue suite, bench and netcheck on each named preset, with `nets/r8brft1kr4.fnet` built in |
| `run-nps-build.sh` | WSL: the speed check's two builds (clang, Release, LTO, x86-64-v3), A = phase-4 with r8brft1, B = the round 3 commit with r8brft1kr4 |
| `run-nps.sh`, `run-nps40.sh` | WSL: at the first idle moment, A/A, A/B, A/A with 20 (or 40) interleaved rounds on core 4 |
| `ab_search_paired.py` | Wrapper round `bench/ab_search.py`'s Side: per-round nps and the paired ratio B/A with a 95% interval |
| `wait-idle.sh`, `when-idle-build.sh` | WSL: wait until no build, `ab_search` or `fork bench` runs (then, for the second, run the nps builds) |
| `work/chain_py.py` | Reference side: an S512+PP and an H512+PP net from float weights, compared with `nets/r8brft1.fnet` and `regioned_net` |
| `work/rquant.py` | Reference side: the quantised file of float weights for a layout |
| `work/verify_warm_r8ceplo2.py` | r8ceplo2's float weights laid out as the two warm starts, quantised and converted at S = 87, against r8ceplo2's own converted file laid out the same way |
| `k-smoke/`, `k-xl-smoke/`, `launch/*/kernel-metadata.json` | The kernel metadata `make_kernel.py` wrote for the two smokes and the nine prepared or launched sessions (A and X for each of the four 8c candidates, X2 for r8ceplo2) |

## scratch-i178m: idea 178, H512+PP+M (2026-11-15)

Session `bossdotcom/fork-i178-m` (arms mb1, H512+PP+M, architecture 12, beside its control kc1, H512+PP, both warm
from r3kr1), and its smoke.

| File | What it did |
|---|---|
| `make_kernel_m.py` | Session M's kernel folder from `bakeoff_r3.py` at a pushed commit (COMMIT, ARM_SET 'M', SMOKE), with the kernel's own M_SOURCE |
| `upload_init.py` | Dataset `fork-i178-init` (r3kr1's float window average) with the download-back check |
| `check_i178.sh` | The training path checked locally: `fork-train check` and the feature leg for h512ppm, the graph lowering on the mock device, the warm start's identities in the reference, a seeded block for the engine's netcheck |
| `smoke_m_check.sh` | Waits for the smoke session, downloads it and passes only if the summary, the kernel's checks, both arms' runs, the legs and both engines' netcheck pass |
| `run-cargo.sh` | WSL: build or test `fork-train`, sharing round 3's CARGO_HOME and target folder |
| `launch/M-full/`, `launch/M-smoke/` (`kernel-metadata.json`) | The kernel metadata `make_kernel_m.py` wrote |

## scratch-promote: r8ceplo2 becomes the default network (2026-11-14)

| File | What it did |
|---|---|
| `presets.sh` | On each named preset of the promotion worktree: bench parity against `tests/bench-r8ceplo2.ref`, perftbench parity and the embedded net's netcheck |

## scratch-promote-kr1: r3kr1 becomes the default network (2026-11-14)

| File | What it did |
|---|---|
| `presets.sh` | On each preset: bench parity against `tests/bench-r3kr1.ref`, perftbench parity, netcheck and the nnue suite |
| `tcec_path.sh` | The TCEC build path: `./update.sh` with each `LABEL=CXX@ARCH`, then bench and perftbench parity, netcheck and a UCI smoke start, each binary copied out first |
| `tcec_wsl.sh` | WSL Ubuntu-22.04: `tcec_path.sh` with TCEC's four compilers at x86-64-v3 and v4 on the clean clone |
| `datagen_wsl.sh` | WSL Ubuntu-22.04: the labeller's PGO build of `fork` and `fork_datagen`, bench parity and a short datagen run checked by `tools/datagen/verify_games.py` |
| `design_rows.py` | One-off edit of DESIGN.md: section 5.6's status row for round 3 and the decisions-log row of the promotion |
| `fix_nets_md.py` | One-off: `docs/nets.md`'s merge conflict, r8ceplo2's status rewritten and r3kr1's entry |
| `resolve2.py` | One-off: the merge conflicts in DESIGN.md (ours, then theirs) and `docs/nets.md` |

## scratch-mates: nothing archived

The elementary-mate suite's work (ideas.md 203, 2026-11-15) left only logs, commit messages and `positions.txt`
(its position list); no scripts.

## Left behind in the scratch folders

- **scratch-r3kr4:** `target/` and `cargo-home/` (Rust build), `wt*/` (worktree folders), `nps/` (two repository
  clones and a binary), `up/` (staged datasets: weights and the `dataset-metadata.json` the upload scripts wrote),
  `smoke-out/`, `xl-smoke-out/` (session outputs), `work/` (logs, commit messages, nets, weights, a copy of
  `tools/nnue`, `test_search_head.cpp`, `accumulator.cpp.good`, `main.rs.good`, `post*/`, `verify-eplo2/`, `chain/`),
  `launch/A-r8cc1-lists.json`, and the kernel copies `bakeoff_r3.py` in `k-smoke/`, `k-xl-smoke/` and `launch/*/`
  (each is the repository's file at its commit with `make_kernel.py`'s replacements).
- **scratch-i178m:** the logs, `commit-msg*.txt`, `smoke-logs.txt`, `dry/` (a dry run's kernels and gate outputs),
  `engines/` (two binaries), `pull-smoke/`, `pull-x2/` (kernels pulled back from Kaggle), `smoke-out-*/`, `up/`,
  `work/`, `work-engine/` (nets, weights, parity files), and the kernel copies in `launch/*/`.
- **scratch-promote:** the build, test and preset logs, `commit-msg.txt`.
- **scratch-promote-kr1:** the build, configure, nnue, preset, TCEC and datagen logs, `commit-msg*.txt`,
  `datagen-smoke/`, `heldout-check/`, `tcec-win/`, `tcec-wsl/` (outputs and binaries), `test_search.before` (a copy
  of a test file).
- **scratch-mates:** everything (logs, commit messages, `positions.txt`).
