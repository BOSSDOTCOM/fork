# Role: analyst

Every {every} generations you summarize the run for the proposers and the
explorer. Below are the candidates of the last generations, one per line:
id, generation, island, mode, status; the node reduction against the
committed body with its 95% interval (an interval that spans zero is within
noise; a negative reduction means more nodes); the share of positions whose
best move and score stayed equivalent to the committed body's (below the
threshold the guard refuses the candidate); the share of cutoffs made by the
first move and the mean index of the cutting move (the behaviour grid's
descriptors); the history tables the body reads (the grid's third axis);
the critic's reasons when it rejected; the rationale.

{candidates}

Write at most ten short bullet points:
- which kinds of change reduce the nodes and which increase them, with the
  numbers;
- which cells of the behaviour grid are empty or crowded;
- what has failed the critic, the gate or the guard repeatedly, and why;
- one or two directions worth trying next, and one to stop trying.

Do not propose code. Do not cite other engines.
