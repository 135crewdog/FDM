#!/usr/bin/env bash
# Runs every test against the binaries in dist-wasm/ and build/native. Each test writes its result file to
# results/; the full console logs go to build/test-logs/ (not committed).
# Run scripts/build.sh first. Exit code 0 only if everything passed.
#   scripts/run-all-tests.sh            everything
#   scripts/run-all-tests.sh quick      without the script sweep and the build self-test (slow)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODE="${1:-all}"
mkdir -p results build/tmp/out build/test-logs
failed=()
run() { # name, command...
  local name="$1"; shift
  echo "== $name"
  if "$@" > "build/test-logs/$name.log" 2>&1; then echo "   ok"; else echo "   FAILED (see build/test-logs/$name.log)"; failed+=("$name"); fi
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
# The committed page must be the one the build script produces from the committed binaries and sources.
run page-is-current bash -c 'cp test-page/build-id.txt build/tmp/page-id.before && node scripts/build-page.mjs && cmp test-page/build-id.txt build/tmp/page-id.before && git diff --quiet -- test-page'
run page-chromium node tests/page.chromium.mjs
run typecheck npx tsc --noEmit
echo
kept="$(grep -c '^  sweep ' results/parity.txt || true)"
if [ "${#failed[@]}" -eq 0 ]; then
  echo "NO NEW FAILURE. Frozen lines kept as failed in the parity sweep: $kept (listed in results/parity.txt and REPORT.md part 3)."
else
  echo "FAILED: ${failed[*]}"; exit 1
fi
