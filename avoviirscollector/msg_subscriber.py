#!/usr/bin/env python

# -*- coding: utf-8 -*-

# I waive copyright and related rights in the this work worldwide
# through the CC0 1.0 Universal public domain dedication.
# https://creativecommons.org/publicdomain/zero/1.0/legalcode

# Author(s):
#   Tom Parker <tparker@usgs.gov>

""" A trival client for msg_publisher
"""

import zmq

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 60)
socket.setsockopt(zmq.TCP_KEEPALIVE_CNT, 20)
socket.setsockopt(zmq.TCP_KEEPALIVE_INTVL, 60)

print("Connecting to msg_publisher...")
socket.connect("tcp://localhost:29092")
print("connected")

socket.setsockopt_string(zmq.SUBSCRIBE, "")

while True:
    print("waiting for message")
    msg = socket.recv_string()
    print("got message: {}".format(msg))
