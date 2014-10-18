"""
Classes to represent the definitions of aggregate functions.
"""
from theory.db.model.constants import LOOKUP_SEP

__all__ = [
  'Aggregate', 'Avg', 'Count', 'Max', 'Min', 'StdDev', 'Sum', 'Variance',
]


def refsAggregate(lookupParts, aggregates):
  """
  A little helper method to check if the lookupParts contains references
  to the given aggregates set. Because the LOOKUP_SEP is contained in the
  default annotation names we must check each prefix of the lookupParts
  for match.
  """
  for n in range(len(lookupParts) + 1):
    levelN_lookup = LOOKUP_SEP.join(lookupParts[0:n])
    if levelN_lookup in aggregates:
      return aggregates[levelN_lookup], lookupParts[n:]
  return False, ()


class Aggregate(object):
  """
  Default Aggregate definition.
  """
  def __init__(self, lookup, **extra):
    """Instantiate a new aggregate.

     * lookup is the field on which the aggregate operates.
     * extra is a dictionary of additional data to provide for the
      aggregate definition

    Also utilizes the class variables:
     * name, the identifier for this aggregate function.
    """
    self.lookup = lookup
    self.extra = extra

  def _defaultAlias(self):
    return '%s__%s' % (self.lookup, self.name.lower())
  defaultAlias = property(_defaultAlias)

  def addToQuery(self, query, alias, col, source, isSummary):
    """Add the aggregate to the nominated query.

    This method is used to convert the generic Aggregate definition into a
    backend-specific definition.

     * query is the backend-specific query instance to which the aggregate
      is to be added.
     * col is a column reference describing the subject field
      of the aggregate. It can be an alias, or a tuple describing
      a table and column name.
     * source is the underlying field or aggregate definition for
      the column reference. If the aggregate is not an ordinal or
      computed type, this reference is used to determine the coerced
      output type of the aggregate.
     * isSummary is a boolean that is set True if the aggregate is a
      summary value rather than an annotation.
    """
    klass = getattr(query.aggregatesModule, self.name)
    aggregate = klass(col, source=source, isSummary=isSummary, **self.extra)
    query.aggregates[alias] = aggregate


class Avg(Aggregate):
  name = 'Avg'


class Count(Aggregate):
  name = 'Count'


class Max(Aggregate):
  name = 'Max'


class Min(Aggregate):
  name = 'Min'


class StdDev(Aggregate):
  name = 'StdDev'


class Sum(Aggregate):
  name = 'Sum'


class Variance(Aggregate):
  name = 'Variance'
