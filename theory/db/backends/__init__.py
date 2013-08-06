# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.db import DEFAULT_DB_ALIAS
from theory.db.utils import DatabaseError
from theory.utils.importlib import import_module
from theory.utils.timezone import is_aware

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class BaseDatabaseWrapper(object):
  """
  Represents a database connection.
  """
  ops = None
  vendor = 'unknown'

  def __init__(self, settings_dict, alias=DEFAULT_DB_ALIAS):
    # `settings_dict` should be a dictionary containing keys such as
    # NAME, USER, etc. It's called `settings_dict` instead of `settings`
    # to disambiguate it from Theory settings modules.
    self.connection = None
    self.settings_dict = settings_dict
    self.alias = alias

  def __eq__(self, other):
    return self.alias == other.alias

  def __ne__(self, other):
    return not self == other

  def close(self):
    if self.connection is not None:
      self.connection.close()
      self.connection = None



# The prefix to put on the default database name when creating
# the test database.
TEST_DATABASE_PREFIX = 'test_'

class BaseDatabaseCreation(object):
  """
  This class encapsulates all backend-specific differences that pertain to
  database *creation*, such as the column types to use for particular Theory
  Fields, the DB command used to create and destroy tables, and the creation and
  destruction of test databases.
  """

  data_types = {}
  def __init__(self, connection, settings_dict):
    self.connection = connection
    self.settings_dict = settings_dict

  def _digest(self, *args):
    """
    Generates a 32-bit digest of a set of arguments that can be used to
    shorten identifying names.
    """
    return '%x' % (abs(hash(args)) % 4294967296L)  # 2**32

  def _getTestDbName(self):
    """
    Internal implementation - returns the name of the test DB that will be
    created. Only useful when called from create_test_db() and
    _create_test_db() and when no external munging is done with the 'NAME'
    or 'TEST_NAME' settings.
    """
    if self.settings_dict['TEST_NAME']:
      return self.settings_dict['TEST_NAME']
    return TEST_DATABASE_PREFIX + self.settings_dict['NAME']

  def testDbSignature(self):
    """
    Returns a tuple with elements of self.settings_dict (a
    DATABASES setting value) that uniquely identify a database
    accordingly to the RDBMS particularities.
    """
    settings_dict = self.settings_dict
    return (
      settings_dict['HOST'],
      settings_dict['PORT'],
      settings_dict['ENGINE'],
      settings_dict['NAME']
    )

  def createTestDb(self, verbosity=1, autoclobber=False):
    testDatabaseName = self._getTestDbName()
    if verbosity >= 1:
      testDbRepr = ''
      if verbosity >= 2:
        testDbRepr = " ('%s')" % testDatabaseName
      print "Creating test database for alias '%s'%s..." % (
          self.connection.alias, testDbRepr)
    self._closeConnection()
    self._createTestDb(verbosity, autoclobber)
    self.settings_dict["NAME"] = testDatabaseName
    return testDatabaseName

  def _closeConnection(self):
    self.connection.close()

  def _createTestDb(self, verbosity, autoclobber):
    """
    Internal implementation - creates the test db tables.
    """
    pass

  def destroyTestDb(self, oldDatabaseName, verbosity=1):
    """
    Destroy a test database, prompting the user for confirmation if the
    database already exists.
    """
    testDatabaseName = self.settings_dict['NAME']
    if verbosity >= 1:
      testDbRepr = ''
      if verbosity >= 2:
        testDbRepr = " ('%s')" % testDatabaseName
      print "Destroying test database for alias '%s'%s..." % (
          self.connection.alias, testDbRepr)
    self._destroyTestDb(testDatabaseName, verbosity)
    self._closeConnection()

  def _destroyTestDb(self, testDatabaseName, verbosity):
    """
    Internal implementation - remove the test db tables.
    """
    self.connection.close()

class BaseDatabaseClient(object):
  """
  This class encapsulates all backend-specific methods for opening a
  client shell.
  """
  # This should be a string representing the name of the executable
  # (e.g., "psql"). Subclasses must override this.
  executable_name = None

  def __init__(self, connection, settings_dict):
    # connection is an instance of BaseDatabaseWrapper.
    self.connection = connection
    self.settings_dict = settings_dict

  def runshell(self):
    raise NotImplementedError()

class BaseDatabaseValidation(object):
  """
  This class encapsualtes all backend-specific model validation.
  """
  def __init__(self, connection, settings_dict):
    self.connection = connection
    self.settings_dict = settings_dict

  def validate_field(self, errors, opts, f):
    "By default, there is no backend-specific validation"
    pass
