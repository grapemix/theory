"""
Dummy database backend for Theory.

Theory uses this if the database ENGINE setting is empty (None or empty string).

Each of these API functions, except connection.close(), raises
ImproperlyConfigured.
"""

from theory.core.exceptions import ImproperlyConfigured
from theory.db.backends import *
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
  quote_name = complain

class DatabaseClient(BaseDatabaseClient):
  runshell = complain

class DatabaseWrapper(BaseDatabaseWrapper):
  operators = {}
  # Override the base class implementations with null
  # implementations. Anything that tries to actually
  # do something raises complain; anything that tries
  # to rollback or undo something raises ignore.
  close = ignore

  def __init__(self, *args, **kwargs):
    super(DatabaseWrapper, self).__init__(*args, **kwargs)

    self.client = DatabaseClient(self)
    self.validation = BaseDatabaseValidation(self)
