// libFuzzer target: move parsing and validation. The first byte picks a
// position; the rest is split into UCI-like tokens (parse_uci) and read as
// raw 16-bit encodings (is_pseudo_legal / is_legal / gives_check / predicted_key),
// each checked against the generator and against make().
#include <cstdint>
#include <cstdlib>
#include <string>
#include <string_view>

#include "core/movegen.hpp"

namespace {

void require(bool ok) {
  if (!ok) std::abort();
}

constexpr std::string_view Starts[] = {
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
    "8/8/8/2k5/3Pp3/8/8/4K3 b - d3 0 1",
    "8/8/8/KPp4r/8/8/8/7k w - c6 0 1",
    "n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1",
};

void check_move(fork::Position& pos, const fork::MoveList& legal, fork::Move m) {
  bool accepted = pos.is_pseudo_legal(m) && pos.is_legal(m);
  require(accepted == legal.contains(m));
  if (!accepted) return;
  bool check = pos.gives_check(m);
  fork::Key k = pos.predicted_key(m);
  pos.make(m);
  require(pos.in_check() == check && pos.key() == k);
  pos.unmake(m);
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
  static const bool initialized = (fork::init(), true);
  (void)initialized;
  if (size < 1 || size > 4096) return 0;

  fork::Position pos;
  require(pos.set_fen(Starts[data[0] % std::size(Starts)]));
  std::string_view rest(reinterpret_cast<const char*>(data + 1), size - 1);

  // Text tokens: parse_uci must accept exactly the legal moves' strings; play them.
  std::size_t played = 0;
  for (std::size_t i = 0; i < rest.size() && played < 200;) {
    std::size_t j = rest.find(' ', i);
    if (j == std::string_view::npos) j = rest.size();
    std::string_view token = rest.substr(i, j - i);
    i = j + 1;
    fork::MoveList legal;
    fork::generate<fork::GenMode::Legal>(pos, legal);
    fork::Move m = pos.parse_uci(token);
    if (m.is_none()) {
      for (fork::Move x : legal) require(pos.move_to_uci(x) != token);
      continue;
    }
    require(legal.contains(m));
    pos.make(m);
    ++played;
  }

  // Raw encodings, two bytes at a time, against the reached position.
  fork::MoveList legal;
  fork::generate<fork::GenMode::Legal>(pos, legal);
  for (std::size_t i = 1; i + 1 < size; i += 2)
    check_move(pos, legal, fork::Move::from_raw(static_cast<std::uint16_t>(data[i] | (data[i + 1] << 8))));
  return 0;
}
