import sys
import time

from theory.conf import settings
from theory.db.backends.creation import BaseDatabaseCreation
from theory.utils.six.moves import input


TEST_DATABASE_PREFIX = 'test_'
PASSWORD = 'ImA_lumberjack'


class DatabaseCreation(BaseDatabaseCreation):
  # This dictionary maps Field objects to their associated Oracle column
  # types, as strings. Column-type strings can contain format strings; they'll
  # be interpolated against the values of Field.__dict__ before being output.
  # If a column type is set to None, it won't be included in the output.
  #
  # Any format strings starting with "qn_" are quoted before being used in the
  # output (the "qn_" prefix is stripped before the lookup is performed.

  dataTypes = {
    'AutoField': 'NUMBER(11)',
    'BinaryField': 'BLOB',
    'BooleanField': 'NUMBER(1)',
    'CharField': 'NVARCHAR2(%(maxLength)s)',
    'CommaSeparatedIntegerField': 'VARCHAR2(%(maxLength)s)',
    'DateField': 'DATE',
    'DateTimeField': 'TIMESTAMP',
    'DecimalField': 'NUMBER(%(maxDigits)s, %(decimalPlaces)s)',
    'FileField': 'NVARCHAR2(%(maxLength)s)',
    'FilePathField': 'NVARCHAR2(%(maxLength)s)',
    'FloatField': 'DOUBLE PRECISION',
    'IntegerField': 'NUMBER(11)',
    'BigIntegerField': 'NUMBER(19)',
    'IPAddressField': 'VARCHAR2(15)',
    'GenericIPAddressField': 'VARCHAR2(39)',
    'NullBooleanField': 'NUMBER(1)',
    'OneToOneField': 'NUMBER(11)',
    'PositiveIntegerField': 'NUMBER(11)',
    'PositiveSmallIntegerField': 'NUMBER(11)',
    'SlugField': 'NVARCHAR2(%(maxLength)s)',
    'SmallIntegerField': 'NUMBER(11)',
    'TextField': 'NCLOB',
    'TimeField': 'TIMESTAMP',
    'URLField': 'VARCHAR2(%(maxLength)s)',
  }

  dataTypeCheckConstraints = {
    'BooleanField': '%(qnColumn)s IN (0,1)',
    'NullBooleanField': '(%(qnColumn)s IN (0,1)) OR (%(qnColumn)s IS NULL)',
    'PositiveIntegerField': '%(qnColumn)s >= 0',
    'PositiveSmallIntegerField': '%(qnColumn)s >= 0',
  }

  def __init__(self, connection):
    super(DatabaseCreation, self).__init__(connection)

  def _createTestDb(self, verbosity=1, autoclobber=False):
    TEST_NAME = self._testDatabaseName()
    TEST_USER = self._testDatabaseUser()
    TEST_PASSWD = self._testDatabasePasswd()
    TEST_TBLSPACE = self._testDatabaseTblspace()
    TEST_TBLSPACE_TMP = self._testDatabaseTblspaceTmp()

    parameters = {
      'dbname': TEST_NAME,
      'user': TEST_USER,
      'password': TEST_PASSWD,
      'tblspace': TEST_TBLSPACE,
      'tblspaceTemp': TEST_TBLSPACE_TMP,
    }

    cursor = self.connection.cursor()
    if self._testDatabaseCreate():
      try:
        self._executeTestDbCreation(cursor, parameters, verbosity)
      except Exception as e:
        sys.stderr.write("Got an error creating the test database: %s\n" % e)
        if not autoclobber:
          confirm = input("It appears the test database, %s, already exists. Type 'yes' to delete it, or 'no' to cancel: " % TEST_NAME)
        if autoclobber or confirm == 'yes':
          try:
            if verbosity >= 1:
              print("Destroying old test database '%s'..." % self.connection.alias)
            self._executeTestDbDestruction(cursor, parameters, verbosity)
            self._executeTestDbCreation(cursor, parameters, verbosity)
          except Exception as e:
            sys.stderr.write("Got an error recreating the test database: %s\n" % e)
            sys.exit(2)
        else:
          print("Tests cancelled.")
          sys.exit(1)

    if self._testUserCreate():
      if verbosity >= 1:
        print("Creating test user...")
      try:
        self._createTestUser(cursor, parameters, verbosity)
      except Exception as e:
        sys.stderr.write("Got an error creating the test user: %s\n" % e)
        if not autoclobber:
          confirm = input("It appears the test user, %s, already exists. Type 'yes' to delete it, or 'no' to cancel: " % TEST_USER)
        if autoclobber or confirm == 'yes':
          try:
            if verbosity >= 1:
              print("Destroying old test user...")
            self._destroyTestUser(cursor, parameters, verbosity)
            if verbosity >= 1:
              print("Creating test user...")
            self._createTestUser(cursor, parameters, verbosity)
          except Exception as e:
            sys.stderr.write("Got an error recreating the test user: %s\n" % e)
            sys.exit(2)
        else:
          print("Tests cancelled.")
          sys.exit(1)

    realSettings = settings.DATABASES[self.connection.alias]
    realSettings['SAVED_USER'] = self.connection.settingsDict['SAVED_USER'] = self.connection.settingsDict['USER']
    realSettings['SAVED_PASSWORD'] = self.connection.settingsDict['SAVED_PASSWORD'] = self.connection.settingsDict['PASSWORD']
    realTestSettings = realSettings['TEST']
    testSettings = self.connection.settingsDict['TEST']
    realTestSettings['USER'] = realSettings['USER'] = testSettings['USER'] = self.connection.settingsDict['USER'] = TEST_USER
    realSettings['PASSWORD'] = self.connection.settingsDict['PASSWORD'] = TEST_PASSWD

    return self.connection.settingsDict['NAME']

  def _destroyTestDb(self, testDatabaseName, verbosity=1):
    """
    Destroy a test database, prompting the user for confirmation if the
    database already exists. Returns the name of the test database created.
    """
    TEST_NAME = self._testDatabaseName()
    TEST_USER = self._testDatabaseUser()
    TEST_PASSWD = self._testDatabasePasswd()
    TEST_TBLSPACE = self._testDatabaseTblspace()
    TEST_TBLSPACE_TMP = self._testDatabaseTblspaceTmp()

    self.connection.settingsDict['USER'] = self.connection.settingsDict['SAVED_USER']
    self.connection.settingsDict['PASSWORD'] = self.connection.settingsDict['SAVED_PASSWORD']

    parameters = {
      'dbname': TEST_NAME,
      'user': TEST_USER,
      'password': TEST_PASSWD,
      'tblspace': TEST_TBLSPACE,
      'tblspaceTemp': TEST_TBLSPACE_TMP,
    }

    cursor = self.connection.cursor()
    time.sleep(1)  # To avoid "database is being accessed by other users" errors.
    if self._testUserCreate():
      if verbosity >= 1:
        print('Destroying test user...')
      self._destroyTestUser(cursor, parameters, verbosity)
    if self._testDatabaseCreate():
      if verbosity >= 1:
        print('Destroying test database tables...')
      self._executeTestDbDestruction(cursor, parameters, verbosity)
    self.connection.close()

  def _executeTestDbCreation(self, cursor, parameters, verbosity):
    if verbosity >= 2:
      print("_createTestDb(): dbname = %s" % parameters['dbname'])
    statements = [
      """CREATE TABLESPACE %(tblspace)s
        DATAFILE '%(tblspace)s.dbf' SIZE 20M
        REUSE AUTOEXTEND ON NEXT 10M MAXSIZE 200M
      """,
      """CREATE TEMPORARY TABLESPACE %(tblspaceTemp)s
        TEMPFILE '%(tblspaceTemp)s.dbf' SIZE 20M
        REUSE AUTOEXTEND ON NEXT 10M MAXSIZE 100M
      """,
    ]
    self._executeStatements(cursor, statements, parameters, verbosity)

  def _createTestUser(self, cursor, parameters, verbosity):
    if verbosity >= 2:
      print("_createTestUser(): username = %s" % parameters['user'])
    statements = [
      """CREATE USER %(user)s
        IDENTIFIED BY %(password)s
        DEFAULT TABLESPACE %(tblspace)s
        TEMPORARY TABLESPACE %(tblspaceTemp)s
        QUOTA UNLIMITED ON %(tblspace)s
      """,
      """GRANT CONNECT, RESOURCE TO %(user)s""",
    ]
    self._executeStatements(cursor, statements, parameters, verbosity)

  def _executeTestDbDestruction(self, cursor, parameters, verbosity):
    if verbosity >= 2:
      print("_executeTestDbDestruction(): dbname=%s" % parameters['dbname'])
    statements = [
      'DROP TABLESPACE %(tblspace)s INCLUDING CONTENTS AND DATAFILES CASCADE CONSTRAINTS',
      'DROP TABLESPACE %(tblspaceTemp)s INCLUDING CONTENTS AND DATAFILES CASCADE CONSTRAINTS',
    ]
    self._executeStatements(cursor, statements, parameters, verbosity)

  def _destroyTestUser(self, cursor, parameters, verbosity):
    if verbosity >= 2:
      print("_destroyTestUser(): user=%s" % parameters['user'])
      print("Be patient.  This can take some time...")
    statements = [
      'DROP USER %(user)s CASCADE',
    ]
    self._executeStatements(cursor, statements, parameters, verbosity)

  def _executeStatements(self, cursor, statements, parameters, verbosity):
    for template in statements:
      stmt = template % parameters
      if verbosity >= 2:
        print(stmt)
      try:
        cursor.execute(stmt)
      except Exception as err:
        sys.stderr.write("Failed (%s)\n" % (err))
        raise

  def _testSettingsGet(self, key, default=None, prefixed=None):
    """
    Return a value from the test settings dict,
    or a given default,
    or a prefixed entry from the main settings dict
    """
    settingsDict = self.connection.settingsDict
    val = settingsDict['TEST'].get(key, default)
    if val is None:
      val = TEST_DATABASE_PREFIX + settingsDict[prefixed]
    return val

  def _testDatabaseName(self):
    return self._testSettingsGet('NAME', prefixed='NAME')

  def _testDatabaseCreate(self):
    return self._testSettingsGet('CREATE_DB', default=True)

  def _testUserCreate(self):
    return self._testSettingsGet('CREATE_USER', default=True)

  def _testDatabaseUser(self):
    return self._testSettingsGet('USER', prefixed='USER')

  def _testDatabasePasswd(self):
    return self._testSettingsGet('PASSWORD', default=PASSWORD)

  def _testDatabaseTblspace(self):
    return self._testSettingsGet('TBLSPACE', prefixed='NAME')

  def _testDatabaseTblspaceTmp(self):
    settingsDict = self.connection.settingsDict
    return settingsDict['TEST'].get('TBLSPACE_TMP',
                     TEST_DATABASE_PREFIX + settingsDict['NAME'] + '_temp')

  def _getTestDbName(self):
    """
    We need to return the 'production' DB name to get the test DB creation
    machinery to work. This isn't a great deal in this case because DB
    names as handled by Theory haven't real counterparts in Oracle.
    """
    return self.connection.settingsDict['NAME']

  def testDbSignature(self):
    settingsDict = self.connection.settingsDict
    return (
      settingsDict['HOST'],
      settingsDict['PORT'],
      settingsDict['ENGINE'],
      settingsDict['NAME'],
      self._testDatabaseUser(),
    )
