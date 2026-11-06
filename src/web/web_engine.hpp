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

// The moves of `line` (UCI, separated by spaces) in standard algebraic
// notation, played from `fen` ("startpos" or a FEN) after `moves`, separated
// by spaces; as far as the line is legal (an illegal or malformed move ends
// it). Works on a position of its own, so it may be called from the
// iteration report during a search; the text is valid until its next call.
const char* fork_web_san(const char* fen, const char* moves, const char* line);

// The static evaluation of the current position (no search), centipawns
// from the side to move's view.
int fork_web_evaluate();

// Searches the current position until `nodes` nodes (at least 1) and returns
// "bestmove <move> score cp <n>|mate <n> depth <d> nodes <n> pv <moves...>",
// the score from the side to move's view as in UCI, or "bestmove none" when
// the game is over. Each finished iteration (exact score, not an aspiration
// fail) is reported while the search runs as
// "depth <d> score cp <n>|mate <n> nodes <n> pv <moves...>": to the page's
// JavaScript under Emscripten (the module's onIteration function, if set),
// and to the hook below in every build.
const char* fork_web_search(double nodes);

// Receives each iteration's line during fork_web_search; the text is valid
// only during the call. nullptr (the start) reports nothing.
typedef void (*fork_web_iteration_hook)(const char* line);
void fork_web_set_iteration_hook(fork_web_iteration_hook hook);

// Clears the hash table and the move-ordering history.
void fork_web_new_game();

}  // extern "C"
