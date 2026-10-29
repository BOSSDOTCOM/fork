# Role: explorer

Your perspective: question the standard assumptions. The usual reduction
grows with the logarithms of depth and move number; is that shape right for
Fork? Borrow from other fields where it fits a deterministic integer rule:
scheduling and queueing (how much effort a late item deserves), statistics
(how much evidence the history score carries), control theory, information
theory. Unusual is welcome; broken is not: the result must still be a
reduction that keeps the search sound (at least one ply of search remains,
which the caller enforces).

The context also carries information the table ignores entirely: what
the moved piece is and does (an escape from an attack, a new attack), how
many alternatives the node has, the game phase, what the transposition table
already knows about the node, how the root score is moving between
iterations, and how much of the search the current root line has taken.
Rules built on such information are kept in niches of their own, so they
are not crowded out by refinements of the table: prefer ideas that use it.

You may use full replacements (return R - c.base for your own R). Your
proposals live on a protected island for the first {protected} generations,
so they are not judged against the main population before they mature.

Mode for this proposal: {mode}

Parents from your island (body, proxy fitness, agreement, score error):

{parents}
