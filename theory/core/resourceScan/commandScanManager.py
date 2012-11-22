# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from mongoengine import *

##### Theory lib #####
from theory.conf import settings
from theory.core.resourceScan.commandClassScanner import CommandClassScanner
from theory.model import Command

##### Theory third-party lib #####

##### Local app #####
from .baseScanManager import BaseScanManager

##### Theory app #####

##### Misc #####

class CommandScanManager(BaseScanManager):

  def scan(self):
    Command.objects.all().delete()
    for cmdParam in self.paramList:
      # TODO: supporting multiple mood
      if(cmdParam[2].endswith("__init__.py")):
        continue
      cmd = Command(name=cmdParam[1], app=cmdParam[0], mood=cmdParam[3], sourceFile=cmdParam[2])
      o = CommandClassScanner()
      o.cmdModel = cmd
      o.scan()
      #o = SourceCodeScanner()
      o.saveModel()
