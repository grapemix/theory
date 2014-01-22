# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict

##### Theory lib #####
from theory.model import Command

##### Theory third-party lib #####

##### Local app #####
from .baseCommandTestCase import BaseCommandTestCase

##### Theory app #####

##### Misc #####
from tests.integrationTest.gui.tests.etk.dummyEnv import getDummyEnv

__all__ = ('ModelUpsertTestCase',)

class ModelUpsertTestCase(BaseCommandTestCase):
  def __init__(self, *args, **kwargs):
    super(ModelUpsertTestCase, self).__init__(*args, **kwargs)
    self.cmdModel = Command.objects.get(name="modelUpsert")
    (dummyWin, dummyBx) = getDummyEnv()
    self.uiParam=OrderedDict([
        ("win", dummyWin),
        ("bx", dummyBx.obj),
        ("unFocusFxn", lambda: True),
        ("cleanUpCrtFxn", lambda: True),
        ])

  def testAdding(self):
    cmd = self._getCmd(
        self.cmdModel,
        kwargs={
          "appName": "theory",
          "modelName": "Command",
          }
        )
    self._validateParamForm(cmd)
    self._execeuteCommand(cmd, self.cmdModel, uiParam=self.uiParam)

  def testEditing(self):
    cmd = self._getCmd(
        self.cmdModel,
        kwargs={
          "appName": "theory",
          "modelName": "Command",
          "instanceId": str(Command.objects.all().first().id),
          }
        )
    self._validateParamForm(cmd)
    self._execeuteCommand(cmd, self.cmdModel, uiParam=self.uiParam)

if __name__ == '__main__':
  unittest.main()
