# -*- coding: utf-8 -*-
##### System wide lib #####
from collections import namedtuple
import json
import sys

##### Theory lib #####
from theory.apps.model import AppModel, Command
from theory.core.bridge import Bridge
from theory.core.reactor.reactor import Reactor
from theory.gui import theory_pb2
from theory.test.testcases import TestCase
from theory.test.util import tag

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

__all__ = (
    'TestCmdModelUpsert',
    )

"""
WARNING: this test case will use cmd modelUpsert getModelFormKlass and hence it
can not mix anything with gevent subprocess stuff. This tc eventually have to
rewrite after core and GUI separated because this tc require both core and GUI's
component. This should be in the truly integration test.
"""
class ReactorTestMixin(object):
  def setUp(self):
    self.reactor = Reactor()
    self.reactor._dumpActionQ = self._fakeDumpActionQ
    self.reactor.actionQ = []

  def _fakeDumpActionQ(self):
    return self.reactor.actionQ

  def unJsonActionVal(self, action):
    try:
      action["val"] = json.loads(action["val"])
    except KeyError:
      pass
    except:
      action["val"] = action["val"]
    return action

  def pprintActionQ(self):
    # For debugging only
    for action in self.reactor.actionQ:
      print
      self.pprintAction(action)

  def pprintAction(self, action):
    # Helper fxn
    print(json.dumps(
      self.unJsonActionVal(action),
      indent=2,
      sort_keys=True
    ).replace("true", "True").replace("false", "False").replace("null", "None"))

class CmdModelUpsert(ReactorTestMixin, TestCase):
  fixtures = ["theory",]

  def setUp(self):
    self.bridge = Bridge()
    super(CmdModelUpsert, self).setUp()

  @tag('gui')
  def testCreateInstance(self):
    val = '{{"cmdName": "modelUpsert", "finalDataDict": {0}}}'.format(
        json.dumps({
          "appName": "theory.apps",
          "modelName": "AppModel",
          "isInNewWindow": True,
        })
    )
    self.reactor.call(
      theory_pb2.ReactorReq(
        action="runCmd",
        val=val
      ),
      None
    )

  @tag('gui')
  def testModelUpsertFlow(self):
    # === step 1 ===
    self.reactor.call(
      theory_pb2.ReactorReq(action="autocompleteRequest", val="modelUpsert("),
      None
    )

    self.assertEqual(len(self.reactor.actionQ), 3)
    self.assertDict(
      self.unJsonActionVal(self.reactor.actionQ[0]),
      {
        "action": "cleanUpCrt"
      }
    )

    self.assertDict(
      self.unJsonActionVal(self.reactor.actionQ[1]),
      {
        "action": "buildParamForm",
        "val": {
          "cmdId": 16,
          "isFocusOnFirstChild": "true",
          "fieldNameVsDesc": {
            "appName": {
              "choices": [
                [
                  "theory.apps",
                  "theory.apps"
                ],
                [
                  "testBase",
                  "testBase"
                ]
              ],
              "errorMessages": {
                "invalid": "Enter a valid value.",
                "invalidChoice": (
                  "Select a valid choice. %(value)s is not one of the "
                  "available choices."
                ),
                "required": "This field is required."
              },
              "helpText": "The name of applications to be listed",
              "initData": "theory.apps",
              "label": "Application Name",
              "localize": False,
              "required": True,
              "showHiddenInitial": False,
              "type": "ChoiceField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": True
            },
            "isInNewWindow": {
              "errorMessages": {
                "invalid": "Enter a valid value.",
                "required": "This field is required."
              },
              "helpText": "Is shown in new window",
              "initData": False,
              "label": "Is in new window",
              "localize": False,
              "required": False,
              "showHiddenInitial": False,
              "type": "BooleanField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": False
            },
            "modelName": {
              "choices": [
                ["Adapter", "Adapter"],
                ["AdapterBuffer", "AdapterBuffer"],
                ["AppModel", "AppModel"],
                ["BinaryClassifierHistory", "BinaryClassifierHistory"],
                ["CmdField", "CmdField"],
                ["Command", "Command"],
                ["FieldParameter", "FieldParameter"],
                ["History", "History"],
                ["Mood", "Mood"],
              ],
              "errorMessages": {
                "invalid": "Enter a valid value.",
                "invalidChoice": (
                  "Select a valid choice. %(value)s is not one of the "
                  "available choices."
                ),
                "required": "This field is required."
              },
              "helpText": "The name of models to be listed",
              "initData": "Adapter",
              "label": "Model Name",
              "localize": False,
              "required": True,
              "showHiddenInitial": False,
              "type": "ChoiceField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": False
            },
            "queryId": {
              "appFieldName": "appName",
              "errorMessages": {
                "appInvalid": "No app has been set",
                "configInvalid": "Configuration has been invalid",
                "dbInvalid": "Unable to find data in DB",
                "invalid": "Unable to import the given queryset",
                "modelInvalid": "No model has been set",
                "required": "This field is required."
              },
              "helpText": "The instance to be edited",
              "initData": None,
              "label": "instance id",
              "localize": False,
              "modelFieldName": "modelName",
              "required": False,
              "showHiddenInitial": False,
              "type": "DynamicModelIdField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": False
            },
            "verbosity": {
              "errorMessages": {
                "invalid": "Enter a whole number.",
                "required": "This field is required."
              },
              "helpText": "",
              "initData": 1,
              "label": "verbosity",
              "localize": False,
              "required": False,
              "showHiddenInitial": False,
              "type": "IntegerField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": False
            }
          }
        }
      },
      excludeKeyLst=[
        "cmdId",
        "helpText",
        "appName",
      ]
    )

    self.assertDict(
      self.unJsonActionVal(self.reactor.actionQ[2]),
      {
        "action": "focusOnParamFormFirstChild"
      }
    )

    # === step 2 ===
    self.reactor.call(
      theory_pb2.ReactorReq(
        action="runCmd",
        val=json.dumps({
          "cmdName": "modelUpsert",
          "finalDataDict": {
            "appName": "theory.apps",
            "modelName": "AppModel",
            "queryId": [1]
          }
        })
      ),
      None
    )

    self.assertEqual(len(self.reactor.actionQ), 3)

    self.assertDict(
      self.unJsonActionVal(self.reactor.actionQ[0]),
      {
        "action": "cleanUpCrt"
      }
    )

    self.assertDict(
      self.unJsonActionVal(self.reactor.actionQ[1]),
      {
        "action": "buildParamForm",
        "val": {
          "appName": "theory.apps",
          "cmdId": 16,
          "isInNewWindow": False,
          "fieldNameVsDesc": {
            "app": {
              "errorMessages": {
                "invalid": "Enter a valid value.",
                "required": "This field is required."
              },
              "helpText": "Application name",
              "initData": "theory.apps",
              "label": "Application name",
              "localize": False,
              "required": True,
              "showHiddenInitial": False,
              "type": "TextField",
              "widgetIsContentChgTrigger": False,
              "maxLen": 256,
              "widgetIsFocusChgTrigger": False
            },
            "formField": {
              "childFieldTemplate": "TextField",
              "errorMessages": {
                "invalid": "Enter a list of values.",
                "required": "This field is required."
              },
              "helpText": "The fields being showed in a form",
              "initData": [
                "id",
                "name",
                "importPath",
                "propertyLst"
              ],
              "label": "Form field",
              "localize": False,
              "required": True,
              "showHiddenInitial": False,
              "type": "ListField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": False
            },
            "id": {
              "errorMessages": {
                "invalid": "Enter a whole number.",
                "required": "This field is required."
              },
              "helpText": "",
              "initData": 1,
              "label": "id",
              "localize": False,
              "required": False,
              "showHiddenInitial": False,
              "type": "IntegerField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": False
            },
            "importPath": {
              "errorMessages": {
                "invalid": "Enter a valid value.",
                "required": "This field is required."
              },
              "helpText": "The path to import the model",
              "initData": "theory.apps.model.Adapter",
              "label": "Import path",
              "localize": False,
              "required": True,
              "maxLen": 256,
              "showHiddenInitial": False,
              "type": "TextField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": False
            },
            "importanceRating": {
              "errorMessages": {
                "invalid": "Enter a whole number.",
                "required": "This field is required."
              },
              "initData": 0,
              "label": "Importance rating",
              "localize": False,
              "required": True,
              "showHiddenInitial": False,
              "type": "IntegerField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": False
            },
            "name": {
              "errorMessages": {
                "invalid": "Enter a valid value.",
                "required": "This field is required."
              },
              "helpText": "Application model name",
              "initData": "Adapter",
              "label": "App model name",
              "localize": False,
              "required": True,
              "maxLen": 256,
              "showHiddenInitial": False,
              "type": "TextField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": False
            },
            "tblField": {
              "childFieldTemplate": "TextField",
              "errorMessages": {
                "invalid": "Enter a list of values.",
                "required": "This field is required."
              },
              "helpText": "The fields being showed in a table",
              "initData": [
                "id",
                "name",
                "importPath",
                "propertyLst"
              ],
              "label": "Table field",
              "localize": False,
              "required": True,
              "showHiddenInitial": False,
              "type": "ListField",
              "widgetIsContentChgTrigger": False,
              "widgetIsFocusChgTrigger": False
            }
          },
          "modelName": "AppModel",
          "nextFxn": "upsertModelLst"
        }
      },
      excludeKeyLst=[
        "cmdId",
        "helpText",
      ]
    )


    self.assertDict(
      self.unJsonActionVal(self.reactor.actionQ[2]),
      {
        "action": "restoreCmdLine"
      }
    )

    # === step 3 ===
    appModelModel = AppModel.objects.get(id=1)
    r = self.reactor.syncFormData(
      theory_pb2.FieldData(
        cmdId=int(Command.objects.get(name="modelUpsert").id),
        fieldName="appName",
        jsonData=json.dumps("theory.apps"),
      ),
      None
    )
    self.assertDict(
      json.loads(r.jsonData),
      {
        "modelName": {
          "choices": [
            ["Adapter", "Adapter"],
            ["AdapterBuffer", "AdapterBuffer"],
            ["AppModel", "AppModel"],
            ["BinaryClassifierHistory", "BinaryClassifierHistory"],
            ["CmdField", "CmdField"],
            ["Command", "Command"],
            ["FieldParameter", "FieldParameter"],
            ["History", "History"],
            ["Mood", "Mood"]
          ]
        }
      }

    )
    # === step 4 ===
    self.reactor.actionQ = []
    org_name = appModelModel.name
    self.reactor.upsertModelLst(
      theory_pb2.MultiModelLstData(
        modelLstData=[theory_pb2.ModelLstData(
          appName="theory.apps",
          mdlName="AppModel",
          jsonDataLst=[
            json.dumps({
              "id": int(appModelModel.id),
              "name": org_name + "_test"

            })
          ]
        )]
      ),
      None
    )
    appModelModel = AppModel.objects.get(id=1)
    self.assertEqual(appModelModel.name, org_name + "_test")

    self.assertDict(
      self.unJsonActionVal(self.reactor.actionQ[0]),
      {
        "action": "printStdOut",
        "val": (
          "=== theory.apps - AppModel ===\n"
          "Status: success\n"
          "Msg: 1 models have been saved\n"
        )
      }
    )

  @tag('gui')
  def testBareModelUpsert(self):
    (cmd, status) = self.bridge.executeEzCommand(
      "theory.apps",
      "modelUpsert",
      [],
      {
        "appName": "theory.apps",
        "modelName": "AppModel",
        "queryId": [1]
      }
    )
    self.assertTrue(status)
    self.assertEqual(len(cmd.actionQ), 2)
    self.assertDict(
      self.unJsonActionVal(cmd.actionQ[0]),
      {'action':'cleanUpCrt'}
    )
    self.assertDict(
      self.unJsonActionVal(cmd.actionQ[1]),
      {
        "action": "buildParamForm",
        "val": {
          "cmdId":1,
          "modelName":"AppModel",
          "isInNewWindow": False,
          "fieldNameVsDesc":{
            "name":{
              "errorMessages":{
                "required":"This field is required.",
                "invalid":"Enter a valid value."
              },
              "widgetIsContentChgTrigger":False,
              "required":True,
              "initData":"Adapter",
              "label":"App model name",
              "helpText":"Application model name",
              "showHiddenInitial":False,
              "localize":False,
              "maxLen": 256,
              "widgetIsFocusChgTrigger":False,
              "type":"TextField"
            },
            "app":{
              "errorMessages":{
                "required":"This field is required.",
                "invalid":"Enter a valid value."
              },
              "widgetIsContentChgTrigger":False,
              "required":True,
              "initData":"theory.apps",
              "label":"Application name",
              "helpText":"Application name",
              "showHiddenInitial":False,
              "localize":False,
              "widgetIsFocusChgTrigger":False,
              "maxLen": 256,
              "type":"TextField"
            },
            "tblField":{
              "errorMessages":{
                "required":"This field is required.",
                "invalid":"Enter a list of values."
              },
              "widgetIsContentChgTrigger":False,
              "required":True,
              "initData":[
                "id",
                "name",
                "importPath",
                "propertyLst"
              ],
              "label":"Table field",
              "helpText":"The fields being showed in a table",
              "childFieldTemplate":"TextField",
              "showHiddenInitial":False,
              "localize":False,
              "widgetIsFocusChgTrigger":False,
              "type":"ListField"
            },
            "formField":{
              "errorMessages":{
                "required":"This field is required.",
                "invalid":"Enter a list of values."
              },
              "widgetIsContentChgTrigger":False,
              "required":True,
              "initData":[
                "id",
                "name",
                "importPath",
                "propertyLst"
              ],
              "label":"Form field",
              "helpText":"The fields being showed in a form",
              "childFieldTemplate":"TextField",
              "showHiddenInitial":False,
              "localize":False,
              "widgetIsFocusChgTrigger":False,
              "type":"ListField"
            },
            "importPath":{
              "errorMessages":{
                "required":"This field is required.",
                "invalid":"Enter a valid value."
              },
              "widgetIsContentChgTrigger":False,
              "required":True,
              "initData":"theory.apps.model.Adapter",
              "label":"Import path",
              "helpText":"The path to import the model",
              "showHiddenInitial":False,
              "localize":False,
              "maxLen": 256,
              "widgetIsFocusChgTrigger":False,
              "type":"TextField"
            },
            "importanceRating":{
              "errorMessages":{
                "required":"This field is required.",
                "invalid":"Enter a whole number."
              },
              "widgetIsContentChgTrigger":False,
              "required":True,
              "initData":0,
              "label":"Importance rating",
              "showHiddenInitial":False,
              "localize":False,
              "widgetIsFocusChgTrigger":False,
              "type":"IntegerField"
            },
            "id":{
              "errorMessages":{
                "required":"This field is required.",
                "invalid":"Enter a whole number."
              },
              "initData":1,
              "showHiddenInitial":False,
              "localize":False,
              "widgetIsContentChgTrigger":False,
              "required":False,
              "label":"id",
              "helpText":"",
              "widgetIsFocusChgTrigger":False,
              "type":"IntegerField"
            }
          },
          "nextFxn":"upsertModelLst",
          "appName":"theory.apps"
        }
      },
      excludeKeyLst=[
        "cmdId",
        "helpText",
      ]
      )
