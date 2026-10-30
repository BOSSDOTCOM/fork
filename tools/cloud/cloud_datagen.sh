#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Cloud self-play data generation, the part that runs on the instance (set
# up by tools/cloud/aws_spot_datagen.sh; also run locally by
# tools/cloud/test_cloud_datagen.sh with a local folder as the upload target).
#
# fork_datagen runs in chunks of --chunk-positions positions (about ten
# minutes each on 8 vCPU), so a spot interruption or the time limit loses
# at most the chunk in progress. Each finished chunk is checked
# (tools/datagen/verify_games.py against its run manifest), sealed as its
# own manifest (tools/datagen/upload_batch.py seal: the labelling network,
# which fork_datagen names itself, the openings file, and why the chunk
# ended; with --instance-type, also the machine: that type and the CPU model
# from /proc/cpuinfo, the build target being the generator's arch) and
# uploaded with its shards; then its local files are deleted.
# Chunk k uses seed --seed-base + k: cloud seed bases start at 10^12, far
# from the local runs' date-shaped seeds (about 2 x 10^7), so cloud and local
# games never share a seed.
#
#   tools/cloud/cloud_datagen.sh --run NAME --seed-base N --datagen BIN --openings EPD \
#       --openings-manifest JSON --tables DIR --upload-to DEST [--chunk-positions 1000000] \
#       [--nodes 20000] [--threads N] [--stop-at EPOCH] [--max-chunks 0] [--work DIR] \
#       [--instance-type TYPE]
#
# DEST is s3://BUCKET/PREFIX (aws s3 cp) or a local folder (cp). --stop-at
# (Unix time) stops before a chunk that would not finish by then (the
# instance's own shutdown comes later). SIGTERM (a spot interruption notice
# via tools/cloud/spot_watch.sh) stops the chunk in progress and ends the
# run; its log records the lost chunk. Exits 0 when at least one chunk was
# uploaded or the stop was clean.
set -uo pipefail
here=$(cd "$(dirname "$0")/../.." && pwd)
run="" seed_base="" datagen="" openings="" om="" tables="" dest="" chunk=1000000 nodes=20000
threads=$(nproc) stop_at=0 max_chunks=0 work="" instance_type=""
while [ $# -gt 0 ]; do
  case $1 in
    --run) run=$2 ;; --seed-base) seed_base=$2 ;; --datagen) datagen=$2 ;; --openings) openings=$2 ;;
    --openings-manifest) om=$2 ;; --tables) tables=$2 ;; --upload-to) dest=$2 ;;
    --chunk-positions) chunk=$2 ;; --nodes) nodes=$2 ;; --threads) threads=$2 ;;
    --stop-at) stop_at=$2 ;; --max-chunks) max_chunks=$2 ;; --work) work=$2 ;; --instance-type) instance_type=$2 ;;
    *) echo "cloud_datagen.sh: unknown option $1" >&2; exit 2 ;;
  esac
  shift 2
done
for v in run seed_base datagen openings om tables dest; do
  [ -n "${!v}" ] || { echo "cloud_datagen.sh: --${v//_/-} is required" >&2; exit 2; }
done
case "$seed_base$chunk$nodes$threads$stop_at$max_chunks" in *[!0-9]*) echo "numbers expected" >&2; exit 2 ;; esac
work=${work:-$(mktemp -d)}
mkdir -p "$work"
py=${PYTHON:-python3}
log() { echo "$(date -u +%FT%TZ) $*"; }
upload() {  # local file, name under DEST
  case $dest in
    s3://*) aws s3 cp --only-show-errors "$1" "${dest%/}/$2" ;;
    *) mkdir -p "$(dirname "$dest/$2")" && cp "$1" "$dest/$2" ;;
  esac
}
# The openings must be the manifest's file, byte for byte.
want=$("$py" -c 'import json,sys; print(json.load(open(sys.argv[1]))["output_sha256"])' "$om")
got=$(sha256sum "$openings" | cut -d' ' -f1)
[ "$got" = "$want" ] || { log "openings SHA-256 $got is not the manifest's $want"; exit 1; }

stopping=0 pid=""
trap 'stopping=1; [ -n "$pid" ] && kill -TERM "$pid" 2>/dev/null' TERM INT
k=0 uploaded=0 last=0
while :; do
  [ "$max_chunks" -gt 0 ] && [ "$k" -ge "$max_chunks" ] && { log "stop: $max_chunks chunks done"; break; }
  if [ "$stop_at" -gt 0 ] && [ $(( $(date +%s) + last * 3 / 2 + 60 )) -gt "$stop_at" ]; then
    log "stop: the next chunk would not finish before the time limit"
    break
  fi
  name=$(printf '%s-c%04d' "$run" "$k")
  dir=$work/$name
  mkdir -p "$dir"
  t0=$(date +%s)
  log "chunk $name: seed $((seed_base + k)), $chunk positions"
  "$datagen" --openings "$openings" --out "$dir" --run "$name" --positions "$chunk" --nodes "$nodes" \
    --threads "$threads" --seed $((seed_base + k)) --hash-mb 1 --shard-mb 1024 --tables "$tables" \
    >"$dir/datagen.log" 2>&1 &
  pid=$!
  wait "$pid"
  rc=$?
  pid=""
  if [ "$stopping" = 1 ]; then
    log "stop: interrupted (spot notice or signal); chunk $name lost (not finished)"
    break
  fi
  [ "$rc" -eq 0 ] && [ -f "$dir/$name.json" ] || { log "chunk $name failed (exit $rc)"; tail -5 "$dir/datagen.log"; exit 1; }
  "$py" -I "$here/tools/datagen/verify_games.py" "$dir"/*.vf --manifest "$dir/$name.json" >"$dir/verify.log" 2>&1 ||
    { log "chunk $name failed verification"; tail -5 "$dir/verify.log"; exit 1; }
  "$py" -I "$here/tools/datagen/upload_batch.py" seal "$dir/$name.json" --openings-manifest "$om" \
    --part-end "chunk complete: $chunk positions" --out "$dir/sealed" >/dev/null || { log "chunk $name: seal failed"; exit 1; }
  if [ -n "$instance_type" ]; then
    "$py" -I -c 'import json, sys
p, t, cpu = sys.argv[1:]
m = json.load(open(p))
m["machine"] = {"instance_type": t, "cpu": cpu}
open(p, "w", newline="\n").write(json.dumps(m, indent=1) + "\n")' "$dir/sealed/$name.json" "$instance_type" \
      "$(grep -m1 '^model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ *//')" || { log "chunk $name: machine record failed"; exit 1; }
  fi
  for f in "$dir"/*.vf; do upload "$f" "$name/$(basename "$f")" || { log "upload of $f failed"; exit 1; }; done
  upload "$dir/sealed/$name.json" "$name/$name.json" || { log "upload of $name.json failed"; exit 1; }
  upload "$dir/datagen.log" "$name/datagen.log" || true
  last=$(( $(date +%s) - t0 ))
  log "chunk $name uploaded in $last s: $(tail -1 "$dir/verify.log")"
  rm -rf "$dir"
  uploaded=$((uploaded + 1))
  k=$((k + 1))
done
log "run $run: $uploaded chunk(s) uploaded"
