import os
import time
import threading
import warnings

from theory.conf import settings
from theory.db import connections
from theory.dispatch import Signal
from theory.utils import timezone
from theory.utils.functional import empty

templateRendered = Signal(providingArgs=["template", "context"])

settingChanged = Signal(providingArgs=["setting", "value", "enter"])

# Most settingChanged receivers are supposed to be added below,
# except for cases where the receiver is related to a contrib app.

# Settings that may not work well when using 'overrideSettings' (#19031)
COMPLEX_OVERRIDE_SETTINGS = set(['DATABASES'])


@receiver(settingChanged)
def clearCacheHandlers(**kwargs):
  if kwargs['setting'] == 'CACHES':
    from theory.core.cache import caches
    caches._caches = threading.local()


@receiver(settingChanged)
def updateInstalledApps(**kwargs):
  if kwargs['setting'] == 'INSTALLED_APPS':
    # Rebuild any AppDirectoriesFinder instance.
    from theory.contrib.staticfiles.finders import getFinder
    getFinder.cacheClear()
    # Rebuild management commands cache
    from theory.core.management import getCommands
    getCommands.cacheClear()
    # Rebuild templatetags module cache.
    from theory.template import base as mod
    mod.templatetagsModules = []
    # Rebuild appTemplateDirs cache.
    from theory.template.loaders import appDirectories as mod
    mod.appTemplateDirs = mod.calculateAppTemplateDirs()
    # Rebuild translations cache.
    from theory.utils.translation import transReal
    transReal._translations = {}


@receiver(settingChanged)
def updateConnectionsTimeZone(**kwargs):
  if kwargs['setting'] == 'TIME_ZONE':
    # Reset process time zone
    if hasattr(time, 'tzset'):
      if kwargs['value']:
        os.environ['TZ'] = kwargs['value']
      else:
        os.environ.pop('TZ', None)
      time.tzset()

    # Reset local time zone cache
    timezone._localtime = None

  # Reset the database connections' time zone
  if kwargs['setting'] == 'USE_TZ' and settings.TIME_ZONE != 'UTC':
    USE_TZ, TIME_ZONE = kwargs['value'], settings.TIME_ZONE
  elif kwargs['setting'] == 'TIME_ZONE' and not settings.USE_TZ:
    USE_TZ, TIME_ZONE = settings.USE_TZ, kwargs['value']
  else:
    # no need to change the database connnections' time zones
    return
  tz = 'UTC' if USE_TZ else TIME_ZONE
  for conn in connections.all():
    conn.settingsDict['TIME_ZONE'] = tz
    tzSql = conn.ops.setTimeZoneSql()
    if tzSql:
      conn.cursor().execute(tzSql, [tz])

