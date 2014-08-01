# -*- coding: utf-8 -*-
#!/usr/bin/env python
"""HTML utilities suitable for global use."""

from __future__ import unicode_literals

import re
import sys

from theory.utils.encoding import forceText, forceStr
from theory.utils.functional import allowLazy
from theory.utils.http import RFC3986_GENDELIMS, RFC3986_SUBDELIMS
from theory.utils.safestring import SafeData, markSafe
from theory.utils import six
from theory.utils.six.moves.urllib.parse import quote, unquote, urlsplit, urlunsplit
from theory.utils.text import normalizeNewlines

# Configuration for urlize() function.
TRAILING_PUNCTUATION = ['.', ',', ':', ';', '.)', '"', '\'']
WRAPPING_PUNCTUATION = [('(', ')'), ('<', '>'), ('[', ']'), ('&lt;', '&gt;'), ('"', '"'), ('\'', '\'')]

# List of possible strings used for bullets in bulleted lists.
DOTS = ['&middot;', '*', '\u2022', '&#149;', '&bull;', '&#8226;']

unencodedAmpersandsRe = re.compile(r'&(?!(\w+|#\d+);)')
wordSplitRe = re.compile(r'(\s+)')
simpleUrlRe = re.compile(r'^https?://\[?\w', re.IGNORECASE)
simpleUrl2_re = re.compile(r'^www\.|^(?!http)\w[^@]+\.(com|edu|gov|int|mil|net|org)($|/.*)$', re.IGNORECASE)
simpleEmailRe = re.compile(r'^\S+@\S+\.\S+$')
linkTargetAttributeRe = re.compile(r'(<a [^>]*?)target=[^\s>]+')
htmlGunkRe = re.compile(r'(?:<br clear="all">|<i><\/i>|<b><\/b>|<em><\/em>|<strong><\/strong>|<\/?smallcaps>|<\/?uppercase>)', re.IGNORECASE)
hardCodedBulletsRe = re.compile(r'((?:<p>(?:%s).*?[a-zA-Z].*?</p>\s*)+)' % '|'.join(re.escape(x) for x in DOTS), re.DOTALL)
trailingEmptyContentRe = re.compile(r'(?:<p>(?:&nbsp;|\s|<br \/>)*?</p>\s*)+\Z')


def escape(text):
  """
  Returns the given text with ampersands, quotes and angle brackets encoded for use in HTML.
  """
  return markSafe(forceText(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;'))
escape = allowLazy(escape, six.textType)

_jsEscapes = {
  ord('\\'): '\\u005C',
  ord('\''): '\\u0027',
  ord('"'): '\\u0022',
  ord('>'): '\\u003E',
  ord('<'): '\\u003C',
  ord('&'): '\\u0026',
  ord('='): '\\u003D',
  ord('-'): '\\u002D',
  ord(';'): '\\u003B',
  ord('\u2028'): '\\u2028',
  ord('\u2029'): '\\u2029'
}

# Escape every ASCII character with a value less than 32.
_jsEscapes.update((ord('%c' % z), '\\u%04X' % z) for z in range(32))


def escapejs(value):
  """Hex encodes characters for use in JavaScript strings."""
  return markSafe(forceText(value).translate(_jsEscapes))
escapejs = allowLazy(escapejs, six.textType)


def conditionalEscape(text):
  """
  Similar to escape(), except that it doesn't operate on pre-escaped strings.
  """
  if hasattr(text, '__html__'):
    return text.__html__()
  else:
    return escape(text)


def formatHtml(formatString, *args, **kwargs):
  """
  Similar to str.format, but passes all arguments through conditionalEscape,
  and calls 'markSafe' on the result. This function should be used instead
  of str.format or % interpolation to build up small HTML fragments.
  """
  argsSafe = map(conditionalEscape, args)
  kwargsSafe = dict((k, conditionalEscape(v)) for (k, v) in six.iteritems(kwargs))
  return markSafe(formatString.format(*argsSafe, **kwargsSafe))


def formatHtmlJoin(sep, formatString, argsGenerator):
  """
  A wrapper of formatHtml, for the common case of a group of arguments that
  need to be formatted using the same format string, and then joined using
  'sep'. 'sep' is also passed through conditionalEscape.

  'argsGenerator' should be an iterator that returns the sequence of 'args'
  that will be passed to formatHtml.

  Example:

   formatHtmlJoin('\n', "<li>{0} {1}</li>", ((u.firstName, u.lastName)
                         for u in users))

  """
  return markSafe(conditionalEscape(sep).join(
    formatHtml(formatString, *tuple(args))
    for args in argsGenerator))


def linebreaks(value, autoescape=False):
  """Converts newlines into <p> and <br />s."""
  value = normalizeNewlines(value)
  paras = re.split('\n{2,}', value)
  if autoescape:
    paras = ['<p>%s</p>' % escape(p).replace('\n', '<br />') for p in paras]
  else:
    paras = ['<p>%s</p>' % p.replace('\n', '<br />') for p in paras]
  return '\n\n'.join(paras)
linebreaks = allowLazy(linebreaks, six.textType)

def _stripOnce(value):
  """
  Internal tag stripping utility used by stripTags.
  """
  s = MLStripper()
  try:
    s.feed(value)
  except HTMLParseError:
    return value
  s.close()

def stripTags(value):
  """Returns the given HTML with all tags stripped."""
  # Note: in typical case this loop executes _stripOnce once. Loop condition
  # is redundant, but helps to reduce number of executions of _stripOnce.
  while '<' in value and '>' in value:
    newValue = _stripOnce(value)
    if newValue == value:
      # _stripOnce was not able to detect more tags
      break
    value = newValue
  return value
stripTags = allowLazy(stripTags)


def removeTags(html, tags):
  """Returns the given HTML with given tags removed."""
  tags = [re.escape(tag) for tag in tags.split()]
  tagsRe = '(%s)' % '|'.join(tags)
  starttagRe = re.compile(r'<%s(/?>|(\s+[^>]*>))' % tagsRe, re.U)
  endtagRe = re.compile('</%s>' % tagsRe)
  html = starttagRe.sub('', html)
  html = endtagRe.sub('', html)
  return html
removeTags = allowLazy(removeTags, six.textType)


def stripSpacesBetweenTags(value):
  """Returns the given HTML with spaces between tags removed."""
  return re.sub(r'>\s+<', '><', forceText(value))
stripSpacesBetweenTags = allowLazy(stripSpacesBetweenTags, six.textType)


def stripEntities(value):
  """Returns the given HTML with all entities (&something;) stripped."""
  return re.sub(r'&(?:\w+|#\d+);', '', forceText(value))
stripEntities = allowLazy(stripEntities, six.textType)


def smartUrlquote(url):
  "Quotes a URL if it isn't already quoted."
  # Handle IDN before quoting.
  try:
    scheme, netloc, path, query, fragment = urlsplit(url)
    try:
      netloc = netloc.encode('idna').decode('ascii')  # IDN -> ACE
    except UnicodeError:  # invalid domain part
      pass
    else:
      url = urlunsplit((scheme, netloc, path, query, fragment))
  except ValueError:
    # invalid IPv6 URL (normally square brackets in hostname part).
    pass

  url = unquote(forceStr(url))
  # See http://bugs.python.org/issue2637
  url = quote(url, safe=RFC3986_SUBDELIMS + RFC3986_GENDELIMS + str('~'))

  return forceText(url)


def urlize(text, trimUrlLimit=None, nofollow=False, autoescape=False):
  """
  Converts any URLs in text into clickable links.

  Works on http://, https://, www. links, and also on links ending in one of
  the original seven gTLDs (.com, .edu, .gov, .int, .mil, .net, and .org).
  Links can have trailing punctuation (periods, commas, close-parens) and
  leading punctuation (opening parens) and it'll still do the right thing.

  If trimUrlLimit is not None, the URLs in the link text longer than this
  limit will be truncated to trimUrlLimit-3 characters and appended with
  an ellipsis.

  If nofollow is True, the links will get a rel="nofollow" attribute.

  If autoescape is True, the link text and URLs will be autoescaped.
  """
  def trimUrl(x, limit=trimUrlLimit):
    if limit is None or len(x) <= limit:
      return x
    return '%s...' % x[:max(0, limit - 3)]
  safeInput = isinstance(text, SafeData)
  words = wordSplitRe.split(forceText(text))
  for i, word in enumerate(words):
    if '.' in word or '@' in word or ':' in word:
      # Deal with punctuation.
      lead, middle, trail = '', word, ''
      for punctuation in TRAILING_PUNCTUATION:
        if middle.endswith(punctuation):
          middle = middle[:-len(punctuation)]
          trail = punctuation + trail
      for opening, closing in WRAPPING_PUNCTUATION:
        if middle.startswith(opening):
          middle = middle[len(opening):]
          lead = lead + opening
        # Keep parentheses at the end only if they're balanced.
        if (middle.endswith(closing)
            and middle.count(closing) == middle.count(opening) + 1):
          middle = middle[:-len(closing)]
          trail = closing + trail

      # Make URL we want to point to.
      url = None
      nofollowAttr = ' rel="nofollow"' if nofollow else ''
      if simpleUrlRe.match(middle):
        url = smartUrlquote(middle)
      elif simpleUrl2_re.match(middle):
        url = smartUrlquote('http://%s' % middle)
      elif ':' not in middle and simpleEmailRe.match(middle):
        local, domain = middle.rsplit('@', 1)
        try:
          domain = domain.encode('idna').decode('ascii')
        except UnicodeError:
          continue
        url = 'mailto:%s@%s' % (local, domain)
        nofollowAttr = ''

      # Make link.
      if url:
        trimmed = trimUrl(middle)
        if autoescape and not safeInput:
          lead, trail = escape(lead), escape(trail)
          url, trimmed = escape(url), escape(trimmed)
        middle = '<a href="%s"%s>%s</a>' % (url, nofollowAttr, trimmed)
        words[i] = markSafe('%s%s%s' % (lead, middle, trail))
      else:
        if safeInput:
          words[i] = markSafe(word)
        elif autoescape:
          words[i] = escape(word)
    elif safeInput:
      words[i] = markSafe(word)
    elif autoescape:
      words[i] = escape(word)
  return ''.join(words)
urlize = allowLazy(urlize, six.textType)


def avoidWrapping(value):
  """
  Avoid text wrapping in the middle of a phrase by adding non-breaking
  spaces where there previously were normal spaces.
  """
  return value.replace(" ", "\xa0")
