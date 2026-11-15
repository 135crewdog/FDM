#!/usr/bin/env bash
# Is a native JSBSim built here from source a valid answer key?  It must agree with a reference key on
# tests 1-4 and on the independent review's controlled-flight probes (tests/review/parity_probe.py).
#   tests/native/verify_key.sh [candidate=unpatched] [reference=pip]
# Typical uses:
#   verify_key.sh unpatched pip        the source build against pip's jsbsim==1.3.3 (step 2 of session 03)
#   verify_key.sh patched unpatched    patches must change NOTHING while they are switched off (their default)
# For every log: "bit-identical", or else the strict comparator with the review's tolerances
# (positions <= 1e-4 ft, velocities <= 1e-5 ft/s, rates and attitudes <= 1e-7; tests/parity/compare.py --gate).
# Exit code 1 if anything is outside tolerance.
set -uo pipefail
cd "$(dirname "$0")/../.."
CAND="${1:-unpatched}"; REF="${2:-pip}"
PY="$PWD/.venv/bin/python"
export JSBSIM_DEBUG=0
O=out/native-key; mkdir -p $O
fail=0
key() { if [ "$1" = pip ]; then env -u PYTHONPATH "${@:2}"; else PYTHONPATH="$PWD/build/native/$1" "${@:2}"; fi; }
same() {  # same <label> <ref.csv> <cand.csv>
  if cmp -s "$2" "$3"; then echo "PASS  $1: bit-identical ($(($(wc -l < "$2") - 1)) rows)"
  elif $PY tests/parity/compare.py "$2" "$3" --gate > $O/last-compare.txt 2>&1; then echo "PASS  $1: within tolerance, not bit-identical (largest: $(sort -g -k2 -r <(grep -E '^[a-z]' $O/last-compare.txt | grep -v '^column\|^rows') | head -1 | awk '{print $1, $2}'))"
  else echo "FAIL  $1: $(grep -E 'REFUSED|GATE FAIL' $O/last-compare.txt)"; fail=1; fi
}
echo "# Native answer key check: candidate [$CAND] against reference [$REF]"
for k in $REF $CAND; do echo "- $k: $(key $k $PY -c 'import sys; sys.path.insert(0, "tests/pylib"); import native; print(native.describe())' 2>/dev/null)"; done

echo; echo "## Test 1: load matrix (same aircraft load, same failure messages)"
for k in $REF $CAND; do LOADMATRIX_OUT=$O/loadmatrix.$k.json key $k $PY tests/loadmatrix/run_native.py 2>/dev/null | tail -1; done
if $PY - "$O/loadmatrix.$REF.json" "$O/loadmatrix.$CAND.json" <<'PYEOF'
import json, sys
a, b = [{r["name"]: (r["ok"], r["msg"]) for r in json.load(open(p))} for p in sys.argv[1:3]]
diff = [n for n in sorted(set(a) | set(b)) if a.get(n) != b.get(n)]
print(f"{sum(v[0] for v in a.values())}/{len(a)} vs {sum(v[0] for v in b.values())}/{len(b)} load; aircraft with a different result or message: {diff or 'none'}")
sys.exit(1 if diff else 0)
PYEOF
then echo "PASS  load matrix identical"; else echo "FAIL  load matrix differs"; fail=1; fi

echo; echo "## Test 2: scripts, every step"
for s in c1721 T38 c1723 f16_test; do
  for k in $REF $CAND; do key $k $PY tests/parity/run_native.py scripts/$s.xml $O/$s.$k.csv >/dev/null 2>&1; done
  same "$s" $O/$s.$REF.csv $O/$s.$CAND.csv
done

echo; echo "## Test 3: external forces, every step"
$PY tests/extforce/make_aircraft.py 0 1 20
for k in $REF $CAND; do key $k $PY tests/extforce/run_native.py parity $O/ext.$k.csv >/dev/null 2>&1; done
same "c172p + scheduled external force" $O/ext.$REF.csv $O/ext.$CAND.csv

echo; echo "## Test 4: NASA check case 02 (default and AB4 body rates), 301 samples"
for k in $REF $CAND; do
  ( key $k $PY tests/nasa/run_native.py && mv out/Atmos_02_native.csv $O/nasa.$k.csv
    key $k $PY tests/nasa/run_native.py 5 && mv out/Atmos_02_native_rateint5.csv $O/nasa5.$k.csv ) >/dev/null 2>&1
done
same "Atmos_02, default" $O/nasa.$REF.csv $O/nasa.$CAND.csv
same "Atmos_02, AB4" $O/nasa5.$REF.csv $O/nasa5.$CAND.csv

echo; echo "## Review's controlled flights (c172x and f16, Euler and AB4 body rates, 480 Hz, 10 s, 30 properties)"
for k in $REF $CAND; do
  key $k $PY tests/review/parity_probe.py >/dev/null 2>&1
  for m in c172x f16; do for i in 1 5; do mv out/review/$m-$i-native.csv $O/flight-$m-$i.$k.csv; done; done
done
for m in c172x f16; do for i in 1 5; do same "controlled flight $m, rate integrator $i" $O/flight-$m-$i.$REF.csv $O/flight-$m-$i.$CAND.csv; done; done

echo; git status --porcelain --ignored jsbsim-data | grep -v -E 'aircraft/c172p_ext[0-9]+/|scripts/ext_' && { echo "FAIL  files were written into jsbsim-data/"; fail=1; } || echo "jsbsim-data/ clean"
[ $fail = 0 ] && echo "# RESULT: PASS: [$CAND] agrees with [$REF]" || echo "# RESULT: FAIL"
exit $fail
