// SPDX-License-Identifier: GPL-3.0-or-later
// One engine for the page (DESIGN.md §5.5): a Web Worker running one
// network's module (engine-worker.js), with requests matched to replies. A
// search cannot be interrupted, so stopping one ends the worker; the next
// request starts a fresh one.

export class EngineClient {
  constructor(net) {
    this.net = net;
    this.worker = null;
    this.nextId = 1;
    this.pending = new Map(); // id -> {resolve, reject, onProgress}
  }

  start() {
    this.worker = new Worker(`./engine-worker.js?net=${encodeURIComponent(this.net)}`, { type: 'module' });
    this.worker.onmessage = (event) => {
      const reply = event.data;
      const waiter = this.pending.get(reply.id);
      if (!waiter) return;
      if (reply.progress) {
        if (waiter.onProgress) waiter.onProgress(reply.progress);
        return;
      }
      this.pending.delete(reply.id);
      if (reply.error) waiter.reject(new Error(reply.error));
      else waiter.resolve(reply);
    };
    this.worker.onerror = (event) => {
      event.preventDefault();
      this.fail(new Error(`the engine could not start (${event.message || 'module failed to load'})`));
    };
  }

  // Sends {cmd, ...args}; resolves with the final reply.
  ask(cmd, args = {}, onProgress = null) {
    if (!this.worker) this.start();
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, onProgress });
      this.worker.postMessage({ id, cmd, ...args });
    });
  }

  fail(err) {
    for (const { reject } of this.pending.values()) reject(err);
    this.pending.clear();
  }

  // Ends the worker (and any search in it); pending requests are rejected.
  stop() {
    if (this.worker) this.worker.terminate();
    this.worker = null;
    this.fail(new Error('engine stopped'));
  }
}

// The network manifest (nets.json, filled in when the page is built).
export async function loadNetworks() {
  const response = await fetch('./nets.json');
  if (!response.ok) throw new Error(`nets.json: ${response.status}`);
  return response.json();
}
