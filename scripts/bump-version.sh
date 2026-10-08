#!/bin/sh
# Start a new release: bumps app/VERSION and adds a changelog stub.
#
#   scripts/bump-version.sh minor   # 2.5 -> 2.6  (single point release)
#   scripts/bump-version.sh major   # 2.5 -> 3.0  (major release)
#
# Fill in the notes in app/CHANGELOG.md, commit, and merge to main.
# CI then tags vX.Y, builds ghcr.io/…/spazcat-stodo:vX.Y and publishes a GitHub Release.
set -e
cd "$(dirname "$0")/.."

cur=$(tr -d '[:space:]' < app/VERSION)
major=${cur%%.*}
minor=${cur#*.}

case "$1" in
  major)       new="$((major + 1)).0" ;;
  minor|point) new="$major.$((minor + 1))" ;;
  *) echo "usage: $0 major|minor" >&2; exit 1 ;;
esac

if grep -qF "## [$new]" app/CHANGELOG.md; then
  echo "app/CHANGELOG.md already has an entry for $new" >&2
  exit 1
fi

today=$(date +%Y-%m-%d)
printf '%s\n' "$new" > app/VERSION
awk -v hdr="## [$new] - $today" '
  !done && /^## \[/ { print hdr; print "### Added"; print "- TODO"; print ""; print "### Fixed"; print "- TODO"; print ""; done = 1 }
  { print }
' app/CHANGELOG.md > app/CHANGELOG.md.tmp
mv app/CHANGELOG.md.tmp app/CHANGELOG.md

echo "Bumped $cur -> $new."
echo "Replace the TODO lines in app/CHANGELOG.md (drop sections you don't need), then commit and merge to main."
