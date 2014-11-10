from __future__ import unicode_literals

from theory.db import migrations
from theory.utils import six


class MigrationOptimizer(object):
  """
  Powers the optimization process, where you provide a list of Operations
  and you are returned a list of equal or shorter length - operations
  are merged into one if possible.

  For example, a CreateModel and an AddField can be optimized into a
  new CreateModel, and CreateModel and DeleteModel can be optimized into
  nothing.
  """

  def optimize(self, operations, appLabel=None):
    """
    Main optimization entry point. Pass in a list of Operation instances,
    get out a new list of Operation instances.

    Unfortunately, due to the scope of the optimization (two combinable
    operations might be separated by several hundred others), this can't be
    done as a peephole optimization with checks/output implemented on
    the Operations themselves; instead, the optimizer looks at each
    individual operation and scans forwards in the list to see if there
    are any matches, stopping at boundaries - operations which can't
    be optimized over (RunSQL, operations on the same field/modal, etc.)

    The inner loop is run until the starting list is the same as the result
    list, and then the result is returned. This means that operation
    optimization must be stable and always return an equal or shorter list.

    The appLabel argument is optional, but if you pass it you'll get more
    efficient optimization.
    """
    # Internal tracking variable for test assertions about # of loops
    self._iterations = 0
    while True:
      result = self.optimizeInner(operations, appLabel)
      self._iterations += 1
      if result == operations:
        return result
      operations = result

  def optimizeInner(self, operations, appLabel=None):
    """
    Inner optimization loop.
    """
    newOperations = []
    for i, operation in enumerate(operations):
      # Compare it to each operation after it
      for j, other in enumerate(operations[i + 1:]):
        result = self.reduce(operation, other, operations[i + 1:i + j + 1])
        if result is not None:
          # Optimize! Add result, then remaining others, then return
          newOperations.extend(result)
          newOperations.extend(operations[i + 1:i + 1 + j])
          newOperations.extend(operations[i + j + 2:])
          return newOperations
        if not self.canOptimizeThrough(operation, other, appLabel):
          newOperations.append(operation)
          break
      else:
        newOperations.append(operation)
    return newOperations

  #### REDUCTION ####

  def reduce(self, operation, other, inBetween=None):
    """
    Either returns a list of zero, one or two operations,
    or None, meaning this pair cannot be optimized.
    """
    submethods = [
      (
        migrations.CreateModel,
        migrations.DeleteModel,
        self.reduceModelCreateDelete,
      ),
      (
        migrations.AlterModelTable,
        migrations.DeleteModel,
        self.reduceModelAlterDelete,
      ),
      (
        migrations.AlterUniqueTogether,
        migrations.DeleteModel,
        self.reduceModelAlterDelete,
      ),
      (
        migrations.AlterIndexTogether,
        migrations.DeleteModel,
        self.reduceModelAlterDelete,
      ),
      (
        migrations.CreateModel,
        migrations.RenameModel,
        self.reduceModelCreateRename,
      ),
      (
        migrations.RenameModel,
        migrations.RenameModel,
        self.reduceModelRenameSelf,
      ),
      (
        migrations.CreateModel,
        migrations.AddField,
        self.reduceCreateModelAddField,
      ),
      (
        migrations.CreateModel,
        migrations.AlterField,
        self.reduceCreateModelAlterField,
      ),
      (
        migrations.CreateModel,
        migrations.RemoveField,
        self.reduceCreateModelRemoveField,
      ),
      (
        migrations.AddField,
        migrations.AlterField,
        self.reduceAddFieldAlterField,
      ),
      (
        migrations.AddField,
        migrations.RemoveField,
        self.reduceAddFieldDeleteField,
      ),
      (
        migrations.AlterField,
        migrations.RemoveField,
        self.reduceAlterFieldDeleteField,
      ),
      (
        migrations.AddField,
        migrations.RenameField,
        self.reduceAddFieldRenameField,
      ),
      (
        migrations.AlterField,
        migrations.RenameField,
        self.reduceAlterFieldRenameField,
      ),
      (
        migrations.CreateModel,
        migrations.RenameField,
        self.reduceCreateModelRenameField,
      ),
      (
        migrations.RenameField,
        migrations.RenameField,
        self.reduceRenameFieldSelf,
      ),
    ]
    for ia, ib, om in submethods:
      if isinstance(operation, ia) and isinstance(other, ib):
        return om(operation, other, inBetween or [])
    return None

  def modalToKey(self, modal):
    """
    Takes either a modal class or a "appname.ModelName" string
    and returns (appname, modalname)
    """
    if isinstance(modal, six.stringTypes):
      return modal.split(".", 1)
    else:
      return (
        modal._meta.appLabel,
        modal._meta.objectName,
      )

  def reduceModelCreateDelete(self, operation, other, inBetween):
    """
    Folds a CreateModel and a DeleteModel into nothing.
    """
    if (operation.name.lower() == other.name.lower() and
        not operation.options.get("proxy", False)):
      return []

  def reduceModelAlterDelete(self, operation, other, inBetween):
    """
    Folds an AlterModelSomething and a DeleteModel into just delete.
    """
    if operation.name.lower() == other.name.lower():
      return [other]

  def reduceModelCreateRename(self, operation, other, inBetween):
    """
    Folds a modal rename into its create
    """
    if operation.name.lower() == other.oldName.lower():
      return [
        migrations.CreateModel(
          other.newName,
          fields=operation.fields,
          options=operation.options,
          bases=operation.bases,
        )
      ]

  def reduceModelRenameSelf(self, operation, other, inBetween):
    """
    Folds a modal rename into another one
    """
    if operation.newName.lower() == other.oldName.lower():
      return [
        migrations.RenameModel(
          operation.oldName,
          other.newName,
        )
      ]

  def reduceCreateModelAddField(self, operation, other, inBetween):
    if operation.name.lower() == other.modelName.lower():
      # Don't allow optimisations of FKs through model they reference
      if hasattr(other.field, "rel") and other.field.rel:
        for between in inBetween:
          # Check that it doesn't point to the modal
          appLabel, objectName = self.modalToKey(other.field.rel.to)
          if between.referencesModel(objectName, appLabel):
            return None
          # Check that it's not through the modal
          if getattr(other.field.rel, "through", None):
            appLabel, objectName = self.modalToKey(other.field.rel.through)
            if between.referencesModel(objectName, appLabel):
              return None
      # OK, that's fine
      return [
        migrations.CreateModel(
          operation.name,
          fields=operation.fields + [(other.name, other.field)],
          options=operation.options,
          bases=operation.bases,
        )
      ]

  def reduceCreateModelAlterField(self, operation, other, inBetween):
    if operation.name.lower() == other.modelName.lower():
      return [
        migrations.CreateModel(
          operation.name,
          fields=[
            (n, other.field if n == other.name else v)
            for n, v in operation.fields
          ],
          options=operation.options,
          bases=operation.bases,
        )
      ]

  def reduceCreateModelRenameField(self, operation, other, inBetween):
    if operation.name.lower() == other.modelName.lower():
      return [
        migrations.CreateModel(
          operation.name,
          fields=[
            (other.newName if n == other.oldName else n, v)
            for n, v in operation.fields
          ],
          options=operation.options,
          bases=operation.bases,
        )
      ]

  def reduceCreateModelRemoveField(self, operation, other, inBetween):
    if operation.name.lower() == other.modelName.lower():
      return [
        migrations.CreateModel(
          operation.name,
          fields=[
            (n, v)
            for n, v in operation.fields
            if n.lower() != other.name.lower()
          ],
          options=operation.options,
          bases=operation.bases,
        )
      ]

  def reduceAddFieldAlterField(self, operation, other, inBetween):
    if operation.modelName.lower() == other.modelName.lower() and operation.name.lower() == other.name.lower():
      return [
        migrations.AddField(
          modelName=operation.modelName,
          name=operation.name,
          field=other.field,
        )
      ]

  def reduceAddFieldDeleteField(self, operation, other, inBetween):
    if operation.modelName.lower() == other.modelName.lower() and operation.name.lower() == other.name.lower():
      return []

  def reduceAlterFieldDeleteField(self, operation, other, inBetween):
    if operation.modelName.lower() == other.modelName.lower() and operation.name.lower() == other.name.lower():
      return [other]

  def reduceAddFieldRenameField(self, operation, other, inBetween):
    if operation.modelName.lower() == other.modelName.lower() and operation.name.lower() == other.oldName.lower():
      return [
        migrations.AddField(
          modelName=operation.modelName,
          name=other.newName,
          field=operation.field,
        )
      ]

  def reduceAlterFieldRenameField(self, operation, other, inBetween):
    if operation.modelName.lower() == other.modelName.lower() and operation.name.lower() == other.oldName.lower():
      return [
        other,
        migrations.AlterField(
          modelName=operation.modelName,
          name=other.newName,
          field=operation.field,
        ),
      ]

  def reduceRenameFieldSelf(self, operation, other, inBetween):
    if operation.modelName.lower() == other.modelName.lower() and operation.newName.lower() == other.oldName.lower():
      return [
        migrations.RenameField(
          operation.modelName,
          operation.oldName,
          other.newName,
        ),
      ]

  #### THROUGH CHECKS ####

  def canOptimizeThrough(self, operation, other, appLabel=None):
    """
    Returns True if it's possible to optimize 'operation' with something
    the other side of 'other'. This is possible if, for example, they
    affect different model.
    """
    MODEL_LEVEL_OPERATIONS = (
      migrations.CreateModel,
      migrations.AlterModelTable,
      migrations.AlterUniqueTogether,
      migrations.AlterIndexTogether,
    )
    FIELD_LEVEL_OPERATIONS = (
      migrations.AddField,
      migrations.AlterField,
    )
    # If it's a modal level operation, let it through if there's
    # nothing that looks like a reference to us in 'other'.
    if isinstance(operation, MODEL_LEVEL_OPERATIONS):
      if not other.referencesModel(operation.name, appLabel):
        return True
    # If it's field level, only let it through things that don't reference
    # the field (which includes not referencing the modal)
    if isinstance(operation, FIELD_LEVEL_OPERATIONS):
      if not other.referencesField(operation.modelName, operation.name, appLabel):
        return True
    return False
