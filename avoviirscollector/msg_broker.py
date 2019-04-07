#!/usr/local/bin/python

import threading
import queue

import zmq
from posttroll.subscriber import Subscribe
import tomputils.util as tutil

class ClientTask(threading.Thread):
    def __init__(self, msgs):
        threading.Thread.__init__ (self)
        self.msgs = msgs

    def run(self):
        topic = "pytroll://AVO/viirs/granule"
        with Subscribe('', topic, True) as sub:
            for msg in sub.recv():
                try:
                    print("received message")
                    self.msgs.put(msg)
                except Exception as e:
                    print("Exception: {}".format(e))


class ServerTask(threading.Thread):
    def __init__(self, msgs):
        threading.Thread.__init__ (self)
        self.msgs = msgs
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.bind("tcp://*:19091")

    def run(self):
        while True:
            print("waiting for request")
            request = self.socket.recv()
            print("Received request: %s" % request)
            msg = self.msgs.get()
            self.socket.send(bytes(msg.encode(), 'UTF-8'))
            print("message sent")


def main():
    msgs = queue.Queue()
    client = ClientTask(msgs)
    client.start()
    print("client started")
    server = ServerTask(msgs)
    server.start()
    print("client started")
    client.join()

if __name__ == '__main__':
    main()

