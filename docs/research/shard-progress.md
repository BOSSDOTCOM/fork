# SPRT shard progress and lane markers: what a display reads

Owner's order, 2026-11-14 (~1:05 PM EST): each SPRT and screen shard uploads a small progress artifact while
it plays, replacing its previous one; the final merge and verdict logic stay exactly as they are; a test shows
the final results are byte-identical with and without the uploads; and each night-queue lane writes a
"current item" marker. The reader is the display-only Fork Operations Display (`tools/ops_display/`, built
separately); nothing in the SPRT path reads any of this.

## 1. Progress artifacts (GitHub, `.github/workflows/sprt.yml`)

Every run of the `sprt` workflow (the design R SPRTs, the head-to-heads and the fixed-node screens: they all
dispatch `sprt.yml`, through `tools/github/sprt_run.sh`) has, per shard job:

| Artifact | Content | When |
|---|---|---|
| `progress-<stage>-<shard>` | one file, `progress.json` (below), about 1 KB | replaced while the games run; the last one has `state` `final` |
| `shard-<stage>-<shard>` | the shard's results (unchanged) | when the shard ends |
| `engines`, `merged-<stage>` | unchanged | build job, merge job |

`<stage>` is the run's stage input, `<shard>` the shard index (0 to shards-1). The names never collide with
`shard-*` (which the merge job downloads by pattern) and the file is never called `result.json` (the only
file the driver reads from a run's download). Retention: 3 days.

### Cadence

A background watcher (`tools/cloud/shard_progress.py watch`, started before the games by
`.github/actions/start-detached`) reads the shard's fastchess log every 30 s and uploads:

- once at the start (0 games: the shard is running);
- then every 100 finished games (the owner's "~100 games"), or every 300 s when at least one game finished
  since the last upload, whichever comes first;
- and the final record after the games (`state: final`), by the workflow's own upload step.

A standard stage plays about 100 games per shard (1,600 games over 16 shards), so the 100-game rule alone
would fire only at the end: the 300-second rule is what shows a shard part-way. A 35-minute screen shard gives
about 8 records; an LTC shard one per 5 minutes. Both numbers are the `PROGRESS_EVERY_GAMES` and
`PROGRESS_EVERY_SECONDS` of the step in `sprt.yml`.

Replacement is delete-then-upload (actions/upload-artifact's `overwrite`): each upload is a new artifact with
a new id, and for a moment (about a second) the shard may have none. A shard whose watcher failed to start has
only the final record; a shard that never reached its games has none.

### `progress.json` (format `fork-shard-progress/1`)

| Field | Type | Meaning |
|---|---|---|
| `format` | string | `fork-shard-progress/1` |
| `state` | string | `running` while the games run; `final` after (the shard's games ended or it was stopped) |
| `shard_status` | string or null | with `final`: the shard's `result.json` status (`done`, `short`, `failed`, `interrupted`; `running` if its final snapshot was never written); null while running or if there is no result |
| `upload_seq` | int | 1, 2, ... per shard: the record's number (the final record is the last) |
| `started_utc`, `updated_utc` | string | ISO 8601 UTC (`2026-11-14T18:30:05Z`): the watcher's start, this record's time |
| `run_id`, `run_attempt` | int | the workflow run (`GITHUB_RUN_ID`) and its attempt |
| `sprt_name` | string | the SPRT's name (the run's `name` input, the driver's NAME; empty for an unnamed run) |
| `stage`, `shard`, `shards` | int | the stage, this shard, the run's shard count |
| `base`, `test` | string | the two commits (40-hex SHAs) |
| `games_planned`, `pairs_planned` | int | this shard's games (an even number) and pairs (games / 2) |
| `games_finished` | int | games fastchess reported finished |
| `pairs_finished` | int | pairs with both games finished: what the merge counts (sum of `ptnml`) |
| `ptnml` | int[5] | pentanomial counts of the finished pairs, test engine's view: pairs scoring 0, 1/2, 1, 3/2, 2; computed by `sprt_merge.py`'s own functions, so the final record equals the shard's `result.json` counts |
| `wdl` | object | `wins`, `draws`, `losses` of the test engine over every finished game (a game whose pair is still open included) |
| `time_losses`, `abnormal` | int | finished games lost on time; abnormal endings (illegal move, crash, disconnect, stall) in the log |

To add up a stage across shards, sum `ptnml` (the merge's statistic: Elo, nElo and LLR follow from the summed
pentanomial as in `tools/cloud/sprt_merge.py`), and `games_finished` / `games_planned` for progress. A
display's running LLR is an estimate: the verdict is the merge's, at the stage's end, and a SPRT's verdict sums
every stage played so far (the driver's log, `$SPRT_DATA/NAME/driver.log`).

### Reading them (GitHub REST API)

All calls need a token (artifact downloads need authentication even on a public repository): the `gh` CLI's
login, or a fine-grained token with "Actions: read" on BOSSDOTCOM/fork.

1. Runs in progress: `GET /repos/BOSSDOTCOM/fork/actions/workflows/sprt.yml/runs?status=in_progress`
   (also `queued`). Each run's `display_title` is `sprt BASE TEST stage N (NAME)`.
2. A run's artifacts: `GET /repos/BOSSDOTCOM/fork/actions/runs/{run_id}/artifacts?per_page=100` (or
   `&name=progress-0-3` for one). Keep the entries whose `name` starts with `progress-`; fields `id`, `name`,
   `size_in_bytes`, `created_at`, `expired`. If a name is listed twice (a replacement in flight), take the
   newest `created_at`. Artifacts of a run in progress are listed as soon as they are uploaded.
3. Download: `GET /repos/BOSSDOTCOM/fork/actions/artifacts/{artifact_id}/zip`, which answers 302 with a
   short-lived storage URL; the zip holds `progress.json`. With gh:
   `gh api repos/BOSSDOTCOM/fork/actions/artifacts/ID/zip > p.zip`. Download only ids not seen before: an id
   changes only when the shard uploads.

Rate: REST calls with a token are limited to 5,000 an hour per user, shared with the SPRT drivers' own `gh`
calls on the same login. Listing each run in progress once a minute (two lanes: 120 calls an hour) and
downloading only new ids (16 shards, one new record per 5 minutes each: about 190 an hour per run) stays far
below it; do not download every artifact on every poll.

### Mapping a run to a test and a lane

- The run-ID ledger, `~/fork-jobs/ledger.jsonl`, one JSON line per dispatched stage: `{"at", "base",
  "run_id", "source", "sprt", "stage", "test"}`; `sprt` is the SPRT's name (the driver's NAME, the run
  title's `(NAME)`, the record's `sprt_name`). `python -I tools/jobs/ledger.py runs NAME` lists one SPRT's.
- The lane: the markers below. While the bridging watcher writes them, their `drivers` field lists the SPRT
  names of the drivers running in each lane; otherwise the lane is the one whose job (`night-queue` = lane A,
  `night-queue-b` = lane B; `python tools/jobs/jobctl.py processes NAME`) holds the driver process
  `tools/github/sprt_run.sh ... NAME BASE TEST`.

## 2. Lane markers (local)

`~/fork-jobs/night/state/current-A.txt` (lane A, the job `night-queue`, `~/fork-jobs/night/chain.sh`) and
`current-B.txt` (lane B, `night-queue-b`, `chain-b.sh`). Each file is replaced whole (written aside, then
renamed), as `KEY=VALUE` lines:

| Key | Meaning |
|---|---|
| `lane` | `A` or `B` |
| `state` | `running` (an item step runs), `idle` (between steps, or waiting for a ready item), `stopped` (the lane's job is not running; the watcher only) |
| `item` | running: the item's key (its script name without `.sh`, in `night/items/` or `night/items-b/`); empty otherwise |
| `started`, `started_epoch` | running: when the item step started, `YYYY-MM-DD HH:MM:SS AM/PM EST` (EST, UTC-5) and Unix seconds |
| `item_pid` | running: the item process's Windows pid (empty if unknown) |
| `since` | idle or stopped: since when |
| `last_item`, `last_exit` | idle: the step that ran last and its exit code (0 done, 10 a stage done, 20 not ready, other: failed); `last_exit` is empty when the watcher wrote it |
| `chain_pid` | a Windows pid that lives as long as the lane's chain (dead: the marker is stale) |
| `drivers` | the watcher only: SPRT names of the `sprt_run.sh` / `h2h_run.sh` drivers in the lane's job (an item can leave its driver running between its steps) |
| `source` | `chain` (written by the chain itself) or `watcher` (the bridging watcher) |
| `updated`, `updated_epoch` | when this file was written (EST text, Unix seconds) |

Cadence: a chain writes its marker when it starts (idle) and at the start and end of every item step, so a
running marker can be hours old: check `chain_pid` is alive. The watcher rewrites both files every 30 s.
A not-ready item (exit 20) shows as `running` for well under a second, then `idle` with `last_exit=20`.

The chains' scripts carry the marker code since 2026-11-14, but a running chain keeps the script it started
with: until the chains are restarted, the bridging watcher (`~/fork-jobs/night/lane_marker_watch.py`, jobctl
job `lane-marker-watch`, type `lanemark`) writes the markers from the process table: the lane's item is the
bash process running `night/items[-b]/KEY.sh` among the lane job's processes. It leaves a lane to its chain
once the lane's job started after its chain script was last changed, and exits when both lanes are
self-marking; `python tools/jobs/jobctl.py stop lane-marker-watch` stops it by hand.

## 3. No effect on games or verdicts

- The shard's `Games` step, `tools/cloud/run_shard.sh`, the `shard-*` upload, the merge job,
  `tools/cloud/sprt_merge.py` and `tools/github/sprt_run.sh` are unchanged. The watcher only reads the
  shard's log (and `result.json` at the end) and writes under `$RUNNER_TEMP/shard-progress`, outside the
  shard's folder; its steps are `continue-on-error`, and a failed upload is logged and skipped.
- `tools/cloud/test_shard_progress.sh` plays the same shard with and without the watcher and compares
  `result.json`, the merge's summary and `merged.json` byte for byte, and the shard's folder (every file with
  a fake fastchess; with real fixed-node games, the PGN and log once their clock fields are masked, after a
  second run without the watcher shows those fields are the only difference between any two runs). Fault
  injections (a file written into the shard's folder, an appended PGN line, an edited `result.json`) make it
  fail. `tools/github/test_sprt_run.sh` runs a SPRT whose downloads hold the progress artifacts: same exit,
  dispatches, verdict and merged lines. The parser's own tests (`tools/cloud/test_shard_progress.py`) use a
  real shard's log and result, with fastchess's own report as the oracle.
- The watcher's cost: a Python process waking every 30 s to parse a log of a few tens of KB, and a node
  upload of about a kilobyte every 5 minutes, on runners whose games use `nproc - 1` cores.
