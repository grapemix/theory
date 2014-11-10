from __future__ import unicode_literals

from theory.db import model
from theory.db.model.options import normalizeTogether
from theory.db.migrations.state import ModelState
from theory.db.migrations.operations.base import Operation
from theory.utils import six


class CreateModel(Operation):
  """
  Create a modal's table.
  """

  serializationExpandArgs = ['fields', 'options']

  def __init__(self, name, fields, options=None, bases=None):
    self.name = name
    self.fields = fields
    self.options = options or {}
    self.bases = bases or (model.Model,)

  def stateForwards(self, appLabel, state):
    state.model[appLabel, self.name.lower()] = ModelState(
      appLabel,
      self.name,
      list(self.fields),
      dict(self.options),
      tuple(self.bases),
    )

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    apps = toState.render()
    modal = apps.getModel(appLabel, self.name)
    if self.allowedToMigrate(schemaEditor.connection.alias, modal):
      schemaEditor.createModel(modal)

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    apps = fromState.render()
    modal = apps.getModel(appLabel, self.name)
    if self.allowedToMigrate(schemaEditor.connection.alias, modal):
      schemaEditor.deleteModel(modal)

  def describe(self):
    return "Create %smodal %s" % ("proxy " if self.options.get("proxy", False) else "", self.name)

  def referencesModel(self, name, appLabel=None):
    stringsToCheck = [self.name]
    # Check we didn't inherit from the modal
    for base in self.bases:
      if isinstance(base, six.stringTypes):
        stringsToCheck.append(base.split(".")[-1])
    # Check we have no FKs/M2Ms with it
    for fname, field in self.fields:
      if field.rel:
        if isinstance(field.rel.to, six.stringTypes):
          stringsToCheck.append(field.rel.to.split(".")[-1])
    # Now go over all the strings and compare them
    for string in stringsToCheck:
      if string.lower() == name.lower():
        return True
    return False

  def __eq__(self, other):
    return (
      (self.__class__ == other.__class__) and
      (self.name == other.name) and
      (self.options == other.options) and
      (self.bases == other.bases) and
      ([(k, f.deconstruct()[1:]) for k, f in self.fields] == [(k, f.deconstruct()[1:]) for k, f in other.fields])
    )


class DeleteModel(Operation):
  """
  Drops a modal's table.
  """

  def __init__(self, name):
    self.name = name

  def stateForwards(self, appLabel, state):
    del state.model[appLabel, self.name.lower()]

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    apps = fromState.render()
    modal = apps.getModel(appLabel, self.name)
    if self.allowedToMigrate(schemaEditor.connection.alias, modal):
      schemaEditor.deleteModel(modal)

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    apps = toState.render()
    modal = apps.getModel(appLabel, self.name)
    if self.allowedToMigrate(schemaEditor.connection.alias, modal):
      schemaEditor.createModel(modal)

  def referencesModel(self, name, appLabel=None):
    return name.lower() == self.name.lower()

  def describe(self):
    return "Delete modal %s" % (self.name, )


class RenameModel(Operation):
  """
  Renames a modal.
  """

  reversible = False

  def __init__(self, oldName, newName):
    self.oldName = oldName
    self.newName = newName

  def stateForwards(self, appLabel, state):
    # Get all of the related objects we need to repoint
    apps = state.render(skipCache=True)
    modal = apps.getModel(appLabel, self.oldName)
    relatedObjects = modal._meta.getAllRelatedObjects()
    relatedM2mObjects = modal._meta.getAllRelatedManyToManyObjects()
    # Rename the modal
    state.model[appLabel, self.newName.lower()] = state.model[appLabel, self.oldName.lower()]
    state.model[appLabel, self.newName.lower()].name = self.newName
    del state.model[appLabel, self.oldName.lower()]
    # Repoint the FKs and M2Ms pointing to us
    for relatedObject in (relatedObjects + relatedM2mObjects):
      # Use the new related key for self referential related objects.
      if relatedObject.modal == modal:
        relatedKey = (appLabel, self.newName.lower())
      else:
        relatedKey = (
          relatedObject.modal._meta.appLabel,
          relatedObject.modal._meta.objectName.lower(),
        )
      newFields = []
      for name, field in state.model[relatedKey].fields:
        if name == relatedObject.field.name:
          field = field.clone()
          field.rel.to = "%s.%s" % (appLabel, self.newName)
        newFields.append((name, field))
      state.model[relatedKey].fields = newFields

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    oldApps = fromState.render()
    newApps = toState.render()
    oldModel = oldApps.getModel(appLabel, self.oldName)
    newModel = newApps.getModel(appLabel, self.newName)
    if self.allowedToMigrate(schemaEditor.connection.alias, newModel):
      # Move the main table
      schemaEditor.alterDbTable(
        newModel,
        oldModel._meta.dbTable,
        newModel._meta.dbTable,
      )
      # Alter the fields pointing to us
      relatedObjects = oldModel._meta.getAllRelatedObjects()
      relatedM2mObjects = oldModel._meta.getAllRelatedManyToManyObjects()
      for relatedObject in (relatedObjects + relatedM2mObjects):
        if relatedObject.modal == oldModel:
          modal = newModel
          relatedKey = (appLabel, self.newName.lower())
        else:
          modal = relatedObject.modal
          relatedKey = (
            relatedObject.modal._meta.appLabel,
            relatedObject.modal._meta.objectName.lower(),
          )
        toField = newApps.getModel(
          *relatedKey
        )._meta.getFieldByName(relatedObject.field.name)[0]
        schemaEditor.alterField(
          modal,
          relatedObject.field,
          toField,
        )

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    self.newName, self.oldName = self.oldName, self.newName
    self.databaseForwards(appLabel, schemaEditor, fromState, toState)
    self.newName, self.oldName = self.oldName, self.newName

  def referencesModel(self, name, appLabel=None):
    return (
      name.lower() == self.oldName.lower() or
      name.lower() == self.newName.lower()
    )

  def describe(self):
    return "Rename modal %s to %s" % (self.oldName, self.newName)


class AlterModelTable(Operation):
  """
  Renames a modal's table
  """

  def __init__(self, name, table):
    self.name = name
    self.table = table

  def stateForwards(self, appLabel, state):
    state.model[appLabel, self.name.lower()].options["dbTable"] = self.table

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    oldApps = fromState.render()
    newApps = toState.render()
    oldModel = oldApps.getModel(appLabel, self.name)
    newModel = newApps.getModel(appLabel, self.name)
    if self.allowedToMigrate(schemaEditor.connection.alias, newModel):
      schemaEditor.alterDbTable(
        newModel,
        oldModel._meta.dbTable,
        newModel._meta.dbTable,
      )

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    return self.databaseForwards(appLabel, schemaEditor, fromState, toState)

  def referencesModel(self, name, appLabel=None):
    return name.lower() == self.name.lower()

  def describe(self):
    return "Rename table for %s to %s" % (self.name, self.table)


class AlterUniqueTogether(Operation):
  """
  Changes the value of uniqueTogether to the target one.
  Input value of uniqueTogether must be a set of tuples.
  """
  optionName = "uniqueTogether"

  def __init__(self, name, uniqueTogether):
    self.name = name
    uniqueTogether = normalizeTogether(uniqueTogether)
    # need None rather than an empty set to prevent infinite migrations
    # after removing uniqueTogether from a modal
    self.uniqueTogether = set(tuple(cons) for cons in uniqueTogether) or None

  def stateForwards(self, appLabel, state):
    modalState = state.model[appLabel, self.name.lower()]
    modalState.options[self.optionName] = self.uniqueTogether

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    oldApps = fromState.render()
    newApps = toState.render()
    oldModel = oldApps.getModel(appLabel, self.name)
    newModel = newApps.getModel(appLabel, self.name)
    if self.allowedToMigrate(schemaEditor.connection.alias, newModel):
      schemaEditor.alterUniqueTogether(
        newModel,
        getattr(oldModel._meta, self.optionName, set()),
        getattr(newModel._meta, self.optionName, set()),
      )

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    return self.databaseForwards(appLabel, schemaEditor, fromState, toState)

  def referencesModel(self, name, appLabel=None):
    return name.lower() == self.name.lower()

  def describe(self):
    return "Alter %s for %s (%s constraint(s))" % (self.optionName, self.name, len(self.uniqueTogether or ''))


class AlterIndexTogether(Operation):
  """
  Changes the value of indexTogether to the target one.
  Input value of indexTogether must be a set of tuples.
  """
  optionName = "indexTogether"

  def __init__(self, name, indexTogether):
    self.name = name
    indexTogether = normalizeTogether(indexTogether)
    # need None rather than an empty set to prevent infinite migrations
    # after removing uniqueTogether from a modal
    self.indexTogether = set(tuple(cons) for cons in indexTogether) or None

  def stateForwards(self, appLabel, state):
    modalState = state.model[appLabel, self.name.lower()]
    modalState.options[self.optionName] = self.indexTogether

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    oldApps = fromState.render()
    newApps = toState.render()
    oldModel = oldApps.getModel(appLabel, self.name)
    newModel = newApps.getModel(appLabel, self.name)
    if self.allowedToMigrate(schemaEditor.connection.alias, newModel):
      schemaEditor.alterIndexTogether(
        newModel,
        getattr(oldModel._meta, self.optionName, set()),
        getattr(newModel._meta, self.optionName, set()),
      )

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    return self.databaseForwards(appLabel, schemaEditor, fromState, toState)

  def referencesModel(self, name, appLabel=None):
    return name.lower() == self.name.lower()

  def describe(self):
    return "Alter %s for %s (%s constraint(s))" % (self.optionName, self.name, len(self.indexTogether or ''))


class AlterOrderWithRespectTo(Operation):
  """
  Represents a change with the orderWithRespectTo option.
  """

  def __init__(self, name, orderWithRespectTo):
    self.name = name
    self.orderWithRespectTo = orderWithRespectTo

  def stateForwards(self, appLabel, state):
    modalState = state.model[appLabel, self.name.lower()]
    modalState.options['orderWithRespectTo'] = self.orderWithRespectTo

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    fromModel = fromState.render().getModel(appLabel, self.name)
    toModel = toState.render().getModel(appLabel, self.name)
    if self.allowedToMigrate(schemaEditor.connection.alias, toModel):
      # Remove a field if we need to
      if fromModel._meta.orderWithRespectTo and not toModel._meta.orderWithRespectTo:
        schemaEditor.removeField(fromModel, fromModel._meta.getFieldByName("_order")[0])
      # Add a field if we need to (altering the column is untouched as
      # it's likely a rename)
      elif toModel._meta.orderWithRespectTo and not fromModel._meta.orderWithRespectTo:
        field = toModel._meta.getFieldByName("_order")[0]
        schemaEditor.addField(
          fromModel,
          field,
        )

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    self.databaseForwards(appLabel, schemaEditor, fromState, toState)

  def referencesModel(self, name, appLabel=None):
    return name.lower() == self.name.lower()

  def describe(self):
    return "Set orderWithRespectTo on %s to %s" % (self.name, self.orderWithRespectTo)


class AlterModelOptions(Operation):
  """
  Sets new modal options that don't directly affect the database schema
  (like verboseName, permissions, ordering). Python code in migrations
  may still need them.
  """

  # Model options we want to compare and preserve in an AlterModelOptions op
  ALTER_OPTION_KEYS = [
    "getLatestBy",
    "ordering",
    "permissions",
    "defaultPermissions",
    "selectOnSave",
    "verboseName",
    "verboseNamePlural",
  ]

  def __init__(self, name, options):
    self.name = name
    self.options = options

  def stateForwards(self, appLabel, state):
    modalState = state.model[appLabel, self.name.lower()]
    modalState.options = dict(modalState.options)
    modalState.options.update(self.options)
    for key in self.ALTER_OPTION_KEYS:
      if key not in self.options and key in modalState.options:
        del modalState.options[key]

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    pass

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    pass

  def referencesModel(self, name, appLabel=None):
    return name.lower() == self.name.lower()

  def describe(self):
    return "Change Meta options on %s" % (self.name, )
