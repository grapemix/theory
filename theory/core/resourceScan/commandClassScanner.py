# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
from mongoengine import *

##### Theory lib #####
from theory.conf import settings
from theory.model import Command, Parameter
from theory.utils.importlib import import_module

##### Theory third-party lib #####

##### Local app #####
from .baseClassScanner import BaseClassScanner

##### Theory app #####

##### Misc #####

class CommandClassScanner(BaseClassScanner):
  @property
  def cmdModel(self):
    return self._cmdModel

  @cmdModel.setter
  def cmdModel(self, cmdModel):
    self._cmdModel = cmdModel

  def _loadCommandClass(self):
    """
    Given a command name and an application name, returns the Command
    class instance. All errors raised by the import process
    (ImportError, AttributeError) are allowed to propagate.
    """
    module = self._loadSubModuleCommandClass(self.cmdModel.app, "command", self.cmdModel.name)
    return module

  def saveModel(self):
    if(self._cmdModel!=None):
      self._cmdModel.save()

  def scan(self):
    cmdFileClass = self._loadCommandClass()
    if(hasattr(cmdFileClass, "ABCMeta")):
      self._cmdModel = None
      return
    try:
      cmdClass = getattr(cmdFileClass, self.cmdModel.name[0].upper() + self.cmdModel.name[1:])
      # Should add debug flag checking and dump to log file instead
    except AttributeError:
      self._cmdModel = None
      return

    # To reserve the order of mandatory parameters
    for paramName in getattr(cmdClass, "params"):
      v = getattr(cmdClass, paramName)
      if(isinstance(v, property)):
        param = Parameter(name=paramName, isOptional = False)
        self.cmdModel.param.append(param)

    for k,v in cmdClass.__dict__.iteritems():
      if(isinstance(v, property)):
        param = Parameter(name=k)
        if(getattr(getattr(cmdClass, k), "fset")==None):
          param.isReadOnly = True
        if(k in getattr(cmdClass, "params")):
          #param.isOptional = False
          # To avoid duplicate
          continue
        self.cmdModel.param.append(param)
