// The bootstrap evaluation (DESIGN.md §5.2, deliverable 1). Positions other
// than the perft suite are constructed for Fork; set_fen validates them.
#include "core/movegen.hpp"
#include "eval/eval.hpp"
#include "harness.hpp"
#include "suite.hpp"

namespace forkeng::test {

namespace {

// Every node of the tree to `depth`: the score equals the mirror's score.
void check_symmetry(Position& pos, int depth, int& checked) {
  const Position mirror = pos.mirrored();
  CHECK_MSG(static_eval(pos) == static_eval(mirror), pos.fen());
  const int e = static_eval(pos);
  CHECK_MSG(e >= -EvalLimit && e <= EvalLimit, pos.fen());
  ++checked;
  if (depth == 0) return;
  MoveList list;
  generate<GenMode::Legal>(pos, list);
  for (Move m : list) {
    pos.make(m);
    check_symmetry(pos, depth - 1, checked);
    pos.unmake(m);
  }
}

int eval_of(std::string_view fen) {
  Position pos;
  const bool ok = pos.set_fen(fen);
  CHECK_MSG(ok, fen);
  return static_eval(pos);
}

}  // namespace

TEST_CASE("eval", "colour symmetry on every perft-suite node to depth 3 (2 in debug builds)") {
  int checked = 0;
  for (const PerftPosition& p : perft_suite()) {
    Position pos;
    CHECK(pos.set_fen(p.fen));
    check_symmetry(pos, Optimized ? 3 : 2, checked);
  }
  CHECK(checked > (Optimized ? 100000 : 1000));
}

TEST_CASE("eval", "start position scores 0; insufficient material scores 0") {
  CHECK_EQ(eval_of(Position::StartFen), 0);
  CHECK_EQ(eval_of("8/8/8/4k3/8/8/8/4K3 w - - 0 1"), 0);    // K v K
  CHECK_EQ(eval_of("8/8/8/4k3/8/8/8/2B1K3 b - - 0 1"), 0);  // K+B v K
  CHECK_EQ(eval_of("8/8/8/4k3/8/8/8/2N1K3 w - - 0 1"), 0);  // K+N v K
}

TEST_CASE("eval", "material decides the sign; side to move flips it") {
  // White is a rook up.
  CHECK(eval_of("4k3/pppppppp/8/8/8/8/PPPPPPPP/R3K3 w - - 0 1") > 300);
  CHECK(eval_of("4k3/pppppppp/8/8/8/8/PPPPPPPP/R3K3 b - - 0 1") < -300);
}

TEST_CASE("eval", "mop-up: with K+R v K the bare king on the edge scores better for the rook side") {
  const int edge = eval_of("k7/8/8/8/8/8/8/1R2K3 w - - 0 1");
  const int centre = eval_of("8/8/8/3k4/8/8/8/1R2K3 w - - 0 1");
  CHECK(edge > centre);
  // And the kings closer together is better for the stronger side.
  const int near = eval_of("k7/8/1K6/8/8/8/8/7R w - - 0 1");
  const int far = eval_of("k7/8/8/8/8/8/8/6KR w - - 0 1");
  CHECK(near > far);
}

}  // namespace forkeng::test
