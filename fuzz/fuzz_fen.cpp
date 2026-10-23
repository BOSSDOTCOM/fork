// libFuzzer target: arbitrary bytes into the FEN parser. Accepted positions
// must round-trip and stay consistent through make/unmake of every legal move.
#include <cstdint>
#include <cstdlib>
#include <string>

#include "core/movegen.hpp"

namespace {

void require(bool ok) {
  if (!ok) std::abort();  // libFuzzer reports the crash with its input
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
  static const bool initialized = (fork::init(), true);
  (void)initialized;
  if (size > 512) return 0;
  std::string fen(reinterpret_cast<const char*>(data), size);

  fork::Position pos;
  std::string error;
  if (!pos.set_fen(fen, &error)) {
    require(!error.empty());
    require(pos.fen() == fork::Position::StartFen);  // unchanged on failure
    return 0;
  }

  // Round trip: our own output must parse back to the same position.
  fork::Position again;
  require(again.set_fen(pos.fen()));
  require(again.fen() == pos.fen() && again.key() == pos.key());
  require(pos.state() == pos.compute_state());

  fork::MoveList list;
  fork::generate<fork::GenType::Legal>(pos, list);
  const fork::Position snapshot = pos;
  for (fork::Move m : list) {
    require(pos.is_pseudo_legal(m) && pos.is_legal(m));
    bool check = pos.gives_check(m);
    fork::Key k = pos.key_after(m);
    pos.make(m);
    require(pos.in_check() == check && pos.key() == k);
    require(pos.state() == pos.compute_state());
    pos.unmake(m);
    require(pos.same_state(snapshot));
  }
  return 0;
}
