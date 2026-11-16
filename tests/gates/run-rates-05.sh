#!/usr/bin/env bash
# G1, G4, G5 / G5b and G6 read at a step rate the frozen gate files do not list (960 or 1200 Hz), WITHOUT
# editing any frozen file: "new, named readings" (GATES-05.md).
#   tests/gates/run-rates-05.sh <config> <hz>        (run the floor first: G3 compares with it)
# How: the frozen measuring and judging code is copied, byte for byte, into a shadow tree under
# out/shadow05/<hz>/, next to a copy of gates.json and gates-04.json in which ONLY the lists of step rates are
# replaced by [<hz>] (every limit is untouched; the script prints the difference and checks that every other
# frozen file is identical). The frozen runners and evaluators then run there, unchanged.
# Result: results/05-rates-<hz>-gates-<config>.txt (G1 to G6 at that rate) and ...-later-<config>.txt (G5b).
# Not run at these rates: G2b, G3b, G2c (the repeated crash runs); the reports say "not measured" for them.
set -euo pipefail
cd "$(dirname "$0")/../.."
CONFIG="$1"; HZ="$2"
ROOT="$PWD"; PY="$PWD/.venv/bin/python"
export JSBSIM_DEBUG=0
FROZEN="tests/gates/gates.json tests/gates/run_native.py tests/gates/run_wasm.ts tests/gates/evaluate.py tests/gates/fixtures/brick_poi.xml tests/parity/compare.py GATES.md"
FROZEN04="tests/gates/gates-04.json tests/gates/run_native_04.py tests/gates/run_wasm_04.ts tests/gates/evaluate_04.py GATES-04.md tests/gates/gates-04b.json tests/gates/run_native_04b.py tests/gates/run_wasm_04b.ts tests/gates/evaluate_04b.py GATES-04b.md"
if [ -n "$(git status --porcelain -- $FROZEN $FROZEN04)" ] || ! git ls-files --error-unmatch $FROZEN $FROZEN04 >/dev/null 2>&1; then
  echo "error: the frozen gate files must be committed and unchanged:" >&2; git status --short -- $FROZEN $FROZEN04 >&2; exit 1
fi
SH="$ROOT/out/shadow05/$HZ"
mkdir -p "$SH"
rm -rf "$SH/tests" "$SH/src"
cp -r tests src "$SH/"
cp GATES.md GATES-04.md GATES-04b.md tsconfig.json package.json "$SH/"
for l in jsbsim-data wasm build .venv node_modules reference; do [ -e "$SH/$l" ] || ln -s "$ROOT/$l" "$SH/$l"; done
$PY - "$SH" "$HZ" <<'PYEOF'
import json, sys
from pathlib import Path
sh, hz = Path(sys.argv[1]), int(sys.argv[2])
p = sh / "tests/gates/gates.json"; g = json.loads(p.read_text()); old = json.loads(p.read_text())
g["rates_hz"] = [hz]; g["G4"]["rates_hz"] = [hz]; g["G5"]["rates_hz"] = [hz]; g["G5"]["report_only_rates_hz"] = []; g["G6"]["hz"] = hz
p.write_text(json.dumps(g, indent=1))
q = sh / "tests/gates/gates-04.json"; g4 = json.loads(q.read_text()); old4 = json.loads(q.read_text())
g4["judged_rates_hz"] = [hz]; g4["reported_rates_hz"] = []
q.write_text(json.dumps(g4, indent=1))
def diff(a, b, path=""):
    out = []
    for k in a:
        if isinstance(a[k], dict):
            out += diff(a[k], b[k], path + k + ".")
        elif a[k] != b[k]:
            out.append(f"{path}{k}: {a[k]} -> {b[k]}")
    return out
changed = diff(old, g) + ["gates-04.json " + x for x in diff(old4, g4)]
allowed = {"rates_hz", "G4.rates_hz", "G5.rates_hz", "G5.report_only_rates_hz", "G6.hz", "gates-04.json judged_rates_hz", "gates-04.json reported_rates_hz"}
assert all(c.split(":")[0] in allowed for c in changed), changed
(sh / "shadow-diff.txt").write_text("\n".join(changed) + "\n")
PYEOF
for f in $FROZEN $FROZEN04; do
  case "$f" in tests/gates/gates.json|tests/gates/gates-04.json) ;; *) cmp -s "$f" "$SH/$f" || { echo "error: $f differs in the shadow tree" >&2; exit 1; } ;; esac
done
SRC="$($PY -c "import json,sys; print(json.load(open('tests/gates/configs.json'))[sys.argv[1]]['source'])" "$CONFIG")"
if [ "$SRC" = patched ]; then BIN="$ROOT/wasm/bin"; else BIN="$ROOT/build/wasm-bin-unpatched"; fi
cd "$SH"
O="out/gates/$CONFIG"; mkdir -p "$O"
jobs=(
 "PYTHONPATH=$ROOT/build/native/$SRC $PY tests/gates/run_native.py $CONFIG ground nasa rigid flights > $O/native.log 2>&1"
 "JSBSIM_BIN=$BIN JSBSIM_VARIANT=jsbsim-weh npx tsx tests/gates/run_wasm.ts $CONFIG ground nasa rigid flights > $O/wasm-jsbsim-weh.log 2>&1"
 "JSBSIM_BIN=$BIN JSBSIM_VARIANT=jsbsim npx tsx tests/gates/run_wasm.ts $CONFIG flights > $O/wasm-jsbsim.log 2>&1"
 "PYTHONPATH=$ROOT/build/native/$SRC $PY tests/gates/run_native_04.py $CONFIG rigidb > $O/native04.rigidb.log 2>&1"
 "JSBSIM_BIN=$BIN JSBSIM_VARIANT=jsbsim-weh npx tsx tests/gates/run_wasm_04.ts $CONFIG rigidb > $O/wasm04.rigidb.log 2>&1"
)
if ! printf '%s\n' "${jobs[@]}" | xargs -P "${JOBS:-$(nproc)}" -I{} bash -c '{}'; then
  echo "error: a runner failed; see $SH/$O/*.log" >&2; tail -n 3 $O/*.log >&2; exit 1
fi
HEAD="# NEW READING (session 05): the frozen gates read at $HZ Hz. Frozen code and limits unchanged; only these rate lists differ in the shadow copy: $(tr '\n' ';' < shadow-diff.txt)"
{ echo "$HEAD"; $PY tests/gates/evaluate.py "$CONFIG"; } > "$ROOT/results/${SESSION:-05}-rates-$HZ-gates-$CONFIG.txt"
{ echo "$HEAD"; $PY tests/gates/evaluate_04.py "$CONFIG"; } > "$ROOT/results/${SESSION:-05}-rates-$HZ-later-$CONFIG.txt"
grep -E "^\| (pass|FAIL|\*\*)|Verdict|verdict" "$ROOT/results/${SESSION:-05}-rates-$HZ-gates-$CONFIG.txt" | tail -n 3
