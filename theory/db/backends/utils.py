from __future__ import unicode_literals

import datetime
import decimal
import hashlib
import logging
from time import time

from theory.conf import settings
from theory.utils.encoding import forceBytes
from theory.utils.timezone import utc


logger = logging.getLogger('theory.db.backends')


class CursorWrapper(object):
  def __init__(self, cursor, db):
    self.cursor = cursor
    self.db = db

  WRAP_ERROR_ATTRS = frozenset(['fetchone', 'fetchmany', 'fetchall', 'nextset'])

  def __getattr__(self, attr):
    cursorAttr = getattr(self.cursor, attr)
    if attr in CursorWrapper.WRAP_ERROR_ATTRS:
      return self.db.wrapDatabaseErrors(cursorAttr)
    else:
      return cursorAttr

  def __iter__(self):
    return iter(self.cursor)

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    # Ticket #17671 - Close instead of passing thru to avoid backend
    # specific behavior. Catch errors liberally because errors in cleanup
    # code aren't useful.
    try:
      self.close()
    except self.db.Database.Error:
      pass

  # The following methods cannot be implemented in __getattr__, because the
  # code must run when the method is invoked, not just when it is accessed.

  def callproc(self, procname, params=None):
    self.db.validateNoBrokenTransaction()
    self.db.setDirty()
    with self.db.wrapDatabaseErrors:
      if params is None:
        return self.cursor.callproc(procname)
      else:
        return self.cursor.callproc(procname, params)

  def execute(self, sql, params=None):
    self.db.validateNoBrokenTransaction()
    self.db.setDirty()
    with self.db.wrapDatabaseErrors:
      if params is None:
        return self.cursor.execute(sql)
      else:
        return self.cursor.execute(sql, params)

  def executemany(self, sql, paramList):
    self.db.validateNoBrokenTransaction()
    self.db.setDirty()
    with self.db.wrapDatabaseErrors:
      return self.cursor.executemany(sql, paramList)


class CursorDebugWrapper(CursorWrapper):

  # XXX callproc isn't instrumented at this time.

  def execute(self, sql, params=None):
    start = time()
    try:
      return super(CursorDebugWrapper, self).execute(sql, params)
    finally:
      stop = time()
      duration = stop - start
      sql = self.db.ops.lastExecutedQuery(self.cursor, sql, params)
      self.db.queries.append({
        'sql': sql,
        'time': "%.3f" % duration,
      })
      logger.debug('(%.3f) %s; args=%s' % (duration, sql, params),
        extra={'duration': duration, 'sql': sql, 'params': params}
      )

  def executemany(self, sql, paramList):
    start = time()
    try:
      return super(CursorDebugWrapper, self).executemany(sql, paramList)
    finally:
      stop = time()
      duration = stop - start
      try:
        times = len(paramList)
      except TypeError:           # paramList could be an iterator
        times = '?'
      self.db.queries.append({
        'sql': '%s times: %s' % (times, sql),
        'time': "%.3f" % duration,
      })
      logger.debug('(%.3f) %s; args=%s' % (duration, sql, paramList),
        extra={'duration': duration, 'sql': sql, 'params': paramList}
      )


###############################################
# Converters from database (string) to Python #
###############################################

def typecastDate(s):
  return datetime.date(*map(int, s.split('-'))) if s else None  # returns None if s is null


def typecastTime(s):  # does NOT store time zone information
  if not s:
    return None
  hour, minutes, seconds = s.split(':')
  if '.' in seconds:  # check whether seconds have a fractional part
    seconds, microseconds = seconds.split('.')
  else:
    microseconds = '0'
  return datetime.time(int(hour), int(minutes), int(seconds), int(float('.' + microseconds) * 1000000))


def typecastTimestamp(s):  # does NOT store time zone information
  # "2005-07-29 15:48:00.590358-05"
  # "2005-07-29 09:56:00-05"
  if not s:
    return None
  if ' ' not in s:
    return typecastDate(s)
  d, t = s.split()
  # Extract timezone information, if it exists. Currently we just throw
  # it away, but in the future we may make use of it.
  if '-' in t:
    t, tz = t.split('-', 1)
    tz = '-' + tz
  elif '+' in t:
    t, tz = t.split('+', 1)
    tz = '+' + tz
  else:
    tz = ''
  dates = d.split('-')
  times = t.split(':')
  seconds = times[2]
  if '.' in seconds:  # check whether seconds have a fractional part
    seconds, microseconds = seconds.split('.')
  else:
    microseconds = '0'
  tzinfo = utc if settings.USE_TZ else None
  return datetime.datetime(int(dates[0]), int(dates[1]), int(dates[2]),
    int(times[0]), int(times[1]), int(seconds),
    int((microseconds + '000000')[:6]), tzinfo)


def typecastDecimal(s):
  if s is None or s == '':
    return None
  return decimal.Decimal(s)


###############################################
# Converters from Python to database (string) #
###############################################

def revTypecastDecimal(d):
  if d is None:
    return None
  return str(d)


def truncateName(name, length=None, hashLen=4):
  """Shortens a string to a repeatable mangled version with the given length.
  """
  if length is None or len(name) <= length:
    return name

  hsh = hashlib.md5(forceBytes(name)).hexdigest()[:hashLen]
  return '%s%s' % (name[:length - hashLen], hsh)


def formatNumber(value, maxDigits, decimalPlaces):
  """
  Formats a number into a string with the requisite number of digits and
  decimal places.
  """
  if isinstance(value, decimal.Decimal):
    context = decimal.getcontext().copy()
    context.prec = maxDigits
    return "{0:f}".format(value.quantize(decimal.Decimal(".1") ** decimalPlaces, context=context))
  else:
    return "%.*f" % (decimalPlaces, value)
