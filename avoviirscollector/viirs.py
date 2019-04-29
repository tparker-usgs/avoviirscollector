# -*- coding: utf-8 -*-
"""
Module parsing a VIIRS filename.

From http://rammb.cira.colostate.edu/projects/npp/
            Beginner_Guide_to_VIIRS_Imagery_Data.pdf

SVM01_npp_d20130117_t2059265_e2100506_b06349_c20130118032130407525_noaa_ops.h5
  A    B    C          D      E        F           G                H
• A: file type (in this case, channel M-01 SDR data file)
• B: satellite identifier (Suomi-NPP)
• C: date in YYYYMMDD (17 January 2013)
• D: UTC time at the start of the granule in HHMMSS.S (20:59:26.5 UTC)
• E: UTC time at the end of the granule in HHMMSS.S (21:00:50.6 UTC)
• F: orbit number (06349)
• G: date and time the file was created in YYYYMMDD
        HHMMSS.SSSSSS (03:21:30.407525 UTC, 18 January 2013)
• H: source of the data file (operational file produced by NOAA)

"""

from datetime import datetime
from functools import total_ordering


@total_ordering
class Viirs(object):
    def __init__(self, filename, md5):
        self.md5 = md5
        self.filename = filename
        self.basename = filename.split('/')[-1]
        parts = self.basename.split('_')
        self.channel = parts[0]
        self.satellite = parts[1]
        self.start = datetime.strptime(parts[2] + "_" + parts[3],
                                       'd%Y%m%d_t%H%M%S%f')
        self.end = datetime.strptime(parts[4], 'e%H%M%S%f')
        self.orbit = int(parts[5][1:])
        self.proc_date = datetime.strptime(parts[6], 'c%Y%m%d%H%M%S%f')

    def __str__(self):
        out_string = 'filename: %s\n' % self.basename
        out_string += 'channel: %s\n' % self.channel
        out_string += 'satellite: %s\n' % self.satellite
        out_string += 'start: %s\n' % self.start
        out_string += 'end: %s\n' % self.end
        out_string += 'orbit: %s\n' % self.orbit
        out_string += 'proc_date: %s\n' % self.proc_date
        return out_string

    def __eq__(self, other):
        eq = isinstance(other, Viirs)
        eq = eq and self.orbit == other.orbit
        eq = eq and self.start == other.start
        eq = eq and self.channel == other.channel
        return eq

    def __lt__(self, other):
        lt = self.orbit > other.orbit
        lt = lt or (self.orbit == other.orbit and self.time < other.time)
        lt = lt or (self.start == other.start and self.channel < other.channel)
        return lt


def product_key(message):
    return ";".join((message.subject, message.data['platform_name'],
                    str(message.data['orbit_number'])))


def products(keys):
    return [product(key) for key in keys]


def product(key):
    topic = key.split(';')[0]
    return topic.split('/')[-1]
