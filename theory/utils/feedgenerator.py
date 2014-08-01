"""
Syndication feed generation library -- used for generating RSS, etc.

Sample usage:

>>> from theory.utils import feedgenerator
>>> feed = feedgenerator.Rss201rev2Feed(
...     title="Poynter E-Media Tidbits",
...     link="http://www.poynter.org/column.asp?id=31",
...     description="A group Weblog by the sharpest minds in online media/journalism/publishing.",
...     language="en",
... )
>>> feed.addItem(
...     title="Hello",
...     link="http://www.holovaty.com/test/",
...     description="Testing."
... )
>>> with open('test.rss', 'w') as fp:
...     feed.write(fp, 'utf-8')

For definitions of the different versions of RSS, see:
http://web.archive.org/web/20110718035220/http://diveintomark.org/archives/2004/02/04/incompatible-rss
"""
from __future__ import unicode_literals

import datetime
from theory.utils.xmlutils import SimplerXMLGenerator
from theory.utils.encoding import forceText, iriToUri
from theory.utils import datetimeSafe
from theory.utils import six
from theory.utils.six import StringIO
from theory.utils.six.moves.urllib.parse import urlparse
from theory.utils.timezone import isAware


def rfc2822Date(date):
  # We can't use strftime() because it produces locale-dependent results, so
  # we have to map english month and day names manually
  months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',)
  days = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
  # Support datetime objects older than 1900
  date = datetimeSafe.newDatetime(date)
  # We do this ourselves to be timezone aware, email.Utils is not tz aware.
  dow = days[date.weekday()]
  month = months[date.month - 1]
  timeStr = date.strftime('%s, %%d %s %%Y %%H:%%M:%%S ' % (dow, month))
  if six.PY2:             # strftime returns a byte string in Python 2
    timeStr = timeStr.decode('utf-8')
  if isAware(date):
    offset = date.tzinfo.utcoffset(date)
    timezone = (offset.days * 24 * 60) + (offset.seconds // 60)
    hour, minute = divmod(timezone, 60)
    return timeStr + '%+03d%02d' % (hour, minute)
  else:
    return timeStr + '-0000'


def rfc3339Date(date):
  # Support datetime objects older than 1900
  date = datetimeSafe.newDatetime(date)
  timeStr = date.strftime('%Y-%m-%dT%H:%M:%S')
  if six.PY2:             # strftime returns a byte string in Python 2
    timeStr = timeStr.decode('utf-8')
  if isAware(date):
    offset = date.tzinfo.utcoffset(date)
    timezone = (offset.days * 24 * 60) + (offset.seconds // 60)
    hour, minute = divmod(timezone, 60)
    return timeStr + '%+03d:%02d' % (hour, minute)
  else:
    return timeStr + 'Z'


def getTagUri(url, date):
  """
  Creates a TagURI.

  See http://web.archive.org/web/20110514113830/http://diveintomark.org/archives/2004/05/28/howto-atom-id
  """
  bits = urlparse(url)
  d = ''
  if date is not None:
    d = ',%s' % datetimeSafe.newDatetime(date).strftime('%Y-%m-%d')
  return 'tag:%s%s:%s/%s' % (bits.hostname, d, bits.path, bits.fragment)


class SyndicationFeed(object):
  "Base class for all syndication feeds. Subclasses should provide write()"
  def __init__(self, title, link, description, language=None, authorEmail=None,
      authorName=None, authorLink=None, subtitle=None, categories=None,
      feedUrl=None, feedCopyright=None, feedGuid=None, ttl=None, **kwargs):
    toUnicode = lambda s: forceText(s, stringsOnly=True)
    if categories:
      categories = [forceText(c) for c in categories]
    if ttl is not None:
      # Force ints to unicode
      ttl = forceText(ttl)
    self.feed = {
      'title': toUnicode(title),
      'link': iriToUri(link),
      'description': toUnicode(description),
      'language': toUnicode(language),
      'authorEmail': toUnicode(authorEmail),
      'authorName': toUnicode(authorName),
      'authorLink': iriToUri(authorLink),
      'subtitle': toUnicode(subtitle),
      'categories': categories or (),
      'feedUrl': iriToUri(feedUrl),
      'feedCopyright': toUnicode(feedCopyright),
      'id': feedGuid or link,
      'ttl': ttl,
    }
    self.feed.update(kwargs)
    self.items = []

  def addItem(self, title, link, description, authorEmail=None,
      authorName=None, authorLink=None, pubdate=None, comments=None,
      uniqueId=None, uniqueIdIsPermalink=None, enclosure=None,
      categories=(), itemCopyright=None, ttl=None, updateddate=None, **kwargs):
    """
    Adds an item to the feed. All args are expected to be Python Unicode
    objects except pubdate and updateddate, which are datetime.datetime
    objects, and enclosure, which is an instance of the Enclosure class.
    """
    toUnicode = lambda s: forceText(s, stringsOnly=True)
    if categories:
      categories = [toUnicode(c) for c in categories]
    if ttl is not None:
      # Force ints to unicode
      ttl = forceText(ttl)
    item = {
      'title': toUnicode(title),
      'link': iriToUri(link),
      'description': toUnicode(description),
      'authorEmail': toUnicode(authorEmail),
      'authorName': toUnicode(authorName),
      'authorLink': iriToUri(authorLink),
      'pubdate': pubdate,
      'updateddate': updateddate,
      'comments': toUnicode(comments),
      'uniqueId': toUnicode(uniqueId),
      'uniqueIdIsPermalink': uniqueIdIsPermalink,
      'enclosure': enclosure,
      'categories': categories or (),
      'itemCopyright': toUnicode(itemCopyright),
      'ttl': ttl,
    }
    item.update(kwargs)
    self.items.append(item)

  def numItems(self):
    return len(self.items)

  def rootAttributes(self):
    """
    Return extra attributes to place on the root (i.e. feed/channel) element.
    Called from write().
    """
    return {}

  def addRootElements(self, handler):
    """
    Add elements in the root (i.e. feed/channel) element. Called
    from write().
    """
    pass

  def itemAttributes(self, item):
    """
    Return extra attributes to place on each item (i.e. item/entry) element.
    """
    return {}

  def addItemElements(self, handler, item):
    """
    Add elements on each item (i.e. item/entry) element.
    """
    pass

  def write(self, outfile, encoding):
    """
    Outputs the feed in the given encoding to outfile, which is a file-like
    object. Subclasses should override this.
    """
    raise NotImplementedError('subclasses of SyndicationFeed must provide a write() method')

  def writeString(self, encoding):
    """
    Returns the feed in the given encoding as a string.
    """
    s = StringIO()
    self.write(s, encoding)
    return s.getvalue()

  def latestPostDate(self):
    """
    Returns the latest item's pubdate or updateddate. If no items
    have either of these attributes this returns the current date/time.
    """
    latestDate = None
    dateKeys = ('updateddate', 'pubdate')

    for item in self.items:
      for dateKey in dateKeys:
        itemDate = item.get(dateKey)
        if itemDate:
          if latestDate is None or itemDate > latestDate:
            latestDate = itemDate

    return latestDate or datetime.datetime.now()


class Enclosure(object):
  "Represents an RSS enclosure"
  def __init__(self, url, length, mimeType):
    "All args are expected to be Python Unicode objects"
    self.length, self.mimeType = length, mimeType
    self.url = iriToUri(url)


class RssFeed(SyndicationFeed):
  mimeType = 'application/rss+xml; charset=utf-8'

  def write(self, outfile, encoding):
    handler = SimplerXMLGenerator(outfile, encoding)
    handler.startDocument()
    handler.startElement("rss", self.rssAttributes())
    handler.startElement("channel", self.rootAttributes())
    self.addRootElements(handler)
    self.writeItems(handler)
    self.endChannelElement(handler)
    handler.endElement("rss")

  def rssAttributes(self):
    return {"version": self._version,
        "xmlns:atom": "http://www.w3.org/2005/Atom"}

  def writeItems(self, handler):
    for item in self.items:
      handler.startElement('item', self.itemAttributes(item))
      self.addItemElements(handler, item)
      handler.endElement("item")

  def addRootElements(self, handler):
    handler.addQuickElement("title", self.feed['title'])
    handler.addQuickElement("link", self.feed['link'])
    handler.addQuickElement("description", self.feed['description'])
    if self.feed['feedUrl'] is not None:
      handler.addQuickElement("atom:link", None,
          {"rel": "self", "href": self.feed['feedUrl']})
    if self.feed['language'] is not None:
      handler.addQuickElement("language", self.feed['language'])
    for cat in self.feed['categories']:
      handler.addQuickElement("category", cat)
    if self.feed['feedCopyright'] is not None:
      handler.addQuickElement("copyright", self.feed['feedCopyright'])
    handler.addQuickElement("lastBuildDate", rfc2822Date(self.latestPostDate()))
    if self.feed['ttl'] is not None:
      handler.addQuickElement("ttl", self.feed['ttl'])

  def endChannelElement(self, handler):
    handler.endElement("channel")


class RssUserland091Feed(RssFeed):
  _version = "0.91"

  def addItemElements(self, handler, item):
    handler.addQuickElement("title", item['title'])
    handler.addQuickElement("link", item['link'])
    if item['description'] is not None:
      handler.addQuickElement("description", item['description'])


class Rss201rev2Feed(RssFeed):
  # Spec: http://blogs.law.harvard.edu/tech/rss
  _version = "2.0"

  def addItemElements(self, handler, item):
    handler.addQuickElement("title", item['title'])
    handler.addQuickElement("link", item['link'])
    if item['description'] is not None:
      handler.addQuickElement("description", item['description'])

    # Author information.
    if item["authorName"] and item["authorEmail"]:
      handler.addQuickElement("author", "%s (%s)" %
        (item['authorEmail'], item['authorName']))
    elif item["authorEmail"]:
      handler.addQuickElement("author", item["authorEmail"])
    elif item["authorName"]:
      handler.addQuickElement("dc:creator", item["authorName"], {"xmlns:dc": "http://purl.org/dc/elements/1.1/"})

    if item['pubdate'] is not None:
      handler.addQuickElement("pubDate", rfc2822Date(item['pubdate']))
    if item['comments'] is not None:
      handler.addQuickElement("comments", item['comments'])
    if item['uniqueId'] is not None:
      guidAttrs = {}
      if isinstance(item.get('uniqueIdIsPermalink'), bool):
        guidAttrs['isPermaLink'] = str(
          item['uniqueIdIsPermalink']).lower()
      handler.addQuickElement("guid", item['uniqueId'], guidAttrs)
    if item['ttl'] is not None:
      handler.addQuickElement("ttl", item['ttl'])

    # Enclosure.
    if item['enclosure'] is not None:
      handler.addQuickElement("enclosure", '',
        {"url": item['enclosure'].url, "length": item['enclosure'].length,
          "type": item['enclosure'].mimeType})

    # Categories.
    for cat in item['categories']:
      handler.addQuickElement("category", cat)


class Atom1Feed(SyndicationFeed):
  # Spec: http://atompub.org/2005/07/11/draft-ietf-atompub-format-10.html
  mimeType = 'application/atom+xml; charset=utf-8'
  ns = "http://www.w3.org/2005/Atom"

  def write(self, outfile, encoding):
    handler = SimplerXMLGenerator(outfile, encoding)
    handler.startDocument()
    handler.startElement('feed', self.rootAttributes())
    self.addRootElements(handler)
    self.writeItems(handler)
    handler.endElement("feed")

  def rootAttributes(self):
    if self.feed['language'] is not None:
      return {"xmlns": self.ns, "xml:lang": self.feed['language']}
    else:
      return {"xmlns": self.ns}

  def addRootElements(self, handler):
    handler.addQuickElement("title", self.feed['title'])
    handler.addQuickElement("link", "", {"rel": "alternate", "href": self.feed['link']})
    if self.feed['feedUrl'] is not None:
      handler.addQuickElement("link", "", {"rel": "self", "href": self.feed['feedUrl']})
    handler.addQuickElement("id", self.feed['id'])
    handler.addQuickElement("updated", rfc3339Date(self.latestPostDate()))
    if self.feed['authorName'] is not None:
      handler.startElement("author", {})
      handler.addQuickElement("name", self.feed['authorName'])
      if self.feed['authorEmail'] is not None:
        handler.addQuickElement("email", self.feed['authorEmail'])
      if self.feed['authorLink'] is not None:
        handler.addQuickElement("uri", self.feed['authorLink'])
      handler.endElement("author")
    if self.feed['subtitle'] is not None:
      handler.addQuickElement("subtitle", self.feed['subtitle'])
    for cat in self.feed['categories']:
      handler.addQuickElement("category", "", {"term": cat})
    if self.feed['feedCopyright'] is not None:
      handler.addQuickElement("rights", self.feed['feedCopyright'])

  def writeItems(self, handler):
    for item in self.items:
      handler.startElement("entry", self.itemAttributes(item))
      self.addItemElements(handler, item)
      handler.endElement("entry")

  def addItemElements(self, handler, item):
    handler.addQuickElement("title", item['title'])
    handler.addQuickElement("link", "", {"href": item['link'], "rel": "alternate"})

    if item['pubdate'] is not None:
      handler.addQuickElement('published', rfc3339Date(item['pubdate']))

    if item['updateddate'] is not None:
      handler.addQuickElement('updated', rfc3339Date(item['updateddate']))

    # Author information.
    if item['authorName'] is not None:
      handler.startElement("author", {})
      handler.addQuickElement("name", item['authorName'])
      if item['authorEmail'] is not None:
        handler.addQuickElement("email", item['authorEmail'])
      if item['authorLink'] is not None:
        handler.addQuickElement("uri", item['authorLink'])
      handler.endElement("author")

    # Unique ID.
    if item['uniqueId'] is not None:
      uniqueId = item['uniqueId']
    else:
      uniqueId = getTagUri(item['link'], item['pubdate'])
    handler.addQuickElement("id", uniqueId)

    # Summary.
    if item['description'] is not None:
      handler.addQuickElement("summary", item['description'], {"type": "html"})

    # Enclosure.
    if item['enclosure'] is not None:
      handler.addQuickElement("link", '',
        {"rel": "enclosure",
         "href": item['enclosure'].url,
         "length": item['enclosure'].length,
         "type": item['enclosure'].mimeType})

    # Categories.
    for cat in item['categories']:
      handler.addQuickElement("category", "", {"term": cat})

    # Rights.
    if item['itemCopyright'] is not None:
      handler.addQuickElement("rights", item['itemCopyright'])

# This isolates the decision of what the system default is, so calling code can
# do "feedgenerator.DefaultFeed" instead of "feedgenerator.Rss201rev2Feed".
DefaultFeed = Rss201rev2Feed
