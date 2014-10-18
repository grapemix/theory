from theory.db.backends.creation import BaseDatabaseCreation
from theory.db.backends.utils import truncateName


class DatabaseCreation(BaseDatabaseCreation):
  # This dictionary maps Field objects to their associated PostgreSQL column
  # types, as strings. Column-type strings can contain format strings; they'll
  # be interpolated against the values of Field.__dict__ before being output.
  # If a column type is set to None, it won't be included in the output.
  dataTypes = {
    'AutoField': 'serial',
    'BinaryField': 'bytea',
    'BooleanField': 'boolean',
    'CharField': 'varchar(%(maxLength)s)',
    'CommaSeparatedIntegerField': 'varchar(%(maxLength)s)',
    'DateField': 'date',
    'DateTimeField': 'timestamp with time zone',
    'DecimalField': 'numeric(%(maxDigits)s, %(decimalPlaces)s)',
    'FileField': 'varchar(%(maxLength)s)',
    'FilePathField': 'varchar(%(maxLength)s)',
    'FloatField': 'double precision',
    'IntegerField': 'integer',
    'BigIntegerField': 'bigint',
    'IPAddressField': 'inet',
    'GenericIPAddressField': 'inet',
    'NullBooleanField': 'boolean',
    'OneToOneField': 'integer',
    'PositiveIntegerField': 'integer',
    'PositiveSmallIntegerField': 'smallint',
    'SlugField': 'varchar(%(maxLength)s)',
    'SmallIntegerField': 'smallint',
    'TextField': 'text',
    'TimeField': 'time',
  }

  dataTypeCheckConstraints = {
    'PositiveIntegerField': '"%(column)s" >= 0',
    'PositiveSmallIntegerField': '"%(column)s" >= 0',
  }

  def sqlTableCreationSuffix(self):
    testSettings = self.connection.settingsDict['TEST']
    assert testSettings['COLLATION'] is None, "PostgreSQL does not support collation setting at database creation time."
    if testSettings['CHARSET']:
      return "WITH ENCODING '%s'" % testSettings['CHARSET']
    return ''

  def sqlIndexesForField(self, modal, f, style):
    output = []
    dbType = f.dbType(connection=self.connection)
    if dbType is not None and (f.dbIndex or f.unique):
      qn = self.connection.ops.quoteName
      dbTable = modal._meta.dbTable
      tablespace = f.dbTablespace or modal._meta.dbTablespace
      if tablespace:
        tablespaceSql = self.connection.ops.tablespaceSql(tablespace)
        if tablespaceSql:
          tablespaceSql = ' ' + tablespaceSql
      else:
        tablespaceSql = ''

      def getIndexSql(indexName, opclass=''):
        return (style.SQL_KEYWORD('CREATE INDEX') + ' ' +
            style.SQL_TABLE(qn(truncateName(indexName, self.connection.ops.maxNameLength()))) + ' ' +
            style.SQL_KEYWORD('ON') + ' ' +
            style.SQL_TABLE(qn(dbTable)) + ' ' +
            "(%s%s)" % (style.SQL_FIELD(qn(f.column)), opclass) +
            "%s;" % tablespaceSql)

      if not f.unique:
        output = [getIndexSql('%s_%s' % (dbTable, f.column))]

      # Fields with database column types of `varchar` and `text` need
      # a second index that specifies their operator class, which is
      # needed when performing correct LIKE queries outside the
      # C locale. See #12234.
      if dbType.startswith('varchar'):
        output.append(getIndexSql('%s_%sLike' % (dbTable, f.column),
                      ' varcharPatternOps'))
      elif dbType.startswith('text'):
        output.append(getIndexSql('%s_%sLike' % (dbTable, f.column),
                      ' textPatternOps'))
    return output
