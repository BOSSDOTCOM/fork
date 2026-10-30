#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# End-to-end dry run of cloud data generation without AWS:
# tools/cloud/cloud_datagen.sh (the instance's part) uploads to a local
# folder, then tools/cloud/pull_datagen.sh (the owner's side) verifies it.
# Uses a real fork_datagen build of a commit that names its network
# (3978e91 or later), the Syzygy 3-4-5 tables and tests/datagen_openings.epd.
#
#   bash tools/cloud/test_cloud_datagen.sh FORK_DATAGEN TABLES_DIR [PYTHON]
#
# PYTHON needs python-chess (tools/datagen/verify_games.py).
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
datagen=${1:?usage: test_cloud_datagen.sh FORK_DATAGEN TABLES_DIR [PYTHON]}
tables=${2:?usage: test_cloud_datagen.sh FORK_DATAGEN TABLES_DIR [PYTHON]}
export PYTHON=${3:-python3}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0
check() {  # description, command...
  local what=$1
  shift
  if "$@"; then echo "PASS  $what"; else echo "FAIL  $what"; failures=$((failures + 1)); fi
}
openings=$repo/tests/datagen_openings.epd
printf '{"output": "datagen_openings.epd", "output_sha256": "%s", "positions": %d, "source": "tests", "source_sha256": "-"}\n' \
  "$(sha256sum "$openings" | cut -d' ' -f1)" "$(wc -l <"$openings")" >"$tmp/om.json"
common=(--datagen "$datagen" --openings "$openings" --openings-manifest "$tmp/om.json" --tables "$tables"
  --chunk-positions 3000 --nodes 1000 --threads 2)

# 1. Two chunks, uploaded with sealed manifests.
bash "$here/cloud_datagen.sh" --run t1 --seed-base 1000000000000 --upload-to "$tmp/up1" --max-chunks 2 \
  --work "$tmp/w1" "${common[@]}" >"$tmp/run1.log" 2>&1
check "two chunks run and upload" [ -f "$tmp/up1/t1-c0000/t1-c0000.json" ] && [ -f "$tmp/up1/t1-c0001/t1-c0001.json" ]
check "the sealed manifest names the labelling network and why the chunk ended" \
  "$PYTHON" -c 'import json,sys; m=json.load(open(sys.argv[1])); sys.exit(not (m["generator"]["evaluator"].startswith("nnue (") and m["part_end"].startswith("chunk complete")))' \
  "$tmp/up1/t1-c0000/t1-c0000.json"
check "each chunk has its own seed from the base" \
  "$PYTHON" -c 'import json,sys; s=[json.load(open(p))["settings"]["seed"] for p in sys.argv[1:]]; sys.exit(s != [1000000000000, 1000000000001])' \
  "$tmp/up1/t1-c0000/t1-c0000.json" "$tmp/up1/t1-c0001/t1-c0001.json"
check "finished chunks leave no local files" [ -z "$(ls -A "$tmp/w1")" ]

# 2. A SIGTERM (spot notice) during a chunk: the run stops, that chunk is lost.
bash "$here/cloud_datagen.sh" --run t2 --seed-base 1000000000000 --upload-to "$tmp/up2" \
  --work "$tmp/w2" "${common[@]}" --chunk-positions 2000000 >"$tmp/run2.log" 2>&1 &
job=$!
sleep 3
kill -TERM $job
wait $job
check "an interrupted run stops and records the lost chunk" grep -q "chunk t2-c0000 lost" "$tmp/run2.log"
check "nothing partial is uploaded" [ ! -e "$tmp/up2/t2-c0000" ]
check "the interrupted datagen process is gone" bash -c "! pgrep -f '[-]-run t2-c0000' >/dev/null"

# 3. A time limit already reached starts nothing.
bash "$here/cloud_datagen.sh" --run t3 --seed-base 1 --upload-to "$tmp/up3" --work "$tmp/w3" \
  --stop-at "$(date +%s)" "${common[@]}" >"$tmp/run3.log" 2>&1
check "no chunk starts after the time limit" grep -q "would not finish before the time limit" "$tmp/run3.log"

# 4. Openings that are not the manifest's file are refused.
sed 's/"output_sha256": "./"output_sha256": "0/' "$tmp/om.json" >"$tmp/om-bad.json"
bash "$here/cloud_datagen.sh" --run t4 --seed-base 1 --upload-to "$tmp/up4" --work "$tmp/w4" \
  "${common[@]}" --openings-manifest "$tmp/om-bad.json" >"$tmp/run4.log" 2>&1
check "wrong openings are refused" [ $? -ne 0 ] && grep -q "is not the manifest's" "$tmp/run4.log"

# 5. The owner's side verifies the uploads, and rejects a damaged shard.
# (A chunk ends with whole games, so it holds a few more positions than asked.)
total=$("$PYTHON" -c 'import json,sys; print(sum(json.load(open(p))["positions"] for p in sys.argv[1:]))' \
  "$tmp/up1/t1-c0000/t1-c0000.json" "$tmp/up1/t1-c0001/t1-c0001.json")
bash "$here/pull_datagen.sh" --from "$tmp/up1" --to "$tmp/home" >"$tmp/pull.log" 2>&1
check "pull_datagen verifies both chunks" grep -q "2 chunk(s), $total positions verified" "$tmp/pull.log"
check "the verified shards and manifests are copied home" [ "$(ls "$tmp/home" | wc -l)" -ge 4 ]
shard=$(ls "$tmp"/up1/t1-c0001/*.vf | head -1)
printf 'x' | dd of="$shard" bs=1 seek=40 conv=notrunc 2>/dev/null
bash "$here/pull_datagen.sh" --from "$tmp/up1" --to "$tmp/home2" >"$tmp/pull2.log" 2>&1
check "a damaged shard is rejected" [ $? -ne 0 ] && grep -q "SHA-256 differs" "$tmp/pull2.log"

echo "$failures failure(s)"
[ $failures -eq 0 ]
