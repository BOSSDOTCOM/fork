// SPDX-License-Identifier: GPL-3.0-or-later
// Fork's page (DESIGN.md §5.5): the Play tab (a chessground board, a choice
// of colour and strength, Fork answering from its Web Worker with an
// evaluation bar and its principal variation), the theme and the tabs. The
// "Watch it learn" tab is watch.js. The engine is the only source of chess
// rules: legal moves, the resulting position, the notation and the game's
// end all come from it.
import { Chessground } from './vendor/chessground/chessground.min.js';
import { countText, endingText, lastMoveChecks, numberedLine, turnOf } from './chess-text.js';
import { EngineClient, loadNetworks } from './engine-client.js';
import { setBar } from './eval-bar.js';
import { startWatchTab } from './watch.js';

// Strength levels: nodes Fork searches per move (page settings, not search
// constants; no rating is claimed for any of them). 200,000 keeps a phone's
// move near a second.
const Levels = [
  { nodes: 1000, name: 'Gentle' },
  { nodes: 10000, name: 'Easy' },
  { nodes: 50000, name: 'Medium' },
  { nodes: 200000, name: 'Standard' },
  { nodes: 1000000, name: 'Strong (slow on phones)' },
];
const DefaultLevel = 200000;

const el = (id) => document.getElementById(id);
const statusLine = el('status');
const colourChoice = el('colour');
const levelChoice = el('level');
const promotionBox = el('promotion');

let engine = null;
let net = null; // the playing network's manifest entry
let game = null; // {moves, sans, human, over, busy, legal}

const ground = Chessground(el('board'), {
  coordinates: true,
  movable: { free: false, color: undefined, showDests: true, events: { after: onHumanMove } },
  premovable: { enabled: false },
  drawable: { enabled: false },
  animation: { enabled: true, duration: 150 },
});

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

function showLine(report, rootFen) {
  if (!report || !report.score) return;
  const whiteToMove = turnOf(rootFen) === 'white';
  setBar(el('bar'), el('bar-score'), report.score, whiteToMove, net.scale, game.human);
  el('pv').textContent = numberedLine(rootFen, report.pvSan || []);
  el('search-info').textContent = `depth ${report.depth}, ${countText(report.nodes)} positions`;
}

function show(state) {
  const turn = turnOf(state.fen);
  const last = game.moves.length ? game.moves[game.moves.length - 1] : null;
  game.over = state.status !== 'playing';
  game.sans = state.sans;
  const humanToMove = !game.over && turn === game.human;
  ground.set({
    fen: state.fen.split(' ')[0],
    turnColor: turn,
    check: lastMoveChecks(state.sans),
    lastMove: last ? [last.slice(0, 2), last.slice(2, 4)] : undefined,
    movable: { color: humanToMove ? game.human : undefined, dests: humanToMove ? destinations(state.legal) : new Map() },
  });
  game.legal = state.legal ? state.legal.split(' ') : [];
  el('moves').textContent = numberedLine('startpos', game.sans);
  if (game.over) {
    statusLine.textContent = endingText(state.status, turn);
  } else {
    statusLine.textContent = humanToMove ? 'Your move.' : 'Fork is thinking…';
  }
  return humanToMove;
}

async function engineMove(token) {
  game.busy = true;
  const rootFen = game.fen;
  try {
    const state = await engine.ask('play', { moves: game.moves, nodes: game.nodes }, (progress) => {
      if (token === game) showLine(progress, rootFen);
    });
    if (token !== game) return;
    game.moves.push(state.move);
    game.fen = state.fen;
    showLine(state.report, rootFen);
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
    const state = await engine.ask('state', { moves: game.moves });
    if (token !== game) return;
    game.fen = state.fen;
    if (!show(state) && !game.over) await engineMove(token);
  } catch (err) {
    if (token === game) statusLine.textContent = `Engine error: ${err.message}`;
  }
}

function remembered(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function remember(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // no storage: the choice lasts for this visit only
  }
}

async function newGame() {
  // A search cannot be interrupted: a new game during one restarts the engine.
  if (game && game.busy) engine.stop();
  promotionBox.hidden = true;
  const choice = colourChoice.value;
  const human = choice === 'random' ? (Math.random() < 0.5 ? 'white' : 'black') : choice;
  const nodes = Number(levelChoice.value);
  game = { moves: [], sans: [], human, over: false, busy: false, legal: [], nodes, fen: 'startpos' };
  const token = game;
  ground.set({ orientation: human, lastMove: undefined });
  setBar(el('bar'), el('bar-score'), null, true, net.scale, human);
  el('bar-score').textContent = '';
  el('pv').textContent = '';
  el('search-info').textContent = '';
  el('moves').textContent = '';
  el('level-note').textContent = `Fork searches ${countText(nodes)} positions per move, running entirely on this device.`;
  statusLine.textContent = 'Starting the engine…';
  try {
    const state = await engine.ask('new', { moves: [] });
    if (token !== game) return;
    game.fen = state.fen;
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
applyTheme(remembered('fork-theme'));
el('theme').addEventListener('click', () => {
  const dark =
    document.documentElement.dataset.theme === 'dark' ||
    (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
  const next = dark ? 'light' : 'dark';
  applyTheme(next);
  remember('fork-theme', next);
});

// Tabs: Play and Watch it learn; the watch tab loads its engines only when opened.
let watchStarted = false;
function selectTab(name) {
  for (const tab of document.querySelectorAll('[role="tab"]')) {
    const on = tab.dataset.tab === name;
    tab.setAttribute('aria-selected', String(on));
    el(`panel-${tab.dataset.tab}`).hidden = !on;
  }
  if (name === 'watch' && !watchStarted && manifest) {
    watchStarted = true;
    startWatchTab(manifest);
  }
  if (name === 'play') ground.redrawAll();
}
for (const tab of document.querySelectorAll('[role="tab"]')) {
  tab.addEventListener('click', () => selectTab(tab.dataset.tab));
}

for (const level of Levels) {
  const option = document.createElement('option');
  option.value = String(level.nodes);
  option.textContent = `${level.name}: ${countText(level.nodes)} positions per move`;
  levelChoice.append(option);
}
const savedLevel = remembered('fork-level');
levelChoice.value = Levels.some((l) => String(l.nodes) === savedLevel) ? savedLevel : String(DefaultLevel);
levelChoice.addEventListener('change', () => remember('fork-level', levelChoice.value));

el('new-game').addEventListener('click', newGame);

let manifest = null;
try {
  manifest = await loadNetworks();
  net = manifest.networks.find((n) => n.id === manifest.default);
  if (!net) throw new Error(`no default network ${manifest.default}`);
  el('playing-net').textContent = net.name;
  engine = new EngineClient(net.id);
  newGame();
} catch (err) {
  statusLine.textContent = `The page could not start: ${err.message}`;
}
