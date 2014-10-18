import warnings

from theory.core import signals
from theory.db.utils import (DEFAULT_DB_ALIAS, DataError, OperationalError,
  IntegrityError, InternalError, ProgrammingError, NotSupportedError,
  DatabaseError, InterfaceError, Error, loadBackend,
  ConnectionHandler, ConnectionRouter)
from theory.utils.deprecation import RemovedInTheory20Warning
from theory.utils.functional import cachedProperty


__all__ = [
  'backend', 'connection', 'connections', 'router', 'DatabaseError',
  'IntegrityError', 'InternalError', 'ProgrammingError', 'DataError',
  'NotSupportedError', 'Error', 'InterfaceError', 'OperationalError',
  'DEFAULT_DB_ALIAS'
]

connections = ConnectionHandler()

router = ConnectionRouter()


# `connection`, `DatabaseError` and `IntegrityError` are convenient aliases
# for backend bits.

# DatabaseWrapper.__init__() takes a dictionary, not a settings module, so
# we manually create the dictionary from the settings, passing only the
# settings that the database backends care about. Note that TIME_ZONE is used
# by the PostgreSQL backends.
# We load all these up for backwards compatibility, you should use
# connections['default'] instead.
class DefaultConnectionProxy(object):
  """
  Proxy for accessing the default DatabaseWrapper object's attributes. If you
  need to access the DatabaseWrapper object itself, use
  connections[DEFAULT_DB_ALIAS] instead.
  """
  def __getattr__(self, item):
    return getattr(connections[DEFAULT_DB_ALIAS], item)

  def __setattr__(self, name, value):
    return setattr(connections[DEFAULT_DB_ALIAS], name, value)

  def __delattr__(self, name):
    return delattr(connections[DEFAULT_DB_ALIAS], name)

  def __eq__(self, other):
    return connections[DEFAULT_DB_ALIAS] == other

  def __ne__(self, other):
    return connections[DEFAULT_DB_ALIAS] != other

connection = DefaultConnectionProxy()


class DefaultBackendProxy(object):
  """
  Temporary proxy class used during deprecation period of the `backend` module
  variable.
  """
  @cachedProperty
  def _backend(self):
    warnings.warn("Accessing theory.db.backend is deprecated.",
      RemovedInTheory20Warning, stacklevel=2)
    return loadBackend(connections[DEFAULT_DB_ALIAS].settingsDict['ENGINE'])

  def __getattr__(self, item):
    return getattr(self._backend, item)

  def __setattr__(self, name, value):
    return setattr(self._backend, name, value)

  def __delattr__(self, name):
    return delattr(self._backend, name)

backend = DefaultBackendProxy()


def closeConnection(**kwargs):
  warnings.warn(
    "closeConnection is superseded by closeOldConnections.",
    RemovedInTheory20Warning, stacklevel=2)
  # Avoid circular imports
  from theory.db import transaction
  for conn in connections:
    # If an error happens here the connection will be left in broken
    # state. Once a good db connection is again available, the
    # connection state will be cleaned up.
    transaction.abort(conn)
    connections[conn].close()


# Register an event to reset saved queries when a Theory request is started.
def resetQueries(**kwargs):
  for conn in connections.all():
    conn.queries = []
signals.requestStarted.connect(resetQueries)


# Register an event to reset transaction state and close connections past
# their lifetime. NB: abort() doesn't do anything outside of a transaction.
def closeOldConnections(**kwargs):
  for conn in connections.all():
    # Remove this when the legacy transaction management goes away.
    try:
      conn.abort()
    except DatabaseError:
      pass
    conn.closeIfUnusableOrObsolete()
signals.requestStarted.connect(closeOldConnections)
signals.requestFinished.connect(closeOldConnections)
