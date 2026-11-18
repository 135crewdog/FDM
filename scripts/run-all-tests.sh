#!/usr/bin/env bash
# Runs every test against the binaries in dist-wasm/ and build/native. Raw output goes to results/.
# Run scripts/build.sh first. Exit code 0 only if everything passed.
#   scripts/run-all-tests.sh            everything
#   scripts/run-all-tests.sh quick      without the script sweep and the build self-test (slow)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODE="${1:-all}"
mkdir -p results build/tmp/out
failed=()
run() { # name, command...
  local name="$1"; shift
  echo "== $name"
  if "$@" > "results/$name.log.txt" 2>&1; then echo "   ok"; else echo "   FAILED (see results/$name.log.txt)"; failed+=("$name"); fi
}
# The binaries under test are the ones build-info.json describes.
run binaries-match-build-info node scripts/check-binaries.mjs
run data-integrity scripts/check-data.sh --committed
node -e "import('./tests/lib/fixtures.ts').then(m => m.prepareFixtures())"
run wrapper-native ./build/native/fdm_native --selftest "$ROOT/jsbsim-data" "$ROOT/build/fixtures" "$ROOT/build/tmp/out"
run compare-selftest node --test tests/compare-selftest.test.ts
run wrapper-wasm node --test tests/wrapper.test.ts
run loop node --test tests/loop.test.ts
run ground node --test tests/ground.test.ts
run load node --test tests/load.test.ts
run forces node --test tests/forces.test.ts
if [ "$MODE" = "all" ]; then
  run parity node --test tests/parity.test.ts
  run build-selftest scripts/selftest-build.sh
else
  PARITY_QUICK=1 run parity-quick node --test tests/parity.test.ts
fi
run typecheck npx tsc --noEmit
echo
if [ "${#failed[@]}" -eq 0 ]; then echo "ALL PASSED"; else echo "FAILED: ${failed[*]}"; exit 1; fi
