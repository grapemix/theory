"""
PostgreSQL database backend for Theory.

Requires psycopg 2: http://initd.org/projects/psycopg2
"""

from theory.conf import settings
from theory.db.backends import (BaseDatabaseFeatures, BaseDatabaseWrapper,
  BaseDatabaseValidation)
from theory.db.backends.postgresqlPsycopg2.operations import DatabaseOperations
from theory.db.backends.postgresqlPsycopg2.client import DatabaseClient
from theory.db.backends.postgresqlPsycopg2.creation import DatabaseCreation
from theory.db.backends.postgresqlPsycopg2.version import getVersion
from theory.db.backends.postgresqlPsycopg2.introspection import DatabaseIntrospection
from theory.db.backends.postgresqlPsycopg2.schema import DatabaseSchemaEditor
from theory.db.utils import InterfaceError
from theory.utils.encoding import forceStr
from theory.utils.functional import cachedProperty
from theory.utils.safestring import SafeText, SafeBytes
from theory.utils.timezone import utc

try:
  import psycopg2 as Database
  import psycopg2.extensions
except ImportError as e:
  from theory.core.exceptions import ImproperlyConfigured
  raise ImproperlyConfigured("Error loading psycopg2 module: %s" % e)

DatabaseError = Database.DatabaseError
IntegrityError = Database.IntegrityError

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)
psycopg2.extensions.register_adapter(SafeBytes, psycopg2.extensions.QuotedString)
psycopg2.extensions.register_adapter(SafeText, psycopg2.extensions.QuotedString)


def utcTzinfoFactory(offset):
  if offset != 0:
    raise AssertionError("database connection isn't set to UTC")
  return utc


class DatabaseFeatures(BaseDatabaseFeatures):
  needsDatetimeStringCast = False
  canReturnIdFromInsert = True
  requiresRollbackOnDirtyTransaction = True
  hasRealDatatype = True
  canDeferConstraintChecks = True
  hasSelectForUpdate = True
  hasSelectForUpdateNowait = True
  hasBulkInsert = True
  usesSavepoints = True
  supportsTablespaces = True
  supportsTransactions = True
  canIntrospectIpAddressField = True
  canIntrospectSmallIntegerField = True
  canDistinctOnFields = True
  canRollbackDdl = True
  supportsCombinedAlters = True
  nullsOrderLargest = True
  closedCursorErrorClass = InterfaceError
  hasCaseInsensitiveLike = False
  requiresSqlparseForSplitting = False


class DatabaseWrapper(BaseDatabaseWrapper):
  vendor = 'postgresql'
  operators = {
    'exact': '= %s',
    'iexact': '= UPPER(%s)',
    'contains': 'LIKE %s',
    'icontains': 'LIKE UPPER(%s)',
    'regex': '~ %s',
    'iregex': '~* %s',
    'gt': '> %s',
    'gte': '>= %s',
    'lt': '< %s',
    'lte': '<= %s',
    'startswith': 'LIKE %s',
    'endswith': 'LIKE %s',
    'istartswith': 'LIKE UPPER(%s)',
    'iendswith': 'LIKE UPPER(%s)',
  }

  patternOps = {
    'startswith': "LIKE %s || '%%%%'",
    'istartswith': "LIKE UPPER(%s) || '%%%%'",
  }

  Database = Database

  def __init__(self, *args, **kwargs):
    super(DatabaseWrapper, self).__init__(*args, **kwargs)

    opts = self.settingsDict["OPTIONS"]
    RC = psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED
    self.isolationLevel = opts.get('isolationLevel', RC)

    self.features = DatabaseFeatures(self)
    self.ops = DatabaseOperations(self)
    self.client = DatabaseClient(self)
    self.creation = DatabaseCreation(self)
    self.introspection = DatabaseIntrospection(self)
    self.validation = BaseDatabaseValidation(self)

  def getConnectionParams(self):
    settingsDict = self.settingsDict
    # None may be used to connect to the default 'postgres' db
    if settingsDict['NAME'] == '':
      from theory.core.exceptions import ImproperlyConfigured
      raise ImproperlyConfigured(
        "settings.DATABASES is improperly configured. "
        "Please supply the NAME value.")
    connParams = {
      'database': settingsDict['NAME'] or 'postgres',
    }
    connParams.update(settingsDict['OPTIONS'])
    if 'autocommit' in connParams:
      del connParams['autocommit']
    if 'isolationLevel' in connParams:
      del connParams['isolationLevel']
    if settingsDict['USER']:
      connParams['user'] = settingsDict['USER']
    if settingsDict['PASSWORD']:
      connParams['password'] = forceStr(settingsDict['PASSWORD'])
    if settingsDict['HOST']:
      connParams['host'] = settingsDict['HOST']
    if settingsDict['PORT']:
      connParams['port'] = settingsDict['PORT']
    return connParams

  def getNewConnection(self, connParams):
    return Database.connect(**connParams)

  def initConnectionState(self):
    settingsDict = self.settingsDict
    self.connection.set_client_encoding('UTF8')
    tz = 'UTC' if settings.USE_TZ else settingsDict.get('TIME_ZONE')
    if tz:
      try:
        getParameterStatus = self.connection.getParameterStatus
      except AttributeError:
        # psycopg2 < 2.0.12 doesn't have getParameterStatus
        connTz = None
      else:
        connTz = getParameterStatus('TimeZone')

      if connTz != tz:
        cursor = self.connection.cursor()
        try:
          cursor.execute(self.ops.setTimeZoneSql(), [tz])
        finally:
          cursor.close()
        # Commit after setting the time zone (see #17062)
        if not self.getAutocommit():
          self.connection.commit()

  def createCursor(self):
    cursor = self.connection.cursor()
    cursor.tzinfo_factory = utcTzinfoFactory if settings.USE_TZ else None
    return cursor

  def _setIsolationLevel(self, isolationLevel):
    assert isolationLevel in range(1, 5)     # Use setAutocommit for level = 0
    if self.psycopg2Version >= (2, 4, 2):
      self.connection.setSession(isolationLevel=isolationLevel)
    else:
      self.connection.setIsolationLevel(isolationLevel)

  def _setAutocommit(self, autocommit):
    with self.wrapDatabaseErrors:
      if self.psycopg2Version >= (2, 4, 2):
        self.connection.autocommit = autocommit
      else:
        if autocommit:
          level = psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
        else:
          level = self.isolationLevel
        self.connection.setIsolationLevel(level)

  def checkConstraints(self, tableNames=None):
    """
    To check constraints, we set constraints to immediate. Then, when, we're done we must ensure they
    are returned to deferred.
    """
    self.cursor().execute('SET CONSTRAINTS ALL IMMEDIATE')
    self.cursor().execute('SET CONSTRAINTS ALL DEFERRED')

  def isUsable(self):
    try:
      # Use a psycopg cursor directly, bypassing Theory's utilities.
      self.connection.cursor().execute("SELECT 1")
    except Database.Error:
      return False
    else:
      return True

  def schemaEditor(self, *args, **kwargs):
    "Returns a new instance of this backend's SchemaEditor"
    return DatabaseSchemaEditor(self, *args, **kwargs)

  @cachedProperty
  def psycopg2Version(self):
    version = psycopg2.__version__.split(' ', 1)[0]
    return tuple(int(v) for v in version.split('.'))

  @cachedProperty
  def pgVersion(self):
    with self.temporaryConnection():
      return getVersion(self.connection)
