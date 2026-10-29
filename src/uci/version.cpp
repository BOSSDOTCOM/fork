// SPDX-License-Identifier: GPL-3.0-or-later

// The version string, from CMakeLists.txt at configure time: the project
// version, "-dev", and "+<short commit>" when the tree is a git checkout.
#include "uci/session.hpp"

#ifndef FORK_VERSION
#error "FORK_VERSION is set by CMakeLists.txt"
#endif

namespace forkeng {

const char* engine_version() { return FORK_VERSION; }

}  // namespace forkeng
