from theory.db.model.sql import compiler
from theory.utils.six.moves import zipLongest


class SQLCompiler(compiler.SQLCompiler):
  def resolveColumns(self, row, fields=()):
    values = []
    indexExtraSelect = len(self.query.extraSelect)
    for value, field in zipLongest(row[indexExtraSelect:], fields):
      if (field and field.getInternalType() in ("BooleanField", "NullBooleanField") and
          value in (0, 1)):
        value = bool(value)
      values.append(value)
    return row[:indexExtraSelect] + tuple(values)

  def asSubqueryCondition(self, alias, columns, qn):
    qn2 = self.connection.ops.quoteName
    sql, params = self.asSql()
    return '(%s) IN (%s)' % (', '.join('%s.%s' % (qn(alias), qn2(column)) for column in columns), sql), params


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
