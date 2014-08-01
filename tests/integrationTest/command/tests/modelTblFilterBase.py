# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict

##### Theory lib #####
from theory.command.modelTblFilterBase import ModelTblFilterBase
from theory.model import Adapter, Command

##### Theory third-party lib #####

##### Local app #####
from .baseCommandTestCase import BaseCommandTestCase

##### Theory app #####

##### Misc #####
from tests.integrationTest.gui.tests.etk.dummyEnv import getDummyEnv

__all__ = ('ModelTblFilterBaseTestCase',)

class DummyModelTblFilter(ModelTblFilterBase):
  _gongs = ["DummysetAsSpreadsheet", ]
  def __init__(self, *args, **kwargs):
    super(DummyModelTblFilter, self).__init__(*args, **kwargs)
    self.hasApplyChange = False

  def _applyChangeOnQueryset(self):
    self.hasApplyChange = True

class ModelTblFilterBaseTestCase(BaseCommandTestCase):

  def __init__(self, *args, **kwargs):
    super(ModelTblFilterBaseTestCase, self).__init__(*args, **kwargs)
    (dummyWin, dummyBx) = getDummyEnv()
    self.uiParam=OrderedDict([
        ("win", dummyWin),
        ("bx", dummyBx.obj),
        ("unFocusFxn", lambda: True),
        ("cleanUpCrtFxn", lambda: True),
        ])
    try:
      Adapter(
          name="DummysetAsSpreadsheet",
          importPath=(
            "testBase."
            "adapter."
            "dummysetAsSpreadsheetAdapter."
            "DummysetAsSpreadsheetAdapter"
            ),
          property=Adapter.objects.get(name="QuerysetAsSpreadsheet").property,
          ).save()
    except:
      pass

  def setUp(self):
    self.cmd = DummyModelTblFilter()
    self.cmd.paramForm = DummyModelTblFilter.ParamForm()
    self.cmd.paramForm.fields["appName"].initData = "theory"
    self.cmd.paramForm.fields["modelName"].initData = "Command"
    self.cmd.paramForm.isValid()

  def testRun(self):
    self._validateParamForm(self.cmd)
    self._execeuteCommand(self.cmd, None, uiParam=self.uiParam)
    self.cmd.paramForm._nextBtnClick()

  def testRunWithWidget(self):
    self.cmd.paramForm.fields["queryset"].finalData = Command.objects.all()
    self._validateParamForm(self.cmd)
    self._execeuteCommand(self.cmd, None, uiParam=self.uiParam)
    self.cmd.paramForm._nextBtnClick()
    self.assertTrue(self.cmd.hasApplyChange)
