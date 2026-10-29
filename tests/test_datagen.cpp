// SPDX-License-Identifier: GPL-3.0-or-later

// Self-play data generation (DESIGN.md §5.3, deliverable 2): the game
// format's writer and reader, and the game player's endings, adjudications
// and determinism. The format's independent oracle is
// tools/datagen/verify_games.py (its own decoder and python-chess's move
// generator), run by the datagen_verify test; these cases check Fork's side.
//
// Test positions: the CPW perft suite (tests/suite.hpp, cited there) and
// positions built for one purpose each, described where they are used.
#include <cstdint>
#include <memory>
#include <set>
#include <string>
#include <string_view>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "datagen/game_record.hpp"
#include "datagen/self_play.hpp"
#include "harness.hpp"
#include "search/endgame_tables.hpp"
#include "suite.hpp"

namespace forkeng::test {

namespace {

// Plays up to `plies` random legal moves from `fen` (seeded), recording each
// with a made-up score; returns the writer's bytes.
std::vector<std::uint8_t> random_game(std::string_view fen, int plies, std::uint64_t seed,
                                      ReadGame& expected, GameResult result) {
  Position pos;
  pos.set_fen(fen);
  GameWriter w;
  w.begin(pos);
  expected = ReadGame{pos.fen(), result, {}};
  for (int i = 0; i < plies; ++i) {
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    if (legal.size() == 0) break;
    const Move m = legal[splitmix_next(seed) % legal.size()];
    const int score = static_cast<int>(splitmix_next(seed) % 2001) - 1000;
    w.add(m, score);
    expected.moves.push_back({m, score});
    pos.make(m);
  }
  w.finish(result);
  return {w.bytes().begin(), w.bytes().end()};
}

bool same_game(const ReadGame& a, const ReadGame& b) {
  if (a.start_fen != b.start_fen || a.result != b.result || a.moves.size() != b.moves.size()) return false;
  for (std::size_t i = 0; i < a.moves.size(); ++i)
    if (!(a.moves[i].move == b.moves[i].move) || a.moves[i].white_score != b.moves[i].white_score)
      return false;
  return true;
}

std::unique_ptr<SelfPlayGame> player(std::uint64_t nodes, int max_plies = 500) {
  SelfPlayConfig c;
  c.nodes = nodes;
  c.hash_bytes = std::size_t{1} << 20;
  c.max_plies = max_plies;
  std::string report;
  auto p = SelfPlayGame::create(c, report);
  CHECK_MSG(p != nullptr, report);
  return p;
}

}  // namespace

TEST_CASE("datagen", "move codes are unique per position and follow the format's bit layout") {
  for (const auto& sp : perft_suite()) {
    Position pos;
    CHECK(pos.set_fen(sp.fen));
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    std::set<std::uint16_t> codes;
    for (Move m : legal) {
      const std::uint16_t c = encode_move(m);
      codes.insert(c);
      CHECK_EQ(c & 63, m.from());
      CHECK_EQ((c >> 6) & 63, m.to());
      const int type = c >> 14;
      CHECK_EQ(type, m.is_castle() ? 2 : m.is_en_passant() ? 1 : m.is_promotion() ? 3 : 0);
      if (m.is_promotion()) CHECK_EQ((c >> 12) & 3, m.promo_type() - Knight);
      if (!m.is_promotion()) CHECK_EQ((c >> 12) & 3, 0);
      CHECK(c != 0);
    }
    CHECK_EQ(codes.size(), legal.size());
  }
}

TEST_CASE("datagen", "games round-trip through the writer and the reader") {
  int games = 0;
  for (const auto& sp : perft_suite()) {
    for (std::uint64_t seed = 1; seed <= 20; ++seed) {
      ReadGame expected;
      const auto result = static_cast<GameResult>(seed % 3);
      const auto bytes = random_game(sp.fen, 120, seed, expected, result);
      ReadGame got;
      std::string error;
      std::size_t offset = 0;
      CHECK_MSG(decode_game(bytes, offset, got, error), error);
      CHECK_EQ(offset, bytes.size());
      CHECK(same_game(expected, got));
      ++games;
    }
  }
  CHECK(games > 100);
}

TEST_CASE("datagen", "the reader walks back-to-back games and rejects malformed input") {
  ReadGame a, b, got;
  auto bytes = random_game(std::string(Position::StartFen), 30, 7, a, GameResult::WhiteWin);
  const auto second = random_game(perft_suite()[1].fen, 30, 8, b, GameResult::Draw);
  bytes.insert(bytes.end(), second.begin(), second.end());
  std::size_t offset = 0;
  std::string error;
  CHECK(decode_game(bytes, offset, got, error) && same_game(a, got));
  CHECK(decode_game(bytes, offset, got, error) && same_game(b, got));
  CHECK_EQ(offset, bytes.size());

  auto rejects = [&](std::vector<std::uint8_t> bad, const char* what) {
    std::size_t at = 0;
    std::string why;
    CHECK_MSG(!decode_game(bad, at, got, why) && !why.empty(), what);
  };
  rejects({bytes.begin(), bytes.begin() + 20}, "truncated board");
  rejects({bytes.begin(), bytes.begin() + 40}, "truncated move list");
  auto zero = second;
  for (int i = 0; i < 8; ++i) zero[i] = 0;
  rejects(zero, "zero occupancy");
  auto result = second;
  result[30] = 3;
  rejects(result, "result byte 3");
  auto reserved = second;
  reserved[31] = 1;
  rejects(reserved, "reserved byte");
  auto illegal = second;
  illegal[32] = illegal[33] = 0xFF;  // the first move becomes h8 to h8, promotion type
  rejects(illegal, "illegal first move");
  auto code7 = second;
  code7[8] = static_cast<std::uint8_t>((code7[8] & 0xF0) | 7);
  rejects(code7, "piece code 7");
}

TEST_CASE("datagen", "castling rights travel only in the rook codes") {
  // Kiwipete (perft suite position 2) has all four rights; dropping them one
  // at a time must change exactly that rook's code.
  const std::string base(perft_suite()[1].fen);
  for (const char* rights : {"KQkq", "Qkq", "Kkq", "KQq", "KQk", "-"}) {
    std::string fen = base;
    fen.replace(fen.find("KQkq"), 4, rights);
    Position pos;
    CHECK(pos.set_fen(fen));
    std::uint8_t board[CompactBoardBytes];
    encode_board(pos, GameResult::Draw, board);
    std::vector<std::uint8_t> bytes(board, board + CompactBoardBytes);
    bytes.insert(bytes.end(), MoveRecordBytes, 0);
    std::size_t offset = 0;
    ReadGame got;
    std::string error;
    CHECK_MSG(decode_game(bytes, offset, got, error), error);
    CHECK_EQ(got.start_fen, pos.fen());
  }
}

TEST_CASE("datagen", "a self-play game is deterministic and reads back legal") {
  auto p = player(3000);
  if (!p) return;
  Position start;
  GameWriter w1, w2;
  const SelfPlayOutcome a = p->play(start, w1);
  const std::vector<std::uint8_t> first(w1.bytes().begin(), w1.bytes().end());
  const SelfPlayOutcome b = p->play(start, w2);
  CHECK(a.written && b.written);
  CHECK(first == std::vector<std::uint8_t>(w2.bytes().begin(), w2.bytes().end()));
  CHECK(a.end == b.end && a.result == b.result);
  std::size_t offset = 0;
  ReadGame got;
  std::string error;
  CHECK_MSG(decode_game(first, offset, got, error), error);
  CHECK_EQ(static_cast<int>(got.moves.size()), w1.positions());
  CHECK(got.moves.size() > 10);
}

TEST_CASE("datagen", "openings beyond the decided bound and over-long games are not written") {
  auto p = player(3000);
  if (!p) return;
  // The start position without Black's queen: built for this case, a
  // queen up for White, far beyond the 400 cp bound.
  Position pos;
  CHECK(pos.set_fen("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"));
  GameWriter w;
  const SelfPlayOutcome decided = p->play(pos, w);
  CHECK(!decided.written);
  CHECK(decided.end == GameEnd::DecidedOpening);

  auto short_player = player(3000, 4);
  if (!short_player) return;
  const SelfPlayOutcome too_long = short_player->play(Position(), w);
  CHECK(!too_long.written);
  CHECK(too_long.end == GameEnd::TooLong);
}

TEST_CASE("datagen", "a node limit too small for depth 1 falls back to a depth-1 search") {
  // One node never finishes depth 1: every move takes the fallback, and the
  // game runs into the ply cap instead of stopping the program.
  auto p = player(1, 6);
  if (!p) return;
  GameWriter w;
  const SelfPlayOutcome o = p->play(Position(), w);
  CHECK(o.end == GameEnd::TooLong);
  CHECK_EQ(w.positions(), 6);
}

TEST_CASE("datagen", "a reported mate ends the game with the mating move recorded") {
  auto p = player(3000);
  if (!p) return;
  // Built for this case: White mates with Ra8 (Black's king on g8 behind
  // its own f7, g7, h7 pawns); any other first move is no mate.
  Position pos;
  CHECK(pos.set_fen("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"));
  GameWriter w;
  const SelfPlayOutcome o = p->play(pos, w);
  CHECK(o.written);
  CHECK(o.end == GameEnd::MateFound);
  CHECK(o.result == GameResult::WhiteWin);
  std::size_t offset = 0;
  ReadGame got;
  std::string error;
  const std::vector<std::uint8_t> bytes(w.bytes().begin(), w.bytes().end());
  CHECK_MSG(decode_game(bytes, offset, got, error), error);
  CHECK_EQ(got.moves.size(), std::size_t{1});
  if (got.moves.size() == 1) {
    CHECK_EQ(pos.move_to_uci(got.moves[0].move), std::string("a1a8"));
    CHECK(got.moves[0].white_score > 0);
  }
}

TEST_CASE("datagen", "the Syzygy tables adjudicate a game whose root they cover") {
  load_endgame_tables(FORK_SYZYGY345_DIR);
  if (endgame_table_pieces() < 3) {
    load_endgame_tables("");
    CHECK_MSG(false, "the 3-4-5 test tables are missing from " FORK_SYZYGY345_DIR " (CMake downloads them)");
    return;
  }
  auto p = player(3000);
  if (p) {
    // Built for this case: king and queen against king (KQvK is among the
    // downloaded tables), White to move, a table win; and the same with only
    // a knight (KNvK), a table draw.
    Position win, draw;
    CHECK(win.set_fen("4k3/8/8/8/8/8/8/3QK3 w - - 0 1"));
    CHECK(draw.set_fen("4k3/8/8/8/8/8/8/3NK3 w - - 0 1"));
    GameWriter w;
    SelfPlayOutcome o = p->play(win, w);
    CHECK(o.end == GameEnd::TableResult && o.result == GameResult::WhiteWin && w.positions() == 0);
    o = p->play(draw, w);
    CHECK(o.end == GameEnd::InsufficientMaterial || o.end == GameEnd::TableResult);
    CHECK(o.result == GameResult::Draw);
  }
  load_endgame_tables("");
}

}  // namespace forkeng::test
