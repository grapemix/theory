from copy import copy
from itertools import repeat
import inspect

from theory.conf import settings
from theory.utils import timezone
from theory.utils.functional import cachedProperty
from theory.utils.six.moves import xrange


class RegisterLookupMixin(object):
  def _getLookup(self, lookupName):
    try:
      return self.classLookups[lookupName]
    except KeyError:
      # To allow for inheritance, check parent class' classLookups.
      for parent in inspect.getmro(self.__class__):
        if 'classLookups' not in parent.__dict__:
          continue
        if lookupName in parent.classLookups:
          return parent.classLookups[lookupName]
    except AttributeError:
      # This class didn't have any classLookups
      pass
    return None

  def getLookup(self, lookupName):
    found = self._getLookup(lookupName)
    if found is None and hasattr(self, 'outputField'):
      return self.outputField.getLookup(lookupName)
    if found is not None and not issubclass(found, Lookup):
      return None
    return found

  def getTransform(self, lookupName):
    found = self._getLookup(lookupName)
    if found is None and hasattr(self, 'outputField'):
      return self.outputField.getTransform(lookupName)
    if found is not None and not issubclass(found, Transform):
      return None
    return found

  @classmethod
  def registerLookup(cls, lookup):
    if 'classLookups' not in cls.__dict__:
      cls.classLookups = {}
    cls.classLookups[lookup.lookupName] = lookup

  @classmethod
  def _unregisterLookup(cls, lookup):
    """
    Removes given lookup from cls lookups. Meant to be used in
    tests only.
    """
    del cls.classLookups[lookup.lookupName]


class Transform(RegisterLookupMixin):
  def __init__(self, lhs, lookups):
    self.lhs = lhs
    self.initLookups = lookups[:]

  def asSql(self, qn, connection):
    raise NotImplementedError

  @cachedProperty
  def outputField(self):
    return self.lhs.outputField

  def relabeledClone(self, relabels):
    return self.__class__(self.lhs.relabeledClone(relabels))

  def getGroupByCols(self):
    return self.lhs.getGroupByCols()


class Lookup(RegisterLookupMixin):
  lookupName = None

  def __init__(self, lhs, rhs):
    self.lhs, self.rhs = lhs, rhs
    self.rhs = self.getPrepLookup()

  def getPrepLookup(self):
    return self.lhs.outputField.getPrepLookup(self.lookupName, self.rhs)

  def getDbPrepLookup(self, value, connection):
    return (
      '%s', self.lhs.outputField.getDbPrepLookup(
        self.lookupName, value, connection, prepared=True))

  def processLhs(self, qn, connection, lhs=None):
    lhs = lhs or self.lhs
    return qn.compile(lhs)

  def processRhs(self, qn, connection):
    value = self.rhs
    # Due to historical reasons there are a couple of different
    # ways to produce sql here. getCompiler is likely a Query
    # instance, _asSql QuerySet and asSql just something with
    # asSql. Finally the value can of course be just plain
    # Python value.
    if hasattr(value, 'getCompiler'):
      value = value.getCompiler(connection=connection)
    if hasattr(value, 'asSql'):
      sql, params = qn.compile(value)
      return '(' + sql + ')', params
    if hasattr(value, '_asSql'):
      sql, params = value._asSql(connection=connection)
      return '(' + sql + ')', params
    else:
      return self.getDbPrepLookup(value, connection)

  def rhsIsDirectValue(self):
    return not(
      hasattr(self.rhs, 'asSql') or
      hasattr(self.rhs, '_asSql') or
      hasattr(self.rhs, 'getCompiler'))

  def relabeledClone(self, relabels):
    new = copy(self)
    new.lhs = new.lhs.relabeledClone(relabels)
    if hasattr(new.rhs, 'relabeledClone'):
      new.rhs = new.rhs.relabeledClone(relabels)
    return new

  def getGroupByCols(self):
    cols = self.lhs.getGroupByCols()
    if hasattr(self.rhs, 'getGroupByCols'):
      cols.extend(self.rhs.getGroupByCols())
    return cols

  def asSql(self, qn, connection):
    raise NotImplementedError


class BuiltinLookup(Lookup):
  def processLhs(self, qn, connection, lhs=None):
    lhsSql, params = super(BuiltinLookup, self).processLhs(
      qn, connection, lhs)
    fieldInternalType = self.lhs.outputField.getInternalType()
    dbType = self.lhs.outputField.dbType(connection=connection)
    lhsSql = connection.ops.fieldCastSql(
      dbType, fieldInternalType) % lhsSql
    lhsSql = connection.ops.lookupCast(self.lookupName) % lhsSql
    return lhsSql, params

  def asSql(self, qn, connection):
    lhsSql, params = self.processLhs(qn, connection)
    rhsSql, rhsParams = self.processRhs(qn, connection)
    params.extend(rhsParams)
    rhsSql = self.getRhsOp(connection, rhsSql)
    return '%s %s' % (lhsSql, rhsSql), params

  def getRhsOp(self, connection, rhs):
    return connection.operators[self.lookupName] % rhs


defaultLookups = {}


class Exact(BuiltinLookup):
  lookupName = 'exact'
defaultLookups['exact'] = Exact


class IExact(BuiltinLookup):
  lookupName = 'iexact'
defaultLookups['iexact'] = IExact


class Contains(BuiltinLookup):
  lookupName = 'contains'
defaultLookups['contains'] = Contains


class IContains(BuiltinLookup):
  lookupName = 'icontains'
defaultLookups['icontains'] = IContains


class GreaterThan(BuiltinLookup):
  lookupName = 'gt'
defaultLookups['gt'] = GreaterThan


class GreaterThanOrEqual(BuiltinLookup):
  lookupName = 'gte'
defaultLookups['gte'] = GreaterThanOrEqual


class LessThan(BuiltinLookup):
  lookupName = 'lt'
defaultLookups['lt'] = LessThan


class LessThanOrEqual(BuiltinLookup):
  lookupName = 'lte'
defaultLookups['lte'] = LessThanOrEqual


class In(BuiltinLookup):
  lookupName = 'in'

  def getDbPrepLookup(self, value, connection):
    params = self.lhs.outputField.getDbPrepLookup(
      self.lookupName, value, connection, prepared=True)
    if not params:
      # TODO: check why this leads to circular import
      from theory.db.model.sql.datastructures import EmptyResultSet
      raise EmptyResultSet
    placeholder = '(' + ', '.join('%s' for p in params) + ')'
    return (placeholder, params)

  def getRhsOp(self, connection, rhs):
    return 'IN %s' % rhs

  def asSql(self, qn, connection):
    maxInListSize = connection.ops.maxInListSize()
    if self.rhsIsDirectValue() and (maxInListSize and
                      len(self.rhs) > maxInListSize):
      rhs, rhsParams = self.processRhs(qn, connection)
      lhs, lhsParams = self.processLhs(qn, connection)
      inClauseElements = ['(']
      params = []
      for offset in xrange(0, len(rhsParams), maxInListSize):
        if offset > 0:
          inClauseElements.append(' OR ')
        inClauseElements.append('%s IN (' % lhs)
        params.extend(lhsParams)
        groupSize = min(len(rhsParams) - offset, maxInListSize)
        paramGroup = ', '.join(repeat('%s', groupSize))
        inClauseElements.append(paramGroup)
        inClauseElements.append(')')
        params.extend(rhsParams[offset: offset + maxInListSize])
      inClauseElements.append(')')
      return ''.join(inClauseElements), params
    else:
      return super(In, self).asSql(qn, connection)


defaultLookups['in'] = In


class PatternLookup(BuiltinLookup):
  def getRhsOp(self, connection, rhs):
    # Assume we are in startswith. We need to produce SQL like:
    #     col LIKE %s, ['thevalue%']
    # For python values we can (and should) do that directly in Python,
    # but if the value is for example reference to other column, then
    # we need to add the % pattern match to the lookup by something like
    #     col LIKE othercol || '%%'
    # So, for Python values we don't need any special pattern, but for
    # SQL reference values we need the correct pattern added.
    value = self.rhs
    if (hasattr(value, 'getCompiler') or hasattr(value, 'asSql')
        or hasattr(value, '_asSql')):
      return connection.patternOps[self.lookupName] % rhs
    else:
      return super(PatternLookup, self).getRhsOp(connection, rhs)


class StartsWith(PatternLookup):
  lookupName = 'startswith'
defaultLookups['startswith'] = StartsWith


class IStartsWith(PatternLookup):
  lookupName = 'istartswith'
defaultLookups['istartswith'] = IStartsWith


class EndsWith(BuiltinLookup):
  lookupName = 'endswith'
defaultLookups['endswith'] = EndsWith


class IEndsWith(BuiltinLookup):
  lookupName = 'iendswith'
defaultLookups['iendswith'] = IEndsWith


class Between(BuiltinLookup):
  def getRhsOp(self, connection, rhs):
    return "BETWEEN %s AND %s" % (rhs, rhs)


class Year(Between):
  lookupName = 'year'
defaultLookups['year'] = Year


class Range(Between):
  lookupName = 'range'
defaultLookups['range'] = Range


class DateLookup(BuiltinLookup):
  def processLhs(self, qn, connection, lhs=None):
    from theory.db.model import DateTimeField
    lhs, params = super(DateLookup, self).processLhs(qn, connection, lhs)
    if isinstance(self.lhs.outputField, DateTimeField):
      tzname = timezone.getCurrentTimezoneName() if settings.USE_TZ else None
      sql, tzParams = connection.ops.datetimeExtractSql(self.extractType, lhs, tzname)
      return connection.ops.lookupCast(self.lookupName) % sql, tzParams
    else:
      return connection.ops.dateExtractSql(self.lookupName, lhs), []

  def getRhsOp(self, connection, rhs):
    return '= %s' % rhs


class Month(DateLookup):
  lookupName = 'month'
  extractType = 'month'
defaultLookups['month'] = Month


class Day(DateLookup):
  lookupName = 'day'
  extractType = 'day'
defaultLookups['day'] = Day


class WeekDay(DateLookup):
  lookupName = 'weekDay'
  extractType = 'weekDay'
defaultLookups['weekDay'] = WeekDay


class Hour(DateLookup):
  lookupName = 'hour'
  extractType = 'hour'
defaultLookups['hour'] = Hour


class Minute(DateLookup):
  lookupName = 'minute'
  extractType = 'minute'
defaultLookups['minute'] = Minute


class Second(DateLookup):
  lookupName = 'second'
  extractType = 'second'
defaultLookups['second'] = Second


class IsNull(BuiltinLookup):
  lookupName = 'isnull'

  def asSql(self, qn, connection):
    sql, params = qn.compile(self.lhs)
    if self.rhs:
      return "%s IS NULL" % sql, params
    else:
      return "%s IS NOT NULL" % sql, params
defaultLookups['isnull'] = IsNull


class Search(BuiltinLookup):
  lookupName = 'search'

  def asSql(self, qn, connection):
    lhs, lhsParams = self.processLhs(qn, connection)
    rhs, rhsParams = self.processRhs(qn, connection)
    sqlTemplate = connection.ops.fulltextSearchSql(fieldName=lhs)
    return sqlTemplate, lhsParams + rhsParams

defaultLookups['search'] = Search


class Regex(BuiltinLookup):
  lookupName = 'regex'

  def asSql(self, qn, connection):
    if self.lookupName in connection.operators:
      return super(Regex, self).asSql(qn, connection)
    else:
      lhs, lhsParams = self.processLhs(qn, connection)
      rhs, rhsParams = self.processRhs(qn, connection)
      sqlTemplate = connection.ops.regexLookup(self.lookupName)
      return sqlTemplate % (lhs, rhs), lhsParams + rhsParams
defaultLookups['regex'] = Regex


class IRegex(Regex):
  lookupName = 'iregex'
defaultLookups['iregex'] = IRegex
