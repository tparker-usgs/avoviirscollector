#!/usr/bin/env python

# -*- coding: utf-8 -*-

# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode

# Author(s):
#   Tom Parker <tparker@usgs.gov>

"""Retrieve files from GINA
"""


import argparse
import re
import json
import signal
import logging
import os.path
import os
import posixpath
from datetime import timedelta, datetime
#from urlparse import urlparse
import pycurl
import tomputils.mattermost as mm
import tomputils.util as tutil
import hashlib
import socket
from io import BytesIO
from rsCollectors import viirs
#from db import Db
#import h5py
#from tomputils.downloader import fetch
import multiprocessing_logging
from functools import cmp_to_key

GINA_URL = ('http://nrt-status.gina.alaska.edu/products.json'
            + '?action=index&commit=Get+Products&controller=products')

class MirrorGina(object):
    def __init__(self, base_dir, config):
        self.base_dir = base_dir
        self.config = config

        # We should ignore SIGPIPE when using pycurl.NOSIGNAL - see
        # the libcurl tutorial for more info.
        try:
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        except ImportError:
            pass

        self.hostname = socket.gethostname()

    def get_file_list(self):
        logger.debug("fetching files")
        backfill = timedelta(days=self.config['backfill_days'])
        end_date = datetime.utcnow() + timedelta(days=1)
        start_date = end_date - backfill

        url = GINA_URL
        url += '&start_date=' + start_date.strftime('%Y-%m-%d')
        url += '&end_date=' + end_date.strftime('%Y-%m-%d')
        url += '&sensors[]=' + self.config['sensor']
        url += '&processing_levels[]=' + self.config['level']
        url += '&facilities[]=' + self.config['facility']
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
        files.sort(key=cmp_to_key(lambda a,b:
                                  viirs.filename_comparator(a['url'],
                                                              b['url'])))
        return files

    def queue_files(self, file_list):
        queue = []
        pattern = re.compile(self._instrument['match'])
        self.logger.debug("%d files before pruning", len(file_list))
        for new_file in file_list:
            out_file = path_from_url(self.out_path, new_file['url'])
            # tmp_path = self.path_from_url(self.tmp_path, new_file['url'])

            if pattern.search(out_file) and not os.path.exists(out_file):
                self.logger.debug("Queueing %s", new_file['url'])
                queue.append(new_file)
            else:
                self.logger.debug("Skipping %s", new_file['url'])

        self.logger.debug("%d files after pruning", len(queue))
        return queue

    def create_multi(self):
        m = pycurl.CurlMulti()
        m.handles = []
        for i in range(self._num_conn):
            self.logger.debug("creating curl object")
            c = pycurl.Curl()
            c.fp = None
            c.setopt(pycurl.FOLLOWLOCATION, 1)
            c.setopt(pycurl.MAXREDIRS, 5)
            c.setopt(pycurl.CONNECTTIMEOUT, 30)
            c.setopt(pycurl.TIMEOUT, 600)
            c.setopt(pycurl.NOSIGNAL, 1)
            m.handles.append(c)

        return m

    def _log_sighting(self, filename, success, message=None, url=None):
        self.logger.debug("TOMP HERE")
        sight_date = datetime.utcnow()
        granule = viirs.Viirs(filename)
        proc_time = granule.proc_date - granule.start
        trans_time = sight_date - granule.proc_date

        msg = None
        if not success:
            msg = '### :x: Failed file transfer'
            if url is not None:
                msg += '\n**URL** %s' % url

            msg += '\n**Filename** %s' % filename
            if message is not None:
                msg += '\n**Message** %s' % message
            msg += '\n**Processing delay** %s' % mm.format_timedelta(proc_time)
        else:
            pause = timedelta(hours=1)

            # post new orbit messasge
            orbit_proc_time = self.conn.get_orbit_proctime(self.args.facility,
                                                           granule)
            gran_proc_time = self.conn.get_granule_proctime(self.args.facility,
                                                            granule)

            orb_msg = None
            if orbit_proc_time is None:
                msg = '### :earth_americas: New orbit from %s: %d'
                orb_msg = msg % (self.args.facility, granule.orbit)
            elif granule.proc_date > orbit_proc_time + pause:
                msg = '### :snail: _Reprocessed orbit_ from %s: %d'
                orb_msg = msg % (self.args.facility, granule.orbit)

            if orb_msg is not None:
                msg = '\n**First granule** %s (%s)'
                orb_msg += msg % (mm.format_span(granule.start, granule.end),
                                  granule.channel)
                count = self.conn.get_orbit_granule_count(granule.orbit - 1,
                                                          self.args.facility)
                msg = '\n**Granules seen from orbit %d** %d'
                orb_msg += msg % (granule.orbit - 1, count)
                self.mattermost.post(orb_msg)

            # post new granule message
            if gran_proc_time is None:
                msg = '### :satellite: New granule from %s'
                gran_msg = msg % self.args.facility
            elif granule.proc_date > gran_proc_time + pause:
                msg = '### :snail: _Reprocessed granule_ from %s'
                gran_msg = msg % self.args.facility
            else:
                gran_msg = None

            if gran_msg is not None:
                gran_span = mm.format_span(granule.start, granule.end)
                gran_delta = mm.format_timedelta(granule.end - granule.start)
                msg = '\n**Granule span** %s (%s)'
                gran_msg += msg % (gran_span, gran_delta)
                msg = '\n**Processing delay** %s'
                gran_msg += msg % mm.format_timedelta(proc_time)
                msg = '\n**Transfer delay** %s'
                gran_msg += msg % mm.format_timedelta(trans_time)
                msg = '\n**Accumulated delay** %s'
                gran_msg += msg % mm.format_timedelta(proc_time + trans_time)

                if message:
                    gran_msg += '\n**Message: %s' % message

        if gran_msg is not None:
            self.mattermost.post(gran_msg)

        self.conn.insert_obs(self.args.facility, granule, sight_date, success)

    def fetch_files(self):
        file_list = self.get_file_list()
        file_queue = self.queue_files(file_list)

        for file in file_queue:
            url = file['url']
            tmp_file = path_from_url(self.tmp_path, url)
            logger.debug("Fetching %s from %s" % (tmp_file, url))
            fetch(url, tmp_file)
            md5 = file['md5sum']
            file_md5 = hashlib.md5(open(tmp_file, 'rb').read()).hexdigest()
            logger.debug("MD5 %s : %s" % (md5, file_md5))

            if md5 == file_md5:
                try:
                    h5py.File(tmp_file, 'r')
                    success = True
                    errmsg = None
                except:
                    success = False
                    errmsg = 'Good checksum, bad format.'
                    os.unlink(tmp_file)
                else:
                    out_file = path_from_url(self.out_path, url)
                    os.rename(tmp_file, out_file)
            else:
                success = False
                size = os.path.getsize(tmp_file)
                msg = 'Bad checksum: %s != %s (%d bytes)'
                errmsg = msg % (file_md5, md5, size)
                os.unlink(tmp_file)

            self._log_sighting(tmp_file, success, message=errmsg)


def path_from_url(base, url):
    path = urlparse(url).path
    filename = posixpath.basename(path)

    return os.path.join(base, filename)


def main():
    # let ctrl-c work as it should.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    global logger
    logger = tutil.setup_logging("filefetcher errors")
    multiprocessing_logging.install_mp_handler()

    config_file = tutil.get_env_var('MIRROR_GINA_CONFIG')
    config = tutil.parse_config(config_file)

    base_dir = config['base-dir']
    logger.debug("base-dir: %s", base_dir)

    for queue in config['queues']:
        logger.info("Launching queueu: %s", queue['name'])
        mirror_gina = MirrorGina(base_dir, queue)
        mirror_gina.fetch_files()

if __name__ == "__main__":
    main()
