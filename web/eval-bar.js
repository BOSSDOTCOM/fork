// SPDX-License-Identifier: GPL-3.0-or-later
// The evaluation bar beside a board (DESIGN.md §5.5): White's share of the
// expected result for the latest score (chess-text.js whiteShare), drawn from
// White's side of the board, with the score as text.
import { scoreText, whiteShare } from './chess-text.js';

// `bar` holds a `.white` child; `label` shows the score. A null score
// centres the bar. `orientation` is the side at the bottom of the board.
export function setBar(bar, label, score, whiteToMove, scale, orientation) {
  const share = whiteShare(score, whiteToMove, scale);
  bar.querySelector('.white').style.height = `${(share * 100).toFixed(1)}%`;
  bar.classList.toggle('flipped', orientation === 'black');
  bar.setAttribute('aria-valuenow', String(Math.round(share * 100)));
  label.textContent = scoreText(score, whiteToMove);
}
