# -*- coding: utf-8 -*-
#!/usr/bin/env python
"""
Synchronization primitives:

  - reader-writer lock (preference to writers)

(Contributed to Theory by eugene@lazutkin.com)
"""

import contextlib
try:
  from theory.thevent import gevent
except ImportError:
  import dummyThreading as gevent.coros


class RWLock(object):
  """
  Classic implementation of reader-writer lock with preference to writers.

  Readers can access a resource simultaneously.
  Writers get an exclusive access.

  API is self-descriptive:
    readerEnters()
    readerLeaves()
    writerEnters()
    writerLeaves()
  """
  def __init__(self):
    self.mutex = gevent.coros.RLock()
    self.canRead = gevent.coros.Semaphore(0)
    self.canWrite = gevent.coros.Semaphore(0)
    self.activeReaders = 0
    self.activeWriters = 0
    self.waitingReaders = 0
    self.waitingWriters = 0

  def readerEnters(self):
    with self.mutex:
      if self.activeWriters == 0 and self.waitingWriters == 0:
        self.activeReaders += 1
        self.canRead.release()
      else:
        self.waitingReaders += 1
    self.canRead.acquire()

  def readerLeaves(self):
    with self.mutex:
      self.activeReaders -= 1
      if self.activeReaders == 0 and self.waitingWriters != 0:
        self.activeWriters += 1
        self.waitingWriters -= 1
        self.canWrite.release()

  @contextlib.contextmanager
  def reader(self):
    self.readerEnters()
    try:
      yield
    finally:
      self.readerLeaves()

  def writerEnters(self):
    with self.mutex:
      if self.activeWriters == 0 and self.waitingWriters == 0 and self.activeReaders == 0:
        self.activeWriters += 1
        self.canWrite.release()
      else:
        self.waitingWriters += 1
    self.canWrite.acquire()

  def writerLeaves(self):
    with self.mutex:
      self.activeWriters -= 1
      if self.waitingWriters != 0:
        self.activeWriters += 1
        self.waitingWriters -= 1
        self.canWrite.release()
      elif self.waitingReaders != 0:
        t = self.waitingReaders
        self.waitingReaders = 0
        self.activeReaders += t
        while t > 0:
          self.canRead.release()
          t -= 1

  @contextlib.contextmanager
  def writer(self):
    self.writerEnters()
    try:
      yield
    finally:
      self.writerLeaves()
