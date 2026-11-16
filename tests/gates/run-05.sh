#!/usr/bin/env bash
# Run one configuration through the gates of session 05 (G2d, G8, G3d, G7; GATES-05.md), native and WebAssembly,
# at the step rates configs.json names for it (rates_05), then judge it.
#   tests/gates/run-05.sh <config>            JOBS=<n> runs at once (default: the number of processors)
# Result: results/05-new-<config>.txt. Measurements: out/gates05/<config>/<hz>/<platform>/.
# The reference runs (9600 Hz) the configuration needs are made first if they do not exist yet.
# The freeze rule: nothing but reference configurations runs unless every frozen gate file, old and new, is
# committed and unchanged.
set -euo pipefail
cd "$(dirname "$0")/../.."
CONFIG="$1"
PY="$PWD/.venv/bin/python"
export JSBSIM_DEBUG=0
FROZEN="tests/gates/gates.json tests/gates/run_native.py tests/gates/run_wasm.ts tests/gates/evaluate.py tests/gates/fixtures/brick_poi.xml tests/parity/compare.py GATES.md"
FROZEN04="tests/gates/gates-04.json tests/gates/run_native_04.py tests/gates/run_wasm_04.ts tests/gates/evaluate_04.py GATES-04.md tests/gates/gates-04b.json tests/gates/run_native_04b.py tests/gates/run_wasm_04b.ts tests/gates/evaluate_04b.py GATES-04b.md"
FROZEN05="tests/gates/gates-05.json tests/gates/sim05.py tests/gates/sim05.ts tests/gates/run_native_05.py tests/gates/run_wasm_05.ts tests/gates/evaluate_05.py GATES-05.md"
case "$CONFIG" in
  ref-*|ref05-*) ;;
  *) if [ -n "$(git status --porcelain -- $FROZEN $FROZEN04 $FROZEN05)" ] || ! git ls-files --error-unmatch $FROZEN $FROZEN04 $FROZEN05 >/dev/null 2>&1; then
       echo "error: the gate files must be committed and unchanged before '$CONFIG' may run:" >&2; git status --short -- $FROZEN $FROZEN04 $FROZEN05 >&2; exit 1
     fi ;;
esac
field() { $PY -c "import json,sys; v=json.load(open('tests/gates/configs.json'))[sys.argv[1]].get(sys.argv[2],''); print(' '.join(map(str,v)) if isinstance(v,list) else v)" "$1" "$2"; }
REF_HZ="$($PY -c "import json; print(json.load(open('tests/gates/gates-05.json'))['reference']['hz'])")"
FW="c172x c310 737 f16"
ALL="c172x f16 c310 ah1s 737"
jobs=()
# add <config> <hz> <part> <models or -> <prefix>: one native and one WebAssembly job
add() {
  local c="$1" hz="$2" part="$3" models="$4" prefix="$5" src bin o tag marg=""
  src="$(field "$c" source)"
  if [ "$src" = patched ]; then bin="$PWD/wasm/bin"; else bin="$PWD/build/wasm-bin-unpatched"; fi
  [ -d "build/native/$src/jsbsim" ] || { echo "error: build/native/$src missing" >&2; exit 1; }
  [ -f "$bin/jsbsim-weh.wasm" ] || { echo "error: $bin missing" >&2; exit 1; }
  o="out/gates05/$c/$hz"; mkdir -p "$o/native" "$o/wasm"
  tag="$part"; if [ "$models" != - ]; then marg="--models $models"; tag="$part-${models//,/-}"; fi
  jobs+=("PYTHONPATH=$PWD/build/native/$src $PY tests/gates/run_native_05.py $c $hz $part $marg > $o/native/log-$tag.txt 2>&1")
  jobs+=("JSBSIM_BIN=$bin JSBSIM_VARIANT=jsbsim-weh npx tsx tests/gates/run_wasm_05.ts $c $hz $part $marg > $o/wasm/log-$tag.txt 2>&1 && $PY tests/gates/evaluate_05.py measure $o/wasm $prefix $tag >> $o/wasm/log-$tag.txt 2>&1")
}
REFG="$(field "$CONFIG" ref_ground)"; REFF="$(field "$CONFIG" ref_flight)"
if [ ! -f "out/gates05/$REFG/$REF_HZ/done" ]; then
  for m in $FW ah1s; do add "$REFG" "$REF_HZ" landing "$m" "landing-$m-"; done
  for m in $FW; do add "$REFG" "$REF_HZ" g8 "$m" "g8-$m-"; done
fi
if [ ! -f "out/gates05/$REFF/$REF_HZ/done" ]; then add "$REFF" "$REF_HZ" fast - fast-; fi
for hz in $(field "$CONFIG" rates_05); do
  rm -f out/gates05/$CONFIG/$hz/*/metrics-*.jsonl
  for m in $FW ah1s; do add "$CONFIG" "$hz" landing "$m" "landing-$m-"; done
  add "$CONFIG" "$hz" g8 - g8-
  for m in $ALL; do add "$CONFIG" "$hz" crash "$m" "crash-$m-"; done
  add "$CONFIG" "$hz" probe - probe-
  add "$CONFIG" "$hz" fast - fast-
done
if ! printf '%s\n' "${jobs[@]}" | xargs -P "${JOBS:-$(nproc)}" -I{} bash -c '{}'; then
  echo "error: a runner failed; see out/gates05/*/*/*/log-*.txt" >&2; exit 1
fi
mkdir -p "out/gates05/$REFG/$REF_HZ" "out/gates05/$REFF/$REF_HZ"; touch "out/gates05/$REFG/$REF_HZ/done" "out/gates05/$REFF/$REF_HZ/done"
mkdir -p results
$PY tests/gates/evaluate_05.py "$CONFIG" | tee "results/${SESSION:-05}-new-$CONFIG.txt"
