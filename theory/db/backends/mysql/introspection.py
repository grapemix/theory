import re
from .base import FIELD_TYPE
from theory.utils.datastructures import OrderedSet
from theory.db.backends import BaseDatabaseIntrospection, FieldInfo
from theory.utils.encoding import forceText


foreignKeyRe = re.compile(r"\sCONSTRAINT `[^`]*` FOREIGN KEY \(`([^`]*)`\) REFERENCES `([^`]*)` \(`([^`]*)`\)")


class DatabaseIntrospection(BaseDatabaseIntrospection):
  dataTypesReverse = {
    FIELD_TYPE.BLOB: 'TextField',
    FIELD_TYPE.CHAR: 'CharField',
    FIELD_TYPE.DECIMAL: 'DecimalField',
    FIELD_TYPE.NEWDECIMAL: 'DecimalField',
    FIELD_TYPE.DATE: 'DateField',
    FIELD_TYPE.DATETIME: 'DateTimeField',
    FIELD_TYPE.DOUBLE: 'FloatField',
    FIELD_TYPE.FLOAT: 'FloatField',
    FIELD_TYPE.INT24: 'IntegerField',
    FIELD_TYPE.LONG: 'IntegerField',
    FIELD_TYPE.LONGLONG: 'BigIntegerField',
    FIELD_TYPE.SHORT: 'IntegerField',
    FIELD_TYPE.STRING: 'CharField',
    FIELD_TYPE.TIME: 'TimeField',
    FIELD_TYPE.TIMESTAMP: 'DateTimeField',
    FIELD_TYPE.TINY: 'IntegerField',
    FIELD_TYPE.TINY_BLOB: 'TextField',
    FIELD_TYPE.MEDIUM_BLOB: 'TextField',
    FIELD_TYPE.LONG_BLOB: 'TextField',
    FIELD_TYPE.VAR_STRING: 'CharField',
  }

  def getTableList(self, cursor):
    "Returns a list of table names in the current database."
    cursor.execute("SHOW TABLES")
    return [row[0] for row in cursor.fetchall()]

  def getTableDescription(self, cursor, tableName):
    """
    Returns a description of the table, with the DB-API cursor.description interface."
    """
    # varchar length returned by cursor.description is an internal length,
    # not visible length (#5725), use informationSchema database to fix this
    cursor.execute("""
      SELECT columnName, characterMaximumLength FROM informationSchema.columns
      WHERE tableName = %s AND tableSchema = DATABASE()
        AND characterMaximumLength IS NOT NULL""", [tableName])
    lengthMap = dict(cursor.fetchall())

    # Also getting precision and scale from informationSchema (see #5014)
    cursor.execute("""
      SELECT columnName, numericPrecision, numericScale FROM informationSchema.columns
      WHERE tableName = %s AND tableSchema = DATABASE()
        AND dataType='decimal'""", [tableName])
    numericMap = dict((line[0], tuple(int(n) for n in line[1:])) for line in cursor.fetchall())

    cursor.execute("SELECT * FROM %s LIMIT 1" % self.connection.ops.quoteName(tableName))
    return [FieldInfo(*((forceText(line[0]),)
              + line[1:3]
              + (lengthMap.get(line[0], line[3]),)
              + numericMap.get(line[0], line[4:6])
              + (line[6],)))
      for line in cursor.description]

  def _nameToIndex(self, cursor, tableName):
    """
    Returns a dictionary of {fieldName: fieldIndex} for the given table.
    Indexes are 0-based.
    """
    return dict((d[0], i) for i, d in enumerate(self.getTableDescription(cursor, tableName)))

  def getRelations(self, cursor, tableName):
    """
    Returns a dictionary of {fieldIndex: (fieldIndexOtherTable, otherTable)}
    representing all relationships to the given table. Indexes are 0-based.
    """
    myFieldDict = self._nameToIndex(cursor, tableName)
    constraints = self.getKeyColumns(cursor, tableName)
    relations = {}
    for myFieldname, otherTable, otherField in constraints:
      otherFieldIndex = self._nameToIndex(cursor, otherTable)[otherField]
      myFieldIndex = myFieldDict[myFieldname]
      relations[myFieldIndex] = (otherFieldIndex, otherTable)
    return relations

  def getKeyColumns(self, cursor, tableName):
    """
    Returns a list of (columnName, referencedTableName, referencedColumnName) for all
    key columns in given table.
    """
    keyColumns = []
    cursor.execute("""
      SELECT columnName, referencedTableName, referencedColumnName
      FROM informationSchema.keyColumnUsage
      WHERE tableName = %s
        AND tableSchema = DATABASE()
        AND referencedTableName IS NOT NULL
        AND referencedColumnName IS NOT NULL""", [tableName])
    keyColumns.extend(cursor.fetchall())
    return keyColumns

  def getIndexes(self, cursor, tableName):
    cursor.execute("SHOW INDEX FROM %s" % self.connection.ops.quoteName(tableName))
    # Do a two-pass search for indexes: on first pass check which indexes
    # are multicolumn, on second pass check which single-column indexes
    # are present.
    rows = list(cursor.fetchall())
    multicolIndexes = set()
    for row in rows:
      if row[3] > 1:
        multicolIndexes.add(row[2])
    indexes = {}
    for row in rows:
      if row[2] in multicolIndexes:
        continue
      if row[4] not in indexes:
        indexes[row[4]] = {'primaryKey': False, 'unique': False}
      # It's possible to have the unique and PK constraints in separate indexes.
      if row[2] == 'PRIMARY':
        indexes[row[4]]['primaryKey'] = True
      if not row[1]:
        indexes[row[4]]['unique'] = True
    return indexes

  def getConstraints(self, cursor, tableName):
    """
    Retrieves any constraints or keys (unique, pk, fk, check, index) across one or more columns.
    """
    constraints = {}
    # Get the actual constraint names and columns
    nameQuery = """
      SELECT kc.`constraintName`, kc.`columnName`,
        kc.`referencedTableName`, kc.`referencedColumnName`
      FROM informationSchema.keyColumnUsage AS kc
      WHERE
        kc.tableSchema = %s AND
        kc.tableName = %s
    """
    cursor.execute(nameQuery, [self.connection.settingsDict['NAME'], tableName])
    for constraint, column, refTable, refColumn in cursor.fetchall():
      if constraint not in constraints:
        constraints[constraint] = {
          'columns': OrderedSet(),
          'primaryKey': False,
          'unique': False,
          'index': False,
          'check': False,
          'foreignKey': (refTable, refColumn) if refColumn else None,
        }
      constraints[constraint]['columns'].add(column)
    # Now get the constraint types
    typeQuery = """
      SELECT c.constraintName, c.constraintType
      FROM informationSchema.tableConstraints AS c
      WHERE
        c.tableSchema = %s AND
        c.tableName = %s
    """
    cursor.execute(typeQuery, [self.connection.settingsDict['NAME'], tableName])
    for constraint, kind in cursor.fetchall():
      if kind.lower() == "primary key":
        constraints[constraint]['primaryKey'] = True
        constraints[constraint]['unique'] = True
      elif kind.lower() == "unique":
        constraints[constraint]['unique'] = True
    # Now add in the indexes
    cursor.execute("SHOW INDEX FROM %s" % self.connection.ops.quoteName(tableName))
    for table, nonUnique, index, colseq, column in [x[:5] for x in cursor.fetchall()]:
      if index not in constraints:
        constraints[index] = {
          'columns': OrderedSet(),
          'primaryKey': False,
          'unique': False,
          'index': True,
          'check': False,
          'foreignKey': None,
        }
      constraints[index]['index'] = True
      constraints[index]['columns'].add(column)
    # Convert the sorted sets to lists
    for constraint in constraints.values():
      constraint['columns'] = list(constraint['columns'])
    return constraints
