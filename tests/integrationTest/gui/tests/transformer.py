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
from theory.utils import unittest

##### Theory third-party lib #####

##### Local app #####
from dummyModelFactory import DummyModelFactory

##### Theory app #####

##### Misc #####

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
  def test_getKlasslabel(self):

    modelFactory = DummyModelFactory()
    model = modelFactory.getDummyModelWithDefaultValue()
    query = modelFactory.getDummyQuerySet([model])
    fieldDict = query[0]._fields
    spreadsheetBuilder = DummyGtkSpreadsheetBuilder()
    spreadsheetBuilder.run(query, True)

    dataRow = spreadsheetBuilder.getDataModel()
    columnHandlerLabel = spreadsheetBuilder.getColumnHandlerLabel()
    queryLst = [model]
    convertedQueryLst = self.handler.run(dataRow, queryLst, columnHandlerLabel)

    correctFieldType = {\
        'binaryField': {'klassLabel': 'const', },
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
        #dynamicField

        'id': {'klassLabel': 'const', },

        'referenceField': {'klassLabel': 'const', },
        'genericReferenceField': {'klassLabel': 'const', },
        'embeddedDocumentField': {'klassLabel': 'const', },
        'genericEmbeddedDocumentField': {'klassLabel': 'const', },

        'listFieldBinaryField': {'klassLabel': 'const', },
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
        'mapFieldBooleanField': {'klassLabel': 'listFieldeditableForceStrField', },
        'mapFieldDateTimeField': {'klassLabel': 'const', },
        'mapFieldComplexDateTimeField': {'klassLabel': 'const', },
        'mapFieldUUIDField': {'klassLabel': 'const', },
        'mapFieldSequenceField': {'klassLabel': 'const', },
        'mapFieldGeoPointField': {'klassLabel': 'listFieldeditableForceStrField', },
        'mapFieldDecimalField': {'klassLabel': 'listFieldeditableForceStrField', },
        'mapFieldFloatField': {'klassLabel': 'listFieldeditableForceStrField', },
        'mapFieldIntField': {'klassLabel': 'listFieldeditableForceStrField', },
        'mapFieldStringField': {'klassLabel': 'listFieldeditableForceStrField', },
        'mapFieldEmailField': {'klassLabel': 'listFieldeditableForceStrField', },
        'mapFieldURLField': {'klassLabel': 'listFieldeditableForceStrField', },
        'mapFieldEmbeddedField': {'klassLabel': 'const', },

        'sortedListFieldBinaryField': {'klassLabel': 'const', },
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

    for fieldName, fieldProperty in self.handler.fieldType.iteritems():
      correctFieldProperty = correctFieldType[fieldName]
      for k,correctValue in correctFieldProperty.iteritems():
        self.assertEqual(fieldProperty[k], correctValue)

  def test_emptyRowSelected(self):
    modelFactory = DummyModelFactory()
    model = modelFactory.getDummyModelWithDefaultValue()
    query = modelFactory.getDummyQuerySet([model])
    fieldDict = query[0]._fields
    spreadsheetBuilder = DummyGtkSpreadsheetBuilder()
    spreadsheetBuilder.run(query, True)

    dataRow = []
    columnHandlerLabel = spreadsheetBuilder.getColumnHandlerLabel()
    queryLst = []
    convertedQueryLst = self.handler.run(dataRow, queryLst, columnHandlerLabel)

  def test_getValueConversion(self):
    modelFactory = DummyModelFactory()
    model = modelFactory.getDummyModelWithDefaultValue()
    queryLst = modelFactory.getDummyQuerySet([model])
    fieldDict = model._fields
    spreadsheetBuilder = DummyGtkSpreadsheetBuilder()
    spreadsheetBuilder.run(queryLst, True)

    dataRow = spreadsheetBuilder.getDataModel()
    columnHandlerLabel = spreadsheetBuilder.getColumnHandlerLabel()

    convertedQueryLst = self.handler.run(dataRow, queryLst, columnHandlerLabel)

    for fieldName in fieldDict.keys():
      self.assertEqual(queryLst[0][fieldName], convertedQueryLst[0][fieldName])

class GtkSpreadsheetModelDataHandlerTestCase(GtkSpreadsheetModelDataHandlerTestCaseBase):
  def setUp(self):
    self.handler = GtkSpreadsheetModelDataHandler()

class GtkSpreadsheetModelBSONDataHandlerTestCase(GtkSpreadsheetModelDataHandlerTestCaseBase):
  def setUp(self):
    self.handler = GtkSpreadsheetModelBSONDataHandler()


