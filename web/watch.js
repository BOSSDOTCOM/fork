// SPDX-License-Identifier: GPL-3.0-or-later
// The "Watch it learn" tab (DESIGN.md §5.5): two of Fork's promoted
// evaluators play each other live, each in its own Web Worker at a fixed
// node count per move; the networks' record from nets.json; and their static
// evaluations of fixed positions side by side.
import { Chessground } from './vendor/chessground/chessground.min.js';
import { countText, endingText, lastMoveChecks, numberedLine, scoreText, turnOf } from './chess-text.js';
import { EngineClient } from './engine-client.js';
import { setBar } from './eval-bar.js';
import { SuitePositions } from './suite-positions.js';

// Nodes per move for the watched games (page settings).
const WatchNodes = [10000, 50000, 200000];
const PauseMs = 400; // between moves, so a fast game can be followed

const el = (id) => document.getElementById(id);

// The bench positions (tests/datagen_openings.epd, copied to the page as
// openings.epd when it is built): Fork's own openings set for these games.
async function loadOpenings() {
  try {
    const response = await fetch('./openings.epd');
    if (!response.ok) return [];
    const text = await response.text();
    return text
      .split('\n')
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith('#'));
  } catch {
    return [];
  }
}

function eloOf(sprt) {
  return sprt ? Number.parseFloat(sprt.elo) : 0;
}

function sizeText(bytes) {
  return bytes ? `${(bytes / 1048576).toFixed(1)} MB` : '';
}

function fillNetworkTable(manifest) {
  const body = el('nets-body');
  body.textContent = '';
  let chain = 0;
  for (const n of manifest.networks) {
    chain += eloOf(n.sprt);
    const row = document.createElement('tr');
    const cells = [
      n.name,
      n.promoted || '',
      n.sprt ? `${n.sprt.elo} vs ${n.sprt.against}` : 'the start',
      n.sprt ? `+${chain.toFixed(0)}` : '0',
      n.validation_loss || '',
      n.data || '',
      n.architecture,
      sizeText(n.module_bytes),
    ];
    for (const text of cells) {
      const cell = document.createElement('td');
      cell.textContent = text;
      row.append(cell);
    }
    body.append(row);
  }
}

export function startWatchTab(manifest) {
  const nets = manifest.networks;
  const byId = (id) => nets.find((n) => n.id === id);
  const whiteChoice = el('white-net');
  const blackChoice = el('black-net');
  const nodesChoice = el('watch-nodes');
  const openingChoice = el('watch-opening');
  const statusLine = el('watch-status');
  for (const select of [whiteChoice, blackChoice]) {
    for (const n of nets) {
      const option = document.createElement('option');
      option.value = n.id;
      option.textContent = n.promoted ? `${n.name} (${n.promoted})` : n.name;
      select.append(option);
    }
  }
  whiteChoice.value = nets[nets.length - 1].id;
  blackChoice.value = nets[Math.max(0, nets.length - 2)].id;
  for (const nodes of WatchNodes) {
    const option = document.createElement('option');
    option.value = String(nodes);
    option.textContent = `${countText(nodes)} positions per move`;
    nodesChoice.append(option);
  }
  nodesChoice.value = String(WatchNodes[1]);
  fillNetworkTable(manifest);

  const ground = Chessground(el('watch-board'), {
    coordinates: true,
    viewOnly: true,
    drawable: { enabled: false },
    animation: { enabled: true, duration: 150 },
  });
  const openings = loadOpenings();
  let current = null; // the running game: {stopped, engines}

  function stopGame() {
    if (!current) return;
    current.stopped = true;
    for (const engine of Object.values(current.engines)) engine.stop();
    current = null;
  }

  function showSearch(report, rootFen, mover, side) {
    if (!report || !report.score) return;
    const whiteToMove = turnOf(rootFen) === 'white';
    setBar(el('watch-bar'), el('watch-bar-score'), report.score, whiteToMove, mover.scale, 'white');
    el('watch-info').textContent =
      `${mover.name} (${side === 'white' ? 'White' : 'Black'}): depth ${report.depth}, ` +
      `${scoreText(report.score, whiteToMove)}, ${countText(report.nodes)} positions. ` +
      numberedLine(rootFen, report.pvSan || []);
  }

  function showPosition(state, startFen) {
    const moves = state.sans;
    ground.set({ fen: state.fen.split(' ')[0], turnColor: turnOf(state.fen), check: lastMoveChecks(moves) });
    el('watch-moves').textContent = numberedLine(startFen, moves);
  }

  async function play() {
    stopGame();
    const white = byId(whiteChoice.value);
    const black = byId(blackChoice.value);
    const nodes = Number(nodesChoice.value);
    const engines = { white: new EngineClient(white.id), black: new EngineClient(black.id) };
    const game = { stopped: false, engines };
    current = game;
    const list = await openings;
    let fen = 'startpos';
    if (openingChoice.value === 'bench' && list.length) fen = list[Math.floor(Math.random() * list.length)];
    const moves = [];
    el('watch-moves').textContent = '';
    el('watch-info').textContent = '';
    setBar(el('watch-bar'), el('watch-bar-score'), null, true, white.scale, 'white');
    statusLine.textContent = `${white.name} (White) against ${black.name} (Black): starting the engines…`;
    try {
      let state = await engines.white.ask('new', { fen, moves });
      await engines.black.ask('new', { fen, moves });
      const startFen = state.fen;
      showPosition(state, startFen);
      while (!game.stopped && state.status === 'playing') {
        const side = turnOf(state.fen);
        const mover = side === 'white' ? white : black;
        statusLine.textContent = `${mover.name} is thinking…`;
        const rootFen = state.fen;
        state = await engines[side].ask('play', { fen, moves, nodes }, (p) => {
          if (!game.stopped) showSearch(p, rootFen, mover, side);
        });
        if (game.stopped) return;
        moves.push(state.move);
        showSearch(state.report, rootFen, mover, side);
        showPosition(state, startFen);
        await new Promise((resolve) => setTimeout(resolve, PauseMs));
      }
      if (!game.stopped) statusLine.textContent = endingText(state.status, turnOf(state.fen));
    } catch (err) {
      if (!game.stopped) statusLine.textContent = `Engine error: ${err.message}`;
    } finally {
      if (current === game) stopGame();
    }
  }

  async function compare() {
    const button = el('compare');
    button.disabled = true;
    const head = el('compare-head');
    const body = el('compare-body');
    head.textContent = '';
    body.textContent = '';
    const headRow = document.createElement('tr');
    for (const text of ['Position', ...nets.map((n) => n.name)]) {
      const th = document.createElement('th');
      th.textContent = text;
      headRow.append(th);
    }
    head.append(headRow);
    const cells = SuitePositions.map((p) => {
      const row = document.createElement('tr');
      const name = document.createElement('td');
      name.textContent = p.name;
      row.append(name);
      body.append(row);
      return nets.map(() => {
        const cell = document.createElement('td');
        cell.textContent = '…';
        row.append(cell);
        return cell;
      });
    });
    const fens = SuitePositions.map((p) => p.fen);
    for (const [j, n] of nets.entries()) {
      const engine = new EngineClient(n.id);
      try {
        const reply = await engine.ask('eval', { fens });
        reply.evals.forEach((v, i) => {
          const whiteToMove = turnOf(fens[i]) === 'white';
          cells[i][j].textContent = v === null ? '?' : scoreText({ mate: false, value: v }, whiteToMove);
        });
      } catch (err) {
        for (const row of cells) row[j].textContent = '!';
        el('compare-note').textContent = `${n.name}: ${err.message}`;
      } finally {
        engine.stop();
      }
    }
    button.disabled = false;
  }

  el('watch-start').addEventListener('click', play);
  el('watch-stop').addEventListener('click', () => {
    stopGame();
    statusLine.textContent = 'Stopped.';
  });
  el('compare').addEventListener('click', compare);
}
