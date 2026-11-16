#!/usr/bin/env bash
# Build native JSBSim (pinned release, Python module) from source: the answer key for our WebAssembly build
# once JSBSim is patched (pip's jsbsim==1.3.3 cannot contain our patches).
#   scripts/build-native.sh                 # both: unpatched and patched (= wasm/patches/*.patch)
#   scripts/build-native.sh unpatched       # only one
# Output: build/native/<set>/jsbsim/ (a Python package) and build/native/<set>/native-info.json.
# Use it with:  PYTHONPATH=build/native/<set> .venv/bin/python ...   (it shadows the pip package)
# Needs: git, cmake, a C++ compiler, .venv with cython and setuptools (pip install -r requirements.txt).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$ROOT/scripts/lib-jsbsim-src.sh"
WORK="${WORK:-$ROOT/build}"
PY="${PY:-$ROOT/.venv/bin/python}"
SETS="${*:-unpatched patched}"

for set in $SETS; do
  SRC="$WORK/src-native-$set"
  B="$WORK/native-build-$set"
  OUT="$WORK/native/$set"
  prepare_src "$SRC" "$set"
  cmake -S "$SRC" -B "$B" -DCMAKE_BUILD_TYPE=Release -DBUILD_PYTHON_MODULE=ON -DBUILD_DOCS=OFF \
    -DBUILD_SHARED_LIBS=OFF -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DPython3_EXECUTABLE="$PY" -DPython3_FIND_VIRTUALENV=ONLY >/dev/null
  # The filter must never hide the build's exit status (it used to: "... | grep ... || true" let a failed
  # compile go on to copy a stale module and record the patches as built; REVIEW-codex-04). With pipefail the
  # pipeline fails when cmake fails; the braces keep grep's "no lines left" from counting as a failure.
  rm -rf "$OUT"
  cmake --build "$B" --target _jsbsim --parallel "$(nproc)" | { grep -v -E '^\[ *[0-9]+%\] Building' || true; } \
    || { echo "error: native build of '$set' failed; no answer key written to $OUT" >&2; exit 1; }
  mkdir -p "$OUT"
  cp -r "$B/tests/jsbsim" "$OUT/jsbsim"
  SO="$(ls "$OUT"/jsbsim/_jsbsim*.so)"
  cat > "$OUT/native-info.json" <<JSON
{
  "set": "$set",
  "jsbsimTag": "$JSBSIM_TAG",
  "jsbsimCommit": "$(git -C "$SRC" rev-parse HEAD)",
  "patches": $(patches_json "$set"),
  "compiler": "$(c++ --version | head -1)",
  "python": "$("$PY" -V 2>&1)",
  "module": "$(basename "$SO")",
  "moduleSha256": "$(sha256sum "$SO" | cut -d' ' -f1)",
  "buildDate": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
  PYTHONPATH="$OUT" JSBSIM_DEBUG=0 "$PY" -c "import jsbsim; print('built', '$set', jsbsim.__version__, jsbsim.__file__)"
done
