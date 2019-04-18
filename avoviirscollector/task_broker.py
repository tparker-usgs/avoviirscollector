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
from datetime import timedelta
import zmq
from posttroll.subscriber import Subscribe
import tomputils.util as tutil
from avoviirscollector.viirs import product_key


TOPIC = "pytroll://AVO/viirs/granule"
UPDATER_ADDRESS = "tcp://*:19191"
TASKER_ADDRESS = "tcp://*:19091"
ORBIT_SLACK = timedelta(minutes=30)


class ClientTask(threading.Thread):
    def __init__(self, msgs):
        threading.Thread.__init__(self)
        self.msgs = msgs

    def run(self):
        with Subscribe('', TOPIC, True) as sub:
            for new_msg in sub.recv():
                try:
                    logger.debug("received message (%d)", len(self.msgs))
                    queue_msg(self.msgs, new_msg)
                except Exception:
                    logger.exception("Can't queue message.")


class Updater(threading.Thread):
    def __init__(self, context, msgs):
        threading.Thread.__init__(self)
        self.msgs = msgs
        self.socket = context.socket(zmq.PUB)
        self.socket.bind(UPDATER_ADDRESS)

    def run(self):
        while True:
            msgs_cnt = len(self.msgs)
            if msgs_cnt:
                self.socket.send_string("There's stuff to do")
                logger.debug("Updater: There's stuff to do: %d", msgs_cnt)
            else:
                self.socket.send_string("")
                logger.debug("Updater: There's nothing to do: %d", msgs_cnt)
            time.sleep(1)


class Tasker(threading.Thread):
    def __init__(self, context, msgs):
        threading.Thread.__init__(self)
        self.msgs = msgs
        self.socket = context.socket(zmq.REP)
        self.socket.bind(TASKER_ADDRESS)

    def get_message(self):
        with msgs_lock:
            (key, msg_list) = self.msgs.popitem(last=False)
            msg = msg_list.pop()
            if msg_list:
                logger.debug("requeing {} items".format(len(msg_list)))
                self.msgs[key] = msg_list
        return msg

    def run(self):
        while True:
            logger.debug("waiting for request")
            self.socket.recv()
            logger.debug("received request")
            try:
                msg = self.get_message()
                self.socket.send(bytes(msg.encode(), 'UTF-8'))
                logger.debug("sent response")
            except KeyError:
                self.socket.send(b'')
                logger.debug("sent empty message")


def queue_msg(msgs, new_msg):
    key = product_key(new_msg)
    with msgs_lock:
        if key not in msgs:
            logger.debug("Adding new key %s", key)
            msgs[key] = []

        new_data = new_msg.data
        for msg in msgs[key]:
            queued_data = msg.data
            time_diff = abs(queued_data['start_time'] - new_data['start_time'])
            if time_diff < ORBIT_SLACK:
                logger.debug("updating messge %s", key)
                queued_data['start_time'] = min(queued_data['start_time'],
                                                new_data['start_time'])
                queued_data['start_date'] = min(queued_data['start_date'],
                                                new_data['start_date'])
                queued_data['end_time'] = max(queued_data['end_time'],
                                              new_data['end_time'])
                queued_data['dataset'] += new_data['dataset']
                new_msg = None
                break

        if new_msg:
            msgs[key].append(new_msg)


def main():
    # let ctrl-c work as it should.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    global logger
    logger = tutil.setup_logging("msg_broker errors")

    global msgs_lock
    msgs_lock = threading.Lock()

    logger.debug("Current libzmq version is %s" % zmq.zmq_version())
    logger.debug("Current  pyzmq version is %s" % zmq.__version__)

    context = zmq.Context()
    msgs = collections.OrderedDict()

    client = ClientTask(msgs)
    client.start()
    logger.info("client started")
    tasker = Tasker(context, msgs)
    tasker.start()
    logger.info("tasker started")
    updater = Updater(context, msgs)
    updater.start()
    logger.info("updater started")
    client.join()
    tasker.join()
    updater.join()


if __name__ == '__main__':
    main()
