# Fork Operations Display: design, as built

Status: **built and running beside production, read-only** (2026-11-14). Branch `tools/cc-dashboard`, not
pushed; nothing merges into `phase-4` or `main` without the owner's approval. The mockup the owner approved
is `mockup/dashboard-mockup.html`; the page in `web/` is that layout fed by live data.

    python -I -B tools/ops_display/serve.py --open     # then http://127.0.0.1:8719/ (-B: no bytecode files either)
    python -I -B -m unittest discover -s tools/ops_display -p "test_*.py"

## 1. What it is

A live, display-only screen of the whole pipeline: the 30-minute sweep, but continuous and readable. It
shows what is running, what is waiting, what just finished, what needs the owner, and how the engine's
strength is moving.

**It only displays.** It has no control that starts, stops, seals, queues, adopts or edits anything, no code
path that could, and it writes no file at all. The old Control Center (`tools/control_center`) is untouched
and not imported: `notify.py`, `seal_part.py` and `start_part.sh` there are used by the cloud watcher, the VM
setup and the label-depth chain.

## 2. The owner's decisions (2026-11-14)

1. A browser page served by a local Python server: standard library only, 127.0.0.1 only.
2. The existing Control Center stays untouched (it will be retired later).
3. "Seen" dims an alert in the browser window only: no write anywhere, gone on reload.
4. Network polls: GitHub every 2 minutes for the live runs; Kaggle only while a session runs.
5. The PC's generation rate is read through the WSL share, only while a part runs and WSL is already up.
6. Name "Fork Operations Display", in `tools/ops_display/`.
7. Additions to production scripts are deferred: listed in section 8, the per-lane current-item marker first
   (the production session added that marker the same day; the display reads it).
8. Automatic discovery is required, and a file that can no longer be parsed raises an alert, never a blank.
9. Preliminary results: once runs carry per-shard progress artifacts, a combined preliminary Elo with error
   bars and games played, labelled "preliminary"; until then stage-end results. No workflow is edited here.

## 3. Screen

One full screen, fixed hierarchy:

- **Status strip**: overall state (the worst state of any alert), default net, latest gauntlet rating with
  its interval, gap to the reference engine with its interval, adoptions of the last 7 days by day, engine
  commit, the display's own state (sources read and failing, its CPU share), clock (EST).
- **Situation** (centre): the pipeline as connected nodes: PC generation, cloud VM generation, training data,
  Kaggle training, tests waiting, one node per GitHub lane, engine, gauntlet, and the loop back (the default
  net labels new data). Each node carries a status light, one key figure and a line of context; active links
  show flow. Above it one generated sentence says what is happening now.
- **Testing** (left): one card per lane: name, kind, Elo with its 95% interval, games, the likelihood ratio
  between its bounds, a countdown to the next result, shard progress, the latest possible end; then the queue
  ahead and the recent verdicts with a one-line meaning.
- **Alerts**, **Progress over time**, **Training**, **Data**, **Machine**, and an **event ticker**.
- **Focus**: keys 1 to 7 or a click on a panel header fill the screen with that panel and its detail. Esc
  returns. `T` switches theme, `S` lists the sources and polls, `?` the keys.

Visual rules: dark by default, light on a key. Colour means state only (nominal, active, attention,
failure, and a neutral for idle), and each state has its own shape, so it never rests on colour alone; the
four colours were checked for colour-blind separation on both backgrounds (worst pair 17.0 dark, 14.8 light,
target 8). Data marks are drawn in ink. A rejected or capped test is a normal outcome and stays neutral.
Labels in Bahnschrift, figures in Cascadia Mono with tabular numerals; no web font, no outside request.
Every figure has its unit and context; internal names are in tooltips. A panel is rebuilt only when its own
data changed; clocks and countdowns tick in place.

## 4. Architecture

```
fsread.py   the only door to files: read-only, shared, read on change, last good value kept
readers.py  one pure function per source (text or JSON in, data out); stats.py the pentanomial figures
machine.py  CPU, memory, commit charge, process liveness: in-process Windows calls, query access only
collect.py  discovery, cadence, health: builds the snapshot        rules.py  alerts and the situation
procs.py    the only door to a process: three read-only commands   net.py    the two network polls
serve.py    127.0.0.1, GET only: the page and /snapshot            web/      index.html, style.css, app.js
```

- The page asks for `/snapshot` every 2 seconds; the server refreshes it every 2 seconds.
- Cadence: machine 2 s; jobs and lanes 5 s; data 10 s; tests, training 30 s; overview 60 s. A file is read
  only when its size or modified time changed.
- Cost, measured beside production on 2026-11-14: 0.55% of one core in steady state (1.33 s of CPU in 240 s)
  and 30 MB of memory; 809 sources watched. The first pass (every job record and test folder once) takes
  about 3 s.
- `readers.py`, `rules.py` and the page reload themselves when their files change; a version that fails to
  load leaves the previous one running and raises an alert. `collect.py` and `serve.py` need a restart.
- `rules.json` beside `rules.py` (optional) overrides the alert thresholds; it is re-read on change.

## 5. Data-source map

`~` is the home folder. Everything is read through `fsread`.

| Feeds | Source | Notes |
|---|---|---|
| Lanes | `~/fork-jobs/locks/github*.json`, the holder's job record, liveness of its recorded processes | a new `github3.json` appears as lane C |
| A lane's items | the folder its own runner script names (`I=$N/items-b`), minus `state/<key>.done` and `.skipped`; `.retry_at`, `.failures` | |
| Current item | `state/current-<LANE>.txt` (the lane's marker: state, item, drivers) when present and, if a watcher writes it, under 3 minutes old; otherwise the first runnable item in name order | an idle lane whose driver still runs shows that test |
| Test behind an item | the item log's last `UTC <name>:` line, or the marker's driver | the item key is not the test name |
| Elo, interval, games, LLR, stage | the last complete block of `~/fork-data/sprt/<name>/driver.log` | changes at stage ends |
| Design, cap | `sprt/<name>/design.json`; absent for fixed-node screens, which report Elo only | |
| Countdown | dispatch time from `ledger.jsonl` plus the median stage time of finished tests of the same kind | no history of a kind: no guess |
| Shards finished | GitHub: the live run's jobs (one GET per run every 2 minutes) | |
| Preliminary result | GitHub: the live run's `progress-<stage>-<shard>` artifacts (`progress.json`, format `fork-shard-progress/1`, `docs/research/shard-progress.md`): the newest per shard, an id downloaded once, a shard refreshed at most every 4 minutes | the lanes' runs carry them once `infra/shard-progress` is merged |
| Verdicts | `sprt/*/verdict` with the last Elo line; tests dispatched and never merged that no lane runs | unknown verdict text is shown as written |
| Names | the item's name, the survey's code table, `docs/ideas.md` headings; the item script's own comment in the tooltip | |
| Jobs, failures, ticker | `~/fork-jobs/jobs/*.json` (each read once per change, after it has been still half a second), `events.jsonl` | command lines are never kept |
| Default net, commit | `CMakeLists.txt`, `docs/nets.md`, `.git/HEAD` and the branch ref | |
| Rating, gap, history | `~/fork-data/gauntlet/run-*/ordo.txt`, `meta.txt`, `summary.md` | the line breaks where the anchor set changed |
| Anchor checks | the check runs' `summary.md` (pooled gain, outcome) | |
| Adoptions | `git log` subjects "adopted on its/their ... pass" (one read-only `git log` when the branch head moves), `tools/gauntlet/transfer.json` | |
| Stacking checks, speed | `sprt/stack-check-*`, the item logs' claimed sum; `perf-log.md` rows | no speed series exists |
| Retrains | every `~/fork-data/<x>/*gate*/<net>/gates.json`; beside it `bakes.txt`, `fetch*.log` (session end, quota); `uho-diag/runs/<net>.json`; the tests named after a net | arms are the nets' names without the seed digit |
| Kaggle session | `kaggle kernels status` every 5 minutes, only for a kernel named in a running Kaggle job's log AND found as the `id` of a `kernel-metadata.json` under `~/fork-data/kaggle` | |
| PC generation | the old app's `watchdog.json`, `parts/<part>/part.json`, `seal-result.json`; the part's log through the WSL share, gated | never between 1:20 and 2:30 AM EST |
| Totals, labellers | `data/manifests/*.json` and `~/fork-data/*/filler/parts/*.json`; cuts and snapshots are not counted | |
| Cloud VM | `~/fork-jobs/gcp/status.json` (the address in it is never read out), `wanted.json`, `egress.jsonl`, three rates of `gcp.json` | positions are an estimate from the last complete run |
| Machine | in-process probes; `freezewatch.log`, the WSL cache job's log, `memwatch*.log`, the compile lock's files, `nps-measure.lock/` | |

Never read: `sprt/<name>/s<K>/` (the driver deletes and re-makes it while downloading). Never run:
`sweep.sh`, `stale.py`, `gcp.py`, `jobctl`, any chain or item script.

## 6. Alerts

Thresholds are data (`rules.py` DEFAULTS, overridden by `rules.json`).

- **Critical**: a lane's runner has no live process; a lane's run failed and stopped it; an expected watcher
  is not running; a production job failed and nothing after it passed; the VM is not in its wanted state, or
  its status file is over 11 minutes old; a seal failed; a freeze stall or a memory-watch alert in the last
  2 hours.
- **Attention**: a lane idle with items behind a gate or retry timer; the PC not generating; a queue item
  with failures; a test dispatched and never merged; a retrain's gate failures or held-out flags (for a day);
  an anchor check flagged; commit charge at 90% or more, or under 1 GB free; quota under 5 hours; the CPU
  under 25% for 15 minutes with work waiting; a job record that says running with no process; **a source that
  can no longer be read as expected**, named.
- **Information**: a step that failed and then passed; a passed test whose adoption is not recorded yet; the
  compile lock lifted.

## 7. Safety

- **No writes.** `fsread.py` opens files for reading only; no module calls anything that writes, renames,
  deletes or creates. A test parses every module and fails on such a call; another runs the collector, the
  rules and the server's refresh under an audit hook that fails on any write or process start, and compares
  the folder trees before and after.
- **Processes.** `procs.py` is the one place a process starts, and only for: `git -C REPO log ...`,
  `gh api repos/.../actions/runs/N/jobs|artifacts` and `.../artifacts/N/zip` (GET), `kaggle kernels status
  OWNER/KERNEL`. Anything else raises before a process exists; a test tries 21 refused commands. With
  `--open` the browser is opened once.
- **File sharing, as measured.** A file is opened with read, write and delete sharing, so production can
  append to it, delete it or rename it away while the display reads. Windows still refuses to *replace* a
  file by rename while anyone has it open, whatever the sharing: jobctl replaces job records that way and
  retries a refusal every 10 ms for 10 seconds. A read by the display can therefore cost jobctl one retry,
  never a failure. To keep even that rare, a record is read whole in one call, only when it changed, and
  only after it has been still for half a second. Measured under load (300 replaces each): no reader, no
  retry; a read each second, 2 retries; 500 reads a second, 195 retries, worst 262 ms; a reader spinning on
  the file, worst 1.5 s. The display never polls a file in a loop.
- **Secrets and personal data.** Fields are taken by allow-list: no command lines, no VM address, three
  rates only from `gcp.json`. Every snapshot passes a scrub that turns home folders into `~`, removes IPv4
  addresses and removes the account names of the home folders wherever they stand. A test plants a user
  name, a key path, a project id, a billing id and an address in the fixtures and finds none in the snapshot.
- **Local only.** The server binds 127.0.0.1, answers GET only (405 otherwise), and refuses a request whose
  Host is not its own (403). The page loads nothing from outside and stores nothing.
- **One mistake made and fixed while building (2026-11-14):** the first Kaggle reader took a piece of a file
  path in a job log for a kernel name, so the display asked Kaggle for the status of a kernel that does not
  exist, twice; the name it sent was the Windows account name followed by `/fork-data`. Kaggle refused both.
  Since then a name is polled only if it is also the id of a kernel that was pushed from this machine.

## 8. For the production session

The display works without these; each line says what it shows until then.

| Addition | Until then | State |
|---|---|---|
| Per-lane current-item marker (`state/current-<LANE>.txt`) | the first runnable item in name order | **done by the production session, 2026-11-14; read by the display** |
| Per-shard progress artifacts for preliminary results | stage-end results only | **built by the production session (branch `infra/shard-progress`, 3ff8454); the display's reader matches its schema**, checked against its test run 43628564195 |
| The cloud watcher stores the positions and rate it already fetches | an estimate from the last complete run | open |
| The watchdog adds positions and rate to its heartbeat file | the gated read of the part's log in WSL | open |
| A periodic speed measurement appended to a file | milestones from the performance log | open |
| A fixed "OPEN" / "ANSWERED" prefix in the morning report's decisions | the section's last lines as text | open |

**Preliminary results, as shown:** the newest progress record of every shard of the stage in flight is
summed (pentanomial counts of finished pairs), added to the finished stages, and shown beside the stage-end
figures, which stay untouched: Elo with its 95% interval, games, an estimate of the LLR, the stage's games
finished of planned, the shards reporting and finished. The verdict is always the merge's at the stage's end.
A record of another format than `fork-shard-progress/1` is refused and reported, never shown.

UNVERIFIED: preliminary results during a live lane run (the fetch and the sums were checked on a completed
test run; the lanes' runs do not carry the artifacts yet); the Kaggle
status poll during a real session (none ran); the gated WSL read during a real part (none ran; tested on a
stand-in folder); whether opening the WSL share starts a stopped distro (the gate assumes it does).

## 9. Not done

- Not wired into `scripts/check.sh`: that file is on the code-paths list, so committing a change to it runs
  the engine's quick check (a build). The tests run by the command at the top.
- No desktop shortcut is installed (`install_shortcut.ps1` is provided, not run).
- Not pushed, not merged.
