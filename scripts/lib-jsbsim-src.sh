# Shared by scripts/build-wasm.sh and scripts/build-native.sh (source it; do not run it).
# One pinned JSBSim source, and one way of applying our patches, for the WebAssembly build and
# for the native answer key.
JSBSIM_TAG="v1.3.3"
JSBSIM_COMMIT_PIN="66f7fafc07fe13e7ede9db20873030fed2881713"
JSBSIM_REPO="${JSBSIM_REPO:-https://github.com/JSBSim-Team/jsbsim.git}"
PATCH_DIR="${PATCH_DIR:-$ROOT/wasm/patches}"   # overridable only for tests/build/selftest_patches.sh

# patch_files <set>: the patch files of a patch set, one per line, in the order applied.
#   patched   = every wasm/patches/*.patch (sorted by name)
#   unpatched = none
patch_files() {
  case "$1" in
    unpatched) ;;
    patched) for p in "$PATCH_DIR"/*.patch; do [ -e "$p" ] && echo "$p"; done ;;
    *) echo "error: unknown patch set '$1' (use patched or unpatched)" >&2; return 1 ;;
  esac
  return 0
}

# patches_json <set>: JSON array [{"file": ..., "sha256": ...}] of the patches in the set.
patches_json() {
  local first=1 p
  printf '['
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    [ $first = 1 ] || printf ', '
    first=0
    printf '{"file": "%s", "sha256": "%s"}' "$(basename "$p")" "$(sha256sum "$p" | cut -d' ' -f1)"
  done < <(patch_files "$1")
  printf ']'
}

# prepare_src <dir> <set>: make <dir> exactly JSBSim at the pinned commit plus the patch set.
# The tree is reset and the patches are re-applied on EVERY call, so a new or changed patch can
# never be skipped (only the patched files get new timestamps, so rebuilds stay incremental).
prepare_src() {
  local src="$1" set="$2" p
  if [ ! -d "$src/.git" ]; then
    rm -rf "$src"
    git -c advice.detachedHead=false clone -q --depth 1 --branch "$JSBSIM_TAG" "$JSBSIM_REPO" "$src" 2>/dev/null || git -c advice.detachedHead=false clone -q --branch "$JSBSIM_TAG" "$JSBSIM_REPO" "$src"
  fi
  local head; head="$(git -C "$src" rev-parse HEAD)"
  [ "$head" = "$JSBSIM_COMMIT_PIN" ] || { echo "error: $src is at $head, pinned is $JSBSIM_COMMIT_PIN" >&2; return 1; }
  git -C "$src" reset -q --hard HEAD
  git -C "$src" clean -fdq
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    echo "applying $(basename "$p") to $src"
    git -C "$src" apply --whitespace=nowarn "$p" || { echo "error: $(basename "$p") does not apply" >&2; return 1; }
  done < <(patch_files "$set")
  patches_json "$set" > "$src/.fdm-patches.json"
}
