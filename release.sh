#!/bin/bash

set -x
set -e # Exit on error

PACKAGE=$(basename "$PWD")
mkdir dist
TEMPDIR="$(mktemp -d)"
read VERSION < NEWS
echo "$PACKAGE-$VERSION: $TEMPDIR"
hg archive "$TEMPDIR/$PACKAGE-$VERSION"
DIR="$PWD"
cd "$TEMPDIR"
rm "$PACKAGE-$VERSION/release.sh"
rm "$PACKAGE-$VERSION"/.hg*
tar czf "$DIR/dist/$PACKAGE-$VERSION.tar.gz" "$PACKAGE-$VERSION"
tar cjf "$DIR/dist/$PACKAGE-$VERSION.tar.bz2" "$PACKAGE-$VERSION"
cd "$PACKAGE-$VERSION"
./setup.py bdist_rpm
mv "dist/$PACKAGE-$VERSION-1."{noarch,src}.rpm "$DIR/dist"
rm -fr "$TEMPDIR"
