#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Brings a cloud data-generation run home (owner, 2026-10-30): downloads its
# chunks (tools/cloud/cloud_datagen.sh's uploads) from S3 or a local folder,
# checks every shard against its chunk's sealed manifest (bytes and
# SHA-256), replays every game with tools/datagen/verify_games.py against
# the manifest's counts, requires the manifest to name its labelling network
# and why the chunk ended, and copies the verified chunks and manifests to
# OUT. With --kaggle-id it then creates a private Kaggle dataset from OUT
# with the owner's Kaggle CLI (its token stays in the CLI's own file).
#
#   tools/cloud/pull_datagen.sh --from s3://BUCKET/datagen/RUN | DIR --to OUT
#       [--kaggle-cli PATH --kaggle-id OWNER/NAME --title TEXT]
#
# Exits non-zero, uploading nothing, if any chunk fails a check.
set -uo pipefail
here=$(cd "$(dirname "$0")/../.." && pwd)
from="" to="" kcli="" kid="" title=""
while [ $# -gt 0 ]; do
  case $1 in
    --from) from=$2 ;; --to) to=$2 ;; --kaggle-cli) kcli=$2 ;; --kaggle-id) kid=$2 ;; --title) title=$2 ;;
    *) echo "pull_datagen.sh: unknown option $1" >&2; exit 2 ;;
  esac
  shift 2
done
[ -n "$from" ] && [ -n "$to" ] || { echo "pull_datagen.sh: --from and --to are required" >&2; exit 2; }
py=${PYTHON:-python3}
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
case $from in
  s3://*) aws s3 cp --only-show-errors --recursive "${from%/}/" "$stage/" || { echo "download failed" >&2; exit 1; } ;;
  *) cp -r "$from"/. "$stage/" ;;
esac
mkdir -p "$to"
chunks=0 positions=0
for d in "$stage"/*/; do
  name=$(basename "$d")
  man=$d$name.json
  [ -f "$man" ] || { echo "$name: no sealed manifest" >&2; exit 1; }
  # Shards against the sealed manifest; the labelling net and the reason named.
  "$py" - "$man" "$d" >"$stage/$name.check" <<'EOF' || { cat "$stage/$name.check" >&2; exit 1; }
import hashlib, json, os, sys
man, d = json.load(open(sys.argv[1])), sys.argv[2]
ev = man['generator']['evaluator']
if ev == 'nnue' or not man.get('part_end', '').strip():
    sys.exit(f"{man['run']}: the manifest must name its labelling network and why it ended ({ev!r})")
shards = [s for b in man['batches'] for s in b]
for s in shards:
    p = os.path.join(d, s['file'])
    if os.path.getsize(p) != s['bytes']:
        sys.exit(f"{s['file']}: {os.path.getsize(p)} bytes, the manifest says {s['bytes']}")
    h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    if h != s['sha256']:
        sys.exit(f"{s['file']}: SHA-256 differs from the manifest")
# The run's settings travel along: verify_games.py reads the score
# adjudication and the split search's settings from them.
json.dump({'shards': shards, 'settings': man['settings'], 'positions_unsaved': man.get('positions_unsaved', 0)},
          open(os.path.join(d, 'shards.json'), 'w'))
print(man['positions'], ev)
EOF
  "$py" -I "$here/tools/datagen/verify_games.py" "$d"*.vf --manifest "$d/shards.json" >"$stage/$name.verify" 2>&1 ||
    { echo "$name: game check failed" >&2; tail -3 "$stage/$name.verify" >&2; exit 1; }
  read -r n ev <"$stage/$name.check"
  echo "$name: $n positions, $ev, shards and games verified"
  positions=$((positions + n))
  chunks=$((chunks + 1))
done
[ "$chunks" -gt 0 ] || { echo "pull_datagen.sh: no chunks found in $from" >&2; exit 1; }
for d in "$stage"/*/; do
  name=$(basename "$d")
  cp "$d"*.vf "$d$name.json" "$to/"
done
echo "$chunks chunk(s), $positions positions verified into $to"
if [ -n "$kid" ]; then
  [ -n "$kcli" ] || { echo "pull_datagen.sh: --kaggle-id needs --kaggle-cli" >&2; exit 2; }
  printf '{\n  "title": "%s",\n  "id": "%s",\n  "licenses": [{"name": "other"}],\n  "keywords": ["synthetic"]\n}\n' \
    "${title:-${kid#*/}}" "$kid" >"$to/dataset-metadata.json"
  # The Kaggle CLI wants the folder as a path relative to where it runs.
  (cd "$(dirname "$to")" && "$kcli" datasets create -p "$(basename "$to")") || { echo "Kaggle upload failed" >&2; exit 1; }
fi
