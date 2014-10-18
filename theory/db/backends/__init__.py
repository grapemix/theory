import datetime
import time
import warnings

try:
  from theory.utils.six.moves import _thread as thread
except ImportError:
  from theory.utils.six.moves import _dummyThread as thread
from collections import namedtuple
from contextlib import contextmanager
from importlib import import_module

from theory.conf import settings
from theory.core import checks
from theory.db import DEFAULT_DB_ALIAS
from theory.db.backends.signals import connectionCreated
from theory.db.backends import utils
from theory.db.transaction import TransactionManagementError
from theory.db.utils import DatabaseError, DatabaseErrorWrapper, ProgrammingError
from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils.functional import cachedProperty
from theory.utils import six
from theory.utils import timezone


class BaseDatabaseWrapper(object):
  """
  Represents a database connection.
  """
  ops = None
  vendor = 'unknown'

  def __init__(self, settingsDict, alias=DEFAULT_DB_ALIAS,
         allowThreadSharing=False):
    # `settingsDict` should be a dictionary containing keys such as
    # NAME, USER, etc. It's called `settingsDict` instead of `settings`
    # to disambiguate it from Theory settings modules.
    self.connection = None
    self.queries = []
    self.settingsDict = settingsDict
    self.alias = alias
    self.useDebugCursor = False

    # Savepoint management related attributes
    self.savepointState = 0

    # Transaction management related attributes
    self.autocommit = False
    self.transactionState = []
    # Tracks if the connection is believed to be in transaction. This is
    # set somewhat aggressively, as the DBAPI doesn't make it easy to
    # deduce if the connection is in transaction or not.
    self._dirty = False
    # Tracks if the connection is in a transaction managed by 'atomic'.
    self.inAtomicBlock = False
    # List of savepoints created by 'atomic'
    self.savepointIds = []
    # Tracks if the outermost 'atomic' block should commit on exit,
    # ie. if autocommit was active on entry.
    self.commitOnExit = True
    # Tracks if the transaction should be rolled back to the next
    # available savepoint because of an exception in an inner block.
    self.needsRollback = False

    # Connection termination related attributes
    self.closeAt = None
    self.closedInTransaction = False
    self.errorsOccurred = False

    # Thread-safety related attributes
    self.allowThreadSharing = allowThreadSharing
    self._threadIdent = thread.get_ident()

  def __eq__(self, other):
    if isinstance(other, BaseDatabaseWrapper):
      return self.alias == other.alias
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    return hash(self.alias)

  @property
  def queriesLogged(self):
    return self.useDebugCursor or settings.DEBUG

  ##### Backend-specific methods for creating connections and cursors #####

  def getConnectionParams(self):
    """Returns a dict of parameters suitable for getNewConnection."""
    raise NotImplementedError('subclasses of BaseDatabaseWrapper may require a getConnectionParams() method')

  def getNewConnection(self, connParams):
    """Opens a connection to the database."""
    raise NotImplementedError('subclasses of BaseDatabaseWrapper may require a getNewConnection() method')

  def initConnectionState(self):
    """Initializes the database connection settings."""
    raise NotImplementedError('subclasses of BaseDatabaseWrapper may require an initConnectionState() method')

  def createCursor(self):
    """Creates a cursor. Assumes that a connection is established."""
    raise NotImplementedError('subclasses of BaseDatabaseWrapper may require a createCursor() method')

  ##### Backend-specific methods for creating connections #####

  def connect(self):
    """Connects to the database. Assumes that the connection is closed."""
    # In case the previous connection was closed while in an atomic block
    self.inAtomicBlock = False
    self.savepointIds = []
    self.needsRollback = False
    # Reset parameters defining when to close the connection
    maxAge = self.settingsDict['CONN_MAX_AGE']
    self.closeAt = None if maxAge is None else time.time() + maxAge
    self.closedInTransaction = False
    self.errorsOccurred = False
    # Establish the connection
    connParams = self.getConnectionParams()
    self.connection = self.getNewConnection(connParams)
    self.setAutocommit(self.settingsDict['AUTOCOMMIT'])
    self.initConnectionState()
    connectionCreated.send(sender=self.__class__, connection=self)

  def ensureConnection(self):
    """
    Guarantees that a connection to the database is established.
    """
    if self.connection is None:
      with self.wrapDatabaseErrors:
        self.connect()

  ##### Backend-specific wrappers for PEP-249 connection methods #####

  def _cursor(self):
    self.ensureConnection()
    with self.wrapDatabaseErrors:
      return self.createCursor()

  def _commit(self):
    if self.connection is not None:
      with self.wrapDatabaseErrors:
        return self.connection.commit()

  def _rollback(self):
    if self.connection is not None:
      with self.wrapDatabaseErrors:
        return self.connection.rollback()

  def _close(self):
    if self.connection is not None:
      with self.wrapDatabaseErrors:
        return self.connection.close()

  ##### Generic wrappers for PEP-249 connection methods #####

  def cursor(self):
    """
    Creates a cursor, opening a connection if necessary.
    """
    self.validateThreadSharing()
    if self.queriesLogged:
      cursor = self.makeDebugCursor(self._cursor())
    else:
      cursor = utils.CursorWrapper(self._cursor(), self)
    return cursor

  def commit(self):
    """
    Commits a transaction and resets the dirty flag.
    """
    self.validateThreadSharing()
    self.validateNoAtomicBlock()
    self._commit()
    self.setClean()
    # A successful commit means that the database connection works.
    self.errorsOccurred = False

  def rollback(self):
    """
    Rolls back a transaction and resets the dirty flag.
    """
    self.validateThreadSharing()
    self.validateNoAtomicBlock()
    self._rollback()
    self.setClean()
    # A successful rollback means that the database connection works.
    self.errorsOccurred = False

  def close(self):
    """
    Closes the connection to the database.
    """
    self.validateThreadSharing()
    # Don't call validateNoAtomicBlock() to avoid making it difficult
    # to get rid of a connection in an invalid state. The next connect()
    # will reset the transaction state anyway.
    if self.closedInTransaction or self.connection is None:
      return
    try:
      self._close()
    finally:
      if self.inAtomicBlock:
        self.closedInTransaction = True
        self.needsRollback = True
      else:
        self.connection = None
    self.setClean()

  ##### Backend-specific savepoint management methods #####

  def _savepoint(self, sid):
    with self.cursor() as cursor:
      cursor.execute(self.ops.savepointCreateSql(sid))

  def _savepointRollback(self, sid):
    with self.cursor() as cursor:
      cursor.execute(self.ops.savepointRollbackSql(sid))

  def _savepointCommit(self, sid):
    with self.cursor() as cursor:
      cursor.execute(self.ops.savepointCommitSql(sid))

  def _savepointAllowed(self):
    # Savepoints cannot be created outside a transaction
    return self.features.usesSavepoints and not self.getAutocommit()

  ##### Generic savepoint management methods #####

  def savepoint(self):
    """
    Creates a savepoint inside the current transaction. Returns an
    identifier for the savepoint that will be used for the subsequent
    rollback or commit. Does nothing if savepoints are not supported.
    """
    if not self._savepointAllowed():
      return

    threadIdent = thread.get_ident()
    tid = str(threadIdent).replace('-', '')

    self.savepointState += 1
    sid = "s%sX%d" % (tid, self.savepointState)

    self.validateThreadSharing()
    self._savepoint(sid)

    return sid

  def savepointRollback(self, sid):
    """
    Rolls back to a savepoint. Does nothing if savepoints are not supported.
    """
    if not self._savepointAllowed():
      return

    self.validateThreadSharing()
    self._savepointRollback(sid)

  def savepointCommit(self, sid):
    """
    Releases a savepoint. Does nothing if savepoints are not supported.
    """
    if not self._savepointAllowed():
      return

    self.validateThreadSharing()
    self._savepointCommit(sid)

  def cleanSavepoints(self):
    """
    Resets the counter used to generate unique savepoint ids in this thread.
    """
    self.savepointState = 0

  ##### Backend-specific transaction management methods #####

  def _setAutocommit(self, autocommit):
    """
    Backend-specific implementation to enable or disable autocommit.
    """
    raise NotImplementedError('subclasses of BaseDatabaseWrapper may require a _setAutocommit() method')

  ##### Generic transaction management methods #####

  def enterTransactionManagement(self, managed=True, forced=False):
    """
    Enters transaction management for a running thread. It must be balanced with
    the appropriate leaveTransactionManagement call, since the actual state is
    managed as a stack.

    The state and dirty flag are carried over from the surrounding block or
    from the settings, if there is no surrounding block (dirty is always false
    when no current block is running).

    If you switch off transaction management and there is a pending
    commit/rollback, the data will be committed, unless "forced" is True.
    """
    self.validateNoAtomicBlock()

    self.transactionState.append(managed)

    if not managed and self.isDirty() and not forced:
      self.commit()
      self.setClean()

    if managed == self.getAutocommit():
      self.setAutocommit(not managed)

  def leaveTransactionManagement(self):
    """
    Leaves transaction management for a running thread. A dirty flag is carried
    over to the surrounding block, as a commit will commit all changes, even
    those from outside. (Commits are on connection level.)
    """
    self.validateNoAtomicBlock()

    if self.transactionState:
      del self.transactionState[-1]
    else:
      raise TransactionManagementError(
        "This code isn't under transaction management")

    if self.transactionState:
      managed = self.transactionState[-1]
    else:
      managed = not self.settingsDict['AUTOCOMMIT']

    if self._dirty:
      self.rollback()
      if managed == self.getAutocommit():
        self.setAutocommit(not managed)
      raise TransactionManagementError(
        "Transaction managed block ended with pending COMMIT/ROLLBACK")

    if managed == self.getAutocommit():
      self.setAutocommit(not managed)

  def getAutocommit(self):
    """
    Check the autocommit state.
    """
    self.ensureConnection()
    return self.autocommit

  def setAutocommit(self, autocommit):
    """
    Enable or disable autocommit.
    """
    self.validateNoAtomicBlock()
    self.ensureConnection()
    self._setAutocommit(autocommit)
    self.autocommit = autocommit

  def getRollback(self):
    """
    Get the "needs rollback" flag -- for *advanced use* only.
    """
    if not self.inAtomicBlock:
      raise TransactionManagementError(
        "The rollback flag doesn't work outside of an 'atomic' block.")
    return self.needsRollback

  def setRollback(self, rollback):
    """
    Set or unset the "needs rollback" flag -- for *advanced use* only.
    """
    if not self.inAtomicBlock:
      raise TransactionManagementError(
        "The rollback flag doesn't work outside of an 'atomic' block.")
    self.needsRollback = rollback

  def validateNoAtomicBlock(self):
    """
    Raise an error if an atomic block is active.
    """
    if self.inAtomicBlock:
      raise TransactionManagementError(
        "This is forbidden when an 'atomic' block is active.")

  def validateNoBrokenTransaction(self):
    if self.needsRollback:
      raise TransactionManagementError(
        "An error occurred in the current transaction. You can't "
        "execute queries until the end of the 'atomic' block.")

  def abort(self):
    """
    Roll back any ongoing transaction and clean the transaction state
    stack.
    """
    if self._dirty:
      self.rollback()
    while self.transactionState:
      self.leaveTransactionManagement()

  def isDirty(self):
    """
    Returns True if the current transaction requires a commit for changes to
    happen.
    """
    return self._dirty

  def setDirty(self):
    """
    Sets a dirty flag for the current thread and code streak. This can be used
    to decide in a managed block of code to decide whether there are open
    changes waiting for commit.
    """
    if not self.getAutocommit():
      self._dirty = True

  def setClean(self):
    """
    Resets a dirty flag for the current thread and code streak. This can be used
    to decide in a managed block of code to decide whether a commit or rollback
    should happen.
    """
    self._dirty = False
    self.cleanSavepoints()

  ##### Foreign key constraints checks handling #####

  @contextmanager
  def constraintChecksDisabled(self):
    """
    Context manager that disables foreign key constraint checking.
    """
    disabled = self.disableConstraintChecking()
    try:
      yield
    finally:
      if disabled:
        self.enableConstraintChecking()

  def disableConstraintChecking(self):
    """
    Backends can implement as needed to temporarily disable foreign key
    constraint checking. Should return True if the constraints were
    disabled and will need to be reenabled.
    """
    return False

  def enableConstraintChecking(self):
    """
    Backends can implement as needed to re-enable foreign key constraint
    checking.
    """
    pass

  def checkConstraints(self, tableNames=None):
    """
    Backends can override this method if they can apply constraint
    checking (e.g. via "SET CONSTRAINTS ALL IMMEDIATE"). Should raise an
    IntegrityError if any invalid foreign key references are encountered.
    """
    pass

  ##### Connection termination handling #####

  def isUsable(self):
    """
    Tests if the database connection is usable.

    This function may assume that self.connection is not None.

    Actual implementations should take care not to raise exceptions
    as that may prevent Theory from recycling unusable connections.
    """
    raise NotImplementedError(
      "subclasses of BaseDatabaseWrapper may require an isUsable() method")

  def closeIfUnusableOrObsolete(self):
    """
    Closes the current connection if unrecoverable errors have occurred,
    or if it outlived its maximum age.
    """
    if self.connection is not None:
      # If the application didn't restore the original autocommit setting,
      # don't take chances, drop the connection.
      if self.getAutocommit() != self.settingsDict['AUTOCOMMIT']:
        self.close()
        return

      # If an exception other than DataError or IntegrityError occurred
      # since the last commit / rollback, check if the connection works.
      if self.errorsOccurred:
        if self.isUsable():
          self.errorsOccurred = False
        else:
          self.close()
          return

      if self.closeAt is not None and time.time() >= self.closeAt:
        self.close()
        return

  ##### Thread safety handling #####

  def validateThreadSharing(self):
    """
    Validates that the connection isn't accessed by another thread than the
    one which originally created it, unless the connection was explicitly
    authorized to be shared between threads (via the `allowThreadSharing`
    property). Raises an exception if the validation fails.
    """
    if not (self.allowThreadSharing
        or self._threadIdent == thread.get_ident()):
      raise DatabaseError("DatabaseWrapper objects created in a "
        "thread can only be used in that same thread. The object "
        "with alias '%s' was created in thread id %s and this is "
        "thread id %s."
        % (self.alias, self._threadIdent, thread.get_ident()))

  ##### Miscellaneous #####

  @cachedProperty
  def wrapDatabaseErrors(self):
    """
    Context manager and decorator that re-throws backend-specific database
    exceptions using Theory's common wrappers.
    """
    return DatabaseErrorWrapper(self)

  def makeDebugCursor(self, cursor):
    """
    Creates a cursor that logs all queries in self.queries.
    """
    return utils.CursorDebugWrapper(cursor, self)

  @contextmanager
  def temporaryConnection(self):
    """
    Context manager that ensures that a connection is established, and
    if it opened one, closes it to avoid leaving a dangling connection.
    This is useful for operations outside of the request-response cycle.

    Provides a cursor: with self.temporaryConnection() as cursor: ...
    """
    mustClose = self.connection is None
    cursor = self.cursor()
    try:
      yield cursor
    finally:
      cursor.close()
      if mustClose:
        self.close()

  def _startTransactionUnderAutocommit(self):
    """
    Only required when autocommitsWhenAutocommitIsOff = True.
    """
    raise NotImplementedError('subclasses of BaseDatabaseWrapper may require a _startTransactionUnderAutocommit() method')

  def schemaEditor(self, *args, **kwargs):
    "Returns a new instance of this backend's SchemaEditor"
    raise NotImplementedError('subclasses of BaseDatabaseWrapper may require a schemaEditor() method')


class BaseDatabaseFeatures(object):
  allowsGroupByPk = False
  # True if theory.db.backend.utils.typecastTimestamp is used on values
  # returned from dates() calls.
  needsDatetimeStringCast = True
  emptyFetchmanyValue = []
  updateCanSelfSelect = True

  # Does the backend distinguish between '' and None?
  interpretsEmptyStringsAsNulls = False

  # Does the backend allow inserting duplicate NULL rows in a nullable
  # unique field? All core backends implement this correctly, but other
  # databases such as SQL Server do not.
  supportsNullableUniqueConstraints = True

  # Does the backend allow inserting duplicate rows when a uniqueTogether
  # constraint exists and some fields are nullable but not all of them?
  supportsPartiallyNullableUniqueConstraints = True

  canUseChunkedReads = True
  canReturnIdFromInsert = False
  hasBulkInsert = False
  usesSavepoints = False
  canCombineInsertsWithAndWithoutAutoIncrementPk = False

  # If True, don't use integer foreign keys referring to, e.g., positive
  # integer primary keys.
  relatedFieldsMatchType = False
  allowSlicedSubqueries = True
  hasSelectForUpdate = False
  hasSelectForUpdateNowait = False

  supportsSelectRelated = True

  # Does the default test database allow multiple connections?
  # Usually an indication that the test database is in-memory
  testDbAllowsMultipleConnections = True

  # Can an object be saved without an explicit primary key?
  supportsUnspecifiedPk = False

  # Can a fixture contain forward references? i.e., are
  # FK constraints checked at the end of transaction, or
  # at the end of each save operation?
  supportsForwardReferences = True

  # Does a dirty transaction need to be rolled back
  # before the cursor can be used again?
  requiresRollbackOnDirtyTransaction = False

  # Does the backend allow very long modal names without error?
  supportsLongModelNames = True

  # Is there a REAL datatype in addition to floats/doubles?
  hasRealDatatype = False
  supportsSubqueriesInGroupBy = True
  supportsBitwiseOr = True

  supportsBinaryField = True

  # Do time/datetime fields have microsecond precision?
  supportsMicrosecondPrecision = True

  # Does the __regex lookup support backreferencing and grouping?
  supportsRegexBackreferencing = True

  # Can date/datetime lookups be performed using a string?
  supportsDateLookupUsingString = True

  # Can datetimes with timezones be used?
  supportsTimezones = True

  # Does the database have a copy of the zoneinfo database?
  hasZoneinfoDatabase = True

  # When performing a GROUP BY, is an ORDER BY NULL required
  # to remove any ordering?
  requiresExplicitNullOrderingWhenGrouping = False

  # Does the backend order NULL values as largest or smallest?
  nullsOrderLargest = False

  # Is there a 1000 item limit on query parameters?
  supports1000QueryParameters = True

  # Can an object have an autoincrement primary key of 0? MySQL says No.
  allowsAutoPk0 = True

  # Do we need to NULL a ForeignKey out, or can the constraint check be
  # deferred
  canDeferConstraintChecks = False

  # dateIntervalSql can properly handle mixed Date/DateTime fields and timedeltas
  supportsMixedDateDatetimeComparisons = True

  # Does the backend support tablespaces? Default to False because it isn't
  # in the SQL standard.
  supportsTablespaces = False

  # Does the backend reset sequences between tests?
  supportsSequenceReset = True

  # Can the backend determine reliably the length of a CharField?
  canIntrospectMaxLength = True

  # Can the backend determine reliably if a field is nullable?
  # Note that this is separate from interpretsEmptyStringsAsNulls,
  # although the latter feature, when true, interferes with correct
  # setting (and introspection) of CharFields' nullability.
  # This is True for all core backends.
  canIntrospectNull = True

  # Confirm support for introspected foreign keys
  # Every database can do this reliably, except MySQL,
  # which can't do it for MyISAM tables
  canIntrospectForeignKeys = True

  # Can the backend introspect an AutoField, instead of an IntegerField?
  canIntrospectAutofield = False

  # Can the backend introspect a BigIntegerField, instead of an IntegerField?
  canIntrospectBigIntegerField = True

  # Can the backend introspect an BinaryField, instead of an TextField?
  canIntrospectBinaryField = True

  # Can the backend introspect an BooleanField, instead of an IntegerField?
  canIntrospectBooleanField = True

  # Can the backend introspect an DecimalField, instead of an FloatField?
  canIntrospectDecimalField = True

  # Can the backend introspect an IPAddressField, instead of an CharField?
  canIntrospectIpAddressField = False

  # Can the backend introspect a PositiveIntegerField, instead of an IntegerField?
  canIntrospectPositiveIntegerField = False

  # Can the backend introspect a SmallIntegerField, instead of an IntegerField?
  canIntrospectSmallIntegerField = False

  # Can the backend introspect a TimeField, instead of a DateTimeField?
  canIntrospectTimeField = True

  # Support for the DISTINCT ON clause
  canDistinctOnFields = False

  # Does the backend decide to commit before SAVEPOINT statements
  # when autocommit is disabled? http://bugs.python.org/issue8145#msg109965
  autocommitsWhenAutocommitIsOff = False

  # Does the backend prevent running SQL queries in broken transactions?
  atomicTransactions = True

  # Can we roll back DDL in a transaction?
  canRollbackDdl = False

  # Can we issue more than one ALTER COLUMN clause in an ALTER TABLE?
  supportsCombinedAlters = False

  # Does it support foreign keys?
  supportsForeignKeys = True

  # Does it support CHECK constraints?
  supportsColumnCheckConstraints = True

  # Does the backend support 'pyformat' style ("... %(name)s ...", {'name': value})
  # parameter passing? Note this can be provided by the backend even if not
  # supported by the Python driver
  supportsParamstylePyformat = True

  # Does the backend require literal defaults, rather than parameterized ones?
  requiresLiteralDefaults = False

  # Does the backend require a connection reset after each material schema change?
  connectionPersistsOldColumns = False

  # What kind of error does the backend throw when accessing closed cursor?
  closedCursorErrorClass = ProgrammingError

  # Does 'a' LIKE 'A' match?
  hasCaseInsensitiveLike = True

  # Does the backend require the sqlparse library for splitting multi-line
  # statements before executing them?
  requiresSqlparseForSplitting = True

  # Suffix for backends that don't support "SELECT xxx;" queries.
  bareSelectSuffix = ''

  # If NULL is implied on columns without needing to be explicitly specified
  impliedColumnNull = False

  uppercasesColumnNames = False

  # Does the backend support "select for update" queries with limit (and offset)?
  supportsSelectForUpdateWithLimit = True

  def __init__(self, connection):
    self.connection = connection

  @cachedProperty
  def supportsTransactions(self):
    "Confirm support for transactions"
    try:
      # Make sure to run inside a managed transaction block,
      # otherwise autocommit will cause the confimation to
      # fail.
      self.connection.enterTransactionManagement()
      with self.connection.cursor() as cursor:
        cursor.execute('CREATE TABLE ROLLBACK_TEST (X INT)')
        self.connection.commit()
        cursor.execute('INSERT INTO ROLLBACK_TEST (X) VALUES (8)')
        self.connection.rollback()
        cursor.execute('SELECT COUNT(X) FROM ROLLBACK_TEST')
        count, = cursor.fetchone()
        cursor.execute('DROP TABLE ROLLBACK_TEST')
        self.connection.commit()
    finally:
      self.connection.leaveTransactionManagement()
    return count == 0

  @cachedProperty
  def supportsStddev(self):
    "Confirm support for STDDEV and related stats functions"
    class StdDevPop(object):
      sqlFunction = 'STDDEV_POP'

    try:
      self.connection.ops.checkAggregateSupport(StdDevPop())
      return True
    except NotImplementedError:
      return False


class BaseDatabaseOperations(object):
  """
  This class encapsulates all backend-specific differences, such as the way
  a backend performs ordering or calculates the ID of a recently-inserted
  row.
  """
  compilerModule = "theory.db.model.sql.compiler"

  # Integer field safe ranges by `internalType` as documented
  # in docs/ref/model/fields.txt.
  integerFieldRanges = {
    'SmallIntegerField': (-32768, 32767),
    'IntegerField': (-2147483648, 2147483647),
    'BigIntegerField': (-9223372036854775808, 9223372036854775807),
    'PositiveSmallIntegerField': (0, 32767),
    'PositiveIntegerField': (0, 2147483647),
  }

  def __init__(self, connection):
    self.connection = connection
    self._cache = None

  def autoincSql(self, table, column):
    """
    Returns any SQL needed to support auto-incrementing primary keys, or
    None if no SQL is necessary.

    This SQL is executed when a table is created.
    """
    return None

  def bulkBatchSize(self, fields, objs):
    """
    Returns the maximum allowed batch size for the backend. The fields
    are the fields going to be inserted in the batch, the objs contains
    all the objects to be inserted.
    """
    return len(objs)

  def cacheKeyCullingSql(self):
    """
    Returns an SQL query that retrieves the first cache key greater than the
    n smallest.

    This is used by the 'db' cache backend to determine where to start
    culling.
    """
    return "SELECT cacheKey FROM %s ORDER BY cacheKey LIMIT 1 OFFSET %%s"

  def dateExtractSql(self, lookupType, fieldName):
    """
    Given a lookupType of 'year', 'month' or 'day', returns the SQL that
    extracts a value from the given date field fieldName.
    """
    raise NotImplementedError('subclasses of BaseDatabaseOperations may require a dateExtractSql() method')

  def dateIntervalSql(self, sql, connector, timedelta):
    """
    Implements the date interval functionality for expressions
    """
    raise NotImplementedError('subclasses of BaseDatabaseOperations may require a dateIntervalSql() method')

  def dateTruncSql(self, lookupType, fieldName):
    """
    Given a lookupType of 'year', 'month' or 'day', returns the SQL that
    truncates the given date field fieldName to a date object with only
    the given specificity.
    """
    raise NotImplementedError('subclasses of BaseDatabaseOperations may require a datetruncSql() method')

  def datetimeCastSql(self):
    """
    Returns the SQL necessary to cast a datetime value so that it will be
    retrieved as a Python datetime object instead of a string.

    This SQL should include a '%s' in place of the field's name.
    """
    return "%s"

  def datetimeExtractSql(self, lookupType, fieldName, tzname):
    """
    Given a lookupType of 'year', 'month', 'day', 'hour', 'minute' or
    'second', returns the SQL that extracts a value from the given
    datetime field fieldName, and a tuple of parameters.
    """
    raise NotImplementedError('subclasses of BaseDatabaseOperations may require a datetimeExtractSql() method')

  def datetimeTruncSql(self, lookupType, fieldName, tzname):
    """
    Given a lookupType of 'year', 'month', 'day', 'hour', 'minute' or
    'second', returns the SQL that truncates the given datetime field
    fieldName to a datetime object with only the given specificity, and
    a tuple of parameters.
    """
    raise NotImplementedError('subclasses of BaseDatabaseOperations may require a datetimeTrunkSql() method')

  def deferrableSql(self):
    """
    Returns the SQL necessary to make a constraint "initially deferred"
    during a CREATE TABLE statement.
    """
    return ''

  def distinctSql(self, fields):
    """
    Returns an SQL DISTINCT clause which removes duplicate rows from the
    result set. If any fields are given, only the given fields are being
    checked for duplicates.
    """
    if fields:
      raise NotImplementedError('DISTINCT ON fields is not supported by this database backend')
    else:
      return 'DISTINCT'

  def dropForeignkeySql(self):
    """
    Returns the SQL command that drops a foreign key.
    """
    return "DROP CONSTRAINT"

  def dropSequenceSql(self, table):
    """
    Returns any SQL necessary to drop the sequence for the given table.
    Returns None if no SQL is necessary.
    """
    return None

  def fetchReturnedInsertId(self, cursor):
    """
    Given a cursor object that has just performed an INSERT...RETURNING
    statement into a table that has an auto-incrementing ID, returns the
    newly created ID.
    """
    return cursor.fetchone()[0]

  def fieldCastSql(self, dbType, internalType):
    """
    Given a column type (e.g. 'BLOB', 'VARCHAR'), and an internal type
    (e.g. 'GenericIPAddressField'), returns the SQL necessary to cast it
    before using it in a WHERE statement. Note that the resulting string
    should contain a '%s' placeholder for the column being searched against.
    """
    return '%s'

  def forceNoOrdering(self):
    """
    Returns a list used in the "ORDER BY" clause to force no ordering at
    all. Returning an empty list means that nothing will be included in the
    ordering.
    """
    return []

  def forUpdateSql(self, nowait=False):
    """
    Returns the FOR UPDATE SQL clause to lock rows for an update operation.
    """
    if nowait:
      return 'FOR UPDATE NOWAIT'
    else:
      return 'FOR UPDATE'

  def fulltextSearchSql(self, fieldName):
    """
    Returns the SQL WHERE clause to use in order to perform a full-text
    search of the given fieldName. Note that the resulting string should
    contain a '%s' placeholder for the value being searched against.
    """
    raise NotImplementedError('Full-text search is not implemented for this database backend')

  def lastExecutedQuery(self, cursor, sql, params):
    """
    Returns a string of the query last executed by the given cursor, with
    placeholders replaced with actual values.

    `sql` is the raw query containing placeholders, and `params` is the
    sequence of parameters. These are used by default, but this method
    exists for database backends to provide a better implementation
    according to their own quoting schemes.
    """
    from theory.utils.encoding import forceText

    # Convert params to contain Unicode values.
    toUnicode = lambda s: forceText(s, stringsOnly=True, errors='replace')
    if isinstance(params, (list, tuple)):
      uParams = tuple(toUnicode(val) for val in params)
    elif params is None:
      uParams = ()
    else:
      uParams = dict((toUnicode(k), toUnicode(v)) for k, v in params.items())

    return six.textType("QUERY = %r - PARAMS = %r") % (sql, uParams)

  def lastInsertId(self, cursor, tableName, pkName):
    """
    Given a cursor object that has just performed an INSERT statement into
    a table that has an auto-incrementing ID, returns the newly created ID.

    This method also receives the table name and the name of the primary-key
    column.
    """
    return cursor.lastrowid

  def lookupCast(self, lookupType):
    """
    Returns the string to use in a query when performing lookups
    ("contains", "like", etc). The resulting string should contain a '%s'
    placeholder for the column being searched against.
    """
    return "%s"

  def maxInListSize(self):
    """
    Returns the maximum number of items that can be passed in a single 'IN'
    list condition, or None if the backend does not impose a limit.
    """
    return None

  def maxNameLength(self):
    """
    Returns the maximum length of table and column names, or None if there
    is no limit.
    """
    return None

  def noLimitValue(self):
    """
    Returns the value to use for the LIMIT when we are wanting "LIMIT
    infinity". Returns None if the limit clause can be omitted in this case.
    """
    raise NotImplementedError('subclasses of BaseDatabaseOperations may require a noLimitValue() method')

  def pkDefaultValue(self):
    """
    Returns the value to use during an INSERT statement to specify that
    the field should use its default value.
    """
    return 'DEFAULT'

  def prepareSqlScript(self, sql, _allowFallback=False):
    """
    Takes a SQL script that may contain multiple lines and returns a list
    of statements to feed to successive cursor.execute() calls.

    Since few databases are able to process raw SQL scripts in a single
    cursor.execute() call and PEP 249 doesn't talk about this use case,
    the default implementation is conservative.
    """
    # Remove _allowFallback and keep only 'return ...' in Theory 1.9.
    try:
      # This import must stay inside the method because it's optional.
      import sqlparse
    except ImportError:
      if _allowFallback:
        # Without sqlparse, fall back to the legacy (and buggy) logic.
        warnings.warn(
          "Providing initial SQL data on a %s database will require "
          "sqlparse in Theory 1.9." % self.connection.vendor,
          RemovedInTheory19Warning)
        from theory.core.management.sql import _splitStatements
        return _splitStatements(sql)
      else:
        raise
    else:
      return [sqlparse.format(statement, stripComments=True)
          for statement in sqlparse.split(sql) if statement]

  def processClob(self, value):
    """
    Returns the value of a CLOB column, for backends that return a locator
    object that requires additional processing.
    """
    return value

  def returnInsertId(self):
    """
    For backends that support returning the last insert ID as part
    of an insert query, this method returns the SQL and params to
    append to the INSERT query. The returned fragment should
    contain a format string to hold the appropriate column.
    """
    pass

  def compiler(self, compilerName):
    """
    Returns the SQLCompiler class corresponding to the given name,
    in the namespace corresponding to the `compilerModule` attribute
    on this backend.
    """
    if self._cache is None:
      self._cache = import_module(self.compilerModule)
    return getattr(self._cache, compilerName)

  def quoteName(self, name):
    """
    Returns a quoted version of the given table, index or column name. Does
    not quote the given name if it's already been quoted.
    """
    raise NotImplementedError('subclasses of BaseDatabaseOperations may require a quoteName() method')

  def randomFunctionSql(self):
    """
    Returns an SQL expression that returns a random value.
    """
    return 'RANDOM()'

  def regexLookup(self, lookupType):
    """
    Returns the string to use in a query when performing regular expression
    lookups (using "regex" or "iregex"). The resulting string should
    contain a '%s' placeholder for the column being searched against.

    If the feature is not supported (or part of it is not supported), a
    NotImplementedError exception can be raised.
    """
    raise NotImplementedError('subclasses of BaseDatabaseOperations may require a regexLookup() method')

  def savepointCreateSql(self, sid):
    """
    Returns the SQL for starting a new savepoint. Only required if the
    "usesSavepoints" feature is True. The "sid" parameter is a string
    for the savepoint id.
    """
    return "SAVEPOINT %s" % self.quoteName(sid)

  def savepointCommitSql(self, sid):
    """
    Returns the SQL for committing the given savepoint.
    """
    return "RELEASE SAVEPOINT %s" % self.quoteName(sid)

  def savepointRollbackSql(self, sid):
    """
    Returns the SQL for rolling back the given savepoint.
    """
    return "ROLLBACK TO SAVEPOINT %s" % self.quoteName(sid)

  def setTimeZoneSql(self):
    """
    Returns the SQL that will set the connection's time zone.

    Returns '' if the backend doesn't support time zones.
    """
    return ''

  def sqlFlush(self, style, tables, sequences, allowCascade=False):
    """
    Returns a list of SQL statements required to remove all data from
    the given database tables (without actually removing the tables
    themselves).

    The returned value also includes SQL statements required to reset DB
    sequences passed in :param sequences:.

    The `style` argument is a Style object as returned by either
    colorStyle() or noStyle() in theory.core.management.color.

    The `allowCascade` argument determines whether truncation may cascade
    to tables with foreign keys pointing the tables being truncated.
    PostgreSQL requires a cascade even if these tables are empty.
    """
    raise NotImplementedError('subclasses of BaseDatabaseOperations must provide a sqlFlush() method')

  def sequenceResetByNameSql(self, style, sequences):
    """
    Returns a list of the SQL statements required to reset sequences
    passed in :param sequences:.

    The `style` argument is a Style object as returned by either
    colorStyle() or noStyle() in theory.core.management.color.
    """
    return []

  def sequenceResetSql(self, style, modalList):
    """
    Returns a list of the SQL statements required to reset sequences for
    the given model.

    The `style` argument is a Style object as returned by either
    colorStyle() or noStyle() in theory.core.management.color.
    """
    return []  # No sequence reset required by default.

  def startTransactionSql(self):
    """
    Returns the SQL statement required to start a transaction.
    """
    return "BEGIN;"

  def endTransactionSql(self, success=True):
    """
    Returns the SQL statement required to end a transaction.
    """
    if not success:
      return "ROLLBACK;"
    return "COMMIT;"

  def tablespaceSql(self, tablespace, inline=False):
    """
    Returns the SQL that will be used in a query to define the tablespace.

    Returns '' if the backend doesn't support tablespaces.

    If inline is True, the SQL is appended to a row; otherwise it's appended
    to the entire CREATE TABLE or CREATE INDEX statement.
    """
    return ''

  def prepForLikeQuery(self, x):
    """Prepares a value for use in a LIKE query."""
    from theory.utils.encoding import forceText
    return forceText(x).replace("\\", "\\\\").replace("%", "\%").replace("_", "\_")

  # Same as prepForLikeQuery(), but called for "iexact" matches, which
  # need not necessarily be implemented using "LIKE" in the backend.
  prepForIexactQuery = prepForLikeQuery

  def validateAutopkValue(self, value):
    """
    Certain backends do not accept some values for "serial" fields
    (for example zero in MySQL). This method will raise a ValueError
    if the value is invalid, otherwise returns validated value.
    """
    return value

  def valueToDbDate(self, value):
    """
    Transform a date value to an object compatible with what is expected
    by the backend driver for date columns.
    """
    if value is None:
      return None
    return six.textType(value)

  def valueToDbDatetime(self, value):
    """
    Transform a datetime value to an object compatible with what is expected
    by the backend driver for datetime columns.
    """
    if value is None:
      return None
    return six.textType(value)

  def valueToDbTime(self, value):
    """
    Transform a time value to an object compatible with what is expected
    by the backend driver for time columns.
    """
    if value is None:
      return None
    if timezone.isAware(value):
      raise ValueError("Theory does not support timezone-aware times.")
    return six.textType(value)

  def valueToDbDecimal(self, value, maxDigits, decimalPlaces):
    """
    Transform a decimal.Decimal value to an object compatible with what is
    expected by the backend driver for decimal (numeric) columns.
    """
    if value is None:
      return None
    return utils.formatNumber(value, maxDigits, decimalPlaces)

  def yearLookupBoundsForDateField(self, value):
    """
    Returns a two-elements list with the lower and upper bound to be used
    with a BETWEEN operator to query a DateField value using a year
    lookup.

    `value` is an int, containing the looked-up year.
    """
    first = datetime.date(value, 1, 1)
    second = datetime.date(value, 12, 31)
    return [first, second]

  def yearLookupBoundsForDatetimeField(self, value):
    """
    Returns a two-elements list with the lower and upper bound to be used
    with a BETWEEN operator to query a DateTimeField value using a year
    lookup.

    `value` is an int, containing the looked-up year.
    """
    first = datetime.datetime(value, 1, 1)
    second = datetime.datetime(value, 12, 31, 23, 59, 59, 999999)
    if settings.USE_TZ:
      tz = timezone.getCurrentTimezone()
      first = timezone.makeAware(first, tz)
      second = timezone.makeAware(second, tz)
    return [first, second]

  def convertValues(self, value, field):
    """
    Coerce the value returned by the database backend into a consistent type
    that is compatible with the field type.
    """
    if value is None or field is None:
      return value
    internalType = field.getInternalType()
    if internalType == 'FloatField':
      return float(value)
    elif (internalType and (internalType.endswith('IntegerField')
                 or internalType == 'AutoField')):
      return int(value)
    return value

  def checkAggregateSupport(self, aggregateFunc):
    """Check that the backend supports the provided aggregate

    This is used on specific backends to rule out known aggregates
    that are known to have faulty implementations. If the named
    aggregate function has a known problem, the backend should
    raise NotImplementedError.
    """
    pass

  def combineExpression(self, connector, subExpressions):
    """Combine a list of subexpressions into a single expression, using
    the provided connecting operator. This is required because operators
    can vary between backends (e.g., Oracle with %% and &) and between
    subexpression types (e.g., date expressions)
    """
    conn = ' %s ' % connector
    return conn.join(subExpressions)

  def modifyInsertParams(self, placeholders, params):
    """Allow modification of insert parameters. Needed for Oracle Spatial
    backend due to #10888.
    """
    return params

  def integerFieldRange(self, internalType):
    """
    Given an integer field internal type (e.g. 'PositiveIntegerField'),
    returns a tuple of the (minValue, maxValue) form representing the
    range of the column type bound to the field.
    """
    return self.integerFieldRanges[internalType]


# Structure returned by the DB-API cursor.description interface (PEP 249)
FieldInfo = namedtuple('FieldInfo',
  'name typeCode displaySize internalSize precision scale nullOk')


class BaseDatabaseIntrospection(object):
  """
  This class encapsulates all backend-specific introspection utilities
  """
  dataTypesReverse = {}

  def __init__(self, connection):
    self.connection = connection

  def getFieldType(self, dataType, description):
    """Hook for a database backend to use the cursor description to
    match a Theory field type to a database column.

    For Oracle, the column dataType on its own is insufficient to
    distinguish between a FloatField and IntegerField, for example."""
    return self.dataTypesReverse[dataType]

  def tableNameConverter(self, name):
    """Apply a conversion to the name for the purposes of comparison.

    The default table name converter is for case sensitive comparison.
    """
    return name

  def tableNames(self, cursor=None):
    """
    Returns a list of names of all tables that exist in the database.
    The returned table list is sorted by Python's default sorting. We
    do NOT use database's ORDER BY here to avoid subtle differences
    in sorting order between databases.
    """
    if cursor is None:
      with self.connection.cursor() as cursor:
        return sorted(self.getTableList(cursor))
    return sorted(self.getTableList(cursor))

  def getTableList(self, cursor):
    """
    Returns an unsorted list of names of all tables that exist in the
    database.
    """
    raise NotImplementedError('subclasses of BaseDatabaseIntrospection may require a getTableList() method')

  def theoryTableNames(self, onlyExisting=False):
    """
    Returns a list of all table names that have associated Theory model and
    are in INSTALLED_APPS.

    If onlyExisting is True, the resulting list will only include the tables
    that actually exist in the database.
    """
    from theory.apps import apps
    from theory.db import router
    tables = set()
    for appConfig in apps.getAppConfigs():
      for modal in router.getMigratableModels(appConfig, self.connection.alias):
        if not modal._meta.managed:
          continue
        tables.add(modal._meta.dbTable)
        tables.update(f.m2mDbTable() for f in modal._meta.localManyToMany)
    tables = list(tables)
    if onlyExisting:
      existingTables = self.tableNames()
      tables = [
        t
        for t in tables
        if self.tableNameConverter(t) in existingTables
      ]
    return tables

  def installedModels(self, tables):
    "Returns a set of all model represented by the provided list of table names."
    from theory.apps import apps
    from theory.db import router
    allModels = []
    for appConfig in apps.getAppConfigs():
      allModels.extend(router.getMigratableModels(appConfig, self.connection.alias))
    tables = list(map(self.tableNameConverter, tables))
    return set([
      m for m in allModels
      if self.tableNameConverter(m._meta.dbTable) in tables
    ])

  def sequenceList(self):
    "Returns a list of information about all DB sequences for all model in all apps."
    from theory.apps import apps
    from theory.db import model, router

    sequenceList = []

    for appConfig in apps.getAppConfigs():
      for modal in router.getMigratableModels(appConfig, self.connection.alias):
        if not modal._meta.managed:
          continue
        if modal._meta.swapped:
          continue
        for f in modal._meta.localFields:
          if isinstance(f, model.AutoField):
            sequenceList.append({'table': modal._meta.dbTable, 'column': f.column})
            break  # Only one AutoField is allowed per modal, so don't bother continuing.

        for f in modal._meta.localManyToMany:
          # If this is an m2m using an intermediate table,
          # we don't need to reset the sequence.
          if f.rel.through is None:
            sequenceList.append({'table': f.m2mDbTable(), 'column': None})

    return sequenceList

  def getKeyColumns(self, cursor, tableName):
    """
    Backends can override this to return a list of (columnName, referencedTableName,
    referencedColumnName) for all key columns in given table.
    """
    raise NotImplementedError('subclasses of BaseDatabaseIntrospection may require a getKeyColumns() method')

  def getPrimaryKeyColumn(self, cursor, tableName):
    """
    Returns the name of the primary key column for the given table.
    """
    for column in six.iteritems(self.getIndexes(cursor, tableName)):
      if column[1]['primaryKey']:
        return column[0]
    return None

  def getIndexes(self, cursor, tableName):
    """
    Returns a dictionary of indexed fieldname -> infodict for the given
    table, where each infodict is in the format:
      {'primaryKey': boolean representing whether it's the primary key,
       'unique': boolean representing whether it's a unique index}

    Only single-column indexes are introspected.
    """
    raise NotImplementedError('subclasses of BaseDatabaseIntrospection may require a getIndexes() method')

  def getConstraints(self, cursor, tableName):
    """
    Retrieves any constraints or keys (unique, pk, fk, check, index)
    across one or more columns.

    Returns a dict mapping constraint names to their attributes,
    where attributes is a dict with keys:
     * columns: List of columns this covers
     * primaryKey: True if primary key, False otherwise
     * unique: True if this is a unique constraint, False otherwise
     * foreignKey: (table, column) of target, or None
     * check: True if check constraint, False otherwise
     * index: True if index, False otherwise.

    Some backends may return special constraint names that don't exist
    if they don't name constraints of a certain type (e.g. SQLite)
    """
    raise NotImplementedError('subclasses of BaseDatabaseIntrospection may require a getConstraints() method')


class BaseDatabaseClient(object):
  """
  This class encapsulates all backend-specific methods for opening a
  client shell.
  """
  # This should be a string representing the name of the executable
  # (e.g., "psql"). Subclasses must override this.
  executableName = None

  def __init__(self, connection):
    # connection is an instance of BaseDatabaseWrapper.
    self.connection = connection

  def runshell(self):
    raise NotImplementedError('subclasses of BaseDatabaseClient must provide a runshell() method')


class BaseDatabaseValidation(object):
  """
  This class encapsulates all backend-specific modal validation.
  """
  def __init__(self, connection):
    self.connection = connection

  def validateField(self, errors, opts, f):
    """
    By default, there is no backend-specific validation.

    This method has been deprecated by the new checks framework. New
    backends should implement checkField instead.
    """
    # This is deliberately commented out. It exists as a marker to
    # remind us to remove this method, and the checkField() shim,
    # when the time comes.
    # warnings.warn('"validateField" has been deprecated", RemovedInTheory19Warning)
    pass

  def checkField(self, field, **kwargs):
    class ErrorList(list):
      """A dummy list class that emulates API used by the older
      validateField() method. When validateField() is fully
      deprecated, this dummy can be removed too.
      """
      def add(self, opts, errorMessage):
        self.append(checks.Error(errorMessage, hint=None, obj=field))

    errors = ErrorList()
    # Some tests create fields in isolation -- the fields are not attached
    # to any modal, so they have no `modal` attribute.
    opts = field.modal._meta if hasattr(field, 'modal') else None
    self.validateField(errors, field, opts)
    return list(errors)
