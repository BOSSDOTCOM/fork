#!/usr/bin/env bash
# The TCEC build path for the r3kr1 promotion: ./update.sh (build/tcec/fork) with each CXX and FORK_ARCH given,
# then bench parity against tests/bench-r3kr1.ref, perftbench parity, netcheck on tests/nnue/r3kr1.parity and a
# UCI smoke start (scripts/uci-smoke.sh BIN 5). One build at a time; each binary copied to OUT/<label>/ first
# (update.sh removes build/tcec before every build).
#   tcec_path.sh SRC OUT LABEL=CXX@ARCH ...
set -u
src=${1:?SRC}; out=${2:?OUT}; shift 2
cd "$src" || exit 1
export FORK_JOBS=${FORK_JOBS:-3}
want=$(tr -d '\r' < tests/bench-r3kr1.ref | grep -E '^(nodes|signature) ' | tr '\n' ' ')
pwant=$(tr -d '\r' < tests/perft_bench.ref | grep -E '^(nodes|signature) ' | tr '\n' ' ')
mkdir -p "$out"
for spec in "$@"; do
  label=${spec%%=*}; rest=${spec#*=}; cxx=${rest%@*}; arch=${rest##*@}
  log=$out/tcec-$label.log
  {
    echo "== $label: CXX=$cxx FORK_ARCH=$arch $(date)"
    if ! CXX=$cxx FORK_ARCH=$arch ./update.sh > "$out/update-$label.log" 2>&1; then
      echo "$label: UPDATE.SH FAILED"; tail -5 "$out/update-$label.log"; continue
    fi
    bin=build/tcec/fork; [ -x "$bin.exe" ] && bin=$bin.exe
    mkdir -p "$out/$label"; cp "$bin" "$out/$label/"
    b=$out/$label/$(basename "$bin")
    "$b" version | tr -d '\r' | grep -E '^(Fork|compiler|arch|lto|net) '
    got=$("$b" bench | tr -d '\r' | grep -E '^(nodes|signature|nps) ')
    echo "$got"
    [ "$(grep -E '^(nodes|signature) ' <<<"$got" | tr '\n' ' ')" = "$want" ] && echo "$label: bench parity OK" || echo "$label: BENCH MISMATCH"
    [ "$("$b" perftbench | tr -d '\r' | grep -E '^(nodes|signature) ' | tr '\n' ' ')" = "$pwant" ] &&
      echo "$label: perftbench parity OK" || echo "$label: PERFTBENCH MISMATCH"
    echo "$label: $("$b" netcheck tests/nnue/r3kr1.parity | tr -d '\r' | tail -1)"
    if bash scripts/uci-smoke.sh "$b" 5 > "$out/smoke-$label.log" 2>&1; then
      echo "$label: uci smoke OK ($(tail -1 "$out/smoke-$label.log" | tr -d '\r'))"
    else
      echo "$label: UCI SMOKE FAILED"
    fi
  } > "$log" 2>&1
  cat "$log"
done
