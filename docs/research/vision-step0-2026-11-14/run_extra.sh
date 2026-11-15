#!/bin/bash
# Vision step 0 (d), extras: the progress routing again with the Gauss-Newton refresh (g4c), phase x progress halves
# Run from anywhere: STEP0_PY (a Python with numpy, scipy, python-chess) and STEP0_DATA (the data folder: the
# feat-*, eval-*, hidden-*, plies-* files the earlier steps wrote) are read from the environment.
# (both sets), wings and columns again, on wider ridge grids (g4s2-val's first grid ended at its chosen 1000); on g4c column 38 is
# g4c's own selection (in-sample there: a selection-biased reading).
set -e
cd "$(dirname "$0")"
PY=${STEP0_PY:-python}; O=${STEP0_DATA:?the folder of the step0 data files}; NET=../../../nets/r3kr1.fnet
$PY -I step0_routing.py fit-progress $O/feat-g4s2val.npz $O/plies-g4s2val.npz --eval $O/eval-g4s2val-r3kr1.npz --out $O/prog2-from-g4s2val.npz > $O/prog2-from-g4s2val.log
$PY -I step0_routing.py fit-progress $O/feat-g4c.npz $O/plies-g4c.npz --eval $O/eval-g4c-r3kr1.npz --out $O/prog2-from-g4c.npz > $O/prog2-from-g4c.log
$PY -I step0_routing.py refit $O/feat-g4s2val.npz $O/eval-g4s2val-r3kr1.npz $O/hidden-g4s2val-r3kr1.u8 --net $NET --progress $O/prog2-from-g4c.npz --column 38 --routings phase,phaseprog,wings,column --lambdas 10,100,1000,10000,100000 --out $O/routing-extra-g4s2val.json
test -s $O/routing-extra-g4s2val.json
$PY -I step0_routing.py refit $O/feat-g4c.npz $O/eval-g4c-r3kr1.npz $O/hidden-g4c-r3kr1.u8 --net $NET --progress $O/prog2-from-g4s2val.npz --column 38 --routings phase,phaseprog,wings,progress,column --lambdas 1,10,100,1000,10000 --out $O/routing-extra-g4c.json
test -s $O/routing-extra-g4c.json
echo extra done
