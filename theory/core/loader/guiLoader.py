# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from datetime import datetime, timedelta
import gevent
import os
os.environ.setdefault("CELERY_LOADER", "theory.core.loader.celeryLoader.CeleryLoader")
import signal

##### Theory lib #####
from theory.conf import settings
from theory.core.reactor import *
from theory.model import AdapterBuffer, Command

##### Theory third-party lib #####
from theory.gui.gtk.notify import getNotify

##### Local app #####

##### Theory app #####

##### Misc #####

def _chkAdapterBuffer():
  while(True):
    adapterBufferModelLst = AdapterBuffer.objects(
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
  if(settings.DEBUG or Command.objects.count()==0):
    from .util import reprobeAllModule
    reprobeAllModule(settings_mod, argv)
  else:
    from theory.utils.importlib import importModule
    for cmd in Command.objects.all():
      importModule(cmd.moduleImportPath)

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
