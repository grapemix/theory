# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict

##### Theory lib #####
from theory.core.bridge import Bridge
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####
from gui.test.integrationTest.etk.testDummyEnv import getDummyEnv

##### Theory app #####

##### Misc #####

__all__ = ('BaseCommandTestCase',)

class BaseCommandTestCase(TestCase):
  def __init__(self, *args, **kwargs):
    super(BaseCommandTestCase, self).__init__(*args, **kwargs)
    (dummyWin, dummyBx) = getDummyEnv()
    self.uiParam=OrderedDict([
        ("win", dummyWin),
        ("bx", dummyBx.obj),
        ("unFocusFxn", lambda: True),
        ("cleanUpCrtFxn", lambda: True),
        ])

  def _executeCommand(self, cmd, cmdModel, uiParam={}):
    """Copied from theory.core.reactor"""
    if (hasattr(cmdModel, "RUN_MODE_ASYNC") and
        cmdModel.runMode==cmdModel.RUN_MODE_ASYNC
        ):
      cmd.delay(paramFormData=cmd.paramForm.toJson())
    else:
      if(not cmd.paramForm.isValid()):
        return False
      cmd._uiParam = uiParam
      cmd.run()
    return True

  def _validateParamForm(self, cmd):
    self.cmd = cmd
    self.assertTrue(self.cmd.paramForm.isValid(), self.cmd.paramForm.errors)
    self.cmd.paramForm.clean()

  def _getCmd(self, cmdModel, args=[], kwargs={}):
    """Copied from theory.core.reactor, except for the default param"""
    bridge = Bridge()
    return bridge.getCmdComplex(cmdModel, args, kwargs)
