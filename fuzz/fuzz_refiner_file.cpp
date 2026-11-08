// SPDX-License-Identifier: GPL-3.0-or-later

// libFuzzer target: arbitrary bytes into the Boundary Refiner's file reader
// (src/eval/nnue/refiner_file.hpp; ideas.md 59, step 3). The reader must never
// crash or read out of bounds; a file it accepts must write back to exactly
// its bytes, and the inference on it must give the same output on the vector
// and the scalar path (its bounds keep every sum in range, so UBSan sees no
// overflow). Each input is read as it is and once more with its payload
// checksum recomputed, so mutations of the payload reach the checks behind
// the checksum.
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <span>
#include <string>
#include <vector>

#include "eval/nnue/net_file.hpp"
#include "eval/nnue/refiner.hpp"
#include "eval/nnue/refiner_file.hpp"

namespace {

void require(bool ok) {
  if (!ok) std::abort();  // libFuzzer reports the crash with its input
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
  if (size > 65536) return 0;
  static const auto refiner = std::make_unique<forkeng::RefinerFile>();
  std::vector<std::uint8_t> bytes(data, data + size);
  for (int pass = 0; pass < 2; ++pass) {
    if (pass == 1) {
      if (size < 64) return 0;
      const std::uint64_t sum = forkeng::net_checksum(std::span<const std::uint8_t>(bytes).subspan(64));
      for (int i = 0; i < 8; ++i) bytes[40 + i] = static_cast<std::uint8_t>(sum >> (8 * i));
    }
    std::string error;
    if (!forkeng::read_refiner_file(bytes, *refiner, error)) {
      require(!error.empty());
      continue;
    }
    require(forkeng::write_refiner_file(*refiner) == bytes);
    forkeng::RefinerInputs in;
    for (int i = 0; i < forkeng::RefinerInputBytes; ++i) in.bytes[i] = static_cast<std::uint8_t>(255 - i % 7);
    in.row_count = forkeng::RefinerMaxActive;
    for (int i = 0; i < in.row_count; ++i) in.rows[i] = (i * 37) % forkeng::RefinerRows;
    const forkeng::RefinerOutput a = forkeng::run_refiner(*refiner, in),
                                 b = forkeng::run_refiner_scalar(*refiner, in);
    require(a.correction == b.correction && a.confidence == b.confidence);
    require(a.correction >= -refiner->cap && a.correction <= refiner->cap);
    require(a.confidence >= 0 && a.confidence <= 1000);
  }
  return 0;
}
