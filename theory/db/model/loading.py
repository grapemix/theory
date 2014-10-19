import warnings

from theory.apps import apps
from theory.utils.deprecation import RemovedInTheory19Warning


warnings.warn(
  "The utilities in theory.db.model.loading are deprecated "
  "in favor of the new application loading system.",
  RemovedInTheory19Warning, stacklevel=2)

__all__ = ('getApps', 'getApp', 'getModels', 'getModel', 'registerModels',
    'loadApp', 'appCacheReady')

# Backwards-compatibility for private APIs during the deprecation period.
UnavailableApp = LookupError
cache = apps

# These methods were always module level, so are kept that way for backwards
# compatibility.
getApps = apps.getApps
getAppPackage = apps.getAppPackage
getAppPath = apps.getAppPath
getAppPaths = apps.getAppPaths
getApp = apps.getApp
getModels = apps.getModels
getModel = apps.getModel
registerModels = apps.registerModels
loadApp = apps.loadApp
appCacheReady = apps.appCacheReady


# This method doesn't return anything interesting in Theory 1.6. Maintain it
# just for backwards compatibility until this module is deprecated.
def getAppErrors():
  try:
    return apps.appErrors
  except AttributeError:
    apps.appErrors = {}
    return apps.appErrors
