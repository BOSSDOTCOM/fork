// perft: perft and divide (see perft.hpp).
#include "core/perft.hpp"

#include "core/movegen.hpp"

namespace forkeng {

std::uint64_t perft(Position& pos, int depth) {
  if (depth == 0) return 1;
  MoveList list;
  generate<GenMode::Legal>(pos, list);
  if (depth == 1) return list.size();
  std::uint64_t nodes = 0;
  for (Move m : list) {
    pos.make(m);
    nodes += perft(pos, depth - 1);
    pos.unmake(m);
  }
  return nodes;
}

std::uint64_t divide(Position& pos, int depth, std::ostream& out) {
  MoveList list;
  generate<GenMode::Legal>(pos, list);
  std::uint64_t total = 0;
  for (Move m : list) {
    pos.make(m);
    std::uint64_t n = depth > 1 ? perft(pos, depth - 1) : 1;
    pos.unmake(m);
    out << pos.move_to_uci(m) << ": " << n << '\n';
    total += n;
  }
  out << "\nnodes " << total << '\n';
  return total;
}

}  // namespace forkeng
