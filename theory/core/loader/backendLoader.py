# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from gevent import monkey; monkey.patch_all()
import os
#from theory.conf import settings
#os.environ["BROKER_URL"] = settings.CELERY_SETTINGS["BROKER_URL"]
os.environ.setdefault("CELERY_LOADER", "theory.core.loader.celeryLoader.CeleryLoader")

# Order is important in here
from celery import current_app
from celery.bin import celeryd
##### Theory lib #####

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

def startCelery():
  worker = celeryd.WorkerCommand(app=current_app._get_current_object())
  args=[]
  kwargs={}
  kwargs["loglevel"] = "DEBUG"
  # TODO: support autoreload (it is in celery's code though)
  kwargs["autoreload"] = False
  worker.run(*args, **kwargs)

