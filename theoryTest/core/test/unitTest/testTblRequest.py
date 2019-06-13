# -*- coding: utf-8 -*-
##### System wide lib #####
from unittest.mock import patch

##### Theory lib #####
from theory.apps.model import AppModel
from collections import OrderedDict
from theory.gui.transformer.protoBufModelTblPaginator import ProtoBufModelTblPaginator
from theory.test.testcases import TestCase
from theory.utils.importlib import importClass

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = ('TestTblRequest',)


class TestTblRequest(TestCase):
  fixtures = ["theory",]

  def setUp(self):
    self.protoBufModelTblPaginator = ProtoBufModelTblPaginator()

  def testFieldExist(self):
    dataComplex = self.protoBufModelTblPaginator.run(
        "theory.apps",
        "CmdField",
        1,
        10
    )
    self.assertIn("dataLst", dataComplex)
    self.assertIn("mdlTotalNum", dataComplex)
    self.assertIn("fieldNameVsProp", dataComplex)
    # Since protobuf does not support OrderedDict, in order to preserve order,
    # the gui should reconstrct the list to OrderedDict
    assert type(dataComplex["fieldNameVsProp"]) is list

    dataComplex = self.protoBufModelTblPaginator.run(
        "theory.apps",
        "CmdField",
        2,
        10
    )

    self.assertIn("dataLst", dataComplex)
    self.assertNotIn("mdlTotalNum", dataComplex)
    self.assertNotIn("fieldNameVsProp", dataComplex)

  @patch("theory.gui.theory_pb2.DataRow", side_effect=lambda **kwarg: kwarg)
  @patch("theory.gui.theory_pb2.StrVsMap", side_effect=lambda **kwarg: kwarg)
  def testData(self, dataRowMock, strVsMapMock):
    dataComplex = self.protoBufModelTblPaginator.run(
        "theory.apps",
        "CmdField",
        1,
        3
    )
    self.assertEqual(
      sorted(dataComplex["fieldNameVsProp"], key=lambda x: x["k"]),
      sorted([
        {
          "k": "comment",
          "v": {
            "klassLabel": "strField",
            "type": "str"
          }
        },
        {
          "k": "isReadOnly",
          "v": {
            "klassLabel": "boolField",
            "type": "bool"
          }
        },
        {
          "k": "isOptional",
          "v": {
            "klassLabel": "boolField",
            "type": "bool"
          }
        },
        {
          "k": "param",
          "v": {
            "klassLabel": "strField",
            "type": "str"
          }
        },
        {
          "k": "type",
          "v": {
            "klassLabel": "strField",
            "type": "str"
          }
        },
        {
          "k": "name",
          "v": {
            "klassLabel": "strField",
            "type": "str"
          }
        },
        {
          "k": "id",
          "v": {
            "klassLabel": "nonEditableForceStrField",
            "type": "nonEditableForceStr"
          }
        },
        {
          "k": "command",
          "v": {
            "klassLabel": "modelField",
            "foreignModel": "Command",
            "type": "model",
            "foreignApp": "theory.apps"
          }
        }
      ], key=lambda x: x["k"]),
    )
    self.assertEqual(dataComplex["mdlTotalNum"], 102)
    self.assertEqual(len(dataComplex["dataLst"]), 3)
