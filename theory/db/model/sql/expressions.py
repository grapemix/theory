import copy

from theory.core.exceptions import FieldError
from theory.db.model.constants import LOOKUP_SEP
from theory.db.model.fields import FieldDoesNotExist


class SQLEvaluator(object):
  def __init__(self, expression, query, allowJoins=True, reuse=None):
    self.expression = expression
    self.opts = query.getMeta()
    self.reuse = reuse
    self.cols = []
    self.expression.prepare(self, query, allowJoins)

  def relabeledClone(self, changeMap):
    clone = copy.copy(self)
    clone.cols = []
    for node, col in self.cols:
      if hasattr(col, 'relabeledClone'):
        clone.cols.append((node, col.relabeledClone(changeMap)))
      else:
        clone.cols.append((node,
                  (changeMap.get(col[0], col[0]), col[1])))
    return clone

  def getGroupByCols(self):
    cols = []
    for node, col in self.cols:
      if hasattr(node, 'getGroupByCols'):
        cols.extend(node.getGroupByCols())
      elif isinstance(col, tuple):
        cols.append(col)
    return cols

  def prepare(self):
    return self

  def asSql(self, qn, connection):
    return self.expression.evaluate(self, qn, connection)

  #####################################################
  # Visitor methods for initial expression preparation #
  #####################################################

  def prepareNode(self, node, query, allowJoins):
    for child in node.children:
      if hasattr(child, 'prepare'):
        child.prepare(self, query, allowJoins)

  def prepareLeaf(self, node, query, allowJoins):
    if not allowJoins and LOOKUP_SEP in node.name:
      raise FieldError("Joined field references are not permitted in this query")

    fieldList = node.name.split(LOOKUP_SEP)
    if node.name in query.aggregates:
      self.cols.append((node, query.aggregateSelect[node.name]))
    else:
      try:
        field, sources, opts, joinList, path = query.setupJoins(
          fieldList, query.getMeta(),
          query.getInitialAlias(), self.reuse)
        self._usedJoins = joinList
        targets, _, joinList = query.trimJoins(sources, joinList, path)
        if self.reuse is not None:
          self.reuse.update(joinList)
        for t in targets:
          self.cols.append((node, (joinList[-1], t.column)))
      except FieldDoesNotExist:
        raise FieldError("Cannot resolve keyword %r into field. "
                 "Choices are: %s" % (self.name,
                           [f.name for f in self.opts.fields]))

  ##################################################
  # Visitor methods for final expression evaluation #
  ##################################################

  def evaluateNode(self, node, qn, connection):
    expressions = []
    expressionParams = []
    for child in node.children:
      if hasattr(child, 'evaluate'):
        sql, params = child.evaluate(self, qn, connection)
      else:
        sql, params = '%s', (child,)

      if len(getattr(child, 'children', [])) > 1:
        format = '(%s)'
      else:
        format = '%s'

      if sql:
        expressions.append(format % sql)
        expressionParams.extend(params)

    return connection.ops.combineExpression(node.connector, expressions), expressionParams

  def evaluateLeaf(self, node, qn, connection):
    col = None
    for n, c in self.cols:
      if n is node:
        col = c
        break
    if col is None:
      raise ValueError("Given node not found")
    if hasattr(col, 'asSql'):
      return col.asSql(qn, connection)
    else:
      return '%s.%s' % (qn(col[0]), qn(col[1])), []

  def evaluateDateModifierNode(self, node, qn, connection):
    timedelta = node.children.pop()
    sql, params = self.evaluateNode(node, qn, connection)
    node.children.append(timedelta)

    if (timedelta.days == timedelta.seconds == timedelta.microseconds == 0):
      return sql, params

    return connection.ops.dateIntervalSql(sql, node.connector, timedelta), params
