# SPDX-License-Identifier: GPL-3.0-or-later
# 3.22 is Ubuntu 22.04's CMake, which TCEC's servers run (DESIGN.md §5.1).
# CMakePresets.json needs 3.25 and is a developer convenience only; the TCEC
# build (update.sh) configures without presets.
cmake_minimum_required(VERSION 3.22)
# The presets pass $env{FORK_CLANG_CXX} / $env{FORK_GCC_CXX}, which are empty
# unless scripts/env.sh (or env.ps1) was sourced; say so instead of CMake's
# generic "no compiler found".
if(DEFINED CMAKE_CXX_COMPILER AND CMAKE_CXX_COMPILER STREQUAL "")
  message(FATAL_ERROR "CMAKE_CXX_COMPILER is empty: source scripts/env.sh (or scripts/env.ps1) "
                      "before using the presets, or pass -DCMAKE_CXX_COMPILER=<compiler>")
endif()
# The semver in `id name` (DESIGN.md §5.1): 0.<phase>.0 until the first release.
project(fork VERSION 0.3.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(FORK_ARCH "native" CACHE STRING "Target CPU: native, x86-64-v3, x86-64-v4")
option(FORK_NO_PEXT "Use magic multiplication even when BMI2 PEXT is available" OFF)
option(FORK_VNNI "Add AVX-512 VNNI to the target (with FORK_ARCH=x86-64-v4; the vnni presets)" OFF)
option(FORK_SANITIZE "Build with ASan + UBSan (where the toolchain supports it)" OFF)
option(FORK_TSAN "Build with ThreadSanitizer (Linux; not with FORK_SANITIZE)" OFF)
option(FORK_LTO "Link-time optimization for optimized builds" ON)
option(FORK_BUILD_TESTS "Build the test executable and CTest tests" ON)
option(FORK_FUZZ "Build libFuzzer targets (clang only)" OFF)
option(FORK_SEARCH_STATS "Debug counters in the search, printed by fork bench (never released)" OFF)
option(FORK_TUNE "Tuning build: every search switch is a UCI option (SPRT and SPSA only, never released)" OFF)
set(FORK_PGO "OFF" CACHE STRING "Profile-guided optimization stage: OFF, GEN, USE")
set(FORK_PGO_DATA "" CACHE PATH "Profile directory (GEN) or merged profile file / directory (USE)")

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

# -g: debug info in the optimized binary, as TCEC recommends (owner,
# 2026-10-24); it does not change the generated code.
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -g -DNDEBUG")
set(CMAKE_CXX_FLAGS_DEBUG "-O1 -g -fno-omit-frame-pointer -DFORK_DEBUG")

# Flags shared by every Fork target.
add_library(fork_flags INTERFACE)
target_compile_options(fork_flags INTERFACE
  -Wall -Wextra -Wpedantic -Wshadow -Werror -march=${FORK_ARCH})
if(FORK_VNNI)
  target_compile_options(fork_flags INTERFACE -mavx512vnni)
endif()
# A/B experiments (Part C): -DFORK_EXPERIMENT=NAME defines FORK_EXP_NAME.
set(FORK_EXPERIMENT "" CACHE STRING "Optimization experiment to enable (A/B builds only)")
if(FORK_EXPERIMENT)
  target_compile_definitions(fork_flags INTERFACE FORK_EXP_${FORK_EXPERIMENT})
endif()
if(FORK_NO_PEXT)
  target_compile_definitions(fork_flags INTERFACE FORK_NO_PEXT)
endif()
target_compile_definitions(fork_flags INTERFACE
  FORK_ARCH_NAME="${FORK_ARCH}" FORK_BUILD_TYPE="${CMAKE_BUILD_TYPE}")

set(fork_is_gcc_mingw FALSE)
if(MINGW AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  set(fork_is_gcc_mingw TRUE)
endif()

# MinGW GCC emits aligned 32-byte AVX moves (vmovdqa ymm) to stack slots that
# Windows x64 only aligns to 16 bytes, so they fault at random: seen
# 2026-10-24 as a crash in about half of all gcc-debug engine starts (fault
# at `vmovdqa %ymm0,-0x40(%rbp)` copying SessionConfig in uci_main), 0 of 50
# with this flag. The GNU as option "encode[s] aligned vector move as
# unaligned vector move" (binutils docs, i386 options; the local binutils is
# 2.47). UNVERIFIED: that this is GCC bug 54412, and which binutils release
# added the option (both sites refused automated fetches on 2026-10-24).
# Windows test builds only: TCEC builds on Linux.
if(fork_is_gcc_mingw)
  target_compile_options(fork_flags INTERFACE -Wa,-muse-unaligned-vector-move)
endif()

set(fork_sanitizing FALSE)
if(FORK_SANITIZE)
  if(fork_is_gcc_mingw)
    message(WARNING "MinGW GCC ships no sanitizer runtimes: building without ASan/UBSan")
  else()
    set(fork_sanitizing TRUE)
    target_compile_options(fork_flags INTERFACE
      -fsanitize=address,undefined -fno-sanitize-recover=undefined)
    target_link_options(fork_flags INTERFACE -fsanitize=address,undefined)
  endif()
endif()

# ThreadSanitizer for the UCI threads (DESIGN.md §5.1, test 4). Linux only:
# MinGW ships no TSan runtime. The no_alloc test is not built: its global
# operator new collides with TSan's (.claude/rules/testing.md).
if(FORK_TSAN)
  if(FORK_SANITIZE OR MINGW)
    message(FATAL_ERROR "FORK_TSAN needs Linux and cannot be combined with FORK_SANITIZE")
  endif()
  set(fork_sanitizing TRUE)
  target_compile_options(fork_flags INTERFACE -fsanitize=thread)
  target_link_options(fork_flags INTERFACE -fsanitize=thread)
endif()

# Self-contained Windows binaries (sanitizer runtimes need the DLL build).
if(MINGW AND NOT fork_sanitizing)
  target_link_options(fork_flags INTERFACE -static)
endif()

# LTO only where the toolchain can link it: clang without lld or the LLVMgold
# plugin (a plain `apt install clang-16` on Ubuntu 22.04) cannot. Bench is
# identical either way.
if(FORK_LTO AND NOT CMAKE_BUILD_TYPE STREQUAL "Debug")
  include(CheckIPOSupported)
  check_ipo_supported(RESULT fork_ipo_ok OUTPUT fork_ipo_log LANGUAGES CXX)
  if(fork_ipo_ok)
    set(CMAKE_INTERPROCEDURAL_OPTIMIZATION ON)
  else()
    message(WARNING "LTO not supported by this toolchain, building without it")
  endif()
endif()
# `fork version` reports whether LTO is on (audit-1, P-6).
target_compile_definitions(fork_flags INTERFACE FORK_LTO=$<BOOL:${CMAKE_INTERPROCEDURAL_OPTIMIZATION}>)

# PGO flags apply only to the engine (core + main), never to tests.
add_library(fork_pgo INTERFACE)
if(FORK_PGO STREQUAL "GEN")
  target_compile_options(fork_pgo INTERFACE -fprofile-generate=${FORK_PGO_DATA})
  target_link_options(fork_pgo INTERFACE -fprofile-generate=${FORK_PGO_DATA})
elseif(FORK_PGO STREQUAL "USE")
  if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    target_compile_options(fork_pgo INTERFACE
      -fprofile-use=${FORK_PGO_DATA} -fprofile-partial-training -Wno-missing-profile)
  else()
    target_compile_options(fork_pgo INTERFACE -fprofile-use=${FORK_PGO_DATA})
  endif()
  target_link_options(fork_pgo INTERFACE -fprofile-use=${FORK_PGO_DATA})
elseif(NOT FORK_PGO STREQUAL "OFF")
  message(FATAL_ERROR "FORK_PGO must be OFF, GEN or USE")
endif()

add_library(forkcore STATIC
  src/core/bitboard.cpp
  src/core/zobrist.cpp
  src/core/position.cpp
  src/core/movegen.cpp
  src/core/perft.cpp
  src/core/bench.cpp)
target_include_directories(forkcore PUBLIC src)
target_link_libraries(forkcore PUBLIC fork_flags PRIVATE fork_pgo)

# Syzygy tablebase probing (DESIGN.md §5.2, deliverable 7): the vendored
# Fathom library, jdart1/Fathom at c9c6fef0 (MIT; third_party/fathom, file
# SHA-256s and lineage in docs/ORIGINALITY.md). tbprobe.c is compiled as
# C++: <sys/mman.h> then provides POSIX_MADV_RANDOM and Fathom advises random
# access on every mapped table (TCEC asks 7-man users for MADV_RANDOM; KB
# tools.md §6), which a strict ISO C build silently skips. Fathom's own
# warnings stay in this target (-w), so Fork's -Werror stays on Fork's code;
# its header is clean under Fork's flags.
add_library(fathom STATIC third_party/fathom/src/tbprobe.c)
set_source_files_properties(third_party/fathom/src/tbprobe.c PROPERTIES LANGUAGE CXX)
target_include_directories(fathom SYSTEM PUBLIC third_party/fathom/src)
target_compile_definitions(fathom PUBLIC TB_NO_HELPER_API)
target_link_libraries(fathom PRIVATE fork_flags)
target_compile_options(fathom PRIVATE -w)

# The evaluator is chosen at build time (owner, 2026-10-24; DESIGN.md §5.2):
# no runtime interface and no indirect call in the search.
# nnue is the default since B0 passed its SPRT against the bootstrap
# evaluation (+486.85 +/- 32.07 Elo; DESIGN.md §5.3, deliverable 7; owner,
# 2026-10-29). The network is nets/b0r2.fnet, B0's shape trained on
# generation 1 (the bake-off's B0 control), since it passed its SPRT against
# B0r1 (+235.45 +/- 16.04 Elo, 2026-10-30; docs/nets.md). nets/b0r1.fnet and
# nets/b0.fnet stay buildable with FORK_NET (tests/bench-b0r1.ref,
# tests/bench-b0.ref), and so does bootstrap (tests/bench.ref).
set(FORK_EVALUATOR "nnue" CACHE STRING "Static evaluation built into Fork: bootstrap or nnue")
set_property(CACHE FORK_EVALUATOR PROPERTY STRINGS bootstrap nnue)
set(FORK_NET "${CMAKE_SOURCE_DIR}/nets/b0r2.fnet" CACHE FILEPATH "Network compiled in with FORK_EVALUATOR=nnue")
if(FORK_EVALUATOR STREQUAL "nnue")
  if(NOT EXISTS ${FORK_NET})
    message(FATAL_ERROR "FORK_EVALUATOR=nnue needs the network file FORK_NET (${FORK_NET})")
  endif()
  # The inference is compiled for the embedded network's architecture
  # (src/eval/nnue/net_shape.hpp): its id is the header's u32 at byte 12.
  file(READ ${FORK_NET} fork_net_arch_hex OFFSET 12 LIMIT 4 HEX)
  string(SUBSTRING "${fork_net_arch_hex}" 0 2 fork_net_arch_byte)
  math(EXPR FORK_NET_ARCH "0x${fork_net_arch_byte}")
  set(fork_net_source ${CMAKE_BINARY_DIR}/generated/embedded_net_data.cpp)
  add_custom_command(OUTPUT ${fork_net_source}
    COMMAND ${CMAKE_COMMAND} -DNET=${FORK_NET} -DOUT=${fork_net_source} -P ${CMAKE_SOURCE_DIR}/cmake/embed_net.cmake
    DEPENDS ${FORK_NET} ${CMAKE_SOURCE_DIR}/cmake/embed_net.cmake
    COMMENT "Embedding the network ${FORK_NET}")
elseif(NOT FORK_EVALUATOR STREQUAL "bootstrap")
  message(FATAL_ERROR "FORK_EVALUATOR must be bootstrap or nnue")
else()
  set(FORK_NET_ARCH 1)
endif()

# Evaluation and search (src/eval/, src/search/ except the hash memory).
add_library(forksearch STATIC
  src/eval/bootstrap_eval.cpp
  src/search/search_bench.cpp
  src/search/endgame_tables.cpp
  src/search/hash_memory.cpp
  src/search/move_selector.cpp
  src/search/searcher.cpp
  src/search/see.cpp
  src/search/time_budget.cpp
  src/search/trans_table.cpp
  src/tune/params.cpp)
if(FORK_EVALUATOR STREQUAL "nnue")
  target_sources(forksearch PRIVATE src/eval/nnue/embedded_net.cpp ${fork_net_source})
  target_compile_definitions(forksearch PUBLIC FORK_EVAL_NNUE)
  target_link_libraries(forksearch PUBLIC forknnue)
else()
  target_compile_definitions(forksearch PUBLIC FORK_EVAL_BOOTSTRAP)
endif()
find_package(Threads REQUIRED)
target_link_libraries(forksearch PUBLIC forkcore fathom Threads::Threads PRIVATE fork_pgo)
if(FORK_SEARCH_STATS)
  target_compile_definitions(forksearch PUBLIC FORK_SEARCH_STATS)
endif()

# The UCI front end (src/uci/): protocol loop, options, info output.
add_library(forkuci STATIC
  src/uci/go_limits.cpp
  src/uci/options.cpp
  src/uci/output.cpp
  src/uci/session.cpp
  src/uci/version.cpp)
target_link_libraries(forkuci PUBLIC forksearch Threads::Threads PRIVATE fork_pgo)
# B0's inference (src/eval/nnue/; DESIGN.md §5.3, deliverable 5): built and
# tested in every configuration; the search uses it only with
# FORK_EVALUATOR=nnue.
add_library(forknnue STATIC
  src/eval/nnue/accumulator.cpp
  src/eval/nnue/net_file.cpp)
target_compile_definitions(forknnue PUBLIC FORK_NET_ARCH=${FORK_NET_ARCH})
target_link_libraries(forknnue PUBLIC forkcore PRIVATE fork_pgo)

# Self-play training data (src/datagen/; DESIGN.md §5.3, deliverable 2): the
# game format and the game player, shared by fork_datagen, the tests and a
# fuzz target. fork_datagen is never part of the engine binary TCEC builds.
add_library(forkdatagen STATIC
  src/datagen/game_record.cpp
  src/datagen/self_play.cpp)
target_link_libraries(forkdatagen PUBLIC forksearch PRIVATE fork_pgo)
add_executable(fork_datagen src/datagen/datagen_main.cpp)
target_link_libraries(fork_datagen PRIVATE forkdatagen forkuci)
target_compile_definitions(fork_datagen PRIVATE FORK_EVALUATOR_NAME="${FORK_EVALUATOR}")

if(FORK_TUNE)
  # Public on the search library, so the search, the UCI session and the tests
  # all see the same parameter declarations (src/tune/params.hpp).
  target_compile_definitions(forksearch PUBLIC FORK_TUNE)
endif()

# Version string `<semver>-dev+<short commit>`, read from git at configure
# time (owner, 2026-10-24); without git, or outside a checkout (a tarball),
# just `<semver>-dev`. Only version.cpp sees it, so a new commit hash
# recompiles one file.
set(fork_version "${PROJECT_VERSION}-dev")
find_package(Git QUIET)
if(GIT_FOUND AND EXISTS ${CMAKE_SOURCE_DIR}/.git)
  execute_process(COMMAND ${GIT_EXECUTABLE} rev-parse --short=7 HEAD
                  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
                  OUTPUT_VARIABLE fork_commit OUTPUT_STRIP_TRAILING_WHITESPACE
                  RESULT_VARIABLE fork_commit_failed ERROR_QUIET)
  if(NOT fork_commit_failed AND fork_commit MATCHES "^[0-9a-f]+$")
    string(APPEND fork_version "+${fork_commit}")
  endif()
endif()
message(STATUS "Fork version ${fork_version}")
set_source_files_properties(src/uci/version.cpp PROPERTIES COMPILE_DEFINITIONS "FORK_VERSION=\"${fork_version}\"")

add_executable(fork src/main.cpp)
target_link_libraries(fork PRIVATE forkuci forknnue fork_pgo)
# `fork version` names the evaluator and, for nnue, the network (its file's
# stem): the SPRT tools use it for the game gate (tools/cloud/build_pair.sh).
get_filename_component(fork_net_stem_for_version ${FORK_NET} NAME_WE)
target_compile_definitions(fork PRIVATE FORK_EVALUATOR_NAME="${FORK_EVALUATOR}"
                                        FORK_NET_NAME="${fork_net_stem_for_version}")
# fork_datagen's run manifest names the labelling network the same way, so
# data labelled by different nets stays apart (owner, 2026-10-30).
target_compile_definitions(fork_datagen PRIVATE FORK_NET_NAME="${fork_net_stem_for_version}")

add_executable(fork_magic_seeds tools/magic_seeds.cpp)
target_link_libraries(fork_magic_seeds PRIVATE forkcore)

add_executable(fork_dump_tables tools/dump_tables.cpp)
target_link_libraries(fork_dump_tables PRIVATE forkcore)

# Hash allocation and clear timing per worker count (DESIGN.md §5.1, test 2).
add_executable(fork_hash_timing tools/hash_timing.cpp)
target_link_libraries(fork_hash_timing PRIVATE forkuci)

add_executable(fork_micro bench/micro.cpp)
target_link_libraries(fork_micro PRIVATE forkcore)
# fork_micro reports its variant and commit so bench/ab.py can verify that it
# compares the binaries it was told to (see cmake/build_id.cmake).
set(FORK_BUILD_LABEL "" CACHE STRING "Variant name embedded in fork_micro (default: FORK_EXPERIMENT, else 'baseline')")
if(FORK_BUILD_LABEL)
  set(fork_variant ${FORK_BUILD_LABEL})
elseif(FORK_EXPERIMENT)
  set(fork_variant ${FORK_EXPERIMENT})
else()
  set(fork_variant baseline)
endif()
add_custom_target(fork_build_id
  COMMAND ${CMAKE_COMMAND} -DSOURCE_DIR=${CMAKE_SOURCE_DIR}
    -DOUTPUT=${CMAKE_BINARY_DIR}/generated/build_id.hpp -DVARIANT=${fork_variant}
    -P ${CMAKE_SOURCE_DIR}/cmake/build_id.cmake
  BYPRODUCTS ${CMAKE_BINARY_DIR}/generated/build_id.hpp
  VERBATIM)
add_dependencies(fork_micro fork_build_id)
target_include_directories(fork_micro PRIVATE ${CMAKE_BINARY_DIR}/generated)
# `fork version` reports the same identity, for bench/ab_search.py.
add_dependencies(fork fork_build_id)
target_include_directories(fork PRIVATE ${CMAKE_BINARY_DIR}/generated)

if(FORK_FUZZ)
  # Coverage instrumentation for everything (engine code included), libFuzzer
  # driver only in the fuzz executables. The clang driver rejects
  # -fsanitize=fuzzer for MinGW targets, so there the same instrumentation and
  # the shipped libFuzzer runtime are wired up by hand.
  if(MINGW)
    execute_process(COMMAND ${CMAKE_CXX_COMPILER} -print-resource-dir
                    OUTPUT_VARIABLE resource_dir OUTPUT_STRIP_TRAILING_WHITESPACE)
    set(fuzz_runtime ${resource_dir}/lib/windows/libclang_rt.fuzzer-x86_64.a)
    target_compile_options(fork_flags INTERFACE
      -fsanitize-coverage=inline-8bit-counters,pc-table,trace-cmp)
  else()
    target_compile_options(fork_flags INTERFACE -fsanitize=fuzzer-no-link)
  endif()
  foreach(target fuzz_fen fuzz_moves fuzz_uci fuzz_game_record)
    add_executable(${target} fuzz/${target}.cpp)
    target_link_libraries(${target} PRIVATE forkuci forkdatagen)
    target_include_directories(${target} PRIVATE ${CMAKE_SOURCE_DIR}/tests)  # uci_message.hpp
    if(MINGW)
      target_link_libraries(${target} PRIVATE ${fuzz_runtime})
    else()
      target_link_options(${target} PRIVATE -fsanitize=fuzzer)
    endif()
  endforeach()
endif()

# `pgo` target: two-stage profile-guided build driven by `fork bench`.
add_custom_target(pgo
  COMMAND ${CMAKE_COMMAND}
    -DSOURCE_DIR=${CMAKE_SOURCE_DIR}
    -DCXX=${CMAKE_CXX_COMPILER}
    -DCOMPILER_ID=${CMAKE_CXX_COMPILER_ID}
    -DARCH=${FORK_ARCH}
    -DNO_PEXT=${FORK_NO_PEXT}
    -P ${CMAKE_SOURCE_DIR}/cmake/pgo.cmake
  USES_TERMINAL
  COMMENT "Profile-guided build in ${CMAKE_SOURCE_DIR}/build/<compiler>-pgo")

if(FORK_BUILD_TESTS)
  enable_testing()
  add_executable(fork_tests
    tests/main.cpp
    tests/test_magics.cpp
    tests/test_fen.cpp
    tests/test_perft.cpp
    tests/test_consistency.cpp
    tests/test_epd.cpp
    tests/test_draws.cpp
    tests/test_eval.cpp
    tests/test_search.cpp
    tests/test_see.cpp
    tests/test_tt.cpp
    tests/test_ordering.cpp
    tests/test_pruning.cpp
    tests/test_endgame_tables.cpp
    tests/test_pruning_review.cpp
    tests/test_ordering_review.cpp
    tests/engine_process.cpp
    tests/test_uci.cpp
    tests/test_options.cpp
    tests/test_params.cpp
    tests/test_datagen.cpp
    tests/test_nnue.cpp)
  target_link_libraries(fork_tests PRIVATE forkuci forkdatagen forknnue)
  # The UCI suites drive the real engine binary over pipes.
  add_dependencies(fork_tests fork)
  target_compile_definitions(fork_tests PRIVATE FORK_EXE_PATH="$<TARGET_FILE:fork>")

  # Public perft suites: downloaded once into .cache/ (not committed, see
  # docs/ORIGINALITY.md) and pinned by SHA-256. A failed download leaves the
  # perft_epd tests failing loudly rather than skipped.
  set(FORK_EPD_DIR ${CMAKE_SOURCE_DIR}/.cache/epd)
  foreach(spec
      "perftsuite.epd|http://web.archive.org/web/20071202022713id_/http://hem.passagen.se/maragor/perftsuite.epd|363e5205dfff3205fc50b376fb1770f9156464456282372c8c0a0e5b45a0bf07"
      "perft-random.epd|https://web.archive.org/web/20201107005611id_/https://marcelk.net/rookie/nostalgia/v3/perft-random.epd|8f7aee8acaa2a988cc117befceb7c0d8d3304fa5749861d561ba95fceb1fecdd")
    string(REPLACE "|" ";" parts "${spec}")
    list(GET parts 0 epd_name)
    list(GET parts 1 epd_url)
    list(GET parts 2 epd_hash)
    set(epd_file ${FORK_EPD_DIR}/${epd_name})
    if(EXISTS ${epd_file})
      file(SHA256 ${epd_file} have)
      if(NOT have STREQUAL epd_hash)
        file(REMOVE ${epd_file})
      endif()
    endif()
    if(NOT EXISTS ${epd_file})
      # Timeouts so a stalled server cannot hang a plain configure.
      file(DOWNLOAD ${epd_url} ${epd_file} STATUS st TIMEOUT 600 INACTIVITY_TIMEOUT 60)
      list(GET st 0 code)
      set(have "")
      if(code EQUAL 0)
        file(SHA256 ${epd_file} have)
      endif()
      if(NOT have STREQUAL epd_hash)
        file(REMOVE ${epd_file})
        message(WARNING "could not download ${epd_name} with the pinned SHA-256 (${st}); perft_epd tests will fail")
      endif()
    endif()
  endforeach()
  target_compile_definitions(fork_tests PRIVATE FORK_EPD_DIR="${FORK_EPD_DIR}")

  # The smallest 7-man Syzygy pair, KPPPPPvK (deliverable 7's 7-piece test;
  # KB tools.md §6.9): downloaded once into .cache/ and pinned by SHA-256,
  # never committed. A failed download makes those cases fail loudly
  # (tests/test_endgame_tables.cpp: a missing file is a failure, not a skip).
  set(FORK_SYZYGY7_DIR ${CMAKE_SOURCE_DIR}/.cache/syzygy7)
  foreach(spec
      "KPPPPPvK.rtbw|https://tablebase.lichess.ovh/tables/standard/7/6v1_pawnful/KPPPPPvK.rtbw|f2e587b1acd940ef836ea80e0c64eb6093255b8273e1f8b049ab8f9f2631cc0b"
      "KPPPPPvK.rtbz|https://tablebase.lichess.ovh/tables/standard/7/6v1_pawnful/KPPPPPvK.rtbz|397a03d6d11823b2ead174c14f0c9e0a9be54c5b4b30890715a36d5fd1c16519")
    string(REPLACE "|" ";" parts "${spec}")
    list(GET parts 0 tb_name)
    list(GET parts 1 tb_url)
    list(GET parts 2 tb_hash)
    set(tb_file ${FORK_SYZYGY7_DIR}/${tb_name})
    if(EXISTS ${tb_file})
      file(SHA256 ${tb_file} have)
      if(NOT have STREQUAL tb_hash)
        file(REMOVE ${tb_file})
      endif()
    endif()
    if(NOT EXISTS ${tb_file})
      file(DOWNLOAD ${tb_url} ${tb_file} STATUS st TIMEOUT 600 INACTIVITY_TIMEOUT 60)
      list(GET st 0 code)
      set(have "")
      if(code EQUAL 0)
        file(SHA256 ${tb_file} have)
      endif()
      if(NOT have STREQUAL tb_hash)
        file(REMOVE ${tb_file})
        message(WARNING "could not download ${tb_name} with the pinned SHA-256 (${st}); the 7-piece tests will fail")
      endif()
    endif()
  endforeach()
  target_compile_definitions(fork_tests PRIVATE FORK_SYZYGY7_DIR="${FORK_SYZYGY7_DIR}")

  # Small 3-4-5 Syzygy tables (audit-1 Q-6): draws, a promotion, a cursed
  # win and a blessed loss (KNNvKP, WDL only, with the tables its captures
  # reach), KQvKP (WDL), and the 3-man tables with their DTZ files for root
  # ranking. From the lichess mirror's 3-4-5-wdl/ and 3-4-5-dtz/, pinned by
  # the SHA-256s of the mirror's own list (https://tablebase.lichess.ovh/
  # tables/standard/sha256; the list's SHA-256, 6dc75697...a783, is the one
  # the KB records, tools.md §6), downloaded and checked 2026-10-27:
  # 13,962,656 bytes in all, 13,729,360 of them KNNvKP.rtbw. Never
  # committed. A failed download makes the table tests fail.
  set(FORK_SYZYGY345_DIR ${CMAKE_SOURCE_DIR}/.cache/syzygy345)
  set(syzygy345_url https://tablebase.lichess.ovh/tables/standard)
  foreach(spec
      "KPvK.rtbw|3-4-5-wdl|02fd2bdcd92821c869458f019f63524def1c9e7a2862ca8d2b16dc7712b16183"
      "KQvK.rtbw|3-4-5-wdl|517667dff787162dbb1ed9d5d6484d30ee854e686ee0675c08d99ecf045d2d50"
      "KRvK.rtbw|3-4-5-wdl|386fbde73308e49a4207836922c68b30b664e83c5a37f7fa37305a15cd16f2f1"
      "KBvK.rtbw|3-4-5-wdl|bc0d8ab3560de9038460f0e8f61e3b7efd3e3d0327d19ae0387c0da7ddeb244d"
      "KNvK.rtbw|3-4-5-wdl|9d3518b12df3d2006441df758bce31e961346e70a11920aaad75c647003bb6e7"
      "KQvKP.rtbw|3-4-5-wdl|2f92788170e8a5c05608f44a47fd42f3f4fff372d0af64633c56bd081039d8f9"
      "KNNvKP.rtbw|3-4-5-wdl|ffee4c066be8d25d148a61bfce3bd317bfe2a592a979147cfbe698aeee06a668"
      "KNNvK.rtbw|3-4-5-wdl|8b5195abd7f1d4be7aa4b4dca669e9075d61d1c6b02dec8b71f5e9ea21d9eced"
      "KNvKP.rtbw|3-4-5-wdl|f21332cc4b380764847d6c32511dee16cbf56e65604596ca24e784f8e4c13bdb"
      "KPvK.rtbz|3-4-5-dtz|ad01af2076183c90ccee662ca6c5d74da3222ff1fee47c01b5d4e56ed01938de"
      "KQvK.rtbz|3-4-5-dtz|71ea9444fa5bd42897d781a0c356975ea6f23e0f65a4254e470897031c161c8c"
      "KRvK.rtbz|3-4-5-dtz|cab59f42e75c2a25da3939231850a79fa838593fff5c28d7772da92062ed965a"
      "KBvK.rtbz|3-4-5-dtz|6246c8a5c643eec9d4758d55ed843e31cc28a9b82a6f630c1c950d8b7755975b"
      "KNvK.rtbz|3-4-5-dtz|0e49a0f2810a131c32fc14872e83044aa9810ce2c86df071851512077291fc25")
    string(REPLACE "|" ";" parts "${spec}")
    list(GET parts 0 tb_name)
    list(GET parts 1 tb_dir)
    list(GET parts 2 tb_hash)
    set(tb_file ${FORK_SYZYGY345_DIR}/${tb_name})
    if(EXISTS ${tb_file})
      file(SHA256 ${tb_file} have)
      if(NOT have STREQUAL tb_hash)
        file(REMOVE ${tb_file})
      endif()
    endif()
    if(NOT EXISTS ${tb_file})
      file(DOWNLOAD ${syzygy345_url}/${tb_dir}/${tb_name} ${tb_file} STATUS st TIMEOUT 600 INACTIVITY_TIMEOUT 60)
      list(GET st 0 code)
      set(have "")
      if(code EQUAL 0)
        file(SHA256 ${tb_file} have)
      endif()
      if(NOT have STREQUAL tb_hash)
        file(REMOVE ${tb_file})
        message(WARNING "could not download ${tb_name} with the pinned SHA-256 (${st}); the 3-4-5 table tests will fail")
      endif()
    endif()
  endforeach()
  target_compile_definitions(fork_tests PRIVATE FORK_SYZYGY345_DIR="${FORK_SYZYGY345_DIR}")

  foreach(suite magics fen zobrist_ep draws eval perft_suite perft_mirror consistency pseudo_legal perft_edge perft_epd
                search see ordering pruning tables time_budget tt params uci_protocol uci_options uci_timing datagen nnue)
    add_test(NAME ${suite} COMMAND fork_tests ${suite})
    set_tests_properties(${suite} PROPERTIES SKIP_RETURN_CODE 77)  # a skipped case (tests/harness.hpp)
  endforeach()
  # Timing tests run alone, never beside another test (owner, 2026-10-26).
  set_tests_properties(uci_timing PROPERTIES RUN_SERIAL TRUE)
  if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    add_test(NAME perft_full COMMAND fork_tests perft_full)
    set_tests_properties(perft_full PROPERTIES LABELS slow)
  endif()
  foreach(suite perft_epd_deep perft_epd_full)
    add_test(NAME ${suite} COMMAND fork_tests ${suite})
    set_tests_properties(${suite} PROPERTIES LABELS slow)
  endforeach()

  if(NOT FORK_TSAN)
    add_executable(fork_alloc_test tests/alloc_test.cpp)
    target_link_libraries(fork_alloc_test PRIVATE forksearch)
    add_test(NAME no_alloc COMMAND fork_alloc_test)
    # One failed allocation during go still gives exactly one real bestmove
    # (review, 2026-10-24). Replaces operator new too, so the same exclusions.
    add_executable(fork_uci_oom_test tests/uci_oom_test.cpp)
    target_link_libraries(fork_uci_oom_test PRIVATE forkuci)
    add_test(NAME uci_oom COMMAND fork_uci_oom_test)
    # Review test (Phase 3 deliverable 3): TT dangling after a throwing Hash resize.
    add_executable(fork_uci_hash_oom_test tests/uci_hash_oom_test.cpp)
    target_link_libraries(fork_uci_hash_oom_test PRIVATE forkuci)
    add_test(NAME uci_hash_oom COMMAND fork_uci_hash_oom_test)
  endif()

  # A short differential run against python-chess (tools/difftest; audit-1
  # Q-10: make, the fifty-move clock, repetitions and insufficient material,
  # which only manual runs checked). Registered only where a Python with
  # python-chess is at hand: FORK_TEST_PYTHON, by default the repository's
  # .venv if it exists. CI, TCEC and the check's Linux copies have no .venv
  # (it is not tracked), so there the test does not exist. Label "python".
  set(FORK_TEST_PYTHON "" CACHE FILEPATH "Python with python-chess for the difftest_short test (default: .venv)")
  set(test_python ${FORK_TEST_PYTHON})
  foreach(candidate ${CMAKE_SOURCE_DIR}/.venv/Scripts/python.exe ${CMAKE_SOURCE_DIR}/.venv/bin/python)
    if(NOT test_python AND EXISTS ${candidate})
      set(test_python ${candidate})
    endif()
  endforeach()
  if(test_python)
    add_test(NAME difftest_short
             COMMAND ${test_python} -I ${CMAKE_SOURCE_DIR}/tools/difftest/difftest.py
                     --fork $<TARGET_FILE:fork> --positions 20000 --workers 2)
    set_tests_properties(difftest_short PROPERTIES LABELS python)
    # fork_datagen's shards against an independent decoder and python-chess,
    # and a second run for byte-identical output (DESIGN.md §5.3); its
    # manifest must name the labelling evaluator (and network).
    set(fork_datagen_evaluator ${FORK_EVALUATOR})
    if(FORK_EVALUATOR STREQUAL "nnue")
      set(fork_datagen_evaluator "nnue (${fork_net_stem_for_version})")
    endif()
    add_test(NAME datagen_verify COMMAND ${CMAKE_COMMAND}
      -DDATAGEN=$<TARGET_FILE:fork_datagen> -DPYTHON=${test_python} -DSOURCE_DIR=${CMAKE_SOURCE_DIR}
      -DWORK=${CMAKE_BINARY_DIR}/datagen_verify -DTABLES=${FORK_SYZYGY345_DIR}
      "-DEVALUATOR=${fork_datagen_evaluator}"
      -P ${CMAKE_SOURCE_DIR}/cmake/datagen_verify.cmake)
    set_tests_properties(datagen_verify PROPERTIES LABELS python)
    # The trainer-engine parity chain on a synthetic net, ending in Fork's own
    # inference on this build's SIMD path (DESIGN.md §5.3, deliverable 6).
    # The synthetic net is a B0 file: builds for another architecture check
    # their embedded network instead (nnue_netcheck_embedded).
    if(FORK_NET_ARCH EQUAL 1)
      add_test(NAME nnue_parity COMMAND ${CMAKE_COMMAND}
        -DFORK=$<TARGET_FILE:fork> -DPYTHON=${test_python} -DSOURCE_DIR=${CMAKE_SOURCE_DIR}
        -DWORK=${CMAKE_BINARY_DIR}/nnue_parity -P ${CMAKE_SOURCE_DIR}/cmake/nnue_parity.cmake)
      set_tests_properties(nnue_parity PROPERTIES LABELS python)
    endif()
  endif()

  # The search bench (`fork bench`) and, so move generation stays tied across
  # builds too, the Phase 1 perft workload (`fork perftbench`).
  # The search bench's reference belongs to the evaluator: tests/bench.ref for
  # the bootstrap evaluation, tests/bench-<net>.ref for a network once one is
  # adopted (DESIGN.md §5.3, deliverable 7). An nnue build of a test network
  # with no reference has no bench_parity test.
  get_filename_component(fork_net_name ${FORK_NET} NAME_WE)
  if(FORK_EVALUATOR STREQUAL "bootstrap")
    set(fork_bench_ref ${CMAKE_SOURCE_DIR}/tests/bench.ref)
  else()
    set(fork_bench_ref ${CMAKE_SOURCE_DIR}/tests/bench-${fork_net_name}.ref)
  endif()
  if(EXISTS ${fork_bench_ref})
    add_test(NAME bench_parity COMMAND ${CMAKE_COMMAND}
      -DFORK=$<TARGET_FILE:fork> -DCMD=bench
      -DREF=${fork_bench_ref}
      -P ${CMAKE_SOURCE_DIR}/cmake/check_bench.cmake)
  endif()
  add_test(NAME perft_bench_parity COMMAND ${CMAKE_COMMAND}
    -DFORK=$<TARGET_FILE:fork> -DCMD=perftbench
    -DREF=${CMAKE_SOURCE_DIR}/tests/perft_bench.ref
    -P ${CMAKE_SOURCE_DIR}/cmake/check_bench.cmake)

  # The network parity gate on this build's SIMD path: Fork's inference must
  # give exactly the reference's R-int values for the committed synthetic net
  # (tests/nnue/synthetic.*, from tools/nnue/reference.py synthetic --seed 7;
  # DESIGN.md §5.3, deliverable 6). Needs no Python, so every preset runs it.
  if(FORK_NET_ARCH EQUAL 1)
    add_test(NAME nnue_netcheck COMMAND fork netcheck ${CMAKE_SOURCE_DIR}/tests/nnue/synthetic.parity
                                                       ${CMAKE_SOURCE_DIR}/tests/nnue/synthetic.fnet)
  endif()
  # An nnue build checks its own embedded network against the parity file
  # named after it (tests/nnue/<net>.parity), the gate games run behind.
  if(FORK_EVALUATOR STREQUAL "nnue")
    get_filename_component(fork_net_stem ${FORK_NET} NAME_WE)
    add_test(NAME nnue_netcheck_embedded COMMAND fork netcheck ${CMAKE_SOURCE_DIR}/tests/nnue/${fork_net_stem}.parity)
  endif()

  # `fork version` says whether this build has LTO (audit-1, P-6).
  add_test(NAME version_lto COMMAND fork version)
  if(CMAKE_INTERPROCEDURAL_OPTIMIZATION)
    set_tests_properties(version_lto PROPERTIES PASS_REGULAR_EXPRESSION "\nlto on[\r\n]")
  else()
    set_tests_properties(version_lto PROPERTIES PASS_REGULAR_EXPRESSION "\nlto off[\r\n]")
  endif()
endif()
