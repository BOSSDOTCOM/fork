# The networks side by side

Clean-room network survey of 2026-11-14 ([README](README.md)). One row per engine, condensed
from the group records; the detail, the sources and every UNVERIFIED item are in the record
the "Rec." column links to. Ranks are CCRL Blitz, all engines, best versions, computed
2026-11-14.

## 1. How to read the tables

- Each cell describes the **rated version's** network. Changes after it are in the record
  under "Since the rated version"; a few are noted here in brackets.
- "KB" is king input buckets. "768 x 16 KB" means 768 piece-square inputs in each of 16 king
  buckets. "Mirrored" means the board is flipped left to right so the own king is always on
  one half.
- "Pairwise" means the clipped accumulator is split in two halves that are multiplied element
  by element, which halves the next layer's input.
- "a -> b -> 1" lists the layers after the accumulator. "None" means the accumulator feeds the
  output directly, as in Fork.
- "Not published" means no page the agent could open states it. "UNVERIFIED" carries the
  agent's reason in the record. Nothing here was read from source code.
- No quantisation scale, clipping bound or trainer setting is recorded.
- **Fork, for comparison** (architecture 8, S512+PP, net r8ceplo2): 768 mirrored piece inputs
  (no king buckets) plus 608 pawn links (pairs of pawns at most one rank apart); accumulator
  512; no further layers; 8 outputs picked by game phase; SCReLU; int16 throughout; about
  1.80 B saved positions, about 1.17 B after the training filter (docs/research/
  network-novelty-2026-11-14.md, E13; UNVERIFIED for the newest parts), own self-play with
  20,000-node labels.

## 2. The tables

### 2.1 Inputs

| # | Engine | Rec. | Piece inputs and king buckets | Threat inputs | Pawn inputs | Other |
|---|---|---|---|---|---|---|
| 1 | Stockfish 19 (SFNNv16) | [A](records/group-a.md) | 22,528 = 32 KB (one per mirrored king square) x 64 x 11, mirrored (king onto files e-h); factoriser in training | 59,808 (non-king to non-king, no x-rays, mutual duplicates removed, pawn-pawn removed in v16); int8 rows | 4,560 pawn pairs (same or adjacent files); int8 rows | PSQT path (8 outputs); total 86,896 inputs |
| 2 | Triumviratus 8.1 | [B](records/group-b.md) | king-relative 704 x 32 KB (Stockfish's mirrored set) x 8 material "experts" per perspective (chosen by the opponent's non-pawn material through a stored table); base + per-expert delta factoriser | 59,808 (Stockfish's full threat block), int8 rows | 4,560 pawn pairs; 96 passed-pawn inputs; pawn-king subnet 256 -> 256 -> 32 added into the head | material routing (the experts); PSQT output kept |
| 3 | Torch v4 | [A](records/group-a.md) | not published for v4 (v2: mirrored HalfKA, 22,528 per perspective) | not published | not published | not published |
| 4 | Obsidian 16.0 | [B](records/group-b.md) | not published for 16.0 (768 x 4 KB mirrored in 2024-03) | none published | not published | not published |
| 5 | PlentyChess 8.0.0 | [B](records/group-b.md) | 768 x 12 KB, mirrored; factoriser | 79,856 at introduction; king and pawn-to-pawn threats removed for 8.0.0 (count not published); int8 rows; separate accumulator in 8.0.0 | pawn pairs (three-file mask) | none published |
| 6 | Coda 0.9.4 | [B](records/group-b.md) | 768 x 16 KB, mirrored (d/e line) | 66,864 with king-attacker threats or 60,144 without (the net declares which; production nets match 66,864 by file-size arithmetic); int8 rows; x-ray threats removed in 0.9.3 | none (pawn pairs in 0.9.5) | none |
| 7 | Reckless 0.9.0 | [B](records/group-b.md) | 768 x 10 KB, mirrored | 79,856 at introduction (2025-12); piece-to-king threats removed 2026-02 | none stated | none |
| 8 | Gaia 4.4.1 | [C](records/group-c.md) | 768 x 12 KB (mirroring not stated for this net) | 59,808 "filtered piece-interaction" inputs; int8 rows | 4,560 pawn pairs; int8 rows | PSQT head |
| 9-10 | Berserk 20250606 | [C](records/group-c.md) | 768 x 16 KB, mirrored (12,288 per perspective) | none (added 2026-10) | none | none |
| 9-10 | Cinder 0.6.1 | [C](records/group-c.md) | 768 x 16 KB, mirrored | added 2026-08 (count not published) | pawn-pawn inputs added 2026-08 (count not published) | none |
| 11 | Dragon by Komodo 3.2 | [A](records/group-a.md) | not published | not published | not published | not published |
| 12-13 | Alexandria 8.0.0 | [C](records/group-c.md) | 768 x 16 KB, mirrored | none (added after) | none (added after) | none |
| 12-13 | pawnocchio 2.0 | [C](records/group-c.md) | 768 x 16 KB, mirrored (at the last published string; 2.0 UNVERIFIED) | yes (count only in code) | "masked pawn-pawn inputs", the author's invention (count not published) | none |
| 14 | Integral 8 | [C](records/group-c.md) | (768 + 11 fifty-move inputs) x 12 KB, mirrored, factorised | 60,144, separate accumulator | none (pawn pairs after v8) | 11 half-move-clock inputs per bucket |
| 15-16 | Caissa 2.0 | [D](records/group-d.md) | 768 x 32 KB, mirrored; factoriser | none | none | none |
| 15-16 | Viridithas 20.0.0 | [D](records/group-d.md) | 704 x 16 KB, mirrored (merged king planes); factoriser dropped 2025-11 | 59,808 (no king threats) | 4,560 pawn-pawn | none |
| 17 | Stormphrax 8.0.0 | [D](records/group-d.md) | 704 x 16 KB, mirrored | 60,144 (no king threats), own accumulator | pawn-pawn (count not stated) | none |
| 18 | Hobbes 3.0 | [D](records/group-d.md) | 768 x 16 KB, mirrored (king planes merged in the file) | 60,144 | none (pawn pairs after 3.0) | none |
| 19 | Horsie 1.1.0 | [D](records/group-d.md) | 768 x 14 KB; factoriser (merged) | none | none | none |
| 20 | Lizard 11.2 | [D](records/group-d.md) | 768 x 14 KB; factoriser (merged) | none | none | none |
| 21-22 | Astra 7.0 | [E](records/group-e.md) | 768 x KB; count in 7.0 UNVERIFIED (13 in the 2025-12 net, one more bucket net 2026-04) | none mentioned | none mentioned | none |
| 21-22 | Raphael 4.2.0 | [E](records/group-e.md) | 768 x 16 KB (704 after merging king planes), mirrored | 60,144 (based on Stormphrax's) | none | none |
| 23 | Incipit 0.6.0 | [B](records/group-b.md) | 768 x 16 KB, mirrored (king on files e-h); factorised when introduced | 56,890 (by file-size arithmetic; variants of 56,218 and 54,090 exist), int8 rows shared by all buckets | pawn pairs, 608-input window (pawns at most one rank apart), int8 rows | none |
| 24-26 | RubiChess 20240817 | [E](records/group-e.md) | HalfKAv2_hm (Stockfish's mirrored king-relative set, one block per mirrored king square) | none (added after) | none | none |
| 24-26 | Starzix 6.0 | [E](records/group-e.md) | 768 x 2 (mirror) x 5 enemy-queen buckets | none | none | enemy-queen input buckets |
| 24-26 | Tarnished 6.0 | [E](records/group-e.md) | 768 x 16 KB, mirrored | none | none | none |
| 27 | Clover 9.1 | [E](records/group-e.md) | 768 x 7 KB; mirroring not restated; factoriser | none | none | none |
| 28 | Ethereal 14.25 | [A](records/group-a.md) | HalfKP, mirrored (20,480 by arithmetic; kings excluded) | none | none | none |
| 29 | Fritz 20 | [H](records/group-h.md) | not published | not published | not published | not published |
| 30 | Halogen 16.0.0 | [E](records/group-e.md) | 768 x 8 KB, mirrored | none (added twelve days after) | none | none |
| 31 | Quanticade Cronus 3.0 | [F](records/group-f.md) | 768 x 13 KB, mirrored | none (added after) | none named | not published |
| 32 | Igel 3.8.0 | [F](records/group-f.md) | 22,528 = HalfKAv2_hm, 32 mirrored KB (README; it may not track the rated net) | 60,144 (FullThreats) | none named | 8 PSQT buckets |
| 33 | PZChessBot 7.1 | [F](records/group-f.md) | 768 x 12 KB, mirrored | none (added after) | none | none |
| 34 | ZigQueen 6.5.0 | [F](records/group-f.md) | 768 x 16 KB (mirrored HalfKA; king on files e-h mirrored); 768-row factoriser | 60,144 (attacker, square, victim, square; kings never victims; both directions of a mutual attack kept); int8 rows | 1,488 pawn-pair rows (1,278 live): pawns on the same or adjacent files; int8 rows | PSQT head |
| 35 | Devre 7.0 | [F](records/group-f.md) | 768 x 12 KB, mirrored | none (added after) | 4,560 pawn pairs | none |
| 36 | JustBot 0.5.0 | [F](records/group-f.md) | 768 x 4 KB, mirrored | none | none | none |
| 37-38 | Titan 1.1.0 | [F](records/group-f.md) | king-bucketed, mirrored (count not published) | none | none | none |
| 37-38 | Velvet 8.1.0 | [G](records/group-g.md) | 768 x 32 KB (kept since 6.0.0: UNVERIFIED); mirroring not published; always evaluates from White's view by colour flip | none | none | material routing ("piece-combination" buckets) dropped at 6.0.0 for more king buckets |
| 39 | Minke 7.0.0 | [G](records/group-g.md) | 768 x 16 KB, mirrored | none | none | none |
| 40-41 | Ginkgo Santiago 1.0 | [H](records/group-h.md) | not published | not published | not published | not published |
| 40-41 | Revenge 4.0 | [H](records/group-h.md) | not published ("pure neural network", "new and bigger" than 3.0) | not published | not published | not published |
| 42 | Tcheran 14.0 | [G](records/group-g.md) | 768 x 8 KB, mirrored | none | none | none |
| 43-44 | Seer 2.8.0 | [G](records/group-g.md) | HalfKA (own king square x piece x square) | none | none | none |
| 43-44 | Uralochka 3.41a | [G](records/group-g.md) | 12,288 per perspective = 16 king areas x 6 x 2 x 64; mirroring not published | none | none | none |
| 45 | Lc0 0.29.0 w753723 (GPU, not NNUE) | [H](records/group-h.md) | 112 planes of 8x8 (8 positions of history, castling, clocks) | none as inputs | none | history planes |
| 46 | Motor 0.9.0 | [G](records/group-g.md) | 768 x 8 KB, mirrored | none | none | none |
| 47-49 | Chess System Tal 3.00 | [H](records/group-h.md) | not published | not published | not published | not published |
| 47-49 | Renegade 1.3.0 | [G](records/group-g.md) | 768 x 14 KB, mirrored; factoriser | none | none | none |
| 47-49 | Stoofvlees II b5 (GPU, not NNUE) | [H](records/group-h.md) | not published | not published | not published | not published |
| 50 | Rebel 17.0 | [H](records/group-h.md) | not published (same net as 16.3) | not published | not published | not published |
| 51 | rofChade 3.1 | [H](records/group-h.md) | "(2x768)x8x1"; inputs not restated (3.0 was HalfKA) | none stated | none stated | none stated |

### 2.2 Body, activations and quantisation

| # | Engine | Accumulator per perspective | Layers after it | Stacks and output buckets | Activations | Quantisation |
|---|---|---|---|---|---|---|
| 1 | Stockfish 19 (SFNNv16) | 1024, pairwise (-> 512 per perspective) | 1024 -> 32 -> 32 -> 1 with skip paths (output reads both hidden layers; two L1 outputs feed the result) | 8 stacks by (piece count - 1) / 4 | CReLU + pairwise; dual activation (squared + plain CReLU) after both hidden layers | int16 accumulator and piece rows; int8 threat and pair rows; int8 dense layers; no float; QAT since 2026-05 |
| 2 | Triumviratus 8.1 | 1024, pairwise | 32 -> 32 -> 1 (Stockfish's SFNNv16 head) | 8 stacks by piece count | clipped + pairwise; head "as in Stockfish" | every FT row int8 (8.1); stacks int8; trained with the int8 clamp |
| 3 | Torch v4 | 2560 (v2, 2024-03; "currently", 2025-07); v4 UNVERIFIED | not published (a sparse first dense layer implied) | not published | not published | not published |
| 4 | Obsidian 16.0 | not published (1280 in 2024-05), pairwise since 2024-08 | multi-layer since 15.0, widths not published | 8 output buckets (selector not published) | pairwise CReLU; head not published | not published |
| 5 | PlentyChess 8.0.0 | 640 (1792 before threats) | 16 -> 32 -> 1 | 8 whole heads by piece count | not published (pairwise implied) | int8 threat rows; head not published |
| 6 | Coda 0.9.4 | 1024, pairwise | 16 (dual) -> 32 -> 1, shared by all buckets | output buckets by material (count not published); no stacks in 0.9.4 | pairwise; dual activation on the 16-wide layer | int16 piece rows, int8 threat rows, int8 first hidden layer, float after (README and notes disagree) |
| 7 | Reckless 0.9.0 | 384 at the threat merge (1024 before); 0.9.0's width UNVERIFIED | 16 -> 32 -> 1 | none in the published string (8 output buckets seen after 0.9.0) | pairwise CReLU -> CReLU -> CReLU | int8 first dense layer, float after |
| 8 | Gaia 4.4.1 | 1024, paired SCReLU | 16 -> 32 -> 1 | 8 material-based | paired SCReLU; head not published | int16 piece rows, int8 auxiliary rows; QAT in the rated net's recipe |
| 9-10 | Berserk 20250606 | 1024 | 16 -> 32 -> 1 | none stated | CReLU (8-bit clipped); head not published | int16 accumulator, 8-bit outputs into the sparse first dense layer, int16 head |
| 9-10 | Cinder 0.6.1 | "4096/2" (width per perspective UNVERIFIED), pairwise implied | four layers: 16x2 -> 16x2 -> 16x2 -> 1, with a residual branch to the output | 8 (selector not published) | not published | not published (two quantisation scales) |
| 11 | Dragon by Komodo 3.2 | not published | not published | not published | not published | not published |
| 12-13 | Alexandria 8.0.0 | 1536 | none | 8 output buckets (selector not published) | SCReLU | int16 activation arithmetic |
| 12-13 | pawnocchio 2.0 | 2048 at the last published string; 2.0's width only in code | 16 -> 32 -> 1 | 8 (selector not published) | pairwise; dual activation after the first dense layer | "fully quantised" (types only in code) |
| 14 | Integral 8 | 768 (1536 before threats) | 16 -> 32 -> 1 | 8, one head per bucket (selector not published) | not published | not published |
| 15-16 | Caissa 2.0 | 1536, pairwise | 16 -> 32 -> 1 | 8 whole heads by piece count | CReLU + pairwise; CReLU in head | int16 FT; int8 both hidden layers; QAT on every layer |
| 15-16 | Viridithas 20.0.0 | 1024, pairwise | 32 -> 32x2 -> 1, residual across layer 2 | 8 by piece count | CReLU + pairwise; hard-Swish, SwiGLU | int8 first dense layer; float after it |
| 17 | Stormphrax 8.0.0 | 640, pairwise | 32x2 -> 32 -> 1, skip across layer 2 | 8 (selector not published) | CReLU + pairwise; dual activation | all integer (widths not published) |
| 18 | Hobbes 3.0 | 768 | 16x2 -> 32 -> 1 | 8 (selector not published) | dual activation in head; pairwise UNVERIFIED for threat nets | not published |
| 19 | Horsie 1.1.0 | 2048, pairwise | 16 -> 32 -> 1 | 8 by material count | CReLU + pairwise; head not published | int8 first dense layer ("utilitarian" double precision) |
| 20 | Lizard 11.2 | 2048, pairwise | 16 -> 32 -> 1 | 8 by material count | CReLU + pairwise; head not published | int8 first dense layer |
| 21-22 | Astra 7.0 | 1536 (2025-12 net; 7.0 UNVERIFIED) | 16 -> 32 -> 1 (2025-12 net) | 8 (selector not stated) | SCReLU after the accumulator; CReLU in head | not published |
| 21-22 | Raphael 4.2.0 | 768, pairwise (1280 before threats, 512 at the threat merge) | 32 -> 32 -> 1 | 8 (selector not stated) | pairwise; SCReLU then CReLU in head (dual activation tried, failed) | all integer (three scales) |
| 23 | Incipit 0.6.0 | 1024, pairwise | 16 -> 16 -> 1, per output bucket; a linear "pre-activation readout" to the output | 6 by piece count (steps of six pieces) | pairwise; SCReLU in head | int16 piece rows; int8 threat and pair rows; int8 first hidden layer (QAT); float after |
| 24-26 | RubiChess 20240817 | not restated (last stated 1024) | 32 -> 32 -> 1 (Stockfish "SFv5" layout, per the author) | UNVERIFIED | not published | not published |
| 24-26 | Starzix 6.0 | 1024 | none | none | SCReLU (4.0; not restated) | not published |
| 24-26 | Tarnished 6.0 | 1792 | 16 -> 32 -> 1 (README writes 16 -> 32 -> 32) | 8 (selector not stated) | SCReLU (2.0; not restated); dual activation in head | not published |
| 27 | Clover 9.1 | last stated 1280 (9.1 UNVERIFIED) | none published | not stated | SCReLU | not published |
| 28 | Ethereal 14.25 | 768 | 8 -> 32 -> 1 | none | ReLU-type; head not stated | int16 accumulator; 8-bit first dense layer; float later layers (as of 13.00) |
| 29 | Fritz 20 | not published | not published | not published | not published | not published |
| 30 | Halogen 16.0.0 | 1536, pairwise | 16 -> 32 -> 1 | 8 (selector not stated) | pairwise; dual activation in head | not published (VNNI 8-bit dot product in use) |
| 31 | Quanticade Cronus 3.0 | 1536 (no pairwise marker) | 16 -> 32 -> 1 | 8 (selector not published) | SCReLU on the second and third layers | not published |
| 32 | Igel 3.8.0 | 1024 | 16 -> 32 -> 1 | 8 output buckets (selector not published) | UNVERIFIED (only in code) | not published |
| 33 | PZChessBot 7.1 | 1280, pairwise | 16 -> 32 -> 1 | 8 by material | pairwise; one SCReLU in the head | not published (part of the head is float) |
| 34 | ZigQueen 6.5.0 | 1024, pairwise | 16 -> 32 -> 1 | 8 stacks by material | CReLU + pairwise; SCReLU after the first dense layer | int16 piece rows; int8 threat and pair rows; int8 first dense layer; all integer; QAT of every layer |
| 35 | Devre 7.0 | 1024, pairwise | 16 -> 32 -> 1 | 8 by material | pairwise; head not published | not published |
| 36 | JustBot 0.5.0 | 1024 | none | output buckets (count not published) | UNVERIFIED (only in code) | not published (file size fits int16 rows) |
| 37-38 | Titan 1.1.0 | not published | none (single layer) | not published | SCReLU | not published |
| 37-38 | Velvet 8.1.0 | 1024 | none (single layer; extra layers removed in 3.2.0 for speed) | none | clipped ReLU (inferred) | 8-bit input-layer weights since 8.1.0 |
| 39 | Minke 7.0.0 | 1280, pairwise | 16x2 -> 32 -> 1 | 8 (selector not published) | pairwise; dual activation (CReLU + SCReLU) on the 16-wide layer | quantised (types not published) |
| 40-41 | Ginkgo Santiago 1.0 | not published | not published | not published | not published | not published |
| 40-41 | Revenge 4.0 | not published | not published | not published | not published | not published |
| 42 | Tcheran 14.0 | 1024 (no pairwise) | 16 -> 32 -> 1 | 8 by remaining material | SCReLU after the accumulator; dual activation in the head | not published |
| 43-44 | Seer 2.8.0 | width UNVERIFIED (only in code; 2x1024 after the rated version) | float head with dense concatenating skip connections; widths not published | 3 outputs (win, draw, loss) | not published | quantised feature transformer; float after |
| 43-44 | Uralochka 3.41a | 1024 | none | 6 output buckets (selector not published) | not published | not published |
| 45 | Lc0 0.29.0 w753723 (GPU, not NNUE) | residual tower, 15 blocks x 192 filters, squeeze-and-excitation | policy head (1858 moves), value head (win, draw, loss), moves-left head | none | ReLU (T75's UNVERIFIED) | float (fp16 optional) |
| 46 | Motor 0.9.0 | 1536 | none | none | SCReLU | not published |
| 47-49 | Chess System Tal 3.00 | not published (a "1024" token in the net's name, UNVERIFIED) | not published | not published | not published | not published |
| 47-49 | Renegade 1.3.0 | 1600 | none | 8 by piece count | SCReLU | quantised (types not published) |
| 47-49 | Stoofvlees II b5 (GPU, not NNUE) | deep convolutional net, sizes not published | not published | not published | not published | not published |
| 50 | Rebel 17.0 | not published | not published | not published | not published | not published |
| 51 | rofChade 3.1 | 768 | 8 -> 1 | none | not published | not published |

### 2.3 Training data

| # | Engine | Size and type |
|---|---|---|
| 1 | Stockfish 19 (SFNNv16) | "hundreds of billions" (800+ GB); Lc0 data relabelled by Lc0's BT4 |
| 2 | Triumviratus 8.1 | about 700 GB, roughly 270 B positions; Lc0 and Stockfish data relabelled by Lc0's BT4 |
| 3 | Torch v4 | size not published; mixed, v4 unknown (some versions partly on Lc0 data) |
| 4 | Obsidian 16.0 | size not published; Lc0 data |
| 5 | PlentyChess 8.0.0 | 15 B+; own self-play plus games against Stockfish (own-side positions); "self-distillation" for part |
| 6 | Coda 0.9.4 | "hundreds of billions"; Lc0 data scored by Lc0's BT4, plus CC0 Kaggle data and some own |
| 7 | Reckless 0.9.0 | "billions"; own self-play from a random net (data since 2025 not published) |
| 8 | Gaia 4.4.1 | size not published; own self-play at least in part |
| 9-10 | Berserk 20250606 | rolling window, total not published; own self-play (Koivisto data mixed in 2023, later status not published) |
| 9-10 | Cinder 0.6.1 | size not published; Lc0 data |
| 11 | Dragon by Komodo 3.2 | "billions"; own games plus some games against other engines (Komodo's moves and evals only) |
| 12-13 | Alexandria 8.0.0 | size not published; Lc0 data |
| 12-13 | pawnocchio 2.0 | size not published; own self-play plus games of the author's MCTS engine Vine, relabelled by a much larger own net |
| 14 | Integral 8 | 16.7 B unfiltered; own self-play, mostly 20,000 soft nodes |
| 15-16 | Caissa 2.0 | 20.5-21 B; mixed (about 99% own self-play, about 1% Stockfish Fishtest games) |
| 15-16 | Viridithas 20.0.0 | size not published; own self-play (25k-node tier) |
| 17 | Stormphrax 8.0.0 | size not published; own self-play (5k and 24k soft nodes) |
| 18 | Hobbes 3.0 | 37.5 B (30 B standard, 7.5 B DFRC); own self-play (5k, 12k, 20k soft nodes) |
| 19 | Horsie 1.1.0 | about 6.6 B; self-play seeded by an Lc0-trained net (mixed lineage) |
| 20 | Lizard 11.2 | about 6.6 B; as Horsie |
| 21-22 | Astra 7.0 | about 12 B; own self-play from random weights (Lc0 data up to 6.1.1) |
| 21-22 | Raphael 4.2.0 | 29.8 B; own self-play (5,000 and 24,000 soft nodes) |
| 23 | Incipit 0.6.0 | 33 B (public set 37.6 B from 323 M games); own self-play only, 8,000 nodes per move, bootstrapped from a hand-written eval |
| 24-26 | RubiChess 20240817 | 55 GB of binpacks; own games labelled by fixed-depth search |
| 24-26 | Starzix 6.0 | size not published; Lc0 data |
| 24-26 | Tarnished 6.0 | about 22 B; own self-play from a random net (5,000 or 20,000 soft nodes), relabelled by a 4096-wide teacher net |
| 27 | Clover 9.1 | size not published (first 9.0 net about 2.7 B); own self-play (5,000 and 20,000-node labels; half DFRC) |
| 28 | Ethereal 14.25 | 11.45 B: 8.35 B self-play at 40,000 nodes, 3.10 B from games against Stockfish (own side only) |
| 29 | Fritz 20 | size not published; own self-play chain (the Ginkgo line) |
| 30 | Halogen 16.0.0 | 14.8 B; own data only, from a random net |
| 31 | Quanticade Cronus 3.0 | size not published; Lc0 data (Cronus is the last release with it) |
| 32 | Igel 3.8.0 | size not published (earlier generations over 30 B); own, fixed-depth labels |
| 33 | PZChessBot 7.1 | about 90 M games generated 2026-04 to 06; own self-play from a random net (5,000 to 20,000 soft nodes) |
| 34 | ZigQueen 6.5.0 | 131.1 B kept of 225.5 B read; Lc0 and Stockfish-project data with Lc0 BT4 labels, no self-play |
| 35 | Devre 7.0 | size not published; own self-play (earlier nets on Lc0 data; any remainder UNVERIFIED) |
| 36 | JustBot 0.5.0 | about 103 M games generated up to its net; own self-play from PeSTO (5,000 to 40,000 nodes) |
| 37-38 | Titan 1.1.0 | size not published; Lc0 data |
| 37-38 | Velvet 8.1.0 | size not published; own self-play |
| 39 | Minke 7.0.0 | 17 B; own self-play from a random net |
| 40-41 | Ginkgo Santiago 1.0 | about 6.7 B (stated 2025-10); own self-play |
| 40-41 | Revenge 4.0 | size not published; own chain from Pedone's evaluation |
| 42 | Tcheran 14.0 | no total published (19.7 GB public set); own self-play (5k and 20k soft nodes) |
| 43-44 | Seer 2.8.0 | size not published; own, from a 6-man tablebase retrograde seed then self-play |
| 43-44 | Uralochka 3.41a | size not published (28 B for 3.42); mixed: own self-play plus positions from games against other engines, self-labelled |
| 45 | Lc0 0.29.0 w753723 (GPU, not NNUE) | size not published; own self-play (run T75) |
| 46 | Motor 0.9.0 | not published |
| 47-49 | Chess System Tal 3.00 | not published |
| 47-49 | Renegade 1.3.0 | 8.4 B from 91 M games; own self-play (10k and 20k soft nodes) |
| 47-49 | Stoofvlees II b5 (GPU, not NNUE) | size not published; self-play plus Leela data (mixed) |
| 50 | Rebel 17.0 | not published |
| 51 | rofChade 3.1 | about 10 B; own, rescored repeatedly |

## 3. King-bucket layouts that are published in prose

Six engines publish a 16-bucket layout in words or as a table; the rest keep theirs in code.
All six describe the mirrored half board (four files by eight ranks), and all have the same
shape: fine where the king usually stands, coarse elsewhere. That the first row is the own
back rank is the agents' reading for Hobbes, Minke, Raphael and Tarnished; the pages do not
label the rows.

| Engine | Buckets | Layout on the four files of the half board |
|---|---|---|
| Stockfish (stated); Triumviratus, Igel and RubiChess by naming the same feature set; Torch v2 by its input count | 32 | one per king square |
| Hobbes 3.0 | 16 | ranks 1 and 2: one bucket per file (8); ranks 3-4: one per file, shared by the two ranks (4); ranks 5-6: two buckets of two files (2); ranks 7-8: the same (2) |
| Tarnished 6.0 | 16 | the same as Hobbes |
| Minke 7.0.0 | 16 | ranks 1 and 2: one per file (8); rank 3: two buckets of two files; rank 4: two more; ranks 5-6: two; ranks 7-8: two |
| Raphael 4.2.0 | 16 | the same as Minke |
| ZigQueen 6.5.0 | 16 | the same as Minke (stated with rank numbers) |
| Incipit 0.6.0 | 16 | "ranks 1-2 per file pair, wing/centre above, ranks 5-6 and 7-8 paired" |
| Incipit, first step | 4 | by king rank: rank 1, rank 2, ranks 3-4, ranks 5-8 |
| Hobbes, first step | 4 | the back rank split in two, the second rank, the rest |
| Minke, first step | 4 | two on the first rank (file pairs), one for the second rank, one for the rest |

**How the count grew with data** (own-data engines that publish both):

| Engine | 4 buckets | 6 | 8 | 10 | 16 |
|---|---|---|---|---|---|
| Hobbes | 1.7 B positions | 2.1 B | 5 B | 7 B | 17 B |
| Minke | 2.5 B | 3.8 B | 6.9 B | 9.2 B | 17 B |
| Raphael | 3.0 B (failed STC on less data) | 4.0 B | 5.5 B | 7.0 B | 10.7 B |

Fork's data (about 1.2 B after the filter) is below the size at which any of the three
merged its first four buckets.

## 4. What the tables show

Counts are over the 51 rows. Six closed engines publish nothing about their architecture
(Fritz, Ginkgo, Revenge, Chess System Tal, Rebel, Dragon), two are GPU engines (Lc0,
Stoofvlees), and Torch and Obsidian publish only fragments.

1. **A multi-layer head is the norm.** 33 of the 42 NNUE engines with a published body have layers
   after the accumulator, nearly all in the form 16 -> 32 -> 1 (or 32 -> 32 -> 1) in 8 copies
   picked by piece count. The nine single-layer nets (Alexandria 8.0.0, Starzix, Clover,
   JustBot, Titan, Velvet, Uralochka, Motor, Renegade) are all 1024 wide or wider, and all
   but Alexandria rank 24th or lower. No engine in the list publishes a single-layer net as
   narrow as Fork's 512.
2. **Pairwise multiplication goes with the head.** 22 engines state or imply it. The heads
   without it are older designs (Ethereal, Berserk's rated net, Tcheran, Quanticade) or do
   not say.
3. **Threat inputs: 16 rated nets have them**, and 7 more engines added them after their
   rated version (Berserk, Alexandria, Halogen, Quanticade, PZChessBot, Devre, RubiChess).
   The counts cluster at 59,808 or 60,144 (Stockfish's set without king threats, or one
   close to it), with Incipit (about 56,900), Coda (66,864) and Reckless and PlentyChess
   (79,856 at first, then cut) as variants. Every rated threat net has a multi-layer head.
4. **Threat nets are narrow.** Their accumulators are 384 (Reckless at its merge), 640
   (PlentyChess, Stormphrax), 768 (Hobbes, Raphael, Integral) or 1024 (Stockfish,
   Triumviratus, Coda, Gaia, Viridithas, Incipit, Igel, ZigQueen). Every engine that
   reports the step cut its width when threats arrived (speed.md, A11).
5. **Pawn-pair inputs: 11 rated nets**, 4,560 inputs (pairs on the same or adjacent files) in
   Stockfish, Triumviratus, Gaia, Viridithas and Devre; 1,488 in ZigQueen; **608 in Incipit,
   by the same rule as Fork's 608 pawn links** (README, "For the owner's attention").
   Triumviratus adds 96 passed-pawn inputs and a pawn-king sub-network.
6. **Material or queen routing of the inputs** exists in Triumviratus (8 weight sets by the
   opponent's non-pawn material), Starzix (5 enemy-queen buckets) and, after their rated
   versions, Stockfish and Gaia (a queen split); Caissa doubled its output heads by queen
   presence instead. Velvet had it and dropped it for
   more king buckets. Integral feeds the fifty-move counter in as 11 inputs per bucket.
7. **King buckets: 8 to 16 is the common range**, 32 in the Stockfish-derived sets and in
   Caissa and Velvet. Incipit measured 32 against 16 at +2.8 and went back to 16.
8. **Output buckets: 8 by piece count almost everywhere.** Incipit uses 6 so that no bucket
   holds only positions its tablebase-adjudicated data never records; Uralochka 6.
9. **Activations in the head:** dual activation (clipped and squared-clipped side by side) in
   Stockfish, Stormphrax, Hobbes, Minke, Tcheran, Tarnished, Halogen, pawnocchio and Coda;
   tried and rejected by Viridithas (twice) and Raphael. Viridithas uses hard-Swish and
   SwiGLU instead.
10. **Quantisation splits two ways.** All-integer heads: Stockfish, Stormphrax, Raphael,
    ZigQueen, Caissa, pawnocchio, Berserk. An int8 first dense layer with float layers after
    it: Viridithas, Coda, Reckless, Incipit, Seer, partly PZChessBot. Training against the
    integer grid: Stockfish (+4.4 STC), Caissa, Triumviratus, ZigQueen, Incipit, Gaia.
11. **Data.** Nets trained wholly or mostly on the engine's own games used 6.6 B to 37.5 B
    positions
    (Hobbes 37.5, Incipit 33, Raphael 29.8, Tarnished 22, Caissa 21, Minke 17, Integral 16.7,
    PlentyChess 15+, Halogen 14.8, Astra 12, Ethereal 11.5, rofChade 10, Renegade 8.4,
    Ginkgo 6.7, Lizard and Horsie 6.6). Fork has about 1.2 B. The engines on Lc0 data
    relabelled by Lc0's BT4 net report 131 B (ZigQueen) to about 270 B (Triumviratus).
12. **Label budgets.** The common own-data budget is 5,000 soft nodes per move, with a
    higher tier added later: 8,000 (Incipit's standard), 12,000 (Hobbes, Minke), 20,000 to
    25,000 (Hobbes, Raphael, Viridithas, Stormphrax, Integral, Renegade, Clover, Tarnished),
    40,000 (Ethereal, Halogen's first sets). Fork labels everything at 20,000.
