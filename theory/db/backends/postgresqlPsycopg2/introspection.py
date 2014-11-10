from __future__ import unicode_literals

from theory.db.backends import BaseDatabaseIntrospection, FieldInfo
from theory.utils.encoding import forceText


class DatabaseIntrospection(BaseDatabaseIntrospection):
  # Maps type codes to Theory Field types.
  dataTypesReverse = {
    16: 'BooleanField',
    17: 'BinaryField',
    20: 'BigIntegerField',
    21: 'SmallIntegerField',
    23: 'IntegerField',
    25: 'TextField',
    700: 'FloatField',
    701: 'FloatField',
    869: 'GenericIPAddressField',
    1042: 'CharField',  # blank-padded
    1043: 'CharField',
    1082: 'DateField',
    1083: 'TimeField',
    1114: 'DateTimeField',
    1184: 'DateTimeField',
    1266: 'TimeField',
    1700: 'DecimalField',
  }

  ignoredTables = []

  def getTableList(self, cursor):
    "Returns a list of table names in the current database."
    cursor.execute("""
      SELECT c.relname
      FROM pg_catalog.pg_class c
      LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relkind IN ('r', 'v', '')
        AND n.nspname NOT IN ('pg_catalog', 'pgToast')
        AND pg_catalog.pg_table_is_visible(c.oid)""")
    return [row[0] for row in cursor.fetchall() if row[0] not in self.ignoredTables]

  def getTableDescription(self, cursor, tableName):
    "Returns a description of the table, with the DB-API cursor.description interface."
    # As cursor.description does not return reliably the nullable property,
    # we have to query the informationSchema (#7783)
    cursor.execute("""
      SELECT columnName, isNullable
      FROM informationSchema.columns
      WHERE tableName = %s""", [tableName])
    nullMap = dict(cursor.fetchall())
    cursor.execute("SELECT * FROM %s LIMIT 1" % self.connection.ops.quoteName(tableName))
    return [FieldInfo(*((forceText(line[0]),) + line[1:6] + (nullMap[forceText(line[0])] == 'YES',)))
        for line in cursor.description]

  def getRelations(self, cursor, tableName):
    """
    Returns a dictionary of {fieldIndex: (fieldIndexOtherTable, otherTable)}
    representing all relationships to the given table. Indexes are 0-based.
    """
    cursor.execute("""
      SELECT con.conkey, con.confkey, c2.relname
      FROM pgConstraint con, pg_class c1, pg_class c2
      WHERE c1.oid = con.conrelid
        AND c2.oid = con.confrelid
        AND c1.relname = %s
        AND con.contype = 'f'""", [tableName])
    relations = {}
    for row in cursor.fetchall():
      # row[0] and row[1] are single-item lists, so grab the single item.
      relations[row[0][0] - 1] = (row[1][0] - 1, row[2])
    return relations

  def getKeyColumns(self, cursor, tableName):
    keyColumns = []
    cursor.execute("""
      SELECT kcu.columnName, ccu.tableName AS referencedTable, ccu.columnName AS referencedColumn
      FROM informationSchema.constraintColumnUsage ccu
      LEFT JOIN informationSchema.keyColumnUsage kcu
        ON ccu.constraintCatalog = kcu.constraintCatalog
          AND ccu.constraintSchema = kcu.constraintSchema
          AND ccu.constraintName = kcu.constraintName
      LEFT JOIN informationSchema.tableConstraints tc
        ON ccu.constraintCatalog = tc.constraintCatalog
          AND ccu.constraintSchema = tc.constraintSchema
          AND ccu.constraintName = tc.constraintName
      WHERE kcu.tableName = %s AND tc.constraintType = 'FOREIGN KEY'""", [tableName])
    keyColumns.extend(cursor.fetchall())
    return keyColumns

  def getIndexes(self, cursor, tableName):
    # This query retrieves each index on the given table, including the
    # first associated field name
    cursor.execute("""
      SELECT attr.attname, idx.indkey, idx.indisunique, idx.indisprimary
      FROM pg_catalog.pg_class c, pg_catalog.pg_class c2,
        pg_catalog.pgIndex idx, pg_catalog.pgAttribute attr
      WHERE c.oid = idx.indrelid
        AND idx.indexrelid = c2.oid
        AND attr.attrelid = c.oid
        AND attr.attnum = idx.indkey[0]
        AND c.relname = %s""", [tableName])
    indexes = {}
    for row in cursor.fetchall():
      # row[1] (idx.indkey) is stored in the DB as an array. It comes out as
      # a string of space-separated integers. This designates the field
      # indexes (1-based) of the fields that have indexes on the table.
      # Here, we skip any indexes across multiple fields.
      if ' ' in row[1]:
        continue
      if row[0] not in indexes:
        indexes[row[0]] = {'primaryKey': False, 'unique': False}
      # It's possible to have the unique and PK constraints in separate indexes.
      if row[3]:
        indexes[row[0]]['primaryKey'] = True
      if row[2]:
        indexes[row[0]]['unique'] = True
    return indexes

  def getConstraints(self, cursor, tableName):
    """
    Retrieves any constraints or keys (unique, pk, fk, check, index) across one or more columns.
    """
    constraints = {}
    # Loop over the key table, collecting things as constraints
    # This will get PKs, FKs, and uniques, but not CHECK
    cursor.execute("""
      SELECT
        kc.constraintName,
        kc.columnName,
        c.constraintType,
        array(SELECT tableName::text || '.' || columnName::text FROM informationSchema.constraintColumnUsage WHERE constraintName = kc.constraintName)
      FROM informationSchema.keyColumnUsage AS kc
      JOIN informationSchema.tableConstraints AS c ON
        kc.tableSchema = c.tableSchema AND
        kc.tableName = c.tableName AND
        kc.constraintName = c.constraintName
      WHERE
        kc.tableSchema = %s AND
        kc.tableName = %s
      ORDER BY kc.ordinalPosition ASC
    """, ["public", tableName])
    for constraint, column, kind, usedCols in cursor.fetchall():
      # If we're the first column, make the record
      if constraint not in constraints:
        constraints[constraint] = {
          "columns": [],
          "primaryKey": kind.lower() == "primary key",
          "unique": kind.lower() in ["primary key", "unique"],
          "foreignKey": tuple(usedCols[0].split(".", 1)) if kind.lower() == "foreign key" else None,
          "check": False,
          "index": False,
        }
      # Record the details
      constraints[constraint]['columns'].append(column)
    # Now get CHECK constraint columns
    cursor.execute("""
      SELECT kc.constraintName, kc.columnName
      FROM informationSchema.constraintColumnUsage AS kc
      JOIN informationSchema.tableConstraints AS c ON
        kc.tableSchema = c.tableSchema AND
        kc.tableName = c.tableName AND
        kc.constraintName = c.constraintName
      WHERE
        c.constraintType = 'CHECK' AND
        kc.tableSchema = %s AND
        kc.tableName = %s
    """, ["public", tableName])
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
    # Now get indexes
    cursor.execute("""
      SELECT
        c2.relname,
        ARRAY(
          SELECT (SELECT attname FROM pg_catalog.pgAttribute WHERE attnum = i AND attrelid = c.oid)
          FROM unnest(idx.indkey) i
        ),
        idx.indisunique,
        idx.indisprimary
      FROM pg_catalog.pg_class c, pg_catalog.pg_class c2,
        pg_catalog.pgIndex idx
      WHERE c.oid = idx.indrelid
        AND idx.indexrelid = c2.oid
        AND c.relname = %s
    """, [tableName])
    for index, columns, unique, primary in cursor.fetchall():
      if index not in constraints:
        constraints[index] = {
          "columns": list(columns),
          "primaryKey": primary,
          "unique": unique,
          "foreignKey": None,
          "check": False,
          "index": True,
        }
    return constraints
