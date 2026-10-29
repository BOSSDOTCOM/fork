// SPDX-License-Identifier: GPL-3.0-or-later

//! Fork's training program for the baseline network B0 (DESIGN.md §5.3,
//! deliverable 4), on bullet's trainer crate (MIT; KB bullet-internals.md
//! §13). Fork's own code: the model, the data reader, the target, the
//! schedule, checkpoints and the quantized save list.
//!
//! B0: 768 inputs per perspective -> 256 hidden, clipped ReLU, the two halves
//! concatenated side to move first -> 1 output. The target is
//! (1 - w) * sigmoid(score / S) + w * result, w the weight on the game result
//! (DESIGN.md's lambda is 1 - w). The saved tensors and their order match
//! tools/nnue/b0.json.
//!
//!   fork-train check  --out DIR
//!   fork-train dump   --data SHARD --count N
//!   fork-train train  --data SHARD... --out DIR --scale S [options]
//!   fork-train eval   --checkpoint DIR --epd FILE --out FILE

use std::{
    fs::{self, File},
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
};

use bullet_trainer::{
    model::{
        DenseInput, ModelDefinition, ModelEvaluator, ModelInputs, ModelInputsMapper, ModelWeights, SavedFormat,
        SparseInput,
    },
    optimiser::adam::{AdamW, AdamWParams},
    reader::{DataReader, ReadMapLoader},
    run::{train, DefaultDevice, HostPool, Step, TrainingSchedule, TrainingSteps},
};
use bulletformat::{BulletFormat, ChessBoard};
use viriformat::dataformat::{Filter, Game};

const INPUTS: usize = 768;
const HIDDEN: usize = 256;
const MAX_ACTIVE: usize = 32;
// Positions are dropped when |score| exceeds Fork's evaluation range
// (EvalLimit, src/eval/eval_scale.hpp): those are mate or tablebase scores.
const MAX_SCORE: u32 = 20000;

type B0Inputs = ModelInputs<((SparseInput, SparseInput), DenseInput<f32>)>;

fn inputs() -> B0Inputs {
    ModelInputs::default()
        .add_sparse("stm", (INPUTS, 1), MAX_ACTIVE)
        .add_sparse("ntm", (INPUTS, 1), MAX_ACTIVE)
        .add_dense("target", (1, 1))
}

fn definition(inputs: &B0Inputs) -> ModelDefinition {
    ModelDefinition::build(inputs, |builder, ((stm, ntm), target)| {
        let l0 = builder.new_affine("l0", INPUTS, HIDDEN);
        let l1 = builder.new_affine("l1", 2 * HIDDEN, 1);
        let ours = l0.forward(stm).crelu();
        let theirs = l0.forward(ntm).crelu();
        let output = l1.forward(ours.concat(theirs));
        let loss = output.sigmoid().squared_error(target).reduce_sum_batch();
        (Some(loss), vec![("output".to_string(), output)])
    })
}

// The quantized file, in tools/nnue/b0.json's order: QA = 255 and QB = 64
// (bullet's convention; ORIGINALITY.md), output bias at QA * QB.
fn save_list() -> Vec<SavedFormat> {
    vec![
        SavedFormat::id("l0w").round().quantise::<i16>(255),
        SavedFormat::id("l0b").round().quantise::<i16>(255),
        SavedFormat::id("l1w").round().quantise::<i16>(64),
        SavedFormat::id("l1b").round().quantise::<i32>(255 * 64),
    ]
}

fn mapper(inputs: &B0Inputs, scale: f32, result_weight: f32) -> ModelInputsMapper<ChessBoard> {
    ModelInputsMapper::build(inputs, move |pos: &ChessBoard, _step: Step, ((stm, ntm), target)| {
        let mut n = 0;
        for (piece, square) in pos.into_iter() {
            let opp = usize::from(piece & 8 != 0);
            let kind = usize::from(piece & 7);
            let sq = usize::from(square);
            stm[n] = (384 * opp + 64 * kind + sq) as i32;
            ntm[n] = (384 * (1 - opp) + 64 * kind + (sq ^ 56)) as i32;
            n += 1;
        }
        // Pooled batch buffers are reused uncleared: end short lists (KB §13).
        if n < MAX_ACTIVE {
            stm[n] = -1;
            ntm[n] = -1;
        }
        let expected = 1.0 / (1.0 + (-f32::from(pos.score()) / scale).exp());
        target[0] = (1.0 - result_weight) * expected + result_weight * pos.result();
    })
}

/// Fork's own splitmix64 (src/core/splitmix.hpp; Vigna's public-domain
/// reference), for a reproducible shuffle.
struct SplitMix(u64);
impl SplitMix {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
}

fn filter() -> Filter {
    Filter { filter_check: true, filter_tactical: true, max_eval: MAX_SCORE, ..Filter::UNRESTRICTED }
}

/// Reads Fork's shards (viriformat games) forever, in file order, through
/// viriformat's own conversion, shuffling each buffer of `buffer` positions
/// with a seeded stream (so the data order is reproducible).
#[derive(Clone)]
struct ShardReader {
    files: Vec<PathBuf>,
    buffer: usize,
    seed: u64,
}

impl ShardReader {
    fn for_each_game(path: &Path, mut f: impl FnMut(Game)) {
        let mut r = BufReader::new(File::open(path).unwrap_or_else(|e| panic!("{}: {e}", path.display())));
        while !r.fill_buf().expect("read").is_empty() {
            let game = Game::deserialise_from(&mut r, Vec::new())
                .unwrap_or_else(|e| panic!("{}: undecodable game: {e}", path.display()));
            f(game);
        }
    }
}

impl DataReader<ChessBoard> for ShardReader {
    fn read_chunks<F: FnMut(&[ChessBoard]) -> bool>(&self, _skip_count: usize, mut f: F) {
        let mut rng = SplitMix(self.seed);
        let mut buf = Vec::with_capacity(self.buffer);
        let filter = filter();
        loop {
            for path in &self.files {
                let mut stop = false;
                Self::for_each_game(path, |game| {
                    if stop {
                        return;
                    }
                    game.splat_to_bulletformat(
                        |b| {
                            buf.push(b);
                            Ok(())
                        },
                        &filter,
                    )
                    .expect("splat");
                    if buf.len() >= self.buffer {
                        for i in (1..buf.len()).rev() {
                            buf.swap(i, (rng.next() % (i as u64 + 1)) as usize);
                        }
                        for chunk in buf.chunks(16384) {
                            if f(chunk) {
                                stop = true;
                                return;
                            }
                        }
                        buf.clear();
                    }
                });
                if stop {
                    return;
                }
            }
        }
    }
}

struct Args(Vec<String>);
impl Args {
    fn get(&self, key: &str) -> Option<&str> {
        self.0.iter().position(|a| a == key).and_then(|i| self.0.get(i + 1)).map(String::as_str)
    }
    fn all(&self, key: &str) -> Vec<String> {
        let mut out = Vec::new();
        let mut it = self.0.iter();
        while let Some(a) = it.next() {
            if a == key {
                out.extend(it.by_ref().take_while(|v| !v.starts_with("--")).cloned());
                break;
            }
        }
        out
    }
    fn num<T: std::str::FromStr>(&self, key: &str, default: T) -> T {
        self.get(key).map(|v| v.parse().unwrap_or_else(|_| panic!("bad value for {key}"))).unwrap_or(default)
    }
    fn need(&self, key: &str) -> &str {
        self.get(key).unwrap_or_else(|| panic!("missing {key}"))
    }
}

fn main() {
    let argv: Vec<String> = std::env::args().skip(1).collect();
    let Some(cmd) = argv.first().cloned() else {
        eprintln!("usage: fork-train check|dump|train|eval ... (see the source header)");
        std::process::exit(2);
    };
    let a = Args(argv);
    let ins = inputs();
    match cmd.as_str() {
        "check" => {
            // The graph builds, and the save list matches it: the quantized
            // file of the initial weights has B0's size (394,756 bytes of
            // tensors, padded to 64).
            let defn = definition(&ins);
            let weights = ModelWeights::new(&defn, a.num("--seed", 1));
            let bytes = weights.to_quantised_buffer(&save_list(), true).expect("quantise");
            let out = PathBuf::from(a.need("--out"));
            fs::create_dir_all(&out).expect("out");
            fs::write(out.join("quantised.bin"), &bytes).expect("write");
            let mut wf = File::create(out.join("weights.bin")).expect("weights.bin");
            weights.write_into(&mut wf).expect("write weights");
            println!("quantised.bin {} bytes", bytes.len());
        }
        "dump" => {
            // Positions exactly as training sees them (side-to-move relative):
            // "piece:square ... | score | result" per kept position.
            let mut left: usize = a.num("--count", 1000);
            let filter = if a.get("--keep-all").is_some() { Filter::UNRESTRICTED } else { filter() };
            let out = std::io::stdout();
            let mut out = out.lock();
            ShardReader::for_each_game(Path::new(a.need("--data")), |game| {
                game.splat_to_bulletformat(
                    |b: ChessBoard| {
                        if left > 0 {
                            left -= 1;
                            let pieces: Vec<String> = b.into_iter().map(|(p, s)| format!("{p}:{s}")).collect();
                            writeln!(out, "{} | {} | {}", pieces.join(" "), b.score(), b.result()).unwrap();
                        }
                        Ok(())
                    },
                    &filter,
                )
                .expect("splat");
            });
        }
        "train" => {
            let scale: f32 = a.num("--scale", 0.0);
            assert!(scale > 0.0, "--scale S is required (fitted on the data)");
            let result_weight: f32 = a.num("--result-weight", 0.5);
            let start: usize = a.num("--start", 1);
            let end: usize = a.num("--superbatches", 40);
            let lr: f32 = a.num("--lr", 0.001);
            let lr_step: usize = a.num("--lr-step", 18);
            let out = PathBuf::from(a.need("--out"));
            let reader = ShardReader {
                files: a.all("--data").into_iter().map(PathBuf::from).collect(),
                buffer: a.num("--buffer", 1 << 24),
                seed: a.num("--seed", 1),
            };
            let defn = definition(&ins);
            let weights = ModelWeights::new(&defn, a.num("--seed", 1));
            let device = DefaultDevice::new(a.num("--device", 0)).expect("device");
            let mut opt = AdamW::new(defn, weights, device, AdamWParams::default()).expect("optimiser");
            if let Some(dir) = a.get("--resume") {
                let state = Path::new(dir).join("optimiser_state");
                opt.load_from_checkpoint(state.to_str().expect("path")).expect("resume");
            }
            let schedule = TrainingSchedule {
                steps: TrainingSteps {
                    batch_size: a.num("--batch", 16384),
                    batches_per_superbatch: a.num("--batches", 6104),
                    start_superbatch: start,
                    end_superbatch: end,
                },
                lr_schedule: Box::new(move |step: Step| lr * 0.1f32.powi(((step.superbatch() - 1) / lr_step) as i32)),
                log_rate: 128,
                track_grad_norms: false,
            };
            let loader = ReadMapLoader::new(reader, mapper(&ins, scale, result_weight), a.num("--threads", 3));
            let net_id = a.get("--id").unwrap_or("b0").to_string();
            train(
                &mut opt,
                schedule,
                loader,
                |_, step, loss| println!("superbatch {} batch {} loss {loss}", step.superbatch(), step.batch()),
                |opt, step| {
                    // <out>/<id>-<superbatch>/: optimiser_state/ (the float
                    // weights and AdamW's moments), quantised.bin, superbatch.txt.
                    let dir = out.join(format!("{net_id}-{}", step.superbatch()));
                    let state = dir.join("optimiser_state");
                    fs::create_dir_all(&state).expect("checkpoint folder");
                    opt.write_to_checkpoint(state.to_str().expect("path")).expect("write checkpoint");
                    let bytes =
                        opt.cpu_weights().expect("weights").to_quantised_buffer(&save_list(), true).expect("quantise");
                    fs::write(dir.join("quantised.bin"), bytes).expect("quantised.bin");
                    fs::write(dir.join("superbatch.txt"), format!("{}\n", step.superbatch())).expect("superbatch.txt");
                },
            )
            .expect("train");
        }
        "eval" => {
            // The trainer's own float evaluation of each FEN (parity leg T):
            // the raw output, side to move's view, before the sigmoid.
            let defn = definition(&ins);
            let weights = ModelWeights::new(&defn, 1);
            let device = DefaultDevice::new(a.num("--device", 0)).expect("device");
            let mut opt = AdamW::new(defn, weights, device.clone(), AdamWParams::default()).expect("optimiser");
            let state = Path::new(a.need("--checkpoint")).join("optimiser_state");
            opt.load_from_checkpoint(state.to_str().expect("path")).expect("load");
            let mut evaluator = ModelEvaluator::new(opt.definition(), opt.device()).expect("evaluator");
            evaluator.load_device_weights(opt.weights()).expect("weights");
            let map = mapper(&ins, 1.0, 0.0);
            let pool = HostPool::new(device.clone());
            let mut out = File::create(a.need("--out")).expect("out");
            for line in BufReader::new(File::open(a.need("--epd")).expect("epd")).lines() {
                let fen = line.expect("line");
                let fen = fen.trim();
                if fen.is_empty() || fen.starts_with('#') {
                    continue;
                }
                let board: ChessBoard = format!("{fen} | 0 | 0.0").parse().expect("fen");
                let batch = map.map(&pool, &[board], Step::default(), 1).expect("map").to_device(&device).expect("dev");
                let raw = evaluator.evaluate(&batch).expect("eval").get("output").expect("output").to_host().expect("host").f32()[0];
                writeln!(out, "{fen} | {raw}").expect("write");
            }
        }
        _ => {
            eprintln!("unknown command {cmd}");
            std::process::exit(2);
        }
    }
}
