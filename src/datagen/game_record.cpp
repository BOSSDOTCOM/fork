// SPDX-License-Identifier: GPL-3.0-or-later

#include "datagen/game_record.hpp"

#include <algorithm>
#include <cstring>

#include "core/movegen.hpp"

namespace forkeng {

namespace {

constexpr int CastlingRookType = 6;

// The format's corner-rook rule for standard chess: the castling right each
// corner rook carries.
constexpr struct {
  Square square;
  Color color;
  int right;
  char fen;
} CornerRooks[] = {{7, White, WhiteOO, 'K'},
                   {0, White, WhiteOOO, 'Q'},
                   {63, Black, BlackOO, 'k'},
                   {56, Black, BlackOOO, 'q'}};

void put_u16(std::uint8_t* p, std::uint16_t v) {
  p[0] = static_cast<std::uint8_t>(v);
  p[1] = static_cast<std::uint8_t>(v >> 8);
}

std::uint16_t get_u16(const std::uint8_t* p) { return static_cast<std::uint16_t>(p[0] | (p[1] << 8)); }

int carried_right(Square s, Piece p, int rights) {
  for (const auto& c : CornerRooks)
    if (c.square == s && p == piece_of(c.color, Rook) && (rights & c.right)) return c.right;
  return 0;
}

}  // namespace

void encode_board(const Position& pos, GameResult result, std::uint8_t out[CompactBoardBytes]) {
  std::memset(out, 0, CompactBoardBytes);
  const Bitboard occupied = pos.pieces();
  for (int i = 0; i < 8; ++i) out[i] = static_cast<std::uint8_t>(occupied >> (8 * i));
  int k = 0;
  for (Bitboard b = occupied; b; ++k) {
    const Square s = pop_lsb(b);
    const Piece p = pos.piece_at(s);
    const int type = carried_right(s, p, pos.castling_rights()) ? CastlingRookType : kind_of(p);
    const int code = (side_of(p) << 3) | type;
    out[8 + k / 2] |= static_cast<std::uint8_t>(code << (4 * (k & 1)));
  }
  out[24] = static_cast<std::uint8_t>(pos.ep_target() | (pos.side_to_move() == Black ? 128 : 0));
  out[25] = static_cast<std::uint8_t>(std::min(pos.halfmove_clock(), 255));
  put_u16(out + 26, static_cast<std::uint16_t>(std::min(pos.fullmove_number(), 65535)));
  // bytes 28-29: the header score, left 0
  out[30] = static_cast<std::uint8_t>(result);
}

std::uint16_t encode_move(Move m) {
  int type = 0, promotion = 0;
  if (m.is_castle())
    type = 2;
  else if (m.is_en_passant())
    type = 1;
  else if (m.is_promotion()) {
    type = 3;
    promotion = m.promo_type() - Knight;
  }
  return static_cast<std::uint16_t>(m.from() | (m.to() << 6) | (promotion << 12) | (type << 14));
}

void GameWriter::begin(const Position& start) {
  bytes_.assign(CompactBoardBytes, 0);
  encode_board(start, GameResult::Draw, bytes_.data());
  positions_ = 0;
}

void GameWriter::add(Move m, int white_score) {
  std::uint8_t rec[MoveRecordBytes];
  put_u16(rec, encode_move(m));
  put_u16(rec + 2,
          static_cast<std::uint16_t>(static_cast<std::int16_t>(std::clamp(white_score, -32768, 32767))));
  bytes_.insert(bytes_.end(), rec, rec + MoveRecordBytes);
  ++positions_;
}

void GameWriter::finish(GameResult result) {
  bytes_[30] = static_cast<std::uint8_t>(result);
  bytes_.insert(bytes_.end(), MoveRecordBytes, 0);
}

bool decode_game(std::span<const std::uint8_t> data, std::size_t& offset, ReadGame& out, std::string& error) {
  out.moves.clear();
  if (data.size() - offset < CompactBoardBytes) return error = "truncated board", false;
  const std::uint8_t* h = data.data() + offset;
  offset += CompactBoardBytes;

  Bitboard occupied = 0;
  for (int i = 0; i < 8; ++i) occupied |= Bitboard{h[i]} << (8 * i);
  if (!occupied) return error = "zero occupancy (an extension record, or not a game)", false;
  if (popcount(occupied) > 32) return error = "more than 32 pieces", false;

  char board[64];
  std::fill(std::begin(board), std::end(board), '.');
  std::string castling;
  int k = 0;
  for (Bitboard b = occupied; b; ++k) {
    const Square s = pop_lsb(b);
    const int code = (h[8 + k / 2] >> (4 * (k & 1))) & 15;
    const int type = code & 7;
    const Color color = Color(code >> 3);
    if (type == 7) return error = "invalid piece code", false;
    int kind = type;
    if (type == CastlingRookType) {
      kind = Rook;
      char right = 0;
      for (const auto& c : CornerRooks)
        if (c.square == s && c.color == color) right = c.fen;
      if (!right) return error = "castling rook off its corner", false;
      castling += right;
    }
    board[s] = "pnbrqk"[kind];
    if (color == White) board[s] = static_cast<char>(board[s] - 'a' + 'A');
  }
  if (h[30] > 2) return error = "invalid result", false;
  if (h[31] != 0) return error = "nonzero reserved byte", false;
  const int ep = h[24] & 127;
  if (ep > 64) return error = "invalid en passant square", false;

  std::string fen;
  for (int rank = 7; rank >= 0; --rank) {
    int empty = 0;
    for (int file = 0; file < 8; ++file) {
      const char c = board[rank * 8 + file];
      if (c == '.') {
        ++empty;
        continue;
      }
      if (empty) fen += static_cast<char>('0' + empty);
      empty = 0;
      fen += c;
    }
    if (empty) fen += static_cast<char>('0' + empty);
    if (rank) fen += '/';
  }
  std::sort(castling.begin(), castling.end(), [](char a, char b) {
    return std::string_view("KQkq").find(a) < std::string_view("KQkq").find(b);
  });
  fen += (h[24] & 128) ? " b " : " w ";
  fen += castling.empty() ? "-" : castling;
  fen += ' ';
  fen += ep == 64 ? std::string("-")
                  : std::string{static_cast<char>('a' + ep % 8), static_cast<char>('1' + ep / 8)};
  fen += ' ' + std::to_string(h[25]) + ' ' + std::to_string(std::max<int>(1, get_u16(h + 26)));

  Position pos;
  std::string why;
  if (!pos.set_fen(fen, &why)) return error = "bad start position (" + why + "): " + fen, false;
  out.start_fen = pos.fen();
  out.result = static_cast<GameResult>(h[30]);

  for (;;) {
    if (data.size() - offset < MoveRecordBytes) return error = "truncated move list", false;
    const std::uint8_t* r = data.data() + offset;
    offset += MoveRecordBytes;
    const std::uint16_t code = get_u16(r);
    const int score = static_cast<std::int16_t>(get_u16(r + 2));
    if (code == 0) {
      if (score != 0) return error = "malformed terminator", false;
      return true;
    }
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    const auto match =
        std::find_if(legal.begin(), legal.end(), [code](Move m) { return encode_move(m) == code; });
    if (match == legal.end())
      return error = "illegal move " + std::to_string(code) + " in " + pos.fen(), false;
    out.moves.push_back({*match, score});
    pos.make(*match);
  }
}

}  // namespace forkeng
