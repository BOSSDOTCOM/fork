# SPDX-License-Identifier: GPL-3.0-or-later
#
# The nnue_parity test on a synthetic network (DESIGN.md §5.3, deliverable 6):
# random float weights written as bullet's weights.bin and quantised.bin
# (tools/nnue/reference.py synthetic), converted to Fork's net file
# (convert.py), every Python leg of the parity test (reference.py legs: the
# quantization leg, R-float, the loss), and then Fork's own inference on
# this build's SIMD path against R-int, exactly (fork netcheck). With the
# first trained net, the same chain runs on bullet's real files.
#
#   cmake -DFORK=... -DPYTHON=... -DSOURCE_DIR=... -DWORK=... -P nnue_parity.cmake

file(REMOVE_RECURSE ${WORK})
file(MAKE_DIRECTORY ${WORK})
set(tools ${SOURCE_DIR}/tools/nnue)
foreach(step
    "synthetic --out ${WORK} --seed 7"
    "CONVERT"
    "legs --net ${WORK}/net.fnet --weights ${WORK}/weights.bin --quantised ${WORK}/quantised.bin --epd ${SOURCE_DIR}/tests/datagen_openings.epd --out ${WORK}/net.parity")
  if(step STREQUAL "CONVERT")
    set(cmd ${PYTHON} -I ${tools}/convert.py ${WORK}/quantised.bin ${WORK}/net.fnet --scale 400)
  else()
    separate_arguments(args UNIX_COMMAND "${step}")
    set(cmd ${PYTHON} -I ${tools}/reference.py ${args})
  endif()
  execute_process(COMMAND ${cmd} RESULT_VARIABLE rc OUTPUT_VARIABLE out ERROR_VARIABLE err)
  message(STATUS "${out}")
  if(NOT rc EQUAL 0)
    message(FATAL_ERROR "${cmd} failed (${rc}): ${err}")
  endif()
endforeach()

execute_process(COMMAND ${FORK} netcheck ${WORK}/net.parity ${WORK}/net.fnet
                RESULT_VARIABLE rc OUTPUT_VARIABLE out ERROR_VARIABLE err)
message(STATUS "${out}${err}")
if(NOT rc EQUAL 0)
  message(FATAL_ERROR "fork netcheck failed")
endif()
file(REMOVE_RECURSE ${WORK})
