"""
Dummy database backend for Theory.

Theory uses this if the database ENGINE setting is empty (None or empty string).

Each of these API functions, except connection.close(), raises
ImproperlyConfigured.
"""

from theory.core.exceptions import ImproperlyConfigured
from theory.db.backends import (BaseDatabaseOperations, BaseDatabaseClient,
  BaseDatabaseIntrospection, BaseDatabaseWrapper, BaseDatabaseFeatures,
  BaseDatabaseValidation)
from theory.db.backends.creation import BaseDatabaseCreation


def complain(*args, **kwargs):
  raise ImproperlyConfigured("settings.DATABASES is improperly configured. "
                "Please supply the ENGINE value. Check "
                "settings documentation for more details.")


def ignore(*args, **kwargs):
  pass


class DatabaseError(Exception):
  pass


class IntegrityError(DatabaseError):
  pass


class DatabaseOperations(BaseDatabaseOperations):
  quoteName = complain


class DatabaseClient(BaseDatabaseClient):
  runshell = complain


class DatabaseCreation(BaseDatabaseCreation):
  createTestDb = ignore
  destroyTestDb = ignore


class DatabaseIntrospection(BaseDatabaseIntrospection):
  getTableList = complain
  getTableDescription = complain
  getRelations = complain
  getIndexes = complain
  getKeyColumns = complain


class DatabaseWrapper(BaseDatabaseWrapper):
  operators = {}
  # Override the base class implementations with null
  # implementations. Anything that tries to actually
  # do something raises complain; anything that tries
  # to rollback or undo something raises ignore.
  _cursor = complain
  _commit = complain
  _rollback = ignore
  _close = ignore
  _savepoint = ignore
  _savepointCommit = complain
  _savepointRollback = ignore
  _setAutocommit = complain
  setDirty = complain
  setClean = complain

  def __init__(self, *args, **kwargs):
    super(DatabaseWrapper, self).__init__(*args, **kwargs)

    self.features = BaseDatabaseFeatures(self)
    self.ops = DatabaseOperations(self)
    self.client = DatabaseClient(self)
    self.creation = DatabaseCreation(self)
    self.introspection = DatabaseIntrospection(self)
    self.validation = BaseDatabaseValidation(self)

  def isUsable(self):
    return True
