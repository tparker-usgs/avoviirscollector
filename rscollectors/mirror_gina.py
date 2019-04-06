#!/usr/bin/env python

# -*- coding: utf-8 -*-

# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode

# Author(s):
#   Tom Parker <tparker@usgs.gov>

"""Retrieve files from GINA
"""


import re
import json
import signal
import logging
import os.path
import os
import posixpath
from datetime import timedelta, datetime
from urllib.parse import urlparse
import pycurl
import tomputils.util as tutil
import hashlib
import socket
from io import BytesIO
from rscollectors import viirs
import h5py
from tomputils.downloader import Downloader
import multiprocessing_logging
from functools import cmp_to_key
from multiprocessing import Process
from single import Lock


GINA_URL = ('http://nrt-status.gina.alaska.edu/products.json'
            + '?action=index&commit=Get+Products&controller=products')


class MirrorGina(object):
    def __init__(self, base_dir, config):
        self.base_dir = base_dir
        self.tmp_path = os.path.join(base_dir, 'tmp')
        self.config = config
        self.out_path = os.path.join(self.base_dir, self.config['out_path'])
        self.connection_count = tutil.get_env_var('NUM_GINA_CONNECTIONS')

        # We should ignore SIGPIPE when using pycurl.NOSIGNAL - see
        # the libcurl tutorial for more info.
        try:
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        except ImportError:
            pass

        self.hostname = socket.gethostname()

    def get_file_list(self):
        logger.debug("fetching files")
        backfill = timedelta(days=tutil.get_env_var('GINA_BACKFILL_DAYS'))
        end_date = datetime.utcnow() + timedelta(days=1)
        start_date = end_date - backfill

        url = GINA_URL
        url += '&start_date=' + start_date.strftime('%Y-%m-%d')
        url += '&end_date=' + end_date.strftime('%Y-%m-%d')
        url += '&sensors[]=' + self.config['sensor']
        url += '&processing_levels[]=' + self.config['level']
        url += '&facilities[]=' + tutil.get_env_var('VIIRS_FACILITY')
        url += '&satellites[]=' + self.config['satellite']
        logger.debug("URL: %s", url)
        buf = BytesIO()

        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.WRITEFUNCTION, buf.write)
        c.perform()

        files = json.loads(buf.getvalue())
        buf.close()

        logger.info("Found %s files", len(files))
        files.sort(key=cmp_to_key(lambda a, b:
                                  viirs.filename_comparator(a['url'],
                                                            b['url'])))
        return files

    def queue_files(self, file_list):
        queue = []
        pattern = re.compile(self.config['match'])
        logger.debug("%d files before pruning", len(file_list))
        for new_file in file_list:
            out_file = path_from_url(self.out_path, new_file['url'])
            # tmp_path = self.path_from_url(self.tmp_path, new_file['url'])

            if pattern.search(out_file) and not os.path.exists(out_file):
                logger.debug("Queueing %s", new_file['url'])
                queue.append(new_file)
            else:
                logger.debug("Skipping %s", new_file['url'])

        logger.info("%d files after pruning", len(queue))
        return queue

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
        file_queue = self.queue_files(file_list)

        for file in file_queue:
            url = file['url']
            tmp_file = path_from_url(self.tmp_path, url)
            logger.debug("Fetching %s from %s" % (tmp_file, url))
            dl = Downloader(max_con=self.connection_count)
            dl.fetch(url, tmp_file)
            md5 = file['md5sum']
            file_md5 = hashlib.md5(open(tmp_file, 'rb').read()).hexdigest()
            logger.debug("MD5 %s : %s" % (md5, file_md5))

            if md5 == file_md5:
                try:
                    h5py.File(tmp_file, 'r')
                except Exception as e:
                    logger.info('Bad HDF5 file %s', tmp_file)
                    logger.info(e)
                    os.unlink(tmp_file)
                else:
                    out_file = path_from_url(self.out_path, url)
                    msg = "File looks good. Moving {} to {}".format(tmp_file,
                                                                    out_file)
                    logger.info(msg)
                    os.rename(tmp_file, out_file)
            else:
                size = os.path.getsize(tmp_file)
                msg = 'Bad checksum: %s != %s (%d bytes)'
                logger.info(msg, file_md5, md5, size)
                os.unlink(tmp_file)


def path_from_url(base, url):
    path = urlparse(url).path
    filename = posixpath.basename(path)

    return os.path.join(base, filename)


def poll_queue(config):
    base_dir = tutil.get_env_var('RSPROCESSING_BASE')
    logger.debug("RSPROCESSING_BASE: %s", base_dir)

    lock_file = os.path.join(base_dir, "tmp", "{}.lock".format(config['name']))

    lock = Lock(lock_file)
    gotlock, pid = lock.lock_pid()
    if not gotlock:
        logger.info("Queue {} locked, skipping".format(config['name']))
        return

    try:
        logger.info("Launching queueu: %s", config['name'])
        mirror_gina = MirrorGina(base_dir, config)
        mirror_gina.fetch_files()
    finally:
        logger.info("All done with queue %s.", config['name'])
        for handler in logger.handlers:
            handler.flush()

        if gotlock:
            try:
                lock.unlock()
            except AttributeError:
                pass


def poll_queues():
    procs = []
    for queue in global_config['queues']:
        if 'disabled' in queue and queue['disabled']:
            logger.info("Queue %s is disabled, skiping it.", queue['name'])
        else:
            p = Process(target=poll_queue, args=(queue,))
            procs.append(p)
            p.start()

    return procs


def main():
    # let ctrl-c work as it should.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    global logger
    logger = tutil.setup_logging("filefetcher errors")
    # logger.setLevel(logging.getLevelName('INFO'))
    multiprocessing_logging.install_mp_handler()

    config_file = tutil.get_env_var('MIRROR_GINA_CONFIG')
    global global_config
    global_config = tutil.parse_config(config_file)

    procs = poll_queues()
    for proc in procs:
        proc.join()

    logger.debug("That's all for now, bye.")
    logging.shutdown()


if __name__ == "__main__":
    main()
