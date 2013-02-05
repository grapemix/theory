# -*- coding: utf-8 -*-
##### System wide lib #####
import unittest

##### Theory lib #####
from theory.command.baseCommand import AsyncContainer
from theory.core.bridge import Bridge

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('BaseCommandTestCase',)

class BaseCommandTestCase(unittest.TestCase):

  def _execeuteCommand(self, cmd, cmdModel):
    """Copied from theory.core.reactor"""
    # Since we only allow execute one command in a time thru terminal,
    # the command doesn't have to return anything
    adapterProperty = []
    if(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC_WRAPPER):
      asyncContainer = AsyncContainer()
      result = asyncContainer.delay(cmd, adapterProperty).get()
    elif(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC):
      #result = cmd.delay(storage).get()
      cmd.delay(paramForm=paramForm)
    else:
      asyncContainer = AsyncContainer()
      result = asyncContainer.run(cmd, adapterProperty)

  def _validateParamForm(self, cmd):
    self.cmd = cmd
    if(not self.cmd.paramForm.is_valid()):
      print self.cmd.paramForm.errors
    self.assertTrue(self.cmd.paramForm.is_valid())
    self.cmd.paramForm.clean()

  def _getCmd(self, cmdModel, args=[], kwargs={}):
    """Copied from theory.core.reactor, except for the default param"""
    bridge = Bridge()
    return bridge.getCmdComplex(cmdModel, args, kwargs)
