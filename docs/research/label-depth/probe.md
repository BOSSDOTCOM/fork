# Label depth: the rate probe and the start of the arms

Written 2026-11-10, about 7:45 AM EST. The design is section 1 of docs/research/labels-teacher/report.md on branch
research/labels-teacher ("Item 2: label depth at equal generation time"). The owner approved it on 2026-11-09 as
designed: layout A, one binary for the whole experiment, the arms in place of the main generation for 40 hours,
and the decision rule declared there. Every number below is from the runs described. Nothing here is adopted.

## Setup

- **g4b stopped and sealed** through the Control Center's stop-and-seal at 6:41 AM EST (job seal-g4b). Main
  generation stays idle until the arms end.
- **One binary:** a clang PGO build of phase-4 a4ee674 (net s512ppr3), built the way the Control Center's
  start_part.sh builds (cmake/pgo.cmake, then fork and fork_datagen) in its own WSL clone. `fork version`:
  0.3.0-dev+a4ee674, clang 21.1.8, arch native. Bench 10,374,064 / 677c436fa145e07f (= tests/bench-s512ppr3.ref).
  SHA-256: fork 59e637fe613b71189329c9e31dd07ec51df96ef5d77b5d388d9dea6166608000, fork_datagen
  ff408d92e087ba123c79fd9443790e8b35703f74ee0398b8d8ef35f65602dac1. ld_arms.sh checks the bench, network and
  commit before every start.
- **Settings:** g4b's standing settings except `--nodes` and `--hash-mb`: adjudication 700 cp for 8 plies,
  `--save-percent 50 --unsaved-nodes 4000 --check-nodes 2000`, shard 1024 MB, Syzygy 3-4-5. 3 threads per arm.

  | arm | `--nodes` | `--hash-mb` |
  |---|---|---|
  | D20 | 20,000 | 1 |
  | D50 | 50,000 | 3 |
  | D100 | 100,000 | 5 |

- **Seed: 2026110900 in every arm.** The Control Center's planner gives each new part the largest earlier local
  seed plus one (generation_control.py; g4b used 20261117, so the next part gets 20261118). It reads only sealed
  part manifests (names g<N><letters>), so it never sees the ld-* runs. A seed taken from that sequence would
  make a later g4 part replay D20's games exactly: same seed, book, binary and settings. 2026110900 (the approval
  date, then 00) is far from the sequence and from every committed seed. It is also below the 10^12 that cloud
  seeds start from (DESIGN.md, 2026-10-30).
- **Pairing by game index is exact.** The design marked this UNVERIFIED. fork_datagen's worker w plays games w,
  w + T, w + 2T, ... (src/datagen/datagen_main.cpp; T = 3 in every arm). Game g's opening, random plies and save
  stream depend only on (seed, g). So game g opens the same way in every arm, and the deeper arms' games are a
  prefix of D20's per worker, until play diverges.

### Openings: a byte-identical reduced book (an infrastructure change, not a design change)

Each fork_datagen process keeps its whole book in memory. A test start of the three arms with lichess-2026-09.epd
(13,943,421 openings, 928 MB) used **1.38-1.41 GB of RSS per process**, about 4.2 GB of WSL's 5.9 GB. That left
329 MB available and the machine swapping, so the test was stopped after a minute. Instead, ld_book.py writes the
2,500,000 openings the full book gives this seed's first 2.5 M games (fork_datagen opens game g from
book[perm[g mod N]], perm being its seeded Fisher-Yates shuffle). It writes them in the order that gives every game
g < 2.5 M the same opening from the reduced file. The result is lichess-2026-09-s2026110900-k2500000.epd, SHA-256
f705366e5a3f4b803ce392f2b9da2f474e181bbcefecef0e0170e569ccdae736, 166,354,749 bytes.

**Check (ld_book_check.sh):** fork_datagen with the full book and with the reduced file, same seed, 3 threads,
wrote **byte-identical shards** at D20's settings (101 games, 9,193 positions, all 3 shards identical) and at
D100's (33 games, 3,194 positions, all 3 identical). With the reduced file each arm uses about 330 MB. The arms'
games stay below 2.5 M: D20 is projected at about 0.8 M games in 40 hours (below).

### Stopping

The arms run as one Windows jobctl job (type datagen, name ld-arms, so memwatch can stop it). Its command is
`wsl.exe -d Ubuntu -- bash ld_arms.sh ...`. A test showed that ending the Windows-side process does not signal
the Linux processes by itself. The runner traps the hangup instead: its log shows "stopping every arm (a hangup
or a closed output)" at 6:48:10 AM, right after the jobctl stop, and then "stopped". A check run a moment before
that still saw the three processes, and a kill by hand went out about then too, so **that the hangup alone always
ends them is UNVERIFIED**. A stop of ld-arms is followed by a check that no ld-* fork_datagen is left. Its
once-a-minute heartbeat write also catches a closed pipe. A stop always ends all three arms together, at a game boundary in
every shard (each game is written whole, so a stopped shard ends with a complete game).

## The probe (layout A, 9 threads, same seed)

The probe ran from 6:51:59 to 7:29:55 AM EST, beside the other jobs: idea 23's pilot, the defense-slice pilot and
the night queue. The CPU-load log averaged **95% busy** (load 8-14 on 12 logical CPUs). The positions targets
were sized for 30 minutes from an assumed rate; the real rate was lower, so the arms ran 36.8-39.6 minutes. Each
arm ended at its target and wrote its run json. From the run jsons, the shards (ld_stats.py, python-chess replay)
and the trainer's own filter (`fork-train stats`):

| | D20 | D50 | D100 |
|---|---|---|---|
| seconds (its own run) | 2,206.8 | 2,295.5 | 2,375.7 |
| games | 12,188 | 5,410 | 2,939 |
| records | 1,150,167 | 520,162 | 280,173 |
| records per game | 94.4 | 96.1 | 95.3 |
| records/s (whole run) | 521.2 | 226.6 | 117.9 |
| records/s at 1,800 s (all three running) | 522.9 | 227.9 | 116.8 |
| unsaved share | 45.63% | 45.67% | 45.77% |
| in-check share | 8.55% | 8.40% | 8.22% |
| saved, not in check | 45.82% | 45.93% | 46.01% |
| mate-band saved (\|score\| > 20,000) | 8,519 | 4,178 | 2,319 |
| tactical saved (capture or promotion played) | 112,984 | 50,090 | 27,072 |
| **kept by the trainer** (fork-train stats; the script's estimate is identical) | **405,497** | **184,646** | **99,506** |
| kept per record | 0.3526 | 0.3550 | 0.3552 |
| kept per saved record | 0.648 | 0.653 | 0.655 |
| nodes_spent per record (model, section 0.1) | 11,181 (11,117) | 25,026 (24,794) | 48,092 (47,587) |
| nodes/s per thread (nodes_spent / s / 3) | 1.943 M | 1.890 M | 1.891 M |
| median completed depth, own 200 positions, fresh table [min-max] | 8 [3-13] | 10 [7-16] | 11 [8-22] |
| the same on D20's 200 positions | 8 [3-13] | 10 [7-16] | 11 [8-20] |

The depth sample is 200 saved, not-in-check positions per arm (ld_sample.py, reservoir sampling, seed 20261110).
They are searched by tools/datagen/measure_nodes.py with the experiment's fork, `ucinewgame` before each, at the
arm's nodes and Hash (ld_depth.sh). In generation the table carries over within a game, so in-game depths may be
a little higher.

### The model's assumptions

- **Yield ratios (kept positions per second against D20's):** at the common time of 1,800 s, **D50 0.4388** and
  **D100 0.2251**, against the model's 0.448 and 0.234 (**-2.1% and -3.8%**). Over each arm's whole run the
  ratios are 0.4378 and 0.2280. Both are within the 10% tolerance, so **the arm sizes are not restated**.
- **Nodes per record:** within 0.6-1.1% of the model.
- **Speed per node:** D50 and D100 run 2.7% fewer nodes per second per thread than D20 (larger tables and
  deeper trees); this is the main part of the yield shortfall. The shares (saved, unsaved, in check, kept) move by
  less than 0.4 points with depth.
- **Absolute rate:** 1.89-1.94 M nodes/s per thread, against the 3.05 M of g3 (10 threads on a quieter machine).
  The machine was oversubscribed during the probe. Layout A equalises CPU between the arms, so this changes the
  arms' volume, not the comparison.

### Projected arm sizes at the probe's rates (40 hours, 144,000 s)

| arm | records | kept | passes at 400 M seen | design's prediction (kept) |
|---|---|---|---|---|
| D20 | 75.3 M | 26.6 M | 15 | 36.2 M |
| D50 | 32.8 M | 11.7 M | 34 | 16.2 M |
| D100 | 16.8 M | 6.0 M | 67 | 8.5 M |

The absolute volumes are about 27% below the design's because of the machine's load, while their ratios hold.
The load during the 40 hours will differ, so these are estimates. With about 67 passes, D100 is more exposed
to the volume limit the design flags (section 1.4: a best checkpoint before superbatch 40 is reported as
volume-starved). The training recipe stays as declared (80 superbatches, 400 M seen).

## The arms

Job **ld-arms** (Windows jobctl, type datagen) started at **7:31:28 AM EST on 2026-11-10**:
`ld_arms.sh ld ~/fork-data/ld-arms 2026110900 144000 999000000 999000000 999000000`. The runs are ld-d20, ld-d50
and ld-d100; the targets are out of reach, and the 144,000 s limit stops all three at once at about
**11:31 PM EST on 2026-11-11**. Each arm is then sealed as its own part with its own manifest.

## Files

- `ld_arms.sh`: the runner (probe and arms).
- `ld_book.py`, `ld_book_check.sh`: the reduced book and its byte-identity check.
- `ld_stats.py`: per-arm statistics; `ld_sample.py`, `ld_depth.sh`: the depth sample.
- `probe-stats.json`: ld_stats.py's output for the probe.

## Stop and resume (2026-11-10)

- **The stop.** At 12:46:20 PM EST memwatch stopped ld-arms: the owner's safety rule fired because Windows' free
  memory stayed under 1 GB for 15 minutes (about 800 MB at the stop), while several agents were compiling at once.
  The runner stopped all three arms together ("stopping every arm (a hangup or a closed output)"), and the shards'
  last writes are from 12:46:20-24 PM. Segment 1 ran from 7:31:28 AM to 12:46:24 PM: **18,896 s** by the wall
  clock (epochs 1794313888 to 1794332784), which agrees with the Windows clock. At the stop: D20 11.34 M records
  (119,273 games), D50 4.96 M (51,785), D100 2.52 M (26,410), by fork_datagen's last progress lines.
- **A clock note.** fork_datagen's own seconds (steady_clock) run about 5% ahead of the wall clock in this WSL
  machine: its last line reads 19,920 s for those 18,896 s. The probe shows the same: D100's run json gives 2,375.7 s
  inside a 2,276 s window. So the probe's records/s figures are about 4-5% low in absolute terms, the same for every
  arm, which leaves the ratios unchanged. The limits use the wall clock (`date +%s`). The cause is UNVERIFIED.
- **The resume.** fork_datagen has no game-index offset, so all three arms resumed together with **one new seed,
  2026110901** (segment 2, job ld-arms2, `ld_arms.sh ld2 ~/fork-data/ld-arms2 2026110901 125104 ...`), for the
  remaining **125,104 s** (144,000 - 18,896). Equal CPU per arm holds, because both segments ran the three arms at
  the same moments. No game is replayed: game g's random plies and save decisions come from (seed, g), and the
  openings from the seed's shuffle. Game i still opens alike in every arm within segment 2. Segment 2 reads
  lichess-2026-09-s2026110901-k2500000.epd (ld_book.py; SHA-256
  da1c2dd85186c7e291cb73fb1c405b1fac4c329d96d75298ded57ae9ed090374). Its shards are byte-identical to the full
  book's at D20's settings (89 games, 9,293 positions) and D100's (29 games, 3,070 positions).
- **Times.** Segment 2 started at 2:55:03 PM EST (epoch 1794340503) and ends at about **1:40 AM EST on
  2026-11-12**.
- **The seal** (ld_seal.py `arm ... --segment ... --segment ...`) makes each arm one part from both segments:
  segment 1's files keep the names `<run>-wWW.vf` (worker 2 split into the held-out file and the rest), and
  segment 2's become `<run>-s2-wWW.vf`. The manifest's openings are lichess-2026-09.epd, every game's opening
  being the full book's for its segment's seed, and each segment's seed, file, times and counts go into
  `settings.segments`.
- **No replay, checked on the data** (ld_overlap.py, 2:58 PM EST, segment 2's first games against all of
  segment 1). The start position is the viriformat start board, i.e. after the opening line and its random
  plies. A game is identical when its start position and every move match. The book-line overlap is estimated
  from the two seeds' shuffles over each segment's played game indices.

  | arm | segment 1 games | segment 2 games so far | same start position | same start and first 8 moves | identical games | book line also used in segment 1 (estimate; expected by chance) |
  |---|---|---|---|---|---|---|
  | D20 | 119,282 | 1,578 | 0 | 0 | **0** | 21 (20.1) |
  | D50 | 51,788 | 695 | 0 | 0 | **0** | 4 (3.8) |
  | D100 | 26,412 | 372 | 0 | 0 | **0** | 3 (1.0) |

  The games that share an opening line still start from different positions: the new seed's random plies make
  them differ. Segment 1 has no repeated start position either: 119,282 distinct in D20. The seal repeats this
  check over both whole segments (ld_seal.py) and refuses to seal if any game is identical to an earlier segment's.
  Fault-injected: with the probe's data given as both segments, it found 2,939 of 2,939 games repeated and sealed
  nothing.
- **Pairing and workers:** both segments run 3 threads per arm, worker w playing games w, w + 3, ... of its segment;
  within segment 2, game i has the same opening and random plies in every arm, as in segment 1.
