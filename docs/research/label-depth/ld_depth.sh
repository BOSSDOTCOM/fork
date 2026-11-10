#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The probe's depth sample (design section 1.6): tools/datagen/measure_nodes.py (go nodes from a cleared table,
# the median completed depth) with the experiment's fork binary, on 200 saved non-check positions per arm
# (ld_sample.py): each arm's own positions at its own --nodes and Hash, and D20's positions at all three settings.
#   bash ld_depth.sh REPO PROBE_DIR
set -euo pipefail
REPO=$1 D=$2
FORK=$HOME/fork-data/ld-builds/pgo/fork
M="python3 -I $REPO/tools/datagen/measure_nodes.py $FORK"
echo "== each arm's own positions at its own setting"
$M --epd "$D/sample-d20.epd" --nodes 20000 --hash-mb 1
$M --epd "$D/sample-d50.epd" --nodes 50000 --hash-mb 3
$M --epd "$D/sample-d100.epd" --nodes 100000 --hash-mb 5
echo "== D20's positions at the three settings"
$M --epd "$D/sample-d20.epd" --nodes 50000 --hash-mb 3
$M --epd "$D/sample-d20.epd" --nodes 100000 --hash-mb 5
