# bullet internals at the pin: quantization, files, evaluation, features, training API, CUDA

This page answers the questions the Phase 4 step 0 spec (DESIGN.md on main,
§5.3, deliverables 4-6) and the step 3 judge (phase4-designs/judgement.md
§1.4, "unconfirmed bullet features") left open about bullet. It extends
phase4-pipeline.md §1-2 and corrects two points that matter for the parity
test (section 10).

- **What it is:** a reading of bullet's code (jw1912/bullet, MIT) at the
  pinned commit `da426a49b2a4b79a55a87031cd51c89bdf1ff030` (2026-10-26),
  plus bullet's data crate bulletformat 1.8.0 (MIT, same author).
- **Why it matters for Fork:** Phase 4, step 0. Deliverable 4 (Fork's own
  training program in `tools/train/`), deliverable 5 (the converter and
  the C++ feature code), deliverable 6 (the parity test: R-quant must
  reproduce bullet's integers exactly, R-float must read bullet's float
  file, T comes from bullet's own evaluation). Also the bake-off designs
  (steps 1-4), whose unconfirmed bullet features are settled in section 7.
- **Tag:** USE (bullet and bulletformat are MIT tools Fork calls; nothing is
  copied into Fork's repository). **Licence:** MIT (bullet workspace
  `Cargo.toml` and `LICENSE`; bulletformat `Cargo.toml` and `LICENSE`).
  Two crates bullet always pulls in are not MIT (section 9).
- **Date verified:** 2026-10-28, every item unless marked otherwise.
- **How it was checked:**
  - bullet was shallow-cloned at the pin into a temporary folder outside
    both repositories (owner's approval of 2026-10-28 to read bullet's
    code). bulletformat 1.8.0 was downloaded from crates.io; its SHA-256
    (`6d171953…c1b0`) equals the checksum in bullet's `Cargo.lock`. Both
    were deleted after reading.
  - **The viriformat crate's source was not opened** (it carries board
    code from the Viridithas engine). Only its rendered API pages on
    docs.rs (field and method doc comments) were read.
  - No code lines are reproduced here. Paths are bullet's; identifiers are
    bullet's public API names, which Fork's training program has to call.
  - Nothing was built or run. Every behaviour below is read from the code;
    "inferred" marks conclusions drawn from reading rather than seeing.

---

## 0. Key findings (short)

1. **bullet quantizes in f64, not f32.** Each f32 weight is widened to f64,
   multiplied by the integer factor (also widened to f64), then rounded
   half away from zero (`.round()`) or truncated toward zero (default).
   DESIGN.md §5.3 deliverable 6 says R-quant does an "f32 multiply": that
   would disagree with bullet on about 13 weights per million at QA = 255
   and about 650 per million at QA × QB = 16320 (my own sampling, section
   1.4). R-quant must widen to f64 before multiplying.
2. **Overflow aborts the file; nothing is clamped.** A rounded value outside
   the target type's full range (or a NaN) makes `quantised.bin` not
   written at all for that checkpoint; training continues.
3. **Factoriser merges are an f32 addition before quantizing**, done by a
   `SavedFormat::transform` closure the training program writes itself.
   bullet never merges automatically (the `merge_factoriser` helper of
   the `Factorised` input type is never called anywhere in bullet).
4. **`optimiser_state/weights.bin`** is a sequence of named records sorted
   by name: ASCII name, a newline byte, a u64 little-endian element count,
   then that many f32 little-endian values (column-major). Section 2.
5. **`ValueTrainer::eval(fen)` returns the raw network output** of the
   current float weights (no sigmoid, no scaling) from the **side to
   move's** point of view; centipawns = output × eval scale. It needs a
   real GPU. Section 3.
6. **Chess768 index** for perspective P: 384 × [piece colour ≠ P] +
   64 × piece type (pawn 0 … king 5) + square, with the square flipped
   vertically (XOR 56) when P is Black. Confirmed through bulletformat's
   stm-relative `ChessBoard`. Section 4.
7. **The viriformat → training-position conversion lives entirely in the
   viriformat crate** (`Game::splat_to_bulletformat…`). Which position a
   score belongs to is stated in viriformat's docs ("the evaluation of the
   position in which they were played", so the position before the move),
   but the sign handling and filter semantics are not visible in bullet:
   **UNVERIFIED**, settled by Fork's decode test (section 6).
8. **Every graph feature the bake-off designs asked about exists** (section
   7): elementwise product, row slicing and concatenation, CReLU, SCReLU,
   custom output-bucket and sparse-input types, repeated sparse indices
   summed (forward and backward), factorisers, per-tensor clipping, and a
   QAT node (`faux_quantise`). `pairwise_mul` exists but is deprecated in
   favour of slicing the first layer.
9. **A CPU-only build (no GPU feature) links no CUDA library.** The input
   feature code and the viriformat loader are plain CPU code. By reading,
   a mock-device build should also construct a trainer, load a checkpoint
   and write `quantised.bin` on the CPU (inferred, not run); training
   steps and `eval` fail on the mock.
10. **bullet_lib always compiles in sfbinpack (GPL-3.0) and montyformat
    (AGPL-3.0)** besides viriformat (MIT); building a program on
    bullet_lib puts their sources in Cargo's cache (section 9; owner
    decision of 2026-10-28: throwaway `CARGO_HOME` locally, training
    builds on Kaggle only). No Cargo feature removes them, but a program
    built on **`bullet-trainer`** instead of bullet_lib never has them in
    its graph (section 12).
11. **A trainer-only program does more itself** (section 13): the
    trainer crate's `TrainingSchedule` has only steps, an LR closure, a
    log rate and a gradient-norm switch, so S and the WDL weight go into
    Fork's mapper closure, and checkpoint folders, `quantised.bin` and
    FEN evaluation are Fork's code over `write_to_checkpoint`,
    `to_quantised_buffer` and `ModelEvaluator`. Sparse input slots must
    end with −1, because pooled batch buffers are reused without
    clearing.

---

## 1. Quantization, exactly (question 1)

Source: `crates/trainer/src/model/weights.rs` (`SavedFormat`,
`QuantTarget`, `ModelWeights::to_quantised_buffer`),
`crates/bullet_lib/src/value/save.rs`, `docs/4-saved-networks.md`.

### 1.1 One `SavedFormat` entry

- `SavedFormat::id(name)` starts from the named weight's f32 values in
  bullet's storage order (column-major, section 1.3). If the name does not
  exist, the save **panics** (an unwrap on the lookup), which would kill a
  training run at its first checkpoint. Test the save list before a long
  run (section 5.8).
- Each `.transform(closure)` then runs in the order written; the closure
  receives the whole weight store and the current f32 vector and returns a
  new f32 vector. `.transpose()` is a transform that turns the
  column-major rows × cols buffer into row-major order, using the shape of
  the entry's own weight.
- `.quantise::<T>(factor)` and `.round()` only set flags; they are applied
  last, after every transform, wherever they appear in the chain (the doc
  says the same).
- `SavedFormat::custom(bytes)` writes the bytes verbatim; `SavedFormat::empty()`
  starts from an empty vector (for interleaving several tensors through
  transforms).

### 1.2 The per-value rule

For every f32 value `w` of the transformed vector:

| Target | Factor type | Computation |
|---|---|---|
| none (`Float`) | — | the f32 is written as its 4 little-endian bytes, unchanged |
| `i8` | i16 factor | `x = f64(factor) × f64(w)`; then `x.round()` if `.round()` was given, else `x.trunc()`; then cast to i8 |
| `i16` | i16 factor | same, cast to i16 |
| `i32` | i32 factor | same, cast to i32 |

- **The multiply is done in f64.** Both operands are widened first, so for
  factors below 2^29 the product is exact (24-bit mantissa times the
  factor's bits fits in f64's 53 bits). For Fork's factors (255, 64,
  16320) it is always exact.
- **Rounding** is Rust's `f64::round`: nearest integer, halfway cases away
  from zero (Rust standard library docs, primitive `f64`). **Truncation**
  is `f64::trunc`: toward zero.
- **Overflow check:** the rounded f64 is cast with Rust's `as`, which
  saturates out-of-range values to the type's limits and maps NaN to 0
  (Rust Reference, numeric casts). The cast result is then compared with
  the rounded f64; any difference returns an error. So the accepted range
  is the **full range of the type** (i16: −32768 … 32767; i8: −128 … 127),
  and a NaN or infinite weight is also an error.
- **What an error does:** the error propagates out of the whole buffer
  build, so `quantised.bin` is **not created** for that checkpoint (not
  even partially); bullet prints "Failed to write quantised network
  weights" and the error text, and training continues. `raw.bin` and the
  optimiser files are still written.

### 1.3 Layout and order of the file

- **Storage order of a weight:** shape rows × cols, column-major: element
  (r, c) at index c × rows + r. `new_affine(id, in, out)` creates `idw`
  of shape out × in and `idb` of shape out × 1 (out × bias_cols with
  `new_affine_custom`). So without a transpose, the `out` weights of input
  feature c are contiguous: the order an accumulator wants for layer 0.
- **File:** the entries' byte strings concatenated in the order given to
  `save_format`, with no header, names, sizes or separators. Little-endian
  throughout.
- **Padding:** if the total length is not a multiple of 64, bytes are
  appended up to the next multiple of 64, cycling through the six ASCII
  bytes `b u l l e t`. **Corrected 2026-10-28 from a file bullet wrote**
  (main's `tools/train check`, 394,756 bytes of B0 tensors): the cycle
  starts at the first padding byte ("bulletbullet..." right after the last
  tensor byte), not at the start of the 64-byte word. No padding when the
  length is already a multiple of 64.
- **Source of the values:** the quantized file is built from the host copy
  of the weights, refreshed from the device just before (`cpu_weights`).
  `raw.bin` reads the device buffers directly. Both see the same f32s.

### 1.4 Recipe for Fork's R-quant (independent reference)

To reproduce bullet's integers exactly from the f32 values of
`weights.bin`:

1. Apply Fork's own transforms in the same order as the training program's
   `SavedFormat` list (merge, transpose), **in f32** where bullet does them
   in f32 (a factoriser merge is one f32 addition per element; section 1.5).
2. Widen each f32 to f64 and multiply by the factor as an f64. Do **not**
   multiply in f32: in a uniform sample of one million f32 weights in
   [−2, 2] (my own check, Python, 2026-10-28), rounding an f32 product
   disagreed with bullet's f64 path 13 times at factor 255, 651 times at
   16320, and never at 64 (a power of two is exact either way). B0's
   layer 0 has 196,608 weights, so an f32 reference would very likely
   fail the exact leg on a real net.
3. Round half away from zero with an exact method. numpy's `round` is
   half-to-even and is wrong here. A safe way: take the truncated value,
   subtract it to get the fraction (exact in f64), and step one unit away
   from zero when the fraction's magnitude is at least one half.
4. Check the range of the target type; a value outside it means bullet
   would not have written the file.

**Test vectors** (f32-exact weights; my own arithmetic):

| Weight | Factor | Product | bullet `.round()` | half-to-even (wrong) | truncation (bullet default) |
|---|---|---|---|---|---|
| 1.5 | 255 | 382.5 | 383 | 382 | 382 |
| −1.5 | 255 | −382.5 | −383 | −382 | −382 |
| 0.5 | 255 | 127.5 | 128 | 128 | 127 |
| 5/128 = 0.0390625 | 64 | 2.5 | 3 | 2 | 2 |
| −5/128 | 64 | −2.5 | −3 | −2 | −2 |
| 3/128 = 0.0234375 | 16320 | 382.5 | 383 | 382 | 382 |

For factor 255, exact ties only occur at weights of ±0.5 and ±1.5 (an odd
multiple of one half); for 64 and 16320, at odd multiples of 1/128. These
make good mutation inputs for the parity test's "missing rounding step"
case.

### 1.5 Factoriser merges

- **What bullet does:** nothing automatic. A factoriser is either
  (a) a separate weight added inside the graph (the progression example
  `3_input_buckets.rs` creates a weight of shape hidden × 768, tiles it
  across the input buckets with `repeat`, and adds it to the bucketed
  weight), or (b) the `Factorised` input type (section 4.5), which adds
  extra sparse features.
- **Saving merged weights:** the training program writes a
  `SavedFormat::transform` on the bucketed weight that adds the tiled
  factoriser element by element. In Rust that is an **f32 + f32 addition**,
  rounded to f32, done **before** the quantization step (which then widens
  the f32 sum to f64). The in-graph addition on the GPU is also a single
  IEEE f32 addition per element (NVRTC is called without fast-math flags,
  `crates/gpu/src/runtime.rs`), so the float forward pass and the
  quantized file see the same merged values.
- **Tiling order:** the factoriser buffer (hidden × 768, column-major) is
  repeated whole B times, so bucketed column 768·b + f receives factoriser
  column f.
- `Factorised::merge_factoriser` (in `game/inputs/factorised.rs`) is a
  ready-made merge for the `Factorised` input layout, also an f32 sum, but
  it is only used if the training program calls it inside a transform.

---

## 2. The float weights file (question 2)

Source: `crates/trainer/src/model/weights.rs` (`write_into`, `load_from`,
`utils::write_to_byte_buffer`, `utils::read_from_byte_buffer`),
`crates/trainer/src/optimiser.rs`, `optimiser/utils.rs`, `optimiser/adam.rs`.

### 2.1 `optimiser_state/weights.bin`

- **Records, in ascending byte order of the weight name** (the store is a
  sorted map). Every trainable weight is present, factorisers included.
- **One record:**
  1. the name as ASCII bytes (non-ASCII names and names containing a
     newline are rejected when writing);
  2. one byte 0x0A;
  3. the element count as an unsigned 64-bit little-endian integer (Rust
     `usize` on a 64-bit platform; on a 32-bit build it would be 4 bytes);
  4. that many f32 values, little-endian, in the weight's column-major
     order.
- **No shapes, no header, no padding, no trailing data.** A reader loops
  until the end of the file. bullet's own loader looks each record up by
  name, panics on an unknown name or a size mismatch, and accepts files
  that omit some weights (those keep their current values).
- **Names for B0:** `l0w` (256 × 768), `l0b` (256 × 1), `l1w` (1 × 512),
  `l1b` (1 × 1), if the program uses those affine ids. So the file order
  is `l0b`, `l0w`, `l1b`, `l1w` (byte order of the names).

### 2.2 The other checkpoint files

| File | Content |
|---|---|
| `optimiser_state/momentum.bin`, `velocity.bin` (AdamW) | the same record layout, one record per weight, the two AdamW moment buffers |
| `raw.bin` | for each `SavedFormat` entry that has an id, in list order: that weight's f32 values straight from the device, no transform, no transpose, no padding; `custom` and `empty` entries contribute nothing |
| `quantised.bin` | section 1 |
| `log.txt` | one line `superbatch,batch,loss` per logged point **of the current run only** (the record starts empty at each `run` call, so a resumed run's log does not repeat the earlier one) |

Checkpoint directory: `<output_directory>/<net_id>-<superbatch>/`.

### 2.3 Loading

- `ValueTrainer::load_from_checkpoint(dir)` reads `dir/optimiser_state/`
  (weights, then the optimiser's moments) and exits the process on error.
- `trainer.optimiser.load_weights_from_file(path)` loads weights only.
- After loading, the device buffers are overwritten in place, so an
  evaluator created earlier sees the loaded weights (it holds references
  to the same buffers, section 3).

---

## 3. Evaluating a FEN with the float model (question 3)

Source: `crates/bullet_lib/src/value.rs` (`eval_raw_output`, `eval`,
`make_mapper`), `crates/trainer/src/model/evaluator.rs`, bulletformat
`src/chess.rs` (the text parser), `examples/tests/test1.rs`,
`examples/advanced/main.rs`.

- **API:** `ValueTrainer::eval_raw_output(fen) -> Vec<f32>` and
  `ValueTrainer::eval(fen) -> f32`. Both take `&mut self` and the FEN text.
- **What happens:**
  1. bullet appends ` | 0 | 0.0` and parses the line with bulletformat's
     `ChessBoard` text parser. Extra `|` fields are ignored, so passing a
     bare FEN is right (bullet's own test passes a FEN that already ends in
     a score and result, which also works).
  2. The parser reads only the piece placement and the side-to-move field
     (`b` means Black; **anything else means White**). Castling, en
     passant and the clocks are ignored. It does not validate the FEN: an
     unknown character is skipped silently, and more than 32 pieces is an
     error (a panic inside `eval`).
  3. The position is mapped by the trainer's own input type and output
     bucket function (the same mapper as training), so the side to move's
     features go to the `stm` input.
  4. A forward pass with batch size 1 runs on the trainer's device using
     the **current float weights** (the evaluator is built once and keeps
     references to the optimiser's device buffers, so later training or a
     checkpoint load is reflected).
  5. `eval_raw_output` returns the graph's `output` node. `eval` returns
     that single value, or, for a 3-value WDL head, the softmax expected
     score (win + draw / 2).
- **What the number means:** the raw output of the network's last layer,
  from the **side to move's** point of view, **before** any sigmoid (the
  sigmoid is part of the loss in bullet's examples, not of the graph's
  output). Since the target is sigmoid(score / eval_scale), the output
  approximates score / eval_scale: bullet's test and advanced examples
  multiply it by their eval scale to print centipawns. For Fork's T, write
  the raw value (and Fork's S) and convert in the comparison.
- **At the end of a training program:** after `trainer.run(...)` returns,
  loop over the parity EPD's FENs and call `eval` (or `eval_raw_output`)
  for each, writing the results with the run's outputs. Or, in a separate
  short program, build the same trainer, call `load_from_checkpoint`, then
  evaluate. Either needs the GPU backend; on the mock the forward pass
  fails at its first kernel launch.
- **Lower-level route:** `ModelEvaluator` (`bullet_trainer::model`) does the
  same with an explicit `ModelDefinition`, as bullet's advanced example
  shows; not needed for B0.

---

## 4. Input features and buckets (question 4)

Sources: `crates/bullet_lib/src/game/inputs.rs`, `inputs/chess768.rs`,
`inputs/chess_buckets.rs`, `inputs/factorised.rs`, `inputs/adapter.rs`,
`game/outputs.rs`; bulletformat `src/chess.rs` (`ChessBoard`, its iterator,
`from_raw`, the text parser); bullet `docs/3-data.md`.

### 4.1 What the input code sees: bulletformat's `ChessBoard`

A 32-byte record **stored relative to the side to move**:

- When Black is to move, every square is flipped vertically (XOR 56) and
  the colours are swapped; score and result are negated / mirrored to the
  side to move (bulletformat `from_raw` and the text parser both do this;
  bullet's `docs/3-data.md` says the record is stm-relative).
- Pieces: an occupancy bitboard plus one 4-bit code per occupied square in
  ascending square order, low nibble first. Code bits 0-2 are the type
  (0 pawn, 1 knight, 2 bishop, 3 rook, 4 queen, 5 king); bit 3 is set for
  the **opponent's** pieces (relative to the side to move).
- `our_ksq()`: the side to move's king, in the stm-relative frame.
  `opp_ksq()`: the opponent's king **in the opponent's own frame** (the
  stm-relative square flipped again by XOR 56).
- Also a score (i16), a result (0, 1, 2 from the side to move's view) and
  three spare bytes. **No castling rights, en-passant square, clocks or
  move**: input features and bucket functions cannot use them.

### 4.2 `Chess768`

768 inputs, at most 32 active. For each piece the type emits one pair
(stm index, ntm index). In absolute terms, for a perspective P (White or
Black):

- index = 384 × [the piece's colour is not P] + 64 × type + square_P;
- type order pawn, knight, bishop, rook, queen, king (0-5);
- square_P is the square number with a1 = 0, b1 = 1, …, h8 = 63, flipped
  vertically (XOR 56) when P is Black; files are never mirrored.

The side to move's index goes to `stm`, the other side's to `nstm`. (Read
from the code: the stm index is 384·[opponent piece] + 64·type + relative
square; the ntm index swaps the colour half and flips the relative square
by XOR 56. Combined with 4.1 this gives the formula above for both sides
to move.) This matches DESIGN.md's B0 description ("ours" first, Black's
board flipped vertically).

### 4.3 King buckets: `ChessBuckets`

- Built from a 64-entry map square → bucket; the number of buckets is the
  largest entry + 1; inputs = 768 × buckets, at most 32 active.
- The stm features are offset by 768 × map[our king square] and the ntm
  features by 768 × map[opponent king square], each king square in its
  own side's frame (4.1).

### 4.4 Mirrored king buckets: `ChessBucketsMirrored`

- Built from a **32-entry** map: index = rank × 4 + column, where the
  column is the file for files a-d and the mirrored file (h→0 … e→3) for
  e-h. **Any values are allowed** (an arbitrary 32-region layout), and the
  bucket count is the largest entry + 1.
- **Mirroring:** for each perspective separately, if that side's own king
  is on files e-h (in its frame), every one of its feature indices has its
  file flipped (index XOR 7, which only touches the file bits of the
  square). Then the bucket offset of that side's king is added.
- `ChessBucketsMirrored::default()` is a **one-bucket map**: 768 inputs with
  horizontal mirroring and no king buckets (the same as `new` with all 32
  entries 0).

### 4.5 Factorised inputs: `Factorised` and `Factorises`

- `Factorised::from_parts(normal, factoriser)` builds an input type whose
  first `factoriser.num_inputs()` indices are the factoriser's and the rest
  are the normal type's, shifted up by that amount; at most twice as many
  active features. For every normal feature it also emits the derived
  factoriser feature (both perspectives must agree on whether one exists).
- `Chess768` implements `Factorises` for `ChessBuckets` and
  `ChessBucketsMirrored`: the derived feature is the bucketed index modulo
  768 (so, for the mirrored type, the mirrored 768 index).
- Merging for saving: section 1.5.

### 4.6 Output buckets

- `MaterialCount::<N>`: bucket = (number of pieces on the board − 2) ÷
  ceil(32 / N), integer division. So the buckets are equal-width groups of
  ceil(32/N) piece counts starting at 2 pieces (for N = 8: 2-5, 6-9, …,
  30-32 pieces).
- **Custom bucket functions are supported:** implement the `OutputBuckets`
  trait for `ChessBoard` (a constant bucket count and a function from a
  `ChessBoard` to a bucket number; the type must be `Copy + Default +
  Send + Sync`). `output_buckets(...)` asserts more than one bucket. The
  function sees only the `ChessBoard` (4.1).
- In the graph, the last layer has N outputs and `.select(buckets)` picks
  one. Saving the output weights with `.transpose()` makes each bucket's
  weights contiguous (progression examples 2 and 3).

### 4.7 Custom sparse input types

- Implement `SparseInputType` (`game/inputs.rs`): total inputs, maximum
  active, a feature function that calls back once per **pair** (stm
  index, ntm index), a short name and a description; optional
  factoriser hooks. The data type is `ChessBoard` for every chess loader
  Fork would use.
- The mapper asserts that every index is below the input count and that
  no more than the maximum are emitted, and ends a shorter list with −1.
- Features whose counts differ between the two perspectives cannot go
  through the paired callback; bullet's advanced example instead uses the
  lower-level API (`ModelInputs`, `ModelInputsMapper::build`,
  `ModelDefinition::build`, `Optimiser`, `train`) with separate sparse
  inputs per perspective. That API lives in the `bullet_trainer` crate,
  which `bullet_lib` does not re-export: Fork's `Cargo.toml` would add a
  second git dependency (`package = "bullet-trainer"`, same `rev`).

---

## 5. A training program for B0 (question 5)

Sources: `value/builder.rs`, `value.rs`, `trainer/schedule.rs`,
`schedule/lr.rs`, `schedule/wdl.rs`, `trainer/settings.rs`,
`crates/trainer/src/run.rs`, `run/schedule.rs`, `run/dataloader.rs`,
`reader.rs`, `optimiser/adam.rs`, `compiler/src/model/builder.rs`,
`value/loader/viribinpack.rs`, `examples/simple.rs`. Prose only; Fork
writes its own program.

### 5.1 The minimal set of calls

1. `ValueTrainerBuilder::default()`, then:
   - `.dual_perspective()`;
   - `.optimiser(AdamW)` (the marker type from `bullet_lib::nn::optimiser`);
   - `.inputs(Chess768)`;
   - `.save_format(&[...])` with four entries, for example: `l0w` rounded,
     i16, factor 255; `l0b` rounded, i16, 255; `l1w` rounded, i16, 64;
     `l1b` rounded, **i32**, factor 255 × 64 (DESIGN.md's int32 output
     bias; an i16 bias with factor 16320 would also fit, since 1.98 ×
     16320 ≈ 32314). Optionally a `SavedFormat::custom` header first;
   - `.loss_fn(...)` with the sigmoid of the output against the target
     (bullet's examples use squared error; `power_error` also exists);
   - `.build(...)` with a closure that creates `new_affine("l0", 768, 256)`
     and `new_affine("l1", 512, 1)`, applies `l0` to each perspective's
     input, then **`.crelu()`** (B0's clipped ReLU; bullet's examples use
     `.screlu()`), concatenates stm first, and applies `l1`.
   - Optional: `.seed(u64)` (weight initialisation seed; default
     198273612), `.use_device(ordinal)`.
2. Optional per-weight clipping: `trainer.optimiser.set_params_for_weight(name, AdamWParams { … })`.
3. A `TrainingSchedule` (5.3) and `LocalSettings` (5.5).
4. A loader (5.2), then `trainer.run(&schedule, &settings, &loader)`.
5. Then the parity evaluations (section 3).

### 5.2 The viriformat loader and its filter

- `ViriBinpackLoader::new(path, buffer_size_mb, threads, filter)`;
  `new_concat_multiple(paths, …)` reads files in order and loops forever;
  `new_interleave_multiple(paths, …)` first counts every file's games with
  a full read, then repeatedly draws a file weighted by its remaining games
  and reads 16 consecutive games from it.
- `threads` here are the game-decoding workers (at least 1). Capacity of
  the shuffle buffer: buffer_size_mb × 2^20 ÷ 32 ÷ 2 positions. The buffer
  is shuffled (Fisher-Yates) with an RNG seeded from the clock in
  microseconds, at every refill.
- **The resume skip count is ignored** (the reader's skip argument is
  unused), as phase4-pipeline.md §1.4 says.
- **Concat mode stops reading a file silently at the first game it cannot
  decode** and moves on to the next file; interleave mode panics instead.
  So a corrupt shard silently shrinks the data in concat mode: check shard
  hashes before training (deliverable 3 already does).
- **Filter:** `ViriFilter::Builtin(Filter)` passes viriformat's own
  `Filter` to viriformat's conversion; `ViriFilter::Custom(f)` takes a
  function of (board before the move, move, score as i16, result as 1.0 /
  0.5 / 0.0) that returns **true to keep** (bullet negates it for
  viriformat's skip callback).
- **The built-in `Filter`** (viriformat 2.0.1, docs.rs field docs): drop
  positions with ply below `min_ply`; with fewer than `min_pieces`
  pieces; with absolute evaluation above `max_eval`; where "a tactical
  move was made" (`filter_tactical`); in check (`filter_check`); where "a
  castling move was made" (`filter_castling`); where the eval "diverges
  from WDL by more than" `max_eval_incorrectness`; random skipping
  (`random_fen_skipping`, `random_fen_skip_probability`); and a WDL-model
  skip (`wdl_filtered` with its model parameters). It implements
  `Default` and serde (missing TOML fields take the default), and
  `Filter::UNRESTRICTED` drops nothing.
  - **UNVERIFIED:** the default values and the exact meaning of
    "tactical" (both live in viriformat's source, not opened). bullet's
    `simple.rs` uses `Filter::default()`; bullet's advanced example sets
    every field explicitly with its own values, so it is no evidence for
    the defaults.
  - Recommendation (unchanged from phase4-pipeline.md): Fork's program
    spells out every field, or uses a custom keep-function written by
    Fork (which then also defines "tactical" itself), and checks the kept
    count on a fixture game.

### 5.3 `TrainingSchedule`: no library defaults

Every field must be set; bullet has no default schedule.

- `net_id`: names the checkpoint folders.
- `eval_scale` (f32): the target uses sigmoid(score / eval_scale), with
  1 / eval_scale computed in f32. **This is Fork's S**: the scale fitted
  on generation-0 data must be passed here, and Fork's inference uses the
  same number.
- `steps: TrainingSteps { batch_size, batches_per_superbatch, start_superbatch, end_superbatch }`:
  superbatches are numbered from 1 and the end is inclusive; a batch is
  `batch_size` positions; the run rejects batch size 0, start 0, start
  after end, and overflow of end × batches × batch size.
- `wdl_scheduler`: **the weight on the game result**. The target is
  w × result + (1 − w) × sigmoid(score / eval_scale), and w must lie in
  [0, 1] (asserted). `ConstantWDL { value }`, `LinearWDL { start, end }`,
  `Warmup`, `Sequence`. DESIGN.md's λ is "the weight on the score"; at
  0.5 the two agree, but **when λ is tuned, pass 1 − λ to bullet**.
  `wdl_adjust_function` can change w per position.
- `lr_scheduler`: `ConstantLR`, `DropLR` (one drop after a superbatch),
  `StepLR` (multiply by gamma every `step` superbatches), `LinearDecayLR`,
  `CosineDecayLR`, `ExponentialDecayLR` (from superbatch 1 to
  `final_superbatch`), `Warmup` (first superbatch, batch-wise), `Sequence`.
  Every scheduler is a pure function of (batch within superbatch,
  superbatch), so a resumed run with the same schedule continues exactly.
- `save_rate`: checkpoint at every superbatch that is a multiple of it and
  at the final one.
- **bullet's `simple.rs` example** (not a library default; if Fork adopts
  any of it, the constants table records it as "bullet's example
  value"): batch 16,384; 6,104 batches per superbatch; superbatches 1-40;
  eval scale 400; constant WDL weight 0.75; StepLR from 0.001, gamma 0.1
  every 18 superbatches; save every 10; 4 threads.

### 5.4 Optimiser: the real defaults

- `AdamWParams::default()`: decay 0.01, beta1 0.9, beta2 0.999, weights
  clipped to [−1.98, 1.98]. `ValueTrainerBuilder` always starts from these.
- Update per weight, per batch: decoupled decay (weight × (1 − decay × lr)),
  then Adam moments, step = momentum ÷ (√velocity + 1e-8), no bias
  correction and no step counter, then the clip. The clip applies only
  after updates (initial weights are not clipped).
- Gradients are averaged over the batch (a factor 1 / batch_size); the
  printed loss is the batch's summed loss ÷ batch size.
- Initialisation: affine weights normal with mean 0 and standard
  deviation √(2 / fan-in); biases zero; seeded (Xoroshiro128+), so the
  initial weights are reproducible, the data order is not.
- `RAdam` and `Ranger` also exist; `WeightClipping` and `WeightDecay`
  wrappers in `bullet_trainer::optimiser`.

### 5.5 `LocalSettings`

- `threads`: the batch-mapping threads (clamped to 1-255), on top of the
  loader's own decoding threads and bullet's helper threads.
- `output_directory`: where checkpoint folders go.
- `test_set`: prints a warning that validation is "not currently
  implemented".
- `batch_queue_size`: **unused at this pin** (the run loop's queue is a
  fixed 32 batches).

On a Kaggle session with 4 cores, decoding threads + mapping threads + the
main thread already exceed the core count; K17 measures the right split.

### 5.6 Superbatch and batch semantics in the run loop

- One step = one batch. The loss and learning rate are evaluated per
  batch; logging every 32 batches and at a superbatch's last batch; the
  superbatch callback (checkpointing) after its last batch.
- The data loader runs in its own thread with its own step counter
  starting at `start_superbatch`, so the WDL weight used for a batch's
  targets follows the same schedule.
- The run ends with an error if the loader stops before the scheduled end
  (the viriformat loader loops forever, so it never does).

### 5.7 Checkpoints and resume

As in phase4-pipeline.md §1.4, now confirmed in the code: resume =
`load_from_checkpoint(dir)` + `start_superbatch` = saved superbatch + 1,
everything else unchanged. The LR and WDL schedules continue exactly; the
data stream does not (clock-seeded shuffles, skip count ignored).

### 5.8 Checks worth running before Kaggle

- Build the program without a GPU feature and call `save_quantised` (or
  `save_to_checkpoint`) right after `build`: a wrong id panics there, and
  the byte count of the file (B0: 2 × (768 × 256 + 256) + 2 × 512 + 4 =
  394,756 bytes with an i32 output bias, padded to 394,816) can be checked
  against Fork's converter (my arithmetic). Whether this works on the mock device is
  inferred from the code (section 8), not run.
- A custom keep-all filter over a fixture game, counting positions
  (section 6).

---

## 6. Score and target semantics in the viriformat path (question 6)

What bullet's own code shows (`value/loader/viribinpack.rs`, `value.rs`):

- The loader hands each raw game to viriformat
  (`Game::splat_to_bulletformat` with the built-in filter, or
  `Game::splat_to_bulletformat_with_filter_callback` with a custom one)
  and collects the `ChessBoard` records it produces. **The conversion from
  a stored (move, score) pair and the game result to a `ChessBoard` is
  inside viriformat; bullet does not touch the score or result itself.**
- The target is built from the `ChessBoard`'s score and result (`make_mapper`):
  score through sigmoid(score / eval_scale), result as 0, 0.5 or 1, blended.
  Both are used as the **side to move's** values, consistent with the stm
  features going first. bulletformat's two `ChessBoard` constructors
  (`from_raw` and the text parser) take a **White-relative** score and
  result and flip them when Black is to move.
- The custom filter callback receives the score as a 32-bit integer from
  viriformat, which bullet narrows to i16, and the result as a WDL enum.

From viriformat's rendered docs (docs.rs, 2.0.1; source not opened):

- `Game.moves` holds "the moves played in the self-play game, along with
  the evaluation of the position in which they were played": **a score
  belongs to the position before its move.**
- `Game::MAX_SPLATTABLE_GAME_SIZE` is 512. What happens to a longer game is
  not documented. bullet unwraps the conversion's result, so if a longer
  game returns an error, a loader worker thread panics.

**UNVERIFIED (lives only in viriformat's source):**

- whether viriformat passes the stored White-relative score and result to
  `from_raw` unchanged (so that the record ends up stm-relative), or
  converts them itself;
- whether each emitted record is the position before its move (the docs
  suggest so) and whether the final position after the last move is
  emitted;
- the perspective of the score and WDL given to the filter callback;
- how the en-passant square in the header is used while replaying (the
  `ChessBoard` has no en-passant field, so it cannot reach the network);
- the behaviour on games longer than 512 moves.

All of these are settled by DESIGN.md's planned decode test: run bullet's
`ViriBinpackLoader` on the CPU over a Fork shard (with a custom keep-all
filter) and compare every record with python-chess's replay, including a
game longer than 512 plies. Calling the loader directly needs the
`DataReader` trait from `bullet_trainer` (section 4.7); no device is
involved at all.

---

## 7. Graph features for the bake-off designs (question 7)

Sources: `crates/compiler/src/model/builder.rs`, `model/operations/pointwise.rs`,
`model/operations/index.rs`, `model/operations/linear.rs`,
`tensor/operation/autograd/qat.rs`, `tensor/operation/linear/sparse.rs`,
`crates/gpu/src/pointwise/write.rs`, `examples/advanced/main.rs`,
`examples/progression/3_input_buckets.rs`; GitHub API for PR #483.

| Feature | At the pin | Notes |
|---|---|---|
| Elementwise product | yes: `node * node` | same-size nodes; the only automatic broadcast is an **unbatched** 1×1 scalar |
| Pairwise multiplication of accumulator halves | yes | `pairwise_mul` exists but is **deprecated** ("apply the slicing to the FT"); the recommended form is `Affine::slice(start, end)` on the first layer, activate each half, multiply (bullet's advanced example does exactly this) |
| Slicing | `slice_rows(start, end)` on a node; `Affine::slice` on a layer (not materialised, faster) | |
| Concatenation | `concat` of two column vectors (cols = 1, same batching); chain for more | |
| CReLU / SCReLU | `crelu` = clamp to [0, 1]; `screlu` = that value squared; also `relu`, `sqrrelu`, `sigmoid`, `abs`, `abs_pow`, `exp` | |
| Custom output buckets | yes, `OutputBuckets` trait (section 4.6) | sees only the `ChessBoard` |
| Layer stacks across several layers | yes: `select(buckets)` after each layer | the advanced example selects after three layers (not run here) |
| Custom sparse input type | yes, `SparseInputType` (section 4.7) | `ChessBoard` only: no castling, en passant or clocks |
| Repeated sparse indices | **summed**: the forward kernel adds a weight column once per occurrence, and the backward kernel adds the gradient once per occurrence (atomic adds) | an index list ends at the first negative or out-of-range index |
| Factorisers | yes, in-graph weight + `repeat`, or the `Factorised` input type | merge for saving: section 1.5 |
| Per-tensor clipping | `optimiser.set_params_for_weight(name, AdamWParams { min_weight, max_weight, … })` | applied inside the AdamW update, after each step |
| QAT | `faux_quantise(factor, round)`: forward is round-or-truncate(factor × x) ÷ factor in f32 on the GPU (CUDA `roundf`, halfway away from zero per NVIDIA's math API docs, or `truncf`); backward passes the gradient through unchanged | PR #483 ("Add QAT operation", merged 2025-10-20) touched crates that no longer exist at the pin; the pin's version lives in `autograd/qat.rs`. Also `clip_pass_through_grad(min, max)` |
| Activation-sparsity penalty | no built-in op; expressible by adding a scaled `reduce_sum_rows` of the activations to the loss | the advanced example does this; in the `ValueTrainerBuilder` path use `build_custom`, which returns (output, loss) |
| Add, subtract, scale by a constant | yes (`+`, `-`, f32 × node, node ÷ f32) | |
| Gate: a 1-wide node multiplying a wide node | needs an explicit `broadcast_across_rows(H)` on the gate, because the automatic broadcast covers unbatched scalars only | whether that compiles for batched nodes: **UNVERIFIED** (not run) |
| Several sparse inputs | yes, in the lower-level API (section 4.7) | |
| Weight dtypes | f32 for training; the pin's newest commit adds "basic support" for f16/bf16 | not needed for step 0 |

**judgement.md §1.4 rows, settled:**

| Design | Unconfirmed feature | Status |
|---|---|---|
| S | one-bucket map in the mirrored bucketed input | **exists**: `ChessBucketsMirrored::default()` |
| S | 33-entry custom piece-count bucket map | **exists**: a custom `OutputBuckets` type. `MaterialCount` is equal-width groups of ceil(32/N) counts from 2 pieces (4.6) |
| AF, H | arbitrary 32-square region map, mirrored and factorised | **exists**: `ChessBucketsMirrored::new` takes any 32-entry map; factorise with `Factorised` or an in-graph weight |
| AF, H | custom output-bucket / stack function | **exists** (`OutputBuckets`) |
| AF | pairwise product node | **exists** (deprecated `pairwise_mul`; slice + multiply preferred) |
| AF | layer stacks across three layers | **exists** (`select` after each layer; bullet's advanced example) |
| AF | QAT operation | **exists** (`faux_quantise`) |
| AF | activation-sparsity penalty | **expressible** (loss term), no built-in |
| AF-LT | custom threat input type; repeated indices summed | **both exist** |
| XGR | custom input type via the sparse-input trait | **exists**, limited to `ChessBoard` information |
| XGR | add, subtract, scale, slice, product of 1-wide nodes, crelu on a 1-wide node | **exist**; gate broadcast needs `broadcast_across_rows` (compiling it UNVERIFIED) |
| all | `.round()` tie rule; factoriser merge in f32 | **settled**: half away from zero, product in f64; merge is an f32 addition before quantizing |

---

## 8. CUDA requirements and a CPU-only build (question 8)

Sources: `crates/gpu/build.rs`, `crates/gpu/src/runtime.rs`,
`runtime/cuda.rs`, `runtime/mock.rs`, `crates/bullet_lib/src/lib.rs`,
`crates/trainer/src/run.rs`, bullet `docs/2-getting-started.md`; NVIDIA
driver-API archive pages (12.3.0, 12.4.0) and the CUDA Compatibility guide.

- **Linked libraries (feature `cuda`):** `cuda` (driver), `cudart`,
  `nvrtc`, `cublas`, dynamically, from `$CUDA_PATH/lib64` on Linux
  (`lib/x64` and `lib` on Windows), plus `/usr/lib/wsl/lib/` when that
  folder exists. `CUDA_PATH` must be set and exist. No runtime-API
  (`cuda…`) function is actually bound in the code; the runtime library is
  linked anyway.
- **nvcc is not needed.** Kernels are generated as CUDA C source at run
  time, compiled by NVRTC to **PTX** with `--gpu-architecture=sm_XY` for
  the detected device (no other options, so no fast-math), and loaded with
  `cuModuleLoadData`. The generated source has no `#include`, so NVRTC
  needs no header path.
- **Minimum versions (inferred, UNVERIFIED until K3/K4):**
  - **driver API ≥ 12.4:** the code binds `cuFuncLoad` (and the stream
    allocator `cuMemAllocAsync`); NVIDIA's driver-API "Execution Control"
    page lists `cuFuncLoad` in the 12.4.0 archive and not in 12.3.0
    (rechecked 2026-10-28). So both the toolkit used to link and the
    installed driver must be 12.4 or newer;
  - **driver at least as new as the NVRTC used:** NVIDIA's compatibility
    guide says applications that compile device code to PTX "will not work
    on older drivers". So a toolkit newer than the driver fails at the
    first kernel load even within one major version;
  - other driver calls (`cuDevicePrimaryCtxRetain`, `cuLaunchKernel`, …)
    and the cuBLAS calls (`cublasSgemm_v2`, `cublasSgemmStridedBatched`) are
    much older.
- **GPU architecture:** whatever NVRTC of the installed toolkit accepts
  for the device's compute capability (phase4-pipeline.md §1.2 covers the
  T4 and P100 under CUDA 12 and 13).
- **CPU-only build (no GPU feature):**
  - the execution context is `MockGpu`; no CUDA library is linked (the
    build script links only under the feature). bullet's CI builds and
    tests the workspace this way;
  - **input feature code** (`Chess768`, the bucket types, a custom
    `SparseInputType`, `OutputBuckets`) is plain Rust on `ChessBoard` and
    runs anywhere: usable as a third party in Fork's feature leg;
  - **the viriformat loader** (`read_chunks`) is plain CPU code (threads and
    file I/O) and needs no device; `measure_max_cpu_throughput` runs the
    loader and the batch mapper on a mock device;
  - **the mock device** allocates real host memory, copies to and from it,
    and accepts kernel "compilation" and module loading as no-ops; only
    kernel launches and matrix multiplies return its error. So, by
    reading, `ValueTrainerBuilder::build`, `load_from_checkpoint`,
    `save_quantised` and `save_to_checkpoint` should all work on the CPU,
    which would let Fork run bullet's own quantizer locally on a downloaded
    checkpoint. **Inferred, not run** (UNVERIFIED);
  - training steps and `eval` cannot run on the mock.

---

## 9. Originality and licence notes

- **Crates bullet always compiles** (`crates/bullet_lib/Cargo.toml`: plain
  dependencies, not optional): bulletformat 1.8.0 (MIT), viriformat 2.0.1
  (MIT; crates.io description "the data-representation used by the
  viridithas chess engine"), **sfbinpack 0.6.4 (GPL-3.0; "Library to read
  Stockfish Binpacks", repository Disservin/binpack-rust)** and
  **montyformat 0.9.2 (AGPL-3.0; "Chess implementation & compressed data
  formats for Monty", repository official-monty/Monty)** (crates.io API,
  2026-10-28). Consequences:
  - any `cargo build` of Fork's training program downloads and unpacks the
    sources of all three into Cargo's cache (`$CARGO_HOME/registry/src`).
    The owner's rule 9 (no engine source left on this machine) is about
    clones and copies; a local build (for the CPU tests of section 8)
    would leave chess-engine-derived crate sources in the local cache.
    **Owner decision needed:** build only on Kaggle and in a disposable
    `CARGO_HOME` (deleted after the run) when building locally, or accept
    the cache. Fork's code must never call montyformat's or sfbinpack's
    chess functions (bullet's advanced example uses montyformat's attack
    tables);
  - the training binary links AGPL and GPL code. Fork distributes neither
    the binary nor those crates (only its own source in `tools/train/`), so
    nothing changes for Fork's GPL-3.0-or-later engine; recorded so the
    licence picture is complete.
- **bullet's advanced example** (`examples/advanced/main.rs`, `inputs.rs`)
  is one specific engine's training setup (its net name refers to another
  engine) and contains a complete threat-feature and pawn-pair input
  design. It was read for the API pattern only (multiple sparse inputs,
  slice-and-multiply, stacked `select`, a loss penalty, the low-level
  training API). **Fork's threat-input designers (AF-LT and any later
  threat work) should not read those two files**, so Fork's feature design
  stays independent; nothing of its feature layout is recorded here.
- QA = 255 and QB = 64 appear in bullet's examples; DESIGN.md already
  credits them to bullet as a trainer-interface convention (owner,
  2026-10-28).

---

## 10. Consequences for DESIGN.md §5.3 (to apply on main)

1. **Deliverable 6, R-quant:** replace "f32 multiply, then bullet's
   rounding rule" by "widen to f64, multiply by the factor in f64, round
   half away from zero (exact method), range-check the target type"
   (section 1.4). Add the tie vectors of 1.4 to the tests.
2. **λ:** bullet's WDL value is the weight on the **result**; pass 1 − λ
   when λ (the score weight) is not 0.5 (section 5.3).
3. **S = `eval_scale`:** the fitted S is the training schedule's eval
   scale, and T's raw outputs are in units of score / S (section 3).
4. **Output bias as i32** needs `quantise::<i32>(255 × 64)` in the save
   list; the B0 file is then 394,756 bytes plus 60 bytes of padding
   (section 5.8).
5. **The decode test** (deliverable 2) needs `bullet-trainer` as a second
   pinned git dependency for the `DataReader` trait, and should include a
   game longer than 512 plies (section 6).
6. **Cargo cache and licences:** the owner decision of section 9
   (2026-10-28), and the choice of section 12: depend on `bullet-trainer`
   (no GPL/AGPL crate in the graph) or on `bullet_lib` (both always
   downloaded).
7. `LocalSettings.batch_queue_size` does nothing at the pin; the run
   record should not present it as a setting that matters.

---

## 11. UNVERIFIED items

| Item | Why |
|---|---|
| viriformat's score/result conversion into `ChessBoard` (sign handling) | in viriformat's source, not opened; Fork's decode test settles it |
| Whether each record is the position before its move, and whether the final position is emitted | viriformat's docs imply "before"; the code is in viriformat |
| Perspective of the score and WDL passed to a custom filter | in viriformat |
| Use of the header's en-passant square during replay | in viriformat |
| Behaviour on games longer than `MAX_SPLATTABLE_GAME_SIZE` (512) | not documented; test with a long game |
| Built-in `Filter` defaults and the definition of "tactical" | in viriformat's source |
| Minimum CUDA: driver and link toolkit ≥ 12.4, driver ≥ NVRTC version | inferred from the bound symbols and NVIDIA's docs; K3/K4 confirm |
| `build`, `load_from_checkpoint` and `save_quantised` working on the mock device | read from the mock's code, not run |
| Batched broadcast of a 1-wide gate (`broadcast_across_rows`) compiling | not run |
| Layer stacks with `select` after three layers training correctly | read in bullet's example, not run |
| Whether the pin's `faux_quantise` matches PR #483's original operation | only the PR's metadata and file list were read; its files were restructured since |
| Depending on `bullet-trainer` by git puts no sfbinpack or montyformat entry in Fork's `Cargo.lock` (section 12) | inferred from bullet's lock graph and Cargo's docs; not run. Check: `cargo generate-lockfile` in `tools/train` in a throwaway `CARGO_HOME`, then search the lock |
| Whether Cargo still downloads the original `.crate` when a `[patch.crates-io]` stub has the same version (section 12.4, option 3) | Cargo's docs say the original crate is "replaced" but not that it is never downloaded; not run |
| A dependency's examples (bullet_lib's `simple`, `advanced`) are not compiled when Fork builds against it (section 12.3) | not stated on Cargo's targets page; general Cargo behaviour, not checked here |
| A trainer-only Fork program compiling against `bullet-trainer` from outside bullet's workspace (section 12) | read only; bullet's README names its advanced example as a direct `bullet-trainer` user, but that example sits inside bullet's own workspace |
| Section 13's own items (mock behaviour, evaluator inputs, inferred types, extra git lines, filter return meaning) | listed in 13.9 |

---

## 12. Excluding the GPL/AGPL dependencies

- **What it is:** the answer to the owner's question of 2026-10-28: can a
  Cargo feature or another supported dependency setting keep sfbinpack
  (GPL-3.0) and montyformat (AGPL-3.0) out of Fork's training build, so
  they are never downloaded?
- **Why it matters for Fork:** Phase 4, step 0, deliverable 4 (Fork's
  training program in `tools/train/`) and the parity test (deliverable 6);
  also the owner's rule that no engine source stays on this machine. The
  owner has already decided (2026-10-28): local builds use a throwaway
  `CARGO_HOME` deleted after each run, training builds run only on Kaggle,
  and Fork never vendors or links those two crates. This section looks for
  a way to avoid even the download.
- **Source:** a fresh shallow clone of github.com/jw1912/bullet at
  `da426a49b2a4b79a55a87031cd51c89bdf1ff030` (MIT), in a temporary folder
  outside both repositories, deleted after reading. Read: the workspace
  `Cargo.toml`, all five member `Cargo.toml` files, `Cargo.lock`,
  `README.md`, `docs/2-getting-started.md`, `docs/3-data.md`, the import
  and module lines of the bullet_lib files named in 12.3, the public item
  list of the trainer crate, and `examples/ataxx.rs`. Cargo's own
  documentation for the rules (sources.md). No crate source of sfbinpack,
  montyformat or viriformat was opened or downloaded; nothing was built;
  no cargo command was run.
- **Tag:** USE for the recommended route (bullet-trainer, MIT).
  sfbinpack and montyformat stay **OFF-LIMITS** to Fork's code (owner,
  2026-10-28). **Licences:** bullet MIT; sfbinpack GPL-3.0; montyformat
  AGPL-3.0 (crates.io metadata, section 9).
- **Date verified:** 2026-10-28.

### 12.1 Short answer

**No through features; yes through a different bullet crate.**

- At the pin, `crates/bullet_lib/Cargo.toml` lists sfbinpack 0.6.4 and
  montyformat 0.9.2 as plain dependencies (no `optional = true`), and its
  `[features]` table has only `cuda`, `rocm` and `metal`, each of which
  just forwards the same-named feature to bullet-gpu and bullet-trainer.
  There is no `default` feature. So `default-features = false` changes
  nothing, and no feature choice removes the two crates: any build that
  depends on `bullet_lib` needs their sources and so downloads them.
- **bullet-trainer (`crates/trainer`) does not depend on them at all.**
  Its manifest lists only bullet-compiler, bullet-gpu, rand_xoshiro
  (pinned `=0.8.1`) and rand_distr (pinned `=0.6.0`). I walked the lock
  file's graph from `bullet-trainer` (my own script over `Cargo.lock`):
  63 packages, none of them sfbinpack, montyformat, viriformat or
  bulletformat. Because a lock file is built as if every feature of the
  workspace members were on, that set is an upper bound for what a
  trainer-only build can pull in (at the lock's versions).
- viriformat 2.0.1's own graph in the same lock (33 packages) and
  bulletformat 1.8.0 (no dependencies) contain neither GPL/AGPL crate.
- So **a training program that depends on `bullet-trainer` (plus
  viriformat and bulletformat directly) never has sfbinpack or montyformat
  in its graph**, and Cargo has no reason to download them (to be
  confirmed by the check in 12.5). bullet's README presents this as a
  supported way to use bullet: its "advanced" example, which it calls
  state of the art, uses `bullet-trainer` directly instead of
  `ValueTrainerBuilder`. bullet's `examples/ataxx.rs` (an example of the
  trainer crate, not of bullet_lib) is a complete training program on the
  trainer crate alone (custom data reader, input mapper, model
  definition, AdamW, `train`).

### 12.2 Who depends on what (at the pin)

| Crate (path) | sfbinpack | montyformat | viriformat | bulletformat | Features |
|---|---|---|---|---|---|
| bullet_lib (`crates/bullet_lib`) | yes, unconditional | yes, unconditional | yes | yes | `cuda`, `rocm`, `metal` (forwarders only); no `default` |
| bullet-trainer (`crates/trainer`) | no | no | no | no | `cuda`, `rocm`, `metal` (forward to bullet-gpu); no `default` |
| bullet-gpu (`crates/gpu`) | no | no | no | no | `cuda` and `rocm` are empty; `metal` turns on four optional macOS-only objc2 crates |
| bullet-compiler (`crates/compiler`) | no | no | no | no | none (depends on `half` only) |
| bullet-utils (`crates/utils`, the data-tool binary) | no | yes, unconditional | yes | yes | none |

- Workspace: virtual workspace, `resolver = "2"`, edition 2024,
  rust-version 1.87, lock file version 4. When bullet is a dependency,
  neither its resolver setting nor its `Cargo.lock` applies: Cargo uses
  only the top-level workspace's resolver, and a package's lock file does
  not affect the packages that depend on it (Cargo resolver page and FAQ).
  Fork's `tools/train` gets its own lock, generated from its own
  manifest, so transitive versions can differ from bullet's tested lock
  (only bullet-trainer's two `=` pins are enforced). Fork should commit
  its own `tools/train/Cargo.lock` and build with `--locked`.
- `bullet-utils` (its shuffle and interleave commands,
  `docs/2-getting-started.md`) pulls montyformat. Fork's tools should not
  build it, or only in a throwaway `CARGO_HOME`.
- Cargo rules that do not help here: for lock generation the resolver
  enables every feature of the workspace's own members, and `cargo fetch`
  downloads every git and registry dependency in the lock (for all
  targets unless `--target` is given; its page says nothing about
  features). Optional dependencies of Fork's own crate would therefore
  still be locked and fetched. None of this matters for the recommended
  route, because the two crates are never in the graph.

### 12.3 Where bullet_lib uses the two crates (paths only)

- `crates/bullet_lib/src/game.rs`: the public `formats` module re-exports
  all four data crates (bulletformat, montyformat, sfbinpack, viriformat).
- `crates/bullet_lib/src/value/loader.rs`: declares the `sfbinpack` (public)
  and `montybinpack` (private) loader modules and re-exports
  `SfBinpackLoader` and `MontyBinpackLoader`.
- `crates/bullet_lib/src/value/loader/sfbinpack.rs` (224 lines): the
  Stockfish-binpack loader; it imports about ten items from sfbinpack and
  re-exports several of them as part of bullet_lib's public API.
- `crates/bullet_lib/src/value/loader/montybinpack.rs` (186 lines): the
  Monty-binpack loader; it imports about five items from montyformat.
- Outside bullet_lib: `crates/utils/src/montybinpack/{count,head,interleave}.rs`
  (bullet-utils), `examples/simple.rs` (uses the sfbinpack loader) and
  `examples/advanced/inputs.rs` (uses montyformat). These examples should
  not be compiled when Fork builds against bullet_lib, since a dependency
  is used through its library target (**UNVERIFIED**: Cargo's targets page
  does not say which targets of a dependency are built). For option 2
  below, removing the `simple` example's sfbinpack lines too keeps the
  copy buildable on its own.
- Nothing else in bullet_lib refers to the two loaders or crates. The
  viriformat loader (`value/loader/viribinpack.rs`), the input types, the
  value trainer and its `eval` do not depend on them.

### 12.4 The options, in order of preference

1. **Depend on `bullet-trainer` instead of `bullet_lib` (recommended).**
   Nothing GPL or AGPL in the graph; no patching; supported by bullet.
   What bullet-trainer already provides, read at the pin: `ModelInputs`
   and `ModelInputsMapper` (sparse and dense inputs, the mapping closure),
   `ModelDefinition` and the graph builder (the graph operations of
   section 7, re-exported from bullet-compiler), `ModelWeights`,
   `SavedFormat` and `QuantTarget` (**the quantisation code of section 1
   lives in this crate**, so R-quant's reference is unchanged),
   `ModelEvaluator`, the `DataReader` trait and `ReadMapLoader`, AdamW and
   the other optimisers, `Optimiser::write_to_checkpoint` and
   `load_from_checkpoint`, `TrainingSchedule`, `TrainingSteps` and
   `train`. What Fork then writes itself in `tools/train` (Fork's own
   code, which deliverable 4 asks for anyway):
   - a `DataReader` over viriformat files that calls viriformat's own
     conversion to bulletformat `ChessBoard` values (the same conversion
     bullet_lib's loader calls, section 5.2), with Fork's filter;
   - the Chess768 index mapping in the mapper closure (section 4.2) and
     the target (sigmoid(score / S) blended with the result, section 5.3
     and the λ note of section 10);
   - the learning-rate schedule, the save list and the per-superbatch
     checkpoint call that `ValueTrainer` otherwise handles.
   **Cost to the parity test:** T would come from bullet's
   `ModelEvaluator` (bullet's forward pass) but through Fork's own Rust
   feature mapping, so T no longer cross-checks Fork's feature indexing
   against bullet's `Chess768`: Fork's C++ features and Fork's Rust mapper
   could share one mistake. Mitigation: a test in `tools/train` that
   checks the Rust mapper on fixture positions against index values worked
   out by hand from section 4.2 (and bulletformat's stm-relative board),
   kept independent of the C++ code.
2. **A Fork-owned copy of bullet with the two loaders removed** (keeps
   `ValueTrainerBuilder`, `Chess768`, the viriformat loader and `eval`).
   The change is small: drop the two dependency lines from
   `crates/bullet_lib/Cargo.toml`, the two re-exports in `game.rs`, the two
   module lines and two re-exports in `value/loader.rs`, and the two loader
   files. Fork would point at it either directly (a git dependency on a
   fork of bullet at a fixed commit) or through a
   `[patch."https://github.com/jw1912/bullet"]` entry in `tools/train`'s
   root manifest (Cargo applies `[patch]` only there). Downsides: Fork
   maintains a fork of a third-party tool and must redo the edit at every
   pin change; the fork carries bullet's whole tree, including the
   advanced example that section 9 asks Fork's threat designers not to
   read; it needs the owner's approval as a new hosted copy.
3. **Empty stubs through `[patch.crates-io]`** (described only; not
   recommended). A path stub named sfbinpack 0.6.4 and one named
   montyformat 0.9.2 would replace the registry crates, since Cargo
   replaces a source's crate when the patch has a version that already
   exists there. But "empty" does not work: bullet_lib's two loader files
   use roughly fifteen items (types, functions and the methods called on
   them), and several sfbinpack items are part of bullet_lib's public
   API, so each stub would have to reproduce those names and signatures.
   Writing that means studying the GPL and AGPL crates' API, the result is
   a committed list of another project's identifiers in a public repo,
   and it breaks whenever bullet's loaders change. Whether Cargo would
   still download the original `.crate` with a same-version patch is not
   stated in Cargo's docs (**UNVERIFIED**). Option 2 reaches the same
   result with less risk.

### 12.5 The Cargo lines for `tools/train/Cargo.toml` (option 1)

My own manifest lines (not copied from anywhere) for Fork's program:

```toml
[dependencies]
bullet-trainer = { git = "https://github.com/jw1912/bullet", rev = "da426a49b2a4b79a55a87031cd51c89bdf1ff030" }
viriformat = "=2.0.1"
bulletformat = "=1.8.0"

[features]
cuda = ["bullet-trainer/cuda"]
```

- Cargo finds `bullet-trainer` by searching the repository for its
  manifest (Cargo's git-dependency rules); its `workspace = true` entries
  resolve to the path crates in the same checkout.
- `=1.8.0` for bulletformat is compatible with viriformat's own
  requirement, because bullet's lock resolved viriformat's bulletformat to
  that version. Keep the line only if Fork's code names bulletformat types
  directly.
- The `cuda` feature adds no crates (bullet-gpu's `cuda` feature is empty).
  Kaggle builds use `--features cuda`; local CPU-only builds (section 8)
  leave it off and get bullet's mock device.
- If the owner prefers option 2, the only line is a git dependency on
  `bullet_lib` at the fork's commit with `features = ["cuda"]` (or the
  upstream line plus the `[patch]` entry); `default-features = false`
  would be pointless, since bullet_lib has no default feature.
- **Check before relying on it (UNVERIFIED until run):** in a throwaway
  `CARGO_HOME`, run `cargo generate-lockfile` in `tools/train`, confirm
  that `Cargo.lock` has no `sfbinpack` or `montyformat` entry, and after
  the first build confirm the registry cache holds no such `.crate`
  file. The lock-graph reading of 12.1 predicts both.

---

## 13. A trainer-only program for B0

- **What it is:** the API map for Fork's training program in `tools/train`
  written against **bullet-trainer** alone (plus viriformat and
  bulletformat), with no `bullet_lib`: the public names, signatures and
  module paths it calls, and the parts of `ValueTrainer` that Fork must now
  do itself. It follows the owner's choice of 2026-10-28 (section 12,
  option 1).
- **Why it matters for Fork:** Phase 4, step 0. Deliverable 4 (the
  training program), deliverable 2's decode test (the `DataReader`),
  deliverable 6 (T comes from `ModelEvaluator`; R-quant reproduces
  `SavedFormat`), and the CPU checks of 5.8.
- **Source:** a fresh shallow clone of github.com/jw1912/bullet at
  `da426a49b2a4b79a55a87031cd51c89bdf1ff030` (MIT), in a temporary folder
  outside both repositories, deleted after reading. Read: the trainer
  crate's every source file (`crates/trainer/src`), `examples/ataxx.rs`,
  `examples/tests/test4.rs` (also a trainer-only example), the bullet_lib
  files that wrap the trainer (`value.rs`, `value/builder.rs`,
  `value/save.rs`, `value/loader.rs`, `value/loader/viribinpack.rs`,
  `game/inputs.rs`, `inputs/chess768.rs`, `trainer/schedule.rs`,
  `schedule/lr.rs` (first 90 lines), `trainer/settings.rs`, `nn.rs`), the
  compiler crate's `model/builder.rs` and `model.rs`, parts of the GPU
  crate (`runtime.rs`, `runtime/mock.rs`, `buffer.rs`, `function.rs`,
  `build.rs`), the API-call lines of `examples/advanced/main.rs` (not its
  `inputs.rs`), the five manifests and the CI workflow. Rendered docs.rs
  pages for viriformat 2.0.1 (`Game`) and bulletformat 1.8.0
  (`ChessBoard`, `BulletFormat`); **no viriformat, sfbinpack or montyformat
  source was opened, nothing was downloaded through Cargo, nothing was
  built or run.**
- **Tag:** USE (bullet-trainer, viriformat, bulletformat are MIT tools Fork
  calls). **Licence:** MIT (bullet workspace manifest `license = "MIT"`;
  viriformat and bulletformat per section 9).
- **Date verified:** 2026-10-28. Everything below is read from the code at
  the pin; "inferred" marks conclusions not seen running. Fork writes its
  own code from this prose; no bullet code is copied.

### 13.1 What `ValueTrainer` did that Fork now does

The trainer crate is lower level than `bullet_lib`. At the pin it has no
input-type trait (`SparseInputType`, `Chess768`), no output buckets, no
viriformat loader, no LR or WDL scheduler types, no eval scale, no
checkpoint folders, no `log.txt`, no `raw.bin` and no `eval(fen)`. Its
`run::TrainingSchedule` is **a different struct** from bullet_lib's
(13.4). So Fork's program provides:

1. the model graph and its input declaration (13.2);
2. the mapper closure: the Chess768 indices of section 4.2 and the
   target, so **S and the WDL weight live in Fork's closure** (13.3);
3. a `DataReader` over viriformat files, including shuffling, the filter
   and looping (13.3);
4. the LR schedule as a closure of `Step` (13.4);
5. the superbatch callback that creates the checkpoint folders and writes
   the optimiser state, `quantised.bin` and any float file (13.4, 13.5);
6. evaluation of FENs through `ModelEvaluator` (13.6).

### 13.2 The model graph for B0

**`use` paths** (crate name `bullet_trainer`; the package is
`bullet-trainer`):

- `bullet_trainer::model::{ModelInputs, ModelInputsMapper, ModelDefinition, ModelWeights, ModelEvaluator, SavedFormat, QuantTarget, ModelBuilder, ModelNode, Affine, Shape, InitSettings}`
  (the last five are re-exports from bullet-compiler, so Fork does not
  need a direct bullet-compiler dependency to build a graph);
- `bullet_trainer::optimiser::{Optimiser, adam::{AdamW, AdamWParams}}`;
- `bullet_trainer::reader::{DataReader, ReadMapLoader}`;
- `bullet_trainer::run::{DefaultDevice, TrainingSchedule, TrainingSteps, Step, HostPool, train}`
  (also `train_with_observer`, `TrainingEvent`, `TrainingError`,
  `measure_max_cpu_throughput`, `DataLoader`, `DataLoadingError`).

**Inputs.** Declared once, in order, by chaining on
`ModelInputs::default()`:

- `add_sparse(name, shape, nnz)`: `name: impl Into<String>`,
  `shape: impl Into<Shape>` (a `(rows, cols)` tuple of `usize` converts),
  `nnz: usize`. For B0: two sparse inputs of shape (768, 1) with
  nnz 32, one per perspective, side to move first.
- `add_dense(name, shape)`: the target, shape (1, 1).
- Each call wraps the previous type in a pair, so three inputs give the
  type `ModelInputs<((SparseInput, SparseInput), DenseInput<f32>)>`, and
  both the graph closure and the mapper closure receive their per-input
  values **nested the same way**: ((first, second), third).
- The names are free (bullet_lib used `stm`, `nstm`, `targets`; the ataxx
  example `stm`, `ntm`, `target`). They only match batch buffers to graph
  inputs; they do not appear in any weights file.

**Graph.** `ModelDefinition::build(&inputs, closure)`. The closure gets
`(&ModelBuilder, nodes)` where `nodes` is the nested tuple of
`ModelNode`s above, and returns
`(Option<ModelNode>, Vec<(String, ModelNode)>)`: the loss, and the named
outputs. For B0, in prose:

1. `builder.new_affine("l0", 768, 256)` and
   `builder.new_affine("l1", 512, 1)`; signature
   `new_affine(&self, id: &str, input_size: usize, output_size: usize) -> Affine`.
2. `Affine::forward(self, input: ModelNode) -> ModelNode` (weights times
   input plus bias) applied to each perspective's sparse node with the
   **same** `l0` (shared weights; `Affine` is `Copy`).
3. `ModelNode::crelu(self)` on each (clamp to [0, 1]; B0's activation).
4. `stm_hidden.concat(ntm_hidden)` (`concat(self, rhs: Self) -> Self`):
   the receiver's rows come first, so side to move occupies rows 0-255
   and columns 0-255 of `l1w`.
5. `l1.forward(...)` gives the raw output; return it in the outputs list
   under a name of Fork's choice ("output" is what bullet_lib and its
   evaluator lookups use).
6. Loss: `output.sigmoid()`, then `.squared_error(target)` (defined as
   (self − other)², so sigmoid comes first), then `.reduce_sum_batch()`.
   `ModelDefinition::new` asserts the loss is an unbatched 1 × 1 f32
   node, so the batch reduction is required. `power_error(targets, power)`
   is the alternative bullet_lib offers.

**Weights, names and order.** `new_affine(id, …)` creates two weights
named `{id}w` (shape output × input, Kaiming normal, standard deviation
√(2 / input_size)) and `{id}b` (output × 1, zero). B0: `l0w` 256 × 768,
`l0b` 256 × 1, `l1w` 1 × 512, `l1b` 1 × 1. Storage is column-major
(section 1.3). `ModelWeights` keeps them in a name-sorted map, so the
`weights.bin` record order and the optimiser's state order are
`l0b`, `l0w`, `l1b`, `l1w` (section 2.1). `quantised.bin`'s order is
the `SavedFormat` list's order instead (13.5).

**Initial weights.** `ModelWeights::new(&defn, rng_seed: u64)` (seeded
Xoroshiro128+; bullet_lib's default seed is 198273612, the ataxx example
passes the same: a bullet example value, to be recorded as such if Fork
uses it) or `ModelWeights::zeroed(&defn)`.

**Ownership detail.** `ModelDefinition` is not `Clone`, and `AdamW::new`
takes it by value. After that, get it back with
`optimiser.definition()` (returns `&ModelDefinition`), which is what
`ModelEvaluator::new` borrows.

### 13.3 Feeding batches: the mapper and the `DataReader`

**The mapper.** `ModelInputsMapper::build(&inputs, closure)`; the closure
is `Fn(&T, Step, slices) + Send + Sync + 'static`, where `T` is the data
type (`bulletformat::ChessBoard`) and `slices` is the nested tuple of
per-datapoint buffers: `&mut [i32]` of length nnz for each sparse input,
`&mut [f32]` of the shape's size for the dense one. bullet runs the
closure on several threads over chunks of the batch.

- **Sparse slots: write a terminator.** Batch buffers come from a pool
  (`HostPool::take`), and the pool documents that **reused buffers have
  unspecified contents**. Dense buffers are zero-filled before mapping;
  sparse ones are not. So when fewer than nnz features are written, the
  next slot must be set to −1 (the sparse kernels stop at the first
  negative or out-of-range index, section 7). bullet_lib also asserted
  every index < 768 and at most nnz features; Fork's mapper should check
  the same.
- **Indices from a `ChessBoard`** (bulletformat 1.8.0, docs.rs):
  `ChessBoard` is `Copy` and implements `IntoIterator` with
  `Item = (u8, u8)`: (piece code, square), stm-relative (section 4.1:
  code bits 0-2 the type, bit 3 set for the opponent). Per piece, the
  stm index is 384 × [opponent bit] + 64 × type + square and the ntm
  index is 384 × [not opponent bit] + 64 × type + (square XOR 56)
  (section 4.2; bullet_lib's `Chess768` does exactly this).
- **Score and result:** `score()` (i16) and `result()` (f32, 0.0 / 0.5 /
  1.0) or `result_idx()` (usize, 0 / 1 / 2) come from the
  `bulletformat::BulletFormat` trait, which must be in scope. Both are
  the side to move's (section 4.1).
- **Target:** Fork computes w × result + (1 − w) × sigmoid(score / S)
  itself, w being the weight on the result (DESIGN.md's 1 − λ). The
  closure receives the batch's `Step` (`superbatch()`, `batch()`,
  `final_superbatch()`), so a WDL schedule is a function of it. Detail
  for bit-exact agreement with bullet_lib's targets: bullet_lib forms the
  f32 reciprocal 1 / S once and multiplies the score by it; the ataxx
  example divides by its scale. The two can differ in the last bit; Fork
  picks one and records it (no effect on the parity test, which compares
  forward passes).

**The reader trait.** `bullet_trainer::reader::DataReader<T>`: a trait
with supertraits `Clone + Send + Sync + 'static` and one method,
`read_chunks<F: FnMut(&[T]) -> bool>(&self, skip_count: usize, f: F)`.

- The reader calls `f` with slices of positions, any length; `f` returns
  `true` when training wants no more data, and the reader must then
  return.
- `skip_count` is the number of **positions** already consumed:
  `ReadMapLoader` passes batch size × the start step's total batches, so
  it is 0 on a fresh run and non-zero on a resume. A reader may honour
  it (deterministic resume) or ignore it (bullet_lib's viriformat loader
  ignores it).
- The reader must keep producing until told to stop: `train` returns an
  error if the data ends before the scheduled last batch. bullet_lib's
  loader loops over its files forever.
- Glue: `ReadMapLoader::new(reader, mapper, threads: u8)` (threads = the
  mapping threads) gives the `DataLoader` that `train` takes by value.
  The trainer's own `FixedSizeDataReader` (for fixed-size records such as
  a raw bulletformat file) is the only reader it ships.

**How bullet_lib's viriformat loader turned games into positions**
(names from its code and viriformat's docs.rs page; Fork writes its own
reader):

1. Raw bytes per game: `Game::deserialise_fast_into_buffer(reader: &mut impl BufRead, buffer: &mut Vec<u8>) -> std::io::Result<()>`
   (appends; the caller clears the buffer). bullet_lib stops reading a
   file at the first error (section 5.2).
2. Decode: `Game::deserialise_from(reader: &mut impl BufRead, buffer: Vec<(Move, I16Le)>) -> std::io::Result<Game>`.
   The second argument is a reusable move vector; bullet_lib passes the
   previous game's public `moves` field back in. (`I16Le` is not linked
   on docs.rs; Fork does not need to name it: an empty `Vec::new()` or
   `game.into_move_buffer()` both type-check by inference, inferred.)
3. Convert: either
   `Game::splat_to_bulletformat(&self, callback: impl FnMut(ChessBoard) -> anyhow::Result<()>, filter: &Filter) -> anyhow::Result<()>`
   or
   `Game::splat_to_bulletformat_with_filter_callback(&self, callback: impl FnMut(ChessBoard) -> anyhow::Result<()>, should_filter: impl FnMut(Move, i32, &Board, WDL, &mut ThreadRng) -> bool) -> anyhow::Result<()>`.
   The callback receives each emitted `bulletformat::ChessBoard`;
   `should_filter` returns **true to drop** a position (bullet_lib negates
   its own keep-function to fit). `ThreadRng` is rand 0.9's; `WDL` has
   `Win`, `Draw`, `Loss`.
4. bullet_lib then shuffles a large buffer of positions with a
   clock-seeded RNG and hands it to `f`.

- Paths: `viriformat::dataformat::{Game, Filter, WDL}`,
  `viriformat::chess::board::Board`, `viriformat::chess::chessmove::Move`
  (docs.rs type titles; the same paths bullet_lib re-exports).
- **No `anyhow` dependency is needed** as long as Fork's callback closure
  returns `Ok(())` (its type comes from the bound) and Fork handles the
  splat result with `unwrap`/`expect` or by converting the error to a
  string rather than naming `anyhow::Result` (inferred).
- Also on `Game` (docs.rs): `filter_pass_count(&self, &Filter) -> u64`
  and a callback variant, `visit_positions`, `len`, `outcome() -> WDL`,
  `MAX_SPLATTABLE_GAME_SIZE = 512`. The semantics questions of section 6
  (sign handling, which positions are emitted, games over 512 moves)
  remain **UNVERIFIED** and are settled by the decode test.

### 13.4 Training entry point, schedule, optimiser, checkpoints

**Device.** `DefaultDevice::new(ordinal: i32)` returns
`Result<Arc<Device<G>>, G::Error>`; `DefaultDevice` is a type alias
chosen by features (13.7). Keep a clone of the `Arc` if the program also
needs it for a `HostPool` or evaluator, or get it back later with
`optimiser.device()`.

**Optimiser.** `AdamW::new(definition: ModelDefinition, weights: ModelWeights, device: Arc<Device<G>>, params: AdamWParams) -> Result<Optimiser<G, AdamW<G>>, G::Error>`.

- `AdamWParams` has public fields `decay`, `beta1`, `beta2`,
  `min_weight`, `max_weight` (all f32) and `Default` = 0.01, 0.9, 0.999,
  −1.98, 1.98 (section 5.4). So "AdamW with clip 1.98" is
  `AdamWParams::default()`; the ataxx example spells out the same five
  values.
- Per-weight settings: `optimiser.set_params_for_weight(id: &str, params)`
  (panics on an unknown id) or `set_params(params)` for all.
- `AdamW::new` errors if `max_weight < min_weight`.

**Schedule (trainer crate).** `run::TrainingSchedule` has exactly four
public fields:

- `steps: TrainingSteps` (`batch_size`, `batches_per_superbatch`,
  `start_superbatch`, `end_superbatch`, all usize; superbatches count from
  1, end inclusive; rejected: any of the first three zero, start after
  end, overflow);
- `lr_schedule: Box<dyn Fn(Step) -> f32>` (called once per batch; Fork
  writes its own schedule as a pure function of `step.superbatch()` and
  `step.batch()`, so resumes continue exactly, as in 5.3);
- `log_rate: usize` (the console prints when the batch index within the
  superbatch is a multiple of it; bullet_lib used 128; 0 disables);
- `track_grad_norms: bool`.

There is **no eval scale, WDL scheduler, save rate or net id**: those
move into the mapper closure (13.3) and the superbatch callback (below).

**Entry point.**
`train(optimiser: &mut Optimiser<G, O>, schedule: TrainingSchedule, dataloader: impl DataLoader, batch_callback: impl FnMut(&mut Optimiser<G, O>, Step, f32), superbatch_callback: impl FnMut(&mut Optimiser<G, O>, Step)) -> Result<(), TrainingError<G>>`.

- The batch callback gets the batch's loss (summed loss ÷ batch size);
  bullet_lib accumulated it every 32 batches into its `log.txt` record.
- The superbatch callback runs on the calling thread after each
  superbatch's last batch, so non-`Send` values (the `SavedFormat` list,
  13.5) can be captured.
- `train_with_observer(…, observer: &mut impl FnMut(&TrainingEvent))`
  replaces the console printer with Fork's own; `TrainingEvent` variants:
  `RunStarted`, `TrainingReady`, `BatchCompleted` (step, loss, learning
  rate, times, optional gradient norms), `SuperbatchCompleted`,
  `RunCompleted` (all `#[non_exhaustive]`, so match with `..`).
- Gradients are averaged (factor 1 / batch size); the data loader runs
  in its own thread with a 32-batch queue.

**Checkpoint saving without bullet_lib** (bullet_lib's `save_to_checkpoint`
did these steps; the trainer crate has none of the folder logic):

1. In the superbatch callback, decide whether to save (bullet_lib: every
   `save_rate` superbatches and at `step.final_superbatch()`).
2. Create `<output>/<net-id>-<superbatch>/` and its `optimiser_state/`
   subfolder **yourself**: `Optimiser::write_to_checkpoint(&self, path: &str) -> Result<(), G::Error>`
   writes `weights.bin`, `momentum.bin`, `velocity.bin` straight into
   `path` and panics (an unwrap on file creation) if the folder is
   missing.
3. Write `quantised.bin` (13.5) and any float file.
4. Write Fork's own loss log if wanted.

Keeping bullet_lib's folder names keeps section 2's descriptions valid
for Fork's files.

**Resume.** `Optimiser::load_from_checkpoint(&mut self, path: &str) -> Result<(), G::Error>`
takes the **`optimiser_state` folder itself** (bullet_lib's wrapper took
the parent and appended `optimiser_state`). It loads `weights.bin` and
the AdamW moments; missing files or unknown names panic rather than
returning an error. `load_weights_from_file(&mut self, path: &str)` loads
weights only. Then set `start_superbatch` to the saved superbatch + 1;
everything else unchanged (5.7).

**What `examples/ataxx.rs` uses** (bullet's example values, not
defaults): AdamW with the five default values spelled out; a constant
LR of 0.001 as a closure; no WDL schedule, the result weight 0.2 and
the scale 400 written inside its mapper; batch 16,384, one batch per
superbatch, superbatches 1-10; `log_rate` 128; gradient norms off; both
callbacks empty (**it saves nothing and loads nothing**); seed
198273612; device 0; `FixedSizeDataReader` over one file of its own
`repr(C)` record type with 4 mapping threads; 147 inputs, nnz 49,
hidden 256, SCReLU. `examples/tests/test4.rs` is the same program for a
768 → 32 chess net reading a raw 32-byte bulletformat-layout file
through its own record struct (no bulletformat dependency).

### 13.5 Saving: the quantised file and the float file

- **Entries:** `SavedFormat::id(name: &str)`, then the builder methods
  `.round()`, `.quantise::<T>(multiplier)` with `T` = `i8` or `i16`
  (multiplier type `i16`) or `i32` (multiplier `i32`), `.transpose()`,
  `.transform(closure)`; also `SavedFormat::custom(bytes)` and
  `SavedFormat::empty()`. Rules: section 1 (f64 product, round half away
  from zero, full-range check, transforms first).
- **B0 list:** `l0w` rounded i16 × 255; `l0b` rounded i16 × 255; `l1w`
  rounded i16 × 64; `l1b` rounded i32 × 16320 (255 × 64). No transpose:
  `l1w` is 1 × 512, so column-major is already the plain order, and `l0w`
  column-major is the accumulator's feature-major order (section 1.3).
- **Writing:** `ModelWeights::to_quantised_buffer(&self, format: &[SavedFormat], pad: bool) -> std::io::Result<Vec<u8>>`;
  `pad = true` gives bullet's 64-byte padding (section 1.3). Get the
  weights with `optimiser.cpu_weights()`, which copies the device values
  to the host and returns a read guard (`Result<RwLockReadGuard<ModelWeights>, G::Error>`).
  An error means bullet would not have written the file (overflow or
  NaN); Fork's program should report it and keep training, as bullet_lib
  did. A wrong id panics inside the entry's first transform.
- `SavedFormat` holds its transforms behind `Rc`, so it is not `Send`:
  build the list on the main thread and use it in the superbatch
  callback (fine, 13.4).
- **Float file, two choices:**
  - `weights.bin` (section 2.1) from `write_to_checkpoint`, or directly
    `ModelWeights::write_into(&self, writer: &mut impl Write)` on the
    `cpu_weights()` guard: named, length-prefixed records in name order
    (`l0b`, `l0w`, `l1b`, `l1w`). This is the file DESIGN.md's float
    order refers to; `ModelWeights::load_from(&mut self, reader: impl Read)`
    reads it back.
  - a `raw.bin` like bullet_lib's: per id in list order, the f32 values
    (from `optimiser.weights()`, a `BTreeMap<String, Arc<Buffer>>`, via
    `get(id)` and `to_host()`, or from the `cpu_weights()` guard's
    `get(id)`), written as little-endian f32 with no header, or through
    `QuantTarget::Float.quantise(false, &values)`.

### 13.6 Evaluating a FEN with the float model

bullet_lib's `eval` was a thin layer over trainer-crate calls; Fork
repeats it:

1. **Position:** parse the FEN with bulletformat's `FromStr` for
   `ChessBoard` (`Err = String`), appending " | 0 | 0.0" as bullet_lib
   did (section 3 for what the parser reads).
2. **Inputs:** with a `HostPool::new(device: Arc<Device<G>>) -> Arc<HostPool<G>>`,
   call `mapper.map(&pool, &[board], Step::default(), 1)` (signature
   `map(&self, pool: &Arc<HostPool<G>>, data: &[T], step: Step, threads: u8) -> Result<PreparedBatchHost<G>, G::Error>`),
   then `.to_device(&device)` (`PreparedBatchHost::to_device(self, device: &Arc<Device<G>>) -> Result<TensorMap<G>, G::Error>`).
   Use a mapper with the **same input list** as the graph, target
   included (any value): bullet_lib did this, and whether the evaluator
   accepts a map without the loss-only input is **UNVERIFIED**.
3. **Evaluator:** `ModelEvaluator::new(defn: &ModelDefinition, device: Arc<Device<G>>) -> Result<ModelEvaluator<G>, G::Error>`
   (compiles a batch-size-1 forward pass), then either
   `load_device_weights(&mut self, weights: &TensorMap<G>)` with
   `optimiser.weights()` (shares the live buffers, so later training or a
   checkpoint load is seen) or `load_weights(&mut self, weights: &ModelWeights)`
   (uploads a copy; for a standalone evaluator: build the definition,
   `ModelWeights::zeroed`, `load_from` a `weights.bin`, then this, with no
   optimiser at all).
4. **Run:** `evaluate(&mut self, inputs: &TensorMap<G>) -> Result<&TensorMap<G>, G::Error>`;
   take the output by the name given in the graph, call `to_host()` on the
   buffer (returns bullet-compiler's `TValue`) and read it with the
   `f32()` method (a `&[f32]`; panics on another dtype). Calling the
   method needs no import, so no direct bullet-compiler dependency is
   required (inferred). The single value is the raw output, side to
   move's view, before any sigmoid (section 3).

### 13.7 The mock (CPU) device

- **Selection:** in bullet-trainer, `DefaultDevice` is
  `Device<MockGpu>` whenever **neither `cuda` nor `rocm`** is enabled
  (`Device<Cuda>` with `cuda`; `rocm` without `cuda` gives ROCm). The
  mock runtime (`bullet_gpu::runtime::mock::MockGpu`) is always compiled;
  its error type is `String`. A `metal` feature exists but the trainer's
  alias ignores it (still the mock).
- **What the mock does:** real zeroed host allocations for device and
  pinned memory, real copies both ways, and success for driver init,
  contexts, streams, kernel "compilation", module loading and the BLAS
  handle; **kernel launches and both matrix-multiply calls return its
  error** ("mock runtime", paraphrased). The stream allocator is reported
  unsupported, so allocation falls back to the context path that works.
- **Works on the mock, by reading (inferred, not run):**
  `DefaultDevice::new`, `ModelInputs`/`ModelDefinition::build`,
  `ModelWeights::new`/`zeroed`/`load_from`/`write_into`/
  `to_quantised_buffer` (plain CPU code), `AdamW::new`,
  `write_to_checkpoint`, `load_from_checkpoint`, `load_weights_from_file`,
  `cpu_weights`, the mapper with a `HostPool`, `to_device`, any
  `DataReader` with `ReadMapLoader`, `ModelEvaluator::new` and its weight
  loading, and `measure_max_cpu_throughput(dataloader, steps)` (which
  builds its own mock device on purpose, to time reading and mapping).
  So the 5.8 checks (save list, file size, decode test) need no GPU.
- **Fails on the mock:** `train`/`train_with_observer` at the first
  backward pass (a `TrainingError::GradientCalculationError` carrying the
  mock's message; the data loader thread has already started) and
  `ModelEvaluator::evaluate` (an `Err`, not a panic). So T needs the
  `cuda` build.

### 13.8 Cargo

- **Lines** (Fork's own, as in 12.5):
  - `bullet-trainer = { git = "https://github.com/jw1912/bullet", rev = "da426a49b2a4b79a55a87031cd51c89bdf1ff030" }`
  - `viriformat = "=2.0.1"`
  - `bulletformat = "=1.8.0"` (needed: Fork names `ChessBoard` and calls
    `BulletFormat` methods; viriformat's docs link `ChessBoard` to
    bulletformat 1.8.0, so the two unify)
  - feature `cuda = ["bullet-trainer/cuda"]` in Fork's `[features]`;
    Kaggle builds with `--features cuda` (with `CUDA_PATH` set, section
    8), local builds without it get the mock.
- **Optional extra lines.** Naming the device type in Fork's own helper
  functions (for example a `save_checkpoint` taking `&Optimiser<G, O>`)
  needs the `Gpu` trait bound from `bullet_gpu::runtime`, which
  bullet-trainer does not re-export. Either keep such code inside closures
  and `main` (types inferred), or add
  `bullet-gpu = { git = "https://github.com/jw1912/bullet", rev = "<same>" }`
  (and bullet-compiler likewise only if Fork wants to name `TValue` or
  `DType`). Same repository and revision, so Cargo resolves them to the
  same packages and adds nothing to the graph (inferred from Cargo's
  source identity rules; not run).
- **Default features:** bullet-trainer's `[features]` has `cuda`, `rocm`,
  `metal` and **no `default`**, and Cargo enables no feature unless a
  `default` list exists (Cargo Book, features). So
  `default-features = false` is unnecessary.
- **Workspace issues:** bullet-trainer's manifest inherits its metadata
  and its bullet-compiler / bullet-gpu dependencies with
  `workspace = true` from bullet's virtual workspace root
  (`[workspace.dependencies]` as path dependencies). Cargo finds the crate
  by searching the git checkout for its `Cargo.toml` (Cargo Book,
  specifying dependencies) and locates a member's workspace by searching
  parent directories for a `[workspace]` manifest (Cargo Book,
  workspaces), so the inheritance should resolve inside the checkout with
  **no `[patch]` and no workspace entry on Fork's side**. That Cargo does
  this for a git dependency is inferred from those two pages, not
  stated by them and not run (**UNVERIFIED**, same check as 12.5).
  bullet's `[profile]` settings would not apply in any case (there are
  none at the pin); Fork sets its own release profile.
- **Toolchain:** the workspace sets edition 2024 and `rust-version = "1.87"`,
  so Fork's toolchain must be at least Rust 1.87 (bullet's CI uses
  current stable).
- bullet-trainer's manifest also declares two `[[example]]` targets
  (`ataxx`, `test4`) by relative path; they are examples of the
  dependency, not built for Fork (general Cargo behaviour, UNVERIFIED as
  in 12.3).

### 13.9 UNVERIFIED items of this section

| Item | Why |
|---|---|
| Everything in 13.7 marked as working on the mock | read from the mock runtime and call paths, not run |
| `ModelEvaluator::evaluate` accepting an input map without the target (loss-only) input | depends on whether the forward lowering drops unused inputs; not read to that depth, not run. Workaround: always pass the full mapped input set |
| No `anyhow`, `bullet-compiler` or `bullet-gpu` dependency needed when types are inferred | Rust inference rules applied to the signatures; not compiled |
| `Vec::new()` or `into_move_buffer()` type-checking as `deserialise_from`'s buffer without naming `I16Le` | inferred from the docs.rs signature; not compiled |
| bullet-trainer as a git dependency from outside bullet's workspace (inheritance, no `[patch]`) | inferred from Cargo's docs; not run (check of 12.5) |
| Extra `bullet-gpu` / `bullet-compiler` git lines unifying with bullet-trainer's path dependencies | inferred; not run |
| viriformat's `should_filter` return meaning (true = drop) | from the parameter name, the docs' "yielding only those positions that pass the filter" and bullet_lib's negation; viriformat's code not opened |
| The section 6 items (score sign, emitted positions, games over 512 moves, filter perspective) | unchanged; the decode test settles them |

## 14. Measured on the CPU (2026-10-28)

Fork's training program (main, `tools/train`, on bullet-trainer at the pin,
viriformat 2.0.1, bulletformat 1.8.0), built locally with the mock device in
a throwaway Cargo home:
- **The lock file and the Cargo cache hold neither sfbinpack nor
  montyformat** (49 packages): depending on bullet-trainer instead of
  bullet_lib works as §12 inferred. Cargo checks out bullet's whole git
  repository, so bullet's own MIT wrapper files that would call those
  crates are present, but the crates themselves are never fetched.
- **Sizes:** `quantised.bin` of B0's initial weights is 394,816 bytes
  (394,756 of tensors plus 60 of padding), `weights.bin` 789,556 bytes, as
  §5.8 predicted. The padding rule is corrected in §1.3.
- **The quantization leg against bullet's real files** passes exactly:
  main's `tools/nnue/reference.py` (f64, half away from zero) reproduces
  every integer of bullet's `quantised.bin`, and Fork's net file and
  inference agree (`fork netcheck`, 46 positions).
- **viriformat's decoding of Fork's shards** (resolves §6's open items and
  §5.2's "tactical"): on 45,626 positions of a generation-0 shard,
  viriformat's `splat_to_bulletformat` with an unrestricted filter gives
  exactly python-chess's replay: the position before each move (the final
  position is not emitted), side-to-move-relative pieces, the score
  negated for Black to move, the result from the side to move's view. With
  `filter_check`, `filter_tactical` and `max_eval` = 20000 it keeps exactly
  the positions that are not in check, whose move played was not a capture
  or promotion, and whose |score| is at most 20000: **"tactical" means a
  capture or promotion was played** (30,955 kept, 0 mismatches).
- Not measured: games longer than 512 moves (Fork discards games over 500
  plies), and anything that needs the GPU (training, `eval`).
