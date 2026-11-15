#!/usr/bin/env bash
# Run one configuration through the LATER gates of session 04 (G5b, G2b, G3b; GATES-04.md), then judge it and
# print the verdict per step rate.  tests/gates/run.sh <config> must have run first (G1, G4 and G6 are read from it).
#   tests/gates/run-later.sh <config> [rigidb repeat]
# Result: results/<SESSION>-later-<config>.txt (SESSION defaults to 04). Raw measurements: out/gates/<config>/.
# JOBS=<n> measurements run at once (default: the number of processors).
# The freeze rule: nothing runs unless the frozen gate files of session 03 AND the later-gate files are committed
# and unchanged.
set -euo pipefail
cd "$(dirname "$0")/../.."
CONFIG="$1"; shift
PARTS="${*:-rigidb repeat}"
PY="$PWD/.venv/bin/python"
export JSBSIM_DEBUG=0
FROZEN="tests/gates/gates.json tests/gates/run_native.py tests/gates/run_wasm.ts tests/gates/evaluate.py tests/gates/fixtures/brick_poi.xml tests/parity/compare.py GATES.md"
FROZEN04="tests/gates/gates-04.json tests/gates/run_native_04.py tests/gates/run_wasm_04.ts tests/gates/evaluate_04.py GATES-04.md"
if [ -n "$(git status --porcelain -- $FROZEN $FROZEN04)" ] || ! git ls-files --error-unmatch $FROZEN $FROZEN04 >/dev/null 2>&1; then
  echo "error: the gate files must be committed and unchanged before '$CONFIG' may run:" >&2; git status --short -- $FROZEN $FROZEN04 >&2; exit 1
fi
SRC="$($PY -c "import json,sys; print(json.load(open('tests/gates/configs.json'))[sys.argv[1]]['source'])" "$CONFIG")"
if [ "$SRC" = patched ]; then BIN="$PWD/wasm/bin"; else BIN="$PWD/build/wasm-bin-unpatched"; fi
[ -d "build/native/$SRC/jsbsim" ] || { echo "error: build/native/$SRC missing (scripts/build-native.sh $SRC)" >&2; exit 1; }
[ -f "$BIN/jsbsim-weh.wasm" ] || { echo "error: $BIN missing (PATCHSET=$SRC scripts/build-wasm.sh)" >&2; exit 1; }
O="out/gates/$CONFIG"; mkdir -p "$O" results
MODELS="$($PY -c "import json; print(' '.join(json.load(open('tests/gates/gates.json'))['aircraft']))")"
jobs=()
for part in $PARTS; do
  if [ "$part" = repeat ]; then
    for m in $MODELS; do
      jobs+=("PYTHONPATH=$PWD/build/native/$SRC $PY tests/gates/run_native_04.py $CONFIG repeat --models $m > $O/native04.repeat.$m.log 2>&1")
      jobs+=("JSBSIM_BIN=$BIN JSBSIM_VARIANT=jsbsim-weh npx tsx tests/gates/run_wasm_04.ts $CONFIG repeat --models $m > $O/wasm04.repeat.$m.log 2>&1")
    done
  else
    jobs+=("PYTHONPATH=$PWD/build/native/$SRC $PY tests/gates/run_native_04.py $CONFIG $part > $O/native04.$part.log 2>&1")
    jobs+=("JSBSIM_BIN=$BIN JSBSIM_VARIANT=jsbsim-weh npx tsx tests/gates/run_wasm_04.ts $CONFIG $part > $O/wasm04.$part.log 2>&1")
  fi
done
if ! printf '%s\n' "${jobs[@]}" | xargs -P "${JOBS:-$(nproc)}" -I{} bash -c '{}'; then
  echo "error: a runner failed; see $O/*04*.log" >&2; tail -n 3 $O/*04*.log >&2; exit 1
fi
$PY tests/gates/evaluate_04.py "$CONFIG" | tee "results/${SESSION:-04}-later-$CONFIG.txt"
