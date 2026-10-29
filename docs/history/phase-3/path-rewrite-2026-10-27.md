# The path rewrite of 2026-10-27: old and new commit hashes

Before `milestone-c` and the deliverable 8 variant branches were first
pushed, their twelve unpushed commits (after 2a7541f) were rewritten:
user-name paths that had entered two files (the heuristic-discovery
harness's `tools/evolve/config.json`, and a `SyzygyPath` option that
`tools/sprt.sh` copied into `docs/history/phase-3/sprt-log.md`) became the
forms of the 2026-10-24 rewrite (`/mnt/c/Users/<user>/`, `~/`). File contents
otherwise, the code, the messages, authors and dates are unchanged; the
code of every branch tip is byte-identical before and after. Two commits
contained no such path and kept their hashes (b7ab410, a11a396).

Two commit messages cite pre-rewrite hashes: d51462f (its cherry-pick line
names cd55f82) and 642fb94 (it names cd55f82 and f1233b4). This table keeps
them traceable.

| Old | New | Branch | Subject |
|---|---|---|---|
| e66a9a2 | 980b891 | milestone-c | Idea 23: the heuristic-discovery harness (deliverable 8c preparation) |
| e07ab24 | 7cbf45b | milestone-c | Idea 23 harness: the dry run, and the perft-count fix it found |
| 3189e2d | 4d65dec | milestone-c | SPRT log: keep-exact INCONCLUSIVE at the owner's cap, into the removal round |
| cd55f82 | afe8946 | milestone-c | The last info line names the move played, also after a reported fail |
| e166f7c | 93875fb | milestone-c | SPRT log: Syzygy probing ACCEPTED by the owner's decision |
| aaff65c | eb2068b | d8-a | Deliverable 8 split, (a): the increment fix alone |
| 1c52c7a | 66eafae | d8-b1 | Deliverable 8 split, variant B1: reserve the overhead the increment does not refund |
| f1233b4 | d51462f | d8-b2 | The last info line names the move played, also after a reported fail (the cherry-pick of cd55f82) |
| f375e7a | 642fb94 | d8-b2 | Deliverable 8 split, variant B2: an extra overhead of reserve only in the danger zone |
| 890ad3b | 07726f7 | d8-c | Deliverable 8 split, variant (c): the iteration rule alone |

The SPRT log's entries for the variants and the stress tests name the old
hashes where they ran before the rewrite (the builds were made from them;
the code is the same).
