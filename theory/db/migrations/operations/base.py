from __future__ import unicode_literals
from theory.db import router


class Operation(object):
  """
  Base class for migration operations.

  It's responsible for both mutating the in-memory modal state
  (see db/migrations/state.py) to represent what it performs, as well
  as actually performing it against a live database.

  Note that some operations won't modify memory state at all (e.g. data
  copying operations), and some will need their modifications to be
  optionally specified by the user (e.g. custom Python code snippets)

  Due to the way this class deals with deconstruction, it should be
  considered immutable.
  """

  # If this migration can be run in reverse.
  # Some operations are impossible to reverse, like deleting data.
  reversible = True

  # Can this migration be represented as SQL? (things like RunPython cannot)
  reducesToSql = True

  # Should this operation be forced as atomic even on backends with no
  # DDL transaction support (i.e., does it have no DDL, like RunPython)
  atomic = False

  serializationExpandArgs = []

  def __new__(cls, *args, **kwargs):
    # We capture the arguments to make returning them trivial
    self = object.__new__(cls)
    self._constructorArgs = (args, kwargs)
    return self

  def deconstruct(self):
    """
    Returns a 3-tuple of class import path (or just name if it lives
    under theory.db.migrations), positional arguments, and keyword
    arguments.
    """
    return (
      self.__class__.__name__,
      self._constructorArgs[0],
      self._constructorArgs[1],
    )

  def stateForwards(self, appLabel, state):
    """
    Takes the state from the previous migration, and mutates it
    so that it matches what this migration would perform.
    """
    raise NotImplementedError('subclasses of Operation must provide a stateForwards() method')

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    """
    Performs the mutation on the database schema in the normal
    (forwards) direction.
    """
    raise NotImplementedError('subclasses of Operation must provide a databaseForwards() method')

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    """
    Performs the mutation on the database schema in the reverse
    direction - e.g. if this were CreateModel, it would in fact
    drop the modal's table.
    """
    raise NotImplementedError('subclasses of Operation must provide a databaseBackwards() method')

  def describe(self):
    """
    Outputs a brief summary of what the action does.
    """
    return "%s: %s" % (self.__class__.__name__, self._constructorArgs)

  def referencesModel(self, name, appLabel=None):
    """
    Returns True if there is a chance this operation references the given
    modal name (as a string), with an optional app label for accuracy.

    Used for optimization. If in doubt, return True;
    returning a false positive will merely make the optimizer a little
    less efficient, while returning a false negative may result in an
    unusable optimized migration.
    """
    return True

  def referencesField(self, modelName, name, appLabel=None):
    """
    Returns True if there is a chance this operation references the given
    field name, with an optional app label for accuracy.

    Used for optimization. If in doubt, return True.
    """
    return self.referencesModel(modelName, appLabel)

  def allowedToMigrate(self, connectionAlias, modal):
    """
    Returns if we're allowed to migrate the modal. Checks the router,
    if it's a proxy, if it's managed, and if it's swapped out.
    """
    return (
      router.allowMigrate(connectionAlias, modal) and
      not modal._meta.proxy and
      not modal._meta.swapped and
      modal._meta.managed
    )

  def __repr__(self):
    return "<%s %s%s>" % (
      self.__class__.__name__,
      ", ".join(map(repr, self._constructorArgs[0])),
      ",".join(" %s=%r" % x for x in self._constructorArgs[1].items()),
    )

  def __eq__(self, other):
    return (self.__class__ == other.__class__) and (self.deconstruct() == other.deconstruct())

  def __ne__(self, other):
    return not (self == other)
