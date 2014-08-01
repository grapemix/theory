# This code was mostly based on ipaddr-py
# Copyright 2007 Google Inc. http://code.google.com/p/ipaddr-py/
# Licensed under the Apache License, Version 2.0 (the "License").
from theory.core.exceptions import ValidationError
from theory.utils.translation import ugettextLazy as _
from theory.utils.six.moves import xrange


def cleanIpv6Address(ipStr, unpackIpv4=False,
    errorMessage=_("This is not a valid IPv6 address.")):
  """
  Cleans an IPv6 address string.

  Validity is checked by calling isValidIpv6Address() - if an
  invalid address is passed, ValidationError is raised.

  Replaces the longest continuous zero-sequence with "::" and
  removes leading zeroes and makes sure all hextets are lowercase.

  Args:
    ipStr: A valid IPv6 address.
    unpackIpv4: if an IPv4-mapped address is found,
    return the plain IPv4 address (default=False).
    errorMessage: A error message for in the ValidationError.

  Returns:
    A compressed IPv6 address, or the same value

  """
  bestDoublecolonStart = -1
  bestDoublecolonLen = 0
  doublecolonStart = -1
  doublecolonLen = 0

  if not isValidIpv6Address(ipStr):
    raise ValidationError(errorMessage, code='invalid')

  # This algorithm can only handle fully exploded
  # IP strings
  ipStr = _explodeShorthandIpString(ipStr)

  ipStr = _sanitizeIpv4Mapping(ipStr)

  # If needed, unpack the IPv4 and return straight away
  # - no need in running the rest of the algorithm
  if unpackIpv4:
    ipv4Unpacked = _unpackIpv4(ipStr)

    if ipv4Unpacked:
      return ipv4Unpacked

  hextets = ipStr.split(":")

  for index in range(len(hextets)):
    # Remove leading zeroes
    hextets[index] = hextets[index].lstrip('0')
    if not hextets[index]:
      hextets[index] = '0'

    # Determine best hextet to compress
    if hextets[index] == '0':
      doublecolonLen += 1
      if doublecolonStart == -1:
        # Start of a sequence of zeros.
        doublecolonStart = index
      if doublecolonLen > bestDoublecolonLen:
        # This is the longest sequence of zeros so far.
        bestDoublecolonLen = doublecolonLen
        bestDoublecolonStart = doublecolonStart
    else:
      doublecolonLen = 0
      doublecolonStart = -1

  # Compress the most suitable hextet
  if bestDoublecolonLen > 1:
    bestDoublecolonEnd = (bestDoublecolonStart +
                bestDoublecolonLen)
    # For zeros at the end of the address.
    if bestDoublecolonEnd == len(hextets):
      hextets += ['']
    hextets[bestDoublecolonStart:bestDoublecolonEnd] = ['']
    # For zeros at the beginning of the address.
    if bestDoublecolonStart == 0:
      hextets = [''] + hextets

  result = ":".join(hextets)

  return result.lower()


def _sanitizeIpv4Mapping(ipStr):
  """
  Sanitize IPv4 mapping in an expanded IPv6 address.

  This converts ::ffff:0a0a:0a0a to ::ffff:10.10.10.10.
  If there is nothing to sanitize, returns an unchanged
  string.

  Args:
    ipStr: A string, the expanded IPv6 address.

  Returns:
    The sanitized output string, if applicable.
  """
  if not ipStr.lower().startswith('0000:0000:0000:0000:0000:ffff:'):
    # not an ipv4 mapping
    return ipStr

  hextets = ipStr.split(':')

  if '.' in hextets[-1]:
    # already sanitized
    return ipStr

  ipv4Address = "%d.%d.%d.%d" % (
    int(hextets[6][0:2], 16),
    int(hextets[6][2:4], 16),
    int(hextets[7][0:2], 16),
    int(hextets[7][2:4], 16),
  )

  result = ':'.join(hextets[0:6])
  result += ':' + ipv4Address

  return result


def _unpackIpv4(ipStr):
  """
  Unpack an IPv4 address that was mapped in a compressed IPv6 address.

  This converts 0000:0000:0000:0000:0000:ffff:10.10.10.10 to 10.10.10.10.
  If there is nothing to sanitize, returns None.

  Args:
    ipStr: A string, the expanded IPv6 address.

  Returns:
    The unpacked IPv4 address, or None if there was nothing to unpack.
  """
  if not ipStr.lower().startswith('0000:0000:0000:0000:0000:ffff:'):
    return None

  return ipStr.rsplit(':', 1)[1]


def isValidIpv6Address(ipStr):
  """
  Ensure we have a valid IPv6 address.

  Args:
    ipStr: A string, the IPv6 address.

  Returns:
    A boolean, True if this is a valid IPv6 address.

  """
  from theory.core.validators import validateIpv4Address

  # We need to have at least one ':'.
  if ':' not in ipStr:
    return False

  # We can only have one '::' shortener.
  if ipStr.count('::') > 1:
    return False

  # '::' should be encompassed by start, digits or end.
  if ':::' in ipStr:
    return False

  # A single colon can neither start nor end an address.
  if ((ipStr.startswith(':') and not ipStr.startswith('::')) or
      (ipStr.endswith(':') and not ipStr.endswith('::'))):
    return False

  # We can never have more than 7 ':' (1::2:3:4:5:6:7:8 is invalid)
  if ipStr.count(':') > 7:
    return False

  # If we have no concatenation, we need to have 8 fields with 7 ':'.
  if '::' not in ipStr and ipStr.count(':') != 7:
    # We might have an IPv4 mapped address.
    if ipStr.count('.') != 3:
      return False

  ipStr = _explodeShorthandIpString(ipStr)

  # Now that we have that all squared away, let's check that each of the
  # hextets are between 0x0 and 0xFFFF.
  for hextet in ipStr.split(':'):
    if hextet.count('.') == 3:
      # If we have an IPv4 mapped address, the IPv4 portion has to
      # be at the end of the IPv6 portion.
      if not ipStr.split(':')[-1] == hextet:
        return False
      try:
        validateIpv4Address(hextet)
      except ValidationError:
        return False
    else:
      try:
        # a value error here means that we got a bad hextet,
        # something like 0xzzzz
        if int(hextet, 16) < 0x0 or int(hextet, 16) > 0xFFFF:
          return False
      except ValueError:
        return False
  return True


def _explodeShorthandIpString(ipStr):
  """
  Expand a shortened IPv6 address.

  Args:
    ipStr: A string, the IPv6 address.

  Returns:
    A string, the expanded IPv6 address.

  """
  if not _isShorthandIp(ipStr):
    # We've already got a longhand ipStr.
    return ipStr

  newIp = []
  hextet = ipStr.split('::')

  # If there is a ::, we need to expand it with zeroes
  # to get to 8 hextets - unless there is a dot in the last hextet,
  # meaning we're doing v4-mapping
  if '.' in ipStr.split(':')[-1]:
    fillTo = 7
  else:
    fillTo = 8

  if len(hextet) > 1:
    sep = len(hextet[0].split(':')) + len(hextet[1].split(':'))
    newIp = hextet[0].split(':')

    for __ in xrange(fillTo - sep):
      newIp.append('0000')
    newIp += hextet[1].split(':')

  else:
    newIp = ipStr.split(':')

  # Now need to make sure every hextet is 4 lower case characters.
  # If a hextet is < 4 characters, we've got missing leading 0's.
  retIp = []
  for hextet in newIp:
    retIp.append(('0' * (4 - len(hextet)) + hextet).lower())
  return ':'.join(retIp)


def _isShorthandIp(ipStr):
  """Determine if the address is shortened.

  Args:
    ipStr: A string, the IPv6 address.

  Returns:
    A boolean, True if the address is shortened.

  """
  if ipStr.count('::') == 1:
    return True
  if any(len(x) < 4 for x in ipStr.split(':')):
    return True
  return False
