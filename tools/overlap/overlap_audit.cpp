// SPDX-License-Identifier: GPL-3.0-or-later

// The training-data audit's overlap check (owner, 2026-11-11: "the training-data audit's validation/training
// overlap check", before retrain 8c's network decision; docs/research/overlap-audit-2026-11-11.md).
//
// Purpose: count how many positions and games of the query sets (validation files and held-out sets) also occur
// in a list of training files, streaming the training files once with a small, fixed memory footprint (the query
// keys only; nothing per training position is kept).
// Definitions (the research note repeats them):
// - A position is the one a record's move was played in (every record of a game, saved or not).
// - Key K1: piece placement, side to move, castling rights and the en passant square when an en passant capture
//   is legal (Fork's Position normalises it, so the key equals the first four FEN fields); the halfmove and
//   fullmove counters are ignored. Key K0: piece placement and side to move only (coarser).
// - Kept: the trainer's filter as recorded in idea 52's 8b-sites.json: saved (score not 32767), not in check, the
//   move played neither a capture nor a promotion, |score| <= 20,000.
// - A game's identity: its start board (the packed header's first 28 bytes: board, en passant and side, both
//   counters) and its move codes; scores and the result are ignored, so relabelled copies of a game match.
// Every hash hit is confirmed by an exact comparison (the FEN fields, or the game's bytes).
//
//   fork_overlap_audit QUERIES.lst TRAIN.lst OUT_PREFIX
//   QUERIES.lst: "vf<TAB>SET<TAB>PATH<TAB>MAX_GAMES" (0 = every game) or "fen<TAB>SET<TAB>PATH" (one FEN per line)
//   TRAIN.lst:   "GROUP<TAB>PATH[<TAB>SKIP]" (SKIP: leading games left out; at most 64 groups)
// Writes OUT_PREFIX-queries.tsv (one line per query position), OUT_PREFIX-games.tsv (one line per query game),
// OUT_PREFIX-files.tsv (one line per training file, with its record counts and hits) and OUT_PREFIX-groups.tsv
// (the group of each mask bit); progress on stderr.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <span>
#include <string>
#include <unordered_map>
#include <vector>

#include "core/position.hpp"
#include "core/zobrist.hpp"
#include "datagen/game_record.hpp"

namespace forkeng {
namespace {

constexpr int UnsavedRecordScore = 32767;  // src/datagen/self_play.hpp UnsavedScore
constexpr int KeptScoreLimit = 20000;      // tools/train/src/main.rs MAX_SCORE
constexpr std::size_t HeaderIdentityBytes = 28;
constexpr std::size_t ReadBlock = std::size_t{32} << 20;

struct QueryKey {
  std::string text;  // the exact comparison: FEN fields 1-4 (K1) or 1-2 (K0)
  std::uint32_t train_any = 0, train_kept = 0;  // occurrences in the training files (saturating)
  std::uint64_t any_mask = 0, kept_mask = 0;     // the training groups holding it (bit = group index)
};

struct QueryPosition {
  int set, item, ply, pieces, kept;
  std::uint32_t k1, k0;  // indices into the key tables
};

struct QueryGame {
  int set, item, plies;
  std::string identity;
  std::uint32_t start_key;
  std::uint32_t identical = 0, same_start = 0;
  std::uint64_t identical_mask = 0, start_mask = 0;
};

struct KeyTable {
  std::unordered_map<std::uint64_t, std::vector<std::uint32_t>> by_hash;
  std::vector<QueryKey> keys;

  std::uint32_t add(std::uint64_t h, const std::string& text) {
    auto& ids = by_hash[h];
    for (std::uint32_t id : ids)
      if (keys[id].text == text) return id;
    keys.push_back({text});
    ids.push_back(static_cast<std::uint32_t>(keys.size() - 1));
    return ids.back();
  }
  const std::vector<std::uint32_t>* find(std::uint64_t h) const {
    auto it = by_hash.find(h);
    return it == by_hash.end() ? nullptr : &it->second;
  }
};

std::string fen_fields(const Position& pos, int fields) {
  const std::string fen = pos.fen();
  std::size_t at = 0;
  for (int k = 0; k < fields && at != std::string::npos; ++k) at = fen.find(' ', at + (k ? 1 : 0));
  return at == std::string::npos ? fen : fen.substr(0, at);
}

std::uint64_t key_k0(const Position& pos) {
  std::uint64_t k = pos.key() ^ zobrist::castling[pos.castling_rights()];
  if (pos.ep_target() != NoSquare) k ^= zobrist::ep_file[file_of(pos.ep_target())];
  return k;
}

std::uint64_t fnv1a(const std::string& s) {
  std::uint64_t h = 1469598103934665603ULL;
  for (unsigned char c : s) h = (h ^ c) * 1099511628211ULL;
  return h;
}

bool is_kept(const Position& pos, Move m, int score) {
  return score != UnsavedRecordScore && !pos.in_check() && !m.is_capture() && !m.is_promotion() &&
         std::abs(score) <= KeptScoreLimit;
}

// The end of the game starting at `at` (just past its zero terminator), or 0 if the buffer ends first.
std::size_t game_end(const std::vector<std::uint8_t>& buf, std::size_t at, std::size_t size) {
  std::size_t o = at + CompactBoardBytes;
  while (o + MoveRecordBytes <= size) {
    const std::uint8_t* r = buf.data() + o;
    o += MoveRecordBytes;
    if (r[0] == 0 && r[1] == 0) return o;
  }
  return 0;
}

std::string game_identity(const std::uint8_t* g, std::size_t bytes) {
  std::string id(reinterpret_cast<const char*>(g), HeaderIdentityBytes);
  for (std::size_t o = CompactBoardBytes; o + MoveRecordBytes <= bytes; o += MoveRecordBytes)
    id.append(reinterpret_cast<const char*>(g + o), 2);
  return id;
}

// Calls visit(game_bytes, size, decoded) for every game of a file, reading it in blocks. Returns false on a
// malformed game (the reason in `error`); a trailing partial game is reported through `truncated`.
template <typename Visit>
bool for_each_game(const std::string& path, Visit visit, std::string& error, bool& truncated, long max_games,
                   long skip_games = 0) {
  std::FILE* f = std::fopen(path.c_str(), "rb");
  if (!f) return error = "cannot open " + path, false;
  std::vector<std::uint8_t> buf(ReadBlock * 2);
  std::size_t have = 0;
  long games = 0;
  bool eof = false;
  ReadGame game;
  truncated = false;
  while (!eof || have) {
    if (!eof && have < buf.size()) {
      const std::size_t n = std::fread(buf.data() + have, 1, buf.size() - have, f);
      have += n;
      if (n == 0) eof = true;
    }
    std::size_t at = 0;
    for (;;) {
      if (have - at < CompactBoardBytes) break;
      const std::size_t end = game_end(buf, at, have);
      if (!end) break;
      std::size_t off = 0;
      std::string why;
      if (!decode_game(std::span<const std::uint8_t>(buf.data() + at, end - at), off, game, why)) {
        std::fclose(f);
        return error = path + ": game " + std::to_string(games) + ": " + why, false;
      }
      if (games >= skip_games) visit(buf.data() + at, end - at, game);
      at = end;
      if (++games == max_games) {
        std::fclose(f);
        return true;
      }
    }
    if (at == 0 && have == buf.size()) {  // one game larger than the buffer: grow it
      buf.resize(buf.size() * 2);
      continue;
    }
    std::memmove(buf.data(), buf.data() + at, have - at);
    have -= at;
    if (eof) {
      truncated = have != 0;
      break;
    }
  }
  std::fclose(f);
  return true;
}

std::vector<std::vector<std::string>> read_list(const std::string& path) {
  std::vector<std::vector<std::string>> rows;
  std::ifstream in(path);
  std::string line;
  while (std::getline(in, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty() || line[0] == '#') continue;
    std::vector<std::string> cols;
    std::size_t at = 0;
    for (;;) {
      const std::size_t tab = line.find('\t', at);
      cols.push_back(line.substr(at, tab == std::string::npos ? std::string::npos : tab - at));
      if (tab == std::string::npos) break;
      at = tab + 1;
    }
    rows.push_back(cols);
  }
  return rows;
}

int run(int argc, char** argv) {
  if (argc != 4) {
    std::fprintf(stderr, "usage: fork_overlap_audit QUERIES.lst TRAIN.lst OUT_PREFIX\n");
    return 2;
  }
  init();
  KeyTable k1, k0;
  std::vector<QueryPosition> positions;
  std::vector<QueryGame> games;
  std::unordered_map<std::uint64_t, std::vector<std::uint32_t>> game_by_hash;
  std::unordered_map<std::uint64_t, std::vector<std::uint32_t>> game_by_start;  // K1 hash of a query game's start
  std::vector<std::string> set_names;
  Position pos;
  pos.reserve_plies(1024);

  for (const auto& row : read_list(argv[1])) {
    if (row.size() < 3) return std::fprintf(stderr, "bad query line\n"), 2;
    const int set = static_cast<int>(set_names.size());
    set_names.push_back(row[1]);
    std::string error;
    if (row[0] == "vf") {
      const long max_games = row.size() > 3 ? std::atol(row[3].c_str()) : 0;
      int item = 0;
      bool truncated = false;
      const bool ok = for_each_game(
          row[2],
          [&](const std::uint8_t* g, std::size_t bytes, const ReadGame& game) {
            pos.set_fen(game.start_fen);
            QueryGame qg{set, item, static_cast<int>(game.moves.size()), game_identity(g, bytes), 0};
            qg.start_key = k1.add(pos.key(), fen_fields(pos, 4));
            game_by_hash[fnv1a(qg.identity)].push_back(static_cast<std::uint32_t>(games.size()));
            game_by_start[pos.key()].push_back(static_cast<std::uint32_t>(games.size()));
            games.push_back(std::move(qg));
            int ply = 0;
            for (const ReadMove& rm : game.moves) {
              QueryPosition q{set, item, ply++, popcount(pos.pieces()), is_kept(pos, rm.move, rm.white_score) ? 1 : 0,
                              k1.add(pos.key(), fen_fields(pos, 4)), k0.add(key_k0(pos), fen_fields(pos, 2))};
              positions.push_back(q);
              pos.make(rm.move);
            }
            ++item;
          },
          error, truncated, max_games);
      if (!ok) return std::fprintf(stderr, "%s\n", error.c_str()), 1;
    } else if (row[0] == "fen") {
      std::ifstream in(row[2]);
      std::string line;
      int item = 0;
      while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        std::string why;
        if (!pos.set_fen(line, &why)) return std::fprintf(stderr, "bad FEN %s: %s\n", line.c_str(), why.c_str()), 1;
        positions.push_back({set, item++, -1, popcount(pos.pieces()), -1, k1.add(pos.key(), fen_fields(pos, 4)),
                             k0.add(key_k0(pos), fen_fields(pos, 2))});
      }
    } else {
      return std::fprintf(stderr, "bad query kind %s\n", row[0].c_str()), 2;
    }
    std::fprintf(stderr, "query set %s: %zu positions so far, %zu K1 keys, %zu games\n", row[1].c_str(),
                 positions.size(), k1.keys.size(), games.size());
  }

  const std::string prefix = argv[3];
  std::FILE* files_out = std::fopen((prefix + "-files.tsv").c_str(), "w");
  if (!files_out) return std::fprintf(stderr, "cannot write %s-files.tsv\n", prefix.c_str()), 1;
  std::fprintf(files_out,
               "group\tpath\tskip\tgames\tpositions\tsaved\tkept\thits_k1\thits_k0\thits_k1_kept\tidentical_games\t"
               "same_start_games\ttruncated\terror\n");
  std::vector<std::string> groups;
  int status = 0;
  for (const auto& row : read_list(argv[2])) {
    if (row.size() < 2) return std::fprintf(stderr, "bad train line\n"), 2;
    int group = static_cast<int>(std::find(groups.begin(), groups.end(), row[0]) - groups.begin());
    if (group == static_cast<int>(groups.size())) groups.push_back(row[0]);
    if (group >= 64) return std::fprintf(stderr, "more than 64 training groups\n"), 2;
    const std::uint64_t bit = std::uint64_t{1} << group;
    const long skip = row.size() > 2 ? std::atol(row[2].c_str()) : 0;
    unsigned long long n_games = 0, n_pos = 0, n_saved = 0, n_kept = 0, hits1 = 0, hits0 = 0, hits1k = 0, ident = 0,
                       same_start = 0;
    std::string error;
    bool truncated = false;
    const bool ok = for_each_game(
        row[1],
        [&](const std::uint8_t* g, std::size_t bytes, const ReadGame& game) {
          ++n_games;
          pos.set_fen(game.start_fen);
          if (auto it = game_by_start.find(pos.key()); it != game_by_start.end()) {
            const std::string start = fen_fields(pos, 4);
            for (std::uint32_t id : it->second)
              if (k1.keys[games[id].start_key].text == start) {
                ++games[id].same_start;
                games[id].start_mask |= bit;
                ++same_start;
              }
          }
          if (!game_by_hash.empty()) {
            const std::string identity = game_identity(g, bytes);
            if (auto it = game_by_hash.find(fnv1a(identity)); it != game_by_hash.end())
              for (std::uint32_t id : it->second)
                if (games[id].identity == identity) {
                  ++games[id].identical;
                  games[id].identical_mask |= bit;
                  ++ident;
                }
          }
          for (const ReadMove& rm : game.moves) {
            ++n_pos;
            const bool saved = rm.white_score != UnsavedRecordScore;
            const bool kept = is_kept(pos, rm.move, rm.white_score);
            n_saved += saved;
            n_kept += kept;
            if (auto* ids = k1.find(pos.key())) {
              const std::string text = fen_fields(pos, 4);
              for (std::uint32_t id : *ids)
                if (k1.keys[id].text == text) {
                  QueryKey& q = k1.keys[id];
                  q.any_mask |= bit;
                  if (kept) q.kept_mask |= bit;
                  if (q.train_any < 0xffffffffu) ++q.train_any;
                  if (kept && q.train_kept < 0xffffffffu) ++q.train_kept;
                  ++hits1;
                  hits1k += kept;
                }
            }
            if (auto* ids = k0.find(key_k0(pos))) {
              const std::string text = fen_fields(pos, 2);
              for (std::uint32_t id : *ids)
                if (k0.keys[id].text == text) {
                  QueryKey& q = k0.keys[id];
                  q.any_mask |= bit;
                  if (kept) q.kept_mask |= bit;
                  if (q.train_any < 0xffffffffu) ++q.train_any;
                  if (kept && q.train_kept < 0xffffffffu) ++q.train_kept;
                  ++hits0;
                }
            }
            pos.make(rm.move);
          }
        },
        error, truncated, 0, skip);
    if (!ok) status = 1;
    std::fprintf(files_out, "%s\t%s\t%ld\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%d\t%s\n", row[0].c_str(),
                 row[1].c_str(), skip, n_games, n_pos, n_saved, n_kept, hits1, hits0, hits1k, ident, same_start,
                 truncated ? 1 : 0, ok ? "" : error.c_str());
    std::fflush(files_out);
    std::fprintf(stderr, "%s %s: %llu games, %llu positions, %llu K1 hits%s\n", row[0].c_str(), row[1].c_str(),
                 n_games, n_pos, hits1, ok ? "" : (" ERROR " + error).c_str());
  }
  std::fclose(files_out);

  std::FILE* q_out = std::fopen((prefix + "-queries.tsv").c_str(), "w");
  std::FILE* g_out = std::fopen((prefix + "-games.tsv").c_str(), "w");
  if (!q_out || !g_out) return std::fprintf(stderr, "cannot write the outputs\n"), 1;
  std::fprintf(q_out, "set\titem\tply\tpieces\tkept\tk1_count\tk1_kept_count\tk1_mask\tk1_kept_mask\tk0_count\t"
                      "k0_mask\tfen4\n");
  for (const QueryPosition& q : positions) {
    const QueryKey& a = k1.keys[q.k1];
    const QueryKey& b = k0.keys[q.k0];
    std::fprintf(q_out, "%s\t%d\t%d\t%d\t%d\t%u\t%u\t%llx\t%llx\t%u\t%llx\t%s\n", set_names[q.set].c_str(),
                 q.item, q.ply, q.pieces, q.kept, a.train_any, a.train_kept,
                 static_cast<unsigned long long>(a.any_mask), static_cast<unsigned long long>(a.kept_mask),
                 b.train_any, static_cast<unsigned long long>(b.any_mask), a.text.c_str());
  }
  std::fprintf(g_out, "set\titem\tplies\tidentical_count\tidentical_mask\tstart_count\tstart_mask\tstart_fen4\n");
  for (const QueryGame& g : games)
    std::fprintf(g_out, "%s\t%d\t%d\t%u\t%llx\t%u\t%llx\t%s\n", set_names[g.set].c_str(), g.item, g.plies,
                 g.identical, static_cast<unsigned long long>(g.identical_mask), g.same_start,
                 static_cast<unsigned long long>(g.start_mask), k1.keys[g.start_key].text.c_str());
  std::FILE* gr_out = std::fopen((prefix + "-groups.tsv").c_str(), "w");
  if (!gr_out) return std::fprintf(stderr, "cannot write the outputs\n"), 1;
  std::fprintf(gr_out, "bit\tgroup\n");
  for (std::size_t k = 0; k < groups.size(); ++k) std::fprintf(gr_out, "%zu\t%s\n", k, groups[k].c_str());
  std::fclose(gr_out);
  std::fclose(q_out);
  std::fclose(g_out);
  return status;
}

}  // namespace
}  // namespace forkeng

int main(int argc, char** argv) { return forkeng::run(argc, argv); }
