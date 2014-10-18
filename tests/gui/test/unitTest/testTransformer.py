# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub

##### Theory lib #####
from theory.apps.model import AppModel
from theory.gui.form import *
from theory.gui.model import fieldsForModel
from theory.gui.transformer.theoryModelFormDetector import \
    TheoryModelFormDetector
from theory.gui.transformer.theoryModelTblDataHandler import \
    TheoryModelTblDataHandler
from theory.gui.transformer.theoryJSONEncoder import TheoryJSONEncoder
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = (
    'TheoryModelFormDetectorTestCase',
    'TheoryModelTblDataHandlerTestCase',
    )

class TheoryModelFormDetectorTestCase(TestCase):
  #fixtures = ["combinatoryModel",]
  def setUp(self):
    self.detector = TheoryModelFormDetector()
    from testBase.patch import *
    patchDumpdata()

  #def testWithCommand(self):
  #  self.embeddedConfigModel = AppModel.objects.get(
  #      app="theory",
  #      name="Command",
  #      )

  #  self.embeddedFieldDict = fieldsForModel(
  #      self.detector.run(appModelObj = self.embeddedConfigModel)
  #      )

  #def testWithCombinatoryModelWithDefaultValue(self):
  #  self.embeddedConfigModel = AppModel.objects.get(
  #      app="testBase",
  #      name="CombinatoryModelWithDefaultValue",
  #      )

  #  self.embeddedFieldDict = fieldsForModel(
  #      self.detector.run(appModelObj = self.embeddedConfigModel)
  #      )

class TheoryModelTblDataHandlerTestCase(TestCase):
  #fixtures = ["combinatoryModel",]
  def setUp(self):
    self.detector = TheoryModelTblDataHandler()
    # temp
    from testBase.patch import *
    patchDumpdata()

  def testHandleFxnName(self):
    self.configModel = AppModel.objects.get(
        app="testBase",
        name="CombinatoryModelWithDefaultValue",
        )

    self.detector.run(self.configModel.fieldParamMap.all())
    #print self.detector.fieldPropDict

