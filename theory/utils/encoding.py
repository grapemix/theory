# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
#from __future__ import unicodeLiterals

import codecs
import datetime
from decimal import Decimal
import locale
import warnings

##### Theory lib #####
from theory.utils.functional import Promise
from theory.utils import six
from theory.utils.six.moves.urllib.parse import quote

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class TheoryUnicodeDecodeError(UnicodeDecodeError):
  def __init__(self, obj, *args):
    self.obj = obj
    UnicodeDecodeError.__init__(self, *args)

  def __str__(self):
    original = UnicodeDecodeError.__str__(self)
    return '%s. You passed in %r (%s)' % (original, self.obj,
        type(self.obj))

class StrAndUnicode(object):
  """
  A class that derives __str__ from __unicode__.

  On Python 2, __str__ returns the output of __unicode__ encoded as a UTF-8
  bytestring. On Python 3, __str__ returns the output of __unicode__.

  Useful as a mix-in. If you support Python 2 and 3 with a single code base,
  you can inherit this mix-in and just define __unicode__.
  """
  def __init__(self, *args, **kwargs):
    warnings.warn("StrAndUnicode is deprecated. Define a __str__ method "
           "and apply the @python2_unicodeCompatible decorator "
           "instead.", DeprecationWarning, stacklevel=2)
    super(StrAndUnicode, self).__init__(*args, **kwargs)

  if six.PY3:
    def __str__(self):
      return self.__unicode__()
  else:
    def __str__(self):
      return self.__unicode__().encode('utf-8')

def python2UnicodeCompatible(klass):
  """
  A decorator that defines __unicode__ and __str__ methods under Python 2.
  Under Python 3 it does nothing.

  To support Python 2 and 3 with a single code base, define a __str__ method
  returning text and apply this decorator to the class.
  """
  if six.PY2:
    if '__str__' not in klass.__dict__:
      raise ValueError("@python2UnicodeCompatible cannot be applied "
               "to %s because it doesn't define __str__()." %
               klass.__name__)
    klass.__unicode__ = klass.__str__
    klass.__str__ = lambda self: self.__unicode__().encode('utf-8')
  return klass

def smartText(s, encoding='utf-8', stringsOnly=False, errors='strict'):
  """
  Returns a text object representing 's' -- unicode on Python 2 and str on
  Python 3. Treats bytestrings using the 'encoding' codec.

  If stringsOnly is True, don't convert (some) non-string-like objects.
  """
  if isinstance(s, Promise):
    # The input is the result of a gettextLazy() call.
    return s
  return forceText(s, encoding, stringsOnly, errors)

def isProtectedType(obj):
  """Determine if the object instance is of a protected type.

  Objects of protected types are preserved as-is when passed to
  forceText(stringsOnly=True).
  """
  return isinstance(obj, six.integerTypes + (type(None), float, Decimal,
    datetime.datetime, datetime.date, datetime.time))

def forceText(s, encoding='utf-8', stringsOnly=False, errors='strict'):
  """
  Similar to smartText, except that lazy instances are resolved to
  strings, rather than kept as lazy objects.

  If stringsOnly is True, don't convert (some) non-string-like objects.
  """
  # Handle the common case first, saves 30-40% when s is an instance of
  # six.text_type. This function gets called often in that setting.
  if isinstance(s, six.text_type):
    return s
  if stringsOnly and isProtectedType(s):
    return s
  try:
    if not isinstance(s, six.string_types):
      if hasattr(s, '__unicode__'):
        s = s.__unicode__()
      else:
        if six.PY3:
          if isinstance(s, bytes):
            s = six.text_type(s, encoding, errors)
          else:
            s = six.text_type(s)
        else:
          s = six.text_type(bytes(s), encoding, errors)
    else:
      # Note: We use .decode() here, instead of six.text_type(s, encoding,
      # errors), so that if s is a SafeBytes, it ends up being a
      # SafeText at the end.
      s = s.decode(encoding, errors)
  except UnicodeDecodeError as e:
    if not isinstance(s, Exception):
      raise TheoryUnicodeDecodeError(s, *e.args)
    else:
      # If we get to here, the caller has passed in an Exception
      # subclass populated with non-ASCII bytestring data without a
      # working unicode method. Try to handle this without raising a
      # further exception by individually forcing the exception args
      # to unicode.
      s = ' '.join([forceText(arg, encoding, stringsOnly,
          errors) for arg in s])
  return s

def smartBytes(s, encoding='utf-8', stringsOnly=False, errors='strict'):
  """
  Returns a bytestring version of 's', encoded as specified in 'encoding'.

  If stringsOnly is True, don't convert (some) non-string-like objects.
  """
  if isinstance(s, Promise):
    # The input is the result of a gettextLazy() call.
    return s
  return forceBytes(s, encoding, stringsOnly, errors)


def forceBytes(s, encoding='utf-8', stringsOnly=False, errors='strict'):
  """
  Similar to smartBytes, except that lazy instances are resolved to
  strings, rather than kept as lazy objects.

  If stringsOnly is True, don't convert (some) non-string-like objects.
  """
  if isinstance(s, six.memoryview):
    s = bytes(s)
  if isinstance(s, bytes):
    if encoding == 'utf-8':
      return s
    else:
      return s.decode('utf-8', errors).encode(encoding, errors)
  if stringsOnly and (s is None or isinstance(s, int)):
    return s
  if isinstance(s, Promise):
    return six.text_type(s).encode(encoding, errors)
  if not isinstance(s, six.string_types):
    try:
      if six.PY3:
        return six.text_type(s).encode(encoding)
      else:
        return bytes(s)
    except UnicodeEncodeError:
      if isinstance(s, Exception):
        # An Exception subclass containing non-ASCII data that doesn't
        # know how to print itself properly. We shouldn't raise a
        # further exception.
        return b' '.join([forceBytes(arg, encoding, stringsOnly,
            errors) for arg in s])
      return six.text_type(s).encode(encoding, errors)
  else:
    return s.encode(encoding, errors)

if six.PY3:
  smartStr = smartText
  forceStr = forceText
else:
  smartStr = smartBytes
  forceStr = forceBytes
  # backwards compatibility for Python 2
  smartUnicode = smartText
  forceUnicode = forceText

smartStr.__doc__ = """\
Apply smartText in Python 3 and smartBytes in Python 2.

This is suitable for writing to sys.stdout (for instance).
"""

forceStr.__doc__ = """\
Apply forceText in Python 3 and forceBytes in Python 2.
"""

def iriToUri(iri):
  """
  Convert an Internationalized Resource Identifier (IRI) portion to a URI
  portion that is suitable for inclusion in a URL.

  This is the algorithm from section 3.1 of RFC 3987.  However, since we are
  assuming input is either UTF-8 or unicode already, we can simplify things a
  little from the full method.

  Returns an ASCII string containing the encoded result.
  """
  # The list of safe characters here is constructed from the "reserved" and
  # "unreserved" characters specified in sections 2.2 and 2.3 of RFC 3986:
  #     reserved    = gen-delims / sub-delims
  #     gen-delims  = ":" / "/" / "?" / "#" / "[" / "]" / "@"
  #     sub-delims  = "!" / "$" / "&" / "'" / "(" / ")"
  #                   / "*" / "+" / "," / ";" / "="
  #     unreserved  = ALPHA / DIGIT / "-" / "." / "_" / "~"
  # Of the unreserved characters, urllib.quote already considers all but
  # the ~ safe.
  # The % character is also added to the list of safe characters here, as the
  # end of section 3.1 of RFC 3987 specifically mentions that % must not be
  # converted.
  if iri is None:
    return iri
  return quote(forceBytes(iri), safe=b"/#%[]=:;$&()+,!?*@'~")

def filepathToUri(path):
  """Convert a file system path to a URI portion that is suitable for
  inclusion in a URL.

  We are assuming input is either UTF-8 or unicode already.

  This method will encode certain chars that would normally be recognized as
  special chars for URIs.  Note that this method does not encode the '
  character, as it is a valid character within URIs.  See
  encodeURIComponent() JavaScript function for more details.

  Returns an ASCII string containing the encoded result.
  """
  if path is None:
    return path
  # I know about `os.sep` and `os.altsep` but I want to leave
  # some flexibility for hardcoding separators.
  return quote(forceBytes(path).replace(b"\\", b"/"), safe=b"/~!*()'")

def getSystemEncoding():
  """
  The encoding of the default system locale but falls back to the given
  fallback encoding if the encoding is unsupported by python or could
  not be determined.  See tickets #10335 and #5846
  """
  try:
    encoding = locale.getdefaultlocale()[1] or 'ascii'
    codecs.lookup(encoding)
  except Exception:
    encoding = 'ascii'
  return encoding

DEFAULT_LOCALE_ENCODING = getSystemEncoding()
