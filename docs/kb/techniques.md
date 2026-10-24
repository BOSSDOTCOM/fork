# Fork KB: Technique Reference

One entry per technique: own-words explanation, Fork phase, primary source,
pitfalls. Sources were opened on **2026-10-23** (list in
`_sources-research.md`). Points marked **UNVERIFIED** were not on the page
opened and come from general knowledge; confirm before relying on them.

All techniques are **REFERENCE ONLY**: Fork writes its own code. Stockfish
(GPL-3.0, https://github.com/official-stockfish/Stockfish) may be read to
understand an idea, never copied or translated line by line; do not keep its
source open while writing the matching Fork code.

Phases (docs/DESIGN.md): 1 board/movegen, 2 UCI, 3 search + Syzygy,
4 evaluation + training, 5 time management, 6 SMP, 7 tournament play,
8 TCEC-conditions testing.

Phase 2 (UCI protocol) has its own file: [uci.md](uci.md).

A useful ordering for Phase 3 is CPW's "Search Progression" page (the
"Connorpasta" and "Improved Connorpasta" lists): TT + move ordering, PVS,
qsearch, aspiration; then NMP, LMR, RFP, history, LMP, futility, continuation
history, SEE pruning, capture history, singular extensions, multicut,
double/negative extensions, correction history. Each addition must pass an
SPRT test. https://www.chessprogramming.org/Search_Progression

---

## 1. Board representation (Phase 1)

### Bitboards
- One 64-bit set per piece type and colour; attacks, masks and move targets
  are sets too, so many squares are processed per instruction.
- Keep a redundant mailbox (piece-on-square array): bitboards answer "what
  is on square x" badly.
- Pitfalls: mailbox and bitboards must stay in sync in make/unmake;
  popcount/bitscan should use hardware intrinsics (with a portable
  fallback).
- Source: https://www.chessprogramming.org/Bitboards

### Magic bitboards (sliders)
- Mask the relevant blockers (edges excluded), multiply by a per-square
  magic, shift, and index a precomputed attack table. Collisions are fine
  only when they map to the same attack set ("constructive").
- "Fancy" magics (per-square table size) are the mainstream choice, about
  800 KiB for rooks+bishops; plain magics are simpler but need about
  2.25 MiB.
- Magics are found by trial and error; Fork generates its own from a fixed
  seed (ORIGINALITY.md), never copies published tables.
- Pitfalls: table size vs cache; a bad magic silently gives wrong attacks,
  so verify every occupancy subset at startup in debug builds.
- Source: https://www.chessprogramming.org/Magic_Bitboards

### PEXT (BMI2) bitboards
- `pext(occupancy, mask)` gives a dense index directly; one shared table of
  about 840 KB.
- Pitfall: PEXT/PDEP were slow on AMD Zen 1/Zen 2 (fixed in Zen 3, Nov
  2020). Ship a magic build and a PEXT build, or detect at runtime (CPUID
  leaf 7, EBX bit 8). TCEC's CPU model, re-checked 2026-10-24 on
  https://wiki.chessdom.org/TCEC_Season_Further_information: the CPU server
  (S28 onward) is 2x AMD EPYC 9754 and the GPU server 2x AMD EPYC 9175F;
  both CPU-flag lists printed there include `bmi2`. Whether PEXT is fast on
  those parts (their Zen generation) is UNVERIFIED: AMD's product pages
  load the spec table by script and the static HTML had no architecture
  field. Keep both builds and measure PEXT vs magics on the target.
- Source: https://www.chessprogramming.org/BMI2

### Zobrist hashing
- Random 64-bit key per (piece, square), plus side to move, castling
  rights, en-passant file; updated incrementally with XOR in make/unmake.
- Pitfalls: 64-bit keys still collide in huge searches (verify TT moves
  are pseudo-legal); seed matters (generate with a good PRNG); keys should
  be linearly independent. Hash the en-passant file only when an ep capture
  is actually possible (UNVERIFIED: the page, re-checked 2026-10-24, only
  says the key includes "the file of a valid en passant square" without
  defining "valid"; the stricter rule is needed so equal positions get
  equal keys for repetition detection).
- Source: https://www.chessprogramming.org/Zobrist_Hashing

---

## 2. Move generation (Phase 1)

### Pseudo-legal vs legal, staged generation
- Pseudo-legal generation is simpler; legality then checked on make (or
  pre-checked with pin/check masks). Fully legal generation must handle
  pins, and double check (king moves only).
- Staged generation (TT move, captures, killers, quiets) avoids generating
  quiets when an early move cuts off.
- Pitfalls: en-passant legality (pins and discovered attacks through the
  two vacated squares, including along the rank) is the classic bug
  (the rank case is UNVERIFIED on the opened page but is well known;
  SF18's notes mention a rare repetition/en-passant/pin bug); castling
  through attacked squares; promotions to all four pieces.
- Source: https://www.chessprogramming.org/Move_Generation

### Perft
- Count leaf nodes of the legal-move tree to a fixed depth and compare with
  published values; "divide" prints per-root-move counts to localise bugs.
  Bulk counting at depth 1 is faster but not comparable with all reference
  numbers.
- Pitfalls: perft ignores repetition/50-move/insufficient material; hashed
  perft can be wrong on collisions.
- Source: https://www.chessprogramming.org/Perft

---

## 3. Search (Phase 3 unless noted)

The Phase 3 idea mining (tiers, dependencies, Elo evidence, clean-room
descriptions) is in [search-techniques.md](search-techniques.md), which
takes precedence over the short entries below for Phase 3 planning.

### Iterative deepening + PVS
- Search depth 1, 2, 3... reusing TT/ordering; the previous best move and
  score drive ordering, aspiration and time management.
- PVS: first move with the full window; others with a null window
  (alpha, alpha+1); re-search with the full window only if the null-window
  score lands inside (alpha, beta). Only PV nodes re-search. Fail-soft is
  current practice.
- Pitfall: re-search instability; PVS re-searches with the original bounds.
- Source: https://www.chessprogramming.org/Principal_Variation_Search

### Aspiration windows
- Search the root with a small window around the previous score; on fail
  high/low widen only the failing side, exponentially.
- Pitfall: instability (a re-search can fail the other way); mate scores
  need the window fully opened (UNVERIFIED: the CPW Aspiration Windows page
  does not mention mate scores, re-checked 2026-10-24).
- Source: https://www.chessprogramming.org/Aspiration_Windows

### Quiescence search + SEE
- At depth 0, search captures (and promotions) only, with stand-pat (static
  eval as a lower bound). When in check, no stand-pat: search all evasions.
- Prune captures with negative SEE; delta pruning for hopeless captures.
- SEE: simulate the capture sequence on one square, least valuable attacker
  first, each side may stop; forced first capture when evaluating a given
  move. Uses: ordering (good vs bad captures), qsearch and main-search
  pruning (linear margin for captures, quadratic for quiets).
- Pitfalls: qsearch explosion without ordering; stand-pat in check; SEE
  ignores pins and x-ray subtleties unless coded (UNVERIFIED: the CPW SEE
  page mentions pin-aware SEE only through forum thread titles, re-checked
  2026-10-24).
- Sources: https://www.chessprogramming.org/Quiescence_Search,
  https://www.chessprogramming.org/Static_Exchange_Evaluation

### Transposition table
- Shared hash table: key check bits, best move, score, depth, bound type
  (exact/lower/upper), age. Cut at non-PV nodes when stored depth is enough
  and the bound allows; always try the TT move first.
- Replacement: buckets (several entries per cache line), prefer deeper and
  current-age entries, replace stale ones.
- SMP: one global table, accessed without locks.
- Pitfalls: TT move may be illegal after a collision (validate with
  `is_pseudo_legal`/`is_legal`, already in Phase 1 design); mate scores must
  be stored relative to the node and converted by ply on store/probe; with
  lockless access, a torn entry must be detected (XOR-key or key-check
  scheme). Both points verified 2026-10-24 on CPW: the Score page says
  ply-relative mate scores need adjusting when stored in the TT and
  re-adjusting when read back; the Shared Hash Table page describes the
  Hyatt/Mann lock-less scheme (store key XOR data next to data, accept a
  probe only if the stored key XOR the stored data equals the probing key),
  with a checksum as the alternative for bigger entries.
- Source: https://www.chessprogramming.org/Transposition_Table,
  https://www.chessprogramming.org/Score,
  https://www.chessprogramming.org/Shared_Hash_Table

### Move ordering
- Typical order: TT move; winning captures/promotions (MVV-LVA or SEE,
  optionally capture history); killers; countermove; quiets by history
  (butterfly + continuation histories); losing captures.
- Selection sort per pick, not a full sort.
- Source: https://www.chessprogramming.org/Move_Ordering

### Killers
- Two quiet moves per ply that caused cutoffs; tried after good captures.
- Pitfall: keep the two slots distinct.
- Source: https://www.chessprogramming.org/Killer_Heuristic

### History, continuation history, capture history
- Butterfly history: score[colour][from][to] (or [piece][to]) raised on
  cutoff, bonus about depth squared. Modern "gravity" update clamps values
  and scales by how surprising the result was; quiets tried before the
  cutoff move get a malus.
- Continuation history: indexed by the move played 1, 2 (and more) plies
  earlier plus the current move; generalises countermove/follow-up history.
- Capture history: [moved piece][to][captured type]; replaces the LVA part
  of MVV-LVA.
- Pitfalls: saturation without gravity; history tables shared or per thread
  is a Phase 6 decision (UNVERIFIED which is better: no opened source
  compares them; settle it by measurement in Phase 6).
- Source: https://www.chessprogramming.org/History_Heuristic

### Countermove
- Table indexed by the previous move (piece/to) storing the quiet reply that
  last caused a cutoff; gets a bonus in ordering.
- Source: https://www.chessprogramming.org/Countermove_Heuristic

### Null move pruning
- Give the opponent a free move, search at depth - R (R grows with depth and
  with eval - beta); if still >= beta, cut.
- Conditions: not in check, side has non-pawn material, eval >= beta, not PV.
- Pitfall: zugzwang. Options: disable with only pawns, verification search
  at high depth.
- Source: https://www.chessprogramming.org/Null_Move_Pruning

### Late move reductions
- Moves late in the ordering get searched at reduced depth (null window),
  re-searched at full depth if they beat alpha. Base reduction about
  a + ln(depth) * ln(moveNumber) / b, then adjusted: less in PV/when
  improving/for checks/killers; more at expected cut nodes, for bad history,
  when TT move is a capture.
- Pitfalls: clamp reductions to [0, depth-1]; tactics hidden in reduced
  captures/checks.
- Source: https://www.chessprogramming.org/Late_Move_Reductions

### Reverse futility pruning (static null move)
- At low depth, non-PV, not in check: if eval - margin(depth) >= beta,
  return (eval or a blend toward beta). Margin smaller when "improving".
- Source: https://www.chessprogramming.org/Reverse_Futility_Pruning

### Futility pruning and late move pruning (LMP)
- Futility: at low depth, skip quiet moves when eval + margin(depth) <=
  alpha. Not in check, not for captures/checks, not near mate bounds.
- LMP (move-count pruning): at low depth stop searching quiets after a
  depth-dependent number of moves.
- Pitfall: false stalemate when every move is pruned; make sure at least
  one legal move was found before scoring "no moves".
- Source: https://www.chessprogramming.org/Futility_Pruning

### ProbCut
- A shallow search with a raised beta predicts that the deep search will
  fail high; cut if so. Buro (1994, Othello). Worked in chess only in later
  engines (CPW credits Stockfish).
- Pitfalls: overlaps with NMP/LMR; needs tuning of margin and depth.
  Implementation detail "captures only with SEE >= margin" is UNVERIFIED
  (not on page).
- Source: https://www.chessprogramming.org/ProbCut

### Singular extensions (+ multicut, double/negative extensions)
- If the TT move has a lower-bound score at sufficient depth, search all
  other moves with a reduced depth and a window below the TT score; if all
  fail low the TT move is singular and is extended. If the excluded search
  itself fails high above beta, cut (multicut). Modern engines add double
  and triple extensions and negative extensions (listed on CPW's Search
  Progression page; exact rules UNVERIFIED).
- Pitfalls: search explosion (limit total extensions per ply), TT pollution
  from excluded-move searches (use a different key or don't store).
- Source: https://www.chessprogramming.org/Singular_Extensions

### Check extensions
- Extend when giving check (or in check), usually one ply. Some engines skip
  checks with negative SEE.
- Pitfall: explosion with spite checks; interaction with LMR.
- Source: https://www.chessprogramming.org/Check_Extensions

### Mate distance pruning
- Clamp alpha/beta to the best/worst possible mate score at this ply;
  return early if the window is empty. Safe; helps mate finding, little Elo.
- Source: https://www.chessprogramming.org/Mate_Distance_Pruning

### IID and IIR
- IID: with no TT move, run a reduced search to find one. IIR (Ed Schroder,
  Rebel, 2020): just reduce depth by one when there is no TT move, usually at
  PV and expected cut nodes above some depth. IIR has largely replaced IID.
- Sources: https://www.chessprogramming.org/Internal_Iterative_Deepening,
  https://www.chessprogramming.org/Internal_Iterative_Reductions

### Static evaluation correction history (essential, Phase 3/4)
- Track how far search results differ from static eval, in tables keyed by
  features: pawn structure hash, material, per-side non-pawn pieces, minor
  and major piece sets, continuation (previous two moves), threats. Add the
  (scaled, clamped) correction to the static eval before it is used by
  RFP, futility, NMP and so on.
- Update only when not in check, best move is quiet or none, and the bound
  is consistent with the direction of the error. EMA or history-gravity
  update with depth-based weight.
- Introduced in Caissa (Oct 2023), now in SF18's release notes. Gains grow
  with longer TC: important for TCEC.
- Pitfalls: never let a corrected eval reach mate/TB score range; keep the
  raw eval for NNUE-training labels (UNVERIFIED: our own design advice, not
  from the CPW page).
- Source: https://www.chessprogramming.org/Static_Evaluation_Correction_History

### Repetitions and the 50-move rule
- Keep a stack of Zobrist keys; compare only back to the last irreversible
  move, every second ply. Most engines score the first repetition inside
  the search as a draw.
- 50-move: halfmove clock >= 100 is a draw unless the side to move is
  mated (checkmate takes precedence).
- Pitfalls: graph history interaction (TT scores that depend on path);
  root mate-in-one at clock 100. "Upcoming repetition" detection (cuckoo
  tables) is not on the CPW page opened (UNVERIFIED; CPW links van
  Kervinck's 2013 upcoming-cycle paper).
- Sources: https://www.chessprogramming.org/Repetitions,
  https://www.chessprogramming.org/Fifty-move_Rule

### Syzygy in search
- WDL tables probed inside the search (not in qsearch) give exact
  win/draw/loss with 50-move awareness; DTZ at the root picks moves that
  convert. 3-5 men about 939 MiB, 6 men about 149 GiB, 7 men about
  16.7 TiB.
- Fathom (MIT, standalone probing code) is Fork's planned library:
  **USE** (log it in ORIGINALITY.md). Pyrrhic is a cleaned-up variant.
- Pitfalls: probe conditions, verified 2026-10-24 in Fathom's
  `src/tbprobe.h` at the pinned commit c9c6fef0
  (https://raw.githubusercontent.com/jdart1/Fathom/c9c6fef0dddc05d2e242c183acf5833149ab676d/src/tbprobe.h):
  the search-time WDL probe returns failure unless castling rights are zero
  **and** the halfmove clock is zero (so probe right after a capture or
  pawn move); the root DTZ probe requires zero castling rights but takes the
  halfmove clock as input; the root probe is documented as not thread-safe
  and meant for one call per search. DTZ50 lines can look odd (the header
  also warns DTZ may suggest unnatural moves); TB scores must stay below
  mate scores.
- Source: https://www.chessprogramming.org/Syzygy_Bases

---

## 4. Evaluation (Phase 4)

### Tapered PST evaluation
- Separate middlegame and endgame scores, blended by game phase from
  remaining material (weights N=1, B=1, R=2, Q=4; full board 24).
- Pitfall: clamp phase when promotions push material above the start.
  Packed mg/eg scores in one integer are a common trick (UNVERIFIED: the
  CPW Tapered Eval page only lists a forum thread titled "two values in one
  integer", re-checked 2026-10-24; no description on the page).
- Tuning: Texel's method (logistic regression of qsearch score vs game
  result; fit K first). Fork tunes on its own games only.
- Sources: https://www.chessprogramming.org/Tapered_Eval,
  https://www.chessprogramming.org/Texel%27s_Tuning_Method

### NNUE: features
- 768 baseline; HalfKP (king-relative, no king features); HalfKA (with
  kings); HalfKAv2 (both kings share a slot); horizontal mirroring
  ("_hm") so own king is on e-h; king input buckets (group king squares
  into a few buckets rather than 64).
- Threat inputs (SF18, 2026): extra attacker/target-pair features in a
  separate accumulator; pawn-pair features (SF19). Plan a later Phase 4
  step for them.
- Sources: https://www.chessprogramming.org/NNUE,
  https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md
  (REFERENCE ONLY)

### Accumulator updates, refresh tables ("Finny tables")
- Two accumulators (one per perspective), concatenated with side to move
  first. On a move, subtract the weight columns of removed features and add
  the new ones. King moves that change bucket or mirror side force a full
  refresh.
- Finny table: per thread, cache an accumulator plus the piece bitboards
  for each king bucket; a refresh then only applies the difference between
  the cached and current boards.
- Lazy updates: mark accumulators dirty and compute only when eval is
  needed.
- Pitfalls: stale accumulator after null move/unmake; perspective flip bugs.
  Test: incremental result must equal a from-scratch refresh on every node
  in debug builds.
- Source: https://www.chessprogramming.org/NNUE

### SIMD and quantisation
- int16 accumulator, clipped ReLU (or squared clipped ReLU, SCReLU) then
  int8 or int16 for the next layer; QA=255, QB=64 typical in bullet-style
  nets; Stockfish-style nets use 127 and scale 64.
- AVX2 (16 int16 lanes), AVX-512 (32 lanes, more registers), VNNI for
  int8 dot products; sparse-input kernels for the first dense layer.
- Pitfalls: int16 overflow with SCReLU (clip output weights or rearrange the
  multiply, e.g. the "Lizard" trick); keep a scalar path and test SIMD vs
  scalar bit-for-bit.
- Sources: CPW NNUE; nnue-pytorch docs (REFERENCE ONLY)

### Output buckets / layer stacks
- Choose the output layer (or a whole small sub-network) by piece count,
  e.g. 8 buckets via (pieces - 1) / 4. Cheap and a clear gain.
- Source: CPW NNUE; nnue-pytorch docs

---

## 5. Training (Phase 4)

### Self-play data generation
- Fork plays itself (fixed nodes or depth per move), from diverse openings
  (Lichess CC0 game positions or random early moves); store position,
  search score and game result. Filter: skip positions in check, with a
  capture as best move, or with mate scores (quiet-position filtering;
  see arXiv 2412.17948 and Texel page).
- Diversity matters (AZ_db result in research.md section 4).
- Source for formats: bullet docs (text `<FEN> | <cp> | <result>`, or
  viriformat binpack recommended). https://github.com/jw1912/bullet

### Bootstrapping from a handcrafted eval
- Generation 0 data is labelled by Fork's tapered-PST search; train net 1;
  regenerate with net 1; repeat. Each generation's provenance (engine
  version, net hash, settings) goes in ORIGINALITY.md.
- Pitfall: early generations inherit PST blind spots; mix in more game
  result (lower lambda) early. (Fork's own reasoning; no single opened
  source describes this chain end to end.)

### WDL / score blending
- Target = lambda * sigmoid(score / scale) + (1 - lambda) * result; scale
  around 400 cp; nnue-pytorch reports an MSE exponent around 2.6 working
  well. Lambda is tuned per generation.
- Source: nnue-pytorch docs (REFERENCE ONLY)

### Rescoring
- Re-evaluate old positions with a newer, stronger Fork net/search to
  improve labels (SF19 rescored all its data with a Leela net; Fork may only
  rescore with Fork).
- Source: https://stockfishchess.org/blog/2026/stockfish-19/

### Trainer
- bullet (MIT, Rust, GPU). **USE**. Alternative: write Fork's own PyTorch
  trainer. nnue-pytorch is REFERENCE ONLY.

---

## 6. Time management (Phase 5)

- Baseline: time/20 + increment/2 per move is competitive. Soft limit
  checked when starting a new iteration; hard limit checked every N nodes.
- Scale the soft limit by best-move stability (how many iterations it has
  stayed the same), score drop/instability, and the share of nodes spent
  under the best move ("node-based" time management; listed on CPW Search
  Progression, details UNVERIFIED).
- Stop early with one legal move; do not start an iteration that cannot
  finish (e.g. more than half the budget used).
- Long increment TC (TCEC 30'+3" to 120'+12", no ponder): with large
  increments the engine can spend close to the increment plus a slice of
  the bank each move; never let the bank fall below a safety reserve.
- Pitfalls: GUI/network lag (Move Overhead option), clock checks too rare
  at very high NPS, OS scheduling under load (Phase 5 stress test).
- Sources: https://www.chessprogramming.org/Time_Management,
  https://wiki.chessdom.org/Rules (TCEC time controls)

---

## 7. SMP (Phase 6)

### Lazy SMP
- All threads search the root on a shared TT; diversity from varied depths
  (e.g. odd helpers one ply deeper) and different ordering. Pick the final
  move by depth/score-weighted vote across threads.
- Term from Julien Marcel (end of 2012); Stockfish switched from YBW in
  SF7 (Jan 2016). Scales in NPS and strength beyond 8 cores.
- Pitfalls: thread-local histories/killers; shared counters cause cache
  contention (keep per-thread node counts); TT races must be tolerated.
- Source: https://www.chessprogramming.org/Lazy_SMP

### NUMA
- Local memory is faster; bind each thread to a node and allocate/first-touch
  its data there. Stockfish 17 added a NumaPolicy option with up to 2.8x
  speedup on 100+ core dual-socket machines (replicating net weights per
  node is the likely reason, UNVERIFIED: release note gives no mechanism).
- Fork plan: per-node copy of NNUE weights, per-thread data on its node,
  TT first-touch spread across nodes.
- Sources: https://www.chessprogramming.org/NUMA,
  https://stockfishchess.org/blog/2024/stockfish-17/

### Windows processor groups (local testing only)
- A group holds up to 64 logical processors. Up to Windows 10, a process is
  confined to one group unless threads are assigned with
  SetThreadGroupAffinity. **From Windows 11 / Server 2022, processes span
  all groups by default** with a "primary group"; explicit binding is still
  needed for NUMA control.
- TCEC runs Linux (per Wikipedia), so the Linux path (sched_setaffinity,
  libnuma or /sys topology) is the one that matters for competition.
- Source: https://learn.microsoft.com/en-us/windows/win32/procthread/processor-groups

### Scaling measurement and testing
- Measure NPS and time-to-depth per thread count, but judge by Elo: SPRT
  with fixed bounds (e.g. [0, 2] or [0, 5]), pentanomial statistics,
  fastchess, unbalanced books (UHO) for strong engines, OpenBench for
  distributed testing.
- Pitfall: stopping SPRT early; too-tight bounds cost many games.
- Source: https://www.chessprogramming.org/Sequential_Probability_Ratio_Test
