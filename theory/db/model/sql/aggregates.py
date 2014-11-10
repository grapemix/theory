"""
Classes to represent the default SQL aggregate functions
"""
import copy

from theory.db.model.fields import IntegerField, FloatField
from theory.db.model.lookups import RegisterLookupMixin
from theory.utils.functional import cachedProperty


__all__ = ['Aggregate', 'Avg', 'Count', 'Max', 'Min', 'StdDev', 'Sum', 'Variance']


class Aggregate(RegisterLookupMixin):
  """
  Default SQL Aggregate.
  """
  isOrdinal = False
  isComputed = False
  sqlTemplate = '%(function)s(%(field)s)'

  def __init__(self, col, source=None, isSummary=False, **extra):
    """Instantiate an SQL aggregate

     * col is a column reference describing the subject field
      of the aggregate. It can be an alias, or a tuple describing
      a table and column name.
     * source is the underlying field or aggregate definition for
      the column reference. If the aggregate is not an ordinal or
      computed type, this reference is used to determine the coerced
      output type of the aggregate.
     * extra is a dictionary of additional data to provide for the
      aggregate definition

    Also utilizes the class variables:
     * sqlFunction, the name of the SQL function that implements the
      aggregate.
     * sqlTemplate, a template string that is used to render the
      aggregate into SQL.
     * isOrdinal, a boolean indicating if the output of this aggregate
      is an integer (e.g., a count)
     * isComputed, a boolean indicating if this output of this aggregate
      is a computed float (e.g., an average), regardless of the input
      type.

    """
    self.col = col
    self.source = source
    self.isSummary = isSummary
    self.extra = extra

    # Follow the chain of aggregate sources back until you find an
    # actual field, or an aggregate that forces a particular output
    # type. This type of this field will be used to coerce values
    # retrieved from the database.
    tmp = self

    while tmp and isinstance(tmp, Aggregate):
      if getattr(tmp, 'isOrdinal', False):
        tmp = self._ordinalAggregateField
      elif getattr(tmp, 'isComputed', False):
        tmp = self._computedAggregateField
      else:
        tmp = tmp.source

    self.field = tmp

  # Two fake fields used to identify aggregate types in data-conversion operations.
  @cachedProperty
  def _ordinalAggregateField(self):
    return IntegerField()

  @cachedProperty
  def _computedAggregateField(self):
    return FloatField()

  def relabeledClone(self, changeMap):
    clone = copy.copy(self)
    if isinstance(self.col, (list, tuple)):
      clone.col = (changeMap.get(self.col[0], self.col[0]), self.col[1])
    return clone

  def asSql(self, qn, connection):
    "Return the aggregate, rendered as SQL with parameters."
    params = []

    if hasattr(self.col, 'asSql'):
      fieldName, params = self.col.asSql(qn, connection)
    elif isinstance(self.col, (list, tuple)):
      fieldName = '.'.join(qn(c) for c in self.col)
    else:
      fieldName = qn(self.col)

    substitutions = {
      'function': self.sqlFunction,
      'field': fieldName
    }
    substitutions.update(self.extra)

    return self.sqlTemplate % substitutions, params

  def getGroupByCols(self):
    return []

  @property
  def outputField(self):
    return self.field


class Avg(Aggregate):
  isComputed = True
  sqlFunction = 'AVG'


class Count(Aggregate):
  isOrdinal = True
  sqlFunction = 'COUNT'
  sqlTemplate = '%(function)s(%(distinct)s%(field)s)'

  def __init__(self, col, distinct=False, **extra):
    super(Count, self).__init__(col, distinct='DISTINCT ' if distinct else '', **extra)


class Max(Aggregate):
  sqlFunction = 'MAX'


class Min(Aggregate):
  sqlFunction = 'MIN'


class StdDev(Aggregate):
  isComputed = True

  def __init__(self, col, sample=False, **extra):
    super(StdDev, self).__init__(col, **extra)
    self.sqlFunction = 'STDDEV_SAMP' if sample else 'STDDEV_POP'


class Sum(Aggregate):
  sqlFunction = 'SUM'


class Variance(Aggregate):
  isComputed = True

  def __init__(self, col, sample=False, **extra):
    super(Variance, self).__init__(col, **extra)
    self.sqlFunction = 'VAR_SAMP' if sample else 'VAR_POP'
