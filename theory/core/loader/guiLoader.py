# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from copy import deepcopy
from datetime import datetime, timedelta
import gevent
import os
os.environ.setdefault("CELERY_LOADER", "theory.core.loader.celeryLoader.CeleryLoader")
import signal

##### Theory lib #####
from theory.apps import apps
from theory.conf import settings
from theory.apps.model import AdapterBuffer, Command
from theory.utils.importlib import importModule
from theory.utils.mood import loadMoodData

##### Theory third-party lib #####
from theory.gui.gtk.notify import getNotify

##### Local app #####

##### Theory app #####

##### Misc #####

def _chkAdapterBuffer():
  while(True):
    adapterBufferModelLst = AdapterBuffer.objects.filter(
        created__gt=datetime.now()-timedelta(minutes=1)
        )
    for m in adapterBufferModelLst:
      getNotify("Done", str(m))
    gevent.sleep(60)
  return False

def getDimensionHints():
  resolutionSet = settings.MOOD["RESOLUTION"]
  maxHeight = maxWidth = 0
  minHeight = minWidth = 99999999

  for resolution in resolutionSet:
    width, height = resolution
    width = int(width)
    height = int(height)
    if minWidth > width:
      minWidth = width
    if minHeight > height:
      minHeight = height
    if maxWidth < width:
      maxWidth = width
    if maxHeight < height:
      maxHeight = height
  settings.dimensionHints = {
      "minWidth": minWidth,
      "minHeight":minHeight,
      "maxWidth": maxWidth,
      "maxHeight": maxHeight,
      }

def wakeup(settings_mod, argv=None):
  appNameLst = deepcopy(settings.INSTALLED_APPS)
  appNameLst.insert(0, "theory.apps")
  apps.populate(appNameLst)
  try:
    Command.objects.count()
  except:
    # DB has been flushed
    from core.bridge import Bridge
    from theory.apps.command.makeMigration import MakeMigration
    from theory.apps.command.migrate import Migrate
    cmd = MakeMigration()
    cmd.paramForm = MakeMigration.ParamForm()
    cmd.paramForm.fields["appLabelLst"].finalData = ["apps", ]
    cmd.paramForm.isValid()
    cmd.run()

    cmd = Migrate()
    cmd.paramForm = Migrate.ParamForm()
    cmd.paramForm.fields["appLabel"].finalData = "apps"
    cmd.paramForm.fields["isFake"].finalData = False
    cmd.paramForm.fields["isInitialData"].finalData = False
    cmd.paramForm.isValid()
    cmd.run()

  if Command.objects.count()==0:
    from .util import reprobeAllModule
    reprobeAllModule(settings_mod, argv)
  else:
    for cmd in Command.objects.all():
      importModule(cmd.moduleImportPath)

  loadMoodData()

  from theory.core.reactor import *
  getDimensionHints()
  # in 0.13.8, it is shutdown
  #gevent.signal(signal.SIGQUIT, gevent.shutdown)
  # in 1.0.1
  gevent.signal(signal.SIGQUIT, gevent.kill)
  gevent.joinall(
      [
        gevent.spawn(reactor.ui.drawAll),
        gevent.spawn(_chkAdapterBuffer),
      ]
  )
