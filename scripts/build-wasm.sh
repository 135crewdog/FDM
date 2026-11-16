#!/usr/bin/env bash
# Build JSBSim (pinned release) to WebAssembly with Emscripten (pinned version).
#   scripts/build-wasm.sh            # both variants: -fwasm-exceptions (default, jsbsim-weh) and -fexceptions (jsbsim)
#   scripts/build-wasm.sh wasm       # only the default variant
# Environment:
#   PATCHSET=patched (default)  JSBSim plus every wasm/patches/*.patch  -> wasm/bin/
#   PATCHSET=unpatched          JSBSim as released                       -> build/wasm-bin-unpatched/ (never wasm/bin/)
#   OUT=<dir>                   override the output directory
# The source tree is reset and the patches are re-applied on every run (scripts/lib-jsbsim-src.sh), so a new
# or changed patch is never skipped. The patch file hashes and the binaries' hashes go into build-info.json.
# Needs emsdk activated (source <emsdk>/emsdk_env.sh) at exactly EMSDK_VERSION, plus git and cmake.
# Outputs <OUT>/jsbsim.{mjs,wasm}, <OUT>/jsbsim-weh.{mjs,wasm}, <OUT>/build-info.json.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$ROOT/scripts/lib-jsbsim-src.sh"
EMSDK_VERSION="6.0.13"
VARIANTS="${*:-js wasm}"
WORK="${WORK:-$ROOT/build}"
PATCHSET="${PATCHSET:-patched}"
if [ "$PATCHSET" = patched ]; then OUT="${OUT:-$ROOT/wasm/bin}"; else OUT="${OUT:-$WORK/wasm-bin-$PATCHSET}"; fi
SRC="$WORK/src-wasm-$PATCHSET"

command -v emcmake >/dev/null || { echo "error: activate emsdk $EMSDK_VERSION first" >&2; exit 1; }
EMCC_VER="$(emcc --version | head -1 | sed -E 's/.* ([0-9]+\.[0-9]+\.[0-9]+) .*/\1/')"
[ "$EMCC_VER" = "$EMSDK_VERSION" ] || { echo "error: emcc is $EMCC_VER, pinned is $EMSDK_VERSION (set ALLOW_EMCC_MISMATCH=1 only to experiment; do not commit the result)" >&2; [ -n "${ALLOW_EMCC_MISMATCH:-}" ] || exit 1; }

prepare_src "$SRC" "$PATCHSET"
JSBSIM_COMMIT="$(git -C "$SRC" rev-parse HEAD)"

mkdir -p "$OUT"
for v in $VARIANTS; do
  name=jsbsim; [ "$v" = wasm ] && name=jsbsim-weh
  B="$WORK/wasm-$PATCHSET-$v"
  emcmake cmake -S "$ROOT/wasm" -B "$B" -DJSBSIM_SOURCE_DIR="$SRC" -DFDM_EH="$v" \
    -DFDM_OUTPUT_NAME="$name" -DCMAKE_BUILD_TYPE=Release >/dev/null
  # The filter must never hide the build's exit status (REVIEW-codex-04: it used to, so a failed compile
  # could go on to copy stale files and record the patches as built).
  cmake --build "$B" --target fdm_jsbsim --parallel "$(nproc)" | { grep -v -E '^\[ *[0-9]+%\] Building' || true; } \
    || { echo "error: WebAssembly build of $name ($PATCHSET) failed; $OUT not updated" >&2; exit 1; }
  cp "$B/$name.mjs" "$B/$name.wasm" "$OUT/"
done

sha() { [ -f "$1" ] && sha256sum "$1" | cut -d' ' -f1 || echo "not built"; }
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GIT_REV="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
cat > "$OUT/build-info.json" <<JSON
{
  "buildVersion": "fdm-wasm-$(date -u +%Y%m%d.%H%M)",
  "buildDate": "$BUILD_DATE",
  "jsbsimTag": "$JSBSIM_TAG",
  "jsbsimCommit": "$JSBSIM_COMMIT",
  "patchSet": "$PATCHSET",
  "patches": $(patches_json "$PATCHSET"),
  "bindingSha256": "$(sha "$ROOT/wasm/bindings.cpp")",
  "emscripten": "$EMCC_VER",
  "repoCommitAtBuild": "$GIT_REV",
  "variants": {
    "jsbsim": "-fexceptions (Emscripten JS-based exception handling) on all code",
    "jsbsim-weh": "-fwasm-exceptions (native WebAssembly exception handling) on all code"
  },
  "sha256": {
    "jsbsim.wasm": "$(sha "$OUT/jsbsim.wasm")",
    "jsbsim.mjs": "$(sha "$OUT/jsbsim.mjs")",
    "jsbsim-weh.wasm": "$(sha "$OUT/jsbsim-weh.wasm")",
    "jsbsim-weh.mjs": "$(sha "$OUT/jsbsim-weh.mjs")"
  }
}
JSON
ls -l "$OUT"
