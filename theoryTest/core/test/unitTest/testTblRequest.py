# -*- coding: utf-8 -*-
##### System wide lib #####
from mock import patch

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
    self.assertDict(
      dataComplex,
      {
        "fieldNameVsProp": [
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
        ],
        "mdlTotalNum": 102,
        "dataLst": [
          {
            'cell': [
              u'',
              '0',
              '1',
              u'{"errorMessages": {"required": "This field is required.", "invalid": "Enter a whole number."}, "widgetIsContentChgTrigger": false, "required": false, "initData": 1, "label": "verbosity", "helpText": "", "showHiddenInitial": false, "localize": false, "widgetIsFocusChgTrigger": false, "type": "IntegerField"}',
              u'',
              u'verbosity',
              u'1',
              '1'
            ]
          },
          {
            'cell': [
              u'',
              '0',
              '0',
              u'{"errorMessages": {"required": "This field is required.", "invalidChoice": "Select a valid choice. %(value)s is not one of the available choices.", "invalid": "Enter a valid value."}, "widgetIsContentChgTrigger": false, "required": true, "initData": "theory.apps", "label": "Application Name", "choices": [], "helpText": "The name of applications to be listed", "dynamicChoiceLst": "", "showHiddenInitial": false, "localize": false, "widgetIsFocusChgTrigger": true, "type": "ChoiceField"}',
              u'',
              u'appName',
              u'2',
              '1'
            ]
          },
          {
            'cell': [
              u'',
              '0',
              '0',
              u'{"errorMessages": {"required": "This field is required.", "invalidChoice": "Select a valid choice. %(value)s is not one of the available choices.", "invalid": "Enter a valid value."}, "widgetIsContentChgTrigger": false, "required": true, "initData": null, "label": "Model Name", "choices": [], "helpText": "The name of models to be listed", "dynamicChoiceLst": "", "showHiddenInitial": false, "localize": false, "widgetIsFocusChgTrigger": false, "type": "ChoiceField"}',
              u'',
              u'modelName',
              u'3',
              '1'
            ]
          }
        ]
      }
    )
