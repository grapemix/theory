import os
import sys

from theory.db.backends.creation import BaseDatabaseCreation
from theory.utils.six.moves import input


class DatabaseCreation(BaseDatabaseCreation):
  # SQLite doesn't actually support most of these types, but it "does the right
  # thing" given more verbose field definitions, so leave them as is so that
  # schema inspection is more useful.
  dataTypes = {
    'AutoField': 'integer',
    'BinaryField': 'BLOB',
    'BooleanField': 'bool',
    'CharField': 'varchar(%(maxLength)s)',
    'CommaSeparatedIntegerField': 'varchar(%(maxLength)s)',
    'DateField': 'date',
    'DateTimeField': 'datetime',
    'DecimalField': 'decimal',
    'FileField': 'varchar(%(maxLength)s)',
    'FilePathField': 'varchar(%(maxLength)s)',
    'FloatField': 'real',
    'IntegerField': 'integer',
    'BigIntegerField': 'bigint',
    'IPAddressField': 'char(15)',
    'GenericIPAddressField': 'char(39)',
    'NullBooleanField': 'bool',
    'OneToOneField': 'integer',
    'PositiveIntegerField': 'integer unsigned',
    'PositiveSmallIntegerField': 'smallint unsigned',
    'SlugField': 'varchar(%(maxLength)s)',
    'SmallIntegerField': 'smallint',
    'TextField': 'text',
    'TimeField': 'time',
  }
  dataTypesSuffix = {
    'AutoField': 'AUTOINCREMENT',
  }

  def sqlForPendingReferences(self, modal, style, pendingReferences):
    "SQLite3 doesn't support constraints"
    return []

  def sqlRemoveTableConstraints(self, modal, referencesToDelete, style):
    "SQLite3 doesn't support constraints"
    return []

  def _getTestDbName(self):
    testDatabaseName = self.connection.settingsDict['TEST']['NAME']
    if testDatabaseName and testDatabaseName != ':memory:':
      return testDatabaseName
    return ':memory:'

  def _createTestDb(self, verbosity, autoclobber):
    testDatabaseName = self._getTestDbName()
    if testDatabaseName != ':memory:':
      # Erase the old test database
      if verbosity >= 1:
        print("Destroying old test database '%s'..." % self.connection.alias)
      if os.access(testDatabaseName, os.F_OK):
        if not autoclobber:
          confirm = input("Type 'yes' if you would like to try deleting the test database '%s', or 'no' to cancel: " % testDatabaseName)
        if autoclobber or confirm == 'yes':
          try:
            os.remove(testDatabaseName)
          except Exception as e:
            sys.stderr.write("Got an error deleting the old test database: %s\n" % e)
            sys.exit(2)
        else:
          print("Tests cancelled.")
          sys.exit(1)
    return testDatabaseName

  def _destroyTestDb(self, testDatabaseName, verbosity):
    if testDatabaseName and testDatabaseName != ":memory:":
      # Remove the SQLite database file
      os.remove(testDatabaseName)

  def testDbSignature(self):
    """
    Returns a tuple that uniquely identifies a test database.

    This takes into account the special cases of ":memory:" and "" for
    SQLite since the databases will be distinct despite having the same
    TEST NAME. See http://www.sqlite.org/inmemorydb.html
    """
    testDbname = self._getTestDbName()
    sig = [self.connection.settingsDict['NAME']]
    if testDbname == ':memory:':
      sig.append(self.connection.alias)
    return tuple(sig)
