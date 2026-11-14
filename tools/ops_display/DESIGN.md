# Fork Operations Display: design for approval

Status: **proposal, nothing built** (2026-11-14). Branch `tools/cc-dashboard`, not pushed.
Mockup: `mockup/dashboard-mockup.html` beside this file (open it in a browser; it is a clickable prototype).

## 1. What it is

A live, display-only screen of the whole pipeline: the 30-minute sweep, but continuous and readable.
It shows what is running, what is waiting, what just finished, what needs the owner, and how the engine's
strength is moving.

**It only displays.** It has no control that starts, stops, seals, queues, adopts or edits anything, and no
code path that could. The existing Control Center keeps its controls and is not touched (section 9).

## 2. Decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| 1 | Front end: a browser page served by a small local Python server (standard library only), or more tkinter | Browser page. The mockup is that page; tkinter cannot do this layout, and no new package is needed |
| 2 | Existing Control Center (start / stop / seal, watchdog) | Leave every file as it is. `notify.py`, `seal_part.py` and `start_part.sh` are used by the cloud watcher, the VM setup and the label-depth chain, so nothing there can be removed safely. The new display is a separate program in its own folder |
| 3 | "Seen" on an attention item (dims it on this screen, stored in the display's own folder) | Keep it: it changes nothing in the pipeline. Say so if even that should go; items would then clear only when their cause clears |
| 4 | Network polls: GitHub (shard progress of the one or two live runs, every 2 minutes) and Kaggle (session state every 5 minutes, only while a session runs; quota every 30 minutes) | On, read-only, through the existing `gh` login and the Kaggle CLI. Without them the display still works but shows no progress inside a stage and a quota figure as old as the last session |
| 5 | Live PC generation rate lives only inside WSL | Read the part's log through the WSL share only while a part is running and the distro is already up; never start WSL, and never between 1:20 and 2:30 AM EST |
| 6 | Name and place | "Fork Operations Display", `tools/control_center/dashboard/`, its own desktop shortcut |
| 7 | Small additions to production scripts that would make the display exact where it now infers (section 8) | None needed to build. Each is listed for the production session to take or leave |

## 3. Screen

One full screen, fixed hierarchy (see the mockup):

- **Status strip**: overall state (the worst state of any alert), default net, latest gauntlet rating with
  its interval, gap to Stockfish with its interval, adoptions this week by day, engine commit, clock (EST).
- **Situation** (centre): the pipeline as connected nodes: PC generation, cloud VM generation, training data,
  Kaggle training, search ideas, GitHub lanes A and B, engine, gauntlet, and the loop back (the default net
  labels new data). Each node carries a status light, one key number and one line of context; active links
  show flow. Above it, one generated sentence says what is happening now.
- **Testing** (left): one card per lane: plain-language name, kind, Elo with its 95% interval, games, the
  likelihood ratio between its two bounds, a countdown to the next result, shard progress; then the queue
  ahead and the recent verdicts with a one-line meaning.
- **Alerts** (top right), **Progress over time** (right), **Training**, **Data**, **Machine** (bottom row),
  and an **event ticker** along the foot.
- **Focus**: keys 1 to 7 or a click on a panel header fill the screen with that panel and its detail
  (Testing shows the likelihood ratio and Elo by stage, the pair-score distribution, the stage table, the
  test's design). Esc returns.

Visual rules:

- Dark by default, light on a key. Colour means state only: nominal, active, attention, failure, plus a
  neutral for idle. Each state also has its own shape (disc, ringed disc, triangle, square, hollow ring), so
  it never rests on colour alone. The four colours were checked for colour-blind separation on both
  backgrounds (worst pair 17.0 dark, 14.8 light, against a target of 8).
- Data marks (lines, bars, sparklines) are drawn in ink, never in a state colour. A rejected or capped test
  is a normal outcome and stays neutral; red is kept for things that are broken.
- Labels in Bahnschrift (the DIN-style face that ships with Windows), figures in Cascadia Mono with tabular
  numerals. No web fonts: the page makes no outside request.
- Every figure has its unit and context (Elo with interval and opponent, "as of" with age). Internal names
  (queue item, test, job, file) are in the tooltip.
- Updates change values in place; nothing reloads or flickers. Motion: the flow on active links, the ticker,
  and one slow pulse on an unseen critical alert. All stop under the system's reduced-motion setting.
- Sizes scale with the window, so 1080p and a large screen show the same layout.

## 4. Architecture

```
readers (pure functions, one per source)  ->  collector (cadence, change detection, health)  ->  snapshot
snapshot + alert rules  ->  local server (127.0.0.1 only, GET only)  ->  page (renders, updates in place)
```

- `readers/`: one small pure function per source: bytes or text in, plain data out. No I/O inside, so each is
  tested on fixtures, including missing, empty, truncated and corrupt input. The existing `parsers.py` and
  `winutil.py` are reused where they already do the job (`ordo`, `nets_md`, `default_net`, `datagen_log`,
  `manifest_summary`, CPU and memory).
- `collector.py`: owns all file access. Per source: a cadence, and a cheap change check (size and modified
  time) before any read; logs are read incrementally from the last offset; a failed read keeps the last good
  value and marks the source stale. One source failing never blanks another.
- `rules.py`: turns the snapshot into alerts (section 6) and into the "what is happening now" sentence.
- `serve.py`: `http.server` on 127.0.0.1, fixed port, GET only: the page, `/snapshot`, and an event stream
  that pushes changes. It checks the Host header, and has no route that writes.
- `web/`: one HTML file, one CSS, one script; no framework, no CDN.
- Its only writes go to its own folder, `%LOCALAPPDATA%/ForkControlCenter/dashboard/`: a bounded history for
  the sparklines (one sample a minute), the "seen" marks, the theme.

Cost target: under 1% of one core on average and under 80 MB, measured and reported with the build.
Steady state spawns no process at all; the only spawns are the optional network polls of decision 4 and one
`git log` when the branch head changes.

| Tier | Cadence | What |
|---|---|---|
| 0 | 2 s | CPU, memory, commit charge (in-process Windows calls) |
| 1 | 5 s, read only on change | locks, the lanes' job records, queue and state folders, live driver logs, events, ledger, VM status, watchdog, lock folders, watcher logs |
| 2 | 60 s, read only on change | verdict list, gauntlet archive, manifests, nets.md, default net, transfer.json, sprt-log headings, retrain state folders |
| 3 | 2 to 30 min | GitHub run jobs, Kaggle state and quota, WSL part log (each gated as in section 2) |

## 5. Data-source map

`~` is the user's home folder. "Change check" means size and modified time before any read.
All reads open the file shared (read, write and delete), read it whole or by tail, and close at once.

### 5.1 Overview and progress

| Feeds | Source | Read |
|---|---|---|
| Default net | `CMakeLists.txt` (`FORK_NET`), `docs/nets.md` Status line | `parsers.default_net`, `nets_md`; on change |
| Engine commit | `.git/HEAD` and the branch ref (file read) | on change |
| Rating and history | `~/fork-data/gauntlet/run-*/ordo.txt`, `meta.txt` | `parsers.ordo`; engine commit from the title's 40-hex if present, else `head_sha`; dates are UTC |
| Gap to Stockfish, transfer ratio | `run-*/summary.md` (`- Stockfish 19 ...`, `- Transfer ratio ...`) | two regexes; the lower bound can be `-inf` |
| Net of each gauntlet | `docs/DESIGN.md` decisions log | `parsers.decision_gauntlets`; the Nov 13 gauntlet is not in it yet, so the net is then taken from `nets.md` by date |
| Anchor-set changes | `run-*/anchors.csv` | compare sets between runs; the chart breaks its line there |
| Adoptions | `tools/gauntlet/transfer.json` (`adopted[]`), `git log` subjects matching "adopted on its/their ... pass" | git only when the branch ref changes; "not adopted" and "neither adopted" excluded |
| Stacking checks | `~/fork-data/sprt/stack-check-*-stc/` (`verdict`, last block of `driver.log`), sum from line 1 of the item log | the claimed sum is free text |
| Speed | `docs/history/phase-4/perf-log.md` rows | milestones only: no regular speed measurement exists (section 8) |
| Decisions waiting | `MORNING.md`, section "Decisions for the owner" | tail; shown as text. Open or answered is not marked in the file, so the display cannot tell |

### 5.2 Testing

| Feeds | Source | Read |
|---|---|---|
| Lane up or down | `~/fork-jobs/locks/github*.json`, then `jobs/<name>.json`; liveness by the recorded process ids and their start times (in-process, query access only) | 5 s on change. A new `github3.json` would appear as lane C with no code change |
| Pending items, in order | names ending exactly `.sh` in `night/items` and `night/items-b`, minus `state/<key>.done` and `.skipped`; `.retry_at`, `.failures` | folder listing on change |
| Current item | the pending key whose `night/<key>.log` is newest and does not end in a "gated" or "not ready" line | inferred (section 8) |
| Test behind an item | last `... UTC <name>:` line of the item log | the item key is not the test name |
| Elo, interval, games, LLR and bounds, stage | last complete block of `~/fork-data/sprt/<name>/driver.log` (`Elo: e +/- h`, `pairs P, games G`, `LLR: v (lo, hi) [e0, e1]`) | tail 2 KB; a block counts only with its LLR line and a final newline. Changes at stage ends only |
| Design, cap, time control | `sprt/<name>/design.json`; absent for fixed-node screens, which report Elo only and whose `verdict` file means nothing | once per test |
| Countdown | dispatch time from `ledger.jsonl` plus the median stage time of past tests with the same time control and games (measured: STC 18 to 19 min, screen 43 to 47, LTC 78 to 81) | a range: next result, and the latest end at the cap |
| Progress inside a stage | GitHub: the jobs of the live run (`gh api`, one GET per live run every 2 min) | optional (decision 4); shards finished, not games |
| Verdicts | `sprt/*/verdict` by modified time, with the last Elo line; also logs ending `; stopping` or dispatched with no merge (interrupted) | folder listing every 60 s; each verdict read once |
| One-line meaning | first comment sentence of the item script; else the idea id from `tries.jsonl` with the survey table; else the name | cached per item |
| Passed and adopted | verdict `H1 accepted` plus an adoption commit or `transfer.json` entry | a passed test with neither shows as "passed, not yet adopted" |

Never read: `sprt/<name>/s<K>/` of the newest stage (the driver deletes and re-makes it while downloading).

### 5.3 Training

There is no single retrain status file; each retrain has its own folder. The display uses a small
registry (`retrains.json`: per retrain, its state folder, gates folder, results file and test-name prefix),
and discovers new retrains by the folders that hold `gates.json` files, listing an unknown one with what it
can read.

| Stage | Source |
|---|---|
| Session running, ended, exit | `~/fork-jobs/jobs/<chain>.json` and the tail of its log |
| Kaggle end state and quota | `fetch-*.log` lines `session ended: ...` and `quota after the session: GPU used left total reset`; live state and quota only by the Kaggle CLI (decision 4) |
| Arms and validity | `result/retrain.json` (`settings.arms`, `validity`), parsed once per session and cached (170 KB) |
| Gates | `<gates>/<net>/gates.json`: `gates_failed`, `clamped`, `recall`. Never search the text for "FAIL": a passing net's log contains it |
| Held-out checks | same file: `heldout`, `heldout67` (`ratio`, `flagged`; the flag is 1.15) |
| Bake | `bakes.txt` (net, commit, bench nodes, signature; last line per net wins) |
| UHO diagnostic | `~/fork-data/uho-diag/runs/<net>.json` (`median_ratio`) |
| Screens | `screens.txt`, `state/*-results.txt`, `state/*.elo`, and the live `driver.log` |
| Promotion SPRT | `sprt/<name>/design.json` with `kind: network`, `driver.log`, `verdict`, `tries.jsonl` |
| Promoted | the default net in `CMakeLists.txt` equals the net |

### 5.4 Data

| Feeds | Source | Read |
|---|---|---|
| PC part running | `%LOCALAPPDATA%/ForkControlCenter/watchdog.json` (fresh heartbeat, no `exited`), `parts/<part>/part.json` | 5 s on change |
| PC rate and total | the part's log in WSL (`N s: G games, P positions, R positions/s`), rate over the last hour of lines | gated (decision 5); otherwise "running, rate not read" |
| Seal state | `parts/<part>/seal-result.json` (`state`, `steps`), then `data/manifests/<part>.json` | first match wins: sealed, sealing, failed, copied, unsealed, running |
| Totals and positions by labeller | `data/manifests/*.json` (`generator.evaluator`, `positions`), cloud run records, slice results | cached by modified time; snapshots and cuts excluded so nothing is counted twice |
| VM state, running item, queue, events | `~/fork-jobs/gcp/status.json` (refreshed by the watcher about every 5 min) | the IP in it is never read into the snapshot; older than 11 min raises "watcher stale" |
| VM positions | verified: `<run>.ok` lines; pulled: chunk folders; since the last pull: time running times the last full run's rate, labelled "estimated" | exact figures need the watcher to store them (section 8) |
| VM cost | hours running times the hourly rates and the egress lines | from `gcp.json` only the three rate fields are read; an estimate, not the bill |
| Arm progress | the arms' heartbeat log (`... s, 3 live: d20 N positions; ...`), `ld-sealed.json`, `ld-decision.json` | any later arms run started the same way is picked up by its log shape |

### 5.5 Machine

| Feeds | Source |
|---|---|
| CPU, memory, commit charge | in-process: `GetSystemTimes`, `GlobalMemoryStatusEx`, `GetPerformanceInfo`; history kept by the display |
| Longer memory history, freezes | `~/fork-jobs/night/freezewatch.log` (`avail N MB, commit P%`, `STALL: N s`) |
| WSL cache and drops | `~/fork-jobs/jobs/wsl-cache-drop2.log` |
| Memory-watch actions | `~/fork-jobs/jobs/memwatch3.log` lines with `dropped`, `stopped agent job`, `ALERT` (none has occurred yet; the wording is taken from the script) |
| Watchers alive | their locks and job records, with the same liveness check as the lanes |
| Compile lock | `compile.lock.lifted`, `compile.lock.d/owner`, `compile.queue.d/`, today's sum in `compile-lock-waits.log` |
| Speed-measurement lock | `nps-measure.lock/` (a convention with no script behind it; shown as written) |
| Running jobs and builds | job records in state running; build activity from `.ninja_log` modified times in the worktrees |
| Events for the ticker | `~/fork-jobs/events.jsonl` (start lines hold full commands and paths: only name, type, exit code and time are kept) |

## 6. Alerts

Rules are data (`rules.json`), reloaded when the file changes.

**Critical** (unmistakable; stays until the cause clears):

- a lane's job record says running but no live process, or the lane's driver log ends `; stopping`;
- a watcher is gone (VM watcher, memory watch, freeze monitor, WSL cache drop);
- a production job ended with a non-zero exit and nothing after it passed;
- the VM's state differs from the wanted state, or its status file is older than 11 minutes;
- a seal failed; a freeze stall was logged; the memory watch logged ALERT.

**Attention** (stays until seen or cleared):

- a lane idle for 10 minutes with items pending and none waiting on a retry;
- CPU under 25% for 15 minutes with work queued; the PC not generating with no part planned;
- an item with failures, or skipped after its third failure; a test interrupted without a verdict;
- a held-out flag; an anchor check flagged for review; a passed test not yet adopted;
- commit charge at or above 90%, or less than 1 GB available; quota under 5 hours;
- a source the display can no longer parse (the format changed).

**Information**: resolved failures, the compile lock lifted, a source that is stale by design.

## 7. Keeping itself current

The owner asked that it follow changes with as little upkeep as possible.

- **Discovery instead of names.** Lanes come from the lock files, items from the folders, tests from the
  ledger and the item logs, jobs from their records, retrains from their gate files, parts and labellers from
  the manifests. A new lane, item, job type, arm or part appears without an edit.
- **Nothing is dropped silently.** A job type or verdict text it has no rule for is shown as written, under
  "other". A file it can no longer parse raises an attention item naming the file, and the last good value
  stays on screen with its age.
- **Every panel shows the age of its data**, and a sources view (key S) lists each source with its last
  read, age and state.
- **Registries reload on change**: sources, retrains, alert rules, plain-language names. The page reloads
  itself when its files change; a reader module that changes is reloaded, and if the new version fails to
  load the old one keeps running and an alert says so.
- **Tests guard the formats**: each reader's fixtures are copied from the live files, so a format change in
  a production script shows as a failed test, not as a blank panel.

## 8. Gaps, and optional additions for the production session

The display works without any of these; each line says what it shows until then.

| Gap | Until then | Addition that would close it (production's choice) |
|---|---|---|
| No record of a lane's current item | inferred from log times and text | the queue runner writes the item key to a state file at each start |
| No progress inside a stage | shards finished, by the GitHub poll | none needed |
| VM positions and rate are not stored | an estimate from the last full run | the watcher stores the progress it already fetches |
| PC rate is only inside WSL | the gated log read | the watchdog adds positions and rate to its heartbeat file |
| No speed series | milestones from the performance log | a periodic speed measurement that appends to a file |
| Quota is logged only at a session's end | the Kaggle poll | none needed |
| Open decisions are not marked | the section's last lines as text | a fixed "OPEN" / "ANSWERED" prefix |
| Adoption has no record of its own | commit subjects and `transfer.json` | none needed |
| Actual cloud spend | the estimate | stays an estimate: the bill needs a cloud call the display will not make |

UNVERIFIED: whether opening the WSL share starts a stopped distro (the gate assumes it does); which Kaggle
command prints the quota (the chains log its output; the command will be read from the chain script before
the display uses it); whether per-shard artifacts can be read mid-run (not used).

## 9. Safety

- **Display only.** The package imports none of the control modules. A test fails the build if any reader,
  the collector or the server opens a file for writing outside the display's own folder, starts a process
  outside the allowed read-only list, or imports `generation_control`, `seal_part`, `watchdog` or
  `runner.Runner.control`. This is the existing app's audit-hook test, extended.
- **Never run**: `sweep.sh` (it restarts the VM and kills processes), `stale.py`, `gcp.py`, `jobctl`, any
  chain or item script.
- **Never hold a production file open.** jobctl replaces job records by rename and failed once this way
  (2026-11-12). Reads use a shared-delete open and close at once; a test renames a file during a read.
- **Secrets and personal data.** Fields are taken by allow-list, never passed through: from `gcp.json` only
  the three rates; from `status.json` no IP; from events no command lines. Every string that leaves the
  server has the home folder replaced by `~`. Credential files are never opened; the Kaggle and GitHub
  tools are called with fixed read-only arguments, and their error text is redacted as the existing app does.
  A test feeds the readers fixtures holding a fake key, IP, project id and user path and asserts none of it
  reaches the snapshot.
- **Local only.** The server binds 127.0.0.1, answers GET only, and refuses a request whose Host is not
  local.
- **The stale-process sweep.** Started from its shortcut, the display has a live parent and no job-over
  evidence, so the sweep can at most report it, as it already does for the existing app. A single-instance
  guard prevents a duplicate.
- **The existing app.** Untouched. Its window does not appear to have been opened since Nov 7 (the date of
  its instance file), but its modules run in production, and its watchdog ran for the last part (g4c). Removing its control tab later is possible only at a moment with
  no part attached, and is a separate decision.

## 10. Build plan after approval

1. Readers with fixtures and tests, one area at a time: testing, overview, training, data, machine. Every
   reader is tested on missing, empty, truncated, corrupt and renamed-while-read input.
2. Collector, rules, the safety tests of section 9, the cost measurement.
3. Server and page (the mockup, fed by the snapshot instead of its built-in sample).
4. Run it beside production, read-only, and show it: screenshots of each panel against the sweep's own
   output at the same minute, with the measured CPU and memory.
5. Tests join `scripts/check.sh` tool tests by discovery; nothing under `scripts/code-paths.txt` changes, so
   no engine build is triggered.

Nothing is pushed, and nothing merges into `phase-4` or `main`, without the owner's approval.
