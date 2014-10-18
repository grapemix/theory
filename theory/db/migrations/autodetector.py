from __future__ import unicode_literals

import re
import datetime

from theory.utils import six
from theory.db import model
from theory.conf import settings
from theory.db.migrations import operations
from theory.db.migrations.migration import Migration
from theory.db.migrations.questioner import MigrationQuestioner
from theory.db.migrations.optimizer import MigrationOptimizer
from theory.db.migrations.operations.model import AlterModelOptions


class MigrationAutodetector(object):
  """
  Takes a pair of ProjectStates, and compares them to see what the
  first would need doing to make it match the second (the second
  usually being the project's current state).

  Note that this naturally operates on entire projects at a time,
  as it's likely that changes interact (for example, you can't
  add a ForeignKey without having a migration to add the table it
  depends on first). A user interface may offer single-app usage
  if it wishes, with the caveat that it may not always be possible.
  """

  def __init__(self, fromState, toState, questioner=None):
    self.fromState = fromState
    self.toState = toState
    self.questioner = questioner or MigrationQuestioner()

  def changes(self, graph, trimToApps=None, convertApps=None):
    """
    Main entry point to produce a list of appliable changes.
    Takes a graph to base names on and an optional set of apps
    to try and restrict to (restriction is not guaranteed)
    """
    changes = self._detectChanges(convertApps, graph)
    changes = self.arrangeForGraph(changes, graph)
    if trimToApps:
      changes = self._trimToApps(changes, trimToApps)
    return changes

  def deepDeconstruct(self, obj):
    """
    Recursive deconstruction for a field and its arguments.
    Used for full comparison for rename/alter; sometimes a single-level
    deconstruction will not compare correctly.
    """
    if not hasattr(obj, 'deconstruct'):
      return obj
    deconstructed = obj.deconstruct()
    if isinstance(obj, model.Field):
      # we have a field which also returns a name
      deconstructed = deconstructed[1:]
    path, args, kwargs = deconstructed
    return (
      path,
      [self.deepDeconstruct(value) for value in args],
      dict(
        (key, self.deepDeconstruct(value))
        for key, value in kwargs.items()
      ),
    )

  def onlyRelationAgnosticFields(self, fields):
    """
    Return a definition of the fields that ignores field names and
    what related fields actually relate to.
    Used for detecting renames (as, of course, the related fields
    change during renames)
    """
    fieldsDef = []
    for name, field in fields:
      deconstruction = self.deepDeconstruct(field)
      if field.rel and field.rel.to:
        del deconstruction[2]['to']
      fieldsDef.append(deconstruction)
    return fieldsDef

  def _detectChanges(self, convertApps=None, graph=None):
    """
    Returns a dict of migration plans which will achieve the
    change from fromState to toState. The dict has app labels
    as keys and a list of migrations as values.

    The resulting migrations aren't specially named, but the names
    do matter for dependencies inside the set.

    convertApps is the list of apps to convert to use migrations
    (i.e. to make initial migrations for, in the usual case)

    graph is an optional argument that, if provided, can help improve
    dependency generation and avoid potential circular dependencies.
    """

    # The first phase is generating all the operations for each app
    # and gathering them into a big per-app list.
    # We'll then go through that list later and order it and split
    # into migrations to resolve dependencies caused by M2Ms and FKs.
    self.generatedOperations = {}

    # Prepare some old/new state and modal lists, separating
    # proxy model and ignoring unmigrated apps.
    self.oldApps = self.fromState.render(ignoreSwappable=True)
    self.newApps = self.toState.render()
    self.oldModelKeys = []
    self.oldProxyKeys = []
    self.oldUnmanagedKeys = []
    self.newModelKeys = []
    self.newProxyKeys = []
    self.newUnmanagedKeys = []
    for al, mn in sorted(self.fromState.model.keys()):
      modal = self.oldApps.getModel(al, mn)
      if not modal._meta.managed:
        self.oldUnmanagedKeys.append((al, mn))
      elif al not in self.fromState.realApps:
        if modal._meta.proxy:
          self.oldProxyKeys.append((al, mn))
        else:
          self.oldModelKeys.append((al, mn))

    for al, mn in sorted(self.toState.model.keys()):
      modal = self.newApps.getModel(al, mn)
      if not modal._meta.managed:
        self.newUnmanagedKeys.append((al, mn))
      elif (
        al not in self.fromState.realApps or
        (convertApps and al in convertApps)
      ):
        if modal._meta.proxy:
          self.newProxyKeys.append((al, mn))
        else:
          self.newModelKeys.append((al, mn))

    # Renames have to come first
    self.generateRenamedModels()

    # Prepare field lists, and prepare a list of the fields that used
    # through model in the old state so we can make dependencies
    # from the through modal deletion to the field that uses it.
    self.keptModelKeys = set(self.oldModelKeys).intersection(self.newModelKeys)
    self.keptProxyKeys = set(self.oldProxyKeys).intersection(self.newProxyKeys)
    self.keptUnmanagedKeys = set(self.oldUnmanagedKeys).intersection(self.newUnmanagedKeys)
    self.throughUsers = {}
    self.oldFieldKeys = set()
    self.newFieldKeys = set()
    for appLabel, modelName in sorted(self.keptModelKeys):
      oldModelName = self.renamedModels.get((appLabel, modelName), modelName)
      oldModelState = self.fromState.model[appLabel, oldModelName]
      newModelState = self.toState.model[appLabel, modelName]
      self.oldFieldKeys.update((appLabel, modelName, x) for x, y in oldModelState.fields)
      self.newFieldKeys.update((appLabel, modelName, x) for x, y in newModelState.fields)

    # Through modal map generation
    for appLabel, modelName in sorted(self.oldModelKeys):
      oldModelName = self.renamedModels.get((appLabel, modelName), modelName)
      oldModelState = self.fromState.model[appLabel, oldModelName]
      for fieldName, field in oldModelState.fields:
        oldField = self.oldApps.getModel(appLabel, oldModelName)._meta.getFieldByName(fieldName)[0]
        if hasattr(oldField, "rel") and getattr(oldField.rel, "through", None) and not oldField.rel.through._meta.autoCreated:
          throughKey = (
            oldField.rel.through._meta.appLabel,
            oldField.rel.through._meta.objectName.lower(),
          )
          self.throughUsers[throughKey] = (appLabel, oldModelName, fieldName)

    # Generate non-rename modal operations
    self.generateDeletedModels()
    self.generateCreatedModels()
    self.generateDeletedProxies()
    self.generateCreatedProxies()
    self.generateDeletedUnmanaged()
    self.generateCreatedUnmanaged()
    self.generateAlteredOptions()

    # Generate field operations
    self.generateRenamedFields()
    self.generateRemovedFields()
    self.generateAddedFields()
    self.generateAlteredFields()
    self.generateAlteredUniqueTogether()
    self.generateAlteredIndexTogether()
    self.generateAlteredOrderWithRespectTo()

    # Now, reordering to make things possible. The order we have already
    # isn't bad, but we need to pull a few things around so FKs work nicely
    # inside the same app
    for appLabel, ops in sorted(self.generatedOperations.items()):
      for i in range(10000):
        found = False
        for i, op in enumerate(ops):
          for dep in op._autoDeps:
            if dep[0] == appLabel:
              # Alright, there's a dependency on the same app.
              for j, op2 in enumerate(ops):
                if self.checkDependency(op2, dep) and j > i:
                  ops = ops[:i] + ops[i + 1:j + 1] + [op] + ops[j + 1:]
                  found = True
                  break
            if found:
              break
          if found:
            break
        if not found:
          break
      else:
        raise ValueError("Infinite loop caught in operation dependency resolution")
      self.generatedOperations[appLabel] = ops

    # Now, we need to chop the lists of operations up into migrations with
    # dependencies on each other.
    # We do this by stepping up an app's list of operations until we
    # find one that has an outgoing dependency that isn't in another app's
    # migration yet (hasn't been chopped off its list). We then chop off the
    # operations before it into a migration and move onto the next app.
    # If we loop back around without doing anything, there's a circular
    # dependency (which _should_ be impossible as the operations are all
    # split at this point so they can't depend and be depended on)

    self.migrations = {}
    numOps = sum(len(x) for x in self.generatedOperations.values())
    chopMode = False
    while numOps:
      # On every iteration, we step through all the apps and see if there
      # is a completed set of operations.
      # If we find that a subset of the operations are complete we can
      # try to chop it off from the rest and continue, but we only
      # do this if we've already been through the list once before
      # without any chopping and nothing has changed.
      for appLabel in sorted(self.generatedOperations.keys()):
        chopped = []
        dependencies = set()
        for operation in list(self.generatedOperations[appLabel]):
          depsSatisfied = True
          operationDependencies = set()
          for dep in operation._autoDeps:
            isSwappableDep = False
            if dep[0] == "__setting__":
              # We need to temporarily resolve the swappable dependency to prevent
              # circular references. While keeping the dependency checks on the
              # resolved modal we still add the swappable dependencies.
              # See #23322
              resolvedAppLabel, resolvedObjectName = getattr(settings, dep[1]).split('.')
              originalDep = dep
              dep = (resolvedAppLabel, resolvedObjectName.lower(), dep[2], dep[3])
              isSwappableDep = True
            if dep[0] != appLabel and dep[0] != "__setting__":
              # External app dependency. See if it's not yet
              # satisfied.
              for otherOperation in self.generatedOperations.get(dep[0], []):
                if self.checkDependency(otherOperation, dep):
                  depsSatisfied = False
                  break
              if not depsSatisfied:
                break
              else:
                if isSwappableDep:
                  operationDependencies.add((originalDep[0], originalDep[1]))
                elif dep[0] in self.migrations:
                  operationDependencies.add((dep[0], self.migrations[dep[0]][-1].name))
                else:
                  # If we can't find the other app, we add a first/last dependency,
                  # but only if we've already been through once and checked everything
                  if chopMode:
                    # If the app already exists, we add a dependency on the last migration,
                    # as we don't know which migration contains the target field.
                    # If it's not yet migrated or has no migrations, we use __first__
                    if graph and graph.leafNodes(dep[0]):
                      operationDependencies.add(graph.leafNodes(dep[0])[0])
                    else:
                      operationDependencies.add((dep[0], "__first__"))
                  else:
                    depsSatisfied = False
          if depsSatisfied:
            chopped.append(operation)
            dependencies.update(operationDependencies)
            self.generatedOperations[appLabel] = self.generatedOperations[appLabel][1:]
          else:
            break
        # Make a migration! Well, only if there's stuff to put in it
        if dependencies or chopped:
          if not self.generatedOperations[appLabel] or chopMode:
            subclass = type(str("Migration"), (Migration,), {"operations": [], "dependencies": []})
            instance = subclass("auto_%i" % (len(self.migrations.get(appLabel, [])) + 1), appLabel)
            instance.dependencies = list(dependencies)
            instance.operations = chopped
            self.migrations.setdefault(appLabel, []).append(instance)
            chopMode = False
          else:
            self.generatedOperations[appLabel] = chopped + self.generatedOperations[appLabel]
      newNumOps = sum(len(x) for x in self.generatedOperations.values())
      if newNumOps == numOps:
        if not chopMode:
          chopMode = True
        else:
          raise ValueError("Cannot resolve operation dependencies: %r" % self.generatedOperations)
      numOps = newNumOps

    # OK, add in internal dependencies among the migrations
    for appLabel, migrations in self.migrations.items():
      for m1, m2 in zip(migrations, migrations[1:]):
        m2.dependencies.append((appLabel, m1.name))

    # De-dupe dependencies
    for appLabel, migrations in self.migrations.items():
      for migration in migrations:
        migration.dependencies = list(set(migration.dependencies))

    # Optimize migrations
    for appLabel, migrations in self.migrations.items():
      for migration in migrations:
        migration.operations = MigrationOptimizer().optimize(migration.operations, appLabel=appLabel)

    return self.migrations

  def checkDependency(self, operation, dependency):
    """
    Checks if an operation dependency matches an operation.
    """
    # Created modal
    if dependency[2] is None and dependency[3] is True:
      return (
        isinstance(operation, operations.CreateModel) and
        operation.name.lower() == dependency[1].lower()
      )
    # Created field
    elif dependency[2] is not None and dependency[3] is True:
      return (
        (
          isinstance(operation, operations.CreateModel) and
          operation.name.lower() == dependency[1].lower() and
          any(dependency[2] == x for x, y in operation.fields)
        ) or
        (
          isinstance(operation, operations.AddField) and
          operation.modelName.lower() == dependency[1].lower() and
          operation.name.lower() == dependency[2].lower()
        )
      )
    # Removed field
    elif dependency[2] is not None and dependency[3] is False:
      return (
        isinstance(operation, operations.RemoveField) and
        operation.modelName.lower() == dependency[1].lower() and
        operation.name.lower() == dependency[2].lower()
      )
    # Removed modal
    elif dependency[2] is None and dependency[3] is False:
      return (
        isinstance(operation, operations.DeleteModel) and
        operation.name.lower() == dependency[1].lower()
      )
    # Field being altered
    elif dependency[2] is not None and dependency[3] == "alter":
      return (
        isinstance(operation, operations.AlterField) and
        operation.modelName.lower() == dependency[1].lower() and
        operation.name.lower() == dependency[2].lower()
      )
    # orderWithRespectTo being unset for a field
    elif dependency[2] is not None and dependency[3] == "orderWrtUnset":
      return (
        isinstance(operation, operations.AlterOrderWithRespectTo) and
        operation.name.lower() == dependency[1].lower() and
        (operation.orderWithRespectTo or "").lower() != dependency[2].lower()
      )
    # Unknown dependency. Raise an error.
    else:
      raise ValueError("Can't handle dependency %r" % (dependency, ))

  def addOperation(self, appLabel, operation, dependencies=None, beginning=False):
    # Dependencies are (appLabel, modelName, fieldName, create/delete as True/False)
    operation._autoDeps = dependencies or []
    if beginning:
      self.generatedOperations.setdefault(appLabel, []).insert(0, operation)
    else:
      self.generatedOperations.setdefault(appLabel, []).append(operation)

  def swappableFirstKey(self, item):
    """
    Sorting key function that places potential swappable model first in
    lists of created model (only real way to solve #22783)
    """
    try:
      modal = self.newApps.getModel(item[0], item[1])
      baseNames = [base.__name__ for base in modal.__bases__]
      stringVersion = "%s.%s" % (item[0], item[1])
      if (
        modal._meta.swappable or
        "AbstractUser" in baseNames or
        "AbstractBaseUser" in baseNames or
        settings.AUTH_USER_MODEL.lower() == stringVersion.lower()
      ):
        return ("___" + item[0], "___" + item[1])
    except LookupError:
      pass
    return item

  def generateRenamedModels(self):
    """
    Finds any renamed model, and generates the operations for them,
    and removes the old entry from the modal lists.
    Must be run before other modal-level generation.
    """
    self.renamedModels = {}
    self.renamedModelsRel = {}
    addedModels = set(self.newModelKeys) - set(self.oldModelKeys)
    for appLabel, modelName in sorted(addedModels):
      modalState = self.toState.model[appLabel, modelName]
      modalFieldsDef = self.onlyRelationAgnosticFields(modalState.fields)

      removedModels = set(self.oldModelKeys) - set(self.newModelKeys)
      for remAppLabel, remModelName in removedModels:
        if remAppLabel == appLabel:
          remModelState = self.fromState.model[remAppLabel, remModelName]
          remModelFieldsDef = self.onlyRelationAgnosticFields(remModelState.fields)
          if modalFieldsDef == remModelFieldsDef:
            if self.questioner.askRenameModel(remModelState, modalState):
              self.addOperation(
                appLabel,
                operations.RenameModel(
                  oldName=remModelState.name,
                  newName=modalState.name,
                )
              )
              self.renamedModels[appLabel, modelName] = remModelName
              self.renamedModelsRel['%s.%s' % (remModelState.appLabel, remModelState.name)] = '%s.%s' % (modalState.appLabel, modalState.name)
              self.oldModelKeys.remove((remAppLabel, remModelName))
              self.oldModelKeys.append((appLabel, modelName))
              break

  def generateCreatedModels(self):
    """
    Find all new model and make creation operations for them,
    and separate operations to create any foreign key or M2M relationships
    (we'll optimise these back in later if we can)

    We also defer any modal options that refer to collections of fields
    that might be deferred (e.g. uniqueTogether, indexTogether)
    """
    addedModels = set(self.newModelKeys) - set(self.oldModelKeys)
    for appLabel, modelName in sorted(addedModels, key=self.swappableFirstKey, reverse=True):
      modalState = self.toState.model[appLabel, modelName]
      # Gather related fields
      relatedFields = {}
      primaryKeyRel = None
      for field in self.newApps.getModel(appLabel, modelName)._meta.localFields:
        if field.rel:
          if field.rel.to:
            if field.primaryKey:
              primaryKeyRel = field.rel.to
            else:
              relatedFields[field.name] = field
          # through will be none on M2Ms on swapped-out model;
          # we can treat lack of through as autoCreated=True, though.
          if getattr(field.rel, "through", None) and not field.rel.through._meta.autoCreated:
            relatedFields[field.name] = field
      for field in self.newApps.getModel(appLabel, modelName)._meta.localManyToMany:
        if field.rel.to:
          relatedFields[field.name] = field
        if getattr(field.rel, "through", None) and not field.rel.through._meta.autoCreated:
          relatedFields[field.name] = field
      # Are there unique/indexTogether to defer?
      uniqueTogether = modalState.options.pop('uniqueTogether', None)
      indexTogether = modalState.options.pop('indexTogether', None)
      orderWithRespectTo = modalState.options.pop('orderWithRespectTo', None)
      # Depend on the deletion of any possible proxy version of us
      dependencies = [
        (appLabel, modelName, None, False),
      ]
      # Depend on all bases
      for base in modalState.bases:
        if isinstance(base, six.stringTypes) and "." in base:
          baseAppLabel, baseName = base.split(".", 1)
          dependencies.append((baseAppLabel, baseName, None, True))
      # Depend on the other end of the primary key if it's a relation
      if primaryKeyRel:
        dependencies.append((
          primaryKeyRel._meta.appLabel,
          primaryKeyRel._meta.objectName,
          None,
          True
        ))
      # Generate creation operation
      self.addOperation(
        appLabel,
        operations.CreateModel(
          name=modalState.name,
          fields=[d for d in modalState.fields if d[0] not in relatedFields],
          options=modalState.options,
          bases=modalState.bases,
        ),
        dependencies=dependencies,
        beginning=True,
      )
      # Generate operations for each related field
      for name, field in sorted(relatedFields.items()):
        # Account for FKs to swappable model
        swappableSetting = getattr(field, 'swappableSetting', None)
        if swappableSetting is not None:
          depAppLabel = "__setting__"
          depObjectName = swappableSetting
        else:
          depAppLabel = field.rel.to._meta.appLabel
          depObjectName = field.rel.to._meta.objectName
        dependencies = [(depAppLabel, depObjectName, None, True)]
        if getattr(field.rel, "through", None) and not field.rel.through._meta.autoCreated:
          dependencies.append((
            field.rel.through._meta.appLabel,
            field.rel.through._meta.objectName,
            None,
            True
          ))
        # Depend on our own modal being created
        dependencies.append((appLabel, modelName, None, True))
        # Make operation
        self.addOperation(
          appLabel,
          operations.AddField(
            modelName=modelName,
            name=name,
            field=field,
          ),
          dependencies=list(set(dependencies)),
        )
      # Generate other opns
      relatedDependencies = [
        (appLabel, modelName, name, True)
        for name, field in sorted(relatedFields.items())
      ]
      relatedDependencies.append((appLabel, modelName, None, True))
      if uniqueTogether:
        self.addOperation(
          appLabel,
          operations.AlterUniqueTogether(
            name=modelName,
            uniqueTogether=uniqueTogether,
          ),
          dependencies=relatedDependencies
        )
      if indexTogether:
        self.addOperation(
          appLabel,
          operations.AlterIndexTogether(
            name=modelName,
            indexTogether=indexTogether,
          ),
          dependencies=relatedDependencies
        )
      if orderWithRespectTo:
        self.addOperation(
          appLabel,
          operations.AlterOrderWithRespectTo(
            name=modelName,
            orderWithRespectTo=orderWithRespectTo,
          ),
          dependencies=[
            (appLabel, modelName, orderWithRespectTo, True),
            (appLabel, modelName, None, True),
          ]
        )

  def generateCreatedProxies(self, unmanaged=False):
    """
    Makes CreateModel statements for proxy model.
    We use the same statements as that way there's less code duplication,
    but of course for proxy model we can skip all that pointless field
    stuff and just chuck out an operation.
    """
    if unmanaged:
      added = set(self.newUnmanagedKeys) - set(self.oldUnmanagedKeys)
    else:
      added = set(self.newProxyKeys) - set(self.oldProxyKeys)
    for appLabel, modelName in sorted(added):
      modalState = self.toState.model[appLabel, modelName]
      if unmanaged:
        assert not modalState.options.get("managed", True)
      else:
        assert modalState.options.get("proxy", False)
      # Depend on the deletion of any possible non-proxy version of us
      dependencies = [
        (appLabel, modelName, None, False),
      ]
      # Depend on all bases
      for base in modalState.bases:
        if isinstance(base, six.stringTypes) and "." in base:
          baseAppLabel, baseName = base.split(".", 1)
          dependencies.append((baseAppLabel, baseName, None, True))
      # Generate creation operation
      self.addOperation(
        appLabel,
        operations.CreateModel(
          name=modalState.name,
          fields=[],
          options=modalState.options,
          bases=modalState.bases,
        ),
        # Depend on the deletion of any possible non-proxy version of us
        dependencies=dependencies,
      )

  def generateCreatedUnmanaged(self):
    """
    Similar to generateCreatedProxies but for unmanaged
    (they are similar to us in that we need to supply them, but they don't
    affect the DB)
    """
    # Just re-use the same code in *_proxies
    self.generateCreatedProxies(unmanaged=True)

  def generateDeletedModels(self):
    """
    Find all deleted model and make creation operations for them,
    and separate operations to delete any foreign key or M2M relationships
    (we'll optimise these back in later if we can)

    We also bring forward removal of any modal options that refer to
    collections of fields - the inverse of generateCreatedModels.
    """
    deletedModels = set(self.oldModelKeys) - set(self.newModelKeys)
    for appLabel, modelName in sorted(deletedModels):
      modalState = self.fromState.model[appLabel, modelName]
      modal = self.oldApps.getModel(appLabel, modelName)
      # Gather related fields
      relatedFields = {}
      for field in modal._meta.localFields:
        if field.rel:
          if field.rel.to:
            relatedFields[field.name] = field
          # through will be none on M2Ms on swapped-out model;
          # we can treat lack of through as autoCreated=True, though.
          if getattr(field.rel, "through", None) and not field.rel.through._meta.autoCreated:
            relatedFields[field.name] = field
      for field in modal._meta.localManyToMany:
        if field.rel.to:
          relatedFields[field.name] = field
        if getattr(field.rel, "through", None) and not field.rel.through._meta.autoCreated:
          relatedFields[field.name] = field
      # Generate option removal first
      uniqueTogether = modalState.options.pop('uniqueTogether', None)
      indexTogether = modalState.options.pop('indexTogether', None)
      if uniqueTogether:
        self.addOperation(
          appLabel,
          operations.AlterUniqueTogether(
            name=modelName,
            uniqueTogether=None,
          )
        )
      if indexTogether:
        self.addOperation(
          appLabel,
          operations.AlterIndexTogether(
            name=modelName,
            indexTogether=None,
          )
        )
      # Then remove each related field
      for name, field in sorted(relatedFields.items()):
        self.addOperation(
          appLabel,
          operations.RemoveField(
            modelName=modelName,
            name=name,
          )
        )
      # Finally, remove the modal.
      # This depends on both the removal/alteration of all incoming fields
      # and the removal of all its own related fields, and if it's
      # a through modal the field that references it.
      dependencies = []
      for relatedObject in modal._meta.getAllRelatedObjects():
        dependencies.append((
          relatedObject.modal._meta.appLabel,
          relatedObject.modal._meta.objectName,
          relatedObject.field.name,
          False,
        ))
        dependencies.append((
          relatedObject.modal._meta.appLabel,
          relatedObject.modal._meta.objectName,
          relatedObject.field.name,
          "alter",
        ))
      for relatedObject in modal._meta.getAllRelatedManyToManyObjects():
        dependencies.append((
          relatedObject.modal._meta.appLabel,
          relatedObject.modal._meta.objectName,
          relatedObject.field.name,
          False,
        ))
      for name, field in sorted(relatedFields.items()):
        dependencies.append((appLabel, modelName, name, False))
      # We're referenced in another field's through=
      throughUser = self.throughUsers.get((appLabel, modalState.name.lower()), None)
      if throughUser:
        dependencies.append((throughUser[0], throughUser[1], throughUser[2], False))
      # Finally, make the operation, deduping any dependencies
      self.addOperation(
        appLabel,
        operations.DeleteModel(
          name=modalState.name,
        ),
        dependencies=list(set(dependencies)),
      )

  def generateDeletedProxies(self, unmanaged=False):
    """
    Makes DeleteModel statements for proxy model.
    """
    if unmanaged:
      deleted = set(self.oldUnmanagedKeys) - set(self.newUnmanagedKeys)
    else:
      deleted = set(self.oldProxyKeys) - set(self.newProxyKeys)
    for appLabel, modelName in sorted(deleted):
      modalState = self.fromState.model[appLabel, modelName]
      if unmanaged:
        assert not modalState.options.get("managed", True)
      else:
        assert modalState.options.get("proxy", False)
      self.addOperation(
        appLabel,
        operations.DeleteModel(
          name=modalState.name,
        ),
      )

  def generateDeletedUnmanaged(self):
    """
    Makes DeleteModel statements for unmanaged model
    """
    self.generateDeletedProxies(unmanaged=True)

  def generateRenamedFields(self):
    """
    Works out renamed fields
    """
    self.renamedFields = {}
    for appLabel, modelName, fieldName in sorted(self.newFieldKeys - self.oldFieldKeys):
      oldModelName = self.renamedModels.get((appLabel, modelName), modelName)
      oldModelState = self.fromState.model[appLabel, oldModelName]
      field = self.newApps.getModel(appLabel, modelName)._meta.getFieldByName(fieldName)[0]
      # Scan to see if this is actually a rename!
      fieldDec = self.deepDeconstruct(field)
      for remAppLabel, remModelName, remFieldName in sorted(self.oldFieldKeys - self.newFieldKeys):
        if remAppLabel == appLabel and remModelName == modelName:
          oldFieldDec = self.deepDeconstruct(oldModelState.getFieldByName(remFieldName))
          if field.rel and field.rel.to and 'to' in oldFieldDec[2]:
            oldRelTo = oldFieldDec[2]['to']
            if oldRelTo in self.renamedModelsRel:
              oldFieldDec[2]['to'] = self.renamedModelsRel[oldRelTo]
          if oldFieldDec == fieldDec:
            if self.questioner.askRename(modelName, remFieldName, fieldName, field):
              self.addOperation(
                appLabel,
                operations.RenameField(
                  modelName=modelName,
                  oldName=remFieldName,
                  newName=fieldName,
                )
              )
              self.oldFieldKeys.remove((remAppLabel, remModelName, remFieldName))
              self.oldFieldKeys.add((appLabel, modelName, fieldName))
              self.renamedFields[appLabel, modelName, fieldName] = remFieldName
              break

  def generateAddedFields(self):
    """
    Fields that have been added
    """
    for appLabel, modelName, fieldName in sorted(self.newFieldKeys - self.oldFieldKeys):
      field = self.newApps.getModel(appLabel, modelName)._meta.getFieldByName(fieldName)[0]
      # Fields that are foreignkeys/m2ms depend on stuff
      dependencies = []
      if field.rel and field.rel.to:
        # Account for FKs to swappable model
        swappableSetting = getattr(field, 'swappableSetting', None)
        if swappableSetting is not None:
          depAppLabel = "__setting__"
          depObjectName = swappableSetting
        else:
          depAppLabel = field.rel.to._meta.appLabel
          depObjectName = field.rel.to._meta.objectName
        dependencies = [(depAppLabel, depObjectName, None, True)]
        if getattr(field.rel, "through", None) and not field.rel.through._meta.autoCreated:
          dependencies.append((
            field.rel.through._meta.appLabel,
            field.rel.through._meta.objectName,
            None,
            True
          ))
      # You can't just add NOT NULL fields with no default
      if not field.null and not field.hasDefault() and not isinstance(field, model.ManyToManyField):
        field = field.clone()
        field.default = self.questioner.askNotNullAddition(fieldName, modelName)
        self.addOperation(
          appLabel,
          operations.AddField(
            modelName=modelName,
            name=fieldName,
            field=field,
            preserveDefault=False,
          ),
          dependencies=dependencies,
        )
      else:
        self.addOperation(
          appLabel,
          operations.AddField(
            modelName=modelName,
            name=fieldName,
            field=field,
          ),
          dependencies=dependencies,
        )

  def generateRemovedFields(self):
    """
    Fields that have been removed.
    """
    for appLabel, modelName, fieldName in sorted(self.oldFieldKeys - self.newFieldKeys):
      self.addOperation(
        appLabel,
        operations.RemoveField(
          modelName=modelName,
          name=fieldName,
        ),
        # We might need to depend on the removal of an orderWithRespectTo;
        # this is safely ignored if there isn't one
        dependencies=[(appLabel, modelName, fieldName, "orderWrtUnset")],
      )

  def generateAlteredFields(self):
    """
    Fields that have been altered.
    """
    for appLabel, modelName, fieldName in sorted(self.oldFieldKeys.intersection(self.newFieldKeys)):
      # Did the field change?
      oldModelName = self.renamedModels.get((appLabel, modelName), modelName)
      newModelState = self.toState.model[appLabel, modelName]
      oldFieldName = self.renamedFields.get((appLabel, modelName, fieldName), fieldName)
      oldField = self.oldApps.getModel(appLabel, oldModelName)._meta.getFieldByName(oldFieldName)[0]
      newField = self.newApps.getModel(appLabel, modelName)._meta.getFieldByName(fieldName)[0]
      # Implement any modal renames on relations; these are handled by RenameModel
      # so we need to exclude them from the comparison
      if hasattr(newField, "rel") and getattr(newField.rel, "to", None):
        renameKey = (
          newField.rel.to._meta.appLabel,
          newField.rel.to._meta.objectName.lower(),
        )
        if renameKey in self.renamedModels:
          newField.rel.to = oldField.rel.to
      oldFieldDec = self.deepDeconstruct(oldField)
      newFieldDec = self.deepDeconstruct(newField)
      if oldFieldDec != newFieldDec:
        self.addOperation(
          appLabel,
          operations.AlterField(
            modelName=modelName,
            name=fieldName,
            field=newModelState.getFieldByName(fieldName),
          )
        )

  def _generateAlteredFooTogether(self, operation):
    optionName = operation.optionName
    for appLabel, modelName in sorted(self.keptModelKeys):
      oldModelName = self.renamedModels.get((appLabel, modelName), modelName)
      oldModelState = self.fromState.model[appLabel, oldModelName]
      newModelState = self.toState.model[appLabel, modelName]
      # We run the old version through the field renames to account for those
      if oldModelState.options.get(optionName) is None:
        oldValue = None
      else:
        oldValue = set([
          tuple(
            self.renamedFields.get((appLabel, modelName, n), n)
            for n in unique
          )
          for unique in oldModelState.options[optionName]
        ])
      if oldValue != newModelState.options.get(optionName):
        self.addOperation(
          appLabel,
          operation(
            name=modelName,
            **{optionName: newModelState.options.get(optionName)}
          )
        )

  def generateAlteredUniqueTogether(self):
    self._generateAlteredFooTogether(operations.AlterUniqueTogether)

  def generateAlteredIndexTogether(self):
    self._generateAlteredFooTogether(operations.AlterIndexTogether)

  def generateAlteredOptions(self):
    """
    Works out if any non-schema-affecting options have changed and
    makes an operation to represent them in state changes (in case Python
    code in migrations needs them)
    """
    modelToCheck = self.keptModelKeys.union(self.keptProxyKeys).union(self.keptUnmanagedKeys)
    for appLabel, modelName in sorted(modelToCheck):
      oldModelName = self.renamedModels.get((appLabel, modelName), modelName)
      oldModelState = self.fromState.model[appLabel, oldModelName]
      newModelState = self.toState.model[appLabel, modelName]
      oldOptions = dict(
        option for option in oldModelState.options.items()
        if option[0] in AlterModelOptions.ALTER_OPTION_KEYS
      )
      newOptions = dict(
        option for option in newModelState.options.items()
        if option[0] in AlterModelOptions.ALTER_OPTION_KEYS
      )
      if oldOptions != newOptions:
        self.addOperation(
          appLabel,
          operations.AlterModelOptions(
            name=modelName,
            options=newOptions,
          )
        )

  def generateAlteredOrderWithRespectTo(self):
    for appLabel, modelName in sorted(self.keptModelKeys):
      oldModelName = self.renamedModels.get((appLabel, modelName), modelName)
      oldModelState = self.fromState.model[appLabel, oldModelName]
      newModelState = self.toState.model[appLabel, modelName]
      if oldModelState.options.get("orderWithRespectTo", None) != newModelState.options.get("orderWithRespectTo", None):
        # Make sure it comes second if we're adding
        # (removal dependency is part of RemoveField)
        dependencies = []
        if newModelState.options.get("orderWithRespectTo", None):
          dependencies.append((
            appLabel,
            modelName,
            newModelState.options["orderWithRespectTo"],
            True,
          ))
        # Actually generate the operation
        self.addOperation(
          appLabel,
          operations.AlterOrderWithRespectTo(
            name=modelName,
            orderWithRespectTo=newModelState.options.get('orderWithRespectTo', None),
          ),
          dependencies=dependencies,
        )

  def arrangeForGraph(self, changes, graph):
    """
    Takes in a result from changes() and a MigrationGraph,
    and fixes the names and dependencies of the changes so they
    extend the graph from the leaf nodes for each app.
    """
    leaves = graph.leafNodes()
    nameMap = {}
    for appLabel, migrations in list(changes.items()):
      if not migrations:
        continue
      # Find the app label's current leaf node
      appLeaf = None
      for leaf in leaves:
        if leaf[0] == appLabel:
          appLeaf = leaf
          break
      # Do they want an initial migration for this app?
      if appLeaf is None and not self.questioner.askInitial(appLabel):
        # They don't.
        for migration in migrations:
          nameMap[(appLabel, migration.name)] = (appLabel, "__first__")
        del changes[appLabel]
        continue
      # Work out the next number in the sequence
      if appLeaf is None:
        nextNumber = 1
      else:
        nextNumber = (self.parseNumber(appLeaf[1]) or 0) + 1
      # Name each migration
      for i, migration in enumerate(migrations):
        if i == 0 and appLeaf:
          migration.dependencies.append(appLeaf)
        if i == 0 and not appLeaf:
          newName = "0001Initial"
        else:
          newName = "%04i_%s" % (
            nextNumber,
            self.suggestName(migration.operations)[:100],
          )
        nameMap[(appLabel, migration.name)] = (appLabel, newName)
        nextNumber += 1
        migration.name = newName
    # Now fix dependencies
    for appLabel, migrations in changes.items():
      for migration in migrations:
        migration.dependencies = [nameMap.get(d, d) for d in migration.dependencies]
    return changes

  def _trimToApps(self, changes, appLabels):
    """
    Takes changes from arrangeForGraph and set of app labels and
    returns a modified set of changes which trims out as many migrations
    that are not in appLabels as possible.
    Note that some other migrations may still be present, as they may be
    required dependencies.
    """
    # Gather other app dependencies in a first pass
    appDependencies = {}
    for appLabel, migrations in changes.items():
      for migration in migrations:
        for depAppLabel, name in migration.dependencies:
          appDependencies.setdefault(appLabel, set()).add(depAppLabel)
    requiredApps = set(appLabels)
    # Keep resolving till there's no change
    oldRequiredApps = None
    while oldRequiredApps != requiredApps:
      oldRequiredApps = set(requiredApps)
      for appLabel in list(requiredApps):
        requiredApps.update(appDependencies.get(appLabel, set()))
    # Remove all migrations that aren't needed
    for appLabel in list(changes.keys()):
      if appLabel not in requiredApps:
        del changes[appLabel]
    return changes

  @classmethod
  def suggestName(cls, ops):
    """
    Given a set of operations, suggests a name for the migration
    they might represent. Names are not guaranteed to be unique,
    but we put some effort in to the fallback name to avoid VCS conflicts
    if we can.
    """
    if len(ops) == 1:
      if isinstance(ops[0], operations.CreateModel):
        return ops[0].name.lower()
      elif isinstance(ops[0], operations.DeleteModel):
        return "delete_%s" % ops[0].name.lower()
      elif isinstance(ops[0], operations.AddField):
        return "%s_%s" % (ops[0].modelName.lower(), ops[0].name.lower())
      elif isinstance(ops[0], operations.RemoveField):
        return "remove_%s_%s" % (ops[0].modelName.lower(), ops[0].name.lower())
    elif len(ops) > 1:
      if all(isinstance(o, operations.CreateModel) for o in ops):
        return "_".join(sorted(o.name.lower() for o in ops))
    return "auto_%s" % datetime.datetime.now().strftime("%Y%m%d_%H%M")

  @classmethod
  def parseNumber(cls, name):
    """
    Given a migration name, tries to extract a number from the
    beginning of it. If no number found, returns None.
    """
    if re.match(r"^\d+_", name):
      return int(name.split("_")[0])
    return None
