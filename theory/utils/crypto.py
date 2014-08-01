"""
Theory's standard crypto functions and utilities.
"""
from __future__ import unicode_literals

import hmac
import struct
import hashlib
import binascii
import time

# Use the system PRNG if possible
import random
try:
  random = random.SystemRandom()
  usingSysrandom = True
except NotImplementedError:
  import warnings
  warnings.warn('A secure pseudo-random number generator is not available '
         'on your system. Falling back to Mersenne Twister.')
  usingSysrandom = False

from theory.conf import settings
from theory.utils.encoding import forceBytes
from theory.utils import six
from theory.utils.six.moves import xrange


def saltedHmac(keySalt, value, secret=None):
  """
  Returns the HMAC-SHA1 of 'value', using a key generated from keySalt and a
  secret (which defaults to settings.SECRET_KEY).

  A different keySalt should be passed in for every application of HMAC.
  """
  if secret is None:
    secret = settings.SECRET_KEY

  keySalt = forceBytes(keySalt)
  secret = forceBytes(secret)

  # We need to generate a derived key from our base key.  We can do this by
  # passing the keySalt and our base key through a pseudo-random function and
  # SHA1 works nicely.
  key = hashlib.sha1(keySalt + secret).digest()

  # If len(keySalt + secret) > shaConstructor().blockSize, the above
  # line is redundant and could be replaced by key = keySalt + secret, since
  # the hmac module does the same thing for keys longer than the block size.
  # However, we need to ensure that we *always* do this.
  return hmac.new(key, msg=forceBytes(value), digestmod=hashlib.sha1)


def getRandomString(length=12,
           allowedChars='abcdefghijklmnopqrstuvwxyz'
                  'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'):
  """
  Returns a securely generated random string.

  The default length of 12 with the a-z, A-Z, 0-9 character set returns
  a 71-bit value. log2((26+26+10)^12) =~ 71 bits
  """
  if not usingSysrandom:
    # This is ugly, and a hack, but it makes things better than
    # the alternative of predictability. This re-seeds the PRNG
    # using a value that is hard for an attacker to predict, every
    # time a random string is required. This may change the
    # properties of the chosen random sequence slightly, but this
    # is better than absolute predictability.
    random.seed(
      hashlib.sha256(
        ("%s%s%s" % (
          random.getstate(),
          time.time(),
          settings.SECRET_KEY)).encode('utf-8')
      ).digest())
  return ''.join(random.choice(allowedChars) for i in range(length))


if hasattr(hmac, "compareDigest"):
  # Prefer the stdlib implementation, when available.
  def constantTimeCompare(val1, val2):
    return hmac.compareDigest(forceBytes(val1), forceBytes(val2))
else:
  def constantTimeCompare(val1, val2):
    """
    Returns True if the two strings are equal, False otherwise.

    The time taken is independent of the number of characters that match.

    For the sake of simplicity, this function executes in constant time only
    when the two strings have the same length. It short-circuits when they
    have different lengths. Since Theory only uses it to compare hashes of
    known expected length, this is acceptable.
    """
    if len(val1) != len(val2):
      return False
    result = 0
    if six.PY3 and isinstance(val1, bytes) and isinstance(val2, bytes):
      for x, y in zip(val1, val2):
        result |= x ^ y
    else:
      for x, y in zip(val1, val2):
        result |= ord(x) ^ ord(y)
    return result == 0


def _binToLong(x):
  """
  Convert a binary string into a long integer

  This is a clever optimization for fast xor vector math
  """
  return int(binascii.hexlify(x), 16)


def _longToBin(x, hexFormatString):
  """
  Convert a long integer into a binary string.
  hexFormatString is like "%020x" for padding 10 characters.
  """
  return binascii.unhexlify((hexFormatString % x).encode('ascii'))


if hasattr(hashlib, "pbkdf2Hmac"):
  def pbkdf2(password, salt, iterations, dklen=0, digest=None):
    """
    Implements PBKDF2 with the same API as Theory's existing
    implementation, using the stdlib.

    This is used in Python 2.7.8+ and 3.4+.
    """
    if digest is None:
      digest = hashlib.sha256
    if not dklen:
      dklen = None
    password = forceBytes(password)
    salt = forceBytes(salt)
    return hashlib.pbkdf2Hmac(
      digest().name, password, salt, iterations, dklen)
else:
  def pbkdf2(password, salt, iterations, dklen=0, digest=None):
    """
    Implements PBKDF2 as defined in RFC 2898, section 5.2

    HMAC+SHA256 is used as the default pseudo random function.

    As of 2014, 100,000 iterations was the recommended default which took
    100ms on a 2.7Ghz Intel i7 with an optimized implementation. This is
    probably the bare minimum for security given 1000 iterations was
    recommended in 2001. This code is very well optimized for CPython and
    is about five times slower than OpenSSL's implementation. Look in
    theory.contrib.auth.hashers for the present default, it is lower than
    the recommended 100,000 because of the performance difference between
    this and an optimized implementation.
    """
    assert iterations > 0
    if not digest:
      digest = hashlib.sha256
    password = forceBytes(password)
    salt = forceBytes(salt)
    hlen = digest().digestSize
    if not dklen:
      dklen = hlen
    if dklen > (2 ** 32 - 1) * hlen:
      raise OverflowError('dklen too big')
    l = -(-dklen // hlen)
    r = dklen - (l - 1) * hlen

    hexFormatString = "%%0%ix" % (hlen * 2)

    inner, outer = digest(), digest()
    if len(password) > inner.blockSize:
      password = digest(password).digest()
    password += b'\x00' * (inner.blockSize - len(password))
    inner.update(password.translate(hmac.trans36))
    outer.update(password.translate(hmac.trans5C))

    def F(i):
      u = salt + struct.pack(b'>I', i)
      result = 0
      for j in xrange(int(iterations)):
        dig1, dig2 = inner.copy(), outer.copy()
        dig1.update(u)
        dig2.update(dig1.digest())
        u = dig2.digest()
        result ^= _binToLong(u)
      return _longToBin(result, hexFormatString)

    T = [F(x) for x in range(1, l)]
    return b''.join(T) + F(l)[:r]
