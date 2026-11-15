#!/bin/bash
# Vision step 0: the injection checks, then the head-routing chain (each step checks its output before the next).
# Run from anywhere: STEP0_PY (a Python with numpy, scipy, python-chess) and STEP0_DATA (the data folder: the
# feat-*, eval-*, hidden-*, plies-* files the earlier steps wrote) are read from the environment.
set -e
cd "$(dirname "$0")"
PY=${STEP0_PY:-python}; O=${STEP0_DATA:?the folder of the step0 data files}; NET=../../../nets/r3kr1.fnet
for spec in "xl mover 0.005" "xl mover 0.001" "pin both 0.005" "pin both 0.001" "kk both 0.005" "mat both 0.005" "xx opp 0.002"; do
  set -- $spec
  $PY -I step0_study.py $O/feat-g4c.npz --net r3kr1=$O/eval-g4c-r3kr1.npz --inject $1 $2 $3 --out $O/inject-g4c-$1-$2-$3.json > $O/inject-g4c-$1-$2-$3.log 2>&1
  test -s $O/inject-g4c-$1-$2-$3.json
done
echo injections done
$PY -I step0_routing.py fit-progress $O/feat-g4s2val.npz $O/plies-g4s2val.npz --out $O/prog-from-g4s2val.npz > $O/prog-from-g4s2val.log
$PY -I step0_routing.py fit-progress $O/feat-g4c.npz $O/plies-g4c.npz --out $O/prog-from-g4c.npz > $O/prog-from-g4c.log
$PY -I step0_routing.py rank-columns $O/feat-g4s2val.npz $O/eval-g4s2val-r3kr1.npz $O/hidden-g4s2val-r3kr1.u8 --out $O/rank-g4s2val.json > $O/rank-g4s2val.log
$PY -I step0_routing.py rank-columns $O/feat-g4c.npz $O/eval-g4c-r3kr1.npz $O/hidden-g4c-r3kr1.u8 --out $O/rank-g4c.json > $O/rank-g4c.log
echo prep done
