# -*- coding: utf-8 -*-
##### System wide lib #####

##### Theory lib #####
from theory.apps.command.modelTblFilterBase import ModelTblFilterBase
from theory.apps.model import Adapter, Command, AppModel

##### Theory third-party lib #####

##### Local app #####
from .baseCommandTestCase import BaseCommandTestCase

##### Theory app #####

##### Misc #####
from gui.test.integrationTest.etk.testDummyEnv import getDummyEnv
from testBase.model import (
    CombinatoryModelWithDefaultValue,
    DummyAppModelManager
    )

__all__ = ('ModelTblFilterBaseTestCase',)

class DummyModelTblFilter(ModelTblFilterBase):
  _gongs = ["DummysetAsSpreadsheet", ]
  def __init__(self, *args, **kwargs):
    super(DummyModelTblFilter, self).__init__(*args, **kwargs)
    self.hasApplyChange = False

  def _applyChangeOnQueryset(self):
    self.hasApplyChange = True

class ModelTblFilterBaseTestCase(BaseCommandTestCase):
  fixtures = ["theory", "combinatoryAppConfig"]

  def setUp(self):
    Adapter.objects.getOrCreate(
        name="DummysetAsSpreadsheet",
        defaults={
          "name":"DummysetAsSpreadsheet",
          "importPath": (
            "testBase."
            "adapter."
            "dummysetAsSpreadsheetAdapter."
            "DummysetAsSpreadsheetAdapter"
            ),
          "propertyLst": \
            Adapter.objects.get(name="QuerysetAsSpreadsheet").propertyLst
          }
        )

    # modelTblDel and modelTblFilterBase's paramForm is the same
    cmdModel = Command.objects.get(app="theory.apps", name="modelTblDel")
    self.cmd = DummyModelTblFilter()
    self.cmd.paramForm = DummyModelTblFilter.ParamForm()
    self.cmd.paramForm.fillInitFields(
        cmdModel,
        [],
        {
          "appName": "testBase",
          "modelName": "CombinatoryModelWithDefaultValue",
        },
    )

  def testRun(self):
    self.cmd.modelKlass = CombinatoryModelWithDefaultValue
    self.cmd.paramForm.isValid()
    self._validateParamForm(self.cmd)
    self._execeuteCommand(self.cmd, None, uiParam=self.uiParam)
    self.cmd.paramForm._nextBtnClick()

  def testRunWithWidget(self):
    manager = DummyAppModelManager()
    manager.getCombinatoryModelWithDefaultValue()
    self.cmd.modelKlass = CombinatoryModelWithDefaultValue
    self.cmd.paramForm.fields["queryset"].finalData = \
        manager.getQuerySet()
    self.cmd.paramForm.isValid()

    self._validateParamForm(self.cmd)
    self._execeuteCommand(self.cmd, None, uiParam=self.uiParam)
    self.cmd.paramForm._nextBtnClick()
    self.assertTrue(self.cmd.hasApplyChange)
