// SPDX-License-Identifier: GPL-3.0-or-later
// The page's rule-free helpers and its data (DESIGN.md §5.5), under Node.js:
//   node --test web/test/page.test.js
// The engine-side notation and reports are tested natively (tests/test_web.cpp).
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { test } from 'node:test';
import {
  countText,
  endingText,
  lastMoveChecks,
  numberedLine,
  parseReport,
  scoreText,
  turnOf,
  whiteShare,
} from '../chess-text.js';
import { SuitePositions } from '../suite-positions.js';

const root = new URL('../../', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');

test('reports: an iteration line and a search result', () => {
  assert.deepEqual(parseReport('depth 9 score cp -31 nodes 48211 pv e2e4 e7e5'), {
    best: null,
    depth: 9,
    score: { mate: false, value: -31 },
    nodes: 48211,
    pv: ['e2e4', 'e7e5'],
  });
  const r = parseReport('bestmove a1a8 score mate 1 depth 12 nodes 20013 pv a1a8');
  assert.equal(r.best, 'a1a8');
  assert.deepEqual(r.score, { mate: true, value: 1 });
  assert.deepEqual(r.pv, ['a1a8']);
  assert.equal(parseReport('bestmove none').best, null);
});

test("the bar: White's share, sigmoid(cp / S) from White's view, mates at the ends", () => {
  assert.equal(whiteShare(null, true, 92), 0.5);
  assert.equal(whiteShare({ mate: false, value: 0 }, true, 92), 0.5);
  assert.equal(whiteShare({ mate: false, value: 92 }, true, 92), 1 / (1 + Math.exp(-1)));
  // Black to move and better: White's share is below a half.
  assert.equal(whiteShare({ mate: false, value: 92 }, false, 92), 1 / (1 + Math.exp(1)));
  assert.equal(whiteShare({ mate: true, value: 3 }, true, 92), 1);
  assert.equal(whiteShare({ mate: true, value: 3 }, false, 92), 0);
  assert.equal(whiteShare({ mate: true, value: -2 }, false, 92), 1);
});

test("scores as text from White's view", () => {
  assert.equal(scoreText({ mate: false, value: 31 }, true), '+0.31');
  assert.equal(scoreText({ mate: false, value: 31 }, false), '-0.31');
  assert.equal(scoreText({ mate: false, value: 0 }, true), '0.00');
  assert.equal(scoreText({ mate: true, value: 3 }, true), 'M3');
  assert.equal(scoreText({ mate: true, value: 3 }, false), '-M3');
  assert.equal(scoreText(null, true), '');
});

test('numbered lines, sides to move and endings', () => {
  assert.equal(numberedLine('startpos', ['e4', 'e5', 'Nf3']), '1. e4 e5 2. Nf3');
  assert.equal(numberedLine('r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 3 12', ['O-O', 'Rf1']), '12... O-O 13. Rf1');
  assert.equal(numberedLine('startpos', []), '');
  assert.equal(turnOf('startpos'), 'white');
  assert.equal(turnOf('8/8/8/8/8/8/8/K6k b - - 0 1'), 'black');
  assert.equal(endingText('checkmate', 'black'), 'Checkmate: White wins.');
  assert.equal(endingText('repetition', 'white'), 'Draw by threefold repetition.');
  assert.equal(endingText('playing', 'white'), null);
  assert.equal(lastMoveChecks(['e4', 'Qh4#']), true);
  assert.equal(lastMoveChecks(['Bb5+', 'c6']), false);
  assert.equal(lastMoveChecks([]), false);
  assert.equal(countText(200000), '200,000');
});

test("the fixed positions are tests/suite.hpp's, character for character", () => {
  const suite = read('tests/suite.hpp');
  assert.equal(SuitePositions.length, 6);
  for (const p of SuitePositions) assert.ok(suite.includes(`"${p.fen}"`), p.name);
});

test('nets.json: every network can be built and its record is in the docs', () => {
  const manifest = JSON.parse(read('web/nets.json'));
  const nets = read('docs/nets.md');
  const log = read('docs/history/phase-4/sprt-log.md');
  const ids = manifest.networks.map((n) => n.id);
  assert.ok(ids.includes(manifest.default));
  assert.equal(new Set(ids).size, ids.length);
  for (const n of manifest.networks) {
    assert.match(n.id, /^[a-z0-9]+$/);
    assert.ok(n.scale > 0, n.id);
    if (n.id === 'bootstrap') {
      assert.ok(existsSync(new URL('tests/bench.ref', root)));
      continue;
    }
    assert.ok(existsSync(new URL(`nets/${n.id}.fnet`, root)), n.id);
    assert.ok(existsSync(new URL(`tests/bench-${n.id}.ref`, root)), n.id);
    assert.ok(existsSync(new URL(`tests/nnue/${n.id}.parity`, root)), n.id);
    assert.ok(nets.includes(`S = ${n.scale}`), `${n.id}: S = ${n.scale}`);
    assert.ok(nets.includes(n.validation_loss), `${n.id}: ${n.validation_loss}`);
    for (const number of n.data.match(/\d[\d,]+\d/g) || []) assert.ok(nets.includes(number), `${n.id}: ${number}`);
    // The SPRT: its Elo line and run as the log records them.
    assert.ok(log.includes(`Elo: ${n.sprt.elo.replace(/^\+/, '')},`), `${n.id}: ${n.sprt.elo}`);
    assert.ok(log.includes(n.sprt.run), `${n.id}: run ${n.sprt.run}`);
    assert.ok(nets.includes(n.promoted), `${n.id}: ${n.promoted}`);
  }
});
