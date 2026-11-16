// SPDX-License-Identifier: GPL-3.0-or-later

// The network compiled into an FORK_EVALUATOR=nnue build (cmake/embed_net.cmake
// writes its bytes from FORK_NET), read and validated once; and, in idea 84's
// experiment builds only (FORK_HELPER_NET), the helper threads' second network.
#include <cstdio>
#include <cstdlib>
#include <span>
#include <string>

#include "eval/eval.hpp"

namespace forkeng {

// The bytes (cmake/embed_net.cmake: an array for small networks, the
// assembler's .incbin for large ones) and their count.
extern const unsigned char* const embedded_net_bytes;
extern const std::size_t embedded_net_size;
#if defined(FORK_HELPER_NET_EMBEDDED)
extern const unsigned char* const helper_net_bytes;
extern const std::size_t helper_net_size;
#endif

namespace {

// A compiled-in network, read for the whole process. An invalid one is a
// build error, so the engine stops at once rather than play with it.
const NetFile* read_compiled_net(const unsigned char* bytes, std::size_t size, const char* what) {
  auto* n = new NetFile;
  std::string error;
  if (!read_net_file(std::span(bytes, size), *n, error)) {
    std::fprintf(stderr, "fork: the %s is invalid: %s\n", what, error.c_str());
    std::abort();
  }
  return n;
}

}  // namespace

const NetFile& embedded_net() {
  // Read on first use, which the Searcher's constructor forces before any
  // search.
  static const NetFile* const net =
      read_compiled_net(embedded_net_bytes, embedded_net_size, "embedded network");
  return *net;
}

const NetFile* helper_net() {
#if defined(FORK_HELPER_NET_EMBEDDED)
  // Read on first use, which the HelperPool's constructor forces before any
  // search.
  static const NetFile* const net = read_compiled_net(helper_net_bytes, helper_net_size, "helper network");
  return net;
#else
  return nullptr;
#endif
}

}  // namespace forkeng
