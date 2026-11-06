// SPDX-License-Identifier: GPL-3.0-or-later

// contacts: S512cl's contact and pawn-link inputs (ideas.md idea 41;
// DESIGN.md §5.4, "S512cl"), Fork's own encoding from the KB's concepts.
//
// Purpose: a perspective's active contact inputs (a non-king piece attacking
// another, not both pawns; of two pieces attacking each other only the
// cheaper attacker's input, of one kind the lower attacker frame square's)
// and link inputs (two pawns, of either side, on the same or adjacent
// files), as row numbers after the piece rows.
// Invariants:
// - The index space is enumerated once, at first use, in the order
//   tools/nnue/contacts.py and tools/train build too: contacts by attacker
//   class (side x 5 + kind, side 0 the perspective's own), attacker frame
//   square, target frame square (ascending, over the attacker kind's reach on
//   an empty board) and victim class, possible combinations only; links by
//   the pair of pawn slots (side x 48 + frame square - 8), the lower first.
//   Its sizes are NetContactInputs and NetLinkInputs (net_shape.hpp;
//   tests/test_nnue.cpp checks them, and the lists against the reference).
// - A frame square is the piece inputs': vertically flipped for Black, files
//   flipped by `flip` (7 when that side's king is on files a-d, else 0).
// - Compiled into every build (the tests use it); only S512cl evaluates the
//   contacts, S512cl and S512+PP the links.
#pragma once

#include <cstdint>

#include "core/position.hpp"

namespace forkeng {

// The most inputs one perspective can have: 8 contacts for each of 30
// non-king pieces (8 rays or knight squares), and a link per pair of 16 pawns.
inline constexpr int ContactMaxActive = 30 * 8 + 16 * 15 / 2;

// The perspective's contact inputs (0 .. NetContactInputs - 1) followed by its
// link inputs (NetContactInputs .. + NetLinkInputs - 1), unsorted, written to
// `out` (room for ContactMaxActive); returns their count.
int contact_inputs(const Position& pos, Color perspective, int flip, std::int32_t* out);

// The most link inputs one perspective can have: a pair per two of 16 pawns.
inline constexpr int LinkMaxActive = 16 * 15 / 2;

// The perspective's link inputs (0 .. NetLinkInputs - 1, within the link
// block), ascending, from the two sides' pawns (S512+PP keeps them
// incrementally; contact_inputs appends the same list); returns their count.
int link_inputs(Bitboard white_pawns, Bitboard black_pawns, Color perspective, int flip, std::int32_t* out);

// The link inputs a move removes and adds, from each side's pawns before and
// after it: only the pairs of the pawns that left or arrived (a link between
// two unchanged pawns is in both lists, so it is in neither change). Each list
// has room for LinkMaxActive; unsorted. Returns the two counts' sum.
int link_changes(const Bitboard (&before)[2], const Bitboard (&after)[2], Color perspective, int flip,
                 std::int32_t* removed, int& removed_count, std::int32_t* added, int& added_count);

// The index space's sizes as built (tests).
int contact_table_size();
int link_table_size();

}  // namespace forkeng
