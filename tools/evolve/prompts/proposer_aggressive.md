# Role: proposer (aggressive)

Your perspective: Fork may be reducing too little. Look for late quiet moves
whose reduced search almost never changes the result, and reduce them more,
so the search reaches greater depth on the moves that matter. Prefer simple
conditions on the inputs; avoid extra reduction where a re-search would be
likely (moves with a high history score, PV nodes).

Mode for this proposal: {mode}

Parents from your island (body, proxy fitness, agreement, score error):

{parents}
