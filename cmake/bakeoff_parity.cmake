# SPDX-License-Identifier: GPL-3.0-or-later
# bakeoff_parity: tools/nnue/reference_s512.py writes a random S-512 network
# and its R-int values into OUT; fork_tests bakeoff (with the folder in
# FORK_BAKEOFF_PARITY_DIR, set by the caller) checks Fork's S-512 inference
# against them exactly. Experiment branch (DESIGN.md §5 plan, step 4).
foreach(arch s512 h512)
  execute_process(COMMAND ${PY} -I ${SRC}/tools/nnue/reference_s512.py write ${OUT} --arch ${arch} RESULT_VARIABLE rc)
  if(NOT rc EQUAL 0)
    message(FATAL_ERROR "reference_s512.py --arch ${arch} failed")
  endif()
endforeach()
execute_process(COMMAND ${TESTS} bakeoff RESULT_VARIABLE rc OUTPUT_VARIABLE out ERROR_VARIABLE err)
message(STATUS "${out}${err}")
if(NOT rc EQUAL 0)
  message(FATAL_ERROR "fork_tests bakeoff failed")
endif()
