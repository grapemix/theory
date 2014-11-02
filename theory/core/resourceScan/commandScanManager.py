# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.conf import settings
from theory.core.resourceScan.commandClassScanner import CommandClassScanner
from theory.db import transaction
from theory.apps.model import Command, Mood

##### Theory third-party lib #####

##### Local app #####
from .baseScanManager import BaseScanManager

##### Theory app #####

##### Misc #####

class CommandScanManager(BaseScanManager):

  def drop(self, app=None):
    if app is None:
      Command.objects.all().delete()
    else:
      Command.objects.filter(
          app=app
          ).delete()



  def scan(self):
    for cmdParam in self.paramList:
      # TODO: supporting multiple mood
      if(cmdParam[2].endswith("__init__.py")):
        continue
      with transaction.atomic():
        cmd = Command(
            name=cmdParam[1],
            app=cmdParam[0],
            sourceFile=cmdParam[2]
            )
        o = CommandClassScanner()
        o.cmdModel = cmd
        o.scan()
        if o.cmdModel is None:
          # abstract cmd will rm o.cmdModel
          continue
        for moodName in cmdParam[3]:
          moodModel, created = Mood.objects.getOrCreate(name=moodName)
          cmd.moodSet.add(moodModel)
        #o = SourceCodeScanner()
        o.saveModel()
