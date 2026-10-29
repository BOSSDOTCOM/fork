// SPDX-License-Identifier: GPL-3.0-or-later

// endgame_tables: Syzygy endgame tablebases through the vendored Fathom
// library (DESIGN.md §5.2, deliverable 7; third_party/fathom, MIT; KB
// tools.md §6).
//
// Purpose: load the tables a SyzygyPath names, answer win/draw/loss for
// positions in the search, and rank the root moves by the distance-to-zero
// tables under the fifty-move rule.
// Invariants:
// - One set of tables per process (Fathom keeps global state);
//   load_endgame_tables runs only while no search is running.
// - endgame_table_pieces() is the largest piece count among the tables found
//   (0: none), never a hard-coded limit; positions with more pieces are never
//   probed. A missing table or a failed probe is "no answer", never an error.
// - probe_table_wdl answers only with no castling rights and a zero halfmove
//   clock: the win/draw/loss tables do not account for a running fifty-move
//   count (Fathom refuses those probes too).
// - The win/draw/loss probe is safe from any thread (Fathom built without
//   TB_NO_THREADS); the root ranking runs once per search, on the search
//   thread.
#pragma once

#include <optional>
#include <string>

#include "core/position.hpp"

namespace forkeng {

// The result for the side to move. Cursed wins and blessed losses are wins
// and losses that the fifty-move rule turns into draws.
enum class TableWdl : int { Loss = -2, BlessedLoss = -1, Draw = 0, CursedWin = 1, Win = 2 };

// Loads the tables in `path` (directories separated by ':' on Linux and ';'
// on Windows); an empty path unloads them. Returns a one-line report.
std::string load_endgame_tables(const std::string& path);

// The largest number of pieces (kings included) the loaded tables cover.
int endgame_table_pieces();

// The win/draw/loss result of `pos`, or nothing if the tables cannot answer.
std::optional<TableWdl> probe_table_wdl(const Position& pos);

// At the root: the legal moves that keep the best result reachable under the
// fifty-move rule, in the tables' order of preference, into `keep`. Uses the
// distance-to-zero tables, or the win/draw/loss tables if those are missing.
// Returns false (and leaves `keep` empty) if the root is not in the tables or
// a probe failed. `repeated`: the position has occurred before since the last
// capture or pawn move (the ranking then avoids walking into a repetition).
bool rank_root_by_tables(const Position& pos, bool repeated, MoveList& keep);

}  // namespace forkeng
