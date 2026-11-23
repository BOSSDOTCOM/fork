#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# fork-paths: ok-file runs only on the Google Cloud VM (Linux)
# Standard data generation as the Google Cloud worker's filler (class c, preemptible; docs/gcp-worker.md):
# tools/cloud/cloud_datagen.sh in chunks, each verified and sealed on the VM into $W/out/filler/RUN/, with the
# standing generation settings given here (the Control Center's for generation 4: 20,000 nodes, adjudication
# 700 cp x 8 plies, the split search at 50% saved, 4,000 unsaved nodes, 2,000 check nodes, hash 1 MB, Syzygy
# 3-4-5). Every start is a new run, so a stop (a more urgent item, a preemption) loses only the chunk in
# progress and no seed is ever used twice:
#   run   GEN-gcp-YYYYmmddTHHMMSSZ (the start time, UTC)
#   seeds 10^14 + start time in Unix seconds x 1000 + chunk (chunk < 1000), far above the AWS runs' rule
#         (10^12 + (4 x launch + slot) x 1000 + k, below 10^13 until 2033) and the local date seeds (~2 x 10^7).
# The PC brings the runs home with gcp.py pull filler and checks every chunk again with
# tools/cloud/pull_datagen.sh --from <staging>/filler/RUN --to OUT before any use.
#
#   bash filler.sh BUILD_DIR PIN_DATAGEN OPENINGS OPENINGS_MANIFEST GEN [CHUNK_POSITIONS]
set -euo pipefail
build=${1:?usage: filler.sh BUILD_DIR PIN_DATAGEN OPENINGS OPENINGS_MANIFEST GEN [CHUNK_POSITIONS]}
pin=$2 openings=$3 om=$4 gen=$5 chunk=${6:-250000}
W=${FORK_WORKER_ROOT:-/opt/fork}
here=$(cd "$(dirname "$0")/../.." && pwd)
[ "$(sha256sum "$build/fork_datagen" | cut -c1-64)" = "$pin" ] || { echo "filler.sh: $build/fork_datagen does not match its pin" >&2; exit 1; }
case $gen in g[0-9]*) ;; *) echo "filler.sh: GEN like g4" >&2; exit 2 ;; esac
launch=$(date -u +%s)
run=$gen-gcp-$(date -u -d "@$launch" +%Y%m%dT%H%M%SZ)
mtype=$(curl -s -m 5 -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/instance/machine-type | sed 's#.*/##')
mkdir -p "$W/out/filler" "$W/work/filler"
echo "filler run $run, seeds from $((100000000000000 + launch * 1000)), chunks of $chunk, machine ${mtype:-unknown}"
rc=0
PYTHON=$W/venv/bin/python bash "$here/tools/cloud/cloud_datagen.sh" --run "$run" \
  --seed-base $((100000000000000 + launch * 1000)) --datagen "$build/fork_datagen" --openings "$openings" \
  --openings-manifest "$om" --tables "$W/syzygy" --upload-to "$W/out/filler/$run" --chunk-positions "$chunk" \
  --nodes 20000 --threads "$(nproc)" --work "$W/work/filler/$run" --instance-type "gcp ${mtype:-unknown}" \
  --adjudicate-cp 700 --adjudicate-plies 8 --save-percent 50 --unsaved-nodes 4000 --check-nodes 2000 || rc=$?
rm -rf "$W/work/filler/$run"
printf '{"run": "%s", "exit": %d, "chunks": %d}\n' "$run" "$rc" \
  "$(find "$W/out/filler/$run" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)" >"$W/out/filler/last-end.json"
exit $rc
