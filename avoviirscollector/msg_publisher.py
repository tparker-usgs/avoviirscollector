#!/usr/bin/env python

# -*- coding: utf-8 -*-

# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode

# Author(s):
#   Tom Parker <tparker@usgs.gov>

""" Consolodate and publish local Pytroll messages
"""


import signal

import zmq
from posttroll.subscriber import Subscribe
import tomputils.util as tutil


def main():
    # let ctrl-c work as it should.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    global logger
    logger = tutil.setup_logging("msg_pub errors")

    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:29092")
    logger.debug("Listening for subscribers.")

    with Subscribe('', '', True) as sub:
        for msg in sub.recv():
            msg_string = msg.encode()
            logger.debug("sending msg: %s", msg_string)
            socket.send(bytes(msg_string, 'UTF-8'))


if __name__ == '__main__':
    main()
