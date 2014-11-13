"""
Oracle database backend for Theory.

Requires cx_Oracle: http://cx-oracle.sourceforge.net/
"""
from __future__ import unicode_literals

import datetime
import decimal
import re
import platform
import sys
import warnings


def _setupEnvironment(environ):
  # Cygwin requires some special voodoo to set the environment variables
  # properly so that Oracle will see them.
  if platform.system().upper().startswith('CYGWIN'):
    try:
      import ctypes
    except ImportError as e:
      from theory.core.exceptions import ImproperlyConfigured
      raise ImproperlyConfigured("Error loading ctypes: %s; "
                    "the Oracle backend requires ctypes to "
                    "operate correctly under Cygwin." % e)
    kernel32 = ctypes.CDLL('kernel32')
    for name, value in environ:
      kernel32.SetEnvironmentVariableA(name, value)
  else:
    import os
    os.environ.update(environ)

_setupEnvironment([
  # Oracle takes client-side character set encoding from the environment.
  ('NLS_LANG', '.UTF8'),
  # This prevents unicode from getting mangled by getting encoded into the
  # potentially non-unicode database character set.
  ('ORA_NCHAR_LITERAL_REPLACE', 'TRUE'),
])


try:
  import cx_Oracle as Database
except ImportError as e:
  from theory.core.exceptions import ImproperlyConfigured
  raise ImproperlyConfigured("Error loading cx_Oracle module: %s" % e)

try:
  import pytz
except ImportError:
  pytz = None

from theory.conf import settings
from theory.db import utils
from theory.db.backends import (BaseDatabaseFeatures, BaseDatabaseOperations,
  BaseDatabaseWrapper, BaseDatabaseValidation, utils as backendUtils)
from theory.db.backends.oracle.client import DatabaseClient
from theory.db.backends.oracle.creation import DatabaseCreation
from theory.db.backends.oracle.introspection import DatabaseIntrospection
from theory.db.backends.oracle.schema import DatabaseSchemaEditor
from theory.db.utils import InterfaceError
from theory.utils import six, timezone
from theory.utils.encoding import forceBytes, forceText
from theory.utils.functional import cachedProperty


DatabaseError = Database.DatabaseError
IntegrityError = Database.IntegrityError

# Check whether cx_Oracle was compiled with the WITH_UNICODE option if cx_Oracle is pre-5.1. This will
# also be True for cx_Oracle 5.1 and in Python 3.0. See #19606
if int(Database.version.split('.', 1)[0]) >= 5 and \
    (int(Database.version.split('.', 2)[1]) >= 1 or
     not hasattr(Database, 'UNICODE')):
  convertUnicode = forceText
else:
  convertUnicode = forceBytes


class OracleDatetime(datetime.datetime):
  """
  A datetime object, with an additional class attribute
  to tell cx_Oracle to save the microseconds too.
  """
  inputSize = Database.TIMESTAMP

  @classmethod
  def fromDatetime(cls, dt):
    return OracleDatetime(dt.year, dt.month, dt.day,
                dt.hour, dt.minute, dt.second, dt.microsecond)


class DatabaseFeatures(BaseDatabaseFeatures):
  emptyFetchmanyValue = ()
  needsDatetimeStringCast = False
  interpretsEmptyStringsAsNulls = True
  usesSavepoints = True
  hasSelectForUpdate = True
  hasSelectForUpdateNowait = True
  canReturnIdFromInsert = True
  allowSlicedSubqueries = False
  supportsSubqueriesInGroupBy = False
  supportsTransactions = True
  supportsTimezones = False
  hasZoneinfoDatabase = pytz is not None
  supportsBitwiseOr = False
  canDeferConstraintChecks = True
  supportsPartiallyNullableUniqueConstraints = False
  hasBulkInsert = True
  supportsTablespaces = True
  supportsSequenceReset = False
  canIntrospectMaxLength = False
  canIntrospectTimeField = False
  atomicTransactions = False
  supportsCombinedAlters = False
  nullsOrderLargest = True
  requiresLiteralDefaults = True
  connectionPersistsOldColumns = True
  closedCursorErrorClass = InterfaceError
  bareSelectSuffix = " FROM DUAL"
  uppercasesColumnNames = True
  # select for update with limit can be achieved on Oracle, but not with the current backend.
  supportsSelectForUpdateWithLimit = False


class DatabaseOperations(BaseDatabaseOperations):
  compilerModule = "theory.db.backends.oracle.compiler"

  # Oracle uses NUMBER(11) and NUMBER(19) for integer fields.
  integerFieldRanges = {
    'SmallIntegerField': (-99999999999, 99999999999),
    'IntegerField': (-99999999999, 99999999999),
    'BigIntegerField': (-9999999999999999999, 9999999999999999999),
    'PositiveSmallIntegerField': (0, 99999999999),
    'PositiveIntegerField': (0, 99999999999),
  }

  def autoincSql(self, table, column):
    # To simulate auto-incrementing primary keys in Oracle, we have to
    # create a sequence and a trigger.
    sqName = self._getSequenceName(table)
    trName = self._getTriggerName(table)
    tblName = self.quoteName(table)
    colName = self.quoteName(column)
    sequenceSql = """
DECLARE
  i INTEGER;
BEGIN
  SELECT COUNT(*) INTO i FROM USER_CATALOG
    WHERE TABLE_NAME = '%(sqName)s' AND TABLE_TYPE = 'SEQUENCE';
  IF i = 0 THEN
    EXECUTE IMMEDIATE 'CREATE SEQUENCE "%(sqName)s"';
  END IF;
END;
/""" % locals()
    triggerSql = """
CREATE OR REPLACE TRIGGER "%(trName)s"
BEFORE INSERT ON %(tblName)s
FOR EACH ROW
WHEN (new.%(colName)s IS NULL)
  BEGIN
    SELECT "%(sqName)s".nextval
    INTO :new.%(colName)s FROM dual;
  END;
/""" % locals()
    return sequenceSql, triggerSql

  def cacheKeyCullingSql(self):
    return """
      SELECT cacheKey
       FROM (SELECT cacheKey, rank() OVER (ORDER BY cacheKey) AS rank FROM %s)
       WHERE rank = %%s + 1
    """

  def dateExtractSql(self, lookupType, fieldName):
    if lookupType == 'weekDay':
      # TO_CHAR(field, 'D') returns an integer from 1-7, where 1=Sunday.
      return "TO_CHAR(%s, 'D')" % fieldName
    else:
      # http://docs.oracle.com/cd/B1930601/server.102/b14200/functions050.htm
      return "EXTRACT(%s FROM %s)" % (lookupType.upper(), fieldName)

  def dateIntervalSql(self, sql, connector, timedelta):
    """
    Implements the interval functionality for expressions
    format for Oracle:
    (datefield + INTERVAL '3 00:03:20.000000' DAY(1) TO SECOND(6))
    """
    minutes, seconds = divmod(timedelta.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days = str(timedelta.days)
    dayPrecision = len(days)
    fmt = "(%s %s INTERVAL '%s %02d:%02d:%02d.%06d' DAY(%d) TO SECOND(6))"
    return fmt % (sql, connector, days, hours, minutes, seconds,
        timedelta.microseconds, dayPrecision)

  def dateTruncSql(self, lookupType, fieldName):
    # http://docs.oracle.com/cd/B1930601/server.102/b14200/functions230.htm#i1002084
    if lookupType in ('year', 'month'):
      return "TRUNC(%s, '%s')" % (fieldName, lookupType.upper())
    else:
      return "TRUNC(%s)" % fieldName

  # Oracle crashes with "ORA-03113: end-of-file on communication channel"
  # if the time zone name is passed in parameter. Use interpolation instead.
  # https://groups.google.com/forum/#!msg/theory-developers/zwQju7hbG78/9l934yelwfsJ
  # This regexp matches all time zone names from the zoneinfo database.
  _tznameRe = re.compile(r'^[\w/:+-]+$')

  def _convertFieldToTz(self, fieldName, tzname):
    if not self._tznameRe.match(tzname):
      raise ValueError("Invalid time zone name: %s" % tzname)
    # Convert from UTC to local time, returning TIMESTAMP WITH TIME ZONE.
    result = "(FROM_TZ(%s, '0:00') AT TIME ZONE '%s')" % (fieldName, tzname)
    # Extracting from a TIMESTAMP WITH TIME ZONE ignore the time zone.
    # Convert to a DATETIME, which is called DATE by Oracle. There's no
    # built-in function to do that; the easiest is to go through a string.
    result = "TO_CHAR(%s, 'YYYY-MM-DD HH24:MI:SS')" % result
    result = "TO_DATE(%s, 'YYYY-MM-DD HH24:MI:SS')" % result
    # Re-convert to a TIMESTAMP because EXTRACT only handles the date part
    # on DATE values, even though they actually store the time part.
    return "CAST(%s AS TIMESTAMP)" % result

  def datetimeExtractSql(self, lookupType, fieldName, tzname):
    if settings.USE_TZ:
      fieldName = self._convertFieldToTz(fieldName, tzname)
    if lookupType == 'weekDay':
      # TO_CHAR(field, 'D') returns an integer from 1-7, where 1=Sunday.
      sql = "TO_CHAR(%s, 'D')" % fieldName
    else:
      # http://docs.oracle.com/cd/B1930601/server.102/b14200/functions050.htm
      sql = "EXTRACT(%s FROM %s)" % (lookupType.upper(), fieldName)
    return sql, []

  def datetimeTruncSql(self, lookupType, fieldName, tzname):
    if settings.USE_TZ:
      fieldName = self._convertFieldToTz(fieldName, tzname)
    # http://docs.oracle.com/cd/B1930601/server.102/b14200/functions230.htm#i1002084
    if lookupType in ('year', 'month'):
      sql = "TRUNC(%s, '%s')" % (fieldName, lookupType.upper())
    elif lookupType == 'day':
      sql = "TRUNC(%s)" % fieldName
    elif lookupType == 'hour':
      sql = "TRUNC(%s, 'HH24')" % fieldName
    elif lookupType == 'minute':
      sql = "TRUNC(%s, 'MI')" % fieldName
    else:
      sql = fieldName    # Cast to DATE removes sub-second precision.
    return sql, []

  def convertValues(self, value, field):
    if isinstance(value, Database.LOB):
      value = value.read()
      if field and field.getInternalType() == 'TextField':
        value = forceText(value)

    # Oracle stores empty strings as null. We need to undo this in
    # order to adhere to the Theory convention of using the empty
    # string instead of null, but only if the field accepts the
    # empty string.
    if value is None and field and field.emptyStringsAllowed:
      if field.getInternalType() == 'BinaryField':
        value = b''
      else:
        value = ''
    # Convert 1 or 0 to True or False
    elif value in (1, 0) and field and field.getInternalType() in ('BooleanField', 'NullBooleanField'):
      value = bool(value)
    # Force floats to the correct type
    elif value is not None and field and field.getInternalType() == 'FloatField':
      value = float(value)
    # Convert floats to decimals
    elif value is not None and field and field.getInternalType() == 'DecimalField':
      value = backendUtils.typecastDecimal(field.formatNumber(value))
    # cx_Oracle always returns datetime.datetime objects for
    # DATE and TIMESTAMP columns, but Theory wants to see a
    # python datetime.date, .time, or .datetime.  We use the type
    # of the Field to determine which to cast to, but it's not
    # always available.
    # As a workaround, we cast to date if all the time-related
    # values are 0, or to time if the date is 1/1/1900.
    # This could be cleaned a bit by adding a method to the Field
    # classes to normalize values from the database (the toPython
    # method is used for validation and isn't what we want here).
    elif isinstance(value, Database.Timestamp):
      if field and field.getInternalType() == 'DateTimeField':
        pass
      elif field and field.getInternalType() == 'DateField':
        value = value.date()
      elif field and field.getInternalType() == 'TimeField' or (value.year == 1900 and value.month == value.day == 1):
        value = value.time()
      elif value.hour == value.minute == value.second == value.microsecond == 0:
        value = value.date()
    return value

  def deferrableSql(self):
    return " DEFERRABLE INITIALLY DEFERRED"

  def dropSequenceSql(self, table):
    return "DROP SEQUENCE %s;" % self.quoteName(self._getSequenceName(table))

  def fetchReturnedInsertId(self, cursor):
    return int(cursor._insertIdVar.getvalue())

  def fieldCastSql(self, dbType, internalType):
    if dbType and dbType.endswith('LOB'):
      return "DBMS_LOB.SUBSTR(%s)"
    else:
      return "%s"

  def lastExecutedQuery(self, cursor, sql, params):
    # http://cx-oracle.sourceforge.net/html/cursor.html#Cursor.statement
    # The DB API definition does not define this attribute.
    statement = cursor.statement
    if statement and six.PY2 and not isinstance(statement, unicode):
      statement = statement.decode('utf-8')
    # Unlike Psycopg's `query` and MySQLdb`'s `_lastExecuted`, CxOracle's
    # `statement` doesn't contain the query parameters. refs #20010.
    return super(DatabaseOperations, self).lastExecutedQuery(cursor, statement, params)

  def lastInsertId(self, cursor, tableName, pkName):
    sqName = self._getSequenceName(tableName)
    cursor.execute('SELECT "%s".currval FROM dual' % sqName)
    return cursor.fetchone()[0]

  def lookupCast(self, lookupType):
    if lookupType in ('iexact', 'icontains', 'istartswith', 'iendswith'):
      return "UPPER(%s)"
    return "%s"

  def maxInListSize(self):
    return 1000

  def maxNameLength(self):
    return 30

  def prepForIexactQuery(self, x):
    return x

  def processClob(self, value):
    if value is None:
      return ''
    return forceText(value.read())

  def quoteName(self, name):
    # SQL92 requires delimited (quoted) names to be case-sensitive.  When
    # not quoted, Oracle has case-insensitive behavior for identifiers, but
    # always defaults to uppercase.
    # We simplify things by making Oracle identifiers always uppercase.
    if not name.startswith('"') and not name.endswith('"'):
      name = '"%s"' % backendUtils.truncateName(name.upper(),
                        self.maxNameLength())
    # Oracle puts the query text into a (query % args) construct, so % signs
    # in names need to be escaped. The '%%' will be collapsed back to '%' at
    # that stage so we aren't really making the name longer here.
    name = name.replace('%', '%%')
    return name.upper()

  def randomFunctionSql(self):
    return "DBMS_RANDOM.RANDOM"

  def regexLookup9(self, lookupType):
    raise NotImplementedError("Regexes are not supported in Oracle before version 10g.")

  def regexLookup10(self, lookupType):
    if lookupType == 'regex':
      matchOption = "'c'"
    else:
      matchOption = "'i'"
    return 'REGEXP_LIKE(%%s, %%s, %s)' % matchOption

  def regexLookup(self, lookupType):
    # If regexLookup is called before it's been initialized, then create
    # a cursor to initialize it and recur.
    with self.connection.cursor():
      return self.connection.ops.regexLookup(lookupType)

  def returnInsertId(self):
    return "RETURNING %s INTO %%s", (InsertIdVar(),)

  def savepointCreateSql(self, sid):
    return convertUnicode("SAVEPOINT " + self.quoteName(sid))

  def savepointRollbackSql(self, sid):
    return convertUnicode("ROLLBACK TO SAVEPOINT " + self.quoteName(sid))

  def sqlFlush(self, style, tables, sequences, allowCascade=False):
    # Return a list of 'TRUNCATE x;', 'TRUNCATE y;',
    # 'TRUNCATE z;'... style SQL statements
    if tables:
      # Oracle does support TRUNCATE, but it seems to get us into
      # FK referential trouble, whereas DELETE FROM table works.
      sql = ['%s %s %s;' % (
        style.SQL_KEYWORD('DELETE'),
        style.SQL_KEYWORD('FROM'),
        style.SQL_FIELD(self.quoteName(table))
      ) for table in tables]
      # Since we've just deleted all the rows, running our sequence
      # ALTER code will reset the sequence to 0.
      sql.extend(self.sequenceResetByNameSql(style, sequences))
      return sql
    else:
      return []

  def sequenceResetByNameSql(self, style, sequences):
    sql = []
    for sequenceInfo in sequences:
      sequenceName = self._getSequenceName(sequenceInfo['table'])
      tableName = self.quoteName(sequenceInfo['table'])
      columnName = self.quoteName(sequenceInfo['column'] or 'id')
      query = _getSequenceResetSql() % {
        'sequence': sequenceName,
        'table': tableName,
        'column': columnName,
      }
      sql.append(query)
    return sql

  def sequenceResetSql(self, style, modalList):
    from theory.db import model
    output = []
    query = _getSequenceResetSql()
    for modal in modalList:
      for f in modal._meta.localFields:
        if isinstance(f, model.AutoField):
          tableName = self.quoteName(modal._meta.dbTable)
          sequenceName = self._getSequenceName(modal._meta.dbTable)
          columnName = self.quoteName(f.column)
          output.append(query % {'sequence': sequenceName,
                      'table': tableName,
                      'column': columnName})
          # Only one AutoField is allowed per modal, so don't
          # continue to loop
          break
      for f in modal._meta.manyToMany:
        if not f.rel.through:
          tableName = self.quoteName(f.m2mDbTable())
          sequenceName = self._getSequenceName(f.m2mDbTable())
          columnName = self.quoteName('id')
          output.append(query % {'sequence': sequenceName,
                      'table': tableName,
                      'column': columnName})
    return output

  def startTransactionSql(self):
    return ''

  def tablespaceSql(self, tablespace, inline=False):
    if inline:
      return "USING INDEX TABLESPACE %s" % self.quoteName(tablespace)
    else:
      return "TABLESPACE %s" % self.quoteName(tablespace)

  def valueToDbDate(self, value):
    """
    Transform a date value to an object compatible with what is expected
    by the backend driver for date columns.
    The default implementation transforms the date to text, but that is not
    necessary for Oracle.
    """
    return value

  def valueToDbDatetime(self, value):
    """
    Transform a datetime value to an object compatible with what is expected
    by the backend driver for datetime columns.

    If naive datetime is passed assumes that is in UTC. Normally Theory
    model.DateTimeField makes sure that if USE_TZ is True passed datetime
    is timezone aware.
    """

    if value is None:
      return None

    # cx_Oracle doesn't support tz-aware datetimes
    if timezone.isAware(value):
      if settings.USE_TZ:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
      else:
        raise ValueError("Oracle backend does not support timezone-aware datetimes when USE_TZ is False.")

    return OracleDatetime.fromDatetime(value)

  def valueToDbTime(self, value):
    if value is None:
      return None

    if isinstance(value, six.stringTypes):
      return datetime.datetime.strptime(value, '%H:%M:%S')

    # Oracle doesn't support tz-aware times
    if timezone.isAware(value):
      raise ValueError("Oracle backend does not support timezone-aware times.")

    return OracleDatetime(1900, 1, 1, value.hour, value.minute,
                value.second, value.microsecond)

  def yearLookupBoundsForDateField(self, value):
    # Create bounds as real date values
    first = datetime.date(value, 1, 1)
    last = datetime.date(value, 12, 31)
    return [first, last]

  def yearLookupBoundsForDatetimeField(self, value):
    # cx_Oracle doesn't support tz-aware datetimes
    bounds = super(DatabaseOperations, self).yearLookupBoundsForDatetimeField(value)
    if settings.USE_TZ:
      bounds = [b.astimezone(timezone.utc) for b in bounds]
    return [OracleDatetime.fromDatetime(b) for b in bounds]

  def combineExpression(self, connector, subExpressions):
    "Oracle requires special cases for %% and & operators in query expressions"
    if connector == '%%':
      return 'MOD(%s)' % ','.join(subExpressions)
    elif connector == '&':
      return 'BITAND(%s)' % ','.join(subExpressions)
    elif connector == '|':
      raise NotImplementedError("Bit-wise or is not supported in Oracle.")
    elif connector == '^':
      return 'POWER(%s)' % ','.join(subExpressions)
    return super(DatabaseOperations, self).combineExpression(connector, subExpressions)

  def _getSequenceName(self, table):
    nameLength = self.maxNameLength() - 3
    return '%s_SQ' % backendUtils.truncateName(table, nameLength).upper()

  def _getTriggerName(self, table):
    nameLength = self.maxNameLength() - 3
    return '%s_TR' % backendUtils.truncateName(table, nameLength).upper()

  def bulkInsertSql(self, fields, numValues):
    itemsSql = "SELECT %s FROM DUAL" % ", ".join(["%s"] * len(fields))
    return " UNION ALL ".join([itemsSql] * numValues)


class _UninitializedOperatorsDescriptor(object):

  def __get__(self, instance, owner):
    # If connection.operators is looked up before a connection has been
    # created, transparently initialize connection.operators to avert an
    # AttributeError.
    if instance is None:
      raise AttributeError("operators not available as class attribute")
    # Creating a cursor will initialize the operators.
    instance.cursor().close()
    return instance.__dict__['operators']


class DatabaseWrapper(BaseDatabaseWrapper):
  vendor = 'oracle'
  operators = _UninitializedOperatorsDescriptor()

  _standardOperators = {
    'exact': '= %s',
    'iexact': '= UPPER(%s)',
    'contains': "LIKE TRANSLATE(%s USING NCHAR_CS) ESCAPE TRANSLATE('\\' USING NCHAR_CS)",
    'icontains': "LIKE UPPER(TRANSLATE(%s USING NCHAR_CS)) ESCAPE TRANSLATE('\\' USING NCHAR_CS)",
    'gt': '> %s',
    'gte': '>= %s',
    'lt': '< %s',
    'lte': '<= %s',
    'startswith': "LIKE TRANSLATE(%s USING NCHAR_CS) ESCAPE TRANSLATE('\\' USING NCHAR_CS)",
    'endswith': "LIKE TRANSLATE(%s USING NCHAR_CS) ESCAPE TRANSLATE('\\' USING NCHAR_CS)",
    'istartswith': "LIKE UPPER(TRANSLATE(%s USING NCHAR_CS)) ESCAPE TRANSLATE('\\' USING NCHAR_CS)",
    'iendswith': "LIKE UPPER(TRANSLATE(%s USING NCHAR_CS)) ESCAPE TRANSLATE('\\' USING NCHAR_CS)",
  }

  _likecOperators = _standardOperators.copy()
  _likecOperators.update({
    'contains': "LIKEC %s ESCAPE '\\'",
    'icontains': "LIKEC UPPER(%s) ESCAPE '\\'",
    'startswith': "LIKEC %s ESCAPE '\\'",
    'endswith': "LIKEC %s ESCAPE '\\'",
    'istartswith': "LIKEC UPPER(%s) ESCAPE '\\'",
    'iendswith': "LIKEC UPPER(%s) ESCAPE '\\'",
  })

  Database = Database

  def __init__(self, *args, **kwargs):
    super(DatabaseWrapper, self).__init__(*args, **kwargs)

    self.features = DatabaseFeatures(self)
    useReturningInto = self.settingsDict["OPTIONS"].get('useReturningInto', True)
    self.features.canReturnIdFromInsert = useReturningInto
    self.ops = DatabaseOperations(self)
    self.client = DatabaseClient(self)
    self.creation = DatabaseCreation(self)
    self.introspection = DatabaseIntrospection(self)
    self.validation = BaseDatabaseValidation(self)

  def _connectString(self):
    settingsDict = self.settingsDict
    if not settingsDict['HOST'].strip():
      settingsDict['HOST'] = 'localhost'
    if settingsDict['PORT'].strip():
      dsn = Database.makedsn(settingsDict['HOST'],
                  int(settingsDict['PORT']),
                  settingsDict['NAME'])
    else:
      dsn = settingsDict['NAME']
    return "%s/%s@%s" % (settingsDict['USER'],
               settingsDict['PASSWORD'], dsn)

  def getConnectionParams(self):
    connParams = self.settingsDict['OPTIONS'].copy()
    if 'useReturningInto' in connParams:
      del connParams['useReturningInto']
    return connParams

  def getNewConnection(self, connParams):
    connString = convertUnicode(self._connectString())
    return Database.connect(connString, **connParams)

  def initConnectionState(self):
    cursor = self.createCursor()
    # Set the territory first. The territory overrides NLS_DATE_FORMAT
    # and NLS_TIMESTAMP_FORMAT to the territory default. When all of
    # these are set in single statement it isn't clear what is supposed
    # to happen.
    cursor.execute("ALTER SESSION SET NLS_TERRITORY = 'AMERICA'")
    # Set Oracle date to ANSI date format.  This only needs to execute
    # once when we create a new connection. We also set the Territory
    # to 'AMERICA' which forces Sunday to evaluate to a '1' in
    # TO_CHAR().
    cursor.execute(
      "ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'"
      " NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS.FF'"
      + (" TIME_ZONE = 'UTC'" if settings.USE_TZ else ''))
    cursor.close()
    if 'operators' not in self.__dict__:
      # Ticket #14149: Check whether our LIKE implementation will
      # work for this connection or we need to fall back on LIKEC.
      # This check is performed only once per DatabaseWrapper
      # instance per thread, since subsequent connections will use
      # the same settings.
      cursor = self.createCursor()
      try:
        cursor.execute("SELECT 1 FROM DUAL WHERE DUMMY %s"
                % self._standardOperators['contains'],
                ['X'])
      except DatabaseError:
        self.operators = self._likecOperators
      else:
        self.operators = self._standardOperators
      cursor.close()

    # There's no way for the DatabaseOperations class to know the
    # currently active Oracle version, so we do some setups here.
    # TODO: Multi-db support will need a better solution (a way to
    # communicate the current version).
    if self.oracleVersion is not None and self.oracleVersion <= 9:
      self.ops.regexLookup = self.ops.regexLookup9
    else:
      self.ops.regexLookup = self.ops.regexLookup10

    try:
      self.connection.stmtcachesize = 20
    except AttributeError:
      # Theory docs specify cx_Oracle version 4.3.1 or higher, but
      # stmtcachesize is available only in 4.3.2 and up.
      pass
    # Ensure all changes are preserved even when AUTOCOMMIT is False.
    if not self.getAutocommit():
      self.commit()

  def createCursor(self):
    return FormatStylePlaceholderCursor(self.connection)

  def _commit(self):
    if self.connection is not None:
      try:
        return self.connection.commit()
      except Database.DatabaseError as e:
        # cx_Oracle 5.0.4 raises a cx_Oracle.DatabaseError exception
        # with the following attributes and values:
        #  code = 2091
        #  message = 'ORA-02091: transaction rolled back
        #            'ORA-02291: integrity constraint (TEST_THEORYTEST.SYS
        #               _C00102056) violated - parent key not found'
        # We convert that particular case to our IntegrityError exception
        x = e.args[0]
        if hasattr(x, 'code') and hasattr(x, 'message') \
          and x.code == 2091 and 'ORA-02291' in x.message:
          six.reraise(utils.IntegrityError, utils.IntegrityError(*tuple(e.args)), sys.exc_info()[2])
        raise

  def schemaEditor(self, *args, **kwargs):
    "Returns a new instance of this backend's SchemaEditor"
    return DatabaseSchemaEditor(self, *args, **kwargs)

  # Oracle doesn't support releasing savepoints. But we fake them when query
  # logging is enabled to keep query counts consistent with other backends.
  def _savepointCommit(self, sid):
    if self.queriesLogged:
      self.queries.append({
        'sql': '-- RELEASE SAVEPOINT %s (faked)' % self.ops.quoteName(sid),
        'time': '0.000',
      })

  def _setAutocommit(self, autocommit):
    with self.wrapDatabaseErrors:
      self.connection.autocommit = autocommit

  def checkConstraints(self, tableNames=None):
    """
    To check constraints, we set constraints to immediate. Then, when, we're done we must ensure they
    are returned to deferred.
    """
    self.cursor().execute('SET CONSTRAINTS ALL IMMEDIATE')
    self.cursor().execute('SET CONSTRAINTS ALL DEFERRED')

  def isUsable(self):
    try:
      if hasattr(self.connection, 'ping'):    # Oracle 10g R2 and higher
        self.connection.ping()
      else:
        # Use a cx_Oracle cursor directly, bypassing Theory's utilities.
        self.connection.cursor().execute("SELECT 1 FROM DUAL")
    except Database.Error:
      return False
    else:
      return True

  @cachedProperty
  def oracleVersion(self):
    with self.temporaryConnection():
      version = self.connection.version
    try:
      return int(version.split('.')[0])
    except ValueError:
      return None


class OracleParam(object):
  """
  Wrapper object for formatting parameters for Oracle. If the string
  representation of the value is large enough (greater than 4000 characters)
  the input size needs to be set as CLOB. Alternatively, if the parameter
  has an `inputSize` attribute, then the value of the `inputSize` attribute
  will be used instead. Otherwise, no input size will be set for the
  parameter when executing the query.
  """

  def __init__(self, param, cursor, stringsOnly=False):
    # With raw SQL queries, datetimes can reach this function
    # without being converted by DateTimeField.getDbPrepValue.
    if settings.USE_TZ and (isinstance(param, datetime.datetime) and
                not isinstance(param, OracleDatetime)):
      if timezone.isNaive(param):
        warnings.warn("Oracle received a naive datetime (%s)"
               " while time zone support is active." % param,
               RuntimeWarning)
        defaultTimezone = timezone.getDefaultTimezone()
        param = timezone.makeAware(param, defaultTimezone)
      param = OracleDatetime.fromDatetime(param.astimezone(timezone.utc))

    stringSize = 0
    # Oracle doesn't recognize True and False correctly in Python 3.
    # The conversion done below works both in 2 and 3.
    if param is True:
      param = "1"
    elif param is False:
      param = "0"
    if hasattr(param, 'bindParameter'):
      self.forceBytes = param.bindParameter(cursor)
    elif isinstance(param, Database.Binary):
      self.forceBytes = param
    else:
      # To transmit to the database, we need Unicode if supported
      # To get size right, we must consider bytes.
      self.forceBytes = convertUnicode(param, cursor.charset,
                       stringsOnly)
      if isinstance(self.forceBytes, six.stringTypes):
        # We could optimize by only converting up to 4000 bytes here
        stringSize = len(forceBytes(param, cursor.charset, stringsOnly))
    if hasattr(param, 'inputSize'):
      # If parameter has `inputSize` attribute, use that.
      self.inputSize = param.inputSize
    elif stringSize > 4000:
      # Mark any string param greater than 4000 characters as a CLOB.
      self.inputSize = Database.CLOB
    else:
      self.inputSize = None


class VariableWrapper(object):
  """
  An adapter class for cursor variables that prevents the wrapped object
  from being converted into a string when used to instantiate an OracleParam.
  This can be used generally for any other object that should be passed into
  Cursor.execute as-is.
  """

  def __init__(self, var):
    self.var = var

  def bindParameter(self, cursor):
    return self.var

  def __getattr__(self, key):
    return getattr(self.var, key)

  def __setattr__(self, key, value):
    if key == 'var':
      self.__dict__[key] = value
    else:
      setattr(self.var, key, value)


class InsertIdVar(object):
  """
  A late-binding cursor variable that can be passed to Cursor.execute
  as a parameter, in order to receive the id of the row created by an
  insert statement.
  """

  def bindParameter(self, cursor):
    param = cursor.cursor.var(Database.NUMBER)
    cursor._insertIdVar = param
    return param


class FormatStylePlaceholderCursor(object):
  """
  Theory uses "format" (e.g. '%s') style placeholders, but Oracle uses ":var"
  style. This fixes it -- but note that if you want to use a literal "%s" in
  a query, you'll need to use "%%s".

  We also do automatic conversion between Unicode on the Python side and
  UTF-8 -- for talking to Oracle -- in here.
  """
  charset = 'utf-8'

  def __init__(self, connection):
    self.cursor = connection.cursor()
    # Necessary to retrieve decimal values without rounding error.
    self.cursor.numbersAsStrings = True
    # Default arraysize of 1 is highly sub-optimal.
    self.cursor.arraysize = 100

  def _formatParams(self, params):
    try:
      return dict((k, OracleParam(v, self, True)) for k, v in params.items())
    except AttributeError:
      return tuple(OracleParam(p, self, True) for p in params)

  def _guessInputSizes(self, paramsList):
    # Try dict handling; if that fails, treat as sequence
    if hasattr(paramsList[0], 'keys'):
      sizes = {}
      for params in paramsList:
        for k, value in params.items():
          if value.inputSize:
            sizes[k] = value.inputSize
      self.setinputsizes(**sizes)
    else:
      # It's not a list of dicts; it's a list of sequences
      sizes = [None] * len(paramsList[0])
      for params in paramsList:
        for i, value in enumerate(params):
          if value.inputSize:
            sizes[i] = value.inputSize
      self.setinputsizes(*sizes)

  def _paramGenerator(self, params):
    # Try dict handling; if that fails, treat as sequence
    if hasattr(params, 'items'):
      return dict((k, v.forceBytes) for k, v in params.items())
    else:
      return [p.forceBytes for p in params]

  def _fixForParams(self, query, params):
    # cx_Oracle wants no trailing ';' for SQL statements.  For PL/SQL, it
    # it does want a trailing ';' but not a trailing '/'.  However, these
    # characters must be included in the original query in case the query
    # is being passed to SQL*Plus.
    if query.endswith(';') or query.endswith('/'):
      query = query[:-1]
    if params is None:
      params = []
      query = convertUnicode(query, self.charset)
    elif hasattr(params, 'keys'):
      # Handle params as dict
      args = dict((k, ":%s" % k) for k in params.keys())
      query = convertUnicode(query % args, self.charset)
    else:
      # Handle params as sequence
      args = [(':arg%d' % i) for i in range(len(params))]
      query = convertUnicode(query % tuple(args), self.charset)
    return query, self._formatParams(params)

  def execute(self, query, params=None):
    query, params = self._fixForParams(query, params)
    self._guessInputSizes([params])
    try:
      return self.cursor.execute(query, self._paramGenerator(params))
    except Database.DatabaseError as e:
      # cx_Oracle <= 4.4.0 wrongly raises a DatabaseError for ORA-01400.
      if hasattr(e.args[0], 'code') and e.args[0].code == 1400 and not isinstance(e, IntegrityError):
        six.reraise(utils.IntegrityError, utils.IntegrityError(*tuple(e.args)), sys.exc_info()[2])
      raise

  def executemany(self, query, params=None):
    if not params:
      # No params given, nothing to do
      return None
    # uniform treatment for sequences and iterables
    paramsIter = iter(params)
    query, firstparams = self._fixForParams(query, next(paramsIter))
    # we build a list of formatted params; as we're going to traverse it
    # more than once, we can't make it lazy by using a generator
    formatted = [firstparams] + [self._formatParams(p) for p in paramsIter]
    self._guessInputSizes(formatted)
    try:
      return self.cursor.executemany(query,
                [self._paramGenerator(p) for p in formatted])
    except Database.DatabaseError as e:
      # cx_Oracle <= 4.4.0 wrongly raises a DatabaseError for ORA-01400.
      if hasattr(e.args[0], 'code') and e.args[0].code == 1400 and not isinstance(e, IntegrityError):
        six.reraise(utils.IntegrityError, utils.IntegrityError(*tuple(e.args)), sys.exc_info()[2])
      raise

  def fetchone(self):
    row = self.cursor.fetchone()
    if row is None:
      return row
    return _rowfactory(row, self.cursor)

  def fetchmany(self, size=None):
    if size is None:
      size = self.arraysize
    return tuple(_rowfactory(r, self.cursor) for r in self.cursor.fetchmany(size))

  def fetchall(self):
    return tuple(_rowfactory(r, self.cursor) for r in self.cursor.fetchall())

  def close(self):
    try:
      self.cursor.close()
    except Database.InterfaceError:
      # already closed
      pass

  def var(self, *args):
    return VariableWrapper(self.cursor.var(*args))

  def arrayvar(self, *args):
    return VariableWrapper(self.cursor.arrayvar(*args))

  def __getattr__(self, attr):
    if attr in self.__dict__:
      return self.__dict__[attr]
    else:
      return getattr(self.cursor, attr)

  def __iter__(self):
    return CursorIterator(self.cursor)


class CursorIterator(six.Iterator):

  """Cursor iterator wrapper that invokes our custom row factory."""

  def __init__(self, cursor):
    self.cursor = cursor
    self.iter = iter(cursor)

  def __iter__(self):
    return self

  def __next__(self):
    return _rowfactory(next(self.iter), self.cursor)


def _rowfactory(row, cursor):
  # Cast numeric values as the appropriate Python type based upon the
  # cursor description, and convert strings to unicode.
  casted = []
  for value, desc in zip(row, cursor.description):
    if value is not None and desc[1] is Database.NUMBER:
      precision, scale = desc[4:6]
      if scale == -127:
        if precision == 0:
          # NUMBER column: decimal-precision floating point
          # This will normally be an integer from a sequence,
          # but it could be a decimal value.
          if '.' in value:
            value = decimal.Decimal(value)
          else:
            value = int(value)
        else:
          # FLOAT column: binary-precision floating point.
          # This comes from FloatField columns.
          value = float(value)
      elif precision > 0:
        # NUMBER(p,s) column: decimal-precision fixed point.
        # This comes from IntField and DecimalField columns.
        if scale == 0:
          value = int(value)
        else:
          value = decimal.Decimal(value)
      elif '.' in value:
        # No type information. This normally comes from a
        # mathematical expression in the SELECT list. Guess int
        # or Decimal based on whether it has a decimal point.
        value = decimal.Decimal(value)
      else:
        value = int(value)
    # datetimes are returned as TIMESTAMP, except the results
    # of "dates" queries, which are returned as DATETIME.
    elif desc[1] in (Database.TIMESTAMP, Database.DATETIME):
      # Confirm that dt is naive before overwriting its tzinfo.
      if settings.USE_TZ and value is not None and timezone.isNaive(value):
        value = value.replace(tzinfo=timezone.utc)
    elif desc[1] in (Database.STRING, Database.FIXED_CHAR,
             Database.LONG_STRING):
      value = toUnicode(value)
    casted.append(value)
  return tuple(casted)


def toUnicode(s):
  """
  Convert strings to Unicode objects (and return all other data types
  unchanged).
  """
  if isinstance(s, six.stringTypes):
    return forceText(s)
  return s


def _getSequenceResetSql():
  # TODO: colorize this SQL code with style.SQL_KEYWORD(), etc.
  return """
DECLARE
  tableValue integer;
  seqValue integer;
BEGIN
  SELECT NVL(MAX(%(column)s), 0) INTO tableValue FROM %(table)s;
  SELECT NVL(lastNumber - cacheSize, 0) INTO seqValue FROM userSequences
      WHERE sequenceName = '%(sequence)s';
  WHILE tableValue > seqValue LOOP
    SELECT "%(sequence)s".nextval INTO seqValue FROM dual;
  END LOOP;
END;
/"""
