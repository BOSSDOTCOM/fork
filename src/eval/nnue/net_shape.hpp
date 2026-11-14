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
//   of pawns at most one rank apart (NetLinkRanks; owner, 2026-11-06), kept
//   incrementally in the main int16 sums (net_file.cpp's bound of 64 links),
//   S-512's output. 9 H512+PP (bake-off round 3's option a; owner,
//   2026-11-14): S512+PP with its 768 piece inputs copied per own-king region
//   (at most 4: the net file's 32-entry map of the mirrored own-king cell,
//   as H-512's), the 608 link inputs shared after all the region rows; a
//   perspective whose frame changes is refreshed lazily from that frame's
//   snapshot (accumulator.hpp, FeatureStack).
// - QA = 255, QB = 64 (bullet's quantization convention; ORIGINALITY.md).
#pragma once

#ifndef FORK_NET_ARCH
#define FORK_NET_ARCH 1
#endif

// The architectures that keep S512+PP's pawn links in the int16 sums.
#define FORK_NET_LINKS (FORK_NET_ARCH == 8 || FORK_NET_ARCH == 9)

// Move-delta rows (ideas.md 182; an A/B experiment, FORK_EXPERIMENT=MOVE_DELTA,
// off by default): a non-pawn piece's move applies one precomputed row, its
// row on the destination minus its row on the origin (net_file.hpp,
// step_rows). S512+PP only: with king regions the table would be four times
// larger.
#if defined(FORK_EXP_MOVE_DELTA)
#if FORK_NET_ARCH != 8
#error "FORK_EXPERIMENT=MOVE_DELTA is built for S512+PP (architecture 8) only"
#endif
#define FORK_MOVE_DELTA 1
#else
#define FORK_MOVE_DELTA 0
#endif

namespace forkeng {

inline constexpr int NetArchitecture = FORK_NET_ARCH;
static_assert(NetArchitecture >= 1 && NetArchitecture <= 9, "unknown network architecture");

inline constexpr int NetQa = 255;
inline constexpr int NetQb = 64;
inline constexpr int NetPieceSquares = 768;  // 2 colours x 6 piece types x 64 squares
inline constexpr int NetHidden = NetArchitecture == 1 ? 256 : 512;
inline constexpr bool NetMirrored = NetArchitecture != 1;
inline constexpr bool NetRegioned = (NetArchitecture >= 3 && NetArchitecture <= 5) || NetArchitecture == 9;
inline constexpr int NetMaxRegions = NetRegioned ? 4 : 1;
inline constexpr bool NetExposure = NetArchitecture == 5 || NetArchitecture == 6;
inline constexpr int NetExposureRows = 640;  // own/enemy x 5 non-king types x 64 squares
// S512cl's contact and link inputs (contacts.hpp builds their index space;
// tests/test_nnue.cpp checks these sizes against it).
inline constexpr bool NetContacts = NetArchitecture == 7;
inline constexpr int NetContactInputs = 50416;
// The links' rank limit: two pawns on the same or adjacent files form a link
// when their ranks are at most this far apart (S512cl: any, 7; S512+PP: 1,
// owner, 2026-11-06, its measured speed step, ideas.md 40; H512+PP's too).
inline constexpr int NetLinkRanks = FORK_NET_LINKS ? 1 : 7;
// Whether pawns on frame squares a and b (8 .. 55) form a link.
constexpr bool link_squares(int a, int b) {
  const int df = (a & 7) - (b & 7), dr = (a >> 3) - (b >> 3);
  return a != b && df <= 1 && df >= -1 && dr <= NetLinkRanks && dr >= -NetLinkRanks;
}
// The link space's size: pairs of pawn slots (side x 48 + frame square - 8),
// the lower first, whose squares form a link (1,488 at 7 ranks, 608 at 1).
constexpr int link_space() {
  int n = 0;
  for (int i = 0; i < 96; ++i)
    for (int j = i + 1; j < 96; ++j) n += link_squares(i % 48 + 8, j % 48 + 8);
  return n;
}
inline constexpr int NetLinkInputs = link_space();
// S512+PP's pawn-link inputs, right after the piece rows (H512+PP: after
// every region's piece rows).
inline constexpr bool NetLinks = FORK_NET_LINKS;
inline constexpr int NetMaxInputs = NetPieceSquares * NetMaxRegions + (NetExposure ? NetExposureRows : 0) +
                                    (NetContacts ? NetContactInputs + NetLinkInputs : 0) +
                                    (NetLinks ? NetLinkInputs : 0);
// Outputs (or layer stacks) picked by the game phase through a 25-entry table.
inline constexpr bool NetPhasePicked = (NetArchitecture >= 2 && NetArchitecture <= 4) ||
                                       NetArchitecture == 6 || NetArchitecture == 7 || NetArchitecture == 8 ||
                                       NetArchitecture == 9;
inline constexpr int NetBuckets = NetPhasePicked ? 8 : 1;
inline constexpr int NetSideLanes = NetArchitecture == 5 ? 3 : 0;
// AF-S's body.
inline constexpr int NetL1 = 16, NetL2 = 32;

}  // namespace forkeng
