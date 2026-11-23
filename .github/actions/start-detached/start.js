// SPDX-License-Identifier: GPL-3.0-or-later
// The action of action.yml beside this file: start `command` with bash, detached (a session of its own,
// output to `log`), and return at once. Never fails the step.
'use strict';
const { spawn } = require('child_process');
const fs = require('fs');

const command = process.env['INPUT_COMMAND'] || '';
const log = process.env['INPUT_LOG'] || '';
// The step's environment without this action's own inputs (a command that runs another action's code, as
// tools/cloud/progress_upload.sh does, sets that action's inputs itself).
const env = {};
for (const [key, value] of Object.entries(process.env)) {
  if (!key.startsWith('INPUT_')) env[key] = value;
}
env['FORK_PROGRESS_NODE'] = process.execPath;
try {
  if (!command || !log) throw new Error('the inputs command and log are required');
  const out = fs.openSync(log, 'a');
  const child = spawn('bash', ['-c', command], {
    detached: true,
    stdio: ['ignore', out, out],
    env,
    cwd: process.env['GITHUB_WORKSPACE'] || process.cwd(),
  });
  child.on('error', (e) => console.log(`::warning::start-detached: the command did not start: ${e.message}`));
  child.unref();
  fs.closeSync(out);
  console.log(`start-detached: started process ${child.pid}; output to ${log}`);
} catch (e) {
  console.log(`::warning::start-detached: the command did not start: ${e.message}`);
}
