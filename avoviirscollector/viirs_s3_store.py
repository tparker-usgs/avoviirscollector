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
import os
from .utils import path_from_url, filename_from_url
import boto3
from botocore.exceptions import SSLError
from avoviirscollector import logger


def queue_files(file_list, channels):
    queue = []
    # pattern = re.compile("/({})_".format("|".join(channels)))
    # logger.debug("%d files before pruning", len(file_list))
    # for new_file in file_list:
    #     out_file = path_from_url(self.out_path, new_file.url)
    #     if pattern.search(out_file) and not os.path.exists(out_file):
    #         logger.debug("Queueing %s", new_file.url)
    #         queue.append(new_file)
    #     else:
    #         logger.debug("Skipping %s", new_file.url)
    # logger.info("%d files after pruning", len(queue))
    return queue


def place_file(url, tmp_file):
    s3_bucket_name = tutil.get_env_var("S3_BUCKET")
    logger.debug("Uploading %s to S3 Bucket %s", tmp_file, s3_bucket_name)
    key = filename_from_url(url)
    ca_bundle = tutil.get_env_var("REQUESTS_CA_BUNDLE", None)
    try:
        s3 = boto3.resource("s3", verify=ca_bundle)
        bucket = s3.Bucket(s3_bucket_name)
        bucket.upload_file(tmp_file, key, verify=ca_bundle)
    except SSLError as e:
        logger.debug("TOMP: caught exception")
        logger.error("Caught exception {} using bundle {}", e, ca_bundle)
        logger.error("TOMP: %s", e.__doc__)
        logger.error("TOMP: %s", e.message)
