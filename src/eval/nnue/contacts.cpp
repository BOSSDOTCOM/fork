// SPDX-License-Identifier: GPL-3.0-or-later

// contacts: S512cl's contact and pawn-link inputs (see contacts.hpp).
#include "eval/nnue/contacts.hpp"

#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <vector>

#include "core/bitboard.hpp"
#include "eval/nnue/net_shape.hpp"

namespace forkeng {

namespace {

constexpr int Kinds = 5;                           // pawn .. queen; kings take no part
constexpr int Classes = 2 * Kinds;                 // side x 5 + kind, side 0 the perspective's own
constexpr int KindValue[Kinds] = {1, 2, 2, 3, 4};  // pawn < knight = bishop < rook < queen

// The squares a class's kind attacks from `s` on occupancy `occ` (own pawns
// attack up the frame, enemy pawns down).
Bitboard reach(int cls, Square s, Bitboard occ) {
  switch (cls % Kinds) {
    case 0:
      return pawn_attacks(cls < Kinds ? White : Black, s);
    case 1:
      return knight_attacks(s);
    case 2:
      return bishop_attacks(s, occ);
    case 3:
      return rook_attacks(s, occ);
    default:
      return bishop_attacks(s, occ) | rook_attacks(s, occ);
  }
}

bool on_line(Square a, Square b) { return (a & 7) == (b & 7) || (a >> 3) == (b >> 3); }
bool on_diagonal(Square a, Square b) { return std::abs((a & 7) - (b & 7)) == std::abs((a >> 3) - (b >> 3)); }

// Whether (att, a, b, vic) can be active in some position, b in att's
// empty-board reach from a: pawns only on ranks 2-7; not both pawns; of one
// kind only the lower attacker square; and none of the mutual pairs whose
// dearer attacker's input is never kept (a queen with a rook on a line or a
// bishop on a diagonal; a bishop or queen with a pawn attacking it back).
bool possible(int att, Square a, Square b, int vic) {
  const int ka = att % Kinds, kv = vic % Kinds;
  const auto middle = [](Square s) { return s >= 8 && s < 56; };
  if ((ka == 0 && !middle(a)) || (kv == 0 && !middle(b)) || (ka == 0 && kv == 0)) return false;
  if (ka == kv && a > b) return false;
  if (ka == 4 && ((kv == 3 && on_line(a, b)) || (kv == 2 && on_diagonal(a, b)))) return false;
  if ((ka == 2 || ka == 4) && kv == 0 && (reach(vic, b, 0) & bb(a))) return false;
  return true;
}

struct ContactTable {
  std::vector<std::int32_t> contact;  // [att][a][b][vic], -1 when impossible
  int contacts = 0;

  ContactTable() : contact(std::size_t{Classes} * 64 * 64 * Classes, -1) {
    for (int att = 0; att < Classes; ++att)
      for (Square a = 0; a < 64; ++a)
        for (Bitboard r = reach(att, a, 0); r;) {
          const Square b = pop_lsb(r);
          for (int vic = 0; vic < Classes; ++vic)
            if (possible(att, a, b, vic)) contact[slot(att, a, b, vic)] = contacts++;
        }
  }
  static std::size_t slot(int att, Square a, Square b, int vic) {
    return ((std::size_t{static_cast<unsigned>(att)} * 64 + a) * 64 + b) * Classes + vic;
  }
};

const ContactTable& contact_table() {
  static const ContactTable t;
  return t;
}

// The link space, built at compile time: each pair of pawn slots' input in
// both orders (-1 when the pair is not a link; int16, 1,488 links, half the
// cache of int32) and each square's partner squares (its own file and the
// neighbouring ones, itself excluded).
struct LinkTables {
  std::int16_t input[96 * 96] = {};
  Bitboard partners[64] = {};
  int size = 0;
};

constexpr LinkTables make_link_tables() {
  const auto partnered = [](int a, int b) { return a != b && (a & 7) - (b & 7) <= 1 && (b & 7) - (a & 7) <= 1; };
  LinkTables t;
  for (int i = 0; i < 96 * 96; ++i) t.input[i] = -1;
  for (int i = 0; i < 96; ++i)
    for (int j = i + 1; j < 96; ++j)
      if (partnered(i % 48 + 8, j % 48 + 8)) {
        t.input[i * 96 + j] = t.input[j * 96 + i] = static_cast<std::int16_t>(t.size);
        ++t.size;
      }
  for (int a = 0; a < 64; ++a)
    for (int b = 0; b < 64; ++b)
      if (partnered(a, b)) t.partners[a] |= Bitboard{1} << b;
  return t;
}

constexpr LinkTables Links = make_link_tables();
static_assert(Links.size == NetLinkInputs, "the link space's size is net_shape.hpp's");

}  // namespace

int contact_inputs(const Position& pos, Color perspective, int flip, std::int32_t* out) {
  const ContactTable& t = contact_table();
  const Bitboard occ = pos.pieces();
  const Bitboard targets = occ & ~pos.pieces(King);
  const auto frame = [&](Square s) {
    return static_cast<Square>((perspective == White ? s : s ^ 56) ^ flip);
  };
  // A piece's class and its attacks in board terms (a pawn by its own colour).
  const auto attacks = [&](Piece p, Square s) {
    const int cls = (side_of(p) == White ? 0 : Kinds) + kind_of(p);  // board colour, not perspective
    return reach(cls, s, occ);
  };
  int n = 0;
  for (Bitboard pieces = targets; pieces;) {
    const Square s = pop_lsb(pieces);
    const Piece x = pos.piece_at(s);
    const int kx = kind_of(x);
    const int own_x = side_of(x) != perspective;
    for (Bitboard hit = attacks(x, s) & targets; hit;) {
      const Square v = pop_lsb(hit);
      const Piece y = pos.piece_at(v);
      const int ky = kind_of(y);
      if (kx == Pawn && ky == Pawn) continue;
      // Of two pieces attacking each other, only the cheaper attacker's input
      // (of one kind, the one whose attacker stands on the lower frame square).
      if ((attacks(y, v) & bb(s)) && (KindValue[ky] < KindValue[kx] || (ky == kx && frame(v) < frame(s))))
        continue;
      const std::int32_t i = t.contact[ContactTable::slot(own_x * Kinds + kx, frame(s), frame(v),
                                                    (side_of(y) != perspective) * Kinds + ky)];
      assert(i >= 0 && "an active contact outside the index space");
      out[n++] = i;
    }
  }
  std::int32_t links[LinkMaxActive];
  const int m = link_inputs(pos.pieces(White, Pawn), pos.pieces(Black, Pawn), perspective, flip, links);
  for (int i = 0; i < m; ++i) out[n++] = NetContactInputs + links[i];
  return n;
}

int link_inputs(Bitboard white_pawns, Bitboard black_pawns, Color perspective, int flip, std::int32_t* out) {
  int slots[16];
  int pawns = 0;
  for (const Color c : {White, Black})
    for (Bitboard b = c == White ? white_pawns : black_pawns; b;) {
      const Square s = pop_lsb(b);
      const int seen = (perspective == White ? s : s ^ 56) ^ flip;
      slots[pawns++] = (c != perspective) * 48 + seen - 8;
    }
  std::sort(slots, slots + pawns);
  // Pairs in slot order, the order the index space enumerates them, so the
  // inputs come out ascending.
  int n = 0;
  for (int i = 0; i < pawns; ++i)
    for (int j = i + 1; j < pawns; ++j) {
      const std::int32_t l = Links.input[slots[i] * 96 + slots[j]];
      if (l >= 0) out[n++] = l;
    }
  return n;
}

int link_changes(const Bitboard (&before)[2], const Bitboard (&after)[2], Color perspective, int flip,
                 std::int32_t* removed, int& removed_count, std::int32_t* added, int& added_count) {
  // A pawn's slot is slot_base[its side] + (its square ^ key).
  const int key = (perspective == White ? 0 : 56) ^ flip;
  const int slot_base[2] = {perspective == White ? -8 : 40, perspective == White ? 40 : -8};
  // The links a set of pawns loses (or gains) with `changed`: every pair of a
  // changed pawn and a pawn of the pool on its own or a neighbouring file, each
  // pair once (a changed pawn leaves the pool once its pairs are listed). One
  // loop over both sides' partners, a partner's side read from the pool's
  // black pawns; the table holds both orders of a pair.
  const auto pairs = [&](const Bitboard (&pool_in)[2], const Bitboard (&changed)[2], std::int32_t* out) {
    const Bitboard black = pool_in[Black];
    Bitboard pool = pool_in[White] | black;
    int n = 0;
    for (const Color c : {White, Black})
      for (Bitboard g = changed[c]; g;) {
        const Square s = pop_lsb(g);
        pool &= ~bb(s);
        const std::int16_t* row = Links.input + (slot_base[c] + (s ^ key)) * 96;
        for (Bitboard p = pool & Links.partners[s]; p;) {
          const Square q = pop_lsb(p);
          const std::int16_t l = row[slot_base[(black >> q) & 1] + (q ^ key)];
          assert(l >= 0 && "a pawn pair outside the link space");
          out[n++] = l;
        }
      }
    return n;
  };
  const Bitboard gone[2] = {before[White] & ~after[White], before[Black] & ~after[Black]};
  const Bitboard came[2] = {after[White] & ~before[White], after[Black] & ~before[Black]};
  removed_count = pairs(before, gone, removed);
  added_count = pairs(after, came, added);
  return removed_count + added_count;
}

int contact_table_size() { return contact_table().contacts; }
int link_table_size() { return Links.size; }

}  // namespace forkeng
