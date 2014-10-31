# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand, AsyncCommand
from theory.conf import settings
from theory.apps.model import Command, Parameter

##### Theory third-party lib #####

##### Local app #####
from .baseClassScanner import BaseClassScanner
from .paramScanner import ParamScanner

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
    if (hasattr(cmdFileClass, "ABCMeta")
        or hasattr(cmdFileClass, "abstract")
        ):
      self._cmdModel = None
      return
    try:
      cmdClass = getattr(cmdFileClass, self.cmdModel.name[0].upper() + self.cmdModel.name[1:])
      # Should add debug flag checking and dump to log file instead
    except AttributeError:
      self._cmdModel = None
      return

    if(issubclass(cmdClass, AsyncCommand)):
      self.cmdModel.runMode = self.cmdModel.RUN_MODE_ASYNC
    elif(not issubclass(cmdClass, SimpleCommand)):
      self.cmdModel.runMode = self.cmdModel.RUN_MODE_SIMPLE

    self.cmdModel.save()
    # Get the fields in the paramForm first. All fields in the paramForm
    # are able to pass to adapter. Only the order of the required fields
    # are important.
    for paramName, param in cmdClass.ParamForm.baseFields.iteritems():
      if(param.required):
        parameter = Parameter(name=paramName, isOptional=False)
      else:
        parameter = Parameter(name=paramName)
      self.cmdModel.parameterSet.add(parameter)

    # Class properties will be able to be captured and passed to adapter
    for k,v in cmdClass.__dict__.iteritems():
      if(isinstance(v, property)):
        param = Parameter(name=k)
        if(getattr(getattr(cmdClass, k), "fset") is None):
          param.isReadOnly = True
        self.cmdModel.parameterSet.add(param)

    paramScanner = ParamScanner()
    paramScanner.filePath = self.cmdModel.sourceFile
    paramScanner.paramModelLst = self.cmdModel.parameterSet.all()
    paramScanner.scan()
