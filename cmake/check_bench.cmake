# SPDX-License-Identifier: GPL-3.0-or-later
# Runs `fork <CMD>` (bench, the default, or perftbench) and compares its node
# count and signature with the committed reference.
# Usage: cmake -DFORK=<exe> [-DCMD=bench|perftbench] -DREF=<ref file> -P check_bench.cmake
if(NOT CMD)
  set(CMD bench)
endif()
execute_process(COMMAND ${FORK} ${CMD}
  OUTPUT_VARIABLE out ERROR_VARIABLE err RESULT_VARIABLE rc)
if(NOT rc EQUAL 0)
  message(FATAL_ERROR "fork ${CMD} failed (${rc}):\n${out}\n${err}")
endif()

string(REGEX MATCH "nodes ([0-9]+)" _ "${out}")
set(nodes "${CMAKE_MATCH_1}")
string(REGEX MATCH "signature ([0-9a-f]+)" _ "${out}")
set(sig "${CMAKE_MATCH_1}")

file(READ ${REF} ref)
string(REGEX MATCH "nodes ([0-9]+)" _ "${ref}")
set(ref_nodes "${CMAKE_MATCH_1}")
string(REGEX MATCH "signature ([0-9a-f]+)" _ "${ref}")
set(ref_sig "${CMAKE_MATCH_1}")

if(nodes STREQUAL "" OR NOT nodes STREQUAL ref_nodes OR NOT sig STREQUAL ref_sig)
  message(FATAL_ERROR "${CMD} mismatch: got nodes ${nodes} signature ${sig}, "
                      "expected nodes ${ref_nodes} signature ${ref_sig}\n${out}")
endif()
message(STATUS "${CMD} parity ok: nodes ${nodes} signature ${sig}")
