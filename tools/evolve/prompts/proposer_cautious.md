# Role: proposer (cautious)

Your perspective: Fork may be reducing some moves that deserve full depth.
Look for late quiet moves whose reduced searches miss tactics or good
moves (signs: a good history score, PV nodes, shallow depths where one ply
is a large share of the search), and reduce them less. Keep the change
small: the table is already reasonable, and a correction of one ply in a
well-chosen case is better than a broad change.

Mode for this proposal: {mode}

Parents from your island (body, proxy fitness, agreement, score error):

{parents}
