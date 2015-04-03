from theory.db.model import Lookup, Transform


class PostgresSimpleLookup(Lookup):
  def asSql(self, qn, connection):
    lhs, lhsParams = self.processLhs(qn, connection)
    rhs, rhsParams = self.processRhs(qn, connection)
    params = lhsParams + rhsParams
    return '%s %s %s' % (lhs, self.operator, rhs), params


class FunctionTransform(Transform):
  def asSql(self, qn, connection):
    lhs, params = qn.compile(self.lhs)
    return "%s(%s)" % (self.function, lhs), params


class DataContains(PostgresSimpleLookup):
  lookupName = 'contains'
  operator = '@>'


class ContainedBy(PostgresSimpleLookup):
  lookupName = 'contained_by'
  operator = '<@'


class Overlap(PostgresSimpleLookup):
  lookupName = 'overlap'
  operator = '&&'


class Unaccent(FunctionTransform):
  bilateral = True
  lookupName = 'unaccent'
  function = 'UNACCENT'
