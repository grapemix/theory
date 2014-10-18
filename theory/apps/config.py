from importlib import import_module
import os

from theory.core.exceptions import AppRegistryNotReady, ImproperlyConfigured
from theory.utils.moduleLoading import moduleHasSubmodule
from theory.utils._os import upath


MODELS_MODULE_NAME = 'model'


class AppConfig(object):
  """
  Class representing a Theory application and its configuration.
  """

  def __init__(self, appName, appModule):
    # Full Python path to the application eg. 'theory.contrib.admin'.
    self.name = appName

    # Root module for the application eg. <module 'theory.contrib.admin'
    # from 'theory/contrib/admin/__init__.pyc'>.
    self.module = appModule

    # The following attributes could be defined at the class level in a
    # subclass, hence the test-and-set pattern.

    # Last component of the Python path to the application eg. 'admin'.
    # This value must be unique across a Theory project.
    if not hasattr(self, 'label'):
      self.label = appName.rpartition(".")[2]

    # Human-readable name for the application eg. "Admin".
    if not hasattr(self, 'verboseName'):
      self.verboseName = self.label.title()

    # Filesystem path to the application directory eg.
    # u'/usr/lib/python2.7/dist-packages/theory/contrib/admin'. Unicode on
    # Python 2 and a str on Python 3.
    if not hasattr(self, 'path'):
      self.path = self._pathFromModule(appModule)

    # Module containing model eg. <module 'theory.contrib.admin.model'
    # from 'theory/contrib/admin/model.pyc'>. Set by importModels().
    # None if the application doesn't have a model module.
    self.modelModule = None

    # Mapping of lower case model names to model classes. Initially set to
    # None to prevent accidental access before importModels() runs.
    self.model = None

  def __repr__(self):
    return '<%s: %s>' % (self.__class__.__name__, self.label)

  def _pathFromModule(self, module):
    """Attempt to determine app's filesystem path from its module."""
    # See #21874 for extended discussion of the behavior of this method in
    # various cases.
    # Convert paths to list because Python 3.3 _NamespacePath does not
    # support indexing.
    paths = list(getattr(module, '__path__', []))
    if len(paths) != 1:
      filename = getattr(module, '__file__', None)
      if filename is not None:
        paths = [os.path.dirname(filename)]
    if len(paths) > 1:
      raise ImproperlyConfigured(
        "The app module %r has multiple filesystem locations (%r); "
        "you must configure this app with an AppConfig subclass "
        "with a 'path' class attribute." % (module, paths))
    elif not paths:
      raise ImproperlyConfigured(
        "The app module %r has no filesystem location, "
        "you must configure this app with an AppConfig subclass "
        "with a 'path' class attribute." % (module,))
    return upath(paths[0])

  @classmethod
  def create(cls, entry):
    """
    Factory that creates an app config from an entry in INSTALLED_APPS.
    """
    try:
      # If import_module succeeds, entry is a path to an app module,
      # which may specify an app config class with defaultAppConfig.
      # Otherwise, entry is a path to an app config class or an error.
      module = import_module(entry)

    except ImportError:
      modPath, _, clsName = entry.rpartition('.')

      # Raise the original exception when entry cannot be a path to an
      # app config class.
      if not modPath:
        raise

    else:
      try:
        # If this works, the app module specifies an app config class.
        entry = module.defaultAppConfig
      except AttributeError:
        # Otherwise, it simply uses the default app config class.
        return cls(entry, module)
      else:
        modPath, _, clsName = entry.rpartition('.')

    # If we're reaching this point, we must load the app config class
    # located at <modPath>.<clsName>.

    # Avoid theory.utils.moduleLoading.importByPath because it
    # masks errors -- it reraises ImportError as ImproperlyConfigured.
    mod = import_module(modPath)
    try:
      cls = getattr(mod, clsName)
    except AttributeError:
      # Emulate the error that "from <modPath> import <clsName>"
      # would raise when <modPath> exists but not <clsName>, with
      # more context (Python just says "cannot import name ...").
      raise ImportError(
        "cannot import name '%s' from '%s'" % (clsName, modPath))

    # Check for obvious errors. (This check prevents duck typing, but
    # it could be removed if it became a problem in practice.)
    if not issubclass(cls, AppConfig):
      raise ImproperlyConfigured(
        "'%s' isn't a subclass of AppConfig." % entry)

    # Obtain app name here rather than in AppClass.__init__ to keep
    # all error checking for entries in INSTALLED_APPS in one place.
    try:
      appName = cls.name
    except AttributeError:
      raise ImproperlyConfigured(
        "'%s' must supply a name attribute." % entry)

    # Ensure appName points to a valid module.
    appModule = import_module(appName)

    # Entry is a path to an app config class.
    return cls(appName, appModule)

  def checkModelsReady(self):
    """
    Raises an exception if model haven't been imported yet.
    """
    if self.model is None:
      raise AppRegistryNotReady(
        "Models for app '%s' haven't been imported yet." % self.label)

  def getModel(self, modelName):
    """
    Returns the model with the given case-insensitive modelName.

    Raises LookupError if no model exists with this name.
    """
    self.checkModelsReady()
    try:
      return self.model[modelName.lower()]
    except KeyError:
      raise LookupError(
        "App '%s' doesn't have a '%s' model." % (self.label, modelName))

  def getModels(self, includeAutoCreated=False,
          includeDeferred=False, includeSwapped=False):
    """
    Returns an iterable of model.

    By default, the following model aren't included:

    - auto-created model for many-to-many relations without
     an explicit intermediate table,
    - model created to satisfy deferred attribute queries,
    - model that have been swapped out.

    Set the corresponding keyword argument to True to include such model.
    Keyword arguments aren't documented; they're a private API.
    """
    self.checkModelsReady()
    for model in self.model.values():
      if model._deferred and not includeDeferred:
        continue
      if model._meta.autoCreated and not includeAutoCreated:
        continue
      if model._meta.swapped and not includeSwapped:
        continue
      yield model

  def importModels(self, allModels):
    # Dictionary of model for this app, primarily maintained in the
    # 'allModels' attribute of the Apps this AppConfig is attached to.
    # Injected as a parameter because it gets populated when model are
    # imported, which might happen before populate() imports model.
    self.model = allModels

    if moduleHasSubmodule(self.module, MODELS_MODULE_NAME):
      modelModuleName = '%s.%s' % (self.name, MODELS_MODULE_NAME)
      self.modelModule = import_module(modelModuleName)

  def ready(self):
    """
    Override this method in subclasses to run code when Theory starts.
    """
