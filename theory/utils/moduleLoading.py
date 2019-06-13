# -*- coding: utf-8 -*-
#!/usr/bin/env python
from __future__ import absolute_import  # Avoid importing `importlib` from this package.

import copy
from importlib import import_module
import os
import sys
import warnings

from theory.core.exceptions import ImproperlyConfigured
from theory.utils import six
from theory.utils.deprecation import RemovedInTheory19Warning


def importString(dottedPath):
  """
  Import a dotted module path and return the attribute/class designated by the
  last name in the path. Raise ImportError if the import failed.
  """
  try:
    modulePath, className = dottedPath.rsplit('.', 1)
  except ValueError:
    msg = "%s doesn't look like a module path" % dottedPath
    six.reraise(ImportError, ImportError(msg), sys.exc_info()[2])

  module = import_module(modulePath)

  try:
    return getattr(module, className)
  except AttributeError:
    msg = 'Module "%s" does not define a "%s" attribute/class' % (
      dottedPath, className)
    six.reraise(ImportError, ImportError(msg), sys.exc_info()[2])


def importByPath(dottedPath, errorPrefix=''):
  """
  Import a dotted module path and return the attribute/class designated by the
  last name in the path. Raise ImproperlyConfigured if something goes wrong.
  """
  warnings.warn(
    'importByPath() has been deprecated. Use importString() instead.',
    RemovedInTheory19Warning, stacklevel=2)
  try:
    attr = importString(dottedPath)
  except ImportError as e:
    msg = '%sError importing module %s: "%s"' % (
      errorPrefix, dottedPath, e)
    six.reraise(ImproperlyConfigured, ImproperlyConfigured(msg),
          sys.exc_info()[2])
  return attr


def autodiscoverModules(*args, **kwargs):
  """
  Auto-discover INSTALLED_APPS modules and fail silently when
  not present. This forces an import on them to register any admin bits they
  may want.

  You may provide a registerTo keyword parameter as a way to access a
  registry. This registerTo object must have a _registry instance variable
  to access it.
  """
  from theory.apps import apps

  registerTo = kwargs.get('registerTo')
  for appConfig in apps.getAppConfigs():
    # Attempt to import the app's module.
    try:
      if registerTo:
        beforeImportRegistry = copy.copy(registerTo._registry)

      for moduleToSearch in args:
        import_module('%s.%s' % (appConfig.name, moduleToSearch))
    except:
      # Reset the model registry to the state before the last import as
      # this import will have to reoccur on the next request and this
      # could raise NotRegistered and AlreadyRegistered exceptions
      # (see #8245).
      if registerTo:
        registerTo._registry = beforeImportRegistry

      # Decide whether to bubble up this error. If the app just
      # doesn't have an admin module, we can ignore the error
      # attempting to import it, otherwise we want it to bubble up.
      if moduleHasSubmodule(appConfig.module, moduleToSearch):
        raise


if sys.version_info[:2] >= (3, 3):
  if sys.version_info[:2] >= (3, 4):
    from importlib.util import find_spec as importlibFind
  else:
    from importlib import findLoader as importlibFind

  def moduleHasSubmodule(package, moduleName):
    """See if 'module' is in 'package'."""
    try:
      packageName = package.__name__
      packagePath = package.__path__
    except AttributeError:
      # package isn't a package.
      return False

    fullModuleName = packageName + '.' + moduleName
    return importlibFind(fullModuleName, packagePath) is not None

else:
  import imp

  def moduleHasSubmodule(package, moduleName):
    """See if 'module' is in 'package'."""
    name = ".".join([package.__name__, moduleName])
    try:
      # None indicates a cached miss; see markMiss() in Python/import.c.
      return sys.modules[name] is not None
    except KeyError:
      pass
    try:
      packagePath = package.__path__   # No __path__, then not a package.
    except AttributeError:
      # Since the remainder of this function assumes that we're dealing with
      # a package (module with a __path__), so if it's not, then bail here.
      return False
    for finder in sys.meta_path:
      if finder.find_module(name, packagePath):
        return True
    for entry in packagePath:
      try:
        # Try the cached finder.
        finder = sys.path_importer_cache[entry]
        if finder is None:
          # Implicit import machinery should be used.
          try:
            file_, _, _ = imp.find_module(moduleName, [entry])
            if file_:
              file_.close()
            return True
          except ImportError:
            continue
        # Else see if the finder knows of a loader.
        elif finder.find_module(name):
          return True
        else:
          continue
      except KeyError:
        # No cached finder, so try and make one.
        for hook in sys.path_hooks:
          try:
            finder = hook(entry)
            # XXX Could cache in sys.path_importer_cache
            if finder.find_module(name):
              return True
            else:
              # Once a finder is found, stop the search.
              break
          except ImportError:
            # Continue the search for a finder.
            continue
        else:
          # No finder found.
          # Try the implicit import machinery if searching a directory.
          if os.path.isdir(entry):
            try:
              file_, _, _ = imp.find_module(moduleName, [entry])
              if file_:
                file_.close()
              return True
            except ImportError:
              pass
          # XXX Could insert None or NullImporter
    else:
      # Exhausted the search, so the module cannot be found.
      return False
