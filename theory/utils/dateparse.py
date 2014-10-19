"""Functions to parse datetime objects."""

# We're using regular expressions rather than time.strptime because:
# - They provide both validation and parsing.
# - They're more flexible for datetimes.
# - The date/datetime/time constructors produce friendlier error messages.

import datetime
import re
from theory.utils import six
from theory.utils.timezone import utc, getFixedTimezone


dateRe = re.compile(
  r'(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})$'
)

timeRe = re.compile(
  r'(?P<hour>\d{1,2}):(?P<minute>\d{1,2})'
  r'(?::(?P<second>\d{1,2})(?:\.(?P<microsecond>\d{1,6})\d{0,6})?)?'
)

datetimeRe = re.compile(
  r'(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})'
  r'[T ](?P<hour>\d{1,2}):(?P<minute>\d{1,2})'
  r'(?::(?P<second>\d{1,2})(?:\.(?P<microsecond>\d{1,6})\d{0,6})?)?'
  r'(?P<tzinfo>Z|[+-]\d{2}(?::?\d{2})?)?$'
)


def parseDate(value):
  """Parses a string and return a datetime.date.

  Raises ValueError if the input is well formatted but not a valid date.
  Returns None if the input isn't well formatted.
  """
  match = dateRe.match(value)
  if match:
    kw = dict((k, int(v)) for k, v in six.iteritems(match.groupdict()))
    return datetime.date(**kw)


def parseTime(value):
  """Parses a string and return a datetime.time.

  This function doesn't support time zone offsets.

  Raises ValueError if the input is well formatted but not a valid time.
  Returns None if the input isn't well formatted, in particular if it
  contains an offset.
  """
  match = timeRe.match(value)
  if match:
    kw = match.groupdict()
    if kw['microsecond']:
      kw['microsecond'] = kw['microsecond'].ljust(6, '0')
    kw = dict((k, int(v)) for k, v in six.iteritems(kw) if v is not None)
    return datetime.time(**kw)


def parseDatetime(value):
  """Parses a string and return a datetime.datetime.

  This function supports time zone offsets. When the input contains one,
  the output uses a timezone with a fixed offset from UTC.

  Raises ValueError if the input is well formatted but not a valid datetime.
  Returns None if the input isn't well formatted.
  """
  match = datetimeRe.match(value)
  if match:
    kw = match.groupdict()
    if kw['microsecond']:
      kw['microsecond'] = kw['microsecond'].ljust(6, '0')
    tzinfo = kw.pop('tzinfo')
    if tzinfo == 'Z':
      tzinfo = utc
    elif tzinfo is not None:
      offsetMins = int(tzinfo[-2:]) if len(tzinfo) > 3 else 0
      offset = 60 * int(tzinfo[1:3]) + offsetMins
      if tzinfo[0] == '-':
        offset = -offset
      tzinfo = getFixedTimezone(offset)
    kw = dict((k, int(v)) for k, v in six.iteritems(kw) if v is not None)
    kw['tzinfo'] = tzinfo
    return datetime.datetime(**kw)
