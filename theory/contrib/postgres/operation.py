from theory.contrib.postgres.signal import registerHstoreHandler
from theory.db.migrations.operations.base import Operation


class CreateExtension(Operation):
  reversible = True

  def __init__(self, name):
    self.name = name

  def stateForwards(self, appLabel, state):
    pass

  def databaseForwards(self, appLabel, schemaEditor, formState, toState):
    schemaEditor.execute("CREATE EXTENSION IF NOT EXISTS %s" % self.name)

  def databaseBackwards(self, appLabel, schemaEditor, formState, toState):
    schemaEditor.execute("DROP EXTENSION %s" % self.name)

  def describe(self):
    return "Creates extension %s" % self.name


class HStoreExtension(CreateExtension):

  def __init__(self):
    self.name = 'hstore'

  def databaseForwards(self, appLabel, schemaEditor, formState, toState):
    super(HStoreExtension, self).databaseForwards(appLabel, schemaEditor, formState, toState)
    # Register hstore straight away as it cannot be done before the
    # extension is installed, a subsequent data migration would use the
    # same connection
    registerHstoreHandler(schemaEditor.connection)


class UnaccentExtension(CreateExtension):

  def __init__(self):
    self.name = 'unaccent'
