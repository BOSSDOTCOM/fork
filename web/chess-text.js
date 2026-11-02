// SPDX-License-Identifier: GPL-3.0-or-later
// Text helpers for Fork's page (DESIGN.md §5.5), free of chess rules: the
// engine is the only rules source (moves in standard notation come from it,
// src/web/web_engine.hpp fork_web_san). These read its reports and turn
// scores into what the page shows. Tested under Node.js (web/test/).

// One engine report, an iteration's line ("depth 9 score cp 31 nodes 48211
// pv e2e4 e7e5") or a search's result ("bestmove e2e4 score mate 3 depth 12
// nodes 200113 pv ..."), as {best, depth, score: {mate, value}, nodes, pv}.
// Scores are from the side to move's view, as the engine gives them.
export function parseReport(text) {
  const words = String(text).trim().split(/\s+/);
  const out = { best: null, depth: 0, score: null, nodes: 0, pv: [] };
  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    if (w === 'bestmove') out.best = words[++i] === 'none' ? null : words[i];
    else if (w === 'depth') out.depth = Number(words[++i]);
    else if (w === 'nodes') out.nodes = Number(words[++i]);
    else if (w === 'score') {
      const kind = words[++i];
      out.score = { mate: kind === 'mate', value: Number(words[++i]) };
    } else if (w === 'pv') {
      out.pv = words.slice(i + 1);
      break;
    }
  }
  return out;
}

// White's share of the expected result for a score, shown by the evaluation
// bar: sigmoid(cp / scale) with the playing network's output scale S
// (docs/nets.md), from White's view; a mate pins the bar to its end.
export function whiteShare(score, whiteToMove, scale) {
  if (!score) return 0.5;
  const sign = whiteToMove ? 1 : -1;
  if (score.mate) return sign * score.value > 0 ? 1 : 0;
  return 1 / (1 + Math.exp(-(sign * score.value) / scale));
}

// The score as text from White's view: "+0.31" in pawns, "M3" when White
// mates in 3, "-M2" when Black does.
export function scoreText(score, whiteToMove) {
  if (!score) return '';
  const v = whiteToMove ? score.value : -score.value;
  if (score.mate) return v > 0 ? `M${v}` : `-M${-v}`;
  const pawns = (v / 100).toFixed(2);
  return v > 0 ? `+${pawns}` : pawns;
}

// Moves in standard notation with move numbers, starting from a FEN's move
// number and side to move: "1. e4 e5 2. Nf3", or "12... Qd7 13. Re1".
export function numberedLine(fen, sans) {
  const fields = String(fen).split(' ');
  let number = Number(fields[5]) || 1;
  let white = fields[1] !== 'b';
  const parts = [];
  sans.forEach((san, i) => {
    if (white) parts.push(`${number}. ${san}`);
    else parts.push(i === 0 ? `${number}... ${san}` : san);
    if (!white) number++;
    white = !white;
  });
  return parts.join(' ');
}

// 200000 -> "200,000".
export function countText(n) {
  return Number(n).toLocaleString('en-US');
}

// The side to move of a FEN ("startpos" is White's).
export function turnOf(fen) {
  return String(fen).split(' ')[1] === 'b' ? 'black' : 'white';
}

// The message for a finished game, from the engine's status and the side to
// move in the final position; null while the game goes on.
export function endingText(status, turn) {
  switch (status) {
    case 'checkmate':
      return `Checkmate: ${turn === 'white' ? 'Black' : 'White'} wins.`;
    case 'stalemate':
      return 'Draw by stalemate.';
    case 'fifty-move':
      return 'Draw by the fifty-move rule.';
    case 'repetition':
      return 'Draw by threefold repetition.';
    case 'insufficient':
      return 'Draw: neither side can checkmate.';
    default:
      return null;
  }
}

// Whether the last move in SAN gave check (its "+" or "#").
export function givesCheck(sans) {
  return sans.length > 0 && /[+#]$/.test(sans[sans.length - 1]);
}
