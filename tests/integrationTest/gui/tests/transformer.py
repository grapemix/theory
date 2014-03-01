# -*- coding: utf-8 -*-
##### System wide lib #####
from copy import deepcopy
from datetime import datetime
from ludibrio import Stub
import os

##### Theory lib #####
from theory.conf import settings
from theory.db import models
from theory.gui.transformer import *
from theory.gui.gtk.spreadsheet import SpreadsheetBuilder
from theory.model import AppModel
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####
from tests.testBase.model.combinatoryModel import (
    DummyAppModelManager,
    )


__all__ = ('GtkSpreadsheetModelDataHandlerTestCase', \
    )

class DummyGtkSpreadsheetBuilder(SpreadsheetBuilder):
  """Just disable displaying all widget."""
  def _showWidget(self, listStoreDataType, gtkDataModel, renderKwargsSet, isMainWindow=True):
    self.gtkDataModel = []
    for row in gtkDataModel:
      newRow = []
      for i, data in enumerate(row):
        if(not renderKwargsSet[i]):
          pass
        elif(isinstance(listStoreDataType[i], str)):
          newRow.append(str(data))
        else:
          newRow.append(data)
      self.gtkDataModel.append(newRow)

  def getDataModel(self):
    return self.gtkDataModel

class GtkSpreadsheetModelDataHandlerTestCaseBase(unittest.TestCase):
  def setUp(self):
    dummyAppModelManager = DummyAppModelManager()
    self.model = dummyAppModelManager.getCombinatoryModelWithDefaultValue()
    self.queryLst = dummyAppModelManager.getCombinatoryQuerySet([self.model])
    self.appModelConfig = AppModel.objects.get(
        app="testBase", name="CombinatoryModelWithDefaultValue"
        )

  def test_getKlasslabel(self):
    fieldDict = self.queryLst[0]._fields
    spreadsheetBuilder = DummyGtkSpreadsheetBuilder()
    spreadsheetBuilder.run(self.queryLst, True)

    dataRow = spreadsheetBuilder.getDataModel()
    columnHandlerLabel = spreadsheetBuilder.getColumnHandlerLabel()
    convertedQueryLst = self.handler.run(
        dataRow,
        self.queryLst,
        columnHandlerLabel,
        self.appModelConfig.fieldParamMap,
        )

    correctFieldType = {\
        #'binaryField': {'klassLabel': 'const', },
        #fileField
        #imageField
        'booleanField': {'klassLabel': 'boolField', },
        'dateTimeField': {'klassLabel': 'const', },
        'complexDateTimeField': {'klassLabel': 'const', },
        'uUIDField': {'klassLabel': 'const', },
        'sequenceField': {'klassLabel': 'const', },
        'geoPointField': {'klassLabel': 'editableForceStrField', },
        'decimalField': {'klassLabel': 'floatField', },
        'floatField': {'klassLabel': 'floatField', },
        'intField': {'klassLabel': 'intField', },
        'stringField': {'klassLabel': 'strField', },
        'emailField': {'klassLabel': 'editableForceStrField', },
        'uRLField': {'klassLabel': 'editableForceStrField', },
        'choiceField': {'klassLabel': 'enumField', },
        #dynamicField

        'id': {'klassLabel': 'const', },

        'referenceField': {'klassLabel': 'const', },
        'genericReferenceField': {'klassLabel': 'const', },
        'embeddedDocumentField': {'klassLabel': 'const', },
        'genericEmbeddedDocumentField': {'klassLabel': 'const', },

        #'listFieldBinaryField': {'klassLabel': 'const', },
        'listFieldBooleanField': {'klassLabel': 'listFieldeditableForceStrField', },
        'listFieldDateTimeField': {'klassLabel': 'const', },
        'listFieldComplexDateTimeField': {'klassLabel': 'const', },
        'listFieldUUIDField': {'klassLabel': 'const', },
        'listFieldSequenceField': {'klassLabel': 'const', },
        'listFieldGeoPointField': {'klassLabel': 'listFieldeditableForceStrField', },
        'listFieldDecimalField': {'klassLabel': 'listFieldeditableForceStrField', },
        'listFieldFloatField': {'klassLabel': 'listFieldeditableForceStrField', },
        'listFieldIntField': {'klassLabel': 'listFieldeditableForceStrField', },
        'listFieldStringField': {'klassLabel': 'listFieldeditableForceStrField', },
        'listFieldEmailField': {'klassLabel': 'listFieldeditableForceStrField', },
        'listFieldURLField': {'klassLabel': 'listFieldeditableForceStrField', },
        'listFieldEmbeddedField': {'klassLabel': 'const', },

        'dictFieldBinaryField': {'klassLabel': 'const', },
        'dictFieldBooleanField': {'klassLabel': 'const', },
        'dictFieldDateTimeField': {'klassLabel': 'const', },
        'dictFieldComplexDateTimeField': {'klassLabel': 'const', },
        'dictFieldUUIDField': {'klassLabel': 'const', },
        'dictFieldSequenceField': {'klassLabel': 'const', },
        'dictFieldGeoPointField': {'klassLabel': 'const', },
        'dictFieldDecimalField': {'klassLabel': 'const', },
        'dictFieldFloatField': {'klassLabel': 'const', },
        'dictFieldIntField': {'klassLabel': 'const', },
        'dictFieldStringField': {'klassLabel': 'const', },
        'dictFieldEmailField': {'klassLabel': 'const', },
        'dictFieldURLField': {'klassLabel': 'const', },
        'dictFieldEmbeddedField': {'klassLabel': 'const', },

        'mapFieldBinaryField': {'klassLabel': 'const', },
        'mapFieldBooleanField': {'klassLabel': 'const', },
        'mapFieldDateTimeField': {'klassLabel': 'const', },
        'mapFieldComplexDateTimeField': {'klassLabel': 'const', },
        'mapFieldUUIDField': {'klassLabel': 'const', },
        'mapFieldSequenceField': {'klassLabel': 'const', },
        'mapFieldGeoPointField': {'klassLabel': 'const', },
        'mapFieldDecimalField': {'klassLabel': 'const', },
        'mapFieldFloatField': {'klassLabel': 'const', },
        'mapFieldIntField': {'klassLabel': 'const', },
        'mapFieldStringField': {'klassLabel': 'const', },
        'mapFieldEmailField': {'klassLabel': 'const', },
        'mapFieldURLField': {'klassLabel': 'const', },
        'mapFieldEmbeddedField': {'klassLabel': 'const', },

        #'sortedListFieldBinaryField': {'klassLabel': 'const', },
        'sortedListFieldBooleanField': {'klassLabel': 'listFieldeditableForceStrField', },
        'sortedListFieldDateTimeField': {'klassLabel': 'const', },
        'sortedListFieldComplexDateTimeField': {'klassLabel': 'const', },
        'sortedListFieldUUIDField': {'klassLabel': 'const', },
        'sortedListFieldSequenceField': {'klassLabel': 'const', },
        'sortedListFieldGeoPointField': {'klassLabel': 'listFieldeditableForceStrField', },
        'sortedListFieldDecimalField': {'klassLabel': 'listFieldeditableForceStrField', },
        'sortedListFieldFloatField': {'klassLabel': 'listFieldeditableForceStrField', },
        'sortedListFieldIntField': {'klassLabel': 'listFieldeditableForceStrField', },
        'sortedListFieldStringField': {'klassLabel': 'listFieldeditableForceStrField', },
        'sortedListFieldEmailField': {'klassLabel': 'listFieldeditableForceStrField', },
        'sortedListFieldURLField': {'klassLabel': 'listFieldeditableForceStrField', },
        'sortedListFieldEmbeddedField': {'klassLabel': 'const', },
    }

    for fieldName, fieldProperty in self.handler.fieldPropDict.iteritems():
      try:
        correctFieldProperty = correctFieldType[fieldName]
      except KeyError:
        continue
      for k,correctValue in correctFieldProperty.iteritems():
        self.assertEqual(
            fieldProperty[k],
            correctValue,
            "In {0}: {1}!={2}".format(fieldName, fieldProperty[k], correctValue)
            )

  def test_emptyRowSelected(self):
    fieldDict = self.queryLst[0]._fields
    spreadsheetBuilder = DummyGtkSpreadsheetBuilder()
    spreadsheetBuilder.run(self.queryLst, True)

    dataRow = []
    columnHandlerLabel = spreadsheetBuilder.getColumnHandlerLabel()
    queryLst = []
    convertedQueryLst = self.handler.run(
        dataRow,
        queryLst,
        columnHandlerLabel,
        self.appModelConfig.fieldParamMap,
        )

  def test_getValueConversion(self):
    fieldDict = self.model._fields
    spreadsheetBuilder = DummyGtkSpreadsheetBuilder()
    spreadsheetBuilder.run(self.queryLst, True)

    dataRow = spreadsheetBuilder.getDataModel()
    columnHandlerLabel = spreadsheetBuilder.getColumnHandlerLabel()

    convertedQueryLst = self.handler.run(
        dataRow,
        self.queryLst,
        columnHandlerLabel,
        self.appModelConfig.fieldParamMap,
        )

    for fieldName in fieldDict.keys():
      self.assertEqual(self.queryLst[0][fieldName], convertedQueryLst[0][fieldName])

class GtkSpreadsheetModelDataHandlerTestCase(GtkSpreadsheetModelDataHandlerTestCaseBase):
  def setUp(self):
    super(GtkSpreadsheetModelDataHandlerTestCase, self).setUp()
    self.handler = GtkSpreadsheetModelDataHandler()

class GtkSpreadsheetModelBSONDataHandlerTestCase(GtkSpreadsheetModelDataHandlerTestCaseBase):
  def setUp(self):
    super(GtkSpreadsheetModelBSONDataHandlerTestCase, self).setUp()
    self.handler = GtkSpreadsheetModelBSONDataHandler()


