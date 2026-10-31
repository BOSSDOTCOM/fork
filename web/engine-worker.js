// SPDX-License-Identifier: GPL-3.0-or-later
// The engine's Web Worker (DESIGN.md §5.5): Fork compiled to WebAssembly
// (fork_web.js, src/web/web_engine.hpp), single-threaded, so a search runs to
// its node limit here while the page stays responsive.
//
// Messages in: {id, cmd: 'state' | 'play' | 'new', moves: [uci...], nodes}.
//   state: the position after `moves` (legal moves, status, FEN);
//   play:  Fork searches that position, plays its best move, and replies with
//          the move and the new position;
//   new:   clears the hash table and history, then as state.
// Messages out: {id, move?, info?, legal, status, fen} or {id, error}.
import createFork from './fork_web.js';

const HashMb = 16;
let fork = null;

const ready = createFork().then((m) => {
  fork = {
    init: m.cwrap('fork_web_init', 'number', ['number']),
    setPosition: m.cwrap('fork_web_set_position', 'number', ['string', 'string']),
    fen: m.cwrap('fork_web_fen', 'string', []),
    legal: m.cwrap('fork_web_legal_moves', 'string', []),
    status: m.cwrap('fork_web_status', 'string', []),
    search: m.cwrap('fork_web_search', 'string', ['number']),
    newGame: m.cwrap('fork_web_new_game', null, []),
  };
  if (fork.init(HashMb) !== 1) throw new Error('no memory for the hash table');
});

function describe(id, extra) {
  return { id, ...extra, legal: fork.legal(), status: fork.status(), fen: fork.fen() };
}

onmessage = async (event) => {
  const { id, cmd, moves = [], nodes = 1 } = event.data;
  try {
    await ready;
  } catch (err) {
    postMessage({ id, error: String(err) });
    return;
  }
  if (cmd === 'new') fork.newGame();
  if (fork.setPosition('startpos', moves.join(' ')) !== 1) {
    postMessage({ id, error: 'illegal move list' });
    return;
  }
  if (cmd !== 'play') {
    postMessage(describe(id, {}));
    return;
  }
  const info = fork.search(nodes);
  const move = info.split(' ')[1];
  if (!move || move === 'none' || fork.setPosition('startpos', [...moves, move].join(' ')) !== 1) {
    postMessage({ id, error: `no move from the engine (${info})` });
    return;
  }
  postMessage(describe(id, { move, info }));
};
