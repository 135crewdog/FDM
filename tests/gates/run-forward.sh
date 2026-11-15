#!/usr/bin/env bash
# Run one configuration through G2c (the forward hard landing, GATES-04b.md), then print the verdict per step
# rate both ways. tests/gates/run.sh and run-later.sh must have run for this configuration (and for the floor).
#   tests/gates/run-forward.sh <config>
# Result: results/<SESSION>-forward-<config>.txt (SESSION defaults to 04).
# The freeze rule: every frozen gate file (sessions 03, 04 and the G2c correction) must be committed and unchanged.
set -euo pipefail
cd "$(dirname "$0")/../.."
CONFIG="$1"
PY="$PWD/.venv/bin/python"
export JSBSIM_DEBUG=0
FROZEN="tests/gates/gates.json tests/gates/run_native.py tests/gates/run_wasm.ts tests/gates/evaluate.py tests/gates/fixtures/brick_poi.xml tests/parity/compare.py GATES.md"
FROZEN04="tests/gates/gates-04.json tests/gates/run_native_04.py tests/gates/run_wasm_04.ts tests/gates/evaluate_04.py GATES-04.md"
FROZEN04B="tests/gates/gates-04b.json tests/gates/run_native_04b.py tests/gates/run_wasm_04b.ts tests/gates/evaluate_04b.py GATES-04b.md"
if [ -n "$(git status --porcelain -- $FROZEN $FROZEN04 $FROZEN04B)" ] || ! git ls-files --error-unmatch $FROZEN $FROZEN04 $FROZEN04B >/dev/null 2>&1; then
  echo "error: the gate files must be committed and unchanged before '$CONFIG' may run:" >&2; git status --short -- $FROZEN $FROZEN04 $FROZEN04B >&2; exit 1
fi
SRC="$($PY -c "import json,sys; print(json.load(open('tests/gates/configs.json'))[sys.argv[1]]['source'])" "$CONFIG")"
if [ "$SRC" = patched ]; then BIN="$PWD/wasm/bin"; else BIN="$PWD/build/wasm-bin-unpatched"; fi
O="out/gates/$CONFIG"; mkdir -p "$O" results
MODELS="$($PY -c "import json; print(' '.join(json.load(open('tests/gates/gates.json'))['aircraft']))")"
jobs=()
for m in $MODELS; do
  jobs+=("PYTHONPATH=$PWD/build/native/$SRC $PY tests/gates/run_native_04b.py $CONFIG --models $m > $O/native04b.$m.log 2>&1")
  jobs+=("JSBSIM_BIN=$BIN JSBSIM_VARIANT=jsbsim-weh npx tsx tests/gates/run_wasm_04b.ts $CONFIG --models $m > $O/wasm04b.$m.log 2>&1")
done
if ! printf '%s\n' "${jobs[@]}" | xargs -P "${JOBS:-$(nproc)}" -I{} bash -c '{}'; then
  echo "error: a runner failed; see $O/*04b*.log" >&2; tail -n 3 $O/*04b*.log >&2; exit 1
fi
$PY tests/gates/evaluate_04b.py "$CONFIG" | tee "results/${SESSION:-04}-forward-$CONFIG.txt"
