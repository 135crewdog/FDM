#!/usr/bin/env bash
# Checks that jsbsim-data/ is byte-identical to the pinned upstream commit.
# Method: build a git tree object from the files on disk (in a throwaway index, so .gitignore and the real
# index play no part) and compare its id with the upstream tree id recorded in pins.env.
# With --committed it checks the tree stored in HEAD instead of the files on disk.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/pins.env"
cd "$ROOT"
MODE="${1:-disk}"
fail=0
check() { # name expected actual
  if [ "$2" = "$3" ]; then echo "ok    $1 $3"; else echo "FAIL  $1 expected $2 got $3"; fail=1; fi
}
tree_on_disk() { # folder relative to jsbsim-data
  local tmp; tmp="$(mktemp)"; rm -f "$tmp"
  ( cd "jsbsim-data/$1" && GIT_INDEX_FILE="$tmp" git --git-dir="$ROOT/.git" --work-tree=. add -f -A . \
      && GIT_INDEX_FILE="$tmp" git --git-dir="$ROOT/.git" write-tree )
  rm -f "$tmp"
}
for d in aircraft engine systems scripts check_cases/NASA_EOM_2015; do
  var="TREE_$(echo "$d" | tr '/' '_')"
  if [ "$MODE" = "--committed" ]; then actual="$(git rev-parse "HEAD:jsbsim-data/$d")"
  else actual="$(tree_on_disk "$d")"; fi
  check "$d" "${!var}" "$actual"
done
if [ "$MODE" = "--committed" ]; then actual="$(git rev-parse HEAD:jsbsim-data/COPYING)"
else actual="$(git hash-object jsbsim-data/COPYING)"; fi
check COPYING "$BLOB_COPYING" "$actual"
[ "$(sed -n 2p jsbsim-data/REF)" = "$JSBSIM_COMMIT" ] && echo "ok    REF" || { echo "FAIL  REF"; fail=1; }
exit $fail
