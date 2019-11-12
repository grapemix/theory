from collections import Counter, defaultdict, OrderedDict
import os
import sys
from theory.thevent import gevent
import warnings

from theory.core.exceptions import AppRegistryNotReady, ImproperlyConfigured
from theory.utils import lruCache
from theory.utils.deprecation import RemovedInTheory19Warning
from theory.utils._os import upath

from .config import AppConfig


class Apps(object):
  """
  A registry that stores the configuration of installed applications.

  It also keeps track of models eg. to provide reverse-relations.
  """

  def __init__(self, installedApps=()):
    # installedApps is set to None when creating the master registry
    # because it cannot be populated at that point. Other registries must
    # provide a list of installed apps and are populated immediately.
    if installedApps is None and hasattr(sys.modules[__name__], 'apps'):
      raise RuntimeError("You must supply an installedApps argument.")

    # Mapping of app labels => model names => model classes. Every time a
    # model is imported, ModelBase.__new__ calls apps.registerModel which
    # creates an entry in allModels. All imported models are registered,
    # regardless of whether they're defined in an installed application
    # and whether the registry has been populated. Since it isn't possible
    # to reimport a module safely (it could reexecute initialization code)
    # allModels is never overridden or reset.
    self.allModels = defaultdict(OrderedDict)

    # Mapping of labels to AppConfig instances for installed apps.
    self.appConfigs = OrderedDict()

    # Stack of appConfigs. Used to store the current state in
    # setAvailableApps and setInstalledApps.
    self.storedAppConfigs = []

    # Whether the registry is populated.
    self.appsReady = self.modelsReady = self.ready = False

    # Lock for thread-safe population.
    self._lock = gevent.threading.Lock()

    # Pending lookups for lazy relations.
    self._pendingLookups = {}

    # Populate apps and models, unless it's the master registry.
    if installedApps is not None:
      self.populate(installedApps)

  def populate(self, installedApps=None):
    """
    Loads application configurations and models.

    This method imports each application module and then each model module.

    It is thread safe and idempotent, but not reentrant.
    """
    if self.ready:
      return

    # populate() might be called by two threads in parallel on servers
    # that create threads before initializing the WSGI callable.
    with self._lock:
      if self.ready:
        return

      # appConfig should be pristine, otherwise the code below won't
      # guarantee that the order matches the order in INSTALLED_APPS.
      if self.appConfigs:
        raise RuntimeError("populate() isn't reentrant")

      # Load app configs and app modules.
      for entry in installedApps:
        if isinstance(entry, AppConfig):
          appConfig = entry
        else:
          appConfig = AppConfig.create(entry)
        if appConfig.label in self.appConfigs:
          raise ImproperlyConfigured(
            "Application labels aren't unique, "
            "duplicates: %s" % appConfig.label)

        self.appConfigs[appConfig.label] = appConfig

      # Check for duplicate app names.
      counts = Counter(
        appConfig.name for appConfig in self.appConfigs.values())
      duplicates = [
        name for name, count in counts.most_common() if count > 1]
      if duplicates:
        raise ImproperlyConfigured(
          "Application names aren't unique, "
          "duplicates: %s" % ", ".join(duplicates))

      self.appsReady = True

      # Load models.
      for appConfig in self.appConfigs.values():
        allModels = self.allModels[appConfig.label]
        appConfig.importModels(allModels)

      self.clearCache()

      self.modelsReady = True

      for appConfig in self.getAppConfigs():
        appConfig.ready()

      self.ready = True

  def checkAppsReady(self):
    """
    Raises an exception if all apps haven't been imported yet.
    """
    if not self.appsReady:
      raise AppRegistryNotReady("Apps aren't loaded yet.")

  def checkModelsReady(self):
    """
    Raises an exception if all models haven't been imported yet.
    """
    if not self.modelsReady:
      raise AppRegistryNotReady("Models aren't loaded yet.")

  def getAppConfigs(self):
    """
    Imports applications and returns an iterable of app configs.
    """
    self.checkAppsReady()
    return self.appConfigs.values()

  def getAppConfig(self, appLabel):
    """
    Imports applications and returns an app config for the given label.

    Raises LookupError if no application exists with this label.
    """
    self.checkAppsReady()
    try:
      return self.appConfigs[appLabel]
    except KeyError:
      raise LookupError("No installed app with label '%s'." % appLabel)

  # This method is performance-critical at least for Theory's test suite.
  @lruCache.lruCache(maxsize=None)
  def getModels(self, appMod=None, includeAutoCreated=False,
          includeDeferred=False, includeSwapped=False):
    """
    Returns a list of all installed models.

    By default, the following models aren't included:

    - auto-created models for many-to-many relations without
     an explicit intermediate table,
    - models created to satisfy deferred attribute queries,
    - models that have been swapped out.

    Set the corresponding keyword argument to True to include such models.
    """
    self.checkModelsReady()
    if appMod:
      warnings.warn(
        "The appMod argument of getModels is deprecated.",
        RemovedInTheory19Warning, stacklevel=2)
      appLabel = appMod.__name__.split('.')[-2]
      try:
        return list(self.getAppConfig(appLabel).getModels(
          includeAutoCreated, includeDeferred, includeSwapped))
      except LookupError:
        return []

    result = []
    for appConfig in self.appConfigs.values():
      result.extend(list(appConfig.getModels(
        includeAutoCreated, includeDeferred, includeSwapped)))
    return result

  def getModel(self, appLabel, modelName=None):
    """
    Returns the model matching the given appLabel and modelName.

    As a shortcut, this function also accepts a single argument in the
    form <appLabel>.<modelName>.

    modelName is case-insensitive.

    Raises LookupError if no application exists with this label, or no
    model exists with this name in the application. Raises ValueError if
    called with a single argument that doesn't contain exactly one dot.
    """
    self.checkModelsReady()
    if modelName is None:
      appLabel, modelName = appLabel.split('.')
    return self.getAppConfig(appLabel).getModel(modelName.lower())

  def registerModel(self, appLabel, model):
    # Since this method is called when models are imported, it cannot
    # perform imports because of the risk of import loops. It mustn't
    # call getAppConfig().
    modelName = model._meta.modelName
    appModels = self.allModels[appLabel]
    if modelName in appModels:
      raise RuntimeError(
        "Conflicting '%s' models in application '%s': %s and %s." %
        (modelName, appLabel, appModels[modelName], model))
    appModels[modelName] = model
    self.clearCache()

  def isInstalled(self, appName):
    """
    Checks whether an application with this name exists in the registry.

    appName is the full name of the app eg. 'theory.contrib.admin'.
    """
    self.checkAppsReady()
    return any(ac.name == appName for ac in self.appConfigs.values())

  def getContainingAppConfig(self, objectName):
    """
    Look for an app config containing a given object.

    objectName is the dotted Python path to the object.

    Returns the app config for the inner application in case of nesting.
    Returns None if the object isn't in any registered app config.
    """
    # In Theory 1.7 and 1.8, it's allowed to call this method at import
    # time, even while the registry is being populated. In Theory 1.9 and
    # later, that should be forbidden with `self.checkAppsReady()`.
    candidates = []
    for appConfig in self.appConfigs.values():
      if objectName.startswith(appConfig.name):
        subpath = objectName[len(appConfig.name):]
        if subpath == '' or subpath[0] == '.':
          candidates.append(appConfig)
    if candidates:
      return sorted(candidates, key=lambda ac: -len(ac.name))[0]

  def getRegisteredModel(self, appLabel, modelName):
    """
    Similar to getModel(), but doesn't require that an app exists with
    the given appLabel.

    It's safe to call this method at import time, even while the registry
    is being populated.
    """
    model = self.allModels[appLabel].get(modelName.lower())
    if model is None:
      raise LookupError(
        "Model '%s.%s' not registered." % (appLabel, modelName))
    return model

  def setAvailableApps(self, available):
    """
    Restricts the set of installed apps used by getAppConfig[s].

    available must be an iterable of application names.

    setAvailableApps() must be balanced with unsetAvailableApps().

    Primarily used for performance optimization in TransactionTestCase.

    This method is safe is the sense that it doesn't trigger any imports.
    """
    available = set(available)
    installed = set(appConfig.name for appConfig in self.getAppConfigs())
    if not available.issubset(installed):
      raise ValueError("Available apps isn't a subset of installed "
        "apps, extra apps: %s" % ", ".join(available - installed))

    self.storedAppConfigs.append(self.appConfigs)
    self.appConfigs = OrderedDict(
      (label, appConfig)
      for label, appConfig in self.appConfigs.items()
      if appConfig.name in available)
    self.clearCache()

  def unsetAvailableApps(self):
    """
    Cancels a previous call to setAvailableApps().
    """
    self.appConfigs = self.storedAppConfigs.pop()
    self.clearCache()

  def setInstalledApps(self, installed):
    """
    Enables a different set of installed apps for getAppConfig[s].

    installed must be an iterable in the same format as INSTALLED_APPS.

    setInstalledApps() must be balanced with unsetInstalledApps(),
    even if it exits with an exception.

    Primarily used as a receiver of the settingChanged signal in tests.

    This method may trigger new imports, which may add new models to the
    registry of all imported models. They will stay in the registry even
    after unsetInstalledApps(). Since it isn't possible to replay
    imports safely (eg. that could lead to registering listeners twice),
    models are registered when they're imported and never removed.
    """
    if not self.ready:
      raise AppRegistryNotReady("App registry isn't ready yet.")
    self.storedAppConfigs.append(self.appConfigs)
    self.appConfigs = OrderedDict()
    self.appsReady = self.modelsReady = self.ready = False
    self.clearCache()
    self.populate(installed)

  def unsetInstalledApps(self):
    """
    Cancels a previous call to setInstalledApps().
    """
    self.appConfigs = self.storedAppConfigs.pop()
    self.appsReady = self.modelsReady = self.ready = True
    self.clearCache()

  def clearCache(self):
    """
    Clears all internal caches, for methods that alter the app registry.

    This is mostly used in tests.
    """
    self.getModels.cacheClear()

  ### DEPRECATED METHODS GO BELOW THIS LINE ###

  def loadApp(self, appName):
    """
    Loads the app with the provided fully qualified name, and returns the
    model module.
    """
    warnings.warn(
      "loadApp(appName) is deprecated.",
      RemovedInTheory19Warning, stacklevel=2)
    appConfig = AppConfig.create(appName)
    appConfig.importModels(self.allModels[appConfig.label])
    self.appConfigs[appConfig.label] = appConfig
    self.clearCache()
    return appConfig.modelModule

  def appCacheReady(self):
    warnings.warn(
      "appCacheReady() is deprecated in favor of the ready property.",
      RemovedInTheory19Warning, stacklevel=2)
    return self.ready

  def getApp(self, appLabel):
    """
    Returns the module containing the models for the given appLabel.
    """
    warnings.warn(
      "getAppConfig(appLabel).modelModule supersedes getApp(appLabel).",
      RemovedInTheory19Warning, stacklevel=2)
    try:
      modelModule = self.getAppConfig(appLabel).modelModule
    except LookupError as exc:
      # Change the exception type for backwards compatibility.
      raise ImproperlyConfigured(*exc.args)
    if modelModule is None:
      raise ImproperlyConfigured(
        "App '%s' doesn't have a models module." % appLabel)
    return modelModule

  def getApps(self):
    """
    Returns a list of all installed modules that contain models.
    """
    warnings.warn(
      "[a.modelModule for a in getAppConfigs()] supersedes getApps().",
      RemovedInTheory19Warning, stacklevel=2)
    appConfigs = self.getAppConfigs()
    return [appConfig.modelModule for appConfig in appConfigs
        if appConfig.modelModule is not None]

  def _getAppPackage(self, app):
    return '.'.join(app.__name__.split('.')[:-1])

  def getAppPackage(self, appLabel):
    warnings.warn(
      "getAppConfig(label).name supersedes getAppPackage(label).",
      RemovedInTheory19Warning, stacklevel=2)
    return self._getAppPackage(self.getApp(appLabel))

  def _getAppPath(self, app):
    if hasattr(app, '__path__'):        # models/__init__.py package
      appPath = app.__path__[0]
    else:                               # models.py module
      appPath = app.__file__
    return os.path.dirname(upath(appPath))

  def getAppPath(self, appLabel):
    warnings.warn(
      "getAppConfig(label).path supersedes getAppPath(label).",
      RemovedInTheory19Warning, stacklevel=2)
    return self._getAppPath(self.getApp(appLabel))

  def getAppPaths(self):
    """
    Returns a list of paths to all installed apps.

    Useful for discovering files at conventional locations inside apps
    (static files, templates, etc.)
    """
    warnings.warn(
      "[a.path for a in getAppConfigs()] supersedes getAppPaths().",
      RemovedInTheory19Warning, stacklevel=2)
    self.checkAppsReady()
    appPaths = []
    for app in self.getApps():
      appPaths.append(self._getAppPath(app))
    return appPaths

  def registerModels(self, appLabel, *models):
    """
    Register a set of models as belonging to an app.
    """
    warnings.warn(
      "registerModels(appLabel, *models) is deprecated.",
      RemovedInTheory19Warning, stacklevel=2)
    for model in models:
      self.registerModel(appLabel, model)


apps = Apps(installedApps=None)
