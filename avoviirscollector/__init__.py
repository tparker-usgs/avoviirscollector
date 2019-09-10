# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
#  Purpose: fetch viirs data
#   Author: Tom Parker
#
# -----------------------------------------------------------------------------
"""
avoviirscollector
=================

Fetch viirs data at AVO

:license:
    CC0 1.0 Universal
    http://creativecommons.org/publicdomain/zero/1.0/
"""

from avoviirscollector.version import __version__
import tomputils.util as tutil

logger = tutil.setup_logging("mirror_gina errors")
BASE_DIR = tutil.get_env_var("VIIRS_BASE_DIR", "unset")
SATELLITE = tutil.get_env_var("VIIRS_SATELLITE", "unset")
CHANNELS = tutil.get_env_var("VIIRS_CHANNELS", "unset").split("|")

__all__ = ["__version__"]
