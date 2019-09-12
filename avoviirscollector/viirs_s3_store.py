#!/usr/bin/env python

# -*- coding: utf-8 -*-

# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode

# Author(s):
#   Tom Parker <tparker@usgs.gov>

""" Store VIIRS files in a S3 bucket
"""

import tomputils.util as tutil
import re
import boto3
import botocore.exceptions
from avoviirscollector import logger, SATELLITE

BUCKET_NAME = tutil.get_env_var("S3_BUCKET", "UNSET")


def list_files(orbit):
    files = []
    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=f"{SATELLITE}/{orbit}/"):
        if page["KeyCount"] == 0:
            continue
        for file in page["Contents"]:
            files.append(file)

    return files


def queue_files(file_list, channels):
    orbits = {}
    for new_file in file_list:
        orbit = new_file.orbit
        if orbit not in orbits:
            try:
                orbits[orbit] = list_files(orbit)
            except Exception as e:
                print("TOMP SAYS:")
                print(e.with_traceback())
                print("THAT's ALL")

    queue = []
    pattern = re.compile("/({})_".format("|".join(channels)))
    for new_file in file_list:

        orbit = new_file.orbit
        filename = f"{SATELLITE}/{orbit}/{new_file.basename}"
        if pattern.search(filename) and filename not in orbits[orbit]:
            logger.debug("Queueing %s", new_file.url)
            queue.append(new_file)
        else:
            logger.debug("Skipping %s", new_file.url)
    logger.info("%d files after pruning", len(queue))
    return queue


def place_file(file, tmp_file):
    filename = file.basename
    orbit = file.orbit
    logger.debug("Uploading %s to S3 Bucket %s", tmp_file, BUCKET_NAME)
    key = f"{SATELLITE}/{orbit}/{filename}"
    try:
        s3 = boto3.resource("s3")
        bucket = s3.Bucket(BUCKET_NAME)
        bucket.upload_file(tmp_file, key)
    except botocore.exceptions.SSLError as e:
        logger.debug("TOMP: caught exception")
        logger.error("TOMP: %s", e.__doc__)
        logger.error("TOMP: %s", e.message)
