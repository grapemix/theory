# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### Patch #####
import concurrent.futures
import gevent

# Comment these two lines if you need to use fabric's ssl cert
from gevent import monkey
monkey.patch_all(thread=False)

from gevent.threadpool import ThreadPoolExecutor
concurrent.futures.ThreadPoolExecutor = ThreadPoolExecutor

#import os
#os.environ.setdefault("CELERY_LOADER", "theory.core.loader.celeryLoader.CeleryLoader")

##### System wide lib #####
from celery import Celery
from copy import deepcopy
from gevent.event import Event
import grpc
import time

##### Theory lib #####
from theory.apps import apps
from theory.conf import settings
from theory.core.loader.celeryLoader import CeleryLoader
from theory.core.reactor.reactor import Reactor
from theory.gui import theory_pb2_grpc
from theory.apps.model import Command
from theory.utils.mood import loadMoodData

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

def _startNotificationCamera(celeryApp):
  while(True):
    if AdapterBuffer.objects.filter(
        created__gt=datetime.now()-timedelta(minutes=1)
      ).count() > 0:
      celeryApp.asyncEvt.set()
    gevent.sleep(60)

def _startGrpcLoop(celeryApp):
  _ONE_DAY_IN_SECONDS = 60 * 60 * 24

  server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=10))
  theory_pb2_grpc.add_ReactorServicer_to_server(Reactor(), server)
  server.add_insecure_port('[::]:50051')
  server.start()
  try:
    while True:
      time.sleep(_ONE_DAY_IN_SECONDS)
  except KeyboardInterrupt:
    server.stop(0)

def wakeup(settings_mod, argv=None):
  appNameLst = deepcopy(settings.INSTALLED_APPS)
  appNameLst.insert(0, "theory.apps")
  apps.populate(appNameLst)
  try:
    Command.objects.count()
  except:
    # DB has been flushed
    from theory.core.bridge import Bridge
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

  loadMoodData()
  celeryApp = Celery(loader=CeleryLoader)
  celeryApp.config_from_object('theory.conf:settings', namespace='CELERY')
  celeryApp.loader.autodiscover()

  celeryApp.asyncEvt = Event()
  _startGrpcLoop(celeryApp)
