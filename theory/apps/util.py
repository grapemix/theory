

def sortDependencies(appList):
  """Sort a list of (appConfig, models) pairs into a single list of models.

  The single list of models is sorted so that any model with a natural key
  is serialized before a normal model, and any model with a natural key
  dependency has it's dependencies serialized first.
  """
  # Process the list of models, and get the list of dependencies
  modelDependencies = []
  models = set()
  for appConfig, modelList in appList:
    if modelList is None:
      modelList = appConfig.getModels()

    for model in modelList:
      models.add(model)
      # Add any explicitly defined dependencies
      if hasattr(model, 'naturalKey'):
        deps = getattr(model.naturalKey, 'dependencies', [])
        if deps:
          deps = [apps.getModel(dep) for dep in deps]
      else:
        deps = []

      # Now add a dependency for any FK relation with a model that
      # defines a natural key
      for field in model._meta.fields:
        if hasattr(field.rel, 'to'):
          relModel = field.rel.to
          if hasattr(relModel, 'naturalKey') and relModel != model:
            deps.append(relModel)
      # Also add a dependency for any simple M2M relation with a model
      # that defines a natural key.  M2M relations with explicit through
      # models don't count as dependencies.
      for field in model._meta.manyToMany:
        if field.rel.through._meta.autoCreated:
          relModel = field.rel.to
          if hasattr(relModel, 'naturalKey') and relModel != model:
            deps.append(relModel)
      modelDependencies.append((model, deps))

  modelDependencies.reverse()
  # Now sort the models to ensure that dependencies are met. This
  # is done by repeatedly iterating over the input list of models.
  # If all the dependencies of a given model are in the final list,
  # that model is promoted to the end of the final list. This process
  # continues until the input list is empty, or we do a full iteration
  # over the input models without promoting a model to the final list.
  # If we do a full iteration without a promotion, that means there are
  # circular dependencies in the list.
  modelList = []
  while modelDependencies:
    skipped = []
    changed = False
    while modelDependencies:
      model, deps = modelDependencies.pop()

      # If all of the models in the dependency list are either already
      # on the final model list, or not on the original serialization list,
      # then we've found another model with all it's dependencies satisfied.
      found = True
      for candidate in ((d not in models or d in modelList) for d in deps):
        if not candidate:
          found = False
      if found:
        modelList.append(model)
        changed = True
      else:
        skipped.append((model, deps))
    if not changed:
      raise CommandError("Can't resolve dependencies for %s in serialized app list." %
        ', '.join('%s.%s' % (model._meta.appLabel, model._meta.objectName)
        for model, deps in sorted(skipped, key=lambda obj: obj[0].__name__))
      )
    modelDependencies = skipped

  return modelList
