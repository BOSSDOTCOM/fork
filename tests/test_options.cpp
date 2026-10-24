// In-process tests of the option table, the go parser and the hash memory
// (the protocol itself is tested over pipes in test_uci.cpp).
#include <algorithm>
#include <cstddef>
#include <limits>
#include <string>
#include <thread>
#include <vector>

#include "harness.hpp"
#include "search/hash_memory.hpp"
#include "uci/go_limits.hpp"
#include "uci/options.hpp"
#include "uci/tokens.hpp"

namespace forkeng::test {

namespace {

OptionTable sample_table(int& presses) {
  OptionTable t;
  t.add_spin("Hash", 16, 1, 4194304);
  t.add_check("Use Thing", false);
  t.add_button("Clear Hash", [&presses](const OptionEntry&, std::string&) { return ++presses > 0; });
  t.add_string("SyzygyPath", "");
  t.add_string("Picky", "keep", [](const OptionEntry& e, std::string& message) {
    if (e.text == "bad") {
      message = "refused";
      return false;
    }
    return true;
  });
  return t;
}

}  // namespace

TEST_CASE("uci_options", "hash sizes are 64-bit byte counts") {
  static_assert(sizeof(std::size_t) == 8, "Fork targets 64-bit platforms");
  CHECK_EQ(hash_bytes_for_mb(1), std::size_t{1048576});
  CHECK_EQ(hash_bytes_for_mb(262144), std::size_t{274877906944});    // TCEC's Hash, 256 GiB
  CHECK_EQ(hash_bytes_for_mb(4194304), std::size_t{4398046511104});  // the maximum, 4 TiB = 2^42
}

TEST_CASE("uci_options", "option lines in declaration order") {
  int presses = 0;
  const std::vector<std::string> lines = sample_table(presses).option_lines();
  const std::vector<std::string> want = {
      "option name Hash type spin default 16 min 1 max 4194304",
      "option name Use Thing type check default false", "option name Clear Hash type button",
      "option name SyzygyPath type string default <empty>", "option name Picky type string default keep"};
  CHECK(lines == want);
}

TEST_CASE("uci_options", "set: names, values, rejections") {
  int presses = 0;
  OptionTable t = sample_table(presses);
  std::string msg;
  CHECK(t.set("hash", "64", msg));
  CHECK_EQ(t.number("Hash"), 64);
  CHECK(t.set("HASH", "+65", msg));
  CHECK_EQ(t.number("Hash"), 65);
  CHECK(t.set("  use \t THING ", "TRUE", msg));  // whitespace runs fold, case folds
  CHECK_EQ(t.number("Use Thing"), 1);
  CHECK(t.set("Use Thing", "false", msg));
  CHECK_EQ(t.number("Use Thing"), 0);
  for (const char* bad : {"0", "33554433", "-1", "abc", "12ab", "", "1 6", "99999999999999999999"}) {
    msg.clear();
    CHECK_MSG(!t.set("Hash", std::string_view(bad), msg), bad);
    CHECK(!msg.empty());
  }
  CHECK(!t.set("Hash", std::nullopt, msg));
  CHECK_EQ(t.number("Hash"), 65);  // unchanged by every rejection
  CHECK(!t.set("Use Thing", "yes", msg));
  CHECK(!t.set("Use Thing", std::nullopt, msg));
  CHECK_EQ(t.number("Use Thing"), 0);
  CHECK(!t.set("No Such", "1", msg));
  CHECK(t.set("Clear Hash", std::nullopt, msg));
  CHECK(t.set("clear hash", "ignored", msg));
  CHECK_EQ(presses, 2);
  CHECK(t.set("SyzygyPath", "C:\\tb one;D:\\tb two", msg));
  CHECK_EQ(t.text("SyzygyPath"), std::string("C:\\tb one;D:\\tb two"));
  CHECK(t.set("SyzygyPath", "<empty>", msg));
  CHECK_EQ(t.text("SyzygyPath"), std::string());
  CHECK(!t.set("SyzygyPath", std::nullopt, msg));
  msg.clear();
  CHECK(!t.set("Picky", "bad", msg));  // the handler's veto keeps the old value
  CHECK_EQ(msg, std::string("refused"));
  CHECK_EQ(t.text("Picky"), std::string("keep"));
}

TEST_CASE("uci_options", "parse_int64 and the go parser") {
  CHECK(parse_int64("0") == std::optional<std::int64_t>(0));
  CHECK(parse_int64("-5") == std::optional<std::int64_t>(-5));
  CHECK(parse_int64("9223372036854775807") ==
        std::optional<std::int64_t>(std::numeric_limits<std::int64_t>::max()));
  CHECK(parse_int64("-9223372036854775808") ==
        std::optional<std::int64_t>(std::numeric_limits<std::int64_t>::min()));
  CHECK(parse_int64("99999999999999999999") ==
        std::optional<std::int64_t>(std::numeric_limits<std::int64_t>::max()));
  CHECK(parse_int64("-99999999999999999999") ==
        std::optional<std::int64_t>(std::numeric_limits<std::int64_t>::min()));
  for (const char* bad : {"", "-", "+", "1.5", "0x10", " 1", "1e3", "--1"}) CHECK_MSG(!parse_int64(bad), bad);

  const Position start;
  std::vector<std::string> warnings;
  const std::string line =
      "go searchmoves e2e4 e2e4 d2d4 zz wtime 1000 btime -20 winc 5 binc 6 movestogo 40 depth 7 nodes "
      "1000000 "
      "mate 3 movetime 250 ponder infinite";
  const std::vector<LineToken> tokens = split_tokens(line);
  const GoLimits g = parse_go(tokens, 1, start, warnings);
  CHECK_EQ(warnings.size(), std::size_t{1});  // zz
  CHECK_EQ(g.restrict_to.size(), std::size_t{2});
  CHECK(g.remaining_ms[White] == std::optional<std::int64_t>(1000) &&
        g.remaining_ms[Black] == std::optional<std::int64_t>(-20));
  CHECK(g.increment_ms[White] == std::optional<std::int64_t>(5) &&
        g.increment_ms[Black] == std::optional<std::int64_t>(6));
  CHECK(g.movestogo == std::optional<std::int64_t>(40) && g.depth == std::optional<std::int64_t>(7));
  CHECK(g.nodes == std::optional<std::int64_t>(1000000) && g.mate == std::optional<std::int64_t>(3));
  CHECK(g.movetime == std::optional<std::int64_t>(250));
  CHECK(g.ponder && g.infinite && g.restrict_sent);

  warnings.clear();
  const GoLimits bare = parse_go(split_tokens("go"), 1, start, warnings);
  CHECK(warnings.empty() && !bare.remaining_ms[White] && !bare.depth && !bare.infinite &&
        !bare.restrict_sent);
  // A keyword missing its number does not swallow the next keyword.
  const GoLimits gap = parse_go(split_tokens("go depth movetime 5"), 1, start, warnings);
  CHECK(!gap.depth && gap.movetime == std::optional<std::int64_t>(5));
}

TEST_CASE("uci_options", "clear_workers") {
  const std::int64_t hw = std::max<std::int64_t>(1, std::thread::hardware_concurrency());
  CHECK_EQ(clear_workers(BytesPerMB, 1), 1u);  // below 2 MiB per thread
  CHECK_EQ(clear_workers(16 * BytesPerMB, 1), static_cast<unsigned>(std::min<std::int64_t>(hw, 8)));
  CHECK_EQ(clear_workers(std::size_t{1} << 40, 1024), 1024u);  // Threads above the hardware count
  CHECK_EQ(clear_workers(std::size_t{1} << 40, 1), static_cast<unsigned>(hw));
}

TEST_CASE("uci_options", "HashMemory: resize, clear, refused sizes keep a table") {
  HashMemory h;
  std::string report;
  CHECK(h.resize(4 * BytesPerMB, report));
  CHECK_EQ(h.bytes(), 4 * BytesPerMB);
  CHECK(h.data() != nullptr);
  std::fill(h.data(), h.data() + h.bytes(), std::byte{0xA5});
  h.clear(3);
  CHECK(std::all_of(h.data(), h.data() + h.bytes(), [](std::byte b) { return b == std::byte{0}; }));
  CHECK(h.resize(2 * BytesPerMB, report));
  CHECK_EQ(h.bytes(), 2 * BytesPerMB);
  // 1 TiB: more than this machine has, so the previous size stays.
  report.clear();
  CHECK(!h.resize(hash_bytes_for_mb(1048576), report));
  CHECK_EQ(h.bytes(), 2 * BytesPerMB);
  CHECK_MSG(report.find("using 2 MB") != std::string::npos, report);
  CHECK(std::all_of(h.data(), h.data() + h.bytes(), [](std::byte b) { return b == std::byte{0}; }));
}

// The Threads maximum (owner, 2026-10-24): nothing is sized for a fixed
// thread count, so a clear with 4096 workers (more than the engine would
// ever start for this size) works and zeroes every byte.
TEST_CASE("uci_options", "HashMemory: a clear with 4096 workers") {
  HashMemory h;
  std::string report;
  CHECK(h.resize(16 * BytesPerMB, report));
  std::fill(h.data(), h.data() + h.bytes(), std::byte{0x5A});
  h.clear(4096);
  CHECK(std::all_of(h.data(), h.data() + h.bytes(), [](std::byte b) { return b == std::byte{0}; }));
  CHECK_EQ(clear_workers(hash_bytes_for_mb(4194304), 4096), 4096u);  // 4 TiB at Threads 4096
}

}  // namespace forkeng::test
