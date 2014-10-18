from __future__ import unicode_literals

from theory.db.model.fields import NOT_PROVIDED
from theory.utils import six
from .base import Operation


class AddField(Operation):
  """
  Adds a field to a modal.
  """

  def __init__(self, modelName, name, field, preserveDefault=True):
    self.modelName = modelName
    self.name = name
    self.field = field
    self.preserveDefault = preserveDefault

  def stateForwards(self, appLabel, state):
    # If preserve default is off, don't use the default for future state
    if not self.preserveDefault:
      field = self.field.clone()
      field.default = NOT_PROVIDED
    else:
      field = self.field
    state.model[appLabel, self.modelName.lower()].fields.append((self.name, field))

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    fromModel = fromState.render().getModel(appLabel, self.modelName)
    toModel = toState.render().getModel(appLabel, self.modelName)
    if self.allowedToMigrate(schemaEditor.connection.alias, toModel):
      field = toModel._meta.getFieldByName(self.name)[0]
      if not self.preserveDefault:
        field.default = self.field.default
      schemaEditor.addField(
        fromModel,
        field,
      )
      if not self.preserveDefault:
        field.default = NOT_PROVIDED

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    fromModel = fromState.render().getModel(appLabel, self.modelName)
    if self.allowedToMigrate(schemaEditor.connection.alias, fromModel):
      schemaEditor.removeField(fromModel, fromModel._meta.getFieldByName(self.name)[0])

  def describe(self):
    return "Add field %s to %s" % (self.name, self.modelName)

  def __eq__(self, other):
    return (
      (self.__class__ == other.__class__) and
      (self.name == other.name) and
      (self.modelName.lower() == other.modelName.lower()) and
      (self.field.deconstruct()[1:] == other.field.deconstruct()[1:])
    )

  def referencesModel(self, name, appLabel=None):
    return name.lower() == self.modelName.lower()

  def referencesField(self, modelName, name, appLabel=None):
    return self.referencesModel(modelName) and name.lower() == self.name.lower()


class RemoveField(Operation):
  """
  Removes a field from a modal.
  """

  def __init__(self, modelName, name):
    self.modelName = modelName
    self.name = name

  def stateForwards(self, appLabel, state):
    newFields = []
    for name, instance in state.model[appLabel, self.modelName.lower()].fields:
      if name != self.name:
        newFields.append((name, instance))
    state.model[appLabel, self.modelName.lower()].fields = newFields

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    fromModel = fromState.render().getModel(appLabel, self.modelName)
    if self.allowedToMigrate(schemaEditor.connection.alias, fromModel):
      schemaEditor.removeField(fromModel, fromModel._meta.getFieldByName(self.name)[0])

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    fromModel = fromState.render().getModel(appLabel, self.modelName)
    toModel = toState.render().getModel(appLabel, self.modelName)
    if self.allowedToMigrate(schemaEditor.connection.alias, toModel):
      schemaEditor.addField(fromModel, toModel._meta.getFieldByName(self.name)[0])

  def describe(self):
    return "Remove field %s from %s" % (self.name, self.modelName)

  def referencesModel(self, name, appLabel=None):
    return name.lower() == self.modelName.lower()

  def referencesField(self, modelName, name, appLabel=None):
    return self.referencesModel(modelName) and name.lower() == self.name.lower()


class AlterField(Operation):
  """
  Alters a field's database column (e.g. null, maxLength) to the provided new field
  """

  def __init__(self, modelName, name, field):
    self.modelName = modelName
    self.name = name
    self.field = field

  def stateForwards(self, appLabel, state):
    state.model[appLabel, self.modelName.lower()].fields = [
      (n, self.field if n == self.name else f) for n, f in state.model[appLabel, self.modelName.lower()].fields
    ]

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    fromModel = fromState.render().getModel(appLabel, self.modelName)
    toModel = toState.render().getModel(appLabel, self.modelName)
    if self.allowedToMigrate(schemaEditor.connection.alias, toModel):
      fromField = fromModel._meta.getFieldByName(self.name)[0]
      toField = toModel._meta.getFieldByName(self.name)[0]
      # If the field is a relatedfield with an unresolved rel.to, just
      # set it equal to the other field side. Bandaid fix for AlterField
      # migrations that are part of a RenameModel change.
      if fromField.rel and fromField.rel.to:
        if isinstance(fromField.rel.to, six.stringTypes):
          fromField.rel.to = toField.rel.to
        elif toField.rel and isinstance(toField.rel.to, six.stringTypes):
          toField.rel.to = fromField.rel.to
      schemaEditor.alterField(fromModel, fromField, toField)

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    self.databaseForwards(appLabel, schemaEditor, fromState, toState)

  def describe(self):
    return "Alter field %s on %s" % (self.name, self.modelName)

  def __eq__(self, other):
    return (
      (self.__class__ == other.__class__) and
      (self.name == other.name) and
      (self.modelName.lower() == other.modelName.lower()) and
      (self.field.deconstruct()[1:] == other.field.deconstruct()[1:])
    )

  def referencesModel(self, name, appLabel=None):
    return name.lower() == self.modelName.lower()

  def referencesField(self, modelName, name, appLabel=None):
    return self.referencesModel(modelName) and name.lower() == self.name.lower()


class RenameField(Operation):
  """
  Renames a field on the modal. Might affect dbColumn too.
  """

  def __init__(self, modelName, oldName, newName):
    self.modelName = modelName
    self.oldName = oldName
    self.newName = newName

  def stateForwards(self, appLabel, state):
    # Rename the field
    state.model[appLabel, self.modelName.lower()].fields = [
      (self.newName if n == self.oldName else n, f) for n, f in state.model[appLabel, self.modelName.lower()].fields
    ]
    # Fix uniqueTogether to refer to the new field
    options = state.model[appLabel, self.modelName.lower()].options
    if "uniqueTogether" in options:
      options['uniqueTogether'] = [
        [self.newName if n == self.oldName else n for n in unique]
        for unique in options['uniqueTogether']
      ]

  def databaseForwards(self, appLabel, schemaEditor, fromState, toState):
    fromModel = fromState.render().getModel(appLabel, self.modelName)
    toModel = toState.render().getModel(appLabel, self.modelName)
    if self.allowedToMigrate(schemaEditor.connection.alias, toModel):
      schemaEditor.alterField(
        fromModel,
        fromModel._meta.getFieldByName(self.oldName)[0],
        toModel._meta.getFieldByName(self.newName)[0],
      )

  def databaseBackwards(self, appLabel, schemaEditor, fromState, toState):
    fromModel = fromState.render().getModel(appLabel, self.modelName)
    toModel = toState.render().getModel(appLabel, self.modelName)
    if self.allowedToMigrate(schemaEditor.connection.alias, toModel):
      schemaEditor.alterField(
        fromModel,
        fromModel._meta.getFieldByName(self.newName)[0],
        toModel._meta.getFieldByName(self.oldName)[0],
      )

  def describe(self):
    return "Rename field %s on %s to %s" % (self.oldName, self.modelName, self.newName)

  def referencesModel(self, name, appLabel=None):
    return name.lower() == self.modelName.lower()

  def referencesField(self, modelName, name, appLabel=None):
    return self.referencesModel(modelName) and (
      name.lower() == self.oldName.lower() or
      name.lower() == self.newName.lower()
    )
