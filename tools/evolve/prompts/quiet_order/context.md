# Fork heuristic discovery: shared context (quiet move ordering)

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
  preprocessor lines, no library calls. It runs for every quiet move the
  search generates, so keep it cheap.
- **Deterministic.** The same inputs must give the same output.

## Quiet move ordering, in general terms

An alpha-beta search cuts off a node as soon as one move proves the node
will not be chosen, so the earlier that move is tried, the fewer moves are
searched. After the hash move and the winning captures, the search tries the
quiet moves (no capture, no promotion) in the order of a score built from
history tables: counters, learned during the search itself, of which quiet
moves caused cutoffs before. Each table entry rises when its move causes a
cutoff and falls when an earlier-tried move's cutoff makes it look worse,
and stays within [-10000, 10000]. Fork keeps three tables for quiet moves:

- the **butterfly** table: the side to move, the move's from-square and
  to-square, whatever happened before;
- the **reply** table: the move (its piece and destination) paired with the
  opponent's last move, so it learns which answers work against which moves;
- the **follow** table: the move paired with the side's own previous move
  (two plies back), so it learns plans that continue.

A node reached by a null move, and the root, have no previous move for the
reply table (and the follow table needs the move two plies back), so those
entries can be missing. How the three entries should combine into one score
is the open question you are working on. No particular engine's rule is the
reference here: Fork's own combination and the inputs below are all you
build on.

## The region: `quiet_score`

```cpp
struct QuietScoreInputs {
  int butterfly;      // the mover's butterfly entry, [-10000, 10000]; 0 when the table is not used
  int reply;          // the reply table's entry, [-10000, 10000]; 0 when has_reply is false
  int follow;         // the follow table's entry, [-10000, 10000]; 0 when has_follow is false
  bool has_reply;     // the reply entry exists (the node has a previous move)
  bool has_follow;    // the follow entry exists
  int reply_weight;   // a tuned weight for the reply entry, in quarters: 6 means 1.5 (range 0-12)
  int follow_weight;  // a tuned weight for the follow entry, in quarters: 4 means 1.0 (range 0-8)
};

constexpr int quiet_score(const QuietScoreInputs& s) {
  // YOUR BODY HERE
}
```

The committed body, Fork's current ordering:

```cpp
  int score = s.butterfly;
  if (s.has_reply) score += s.reply * s.reply_weight / 4;
  if (s.has_follow) score += s.follow * s.follow_weight / 4;
  return score;
```

The function is `constexpr` (C++20) and must compile as such with both GCC
11 and Clang 19 with every warning an error: call no functions at all (no
library math, no `std::` helpers), declare no `static` or `thread_local`
variables. Write plain integer code: locals, `if`, `?:`, arithmetic, `<`
and `>`, bounded loops. Higher scores are tried first; only the order of
the moves at one node matters, not the scale. The caller clamps your result
to [-32767, 32767], but your own arithmetic must not overflow an `int`
anywhere in the inputs' ranges (a test evaluates the body at every extreme
and refuses one that overflows): a product of two entries (at most 100
million) is safe, a product of three is not; divide first if you need more.

- **Residual mode** (the default): keep the committed combination and make
  one well-chosen change (a term, a condition, a weight's use).
- **Full replacement** (only when asked): write your own combination from
  scratch.

## How a candidate is measured

Every candidate is built and checked (perft, the search's correctness
tests, determinism, both compilers), then searches a few thousand positions
from Fork's own games to a fixed depth (12 plies), each from a fresh state
(the history tables start empty at every position, so the ordering must
learn quickly). Fitness is the total number of nodes searched: fewer is
better, reported as the reduction against the committed body with a 95%
interval over the positions. A candidate whose best moves and scores at
that depth differ from the committed body's on too many positions is
refused (the equivalence guard): the aim is the same search for fewer
nodes, not a different search.

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
