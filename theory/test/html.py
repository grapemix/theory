"""
Comparing two html documents.
"""

from __future__ import unicodeLiterals

import re
from theory.utils.encoding import forceText
from theory.utils.htmlParser import HTMLParser, HTMLParseError
from theory.utils import six
from theory.utils.encoding import python2_unicodeCompatible


WHITESPACE = re.compile('\s+')


def normalizeWhitespace(string):
  return WHITESPACE.sub(' ', string)


@python2_unicodeCompatible
class Element(object):
  def __init__(self, name, attributes):
    self.name = name
    self.attributes = sorted(attributes)
    self.children = []

  def append(self, element):
    if isinstance(element, six.stringTypes):
      element = forceText(element)
      element = normalizeWhitespace(element)
      if self.children:
        if isinstance(self.children[-1], six.stringTypes):
          self.children[-1] += element
          self.children[-1] = normalizeWhitespace(self.children[-1])
          return
    elif self.children:
      # removing last children if it is only whitespace
      # this can result in incorrect dom representations since
      # whitespace between inline tags like <span> is significant
      if isinstance(self.children[-1], six.stringTypes):
        if self.children[-1].isspace():
          self.children.pop()
    if element:
      self.children.append(element)

  def finalize(self):
    def rstripLastElement(children):
      if children:
        if isinstance(children[-1], six.stringTypes):
          children[-1] = children[-1].rstrip()
          if not children[-1]:
            children.pop()
            children = rstripLastElement(children)
      return children

    rstripLastElement(self.children)
    for i, child in enumerate(self.children):
      if isinstance(child, six.stringTypes):
        self.children[i] = child.strip()
      elif hasattr(child, 'finalize'):
        child.finalize()

  def __eq__(self, element):
    if not hasattr(element, 'name'):
      return False
    if hasattr(element, 'name') and self.name != element.name:
      return False
    if len(self.attributes) != len(element.attributes):
      return False
    if self.attributes != element.attributes:
      # attributes without a value is same as attribute with value that
      # equals the attributes name:
      # <input checked> == <input checked="checked">
      for i in range(len(self.attributes)):
        attr, value = self.attributes[i]
        otherAttr, otherValue = element.attributes[i]
        if value is None:
          value = attr
        if otherValue is None:
          otherValue = otherAttr
        if attr != otherAttr or value != otherValue:
          return False
    if self.children != element.children:
      return False
    return True

  def __hash__(self):
    return hash((self.name,) + tuple(a for a in self.attributes))

  def __ne__(self, element):
    return not self.__eq__(element)

  def _count(self, element, count=True):
    if not isinstance(element, six.stringTypes):
      if self == element:
        return 1
    i = 0
    for child in self.children:
      # child is text content and element is also text content, then
      # make a simple "text" in "text"
      if isinstance(child, six.stringTypes):
        if isinstance(element, six.stringTypes):
          if count:
            i += child.count(element)
          elif element in child:
            return 1
      else:
        i += child._count(element, count=count)
        if not count and i:
          return i
    return i

  def __contains__(self, element):
    return self._count(element, count=False) > 0

  def count(self, element):
    return self._count(element, count=True)

  def __getitem__(self, key):
    return self.children[key]

  def __str__(self):
    output = '<%s' % self.name
    for key, value in self.attributes:
      if value:
        output += ' %s="%s"' % (key, value)
      else:
        output += ' %s' % key
    if self.children:
      output += '>\n'
      output += ''.join(six.textType(c) for c in self.children)
      output += '\n</%s>' % self.name
    else:
      output += ' />'
    return output

  def __repr__(self):
    return six.textType(self)


@python2_unicodeCompatible
class RootElement(Element):
  def __init__(self):
    super(RootElement, self).__init__(None, ())

  def __str__(self):
    return ''.join(six.textType(c) for c in self.children)


class Parser(HTMLParser):
  SELF_CLOSING_TAGS = ('br', 'hr', 'input', 'img', 'meta', 'spacer',
    'link', 'frame', 'base', 'col')

  def __init__(self):
    HTMLParser.__init__(self)
    self.root = RootElement()
    self.openTags = []
    self.elementPositions = {}

  def error(self, msg):
    raise HTMLParseError(msg, self.getpos())

  def formatPosition(self, position=None, element=None):
    if not position and element:
      position = self.elementPositions[element]
    if position is None:
      position = self.getpos()
    if hasattr(position, 'lineno'):
      position = position.lineno, position.offset
    return 'Line %d, Column %d' % position

  @property
  def current(self):
    if self.openTags:
      return self.openTags[-1]
    else:
      return self.root

  def handleStartendtag(self, tag, attrs):
    self.handleStarttag(tag, attrs)
    if tag not in self.SELF_CLOSING_TAGS:
      self.handleEndtag(tag)

  def handleStarttag(self, tag, attrs):
    # Special case handling of 'class' attribute, so that comparisons of DOM
    # instances are not sensitive to ordering of classes.
    attrs = [
      (name, " ".join(sorted(value.split(" "))))
      if name == "class"
      else (name, value)
      for name, value in attrs
    ]
    element = Element(tag, attrs)
    self.current.append(element)
    if tag not in self.SELF_CLOSING_TAGS:
      self.openTags.append(element)
    self.elementPositions[element] = self.getpos()

  def handleEndtag(self, tag):
    if not self.openTags:
      self.error("Unexpected end tag `%s` (%s)" % (
        tag, self.formatPosition()))
    element = self.openTags.pop()
    while element.name != tag:
      if not self.openTags:
        self.error("Unexpected end tag `%s` (%s)" % (
          tag, self.formatPosition()))
      element = self.openTags.pop()

  def handleData(self, data):
    self.current.append(data)

  def handleCharref(self, name):
    self.current.append('&%s;' % name)

  def handleEntityref(self, name):
    self.current.append('&%s;' % name)


def parseHtml(html):
  """
  Takes a string that contains *valid* HTML and turns it into a Python object
  structure that can be easily compared against other HTML on semantic
  equivalence. Syntactical differences like which quotation is used on
  arguments will be ignored.

  """
  parser = Parser()
  parser.feed(html)
  parser.close()
  document = parser.root
  document.finalize()
  # Removing ROOT element if it's not necessary
  if len(document.children) == 1:
    if not isinstance(document.children[0], six.stringTypes):
      document = document.children[0]
  return document
