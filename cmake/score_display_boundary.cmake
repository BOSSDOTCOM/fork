# SPDX-License-Identifier: GPL-3.0-or-later
# The CalibratedScore display stays at the UCI output boundary (owner,
# 2026-11-12): the calibrated score (src/uci/score_display.hpp) may be named
# only by that header and by the UCI session's info-line printer
# (src/uci/session.cpp). No search, evaluation, time-management, TT, tuning,
# data-generation, web or core file may reach it, so fork_datagen's output and
# every search are the same whatever the option says.
# Usage: cmake -DSOURCE_DIR=<repo> -P score_display_boundary.cmake
# Script mode sets no policies, so if(... IN_LIST ...) needs CMP0057 set here:
# without it CMake 3.22 (the TCEC toolchain's floor) refuses the operator
# (CI run 43417188774).
cmake_policy(SET CMP0057 NEW)
set(allowed "src/uci/score_display.hpp;src/uci/session.cpp")
set(tokens "score_display.hpp;calibrated_display_score;DisplayFittedScale;DisplayTargetScale;CalibratedScore")
file(GLOB_RECURSE sources RELATIVE ${SOURCE_DIR} ${SOURCE_DIR}/src/*.cpp ${SOURCE_DIR}/src/*.hpp
     ${SOURCE_DIR}/src/*.h ${SOURCE_DIR}/src/*.c)
set(bad "")
foreach(f ${sources})
  if(f IN_LIST allowed)
    continue()
  endif()
  file(READ ${SOURCE_DIR}/${f} text)
  foreach(t ${tokens})
    string(FIND "${text}" "${t}" at)
    if(NOT at EQUAL -1)
      list(APPEND bad "${f} names ${t}")
    endif()
  endforeach()
endforeach()
# The header itself includes nothing but the score bands.
file(STRINGS ${SOURCE_DIR}/src/uci/score_display.hpp includes REGEX "^#include \"")
if(NOT includes STREQUAL "#include \"search/score_bounds.hpp\"")
  list(APPEND bad "src/uci/score_display.hpp includes ${includes}")
endif()
# In the session, only the printers (InfoWriter's line and report_unfinished's)
# call the mapping, and the option is read once per go.
file(STRINGS ${SOURCE_DIR}/src/uci/session.cpp calls REGEX "calibrated_display_score\\(")
list(LENGTH calls n_calls)
if(NOT n_calls EQUAL 2)
  list(APPEND bad "src/uci/session.cpp calls calibrated_display_score ${n_calls} times (expected 2: the info line and the unfinished-search line)")
endif()
file(STRINGS ${SOURCE_DIR}/src/uci/session.cpp reads REGEX "options_\\.number\\(\"CalibratedScore\"\\)")
list(LENGTH reads n_reads)
if(NOT n_reads EQUAL 1)
  list(APPEND bad "src/uci/session.cpp reads CalibratedScore ${n_reads} times (expected 1, at go)")
endif()
if(bad)
  string(REPLACE ";" "\n  " bad "${bad}")
  message(FATAL_ERROR "the calibrated score left the UCI output boundary:\n  ${bad}")
endif()
list(LENGTH sources n)
message(STATUS "score display boundary ok: ${n} source files checked")
