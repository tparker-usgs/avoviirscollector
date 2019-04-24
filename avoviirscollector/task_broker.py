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
from avoviirscollector.viirs import product_key, products, product
from json.decoder import JSONDecodeError

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


class Server(threading.Thread):
    def __init__(self, context, msgs, socket_type, address):
        threading.Thread.__init__(self)
        self.msgs = msgs
        self.socket = context.socket(socket_type)
        self.socket.bind(address)


class Updater(Server):
    def __init__(self, context, msgs):
        Server.__init__(self, context, msgs, zmq.PUB, UPDATER_ADDRESS)

    def run(self):
        while True:
            update = {}
            update['queue length'] = len(self.msgs)
            update['products waiting'] = products(self.msgs.keys())
            self.socket.send_json(update)
            logger.debug("Updater: queue length:: %d", update['queue length'])
            time.sleep(1)


class Tasker(threading.Thread):
    def __init__(self, context, msgs):
        Server.__init__(self, context, msgs, zmq.REP, TASKER_ADDRESS)

    def get_message(self, desired_products):
        with msgs_lock:
            waiting_tasks = []
            while self.msgs:
                (key, msg_list) = self.msgs.popitem(last=False)
                if product(key) in desired_products:
                    msg = msg_list.pop()
                    if msg_list:
                        logger.debug("requeing {} items".format(len(msg_list)))
                        self.msgs[key] = msg_list
                    break
                else:
                    waiting_tasks.append(msg_list)
            for msg_list in waiting_tasks:
                self.msgs[key] = msg_list
                self.msgs.move_to_end(key, last=False)

        return msg

    def run(self):
        while True:
            logger.debug("waiting for request")
            try:
                request = self.socket.recv_json()
                logger.debug("received request: %s", request)
            except JSONDecodeError:
                logger.exception("Bad reqeust from client")
                pass
            try:
                msg = self.get_message(request['desired products'])
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
