// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

// Fork's entry points for the public web page (DESIGN.md §5.5): a
// single-threaded, synchronous interface for one Web Worker. Browsers give a
// GitHub Pages site no threads (no COOP/COEP headers), so the UCI session,
// which searches on a thread of its own, is not used there; each call below
// runs to completion on the caller's thread. Built with Emscripten for the
// page (target fork_web) and natively for its tests.
//
// Text results point into one buffer owned by the engine, valid until the
// next call. Moves are in UCI notation (e2e4, e7e8q, castling as the king's
// two-square move).
//
// Invariants:
// - fork_web_init must succeed before any other call.
// - A search is deterministic for a given position, node limit and engine
//   state; fork_web_new_game clears the hash table and the move-ordering
//   history, as `ucinewgame` does.

extern "C" {

// Allocates a hash table of `hash_mb` MB (cleared) and readies the engine at
// the start position. Returns 1, or 0 if the memory cannot be had.
int fork_web_init(int hash_mb);

// Sets the position: `fen` is a FEN or "startpos", `moves` the moves played
// from it, separated by spaces (may be empty). Returns 1, or 0 if the FEN is
// invalid or a move is illegal (the position is then left unchanged).
int fork_web_set_position(const char* fen, const char* moves);

// The current position as FEN.
const char* fork_web_fen();

// The legal moves of the current position, separated by spaces.
const char* fork_web_legal_moves();

// The game's state in the current position: "playing", "checkmate",
// "stalemate", "fifty-move", "repetition" (the third occurrence) or
// "insufficient" (neither side can mate). Checkmate and stalemate take
// precedence over the draws by rule.
const char* fork_web_status();

// Searches the current position until `nodes` nodes (at least 1) and returns
// "bestmove <move> score cp <n>|mate <n> depth <d> nodes <n> pv <moves...>",
// the score from the side to move's view as in UCI, or "bestmove none" when
// the game is over.
const char* fork_web_search(double nodes);

// Clears the hash table and the move-ordering history.
void fork_web_new_game();

}  // extern "C"
