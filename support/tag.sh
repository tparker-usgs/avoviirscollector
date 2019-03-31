#!/bin/sh

VERSION=`python -c "import rscollectors; print(rscollectors.__version__)"`
echo Tagging release $VERSION
git add rscollectors/__init__.py
git commit -m 'version bump'
git push \
&& git tag $VERSION \
&& git push --tags
