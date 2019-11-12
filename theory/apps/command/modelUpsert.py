# -*- coding: utf-8 -*-
#!/usr/bin/env python
##### System wide lib #####
import json

##### Theory lib #####
from theory.apps.command.baseCommand import SimpleCommand
from theory.apps.model import AppModel, Command
from theory.conf import settings
from theory.core.exceptions import ValidationError
from theory.core.resourceScan.commandClassScanner import CommandClassScanner
from theory.gui import field
from theory.gui.transformer.theoryJSONEncoder import TheoryJSONEncoder
from theory.utils.importlib import importClass

##### Theory third-party lib #####

##### Local app #####

##### Theory app #####

##### Misc #####

class ModelUpsert(SimpleCommand):
  """
  To update model if an instance id is provided. Otherwise, this class will
  insert a model.
  """
  name = "modelUpsert"
  verboseName = "modelUpsert"
  _drums = {"Dummy": 1,}

  class ParamForm(SimpleCommand.ParamForm):
    appName = field.ChoiceField(label="Application Name",
        helpText="The name of applications to be listed",
        initData="theory.apps",
        dynamicChoiceLst=(set([("theory.apps", "theory.apps")] +
          [(appName, appName) for appName in settings.INSTALLED_APPS])),
        uiPropagate=[
          ("fields", "queryId", "appName",),
        ],
        )
    modelName = field.ChoiceField(label="Model Name",
        helpText="The name of models to be listed",
        dynamicChoiceLst=[
          (appModel.name, appModel.name)
           for appModel in AppModel.objects.only("name").filter(
               app="theory.apps"
           ).orderBy("name")
          ],
        uiPropagate=[
          ("fields", "queryId", "mdlName",),
        ],
        )
    queryId = field.QuerysetField(
        required=False,
        label="instance id",
        helpText="The instance to be edited",
        initData=None,
        maxLen=1,
        isSkipInHistory=True,
        )
    isInNewWindow = field.BooleanField(
        label="Is in new window",
        helpText="Is shown in new window",
        required=False,
        initData=False,
        )

    def _getQuerysetByAppAndModel(self, appName, modelName):
      # being called from modelTblFilterBase.py
      appModel = AppModel.objects.only("importPath").get(
          app=appName,
          name=modelName
          )
      return importClass(appModel.importPath).objects.all()

    def _updateDynamicChoiceLst(self, appName):
        self.fields["modelName"].dynamicChoiceLst = \
            self._getModelNameChoices(appName)

    def fillInitFields(self, cmdModel, cmdArgs, cmdKwargs):
      super(ModelUpsert.ParamForm, self).fillInitFields(
          cmdModel,
          cmdArgs,
          cmdKwargs
          )
      if len(cmdArgs) == 2:
        # This is for QuerysetField preset the form for modelSelect
        self._updateDynamicChoiceLst(self.fields["appName"].initData)
      elif "appName" in cmdKwargs and "modelName" in cmdKwargs:
        # For perseting by kwargs
        self._updateDynamicChoiceLst(cmdKwargs["appName"])

    def fillFinalFields(self, cmdModel, cmdArgs, cmdKwargs):
      super(ModelUpsert.ParamForm, self).fillFinalFields(
          cmdModel,
          cmdArgs,
          cmdKwargs
          )
      if len(cmdArgs) == 2:
        # This is for QuerysetField preset the form for modelSelect
        self._updateDynamicChoiceLst(self.fields["appName"].finalData)
      elif "appName" in cmdKwargs and "modelName" in cmdKwargs:
        # For perseting by kwargs
        self._updateDynamicChoiceLst(cmdKwargs["appName"])

    def _getModelNameChoices(self, appName):
      return [
        (i.name, i.name)
        for i in AppModel.objects.only("name").filter(app=appName).orderBy("name")
      ]

    def appNameFocusChgCallback(self, appName):
      return {
          "modelName": {"choices": self._getModelNameChoices(appName)},
      }

  @property
  def stdOut(self):
    return self._stdOut

  def getModelFormKlass(self, appModel, modelKlass):
    from theory.gui.model import ModelForm
    from theory.gui.etk.form import StepFormBase
    class DynamicModelForm(ModelForm, StepFormBase):
      class Meta:
        model = modelKlass
        #fields = appModel.formField
        exclude = []
    return DynamicModelForm

  def isQueryIdNonEmpty(self, queryId):
    return queryId is not None and queryId != "None" and queryId != []

  def run(self, *args, **kwargs):
    f = self.paramForm.clean()
    appModel = AppModel.objects.get(
        app=f["appName"],
        name=f["modelName"]
        )

    modelKlass = importClass(appModel.importPath)
    modelFormKlass = self.getModelFormKlass(appModel, modelKlass)
    if self.isQueryIdNonEmpty(f["queryId"]):
      modelForm = modelFormKlass(
          instance=modelKlass.objects.get(id=f["queryId"])
          )
    else:
      modelForm = modelFormKlass()

    cmdModel = Command.objects.only("id").get(
        app="theory.apps",
        name="modelUpsert"
        )
    scanner = CommandClassScanner()
    fieldNameVsDesc = scanner.geneateModelFormFieldDesc(modelForm)
    if self.isQueryIdNonEmpty(f["queryId"]):
      fieldNameVsDesc["id"] = {
          "errorMessages": {
            "required": "This field is required.",
            "invalid": "Enter a whole number."
          },
          "widgetIsContentChgTrigger": False,
          "required": False,
          "initData": f["queryId"],
          "label": "id",
          "helpText": "",
          "showHiddenInitial": False,
          "localize": False,
          "widgetIsFocusChgTrigger": False,
          "type": "IntegerField"
          }
    try:
      val = json.dumps({
        "cmdId": cmdModel.id,
        "fieldNameVsDesc": fieldNameVsDesc,
        "nextFxn": "upsertModelLst",
        # Needed for the model form's save fxn when users call this cmd thru
        # history
        "appName": f["appName"],
        "modelName": f["modelName"],
        "isInNewWindow": f["isInNewWindow"],
        },
        cls=TheoryJSONEncoder
      )
    except Exception as e: # eval can throw many different errors
      import logging
      logger = logging.getLogger(__name__)
      logger.error(e, exc_info=True)
      raise ValidationError(str(e))

    if not f["isInNewWindow"]:
      self.actionQ.append({
        "action": "cleanUpCrt",
        })
    self.actionQ.append({
      "action": "buildParamForm",
      "val": val
      })
