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
from urlparse import urlparse
import cStringIO
import pycurl
import tomputils.mattermost as mm
import hashlib
import socket
import viirs
from db import Db
import h5py
from tomputils.downloader import fetch

DEFAULT_BACKFILL = 2
DEFAULT_NUM_CONN = 5

INSTRUMENTS = {
    'viirs': {
        'name': 'viirs',
        'level': 'level1',
        'out_path': 'viirs/sdr',
        'match': '/(GMTCO|SVM03|SVM04|SVM05|SVM15|SVM16)_'
    },
    'viirs_hr': {
        'name': 'viirs',
        'level': 'level1',
        'out_path': 'viirs/sdr',
        'match': '/(GITCO|SVI01|SVI04|SVI05)_'
    },
    'viirs_dnb': {
        'name': 'viirs',
        'level': 'level1',
        'out_path': 'viirs/sdr',
        'match': '/(GDNBO|SVDNB)_'
    }

}

FACILITIES = ('uafgina', 'gilmore')
SATELLITES = ('snpp', 'noaa20')
GINA_URL = ('http://nrt-status.gina.alaska.edu/products.json'
            + '?action=index&commit=Get+Products&controller=products')
OUT_DIR = os.path.join(os.environ['BASE_DIR'], 'data')
TMP_DIR = os.path.join(os.environ['BASE_DIR'], 'data/temp')
DB_DIR = os.path.join(os.environ['BASE_DIR'], 'db')


class MirrorGina(object):
    def __init__(self, args):
        self.args = args
        self.logger = self._setup_logging()

        # We should ignore SIGPIPE when using pycurl.NOSIGNAL - see
        # the libcurl tutorial for more info.
        try:
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        except ImportError:
            pass

        self._instrument = INSTRUMENTS[args.instrument]
        self.logger.debug("instrument: %s", self._instrument)

        self._satellite = args.satellite
        self.logger.debug("satellite: %s", self._satellite)

        self._num_conn = args.num_conn
        self.logger.debug("num_conn: %s", self._num_conn)

        self._backfill = args.backfill
        self.logger.debug("backfill: %s", self._backfill)

        self.out_path = os.path.join(OUT_DIR, self._instrument['out_path'],
                                     self.args.facility)
        if not os.path.exists(self.out_path):
            self.logger.debug("Making out dir " + self.out_path)
            os.makedirs(self.out_path)

        self.tmp_path = os.path.join(TMP_DIR, self._instrument['out_path'],
                                     self.args.facility)
        if not os.path.exists(self.tmp_path):
            self.logger.debug("Making out dir " + self.tmp_path)
            os.makedirs(self.tmp_path)

        self.conn = Db(DB_DIR)
        self.mattermost = mm.Mattermost()
        # self.mattermost.set_log_level(logging.DEBUG)

        self.hostname = socket.gethostname()

    def _setup_logging(self):
        logger = logging.getLogger('MirrorGina')
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        if self.args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.info("Verbose logging")
        else:
            logging.getLogger().setLevel(logging.INFO)

        return logger

    def get_file_list(self):
        self.logger.debug("fetching files")
        backfill = timedelta(days=self._backfill)
        end_date = datetime.utcnow() + timedelta(days=1)
        start_date = end_date - backfill

        url = GINA_URL
        url += '&start_date=' + start_date.strftime('%Y-%m-%d')
        url += '&end_date=' + end_date.strftime('%Y-%m-%d')
        url += '&sensors[]=' + self._instrument['name']
        url += '&processing_levels[]=' + self._instrument['level']
        url += '&facilities[]=' + self.args.facility
        url += '&satellites[]=' + self.args.satellite
        self.logger.debug("URL: %s", url)
        buf = cStringIO.StringIO()

        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.WRITEFUNCTION, buf.write)
        c.perform()

        files = json.loads(buf.getvalue())
        buf.close()

        self.logger.info("Found %s files", len(files))
        files = sorted(files, key=lambda k: k['url'],
                       cmp=viirs.filename_comparator)
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
            self.logger.debug("Fetching %s from %s" % (tmp_file, url))
            fetch(url, tmp_file)
            md5 = file['md5sum']
            file_md5 = hashlib.md5(open(tmp_file, 'rb').read()).hexdigest()
            self.logger.debug("MD5 %s : %s" % (md5, file_md5))

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


def arg_parse():

    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--num_conn",
                        help="# of concurrent connections", type=int,
                        default=DEFAULT_NUM_CONN)
    parser.add_argument("-b", "--backfill",
                        help="# of days to back fill",
                        type=int, default=DEFAULT_BACKFILL)
    parser.add_argument("-v", "--verbose",
                        help="Verbose logging",
                        action='store_true')
    parser.add_argument('-f', '--facility', choices=FACILITIES,
                        help="facility to query", required=True)
    parser.add_argument('-s', '--satellite', choices=SATELLITES,
                        help="satellite to query", required=True)
    parser.add_argument('instrument', choices=INSTRUMENTS.keys(),
                        help="instrument to query")

    return parser.parse_args()


def main():
    args = arg_parse()

    mirror_gina = MirrorGina(args)
    mirror_gina.fetch_files()


if __name__ == "__main__":
    main()
