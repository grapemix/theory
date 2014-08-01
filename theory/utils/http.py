# -*- coding: utf-8 -*-
#!/usr/bin/env python
from __future__ import unicode_literals

import base64
import calendar
import datetime
import re
import sys

from binascii import Error as BinasciiError
from email.utils import formatdate

from theory.utils.datastructures import MultiValueDict
from theory.utils.encoding import forceStr, forceText
from theory.utils.functional import allowLazy
from theory.utils import six
from theory.utils.six.moves.urllib.parse import (
  quote, quote_plus, unquote, unquote_plus, urlparse,
  urlencode as originalUrlencode)

ETAG_MATCH = re.compile(r'(?:W/)?"((?:\\.|[^"])*)"')

MONTHS = 'jan feb mar apr may jun jul aug sep oct nov dec'.split()
__D = r'(?P<day>\d{2})'
__D2 = r'(?P<day>[ \d]\d)'
__M = r'(?P<mon>\w{3})'
__Y = r'(?P<year>\d{4})'
__Y2 = r'(?P<year>\d{2})'
__T = r'(?P<hour>\d{2}):(?P<min>\d{2}):(?P<sec>\d{2})'
RFC1123_DATE = re.compile(r'^\w{3}, %s %s %s %s GMT$' % (__D, __M, __Y, __T))
RFC850_DATE = re.compile(r'^\w{6,9}, %s-%s-%s %s GMT$' % (__D, __M, __Y2, __T))
ASCTIME_DATE = re.compile(r'^\w{3} %s %s %s %s$' % (__M, __D2, __T, __Y))

RFC3986_GENDELIMS = str(":/?#[]@")
RFC3986_SUBDELIMS = str("!$&'()*+,;=")


def urlquote(url, safe='/'):
  """
  A version of Python's urllib.quote() function that can operate on unicode
  strings. The url is first UTF-8 encoded before quoting. The returned string
  can safely be used as part of an argument to a subsequent iriToUri() call
  without double-quoting occurring.
  """
  return forceText(quote(forceStr(url), forceStr(safe)))
urlquote = allowLazy(urlquote, six.textType)


def urlquotePlus(url, safe=''):
  """
  A version of Python's urllib.quote_plus() function that can operate on
  unicode strings. The url is first UTF-8 encoded before quoting. The
  returned string can safely be used as part of an argument to a subsequent
  iriToUri() call without double-quoting occurring.
  """
  return forceText(quote_plus(forceStr(url), forceStr(safe)))
urlquotePlus = allowLazy(urlquotePlus, six.textType)


def urlunquote(quotedUrl):
  """
  A wrapper for Python's urllib.unquote() function that can operate on
  the result of theory.utils.http.urlquote().
  """
  return forceText(unquote(forceStr(quotedUrl)))
urlunquote = allowLazy(urlunquote, six.textType)


def urlunquotePlus(quotedUrl):
  """
  A wrapper for Python's urllib.unquote_plus() function that can operate on
  the result of theory.utils.http.urlquotePlus().
  """
  return forceText(unquote_plus(forceStr(quotedUrl)))
urlunquotePlus = allowLazy(urlunquotePlus, six.textType)


def urlencode(query, doseq=0):
  """
  A version of Python's urllib.urlencode() function that can operate on
  unicode strings. The parameters are first cast to UTF-8 encoded strings and
  then encoded as per normal.
  """
  if isinstance(query, MultiValueDict):
    query = query.lists()
  elif hasattr(query, 'items'):
    query = query.items()
  return originalUrlencode(
    [(forceStr(k),
     [forceStr(i) for i in v] if isinstance(v, (list, tuple)) else forceStr(v))
      for k, v in query],
    doseq)


def cookieDate(epochSeconds=None):
  """
  Formats the time to ensure compatibility with Netscape's cookie standard.

  Accepts a floating point number expressed in seconds since the epoch, in
  UTC - such as that outputted by time.time(). If set to None, defaults to
  the current time.

  Outputs a string in the format 'Wdy, DD-Mon-YYYY HH:MM:SS GMT'.
  """
  rfcdate = formatdate(epochSeconds)
  return '%s-%s-%s GMT' % (rfcdate[:7], rfcdate[8:11], rfcdate[12:25])


def httpDate(epochSeconds=None):
  """
  Formats the time to match the RFC1123 date format as specified by HTTP
  RFC2616 section 3.3.1.

  Accepts a floating point number expressed in seconds since the epoch, in
  UTC - such as that outputted by time.time(). If set to None, defaults to
  the current time.

  Outputs a string in the format 'Wdy, DD Mon YYYY HH:MM:SS GMT'.
  """
  return formatdate(epochSeconds, usegmt=True)


def parseHttpDate(date):
  """
  Parses a date format as specified by HTTP RFC2616 section 3.3.1.

  The three formats allowed by the RFC are accepted, even if only the first
  one is still in widespread use.

  Returns an integer expressed in seconds since the epoch, in UTC.
  """
  # emails.Util.parsedate does the job for RFC1123 dates; unfortunately
  # RFC2616 makes it mandatory to support RFC850 dates too. So we roll
  # our own RFC-compliant parsing.
  for regex in RFC1123_DATE, RFC850_DATE, ASCTIME_DATE:
    m = regex.match(date)
    if m is not None:
      break
  else:
    raise ValueError("%r is not in a valid HTTP date format" % date)
  try:
    year = int(m.group('year'))
    if year < 100:
      if year < 70:
        year += 2000
      else:
        year += 1900
    month = MONTHS.index(m.group('mon').lower()) + 1
    day = int(m.group('day'))
    hour = int(m.group('hour'))
    min = int(m.group('min'))
    sec = int(m.group('sec'))
    result = datetime.datetime(year, month, day, hour, min, sec)
    return calendar.timegm(result.utctimetuple())
  except Exception:
    six.reraise(ValueError, ValueError("%r is not a valid date" % date), sys.excInfo()[2])


def parseHttpDateSafe(date):
  """
  Same as parseHttpDate, but returns None if the input is invalid.
  """
  try:
    return parseHttpDate(date)
  except Exception:
    pass


# Base 36 functions: useful for generating compact URLs

def base36ToInt(s):
  """
  Converts a base 36 string to an ``int``. Raises ``ValueError` if the
  input won't fit into an int.
  """
  # To prevent overconsumption of server resources, reject any
  # base36 string that is long than 13 base36 digits (13 digits
  # is sufficient to base36-encode any 64-bit integer)
  if len(s) > 13:
    raise ValueError("Base36 input too large")
  value = int(s, 36)
  # ... then do a final check that the value will fit into an int to avoid
  # returning a long (#15067). The long type was removed in Python 3.
  if six.PY2 and value > sys.maxint:
    raise ValueError("Base36 input too large")
  return value


def intToBase36(i):
  """
  Converts an integer to a base36 string
  """
  digits = "0123456789abcdefghijklmnopqrstuvwxyz"
  factor = 0
  if i < 0:
    raise ValueError("Negative base36 conversion input.")
  if six.PY2:
    if not isinstance(i, six.integerTypes):
      raise TypeError("Non-integer base36 conversion input.")
    if i > sys.maxint:
      raise ValueError("Base36 conversion input too large.")
  # Find starting factor
  while True:
    factor += 1
    if i < 36 ** factor:
      factor -= 1
      break
  base36 = []
  # Construct base36 representation
  while factor >= 0:
    j = 36 ** factor
    base36.append(digits[i // j])
    i = i % j
    factor -= 1
  return ''.join(base36)


def urlsafeBase64Encode(s):
  """
  Encodes a bytestring in base64 for use in URLs, stripping any trailing
  equal signs.
  """
  return base64.urlsafeB64encode(s).rstrip(b'\n=')


def urlsafeBase64Decode(s):
  """
  Decodes a base64 encoded string, adding back any trailing equal signs that
  might have been stripped.
  """
  s = s.encode('utf-8')  # base64encode should only return ASCII.
  try:
    return base64.urlsafeB64decode(s.ljust(len(s) + len(s) % 4, b'='))
  except (LookupError, BinasciiError) as e:
    raise ValueError(e)


def parseEtags(etagStr):
  """
  Parses a string with one or several etags passed in If-None-Match and
  If-Match headers by the rules in RFC 2616. Returns a list of etags
  without surrounding double quotes (") and unescaped from \<CHAR>.
  """
  etags = ETAG_MATCH.findall(etagStr)
  if not etags:
    # etagStr has wrong format, treat it as an opaque string then
    return [etagStr]
  etags = [e.encode('ascii').decode('unicodeEscape') for e in etags]
  return etags


def quoteEtag(etag):
  """
  Wraps a string in double quotes escaping contents as necessary.
  """
  return '"%s"' % etag.replace('\\', '\\\\').replace('"', '\\"')


def sameOrigin(url1, url2):
  """
  Checks if two URLs are 'same-origin'
  """
  p1, p2 = urlparse(url1), urlparse(url2)
  try:
    return (p1.scheme, p1.hostname, p1.port) == (p2.scheme, p2.hostname, p2.port)
  except ValueError:
    return False


def isSafeUrl(url, host=None):
  """
  Return ``True`` if the url is a safe redirection (i.e. it doesn't point to
  a different host and uses a safe scheme).

  Always returns ``False`` on an empty url.
  """
  if not url:
    return False
  # Chrome treats \ completely as /
  url = url.replace('\\', '/')
  # Chrome considers any URL with more than two slashes to be absolute, but
  # urlparse is not so flexible. Treat any url with three slashes as unsafe.
  if url.startswith('///'):
    return False
  urlInfo = urlparse(url)
  # Forbid URLs like http:///example.com - with a scheme, but without a hostname.
  # In that URL, example.com is not the hostname but, a path component. However,
  # Chrome will still consider example.com to be the hostname, so we must not
  # allow this syntax.
  if not urlInfo.netloc and urlInfo.scheme:
    return False
  return ((not urlInfo.netloc or urlInfo.netloc == host) and
      (not urlInfo.scheme or urlInfo.scheme in ['http', 'https']))
