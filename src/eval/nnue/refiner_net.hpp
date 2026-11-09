// SPDX-License-Identifier: GPL-3.0-or-later

// refiner_net: the oracle's second network (ideas.md 59, step 2; experiment
// builds with FORK_REFINER_NET only, never released).
//
// Purpose: the refiner (S512+X, architecture 6; or item 7's scratch run, architecture 8), compiled in beside the base
// network (embedded_net(), here a plain S-512 net read into the same layout)
// and consulted by the search only where its gate fires
// (search/refiner_gate.hpp).
// Invariants:
// - Read and validated once, on first use (the Searcher's constructor forces
//   it, so no search allocates); an invalid embedded file stops the engine.
// - Its evaluations are in centipawns at its own output scale S, which its
//   file carries (S512+X's S = 89, matched to S512r2's when it was trained).
#pragma once

#include "eval/nnue/net_file.hpp"

namespace forkeng {

#ifdef FORK_REFINER
// Architecture 6: the prototype's pair (an S-512 base read as plain); 8: two S512+PP networks (idea 59 step 3's
// second opinion, S512ppr3 and item 7's scratch run), one layout for both.
static_assert(NetArchitecture == 6 || NetArchitecture == 8,
              "the oracle is compiled for the refiner's architecture: 6, or 8 for two S512+PP networks");
const NetFile& refiner_net();
#endif

}  // namespace forkeng
