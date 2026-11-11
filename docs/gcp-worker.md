# The Google Cloud CPU worker

A second general CPU worker for Fork (owner, 2026-11-10): one 8-vCPU spot VM on Google Cloud's free trial,
fed from a priority queue the PC owns. Free-trial limits: at most 8 vCPU running, no GPUs, spot only, and the
billing account is never upgraded. Project, zone, billing ids, addresses and keys live only in the untracked
settings file `~/fork-jobs/gcp.json` on the PC; nothing here names them.

## Machine

- Chosen by measurement, the cheapest test that could decide (2026-11-10): the positional slice's settings
  (80,000 nodes, hash 4 MB, 3-4-5 tables, adjudication 1500 cp x 16 plies, no random plies) on 8 threads,
  96,000 positions from the slice's own start list with seed 20261110, so both machines played the same games.
  See "Measurement" below for the numbers.
- Spot provisioning, termination action STOP (a preempted VM keeps its disk and is started again), Ubuntu
  26.04 LTS (the same clang 21 the PC's WSL builds with), a 30 GB balanced persistent disk, an ephemeral
  external address (SSH and the downloads; released while stopped). On the free trial spot VMs count against
  the regular CPUS quota (PREEMPTIBLE_CPUS is 0 there and a spot VM was created without it).

## Measurement (2026-11-10)

Both types run AMD EPYC 7B13 (Zen 3, AVX2 and BMI2, no AVX-512: target x86-64-v3); the two PGO builds of
d807c57 were byte-identical (fork 7fd9e1f8..., fork_datagen c6ad5187...), and both runs wrote byte-identical
shards (987 games, 96,626 positions).

| | c2d-highcpu-8 (us-east4) | t2d-standard-8 (us-east1) |
|---|---|---|
| vCPU | 8 = 4 cores x 2 threads, 16 GB | 8 cores, no SMT, 32 GB |
| 8-thread data generation | 487.8 s, 198 positions/s | 351.1 s, 275 positions/s |
| 8 concurrent `fork bench` | 1.58-1.61 M nps each | 2.14-2.28 M nps each |
| spot price, running (VM + 30 GB disk + address) | $0.1190/h | $0.2094/h |
| per million slice positions | **$0.167** | $0.211 |

T2D is 1.39x faster but costs 1.76x as much, so C2D gives the lower cost per position (the owner's rule) and
was kept; T2D was deleted with its disk. Prices: the Cloud Billing Catalog's spot SKUs on 2026-11-10 (C2D
us-east4 $0.01104 per vCPU-hour and $0.001476 per GiB-hour; T2D us-east1 $0.0165 and $0.002212; balanced
persistent disk $0.11 (us-east4) and $0.10 (us-east1) per GiB-month; an external address on a spot VM $0.0025
an hour).

## Engine builds

`tools/gcp/vm_setup.sh COMMIT` builds Fork on the VM the way the PC's data generation does
(`cmake/pgo.cmake`, clang, as `tools/control_center/start_part.sh`), but with the target from the CPU's own
flags, never native: x86-64-v3 (AVX2, BMI2 and FMA required) or x86-64-v4 with the five AVX-512 features.
Every build is checked (`fork version`: target, network, commit; bench and perftbench parity,
`.github/ci/bench-parity.sh`) and lands in `/opt/fork/builds/COMMIT12-ARCH/` with `pins.txt` (SHA-256 of fork and
fork_datagen). Every job checks its binaries' SHA-256 against the pins its queue item carries before it runs,
and the slice also runs bench before and after.

## Job supervisor and queue

- On the VM, `tools/gcp/worker.py` runs as the systemd service `fork-worker` (`tools/gcp/vm_install_worker.sh`):
  started at every boot, restarted if it dies, `KillMode=process` so the jobs outlive a restart of the worker.
  Each job runs under the job supervisor, `tools/jobs/jobctl.py` (its POSIX side: a session per job, every
  process marked with FORK_JOB_ID, `stop` verified over the whole tree), with `FORK_JOBS=/opt/fork/jobs`; jobs
  survive SSH disconnects.
- The queue: one JSON file per item. The PC is authoritative: the items live in `~/fork-jobs/gcp/queue/` on the
  PC and `tools/gcp/gcp.py push` mirrors them to `/opt/fork/queue/` (rsync --delete). The VM keeps its copy, so
  it carries on while the PC is off; removing an item on the PC and pushing withdraws it (the worker stops it).
- Order: class a (the positional slice), then b (labelling and measurement jobs: deep labels, pilots, ChessTB
  slice labelling), then c (standard data generation as filler, `tools/gcp/filler.sh`), then the name. One job
  at a time (8 vCPU). A filler is `"preemptible": true`: when an a or b item appears it is stopped (it loses
  only the chunk in progress) and starts again, as a new run, when nothing more urgent is left. `"hold": true`
  keeps an item queued but unrun.
- An item ends **done** only with exit 0 and every listed output present and valid (`tools/jobs/paths.py`'s
  outputs check: no silent done); anything else is **failed** and is not retried until the PC deletes its state
  file (`/opt/fork/state/items/NAME.failed`). The worker writes `/opt/fork/state/worker.json` every 30 s and
  appends to `/opt/fork/state/events.jsonl`.

## Preemption

A spot preemption stops the VM (termination action STOP). `gcp.py watch --restart` starts it again while
`~/fork-jobs/gcp/wanted.json` says running (`gcp.py start` and `gcp.py stop` set it, so a stop by the owner is
never undone). At boot the worker finds the interrupted job (its record says running, it started before the
boot, no process is left), counts a resume (at most `max_resumes`, default 50) and starts the same command,
which resumes from its own files:
- the slice (`tools/gcp/slice_vm.py`) at game boundaries: the interrupted segment's shards are cut after each
  worker's last complete game (the Control Center seal's `complete_games`), a manifest is written for them, and
  a new segment (seed + 1) plays only the starts no complete game has used, for the positions still missing. At
  most one game per thread is lost; no start is ever played twice (checked with `defense_starts.py played`);
- the filler at chunk boundaries (`tools/cloud/cloud_datagen.sh`, chunks of 250,000 records, each verified and
  sealed on the VM before it counts); a new run name and seed base at each start.
Tested end to end on the worker (2026-11-10): a 30,000-position slice item through the queue, the VM stopped
(`gcp.py stop`, the same ACPI shutdown a preemption gives) after segment 0 had run about two minutes, then
started: the worker recorded the interruption ("preempted", resume 1), slice_vm.py salvaged 243 complete games
(23,663 positions), segment 1 (seed + 1) played 75 games from the 185,312 unplayed starts, both segments passed
verify_games.py, `defense_starts.py played` matched all 318 games with no start twice, and `gcp.py finish`
repeated the checks on the PC (the pull moved 154,752 bytes). The filler was smoke-tested on the worker with
3,000-record chunks: five chunks verified and sealed on the VM, the sixth dropped at the stop (SIGTERM to its
session), as designed; its outputs were then deleted.
fork_datagen itself has no resume: a stopped run writes no manifest, and its last game is usually cut off.
The salvage above needs no engine change. A true in-run resume would need fork_datagen to start worker w at a
given game index (the game sequence is deterministic per seed); not needed for game-boundary resume.

## Results back to the PC

`gcp.py pull JOB` rsyncs `/opt/fork/out/JOB/` into the staging folder (WSL `~/fork-data/gcp/JOB/`) and logs the
bytes and their egress price in `~/fork-jobs/gcp/egress.jsonl`. `gcp.py finish JOB` then runs the PC's own checks
before anything counts: for the slice, every shard's SHA-256 against the VM's `done.json`, `verify_games.py` per
segment with its manifest and 5-piece tables, and `defense_starts.py played` over all segments, on a copy on C:
with the Windows venv (as `slice.sh` does), and only then writes the done file. Filler runs come home with
`gcp.py pull filler`, then `tools/cloud/pull_datagen.sh --from <staging>/filler/RUN --to OUT`, which checks
every chunk's shards against its sealed manifest and replays every game.

Egress (internet data transfer out from us-east4, "Virginia to Americas", Cloud Billing Catalog, 2026-11-10):
$0.12 per GiB for the first TiB a month; ingress is free. Fork's data is 4.37-4.39 bytes per record
(viriformat: the pilot's dp-pos shards, the sealed g4 and g4b parts), so a million records is about 4.4 MB,
$0.0005; a million saved positions at the standard 50% save rate is about 8 MB, $0.001.

## Status and alerts

- `gcp.py sweep` (for a sweep every 15 minutes, from PowerShell): one pass that restarts the VM if it is stopped
  while `wanted.json` says running (a preemption: spot VMs with the STOP action do not restart themselves),
  reports new preemptions and failed items, shows each item's build folder with its network and whether the
  item's binary pins are in that build's pins.txt (ATTENTION if not), prints the running job's positions, rate,
  ETA and last output time
  (from fork_datagen's own log lines, read on the VM over one SSH call), and, for a job done on the VM whose PC
  check has not run, prints the exact `jobctl.py start gcpfinish ...` command that runs `gcp.py finish` under
  the PC's supervisor (the slice's PC checks take a while, so the sweep never runs them inline). Exit 1 with
  ATTENTION lines when something needs a look, an idle VM included.
- Filler runs come home on demand: `gcp.py pull filler`, then in WSL, per run,
  `PYTHON=~/fork-cloud-venv/bin/python bash tools/cloud/pull_datagen.sh --from ~/fork-data/gcp/filler/RUN --to OUT`
  (every chunk's shards against its sealed manifest, every game replayed); a run still in progress has its
  finished chunks only.

- `gcp.py status`: the VM through `gcloud compute instances describe` (no SSH, nothing billed), and, when it
  runs, the worker's state and last events over one SSH call; also written to `~/fork-jobs/gcp/status.json`.
- `gcp.py watch --restart --finish` (under the PC's job supervisor, type gcpwatch, started from PowerShell):
  every 5 minutes; a Windows toast (the Control Center's `notify.toast`) and a line in
  `~/fork-jobs/gcp/alerts.jsonl` on a preemption (`compute.instances.preempted` operations), a stop nobody asked
  for, a job that failed or used up its resumes, a refused start, or a VM unreachable three times in a row. It
  restarts a preempted VM and, with --finish, pulls and checks each finished job. Being a supervisor job, it
  shows in the Control Center's Jobs tab like every other job.

## Setup, from the PC

1. Budget alert on the billing account (gross cost, credits excluded, cumulative from the start date).
2. The VM: `gcloud compute instances create NAME --zone ZONE --machine-type TYPE --provisioning-model=SPOT
   --instance-termination-action=STOP --image-family=ubuntu-2604-lts-amd64 --image-project=ubuntu-os-cloud
   --boot-disk-size=30GB --boot-disk-type=pd-balanced --metadata-from-file=ssh-keys=FILE` with the worker's own
   key (kept in WSL).
3. On the VM: `bash vm_setup.sh ENGINE_COMMIT`, then `bash vm_install_worker.sh TOOLS_COMMIT`.
4. Inputs the jobs read (`/opt/fork/inputs/`, `/opt/fork/slice-tools/`) are copied from the PC with rsync and
   checked by SHA-256 by the jobs themselves.
