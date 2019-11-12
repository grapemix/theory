import hashlib
import sys
import time
import warnings

from theory.conf import settings
from theory.db.utils import loadBackend
from theory.utils.deprecation import RemovedInTheory20Warning
from theory.utils.encoding import forceBytes
from theory.utils.functional import cachedProperty
from theory.utils.six.moves import input
from theory.utils.six import StringIO
from theory.apps.util import sortDependencies
from theory.db import router
from theory.apps import apps
from theory.core import serializers

from .utils import truncateName

# The prefix to put on the default database name when creating
# the test database.
TEST_DATABASE_PREFIX = 'test_'
NO_DB_ALIAS = '__noDb__'


class BaseDatabaseCreation(object):
  """
  This class encapsulates all backend-specific differences that pertain to
  database *creation*, such as the column types to use for particular Theory
  Fields, the SQL used to create and destroy tables, and the creation and
  destruction of test databases.
  """
  dataTypes = {}
  dataTypesSuffix = {}
  dataTypeCheckConstraints = {}

  def __init__(self, connection):
    self.connection = connection

  @cachedProperty
  def _nodbConnection(self):
    """
    Alternative connection to be used when there is no need to access
    the main database, specifically for test db creation/deletion.
    This also prevents the production database from being exposed to
    potential child threads while (or after) the test database is destroyed.
    Refs #10868, #17786, #16969.
    """
    settingsDict = self.connection.settingsDict.copy()
    settingsDict['NAME'] = None
    backend = loadBackend(settingsDict['ENGINE'])
    nodbConnection = backend.DatabaseWrapper(
      settingsDict,
      alias=NO_DB_ALIAS,
      allowThreadSharing=False)
    return nodbConnection

  @classmethod
  def _digest(cls, *args):
    """
    Generates a 32-bit digest of a set of arguments that can be used to
    shorten identifying names.
    """
    h = hashlib.md5()
    for arg in args:
      h.update(forceBytes(arg))
    return h.hexdigest()[:8]

  def sqlCreateModel(self, modal, style, knownModels=set()):
    """
    Returns the SQL required to create a single modal, as a tuple of:
      (listOfSql, pendingReferencesDict)
    """
    opts = modal._meta
    if not opts.managed or opts.proxy or opts.swapped:
      return [], {}
    finalOutput = []
    tableOutput = []
    pendingReferences = {}
    qn = self.connection.ops.quoteName
    for f in opts.localFields:
      colType = f.dbType(connection=self.connection)
      colTypeSuffix = f.dbTypeSuffix(connection=self.connection)
      tablespace = f.dbTablespace or opts.dbTablespace
      if colType is None:
        # Skip ManyToManyFields, because they're not represented as
        # database columns in this table.
        continue
      # Make the definition (e.g. 'foo VARCHAR(30)') for this field.
      fieldOutput = [style.SQL_FIELD(qn(f.column)),
        style.SQL_COLTYPE(colType)]
      # Oracle treats the empty string ('') as null, so coerce the null
      # option whenever '' is a possible value.
      null = f.null
      if (f.emptyStringsAllowed and not f.primaryKey and
          self.connection.features.interpretsEmptyStringsAsNulls):
        null = True
      if not null:
        fieldOutput.append(style.SQL_KEYWORD('NOT NULL'))
      if f.primaryKey:
        fieldOutput.append(style.SQL_KEYWORD('PRIMARY KEY'))
      elif f.unique:
        fieldOutput.append(style.SQL_KEYWORD('UNIQUE'))
      if tablespace and f.unique:
        # We must specify the index tablespace inline, because we
        # won't be generating a CREATE INDEX statement for this field.
        tablespaceSql = self.connection.ops.tablespaceSql(
          tablespace, inline=True)
        if tablespaceSql:
          fieldOutput.append(tablespaceSql)
      if f.rel and f.dbConstraint:
        refOutput, pending = self.sqlForInlineForeignKeyReferences(
          modal, f, knownModels, style)
        if pending:
          pendingReferences.setdefault(f.rel.to, []).append(
            (modal, f))
        else:
          fieldOutput.extend(refOutput)
      if colTypeSuffix:
        fieldOutput.append(style.SQL_KEYWORD(colTypeSuffix))
      tableOutput.append(' '.join(fieldOutput))
    for fieldConstraints in opts.uniqueTogether:
      tableOutput.append(style.SQL_KEYWORD('UNIQUE') + ' (%s)' %
        ", ".join(
          [style.SQL_FIELD(qn(opts.getField(f).column))
           for f in fieldConstraints]))

    fullStatement = [style.SQL_KEYWORD('CREATE TABLE') + ' ' +
             style.SQL_TABLE(qn(opts.dbTable)) + ' (']
    for i, line in enumerate(tableOutput):  # Combine and add commas.
      fullStatement.append(
        '    %s%s' % (line, ',' if i < len(tableOutput) - 1 else ''))
    fullStatement.append(')')
    if opts.dbTablespace:
      tablespaceSql = self.connection.ops.tablespaceSql(
        opts.dbTablespace)
      if tablespaceSql:
        fullStatement.append(tablespaceSql)
    fullStatement.append(';')
    finalOutput.append('\n'.join(fullStatement))

    if opts.hasAutoField:
      # Add any extra SQL needed to support auto-incrementing primary
      # keys.
      autoColumn = opts.autoField.dbColumn or opts.autoField.name
      autoincSql = self.connection.ops.autoincSql(opts.dbTable,
                             autoColumn)
      if autoincSql:
        for stmt in autoincSql:
          finalOutput.append(stmt)

    return finalOutput, pendingReferences

  def sqlForInlineForeignKeyReferences(self, modal, field, knownModels, style):
    """
    Return the SQL snippet defining the foreign key reference for a field.
    """
    qn = self.connection.ops.quoteName
    relTo = field.rel.to
    if relTo in knownModels or relTo == modal:
      output = [style.SQL_KEYWORD('REFERENCES') + ' ' +
        style.SQL_TABLE(qn(relTo._meta.dbTable)) + ' (' +
        style.SQL_FIELD(qn(relTo._meta.getField(
          field.rel.fieldName).column)) + ')' +
        self.connection.ops.deferrableSql()
      ]
      pending = False
    else:
      # We haven't yet created the table to which this field
      # is related, so save it for later.
      output = []
      pending = True

    return output, pending

  def sqlForPendingReferences(self, modal, style, pendingReferences):
    """
    Returns any ALTER TABLE statements to add constraints after the fact.
    """
    opts = modal._meta
    if not opts.managed or opts.swapped:
      return []
    qn = self.connection.ops.quoteName
    finalOutput = []
    if modal in pendingReferences:
      for relClass, f in pendingReferences[modal]:
        relOpts = relClass._meta
        rTable = relOpts.dbTable
        rCol = f.column
        table = opts.dbTable
        col = opts.getField(f.rel.fieldName).column
        # For MySQL, rName must be unique in the first 64 characters.
        # So we are careful with character usage here.
        rName = '%sRefs_%s_%s' % (
          rCol, col, self._digest(rTable, table))
        finalOutput.append(style.SQL_KEYWORD('ALTER TABLE') +
          ' %s ADD CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s (%s)%s;' %
          (qn(rTable), qn(truncateName(
            rName, self.connection.ops.maxNameLength())),
          qn(rCol), qn(table), qn(col),
          self.connection.ops.deferrableSql()))
      del pendingReferences[modal]
    return finalOutput

  def sqlIndexesForModel(self, modal, style):
    """
    Returns the CREATE INDEX SQL statements for a single modal.
    """
    if not modal._meta.managed or modal._meta.proxy or modal._meta.swapped:
      return []
    output = []
    for f in modal._meta.localFields:
      output.extend(self.sqlIndexesForField(modal, f, style))
    for fs in modal._meta.indexTogether:
      fields = [modal._meta.getFieldByName(f)[0] for f in fs]
      output.extend(self.sqlIndexesForFields(modal, fields, style))
    return output

  def sqlIndexesForField(self, modal, f, style):
    """
    Return the CREATE INDEX SQL statements for a single modal field.
    """
    if f.dbIndex and not f.unique:
      return self.sqlIndexesForFields(modal, [f], style)
    else:
      return []

  def sqlIndexesForFields(self, modal, fields, style):
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

    return [
      style.SQL_KEYWORD("CREATE INDEX") + " " +
      style.SQL_TABLE(qn(truncateName(indexName, self.connection.ops.maxNameLength()))) + " " +
      style.SQL_KEYWORD("ON") + " " +
      style.SQL_TABLE(qn(modal._meta.dbTable)) + " " +
      "(%s)" % style.SQL_FIELD(", ".join(fieldNames)) +
      "%s;" % tablespaceSql,
    ]

  def sqlDestroyModel(self, modal, referencesToDelete, style):
    """
    Return the DROP TABLE and restraint dropping statements for a single
    modal.
    """
    if not modal._meta.managed or modal._meta.proxy or modal._meta.swapped:
      return []
    # Drop the table now
    qn = self.connection.ops.quoteName
    output = ['%s %s;' % (style.SQL_KEYWORD('DROP TABLE'),
               style.SQL_TABLE(qn(modal._meta.dbTable)))]
    if modal in referencesToDelete:
      output.extend(self.sqlRemoveTableConstraints(
        modal, referencesToDelete, style))
    if modal._meta.hasAutoField:
      ds = self.connection.ops.dropSequenceSql(modal._meta.dbTable)
      if ds:
        output.append(ds)
    return output

  def sqlRemoveTableConstraints(self, modal, referencesToDelete, style):
    if not modal._meta.managed or modal._meta.proxy or modal._meta.swapped:
      return []
    output = []
    qn = self.connection.ops.quoteName
    for relClass, f in referencesToDelete[modal]:
      table = relClass._meta.dbTable
      col = f.column
      rTable = modal._meta.dbTable
      rCol = modal._meta.getField(f.rel.fieldName).column
      rName = '%sRefs_%s_%s' % (
        col, rCol, self._digest(table, rTable))
      output.append('%s %s %s %s;' % (
        style.SQL_KEYWORD('ALTER TABLE'),
        style.SQL_TABLE(qn(table)),
        style.SQL_KEYWORD(self.connection.ops.dropForeignkeySql()),
        style.SQL_FIELD(qn(truncateName(
          rName, self.connection.ops.maxNameLength())))
      ))
    del referencesToDelete[modal]
    return output

  def sqlDestroyIndexesForModel(self, modal, style):
    """
    Returns the DROP INDEX SQL statements for a single modal.
    """
    if not modal._meta.managed or modal._meta.proxy or modal._meta.swapped:
      return []
    output = []
    for f in modal._meta.localFields:
      output.extend(self.sqlDestroyIndexesForField(modal, f, style))
    for fs in modal._meta.indexTogether:
      fields = [modal._meta.getFieldByName(f)[0] for f in fs]
      output.extend(self.sqlDestroyIndexesForFields(modal, fields, style))
    return output

  def sqlDestroyIndexesForField(self, modal, f, style):
    """
    Return the DROP INDEX SQL statements for a single modal field.
    """
    if f.dbIndex and not f.unique:
      return self.sqlDestroyIndexesForFields(modal, [f], style)
    else:
      return []

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

    return [
      style.SQL_KEYWORD("DROP INDEX") + " " +
      style.SQL_TABLE(qn(truncateName(indexName, self.connection.ops.maxNameLength()))) + " " +
      ";",
    ]

  def createTestDb(self, verbosity=1, autoclobber=False, serialize=True):
    """
    Creates a test database, prompting the user for confirmation if the
    database already exists. Returns the name of the test database created.
    """
    # Don't import theory.core.management if it isn't needed.
    #from theory.core.management import callCommand
    from theory.core.bridge import Bridge

    testDatabaseName = self._getTestDbName()
    bridge =  Bridge()

    if verbosity >= 1:
      testDbRepr = ''
      if verbosity >= 2:
        testDbRepr = " ('%s')" % testDatabaseName
      print("Creating test database for alias '%s'%s..." % (
        self.connection.alias, testDbRepr))

    self._createTestDb(verbosity, autoclobber)

    self.connection.close()
    settings.DATABASES[self.connection.alias]["NAME"] = testDatabaseName
    self.connection.settingsDict["NAME"] = testDatabaseName

    # We report migrate messages at one level lower than that requested.
    # This ensures we don't get flooded with messages during testing
    # (unless you really ask to be flooded).
    #callCommand(
    #  'migrate',
    #  verbosity=max(verbosity - 1, 0),
    #  interactive=False,
    #  database=self.connection.alias,
    #  testDatabase=True,
    #  testFlush=True,
    #)
    bridge.executeEzCommand(
        'theory',
        'migrate',
        [],
        {
          "verbosity": max(verbosity - 1, 0),
          "database": self.connection.alias,
          "isTestDatabase": True,
          "isTestFlush": True,
        }
    )



    # We then serialize the current state of the database into a string
    # and store it on the connection. This slightly horrific process is so people
    # who are testing on databases without transactions or who are using
    # a TransactionTestCase still get a clean database on every test run.
    if serialize:
      self.connection._testSerializedContents = self.serializeDbToString()

    # !!!!!!!!!! fix me
    #callCommand('createcachetable', database=self.connection.alias)
    #bridge.executeEzCommand(
    #    'theory',
    #    'createcachetable',
    #    [],
    #    {
    #      "database": self.connection.alias,
    #    }
    #)



    # Ensure a connection for the side effect of initializing the test database.
    self.connection.ensureConnection()

    return testDatabaseName

  def serializeDbToString(self):
    """
    Serializes all data in the database into a JSON string.
    Designed only for test runner usage; will not handle large
    amounts of data.
    """
    # Build list of all apps to serialize
    from theory.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(self.connection)
    appList = []
    for appConfig in apps.getAppConfigs():
      if (
        appConfig.modelModule is not None and
        appConfig.label in loader.migratedApps and
        appConfig.name not in settings.TEST_NON_SERIALIZED_APPS
      ):
        appList.append((appConfig, None))

    # Make a function to iteratively return every object
    def getObjects():
      for modal in sortDependencies(appList):
        if not modal._meta.proxy and modal._meta.managed and router.allowMigrate(self.connection.alias, modal):
          queryset = modal._defaultManager.using(self.connection.alias).orderBy(modal._meta.pk.name)
          for obj in queryset.iterator():
            yield obj
    # Serialise to a string
    out = StringIO()
    serializers.serialize("json", getObjects(), indent=None, stream=out)
    return out.getvalue()

  def deserializeDbFromString(self, data):
    """
    Reloads the database with data from a string generated by
    the serializeDbToString method.
    """
    data = StringIO(data)
    for obj in serializers.deserialize("json", data, using=self.connection.alias):
      obj.save()

  def _getTestDbName(self):
    """
    Internal implementation - returns the name of the test DB that will be
    created. Only useful when called from createTestDb() and
    _createTestDb() and when no external munging is done with the 'NAME'
    or 'TEST_NAME' settings.
    """
    if self.connection.settingsDict['TEST']['NAME']:
      return self.connection.settingsDict['TEST']['NAME']
    return TEST_DATABASE_PREFIX + self.connection.settingsDict['NAME']

  def _createTestDb(self, verbosity, autoclobber):
    """
    Internal implementation - creates the test db tables.
    """
    suffix = self.sqlTableCreationSuffix()

    testDatabaseName = self._getTestDbName()

    qn = self.connection.ops.quoteName

    # Create the test database and connect to it.
    with self._nodbConnection.cursor() as cursor:
      try:
        cursor.execute(
          "CREATE DATABASE %s %s" % (qn(testDatabaseName), suffix))
      except Exception as e:
        sys.stderr.write(
          "Got an error creating the test database: %s\n" % e)
        if not autoclobber:
          confirm = input(
            "Type 'yes' if you would like to try deleting the test "
            "database '%s', or 'no' to cancel: " % testDatabaseName)
        if autoclobber or confirm == 'yes':
          try:
            if verbosity >= 1:
              print("Destroying old test database '%s'..."
                 % self.connection.alias)
            cursor.execute(
              "DROP DATABASE %s" % qn(testDatabaseName))
            cursor.execute(
              "CREATE DATABASE %s %s" % (qn(testDatabaseName),
                            suffix))
          except Exception as e:
            sys.stderr.write(
              "Got an error recreating the test database: %s\n" % e)
            sys.exit(2)
        else:
          print("Tests cancelled.")
          sys.exit(1)

    return testDatabaseName

  def destroyTestDb(self, oldDatabaseName, verbosity=1):
    """
    Destroy a test database, prompting the user for confirmation if the
    database already exists.
    """
    self.connection.close()
    testDatabaseName = self.connection.settingsDict['NAME']
    if verbosity >= 1:
      testDbRepr = ''
      if verbosity >= 2:
        testDbRepr = " ('%s')" % testDatabaseName
      print("Destroying test database for alias '%s'%s..." % (
        self.connection.alias, testDbRepr))

    self._destroyTestDb(testDatabaseName, verbosity)

  def _destroyTestDb(self, testDatabaseName, verbosity):
    """
    Internal implementation - remove the test db tables.
    """
    # Remove the test database to clean up after
    # ourselves. Connect to the previous database (not the test database)
    # to do so, because it's not allowed to delete a database while being
    # connected to it.
    with self._nodbConnection.cursor() as cursor:
      # Wait to avoid "database is being accessed by other users" errors.
      time.sleep(1)
      cursor.execute("DROP DATABASE %s"
              % self.connection.ops.quoteName(testDatabaseName))

  def setAutocommit(self):
    """
    Make sure a connection is in autocommit mode. - Deprecated, not used
    anymore by Theory code. Kept for compatibility with user code that
    might use it.
    """
    warnings.warn(
      "setAutocommit was moved from BaseDatabaseCreation to "
      "BaseDatabaseWrapper.", RemovedInTheory20Warning, stacklevel=2)
    return self.connection.setAutocommit(True)

  def sqlTableCreationSuffix(self):
    """
    SQL to append to the end of the test table creation statements.
    """
    return ''

  def testDbSignature(self):
    """
    Returns a tuple with elements of self.connection.settingsDict (a
    DATABASES setting value) that uniquely identify a database
    accordingly to the RDBMS particularities.
    """
    settingsDict = self.connection.settingsDict
    return (
      settingsDict['HOST'],
      settingsDict['PORT'],
      settingsDict['ENGINE'],
      settingsDict['NAME']
    )
