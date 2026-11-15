#!/usr/bin/env bash
# Run one configuration through all the gates (native and WebAssembly), then judge it.
#   tests/gates/run.sh <config> [ground nasa rigid flights cost]
# Result: results/<SESSION>-gates-<config>.txt (the evaluator's report; SESSION defaults to 04; session 03's
# reports are results/03-gates-*). Raw measurements: out/gates/<config>/.
# The freeze rule is enforced here: nothing but the two reference configurations runs unless the gate
# files are committed and unchanged (so the gates cannot be edited after a result has been seen).
set -euo pipefail
cd "$(dirname "$0")/../.."
CONFIG="$1"; shift
PARTS="${*:-ground nasa rigid flights cost}"
PY=.venv/bin/python
export JSBSIM_DEBUG=0
FROZEN="tests/gates/gates.json tests/gates/run_native.py tests/gates/run_wasm.ts tests/gates/evaluate.py tests/gates/fixtures/brick_poi.xml tests/parity/compare.py GATES.md"
SRC="$($PY -c "import json,sys; print(json.load(open('tests/gates/configs.json'))[sys.argv[1]]['source'])" "$CONFIG")"
case "$CONFIG" in
  ref-*) ;;
  *) if [ -n "$(git status --porcelain -- $FROZEN)" ] || ! git ls-files --error-unmatch $FROZEN >/dev/null 2>&1; then
       echo "error: the gate files must be committed and unchanged before '$CONFIG' may run:" >&2; git status --short -- $FROZEN >&2; exit 1
     fi ;;
esac
if [ "$SRC" = patched ]; then BIN="$PWD/wasm/bin"; else BIN="$PWD/build/wasm-bin-unpatched"; fi
[ -d "build/native/$SRC/jsbsim" ] || { echo "error: build/native/$SRC missing (scripts/build-native.sh $SRC)" >&2; exit 1; }
[ -f "$BIN/jsbsim-weh.wasm" ] || { echo "error: $BIN missing (PATCHSET=$SRC scripts/build-wasm.sh)" >&2; exit 1; }
mkdir -p "out/gates/$CONFIG" results
MEASURE=""; for p in $PARTS; do [ "$p" = cost ] || MEASURE="$MEASURE $p"; done
pids=()
if [ -n "$MEASURE" ]; then
  PYTHONPATH="$PWD/build/native/$SRC" $PY tests/gates/run_native.py "$CONFIG" $MEASURE > "out/gates/$CONFIG/native.log" 2>&1 & pids+=($!)
  JSBSIM_BIN="$BIN" JSBSIM_VARIANT=jsbsim-weh npx tsx tests/gates/run_wasm.ts "$CONFIG" $MEASURE > "out/gates/$CONFIG/wasm-jsbsim-weh.log" 2>&1 & pids+=($!)
  if [[ " $MEASURE " == *" flights "* ]]; then
    JSBSIM_BIN="$BIN" JSBSIM_VARIANT=jsbsim npx tsx tests/gates/run_wasm.ts "$CONFIG" flights > "out/gates/$CONFIG/wasm-jsbsim.log" 2>&1 & pids+=($!)
  fi
fi
status=0
for pid in "${pids[@]:-}"; do [ -z "$pid" ] || wait "$pid" || status=1; done
[ $status = 0 ] || { echo "error: a runner failed; see out/gates/$CONFIG/*.log" >&2; tail -5 out/gates/$CONFIG/*.log >&2; exit 1; }
# Timing runs alone, after the measurements, so that nothing else competes for the processor.
if [[ " $PARTS " == *" cost "* ]]; then JSBSIM_BIN="$BIN" JSBSIM_VARIANT=jsbsim-weh npx tsx tests/gates/cost.ts "$CONFIG" > "out/gates/$CONFIG/cost.log" 2>&1; fi
$PY tests/gates/evaluate.py "$CONFIG" | tee "results/${SESSION:-04}-gates-$CONFIG.txt"
