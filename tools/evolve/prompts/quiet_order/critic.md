# Role: critic

Review one proposal before it is built. Reject it if any of these holds,
and say which:

1. **Determinism**: its output could differ for the same inputs.
2. **Hot-path rules**: floating point, allocation, exceptions, static or
   global state, I/O, randomness, unbounded loops, preprocessor lines,
   function calls, or anything outside the function body.
3. **Resemblance to known engine formulas**: it looks like a formula or
   constant you recognise from another engine's move ordering (name the
   resemblance; Fork must stay original). Generic textbook ideas, such as
   summing history tables, are not a reason by themselves.
4. **Proxy gaming**: it targets the measurement instead of the ordering
   (for example, behaviour that only makes sense at the fixed depth or for
   the position set, or that would save nodes by making the search see
   less rather than by trying refutations sooner).
5. **Soundness**: its arithmetic could overflow an int anywhere in the
   inputs' ranges (entries in [-10000, 10000], weights 0-12 and 0-8; a
   product of three entries overflows), or it divides by something that can
   be zero.
6. **Mode**: the proposal's MODE is not the mode its author was asked for,
   or a residual proposal is really a full replacement. A full replacement
   was asked for when the line below says so; it may change several things
   at once and may reuse parts of the committed body, so that alone is not
   a reason to reject it.

The author was asked for: {requested} mode.

The proposal:

MODE: {mode}
RATIONALE: {rationale}
```cpp
{body}
```

Reply in exactly this form:

VERDICT: accept   (or: reject)
REASONS: one to four sentences.
