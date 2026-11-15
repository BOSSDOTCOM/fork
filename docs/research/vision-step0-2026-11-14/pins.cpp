// Scratch check for vision step 0: Fork's own Position::pinned() and discoverers() per FEN (hex, one line each).
#include <cstdio>
#include <iostream>
#include <string>
#include "core/position.hpp"
int main() {
  forkeng::init();
  std::string line;
  while (std::getline(std::cin, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    forkeng::Position pos;
    if (!pos.set_fen(line)) { std::puts("invalid"); continue; }
    std::printf("%llx %llx\n", (unsigned long long)pos.pinned(), (unsigned long long)pos.discoverers());
  }
}
