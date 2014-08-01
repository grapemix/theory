from __future__ import unicode_literals

import re
import unicodedata
from gzip import GzipFile
from io import BytesIO
import warnings

from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils.encoding import forceText
from theory.utils.functional import allowLazy, SimpleLazyObject
from theory.utils import six
from theory.utils.six.moves import html_entities
from theory.utils.translation import ugettextLazy, ugettext as _, pgettext
from theory.utils.safestring import markSafe

if six.PY2:
  # Import forceUnicode even though this module doesn't use it, because some
  # people rely on it being here.
  from theory.utils.encoding import forceUnicode  # NOQA


# Capitalizes the first letter of a string.
capfirst = lambda x: x and forceText(x)[0].upper() + forceText(x)[1:]
capfirst = allowLazy(capfirst, six.textType)

# Set up regular expressions
reWords = re.compile(r'<.*?>|((?:\w[-\w]*|&.*?;)+)', re.U | re.S)
reChars = re.compile(r'<.*?>|(.)', re.U | re.S)
reTag = re.compile(r'<(/)?([^ ]+?)(?:(\s*/)| .*?)?>', re.S)
reNewlines = re.compile(r'\r\n|\r')  # Used in normalizeNewlines
reCamelCase = re.compile(r'(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))')


def wrap(text, width):
  """
  A word-wrap function that preserves existing line breaks. Expects that
  existing line breaks are posix newlines.

  All white space is preserved except added line breaks consume the space on
  which they break the line.

  Long words are not wrapped, so the output text may have lines longer than
  ``width``.
  """
  text = forceText(text)

  def _generator():
    for line in text.splitlines(True):  # True keeps trailing linebreaks
      maxWidth = min((line.endswith('\n') and width + 1 or width), width)
      while len(line) > maxWidth:
        space = line[:maxWidth + 1].rfind(' ') + 1
        if space == 0:
          space = line.find(' ') + 1
          if space == 0:
            yield line
            line = ''
            break
        yield '%s\n' % line[:space - 1]
        line = line[space:]
        maxWidth = min((line.endswith('\n') and width + 1 or width), width)
      if line:
        yield line
  return ''.join(_generator())
wrap = allowLazy(wrap, six.textType)


class Truncator(SimpleLazyObject):
  """
  An object used to truncate text, either by characters or words.
  """
  def __init__(self, text):
    super(Truncator, self).__init__(lambda: forceText(text))

  def addTruncationText(self, text, truncate=None):
    if truncate is None:
      truncate = pgettext(
        'String to return when truncating text',
        '%(truncatedText)s...')
    truncate = forceText(truncate)
    if '%(truncatedText)s' in truncate:
      return truncate % {'truncatedText': text}
    # The truncation text didn't contain the %(truncatedText)s string
    # replacement argument so just append it to the text.
    if text.endswith(truncate):
      # But don't append the truncation text if the current text already
      # ends in this.
      return text
    return '%s%s' % (text, truncate)

  def chars(self, num, truncate=None, html=False):
    """
    Returns the text truncated to be no longer than the specified number
    of characters.

    Takes an optional argument of what should be used to notify that the
    string has been truncated, defaulting to a translatable string of an
    ellipsis (...).
    """
    length = int(num)
    text = unicodedata.normalize('NFC', self._wrapped)

    # Calculate the length to truncate to (max length - endText length)
    truncateLen = length
    for char in self.addTruncationText('', truncate):
      if not unicodedata.combining(char):
        truncateLen -= 1
        if truncateLen == 0:
          break
    if html:
      return self._truncateHtml(length, truncate, text, truncateLen, False)
    return self._textChars(length, truncate, text, truncateLen)
  chars = allowLazy(chars)

  def _textChars(self, length, truncate, text, truncateLen):
    """
    Truncates a string after a certain number of chars.
    """
    sLen = 0
    endIndex = None
    for i, char in enumerate(text):
      if unicodedata.combining(char):
        # Don't consider combining characters
        # as adding to the string length
        continue
      sLen += 1
      if endIndex is None and sLen > truncateLen:
        endIndex = i
      if sLen > length:
        # Return the truncated string
        return self.addTruncationText(text[:endIndex or 0],
                        truncate)

    # Return the original string since no truncation was necessary
    return text

  def words(self, num, truncate=None, html=False):
    """
    Truncates a string after a certain number of words. Takes an optional
    argument of what should be used to notify that the string has been
    truncated, defaulting to ellipsis (...).
    """
    length = int(num)
    if html:
      return self._truncateHtml(length, truncate, self._wrapped, length, True)
    return self._textWords(length, truncate)
  words = allowLazy(words)

  def _textWords(self, length, truncate):
    """
    Truncates a string after a certain number of words.

    Newlines in the string will be stripped.
    """
    words = self._wrapped.split()
    if len(words) > length:
      words = words[:length]
      return self.addTruncationText(' '.join(words), truncate)
    return ' '.join(words)

  def _truncateHtml(self, length, truncate, text, truncateLen, words):
    """
    Truncates HTML to a certain number of chars (not counting tags and
    comments), or, if words is True, then to a certain number of words.
    Closes opened tags if they were correctly closed in the given HTML.

    Newlines in the HTML are preserved.
    """
    if words and length <= 0:
      return ''

    html4Singlets = (
      'br', 'col', 'link', 'base', 'img',
      'param', 'area', 'hr', 'input'
    )

    # Count non-HTML chars/words and keep note of open tags
    pos = 0
    endTextPos = 0
    currentLen = 0
    openTags = []

    regex = reWords if words else reChars

    while currentLen <= length:
      m = regex.search(text, pos)
      if not m:
        # Checked through whole string
        break
      pos = m.end(0)
      if m.group(1):
        # It's an actual non-HTML word or char
        currentLen += 1
        if currentLen == truncateLen:
          endTextPos = pos
        continue
      # Check for tag
      tag = reTag.match(m.group(0))
      if not tag or currentLen >= truncateLen:
        # Don't worry about non tags or tags after our truncate point
        continue
      closingTag, tagname, selfClosing = tag.groups()
      # Element names are always case-insensitive
      tagname = tagname.lower()
      if selfClosing or tagname in html4Singlets:
        pass
      elif closingTag:
        # Check for match in open tags list
        try:
          i = openTags.index(tagname)
        except ValueError:
          pass
        else:
          # SGML: An end tag closes, back to the matching start tag,
          # all unclosed intervening start tags with omitted end tags
          openTags = openTags[i + 1:]
      else:
        # Add it to the start of the open tags list
        openTags.insert(0, tagname)

    if currentLen <= length:
      return text
    out = text[:endTextPos]
    truncateText = self.addTruncationText('', truncate)
    if truncateText:
      out += truncateText
    # Close any tags still open
    for tag in openTags:
      out += '</%s>' % tag
    # Return string
    return out


def getValidFilename(s):
  """
  Returns the given string converted to a string that can be used for a clean
  filename. Specifically, leading and trailing spaces are removed; other
  spaces are converted to underscores; and anything that is not a unicode
  alphanumeric, dash, underscore, or dot, is removed.
  >>> getValidFilename("john's portrait in 2004.jpg")
  'johnsPortraitIn2004.jpg'
  """
  s = forceText(s).strip().replace(' ', '_')
  return re.sub(r'(?u)[^-\w.]', '', s)
getValidFilename = allowLazy(getValidFilename, six.textType)


def getTextList(list_, lastWord=ugettextLazy('or')):
  """
  >>> getTextList(['a', 'b', 'c', 'd'])
  'a, b, c or d'
  >>> getTextList(['a', 'b', 'c'], 'and')
  'a, b and c'
  >>> getTextList(['a', 'b'], 'and')
  'a and b'
  >>> getTextList(['a'])
  'a'
  >>> getTextList([])
  ''
  """
  if len(list_) == 0:
    return ''
  if len(list_) == 1:
    return forceText(list_[0])
  return '%s %s %s' % (
    # Translators: This string is used as a separator between list elements
    _(', ').join(forceText(i) for i in list_[:-1]),
    forceText(lastWord), forceText(list_[-1]))
getTextList = allowLazy(getTextList, six.textType)


def normalizeNewlines(text):
  """Normalizes CRLF and CR newlines to just LF."""
  text = forceText(text)
  return reNewlines.sub('\n', text)
normalizeNewlines = allowLazy(normalizeNewlines, six.textType)


def phone2numeric(phone):
  """Converts a phone number with letters into its numeric equivalent."""
  char2number = {'a': '2', 'b': '2', 'c': '2', 'd': '3', 'e': '3', 'f': '3',
     'g': '4', 'h': '4', 'i': '4', 'j': '5', 'k': '5', 'l': '5', 'm': '6',
     'n': '6', 'o': '6', 'p': '7', 'q': '7', 'r': '7', 's': '7', 't': '8',
     'u': '8', 'v': '8', 'w': '9', 'x': '9', 'y': '9', 'z': '9'}
  return ''.join(char2number.get(c, c) for c in phone.lower())
phone2numeric = allowLazy(phone2numeric)


# From http://www.xhaus.com/alan/python/httpcomp.html#gzip
# Used with permission.
def compressString(s):
  zbuf = BytesIO()
  zfile = GzipFile(mode='wb', compresslevel=6, fileobj=zbuf)
  zfile.write(s)
  zfile.close()
  return zbuf.getvalue()


class StreamingBuffer(object):
  def __init__(self):
    self.vals = []

  def write(self, val):
    self.vals.append(val)

  def read(self):
    ret = b''.join(self.vals)
    self.vals = []
    return ret

  def flush(self):
    return

  def close(self):
    return


# Like compressString, but for iterators of strings.
def compressSequence(sequence):
  buf = StreamingBuffer()
  zfile = GzipFile(mode='wb', compresslevel=6, fileobj=buf)
  # Output headers...
  yield buf.read()
  for item in sequence:
    zfile.write(item)
    zfile.flush()
    yield buf.read()
  zfile.close()
  yield buf.read()

ustringRe = re.compile("([\u0080-\uffff])")


def javascriptQuote(s, quoteDoubleQuotes=False):
  msg = (
    "theory.utils.text.javascriptQuote() is deprecated. "
    "Use theory.utils.html.escapejs() instead."
  )
  warnings.warn(msg, RemovedInTheory19Warning, stacklevel=2)

  def fix(match):
    return "\\u%04x" % ord(match.group(1))

  if type(s) == bytes:
    s = s.decode('utf-8')
  elif type(s) != six.textType:
    raise TypeError(s)
  s = s.replace('\\', '\\\\')
  s = s.replace('\r', '\\r')
  s = s.replace('\n', '\\n')
  s = s.replace('\t', '\\t')
  s = s.replace("'", "\\'")
  s = s.replace('</', '<\\/')
  if quoteDoubleQuotes:
    s = s.replace('"', '&quot;')
  return ustringRe.sub(fix, s)
javascriptQuote = allowLazy(javascriptQuote, six.textType)

# Expression to match someToken and someToken="with spaces" (and similarly
# for single-quoted strings).
smartSplitRe = re.compile(r"""
  ((?:
    [^\s'"]*
    (?:
      (?:"(?:[^"\\]|\\.)*" | '(?:[^'\\]|\\.)*')
      [^\s'"]*
    )+
  ) | \S+)
""", re.VERBOSE)


def smartSplit(text):
  r"""
  Generator that splits a string by spaces, leaving quoted phrases together.
  Supports both single and double quotes, and supports escaping quotes with
  backslashes. In the output, strings will keep their initial and trailing
  quote marks and escaped quotes will remain escaped (the results can then
  be further processed with unescapeStringLiteral()).

  >>> list(smartSplit(r'This is "a person\'s" test.'))
  ['This', 'is', '"a person\\\'s"', 'test.']
  >>> list(smartSplit(r"Another 'person\'s' test."))
  ['Another', "'person\\'s'", 'test.']
  >>> list(smartSplit(r'A "\"funky\" style" test.'))
  ['A', '"\\"funky\\" style"', 'test.']
  """
  text = forceText(text)
  for bit in smartSplitRe.finditer(text):
    yield bit.group(0)


def _replaceEntity(match):
  text = match.group(1)
  if text[0] == '#':
    text = text[1:]
    try:
      if text[0] in 'xX':
        c = int(text[1:], 16)
      else:
        c = int(text)
      return six.unichr(c)
    except ValueError:
      return match.group(0)
  else:
    try:
      return six.unichr(html_entities.name2codepoint[text])
    except (ValueError, KeyError):
      return match.group(0)

_entityRe = re.compile(r"&(#?[xX]?(?:[0-9a-fA-F]+|\w{1,8}));")


def unescapeEntities(text):
  return _entityRe.sub(_replaceEntity, text)
unescapeEntities = allowLazy(unescapeEntities, six.textType)


def unescapeStringLiteral(s):
  r"""
  Convert quoted string literals to unquoted strings with escaped quotes and
  backslashes unquoted::

    >>> unescapeStringLiteral('"abc"')
    'abc'
    >>> unescapeStringLiteral("'abc'")
    'abc'
    >>> unescapeStringLiteral('"a \"bc\""')
    'a "bc"'
    >>> unescapeStringLiteral("'\'ab\' c'")
    "'ab' c"
  """
  if s[0] not in "\"'" or s[-1] != s[0]:
    raise ValueError("Not a string literal: %r" % s)
  quote = s[0]
  return s[1:-1].replace(r'\%s' % quote, quote).replace(r'\\', '\\')
unescapeStringLiteral = allowLazy(unescapeStringLiteral)


def slugify(value):
  """
  Converts to lowercase, removes non-word characters (alphanumerics and
  underscores) and converts spaces to hyphens. Also strips leading and
  trailing whitespace.
  """
  value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
  value = re.sub('[^\w\s-]', '', value).strip().lower()
  return markSafe(re.sub('[-\s]+', '-', value))
slugify = allowLazy(slugify, six.textType)


def camelCaseToSpaces(value):
  """
  Splits CamelCase and converts to lower case. Also strips leading and
  trailing whitespace.
  """
  return reCamelCase.sub(r' \1', value).strip().lower()
