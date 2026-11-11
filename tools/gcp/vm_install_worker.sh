#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Installs the queue worker (tools/gcp/worker.py) on the Google Cloud VM as the systemd service fork-worker
# (docs/gcp-worker.md). Run on the VM as the worker user after vm_setup.sh:
#
#   bash vm_install_worker.sh TOOLS_COMMIT [--no-start]
#
# The worker's own code comes from TOOLS_COMMIT (a full commit of the public repository), checked out in
# $W/tools, separate from the engine builds (which vm_setup.sh pins by SHA-256). The service starts at every
# boot (so a preempted VM resumes its queue when it is started again), restarts the worker if it dies, and
# leaves the jobs alone when the worker itself restarts (KillMode=process: the jobs belong to the job
# supervisor, tools/jobs/jobctl.py, with FORK_JOBS=$W/jobs). --no-start installs and enables it without
# starting it.
set -euo pipefail
commit=${1:?usage: vm_install_worker.sh TOOLS_COMMIT [--no-start]}
[[ $commit =~ ^[0-9a-f]{40}$ ]] || { echo "vm_install_worker.sh: TOOLS_COMMIT must be a full 40-hex commit" >&2; exit 2; }
W=${FORK_WORKER_ROOT:-/opt/fork}
[ -d "$W/src/.git" ] || { echo "vm_install_worker.sh: run vm_setup.sh first ($W/src missing)" >&2; exit 1; }
git -C "$W/src" fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
if [ -d "$W/tools/.git" ] || [ -f "$W/tools/.git" ]; then
  git -C "$W/tools" checkout -q --detach "$commit"
else
  git -C "$W/src" worktree add -q --detach "$W/tools" "$commit"
fi
[ "$(git -C "$W/tools" rev-parse HEAD)" = "$commit" ] || { echo "vm_install_worker.sh: tools checkout is not $commit" >&2; exit 1; }
mkdir -p "$W/queue" "$W/state/items" "$W/jobs" "$W/logs" "$W/out"
sudo tee /etc/systemd/system/fork-worker.service >/dev/null <<EOF
[Unit]
Description=Fork CPU worker queue (tools/gcp/worker.py, tools commit ${commit:0:12})
After=network-online.target
Wants=network-online.target

[Service]
User=$(id -un)
Environment=FORK_WORKER_ROOT=$W
Environment=FORK_JOBS=$W/jobs
ExecStart=/usr/bin/python3 -I $W/tools/tools/gcp/worker.py run --interval 30
Restart=always
RestartSec=30
KillMode=process

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable fork-worker.service >/dev/null
if [ "${2:-}" != --no-start ]; then sudo systemctl restart fork-worker.service; fi
systemctl is-enabled fork-worker.service
echo "worker installed from ${commit:0:12}"
