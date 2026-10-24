// Draw rules: repetition counting.
#include "core/position.hpp"
#include "harness.hpp"

using namespace forkeng;
using namespace forkeng::test;

namespace {

void play(Position& pos, std::initializer_list<const char*> moves) {
  for (const char* uci : moves) {
    Move m = pos.parse_uci(uci);
    CHECK_MSG(!m.is_none(), uci);
    if (!m.is_none()) pos.make(m);
  }
}

}  // namespace

TEST_CASE("draws", "a position repeats after a knight shuffle") {
  Position pos;
  play(pos, {"g1f3", "g8f6", "f3g1", "f6g8"});
  CHECK_EQ(pos.repetition_count(), 2);
  play(pos, {"g1f3", "g8f6", "f3g1", "f6g8"});
  CHECK_EQ(pos.repetition_count(), 3);
}

TEST_CASE("draws", "an irreversible move ends the repetition window") {
  Position pos;
  play(pos, {"g1f3", "g8f6", "f3g1", "f6g8", "e2e4", "e7e5"});
  CHECK_EQ(pos.repetition_count(), 1);
}

// Review M2 (2026-10-23): the window reached back across a null move. The
// start position with Black to move exists only because White passed, so a
// search must not count a later occurrence as a repetition of it.
TEST_CASE("draws", "the repetition window stops at a null move") {
  Position pos;
  pos.make_null();
  play(pos, {"g8f6", "b1c3", "f6g8", "c3b1"});
  CHECK_EQ(pos.repetition_count(), 1);
  // After the null move, ordinary repetitions still count.
  play(pos, {"g8f6", "b1c3", "f6g8", "c3b1"});
  CHECK_EQ(pos.repetition_count(), 2);
}
