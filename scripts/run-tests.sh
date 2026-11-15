#!/usr/bin/env bash
# Run tests 1-3 (Node WASM vs native Python JSBSim). Summaries go to results/, raw logs to out/ (ignored).
# Needs: npm ci; python venv with jsbsim==1.3.0 at .venv; scripts/fetch-jsbsim-data.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
export JSBSIM_DEBUG=0
mkdir -p out results

{
  echo "# Test 1: WASM vs native JSBSim, every step"
  for s in c1723 f16_test c1721 T38; do
    echo; echo "## scripts/$s.xml"
    npx tsx tests/parity/run_wasm.ts scripts/$s.xml out/$s.wasm.csv || true
    $PY tests/parity/run_native.py scripts/$s.xml out/$s.native.csv 2>/dev/null | tail -1
    if [ "$(tail -n +2 out/$s.wasm.csv | grep -c .)" -gt 0 ]; then
      $PY tests/parity/compare.py out/$s.native.csv out/$s.wasm.csv
      $PY tests/parity/first_diff.py out/$s.native.csv out/$s.wasm.csv
    fi
  done
} 2>&1 | tee results/test1-parity.txt

{
  echo "# Test 2: external forces set from JS every step"
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
  echo; echo "## Cost per step, WASM (Node)"
  npx tsx tests/extforce/run_wasm.ts bench
  echo; echo "## Cost per step, native (Python)"
  $PY tests/extforce/run_native.py bench 2>/dev/null
} 2>&1 | tee results/test2-extforce.txt

{
  echo "# Test 3: NASA check case 02 (tumbling brick)"
  $PY tests/nasa/make_brick.py
  npx tsx tests/nasa/run_wasm.ts
  npx tsx tests/nasa/run_wasm.ts 5
  $PY tests/nasa/run_native.py 2>/dev/null
  $PY tests/nasa/compare.py out/Atmos_02_wasm.csv out/Atmos_02_native.csv
  $PY tests/nasa/compare.py out/Atmos_02_wasm_rateint5.csv
} 2>&1 | tee results/test3-nasa.txt
