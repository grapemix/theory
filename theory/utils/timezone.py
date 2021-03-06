# -*- coding: utf-8 -*-
#!/usr/bin/env python
"""
Timezone-related classes and functions.

This module uses pytz when it's available and fallbacks when it isn't.
"""

from datetime import datetime, timedelta, tzinfo
from gevent.local import local
import sys
import time as _time

try:
  import pytz
except ImportError:
  pytz = None

from theory.conf import settings
from theory.utils import six

__all__ = [
  'utc', 'getFixedTimezone',
  'getDefaultTimezone', 'getDefaultTimezoneName',
  'getCurrentTimezone', 'getCurrentTimezoneName',
  'activate', 'deactivate', 'override',
  'localtime', 'now',
  'isAware', 'isNaive', 'makeAware', 'makeNaive',
]


# UTC and local time zones

ZERO = timedelta(0)


class UTC(tzinfo):
  """
  UTC implementation taken from Python's docs.

  Used only when pytz isn't available.
  """

  def __repr__(self):
    return "<UTC>"

  def utcoffset(self, dt):
    return ZERO

  def tzname(self, dt):
    return "UTC"

  def dst(self, dt):
    return ZERO


class FixedOffset(tzinfo):
  """
  Fixed offset in minutes east from UTC. Taken from Python's docs.

  Kept as close as possible to the reference version. __init__ was changed
  to make its arguments optional, according to Python's requirement that
  tzinfo subclasses can be instantiated without arguments.
  """

  def __init__(self, offset=None, name=None):
    if offset is not None:
      self.__offset = timedelta(minutes=offset)
    if name is not None:
      self.__name = name

  def utcoffset(self, dt):
    return self.__offset

  def tzname(self, dt):
    return self.__name

  def dst(self, dt):
    return ZERO


class ReferenceLocalTimezone(tzinfo):
  """
  Local time. Taken from Python's docs.

  Used only when pytz isn't available, and most likely inaccurate. If you're
  having trouble with this class, don't waste your time, just install pytz.

  Kept as close as possible to the reference version. __init__ was added to
  delay the computation of STDOFFSET, DSTOFFSET and DSTDIFF which is
  performed at import time in the example.

  Subclasses contain further improvements.
  """

  def __init__(self):
    self.STDOFFSET = timedelta(seconds=-_time.timezone)
    if _time.daylight:
      self.DSTOFFSET = timedelta(seconds=-_time.altzone)
    else:
      self.DSTOFFSET = self.STDOFFSET
    self.DSTDIFF = self.DSTOFFSET - self.STDOFFSET
    tzinfo.__init__(self)

  def utcoffset(self, dt):
    if self._isdst(dt):
      return self.DSTOFFSET
    else:
      return self.STDOFFSET

  def dst(self, dt):
    if self._isdst(dt):
      return self.DSTDIFF
    else:
      return ZERO

  def tzname(self, dt):
    return _time.tzname[self._isdst(dt)]

  def _isdst(self, dt):
    tt = (dt.year, dt.month, dt.day,
       dt.hour, dt.minute, dt.second,
       dt.weekday(), 0, 0)
    stamp = _time.mktime(tt)
    tt = _time.localtime(stamp)
    return tt.tmIsdst > 0


class LocalTimezone(ReferenceLocalTimezone):
  """
  Slightly improved local time implementation focusing on correctness.

  It still crashes on dates before 1970 or after 2038, but at least the
  error message is helpful.
  """

  def tzname(self, dt):
    isDst = False if dt is None else self._isdst(dt)
    return _time.tzname[isDst]

  def _isdst(self, dt):
    try:
      return super(LocalTimezone, self)._isdst(dt)
    except (OverflowError, ValueError) as exc:
      excType = type(exc)
      excValue = excType(
        "Unsupported value: %r. You should install pytz." % dt)
      excValue.__cause__ = exc
      six.reraise(excType, excValue, sys.excInfo()[2])

utc = pytz.utc if pytz else UTC()
"""UTC time zone as a tzinfo instance."""


def getFixedTimezone(offset):
  """
  Returns a tzinfo instance with a fixed offset from UTC.
  """
  if isinstance(offset, timedelta):
    offset = offset.seconds // 60
  sign = '-' if offset < 0 else '+'
  hhmm = '%02d%02d' % divmod(abs(offset), 60)
  name = sign + hhmm
  return FixedOffset(offset, name)

# In order to avoid accessing the settings at compile time,
# wrap the expression in a function and cache the result.
_localtime = None


def getDefaultTimezone():
  """
  Returns the default time zone as a tzinfo instance.

  This is the time zone defined by settings.TIME_ZONE.
  """
  global _localtime
  if _localtime is None:
    if isinstance(settings.TIME_ZONE, six.stringTypes) and pytz is not None:
      _localtime = pytz.timezone(settings.TIME_ZONE)
    else:
      # This relies on os.environ['TZ'] being set to settings.TIME_ZONE.
      _localtime = LocalTimezone()
  return _localtime


# This function exists for consistency with getCurrentTimezoneName
def getDefaultTimezoneName():
  """
  Returns the name of the default time zone.
  """
  return _getTimezoneName(getDefaultTimezone())

_active = local()


def getCurrentTimezone():
  """
  Returns the currently active time zone as a tzinfo instance.
  """
  return getattr(_active, "value", getDefaultTimezone())


def getCurrentTimezoneName():
  """
  Returns the name of the currently active time zone.
  """
  return _getTimezoneName(getCurrentTimezone())


def _getTimezoneName(timezone):
  """
  Returns the name of ``timezone``.
  """
  try:
    # for pytz timezones
    return timezone.zone
  except AttributeError:
    # for regular tzinfo objects
    return timezone.tzname(None)

# Timezone selection functions.

# These functions don't change os.environ['TZ'] and call time.tzset()
# because it isn't thread safe.


def activate(timezone):
  """
  Sets the time zone for the current thread.

  The ``timezone`` argument must be an instance of a tzinfo subclass or a
  time zone name. If it is a time zone name, pytz is required.
  """
  if isinstance(timezone, tzinfo):
    _active.value = timezone
  elif isinstance(timezone, six.stringTypes) and pytz is not None:
    _active.value = pytz.timezone(timezone)
  else:
    raise ValueError("Invalid timezone: %r" % timezone)


def deactivate():
  """
  Unsets the time zone for the current thread.

  Theory will then use the time zone defined by settings.TIME_ZONE.
  """
  if hasattr(_active, "value"):
    del _active.value


class override(object):
  """
  Temporarily set the time zone for the current thread.

  This is a context manager that uses ``~theory.utils.timezone.activate()``
  to set the timezone on entry, and restores the previously active timezone
  on exit.

  The ``timezone`` argument must be an instance of a ``tzinfo`` subclass, a
  time zone name, or ``None``. If is it a time zone name, pytz is required.
  If it is ``None``, Theory enables the default time zone.
  """
  def __init__(self, timezone):
    self.timezone = timezone
    self.oldTimezone = getattr(_active, 'value', None)

  def __enter__(self):
    if self.timezone is None:
      deactivate()
    else:
      activate(self.timezone)

  def __exit__(self, excType, excValue, traceback):
    if self.oldTimezone is None:
      deactivate()
    else:
      _active.value = self.oldTimezone


# Templates

def templateLocaltime(value, useTz=None):
  """
  Checks if value is a datetime and converts it to local time if necessary.

  If useTz is provided and is not None, that will force the value to
  be converted (or not), overriding the value of settings.USE_TZ.

  This function is designed for use by the template engine.
  """
  shouldConvert = (isinstance(value, datetime)
    and (settings.USE_TZ if useTz is None else useTz)
    and not isNaive(value)
    and getattr(value, 'convertToLocalTime', True))
  return localtime(value) if shouldConvert else value


# Utilities

def localtime(value, timezone=None):
  """
  Converts an aware datetime.datetime to local time.

  Local time is defined by the current time zone, unless another time zone
  is specified.
  """
  if timezone is None:
    timezone = getCurrentTimezone()
  # If `value` is naive, astimezone() will raise a ValueError,
  # so we don't need to perform a redundant check.
  value = value.astimezone(timezone)
  if hasattr(timezone, 'normalize'):
    # This method is available for pytz time zones.
    value = timezone.normalize(value)
  return value


def now():
  """
  Returns an aware or naive datetime.datetime, depending on settings.USE_TZ.
  """
  if settings.USE_TZ:
    # timeit shows that datetime.now(tz=utc) is 24% slower
    return datetime.utcnow().replace(tzinfo=utc)
  else:
    return datetime.now()


# By design, these four functions don't perform any checks on their arguments.
# The caller should ensure that they don't receive an invalid value like None.

def isAware(value):
  """
  Determines if a given datetime.datetime is aware.

  The logic is described in Python's docs:
  http://docs.python.org/library/datetime.html#datetime.tzinfo
  """
  return value.tzinfo is not None and value.tzinfo.utcoffset(value) is not None


def isNaive(value):
  """
  Determines if a given datetime.datetime is naive.

  The logic is described in Python's docs:
  http://docs.python.org/library/datetime.html#datetime.tzinfo
  """
  return value.tzinfo is None or value.tzinfo.utcoffset(value) is None


def makeAware(value, timezone):
  """
  Makes a naive datetime.datetime in a given time zone aware.
  """
  if hasattr(timezone, 'localize'):
    # This method is available for pytz time zones.
    return timezone.localize(value, isDst=None)
  else:
    # Check that we won't overwrite the timezone of an aware datetime.
    if isAware(value):
      raise ValueError(
        "makeAware expects a naive datetime, got %s" % value)
    # This may be wrong around DST changes!
    return value.replace(tzinfo=timezone)


def makeNaive(value, timezone):
  """
  Makes an aware datetime.datetime naive in a given time zone.
  """
  # If `value` is naive, astimezone() will raise a ValueError,
  # so we don't need to perform a redundant check.
  value = value.astimezone(timezone)
  if hasattr(timezone, 'normalize'):
    # This method is available for pytz time zones.
    value = timezone.normalize(value)
  return value.replace(tzinfo=None)
