from __future__ import unicode_literals
from theory.db.transaction import atomic


class Migration(object):
  """
  The base class for all migrations.

  Migration files will import this from theory.db.migrations.Migration
  and subclass it as a class called Migration. It will have one or more
  of the following attributes:

   - operations: A list of Operation instances, probably from theory.db.migrations.operations
   - dependencies: A list of tuples of (appPath, migrationName)
   - runBefore: A list of tuples of (appPath, migrationName)
   - replaces: A list of migrationNames

  Note that all migrations come out of migrations and into the Loader or
  Graph as instances, having been initialized with their app label and name.
  """

  # Operations to apply during this migration, in order.
  operations = []

  # Other migrations that should be run before this migration.
  # Should be a list of (app, migrationName).
  dependencies = []

  # Other migrations that should be run after this one (i.e. have
  # this migration added to their dependencies). Useful to make third-party
  # apps' migrations run after your AUTH_USER replacement, for example.
  runBefore = []

  # Migration names in this app that this migration replaces. If this is
  # non-empty, this migration will only be applied if all these migrations
  # are not applied.
  replaces = []

  # Error class which is raised when a migration is irreversible
  class IrreversibleError(RuntimeError):
    pass

  def __init__(self, name, appLabel):
    self.name = name
    self.appLabel = appLabel
    # Copy dependencies & other attrs as we might mutate them at runtime
    self.operations = list(self.__class__.operations)
    self.dependencies = list(self.__class__.dependencies)
    self.runBefore = list(self.__class__.runBefore)
    self.replaces = list(self.__class__.replaces)

  def __eq__(self, other):
    if not isinstance(other, Migration):
      return False
    return (self.name == other.name) and (self.appLabel == other.appLabel)

  def __ne__(self, other):
    return not (self == other)

  def __repr__(self):
    return "<Migration %s.%s>" % (self.appLabel, self.name)

  def __str__(self):
    return "%s.%s" % (self.appLabel, self.name)

  def __hash__(self):
    return hash("%s.%s" % (self.appLabel, self.name))

  def mutateState(self, projectState):
    """
    Takes a ProjectState and returns a new one with the migration's
    operations applied to it.
    """
    newState = projectState.clone()
    for operation in self.operations:
      operation.stateForwards(self.appLabel, newState)
    return newState

  def apply(self, projectState, schemaEditor, collectSql=False):
    """
    Takes a projectState representing all migrations prior to this one
    and a schemaEditor for a live database and applies the migration
    in a forwards order.

    Returns the resulting project state for efficient re-use by following
    Migrations.
    """
    for operation in self.operations:
      # If this operation cannot be represented as SQL, place a comment
      # there instead
      if collectSql and not operation.reducesToSql:
        schemaEditor.collectedSql.append("--")
        schemaEditor.collectedSql.append("-- MIGRATION NOW PERFORMS OPERATION THAT CANNOT BE WRITTEN AS SQL:")
        schemaEditor.collectedSql.append("-- %s" % operation.describe())
        schemaEditor.collectedSql.append("--")
        continue
      # Get the state after the operation has run
      newState = projectState.clone()
      operation.stateForwards(self.appLabel, newState)
      # Run the operation
      if not schemaEditor.connection.features.canRollbackDdl and operation.atomic:
        # We're forcing a transaction on a non-transactional-DDL backend
        with atomic(schemaEditor.connection.alias):
          operation.databaseForwards(self.appLabel, schemaEditor, projectState, newState)
      else:
        # Normal behaviour
        operation.databaseForwards(self.appLabel, schemaEditor, projectState, newState)
      # Switch states
      projectState = newState
    return projectState

  def unapply(self, projectState, schemaEditor, collectSql=False):
    """
    Takes a projectState representing all migrations prior to this one
    and a schemaEditor for a live database and applies the migration
    in a reverse order.
    """
    # We need to pre-calculate the stack of project states
    toRun = []
    for operation in self.operations:
      # If this operation cannot be represented as SQL, place a comment
      # there instead
      if collectSql and not operation.reducesToSql:
        schemaEditor.collectedSql.append("--")
        schemaEditor.collectedSql.append("-- MIGRATION NOW PERFORMS OPERATION THAT CANNOT BE WRITTEN AS SQL:")
        schemaEditor.collectedSql.append("-- %s" % operation.describe())
        schemaEditor.collectedSql.append("--")
        continue
      # If it's irreversible, error out
      if not operation.reversible:
        raise Migration.IrreversibleError("Operation %s in %s is not reversible" % (operation, self))
      newState = projectState.clone()
      operation.stateForwards(self.appLabel, newState)
      toRun.append((operation, projectState, newState))
      projectState = newState
    # Now run them in reverse
    toRun.reverse()
    for operation, toState, fromState in toRun:
      if not schemaEditor.connection.features.canRollbackDdl and operation.atomic:
        # We're forcing a transaction on a non-transactional-DDL backend
        with atomic(schemaEditor.connection.alias):
          operation.databaseBackwards(self.appLabel, schemaEditor, fromState, toState)
      else:
        # Normal behaviour
        operation.databaseBackwards(self.appLabel, schemaEditor, fromState, toState)
    return projectState


class SwappableTuple(tuple):
  """
  Subclass of tuple so Theory can tell this was originally a swappable
  dependency when it reads the migration file.
  """

  def __new__(cls, value, setting):
    self = tuple.__new__(cls, value)
    self.setting = setting
    return self


def swappableDependency(value):
  """
  Turns a setting value into a dependency.
  """
  return SwappableTuple((value.split(".", 1)[0], "__first__"), value)
