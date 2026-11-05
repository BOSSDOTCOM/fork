# NNUE inputs beyond piece-square: threat inputs and pawn-pair inputs (Phase 4)

Created 2026-11-05. This file goes deeper than the short entries in
[nnue-design.md](nnue-design.md) §1.6 (threat inputs) and §1.7 (pawn-structure
inputs). Those entries stay as they are; where the two disagree, this file
is newer and takes precedence.

**How this file was written (clean room).**
- No engine repository or trainer repository was cloned or downloaded, and
  no engine or trainer source file was opened. The sources are pull-request
  descriptions and commit messages (GitHub REST and commit-search APIs: text
  only, no diffs), release notes, two PDF attachments that the Stockfish
  threat-inputs PR links (a prose summary and a slide deck), nnue-pytorch's
  documentation, one author's blog post (prose only) and one forum thread.
  Each one is listed in [sources.md](sources.md), section "NNUE inputs:
  threat and pawn-pair inputs (nnue-inputs.md), 2026-11-05".
- **Concepts only** (owner's rule for this entry). No code, no feature-index
  formula, no table layout, no input counts, no bucket counts, no offsets,
  no layer widths, no quantization factors and no tuned values from any
  engine or trainer appear here. Some sources print exact counts and
  architecture strings; they were deliberately left out.
- Elo figures are the cited project's own self-play results, quoted as
  evidence of scale, not as parameters. "Derived" means this file's logistic
  conversion of the win/loss/draw counts in a Stockfish commit or PR (an
  approximation, not fishtest's own figure). "STC" and "LTC" are each
  project's short and long test controls.
- Anything not confirmed on an opened primary source is marked
  **UNVERIFIED** with the reason.

**Tags.** Every technique here is **REFERENCE ONLY**: study the idea, write
Fork's own code. bullet is **USE** (MIT, a tool). Nets and data of other
engines are **OFF-LIMITS** ([data-policy.md](data-policy.md)).

**Phase and component.** Phase 4, a later network generation (DESIGN.md on
main, Phase 4 answer 13: threat inputs are in scope as a later add-on to
the piece-square net). Components: the feature set and accumulator in
`src/nnue`, the attack bookkeeping in make-move (`src/core`), the bullet
training graph's custom sparse input (bullet-internals.md §4.7), and the
parity test.

---

## 1. Threat inputs (attacker-victim pairs)

Verified 2026-11-05.

### 1.1 What they are

- One binary input for each relation "this piece, on this square, attacks
  that piece, on that square" that holds in the current position. Both
  pieces are described by type and by colour relative to the perspective
  (own or enemy), so each accumulator perspective sees its own copy.
- Both directions of contact count: attacks on enemy pieces (threats) and
  attacks on own pieces (defences).
- The attack relation is the real one on the current occupancy: a slider's
  attack stops at the first piece in its path.
- Threat inputs are an **add-on** to a king-relative piece-square set, not a
  replacement. nnue-pytorch's docs describe the piece inputs as the
  foundation and the threat inputs as many small corrections. A quiet
  position may have few or no active threat inputs, and the net must still
  evaluate it.

### 1.2 Why they help

- A first layer fed only piece-square inputs computes a sum of independent
  per-piece contributions. Whether a knight on one square attacks a queen
  on another is a property of the *pair*, which the first layer cannot
  represent; the later, much smaller layers must reconstruct it through the
  non-linearity. Threat inputs make each attack relation a first-layer
  feature, so the accumulator carries second-order (pair) terms directly.
  (This explanation is Fork's reasoning from the definitions; the sources
  state the effect, not the mechanism.)
- The measured effect is a large gain at equal nodes (§1.5): the net is
  much more accurate per evaluation, and the cost is speed.

### 1.3 Lineage

- **Monty** (an MCTS engine; Viren6 and jw1912). The Stockfish PR's summary
  PDF says Viren created the feature set by extending an earlier Monty
  scheme in which each piece-square input was split four ways by whether
  the piece was attacked, defended, both or neither. Monty PR #87
  (2024-12-30) introduced the threat-input value net: +48.06 ± 3.3 at STC
  in Monty's own testing (an MCTS engine, so not comparable to alpha-beta
  figures).
- **Yukari** (Ravenslofty) was the first alpha-beta engine to use a
  simplified version, built on its existing incremental attack tables:
  commit 2d482c64 (2025-02-21), +28.34 ± 10.87 at 8+0.08 and +28.27 ± 10.11
  at 40+0.4.
- **PlentyChess** (Yoshie2000): first top alpha-beta engine with the full
  set and efficiently updated threats, PR #400 (2025-10-12). The PR credits
  Monty for the encoding, a Stockfish inference branch (sscg13), Stockfish
  net trainers (vondele, linrock), and Yukari for the idea of incremental
  threat tracking. The summary PDF credits Yoshie2000 with the first
  bitboard-based incremental threat tracking.
- **Stockfish**: PR #6411 (sscg13, 2025-11-12), released in Stockfish 18.
  nnue-pytorch PR #373 added training support; its description says it is
  translated almost verbatim from jw1912's threat-input implementation in
  bullet.
- **Later adopters** (PR descriptions): Stormphrax #293 (2026-02-22; credits
  87flowers for fast incremental updates), Viridithas #425 (2026-04-15; uses
  Stockfish's king-free threat set and credits Stormphrax's implementation),
  Integral #243 (2026-08-30), Alexandria #630 (2026-10-12). Reckless's
  adoption is known from its PR titles and the existing KB entry
  (nnue-design.md §1.6), not from a PR description read here.

### 1.4 Keeping the input count manageable

Six ideas appear in the sources. Each one shrinks the index space, the net
file, the number of feature updates per move, or the training data needed
per weight.

1. **Index only reachable geometry.** A naive scheme would reserve every
   (attacker square, victim square) combination for every pair of piece
   kinds. Monty's slides instead enumerate, per attacker kind, only the
   square pairs that attacker could ever reach on an empty board, and
   multiply by the victim kinds that are possible. That removes most of the
   naive space before any other rule is applied.
2. **Remove implied pairs (redundancy removal).** A pair carries no new
   information when another active pair always accompanies it:
   - *Containment.* If piece kind A's attack pattern, from A's square, is
     always matched by piece kind B attacking back (a rook and a queen on
     the same file or rank is the sources' example), then "A attacks B"
     implies "B attacks A". Keep one direction and drop the other. Stockfish
     keeps the pair whose attacker is the more valuable piece.
   - *Same kind.* Two pieces of the same kind attack each other mutually,
     so one of the two features is dropped by a fixed ordering of their
     squares.
   - *Impossible pairs.* A king can never attack a king in a legal
     position.
   - Filtering is applied after mirroring, so the rule is the same in both
     perspectives (Stockfish summary PDF).
   - *Packing the holes.* Deduplication leaves unused indices. Stockfish
     PR #6635 (2026-02-24, no functional change) reused them to merge two
     families of same-kind planes into one block and dropped some indices
     that could never be used, making the file smaller with the same
     function.
3. **Drop low-value relations.**
   - *Attacks on a king.* If the side to move is attacked it is in check,
     and evaluation is normally not called in check; if the other king is
     attacked the position is illegal. nnue-pytorch's docs first noted that
     removing them had not gained. Stockfish then removed piece-to-king
     threats (PR #6593, 2026-02-04: about 13 MB smaller net and about 0.8
     fewer threat updates per incremental update; passed non-regression at
     STC and LTC).
   - *Attacks by a king.* Removed next (Stockfish PR #6609, 2026-02-10:
     about 7 MB smaller; non-regression at STC and LTC, derived +0.6 STC and
     +0.1 LTC, so worth about nothing). Stormphrax #285 removed them too: at
     fixed nodes −2.38 ± 2.75 (the test stopped on its lower bound), at STC
     +1.66 ± 2.49 (passed non-regression), "decent net size reduction".
   - *Pawn-pawn contact.* Removed once pawn-pair inputs (§2) took it over.
4. **Mirror horizontally.** Threat inputs are mirrored by the king's side of
   the board, like the piece inputs. This halves the space and means a full
   threat refresh is needed only when a king crosses the centre line, not
   on every king move.
5. **Narrow the first layer.** Every adopter that published its architecture
   cut its first-layer width when it added threat inputs (Stockfish summary
   PDF; Stormphrax #293; Viridithas #425). Widths are not recorded here.
6. **Store threat weights as int8.** Monty first quantized input weights to
   int8 while keeping the arithmetic in int16 (Monty #116). Yoshie2000
   tested variants and found int8 for the threat weights only to be the best
   balance. Threat weights are small, so they can be clipped in training at
   negligible loss (nnue-pytorch docs).

   | Test | Monty #116 (2025-09) | PlentyChess #411 (2025-10) |
   |---|---|---|
   | fixed nodes | −5.22 ± 3.16 | −2.52 ± 4.09 |
   | STC | passed [0, 4] | +9.87 ± 3.86 |
   | LTC | passed [1, 5] | +3.30 ± 2.59 |

   A small accuracy loss buys bandwidth. nnue-pytorch's docs put the speed
   gain at about 5% on x86 and about 10% on ARM.

What dedup buys is mainly net size and data per weight, not speed by
itself. 87flowers' draft post reports that removing redundant threats at
feature-generation time did not speed up Reckless. Stockfish PR #6936,
which filters invalid pairs earlier, measured about a 1% speedup.

### 1.5 Incremental updates and the accumulator

- **What changes when a piece is placed or removed** (87flowers' draft
  post, 2026-10-18):
  - its outgoing attacks;
  - incoming attacks on it from other pieces;
  - slider attacks that pass through its square, which it now blocks or
    unblocks.

  A quiet move is "remove at origin, place at destination". A capture can be
  modelled as the attacker leaving its origin and the victim's square
  changing piece kind. The destination's occupancy does not change, so its
  slider-through-square updates can be skipped. PlentyChess adopted this
  ("idea from Stockfish") as a dedicated piece-swap update: PR #438, +1.37 ±
  1.10 at STC.
- **Cancelling pairs.** When a slider's ray is unblocked by the piece
  leaving its origin and blocked again by the piece landing on the same ray,
  the same feature is added and removed. Stockfish PR #6453 skips such
  discoveries.
- **Volume.** In a typical middlegame three to four times as many threat
  features change as piece features (nnue-pytorch docs), so the update is
  memory-bandwidth bound. Prefetching the weight rows as soon as the changed
  indices are known helped in several engines (Stockfish #6602, Viridithas
  #433 and Halogen #888, the last two by title).
- **Tables or bitboards.** PlentyChess first kept incremental threat tables,
  then replaced them by computing the deltas from bitboards during
  make-move (PR #406, idea by rn5f107s2: +3.44 ± 2.19 at 2+0.02). Fork's
  reading: deriving the deltas from attack bitboards on the fly cost less
  there than maintaining a separate table.
- **Separate accumulators, then merged.**
  - At first the threat inputs got their own accumulator, because their
    refresh trigger differs (the king crossing the centre line, against a
    king-bucket change for the piece inputs). The two were added at
    evaluation time.
  - Stockfish PR #6890 (2026-06-10, no functional change) merged them into
    one accumulator per side. A threat refresh always coincides with a
    piece-input refresh anyway. Merging saves an extra load and store and
    halves the accumulators' cache footprint: about 2.5% faster locally,
    passed STC as a speedup. PlentyChess #488 and Integral #266 (+6% speed
    on the author's machine) did the same.
  - The price is that any king move now re-adds the threat (and pawn-pair)
    contributions. Stockfish PR #6990 recovers part of it for positions with
    many pieces: it computes a king move's change from the refresh cache's
    piece-input part instead of re-adding every threat feature.
- **Paths that never evaluate** (perft, TT-move verification, walking the
  PV, root tablebase ranking) should not compute threat deltas. Stockfish
  PR #7203 compiled them out of that path: perft 5 over the bench positions
  about 27% faster.
- **Search can read the delta count.** Stockfish PR #6739 (2026-04-17)
  proposed the number of changed threat features as an LMR signal, since
  it is already computed. Whether it was tested and merged is
  **UNVERIFIED** (the PR shows no result).

### 1.6 Evidence

| Engine, PR | Fixed nodes | STC | LTC | Other |
|---|---|---|---|---|
| Yukari 2d482c64 (2025-02) | not given | +28.34 ± 10.87 | +28.27 ± 10.11 | simplified set |
| PlentyChess #400 (2025-10) | +45.49 ± 2.23 | −3.08 ± 2.89 (failed) | +1.78 ± 1.37 | |
| Stockfish #6411 (2025-11) | about +30 (summary PDF) | passed [0, 2], derived +2.0 | passed [0.5, 2.5], derived +3.8 | VVLTC passed, derived +7.0; ARM LTC +13.9 ± 1.9 |
| Stormphrax #293 (2026-02) | +33.51 ± 9.35 | +2.73 ± 2.07 | +9.85 ± 4.24 | 4 threads +13.03 ± 4.94 (nnue-design.md §1.6) |
| Viridithas #425 (2026-04) | +27.43 ± 7.91 | +2.98 ± 2.09 | +5.38 ± 2.97 | about 87% of the old speed on AVX-512 |
| Integral #243 (2026-08) | not given | not given | +24.43 ± 7.77 | |
| Alexandria #630 (2026-10) | not given | +15.53 ± 5.50 | +13.43 ± 4.96 | |

- **Speed.** Stockfish's summary puts the threat net 5% to 15% slower than
  its predecessor on x86, and about as fast on ARM.
- **Scaling.** Stockfish's summary says the gain grows slightly with time
  control and especially with threads, probably through better weight-access
  patterns. Stormphrax's 4-thread result points the same way. For TCEC's
  long, many-threaded games this is the favourable direction.
- **What failed** (Stockfish summary PDF): in Monty, using threats through
  pieces (x-rays), and keeping the piece inputs active only where a piece
  had no threat, were each more than 50 Elo worse at fixed nodes. An early
  single-layer Stockfish port without incremental tracking was about −90
  against master even with +50% time odds.
- **A contrary report.** In a talkchess thread (2026-01-27 to 29) one team
  reported that a threat-input net was only marginally better than a
  smaller one and lost "evaluation stability". sscg13 and others disputed
  the implementation and asked for the diff; no data was posted. Treat it
  as **UNVERIFIED** and as a reminder that a slow or buggy implementation
  hides the gain.

### 1.7 Pitfalls

- **Delta correctness.** Debug builds should compare the incremental
  threat accumulator against a from-scratch rebuild at every node. The net
  trains around an indexing bug instead of failing: Monty's first version
  did not separate colours correctly, and PR #114 (2025-09-06) fixed it
  about eight months after PR #87.
- **Trainer-engine parity.** The trainer and the engine compute the same
  feature list in two code bases. Fork's parity test (DESIGN.md §5.3) must
  cover the threat features too, including mirrored positions and positions
  with no threats.
- **Overflow.** Many more active inputs per perspective tighten the int16
  accumulator bound (nnue-design.md §5.1). That is one more reason for
  small, clipped threat weights.
- **Untrained indices.** Space reserved but never active (deduplicated or
  impossible pairs) wastes file space. It is harmless only if those weights
  are never read.
- **The net is not the only variable.** Stockfish's threat net was not
  SPSA-tuned, while its predecessor was, and the summary recommends a
  fresh long-TC search tune after the eval change. A comparison must
  account for both.
- **Data.** More inputs need more positions. The minimum is still
  **UNVERIFIED**; every adopter trains on billions of positions.

### 1.8 For Fork

- **Order.**
  1. First a piece-square net.
  2. Then threat inputs as an add-on. A separate threat accumulator is the
     easiest to test against a rebuild.
  3. The merged accumulator is a later speed step, with bench unchanged.
- **Design choices that need Fork's own decisions and the DESIGN.md §8
  screen:**
  - the dedup rules;
  - whether king relations are included;
  - the mirroring axis;
  - int8 storage with a training clip;
  - the first-layer width;
  - the data volume.
- **Shared bookkeeping.** The same attack-delta code could feed T56's
  threat-aware ordering (search-techniques.md §3.34). That is Fork's
  inference and **UNVERIFIED** until measured.
- **Names not to use** (identifiers seen in PR titles and descriptions
  read for this entry; DESIGN.md §8 applies to every new name):
  `update_piece_threats`, `DirtyThreat`, `DirtyThreatList`,
  `threatDeltaCount`, `Full_Threats`, `FullThreats`, `swapPiece`,
  `noRaysContaining`, `update_accumulator_hybrid`, `append_changed_indices`,
  `threat_index`. The concepts are fine; the identifiers are not.
- **Licences of the projects cited.**
  - GPL-3.0: Stockfish, nnue-pytorch, PlentyChess, Stormphrax, Alexandria,
    Halogen.
  - AGPL-3.0: Monty, Viridithas, Reckless.
  - Integral: none.
  - Yukari: GitHub reports NOASSERTION; the licence file was not read.

  Only ideas are used.

### 1.9 UNVERIFIED items (threat inputs)

1. Whether Stockfish PR #6739 (threat-delta count in LMR) was tested or
   merged: the PR shows no result.
2. The minimum data volume for threat inputs: no opened source states one.
3. Reckless's threat-input PR description and results: known only from PR
   titles here.
4. The contrary "eval stability" report (talkchess, 2026-01): no data
   posted.
5. The exact rule behind "reachable geometry" in Stockfish's current
   indexing: Monty's slides describe it for Monty's V2 scheme. Whether
   Stockfish indexes the same way is not stated in prose, and its code was
   not read.
