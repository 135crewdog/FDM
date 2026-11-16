#!/usr/bin/env bash
# Self-test of the patch mechanics shared by scripts/build-wasm.sh and scripts/build-native.sh
# (scripts/lib-jsbsim-src.sh): a new or changed patch must always reach the source tree, its hash must be
# recorded, a patch that does not apply must stop the build, and a wrong Emscripten version must be refused.
#   tests/build/selftest_patches.sh         (exit 1 on any failure)
# It works on a scratch copy of the JSBSim source and a scratch patch directory; nothing in the repository or
# in build/ is changed. The JSBSim source is taken from an existing clone in build/ when there is one (no network).
#
# History: session 03 wrote this test, but .gitignore's "build/" also matched tests/build/, so the file was never
# committed. Session 04 found it missing on a fresh clone and rewrote it from the nine checks recorded in
# results/03-build-selftest.txt. .gitignore now only ignores /build/ at the top level.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
fail=0
check() { if [ "$2" = 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; fail=1; fi; }
for c in "$ROOT"/build/src-native-unpatched "$ROOT"/build/src-wasm-unpatched "$ROOT"/build/src-native-patched "$ROOT"/build/src-wasm-patched; do
  [ -d "$c/.git" ] && { export JSBSIM_REPO="$c"; break; }
done
export PATCH_DIR="$T/patches"; mkdir -p "$PATCH_DIR"
. "$ROOT/scripts/lib-jsbsim-src.sh"
SRC="$T/src"
FILE=src/models/FGPropagate.cpp
mkpatch() {  # mkpatch <marker>: a one-line patch of $FILE made against the pinned source
  ( cd "$SRC" && git reset -q --hard HEAD && sed -i "1s|^|// $1\n|" $FILE && git diff > "$PATCH_DIR/9999-selftest.patch" && git reset -q --hard HEAD )
}

prepare_src "$SRC" unpatched >/dev/null 2>&1
[ "$(git -C "$SRC" rev-parse HEAD)" = "$JSBSIM_COMMIT_PIN" ] && [ -z "$(git -C "$SRC" status --porcelain --untracked-files=no)" ]
check "unpatched tree equals the pinned commit" $?
[ "$(cat "$SRC/.fdm-patches.json")" = "[]" ]; check "unpatched: recorded patch list is empty" $?

mkpatch "selftest marker ONE"
prepare_src "$SRC" patched >/dev/null 2>&1
grep -q "selftest marker ONE" "$SRC/$FILE"; check "a NEW patch reaches an EXISTING source tree (the old script skipped it)" $?
h1="$(sha256sum "$PATCH_DIR/9999-selftest.patch" | cut -d' ' -f1)"
grep -q '"file": "9999-selftest.patch"' "$SRC/.fdm-patches.json" && grep -q "$h1" "$SRC/.fdm-patches.json"; check "the patch name and sha256 are recorded" $?

mkpatch "selftest marker TWO"
prepare_src "$SRC" patched >/dev/null 2>&1
grep -q "selftest marker TWO" "$SRC/$FILE" && ! grep -q "selftest marker ONE" "$SRC/$FILE"; check "a CHANGED patch replaces the old one in the tree" $?
h2="$(sha256sum "$PATCH_DIR/9999-selftest.patch" | cut -d' ' -f1)"
[ "$h1" != "$h2" ] && grep -q "$h2" "$SRC/.fdm-patches.json" && ! grep -q "$h1" "$SRC/.fdm-patches.json"; check "the recorded hash changed with the patch" $?

prepare_src "$SRC" unpatched >/dev/null 2>&1
! grep -q "selftest marker" "$SRC/$FILE" && [ "$(cat "$SRC/.fdm-patches.json")" = "[]" ]; check "the unpatched set removes the patch again" $?

printf 'diff --git a/src/models/FGPropagate.cpp b/src/models/FGPropagate.cpp\n--- a/src/models/FGPropagate.cpp\n+++ b/src/models/FGPropagate.cpp\n@@ -1,2 +1,2 @@\n-this line is not in the file\n+nor is this one\n context that does not exist\n' > "$PATCH_DIR/9999-selftest.patch"
if prepare_src "$SRC" patched >/dev/null 2>&1; then r=1; else r=0; fi
check "a patch that does not apply stops the build" $r

mkdir -p "$T/fakebin"
printf '#!/bin/sh\necho "emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 0.0.1 (fake)"\n' > "$T/fakebin/emcc"
printf '#!/bin/sh\nexit 0\n' > "$T/fakebin/emcmake"
chmod +x "$T/fakebin/emcc" "$T/fakebin/emcmake"
out="$(env -u ALLOW_EMCC_MISMATCH PATH="$T/fakebin:$PATH" WORK="$T/work" OUT="$T/out" PATCH_DIR="$T/none" "$ROOT/scripts/build-wasm.sh" 2>&1)"; rc=$?
[ $rc != 0 ] && echo "$out" | grep -q "pinned is" && [ ! -e "$T/out" ] && [ ! -e "$T/work" ]
check "a different Emscripten version stops scripts/build-wasm.sh" $?

# A failed compile must stop the build scripts, even when an older, valid build output is lying in the build
# directory (REVIEW-codex-04: both scripts used to exit 0, copy the stale output and record the patches as built).
# A fake cmake succeeds at configuring and fails at building.
mkdir -p "$T/failbin"
printf '#!/bin/sh\nif [ "$1" = --build ]; then echo "INJECTED compile failure" >&2; exit 42; fi\nexit 0\n' > "$T/failbin/cmake"
printf '#!/bin/sh\nexec "$@"\n' > "$T/failbin/emcmake"
printf '#!/bin/sh\necho "emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 6.0.13 (fake)"\n' > "$T/failbin/emcc"
chmod +x "$T/failbin/cmake" "$T/failbin/emcmake" "$T/failbin/emcc"
: > "$PATCH_DIR/9999-selftest.patch"; rm -f "$PATCH_DIR/9999-selftest.patch"

W="$T/work-native"; mkdir -p "$W/native-build-patched/tests/jsbsim" "$W/native/patched"
echo stale > "$W/native-build-patched/tests/jsbsim/_jsbsim.stale.so"; echo old > "$W/native/patched/native-info.json"
out="$(PATH="$T/failbin:$PATH" WORK="$W" "$ROOT/scripts/build-native.sh" patched 2>&1)"; rc=$?
[ $rc != 0 ] && echo "$out" | grep -q "native build of 'patched' failed" && [ ! -e "$W/native/patched/native-info.json" ] && [ ! -d "$W/native/patched/jsbsim" ]
check "a failed compile stops scripts/build-native.sh and leaves no answer key (stale module present)" $?

W="$T/work-wasm"; mkdir -p "$W/wasm-patched-wasm" "$T/out-wasm"
echo stale > "$W/wasm-patched-wasm/jsbsim-weh.wasm"; echo stale > "$W/wasm-patched-wasm/jsbsim-weh.mjs"
out="$(env -u ALLOW_EMCC_MISMATCH PATH="$T/failbin:$PATH" WORK="$W" OUT="$T/out-wasm" "$ROOT/scripts/build-wasm.sh" wasm 2>&1)"; rc=$?
[ $rc != 0 ] && echo "$out" | grep -q "WebAssembly build of jsbsim-weh (patched) failed" && [ ! -e "$T/out-wasm/jsbsim-weh.wasm" ] && [ ! -e "$T/out-wasm/build-info.json" ]
check "a failed compile stops scripts/build-wasm.sh and writes no binary or build-info (stale files present)" $?

[ $fail = 0 ] && echo "# all build self-tests passed" || echo "# build self-tests FAILED"
exit $fail
