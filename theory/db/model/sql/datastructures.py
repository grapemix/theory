"""
Useful auxiliary data structures for query construction. Not useful outside
the SQL domain.
"""


class Col(object):
  def __init__(self, alias, target, source):
    self.alias, self.target, self.source = alias, target, source

  def asSql(self, qn, connection):
    return "%s.%s" % (qn(self.alias), qn(self.target.column)), []

  @property
  def outputField(self):
    return self.source

  def relabeledClone(self, relabels):
    return self.__class__(relabels.get(self.alias, self.alias), self.target, self.source)

  def getGroupByCols(self):
    return [(self.alias, self.target.column)]

  def getLookup(self, name):
    return self.outputField.getLookup(name)

  def getTransform(self, name):
    return self.outputField.getTransform(name)

  def prepare(self):
    return self


class EmptyResultSet(Exception):
  pass


class MultiJoin(Exception):
  """
  Used by join construction code to indicate the point at which a
  multi-valued join was attempted (if the caller wants to treat that
  exceptionally).
  """
  def __init__(self, namesPos, pathWithNames):
    self.level = namesPos
    # The path travelled, this includes the path to the multijoin.
    self.namesWithPath = pathWithNames


class Empty(object):
  pass


class Date(object):
  """
  Add a date selection column.
  """
  def __init__(self, col, lookupType):
    self.col = col
    self.lookupType = lookupType

  def relabeledClone(self, changeMap):
    return self.__class__((changeMap.get(self.col[0], self.col[0]), self.col[1]))

  def asSql(self, qn, connection):
    if isinstance(self.col, (list, tuple)):
      col = '%s.%s' % tuple(qn(c) for c in self.col)
    else:
      col = self.col
    return connection.ops.dateTruncSql(self.lookupType, col), []


class DateTime(object):
  """
  Add a datetime selection column.
  """
  def __init__(self, col, lookupType, tzname):
    self.col = col
    self.lookupType = lookupType
    self.tzname = tzname

  def relabeledClone(self, changeMap):
    return self.__class__((changeMap.get(self.col[0], self.col[0]), self.col[1]))

  def asSql(self, qn, connection):
    if isinstance(self.col, (list, tuple)):
      col = '%s.%s' % tuple(qn(c) for c in self.col)
    else:
      col = self.col
    return connection.ops.datetimeTruncSql(self.lookupType, col, self.tzname)
