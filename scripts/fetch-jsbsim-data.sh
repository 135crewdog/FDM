#!/usr/bin/env bash
# Refresh the JSBSim data folders committed in ./jsbsim-data from a JSBSim release tag.
# The data IS committed (private, non-commercial project); run this only to change version:
#   scripts/fetch-jsbsim-data.sh v1.3.3
set -euo pipefail
REF="${1:-v1.3.3}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/jsbsim-data"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git -C "$TMP" init -q
git -C "$TMP" remote add origin https://github.com/JSBSim-Team/jsbsim.git
git -C "$TMP" sparse-checkout set --no-cone /aircraft/ /engine/ /systems/ /scripts/ /check_cases/NASA_EOM_2015/ /COPYING
git -C "$TMP" fetch -q --depth 1 --filter=blob:none origin "refs/tags/$REF"
git -C "$TMP" checkout -q FETCH_HEAD
rm -rf "$DEST"; mkdir -p "$DEST/check_cases"
cp -r "$TMP"/aircraft "$TMP"/engine "$TMP"/systems "$TMP"/scripts "$DEST"/
cp -r "$TMP"/check_cases/NASA_EOM_2015 "$DEST"/check_cases/
cp "$TMP"/COPYING "$DEST"/
{ echo "$REF"; git -C "$TMP" rev-parse HEAD; } > "$DEST/REF"
echo "JSBSim data ($REF) -> $DEST"
