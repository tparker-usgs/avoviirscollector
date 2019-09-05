#!/usr/bin/env python

# -*- coding: utf-8 -*-

# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode

# Author(s):
#   Tom Parker <tparker@usgs.gov>

"""Retrieve files from GINA
"""


import json
import signal
import logging
import os.path
import os
from datetime import timedelta, datetime
import pycurl
import tomputils.util as tutil
import hashlib
import socket
from io import BytesIO
from .viirs import Viirs
import h5py
from tomputils.downloader import Downloader
import multiprocessing_logging
from multiprocessing import Process
from single import Lock
import avoviirscollector.viirs_filesystem_store
import avoviirscollector.viirs_s3_store
from .utils import path_from_url
from avoviirscollector import BASE_DIR, logger, SATELLITE, CHANNELS

GINA_URL = (
    "http://nrt-status.gina.alaska.edu/products.json"
    + "?action=index&commit=Get+Products&controller=products"
)


class MirrorGina(object):
    def __init__(self):
        self.tmp_path = os.path.join(BASE_DIR, "tmp")
        self.connection_count = int(tutil.get_env_var("NUM_GINA_CONNECTIONS"))
        self.file_store_type = tutil.get_env_var("VIIRS_FILE_STORE_TYPE")
        if self.file_store_type == "S3":
            self.file_store = avoviirscollector.viirs_s3_store
        elif self.file_store_type == "local":
            self.file_store = avoviirscollector.viirs_filesystem_store
        else:
            tutil.exit_with_error("Missing VIIRS_FILE_STORE_TYPE env var")

        # We should ignore SIGPIPE when using pycurl.NOSIGNAL - see
        # the libcurl tutorial for more info.
        try:
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        except ImportError:
            pass

        self.hostname = socket.gethostname()

    def get_file_list(self):
        logger.debug("fetching files")
        backfill = timedelta(days=int(tutil.get_env_var("GINA_BACKFILL_DAYS")))
        end_date = datetime.utcnow() + timedelta(days=1)
        start_date = end_date - backfill

        url = GINA_URL
        url += "&start_date=" + start_date.strftime("%Y-%m-%d")
        url += "&end_date=" + end_date.strftime("%Y-%m-%d")
        url += "&sensors[]=viirs"
        url += "&processing_levels[]=level1"
        url += "&facilities[]=" + tutil.get_env_var("VIIRS_FACILITY")
        url += "&satellites[]=" + SATELLITE
        logger.debug("URL: %s", url)
        buf = BytesIO()

        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.WRITEFUNCTION, buf.write)
        c.perform()

        files = []
        for file in json.loads(buf.getvalue()):
            files.append(Viirs(file["url"], file["md5sum"]))

        buf.close()

        logger.info("Found %s files", len(files))
        return files

    def create_multi(self):
        m = pycurl.CurlMulti()
        m.handles = []
        for i in range(self._num_conn):
            logger.debug("creating curl object")
            c = pycurl.Curl()
            c.fp = None
            c.setopt(pycurl.FOLLOWLOCATION, 1)
            c.setopt(pycurl.MAXREDIRS, 5)
            c.setopt(pycurl.CONNECTTIMEOUT, 30)
            c.setopt(pycurl.TIMEOUT, 600)
            c.setopt(pycurl.NOSIGNAL, 1)
            m.handles.append(c)

        return m

    def fetch_files(self):
        file_list = self.get_file_list()
        file_queue = self.file_store.queue_files(file_list, CHANNELS)

        # sort to retrieve geoloc files first. I should run frequently
        # enough that getting stuck wile retrieving several orbits
        # shouldn't be a problem.
        file_queue.sort()

        for file in file_queue:
            url = file.url
            tmp_file = path_from_url(self.tmp_path, url)
            logger.debug("Fetching %s from %s" % (tmp_file, url))
            dl = Downloader(max_con=self.connection_count)
            dl.fetch(url, tmp_file)
            file_md5 = hashlib.md5(open(tmp_file, "rb").read()).hexdigest()
            logger.debug("MD5 %s : %s" % (file.md5, file_md5))

            if file.md5 == file_md5:
                try:
                    check = h5py.File(tmp_file, "r")
                    check.close()
                except Exception as e:
                    logger.info("Bad HDF5 file %s", tmp_file)
                    logger.info(e)
                    os.unlink(tmp_file)
                else:
                    self.file_store.place_file(url, tmp_file)
            else:
                size = os.path.getsize(tmp_file)
                msg = "Bad checksum: %s != %s (%d bytes)"
                logger.info(msg, file_md5, file.md5, size)
                os.unlink(tmp_file)


def aquire_lock():
    dir = os.path.join(BASE_DIR, "tmp")
    if not os.path.exists(dir):
        os.mkdir(dir)
    filename = "{}_{}.lock".format(SATELLITE, "|".join(CHANNELS))
    filename = os.path.join(BASE_DIR, "tmp", filename)
    lock = Lock(filename)
    gotlock, pid = lock.lock_pid()

    return (gotlock, lock)


def main():
    # let ctrl-c work as it should.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # exit quickly if queue is already running
    (gotlock, lock) = aquire_lock()
    if not gotlock:
        tutil.exit_with_error(
            "Queue {} locked, skipping".format(SATELLITE + "-".join(CHANNELS))
        )
        return

    try:
        mirror_gina = MirrorGina()
        mirror_gina.fetch_files()
    finally:
        logger.info("All done with queue.")

        if gotlock:
            try:
                lock.unlock()
            except AttributeError:
                pass

    logger.debug("That's all for now, bye.")
    logging.shutdown()


if __name__ == "__main__":
    main()
