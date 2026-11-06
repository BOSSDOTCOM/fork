// SPDX-License-Identifier: GPL-3.0-or-later

// net_shape: the network shape this build's inference is compiled for
// (DESIGN.md §5.3 for B0, §5.4 for the bake-off entries), fixed at build
// time: CMake reads the architecture id from the embedded network's header
// and defines FORK_NET_ARCH (1 when absent, B0).
//
// Purpose: the compile-time constants every NNUE module sizes its tables by
// and branches on, so one build carries exactly one network shape and no
// runtime dispatch.
// Invariants:
// - 1 B0: 768 inputs per perspective, 256 hidden, clipped ReLU, one output.
//   2 S-512: 768 inputs mirrored left-right when the perspective's own king
//   is on files a-d, 512 hidden, squared clipped ReLU, 8 outputs picked by
//   the game phase. 3 H-512: S-512 with the inputs copied per king region
//   (at most 4). 4 AF-S: H-512's inputs; the two halves of each
//   perspective's clipped values multiplied, then 16 -> 32 -> 1 in 8 phase
//   stacks. 5 XGR-512: 4 king regions, 640 exposure inputs, 3 side lanes per
//   input (a gate and two linear lanes), two outputs blended by the gate.
//   6 S512+X: S-512 plus XGR's 640 exposure inputs (owner, 2026-11-02: XGR's
//   parts as add-ons to S512r2), S-512's output. 7 S512cl: S-512 plus Fork's
//   contact and pawn-link inputs (contacts.hpp; ideas.md 41, owner,
//   2026-11-05; no exposure plane), S-512's output. 8 S512+PP: S-512 plus
//   the pawn-link inputs only (owner, 2026-11-05; idea 40's first L1 step),
//   kept incrementally in the main int16 sums (net_file.hpp's bound of 96
//   links), S-512's output.
// - QA = 255, QB = 64 (bullet's quantization convention; ORIGINALITY.md).
#pragma once

#ifndef FORK_NET_ARCH
#define FORK_NET_ARCH 1
#endif

namespace forkeng {

inline constexpr int NetArchitecture = FORK_NET_ARCH;
static_assert(NetArchitecture >= 1 && NetArchitecture <= 8, "unknown network architecture");

inline constexpr int NetQa = 255;
inline constexpr int NetQb = 64;
inline constexpr int NetPieceSquares = 768;  // 2 colours x 6 piece types x 64 squares
inline constexpr int NetHidden = NetArchitecture == 1 ? 256 : 512;
inline constexpr bool NetMirrored = NetArchitecture != 1;
inline constexpr bool NetRegioned = NetArchitecture >= 3 && NetArchitecture <= 5;
inline constexpr int NetMaxRegions = NetRegioned ? 4 : 1;
inline constexpr bool NetExposure = NetArchitecture == 5 || NetArchitecture == 6;
inline constexpr int NetExposureRows = 640;  // own/enemy x 5 non-king types x 64 squares
// S512cl's contact and link inputs (contacts.hpp builds their index space;
// tests/test_nnue.cpp checks these sizes against it).
inline constexpr bool NetContacts = NetArchitecture == 7;
inline constexpr int NetContactInputs = 50416;
inline constexpr int NetLinkInputs = 1488;
// S512+PP's pawn-link inputs, right after the piece rows.
inline constexpr bool NetLinks = NetArchitecture == 8;
inline constexpr int NetMaxInputs = NetPieceSquares * NetMaxRegions + (NetExposure ? NetExposureRows : 0) +
                                    (NetContacts ? NetContactInputs + NetLinkInputs : 0) +
                                    (NetLinks ? NetLinkInputs : 0);
// Outputs (or layer stacks) picked by the game phase through a 25-entry table.
inline constexpr bool NetPhasePicked =
    (NetArchitecture >= 2 && NetArchitecture <= 4) || NetArchitecture == 6 || NetArchitecture == 7 ||
    NetArchitecture == 8;
inline constexpr int NetBuckets = NetPhasePicked ? 8 : 1;
inline constexpr int NetSideLanes = NetArchitecture == 5 ? 3 : 0;
// AF-S's body.
inline constexpr int NetL1 = 16, NetL2 = 32;

}  // namespace forkeng
