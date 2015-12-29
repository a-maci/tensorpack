#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
# File: concurrency.py
# Author: Yuxin Wu <ppwwyyxx@gmail.com>

import threading
from contextlib import contextmanager
from itertools import izip
import tensorflow as tf

from .utils import expand_dim_if_necessary
from .naming import *
import logger

class StoppableThread(threading.Thread):
    def __init__(self):
        super(StoppableThread, self).__init__()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


class EnqueueThread(threading.Thread):
    def __init__(self, sess, coord, enqueue_op, dataflow):
        super(EnqueueThread, self).__init__()
        self.sess = sess
        self.coord = coord
        self.input_vars = sess.graph.get_collection(INPUT_VARS_KEY)
        self.dataflow = dataflow
        self.op = enqueue_op

    def run(self):
        try:
            while True:
                for dp in self.dataflow.get_data():
                    if self.coord.should_stop():
                        return
                    feed = {}
                    for var, data in izip(self.input_vars, dp):
                        data = expand_dim_if_necessary(var, data)
                        feed[var] = data
                    self.sess.run([self.op], feed_dict=feed)
        except tf.errors.CancelledError as e:
            pass
        except Exception:
            logger.exception("Exception in EnqueueThread:")
            self.coord.request_stop()

@contextmanager
def coordinator_guard(sess, coord, threads, queue):
    """
    Context manager to make sure that:
        queue is closed
        threads are joined
    """
    for th in threads:
        th.start()
    try:
        yield
    except (KeyboardInterrupt, Exception) as e:
        raise
    finally:
        coord.request_stop()
        sess.run(
            queue.close(cancel_pending_enqueues=True))
        coord.join(threads)