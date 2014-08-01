# -*- coding: utf-8 -*-
#!/usr/bin/env python
"Implementation of tzinfo classes for use with datetime.datetime."

from __future__ import unicode_literals

from datetime import timedelta, tzinfo
import time
import warnings

from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils.encoding import forceStr, forceText, DEFAULT_LOCALE_ENCODING

warnings.warn(
  "theory.utils.tzinfo will be removed in Theory 1.9. "
  "Use theory.utils.timezone instead.",
  RemovedInTheory19Warning, stacklevel=2)


# Python's doc say: "A tzinfo subclass must have an __init__() method that can
# be called with no arguments". FixedOffset and LocalTimezone don't honor this
# requirement. Defining __getinitargs__ is sufficient to fix copy/deepcopy as
# well as pickling/unpickling.

class FixedOffset(tzinfo):
  "Fixed offset in minutes east from UTC."
  def __init__(self, offset):
    warnings.warn(
      "theory.utils.tzinfo.FixedOffset will be removed in Theory 1.9. "
      "Use theory.utils.timezone.getFixedTimezone instead.",
      RemovedInTheory19Warning)
    if isinstance(offset, timedelta):
      self.__offset = offset
      offset = self.__offset.seconds // 60
    else:
      self.__offset = timedelta(minutes=offset)

    sign = '-' if offset < 0 else '+'
    self.__name = "%s%02d%02d" % (sign, abs(offset) / 60., abs(offset) % 60)

  def __repr__(self):
    return self.__name

  def __getinitargs__(self):
    return self.__offset,

  def utcoffset(self, dt):
    return self.__offset

  def tzname(self, dt):
    return self.__name

  def dst(self, dt):
    return timedelta(0)


# This implementation is used for display purposes. It uses an approximation
# for DST computations on dates >= 2038.

# A similar implementation exists in theory.utils.timezone. It's used for
# timezone support (when USE_TZ = True) and focuses on correctness.

class LocalTimezone(tzinfo):
  "Proxy timezone information from time module."
  def __init__(self, dt):
    warnings.warn(
      "theory.utils.tzinfo.LocalTimezone will be removed in Theory 1.9. "
      "Use theory.utils.timezone.getDefaultTimezone instead.",
      RemovedInTheory19Warning)
    tzinfo.__init__(self)
    self.__dt = dt
    self._tzname = self.tzname(dt)

  def __repr__(self):
    return forceStr(self._tzname)

  def __getinitargs__(self):
    return self.__dt,

  def utcoffset(self, dt):
    if self._isdst(dt):
      return timedelta(seconds=-time.altzone)
    else:
      return timedelta(seconds=-time.timezone)

  def dst(self, dt):
    if self._isdst(dt):
      return timedelta(seconds=-time.altzone) - timedelta(seconds=-time.timezone)
    else:
      return timedelta(0)

  def tzname(self, dt):
    isDst = False if dt is None else self._isdst(dt)
    try:
      return forceText(time.tzname[isDst], DEFAULT_LOCALE_ENCODING)
    except UnicodeDecodeError:
      return None

  def _isdst(self, dt):
    tt = (dt.year, dt.month, dt.day,
       dt.hour, dt.minute, dt.second,
       dt.weekday(), 0, 0)
    try:
      stamp = time.mktime(tt)
    except (OverflowError, ValueError):
      # 32 bit systems can't handle dates after Jan 2038, and certain
      # systems can't handle dates before ~1901-12-01:
      #
      # >>> time.mktime((1900, 1, 13, 0, 0, 0, 0, 0, 0))
      # OverflowError: mktime argument out of range
      # >>> time.mktime((1850, 1, 13, 0, 0, 0, 0, 0, 0))
      # ValueError: year out of range
      #
      # In this case, we fake the date, because we only care about the
      # DST flag.
      tt = (2037,) + tt[1:]
      stamp = time.mktime(tt)
    tt = time.localtime(stamp)
    return tt.tmIsdst > 0
