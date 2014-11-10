import os
import time
import threading
import warnings

from theory.conf import settings
from theory.db import connections
from theory.dispatch import receiver, Signal
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


@receiver(settingChanged)
def clearContextProcessorsCache(**kwargs):
  if kwargs['setting'] == 'TEMPLATE_CONTEXT_PROCESSORS':
    from theory.template import context
    context._standardContextProcessors = None


@receiver(settingChanged)
def clearTemplateLoadersCache(**kwargs):
  if kwargs['setting'] == 'TEMPLATE_LOADERS':
    from theory.template import loader
    loader.templateSourceLoaders = None


@receiver(settingChanged)
def clearSerializersCache(**kwargs):
  if kwargs['setting'] == 'SERIALIZATION_MODULES':
    from theory.core import serializers
    serializers._serializers = {}


@receiver(settingChanged)
def languageChanged(**kwargs):
  if kwargs['setting'] in {'LANGUAGES', 'LANGUAGE_CODE', 'LOCALE_PATHS'}:
    from theory.utils.translation import transReal
    transReal._default = None
    transReal._active = threading.local()
  if kwargs['setting'] in {'LANGUAGES', 'LOCALE_PATHS'}:
    from theory.utils.translation import transReal
    transReal._translations = {}
    transReal.checkForLanguage.cacheClear()


@receiver(settingChanged)
def fileStorageChanged(**kwargs):
  if kwargs['setting'] in ('MEDIA_ROOT', 'DEFAULT_FILE_STORAGE'):
    from theory.core.files.storage import defaultStorage
    defaultStorage._wrapped = empty


@receiver(settingChanged)
def complexSettingChanged(**kwargs):
  if kwargs['enter'] and kwargs['setting'] in COMPLEX_OVERRIDE_SETTINGS:
    # Considering the current implementation of the signals framework,
    # stacklevel=5 shows the line containing the overrideSettings call.
    warnings.warn("Overriding setting %s can lead to unexpected behavior."
           % kwargs['setting'], stacklevel=5)


@receiver(settingChanged)
def rootUrlconfChanged(**kwargs):
  if kwargs['setting'] == 'ROOT_URLCONF':
    from theory.core.urlresolvers import clearUrlCaches, setUrlconf
    clearUrlCaches()
    setUrlconf(None)
