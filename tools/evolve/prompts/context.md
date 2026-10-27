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

## The region: `lmr_correction`

```cpp
struct LmrContext {
  int depth;        // remaining depth at the node, in plies (>= LmrMinDepth, 3)
  int move_number;  // the move's number in the order, 1 = first (>= LmrMinMove, 4)
  int base;         // the table's reduction for (depth, move_number), in plies
  int history;      // the move's butterfly history score, in [-10000, 10000]
  bool on_pv;       // the node is on the principal variation
};

int lmr_correction(const LmrContext& c) {
  // YOUR BODY HERE
}
```

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
