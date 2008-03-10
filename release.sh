#!/bin/bash

set -x
set -e # Exit on error

PACKAGE=$(basename "$PWD")
mkdir dist
TEMPDIR="$(mktemp -d)"
VERSION=$(python -c "from $PACKAGE.version import VERSION; print VERSION")
echo "$PACKAGE-$VERSION: $TEMPDIR"
mkdir "$TEMPDIR/$PACKAGE-$VERSION"
git archive HEAD | (cd "$TEMPDIR/$PACKAGE-$VERSION" && tar vx)
DIR="$PWD"
cd "$TEMPDIR"
rm "$PACKAGE-$VERSION/release.sh"
tar czf "$DIR/dist/$PACKAGE-$VERSION.tar.gz" "$PACKAGE-$VERSION"
tar cjf "$DIR/dist/$PACKAGE-$VERSION.tar.bz2" "$PACKAGE-$VERSION"
cd "$PACKAGE-$VERSION"
./setup.py bdist_rpm
mv "dist/$PACKAGE-$VERSION-1."{noarch,src}.rpm "$DIR/dist"
rm -fr "$TEMPDIR"
