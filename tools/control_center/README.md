# Fork Control Center

A Windows desktop window over Fork's long-running work (Python's tkinter, no other dependencies).
**Everything is read-only except the Data generation tab's controls.**

## Launch

- Desktop shortcut "Fork Control Center" (made by `install_shortcut.ps1`), or
- `~/fork/.venv/Scripts/pythonw.exe -I tools/control_center/app.py` (any Python 3.12+ with tkinter).

Only one window opens at a time. Settings: `config.py`; override any key in
`%LOCALAPPDATA%/ForkControlCenter/config.json`. The app's own state (each part's launch files, seal
requests and results, the auto-stop deadline, the watchdog's heartbeat) lives in that folder too, never in
the repository.

## Tabs

1. **Data generation** (the only controls). *Start generating* plans the next part of the current
   generation (DESIGN.md §5.3 deliverable 2, the labeller policy): the next letter, the current default
   engine (the tip of `phase-4` and its default network; a PGO build of it for x86-64-v3 (`build_arch`; owner,
   2026-11-12) in WSL in `~/fork-cc-build`, or the previous part's binary when no engine file changed since
   that binary's commit and it was built for that target; bench-checked against
   `tests/bench-<net>.ref` either way), the standing settings, the next unused local seed and the rest of
   the generation's target, shows the plan for confirmation and starts it through the WSL supervisor
   (`jobctl.py start datagen NAME`). It refuses while any data-generation job lives or holds the lock (in
   either supervisor), while the last part is neither sealed nor copied, and when the disk margin is not met
   (the policy in DESIGN.md §5.3 deliverable 2, "Disk margin": the part's size at 4.6 bytes a position on
   WSL's disk, twice that on C:, plus 20 GB each; `config.py`), and when the openings' WSL copy is missing or
   does not hash to the planned SHA-256 (`sha256sum` in WSL). The openings are the previous part's unless a
   book was chosen for the next parts: `next-openings.json` in the state folder (`%LOCALAPPDATA%\ForkControlCenter`),
   written by `GenerationControl.set_next_openings(FILE, SHA256, REASON)` and read at every plan. The book
   needs its manifest in the repo (`data/manifests/openings-<name>.json`) with that SHA-256 (both checked
   when it is set and at every plan; an unreadable file refuses the plan); `set_next_openings(None)` goes
   back to the previous part's. The plan shows the book, where it came from (`openings_source`) and, at a
   switch, `openings` under "Differs from"; the part's settings record it, and its seal records it from
   fork_datagen's command line. A window opened before this change reads no such file: restart it before
   the next start. A running part (such as g3e, started by hand) is
   attached: its settings are read from fork_datagen's command line. Live: part, elapsed time, games,
   positions, positions/s (the log's average and the last 30 s). A watchdog process (`watchdog.py`) keeps
   Windows from sleeping (system sleep only) while the part's job lives, also with the window closed, and
   runs the optional auto-stop after N hours. *Stop & seal*: `jobctl.py stop NAME` (the whole process tree,
   verified), then a seal job under the Windows supervisor (`seal_part.py`, below-normal priority): each
   worker's complete games copied to `~/fork-data/kaggle/<part>/` (the unfinished game at each shard's end
   dropped; the last worker's shard held out as `*-val.vf`), every game verified with
   `tools/datagen/verify_games.py`, then sealed with `tools/datagen/upload_batch.py seal` into
   `data/manifests/<part>.json` of the phase-4 checkout (uncommitted: commit it there). A failed verification
   is reported and every file is kept.
2. **Jobs**: every job and lock of both supervisors (Windows `~/fork-jobs`, WSL `~/fork-jobs`), with elapsed
   time and processes; a measurement's progress from its log.
3. **Testing**: the current SPRT from the driver log (stage, games, Elo and nElo with their intervals, LLR
   against its bounds), waiting queue jobs and the §5.6 order, recent results from the SPRT log, GitHub runs
   and CI (`gh run list`; double-click opens the run).
4. **Training**: Kaggle sessions (`kaggle kernels list/status`; the token is never read or shown) and the
   downloaded training records (`*/result/*/run.json`).
5. **Networks and strength**: the default network and the others from `docs/nets.md`, the gauntlet ratings
   (DESIGN.md's decisions log and downloaded Ordo tables) and the accepted SPRTs' cumulative Elo.
6. **Data**: every sealed part from `data/manifests/` by generation (games, positions, saved positions,
   labelling network, seed, threads, settings) and where copies live (WSL, C:, a Kaggle dataset named
   `fork-<part>`).
7. **Machine**: CPU, memory (Windows and WSL), free disk, with low-disk and memory-pressure warnings.
8. **Roadmap**: DESIGN.md §5.6, the Phase 4 checklist, each item with its status.

Notifications (Windows toasts): an SPRT decides, a Kaggle session finishes, a job fails or stops
unexpectedly, a seal ends, the disk runs low or memory is under pressure. Polls every 30 s (GitHub every
60 s, Kaggle every 120 s); one WSL process per poll (`wsl_probe.py`, read-only).

## How "read-only" is enforced

The read-only tabs are built without the controller or the runner; they only receive snapshots.
Their commands go through `runner.ReadOnly`, which runs only `git rev-parse/show/log/cat-file/diff --quiet`,
`gh run list/view`, the Kaggle CLI's `kernels list/status` and `datasets list`, the read-only WSL probe,
`fork version` and `sha256sum` of one `.epd` file in WSL; anything else raises before a process starts.
The tests run every collector and every
read-only tab's rendering under an audit hook that blocks any write, delete, rename, folder creation,
process start or file launch, and hash the fixture tree before and after.

## Tests

    python -I -m unittest discover -s tools/control_center -p "test_*.py"
    bash tools/control_center/test_start_part.sh        (Linux or WSL: the launch script with stubs)

Every external command is stubbed (a simulated WSL supervisor, git, gh, Kaggle); the parsers run on the
committed docs and manifests and on fixtures copied from the live logs (`fixtures/`, user paths replaced).
