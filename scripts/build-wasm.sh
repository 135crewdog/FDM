#!/usr/bin/env bash
# Build JSBSim (pinned release) to WebAssembly with Emscripten (pinned version).
#   scripts/build-wasm.sh            # both variants: -fwasm-exceptions (default, jsbsim-weh) and -fexceptions (jsbsim)
#   scripts/build-wasm.sh wasm       # only the default variant
# Needs emsdk activated (source <emsdk>/emsdk_env.sh) at EMSDK_VERSION, plus git and cmake.
# Outputs wasm/bin/jsbsim.{mjs,wasm}, wasm/bin/jsbsim-weh.{mjs,wasm}, wasm/bin/build-info.json.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JSBSIM_TAG="v1.3.3"
EMSDK_VERSION="6.0.13"
VARIANTS="${1:-js wasm}"
WORK="${WORK:-$ROOT/build}"
SRC="$WORK/jsbsim-$JSBSIM_TAG"

command -v emcmake >/dev/null || { echo "error: activate emsdk $EMSDK_VERSION first" >&2; exit 1; }
EMCC_VER="$(emcc --version | head -1 | sed -E 's/.* ([0-9]+\.[0-9]+\.[0-9]+) .*/\1/')"
[ "$EMCC_VER" = "$EMSDK_VERSION" ] || echo "warning: emcc is $EMCC_VER, pinned is $EMSDK_VERSION" >&2

if [ ! -d "$SRC/.git" ]; then
  rm -rf "$SRC"
  git clone -q --depth 1 --branch "$JSBSIM_TAG" https://github.com/JSBSim-Team/jsbsim.git "$SRC"
  for p in "$ROOT"/wasm/patches/*.patch; do
    [ -e "$p" ] || continue
    echo "applying $(basename "$p")"; git -C "$SRC" apply "$p"
  done
fi
JSBSIM_COMMIT="$(git -C "$SRC" rev-parse HEAD)"

mkdir -p "$ROOT/wasm/bin"
for v in $VARIANTS; do
  name=jsbsim; [ "$v" = wasm ] && name=jsbsim-weh
  B="$WORK/wasm-$v"
  emcmake cmake -S "$ROOT/wasm" -B "$B" -DJSBSIM_SOURCE_DIR="$SRC" -DFDM_EH="$v" \
    -DFDM_OUTPUT_NAME="$name" -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build "$B" --target fdm_jsbsim --parallel "$(nproc)"
  cp "$B/$name.mjs" "$B/$name.wasm" "$ROOT/wasm/bin/"
done

BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GIT_REV="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
cat > "$ROOT/wasm/bin/build-info.json" <<JSON
{
  "buildVersion": "fdm-wasm-$(date -u +%Y%m%d.%H%M)",
  "buildDate": "$BUILD_DATE",
  "jsbsimTag": "$JSBSIM_TAG",
  "jsbsimCommit": "$JSBSIM_COMMIT",
  "emscripten": "$EMCC_VER",
  "repoCommitAtBuild": "$GIT_REV",
  "variants": {
    "jsbsim": "-fexceptions (Emscripten JS-based exception handling) on all code",
    "jsbsim-weh": "-fwasm-exceptions (native WebAssembly exception handling) on all code"
  }
}
JSON
ls -l "$ROOT/wasm/bin"
