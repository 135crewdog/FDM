#!/usr/bin/env bash
# Download JSBSim data folders (aircraft, engine, systems, scripts, check_cases)
# into ./jsbsim-data (git-ignored). Never commit these files.
#
# Default ref = the exact JSBSim commit that @0x62/jsbsim-wasm@1.2.4-beta.4 was
# built from (see release/publish-metadata.json in github.com/0x62/jsbsim-wasm).
# The package is labelled "1.2.4" but the binary reports "1.2.5.dev1" and the
# commit is on master, NOT on the v1.2.4 release tag. Pass another ref to override:
#   scripts/fetch-jsbsim-data.sh v1.2.4
set -euo pipefail
REF="${1:-1a2e114d79af2430db02a4f7a4a85328cdc5d403}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/jsbsim-data"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git -C "$TMP" init -q
git -C "$TMP" remote add origin https://github.com/JSBSim-Team/jsbsim.git
git -C "$TMP" config core.sparseCheckout true
git -C "$TMP" sparse-checkout set --no-cone /aircraft/ /engine/ /systems/ /scripts/ /check_cases/ /src/models/FGExternalForce.h /COPYING
git -C "$TMP" fetch -q --depth 1 --filter=blob:none origin "$REF"
git -C "$TMP" checkout -q FETCH_HEAD
rm -rf "$DEST"; mkdir -p "$DEST"
cp -r "$TMP"/aircraft "$TMP"/engine "$TMP"/systems "$TMP"/scripts "$TMP"/check_cases "$DEST"/
cp "$TMP"/src/models/FGExternalForce.h "$TMP"/COPYING "$DEST"/
echo "$REF" > "$DEST/REF"

# NASA EOM 2015 check case 02 (tumbling brick) only exists from JSBSim v1.3.2 on.
NASA_REF="${NASA_REF:-v1.3.2}"
TMP2="$(mktemp -d)"
git -C "$TMP2" init -q
git -C "$TMP2" remote add origin https://github.com/JSBSim-Team/jsbsim.git
git -C "$TMP2" sparse-checkout set --no-cone /check_cases/NASA_EOM_2015/
git -C "$TMP2" fetch -q --depth 1 --filter=blob:none origin "refs/tags/$NASA_REF"
git -C "$TMP2" checkout -q FETCH_HEAD
cp -r "$TMP2"/check_cases/NASA_EOM_2015 "$DEST"/check_cases/
rm -rf "$TMP2"
echo "$NASA_REF" > "$DEST/check_cases/NASA_EOM_2015/REF"
echo "JSBSim data ($REF) -> $DEST"
