// SPDX-License-Identifier: GPL-3.0-or-later

// The Boundary Refiner compiled into a refiner build (ideas.md 59; CMake
// FORK_REFINER_NET; cmake/embed_net.cmake writes its bytes as
// embedded_refiner), read and validated once, and bound to the embedded base
// network by that network's payload checksum.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <span>
#include <string>

#include "eval/nnue/refiner_file.hpp"

namespace forkeng {

extern const unsigned char* const embedded_refiner_bytes;
extern const std::size_t embedded_refiner_size;
// The base network's bytes (embedded_net.cpp's source): its header holds its
// payload checksum at byte 40.
extern const unsigned char* const embedded_net_bytes;

const RefinerFile& embedded_refiner() {
  // Read on first use, which the Searcher's constructor forces before any
  // search; kept for the whole process. An invalid refiner, or one trained on
  // another base network, is a build error: the engine stops at once.
  static const RefinerFile* const refiner = [] {
    auto* r = new RefinerFile;
    std::string error;
    if (!read_refiner_file(std::span(embedded_refiner_bytes, embedded_refiner_size), *r, error)) {
      std::fprintf(stderr, "fork: the embedded refiner is invalid: %s\n", error.c_str());
      std::abort();
    }
    std::uint64_t base = 0;
    for (int i = 7; i >= 0; --i) base = base << 8 | embedded_net_bytes[40 + i];
    if (r->base_checksum != base) {
      std::fprintf(stderr,
                   "fork: the embedded refiner was trained on another base network (%016llx, not %016llx)\n",
                   static_cast<unsigned long long>(r->base_checksum), static_cast<unsigned long long>(base));
      std::abort();
    }
    return r;
  }();
  return *refiner;
}

}  // namespace forkeng
