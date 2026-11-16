#!/usr/bin/env bash
# Tests 1-5 (our WASM build vs native JSBSim) plus the harness self-tests. Summaries -> results/, raw logs -> out/ (ignored).
# Needs: npm ci; python venv at .venv (pip install -r requirements.txt); wasm/bin built (scripts/build-wasm.sh) or as committed.
# Usage: scripts/run-tests.sh [0 1 2 3 4 5]        0 = harness and binding self-tests
# Environment:
#   NATIVE=pip (default) | unpatched | patched   which native answer key (the last two from scripts/build-native.sh)
#   SESSION=03                                   prefix of the summaries in results/
#   TAG=""                                       extra suffix for the summaries (e.g. -native-src)
# Every WASM run names its build variant explicitly (EXC = -fexceptions, WEH = -fwasm-exceptions), and the
# hash of every binary under test is written at the top of each summary.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
export JSBSIM_DEBUG=0
NATIVE="${NATIVE:-pip}"
SESSION="${SESSION:-03}"
TAG="${TAG:-}"
EXC=jsbsim        # -fexceptions
WEH=jsbsim-weh    # -fwasm-exceptions (the default build)
if [ "$NATIVE" != pip ]; then
  [ -d "build/native/$NATIVE/jsbsim" ] || { echo "error: build/native/$NATIVE missing; run scripts/build-native.sh $NATIVE" >&2; exit 1; }
  export PYTHONPATH="$PWD/build/native/$NATIVE"
fi
TESTS="${*:-0 1 2 3 4 5}"
mkdir -p out results
has() { [[ " $TESTS " == *" $1 "* ]]; }
wasm() { local v="$1"; shift; JSBSIM_VARIANT="$v" npx tsx "$@"; }   # wasm <variant> <script.ts> [args]
res() { echo "results/$SESSION-$1$TAG.txt"; }
builds() {
  echo "## Builds under test"
  for v in $EXC $WEH; do echo "- wasm $v: sha256 $(sha256sum wasm/bin/$v.wasm | cut -d' ' -f1) ($(grep -o '"buildVersion": "[^"]*"' wasm/bin/build-info.json | cut -d'"' -f4))"; done
  echo "- wasm patches: $(grep -A3 '"patches"' wasm/bin/build-info.json | tr -d '\n' | sed -E 's/.*"patches": *(\[[^]]*\]).*/\1/')"
  echo "- $($PY -c 'import sys; sys.path.insert(0, "tests/pylib"); import native; print(native.describe())' 2>/dev/null)"
  echo
}
# Native runs must not leave files in the committed JSBSim data (only the generated ext_* test copies may appear).
data_clean() {
  local extra; extra="$(git status --porcelain --ignored jsbsim-data | grep -v -E 'aircraft/c172p_ext[0-9]+/|scripts/ext_' || true)"
  if [ -n "$extra" ]; then echo "FAIL: files written into jsbsim-data/:"; echo "$extra"; return 1; fi
  echo "jsbsim-data/ clean: no output files written into the data root"
}

if has 0; then {
  echo "# Test 0: self-tests of the harness and the binding"; builds
  echo "## Comparator self-test (synthetic bad logs must be refused)"
  $PY tests/parity/selftest_compare.py
  for v in $EXC $WEH; do echo; wasm $v tests/binding/regress.ts; done
  for v in $EXC $WEH; do echo; wasm $v tests/binding/containment.ts unit; done
  echo; echo "## Build self-test (patches always re-applied and hashed; wrong Emscripten version refused)"
  tests/build/selftest_patches.sh
  echo; npx tsc && echo "typecheck: ok"
} 2>&1 | tee "$(res test0-selftests)"; fi

if has 1; then {
  echo "# Test 1: every aircraft loads (ours vs native)"; builds
  wasm $EXC tests/loadmatrix/run_wasm.ts $EXC
  wasm $WEH tests/loadmatrix/run_wasm.ts $WEH
  $PY tests/loadmatrix/run_native.py 2>/dev/null | tail -1
  $PY tests/loadmatrix/compare.py $EXC $WEH
  data_clean
} 2>&1 | tee "$(res test1-loadmatrix)"; fi

if has 2; then {
  echo "# Test 2: WASM vs native JSBSim, every step (differences are WASM minus native)"; builds
  for s in c1723 f16_test c1721 T38; do
    echo; echo "## scripts/$s.xml (wasm $EXC vs native)"
    wasm $EXC tests/parity/run_wasm.ts scripts/$s.xml out/$s.$EXC.csv
    $PY tests/parity/run_native.py scripts/$s.xml out/$s.native.csv 2>/dev/null | tail -1
    $PY tests/parity/compare.py out/$s.native.csv out/$s.$EXC.csv
    $PY tests/parity/first_diff.py out/$s.native.csv out/$s.$EXC.csv
  done
  echo; echo "## Sensitivity check: native vs native with the initial altitude raised by 1e-8 ft"
  echo "## (WASM and native already differ by 7.45e-9 ft at t=0, 2 ulp of the Earth radius)"
  for s in c1723 f16_test; do
    echo; echo "### $s, native vs native+1e-8 ft"
    PERTURB_H=1e-8 $PY tests/parity/run_native.py scripts/$s.xml out/$s.native_pert.csv 2>/dev/null | tail -1
    $PY tests/parity/compare.py out/$s.native.csv out/$s.native_pert.csv
  done
  echo; echo "## c1723 with the autopilot sensor noise removed (out/nonoise), wasm $EXC vs native"
  $PY tests/parity/make_nonoise.py
  JSBSIM_DATA=$PWD/out/nonoise wasm $EXC tests/parity/run_wasm.ts scripts/c1723.xml out/c1723.nonoise.$EXC.csv
  JSBSIM_DATA=$PWD/out/nonoise $PY tests/parity/run_native.py scripts/c1723.xml out/c1723.nonoise.native.csv 2>/dev/null | tail -1
  $PY tests/parity/compare.py out/c1723.nonoise.native.csv out/c1723.nonoise.$EXC.csv
  cmp -s out/c1723.$EXC.csv out/c1723.nonoise.$EXC.csv && echo "WASM c1723 with and without noise: bit-identical (noise is below the sensor's 12-bit quantization step)"

  echo; echo "## wasm $WEH vs wasm $EXC, every step of every script (should be bit-identical)"
  for s in c1723 f16_test c1721 T38; do
    wasm $WEH tests/parity/run_wasm.ts scripts/$s.xml out/$s.$WEH.csv
    cmp -s out/$s.$EXC.csv out/$s.$WEH.csv && echo "$s: $WEH and $EXC logs are bit-identical" || { echo "$s: $WEH and $EXC DIFFER"; $PY tests/parity/first_diff.py out/$s.$EXC.csv out/$s.$WEH.csv; }
  done
  data_clean
} 2>&1 | tee "$(res test2-parity)"; fi

if has 3; then {
  echo "# Test 3: external forces set from JS every step"; builds
  $PY tests/extforce/make_aircraft.py 0 1 20
  for v in $EXC $WEH; do
    wasm $v tests/extforce/run_wasm.ts parity out/ext.$v.csv
    wasm $v tests/extforce/run_wasm.ts parity out/ext0.$v.csv zero
  done
  $PY tests/extforce/run_native.py parity out/ext.native.csv 2>/dev/null
  $PY tests/extforce/run_native.py parity out/ext0.native.csv zero 2>/dev/null
  for v in $EXC $WEH; do
    echo; echo "## wasm $v vs native, same force schedule"
    $PY tests/parity/compare.py out/ext.native.csv out/ext.$v.csv
    $PY tests/parity/first_diff.py out/ext.native.csv out/ext.$v.csv
  done
  cmp -s out/ext.$EXC.csv out/ext.$WEH.csv && echo && echo "wasm $EXC and $WEH logs are bit-identical"
  echo; echo "## Effect of the force (wasm $WEH, schedule vs magnitude 0)"
  $PY tests/parity/compare.py out/ext0.$WEH.csv out/ext.$WEH.csv
  for v in $EXC $WEH; do
    echo; echo "## Cost per step, wasm $v (Node)"
    wasm $v tests/extforce/run_wasm.ts bench
  done
  echo; echo "## Cost per step, native (Python)"
  $PY tests/extforce/run_native.py bench 2>/dev/null
  data_clean
} 2>&1 | tee "$(res test3-extforce)"; fi

if has 4; then {
  echo "# Test 4: NASA check case 02 (tumbling brick), JSBSim v1.3.3 files unchanged"; builds
  for v in $EXC $WEH; do
    wasm $v tests/nasa/run_wasm.ts 1 0 out/Atmos_02_$v.csv
    wasm $v tests/nasa/run_wasm.ts 5 0 out/Atmos_02_${v}_rateint5.csv
  done
  cmp -s out/Atmos_02_$EXC.csv out/Atmos_02_$WEH.csv && cmp -s out/Atmos_02_${EXC}_rateint5.csv out/Atmos_02_${WEH}_rateint5.csv && echo "wasm $EXC and $WEH logs are bit-identical (default and AB4)"
  $PY tests/nasa/run_native.py 2>/dev/null
  $PY tests/nasa/run_native.py 5 2>/dev/null
  echo; echo "## Default rate integrator (1 = rectangular Euler), wasm $WEH vs NASA and vs native"
  $PY tests/nasa/compare.py out/Atmos_02_$WEH.csv out/Atmos_02_native.csv
  echo; echo "## AB4 (simulation/integrator/rate/rotational = 5), wasm $WEH vs NASA and vs native"
  $PY tests/nasa/compare.py out/Atmos_02_${WEH}_rateint5.csv out/Atmos_02_native_rateint5.csv
  echo; echo "## Higher step rates (dt given to loadScript, so set before the model loads), wasm $WEH, body rates only"
  for hz in 480 1000; do
    wasm $WEH tests/nasa/run_wasm.ts 1 $hz out/Atmos_02_${WEH}_${hz}hz.csv >/dev/null
    wasm $WEH tests/nasa/run_wasm.ts 5 $hz out/Atmos_02_${WEH}_rateint5_${hz}hz.csv >/dev/null
    for f in out/Atmos_02_${WEH}_${hz}hz.csv out/Atmos_02_${WEH}_rateint5_${hz}hz.csv; do
      $PY tests/nasa/compare.py $f | grep -E "^Atmos|^variable|Rate"
    done
  done
  data_clean
} 2>&1 | tee "$(res test4-nasa)"; fi

if has 5; then {
  echo "# Test 5: AB4 side effects (rate/rotational = 5 vs default 1), wasm $WEH"; builds
  for s in c1723 f16_test f16_runway_test; do
    echo; echo "## scripts/$s.xml"
    wasm $WEH tests/parity/run_wasm.ts scripts/$s.xml out/$s.$WEH.csv
    wasm $WEH tests/parity/run_wasm.ts scripts/$s.xml out/$s.ab4.$WEH.csv 5
    $PY tests/ab4/compare.py out/$s.$WEH.csv out/$s.ab4.$WEH.csv
    $PY tests/parity/run_native.py scripts/$s.xml out/$s.ab4.native.csv 5 2>/dev/null | tail -1
    echo "AB4, native vs wasm $WEH (the comparator refuses logs that contain NaN; that is expected for f16_test):"
    $PY tests/parity/compare.py out/$s.ab4.native.csv out/$s.ab4.$WEH.csv > out/$s.ab4.cmp.txt 2>/dev/null || true
    grep -E "REFUSED|rows|h-sl-ft|q-rad" out/$s.ab4.cmp.txt || true
  done
  echo; echo "## 5b: AB4 vs default at higher step rates (runaway and first NaN reported separately)"
  for s in f16_test f16_runway_test c1723; do
    echo; wasm $WEH tests/ab4/rate_sweep.ts scripts/$s.xml
  done
  data_clean
} 2>&1 | tee "$(res test5-ab4)"; fi
