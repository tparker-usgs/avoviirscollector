#!/bin/sh

VERSION=`python -c "import rsCollectors; print(rsCollectors.__version__)"`
echo Tagging release $VERSION
git add rsCollectors/__init__.py
git commit -m 'version bump'
git push \
&& git tag $VERSION \
&& git push --tags
