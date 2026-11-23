#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Uploads one file as a workflow artifact from a background process of a GitHub job, replacing the artifact
# of the same name (the shard progress records, tools/cloud/shard_progress.py; owner, 2026-11-14). A `run`
# step cannot use actions/upload-artifact while another step runs, so this runs that action's own bundled
# code (dist/upload/index.js, which the runner fetched for the job because a step of the job uses
# actions/upload-artifact@v4) with node, its inputs given as the runner gives them (INPUT_<NAME> variables),
# overwrite on. It needs the job's runtime credentials (ACTIONS_RUNTIME_TOKEN, ACTIONS_RESULTS_URL), which
# only an action's process gets: .github/actions/start-detached starts the watcher from one, and passes its
# node as FORK_PROGRESS_NODE. The action's file outputs and summary go to a scratch folder, never the job's.
#
#   tools/cloud/progress_upload.sh NAME FILE
#
# FORK_UPLOAD_ARTIFACT_JS overrides the bundled action's path (tests). Exit status: the upload's (non-zero
# when it failed, or when the uploader, node or the credentials are missing). The caller ignores a failure.
set -uo pipefail
name=${1:?usage: progress_upload.sh NAME FILE} file=${2:?usage: progress_upload.sh NAME FILE}
node=${FORK_PROGRESS_NODE:-$(command -v node || true)}
js=${FORK_UPLOAD_ARTIFACT_JS:-}
if [ -z "$js" ] && [ -n "${RUNNER_WORKSPACE:-}" ]; then
  c="$(dirname "$RUNNER_WORKSPACE")/_actions/actions/upload-artifact/v4/dist/upload/index.js"
  [ -f "$c" ] && js=$c
fi
[ -n "$node" ] || { echo "progress_upload.sh: no node" >&2; exit 1; }
[ -n "$js" ] && [ -f "$js" ] || { echo "progress_upload.sh: no actions/upload-artifact@v4 on this runner" >&2; exit 1; }
[ -n "${ACTIONS_RUNTIME_TOKEN:-}" ] && [ -n "${ACTIONS_RESULTS_URL:-}" ] ||
  { echo "progress_upload.sh: no runtime credentials (not started from an action)" >&2; exit 1; }
[ -f "$file" ] || { echo "progress_upload.sh: no file $file" >&2; exit 1; }
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
for f in output env path state summary; do : >"$scratch/$f"; done
env INPUT_NAME="$name" INPUT_PATH="$file" "INPUT_IF-NO-FILES-FOUND=error" "INPUT_RETENTION-DAYS=3" \
  "INPUT_COMPRESSION-LEVEL=6" INPUT_OVERWRITE=true "INPUT_INCLUDE-HIDDEN-FILES=false" \
  GITHUB_OUTPUT="$scratch/output" GITHUB_ENV="$scratch/env" GITHUB_PATH="$scratch/path" \
  GITHUB_STATE="$scratch/state" GITHUB_STEP_SUMMARY="$scratch/summary" \
  "$node" "$js"
