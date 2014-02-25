# -*- coding: utf-8 -*-
##### System wide lib #####
import unittest

##### Theory lib #####
from theory.core.bridge import Bridge

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('BaseCommandTestCase',)

class BaseCommandTestCase(unittest.TestCase):

  def _execeuteCommand(self, cmd, cmdModel, uiParam={}):
    """Copied from theory.core.reactor"""
    if(cmdModel.runMode==cmdModel.RUN_MODE_ASYNC):
      cmd.delay(paramFormData=cmd.paramForm.toJson())
    else:
      if(not cmd.paramForm.is_valid()):
        return False
      cmd._uiParam = uiParam
      cmd.run()
    return True

  def _validateParamForm(self, cmd):
    self.cmd = cmd
    if(not self.cmd.paramForm.is_valid()):
      print self.cmd.paramForm.errors
    self.assertTrue(self.cmd.paramForm.is_valid(), self.cmd.paramForm.errors)
    self.cmd.paramForm.clean()

  def _getCmd(self, cmdModel, args=[], kwargs={}):
    """Copied from theory.core.reactor, except for the default param"""
    bridge = Bridge()
    return bridge.getCmdComplex(cmdModel, args, kwargs)
