# -*- coding: utf-8 -*-
##### System wide lib #####
from ludibrio import Stub

##### Theory lib #####
from theory.gui.form import *
from theory.gui.model import fieldsForModel
from theory.gui.transformer.mongoModelFormDetector import \
    MongoModelFormDetector
from theory.gui.transformer.mongoModelTblDataHandler import \
    MongoModelTblDataHandler
from theory.gui.transformer.theoryJSONEncoder import TheoryJSONEncoder
from theory.model import AppModel
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = (
    'MongoModelFormDetectorTestCase',
    'MongoModelTblDataHandlerTestCase',
    )

class MongoModelFormDetectorTestCase(unittest.TestCase):
  def setUp(self):
    self.detector = MongoModelFormDetector()

  def testWithCommand(self):
    self.embeddedConfigModel = AppModel.objects.get(
        app="theory",
        name="Command",
        )

    self.embeddedFieldDict = fieldsForModel(
        self.detector.run(appModelObj = self.embeddedConfigModel)
        )

  def testWithCombinatoryModelWithDefaultValue(self):
    self.embeddedConfigModel = AppModel.objects.get(
        app="testBase",
        name="CombinatoryModelWithDefaultValue",
        )

    self.embeddedFieldDict = fieldsForModel(
        self.detector.run(appModelObj = self.embeddedConfigModel)
        )

class MongoModelTblDataHandlerTestCase(unittest.TestCase):
  def setUp(self):
    self.detector = MongoModelTblDataHandler()

  def testHandleFxnName(self):
    self.configModel = AppModel.objects.get(
        app="testBase",
        name="CombinatoryModelWithDefaultValue",
        )

    self.detector.run(self.configModel.fieldParamMap)
    #print self.detector.fieldPropDict

