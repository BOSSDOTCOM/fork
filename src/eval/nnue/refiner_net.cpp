// SPDX-License-Identifier: GPL-3.0-or-later

// The oracle's refiner network (refiner_net.hpp; cmake/embed_net.cmake writes
// its bytes from FORK_REFINER_NET as refiner_net), read and validated once.
#include "eval/nnue/refiner_net.hpp"

#include <cstdio>
#include <cstdlib>
#include <span>
#include <string>

namespace forkeng {

extern const unsigned char* const refiner_net_bytes;
extern const std::size_t refiner_net_size;

const NetFile& refiner_net() {
  static const NetFile* const net = [] {
    auto* n = new NetFile;
    std::string error;
    if (!read_net_file(std::span(refiner_net_bytes, refiner_net_size), *n, error) ||
        n->inputs == NetPieceSquares) {  // the refiner must be an S512+X net, not a plain one
      std::fprintf(stderr, "fork: the embedded refiner network is invalid: %s\n",
                   error.empty() ? "a plain S-512 net" : error.c_str());
      std::abort();
    }
    return n;
  }();
  return *net;
}

}  // namespace forkeng
