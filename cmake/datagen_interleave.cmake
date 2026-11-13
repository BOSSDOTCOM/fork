# SPDX-License-Identifier: GPL-3.0-or-later
#
# The datagen_interleave test (ideas.md idea 165, prototype; registered only
# in FORK_DATAGEN_INTERLEAVE builds): fork_datagen with --interleave 3 and
# --interleave 8 must write exactly the shards of --interleave 1 (today's
# one-game-at-a-time worker) for the same seed and worker count, every shard
# byte for byte, so every game byte for byte, and the same manifest counts
# (games, positions, nodes spent, results, ends). The settings are g4c's
# (split search, score adjudication, Syzygy tables when given) at smaller
# node counts.
#
#   cmake -DDATAGEN=... -DSOURCE_DIR=... -DWORK=... [-DTABLES=...] -P datagen_interleave.cmake

file(REMOVE_RECURSE ${WORK})
set(tables_args "")
if(TABLES)
  set(tables_args --tables ${TABLES})
endif()
foreach(k 1 3 8)
  file(MAKE_DIRECTORY ${WORK}/k${k})
  execute_process(
    COMMAND ${DATAGEN} --openings ${SOURCE_DIR}/tests/datagen_openings.epd --out ${WORK}/k${k}
            --positions 4000 --nodes 2000 --threads 2 --seed 7 --run t --hash-mb 1 --save-percent 50
            --unsaved-nodes 400 --check-nodes 200 --adjudicate-cp 700 --adjudicate-plies 8 ${tables_args}
            --interleave ${k}
    RESULT_VARIABLE rc ERROR_VARIABLE err)
  if(NOT rc EQUAL 0)
    message(FATAL_ERROR "fork_datagen --interleave ${k} failed (${rc}): ${err}")
  endif()
endforeach()

# The manifest up to its shard list (whose order follows the workers'
# finishing times), without the run time and the interleave setting.
function(manifest_counts dir out)
  file(READ ${dir}/t.json m)
  string(FIND "${m}" "\"shards\"" at)
  string(SUBSTRING "${m}" 0 ${at} m)
  string(REGEX REPLACE "\"seconds\": [^\n]*\n" "" m "${m}")
  string(REGEX REPLACE ", \"interleave\": [0-9]+" "" m "${m}")
  set(${out} "${m}" PARENT_SCOPE)
endfunction()

file(GLOB reference RELATIVE ${WORK}/k1 ${WORK}/k1/*.vf)
list(LENGTH reference n)
if(n LESS 2)
  message(FATAL_ERROR "expected a shard per worker, found ${n}")
endif()
manifest_counts(${WORK}/k1 reference_counts)
foreach(k 3 8)
  file(GLOB got RELATIVE ${WORK}/k${k} ${WORK}/k${k}/*.vf)
  if(NOT got STREQUAL reference)
    message(FATAL_ERROR "--interleave ${k} wrote shards [${got}], --interleave 1 [${reference}]")
  endif()
  foreach(shard ${reference})
    execute_process(COMMAND ${CMAKE_COMMAND} -E compare_files ${WORK}/k1/${shard} ${WORK}/k${k}/${shard}
                    RESULT_VARIABLE differs)
    if(differs)
      message(FATAL_ERROR "--interleave ${k}: shard ${shard} differs from --interleave 1's")
    endif()
  endforeach()
  manifest_counts(${WORK}/k${k} counts)
  if(NOT counts STREQUAL reference_counts)
    message(FATAL_ERROR "--interleave ${k}: manifest counts differ:\n${counts}\nagainst\n${reference_counts}")
  endif()
endforeach()
message(STATUS "--interleave 3 and 8: ${n} shards identical to --interleave 1's, manifest counts equal")
