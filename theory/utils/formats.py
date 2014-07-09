# -*- coding: utf-8 -*-
#!/usr/bin/env python
import decimal
import datetime

from theory.conf import settings
from theory.utils.translation import getLanguage, toLocale, checkForLanguage
from theory.utils.importlib import importModule
from theory.utils.encoding import smartStr
from theory.utils.functional import lazy
from theory.utils import dateformat, numberformat, datetime_safe
from theory.utils.safestring import markSafe

# format_cache is a mapping from (format_type, lang) to the format string.
# By using the cache, it is possible to avoid running get_format_modules
# repeatedly.
_format_cache = {}
_format_modules_cache = {}

def reset_format_cache():
  """Clear any cached formats.

  This method is provided primarily for testing purposes,
  so that the effects of cached formats can be removed.
  """
  global _format_cache, _format_modules_cache
  _format_cache = {}
  _format_modules_cache = {}

def iter_format_modules(lang):
  """
  Does the heavy lifting of finding format modules.
  """
  if checkForLanguage(lang):
    format_locations = ['theory.conf.locale.%s']
    if settings.FORMAT_MODULE_PATH:
      format_locations.append(settings.FORMAT_MODULE_PATH + '.%s')
      format_locations.reverse()
    locale = toLocale(lang)
    locales = [locale]
    if '_' in locale:
      locales.append(locale.split('_')[0])
    for location in format_locations:
      for loc in locales:
        try:
          yield importModule('.formats', location % loc)
        except ImportError:
          pass

def get_format_modules(reverse=False):
  """
  Returns a list of the format modules found
  """
  lang = getLanguage()
  modules = _format_modules_cache.setdefault(lang, list(iter_format_modules(lang)))
  if reverse:
    return list(reversed(modules))
  return modules

def get_format(format_type, lang=None, use_l10n=None):
  """
  For a specific format type, returns the format for the current
  language (locale), defaults to the format in the settings.
  format_type is the name of the format, e.g. 'DATE_FORMAT'

  If use_l10n is provided and is not None, that will force the value to
  be localized (or not), overriding the value of settings.USE_L10N.
  """
  format_type = smartStr(format_type)
  if use_l10n or (use_l10n is None and settings.USE_L10N):
    if lang is None:
      lang = getLanguage()
    cache_key = (format_type, lang)
    try:
      return _format_cache[cache_key] or getattr(settings, format_type)
    except KeyError:
      for module in get_format_modules():
        try:
          val = getattr(module, format_type)
          _format_cache[cache_key] = val
          return val
        except AttributeError:
          pass
      _format_cache[cache_key] = None
  return getattr(settings, format_type)

get_format_lazy = lazy(get_format, unicode, list, tuple)

def date_format(value, format=None, use_l10n=None):
  """
  Formats a datetime.date or datetime.datetime object using a
  localizable format

  If use_l10n is provided and is not None, that will force the value to
  be localized (or not), overriding the value of settings.USE_L10N.
  """
  return dateformat.format(value, get_format(format or 'DATE_FORMAT', use_l10n=use_l10n))

def time_format(value, format=None, use_l10n=None):
  """
  Formats a datetime.time object using a localizable format

  If use_l10n is provided and is not None, that will force the value to
  be localized (or not), overriding the value of settings.USE_L10N.
  """
  return dateformat.time_format(value, get_format(format or 'TIME_FORMAT', use_l10n=use_l10n))

def number_format(value, decimal_pos=None, use_l10n=None):
  """
  Formats a numeric value using localization settings

  If use_l10n is provided and is not None, that will force the value to
  be localized (or not), overriding the value of settings.USE_L10N.
  """
  if use_l10n or (use_l10n is None and settings.USE_L10N):
    lang = getLanguage()
  else:
    lang = None
  return numberformat.format(
    value,
    get_format('DECIMAL_SEPARATOR', lang, use_l10n=use_l10n),
    decimal_pos,
    get_format('NUMBER_GROUPING', lang, use_l10n=use_l10n),
    get_format('THOUSAND_SEPARATOR', lang, use_l10n=use_l10n),
  )

def localize(value, use_l10n=None):
  """
  Checks if value is a localizable type (date, number...) and returns it
  formatted as a string using current locale format.

  If use_l10n is provided and is not None, that will force the value to
  be localized (or not), overriding the value of settings.USE_L10N.
  """
  if isinstance(value, bool):
    return mark_safe(unicode(value))
  elif isinstance(value, (decimal.Decimal, float, int, long)):
    return number_format(value, use_l10n=use_l10n)
  elif isinstance(value, datetime.datetime):
    return date_format(value, 'DATETIME_FORMAT', use_l10n=use_l10n)
  elif isinstance(value, datetime.date):
    return date_format(value, use_l10n=use_l10n)
  elif isinstance(value, datetime.time):
    return time_format(value, 'TIME_FORMAT', use_l10n=use_l10n)
  else:
    return value

def localize_input(value, default=None):
  """
  Checks if an input value is a localizable type and returns it
  formatted with the appropriate formatting string of the current locale.
  """
  if isinstance(value, (decimal.Decimal, float, int, long)):
    return number_format(value)
  elif isinstance(value, datetime.datetime):
    value = datetime_safe.new_datetime(value)
    format = smartStr(default or get_format('DATETIME_INPUT_FORMATS')[0])
    return value.strftime(format)
  elif isinstance(value, datetime.date):
    value = datetime_safe.new_date(value)
    format = smartStr(default or get_format('DATE_INPUT_FORMATS')[0])
    return value.strftime(format)
  elif isinstance(value, datetime.time):
    format = smartStr(default or get_format('TIME_INPUT_FORMATS')[0])
    return value.strftime(format)
  return value

def sanitize_separators(value):
  """
  Sanitizes a value according to the current decimal and
  thousand separator setting. Used with form field input.
  """
  if settings.USE_L10N:
    decimal_separator = get_format('DECIMAL_SEPARATOR')
    if isinstance(value, basestring):
      parts = []
      if decimal_separator in value:
        value, decimals = value.split(decimal_separator, 1)
        parts.append(decimals)
      if settings.USE_THOUSAND_SEPARATOR:
        parts.append(value.replace(get_format('THOUSAND_SEPARATOR'), ''))
      else:
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
