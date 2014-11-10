# -*- coding: utf-8 -*-
#!/usr/bin/env python
from __future__ import absolute_import  # Avoid importing `importlib` from this package.

import decimal
import datetime
from importlib import import_module
import unicodedata

from theory.conf import settings
from theory.utils import dateformat, numberformat, datetimeSafe
from theory.utils.encoding import forceStr
from theory.utils.functional import lazy
from theory.utils.safestring import markSafe
from theory.utils import six
from theory.utils.translation import getLanguage, toLocale, checkForLanguage

# formatCache is a mapping from (formatType, lang) to the format string.
# By using the cache, it is possible to avoid running getFormatModules
# repeatedly.
_formatCache = {}
_formatModulesCache = {}

ISO_INPUT_FORMATS = {
  'DATE_INPUT_FORMATS': ('%Y-%m-%d',),
  'TIME_INPUT_FORMATS': ('%H:%M:%S', '%H:%M:%S.%f', '%H:%M'),
  'DATETIME_INPUT_FORMATS': (
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M:%S.%f',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%d'
  ),
}


def resetFormatCache():
  """Clear any cached formats.

  This method is provided primarily for testing purposes,
  so that the effects of cached formats can be removed.
  """
  global _formatCache, _formatModulesCache
  _formatCache = {}
  _formatModulesCache = {}


def iterFormatModules(lang, formatModulePath=None):
  """
  Does the heavy lifting of finding format modules.
  """
  if not checkForLanguage(lang):
    return

  if formatModulePath is None:
    formatModulePath = settings.FORMAT_MODULE_PATH

  formatLocations = []
  if formatModulePath:
    if isinstance(formatModulePath, six.stringTypes):
      formatModulePath = [formatModulePath]
    for path in formatModulePath:
      formatLocations.append(path + '.%s')
  formatLocations.append('theory.conf.locale.%s')
  locale = toLocale(lang)
  locales = [locale]
  if '_' in locale:
    locales.append(locale.split('_')[0])
  for location in formatLocations:
    for loc in locales:
      try:
        yield import_module('%s.formats' % (location % loc))
      except ImportError:
        pass


def getFormatModules(lang=None, reverse=False):
  """
  Returns a list of the format modules found
  """
  if lang is None:
    lang = getLanguage()
  modules = _formatModulesCache.setdefault(lang, list(iterFormatModules(lang, settings.FORMAT_MODULE_PATH)))
  if reverse:
    return list(reversed(modules))
  return modules


def getFormat(formatType, lang=None, useL10n=None):
  """
  For a specific format type, returns the format for the current
  language (locale), defaults to the format in the settings.
  formatType is the name of the format, e.g. 'DATE_FORMAT'

  If useL10n is provided and is not None, that will force the value to
  be localized (or not), overriding the value of settings.USE_L10N.
  """
  formatType = forceStr(formatType)
  if useL10n or (useL10n is None and settings.USE_L10N):
    if lang is None:
      lang = getLanguage()
    cacheKey = (formatType, lang)
    try:
      cached = _formatCache[cacheKey]
      if cached is not None:
        return cached
      else:
        # Return the general setting by default
        return getattr(settings, formatType)
    except KeyError:
      for module in getFormatModules(lang):
        try:
          val = getattr(module, formatType)
          for isoInput in ISO_INPUT_FORMATS.get(formatType, ()):
            if isoInput not in val:
              if isinstance(val, tuple):
                val = list(val)
              val.append(isoInput)
          _formatCache[cacheKey] = val
          return val
        except AttributeError:
          pass
      _formatCache[cacheKey] = None
  return getattr(settings, formatType)

getFormatLazy = lazy(getFormat, six.textType, list, tuple)


def dateFormat(value, format=None, useL10n=None):
  """
  Formats a datetime.date or datetime.datetime object using a
  localizable format

  If useL10n is provided and is not None, that will force the value to
  be localized (or not), overriding the value of settings.USE_L10N.
  """
  return dateformat.format(value, getFormat(format or 'DATE_FORMAT', useL10n=useL10n))


def timeFormat(value, format=None, useL10n=None):
  """
  Formats a datetime.time object using a localizable format

  If useL10n is provided and is not None, that will force the value to
  be localized (or not), overriding the value of settings.USE_L10N.
  """
  return dateformat.timeFormat(value, getFormat(format or 'TIME_FORMAT', useL10n=useL10n))


def numberFormat(value, decimalPos=None, useL10n=None, forceGrouping=False):
  """
  Formats a numeric value using localization settings

  If useL10n is provided and is not None, that will force the value to
  be localized (or not), overriding the value of settings.USE_L10N.
  """
  if useL10n or (useL10n is None and settings.USE_L10N):
    lang = getLanguage()
  else:
    lang = None
  return numberformat.format(
    value,
    getFormat('DECIMAL_SEPARATOR', lang, useL10n=useL10n),
    decimalPos,
    getFormat('NUMBER_GROUPING', lang, useL10n=useL10n),
    getFormat('THOUSAND_SEPARATOR', lang, useL10n=useL10n),
    forceGrouping=forceGrouping
  )


def localize(value, useL10n=None):
  """
  Checks if value is a localizable type (date, number...) and returns it
  formatted as a string using current locale format.

  If useL10n is provided and is not None, that will force the value to
  be localized (or not), overriding the value of settings.USE_L10N.
  """
  if isinstance(value, bool):
    return markSafe(six.textType(value))
  elif isinstance(value, (decimal.Decimal, float) + six.integerTypes):
    return numberFormat(value, useL10n=useL10n)
  elif isinstance(value, datetime.datetime):
    return dateFormat(value, 'DATETIME_FORMAT', useL10n=useL10n)
  elif isinstance(value, datetime.date):
    return dateFormat(value, useL10n=useL10n)
  elif isinstance(value, datetime.time):
    return timeFormat(value, 'TIME_FORMAT', useL10n=useL10n)
  else:
    return value


def localizeInput(value, default=None):
  """
  Checks if an input value is a localizable type and returns it
  formatted with the appropriate formatting string of the current locale.
  """
  if isinstance(value, (decimal.Decimal, float) + six.integerTypes):
    return numberFormat(value)
  elif isinstance(value, datetime.datetime):
    value = datetimeSafe.newDatetime(value)
    format = forceStr(default or getFormat('DATETIME_INPUT_FORMATS')[0])
    return value.strftime(format)
  elif isinstance(value, datetime.date):
    value = datetimeSafe.newDate(value)
    format = forceStr(default or getFormat('DATE_INPUT_FORMATS')[0])
    return value.strftime(format)
  elif isinstance(value, datetime.time):
    format = forceStr(default or getFormat('TIME_INPUT_FORMATS')[0])
    return value.strftime(format)
  return value


def sanitizeSeparators(value):
  """
  Sanitizes a value according to the current decimal and
  thousand separator setting. Used with form field input.
  """
  if settings.USE_L10N and isinstance(value, six.stringTypes):
    parts = []
    decimalSeparator = getFormat('DECIMAL_SEPARATOR')
    if decimalSeparator in value:
      value, decimals = value.split(decimalSeparator, 1)
      parts.append(decimals)
    if settings.USE_THOUSAND_SEPARATOR:
      thousandSep = getFormat('THOUSAND_SEPARATOR')
      for replacement in set([
          thousandSep, unicodedata.normalize('NFKD', thousandSep)]):
        value = value.replace(replacement, '')
    parts.append(value)
    value = '.'.join(reversed(parts))
  return value

SYMBOLS = {
    'default'     : ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'),
    'customary'     : ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y'),
    'customary_ext' : ('byte', 'kilo', 'mega', 'giga', 'tera', 'peta', 'exa',
                       'zetta', 'iotta'),
    'iec'           : ('Bi', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi'),
    'iec_ext'       : ('byte', 'kibi', 'mebi', 'gibi', 'tebi', 'pebi', 'exbi',
                       'zebi', 'yobi'),
}

def bytes2human(n, format='%(value).1f %(symbol)s', symbols='default'):
    """
    Bytes-to-human / human-to-bytes converter.
    Based on: http://goo.gl/kTQMs
    Working with Python 2.x and 3.x.

    Author: Giampaolo Rodola' <g.rodola [AT] gmail [DOT] com>
    License: MIT

    Convert n bytes into a human readable string based on format.
    symbols can be either "customary", "customary_ext", "iec" or "iec_ext",
    see: http://goo.gl/kTQMs

      >>> bytes2human(0)
      '0.0 B'
      >>> bytes2human(0.9)
      '0.0 B'
      >>> bytes2human(1)
      '1.0 B'
      >>> bytes2human(1.9)
      '1.0 B'
      >>> bytes2human(1024)
      '1.0 K'
      >>> bytes2human(1048576)
      '1.0 M'
      >>> bytes2human(1099511627776127398123789121)
      '909.5 Y'

      >>> bytes2human(9856, symbols="customary")
      '9.6 K'
      >>> bytes2human(9856, symbols="customary_ext")
      '9.6 kilo'
      >>> bytes2human(9856, symbols="iec")
      '9.6 Ki'
      >>> bytes2human(9856, symbols="iec_ext")
      '9.6 kibi'

      >>> bytes2human(10000, "%(value).1f %(symbol)s/sec")
      '9.8 K/sec'

      >>> # precision can be adjusted by playing with %f operator
      >>> bytes2human(10000, format="%(value).5f %(symbol)s")
      '9.76562 K'
    """
    n = int(n)
    if n < 0:
        raise ValueError("n < 0")
    symbols = SYMBOLS[symbols]
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i+1)*10
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return format % locals()
    return format % dict(symbol=symbols[0], value=n)

def human2bytes(s):
    """
    Bytes-to-human / human-to-bytes converter.
    Based on: http://goo.gl/kTQMs
    Working with Python 2.x and 3.x.

    Author: Giampaolo Rodola' <g.rodola [AT] gmail [DOT] com>
    License: MIT

    Attempts to guess the string format based on default symbols
    set and return the corresponding bytes as an integer.
    When unable to recognize the format ValueError is raised.

      >>> human2bytes('0 B')
      0
      >>> human2bytes('1 K')
      1024
      >>> human2bytes('1 M')
      1048576
      >>> human2bytes('1 Gi')
      1073741824
      >>> human2bytes('1 tera')
      1099511627776

      >>> human2bytes('0.5kilo')
      512
      >>> human2bytes('0.1  byte')
      0
      >>> human2bytes('1 k')  # k is an alias for K
      1024
      >>> human2bytes('12 foo')
      Traceback (most recent call last):
          ...
      ValueError: can't interpret '12 foo'
    """
    init = s
    num = ""
    while s and s[0:1].isdigit() or s[0:1] == '.':
        num += s[0]
        s = s[1:]
    num = float(num)
    letter = s.strip()
    for name, sset in SYMBOLS.items():
        if letter in sset:
            break
    else:
        if letter == 'k':
            # treat 'k' as an alias for 'K' as per: http://goo.gl/kTQMs
            sset = SYMBOLS['customary']
            letter = letter.upper()
        else:
            raise ValueError("can't interpret %r" % init)
    prefix = {sset[0]:1}
    for i, s in enumerate(sset[1:]):
        prefix[s] = 1 << (i+1)*10
    return int(num * prefix[letter])
