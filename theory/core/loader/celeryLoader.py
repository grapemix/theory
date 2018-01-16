# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from celery.loaders.base import BaseLoader

##### Theory lib #####
from theory.apps import apps
from theory.apps.model import Command
from theory.utils import timezone
from theory.utils.importlib import importModule
from theory.utils.mood import loadMoodData
loadMoodData()
from theory.conf import settings

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class CeleryLoader(BaseLoader):
  """Modified from celery default loader and django-celery DjangoLoader"""
  def now(self):
    return timezone.now()

  def read_configuration(self):
    """Read configuration from theory config file and configure
    celery and Theory so it can be used by regular Python."""
    self.configured = True
    return settings.CELERY_SETTINGS

  def import_default_modules(self):
    super(CeleryLoader, self).import_default_modules()
    self.autodiscover()

  def autodiscover(self):
    apps.populate(["theory.apps",])
    cmdImportPath = [
        cmd.moduleImportPath for cmd in \
            Command.objects.only('app', 'name').
            filter(runMode=Command.RUN_MODE_ASYNC)
            ]
    for path in cmdImportPath:
      module = importModule(path)
      klsName = path.split(".")[-1]
      klsName = klsName[0].upper() + klsName[1:]
      kls = getattr(module, klsName)
      self.app.tasks.register(kls)
      kls.bind(self.app)
