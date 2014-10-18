import re

from theory.db.backends import BaseDatabaseIntrospection, FieldInfo


fieldSizeRe = re.compile(r'^\s*(?:var)?char\s*\(\s*(\d+)\s*\)\s*$')


def getFieldSize(name):
  """ Extract the size number from a "varchar(11)" type name """
  m = fieldSizeRe.search(name)
  return int(m.group(1)) if m else None


# This light wrapper "fakes" a dictionary interface, because some SQLite data
# types include variables in them -- e.g. "varchar(30)" -- and can't be matched
# as a simple dictionary lookup.
class FlexibleFieldLookupDict(object):
  # Maps SQL types to Theory Field types. Some of the SQL types have multiple
  # entries here because SQLite allows for anything and doesn't normalize the
  # field type; it uses whatever was given.
  baseDataTypesReverse = {
    'bool': 'BooleanField',
    'boolean': 'BooleanField',
    'smallint': 'SmallIntegerField',
    'smallint unsigned': 'PositiveSmallIntegerField',
    'smallinteger': 'SmallIntegerField',
    'int': 'IntegerField',
    'integer': 'IntegerField',
    'bigint': 'BigIntegerField',
    'integer unsigned': 'PositiveIntegerField',
    'decimal': 'DecimalField',
    'real': 'FloatField',
    'text': 'TextField',
    'char': 'CharField',
    'blob': 'BinaryField',
    'date': 'DateField',
    'datetime': 'DateTimeField',
    'time': 'TimeField',
  }

  def __getitem__(self, key):
    key = key.lower()
    try:
      return self.baseDataTypesReverse[key]
    except KeyError:
      size = getFieldSize(key)
      if size is not None:
        return ('CharField', {'maxLength': size})
      raise KeyError


class DatabaseIntrospection(BaseDatabaseIntrospection):
  dataTypesReverse = FlexibleFieldLookupDict()

  def getTableList(self, cursor):
    "Returns a list of table names in the current database."
    # Skip the sqliteSequence system table used for autoincrement key
    # generation.
    cursor.execute("""
      SELECT name FROM sqliteMaster
      WHERE type in ('table', 'view') AND NOT name='sqliteSequence'
      ORDER BY name""")
    return [row[0] for row in cursor.fetchall()]

  def getTableDescription(self, cursor, tableName):
    "Returns a description of the table, with the DB-API cursor.description interface."
    return [FieldInfo(info['name'], info['type'], None, info['size'], None, None,
         info['nullOk']) for info in self._tableInfo(cursor, tableName)]

  def getRelations(self, cursor, tableName):
    """
    Returns a dictionary of {fieldIndex: (fieldIndexOtherTable, otherTable)}
    representing all relationships to the given table. Indexes are 0-based.
    """

    # Dictionary of relations to return
    relations = {}

    # Schema for this table
    cursor.execute("SELECT sql FROM sqliteMaster WHERE tblName = %s AND type = %s", [tableName, "table"])
    try:
      results = cursor.fetchone()[0].strip()
    except TypeError:
      # It might be a view, then no results will be returned
      return relations
    results = results[results.index('(') + 1:results.rindex(')')]

    # Walk through and look for references to other tables. SQLite doesn't
    # really have enforced references, but since it echoes out the SQL used
    # to create the table we can look for REFERENCES statements used there.
    for fieldIndex, fieldDesc in enumerate(results.split(',')):
      fieldDesc = fieldDesc.strip()
      if fieldDesc.startswith("UNIQUE"):
        continue

      m = re.search('references (.*) \(["|](.*)["|]\)', fieldDesc, re.I)
      if not m:
        continue

      table, column = [s.strip('"') for s in m.groups()]

      cursor.execute("SELECT sql FROM sqliteMaster WHERE tblName = %s", [table])
      result = cursor.fetchall()[0]
      otherTableResults = result[0].strip()
      li, ri = otherTableResults.index('('), otherTableResults.rindex(')')
      otherTableResults = otherTableResults[li + 1:ri]

      for otherIndex, otherDesc in enumerate(otherTableResults.split(',')):
        otherDesc = otherDesc.strip()
        if otherDesc.startswith('UNIQUE'):
          continue

        name = otherDesc.split(' ', 1)[0].strip('"')
        if name == column:
          relations[fieldIndex] = (otherIndex, table)
          break

    return relations

  def getKeyColumns(self, cursor, tableName):
    """
    Returns a list of (columnName, referencedTableName, referencedColumnName) for all
    key columns in given table.
    """
    keyColumns = []

    # Schema for this table
    cursor.execute("SELECT sql FROM sqliteMaster WHERE tblName = %s AND type = %s", [tableName, "table"])
    results = cursor.fetchone()[0].strip()
    results = results[results.index('(') + 1:results.rindex(')')]

    # Walk through and look for references to other tables. SQLite doesn't
    # really have enforced references, but since it echoes out the SQL used
    # to create the table we can look for REFERENCES statements used there.
    for fieldIndex, fieldDesc in enumerate(results.split(',')):
      fieldDesc = fieldDesc.strip()
      if fieldDesc.startswith("UNIQUE"):
        continue

      m = re.search('"(.*)".*references (.*) \(["|](.*)["|]\)', fieldDesc, re.I)
      if not m:
        continue

      # This will append (columnName, referencedTableName, referencedColumnName) to keyColumns
      keyColumns.append(tuple(s.strip('"') for s in m.groups()))

    return keyColumns

  def getIndexes(self, cursor, tableName):
    indexes = {}
    for info in self._tableInfo(cursor, tableName):
      if info['pk'] != 0:
        indexes[info['name']] = {'primaryKey': True,
                     'unique': False}
    cursor.execute('PRAGMA indexList(%s)' % self.connection.ops.quoteName(tableName))
    # seq, name, unique
    for index, unique in [(field[1], field[2]) for field in cursor.fetchall()]:
      cursor.execute('PRAGMA indexInfo(%s)' % self.connection.ops.quoteName(index))
      info = cursor.fetchall()
      # Skip indexes across multiple fields
      if len(info) != 1:
        continue
      name = info[0][2]  # seqno, cid, name
      indexes[name] = {'primaryKey': indexes.get(name, {}).get("primaryKey", False),
               'unique': unique}
    return indexes

  def getPrimaryKeyColumn(self, cursor, tableName):
    """
    Get the column name of the primary key for the given table.
    """
    # Don't use PRAGMA because that causes issues with some transactions
    cursor.execute("SELECT sql FROM sqliteMaster WHERE tblName = %s AND type = %s", [tableName, "table"])
    row = cursor.fetchone()
    if row is None:
      raise ValueError("Table %s does not exist" % tableName)
    results = row[0].strip()
    results = results[results.index('(') + 1:results.rindex(')')]
    for fieldDesc in results.split(','):
      fieldDesc = fieldDesc.strip()
      m = re.search('"(.*)".*PRIMARY KEY( AUTOINCREMENT)?$', fieldDesc)
      if m:
        return m.groups()[0]
    return None

  def _tableInfo(self, cursor, name):
    cursor.execute('PRAGMA tableInfo(%s)' % self.connection.ops.quoteName(name))
    # cid, name, type, notnull, dfltValue, pk
    return [{'name': field[1],
         'type': field[2],
         'size': getFieldSize(field[2]),
         'nullOk': not field[3],
         'pk': field[5]     # undocumented
         } for field in cursor.fetchall()]

  def getConstraints(self, cursor, tableName):
    """
    Retrieves any constraints or keys (unique, pk, fk, check, index) across one or more columns.
    """
    constraints = {}
    # Get the index info
    cursor.execute("PRAGMA indexList(%s)" % self.connection.ops.quoteName(tableName))
    for number, index, unique in cursor.fetchall():
      # Get the index info for that index
      cursor.execute('PRAGMA indexInfo(%s)' % self.connection.ops.quoteName(index))
      for indexRank, columnRank, column in cursor.fetchall():
        if index not in constraints:
          constraints[index] = {
            "columns": [],
            "primaryKey": False,
            "unique": bool(unique),
            "foreignKey": False,
            "check": False,
            "index": True,
          }
        constraints[index]['columns'].append(column)
    # Get the PK
    pkColumn = self.getPrimaryKeyColumn(cursor, tableName)
    if pkColumn:
      # SQLite doesn't actually give a name to the PK constraint,
      # so we invent one. This is fine, as the SQLite backend never
      # deletes PK constraints by name, as you can't delete constraints
      # in SQLite; we remake the table with a new PK instead.
      constraints["__primary__"] = {
        "columns": [pkColumn],
        "primaryKey": True,
        "unique": False,  # It's not actually a unique constraint.
        "foreignKey": False,
        "check": False,
        "index": False,
      }
    return constraints
