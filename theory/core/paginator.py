import collections
from math import ceil

from theory.utils import six


class InvalidPage(Exception):
  pass


class PageNotAnInteger(InvalidPage):
  pass


class EmptyPage(InvalidPage):
  pass


class Paginator(object):

  def __init__(self, objectList, perPage, orphans=0,
         allowEmptyFirstPage=True):
    self.objectList = objectList
    self.perPage = int(perPage)
    self.orphans = int(orphans)
    self.allowEmptyFirstPage = allowEmptyFirstPage
    self._numPages = self._count = None

  def validateNumber(self, number):
    """
    Validates the given 1-based page number.
    """
    try:
      number = int(number)
    except (TypeError, ValueError):
      raise PageNotAnInteger('That page number is not an integer')
    if number < 1:
      raise EmptyPage('That page number is less than 1')
    if number > self.numPages:
      if number == 1 and self.allowEmptyFirstPage:
        pass
      else:
        raise EmptyPage('That page contains no results')
    return number

  def page(self, number):
    """
    Returns a Page object for the given 1-based page number.
    """
    number = self.validateNumber(number)
    bottom = (number - 1) * self.perPage
    top = bottom + self.perPage
    if top + self.orphans >= self.count:
      top = self.count
    return self._getPage(self.objectList[bottom:top], number, self)

  def _getPage(self, *args, **kwargs):
    """
    Returns an instance of a single page.

    This hook can be used by subclasses to use an alternative to the
    standard :cls:`Page` object.
    """
    return Page(*args, **kwargs)

  def _getCount(self):
    """
    Returns the total number of objects, across all pages.
    """
    if self._count is None:
      try:
        self._count = self.objectList.count()
      except (AttributeError, TypeError):
        # AttributeError if objectList has no count() method.
        # TypeError if objectList.count() requires arguments
        # (i.e. is of type list).
        self._count = len(self.objectList)
    return self._count
  count = property(_getCount)

  def _getNumPages(self):
    """
    Returns the total number of pages.
    """
    if self._numPages is None:
      if self.count == 0 and not self.allowEmptyFirstPage:
        self._numPages = 0
      else:
        hits = max(1, self.count - self.orphans)
        self._numPages = int(ceil(hits / float(self.perPage)))
    return self._numPages
  numPages = property(_getNumPages)

  def _getPageRange(self):
    """
    Returns a 1-based range of pages for iterating through within
    a template for loop.
    """
    return range(1, self.numPages + 1)
  pageRange = property(_getPageRange)


QuerySetPaginator = Paginator   # For backwards-compatibility.


class Page(collections.Sequence):

  def __init__(self, objectList, number, paginator):
    self.objectList = objectList
    self.number = number
    self.paginator = paginator

  def __repr__(self):
    return '<Page %s of %s>' % (self.number, self.paginator.numPages)

  def __len__(self):
    return len(self.objectList)

  def __getitem__(self, index):
    if not isinstance(index, (slice,) + six.integerTypes):
      raise TypeError
    # The objectList is converted to a list so that if it was a QuerySet
    # it won't be a database hit per __getitem__.
    if not isinstance(self.objectList, list):
      self.objectList = list(self.objectList)
    return self.objectList[index]

  def hasNext(self):
    return self.number < self.paginator.numPages

  def hasPrevious(self):
    return self.number > 1

  def hasOtherPages(self):
    return self.hasPrevious() or self.hasNext()

  def nextPageNumber(self):
    return self.paginator.validateNumber(self.number + 1)

  def previousPageNumber(self):
    return self.paginator.validateNumber(self.number - 1)

  def startIndex(self):
    """
    Returns the 1-based index of the first object on this page,
    relative to total objects in the paginator.
    """
    # Special case, return zero if no items.
    if self.paginator.count == 0:
      return 0
    return (self.paginator.perPage * (self.number - 1)) + 1

  def endIndex(self):
    """
    Returns the 1-based index of the last object on this page,
    relative to total objects found (hits).
    """
    # Special case for the last page because there can be orphans.
    if self.number == self.paginator.numPages:
      return self.paginator.count
    return self.number * self.paginator.perPage
