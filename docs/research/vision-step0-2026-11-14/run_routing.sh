#!/bin/bash
# Vision step 0 (d): the refits; each set's learned routings come from the other set.
# Run from anywhere: STEP0_PY (a Python with numpy, scipy, python-chess) and STEP0_DATA (the data folder: the
# feat-*, eval-*, hidden-*, plies-* files the earlier steps wrote) are read from the environment.
set -e
cd "$(dirname "$0")"
PY=${STEP0_PY:-python}; O=${STEP0_DATA:?the folder of the step0 data files}; NET=../../../nets/r3kr1.fnet
J1=$($PY -c "import json;print(json.load(open('$O/select-g4s2val.json'))['chosen'])")
$PY -I step0_routing.py refit $O/feat-g4c.npz $O/eval-g4c-r3kr1.npz $O/hidden-g4c-r3kr1.u8 --net $NET --progress $O/prog-from-g4s2val.npz --column $J1 --out $O/routing-g4c.json
test -s $O/routing-g4c.json
echo g4c refit done
$PY -I step0_routing.py select-column $O/feat-g4c.npz $O/eval-g4c-r3kr1.npz $O/hidden-g4c-r3kr1.u8 --net $NET --rank $O/rank-g4c.json --out $O/select-g4c.json
J2=$($PY -c "import json;print(json.load(open('$O/select-g4c.json'))['chosen'])")
echo g4c selection done: $J2
$PY -I step0_routing.py refit $O/feat-g4s2val.npz $O/eval-g4s2val-r3kr1.npz $O/hidden-g4s2val-r3kr1.u8 --net $NET --progress $O/prog-from-g4c.npz --column $J2 --out $O/routing-g4s2val.json
test -s $O/routing-g4s2val.json
echo routing done
