# SPDX-License-Identifier: GPL-3.0-or-later
#
# The datagen_verify test (DESIGN.md §5.3, deliverable 2): a short
# fork_datagen run with two workers, then the independent checker
# tools/datagen/verify_games.py over its shards and manifest; then the same
# run again, which must give byte-identical shards (reproducibility).
#
#   cmake -DDATAGEN=... -DPYTHON=... -DSOURCE_DIR=... -DWORK=... -DTABLES=... -P datagen_verify.cmake

file(REMOVE_RECURSE ${WORK})
file(MAKE_DIRECTORY ${WORK}/a ${WORK}/b)
foreach(dir a b)
  execute_process(
    COMMAND ${DATAGEN} --openings ${SOURCE_DIR}/tests/datagen_openings.epd --out ${WORK}/${dir}
            --positions 4000 --nodes 2000 --threads 2 --seed 7 --run t --hash-mb 2 --shard-mb 1
            --tables ${TABLES}
    RESULT_VARIABLE rc ERROR_VARIABLE err)
  if(NOT rc EQUAL 0)
    message(FATAL_ERROR "fork_datagen failed (${rc}): ${err}")
  endif()
endforeach()

file(GLOB shards ${WORK}/a/*.vf)
list(LENGTH shards n)
if(n LESS 2)
  message(FATAL_ERROR "expected a shard per worker, found ${n}")
endif()
execute_process(
  COMMAND ${PYTHON} -I ${SOURCE_DIR}/tools/datagen/verify_games.py ${shards} --manifest ${WORK}/a/t.json
  RESULT_VARIABLE rc OUTPUT_VARIABLE out ERROR_VARIABLE err)
message(STATUS "${out}")
if(NOT rc EQUAL 0)
  message(FATAL_ERROR "verify_games.py failed: ${err}")
endif()

foreach(shard ${shards})
  get_filename_component(name ${shard} NAME)
  file(SHA256 ${shard} ha)
  file(SHA256 ${WORK}/b/${name} hb)
  if(NOT ha STREQUAL hb)
    message(FATAL_ERROR "${name} differs between two runs with the same settings")
  endif()
endforeach()
file(REMOVE_RECURSE ${WORK})
