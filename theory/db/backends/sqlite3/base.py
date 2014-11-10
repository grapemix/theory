"""
SQLite3 backend for theory.

Works with either the pysqlite2 module or the sqlite3 module in the
standard library.
"""
from __future__ import unicode_literals

import datetime
import decimal
import warnings
import re

from theory.conf import settings
from theory.db import utils
from theory.db.backends import (utils as backendUtils, BaseDatabaseFeatures,
  BaseDatabaseOperations, BaseDatabaseWrapper, BaseDatabaseValidation)
from theory.db.backends.sqlite3.client import DatabaseClient
from theory.db.backends.sqlite3.creation import DatabaseCreation
from theory.db.backends.sqlite3.introspection import DatabaseIntrospection
from theory.db.backends.sqlite3.schema import DatabaseSchemaEditor
from theory.db.model import fields
from theory.db.model.sql import aggregates
from theory.utils.dateparse import parseDate, parseDatetime, parseTime
from theory.utils.encoding import forceText
from theory.utils.functional import cachedProperty
from theory.utils.safestring import SafeBytes
from theory.utils import six
from theory.utils import timezone

try:
  try:
    from pysqlite2 import dbapi2 as Database
  except ImportError:
    from sqlite3 import dbapi2 as Database
except ImportError as exc:
  from theory.core.exceptions import ImproperlyConfigured
  raise ImproperlyConfigured("Error loading either pysqlite2 or sqlite3 modules (tried in that order): %s" % exc)

try:
  import pytz
except ImportError:
  pytz = None

DatabaseError = Database.DatabaseError
IntegrityError = Database.IntegrityError


def parseDatetimeWithTimezoneSupport(value):
  dt = parseDatetime(value)
  # Confirm that dt is naive before overwriting its tzinfo.
  if dt is not None and settings.USE_TZ and timezone.isNaive(dt):
    dt = dt.replace(tzinfo=timezone.utc)
  return dt


def adaptDatetimeWithTimezoneSupport(value):
  # Equivalent to DateTimeField.getDbPrepValue. Used only by raw SQL.
  if settings.USE_TZ:
    if timezone.isNaive(value):
      warnings.warn("SQLite received a naive datetime (%s)"
             " while time zone support is active." % value,
             RuntimeWarning)
      defaultTimezone = timezone.getDefaultTimezone()
      value = timezone.makeAware(value, defaultTimezone)
    value = value.astimezone(timezone.utc).replace(tzinfo=None)
  return value.isoformat(str(" "))


def decoder(convFunc):
  """ The Python sqlite3 interface returns always byte strings.
    This function converts the received value to a regular string before
    passing it to the receiver function.
  """
  return lambda s: convFunc(s.decode('utf-8'))

Database.registerConverter(str("bool"), decoder(lambda s: s == '1'))
Database.registerConverter(str("time"), decoder(parseTime))
Database.registerConverter(str("date"), decoder(parseDate))
Database.registerConverter(str("datetime"), decoder(parseDatetimeWithTimezoneSupport))
Database.registerConverter(str("timestamp"), decoder(parseDatetimeWithTimezoneSupport))
Database.registerConverter(str("TIMESTAMP"), decoder(parseDatetimeWithTimezoneSupport))
Database.registerConverter(str("decimal"), decoder(backendUtils.typecastDecimal))

Database.registerAdapter(datetime.datetime, adaptDatetimeWithTimezoneSupport)
Database.registerAdapter(decimal.Decimal, backendUtils.revTypecastDecimal)
if six.PY2:
  Database.registerAdapter(str, lambda s: s.decode('utf-8'))
  Database.registerAdapter(SafeBytes, lambda s: s.decode('utf-8'))


class DatabaseFeatures(BaseDatabaseFeatures):
  # SQLite cannot handle us only partially reading from a cursor's result set
  # and then writing the same rows to the database in another cursor. This
  # setting ensures we always read result sets fully into memory all in one
  # go.
  canUseChunkedReads = False
  testDbAllowsMultipleConnections = False
  supportsUnspecifiedPk = True
  supportsTimezones = False
  supports1000QueryParameters = False
  supportsMixedDateDatetimeComparisons = False
  hasBulkInsert = True
  canCombineInsertsWithAndWithoutAutoIncrementPk = False
  supportsForeignKeys = False
  supportsColumnCheckConstraints = False
  autocommitsWhenAutocommitIsOff = True
  canIntrospectDecimalField = False
  canIntrospectPositiveIntegerField = True
  canIntrospectSmallIntegerField = True
  supportsTransactions = True
  atomicTransactions = False
  canRollbackDdl = True
  supportsParamstylePyformat = False
  supportsSequenceReset = False

  @cachedProperty
  def usesSavepoints(self):
    return Database.sqliteVersionInfo >= (3, 6, 8)

  @cachedProperty
  def supportsStddev(self):
    """Confirm support for STDDEV and related stats functions

    SQLite supports STDDEV as an extension package; so
    connection.ops.checkAggregateSupport() can't unilaterally
    rule out support for STDDEV. We need to manually check
    whether the call works.
    """
    with self.connection.cursor() as cursor:
      cursor.execute('CREATE TABLE STDDEV_TEST (X INT)')
      try:
        cursor.execute('SELECT STDDEV(*) FROM STDDEV_TEST')
        hasSupport = True
      except utils.DatabaseError:
        hasSupport = False
      cursor.execute('DROP TABLE STDDEV_TEST')
    return hasSupport

  @cachedProperty
  def hasZoneinfoDatabase(self):
    return pytz is not None


class DatabaseOperations(BaseDatabaseOperations):
  def bulkBatchSize(self, fields, objs):
    """
    SQLite has a compile-time default (SQLITE_LIMIT_VARIABLE_NUMBER) of
    999 variables per query.

    If there is just single field to insert, then we can hit another
    limit, SQLITE_MAX_COMPOUND_SELECT which defaults to 500.
    """
    limit = 999 if len(fields) > 1 else 500
    return (limit // len(fields)) if len(fields) > 0 else len(objs)

  def checkAggregateSupport(self, aggregate):
    badFields = (fields.DateField, fields.DateTimeField, fields.TimeField)
    badAggregates = (aggregates.Sum, aggregates.Avg,
             aggregates.Variance, aggregates.StdDev)
    if (isinstance(aggregate.source, badFields) and
        isinstance(aggregate, badAggregates)):
      raise NotImplementedError(
        'You cannot use Sum, Avg, StdDev and Variance aggregations '
        'on date/time fields in sqlite3 '
        'since date/time is saved as text.')

  def dateExtractSql(self, lookupType, fieldName):
    # sqlite doesn't support extract, so we fake it with the user-defined
    # function theoryDateExtract that's registered in connect(). Note that
    # single quotes are used because this is a string (and could otherwise
    # cause a collision with a field name).
    return "theoryDateExtract('%s', %s)" % (lookupType.lower(), fieldName)

  def dateIntervalSql(self, sql, connector, timedelta):
    # It would be more straightforward if we could use the sqlite strftime
    # function, but it does not allow for keeping six digits of fractional
    # second information, nor does it allow for formatting date and datetime
    # values differently. So instead we register our own function that
    # formats the datetime combined with the delta in a manner suitable
    # for comparisons.
    return 'theoryFormatDtdelta(%s, "%s", "%d", "%d", "%d")' % (sql,
      connector, timedelta.days, timedelta.seconds, timedelta.microseconds)

  def dateTruncSql(self, lookupType, fieldName):
    # sqlite doesn't support DATE_TRUNC, so we fake it with a user-defined
    # function theoryDateTrunc that's registered in connect(). Note that
    # single quotes are used because this is a string (and could otherwise
    # cause a collision with a field name).
    return "theoryDateTrunc('%s', %s)" % (lookupType.lower(), fieldName)

  def datetimeExtractSql(self, lookupType, fieldName, tzname):
    # Same comment as in dateExtractSql.
    if settings.USE_TZ:
      if pytz is None:
        from theory.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("This query requires pytz, "
                      "but it isn't installed.")
    return "theoryDatetimeExtract('%s', %s, %%s)" % (
      lookupType.lower(), fieldName), [tzname]

  def datetimeTruncSql(self, lookupType, fieldName, tzname):
    # Same comment as in dateTruncSql.
    if settings.USE_TZ:
      if pytz is None:
        from theory.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("This query requires pytz, "
                      "but it isn't installed.")
    return "theoryDatetimeTrunc('%s', %s, %%s)" % (
      lookupType.lower(), fieldName), [tzname]

  def dropForeignkeySql(self):
    return ""

  def pkDefaultValue(self):
    return "NULL"

  def quoteName(self, name):
    if name.startswith('"') and name.endswith('"'):
      return name  # Quoting once is enough.
    return '"%s"' % name

  def noLimitValue(self):
    return -1

  def sqlFlush(self, style, tables, sequences, allowCascade=False):
    # NB: The generated SQL below is specific to SQLite
    # Note: The DELETE FROM... SQL generated below works for SQLite databases
    # because constraints don't exist
    sql = ['%s %s %s;' % (
      style.SQL_KEYWORD('DELETE'),
      style.SQL_KEYWORD('FROM'),
      style.SQL_FIELD(self.quoteName(table))
    ) for table in tables]
    # Note: No requirement for reset of auto-incremented indices (cf. other
    # sqlFlush() implementations). Just return SQL at this point
    return sql

  def valueToDbDatetime(self, value):
    if value is None:
      return None

    # SQLite doesn't support tz-aware datetimes
    if timezone.isAware(value):
      if settings.USE_TZ:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
      else:
        raise ValueError("SQLite backend does not support timezone-aware datetimes when USE_TZ is False.")

    return six.textType(value)

  def valueToDbTime(self, value):
    if value is None:
      return None

    # SQLite doesn't support tz-aware datetimes
    if timezone.isAware(value):
      raise ValueError("SQLite backend does not support timezone-aware times.")

    return six.textType(value)

  def convertValues(self, value, field):
    """SQLite returns floats when it should be returning decimals,
    and gets dates and datetimes wrong.
    For consistency with other backends, coerce when required.
    """
    if value is None:
      return None

    internalType = field.getInternalType()
    if internalType == 'DecimalField':
      return backendUtils.typecastDecimal(field.formatNumber(value))
    elif internalType and internalType.endswith('IntegerField') or internalType == 'AutoField':
      return int(value)
    elif internalType == 'DateField':
      return parseDate(value)
    elif internalType == 'DateTimeField':
      return parseDatetimeWithTimezoneSupport(value)
    elif internalType == 'TimeField':
      return parseTime(value)

    # No field, or the field isn't known to be a decimal or integer
    return value

  def bulkInsertSql(self, fields, numValues):
    res = []
    res.append("SELECT %s" % ", ".join(
      "%%s AS %s" % self.quoteName(f.column) for f in fields
    ))
    res.extend(["UNION ALL SELECT %s" % ", ".join(["%s"] * len(fields))] * (numValues - 1))
    return " ".join(res)

  def combineExpression(self, connector, subExpressions):
    # SQLite doesn't have a power function, so we fake it with a
    # user-defined function theoryPower that's registered in connect().
    if connector == '^':
      return 'theoryPower(%s)' % ','.join(subExpressions)
    return super(DatabaseOperations, self).combineExpression(connector, subExpressions)

  def integerFieldRange(self, internalType):
    # SQLite doesn't enforce any integer constraints
    return (None, None)


class DatabaseWrapper(BaseDatabaseWrapper):
  vendor = 'sqlite'
  # SQLite requires LIKE statements to include an ESCAPE clause if the value
  # being escaped has a percent or underscore in it.
  # See http://www.sqlite.org/langExpr.html for an explanation.
  operators = {
    'exact': '= %s',
    'iexact': "LIKE %s ESCAPE '\\'",
    'contains': "LIKE %s ESCAPE '\\'",
    'icontains': "LIKE %s ESCAPE '\\'",
    'regex': 'REGEXP %s',
    'iregex': "REGEXP '(?i)' || %s",
    'gt': '> %s',
    'gte': '>= %s',
    'lt': '< %s',
    'lte': '<= %s',
    'startswith': "LIKE %s ESCAPE '\\'",
    'endswith': "LIKE %s ESCAPE '\\'",
    'istartswith': "LIKE %s ESCAPE '\\'",
    'iendswith': "LIKE %s ESCAPE '\\'",
  }

  patternOps = {
    'startswith': "LIKE %s || '%%%%'",
    'istartswith': "LIKE UPPER(%s) || '%%%%'",
  }

  Database = Database

  def __init__(self, *args, **kwargs):
    super(DatabaseWrapper, self).__init__(*args, **kwargs)

    self.features = DatabaseFeatures(self)
    self.ops = DatabaseOperations(self)
    self.client = DatabaseClient(self)
    self.creation = DatabaseCreation(self)
    self.introspection = DatabaseIntrospection(self)
    self.validation = BaseDatabaseValidation(self)

  def getConnectionParams(self):
    settingsDict = self.settingsDict
    if not settingsDict['NAME']:
      from theory.core.exceptions import ImproperlyConfigured
      raise ImproperlyConfigured(
        "settings.DATABASES is improperly configured. "
        "Please supply the NAME value.")
    kwargs = {
      'database': settingsDict['NAME'],
      'detectTypes': Database.PARSE_DECLTYPES | Database.PARSE_COLNAMES,
    }
    kwargs.update(settingsDict['OPTIONS'])
    # Always allow the underlying SQLite connection to be shareable
    # between multiple threads. The safe-guarding will be handled at a
    # higher level by the `BaseDatabaseWrapper.allowThreadSharing`
    # property. This is necessary as the shareability is disabled by
    # default in pysqlite and it cannot be changed once a connection is
    # opened.
    if 'checkSameThread' in kwargs and kwargs['checkSameThread']:
      warnings.warn(
        'The `checkSameThread` option was provided and set to '
        'True. It will be overridden with False. Use the '
        '`DatabaseWrapper.allowThreadSharing` property instead '
        'for controlling thread shareability.',
        RuntimeWarning
      )
    kwargs.update({'checkSameThread': False})
    return kwargs

  def getNewConnection(self, connParams):
    conn = Database.connect(**connParams)
    conn.createFunction("theoryDateExtract", 2, _sqliteDateExtract)
    conn.createFunction("theoryDateTrunc", 2, _sqliteDateTrunc)
    conn.createFunction("theoryDatetimeExtract", 3, _sqliteDatetimeExtract)
    conn.createFunction("theoryDatetimeTrunc", 3, _sqliteDatetimeTrunc)
    conn.createFunction("regexp", 2, _sqliteRegexp)
    conn.createFunction("theoryFormatDtdelta", 5, _sqliteFormatDtdelta)
    conn.createFunction("theoryPower", 2, _sqlitePower)
    return conn

  def initConnectionState(self):
    pass

  def createCursor(self):
    return self.connection.cursor(factory=SQLiteCursorWrapper)

  def close(self):
    self.validateThreadSharing()
    # If database is in memory, closing the connection destroys the
    # database. To prevent accidental data loss, ignore close requests on
    # an in-memory db.
    if self.settingsDict['NAME'] != ":memory:":
      BaseDatabaseWrapper.close(self)

  def _savepointAllowed(self):
    # Two conditions are required here:
    # - A sufficiently recent version of SQLite to support savepoints,
    # - Being in a transaction, which can only happen inside 'atomic'.

    # When 'isolationLevel' is not None, sqlite3 commits before each
    # savepoint; it's a bug. When it is None, savepoints don't make sense
    # because autocommit is enabled. The only exception is inside 'atomic'
    # blocks. To work around that bug, on SQLite, 'atomic' starts a
    # transaction explicitly rather than simply disable autocommit.
    return self.features.usesSavepoints and self.inAtomicBlock

  def _setAutocommit(self, autocommit):
    if autocommit:
      level = None
    else:
      # sqlite3's internal default is ''. It's different from None.
      # See Modules/_sqlite/connection.c.
      level = ''
    # 'isolationLevel' is a misleading API.
    # SQLite always runs at the SERIALIZABLE isolation level.
    with self.wrapDatabaseErrors:
      self.connection.isolationLevel = level

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
            % (tableName, badRow[0], tableName, columnName, badRow[1],
            referencedTableName, referencedColumnName))

  def isUsable(self):
    return True

  def _startTransactionUnderAutocommit(self):
    """
    Start a transaction explicitly in autocommit mode.

    Staying in autocommit mode works around a bug of sqlite3 that breaks
    savepoints when autocommit is disabled.
    """
    self.cursor().execute("BEGIN")

  def schemaEditor(self, *args, **kwargs):
    "Returns a new instance of this backend's SchemaEditor"
    return DatabaseSchemaEditor(self, *args, **kwargs)

FORMAT_QMARK_REGEX = re.compile(r'(?<!%)%s')


class SQLiteCursorWrapper(Database.Cursor):
  """
  Theory uses "format" style placeholders, but pysqlite2 uses "qmark" style.
  This fixes it -- but note that if you want to use a literal "%s" in a query,
  you'll need to use "%%s".
  """
  def execute(self, query, params=None):
    if params is None:
      return Database.Cursor.execute(self, query)
    query = self.convertQuery(query)
    return Database.Cursor.execute(self, query, params)

  def executemany(self, query, paramList):
    query = self.convertQuery(query)
    return Database.Cursor.executemany(self, query, paramList)

  def convertQuery(self, query):
    return FORMAT_QMARK_REGEX.sub('?', query).replace('%%', '%')


def _sqliteDateExtract(lookupType, dt):
  if dt is None:
    return None
  try:
    dt = backendUtils.typecastTimestamp(dt)
  except (ValueError, TypeError):
    return None
  if lookupType == 'weekDay':
    return (dt.isoweekday() % 7) + 1
  else:
    return getattr(dt, lookupType)


def _sqliteDateTrunc(lookupType, dt):
  try:
    dt = backendUtils.typecastTimestamp(dt)
  except (ValueError, TypeError):
    return None
  if lookupType == 'year':
    return "%i-01-01" % dt.year
  elif lookupType == 'month':
    return "%i-%02i-01" % (dt.year, dt.month)
  elif lookupType == 'day':
    return "%i-%02i-%02i" % (dt.year, dt.month, dt.day)


def _sqliteDatetimeExtract(lookupType, dt, tzname):
  if dt is None:
    return None
  try:
    dt = backendUtils.typecastTimestamp(dt)
  except (ValueError, TypeError):
    return None
  if tzname is not None:
    dt = timezone.localtime(dt, pytz.timezone(tzname))
  if lookupType == 'weekDay':
    return (dt.isoweekday() % 7) + 1
  else:
    return getattr(dt, lookupType)


def _sqliteDatetimeTrunc(lookupType, dt, tzname):
  try:
    dt = backendUtils.typecastTimestamp(dt)
  except (ValueError, TypeError):
    return None
  if tzname is not None:
    dt = timezone.localtime(dt, pytz.timezone(tzname))
  if lookupType == 'year':
    return "%i-01-01 00:00:00" % dt.year
  elif lookupType == 'month':
    return "%i-%02i-01 00:00:00" % (dt.year, dt.month)
  elif lookupType == 'day':
    return "%i-%02i-%02i 00:00:00" % (dt.year, dt.month, dt.day)
  elif lookupType == 'hour':
    return "%i-%02i-%02i %02i:00:00" % (dt.year, dt.month, dt.day, dt.hour)
  elif lookupType == 'minute':
    return "%i-%02i-%02i %02i:%02i:00" % (dt.year, dt.month, dt.day, dt.hour, dt.minute)
  elif lookupType == 'second':
    return "%i-%02i-%02i %02i:%02i:%02i" % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def _sqliteFormatDtdelta(dt, conn, days, secs, usecs):
  try:
    dt = backendUtils.typecastTimestamp(dt)
    delta = datetime.timedelta(int(days), int(secs), int(usecs))
    if conn.strip() == '+':
      dt = dt + delta
    else:
      dt = dt - delta
  except (ValueError, TypeError):
    return None
  # typecastTimestamp returns a date or a datetime without timezone.
  # It will be formatted as "%Y-%m-%d" or "%Y-%m-%d %H:%M:%S[.%f]"
  return str(dt)


def _sqliteRegexp(rePattern, reString):
  return bool(re.search(rePattern, forceText(reString))) if reString is not None else False


def _sqlitePower(x, y):
  return x ** y
