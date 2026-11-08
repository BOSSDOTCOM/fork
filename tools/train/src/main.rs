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
//! - s512x: s512 plus XGR's exposure inputs (640 and their 10-input
//!   factoriser, merged when saved; owner, 2026-11-02: XGR's parts as add-ons
//!   to S512r2, the exposure plane first); the output as s512's.
//! - s512cl: s512 plus Fork's contact and pawn-link inputs (ideas.md 41;
//!   DESIGN.md §5.4, "S512cl"; no exposure plane): 50,416 contacts (a
//!   non-king piece attacking another, not both pawns, of a mutual pair only
//!   the cheaper attacker's) and 1,488 links (two pawns on the same or
//!   adjacent files), after the 768 piece inputs; the output as s512's.
//! - s512pp: s512 plus the pawn links only, of pawns at most one rank apart
//!   (S512+PP; ideas.md 40; owner, 2026-11-06): 608 links after the 768
//!   piece inputs, numbered as S512cl's in their own space; the output as
//!   s512's.
//! - refiner: the Boundary Refiner (ideas.md 59, step 3;
//!   docs/research/boundary-refiner/step3-plan.md 2.2-2.5, 3.6-3.7) on
//!   S512ppr3's frozen first layer, the engine net's own integers read as
//!   floats (--base-weights NET.fnet: each int / 255; owner, 2026-11-08):
//!   each perspective's 512 sums clipped to [0, 1] and detached (no gradient;
//!   decay 0 and a wide clip keep them bit for bit), the side to move's first
//!   -> 8, plus the active rows (640 exposure rows from the side to move's
//!   view with their 10-row factoriser, 8 phase rows, 16 evaluation bins) ->
//!   32 -> 2 heads (the correction, the confidence), clipped ReLU, the dense
//!   weights clipped to [-1, 1]. Data: .sites files (tools/nnue/refiner.py
//!   export), the sites of weight 0 left out. Loss: weight x (sigmoid(base /
//!   S + correction) - sigmoid((label - mu) / S))^2, base the engine's
//!   integer evaluation, mu the training file's weighted mean of label -
//!   base (written to mu.txt; never added back in the engine). The
//!   confidence head stays zero here (its pass is 3.7's second run).
//! The target is (1 - w) * sigmoid(score / S) + w * result, w the weight on
//! the game result (DESIGN.md's lambda is 1 - w).
//!
//!   fork-train check    --arch A [maps] --out DIR
//!   fork-train order    --data SHARD... [--count N]   (the file of each game of an --interleave pass)
//!   fork-train dump     --data SHARD --count N
//!   fork-train stats    --data SHARD... [--positions N]   (king squares, phase, piece counts)
//!   fork-train features --arch A [maps] (--epd FILE | --data SHARD --count N)
//!   fork-train train    --arch A [maps] --data SHARD... --out DIR --scale S [--val SHARD --patience P]
//!                       [--init-weights weights.bin] [options]
//!   fork-train eval     --arch A [maps] (--checkpoint DIR | --weights weights.bin) --epd FILE --out FILE
//!   fork-train loader   --data SHARD... [--positions N]   (decoding speed, one thread)
//!   fork-train check    --arch refiner --base-weights NET.fnet --out DIR
//!   fork-train train    --arch refiner --base-weights NET.fnet --sites FILE [--val-sites FILE] --out DIR
//!                       --scale S [--superbatches 80 --lr 0.001 --lr-step 40 --patience 8 --batch 16384]
//!   fork-train eval     --arch refiner --base-weights NET.fnet --weights weights.bin --sites FILE --out FILE
//! --qat (train, eval, check; the S-512 family): quantization-aware training
//! (ideas.md 44), the forward pass on the integer file's weight grid.
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
    io::{BufRead, BufReader, Seek, Write},
    path::{Path, PathBuf},
    str::FromStr,
    sync::Arc,
};

use bullet_trainer::{
    model::{
        DenseInput, InitSettings, ModelDefinition, ModelEvaluator, ModelInputs, ModelInputsMapper, ModelNode,
        ModelWeights, SavedFormat, SparseInput,
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
    S512x,
    S512cl,
    S512pp,
    Refiner,
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
    contacts: bool,
    /// S512+PP's links of rank limit PP_LINK_RANKS (no contacts).
    links: bool,
    /// --qat: quantization-aware training (the S-512 family; ideas.md 44).
    qat: bool,
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
            "s512x" => Arch::S512x,
            "s512cl" => Arch::S512cl,
            "s512pp" => Arch::S512pp,
            "refiner" => Arch::Refiner,
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
            contacts: false,
            links: false,
            qat: a.0.iter().any(|x| x == "--qat"),
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
            Arch::S512x => {
                s.exposure = true;
                s.picker = Picker::Phase;
            }
            Arch::S512cl => {
                s.contacts = true;
                s.picker = Picker::Phase;
            }
            Arch::S512pp => {
                s.links = true;
                s.picker = Picker::Phase;
            }
            // The refiner's base inputs are S512+PP's; its own output picks no bucket.
            Arch::Refiner => s.links = true,
        }
        s.region_count = usize::from(*s.regions.iter().max().expect("map")) + 1;
        assert!(!s.qat || matches!(arch, Arch::S512 | Arch::H512 | Arch::S512x | Arch::S512cl | Arch::S512pp), "--qat: the S-512 family only");
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
    /// First contact input, first link input (S512cl: right after the
    /// piece inputs).
    fn contact_start(&self) -> usize {
        self.factor_start()
    }
    fn link_start(&self) -> usize {
        self.contact_start() + if self.contacts { contact_tables().contacts } else { 0 }
    }
    fn contact_inputs(&self) -> usize {
        if self.contacts { contact_tables().contacts + contact_tables().links } else { 0 }
    }
    /// S512+PP's link inputs.
    fn pp_link_inputs(&self) -> usize {
        if self.links { rank_links().links } else { 0 }
    }
    fn inputs(&self) -> usize {
        self.exposure_start() + if self.exposure { EXPOSURE_ROWS + EXPOSURE_FACTORS } else { 0 } + self.contact_inputs()
            + self.pp_link_inputs()
    }
    /// At most 8 contacts per non-king piece (8 rays or knight squares) and
    /// a link per pair of the 16 pawns.
    fn max_active(&self) -> usize {
        32 * (1 + usize::from(self.factoriser))
            + if self.exposure { 60 } else { 0 }
            + if self.contacts { 30 * 8 + 120 } else { 0 }
            + if self.links { 64 } else { 0 }
    }
    /// Inputs that remain after the factorisers are merged (the saved file).
    fn saved_inputs(&self) -> usize {
        self.factor_start() + if self.exposure { EXPOSURE_ROWS } else { 0 } + self.contact_inputs() + self.pp_link_inputs()
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

// S512cl's contact and link inputs (DESIGN.md §5.4, "S512cl"): a class is
// side * 5 + kind (side 0 the perspective's own, kinds pawn .. queen);
// squares are frame squares. The index space is enumerated in one fixed
// order (tools/nnue/contacts.py and the engine build the same).
const CLASS_KINDS: usize = 5;
const KIND_VALUE: [u8; 5] = [1, 2, 2, 3, 4];

struct ContactTables {
    /// [attacker class][attacker square][target square][victim class], -1 when impossible.
    contact: Vec<i32>,
    /// [pawn slot][pawn slot] (slot = side * 48 + square - 8), -1 when not a link.
    link: Vec<i32>,
    contacts: usize,
    links: usize,
}

fn contact_slot(att: usize, a: usize, b: usize, vic: usize) -> usize {
    ((att * 64 + a) * 64 + b) * (2 * CLASS_KINDS) + vic
}

fn link_slot(i: usize, j: usize) -> usize {
    i * 96 + j
}

/// Whether a contact can be active in some position (b in the attacker's
/// empty-board reach from a): kings and pawn-pawn left out, pawns only on
/// ranks 2-7, of one kind only the lower attacker square, and the mutual
/// pairs whose dearer attacker's input is never kept.
fn contact_possible(att: usize, a: usize, b: usize, vic: usize) -> bool {
    let (sa, ka) = (att / CLASS_KINDS, att % CLASS_KINDS);
    let (sv, kv) = (vic / CLASS_KINDS, vic % CLASS_KINDS);
    let _ = sa;
    let middle = |s: usize| (8..56).contains(&s);
    let line = a % 8 == b % 8 || a / 8 == b / 8;
    let diagonal = (a % 8).abs_diff(b % 8) == (a / 8).abs_diff(b / 8);
    if (ka == 0 && !middle(a)) || (kv == 0 && !middle(b)) || (ka == 0 && kv == 0) {
        return false;
    }
    if ka == kv && a > b {
        return false;
    }
    if ka == 4 && ((kv == 3 && line) || (kv == 2 && diagonal)) {
        return false;
    }
    let empty = Board { piece: [None; 64], count: 0 };
    if (ka == 2 || ka == 4) && kv == 0 && empty.attacks(b, 0, sv) & (1u64 << a) != 0 {
        return false;
    }
    true
}

fn contact_tables() -> &'static ContactTables {
    static TABLES: std::sync::OnceLock<ContactTables> = std::sync::OnceLock::new();
    TABLES.get_or_init(|| {
        let empty = Board { piece: [None; 64], count: 0 };
        let mut contact = vec![-1i32; 2 * CLASS_KINDS * 64 * 64 * 2 * CLASS_KINDS];
        let mut contacts = 0usize;
        for att in 0..2 * CLASS_KINDS {
            for a in 0..64 {
                let mut reach = empty.attacks(a, att % CLASS_KINDS, att / CLASS_KINDS);
                while reach != 0 {
                    let b = reach.trailing_zeros() as usize;
                    reach &= reach - 1;
                    for vic in 0..2 * CLASS_KINDS {
                        if contact_possible(att, a, b, vic) {
                            contact[contact_slot(att, a, b, vic)] = contacts as i32;
                            contacts += 1;
                        }
                    }
                }
            }
        }
        let mut link = vec![-1i32; 96 * 96];
        let mut links = 0usize;
        for i in 0..96usize {
            for j in i + 1..96 {
                let (qi, qj) = (i % 48 + 8, j % 48 + 8);
                if qi != qj && (qi % 8).abs_diff(qj % 8) <= 1 {
                    link[link_slot(i, j)] = links as i32;
                    links += 1;
                }
            }
        }
        ContactTables { contact, link, contacts, links }
    })
}

/// S512+PP's link space: S512cl's pairs of pawn slots whose squares are at
/// most PP_LINK_RANKS ranks apart, numbered in the same order.
const PP_LINK_RANKS: usize = 1;

struct RankLinks {
    /// [pawn slot][pawn slot], -1 when not a link.
    link: Vec<i32>,
    links: usize,
}

fn rank_links() -> &'static RankLinks {
    static TABLE: std::sync::OnceLock<RankLinks> = std::sync::OnceLock::new();
    TABLE.get_or_init(|| {
        let mut link = vec![-1i32; 96 * 96];
        let mut links = 0usize;
        for i in 0..96usize {
            for j in i + 1..96 {
                let (qi, qj) = (i % 48 + 8, j % 48 + 8);
                if qi != qj && (qi % 8).abs_diff(qj % 8) <= 1 && (qi / 8).abs_diff(qj / 8) <= PP_LINK_RANKS {
                    link[link_slot(i, j)] = links as i32;
                    links += 1;
                }
            }
        }
        RankLinks { link, links }
    })
}

/// S512+PP's link inputs of one perspective (numbers within the link block),
/// appended to `links`; `frame` and `own` as contact_features's.
fn pp_link_features(b: &Board, frame: impl Fn(usize) -> usize, own: impl Fn(usize) -> usize, links: &mut Vec<usize>) {
    let t = rank_links();
    let mut pawns: Vec<usize> = (0..64)
        .filter_map(|s| match b.piece[s] {
            Some((0, side)) => Some(own(side) * 48 + frame(s) - 8),
            _ => None,
        })
        .collect();
    pawns.sort_unstable();
    for (n, &i) in pawns.iter().enumerate() {
        for &j in &pawns[n + 1..] {
            let l = t.link[link_slot(i, j)];
            if l >= 0 {
                links.push(l as usize);
            }
        }
    }
}

/// A perspective's contact and link inputs (numbers within each block),
/// appended to `contacts` and `links`; `frame` maps a stored square to the
/// perspective's frame square, `own` a stored side to the relative one.
fn contact_features(
    b: &Board,
    frame: impl Fn(usize) -> usize,
    own: impl Fn(usize) -> usize,
    contacts: &mut Vec<usize>,
    links: &mut Vec<usize>,
) {
    let t = contact_tables();
    let mut pawns: Vec<usize> = Vec::new();
    for s in 0..64 {
        let Some((kind, side)) = b.piece[s] else { continue };
        if kind == 5 {
            continue;
        }
        if kind == 0 {
            pawns.push(own(side) * 48 + frame(s) - 8);
        }
        let mut hit = b.attacks(s, kind, side);
        while hit != 0 {
            let v = hit.trailing_zeros() as usize;
            hit &= hit - 1;
            let Some((vkind, vside)) = b.piece[v] else { continue };
            if vkind == 5 || (kind == 0 && vkind == 0) {
                continue;
            }
            // Of two pieces attacking each other, only the cheaper attacker's
            // input (of one kind, the lower attacker frame square's).
            if b.attacks(v, vkind, vside) & (1u64 << s) != 0
                && (KIND_VALUE[vkind] < KIND_VALUE[kind] || (vkind == kind && frame(v) < frame(s)))
            {
                continue;
            }
            let i = t.contact[contact_slot(own(side) * CLASS_KINDS + kind, frame(s), frame(v), own(vside) * CLASS_KINDS + vkind)];
            assert!(i >= 0, "an active contact outside the index space");
            contacts.push(i as usize);
        }
    }
    pawns.sort_unstable();
    for (n, &i) in pawns.iter().enumerate() {
        for &j in &pawns[n + 1..] {
            let l = t.link[link_slot(i, j)];
            if l >= 0 {
                links.push(l as usize);
            }
        }
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
    if spec.contacts {
        let (mut c, mut l) = (Vec::with_capacity(64), Vec::with_capacity(32));
        contact_features(b, |sq| orient(sq) ^ flip, |side| usize::from(side != persp), &mut c, &mut l);
        for i in c {
            out[n] = (spec.contact_start() + i) as i32;
            n += 1;
        }
        for i in l {
            out[n] = (spec.link_start() + i) as i32;
            n += 1;
        }
    }
    if spec.links {
        let mut l = Vec::with_capacity(64);
        pp_link_features(b, |sq| orient(sq) ^ flip, |side| usize::from(side != persp), &mut l);
        for i in l {
            out[n] = (spec.link_start() + i) as i32;
            n += 1;
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
            Arch::S512 | Arch::H512 | Arch::S512x | Arch::S512cl | Arch::S512pp => {
                let l0 = builder.new_affine("l0", n, h);
                let l1 = builder.new_affine("l1", 2 * h, nb);
                if s.qat {
                    // Quantization-aware training (ideas.md 44; KB nnue-design.md
                    // §5.6): the forward pass uses each weight and bias rounded to
                    // the grid Fork's integer file stores it on (save_list's
                    // factors: 255 for the first layer, 64 for the output
                    // weights, 255 x 64 for their biases), so the loss is the
                    // quantized network's; the gradient passes the rounding
                    // unchanged (a straight-through estimate).
                    let (w0, b0) = (l0.weights.faux_quantise(255.0, true), l0.bias.faux_quantise(255.0, true));
                    let (w1, b1) = (l1.weights.faux_quantise(64.0, true), l1.bias.faux_quantise(255.0 * 64.0, true));
                    let (a_s, a_n) = (w0.matmul(stm) + b0, w0.matmul(ntm) + b0);
                    (w1.matmul(a_s.screlu().concat(a_n.screlu())) + b1).select(bucket)
                } else {
                    l1.forward(l0.forward(stm).screlu().concat(l0.forward(ntm).screlu())).select(bucket)
                }
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
            Arch::Refiner => unreachable!("the refiner builds its own graph (main)"),
        };
        let loss = output.sigmoid().squared_error(target).reduce_sum_batch();
        (Some(loss), vec![("output".to_string(), output)])
    })
}

/// A first-layer weight (rows values per input, input-major as bullet
/// stores it) with its factoriser inputs added into the inputs they share
/// (an f32 addition each, KB bullet-internals.md §1.5) and dropped; an
/// architecture without the piece factoriser keeps its piece inputs as they
/// are.
fn merge_factors(spec: &Spec, rows: usize, v: &[f32]) -> Vec<f32> {
    let col = |c: usize| &v[c * rows..(c + 1) * rows];
    let mut out = Vec::with_capacity(rows * spec.saved_inputs());
    for r in 0..spec.region_count {
        for f in 0..PIECE_SQUARES {
            let a = col(PIECE_SQUARES * r + f);
            if spec.factoriser {
                out.extend(a.iter().zip(col(spec.factor_start() + f)).map(|(x, y)| x + y));
            } else {
                out.extend_from_slice(a);
            }
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
    if spec.factoriser || spec.exposure { f.transform(move |_, v| merge_factors(&s, rows, &v)) } else { f }
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
        Arch::S512 | Arch::H512 | Arch::S512x | Arch::S512cl | Arch::S512pp => vec![
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
        // The refiner's file is written by tools/nnue/refiner.py convert.
        Arch::Refiner => Vec::new(),
    }
}

/// Per-tensor weight clips: the first layer and its factorisers at +-0.99
/// each, so a merged weight stays within 1.98 (judgement.md §1.1, §4); every
/// other tensor at bullet's default +-1.98. S512x and S512cl keep S-512's rule (no
/// first-layer clip: a warm start from S512r2 must not move its weights; Fork
/// sums its exposure rows in 32 bits, so their size needs no bound).
fn clipped(spec: &Spec) -> Vec<&'static str> {
    match spec.arch {
        Arch::B0 | Arch::S512 | Arch::S512x | Arch::S512cl | Arch::S512pp | Arch::Refiner => vec![],
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
/// with a seeded stream (so the data order is reproducible). With
/// `interleave` (--interleave; owner, 2026-11-06: the endgame slice spread
/// through the snapshot), each pass reads the files side by side instead,
/// one game at a time from the file furthest behind in the share of its
/// bytes read, so every file is spread evenly over the pass.
#[derive(Clone)]
struct ShardReader {
    files: Vec<PathBuf>,
    buffer: usize,
    seed: u64,
    interleave: bool,
}

/// The next file of an interleaved pass: of the files not finished, the one
/// whose share read (read / size) is smallest, the lower index on ties.
fn interleave_next(read: &[u64], size: &[u64], done: &[bool]) -> Option<usize> {
    let mut best: Option<usize> = None;
    for k in 0..read.len() {
        if done[k] {
            continue;
        }
        // read[k] / size[k] < read[b] / size[b], without division.
        if best.map_or(true, |b| (read[k] as u128) * (size[b] as u128) < (read[b] as u128) * (size[k] as u128)) {
            best = Some(k);
        }
    }
    best
}

/// One interleaved pass over `files`: `f(file index, game)` for every game,
/// in interleave_next's order; stops early when `f` returns true.
fn for_each_interleaved(files: &[PathBuf], mut f: impl FnMut(usize, Game) -> bool) {
    let mut readers: Vec<BufReader<File>> = files
        .iter()
        .map(|p| BufReader::new(File::open(p).unwrap_or_else(|e| panic!("{}: {e}", p.display()))))
        .collect();
    let size: Vec<u64> = files.iter().map(|p| fs::metadata(p).expect("size").len().max(1)).collect();
    let mut read = vec![0u64; files.len()];
    let mut done = vec![false; files.len()];
    while let Some(k) = interleave_next(&read, &size, &done) {
        let r = &mut readers[k];
        if r.fill_buf().expect("read").is_empty() {
            done[k] = true;
            continue;
        }
        let game = Game::deserialise_from(r, Vec::new())
            .unwrap_or_else(|e| panic!("{}: undecodable game: {e}", files[k].display()));
        read[k] = r.stream_position().expect("position");
        if f(k, game) {
            return;
        }
    }
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

/// One labelled site of a .sites file (tools/nnue/refiner.py export,
/// "FEN | base | label | weight | rows"): the position, the engine's integer
/// base evaluation and the deep label (cp, side to move's view), the training
/// weight, and the refiner's active rows in its file's order (at most 32 in
/// architecture 1; -1 ends a shorter list).
#[derive(Clone, Copy)]
struct SiteRecord(ChessBoard, i16, i16, f32, [i16; 32]);

impl FromStr for SiteRecord {
    type Err = String;
    fn from_str(line: &str) -> Result<Self, Self::Err> {
        let f: Vec<&str> = line.split(" | ").collect();
        if f.len() != 5 {
            return Err(format!("not a site line: {line}"));
        }
        let pos: ChessBoard = format!("{} | 0 | 0.0", f[0]).parse().map_err(|e| format!("{e:?}: {line}"))?;
        let num = |x: &str| x.trim().parse::<i16>().map_err(|_| format!("bad number {x}: {line}"));
        let mut rows = [-1i16; 32];
        for (k, r) in f[4].split_whitespace().enumerate() {
            *rows.get_mut(k).ok_or(format!("more than 32 rows: {line}"))? = num(r)?;
        }
        let weight = f[3].trim().parse::<f32>().map_err(|_| format!("bad weight: {line}"))?;
        Ok(SiteRecord(pos, num(f[1])?, num(f[2])?, weight, rows))
    }
}

/// The training sites, held in memory and served forever, each pass in a
/// seeded shuffle (Fork's splitmix64), as the shard reader serves positions.
#[derive(Clone)]
struct SiteLoader(Arc<Vec<SiteRecord>>, u64);

impl DataReader<SiteRecord> for SiteLoader {
    fn read_chunks<F: FnMut(&[SiteRecord]) -> bool>(&self, _skip_count: usize, mut f: F) {
        let mut rng = SplitMix(self.1);
        let mut order: Vec<SiteRecord> = self.0.as_ref().clone();
        loop {
            for i in (1..order.len()).rev() {
                order.swap(i, (rng.next() % (i as u64 + 1)) as usize);
            }
            for chunk in order.chunks(16384) {
                if f(chunk) {
                    return;
                }
            }
        }
    }
}

impl DataReader<ChessBoard> for ShardReader {
    fn read_chunks<F: FnMut(&[ChessBoard]) -> bool>(&self, _skip_count: usize, mut f: F) {
        let mut rng = SplitMix(self.seed);
        let mut buf = Vec::with_capacity(self.buffer);
        let filter = filter();
        loop {
            if self.interleave {
                let mut stop = false;
                for_each_interleaved(&self.files, |_, game| {
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
                    stop
                });
                if stop {
                    return;
                }
                if !buf.is_empty() && emit_shuffled(&mut buf, &mut rng, &mut f) {
                    return;
                }
                continue;
            }
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
    if spec.arch == Arch::Refiner {
        // The Boundary Refiner (the header): its own inputs, graph, data and loss.
        let (n, h) = (spec.inputs(), spec.hidden);
        let l1 = 8; // the entry layer's width: the 8-wide shape (step3-plan.md 4.5; owner, 2026-11-08)
        let row_count = EXPOSURE_ROWS + EXPOSURE_FACTORS + 8 + 16; // then the phase rows and the evaluation bins
        // The frozen base: the engine's net file (64-byte header, 128-byte map
        // block, then the first layer i16 [inputs][hidden] and its biases i16
        // [hidden]), each integer / 255, as bullet's weights records.
        let net = fs::read(a.need("--base-weights")).expect("--base-weights");
        let field = |at: usize| u32::from_le_bytes(net[at..at + 4].try_into().expect("header"));
        assert!(net.len() > 64 + 128 + 2 * (n + 1) * h && &net[..8] == b"FORKNET\0", "--base-weights: not a Fork net file");
        assert_eq!((field(12), field(16) as usize, field(20) as usize), (8, n, h), "--base-weights: an S512+PP net file");
        let net_scale = field(32) as i32;
        let at = 64 + 128;
        let int16 = |i: usize| f32::from(i16::from_le_bytes([net[at + 2 * i], net[at + 2 * i + 1]]));
        let mut base_file = Vec::new();
        for (name, start, count) in [("l0w", 0, n * h), ("l0b", n * h, h)] {
            base_file.extend_from_slice(name.as_bytes());
            base_file.push(b'\n');
            base_file.extend_from_slice(&(count as u64).to_le_bytes());
            for i in start..start + count {
                base_file.extend_from_slice(&(int16(i) / 255.0).to_le_bytes());
            }
        }
        let rins = ModelInputs::default()
            .add_sparse("stm", (n, 1), spec.max_active())
            .add_sparse("ntm", (n, 1), spec.max_active())
            .add_sparse("rows", (row_count, 1), 64)
            .add_dense("target", (1, 1))
            .add_dense("weight", (1, 1))
            .add_dense("base", (1, 1));
        let defn = ModelDefinition::build(&rins, move |builder, (((((stm, ntm), rows), target), weight), base)| {
            let normal = |fan_in: usize| InitSettings::Normal { mean: 0.0, stdev: (2.0 / fan_in as f32).sqrt() };
            let w0 = builder.new_weights("l0w", (h, n), InitSettings::Zeroed);
            let b0 = builder.new_weights("l0b", (h, 1), InitSettings::Zeroed);
            let x = (w0.matmul(stm) + b0).crelu().detach().concat((w0.matmul(ntm) + b0).crelu().detach());
            let ew = builder.new_weights("entry_weights", (l1, 2 * h), normal(2 * h));
            let eb = builder.new_weights("entry_bias", (l1, 1), InitSettings::Zeroed);
            let rw = builder.new_weights("row_weights", (l1, row_count), InitSettings::Zeroed);
            let a1 = (ew.matmul(x) + rw.matmul(rows) + eb).crelu();
            let mw = builder.new_weights("middle_weights", (32, l1), normal(l1));
            let mb = builder.new_weights("middle_bias", (32, 1), InitSettings::Zeroed);
            let a2 = (mw.matmul(a1) + mb).crelu();
            let hw = builder.new_weights("head_weights", (2, 32), InitSettings::Zeroed);
            let hb = builder.new_weights("head_bias", (2, 1), InitSettings::Zeroed);
            let y = hw.matmul(a2) + hb;
            let loss = ((base + y.slice_rows(0, 1)).sigmoid().squared_error(target) * weight).reduce_sum_batch();
            (Some(loss), vec![("output".to_string(), y)])
        });
        let mut weights = ModelWeights::new(&defn, a.num("--seed", 1));
        weights.load_from(&base_file[..]).expect("base weights");
        let read_sites = |path: &str, all: bool| -> Vec<SiteRecord> {
            BufReader::new(File::open(path).unwrap_or_else(|_| panic!("cannot read {path}")))
                .lines()
                .map(|l| l.expect("line").parse::<SiteRecord>().unwrap_or_else(|e| panic!("{e}")))
                .filter(|s| all || s.3 > 0.0)
                .collect()
        };
        let scale: f32 = a.num("--scale", net_scale as f32);
        assert_eq!(scale as i32, net_scale, "--scale differs from the base net's S");
        let device = DefaultDevice::new(a.num("--device", 0)).expect("device");
        let pool = HostPool::new(device.clone());
        let mapper_for = |mu: f32| {
            let sp = spec.clone();
            ModelInputsMapper::build(&rins, move |s: &SiteRecord, _step: Step, (((((stm, ntm), rows), target), weight), base)| {
                fill(&sp, &s.0, stm, ntm);
                let mut k = 0;
                for &r in s.4.iter().take_while(|&&r| r >= 0) {
                    let r = r as usize;
                    if r < EXPOSURE_ROWS {
                        rows[k] = r as i32;
                        rows[k + 1] = (EXPOSURE_ROWS + r / 64) as i32; // its own/enemy x type factoriser row
                        k += 2;
                    } else {
                        rows[k] = (r + EXPOSURE_FACTORS) as i32;
                        k += 1;
                    }
                }
                if k < rows.len() {
                    rows[k] = -1;
                }
                target[0] = 1.0 / (1.0 + (-(f32::from(s.2) - mu) / scale).exp());
                weight[0] = s.3;
                base[0] = f32::from(s.1) / scale;
            })
        };
        match cmd.as_str() {
            "check" => {
                // The graph builds and the frozen base loads: the initial weights.
                let out = PathBuf::from(a.need("--out"));
                fs::create_dir_all(&out).expect("out");
                weights.write_into(&mut File::create(out.join("weights.bin")).expect("weights.bin")).expect("write");
                println!("refiner: base {n} x {h} (S {net_scale}), entry {l1}, rows {row_count}, middle 32, heads 2");
                // The training graph (forward and backward, the per-sample weight
                // included) lowers without a device; running it needs CUDA (Kaggle).
                defn.lower_backward(&Default::default(), a.num("--batch", 16384), false, false).expect("backward graph");
                println!("backward graph lowered at batch {}", a.num("--batch", 16384));
            }
            "train" => {
                let sites = read_sites(a.need("--sites"), false);
                let wsum: f64 = sites.iter().map(|s| f64::from(s.3)).sum();
                let mu = sites.iter().map(|s| f64::from(s.3) * (f64::from(s.2) - f64::from(s.1))).sum::<f64>() / wsum;
                let out = PathBuf::from(a.need("--out"));
                fs::create_dir_all(&out).expect("out");
                fs::write(out.join("mu.txt"), format!("{mu:.6}\n")).expect("mu.txt");
                println!("{} training sites, weight {wsum:.1}; mu = {mu:.3} cp (the target is centred on it)", sites.len());
                let rmap = mapper_for(mu as f32);
                let val = a.get("--val-sites").map(|p| read_sites(p, false)).unwrap_or_default();
                let mut opt = AdamW::new(defn, weights, device.clone(), AdamWParams::default()).expect("optimiser");
                // The frozen base: no gradient reaches it (detach), and decay 0 and a
                // clip wider than its values leave AdamW's update at zero.
                for id in ["l0w", "l0b"] {
                    opt.set_params_for_weight(id, AdamWParams { decay: 0.0, min_weight: -1000.0, max_weight: 1000.0, ..AdamWParams::default() });
                }
                // The dense weights' bound, |w| <= 1.0 (64 in the file; plan 2.5).
                for id in ["entry_weights", "middle_weights"] {
                    opt.set_params_for_weight(id, AdamWParams { min_weight: -1.0, max_weight: 1.0, ..AdamWParams::default() });
                }
                // Validation: the weighted loss on --val-sites, as training's.
                macro_rules! validation_loss {
                    ($opt:expr) => {{
                        let mut evaluator = ModelEvaluator::new($opt.definition(), $opt.device()).expect("evaluator");
                        evaluator.load_device_weights($opt.weights()).expect("weights");
                        let (mut total, mut base_total, mut wv) = (0.0f64, 0.0f64, 0.0f64);
                        for s in &val {
                            let batch = rmap.map(&pool, std::slice::from_ref(s), Step::default(), 1).expect("map");
                            let batch = batch.to_device(&device).expect("device");
                            let y = evaluator.evaluate(&batch).expect("eval").get("output").expect("output").to_host().expect("host");
                            let b = f64::from(s.1) / f64::from(scale);
                            let t = 1.0 / (1.0 + (-(f64::from(s.2) - mu) / f64::from(scale)).exp());
                            let p = 1.0 / (1.0 + (-(b + f64::from(y.f32()[0]))).exp());
                            let w = f64::from(s.3);
                            total += w * (p - t).powi(2);
                            base_total += w * (1.0 / (1.0 + (-b).exp()) - t).powi(2);
                            wv += w;
                        }
                        (total / wv, base_total / wv)
                    }};
                }
                let patience: usize = a.num("--patience", 8);
                let mut best: Option<(f64, usize)> = None;
                if !val.is_empty() {
                    // A1 (plan 3.8): with the correction head at zero the loss is the base's own.
                    let (loss, base_loss) = validation_loss!(opt);
                    fs::write(out.join("val.txt"), format!("0 {loss:.10}\n")).expect("val.txt");
                    println!("superbatch 0 validation loss {loss:.10}, the base's own {base_loss:.10} (difference {:.2e})", loss - base_loss);
                    best = Some((loss, 0));
                }
                let lr: f32 = a.num("--lr", 0.001);
                let end: usize = a.num("--superbatches", 80);
                let lr_step: usize = a.num("--lr-step", (end / 2).max(1));
                let batch: usize = a.num("--batch", 16384);
                let schedule = TrainingSchedule {
                    steps: TrainingSteps {
                        batch_size: batch,
                        batches_per_superbatch: a.num("--batches", sites.len().div_ceil(batch)),
                        start_superbatch: 1,
                        end_superbatch: end,
                    },
                    lr_schedule: Box::new(move |step: Step| lr * 0.1f32.powi(((step.superbatch() - 1) / lr_step) as i32)),
                    log_rate: 16,
                    track_grad_norms: false,
                };
                let loader = ReadMapLoader::new(SiteLoader(Arc::new(sites), a.num("--seed", 1)), rmap.clone(), a.num("--threads", 3));
                train(
                    &mut opt,
                    schedule,
                    loader,
                    |_, step, loss| println!("superbatch {} batch {} loss {loss}", step.superbatch(), step.batch()),
                    |opt, step| {
                        let sb = step.superbatch();
                        let dir = out.join(format!("refiner-{sb}"));
                        let state = dir.join("optimiser_state");
                        fs::create_dir_all(&state).expect("checkpoint folder");
                        opt.write_to_checkpoint(state.to_str().expect("path")).expect("write checkpoint");
                        fs::write(dir.join("superbatch.txt"), format!("{sb}\n")).expect("superbatch.txt");
                        if val.is_empty() {
                            return;
                        }
                        let (loss, _) = validation_loss!(opt);
                        let mut log = fs::OpenOptions::new().create(true).append(true).open(out.join("val.txt")).expect("val.txt");
                        writeln!(log, "{sb} {loss:.10}").expect("val.txt");
                        println!("superbatch {sb} validation loss {loss:.10}");
                        if best.is_none_or(|(b, _)| loss < b) {
                            best = Some((loss, sb));
                        }
                        let (b, bsb) = best.expect("best");
                        if sb >= bsb + patience {
                            fs::write(out.join("stopped-early.txt"), format!("best superbatch {bsb} loss {b:.10}\n"))
                                .expect("stopped-early.txt");
                            println!("stopping early: best superbatch {bsb}");
                            std::process::exit(0);
                        }
                    },
                )
                .expect("train");
            }
            "eval" => {
                // The trainer's float outputs for every site of --sites (the parity
                // chain's trainer leg): the correction and the confidence heads, raw.
                let sites = read_sites(a.need("--sites"), true);
                let rmap = mapper_for(0.0);
                let mut opt = AdamW::new(defn, weights, device.clone(), AdamWParams::default()).expect("optimiser");
                opt.load_weights_from_file(a.need("--weights")).expect("weights");
                let mut evaluator = ModelEvaluator::new(opt.definition(), opt.device()).expect("evaluator");
                evaluator.load_device_weights(opt.weights()).expect("weights");
                let mut out = File::create(a.need("--out")).expect("out");
                for s in &sites {
                    let batch = rmap.map(&pool, std::slice::from_ref(s), Step::default(), 1).expect("map");
                    let batch = batch.to_device(&device).expect("device");
                    let y = evaluator.evaluate(&batch).expect("eval").get("output").expect("output").to_host().expect("host");
                    writeln!(out, "{} {}", y.f32()[0], y.f32()[1]).expect("write");
                }
            }
            other => panic!("--arch refiner: check, train or eval, not {other}"),
        }
        return;
    }
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
        "order" => {
            // The source file of each of the first --count games of one
            // interleaved pass (--interleave's order), one index per line.
            let files: Vec<PathBuf> = a.all("--data").into_iter().map(PathBuf::from).collect();
            let mut left: usize = a.num("--count", 1000);
            let out = std::io::stdout();
            let mut out = out.lock();
            for_each_interleaved(&files, |k, _| {
                writeln!(out, "{k}").unwrap();
                left -= 1;
                left == 0
            });
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
                interleave: a.0.iter().any(|x| x == "--interleave"),
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

#[cfg(test)]
mod interleave_tests {
    use super::interleave_next;

    #[test]
    fn the_file_furthest_behind_comes_next() {
        // A 2% file beside a 98% one: about one game in 50 from it, spread
        // evenly, and both finish together.
        let size = [9800u64, 200];
        let mut read = [0u64, 0];
        let done = [false, false];
        let mut order = Vec::new();
        for _ in 0..500 {
            let k = interleave_next(&read, &size, &done).unwrap();
            read[k] += 10;
            order.push(k);
        }
        let small: Vec<usize> = order.iter().enumerate().filter(|&(_, &k)| k == 1).map(|(i, _)| i).collect();
        assert_eq!(small.len(), 10);
        assert!(small.windows(2).all(|w| w[1] - w[0] == 50), "{small:?}");
    }

    #[test]
    fn finished_files_are_skipped_and_ties_take_the_lower_index() {
        assert_eq!(interleave_next(&[0, 0], &[10, 10], &[false, false]), Some(0));
        assert_eq!(interleave_next(&[5, 0], &[10, 10], &[false, true]), Some(0));
        assert_eq!(interleave_next(&[5, 5], &[10, 10], &[true, true]), None);
    }
}
