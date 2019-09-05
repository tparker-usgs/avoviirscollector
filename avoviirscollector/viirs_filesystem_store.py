#!/usr/bin/env python

# -*- coding: utf-8 -*-

# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode

# Author(s):
#   Tom Parker <tparker@usgs.gov>

""" Store VIIRS files in a local filesystem path
"""

import tomputils.util as tutil
import re
import os
from .utils import path_from_url
from shutil import copyfile
from avoviirscollector import BASE_DIR, logger

OUT_PATH = os.path.join(BASE_DIR, "sdr")


def queue_files(file_list, channels):
    queue = []
    pattern = re.compile("/({})_".format("|".join(channels)))
    logger.debug("%d files before pruning", len(file_list))
    for new_file in file_list:
        out_file = path_from_url(OUT_PATH, new_file.url)
        if pattern.search(out_file) and not os.path.exists(out_file):
            logger.debug("Queueing %s", new_file.url)
            queue.append(new_file)
        else:
            logger.debug("Skipping %s", new_file.url)
    logger.info("%d files after pruning", len(queue))
    return queue


def place_file(url, tmp_file):
    if not os.path.exists(OUT_PATH):
        os.mkdir(OUT_PATH)

    out_file = path_from_url(OUT_PATH, url)
    msg = "File looks good. Moving {} to {}".format(tmp_file, out_file)
    logger.info(msg)
    copyfile(tmp_file, out_file)
