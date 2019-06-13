# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
import json
import os

##### Theory lib #####
from theory.apps.model import AppModel
from theory.conf import settings
from theory.gui.transformer import *
from theory.gui.transformer.protoBufModelTblPaginator import ProtoBufModelTblPaginator
from theory.gui.gtk.spreadsheet import SpreadsheetBuilder
from theory.test.testcases import TestCase

##### Theory third-party lib #####

##### Local app #####
from testBase.patch import patchDumpdata

##### Theory app #####

##### Misc #####
from testBase.model import (
    CombinatoryModelWithDefaultValue,
    DummyAppModelManager,
    )


__all__ = ('GtkSpreadsheetModelDataHandlerTestCase',
    )

class DummyGtkSpreadsheetBuilder(SpreadsheetBuilder):
  """Just disable displaying all widget."""
  def _showWidget(
      self,
      listStoreDataType,
      gtkDataModel,
      renderKwargsSet,
      isMainWindow=True
      ):
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

class GtkSpreadsheetModelDataHandlerTestCaseBase(object):
  fixtures = ["theory", "combinatory_meta",]

  #@patch("theory.gui.theory_pb2.DataRow", side_effect=lambda **kwarg: kwarg)
  #@patch("theory.gui.theory_pb2.StrVsMap", side_effect=lambda **kwarg: kwarg)
  def setUp(self):
    CombinatoryModelWithDefaultValue().save()

    self.spData = {
      "appName": "testBase",
      "mdlName": "CombinatoryModelWithDefaultValue",
      "pageNum": 1,
      "pageSize": 10,
      "boolIdxLst": [],
    }

    protoBufModelTblPaginator = ProtoBufModelTblPaginator()
    self.dataComplex = protoBufModelTblPaginator.run(
        self.spData["appName"],
        self.spData["mdlName"],
        self.spData["pageNum"],
        self.spData["pageSize"],
    )
    flatDataLst = []
    for grpcDataRow in self.dataComplex["dataLst"]:
      flatDataLst.append([i for i in grpcDataRow.cell])
    self.dataComplex["dataLst"] = flatDataLst

    # To convert protobuf msg of dataLst back into python list
    fieldNameVsProp = []
    for i in self.dataComplex["fieldNameVsProp"]:
      row = (i.k, {})
      for k, v in i.v.items():
        if k == "choices":
          v = json.loads(v)
        row[1][k] = v
      fieldNameVsProp.append(row)
    fieldNameVsProp = OrderedDict(fieldNameVsProp)
    self.dataComplex["fieldNameVsProp"] = fieldNameVsProp

  def dummyFxn(self):
    pass

  def test_getKlasslabel(self):
    spreadsheetBuilder = DummyGtkSpreadsheetBuilder()
    spreadsheetBuilder.run(
        "testBase",
        "CombinatoryModelWithDefaultValue",
        self.dataComplex["dataLst"],
        self.dataComplex["fieldNameVsProp"],
        True,
        [],
        self.spData,
        self.dummyFxn,
        None
        )

    dataRow = self.dataComplex["dataLst"]
    columnHandlerLabel = spreadsheetBuilder.getColumnHandlerLabel()

    correctFieldType = {
        #'binaryField': {'klassLabel': 'const', },
        #fileField
        #imageField
        'booleanField': {'klassLabel': 'boolField', },
        'dateTimeField': {'klassLabel': 'nonEditableForceStrField', },
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

        'id': {'klassLabel': 'nonEditableForceStrField', },

        'referenceField': {'klassLabel': 'modelField', },
        'genericReferenceField': {'klassLabel': 'const', },
        'embeddedDocumentField': {'klassLabel': 'const', },
        'genericEmbeddedDocumentField': {'klassLabel': 'const', },

        #'listFieldBinaryField': {'klassLabel': 'const', },
        'listFieldBooleanField': {'klassLabel': 'listFieldeditableForceStrField', },
        'listFieldDateTimeField': {'klassLabel': 'listFieldnonEditableForceStrField', },
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

    for fieldName, fieldProperty in self.dataComplex["fieldNameVsProp"].items():
      try:
        correctFieldProperty = correctFieldType[fieldName]
      except KeyError:
        continue
      for k,correctValue in correctFieldProperty.items():
        self.assertEqual(
            fieldProperty[k],
            correctValue,
            "In {0}: {1}!={2}".format(fieldName, fieldProperty[k], correctValue)
            )

  def test_emptyRowSelected(self):
    spreadsheetBuilder = DummyGtkSpreadsheetBuilder()
    spreadsheetBuilder.run(
        "testBase",
        "CombinatoryModelWithDefaultValue",
        self.dataComplex["dataLst"],
        self.dataComplex["fieldNameVsProp"],
        True,
        [],
        self.spData,
        self.dummyFxn,
        None
        )

  def test_getValueConversion(self):
    fieldNameLst = self.dataComplex["fieldNameVsProp"].keys()
    spreadsheetBuilder = DummyGtkSpreadsheetBuilder()
    spreadsheetBuilder.run(
        "testBase",
        "CombinatoryModelWithDefaultValue",
        self.dataComplex["dataLst"],
        self.dataComplex["fieldNameVsProp"],
        True,
        [],
        self.spData,
        self.dummyFxn,
        None
        )

    dataRow = self.dataComplex["dataLst"]
    columnHandlerLabel = spreadsheetBuilder.getColumnHandlerLabel()

    convertedQueryLst = self.handler.run(
        dataRow,
        columnHandlerLabel,
        self.dataComplex["fieldNameVsProp"],
        )
    convertedQueryLst = json.loads(convertedQueryLst[0])

    for i, fieldName in enumerate(fieldNameLst):
      if fieldName in ["intField", "floatField", ]:
        convertedQueryLst[fieldName] = json.dumps(convertedQueryLst[fieldName])
      elif fieldName in [
        "binaryField",
        "listFieldDateTimeField",
        "referenceField"
      ]:
        # The above will be ignored
        continue
      elif fieldName.startswith("listField"):
        convertedQueryLst[fieldName] = json.dumps(convertedQueryLst[fieldName])
      elif fieldName == "choiceField":
        convertedQueryLst[fieldName] = \
          CombinatoryModelWithDefaultValue.DUMMY_CHOICES[0][1]
      elif fieldName == "decimalField":
        convertedQueryLst[fieldName] = str(
          Decimal(convertedQueryLst[fieldName]).quantize(Decimal('.001'))
        )
      elif fieldName == "booleanField":
        convertedQueryLst[fieldName] = "1"
      self.assertEqual(
          dataRow[0][i],
          convertedQueryLst[fieldName]
          )

class GtkSpreadsheetModelDataHandlerTestCase(
    GtkSpreadsheetModelDataHandlerTestCaseBase,
    TestCase
    ):
  def setUp(self):
    super(GtkSpreadsheetModelDataHandlerTestCase, self).setUp()
    self.handler = GtkSpreadsheetModelDataHandler()

class GtkSpreadsheetModelBSONDataHandlerTestCase(
    GtkSpreadsheetModelDataHandlerTestCaseBase,
    TestCase
    ):
  def setUp(self):
    super(GtkSpreadsheetModelBSONDataHandlerTestCase, self).setUp()
    self.handler = GtkSpreadsheetModelBSONDataHandler()


