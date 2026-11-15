#!/usr/bin/env bash
# Session 02 tests 1-5 (our WASM build vs native JSBSim 1.3.3). Summaries -> results/, raw logs -> out/ (ignored).
# Needs: npm ci; python venv with jsbsim==1.3.3 at .venv; wasm/bin built (scripts/build-wasm.sh) or as committed.
# Usage: scripts/run-tests.sh [1 2 3 4 5]
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
export JSBSIM_DEBUG=0
TESTS="${*:-1 2 3 4 5}"
mkdir -p out results
has() { [[ " $TESTS " == *" $1 "* ]]; }

if has 1; then {
  echo "# Test 1: every aircraft loads (ours vs native jsbsim 1.3.3)"
  npx tsx tests/loadmatrix/run_wasm.ts jsbsim
  npx tsx tests/loadmatrix/run_wasm.ts jsbsim-weh
  $PY tests/loadmatrix/run_native.py 2>/dev/null | tail -1
  $PY tests/loadmatrix/compare.py jsbsim jsbsim-weh
} 2>&1 | tee results/02-test1-loadmatrix.txt; fi

if has 2; then {
  echo "# Test 2: WASM vs native JSBSim 1.3.3, every step (differences are WASM minus native)"
  for s in c1723 f16_test c1721 T38; do
    echo; echo "## scripts/$s.xml"
    npx tsx tests/parity/run_wasm.ts scripts/$s.xml out/$s.wasm.csv
    $PY tests/parity/run_native.py scripts/$s.xml out/$s.native.csv 2>/dev/null | tail -1
    $PY tests/parity/compare.py out/$s.native.csv out/$s.wasm.csv
    $PY tests/parity/first_diff.py out/$s.native.csv out/$s.wasm.csv
  done
  echo; echo "## Sensitivity check: native vs native with the initial altitude raised by 1e-8 ft"
  echo "## (WASM and native already differ by 7.45e-9 ft at t=0, 2 ulp of the Earth radius)"
  for s in c1723 f16_test; do
    echo; echo "### $s, native vs native+1e-8 ft"
    PERTURB_H=1e-8 $PY tests/parity/run_native.py scripts/$s.xml out/$s.native_pert.csv 2>/dev/null | tail -1
    $PY tests/parity/compare.py out/$s.native.csv out/$s.native_pert.csv
  done
  echo; echo "## c1723 with the autopilot sensor noise removed (out/nonoise), WASM vs native"
  $PY tests/parity/make_nonoise.py
  JSBSIM_DATA=$PWD/out/nonoise npx tsx tests/parity/run_wasm.ts scripts/c1723.xml out/c1723.nonoise.wasm.csv
  JSBSIM_DATA=$PWD/out/nonoise $PY tests/parity/run_native.py scripts/c1723.xml out/c1723.nonoise.native.csv 2>/dev/null | tail -1
  $PY tests/parity/compare.py out/c1723.nonoise.native.csv out/c1723.nonoise.wasm.csv
  cmp -s out/c1723.wasm.csv out/c1723.nonoise.wasm.csv && echo "WASM c1723 with and without noise: bit-identical (noise is below the sensor's 12-bit quantization step)"

  echo; echo "## -fwasm-exceptions build vs -fexceptions build (should be bit-identical)"
  for s in c1723 f16_test; do
    JSBSIM_VARIANT=jsbsim-weh npx tsx tests/parity/run_wasm.ts scripts/$s.xml out/$s.weh.csv
    cmp -s out/$s.wasm.csv out/$s.weh.csv && echo "$s: bit-identical" || $PY tests/parity/first_diff.py out/$s.wasm.csv out/$s.weh.csv
  done
} 2>&1 | tee results/02-test2-parity.txt; fi

if has 3; then {
  echo "# Test 3: external forces set from JS every step"
  $PY tests/extforce/make_aircraft.py 1 20
  npx tsx tests/extforce/run_wasm.ts parity out/ext.wasm.csv
  npx tsx tests/extforce/run_wasm.ts parity out/ext0.wasm.csv zero
  $PY tests/extforce/run_native.py parity out/ext.native.csv 2>/dev/null
  $PY tests/extforce/run_native.py parity out/ext0.native.csv zero 2>/dev/null
  echo; echo "## WASM vs native, same force schedule"
  $PY tests/parity/compare.py out/ext.native.csv out/ext.wasm.csv
  $PY tests/parity/first_diff.py out/ext.native.csv out/ext.wasm.csv
  echo; echo "## Effect of the force (WASM, schedule vs magnitude 0)"
  $PY tests/parity/compare.py out/ext0.wasm.csv out/ext.wasm.csv
  echo; echo "## Cost per step, WASM -fexceptions (Node)"
  npx tsx tests/extforce/run_wasm.ts bench
  echo; echo "## Cost per step, WASM -fwasm-exceptions (Node)"
  JSBSIM_VARIANT=jsbsim-weh npx tsx tests/extforce/run_wasm.ts bench
  echo; echo "## Cost per step, native (Python)"
  $PY tests/extforce/run_native.py bench 2>/dev/null
} 2>&1 | tee results/02-test3-extforce.txt; fi

if has 4; then {
  echo "# Test 4: NASA check case 02 (tumbling brick), JSBSim v1.3.3 files unchanged"
  npx tsx tests/nasa/run_wasm.ts
  npx tsx tests/nasa/run_wasm.ts 5
  $PY tests/nasa/run_native.py 2>/dev/null
  $PY tests/nasa/run_native.py 5 2>/dev/null
  echo; echo "## Default rate integrator (1 = rectangular Euler), WASM vs NASA and vs native"
  $PY tests/nasa/compare.py out/Atmos_02_wasm.csv out/Atmos_02_native.csv
  echo; echo "## AB4 (simulation/integrator/rate/rotational = 5), WASM vs NASA and vs native"
  $PY tests/nasa/compare.py out/Atmos_02_wasm_rateint5.csv out/Atmos_02_native_rateint5.csv
  echo; echo "## Higher step rates (script dt overridden), WASM, body rates only"
  for hz in 480 1000; do
    npx tsx tests/nasa/run_wasm.ts 1 $hz >/dev/null; npx tsx tests/nasa/run_wasm.ts 5 $hz >/dev/null
    for f in out/Atmos_02_wasm_${hz}hz.csv out/Atmos_02_wasm_rateint5_${hz}hz.csv; do
      $PY tests/nasa/compare.py $f | grep -E "^Atmos|^variable|Rate"
    done
  done
} 2>&1 | tee results/02-test4-nasa.txt; fi

if has 5; then {
  echo "# Test 5: AB4 side effects (rate/rotational = 5 vs default 1), WASM"
  for s in c1723 f16_test f16_runway_test; do
    echo; echo "## scripts/$s.xml"
    [ -f out/$s.wasm.csv ] || npx tsx tests/parity/run_wasm.ts scripts/$s.xml out/$s.wasm.csv
    npx tsx tests/parity/run_wasm.ts scripts/$s.xml out/$s.ab4.wasm.csv 5
    $PY tests/ab4/compare.py out/$s.wasm.csv out/$s.ab4.wasm.csv
    $PY tests/parity/run_native.py scripts/$s.xml out/$s.ab4.native.csv 5 2>/dev/null | tail -1
    echo "AB4, native vs WASM:"; $PY tests/parity/compare.py out/$s.ab4.native.csv out/$s.ab4.wasm.csv > out/$s.ab4.cmp.txt || true
    grep -E "rows|h-sl-ft|q-rad" out/$s.ab4.cmp.txt || true
  done
  echo; echo "## 5b: AB4 vs default at higher step rates (first non-finite time, peak body rate, end state)"
  for s in f16_test f16_runway_test c1723; do
    echo; npx tsx tests/ab4/rate_sweep.ts scripts/$s.xml
  done
} 2>&1 | tee results/02-test5-ab4.txt; fi
