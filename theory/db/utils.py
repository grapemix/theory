from importlib import import_module
import os
import pkgutil
from threading import local
import warnings

from theory.conf import settings
from theory.core.exceptions import ImproperlyConfigured
from theory.utils.deprecation import RemovedInTheory20Warning, RemovedInTheory19Warning
from theory.utils.functional import cachedProperty
from theory.utils.moduleLoading import importString
from theory.utils._os import upath
from theory.utils import six


DEFAULT_DB_ALIAS = 'default'


class Error(Exception if six.PY3 else StandardError):
  pass


class InterfaceError(Error):
  pass


class DatabaseError(Error):
  pass


class DataError(DatabaseError):
  pass


class OperationalError(DatabaseError):
  pass


class IntegrityError(DatabaseError):
  pass


class InternalError(DatabaseError):
  pass


class ProgrammingError(DatabaseError):
  pass


class NotSupportedError(DatabaseError):
  pass


class DatabaseErrorWrapper(object):
  """
  Context manager and decorator that re-throws backend-specific database
  exceptions using Theory's common wrappers.
  """

  def __init__(self, wrapper):
    """
    wrapper is a database wrapper.

    It must have a Database attribute defining PEP-249 exceptions.
    """
    self.wrapper = wrapper

  def __enter__(self):
    pass

  def __exit__(self, excType, excValue, traceback):
    if excType is None:
      return
    for djExcType in (
        DataError,
        OperationalError,
        IntegrityError,
        InternalError,
        ProgrammingError,
        NotSupportedError,
        DatabaseError,
        InterfaceError,
        Error,
    ):
      dbExcType = getattr(self.wrapper.Database, djExcType.__name__)
      if issubclass(excType, dbExcType):
        djExcValue = djExcType(*excValue.args)
        djExcValue.__cause__ = excValue
        # Only set the 'errorsOccurred' flag for errors that may make
        # the connection unusable.
        if djExcType not in (DataError, IntegrityError):
          self.wrapper.errorsOccurred = True
        six.reraise(djExcType, djExcValue, traceback)

  def __call__(self, func):
    # Note that we are intentionally not using @wraps here for performance
    # reasons. Refs #21109.
    def inner(*args, **kwargs):
      with self:
        return func(*args, **kwargs)
    return inner


def loadBackend(backendName):
  # Look for a fully qualified database backend name
  try:
    return import_module('%s.base' % backendName)
  except ImportError as eUser:
    # The database backend wasn't found. Display a helpful error message
    # listing all possible (built-in) database backends.
    backendDir = os.path.join(os.path.dirname(upath(__file__)), 'backends')
    try:
      builtinBackends = [
        name for _, name, ispkg in pkgutil.iter_modules([backendDir])
        if ispkg and name != 'dummy']
    except EnvironmentError:
      builtinBackends = []
    if backendName not in ['theory.db.backends.%s' % b for b in
                builtinBackends]:
      backendReprs = map(repr, sorted(builtinBackends))
      errorMsg = ("%r isn't an available database backend.\n"
             "Try using 'theory.db.backends.XXX', where XXX "
             "is one of:\n    %s\nError was: %s" %
             (backendName, ", ".join(backendReprs), eUser))
      raise ImproperlyConfigured(errorMsg)
    else:
      # If there's some other error, this must be an error in Theory
      raise


class ConnectionDoesNotExist(Exception):
  pass


class ConnectionHandler(object):
  def __init__(self, databases=None):
    """
    databases is an optional dictionary of database definitions (structured
    like settings.DATABASES).
    """
    self._databases = databases
    self._connections = local()

  @cachedProperty
  def databases(self):
    if self._databases is None:
      self._databases = settings.DATABASES
    if self._databases == {}:
      self._databases = {
        DEFAULT_DB_ALIAS: {
          'ENGINE': 'theory.db.backends.dummy',
        },
      }
    if DEFAULT_DB_ALIAS not in self._databases:
      raise ImproperlyConfigured("You must define a '%s' database" % DEFAULT_DB_ALIAS)
    return self._databases

  def ensureDefaults(self, alias):
    """
    Puts the defaults into the settings dictionary for a given connection
    where no settings is provided.
    """
    try:
      conn = self.databases[alias]
    except KeyError:
      raise ConnectionDoesNotExist("The connection %s doesn't exist" % alias)

    conn.setdefault('ATOMIC_REQUESTS', False)
    if settings.TRANSACTIONS_MANAGED:
      warnings.warn(
        "TRANSACTIONS_MANAGED is deprecated. Use AUTOCOMMIT instead.",
        RemovedInTheory20Warning, stacklevel=2)
      conn.setdefault('AUTOCOMMIT', False)
    conn.setdefault('AUTOCOMMIT', True)
    conn.setdefault('ENGINE', 'theory.db.backends.dummy')
    if conn['ENGINE'] == 'theory.db.backends.' or not conn['ENGINE']:
      conn['ENGINE'] = 'theory.db.backends.dummy'
    conn.setdefault('CONN_MAX_AGE', 0)
    conn.setdefault('OPTIONS', {})
    conn.setdefault('TIME_ZONE', 'UTC' if settings.USE_TZ else settings.TIME_ZONE)
    for setting in ['NAME', 'USER', 'PASSWORD', 'HOST', 'PORT']:
      conn.setdefault(setting, '')

  TEST_SETTING_RENAMES = {
    'CREATE': 'CREATE_DB',
    'USER_CREATE': 'CREATE_USER',
    'PASSWD': 'PASSWORD',
  }
  TEST_SETTING_RENAMES_REVERSE = {v: k for k, v in TEST_SETTING_RENAMES.items()}

  def prepareTestSettings(self, alias):
    """
    Makes sure the test settings are available in the 'TEST' sub-dictionary.
    """
    try:
      conn = self.databases[alias]
    except KeyError:
      raise ConnectionDoesNotExist("The connection %s doesn't exist" % alias)

    testDictSet = 'TEST' in conn
    testSettings = conn.setdefault('TEST', {})
    oldTestSettings = {}
    for key, value in six.iteritems(conn):
      if key.startswith('TEST_'):
        newKey = key[5:]
        newKey = self.TEST_SETTING_RENAMES.get(newKey, newKey)
        oldTestSettings[newKey] = value

    if oldTestSettings:
      if testDictSet:
        if testSettings != oldTestSettings:
          raise ImproperlyConfigured(
            "Connection '%s' has mismatched TEST and TEST_* "
            "database settings." % alias)
      else:
        testSettings.update(oldTestSettings)
        for key, _ in six.iteritems(oldTestSettings):
          warnings.warn("In Theory 1.9 the %s connection setting will be moved "
                 "to a %s entry in the TEST setting" %
                 (self.TEST_SETTING_RENAMES_REVERSE.get(key, key), key),
                 RemovedInTheory19Warning, stacklevel=2)

    for key in list(conn.keys()):
      if key.startswith('TEST_'):
        del conn[key]
    # Check that they didn't just use the old name with 'TEST_' removed
    for key, newKey in six.iteritems(self.TEST_SETTING_RENAMES):
      if key in testSettings:
        warnings.warn("Test setting %s was renamed to %s; specified value (%s) ignored" %
               (key, newKey, testSettings[key]), stacklevel=2)
    for key in ['CHARSET', 'COLLATION', 'NAME', 'MIRROR']:
      testSettings.setdefault(key, None)

  def __getitem__(self, alias):
    if hasattr(self._connections, alias):
      return getattr(self._connections, alias)

    self.ensureDefaults(alias)
    self.prepareTestSettings(alias)
    db = self.databases[alias]
    backend = loadBackend(db['ENGINE'])
    conn = backend.DatabaseWrapper(db, alias)
    setattr(self._connections, alias, conn)
    return conn

  def __setitem__(self, key, value):
    setattr(self._connections, key, value)

  def __delitem__(self, key):
    delattr(self._connections, key)

  def __iter__(self):
    return iter(self.databases)

  def all(self):
    return [self[alias] for alias in self]


class ConnectionRouter(object):
  def __init__(self, routers=None):
    """
    If routers is not specified, will default to settings.DATABASE_ROUTERS.
    """
    self._routers = routers

  @cachedProperty
  def routers(self):
    if self._routers is None:
      self._routers = settings.DATABASE_ROUTERS
    routers = []
    for r in self._routers:
      if isinstance(r, six.stringTypes):
        router = importString(r)()
      else:
        router = r
      routers.append(router)
    return routers

  def _routerFunc(action):
    def _routeDb(self, modal, **hints):
      chosenDb = None
      for router in self.routers:
        try:
          method = getattr(router, action)
        except AttributeError:
          # If the router doesn't have a method, skip to the next one.
          pass
        else:
          chosenDb = method(modal, **hints)
          if chosenDb:
            return chosenDb
      try:
        return hints['instance']._state.db or DEFAULT_DB_ALIAS
      except KeyError:
        return DEFAULT_DB_ALIAS
    return _routeDb

  dbForRead = _routerFunc('dbForRead')
  dbForWrite = _routerFunc('dbForWrite')

  def allowRelation(self, obj1, obj2, **hints):
    for router in self.routers:
      try:
        method = router.allowRelation
      except AttributeError:
        # If the router doesn't have a method, skip to the next one.
        pass
      else:
        allow = method(obj1, obj2, **hints)
        if allow is not None:
          return allow
    return obj1._state.db == obj2._state.db

  def allowMigrate(self, db, modal):
    for router in self.routers:
      try:
        try:
          method = router.allowMigrate
        except AttributeError:
          method = router.allowSyncdb
          warnings.warn(
            'Router.allowSyncdb has been deprecated and will stop working in Theory 1.9. '
            'Rename the method to allowMigrate.',
            RemovedInTheory19Warning, stacklevel=2)
      except AttributeError:
        # If the router doesn't have a method, skip to the next one.
        pass
      else:
        allow = method(db, modal)
        if allow is not None:
          return allow
    return True

  def getMigratableModels(self, appConfig, db, includeAutoCreated=False):
    """
    Return app model allowed to be synchronized on provided db.
    """
    model = appConfig.getModels(includeAutoCreated=includeAutoCreated)
    return [modal for modal in model if self.allowMigrate(db, modal)]
