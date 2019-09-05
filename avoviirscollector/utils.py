#!/usr/bin/env python

# -*- coding: utf-8 -*-

# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode

# Author(s):
#   Tom Parker <tparker@usgs.gov>

""" simple utility functions
"""

import os
from urllib.parse import urlparse
import posixpath


def filename_from_url(url):
    path = urlparse(url).path
    return posixpath.basename(path)


def path_from_url(base, url):
    return os.path.join(base, filename_from_url(url))
