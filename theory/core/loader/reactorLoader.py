# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### Patch #####
from theory.thevent import gevent
import concurrent.futures
import os
os.environ.setdefault("CELERY_LOADER", "theory.core.loader.celeryLoader.CeleryLoader")

##### System wide lib #####
from celery import Celery
from copy import deepcopy
import grpc
from grpc_health.v1 import health
from grpc_health.v1 import health_pb2_grpc
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
  servicer = Reactor()
  # Ref: https://grpc.github.io/grpc/python/grpc_health_checking.html
  # Ref: https://github.com/GoogleCloudPlatform/microservices-demo/blob/master/src/recommendationservice/recommendation_server.py  # noqa
  # The servicer will return service unhealthy (responded with "NOT_SERVING")
  #servicer.isReady = False
  theory_pb2_grpc.add_ReactorServicer_to_server(servicer, server)
  health_pb2_grpc.add_HealthServicer_to_server(servicer, server)
  server.add_insecure_port('[::]:50051')
  server.start()

  # TODO: move this block at the end and merged w/ wakeup() to better take
  # advantage of GRPC's health svc flow
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
    from theory.db import connection
    from theory.apps.command.migrate import Migrate
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('schema_name.apps_command')")
        # If rowcount == 1(Yip, not a typo), it means the table apps_command
        # does not exist and the db is completely fleshed. Therefore, calling
        # MakeMigration will yield error.
        if cursor.rowcount > 1:
          # DB has been flushed
          from theory.apps.command.makeMigration import MakeMigration
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
    print("reprobeAllModule is completed")

  loadMoodData()
  celeryApp = Celery(loader=CeleryLoader)
  celeryApp.config_from_object('theory.conf:settings', namespace='CELERY')
  celeryApp.loader.autodiscover()

  celeryApp.asyncEvt = gevent.event.Event()
  _startGrpcLoop(celeryApp)
