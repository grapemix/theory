# -*- coding: utf-8 -*-
##### System wide lib #####
from mongoengine import *

##### Theory lib #####
from theory.conf import settings
from theory.core.commandScan.classScanner import ClassScanner
from theory.core.commandScan.sourceCodeScanner import SourceCodeScanner
from theory.model import Command

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class CommandScanManager(object):
  _cmdList = []

  @property
  def cmdList(self):
    return self._cmdList

  @cmdList.setter
  def cmdList(self, cmdList):
    self._cmdList = cmdList

  def scan(self):
    Command.objects.all().delete()
    for cmdParam in self.cmdList:
      cmd = Command(name=cmdParam[1], app=cmdParam[0], mood=cmdParam[3], sourceFile=cmdParam[2])
      o = ClassScanner()
      o.cmdModel = cmd
      o.scan()
      #o = SourceCodeScanner()
      o.cmdModel.save()
