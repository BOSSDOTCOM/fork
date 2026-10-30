# SPDX-License-Identifier: GPL-3.0-or-later
#
# The datagen_verify test (DESIGN.md §5.3, deliverable 2): a short
# fork_datagen run with two workers, then the independent checker
# tools/datagen/verify_games.py over its shards and manifest; then the same
# run again, which must give byte-identical shards (reproducibility).
#
#   cmake -DDATAGEN=... -DPYTHON=... -DSOURCE_DIR=... -DWORK=... -DTABLES=... -DEVALUATOR=... -P datagen_verify.cmake

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

# The run manifest names the labelling evaluator, and for nnue the network,
# so data from different nets stays apart (owner, 2026-10-30).
file(READ ${WORK}/a/t.json manifest)
string(FIND "${manifest}" "\"evaluator\": \"${EVALUATOR}\"" at)
if(at EQUAL -1)
  message(FATAL_ERROR "the run manifest does not name the evaluator \"${EVALUATOR}\"")
endif()

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

# The score adjudication (off above): a run with it on, checked by the
# independent rule in verify_games.py, which must also reject the shards
# under a shorter run length (so the check can fail).
file(MAKE_DIRECTORY ${WORK}/adj)
execute_process(
  COMMAND ${DATAGEN} --openings ${SOURCE_DIR}/tests/datagen_openings.epd --out ${WORK}/adj
          --positions 4000 --nodes 2000 --threads 2 --seed 7 --run t --hash-mb 2 --shard-mb 1
          --tables ${TABLES} --adjudicate-cp 300 --adjudicate-plies 4
  RESULT_VARIABLE rc ERROR_VARIABLE err)
if(NOT rc EQUAL 0)
  message(FATAL_ERROR "fork_datagen with score adjudication failed (${rc}): ${err}")
endif()
file(READ ${WORK}/adj/t.json manifest)
string(FIND "${manifest}" "\"adjudicate_cp\": 300, \"adjudicate_plies\": 4" at)
string(REGEX MATCH "\"score_adjudicated\": ([0-9]+)" _ "${manifest}")
if(at EQUAL -1 OR NOT CMAKE_MATCH_1 GREATER 0)
  message(FATAL_ERROR "the adjudicated run's manifest lacks its settings or adjudicated no game")
endif()
file(GLOB shards ${WORK}/adj/*.vf)
execute_process(
  COMMAND ${PYTHON} -I ${SOURCE_DIR}/tools/datagen/verify_games.py ${shards} --manifest ${WORK}/adj/t.json
          --adjudicate 300 4
  RESULT_VARIABLE rc OUTPUT_VARIABLE out ERROR_VARIABLE err)
message(STATUS "${out}")
if(NOT rc EQUAL 0)
  message(FATAL_ERROR "verify_games.py failed on the adjudicated run: ${err}")
endif()
execute_process(
  COMMAND ${PYTHON} -I ${SOURCE_DIR}/tools/datagen/verify_games.py ${shards} --adjudicate 300 3
  RESULT_VARIABLE rc OUTPUT_QUIET ERROR_QUIET)
if(rc EQUAL 0)
  message(FATAL_ERROR "verify_games.py accepted the adjudicated run under a shorter run length")
endif()
file(REMOVE_RECURSE ${WORK})
