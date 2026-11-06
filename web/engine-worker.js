// SPDX-License-Identifier: GPL-3.0-or-later
// The engine's Web Worker (DESIGN.md §5.5): Fork compiled to WebAssembly
// (engines/<net>/fork_web.js, src/web/web_engine.hpp), single-threaded, so a
// search runs to its node limit here while the page stays responsive. The
// network is the worker's `net` URL parameter: each network is its own
// module, downloaded only when a worker asks for it.
//
// Messages in: {id, cmd, fen, moves: [uci...], nodes, fens}, the position
// being `fen` ('startpos' or a FEN) after `moves`:
//   state: the position (legal moves, status, FEN, the moves in SAN);
//   new:   clears the hash table and history, then as state;
//   play:  Fork searches the position, sending {id, progress} after each
//          finished iteration, then plays its best move and replies with the
//          move, the search's report and the new position;
//   eval:  the static evaluation of each FEN of `fens` (side to move's view).
// Messages out: {id, progress} during play; {id, move?, report?, evals?,
// legal, status, fen, sans} at the end; or {id, error}.
import { parseReport } from './chess-text.js';

const HashMb = 16;
const net = new URL(self.location.href).searchParams.get('net') || '';
let fork = null;
let module = null;

const ready = (async () => {
  if (!/^[a-z0-9]+$/.test(net)) throw new Error(`no such network: ${net}`);
  const { default: createFork } = await import(`./engines/${net}/fork_web.js`);
  module = await createFork();
  fork = {
    init: module.cwrap('fork_web_init', 'number', ['number']),
    setPosition: module.cwrap('fork_web_set_position', 'number', ['string', 'string']),
    fen: module.cwrap('fork_web_fen', 'string', []),
    legal: module.cwrap('fork_web_legal_moves', 'string', []),
    status: module.cwrap('fork_web_status', 'string', []),
    san: module.cwrap('fork_web_san', 'string', ['string', 'string', 'string']),
    evaluate: module.cwrap('fork_web_evaluate', 'number', []),
    search: module.cwrap('fork_web_search', 'string', ['number']),
    newGame: module.cwrap('fork_web_new_game', null, []),
  };
  if (fork.init(HashMb) !== 1) throw new Error('no memory for the hash table');
})();

function words(list) {
  return list ? list.split(' ').filter(Boolean) : [];
}

function describe(id, base, moves, extra) {
  return {
    id,
    ...extra,
    legal: fork.legal(),
    status: fork.status(),
    fen: fork.fen(),
    sans: words(fork.san(base, '', moves.join(' '))),
  };
}

onmessage = async (event) => {
  const { id, cmd, fen = 'startpos', moves = [], nodes = 1, fens = [] } = event.data;
  try {
    await ready;
  } catch (err) {
    postMessage({ id, error: String(err.message || err) });
    return;
  }
  if (cmd === 'eval') {
    const evals = fens.map((f) => (fork.setPosition(f, '') === 1 ? fork.evaluate() : null));
    postMessage({ id, evals });
    return;
  }
  if (cmd === 'new') fork.newGame();
  if (fork.setPosition(fen, moves.join(' ')) !== 1) {
    postMessage({ id, error: 'illegal position or move list' });
    return;
  }
  if (cmd !== 'play') {
    postMessage(describe(id, fen, moves, {}));
    return;
  }
  const played = moves.join(' ');
  // Each finished iteration, with its line in SAN (fork_web_san works on a
  // position of its own, so it is safe to call during the search).
  module.onIteration = (line) => {
    const progress = parseReport(line);
    progress.pvSan = words(fork.san(fen, played, progress.pv.join(' ')));
    postMessage({ id, progress });
  };
  const text = fork.search(nodes);
  module.onIteration = null;
  const report = parseReport(text);
  report.pvSan = words(fork.san(fen, played, report.pv.join(' ')));
  const move = report.best;
  if (!move || fork.setPosition(fen, [...moves, move].join(' ')) !== 1) {
    postMessage({ id, error: `no move from the engine (${text})` });
    return;
  }
  postMessage(describe(id, fen, [...moves, move], { move, report }));
};
