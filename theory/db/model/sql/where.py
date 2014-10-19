"""
Code to manage the creation and SQL rendering of 'where' constraints.
"""

import collections
import datetime
from itertools import repeat
import warnings

from theory.conf import settings
from theory.db.model.fields import DateTimeField, Field
from theory.db.model.sql.datastructures import EmptyResultSet, Empty
from theory.db.model.sql.aggregates import Aggregate
from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils.six.moves import xrange
from theory.utils import timezone
from theory.utils import tree


# Connection types
AND = 'AND'
OR = 'OR'


class EmptyShortCircuit(Exception):
  """
  Internal exception used to indicate that a "matches nothing" node should be
  added to the where-clause.
  """
  pass


class WhereNode(tree.Node):
  """
  Used to represent the SQL where-clause.

  The class is tied to the Query class that created it (in order to create
  the correct SQL).

  A child is usually a tuple of:
    (Constraint(alias, targetcol, field), lookupType, value)
  where value can be either raw Python value, or Query, ExpressionNode or
  something else knowing how to turn itself into SQL.

  However, a child could also be any class with asSql() and either
  relabeledClone() method or relabelAliases() and clone() methods. The
  second alternative should be used if the alias is not the only mutable
  variable.
  """
  default = AND

  def _prepareData(self, data):
    """
    Prepare data for addition to the tree. If the data is a list or tuple,
    it is expected to be of the form (obj, lookupType, value), where obj
    is a Constraint object, and is then slightly munged before being
    stored (to avoid storing any reference to field objects). Otherwise,
    the 'data' is stored unchanged and can be any class with an 'asSql()'
    method.
    """
    if not isinstance(data, (list, tuple)):
      return data
    obj, lookupType, value = data
    if isinstance(value, collections.Iterator):
      # Consume any generators immediately, so that we can determine
      # emptiness and transform any non-empty values correctly.
      value = list(value)

    # The "valueAnnotation" parameter is used to pass auxiliary information
    # about the value(s) to the query construction. Specifically, datetime
    # and empty values need special handling. Other types could be used
    # here in the future (using Python types is suggested for consistency).
    if (isinstance(value, datetime.datetime)
        or (isinstance(obj.field, DateTimeField) and lookupType != 'isnull')):
      valueAnnotation = datetime.datetime
    elif hasattr(value, 'valueAnnotation'):
      valueAnnotation = value.valueAnnotation
    else:
      valueAnnotation = bool(value)

    if hasattr(obj, "prepare"):
      value = obj.prepare(lookupType, value)
    return (obj, lookupType, valueAnnotation, value)

  def asSql(self, qn, connection):
    """
    Returns the SQL version of the where clause and the value to be
    substituted in. Returns '', [] if this node matches everything,
    None, [] if this node is empty, and raises EmptyResultSet if this
    node can't match anything.
    """
    # Note that the logic here is made slightly more complex than
    # necessary because there are two kind of empty nodes: Nodes
    # containing 0 children, and nodes that are known to match everything.
    # A match-everything node is different than empty node (which also
    # technically matches everything) for backwards compatibility reasons.
    # Refs #5261.
    result = []
    resultParams = []
    everythingChilds, nothingChilds = 0, 0
    nonEmptyChilds = len(self.children)

    for child in self.children:
      try:
        if hasattr(child, 'asSql'):
          sql, params = qn.compile(child)
        else:
          # A leaf node in the tree.
          sql, params = self.makeAtom(child, qn, connection)
      except EmptyResultSet:
        nothingChilds += 1
      else:
        if sql:
          result.append(sql)
          resultParams.extend(params)
        else:
          if sql is None:
            # Skip empty childs totally.
            nonEmptyChilds -= 1
            continue
          everythingChilds += 1
      # Check if this node matches nothing or everything.
      # First check the amount of full nodes and empty nodes
      # to make this node empty/full.
      if self.connector == AND:
        fullNeeded, emptyNeeded = nonEmptyChilds, 1
      else:
        fullNeeded, emptyNeeded = 1, nonEmptyChilds
      # Now, check if this node is full/empty using the
      # counts.
      if emptyNeeded - nothingChilds <= 0:
        if self.negated:
          return '', []
        else:
          raise EmptyResultSet
      if fullNeeded - everythingChilds <= 0:
        if self.negated:
          raise EmptyResultSet
        else:
          return '', []

    if nonEmptyChilds == 0:
      # All the child nodes were empty, so this one is empty, too.
      return None, []
    conn = ' %s ' % self.connector
    sqlString = conn.join(result)
    if sqlString:
      if self.negated:
        # Some backends (Oracle at least) need parentheses
        # around the inner SQL in the negated case, even if the
        # inner SQL contains just a single expression.
        sqlString = 'NOT (%s)' % sqlString
      elif len(result) > 1:
        sqlString = '(%s)' % sqlString
    return sqlString, resultParams

  def getGroupByCols(self):
    cols = []
    for child in self.children:
      if hasattr(child, 'getGroupByCols'):
        cols.extend(child.getGroupByCols())
      else:
        if isinstance(child[0], Constraint):
          cols.append((child[0].alias, child[0].col))
        if hasattr(child[3], 'getGroupByCols'):
          cols.extend(child[3].getGroupByCols())
    return cols

  def makeAtom(self, child, qn, connection):
    """
    Turn a tuple (Constraint(tableAlias, columnName, dbType),
    lookupType, valueAnnotation, params) into valid SQL.

    The first item of the tuple may also be an Aggregate.

    Returns the string for the SQL fragment and the parameters to use for
    it.
    """
    warnings.warn(
      "The makeAtom() method will be removed in Theory 1.9. Use Lookup class instead.",
      RemovedInTheory19Warning)
    lvalue, lookupType, valueAnnotation, paramsOrValue = child
    fieldInternalType = lvalue.field.getInternalType() if lvalue.field else None

    if isinstance(lvalue, Constraint):
      try:
        lvalue, params = lvalue.process(lookupType, paramsOrValue, connection)
      except EmptyShortCircuit:
        raise EmptyResultSet
    elif isinstance(lvalue, Aggregate):
      params = lvalue.field.getDbPrepLookup(lookupType, paramsOrValue, connection)
    else:
      raise TypeError("'makeAtom' expects a Constraint or an Aggregate "
              "as the first item of its 'child' argument.")

    if isinstance(lvalue, tuple):
      # A direct database column lookup.
      fieldSql, fieldParams = self.sqlForColumns(lvalue, qn, connection, fieldInternalType), []
    else:
      # A smart object with an asSql() method.
      fieldSql, fieldParams = qn.compile(lvalue)

    isDatetimeField = valueAnnotation is datetime.datetime
    castSql = connection.ops.datetimeCastSql() if isDatetimeField else '%s'

    if hasattr(params, 'asSql'):
      extra, params = qn.compile(params)
      castSql = ''
    else:
      extra = ''

    params = fieldParams + params

    if (len(params) == 1 and params[0] == '' and lookupType == 'exact'
        and connection.features.interpretsEmptyStringsAsNulls):
      lookupType = 'isnull'
      valueAnnotation = True

    if lookupType in connection.operators:
      format = "%s %%s %%s" % (connection.ops.lookupCast(lookupType),)
      return (format % (fieldSql,
               connection.operators[lookupType] % castSql,
               extra), params)

    if lookupType == 'in':
      if not valueAnnotation:
        raise EmptyResultSet
      if extra:
        return ('%s IN %s' % (fieldSql, extra), params)
      maxInListSize = connection.ops.maxInListSize()
      if maxInListSize and len(params) > maxInListSize:
        # Break up the params list into an OR of manageable chunks.
        inClauseElements = ['(']
        for offset in xrange(0, len(params), maxInListSize):
          if offset > 0:
            inClauseElements.append(' OR ')
          inClauseElements.append('%s IN (' % fieldSql)
          groupSize = min(len(params) - offset, maxInListSize)
          paramGroup = ', '.join(repeat('%s', groupSize))
          inClauseElements.append(paramGroup)
          inClauseElements.append(')')
        inClauseElements.append(')')
        return ''.join(inClauseElements), params
      else:
        return ('%s IN (%s)' % (fieldSql,
                    ', '.join(repeat('%s', len(params)))),
            params)
    elif lookupType in ('range', 'year'):
      return ('%s BETWEEN %%s and %%s' % fieldSql, params)
    elif isDatetimeField and lookupType in ('month', 'day', 'weekDay',
                          'hour', 'minute', 'second'):
      tzname = timezone.getCurrentTimezoneName() if settings.USE_TZ else None
      sql, tzParams = connection.ops.datetimeExtractSql(lookupType, fieldSql, tzname)
      return ('%s = %%s' % sql, tzParams + params)
    elif lookupType in ('month', 'day', 'weekDay'):
      return ('%s = %%s'
          % connection.ops.dateExtractSql(lookupType, fieldSql), params)
    elif lookupType == 'isnull':
      assert valueAnnotation in (True, False), "Invalid valueAnnotation for isnull"
      return ('%s IS %sNULL' % (fieldSql, ('' if valueAnnotation else 'NOT ')), ())
    elif lookupType == 'search':
      return (connection.ops.fulltextSearchSql(fieldSql), params)
    elif lookupType in ('regex', 'iregex'):
      return connection.ops.regexLookup(lookupType) % (fieldSql, castSql), params

    raise TypeError('Invalid lookupType: %r' % lookupType)

  def sqlForColumns(self, data, qn, connection, internalType=None):
    """
    Returns the SQL fragment used for the left-hand side of a column
    constraint (for example, the "T1.foo" portion in the clause
    "WHERE ... T1.foo = 6") and a list of parameters.
    """
    tableAlias, name, dbType = data
    if tableAlias:
      lhs = '%s.%s' % (qn(tableAlias), qn(name))
    else:
      lhs = qn(name)
    return connection.ops.fieldCastSql(dbType, internalType) % lhs

  def relabelAliases(self, changeMap):
    """
    Relabels the alias values of any children. 'changeMap' is a dictionary
    mapping old (current) alias values to the new values.
    """
    for pos, child in enumerate(self.children):
      if hasattr(child, 'relabelAliases'):
        # For example another WhereNode
        child.relabelAliases(changeMap)
      elif hasattr(child, 'relabeledClone'):
        self.children[pos] = child.relabeledClone(changeMap)
      elif isinstance(child, (list, tuple)):
        # tuple starting with Constraint
        child = (child[0].relabeledClone(changeMap),) + child[1:]
        if hasattr(child[3], 'relabeledClone'):
          child = (child[0], child[1], child[2]) + (
            child[3].relabeledClone(changeMap),)
        self.children[pos] = child

  def clone(self):
    """
    Creates a clone of the tree. Must only be called on root nodes (nodes
    with empty subtreeParents). Childs must be either (Contraint, lookup,
    value) tuples, or objects supporting .clone().
    """
    clone = self.__class__._newInstance(
      children=[], connector=self.connector, negated=self.negated)
    for child in self.children:
      if hasattr(child, 'clone'):
        clone.children.append(child.clone())
      else:
        clone.children.append(child)
    return clone


class EmptyWhere(WhereNode):
  def add(self, data, connector):
    return

  def asSql(self, qn=None, connection=None):
    raise EmptyResultSet


class EverythingNode(object):
  """
  A node that matches everything.
  """

  def asSql(self, qn=None, connection=None):
    return '', []


class NothingNode(object):
  """
  A node that matches nothing.
  """
  def asSql(self, qn=None, connection=None):
    raise EmptyResultSet


class ExtraWhere(object):
  def __init__(self, sqls, params):
    self.sqls = sqls
    self.params = params

  def asSql(self, qn=None, connection=None):
    sqls = ["(%s)" % sql for sql in self.sqls]
    return " AND ".join(sqls), list(self.params or ())


class Constraint(object):
  """
  An object that can be passed to WhereNode.add() and knows how to
  pre-process itself prior to including in the WhereNode.
  """
  def __init__(self, alias, col, field):
    warnings.warn(
      "The Constraint class will be removed in Theory 1.9. Use Lookup class instead.",
      RemovedInTheory19Warning)
    self.alias, self.col, self.field = alias, col, field

  def prepare(self, lookupType, value):
    if self.field and not hasattr(value, 'asSql'):
      return self.field.getPrepLookup(lookupType, value)
    return value

  def process(self, lookupType, value, connection):
    """
    Returns a tuple of data suitable for inclusion in a WhereNode
    instance.
    """
    # Because of circular imports, we need to import this here.
    from theory.db.model.base import ObjectDoesNotExist
    try:
      if self.field:
        params = self.field.getDbPrepLookup(lookupType, value,
          connection=connection, prepared=True)
        dbType = self.field.dbType(connection=connection)
      else:
        # This branch is used at times when we add a comparison to NULL
        # (we don't really want to waste time looking up the associated
        # field object at the calling location).
        params = Field().getDbPrepLookup(lookupType, value,
          connection=connection, prepared=True)
        dbType = None
    except ObjectDoesNotExist:
      raise EmptyShortCircuit

    return (self.alias, self.col, dbType), params

  def relabeledClone(self, changeMap):
    if self.alias not in changeMap:
      return self
    else:
      new = Empty()
      new.__class__ = self.__class__
      new.alias, new.col, new.field = changeMap[self.alias], self.col, self.field
      return new


class SubqueryConstraint(object):
  def __init__(self, alias, columns, targets, queryObject):
    self.alias = alias
    self.columns = columns
    self.targets = targets
    self.queryObject = queryObject

  def asSql(self, qn, connection):
    query = self.queryObject

    # QuerySet was sent
    if hasattr(query, 'values'):
      if query._db and connection.alias != query._db:
        raise ValueError("Can't do subqueries with queries on different DBs.")
      # Do not override already existing values.
      if not hasattr(query, 'fieldNames'):
        query = query.values(*self.targets)
      else:
        query = query._clone()
      query = query.query
      if query.canFilter():
        # If there is no slicing in use, then we can safely drop all ordering
        query.clearOrdering(True)

    queryCompiler = query.getCompiler(connection=connection)
    return queryCompiler.asSubqueryCondition(self.alias, self.columns, qn)

  def relabelAliases(self, changeMap):
    self.alias = changeMap.get(self.alias, self.alias)

  def clone(self):
    return self.__class__(
      self.alias, self.columns, self.targets,
      self.queryObject)
