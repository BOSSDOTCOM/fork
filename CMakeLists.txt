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
project(fork LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(FORK_ARCH "native" CACHE STRING "Target CPU: native, x86-64-v3, x86-64-v4")
option(FORK_NO_PEXT "Use magic multiplication even when BMI2 PEXT is available" OFF)
option(FORK_SANITIZE "Build with ASan + UBSan (where the toolchain supports it)" OFF)
option(FORK_LTO "Link-time optimization for optimized builds" ON)
option(FORK_BUILD_TESTS "Build the test executable and CTest tests" ON)
option(FORK_FUZZ "Build libFuzzer targets (clang only)" OFF)
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

add_executable(fork src/main.cpp)
target_link_libraries(fork PRIVATE forkcore fork_pgo)

add_executable(fork_magic_seeds tools/magic_seeds.cpp)
target_link_libraries(fork_magic_seeds PRIVATE forkcore)

add_executable(fork_dump_tables tools/dump_tables.cpp)
target_link_libraries(fork_dump_tables PRIVATE forkcore)

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
  foreach(target fuzz_fen fuzz_moves)
    add_executable(${target} fuzz/${target}.cpp)
    target_link_libraries(${target} PRIVATE forkcore)
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
    tests/test_draws.cpp)
  target_link_libraries(fork_tests PRIVATE forkcore)

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

  foreach(suite magics fen zobrist_ep draws perft_suite perft_mirror consistency pseudo_legal perft_edge perft_epd)
    add_test(NAME ${suite} COMMAND fork_tests ${suite})
  endforeach()
  if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    add_test(NAME perft_full COMMAND fork_tests perft_full)
    set_tests_properties(perft_full PROPERTIES LABELS slow)
  endif()
  foreach(suite perft_epd_deep perft_epd_full)
    add_test(NAME ${suite} COMMAND fork_tests ${suite})
    set_tests_properties(${suite} PROPERTIES LABELS slow)
  endforeach()

  add_executable(fork_alloc_test tests/alloc_test.cpp)
  target_link_libraries(fork_alloc_test PRIVATE forkcore)
  add_test(NAME no_alloc COMMAND fork_alloc_test)

  add_test(NAME bench_parity COMMAND ${CMAKE_COMMAND}
    -DFORK=$<TARGET_FILE:fork>
    -DREF=${CMAKE_SOURCE_DIR}/tests/bench.ref
    -P ${CMAKE_SOURCE_DIR}/cmake/check_bench.cmake)
endif()
