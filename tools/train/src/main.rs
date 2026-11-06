// SPDX-License-Identifier: GPL-3.0-or-later

//! Fork's training program (DESIGN.md §5.3, deliverable 4, and the Phase 4
//! bake-off, §5.4), on bullet's trainer crate (MIT; KB bullet-internals.md
//! §13). Fork's own code: the models, the input features, the data reader,
//! the target, the schedule, checkpoints and the quantized save lists.
//!
//! Architectures (--arch; tools/nnue/<arch>.json describes each saved file):
//! - b0: 768 inputs per perspective -> 256, clipped ReLU, the two halves
//!   concatenated side to move first -> 1 output (the baseline network).
//! - s512: the 768 inputs mirrored left-right when the perspective's own king
//!   is on files a-d -> 512, squared clipped ReLU -> 8 outputs, one picked by
//!   the game phase through a 25-entry table (--buckets; owner, 2026-10-30:
//!   H-512's selector, so S and H differ only in the king regions).
//! - h512: as s512, the inputs copied per king region (a 32-entry map of the
//!   mirrored own-king square, --regions) plus a shared factoriser set that
//!   is merged into every region when saved.
//! - afs: h512's inputs -> 512, clipped, each half's first 256 values times
//!   its last 256 -> 512 values -> 16 -> 32 -> 1, squared clipped ReLU between,
//!   each of the three layers in 8 copies picked by the game phase.
//! - xgr512: mirrored 768 inputs over 4 fixed king regions with a factoriser,
//!   plus 640 exposure inputs (a non-king piece attacked by a lower-valued
//!   enemy piece, or attacked and undefended) with a 10-input factoriser ->
//!   512 hidden values and 3 side values per perspective; squared clipped
//!   ReLU; two outputs blended by a gate: out = b + g (a - b), g the clipped
//!   sum of both perspectives' side value 0, a and b each plus twice the
//!   difference of the perspectives' side value 1 or 2.
//! The target is (1 - w) * sigmoid(score / S) + w * result, w the weight on
//! the game result (DESIGN.md's lambda is 1 - w).
//!
//!   fork-train check    --arch A [maps] --out DIR
//!   fork-train dump     --data SHARD --count N
//!   fork-train stats    --data SHARD... [--positions N]   (king squares, phase, piece counts)
//!   fork-train features --arch A [maps] (--epd FILE | --data SHARD --count N)
//!   fork-train train    --arch A [maps] --data SHARD... --out DIR --scale S [--val SHARD --patience P]
//!                       [--init-weights weights.bin] [options]
//!   fork-train eval     --arch A [maps] (--checkpoint DIR | --weights weights.bin) --epd FILE --out FILE
//!   fork-train loader   --data SHARD... [--positions N]   (decoding speed, one thread)
//! [maps] are --regions (32 comma-separated region numbers) and --buckets (25
//! bucket numbers), as the architecture needs; the files in
//! tools/nnue/ hold the fitted ones.
//!
//! With --val, the loss on the first --val-positions (default 20,000) kept positions of a
//! held-out shard is measured after every superbatch (written to val.txt);
//! training stops early, after that superbatch's checkpoint, once it has not
//! improved for --patience superbatches (stopped-early.txt names the best).

use std::{
    fs::{self, File},
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
};

use bullet_trainer::{
    model::{
        DenseInput, ModelDefinition, ModelEvaluator, ModelInputs, ModelInputsMapper, ModelNode, ModelWeights,
        SavedFormat, SparseInput,
    },
    optimiser::adam::{AdamW, AdamWParams},
    reader::{DataReader, ReadMapLoader},
    run::{train, DefaultDevice, HostPool, Step, TrainingSchedule, TrainingSteps},
};
use bulletformat::{BulletFormat, ChessBoard};
use viriformat::dataformat::{Filter, Game};

// Positions are dropped when |score| exceeds Fork's evaluation range
// (EvalLimit, src/eval/eval_scale.hpp): those are mate or tablebase scores.
const MAX_SCORE: u32 = 20000;
const PIECE_SQUARES: usize = 768;
const EXPOSURE_ROWS: usize = 640; // own/enemy x 5 non-king types x 64 squares
const EXPOSURE_FACTORS: usize = 10; // own/enemy x 5 types
// XGR's fixed regions of the mirrored own-king square (cell = rank * 4 +
// file - 4): e1; f1-h1; the second rank; everything from the third rank up.
const XGR_REGIONS: [u8; 32] = [0, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3];
// Fork's game phase (src/core/material.hpp): knights and bishops 1, rooks 2,
// queens 4, capped at 24.
const PHASE_WEIGHT: [usize; 6] = [0, 1, 1, 2, 4, 0];
const FULL_PHASE: usize = 24;

#[derive(Clone, Copy, PartialEq, Debug)]
enum Arch {
    B0,
    S512,
    H512,
    AfS,
    Xgr512,
}

#[derive(Clone, Copy, PartialEq)]
enum Picker {
    None,
    Phase,
}

/// What an architecture's inputs and outputs are.
#[derive(Clone)]
struct Spec {
    arch: Arch,
    hidden: usize,
    mirror: bool,
    regions: [u8; 32],
    region_count: usize,
    factoriser: bool,
    exposure: bool,
    picker: Picker,
    table: Vec<u8>,
    buckets: usize,
}

fn parse_list(text: &str, len: usize, what: &str) -> Vec<u8> {
    let v: Vec<u8> = text.split(',').map(|x| x.trim().parse().unwrap_or_else(|_| panic!("bad {what} entry {x}"))).collect();
    assert_eq!(v.len(), len, "{what} needs {len} entries");
    v
}

impl Spec {
    fn from_args(a: &Args) -> Spec {
        let arch = match a.get("--arch").unwrap_or("b0") {
            "b0" => Arch::B0,
            "s512" => Arch::S512,
            "h512" => Arch::H512,
            "afs" => Arch::AfS,
            "xgr512" => Arch::Xgr512,
            other => panic!("unknown --arch {other}"),
        };
        let mut s = Spec {
            arch,
            hidden: 512,
            mirror: true,
            regions: [0; 32],
            region_count: 1,
            factoriser: false,
            exposure: false,
            picker: Picker::None,
            table: Vec::new(),
            buckets: 1,
        };
        match arch {
            Arch::B0 => {
                s.hidden = 256;
                s.mirror = false;
            }
            Arch::S512 => s.picker = Picker::Phase,
            Arch::H512 | Arch::AfS => {
                let map = parse_list(a.need("--regions"), 32, "--regions");
                s.regions.copy_from_slice(&map);
                s.factoriser = true;
                s.picker = Picker::Phase;
            }
            Arch::Xgr512 => {
                s.regions = XGR_REGIONS;
                s.factoriser = true;
                s.exposure = true;
            }
        }
        s.region_count = usize::from(*s.regions.iter().max().expect("map")) + 1;
        match s.picker {
            Picker::None => {}
            Picker::Phase => s.table = parse_list(a.need("--buckets"), FULL_PHASE + 1, "--buckets"),
        }
        if s.picker != Picker::None {
            // Always 8 outputs; a table may leave one unused (a merged bucket).
            s.buckets = 8;
            assert!(s.table.iter().all(|&b| b < 8), "bucket numbers are 0-7");
        }
        s
    }
    /// First input of the factoriser set, of the exposure rows, and the
    /// total input count.
    fn factor_start(&self) -> usize {
        PIECE_SQUARES * self.region_count
    }
    fn exposure_start(&self) -> usize {
        self.factor_start() + if self.factoriser { PIECE_SQUARES } else { 0 }
    }
    fn inputs(&self) -> usize {
        self.exposure_start() + if self.exposure { EXPOSURE_ROWS + EXPOSURE_FACTORS } else { 0 }
    }
    fn max_active(&self) -> usize {
        32 * (1 + usize::from(self.factoriser)) + if self.exposure { 60 } else { 0 }
    }
    /// Inputs that remain after the factorisers are merged (the saved file).
    fn saved_inputs(&self) -> usize {
        self.factor_start() + if self.exposure { EXPOSURE_ROWS } else { 0 }
    }
}

/// One position seen from the side to move (bulletformat's frame): the
/// type (0 pawn .. 5 king) and side (0 ours, 1 theirs) of each square's
/// piece.
struct Board {
    piece: [Option<(usize, usize)>; 64],
    count: usize,
}

impl Board {
    fn from_chessboard(pos: &ChessBoard) -> Board {
        let mut b = Board { piece: [None; 64], count: 0 };
        for (piece, square) in pos.into_iter() {
            b.piece[usize::from(square)] = Some((usize::from(piece & 7), usize::from(piece & 8 != 0)));
            b.count += 1;
        }
        b
    }
    fn king(&self, side: usize) -> usize {
        (0..64).find(|&s| self.piece[s] == Some((5, side))).expect("a king per side")
    }
    fn phase(&self) -> usize {
        let p: usize = self.piece.iter().flatten().map(|&(t, _)| PHASE_WEIGHT[t]).sum();
        p.min(FULL_PHASE)
    }
    /// The squares a piece on `s` attacks (pseudo-attacks on this
    /// occupancy: sliders stop at the first piece; a side-0 pawn attacks
    /// up the board, a side-1 pawn down).
    fn attacks(&self, s: usize, kind: usize, side: usize) -> u64 {
        let (r, f) = ((s / 8) as i32, (s % 8) as i32);
        let mut out = 0u64;
        let mut add = |rr: i32, ff: i32| {
            if (0..8).contains(&rr) && (0..8).contains(&ff) {
                out |= 1u64 << (rr * 8 + ff);
            }
        };
        match kind {
            0 => {
                let dr = if side == 0 { 1 } else { -1 };
                add(r + dr, f - 1);
                add(r + dr, f + 1);
            }
            1 => {
                for (dr, df) in [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)] {
                    add(r + dr, f + df);
                }
            }
            5 => {
                for (dr, df) in [(1, 1), (1, 0), (1, -1), (0, 1), (0, -1), (-1, 1), (-1, 0), (-1, -1)] {
                    add(r + dr, f + df);
                }
            }
            _ => {
                const ALL: [(i32, i32); 8] = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)];
                let dirs: &[(i32, i32)] = match kind {
                    2 => &ALL[4..],
                    3 => &ALL[..4],
                    _ => &ALL,
                };
                for &(dr, df) in dirs {
                    let (mut rr, mut ff) = (r + dr, f + df);
                    while (0..8).contains(&rr) && (0..8).contains(&ff) {
                        add(rr, ff);
                        if self.piece[(rr * 8 + ff) as usize].is_some() {
                            break;
                        }
                        rr += dr;
                        ff += df;
                    }
                }
            }
        }
        out
    }
    /// XGR's exposure rule: a non-king piece is exposed when an enemy piece
    /// of a lower value class attacks it (pawn < knight = bishop < rook <
    /// queen < king), or when an enemy piece attacks it and none of its own
    /// defends it. Returns a bitboard of exposed squares.
    fn exposed(&self) -> u64 {
        const CLASS: [u8; 6] = [1, 2, 2, 3, 4, 5];
        let mut lowest = [[u8::MAX; 64]; 2]; // lowest attacker class per (attacking side, square)
        let mut hit = [0u64; 2];
        for s in 0..64 {
            if let Some((kind, side)) = self.piece[s] {
                let mut a = self.attacks(s, kind, side);
                hit[side] |= a;
                while a != 0 {
                    let t = a.trailing_zeros() as usize;
                    a &= a - 1;
                    lowest[side][t] = lowest[side][t].min(CLASS[kind]);
                }
            }
        }
        let mut out = 0u64;
        for s in 0..64 {
            if let Some((kind, side)) = self.piece[s] {
                if kind == 5 {
                    continue;
                }
                let enemy = 1 - side;
                let bit = 1u64 << s;
                let attacked_by_lower = lowest[enemy][s] < CLASS[kind];
                let loose = hit[enemy] & bit != 0 && hit[side] & bit == 0;
                if attacked_by_lower || loose {
                    out |= bit;
                }
            }
        }
        out
    }
}

/// The active inputs of one perspective (0: the side to move, 1: the
/// other), written to `out`; returns their count.
fn perspective_features(spec: &Spec, b: &Board, exposed: u64, persp: usize, out: &mut [i32]) -> usize {
    // A perspective's frame: the side to move's as stored; the other's
    // flipped vertically, with "ours" and "theirs" swapped.
    let orient = |sq: usize| if persp == 0 { sq } else { sq ^ 56 };
    let king = orient(b.king(persp));
    let flip = if spec.mirror && king % 8 < 4 { 7 } else { 0 };
    let k = king ^ flip;
    let region = if spec.region_count > 1 { usize::from(spec.regions[(k / 8) * 4 + k % 8 - 4]) } else { 0 };
    let mut n = 0;
    for s in 0..64 {
        let Some((kind, side)) = b.piece[s] else { continue };
        let own = usize::from(side != persp);
        let sq = orient(s) ^ flip;
        let base = 384 * own + 64 * kind + sq;
        out[n] = (PIECE_SQUARES * region + base) as i32;
        n += 1;
        if spec.factoriser {
            out[n] = (spec.factor_start() + base) as i32;
            n += 1;
        }
        if spec.exposure && exposed & (1u64 << s) != 0 {
            let x = spec.exposure_start();
            out[n] = (x + 320 * own + 64 * kind + sq) as i32;
            out[n + 1] = (x + EXPOSURE_ROWS + 5 * own + kind) as i32;
            n += 2;
        }
    }
    n
}

/// The output bucket (or layer stack) of a position.
fn bucket(spec: &Spec, b: &Board) -> usize {
    match spec.picker {
        Picker::None => 0,
        Picker::Phase => usize::from(spec.table[b.phase()]),
    }
}

type Inputs = ModelInputs<(((SparseInput, SparseInput), SparseInput), DenseInput<f32>)>;

fn inputs(spec: &Spec) -> Inputs {
    ModelInputs::default()
        .add_sparse("stm", (spec.inputs(), 1), spec.max_active())
        .add_sparse("ntm", (spec.inputs(), 1), spec.max_active())
        .add_sparse("bucket", (spec.buckets, 1), 1)
        .add_dense("target", (1, 1))
}

/// Clipped values of the first half times those of the second half.
fn pairwise(x: ModelNode<'_>, width: usize) -> ModelNode<'_> {
    let c = x.crelu();
    c.slice_rows(0, width / 2) * c.slice_rows(width / 2, width)
}

fn definition(spec: &Spec, inputs: &Inputs) -> ModelDefinition {
    let s = spec.clone();
    ModelDefinition::build(inputs, move |builder, (((stm, ntm), bucket), target)| {
        let (n, h, nb) = (s.inputs(), s.hidden, s.buckets);
        let output = match s.arch {
            Arch::B0 => {
                let l0 = builder.new_affine("l0", n, h);
                let l1 = builder.new_affine("l1", 2 * h, 1);
                l1.forward(l0.forward(stm).crelu().concat(l0.forward(ntm).crelu()))
            }
            Arch::S512 | Arch::H512 => {
                let l0 = builder.new_affine("l0", n, h);
                let l1 = builder.new_affine("l1", 2 * h, nb);
                l1.forward(l0.forward(stm).screlu().concat(l0.forward(ntm).screlu())).select(bucket)
            }
            Arch::AfS => {
                let l0 = builder.new_affine("l0", n, h);
                let l1 = builder.new_affine("l1", h, 16 * nb);
                let l2 = builder.new_affine("l2", 16, 32 * nb);
                let l3 = builder.new_affine("l3", 32, nb);
                let x = pairwise(l0.forward(stm), h).concat(pairwise(l0.forward(ntm), h));
                let y1 = l1.forward(x).select(bucket).screlu();
                let y2 = l2.forward(y1).select(bucket).screlu();
                l3.forward(y2).select(bucket)
            }
            Arch::Xgr512 => {
                let l0 = builder.new_affine("l0", n, h);
                let s0 = builder.new_affine("s0", n, 3);
                let oa = builder.new_affine("oa", 2 * h, 1);
                let ob = builder.new_affine("ob", 2 * h, 1);
                let hidden = l0.forward(stm).screlu().concat(l0.forward(ntm).screlu());
                let (ss, sn) = (s0.forward(stm), s0.forward(ntm));
                let gate = (ss.slice_rows(0, 1) + sn.slice_rows(0, 1)).crelu();
                let lin_a = (ss.slice_rows(1, 2) - sn.slice_rows(1, 2)) * 2.0;
                let lin_b = (ss.slice_rows(2, 3) - sn.slice_rows(2, 3)) * 2.0;
                let out_a = oa.forward(hidden) + lin_a;
                let out_b = ob.forward(hidden) + lin_b;
                out_b + gate * (out_a - out_b)
            }
        };
        let loss = output.sigmoid().squared_error(target).reduce_sum_batch();
        (Some(loss), vec![("output".to_string(), output)])
    })
}

/// A first-layer weight (rows values per input, input-major as bullet
/// stores it) with its factoriser inputs added into the inputs they share
/// (an f32 addition each, KB bullet-internals.md §1.5) and dropped.
fn merge_factors(spec: &Spec, rows: usize, v: &[f32]) -> Vec<f32> {
    let col = |c: usize| &v[c * rows..(c + 1) * rows];
    let mut out = Vec::with_capacity(rows * spec.saved_inputs());
    for r in 0..spec.region_count {
        for f in 0..PIECE_SQUARES {
            let (a, b) = (col(PIECE_SQUARES * r + f), col(spec.factor_start() + f));
            out.extend(a.iter().zip(b).map(|(x, y)| x + y));
        }
    }
    if spec.exposure {
        let x = spec.exposure_start();
        for e in 0..EXPOSURE_ROWS {
            let (own, kind) = (e / 320, (e % 320) / 64);
            let (a, b) = (col(x + e), col(x + EXPOSURE_ROWS + 5 * own + kind));
            out.extend(a.iter().zip(b).map(|(x, y)| x + y));
        }
    }
    out
}

fn first_layer(spec: &Spec, id: &str, rows: usize) -> SavedFormat {
    let s = spec.clone();
    let f = SavedFormat::id(id);
    if spec.factoriser { f.transform(move |_, v| merge_factors(&s, rows, &v)) } else { f }
}

// The quantized file, in tools/nnue/<arch>.json's order: QA = 255 and QB = 64
// (bullet's convention; ORIGINALITY.md), output biases at QA * QB; AF's small
// layers at 64 (int8) and 8,192 (int16), their biases left in f32 for the
// converter (their scales are not integers).
fn save_list(spec: &Spec) -> Vec<SavedFormat> {
    let h = spec.hidden;
    match spec.arch {
        Arch::B0 => vec![
            SavedFormat::id("l0w").round().quantise::<i16>(255),
            SavedFormat::id("l0b").round().quantise::<i16>(255),
            SavedFormat::id("l1w").round().quantise::<i16>(64),
            SavedFormat::id("l1b").round().quantise::<i32>(255 * 64),
        ],
        Arch::S512 | Arch::H512 => vec![
            first_layer(spec, "l0w", h).round().quantise::<i16>(255),
            SavedFormat::id("l0b").round().quantise::<i16>(255),
            SavedFormat::id("l1w").transpose().round().quantise::<i16>(64),
            SavedFormat::id("l1b").round().quantise::<i32>(255 * 64),
        ],
        Arch::AfS => vec![
            first_layer(spec, "l0w", h).round().quantise::<i16>(255),
            SavedFormat::id("l0b").round().quantise::<i16>(255),
            SavedFormat::id("l1w").transpose().round().quantise::<i8>(64),
            SavedFormat::id("l1b"),
            SavedFormat::id("l2w").transpose().round().quantise::<i16>(8192),
            SavedFormat::id("l2b"),
            SavedFormat::id("l3w").transpose().round().quantise::<i16>(8192),
            SavedFormat::id("l3b"),
        ],
        Arch::Xgr512 => vec![
            first_layer(spec, "l0w", h).round().quantise::<i16>(255),
            SavedFormat::id("l0b").round().quantise::<i16>(255),
            first_layer(spec, "s0w", 3).round().quantise::<i16>(255),
            SavedFormat::id("s0b").round().quantise::<i16>(255),
            SavedFormat::id("oaw").round().quantise::<i16>(64),
            SavedFormat::id("oab").round().quantise::<i32>(255 * 64),
            SavedFormat::id("obw").round().quantise::<i16>(64),
            SavedFormat::id("obb").round().quantise::<i32>(255 * 64),
        ],
    }
}

/// Per-tensor weight clips: the first layer and its factorisers at +-0.99
/// each, so a merged weight stays within 1.98 (judgement.md §1.1, §4); every
/// other tensor at bullet's default +-1.98.
fn clipped(spec: &Spec) -> Vec<&'static str> {
    match spec.arch {
        Arch::B0 | Arch::S512 => vec![],
        Arch::H512 | Arch::AfS => vec!["l0w", "l0b"],
        Arch::Xgr512 => vec!["l0w", "l0b", "s0w", "s0b"],
    }
}

/// The inputs of one position, as the mapper fills them; returns the
/// bucket.
fn fill(spec: &Spec, pos: &ChessBoard, stm: &mut [i32], ntm: &mut [i32]) -> usize {
    let b = Board::from_chessboard(pos);
    let exposed = if spec.exposure { b.exposed() } else { 0 };
    for (persp, out) in [(0, &mut *stm), (1, &mut *ntm)] {
        let n = perspective_features(spec, &b, exposed, persp, out);
        // Pooled batch buffers are reused uncleared: end short lists (KB §13).
        if n < out.len() {
            out[n] = -1;
        }
    }
    bucket(spec, &b)
}

fn mapper(spec: &Spec, inputs: &Inputs, scale: f32, result_weight: f32) -> ModelInputsMapper<ChessBoard> {
    let s = spec.clone();
    ModelInputsMapper::build(inputs, move |pos: &ChessBoard, _step: Step, (((stm, ntm), bucket), target)| {
        bucket[0] = fill(&s, pos, stm, ntm) as i32;
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

/// Shuffles `buf` with `rng` and hands it to `f` in chunks; true once `f`
/// asks to stop.
fn emit_shuffled<F: FnMut(&[ChessBoard]) -> bool>(buf: &mut Vec<ChessBoard>, rng: &mut SplitMix, f: &mut F) -> bool {
    for i in (1..buf.len()).rev() {
        buf.swap(i, (rng.next() % (i as u64 + 1)) as usize);
    }
    for chunk in buf.chunks(16384) {
        if f(chunk) {
            return true;
        }
    }
    buf.clear();
    false
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
                        stop = emit_shuffled(&mut buf, &mut rng, &mut f);
                    }
                });
                if stop {
                    return;
                }
            }
            // The end of a pass over every file: flush the partial buffer, so
            // data smaller than one buffer still trains (a test dataset).
            if !buf.is_empty() && emit_shuffled(&mut buf, &mut rng, &mut f) {
                return;
            }
        }
    }
}

/// The kept positions of a shard (the training filter), at most `limit`.
fn read_positions(path: &Path, limit: usize) -> Vec<ChessBoard> {
    let mut out = Vec::new();
    let filter = filter();
    ShardReader::for_each_game(path, |game| {
        if out.len() < limit {
            game.splat_to_bulletformat(
                |b| {
                    out.push(b);
                    Ok(())
                },
                &filter,
            )
            .expect("splat");
        }
    });
    out.truncate(limit);
    out
}

fn pieces_text(b: &ChessBoard) -> String {
    let pieces: Vec<String> = b.into_iter().map(|(p, s)| format!("{p}:{s}")).collect();
    pieces.join(" ")
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
        eprintln!("usage: fork-train check|dump|stats|features|train|eval|loader ... (see the source header)");
        std::process::exit(2);
    };
    let a = Args(argv);
    let needs_spec = !matches!(cmd.as_str(), "dump" | "stats" | "loader");
    let spec = if needs_spec { Spec::from_args(&a) } else { Spec::from_args(&Args(Vec::new())) };
    let ins = inputs(&spec);
    match cmd.as_str() {
        "check" => {
            // The graph builds and the save list matches it: the quantized
            // file of the initial weights (B0: 394,756 bytes of tensors,
            // padded to 64).
            let defn = definition(&spec, &ins);
            let weights = ModelWeights::new(&defn, a.num("--seed", 1));
            let bytes = weights.to_quantised_buffer(&save_list(&spec), true).expect("quantise");
            let out = PathBuf::from(a.need("--out"));
            fs::create_dir_all(&out).expect("out");
            fs::write(out.join("quantised.bin"), &bytes).expect("write");
            let mut wf = File::create(out.join("weights.bin")).expect("weights.bin");
            weights.write_into(&mut wf).expect("write weights");
            println!("{:?}: {} inputs, quantised.bin {} bytes", spec.arch, spec.inputs(), bytes.len());
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
                            writeln!(out, "{} | {} | {}", pieces_text(&b), b.score(), b.result()).unwrap();
                        }
                        Ok(())
                    },
                    &filter,
                )
                .expect("splat");
            });
        }
        "stats" => {
            // Histograms of the kept positions for fitting the maps: the
            // mirrored own-king cell of both perspectives (rank * 4 + file - 4),
            // the game phase and the piece count.
            let limit: usize = a.num("--positions", usize::MAX);
            let (mut kings, mut phase, mut pieces, mut n) = ([0u64; 32], [0u64; FULL_PHASE + 1], [0u64; 33], 0usize);
            for f in a.all("--data") {
                let filter = filter();
                ShardReader::for_each_game(Path::new(&f), |game| {
                    game.splat_to_bulletformat(
                        |pos: ChessBoard| {
                            if n < limit {
                                n += 1;
                                let b = Board::from_chessboard(&pos);
                                for persp in 0..2 {
                                    let k = if persp == 0 { b.king(0) } else { b.king(1) ^ 56 };
                                    let k = if k % 8 < 4 { k ^ 7 } else { k };
                                    kings[(k / 8) * 4 + k % 8 - 4] += 1;
                                }
                                phase[b.phase()] += 1;
                                pieces[b.count] += 1;
                            }
                            Ok(())
                        },
                        &filter,
                    )
                    .expect("splat");
                });
            }
            let join = |v: &[u64]| v.iter().map(u64::to_string).collect::<Vec<_>>().join(" ");
            println!("positions {n}");
            println!("kings {}", join(&kings));
            println!("phase {}", join(&phase));
            println!("pieces {}", join(&pieces));
        }
        "features" => {
            // The feature leg (DESIGN.md §5.3, deliverable 6): each position's
            // active inputs per perspective (sorted) and its bucket, as the
            // mapper computes them. "FEN-or-pieces | stm ... | ntm ... | bucket".
            let mut boards: Vec<(String, ChessBoard)> = Vec::new();
            if let Some(epd) = a.get("--epd") {
                for line in BufReader::new(File::open(epd).expect("epd")).lines() {
                    let fen = line.expect("line").trim().to_string();
                    if !fen.is_empty() && !fen.starts_with('#') {
                        let b: ChessBoard = format!("{fen} | 0 | 0.0").parse().expect("fen");
                        boards.push((fen, b));
                    }
                }
            } else {
                for b in read_positions(Path::new(a.need("--data")), a.num("--count", 1000)) {
                    boards.push((pieces_text(&b), b));
                }
            }
            let out = std::io::stdout();
            let mut out = out.lock();
            let (mut stm, mut ntm) = (vec![0i32; spec.max_active()], vec![0i32; spec.max_active()]);
            for (text, b) in &boards {
                stm.fill(-1);
                ntm.fill(-1);
                let k = fill(&spec, b, &mut stm, &mut ntm);
                let list = |v: &[i32]| {
                    let mut x: Vec<i32> = v.iter().copied().filter(|&i| i >= 0).collect();
                    x.sort_unstable();
                    x.iter().map(i32::to_string).collect::<Vec<_>>().join(" ")
                };
                writeln!(out, "{text} | {} | {} | {k}", list(&stm), list(&ntm)).unwrap();
            }
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
            let defn = definition(&spec, &ins);
            let weights = ModelWeights::new(&defn, a.num("--seed", 1));
            let device = DefaultDevice::new(a.num("--device", 0)).expect("device");
            let pool = HostPool::new(device.clone());
            let mut opt = AdamW::new(defn, weights, device.clone(), AdamWParams::default()).expect("optimiser");
            for id in clipped(&spec) {
                opt.set_params_for_weight(id, AdamWParams { min_weight: -0.99, max_weight: 0.99, ..AdamWParams::default() });
            }
            let val: Vec<ChessBoard> =
                a.get("--val").map(|p| read_positions(Path::new(p), a.num("--val-positions", 20_000))).unwrap_or_default();
            let patience: usize = a.num("--patience", 3);
            let val_map = mapper(&spec, &ins, scale, result_weight);
            let mut best: Option<(f64, usize)> = None;
            if let Some(dir) = a.get("--resume") {
                let state = Path::new(dir).join("optimiser_state");
                opt.load_from_checkpoint(state.to_str().expect("path")).expect("resume");
            }
            // Validation: mean squared error of sigmoid(output) against the
            // same target as training. bullet's evaluator is compiled for one
            // position at a time (ModelEvaluator::new lowers the graph at
            // batch 1). A macro, so the warm start and the per-superbatch
            // callback share it without naming the optimiser's types.
            macro_rules! validation_loss {
                ($opt:expr) => {{
                    let mut evaluator = ModelEvaluator::new($opt.definition(), $opt.device()).expect("evaluator");
                    evaluator.load_device_weights($opt.weights()).expect("weights");
                    let mut total = 0.0f64;
                    for pos in &val {
                        let batch = val_map.map(&pool, std::slice::from_ref(pos), Step::default(), 1).expect("map");
                        let expected = 1.0 / (1.0 + (-f32::from(pos.score()) / scale).exp());
                        let target = (1.0 - result_weight) * expected + result_weight * pos.result();
                        let batch = batch.to_device(&device).expect("device");
                        let out = evaluator.evaluate(&batch).expect("eval").get("output").expect("output");
                        let host = out.to_host().expect("host");
                        let p = 1.0 / (1.0 + (-f64::from(host.f32()[0])).exp());
                        total += (p - f64::from(target)).powi(2);
                    }
                    total / val.len() as f64
                }};
            }
            // A warm start (--init-weights): an earlier net's float weights
            // (train_b0.py keeps the best checkpoint's), AdamW's moments
            // fresh. Its validation loss is superbatch 0 in val.txt and the
            // first best, so a run that never beats it stops after --patience.
            if let Some(file) = a.get("--init-weights") {
                opt.load_weights_from_file(file).expect("init weights");
                if !val.is_empty() {
                    let loss = validation_loss!(opt);
                    fs::create_dir_all(&out).expect("out");
                    fs::write(out.join("val.txt"), format!("0 {loss:.8}\n")).expect("val.txt");
                    println!("superbatch 0 (initial weights) validation loss {loss:.8}");
                    best = Some((loss, 0));
                }
            }
            // --superbatches below --start: only the initial validation.
            if end < start {
                return;
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
            let loader = ReadMapLoader::new(reader, mapper(&spec, &ins, scale, result_weight), a.num("--threads", 3));
            let net_id = a.get("--id").unwrap_or("b0").to_string();
            let saves = save_list(&spec);
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
                    let bytes = opt.cpu_weights().expect("weights").to_quantised_buffer(&saves, true).expect("quantise");
                    fs::write(dir.join("quantised.bin"), bytes).expect("quantised.bin");
                    fs::write(dir.join("superbatch.txt"), format!("{}\n", step.superbatch())).expect("superbatch.txt");
                    if val.is_empty() {
                        return;
                    }
                    let loss = validation_loss!(opt);
                    let sb = step.superbatch();
                    let mut log = fs::OpenOptions::new().create(true).append(true).open(out.join("val.txt")).expect("val.txt");
                    writeln!(log, "{sb} {loss:.8}").expect("val.txt");
                    println!("superbatch {sb} validation loss {loss:.8}");
                    if best.is_none_or(|(b, _)| loss < b) {
                        best = Some((loss, sb));
                    }
                    let (b, bsb) = best.expect("best");
                    if sb >= bsb + patience {
                        fs::write(out.join("stopped-early.txt"), format!("best superbatch {bsb} loss {b:.8}\n"))
                            .expect("stopped-early.txt");
                        println!("stopping early: best superbatch {bsb}");
                        std::process::exit(0);
                    }
                },
            )
            .expect("train");
        }
        "eval" => {
            // The trainer's own float evaluation of each FEN (parity leg T):
            // the raw output, side to move's view, before the sigmoid.
            let defn = definition(&spec, &ins);
            let weights = ModelWeights::new(&defn, 1);
            let device = DefaultDevice::new(a.num("--device", 0)).expect("device");
            let mut opt = AdamW::new(defn, weights, device.clone(), AdamWParams::default()).expect("optimiser");
            // A checkpoint folder, or (--weights) just a float weights file,
            // as train_b0.py keeps for the best checkpoint.
            if let Some(file) = a.get("--weights") {
                opt.load_weights_from_file(file).expect("load weights");
            } else {
                let state = Path::new(a.need("--checkpoint")).join("optimiser_state");
                opt.load_from_checkpoint(state.to_str().expect("path")).expect("load");
            }
            let mut evaluator = ModelEvaluator::new(opt.definition(), opt.device()).expect("evaluator");
            evaluator.load_device_weights(opt.weights()).expect("weights");
            let map = mapper(&spec, &ins, 1.0, 0.0);
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
        "loader" => {
            // K17: how fast one thread decodes and filters Fork's shards.
            let limit: usize = a.num("--positions", 2_000_000);
            let start = std::time::Instant::now();
            let mut n = 0usize;
            for f in a.all("--data") {
                n += read_positions(Path::new(&f), limit - n).len();
                if n >= limit {
                    break;
                }
            }
            let secs = start.elapsed().as_secs_f64();
            println!("loader: {n} kept positions in {secs:.2} s, {:.0} positions/s on one thread", n as f64 / secs);
        }
        _ => {
            eprintln!("unknown command {cmd}");
            std::process::exit(2);
        }
    }
}
