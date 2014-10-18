from __future__ import unicode_literals

from .base import Operation


class SeparateDatabaseAndState(Operation):
  """
  Takes two lists of operations - ones that will be used for the database,
  and ones that will be used for the state change. This allows operations
  that don't support state change to have it applied, or have operations
  that affect the state or not the database, or so on.
  """

  def __init__(self, databaseOperations=None, stateOperations=None):
    self.databaseOperations = databaseOperations or []
    self.stateOperations = stateOperations or []

  def stateForwards(self, appLabel, state):
    for stateOperation in self.stateOperations:
      stateOperation.stateForwards(appLabel, state)

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    # We calculate state separately in here since our state functions aren't useful
    for databaseOperation in self.databaseOperations:
      toState = fromState.clone()
      databaseOperation.stateForwards(appLabel, toState)
      databaseOperation.databaseForwards(self, appLabel, schemaEditor, fromState, toState)
      fromState = toState

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    # We calculate state separately in here since our state functions aren't useful
    baseState = toState
    for pos, databaseOperation in enumerate(reversed(self.databaseOperations)):
      toState = baseState.clone()
      for dbop in self.databaseOperations[:-(pos + 1)]:
        dbop.stateForwards(appLabel, toState)
      fromState = baseState.clone()
      databaseOperation.stateForwards(appLabel, fromState)
      databaseOperation.databaseBackwards(self, appLabel, schemaEditor, fromState, toState)

  def describe(self):
    return "Custom state/database change combination"


class RunSQL(Operation):
  """
  Runs some raw SQL. A reverse SQL statement may be provided.

  Also accepts a list of operations that represent the state change effected
  by this SQL change, in case it's custom column/table creation/deletion.
  """

  def __init__(self, sql, reverseSql=None, stateOperations=None):
    self.sql = sql
    self.reverseSql = reverseSql
    self.stateOperations = stateOperations or []

  @property
  def reversible(self):
    return self.reverseSql is not None

  def stateForwards(self, appLabel, state):
    for stateOperation in self.stateOperations:
      stateOperation.stateForwards(appLabel, state)

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    statements = schemaEditor.connection.ops.prepareSqlScript(self.sql)
    for statement in statements:
      schemaEditor.execute(statement)

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    if self.reverseSql is None:
      raise NotImplementedError("You cannot reverse this operation")
    statements = schemaEditor.connection.ops.prepareSqlScript(self.reverseSql)
    for statement in statements:
      schemaEditor.execute(statement)

  def describe(self):
    return "Raw SQL operation"


class RunPython(Operation):
  """
  Runs Python code in a context suitable for doing versioned ORM operations.
  """

  reducesToSql = False

  def __init__(self, code, reverseCode=None, atomic=True):
    self.atomic = atomic
    # Forwards code
    if not callable(code):
      raise ValueError("RunPython must be supplied with a callable")
    self.code = code
    # Reverse code
    if reverseCode is None:
      self.reverseCode = None
    else:
      if not callable(reverseCode):
        raise ValueError("RunPython must be supplied with callable arguments")
      self.reverseCode = reverseCode

  @property
  def reversible(self):
    return self.reverseCode is not None

  def stateForwards(self, appLabel, state):
    # RunPython objects have no state effect. To add some, combine this
    # with SeparateDatabaseAndState.
    pass

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    # We now execute the Python code in a context that contains a 'model'
    # object, representing the versioned model as an app registry.
    # We could try to override the global cache, but then people will still
    # use direct imports, so we go with a documentation approach instead.
    self.code(fromState.render(), schemaEditor)

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    if self.reverseCode is None:
      raise NotImplementedError("You cannot reverse this operation")
    self.reverseCode(fromState.render(), schemaEditor)

  def describe(self):
    return "Raw Python operation"
