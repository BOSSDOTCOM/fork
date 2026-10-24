// Writes Fork's between, line, mask and slider attack tables as binary files,
// so their SHA-256 fingerprints can be compared across rewrites and builds
// (docs/ORIGINALITY.md lists the expected values). Every value is a uint64
// written as 8 little-endian bytes:
//   between.bin         between(a, b), a = 0..63 outer, b = 0..63 inner
//   line.bin            line(a, b), same order
//   masks.bin           rook mask for s = 0..63, then bishop mask for s = 0..63
//   rook_attacks.bin    for s = 0..63: rook_attacks(s, occ) for every subset occ
//                       of the rook mask, in ascending numeric order of occ
//   bishop_attacks.bin  the same for bishops
//
//   fork_dump_tables <output directory>
//   (cd <output directory> && sha256sum *.bin)
#include <cstdio>
#include <string>

#include "core/bitboard.hpp"

using namespace forkeng;

namespace {

bool write_all(const std::string& path, auto&& produce) {
  std::FILE* f = std::fopen(path.c_str(), "wb");
  if (!f) return false;
  produce([f](Bitboard b) {
    unsigned char bytes[8];
    for (int i = 0; i < 8; ++i) bytes[i] = static_cast<unsigned char>(b >> (8 * i));
    std::fwrite(bytes, 1, 8, f);
  });
  return std::fclose(f) == 0;
}

// Every subset of `mask` in ascending numeric order (the carry-rippler step of
// CPW "Traversing Subsets of a Set").
template <class F>
void each_subset(Bitboard mask, F&& f) {
  Bitboard subset = 0;
  do {
    f(subset);
    subset = (subset - mask) & mask;
  } while (subset);
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    std::fprintf(stderr, "usage: fork_dump_tables <output directory>\n");
    return 2;
  }
  init_bitboards();
  const std::string dir = argv[1];
  bool ok = write_all(dir + "/between.bin", [](auto put) {
    for (Square a = 0; a < 64; ++a)
      for (Square b = 0; b < 64; ++b) put(between(a, b));
  });
  ok &= write_all(dir + "/line.bin", [](auto put) {
    for (Square a = 0; a < 64; ++a)
      for (Square b = 0; b < 64; ++b) put(line(a, b));
  });
  ok &= write_all(dir + "/masks.bin", [](auto put) {
    for (Square s = 0; s < 64; ++s) put(tables::rook[s].mask);
    for (Square s = 0; s < 64; ++s) put(tables::bishop[s].mask);
  });
  ok &= write_all(dir + "/rook_attacks.bin", [](auto put) {
    for (Square s = 0; s < 64; ++s) each_subset(tables::rook[s].mask, [&](Bitboard o) { put(rook_attacks(s, o)); });
  });
  ok &= write_all(dir + "/bishop_attacks.bin", [](auto put) {
    for (Square s = 0; s < 64; ++s)
      each_subset(tables::bishop[s].mask, [&](Bitboard o) { put(bishop_attacks(s, o)); });
  });
  if (!ok) std::fprintf(stderr, "fork_dump_tables: could not write to %s\n", dir.c_str());
  return ok ? 0 : 1;
}
