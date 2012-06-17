# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import os
os.environ.setdefault("CELERY_LOADER", "theory.core.loader.celeryLoader.CeleryLoader")

##### Theory lib #####
from theory.core.reactor import *
from theory.model import Command

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

def wakeup(settings_mod, argv=None):
  if(Command.objects.count()==0):
    from .util import reprobeAllModule
    reprobeAllModule(settings_mod, argv)
  else:
    from theory.utils.importlib import import_module
    for cmd in Command.objects.all():
      import_module(cmd.moduleImportPath)
  #from theory.core import t
  #reactor = Reactor()
  #reactor.test()
  reactor.ui.drawAll()


