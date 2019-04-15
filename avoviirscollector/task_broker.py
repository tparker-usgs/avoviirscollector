#!/usr/bin/env python

# -*- coding: utf-8 -*-

# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode

# Author(s):
#   Tom Parker <tparker@usgs.gov>

""" Present a consolodated event stream from messages gathered from individual
    segment_gatherer processes.
"""


import collections
import threading
import signal
import time

import zmq
from posttroll.subscriber import Subscribe
import tomputils.util as tutil
from avoviirscollector.viirs import product_key


class ClientTask(threading.Thread):
    def __init__(self, msgs):
        threading.Thread.__init__(self)
        self.msgs = msgs

    def run(self):
        topic = "pytroll://AVO/viirs/granule"
        with Subscribe('', topic, True) as sub:
            for new_msg in sub.recv():
                try:
                    logger.debug("received message (%d)", len(self.msgs))
                    queue_msg(self.msgs, new_msg)
                except Exception as e:
                    logger.error("Exception: {}".format(e))
                    logger.error(e)


class ServerTask(threading.Thread):
    def __init__(self, msgs):
        threading.Thread.__init__(self)
        self.msgs = msgs
        context = zmq.Context()
        self.socket = context.socket(zmq.DEALER)
        self.socket.bind("tcp://*:19091")

    def get_message(self):
        msg = None
        while not msg:
            try:
                (topic, msg) = self.msgs.popitem(last=False)
            except KeyError:
                time.sleep(1)
        return msg

    def run(self):
        while True:
            try:
                msg = self.get_message()
                self.socket.send(bytes(msg.encode(), 'UTF-8'), zmq.NOBLOCK)
                logger.debug("message sent: %s %s - %s", product_key(msg),
                             msg.data['start_time'].strftime('%Y%m%d.%H%M'),
                             msg.data['end_time'].strftime('%Y%m%d.%H%M'))
            except zmq.Again:
                queue_msg(self.msgs, msg)
                logger.debug("a client was there, now it's gone")

            logger.debug("waiting for response")
            request = self.socket.recv()
            logger.debug("Received response: %s (%d)",
                         request, len(self.msgs))


def queue_msg(msgs, new_msg):
    key = product_key(new_msg)
    with msgs_lock:
        if key in msgs:
            logger.debug("updating messge %s", key)
            queued_data = msgs[key].data
            new_data = new_msg.data
            queued_data['start_time'] = min(queued_data['start_time'],
                                            new_data['start_time'])
            queued_data['start_date'] = min(queued_data['start_date'],
                                            new_data['start_date'])
            queued_data['end_time'] = max(queued_data['end_time'],
                                          new_data['end_time'])
            queued_data['dataset'] += new_data['dataset']
        else:
            logger.debug("queueing messge %s", key)
            msgs[key] = new_msg


def main():
    # let ctrl-c work as it should.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    global logger
    logger = tutil.setup_logging("msg_broker errors")

    global msgs_lock
    msgs_lock = threading.Lock()

    logger.debug("Current libzmq version is %s" % zmq.zmq_version())
    logger.debug("Current  pyzmq version is %s" % zmq.__version__)
    
    # msgs = queue.Queue()
    msgs = collections.OrderedDict()
    client = ClientTask(msgs)
    client.start()
    logger.info("client started")
    server = ServerTask(msgs)
    server.start()
    logger.info("server started")
    client.join()


if __name__ == '__main__':
    main()
