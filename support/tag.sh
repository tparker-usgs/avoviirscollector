#!/bin/sh

git add rsCollectors/__init__.py
git commit -m 'version bump'
git push \
&& git tag `cat VERSION` \
&& git push --tags
