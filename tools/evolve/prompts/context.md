# Fork heuristic discovery: shared context

You are one agent in Fork's heuristic-discovery loop (Fork's ideas.md idea
23). Fork is an original chess engine; its code must stay demonstrably
original.

## Rules you must follow

- **Clean room.** Do not consult, recall or reproduce any other chess
  engine's source code, formulas or constants (Stockfish, Ethereal, Berserk,
  Weiss, Leela or any other). Reason from first principles, from Fork's own
  measurements given below, and from general knowledge of search.
  Model memory can reproduce famous formulas without noticing: if an idea
  looks like a known engine's formula, say so in your rationale.
- **Only the region.** You write the body of one C++ function, nothing
  else. Anything outside it is rejected before it is built.
- **Hot-path rules.** Integer arithmetic only (no float or double), no heap
  allocation, no exceptions, no static or global state, no I/O, no
  randomness, no loops whose length is not bounded by the inputs, no
  preprocessor lines. It runs at every late quiet move of the search.
- **Deterministic.** The same inputs must give the same output.

## Late move reductions, in general terms

An alpha-beta search orders the moves at a node so that the best ones are
likely to come first. Moves late in that order rarely turn out best, so the
search can look at them less deeply first: a reduced, zero-window search
that only asks whether the move beats the best score so far. If it does,
the move is searched again at full depth; if not, the saved effort goes to
the moves that matter. Reducing too much misses good late moves (tactics
found too late); reducing too little wastes time that a deeper search of
the main line would use better. Which information predicts that a late move
is safe to reduce, and by how much, is the open question you are working
on. No particular engine's rule is the reference here: Fork's own table and
the inputs below are all you build on.

## The region: `lmr_correction`

```cpp
struct LmrContext {
  int depth;        // remaining depth at the node, in plies (>= LmrMinDepth, 3)
  int move_number;  // the move's number in the order, 1 = first (>= LmrMinMove, 4)
  int base;         // the table's reduction for (depth, move_number), in plies
  int history;      // the moving side's butterfly history score for the move, in [-10000, 10000]
  bool on_pv;       // the node is on the principal variation
  int piece;        // the moved piece: 0 pawn, 1 knight, 2 bishop, 3 rook, 4 queen, 5 king
  bool threatened;  // the opponent attacked the piece's square before the move (the move may escape a threat)
  bool attacks;     // from its new square the piece attacks an enemy knight, bishop, rook or queen
  int quiet_moves;  // the number of quiet moves generated at this node (how many alternatives there are)
  int phase;        // game phase from the material left: 24 with all pieces, 0 with only kings and pawns
  int entry_bound;  // this node's transposition-table entry: 0 none, 1 upper bound, 2 lower bound, 3 exact
  int entry_depth;  // that entry's depth in plies, -1 without an entry
  int score_trend;  // the root score's change between the last two finished iterations, in centipawns,
                    // in [-1000, 1000] (negative: the engine's view of its position got worse)
  int branch_share; // per mille of the last finished iteration's nodes spent under the root move this
                    // line starts with, 0 to 1000 (0 in the first iteration)
};

constexpr int lmr_correction(const LmrContext& c) {
  // YOUR BODY HERE
}
```

The function is `constexpr` (C++20) and must compile as such with GCC 11
and Clang 16 to 19: call only `constexpr` functions (no library math, no
I/O), and declare no `static` or `thread_local` variables. Write plain
integer code: locals, `if`, `?:`, arithmetic and bounded loops.

The search reduces a late quiet move (not in check, not a capture or
promotion) by `base + correction * strength / 64` plies, where `strength`
is a tunable coefficient (64 by default), clamped so the reduced search
keeps between 1 ply and the full depth. A reduced search that beats alpha
is re-searched at full depth.

- **Residual mode** (the default): return a small correction to the table,
  in plies (usually -2 to +2). Returning 0 keeps the current search exactly.
- **Full replacement** (only when asked): compute your own reduction R and
  return `R - c.base`.

The table: `base` is round(log2(depth) * log2(move_number) / 4.5); for
example 1 ply at (3, 3), 2 at (8, 10), 3 at (12, 20), 5 at (20, 30).

## Fork's measurements (bench, 46 positions to depth 13)

{statistics}

## What has been tried

{history}

## Analyst's notes

{insights}

## Your answer

Reply in exactly this form:

MODE: residual   (or: full)
RATIONALE: two to five sentences: what the change does, why it should help,
and any resemblance to a known formula.
```cpp
...the function body only...
```
