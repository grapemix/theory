import re

import cx_Oracle

from theory.db.backends import BaseDatabaseIntrospection, FieldInfo
from theory.utils.encoding import forceText

foreignKeyRe = re.compile(r"\sCONSTRAINT `[^`]*` FOREIGN KEY \(`([^`]*)`\) REFERENCES `([^`]*)` \(`([^`]*)`\)")


class DatabaseIntrospection(BaseDatabaseIntrospection):
  # Maps type objects to Theory Field types.
  dataTypesReverse = {
    cx_Oracle.BLOB: 'BinaryField',
    cx_Oracle.CLOB: 'TextField',
    cx_Oracle.DATETIME: 'DateField',
    cx_Oracle.FIXED_CHAR: 'CharField',
    cx_Oracle.NCLOB: 'TextField',
    cx_Oracle.NUMBER: 'DecimalField',
    cx_Oracle.STRING: 'CharField',
    cx_Oracle.TIMESTAMP: 'DateTimeField',
  }

  try:
    dataTypesReverse[cx_Oracle.NATIVE_FLOAT] = 'FloatField'
  except AttributeError:
    pass

  try:
    dataTypesReverse[cx_Oracle.UNICODE] = 'CharField'
  except AttributeError:
    pass

  def getFieldType(self, dataType, description):
    # If it's a NUMBER with scale == 0, consider it an IntegerField
    if dataType == cx_Oracle.NUMBER:
      precision, scale = description[4:6]
      if scale == 0:
        if precision > 11:
          return 'BigIntegerField'
        elif precision == 1:
          return 'BooleanField'
        else:
          return 'IntegerField'
      elif scale == -127:
        return 'FloatField'

    return super(DatabaseIntrospection, self).getFieldType(dataType, description)

  def getTableList(self, cursor):
    "Returns a list of table names in the current database."
    cursor.execute("SELECT TABLE_NAME FROM USER_TABLES")
    return [row[0].lower() for row in cursor.fetchall()]

  def getTableDescription(self, cursor, tableName):
    "Returns a description of the table, with the DB-API cursor.description interface."
    cursor.execute("SELECT * FROM %s WHERE ROWNUM < 2" % self.connection.ops.quoteName(tableName))
    description = []
    for desc in cursor.description:
      name = forceText(desc[0])  # cx_Oracle always returns a 'str' on both Python 2 and 3
      name = name % {}  # cx_Oracle, for some reason, doubles percent signs.
      description.append(FieldInfo(*(name.lower(),) + desc[1:]))
    return description

  def tableNameConverter(self, name):
    "Table name comparison is case insensitive under Oracle"
    return name.lower()

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
    tableName = tableName.upper()
    cursor.execute("""
  SELECT ta.columnId - 1, tb.tableName, tb.columnId - 1
  FROM   userConstraints, USER_CONS_COLUMNS ca, USER_CONS_COLUMNS cb,
      userTabCols ta, userTabCols tb
  WHERE  userConstraints.tableName = %s AND
      ta.tableName = userConstraints.tableName AND
      ta.columnName = ca.columnName AND
      ca.tableName = ta.tableName AND
      userConstraints.constraintName = ca.constraintName AND
      userConstraints.rConstraintName = cb.constraintName AND
      cb.tableName = tb.tableName AND
      cb.columnName = tb.columnName AND
      ca.position = cb.position""", [tableName])

    relations = {}
    for row in cursor.fetchall():
      relations[row[0]] = (row[2], row[1].lower())
    return relations

  def getKeyColumns(self, cursor, tableName):
    cursor.execute("""
      SELECT ccol.columnName, rcol.tableName AS referencedTable, rcol.columnName AS referencedColumn
      FROM userConstraints c
      JOIN userConsColumns ccol
       ON ccol.constraintName = c.constraintName
      JOIN userConsColumns rcol
       ON rcol.constraintName = c.rConstraintName
      WHERE c.tableName = %s AND c.constraintType = 'R'""", [tableName.upper()])
    return [tuple(cell.lower() for cell in row)
        for row in cursor.fetchall()]

  def getIndexes(self, cursor, tableName):
    sql = """
  SELECT LOWER(uic1.columnName) AS columnName,
      CASE userConstraints.constraintType
        WHEN 'P' THEN 1 ELSE 0
      END AS isPrimaryKey,
      CASE userIndexes.uniqueness
        WHEN 'UNIQUE' THEN 1 ELSE 0
      END AS isUnique
  FROM   userConstraints, userIndexes, userIndColumns uic1
  WHERE  userConstraints.constraintType (+) = 'P'
   AND  userConstraints.indexName (+) = uic1.indexName
   AND  userIndexes.uniqueness (+) = 'UNIQUE'
   AND  userIndexes.indexName (+) = uic1.indexName
   AND  uic1.tableName = UPPER(%s)
   AND  uic1.columnPosition = 1
   AND  NOT EXISTS (
       SELECT 1
       FROM   userIndColumns uic2
       WHERE  uic2.indexName = uic1.indexName
        AND  uic2.columnPosition = 2
      )
    """
    cursor.execute(sql, [tableName])
    indexes = {}
    for row in cursor.fetchall():
      indexes[row[0]] = {'primaryKey': bool(row[1]),
                'unique': bool(row[2])}
    return indexes

  def getConstraints(self, cursor, tableName):
    """
    Retrieves any constraints or keys (unique, pk, fk, check, index) across one or more columns.
    """
    constraints = {}
    # Loop over the constraints, getting PKs and uniques
    cursor.execute("""
      SELECT
        userConstraints.constraintName,
        LOWER(cols.columnName) AS columnName,
        CASE userConstraints.constraintType
          WHEN 'P' THEN 1
          ELSE 0
        END AS isPrimaryKey,
        CASE userIndexes.uniqueness
          WHEN 'UNIQUE' THEN 1
          ELSE 0
        END AS isUnique,
        CASE userConstraints.constraintType
          WHEN 'C' THEN 1
          ELSE 0
        END AS isCheckConstraint
      FROM
        userConstraints
      INNER JOIN
        userIndexes ON userIndexes.indexName = userConstraints.indexName
      LEFT OUTER JOIN
        userConsColumns cols ON userConstraints.constraintName = cols.constraintName
      WHERE
        (
          userConstraints.constraintType = 'P' OR
          userConstraints.constraintType = 'U'
        )
        AND userConstraints.tableName = UPPER(%s)
      ORDER BY cols.position
    """, [tableName])
    for constraint, column, pk, unique, check in cursor.fetchall():
      # If we're the first column, make the record
      if constraint not in constraints:
        constraints[constraint] = {
          "columns": [],
          "primaryKey": pk,
          "unique": unique,
          "foreignKey": None,
          "check": check,
          "index": True,  # All P and U come with index, see inner join above
        }
      # Record the details
      constraints[constraint]['columns'].append(column)
    # Check constraints
    cursor.execute("""
      SELECT
        cons.constraintName,
        LOWER(cols.columnName) AS columnName
      FROM
        userConstraints cons
      LEFT OUTER JOIN
        userConsColumns cols ON cons.constraintName = cols.constraintName
      WHERE
        cons.constraintType = 'C' AND
        cons.tableName = UPPER(%s)
      ORDER BY cols.position
    """, [tableName])
    for constraint, column in cursor.fetchall():
      # If we're the first column, make the record
      if constraint not in constraints:
        constraints[constraint] = {
          "columns": [],
          "primaryKey": False,
          "unique": False,
          "foreignKey": None,
          "check": True,
          "index": False,
        }
      # Record the details
      constraints[constraint]['columns'].append(column)
    # Foreign key constraints
    cursor.execute("""
      SELECT
        cons.constraintName,
        LOWER(cols.columnName) AS columnName,
        LOWER(rcons.tableName),
        LOWER(rcols.columnName)
      FROM
        userConstraints cons
      INNER JOIN
        userConstraints rcons ON cons.rConstraintName = rcons.constraintName
      INNER JOIN
        userConsColumns rcols ON rcols.constraintName = rcons.constraintName
      LEFT OUTER JOIN
        userConsColumns cols ON cons.constraintName = cols.constraintName
      WHERE
        cons.constraintType = 'R' AND
        cons.tableName = UPPER(%s)
      ORDER BY cols.position
    """, [tableName])
    for constraint, column, otherTable, otherColumn in cursor.fetchall():
      # If we're the first column, make the record
      if constraint not in constraints:
        constraints[constraint] = {
          "columns": [],
          "primaryKey": False,
          "unique": False,
          "foreignKey": (otherTable, otherColumn),
          "check": False,
          "index": False,
        }
      # Record the details
      constraints[constraint]['columns'].append(column)
    # Now get indexes
    cursor.execute("""
      SELECT
        indexName,
        LOWER(columnName)
      FROM
        userIndColumns cols
      WHERE
        tableName = UPPER(%s) AND
        NOT EXISTS (
          SELECT 1
          FROM userConstraints cons
          WHERE cols.indexName = cons.indexName
        )
      ORDER BY cols.columnPosition
    """, [tableName])
    for constraint, column in cursor.fetchall():
      # If we're the first column, make the record
      if constraint not in constraints:
        constraints[constraint] = {
          "columns": [],
          "primaryKey": False,
          "unique": False,
          "foreignKey": None,
          "check": False,
          "index": True,
        }
      # Record the details
      constraints[constraint]['columns'].append(column)
    return constraints
