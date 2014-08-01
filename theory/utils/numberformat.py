# -*- coding: utf-8 -*-
#!/usr/bin/env python
from theory.conf import settings
from theory.utils.safestring import markSafe
from theory.utils import six


def format(number, decimalSep, decimalPos=None, grouping=0, thousandSep='',
      forceGrouping=False):
  """
  Gets a number (as a number or string), and returns it as a string,
  using formats defined as arguments:

  * decimalSep: Decimal separator symbol (for example ".")
  * decimalPos: Number of decimal positions
  * grouping: Number of digits in every group limited by thousand separator
  * thousandSep: Thousand separator symbol (for example ",")
  """
  useGrouping = settings.USE_L10N and settings.USE_THOUSAND_SEPARATOR
  useGrouping = useGrouping or forceGrouping
  useGrouping = useGrouping and grouping > 0
  # Make the common case fast
  if isinstance(number, int) and not useGrouping and not decimalPos:
    return markSafe(six.textType(number))
  # sign
  sign = ''
  strNumber = six.textType(number)
  if strNumber[0] == '-':
    sign = '-'
    strNumber = strNumber[1:]
  # decimal part
  if '.' in strNumber:
    intPart, decPart = strNumber.split('.')
    if decimalPos is not None:
      decPart = decPart[:decimalPos]
  else:
    intPart, decPart = strNumber, ''
  if decimalPos is not None:
    decPart = decPart + ('0' * (decimalPos - len(decPart)))
  if decPart:
    decPart = decimalSep + decPart
  # grouping
  if useGrouping:
    intPartGd = ''
    for cnt, digit in enumerate(intPart[::-1]):
      if cnt and not cnt % grouping:
        intPartGd += thousandSep
      intPartGd += digit
    intPart = intPartGd[::-1]
  return sign + intPart + decPart
