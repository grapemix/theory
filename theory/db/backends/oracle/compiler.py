from theory.db.model.sql import compiler
from theory.utils.six.moves import zipLongest


class SQLCompiler(compiler.SQLCompiler):
  def resolveColumns(self, row, fields=()):
    # If this query has limit/offset information, then we expect the
    # first column to be an extra "_RN" column that we need to throw
    # away.
    if self.query.highMark is not None or self.query.lowMark:
      rnOffset = 1
    else:
      rnOffset = 0
    indexStart = rnOffset + len(self.query.extraSelect)
    values = [self.query.convertValues(v, None, connection=self.connection)
         for v in row[rnOffset:indexStart]]
    for value, field in zipLongest(row[indexStart:], fields):
      values.append(self.query.convertValues(value, field, connection=self.connection))
    return tuple(values)

  def asSql(self, withLimits=True, withColAliases=False):
    """
    Creates the SQL for this query. Returns the SQL string and list
    of parameters.  This is overridden from the original Query class
    to handle the additional SQL Oracle requires to emulate LIMIT
    and OFFSET.

    If 'withLimits' is False, any limit/offset information is not
    included in the query.
    """
    if withLimits and self.query.lowMark == self.query.highMark:
      return '', ()

    # The `doOffset` flag indicates whether we need to construct
    # the SQL needed to use limit/offset with Oracle.
    doOffset = withLimits and (self.query.highMark is not None
                   or self.query.lowMark)
    if not doOffset:
      sql, params = super(SQLCompiler, self).asSql(withLimits=False,
          withColAliases=withColAliases)
    else:
      sql, params = super(SQLCompiler, self).asSql(withLimits=False,
                          withColAliases=True)

      # Wrap the base query in an outer SELECT * with boundaries on
      # the "_RN" column.  This is the canonical way to emulate LIMIT
      # and OFFSET on Oracle.
      highWhere = ''
      if self.query.highMark is not None:
        highWhere = 'WHERE ROWNUM <= %d' % (self.query.highMark,)
      sql = 'SELECT * FROM (SELECT ROWNUM AS "_RN", "_SUB".* FROM (%s) "_SUB" %s) WHERE "_RN" > %d' % (sql, highWhere, self.query.lowMark)

    return sql, params


class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
  pass


class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
  pass


class SQLUpdateCompiler(compiler.SQLUpdateCompiler, SQLCompiler):
  pass


class SQLAggregateCompiler(compiler.SQLAggregateCompiler, SQLCompiler):
  pass


class SQLDateCompiler(compiler.SQLDateCompiler, SQLCompiler):
  pass


class SQLDateTimeCompiler(compiler.SQLDateTimeCompiler, SQLCompiler):
  pass
