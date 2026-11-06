# SPDX-License-Identifier: GPL-3.0-or-later
# Two-stage profile-guided build driven by `fork bench`.
# Usage: cmake -DSOURCE_DIR=<repo> -DCXX=<compiler> -DCOMPILER_ID=<Clang|GNU>
#              [-DARCH=native] [-DNO_PEXT=OFF] -P pgo.cmake
# Both stages build in the same directory: GCC names .gcda files after the
# object paths, so the instrumented and optimized builds must share them.
if(NOT ARCH)
  set(ARCH native)
endif()
if(NOT NO_PEXT)
  set(NO_PEXT OFF)
endif()
if(COMPILER_ID STREQUAL "GNU")
  set(tag gcc)
else()
  set(tag clang)
endif()
set(dir ${SOURCE_DIR}/build/${tag}-pgo)
set(data ${dir}/profile)
file(REMOVE_RECURSE ${data})
file(MAKE_DIRECTORY ${data})

function(run)
  execute_process(COMMAND ${ARGN} RESULT_VARIABLE rc)
  if(NOT rc EQUAL 0)
    message(FATAL_ERROR "command failed (${rc}): ${ARGN}")
  endif()
endfunction()

function(configure stage use_data)
  # -U: the build folder is reused, and a cached evaluator or network must
  # not outlive a change of the default.
  run(${CMAKE_COMMAND} -S ${SOURCE_DIR} -B ${dir} -G Ninja -U FORK_EVALUATOR -U FORK_NET
      -DCMAKE_CXX_COMPILER=${CXX} -DCMAKE_BUILD_TYPE=Release
      -DFORK_ARCH=${ARCH} -DFORK_NO_PEXT=${NO_PEXT}
      -DFORK_BUILD_TESTS=OFF -DFORK_PGO=${stage} -DFORK_PGO_DATA=${use_data})
  run(${CMAKE_COMMAND} --build ${dir} --target fork --clean-first)
endfunction()

message(STATUS "PGO stage 1: instrumented build (${tag}, ${ARCH})")
configure(GEN ${data})
run(${dir}/fork bench)

if(tag STREQUAL "clang")
  get_filename_component(bindir ${CXX} DIRECTORY)
  find_program(PROFDATA llvm-profdata HINTS ${bindir} REQUIRED)
  file(GLOB raw ${data}/*.profraw)
  run(${PROFDATA} merge -output=${data}/fork.profdata ${raw})
  set(use ${data}/fork.profdata)
else()
  set(use ${data})
endif()

message(STATUS "PGO stage 2: optimized build")
configure(USE ${use})
# The bench reference belongs to the evaluator, as in CMakeLists.txt.
load_cache(${dir} READ_WITH_PREFIX pgo_ FORK_EVALUATOR FORK_NET)
if(pgo_FORK_EVALUATOR STREQUAL "bootstrap")
  set(bench_ref ${SOURCE_DIR}/tests/bench.ref)
else()
  get_filename_component(net_name ${pgo_FORK_NET} NAME_WE)
  set(bench_ref ${SOURCE_DIR}/tests/bench-${net_name}.ref)
endif()
execute_process(COMMAND ${CMAKE_COMMAND} -DFORK=${dir}/fork${CMAKE_EXECUTABLE_SUFFIX}
  -DREF=${bench_ref} -P ${SOURCE_DIR}/cmake/check_bench.cmake
  RESULT_VARIABLE rc)
if(NOT rc EQUAL 0)
  message(FATAL_ERROR "PGO binary failed bench parity")
endif()
message(STATUS "PGO binary: ${dir}/fork")
