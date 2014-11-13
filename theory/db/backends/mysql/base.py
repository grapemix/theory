"""
MySQL database backend for Theory.

Requires MySQLdb: http://sourceforge.net/projects/mysql-python
"""
from __future__ import unicode_literals

import datetime
import re
import sys
import warnings

try:
  import MySQLdb as Database
except ImportError as e:
  from theory.core.exceptions import ImproperlyConfigured
  raise ImproperlyConfigured("Error loading MySQLdb module: %s" % e)

# We want version (1, 2, 1, 'final', 2) or later. We can't just use
# lexicographic ordering in this check because then (1, 2, 1, 'gamma')
# inadvertently passes the version test.
version = Database.versionInfo
if (version < (1, 2, 1) or (version[:3] == (1, 2, 1) and
    (len(version) < 5 or version[3] != 'final' or version[4] < 2))):
  from theory.core.exceptions import ImproperlyConfigured
  raise ImproperlyConfigured("MySQLdb-1.2.1p2 or newer is required; you have %s" % Database.__version__)

from MySQLdb.converters import conversions, Thing2Literal
from MySQLdb.constants import FIELD_TYPE, CLIENT

try:
  import pytz
except ImportError:
  pytz = None

from theory.conf import settings
from theory.db import utils
from theory.db.backends import (utils as backendUtils, BaseDatabaseFeatures,
  BaseDatabaseOperations, BaseDatabaseWrapper)
from theory.db.backends.mysql.client import DatabaseClient
from theory.db.backends.mysql.creation import DatabaseCreation
from theory.db.backends.mysql.introspection import DatabaseIntrospection
from theory.db.backends.mysql.validation import DatabaseValidation
from theory.utils.encoding import forceStr, forceText
from theory.db.backends.mysql.schema import DatabaseSchemaEditor
from theory.utils.functional import cachedProperty
from theory.utils.safestring import SafeBytes, SafeText
from theory.utils import six
from theory.utils import timezone

# Raise exceptions for database warnings if DEBUG is on
if settings.DEBUG:
  warnings.filterwarnings("error", category=Database.Warning)

DatabaseError = Database.DatabaseError
IntegrityError = Database.IntegrityError

# It's impossible to import datetimeOr_None directly from MySQLdb.times
parseDatetime = conversions[FIELD_TYPE.DATETIME]


def parseDatetimeWithTimezoneSupport(value):
  dt = parseDatetime(value)
  # Confirm that dt is naive before overwriting its tzinfo.
  if dt is not None and settings.USE_TZ and timezone.isNaive(dt):
    dt = dt.replace(tzinfo=timezone.utc)
  return dt


def adaptDatetimeWithTimezoneSupport(value, conv):
  # Equivalent to DateTimeField.getDbPrepValue. Used only by raw SQL.
  if settings.USE_TZ:
    if timezone.isNaive(value):
      warnings.warn("MySQL received a naive datetime (%s)"
             " while time zone support is active." % value,
             RuntimeWarning)
      defaultTimezone = timezone.getDefaultTimezone()
      value = timezone.makeAware(value, defaultTimezone)
    value = value.astimezone(timezone.utc).replace(tzinfo=None)
  return Thing2Literal(value.strftime("%Y-%m-%d %H:%M:%S"), conv)

# MySQLdb-1.2.1 returns TIME columns as timedelta -- they are more like
# timedelta in terms of actual behavior as they are signed and include days --
# and Theory expects time, so we still need to override that. We also need to
# add special handling for SafeText and SafeBytes as MySQLdb's type
# checking is too tight to catch those (see Theory ticket #6052).
# Finally, MySQLdb always returns naive datetime objects. However, when
# timezone support is active, Theory expects timezone-aware datetime objects.
theoryConversions = conversions.copy()
theoryConversions.update({
  FIELD_TYPE.TIME: backendUtils.typecastTime,
  FIELD_TYPE.DECIMAL: backendUtils.typecastDecimal,
  FIELD_TYPE.NEWDECIMAL: backendUtils.typecastDecimal,
  FIELD_TYPE.DATETIME: parseDatetimeWithTimezoneSupport,
  datetime.datetime: adaptDatetimeWithTimezoneSupport,
})

# This should match the numerical portion of the version numbers (we can treat
# versions like 5.0.24 and 5.0.24a as the same). Based on the list of version
# at http://dev.mysql.com/doc/refman/4.1/en/news.html and
# http://dev.mysql.com/doc/refman/5.0/en/news.html .
serverVersionRe = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{1,2})')


# MySQLdb-1.2.1 and newer automatically makes use of SHOW WARNINGS on
# MySQL-4.1 and newer, so the MysqlDebugWrapper is unnecessary. Since the
# point is to raise Warnings as exceptions, this can be done with the Python
# warning module, and this is setup when the connection is created, and the
# standard backendUtils.CursorDebugWrapper can be used. Also, using sqlMode
# TRADITIONAL will automatically cause most warnings to be treated as errors.

class CursorWrapper(object):
  """
  A thin wrapper around MySQLdb's normal cursor class so that we can catch
  particular exception instances and reraise them with the right types.

  Implemented as a wrapper, rather than a subclass, so that we aren't stuck
  to the particular underlying representation returned by Connection.cursor().
  """
  codesForIntegrityerror = (1048,)

  def __init__(self, cursor):
    self.cursor = cursor

  def execute(self, query, args=None):
    try:
      # args is None means no string interpolation
      return self.cursor.execute(query, args)
    except Database.OperationalError as e:
      # Map some error codes to IntegrityError, since they seem to be
      # misclassified and Theory would prefer the more logical place.
      if e.args[0] in self.codesForIntegrityerror:
        six.reraise(utils.IntegrityError, utils.IntegrityError(*tuple(e.args)), sys.exc_info()[2])
      raise

  def executemany(self, query, args):
    try:
      return self.cursor.executemany(query, args)
    except Database.OperationalError as e:
      # Map some error codes to IntegrityError, since they seem to be
      # misclassified and Theory would prefer the more logical place.
      if e.args[0] in self.codesForIntegrityerror:
        six.reraise(utils.IntegrityError, utils.IntegrityError(*tuple(e.args)), sys.exc_info()[2])
      raise

  def __getattr__(self, attr):
    if attr in self.__dict__:
      return self.__dict__[attr]
    else:
      return getattr(self.cursor, attr)

  def __iter__(self):
    return iter(self.cursor)

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    # Ticket #17671 - Close instead of passing thru to avoid backend
    # specific behavior.
    self.close()


class DatabaseFeatures(BaseDatabaseFeatures):
  emptyFetchmanyValue = ()
  updateCanSelfSelect = False
  allowsGroupByPk = True
  relatedFieldsMatchType = True
  allowSlicedSubqueries = False
  hasBulkInsert = True
  hasSelectForUpdate = True
  hasSelectForUpdateNowait = False
  supportsForwardReferences = False
  supportsLongModelNames = False
  # XXX MySQL DB-API drivers currently fail on binary data on Python 3.
  supportsBinaryField = six.PY2
  supportsMicrosecondPrecision = False
  supportsRegexBackreferencing = False
  supportsDateLookupUsingString = False
  canIntrospectBinaryField = False
  canIntrospectBooleanField = False
  supportsTimezones = False
  requiresExplicitNullOrderingWhenGrouping = True
  allowsAutoPk0 = False
  usesSavepoints = True
  atomicTransactions = False
  supportsColumnCheckConstraints = False

  def __init__(self, connection):
    super(DatabaseFeatures, self).__init__(connection)

  @cachedProperty
  def _mysqlStorageEngine(self):
    "Internal method used in Theory tests. Don't rely on this from your code"
    with self.connection.cursor() as cursor:
      cursor.execute('CREATE TABLE INTROSPECT_TEST (X INT)')
      # This command is MySQL specific; the second column
      # will tell you the default table type of the created
      # table. Since all Theory's test tables will have the same
      # table type, that's enough to evaluate the feature.
      cursor.execute("SHOW TABLE STATUS WHERE Name='INTROSPECT_TEST'")
      result = cursor.fetchone()
      cursor.execute('DROP TABLE INTROSPECT_TEST')
    return result[1]

  @cachedProperty
  def canIntrospectForeignKeys(self):
    "Confirm support for introspected foreign keys"
    return self._mysqlStorageEngine != 'MyISAM'

  @cachedProperty
  def hasZoneinfoDatabase(self):
    # MySQL accepts full time zones names (eg. Africa/Nairobi) but rejects
    # abbreviations (eg. EAT). When pytz isn't installed and the current
    # time zone is LocalTimezone (the only sensible value in this
    # context), the current time zone name will be an abbreviation. As a
    # consequence, MySQL cannot perform time zone conversions reliably.
    if pytz is None:
      return False

    # Test if the time zone definitions are installed.
    with self.connection.cursor() as cursor:
      cursor.execute("SELECT 1 FROM mysql.timeZone LIMIT 1")
      return cursor.fetchone() is not None


class DatabaseOperations(BaseDatabaseOperations):
  compilerModule = "theory.db.backends.mysql.compiler"

  # MySQL stores positive fields as UNSIGNED ints.
  integerFieldRanges = dict(BaseDatabaseOperations.integerFieldRanges,
    PositiveSmallIntegerField=(0, 4294967295),
    PositiveIntegerField=(0, 18446744073709551615),
  )

  def dateExtractSql(self, lookupType, fieldName):
    # http://dev.mysql.com/doc/mysql/en/date-and-time-functions.html
    if lookupType == 'weekDay':
      # DAYOFWEEK() returns an integer, 1-7, Sunday=1.
      # Note: WEEKDAY() returns 0-6, Monday=0.
      return "DAYOFWEEK(%s)" % fieldName
    else:
      return "EXTRACT(%s FROM %s)" % (lookupType.upper(), fieldName)

  def dateTruncSql(self, lookupType, fieldName):
    fields = ['year', 'month', 'day', 'hour', 'minute', 'second']
    format = ('%%Y-', '%%m', '-%%d', ' %%H:', '%%i', ':%%s')  # Use double percents to escape.
    formatDef = ('0000-', '01', '-01', ' 00:', '00', ':00')
    try:
      i = fields.index(lookupType) + 1
    except ValueError:
      sql = fieldName
    else:
      formatStr = ''.join([f for f in format[:i]] + [f for f in formatDef[i:]])
      sql = "CAST(DATE_FORMAT(%s, '%s') AS DATETIME)" % (fieldName, formatStr)
    return sql

  def datetimeExtractSql(self, lookupType, fieldName, tzname):
    if settings.USE_TZ:
      fieldName = "CONVERT_TZ(%s, 'UTC', %%s)" % fieldName
      params = [tzname]
    else:
      params = []
    # http://dev.mysql.com/doc/mysql/en/date-and-time-functions.html
    if lookupType == 'weekDay':
      # DAYOFWEEK() returns an integer, 1-7, Sunday=1.
      # Note: WEEKDAY() returns 0-6, Monday=0.
      sql = "DAYOFWEEK(%s)" % fieldName
    else:
      sql = "EXTRACT(%s FROM %s)" % (lookupType.upper(), fieldName)
    return sql, params

  def datetimeTruncSql(self, lookupType, fieldName, tzname):
    if settings.USE_TZ:
      fieldName = "CONVERT_TZ(%s, 'UTC', %%s)" % fieldName
      params = [tzname]
    else:
      params = []
    fields = ['year', 'month', 'day', 'hour', 'minute', 'second']
    format = ('%%Y-', '%%m', '-%%d', ' %%H:', '%%i', ':%%s')  # Use double percents to escape.
    formatDef = ('0000-', '01', '-01', ' 00:', '00', ':00')
    try:
      i = fields.index(lookupType) + 1
    except ValueError:
      sql = fieldName
    else:
      formatStr = ''.join([f for f in format[:i]] + [f for f in formatDef[i:]])
      sql = "CAST(DATE_FORMAT(%s, '%s') AS DATETIME)" % (fieldName, formatStr)
    return sql, params

  def dateIntervalSql(self, sql, connector, timedelta):
    return "(%s %s INTERVAL '%d 0:0:%d:%d' DAY_MICROSECOND)" % (sql, connector,
        timedelta.days, timedelta.seconds, timedelta.microseconds)

  def dropForeignkeySql(self):
    return "DROP FOREIGN KEY"

  def forceNoOrdering(self):
    """
    "ORDER BY NULL" prevents MySQL from implicitly ordering by grouped
    columns. If no ordering would otherwise be applied, we don't want any
    implicit sorting going on.
    """
    return ["NULL"]

  def fulltextSearchSql(self, fieldName):
    return 'MATCH (%s) AGAINST (%%s IN BOOLEAN MODE)' % fieldName

  def lastExecutedQuery(self, cursor, sql, params):
    # With MySQLdb, cursor objects have an (undocumented) "_lastExecuted"
    # attribute where the exact query sent to the database is saved.
    # See MySQLdb/cursors.py in the source distribution.
    return forceText(getattr(cursor, '_lastExecuted', None), errors='replace')

  def noLimitValue(self):
    # 2**64 - 1, as recommended by the MySQL documentation
    return 18446744073709551615

  def quoteName(self, name):
    if name.startswith("`") and name.endswith("`"):
      return name  # Quoting once is enough.
    return "`%s`" % name

  def randomFunctionSql(self):
    return 'RAND()'

  def sqlFlush(self, style, tables, sequences, allowCascade=False):
    # NB: The generated SQL below is specific to MySQL
    # 'TRUNCATE x;', 'TRUNCATE y;', 'TRUNCATE z;'... style SQL statements
    # to clear all tables of all data
    if tables:
      sql = ['SET FOREIGN_KEY_CHECKS = 0;']
      for table in tables:
        sql.append('%s %s;' % (
          style.SQL_KEYWORD('TRUNCATE'),
          style.SQL_FIELD(self.quoteName(table)),
        ))
      sql.append('SET FOREIGN_KEY_CHECKS = 1;')
      sql.extend(self.sequenceResetByNameSql(style, sequences))
      return sql
    else:
      return []

  def sequenceResetByNameSql(self, style, sequences):
    # Truncate already resets the AUTO_INCREMENT field from
    # MySQL version 5.0.13 onwards. Refs #16961.
    if self.connection.mysqlVersion < (5, 0, 13):
      return [
        "%s %s %s %s %s;" % (
          style.SQL_KEYWORD('ALTER'),
          style.SQL_KEYWORD('TABLE'),
          style.SQL_TABLE(self.quoteName(sequence['table'])),
          style.SQL_KEYWORD('AUTO_INCREMENT'),
          style.SQL_FIELD('= 1'),
        ) for sequence in sequences
      ]
    else:
      return []

  def validateAutopkValue(self, value):
    # MySQLism: zero in AUTO_INCREMENT field does not work. Refs #17653.
    if value == 0:
      raise ValueError('The database backend does not accept 0 as a '
               'value for AutoField.')
    return value

  def valueToDbDatetime(self, value):
    if value is None:
      return None

    # MySQL doesn't support tz-aware datetimes
    if timezone.isAware(value):
      if settings.USE_TZ:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
      else:
        raise ValueError("MySQL backend does not support timezone-aware datetimes when USE_TZ is False.")

    # MySQL doesn't support microseconds
    return six.textType(value.replace(microsecond=0))

  def valueToDbTime(self, value):
    if value is None:
      return None

    # MySQL doesn't support tz-aware times
    if timezone.isAware(value):
      raise ValueError("MySQL backend does not support timezone-aware times.")

    # MySQL doesn't support microseconds
    return six.textType(value.replace(microsecond=0))

  def yearLookupBoundsForDatetimeField(self, value):
    # Again, no microseconds
    first, second = super(DatabaseOperations, self).yearLookupBoundsForDatetimeField(value)
    return [first.replace(microsecond=0), second.replace(microsecond=0)]

  def maxNameLength(self):
    return 64

  def bulkInsertSql(self, fields, numValues):
    itemsSql = "(%s)" % ", ".join(["%s"] * len(fields))
    return "VALUES " + ", ".join([itemsSql] * numValues)

  def combineExpression(self, connector, subExpressions):
    """
    MySQL requires special cases for ^ operators in query expressions
    """
    if connector == '^':
      return 'POW(%s)' % ','.join(subExpressions)
    return super(DatabaseOperations, self).combineExpression(connector, subExpressions)


class DatabaseWrapper(BaseDatabaseWrapper):
  vendor = 'mysql'
  operators = {
    'exact': '= %s',
    'iexact': 'LIKE %s',
    'contains': 'LIKE BINARY %s',
    'icontains': 'LIKE %s',
    'regex': 'REGEXP BINARY %s',
    'iregex': 'REGEXP %s',
    'gt': '> %s',
    'gte': '>= %s',
    'lt': '< %s',
    'lte': '<= %s',
    'startswith': 'LIKE BINARY %s',
    'endswith': 'LIKE BINARY %s',
    'istartswith': 'LIKE %s',
    'iendswith': 'LIKE %s',
  }

  Database = Database

  def __init__(self, *args, **kwargs):
    super(DatabaseWrapper, self).__init__(*args, **kwargs)

    self.features = DatabaseFeatures(self)
    self.ops = DatabaseOperations(self)
    self.client = DatabaseClient(self)
    self.creation = DatabaseCreation(self)
    self.introspection = DatabaseIntrospection(self)
    self.validation = DatabaseValidation(self)

  def getConnectionParams(self):
    kwargs = {
      'conv': theoryConversions,
      'charset': 'utf8',
    }
    if six.PY2:
      kwargs['useUnicode'] = True
    settingsDict = self.settingsDict
    if settingsDict['USER']:
      kwargs['user'] = settingsDict['USER']
    if settingsDict['NAME']:
      kwargs['db'] = settingsDict['NAME']
    if settingsDict['PASSWORD']:
      kwargs['passwd'] = forceStr(settingsDict['PASSWORD'])
    if settingsDict['HOST'].startswith('/'):
      kwargs['unixSocket'] = settingsDict['HOST']
    elif settingsDict['HOST']:
      kwargs['host'] = settingsDict['HOST']
    if settingsDict['PORT']:
      kwargs['port'] = int(settingsDict['PORT'])
    # We need the number of potentially affected rows after an
    # "UPDATE", not the number of changed rows.
    kwargs['clientFlag'] = CLIENT.FOUND_ROWS
    kwargs.update(settingsDict['OPTIONS'])
    return kwargs

  def getNewConnection(self, connParams):
    conn = Database.connect(**connParams)
    conn.encoders[SafeText] = conn.encoders[six.textType]
    conn.encoders[SafeBytes] = conn.encoders[bytes]
    return conn

  def initConnectionState(self):
    with self.cursor() as cursor:
      # SQL_AUTO_IS_NULL in MySQL controls whether an AUTO_INCREMENT column
      # on a recently-inserted row will return when the field is tested for
      # NULL.  Disabling this value brings this aspect of MySQL in line with
      # SQL standards.
      cursor.execute('SET SQL_AUTO_IS_NULL = 0')

  def createCursor(self):
    cursor = self.connection.cursor()
    return CursorWrapper(cursor)

  def _rollback(self):
    try:
      BaseDatabaseWrapper._rollback(self)
    except Database.NotSupportedError:
      pass

  def _setAutocommit(self, autocommit):
    with self.wrapDatabaseErrors:
      self.connection.autocommit(autocommit)

  def disableConstraintChecking(self):
    """
    Disables foreign key checks, primarily for use in adding rows with forward references. Always returns True,
    to indicate constraint checks need to be re-enabled.
    """
    self.cursor().execute('SET foreignKeyChecks=0')
    return True

  def enableConstraintChecking(self):
    """
    Re-enable foreign key checks after they have been disabled.
    """
    # Override needsRollback in case constraintChecksDisabled is
    # nested inside transaction.atomic.
    self.needsRollback, needsRollback = False, self.needsRollback
    try:
      self.cursor().execute('SET foreignKeyChecks=1')
    finally:
      self.needsRollback = needsRollback

  def checkConstraints(self, tableNames=None):
    """
    Checks each table name in `tableNames` for rows with invalid foreign key references. This method is
    intended to be used in conjunction with `disableConstraintChecking()` and `enableConstraintChecking()`, to
    determine if rows with invalid references were entered while constraint checks were off.

    Raises an IntegrityError on the first invalid foreign key reference encountered (if any) and provides
    detailed information about the invalid reference in the error message.

    Backends can override this method if they can more directly apply constraint checking (e.g. via "SET CONSTRAINTS
    ALL IMMEDIATE")
    """
    cursor = self.cursor()
    if tableNames is None:
      tableNames = self.introspection.tableNames(cursor)
    for tableName in tableNames:
      primaryKeyColumnName = self.introspection.getPrimaryKeyColumn(cursor, tableName)
      if not primaryKeyColumnName:
        continue
      keyColumns = self.introspection.getKeyColumns(cursor, tableName)
      for columnName, referencedTableName, referencedColumnName in keyColumns:
        cursor.execute("""
          SELECT REFERRING.`%s`, REFERRING.`%s` FROM `%s` as REFERRING
          LEFT JOIN `%s` as REFERRED
          ON (REFERRING.`%s` = REFERRED.`%s`)
          WHERE REFERRING.`%s` IS NOT NULL AND REFERRED.`%s` IS NULL"""
          % (primaryKeyColumnName, columnName, tableName, referencedTableName,
          columnName, referencedColumnName, columnName, referencedColumnName))
        for badRow in cursor.fetchall():
          raise utils.IntegrityError("The row in table '%s' with primary key '%s' has an invalid "
            "foreign key: %s.%s contains a value '%s' that does not have a corresponding value in %s.%s."
            % (tableName, badRow[0],
            tableName, columnName, badRow[1],
            referencedTableName, referencedColumnName))

  def schemaEditor(self, *args, **kwargs):
    "Returns a new instance of this backend's SchemaEditor"
    return DatabaseSchemaEditor(self, *args, **kwargs)

  def isUsable(self):
    try:
      self.connection.ping()
    except Database.Error:
      return False
    else:
      return True

  @cachedProperty
  def mysqlVersion(self):
    with self.temporaryConnection():
      serverInfo = self.connection.getServerInfo()
    match = serverVersionRe.match(serverInfo)
    if not match:
      raise Exception('Unable to determine MySQL version from version string %r' % serverInfo)
    return tuple(int(x) for x in match.groups())
