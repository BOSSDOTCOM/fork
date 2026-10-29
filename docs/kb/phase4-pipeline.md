# Phase 4 pipeline: datagen, Kaggle, bullet, Fork inference

Research for the Phase 4 step 0 spec (DESIGN.md on main, "Phase 4",
deliverables 0-7 and the Kaggle check table K1-K16). It covers the loop
Fork self-play datagen (local CPU) -> Kaggle Datasets -> bullet training
on a Kaggle GPU -> Fork's own C++ inference -> parity test -> SPRT.

- **Date verified:** 2026-10-28 for every item unless marked otherwise.
- **Why it matters for Fork:** Phase 4, deliverables 0 (Kaggle test
  session), 1 (openings), 2 (datagen writer), 3 (upload), 4 (training),
  5 (net reader), 6 (parity test).
- **How it was checked:**
  - bullet (MIT, a tool Fork uses; reading allowed by the brief) was
    shallow-cloned into a temporary scratch folder outside both
    repositories, at the commit pinned below. I read its README, docs,
    examples, data loaders, `bullet-utils`, the checkpoint and
    quantisation code, and the GPU build script and runtime bindings.
    The clone was deleted afterwards (see the report).
  - bulletformat 1.8.0 (MIT, jw1912, bullet's data crate) was downloaded
    from crates.io (its SHA-256 matches bullet's `Cargo.lock`) and its
    marlinformat and ChessBoard readers were read. Deleted afterwards.
  - viriformat: **only the README** (at two commits) and the docs.rs API
    page for `Filter` were read. Its source was not opened: the crate
    carries board code from the Viridithas engine.
  - No chess engine's source was opened. Notes below are in my own words;
    no code lines are reproduced. Identifiers (function, type and file
    names) are given so Fork's code can call bullet's documented API.
- **Tags:** bullet, bulletformat, bullet-utils: USE (MIT tools; never
  copied into Fork's repo). viriformat: USE (format spec). Kaggle CLI:
  USE (Apache-2.0 tool). Fathom: USE (already vendored, MIT). Lichess
  standard game DB: USE as openings only (CC0), per data-policy.md.

---

## 0. Key findings (short)

1. **bullet main is `da426a49` (2026-10-26).** It needs Rust 1.87 or newer
   (edition 2024; current stable is 1.99.1). The CUDA backend links
   `cuda`, `cudart`, `nvrtc` and `cublas`, compiles its kernels at run time
   with NVRTC for the detected GPU (no `nvcc` needed), and calls the driver
   function `cuFuncLoad`, which first appears in NVIDIA's CUDA 12.4
   driver-API docs. So, by inference, **CUDA 12.4 or newer** is needed
   (toolkit and driver). **There is still no CPU training backend**: only a
   mock device that type-checks the code and can time the data loader.
2. **bullet can evaluate a FEN with the float model, on the GPU only**
   (`ValueTrainer::eval` / `eval_raw_output`). There is no evaluator for
   the quantised file. So K15 can succeed and parity leg T runs on Kaggle.
3. **The quantised file has no header, no names and no shapes.** It is the
   `SavedFormat` entries in listed order, little-endian, each tensor
   column-major unless `.transpose()` is used, quantised by truncation
   unless `.round()` is used, then padded to a multiple of 64 bytes with
   the repeating ASCII bytes `bullet`. Entries without `.quantise` are
   written as f32. The optimiser's `weights.bin` is self-describing (name,
   count, f32 values), which is the best input for Fork's float reference.
4. **Resuming:** `load_from_checkpoint(dir)` restores the weights and the
   AdamW moments, and the next run must set `start_superbatch` to the
   saved superbatch + 1. bullet's AdamW keeps no step counter, so nothing
   else is lost. **But the viriformat loader ignores the resume position
   and shuffles with a clock-seeded RNG.** A resumed run sees a fresh
   random stream, and no bullet run is bit-reproducible.
5. **The viriformat loader reads game files directly and shuffles in RAM**
   (no pre-shuffle step). It takes either viriformat's built-in `Filter`
   (in check, tactical move, castling move, minimum ply, maximum |eval|,
   random skip and others) or a custom keep-function. Kaggle's GPU
   sessions have 4 CPU cores, so decoding games may limit training speed:
   measure it (section 2.5).
6. **viriformat spec, pinned at `0238b315`:** the format is fully specified
   in its README (section 3). Two traps:
   - The piece nibbles are **low nibble first**. The v2.0.1-era README
     example had them reversed, fixed on 2026-04-08 in a commit labelled
     "tentative". bulletformat's own marlinformat reader confirms low
     nibble first.
   - **bullet pins viriformat 2.0.1, which predates the extension record**
     (added 2026-06-17, after the last crates.io release, 3.0.0). Fork
     must not write extension records for bullet at this pin.
7. **Kaggle changes since 2026-10-24:**
   - **P100 looks gone.** The CLI's accelerator list "as of Sep 2026" has
     no P100, and Kaggle's image repository dropped its P100 test agent
     on 2026-09-05. The Kaggle docs pages still describe P100.
   - The GPU image is now built on the Colab runtime of 2026-09-17
     (Ubuntu 24.04, Python 3.13). Its CUDA was probably 12.8, but Colab
     itself moved through CUDA 13.3 and back to 13.0 in late September.
   - Rust is not preinstalled.
   - The CLI (v2.2.5) has `kernels push --accelerator/-t/--no-run` and a
     `kernels logs` command, and authenticates with a token
     (`KAGGLE_API_TOKEN` or `~/.kaggle/access_token`) as well as the
     legacy `kaggle.json`.
8. **Dataset uploads skip subfolders by default.** `kaggle datasets create`
   has `--dir-mode skip|zip|tar`, default `skip`. DESIGN.md deliverable 3
   says "shards as plain files in a subfolder". That needs changing: put at
   most 50 shard files at the top level of each batch dataset, or upload a
   zip (Kaggle unpacks zips). Whether Kaggle unpacks a tar is
   **UNVERIFIED**.
9. **Fathom's README** (pinned `c9c6fef0`, still master head) says
   `tb_probe_wdl` is thread-safe unless `TB_NO_THREADS` is defined, and so
   are the root probes. Concurrent WDL probes from datagen threads are
   fine, as long as `tb_init`/`tb_free` never run while a probe is active.
10. **Lichess:** monthly standard files are now about 28-33 GB (2025-2026).
    A small, clean month is **2016-09** (1.21 GB, 6,813,113 games). It falls
    after the documented self-play and illegal-castling issues. Its SHA-256
    is in section 6.

---

## 1. bullet today (question 1)

### 1.1 Pin, licence, toolchain

| Item | Value | Source |
|---|---|---|
| Repository | github.com/jw1912/bullet, branch `main`, MIT (GitHub API and workspace `Cargo.toml`) | API, clone |
| Current head | `da426a49b2a4b79a55a87031cd51c89bdf1ff030`, 2026-10-26 ("Basic support for f16 and bf16", #570). The KB's earlier `579b78b3` (2026-10-20) is two commits behind (the other one is #566, TensorIR history tracking) | GitHub API |
| Releases | none; the workspace crate `bullet_lib` is version 1.0.0 inside the repo | `crates/bullet_lib/Cargo.toml` |
| Workspace crates | `bullet_lib` (the user-facing library), `bullet-compiler` (tensor graph), `bullet-gpu` (CUDA/ROCm/Metal runtime), `bullet-trainer` (optimisers, data reader, run loop), `bullet-utils` (CLI) | `Cargo.toml` |
| Rust | `rust-version = 1.87`, `edition = 2024`; no `rust-toolchain` file; bullet's CI uses the stable channel and runs `cargo test --workspace` **without any GPU feature** (so it compiles on a machine with no CUDA) | `Cargo.toml`, `.github/workflows/checks.yaml` |
| Using it | either edit an example in the repo, or depend on `bullet_lib` as a git dependency (`package = "bullet_lib"`). Fork's plan (`tools/train/`, own Cargo project, `Cargo.lock` committed) is the second route; pin it with `rev = <full sha>` | README |
| Data crates locked | viriformat 2.0.1, bulletformat 1.8.0, sfbinpack 0.6.4, montyformat 0.9.2 | bullet `Cargo.lock` |

Recommendation: pin `da426a49` (the commit this page describes), commit
`Cargo.lock`, and add a `rust-toolchain.toml` with a fixed stable version
(for example 1.99.1), so Kaggle and WSL builds use the same compiler. That
toolchain-file choice is mine, not bullet's.

### 1.2 Backends, CUDA versions, CPU

- **Features:** `cuda`, `rocm`, `metal`. `metal` cannot be combined with
  the others. With no feature, the execution context is a **mock GPU**:
  bullet's own error text says it "can't actually do anything". There is
  **no CPU training backend** (rechecked; the KB was right).
- **What the mock is good for:** type-checking Fork's training program
  locally, and `measure_max_cpu_throughput`, which runs the data loader on
  a mock device (pinned memory is not needed because batches never reach
  a GPU). So **data-loader speed can be measured on the local CPU**
  (`trainer/src/run.rs`). Whether a full `ValueTrainerBuilder::build`
  succeeds on the mock is **UNVERIFIED** (not run).
- **CUDA build requirements** (`crates/gpu/build.rs`):
  - `CUDA_PATH` must be set, and the path must exist;
  - on Linux the link search path is `$CUDA_PATH/lib64` (on Windows,
    `lib/x64` and `lib`), plus `/usr/lib/wsl/lib/` when it exists (WSL);
  - it links `cuda`, `cudart`, `nvrtc` and `cublas` dynamically.
- **Kernels are compiled at run time** with NVRTC, with
  `--gpu-architecture=sm_XY` set from the device's compute capability
  (`runtime.rs`, `runtime/cuda.rs`). `nvcc` is therefore not needed to
  build or run bullet, but the NVRTC library is.
- **Which CUDA versions:**
  - The docs only say "as recent a version as possible"; a too-old
    toolkit should fail clearly at link or run time.
  - bullet's CI never builds against real CUDA (it sets
    `CUDA_PATH=.` for clippy).
  - The newest driver call it binds is `cuFuncLoad` (alongside
    `cuMemAllocAsync`). NVIDIA's archived driver-API "Execution Control"
    pages mention `cuFuncLoad` in 12.4.0 and not in 11.8, 12.0, 12.2 or
    12.3. Inference: **toolkit and driver of CUDA 12.4 or newer.**
    **UNVERIFIED** until a real build runs (K3/K4).
- **GPU architecture:**
  - CUDA 13.0 removed offline compilation and library support for
    Maxwell, Pascal and Volta (CUDA 13.0 release notes, "Deprecated
    Architectures"); 12.x still supports them.
  - The T4 is Turing (sm_75), so it is fine with 12.4+ and 13.x.
  - A P100 (Pascal, sm_60) would need a 12.4-12.9 image. bullet links
    cuBLAS, so under CUDA 13 it is expected to fail (**UNVERIFIED**, not
    tested).
- **One GPU per trainer:** `ValueTrainerBuilder::use_device(ordinal)` picks
  the device, and there is no multi-GPU training. On "T4 x2", one session
  could run two independent trainings (two processes, devices 0 and 1)
  sharing the 4 CPU cores. Throughput is **UNVERIFIED**.

### 1.3 How a training run is defined

A training program is a Rust `main` (an example or Fork's own binary)
that:

1. **builds a trainer** with `ValueTrainerBuilder`:
   - `dual_perspective()`;
   - an optimiser (`AdamW`, `RAdam` or `Ranger`);
   - an input type (`Chess768`, the bucketed variants, factorised inputs);
   - optional output buckets (e.g. `MaterialCount`);
   - `save_format(&[SavedFormat...])`;
   - a loss function;
   - `build(|builder, stm, ntm[, buckets]| ...)`, a closure describing the
     forward pass with graph nodes: `new_affine(name, in, out)`, `forward`,
     activations such as `screlu`/`crelu`, `concat`, `select` and so on;
2. **sets a `TrainingSchedule`:**
   - `net_id`;
   - `eval_scale` (the sigmoid scale applied to the stored score);
   - `TrainingSteps { batch_size, batches_per_superbatch, start_superbatch, end_superbatch }`;
   - `wdl_scheduler` (the blend weight of game result against score);
   - `lr_scheduler`;
   - `save_rate` (checkpoint every N superbatches, and at the end);
3. **sets `LocalSettings`:**
   - `threads` (loader threads besides the main thread);
   - `output_directory`;
   - `batch_queue_size`;
   - `test_set` (validation: bullet prints that it is "not currently
     implemented");
4. **calls `trainer.run(&schedule, &settings, &loader)`.**

Facts that matter for Fork's spec (from `value.rs` and the examples):

- **Training target:**
  - The stored score is divided by `eval_scale` and passed through a
    sigmoid (an alternative fixed win-rate model also exists).
  - The game result (0, 0.5 or 1) is blended in with the scheduler's
    weight.
  - The loss compares that target with the network output (the example
    applies the sigmoid to the output and uses squared error).
  - **Score and result are taken from the side-to-move's view** after the
    loader's conversion (section 1.6).
- **Weight names:** `new_affine("l0", in, out)` creates weights `l0w`
  (shape out x in) and biases `l0b` (out x 1). These names are the ids used
  by `SavedFormat::id`.
- **Weight clipping:** AdamW's default clips every weight to ±1.98 (the
  default `AdamWParams`; the simple example's comment says the same).
  `set_params_for_weight` changes it per tensor. This bounds what fits
  into the quantised integer types.
- **Optimiser maths:** bullet's AdamW update has no bias correction and no
  step counter (`trainer/src/optimiser/adam.rs`), which is why a
  checkpoint holds the whole optimiser state.

### 1.4 Checkpoints and resume (12-hour Kaggle sessions)

- **When saved:** at every superbatch that is a multiple of `save_rate`,
  and at the last one.
- **Where:** a directory `<output_directory>/<net_id>-<superbatch>/`
  containing:

| File | Content |
|---|---|
| `optimiser_state/weights.bin` | every weight tensor, as named records (layout in 1.5) |
| `optimiser_state/momentum.bin`, `velocity.bin` | AdamW's two moment buffers, same record layout (other optimisers write their own files) |
| `raw.bin` | f32 values of each `SavedFormat` entry that has an id, **before** any transform (so no transpose and no factoriser merge), no padding; `custom` and `empty` entries are skipped |
| `quantised.bin` | the `SavedFormat` byte stream (layout in 1.5), padded to 64 bytes. If any value overflows its integer type, this file is **not written** (an error line is printed) and training continues |
| `log.txt` | one line per logged batch: superbatch, batch, loss (comma-separated) |

- **How to resume:**
  - call `trainer.load_from_checkpoint("<dir>")` (`ValueTrainer`, in
    `value/save.rs`). It reads `optimiser_state/` and exits the process on
    an error.
  - Or call `trainer.optimiser.load_weights_from_file(".../weights.bin")`
    to load the weights only (a warm start with fresh moments).
  - **The superbatch counter is not stored.** Set `start_superbatch` to
    the checkpoint's superbatch + 1 and keep every other schedule value
    unchanged. The LR and WDL schedulers are functions of (batch,
    superbatch), so they continue correctly.
- **Data position:**
  - `DirectSequentialDataLoader` (bulletformat files) **skips** the
    positions already consumed (`start_batch × batch_size`, wrapping over
    the files).
  - `ViriBinpackLoader` **ignores** the skip count. It starts again from
    the files' beginning (or a fresh random interleave), shuffles with an
    RNG seeded from the system clock, and loops over the files forever.
  - Consequence: K6's "loss continues from the saved point" and "weights
    identical at the resume point" are testable, but a run is **not
    reproducible bit for bit**, resumed or not.
- **Disk:** each checkpoint holds about 3 copies of the float weights plus
  `raw.bin` and `quantised.bin`. For a net of about 400 KB quantised that
  is a few MB per checkpoint, far below `/kaggle/working`'s 20 GB.
  Keep `save_rate` small enough that a 12-hour cut loses little work.
- **Session chaining:** the next session attaches the previous one's
  output (notebook output as an input, section 4.5) and calls
  `load_from_checkpoint` on the newest directory.

### 1.5 Output layouts (for Fork's reader and converter)

All of this comes from `trainer/src/model/weights.rs`,
`bullet_lib/src/value/save.rs` and `docs/4-saved-networks.md` at
`da426a49`.

**General conventions:**

- Every primitive is little-endian.
- A weight of shape rows x cols is stored **column-major**: element (r, c)
  is at index `c·rows + r`.
- For an affine layer the weight shape is out x in. So, without a
  transpose, the `out` values of input column `c` are contiguous. For the
  first layer, that means the N accumulator weights of feature `c` sit
  together: the order an accumulator wants.
- Biases are out x 1 (out values in order).

**`quantised.bin`:**

1. For each `SavedFormat` entry, in the order given to `save_format`:
   - `SavedFormat::custom(bytes)` writes those bytes verbatim (a header,
     padding and so on).
   - `SavedFormat::id(name)` starts from the named weight's f32 values
     (column-major). Then every `.transform(f)` and `.transpose()` runs in
     the order written. `.transpose()` turns the column-major rows x cols
     buffer into row-major order.
   - The value is then quantised: multiplied by the factor and
     **truncated toward zero** by default, or **rounded** if `.round()` was
     given (where `.round()` appears in the chain does not matter).
     The exact rule (multiply in f64, round half away from zero) is in
     bullet-internals.md §1 (2026-10-28). Target types: i8 (with an i16 factor), i16 (i16 factor), i32 (i32
     factor). With no `.quantise`, the value is written as f32.
   - A value that does not fit its type aborts the whole file (it is not
     clamped).
   - `SavedFormat::empty()` starts from no values. It is for building
     interleaved tensors with transforms.
2. Entries are concatenated with **no names, sizes, shapes or
   separators**. The reader must know the architecture.
3. Then the file is padded to a multiple of 64 bytes, repeating the bytes
   `b`, `u`, `l`, `l`, `e`, `t` (cut off wherever the padding ends). No
   padding is added if the length is already a multiple of 64.

**`optimiser_state/weights.bin`** (and `momentum.bin`, `velocity.bin`):

- A sequence of records, one per weight tensor, in **lexicographic order
  of the weight name** (a BTreeMap). Each record is:
  1. the name in ASCII;
  2. one newline byte (0x0A);
  3. an 8-byte little-endian unsigned element count (`usize` on 64-bit);
  4. that many f32 values, column-major for the tensor's shape.
- Shapes are not stored. This file holds **every** trainable tensor
  (including factoriser weights that the quantised file merges away), so
  it is the right input for Fork's numpy float reference (R-float). Read
  it by name, not by position.

**Practical rule for Fork's converter (deliverable 5):**

- Fork's training program chooses the `SavedFormat` list, so the
  quantised layout is Fork's own decision. Fork can even emit its header
  first with `SavedFormat::custom`.
- Either way the converter must check the total byte count against the
  architecture, plus the 64-byte padding with the `bullet` filler.
  That catches a wrong tensor order or a missing transpose early.
- The parity test's corrupted-weight and transposed-tensor cases (DESIGN
  deliverable 6) remain the real guard.

### 1.6 What the network sees: Chess768 and the perspective convention

From `bullet_lib/src/game/inputs/chess768.rs` and bulletformat's
`ChessBoard`:

- **Training positions become `ChessBoard` records**, stored relative to
  the side to move:
  - when Black is to move, every square is mirrored vertically (index XOR
    56) and the colours are swapped;
  - score and result are flipped to the side to move.
- **`Chess768` emits two feature indices per piece.** For a perspective P
  (White or Black), the index is
  `384·[piece colour ≠ P] + 64·type + square_P`, where:
  - type runs 0-5 (pawn, knight, bishop, rook, queen, king);
  - `square_P` is the square index (a1 = 0, h8 = 63), mirrored by XOR 56
    when P is Black.
- **The side to move's perspective feeds the trainer's `stm` input, and
  the other side's feeds `ntm`.** In the examples the first-layer outputs
  are concatenated stm first, so the output layer's first N weights pair
  with the side to move.
- **Bucketed input types** (`ChessBuckets`, `ChessBucketsMirrored`,
  factorised) change the index. If Fork chooses one, read its mapping in
  `game/inputs/` at the pin before writing the C++ feature code (bullet
  code may be read; Fork writes its own).

### 1.7 Evaluating a FEN from Rust (needed for parity leg T, K15)

- **Methods:** `ValueTrainer::eval_raw_output(fen)` returns the network's
  raw output vector. `ValueTrainer::eval(fen)` returns the single output,
  or, for a 3-output (WDL) head, the expected score computed with a
  softmax.
- **Mechanics:**
  - The FEN is parsed by bulletformat's text parser (`FEN | score |
    result`; the method appends a dummy score and result itself).
    Castling and en-passant fields are ignored, which is fine for piece
    inputs.
  - The forward pass runs on the **trainer's device** with the
    **current float weights**.
  - bullet's test example multiplies the raw output by the eval scale to
    get centipawns.
- **Float only.** bullet has no evaluator for `quantised.bin`; the
  quantised forward pass exists only as a commented sample in
  `examples/simple.rs`. Fork's R-int and F legs are Fork's own.
- **Backend:** CUDA, ROCm or Metal (whatever the trainer was built with).
  On the mock it cannot run. So **T must be produced on Kaggle**: either at
  the end of the training program, or in a short follow-up step that
  builds the same trainer, calls `load_from_checkpoint`, and evaluates the
  parity EPD. That makes DESIGN.md's fallback (T through the loss path)
  unnecessary.
- **Fallback path** if ever needed: `InMemoryTextLoader` reads a text file
  of `FEN | score | result` lines into memory and replays it in order
  (no shuffle).

---

## 2. bullet's data path (question 2)

### 2.1 Loaders (`bullet_lib/src/value/loader/`)

| Loader | Reads | Shuffles | Resume skip | Filter |
|---|---|---|---|---|
| `DirectSequentialDataLoader` | fixed-size records: bulletformat `ChessBoard` (32 B), also `MarlinFormat`, `CudADFormat`, `AtaxxBoard` | **no**: data must be pre-shuffled | yes | no |
| `ViriBinpackLoader` (`new`, `new_concat_multiple`, `new_interleave_multiple`) | **viriformat game files directly** | yes, in a RAM buffer | **no** | `ViriFilter::Builtin(Filter)` or `ViriFilter::Custom(fn)` |
| `SfBinpackLoader` | Stockfish binpacks | yes | no | custom function |
| `MontyBinpackLoader` | Monty binpacks | yes | no | custom function |
| `InMemoryTextLoader` | text lines `FEN \| score \| result` (white-relative score in cp, result 1.0/0.5/0.0) | no (whole file in RAM, replayed in order) | no | no |

Only the viriformat and bulletformat paths matter for Fork; the
Stockfish binpack path is irrelevant (data-policy rule 2).

**How the viriformat loader works** (`viribinpack.rs`):

- A reader thread pulls raw games:
  - **concat mode:** the files in order, looping forever;
  - **interleave mode:** first counts the games in every file with a full
    read, then repeatedly picks a file at random, weighted by its
    remaining games, and takes 16 consecutive games from it.
- Worker threads (the loader's `threads` argument) decode games into
  `ChessBoard` positions, applying the filter.
- A buffer of `buffer_size_mb` holds the positions. Its capacity in
  positions is `buffer_size_mb · 2^20 / 32 / 2`, so 1024 MB holds about
  16.8 million. It is shuffled (Fisher-Yates) and handed to training as
  one chunk.
- Positions of one game are therefore spread only within a buffer. A
  bigger buffer decorrelates them better. Kaggle's 29 GB RAM allows a
  buffer of several GB (choose and measure).

### 2.2 Filters (skip in-check, captures, mate scores)

- **Built-in `Filter` (viriformat 2.0.1, docs.rs API page).** Its public
  fields:
  - `min_ply`; `min_pieces`;
  - `max_eval` (drops |eval| above it, which removes mate scores if they
    are stored large);
  - `filter_tactical` (drops positions where "a tactical move was made");
  - `filter_check` (drops in-check positions);
  - `filter_castling` (drops positions where a castling move was made);
  - `max_eval_incorrectness` (eval against result disagreement);
  - `random_fen_skipping` with `random_fen_skip_probability`;
  - a WDL-model-based skip (`wdl_filtered`, two 4-term parameter arrays,
    `material_min`, `material_max`, `mom_target`, `wdl_heuristic_scale`).

  It derives `Default` and serde. `Filter::from_path` reads a TOML file,
  and `Filter::UNRESTRICTED` is a constant that drops nothing.
  **UNVERIFIED:**
  - the default values (not shown in the API docs; the crate source was
    not opened);
  - the exact definition of "tactical" (captures and promotions are
    likely, not confirmed).

  So Fork's training program should spell out **every field** (struct
  update from `Filter::UNRESTRICTED`) rather than rely on `default()`,
  and test the filter on a fixture (a known game, count kept positions).
- **Custom filter:** `ViriFilter::Custom(fn(&Board, Move, i16, f32) -> bool)`
  receives the board before the move, the move played, the stored score
  and the result (1.0, 0.5 or 0.0), and returns **true to keep**. bullet's
  advanced example names its function "should_keep", and the loader
  negates it for viriformat's skip callback. `Board` and `Move` are
  viriformat's types: Fork's program may call their public API, but
  anything beyond the signature is **UNVERIFIED** here.
- **Mate scores:** the format stores a score, not a mate flag. Store mates
  as large scores (section 3.4) and drop them with `max_eval`, or drop
  them with a custom filter.
- **Filter at training time, not at datagen** (as DESIGN.md deliverable 2
  already says): it keeps the raw data complete for rescoring.

### 2.3 bullet-utils (`crates/utils`, needs no CUDA)

Build with `cargo b -r --package bullet-utils`.

| Subcommand | Does | Notes |
|---|---|---|
| `convert --from marlinformat\|cudadformat\|text\|ataxx -i IN -o OUT [-t THREADS]` | to bulletformat | `text` holds every position in RAM before writing |
| `shuffle -i IN -o OUT -m MEM_MB` | shuffles bulletformat (32-byte records) | if the file fits in `MEM_MB`, shuffled in RAM; otherwise split into `ceil(size / MEM)` temp files (at least 4) in `OUT.tmp/`, each shuffled in RAM, then interleaved into OUT and the temp folder deleted |
| `interleave IN1 IN2 ... -o OUT` | random merge of bulletformat files, each record drawn in proportion to the remaining counts | streaming |
| `validate -i IN` | checks bulletformat records: one king each, king squares match the stored ones, no pawns on the back ranks, 3-32 pieces | |
| `bucket-count` | counts positions per input bucket | |
| `viribinpack count FILE` | games and positions in a viriformat file | **stops silently** at the first record it cannot decode, so compare its counts with the manifest |
| `viribinpack head FILE -o OUT -g N` | the first N games | |
| `viribinpack interleave IN1 IN2 ... -o OUT` | random game-level merge of viriformat files | |
| `viribinpack splat FILE OUT [CFG.toml]` | **replays every game** and writes bulletformat, applying a `Filter` from the TOML (unrestricted if none) | the strongest external check of Fork's writer (section 3.6) |
| `montybinpack ...` | Monty format tools | not needed |

The RNG in `shuffle`/`interleave` is clock-seeded (not reproducible).

### 2.4 Disk and RAM for shuffling billions of positions

- **viriformat route (recommended):**
  - no shuffle file at all, since the loader shuffles in RAM;
  - disk is only the data itself, about 4 bytes per position plus 36
    bytes per game (32-byte header and 4-byte terminator);
  - RAM is the loader buffer you choose.
  - Example (*estimate*): 1 billion positions in games of about 100
    plies is about 4.4 GB on disk.
- **bulletformat route:**
  - 32 bytes per position, so 1 billion positions is 32 GB, about 7-8
    times the viriformat size, and the upload and the 200 GB private
    quota scale with it;
  - an on-disk shuffle needs the input, the temp copy and the output at
    the same time (**about 3 × the file**: 96 GB for 1 billion) and
    `-m` MB of RAM.
  - Only worth it if section 2.5 shows game decoding cannot keep the GPU
    busy.

### 2.5 Consequence: measure the loader before choosing

- Kaggle GPU sessions have **4 CPU cores** (Kaggle docs). Decoding games
  (replaying moves on a board, filtering, building features) runs on
  those cores. The fixed-size bulletformat loader is close to a memory
  copy.
- **Plan:**
  1. Build Fork's training program locally without a GPU feature.
  2. Run `measure_max_cpu_throughput` on a real Fork shard with 3-4
     loader threads (positions per second).
  3. Compare with the GPU's training rate from K5.
  4. If decoding is slower, `splat` the batch to bulletformat (locally or
     in a CPU session) and accept the 8× size.
- None of these speeds is known yet: **UNVERIFIED** until measured.

---

## 3. viriformat specification (question 3)

- **What it is:** a game-based binary format: one packed starting board
  per game, then 4 bytes per move.
- **Pin:** cosmobobak/viriformat `main` at
  `0238b315ea62...` (2026-10-03). README SHA-256
  `147711e1cd4be1f933fbe5e415615479fc01537aac5df1a41e0da2fb887ef466`.
- **Licence:** MIT, declared in `Cargo.toml` (and on crates.io for every
  version). The repository has **no LICENSE file**, and GitHub reports no
  licence. Fork uses only the spec (a data format, like UCI) and writes
  its own C++, so no notice ships with Fork. Cite the README in
  ORIGINALITY.md.
- **Versions:**

  | Version | Published |
  |---|---|
  | crates.io 2.0.1 (what bullet `da426a49` locks) | 2025-09-21 |
  | 3.0.0 | 2025-12-23 ("Use DFRC by default") |
  | the extension record | added to the README 2026-06-17, after 3.0.0; **no published crate version documents it** |

  The README for 2.0.1 (commit `5967bbac`) differs from main only in the
  extension record and in the example's nibble order (3.2).

### 3.1 File and game

- **Little-endian throughout.** Squares are numbered a1 = 0, h1 = 7,
  a8 = 56, h8 = 63.
- **File:** one or more games back to back. Nothing comes before the first
  game, and there is no file header or footer.
- **Game:**
  1. a 32-byte packed board (the marlinformat `PackedBoard`) for the
     starting position;
  2. zero or more (move, score) pairs, 2 + 2 bytes each;
  3. a terminator of 4 zero bytes, which reads as a move of 0 with a
     score of 0. A real move can never encode as 0 (a1 to a1).

### 3.2 The 32-byte packed board

| Offset | Size | Field |
|---|---|---|
| 0 | 8 | occupancy bitboard (u64), bit i set when square i holds a piece. Must not be zero (zero marks an extension record, 3.5) |
| 8 | 16 | 32 four-bit piece codes. Entry k describes the k-th occupied square counting from the least significant set bit. **Entry k sits in byte 8 + k/2: the low nibble for even k, the high nibble for odd k.** Unused entries may be 0 |
| 24 | 1 | side to move and en passant: bits 0-6 hold the en-passant target square, or 64 if none; bit 7 is 0 for White to move, 1 for Black |
| 25 | 1 | halfmove clock (may be 0) |
| 26 | 2 | fullmove number (u16; may be 0) |
| 28 | 2 | a score for this position (i16, same convention as move scores; may be 0) |
| 30 | 1 | game result: 0 Black won, 1 draw, 2 White won (no other value is valid) |
| 31 | 1 | unused (write 0) |

**Piece code** (4 bits):

- **Bits 0-2, the type:** 0 pawn, 1 knight, 2 bishop, 3 rook, 4 queen,
  5 king, **6 a rook that still carries a castling right** (in standard
  chess, the a1/h1/a8/h8 rook whose side may still castle). 7 is invalid.
- **Bit 3:** 0 for a White piece, 1 for a Black piece.
- **Castling rights exist only in that unmoved-rook code.** There is no
  separate castling field.

**Nibble order: the trap.**

- In the current README's start-position example, byte 8 holds the a1
  rook in its low nibble and the b1 knight in its high nibble.
- In the v2.0.1-era README the example had the two nibbles reversed. Commit
  `db799183` (2026-04-08, titled "tentative: reorder readme example
  nibbles") changed it.
- Independent evidence that low nibble first is right: bulletformat
  1.8.0's marlinformat iterator reads entry k from byte k/2 shifted right
  by 4·(k mod 2), the same layout. So does its own `ChessBoard`.
- Fork's writer uses low nibble first, and the round-trip check in 3.6
  confirms it against bullet's actual reader.

### 3.3 Moves (16 bits, little-endian)

Bit layout, from the least significant bit (confirmed by decoding the
README example's moves, e.g. 1. e4 decodes to from = 12, to = 28):

| Bits | Field |
|---|---|
| 0-5 | from square |
| 6-11 | to square |
| 12-13 | promotion piece: 0 knight, 1 bishop, 2 rook, 3 queen (may be 0 when not a promotion) |
| 14-15 | move type: 0 normal (including normal captures and double pushes), 1 en-passant capture, 2 castling, 3 promotion (including capture-promotions) |

- **Castling is written king-takes-rook:** from the king's square to its
  own rook's square. Standard chess: White O-O is e1->h1, O-O-O e1->a1;
  Black e8->h8 and e8->a8. Type 2.
- **En passant:** the to-square is the capturing pawn's destination (the
  ep target square); type 1. This is the natural reading, since the README
  only says "en-passant captures are 1".

### 3.4 Scores and results

- **Each move's score** is a signed 16-bit integer, **from White's point
  of view**, "for said move".
- The sensible reading is the search score of the position in which the
  move is played: the score of the search that chose it. bullet's
  filter callback receives (board before the move, move, score), which
  matches. The README does not say so in so many words: Fork's spec
  should state the convention it writes and test it with `splat`.
- **Mate scores:** the README example writes +32767 for positions where
  White mates (the move before the mate and the mating move). Fork chooses
  its own encoding, but it must be i16, white-relative, and outside any
  `max_eval` used for normal positions. For example, Fork's internal mate
  scores (if they fit in ±32767) converted to White's view, or a fixed
  ±32767.
- **The header score** may be left at 0.
- **The result** is game-level and white-relative (0, 1, 2).
  - bullet converts it to the side to move's view per position.
  - TB-adjudicated games store the tablebase result.

### 3.5 Extension record (main README only)

- **Layout:**
  1. 8 zero bytes where an occupancy would be;
  2. a u16 extension id;
  3. a u16 payload length N;
  4. N payload bytes;
  5. 4 zero bytes.
- Readers that do not know the id skip it. No ids are registered yet.
- **Do not write it for bullet `da426a49`:** that pin's viriformat 2.0.1
  predates the record. How 2.0.1 reacts to a zero occupancy is
  **UNVERIFIED** (source not opened); assume it fails.

### 3.6 Checklist for Fork's C++ writer and its acceptance tests

Writer rules:

1. **Header:**
   - occupancy from Fork's board;
   - nibbles in ascending square order, low nibble first;
   - castling as type 6 on exactly the rooks whose rights remain;
   - en-passant square or 64;
   - stm bit;
   - halfmove and fullmove filled in (useful later for rescoring, and for
     Fathom, which probes WDL only at halfmove 0);
   - header score 0 (or the first search score; choose one);
   - result written when the game ends;
   - byte 31 = 0.
2. **One (move, score) pair per position played**, with move types and
   king-takes-rook castling as in 3.3, scores white-relative.
3. **Four zero bytes** per game.
4. **The result lives in the header but is known only at the end.**
   Buffer the game in memory and write it whole (simplest, and keeps
   shards valid if the process stops mid-game).

En-passant convention, an **open choice**: whether to write the ep square
only when an ep capture is legal, or after every double push, is not
stated. It only affects the starting position of each game, since later
ep captures are typed explicitly. Fork's spec should pick one and the
tests should pin it.

Acceptance tests, beyond DESIGN.md's own (python-chess replay, round
trip, fuzz target):

- **bullet's tools read Fork's shards** (built locally, no CUDA):
  `viribinpack count` must equal the manifest's games and positions, and
  `viribinpack splat` must succeed. Running `validate` on the splatted
  file must find no invalid position.
- **A fixture game** with all the special moves (both castlings for each
  side, en passant, under-promotion, capture-promotion), checked through
  bullet's `ViriBinpackLoader` with a custom keep-all filter. Its
  positions must equal python-chess's replay of the same moves.

---

## 4. Kaggle in practice (question 4)

### 4.1 What changed since the KB's 2026-10-24 check

| Item | 2026-10-24 (training-data.md §2.1) | 2026-10-28 | Source |
|---|---|---|---|
| Free GPUs | T4 x2 (default) or P100 | CLI docs list "as of Sep 2026": NvidiaTeslaT4 (T4 x2), NvidiaTeslaA100, NvidiaL4, NvidiaL4X1, NvidiaH100, NvidiaRtxPro6000, TpuV5E8, TpuV6E8, "some only for specific competitions, some only for admins". **No P100.** Kaggle's image repo removed its P100 test stage on 2026-09-05 ("Drop P100 support", #1560). The Kaggle docs pages still describe P100 (likely stale). Free-tier availability of each: **UNVERIFIED** (K1) | kaggle-cli `docs/kernels.md`; docker-python commit `1ed8d435`; kaggle.com/docs/notebooks |
| GPU image base | not checked | Colab runtime image `release-colab-external-images_20260917-060051` (GPU), Python 3.13 packages path; `CUDA_HOME=/usr/local/cuda`; NVIDIA driver libraries mounted at run time in `/usr/local/nvidia/lib64` (added to `LD_LIBRARY_PATH` and `ld.so.conf`) | docker-python `Dockerfile.tmpl` at `c43593a3` |
| CUDA in the image | not checked | Colab's published package lists: Ubuntu 24.04 with **CUDA 12.8** (nvcc and NVRTC 12.8.93, cuBLAS 12.8.4) from 2026-09-04; CUDA 13.3 from 2026-09-21; CUDA 13.0 (driver-compat 580) from 2026-09-30. The Kaggle image of 2026-09-17 therefore most likely has 12.8 (**inference, UNVERIFIED**: the lists are not tied to image tags and may lag). Either version satisfies bullet's 12.4+ on a T4. **Kaggle will follow Colab's base images, so the CUDA major version can change under Fork** | googlecolab/backend-info commits `f1404247`, `e9534f11`, `b8506613` |
| Rust | not checked | not in the Colab apt list or Kaggle's Dockerfile: install with rustup each session (needs internet) or bring it in a dataset | backend-info `apt-list-gpu.txt`; Dockerfile |
| C/C++ toolchain | not checked | gcc/g++ 13 present (Ubuntu 24.04), `build-essential` installed by Kaggle's Dockerfile | backend-info; Dockerfile |
| Kaggle CLI | 2.2.5 resumes uploads | still 2.2.5 (released 2026-10-22); resume confirmed at head `a636fc70`; adds `kernels push --accelerator`, `-t/--timeout`, `--no-run`, and a `kernels logs` command (in the CLI source; not on the docs page) | kaggle-cli releases, `docs/kernels.md`, `src/kaggle/cli.py` |
| CLI auth | `~/.kaggle/kaggle.json` | also an API token: environment variable `KAGGLE_API_TOKEN`, or the file `~/.kaggle/access_token`; `KAGGLE_CONFIG_DIR` relocates the folder (on Linux, `~/.config/kaggle` is used when `~/.kaggle` does not exist) | `kaggle_api_extended.py` |
| Extra GPU hours | 30 h/week | still 30 h "or sometimes higher"; an experimental offer not in the KB's earlier notes (start date not stated): Colab Pro / Pro+ subscribers who link accounts get 15 / 30 extra Kaggle GPU hours per week (a "limited time promotion") | kaggle.com/docs/notebooks, /docs/efficient-gpu-usage |
| Scheduling | not checked | notebooks can re-run on a daily/weekly/monthly timer or when an attached dataset changes (at most once a day); the number of scheduled notebooks is limited (number not stated) | kaggle.com/docs/notebooks |
| Session, disk, idle | 12 h; 20 GB `/kaggle/working`; 20 vs 60 min idle conflict | unchanged on both pages (the 20/60 min conflict is still there); GPU sessions: 4 CPU cores, 29 GB RAM | same pages |
| Datasets | 200 GB/dataset, 200 GB private total, 50 top-level files, archives unpacked | unchanged | kaggle.com/docs/datasets |

### 4.2 Building bullet in a Kaggle GPU notebook (the plan to test)

Each step below follows from the pages cited. None was run here.

1. **Kernel metadata** (`kernel-metadata.json`, kaggle-cli
   `docs/kernels_metadata.md`):
   - `enable_gpu: true`, `enable_internet: true`,
     `machine_shape: NvidiaTeslaT4`;
   - `kernel_type: script` or `notebook`, `is_private: true`;
   - `dataset_sources` holds the data batches; `kernel_sources` holds the
     previous run's notebook (its output is mounted for resume).
   - The CLI defaults are internet **off** and GPU **off**, so both must
     be set.
2. **Install Rust:**
   - rustup's official shell installer, with options passed after
     `sh -s --`;
   - `-y` (`--yes`) skips the prompt (rustup-init's help text);
   - `--profile minimal` and `--default-toolchain <pinned version>` are
     documented options.
3. **Set `CUDA_PATH=/usr/local/cuda`.** bullet reads `CUDA_PATH`, not
   `CUDA_HOME`.
4. **`cargo build --release --features cuda`** of Fork's `tools/train`,
   with the committed `Cargo.lock` and `--locked`.
5. **Link step risk:** `build.rs` adds only `$CUDA_PATH/lib64` to the link
   path. On Kaggle the driver's `libcuda.so` is in `/usr/local/nvidia/lib64`.
   The toolkit usually also ships a link stub in `lib64/stubs`
   (**UNVERIFIED** for this image). If linking `-lcuda` fails, pass the
   extra directory to the linker:
   `RUSTFLAGS="-L native=/usr/local/nvidia/lib64"`, or the stubs folder.
   K4 settles it.
6. **Offline variant** (if internet is off or flaky in GPU sessions):
   - `cargo vendor` (Cargo book) copies every crates.io and git
     dependency into a folder; attach it as a dataset together with a
     Rust toolchain (rustup's standalone installers; not checked here),
     and build with `--offline`.
   - More moving parts than the binary fallback below; keep it as
     plan C.

### 4.3 Prebuilt binary as a dataset (fallback)

- **Build once**, in a GPU or CPU Kaggle session (the CUDA toolkit is in
  the image either way), or locally in WSL with a CUDA toolkit installed.
  Upload the binary as a private dataset. Linking needs the toolkit
  libraries; no GPU is needed to compile.
- **Catch:**
  - the binary links `libcudart`, `libnvrtc` and `libcublas` by their
    major-version names (standard Linux shared-library practice; check
    with `ldd`), and glibc by version;
  - a binary built against CUDA 12.x will not start on an image that
    moved to CUDA 13 (Colab already has);
  - building inside a Kaggle session on the current image avoids both
    mismatches, so a binary built **in** a Kaggle session is the safer
    fallback.
- **Rebuild whenever** `nvcc --version` or `ldd` changes in the run log
  (log both in every run).

### 4.4 Running headless from the CLI (kaggle-cli `docs/kernels.md`)

- **`kaggle kernels push -p DIR`:**
  - uploads the code file and its metadata, creates or updates the
    kernel, and **starts a run** (a full top-to-bottom run, which is what
    the web's "Save & Run All" commit does);
  - options: `--accelerator NvidiaTeslaT4`, `-t SECONDS` (maximum run
    time), `--no-run` (save only).
  - Only the code file is uploaded; data must come from attached sources.
- **`kaggle kernels status OWNER/SLUG`** reports the latest run's status
  and any failure message. Poll it. The exact status strings are an enum
  in kagglesdk, not listed in the docs: record them in K7.
- **`kaggle kernels output OWNER/SLUG[/VERSION] -p DIR`** downloads the
  output files (`--file-pattern REGEX`, paging options); a version can be
  named.
- **`kaggle kernels logs`** gets a run's log (CLI source only).
- **`kaggle kernels pull -m`** gets the code and metadata back.
- **Commit runs are subject to the 12-hour limit** (docs/notebooks).
  Whether the interactive idle timeout affects them: the docs imply not
  (K12).

### 4.5 Chaining sessions (checkpoint carry-over)

- Notebook outputs (up to 20 GB from `/kaggle/working`) can be attached as
  inputs to other notebooks (docs/notebooks, "Notebooks" data section),
  and `kernel_sources` attaches a kernel in the metadata.
- **UNVERIFIED:** whether `kernel_sources` always mounts the latest
  version's output, and whether a notebook can attach **its own** previous
  output.
- Robust fallback that needs neither:
  1. download the checkpoint with `kaggle kernels output` (a few MB for
     B0);
  2. publish it as a small private dataset ("fork-ckpt-<run>");
  3. attach that dataset to the next run.

### 4.6 Secrets

- **Defining:** Kaggle Secrets are defined only in the web editor
  (Add-ons -> Secrets); the CLI cannot create them.
- **Reading:** code reads them with `UserSecretsClient().get_secret(label)`
  from the preinstalled `kaggle_secrets` package. It works only inside
  Kaggle, and only for secrets **attached to that notebook**
  (kaggle-cli `docs/kernels.md`; docker-python `patches/kaggle_secrets.py`).
- **Does a notebook need any secret?** Only if it calls an external
  service: a GitHub release upload, or a Kaggle API call from inside the
  notebook (for example to create the checkpoint dataset of 4.5). The
  plain training run needs none.
- **The local CLI token never goes into a notebook, dataset or
  repository.** Also: the CLI's resumable-upload state, which holds
  signed upload URLs, lives in `<system temp>/.kaggle-uploads-<uid>/`
  (owner-only permissions; source). It must never be copied anywhere.

### 4.7 Dataset upload: limits and resume

- **Commands:**
  - `kaggle datasets create -p DIR` (private by default; `-u` makes it
    public);
  - `kaggle datasets version -p DIR -m MSG [-d]`;
  - `kaggle datasets status`, `kaggle datasets files`.
  - `-t` keeps tabular files as they are (irrelevant for binary shards).
- **Subfolders:** `-r/--dir-mode` takes `skip` (the default: subfolders
  are ignored), `zip` (compressed) or `tar` (uncompressed). With Kaggle's
  50-top-level-file limit this means:
  - **at most 50 shard files per batch dataset, at the top level**
    (simplest; for example 25 shards of 2 GB is 50 GB per batch); or
  - one zip per batch (Kaggle unpacks archives; zip compression gains
    little on packed data and costs CPU).
  - **UNVERIFIED:** whether a `tar` upload is unpacked.
  - **DESIGN.md deliverable 3 should drop "in a subfolder".**
- **Resume** (`kaggle_api_extended.py` at `a636fc70`):
  - each file goes up as a Google Cloud Storage resumable upload;
  - its state is saved per file in the temp folder above;
  - re-running the same command resumes if the state is younger than
    6 days (GCS's one-week limit), with up to 10 resume attempts per run;
  - `--no-resume` disables it.
  - **WSL caveat:** if `/tmp` is cleared (for example on a WSL restart),
    the state is lost and the upload starts over: lost time, not lost
    data. Whether this WSL setup clears `/tmp` is **UNVERIFIED**.
- **Still UNVERIFIED** (K8, K11): the maximum single-file size; whether
  `version` re-sends unchanged files; read speed of mounted inputs; the
  scratch-disk size; phone verification.

---

## 5. Syzygy WDL probes from many datagen threads (question 5)

- **What Fork vendors:** Fathom from jdart1/Fathom at
  `c9c6fef0dddc05d2e242c183acf5833149ab676d` (MIT). It is still `master`'s
  head on 2026-10-28 (`git ls-remote`). The README at the pin (SHA-256
  `8a44c2a0...cd074b`, identical to tools.md §6.1's table) says:
  - `tb_probe_wdl` is thread-safe unless `TB_NO_THREADS` is set;
  - the root-probe functions (`tb_probe_root`, `tb_probe_root_dtz`,
    `tb_probe_root_wdl`) are meant for the root but are also thread-safe;
  - `tb_init` and `tb_free` set up and release the tables (no
    thread-safety claim).
- **Unchanged from tools.md §6.5:** the header's older "root probe not
  thread-safe" note conflicts with the README. The maintainer explained it
  as outdated documentation (PR #10). Concurrent probing has not been
  tested on this machine.
- **For datagen:**
  - **Threads:** one `tb_init` per process before any worker starts, and
    no `tb_free` or path change while workers run. Then concurrent
    `tb_probe_wdl` calls from all worker threads are within the documented
    guarantee.
  - **Never define `TB_NO_THREADS`** in the engine/datagen build.
  - **Processes:** if datagen ever runs as several processes instead,
    each maps the tables itself (the page cache is shared). No locking
    question arises.
  - **Probe conditions** (tools.md §6.7): WDL probes fail when the
    halfmove clock is nonzero or castling rights remain. In self-play, the
    piece count drops only on a capture, which resets the halfmove clock
    to 0. So **probe immediately after the capture that brings the board
    within the tables' piece count** (5 pieces with the local 3-4-5 set).
    That probe succeeds, and its WDL decides the adjudicated result. Later
    positions of that game are not probed (they will not be: the game
    ends).
  - **Cursed wins and blessed losses** (the 50-move rule turns them into
    draws) must map to draws for the game result. That rule belongs in
    Fork's spec.
  - **Test (Phase 4, deliverable 2):** a datagen run with 10 threads
    against the 3-4-5 tables under ThreadSanitizer (`{clang,gcc}-tsan`
    presets) and a TB-heavy opening set. That gives the first concurrent
    test of Fathom on this machine (tools.md UNVERIFIED item 12).

---

## 6. Lichess CC0 database as datagen openings (question 6)

Source: https://database.lichess.org/ (opened 2026-10-28), its standard
`sha256sums.txt` and `list.txt`, and HTTP `HEAD` requests for three files
(no file downloaded).

- **Licence:** all exports CC0 (the page's header).
- **Size today:**
  - 165 monthly standard files, 2.6 TB, 8,220,312,882 games in total;
  - recent months are about 28-33 GB compressed each (2026-09: 29.2 GB,
    89,616,462 games; `HEAD`: 29,224,520,887 bytes);
  - uncompressed is "about 7.1 times larger";
  - zstd files can be decompressed partially and streamed (`zstdcat`).
- **Older months are far smaller:**

  | Month | Size | Games |
  |---|---|---|
  | 2013-01 | 17.8 MB | 121,332 |
  | 2015-01 | 286 MB | 1,497,237 |
  | 2016-01 | 872 MB | 4,770,357 |
  | 2016-09 | 1.21 GB | 6,813,113 |
  | 2016-12 | 1.7 GB | 9,433,412 |
  | 2017-01 | 1.9 GB | 10,680,708 |
  | 2018-01 | 5.47 GB | 17,945,784 |
  | 2020-01 | 13.7 GB | 46,800,709 |

- **Checksums:** `https://database.lichess.org/standard/sha256sums.txt`
  (one `<sha256>  <file name>` line per month, 165 lines). Download list:
  `standard/list.txt`.
- **Headers to use:**
  - `WhiteElo` and `BlackElo` (Glicko-2 ratings);
  - `WhiteTitle` / `BlackTitle`: **players using the Bot API are marked
    `[WhiteTitle "BOT"]` or `[BlackTitle "BOT"]`**; drop any game with
    either;
  - `Event` (for example "Rated Bullet tournament ...");
  - `TimeControl` (for example `300+0`);
  - `Termination` (for example "Time forfeit");
  - also `Result`, `UTCDate`/`UTCTime`, `ECO`/`Opening` and
    `WhiteRatingDiff`/`BlackRatingDiff`.
  - Variant games carry a `Variant` tag (absent in the standard files'
    sample).
- **Comments to strip:**
  - About 6 % of standard games carry engine evaluations in move comments,
    as `[%eval 2.35]` (centipawns ×100, White's view) or `[%eval #-4]`
    (mate in N); these are Stockfish's.
  - Clocks appear as `[%clk 0:00:30]` since April 2017.
  - Fork's opening tool should **ignore every comment** (DESIGN.md
    deliverable 1 already says so), not just strip `%eval`.
- **Known issues that affect month choice** (the page's "Known issues"):
  - all months before March 2016, and June 2020: some players played
    themselves in rated games;
  - up to August 2016: 7 games with illegal castling moves;
  - 12 March 2021: some wrong results.
  - Evaluation problems (December 2016, July-August 2020) do not matter,
    since evals are ignored.
- **Suggested first month: 2016-09.**
  - It is the first month after both the self-play and illegal-castling
    windows.
  - Size 1,213,809,361 bytes (`HEAD`), 6,813,113 games, `Last-Modified`
    2022-11-04.
  - SHA-256
    `3a4d18db787db558083aacb7c27ab3588f0745c1baaca37846b3f0d8b9677db3`.
  - Alternatives: 2016-10 (1.35 GB,
    `f2ba328354509957e9e916bb89c956a1e3d09eeec0785534c492425ec2855c79`)
    and 2016-12 (1.7 GB,
    `285d09bcb7f47af2d58594ecee7da8c18f9e800fd7df2e0158b4fb5429f9a904`).
  - **UNVERIFIED:** how many games in such a month have both players
    rated 2000 or more. Count it with the opening tool's first run. If too
    few, move to a later month.
- **Provenance caveats:**
  - **UNVERIFIED:** whether games of accounts later closed for engine use
    were removed from the exports (the page does not say).
  - The Bot API (and so the BOT title) did not exist in early months, so
    pre-Bot-API engine accounts would not be tagged (**UNVERIFIED**: the
    page gives no Bot API start date).
  - Fork takes only an early-opening position plus random plies, so
    engine influence on its openings is small. But this is a reason to
    keep the rating floor and the random plies.

---

## 7. Streamlining the loop (question 7)

| Idea | What the docs confirm | What is UNVERIFIED |
|---|---|---|
| **Background upload while datagen runs** (DESIGN deliverable 3) | CLI uploads resume per file on re-run (6-day window, 10 attempts per run); `create` is private by default; datasets are mounted read-only in notebooks; up to 50 top-level files per dataset | effect on datagen throughput and on benchmarks (measure); max file size; whether WSL clears the resume state |
| **Upload confirmation in a CPU session** | CPU sessions exist (4 cores, 30 GB); GPU quota is a GPU-only quota; `kernels push` without `enable_gpu` runs on CPU | that CPU sessions consume no GPU quota (K9 checks); mounted-read speed |
| **Automatic kernel pushes** | `kernels push -p DIR [--accelerator] [-t]` starts a commit run; `status` polls; `output` downloads (paging, regex); `logs` exists | status strings; whether a pushed run keeps going with the browser closed (expected: yes, commit runs are server-side, K7) |
| **Chaining 12-hour runs** | notebook outputs can be inputs; `kernel_sources` in metadata | whether `kernel_sources` pins a version or tracks the latest; self-reference. Fallback: checkpoint republished as a small dataset (4.5) |
| **Two trainings per T4 x2 session** | bullet selects a device per trainer (`use_device`) | data-loading on 4 shared cores (measure); whether it counts as one session's quota (expected) |
| **Compile-check locally before pushing** | bullet's CI compiles and tests the workspace with no GPU feature; the mock runtime type-checks; `measure_max_cpu_throughput` runs on the mock | that Fork's full program builds without features (try it; it should, as bullet's CI does) |
| **One script: download net, convert, parity, SPRT** | the pieces exist or are specified: `kaggle kernels output` (download), DESIGN deliverable 5 converter, `fork netcheck` and the `nnue_parity` ctest (deliverable 6), `tools/sprt.sh` locally or `.github/workflows/sprt.yml` (manual `workflow_dispatch`, at most 16 shard jobs; KB tools.md §11) | `sprt.yml` has not run yet; a CLI trigger for it is `gh workflow run` (GitHub CLI; not re-checked here) |
| **GitHub Actions for SPRT** | public-repo standard runners are free; 6-hour job cap; 20 concurrent jobs on Free; the Actions terms allow testing of the repository's own software (tools.md §11, verified 2026-10-27) | GitHub's view of sustained engine-match load ("disproportionate burden"); runner CPU model (tools.md §11 UNVERIFIED items) |
| **Kaggle orchestration from GitHub Actions** | the CLI authenticates with `KAGGLE_API_TOKEN`, which an Actions secret could supply | not recommended now: a 12-hour training run outlasts the 6-hour Actions job cap, so polling needs a scheduled workflow; secrets in a public repo's workflows need care (whether fork pull requests can read them was not re-checked). Orchestrate from WSL instead |
| **Kaggle scheduling** (timer or dataset-update trigger) | exists, at most once a day for the dataset trigger | limits on scheduled notebooks; not useful with immutable per-batch datasets; skip |
| **Skip the bulletformat conversion** | the viriformat loader reads game files directly and shuffles in RAM | that its decode speed on 4 cores keeps a T4 busy (2.5) |

Recommended shape (my synthesis, for the spec):

1. **Datagen** writes viriformat shards plus manifest lines (deliverable
   2).
2. **`upload.sh`**, beside datagen: one private dataset per batch, at most
   50 top-level shards, re-run until `datasets status` is ready, then a
   CPU hash-check kernel (`kernels push`), compare, delete local shards
   (deliverable 3).
3. **`train.sh`** (WSL): write `kernel-metadata.json` (batches,
   previous-checkpoint dataset, T4), `kernels push`, poll `status` every
   few minutes, then `kernels output` into a run folder. Log `nvidia-smi`,
   `nvcc --version`, `ldd` and the run record from the notebook's output.
4. **`accept.sh`:** convert `quantised.bin` -> Fork net file, run the
   parity legs (T from the run's `parity-trainer.txt`), build, run
   `fork netcheck`, then start the SPRT (local `tools/sprt.sh` or
   `gh workflow run sprt.yml`).

The owner only starts datagen and reads verdicts.

---

## 8. Kaggle test session checklist (question 8)

DESIGN.md (main) already has K1-K16. Below:

- each check re-stated with what this research changes (**bold**);
- new checks K17-K22.

Run them in one session with the owner (he holds the account); record
every result in training-data.md §2.1 and the decisions log.

| # | Check | How | Acceptable |
|---|---|---|---|
| K1 | GPU and internet allowed | Settings; phone verification if asked; **note which accelerators the GPU menu offers** | **T4 x2 available** (P100 is probably gone; record what is offered) |
| K2 | Internet in a GPU session | `curl -sI https://static.rust-lang.org` and `https://index.crates.io` | HTTP 200 for both, else the offline variants (4.2 step 6, 4.3) |
| K3 | CUDA and driver | `nvidia-smi` (driver version, CUDA version, GPU name), `nvcc --version`, `ls /usr/local/cuda/lib64 \| grep -E 'nvrtc\|cublas\|cudart'`, `ls /usr/local/cuda/lib64/stubs` | **toolkit 12.4 or newer and a driver at least as new** (bullet binds `cuFuncLoad`, first documented in 12.4); NVRTC and cuBLAS present |
| K4 | Rust and bullet build | rustup (`-y`, minimal profile, pinned toolchain); `CUDA_PATH=/usr/local/cuda cargo build --release --locked --features cuda`; time it | builds in under 30 min; **if `-lcuda` fails, retry with `RUSTFLAGS="-L native=/usr/local/nvidia/lib64"` or the stubs folder and record which worked** |
| K5 | Toy training run | 1-2 superbatches on a ~10 M-position Fork sample | loss falls; positions/s recorded |
| K6 | Checkpoint and resume | save at superbatch N, stop; second session attaches the output, `load_from_checkpoint`, `start_superbatch = N+1` | `weights.bin` hash at load equals the saved one; loss continues near the saved level. **Do not expect bit-identical continuation** (clock-seeded viriformat shuffle) |
| K7 | Headless runs | `kaggle kernels push` from WSL; poll `kaggle kernels status`; `kaggle kernels output`; `kaggle kernels logs` | completes with no browser open; **record every status string seen**; outputs download |
| K8 | Dataset upload and resume | `kaggle datasets create -p DIR` with **shards at the top level** (no subfolder), interrupt once (Ctrl-C), re-run; `kaggle datasets files` | resume message seen, sizes match, files under `/kaggle/input/<slug>/` |
| K9 | Mounted-data hash check | CPU-only kernel hashes the shards | SHA-256 matches the manifest; quota page shows no GPU time used |
| K10 | Read speed | time a full sequential read of a mounted shard in the GPU session | faster than K5's consumption rate |
| K11 | Scratch disk, file limits | `df -h /kaggle/working /kaggle/temp /tmp /`; upload one large (e.g. 5 GB) test file | recorded; shard size set below what worked |
| K12 | Idle timeout and session length | as DESIGN | recorded; training only as commit runs |
| K13 | Weekly quota | quota display before and after | recorded |
| K14 | Secrets | read one attached secret in the notebook | works; nothing secret in any output file |
| K15 | Trainer evaluation of fixed positions | **`ValueTrainer::eval_raw_output` on each parity FEN after `load_from_checkpoint`**, written to `parity-trainer.txt` | one score per position; repeated calls give identical numbers (record whether two sessions agree too) |
| K16 | Terms | re-read kaggle.com/terms and /aup | still personal, non-commercial ML use |
| K17 | **Data-loader speed on Kaggle's 4 cores** | `measure_max_cpu_throughput` on a Fork shard (also runs locally on the mock); compare with K5 | decoding is not the bottleneck, otherwise splat to bulletformat (2.5) |
| K18 | **Shared libraries of the built trainer** | `ldd target/release/<trainer>`; `cat /etc/os-release`; `ldd --version` | all CUDA libraries resolve; versions recorded (the fallback binary must match them) |
| K19 | **Fallback binary in a fresh session** | attach the binary built in K4 as a private dataset; run its `--help` (or a 1-batch run) in a new session | starts and finds the GPU; if not, the fallback is rebuild-per-session |
| K20 | **Checkpoint carry-over route** | try `kernel_sources` pointing at the previous run; if it fails, the checkpoint-as-dataset route (4.5) | one route works and is written into `train.sh` |
| K21 | **Fork's viriformat shards accepted by bullet** (locally, before the session) | `bullet-utils viribinpack count` and `splat` on a Fork shard; `validate` on the result | counts equal the manifest; no invalid positions |
| K22 | **Both T4s usable** (optional) | two trainings at once on devices 0 and 1 (`use_device`) | both run; record the combined positions/s; the CPU is likely the limit |

---

### 8.1 Session 1 results (2026-10-28)

The owner ran main's `tools/train/kaggle/session_check.py` in one cell of a
private Kaggle notebook (GPU T4 x2, internet on). Its output, verbatim
except that the 57 library paths are summarised:

- **K2:** `https://github.com/` 200; `https://static.rust-lang.org/rustup/dist/`
  and `https://crates.io/` "HTTP Error 404: Not Found" (servers reached;
  real downloads untested).
- **K3 GPUs:** "Tesla T4, 580.178.04, 15360 MiB" twice; nvidia-smi header
  "Driver Version: 580.178.04 CUDA Version: 13.0".
- **K3 CUDA toolkit:** nvcc "Cuda compilation tools, release 12.8, V12.8.93";
  in `/usr/local/cuda/lib64` (same files under
  `/usr/local/cuda/targets/x86_64-linux/lib`): libcudart.so.12.8.90,
  libnvrtc.so.12.8.93 (and the `.alt` and builtins variants),
  libcublas.so.12.8.4.1, libcublasLt.so.12.8.4.1, plus the static
  archives. `libcuda.so.580.178.04` only in `/usr/local/nvidia/lib64`, which
  the loader cache (`ldconfig -p`) does not list.
- **K3 environment:** `CUDA_PATH` unset; `CUDA_HOME=/usr/local/cuda`;
  `LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda/lib64:/usr/local/cuda/lib64`.
- **K4:** `rustc` not installed.
- **K11:** free space `/kaggle/working` 19.5 GB, `/kaggle/input` 19.5 GB,
  `/tmp` and `/` 1,048.8 GB.
- **K17:** 4 CPUs; 31.3 GB RAM; Linux-6.18.55+-x86_64-with-glibc2.39;
  Python 3.13.15.

**Reading.** T4 x2 is confirmed. The toolkit (12.8) and the driver (CUDA
13.0) both meet the 12.4 minimum inferred in §1.2 and bullet-internals.md
§8, and the driver is newer than NVRTC; whether bullet builds and runs on
them stays open until session 2 (K4/K5). `libcuda` outside the loader
cache may matter when Rust links `cuda` at build time (§9 item 11):
session 2 sets `CUDA_PATH=/usr/local/cuda` and adds
`-L /usr/local/nvidia/lib64` if the link fails. The owner's manual items
(the accelerator menu, the weekly quota before and after, the idle
timeout, a per-file upload limit, the terms) were not yet reported.

## 9. UNVERIFIED items (with reasons)

1. **CUDA minimum for bullet `da426a49`.** It is 12.4+ by inference from
   `cuFuncLoad`'s first appearance in NVIDIA's archived docs; no bullet
   statement, and its CI never builds real CUDA (K3/K4).
2. **P100 under CUDA 13:** bullet expected not to run (cuBLAS 13 dropped
   Pascal). Not tested; NVRTC's own sm_60 support in 13.x not checked.
3. **Whether `ValueTrainerBuilder::build` works on the mock** device (only
   the throughput meter is documented to run there).
4. **Multi-GPU:** two parallel trainings on T4 x2. Throughput unknown.
5. **viriformat built-in `Filter` defaults** and the exact meaning of
   "tactical": the crate source was not opened (engine-derived code).
6. **viriformat 2.0.1's behaviour on an extension record** (zero
   occupancy): not opened; assume failure.
7. **The en-passant square convention** in viriformat headers (legal-only
   or after every double push): the README is silent.
8. **That a move's score is the score of the position before that move:**
   strongly implied by the README wording and bullet's filter signature,
   not stated outright.
9. **Kaggle accelerators for a free account,** and whether P100 is gone
   for users or only from Kaggle's test infrastructure (the docs pages
   and the CLI list disagree).
10. **The Kaggle GPU image's CUDA version:** 12.8 inferred from Colab's
    package lists by date, not tied to the image tag.
11. **Whether `-lcuda` links with `CUDA_PATH=/usr/local/cuda` alone** on
    Kaggle (`libcuda` lives in `/usr/local/nvidia/lib64`); whether the
    image ships `lib64/stubs`.
12. **Internet in GPU sessions; phone verification; scratch-disk size;**
    the 20 vs 60 minute idle timeout (docs conflict); max dataset file
    size; mounted read speed (unchanged from 2026-10-24).
13. **Whether a `tar` dataset upload is unpacked** (docs mention ZIP and 7z
    only).
14. **Whether `kaggle datasets version` re-sends unchanged files**
    (unchanged; avoided by the immutable-dataset design).
15. **`kernel_sources`:** latest-version tracking and self-reference.
16. **The exact `kaggle kernels status` values** (an SDK enum, not in the
    docs).
17. **Whether WSL clears `/tmp`,** losing the CLI's upload-resume state.
18. **Fathom under concurrent probing:** documented thread-safe, never
    tested on this machine (carried over from tools.md, item 12).
19. **Lichess:** the number of 2000+ vs 2000+ games in 2016-09; whether
    engine-banned accounts' games were removed; the Bot API start date
    (so early-month engine accounts may be untagged).
20. **GitHub CLI `gh workflow run` syntax** and whether fork pull requests
    receive Actions secrets: not re-checked this pass.
21. **The Kaggle docs pages are rendered by JavaScript.** Plain fetches
    return a shell. They were read through a headless Edge render of the
    official pages; that render crashed after writing output for two of
    the three pages, but the text was complete for the parts quoted.

---

## Sources

Every page opened for this file is listed in [sources.md](sources.md), section "Phase 4 pipeline: bullet, viriformat, Kaggle, Fathom threads, Lichess openings (phase4-pipeline.md), 2026-10-28".
