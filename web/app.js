// SPDX-License-Identifier: GPL-3.0-or-later
// Fork's play page (DESIGN.md §5.5, the bare-bones version): a chessground
// board, a choice of colour, and Fork answering at a fixed node limit per
// move from its Web Worker. The engine is the only source of chess rules:
// legal moves, the resulting position and the game's end all come from it.
import { Chessground } from './vendor/chessground/chessground.min.js';

// Nodes Fork searches per move: a page setting (not a search constant), set
// so that a move takes about a second or less in a phone's browser.
const NodesPerMove = 200000;

const el = (id) => document.getElementById(id);
const board = el('board');
const statusLine = el('status');
const colourChoice = el('colour');
const promotionBox = el('promotion');

let worker = null;
let nextId = 1;
const pending = new Map();
let game = null; // {moves, human: 'white'|'black', over, busy}

function startWorker() {
  if (worker) worker.terminate();
  for (const { reject } of pending.values()) reject(new Error('engine restarted'));
  pending.clear();
  worker = new Worker('./engine-worker.js', { type: 'module' });
  worker.onmessage = (event) => {
    const reply = event.data;
    const waiter = pending.get(reply.id);
    if (!waiter) return;
    pending.delete(reply.id);
    if (reply.error) waiter.reject(new Error(reply.error));
    else waiter.resolve(reply);
  };
  worker.onerror = (event) => {
    statusLine.textContent = `The engine could not start: ${event.message || 'unknown error'}`;
  };
}

function ask(cmd, moves, nodes) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, cmd, moves, nodes });
  });
}

const ground = Chessground(board, {
  coordinates: true,
  movable: { free: false, color: undefined, showDests: true, events: { after: onHumanMove } },
  premovable: { enabled: false },
  drawable: { enabled: false },
  animation: { enabled: true, duration: 150 },
});

function turnOf(fen) {
  return fen.split(' ')[1] === 'w' ? 'white' : 'black';
}

// chessground's destination map from the engine's legal moves (a promotion
// appears once per piece, so destinations are kept once).
function destinations(legal) {
  const dests = new Map();
  for (const m of legal ? legal.split(' ') : []) {
    const from = m.slice(0, 2);
    const to = m.slice(2, 4);
    const list = dests.get(from) || [];
    if (!list.includes(to)) list.push(to);
    dests.set(from, list);
  }
  return dests;
}

const Endings = {
  checkmate: (loser) => `Checkmate: ${loser === 'white' ? 'Black' : 'White'} wins.`,
  stalemate: () => 'Draw by stalemate.',
  'fifty-move': () => 'Draw by the fifty-move rule.',
  repetition: () => 'Draw by threefold repetition.',
  insufficient: () => 'Draw: neither side can checkmate.',
};

function show(state) {
  const turn = turnOf(state.fen);
  const last = game.moves.length ? game.moves[game.moves.length - 1] : null;
  game.over = state.status !== 'playing';
  const humanToMove = !game.over && turn === game.human;
  ground.set({
    fen: state.fen.split(' ')[0],
    turnColor: turn,
    lastMove: last ? [last.slice(0, 2), last.slice(2, 4)] : undefined,
    movable: { color: humanToMove ? game.human : undefined, dests: humanToMove ? destinations(state.legal) : new Map() },
  });
  game.legal = state.legal ? state.legal.split(' ') : [];
  if (game.over) {
    statusLine.textContent = Endings[state.status](turn);
  } else {
    statusLine.textContent = humanToMove ? 'Your move.' : 'Fork is thinking…';
  }
  return humanToMove;
}

async function engineMove(token) {
  game.busy = true;
  try {
    const state = await ask('play', game.moves, NodesPerMove);
    if (token !== game) return;
    game.moves.push(state.move);
    show(state);
  } catch (err) {
    if (token === game) statusLine.textContent = `Engine error: ${err.message}`;
  } finally {
    if (token === game) game.busy = false;
  }
}

function choosePromotion() {
  return new Promise((resolve) => {
    promotionBox.hidden = false;
    for (const button of promotionBox.querySelectorAll('button')) {
      button.onclick = () => {
        promotionBox.hidden = true;
        resolve(button.dataset.piece);
      };
    }
  });
}

async function onHumanMove(from, to) {
  const token = game;
  let move = from + to;
  const options = game.legal.filter((m) => m.startsWith(move));
  if (options.length > 1) move += await choosePromotion();
  if (token !== game) return;
  if (!game.legal.includes(move)) {
    statusLine.textContent = 'That move is not legal here.';
    return;
  }
  game.moves.push(move);
  try {
    const state = await ask('state', game.moves);
    if (token !== game) return;
    if (!show(state) && !game.over) await engineMove(token);
  } catch (err) {
    if (token === game) statusLine.textContent = `Engine error: ${err.message}`;
  }
}

async function newGame() {
  // A search cannot be interrupted: a new game during one restarts the engine.
  if (!worker || (game && game.busy)) startWorker();
  promotionBox.hidden = true;
  const choice = colourChoice.value;
  const human = choice === 'random' ? (Math.random() < 0.5 ? 'white' : 'black') : choice;
  game = { moves: [], human, over: false, busy: false, legal: [] };
  const token = game;
  ground.set({ orientation: human, lastMove: undefined });
  statusLine.textContent = 'Starting the engine…';
  try {
    const state = await ask('new', []);
    if (token !== game) return;
    if (!show(state)) await engineMove(token);
  } catch (err) {
    if (token === game) statusLine.textContent = `Engine error: ${err.message}`;
  }
}

// Light and dark: the system's choice unless the visitor picks one here.
function applyTheme(theme) {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}
function savedTheme() {
  try {
    return localStorage.getItem('fork-theme');
  } catch {
    return null;
  }
}
applyTheme(savedTheme());
el('theme').addEventListener('click', () => {
  const dark =
    document.documentElement.dataset.theme === 'dark' ||
    (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
  const next = dark ? 'light' : 'dark';
  applyTheme(next);
  try {
    localStorage.setItem('fork-theme', next);
  } catch {
    // no storage: the choice lasts for this visit only
  }
});

el('new-game').addEventListener('click', newGame);
newGame();
