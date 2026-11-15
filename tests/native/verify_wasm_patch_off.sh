#!/usr/bin/env bash
# The patched WebAssembly build (wasm/bin) with every patch switched off (the default) must give the same
# logs, bit for bit, as the unpatched WebAssembly build (build/wasm-bin-unpatched): tests 2-4 workloads and
# the review's controlled flights, both exception variants.
#   tests/native/verify_wasm_patch_off.sh        (exit 1 on any difference)
set -uo pipefail
cd "$(dirname "$0")/../.."
O=out/wasm-patch-off; mkdir -p $O
fail=0
PY=.venv/bin/python
$PY tests/extforce/make_aircraft.py 0 1 20
echo "# Patched WebAssembly build with patches off against the unpatched build"
for b in wasm/bin build/wasm-bin-unpatched; do echo "- $b: $(grep -o '"patchSet": "[^"]*"' $b/build-info.json), jsbsim-weh.wasm sha256 $(sha256sum $b/jsbsim-weh.wasm | cut -c1-16), patches $(grep -A2 '"patches"' $b/build-info.json | tr -d '\n ' | cut -c1-140)"; done
for v in jsbsim-weh jsbsim; do
  for kind in patched unpatched; do
    if [ $kind = patched ]; then B=$PWD/wasm/bin; else B=$PWD/build/wasm-bin-unpatched; fi
    for s in c1721 T38 c1723 f16_test; do JSBSIM_BIN=$B JSBSIM_VARIANT=$v npx tsx tests/parity/run_wasm.ts scripts/$s.xml $O/$s.$v.$kind.csv >/dev/null; done
    JSBSIM_BIN=$B JSBSIM_VARIANT=$v npx tsx tests/extforce/run_wasm.ts parity $O/ext.$v.$kind.csv 2>/dev/null
    JSBSIM_BIN=$B JSBSIM_VARIANT=$v npx tsx tests/nasa/run_wasm.ts 1 0 $O/nasa.$v.$kind.csv >/dev/null
    JSBSIM_BIN=$B JSBSIM_VARIANT=$v npx tsx tests/nasa/run_wasm.ts 5 0 $O/nasa5.$v.$kind.csv >/dev/null
    JSBSIM_BIN=$B JSBSIM_VARIANT=$v GATES_ALLOW_KEY_MISMATCH=1 npx tsx tests/gates/run_wasm.ts ref-ab4 flights >/dev/null
    for m in c172x f16; do mv out/gates/ref-ab4/flight-$m.wasm-$v.csv $O/flight-$m.$v.$kind.csv; done
  done
  for f in c1721 T38 c1723 f16_test ext nasa nasa5 flight-c172x flight-f16; do
    if cmp -s $O/$f.$v.patched.csv $O/$f.$v.unpatched.csv; then echo "PASS  $v $f: bit-identical ($(($(wc -l < $O/$f.$v.patched.csv) - 1)) rows)"; else echo "FAIL  $v $f: differs"; fail=1; fi
  done
done
[ $fail = 0 ] && echo "# RESULT: PASS" || echo "# RESULT: FAIL"
exit $fail
