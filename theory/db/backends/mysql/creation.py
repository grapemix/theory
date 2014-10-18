from theory.db.backends.creation import BaseDatabaseCreation


class DatabaseCreation(BaseDatabaseCreation):
  # This dictionary maps Field objects to their associated MySQL column
  # types, as strings. Column-type strings can contain format strings; they'll
  # be interpolated against the values of Field.__dict__ before being output.
  # If a column type is set to None, it won't be included in the output.
  dataTypes = {
    'AutoField': 'integer AUTO_INCREMENT',
    'BinaryField': 'longblob',
    'BooleanField': 'bool',
    'CharField': 'varchar(%(maxLength)s)',
    'CommaSeparatedIntegerField': 'varchar(%(maxLength)s)',
    'DateField': 'date',
    'DateTimeField': 'datetime',
    'DecimalField': 'numeric(%(maxDigits)s, %(decimalPlaces)s)',
    'FileField': 'varchar(%(maxLength)s)',
    'FilePathField': 'varchar(%(maxLength)s)',
    'FloatField': 'double precision',
    'IntegerField': 'integer',
    'BigIntegerField': 'bigint',
    'IPAddressField': 'char(15)',
    'GenericIPAddressField': 'char(39)',
    'NullBooleanField': 'bool',
    'OneToOneField': 'integer',
    'PositiveIntegerField': 'integer UNSIGNED',
    'PositiveSmallIntegerField': 'smallint UNSIGNED',
    'SlugField': 'varchar(%(maxLength)s)',
    'SmallIntegerField': 'smallint',
    'TextField': 'longtext',
    'TimeField': 'time',
  }

  def sqlTableCreationSuffix(self):
    suffix = []
    testSettings = self.connection.settingsDict['TEST']
    if testSettings['CHARSET']:
      suffix.append('CHARACTER SET %s' % testSettings['CHARSET'])
    if testSettings['COLLATION']:
      suffix.append('COLLATE %s' % testSettings['COLLATION'])
    return ' '.join(suffix)

  def sqlForInlineForeignKeyReferences(self, modal, field, knownModels, style):
    "All inline references are pending under MySQL"
    return [], True

  def sqlDestroyIndexesForFields(self, modal, fields, style):
    if len(fields) == 1 and fields[0].dbTablespace:
      tablespaceSql = self.connection.ops.tablespaceSql(fields[0].dbTablespace)
    elif modal._meta.dbTablespace:
      tablespaceSql = self.connection.ops.tablespaceSql(modal._meta.dbTablespace)
    else:
      tablespaceSql = ""
    if tablespaceSql:
      tablespaceSql = " " + tablespaceSql

    fieldNames = []
    qn = self.connection.ops.quoteName
    for f in fields:
      fieldNames.append(style.SQL_FIELD(qn(f.column)))

    indexName = "%s_%s" % (modal._meta.dbTable, self._digest([f.name for f in fields]))

    from ..utils import truncateName

    return [
      style.SQL_KEYWORD("DROP INDEX") + " " +
      style.SQL_TABLE(qn(truncateName(indexName, self.connection.ops.maxNameLength()))) + " " +
      style.SQL_KEYWORD("ON") + " " +
      style.SQL_TABLE(qn(modal._meta.dbTable)) + ";",
    ]
