// SPDX-License-Identifier: GPL-3.0-or-later

// The network compiled into an FORK_EVALUATOR=nnue build (cmake/embed_net.cmake
// writes its bytes from FORK_NET), read and validated once.
#include <cstdio>
#include <cstdlib>
#include <span>
#include <string>

#include "eval/eval.hpp"

namespace forkeng {

extern const unsigned char embedded_net_bytes[];
extern const std::size_t embedded_net_size;

const NetFile& embedded_net() {
  // Read on first use, which the Searcher's constructor forces before any
  // search; kept for the whole process. An invalid embedded network is a
  // build error, so the engine stops at once rather than play with it.
  static const NetFile* const net = [] {
    auto* n = new NetFile;
    std::string error;
    if (!read_net_file(std::span(embedded_net_bytes, embedded_net_size), *n, error)) {
      std::fprintf(stderr, "fork: the embedded network is invalid: %s\n", error.c_str());
      std::abort();
    }
    return n;
  }();
  return *net;
}

}  // namespace forkeng
