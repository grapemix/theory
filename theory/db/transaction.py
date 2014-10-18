"""
This module implements a transaction manager that can be used to define
transaction handling in a request or view function. It is used by transaction
control middleware and decorators.

The transaction manager can be in managed or in auto state. Auto state means the
system is using a commit-on-save strategy (actually it's more like
commit-on-change). As soon as the .save() or .delete() (or related) methods are
called, a commit is made.

Managed transactions don't do those commits, but will need some kind of manual
or implicit commits or rollbacks.
"""

import warnings

from functools import wraps

from theory.db import (
  connections, DEFAULT_DB_ALIAS,
  DatabaseError, Error, ProgrammingError)
from theory.utils.decorators import availableAttrs
from theory.utils.deprecation import RemovedInTheory20Warning


class TransactionManagementError(ProgrammingError):
  """
  This exception is thrown when transaction management is used improperly.
  """
  pass


################
# Private APIs #
################

def getConnection(using=None):
  """
  Get a database connection by name, or the default database connection
  if no name is provided.
  """
  if using is None:
    using = DEFAULT_DB_ALIAS
  return connections[using]


###########################
# Deprecated private APIs #
###########################

def abort(using=None):
  """
  Roll back any ongoing transactions and clean the transaction management
  state of the connection.

  This method is to be used only in cases where using balanced
  leaveTransactionManagement() calls isn't possible. For example after a
  request has finished, the transaction state isn't known, yet the connection
  must be cleaned up for the next request.
  """
  getConnection(using).abort()


def enterTransactionManagement(managed=True, using=None, forced=False):
  """
  Enters transaction management for a running thread. It must be balanced with
  the appropriate leaveTransactionManagement call, since the actual state is
  managed as a stack.

  The state and dirty flag are carried over from the surrounding block or
  from the settings, if there is no surrounding block (dirty is always false
  when no current block is running).
  """
  getConnection(using).enterTransactionManagement(managed, forced)


def leaveTransactionManagement(using=None):
  """
  Leaves transaction management for a running thread. A dirty flag is carried
  over to the surrounding block, as a commit will commit all changes, even
  those from outside. (Commits are on connection level.)
  """
  getConnection(using).leaveTransactionManagement()


def isDirty(using=None):
  """
  Returns True if the current transaction requires a commit for changes to
  happen.
  """
  return getConnection(using).isDirty()


def setDirty(using=None):
  """
  Sets a dirty flag for the current thread and code streak. This can be used
  to decide in a managed block of code to decide whether there are open
  changes waiting for commit.
  """
  getConnection(using).setDirty()


def setClean(using=None):
  """
  Resets a dirty flag for the current thread and code streak. This can be used
  to decide in a managed block of code to decide whether a commit or rollback
  should happen.
  """
  getConnection(using).setClean()


def isManaged(using=None):
  warnings.warn("'isManaged' is deprecated.",
    RemovedInTheory20Warning, stacklevel=2)


def managed(flag=True, using=None):
  warnings.warn("'managed' no longer serves a purpose.",
    RemovedInTheory20Warning, stacklevel=2)


def commitUnlessManaged(using=None):
  warnings.warn("'commitUnlessManaged' is now a no-op.",
    RemovedInTheory20Warning, stacklevel=2)


def rollbackUnlessManaged(using=None):
  warnings.warn("'rollbackUnlessManaged' is now a no-op.",
    RemovedInTheory20Warning, stacklevel=2)


###############
# Public APIs #
###############

def getAutocommit(using=None):
  """
  Get the autocommit status of the connection.
  """
  return getConnection(using).getAutocommit()


def setAutocommit(autocommit, using=None):
  """
  Set the autocommit status of the connection.
  """
  return getConnection(using).setAutocommit(autocommit)


def commit(using=None):
  """
  Commits a transaction and resets the dirty flag.
  """
  getConnection(using).commit()


def rollback(using=None):
  """
  Rolls back a transaction and resets the dirty flag.
  """
  getConnection(using).rollback()


def savepoint(using=None):
  """
  Creates a savepoint (if supported and required by the backend) inside the
  current transaction. Returns an identifier for the savepoint that will be
  used for the subsequent rollback or commit.
  """
  return getConnection(using).savepoint()


def savepointRollback(sid, using=None):
  """
  Rolls back the most recent savepoint (if one exists). Does nothing if
  savepoints are not supported.
  """
  getConnection(using).savepointRollback(sid)


def savepointCommit(sid, using=None):
  """
  Commits the most recent savepoint (if one exists). Does nothing if
  savepoints are not supported.
  """
  getConnection(using).savepointCommit(sid)


def cleanSavepoints(using=None):
  """
  Resets the counter used to generate unique savepoint ids in this thread.
  """
  getConnection(using).cleanSavepoints()


def getRollback(using=None):
  """
  Gets the "needs rollback" flag -- for *advanced use* only.
  """
  return getConnection(using).getRollback()


def setRollback(rollback, using=None):
  """
  Sets or unsets the "needs rollback" flag -- for *advanced use* only.

  When `rollback` is `True`, it triggers a rollback when exiting the
  innermost enclosing atomic block that has `savepoint=True` (that's the
  default). Use this to force a rollback without raising an exception.

  When `rollback` is `False`, it prevents such a rollback. Use this only
  after rolling back to a known-good state! Otherwise, you break the atomic
  block and data corruption may occur.
  """
  return getConnection(using).setRollback(rollback)


#################################
# Decorators / context managers #
#################################

class Atomic(object):
  """
  This class guarantees the atomic execution of a given block.

  An instance can be used either as a decorator or as a context manager.

  When it's used as a decorator, __call__ wraps the execution of the
  decorated function in the instance itself, used as a context manager.

  When it's used as a context manager, __enter__ creates a transaction or a
  savepoint, depending on whether a transaction is already in progress, and
  __exit__ commits the transaction or releases the savepoint on normal exit,
  and rolls back the transaction or to the savepoint on exceptions.

  It's possible to disable the creation of savepoints if the goal is to
  ensure that some code runs within a transaction without creating overhead.

  A stack of savepoints identifiers is maintained as an attribute of the
  connection. None denotes the absence of a savepoint.

  This allows reentrancy even if the same AtomicWrapper is reused. For
  example, it's possible to define `oa = @atomic('other')` and use `@oa` or
  `with oa:` multiple times.

  Since database connections are thread-local, this is thread-safe.
  """

  def __init__(self, using, savepoint):
    self.using = using
    self.savepoint = savepoint

  def __enter__(self):
    connection = getConnection(self.using)

    if not connection.inAtomicBlock:
      # Reset state when entering an outermost atomic block.
      connection.commitOnExit = True
      connection.needsRollback = False
      if not connection.getAutocommit():
        # Some database adapters (namely sqlite3) don't handle
        # transactions and savepoints properly when autocommit is off.
        # Turning autocommit back on isn't an option; it would trigger
        # a premature commit. Give up if that happens.
        if connection.features.autocommitsWhenAutocommitIsOff:
          raise TransactionManagementError(
            "Your database backend doesn't behave properly when "
            "autocommit is off. Turn it on before using 'atomic'.")
        # When entering an atomic block with autocommit turned off,
        # Theory should only use savepoints and shouldn't commit.
        # This requires at least a savepoint for the outermost block.
        if not self.savepoint:
          raise TransactionManagementError(
            "The outermost 'atomic' block cannot use "
            "savepoint = False when autocommit is off.")
        # Pretend we're already in an atomic block to bypass the code
        # that disables autocommit to enter a transaction, and make a
        # note to deal with this case in __exit__.
        connection.inAtomicBlock = True
        connection.commitOnExit = False

    if connection.inAtomicBlock:
      # We're already in a transaction; create a savepoint, unless we
      # were told not to or we're already waiting for a rollback. The
      # second condition avoids creating useless savepoints and prevents
      # overwriting needsRollback until the rollback is performed.
      if self.savepoint and not connection.needsRollback:
        sid = connection.savepoint()
        connection.savepointIds.append(sid)
      else:
        connection.savepointIds.append(None)
    else:
      # We aren't in a transaction yet; create one.
      # The usual way to start a transaction is to turn autocommit off.
      # However, some database adapters (namely sqlite3) don't handle
      # transactions and savepoints properly when autocommit is off.
      # In such cases, start an explicit transaction instead, which has
      # the side-effect of disabling autocommit.
      if connection.features.autocommitsWhenAutocommitIsOff:
        connection._startTransactionUnderAutocommit()
        connection.autocommit = False
      else:
        connection.setAutocommit(False)
      connection.inAtomicBlock = True

  def __exit__(self, excType, excValue, traceback):
    connection = getConnection(self.using)

    if connection.savepointIds:
      sid = connection.savepointIds.pop()
    else:
      # Prematurely unset this flag to allow using commit or rollback.
      connection.inAtomicBlock = False

    try:
      if connection.closedInTransaction:
        # The database will perform a rollback by itself.
        # Wait until we exit the outermost block.
        pass

      elif excType is None and not connection.needsRollback:
        if connection.inAtomicBlock:
          # Release savepoint if there is one
          if sid is not None:
            try:
              connection.savepointCommit(sid)
            except DatabaseError:
              try:
                connection.savepointRollback(sid)
              except Error:
                # If rolling back to a savepoint fails, mark for
                # rollback at a higher level and avoid shadowing
                # the original exception.
                connection.needsRollback = True
              raise
        else:
          # Commit transaction
          try:
            connection.commit()
          except DatabaseError:
            try:
              connection.rollback()
            except Error:
              # An error during rollback means that something
              # went wrong with the connection. Drop it.
              connection.close()
            raise
      else:
        # This flag will be set to True again if there isn't a savepoint
        # allowing to perform the rollback at this level.
        connection.needsRollback = False
        if connection.inAtomicBlock:
          # Roll back to savepoint if there is one, mark for rollback
          # otherwise.
          if sid is None:
            connection.needsRollback = True
          else:
            try:
              connection.savepointRollback(sid)
            except Error:
              # If rolling back to a savepoint fails, mark for
              # rollback at a higher level and avoid shadowing
              # the original exception.
              connection.needsRollback = True
        else:
          # Roll back transaction
          try:
            connection.rollback()
          except Error:
            # An error during rollback means that something
            # went wrong with the connection. Drop it.
            connection.close()

    finally:
      # Outermost block exit when autocommit was enabled.
      if not connection.inAtomicBlock:
        if connection.closedInTransaction:
          connection.connection = None
        elif connection.features.autocommitsWhenAutocommitIsOff:
          connection.autocommit = True
        else:
          connection.setAutocommit(True)
      # Outermost block exit when autocommit was disabled.
      elif not connection.savepointIds and not connection.commitOnExit:
        if connection.closedInTransaction:
          connection.connection = None
        else:
          connection.inAtomicBlock = False

  def __call__(self, func):
    @wraps(func, assigned=availableAttrs(func))
    def inner(*args, **kwargs):
      with self:
        return func(*args, **kwargs)
    return inner


def atomic(using=None, savepoint=True):
  # Bare decorator: @atomic -- although the first argument is called
  # `using`, it's actually the function being decorated.
  if callable(using):
    return Atomic(DEFAULT_DB_ALIAS, savepoint)(using)
  # Decorator: @atomic(...) or context manager: with atomic(...): ...
  else:
    return Atomic(using, savepoint)


def _nonAtomicRequests(view, using):
  try:
    view._nonAtomicRequests.add(using)
  except AttributeError:
    view._nonAtomicRequests = set([using])
  return view


def nonAtomicRequests(using=None):
  if callable(using):
    return _nonAtomicRequests(using, DEFAULT_DB_ALIAS)
  else:
    if using is None:
      using = DEFAULT_DB_ALIAS
    return lambda view: _nonAtomicRequests(view, using)


############################################
# Deprecated decorators / context managers #
############################################

class Transaction(object):
  """
  Acts as either a decorator, or a context manager.  If it's a decorator it
  takes a function and returns a wrapped function.  If it's a contextmanager
  it's used with the ``with`` statement.  In either event entering/exiting
  are called before and after, respectively, the function/block is executed.

  autocommit, commitOnSuccess, and commitManually contain the
  implementations of entering and exiting.
  """
  def __init__(self, entering, exiting, using):
    self.entering = entering
    self.exiting = exiting
    self.using = using

  def __enter__(self):
    self.entering(self.using)

  def __exit__(self, excType, excValue, traceback):
    self.exiting(excType, self.using)

  def __call__(self, func):
    @wraps(func)
    def inner(*args, **kwargs):
      with self:
        return func(*args, **kwargs)
    return inner


def _transactionFunc(entering, exiting, using):
  """
  Takes 3 things, an entering function (what to do to start this block of
  transaction management), an exiting function (what to do to end it, on both
  success and failure, and using which can be: None, indicating using is
  DEFAULT_DB_ALIAS, a callable, indicating that using is DEFAULT_DB_ALIAS and
  to return the function already wrapped.

  Returns either a Transaction objects, which is both a decorator and a
  context manager, or a wrapped function, if using is a callable.
  """
  # Note that although the first argument is *called* `using`, it
  # may actually be a function; @autocommit and @autocommit('foo')
  # are both allowed forms.
  if using is None:
    using = DEFAULT_DB_ALIAS
  if callable(using):
    return Transaction(entering, exiting, DEFAULT_DB_ALIAS)(using)
  return Transaction(entering, exiting, using)


def autocommit(using=None):
  """
  Decorator that activates commit on save. This is Theory's default behavior;
  this decorator is useful if you globally activated transaction management in
  your settings file and want the default behavior in some view functions.
  """
  warnings.warn("autocommit is deprecated in favor of setAutocommit.",
    RemovedInTheory20Warning, stacklevel=2)

  def entering(using):
    enterTransactionManagement(managed=False, using=using)

  def exiting(excType, using):
    leaveTransactionManagement(using=using)

  return _transactionFunc(entering, exiting, using)


def commitOnSuccess(using=None):
  """
  This decorator activates commit on response. This way, if the view function
  runs successfully, a commit is made; if the viewfunc produces an exception,
  a rollback is made. This is one of the most common ways to do transaction
  control in Web apps.
  """
  warnings.warn("commitOnSuccess is deprecated in favor of atomic.",
    RemovedInTheory20Warning, stacklevel=2)

  def entering(using):
    enterTransactionManagement(using=using)

  def exiting(excType, using):
    try:
      if excType is not None:
        if isDirty(using=using):
          rollback(using=using)
      else:
        if isDirty(using=using):
          try:
            commit(using=using)
          except:
            rollback(using=using)
            raise
    finally:
      leaveTransactionManagement(using=using)

  return _transactionFunc(entering, exiting, using)


def commitManually(using=None):
  """
  Decorator that activates manual transaction control. It just disables
  automatic transaction control and doesn't do any commit/rollback of its
  own -- it's up to the user to call the commit and rollback functions
  themselves.
  """
  warnings.warn("commitManually is deprecated in favor of setAutocommit.",
    RemovedInTheory20Warning, stacklevel=2)

  def entering(using):
    enterTransactionManagement(using=using)

  def exiting(excType, using):
    leaveTransactionManagement(using=using)

  return _transactionFunc(entering, exiting, using)


def commitOnSuccessUnlessManaged(using=None, savepoint=False):
  """
  Transitory API to preserve backwards-compatibility while refactoring.

  Once the legacy transaction management is fully deprecated, this should
  simply be replaced by atomic. Until then, it's necessary to guarantee that
  a commit occurs on exit, which atomic doesn't do when it's nested.

  Unlike atomic, savepoint defaults to False because that's closer to the
  legacy behavior.
  """
  connection = getConnection(using)
  if connection.getAutocommit() or connection.inAtomicBlock:
    return atomic(using, savepoint)
  else:
    def entering(using):
      pass

    def exiting(excType, using):
      setDirty(using=using)

    return _transactionFunc(entering, exiting, using)
