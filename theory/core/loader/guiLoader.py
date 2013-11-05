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
      getNotify(m)
    gevent.sleep(60)
  return False

def wakeup(settings_mod, argv=None):
  if(settings.DEBUG or Command.objects.count()==0):
    from .util import reprobeAllModule
    reprobeAllModule(settings_mod, argv)
  else:
    from theory.utils.importlib import import_module
    for cmd in Command.objects.all():
      import_module(cmd.moduleImportPath)

  gevent.signal(signal.SIGQUIT, gevent.shutdown)
  gevent.joinall(
      [
        gevent.spawn(reactor.ui.drawAll),
        gevent.spawn(_chkAdapterBuffer),
      ]
  )
